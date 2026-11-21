# Les alertes de l'hébergeur comme signaux : Defender for Cloud et Sentinel (DEF1, #1020) — conception

_Conception — 21/11 (DEF1, #1020) — statut : **conception seulement, questions ouvertes** (§9). Rien
n'est codé, activé ni mesuré. Jonathan a décidé le lot le 21/11, à la suite de la dixième passe de
revue (20/11, question A) : préparer un adaptateur, sans rien activer. L'effort d'Eregion reste sur la
réponse et la preuve ; l'adaptateur n'est qu'une source de détection de plus, et le premier lot est une
mesure (§5)._

**Lié** : [`correlation.md`](correlation.md) (COR1 : un fait établi par le code, avant la décision) ;
[`corroboration.md`](corroboration.md) (SEC-A3 : Defender for Endpoint y est la source C, « pour un
client qui l'a déjà, plus tard ») ; [`mesure-en-retard.md`](mesure-en-retard.md) (ING1 : une ligne jugée
à son arrivée) ; [`dossier-isolation.md`](dossier-isolation.md) (DOS1 : un fait sur la carte, jamais vu
du modèle) ; [`reponse-identite.md`](reponse-identite.md) ; [`identites.md`](identites.md) (IDM1 : ce que
tient chaque identité) ; [`modele-de-menace.md`](modele-de-menace.md) ; [`docs/glorfindel.md`](../glorfindel.md)
(le RulePoller, l'attribution d'une ligne, les gardes de `decide`).

**Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne (au
commit `1d2ee0ab`, la base de la branche : une fusion plus récente de `main` peut décaler les lignes). Ce qui est dit de Defender for Cloud, de Sentinel, de Microsoft Graph et de leurs
prix vient de la documentation publique de Microsoft, lue le 21/11 (§10), ou de l'API publique des prix
de détail d'Azure. Ce sont des **hypothèses**, numérotées HA1 à HA21 (§5.6), à mesurer avant le code
qui en dépend : au banc pour la plupart, chez un client qui a Sentinel pour HA17, HA19 et HA20. La conception n'a appelé ni Azure ni le modèle.

---

## 0. En bref

- **Ce qui manque.** Glorfindel ne voit que ce que lisent ses 20 règles livrées : les mesures et les
  journaux que la VM écrit, le journal d'activité, les journaux d'Entra ID. Ce que les produits de
  l'hébergeur voient de plus (le comportement d'un processus, un logiciel malveillant connu, une analyse
  faite chez Microsoft), il ne le lit pas. Et rien n'en est mesuré : ni la latence de ces alertes, ni ce
  qu'elles voient sur les VM Linux du banc, ni leur coût.
- **La voie recommandée** : une requête KQL sur la table `SecurityAlert`, dans le workspace que Glorfindel
  lit déjà. Elle est alimentée par l'export continu de Defender for Cloud, ou par Sentinel quand le client
  l'a. Aucun droit nouveau : `Log Analytics Reader` suffit. L'API des alertes d'ARM se mesure à côté,
  comme repli. Graph est écarté : sa permission lit les alertes de tout le tenant.
- **Une alerte devient un signal du contrat dans la watch même**, comme une ligne du RulePoller, jamais
  par le canal `runs/`. Seule la requête livrée, par son nom et son empreinte, a ses colonnes lues comme
  écrites par le service (la forme d'ATT1 et de MID1). L'alerte est retenue par son type, dans une liste
  fermée écrite dans le dépôt, et attribuée à une VM par sa ressource (`ResourceId`), jamais par un nom ;
  sinon elle n'est attribuée à aucune VM, et suit SLF1. `ProductName` ne prouve rien : une règle de
  Sentinel le réécrit.
- **Le workspace est une racine de confiance** (§4.3). Qui peut y écrire, une règle d'analyse ou une
  transformation, peut forger une alerte. Les identités de Glorfindel n'y ont que la lecture.
- **En v1, l'alerte n'atteint pas le modèle et ne fait aucune action autonome.** Sa décision est
  construite par le code, comme celles du plan de contrôle (AL1) et des identités (C2). Cette décision
  saute la chaîne des gardes de `decide` : ce qui tient, c'est le constructeur, qui ne propose jamais
  d'action sur une VM sans attribution, et ATT1 (`approval_refusal`), qui refuse en un clic toute carte
  non attribuée visant une VM. Son texte vient du dehors : il est échappé et borné partout où il
  s'affiche. Le montrer un jour au modèle serait un lot à part, avec son run de bout en bout, sur décision
  de Jonathan (Q3).
- **Une règle livrée n'est jamais retenue par une alerte.** Quand les deux voient la même chose,
  l'alerte s'ajoute comme un fait à la carte de la règle, par une correspondance écrite dans le dépôt. Le
  silence de l'hébergeur ne prouve rien. La couverture d'Eregion reste celle de ses propres règles.
- **La mesure d'abord, de la main de Jonathan, et payante** (§5) : Defender for Servers Plan 1 sur une
  seule VM du banc, le temps du test, et l'export continu vers le workspace du banc. On joue des alertes
  d'exemple, le fichier de test EICAR, puis T1486 et la technique de BL1, déjà jouées. On compare la
  latence, ce qui est vu, l'attribution et le coût, sur des critères écrits avant la mesure. Prix publics
  de détail : environ 0,0067 USD par heure et par VM pour le Plan 1, 0,02 USD pour le Plan 2.
- **Huit lots** (§6), DEF2 à DEF9, dont deux conditionnels ; le premier est la mesure. **Huit questions**
  pour Jonathan (§9).

---

## 1. Le constat

### 1.1 Ce que les règles livrées mesurent aujourd'hui

Le RulePoller lance chaque règle dans son fil, une requête par cycle (`poll_once`,
`glorfindel/detection_rules.py:1948`). Les 20 règles de `glorfindel/rules/azure/detection_rules.yaml` :

| Plan | Règles | Tables lues | Intervalle |
|---|---|---|---|
| données | 9 : T1486, T1041, T1110.001, T1548.003, T1059.004 (deux), T1136.001, T1053.003, T1070.002 | `Perf`, `StorageBlobLogs`, `Syslog` | 30 à 60 s |
| contrôle (AL1) | 7 | `AzureActivity` | 60 s |
| identités (C2) | 4 | `AuditLogs`, `AADServicePrincipalSignInLogs` | 120 à 300 s |

**Les chiffres mesurés** (`docs/proofs.json`) :
- `detect_range` : la détection d'une première attaque au banc en **44,7 s** (20/10) à **144 s** (31/10) ;
- `detect_median` : **107 s** en médiane sur 30 jours (au 27/10) ;
- `contain_ransom` : **7 min 43 s** de l'attaque T1486 à l'isolement relu sur Azure (12/11).

**L'ingestion en retard (ING1).** La fenêtre d'une règle porte sur `TimeGenerated`, avec une marge de
300 s (`_INGESTION_MARGIN_S`, `glorfindel/detection_rules.py:1147`). D'après ING1, une ligne qui arrive
plus de 10 minutes après son heure n'est jamais jugée. Le banc l'a montré le 11/11 : après la levée de bree,
des mesures `Perf` sont arrivées jusqu'à 27 minutes en retard ([`docs/glorfindel.md`](../glorfindel.md),
[`mesure-en-retard.md`](mesure-en-retard.md)). La correction est conçue, pas codée.

**Ce qu'elles lisent est écrit par la VM.** Sur le plan de données, `Syslog` est forgeable par un
utilisateur local, et `Perf` vient de l'agent de l'invité ([`corroboration.md`](corroboration.md), §2.3 ;
le modèle de menace, §4, lignes « S »). Elles ne lisent ni l'arbre des processus, ni les fichiers, ni la
mémoire, ni une réputation de fichier ou d'adresse.

### 1.2 Ce que les produits de l'hébergeur promettent (hypothèses)

**Defender for Cloud** produit des alertes quand un plan Defender est actif sur une ressource (S1). Pour
une VM, c'est **Defender for Servers** (S8) :
- **le Plan 1** s'appuie sur Defender for Endpoint (EDR). Sous Linux, ses capacités demandent l'agent de
  Defender for Endpoint, que l'activation installe d'office (S8, S9) ;
- **le Plan 2** ajoute, entre autres, l'analyse sans agent, la détection sur la couche réseau d'Azure,
  le suivi d'intégrité des fichiers et 500 Mo d'ingestion gratuits par jour et par nœud (S8, S11) ;
- la liste des alertes Linux (S10) donne des détections **propres au Plan 2**, en plus de celles de
  Defender for Endpoint : « Behavior similar
  to ransomware detected » (High), « Failed SSH brute force attack » (Medium), « Successful SSH brute
  force attack » (High), « New SSH key added » (Low), « A history file has been cleared » (Medium),
  « Disabling of auditd logging » (Low). La même page prévient que des alertes récentes de Defender for
  Endpoint peuvent ne pas y figurer, et que des alertes de sources différentes mettent des temps
  différents à apparaître ;
- la sévérité va de High à Informational, et une alerte reste visible 90 jours (S1) ;
- pour valider la chaîne sous Linux, la documentation donne le fichier de test EICAR : « a new alert
  should appear in the Defender for Cloud Alerts blade within 10 minutes » (S12).

Aucune page lue ne donne la latence de l'export continu vers un workspace (§8).

**Sentinel** est le SIEM de Microsoft, posé sur un workspace. Toutes les alertes, celles des produits
Defender comme celles des règles planifiées de Sentinel, vont dans la même table `SecurityAlert` (S2).
Les incidents vont dans `SecurityIncident` (S6). Après le 31/03/2027, Sentinel ne vivra plus que dans le
portail Defender (S14).

**Le coût** (prix de détail de l'API publique d'Azure, région westeurope, lus le 21/11, en USD hors
remise : S15, S16) :

