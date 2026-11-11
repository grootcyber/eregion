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
| le point de restauration propre, vérifié, et pris s'il manque | le poste, dans `bench-run`, par le chemin du bouton 📸 d'Imladris | à faire (BNC3) |
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
préflight (BNC1) ─ calme ─ demande ─▶ Orodruin (rejuge : contrat, V1, zone, nom tapé, plafond)
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
heure trop proche pour le réveil (§2.7) : moins de 80 min après l'armement, Orodruin éteint.

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
  à la portée du conteneur `exercises` (`infra/orodruin/main.tf`), jamais du compte. Elle y lit ce
  que le canal publie déjà (fenêtres, statuts, rapports, permis), sans identifiant ni cible. Elle
  n'y écrit rien ;
- **elle ne joue rien** : elle allume une VM. Le minuteur d'Orodruin, ses gardes (§2.6) et le permis
  décident seuls de l'occurrence. Allumé pour rien (un permis forgé par Orodruin, qui peut écrire le
  canal), Orodruin coûte une soirée de VM, puis s'éteint à 23:00 UTC ;
- **le kill** supprime le permis : plus de réveil. Il désactive aussi la Logic App, comme dans DRL1
  (§3.1 de `drill-banc.md`). `slot-arm` lit son état, en lecture seule : désactivée, il le dit
  (« the wake-up is disabled »), et refuse, puisque le réveil ne viendrait pas. Le réarmement du
  drill de la semaine la réactive (DRL1).

**Les gestes de Jonathan** (BNC5b) : `make orodruin-plan`, relu (une récurrence de plus, une
attribution de rôle à la portée du conteneur, rien d'autre), puis `make orodruin-lock`, qui en est
l'apply. Aucun droit nouveau pour l'identité d'Orodruin.

**À mesurer** : la lecture d'un blob par la Logic App sous son identité managée ; le JSON du permis
lu par son expression ; le délai entre le réveil et docker prêt (les 20 min de marge
suffisent-elles ?) ; le coût d'une récurrence horaire.

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
| 3 | **Le calme** : gondolin démarrée depuis 10 min au moins, aucun run sur elle depuis 10 min | le préflight, en lecture (le journal d'activité de la VM, les rapports de `runs/bench/`) | une ligne de plus du préflight (BNC3) : un ✗ qui dit les minutes qui restent, jamais une attente ; l'opérateur relance (Q6). Aujourd'hui, la montre de l'opérateur | non (à faire) |
| 4 | **Le point de restauration propre** (Q3) | `bench-run`, après le préflight. Il lit le point que le restore prendra, le plus récent de la VM, et vérifie qu'il est **propre** : pris après le dernier restore de la VM (les jobs du coffre) et **hors de toute quarantaine** (l'historique d'isolement d'Imladris, lu comme BNC1 le lit). Sinon, il en demande un par le chemin du bouton 📸 : `glorfindel snapshot --yes --wait` dans le conteneur de la console d'Imladris, par le SSH à clé d'hôte épinglée, sous l'identité d'Imladris (son rôle Response, aucun droit ajouté). Il attend que le job soit terminé, `Completed`, puis attaque | la ligne « point » de `bench-run` : le point gardé et pourquoi, ou celui qui vient d'être pris ; le job du coffre ; `runs/console/manual_actions.jsonl` sur Imladris | non (à faire, BNC3) |
| 5 | **La demande**, puis **le nom tapé** et « [o/N] » | le poste écrit la demande par le lecteur de Dagorlad (`exercise_request.new`) ; le nom de la VM, tapé, est comparé à celui qu'Azure donne | la demande, son identifiant ; un autre nom, et rien ne part | **oui** (fait partie du geste 1) |
| 6 | **L'attaque, par Orodruin** | `exercise_runner` rejuge tout (contrat, V1, inscription, zone, le nom tapé contre le nom qu'il lit, plafond), puis `annatar wire` : Run Command sous l'identité d'Orodruin (`injector_vm`), journalisé **avant** l'appel ; `setup_testdata.sh` puis le script de T1486, sous la fenêtre d'exercice | la fenêtre porte l'identifiant de la demande ; `attack_started`, T0 ; le journal d'activité, appelant Orodruin | non |
| 7 | **La détection, l'isolement autonome et sa vérification** | la watch d'Imladris : `Reader` et `Log Analytics Reader` sur le banc, « Response », « Session Drain » sur gondolin ; `isolate_vm` en `non_disruptive` ; la coupure des sessions suivie sur Azure (DRN1) | le cycle `isolate_vm` relu `verified=True` ; la carte d'isolement | non |
| 8 | **Le rapport intermédiaire** | `bench-run` compose `make bench-report RUN=<run_id>` à sa sortie, sur le poste (BNC1) | `runs/bench/<run_id>.json` et son Markdown, sur le poste | non |
| 9 | **L'attente**, en quarantaine | personne : la VM reste isolée, réaffirmée chaque minute (§3.2) | l'état d'isolement d'Imladris, la carte | — |
| 10 | **Le geste 2 : le restore** (§4) | aujourd'hui `make bench-restore TARGET=gondolin RUN=<run_id>` sur le poste, sous la paire de la console ; demain, la carte d'isolement (FS1g, TOT1) | le job du coffre `Completed` ; la neutralisation (SEC17) dans le journal d'activité | **oui** |
| 11 | **La levée, par Imladris** | la watch lit la reprise sur Azure chaque minute (REC1) : le job fini, sur place, le point antérieur, la VM qui tourne, la neutralisation par le seul journal (REC1b) ; aujourd'hui la levée suit le mode de gondolin (`non_disruptive` : seule) ; à venir, LEV1 (LEV3 et suivants) en fait la règle d'un exercice prouvé par le plan de contrôle ; son seul `Reader` | le cycle de son `recovery_complete`, `release_isolation` vérifié ; ou une carte « levée retenue » qui dit pourquoi | non (une carte, si retenue) |
| 12 | **Le rapport final** (§5) | composé seul : sur le poste à la fin de `bench-restore` (BNC3), puis sur Imladris en fin de run (BNC4) | `runs/bench/<run_id>.json` ; le message du bot de Glorfindel | non |
| 13 | **La remise en état** (§6) | les lectures dans le rapport ; les gestes à froid à l'opérateur | la section « état du banc à la fin » du rapport | les gestes à froid |

