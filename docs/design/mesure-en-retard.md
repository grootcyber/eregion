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
d'une mesure faite au banc, et le dit. Tout le reste est une **hypothèse**, numérotée RH1 à RH11
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
  règles concernées (130 min au lieu de 10), et en rend autant qu'avant. Les plafonds de SEC2 et de
  SEC-A2 ne bougent pas. Une seule requête de plus, toutes les 5 minutes, pour voir le retard (§8).
- **Ce que voit le modèle** : rien de neuf dans sa forme. Les colonnes rendues par chaque règle restent
  les mêmes ; les heures du retard sont retirées de la ligne avant le signal et gardées à côté. Ce qui
  change, c'est quelles lignes deviennent des détections.
- **Ce que LEV3 et LEV4 doivent en tirer** (§7) : sous la quarantaine, la télémétrie de l'invité
  n'arrive pas ; elle arrive après la levée, en retard. Le cas 2 de LEV (une détection entre la fin du
  restore et la levée) ne peut pas venir de `Perf` ni de `Syslog`. La réisolation de la probation, elle,
  ne voit ces lignes qu'avec ce mécanisme, et une levée humaine tardive demande une relecture de
  rattrapage.
- **Le retard lui-même se voit** (§8) : un état par VM et par table ; une carte seulement quand des
  lignes arrivent au-delà de l'horizon (jamais jugées), ou quand une table se tait alors que
  `Heartbeat` arrive ; un fait du dossier de DOS1 et de la probation.
- **Six lots de code** (§11), ING2 à ING7, dont un de mesure et un conditionnel. **Huit questions**
  pour Jonathan (§12).

---

## 1. Le cas qui fonde le lot : la levée de bree, le 11/11

### 1.1 Le relevé

Mesuré le 12/11, en lecture seule, par la session Tests avec Jonathan (heures des sources) :

- bree a été levée le 11/11 à **15:54:10**, après 35 h d'isolation ;
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
  a été retenu** ;
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
  étaient déjà hors des deux fenêtres à leur arrivée. **Ils n'ont jamais été jugés.** La détection de
  16:17:18 s'est faite sur les échantillons de 16:07 à 16:14.
- **La déduplication** n'explique pas le trou : la ligne de la règle est agrégée
  (`summarize MaxWrite = max(Peak) by Computer, _ResourceId`, `:80`), son identité est la VM
  (`_row_identity`, `detection_rules.py:1148-1152`). Elle peut retenir une carte, jamais faire
  manquer une ligne à la requête.

### 1.3 Ce que ça veut dire

- **Une écriture de 10 minutes, de 15:56 à 16:06, n'aurait fait aucune détection.** Ce soir-là, la
  règle a tiré 21 minutes après le premier échantillon, et seulement parce que l'écriture a duré 18
  minutes.
- **Ce n'est pas un retard d'ingestion ordinaire.** Le retard normal de `Perf` (55 à 108 s le 12/11,
  89 à 109 s le 05/10) tient largement dans la fenêtre. C'est un bloc retenu, puis livré d'un coup,
  juste après une quarantaine.
- **C'est le pire moment.** Une levée ouvre la probation de LEV1 (la VM restaurée, en service sous
  surveillance renforcée). Les minutes qui arrivent en retard sont celles de la probation, et celles
  sous la quarantaine : le démarrage du disque restauré, où une persistance se déclenche
  (`levee-probation.md`, §6.3).

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
plus courte que 30 minutes est dite au chargement (`MIN_LOOKBACK_S`, `activity.py:60`,
`entra.py:56` ; `detection_rules.py:938-946`). Aucune borne de cette sorte pour le plan des données.

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
| la corrélation de COR1 (`correlation.py:293-300`, `:501-522`) | la fenêtre de la passe, que le RulePoller lui passe (`detection_rules.py:1681-1682`) | ses connexions après un brute force arrivées en retard ne sont pas lues | ING2 lui passe la fenêtre **sans** l'horizon : sinon une connexion de la même adresse 2 h plus tôt marquerait la compromission |
| la découverte (`discovery.py:172`) | `Heartbeat`, `ago(2h)` | rien : `Heartbeat` est arrivé à temps le 11/11 | rien |
| `poll_detection` sur un `attack_started` | `timespan` depuis le T0 de l'attaque (`monitor.py:61-64`), plus la fenêtre de la règle | la fenêtre de la règle coupe une ligne en retard, comme au RulePoller | suit la règle |
| `glorfindel rules check` (`rule_check.py:214-218`) | la fenêtre du RulePoller | la même | suit la règle, rien à changer |
| `campaign_replay` (`campaign_replay.py:44-46`, `:95-100`) | chaque `ago()` réécrit pour remonter au T0 | la sélection à l'arrivée remonte aussi au T0 : juste pour un rejeu | à dire dans le lot |

