# ING5 au banc — le retard de chaque source, mesuré en lecture seule (RH1 à RH12)

[← le banc](demarrer/banc.md) · la conception : [une mesure arrivée en retard](design/mesure-en-retard.md) (§10, §11) · [le dossier d'une isolation](design/dossier-isolation.md) (§9 : DH2 et DH11)

La conception d'ING1 (#738) propose de juger une ligne à son **arrivée** (`ingestion_time()`) et de
l'agréger à son **heure** (`TimeGenerated`). Elle repose sur douze hypothèses, RH1 à RH12, que
personne n'a mesurées (§10). Cette page les mesure. Ses résultats fixent l'horizon de retard d'ING3
(Q2 : 2 h, revu après RH4 et RH6), et disent à LEV3 et LEV4 si la quarantaine retient la télémétrie
de l'invité (RH5).

**Tout se lit sur les données que le workspace du banc garde** : 30 jours (`log_retention_days: 30`,
`infra/terraform/config.yaml:114`). Les exceptions :
- RH9, un geste non destructif : trois lignes de journal sur gondolin ;
- RH10, qui attend ING3.

Les requêtes sont écrites ici et vérifiées à la lecture contre les règles livrées
(`glorfindel/rules/azure/detection_rules.yaml`) et la conception. **Aucune n'a encore tourné** :
une requête refusée par Log Analytics se corrige ici, dans un lot relu.

## Les règles de la session

- **Rien n'écrit sur Azure**, sauf le geste de RH9 (une Run Command qui écrit trois lignes dans le
  journal de gondolin). Une requête `az monitor log-analytics query` est une lecture, sous le
  `az login` du poste (Log Analytics Reader suffit). Au premier appel, `az` installe son extension
  `log-analytics`, sur le poste. Les requêtes sont gratuites : les tables du banc sont facturées à
  l'ingestion, pas à la lecture (la conception, §5).
- **Aucun identifiant dans les résultats.** Aucune requête ne rend `_ResourceId`, `Computer`,
  `CorrelationId`, un appelant, une adresse ou un nom de compte. Une VM se dit par son nom du dépôt
  (`bree`, `gondolin`). On reporte des secondes et des comptes. Le dossier `${RET}` reste sur le
  poste.
- **Les heures sont en UTC**, partout : celles des requêtes, des comptes rendus du banc, et de
  `TimeGenerated`. Le compte rendu du 11/11 tient la levée de bree à 15:54:10 UTC. Le §1.1 de la
  conception demandait de vérifier le fuseau : la requête des bornes (étape 1) le règle.
- **Qui lance** : Jonathan, ou la session Tests avec lui, depuis le poste, à la racine du dépôt.
  Aucune session de code ne lance une requête.

## 0. Avant (2 min)

```zsh
export RET=~/eregion-banc/retard-$(date -u +%Y%m%d); mkdir -p ${RET}
WS=$(terraform -chdir=infra/terraform output -raw law_workspace_id)   # le GUID du workspace : jamais affiché, jamais recopié
az account show -o none && print -r -- "az : connecté"
# kq <nom> : la requête ${RET}/<nom>.kql, une fois, en lecture seule ; la sortie dans ${RET}/<nom>.txt.
kq() { az monitor log-analytics query -w ${WS} --analytics-query "$(<${RET}/$1.kql)" --timespan P31D -o table | tee ${RET}/$1.txt; }
# rh <corps> <nom> <vm> <isolement> <levée> <fin> : les bornes d'une quarantaine devant un corps de requête.
rh() {
  { print -r -- "let vm = \"/$3\"; let isolated = datetime($4); let lift = datetime($5); let window_end = datetime($6);"
    print -r -- "$(<${RET}/$1.kql)"; } > ${RET}/$2.kql
  kq $2
}
```

**Le `--timespan` couvre toute la rétention** (`P31D`). La fenêtre d'une requête est dans son texte,
en dates absolues (`datetime(…)`). Le `--timespan` porte sur `TimeGenerated`, comme celui du
RulePoller (la conception, §1.2) : il ne borne jamais l'arrivée, et une ligne datée dans la fenêtre
est rendue quelle que soit l'heure de son arrivée. C'est ce qu'on mesure.

## L'ordre et les échéances

Les données partent 30 jours après leur heure. **RH5, RH3, RH4, puis RH6 d'abord**, dans une même
séance (20 minutes), dès que possible : leurs données partent les premières, et RH5 décide du §7 de la
conception. Les bornes (étape 1) passent avant elles. DH2 et DH11 (DOS8) se joignent à cette séance :
même VM, mêmes jours.

La date limite la plus proche est **celle de RH6** : les données du 09/11 partent vers le 09/12. Si la
séance glisse vers le 08/12, RH6 passe en premier.

| Ordre | Quoi | Les lignes lues (UTC, par leur heure) | Partent vers | **Au plus tard** |
|---|---|---|---|---|
| 1 | les bornes | `AzureActivity`, 09/11 00:00 → 13/11 00:00 | 09/12 | **08/12** |
| 2 | **RH5** | bree, 10/11 02:06 → 11/11 16:17 ; la contre-épreuve, 11/11 15:47 → 19:40 | 10/12 ; 11/12 | **09/12** ; 10/12 |
| 3 | **RH3** | bree, 11/11 15:40 → 16:40 | 11/12 | **10/12** |
| 4 | **RH4** | bree, 10/11 02:00 → 11/11 16:17 | 10/12 | **09/12** |
| 5 | **RH6** | gondolin, 09/11 16:13 → 22:05 ; bree, 11/11 15:47 → 19:40 ; gondolin, 12/11 08:48 → 11:06 | 09/12 ; 11/12 ; 12/12 | **08/12** ; 10/12 ; 11/12 |
| 6 | DH11 | `AzureActivity` de bree, 10/11 02:28 → 02:50 | 10/12 dans le workspace ; le journal d'activité, 90 jours | **09/12** (le workspace) |
| 7 | DH2 | les jobs du coffre, 01/11 → 12/11 | le coffre garde ses jobs | — |
| 8 | RH1, RH2, RH12, RH7 | une semaine normale : 02/11 00:00 → 09/11 00:00 | 02/12 | **01/12** ; ensuite, une autre semaine sans quarantaine |
| 9 | RH8 | `StorageBlobLogs`, 01/11 → 12/12 : ce qui est gardé | au fil de l'eau | vers le 01/12 : le plus de jours |
| 10 | RH11 | une journée : 11/11 | 11/12 | 10/12 ; ensuite, un autre jour |
| 11 | RH9 | un geste sur gondolin, un jour où elle tourne | — | — |
| 12 | RH10 | après ING3 (les règles), et après ING4 (la vue du retard) | — | — |

« Partent vers » : la rétention compte 30 jours depuis l'heure de la ligne, et la purge n'est pas à
la minute. « Au plus tard » laisse un jour de marge.

**Les quarantaines de la période**, d'après les comptes rendus du banc (hors dépôt). L'étape 1 les
relit au journal d'activité.

