# Le banc qui se mesure seul : le destructif de la main de l'opérateur, le rapport composé seul (BNC2)

_Conception — 10/11, reprise le 11/11 sur le cadre réduit (BNC2, #684) — statut : **conception
seulement**, relue en Opus 5.5 (11/11) ; les huit questions du §10.1 tranchées par Jonathan le
11/11. Rien n'est codé, armé ni mesuré. Elle prolonge le drill du banc
([`drill-banc.md`](drill-banc.md), DRL1), le banc lisible par la machine (BNC1, #682) et le banc
piloté depuis le téléphone (MOB1, #686). Elle remplace le premier jet du 10/11, écrit avant les
décisions qui ont réduit le cadre : ce qu'il proposait et que ce cadre exclut est au §10.2, avec sa
raison._

> **Les décisions de Jonathan du 10/11 qui cadrent la conception.** Les décisions 1 et 2 sont celles
> du dernier commentaire de #684, qui fait foi. Les décisions 3 et 4 viennent du corps de l'issue et
> de la fiche du lot (« Reprise du 11/11, sur le cadre réduit »).
> 1. **Le destructif reste lancé de la main de l'opérateur.** BL1b (« jamais un script maison ») et
>    les conditions de DRL1 restent intactes. Le T1486 part toujours de sa main, depuis le poste ou
>    depuis le téléphone par le terminal du poste (MOB1). Tout ce qui l'entoure s'automatise : le
>    préflight, le rapport, la levée par Imladris (anciennement H0).
> 2. **Le restore se lance depuis la carte d'isolement.** Le graphe ne recommande un restore qu'au
>    cycle suivant, sur une nouvelle détection, et sous la quarantaine cette détection ne vient pas
>    (DRN1, #677). On ne touche ni au graphe ni au prompt. Le bot et la console d'Imladris ne
>    peuvent pas restaurer sous son identité : il y faut FS1g, un exécuteur de restore, et TOT1
>    (#685). D'ici là, le restore part du terminal du poste (`make bench-restore`).
> 3. **Le rapport est composé seul**, à partir de BNC1, là où les droits existent déjà ; publié
>    masqué ; une session Banc ne lit que lui ; aucune identité nouvelle, aucun droit élargi (le
>    corps de #684 ; la fiche, point 3).
> 4. **Le créneau daté ne vaut que pour les drills non destructifs** (la fiche, point 4) : « un
>    créneau armé ne joue que des techniques publiques et non destructives : c'est une occurrence
>    datée du drill de DRL1 » (#684, le dernier commentaire, point 1).

L'hôte de Glorfindel s'appelle **Imladris** (IML1, #688). Les cibles Make, la
ressource Azure et l'histoire gardent leur nom (`make glorfindel-host-*`).

## En bref

Un run du banc suit l'un de deux chemins, et ils ne se mélangent jamais.

- **Le run destructif** (le rançongiciel T1486 de [`docs/banc-t1486.md`](../banc-t1486.md)) part
  d'un geste de l'opérateur : `make bench-run TARGET=gondolin SCENARIO=T1486`, tapé au clavier du
  poste ou depuis le téléphone, dans le terminal du poste. Le restore est son second geste.
- **Le créneau daté** joue un drill **non destructif** de DRL1 à une heure armée par Jonathan
  (« joue banc-hebdo jeudi à 10:00 sur gondolin »), une seule fois. Il ne joue jamais T1486.

Entre ces gestes, rien ne demande la main :

| Ce qui s'automatise | Où | Ce qui existe déjà |
|---|---|---|
| le préflight, qui refuse s'il n'est pas vert | le poste, dans `bench-run` | BNC1, MOB1 |
| le calme de 10 minutes, vérifié au lieu d'être attendu à la montre : un ✗, jamais une attente | le poste, dans le préflight | à faire (BNC3) |
| le point de restauration propre, vérifié, et pris s'il manque ; « restore d'abord » sur une VM attaquée et non restaurée | le poste, dans `bench-run`, par la route du bouton 📸 de la console d'Imladris, après le nom tapé | à faire (BNC3) |
| la détection, l'isolement autonome et sa vérification | Imladris | la watch, DRN1 |
| la levée après le restore | Imladris | REC1, REC1b ; à venir, LEV1 (LEV3 et suivants) : un exercice prouvé par le plan de contrôle se lèvera seul |
| le rapport, composé sans rien taper | le poste, puis Imladris en fin de run | BNC1 (le poste) ; à faire (BNC3, BNC4) |
| la proposition d'une preuve pour `docs/proofs.json` | une PR relue | à faire (BNC6) |
| le réveil d'Orodruin pour un créneau daté | la Logic App de DRL1c, chaque heure | à faire (BNC5b) |

Le T1486 garde donc **deux gestes humains** : le lancer, puis le restaurer. Le premier jet promettait
un seul geste, le restore, en faisant jouer l'attaque par le minuteur d'Orodruin. Le cadre du 10/11
l'exclut (§10.2).

```
opérateur (poste, ou téléphone → terminal du poste)
   │ geste 1 : make bench-run TARGET=gondolin SCENARIO=T1486   (nom tapé, [o/N])
   ▼
préflight (BNC1) ─ calme ─ restore d'abord ? ─ demande, nom tapé, [o/N] ─ point propre (route 📸)
   ─▶ Orodruin (rejuge : contrat, V1, zone, nom tapé, plafond)
                                         │ setup_testdata.sh, puis T1486, T0
                                         ▼
Imladris : détection ─ isolement autonome vérifié (DRN1) ─ carte d'isolement
   │                                          │
   │  rapport intermédiaire (poste, BNC1)     │  ⏸ quarantaine : l'état sûr, tant que personne ne restaure
   ▼                                          ▼
opérateur : geste 2 : le restore ── aujourd'hui make bench-restore (poste) ; demain la carte d'isolement (FS1g + TOT1)
   ▼
Imladris : la reprise lue sur Azure, la levée (REC1, REC1b) ─ le rapport final composé seul (BNC4)
   ▼
fichier runs/bench/<run_id>.json + message du bot de Glorfindel ──▶ plus tard, une PR relue vers docs/proofs.json

Jonathan ── arme un créneau daté (non destructif) ──▶ Orodruin : une occurrence de DRL1, à l'heure armée, une fois
```

---

## 1. Le but, et ce qui ne change pas

### 1.1 Le but

Le rejeu T1486 du 09/11 (compte rendu hors dépôt) a rendu le service à T0 + 4 h 24. Environ 3 h 25
venaient du blocage du restore, deux défauts jamais mesurés que RST1 (#680) a corrigés, et une
pause. Le reste venait de la façon de faire : chaque vérification tapée à la main, chaque sortie
masquée puis recopiée pour reconstruire la chronologie. MOB1 et BNC1 ont déjà réduit le run à deux
commandes et un rapport. BNC2 dit ce qui reste à automatiser **autour** des deux gestes humains, et
où, sans rien ajouter à ce qui peut lancer une attaque ou restaurer.

Ce que le banc y gagne :
- un run T1486 qui se rejoue en deux gestes, sans une heure de clavier ;
- un rapport complet, masqué, composé sans qu'on le tape ;
- moins d'identifiants à l'écran et dans le transcript d'une session, puisque le rapport est masqué
  par construction et qu'une session Banc ne lit que lui ;
- une preuve datée et sourcée par run, qui entre dans `docs/proofs.json` par une PR relue (§5.4).

### 1.2 Ce qui ne change pas

- **La règle de production** (`eregion_core/inscription.py`, O0) : jamais de panne ni d'action
  destructive sur une charge réelle. T1486 ne joue que sur une VM inscrite `bench`.
- **BL1b** : un drill, et donc un créneau, ne joue qu'une bibliothèque publique, à version épinglée.
  `scripts/vm/ransomware_sim.sh` est un script maison et destructif : aucun minuteur ne le joue.
- **DRL1** : « Orodruin ne tire rien et n'écoute rien » ; trois entrées décident d'une occurrence
  (l'image, l'armement, l'horloge) ; ce qui vient du dehors (V1, le permis, l'état des cibles) ne
  peut que refuser ; le destructif est refusé dans un drill planifié.
- **SEC7** : la watch ne restaure jamais, et Imladris n'a pas le rôle Restore. Son Terraform refuse
  de le lui donner (`infra/glorfindel-host/README.md`, « Ce que la VM est »).
- **Le restore n'est jamais pré-approuvé**, ni par un armement, ni par une signature, ni par une
  commande qui l'enchaînerait à l'attaque.
- **Les trois zones du prompt** (`few_shot_examples.yaml`, `_SYSTEM_PROMPT`, `_build_user_message()`)
  ne bougent pas, et le graphe non plus. BNC2 ne demande donc pas le run de bout en bout du prompt.

---

## 2. Le créneau daté, une occurrence de DRL1, non destructive

### 2.1 Ce qui change dans DRL1, et ce qui ne change pas

DRL1 arme un drill livré qui porte son heure (`schedule`, le mardi à 19:00 UTC), rejoué chaque
semaine par le minuteur d'Orodruin. Le créneau daté lui ajoute **une occurrence unique**, à une
heure que Jonathan choisit en armant, sur la machinerie que DRL1a codera (`eregion_core/scheduled_drill.py`,
proposé), le verrou « un run à la fois », le permis, le registre, l'arrêt du service, le démarrage de la cible.

| | Le drill de la semaine (DRL1) | Le créneau daté (BNC2) |
|---|---|---|
| **Occurrence** | récurrente, l'heure du `schedule` du drill | **une seule**, l'heure donnée à l'armement (`AT=…`) ; jouée ou passée, elle est éteinte |
| **Drill** | `banc-hebdo` | un drill livré qui porte `schedule` et tient le §1.2 de DRL1 ; seule l'heure du `schedule` est ignorée : v1, `banc-hebdo` seul |
| **Technique** | non destructive, publique (T1136.001) | **la même règle, le même code** : non destructive, publique, implémentée |
| **Cible** | nommée à l'armement (`TARGETS=gondolin`), jamais `all` | pareil |
| **Registre** | une occurrence par 6 jours au plus (`too_soon`) | une entrée par créneau (`already_played`), à part : le créneau ne consomme pas la semaine |
| **Permis** | `orodruin/drill-permit.json`, réécrit à chaque occurrence | un permis à lui, jamais réécrit (§2.4) |
| **Allumage d'Orodruin** | le démarrage planifié de DRL1c (une Logic App, à T − 20 min) | la même Logic App, qui lit chaque heure dans le canal le permis d'un créneau et allume Orodruin si son heure tombe dans l'heure qui vient (§2.7, Q4) |

**Ce qui ne change pas de DRL1** : l'armement reste un geste de Jonathan ; le service ne prend aucun
argument venu d'ailleurs ; aucune écriture sur le banc avant le contrat, V1 et le journal ; la zone
`bench` est exigée au premier jugement et avant chaque fil ; une occurrence manquée n'est jamais
rattrapée ; le kill arrête tout.

**À quoi il sert.** À rejouer une preuve non destructive à une heure choisie, sans être là :
- après une release qui touche la détection ;
- pendant la probation de LEV1 : le T1136.001 pendant la probation mesure la réisolation
  (`docs/design/levee-probation.md`, décisions du 10/11) ;
- quand le mardi soir ne convient pas.

Pour jouer tout de suite, c'est `make bench-run` : un créneau n'est pas un lancement immédiat
déguisé.

### 2.2 Le scénario, pris dans l'image signée

Le créneau ne construit rien. Il nomme un drill livré, et le service le relit dans l'image des
injecteurs, par le seul lecteur de DRL1 :
- dans la couche livrée seulement (`drill.load_file(…, SHIPPED)` sur `/app/drills/<nom>.yaml`),
  jamais `drill.find`, jamais un répertoire où Orodruin écrit ;
- son empreinte, le sha256 du fichier entier, est épinglée à l'armement (la décision 5 de DRL1) :
  une release qui change le drill le fait refuser (`drill_changed`) jusqu'au réarmement ;
- **il porte `schedule`**, et le lecteur de DRL1 l'a donc admis (§1.2 de `drill-banc.md`) : chaque
  fil vise `{zone: bench}` ; chaque expérience est une technique, jamais une panne, `implemented`,
  non destructive, d'un moteur public ; `max_injections` et `max_run_s` restent sous les plafonds
  absolus. Un drill livré sans `schedule` (`sentinelle`, en zone `production` ; `bl1-reponse`, une
  panne) est refusé, à l'armement comme à l'occurrence (`not_scheduled`) ;
- le catalogue de l'image confirme chaque fil : une technique, jamais une panne ; `implemented`,
  `destructive: false`, un moteur public. **C'est le même contrôle que pour le drill de la
  semaine**, pas une seconde forme : aucun chemin du lecteur n'admet le destructif.

Du `schedule`, seule l'heure (`day`, `at`) est ignorée : l'heure du créneau vient de l'armement. Ses
plafonds valent, comme ses autres conditions.

**Deux couches indépendantes tiennent le destructif à l'écart du créneau :**
1. **le catalogue**, relu dans l'image à l'armement et à l'occurrence : un fil dont l'expérience est
   destructive est refusé avant la demande (`not_eligible`) ;
2. **le nom tapé** : le runner refuse un fil destructif, ou non déclaré inoffensif, sans nom tapé
   égal au nom qu'il lit de la cible (`eregion_core/exercise_runner.py`, `_typed_refusal`). Le
   créneau n'écrit **jamais** de nom tapé. Un fil destructif qui passerait la première couche
   (un catalogue de l'image faux, un bogue du lecteur) serait refusé par la seconde.

**Une panne aussi est tenue par deux couches** : le lecteur du `schedule`, qui n'admet que des
techniques (§1.2 de DRL1), et le contrôle du catalogue au rang 4 du §2.6, qui refuse une panne à
l'occurrence (`not_eligible`). Chacune a son mutant (§9).

### 2.3 L'armement d'une occurrence datée

**Rien n'est posé avant l'armement.** Les noms des cibles Make sont proposés ; le lot de code les
fixe à la forme de DRL1a.

| Cible Make (depuis le poste, par la clé d'hôte épinglée) | Fait |
|---|---|
| `make orodruin-slot-check DRILL=banc-hebdo TARGETS=gondolin AT=2026-11-19T10:00Z` | à blanc : le drill dans l'image, son empreinte, le catalogue, le contrat, la watch, la cible, l'heure dans l'horizon ; dit ce que ferait l'occurrence. Aucune écriture |
| `make orodruin-slot-arm DRILL=… TARGETS=… AT=…` | **Jonathan.** Écrit l'armement du créneau, pose ses unités, active son minuteur ; écrit son permis dans le canal sous l'identité de l'opérateur ; publie `orodruin/slot.json` |
| `make orodruin-slot-disarm` | désactive le minuteur, retire ses unités et l'armement ; supprime le permis ; publie « désarmé » ; dit chaque pas, et sort en erreur si l'un manque |

Les trois refusent dans une session d'agent, comme `bench-run` (`bench_shared.session_refusal` :
`EREGION_AGENT_SESSION`, le worktree d'un lot). Une session n'arme jamais rien.

**L'armement du créneau** (`~/drill/slot.json`, mode 600, à côté de l'armement de la semaine, monté
en lecture seule dans les conteneurs) dit le nom du drill, son empreinte, la cible, l'heure armée
`at`, l'heure de l'armement et le commit de l'image. Aucun identifiant, aucun secret.

**Les unités.**
- `eregion-slot.timer` : un `OnCalendar` à la date exacte (`2026-11-19 10:00:00 UTC`),
  `Persistent=false`, `AccuracySec=1min` ;
- `eregion-slot.service` : le `docker run` durci de DRL1 (`--pull never`, `--init`, la racine en
  lecture seule, aucune capacité, `RuntimeMaxSec`, `ExecStop=-docker stop --time 90`), avec une
  commande fixe, `python -m eregion_core.scheduled_drill run --slot` (le module que DRL1a codera). Le
  drapeau est écrit dans l'unité ; aucun argument ne vient d'ailleurs.

**Un seul créneau armé à la fois** (Q5). Tout armement exige le désarmement du précédent, qu'il
soit en attente, joué, refusé ou passé (« a slot is already armed: disarm first »).

**L'heure armée finit avant l'extinction.** Orodruin et gondolin s'éteignent à 23:00 UTC (DRL1c, le
planning de Celebrimbor). `slot-arm` refuse une heure dont l'occurrence ne finirait pas avant :
`at` + `RuntimeMaxSec` (60 min) après 23:00 UTC, soit `at` après 22:00 UTC. Il refuse aussi une
heure trop proche pour le réveil (§2.7) : moins de 80 min après l'armement, Orodruin éteint. Et il
refuse tant que le réveil est désactivé, c'est-à-dire tant que le drill de la semaine n'est pas
armé (§2.7).

**L'horizon : sept jours au plus.** `AT` tombe dans le futur, au plus 7 jours après l'armement. La
politique du canal supprime un blob 9 jours après sa dernière écriture (`channel_retention_days`,
§2.4 de DRL1) : un permis écrit à l'armement et jamais réécrit vit donc jusqu'à l'heure armée et
au-delà. L'horizon le garantit sans réécriture (Q5).

### 2.4 L'expiration et l'usage unique

Trois bornes se cumulent ; chacune suffit à fermer.
1. **L'heure.** Le service ne joue que dans les 30 minutes qui suivent `at` (`off_slot`, le pendant
   d'`off_schedule`). Un déclenchement à la main hors de cette fenêtre est refusé, et rien n'est
   écrit avant ce contrôle : il ne consomme pas le créneau.
2. **Le registre.** Sous le verrou, le service lit `runs/orodruin/drills/slots.jsonl` : une entrée
   de ce créneau (son heure d'armement et son `at`) refuse `already_played`. Sinon il l'écrit, sur
   le disque (fsync), **avant** le jugement : quoi qu'il arrive ensuite, le créneau est joué. Un
   registre illisible ne laisse rien jouer. C'est le registre, pas le minuteur, qui tient l'usage
   unique : un `OnCalendar` réécrit ou le service lancé à la main ne rejouent pas.
3. **Le permis.** `orodruin/slot-permit.json`, écrit par l'opérateur à l'armement (le drill, son
   empreinte, `at`, l'heure de l'armement ; ni cible, ni identifiant), supprimé par le désarmement
   et par le kill, exigé présent et égal à l'armement local. Absent : `no_permit` ; différent :
   `permit_mismatch`. Il n'est **jamais réécrit** par Orodruin : contrairement au permis de la
   semaine, il n'a pas à survivre à la rétention, puisque l'horizon est sous elle. Orodruin n'a
   donc aucune raison d'y écrire. Il le pourrait : son rôle `channel_writer` couvre tout le
   conteneur du canal. Seul le code l'en empêche, et un mutant le garde (§9) ; un Orodruin
   compromis n'en a pas besoin pour attaquer (§8). Une absence ferme, comme dans DRL1.

Un créneau joué, refusé ou passé reste inerte jusqu'à `orodruin-slot-disarm` : le minuteur à date
passée ne part plus, et le registre refuserait. Ce désarmement est aussi ce qui permet d'en armer un
autre ; `slot-check` le suggère.

### 2.5 La cible nommée à l'armement

Comme DRL1 (§1.3 de `drill-banc.md`) : la cible se donne par son nom (`TARGETS=gondolin`), jamais
dans le drill livré, puisque le dépôt est public. `all` est refusé. Le nom n'est pas tapé : la
technique est non destructive, et le nom tapé est la garde d'une demande portée à la main
(DG-b). La demande est fabriquée sous le verrou, avec l'identifiant de la VM lu par l'identité
d'Orodruin (une seule de ce nom, sinon `not_placed`).

### 2.6 Ce qui peut refuser

Le service relit dans l'ordre, et refuse au premier manque. C'est l'ordre de DRL1 (§2.3 et §3.1 de
`drill-banc.md`), avec les codes du créneau :

| # | Garde | Refus |
|---|---|---|
| 1 | l'armement du créneau se lit | `disarmed` |
| 2 | le drill vient de l'image, couche livrée ; il porte `schedule` et tient le §1.2 de DRL1 | `drill_missing`, `not_scheduled` |
| 3 | son empreinte est celle de l'armement | `drill_changed` |
| 4 | le catalogue de l'image : une technique, jamais une panne ; implémentée, non destructive, moteur public | `not_eligible` |
| 5 | l'heure dans les 30 min qui suivent `at` | `off_slot` |
| 6 | le permis du créneau, présent et égal | `no_permit`, `permit_mismatch` |
| 7 | le verrou « un run à la fois », jamais attendu | `busy` |
| 8 | le registre des créneaux, lu puis écrit sous le verrou | `already_played` |
| 9 | la demande fabriquée, la cible lue | `not_placed` |
| 10 | le contrat d'Orodruin, armé | `passive` |
| 11 | V1 : le battement signé de la watch, relu 10 min au plus | `watch` |
| 12 | la zone `bench`, au jugement et avant chaque fil | `not_bench` |
| 13 | l'isolation, lue avant tout démarrage : le créneau ne lève jamais une isolation | `isolated` |
| 14 | la cible prête (démarrée s'il le faut, Heartbeat frais) | `not_ready` |

Les codes `drill_missing`, `not_scheduled`, `not_eligible`, `off_slot` et `already_played` sont
proposés ; les autres sont ceux de DRL1 et de DG-b. Ce qui vient du dehors (V1, le permis, l'état de
la cible) ne peut que refuser. Un Imladris compromis, ou qui écrit dans le canal, peut empêcher un créneau, jamais en lancer un, ni en changer
le drill ou la cible. Le lot de code porte un mutant par garde (§9).

**Ce qu'Imladris en dit.** Le statut `orodruin/slot.json` (armé, joué, refusé et pourquoi, désarmé,
tué ; ni identifiant ni cible) est lu par un lecteur exact, comme `drill.json` dans DRL1b. Le
permis présent dans la liste du canal arme une **alarme d'absence** : aucune occurrence publiée deux
heures après `at`, et Imladris dit « slot not run », par le bot de Glorfindel, dans le fil du drill.
Le verdict d'une occurrence est celui de DRL1 (§4 de `drill-banc.md`), et VP1 le propose de même.

### 2.7 Le réveil d'Orodruin (Q4)

Orodruin est éteint entre les sessions, et un minuteur sur une VM désallouée ne part jamais. Le
créneau a donc un réveil, décidé par Jonathan le 11/11 :
- **la Logic App de DRL1c, déclarée une fois dans Terraform**, porte une seconde récurrence, chaque
  heure à l'heure pile. Elle lit dans le canal `orodruin/slot-permit.json`. Présent, bien formé, et
  son `at` dans l'heure qui vient (entre 20 et 80 min après la lecture) : elle allume Orodruin, par
  l'action qu'elle tient déjà (`virtualMachines/start/action`, à la portée de la VM d'Orodruin).
  Sinon, rien ;
- **l'armement n'écrit qu'une donnée**, le permis. Il ne touche jamais la Logic App, ni son
  planning, ni son état : rien ne s'écarte de l'état de Terraform ;
- **son identité reçoit une lecture, sur ce seul conteneur du canal** : `Storage Blob Data Reader`
  à la portée du conteneur `exercises` (`infra/orodruin/main.tf`), jamais du compte. Elle n'y écrit
  rien. Le conteneur porte bien plus que le permis : le journal d'Orodruin (`audit/<run_id>.jsonl`,
  dont chaque ligne nomme sa cible par son identifiant ARM, donc l'abonnement :
  `eregion_core/orodruin.py`), les fenêtres et leurs cibles (`eregion_core/exercise.py`), les
  statuts et les rapports. D'où **une condition ABAC sur l'attribution**, qui borne la lecture au
  seul chemin `orodruin/slot-permit.json` :
  `((!(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read'})) OR
  (@Resource[Microsoft.Storage/storageAccounts/blobServices/containers/blobs:path] StringEquals
  'orodruin/slot-permit.json'))`, avec `condition_version = "2.0"` sur l'attribution
  (`azurerm_role_assignment`). La portée reste ce seul conteneur, comme Jonathan l'a décidé, et la
  lecture ce seul blob. La Logic App lit le blob par un `GET` sur son chemin, **sans lister le
  conteneur**. Son mutant : la condition absente. **À mesurer au banc (BNC5b)** : que la condition tienne pour une Logic App, et
  qu'une lecture d'un autre blob soit refusée. Si elle ne tient pas, la Logic App lit tout le
  conteneur : la même lecture que la watch (`channel_watch_reader`, `infra/orodruin/main.tf`), les
  identifiants ARM des cibles compris, et le modèle de menace le dira noir sur blanc ;
- **le pare-feu du canal (SEC5) la laisse passer, et elle seule (Q4b).** Le compte du canal ferme
  tout par défaut : `default_action = "Deny"`, `bypass = ["None"]`, seuls passent les sous-réseaux
  et les adresses d'Orodruin, d'Imladris et de l'opérateur (`infra/orodruin/main.tf`,
  `network_rules`). Une Logic App de consommation sort par les adresses partagées de sa région :
  sans rien de plus, elle ne lit pas le permis, quels que soient son rôle et sa condition. La
  décision de Jonathan (11/11) : **une règle d'instance de ressource** sur le compte, pour cette
  seule Logic App et son identité managée (`network_rules.private_link_access`,
  `endpoint_resource_id` = la Logic App). `bypass` reste à `None`, **jamais `AzureServices`**, qui
  ouvrirait le compte à tout service d'Azure d'un autre client. La lecture reste bornée au permis
  par la condition ABAC. Jonathan la relit au plan. Ses mutants : le bypass élargi ; une règle
  d'instance pour une autre ressource. **À mesurer au banc (BNC5b)** : qu'Azure accepte une règle
  d'instance pour une Logic App, et que la lecture passe par elle. Si Azure ne l'accepte pas, la
  décision revient à Jonathan ;
- **elle ne joue rien** : elle allume une VM. Le minuteur d'Orodruin, ses gardes (§2.6) et le permis
  décident seuls de l'occurrence. Allumé pour rien (un permis forgé par Orodruin, qui peut écrire le
  canal), Orodruin coûte une soirée de VM, puis s'éteint à 23:00 UTC ;
- **le réveil dépend du drill de la semaine.** DRL1 crée la Logic App désactivée, et seul
  `orodruin-drill-arm` l'active ; `orodruin-drill-disarm` et le kill la désactivent (§5.1 et §3.1 de
  `drill-banc.md`). Donc : sans drill de la semaine armé, aucun créneau ne s'arme (`slot-arm` lit
  son état, en lecture seule, et refuse : « the wake-up is disabled: arm the weekly drill first ») ;
  et désarmer le drill de la semaine coupe le réveil d'un créneau déjà armé. Ce cas n'est pas
  silencieux : l'alarme d'absence « slot not run » d'Imladris (§2.6) le rattrape ;
- **le kill** supprime le permis : plus de réveil, et la Logic App est désactivée ;
- **deux récurrences dans une même Logic App** : celle de la semaine (T − 20 min) et celle de
  l'heure. Elles partagent les mêmes actions : la condition doit tester laquelle s'est déclenchée,
  et le contrôle d'heure d'`orodruin-drill-arm` (« apply first », §5.1 de `drill-banc.md`) viser la
  récurrence de la semaine. Une Logic App de consommation n'a peut-être qu'un déclencheur : la
  récurrence horaire porterait alors les deux conditions. À mesurer (BNC5b).

**Les gestes de Jonathan** (BNC5b) : `make orodruin-plan`, relu, puis `make orodruin-lock`, qui en
est l'apply. Le plan porte trois changements, à relire chacun :
- une récurrence de plus dans la Logic App de DRL1c ;
- une attribution `Storage Blob Data Reader` à la portée du conteneur, avec sa condition ABAC ;
- une règle d'instance de ressource sur le pare-feu du compte, pour cette Logic App seule, et
  `bypass` toujours à `None`.

Aucun droit nouveau pour l'identité d'Orodruin.

**À mesurer** (BNC5b) : la règle d'instance de ressource acceptée pour une Logic App, et la
lecture qui passe le pare-feu par elle seule ; la lecture d'un blob par la Logic App sous son
identité managée, et la condition ABAC qui la borne au seul permis (un autre blob refusé) ; le JSON du permis lu par son expression ; les deux
récurrences et la condition qui les distingue ; le délai entre le réveil et docker prêt (les 20 min
de marge suffisent-elles ?) ; le coût d'une récurrence horaire.

---

## 3. Le déroulé du T1486, de bout en bout

Le chemin est celui que MOB1 a livré (`scripts/bench_run.py`, `scripts/bench_restore.py`) : une
demande jugée par Orodruin comme une demande de Dagorlad (DG-b). Chaque étape dit qui agit, avec
quels droits, ce qui le prouve, et si une main la fait.

| # | Étape | Qui agit, avec quels droits | Ce qui le prouve | Main |
|---|---|---|---|---|
| 0 | **Allumer** gondolin et Orodruin | l'opérateur, `make celebrimbor-start`, `make orodruin-start` (OI3 met Orodruin à jour) | leur état, relu par le préflight | oui, comme aujourd'hui |
| 1 | **Le geste 1** : `make bench-run TARGET=gondolin SCENARIO=T1486` | l'opérateur, dans un terminal du poste (au clavier, ou depuis le téléphone, MOB1) ; refusé dans une session d'agent, ou sans terminal | la commande et sa sortie ; le journal du serveur SSH du poste pour le téléphone | **oui** |
| 2 | **Le préflight** (BNC1) | le poste, en lecture seule : l'`az login` de l'opérateur, la lecture d'Imladris par SSH dans un conteneur sans réseau, le contrat lu sur Orodruin | une ligne ✓/⚠/✗ par contrôle ; **un ✗, et rien ne part** | non |
| 3 | **Le calme**, et **le restore d'abord** : gondolin démarrée depuis 10 min au moins, aucun run sur elle depuis 10 min ; et elle ne porte **aucun run destructif sans restore depuis** (Q3b) | le préflight, en lecture : le journal d'activité de la VM pour le calme ; pour le restore d'abord, la liste de référence des runs de la VM (tout Run Command sur la VM dans le journal d'activité d'Azure, quel que soit l'appelant ; la coupure des sessions d'Imladris seule hors du compte ; la technique d'un run de l'Orodruin actuel dans son journal) et les jobs du coffre (§3.1). Un run de cette liste sans restore lisible donne le ✗ ; une liste illisible aussi | deux lignes de plus du préflight (BNC3) : un ✗ qui dit les minutes qui restent, jamais une attente (Q6) ; un ✗ « restore d'abord » (Q3b). L'opérateur relance. Aujourd'hui, la montre de l'opérateur | non (à faire) |
| 4 | **La demande**, puis **le nom tapé** et « [o/N] » | le poste écrit la demande par le lecteur de Dagorlad (`exercise_request.new`) ; le nom de la VM, tapé, est comparé à celui qu'Azure donne. **Rien n'est écrit, ni sur Imladris ni sur Azure, avant cette confirmation** | la demande, son identifiant ; un autre nom, ou « N », et rien ne part | **oui** (fait partie du geste 1) |
| 5 | **Le point de restauration propre** (Q3) | `bench-run`, après la confirmation. Il lit **le point le plus récent** de la VM, celui que le restore prendra, et vérifie qu'il est **propre** (§3.1). Sinon, il en demande un par **la route du bouton 📸**, `POST /api/action/snapshot/<vm>` de la console d'Imladris (`eregion_console/api.py`, `action_snapshot`), attend que le job soit `Completed`, puis attaque | la ligne « point » de `bench-run` : le point gardé et pourquoi, ou celui qui vient d'être pris ; le reçu de la demande (sous FS1) ; le job du coffre | non (à faire, BNC3) |
| 6 | **L'attaque, par Orodruin** | `exercise_runner` rejuge tout (contrat, V1, inscription, zone, le nom tapé contre le nom qu'il lit, plafond), puis `annatar wire` : Run Command sous l'identité d'Orodruin (`injector_vm`), journalisé **avant** l'appel ; `setup_testdata.sh` puis le script de T1486, sous la fenêtre d'exercice | la fenêtre porte l'identifiant de la demande ; `attack_started`, T0 ; le journal d'activité, appelant Orodruin | non |
| 7 | **La détection, l'isolement autonome et sa vérification** | la watch d'Imladris : `Reader` et `Log Analytics Reader` sur le banc, « Response », « Session Drain » sur gondolin ; `isolate_vm` en `non_disruptive` ; la coupure des sessions suivie sur Azure (DRN1) | le cycle `isolate_vm` relu `verified=True` ; la carte d'isolement | non |
| 8 | **Le rapport intermédiaire** | `bench-run` compose `make bench-report RUN=<run_id>` à sa sortie, sur le poste (BNC1) | `runs/bench/<run_id>.json` et son Markdown, sur le poste | non |
| 9 | **L'attente**, en quarantaine | personne : la VM reste isolée, réaffirmée chaque minute (§3.3) | l'état d'isolement d'Imladris, la carte | — |
| 10 | **Le geste 2 : le restore** (§4) | aujourd'hui `make bench-restore TARGET=gondolin RUN=<run_id>` sur le poste, sous la paire de la console ; demain, la carte d'isolement (FS1g, TOT1) | le job du coffre `Completed` ; la neutralisation (SEC17) dans le journal d'activité | **oui** |
| 11 | **La levée, par Imladris** | la watch lit la reprise sur Azure chaque minute (REC1) : le job fini, sur place, le point antérieur, la VM qui tourne, la neutralisation par le seul journal (REC1b) ; aujourd'hui la levée suit le mode de gondolin (`non_disruptive` : seule) ; à venir, LEV1 (LEV3 et suivants) en fait la règle d'un exercice prouvé par le plan de contrôle ; son seul `Reader` | le cycle de son `recovery_complete`, `release_isolation` vérifié ; ou une carte « levée retenue » qui dit pourquoi | non (une carte, si retenue) |
| 12 | **Le rapport final** (§5) | composé seul : sur le poste à la fin de `bench-restore` (BNC3), puis sur Imladris en fin de run (BNC4) | `runs/bench/<run_id>.json` ; le message du bot de Glorfindel | non |
| 13 | **La remise en état** (§6) | les lectures dans le rapport ; les gestes à froid à l'opérateur | la section « état du banc à la fin » du rapport | les gestes à froid |

### 3.1 Le point propre (Q3, Q3b)

**Pourquoi il se vérifie.** Le restore prend le point le plus récent avant T0. Quand les runs
s'enchaînent, ce point peut avoir été pris pendant la quarantaine du run précédent : un instantané
que la watch déclenche sur la VM isolée, ou un point de la politique pris avant son restore. Il
porterait alors les données chiffrées.

**Ce qui est vérifié : le point le plus récent**, celui que le restore prendra, et pas seulement
qu'un point propre existe quelque part. C'est plus strict que la lettre de Q3, et c'est la bonne
lecture : un point propre plus ancien ne servirait pas. Il est propre s'il tient les deux critères :
1. **pris après le dernier restore de la VM**, lu dans les jobs du coffre, sous l'`az login` de
   l'opérateur. Si la liste des jobs ne remonte pas jusqu'au dernier restore (sa profondeur, sa
   rétention), le point est refusé ;
2. **pris hors de toute quarantaine.** La source : les intervalles entre un `isolate_vm` vérifié
   (les cycles de la watch d'Imladris) et sa levée (le cycle du `recovery_complete` de la watch, ou
   un `release_isolation` dans `runs/console/manual_actions.jsonl` et `runs/bot/manual_actions.jsonl`),
   **sur tous les runs**, pas sur le seul run en cours. Le lecteur de BNC1 ne les lit pas
   aujourd'hui (`scripts/bench_h0_reader.py` ne lit que l'isolement courant et les cycles d'un run
   après son T0) : BNC3 l'étend, toujours dans le conteneur jetable, sans réseau, aux montages en
   lecture seule. **Faute de lecture**, ou sur une quarantaine dont la levée ne se lit pas, le
   point est refusé et un nouveau est pris.

**Le trou que ferme Q3b.** Un T1486 dont la détection a manqué ne met pas la VM en quarantaine. Si
elle n'a pas été restaurée depuis, un point pris après est chiffré, et il tiendrait pourtant les deux
critères. Jonathan l'a tranché le 11/11 (Q3b) : le préflight refuse le run sur une VM qui porte un
run destructif sans restore depuis, par un ✗ « restore d'abord » ; un rapport manquant compte comme
un refus. Une VM attaquée et non restaurée ne se rattaque donc pas, et les deux critères suffisent
alors.

**La liste de référence des runs de la VM.** Les rapports de `runs/bench/` ne suffisent pas : un run
sans rapport y est invisible, et aucun rapport n'y « manque ». Un T1486 lancé hors de `bench-run`
(Dagorlad, `make orodruin-exercise`, le repli `annatar run` dans le conteneur d'Orodruin), ou dont
`bench-report` n'a rien composé, y échapperait. Il faut une liste que le run ne peut pas éviter.

| Source | Ce qu'elle voit | Verdict |
|---|---|---|
| **le journal d'activité d'Azure de la VM** | chaque `Microsoft.Compute/virtualMachines/runCommand/action` sur la VM, avec son appelant ; écrit par Azure, pas par Orodruin ; gardé 90 jours | **retenue** pour dire qu'un run a eu lieu : elle couvre un run planté avant son rapport, un envoi de journal perdu, un Orodruin compromis, et un Orodruin reconstruit depuis, qui a changé d'identité |
| le journal d'Orodruin, `audit/<run_id>.jsonl` dans le canal (V-29, `eregion_core/orodruin.py`) | chaque appel d'un injecteur, écrit avant l'appel sur l'hôte ; des blobs d'ajout gardés 90 jours (`journal_retention_days`, `infra/orodruin/variables.tf`) | **pour la technique seulement** : sa poussée vers le canal est faite au mieux (`_journal`, `push_offhost`) ; un canal injoignable ou un 403, et l'appel part quand même, absent du canal |
| les statuts des demandes, `orodruin/requests/<id>.json`, tirés sur Imladris | les demandes seulement | écartée : un `annatar run` lancé sans demande n'y figure pas |
| les rapports de run de la watch, tirés sur Imladris | les runs qui ont publié un rapport | écartée comme liste : un run planté, ou dont le canal était coupé, n'en publie pas |

Comment le préflight la lit :
- **le journal d'activité de la VM**, sous l'`az login` de l'opérateur, qui le lit déjà pour le
  rapport (`scripts/bench_report.py`, BNC1 : chaque Run Command de la cible et son appelant), et le
  lira pour le calme (BNC3) : aucun droit ajouté. **Tout `runCommand/action` sur la VM depuis son
  dernier restore compte, quel que soit l'appelant.** L'appelant sert à dire qui a agi
  (`bench_shared.Roles`), jamais à filtrer : une liste filtrée sur l'identité actuelle d'Orodruin
  laisserait passer une VM chiffrée par l'Orodruin d'avant une reconstruction (§5.5). Une lecture
  coupée (elle atteint sa borne, `MAX_EVENTS`) ou en échec est illisible. Au lot BNC3 : la fenêtre
  de 90 jours face à cette borne, une lecture coupée comptant comme illisible ;
- **un seul appelant ne compte pas comme destructif : Imladris**, dont l'identité est connue, et
  dont le seul Run Command est celui de la défense : **la coupure des sessions** d'une VM qu'il
  isole (`ss -K`, `glorfindel/providers/azure/isolation.py`, `drain_connections` ; DRN1). Encore
  faut-il que ce soit la coupure d'une isolation, et le préflight le juge **sur les isolations
  persistantes** de la watch (Q3c) :
  - **la source** : les cycles `isolate_vm` de la watch sur cette VM, dans `runs/glorfindel/*_debug.jsonl`
    sur Imladris, ceux que BNC3 lit déjà pour « hors de toute quarantaine », par le lecteur de BNC1
    étendu (`scripts/bench_h0_reader.py`, dans son conteneur jetable). Un cycle compte s'il est
    **vérifié** (`verified` vrai dans son résultat) ; le début de l'isolation est `verified_at`
    moins `action_s`. Jamais `drains_at` : il vit dans l'état d'isolation de la VM, que la levée
    efface (`_clear_isolation_state`, `glorfindel/response/state.py`) ;
  - **l'écart retenu** : le Run Command d'Imladris commence entre **2 min avant et 7 min après** le
    début d'une isolation vérifiée. C'est la fenêtre de SID1 autour d'une coupure
    (`DRAIN_BEFORE_S`, 120 s, et `DRAIN_AFTER_S`, 420 s, `glorfindel/providers/azure/own_run_command.py`),
    reprise ici comme modèle, pas comme source : SID1 juge sur le moment, et ne garde ses coupures
    que 2 h en mémoire. La coupure est demandée juste après l'isolation (le 09/11 : 0,5 s après) ;
  - **une coupure sans isolation vérifiée à son heure**, ou hors de l'écart, compte comme
    destructive ; **une isolation illisible** (les cycles qui ne se lisent pas, un `verified_at` ou un
    `action_s` absents) donne le ✗ ;
  - **la raison** *(Jonathan)* : un drill qui isole ne doit pas imposer un restore et un nouveau
    point avant le T1486 suivant.

  Un Run Command d'Imladris hors d'une coupure compte comme destructif. **Un Imladris reconstruit**
  change d'identité, comme Orodruin : ses anciennes coupures sont alors d'un appelant inconnu, et
  comptent comme destructives. C'est prudent, et voulu. **La neutralisation** (SEC17,
  `glorfindel/providers/azure/restore.py`, `_neutralize_run_command`) n'est pas d'Imladris : elle
  vient du principal qui restaure, juste avant le job de restore, donc avant le début de la
  fenêtre ; une neutralisation qu'aucun restore n'a suivie compte comme destructive, comme tout
  autre appelant ;
- **tout autre appelant compte comme destructif** : un ancien Orodruin, l'opérateur à la main, la
  console, un inconnu. **L'Orodruin actuel** compte comme destructif aussi quand la technique de son
  run ne se lit pas : elle vient, elle seule, du journal d'Orodruin dans le canal, lu sous la même
  identité (`channel_operator`, à la portée du conteneur ; l'adresse de l'opérateur passe le
  pare-feu), par le `run_id` des lignes de la VM à cette heure, puis la technique que dit son
  rapport, ou, si c'est sans risque, son `action` ou son `detail`. **Une technique qui ne se lit
  pas compte comme destructive** ;
- **les conséquences, voulues** : un run non destructif dont le journal s'est perdu bloque la VM
  jusqu'à un restore ; après une reconstruction d'Orodruin, une VM qui a reçu un run depuis son
  dernier restore demande un restore ; un Run Command lancé à la main aussi. La règle refuse au
  moindre doute ;
- **« sans restore depuis » se lit dans les jobs du coffre**, déjà lus pour le premier critère du
  point propre, pas dans les rapports : un restore de la VM terminé après le dernier appel du run
  le règle, même fait à la main, hors de `bench-restore`. Cela suppose que le restore garde la même
  VM, le même identifiant : c'est le cas du restore en place de RST1 (à tenir au lot BNC3) ;
- **l'horizon** : le journal d'activité et le journal d'Orodruin remontent à 90 jours. Si le dernier
  restore de la VM est plus ancien, la liste compte comme illisible ;
- **un run de la liste sans restore lisible donne le ✗**, et **une liste illisible aussi** (la
  lecture coupée ou en échec, le dernier restore au-delà de l'horizon, la liste des jobs qui ne
  remonte pas assez).

**Le chemin du bouton 📸.** Quand le point le plus récent n'est pas propre, `bench-run` prend le
chemin du bouton, la route `POST /api/action/snapshot/<vm>` de la console d'Imladris :
- **comment il la joint : par un renvoi de port court qu'il ouvre lui-même**,
  `ssh -N -L 127.0.0.1:<port libre>:127.0.0.1:7007` vers Imladris, avec la clé d'hôte épinglée
  (`glorfindel-host-known`), le temps de la demande et de son reçu, fermé dans tous les cas à la
  fin. Raison : il ne dépend pas du tunnel de MOB2, armé à la demande pour 12 h au plus ; il ne
  laisse rien d'ouvert après lui ; il ne dispute pas le port 7007 au tunnel du téléphone ;
- **le jeton** est celui de la console, lu dans `host.env` par le Makefile, comme pour `make
  console-url-imladris`, et refusé aux sessions d'agent par le même garde (`CONSOLE_GUARD`,
  `scripts/mobile.py guard`). Il passe du Makefile au script **par l'environnement, jamais en
  argv** (en argv, `ps` le montrerait). Il part en `Authorization: Bearer`, jamais dans l'URL,
  jamais affiché. Le `POST` porte un corps JSON (`Content-Type: application/json`) et un `Host` à
  `127.0.0.1:<port>` : deux contrôles d'entrée de la console, à vérifier au lot ;
- **ce que la route fait.** Sans la file d'actions, elle lance l'instantané dans la console, sous
  l'identité d'Imladris (son rôle Response), et rend l'identifiant du job. Sous FS1
  (`EREGION_ACTION_QUEUE=1`), elle dépose une demande signée par la clé de la console, et **c'est la
  watch qui l'exécute** (`_queued`) : la route rend l'identifiant de la demande, et `bench-run` suit
  son reçu, `GET /api/queue/<id>`, jusqu'à une réponse finale. `not_taken`, `untrusted`,
  `refused`, `failed` ou une demande expirée arrêtent le run ;
- **la suite** : le job du coffre, lu par `az backup job show` sous l'`az login` de l'opérateur,
  jusqu'à `Completed`. Le premier point après un restore est complet, et peut prendre environ
  40 min : l'attente est bornée (60 min, à mesurer). Un job qui échoue ou qui dépasse arrête le run
  avant que la demande parte vers Orodruin : rien n'est attaqué ;
- **le préflight rejoué** après l'attente du point, juste avant l'attaque : jusqu'à 60 min ont pu
  passer, et Orodruin ne rejuge ni le calme ni ce qu'Imladris voit de la VM. Un ✗ arrête là. Le point
  pris reste : il est propre, et sans danger ;
- **jamais de `docker exec`** dans un conteneur d'Imladris, ni la CLI de Glorfindel lancée dans celui
  de la console : BNC1 se l'interdit (`scripts/bench_shared.py`, `read_h0`), et FS1 le dit, la CLI
  lancée dans le conteneur de la console y échoue sous la file, et c'est voulu
  (`docs/design/file-actions-signee.md`, §2.12).

### 3.2 Ce qui arrête le run

- **Un préflight rouge** : rien n'est demandé, rien n'est envoyé (`bench-run`, étape 1 de son
  script). Le calme non tenu en est un : un ✗, jamais une attente. « Restore d'abord » aussi.
- **Une VM qui porte un run destructif sans restore depuis** (Q3b) : un ✗ « restore d'abord » du
  préflight ; un rapport manquant compte comme un refus.
- **Un nom mal tapé, « N », ou pas de terminal** : rien ne part, et rien n'est écrit, ni le point ni
  l'attaque. Un nom passé par un tube n'est pas un nom tapé.
- **Pas de point propre** : après la confirmation, `bench-run` en demande un par la route du bouton
  📸 ; si la demande est refusée (`not_taken`, `untrusted`, `refused`, `failed`, expirée), si le job
  échoue ou dépasse son attente, le run s'arrête avant que la demande parte vers Orodruin.
- **Le préflight rejoué après l'attente du point** : un ✗ arrête le run juste avant l'attaque ; le
  point pris reste, sans danger.
- **Le battement absent** (V1) : Orodruin refuse `watch` avant tout appel au cloud, après 10 min de
  relecture. Sans Glorfindel vivant, aucune attaque.
- **« Stop all »** : `make orodruin-kill`, depuis le poste (et montré par Dagorlad,
  `/api/dagorlad/stop`), révoque l'identité d'Orodruin, annule ce qui tourne, ferme les fenêtres.
  Avec DRL1a et BNC5, il supprime aussi les permis et désactive les minuteurs.
- **Le plafond d'Orodruin** (`max_run_s`, le plafond absolu) : le fil est arrêté, sa fenêtre fermée.
- **Le restore qui ne vient pas** : la quarantaine tient (§3.3). Rien ne part seul.
- **Le restore refusé** : il lit ses propres droits avant de toucher la VM (RST1) et dit ce qui
  manque ; la VM reste isolée.
- **Ce qui expire** : ce n'est pas la quarantaine. Ce qui expire, c'est le geste (§4.3) : la
  demande signée d'un clic (FS1), le code de TOT1, la session de la console. La carte du TTL, elle,
  ne lève rien (§3.3).

### 3.3 L'état sûr quand l'humain ne répond pas

Si personne ne restaure, le banc reste dans l'état où la watch l'a mis :
- **la VM est en quarantaine** : le NSG de quarantaine, réaffirmé chaque minute ; les sessions
  coupées (DRN1). Elle le reste tant qu'un humain ne la restaure ni ne la libère ;
- **rien de destructif ne se produit** : l'attaque a chiffré les données de test de gondolin
  (`/mnt/testdata`), qui ne portent rien de réel. Glorfindel ne fait aucune action destructive :
  `isolate_vm` est réversible, et le restore n'est jamais une action de la watch (SEC7) ;
- **rien ne restaure, rien ne lève** : aucune carte séparée de restore n'existe. Sous la quarantaine,
  le graphe n'en recommande pas (décision 2), et rien n'est pré-approuvé. REC1 ne lève qu'après un
  restore lu sur Azure ;
- **la carte du TTL** : passé `GLORFINDEL_ISOLATION_TTL_H` (4 h par défaut), la watch écrit **une**
  carte `ttl_exceeded` et ne lève rien (`glorfindel/reassert.py`, `ttl_alerts` : « never a
  release ») ;
- **gondolin s'éteint à 23:00 UTC** (le planning de Celebrimbor). Le NSG de quarantaine reste
  associé ; au prochain démarrage, elle est toujours isolée ;
- **Orodruin n'a plus rien en vol** : le fil est fini quand `bench-run` rend la main. L'opérateur
  l'éteint, ou l'extinction de 23:00 UTC de DRL1c le fait ;
- **le run se ferme quand même** : le rapport intermédiaire existe (étape 8), et Imladris compose le
  rapport final à la carte du TTL, avec la mention « contained, not restored » (Q1).

L'absence de réponse humaine laisse donc **une VM du banc isolée, chiffrée sur ses données de test,
et rien d'autre** : ce qu'un incident réel contenu et laissé à l'humain laisserait.

---

## 4. Le restore, geste humain

### 4.1 Jamais pré-approuvé

Le restore est un consentement distinct, donné à chaque run, après l'attaque. Ni l'armement d'un
créneau, ni une signature, ni `bench-run` ne le portent : `bench-run` s'arrête au rapport
intermédiaire, et `bench-restore` est une autre commande, avec son propre nom tapé.

### 4.2 Depuis la carte d'isolement, avec FS1g et TOT1

La décision 2 place le restore sur **la carte d'isolement** de la VM, sans carte séparée :
- l'action « Restaurer » de la carte ouvre le formulaire du moment (SEC4c, `glorfindel/restore_plan.py`
  : le moment proposé, les points antérieurs) ;
- le **nom de la VM tapé**, comme dans Dagorlad, puis le **code TOTP** (TOT1, #685), vérifié avant
  tout restore ; sans secret configuré, le restore depuis le bouton est refusé, et la raison dite ;
- le clic dépose une **demande signée** dans la file d'actions (FS1, `docs/design/file-actions-signee.md`) ;
- **FS1g**, un exécuteur de restore à identité propre, seul à tenir Restore et Restore Neutralize,
  vérifie la demande, rejoue les gardes (`glorfindel/approval.py`) et restaure. C'est l'option 2 du
  Q2 de FS1, retenue.

Pourquoi il le faut : la console et le bot de Glorfindel tournent **sur Imladris**. Un bouton y part
sous l'identité d'Imladris, qui n'a pas Restore : Azure le refuse, et la carte le dit. FS1g et TOT1
sont leurs propres lots, après la 0.6.0. BNC2 dit seulement où ils entrent dans le run.

### 4.3 D'ici là : `make bench-restore`, depuis le terminal du poste

Le restore part du poste, au clavier ou depuis le téléphone par le terminal du poste (MOB1), sous la
paire de la console pour cette seule commande. `scripts/bench_restore.py`, dans l'ordre : le garde
de session et le terminal ; la paire présente (ses noms dits, jamais ses valeurs) ; le moment, le T0
du rapport du run (`RUN=`) ; la VM, une seule de ce nom ; le nom tapé ; le dry-run ; « [o/N] » ; puis
`glorfindel restore … --wait --yes --keep-isolated`. `--keep-isolated` toujours : la levée est celle
d'Imladris. La clé matérielle du SSH du téléphone tient lieu de second facteur
(`docs/design/modele-de-menace.md`, frontière 9).

### 4.4 Ce qui expire

- **La quarantaine n'expire pas.** La carte d'isolement reste tant que la VM est isolée, et
  disparaît à la levée : plus de bouton « Restaurer » sur une VM levée.
- **Le geste expire** : une demande de la file vit 120 s au plus (`expires_at`, FS1) ; un code TOTP
  vaut pour son pas de temps (TOT1) ; le cookie de session de la console, 12 h.
- **La carte du TTL** demande à un humain de trancher, et ne lève rien (§3.3).
- **L'approbation en un clic** d'une carte de recommandation (`GLORFINDEL_APPROVAL_MAX_AGE_H`, 2 h,
  `glorfindel/approval.py`) ne concerne pas ce run : il n'y a pas de carte de recommandation de
  restore.

---

## 5. Le rapport composé seul

### 5.1 Où, et pourquoi là

La conception retient **le poste, puis Imladris en fin de run**, là où les droits existent déjà
(décision 3). Le code est celui de BNC1 (`scripts/bench_report.py`, `scripts/bench_shared.py`).

| Lieu | Quand | Ce qu'il lit, avec quels droits | Statut |
|---|---|---|---|
| **le poste** | à la sortie de `bench-run` | l'`az login` de l'opérateur : le journal d'activité des ressources de la cible, les jobs du coffre, la vue d'instance ; les fichiers d'Imladris par SSH, dans un conteneur sans réseau, ses montages en lecture seule (`scripts/bench_h0_reader.py`) | existe (BNC1, MOB1) |
| **le poste** | à la fin de `bench-restore` : il suit la levée, en lecture, 30 min au plus, puis compose | les mêmes | à faire (BNC3) |
| **Imladris** | **en fin de run** : la levée vérifiée, la carte « levée retenue », ou la carte du TTL (Q1) | son identité managée : `Reader` sur le groupe du banc (`infra/glorfindel-host/main.tf`, `bench_reader`), qui lit déjà le journal d'activité (REC1b, LEV2), les jobs du coffre et la vue d'instance (REC1) ; ses propres fichiers | à faire (BNC4) |
| ~~Orodruin~~ | — | ses rôles sont `injector_read`, `injector_vm`, `injector_chaos`, `Log Analytics Reader`, `contract_reader` (la lecture des attributions, pour son contrat) et `channel_writer` (l'écriture du conteneur du canal, qui lui permet aussi d'écrire le permis d'un créneau) (`infra/orodruin/main.tf`) : ni le journal d'activité, ni les jobs du coffre. Il faudrait l'élargir, et il est éteint à la fin du run | écarté (§10.2) |

**Pourquoi Imladris pour la fin.** La levée est son propre geste : il sait quand le run se ferme. Il
est allumé tout le temps. Et quand FS1g fera partir le restore de la carte d'isolement, le poste ne
sera plus dans la boucle : le rapport ne doit pas dépendre d'un terminal resté ouvert. Le poste
garde ses deux compositions, qui donnent tout de suite à l'opérateur ce qu'il vient de faire.

**La limite, dite.** Sur Imladris, c'est le défenseur qui compose le rapport de son propre run. Les
chiffres viennent d'Azure (le journal d'activité, le coffre) et de ses propres fichiers. Il ne les
juge pas : il les recopie, masqués. Le témoin indépendant reste la session Banc, qui relit le
workspace avec sa seule identité (BRO1), et la preuve n'entre au site que par une PR relue (§5.4).

### 5.2 Avec quels droits, et masqué par construction

- **En lecture seule, sur Azure.** Le seul fichier écrit est le rapport lui-même. Aucun appel au
  modèle. Rien du rapport ne va dans `_build_user_message()`, ni dans une décision : c'est une
  sortie, jamais une entrée de la watch (§8).
- **Sur Imladris, hors de la watch.** La composition est une sous-commande en lecture seule, livrée
  dans l'image, à la place du script que le poste envoie aujourd'hui (le docstring de
  `scripts/bench_h0_reader.py` le prévoit). Elle ne tourne pas dans le processus de la watch.
- **Son déclenchement : une unité de l'hôte, sur un marqueur.** En fin de run (Q1), la watch écrit
  un marqueur **dans son propre répertoire**, `runs/glorfindel/bench-pending/<run_id>` : le
  `run_id` et l'événement de fin, rien d'autre. Une unité systemd de l'hôte (un `.path` sur ce
  répertoire, ou un minuteur qui le relit) lance alors un `docker run --rm` de l'image déployée,
  cette sous-commande. **La watch ne reçoit jamais le socket Docker**, et aucun conteneur non plus :
  c'est l'hôte qui lance, comme il lance déjà les services. Les bornes de ce passage du conteneur à
  l'hôte sont au §8.
- **Un écrivain par répertoire (SEC18).** `runs/` a un répertoire par écrivain, écrit par lui seul
  et monté en lecture seule par ceux qui le lisent (`eregion_core/runs_layout.py`,
  `docker-compose.yml`). D'où :
  - le marqueur est dans `runs/glorfindel/`, que la watch écrit déjà ; ses montages en écriture ne
    s'élargissent pas ;
  - la composition lit ce répertoire **en lecture seule**, et ne retire jamais le marqueur : la
    présence de `runs/bench/<run_id>.json` suffit à dire que c'est fait, et l'unité saute un
    marqueur dont le rapport existe. Un marqueur pèse quelques octets par run ;
  - `runs/bench/` devient un **écrivain déclaré** (`runs_layout.WRITERS`, tenu par
    `tests/unit/test_runs_mounts.py`), monté en écriture par la seule composition, en lecture seule
    par la console et le bot qui le montrent ; jamais par la watch.
- **Son identité : celle de la VM, qui écrit.** Le conteneur lit Azure par l'identité managée
  de l'hôte, la seule identité managée d'Imladris. Elle ne tient pas que `Reader` : elle tient aussi
  « Response » et « Session Drain » sur le banc, et l'écriture du canal. **La lecture seule de la
  composition sur Azure ne tient donc que par son code**, et par un mutant (« la composition écrit
  sur Azure »). Ce n'est pas un droit ajouté, mais ce n'est pas une identité de lecture non plus :
  c'est le risque que Jonathan a accepté pour la v1, dit au §8 (Q8).
- **Masqué par construction** : un appelant devient un rôle (la console, le bot, Imladris,
  Orodruin, un humain, inconnu), une ressource devient un nom du banc déjà public, et chaque ligne
  passe par `bench_shared.scrub` (GUID, IPv4, UPN, identifiant ARM). Sur Imladris, les rôles se
  tirent de ce qu'il connaît : sa propre identité, `GLORFINDEL_RESTORE_PRINCIPALS` pour la console.
  Orodruin, par une variable non secrète posée sur Imladris pour nommer et masquer seulement
  (Q7, §5.5). « Inconnu » ne désigne plus qu'un vrai inconnu, et jamais un identifiant ne sort.

### 5.3 Où il est publié

- **Un fichier** : `runs/bench/<run_id>.json` et son Markdown, dans la forme du compte rendu du
  09/11 : « Les chiffres » depuis T0, la chronologie, les Run Command, le `restore_time` en deux
  nombres. Sur le poste pour ses compositions ; sur Imladris pour la sienne, relue depuis le poste
  par le même chemin SSH en lecture seule.
- **Discord** : un message du **bot de Glorfindel**, qui tourne déjà sur Imladris, dans le fil du
  drill de DRL1, le fil du banc (sa décision 4), un message par run (Q2). Le texte passe par `glorfindel/chat_text.py`,
  sans autre mention que le rôle configuré, **sans bouton**. Le jeton du bot de l'atelier ne va
  jamais sur Imladris. Le poste ne poste rien : une seule voix.
- **Une session Banc ne lit que ce rapport** : le fichier, ou le message. En témoin, elle relit le
  workspace du banc avec son seul `Log Analytics Reader` (BRO1). Elle ne reçoit rien de plus.

### 5.4 Comment il alimente `docs/proofs.json`, plus tard

`docs/proofs.json` est la source unique des chiffres du site (ADO2, #671). Chaque figure porte sa
valeur, sa date, sa nature (`measured`, une estimation, un réglage, `to-remeasure`) et sa source :
un fichier du dépôt, la phrase qui donne le chiffre, et son ancre ou **le run** d'où il vient.
`scripts/adoption.py check` refuse une figure sans date ni source.

Un run T1486 produit des chiffres `measured` : la détection, le confinement vérifié, le
`restore_time`, le service rendu, avec le `run_id` pour source. **Aucun run n'écrit
`proofs.json`.** Un lot (BNC6) lit `runs/bench/<run_id>.json` et **propose** une PR qui ajoute ou
met à jour les figures.

**La source est un fichier du dépôt, jamais `runs/`**, que Git ignore. La PR écrit donc aussi la
phrase source : une ligne datée dans une section de `docs/banc-t1486.md` (par exemple « Les runs
mesurés » : la date, le `run_id`, les chiffres, chacun avec sa cause). La figure de `proofs.json` a
pour `source` ce fichier, pour `quote` cette phrase, et pour `run` le `run_id` en référence.
`scripts/adoption.py check` relit la phrase dans le fichier. La relecture la valide avant la fusion. Les
chiffres T1486 du README, aujourd'hui `to-remeasure`, deviennent `measured` run par run, par une
porte relue.

### 5.5 La variable d'Orodruin sur Imladris (Q7), son mode opératoire

**La valeur** : l'identifiant du principal de l'identité managée d'Orodruin, la sortie
`principal_id` de son module (`infra/orodruin/outputs.tf`). Un identifiant, aucun secret. Le poste
n'en a pas besoin dans `.envrc` : BNC1 la lit déjà par `terraform output` (`bench_shared.Roles`).
**Où** : une ligne `EREGION_ORODRUIN_PRINCIPAL_ID=` dans `infra/glorfindel-host/host.env`, jamais
dans le dépôt. **Qui la lit** : la seule composition (BNC4), que l'unité de l'hôte lance avec cette
variable et aucune autre de `host.env`.

Le geste de Jonathan, une fois BNC4 déployé, depuis le poste, en zsh. La valeur va de `terraform`
à une variable du shell, puis au fichier, jamais recopiée de l'écran (zsh marque d'un `%` une sortie
sans fin de ligne : recopiée, elle entre dans la valeur) ; elle n'est jamais affichée.

```zsh
cd ~/eregion && source .envrc
F=infra/glorfindel-host/host.env
grep -c '^EREGION_ORODRUIN_PRINCIPAL_ID=' $F    # → 0 (sinon : la retirer d'abord, sed -i '/^EREGION_ORODRUIN_PRINCIPAL_ID=/d' $F)
P=$(terraform -chdir=infra/orodruin output -no-color -raw principal_id)
print -r -- ${#P}                               # → 36, la longueur d'un GUID (0 : l'état d'Orodruin illisible, s'arrêter)
tail -c1 $F | wc -l                             # → 1 : host.env finit par un saut de ligne (0 : print >> $F d'abord)
print -r -- "EREGION_ORODRUIN_PRINCIPAL_ID=$P" >> $F
unset P
grep -cE '^EREGION_ORODRUIN_PRINCIPAL_ID=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' $F   # → 1, sans l'afficher
make glorfindel-host-push                       # host.env → ~/eregion/.env sur Imladris ; --check dit une valeur qui n'est pas un GUID (BNC4)
make glorfindel-host-ssh                        # puis, sur Imladris :
grep -c '^EREGION_ORODRUIN_PRINCIPAL_ID=' ~/eregion/.env   # → 1
```

**La vérification dans le conteneur** : la sous-commande de composition, en mode contrôle, lancée
par l'unité de l'hôte comme pour un vrai rapport (BNC4 en fixe le nom), dit « orodruin: known » sans
afficher la valeur ; « unknown », la variable n'arrive pas au conteneur : reprendre l'étape du
push. **Après coup** : dans le rapport du run suivant, le Run Command de l'attaque est appelé par
« Orodruin », plus par « inconnu ». **Orodruin reconstruit** (`orodruin-down`, puis `-up`) change
d'identité : refaire le geste ; d'ici là, ses appels redeviennent « inconnu », jamais un
identifiant.

---

## 6. La remise en état

Elle reprend l'étape 9 de `docs/banc-t1486.md`, **sans rien supprimer**.
- **Le nettoyage du scénario** : `setup_testdata.sh` tourne dans le fil, avant l'attaque, et retire
  les fichiers d'un run précédent ; `annatar clean` n'est pas nécessaire sur ce chemin. Après le
  restore, le disque de gondolin est celui d'avant l'attaque.
- **Les lectures, dans le rapport** : une section « état du banc à la fin », lue et jamais écrite
  (BNC3) : gondolin ni isolée ni bloquée ; aucune règle de Glorfindel sur ses NSG (ce que dit
  `glorfindel reset --from-azure --dry-run`) ; les cartes de l'exercice jugées ou acquittées ; aucun
  job du coffre en cours.
- **L'inventaire des disques, sans suppression** (`docs/azure.md`, « Détails Azure à connaître ») : un restore en place
  laisse des disques détachés. Le disque de données et le disque OS d'origine sont suivis par
  Terraform et se gardent ; LEV1 (à venir, LEV3 et suivants) les gardera aussi pour l'enquête, et les nommera. Les disques créés par
  un restore remplacé depuis sont jetables. Le rapport les **relève**, et rappelle que le prochain
  `terraform apply` détachera le disque de données restauré (`clean_lun10`) : le plan se lit avant
  tout apply. La suppression d'un disque jetable reste un **geste à froid de Jonathan**.
- **Les gestes à froid**, à l'opérateur : `make orodruin-stop`, `make celebrimbor-stop` (bree
  épargnée), le CD d'Imladris réactivé s'il a été mis en pause. Les points à la demande expirent
  seuls à 30 jours. gondolin s'éteint à 23:00 UTC.