| Produit | Prix | Par mois de 730 h | Remarques |
|---|---|---|---|
| Defender for Servers Plan 1 | 0,00672 USD par heure et par nœud | ~4,9 USD par VM | activable sur une seule VM (S8, S9) |
| Defender for Servers Plan 2 | 0,02 USD par heure et par nœud | ~14,6 USD par VM | sur l'abonnement entier seulement (S8) |
| Sentinel, à l'usage | 5,59 USD par Go analysé | — | sur tout ce que le workspace ingère et facture ; les alertes de Defender for Cloud y sont gratuites (S14) |

- Un plan Defender se facture à l'heure. Son activation ouvre un essai de 30 jours, qu'on ne peut ni
  suspendre ni prolonger (S8, S9).
- Sentinel a un essai de 31 jours, 10 Go par jour (S14).
- Pour comparer : Imladris (anciennement H0) coûte environ 61 € par mois en continu (`docs/proofs.json`, `host_cost`).

### 1.3 Ce que ça veut dire pour Eregion

- **Une alerte de l'hébergeur est une détection, pas une réponse.** Ce qu'Eregion apporte, c'est la
  réponse réversible et vérifiée, et la preuve. Une alerte est une détection de plus à laquelle Glorfindel
  peut répondre, sous ses propres gardes.
- **Pour un client qui paie déjà Defender ou Sentinel**, lire ces alertes ne coûte rien de plus, et
  élargit ce que Glorfindel voit. **Pour un client qui ne les a pas**, l'adaptateur n'est pas une raison
  de les acheter : les règles livrées restent la base, et Glorfindel est toujours présent.
- **Aucun chiffre ne tranche encore.** La mesure décide (§5).

---

## 2. Ce que l'adaptateur lit, et par quelle voie

### 2.1 Ce qu'il lit

Les alertes de Defender for Cloud sur les VM inscrites. Pour chaque alerte, ces champs (les noms de
`SecurityAlert`, S2, S4, S5 ; ceux de l'API d'ARM sont leurs équivalents, S7) :

| Champ | Sert à | Écrit par |
|---|---|---|
| `SystemAlertId` | l'identité de l'alerte, d'une passe à l'autre | le service |
| `AlertType` | ce qu'est l'alerte : la clé de la liste fermée (Q5) | le service ; pour une règle planifiée de Sentinel, l'identifiant de la règle (S2), que choisit son auteur (S22) |
| `ProductName`, `ProviderName`, `VendorName` | la carte seule : **ils ne prouvent rien** | le service ; une règle planifiée réécrit les deux premiers (S23) |
| `AlertSeverity`, `Status` | la sévérité du signal ; l'état, dit sur la carte | le service ; une règle planifiée réécrit la sévérité (S23) ; le statut, aussi un humain chez l'hébergeur |
| `StartTime`, `EndTime`, `ProcessingEndTime`, `TimeGenerated`, `ingestion_time()` | la fenêtre et la latence | le service, le workspace |
| `ResourceId` | l'attribution | le service |
| `Entities` (un texte JSON) | l'accord sur la ressource ; les adresses, comptes et processus pour la carte | le service, avec des valeurs que l'invité choisit : nom d'hôte, ligne de commande, nom de fichier |
| `SubTechniques`, `Techniques`, `Tactics` | la technique du signal, la sous-technique d'abord ; leur forme (JSON ou virgules) est à mesurer (HA21) | le service ; une règle planifiée réécrit `Techniques` et `Tactics` (S23) |
| `AlertName`, `Description`, `RemediationSteps`, `ExtendedProperties`, `AlertLink` | la carte seule | le service, avec des valeurs de l'invité dans le texte (`%{user name}`, `%{Compromised Host}` dans les modèles de description, S10) |
| `CompromisedEntity` | la carte seule, **jamais l'attribution** | un nom d'affichage |

« Le service », c'est le service de Microsoft, ou quiconque écrit dans le workspace : une transformation
du workspace peut réécrire toute colonne de la table (S5, HA18). C'est la racine de confiance du §4.3.

**Ce qu'il ne lit pas en v1** :
- `SecurityIncident`, un regroupement fait par l'hébergeur : la carte dirait un incident sans ses alertes ;
- les recommandations et le score de sécurité ;
- les tables brutes de Defender for Endpoint (`Device…`), dont l'ingestion est payante (S14) ;
- les alertes des autres plans (stockage, coffres de clés) : la v1 n'attribue qu'à une VM.

### 2.2 Les voies

| Voie | Ce qu'il faut en amont | Le droit de lecture | Pour | Contre |
|---|---|---|---|---|
| **A. KQL sur `SecurityAlert`** dans le workspace déjà lu | l'export continu de Defender for Cloud vers ce workspace, en flux (S3) ; ou le connecteur de Sentinel sur ce workspace (S13) | `Log Analytics Reader`, déjà tenu | le même lecteur que `Perf`, `Syslog`, `AzureActivity` et Entra ID (`AzureMonitorDetector`, le SDK déjà épinglé) ; la même passe, le même statut, les mêmes chemins d'erreur ; les alertes de Sentinel aussi, quand il existe ; `ingestion_time()` donne la latence ; le faux Azure n'a qu'à rendre des lignes | un saut de plus, l'export, de latence inconnue (HA1) ; le `_ResourceId` de la ligne est inconnu (HA3), et SEC-A4 interdit de le réécrire dans la requête : il faut un adaptateur à soi (§2.4) ; une mise à jour serait une ligne de plus (HA4) ; une ligne fait au plus 32 Ko (S3) |
| **B. L'API d'ARM des alertes**, groupe par groupe (`Microsoft.Security/alerts`, api-version 2022-01-01) | rien de plus que le plan | `Reader` sur le groupe (S17 ; HA6) | pas d'export ; une ressource typée (`resourceIdentifiers`, `AzureResource`, `azureResourceId`) ; le statut courant ; bornée d'elle-même aux groupes où Glorfindel lit, c'est-à-dire au périmètre ; un lecteur borné d'ARM existe déjà (`_arm_get`, `_arm_paged`, `glorfindel/providers/azure/door.py:136-174`) ; une liste par minute et par groupe reste très loin de la limite d'ARM (250 lectures, 25 par seconde de recharge, par abonnement et par principal, S19) | les alertes de Defender for Cloud seules, pas celles de Sentinel ; un second chemin de détection, hors du workspace, avec son propre faux ; la pagination ; pas d'heure d'ingestion : la latence se mesure autrement |
| **C. Graph, `GET /security/alerts_v2`** | Defender for Cloud intégré à Defender XDR ; Sentinel rattaché au portail Defender pour ses alertes (S20) | `SecurityAlert.Read.All` en application : les alertes de **tout le tenant**, tous produits Defender confondus, messagerie et identités comprises (S21) | une vue unifiée, les incidents, des preuves avec `vmMetadata.resourceId` ; des filtres sur la date, la sévérité, la source et le statut (S21) | une lecture de tout le tenant sur une identité que la console, le bot et tout processus d'Imladris partagent (le modèle de menace, §5 ; [`identites.md`](identites.md), §3.1) ; l'identité Graph prévue n'est « jamais l'identité d'Imladris » ([`identites.md`](identites.md), §3.9) ; une frontière nouvelle |
| **D. Le journal d'activité**, catégorie `Security`, vers `AzureActivity` | ajouter la catégorie `Security` au paramètre de diagnostic de l'abonnement (aujourd'hui `Administrative` seule : `docs/operations.md`, « Rien d'autre ») | `Log Analytics Reader` | la source d'AL1 lit déjà `AzureActivity` | la ressource de la ligne est l'alerte (`Microsoft.Security/locations/alerts/…`), et la VM n'y figure que par son nom d'affichage, `compromisedEntity` (S4) : une attribution par un nom, refusée (V-04), donc toute alerte non attribuée ; le journal d'activité arrive en 3 à 20 minutes (S18) |
| **E. Event Hubs**, par l'export continu | un espace de noms, un hub, un export | un rôle de lecture des données du hub, et un consommateur | les alertes poussées, sans sondage | une ressource de plus, facturée ; un SDK, une identité et un point de reprise de plus ; un consommateur qui ne doit rien perdre ; tout hors du RulePoller |

### 2.3 La voie recommandée : A, et B mesurée à côté

1. **Aucun droit nouveau** : `Log Analytics Reader`, déjà tenu par Imladris et par la paire de la watch
   d'un poste ([`identites.md`](identites.md), §3.1 et §3.3). **Aucune frontière nouvelle** : le
   workspace est déjà la source de toute détection (le modèle de menace, §4 et §5).
2. **Le même mécanisme qu'AL1 et C2** : une source du workspace, son adaptateur dans
   `glorfindel/providers/azure/` (MC0), sa règle livrée désactivée par défaut. La passe du RulePoller, ses
   erreurs dites, son statut, ses plafonds et sa déduplication servent tels quels, et le faux Azure teste
   des lignes.
3. **Elle lit ce que le client a déjà** : le workspace de son Sentinel, ou un export. Une seule requête
   lit les deux. Mais une même alerte peut arriver deux fois, par l'export et par le connecteur (HA17).
   Et le connecteur de Sentinel demande Sentinel dans le portail Azure (S13), qui ne le sera plus après
   le 31/03/2027 (S14) : l'alimentation recommandée est donc **l'export continu**, une fonction de
   Defender for Cloud qui ne dépend pas du portail de Sentinel (HA20).
4. **La mesure départage** : si le saut de l'export est trop lent (HA1), ou si `ResourceId` ne nomme pas
   la VM (HA3), B est le repli. On la mesure dans la même séance, pour la même alerte (§5).

**Pourquoi pas B d'abord.** Sa latence est peut-être meilleure. Mais elle ne lit que Defender for Cloud.
Elle ajoute un second chemin de détection, hors du workspace, avec son faux à tenir. Et le droit de
`Reader` sur un groupe pour les alertes n'est pas mesuré (HA6).

### 2.4 Ce que la voie A demande au code