| Quarantaine | Isolement | Levée | Ce qui s'y est passé |
|---|---|---|---|
| gondolin, 09/11 (le T1486, sans REC1) | 16:43:03 | 21:05:49 | désallouée de 17:10:35 à 20:50:19, le disque restauré depuis un point de 15:49 ; redémarrée sous la quarantaine à 20:50:28 |
| bree, 10/11 → 11/11 (la sauvegarde nocturne, un faux positif) | ≈ 02:36:15 le 10/11 | 15:54:10 le 11/11 | 37 h 18 en marche, sans restore |
| bree, 11/11 (la réisolation) | ≈ 16:17:40 | ≈ 18:40:30 | 2 h 23 en marche, sans restore ; levée par Jonathan, puis `human_only` |
| gondolin, 12/11 (le T1486, avec REC1) | 09:18:46 | 10:06:23 | désallouée à 09:44:54, redémarrée après le restore à 10:00:38, sous la quarantaine |

« ≈ » : déduite d'une autre heure (le cycle moins `action_s`, le message de Jonathan) ; l'étape 1 la
donne.

## 1. Les bornes : chaque écriture des cartes réseau, du 09/11 au 13/11

Isoler, c'est poser le NSG de quarantaine sur la carte réseau ; lever, c'est remettre l'ancien.
Chaque isolement et chaque levée s'écrivent donc `networkInterfaces/write` sur la carte de la VM
(`nic-celebrimbor-<vm>`, `infra/terraform/locals.tf`). Le corps des requêtes de RH4 à RH6 prend ces
heures à la minute près.

```zsh
cat > ${RET}/bornes.kql <<'KQL'
// Les bornes : chaque écriture des cartes réseau de bree et de gondolin, du 09/11 au 13/11, état par état.
AzureActivity
| where TimeGenerated >= datetime(2026-11-09T00:00:00Z) and TimeGenerated < datetime(2026-11-13T00:00:00Z)
| where OperationNameValue =~ "MICROSOFT.NETWORK/NETWORKINTERFACES/WRITE"
| extend Nic = extract(@"(?i)/networkinterfaces/([^/]+)$", 1, _ResourceId)
| where Nic in~ ("nic-celebrimbor-bree", "nic-celebrimbor-gondolin")
| project TimeGenerated, Nic, Status = ActivityStatusValue
| order by TimeGenerated asc
KQL
kq bornes
```

**Ce qu'on doit voir** : pour chaque quarantaine du tableau, une écriture à l'isolement et une à la
levée, chacune en deux ou trois états (`Start`, `Accept`, `Success`, ou les mots de la table). Le
12/11, une écriture de plus sur gondolin vers 10:3x : le tag posé puis retiré par LEV2 (le geste 9
et son retour, `docs/banc-lev2.md`). **Si une heure diffère de plus d'une minute** de celle du tableau,
on prend celle du journal (le premier `Success`) dans les appels `rh` ci-dessous. **Aucune ligne** :
`AzureActivity` n'était pas encore versée au workspace ces jours-là. Alors on garde les heures du
tableau, et on le note.

## 2. RH5 — la quarantaine retient-elle la télémétrie de l'invité ?

**L'hypothèse** (la conception, §10) : aucune ligne `Heartbeat` de bree datée sous la quarantaine
(avant 15:54:10 le 11/11) n'est arrivée à temps. Le NSG de quarantaine refuse tout en sortie
(`glorfindel/providers/azure/quarantine.py:17-19`) : il **devrait** couper l'agent.

**Ce qu'on sait déjà** : le 11/11 à 15:55, juste après la levée, la session Tests a relevé un seul
battement de bree dans l'heure, à 15:55:35. Cette lecture a été faite une minute après la levée : un
bloc arrivé plus tard n'y était pas. Le relevé du 12/11 montre `Heartbeat` de 15:54 à 16:20 arrivé
avec 2 à 10 s de retard. Il ne dit rien des battements datés d'avant la levée.

**Fenêtre** : bree, du 10/11 02:06 au 11/11 16:17, qui s'arrête avant la réisolation. Les données
partent vers le 10/12 : **au plus tard le 09/12**. La contre-épreuve (la réisolation) : au plus tard
le 10/12.

Le corps des phases sert aussi à RH6. Il classe chaque ligne de `Perf` (l'écriture disque, tous
volumes), `Syslog` et `Heartbeat` selon son heure, par rapport à l'isolement et à la levée. Puis il
dit combien de lignes de chaque phase sont arrivées avant et après la levée.

```zsh
cat > ${RET}/phases.kql <<'KQL'
// Le corps des phases : les bornes (vm, isolated, lift, window_end) viennent devant, posées par rh.
union withsource=Table
    (Perf | where ObjectName in ("Logical Disk", "LogicalDisk") and CounterName == "Disk Write Bytes/sec"),
    Syslog, Heartbeat
| where TimeGenerated >= isolated - 30m and TimeGenerated < window_end
| where _ResourceId endswith vm
| extend Arrived = ingestion_time(), DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| extend Phase = case(TimeGenerated < isolated - 1m, "1 avant l'isolement",
                      TimeGenerated < isolated + 1m, "2 bord de l'isolement",
                      TimeGenerated < lift - 1m, "3 sous la quarantaine",
                      TimeGenerated < lift + 1m, "4 bord de la levée",
                      TimeGenerated < lift + 10m, "5 levée + 10 min",
                      "6 après")
| summarize Rows = count(), BeforeLift = countif(Arrived < lift), AfterLift = countif(Arrived >= lift),
            NoArrival = countif(isnull(Arrived)), FirstDated = min(TimeGenerated), LastDated = max(TimeGenerated),
            LastArrived = max(Arrived), P50DelayS = percentile(DelayS, 50), MaxDelayS = max(DelayS)
            by Table, Phase
| order by Table asc, Phase asc
KQL
rh phases rh5-bree-q1 vm-celebrimbor-bree 2026-11-10T02:36:15Z 2026-11-11T15:54:10Z 2026-11-11T16:17:00Z
# La contre-épreuve : la réisolation du 11/11, 2 h 23 de quarantaine.
rh phases rh5-bree-q2 vm-celebrimbor-bree 2026-11-11T16:17:40Z 2026-11-11T18:40:30Z 2026-11-11T19:40:00Z
```

**Comment lire.** Une phase absente pour une table veut dire qu'aucune ligne n'est datée là.
`BeforeLift` compte les lignes arrivées avant la levée, `AfterLift` celles arrivées après.

**Elle tient si**, pour les deux quarantaines, la phase « 3 sous la quarantaine » est absente, ou
n'a que des lignes `AfterLift` : rien n'est passé sous la quarantaine, ou tout a été retenu puis
livré après la levée. On note pour chaque table les lignes datées sous la quarantaine et livrées
après, et `LastArrived` moins la levée.

**Elle tombe si** une ligne de la phase 3 a `BeforeLift` > 0, pour n'importe quelle table : l'agent
passait la quarantaine. On note la table, le nombre, `P50DelayS`. La contre-épreuve compte autant
que la première : le relevé du 12/11 dit `Perf` « au fil de l'eau à partir de 16:16 », et la
réisolation tombe vers 16:17:40.

**Si elle tombe** (la conception, §10, §7) : le bloc du 11/11 vient d'ailleurs (la règle de collecte,
l'ingestion du workspace). Les points 1 à 3 et 5 à 6 du §7 tombent, et Q7 avec eux. LEV3 et LEV4
gardent les points 4, 7 et 8.

**Reporter** : sur #758, pour chaque quarantaine et chaque table, les comptes de la phase 3
(`Rows`, `BeforeLift`, `AfterLift`) et `LastArrived` moins la levée, en secondes. L'Orchestre écrit
le résultat à la ligne RH5 du §10 de la conception, dans un lot relu, et le route vers LEV3 et LEV4
(session Glorfindel).