---

## 7. Le coût

L'automatisation retire du temps humain, pas du temps machine. Ordres de grandeur, **à mesurer** :

| Poste | Un run T1486 (deux gestes) | Un créneau daté |
|---|---|---|
| Orodruin (D2als_v6, environ 61 € par mois en continu, soit environ 0,08 € de l'heure) | allumé environ 1 h 30 par l'opérateur : environ 0,13 € | réveillé 20 à 80 min avant l'heure (Q4), puis allumé jusqu'à l'extinction de 23:00 UTC : de 0,15 € pour un créneau du soir à environ 1,20 € pour un créneau du matin |
| gondolin | de 1 h 30 à 4 h, jusqu'à 23:00 UTC : de 0,15 à 0,40 € | pareil, si le créneau la démarre |
| le coffre | le restore lui-même ; un point à la demande quand le plus récent n'est pas propre (Q3), gardé 30 jours | un instantané si la watch en déclenche un (T1136.001) |
| le réveil (la Logic App) | — | une récurrence horaire, environ 720 exécutions par mois, une lecture de blob chacune : quelques centimes par mois |
| les disques laissés par le restore | quelques euros par mois et par disque, tant que Jonathan ne les supprime pas | — |
| le modèle, sur Imladris | quelques appels : la détection, ses tirages | un appel |
| Imladris, les journaux, le canal, Discord | déjà allumés : négligeable | négligeable |

**Par mois.** À deux runs T1486 et deux créneaux par mois : de l'ordre de **2 à 6 €** de temps
machine, plus les disques gardés, à confirmer au banc. Le drill de la semaine de DRL1 reste à part
(moins de 10 € par mois, §5.3 de `drill-banc.md`). La cadence du T1486 n'est pas un calendrier : un
run après chaque lot qui touche la chaîne (le restore, la coupure, la levée), et quand une preuve
T1486 approche de 30 jours.

---

## 8. Le modèle de menace

BNC2 n'ajoute **aucun chemin** qui lance une attaque ou un restore. Il ajoute un créneau non
destructif sur la machinerie de DRL1 et son réveil, une composition en lecture sur Imladris, un
point propre demandé par `bench-run`, un message du bot, et une proposition de preuve par PR. Frontière par frontière de
[`modele-de-menace.md`](modele-de-menace.md) :

| Frontière | Ce que BNC2 gagne | Ce qu'il ajoute, ou met en risque | Ce qui le tient |
|---|---|---|---|
| **1. La console** | elle ne lance aucune attaque ; le restore depuis la carte d'isolement attend FS1g et TOT1, qui portent leurs propres menaces | **une écriture du poste** : `bench-run` appelle la route du bouton 📸 (`POST /api/action/snapshot/<vm>`) sous le jeton de la console, sans clic. Avant FS1, la console lance l'instantané ; sous FS1, elle dépose une demande signée, et c'est **la watch qui exécute** | la même route, les mêmes gardes que le bouton (le jeton, `_one_slot`, la file sous FS1) ; un seul verbe, l'instantané, qui n'est pas destructif ; le jeton refusé aux sessions d'agent, jamais dans l'URL, jamais affiché ; seulement après le nom tapé et « [o/N] » ; le renvoi de port fermé à la fin |
| **2. `runs/` et l'état local** | — | un écrivain de plus sur Imladris, `runs/bench/` (le rapport) ; un marqueur de plus dans `runs/glorfindel/` | SEC18 tenu : `runs/bench/` est un écrivain déclaré (`runs_layout.WRITERS`, `test_runs_mounts.py`), monté en écriture par la seule composition ; le marqueur reste dans le répertoire de la watch, que la composition lit en lecture seule et ne touche pas. Le rapport n'est **lu par aucune décision** : ni par la watch, ni par REC1, ni par `_build_user_message()` (mutant proposé) |
| **3. Discord** | — | un message de plus du bot de Glorfindel | le texte passe par `chat_text.py`, sans mention sauf le rôle configuré (SEC6), et **sans bouton** ; masqué avant d'être posté |
| **4. Le fournisseur du modèle** | Glorfindel reste aveugle au rouge : rien du rapport, du créneau ni de la demande n'entre dans le message au modèle | — | les trois zones du prompt inchangées ; le test de `test_dagorlad_blind.py`, étendu au créneau |
| **5. Les hôtes : Imladris** | — | un conteneur de plus, lancé par une unité de l'hôte sur un marqueur de la watch, qui lit Azure sous l'identité managée ; et un instantané demandé depuis le poste (Q3), exécuté sous l'identité d'Imladris (Response) | **aucun droit ajouté** : aucune attribution nouvelle dans son Terraform (`infra/glorfindel-host/`) ; la watch n'a jamais le socket Docker ; les montages en lecture seule sauf `runs/bench/`. **Mais l'identité est celle qui écrit** (Response, Session Drain, le canal) : la lecture seule sur Azure ne tient que par le code, son test et son mutant : **risque accepté par Jonathan pour la v1 (Q8)**. À FS1d, la règle `DOCKER-USER` qui coupe IMDS vise aussi ce conteneur |
| **5. Les hôtes : Imladris, du conteneur à l'hôte** | — | **une frontière neuve** : un fichier qu'un conteneur écrit (le marqueur de la watch) déclenche, sur l'hôte, un `docker run` sous le groupe docker, qui vaut root | les bornes, chacune avec son mutant (§9) : le `run_id` est pris du **nom** du fichier, validé par le motif des `run_id` du cœur (`eregion_core/exercise.py`, `_SAFE_RUN_ID`, à exposer par `runs_layout` au lot), et passé en argv, **jamais par un shell** ; le **contenu** du marqueur n'est jamais lu comme argument ; l'image (celle qui est déployée), la commande et les montages sont fixés dans l'unité, rien ne vient du marqueur ; **une composition à la fois**, sous verrou (`flock`), avec un `RuntimeMaxSec`. Un marqueur forgé par la watch ne fait que composer, en lecture, le rapport d'un `run_id` valide |
| **5. Les hôtes : Orodruin** | — | une occurrence armée de plus | la frontière du minuteur proposée par DRL1 (§7 de `drill-banc.md` ; numérotée à son lot de code, puisque la 9 est désormais celle du téléphone) : le même lecteur, le même refus du destructif, la zone `bench`, le contrat, V1. En plus : l'horizon de 7 jours, un créneau à la fois, le registre à part, le permis jamais réécrit |
| **5. Les hôtes : Orodruin, le réveil** | un créneau joue sans qu'on ait allumé Orodruin à la main | l'identité de la Logic App de DRL1c reçoit **une lecture** : `Storage Blob Data Reader` sur le seul conteneur du canal. Ce conteneur porte le journal d'Orodruin, dont les lignes nomment les cibles par leur identifiant ARM, et les fenêtres | une condition ABAC borne la lecture au seul blob `orodruin/slot-permit.json`, lu par un `GET`, sans liste (son mutant ; à mesurer au banc, BNC5b). Sans elle, la même lecture que la watch (`channel_watch_reader`), identifiants compris : dit ici si la mesure l'impose. **Le pare-feu du canal (SEC5) est une garde touchée, et bornée** : une règle d'instance de ressource pour cette seule Logic App, `bypass` gardé à `None`, jamais `AzureServices` (Q4b) ; ses mutants, le bypass élargi et une règle d'instance pour une autre ressource ; relue par Jonathan au plan, à mesurer au banc. Elle n'écrit rien, et ne peut qu'allumer Orodruin ; elle n'allume que sur un permis présent dont l'heure tombe dans l'heure qui vient ; le kill supprime le permis et la désactive ; l'armement n'écrit jamais dans la Logic App. Compromise, elle lit le canal et allume Orodruin, dont le minuteur ne joue qu'à son heure et sous ses gardes |
| **6. La CI et le CD** | — | rien de neuf | la PR de BNC6 passe la CI et la relecture, comme toute PR ; aucun workflow ne lit un rapport |
| **7. Les sessions d'agents** | le transcript d'une session voit le rapport masqué, et non plus les sorties brutes d'`az` | — | les sessions n'arment rien et ne lancent rien : `slot-arm`, `bench-run`, `bench-restore` refusent dans une session d'agent (`session_refusal`) ; `proofs.json` change par une PR relue |
| **8. La session Banc** | elle n'a besoin de rien de plus que le rapport | — | BRO1 n'est pas élargi |
| **9. Le téléphone** | — | rien : les deux gestes du T1486 restent tapés dans le terminal du poste | ce que MOB1 tient déjà, la réserve de `tmux` comprise. `bench-run` porte une écriture de plus, le point propre (Q3) : la route du bouton 📸, jointe par un renvoi de port court à clé d'hôte épinglée, sous le jeton de la console, derrière le même garde de session et le même terminal, après le nom tapé (frontière 1) |

**Par STRIDE, ce qui compte :**
- **S, lancer une attaque sans l'opérateur** : aucun chemin du dehors. Le destructif part du seul
  terminal du poste, nom tapé ; le créneau ne joue que du non destructif, armé par Jonathan, et le
  dehors ne peut que refuser.
- **T, un restore qui remet un disque chiffré** : `bench-run` vérifie que le point le plus récent,
  celui que le restore prendra, est pris après le dernier restore et hors de toute quarantaine, et
  en prend un propre sinon (Q3) ; une VM qui porte un run destructif sans restore n'est pas
  rattaquée (Q3b). Une lecture qui manque refuse le point.
- **T, un créneau qui rejoue ou joue autre chose** : le registre sous le verrou, écrit avant le
  jugement ; `off_slot` ; l'empreinte épinglée ; le catalogue relu dans l'image.
- **E, un créneau qui atteint le destructif, une panne, ou hors du banc** : deux couches
  indépendantes pour chacun (§2.2). Le destructif : le catalogue de l'image, le même contrôle que le
  drill de la semaine, sans seconde forme ; et le nom tapé que le runner exige pour un tel fil, que
  le créneau n'écrit jamais. La panne : le lecteur du `schedule`, et le catalogue au rang 4. Hors du
  banc : le lecteur du `schedule`, et la zone `bench` au jugement et avant chaque fil.
- **E, un marqueur de la watch qui fait agir l'hôte** : les bornes de la frontière « du conteneur à
  l'hôte » (le tableau ci-dessus).
- **E, le rapport qui demande un droit** : composé avec les droits déjà présents ; Orodruin écarté.
  Sur Imladris, ces droits comprennent des écritures, que seul le code n'emploie pas (Q8).
- **R, un run sans trace** : le journal avant chaque appel (O1) ; la demande ; le rapport, daté et
  composé seul.
- **D, l'humain absent** : l'état sûr du §3.3. Rien de pire qu'un incident réel contenu et laissé à
  l'humain.
- **I, ce que le rapport publie** : masqué par construction, un test le scrute. L'heure d'un créneau
  n'est pas dans le dépôt (elle est à l'armement), au contraire du calendrier de DRL1 ; Imladris la
  voit par le permis.

