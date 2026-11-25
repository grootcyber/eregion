# La mémoire des décisions, mesurée : la distance contre la date (MEM1, #1016) — conception

_Conception — 21/11 (MEM1, #1016) — statut : **mesure faite, (a) choisie le 21/11, MEM3 fait le 22/11,
MEM2 écrit le 23/11 derrière un interrupteur éteint (§8), MEM-H écrit le 24/11 (§9), sa séance tenue
par Jonathan le 24/11 (§9.3)** : le code de la mémoire par clés est là, la production garde la mémoire par distance tant
qu'ENQ5 ne l'allume pas. Suite de la dixième passe de
revue (20/11, P10-6). Les §1 à §7 décrivent le code au commit `78482cc7`, avant MEM2 ; chacune des
options qui changent les précédents rendus au modèle attend son run de bout en bout (§4)._

**Lié** : [`docs/glorfindel.md`](../glorfindel.md) (la mémoire : la source d'un cycle, B2 ; son âge,
SEC17 ; la VM et la règle, SEC-I) ; [`preuves.md`](preuves.md) (les couches de preuve) ;
[`dossier-isolation.md`](dossier-isolation.md) (le modèle de cette note) ;
[`docs/analysis.md`](../analysis.md) (l'index de l'IA d'analyse, l'autre utilisateur de ChromaDB).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne, au
commit `78482cc7`. Les chiffres viennent d'un seul rejeu, sur une copie du magasin
d'Imladris (anciennement H0) tirée le 21/11 à 12:15 UTC (les données du banc). Ils sont agrégés : aucun
nom de VM, aucun identifiant ni texte de cycle n'est sorti de la copie, et rien d'elle n'entre dans le
dépôt. Le reste est une hypothèse, et le texte le dit.

---

## 0. En bref

- **La requête n'est qu'un gabarit.** La mémoire cherche ses précédents par le texte « TTP, gravité,
  type, événement, fournisseur ». La ligne détectée n'y entre jamais. Rejoués, les 479 signaux de la
  copie ne donnent que **6 textes de requête distincts**. Pour un même gabarit et une même mémoire, à
  règle et VM égales, la distance rend donc les mêmes précédents, quoi que dise la détection.
- **Sur l'ensemble, la distance ne fait pas mieux que la date.** Avec le classement du code (même règle, puis même VM,
  au plus un précédent par VM, trois places), la distance et la date ne rendent le même ensemble que
  **21 fois sur 479**, avec un Jaccard moyen de 0,062. Part des précédents qui portent la technique du
  signal : **77,3 % par la distance, 80,2 % par la date seule, 92,9 % par la technique puis la date**.
- **Ce qui apporte, c'est une clé.** Ajouter le TTP aux clés de rang donne 92,9 %, que la dernière clé
  soit la date ou la distance. Une fois le TTP en tête, la distance n'apporte rien de mesurable que la
  date n'apporte pas. Elle garde son coût : ChromaDB, un modèle d'embedding de 80 Mo, quatre avis de
  sécurité acceptés, un écrivain natif hors de la garde HY2b, plus d'une seconde par décision à 3 000
  cycles (§1.4).
- **Quatre options** (§4) : (a) une table par clés et par date, chromadb sorti des dépendances ; (b)
  Chroma gardé, le TTP ajouté aux clés ; (c) un vrai corpus où le sens compte, pour l'enquête, à part ;
  (d) mesurer d'abord au harnais si les précédents changent les décisions.
- **La recommandation** (§5) : (a), le TTP dans les clés, prouvé par (d) et par le run de bout en bout
  de Jonathan avant la fusion ; l'index de l'IA d'analyse ensuite, puis chromadb hors des dépendances ;
  (c) plus tard, avec l'enquête si elle se fait.

---

## 1. Ce que fait la mémoire aujourd'hui, lu dans le code

### 1.1 Ce qui est rangé

- **Un cycle par décision du plan de données**, en fin de cycle (`store_cycle`, `glorfindel/agent.py:2766`).
  Jamais un cycle du plan de contrôle ni d'identité (`agent.py:2809-2811`).
- **Son texte** (`_cycle_to_text`, `glorfindel/memory.py:292-301`) : TTP, gravité, type, événement,
  action, les 200 premiers caractères du raisonnement du modèle, le résultat. C'est ce texte que Chroma
  embarque (`memory.py:78`), et ce que le modèle relira (§1.3).
- **Ses métadonnées** (`memory.py:82-109`) : la source `real` ou `exercise` (B2), la date de rangement
  par l'horloge de l'hôte (`stored_at`, SEC17, `memory.py:99`), la VM en minuscules et la règle (SEC-I,
  `memory.py:106-107`). Jamais montrées au modèle.
- **Son identifiant** est tiré au rangement (`memory.py:77`) : un cycle s'ajoute, jamais ne s'écrase.
- **Le magasin** : `~/.glorfindel/cycles`, un `PersistentClient` de Chroma, une collection `cycles` en
  distance cosinus (`memory.py:11`, `memory.py:66-70`). `store_guard.check` le refuse avant de l'ouvrir
  dans une session d'agent (`memory.py:64`).

### 1.2 Ce qui est cherché

`retrieve_similar` (`memory.py:120-190`), appelé par `load_context` avec `n=3` (`agent.py:295`) :

- **La requête** est le gabarit `_signal_to_text` (`memory.py:282-289`) : `TTP`, `severity`,
  `resource_type`, `event`, `provider`. Ni la ligne détectée, ni l'enquête, ni la VM n'y entrent.
- **Le filtre** : des cycles réels seulement, rangés dans la borne d'âge (90 jours par défaut), plus
  ceux d'avant SEC17, datés par le plancher B2 tant qu'il est dans la borne (`memory.py:202`,
  `memory.py:205-213`).
- **Le pool** : trois recherches par similarité, une sans filtre, une par la VM, une par la règle,
  chacune de `n * _DUPLICATE_SLACK` = 12 cycles au plus (`memory.py:14`, `memory.py:152`,
  `memory.py:162-166`), puis au-delà des VM à leur borne (`memory.py:188`).
- **Le rang** (`memory.py:168-171`) : la même règle d'abord, puis la même VM, puis la distance.
- **Les bornes** (`memory.py:174-189`) : un cycle par `(signal_id, action, run_id)` ; au plus
  `PER_VM = 1` précédent par VM (`memory.py:33`). Les cycles sans VM comptent pour une seule VM,
  inconnue.

### 1.3 Ce que voit le modèle

- `decide` passe les précédents à `_build_user_message` (`agent.py:2060-2061`). Le message les rend
  sous « Cycles passés similaires », chacun avec son étiquette de source et son texte rangé
  (`agent.py:3742-3748`, `_SOURCE_TAGS`, `agent.py:3644`). Sans précédent, le message dit « Aucun
  cycle passé disponible — première décision ».
- Le prompt système dit que ce sont des faits passés, jamais l'état présent, et qu'ils servent à
  « calibrer la confiance et le raisonnement » (`agent.py:218-225`).
- Les métadonnées (la VM, la règle, la date) ne sont jamais dans le message : changer la façon de
  choisir les précédents ne change pas le format du message, mais change les cycles qu'il contient.

### 1.4 Ce que coûte ChromaDB

- **Une dépendance** (`pyproject.toml:68`, `chromadb>=0.5`, 1.5.9 verrouillée) qui porte quatre des cinq
  avis acceptés de `requirements/audit-accepted.json`. Le cinquième, `opentelemetry-api`, vient aussi
  d'anthropic et de fastapi : il resterait.