- **Sa propre source, pas une règle KQL de plus.** Une règle du plan de données route ses lignes par
  `_ResourceId` ou `CallerIpAddress`, quand sa requête les prouve. `ResourceId` n'est jamais lu pour le
  plan de données (`RowAttribution`, `glorfindel/detection_rules.py:1676-1714`, les `keys` aux lignes
  1690-1692). Une requête qui écrit une clé de routage, `extend _ResourceId = ResourceId` par exemple, est
  refusée (`eregion_core/rule_routing.py:16-20`). SEC-A4 tient donc : l'adaptateur lit `ResourceId` dans
  le code, dans sa propre source (`azure_security_alert`, avec son plan), comme `activity.py` et
  `entra.py` font leur lecture avant que les lignes ne les quittent
  (`glorfindel/providers/azure/activity.py:9-35`, `glorfindel/providers/azure/entra.py:19-33`). Une
  entrée de plus au registre des sources (`_DETECTORS`, `glorfindel/detectors.py:19-23`).
- **Ses colonnes de confiance, lues seulement sous la requête livrée.** La source fait confiance à
  `ResourceId`, `Entities`, `AlertType`, `SystemAlertId` et aux techniques. Or la règle s'allume dans la
  couche du client (P1), qui peut remplacer la requête livrée sous son nom. Une requête du client pourrait
  alors écrire ces colonnes (`extend ResourceId = …`), lire une autre source (`union`, `datatable`) ou les
  fabriquer. Deux pièces le tiendraient :
  - **retenue : la forme d'ATT1 et de MID1.** Seule la règle livrée, par son nom et sa requête à l'octet
    (une copie à la lettre, WL1, comprise), a ses colonnes lues comme écrites par le service
    (`shipped_query`, `glorfindel/detection_rules.py:450-458` ; `own_channel.is_shipped`,
    `glorfindel/own_channel.py:151-157`). Une autre requête de cette source tourne quand même, mais ses
    lignes ne sont jamais attribuées (SLF1), ne se rapprochent d'aucune règle livrée et ne proposent
    aucune action ; la watch le dit au chargement, comme elle dit une règle livrée remplacée (SEC2). C'est
    une liste blanche d'une seule requête, relue en PR : elle échoue fermée, et le dépôt l'applique déjà
    deux fois ;
  - **en option : le refus par `rule_routing` étendu.** Pour cette source, refuser à la lecture du texte
    toute requête qui écrit l'une de ces colonnes, ou lit autre chose que `SecurityAlert` (`union`,
    `datatable`, `print`, `externaldata`, `evaluate`, `let`). Le client garderait sa requête, ses filtres
    et sa fenêtre. Mais c'est une liste noire sur une lecture du texte, « not KQL's parser »
    (`eregion_core/rule_routing.py:26-27`), qui devrait suivre chaque forme nouvelle de KQL. À retenir
    seulement si un client a besoin de sa propre requête.
- **La fenêtre sur l'arrivée.** Une alerte arrive en retard par construction : une analyse, puis un
  export. Une fenêtre sur `TimeGenerated` perdrait celles qui dépassent la marge (ING1). Elle se choisit
  donc par `ingestion_time()`, et se déduplique par `SystemAlertId` : c'est le mécanisme que recommande
  ING1 ([`mesure-en-retard.md`](mesure-en-retard.md), §3.3). Le regard en arrière reste long, comme celui
  d'AL1 (`MIN_LOOKBACK_S = 1800.0`, `glorfindel/providers/azure/activity.py:63`).
- **Une ligne par alerte** : la plus récente par `SystemAlertId` (HA4).
- **Désactivée à la livraison** (`enabled: false`), allumée dans la couche du client (P1,
  [`docs/glorfindel.md`](../glorfindel.md), « Couches de règles »).

---

## 3. Comment une alerte devient un signal

### 3.1 Le chemin

L'alerte est lue dans la watch, par le fil de sa règle, puis passe par `_dispatch`, la file de décision
de la VM et le graphe, comme toute détection du RulePoller. **Jamais par le canal `runs/`** : une ligne
`detection` écrite dans le canal y est refusée (`glorfindel/signal_origin.py:25-28`, `CHANNEL_EVENTS`,
ligne 59). Un injecteur ne peut donc pas se faire passer pour Defender, et aucun fichier d'Imladris ne
porte l'alerte.

### 3.2 Le mapping vers le contrat

Le contrat est `Signal` (`eregion_core/signals.py:30-41`). Le RulePoller en écrit les mêmes champs
(`glorfindel/detection_rules.py:2296-2328`). L'adaptateur fait de même :

| Champ du contrat | Valeur | D'où |
|---|---|---|
| `signal_id` | `rule-<règle>-<8 hex>`, comme le RulePoller | Glorfindel ; jamais l'identifiant de l'alerte, qui va dans `context` |
| `timestamp` | l'instant de la passe | Glorfindel |
| `provider` | `azure` | — |
| `resource_id` | l'identifiant complet de la VM, celui du registre, quand l'alerte est attribuée ; sinon la VM d'ancrage (SLF1) | §3.3 |
| `resource_type` | `vm` | — |
| `ttp` | la première sous-technique de `SubTechniques` (forme `T1234.567`), sinon la première technique de `Techniques` (forme `T1234`), si le catalogue ou les règles la connaissent (`known_techniques`, `glorfindel/signal_origin.py:151`) ; sinon aucune, et la carte le dit. Elle sert à la carte et au rapprochement (§3.6), jamais à la classe de la file (§3.4) | le service, filtré (HA21) |
| `severity` | §3.4 | le service, borné |
| `event` | `detection` | — |
| `raw_signal` | `detection_source` : `azure_security_alert` ; `first_result_row` : la ligne, chaque texte borné ; `normalized_signal` : l'indicateur `provider_alert`, absent des indicateurs reconnus (`RECOGNIZED_INDICATOR_KEYS`, `glorfindel/detection_rules.py:222`) | l'adaptateur |
| `context` | `rule_name`, `asset_name`, `run_id` (`watch-<règle>-<ts>`), `attribution` (et `candidates`), `plane` : `provider_alert`, et `alert` : son identifiant, son type, son produit, son statut, ses quatre heures | l'adaptateur |

Le plan `provider_alert` est nouveau. `decide`, `load_context` et `investigate` le reconnaissent avant
tout le reste, comme ils reconnaissent le plan de contrôle et les identités (§3.7, N1).

### 3.3 L'attribution

1. `ResourceId` nomme une VM (`/microsoft.compute/virtualmachines/`, une sous-ressource ramenée à sa VM,
   comme le fait `RowAttribution`), et le registre la connaît par son identifiant complet, sans tenir
   compte de la casse.
2. Si `Entities` porte une ressource Azure, elle nomme la même VM. Si elle en nomme une autre, ou
   plusieurs, l'alerte n'est pas attribuée : un doute ne vaut jamais une attribution (A0). Qu'une telle
   entité existe est une hypothèse sans source (HA14) : dans l'exemple de l'API d'ARM, la VM est dans
   `resourceIdentifiers`, et `entities` ne porte qu'une adresse (S7). Par la voie B, l'accord se lit sur
   `resourceIdentifiers`.
3. **Le type de l'alerte est dans une liste fermée, écrite dans le dépôt** (Q5) : des types de Defender
   for Cloud, relus, ceux de la correspondance de DEF5 et ceux que la mesure aura vus. Un autre type n'est
   jamais attribué : selon Q5, il est compté sans carte, ou fait une carte non attribuée. **`ProductName` ne prouve rien** : une règle planifiée de Sentinel le réécrit, comme
   `ProviderName`, la sévérité, les techniques, le nom et la description (S23), et une transformation du
   workspace peut réécrire toute colonne (HA18). La liste fermée réduit sans prouver : le type d'une alerte
   de règle planifiée est l'identifiant de la règle (S2), et l'auteur de la règle choisit cet identifiant
   (S22 ; HA19). Ce qui reste est la racine de confiance du §4.3.
4. **Jamais** `CompromisedEntity`, ni le nom d'hôte ou l'adresse d'une entité : root sur une VM choisit
   son nom d'hôte, et une ligne routée par lui faisait isoler une autre VM (V-04 ; le modèle de menace,
   §4).
5. Sinon, l'alerte n'est attribuée à aucune VM, et suit **SLF1**. Elle est ancrée sur une VM surveillée
   qu'elle ne nomme pas. La carte dit « non attribuée » et ses candidates, et l'enregistre
   (`attribution`, `glorfindel/escalations.py:303-319`). **Aucune action sur une VM n'y est proposée** :
   la décision construite par le code ne passe pas par la garde de l'attribution (`_ATTRIBUTION_HELD`,
   `glorfindel/agent.py:826`), c'est donc le constructeur de DEF4 qui s'en charge. Et si une telle carte
   en portait une, ATT1 refuse de l'exécuter en un clic, quel que soit son type (`approval_refusal`,
   `glorfindel/approval.py:58-72` ; `unattributed_aim`, `eregion_core/action_queue.py:93-102`), à
   condition que la carte enregistre son attribution. Les alertes d'exemple, faites pour des ressources
   simulées (S12), prennent ce chemin (HA15).
6. Une alerte qui nomme une VM hors des cibles de la règle suit la conduite actuelle du RulePoller pour
   une telle ligne. DEF3 la fixe par un test.

### 3.4 La sévérité

| Defender | Signal | Carte |
|---|---|---|
| High | `high` | oui |
| Medium | `medium` | oui |
| Low | `low` | non : comptée au statut de la règle et au rapport (Q6) |
| Informational | aucun signal | non : comptée. Ces alertes ne valent que dans un incident (S13) |

**Jamais `critical`.** Chez Eregion, le critique vient du code : la corrélation d'un brute force réussi
(COR1), une opération sous l'identité de Glorfindel ou sur ce qu'il gère
(`glorfindel/detection_rules.py:2287-2289`). La sévérité d'un hébergeur ne la donne pas.

**Jamais la classe grave de la file.** La file de décision classe les détections : la critique d'abord,
puis celle d'une technique grave (`GRAVE_TTPS` : T1486, T1485, T1490, T1041, T1567), puis les autres
(`glorfindel/decision_queue.py:15-16`, ligne 70). Une alerte de technique T1486 y passerait devant les
autres détections de sa VM, et un root qui provoque de telles alertes sur sa VM y gagnerait la place. La
technique d'une alerte est la lecture de l'hébergeur, ou de qui écrit le workspace : le signal se range
dans la classe ordinaire, quelle que soit sa technique. Une détection d'une règle livrée d'une technique
grave, sur la même VM, passe toujours devant.