**Ce qui reste ouvert**, dit neutre :
- un Imladris compromis peut écrire un faux rapport de son propre run ; la session Banc relit le
  workspace, et la preuve passe par une relecture ;
- **la composition sur Imladris tient l'identité qui écrit de la watch** (Response, Session Drain,
  l'écriture du canal) : sa lecture seule sur Azure ne tient que par son code et par un mutant
  (« la composition écrit sur Azure »). Jonathan l'a accepté et dit pour la v1 (Q8) ; il se ferme
  à FS1d, quand la règle `DOCKER-USER` qui coupe IMDS vise aussi ce conteneur, et qu'il lit par le
  principal lecteur de la console ;
- **le réveil allume Orodruin sur un permis**, que l'identité d'Orodruin peut écrire : un réveil
  pour rien, une soirée de VM ;
- **le pare-feu du canal admet une ressource de plus**, la Logic App, par une règle d'instance
  (Q4b) : la lecture qu'elle y fait ne tient au seul permis que par la condition ABAC, et la règle
  elle-même reste à mesurer ; si Azure la refuse pour une Logic App, la voie revient à Jonathan ;
- **l'unité de l'hôte lance un conteneur sur un fichier d'un conteneur** : ses bornes tiennent par
  son code, sa validation du `run_id` et ses mutants ; une faille dans l'unité serait une montée de
  la watch vers le groupe docker de l'hôte ;