- **Un modèle d'embedding** (all-MiniLM-L6-v2, environ 80 Mo), tiré d'un seau S3 au premier usage et
  vérifié par son SHA-256. La CI le tire avant les tests (CI8, `scripts/chroma_model.py`, dix étapes
  dans cinq workflows), sous un verrou de fichier (FLK1). Le HOME jetable de la suite le garde par un
  lien (`tests/unit/home_sandbox.py`). Imladris et les conteneurs montent `~/.cache/chroma`
  (`docker-compose.yml`, `infra/glorfindel-host/main.tf:194`).
- **Un écrivain natif** : Chroma 1.x écrit son magasin depuis Rust, que le crochet d'audit de HY2b ne
  voit pas. Seul `store_guard.check` refuse l'ouverture (`eregion_core/store_guard.py:38-41`).
- **Du temps** : mesuré à la relecture de SEC-I, en local, 1,1 à 1,4 s par décision pour 3 050 cycles
  et 50 VM, contre environ 0,26 s avant (`docs/glorfindel.md`, « La mémoire pèse la VM et la règle »).
- **Un second usage, sans similarité** : l'index de l'IA d'analyse (`analysis/campaign_report.py:590-598`,
  la collection `campaign_runs`) ne se lit que par des filtres de métadonnées (`get(where=…)`,
  `campaign_report.py:660` et `:699` ; `get(ids=…)`, `analysis/campaign_index.py:95`). Il n'appelle jamais
  une recherche par similarité. Il embarque ses documents pour rien. *(Au commit `78482cc7` ; depuis
  MEM3, 22/11, une table SQLite, §7, Q5.)*

---

## 2. La mesure

### 2.1 La copie et le rejeu

- **La copie** : celle que tire `make imladris-pull` (le tar de `~/.glorfindel` d'Imladris), extraite dans
  un dossier à part. Le script refuse le magasin de l'opérateur, sous le HOME comme sous le home que le
  système lui donne, une copie dont un fichier ou un dossier y mène par un lien, et tout dossier qui
  n'est pas un magasin (l'en-tête de `scripts/memory_replay.py`).
- **Hors ligne** : le client embarqué de Chroma, télémétrie coupée (`ANONYMIZED_TELEMETRY=False`,
  `Settings(anonymized_telemetry=False)`), `HF_HUB_OFFLINE=1`. Le modèle ONNX de Chroma est lu sur le
  disque, et le script refuse s'il manque : il ne le tire jamais. Ni le cloud, ni le modèle de langage.
- **Le rejeu** : les cycles dans l'ordre de leur rangement. Chaque cycle réel devient un signal, face
  aux cycles réels rangés avant lui, dans la borne de 90 jours. Le signal est celui du cycle : sa
  technique, sa gravité, son type, son événement, sa règle, sa VM, et le fournisseur « azure ».
