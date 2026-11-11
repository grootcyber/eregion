# Le dossier d'une isolation : les faits lus pour qu'un humain n'ait plus qu'à juger (DOS1, #727) — conception

_Conception — 11/11 (DOS1, #727) — statut : **conception seulement, questions ouvertes** (§12). Rien
n'est codé ni mesuré. Jonathan a décidé le lot le 11/11 (« conception maintenant »), après l'enquête
qu'il a menée à la main sur bree. Les lots de code (§11) attendent ses réponses ; chaque fait nouveau
reste à mesurer au banc avant d'être cru (§9)._

> « J'aurais aimé que ce soit Glorfindel qui fasse tout ça, et pas moi qui passe mon temps à tout
> vérifier. » — Jonathan, le 11/11, après l'enquête sur l'isolement de bree.

**Lié** : [`levee-probation.md`](levee-probation.md) (LEV1, LEV2 : des faits « pour information » sur
la carte d'isolement, le modèle que ce document suit) ; [`corroboration.md`](corroboration.md)
(SEC-A3 : une preuve non forgeable avant une action autonome) ; [`identites.md`](identites.md) (IDM1 :
ce que tient chaque identité) ; [`docs/glorfindel.md`](../glorfindel.md) (l'enquête, les gardes de
`decide`, la vérification, la coupure suivie de DRN1, la porte de LEV2) ;
[`modele-de-menace.md`](modele-de-menace.md).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne
(au commit `b59c2419`). Ce qui est dit d'Azure (le journal d'activité, les métriques de l'hôte, les
jobs du coffre, la santé des ressources) vient de la documentation publique de Microsoft ou d'une
mesure déjà faite au banc, et le dit. Tout le reste est une **hypothèse**, numérotée DH1 à DH12 (§9),
à mesurer avant le code qui en dépend. Les chiffres de la nuit du 10/11 sont ceux du relevé de la
session Tests (fiche du lot) ; ce document les reprend sans les avoir relus.

---

## 0. En bref

- **Le dossier, ce sont des faits, jamais un verdict.** Pour une isolation (et pour une carte qui
  propose d'isoler, Q2), la watch lit ce que Jonathan a lu à la main le 11/11 : ce que faisait la
  plateforme au moment du signal, ce que l'hôte a vu du même chiffre, si le dépassement revient, qui
  s'est connecté, et ce qu'ont donné les propres gestes de Glorfindel. Chaque fait dit sa source, son
  auteur (la plateforme, l'invité, Glorfindel), la requête qui l'a lu et son état : **lu**, **vide**,
  **illisible** ou **en attente**. Une lecture qui échoue est dite illisible, jamais vide. Le dossier
  ne conclut pas « faux positif ». L'humain juge.
- **Il vient après l'action, jamais avant.** La contention ne l'attend pas. Il se compose en trois
  temps (§4.5) : ce que le cycle sait déjà, écrit à la fin du cycle, sans aucun appel ; les lectures
  d'Azure, dans un fil à part, comme la porte de LEV2 ; l'après-coup (la coupure, la vérification,
  les cartes), complété jusqu'à ce qu'il soit réglé.
- **Il n'atteint jamais le modèle.** Le dossier vit à côté du signal, dans un fichier de la watch, comme
  les faits de la porte (`glorfindel/door_facts.py`). Ni `_build_user_message()`, ni
  `few_shot_examples.yaml`, ni `_SYSTEM_PROMPT` ne changent : un test fige le message. Le montrer un
  jour au modèle est une question à part (Q3) et un lot à part, avec son run de bout en bout, par
  Jonathan.
- **Il ne demande aucun droit nouveau.** Le journal d'activité de la VM, les jobs du coffre, la vue
  d'instance, l'état de santé de la ressource et les métriques se lisent sous le `Reader`
  qu'Imladris (anciennement H0) tient sur le groupe du banc ; `Perf`, `Syslog` et `Heartbeat`, sous son `Log Analytics Reader`. Deux
  de ces lectures n'ont encore jamais été faites par Glorfindel : les métriques de l'hôte et l'état de
  santé de la ressource. Leur droit est tenu sur le papier, et à mesurer (DH4, DH7). Les événements
  `ServiceHealth`, qui vivent au niveau de l'abonnement, demanderaient un `Reader` sur l'abonnement :
  ils restent **sans objet** sous les droits actuels (§3.2).
- **La garde est la question de Jonathan (Q1).** La conception recommande de ne rien retenir sur le
  dossier en v1. Comparée sur la même minute, la métrique de l'hôte risque de ne dire que la durée
  du pic, que l'invité dit déjà. L'attaque de référence du banc écrit pendant environ 50 s : une
  métrique à la minute pourrait la lire faible, et la garde retiendrait alors l'attaque même
  qu'Eregion prouve. Et la latence de cette métrique se paierait sur la contention d'une technique
  grave. On mesure d'abord, sur les données déjà gardées (§9.1).
- **Sept lots de code** (§11), DOS2 à DOS8, et deux lots conditionnels, selon les réponses de Jonathan.

---

## 1. Le cas qui fonde le lot : bree, la nuit du 10/11

### 1.1 Ce qui s'est passé

| Heure (UTC, 10/11) | Fait | Source |
|---|---|---|
| 02:33:19 | la sauvegarde nocturne de bree démarre | le job du coffre |
| ~02:33:50 et ~02:34:00 | deux échantillons de 10 s de `Disk Write Bytes/sec` sur `/`, 30,4 puis 65,9 Mo/s, le premier daté 31 s après le départ de la sauvegarde (un échantillon daté couvre les 10 s qui précèdent sa date ; les échantillons d'avant ne sont pas dans le relevé) | `Perf` (l'agent de l'invité) |
| autour du pic | la métrique de l'hôte, `OS Disk Write Bytes/sec`, ne voit que 9,4 Mo/s (le relevé ne dit ni l'agrégation ni la minute) | Azure Monitor (l'hôte) |
| 02:35:56 | `ransomware-disk-write` (T1486) correspond | le RulePoller |
| juste après | `decide` : `isolate_vm`, confiance 0,80 ; bree en `non_disruptive` ; les 3 tirages de D-1 sont unanimes ; l'isolation part seule | `*_debug.jsonl` |
| 02:36:22 → 02:43:36 | la coupure des sessions (Run Command) dure 7 min 14 s, pendant que l'extension de sauvegarde tourne. Qu'elle **attende derrière** l'extension est l'hypothèse du relevé, pas une mesure (DH11) | le journal d'activité |
| ensuite | la v0.5.8 n'a pas DRN1 : la vérification échoue (d'après le code de la v0.5.8 : la coupure était attendue 300 s, puis lue comme une sortie illisible, `docs/glorfindel.md`, « La coupure suivie sur Azure ») | la carte `verification_failed` |
| ensuite | une carte critique T1651 naît de cette seule coupure (la règle de SID1, `run-command-by-glorfindel-outside-isolation`, `detection_rules.yaml:708`) | la carte |
| pendant 35 h | personne n'acquitte les trois cartes | `escalations.jsonl` |
| sur 10 jours | aucun autre dépassement ; aucune connexion SSH acceptée ; 298 échecs depuis 41 sources | `Perf`, `Syslog` |

**Le seuil, lu dans la règle.** La fiche dit « 50 Mo/s ». La règle livrée est plus fine
(`glorfindel/rules/azure/detection_rules.yaml:29-80`). Le banc échantillonne toutes les 10 s
(`infra/terraform/config.yaml:115`, `perf_sampling_frequency: 10`) : la règle est alors en pas fin, et
elle compare la **moyenne de deux échantillons consécutifs** à 45 000 000 octets/s. Sur les chiffres
relevés, (30,4 + 65,9) / 2 = 48,2 Mo/s, soit 7 % au-dessus du seuil ; `MaxWrite` porte le pic, 65,9.
Ce calcul est fait ici, sur le relevé. Il reste à confirmer sur la ligne `detected_data` du cycle, et
selon l'unité du relevé (Mo de 10⁶ octets, ou Mio).

### 1.2 Ce que les principales gardes ont fait, lu dans le code

| Garde | Ce qu'elle a fait ce soir-là | Pourquoi |
|---|---|---|
| le garde-fou du signal (`_apply_signal_guardrail`, `glorfindel/agent.py:1166`) | rien | `MaxWrite` est un indicateur curé : le signal est caractérisé |
| la porte de confiance (`_apply_confidence_gate`, `agent.py:931`) | rien | 0,80, au-dessus du seuil par défaut de 0,7 (`glorfindel/config.py`, `confidence_threshold`) |
| la garde de télémétrie (`_apply_telemetry_guard`, `agent.py:1419`) | rien | aucune requête d'enquête **en échec**. Mais une requête qui ne peut rien dire n'est pas un échec (§1.3) |
| le mode (`_apply_autonomy_mode`, `agent.py:1523`) | laisse partir | bree en `non_disruptive` depuis le 01/11 ([`bl1-technique-grave.md`](bl1-technique-grave.md)) |
| l'accord des tirages (D-1, `_apply_agreement_guard`, `agent.py:1629`) | laisse partir | 3 tirages sur 3. Les tirages sondent la variance du modèle sur **la même entrée**, pas la vérité de l'entrée : un modèle constant dans l'erreur passe |
| `GRAVE_TTPS` (`glorfindel/decision_queue.py:57`) | fait passer la détection en tête de file | ce n'est pas une garde : il ordonne la file de décision (SEC-A2), il ne retient rien |

Les autres gardes de `decide` ne visent pas ce cas, d'après leur docstring : la garde exécutable
(`_apply_executable_guard`, `agent.py:917` : `isolate_vm` est implémentée), l'attribution
(`_apply_attribution_guard`, `agent.py:1193` : la ligne nomme sa VM), la précondition de levée
(`agent.py:1449` : une levée seulement), `never_block` (`agent.py:1241` : un blocage seulement), le
plancher d'un compromis confirmé (B3a, `agent.py:1306` : ni brute force réussi ni sudo vers root) et
celui d'une détection non contenue (`agent.py:1353` : un instantané seul).

Toutes les gardes déterministes ont vu juste sur ce qu'elles regardent. Aucune ne regarde la
plateforme. La seule lecture qui aurait pu changer l'issue est une lecture que personne ne faisait.

### 1.3 Ce que le modèle ne pouvait pas voir

`investigate` (`glorfindel/agent.py:610`) lance, sur un dépassement d'écriture, trois requêtes
(`agent.py:702-708`) :
- `top_write_processes` et `backup_agent_check` lisent le compteur `Process` `IO Write Bytes/sec`.
  Le code le dit lui-même (`agent.py:536-544`) : ce compteur n'existe que sous Windows, et **ces deux
  requêtes rendent toujours `[]` sur une VM Linux**. Ce que le modèle a reçu sur bree, c'est le texte
  que `_build_user_message()` rend pour une liste vide (`agent.py:3054-3060`) :
  `**backup agent check** : aucun résultat (requête vide ou données absentes)`, là où la télémétrie ne
  pouvait rien en dire. Comment le modèle l'a lu (une absence de sauvegarde, ou une donnée manquante)
  reste à vérifier dans le `reasoning` du cycle, que ce document n'a pas relu. Ce n'est pas un échec de
  requête : la garde de télémétrie ne le compte pas ;
- `heartbeat_gap` cherche un redémarrage récent, sur deux heures.

`successful_auth_from_ip` (`agent.py:555`, `agent.py:712`) ne tourne que sur un brute force, pour
l'adresse de la ligne. Sur le signal de bree, personne ne l'a lancée. Rien, dans le cycle, ne lit le
coffre, le journal d'activité ni la métrique de l'hôte.

### 1.4 Ce que l'humain a dû lire à la main

Jonathan a ouvert le coffre (le job de 02:33:19), la métrique de l'hôte (9,4 Mo/s), `Perf` sur dix
jours (aucun autre dépassement), `Syslog` (aucune connexion acceptée), le journal d'activité (la
coupure de 7 min 14 s), et le fichier de debug sur Imladris. Ce dernier ne disait pas le modèle de la
décision (§3.7). Ce sont ces lectures que le dossier fait à sa place.

---

## 2. Les principes

1. **Des faits, jamais un verdict.** Le dossier ne dit ni « bénin » ni « attaque ». Il peut aligner des
   faits qui se répondent (« la sauvegarde a démarré 31 s avant la date du premier échantillon ») ; il ne les
   pèse pas. LEV2 a posé la même règle pour la porte (`glorfindel/door_facts.py`, en-tête).
2. **Illisible n'est jamais vide.** Une lecture coupée, refusée, en échec, ou d'une forme inattendue
   rend le fait **illisible**, avec sa raison. « Aucun job de sauvegarde » ne s'écrit que si le coffre a
   répondu en entier (la propriété de LEV2, `tests/unit/test_door_facts.py`). Une source qui ne peut
   rien dire sur cette VM (le compteur `Process` sous Linux) le dit : **sans objet**, jamais vide.
3. **Chaque fait dit son auteur.** La plateforme (le coffre, ARM, l'hôte) : un utilisateur local ne
   l'écrit pas. L'invité (`Perf`, `Syslog`) : `Syslog` est forgeable par tout utilisateur local
   ([`corroboration.md`](corroboration.md), §1.1). `Perf` ne l'est pas, mais un utilisateur local peut
   provoquer une vraie écriture (§2.2 du même document) : il est **provocable**. Un trou de `Heartbeat`
   (un root local arrête l'agent) et l'état d'une extension dans la vue d'instance (écrit par l'agent
   de la VM) le sont aussi : ce sont des faits de l'invité, et la carte les dit « dit par l'invité ».
   Glorfindel (son état, ses cartes, sa ligne de debug).
4. **Après l'action, ou à côté.** Aucune lecture du dossier ne se fait dans le fil de la VM avant
   l'action, ni sous son verrou. L'étape 0 (§4.5) se fait dans le fil de la VM, mais après l'action et
   sa vérification ; elle ne lit que des fichiers locaux (`escalations.jsonl`, l'état d'isolement, le
   registre des assets) et l'état du cycle, sans aucun appel. Les lectures d'Azure se font dans un
   autre fil. La contention ne paie rien (§7).
5. **Jamais au modèle sans le dire.** Le dossier ne va ni dans le signal, ni dans la mémoire
   (ChromaDB : `past_cycles` est l'entrée du modèle), ni dans le message (§4.4).
6. **Aucune identité, aucun droit nouveau** (§6).
7. **Borné.** Chaque lecture a sa fenêtre, ses pages, son délai ; le dossier a un plafond par heure
   (§7).

---

## 3. Les faits du dossier

### 3.1 La forme d'un fait

Chaque fait est une entrée du fichier du dossier :

| Champ | Ce qu'il dit |
|---|---|
| `id` | le nom du fait (`backup_job`, `host_metric`…) |
| `dit` | la phrase de la carte, composée par le code à partir des valeurs lues |
| `valeurs` | ce qui a été lu, brut et borné (heures, octets, nombres) |
| `source` | la table, l'API ou le fichier |
| `lecture` | la requête KQL, ou l'appel REST, tels qu'envoyés (sans jeton) |
| `auteur` | `plateforme`, `invité` ou `glorfindel` ; un fait de l'invité porte `forgeable: true` (une ligne de `Syslog`, qu'un utilisateur local écrit) ou `provocable: true` (un fait vrai qu'il peut faire naître : une écriture dans `Perf`, un trou de `Heartbeat`, l'état d'une extension écrit par l'agent) |
| `etat` | `lu`, `vide`, `sans_objet`, `illisible` (avec `pourquoi`), `en_attente` (la latence de la source n'est pas encore passée) |
| `lu_a` | l'heure de la lecture ; un fait relu garde la dernière |
| `mesure` | `mesuré` (et où) ou `à mesurer` (le numéro DH) : ce qui n'est pas mesuré le dit sur la carte |

Toutes les fenêtres sont **ancrées sur l'heure du signal** (`T`, l'heure de la ligne qui a déclenché la
règle), jamais sur l'heure de la lecture. Les requêtes d'`investigate` utilisent `ago(5m)` à
`ago(10m)` (`agent.py:505-509`), et `ago(2h)` pour `heartbeat_gap` (`agent.py:511-522`) : lues dix
minutes plus tard, elles ne verraient plus la même chose.
Le dossier passe au contraire une fenêtre absolue (`run_query(…, timespan=(début, fin))`,
`glorfindel/providers/azure/monitor.py:93`), et chaque valeur tirée d'une ligne entre dans sa requête
comme littéral vérifié (`glorfindel/kql.py`, SEC4c).

### 3.2 F1 — Le contexte de la plateforme

Ce que faisait Azure sur la VM, de `T − 30 min` à `T + 10 min`.

| Fait | Ce qu'il dit | Source, lecture | Auteur | Illisible quand | État |
|---|---|---|---|---|---|
| **F1a** `backup_job` | un job du coffre sur cette VM dans la fenêtre : son type (`Backup`, `Restore`…), son heure de départ, son état, sa durée ; l'écart entre son départ et `T` | les jobs du coffre : `backup_jobs.list(vault, vault_rg)`. Deux lecteurs existent déjà : celui des jobs `Backup` de l'action `snapshot` (`glorfindel/providers/azure/backup.py:160-187` : `operation == "Backup"`, `entity_friendly_name`, `start_time`), et celui de REC1 pour un restore (`recovery.py:250`), filtré par la VM et son conteneur | plateforme | le coffre ne répond pas, la liste est coupée, la VM n'a pas de coffre connu (`action_backends`) | les jobs `Backup` d'un instantané à la demande sont lus en service ; **la forme d'un job planifié et son filtrage sur N jours, à mesurer** (DH2) |
| **F1b** `extensions` | les extensions de la VM en cours ou finies dans la fenêtre (la sauvegarde : `VMSnapshotLinux` ; l'agent ; une extension d'un tiers), leur état et l'heure de cet état | la vue d'instance (`virtualMachines/instanceView`), et les écritures d'extension du journal d'activité (la lecture du groupe de LEV2, `door.py`, filtrée sur les enfants de la VM) | l'écriture d'une extension au journal : plateforme. **Son état dans la vue d'instance : invité, `provocable`** (l'agent de la VM l'écrit ; la carte dit « dit par l'invité ») | la vue d'instance ne se lit pas | **à mesurer** (DH3) : la vue d'instance ne porte jamais Run Command v1 (mesuré, REC1b), on ignore ce qu'elle porte d'une sauvegarde en cours |
| **F1c** `reboot` | un démarrage, un redémarrage, un redéploiement dans la fenêtre ; un trou de `Heartbeat` | le journal d'activité (`restart/action`, `start/action`, `redeploy/action`, `deallocate/action`) ; `Heartbeat` (la requête `heartbeat_gap` d'`investigate`, déjà lancée sur ce signal : son résultat est repris, sans relecture) | le journal : plateforme. **Le trou de `Heartbeat` : invité, `provocable`** (un root local arrête l'agent, et le code lit ce trou comme un redémarrage, une explication bénigne de l'écriture : `agent.py:705-707`) ; la carte dit « dit par l'invité » | le journal ne se lit pas | `Heartbeat` lu par `investigate` ; le journal **à mesurer** (DH1) |
| **F1d** `platform_health` | un événement de santé de la VM dans la fenêtre (une dégradation de l'hôte, une migration à chaud), et une maintenance planifiée en attente | le journal d'activité, catégorie `ResourceHealth`, dans la même lecture que F1c ; l'état de disponibilité de la ressource (`Microsoft.ResourceHealth/availabilityStatuses`) ; `instanceView.maintenanceRedeployStatus` (la maintenance planifiée), dans la lecture de la vue d'instance de F1b. **`ServiceHealth` : sans objet sous les droits actuels.** D'après la documentation d'Azure (pas une mesure), un événement `ServiceHealth` vit au niveau de l'abonnement, sans le `resourceUri` de la VM : la lecture exacte de la VM ne le rend jamais, et le lire au niveau de l'abonnement demanderait `Microsoft.Insights/eventtypes/values/read` sur l'abonnement (un `Reader` d'abonnement), qu'Imladris n'a pas | plateforme | la lecture échoue | **à mesurer** (DH7) : la portée et le délai de ces événements viennent de la documentation d'Azure ; on ne sait pas s'ils arrivent pour une VM du banc |
| **F1e** `guest_context` | ce que l'invité dit faire dans la fenêtre : les lignes de `waagent`, d'`apt`/`unattended-upgrades`, de `cron` | `Syslog`, sur la VM, dans la fenêtre | **invité, forgeable** | la requête échoue | la carte le marque « dit par l'invité » |

**Pourquoi F1e.** La règle a déjà tiré, au matin du 05/10, sur le rattrapage d'`apt`/`snap` d'Ubuntu
(commentaire de la règle, `detection_rules.yaml:37-38`). Ce contexte aide l'humain. Mais un attaquant
local écrit dans `Syslog` sous l'étiquette qu'il veut : F1e ne pèse jamais seul, et la carte le dit.

**Une seule lecture du journal pour F1b, F1c et F1d.** Une lecture exacte de la VM
(`resourceUri eq '<vm>'`) sur la fenêtre, toutes catégories, bornée à `ACTIVITY_PAGES` pages comme
REC1b et LEV2 (`glorfindel/providers/azure/recovery.py`, `door.py`) ; plus la lecture du groupe
filtrée sur les enfants de la VM, que LEV2 fait déjà pour la porte (H9 de LEV2 : le filtre exact ne
rend pas les enfants).

### 3.3 F2 — Un second avis sur le chiffre

**Ce qu'il dit.** Pour une règle qui lit un compteur de l'invité, la métrique de l'hôte qui mesure la
même grandeur, **sur les mêmes minutes**. Aujourd'hui, une seule règle livrée lit `Perf` :
`ransomware-disk-write`. Les autres lisent `Syslog`, `StorageBlobLogs`, `AzureActivity` ou les journaux
d'Entra ID (`detection_rules.yaml`).

| Règle (compteur de l'invité) | Métrique de l'hôte (Azure Monitor, `Microsoft.Compute/virtualMachines`) | Correspondance |
|---|---|---|
| `ransomware-disk-write` (`Logical Disk` / `Disk Write Bytes/sec`, par point de montage) | `OS Disk Write Bytes/sec` pour `/` ; `Data Disk Write Bytes/sec` par LUN pour un disque de données ; `Disk Write Bytes` (tous disques) en total | une table fermée, dans le code : un point de montage ne se relie pas seul à un LUN (DH5). Faute de lien sûr, le dossier compare le total de l'invité (`_Total`) au total de l'hôte, et le dit |
| une règle d'un client sur `Network Interface` / `Bytes Sent/sec` | `Network Out Total` | la même table, une ligne de plus le jour où une règle l'exige |

**La fenêtre et le rapport.** C'est le cœur du fait, et ce que le cas de bree apprend :
- La métrique de la plateforme a une granularité d'**une minute** au plus fin (la documentation
  d'Azure Monitor ; DH4). Le compteur de l'invité, au banc, en a une de **10 s**. Comparer le pic de
  l'invité (65,9) à la moyenne d'une minute de l'hôte (9,4), c'est surtout mesurer la **durée** du pic.
- Le dossier compare donc **la même chose** : pour chaque minute de `T − 5 min` à `T + 2 min`, la
  moyenne des échantillons de l'invité dans cette minute (reconstruite par une requête `Perf`, `bin(1m)`
  sur l'heure de l'échantillon) face à la moyenne de l'hôte sur la même minute (agrégation `Average`,
  et `Maximum` si Azure la fournit pour cette métrique, DH4). Il écrit les deux séries et leur rapport,
  minute par minute.
- Sur bree, le relevé ne dit ni l'agrégation, ni la minute du 9,4. Si les autres échantillons de la
  minute étaient proches de zéro, la moyenne de l'invité sur la minute serait d'environ 16 Mo/s :
  l'écart avec l'hôte serait bien plus mince que ne le laisse croire 65,9 contre 9,4. C'est la
  première chose à mesurer, sur les données gardées (§9.1, DH5).

**Le lien avec la corroboration (SEC-A3, CR15).** Ce n'est **pas** le même mécanisme, et ce n'est
pas la même question.
- La corroboration demande : **la ligne a-t-elle pu être écrite par un utilisateur local ?** Elle exige
  une source qu'il ne peut pas écrire (le journal d'audit du noyau, un flux réseau par 5-tuple). Pour
  `Perf`, la réponse est déjà non : l'agent lit le noyau, et aucune preuve n'est requise
  ([`corroboration.md`](corroboration.md), §2.1 et §2.2). CR15 est une propriété du compte des flux
  (aucune identité joignable depuis une VM n'y écrit), sans rapport avec les disques.
- Le second avis demande : **le chiffre, vrai, mesure-t-il ce que la règle croit ?** Un pic réel, court,
  que la plateforme a provoqué (un gel du système de fichiers pour l'instantané, une écriture de
  l'extension) est un fait vrai que la règle lit comme un chiffrement.
- Ce qu'ils partagent : **l'architecture**. Si F2 devient un jour une garde (Q1, option B), elle
  prendrait la forme que SEC-A3 a décidée. Un verdict qui voyage à côté du signal, dans
  `GlorfindelState`, jamais dans le message. Une garde de `decide` qui retient l'action disruptive
  quand le verdict n'est pas « corroboré ». Une source en retard, en panne ou muette : une carte
  (`corroboration.md`, §3.2 à §3.5). Le dossier, lui, n'a besoin de rien de cela : il est lu après.

### 3.4 F3 — La récurrence

| Fait | Ce qu'il dit | Source, lecture | Auteur | État |
|---|---|---|---|---|
| **F3a** `recurrence` | sur les `N` derniers jours (Q6, 10 par défaut), le nombre de fenêtres où la règle aurait tiré sur cette VM, avec le même calcul (pas fin ou grossier, moyenne de deux échantillons ou échantillon seul), par heure du jour et par point de montage ; le maximum de la même heure, nuit après nuit | `Perf`, la requête de la règle rejouée sur `[T − N jours, T]` pour cette seule VM, résumée par `bin(1h)` et par `InstanceName` | invité (non forgeable, provocable) | **à mesurer** (DH9 : son coût sur dix jours d'échantillons à 10 s) |
| **F3b** `recurrence_vs_backup` | les mêmes nuits, l'écriture maximale de l'invité dans les 5 minutes qui suivent le départ de chaque job de sauvegarde de la VM | F3a croisé avec la liste des jobs `Backup` de F1a sur `N` jours (la même lecture du coffre, la fenêtre élargie) | les jobs : plateforme ; l'écriture : invité, `provocable` (un attaquant peut écrire chaque nuit à la même heure, pour conditionner la série) | **à mesurer** (DH2, DH9) |
| **F3c** `past_cards` | les cartes de cette VM et de cette règle sur `N` jours, et leur verdict quand un humain en a donné un (`escalations.verdict` : jugée bénigne, malveillante…) | `~/.glorfindel/escalations.jsonl`, `escalations.recurrence` (`glorfindel/escalations.py:767`) étendu à la règle | glorfindel | lu (local) |

**Pourquoi F3b.** C'est le fait qui aurait suffi à Jonathan : chaque nuit, à la même minute, une
écriture qui suit la sauvegarde. Ou au contraire aucune les neuf autres nuits, ce qui ferait du 10/11
une nuit à part. Le dossier aligne les deux séries ; il ne dit pas laquelle des deux lectures est la
bonne.

**La rétention.** `Perf` est gardé 30 jours au banc (`infra/terraform/config.yaml:114`,
`log_retention_days: 30`). `N` ne peut pas dépasser la rétention du workspace : le dossier lit ce qui
reste, et dit la fenêtre réellement couverte.

### 3.5 F4 — Les connexions acceptées, et les portes du plan de contrôle

| Fait | Ce qu'il dit | Source, lecture | Auteur | État |
|---|---|---|---|---|
| **F4a** `ssh_accepted` | les lignes `Accepted …` de sshd sur la VM de `T − 24 h` à `T`, quelle que soit l'adresse : leur nombre, les comptes, les adresses (au plus 10, le reste compté) | `Syslog` : les filtres de `_IQ_SUCCESS_AUTH` (`agent.py:555` : `Facility == "auth"`, `ProcessName in ("sshd", "sshd-session")`, `SyslogMessage startswith "Accepted "`), sans le filtre d'adresse, sur une fenêtre absolue | **invité, forgeable** | le filtre est celui d'`investigate`, déjà en service ; la fenêtre de 24 h **à mesurer** (DH8) |
| **F4b** `ssh_failed` | les échecs de connexion de la même fenêtre, et sur `N` jours : leur nombre, le nombre de sources | `Syslog`, les filtres de la règle `ssh-brute-force` (`detection_rules.yaml:104`) | invité, forgeable | lu par la règle |
| **F4c** `model_saw_auth` | quand `investigate` a lancé `successful_auth_from_ip` (un brute force), les lignes que le modèle a vues | `raw_signal.investigative_context` du cycle : repris, sans relecture | glorfindel | lu (local) |
| **F4d** `control_plane_doors` | qui a agi sur la VM par le plan de contrôle (une Run Command, une extension, VMAccess, la console série…) et s'il garde ses droits | **les faits de la porte de LEV2** (`~/.glorfindel/door/<vm>-<h8>.json`, `glorfindel/door_facts.py`), repris tels quels, avec leur heure de lecture | plateforme | lu par LEV2 ; ses hypothèses (H1, H2, H7, H9, H12 de LEV2) restent ouvertes |

**« Réutilise-le pour la carte »** (la fiche). Le dossier réutilise ce qu'`investigate` a lu (F4c) et
les filtres de sa requête (F4a). Il ne réutilise pas l'appel lui-même : sur le signal de bree, il n'a
pas eu lieu (§1.3). Sa fenêtre (`ago(5m)`) est aussi trop courte pour la question de l'humain : « quelqu'un
est-il entré avant ? ».

**Ce que F4 ne prouve pas.** « Aucune connexion acceptée dans le journal de l'invité » ne veut pas dire
« personne n'est entré ». Un root local efface ou n'écrit pas ses lignes ; une coquille inverse
n'en écrit aucune ; Run Command et la console série passent par le plan de contrôle (F4d). La carte dit
« aucune ligne `Accepted` dans `Syslog` », jamais « aucune connexion ». Quand la preuve par les flux
réseau existera (SEC-A3f), F4 la reprendra : une connexion établie vers le port 22 dans la fenêtre,
écrite par la plateforme.

### 3.6 F5 — L'après-coup

| Fait | Ce qu'il dit | Source | Auteur | État |
|---|---|---|---|---|
| **F5a** `own_operations` | les gestes de Glorfindel sur la VM depuis `T` : chaque écriture de règle de NSG, chaque Run Command (la coupure), leur heure de départ et de fin, leur durée, leur statut | les gestes de rôle `glorfindel` des faits de la porte (`door.py:246`, `observed_actors` : `gestures` porte `at`, `operation`, `status`) ; la durée se calcule par `operationId`, du premier `Started` au dernier état, ce que `observed_actors` ne regroupe pas encore (DOS4) | plateforme | **à mesurer** : la latence du journal (H12 de LEV2, DH1) |
| **F5b** `drain` | la coupure : demandée à quelle heure, aboutie ou non, en combien de temps ; `pending` suivie par DRN1 | l'état d'isolement (`drains_at`, écrit par `glorfindel/providers/azure/isolation.py` juste avant la Run Command de la coupure ; `drain` et `drain_ended_at`, écrits par `glorfindel/drain_watch.py`) | glorfindel | lu (local) |
| **F5c** `verification` | le verdict de `verify_action` (`agent.py:2241`), sa raison, `verified_at` | l'`outcome` du cycle | glorfindel | lu (local) |
| **F5d** `cards` | les cartes de la VM nées depuis `T` (la vérification, la coupure, une carte de SID1), leur type, leur état (acquittée ou non), leur âge | `escalations.jsonl` | glorfindel | lu (local) |

**Pourquoi F5d.** Sur bree, une carte T1651 critique est née de la seule coupure de Glorfindel. Le
dossier la range sous l'isolation qui l'a causée, avec l'heure de la coupure (F5b). Il ne la ferme pas :
le rapprochement d'une coupure lente par SID1 est un lot à part (§10). Les 35 h sans acquittement se
lisent aussi ici : l'âge de chaque carte en attente.

### 3.7 F6 — La décision telle qu'elle a été prise

Ce que le cycle sait déjà, écrit sans aucun appel, à la fin du cycle.

| Fait | Ce qu'il dit | Source | Écrit aujourd'hui ? |
|---|---|---|---|
| **F6a** `rule_margin` | la règle, son calcul (pas fin ou grossier, moyenne de deux échantillons ou échantillon seul), la valeur, le seuil dans l'unité de la règle (45 000 000 octets/s), l'écart en pourcentage | `detected_data` du signal ; la règle (`detection_rules.yaml`), son nom et l'empreinte de sa requête | la valeur oui (le signal) ; le seuil et le pas, non |
| **F6b** `gates` | le mode résolu, le seuil de confiance en vigueur, les gardes traversées, celle qui a retenu (`held_by`) | l'état du cycle | `resolved_autonomy_mode` oui ; le seuil, non |
| **F6c** `draws` | les tirages de D-1 : leur nombre requis, chacun avec son action, sa confiance, son escalade | `decision_draws` | **oui** (`agent.py:2546-2547`) |
| **F6d** `model` | le modèle de la décision (`glorfindel_model()`, `eregion_core/models.py:30`, ou `GLORFINDEL_LLM_MODEL`) | l'appel de `decide` | **non** |
| **F6e** `temperature` | la température du premier tirage : `0.0`, ou `null` quand le modèle refuse une température fixée (le cas du modèle par défaut, `claude-sonnet-5-5`, mesuré le 26/10 : `agent.py:1567-1571`) ; les tirages de confirmation, toujours à l'échantillonnage par défaut du fournisseur (`agent.py:1599-1604`) | `decision_temperature` | **oui** (`agent.py:2544`), mais `null` se lit mal : « défaut du fournisseur » doit être dit en clair, et rien ne dit la température des tirages de confirmation |
| **F6f** `version` | la version de Glorfindel en service : la référence déployée (`EREGION_REF`, `EREGION_REVISION`), sinon le commit et la version du paquet | `eregion_console/sections.py:80`, `version()`, déplacé dans un module neutre (`eregion_core/`) pour que la watch le lise sans importer la console (D1) | **non** |
| **F6g** `model_inputs` | ce que le modèle a vu de l'enquête : chaque requête d'`investigate`, son nombre de lignes, et **ce qu'elle ne pouvait pas dire** (`top_write_processes` et `backup_agent_check` sans objet sous Linux, §1.3) ; les requêtes en échec (`telemetry_gaps`) | `investigative_context`, `telemetry_gaps`, le système d'exploitation de la VM (le registre des assets) | les résultats oui ; « sans objet », non |
| **F6h** `source` | exercice ou réel (B2, `_cycle_source`, `agent.py:2344`) | le cycle | **oui** |

**La fiche dit que le cycle « ne note ni le modèle ni la température ».** Lu dans le code, c'est vrai
pour le modèle et à moitié pour la température. `decision_temperature` est écrit dès qu'une décision du
modèle a eu lieu, mais vaut `null` avec le modèle par défaut, qui refuse une température fixée : la
ligne de bree portait sans doute `null`, qui se lit comme « non noté ». DOS2 (§11) écrit, **dans la
seule ligne de debug** :
- `decision_model` : la chaîne du modèle appelé ;
- `decision_temperature` : gardé tel quel (les lecteurs existants, `scripts/llm_smoke.py:400`, le
  lisent), plus `decision_sampling` : `fixed` ou `provider_default`, et `confirming_sampling:
  provider_default` ;
- `confidence_threshold` et `decision_draws_required` : les réglages en vigueur au moment du cycle ;
- `glorfindel_version` : `{ref, revision, package}` ;
- `rule_fingerprint` : le nom de la règle et les huit premiers caractères du sha256 de sa requête.
  Une règle change d'une version à l'autre, et l'humain doit savoir laquelle a tiré.

**Jamais dans la mémoire.** Le `cycle` que `store_cycle` écrit dans ChromaDB (`agent.py:2375-2396`) ne
change pas : la mémoire nourrit `past_cycles`, donc le message au modèle. Un test fige les clés de ce
dict.

### 3.8 Les faits écartés, et pourquoi

- **Les processus qui écrivent, sous Linux.** Ce compteur n'existe pas sous Linux (§1.3). Le lire
  autrement (auditd, `/proc` par Run Command) demanderait une collecte nouvelle, ou une commande root
  sur une VM isolée : le dossier ne lance jamais de Run Command. Il dit « sans objet ».
- **Le planning de la sauvegarde** (la politique du coffre). F3b dit mieux la même chose, par les jobs
  réellement joués, et sans lecture de plus.
- **Les événements planifiés d'IMDS** (`/metadata/scheduledevents`). Ils ne se lisent que depuis
  l'invité, donc par Run Command : écarté pour la même raison.
- **Les métriques de l'hôte sur une règle qui ne lit pas `Perf`.** Une ligne de `Syslog` n'a pas
  d'équivalent à l'hôte. Sa preuve, c'est la corroboration (SEC-A3).
- **Un résumé rédigé par un modèle.** L'IA d'analyse (IA0) pourrait résumer le dossier. Ce serait un
  texte d'un modèle sur la carte d'un incident, hors de ce lot ; la phrase de chaque fait reste
  composée par le code.

### 3.9 La table d'ensemble

| Fait | Source | Droit | Auteur | Mesuré ? |
|---|---|---|---|---|
| F1a job du coffre | `backupJobs` (ARM) | `Microsoft.RecoveryServices/vaults/backupJobs/read` (Reader, tenu : `snapshot`, REC1) | plateforme | lecteurs en service (`backup.py`, `recovery.py`) ; job planifié sur N jours à mesurer (DH2) |
| F1b extensions | vue d'instance ; journal d'activité | `virtualMachines/instanceView/read`, `Microsoft.Insights/eventtypes/values/read` (Reader, tenus : REC1, LEV2) | l'écriture : plateforme ; l'état : invité, provocable | à mesurer (DH3) |
| F1c redémarrage | journal d'activité ; `Heartbeat` | Reader ; Log Analytics Reader (tenus) | le journal : plateforme ; le trou de `Heartbeat` : invité, provocable | `Heartbeat` en service ; journal à mesurer (DH1) |
| F1d santé, maintenance | journal d'activité (`ResourceHealth`) ; `availabilityStatuses` ; `maintenanceRedeployStatus` | Reader sur le groupe (`*/read`), jamais lu pour `availabilityStatuses`. `ServiceHealth` : un Reader d'abonnement, **non tenu**, donc sans objet | plateforme | à mesurer (DH7) |
| F1e contexte de l'invité | `Syslog` | Log Analytics Reader (tenu) | invité, forgeable | filtre à écrire ; volume à mesurer (DH8) |
| F2 métrique de l'hôte | Azure Monitor, `metrics` (ARM) | `Microsoft.Insights/metrics/read` (Reader `*/read` : tenu sur le papier, **jamais lu par Glorfindel**) | plateforme | à mesurer (DH4, DH5, DH6) |
| F2 série de l'invité | `Perf` | Log Analytics Reader (tenu) | invité | la règle en service ; la série par minute à écrire |
| F3a, F3b récurrence | `Perf` ; jobs du coffre | Log Analytics Reader ; Reader (tenus) | invité, provocable ; plateforme | à mesurer (DH9) |
| F3c cartes passées | `escalations.jsonl` | aucun (local) | glorfindel | lu |
| F4a, F4b connexions | `Syslog` | Log Analytics Reader (tenu) | invité, forgeable | filtres en service ; fenêtre à mesurer (DH8) |
| F4c ce que le modèle a vu | le cycle | aucun | glorfindel | lu |
| F4d portes du plan de contrôle | faits de LEV2 | aucun de plus (LEV2 lit sous Reader) | plateforme | hypothèses de LEV2 ouvertes |
| F5a gestes de Glorfindel | journal d'activité | Reader (tenu) | plateforme | latence à mesurer (DH1) |
| F5b–F5d coupure, vérification, cartes | état local | aucun | glorfindel | lu |
| F6 la décision | le cycle ; l'environnement | aucun | glorfindel | F6d à F6g à écrire (DOS2) |

---

## 4. Où le dossier vit, et qui le voit

### 4.1 Le fichier

`~/.glorfindel/dossier/<vm>-<h8>-<signal8>.json` : le nom de la VM et le hachage de son identifiant,
comme la porte (`door_facts._file`), plus les huit premiers caractères du `signal_id`. Un dossier par
cycle : deux isolations de la même VM ont deux dossiers. Écrit **par la watch seule**, en entier et en
mode `0600` (`response.state._atomic_write_text`, SEC13), jamais à travers un lien (SEC16). La console
et le bot le lisent, n'y écrivent jamais. Gardé 30 jours après la levée (Q7), puis retiré à la passe
suivante. Le dossier est la trace d'un incident, il ne meurt pas avec la quarantaine, à la différence
des faits de la porte.

La ligne de debug du cycle (`*_debug.jsonl`) gagne le nom du fichier du dossier (`dossier`), pas son
contenu : la ligne est écrite avant que les lectures d'Azure aient eu lieu.

### 4.2 La carte de la console

Sur la carte d'isolement (`/api/state`, `eregion_console/api.py:681-735`, à côté de `door` : un champ
`dossier`), et sur chaque carte du même cycle (la vérification, la coupure, la carte de SID1 : par le
`signal_id` et la VM) :
- **une ligne d'un coup d'œil**, composée par le code, un segment par famille, chacun avec son état. Sur
  bree, elle aurait dit : « Plateforme : sauvegarde démarrée 2 min 37 s avant le signal · Hôte : à
  comparer minute par minute (§3.3) · Récurrence : 0 sur 10 j · `Accepted` : 0 sur 24 h · Coupure :
  7 min 14 s · Cartes en attente : 3 ». Un segment illisible le dit (« Plateforme : illisible »), un
  segment pas encore réglé aussi (« Hôte : en attente, 3 min ») ;
- **le détail au dépli** : chaque fait, sa phrase, sa source, sa requête, son auteur, son état, l'heure
  de sa lecture, « à mesurer » quand il l'est ;
- tout texte venu d'Azure ou de l'invité passe par l'échappement de la console (`_attr`, #254, #257 :
  `tests/unit/test_console_escaping.py`) ;
- **aucun bouton** de plus : le dossier n'est pas une action. Les boutons de la carte restent ceux
  qu'elle a.

### 4.3 Discord

Le bot (`glorfindel/bot.py`) ajoute à l'embed d'une carte du cycle un champ **« Dossier »**. Il porte
la ligne d'un coup d'œil, puis au plus quatre lignes (les faits lus, les illisibles d'abord), dans les
1 024 caractères d'un champ (`_embed_body`, `bot.py:208`). Le texte passe par `discord_text`
(SEC6, N-09).

**Le bot ne redessine aujourd'hui une carte que si son état change** : la signature est
`status|verdict|occurrences` (`_card_signature`, `bot.py:429`). Un dossier complété après la
publication ne se verrait pas. La signature gagne donc l'étape du dossier (`0`, `1`, `2`, §4.5) :
le message est réédité à chaque étape, sans nouvelle notification (Q5).

La notification d'une action autonome (`notify_action`, `glorfindel/escalations.py:564`) part avant
le dossier ; elle gagne une ligne « dossier : sur la carte de la console ».

### 4.4 Ce que voit le modèle : rien

| Ce qui atteint le modèle | Change-t-il ? |
|---|---|
| `_build_user_message()` (`agent.py:3027`) : le signal, `past_cycles`, l'incident, l'état de la VM | **non** : le dossier n'est ni dans le signal ni dans l'incident |
| `past_cycles` (ChromaDB) | **non** : le `cycle` stocké garde ses clés (§3.7) |
| `_SYSTEM_PROMPT`, `few_shot_examples.yaml`, `_DECISION_TOOL` | **non** |

Chaque lot de code porte un test qui compose le message d'un signal fixe, avec un dossier présent, et
le compare à l'octet au message sans dossier. C'est la forme du test de LEV2
(`tests/unit/test_recovery_watch.py`). Montrer un fait du dossier au modèle (F1a, le job de
sauvegarde, serait le premier candidat) change ce qu'il voit : la règle de `CLAUDE.md` exige alors un
run de bout en bout T1486 et un autre TTP, par Jonathan. C'est Q3 et un lot conditionnel, DOS10.

### 4.5 Quand il se compose : trois étapes

| Étape | Quand | Quoi | Où | Appels |
|---|---|---|---|---|
| **0** | à la fin du cycle, dans `store_cycle`, après l'action et sa vérification | F3c, F4c, F5b, F5c, F6 : ce que le cycle sait | le fil de la VM, après l'action | **aucun** |
| **1** | à la première passe d'entretien de la watch qui suit (toutes les ~60 s, `glorfindel/cli.py:1414-1428`), dans **son propre fil** (`dossier`), une passe à la fois | F1, F2, F3a, F3b, F4a, F4b, F4d | hors du fil de la VM, hors de son verrou, hors de la file de décision | §7 |
| **1 bis** | relu à `T + 5`, `T + 15` et `T + 30 min`, pour les seuls faits `en_attente` | les faits dont la source n'avait pas encore livré | le même fil | les seuls faits à relire |
| **2** | quand la coupure est réglée (aboutie, refusée, ou à `DRAIN_DEADLINE_S`, 30 min, DRN1), et à chaque carte nouvelle de la VM | F5a, F5b, F5d | le même fil | une lecture du journal |

Le dossier est « réglé » quand plus aucun fait n'est `en_attente`, ou à `T + 30 min` : ce qui reste en
attente devient alors `illisible`, avec la raison « la source n'a rien livré en 30 min ». Ces délais
sont des hypothèses (DH1, DH4) : ils se règlent sur la mesure.

### 4.6 Le périmètre

La conception recommande (Q2) un dossier pour :
- toute isolation exécutée (autonome, ou approuvée par un humain) ;
- toute carte d'un cycle du plan de données qui **propose** `isolate_vm` ou `block_suspicious_ip`
  sans l'exécuter (retenue par le mode, la confiance, D-1, une garde). C'est là que l'humain doit
  trancher, et c'est là que le dossier lui sert le plus.

Pas pour un cycle du plan de contrôle ou d'identité (AL1, C2) : décidés par le code, leurs faits sont
déjà sur la carte. Ni pour un instantané seul. Un exercice (B2) a son dossier, marqué exercice.

---

## 5. La question de la garde (Q1, pour Jonathan)

Le dossier sert-il seulement au jugement, ou certains faits deviennent-ils une garde ?

### 5.1 La leçon du projet

**La sûreté ne se délègue jamais à la confiance du modèle.** Elle se juge par l'action, l'asset, le mode
et l'alerte. Sur bree :
- **l'action**, `isolate_vm`, est réversible ;
- **l'asset** est une VM du banc ;
- **le mode** est `non_disruptive`, choisi par Jonathan le 01/11 pour mesurer la part contenue seule ;
- **l'alerte**, elle, a manqué : trois cartes, 35 h sans acquittement.

Le coût réel de la nuit, c'est une isolation de 35 h sur une VM du banc que personne n'a regardée. La
v0.5.8 l'a en plus déclarée non vérifiée (DRN1 le corrige depuis la v0.5.9). Une garde ne règle pas
la part de l'alerte. La boucle humaine est une question à part (Q4).

### 5.2 Les options pesées

**A. Le dossier pour le jugement seul, en v1 (recommandée).** Rien ne retient sur le dossier. On
mesure (§9) sur les données gardées, puis sur le trafic réel pendant quelques semaines, combien de fois
l'hôte et l'invité divergent sur un bénin et sur une attaque. La question revient avec des chiffres.

**B. Une garde de corroboration par l'hôte, sur `ransomware-disk-write` seule, après la mesure.** Une
isolation autonome sur un dépassement que la métrique de l'hôte ne corrobore pas, sur les mêmes
minutes et au-delà d'un rapport mesuré, est retenue : une carte, avec le dossier. Une métrique
illisible ou en retard : une carte (A0).

**C. Une garde de contexte : un job de sauvegarde en cours retient l'isolation (déconseillée).**

| | Gain | Risque | Latence de la contention | Ce que les gardes existantes font déjà |
|---|---|---|---|---|
| **A** | l'humain juge en une minute au lieu d'une enquête d'une heure ; aucun risque nouveau | bree se répète : une isolation réversible à tort, jusqu'à ce qu'un humain lève | **aucune** | D-1, la confiance et le garde-fou du signal ont laissé passer bree. Aucune ne lit la plateforme |
| **B** | bree n'aurait sans doute pas isolé, **si** la divergence tient sur la même minute (DH5, pas acquis : §3.3) | **un vrai rançongiciel que l'hôte voit mal** : une attaque courte (celle du banc écrit environ 50 s : `detection_rules.yaml:50-53`), lue sur une moyenne d'une minute, peut tomber sous le rapport ; une écriture absorbée par le cache de l'hôte (DH6) ; un disque que la table ne relie pas au bon point de montage | la métrique de l'hôte arrive en quelques minutes (DH4). Attendre la preuve, c'est retarder l'isolation d'une technique de `GRAVE_TTPS`, « every minute counts » (`decision_queue.py:54-55`). Ne pas l'attendre, c'est retenir sur une source absente : une carte à chaque fois | la corroboration (SEC-A3) a fait le choix d'attendre la preuve pour le brute force (Q3 de SEC-A3), sur une source **forgeable**. Ici, la source n'est pas forgeable : le gain est plus mince et le prix est le même |
| **C** | bree n'aurait pas isolé | **un trou prévisible** : l'heure de la sauvegarde est stable, nuit après nuit (F3b), et l'invité voit l'extension tourner. Un attaquant sur la VM chiffre pendant la sauvegarde, et l'isolation autonome devient une carte, à l'heure où personne ne lit | aucune (la lecture du coffre est rapide) | aucune |

### 5.3 La règle face à un pic ponctuel : ce que la garde ne règle pas

La règle `ransomware-disk-write` a tiré sur deux échantillons de 10 s dont la moyenne vaut 48,2 Mo/s
(§1.1, calculée ici sur le relevé), 7 % au-dessus de son seuil. Les échantillons d'avant ne sont pas
dans le relevé : la durée réelle du pic reste à lire (DH5). La fiche demande si la garde du point 3 règle ce cas. **Pas proprement.**
- Si la métrique de l'hôte ne fait que lisser le pic sur la minute, une garde B **déplacerait** le seuil
  de durée de la règle (20 s) vers la granularité de la métrique (60 s), sans le dire.
- La bonne réponse au pic ponctuel est dans la règle : une durée minimale, ou une somme d'octets sur
  une fenêtre, calibrée sur les attaques mesurées (`detection_rules.yaml:35-53`). C'est le lot à part
  que la fiche nomme (§10). Le dossier lui apporte ses données : F3a et F3b disent combien de fois,
  par nuit et par point de montage, un pic court revient.

### 5.4 Ce que la conception recommande

L'option A. Les raisons :
- la seule garde qui aurait arrêté bree (B) repose sur une divergence **pas encore établie** une fois
  les deux chiffres comparés sur la même minute ;
- elle risquerait de retenir l'attaque de référence du banc ;
- elle ajouterait des minutes à la contention d'une technique grave.

C est déconseillée pour le trou qu'elle ouvre ; c'est Jonathan qui l'écarte ou non (Q1). Si la mesure de DH5 et DH6 montre une divergence franche et
stable, sur des bénins réels comme sur les attaques du banc, B se rouvre comme un lot à part, DOS9 :
la forme de SEC-A3, la métrique attendue au plus quelques minutes, une carte sinon. Jonathan tranche
alors sur des chiffres.

---

## 6. Les identités et les droits

**Qui lit.** La watch, sous l'identité managée d'Imladris (`imladris-mi`), ou sous la paire de la
watch sur un poste (WC1). La console et le bot ne lisent que le fichier du dossier : aucun appel à
Azure, aucun droit de plus pour leurs paires.

**Ce qu'elle tient** ([`identites.md`](identites.md), §3.1) : `Reader` sur le groupe du banc, où sont la
VM, ses disques et le coffre ; `Log Analytics Reader` sur le workspace ; Response et Session Drain, que
le dossier n'utilise pas.

| Lecture | Action | Sous quel rôle | Déjà lue par Glorfindel ? |
|---|---|---|---|
| journal d'activité (REST d'ARM) | `Microsoft.Insights/eventtypes/values/read` | Reader (`*/read`) | oui : REC1, LEV2 |
| jobs du coffre | `Microsoft.RecoveryServices/vaults/backupJobs/read` | Reader | oui : REC1 |
| vue d'instance, extensions | `Microsoft.Compute/virtualMachines/instanceView/read`, `.../extensions/read` | Reader | oui : REC1 |
| métriques de l'hôte | `Microsoft.Insights/metrics/read` | Reader (`*/read`) | **non** : tenu sur le papier, à mesurer (DH4) |
| santé de la ressource | `Microsoft.ResourceHealth/availabilityStatuses/read` ; le journal d'activité de la VM, catégorie `ResourceHealth` | Reader (`*/read`) sur le groupe | **non** pour `availabilityStatuses` : à mesurer (DH7) |
| événements `ServiceHealth` | `Microsoft.Insights/eventtypes/values/read` **sur l'abonnement** | un Reader d'abonnement : **non tenu** | sans objet : F1d le dit, aucun droit n'est demandé |
| `Perf`, `Syslog`, `Heartbeat` | la lecture du workspace | Log Analytics Reader | oui : le RulePoller, `investigate` |

**Rien de nouveau.** Aucune identité, aucune attribution, aucun rôle n'est ajouté : `ServiceHealth`,
qui demanderait un Reader sur l'abonnement, reste sans objet plutôt que de l'exiger ; aucune déclaration
de Terraform ni d'environnement ne change. `scripts/identity_map.py check` passe donc tel quel : le lot
de conception ne touche aucun de ses fichiers. Une lecture refusée (403) par un Reader plus étroit chez
un client est un fait `illisible`, avec la raison « droit absent », jamais un échec du cycle.

**Le coffre ailleurs.** Chez un client, le coffre peut vivre dans un autre groupe que la VM. Imladris
n'y a Reader que si on le lui donne. Sans lui, F1a et F3b sont illisibles et le disent. La conception
n'ajoute pas ce droit : il appartient au geste d'inscription du client (`docs/operations.md`,
« Identités Azure »).

---

## 7. Le coût et les bornes

**Par dossier (étape 1)**, estimé, à mesurer :

| Lecture | Appels | Borne |
|---|---|---|
| journal d'activité de la VM (F1b, F1c, F1d, F5a) | 1 lecture exacte + 1 lecture du groupe filtrée (celle de LEV2, partagée quand elle a eu lieu dans la minute) | `ACTIVITY_PAGES` (20) pages chacune ; fenêtre `T − 30 min` → `T + 30 min` |
| jobs du coffre (F1a, F3b) | 1 liste, filtrée sur la VM et la fenêtre de `N` jours | les pages d'ARM, bornées comme REC1 |
| vue d'instance (F1b) | 1 | — |
| métriques de l'hôte (F2) | 1 (plusieurs métriques en un appel, `PT1M`) | fenêtre de 7 min |
| santé de la ressource (F1d) | 1 | — |
| `Perf` : la série par minute (F2) | 1 KQL | 7 min, une VM |
| `Perf` : la récurrence (F3a, F3b) | 1 KQL | `N` jours, une VM : ~86 400 échantillons par jour et par volume à 10 s (DH9) |
| `Syslog` : contexte, connexions (F1e, F4a, F4b) | 2 KQL | 24 h et `N` jours, une VM ; au plus 10 lignes rendues par fait, le reste compté |

Soit environ **6 appels à ARM et 4 requêtes KQL** par dossier. Les relectures (étape 1 bis) ne
reprennent que les faits en attente, trois fois au plus : **au pire une quarantaine d'appels** par
isolation, étalés sur 30 min.

**Les bornes.**
- Un fil, une passe à la fois, comme la porte de LEV2 (`cli.py:1084-1096`). Les lectures d'un dossier
  se font l'une après l'autre : le dossier ne dispute jamais au RulePoller la concurrence de l'API de
  Log Analytics.
- Chaque appel REST porte `REST_TIMEOUT_S` (`glorfindel/providers/azure/sdk.py`) ; chaque requête KQL,
  une fenêtre absolue.
- **Un plafond** : au plus 6 dossiers composés par heure pour toute la watch (`GLORFINDEL_DOSSIER_MAX_PER_H`,
  0 l'éteint). La valeur est une proposition, à trancher par Jonathan (Q9). Au-delà, un dossier `non composé : plafond atteint`, dit sur la carte, jamais en
  silence. Une rafale d'isolations (une campagne) ne se paie pas en appels.
- **La file de décision (SEC-A2)** n'est pas touchée : le dossier n'appelle jamais le modèle, n'entre pas
  dans `MODEL_CALLS_PER_MIN`, et ne tient jamais le verrou de la VM. Une détection suivante de la VM
  n'attend pas le dossier.
- **La contention** ne paie rien : l'étape 0 se fait après l'action et sa vérification, sans appel ;
  les étapes 1 et 2, dans un autre fil.

**Le prix en argent.** Les lectures d'ARM sont gratuites. Les requêtes KQL sur un workspace en
facturation à l'ingestion ne coûtent rien de plus. À vérifier sur un workspace en tables `Basic` ou
`Auxiliary`, où la requête se paie : pas le cas du banc.

---

## 8. Le modèle de menace

| Frontière | Ce qui la tient | Ce qui reste ouvert |
|---|---|---|
| **un fait de l'invité trompe l'humain** (une ligne `Syslog` écrite pour faire croire à un `apt` ou à une absence de connexion) | l'auteur dit sur chaque fait, « forgeable » sur `Syslog` ; F4 dit « aucune ligne », jamais « aucune connexion » | l'humain peut quand même s'y fier : c'est le prix d'un fait dit plutôt que tu |
| **un fait provoqué par l'invité passe pour une explication bénigne** : un root local arrête l'agent (un trou de `Heartbeat`, lu comme un redémarrage, `agent.py:705-707`), ou fait écrire à l'agent l'état d'une extension | ces faits portent l'auteur `invité` et `provocable` ; la carte dit « dit par l'invité », et la ligne d'un coup d'œil ne les range jamais sous « Plateforme » | le même prix : un fait dit, que l'humain pèse |
| **un fait vrai de la plateforme, à une heure prévisible, pousse l'humain à juger bénin** : le job de sauvegarde (F1a) ne se forge pas, mais son heure est stable nuit après nuit (F3b), et un attaquant peut chiffrer à cette heure-là (l'argument de l'option C, §5.2) | la carte dit, à côté de F1a : « l'heure de la sauvegarde est prévisible : une attaque peut s'y caler » ; aucun verdict | l'humain peut conclure trop vite ; F2 et F4d sont là pour le contredire |
| **le dossier pousse l'humain à lever à tort** (un « tout semble bénin » qui n'est que l'absence de preuve) | aucun verdict ; les illisibles en tête ; F4d (la porte de LEV2) toujours présent ; la levée garde ses propres règles (REC1, LEV3) | un humain pressé lit la ligne d'un coup d'œil. Q4 (le rappel) ne doit pas devenir « lever en un clic » |
| **un fichier du dossier forgé** (`~/.glorfindel/` s'écrit aussi depuis la console et le bot) | le dossier n'est lu par aucune garde, aucun modèle, aucune levée ; la console et le bot le lisent comme une information | un conteneur de la console compromis peut mentir à l'humain sur la carte. C'est la même frontière que les faits de la porte de LEV2 (§2 du modèle de menace, `runs/` et l'état) |
| **un texte d'Azure ou de l'invité dans la console ou sur Discord** | `_attr` (#254, #257), `discord_text` (SEC6, N-09) | — |
| **une lecture fait taire une source** (un 403, une page coupée lus comme « rien ») | `illisible` avec sa raison ; le test de LEV2 étendu à chaque lecture du dossier | — |
| **le dossier devient une garde sans le dire** | Q1 ; un test : aucune garde de `decide` n'importe `glorfindel.dossier` | — |

---

## 9. Ce qui n'est pas mesuré

Chaque fait nouveau, avec sa forme réelle, est à prouver au banc avant d'être cru. Aucune mesure n'est
faite par ce lot.

| N° | Hypothèse | Ce qui la mesure | Si elle tombe |
|---|---|---|---|
| **DH1** | le journal d'activité livre les écritures et les Run Commands d'une VM en quelques minutes (la documentation ; H12 de LEV2, non mesurée) | les heures `eventTimestamp` et `submissionTimestamp` des gestes de la coupure de bree, lus après coup | les délais de l'étape 1 bis s'allongent ; F5a reste `en_attente` plus longtemps |
| **DH2** | un job `Backup` **planifié** se lit comme celui d'un instantané à la demande, que `backup.py:160-187` lit déjà (`operation`, `entity_friendly_name`, `start_time`), et la liste du coffre se filtre sur `N` jours sans couper | la liste des jobs du coffre sur bree, du 01/11 au 11/11 | F1a et F3b changent de filtre, ou `N` baisse |
| **DH3** | la vue d'instance porte l'état de `VMSnapshotLinux` pendant une sauvegarde | une lecture de la vue d'instance pendant une sauvegarde à la demande (un geste de Jonathan) | F1b se réduit au journal d'activité |
| **DH4** | les métriques `OS Disk Write Bytes/sec`, `Data Disk Write Bytes/sec` et `Disk Write Bytes` d'une VM se lisent sous Reader, à `PT1M`, avec `Average` (et `Maximum` ?), avec quelques minutes de latence | une lecture des métriques de bree sur la nuit du 10/11 (gardées 93 jours, la documentation) | F2 est illisible ; Q1, option B, tombe |
| **DH5** | **sur la même minute**, la moyenne de l'invité et celle de l'hôte divergent nettement pendant le pic de bree | la série `Perf` de bree, `bin(1m)`, de 02:28 à 02:38 le 10/11, face à DH4 ; le lien entre `/` et le disque OS | si elles ne divergent pas, F2 ne dit que la durée du pic, et B n'a plus d'objet |
| **DH6** | sur une attaque T1486 du banc (environ 50 s d'écritures), l'hôte voit autant que l'invité sur la même minute ; le cache de l'hôte (disque OS en `ReadWrite`) n'absorbe pas les écritures | le dernier T1486 du banc (09/11), même lecture | si l'hôte voit moins, B retiendrait la vraie attaque : B tombe |
| **DH7** | les événements `ResourceHealth` d'une VM arrivent dans la lecture exacte de la VM au journal d'activité ; `availabilityStatuses` et `instanceView.maintenanceRedeployStatus` se lisent sous le Reader du groupe ; `ServiceHealth` ne s'y lit pas (la documentation d'Azure le place au niveau de l'abonnement : à confirmer, sans le lire au niveau de l'abonnement) | une lecture sur bree et gondolin, sur 30 jours | F1d se réduit à ce qui se lit ; si `ServiceHealth` se lisait sous le groupe, il entrerait dans F1d sans droit nouveau |
| **DH8** | les lignes `Accepted` et `Failed` d'une VM exposée tiennent en une requête bornée sur 24 h et sur `N` jours | le volume de `Syslog` `auth` de bree sur 10 jours (298 échecs, 41 sources) | les bornes de F4 changent |
| **DH9** | la requête de récurrence sur `N` jours d'échantillons à 10 s, pour une VM, rend en quelques secondes | la requête rejouée sur bree, `N` = 10 et 30 | `N` baisse, ou F3a passe en agrégats précalculés |
| **DH10** | la sauvegarde du coffre apparaît parmi les acteurs de la porte de LEV2 (une écriture d'extension par le service de sauvegarde) | les faits de la porte d'une VM isolée pendant une sauvegarde | à dire à LEV3, pour « qui n'est pas un tiers » |
| **DH11** | la coupure attend derrière l'extension de sauvegarde (une Run Command après l'autre) | le journal d'activité de bree, 02:33–02:44 le 10/11 | F5a le dit autrement ; DRN1 et SID1 en tirent leurs délais |
| **DH12** | une lecture complète du dossier tient sous une minute | l'étape 1 jouée sur bree par la commande à la demande (DOS4 : `glorfindel dossier <vm> --at <T>`), sans rien écrire | les bornes du §7 changent |

### 9.1 Ce qui se mesure déjà, sur les données gardées

DH1, DH2, DH4, DH5, DH6, DH8, DH9 et DH11 se mesurent **en lecture seule, sur les données déjà
gardées**, sans attaque ni panne : la nuit du 10/11 sur bree, le T1486 du 09/11. **La rétention de
`Perf` et de `Syslog` au banc est de 30 jours** : les échantillons du 10/11 disparaissent vers le
10/12. Les métriques de l'hôte et le journal d'activité restent 90 jours environ (la documentation).
DH5 et DH6 décident Q1 : c'est la mesure à faire en premier (Q8). Le protocole sera
`docs/banc-dos.md` (DOS8) : les requêtes exactes, que Jonathan lance depuis le poste ; rien n'écrit
sur Azure.

DH3 et DH10 demandent une sauvegarde à la demande d'une VM du banc. C'est un geste non destructif, mais
il reste un geste de Jonathan.

---

## 10. Ce qui va ailleurs

Cité ici, fait ailleurs, chacun dans son lot :
- **La carte TTL qui dit « levée à l'expiration »** alors que rien n'est levé : un bug de texte.
- **Le rapprochement par SID1 d'une coupure lente** : la carte T1651 née de la coupure de bree (la
  fenêtre `DRAIN_BEFORE_S`/`DRAIN_AFTER_S`, `glorfindel/providers/azure/own_run_command.py:57-58`).
  Le dossier range la carte sous l'isolation (F5d), il ne la ferme pas.
- **La règle `ransomware-disk-write` face à un pic ponctuel de l'invité** : une durée minimale ou une
  somme d'octets (§5.3). La garde ne la règle pas ; F3 lui donne ses données.
- **L'indicateur des actions disruptives à tort**, qui passe à 1 (`docs/proofs.json`).
- **La boucle humaine**, 35 h sans acquittement : Q4.
- **Les requêtes d'`investigate` sans objet sous Linux** (`top_write_processes`,
  `backup_agent_check`, §1.3) : les compter comme un trou de télémétrie retiendrait toute isolation
  autonome d'un T1486 sous Linux. Les remplacer change ce que voit le modèle (DOS10, Q3). Le dossier
  se contente de le dire (F6g).

---

## 11. Les lots de code proposés

Dans l'ordre. Les mutants sont comptés ; l'Orchestre donne les plages.

| Lot | Session | Contenu | Ce qu'il prouve au banc | Mutants |
|---|---|---|---|---|
| **DOS2** — la décision notée | Glorfindel | la ligne de debug gagne `decision_model`, `decision_sampling`, `confirming_sampling`, `confidence_threshold`, `decision_draws_required`, `glorfindel_version`, `rule_fingerprint` (§3.7). `version()` passe de `eregion_console/sections.py` à `eregion_core/` (la console l'importe de là, D1). Le `cycle` de la mémoire et le message au modèle sont figés par un test | rien à jouer : la ligne du prochain cycle d'Imladris se lit | **3** : le modèle absent de la ligne ; la version absente ; un champ nouveau qui fuit dans le `cycle` de la mémoire |
| **DOS3** — le dossier, étape 0, et son fichier | Glorfindel | `glorfindel/dossier.py`, un module neutre : la forme d'un fait (§3.1), les faits locaux F3c, F4c, F5b, F5c, F6 (avec « sans objet » sous Linux), le fichier de la watch (§4.1), écrit en fin de `store_cycle` pour le périmètre retenu (Q2), la rétention (Q7) ; aucune garde n'importe le module (un test) | rien à jouer | **4** : un illisible écrit vide ; le dossier dans le signal ; un cycle hors périmètre composé ; le fichier écrit à travers un lien |
| **DOS4** — les lectures d'Azure | Glorfindel | `glorfindel/providers/azure/dossier_reads.py` : le journal d'activité de la fenêtre (le lecteur de `door.py`, la durée par `operationId`), les jobs du coffre (celui de `recovery.py`), la vue d'instance, les métriques de l'hôte (REST d'ARM, `metrics`, `PT1M`), la santé de la ressource ; chaque lecture bornée, illisible jamais vide. Le fil `dossier` de la watch (étapes 1, 1 bis, 2), le plafond. Le faux Azure gagne les jobs `Backup`, les métriques, les événements de santé. `glorfindel dossier <vm> --at <T> [--json]` : la même lecture, sans rien écrire | DH1, DH2, DH4, DH7, DH12 par la commande à la demande, sur bree | **6** : une lecture en échec rendue vide (une par source, quatre) ; la borne de pages retirée ; la fenêtre ancrée sur la lecture au lieu du signal |
| **DOS5** — les faits de KQL | Glorfindel | la série de l'invité par minute et son rapport à l'hôte (F2), la récurrence et son croisement avec les sauvegardes (F3a, F3b), le contexte de l'invité (F1e), les connexions (F4a, F4b) ; fenêtres absolues, littéraux vérifiés (SEC4c), lignes bornées | DH5, DH6, DH8, DH9 sur les données gardées | **5** : la série de l'invité comparée au pic plutôt qu'à la minute ; le filtre `startswith "Accepted "` relâché ; une valeur de la ligne hors de son littéral ; la récurrence sur toutes les VM ; « forgeable » retiré de `Syslog` |
| **DOS6** — la section de la console | Console | le champ `dossier` de `/api/state` et des cartes du cycle ; la ligne d'un coup d'œil, le détail au dépli, l'état de chaque fait, « à mesurer » ; l'échappement | une capture de la carte de bree rejouée sur le jeu d'exemple | **3** : un texte d'Azure non échappé ; un illisible affiché comme vide ; la carte qui casse sur un dossier absent |
| **DOS7** — le champ de Discord | Glorfindel (bot) | le champ « Dossier » ≤ 1 024 caractères, les illisibles d'abord ; l'étape du dossier dans `_card_signature` ; la ligne de `notify_action` | le message d'une carte réédité à l'étape 1, sur le banc | **2** : l'étape absente de la signature ; le champ au-delà de 1 024 caractères |
| **DOS8** — la mesure | Tests, gestes de Jonathan | `docs/banc-dos.md` : les requêtes de DH1 à DH12, d'abord sur les données gardées (§9.1), puis une sauvegarde à la demande pour DH3 et DH10 ; les résultats reportés au §9 | DH1 à DH12 | **0** |
| **DOS9** — la garde de l'hôte (si Q1 = B, après DOS8) | Glorfindel | un verdict de corroboration par l'hôte dans `GlorfindelState`, une garde de `decide` sur `ransomware-disk-write`, la forme de SEC-A3 | la vraie attaque du banc isole toujours ; le pic de bree rejoué ne l'aurait pas fait | **4** (estimés) |
| **DOS10** — le contexte de la plateforme au modèle (si Q3 le retient) | Glorfindel | F1a (et « sans objet » pour les requêtes Linux) dans `_build_user_message()` ; **run de bout en bout T1486 et un autre TTP, par Jonathan** | le run lui-même | **2** (estimés) |

**Total** : 23 mutants pour DOS2 à DOS7 ; 6 de plus si DOS9 et DOS10 partent.

**L'ordre.** DOS2 et DOS3 ne lisent pas Azure : ils partent dès les réponses à Q2 et Q7. DOS8 se fait
**en même temps**, sur les données gardées, avant le 10/12. DOS4 et DOS5 attendent la mesure de DH1,
DH2, DH4 et DH5 : ils codent la forme mesurée, pas celle de la documentation. DOS6 et DOS7 suivent
DOS3 (le fichier existe, même en étape 0).

---

## 12. Les questions à Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est
décidé à sa place.

**Q1 — Le dossier sert-il seulement au jugement, ou certains faits deviennent-ils une garde ?** (§5)
1. **Le jugement seul en v1 ; la garde se rejuge sur la mesure de DH5 et DH6 (recommandée).** La
   divergence de l'hôte n'est pas établie sur la même minute ; une garde risquerait de retenir l'attaque
   du banc et ajouterait des minutes à la contention d'une technique grave. Le coût de bree tient d'abord
   à l'alerte (Q4).
2. Une garde de corroboration par l'hôte sur `ransomware-disk-write`, codée après la mesure (DOS9),
   quel qu'en soit le résultat. Bree n'aurait pas isolé ; la vraie attaque courte pourrait ne pas isoler
   non plus.
3. Une garde de contexte : une sauvegarde en cours retient l'isolation. Déconseillée : l'heure de la
   sauvegarde est prévisible, et un attaquant chiffre à cette heure-là.

**Q2 — Pour quels cycles composer un dossier ?** (§4.6)
1. **Toute isolation exécutée, et toute carte qui propose `isolate_vm` ou `block_suspicious_ip` sans
   l'exécuter (recommandée).** C'est sur une carte retenue que l'humain doit trancher : le dossier y
   sert le plus.
2. Les seules isolations exécutées. Le périmètre de la fiche, le moins d'appels.
3. Toute carte d'un cycle du plan de données. Le plus complet ; des dossiers pour des cartes où ils
   n'aident pas (un instantané, une ligne non caractérisée).

**Q3 — Le modèle verra-t-il un jour un fait du dossier ?** (§4.4)
1. **Jamais en v1 : le dossier est pour l'humain (recommandée).** On sépare d'abord, on mesure ; un
   ajout au message se décide ensuite, sur des faits mesurés.
2. Plus tard, par un lot à part (DOS10) : le job de sauvegarde et les requêtes sans objet sous Linux dans
   `_build_user_message()`, avec un run de bout en bout T1486 et un autre TTP, par Jonathan. Le modèle
   ne recevrait plus « aucun résultat » pour une requête qui ne peut rien dire sous Linux ; comment il a
   lu ce texte sur bree reste à vérifier dans le `reasoning` du cycle.
3. Jamais : le modèle ne voit que la détection et l'enquête, le dossier reste hors de sa portée pour de
   bon.

**Q4 — La boucle humaine : que faire quand les cartes d'une VM isolée restent sans réponse ?** (35 h
sur bree)
1. **Un rappel sur Discord, dans le fil de la VM, pour une carte en attente sur une VM isolée : à 4 h,
   puis toutes les 12 h, avec la ligne du dossier (recommandée).** La VM isolée est l'état qui coûte ;
   un rappel ciblé ne noie pas le canal. Un lot à part, du bot.
2. Un récapitulatif quotidien de ce qui attend, à heure fixe. Moins de bruit, mais une isolation de la
   nuit attend jusqu'au matin.
3. Rien de neuf : le résumé du lundi (`_post_weekly`) et le tableau de #agents suffisent.

**Q5 — Sur Discord, comment le dossier arrive-t-il ?** (§4.3)
1. **Le champ « Dossier » de l'embed, réédité à chaque étape, sans nouvelle notification
   (recommandée).** Un seul message à lire, à jour ; le canal ne s'allonge pas.
2. Un message dans le fil de la VM quand le dossier est réglé. Il notifie, et il se lit à part de la
   carte.
3. La console seule. Discord dit déjà la carte ; le dossier y serait trop long.

**Q6 — Sur combien de jours lire la récurrence (`N`) ?** (§3.4)
1. **10 jours (recommandée).** C'est la fenêtre que Jonathan a lue à la main. Elle couvre plus d'une
   semaine de sauvegardes nocturnes, pour un coût de requête à mesurer (DH9).
2. 30 jours, toute la rétention du banc. Plus de nuits, une requête plus lourde, et rien au-delà de la
   rétention d'un client.
3. 7 jours. La requête la plus légère, une semaine de sauvegardes tout juste.

**Q7 — Combien de temps garder un dossier ?** (§4.1)
1. **30 jours après la levée (recommandée).** C'est l'âge de la preuve de la feuille de route
   (« dernière preuve < 30 jours »), et la rétention de `Perf` au banc : au-delà, le dossier ne se
   relit plus.
2. Jusqu'à la levée, comme les faits de la porte de LEV2. Le moins de fichiers ; l'histoire de
   l'incident perdue à la levée.
3. 90 jours, la rétention du journal d'activité. Plus d'histoire, plus de fichiers sur Imladris.

**Q8 — Dans quel ordre ?** (§11)
1. **La mesure sur les données gardées (DOS8) en même temps que DOS2 et DOS3, qui ne lisent pas Azure ;
   DOS4 et DOS5 après la mesure (recommandée).** Les échantillons du 10/11 disparaissent vers le 10/12 ;
   le code d'Azure suit la forme mesurée.
2. Tout après la mesure. Le plus prudent ; la ligne de debug (DOS2) attend sans raison.
3. Tout le code d'abord, la mesure ensuite. Le plus rapide à livrer ; les données de bree risquent de
   partir avant d'être lues, et le code d'Azure suit la documentation.

**Q9 — Le plafond de dossiers par heure, pour toute la watch ?** (§7)
1. **6 par heure (recommandée).** Une isolation réelle est rare ; une rafale (une campagne d'exercices)
   ne se paie pas en appels, et chaque dossier non composé est dit sur sa carte.
2. 20 par heure. Une campagne garde tous ses dossiers ; au pire, quelques centaines d'appels de lecture
   par heure.
3. Pas de plafond, seulement le fil unique et les bornes de chaque lecture. Le plus simple ; une rafale
   se paie en appels et retarde les dossiers suivants.