- root sur Orodruin peut déjà lancer tout injecteur sous le contrat (la limite de DG-b) : le
  créneau ne lui donne rien de plus ;
- l'identité d'Orodruin peut supprimer le permis d'un créneau, ou en écrire un (`channel_writer`) :
  supprimé, Imladris y voit un désarmement, sans alarme d'absence ; écrit, il ne sert qu'avec un
  armement local, que root sur Orodruin tient déjà. Elle n'en a pas besoin pour attaquer ;
- le restore depuis un bouton attend FS1g et TOT1 ; d'ici là, le second facteur est la clé matérielle
  du SSH du téléphone ;
- une session `tmux` qui dure se pilote par tout processus du même utilisateur (frontière 9).

---

## 9. Le découpage en lots de code

Ce document vient d'abord, relu. Le code vient après la 0.6.0.

**Les préalables.** BNC1, MOB1, RST1, DRN1, REC1b et LEV2 sont livrés ; la règle de levée de LEV1 est à venir (LEV3 et suivants). Le créneau suppose DRL1a
(`scheduled_drill`, le permis, le verrou, le registre, l'arrêt du service), DRL1b (le verdict, les
alertes, l'alarme d'absence sur Imladris) et DRL1c (la Logic App, que le réveil prolonge). FS1g et TOT1 avancent à part, et portent le restore depuis la carte.

