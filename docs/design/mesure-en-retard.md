# Une mesure arrivée en retard est jugée (ING1, #738) — conception

_Conception — 12/11 (ING1, #738) — statut : **conception seulement, questions ouvertes** (§12). Rien
n'est codé ni mesuré par ce lot. Jonathan a décidé le lot le 12/11 (« conception maintenant »), sur
un trou de détection mesuré au banc. Les lots de code (§11) attendent ses réponses ; chaque retard
d'une source reste à mesurer avant d'être cru (§10)._

**Lié** : [`levee-probation.md`](levee-probation.md) (LEV1 : la levée, la probation, la borne de la
fin du restore) ; [`dossier-isolation.md`](dossier-isolation.md) (DOS1 : le dossier d'une isolation,
ses faits, son après-coup) ; [`docs/glorfindel.md`](../glorfindel.md) (le RulePoller, sa fenêtre et
sa déduplication ; la file de décision, SEC-A2) ; [`modele-de-menace.md`](modele-de-menace.md).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne
(au commit `97c0ef68`). Ce qui est dit d'Azure vient de la documentation publique de Microsoft ou
d'une mesure faite au banc, et le dit. Tout le reste est une **hypothèse**, numérotée RH1 à RH12
(§10). Les chiffres du 11/11 sont ceux du relevé de la session Tests avec Jonathan (fiche du lot, en
lecture seule, heures des sources) ; ce document les reprend sans les avoir relus.

---

## 0. En bref

- **Le trou.** Une règle livrée choisit ses lignes par leur heure (`TimeGenerated > ago(10m)`), et le
  RulePoller borne la requête à cette fenêtre plus 5 minutes (`detection_rules.py:1640-1645`). Une
  ligne qui arrive plus de 10 minutes après son heure n'est **jamais jugée**. Le 11/11, après la levée
  de bree, les mesures `Perf` sont arrivées d'un bloc, jusqu'à 26 min 50 s après leur heure : les
  échantillons de 15:56 à 16:06, au-dessus du seuil, n'ont été dans aucune fenêtre. La détection n'a
  eu lieu que parce que l'écriture durait encore après 16:07.
- **Le mécanisme recommandé : jugée à l'arrivée, agrégée à l'heure.** Une ligne est jugée pendant
  les 10 minutes qui suivent son **arrivée** (`ingestion_time()`, écrite par la plateforme), quelle
  que soit son heure, jusqu'à un **horizon de retard** déclaré par la règle (`late_s`, 2 h proposées,
  Q2). Ce qui s'agrège (la paire d'échantillons, les dix échecs, une moyenne) se calcule toujours sur
  `TimeGenerated`, lu sur tout l'horizon : le seuil garde son sens. Un agrégat est jugé à l'arrivée
  de sa **dernière** ligne.
- **La déduplication tient** (§4). Une ligne d'événement garde son identité (son heure et son texte)
  pendant toute la fenêtre, horizon compris : elle ne revient jamais. Une ligne agrégée (qui, où)
  garde l'expiration d'aujourd'hui, la fenêtre de sélection plus 5 minutes : une nouvelle rafale sur
  la même VM après une levée refait une carte.
- **Le coût** : aucune requête de plus par passe ; le serveur lit treize fois plus de lignes pour les
  règles à 10 minutes (130 min au lieu de 10 ; ×25 pour `data-exfiltration-blob`, dont la fenêtre est
  de 5 min), et en rend autant qu'avant. Les plafonds de SEC2 et de
  SEC-A2 ne bougent pas. Une seule requête de plus, toutes les 5 minutes, pour voir le retard (§8).
- **Ce que voit le modèle** : rien de neuf dans sa forme. Les colonnes rendues par chaque règle restent
  les mêmes ; les heures du retard sont retirées de la ligne avant le signal et gardées à côté. Ce qui
  change, c'est quelles lignes deviennent des détections.
- **Ce que LEV3 et LEV4 doivent en tirer** (§7), **si la quarantaine retient la télémétrie de
  l'invité** (l'hypothèse RH5, avec RH3 ; non acquise : `Heartbeat` est peut-être passé) : elle arrive
  alors après la levée, en retard. Le cas 2 de LEV (une détection entre la fin du restore et la levée)
  ne pourrait pas venir de `Perf` ni de `Syslog`. La réisolation de la probation ne voit ces lignes
  qu'avec ce mécanisme, et une levée humaine tardive demande une relecture de rattrapage, à bornes
  absolues.
- **Le retard lui-même se voit** (§8) : un état par VM et par table ; une carte seulement quand des
  lignes arrivent au-delà de l'horizon (jamais jugées, une carte par passage dans cet état), ou quand
  une table **à cadence** (`Perf`) se tait alors que `Heartbeat` arrive ; un fait du dossier de DOS1 et
  de la probation.
- **Six lots de code** (§11), ING2 à ING7, dont un de mesure et un conditionnel. **Dix questions**
  pour Jonathan (§12).

---

## 1. Le cas qui fonde le lot : la levée de bree, le 11/11

### 1.1 Le relevé

Mesuré le 12/11, en lecture seule, par la session Tests avec Jonathan (heures des sources) :

- bree a été levée le 11/11 à **15:54:10**, après environ 35 à 37 h d'isolation (35 h selon la
  fiche ; l'isolement de 02:36 UTC le 10/11, `dossier-isolation.md`, §1.1, en donne environ 37 si
  15:54 est en UTC : le fuseau des « heures des sources » est à vérifier, sans effet sur la suite) ;
- les mesures `Perf` de « / », de 15:50 à 16:14, sont **toutes arrivées en un seul bloc, entre
  16:16:50 et 16:16:59**, y compris celles prises sous la quarantaine (de 15:50 à 15:54) ;
- le retard (`ingestion_time() - TimeGenerated`) décroît d'une tranche à l'autre :

  | Échantillons de | Retard | Arrivés |
  |---|---|---|
  | 15:50 | 1 503 à 1 610 s (25 à 27 min) | 16:16:50–59 |
  | 15:56 | 1 143 à 1 254 s (19 à 21 min) | 16:16:50–59 |
  | 16:06 | 544 à 652 s (9 à 11 min) | 16:16:50–59 |
  | 16:14 | 69 à 179 s | 16:16:50–59 |
  | 16:16 et après | 55 à 108 s | au fil de l'eau |

- le premier échantillon au-dessus de 50 Mo/s, à 15:56:20, est arrivé vers 16:16:53 ;
- la détection de `ransomware-disk-write` est de 16:17:18 ;
- `Heartbeat`, sur la même période, est arrivé au fil de l'eau, avec 2 à 10 s de retard : **seul `Perf`
  a été retenu**. Le relevé ne dit pas si des lignes `Heartbeat` datées d'avant 15:54:10 (sous la
  quarantaine) sont arrivées à temps : s'il y en a, l'agent passait la quarantaine (RH5) ;
- le même relevé (DOS8) a montré une écriture réelle d'environ 80 Mo/s pendant 18 minutes, que l'hôte
  voyait aussi, et dont l'auteur n'est pas identifié. **Ça ne relève pas de ce lot.**

### 1.2 Ce que le code a fait, lu dans le code

- **La fenêtre de la règle.** `ransomware-disk-write` lit `Perf | where TimeGenerated > ago(10m)`
  (`glorfindel/rules/azure/detection_rules.yaml:57`). À la passe de 16:17:18, elle ne voit que les
  échantillons datés après 16:07:18.
- **La fenêtre de l'API.** `poll_once` demande à Log Analytics la plus longue fenêtre `ago()` de la
  requête plus 5 minutes (`_query_lookback_s`, `_INGESTION_MARGIN_S` = 300 s ;
  `detection_rules.py:1057-1058`, `:1076-1081`, `:1640-1645`) : de 16:02:18 à 16:18:18. Ce `timespan`
  porte sur `TimeGenerated`. Le dépôt le sait par la mesure : le 05/10, un `timespan` de 60 s rendait
  invisible toute ligne ingérée avec plus de ~84 s de retard (`detection_rules.py:1053-1056`).
- **Donc** les échantillons de 15:56:20 à 16:07:18, arrivés à 16:16:5x avec 9 à 21 minutes de retard,
  étaient déjà hors de la fenêtre de la règle à leur arrivée, et les plus anciens (avant 16:02:18)
  hors de celle de l'API aussi. C'est l'intersection des deux qui décide. **Ils n'ont jamais été
  jugés.** La détection de
  16:17:18 s'est faite sur les échantillons de 16:07 à 16:14.
- **La déduplication** n'explique pas le trou : la ligne de la règle est agrégée
  (`summarize MaxWrite = max(Peak) by Computer, _ResourceId`, `:80`), son identité est la VM
  (`_row_identity`, `detection_rules.py:1148-1152`). Elle peut retenir une carte, jamais faire
  manquer une ligne à la requête.

### 1.3 Ce que ça veut dire

- **Une écriture de 10 minutes, de 15:56 à 16:06, n'aurait fait aucune détection.** Ce soir-là, la
  règle a tiré 21 minutes après le premier échantillon, et seulement parce que l'écriture a duré 18
  minutes.
- **Ce n'est pas un retard d'ingestion ordinaire.** Les retards de `Perf` juste après le bloc (55 à
  108 s, le 11/11 à partir de 16:16, relevés le 12/11) et ceux du 05/10 (89 à 109 s) tiennent
  largement dans la fenêtre ; le retard de `Perf` en temps normal n'est pas encore mesuré (RH1). C'est
  un bloc retenu, puis livré d'un coup, juste après une quarantaine.
- **C'est le pire moment.** Une levée ouvre la probation de LEV1 (la VM restaurée, en service sous
  surveillance renforcée). Les minutes qui arrivent en retard sont celles de la probation, et, si
  la quarantaine les retient (RH5), celles d'avant la levée : le démarrage du disque restauré, où une
  persistance se déclenche (`levee-probation.md`, §6.3).

---

## 2. L'inventaire

### 2.1 Les règles livrées