### 2.4 Ce qu'on sait du retard de chaque source

| Source | Qui la livre | Ce qu'on sait | D'où | Statut |
|---|---|---|---|---|
| `Perf` | l'agent de la VM | 55 à 108 s en temps normal (12/11) ; 89 à 109 s (05/10) ; un bloc jusqu'à 1 610 s juste après une levée | le relevé de la fiche ; `detection_rules.py:1056` | **mesuré**, deux fois ; le bloc, une fois |
| `Syslog` | l'agent de la VM | `expected_latency_s: 480` (`detection_rules.yaml:25`) ; détections de bout en bout : T1110 à T0+~125 s (07/10, `docs/glorfindel.md`), T1136.001 en 144 s (31/10, `docs/demarrer/banc.md`) | l'en-tête des règles ne cite aucune mesure ; les détections bornent le retard ces jours-là | **non mesuré** en temps normal, ni après une levée (RH2, RH3) |
| `Heartbeat` | l'agent de la VM | 2 à 10 s, le 11/11, autour de la levée | le relevé | mesuré une fois ; sous la quarantaine, à lire (RH5) |
| `StorageBlobLogs` | la plateforme (le stockage) | `expected_latency_s: 90` ; « latence variable » (le T1041, `docs/historique.md`) | aucune mesure chiffrée | **non mesuré** (RH8) |
| `AzureActivity` | la plateforme | 3 à 20 min (Microsoft Learn, hypothèse A1 d'ID1) ; « minutes, parfois plus de dix » (`activity.py:39-40`) | la documentation | **non mesuré** : le protocole existe (`docs/operations.md`, « Les requêtes de mesure »), pas son résultat (RH7) |
| Entra (`AuditLogs`, `AADServicePrincipalSignInLogs`) | la plateforme | « quelques minutes (lots d'environ 5 min) », hypothèse E3 d'ID1 | la documentation | **non mesuré** (RH7) |

**Le partage qui compte.** `Perf`, `Syslog` et `Heartbeat` passent par l'agent de la VM, que la
quarantaine coupe : le NSG de quarantaine refuse tout en sortie
(`glorfindel/providers/azure/quarantine.py:17-19`, `docs/azure.md`). Les autres sources viennent de la
plateforme, que la quarantaine ne touche pas. Le bloc du 11/11 est celui de l'agent.

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
| **2. `TimeGenerated > ago(N) or ingestion_time() > ago(N)`** | ce que juge 1 ; plus une ligne datée dans le futur par l'horloge de la VM | comme 1 (la branche de l'heure n'ajoute rien quand l'arrivée suit l'heure) | comme 1 ; et l'agrégat mêle les lignes à l'heure et le bloc en retard |
| **3. Une fenêtre de rattrapage au RulePoller** (une seconde requête par passe, décalée vers le passé) | les lignes en retard, par une seconde lecture | ce que la réécriture du texte rate : le RulePoller réécrirait les `ago()` d'une requête qu'il ne lit pas (la leçon de P1 : suivre le KQL par des expressions régulières ne converge pas) | **une requête de plus par règle et par passe** (§5) ; une double lecture à dédupliquer |
| **3 bis. Un curseur d'arrivée** (le RulePoller pose `let arrived_since = datetime(…)`, la dernière passe réussie) | exactement ce qui est arrivé depuis la dernière passe, même après une coupure de la watch | rien de plus | **la règle ne se lit plus seule** : ni l'opérateur (`az monitor log-analytics query`), ni `rules check`, ni `campaign_replay` ne la lancent telle qu'écrite |
| **4. Jugée à l'arrivée, agrégée à l'heure** (§3.3, recommandée) | chaque ligne, à son arrivée, jusqu'à l'horizon ; chaque agrégat à l'arrivée de sa dernière ligne | une ligne au-delà de l'horizon (dite, §8) ; une ligne arrivée pendant une coupure de la watch plus longue que la fenêtre (comme aujourd'hui) | ×13 lignes lues par le serveur pour les règles concernées, autant de lignes rendues qu'avant ; aucune requête de plus |

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

**`ssh-brute-force`** : le seuil est « 10 échecs en 10 minutes ». Chaque échec arrivé dans les 10
dernières minutes compte les échecs du même couple (adresse, VM) dans les 10 minutes qui le précèdent,
sur `TimeGenerated`, lus sur tout l'horizon ; la règle tire quand ce compte atteint 10, et rend
`FailedAttempts` (le nom que COR1 lit, `correlation.py:511`). Dix échecs étalés sur 2 h et arrivés
d'un bloc ne tirent pas ; dix échecs en 5 minutes arrivés en deux blocs tirent à l'arrivée du second. La
forme KQL (un `join` des échecs frais sur ceux de l'horizon, par couple, borné par l'heure) est celle
du lot ING3, prouvée par `tests/unit/kql_subset.py`, qui lit déjà `let`, `join kind=inner` et
`between` (sa docstring) ; une borne par l'expression d'une colonne y est à vérifier.

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
| la fenêtre passée à COR1 (`:1681-1682`) | fenêtre de l'API | `N` + 300 s, comme aujourd'hui |
| les colonnes `Ing*` de la ligne | — | retirées de la ligne **avant** le routage, l'identité et le signal ; gardées à côté du signal (§3.5) |

**`late_s` est validé au chargement** (la validation de P1, `_invalid_client_entry`,
`detection_rules.py:423-478`, et `load_config` pour la base) : un entier de secondes, `0 < late_s <`
le plus long `ago()`, au plus 6 h ; et la requête lit `ingestion_time()` dans son code (commentaires
exclus, comme `_query_lookback_s`). Sinon `late_s` est ignoré et c'est dit
(« règle … : `late_s` ignoré, la requête ne lit pas `ingestion_time()` ») : la règle tourne avec `N` =
sa fenêtre entière, la déduplication d'aujourd'hui. **Jamais l'inverse** : une règle qui déclare un
horizon sans sélectionner par l'arrivée garderait ses lignes agrégées sélectionnables 2 h, et une
expiration de 15 minutes les rejugerait (§4).

**Une règle du plan des données sans `late_s`** se charge comme aujourd'hui, et c'est dit (une note,
comme `MIN_LOOKBACK_S`) : « règle … : jugée sur `TimeGenerated` seulement ; une ligne arrivée plus de
N min après son heure n'est jamais jugée ». Le plan de contrôle et les identités n'ont pas cette note
tant que leur retard mesuré tient dans leur heure (ING7).

### 3.5 Ce que le modèle voit

- **La forme ne change pas.** `_build_user_message()` écrit le signal entier, en JSON
  (`agent.py:3033-3035`), ligne de la règle comprise (`raw_signal.first_result_row`). Une colonne de
  plus dans la ligne serait vue du modèle. Les colonnes `Ing*` sont donc **retirées de la ligne** avant
  le signal, et gardées à côté : dans l'enregistrement de l'envoi (`rule_status.json`, à côté de
  `dispatched`, par `signal_id`), où DOS et LEV les lisent. Un test fige le message, à l'octet, pour
  une ligne donnée. Ni `_SYSTEM_PROMPT`, ni `few_shot_examples.yaml`, ni `_build_user_message()` ne
  changent.
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
- Une arrivée dans le désordre (l'échantillon d'avant arrivé après celui d'après) peut faire rejuger
  une paire : au plus une carte de plus, après l'expiration, jamais une de moins.

**Ce qui n'est pas jugé, et le dit.**
- Une ligne arrivée plus de `H` après son heure : la borne de l'heure la coupe. Le retard est vu
  (§8), une carte le dit.
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

**Le volume lu par le serveur.** `N + H = 130 min` au lieu de 10 : **×13** pour chaque règle qui
déclare `late_s` (×7 pour un horizon d'1 h, ×37 pour 6 h). Au banc, un échantillon toutes les 10 s par
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
remarque que DOS1, §7) ; sur une table `Basic` ou `Auxiliary`, la requête se paie, et ×13 aussi. Pas
le cas du banc.

**La durée d'une requête.** Celle de `ransomware-disk-write` sur 130 minutes, et du `join` de
`ssh-brute-force`, est à mesurer (RH10) : `glorfindel rules check --live` la donne, règle par règle.

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

La probation suit une levée ; ce sont justement les minutes qui arrivent en retard.

1. **Sous la quarantaine, la télémétrie de l'invité n'arrive pas.** Le NSG de quarantaine refuse
   tout en sortie (§2.4). Le 11/11, les échantillons pris sous la quarantaine (15:50 à 15:54) sont
   arrivés 22 min 40 s après la levée. Ce que l'agent garde des 35 h, et combien de temps il le
   garde, n'est pas mesuré (RH4).
2. **Le cas 2 de LEV ne peut pas venir de l'invité.** « Une détection sur la VM datée après la fin du
   restore » retient la levée (`levee-probation.md`, §3.1). La VM restaurée démarre sous la
   quarantaine (§6.3 de LEV) : ses lignes `Perf` et `Syslog` n'arrivent qu'**après** la levée. Avant la
   levée, le cas 2 ne voit que le plan de contrôle. **LEV3 doit le dire** : la marge
   `lift.log_settle_s` (900 s, Q14 de LEV) attend le journal d'activité, pas l'invité.
3. **Le démarrage se juge donc en probation, et seulement avec ING3.** LEV le dit déjà : « Sa
   télémétrie peut arriver après la levée, avec un moment d'avant ; elle compte » (§6.3). Avec les
   fenêtres d'aujourd'hui, une ligne `useradd` du démarrage, arrivée 23 minutes après la levée avec une
   heure plus vieille encore, n'est jamais jugée. **ING3 est une condition de LEV4.**
4. **Le moment d'une détection.** La borne de la probation (« un signal dont le moment est après la fin
   du job de restore ») lit l'heure des lignes : `TimeGenerated` pour une règle d'événements,
   `IngFirstAt` (gardé à côté du signal, §3.5) pour une règle agrégée — **jamais** le `timestamp` du
   signal, qui est l'heure de la passe (`detection_rules.py:1891`). Un mutant de LEV4.
5. **L'horizon face à la levée.** Le retard d'une ligne du démarrage, à son arrivée, vaut le temps
   passé sous la quarantaine après le restore, plus le rattrapage de l'agent.
   - En `non_disruptive`, Imladris lève après la fin du job plus 15 minutes : avec le rattrapage du
     11/11 (22 min 49 s, de la levée à la fin du bloc), environ 38 minutes. **Dans l'horizon de 2 h.**
   - En `human_only`, ou sur une retenue, un humain lève des heures plus tard : **au-delà de
     l'horizon.** Les lignes du démarrage ne sont jugées par aucune règle.
6. **Donc une relecture de rattrapage, propre à la probation** (recommandée, Q7). Au début de la
   probation, une fois le rattrapage de l'agent fini (la vue du retard, §8, voit les tables de la VM
   arriver de nouveau au fil de l'eau), les règles de probation tournent **une fois** sur la fenêtre
   absolue `[fin du restore, maintenant]` (un `timespan` absolu, comme le dossier de DOS1, §3.1), leurs
   détections par `_probation_decision`. Si le rattrapage ne finit pas, ou si des heures manquent
   (l'agent les a perdues), c'est un fait de la carte de probation : « les mesures de la VM sous la
   quarantaine ne sont jamais arrivées, de … à … ».
7. **La déduplication agrégée** (§4) : une rafale de `ransomware-disk-write` sur la VM restaurée,
   après la levée, refait une carte dès que `N + 300 s` sont passés depuis la carte de l'incident. Le
   restore prend environ 20 minutes : c'est déjà le cas. La piste 0 l'aurait cassé.
8. **La carte de début de probation** dit l'état du rattrapage, à côté de la règle des ports et des
   disques d'origine (`probation_started`, §3.1 de LEV).

À reporter dans LEV3 (le cas 2, la marge) et LEV4 (la borne par l'heure des lignes, la relecture de
rattrapage) : l'Orchestre route ces points vers la session Glorfindel.

---

## 8. Le retard lui-même : un état, un fait, une carte au-delà de l'horizon

**Pourquoi le voir.** Le 11/11, `Heartbeat` est arrivé à temps pendant que `Perf` était retenu : la VM
semblait vivante et bien suivie, et elle ne l'était pas. Le retard est un fait de la plateforme
(`ingestion_time()` est écrit par Log Analytics, pas par l'invité), et la seule façon de dire ce qui
n'a pas été jugé.

**La vue du retard** (ING4). Une requête toutes les 5 minutes, pour toute la watch, sur les lignes
**arrivées** dans les 10 dernières minutes de `Perf`, `Syslog` et `Heartbeat` : par VM et par table,
le nombre de lignes, le retard médian et maximal, et la plus vieille heure arrivée. Bornée par ce qui
est arrivé : quelques lignes par VM.

**Un état par VM et par table**, dans le statut de la watch, lu par la console :

| État | Quand | Ce qui suit |
|---|---|---|
| à l'heure | le retard maximal sous `N` | rien |
| en retard | le retard maximal au-dessus de `N`, sous l'horizon | un état, sur la tuile : « `Perf` de bree : 25 min de retard » ; les lignes sont jugées (ING3) |
| au-delà de l'horizon | une ligne arrivée plus de `H` après son heure | **une carte** : ces lignes n'ont été jugées par aucune règle (A0 : ce qui n'est pas jugé est dit) |
| muette | aucune ligne de `Perf` ou de `Syslog` depuis plus de `N`, alors que `Heartbeat` arrive | **une carte** : la VM semble suivie et ne l'est pas — le motif du 11/11 |
| illisible | la requête échoue | un état illisible, jamais « à l'heure » (A0) |

**Une VM en quarantaine** est mise à part : son silence est attendu. À sa levée commence son
**rattrapage**, suivi jusqu'à ce que ses tables reviennent « à l'heure » : c'est le fait que LEV4 lit
(§7, point 6).

**Un fait du dossier de DOS1.** Le dossier ancre ses fenêtres sur l'heure du signal, `T`
(`dossier-isolation.md`, §3.1). Pour une règle agrégée, `T` n'est pas dans la ligne : c'est
`IngFirstAt`, gardé à côté du signal. Un fait de plus, `signal_delay` (parmi ceux de la décision, F6) :
« la détection s'est faite sur des lignes arrivées avec jusqu'à 21 min de retard ; l'enquête a lu les
minutes d'après » — l'auteur est la plateforme, l'état `lu`. Et l'après-coup (F5) d'une isolation dit,
à sa levée, le rattrapage de la VM. Les deux restent pour l'humain, jamais pour le modèle.

**Sur la console** : l'état sur la tuile de la VM, et une ligne dans la section des règles. Un lot de
la console après ING4.

---

## 9. Le modèle de menace

| Ce que fait un attaquant | Ce qui le tient | Ce qui reste ouvert |
|---|---|---|
| root sur la VM arrête l'agent, agit, le relance : ses lignes arrivent en retard | jugées à leur arrivée, jusqu'à l'horizon (ING3) ; au-delà, la carte du §8 | ce que l'agent perd en route n'arrive jamais (RH4) |
| il ne coupe que `Perf` ou `Syslog`, et laisse `Heartbeat` | l'état « muette », une carte (§8) | — |
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
| **RH1** | le retard normal de `Perf` reste sous 2 min (55 à 108 s le 12/11) | p50, p95 et maximum de `ingestion_time() - TimeGenerated` sur 7 jours, par VM (lecture seule) | `N` à revoir pour `Perf` |
| **RH2** | le retard normal de `Syslog` tient sous `N` = 10 min ; l'en-tête dit 480 s sans mesure (`detection_rules.yaml:25`) | la même requête sur `Syslog`, par facilité, sur 7 jours (lecture seule) | `N` ou `H` à revoir pour `Syslog` |
| **RH3** | `Syslog` de bree a été retenu comme `Perf` autour de la levée du 11/11 | `Syslog` de bree de 15:40 à 16:40 le 11/11 : heure, arrivée, retard (lecture seule, **avant le 11/12**) | si `Syslog` arrivait à temps, le bloc est propre à `Perf` (une file de l'agent par flux ?) : le §7 se resserre sur `Perf` |
| **RH4** | ce que l'agent livre de la quarantaine : tout, une partie, rien des 35 h | `Perf` et `Syslog` de bree, comptés par heure de l'échantillon et par heure d'arrivée, de l'isolation à la levée plus une heure (lecture seule, **avant le 10/12**) | une quarantaine perdue : la relecture de rattrapage (§7) ne trouve rien, et le dit |
| **RH5** | aucune ligne `Heartbeat` de bree n'est datée sous la quarantaine (avant 15:54:10) | `Heartbeat` de bree sur la même fenêtre | s'il y en a, arrivées à temps, la quarantaine laisse passer `Heartbeat` et pas `Perf` : à comprendre avant tout le reste |
| **RH6** | après une quarantaine courte (une isolation d'exercice), le rattrapage est le même | la levée du T1486 du 09/11 sur gondolin, les mêmes requêtes (lecture seule, **avant le 09/12**) | l'horizon dépend de la durée de la quarantaine |
| **RH7** | `AzureActivity` arrive en 3 à 20 min (A1 d'ID1), Entra en quelques minutes (E3) | le protocole d'ID1 (`docs/operations.md`, « Les requêtes de mesure »), p95 sur 24 h | au-delà de 45 min : ING7, et le piège de `entra-sp-unusual-signin` |
| **RH8** | `StorageBlobLogs` arrive sous 5 min, la fenêtre de `data-exfiltration-blob` | la même requête sur 30 jours, là où le T1041 a tourné (lecture seule) | ING3 la couvre déjà ; à dire |
| **RH9** | l'agent date une ligne `Syslog` à sa réception, pas par l'heure écrite dans la ligne | une ligne `logger` datée à la main sur une VM du banc (un geste de Jonathan, non destructif) | une ligne datée par root : l'horizon et la fin de la fenêtre se contournent, à dire au modèle de menace |
| **RH10** | la requête de `ransomware-disk-write` sur 130 min, et le `join` de `ssh-brute-force`, rendent en quelques secondes | `glorfindel rules check --live`, après ING3 | `H` baisse, ou la règle change de forme |
| **RH11** | `ingestion_time()` est rempli sur `Perf`, `Syslog`, `StorageBlobLogs` (la documentation) ; le SDK rend les colonnes d'heure en `datetime` | une requête sur chaque table ; un test du type de la colonne | une table sans arrivée garde sa fenêtre sur l'heure, et la note du chargement le dit |

**L'ordre de la mesure.** RH3, RH4, RH5, puis RH6 d'abord : leurs données partent les premières. Le
protocole sera `docs/banc-retard.md` (ING5) : les requêtes exactes, que Jonathan lance depuis le poste
; rien n'écrit sur Azure. RH3 à RH5 se font en même temps que DOS8, sur la même VM et les mêmes
jours.

---

## 11. Les lots de code proposés

Dans l'ordre. Les mutants sont comptés ; l'Orchestre donne les plages.

| Lot | Session | Contenu | Ce qu'il prouve | Mutants |
|---|---|---|---|---|
| **ING2** — la sélection à l'arrivée dans le RulePoller | Glorfindel | `late_s` validé au chargement (la base et la couche du client), ignoré et dit sur une requête qui ne lit pas `ingestion_time()`, ou hors de `0 < late_s <` fenêtre, ou au-delà de 6 h ; les deux expirations (§3.4) ; la fenêtre de COR1 sans l'horizon ; les colonnes `Ing*` retirées de la ligne avant le routage, l'identité et le signal, gardées par `signal_id` ; la note du chargement pour une règle du plan des données sans `late_s` ; `kql_subset` gagne `ingestion_time()` (une colonne cachée de la ligne de test) ; la doc. **Aucune règle livrée ne change** | le message au modèle identique à l'octet ; une ligne jamais jugée deux fois, sur un faux qui livre en retard | **5** : l'identité agrégée expirée avec l'horizon (une seconde rafale tue) ; l'identité d'événement expirée à `N + 300 s` (une ligne rejugée) ; `late_s` admis sans `ingestion_time()` ; COR1 qui reçoit l'horizon ; une colonne `Ing*` laissée dans la ligne |
| **ING3** — les règles du plan des données | Glorfindel | les neuf règles de `Perf`, `Syslog` et `StorageBlobLogs` (§2.1) dans la forme du §3.3, `late_s: 7200` (Q2) ; la paire jugée à l'arrivée de son dernier échantillon ; le brute force glissant ; les colonnes rendues inchangées (un test les compare) ; la copie sudo du banc refaite ; `kql_subset` gagne ce que lit `ransomware-disk-write` (`order by`, `prev`, `join kind=leftouter`, `minif`, `max_of`), sinon un oracle en Python ; la levée du 11/11 rejouée en données de test, aux retards du relevé | la levée du 11/11 détectée sur l'écriture de 15:56 à 16:06 seule ; dix échecs étalés sur 2 h ne tirent pas | **5** : la borne de l'arrivée retirée de `ransomware-disk-write` (le 11/11 de nouveau aveugle) ; la paire jugée à l'arrivée de son échantillon d'après, pas du dernier arrivé (une arrivée dans le désordre tue) ; le brute force compté sur l'horizon (le filet de 2 h tire) ; la borne de l'arrivée retirée de `t1136-001-…` (le `useradd` du démarrage, arrivé après la levée, tue) ; celle de `data-exfiltration-blob` retirée |
| **ING4** — le retard vu | Glorfindel, puis Console | la requête du §8 toutes les 5 min (Q4), l'état par VM et par table, les VM en quarantaine à part, le rattrapage après une levée ; les cartes « au-delà de l'horizon » et « muette » ; le fait `signal_delay` pour DOS, le rattrapage pour LEV ; la tuile et la section des règles de la console | une VM muette sous `Heartbeat` vivant fait une carte ; une VM en quarantaine n'en fait pas | **4** : une VM en quarantaine en carte ; une ligne au-delà de l'horizon sans carte ; une table muette lue « à l'heure » quand `Heartbeat` arrive ; une requête en échec lue « à l'heure » |
| **ING5** — la mesure | Tests, gestes de Jonathan | `docs/banc-retard.md` : RH1 à RH8 en lecture seule sur les données gardées, RH3 à RH6 d'abord ; RH9 (un geste) ; RH10 après ING3 ; les résultats reportés au §10 | RH1 à RH10 | **0** |
| **ING6** — les règles autorées | Glorfindel | la note du §3.4 à l'approbation d'une proposition (`approve-rule`, la console) et dans `rules check` ; le prompt d'autorat inchangé (Q5) | une proposition sur `TimeGenerated` seulement est approuvée, et c'est dit | **2** : la note absente à l'approbation ; la note absente au chargement de la couche du client |
| **ING7** — le plan de contrôle et les identités (si RH7 le demande) | Glorfindel | les neuf règles d'`AzureActivity` et d'Entra dans la même forme ; la base de `entra-sp-unusual-signin` lue par l'arrivée (« connue » = arrivée avant la fenêtre) ; les deux copies du banc refaites, et le geste | une connexion arrivée 70 min en retard n'entre pas dans sa propre base | **3** (estimés) |

**Total** : 16 mutants pour ING2 à ING6 ; 3 de plus si ING7 part.

**L'ordre.**
- **ING5 tout de suite**, en même temps qu'ING2 : les données de la levée du 11/11 partent vers le
  11/12, celles du 09/11 vers le 09/12. Comme DOS8, sur la même VM.
- **ING3 après ING2**, et après RH2 et RH3 : l'horizon se fixe sur le retard mesuré de `Syslog` et du
  rattrapage.
- **ING4 après ING2** (les colonnes `Ing*` gardées à côté), en parallèle d'ING3.
- **ING6 après ING3.**
- **LEV4 attend ING3 et ING4** : la réisolation ne voit le démarrage qu'avec ING3, et le rattrapage
  qu'avec ING4. LEV3 peut partir avant, en disant le cas 2 (§7, point 2).
- **Le jalon** : 0.6.x. ING2 et ING3 touchent le RulePoller, comme LEV4 : l'Orchestre tient l'ordre
  des fusions.

---

## 12. Les questions à Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est
décidé à sa place.

**Q1 — Le mécanisme** (§3)
1. **Jugée à l'arrivée, agrégée à l'heure, dans le texte de la règle, avec `late_s` déclaré
   (recommandée).** La règle se lit et se lance seule ; les seuils gardent leur sens ; aucune requête
   de plus ; la déduplication se prouve (§4).
2. `TimeGenerated > ago(N) or ingestion_time() > ago(N)`. Une ligne à changer par règle, mais les
   agrégats mêlent des heures éloignées, et la fenêtre de l'API reste à élargir.
3. Une fenêtre de rattrapage au RulePoller. Les règles ne changent pas ; une requête de plus par passe
   (+70 %), et un RulePoller qui réécrit un KQL qu'il ne lit pas.
4. Élargir `ago()` à 2 h. Le plus simple ; les agrégats perdent leur sens, et une seconde rafale sur
   la même VM se tait 2 h.

**Q2 — L'horizon de retard (`late_s`)** (§3.3, §5, §7)
1. **2 h (recommandée).** Trois fois le rattrapage du 11/11 avec la marge de LEV (environ 38 min) ;
   mesuré une seule fois, et après 35 h de quarantaine. ×13 lignes lues, côté serveur.
2. 1 h. Une fois et demie ; ×7 ; la même heure que le plan de contrôle.
3. 6 h. Une levée humaine dans la journée ; ×37, et des détections de lignes vieilles de plusieurs
   heures.

**Q3 — Quelles règles d'abord** (§2.1, §11)
1. **Les neuf du plan des données (`Perf`, `Syslog`, `StorageBlobLogs`) dans ING3 ; le plan de contrôle
   et les identités après la mesure de RH7 (recommandée).** Le trou mesuré est celui de l'agent ; une
   seule copie du banc à refaire.
2. Les dix-huit dans ING3. Le piège d'`entra-sp-unusual-signin` fermé tout de suite ; trois copies du
   banc et une fenêtre d'une heure déjà large pour un retard documenté de 20 minutes.
3. `Perf` et `Syslog` seulement (huit). `StorageBlobLogs` attend RH8, malgré sa fenêtre de 5 minutes.

**Q4 — Le retard lui-même** (§8)
1. **Un état par VM et par table ; une carte seulement au-delà de l'horizon, ou pour une table muette
   quand `Heartbeat` arrive ; un fait du dossier et de la probation (recommandée).** Ce qui n'est pas
   jugé est dit ; un retard jugé quand même ne fait pas de bruit.
2. Une carte dès qu'un bloc arrive avec plus de `N` de retard. Le plus visible ; une carte à chaque
   levée, et à chaque lenteur d'Azure.
3. Rien de neuf : seulement le fait du dossier. Le moins de code ; une VM muette sous un `Heartbeat`
   vivant reste invisible.

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
2. ING3 sans la règle sudo : sa copie reste intacte, la règle sudo reste aveugle au retard jusqu'à un
   prochain changement qui la touche.
3. ING3 attend une autre release qui change aussi la règle sudo, pour un seul geste.

**Q7 — Le démarrage sous la quarantaine, pour LEV4** (§7)
1. **Une relecture de rattrapage au début de la probation, sur `[fin du restore, maintenant]`, une
   fois le rattrapage de l'agent fini ; plus la forme d'ING3 pour le cas courant (recommandée).** Elle
   couvre une levée humaine tardive, et dit ce qui n'est jamais arrivé.
2. L'horizon d'ING3 seul. Le plus simple ; une levée humaine plus tardive que l'horizon laisse le
   démarrage sans juge.
3. LEV4 attend la mesure de RH4 (ce que l'agent livre de la quarantaine) avant de choisir.

**Q8 — L'enquête d'une détection arrivée en retard** (§2.3, §3.5)
1. **Inchangée en v1 ; le retard est dit au dossier, pour l'humain, jamais au modèle (recommandée).**
   Le modèle voit ce qu'il voit aujourd'hui ; on mesure d'abord combien de détections arrivent en
   retard.
2. Ancrer les fenêtres d'`investigate` sur l'heure des lignes (`IngFirstAt`). L'enquête lirait les
   bonnes minutes ; elle change ce que voit le modèle : un lot à part, avec son run de bout en bout
   T1486 et un autre TTP, par toi.