| Ordre | Lot (proposé) | Session | Contenu | Ce qu'il prouve au banc |
|---|---|---|---|---|
| **1** | **BNC3** (le poste) | Tests, Orodruin | le calme dans le préflight (gondolin démarrée depuis 10 min, aucun run sur elle depuis 10 min) : un ✗ qui dit les minutes qui restent, jamais une attente (Q6) ; « restore d'abord » dans le préflight (Q3b) : la liste de référence des runs de la VM (tout `runCommand/action` sur la VM dans le journal d'activité d'Azure depuis le dernier restore, quel que soit l'appelant, sous l'`az login` de l'opérateur ; seule la coupure des sessions d'Imladris hors du compte, rapprochée des cycles `isolate_vm` vérifiés de `runs/glorfindel/*_debug.jsonl` (de 2 min avant à 7 min après le début de l'isolation ; une isolation illisible donne le ✗) ; la technique d'un run de l'Orodruin actuel dans le journal `audit/` du canal, illisible comptant comme destructive ; la fenêtre de 90 jours face à `MAX_EVENTS`, une lecture coupée comptant comme illisible), le restore lu dans les jobs du coffre (un restore en place, qui garde la VM) ; un ✗ sur un run de la liste sans restore, sur une liste illisible, ou sur un dernier restore au-delà de 90 jours ; le point propre dans `bench-run` (Q3), après le nom tapé et « [o/N] » : le point le plus récent vérifié (après le dernier restore, lu dans les jobs du coffre ; hors de toute quarantaine, par le lecteur de BNC1 étendu aux intervalles d'isolement de tous les runs), sinon demandé par la route du bouton 📸 (le renvoi de port court, le jeton de la console, le reçu sous FS1) et attendu jusqu'à `Completed` avant l'attaque ; `bench-restore` qui suit la levée en lecture, 30 min au plus, puis compose le rapport ; la section « état du banc à la fin » et l'inventaire des disques dans le rapport, en lecture | un T1486 en deux gestes, et un rapport complet composé sans rien taper ; aucun ✓ sur un banc pas calme ; **deux runs enchaînés** : au second, le point le plus récent est celui pris pendant la quarantaine du premier, `bench-run` le refuse, en prend un propre par la route, attend `Completed`, puis attaque, et le restore du second prend ce point ; **un T1486 sans restore**, puis `bench-run` sur la même VM : ✗ « restore d'abord » ; son rapport retiré : ✗ aussi ; **un T1486 lancé par `make orodruin-exercise`**, hors de `bench-run` : ✗ aussi ; **un T1486 dont l'envoi du journal vers le canal est coupé** : ✗ quand même, par le journal d'activité ; **Orodruin reconstruit entre deux T1486** : ✗ quand même ; **une VM restaurée, puis isolée par une détection et levée, dont le seul Run Command depuis le restore est la coupure de cette isolation** : pas de ✗ ; sa contre-épreuve, **une coupure sans isolation vérifiée à son heure** : ✗ ; un restore fait à la main : le ✗ levé ; un nom mal tapé : aucun point demandé |
| **2** | **BNC4** (Imladris) | Glorfindel, Console | la sous-commande de composition, en lecture seule, livrée dans l'image ; le marqueur de fin de run, écrit par la watch dans `runs/glorfindel/bench-pending/` (la levée, la carte « levée retenue », la carte du TTL) ; l'unité de l'hôte qui lance le `docker run --rm`, avec ses bornes ; la variable d'Orodruin (Q7) passée au seul conteneur de la composition, son mode contrôle, la clé `EREGION_ORODRUIN_PRINCIPAL_ID` connue de `host_env.py --check` (un GUID), et le mode opératoire du §5.5 dans `infra/glorfindel-host/README.md` ; `runs/bench/` déclaré dans `runs_layout.WRITERS` et `test_runs_mounts.py` ; le fichier `runs/bench/<run_id>.json` ; le message du bot de Glorfindel dans le fil du drill, sans bouton | le rapport final posté sans personne au poste, masqué ; aucune attribution de rôle ajoutée à Imladris |
| **3** | **BNC5** (Orodruin) | Orodruin, Glorfindel | le créneau daté : `scheduled_drill run --slot`, son armement, son permis, son registre, l'horizon, un créneau à la fois ; les cibles `orodruin-slot-check`, `-arm`, `-disarm` ; ses unités ; le pas du kill ; `orodruin/slot.json` et son lecteur exact sur Imladris ; l'alarme d'absence « slot not run » | le créneau joue une fois à l'heure armée, refuse après, refuse un drill destructif, ne joue plus après un kill ; manqué et dit si Orodruin n'est pas allumé à l'heure |
| **3b** | **BNC5b** (Terraform) | Orodruin, Infra | le réveil (§2.7) : la récurrence horaire de la Logic App de DRL1c, sa lecture du permis, sa condition sur l'heure qui vient ; le rôle `Storage Blob Data Reader` de son identité à la portée du seul conteneur du canal, avec la condition ABAC qui borne la lecture au seul permis, lu par un `GET` ; la règle d'instance de ressource du pare-feu du canal pour cette seule Logic App, `bypass` à `None` (Q4b) ; la condition qui distingue les deux récurrences ; la lecture de son état par `slot-arm`. Les gestes de Jonathan : `make orodruin-plan`, relu (la récurrence, l'attribution et sa condition, la règle d'instance), puis `make orodruin-lock` | Orodruin éteint, un créneau armé est réveillé et joue à l'heure ; sans permis, rien ne s'allume ; après un kill, rien ne s'allume |
| **4** | **BNC6** (la preuve) | Orchestre | un script qui lit `runs/bench/<run_id>.json` et prépare, dans une branche, la ligne datée de `docs/banc-t1486.md` et le changement de `docs/proofs.json` qui la cite, que `scripts/adoption.py check` passe ; jamais un push sur `main` | un run mesuré devient une figure datée et sourcée, par une PR relue |

**Mutants proposés** (la plage, à demander à l'Orchestre au lot de code) :
- un créneau qui admet une technique destructive, ou une panne ;
- un drill livré sans `schedule` armé en créneau (`bl1-reponse`) ;
- le contrôle du catalogue au rang 4 qui admet une panne ;
- le créneau qui écrit un nom tapé ;
- le registre des créneaux lu hors du verrou, ou écrit après le jugement ;
- `off_slot` sauté ; un `at` au-delà de l'horizon admis ;
- un permis de créneau absent pris pour un armement ;
- un créneau qui consomme l'occurrence de la semaine (le registre partagé) ;
- un second créneau armé par-dessus le premier ;
- le kill qui laisse le permis du créneau ;
- Orodruin qui réécrit le permis d'un créneau ;
- l'armement d'un créneau admis dans une session d'agent ;
- le calme sauté par le préflight ;
- le calme attendu au lieu d'être refusé ;
- un point pris pendant une quarantaine est accepté ;
- un point d'avant le dernier restore de la VM est accepté, ou accepté quand la liste des jobs ne montre pas le dernier restore ;
- un historique des quarantaines illisible pris pour vide ;
- un point propre plus ancien accepté quand le plus récent ne l'est pas ;
- un run accepté sur une VM qui porte un destructif sans restore ;
- un rapport manquant pris pour un restore ;
- un T1486 lancé hors de `bench-run` échappe à « restore d'abord » ;
- un run absent du journal du canal échappe à « restore d'abord » ;
- la liste filtrée sur l'identité actuelle d'Orodruin ;
- un Run Command d'un appelant inconnu pris pour non destructif ;
- un Run Command d'Imladris hors d'une coupure de sessions pris pour non destructif ;
- une coupure rapprochée d'une isolation non vérifiée, ou hors de l'écart ;
- l'exemption d'une coupure jugée sur `drains_at` au lieu des cycles persistants ;
- une isolation illisible prise pour une coupure exemptée ;
- la liste prise dans le journal d'Orodruin au lieu du journal d'activité d'Azure ;
- un dernier restore au-delà de 90 jours, ou une lecture du journal d'activité coupée, pris pour une liste vide ;
- une liste de référence illisible prise pour vide ;
- un run dont la technique ne se lit pas pris pour non destructif ;
- un restore fait à la main, hors de `bench-restore`, non compté ;
- le point demandé avant le nom tapé et « [o/N] » ;
- le préflight non rejoué après l'attente du point ;
- le jeton de la console passé au script en argv ;
- l'attaque lancée avant que le point demandé soit `Completed` ;
- le point demandé par `docker exec`, ou par la CLI dans le conteneur de la console, au lieu de la route ;
- le jeton de la console dans l'URL, affiché, ou donné dans une session d'agent ;
- le renvoi de port de `bench-run` laissé ouvert ;
- la condition ABAC du réveil absente (la lecture de tout le conteneur) ;
- le réveil déclenché par la récurrence de la semaine pour un créneau, ou l'inverse ;
- le `bypass` du pare-feu du canal élargi (`AzureServices`, ou autre que `None`) ;
- une règle d'instance de ressource pour une autre ressource que la Logic App du réveil ;
- la Logic App qui liste le conteneur au lieu de lire le permis par son chemin ;
- le réveil qui allume Orodruin sans permis, ou pour une heure hors de l'heure qui vient ;
- la lecture du réveil à la portée du compte du canal au lieu du seul conteneur ;
- l'armement qui écrit dans la Logic App ;
- une heure armée dont l'occurrence ne finirait pas avant 23:00 UTC admise ;
- la variable d'Orodruin passée à un autre conteneur que la composition ;
- `bench-restore` qui lève, ou qui compose sans attendre la levée ;
- la composition sur Imladris qui écrit hors de `runs/bench/`, ou qui appelle le modèle ;
- la composition qui écrit sur Azure ;
- la watch qui reçoit le socket Docker, ou qui lance elle-même la composition ;
- la watch qui monte `runs/bench/` en écriture ;
- la composition qui écrit dans le répertoire de la watch (ou qui retire le marqueur) ;
- l'unité de l'hôte qui prend un `run_id` non validé, ou qui le passe par un shell ;
- l'unité qui lit le contenu du marqueur comme argument ;
- deux compositions à la fois, ou une composition sans `RuntimeMaxSec` ;
- à FS1d, la règle `DOCKER-USER` qui oublie le conteneur de la composition ;
- le rapport lu par la watch ou par `_build_user_message()` ;
- `scrub` sauté, ou un identifiant d'Orodruin imprimé faute de rôle ;
- un message du bot avec un bouton, ou une mention ;
- `proofs.json` écrit directement par un run.

**Ce qui reste à Jonathan** : relire ce document ; armer, désarmer chaque créneau ; lancer chaque
T1486 et chaque restore ; supprimer les disques jetables ; le plan et l'apply du réveil (BNC5b :
`make orodruin-plan`, relu, dont la règle d'instance du pare-feu du canal et son `bypass` à `None`,
puis `make orodruin-lock`) et tout autre apply ; trancher la voie du réveil si Azure refuse la règle
d'instance pour une Logic App ; poser la variable d'Orodruin
sur Imladris, une fois BNC4 déployé (§5.5).

---

## 10. Les décisions de Jonathan, et les options écartées

### 10.1 Décisions de Jonathan (11/11)

Prises une à une, sur les huit questions de cette conception. Q1, Q2 et Q5 à Q8 suivent l'option
recommandée ; pour Q3, Jonathan a retenu l'option 2, pour la raison des runs enchaînés ; pour Q4,
une option nouvelle : un réveil qui lit le créneau. Q3b, prise à la quatrième relecture, ferme le
trou de Q3 ; Q3c, prise à la huitième, dit quand une coupure d'Imladris ne compte pas. Dans la colonne « Raison », *(Jonathan)* marque sa raison, *(le document)* celle de la
conception.

| | Décision | Raison |
|---|---|---|
| **Q1. La fin du run, pour Imladris** | Au premier des trois événements : la levée vérifiée, la levée retenue, la carte du TTL. Le rapport dit lequel (« restored and lifted », « lift held », « contained, not restored ») (§3.3, §5.1) | *(le document)* Le run se ferme toujours, même sans réponse humaine |
| **Q2. Où le rapport est publié** | Dans le fil du banc, celui du drill de DRL1, un message par run, sans bouton ; le poste ne publie rien (§5.3) | *(le document)* Un seul fil du banc, déjà décidé pour les alertes du drill (décision 4 de DRL1) ; une seule voix |
| **Q3. Le point de restauration propre** | `bench-run` vérifie qu'un point propre existe, pris après le dernier restore de la VM et hors de toute quarantaine ; sinon il en demande un par le chemin du bouton 📸 (la console d'Imladris), attend qu'il soit terminé, puis lance l'attaque. Le document vérifie le point le plus récent, celui que le restore prendra, et passe par la route du bouton (§3, étape 5 ; §3.1) | *(Jonathan)* Quand les runs s'enchaînent, « le plus récent avant T0 » peut être un point pris pendant la quarantaine du run précédent, donc chiffré |
| **Q3b. Restore d'abord** | Quand la VM porte un run destructif sans restore depuis (lu dans les rapports de `runs/bench/`), le préflight refuse le run : ✗ « restore d'abord », comme pour le calme ; un rapport manquant compte comme un refus. Les deux critères du point propre suffisent alors. Le document nomme la liste de référence, pour qu'un rapport puisse « manquer » : tout Run Command sur la VM dans le journal d'activité d'Azure depuis le dernier restore, quel que soit l'appelant ; seule la coupure des sessions d'Imladris n'y compte pas, rapprochée d'une isolation vérifiée (Q3c) ; le journal d'Orodruin ne dit que la technique d'un run de l'Orodruin actuel, et une technique illisible compte comme destructive ; « sans restore » se lit dans les jobs du coffre ; au-delà de 90 jours, illisible (§3, étape 3 ; §3.1) | *(la relecture, retenue par Jonathan)* Un T1486 dont la détection a manqué laisse la VM chiffrée sans quarantaine : un point pris après passerait pour propre |
| **Q3c. La coupure d'Imladris** | Une coupure de sessions d'Imladris ne compte pas comme destructive si elle tombe à quelques minutes d'un `isolate_vm` vérifié de la watch sur cette VM (les cycles que BNC3 lit déjà pour « hors quarantaine ») ; une isolation illisible donne le ✗. Le document retient l'écart de SID1 : de 2 min avant à 7 min après le début de l'isolation, lu dans `runs/glorfindel/*_debug.jsonl` (§3.1) | *(Jonathan)* Un drill qui isole ne doit pas imposer un restore et un nouveau point avant le T1486 suivant |
| **Q4. Le réveil d'Orodruin** | Un réveil qui lit le créneau : la Logic App, déclarée une fois dans Terraform, regarde chaque heure dans le canal si un créneau est armé pour l'heure qui vient, et allume Orodruin. L'armement n'écrit qu'une donnée ; la Logic App reçoit une lecture sur ce seul conteneur du canal (§2.7) | *(le document)* Un créneau qui ne joue que si quelqu'un a allumé Orodruin n'en est pas un ; l'armement ne touche pas l'infrastructure |
| **Q4b. Le pare-feu du canal** | Une règle d'instance de ressource sur le compte du canal, pour cette Logic App seule (son identité managée) ; `bypass` gardé à `None`, jamais « AzureServices » ; la lecture reste bornée au permis par l'ABAC ; relue par Jonathan au plan, son mutant « bypass élargi », à mesurer au banc ; si Azure ne l'accepte pas pour une Logic App, retour à Jonathan (§2.7) | *(la relecture, retenue par Jonathan)* Le pare-feu du canal (SEC5) ferme tout par défaut : sans règle, la Logic App ne lit pas le permis. La voie la plus étroite garde le compte fermé à tout autre service |
| **Q5. Combien de créneaux** | Un créneau à la fois en v1 ; pour en poser un autre, désarmer le précédent, joué ou non (§2.3) | *(le document)* Un seul état à juger ; sous la rétention du canal, le permis n'a jamais à être réécrit |
| **Q6. Le calme** | Un ✗ du préflight, jamais une attente : `bench-run` refuse, dit les minutes qui restent, l'opérateur relance (§3, étape 3) | *(le document)* Une commande qui attaque ne garde pas la main en attendant |
| **Q7. Le rôle d'Orodruin dans le rapport d'Imladris** | Une variable non secrète sur Imladris, l'identifiant du principal d'Orodruin, pour nommer et masquer seulement ; « inconnu » ne désigne plus qu'un vrai inconnu. Le mode opératoire complet est au §5.5 | *(Jonathan)* « Inconnu » ne désigne plus qu'un vrai inconnu ; *(le document)* l'attaquant du run se nomme dans son propre rapport, sans droit ajouté |
| **Q8. L'identité de la composition sur Imladris** | Le risque accepté et dit pour la v1 : l'identité de la VM, la lecture seule tenue par le code, son test et son mutant, écrit au §8. Au moment de FS1d, la règle `DOCKER-USER` qui coupe IMDS vise aussi le conteneur de la composition, qui lit alors par le principal lecteur de la console (§5.2) | *(le document)* La décision 3 : aucune identité nouvelle. FS1 ferme le risque à son heure |