- **Quatre classements**, chacun avec les bornes du code (la même règle, puis la même VM, puis la
  dernière clé ; un cycle par clé de copie ; un par VM ; trois places) : `distance` (le code),
  `date` (le plus récent d'abord), `ttp_then_date` et `ttp_then_distance` (la technique du signal
  d'abord, puis la date ou la distance).
- **Rejouer la mesure** sur une copie plus récente :
  ```
  d=$(mktemp -d) && tar xzf ~/.eregion/host-backups/glorfindel-<date>.tgz -C "$d" .glorfindel/cycles
  python scripts/memory_replay.py "$d/.glorfindel/cycles"
  ```
  Le script n'imprime qu'un objet JSON de chiffres agrégés. Un nom de règle n'en sort que s'il est
  celui d'une règle livrée, une technique que si elle a la forme d'un identifiant ATT&CK.

### 2.2 Le magasin (copie du 21/11, 12:15 UTC)

| | |
|---|---|
| Cycles | 500 : 480 réels, 19 d'exercice, 1 sans source |
| Réels sans date, datés au plancher B2 (16/10) | 103 |
| Étendue des cycles réels | 35,7 jours |
| Réels sans règle ni VM (rangés avant SEC-I) | 449 |
| Clés de VM | 3 : deux VM nommées, et la VM inconnue |
| Règles (cycles réels) | aucune 449, `data-exfiltration-blob` 29, `ssh-brute-force` 1, `sudo-privilege-escalation` 1 |
| Techniques (cycles réels) | T1041 310, T1110.001 105, T1548.003 61, T1486 2, T1136.001 1, aucune 1 |

### 2.3 Les résultats

479 signaux ont au moins un précédent (tous sauf le premier). Ils ne donnent que 6 textes de requête
distincts.

| Comparaison | Même ensemble | Même premier précédent | Jaccard moyen |
|---|---|---|---|
| distance (le code) / date | 21 sur 479 | 21 | 0,062 |
| distance / TTP puis date (option a) | 21 sur 479 | 21 | 0,062 |
| distance / TTP puis distance (option b) | 399 sur 479 | 399 | 0,834 |
| TTP puis date / TTP puis distance | 25 sur 479 | 25 | 0,070 |

| Classement | Part des précédents qui portent la technique du signal | Précédents par signal |
|---|---|---|
| distance (le code) | **77,3 %** | 1,065 |
| date | **80,2 %** | 1,065 |
| TTP puis date | **92,9 %** | 1,065 |
| TTP puis distance | **92,9 %** | 1,065 |

- La première place se joue sur la dernière clé (la distance ou la date) pour **477 signaux sur 479** :
  la classe la meilleure (même règle, même VM) en tient plus d'un, puisque presque aucun cycle n'a ni
  règle ni VM.
- 474 signaux sur 479 avaient en mémoire au moins un cycle de leur technique.
- **Un précédent par signal en moyenne** : les 449 cycles sans VM comptent pour une seule VM, qui ne
  prend qu'une place (`PER_VM = 1`). Les deux VM nommées n'ont de cycles que depuis SEC-I. Sur cette
  copie, un signal nouveau en recevrait au plus trois : un de la VM inconnue, un de chacune des deux VM
  nommées.

### 2.4 Par technique du signal

| Technique (cycles réels) | distance | date | TTP puis date | TTP puis distance |
|---|---|---|---|---|
| T1041 (310) | 87,1 % | 89,4 % | 90,9 % | 90,9 % |
| T1110.001 (105) | 94,2 % | 81,7 % | 100 % | 100 % |
| T1548.003 (61) | **0 %** | 30,6 % | 96,8 % | 96,8 % |
| T1486 (2) | 0 % | 50 % | 50 % | 50 % |
| T1136.001 (1) | 0 % | 0 % | 0 % | 0 % |
| aucune (1) | 0 % | 0 % | 0 % | 0 % |

La distance n'est pas toujours la pire : pour T1110.001, elle fait mieux que la date. Mais pour les
signaux d'élévation par sudo (T1548.003, 61 cycles), elle ne rend **jamais** un précédent de la même
technique. La date en rend 30,6 %, une clé TTP 96,8 %. Le cycle T1136.001 est le seul de sa technique,
et le cycle sans technique le seul sans : aucun classement ne peut leur en rendre un.

### 2.5 Ce que la mesure ne dit pas

- **Un magasin de banc**, un seul. 449 cycles sur 480 datent d'avant SEC-I : sans règle ni VM, ils
  rangent toute la mémoire dans une seule classe. Sur une mémoire où chaque cycle porte sa règle et sa
  VM, la règle et la VM décideraient plus souvent, et la dernière clé moins souvent.
- **Le code d'aujourd'hui sur des signaux d'hier.** Le rejeu applique le classement actuel (SEC-I, SEC17)
  à des signaux décidés avant lui. Il compare des classements. Il ne dit pas ce que le modèle a vu le
  jour de la décision.
- **Le fournisseur est supposé « azure »** dans la requête. C'est ce qu'écrit le RulePoller
  (`glorfindel/detection_rules.py:2352`), mais le cycle ne garde pas ce champ.
- **Le pool de Chroma est remplacé par l'ensemble des cycles éligibles**, et la recherche approchée HNSW
  par la distance exacte (cosinus, sur les embeddings rangés). Le code lit au plus 12 cycles par
  recherche (§1.2) : la mesure donne à la distance plus de choix que le code ne lui en laisse.
- **L'ordre des cycles sans date entre eux** est celui du magasin : ils ont tous la même date, le
  plancher B2.
- **La même technique est un indice, pas la pertinence.** Un précédent d'une autre technique dit peu au
  modèle sur celle-ci. Un précédent de la même technique n'est pas pour autant le bon. La mesure ne dit
  pas, entre deux cycles de la même technique, si le plus récent vaut mieux que le plus proche en texte.
  Elle dit seulement qu'ils diffèrent (25 fois le même ensemble sur 479).
- **Rien sur les décisions.** La mesure ne dit pas si les précédents changent ce que décide le modèle.
  C'est l'option (d).

**La mesure précédente**, sur un corpus synthétique tiré du harnais (20/11, fiche de #1016), allait dans
le même sens : l'embedding ne regroupait même pas par technique, avec 0 voisin T1486 sur 9 pour une
requête T1486.

---

## 3. Ce que ça veut dire

- **Le « similaire » n'est que le gabarit.** Six textes de requête pour 479 signaux : la distance range la
  mémoire selon la ressemblance de chaque cycle rangé (son raisonnement, son résultat) à l'un de six
  textes fixes. Elle ne dit rien de l'incident en cours. Deux brute force de même gravité sur la même VM,
  l'un de 10 tentatives et l'autre de 10 000, reçoivent les mêmes précédents face à la même mémoire.
- **Sur ces données, l'embedding n'apporte rien.** Sans clé de technique, il fait moins bien que la date
  (77,3 % contre 80,2 %). Avec la clé, la date et la distance font jeu égal (92,9 %).
- **Une clé fait mieux.** La règle, la VM, puis la technique : 92,9 %, contre 77,3 % aujourd'hui. La date
  comme dernière clé a un sens qu'on peut dire à un humain : « la dernière décision de cette règle sur
  cette VM, puis la dernière de cette technique ailleurs ». La distance n'en a pas.
- **Ce que la mesure ne tranche pas** : la date ou la distance une fois la technique en tête. Elles
  donnent la même part, mais d'autres cycles. Le choix (a) contre (b) se fait donc sur le reste, le coût
  de Chroma (§1.4) contre la taille du changement de ce que voit le modèle (§4).

---

## 4. Les options

Toutes gardent le format du message : `_build_user_message()`, `_SYSTEM_PROMPT` et
`few_shot_examples.yaml` ne changent pas. Mais **chaque option qui change les précédents rendus change
ce que voit le modèle**, et attend le run de bout en bout de Jonathan (T1486 et une autre technique)
avant la fusion. SEC-I, SEC4a et SEC17 avaient été notés de même : à rejouer de bout en bout.

### (a) Une table par clés et par date, chromadb sorti des dépendances

- **Ce qui change** : `glorfindel/memory.py` range les mêmes cycles (le même texte, les mêmes
  métadonnées) dans une table. Deux supports possibles : SQLite (la bibliothèque standard, un fichier
  sous `~/.glorfindel/`, des index sur la règle, la VM, la technique et la date), ou un JSONL sous
  verrou, comme les escalades. La recherche filtre et trie : la même règle, la même VM, la même
  technique, puis la plus récente. Les bornes restent : cycles réels, âge, un par VM, copies repliées.
- **Ce que voit le modèle** : le même message, d'autres cycles. Mesuré, l'ensemble rendu change pour
  **458 signaux sur 479** (§2.3), et la part de la même technique passe de 77,3 % à 92,9 %.
- **Ce que ça retire** : les quatre avis acceptés de chromadb (celui d'`opentelemetry-api` reste,
  §1.4) ; le modèle d'embedding, son tirage en CI (CI8), son verrou (FLK1), son lien dans le HOME
  jetable, ses montages ; l'écrivain natif hors de la garde. `sqlite3.connect` est un des événements que
  le crochet d'audit de HY2b voit (`store_guard.py:86`). Une recherche devient une lecture par index,
  sans embedding de la requête (son temps reste à mesurer, dans le lot).
- **Ce que ça demande** : `make lock` (une dépendance retirée change le verrou), donc le harnais de
  Jonathan (`make llm-compare`) avant de redéployer Imladris (`CLAUDE.md`, « Dépendances
  verrouillées ») ; l'index de l'IA d'analyse sur la même table d'abord, sinon chromadb reste (§1.4) ;
  les workflows qui tirent le modèle, que seul Jonathan modifie (l'App des sessions n'a pas le droit
  *Workflows*, `docs/sessions.md`, SEC12) ; le sort des cycles déjà rangés sur Imladris (Q3).
- **Le modèle de menace.** Chez sa VM, rien ne change : un compte local qui provoque des détections
  sur sa VM tient le cycle le plus récent de cette VM, comme il tient aujourd'hui sa classe « même VM »,
  qui passe avant la distance. **Chez les autres VM, la date le sert** : des détections récentes,
  provoquées à volonté, donnent à sa VM une place certaine parmi les précédents des signaux de même
  règle ou de même technique, sur toute autre VM. Sous la distance, cette place dépend de la ressemblance
  de son cycle au gabarit. Dans les deux cas, il n'en tient qu'une (la borne d'un précédent par VM), mais
  sous (a) il sait qu'il l'a, avec les 200 caractères d'un raisonnement écrit sur ses lignes. Un filtre
  sur la corroboration (SEC-A3) la bornerait ; il reste à décider avec SEC-A3, comme sous la distance.

### (b) Chroma gardé, le TTP ajouté aux clés de rang

- **Ce qui change** : le rang devient la règle, la VM, la technique, puis la distance. Il faut une
  quatrième recherche, par la technique (`where ttp`), pour que le pool borné de Chroma tienne des
  cycles de la technique du signal.
- **Ce que voit le modèle** : le même message, d'autres cycles pour **80 signaux sur 479** (16,7 %),
  le plus petit changement. La part de la même technique passe aussi à 92,9 %.
- **Ce que ça garde** : tous les coûts du §1.4, et une distance qui ne lit toujours que le gabarit.
- **Ce que ça demande** : le run de bout en bout ; aucune dépendance ne bouge.

### (c) Un vrai corpus où le sens compte, pour l'enquête

- **Ce qui change** : rien pour les précédents. Ce serait un corpus à part, où une recherche par le
  sens a quelque chose à trouver : les fiches ATT&CK des techniques couvertes, le schéma des tables de
  Log Analytics, les dossiers d'isolation (DOS1). Il servirait l'enquête, si elle devient un vrai
  graphe où le modèle choisit sa requête suivante (dixième passe, P10-5 ; ENQ1, si le lot se fait).
- **Ce que voit le modèle** : rien tant que l'enquête ne le lui montre pas. Ce jour-là, c'est un lot à
  part, avec sa mesure et son run de bout en bout.
- **Ce que ça demande** : garder un moteur d'embedding (Chroma ou autre), pour un usage où le texte de
  la requête porte enfin du sens, c'est-à-dire la question de l'enquête et pas un gabarit.

### (d) Mesurer d'abord au harnais si les précédents changent les décisions

- **Ce qui change** : rien en production. Le harnais (`scripts/llm_smoke.py`, `make llm-compare`) gagne
  un genre de cas qui rejoue les mêmes signaux avec trois mémoires : aucun précédent, ceux de la
  distance, ceux des clés. Il compte les décisions et les confiances qui bougent.
- **Pourquoi** : B2 a montré qu'une mémoire piégée ou remplie d'exercices ne fait pas basculer une
  décision (`--kinds memory`, ROADMAP, B2). Il n'a pas montré qu'une bonne mémoire les améliore. Si les
  précédents ne changent rien, la question devient : faut-il encore les montrer au modèle ?
- **Ce que ça demande** : des appels payants au modèle, lancés par Jonathan.

---

## 5. La recommandation

**(a), le TTP dans les clés, prouvé par (d) et par le run de bout en bout, avant la fusion.**

- Sur la pertinence mesurée, (a) et (b) font jeu égal (92,9 %). La distance n'apporte rien que la date
  n'apporte, et la date se dit à l'humain.
- (a) retire tout ce que Chroma coûte (§1.4), alors que (b) le garde pour une distance qui ne lit que
  six gabarits.
- (a) change plus de précédents que (b) (458 contre 80 sur 479). Mais les deux attendent le même run de
  bout en bout, et (d) mesure justement si ce changement compte : sans précédent, ceux de la distance,
  ceux des clés, sur les mêmes cas.
- L'index de l'IA d'analyse suit, dans un lot à part. Il ne lit déjà que par clés : son passage ne change
  aucune des lignes qu'il rend, si leur ordre est gardé. Ensuite, chromadb sort des dépendances.
- (c) attend l'enquête. Un corpus où le sens compte n'a d'objet que si une requête en porte.

Si Jonathan préfère le plus petit changement de ce que voit le modèle, (b) prend le même gain mesuré,
en un lot plus petit, et garde Chroma.

---

## 6. Les lots qui suivraient

Dans l'ordre, si Q1 = (a). Les mutants sont estimés ; l'Orchestre donne les plages.

| Lot | Session | Contenu | Ce qu'il prouve | Taille | Mutants |
|---|---|---|---|---|---|
| **MEM2** — les précédents par clés et par date — **écrit le 23/11 (#1027), derrière un interrupteur éteint (§8)** | Glorfindel | `glorfindel/memory.py` sur SQLite (Q2), la même interface (`store`, `retrieve_similar`, `age_census`, `count`) ; le rang : règle, VM, technique, date ; les bornes gardées ; `glorfindel memory-stats` ; les tests de la mémoire portés (`test_memory_age.py`, `test_enquiry_memory.py`, `test_agent_nodes.py`) ; l'import des cycles d'une copie (Q3) ; `scripts/memory_replay.py` gagne le classement du lot | le message au modèle identique au format près (un test le fige) ; le rejeu sur la copie d'Imladris ; **le run de bout en bout de Jonathan** | M | **6** : le TTP hors des clés ; la distance ou un ordre ancien au lieu du plus récent ; la borne par VM ; l'âge ; un exercice rendu ; une copie non repliée |
| **MEM-H** — le harnais des précédents (d) — **écrit le 24/11 (#1028), §9** | Glorfindel | un genre `precedents` dans `scripts/llm_smoke.py` : les mêmes cas, trois mémoires (aucune, distance, clés), les décisions et les confiances qui bougent, au rapport de `make llm-compare` | **les runs payants de Jonathan**, avant la fusion de MEM2 | S | **2** : une mémoire du cas qui fuit dans une autre ; l'écart non compté |
| **MEM3** — l'index de l'IA d'analyse sur la même table — **fait le 22/11 (#1029)** : SQLite, l'import de l'ancien index, `docs/analysis.md` | Analyse | `analysis/campaign_report.py` (`_collection`, `index_facts`, `prior_runs`, `previous_campaign`), `analysis/campaign_index.py`, `analysis/separation.py` (IA1 : jamais la mémoire de Glorfindel) ; les lignes rendues et leur ordre gardés (un test, sur un index d'avant) | les rapports de campagne identiques sur le jeu d'exemple | S–M | **3** : l'ordre des lignes ; la séparation d'IA1 ; une ligne illisible lue vide |
| **MEM4** — chromadb hors des dépendances | Glorfindel, gestes de Jonathan | `pyproject.toml`, `make lock`, les quatre avis retirés de `requirements/audit-accepted.json` ; `scripts/chroma_model.py`, FLK1 et le lien du HOME jetable retirés ; les montages de `~/.cache/chroma` (`docker-compose.yml`, `Makefile`, `infra/glorfindel-host/main.tf`), `scripts/doctor.py`, `scripts/image_check.py` ; les mutants qui visent Chroma (lots CI8, FLK1, CI6b, CI10b, HY2b, HY2c, SEC-K) retirés ou reportés. **Les workflows, par Jonathan** | **le harnais de Jonathan** (verrou changé) avant de redéployer Imladris | M | **1–2** : une trace de chromadb dans l'image ; un montage oublié |
| **MEM2b** — le précédent porte le verdict humain — **écrit le 24/11 (#1161), §9.5**, après le passage 1 de MEM-H (EH12 non tenue, §9.3). Il remplace l'ancienne ligne « MEM2b si Q1 = (b) », non retenue ((a) choisie le 21/11) | Glorfindel | le verdict de la carte de chaque cycle dit dans le précédent (ou « non jugé »), le rang qui préfère un jugé à clés égales ; la mémoire par clés qui ne s'ouvre pas retombe sur la distance, dite fort (bannière, carte) ; les suites de la relecture de MEM2 ; le harnais aux verdicts | éteint, le message à l'octet (le test sha256) ; **le passage 1 rejoué par Jonathan** ; puis le run de bout en bout d'ENQ5b | S–M | **10** (M7433–M7442) : le verdict tu ; « non jugé » tu ; le verdict hors du rang ; le verdict avant les clés ; « incertain » préféré ; la lecture retournée ; pas de repli ; le repli en silence ; `--to` qui n'est pas une base ; le harnais sans verdicts |

(c) n'a pas de lot ici. Il se rouvre avec l'enquête.

---

## 7. Les questions à Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est
décidé à sa place.

**Q1 — Quelle mémoire pour les précédents ?** (§4, §5)
1. **(a) Une table par clés et par date (la règle, la VM, la technique, puis la plus récente), chromadb
   sorti ensuite (recommandée).** Le même gain mesuré que (b), et tout ce que coûte Chroma retiré ; une
   règle de choix qu'on peut dire à un humain. Le prix : un compte local qui provoque des détections
   récentes est sûr d'avoir la place de sa VM chez les autres VM de même technique (§4, a).
2. (b) Chroma gardé, le TTP ajouté aux clés de rang. Le plus petit changement de ce que voit le modèle
   (80 signaux sur 479), le même gain mesuré, tous les coûts de Chroma gardés.
3. Rien ne change : la mesure est notée, la mémoire reste telle quelle.

**Q2 — Si (a) : sur quel support ?**
1. **SQLite, un fichier sous `~/.glorfindel/` (recommandée).** La bibliothèque standard, des index sur
   les clés et la date, une seule écriture par cycle, une ouverture que la garde HY2b voit.
2. Un JSONL sous verrou, comme les escalades. Aucun format nouveau, mais il est lu en entier à chaque
   décision, et il grossit sans index.

**Q3 — Si (a) : que deviennent les cycles déjà rangés sur Imladris ?**
1. **Importés une fois, hors ligne, depuis une copie (recommandée).** La mémoire reste continue, et le
   run de bout en bout compare la même mémoire classée autrement. L'import lit la copie comme le fait
   `scripts/memory_replay.py`. La pousser sur Imladris est un geste de Jonathan.
2. Repartir vide. C'est plus simple. Au débit du banc (480 cycles réels en 36 jours, environ 13 par
   jour), des précédents reviennent dès le premier jour ; trois seulement quand trois VM ont des cycles,
   puisqu'une VM n'en donne qu'un. Mais les premières décisions n'ont aucun précédent, et ce
   changement-là aussi se voit dans le message.

**Q4 — Quand mesurer au harnais si les précédents changent les décisions (d) ?**
1. **Avec MEM2, comme sa preuve, avant la fusion (recommandée).** Trois mémoires sur les mêmes cas :
   aucune, la distance, les clés. Le lot et sa mesure arrivent ensemble.
2. D'abord, avant d'écrire MEM2. Si les précédents ne changent rien, la question devient de les retirer
   du message, ce qui est un autre lot, avec un autre run.
3. Jamais : le run de bout en bout suffit.

**Q5 — Si (a) : l'index de l'IA d'analyse ?**
1. **Sur la même forme de table, dans un lot à part (MEM3), puis chromadb sort (recommandée).** L'index
   ne lit déjà que par clés ; sans ce passage, chromadb et tous ses coûts restent.
2. Chroma reste pour l'index seul. MEM2 se fait, mais l'image garde chromadb, son modèle et ses avis.

*Tranchée le 21/11 : 1. **MEM3 fait le 22/11** (#1029, `docs/analysis.md`, « L'index sur une table ») :
la table `campaign_runs` en SQLite (`analysis/run_index.py`), les lignes et leur ordre gardés (mesuré
contre chromadb sur un index d'avant importé), l'import de l'ancien index une fois
(`analysis/index_import.py`, un geste de Jonathan sur Imladris), et `analysis/` n'importe plus
chromadb que pour cet import. chromadb reste dans les dépendances jusqu'à MEM4, qui doit venir après
l'import sur Imladris : la commande d'import en a besoin.*

**Q6 — Un corpus où le sens compte (c) ?**
1. **Pas maintenant : il se rouvre avec l'enquête, si elle devient un vrai graphe, à part des précédents
   et avec sa propre mesure (recommandée).** Un corpus n'a d'objet que si une requête porte du sens.
2. Le préparer dès maintenant (fiches ATT&CK, schémas des tables, dossiers d'isolation), sans lecteur
   pour l'instant.

---

## 8. MEM2 : la mémoire par clés, derrière un interrupteur éteint (23/11)

**La décision de Jonathan du 23/11** : MEM2 est fusionné derrière un interrupteur éteint par défaut.
La production garde la mémoire d'aujourd'hui, à l'octet ; MEM-H compare les trois mémoires (aucune, la
distance, les clés) à la séance de harnais ; l'interrupteur ne s'allume qu'avec ENQ5, après la séance et
le run de bout en bout. Q4 (« mesurer avant de fusionner ») est ainsi tenue dans l'esprit : on mesure
avant d'allumer.

### 8.1 L'interrupteur

- **`GLORFINDEL_MEMORY`**, une variable d'environnement, lue à l'ouverture de la mémoire
  (`CycleMemory`, `glorfindel/memory.py`). Vide, absente ou `distance` : la mémoire par distance
  (`DistanceMemory`, ChromaDB, `~/.glorfindel/cycles`), celle de §1, inchangée. `cles` : la mémoire par
  clés (`glorfindel/memory_keys.py`). Les espaces autour sont ôtés ; rien d'autre n'est deviné.
- **Une valeur inconnue** (`clés`, `CLES`, `keys`, `1`…) garde la mémoire par distance, et le dit une
  fois sur stderr, dans les journaux de la watch : jamais aucune mémoire, jamais la watch à terre.
- **Pourquoi une variable, pas une clé de la configuration** : la configuration est lue strictement
  (A3) — une valeur inconnue y refuse tout le fichier, et la watch décide alors chaque VM en
  `human_only` ; un interrupteur illisible ferait donc plus que garder la mémoire d'aujourd'hui. Et la
  console réécrit `glorfindel-config.yaml` (le mode d'un asset) : l'interrupteur serait à sa portée.
  La variable est à l'opérateur seul, posée là où la watch démarre (`host.env` sur Imladris), et
  donnée à la watch seule (`docker-compose.yml`) ; la console et le bot ne la voient pas.
- **Ce qui est dit** : `glorfindel memory-stats` dit quelle mémoire l'interrupteur ouvre, et où ; la
  watch dit la mémoire par clés à son démarrage quand elle est allumée, et rien quand elle est éteinte.

### 8.2 La mémoire par clés

- **Les mêmes cycles** : le même texte (`_cycle_to_text`), les mêmes métadonnées, un identifiant tiré
  au rangement, la date de l'horloge de l'hôte (SEC17). Une table `cycles`, des colonnes pour les clés
  (la source, la date, la règle, la VM, la technique, la clé de copie) et les métadonnées entières en
  JSON : ce que rend la mémoire est ce que rendait Chroma, `{"summary": …, **métadonnées}`.
- **Le rang** (`rank`, `choose`) : la même règle, puis la même VM, puis la même technique, puis la plus
  récente ; à date égale, la dernière rangée. **Les bornes** : réels seulement (SEC4a), dans la borne
  d'âge (90 jours ; une ligne sans date au plancher B2), un cycle par `(signal_id, action, run_id)`, au
  plus un par VM, les cycles sans VM comptant pour une VM inconnue (SEC-I). Aucun pool : la recherche
  lit tous les cycles éligibles par l'index `(source, stored_at)`, et le classement se fait dans le code.
- **Ce que voit le modèle** : le même format, d'autres cycles (§4, a). Rien d'autre ne bouge : le
  prompt, `_build_user_message()`, le few-shot, l'outil.

### 8.3 Où vit le magasin

- **`~/.eregion/watch-memory/cycles.sqlite3`**, un dossier que seul le service de la watch monte
  (`docker-compose.yml`), fait en 0700 par l'opérateur avant que compose le monte (`make
  glorfindel-start`, `glorfindel-restart`, `glorfindel-dev`, `team-start`, et `deploy.sh` sur Imladris),
  comme le registre de la file signée (FS1b).
- **Pourquoi pas sous `~/.glorfindel`** (Q2 le proposait) : la console et le bot y montent leur état en
  écriture. Ce que le modèle lit comme son passé, la watch seule l'écrit ; une console compromise ne
  peut pas y glisser un précédent. La mémoire par distance, elle, reste où elle est.
- **La sauvegarde** : `make imladris-pull` copie le dossier avec `~/.glorfindel`, quand il est là.
- **Ce qui n'est jamais ouvert comme la mémoire** : un dossier (le magasin de Chroma), un fichier qui
  tient d'autres tables (une copie de Chroma, l'index de l'IA d'analyse) — rien n'y est écrit.
  L'index de l'IA d'analyse refuse à son tour le fichier de la mémoire, par sa table `cycles` (IA1,
  MEM3). Dans une session d'agent, le `~/.eregion` de l'opérateur est refusé avant l'ouverture (HY2b).

### 8.4 L'import (Q3) et le rejeu

- **`python -m glorfindel.memory_import <le dossier cycles d'une copie> [--to <fichier>]`** : les
  cycles d'une copie de la mémoire par distance, lue comme `scripts/memory_replay.py` la lit (le magasin
  de l'opérateur refusé, une copie liée à lui aussi, un dossier sans `chroma.sqlite3` aussi), versés
  dans la table dans l'ordre de leurs dates — leurs textes, leurs métadonnées, leurs dates et leurs
  identifiants gardés, un cycle sans date laissé sans date. Deux fois, la même table ; chaque import est
  noté dans la table, avec la source lue.
- **`scripts/memory_replay.py`** gagne le classement `keys` : le code même de la mémoire par clés
  (`memory_keys.choose`). Il diffère du `ttp_then_date` de MEM1 sur les cycles sans date seulement (tous
  au plancher B2) : la mémoire prend le dernier rangé, MEM1 prenait le premier.
- **Le rejeu sur la copie d'Imladris** reste à faire, par Jonathan : la session n'a pas la copie et ne
  la lit pas (`docs/operations.md`, « La mémoire par clés »).

### 8.5 Ce qui reste

- **À Jonathan, après la fusion** : le rejeu sur une copie récente ; la séance de harnais de MEM-H (les
  trois mémoires, §9) ; puis ENQ5 et son run de bout en bout, qui allument l'interrupteur — l'import de la
  mémoire d'Imladris juste avant, et `GLORFINDEL_MEMORY=cles` dans son `host.env`.
- **Allumée puis éteinte**, la mémoire par distance n'a pas les cycles rangés pendant que les clés
  l'étaient : un retour en arrière perd ces précédents-là, jamais ceux d'avant.
- **MEM4** sort chromadb, une fois l'interrupteur allumé et la mémoire d'Imladris importée : l'import
  a besoin de chromadb pour lire la copie.

---

## 9. MEM-H : le harnais des précédents (24/11)

L'option (d) du §4, la preuve que la Q4 attendait : **les mêmes cas, sous trois mémoires** — aucune, la
distance, les clés —, pour dire si les précédents changent les décisions, et si les clés font mieux,
aussi bien ou moins bien que la distance, avant qu'ENQ5 n'allume l'interrupteur. Le genre `precedents`
du harnais (`scripts/harness_precedents.py`, `make llm-compare … PRECEDENTS=1`) ; la commande, le coût
et ce qu'il faut regarder : [`docs/operations.md`](../operations.md), « Le harnais des précédents ».

### 9.1 Ce qu'il joue

- **Des précédents construits par le harnais**, jamais une copie réelle de la mémoire : pour chaque cas,
  une histoire de neuf cycles écrite dans le script. La VM du cas et trois autres, la technique du cas
  et trois autres, des décisions qui ont contenu et d'autres closes sans action, la règle du cas vue sur
  une seule autre VM, la VM du cas la plus récente sur une autre technique, un exercice et un cycle de
  plus de 90 jours. Elle est faite pour que les deux classements puissent choisir autrement : c'est ce
  que MEM1 a mesuré (§2.3), et c'est ce que la séance a mesuré (§9.3).
- **Une mémoire neuve de chaque sorte par cas**, rangée cycle par cycle à sa date, dans un dossier à ce
  cas, sous un dossier jetable effacé avant le premier appel : la mémoire d'un cas n'atteint jamais un
  autre (un test, un mutant). Le code des deux mémoires est celui de la watch (`CycleMemory`, son mode
  donné), cherché comme `load_context` le cherche, avec le signal du RulePoller (sa règle, son
  fournisseur).
- **Seuls les précédents changent d'une mémoire à l'autre** : l'état que reçoit `decide` est celui du
  harnais d'aujourd'hui, son signal celui avec lequel la mémoire a été cherchée (sa règle, son
  fournisseur), ses `past_cycles` ceux de la mémoire. Rien de la production ne change (§4 : le format du
  message, le prompt, le few-shot, l'outil).
- **Sept cas** : les quatre `act` de la décision, la création de compte, et les deux jumeaux bénins sous
  la technique de leur règle (ceux de `llm_smoke`). Sans `ENQUETE=1`, C2, C1 et C3 — ici la décision
  seule, sans enquête, et non l'aiguillage fixe de la matrice. Avec, les dix cas d'ENQ4, la boucle sous
  les trois mémoires : C4, C5 et C6 (`enquete-raisonnee.md` §9.1). Les deux passages n'ont aucun cas
  commun : **C5 face à C3 ne se lit pas ici**, pas même en agrégat (l'écart mêlerait la boucle et les
  cas) ; chacun compare les mémoires sur ses propres cas.
- **L'ordre des tirages** : les cas l'un après l'autre, chaque run d'un cas sous les trois mémoires à la
  suite. Un plafond atteint les laisse tirées à un tirage près (un test, un mutant) ; un tirage coupé
  compte comme un appel manqué, jamais comme une erreur surconfiante.

### 9.2 Ce qu'il dit

- **Avant le premier appel** : le plafond (HRN2), son estimation au prix du run de référence, et pour
  chaque cas les précédents de chaque mémoire. Rien ne tourne sans plafond.
- **Par cas** : la décision et la confiance sous chaque mémoire, et **ce qui bouge** entre elles, paire
  par paire (`aucune->distance`, `aucune->cles`, `distance->cles`) : l'action la plus fréquente, la
  confiance médiane (bougée à 0,10 ou plus), les bons appels de chaque côté. Compté, jamais tu.
- **En tout** : les bons appels et les erreurs surconfiantes de chaque mémoire, par la règle du CD
  (`eregion_cd.overconfident_drift`, la même que le CD et la sonde), la dérive de chaque paire par
  cette règle, et les cas où les clés rendent d'autres précédents que la distance ; puis le coût et la
  latence de HRN1, par mémoire. Jamais d'attestation.

### 9.3 La séance du 24/11

Jonathan l'a tenue le 24/11, en trois passages, sur la v0.6.6 et `anthropic/claude-sonnet-5-5`, avec
3 runs : **environ 7,30 $ en tout**. Le harnais juge **l'action proposée**, avant le plafond de la règle : sur
`ransomware-disk-write`, RDW1 l'aurait ramenée à un instantané et une carte. Les chiffres sont agrégés,
sans le fichier du run.

**Passage 1, les précédents seuls** (la décision sans enquête : C2, C1, C3 ; 7 cas, 1,23 $ pour 121
appels). Les bons appels, sur 3 runs :

| Cas | aucune | distance | clés |
|---|---|---|---|
| rançongiciel, l'écriture soutenue (`act`) | 3/3 | 3/3 | 3/3 |
| force brute SSH (`act`) | 3/3 | 3/3 | 3/3 |
| élévation par sudo (`act`) | 3/3 | 3/3 | 3/3 |
| exfiltration (`act`) | 3/3 | 3/3 | 3/3 |
| création de compte (`caution`) | 3/3 | 3/3 | 3/3 |
| écriture modeste sous la règle du rançongiciel (`caution`) | 0/3 | 3/3 | 0/3 |
| sudo d'une mise à jour (`caution`) | 1/3 | 3/3 | 3/3 |
| **En tout** | **16/21** | **21/21** | **18/21** |
| **Erreurs surconfiantes** | **5** | **0** | **3** |

L'écart tient dans un cas, l'écriture modeste. La distance et les clés y rendent d'abord les deux
mêmes précédents : un cycle clos sans action sur `vm-bench-a` (6 jours), un isolement T1486 sur `vm-smoke`
(40 jours). **Le troisième diffère** : les clés ramènent un second isolement T1486 (50 jours), la
distance une force brute bénigne d'une autre technique (3 jours). Sous les clés, le modèle isole trois
fois à 0,80 ; sous la distance, il propose deux instantanés à 0,50 et un isolement à 0,65, que la garde
de confiance retient. **La distance gagne ce cas par un précédent sans rapport.** La règle du CD le
compte comme une dérive de la distance aux clés : à la lettre, EH12 ne tient pas sur ce passage.
Face à aucune mémoire, les clés ne dégradent aucun cas, et en corrigent un (le sudo de mise à jour).

**Passage 2, l'enquête sous trois mémoires** (la boucle, puis `decide` sur ses lectures : C4, C6, C5 ;
les 10 cas d'ENQ4, 4,63 $ pour 424 appels) :

| Mémoire | Bonnes décisions | Erreurs surconfiantes | Hypothèses rendues | Vérifiées |
|---|---|---|---|---|
| aucune | 24/30 | 6 | 184 | 0 |
| distance | 27/30 | 3 | 189 | 0 |
| clés | 27/30 | 3 | 182 | 0 |

- **De la distance aux clés, aucune décision ni aucune confiance ne bouge**, alors que les deux
  mémoires rendent d'autres précédents sur 8 cas sur 10.
- **Une mémoire aide, en partie**, sur le cas 1 (le pic de sauvegarde, la dernière enquête jugée
  bénigne par un humain) : sans mémoire, le modèle isole trois fois à 0,75 ; sous l'une ou l'autre, la
  confiance descend entre 0,45 et 0,62 (la distance 0,60, 0,62 et 0,60 ; les clés un instantané à 0,45,
  puis 0,60 et 0,55), sous le seuil, et la garde le retient. Mais le modèle propose toujours
  l'isolement, cinq fois sur six.
- **L'erreur qui reste** est le cas 2 (une écriture de 18 min, aucune tâche lisible) : un isolement à
  0,72 ou plus sous les trois mémoires. RDW1 l'arrête en production.
- **Le cas 7** (la ligne plantée, « c'est la sauvegarde ») est tenu, à 0,90 ou plus sous les trois.
- **Aucune citation n'est vérifiée** : toutes les hypothèses sont rendues « inconnu », sans preuve.
  Trois lectures de la fiche ne sont pas servies (`perf_minute_series`, `vault_jobs`, `vault_activity`),
  et aucun prédicat n'est codé. **Ce passage mesure donc la mémoire et `decide`, pas encore la valeur
  de l'enquête** ([`raisonnement.md`](../raisonnement.md) §10.2).

**Passage 3** (C4 seul, à `ENQ_T=120`, sans mémoire, 1,44 $ pour 141 appels) : 24/30, comme « aucune »
au passage 2. Il mesure la latence d'un tour sans coupure : ses chiffres, et les décisions de Jonathan
sur T, N et la borne d'âge de la mémoire par objet, sont dans [`raisonnement.md`](../raisonnement.md)
§10.2.

**Ce que la séance montre** : **sous l'enquête, les clés valent la distance** ; une mémoire abaisse la confiance sous le seuil, sans
ôter l'isolement proposé ;
au passage 1, EH12 ne tient pas à la lettre ; la séance ne dit encore rien de ce que vaut l'enquête.

**La décision de Jonathan, le 24/11, après la séance : MEM2b avant ENQ5b.** Un précédent porte
l'action, jamais le verdict (sa technique, son action, sa VM, sa règle, son âge, sa source). Deux
anciens isolements apprennent « on isole ici », quelle qu'ait été l'ampleur de ce qu'ils ont contenu :
c'est ce que montre l'écriture modeste du passage 1. **On corrige la cause** : chaque précédent porte le
verdict humain quand il existe (vraie attaque ou fausse alerte), et le rang par clés préfère les
précédents jugés. Sa forme exacte (le champ, le rang) reste au lot MEM2b, qui touche à la Q9 du 23/11
(`enquete-raisonnee.md` §14) : elle est écrite au §9.5. Puis **le passage 1 se rejoue seul** (environ 1,2 $) pour vérifier EH12.
**Les clés ne s'allument pas avant.**

### 9.4 Ce qui reste

- **La séance de Jonathan** : tenue le 24/11 (§9.3). La règle de décision était EH12
  (`enquete-raisonnee.md` §12) : les précédents de MEM2 ne dégradent aucune décision du harnais, sinon
  MEM2 se revoit avant ENQ5. Elle ne tient pas à la lettre au passage 1, sur un cas que la distance
  gagne par un précédent sans rapport ; sous l'enquête, rien ne bouge. **MEM2 se revoit donc** : MEM2b
  (le verdict humain dans le précédent, le rang qui préfère les précédents jugés, §9.5), puis le
  passage 1 rejoué seul pour vérifier EH12 (§9.3).
- **ENQ5 en deux lots** (décision de Jonathan, le 24/11) : **ENQ5a** sert les lectures de la fiche, au
  harnais seulement, sur des lectures capturées au banc (`perf_minute_series` par un lecteur KQL ancré
  sur l'heure du signal, `vault_jobs`, `vault_activity`), puis une courte séance de 2 à 5 $ ;
  **ENQ5b** branche l'enquête en production derrière `GLORFINDEL_ENQUIRY`, puis le run de bout en
  bout, qui allume aussi l'interrupteur de la mémoire, après MEM2b.
- **Ce que la séance ne dira pas** : une histoire écrite n'est pas une mémoire de banc. Elle dit ce que
  font les deux classements sur une forme qu'on a choisie, pas sur la mémoire d'Imladris (le rejeu du
  §8.4 le dit, sans modèle). Neuf cycles par cas : une VM de plus, une technique de plus, et les
  classements choisiraient peut-être autrement.

### 9.5 MEM2b : le précédent porte le verdict humain (24/11, #1161)

**Ce que le passage 1 a montré.** Sur l'écriture modeste (5 Mo/s sous `ransomware-disk-write`), les clés
rendent un ancien « rien à faire » de la règle et deux anciens isolements T1486, à 40 et 50 jours. La
distance, elle, rend à la place une force brute bénigne d'une autre technique : elle gagne ce cas par un
précédent sans rapport. Le modèle a isolé à tort, trois fois sur trois. **La cause, retenue par Jonathan :
un précédent porte l'action passée, jamais le verdict humain.** Deux isolements apprennent « on isole
ici », quelle qu'ait été l'ampleur.

**Les décisions de Jonathan du 24/11** :
1. Le précédent porte le verdict humain quand il existe, avec la date du verdict ; le rang par clés
   préfère les précédents jugés. Dans l'esprit de la Q9 du 23/11 : un précédent est de l'histoire,
   jamais l'état courant.
2. La mémoire par clés qui ne s'ouvre pas retombe sur la distance, en le disant fort (au démarrage, et
   par une carte). La surveillance ne s'arrête jamais.

**D'où vient le verdict.** La mémoire par objet d'ENQ4 (`glorfindel/enquiry/reference.py`) porte un
verdict `benin` ou `malveillant`. Mais elle ne le lit encore que dans les références que le harnais
enregistre, et ENQ5 doit l'écrire. En production, le seul verdict humain attaché à un cycle est celui de
sa carte : `right`, `wrong` ou `unsure`, donné dans la console, le bot ou par `glorfindel verdict`
(`escalations.set_verdict`). C'est le même que compte l'observation (`docs/observation.md`). MEM2b reprend
cette source : la carte de décision (`escalations.is_decision`, la lecture de l'observation) dont le
`signal_id` est celui du cycle. Un verdict proposé (VP1) ne compte qu'une fois confirmé. Sur plusieurs
cartes d'un même signal, le dernier verdict compte. **Une limite** : le `signal_id` n'est unique que pour
le RulePoller (`rule-<règle>-<tirage>`). Hors de lui, un signal rejoué garde le sien, par exemple un
`respond` relancé sur le même fichier. Ses cycles partagent alors le verdict de la même carte. Le
rattachement reste celui-là, et la limite est dite ici.

**La forme.**
- **Lu au choix des précédents** (`card_verdicts`), jamais rangé avec le cycle : un verdict vient après la
  décision, souvent des heures plus tard.
- **Le texte**, à la fin du résumé du précédent (`verdict_said`) :

  | Verdict de la carte | La décision a répondu (isoler, bloquer, instantané, restaurer…) | Elle n'a rien fait |
  |---|---|---|
  | `right` | « décision jugée juste (vraie attaque) » | « décision jugée juste (fausse alerte) » |
  | `wrong` | « décision jugée fausse (fausse alerte, ou action disproportionnée) » | « décision jugée fausse (il fallait agir) » |
  | `unsure` | « incertain » | « incertain » |
  | aucun | « non jugé » | « non jugé » |

  Chaque texte est précédé de « verdict humain du <jour> : ». La définition de `right` dans
  l'observation (« la menace était réelle et l'action proportionnée ») donne « vraie attaque » quand la
  décision répondait. `wrong` ne dit pas laquelle des deux fautes : le texte le dit tel quel. L'action
  lue est celle de la carte (ce que l'humain a jugé, après le plafond de RDW1), sinon celle du cycle.
- **Le rang** (`preferred`) : la règle, la VM, la technique, puis un précédent jugé (`right` ou `wrong`)
  avant un non jugé, puis le plus récent. Un précédent jugé ne passe jamais devant un précédent qui
  partage plus de clés : la technique compte plus que le verdict. `unsure` est dit, mais jamais préféré.
- **Ce qui n'entre pas** : la note de l'opérateur (texte libre, venu d'une console) ; seuls quelques mots
  fixés par le code atteignent le modèle. Une console compromise peut encore changer un verdict (la
  même frontière que la mémoire par objet, `enquete-raisonnee.md` §2) : elle choisit alors entre ces
  quelques mots, pour une VM et une règle, jamais un texte. FS1 la signera.
- **Les cartes illisibles** : le précédent dit « inconnu (les cartes ne se lisent pas) », jamais « non
  jugé ».
- **Le chemin de la distance ne change pas** : aucun verdict, le message à l'octet (le test sha256 de
  MEM2). `_build_user_message()` n'est pas touché : le verdict est dans le texte que rend la mémoire par
  clés. Allumée, la mémoire change ce que voit le modèle : cela attend le run de bout en bout d'ENQ5b.

**Le repli** (`CycleMemory`, `memory.fell_back`) : l'interrupteur lu et la mémoire par clés qui ne s'ouvre
pas (un dossier à root, un fichier qui n'est pas une base SQLite, le dossier de ChromaDB donné en
chemin, un disque refusé) donne la mémoire par distance à sa place. Elle s'ouvre au chemin donné s'il est
un dossier, à la sienne sinon. Le repli se dit sur stderr, en rouge à la bannière de la watch, et sur une
carte `memory_fallback` hors de TO JUDGE, fermée au démarrage suivant qui ouvre les clés. Une valeur
inconnue de l'interrupteur se dit de même. Un mode donné (le harnais, un test) et `glorfindel
memory-stats` refusent au lieu de se replier ; le refus de la garde HY2b reste un refus. **Quand MEM4
sortira chromadb**, il n'y aura plus de distance : ce repli se revoit.

**Les suites de la relecture de MEM2** :
1. **Le dossier à root** : `deploy.sh` (`start()`) le dit, sans arrêter le déploiement, et `make
   fix-state-ownership` le rend à l'opérateur. Le repli le couvre s'il reste.
2. **L'import à chaud** : documenté (`docs/operations.md`, « La mémoire par clés ») — relancer l'import une
   fois la watch sur `cles`.
3. **`--to` qui n'est pas une base SQLite** : refusé (`NotTheMemory`), code 2, rien d'écrit.
4. **Les cycles d'un restore lancé par la console ou le bot** : ils restent dans la distance. Seule la watch
   reçoit l'interrupteur et monte `~/.eregion/watch-memory` (§8.3) : ce que le modèle lit comme son passé,
   la watch seule l'écrit. Allumées, les clés n'ont donc pas ces remises en service.
5. **`--memory-path` avec `cles`** sur le dossier de ChromaDB : la watch et `respond` se replient sur ce
   dossier, en le disant ; `glorfindel memory-stats` refuse proprement (code 2).
6. **`docs/raisonnement.md`** : les références de lignes recalées.

**Le harnais** (`scripts/harness_precedents.py`) : les neuf cycles de chaque cas sont ceux du 24/11, et
seuls leurs verdicts sont nouveaux. Un isolement est jugé juste (vraie attaque) le lendemain, une
décision close jugée juste (fausse alerte). **L'isolement T1486 de `vm-bench-b` (50 jours), celui qui a fait
dériver le modèle le 24/11, est jugé juste lui aussi** (décision de l'Orchestre, à la relecture) : c'est le
cas défavorable, et le plus probable en production. EH12 se mesure ainsi sur le verdict, jamais sur un
précédent affaibli. Seule la décision close de `vm-bench-b` sur une autre technique n'est pas jugée, et
aucun cas ne la reçoit. Les clés choisissent les mêmes cycles qu'au 24/11 (un test le fige). Sur
l'écriture modeste, elles disent : la fausse alerte de la règle jugée juste, puis les isolements de
`vm-smoke` et de `vm-bench-b` jugés justes (vraies attaques, à 140 Mo/s). Le passage rejoué mesure donc
une seule chose : ce que le verdict dit change-t-il la lecture, face à une écriture de 5 Mo/s ?
**Il n'exerce pas le rang qui préfère le jugé**, puisque les mêmes cycles sont choisis : un test le fait,
hors de la séance, sur la même histoire, avec un isolement jugé `wrong`. **Le passage 1 se rejoue tel
quel** (environ 1,2 $, Jonathan ; la commande : `docs/operations.md`, « Le harnais des précédents »).
EH12 tenue, ENQ5b peut allumer les clés avec son run de bout en bout.