**Pourquoi le point se vérifie (Q3).** Le restore prend le point le plus récent avant T0. Quand les
runs s'enchaînent, ce point peut avoir été pris pendant la quarantaine du run précédent : un
instantané que la watch déclenche sur la VM isolée, ou un point de la politique pris avant son
restore. Il porterait alors les données chiffrées. `bench-run` refuse donc un point pris avant le
dernier restore ou pendant une quarantaine, et en prend un propre avant l'attaque. Le premier point
après un restore est complet, et peut prendre environ 40 min : l'attente est bornée (60 min, à
mesurer), et un job qui échoue ou dépasse arrête le run avant la demande, rien n'est envoyé.

### 3.1 Ce qui arrête le run

- **Un préflight rouge** : rien n'est demandé, rien n'est envoyé (`bench-run`, étape 1 de son
  script). Le calme non tenu en est un : un ✗, jamais une attente.
- **Pas de point propre** : `bench-run` en demande un ; s'il échoue ou dépasse son attente, le run
  s'arrête avant la demande.
- **Un nom mal tapé, ou pas de terminal** : rien ne part. Un nom passé par un tube n'est pas un nom
  tapé.
- **Le battement absent** (V1) : Orodruin refuse `watch` avant tout appel au cloud, après 10 min de
  relecture. Sans Glorfindel vivant, aucune attaque.
- **« Stop all »** : `make orodruin-kill`, depuis le poste (et montré par Dagorlad,
  `/api/dagorlad/stop`), révoque l'identité d'Orodruin, annule ce qui tourne, ferme les fenêtres.
  Avec DRL1a et BNC5, il supprime aussi les permis et désactive les minuteurs.
- **Le plafond d'Orodruin** (`max_run_s`, le plafond absolu) : le fil est arrêté, sa fenêtre fermée.
- **Le restore qui ne vient pas** : la quarantaine tient (§3.2). Rien ne part seul.
- **Le restore refusé** : il lit ses propres droits avant de toucher la VM (RST1) et dit ce qui
  manque ; la VM reste isolée.
- **Ce qui expire** : ce n'est pas la quarantaine. Ce qui expire, c'est le geste (§4.3) : la
  demande signée d'un clic (FS1), le code de TOT1, la session de la console. La carte du TTL, elle,
  ne lève rien (§3.2).