### 10.2 Les options écartées, et leur raison

Le premier jet du 10/11 en proposait plusieurs, que le cadre du 10/11 exclut ; les décisions du
11/11 en écartent d'autres, en bas du tableau.

| Option écartée | Pourquoi |
|---|---|
| **Le T1486 joué par un créneau armé**, l'attaque partant seule à l'heure armée (le cœur du premier jet) | Décision 1 : le destructif part de la main de l'opérateur. BL1b : le script de T1486 est un script maison, et un drill ne joue qu'une bibliothèque publique. DRL1 : un drill planifié est non destructif |
| **Une « forme à occurrence unique » du lecteur de drill qui admet le destructif** sous la zone `bench` et un nom tapé (premier jet, §2.2) | La même raison. Une seconde forme du lecteur serait un chemin de plus vers le destructif, que rien d'autre ne garde |
| **Le nom de la cible tapé à l'armement**, pour une attaque destructive jouée des jours plus tard | Un nom tapé est un consentement au moment du geste, pas une réserve. Tapé des jours avant, il ne dit plus rien |
| **Un lancement distant** : la console, Discord, un workflow planifié, ou un ordonnanceur sur Imladris déclenche l'attaque | Casse « Orodruin ne tire ni n'écoute rien ». Un chemin d'écriture du dehors vers une attaque est ce que DRL1 et le modèle de menace excluent |
| **La pré-approbation du restore**, par l'armement, une signature, ou un `bench-run` qui enchaînerait le restore après la détection | Le restore est destructif, et il reste un consentement distinct à chaque run (décision 2) |
| **Une carte séparée de recommandation de restore**, que la watch écrirait après l'isolement (premier jet, étape 5) | Sous la quarantaine, le graphe ne recommande pas de restore, faute de nouvelle détection (DRN1). L'y forcer toucherait le graphe ou le prompt. Le restore part de la carte d'isolement |
| **Le restore depuis le bouton de la console ou du bot d'Imladris, aujourd'hui** | Il part sous l'identité d'Imladris, qui n'a pas Restore : Azure le refuse. Il faut FS1g et TOT1 |
| **Donner à Imladris le rôle Restore** | Casse SEC7 et l'étroitesse d'Imladris ; son Terraform refuse de le lui donner |
| **Un restore autonome par la watch** | Défait SEC7 : une watch compromise pourrait écraser des disques. La seule voie propre vers un restore encadré est un exécuteur à part (FS1g) |
| **Composer le rapport sur Orodruin** | Il faudrait lui donner la lecture du journal d'activité et des jobs du coffre : une identité élargie. Et il est éteint à la fin du run |
| **Élargir BRO1** pour que la session Banc compose elle-même le rapport | La décision 3 : aucune identité nouvelle, et la session Banc ne lit que le rapport. BRO1 reste tel qu'il est |
| **Un écrivain automatique de `docs/proofs.json`** | Un run écrirait une figure du site public sans relecture. La preuve n'entre que par une PR relue |
| **La composition dans le processus de la watch** | Elle ajouterait du code et des appels au processus qui décide. Elle tourne à part, déclenchée par la watch (§5.2) |
| Q1 : **le run fini à la levée seulement** | Un run sans restore ne se fermerait jamais, et n'aurait que le rapport intermédiaire du poste |
| Q2 : **un fil par run**, ou **le fil de la VM** | Un fil à créer et à archiver à chaque run ; ou le rapport mêlé aux cartes de la VM |
| Q2 : **le poste qui publie aussi** | Deux voix pour un même run, et le jeton du bot de l'atelier dans la chaîne |
| Q3 : **le point pris par `docker exec`**, la CLI de Glorfindel lancée dans le conteneur de la console | Contourne la file d'actions de FS1, où seule la watch écrit, et cesse de marcher quand la console perd IMDS (FS1d). BNC1 s'interdit tout `docker exec` dans un conteneur d'Imladris. Le point passe par la route du bouton 📸 |
| Q3 : **aucun point pris par le run**, le restore prenant le plus récent avant T0 | Quand les runs s'enchaînent, ce point peut être pris pendant la quarantaine du run précédent : le restore remettrait un disque chiffré |
| Q4 : **aucun réveil**, le créneau ne jouant que si Orodruin est déjà allumé | Le créneau manquerait chaque fois qu'Orodruin est éteint, c'est-à-dire presque toujours |
| Q4 : **l'armement qui écrit une occurrence dans la Logic App** | Un écart avec l'état de Terraform, et un armement qui touche l'infrastructure |
| Q4 : **une seconde Logic App**, réservée aux créneaux | Une ressource et une identité de plus, pour ce que la première fait par une récurrence |
| Q5 : **plusieurs créneaux à la fois** | Écarté pour la v1 : un seul état à juger. *(Jonathan)* Élargi si l'usage le demande |
| Q5 : **un horizon plus long** | Au-delà de la rétention du canal, Orodruin devrait réécrire le permis : une écriture de plus, et son mutant |
| Q6 : **`bench-run` qui attend lui-même les minutes qui restent** | Une commande qui attaque garderait la main en attendant |
| Q7 : **aucune variable**, Orodruin dit « inconnu » | L'attaquant du run serait inconnu dans son propre rapport, et « inconnu » ne distinguerait plus un vrai inconnu |
| Q4b : **le `bypass` à `AzureServices`** pour laisser passer la Logic App | Ouvrirait le compte du canal à tout service d'Azure, d'un autre client compris : la garde de SEC5 tomberait pour tous, quand une règle d'instance ne l'ouvre qu'à une ressource |
| Q8 : **une identité de lecture à part** pour la composition | Une identité nouvelle, que la décision 3 exclut ; FS1 ferme le même risque sans elle |

---

## Ce que ce document ne décide pas

- Rien n'est mesuré : le calme lu dans le journal d'activité, le point propre et son attente, la
  composition sur Imladris, le réveil et le créneau à l'heure, le coût réel sont des hypothèses, à
  prouver au banc.
- Le restore depuis la carte d'isolement est à FS1g et TOT1 : leur file, leur exécuteur, leur code,
  leur frontière.
- La levée d'un exercice suit la règle de LEV1 et ses lots de code (LEV3 et suivants) : BNC2 la lit,
  il ne la change pas.
- Les noms exacts des cibles Make, des unités et des fichiers du créneau sont au lot BNC5, à la forme
  de DRL1a.
- Les décisions du 11/11 (§10.1) s'appliquent aux lots de code. Ce qui en dépend d'Azure (le réveil
  de la Logic App, la durée d'un point après un restore) se mesure au banc.
