# Observer avant d'autoriser

Le mode autonome d'une VM ne se décide pas sur une impression. Le dernier critère de
maturité du ROADMAP le dit : **au moins quatre semaines en `human_only` sur un parc réel,
avec un taux de recommandations disruptives fausses mesuré et jugé acceptable.** Cette page
décrit comment mener cette observation et lire ce qu'elle mesure.

Pendant l'observation, Glorfindel détecte, enquête et décide comme en production, mais
n'exécute rien : chaque décision devient une carte (« isoler la VM, 92 % — retenu par le
mode `human_only` »). L'opérateur dit, pour chaque carte, si la recommandation était juste.
Le rapport compte.

## Mise en place

1. **Des identifiants en lecture seule.** Un principal de service avec les rôles *Reader*
   et *Log Analytics Reader* sur le périmètre observé, rien de plus. Ses identifiants dans
   `.envrc` (jamais dans le dépôt), et `GLORFINDEL_READ_ONLY=1` : toute tentative d'écriture
   lèverait une erreur claire au lieu d'atteindre Azure.
2. **Le mode `human_only` partout.** C'est le défaut ; vérifier qu'aucune section
   `autonomy` de `glorfindel-config.yaml` ne passe un actif en `non_disruptive`.
   `glorfindel list` affiche le mode résolu par VM.
3. **Le workspace Log Analytics** dans `glorfindel-config.yaml` (`monitoring_backends`), et
   les règles de détection livrées (`assets: [auto]`).
4. **Une alerte qui arrive** : webhook (`GLORFINDEL_WEBHOOK_URL`) ou bot Discord. Sans elle,
   les cartes s'accumulent sans que personne les voie.
5. `make glorfindel-start` (il refuse de démarrer sans `AZURE_SUBSCRIPTION_ID`), puis
   vérifier dans `make glorfindel-logs` que la découverte trouve les VMs
   (`heartbeat → N VM(s)`).

Les règles des environnements de test s'appliquent : lecture seule d'abord, et rien de ces
environnements dans le dépôt public — ni nom, ni identifiant, ni rapport.

## Pré-observation sur le banc (H0)

Avant le parc réel, l'observation tourne sur le banc (décision du 15/10) : bree, une VM du banc
allumée en continu et non inscrite (`always_on`, `enrolled: false` dans
`infra/terraform/config.yaml`), et Glorfindel sur une petite VM dédiée,
pour que le `watch` n'ait pas de trou (`infra/glorfindel-host/README.md`). Une VM allumée mais vide ne produit presque aucun bruit
bénin : quatre semaines sans fausse alerte n'y prouveraient rien. Bree porte donc une vraie
charge — un petit site, des crons, les mises à jour automatiques, la sauvegarde de la nuit.
Les exercices d'Annatar et de Gothmog sont marqués (B2) et sortent du rapport. Cette
pré-observation démarre l'outillage et calibre le bruit ; elle ne compte pas pour le critère
« quatre semaines sur un parc réel ».

**Un scanner qui revient.** En observation rien n'est bloqué : le même attaquant revient et ouvre une carte à chaque visite (une fois la précédente acquittée). La carte le dit (« ↻ same IP seen 2× in 7 days — judged right ») — elle n'est jamais jugée à ta place —, et le rapport compte les attaquants derrière les blocages (« blocks 4 for 2 IPs »).

**Le résumé du lundi.** Avec le bot Discord, chaque lundi matin le salon reçoit le compte de la semaine — le même que `glorfindel report --since 7d`.

