# Le run du banc en un geste — un créneau armé, le restore pour seul geste humain (BNC2)

_Conception — 10/11 (BNC2, #684) — statut : **conception seulement**, à relire en Opus 5.5. Rien
n'est codé, armé ni mesuré. L'armement reste à Jonathan. Elle prolonge le drill du banc
([`drill-banc.md`](drill-banc.md), DRL1) et le banc lisible par la machine (BNC1, #682), et porte
les quatre décisions de Jonathan du 10/11 (§1)._

> **Décision de Jonathan (10/11, « security by design »).** Un run du banc doit tenir en **un seul
> geste humain**, celui du produit : approuver le restore. Le reste s'exécute, se mesure et se
> rapporte seul. Quatre règles cadrent toute la conception (§1.2) :
> 1. **le lancement** garde la propriété de DRL1 — « Orodruin ne tire rien et n'écoute rien » ;
> 2. **la signature** ne couvre que le lancement, jamais le restore ;
> 3. **le restore** reste le geste humain du produit, sur la carte de H0 ;
> 4. **le rapport** se compose là où les droits existent déjà, sans identité nouvelle.

## En bref

DRL1 arme un **drill hebdomadaire**, non destructif, qui joue T1136.001 et laisse la watch décider.
BNC2 arme, **à côté de lui**, un **créneau unique daté** qui déroule le **scénario de référence
entier** — le rançongiciel T1486 de [`docs/banc-t1486.md`](../banc-t1486.md) — de l'attaque jusqu'à
la levée. La différence tient en une phrase : le drill mesure une détection chaque semaine ; le
créneau rejoue la chaîne complète, destructif compris, pour dater à froid le confinement et le
service rendu.

Ce que BNC2 **garde** de DRL1 : l'armement par Jonathan ; le minuteur d'Orodruin, qui ne tire ni
n'écoute rien ; le permis fermé par défaut ; le verrou « un run à la fois » ; le registre ; l'arrêt
du service ; tout ce que le modèle de menace de DRL1 (§7) tient déjà.

Ce que BNC2 **change** : le créneau est **unique et daté** (pas une récurrence hebdomadaire) ; le
scénario est **destructif**, donc la cible est **nommée et tapée** à l'armement, zone `bench` seule ;
la chaîne comprend un **restore** (le geste humain) et une **levée** (REC1).

```
Jonathan ── arme un créneau daté ───▶ Orodruin (minuteur à usage unique)
                                          │ à l'heure armée
   image signée (le scénario) + armement + horloge ─▶ le créneau   (décident)
   V1, permis, nom tapé, zone, isolation ───────────▶ le créneau   (refusent seulement)
                                          │ demande → exercise_runner (chemin DG-b)
                                          ▼
   préflight (BNC1) ─ point ─ T1486 ─ détection ─ isolement autonome vérifié (DRN1)
                                          │
                        carte de restore ──▶  ⏸  attend l'humain  (état sûr : VM isolée)
                                          │ Jonathan approuve (console, ou bot + TOT1)
                                          ▼
   restore (geste humain) ─ levée par la watch de H0 (REC1, REC1b) ─ rapport composé seul (BNC1, sur H0)
                                          │
                       Discord (fil du run, masqué) + runs/bench/<run_id>.json ──▶ plus tard proofs.json (PR relue)
```

---

## 1. Le but, et ce qui ne change pas

### 1.1 Le but

Le rejeu T1486 du 09/11 (`~/eregion-banc/t1486-2026-11-09.md`, hors dépôt) a duré 4 h 24. La moitié
venait de deux défauts du restore (RST1, #680) ; l'autre moitié, de la façon de faire : chaque
vérification et chaque mesure tapée à la main, les sorties masquées puis recopiées pour reconstruire
la chronologie. BNC1 (#682) automatise déjà les deux bouts (le préflight, le rapport). BNC2 ferme
la boucle au milieu : **l'attaque et la mesure s'enchaînent seules**, et il ne reste à l'humain que
le geste du produit — approuver le restore.

Ce que le banc gagne à être automatisé : il rejoue le scénario de référence sans 4 h de clavier, il
en date le confinement et le service rendu à cadence régulière, et chaque run devient une preuve
datée et sourcée pour `docs/proofs.json` (§5). C'est un des cinq indicateurs de la 1.0 : l'âge de la
dernière preuve sous 30 jours.

### 1.2 Les quatre décisions qui cadrent la conception

| | Décision | Où elle vit dans ce document |
|---|---|---|
| **1. Le lancement** | Un run part d'une commande du poste, ou d'un **créneau unique armé à l'avance** (« joue T1486 demain à 10:00 sur gondolin »), une extension du minuteur de DRL1. Aucun chemin distant ne déclenche une attaque. Ce qui arrive de l'extérieur ne peut que **refuser** (le battement de la watch, le permis, « Stop all ») | §2, §3 |
| **2. La signature** | Elle ne couvre que le lancement : la technique, la cible au nom tapé, le banc seul, un **usage unique**, une **expiration**. Le restore n'est **jamais** pré-approuvé | §2.3, §4 |
| **3. Le restore** | Il reste le geste humain du produit, sur la carte de H0, depuis la console ou le bot (TOT1 pour le bot) | §4 |
| **4. Le rapport** | Il se compose là où les droits existent déjà : **H0** (qui lit déjà le journal d'activité, les jobs du coffre et la vue d'instance pour REC1), à partir du code de BNC1. Publié masqué dans le fil Discord du run et dans un fichier. Une session Banc ne lit que ce rapport. Aucune identité nouvelle, aucun droit élargi | §5 |

### 1.3 La règle de production, inchangée

BNC2 ne touche pas la règle de production (`eregion_core/inscription.py`, O0) : jamais de panne ni
d'action destructive sur une charge réelle. T1486 est destructif ; il ne joue donc que sur le
**banc** (zone `bench`), jamais `twin` ni `production`. Le créneau exige la zone `bench` au jugement
**et** avant chaque fil, comme DRL1, plus strict que la règle de production. La cible nommée à
l'armement est une VM inscrite `bench` ; `all` est refusé.

---

## 2. Le créneau unique armé

### 2.1 Ce qui change dans DRL1, et ce qui ne change pas

DRL1 porte un **drill livré** (`drills/banc-hebdo.yaml`) avec un bloc `schedule` **récurrent**
(`day: tue, at: "19:00"`) que le minuteur d'Orodruin rejoue chaque semaine. BNC2 n'ajoute pas un
second drill récurrent : il ajoute un **créneau unique daté**, à côté du drill hebdomadaire, sur la
même machinerie (`eregion_core/scheduled_drill.py`, le permis, le verrou, le registre, l'arrêt du
service).

| Ce dont il s'agit | DRL1 (drill hebdomadaire) | BNC2 (créneau unique) |
|---|---|---|
| **Occurrence** | récurrente (`OnCalendar` hebdomadaire, `Persistent=false`) | **une seule**, datée (`OnCalendar` à une date précise, ou un minuteur à usage unique) ; jouée une fois, puis inerte |
| **Scénario** | T1136.001, `destructive: false` | **T1486**, `destructive: true` — le scénario de `docs/banc-t1486.md` |
| **Cible** | nommée à l'armement (`TARGETS=gondolin`), pas tapée (non destructif) | **nommée et tapée** à l'armement, comme un fil destructif de Dagorlad (DG-b) |
| **Ce qui joue** | un fil, la détection mesurée par VP1 | la **chaîne entière** : préflight, point, attaque, détection, isolement, carte de restore, restore, levée, rapport |
| **Geste humain pendant le run** | aucun (VP1 propose un verdict, Jonathan le confirme après) | **un seul** : approuver le restore |

**Ce qui ne change pas de DRL1** : l'armement reste un geste de Jonathan ; le minuteur ne tire ni
n'écoute rien ; trois entrées décident (l'image, l'armement, l'horloge) et ce qui vient du dehors ne
peut que refuser ; le permis fermé par défaut ; le verrou « un run à la fois » ; l'arrêt du service à
`RuntimeMaxSec` ; le journal avant chaque appel.

### 2.2 Le scénario pris dans l'image signée

Le scénario joué est **déclaré dans le dépôt** et **pris dans l'image des injecteurs**, jamais
construit à l'armement :

- il vit dans un **drill livré** (`drills/banc-t1486.yaml`, DG-d), relu en PR, du même format exact
  que `banc-hebdo.yaml`, avec un bloc d'occurrence unique (§2.3) ;
- son fil nomme l'expérience **T1486** du catalogue (`technique_catalog.yaml`), par un sélecteur de
  zone (`{zone: bench}`), jamais un nom de VM ni un identifiant ;
- son empreinte est le **sha256 du fichier entier**, octet pour octet, épinglée à l'armement, comme
  DRL1 (décision 5 de DRL1). Une PR qui change le scénario change l'empreinte : `drill_changed`,
  rien ne part jusqu'au réarmement de Jonathan.

**La condition destructive, admise sous conditions strictes.** DRL1 refuse `destructive: true` dans
un bloc planifié (`banc-hebdo` est non destructif par règle). BNC2 doit lever ce refus **pour le
créneau unique seul**, et seulement parce que trois gardes le resserrent en même temps :

1. la zone `bench` exigée au jugement et avant chaque fil (jamais `twin`, jamais `production`) ;
2. la cible **nommée et tapée** à l'armement, comparée par Orodruin au nom qu'Azure lui donne
   (`typed_name`, DG-b) — un fil destructif n'agit jamais sans ce nom ;
3. l'**usage unique** et l'**expiration** (§2.3) : un créneau joué, ou expiré, ne rejoue jamais.

Le lecteur du drill distingue donc **deux formes de planification** : un bloc récurrent, qui refuse
le destructif (DRL1) ; un bloc à occurrence unique, qui l'admet pour la zone `bench` et une cible
tapée (BNC2). Le choix est dans la structure du fichier, pas dans un drapeau de ligne de commande, et
un test de CI relit chaque drill livré contre sa forme.

### 2.3 L'armement d'une occurrence datée

**Rien n'est posé avant l'armement.** La vérification à blanc n'écrit rien ; l'armement pose l'unité
et active le minuteur, dans le même geste, celui de Jonathan.

| Cible Make (depuis le poste) | Fait |
|---|---|
| `make orodruin-bench-check [DRILL=banc-t1486 TARGETS=gondolin AT=…]` | à blanc : relit le drill dans l'image d'Orodruin, son empreinte, le contrat, la watch, la cible et la date ; dit ce que ferait l'occurrence et quand. Aucune écriture |
| `make orodruin-bench-arm DRILL=banc-t1486 TARGETS=gondolin AT=2026-11-12T10:00Z` | **Jonathan.** Écrit le fichier d'armement, pose l'unité systemd à usage unique, active le minuteur ; écrit le **permis** dans le canal sous l'identité de l'opérateur ; publie `orodruin/bench.json` |
| `make orodruin-bench-disarm` | désactive le minuteur, retire l'unité et l'armement ; **supprime le permis** ; publie « désarmé » ; dit chaque pas, et sort en erreur si l'un manque |

**Le fichier d'armement** (`~/bench/armed.json`, mode 600, hors de `~/runs`, monté en lecture seule
dans les conteneurs) dit, comme DRL1, avec un champ de plus :
- le nom du drill et son empreinte sha256, lue dans l'image au moment d'armer ;
- le nom de la cible ;
- **l'heure armée de l'occurrence unique** (`at`) ;
- l'heure de l'armement, le commit de l'image.

Il ne contient aucun identifiant, aucun secret.

**L'unité, à usage unique.** `eregion-bench.timer` porte un `OnCalendar` à **date précise**
(`2026-11-12 10:00:00 UTC`), `Persistent=false` : une occurrence manquée (Orodruin éteint à l'heure)
n'est **jamais rattrapée**. Elle est dite manquée, et le créneau reste à réarmer. Le service
`eregion-bench.service` est le `docker run` durci de DRL1 (ORO_HARDEN, `--init`,
`RuntimeMaxSec`, `ExecStop=-docker stop --time 90`, la racine en lecture seule, l'armement en
lecture seule), avec une commande fixe, `python -m eregion_core.scheduled_drill run --slot bench`,
sans argument venu d'ailleurs.

**L'usage unique est tenu par le registre, pas par le minuteur seul.** Le registre (sous le verrou,
§3) note le créneau joué : rejoué malgré un `OnCalendar` réécrit ou un déclenchement à la main du
service, il refuse `already_played`. Le minuteur à date fixe ne part qu'une fois ; le registre tient
l'usage unique même si le minuteur est forcé.

**L'expiration.** Au-delà de l'heure armée, le créneau se ferme. Deux bornes se cumulent :
- l'**heure dans les 30 min** qui suivent l'heure armée (`off_schedule`), comme DRL1 : un
  déclenchement à la main hors de la fenêtre est refusé ;
- le **permis**, réécrit par chaque occurrence et supprimé par la rétention du canal (9 jours, §2.4
  de DRL1) : un créneau armé puis jamais joué (Orodruin éteint deux semaines) voit son permis
  expirer, et `no_permit` ferme au lieu d'ouvrir.

### 2.4 La cible nommée à l'armement

La cible se donne par son nom à l'armement (`TARGETS=gondolin`), jamais dans le drill livré (le dépôt
est public). « Jamais choisie à la place de l'opérateur » (Jonathan, 03/11) : il la choisit une fois,
en armant. `all` est refusé. Parce que T1486 est destructif, le nom est aussi **tapé** au moment de
l'armement et comparé par Orodruin, à chaque injection, au nom qu'il lit de la VM (`typed_name`,
DG-b). Une lecture d'Azure qui échoue là est un refus dit (`typed_name: the target's name
unreadable`), jamais une exception (#358).

### 2.5 Ce qui peut refuser

Comme DRL1 (§2.3), le service relit dans l'ordre et refuse au premier manque : armement présent,
drill de l'image et empreinte épinglée, catalogue (T1486 au catalogue, du moteur déclaré), heure dans
les 30 min, permis présent et égal, verrou pris, registre (usage unique), demande fabriquée, contrat,
V1, zone `bench`, nom tapé. Ce qui vient du dehors (V1, le permis, l'état de la cible) ne peut que
refuser. Un H0 compromis, ou qui écrit le canal, peut **empêcher** une occurrence, jamais en lancer
une, ni en changer le contenu ou la cible.

---

## 3. Le déroulé du T1486, de bout en bout

Chaque étape dit **qui agit, avec quels droits, et ce qui le prouve**. Le chemin est celui de DG-b
(une demande jugée par `exercise_runner`), avec le démarrage de la cible de DRL1 (§3.1 de
`drill-banc.md`) en plus. Rien n'atteint le banc avant le contrat, V1 et le journal.

| # | Étape | Qui agit, avec quels droits | Ce qui le prouve |
|---|---|---|---|
| 0 | **Le préflight (BNC1)** : l'étape 0 de `docs/banc-t1486.md` en un verdict | Orodruin relit l'armement, l'empreinte, le catalogue, l'heure, le permis (lectures locales et du canal) ; BNC1 relit la santé de H0, les paires, les droits effectifs de chaque principal, l'âge du point | **rouge → rien ne part.** Le service refuse avant toute écriture ; le code de sortie de `bench-preflight` est non nul |
| 1 | **Le verrou et le registre** | `scheduled_drill`, sous `flock` (`request_lock`), le descripteur passé au runner | pris, sinon `busy` ; registre lu (usage unique) puis écrit **avant** le jugement : quoi qu'il arrive, ce créneau est consommé |
| 2 | **Le point de restauration** | Pris par **H0** avant l'attaque, pas par Orodruin : « Eregion Glorfindel Response » porte l'action de sauvegarde du coffre, sur le groupe du banc (`infra/identities/glorfindel-response.json`) | le job du coffre `Completed` ; son heure est le `--before` de l'étape 6 |
| 3 | **L'attaque, par Orodruin** | `annatar wire T1486 <vm> --request <id> --typed-name <nom>`, sous l'identité d'Orodruin (Run Command), journalisée **avant** l'appel, sous le plafond ; la fenêtre d'exercice ouverte | la fenêtre porte l'identifiant de la demande ; le journal d'activité porte le Run Command, appelant « Orodruin » ; `attack_started` émis, T0 |
| 4 | **La détection, puis l'isolement autonome et sa vérification (DRN1)** | La watch de **H0** : `Reader`, `Log Analytics Reader`, « Response », « Session Drain » VM par VM. `isolate_vm` seule, dans le mode de gondolin (`non_disruptive`), au-dessus du seuil | le cycle `isolate_vm`, `verified=True`, T0+… ; la carte dans la console ; DRN1 corrige le délai de coupure (le `verified=False` du 09/11) |
| 5 | **La carte de recommandation de restore, qui attend l'humain** | La watch écrit une carte `restore_from_backup`, recommandée, **jamais autonome** : le restore n'est pas une action de la watch (SEC7) | la carte en attente dans TO JUDGE, marquée exercice ; **le run s'arrête là tant que l'humain n'a rien fait** |
| 6 | **Le restore** (§4) | **Geste humain**, sur la carte de H0, depuis la console ou le bot (TOT1) ; la CLI tourne sous le principal de la console/du bot (Restore, Restore Neutralize, Restore Staging), jamais sous la watch | le job de restore `Completed`, la neutralisation faite ; `runs/console/manual_actions.jsonl` |
| 7 | **La levée, par la watch de H0 (REC1, REC1b)** | La watch de H0 lit la reprise sur Azure (le job fini, sur place, le point antérieur, la VM qui tourne, la neutralisation dans le journal d'activité) et lève **elle-même**, avec son seul `Reader` du groupe | le cycle du `recovery_complete`, `release_isolation` vérifié ; ou une carte « levée retenue » qui dit pourquoi, levée alors à la main |
| 8 | **Le rapport** (§5) | Composé seul sur **H0**, par le code de BNC1 (`bench-report`), avec les droits déjà présents | `runs/bench/<run_id>.json` et son Markdown ; le fil Discord du run |
| 9 | **La remise en état** (§6) | Nettoyage du scénario par le fil ; inventaire des disques sans suppression ; les gestes à froid restent à Jonathan | `glorfindel reset --from-azure --dry-run` : « Aucune règle Glorfindel » |

### 3.1 Ce qui arrête le run

Le run s'arrête, proprement, sur chacun de ces signaux — repris de DRL1 (§3) et de `docs/banc-t1486.md`
(« Ce qui peut mal tourner ») :

- **préflight rouge** (étape 0) : rien ne part, le service refuse avant toute écriture ;
- **battement absent** (V1) : refus `watch` avant tout appel au cloud, après 10 min de relecture (un
  déploiement de H0 en cours) ;
- **« Stop all »** : `make orodruin-kill`, depuis le poste, révoque l'identité d'Orodruin, annule ce
  qui tourne, ferme les fenêtres ; comme DRL1, il désactive le minuteur du créneau et supprime le
  permis, et écrit `orodruin/bench.json` à `disarmed (killed)` ;
- **la carte qui expire** : voir §3.2.

### 3.2 L'état sûr quand l'humain ne répond pas

C'est le cœur de la décision 3. Si personne n'approuve le restore (étape 5), **le banc reste dans un
état sûr** :

- **la VM est isolée** (le NSG de quarantaine, posé par la watch, réaffirmé chaque minute) et le
  **reste** jusqu'à ce qu'un humain la libère ou la restaure. Le drill ne lève jamais une isolation ;
- **rien de destructif ne se produit** : l'attaque T1486 a chiffré des données de test sur la VM du
  banc (`/mnt/testdata`), réversibles par le restore, et recréées par `setup_testdata.sh` au fil
  suivant. Aucune action destructive **de Glorfindel** : `isolate_vm` est réversible, et le restore,
  destructif, n'est jamais autonome ;
- **la carte de restore ne s'exécute jamais seule.** Elle attend, recommandée. Au-delà du TTL
  d'isolation (`GLORFINDEL_ISOLATION_TTL_H`, 4 h par défaut), la watch émet une carte `ttl_exceeded`
  (« isolée depuis 4 h ») et **n'ôte rien** : l'isolement tient, l'escalade monte, mais aucune levée
  ni aucun restore n'est fait sans l'humain ;
- **le créneau est consommé** (le registre, écrit avant le jugement) : il ne rejoue pas de lui-même.
  Un nouveau run demande un réarmement.

Autrement dit : l'absence de réponse humaine **laisse la VM isolée et sûre**, jamais une action
destructive, jamais une levée automatique de l'isolement hors du chemin propre de REC1.

---

## 4. Le restore, geste humain

Le restore est le **seul geste humain** du run, et la décision 2 le protège : **la signature du
créneau ne le couvre jamais.** Ce que le créneau armé autorise, c'est l'attaque (la technique, la
cible tapée, le banc, un usage unique, une expiration) ; le restore reste, à chaque run, un
consentement humain distinct, sur la carte de H0.

- **La carte de H0** (`restore_from_backup`) est produite par la watch, recommandée, jamais
  autonome ; le restore d'une VM n'accepte que la carte de cette VM, jamais une carte ancrée
  (`_restore_refusal`, SEC1).
- **La console** : le bouton 🔄 Restore montre le plan (le moment, les points, SEC4c), puis la
  commande. Le restore part sous le principal de la console (Restore, Restore Neutralize, Restore
  Staging sur le compte de transit — RST1), jamais sous la watch ni sous H0 (SEC7 : H0 ne restaure
  pas). Aujourd'hui il part de la CLI d'un poste ; la voie console/exécuteur suivra FS1g.
- **Le bot (TOT1, #685)** : un restore approuvé depuis le téléphone demande **plus** que la liste
  d'autorisation, parce que c'est une action destructive : le **nom de la VM tapé** (le nom exact de
  la cible de la carte, comme Dagorlad) **et** un **code TOTP** (RFC 6238), vérifié par le bot avant
  tout restore. Un compte Discord compromis ne suffit plus. Sans secret configuré, le restore depuis
  le bot est **refusé**, la raison dite, jamais un repli silencieux. Seules les actions destructives
  (le restore) sont concernées ; un verdict, un acquittement, un « Stop all » restent sans code.
- **L'expiration de la carte.** Une carte exécutable en un clic a un âge maximal
  (`GLORFINDEL_APPROVAL_MAX_AGE_H`, 2 h ; le bot : `_RESTORE_DAYS`, 14 jours pour retrouver ses
  boutons). Passé ce délai, le bouton répond « carte réglée » et rien ne part : le restore d'une
  vieille carte repasse par la CLI et un `--before` explicite. L'isolement, lui, tient tant que
  personne ne lève : la carte expire, la sûreté non.

**Ce que la signature ne couvre jamais, écrit noir sur blanc** : le créneau armé ne porte ni un
restore pré-approuvé, ni une levée pré-approuvée. Les options qui l'exigeraient sont écartées (§10.2).

---

## 5. Le rapport composé seul

### 5.1 Où, et pourquoi là

**Le rapport se compose sur H0**, par le code de **BNC1** (`make bench-report RUN=<run_id>`), et non
sur Orodruin. La raison est la décision 4 : **là où les droits existent déjà.**

| Source du rapport (BNC1) | Droit qu'elle demande | Qui l'a déjà |
|---|---|---|
| le rapport du run, l'état d'isolement, `manual_actions.jsonl` | lecture de `runs/glorfindel/`, `runs/console/` sur H0 | H0 (la watch les écrit) |
| le journal d'activité de la cible (Run Command, appelant, durée) | lecture du journal d'activité du groupe | H0 : `Reader` sur le groupe du banc — il le lit déjà pour REC1/REC1b |
| les jobs du coffre (type, durées) | lecture des jobs du coffre | H0 : `Reader` sur le groupe (le coffre y est) — déjà lu pour REC1 |
| la vue d'instance (agent `Ready`) | lecture de la VM | H0 : `Reader` — déjà lu pour REC1 |

H0 tient déjà tout cela : `Reader` et `Log Analytics Reader` sur le groupe du banc, et le code de
REC1/REC1b qui lit le journal d'activité, les jobs du coffre et la vue d'instance. **Orodruin, lui,
n'a que** `bench_logs_reader` (Log Analytics) et ses droits d'injecteur : composer le rapport depuis
Orodruin demanderait de lui donner la lecture des jobs du coffre et du journal d'activité — **une
identité élargie**, que la décision 4 écarte (§10.2). Composer sur H0 n'ajoute **aucun droit** :
c'est la même identité qui lève déjà l'isolement.

### 5.2 Avec quels droits, et masqué par construction

Le rapport est composé sous l'identité de H0 (la VM), en **lecture seule**. BNC1 le produit **masqué
par construction** : les appelants deviennent un rôle (console, bot, H0, Orodruin, un humain,
inconnu), les ressources un nom du banc déjà public ; aucun GUID, abonnement, IP ni UPN ne sort. Un
test de BNC1 scrute la sortie à la recherche d'identifiants. BNC2 n'ajoute rien à ce masquage : il
réutilise `bench-report` tel quel, déclenché à la fin du run au lieu d'être tapé à la main.

### 5.3 Où il est publié

- **Dans un fichier** : `runs/bench/<run_id>.json` (le JSON, prêt pour `proofs.json`) et son Markdown,
  la forme du compte rendu du 09/11 (« Les chiffres » depuis T0, la chronologie, le tableau des Run
  Command, le `restore_time` en deux nombres) ;
- **dans Discord** : dans le **fil du run**, par le **bot de Glorfindel** (le produit), que H0 tient
  déjà, le texte passé par `chat_text.py`, masqué, sans autre mention que le rôle configuré. Le jeton
  du bot de l'atelier ne va jamais sur H0, et Orodruin n'a pas de sortie Discord (décision 4 de DRL1,
  reprise ici).

**Une session Banc ne lit que ce rapport.** Elle ne reçoit aucune identité nouvelle : elle lit le
rapport publié (le fichier, le fil Discord), et, en témoin indépendant, relit le workspace du banc
avec son seul `Log Analytics Reader` (BRO1), comme pour DRL1.

### 5.4 Comment il alimente `docs/proofs.json`, plus tard

`docs/proofs.json` est la source unique des chiffres du site (ADO2, #671). Chaque figure y porte sa
date, sa nature (`measured`, `to-remeasure`…) et sa **source** : un fichier du dépôt, la phrase qui
donne le chiffre, et l'ancre ou **le run** (`run`) d'où il vient. `scripts/adoption.py` refuse une
figure sans date ni source.

Le run de BNC2 produit des chiffres `measured` (détection, confinement vérifié, `restore_time`,
service rendu), avec le `run_id` pour source. Mais **`proofs.json` n'est jamais écrit directement par
un run** : la chaîne reste une **PR relue**. Un lot (une session, ou un successeur de BNC1, §9)
prend les chiffres du `runs/bench/<run_id>.json`, propose une PR qui ajoute ou met à jour les figures
avec le run comme source, et la relecture Opus 5.5 la valide avant la fusion. Ainsi un chiffre du
site vient toujours d'un run mesuré, mais entre par une porte relue : les chiffres T1486 du README,
aujourd'hui `to-remeasure`, deviennent `measured` run par run, sans écriture automatique.

---

## 6. La remise en état

Elle reprend l'étape 9 de `docs/banc-t1486.md` et la remise en état du 09/11, sans rien supprimer :

- **le nettoyage du scénario** : `setup_testdata.sh` tourne dans le fil, avant l'attaque, et retire
  les fichiers d'un run précédent (`annatar clean` n'est pas nécessaire sur ce chemin). Le disque de
  gondolin, après le restore, est celui d'avant l'attaque ; le fil suivant refait son `setup` ;
- **l'inventaire des disques, sans suppression** (`docs/azure.md`) : un restore `OriginalLocation`
  laisse des disques détachés (l'OS et les données d'origine suivis par Terraform, à garder ; un OS
  de restore jetable). Le rapport **les relève**, ne supprime rien, et signale à l'Infra que le
  prochain `terraform apply` rattachera `clean_lun10` et trouvera un disque OS qui n'est plus celui
  de l'état (`docs/azure.md`) : **le plan est à lire avant tout apply.** La suppression d'un disque
  jetable reste un **geste à froid de Jonathan** ;
- **les gestes à froid** : `make orodruin-stop` et `make celebrimbor-stop` (bree épargnée), le point
  à la demande qui expire seul à 30 jours, le CD de H0 réactivé s'il a été mis en pause. La VM du
  banc s'éteint à 23:00 UTC par son extinction quotidienne.

---

## 7. Le coût

Un run du créneau ne coûte pas plus qu'un rejeu T1486 à la main : il en retire les 3 h 25 de clavier
et d'attente du 09/11, pas le temps machine.

| Poste | Ordre de grandeur, à mesurer |
|---|---|
| Orodruin, allumé pour le run (démarrage planifié de DRL1, §5.1 de `drill-banc.md`) | ~4 h 20 de D2als_v6 par occurrence |
| gondolin allumée ~1 h 30 à 4 h | ~0,15 à 0,40 € (0,10 €/h) |
| Le point à la demande + le point de restore | stockage incrémental, 30 jours, 4–5 à la fois sur gondolin |
| La décision du modèle sur H0 (détection, tirages, recommandation de restore) | ~0,10 à 0,30 $ par run |
| Journaux, canal, Logic App, Discord | négligeable |

**Par mois, à une cadence donnée.** La cadence de BNC2 n'est **pas** hebdomadaire (c'est un créneau
unique, armé quand Jonathan veut dater le confinement et le service rendu) : c'est le drill
hebdomadaire de DRL1 qui tient l'indicateur « dernière preuve sous 30 jours » avec T1136.001. BNC2
sert à **remesurer la chaîne complète** après un lot qui la touche (RST1, DRN1, REC1b) : disons **une
à deux fois par mois**. À deux runs par mois : de l'ordre de **moins de 5 € par mois** de temps
machine, le point de restore et les appels au modèle compris, à confirmer au banc. Une cadence plus
élevée ferait monter surtout le temps d'Orodruin et de gondolin.

---

## 8. Le modèle de menace

BNC2 **n'ajoute pas** de frontière à [`modele-de-menace.md`](modele-de-menace.md) : il **réutilise**
celle que DRL1 propose (§7 de `drill-banc.md`, « 9. Le minuteur d'Orodruin »). Ce qui suit dit ce que
le design **gagne ou perd** par rapport à DRL1, frontière par frontière, et ce qui reste ouvert.

### 8.1 Ce que le design gagne

| Frontière | Ce que BNC2 gagne |
|---|---|
| **Le minuteur d'Orodruin** (DRL1, §7) | Rien de neuf à tenir : l'armement, le permis fermé par défaut, le verrou, le registre, l'empreinte épinglée, la zone `bench` rejugée, « ce qui vient du dehors ne peut que refuser » valent à l'identique. L'occurrence est unique au lieu de récurrente : **une surface de moins** (pas de rattrapage, pas de rotation) |
| **La console / Discord** (§1, §3 de `modele-de-menace.md`) | Aucun chemin distant ne déclenche l'attaque : la console et le bot ne lancent rien ; ils ne portent que le **restore**, un geste humain gardé par SEC1 (console) et, sur le bot, par le nom tapé **et** le TOTP (TOT1) |
| **Le fournisseur du modèle** (§4) | Glorfindel reste aveugle au rouge : les attentes du scénario ne vont ni dans la fenêtre, ni dans la demande, ni dans `_build_user_message()`. BNC2 ne touche aucune des trois zones du prompt, et ne demande donc **pas** le run de bout en bout du prompt |
| **`runs/` et l'état local** (§2) | Le rapport est composé par un **lecteur** (H0, `Reader`) ; il est masqué par construction (BNC1). Aucune identité nouvelle, aucun droit d'écriture ajouté |

### 8.2 Ce que le design perd (ou met en risque), et ce qui le tient

| | Menace | Ce qui la tient |
|---|---|---|
| E | Le créneau joue un scénario **destructif** (T1486), là où le drill hebdomadaire ne joue que du non destructif | Zone `bench` seule, exigée au jugement **et** avant chaque fil ; cible **nommée et tapée** à l'armement (`typed_name`, DG-b) ; usage unique et expiration ; jamais `twin` ni `production` ; la règle de production inchangée. Le destructif n'est admis que par la forme « occurrence unique » du drill, pas par un drapeau de ligne de commande |
| D | Un créneau destructif qui s'emballe | `RuntimeMaxSec`, l'arrêt qui ferme les fenêtres ; le nettoyage de l'atomic ; le point de sauvegarde ; **l'usage unique** : un créneau joué ne rejoue pas |
| D | L'humain ne répond pas : la VM reste chiffrée et isolée | **État sûr tenu** (§3.2) : la VM isolée (réversible), aucune action destructive de Glorfindel, la carte de restore qui n'exécute jamais seule, `ttl_exceeded` qui escalade sans lever. Rien de pire qu'un incident réel contenu et laissé à l'humain |
| E | Le rapport compose sur une identité élargie | Il compose sur H0, avec `Reader` déjà présent (REC1) ; Orodruin ne reçoit aucun droit de lecture du coffre ni du journal (option écartée, §10.2) |
| S | Un restore forgé ou pré-approuvé | La signature du créneau ne couvre jamais le restore (décision 2) ; la carte de H0 seule le déclenche, gardée par SEC1 ; sur le bot, le nom tapé et le TOTP (TOT1) |
| I | Le calendrier public | L'heure du créneau unique n'est **pas** dans le dépôt (elle est à l'armement, `AT=…`), contrairement au `schedule` récurrent de DRL1 : un run unique n'annonce pas sa date au dépôt public. Impact plus faible que DRL1 sur ce point |

### 8.3 Ce qui reste ouvert

- **root sur Orodruin** peut déjà lancer tout injecteur sous le contrat (la limite de DG-b) : le
  créneau ne lui donne rien de plus. L'armement et le registre, sur son disque, sont à sa main ;
- **un Orodruin compromis** peut supprimer le permis et écrire `bench.json` à `disarmed` : H0 y voit
  un désarmement de Jonathan, sans alerte ; il n'en a pas besoin pour attaquer (comme DRL1) ;
- **le restore reste autant que l'identité qui restaure** (la console, le bot) : la frontière tient
  autant que ces principaux, comme le dit déjà REC1 (§2 de `modele-de-menace.md`) ;
- **la chaîne complète dépend de RST1, DRN1 et REC1b** : tant qu'ils ne sont pas tous verts au banc,
  le run ne se ferme pas seul (le restore a demandé une enveloppe le 09/11 ; la coupure n'était pas
  vérifiée). BNC2 suppose ces lots livrés.

---

## 9. Le découpage en lots de code

La conception (ce document) vient d'abord, relue. Le code vient **après la 0.6.0**, et **après
DRL1a** (la machinerie `scheduled_drill`) et **BNC1** (le préflight et le rapport), dont BNC2
réutilise tout.

| Ordre | Lot (proposé) | Contenu | Ce qu'il prouve au banc |
|---|---|---|---|
| préalables | **DRL1a**, **DRL1b**, **DRL1c** | la machinerie du créneau armé : `scheduled_drill`, le permis, le verrou, le registre, l'arrêt du service, le démarrage planifié (§9 de `drill-banc.md`) | que le minuteur arme, refuse et joue sous contrat (le drill hebdomadaire) |
| préalable | **BNC1** (#682) | `make bench-preflight`, `make bench-report` | le préflight et la chronologie composés seuls, masqués |
| préalables | **RST1** (#680), **DRN1** (#677), **REC1b** (#679) | le restore lisible, la coupure vérifiée, la décision par le plan de contrôle | que la chaîne du 09/11 tient sans enveloppe |
| **1** | **BNC3** (Orodruin, cœur) | le **créneau unique** : la forme « occurrence unique » dans le lecteur de drill (le destructif admis sous zone `bench` + nom tapé) ; `drills/banc-t1486.yaml` ; `eregion_core/scheduled_drill.py --slot bench` (l'armement daté, l'usage unique par le registre, l'expiration) ; les cibles Make `orodruin-bench-check`/`-arm`/`-disarm` ; l'unité systemd à usage unique ; le pas « bench » du kill ; `orodruin/bench.json` et son lecteur exact sur H0 | le créneau joue **une fois** T1486 sur la VM nommée, à l'heure armée, et rien d'autre ; expire ; refuse sans permis ; laisse la VM isolée si l'humain ne répond pas |
| **2** | **BNC4** (H0) | le rapport composé **à la fin du run** par le code de BNC1, publié dans le fil Discord du run (bot de Glorfindel) et dans `runs/bench/<run_id>.json` ; la session Banc ne lit que ce rapport | la chronologie recomposée seule, masquée, postée ; aucun droit nouveau |
| **3** | **BNC5** (preuve par PR) | la lecture d'un `runs/bench/<run_id>.json` et la **proposition** d'une PR qui met à jour `docs/proofs.json` (jamais une écriture directe) ; `scripts/adoption.py` relu | un run mesuré devient une figure datée et sourcée du site, par une porte relue |
| en parallèle | **TOT1** (#685) | le restore depuis le bot : le nom de la VM tapé + le code TOTP | un restore approuvé depuis le téléphone exige plus que la liste d'autorisation |

---

## 10. Les questions ouvertes, et les options écartées

### 10.1 Les questions pour Jonathan (chacune avec une option recommandée)

**Q1. La cadence du créneau.** BNC2 est un **créneau unique** (armé quand on veut remesurer la
chaîne). Faut-il, plus tard, un créneau T1486 **récurrent** (mensuel) à côté du drill hebdomadaire ?
- **Recommandé : non, pas de récurrence pour T1486.** Un scénario destructif récurrent, à heure
  publique, use le banc et annonce son calendrier (la ligne I du §8.2). Le drill hebdomadaire non
  destructif tient déjà l'indicateur ; BNC2 remesure la chaîne à la demande. Une récurrence
  viendrait, si le besoin se montre, comme une suite relue.

**Q2. Qui déclenche la composition du rapport (étape 8) ?** Le run fini, le rapport doit se composer.
- **Recommandé : la watch de H0, à la levée.** Quand la watch émet le `recovery_complete` (REC1),
  elle sait que le run est fini ; elle déclenche `bench-report` dans le conteneur de la console de H0
  (qui tient le code de BNC1), comme un bouton. L'autre voie (un minuteur sur H0 qui guette un run
  récent) ajoute une horloge ; le déclenchement à la levée est plus net.

**Q3. Le nom et l'identité de la session Banc pour BNC2.** La session Banc de DRL1 (BRO1) a `Log
Analytics Reader` sur le workspace. Lit-elle le rapport de BNC2 avec la même identité ?
- **Recommandé : oui, la même (BRO1), sans rien de plus.** Elle lit le rapport publié (fichier, fil
  Discord) et relit le workspace en témoin indépendant. Aucune identité nouvelle (décision 4).

### 10.2 Les options écartées (avec leur raison)

Conformément à la consigne de #684 (« ne propose aucun chemin de lancement distant, aucune
pré-approbation du restore et aucune identité élargie »), les idées qui l'exigeraient sont écartées
ici, pas retenues :

| Option écartée | Pourquoi |
|---|---|
| **Un lancement distant** : la console, Discord ou un workflow planifié déclenche l'attaque pour que le run soit vraiment « sans les mains » | Casse la décision 1 et la propriété de DRL1 : Orodruin ne tire ni n'écoute rien. Un chemin d'écriture du dehors vers une attaque est précisément ce que le modèle de menace exclut. Ce qui vient du dehors ne peut que **refuser** (V1, le permis, « Stop all ») |
| **La pré-approbation du restore** : le créneau armé autorise aussi le restore (ou une levée), pour supprimer le dernier geste humain | Casse la décision 2 et SEC7. Le restore est destructif (il écrase des disques) ; il reste un consentement humain distinct à chaque run, sur la carte de H0. La signature ne couvre que le lancement |
| **Un restore autonome par la watch** | Défait SEC7 (« même un bogue ou une décision détournée ne le pourrait pas ») : une watch compromise pourrait écraser des disques. La seule voie propre vers un restore encadré, si on le veut un jour, est un **exécuteur de restore à part** (FS1g), pas la watch |
| **Composer le rapport sur Orodruin** | Exigerait de donner à Orodruin la lecture des jobs du coffre et du journal d'activité — une **identité élargie** (décision 4). H0 tient déjà ces droits (REC1) : le rapport s'y compose sans rien ajouter |
| **Donner à H0 le rôle Restore pour fermer la boucle lui-même** | Casse SEC7 et l'étroitesse de H0 : il ne restaure pas, et son Terraform refuse de lui donner ce rôle. Le restore part du poste (console) ou du bot (TOT1), jamais de H0 |
| **Un écrivain automatique de `docs/proofs.json`** | Un run écrirait directement une figure du site public, sans relecture. Écarté : `proofs.json` n'entre que par une PR relue (§5.4), même quand le run est la source |

---

## Ce que ce document ne décide pas

- Rien n'est mesuré : la chaîne complète (le restore sans enveloppe, la coupure vérifiée, la levée
  par REC1) suppose RST1, DRN1 et REC1b verts au banc. BNC2 les rejouera pour les dater.
- Le format exact du drill à occurrence unique, le nom des cibles Make et des unités systemd sont
  au lot de code (BNC3), qui suit la forme de DRL1a.
- Le TOTP du bot est à TOT1 (#685) : sa mise en place, sa rotation, sa perte, et sa frontière.
- La cadence (Q1) et la voie de proposition vers `proofs.json` (BNC5) restent à trancher avec
  Jonathan au moment du code.
