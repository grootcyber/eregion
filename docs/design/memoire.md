# La mémoire des décisions, mesurée : la distance contre la date (MEM1, #1016) — conception

_Conception — 21/11 (MEM1, #1016) — statut : **mesure faite, choix ouvert** (§7). Suite de la dixième
passe de revue (20/11, P10-6). Le code de la mémoire ne change pas. Seul le script de mesure entre dans
le dépôt (`scripts/memory_replay.py`). Le choix revient à Jonathan, et chacune des options qui changent
les précédents rendus au modèle attend son run de bout en bout (§4)._

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
  `campaign_report.py:658` et `:697` ; `get(ids=…)`, `analysis/campaign_index.py:95`). Il n'appelle jamais
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
| **MEM2** — les précédents par clés et par date | Glorfindel | `glorfindel/memory.py` sur SQLite (Q2), la même interface (`store`, `retrieve_similar`, `age_census`, `count`) ; le rang : règle, VM, technique, date ; les bornes gardées ; `glorfindel memory-stats` ; les tests de la mémoire portés (`test_memory_age.py`, `test_enquiry_memory.py`, `test_agent_nodes.py`) ; l'import des cycles d'une copie (Q3) ; `scripts/memory_replay.py` gagne le classement du lot | le message au modèle identique au format près (un test le fige) ; le rejeu sur la copie d'Imladris ; **le run de bout en bout de Jonathan** | M | **6** : le TTP hors des clés ; la distance ou un ordre ancien au lieu du plus récent ; la borne par VM ; l'âge ; un exercice rendu ; une copie non repliée |
| **MEM-H** — le harnais des précédents (d) | Glorfindel | un genre `precedents` dans `scripts/llm_smoke.py` : les mêmes cas, trois mémoires (aucune, distance, clés), les décisions et les confiances qui bougent, au rapport de `make llm-compare` | **les runs payants de Jonathan**, avant la fusion de MEM2 | S | **2** : une mémoire du cas qui fuit dans une autre ; l'écart non compté |
| **MEM3** — l'index de l'IA d'analyse sur la même table — **fait le 22/11 (#1029)** : SQLite, l'import de l'ancien index, `docs/analysis.md` | Analyse | `analysis/campaign_report.py` (`_collection`, `index_facts`, `prior_runs`, `previous_campaign`), `analysis/campaign_index.py`, `analysis/separation.py` (IA1 : jamais la mémoire de Glorfindel) ; les lignes rendues et leur ordre gardés (un test, sur un index d'avant) | les rapports de campagne identiques sur le jeu d'exemple | S–M | **3** : l'ordre des lignes ; la séparation d'IA1 ; une ligne illisible lue vide |
| **MEM4** — chromadb hors des dépendances | Glorfindel, gestes de Jonathan | `pyproject.toml`, `make lock`, les quatre avis retirés de `requirements/audit-accepted.json` ; `scripts/chroma_model.py`, FLK1 et le lien du HOME jetable retirés ; les montages de `~/.cache/chroma` (`docker-compose.yml`, `Makefile`, `infra/glorfindel-host/main.tf`), `scripts/doctor.py`, `scripts/image_check.py` ; les mutants qui visent Chroma (lots CI8, FLK1, CI6b, CI10b, HY2b, HY2c, SEC-K) retirés ou reportés. **Les workflows, par Jonathan** | **le harnais de Jonathan** (verrou changé) avant de redéployer Imladris | M | **1–2** : une trace de chromadb dans l'image ; un montage oublié |
| **MEM2b** — si Q1 = (b) à la place | Glorfindel | le TTP dans le rang de `retrieve_similar`, une recherche par technique dans le pool | le rejeu ; **le run de bout en bout de Jonathan** | S | **2** : le TTP hors du rang ; la recherche par technique absente du pool |

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