**Le modèle.** Depuis le 19/10, le Glorfindel de l'observation (VM hébergée) décide avec `claude-sonnet-5-5` (harnais : 36/36 bonnes décisions, 0 erreur sûre d'elle ; `claude-sonnet-4-6` : 32/36 et 4). Les cartes d'avant le 19/10 viennent de `claude-sonnet-4-6`. Run de bout en bout fait le 19/10 (T1486 → isoler 0,80 ; T1110.001 → bloquer 0,88) : c'est le défaut du code depuis (#139).

**Garder les verdicts.** Ils ne vivent que sur l'hôte de Glorfindel : une copie par semaine
(`make imladris-pull` sur la VM hébergée, Imladris, anciennement H0) évite de perdre l'observation avec un disque.

## Juger chaque carte

Pour chaque carte de décision, juger la recommandation **comme si elle avait été
exécutée** :

| Verdict | Quand |
|---|---|
| `right` | la menace était réelle et l'action proportionnée |
| `wrong` | faux positif, ou action disproportionnée ou erronée (isoler une VM pour une sauvegarde nocturne) |
| `unsure` | impossible de trancher avec ce qu'on sait |

Dans la console, page Glorfindel (`/glorfindel`), la liste **TO JUDGE** (colonne de gauche, 16/10 ; le seul endroit où l'on juge une carte depuis le 26/10) : les cartes de décision des 7 derniers jours sans verdict — en attente ou déjà acquittées, les cartes d'exercice comprises et marquées (H-1, 26/10) —, chacune avec une note facultative et **✓ Right** / **✗ Wrong** / **? Unsure** — un verdict donné là ou dans Discord acquitte aussi la carte (un seul clic) ; l'en-tête affiche le compte de la semaine (cartes, jugées, part des isolations et blocages jugés faux). Les mêmes boutons restent sur les cartes de décision. En ligne de
commande, avec l'identifiant (ou ses 6 premiers caractères) affiché par `glorfindel pending` :

```bash
glorfindel verdict 3f2a91c0 wrong --note "rattrapage apt du matin"
glorfindel verdict 3f2a91c0 right
```

**Une action disruptive autonome exécutée et vérifiée a sa carte, à juger (JUG1, #760, 12/11).** En
`non_disruptive` ou `full_auto`, un isolement (`isolate_vm`) ou un blocage (`block_suspicious_ip`) que
Glorfindel fait seul, et dont la vérification tient, crée une carte « exécutée » (`autonomous_action`,
`_record_executed`, `glorfindel/agent.py`) : l'action, la VM, les preuves (quelques valeurs de la ligne
de la détection), la vérification relue sur Azure et le mode. Elle entre dans TO JUDGE, se juge comme
les autres (**Right** si l'action était justifiée et proportionnée, **Wrong** sinon) et compte dans le
taux des disruptives jugées fausses — c'est l'indicateur « actions disruptives à tort » de l'accueil.
Elle ne change rien à l'action ni à l'autonomie : aucune approbation en un clic, aucun bouton qui
défasse ; si elle est jugée à tort, elle se défait par le chemin habituel (`glorfindel release`,
`glorfindel unblock`, ou les boutons de la carte de la VM), que ses étapes nomment. **Une seule par
action** (sa clé : le signal du cycle, la VM, l'action, l'adresse), même après un redémarrage de la
watch ; un `snapshot` ou une levée n'en crée pas ; une seconde action, même sur la même VM, a sa propre
carte, jamais repliée dans celle d'une autre : chacune se juge et compte. Mesuré au banc le 12/11 avant JUG1 : l'isolement autonome et vérifié de gondolin (le T1486)
n'avait laissé aucune carte à juger. Une vérification en échec, elle, devient toujours une carte
`verification_failed`, et une action retenue par le mode sa carte `mode_hold`.

**Une carte dont l'heure n'a pas de fuseau reste dans TO JUDGE** (VP1c, #920, 19/11). Une heure sans
fuseau (ou illisible) n'est jamais comparée à une heure qui en a un, ni prise pour de l'UTC : où elle
tombe n'est pas connu, et jamais deviné. La carte reste dans la liste quelle que soit la période,
en tête (aucune limite ne la coupe), marquée « ⚠ time unreadable — judge it all the same »
(`time_unreadable` dans `/api/to-judge`), pour être jugée quand même ; elle n'a pas de récurrence et
n'entre dans celle d'aucune autre. Le bot garde son message à jour et ses boutons de verdict ; ses
boutons d'action refusent (« heure illisible (sans fuseau) ») : son âge n'est pas connu.
`glorfindel pending` la montre, son heure telle qu'écrite, « age unknown ». Mesuré à la relecture
de VP1b : une seule de ces cartes faisait tomber toute la liste et le rapport (`TypeError`).

**Une carte non attribuée le dit** (SLF1, #929, 19/11). Une détection qui ne nomme aucune VM (aucune
VM surveillée n'a fait l'appel) est rangée sur une VM d'ancrage ; sa ligne de TO JUDGE, sa note, son
titre, le champ « Ressource » de Discord et `glorfindel pending` disent « not attributed » (« non
attribuée ») et ses candidates, jamais le nom de cette VM comme ressource. Juger la carte, c'est juger
la détection : la VM concernée est à trouver avant d'agir ([glorfindel.md](glorfindel.md), « La voie
de retour de la watch »). Les écritures de la voie de retour de la watch elle-même ne font plus de
carte : comptées sur la règle `data-exfiltration-blob`.

Dans la console, **une ligne de TO JUDGE ouvre sa carte** (ses détails, une note, son verdict), et une
tuile qui replie plusieurs cartes (« ×6 ») les montre toutes dans ses détails, chacune avec sa raison,
son explication et son chemin vers le verdict.
**Plusieurs cartes se jugent d'un geste** (JUG3, #980) : cochées dans TO JUDGE ou dans la fenêtre d'un
groupe (« to judge ×N »), elles reçoivent un même verdict et une même note, après un récapitulatif ;
chacune comme par son propre bouton, son verdict puis son acquittement, et compte pour elle seule dans
les indicateurs. Un échec est dit carte par carte ([design/console.md](design/console.md), « Juger
plusieurs cartes »).

**Un verdict proposé sur la carte d'exercice attendue** (VP1, #615, `docs/design/drill-banc.md` §8.2).
Le drill de la semaine déclare la détection qu'il attend (sa règle, sur sa cible, dans un délai après
le T0) : la carte d'exercice qui l'est — la première du fil — reçoit un **verdict proposé**, `right`,
calculé par la watch sur Imladris. C'est un champ à part (`proposed_verdict`), jamais le verdict :
la carte reste dans TO JUDGE, son compte compris, et **ni le rapport ni les indicateurs ne le
comptent** — seuls les verdicts posés comptent. L'opérateur le confirme d'un clic (console ou Discord :
il devient son verdict, `verdict_from: proposed`) ou le refuse (il s'efface, et n'est jamais reproposé).
Rejugée ensuite à la main, la carte porte le verdict de l'opérateur, et ne dit plus qu'il vient de la
proposition (`verdict_from` retiré, VP1b).
Il ne compare que la détection, jamais la décision : ne le confirmer que si l'action était
proportionnée. Une carte d'exercice sans proposition dit pourquoi (une autre règle, une autre VM,
hors du délai ou de la fenêtre, une seconde carte, deux versions du drill…). Les cartes d'exercice
restent hors du rapport, comme avant.

Le verdict est indépendant de l'acquittement : on peut juger une carte avant ou après
l'avoir acquittée. Une carte qui se répète (« 12× depuis 3 h ») compte une seule fois. La
note est gardée avec le verdict : c'est elle qui dira, plus tard, quelle règle affiner.

Les cartes de posture, de règle proposée, de préparation, de TTL et les alertes de la
réaffirmation ne sont pas des décisions sur une détection : elles n'entrent pas dans le
rapport.

## Le rapport

```bash
glorfindel report --since 7d       # la semaine
glorfindel report --since 4w       # la période d'observation
glorfindel report --since all --json
```

Il donne, par action recommandée et par règle de détection, le nombre de verdicts justes,
faux, incertains et de cartes non jugées, et surtout le **taux de recommandations
disruptives fausses** : parmi les recommandations d'isoler ou de bloquer qui ont été
jugées, la part fausse. Depuis B4a, les mêmes cartes aussi par tranche de confiance, par règle ×
tranche, au-dessus du seuil de la porte et par provenance (plus bas, « Par confiance et par
provenance »). (`GET /api/report?since=7d` renvoie la même chose.)

Les cartes d'exercice n'y entrent pas (B2, 16/10) : une carte dont la VM était couverte par la
fenêtre d'un injecteur (Annatar, puis Gothmog) porte `source: exercise` et le rapport la compte
à part (« N exercise card(s) left out »). Celles qui existent restent pourtant dans la liste TO
JUDGE, marquées (H-1) — la carte « exécutée » d'un isolement autonome d'un exercice aussi (plus haut) : une fenêtre d'exercice est l'affirmation de l'hôte des injecteurs, et une carte cachée
sur cette seule foi laisserait passer une vraie attaque qu'une fenêtre forgée couvrirait. Un compte créé à la main pour un test, comme celui du
16/10 sur bree, n'est pas un exercice déclaré : il compte, d'où la note du verdict.

Une carte dont l'heure n'a pas de fuseau, ou ne se lit pas (VP1c), n'est comptée dans aucune
période : dans la fenêtre ou non, on ne le sait pas, et on ne le devine pas. Le rapport la compte à
part, `undated` (« N card(s) left out: their time carries no time zone… ») ; `--since all`, sans
fenêtre à trancher, la compte comme les autres.

Une carte non jugée n'entre pas dans le taux. Un taux calculé sur trois cartes ne dit rien :
le rapport donne aussi les effectifs.

### Par confiance et par provenance (B4a, #991)

Le seuil de la porte de l'autonomie (`GLORFINDEL_CONFIDENCE_THRESHOLD`) ne reposait sur aucune
mesure : quelle part des décisions à 0,9 est jugée juste, on ne le savait pas. Le rapport compte donc
aussi les mêmes cartes (dans la période, exercices écartés) par la confiance de la décision jugée. Il
les lit sur les cartes seules : aucun appel au cloud ni au modèle, et rien de ce que lit le modèle ne
change (`glorfindel/calibration.py`).

- **Les tranches** : ]0 ; 0,5[, [0,5 ; 0,7[, [0,7 ; 0,8[, [0,8 ; 0,9[, [0,9 ; 1]. Chacune est fermée
  en bas et ouverte en haut ; la dernière est fermée à 1. Chaque case donne `right`, `wrong`, `unsure`,
  `not judged` et l'effectif jugé (`judged` : right, wrong et unsure).
- **Trop peu.** Sous 10 cartes jugées, une case dit « too few » au lieu d'un pourcentage
  (`too_few: true`, `right_share: null` en `--json`). La part est celle des cartes jugées justes parmi
  les cartes jugées. Un `unsure` compte dans l'effectif sans être jugé juste : quand on règle une
  porte, c'est le côté où se tromper. Le taux de disruptives fausses garde sa définition : les fausses
  parmi les justes et les fausses.
- **Par règle × tranche** : les mêmes colonnes, une ligne par tranche où la règle a des cartes.
- **Au-dessus du seuil** : les cartes à une confiance ≥ seuil, sans filtre d'action. C'est la
  comparaison même de la porte (`_apply_confidence_gate`, `glorfindel/agent.py`), mais la porte ne
  s'applique qu'aux `AUTONOMOUS_ACTIONS` : ce compte ne dit pas ce que la porte a laissé partir. Le seuil se résout
  comme celui de la porte (`glorfindel.config.confidence_threshold`, que lit `_confidence_threshold()`) :
  0,7 sans variable. Une valeur mal formée le rend infini : aucune action ne part seule, rien n'est
  au-dessus, et le rapport le dit (`threshold: null`, « GLORFINDEL_CONFIDENCE_THRESHOLD invalid »). C'est
  le seuil de l'environnement qui lance le rapport ; sur Imladris, celui de la watch.

**Quelle confiance compte.** Celle que la carte montrait quand elle a été jugée, son `confidence`. La
carte la porte à côté de la raison et de l'explication que l'opérateur a lues. Un nouveau
déclenchement qui la change d'au moins 0,1, qui monte la sévérité ou qui dit une compromission
réécrit les trois ensemble et garde la première dans
`first_confidence`, qu'aucune console, aucun bot, aucune commande n'affiche. Le verdict juge donc ce que
la carte montrait, jamais la première décision. Deux cas sortent des tranches, comptés à part
(`confidence_unknown`, « N card(s) left out of the bands ») :
- **aucune confiance** : 0 est la valeur par défaut d'une carte écrite sans décision du modèle (un cycle
  en échec, une détection sans décision, le geste d'un opérateur dont la vérification échoue) et d'une
  décision dont la confiance ne se lisait pas ; la console et Discord n'en affichent pas. Ce qui n'est
  pas un nombre de ]0 ; 1] non plus ;
- **une carte mise à jour après son verdict** : `glorfindel verdict` laisse la carte en attente, et un
  nouveau déclenchement peut la réécrire. Une carte dont la confiance a déjà été réécrite une fois
  (`first_confidence`) et qui a connu **toute mise à jour après le verdict** sort des tranches :
  `updated_at` bouge avec la réécriture de sa confiance, mais aussi avec `refresh()` et
  `note_identity_check`, et ne les distingue pas. La confiance jugée n'est pas devinée : c'est le côté
  prudent. Un verdict donné dans la console ou sur Discord acquitte la carte, que plus rien ne
  réécrit. Jugée de nouveau, la carte compte à la confiance qu'elle montre.

**La provenance.** Une carte ne porte pas sa zone. La zone d'inscription (`eregion-zone`,
`eregion_core/inscription.py`) est une étiquette de la VM : elle ne se lit que par un appel à Azure, et
la plupart des VMs surveillées n'en ont pas. L'inscription est faite pour les cibles des injecteurs :
une VM d'un parc réel n'est pas inscrite, et bree, la VM de la pré-observation, non plus. Le rapport
lit donc la provenance sur la carte seule, par son `resource_id` :
- `bench` : la VM est dans le périmètre du banc tel que le dessine la garde des injecteurs
  (`Scope.check` : l'abonnement d'`AZURE_SUBSCRIPTION_ID`, un groupe de ressources de Celebrimbor,
  `rg-celebrimbor` ou `rg-celebrimbor-*`), bree comprise. Les critères avant le mode autonome ne comptent pas ces cartes
  (`ROADMAP.md`, « Critères avant le mode autonome ») ;
- `unknown` : tout le reste. Hors du périmètre, le jumeau, la production et tout autre parc ne se
  distinguent pas encore. S'y ajoutent toutes les cartes d'un rapport lancé sans `AZURE_SUBSCRIPTION_ID`, et une
  carte non attribuée (SLF1 : sa VM est celle où elle est rangée, pas celle dont elle parle), qu'elle
  porte `attribution` ou l'ancien type `unattributed_signal` (`escalations.unattributed`).

Pour dire `twin` et `production`, il faudrait que l'opérateur déclare la provenance de chaque périmètre
surveillé (dans `glorfindel-config.yaml`, par exemple), et que la carte l'écrive à sa création.

**Le plafond d'une règle (RDW1, #994).** Une détection d'une règle plafonnée (`ransomware-disk-write`)
fait, en `human_only`, deux cartes : `mode_hold`, qui propose l'instantané, et `ceiling_proposal`, qui
propose l'isolement. Le rapport compte donc deux verdicts pour une seule détection, tous deux à la
même confiance : celle que le modèle donnait à l'isolement qu'il proposait. En `non_disruptive`,
l'instantané part seul et seule la carte du plafond est à juger.

**Ce qui reste à B4 (#75)** : étiqueter les détections d'une observation réelle, hors du banc ; en tirer
la précision des règles et des décisions sur du vrai trafic ; verser des cas anonymisés au harnais. Ce
rapport en est l'instrument, il ne la mesure pas encore.

## Ce que les chiffres décident

À fixer avant de commencer, pour ne pas les ajuster aux résultats :

- **Le seuil** : à partir de quel taux de recommandations disruptives fausses une VM peut
  passer en `non_disruptive` ? Avec combien de recommandations jugées au minimum ?
- **Par règle** : une règle qui produit des verdicts `wrong` est-elle affinée (seuil,
  exclusion) avant d'activer l'autonomie sur les actifs qu'elle couvre ?
- **Les VMs** : l'autonomie s'active VM par VM (contrôle de préparation, réserves
  confirmées) — lesquelles en premier ?

Ces seuils sont une décision de l'opérateur, pas du code.

## Et le confinement ?

L'observation mesure la décision, jamais le confinement : en `human_only`, rien ne s'exécute. Le
temps pour contenir et la part contenue seule restent donc vides sur Imladris. Ils se mesurent sur le
banc, sur une VM `bench` en `non_disruptive`, le temps d'une campagne déclarée (BL1, #280) :
[`banc-bl1.md`](banc-bl1.md). Les définitions sont dans [`analysis.md`](analysis.md), « Temps
pour contenir et part contenue seule ». Les cartes de cette campagne sont des cartes d'exercice
(B2) : elles n'entrent pas dans le taux de recommandations disruptives fausses de l'observation.

**D'où viennent les chiffres (SEC9).** La décision, son exécution, sa relecture et sa tenue viennent
de la watch, dans ses propres fichiers. Le T0 de chaque attaque, la liste des runs et l'effet d'une
panne viennent de l'hôte des injecteurs, par le canal ; l'hôte de la watch les confronte à ce qu'il
tient avant qu'ils comptent :
- un T0 hors de la fenêtre de son run, ou après ce que la watch a reçu ou vu de la VM, ne compte
  pas au temps pour contenir, et c'est dit ;
- un run que la watch a vu et que le manifeste ne donne pas exécuté, ou que le contrôle du canal
  écarte, compte, sa décision inconnue ;
- une panne dont le rapport n'a pas les lectures de la télémétrie qui montrent son effet n'est pas
  mesurée. Ces lectures sont vérifiées dans leur cohérence (des lectures par cible, `ok`, datées
  dans la panne), pas relues par la watch.

Cette confrontation vaut pour le rapport de campagne et la page d'une campagne ; l'accueil de la
console et le suivi de Dagorlad suivront.

Le détail est dans [`analysis.md`](analysis.md), « D'où vient chaque entrée ».