## 3. RH3 — `Syslog` a-t-il été retenu comme `Perf`, autour de la levée du 11/11 ?

**L'hypothèse** : `Syslog` de bree a été retenu comme `Perf` autour de la levée du 11/11. Le relevé
du 12/11 a montré `Perf` de « / », de 15:50 à 16:14, arrivé d'un bloc entre 16:16:50 et 16:16:59. Il
a aussi compté les lignes `Syslog` par processus de 15:54 à 16:20, sans lire leur arrivée.

**Fenêtre** : bree, le 11/11 de 15:40 à 16:40. Les données partent vers le 11/12 : **au plus tard le
10/12**. La fenêtre traverse trois moments : la première quarantaine (jusqu'à 15:54:10), l'entre-deux,
et la réisolation (à partir de ≈ 16:17:40, l'heure de l'étape 1).

La requête refait la mesure du relevé pour `Perf` : c'est son contrôle. Elle met `Syslog` et
`Heartbeat` à côté, par tranches de 2 minutes de l'heure de la ligne.

```zsh
cat > ${RET}/rh3.kql <<'KQL'
// RH3 : par table et par tranche de 2 min de l'heure de la ligne, quand les lignes de bree sont arrivées (11/11, 15:40 → 16:40).
let lift = datetime(2026-11-11T15:54:10Z);
let reisolated = datetime(2026-11-11T16:17:40Z);
union withsource=Table
    (Perf | where ObjectName in ("Logical Disk", "LogicalDisk") and CounterName == "Disk Write Bytes/sec" and InstanceName == "/"),
    Syslog, Heartbeat
| where TimeGenerated >= datetime(2026-11-11T15:40:00Z) and TimeGenerated < datetime(2026-11-11T16:40:00Z)
| where _ResourceId endswith "/vm-celebrimbor-bree"
| extend Arrived = ingestion_time(), DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| extend Moment = case(TimeGenerated < lift, "quarantaine 1", TimeGenerated < reisolated, "entre les deux", "quarantaine 2")
| summarize Rows = count(), NoArrival = countif(isnull(Arrived)), FirstArrived = min(Arrived), LastArrived = max(Arrived),
            MinDelayS = min(DelayS), MaxDelayS = max(DelayS)
            by Table, Moment, Slice = bin(TimeGenerated, 2m)
| order by Table asc, Slice asc
KQL
kq rh3
```

**Le contrôle** : `Perf` doit redonner le relevé, à savoir les tranches de 15:50 à 16:14 arrivées
entre 16:16:50 et 16:16:59, avec des retards de 1 503–1 610 s (15:50) à 69–179 s (16:14). Sinon, la
requête ne lit pas ce que le relevé a lu, et on s'arrête là.

**Elle tient si** les tranches `Syslog` datées avant 16:16 arrivent dans le même bloc que `Perf`
(`FirstArrived` vers 16:16:50 ou après), avec des retards du même ordre.

**Elle tombe si** les tranches `Syslog` de « entre les deux » (15:54 à 16:16) arrivent au fil de
l'eau (`MaxDelayS` de l'ordre de la minute), alors que `Perf` des mêmes tranches arrive à 16:16:5x.
Ce qu'on lit des lignes `Syslog` de « quarantaine 1 » se note à part : présentes et arrivées après la
levée (retenues), ou absentes (perdues, ou jamais écrites). `MetricsExtension` écrit chaque minute dans
`Syslog` (le relevé du 12/11), donc une tranche vide n'est pas un silence de la VM.