### 3.2 L'état sûr quand l'humain ne répond pas

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
- **La carte du TTL** demande à un humain de trancher, et ne lève rien (§3.2).
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
print -r -- "EREGION_ORODRUIN_PRINCIPAL_ID=$P" >> $F
unset P
grep -cE '^EREGION_ORODRUIN_PRINCIPAL_ID=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' $F   # → 1, sans l'afficher
make glorfindel-host-push                       # host.env → ~/eregion/.env sur Imladris
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
| **1. La console** | rien de neuf à défendre : elle ne lance rien ; le restore depuis la carte d'isolement attend FS1g et TOT1, qui portent leurs propres menaces | — | — |
| **2. `runs/` et l'état local** | — | un écrivain de plus sur Imladris, `runs/bench/` (le rapport) ; un marqueur de plus dans `runs/glorfindel/` | SEC18 tenu : `runs/bench/` est un écrivain déclaré (`runs_layout.WRITERS`, `test_runs_mounts.py`), monté en écriture par la seule composition ; le marqueur reste dans le répertoire de la watch, que la composition lit en lecture seule et ne touche pas. Le rapport n'est **lu par aucune décision** : ni par la watch, ni par REC1, ni par `_build_user_message()` (mutant proposé) |
| **3. Discord** | — | un message de plus du bot de Glorfindel | le texte passe par `chat_text.py`, sans mention sauf le rôle configuré (SEC6), et **sans bouton** ; masqué avant d'être posté |
| **4. Le fournisseur du modèle** | Glorfindel reste aveugle au rouge : rien du rapport, du créneau ni de la demande n'entre dans le message au modèle | — | les trois zones du prompt inchangées ; le test de `test_dagorlad_blind.py`, étendu au créneau |
| **5. Les hôtes : Imladris** | — | un conteneur de plus, lancé par une unité de l'hôte sur un marqueur de la watch, qui lit Azure sous l'identité managée | **aucun droit ajouté** : aucune attribution nouvelle dans son Terraform (`infra/glorfindel-host/`) ; la watch n'a jamais le socket Docker ; les montages en lecture seule sauf `runs/bench/`. **Mais l'identité est celle qui écrit** (Response, Session Drain, le canal) : la lecture seule sur Azure ne tient que par le code, son test et son mutant : **risque accepté par Jonathan pour la v1 (Q8)**. À FS1d, la règle `DOCKER-USER` qui coupe IMDS vise aussi ce conteneur |
| **5. Les hôtes : Imladris, du conteneur à l'hôte** | — | **une frontière neuve** : un fichier qu'un conteneur écrit (le marqueur de la watch) déclenche, sur l'hôte, un `docker run` sous le groupe docker, qui vaut root | les bornes, chacune avec son mutant (§9) : le `run_id` est pris du **nom** du fichier, validé par le motif des `run_id` du cœur (`eregion_core/exercise.py`, `_SAFE_RUN_ID`, à exposer par `runs_layout` au lot), et passé en argv, **jamais par un shell** ; le **contenu** du marqueur n'est jamais lu comme argument ; l'image (celle qui est déployée), la commande et les montages sont fixés dans l'unité, rien ne vient du marqueur ; **une composition à la fois**, sous verrou (`flock`), avec un `RuntimeMaxSec`. Un marqueur forgé par la watch ne fait que composer, en lecture, le rapport d'un `run_id` valide |
| **5. Les hôtes : Orodruin** | — | une occurrence armée de plus | la frontière du minuteur proposée par DRL1 (§7 de `drill-banc.md` ; numérotée à son lot de code, puisque la 9 est désormais celle du téléphone) : le même lecteur, le même refus du destructif, la zone `bench`, le contrat, V1. En plus : l'horizon de 7 jours, un créneau à la fois, le registre à part, le permis jamais réécrit |
| **5. Les hôtes : Orodruin, le réveil** | un créneau joue sans qu'on ait allumé Orodruin à la main | l'identité de la Logic App de DRL1c reçoit **une lecture** : `Storage Blob Data Reader` sur le seul conteneur du canal | elle n'écrit rien, ne lit que ce que le canal publie déjà (sans identifiant ni cible), et ne peut qu'allumer Orodruin ; elle n'allume que sur un permis présent dont l'heure tombe dans l'heure qui vient ; le kill supprime le permis et la désactive ; l'armement n'écrit jamais dans la Logic App. Compromise, elle lit le canal et allume Orodruin, dont le minuteur ne joue qu'à son heure et sous ses gardes |
| **6. La CI et le CD** | — | rien de neuf | la PR de BNC6 passe la CI et la relecture, comme toute PR ; aucun workflow ne lit un rapport |
| **7. Les sessions d'agents** | le transcript d'une session voit le rapport masqué, et non plus les sorties brutes d'`az` | — | les sessions n'arment rien et ne lancent rien : `slot-arm`, `bench-run`, `bench-restore` refusent dans une session d'agent (`session_refusal`) ; `proofs.json` change par une PR relue |
| **8. La session Banc** | elle n'a besoin de rien de plus que le rapport | — | BRO1 n'est pas élargi |
| **9. Le téléphone** | — | rien : les deux gestes du T1486 restent tapés dans le terminal du poste | ce que MOB1 tient déjà, la réserve de `tmux` comprise. `bench-run` porte une écriture de plus, le point propre (Q3) : demandé par le SSH à clé d'hôte épinglée au conteneur de la console d'Imladris, sous son identité (Response), derrière le même garde de session et le même terminal |