### 3.5 L'identité et les mises à jour

- **L'identité est `SystemAlertId`**, comme celle d'une opération d'AL1 est son `CorrelationId`, et celle
  d'une détection de C2 son `EventId` (`_row_identity`, `glorfindel/detection_rules.py:1233-1241` : « a line ingested late is the same
  one »). Une ligne de même identifiant est la même alerte : jamais une nouvelle carte.
- **Une mise à jour** (un statut résolu ou rejeté, une alerte « seen multiple times » qui grossit) met la
  carte à jour et le dit (« rejetée chez l'hébergeur à 14:02 »). Les statuts diffèrent selon la voie :
  `New`, `InProgress`, `Resolved`, `Dismissed`, `Unknown` dans `SecurityAlert` (S2) ; `Active`,
  `InProgress`, `Resolved`, `Dismissed` par ARM (S7). Une mise à jour ne ferme jamais la carte (Q7) :
  Security Admin peut rejeter une alerte, et Contributor et Owner aussi, à la portée de l'abonnement
  (S17). Avec la synchronisation dans les deux sens du connecteur, fermer un incident de Sentinel ferme
  aussi l'alerte d'origine (S13).
- **Une même alerte arrivée deux fois**, par l'export et par le connecteur (HA17) : `SystemAlertId` ne la
  dédoublonne peut-être pas. D'ici la mesure chez un client qui a les deux, DEF3 dédoublonne aussi par
  le type, la ressource et `StartTime`.

### 3.6 Le dédoublonnage avec une règle livrée

1. **Une règle livrée n'est jamais retenue, adoucie ni fondue à cause d'une alerte.** Sa détection est
   décidée comme aujourd'hui.
2. **Une alerte s'ajoute, comme un fait, à la carte d'une règle livrée qui voit la même chose**, à trois
   conditions : la même VM, par son identifiant complet ; une correspondance écrite dans le dépôt entre le
   type d'alerte et la règle (`VM_SshBruteForceSuccess` et `ssh-brute-force` corrélée par COR1, par
   exemple : une alerte propre au Plan 2, que la mesure au Plan 1 ne verra pas, ce que DEF5 dira) ; une fenêtre bornée. Le fait dit : « vu aussi par Defender for
   Cloud : <nom>, <sévérité>, à 14:02, 95 s après la règle ». Il n'y a ni nouvelle carte, ni décision.
3. **Sans correspondance, ou hors de la fenêtre, l'alerte a sa carte.** Deux attaques différentes sur une
   VM restent deux cartes.
4. **L'alerte d'abord, la règle ensuite** : la règle décide comme toujours, et sa carte nomme celle de
   l'alerte.
5. **Le fait vit à côté du signal**, comme le dossier d'une isolation (DOS1) : jamais dans ce que lit le
   modèle.
6. **La couverture reste celle des règles.** `rulepoller_recently_matched`
   (`glorfindel/detection_rules.py:1520`) lit le statut de toute règle par technique. La proposition
   d'une règle s'en sert pour ne pas proposer quand le RulePoller a vu l'attaque
   (`glorfindel/agent.py:3242-3243`). Une alerte comptée là cacherait un trou des règles de Glorfindel :
   le statut de l'adaptateur n'y répond jamais. L'indicateur de couverture de la feuille de route compte
   les règles de Glorfindel ; ce que l'hébergeur a vu se dit à côté.

**Pourquoi pas un dédoublonnage par technique seule.** Les techniques d'une alerte sont la lecture de
l'hébergeur. Une correspondance écrite et relue dans le dépôt se teste.

### 3.7 Ce qui ne doit jamais arriver

| N° | Jamais | Ce qui le tient, ou le tiendra |
|---|---|---|
| **N1** | une action autonome sur une alerte, ou une action sur une VM qu'elle ne nomme pas | la décision est construite par le code avant le mode, comme `_control_plane_decision` (`glorfindel/agent.py:1233-1277`) et `_identity_decision` (ligne 1298), aiguillées en tête de `decide` (lignes 2050-2053). **Cette décision saute toute la chaîne des gardes** (lignes 2035-2047), celle de l'attribution comprise : il n'y a pas de défense en profondeur dans `decide`. Pour AL1 et C2, rien n'est à approuver (`action: ""`, ligne 1264). Si Q3 retient une action proposée, ce qui tient est double. D'abord le constructeur de DEF4 : `_provider_alert_decision` ne propose jamais d'action sur une VM sans `attribution: asset`. Ensuite ATT1 : `approval_refusal` (`glorfindel/approval.py:58-72`) refuse en un clic, quel que soit son type, toute carte qui se dit non attribuée et porte une action sur la VM, à condition que la carte enregistre `attribution` (`unattributed_aim`, `eregion_core/action_queue.py:93-102`). Le type de carte n'entre dans `APPROVABLE_TYPES` (`eregion_core/action_queue.py:73-79`) qu'avec Q3, option 1 |
| **N2** | une garde contournée par le chemin du modèle | si une alerte atteint un jour le modèle (DEF8), elle passe toutes les gardes, dans leur ordre (`glorfindel/agent.py:2035-2047`) : l'exécutable, la confiance, la garde du signal, l'attribution, la télémétrie, la précondition de levée, le plafond de la règle (RDW1), le mode, l'accord des tirages, le plancher. Aucun champ de l'alerte n'en saute une. L'adaptateur n'écrit aucun champ qu'une garde lit comme une preuve : ni `attribution: asset` sans preuve du code, ni `Correlation`, ni `GlorfindelManaged` |
| **N3** | un incident ouvert ou nourri | `load_context` ouvre et nourrit l'incident d'un signal du plan de données (`glorfindel/agent.py:286-299`), et `_build_user_message` écrit au modèle les techniques de l'incident (lignes 3679-3690). Une alerte qui nourrirait l'incident atteindrait le modèle par le cycle suivant de la VM. Comme une identité (lignes 286-287), elle n'ouvre ni ne nourrit aucun incident, et n'inscrit aucun fait du plancher B3a |
| **N4** | son texte au modèle | `_build_user_message` écrit le signal entier en JSON (`glorfindel/agent.py:3651-3653`) : une alerte qui prendrait le chemin du modèle y enverrait sa description, ses entités, ses lignes de commande. En v1, aucun appel (N1). Deux tests : aucun appel au modèle sur ce plan ; le message de tout autre signal, inchangé à l'octet |
| **N5** | un précédent de la mémoire | aucun cycle de ce plan n'est rendu comme précédent, comme le plan de contrôle (`past_cycles: []`, `glorfindel/agent.py:288-293`) |
| **N6** | une attribution par un nom | §3.3, point 4 (V-04) |
| **N7** | le silence pris pour une preuve | aucun fait « Defender n'a rien vu » ; aucune garde ne lit l'adaptateur |
| **N8** | une écriture chez l'hébergeur | ni rejet, ni statut, ni commentaire. Ni `SecurityAlert.ReadWrite.All`, ni Security Admin pour Glorfindel |
| **N9** | un texte du dehors écrit brut | échappé partout où il s'affiche : au terminal (`outside()`, `glorfindel/terminal.py:48`), dans la console (`_attr`, `eregion_console/static/glorfindel.js:4242`), dans Discord (`discord_text`, `glorfindel/chat_text.py:37`). Chaque champ est borné, et la carte dit quand il est coupé |
| **N10** | une alerte par le canal `runs/` | §3.1 |

### 3.8 Le texte du dehors

Même la description qu'écrit Microsoft embarque des valeurs de l'invité : `%{user name}`,
`%{Compromised Host}`, et les lignes de commande des entités (S10). Root sur la VM choisit son nom
d'hôte, ses noms de processus et le contenu de ses fichiers. Le texte entier est donc du dehors, comme
une ligne `Syslog`. Chaque champ est borné (DEF6). `Entities` se lit comme du JSON, avec une borne sur le
nombre d'entités et la profondeur ; un JSON illisible est dit « illisible », jamais vide (A0). Le modèle
n'en voit rien en v1. Un lot plus tard (DEF8) n'enverrait que des champs structurés d'une liste fermée
(type, sévérité, techniques, heures, attribution), jamais la description ni les entités, avec le run de
bout en bout (`CLAUDE.md`, « Conventions »).

---

## 4. Les droits, et ce qui change au modèle de menace

### 4.1 Qui lit, et sous quel droit

Imladris tient aujourd'hui `Reader` sur le groupe du banc, `Log Analytics Reader` sur son workspace,
Response sur le groupe (posé à la main), Session Drain VM par VM, et ses deux rôles sur le canal. Aucune
permission de Graph n'est posée ([`identites.md`](identites.md), §3.1). La paire de la watch d'un poste
tient `Reader` et `Log Analytics Reader` sur les groupes inscrits (même document, §3.3).