**Si elle tombe** (la conception, §10) : le bloc est propre à `Perf` (une file de l'agent par flux ?),
et le §7 se resserre sur `Perf`. ING3 fixe alors l'horizon de `Syslog` sur RH2 seul.

**Reporter** : sur #758, pour `Syslog` et `Heartbeat`, et pour chaque moment, la première et la
dernière arrivée, et les retards minimal et maximal, en secondes. Puis la ligne RH3 du §10 de la
conception, par l'Orchestre.

## 4. RH4 — ce que l'agent livre de 37 heures de quarantaine

**L'hypothèse** : l'agent livre, à la levée, **tout** ce qu'il a collecté sous la quarantaine. La
mesure dit tout, une partie (les dernières heures : la profondeur de sa file), ou rien. Le relevé ne
connaît que les échantillons de 15:50 à 15:54, arrivés 22 min 40 s après la levée.

**Fenêtre** : bree, du 10/11 02:00 au 11/11 16:17. Les données partent vers le 10/12 : **au plus tard
le 09/12**.

`Perf` est restreint à l'écriture disque de « / » : au banc, un échantillon toutes les 10 s
(`infra/terraform/config.yaml:115`), donc **360 lignes par heure** quand rien ne manque. `Heartbeat`
en attend environ une par minute (la période exacte vient de RH12). `Syslog` n'a pas de cadence.

```zsh
cat > ${RET}/rh4-heure.kql <<'KQL'
// RH4 (a) : de la quarantaine de bree (10/11 02:36 → 11/11 15:54:10), ce qui est arrivé, heure par heure de la ligne.
let lift = datetime(2026-11-11T15:54:10Z);
union withsource=Table
    (Perf | where ObjectName in ("Logical Disk", "LogicalDisk") and CounterName == "Disk Write Bytes/sec" and InstanceName == "/"),
    Syslog, Heartbeat
| where TimeGenerated >= datetime(2026-11-10T02:00:00Z) and TimeGenerated < datetime(2026-11-11T16:17:00Z)
| where _ResourceId endswith "/vm-celebrimbor-bree"
| extend Arrived = ingestion_time()
| summarize Rows = count(), BeforeLift = countif(Arrived < lift), AfterLift = countif(Arrived >= lift),
            NoArrival = countif(isnull(Arrived)), FirstArrived = min(Arrived), LastArrived = max(Arrived)
            by Table, Hour = bin(TimeGenerated, 1h)
| order by Table asc, Hour asc
KQL
kq rh4-heure
cat > ${RET}/rh4-arrivee.kql <<'KQL'
// RH4 (b) : les lignes de bree datées sous la quarantaine, par tranche de 10 min de leur arrivée (sans borne sur l'arrivée).
let isolated = datetime(2026-11-10T02:36:15Z);
let lift = datetime(2026-11-11T15:54:10Z);
union withsource=Table
    (Perf | where ObjectName in ("Logical Disk", "LogicalDisk") and CounterName == "Disk Write Bytes/sec" and InstanceName == "/"),
    Syslog, Heartbeat
| where TimeGenerated > isolated + 1m and TimeGenerated < lift - 1m
| where _ResourceId endswith "/vm-celebrimbor-bree"
| extend Arrived = ingestion_time()
| summarize Rows = count(), OldestDated = min(TimeGenerated), NewestDated = max(TimeGenerated)
            by Table, ArrivedAt = bin(Arrived, 10m)
| order by Table asc, ArrivedAt asc
KQL
kq rh4-arrivee
```

**Comment lire** (a) : une heure absente de la liste veut dire qu'aucune ligne n'est datée dans cette
heure-là. (b) dit quand le reliquat est arrivé, peut-être après la seconde levée (≈ 18:40).

**Elle tient si** chaque heure de la quarantaine a ses ≈ 360 lignes `Perf` (et ses battements),
toutes `AfterLift`.

**Elle tombe si** des heures manquent : on note la première heure livrée (la profondeur de la file,
en heures et en lignes), ou « rien » si aucune ligne n'est datée sous la quarantaine, hors de ses
dernières minutes.

**Si elle tombe** (la conception, §10, §7, point 6) : une quarantaine est perdue, en tout ou en
partie. La relecture de rattrapage de LEV4 ne trouve rien pour ces heures, et la carte de probation le
dit (« les mesures de la VM sous la quarantaine ne sont jamais arrivées, de … à … »). La profondeur
mesurée borne aussi la fenêtre de la vue du retard (Q4 : 48 h).

**Reporter** : sur #758, la première heure livrée et le nombre de lignes par table, et l'heure de la
dernière arrivée, en secondes après la levée. Puis la ligne RH4 du §10, par l'Orchestre.

## 5. RH6 — le rattrapage après une quarantaine plus courte

**L'hypothèse** : après une quarantaine courte, le rattrapage est le même qu'après les 37 h de bree.
Le 11/11, il a fallu 22 min 49 s entre la levée et la fin du bloc.

**Trois quarantaines** à comparer à celle de bree (RH5 : `rh5-bree-q1`). Chacune a ses fenêtres et
sa date limite.

| Nom | La VM, la quarantaine | Les données partent vers | **Au plus tard** |
|---|---|---|---|
| `rh6-gondolin-0911` | gondolin, 09/11, 4 h 23 dont 3 h 40 désallouée, et un disque restauré | 09/12 | **08/12** |
| `rh6-bree-q2` | bree, la réisolation du 11/11, 2 h 23 en marche | 11/12 | 10/12 |
| `rh6-gondolin-1212` | gondolin, 12/11, 48 min dont 16 min désallouée, et un disque restauré | 12/12 | 11/12 |

Le corps des tranches dit, par 5 minutes de l'heure de la ligne, ce qui est daté sous la quarantaine
et quand c'est arrivé. Pour gondolin, on y lit à part les tranches d'avant la désallocation (l'ancien
disque) et celles d'après le démarrage du disque restauré.

```zsh
cat > ${RET}/tranches.kql <<'KQL'
// Le corps des tranches : les lignes datées sous la quarantaine, par 5 min de leur heure ; les bornes devant, posées par rh.
union withsource=Table
    (Perf | where ObjectName in ("Logical Disk", "LogicalDisk") and CounterName == "Disk Write Bytes/sec"),
    Syslog, Heartbeat
| where TimeGenerated > isolated + 1m and TimeGenerated < lift - 1m
| where _ResourceId endswith vm
| extend Arrived = ingestion_time()
| summarize Rows = count(), BeforeLift = countif(Arrived < lift), FirstArrived = min(Arrived), LastArrived = max(Arrived)
            by Table, Slice = bin(TimeGenerated, 5m)
| order by Table asc, Slice asc
KQL
rh phases   rh6-gondolin-0911          vm-celebrimbor-gondolin 2026-11-09T16:43:03Z 2026-11-09T21:05:49Z 2026-11-09T22:05:00Z
rh tranches rh6-gondolin-0911-tranches vm-celebrimbor-gondolin 2026-11-09T16:43:03Z 2026-11-09T21:05:49Z 2026-11-09T22:05:00Z
rh phases   rh6-bree-q2                vm-celebrimbor-bree     2026-11-11T16:17:40Z 2026-11-11T18:40:30Z 2026-11-11T19:40:00Z
rh tranches rh6-bree-q2-tranches       vm-celebrimbor-bree     2026-11-11T16:17:40Z 2026-11-11T18:40:30Z 2026-11-11T19:40:00Z
rh phases   rh6-gondolin-1212          vm-celebrimbor-gondolin 2026-11-12T09:18:46Z 2026-11-12T10:06:23Z 2026-11-12T11:06:00Z
rh tranches rh6-gondolin-1212-tranches vm-celebrimbor-gondolin 2026-11-12T09:18:46Z 2026-11-12T10:06:23Z 2026-11-12T11:06:00Z
```

**Le rattrapage d'une quarantaine**, en secondes : `LastArrived` de la phase « 3 sous la quarantaine »
moins la levée (le 11/11 : 22 min 49 s, soit 1 369 s). Le même chiffre pour `rh5-bree-q1` sert de
référence. Et la phase « 5 levée + 10 min » dit si le retard redevient normal (`P50DelayS` de
l'ordre de la minute) ou si un second bloc suit.

**À lire pour gondolin** (le 09/11 et le 12/11) : les tranches d'avant la désallocation ont été
collectées sur un disque que le restore a remplacé. Sont-elles jamais arrivées ? Les tranches d'après
le démarrage du disque restauré sont celles du cas 2 de LEV, le démarrage sous la quarantaine
(`levee-probation.md`, §6.3) : arrivent-elles seulement après la levée ?

**Elle tient si** le rattrapage des trois quarantaines est du même ordre que celui de bree (quelques
dizaines de minutes au plus), quelle que soit leur durée.

**Elle tombe si** le rattrapage grandit (ou rapetisse) avec la durée de la quarantaine.

**Si elle tombe** (la conception, §10) : l'horizon dépend de la durée de la quarantaine, et Q2 (2 h)
se revoit. Un rattrapage de plus d'une heure après une levée de `non_disruptive` (la fin du job plus
15 minutes) sortirait l'horizon de 2 h de sa marge (la conception, §7, point 5).

**Reporter** : sur #758, pour chaque quarantaine, sa durée en marche, son rattrapage en secondes, et
pour gondolin, les comptes des tranches d'avant la désallocation et d'après le démarrage (arrivées ou
non, avant ou après la levée). Puis la ligne RH6 du §10, par l'Orchestre.

## 6. DH2 et DH11, du dossier d'une isolation (DOS8), joints à la même séance

Ces deux hypothèses de DOS1 portent sur la même VM et les mêmes jours que RH4 et RH5 : la nuit du
10/11 sur bree. Elles se lisent en lecture seule, et DH11 du même ordre (`AzureActivity`, dans le
workspace). Elles se reportent au dossier d'une isolation (#727, son §9), pas à la conception d'ING1.

### DH11 — la coupure attend-elle derrière l'extension de sauvegarde ?

**L'hypothèse** (`dossier-isolation.md`, §9) : la coupure des sessions de bree, le 10/11 (la Run
Command de 02:36:22 à 02:43:36), attend derrière l'extension de sauvegarde (une Run Command après
l'autre). **Fenêtre** : 02:28 à 02:50 le 10/11. Dans le workspace, ces lignes partent vers le 10/12 :
**au plus tard le 09/12**. Ensuite, le journal d'activité lui-même les garde 90 jours (la
documentation d'Azure, `dossier-isolation.md`, §9.1).

```zsh
cat > ${RET}/dh11.kql <<'KQL'
// DH11 : le journal d'activité de bree et de ses enfants (extensions, Run Command), le 10/11 de 02:28 à 02:50, sans appelant.
AzureActivity
| where TimeGenerated >= datetime(2026-11-10T02:28:00Z) and TimeGenerated < datetime(2026-11-10T02:50:00Z)
| where _ResourceId has "/virtualmachines/vm-celebrimbor-bree"
| extend Child = extract(@"(?i)/virtualmachines/vm-celebrimbor-bree(/.*)?$", 1, _ResourceId)
| project TimeGenerated, Op = OperationNameValue, Status = ActivityStatusValue, Child
| order by TimeGenerated asc
KQL
kq dh11
```