**Par STRIDE, ce qui compte :**
- **S, lancer une attaque sans l'opérateur** : aucun chemin du dehors. Le destructif part du seul
  terminal du poste, nom tapé ; le créneau ne joue que du non destructif, armé par Jonathan, et le
  dehors ne peut que refuser.
- **T, un restore qui remet un disque chiffré** : `bench-run` vérifie que le point que le restore
  prendra est pris après le dernier restore et hors de toute quarantaine, et en prend un propre
  sinon (Q3).
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
- **D, l'humain absent** : l'état sûr du §3.2. Rien de pire qu'un incident réel contenu et laissé à
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
| **1** | **BNC3** (le poste) | Tests, Orodruin | le calme dans le préflight (gondolin démarrée depuis 10 min, aucun run sur elle depuis 10 min) : un ✗ qui dit les minutes qui restent, jamais une attente (Q6) ; le point propre dans `bench-run` (Q3) : le point que le restore prendra, vérifié (après le dernier restore, hors de toute quarantaine), sinon demandé par le chemin du bouton 📸 et attendu jusqu'à `Completed` avant l'attaque ; `bench-restore` qui suit la levée en lecture, 30 min au plus, puis compose le rapport ; la section « état du banc à la fin » et l'inventaire des disques dans le rapport, en lecture | un T1486 en deux gestes, et un rapport complet composé sans rien taper ; aucun ✓ sur un banc pas calme ; **deux runs enchaînés** : au second, le point le plus récent est celui pris pendant la quarantaine du premier, `bench-run` le refuse, en prend un propre, attend `Completed`, puis attaque, et le restore du second prend ce point |
| **2** | **BNC4** (Imladris) | Glorfindel, Console | la sous-commande de composition, en lecture seule, livrée dans l'image ; le marqueur de fin de run, écrit par la watch dans `runs/glorfindel/bench-pending/` (la levée, la carte « levée retenue », la carte du TTL) ; l'unité de l'hôte qui lance le `docker run --rm`, avec ses bornes ; la variable d'Orodruin (Q7) passée au seul conteneur de la composition, son mode contrôle, et le mode opératoire du §5.5 dans `infra/glorfindel-host/README.md` ; `runs/bench/` déclaré dans `runs_layout.WRITERS` et `test_runs_mounts.py` ; le fichier `runs/bench/<run_id>.json` ; le message du bot de Glorfindel dans le fil du drill, sans bouton | le rapport final posté sans personne au poste, masqué ; aucune attribution de rôle ajoutée à Imladris |
| **3** | **BNC5** (Orodruin) | Orodruin, Glorfindel | le créneau daté : `scheduled_drill run --slot`, son armement, son permis, son registre, l'horizon, un créneau à la fois ; les cibles `orodruin-slot-check`, `-arm`, `-disarm` ; ses unités ; le pas du kill ; `orodruin/slot.json` et son lecteur exact sur Imladris ; l'alarme d'absence « slot not run » | le créneau joue une fois à l'heure armée, refuse après, refuse un drill destructif, ne joue plus après un kill ; manqué et dit si Orodruin n'est pas allumé à l'heure |
| **3b** | **BNC5b** (Terraform) | Orodruin, Infra | le réveil (§2.7) : la récurrence horaire de la Logic App de DRL1c, sa lecture du permis, sa condition sur l'heure qui vient ; le rôle `Storage Blob Data Reader` de son identité à la portée du seul conteneur du canal ; la lecture de son état par `slot-arm`. Les gestes de Jonathan : `make orodruin-plan`, relu, puis `make orodruin-lock` | Orodruin éteint, un créneau armé est réveillé et joue à l'heure ; sans permis, rien ne s'allume ; après un kill, rien ne s'allume |
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
- un point d'avant le dernier restore de la VM est accepté ;
- l'attaque lancée avant que le point demandé soit `Completed` ;
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
`make orodruin-plan`, puis `make orodruin-lock`) et tout autre apply ; poser la variable d'Orodruin
sur Imladris, une fois BNC4 déployé (§5.5).