| Voie | Lecture | Rôle (d'après la documentation) | Tenu par Imladris ? |
|---|---|---|---|
| A | `SecurityAlert` du workspace | `Log Analytics Reader` | oui |
| B | `Microsoft.Security/alerts` du groupe | `Reader` : « View alerts and recommendations » est permis à Security Reader et à Reader (S17) | oui sur le papier, à mesurer à la portée d'un groupe (HA6) |
| C | Graph, `alerts_v2` | `SecurityAlert.Read.All`, en application, sur tout le tenant (S21) | non, et il ne doit pas l'être |
| D | `AzureActivity`, catégorie `Security` | `Log Analytics Reader` | oui, mais l'attribution y est impossible |
| E | Event Hubs | un rôle de lecture des données du hub | non |

**Le moindre privilège.** Les voies A et B ne demandent rien de nouveau. L'adaptateur ne tient jamais un
droit d'écriture : ni Security Admin, ni Contributor, ni `SecurityAlert.ReadWrite.All`. Ce lot de
conception ne touche aucun fichier que lit `scripts/identity_map.py check`.

### 4.2 Qui configure : jamais Glorfindel

| Geste | Droit (d'après la documentation) | Qui |
|---|---|---|
| activer Defender for Servers, sur l'abonnement ou le Plan 1 sur une VM | Security Admin, ou Contributor ou Owner à la portée de l'abonnement ; Owner pour toutes les capacités d'un plan (S17) | Jonathan au banc ; l'administrateur chez un client |
| l'export continu vers le workspace | Security Admin ou Owner sur le groupe ; l'écriture sur la ressource cible ; la lecture de la solution `SecurityCenterFree` du workspace, ou son écriture si elle n'y est pas (S3) | idem |
| le connecteur de Sentinel | Contributor ou Owner sur l'abonnement ; lecture et écriture du workspace de Sentinel (S13) | idem |
| les alertes d'exemple | Contributor de l'abonnement (S12) | idem |

- **Au banc**, ce sont des gestes de Jonathan (§5.3), comme les paramètres de diagnostic d'ID1,
  « désactivées par défaut » (`docs/operations.md`).
- **Un lot plus tard** (DEF7) écrit l'export en Terraform, désactivé par défaut, sur l'instance canonique
  seule ; l'`apply` reste à Jonathan. `tests/unit/test_bench_logs.py` vérifie que les catégories envoyées sont exactement celles que
  lisent les règles livrées. L'export n'est pas une catégorie de diagnostic : le test gagne sa ligne.
- **Chez un client**, Eregion n'active jamais un plan : il lit ce qui existe. Si la table est vide ou
  absente, la préparation dit « aucune alerte de l'hébergeur dans le workspace ».
- **Les requêtes KQL de la mesure** (§5) se lisent sous `lecteur-banc`, l'identité de la session Banc (`Log Analytics Reader` sur
  le seul workspace du banc, [`identites.md`](identites.md), §3.3). Ses résultats partent vers le modèle
  de cette session, comme toute requête du banc (le modèle de menace, §8).

### 4.3 Ce qui change au modèle de menace

| Ce qui change | Ce qui le tient | Ce qui reste ouvert |
|---|---|---|
| **§1, §3** : un texte du dehors de plus sur les cartes (nom, description, entités) | N9 : l'échappement et les bornes | — |
| **§4** : rien ne part au modèle en v1. « Ce qui ne part jamais » gagne les alertes de l'hébergeur (DEF4 met la page à jour) | N1, N4 | DEF8 le changerait, par son propre lot |
| **§5** : aucun droit nouveau sur la voie A | — | sur la voie B, le `*/read` de `Reader` lit déjà les alertes aujourd'hui, sans que rien ne les lise |
| **une source que l'invité provoque** : root sur une VM déclenche des alertes sur sa propre VM (un fichier EICAR suffit, d'après S12) | une carte, jamais une action autonome ; au plus 5 cartes par règle et par passe, le reste dans une carte par VM qui le nomme (`_DATA_CARDS_PER_POLL`, `glorfindel/detection_rules.py:1488`) ; la file de la VM bornée à 50 (`QUEUE_MAX`, `glorfindel/decision_queue.py:59`) ; jamais la classe grave, quelle que soit la technique (§3.4) ; la déduplication par `SystemAlertId` | le bruit sur sa propre VM ; l'opérateur le pèse |
| **une alerte qui nomme la mauvaise VM** | `ResourceId`, écrit par le service ; l'accord des entités ; la liste fermée des types (Q5) ; la requête livrée seule (§2.4) | la façon dont le service fixe `ResourceId` pour une alerte de la couche réseau (Plan 2), à mesurer (HA3) ; d'ici là, une famille d'alertes dont la ressource viendrait d'une adresse reste non attribuée |
| **le workspace, racine de confiance : qui peut y écrire peut forger une alerte**. Y écrivent l'export de Defender for Cloud, le connecteur de Sentinel, les règles d'analyse de Sentinel, qui réécrivent `ProductName`, la sévérité, les techniques et les textes (S23) et choisissent leur identifiant, donc leur `AlertType` (S2, S22 ; HA19), et une transformation du workspace, qui peut réécrire toute colonne, `ResourceId` comprise (S5 ; HA18) | une racine **assumée** ; le même pouvoir porterait sur les tables que lisent déjà les règles livrées, si une transformation y réécrit les colonnes (HA18). Les identités de Glorfindel n'y ont que la lecture (Imladris, les paires : `Log Analytics Reader`), Glorfindel ne forge donc pas sa propre alerte ; la table n'accepte pas l'API d'ingestion des journaux (S5, HA7) ; la liste fermée des types réduit, sans prouver ; en v1, une alerte forgée fait une carte, jamais une action autonome ; les alertes d'exemple nomment des ressources simulées (HA15) | qui tient l'écriture du workspace (une règle d'analyse, sa transformation) fait une carte attribuée à n'importe quelle VM inscrite, d'un type de la liste. Avec Q3, option 1, une alerte High forgée propose `isolate_vm` à un humain, qui juge. À inscrire au modèle de menace (DEF4) |
| **le statut changé chez l'hébergeur** (une alerte rejetée) | dit sur la carte, ne la ferme jamais (§3.5) | — |
| **le silence de l'hébergeur** | N7 | — |
| **la voie de Graph, écartée** : une lecture de tout le tenant sur l'identité d'Imladris | pas prise | si un jour : l'identité Graph dédiée prévue ([`identites.md`](identites.md), §3.9), jamais celle d'Imladris |

« Une frontière nouvelle a sa page avant d'être livrée » (le modèle de menace, « Comment ce document
vit ») : la voie A n'en ajoute aucune, le workspace est déjà la source de toute détection. Les voies B et
C en ajouteraient une.

---

## 5. La mesure au banc, avant toute décision

C'est un geste de Jonathan, et il est payant : un plan Defender, une attaque sur le banc (`CLAUDE.md`,
« Jamais seule »). Le protocole exact sera `docs/banc-defender.md` (DEF2) : les gestes, les requêtes en
lecture seule, la fiche des résultats.

### 5.1 Ce qu'on veut savoir, et les critères écrits avant