Après le 09/12, la même lecture au journal d'activité. Le filtre exact rend aussi les enfants (H9,
mesuré le 12/11, `docs/banc-lev2.md`) :

```zsh
VMID=$(az vm show -g rg-celebrimbor -n vm-celebrimbor-bree --query id -o tsv)   # jamais affiché
az monitor activity-log list --resource-id ${VMID} --start-time 2026-11-10T02:28:00Z --end-time 2026-11-10T02:50:00Z \
  --query "[].{at:eventTimestamp, op:operationName.value, status:status.value, kind:resourceType.value}" -o table | tee ${RET}/dh11-journal.txt
```

**Elle tient si** une opération de l'extension de sauvegarde (`…/extensions/…`, un nom comme
`VMSnapshotLinux`) court de 02:33 environ jusque juste avant l'aboutissement de la Run Command
(02:43:36) : la Run Command est `Accepted` dès 02:36:24, et n'aboutit qu'après la fin de l'extension.
**Elle tombe si** aucune opération d'extension n'apparaît dans la fenêtre, ou si sa fin ne précède pas
l'aboutissement de la coupure. **Si elle tombe** : F5a dit autrement la durée de la coupure, et DRN1
et SID1 tirent d'ailleurs leurs délais (`dossier-isolation.md`, §9). **Reporter** : sur #727,
chaque opération (son nom, sa sorte de ressource, ses heures et ses états), puis la ligne DH11 du §9
du dossier, par l'Orchestre.

### DH2 — un job de sauvegarde planifié se lit-il comme celui d'un instantané ?

**L'hypothèse** : un job `Backup` planifié se lit comme celui d'un instantané à la demande, que
`glorfindel/providers/azure/backup.py:160-187` lit déjà (`operation`, `entity_friendly_name`,
`start_time`). Et la liste du coffre se filtre sur `N` jours sans couper. Le coffre garde ses jobs :
pas d'échéance du workspace.

```zsh
az backup job list -g rg-celebrimbor -v rsv-celebrimbor-erebor --start-date 1-11-2026 --end-date 12-11-2026 \
  --query "length(@)" -o tsv | tee ${RET}/dh2-nombre.txt          # tous les jobs de la plage, un nombre
az backup job list -g rg-celebrimbor -v rsv-celebrimbor-erebor --start-date 1-11-2026 --end-date 12-11-2026 \
  --query "[?contains(properties.entityFriendlyName, 'bree')].{op:properties.operation, start:properties.startTime, end:properties.endTime, status:properties.status}" \
  -o table | tee ${RET}/dh2-bree.txt
```

**Elle tient si** chaque nuit du 01/11 au 11/11 a son job `Backup` sur bree, avec `operation`,
`entityFriendlyName` et `startTime` remplis comme pour un instantané (le 11/11, la session Tests en a
lu deux : 09/11 02:30:27 → 04:26:49, 10/11 02:33:19 → 04:44:41). **Elle tombe si** des nuits manquent,
ou si un champ diffère. **Si elle tombe** : F1a et F3b changent de filtre, ou `N` baisse
(`dossier-isolation.md`, §9). **Reporter** : sur #727, le nombre de jobs de la plage, le nombre de
nuits de bree et leur opération, puis la ligne DH2 du §9 du dossier, par l'Orchestre.

## 7. RH1 et RH2 — le retard normal de `Perf` et de `Syslog`

**Les hypothèses** :
- RH1 : le retard normal de `Perf` reste sous 2 min. Le 05/10, 89 à 109 s ; le 11/11, juste après le
  bloc, 55 à 108 s, ce qui n'est pas un temps normal.
- RH2 : celui de `Syslog` tient sous la fenêtre `N` = 10 min. L'en-tête des règles dit 480 s sans
  mesure (`detection_rules.yaml:25`).

**Fenêtre** : une semaine normale, du 02/11 00:00 au 09/11 00:00 : avant le T1486 du 09/11, sans
quarantaine connue des comptes rendus. Les données partent vers le 02/12 : **au plus tard le 01/12**.
Ensuite, une autre semaine, qui évite les quarantaines du tableau des échéances.

```zsh
cat > ${RET}/rh1.kql <<'KQL'
// RH1 : le retard de Perf en temps normal, par VM, du 02/11 au 09/11.
Perf
| where TimeGenerated >= datetime(2026-11-02T00:00:00Z) and TimeGenerated < datetime(2026-11-09T00:00:00Z)
| extend Vm = case(_ResourceId endswith "/vm-celebrimbor-bree", "bree", _ResourceId endswith "/vm-celebrimbor-gondolin", "gondolin", "")
| where Vm != ""
| extend DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| summarize Rows = count(), NoArrival = countif(isnull(DelayS)), P50 = percentile(DelayS, 50), P95 = percentile(DelayS, 95),
            P99 = percentile(DelayS, 99), Max = max(DelayS), Over120 = countif(DelayS > 120), Over600 = countif(DelayS > 600)
            by Vm
KQL
kq rh1
cat > ${RET}/rh2.kql <<'KQL'
// RH2 : le retard de Syslog en temps normal, par VM et par facilité, du 02/11 au 09/11.
Syslog
| where TimeGenerated >= datetime(2026-11-02T00:00:00Z) and TimeGenerated < datetime(2026-11-09T00:00:00Z)
| extend Vm = case(_ResourceId endswith "/vm-celebrimbor-bree", "bree", _ResourceId endswith "/vm-celebrimbor-gondolin", "gondolin", "")
| where Vm != ""
| extend DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| summarize Rows = count(), NoArrival = countif(isnull(DelayS)), P50 = percentile(DelayS, 50), P95 = percentile(DelayS, 95),
            P99 = percentile(DelayS, 99), Max = max(DelayS), Over480 = countif(DelayS > 480), Over600 = countif(DelayS > 600)
            by Vm, Facility
| order by Vm asc, Facility asc
KQL
kq rh2
cat > ${RET}/rh1-rh2-heures.kql <<'KQL'
// RH1, RH2 : les heures où une ligne est arrivée plus de 10 min après son heure, du 02/11 au 09/11.
union withsource=Table Perf, Syslog
| where TimeGenerated >= datetime(2026-11-02T00:00:00Z) and TimeGenerated < datetime(2026-11-09T00:00:00Z)
| extend Vm = case(_ResourceId endswith "/vm-celebrimbor-bree", "bree", _ResourceId endswith "/vm-celebrimbor-gondolin", "gondolin", "")
| where Vm != ""
| extend DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| summarize Over600 = countif(DelayS > 600), Max = max(DelayS) by Table, Vm, Hour = bin(TimeGenerated, 1h)
| where Over600 > 0
| order by Hour asc
KQL
kq rh1-rh2-heures
```

**Comment lire les heures en retard.** gondolin s'éteint chaque soir à 23 h UTC et redémarre à la
main : le premier envoi après un démarrage est un rattrapage, pas un temps normal (#105, en commentaire
de `ransomware-disk-write`). Une heure en retard qui suit un démarrage se note à part. Une autre est
un temps normal, et elle compte.