`glorfindel/rules/azure/detection_rules.yaml`, 18 règles. « Événement » : la ligne rendue porte
`TimeGenerated`, son identité est son heure et son texte (ou son événement d'audit). « Agrégat » : la
ligne rendue n'a pas d'heure, son identité est ses colonnes texte (`_row_identity`,
`detection_rules.py:1116-1152`). « Opération » : l'identité est l'opération (`CorrelationId`,
opération, ressource) ou le constat d'Entra (`EventId`).

| Règle | Table (qui la transporte) | Fenêtre | Ligne rendue | Exposition au retard |
|---|---|---|---|---|
| `ransomware-disk-write` (`:29`) | `Perf` (l'agent de la VM) | `ago(10m)` (`:57`) | agrégat (`MaxWrite` par VM) | **mesurée : trou au 11/11** |
| `data-exfiltration-blob` (`:82`) | `StorageBlobLogs` (la plateforme) | `ago(5m)` (`:94`), la plus courte | agrégat (par appelant et compte) | inconnue ; la plus courte des fenêtres |
| `ssh-brute-force` (`:104`) | `Syslog` (l'agent) | `ago(10m)` (`:117`) | agrégat (`FailedAttempts` par adresse et VM) | inconnue sous la quarantaine (RH3) |
| `sudo-privilege-escalation` (`:133`) | `Syslog` | `ago(10m)` (`:144`) | événement (une ligne par VM et texte) | idem |
| `auditd-sensitive-root-command` (`:179`) | `Syslog` local6 | `ago(10m)` (`:191`) | événement d'audit | idem |
| `t1136-001-local-account-creation-linux-v1` (`:217`) | `Syslog` | `ago(10m)` (`:231`) | événement | idem ; **la persistance du démarrage** (LEV, §6.2) |
| `t1053-003-cron-crontab-replace` (`:260`) | `Syslog` cron | `ago(10m)` (`:278`) | événement | idem |
| `t1070-002-log-tamper` (`:289`) | `Syslog` local6 | `ago(10m)` (`:316`) | événement d'audit | idem |
| `t1059-004-shell-from-world-writable` (`:371`) | `Syslog` local6 | `ago(10m)` (`:392`) | événement d'audit | idem |
| `nsg-change-outside-glorfindel` (`:440`) | `AzureActivity` (la plateforme) | `ago(1h)` (`:453`) | opération | faible si le retard documenté tient (3 à 20 min, A1) |
| `role-assignment-write` (`:488`) | `AzureActivity` | `ago(1h)` (`:501`) | opération | idem |
| `snapshot-by-unexpected-caller` (`:532`) | `AzureActivity` | `ago(1h)` (`:549`) | opération | idem |
| `restorepoint-by-unexpected-caller` (`:608`) | `AzureActivity` | `ago(1h)` (`:638`) | opération | idem |
| `run-command-by-glorfindel-outside-isolation` (`:708`) | `AzureActivity` | `ago(1h)` (`:722`) | opération | idem |
| `entra-credential-added` (`:771`) | `AuditLogs` (Entra) | `ago(1h)` (`:786`) | constat | faible si E3 tient (quelques minutes) |
| `entra-app-consent` (`:810`) | `AuditLogs` | `ago(1h)` (`:825`) | constat | idem |
| `entra-privileged-role-assigned` (`:849`) | `AuditLogs` | `ago(1h)` (`:864`) | constat | idem |
| `entra-sp-unusual-signin` (`:890`) | `AADServicePrincipalSignInLogs` | base `ago(14d) .. ago(1h)`, courante `ago(1h)` (`:907`, `:913`) | constat | **un piège** : une connexion arrivée plus d'une heure en retard tombe dans la base, et s'y rend « connue » elle-même |

Deux bornes de chargement existent déjà : une règle d'`AzureActivity` ou d'Entra dont la fenêtre est
plus courte que 30 minutes est dite au chargement (`MIN_LOOKBACK_S`,
`glorfindel/providers/azure/activity.py:60`, `glorfindel/providers/azure/entra.py:56` ;
`detection_rules.py:938-946`). Aucune borne de cette sorte pour le plan des données.

`expected_latency_s` (45 s pour `Perf`, 90 s pour `StorageBlobLogs`, 480 s pour `Syslog`, 1 200 s
pour `AzureActivity`, 1 800 s pour Entra) ne sert qu'au délai de `poll_detection` sur un
`attack_started` (`agent.py:398-401`) : le RulePoller ne le lit pas.

### 2.2 Les copies du banc

`infra/glorfindel-host/client_rules.bench.yaml` : trois copies, chacune la règle livrée plus une
exclusion, avec l'empreinte de la règle livrée entière (`base_sha256`, WL1).

| Copie | Fenêtre | Ce qui la touche ici |
|---|---|---|
| `sudo-privilege-escalation` (`:19`, `base_sha256` `:26`) | `ago(10m)` (`:31`) | **refaite par ING3** (§6) |
| `nsg-change-outside-glorfindel` (`:69`) | `ago(1h)` (`:81`) | intacte, sauf ING7 |
| `entra-sp-unusual-signin` (`:140`) | base et courante comme la livrée (`:160`, `:166`) | intacte, sauf ING7 ; le même piège |

### 2.3 Les autres lectures exposées

| Lecture | Fenêtre | Ce que le retard y fait | Ici |
|---|---|---|---|
| l'enquête d'`investigate` (`agent.py:505-590`) | `ago(5m)` à `ago(10m)`, `ago(2h)` pour `heartbeat_gap` | sur une détection faite d'un bloc en retard, elle lit les minutes d'**après** les lignes, pas celles des lignes ; le modèle le voit | **non changée** : elle touche ce que voit le modèle (Q8) ; le retard est dit au dossier (§8) |
| la corrélation de COR1 (`correlation.py:151-160`, `:293-300`, `:501-522`) | `_LOGINS` lit `ago({lookback}s)`, la fenêtre de la passe, que le RulePoller lui passe (`detection_rules.py:1681-1682`) | **un brute force et la connexion qui le suit, livrés ensemble 30 min en retard** : ING3 juge le brute force, la connexion est hors de la fenêtre de `_LOGINS`, et la carte grave `ssh-login-after-brute-force` est perdue — le motif même du 11/11 | ancrer `_LOGINS` sur l'heure des échecs, de leur `IngFirstAt` à maintenant, bornée par l'horizon (§3.4, Q9) ; pas la fenêtre entière, qui marquerait une connexion de la même adresse 2 h **avant** le brute force |
| la découverte (`discovery.py:172`) | `Heartbeat`, `ago(2h)` | rien : `Heartbeat` est arrivé à temps le 11/11 | rien |
| `poll_detection` sur un `attack_started` | `timespan` depuis le T0 de l'attaque (`glorfindel/providers/azure/monitor.py:61-64`), plus la fenêtre de la règle | la fenêtre de la règle coupe une ligne en retard, comme au RulePoller | suit la règle |
| `glorfindel rules check` (`rule_check.py:214-218`) | la fenêtre du RulePoller | la même | suit la règle, rien à changer |
| `campaign_replay` (`campaign_replay.py:44-46`, `:95-100`) | chaque `ago()` réécrit pour remonter au T0 | la sélection à l'arrivée remonte aussi au T0 : juste pour un rejeu | à dire dans le lot |

### 2.4 Ce qu'on sait du retard de chaque source

| Source | Qui la livre | Ce qu'on sait | D'où | Statut |
|---|---|---|---|---|
| `Perf` | l'agent de la VM (par la règle de collecte) | 55 à 108 s juste après le bloc (le 11/11 à partir de 16:16, relevé le 12/11) ; 89 à 109 s (05/10) ; un bloc jusqu'à 1 610 s juste après une levée | le relevé de la fiche ; `detection_rules.py:1056` | mesuré deux fois, jamais en temps normal sur plusieurs jours (RH1) ; le bloc, une fois |
| `Syslog` | l'agent de la VM | `expected_latency_s: 480` (`detection_rules.yaml:25`) ; détections de bout en bout : T1110 à T0+~125 s (07/10, `docs/glorfindel.md`), T1136.001 en 144 s (31/10, `docs/demarrer/banc.md`) | l'en-tête des règles ne cite aucune mesure ; les détections bornent le retard ces jours-là | **non mesuré** en temps normal, ni après une levée (RH2, RH3) |
| `Heartbeat` | l'agent de la VM | 2 à 10 s, le 11/11, autour de la levée | le relevé | mesuré une fois ; sous la quarantaine, à lire (RH5) |
| `StorageBlobLogs` | la plateforme (le stockage) | `expected_latency_s: 90` ; « latence variable » (le T1041, `docs/historique.md`) | aucune mesure chiffrée | **non mesuré** (RH8) |
| `AzureActivity` | la plateforme | 3 à 20 min (Microsoft Learn, hypothèse A1 d'ID1) ; « minutes, parfois plus de dix » (`glorfindel/providers/azure/activity.py:39-40`) | la documentation | **non mesuré** : le protocole existe (`docs/operations.md`, « Les requêtes de mesure »), pas son résultat (RH7) |
| Entra (`AuditLogs`, `AADServicePrincipalSignInLogs`) | la plateforme | « quelques minutes (lots d'environ 5 min) », hypothèse E3 d'ID1 | la documentation | **non mesuré** (RH7) |

**Le partage qui compte, une hypothèse.** `Perf`, `Syslog` et `Heartbeat` passent par l'agent de la
VM, et le NSG de quarantaine refuse tout en sortie (`glorfindel/providers/azure/quarantine.py:17-19`,
`docs/azure.md`) : la quarantaine **devrait** couper l'agent. Les autres sources viennent de la
plateforme, que la quarantaine ne touche pas. Deux choses ne sont pas acquises :
- **que la quarantaine retienne la télémétrie** (RH5) : si des lignes `Heartbeat` datées d'avant la
  levée sont arrivées à temps, l'agent passait, et la quarantaine n'explique pas le bloc ;
- **que le bloc du 11/11 soit celui de l'agent** : le chemin de `Perf` côté Azure (la règle de
  collecte, l'ingestion du workspace) n'est pas exclu. RH3 (`Syslog`, par le même agent, retenu ou
  non) et RH5 départagent.

Le mécanisme (§3 à §6) vaut dans les deux cas ; le §7 en dépend, et le dit.

---

## 3. Le mécanisme

### 3.1 Ce qu'une règle doit garder

Deux questions différentes, que la fenêtre d'aujourd'hui confond :
- **Qu'est-ce qui est jugé à cette passe ?** Ce qui est arrivé depuis la passe d'avant. C'est une
  question d'**arrivée**.
- **Que vaut l'agrégat ?** Deux échantillons consécutifs du même volume (`ransomware-disk-write`),
  dix échecs en dix minutes (`ssh-brute-force`), une moyenne. C'est une question d'**heure** : la paire
  est celle de deux échantillons voisins dans le temps, quel que soit leur moment d'arrivée.

La règle : **on agrège sur `TimeGenerated`, on sélectionne par l'arrivée.** Un agrégat est jugé à
l'arrivée de sa dernière ligne : avant, il n'est pas complet.

### 3.2 Les pistes

| Piste | Ce qu'elle juge | Ce qu'elle rate | Ce qu'elle coûte |
|---|---|---|---|
| **0. Élargir `ago()`** (`ago(2h)` partout) | toute ligne arrivée moins de 2 h après son heure | rien de plus que 1 | **le sens des agrégats** : dix échecs étalés sur 2 h font un brute force ; la déduplication s'étire d'autant (une identité agrégée reste vue 2 h 05, une seconde rafale sur la même VM ne fait plus de carte) ; ×13 lignes lues |
| **1. Une fenêtre sur `ingestion_time()`** (`where ingestion_time() > ago(10m)` en tête) | chaque ligne une fois, à son arrivée | les agrégats d'heures mêlées : un bloc de 2 h compté comme 10 minutes ; une paire dont l'autre échantillon est arrivé à une autre passe | il faut **aussi** élargir la fenêtre de l'API (sur `TimeGenerated`, §1.2), sinon la ligne en retard est coupée avant la requête |
| **2. `TimeGenerated > ago(N) or ingestion_time() > ago(N)`** | ce que juge 1 | comme 1 (la branche de l'heure n'ajoute rien quand l'arrivée suit l'heure) | comme 1 ; l'agrégat mêle les lignes à l'heure et le bloc en retard ; et **une ligne d'une VM dont l'horloge avance est rejugée** tant que son heure reste dans la fenêtre (sous « maintenant + 1 min », la borne de l'API) |
| **3. Une fenêtre de rattrapage au RulePoller** (une seconde requête par passe, décalée vers le passé) | les lignes en retard, par une seconde lecture ; **sans changer aucune règle** : les règles du client, les règles autorées par `propose-rules` et les copies du banc sont couvertes telles quelles, sans dérive de `base_sha256` ni geste WL1 | ce que la réécriture du texte rate : le RulePoller réécrirait les `ago()` d'une requête qu'il ne lit pas (la leçon de P1 : suivre le KQL par des expressions régulières ne converge pas) ; un agrégat décalé mêle encore des heures | **une requête de plus par règle et par passe** (§5) ; une double lecture à dédupliquer |
| **3 bis. Un curseur d'arrivée** (le RulePoller pose `let arrived_since = datetime(…)`, la dernière passe réussie) | exactement ce qui est arrivé depuis la dernière passe, même après une coupure de la watch | rien de plus | **la règle ne se lit plus seule** : ni l'opérateur (`az monitor log-analytics query`), ni `rules check`, ni `campaign_replay` ne la lancent telle qu'écrite |
| **4. Jugée à l'arrivée, agrégée à l'heure** (§3.3, recommandée) | chaque ligne, à son arrivée, jusqu'à l'horizon ; chaque agrégat à l'arrivée de sa dernière ligne | une ligne au-delà de l'horizon (dite, §8) ; une ligne arrivée pendant une coupure de la watch plus longue que la fenêtre (comme aujourd'hui) | ×13 lignes lues par le serveur pour les règles à 10 min (×25 pour celle à 5 min), autant de lignes rendues qu'avant ; aucune requête de plus ; chaque règle réécrite, et ses copies |

### 3.3 La recommandée : jugée à l'arrivée, agrégée à l'heure

**Deux bornes, dans le texte de la règle**, que l'opérateur lit et lance tel quel :
- **la borne de l'heure** : `TimeGenerated > ago(N + H)`, la fenêtre de la règle `N` (10 min
  aujourd'hui) plus l'horizon de retard `H` (2 h proposées, Q2). Elle fixe ce que le serveur lit, et la
  fenêtre de l'API suit (`_query_lookback_s` lit le plus long `ago()`, inchangé) ;
- **la borne de l'arrivée** : `ingestion_time() > ago(N)`, ce qui est jugé à cette passe.

**Un champ déclaré**, `late_s` (= `H`, en secondes), pour que le RulePoller sache quelle part de la
fenêtre est l'horizon, sans deviner le texte (§3.4).

**Une règle d'événements** (sudo, `useradd`, crontab) : les deux bornes en tête, rien d'autre.

```kusto
Syslog
// La borne de l'heure : la fenêtre de la règle (10 min) et l'horizon de retard (2 h, late_s: 7200).
| where TimeGenerated > ago(130m)
// Jugée à son arrivée : une ligne l'est dans les 10 minutes qui suivent son ingestion, quelle que
// soit son heure.
| where ingestion_time() > ago(10m)
| where Facility in ("auth", "authpriv")
| where SyslogMessage has "new user: name="
…
```

Pour une règle qui résume (`summarize arg_max(TimeGenerated, *) by …` de sudo), la borne de l'arrivée
vient **avant** le résumé : la ligne la plus récente parmi celles arrivées, comme aujourd'hui parmi
celles de la fenêtre.

**Une règle qui agrège** (`ransomware-disk-write`) : l'arrivée est lue sur la table, avant tout
`project`, et la sélection se fait **après** le calcul de la paire, sur l'arrivée de la paire.

```kusto
let samples = Perf
  | where TimeGenerated > ago(130m)                   // la fenêtre et l'horizon
  | where ObjectName == "Logical Disk" or ObjectName == "LogicalDisk"
  | where CounterName == "Disk Write Bytes/sec"
  | extend Arrived = ingestion_time()                 // lue sur la table, avant tout project
  | project TimeGenerated, Arrived, Computer, _ResourceId, InstanceName, CounterValue
  | extend Vm = iff(isnotempty(_ResourceId), tolower(_ResourceId), Computer)
  | order by Vm asc, InstanceName asc, TimeGenerated asc
  | extend Same = prev(Vm) == Vm and prev(InstanceName) == InstanceName
  | extend Gap = iff(Same, TimeGenerated - prev(TimeGenerated), timespan(null)),
             PrevValue = iff(Same, prev(CounterValue), real(null)),
             // La paire est jugée à l'arrivée de son dernier échantillon.
             PairArrived = iff(Same, max_of(Arrived, prev(Arrived)), Arrived);
samples
| join kind=leftouter (samples | summarize Step = minif(Gap, Gap >= 1s) by Vm, InstanceName)
    on Vm, InstanceName
| extend Fine = …, Rate = …, Peak = …                // inchangés
| where PairArrived > ago(10m)                        // jugée à l'arrivée
| where (Fine and Rate > 45000000) or (not(Fine) and Rate > 25000000)
| summarize MaxWrite = max(Peak),
            // Les heures du retard, retirées de la ligne avant le signal (§3.5).
            IngFirstAt = min(TimeGenerated), IngLastAt = max(TimeGenerated),
            IngMaxDelayS = max(datetime_diff('second', Arrived, TimeGenerated))
            by Computer, _ResourceId
```

Rejoué sur le 11/11, à la passe d'après 16:16:59 : les échantillons de 15:50 à 16:14 sont tous
« arrivés depuis moins de 10 minutes », tous lus sur l'horizon ; les paires de 15:56:20 à 16:06
passent le seuil et entrent dans `MaxWrite`. Une écriture de 10 minutes, de 15:56 à 16:06, aurait fait
sa carte à cette passe. `IngFirstAt` dit 15:56:20 : l'heure de l'écriture, pas celle de la passe.

**`ssh-brute-force`** : le seuil est « 10 échecs en 10 minutes ». La règle tire **s'il existe une
fenêtre de 10 minutes (sur `TimeGenerated`) qui tient au moins 10 échecs du même couple (adresse,
VM), dont au moins un frais** (arrivé dans les 10 dernières minutes), lus sur tout l'horizon. Un
décompte qui ne regarderait qu'en arrière de chaque échec frais rate une arrivée dans le désordre :
dix échecs en 5 minutes, les cinq plus récents arrivés d'abord, puis les cinq plus anciens — à la
seconde passe, aucun échec frais n'a dix échecs derrière lui, et la règle ne tirerait jamais.

La forme exacte, linéaire : une telle fenêtre existe si et seulement si **dix échecs consécutifs** du
couple (triés par heure) tiennent en 10 minutes et que l'un d'eux est frais.

```kusto
let failures = Syslog
  | where TimeGenerated > ago(130m)                   // la fenêtre et l'horizon (late_s: 7200)
  | extend Fresh = toint(ingestion_time() > ago(10m)) // arrivé dans les 10 dernières minutes
  | where Facility == "auth"
  | …                                                 // les filtres de la règle, inchangés (SEC2)
  | extend SourceIP = extract(…)                      // inchangé
  | where isnotempty(SourceIP) and not(SourceIP matches regex …)
  | extend Key = strcat(SourceIP, "|", Computer, "|", _ResourceId)
  | order by Key asc, TimeGenerated asc
  // Le nombre d'échecs frais jusqu'à cette ligne, repris à zéro à chaque couple.
  | extend CumFresh = row_cumsum(Fresh, Key != prev(Key))
  // Cette ligne et les neuf suivantes du même couple, lues dans le let, sur les lignes triées.
  | extend LastKey = next(Key, 9), Last = next(TimeGenerated, 9), LastCum = next(CumFresh, 9);
failures
// Dix échecs consécutifs du couple en 10 minutes au plus, un frais au moins parmi eux.
| where LastKey == Key and Last - TimeGenerated <= 10m and LastCum - (CumFresh - Fresh) > 0
| summarize Start = min(TimeGenerated), End = max(Last) by Key, SourceIP, Computer, _ResourceId
// FailedAttempts : les échecs du couple entre le début de la première suite et la fin de la dernière.
| join kind=inner (failures | project Key, T = TimeGenerated) on Key
| where T between (Start .. End)
| summarize FailedAttempts = count(), IngFirstAt = min(Start), IngLastAt = max(End)
            by SourceIP, Computer, _ResourceId
```

Les `next()` sont dans le `let`, juste après son `order by` : ils lisent les lignes triées, sans
dépendre de la façon dont Kusto développe une référence au `let`. Si un même bloc tient deux
rafales éloignées du même couple, `Start .. End` les réunit, et `FailedAttempts` compte aussi les
échecs isolés entre elles : une valeur plus haute, jamais une carte de moins.

La règle rend `FailedAttempts` (le nom que COR1 lit, `correlation.py:511`) ; sa valeur change de sens
(les échecs de la rafale, non plus ceux des 10 dernières minutes), pas sa forme. Dix échecs étalés
sur 2 h et arrivés d'un bloc ne tirent pas ; dix échecs en 5 minutes arrivés en deux blocs, dans
n'importe quel ordre, tirent à l'arrivée du second. Ce sens nouveau change des détections : une rafale
ancienne arrivée en retard tire, et c'est une question (Q10). La garde de la borne de l'arrivée
(§3.4) reconnaît `Fresh`, puis `CumFresh`, comme des colonnes qui dérivent de l'arrivée. `kql_subset` ne lit encore
ni `row_cumsum`, ni `next`, ni `between` sur des colonnes : ING3 les lui ajoute, ou prouve la règle par
un oracle en Python, puis par `rules check --live` (RH10).

**`data-exfiltration-blob`** : son seuil est une écriture (`PutBlobCount >= 1`, `:101`) ; il ne dépend
pas de la fenêtre. La sélection à l'arrivée suffit, `PutBlobCount` compte alors les écritures
arrivées.

**Les règles d'auditd** (trois) : un événement est jugé à l'arrivée de son dernier enregistrement
(`Arrived = max(ingestion_time())` par `AuditEvent`). Un événement dont le `SYSCALL` arrive avant
l'`EXECVE` est relu à l'arrivée du second ; son identité (`ts:` + l'événement, `:1142-1146`) ne bouge
pas, il est donc dédupliqué comme aujourd'hui dans une même fenêtre.

**Ce que ça ne change pas** : ni les seuils, ni les colonnes rendues, ni les exclusions, ni la
préparation des lignes (AUD1, ADM1, COR1), ni la façon dont le RulePoller route et plafonne.

### 3.4 Ce que le RulePoller change

| Quoi | Aujourd'hui | Avec ING2 |
|---|---|---|
| la fenêtre de l'API | le plus long `ago()` + 300 s (`:1640-1641`) | **inchangée** : le plus long `ago()` est maintenant `N + H` |
| la fenêtre de sélection `N` | le plus long `ago()` | le plus long `ago()` moins `late_s` |
| l'expiration d'une identité d'**événement** (`ts:`, `op:`, `entra:`) | fenêtre de l'API (`:1694-1699`) | **inchangée** : la fenêtre de l'API, horizon compris |
| l'expiration d'une identité **agrégée** (`row:`) | fenêtre de l'API | `N` + 300 s, comme aujourd'hui sans horizon |
| la fenêtre de `_LOGINS` de COR1 (`:1681-1682`) | fenêtre de l'API | **ancrée sur les échecs** : une requête par VM, comme aujourd'hui, depuis le plus ancien `IngFirstAt` des lignes de brute force de cette VM, bornée par `N + H` + 300 s ; puis, **ligne par ligne**, seule une connexion datée à partir de l'`IngFirstAt` de cette ligne compte (`at >= IngFirstAt`). Ce filtre par ligne n'existe pas aujourd'hui : `tag_compromise` compare l'adresse, jamais l'heure (`correlation.py:522-535`) ; ING3 l'écrit (Q9) |
| les colonnes `Ing*` de la ligne | — | retirées de la ligne **avant** le routage, l'identité et le signal, et rangées dans une table à côté, par ligne (`id(row)`, comme `judged` d'ADM1, `detection_rules.py:1673`) ; `correlation.settle` la reçoit en paramètre, pour l'`IngFirstAt` de chaque brute force ; le signal en tire sa ligne de `signal_timing.jsonl` (§3.5) |

**`late_s` est validé au chargement** (la validation de P1, `_invalid_client_entry`,
`detection_rules.py:423-478`, et `load_config` pour la base) : un entier de secondes, `0 < late_s <`
le plus long `ago()`, au plus 6 h ; et la requête **filtre** sur l'arrivée dans une forme reconnue
(commentaires exclus, comme `_query_lookback_s`) : un `where` lit la comparaison
`ingestion_time() > ago(…)`, directement ou par une colonne qui en dérive. Une colonne en dérive
quand elle est affectée par `= ingestion_time()` puis comparée à `ago(…)` (le `PairArrived` de
`ransomware-disk-write`, par `max_of(Arrived, prev(Arrived))`), ou par cette comparaison elle-même
(le `Fresh` de `ssh-brute-force`, puis son cumul `row_cumsum`, que lit le `where`). Lire
`ingestion_time()` ne suffit pas : une règle qui fait seulement
`extend Arrived = ingestion_time()` passerait une garde qui ne cherche que le mot. Hors de cette forme,
`late_s` est ignoré et c'est dit (« règle … : `late_s` ignoré, la requête ne filtre pas sur
l'arrivée ») : la règle tourne avec `N` = sa fenêtre entière, la déduplication d'aujourd'hui.
**Jamais l'inverse** : une règle qui déclare un horizon sans sélectionner par l'arrivée garderait ses
lignes agrégées sélectionnables 2 h, et une expiration de 15 minutes les rejugerait (§4).

**La limite de cette garde** : elle lit le texte, la plus stricte, et refuse au doute (comme
`eregion_core/rule_routing.py`). Une requête qui filtre sur l'arrivée puis rejoint des lignes non
filtrées la passerait encore. Ses formes sont aussi à
préciser dans ING2 pour deux règles livrées : le `where` de `ssh-brute-force` lit `CumFresh` à travers
`next()` et une soustraction, et les trois règles d'auditd affectent `Arrived = max(ingestion_time())`
dans un `summarize`, non par `= ingestion_time()`. Une dérivation à travers l'arithmétique admettrait
`where Fresh >= 0`, qui ne filtre rien. L'effet est toujours du bruit (une carte agrégée toutes les
`N` + 300 s pendant l'horizon), jamais un silence : une identité d'événement, elle, est gardée toute
la fenêtre.

**Une règle du plan des données sans `late_s`** se charge comme aujourd'hui, et c'est dit (une note,
comme `MIN_LOOKBACK_S`) : « règle … : jugée sur `TimeGenerated` seulement ; une ligne arrivée plus de
N min après son heure n'est jamais jugée ». Le plan de contrôle et les identités n'ont pas cette note
tant que leur retard mesuré tient dans leur heure (ING7).

### 3.5 Ce que le modèle voit

- **La forme ne change pas.** `_build_user_message()` écrit le signal entier, en JSON
  (`agent.py:3033-3035`), ligne de la règle comprise (`raw_signal.first_result_row`). Une colonne de
  plus dans la ligne serait vue du modèle. Les colonnes `Ing*` sont donc **retirées de la ligne** avant
  le signal, et gardées à côté.
- **Où et combien de temps.** Pas dans `dispatched`, élagué à chaque passe (`:1694-1699`), en 15
  minutes pour une identité agrégée : l'après-coup du dossier peut venir à la levée, 35 à 37 h plus tard.
  Dans leur propre fichier, `~/.glorfindel/signal_timing.jsonl` (0600, une ligne par signal du plan des
  données : `signal_id`, la règle, la VM, `IngFirstAt`, `IngLastAt`, `IngMaxDelayS`), écrit avec le
  signal, élagué après 30 jours — la rétention de `Perf` au banc, et celle que DOS1 propose pour un
  dossier (sa Q7) ; la probation, 24 h, y tient. Borné par les plafonds de cartes (SEC2).
- **Ce qu'il porte, selon la règle.** `ransomware-disk-write` rend les trois colonnes ;
  `ssh-brute-force`, `IngFirstAt` et `IngLastAt` ; les règles d'événements, aucune : leur ligne porte
  déjà son `TimeGenerated`, mais pas son arrivée. Pour elles, `signal_timing.jsonl` n'a que l'heure de
  la ligne, et le fait `signal_delay` (§8) n'a pas de chiffre de retard : il le dit.
- **Dans la suite hermétique.** ING2 ajoute `signal_timing.jsonl` aux chemins que le `conftest`
  redirige vers un dossier jetable (HY1) : un test n'écrit jamais dans `~/.glorfindel/`.
- **Hors de ce que lit le modèle.** `_build_user_message()` injecte l'état de la VM depuis
  `~/.glorfindel/isolation/<vm>.json`, les blocages (`levee-probation.md`, §6.3) et le dernier restore
  (`glorfindel.jobs.get_last_restore`, `agent.py:3108-3118`) : ces fichiers ne conviennent pas.
  `signal_timing.jsonl` n'est lu par aucun chemin du message ; un test le tient, et un autre fige le
  message, à l'octet, pour une ligne donnée. Ni `_SYSTEM_PROMPT`, ni `few_shot_examples.yaml`, ni
  `_build_user_message()` ne changent.
- **Ce qui change, c'est quelles lignes deviennent des détections** : une ligne en retard en devient
  une. La règle d'événements rend son `TimeGenerated`, que le modèle lit ; la ligne agrégée de
  `ransomware-disk-write` n'a pas d'heure, et le modèle ne sait pas que les échantillons ont 20
  minutes. L'enquête lit alors les minutes d'après (§2.3). C'est une limite, dite au dossier (§8), et
  la question Q8.

---

## 4. La déduplication : une ligne n'est jamais jugée deux fois

Notations : `a` l'arrivée d'une ligne, `N` la fenêtre de sélection, `H` l'horizon, `I` l'intervalle
de la règle, `d` l'heure du premier envoi. Le RulePoller enregistre l'identité **après** l'envoi
(`:1793-1797`), l'expire depuis `d` (`:1694-1699`), et la garde sur disque à travers un redémarrage
(`rule_status.json`).

**Une ligne d'événement** (son identité : son heure et son texte, ou son événement d'audit ; une
opération ; un constat d'Entra).
- Elle est rendue par la requête tant que `a > now − N` (la borne de l'arrivée) et que son heure est
  dans `N + H` (la borne de l'heure et l'API) : au plus pendant `[a, a + N]`.
- Elle est vue à la première passe après `a` : `d ≤ a + I` plus la durée de la requête.
- Son identité est gardée jusqu'à `d + N + H + 300 s`, bien après `a + N`. **Elle ne revient jamais.**
- C'est vrai même d'une règle qui déclare `late_s` en lisant `ingestion_time()` sans la filtrer : la
  ligne reste sélectionnable `N + H`, et son identité aussi longtemps.

**Une ligne agrégée** (son identité : qui, où).
- L'agrégat est rendu tant qu'une de ses lignes est fraîche. Son identité est gardée `N + 300 s` après
  la carte, **comme aujourd'hui** : pendant ce temps, la même VM ne refait pas de carte de cette règle.
- Après, une nouvelle rafale, ou la suite de la même, refait une carte : c'est le comportement
  d'aujourd'hui, une carte par fenêtre glissante. Ce n'est pas une ligne jugée deux fois : c'est
  l'agrégat qui l'est, par fenêtre.
- **Pourquoi pas l'horizon** : une identité agrégée gardée 2 h 15 cacherait une seconde rafale sur la
  même VM pendant 2 h 15 — par exemple sur la VM restaurée, après sa levée (§7). C'est la piste 0, et
  la raison de séparer les deux expirations.
- Une arrivée dans le désordre peut faire rejuger un agrégat : la paire de `ransomware-disk-write`
  (l'échantillon d'avant arrivé après celui d'après ; la paire est symétrique, `max_of(Arrived,
  prev(Arrived))`), ou les dix échecs de `ssh-brute-force` (une suite de dix qui gagne une ligne
  fraîche). Pour ces deux formes, c'est au plus une carte de plus, après l'expiration, jamais une de
  moins. Un décompte qui ne regarde qu'en arrière (§3.3) en perdrait une : c'est un mutant d'ING3.

**Ce qui n'est pas jugé, et le dit.**
- Une ligne arrivée plus de `H` après son heure : la borne de l'heure la coupe. Le retard est vu
  (§8), une carte le dit, jusqu'à 48 h de retard ; au-delà, la ligne reste invisible, à la vue comme
  aux règles.
- Une ligne arrivée pendant une coupure de la watch plus longue que `N` : comme aujourd'hui avec
  `TimeGenerated`. La console dit déjà la coupure (le battement de la watch). Le curseur d'arrivée (la
  piste 3 bis) la fermerait, au prix d'une règle qui ne se lit plus seule.

**Le premier passage d'une version à l'autre.** Le jour où ING3 se déploie, les identités enregistrées
restent les mêmes (l'heure et le texte d'une ligne ne changent pas) : rien n'est renvoyé. Une ligne en
retard, déjà arrivée mais jamais jugée, l'est une fois, si son heure tient dans l'horizon.

---

## 5. Le coût

**Les requêtes.** Une par règle et par passe, comme aujourd'hui. Aux intervalles livrés : six règles à
30 s, huit à 60 s, trois à 120 s, une à 300 s, soit environ **1 300 requêtes par heure** pour la watch.
La recommandée n'en ajoute aucune. La piste 3 en ajouterait une par passe pour chacune des neuf règles
du plan des données : environ 900 de plus par heure (+70 %). La vue du retard (§8) : une requête
toutes les 5 minutes, 12 par heure.

**Le volume lu par le serveur.** `N + H = 130 min` au lieu de 10 : **×13** pour chaque règle à 10
minutes (×7 pour un horizon d'1 h, ×37 pour 6 h) ; **×25** pour `data-exfiltration-blob`, dont `N` vaut
5 minutes (125 au lieu de 5). Au banc, un échantillon toutes les 10 s par
volume (`detection_rules.yaml:43-44`) : 60 par volume et par VM sur 10 minutes, 780 sur 130. Pour
`Syslog`, le volume se lit sur les données gardées (DH8 de DOS1 : 298 échecs SSH sur 10 jours, 41
sources, sur bree).

**Le volume rendu.** Le même ordre qu'aujourd'hui : la borne de l'arrivée filtre avant le résumé ou la
projection. Une règle agrégée rend une ligne par VM ; une règle d'événements, les lignes arrivées.

**Les plafonds, inchangés.** Un bloc en retard est, pour le RulePoller, une passe chargée :
- `ransomware-disk-write`, agrégée : une ligne par VM, donc une carte ;
- une règle d'événements : la plus récente au modèle, les autres sur une carte sans décision
  (`_SAME_PASS`, V-13, `:1742-1751`) ; au plus 5 cartes par règle et par passe, puis une synthèse
  (`_DATA_CARDS_PER_POLL`, `_SUMMARY_ROWS_MAX`, `:1208`, `:1223`) ;
- la file de décision : `QUEUE_MAX` 50, `DEDUP_WINDOW_S` 300 s, `MODEL_CALLS_PER_MIN` 10 (SEC-A2,
  `docs/glorfindel.md`). Un bloc en retard ne coûte pas plus d'appels au modèle qu'une rafale à l'heure.

**La mémoire de la déduplication.** Une identité d'événement est gardée `N + H + 300 s` au lieu de
`N + 300 s` : environ neuf fois plus d'entrées dans `dispatched`. Sous un flot de lignes forgées (un
utilisateur local écrit des lignes à volonté, SEC-A2), quelques milliers d'identités par règle et par
VM, quelques centaines de Ko dans `rule_status.json`. Le lot ING2 le mesure dans un test ; une borne
par VM, si elle vient, ne peut que faire rejuger (une carte de plus), jamais taire.

**Le prix.** Une requête sur une table en facturation à l'ingestion ne coûte rien de plus (la même
remarque que DOS1, §7) ; sur une table `Basic` ou `Auxiliary`, la requête se paie, et ×13 (×25) aussi. Pas
le cas du banc.

**La durée d'une requête.** Celle de `ransomware-disk-write` sur 130 minutes, et de
`ssh-brute-force` (son tri, son `join`), est à mesurer (RH10) : `glorfindel rules check --live` la donne, règle par règle.

---

## 6. Les copies du client et les règles autorées

**La copie de `sudo-privilege-escalation`.** ING3 change la règle livrée (ses deux bornes, `late_s`) :
son `base_sha256` change (`base_rule_sha256`, l'empreinte de la règle livrée entière,
`detection_rules.py:499`). La watch écarte alors la copie du banc, dit la dérive, et fait tourner la
règle livrée (`_drift`, `:509`) : **les cartes de la maintenance programmée de bree reviennent**, rien
n'est caché.
- **Dans la PR d'ING3** : la copie refaite dans `infra/glorfindel-host/client_rules.bench.yaml` — la
  nouvelle requête livrée, le même bloc d'exclusion, `late_s` recopié, l'empreinte recalculée.
  `tests/unit/test_bench_routine.py` échoue tant qu'elle ne l'est pas
  (`test_the_bench_rule_is_the_shipped_query_plus_the_exclusion_block_alone`).
- **Le geste de Jonathan** : `make glorfindel-host-client-rules`, une fois la release qui porte ING3
  déployée sur Imladris (anciennement H0) par son CD. Pas avant : la watch d'avant tourne encore
  l'ancienne règle livrée, et la nouvelle copie y serait écartée. Entre le déploiement et le geste,
  les cartes de la maintenance de bree reviennent (Q6).
- **Les deux autres copies** (`nsg-change-outside-glorfindel`, `entra-sp-unusual-signin`) ne bougent
  pas : ING3 ne touche ni le plan de contrôle ni les identités. ING7, s'il part, les refait, avec le
  même geste.

**Les règles approuvées sur Imladris** (la couche du client, `~/.glorfindel/client_rules.yaml`) restent
telles qu'écrites, sur `TimeGenerated`. ING2 les dit au chargement (la note du §3.4), et
`glorfindel rules` les liste. Les réécrire est un geste de Jonathan (une règle refaite à la main, ou
proposée à nouveau puis approuvée).

**`propose-rules`** (`detection_authoring`). Le prompt d'autorat demande une fenêtre serrée (« Keep
the time window tight », `detection_authoring.py:235`) : le modèle écrira des fenêtres sur
`TimeGenerated`. La recommandation (Q5) : **le code dit, le prompt ne change pas en v1**. À
l'approbation (`proposed_rules.approve`, puis `rule_layers.write_client_rule`) et dans
`rules check`, une règle du plan des données qui ne sélectionne pas par l'arrivée porte la note du
§3.4 ; elle est approuvée quand même. Changer le prompt d'autorat change ce que le modèle écrit : un
lot à part, avec le harnais (`make llm-compare`, par Jonathan). Tout reste proposition ; le chargement
reste déterministe.

---

## 7. Ce que LEV3 et LEV4 doivent en tirer

La probation suit une levée ; ce sont justement les minutes qui arrivent en retard. **Les points 1 à 3
et 5 à 6 supposent que la quarantaine retient la télémétrie de l'invité** (RH5, avec RH3 : §2.4). Si
RH5 tombe (l'agent passe la quarantaine), le cas 2 de LEV voit l'invité comme aujourd'hui, et seuls
les points 4, 7 et 8 restent ; le bloc du 11/11 serait alors à chercher côté Azure.

1. **Sous la quarantaine, la télémétrie de l'invité n'arriverait pas** (RH5). Le NSG de quarantaine
   refuse tout en sortie (§2.4). Le 11/11, les échantillons pris sous la quarantaine (15:50 à 15:54)
   sont arrivés 22 min 40 s après la levée. Ce que l'agent garde des 35 à 37 h, et combien de temps il
   le garde, n'est pas mesuré (RH4).
2. **Le cas 2 de LEV ne pourrait pas venir de l'invité.** « Une détection sur la VM datée après la fin
   du restore » retient la levée (`levee-probation.md`, §3.1). La VM restaurée démarre sous la
   quarantaine (§6.3 de LEV) : si RH5 tient, ses lignes `Perf` et `Syslog` n'arrivent qu'**après** la
   levée, et avant la levée le cas 2 ne voit que le plan de contrôle. **LEV3 doit dire cette condition**,
   et que la marge `lift.log_settle_s` (900 s, Q14 de LEV) attend le journal d'activité, pas l'invité.
3. **Le démarrage se jugerait donc en probation, et seulement avec ING3.** LEV le dit déjà : « Sa
   télémétrie peut arriver après la levée, avec un moment d'avant ; elle compte » (§6.3). Avec les
   fenêtres d'aujourd'hui, une ligne `useradd` du démarrage, arrivée 23 minutes après la levée avec une
   heure plus vieille encore, n'est jamais jugée. **ING3 est une condition de LEV4.**
4. **Le moment d'une détection** (quoi que donne RH5). La borne de la probation (« un signal dont le
   moment est après la fin du job de restore ») lit l'heure des lignes : `TimeGenerated` pour une règle
   d'événements ; pour une règle agrégée, **`IngLastAt`** (gardé à côté du signal, §3.5), la dernière
   ligne au-dessus du seuil — **jamais** le `timestamp` du signal, qui est l'heure de la passe
   (`detection_rules.py:1891`), **ni `IngFirstAt`**. Un agrégat peut mêler, dans un même bloc en
   retard, des échantillons d'avant la fin du restore et d'après (si RH5 tient, si le tampon de l'agent
   survit au restore, si l'écriture tournait sous la quarantaine) : lu par son `IngFirstAt`, il
   passerait pour l'incident d'origine, et la réécriture d'après le restore ne réisolerait pas. Une
   lecture plus fine, l'agrégat recalculé sur les seules lignes datées après la fin du restore, reste
   ouverte à LEV4. `IngFirstAt` sert au dossier (DOS5, DOS9) et à COR1. Deux mutants de LEV4 : la borne
   sur le `timestamp` du signal ; la borne sur `IngFirstAt` (l'agrégat mêlé ne réisole pas).
5. **L'horizon face à la levée.** Le retard d'une ligne du démarrage, à son arrivée, vaut le temps
   passé sous la quarantaine après le restore, plus le rattrapage de l'agent.
   - En `non_disruptive`, Imladris lève après la fin du job plus 15 minutes : avec le rattrapage du
     11/11 (22 min 49 s, de la levée à la fin du bloc), environ 38 minutes. **Dans l'horizon de 2 h.**
   - En `human_only`, ou sur une retenue, un humain lève des heures plus tard : **au-delà de
     l'horizon.** Les lignes du démarrage ne sont jugées par aucune règle.
6. **Donc une relecture de rattrapage, propre à la probation** (Q7). Au début de la probation, une fois
   le rattrapage de l'agent fini (la vue du retard, §8, voit `Perf` arriver de nouveau à l'heure), les
   règles de probation tournent **une fois** sur `[fin du restore, maintenant]`, leurs détections par
   `_probation_decision`. Si le rattrapage ne finit pas, ou si des heures manquent (l'agent les a
   perdues), c'est un fait de la carte de probation : « les mesures de la VM sous la quarantaine ne
   sont jamais arrivées, de … à … ».

   **Comment elle lit une fenêtre absolue**, alors que le texte des règles porte `ago(130m)` et
   `ingestion_time() > ago(10m)`. Deux façons, et aucune n'est gratuite :
   - **la réécriture de `campaign_replay`, assumée** (recommandée) : chaque `ago()` remplacé par
     `ago(<depuis la fin du restore>)` (`campaign_replay.py:44-46`, `:95-100`, en service), le
     `timespan` absolu `[fin du restore − 5 min, maintenant]`. Pour une règle de la forme du §3.3, le
     sens est simple et juste : tout ce qui est daté **et** arrivé depuis la fin du restore ; les
     fenêtres internes (`<= 10m`, `25s`) ne sont pas des `ago()` et ne bougent pas. C'est bien ce que
     le §3.2 reproche à la piste 3 — réécrire un KQL qu'on ne lit pas —, mais borné : une fois par
     probation, d'une seule façon, et seulement sur une règle dont les `ago()` sont exactement ses deux
     bornes (vérifié au chargement). Elle couvre sans les changer **les copies du banc et les règles du
     client écrites dans la forme d'ING3**. Une règle restée sur `TimeGenerated` seul — une règle du
     client d'avant ING3, une règle autorée (Q5) — n'a qu'un `ago()` : elle est **exclue** de la
     relecture, et la carte de probation la nomme. La réécrire aussi serait juste pour une règle
     d'événements, mais un agrégat y perdrait son sens (dix échecs sur 3 h) : la conception ne le fait
     pas. La relecture se **déduplique par les mêmes identités que `dispatched`** : dans l'horizon
     (une levée de `non_disruptive`, environ 38 min), elle relit des lignes déjà jugées, qui ne
     reviennent pas ;
   - **un `probation_query` à bornes absolues** : la variante de probation que LEV prévoit déjà
     (§6.2 de LEV), écrite avec deux noms que la watch pose devant (`let since = datetime(…);
     let until = datetime(…);`). Aucune réécriture ; mais un second texte par règle, qui ne se lance
     pas seul (le défaut de la piste 3 bis), et rien pour une règle qui n'en a pas.
7. **La déduplication agrégée** (§4) : une rafale de `ransomware-disk-write` sur la VM restaurée,
   après la levée, refait une carte dès que `N + 300 s` sont passés depuis la carte de l'incident. Le
   restore prend environ 20 minutes : c'est déjà le cas. La piste 0 l'aurait cassé.
8. **La carte de début de probation** dit l'état du rattrapage, à côté de la règle des ports et des
   disques d'origine (`probation_started`, §3.1 de LEV).

À reporter dans LEV3 (le cas 2 et sa condition, la marge) et LEV4 (la borne par l'heure des lignes, la
relecture de rattrapage) : l'Orchestre route ces points vers la session Glorfindel.

---

## 8. Le retard lui-même : un état, un fait, une carte au-delà de l'horizon

**Pourquoi le voir.** Le 11/11, `Heartbeat` est arrivé à temps pendant que `Perf` était retenu : la VM
semblait vivante et bien suivie, et elle ne l'était pas. `ingestion_time()` est écrit par Log
Analytics, pas par l'invité ; et le retard est la seule façon de dire ce qui n'a pas été jugé.

**Ce que le retard mesure.** `ingestion_time() - TimeGenerated` confond deux choses : le retard
d'ingestion, et le **décalage de l'horloge** qui date la ligne (celle de la VM, si l'agent date à la
collecte : RH9). Une VM dont l'horloge retarde de 20 minutes paraît livrer avec 20 minutes de retard.
Les cartes le disent : « retard d'ingestion ou horloge de la VM ».

**La vue du retard** (ING4). Une requête toutes les 5 minutes, pour toute la watch, sur les lignes
**arrivées** dans les 10 dernières minutes de `Perf`, `Syslog` et `Heartbeat` : par VM et par table,
le nombre de lignes, le retard médian et maximal, et la plus vieille heure arrivée.

**Sa fenêtre de `TimeGenerated` va bien au-delà de l'horizon.** Le `timespan` de l'API porte sur
`TimeGenerated` (§1.2) : bornée comme le RulePoller (`N + H`), la vue ne verrait jamais une ligne
arrivée au-delà de `H`, et la carte « au-delà de l'horizon » ne se ferait jamais — le trou du 11/11
sous une autre forme. La vue lit donc **48 h** de `TimeGenerated` (au-dessus des 35 à 37 h de la
quarantaine de bree, la plus longue connue ; réglable, Q4), filtrées par `ingestion_time() > ago(10m)`.
- **Ce qu'elle rend** est borné par ce qui est arrivé : quelques lignes par VM et par table.
- **Ce qu'elle coûte** : le serveur lit 48 h de ces trois tables toutes les 5 minutes, 12 fois par
  heure, pour n'en garder que les arrivées récentes. Au banc, pour `Perf`, 17 280 échantillons par
  volume et par VM à chaque passe (un toutes les 10 s). La durée en est à mesurer (RH10).
- **Ce qu'elle ne voit pas** : une ligne datée de plus de 48 h avant son arrivée reste invisible, à la
  vue comme aux règles. RH4 dit si l'agent en livre ; si oui, la fenêtre s'allonge (7 jours), ou la
  limite reste dite.

**Les tables à cadence, et les autres.** `Perf` a une cadence : un échantillon toutes les 10 s au banc,
60 s sur la règle de collecte par défaut d'Azure (`detection_rules.yaml:43-44`). `Heartbeat` aussi, un
battement régulier de l'agent, dont la période est à lire (RH12). Leur silence prouve quelque chose. `Syslog` n'en a pas : il suit les
événements, la règle de collecte du banc lit auth, authpriv, syslog et daemon, plus local6 et cron en
option (`infra/terraform/monitoring.tf:47`), et celle d'un client peut se limiter à auth. Une VM calme
se tait des heures (RH12). Le silence de `Syslog` ne fait **jamais** de carte ; une cadence se déclare
par table, `Perf` seul en v1, et ne vaut pour une VM qu'une fois `Perf` vu sur elle : une VM dont la
règle de collecte ne prend pas `Perf` n'entre jamais dans l'état « muette ».

**Un état par VM et par table**, dans le statut de la watch, lu par la console :

| État | Quand | Ce qui suit |
|---|---|---|
| à l'heure | le retard maximal sous `N` | rien |
| en retard | le retard maximal au-dessus de `N`, sous l'horizon | un état, sur la tuile : « `Perf` de bree : 25 min de retard » ; les lignes sont jugées (ING3) |
| au-delà de l'horizon | une ligne arrivée plus de `H` après son heure | **une carte, au passage dans cet état**, une par VM et par table ; elle se ferme quand la table repasse sous l'horizon. Jamais une par passe : une horloge en retard de plus de `H` en ferait une toutes les 5 minutes. Ces lignes n'ont été jugées par aucune règle (A0 : ce qui n'est pas jugé est dit) |
| muette | **une table à cadence** (`Perf`) sans ligne depuis plus de `N`, alors que `Heartbeat` arrive | **une carte, au passage dans cet état** : la VM semble suivie et ne l'est pas — le motif du 11/11 |
| illisible | la requête échoue | un état illisible, jamais « à l'heure » (A0) |

**Une VM en quarantaine** est mise à part : son silence est attendu. À sa levée commence son
**rattrapage**, suivi jusqu'à ce que `Perf` revienne « à l'heure » : c'est le fait que LEV4 lit (§7,
point 6).

**Un fait du dossier de DOS1.** Le dossier ancre ses fenêtres sur l'heure du signal, `T`
(`dossier-isolation.md`, §3.1). Pour une règle agrégée, `T` n'est pas dans la ligne : c'est
`IngFirstAt`, lu dans `signal_timing.jsonl` (§3.5). Un fait de plus, `signal_delay`, parmi ceux de la
décision (F6) : « la détection s'est faite sur des lignes arrivées avec jusqu'à 21 min de retard ;
l'enquête a lu les minutes d'après » — l'auteur est la plateforme, l'état `lu`. Pour une règle
d'événements, qui ne rend pas son arrivée (§3.5), le fait dit l'heure de la ligne, et « retard non
lu ». C'est un fait local,
qui revient donc à DOS3 (les faits locaux, dont F6) ; avant ING2, il est `sans_objet`. Et l'après-coup
(F5) d'une isolation dit, à sa levée, le rattrapage de la VM. Les deux restent pour l'humain, jamais
pour le modèle.

**Sur la console** : l'état sur la tuile de la VM, et une ligne dans la section des règles. Un lot de
la console après ING4.

---

## 9. Le modèle de menace

| Ce que fait un attaquant | Ce qui le tient | Ce qui reste ouvert |
|---|---|---|
| root sur la VM arrête l'agent, agit, le relance : ses lignes arrivent en retard | jugées à leur arrivée, jusqu'à l'horizon (ING3) ; au-delà, la carte du §8 | ce que l'agent perd en route n'arrive jamais (RH4) |
| il ne coupe que `Perf`, et laisse `Heartbeat` | l'état « muette », une carte (§8) | — |
| il ne coupe que `Syslog` | — | `Syslog` n'a pas de cadence : son silence ne prouve rien (RH12) ; aucune règle ne le voit |
| il retarde une connexion avec son brute force, dans le même bloc | `_LOGINS` ancrée sur l'heure des échecs (Q9) | sans elle, la compromission est perdue (§2.3) |
| il arrête tout l'agent | `Heartbeat` s'arrête : la découverte le voit (`LastSeen`, `discovery.py:172`) | inchangé |
| il écrit une ligne `Syslog` datée dans le passé | jugée à son arrivée | si l'agent prend l'heure de la ligne pour `TimeGenerated` (RH9), une heure plus vieille que l'horizon la cache, et la carte du §8 le dit |
| il écrit une ligne datée dans le futur | — | la fenêtre de l'API s'arrête à « maintenant + 1 min » (`:1645`) : une ligne plus loin n'est jamais lue, aujourd'hui comme demain (RH9) |
| il inonde de lignes en retard | les plafonds de SEC2 et de SEC-A2, inchangés (§5) | la mémoire de la déduplication grandit (§5) |
| il cache une connexion dans la base de `entra-sp-unusual-signin` | — | une connexion arrivée plus d'une heure en retard se rend « connue » (§2.1) : ING7, si le retard d'Entra l'exige |

`ingestion_time()` est écrit par la plateforme (la documentation de Microsoft) : l'invité ne choisit
pas le moment où sa ligne est jugée.

---

## 10. Ce qui n'est pas mesuré

Aucune mesure n'est faite par ce lot. La plupart se font **en lecture seule, sur les données
gardées** : `Perf` et `Syslog` sont gardés 30 jours au banc (`infra/terraform/config.yaml:114`,
`log_retention_days: 30`). Les lignes de la levée du 11/11 disparaissent vers le 11/12 ; celles du
T1486 du 09/11 sur gondolin (une isolation, puis un restore), vers le 09/12.

| N° | Hypothèse | Ce qui la mesure | Si elle tombe |
|---|---|---|---|
| **RH1** | le retard normal de `Perf` reste sous 2 min (55 à 108 s le 11/11 juste après le bloc, relevés le 12/11 : pas un temps normal ; 89 à 109 s le 05/10) | p50, p95 et maximum de `ingestion_time() - TimeGenerated` sur 7 jours, par VM (lecture seule) | `N` à revoir pour `Perf` |
| **RH2** | le retard normal de `Syslog` tient sous `N` = 10 min ; l'en-tête dit 480 s sans mesure (`detection_rules.yaml:25`) | la même requête sur `Syslog`, par facilité, sur 7 jours (lecture seule) | `N` ou `H` à revoir pour `Syslog` |
| **RH3** | `Syslog` de bree a été retenu comme `Perf` autour de la levée du 11/11 | `Syslog` de bree de 15:40 à 16:40 le 11/11 : heure, arrivée, retard (lecture seule, **avant le 11/12**) | si `Syslog` arrivait à temps, le bloc est propre à `Perf` (une file de l'agent par flux ?) : le §7 se resserre sur `Perf` |
| **RH4** | ce que l'agent livre de la quarantaine : tout, une partie, rien des 35 à 37 h | `Perf` et `Syslog` de bree, comptés par heure de l'échantillon et par heure d'arrivée, de l'isolation à la levée plus une heure (lecture seule, **avant le 10/12**) | une quarantaine perdue : la relecture de rattrapage (§7) ne trouve rien, et le dit |
| **RH5** | la quarantaine retient la télémétrie de l'invité : aucune ligne `Heartbeat` de bree datée sous la quarantaine (avant 15:54:10) n'est arrivée à temps | `Heartbeat` de bree sur la même fenêtre, heure et arrivée (lecture seule, **avant le 11/12**) | s'il y en a, l'agent passait la quarantaine : le bloc vient d'ailleurs (la règle de collecte, l'ingestion), les points 1 à 3 et 5 à 6 du §7 tombent, et Q7 avec eux |
| **RH6** | après une quarantaine courte (une isolation d'exercice), le rattrapage est le même | la levée du T1486 du 09/11 sur gondolin, les mêmes requêtes (lecture seule, **avant le 09/12**) | l'horizon dépend de la durée de la quarantaine |
| **RH7** | `AzureActivity` arrive en 3 à 20 min (A1 d'ID1), Entra en quelques minutes (E3) | le protocole d'ID1 (`docs/operations.md`, « Les requêtes de mesure »), p95 sur 24 h | au-delà de 45 min : ING7, et le piège de `entra-sp-unusual-signin` |
| **RH8** | `StorageBlobLogs` arrive sous 5 min, la fenêtre de `data-exfiltration-blob` | la même requête sur 30 jours, là où le T1041 a tourné (lecture seule) | ING3 la couvre déjà ; à dire |
| **RH9** | l'agent date une ligne `Syslog` à sa réception, pas par l'heure écrite dans la ligne | une ligne `logger` datée à la main sur une VM du banc (un geste de Jonathan, non destructif) | une ligne datée par root : l'horizon et la fin de la fenêtre se contournent, à dire au modèle de menace |
| **RH10** | la requête de `ransomware-disk-write` sur 130 min, le tri et le `join` de `ssh-brute-force`, et la vue du retard sur 48 h, rendent en quelques secondes | `glorfindel rules check --live`, après ING3 | `H` baisse, ou la règle change de forme |
| **RH11** | `ingestion_time()` est rempli sur `Perf`, `Syslog`, `StorageBlobLogs` (la documentation) ; le SDK rend les colonnes d'heure en `datetime` | une requête sur chaque table ; un test du type de la colonne | une table sans arrivée garde sa fenêtre sur l'heure, et la note du chargement le dit |
| **RH12** | le silence normal de `Syslog` par VM (le plus long écart entre deux lignes, par facilité, sur une VM calme) ; la période de `Heartbeat` | les écarts entre lignes consécutives, par VM, sur 7 jours (lecture seule) | rien pour `Syslog` (jamais de carte de silence, §8) ; la période de `Heartbeat` fixe le seuil de « muette » |

**L'ordre de la mesure.** RH5, RH3, RH4, puis RH6 d'abord : leurs données partent les premières, et
RH5 conditionne le §7. Le
protocole sera `docs/banc-retard.md` (ING5) : les requêtes exactes, que Jonathan lance depuis le poste
; rien n'écrit sur Azure. RH3 à RH5 se font en même temps que DOS8, sur la même VM et les mêmes
jours.

---

## 11. Les lots de code proposés

Dans l'ordre. Les mutants sont comptés ; l'Orchestre donne les plages.

| Lot | Session | Contenu | Ce qu'il prouve | Mutants |
|---|---|---|---|---|
| **ING2** — la sélection à l'arrivée dans le RulePoller | Glorfindel | `late_s` validé au chargement (la base et la couche du client), ignoré et dit sur une requête qui ne filtre pas sur l'arrivée dans une forme reconnue (§3.4), ou hors de `0 < late_s <` fenêtre, ou au-delà de 6 h ; les deux expirations ; les colonnes `Ing*` retirées de la ligne avant le routage, l'identité et le signal, rangées dans une table à côté des lignes, passée à `correlation.settle`, et écrites dans `signal_timing.jsonl` (30 jours), chemin que le `conftest` redirige (HY1) ; la note du chargement pour une règle du plan des données sans `late_s` ; `kql_subset` gagne `ingestion_time()` (une colonne cachée de la ligne de test) ; la doc. **Aucune règle livrée ne change** | le message au modèle identique à l'octet ; une ligne jamais jugée deux fois, sur un faux qui livre en retard | **6** : l'identité agrégée expirée avec l'horizon (une seconde rafale tue) ; l'identité d'événement expirée à `N + 300 s` (une ligne rejugée) ; `late_s` admis sans `ingestion_time()` ; `late_s` admis sur une requête qui ne fait qu'`extend Arrived = ingestion_time()` (la garde textuelle) ; une colonne `Ing*` laissée dans la ligne ; `signal_timing.jsonl` élagué avec `dispatched` (l'après-coup du dossier ne le trouve plus) |
| **ING3** — les règles du plan des données | Glorfindel | les neuf règles de `Perf`, `Syslog` et `StorageBlobLogs` (§2.1) dans la forme du §3.3, `late_s` selon Q2 ; la paire jugée à l'arrivée de son dernier échantillon ; le brute force par fenêtre glissante (Q10) ; `_LOGINS` de COR1 ancrée sur l'heure des échecs (Q9) ; les colonnes rendues inchangées (un test les compare) ; la copie sudo du banc refaite ; `kql_subset` gagne ce que lisent `ransomware-disk-write` et `ssh-brute-force` (`order by`, `prev`, `next`, `row_cumsum`, `join kind=leftouter`, `minif`, `max_of`, `between` sur des colonnes), sinon un oracle en Python ; la levée du 11/11 rejouée en données de test, aux retards du relevé | la levée du 11/11 détectée sur l'écriture de 15:56 à 16:06 seule ; dix échecs étalés sur 2 h ne tirent pas ; dix échecs en 5 min arrivés dans le désordre tirent ; la connexion livrée dans le même bloc que son brute force marque la compromission | **9** : la borne de l'arrivée retirée de `ransomware-disk-write` (le 11/11 de nouveau aveugle) ; la paire jugée à l'arrivée de son échantillon d'après, pas du dernier arrivé ; le brute force compté sur l'horizon (le filet de 2 h tire) ; le brute force compté vers l'arrière seulement (les cinq récents arrivés d'abord : jamais de carte) ; la borne de l'arrivée retirée de `t1136-001-…` (le `useradd` du démarrage, arrivé après la levée, tue) ; celle de `data-exfiltration-blob` retirée ; `_LOGINS` ancrée sur la passe (la connexion du bloc perdue) ; le filtre par ligne de COR1 retiré (une connexion d'avant le premier échec marque la compromission) ; `Step` calculé sur toute la fenêtre de 130 min sans garde (une série à 60 s avec un rattrapage passe en pas fin et rate une attaque : le test d'une série à 60 s avec un rattrapage) |
| **ING4** — le retard vu | Glorfindel, puis Console | la requête du §8 toutes les 5 min (Q4), l'état par VM et par table, la cadence déclarée par table (`Perf` en v1), les VM en quarantaine à part, le rattrapage après une levée ; les cartes « au-delà de l'horizon » et « muette », au passage dans l'état ; le rattrapage pour LEV ; la tuile et la section des règles de la console | une VM dont `Perf` se tait sous un `Heartbeat` vivant fait une carte ; une VM en quarantaine n'en fait pas ; un `Syslog` calme n'en fait pas | **7** : une VM en quarantaine en carte ; une ligne au-delà de l'horizon sans carte ; la vue bornée à `N + H` (une ligne arrivée avec 3 h de retard ne fait pas de carte) ; la carte « au-delà de l'horizon » refaite à chaque passe ; une table à cadence muette lue « à l'heure » quand `Heartbeat` arrive ; un `Syslog` calme lu « muette » ; une requête en échec lue « à l'heure » |
| **ING5** — la mesure | Tests, gestes de Jonathan | `docs/banc-retard.md` : RH1 à RH8 et RH12 en lecture seule sur les données gardées, RH3 à RH6 d'abord ; RH9 (un geste) ; RH10 après ING3 ; les résultats reportés au §10 | RH1 à RH10, RH12 | **0** |
| **ING6** — les règles autorées | Glorfindel | la note du §3.4 à l'approbation d'une proposition (`approve-rule`, la console) et dans `rules check` ; le prompt d'autorat inchangé (Q5) | une proposition sur `TimeGenerated` seulement est approuvée, et c'est dit | **2** : la note absente à l'approbation ; la note absente au chargement de la couche du client |
| **ING7** — le plan de contrôle et les identités (si RH7 le demande) | Glorfindel | les neuf règles d'`AzureActivity` et d'Entra dans la même forme ; la base de `entra-sp-unusual-signin` lue par l'arrivée (« connue » = arrivée avant la fenêtre) ; les deux copies du banc refaites, et le geste | une connexion arrivée 70 min en retard n'entre pas dans sa propre base | **3** (estimés) |

**Total** : 24 mutants pour ING2 à ING6 ; 3 de plus si ING7 part. Deux mutants de plus reviennent à
LEV4 (la borne de la probation, §7, point 4). La relecture de rattrapage de la
probation (§7, point 6) est à LEV4, avec ses propres mutants.

**L'ordre.**
- **ING5 tout de suite**, en même temps qu'ING2 : les données de la levée du 11/11 partent vers le
  11/12, celles de la quarantaine de bree vers le 10/12, celles du 09/11 vers le 09/12. Comme DOS8, sur
  la même VM.
- **ING3 après ING2**, et après RH2 et RH3 : l'horizon se fixe sur le retard mesuré de `Syslog` et du
  rattrapage (Q2).
- **ING4 après ING2** (les colonnes `Ing*` gardées à côté), en parallèle d'ING3.
- **ING6 après ING3.**
- **Les lots de DOS1** : **DOS5 et DOS9 après ING2**. DOS5 (la série de l'invité par minute, F2) et
  DOS9 (la garde de l'hôte sur `ransomware-disk-write`, si la Q1 de DOS1 vaut B) ancrent leurs fenêtres
  sur `T` ; pour une règle agrégée, `T` est `IngFirstAt`, qu'ING2 garde. Sans lui, ils liraient les
  minutes d'après, et une garde de corroboration pourrait retenir ou confirmer à tort. `signal_delay`
  (F6) est un fait local de **DOS3**, `sans_objet` tant qu'ING2 n'est pas là.
- **LEV4 attend ING3 et ING4** : la réisolation ne voit le démarrage qu'avec ING3, et le rattrapage
  qu'avec ING4. LEV3 peut partir avant, en disant le cas 2 et sa condition (§7, point 2).
- **Le jalon** : 0.6.x. ING2 et ING3 touchent le RulePoller, comme LEV4 : l'Orchestre tient l'ordre
  des fusions.

---

## 12. Les questions à Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est
décidé à sa place.

**Q1 — Le mécanisme** (§3)
1. **Jugée à l'arrivée, agrégée à l'heure, dans le texte de la règle, avec `late_s` déclaré
   (recommandée).** La règle se lit et se lance seule ; les seuils gardent leur sens ; aucune requête
   de plus ; la déduplication se prouve (§4). Chaque règle est réécrite, et la copie sudo du banc avec.
2. `TimeGenerated > ago(N) or ingestion_time() > ago(N)`. Une ligne à changer par règle, mais les
   agrégats mêlent des heures éloignées, la fenêtre de l'API reste à élargir, et une ligne d'une VM à
   l'horloge en avance est rejugée.
3. Une fenêtre de rattrapage au RulePoller. **Aucune règle ne change** : les règles du client, les
   règles autorées et les copies du banc sont couvertes telles quelles, sans dérive de `base_sha256` ni
   geste WL1. En échange, une requête de plus par passe (+70 %), un RulePoller qui réécrit un KQL qu'il
   ne lit pas, et des agrégats qui mêlent encore des heures.
4. Un curseur d'arrivée : la watch pose devant chaque règle la date de sa dernière passe réussie
   (`let arrived_since = datetime(…)`). Exact, même après une coupure de la watch ; mais la règle ne se
   lance plus seule (ni l'opérateur, ni `rules check`, ni `campaign_replay`), et chacune est réécrite.

**Q2 — L'horizon de retard (`late_s`)** (§3.3, §5, §7)
1. **2 h maintenant, revu après RH4 et RH6 (recommandée).** Trois fois le rattrapage du 11/11 avec la
   marge de LEV (environ 38 min). ×13 lignes lues, côté serveur. Le chiffre repose sur un seul relevé,
   après 35 à 37 h de quarantaine : la mesure le corrige.
2. 1 h. Une fois et demie ; ×7 ; la même heure que le plan de contrôle.
3. 6 h. Une levée humaine dans la journée ; ×37, et des détections de lignes vieilles de plusieurs
   heures.
4. Ne le fixer qu'après RH4 et RH6 : ING3 attend la mesure, le trou reste ouvert d'ici là.

**Q3 — Quelles règles d'abord** (§2.1, §11)
1. **Les neuf du plan des données (`Perf`, `Syslog`, `StorageBlobLogs`) dans ING3 ; le plan de contrôle
   et les identités après la mesure de RH7 (recommandée).** Le trou mesuré est celui de `Perf` ; une
   seule copie du banc à refaire.
2. Les dix-huit dans ING3. Le piège d'`entra-sp-unusual-signin` fermé tout de suite ; trois copies du
   banc et une fenêtre d'une heure déjà large pour un retard documenté de 20 minutes.
3. `Perf` et `Syslog` seulement (huit). `StorageBlobLogs` attend RH8, malgré sa fenêtre de 5 minutes.

**Q4 — Le retard lui-même** (§8)
1. **Un état par VM et par table, lu sur 48 h de `TimeGenerated` ; une carte, au passage dans
   l'état, seulement quand des lignes arrivent au-delà de l'horizon, ou quand une table à cadence
   (`Perf`) se tait alors que `Heartbeat` arrive ; jamais sur le silence de `Syslog` ; un fait du
   dossier et de la probation (recommandée).** Ce qui n'est pas jugé est dit, jusqu'à 48 h de retard ;
   un retard jugé quand même, ou une VM calme, ne fait pas de bruit. Le prix : 48 h de trois tables
   lues côté serveur toutes les 5 minutes.
2. Une carte dès qu'un bloc arrive avec plus de `N` de retard. Le plus visible ; une carte à chaque
   levée, et à chaque lenteur d'Azure.
3. Rien de neuf : seulement le fait du dossier. Le moins de code ; une VM dont `Perf` se tait sous un
   `Heartbeat` vivant reste invisible.

La fenêtre de la vue, sous l'option 1 : 48 h (recommandée), 7 jours (une quarantaine plus longue, sept
fois plus lu), ou `N + H` — à écarter : la carte « au-delà de l'horizon » ne se ferait jamais.

**Q5 — Les règles autorées** (§6)
1. **Le code dit la forme manquante, à l'approbation et dans `rules check` ; la règle est approuvée
   quand même ; le prompt d'autorat ne change pas en v1 (recommandée).** Déterministe, sans toucher
   à ce que le modèle écrit.
2. L'approbation refuse une règle du plan des données sans sélection par l'arrivée. Plus sûr ; une
   proposition juste mais sur l'heure ne s'approuve plus sans être réécrite à la main.
3. Le prompt d'autorat demande la forme. Les propositions arrivent justes ; un changement de ce que le
   modèle écrit, avec son harnais (`make llm-compare`, par toi).

**Q6 — La copie sudo du banc** (§6)
1. **Refaite dans la PR d'ING3 ; ton geste `make glorfindel-host-client-rules` juste après que le CD
   a déployé la release ; les cartes de la maintenance de bree reviennent entre les deux
   (recommandée).** Rien n'est caché ; le geste est celui que WL1 prévoit.
2. La règle sudo à part : hors d'ING3, sa copie reste intacte, et la règle sudo reste aveugle au
   retard jusqu'à un lot qui la touche.

**Q7 — Le démarrage sous la quarantaine, pour LEV4, si RH5 tient** (§7)
1. **Une relecture de rattrapage au début de la probation, sur `[fin du restore, maintenant]`, une
   fois le rattrapage de l'agent fini, par la réécriture des `ago()` de `campaign_replay`, assumée et
   bornée aux règles dont les `ago()` sont leurs deux bornes ; plus la forme d'ING3 pour le cas courant
   (recommandée).** Elle couvre une levée humaine tardive, les copies du banc et les règles du client
   écrites dans la forme d'ING3, et dit ce qui n'est jamais arrivé. Une règle restée sur
   `TimeGenerated` seul (une règle du client d'avant ING3, une règle autorée) en est exclue, et la
   carte de probation la nomme.
2. La même relecture par un `probation_query` à bornes absolues (`let since …; let until …;`). Aucune
   réécriture ; un second texte par règle, qui ne se lance pas seul, et rien pour une règle qui n'en a
   pas.
3. Un horizon de probation qui suit le temps passé en quarantaine : tant que la VM est en probation,
   ses règles lisent depuis la fin du restore. Pas de relecture à part ; mais la watch réécrit l'horizon
   à chaque passe, pour cette VM, et le volume lu grandit avec la quarantaine.
4. L'horizon d'ING3 seul. Le plus simple ; une levée humaine plus tardive que l'horizon laisse le
   démarrage sans juge.

**Q8 — L'enquête d'une détection arrivée en retard** (§2.3, §3.5)
1. **Inchangée en v1 ; le retard est dit au dossier, pour l'humain, jamais au modèle (recommandée).**
   Le modèle voit ce qu'il voit aujourd'hui ; on mesure d'abord combien de détections arrivent en
   retard.
2. Ancrer les fenêtres d'`investigate` sur l'heure des lignes (`IngFirstAt`). L'enquête lirait les
   bonnes minutes ; elle change ce que voit le modèle : un lot à part, avec son run de bout en bout
   T1486 et un autre TTP, par toi.

**Q9 — Les connexions après un brute force, dans le même bloc** (§2.3, §3.4)
1. **`_LOGINS` ancrée sur l'heure des échecs : une requête par VM depuis le plus ancien `IngFirstAt`
   de ses brute forces, bornée par l'horizon, puis un filtre par ligne, `at >= IngFirstAt` de ce
   brute force, à écrire dans `tag_compromise` (recommandée).** Une connexion livrée dans le même
   bloc que son brute force marque la compromission ; une connexion d'avant son premier échec, non.
   `IngFirstAt` arrive à COR1 par la table à côté des lignes (§3.4), pas par la ligne.
2. La fenêtre de la passe, sans l'horizon, comme aujourd'hui. Rien ne change ; la compromission livrée
   en retard avec son brute force est perdue, et c'est dit au modèle de menace.
3. La fenêtre entière, horizon compris. Simple ; une connexion de la même adresse jusqu'à 2 h **avant**
   le brute force marque la compromission à tort.

**Q10 — Le sens nouveau de `ssh-brute-force`** (§3.3)
1. **Une fenêtre glissante : la règle tire s'il existe 10 minutes qui tiennent 10 échecs du couple,
   dont un frais (recommandée).** Le seuil garde son sens, quel que soit l'ordre d'arrivée. Elle change
   des détections : une rafale ancienne, arrivée en retard, tire ; `FailedAttempts` compte la rafale.
2. Le décompte des échecs **arrivés** dans les 10 dernières minutes (la piste 1). Plus simple ; dix
   échecs étalés sur 2 h et livrés d'un bloc tirent, et une rafale livrée en deux blocs peut ne jamais
   tirer.
3. Ne pas toucher à `ssh-brute-force` dans ING3. Son sens d'aujourd'hui reste ; elle reste aveugle au
   retard.