| Critère | La question |
|---|---|
| **C1, la latence** | pour une même attaque, le temps de T0 à l'alerte lisible par Glorfindel (son arrivée dans le workspace ; sa première apparition dans la liste d'ARM), face à la détection de la règle livrée (44,7 à 144 s aujourd'hui) |
| **C2, ce qui est vu** | pour chaque technique jouée : une alerte ou non, son type, sa sévérité, sa technique ; et ce qu'ont vu les règles livrées |
| **C3, l'attribution** | chaque alerte de la VM la nomme par `ResourceId`, et ses entités sont d'accord ; aucune n'en nomme une autre |
| **C4, le coût** | les heures facturées, lues dans Cost Management après coup ; ramenées à une VM et à un mois au prix public ; face à Imladris (~61 € par mois) |
| **C5, les effets de bord** | Defender for Endpoint sur la VM ne bloque ni n'altère la technique du banc (HA10) ; il ne fait aucune carte des règles de Glorfindel (HA11) ; le temps de son installation |

**La grille, écrite avant la mesure** :
- **coder** (DEF3 et la suite) si C3 tient, et si l'une des deux est vraie : Defender voit au moins une
  technique du banc que les règles ne voient pas (C2) ; ou il voit plus tôt une technique que les règles
  voient (C1) ;
- **une corroboration seulement** (une note pour SEC-A3, pas d'adaptateur) si C3 tient mais que C1 et C2
  n'apportent rien ;
- **arrêter** si C3 tombe (l'attribution ne passe pas par la ressource), ou si C5 casse le banc.

### 5.2 Le dispositif

- **Une seule VM inscrite du banc**, en zone `bench` : la règle de production est tenue.
- **La VM en `human_only` le temps de la mesure** : Glorfindel détecte sans agir, pour qu'une isolation
  ne coupe pas en pleine attaque la télémétrie de l'une des deux sources (que la quarantaine retienne la
  télémétrie de l'invité est une hypothèse d'ING1, non mesurée). C'est le choix de Jonathan.
- **Defender for Servers Plan 1 sur cette VM seule**, au niveau de la ressource (un `PUT` du prix de la VM,
  `subPlan: P1`, S9). Le Plan 2 seulement selon Q1.
- **L'export continu** : les alertes seules, en flux, toutes sévérités, vers le workspace du banc.
- **Pas de Sentinel** : son coût porterait sur toute l'ingestion du workspace, et la table est la même.
- **L'adaptateur n'existe pas** : la mesure lit à la main, en lecture seule, KQL et ARM depuis le poste.
- **Hors des autres séances du banc** et du drill de la semaine (DRL1).

### 5.3 Les étapes

| Étape | Geste ou lecture | Ce qu'elle établit |
|---|---|---|
| **G0** | lire les plans déjà actifs sur l'abonnement du banc, et si l'essai de 30 jours y a déjà servi (une lecture, Jonathan) | HA12 |
| **G1** | le Plan 1 sur la VM ; l'heure notée | — |
| **G2** | l'export continu ; l'heure notée | — |
| **G3** | attendre l'installation de Defender for Endpoint (l'extension de la VM) ; la durée notée | C5 |
| **M0** | des alertes d'exemple, depuis le portail (S12) | la forme d'une ligne d'une ressource simulée, la latence de l'export, le chemin d'une alerte non attribuée (HA1, HA3, HA5, HA15) |
| **M1** | le fichier de test EICAR sur la VM (S12) ; la même alerte lue à la minute dans la liste d'ARM du groupe ; puis rejetée dans le portail par Jonathan | l'attribution (`ResourceId`, `_ResourceId`, `Entities`, `resourceIdentifiers`), les heures, la latence par A et par B, les lignes d'une mise à jour, la forme des techniques (HA1 à HA6, HA14, HA21) |
| **M2** | T1486, joué comme le 12/11, depuis un Orodruin armé (le geste de Jonathan) | C1, C2, C3 ; Defender a-t-il bloqué quelque chose (HA9, HA10) |
| **M3** | la technique de BL1 (T1136.001), de même | C1, C2, C3 (HA9) |
| **M4** | 24 h sans exercice | les alertes sans exercice ; les cartes que l'agent de Defender aurait provoquées (HA11) |
| **G4** | le retrait : le Plan 1 retiré de la VM (le prix `Free`, puis la suppression de la configuration de la ressource, S9), Defender for Endpoint désinstallé, l'export retiré ; l'heure notée ; le coût lu 48 h après | C4 |

### 5.4 Ce que chaque étape lit

**Les latences** :
- **La** : de `StartTime` à `ProcessingEndTime`, l'analyse chez Microsoft ;
- **Le** : de `ProcessingEndTime` à `ingestion_time()`, l'export vers le workspace (voie A) ;
- **Lr** : de `ProcessingEndTime` à la première liste d'ARM qui montre l'alerte, relevée à la minute
  (voie B) ;
- **Lg** : de T0 à la détection de Glorfindel, lue comme aujourd'hui.

**Les colonnes de `SecurityAlert`** : `SystemAlertId`, `VendorOriginalId`, `AlertType`, `AlertName`,
`ProductName`, `ProviderName`, `VendorName`, `AlertSeverity`, `Status`, `StartTime`, `EndTime`,
`ProcessingEndTime`, `TimeGenerated`, `ingestion_time()`, `ResourceId`, `_ResourceId`,
`CompromisedEntity`, `Entities`, `SubTechniques`, `Techniques`, `Tactics`, `_IsBillable`, `_BilledSize`.

**Les champs d'ARM** : `properties.systemAlertId`, `alertType`, `severity`, `status`, `startTimeUtc`,
`endTimeUtc`, `processingEndTimeUtc`, `timeGeneratedUtc`, `resourceIdentifiers`, `compromisedEntity`,
`entities`, `techniques`, `subTechniques` (S7).

### 5.5 Le coût de la mesure

- **Le Plan 1 sur une VM, 48 h** : 48 × 0,00672 ≈ 0,32 USD au prix public, ou rien sous l'essai (HA12).
- **Le Plan 2, si Q1 le retient** : pour chaque VM de l'abonnement, 48 h ≈ 0,96 USD par VM, ou rien sous
  l'essai. Mais l'essai démarre alors pour l'abonnement entier et ne se suspend pas, et Defender for
  Endpoint s'installe d'office sur toute VM de l'abonnement (S8), les hôtes compris s'ils y vivent.
- **L'export** : quelques lignes de `SecurityAlert`, de l'ordre du kilo-octet, au tarif du workspace
  (HA13).
- **Sentinel** : pas activé.
- **Le modèle** : M2 et M3 sont des runs comme les autres, environ 0,05 à 0,10 USD chacun
  (`docs/proofs.json`, `model_cost`). L'adaptateur n'appelle rien.

### 5.6 Les hypothèses

| N° | Hypothèse | Source | Ce qui la mesure | Si elle tombe |
|---|---|---|---|---|
| **HA1** | l'export continu, en flux, écrit une alerte dans `SecurityAlert` du workspace en quelques minutes après `ProcessingEndTime` ; aucune page ne donne de chiffre | S3 (« stream data as it's generated ») | Le, en M0, M1, M2 | si Le dépasse quelques minutes, la voie B passe devant (Q2) |
| **HA2** | sous Linux, une alerte de Defender for Endpoint paraît en moins de 10 minutes | S12 | La, en M1 et M2 | C1 se juge sur le chiffre mesuré |
| **HA3** | `ResourceId` d'une alerte d'hôte est l'identifiant complet de la VM, celui du registre ; le `_ResourceId` de la ligne est inconnu (le workspace, la VM ou rien) | S4 (« Full identifier of the affected resource »), S5 | M1, M2 | si `ResourceId` ne nomme pas la VM : la voie A n'attribue rien, B ou l'arrêt (C3) |
| **HA4** | une mise à jour (un statut, une alerte agrégée) écrit une ligne de plus, de même `SystemAlertId` | des réponses de forum seulement, aucune page officielle | M1 (le rejet par Jonathan) | sinon, une ligne par alerte, et l'identité reste la même |
| **HA5** | `ProductName` vaut `Azure Security Center` pour Defender for Cloud ; pour une alerte venue de Defender for Endpoint par Defender for Servers, la valeur est inconnue. **Une valeur, jamais une garde** : une règle planifiée la réécrit (S23) | S4, S13, S23 | M0, M1, M2 | la carte dit la valeur mesurée ; rien ne la lit comme une preuve |
| **HA6** | `Reader` sur le groupe du banc liste les alertes du groupe (`Microsoft.Security/alerts`) | S17 : « view resource information when assigned one of these roles for the subscription or resource group: Owner, Contributor, or Reader », et « View alerts and recommendations » pour Reader ; S7 ne nomme aucun droit | M1, sous une identité qui ne tient que `Reader` sur le groupe (celle d'Imladris, par un geste de Jonathan, ou une identité de test) | la voie B demanderait Security Reader : un droit de plus |
| **HA7** | `SecurityAlert` n'accepte pas l'API d'ingestion des journaux | S5 (« Ingestion API support : No ») | la documentation, puis un essai refusé au banc si Jonathan le veut | un écrivain de plus dans le workspace : la racine de confiance (§4.3) s'élargit, et le dire. Même si elle tient, une transformation (HA18) et une règle planifiée (HA19) écrivent dans la table |
| **HA8** | le Plan 1 s'active sur une seule VM par l'API, et n'installe Defender for Endpoint que sur elle ; le Plan 2 ne s'active que sur l'abonnement | S8, S9 | G1, G3 | le coût et la portée de la mesure changent (Q1) |
| **HA9** | Defender voit T1486 sous Linux (« Behavior similar to ransomware detected », Plan 2, ou une détection de Defender for Endpoint) ; il ne voit probablement pas T1136.001 (« Suspicious Account Creation Detected » vise un nom proche d'un compte Windows) | S10 | M2, M3 | C2 se juge sur ce qui est mesuré |
| **HA10** | la protection en temps réel de Defender for Endpoint ne bloque ni n'altère la technique du banc | aucune | M2, M3 : ce que les règles livrées ont vu, face au dernier run sans Defender | si elle bloque : on le dit, la comparaison de C1 ne vaut plus, et le banc d'un client équipé diffère du nôtre |
| **HA11** | l'agent de Defender for Endpoint ne fait déclencher aucune règle de Glorfindel (écritures disque, processus) | aucune | M4 | des cartes de bruit, à écarter par la règle avant tout adaptateur |
| **HA12** | Plan 1 à 0,00672 USD par heure et par nœud, Plan 2 à 0,02 USD ; facturé à l'heure ; un essai de 30 jours à la première activation ; on ignore s'il a déjà servi sur l'abonnement du banc | S15, S8, S9 | G0 ; Cost Management après G4 | C4 se juge sur la facture |
| **HA13** | sans Sentinel ni Plan 2, les lignes de `SecurityAlert` exportées sont facturées au tarif du workspace ; leur volume est négligeable | S5 (`_IsBillable`), S11, S14 | `_IsBillable`, `_BilledSize` en M1 | un coût à dire, sans changer la voie |
| **HA14** | `Entities` porte une entité de ressource Azure qui nomme la VM, d'accord avec `ResourceId` ; l'entité d'hôte porte un nom d'hôte, choisi par l'invité | aucune : dans l'exemple d'ARM (S7), la VM est dans `resourceIdentifiers` et `entities` ne porte qu'une adresse ; S2 ne dit que les types d'entités | M1, M2 | sans entité de ressource, le point 2 du §3.3 ne s'applique pas : `ResourceId` seul ; par la voie B, l'accord se lit sur `resourceIdentifiers` |
| **HA15** | une alerte d'exemple nomme une ressource simulée, aucune VM réelle | S12 (« The alerts are for simulated resources ») | M0 | si elle nommait une VM réelle, un Contributor de l'abonnement ferait des cartes attribuées, d'un type peut-être de la liste : c'est la racine de confiance (§4.3), à dire |
| **HA16** | une alerte agrégée (« seen multiple times ») garde son premier `TimeGenerated` et se met à jour dans la journée : une fenêtre sur `TimeGenerated` la perdrait | S10 (« seen multiple times ») ; rien sur son heure | M4, si une telle alerte paraît | la fenêtre sur l'arrivée (§2.4) le couvre de toute façon |
| **HA17** | une alerte qui arrive par l'export continu **et** par le connecteur de Sentinel, dans le même workspace, fait deux lignes ; on ignore si elles ont le même `SystemAlertId` (« the internal unique ID for the alert in Microsoft Sentinel », S2 ; `VendorOriginalId` « unused » pour Defender for Cloud, S4) | aucune | chez un client qui a les deux : le banc n'a pas Sentinel, et la mesure ne l'active pas | deux cartes pour une alerte : la clé de secours (le type, la ressource, `StartTime`, §3.5) devient la règle |
| **HA18** | une transformation du workspace réécrit toute colonne de `SecurityAlert` à l'ingestion, `ResourceId` comprise ; et de même pour les tables que lisent les règles livrées | S5 (« DCR workspace transformation support : Yes ») | la documentation des transformations, en lecture ; aucun essai au banc sans le mot de Jonathan | si une transformation ne pouvait pas toucher `ResourceId`, la racine de confiance se réduirait aux règles planifiées |
| **HA19** | le type (`AlertType`) d'une alerte de règle planifiée est l'identifiant de la règle, que son auteur choisit ; son `ResourceId` est vide, ou rempli par une entité de ressource Azure mappée | S2 (« taken from the rule ID ») ; S22 (`ruleId`, une chaîne, sans contrainte écrite) ; rien sur `ResourceId` | la documentation ; un essai seulement chez un client qui a Sentinel, ou sur le mot de Jonathan | si l'identifiant ne pouvait pas prendre la valeur d'un type de Defender, la liste fermée suffirait contre les règles planifiées ; la transformation (HA18) resterait |
| **HA20** | une fois Sentinel dans le portail Defender (au plus tard le 31/03/2027), les alertes de Defender for Cloud passent par Defender XDR, et le connecteur par tenant n'est plus listé ; l'export continu, lui, écrit toujours dans `SecurityAlert` du workspace, avec les mêmes colonnes | S13, S14 ; rien sur l'export | chez un client passé au portail Defender ; au banc, l'export ne dépend pas de Sentinel | si l'export cessait aussi, la voie B (ARM) deviendrait la voie |
| **HA21** | `Techniques` et `SubTechniques` arrivent sous une forme lisible (un tableau JSON, ou une liste séparée par des virgules : « comma-delineated list », S2), `T1234` dans l'une et `T1234.567` dans l'autre | S2, S5, S7 | M1, M2 | le `ttp` du signal se lit sous la forme mesurée ; illisible, aucune technique, et la carte le dit |

---

## 6. Les lots, si Jonathan dit oui

En jours de travail effectif, à ±50 %, comme la feuille de route. Les mutants sont estimés ; l'Orchestre
donne les plages.

| Lot | Session | Contenu | Ce qu'il prouve | Taille | Mutants |
|---|---|---|---|---|---|
| **DEF2** — la mesure | Tests, gestes de Jonathan | `docs/banc-defender.md` : les gestes G0 à G4, les requêtes en lecture seule de M0 à M4, la fiche ; les résultats reportés ici, au §5.6 ; la grille du §5.1 appliquée | HA1 à HA16, HA18 en lecture, HA21 | 1 j d'écriture, une séance du banc | 0 |
| **DEF3** — le lecteur et sa règle, désactivée | Glorfindel | `glorfindel/providers/azure/security_alert.py` : la source `azure_security_alert`, son plan `provider_alert`, sa lecture faite avant que les lignes ne la quittent (la liste fermée des types, `ResourceId`, l'accord des entités, `SystemAlertId` et la clé de secours de HA17, la ligne la plus récente, la fenêtre sur l'arrivée, les bornes des textes) ; ses colonnes de confiance lues seulement sous la requête livrée, par son nom et son empreinte (§2.4) ; la règle livrée avec `enabled: false` ; le faux Azure gagne des lignes de `SecurityAlert` à la forme mesurée | une ligne mesurée en M1, rejouée sur le faux | 3,5 j | 7 : une attribution par `CompromisedEntity` ; l'accord des entités retiré ; un type hors de la liste attribué ; deux lignes d'une même alerte, deux signaux ; la fenêtre sur `TimeGenerated` ; un texte non borné ; une requête de la couche du client, autre que la livrée, dont les lignes sont attribuées |
| **DEF4** — la décision par le code | Glorfindel | le plan aiguillé en tête de `load_context`, `investigate` et `decide` ; `_provider_alert_decision`, qui ne propose jamais d'action sur une VM sans `attribution: asset` ; le type de carte, son `attribution` enregistrée (SLF1), et son entrée dans `APPROVABLE_TYPES` seulement avec Q3, option 1 ; la classe ordinaire de la file ; ni incident, ni mémoire, ni plancher, ni réponse à `rulepoller_recently_matched` ; le modèle de menace (§4 : « Ce qui ne part jamais », la racine de confiance du workspace) et `docs/glorfindel.md` mis à jour | aucun appel au modèle sur ce plan ; le message de tout autre signal inchangé à l'octet ; une carte non attribuée refusée en un clic par la console, la file signée et le bot | 3 j | 9 : un appel au modèle ; un incident nourri ; un précédent rendu ; une sévérité `critical` ; la classe grave de la file ; une action autonome ; une carte non attribuée High qui propose `isolate_vm` approuvable (vérifié par la console, la file signée et le bot) ; la couverture comptée ; une carte fermée par un rejet chez l'hébergeur |
| **DEF5** — le rapprochement | Glorfindel | la correspondance entre types d'alerte et règles, écrite dans le dépôt, chaque type avec son plan (une alerte propre au Plan 2, que la mesure au Plan 1 n'a pas vue, le dit) ; le fait sur la carte de la règle ; compté au statut | une alerte et une règle sur la même VM : une carte et un fait | 2 j | 4 : une règle livrée retenue par une alerte ; un rapprochement sans correspondance ; un rapprochement entre deux VM ; le fait dans le signal |
| **DEF6** — la carte | Console, Glorfindel (bot, TUI) | la section de la carte dans la console, le champ de Discord, le panneau de la TUI ; « dit par l'hébergeur » ; le statut chez l'hébergeur ; l'échappement et les bornes | une alerte d'exemple rejouée sur le jeu d'exemple | 2 j | 4 : un texte non échappé dans la console, dans Discord, au terminal ; un champ illisible affiché vide |
| **DEF7** — l'export en Terraform | Infra (Celebrimbor) | l'export continu des alertes vers le workspace du banc, `defender_alerts_export_enabled = false` par défaut, sur l'instance canonique seule ; `tests/unit/test_bench_logs.py` étendu ; le Plan 1 par VM en option désactivée ; l'`apply` reste à Jonathan | un `terraform test` contre le faux azurerm | 1 j | 1 |
| **DEF8** — l'alerte au modèle (si Q3 le retient) | Glorfindel | des champs structurés d'une liste fermée ; **run de bout en bout T1486 et un autre TTP, par Jonathan** | le run lui-même | 2 j | 3 (estimés) |
| **DEF9** — un plafond par type d'alerte (plus tard) | Glorfindel | une action autonome permise pour un type d'alerte mesuré, sur le modèle du plafond d'une règle (RDW1), après la précision mesurée (B4a) | à fixer | à fixer | à fixer |

**Total** : environ 12,5 jours pour DEF2 à DEF7, et 25 mutants.

**L'ordre.** DEF2 d'abord : c'est la porte. Si la grille dit « coder », DEF3 et DEF7 partent ensemble,
puis DEF4, puis DEF5 et DEF6. DEF3 code la forme mesurée, pas celle de la documentation. DEF8 et DEF9 ne
partent que sur le mot de Jonathan, après une période d'observation.

---

## 7. Ce qui va ailleurs

- **La corroboration** (SEC-A3, #632) : une alerte de l'hébergeur comme source que la VM ne forge pas,
  avant une action autonome. [`corroboration.md`](corroboration.md) la range en source C, « pour un client
  qui l'a déjà, plus tard ». La mesure dira si elle peut l'être. Ce n'est pas cet adaptateur.
- **ING1** (#738) : l'adaptateur juge par l'arrivée dès le départ. Les lots de code d'ING1 (ING2 et
  suivants) restent indépendants.
- **DOS1** (#727) : le fait « vu aussi par Defender » peut vivre dans le dossier d'une isolation. Si DOS3
  est livré d'abord, ce sera l'un de ses faits.
- **Le multi-cloud** : un pendant AWS (GuardDuty, Security Hub) serait un adaptateur frère, dans
  `glorfindel/providers/aws/`. Pas avant que la boucle Azure soit solide (`CLAUDE.md`, « Ce qu'on ne fait
  PAS »).
- **La preuve en production** : lire en mode ombre les alertes qu'un client a déjà serait la preuve la
  moins chère chez lui. À dire dans les fiches d'adoption, une fois mesuré.

---

## 8. Ce que la conception n'a pas pu établir

- **La latence de l'export continu** vers un workspace : aucune page officielle ne la chiffre (HA1). Une
  recherche n'a rendu que des fils de forum, sur d'autres produits.
- **Le `_ResourceId` d'une ligne de `SecurityAlert`** : la référence de la table donne le type de
  ressource `microsoft.securityinsights/securityinsights`, sans dire ce que vaut la colonne pour une
  alerte de Defender for Cloud (HA3).
- **Si une mise à jour écrit une ligne de plus** : seuls des forums l'affirment (HA4).
- **La valeur de `ProductName`** pour une alerte de Defender for Endpoint passée par Defender for Servers
  (HA5).
- **Si `Reader` à la portée d'un groupe liste les alertes par l'API d'ARM** : la documentation donne la
  vue des alertes à Reader, sur l'abonnement ou le groupe (S17). Reste à mesurer que la liste par groupe
  le respecte (HA6).
- **Si une même alerte arrive deux fois**, par l'export et par le connecteur, et sous quel identifiant
  (HA17). Cela ne se mesure que chez un client qui a les deux.
- **Ce qu'une transformation du workspace peut réécrire**, `ResourceId` et les colonnes standard des
  tables des règles livrées comprises (HA18) ; **et le type d'une alerte de règle planifiée**, son
  identifiant choisi par l'auteur, sa `ResourceId` (HA19).
- **Ce que deviennent les alertes de Defender for Cloud dans le workspace** une fois Sentinel passé au
  portail Defender, au plus tard le 31/03/2027 : le connecteur n'y est plus listé (S13), et rien ne dit
  que l'export change (HA20).
- **La forme réelle de `Techniques` et `SubTechniques`** (HA21).
- **Ce que Defender voit des deux techniques du banc sous Linux** : la liste publique des alertes ne dit
  rien de T1136.001, et prévient qu'une partie des alertes de Defender for Endpoint n'y figure pas (HA9).
- **Si la protection en temps réel gêne la technique du banc** (HA10).
- **Si l'essai de 30 jours a déjà servi** sur l'abonnement du banc : c'est une lecture d'Azure, laissée
  à Jonathan (G0).
- **Les prix en euros, et ceux d'un contrat** : la page des prix de Defender ne les affiche pas sans
  navigateur. Les chiffres viennent de l'API publique des prix de détail, en USD, pour une seule région.

---

## 9. Les questions à Jonathan

Posées une à une par l'Orchestre. L'option recommandée vient en premier, avec sa raison. Rien n'est
décidé à sa place.

**Q1 — Quel plan Defender pour la mesure ?** (§5.2, §5.5)
1. **Le Plan 1 sur la seule VM du test, au niveau de la ressource, le temps de la mesure ; un second temps
   au Plan 2 seulement si le Plan 1 ne voit rien des techniques du banc (recommandée).** C'est le moins
   cher (environ 0,16 USD par jour au prix public), sur une seule VM, et rien ne s'installe ailleurs. Il
   voit les alertes de Defender for Endpoint, mais **ne mesure pas les alertes Linux propres au Plan 2**
   (S10), dont la force brute SSH réussie, l'exemple de rapprochement du §3.6 : DEF5 le dira, type par type.
2. Le Plan 2 sur l'abonnement du banc, pendant l'essai de 30 jours. On a toutes les détections, les
   alertes Linux du Plan 2 comprises, peut-être gratuites. Mais l'essai ne se suspend pas, et Defender for
   Endpoint s'installe sur toute VM de l'abonnement, les hôtes compris s'ils y vivent.
3. Les deux à la suite, dans une même séance : le Plan 1 d'abord, puis le Plan 2 sur l'abonnement. On a
   la réponse complète en une fois, mais le coût et l'empreinte sont ceux de l'option 2.

**Q2 — Par quelle voie l'adaptateur lit-il les alertes ?** (§2.2, §2.3)
1. **KQL sur `SecurityAlert`, dans le workspace déjà lu, alimenté par l'export continu ; l'API d'ARM
   mesurée à côté, en repli (recommandée).** Aucun droit nouveau, le mécanisme d'AL1 et de C2, et un export
   qui ne dépend pas du portail de Sentinel (HA20). Le workspace devient une racine de confiance (§4.3).
2. L'API d'ARM des alertes, groupe par groupe, sous le `Reader` tenu. Pas d'export, et peut-être plus
   rapide. Mais Defender for Cloud seul, et un second chemin de détection à tenir.
3. Graph (`alerts_v2`). Tout Defender, incidents compris. Mais une lecture de tout le tenant, sur une
   identité à poser hors d'Imladris.

**Q3 — Que fait Glorfindel d'une alerte attribuée, en v1 ?** (§3.3, §3.7)
1. **Une carte construite par le code, sans modèle et sans action autonome. Sur une alerte High
   attribuée (un type de la liste, la `ResourceId` d'une VM du registre, la requête livrée), la carte
   propose `isolate_vm` à l'approbation d'un humain, comme la carte du plancher B3a (`FLOOR_TYPE`,
   `glorfindel/agent.py:816`) (recommandée).** La réponse reste celle d'Eregion, en un clic, et rien ne
   part seul. La décision construite par le code saute la chaîne des gardes de `decide` : ce qui tient,
   c'est le constructeur, qui ne propose rien sans `attribution: asset`, et ATT1 (`approval_refusal`), qui
   refuse en un clic toute carte non attribuée visant une VM. Un mutant de DEF4 le vérifie par la console,
   la file signée et le bot. Le prix : une alerte High forgée par qui écrit le workspace propose une
   isolation à un humain (§4.3).
2. Une carte d'information seule, sans action proposée, hors d'`APPROVABLE_TYPES`, comme celles d'AL1 et
   de C2. Le plus prudent : une alerte forgée ne mène qu'à une carte, et l'humain agit hors d'Eregion.
3. Une détection comme une autre, décidée par le modèle sur des champs structurés (DEF8, avec son run de
   bout en bout). Toute la chaîne des gardes joue, celle de l'attribution comprise, et la garde du signal
   retient toute action disruptive seule.

**Q4 — Quand une alerte et une règle livrée voient la même chose ?** (§3.6)
1. **Un fait sur la carte de la règle, seulement par une correspondance écrite dans le dépôt, sur la
   même VM et dans une fenêtre bornée ; sinon l'alerte a sa carte (recommandée).** Une seule carte à
   juger, et deux attaques différentes ne se fondent jamais.
2. Toujours deux cartes. Le plus simple ; l'humain juge deux fois la même chose.
3. Une seule carte par VM et par fenêtre, quelle que soit la technique. Déconseillée : deux attaques
   différentes se fondraient.

**Q5 — Quelles alertes l'adaptateur retient-il ?** (§3.3, §4.3)
1. **Une liste fermée de types d'alerte de Defender for Cloud, écrite et relue dans le dépôt, avec la
   `ResourceId` d'une VM du registre ; toute autre alerte (une règle planifiée de Sentinel, un type hors
   de la liste) est comptée et dite au statut de la règle, sans carte (recommandée).** `ProductName` ne
   prouve rien : une règle planifiée le réécrit (S23). La liste réduit sans prouver, puisque l'auteur d'une
   règle choisit son identifiant, donc son type (HA19). Le reste est la racine de confiance du workspace.
2. Toute alerte lue : seules celles de la liste sont attribuées, les autres font des cartes non
   attribuées (SLF1). On voit davantage, avec plus de bruit, et les règles planifiées du client arrivent
   en cartes.
3. Toute alerte lue et attribuée par sa `ResourceId`. Déconseillée : une règle planifiée ou une
   transformation du workspace y écrit ce qu'elle veut.

**Q6 — Quelles sévérités font une carte ?** (§3.4)
1. **High et Medium ; Low et Informational comptées et dites au rapport, sans carte (recommandée).** Le
   canal reste lisible. D'après Microsoft, une alerte Informational ne vaut que dans un incident.
2. Toutes les sévérités. Rien n'est perdu ; plus de bruit.
3. High seulement. Le moins de bruit ; une alerte Medium, une connexion inhabituelle par exemple, serait
   perdue.

**Q7 — Une alerte rejetée ou résolue chez l'hébergeur ?** (§3.5)
1. **Dit sur la carte, sans jamais la fermer (recommandée).** Security Admin peut rejeter une alerte, et
   Contributor et Owner aussi, à la portée de l'abonnement (S17). Avec la synchronisation dans les deux
   sens, fermer un incident de Sentinel ferme l'alerte d'origine (S13). La carte reste à l'humain
   d'Eregion.
2. Le rejet ferme la carte. Moins de cartes en attente ; un rejet par un tiers les fait disparaître.
3. Ignoré. Le plus simple ; la carte ignore ce que sait l'hébergeur.

**Q8 — Dans quel ordre ?** (§6)
1. **La mesure (DEF2) d'abord, à une prochaine séance du banc ; le code seulement si la grille du §5.1
   le dit (recommandée).** On ne code pas la forme de la documentation, et la décision se prend sur des
   critères écrits avant.
2. DEF3 et DEF4 en même temps que la mesure, livrés désactivés. Plus rapide ; le code suit la
   documentation, et sera repris si la mesure diffère.
3. Rien avant la 1.0. L'effort reste ailleurs ; la question reste sans chiffre.

---

## 10. Les sources (documentation de Microsoft, lue le 21/11)

- **S1** — Defender for Cloud, les alertes et les incidents (les sévérités, 90 jours) — https://learn.microsoft.com/en-us/azure/defender-for-cloud/alerts-overview
- **S2** — Le schéma des alertes de Sentinel (toutes les sources dans `SecurityAlert`, les entités) — https://learn.microsoft.com/en-us/azure/sentinel/security-alert-schema
- **S3** — L'export continu (destinations, flux ou instantanés, rôles, 32 Ko par ligne) — https://learn.microsoft.com/en-us/azure/defender-for-cloud/continuous-export
- **S4** — Le schéma des alertes (Sentinel, journal d'activité, export continu) — https://learn.microsoft.com/en-us/azure/defender-for-cloud/alerts-schemas
- **S5** — La table `SecurityAlert` (colonnes, attributs) — https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/securityalert
- **S6** — La table `SecurityIncident` — https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/securityincident
- **S7** — L'API d'ARM, Alerts - List By Resource Group (api-version 2022-01-01) — https://learn.microsoft.com/en-us/rest/api/defenderforcloud-composite/alerts/list-by-resource-group
- **S8** — Defender for Servers, vue d'ensemble (les plans, la portée, l'essai, l'installation d'office) — https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-servers-overview
- **S9** — Activer Defender for Servers, au niveau d'une ressource — https://learn.microsoft.com/en-us/azure/defender-for-cloud/tutorial-enable-servers-plan
- **S10** — Les alertes des machines Linux — https://learn.microsoft.com/en-us/azure/defender-for-cloud/alerts-linux-machines
- **S11** — Les 500 Mo d'ingestion du Plan 2 — https://learn.microsoft.com/en-us/azure/defender-for-cloud/data-ingestion-benefit
- **S12** — Valider les alertes (alertes d'exemple, EICAR sous Linux) — https://learn.microsoft.com/en-us/azure/defender-for-cloud/alert-validation
- **S13** — Le connecteur de Defender for Cloud pour Sentinel — https://learn.microsoft.com/en-us/azure/sentinel/connect-defender-for-cloud
- **S14** — La facturation de Sentinel (essai, sources gratuites, fin du portail Azure) — https://learn.microsoft.com/en-us/azure/sentinel/billing
- **S15** — L'API publique des prix de détail, Defender for Cloud, westeurope — https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20'Microsoft%20Defender%20for%20Cloud'%20and%20armRegionName%20eq%20'westeurope'
- **S16** — idem, Sentinel — https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20'Sentinel'%20and%20armRegionName%20eq%20'westeurope'
- **S17** — Les rôles de Defender for Cloud — https://learn.microsoft.com/en-us/azure/defender-for-cloud/permissions
- **S18** — Le temps d'ingestion d'Azure Monitor (journal d'activité : 3 à 20 minutes) — https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-ingestion-time
- **S19** — Les limites d'ARM — https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling
- **S20** — La ressource `alert` de Graph (alertes et incidents de Defender XDR) — https://learn.microsoft.com/en-us/graph/api/resources/security-alert?view=graph-rest-1.0 ; ses valeurs (`serviceSource`) — https://learn.microsoft.com/en-us/graph/api/resources/enums-security?view=graph-rest-1.0
- **S21** — Lister les alertes de Graph, `alerts_v2` (permissions, filtres) — https://learn.microsoft.com/en-us/graph/api/security-list-alerts_v2?view=graph-rest-1.0
- **S22** — L'API des règles d'analyse de Sentinel, Alert Rules - Create Or Update (`ruleId`, une chaîne) — https://learn.microsoft.com/en-us/rest/api/securityinsights/alert-rules/create-or-update
- **S23** — Personnaliser le détail d'une alerte de Sentinel (les propriétés qu'une règle planifiée réécrit) — https://learn.microsoft.com/en-us/azure/sentinel/customize-alert-details