**RH1 tient si** `P95` de `Perf` reste sous 120 s pour chaque VM, et qu'aucune heure normale n'a de
ligne au-delà de 600 s. **Elle tombe si** `P95` passe 120 s, ou si des heures normales dépassent
600 s. **Si elle tombe** : `N` est à revoir pour `Perf` (la conception, §10).

**RH2 tient si** `P99` de `Syslog` reste sous 600 s pour chaque VM et chaque facilité, hors
rattrapages. **Elle tombe si** une facilité dépasse 600 s en temps normal. **Si elle tombe** : `N`
ou `H` est à revoir pour `Syslog`, avant ING3 (la conception, §10, §11 : ING3 attend RH2 et RH3).

**Reporter** : sur #758, par VM (et par facilité pour `Syslog`), `P50`, `P95`, `P99`, `Max`,
`Over600`, et les heures en retard, chacune avec sa raison (démarrage, ou rien de connu). Puis les
lignes RH1 et RH2 du §10, par l'Orchestre.

## 8. RH12 — le silence normal de `Syslog`, et la période de `Heartbeat`

**L'hypothèse** : sur une VM calme, `Syslog` se tait parfois longtemps : il suit les événements et n'a
pas de cadence. `Heartbeat` bat à une période régulière, à lire. Le silence de `Syslog` ne fait jamais
de carte (la conception, §8). La période de `Heartbeat` fixe le seuil de l'état « muette » d'ING4.

**Fenêtre** : la semaine de RH1, du 02/11 au 09/11, **au plus tard le 01/12**. Pour `Syslog`, bree
seule : elle tourne toujours, alors que gondolin s'éteint chaque soir, et ses nuits feraient des
silences qui n'en sont pas.

```zsh
cat > ${RET}/rh12-syslog.kql <<'KQL'
// RH12 (a) : les silences de Syslog sur bree, toutes facilités, puis par facilité, du 02/11 au 09/11.
let lines = Syslog
  | where TimeGenerated >= datetime(2026-11-02T00:00:00Z) and TimeGenerated < datetime(2026-11-09T00:00:00Z)
  | where _ResourceId endswith "/vm-celebrimbor-bree";
union (lines | project Key = "toutes", TimeGenerated), (lines | project Key = Facility, TimeGenerated)
| order by Key asc, TimeGenerated asc
| extend GapS = iff(prev(Key) == Key, datetime_diff('second', TimeGenerated, prev(TimeGenerated)), long(null))
| summarize Lines = count(), P50GapS = percentile(GapS, 50), P99GapS = percentile(GapS, 99), MaxGapS = max(GapS),
            Over600 = countif(GapS > 600), Over3600 = countif(GapS > 3600) by Key
| order by Key asc
KQL
kq rh12-syslog
cat > ${RET}/rh12-heartbeat.kql <<'KQL'
// RH12 (b) : la période de Heartbeat, par VM, du 02/11 au 09/11.
Heartbeat
| where TimeGenerated >= datetime(2026-11-02T00:00:00Z) and TimeGenerated < datetime(2026-11-09T00:00:00Z)
| extend Vm = case(_ResourceId endswith "/vm-celebrimbor-bree", "bree", _ResourceId endswith "/vm-celebrimbor-gondolin", "gondolin", "")
| where Vm != ""
| project Vm, TimeGenerated
| order by Vm asc, TimeGenerated asc
| extend GapS = iff(prev(Vm) == Vm, datetime_diff('second', TimeGenerated, prev(TimeGenerated)), long(null))
| summarize Beats = count(), P50GapS = percentile(GapS, 50), P99GapS = percentile(GapS, 99), MaxGapS = max(GapS),
            Over180 = countif(GapS > 180) by Vm
KQL
kq rh12-heartbeat
```

**Comment lire.** `MaxGapS` de `Heartbeat` sur bree dit si bree s'est tue. S'il dépasse quelques
minutes, l'agent ou la VM étaient arrêtés : ce n'est pas un silence de `Syslog`, et on le note. Pour
gondolin, `MaxGapS` est une nuit éteinte : seuls `P50GapS` et `P99GapS` comptent.

**Elle tient si** `P50GapS` de `Heartbeat` donne une période nette (de l'ordre de 60 s), et si les
silences de `Syslog` sur bree restent bornés et lisibles (`P99GapS`, `MaxGapS`). **Elle tombe si**
`Heartbeat` n'a pas de période nette (`P50GapS` et `P99GapS` très écartés). **Si elle tombe** : rien
pour `Syslog`, qui ne fait jamais de carte de silence. Le seuil de « muette » d'ING4 se fixe sur ce
qu'on lit (la conception, §10).

**Reporter** : sur #758, la période de `Heartbeat` (`P50GapS`, `P99GapS`) par VM, et pour `Syslog`
sur bree, `P50GapS`, `P99GapS`, `MaxGapS`, `Over3600`, toutes facilités puis par facilité. Puis la
ligne RH12 du §10, par l'Orchestre.

## 9. RH7 — le retard du plan de contrôle et d'Entra

**L'hypothèse** : `AzureActivity` arrive en 3 à 20 min (A1 d'ID1), Entra en quelques minutes (E3). Le
protocole d'ID1 existe (`docs/operations.md`, « Les requêtes de mesure ») ; voici sa requête sur 24 h,
élargie à une semaine absolue. **Ce qu'on sait déjà** : le 12/11, une attribution de rôle a été
ingérée 621 à 623 s après son heure (le compte rendu du banc, hors dépôt).

**Fenêtre** : du 02/11 au 09/11, **au plus tard le 01/12**. Une table à zéro ligne ne versait pas
encore au workspace ces jours-là : on prend alors une semaine plus récente.

```zsh
cat > ${RET}/rh7.kql <<'KQL'
// RH7 : le retard d'AzureActivity et d'Entra, par table, du 02/11 au 09/11.
union withsource=Table isfuzzy=true AzureActivity, AuditLogs, AADServicePrincipalSignInLogs
| where TimeGenerated >= datetime(2026-11-02T00:00:00Z) and TimeGenerated < datetime(2026-11-09T00:00:00Z)
| extend DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| summarize Rows = count(), P50 = percentile(DelayS, 50), P95 = percentile(DelayS, 95), P99 = percentile(DelayS, 99),
            Max = max(DelayS), Over1200 = countif(DelayS > 1200), Over2700 = countif(DelayS > 2700) by Table
| order by Table asc
KQL
kq rh7
```

**Elle tient si** `P95` d'`AzureActivity` reste sous 1 200 s (20 min) et celui des deux tables d'Entra
sous quelques minutes, sans ligne au-delà de 2 700 s (45 min). **Elle tombe si** des lignes passent
45 min. **Si elle tombe** (la conception, §10) : ING7 part, et avec lui le piège de
`entra-sp-unusual-signin` (une connexion arrivée plus d'une heure en retard entre dans sa propre
base). **Reporter** : sur #758, par table, `Rows`, `P50`, `P95`, `P99`, `Max`, `Over2700`. Puis la
ligne RH7 du §10, par l'Orchestre.

## 10. RH8 — le retard de `StorageBlobLogs`