---

## 10. Les décisions de Jonathan, et les options écartées

### 10.1 Décisions de Jonathan (11/11)

Prises une à une, sur les huit questions de cette conception ; chacune suit l'option recommandée,
précisée pour Q3 et Q4.

| | Décision | Raison |
|---|---|---|
| **Q1. La fin du run, pour Imladris** | Au premier des trois événements : la levée vérifiée, la levée retenue, la carte du TTL. Le rapport dit lequel (« restored and lifted », « lift held », « contained, not restored ») (§3.2, §5.1) | Le run se ferme toujours, même sans réponse humaine |
| **Q2. Où le rapport est publié** | Dans le fil du banc, celui du drill de DRL1, un message par run, sans bouton ; le poste ne publie rien (§5.3) | Un seul fil du banc, déjà décidé pour les alertes du drill (décision 4 de DRL1) ; une seule voix |
| **Q3. Le point de restauration propre** | `bench-run` vérifie qu'un point propre existe, pris après le dernier restore de la VM et hors de toute quarantaine ; sinon il en demande un par le chemin du bouton 📸 (la console d'Imladris), attend qu'il soit terminé, puis lance l'attaque (§3, étape 4) | Quand les runs s'enchaînent, « le plus récent avant T0 » peut être un point pris pendant la quarantaine du run précédent, donc chiffré |
| **Q4. Le réveil d'Orodruin** | Un réveil qui lit le créneau : la Logic App, déclarée une fois dans Terraform, regarde chaque heure dans le canal si un créneau est armé pour l'heure qui vient, et allume Orodruin. L'armement n'écrit qu'une donnée ; la Logic App reçoit une lecture sur ce seul conteneur du canal (§2.7) | Un créneau qui ne joue que si quelqu'un a allumé Orodruin n'en est pas un ; l'armement ne touche pas l'infrastructure |
| **Q5. Combien de créneaux** | Un créneau à la fois en v1 ; pour en poser un autre, désarmer le précédent, joué ou non (§2.3) | Un seul état à juger ; sous la rétention du canal, le permis n'a jamais à être réécrit |
| **Q6. Le calme** | Un ✗ du préflight, jamais une attente : `bench-run` refuse, dit les minutes qui restent, l'opérateur relance (§3, étape 3) | Une commande qui attaque ne garde pas la main en attendant |
| **Q7. Le rôle d'Orodruin dans le rapport d'Imladris** | Une variable non secrète sur Imladris, l'identifiant du principal d'Orodruin, pour nommer et masquer seulement ; « inconnu » ne désigne plus qu'un vrai inconnu. Le mode opératoire complet est au §5.5 | L'attaquant du run se nomme dans son propre rapport, sans droit ajouté |
| **Q8. L'identité de la composition sur Imladris** | Le risque accepté et dit pour la v1 : l'identité de la VM, la lecture seule tenue par le code, son test et son mutant, écrit au §8. Au moment de FS1d, la règle `DOCKER-USER` qui coupe IMDS vise aussi le conteneur de la composition, qui lit alors par le principal lecteur de la console (§5.2) | La décision 3 : aucune identité nouvelle. FS1 ferme le risque à son heure |

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
| Q3 : **aucun point pris par le run**, le restore prenant le plus récent avant T0 | Quand les runs s'enchaînent, ce point peut être pris pendant la quarantaine du run précédent : le restore remettrait un disque chiffré |
| Q4 : **aucun réveil**, le créneau ne jouant que si Orodruin est déjà allumé | Le créneau manquerait chaque fois qu'Orodruin est éteint, c'est-à-dire presque toujours |
| Q4 : **l'armement qui écrit une occurrence dans la Logic App** | Un écart avec l'état de Terraform, et un armement qui touche l'infrastructure |
| Q4 : **une seconde Logic App**, réservée aux créneaux | Une ressource et une identité de plus, pour ce que la première fait par une récurrence |
| Q5 : **plusieurs créneaux, ou un horizon plus long** | Plusieurs états à juger ; au-delà de la rétention du canal, Orodruin devrait réécrire le permis, une écriture de plus et son mutant |
| Q6 : **`bench-run` qui attend lui-même les minutes qui restent** | Une commande qui attaque garderait la main en attendant |
| Q7 : **aucune variable**, Orodruin dit « inconnu » | L'attaquant du run serait inconnu dans son propre rapport, et « inconnu » ne distinguerait plus un vrai inconnu |
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