**L'hypothèse** : `StorageBlobLogs` arrive sous 5 min, la fenêtre de `data-exfiltration-blob`
(`detection_rules.yaml:94`). **Fenêtre** : du 01/11 au 12/12, c'est-à-dire ce que le workspace garde
de cette période au moment de la requête. Elle lit le plus de jours vers le 01/12 : avant, moins de
jours ont eu lieu ; après, les premiers sont partis. Les écritures (`PutBlob`, `PutBlock`, `PutBlockList`, celles que lit la règle) sont comptées à part.

```zsh
cat > ${RET}/rh8.kql <<'KQL'
// RH8 : le retard de StorageBlobLogs, les écritures à part, sur ce qui est gardé (01/11 → 12/12).
StorageBlobLogs
| where TimeGenerated >= datetime(2026-11-01T00:00:00Z) and TimeGenerated < datetime(2026-12-12T00:00:00Z)
| extend DelayS = datetime_diff('second', ingestion_time(), TimeGenerated),
         Write = OperationName in ("PutBlob", "PutBlock", "PutBlockList")
| summarize Rows = count(), Days = dcount(bin(TimeGenerated, 1d)), P50 = percentile(DelayS, 50), P95 = percentile(DelayS, 95),
            Max = max(DelayS), Over300 = countif(DelayS > 300) by Write
KQL
kq rh8
```

**Une erreur « Failed to resolve table »**, ou aucune ligne : aucun blob n'a été journalisé dans le
workspace pendant ces jours. RH8 reste ouverte, et un T1041 au banc la mesurera (une attaque : un
geste de Jonathan, hors de cette page). **Elle tient si** `P95` des écritures reste sous 300 s.
**Elle tombe si** des écritures passent 300 s. **Si elle tombe** : ING3 la couvre déjà (la sélection
à l'arrivée), et il faut le dire (la conception, §10). **Reporter** : sur #758, pour les écritures et
pour le reste, `Rows`, `Days`, `P50`, `P95`, `Max`, `Over300`. Puis la ligne RH8 du §10, par
l'Orchestre.

## 11. RH11 — `ingestion_time()` est rempli, et le SDK rend une heure

**L'hypothèse** : `ingestion_time()` est rempli sur `Perf`, `Syslog` et `StorageBlobLogs` (la
documentation). Et le SDK (`azure-monitor-query`, que lit le RulePoller) rend les colonnes d'heure en
`datetime`. **Fenêtre** : la journée du 11/11, **au plus tard le 10/12**. Ensuite, un autre jour.

```zsh
cat > ${RET}/rh11.kql <<'KQL'
// RH11 : la part des lignes dont l'arrivée est remplie, table par table, le 11/11.
union withsource=Table isfuzzy=true Perf, Syslog, Heartbeat, StorageBlobLogs, AzureActivity, AuditLogs, AADServicePrincipalSignInLogs
| where TimeGenerated >= datetime(2026-11-11T00:00:00Z) and TimeGenerated < datetime(2026-11-12T00:00:00Z)
| extend HasArrival = isnotnull(ingestion_time())
| summarize Rows = count(), WithArrival = countif(HasArrival) by Table
| order by Table asc
KQL
kq rh11
```

Et le type des colonnes, lu par le SDK du dépôt (le `.venv` de `make install`) sous le même
`az login`. Le script n'affiche que des noms de types, jamais une valeur ni un message d'erreur :

```zsh
WS=${WS} .venv/bin/python -I - <<'PY' | tee ${RET}/rh11-sdk.txt
import os
from datetime import datetime, timezone
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient

client = LogsQueryClient(DefaultAzureCredential())
span = (datetime(2026, 11, 11, tzinfo=timezone.utc), datetime(2026, 11, 12, tzinfo=timezone.utc))
for table in ("Perf", "Syslog", "Heartbeat", "StorageBlobLogs"):
    query = (f"{table} | where TimeGenerated >= datetime(2026-11-11T00:00:00Z) and TimeGenerated < datetime(2026-11-12T00:00:00Z)"
             " | take 1 | project TimeGenerated, Arrived = ingestion_time()")
    try:
        result = client.query_workspace(os.environ["WS"], query, timespan=span)
        rows = [row for t in result.tables for row in t.rows]
        print(table, "aucune ligne" if not rows else " ".join(type(v).__name__ for v in rows[0]))
    except Exception as exc:
        print(table, "erreur :", type(exc).__name__)
PY
```

**Elle tient si** `WithArrival` égale `Rows` pour chaque table, et si le script dit
`datetime datetime` pour chaque table qui a une ligne. **Elle tombe si** une table a des arrivées
vides, ou si le SDK rend un texte. **Si elle tombe** (la conception, §10) : une table sans arrivée
garde sa fenêtre sur l'heure, et la note du chargement d'ING2 le dit. Un texte au lieu d'une heure
change le lecteur d'ING2. **Reporter** : sur #758, `Rows` et `WithArrival` par table, et la ligne du
script par table. Puis la ligne RH11 du §10, par l'Orchestre.

## 12. RH9 — l'agent date-t-il une ligne à sa réception ? (un geste)

**L'hypothèse** : l'agent date une ligne `Syslog` à sa réception, pas par l'heure écrite dans la ligne.
Sinon, un utilisateur de la VM (root, ou un autre : `/dev/log` est ouvert à tous) écrit une ligne
datée dans le passé, au-delà de l'horizon, ou dans le futur, au-delà de la fin de la fenêtre de l'API
(« maintenant + 1 min », la conception, §9).

**Le geste**, de Jonathan, non destructif. Une Run Command sur gondolin écrit trois lignes dans
`/dev/log`, chacune avec une date écrite à la main : deux au format RFC 3164, une au format RFC 5424.
`logger` date toujours à l'instant et ne prend pas une date à la main : c'est pourquoi on passe par
`python3`.
- La facilité est `daemon` (code 29, `daemon.notice`) : la règle de collecte du banc la prend
  (`infra/terraform/monitoring.tf:47`), et aucune règle livrée ne la lit.
- L'étiquette est `eregion-rh9`.
- La Run Command de l'opérateur ne fait pas de carte : `run-command-by-glorfindel-outside-isolation`
  ne regarde que l'identité de Glorfindel (`docs/operations.md`).
- Le retour en arrière : rien, trois lignes de journal.
- Le coût : gondolin allumée quelques minutes.

```zsh
make celebrimbor-start VM=gondolin          # si elle est arrêtée ; elle s'éteint à 23 h UTC
cat > ${RET}/rh9.sh <<'SH'
#!/bin/sh
# RH9 : trois lignes daemon.notice dans /dev/log, datées à la main (3 h avant, 30 min après, 3 h avant). Rien d'autre.
python3 - <<'PY'
import socket, time
now = time.time()
def rfc3164(t): return time.strftime("%b %e %H:%M:%S", time.gmtime(t))
def iso(t): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))
sent = iso(now)
frames = [
    f"<29>{rfc3164(now - 3 * 3600)} eregion-rh9: eregion-rh9 form=3164 claimed=past-3h sent={sent}",
    f"<29>{rfc3164(now + 1800)} eregion-rh9: eregion-rh9 form=3164 claimed=future-30m sent={sent}",
    f"<29>1 {iso(now - 3 * 3600)} - eregion-rh9 - - - eregion-rh9 form=5424 claimed=past-3h sent={sent}",
]
s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
s.connect("/dev/log")
for f in frames:
    s.send(f.encode())
print("sent", sent)
PY
SH
SENT=$(az vm run-command invoke -g rg-celebrimbor -n vm-celebrimbor-gondolin --command-id RunShellScript \
  --scripts @${RET}/rh9.sh --query 'value[0].message' -o tsv | sed -n 's/.*sent \([0-9TZ:-]*\).*/\1/p')
print -r -- "envoyé à ${SENT}" | tee ${RET}/rh9-envoi.txt
```

Puis, **15 minutes après** (le temps de `Syslog`), et **une seconde fois 45 minutes après**, quand
l'heure de la ligne « future » est passée :

```zsh
cat > ${RET}/rh9.kql <<'KQL'
// RH9 : les trois lignes datées à la main, leur heure dans le workspace, leur arrivée ; la borne `sent` vient devant.
Syslog
| where TimeGenerated >= sent - 4h and TimeGenerated < sent + 1h
| where _ResourceId endswith "/vm-celebrimbor-gondolin"
| where SyslogMessage contains "eregion-rh9"
| extend Form = extract(@"form=(\d+)", 1, SyslogMessage), Claimed = extract(@"claimed=(\S+)", 1, SyslogMessage)
| project Form, Claimed, TimeGenerated, EventTime = column_ifexists("EventTime", datetime(null)), Arrived = ingestion_time(),
          SkewS = datetime_diff('second', TimeGenerated, sent), DelayS = datetime_diff('second', ingestion_time(), TimeGenerated), ProcessName
| order by Form asc, Claimed asc
KQL
{ print -r -- "let sent = datetime(${SENT});"; print -r -- "$(<${RET}/rh9.kql)"; } > ${RET}/rh9-lu.kql
kq rh9-lu
```

**Comment lire.** `SkewS` est l'écart entre l'heure que le workspace donne à la ligne et l'envoi. Il
vaut à peu près 0 si l'agent date à la réception, −10 800 s (3 h) s'il prend la date écrite. La ligne
« future », si elle est datée à sa date écrite, n'apparaît qu'à la seconde lecture : le `--timespan`
s'arrête à maintenant. `EventTime` dit ce que la table garde de la date écrite.

**Elle tient si** les trois lignes ont `SkewS` sous la minute, en valeur absolue. **Elle tombe si**
une ligne a `SkewS` près de −10 800 s ou de +1 800 s. **Si elle tombe** (la conception, §9, §10) :
root date ses lignes. L'horizon (une ligne plus vieille que 2 h n'est jamais jugée) et la fin de la
fenêtre de l'API se contournent, et cela se dit au modèle de menace. **Reporter** : sur #758, pour
chaque ligne, `Form`, `Claimed`, `SkewS` et `DelayS`, et si `EventTime` porte la date écrite. Puis la
ligne RH9 du §10, par l'Orchestre.

## 13. RH10 — la durée des requêtes, après ING3

**L'hypothèse** : trois requêtes rendent en quelques secondes :
- `ransomware-disk-write` sur 130 min ;
- `ssh-brute-force`, avec son tri et son `join` ;
- la vue du retard sur 48 h.

**Après ING3**, quand la release qui le porte tourne sur Imladris (anciennement H0). Chaque règle du plan des données,
une fois, telle que la watch la lance, avec sa durée :

```zsh
make imladris-ssh              # puis, sur Imladris :
docker exec eregion-watch glorfindel rules check --live
exit
```

La ligne de chaque règle dit `✓ N ligne(s), X s`. **Après ING4**, la durée de la vue du retard se
lit là où ING4 la dit.

**Facultatif, dès maintenant** : une estimation de la vue sur 48 h, dans la forme du §8 de la
conception. Ce n'est pas la requête d'ING4. Elle porte sur « maintenant », et c'est la seule de cette
page dont la fenêtre est relative (`ago`). Le temps mesuré compte celui d'`az` : on le compare à une
requête vide.

```zsh
print -r -- 'print Now = now()' > ${RET}/rh10-vide.kql
cat > ${RET}/rh10-vue.kql <<'KQL'
// RH10 (estimation) : la vue du retard du §8 — 48 h de TimeGenerated, les lignes arrivées dans les 10 dernières minutes.
union withsource=Table Perf, Syslog, Heartbeat
| where TimeGenerated > ago(48h)
| where ingestion_time() > ago(10m)
| extend Vm = case(_ResourceId endswith "/vm-celebrimbor-bree", "bree", _ResourceId endswith "/vm-celebrimbor-gondolin", "gondolin", "autre")
| extend DelayS = datetime_diff('second', ingestion_time(), TimeGenerated)
| summarize Rows = count(), P50DelayS = percentile(DelayS, 50), MaxDelayS = max(DelayS), Oldest = min(TimeGenerated) by Vm, Table
KQL
time kq rh10-vide
time kq rh10-vue
```

**Elle tient si** chaque règle rend en moins de 10 s, un tiers de l'intervalle de 30 s de ces règles
(un seuil de lecture proposé ici, pas une mesure). Et la vue doit rendre en quelques secondes de plus
que la requête vide. **Elle tombe si** une règle ou la vue dépasse ce seuil. **Si elle tombe** (la
conception, §10) : `H` baisse, ou la règle change de forme. **Reporter** : sur #758, la durée de
chaque règle, et celle de la vue moins la requête vide. Puis la ligne RH10 du §10, par l'Orchestre.

## Ce que Jonathan note à la fin

Un commentaire sur #758, **des chiffres seulement** (des secondes, des comptes, des heures UTC),
sans identifiant ni sortie brute : les fichiers de `${RET}` restent sur le poste. DH2 et DH11 vont
sur #727. La forme :

| N° | Lu le | Le chiffre | Verdict |
|---|---|---|---|
| RH5 | JJ/MM | phase 3, par table et par quarantaine : `Rows`, `BeforeLift`, `AfterLift` | tient / tombe / illisible |
| RH3 | | `Syslog`, par moment : première et dernière arrivée, retards min et max | |
| RH4 | | la première heure livrée, les lignes par table, la dernière arrivée après la levée | |
| RH6 | | pour chaque quarantaine : sa durée en marche, son rattrapage | |
| RH1, RH2 | | `P50`, `P95`, `P99`, `Max`, `Over600`, les heures en retard et leur raison | |
| RH12 | | la période de `Heartbeat` ; les silences de `Syslog` sur bree | |
| RH7 | | par table : `P95`, `Max`, `Over2700` | |
| RH8 | | les écritures : `Rows`, `Days`, `P95`, `Over300` | |
| RH11 | | `WithArrival` / `Rows` par table ; les types du SDK | |
| RH9 | | `SkewS` des trois lignes ; `EventTime` | |
| RH10 | | la durée de chaque règle ; celle de la vue | |

Une requête refusée par Log Analytics (une erreur de syntaxe, une colonne absente) se note avec son
message, sans identifiant. Elle se corrige ici, dans un lot relu, et se relance avant sa date limite.

**Ensuite** : l'Orchestre reporte chaque résultat à sa ligne du §10 de la conception
(`docs/design/mesure-en-retard.md`), et DH2 et DH11 au §9 du dossier, par un lot relu. Il route ce
qui change :
- RH5, RH3, RH4 et RH6 vers LEV3 et LEV4, le §7 ;
- RH2, RH3, RH4 et RH6 vers ING3 (l'horizon, Q2) ;
- RH7 vers ING7 ;
- RH9 vers le modèle de menace ;
- RH12 vers ING4.
