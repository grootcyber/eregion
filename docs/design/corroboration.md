# La corroboration avant toute action autonome (SEC-A3, #632) — conception

> **Statut : conception relue, questions tranchées par Jonathan le 09/11** (§6.1). Rien n'est codé.
> Ce document prépare les lots SEC-A3a à SEC-A3f (§7). Les mesures du §5 sont des gestes de
> Jonathan, au banc, à faire avant le code : décision du 09/11, « mesurer au banc quelles sources
> sont disponibles avant d'écrire le code ».
>
> **La décision de Jonathan (09/11, issue #632).** Une action autonome exige une corroboration par
> une source qu'un utilisateur local ne peut pas écrire : un enregistrement auditd du noyau pour ce
> qui se passe sur la VM, un flux réseau pour une adresse distante. Sans corroboration, la détection
> reste vue. Elle devient une carte pour un humain, jamais une action.
>
> **Lié** : [`correlation.md`](correlation.md) (COR1, COR2, AUD1, B3a), le modèle de menace
> ([`modele-de-menace.md`](modele-de-menace.md), §4, les lignes « S »),
> [`docs/glorfindel.md`](../glorfindel.md) (les gardes de `decide`),
> [`docs/operations.md`](../operations.md) (F1–F4, A1–A13, les coûts).
>
> **Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne
> (au commit `eef16bc7`). Ce qui est dit de Linux (auditd, PAM, sshd, sudo), de l'agent Azure Monitor
> et des journaux de flux vient de leur documentation publique : c'est une **hypothèse**, numérotée
> CR1 à CR16 (§5), à mesurer au banc. Ces numéros ne se confondent ni avec A1–A13 d'AUD1, ni avec
> B1–B5 et F1–F4 de COR2 (`docs/operations.md`), qu'ils réutilisent quand ils le peuvent.
>
> **Règle d'écriture (dépôt public, décision de Jonathan du 09/11).** Tant que le code n'est pas
> livré, ce document dit, pour chaque règle, la source qu'elle lit, si un utilisateur local peut
> l'écrire, et la preuve à obtenir. Il ne dit pas ce qui, aujourd'hui, peut partir seul, ni comment.

## 0. En bref

- **Le constat (V-01).** Les règles livrées qui lisent `Syslog` prennent l'étiquette d'une ligne
  (`ProcessName`) pour la preuve de son émetteur. Or tout utilisateur local d'une VM écrit dans
  `Syslog` sous l'étiquette qu'il choisit.
- **Le point dur.** Le chemin d'auditd posé par AUD1 n'est pas une corroboration. Ses lignes arrivent
  dans `Syslog`, par `audisp-syslog`, sur la facilité `local6`, et n'importe quel utilisateur peut y
  écrire sous la même étiquette. AUD1 le dit lui-même (`infra/terraform/auditd.tf:17-23`). « Un
  enregistrement du noyau » ne tient que par un canal que l'utilisateur local ne peut pas écrire : le
  fichier `/var/log/audit/audit.log`, que seul root écrit, lu par l'agent comme un journal texte,
  vers une table à lui. C'est une collecte nouvelle (Q1, retenue).
- **La preuve d'une adresse distante.** Ce sont les enregistrements de flux **par connexion** (5-tuple)
  des blobs des VNet flow logs, déjà écrits au banc dans un compte de stockage
  (`infra/terraform/monitoring.tf:113-137`). Une connexion de l'adresse vers le port 22, établie, avec
  des octets dans les deux sens au-delà d'une poignée de main (Q5, décidée : SEC-A3f). La table
  agrégée `NTANetAnalytics` ne suffit pas : elle somme les flux d'une source sur 10 minutes (§3.10).
  **Un prérequis** : aucune identité joignable depuis une VM surveillée ne doit pouvoir écrire dans
  le compte qui porte les blobs. Au banc, ce compte était aussi celui des exfiltrations, et l'identité
  managée des VM inscrites y écrit (§2.4). Le lot Infra INF-FL (#654) donne aux flux un compte à eux
  seuls, sans clé partagée, qu'aucune VM n'atteint (CR15). Il est écrit, tenu par un test, appliqué
  au banc et mesuré le 12/11 : CR15 tient, CF1 et CF2 aussi (§2.4).
- **Le mécanisme.** Le code juge, jamais le modèle. Une étape du RulePoller cherche la preuve, hors du
  verrou, comme COR1, COR2 et AUD1. Son verdict voyage à côté du signal, jamais dedans : il arrive
  dans l'état du graphe (`GlorfindelState`), comme `telemetry_gaps`, et n'atteint jamais le prompt.
  Une garde de `decide` retient toute action disruptive dont le verdict n'est pas « corroborée » pour
  l'adresse et la VM qu'elle viserait. Un verdict absent, une source en panne, en retard ou muette :
  une carte (A0).
- **Le prix.** Avec la corroboration, un brute force bloque seul quand les blobs prouvent la
  connexion, quelques minutes après la ligne, et la carte part tout de suite (Q3). Le sudo, la
  création de compte et la commande sensible d'AUD1 attendent le canal d'audit (SEC-A3d, SEC-A3e).
  Le coût de collecte reste faible : les blobs de flux sont déjà écrits, et le canal d'audit est
  estimé sous 1 USD par mois au banc (CR10).

## 1. Le constat, lu dans le dépôt

### 1.1 Qui écrit dans `Syslog`

L'agent Azure Monitor collecte les facilités `auth`, `authpriv`, `syslog`, `daemon`, et `local6` et
`cron` quand leur drapeau est posé (`infra/terraform/monitoring.tf:47`). Une ligne y arrive avec ce
que son émetteur déclare : la facilité, l'étiquette (`ProcessName`) et même le numéro de processus
(`ProcessID`). Seul `_ResourceId` vient de l'agent (CR2). `logger`, ou toute écriture sur
`/dev/log`, ne demande aucun privilège (CR1).

Les règles livrées filtrent sur l'étiquette depuis SEC2 et SEC4c (`ProcessName in ("sshd",
"sshd-session")`, `== "sudo"`, `== "useradd"`), et le code relit l'étiquette depuis SEC13
(`_sudo_to_root`, `glorfindel/detection_rules.py:206`). Ce filtre écarte un programme qui écrit
« USER=root » au hasard d'une ligne. Il n'écarte pas quelqu'un qui choisit l'étiquette.

### 1.2 Comment une action devient autonome

Une action est autonome quand elle passe toutes les gardes de `decide` (`docs/glorfindel.md`, « Gates
extraits en helpers ») et que la VM est en `non_disruptive` (`human_only` par défaut). Les actions
disruptives sont `isolate_vm` et `block_suspicious_ip` (`_DISRUPTIVE_AUTONOMOUS`,
`glorfindel/agent.py:745`, qui nomme aussi `revoke_temp_access`, retirée des actions autonomes et
jamais exécutable). Le garde-fou du signal non caractérisé (`_apply_signal_guardrail`,
`glorfindel/agent.py:1150`) retient une action disruptive sur une ligne qui ne porte aucun indicateur
curé (`RECOGNIZED_INDICATOR_KEYS`, `glorfindel/detection_rules.py:185`). Un instantané (`snapshot`)
n'est pas disruptif : ce garde-fou ne le retient pas (le mode `human_only` et la porte de confiance,
si).

## 2. Règle par règle

### 2.1 La table

« Forgeable » : un utilisateur local, sans privilège, peut faire naître la ligne qui déclenche la
règle. La carte complète, règle par règle, de ce qui peut agir seul reviendra avec SEC-A3b, quand
elle ne décrira plus un point ouvert.

| Règle livrée (`detection_rules.yaml`) | Table lue | Forgeable | Preuve non forgeable à obtenir | Au banc |
|---|---|---|---|---|
| `ransomware-disk-write` (T1486, l. 29) | `Perf` | non : l'agent lit les compteurs du noyau (CR3) | aucune requise | — |
| `data-exfiltration-blob` (T1041, l. 82) | `StorageBlobLogs` | non : écrite par Azure Storage | aucune requise | — |
| `ssh-brute-force` (T1110.001, l. 104) | `Syslog` `auth`, `sshd` | **oui** | **une connexion par 5-tuple** dans les blobs des VNet flow logs : de l'adresse de la ligne vers le port 22 de la VM, autorisée, **établie**, avec des octets dans les deux sens au-delà d'une poignée de main (§3.10, CR13). En plus, là où le canal d'audit existe : `USER_AUTH`/`USER_LOGIN` `res=failed` `addr=<adresse>` écrits par sshd (CR8) | blobs : **écrits** (VNet flow logs vers le compte de stockage du banc), **pas encore lus** par Glorfindel (SEC-A3f). Audit : non |
| `sudo-privilege-escalation` (T1548.003, l. 133) | `Syslog` `authpriv`, `sudo` | **oui** | **audit** : `USER_CMD` `res=success`, écrit par sudo lui-même (CR8) ; sur une image dont sudo n'en écrit pas (décidé par image, jamais par événement), l'`execve` de la commande avec **uid = 0 et euid = 0** sous l'`auid` du compte (clé `root_command`, `exe` = le chemin de `COMMAND=`), à ±2 s. Un `execve` à euid 0 seul ne suffit pas : un programme setuid (`passwd`, `chsh`, `mount`) lancé par n'importe quel compte en a un (§3.9) | **non** : les règles d'audit d'AUD1 sont posables (drapeau désactivé), mais leur canal est `Syslog` (§2.3) |
| COR1 → B3a (`login_after_brute_force` + `root_elevation`, `glorfindel/agent.py:1272`) | `Syslog` (`Accepted` de sshd, sudo) | **oui**, les deux faits | la connexion : `USER_LOGIN` `res=success` `addr=<adresse>` de sshd (CR8) ; les flux ne distinguent pas un échec d'un succès. L'élévation : comme le sudo (§3.9) : `USER_CMD`, ou l'`execve` à uid = euid = 0 sur une image déclarée sans `USER_CMD` (Q6) | **non** |
| `t1136-001-local-account-creation-linux-v1` (l. 217) | `Syslog` `auth`, `useradd` | **oui** | **audit** : la surveillance du CIS `-w /etc/passwd -p wa -k identity` (`exe=/usr/sbin/useradd`, `auid` non requis : Run Command est vu), ou `ADD_USER` écrit par useradd (CR8) | **non** : règle d'audit nouvelle et canal nouveau |
| `auditd-sensitive-root-command` (T1059.004, l. 179) | `Syslog` `local6`, `audisp-syslog` | **oui** (AUD1 le dit) | la règle lit directement la table d'audit (Q7, retenue) | **non** |
| `t1053-003-cron-crontab-replace` (l. 260) | `Syslog` `cron` | oui | — (si un jour elle demande une preuve : `-w /var/spool/cron/crontabs -k cron`) | — |
| `t1070-002-log-tamper` (l. 289), `t1059-004-shell-from-world-writable` (l. 371) | `Syslog` `local6` | oui | lire la table d'audit (Q7) | — |
| Plan de contrôle (`AzureActivity`, l. 440-770) et identités (Entra ID, l. 771-925) | écrites par Azure | non | — : décision construite par le code, jamais autonome (AL1, C2) | — |

L'instantané suit Q2 (§6.1) : autonome sans corroboration, plafonné.

### 2.2 Les règles qui n'en ont pas besoin, et pourquoi

- **`Perf`.** L'agent lit `/proc` et l'écrit lui-même. Un utilisateur local peut **provoquer** une
  écriture disque réelle. C'est un fait réel, pas une ligne forgée : ce cas est hors de V-01. Le
  seuil de la règle et le mode le tiennent (`human_only` par défaut, isolation réversible). CR3
  vérifie qu'aucun point d'entrée local de l'agent n'accepte des compteurs.
- **`StorageBlobLogs`.** Azure Storage écrit l'adresse qu'il voit. Un utilisateur local peut faire un
  vrai envoi, par l'identité de la VM via IMDS. C'est aussi un fait réel, hors de V-01.
- **Le plan de contrôle et les identités** ne font jamais agir seul (`_control_plane_decision`,
  `_identity_decision`).

### 2.3 Le point dur : auditd par `Syslog` n'est pas une corroboration

AUD1 a choisi `audisp-syslog` vers `Syslog`, sur `local6`, plutôt que le journal texte d'AMA. Ce
choix évitait une table, une transformation et un point de collecte (`infra/terraform/auditd.tf:17-23`,
`docs/operations.md`, « L'acheminement »). Il a un prix, écrit dans AUD1 : « une ligne écrite par
`logger -p local6.info` arrive au même endroit ».

Le noyau écrit bien l'enregistrement. Mais le canal qui l'amène au workspace passe par `/dev/log`, que
tout le monde peut écrire. Corroborer une ligne `sshd` forgée par une ligne `audisp-syslog` tout aussi
forgée ne prouve rien. **La corroboration « par auditd » demande donc un canal à part**, que
l'utilisateur local ne peut pas écrire :

| Canal | Qui peut y écrire | Ce qu'il coûte | Avis |
|---|---|---|---|
| **A. Le journal texte d'AMA** : `/var/log/audit/audit.log`, en root seul (CR7), vers une table à lui (`EregionAudit_CL`, nom à fixer), avec une transformation de la DCR qui ne garde que les types utiles | root (auditd) seul | une table personnalisée, une DCR de journal texte, peut-être un point de collecte (CR9) ; l'ingestion (CR10) | **retenu** (Q1, 09/11) |
| B. Les propriétés de confiance de journald ou de rsyslog (`_UID`, `_EXE`, posées par le noyau), recopiées dans le message | — | un gabarit rsyslog à tenir sur chaque VM ; l'agent ne les range dans aucune colonne | fragile : non retenu |
| C. Microsoft Defender for Endpoint (`DeviceLogonEvents`, `DeviceProcessEvents`) | son capteur, en root | une licence par serveur | pour un client qui l'a déjà, plus tard |
| D. `VMConnection` (VM insights, agent de dépendances) | son agent, en root | un agent de plus, sa DCR | réseau vu de la VM seulement : non retenu |

Le canal A tient contre un utilisateur sans privilège, pas contre root : root écrit le fichier. Les
blobs de flux sont écrits par Azure, hors de la VM, et ni un utilisateur local ni root ne les écrit
**tant qu'aucune identité joignable depuis une VM surveillée n'a d'écriture sur le compte qui les
porte** (CR15). Ce n'était pas le cas au banc ; INF-FL le sépare, appliqué et mesuré le 12/11 (§2.4). Et un flux autorisé **ne prouve
pas la source d'un paquet** : seule une connexion établie la prouve (§3.10).
Les deux sources ne protègent donc pas la même chose : §3.9 et §3.10.

### 2.4 Ce qui est collecté, d'après le dépôt

| Source | Où dans le dépôt | État au banc |
|---|---|---|
| `Syslog` `auth`, `authpriv`, `syslog`, `daemon` | `monitoring.tf:47` | collecté |
| `Syslog` `local6` (auditd par `audisp-syslog`) | `auditd.tf`, drapeau `auditd_enabled` | désactivé par défaut. Son état réel n'est pas dans le dépôt : `docs/operations.md` dit « rien ici n'a été planifié ni appliqué » (geste 0, §5) |
| VNet flow logs, **blobs** (enregistrements par 5-tuple) | `monitoring.tf`, `azurerm_network_watcher_flow_log.celebrimbor` (rétention 7 jours). Avant INF-FL, `storage_account_id` visait le compte `exfil` du banc ; depuis INF-FL, le compte des flux, `azurerm_storage_account.flows` (`storage.tf`) | **écrits**. Avant INF-FL, ils n'étaient **pas une preuve** : le compte était aussi la cible des exfiltrations d'Annatar, et l'identité managée de chaque VM inscrite y a `Storage Blob Data Contributor` sur tout le compte (`vm_storage_exfil`). Tout utilisateur local se sert de cette identité par IMDS : il pouvait écrire dans le compte qui porte les blobs. **INF-FL (#654)** leur donne un compte à eux seuls : aucune attribution à une VM, sur lui ni au-dessus ; pas de clé partagée ; aucun conteneur public. C'est écrit, tenu par un test, **appliqué au banc le 12/11** (l'apply ciblé, 2 ajouts, 1 changement, 0 destruction) et mesuré le même jour : CR15 tient (une écriture d'essai depuis gondolin, par son identité managée, refusée en HTTP 403 `AuthorizationPermissionMismatch`, un refus RBAC), CF1 (Network Watcher écrit sans clé : le premier blob 5 min 23 s après l'apply) et CF2 (traffic analytics lit sans clé : une tranche de `NTANetAnalytics` faite des seuls flux d'après la bascule) aussi (`docs/operations.md`, « Vérifier CR15 au banc » ; #654). Glorfindel n'a encore ni le droit de les lire ni le lecteur : SEC-A3f |
| traffic analytics 10 min → `NTANetAnalytics` | `monitoring.tf`, le bloc `traffic_analytics` du flow log | collecté (lu par COR2). Le commentaire de la ressource nommait `AzureNetworkAnalytics_CL`, la table des NSG flow logs retirés ; INF-FL l'a corrigé |
| `MicrosoftAzureBastionAuditLogs` | aucun (COR2 la lit si un client la déclare) | pas de Bastion au banc |
| `/var/log/audit/audit.log` vers une table | aucun | **nouveau** (SEC-A3d) |
| Règles d'audit `identity` (`-w /etc/passwd`…) | aucune dans `infra/terraform/scripts/auditd.sh`. `vm3_auditd.sh` pose `log_tamper` et `shell_exec`, sans extension pour le lancer | **nouveau** |
| `VMConnection`, Defender for Endpoint | aucun | non collecté |

Les VM du baseline ont une adresse publique et SSH ouvert à tous (`allow-ssh`, priorité 1000,
`infra/terraform/network.tf:34-42`). Des scanners d'Internet y font donc de vrais brute force en
continu. Le §5 s'en sert : il mesure la corroboration d'un vrai brute force sans lancer d'attaque.

## 3. Le mécanisme

### 3.1 Le principe

- **Le code, jamais le modèle.** La preuve est cherchée par une requête ou une lecture écrite dans le
  code, avec des valeurs vérifiées (`kql.literal`, SEC4c ; une adresse par `ipaddress`). Le verdict
  n'entre jamais dans le prompt. `_build_user_message` écrit le signal entier (`json.dumps(signal)`,
  `glorfindel/agent.py:2993`), et la watch passe ce signal entier au worker (`glorfindel/cli.py:735`,
  `:803`). Le verdict n'est donc **jamais une clé du signal** : il voyage à côté et se range dans
  l'état du graphe (§3.3). Ni `_SYSTEM_PROMPT`, ni `_build_user_message()`, ni le few-shot ne
  changent. Un test l'exige : le message utilisateur est identique à l'octet avec et sans verdict.
  Sans ce test, la règle de `CLAUDE.md` imposerait un run T1486 et un autre TTP.
- **Quelles lignes la demandent : par la forme de la requête, en liste blanche, jamais par le nom
  de la règle (Q4).** Une liste fermée de tables qu'un utilisateur local ne peut pas écrire : `Perf`,
  `StorageBlobLogs`, `NTANetAnalytics`, la table d'audit du canal A, et les tables du plan de
  contrôle et des identités (déjà jamais autonomes). Une requête est `not_required` seulement si
  les deux conditions tiennent :
  - **une table lue est tout identifiant qui ouvre une expression tabulaire, où qu'il soit** : en
    tête d'une instruction ou d'un pipeline, juste avant un `|`, juste après une `(` qui ouvre un
    argument tabulaire (`join (`, `lookup (`, `in (`, `toscalar(`, `materialize(`…), opérande de
    `join`, `lookup`, `union`, `in` ou `!in`. Chacun doit être une table de la liste, ou un nom lié
    par `let` à une expression qui n'en lit que de sûres. `Perf | where Computer in (Syslog | …)`
    lit `Syslog` ;
  - **chaque opérateur et chaque fonction appartient à une liste fermée reconnue** (`where`,
    `extend`, `project`, `summarize`, `join`, `order by`, `take`, `make_set_if`, `extract`…, ceux des
    règles livrées). Tout le reste rend la corroboration requise, sans chercher à le comprendre :
    `search`, `find`, `table(`, `workspace(`, `app(`, `datatable`, `externaldata`, `print`,
    `evaluate`, `mv-apply`, `partition`, `facet`, `fork`, une fonction enregistrée du workspace (un
    nom qui n'est ni une table de la liste ni un `let`), ou une requête qui ne lit aucune table.

  La seconde condition rattrape ce que la première oublierait : une sous-requête dans une forme
  que le lecteur ne connaît pas fait échouer la liste fermée, donc l'exemption.

  Sinon la ligne en a besoin : `Syslog` d'abord, une table inconnue, une règle du client ou une
  règle proposée. Le jugement est **statique**, fait sur le texte de la requête (commentaires ôtés),
  avant toute requête et sans aucune lecture. `ransomware-disk-write` (`let samples = Perf …;
  samples | join (samples …)`) reste exempté ; `Perf | join (Syslog …)` ne l'est pas. Les regex de
  `_reads_activity_table` et `_reads_entra_table`, qui trouvent un nom n'importe où dans le texte,
  servent à durcir (un plan plus strict). Elles ne servent jamais à exempter : une simple mention
  d'une table sûre n'exempte rien.
- **Quelles actions.** Les actions disruptives autonomes (`_DISRUPTIVE_AUTONOMOUS`). L'instantané
  suit Q2 : autonome sans corroboration, plafonné. La levée d'isolation n'est pas concernée : elle
  n'est autonome que sur le `recovery_complete` de Glorfindel lui-même (SEC3).
- **Aucune dérogation.** La décision ne prévoit pas d'opt-out. Un déploiement sans source déclarée
  voit les lignes de ces tables en cartes.

### 3.2 Où : une étape du RulePoller, une garde de `decide`

1. **L'étape** (`glorfindel/corroboration.py`, nouveau) tourne dans `poll_once`
   (`glorfindel/detection_rules.py:1572`), après le routage et l'écart d'ADM1, à côté de
   `correlation.settle` (l. 1617). Elle tourne hors du verrou, et une faute ne fait jamais tomber la
   passe : elle devient un verdict `unknown` et la passe continue, comme `faults`. Elle interroge la
   source **pour la VM du registre** (la ressource où la ligne a été routée, toutes les adresses
   de toutes ses interfaces pour les blobs de flux), jamais pour celle qu'écrit la ligne, comme COR2. Elle fait une lecture par VM
   et par source pour toutes les lignes de la passe, dans un plafond par règle et par passe (à part
   de celui de la corrélation). Au-delà du plafond : `unknown`. Une ligne de synthèse, qui en nomme
   d'autres (`_data_summary`, `glorfindel/detection_rules.py:1206` ; `auditd.fold`), n'est jamais
   corroborée : elle porte plusieurs adresses ou plusieurs commandes. L'étape prouve l'adresse **lue
   dans la ligne** (`detected_data` ou `first_result_row`), jamais `context.suspicious_ip`. Si
   `context` en nomme une autre, `_extract_suspicious_ip` la préfère, et la comparaison du point 4
   retient l'action.
2. **Le même jugement sur le chemin de `respond`.** `resolve_attack_started`
   (`glorfindel/agent.py:342`, `poll_alert` l. 430) ne passe pas par `poll_once`. Il appelle la même
   fonction. Sans elle, le verdict manque, et un manque se lit « non corroborée » (ci-dessous). **Ce
   chemin n'attend pas la preuve** (§3.6 ne vaut que pour le RulePoller) : une ligne non corroborée
   à l'instant où `poll_alert` la trouve reste une carte. L'effet sur les exercices est au §4.
3. **Toute clé `corroboration` entrante est retirée.** Un signal lu dans `runs/` (le canal des
   injecteurs, qui n'est pas de confiance), ou recopié par `resolve_attack_started` (qui renvoie
   `{**signal, …}`), peut porter une telle clé. Elle est retirée et ignorée à l'entrée, et jamais
   lue.
4. **La garde** `_apply_corroboration_guard` se place dans `decide` juste après
   `_apply_signal_guardrail` et avant `_apply_attribution_guard`. Elle est de la même nature, la
   qualité de la preuve, et passe avant le mode et l'accord des tirages : une action qu'elle retient
   ne paie pas de tirages. Elle lit seulement le verdict, dans l'état. **Le verdict est lié à sa
   cible** : il porte l'adresse et le `resource_id` qu'il prouve. La garde les compare à ce que
   l'action viserait : l'adresse que `block_suspicious_ip` bloquerait (`_extract_suspicious_ip`,
   `glorfindel/agent.py:1881`, la même lecture que `execute_action`), la VM que `isolate_vm`
   isolerait. Un écart, et l'action est retenue. Sur une action disruptive autonome dont le verdict
   n'est ni `corroborated` ni `not_required` pour cette cible, elle met `escalate = True` et
   `held_by = "corroboration"`.

   **Deux types de carte (Q8).** L'approbation en un clic se filtre par type de carte :
   `eregion_core/action_queue.APPROVABLE_TYPES` (l. 72, lu l. 606), `glorfindel/approval.py:66` et
   la liste de la console, que `tests/unit/test_action_proposal.py` garde identiques. Le statut ne
   s'y lit pas. La décision de Q8 donne donc deux types, dans `_HELD_BY_TYPE` (l. 756) :
   `corroboration_pending` (statut `pending` ou `unknown`, approuvable en un clic) et
   `uncorroborated_signal` (une source vivante a dit non, non approuvable). La carte change de type
   quand le statut change : à l'échéance de l'attente (§3.6), `pending` devient `uncorroborated`, et
   la carte passe à `uncorroborated_signal` (`escalations.record`, changement matériel). Une action
   déjà retenue par une garde plus tôt garde son type, et sa raison gagne la phrase de la
   corroboration, comme le fait la garde de télémétrie.

### 3.3 Ce qu'elle ajoute, et où

Un **verdict**, jamais une clé du signal ni une colonne de la ligne (`first_result_row`). Le
RulePoller le passe à côté du signal, avec lui dans la file du worker (`_dispatch`,
`glorfindel/cli.py:735`). Le graphe le range dans un champ de `GlorfindelState`, `corroboration`,
documenté comme `telemetry_gaps` (`glorfindel/agent.py:86`, « never shown to the model »). Ainsi :

- aucune requête, d'une règle du client ou proposée, ne peut le fournir en projetant une colonne ;
- aucun signal de `runs/` ne peut le fournir en portant une clé (§3.2, point 3) ;
- il ne touche pas l'identité de dédoublonnage de la ligne ;
- `json.dumps(signal)` ne le voit jamais.

```yaml
corroboration:
  required: true                 # la requête lit une table hors de la liste sûre
  resource_id: <id ARM de la VM du registre>
  ip: 198.51.100.23              # l'adresse prouvée (brute force) ; vide pour un fait de la VM
  status: corroborated           # corroborated | uncorroborated | pending | unknown | not_required
  source: flow_blobs             # flow_blobs | audit | none
  window: [<début UTC>, <fin UTC>]
  evidence: {connections: 3, first: <UTC>, last: <UTC>}   # borné : des nombres et des instants
  why: "aucune connexion établie de 198.51.100.23 vers le port 22 de <vm> entre 10:02 et 10:14 UTC"
```

**Un verdict absent vaut `uncorroborated`** quand l'action est disruptive : c'est l'échec fermé.
Seule l'étape écrit `not_required`, après avoir lu la requête.

Les faits que `confirm_facts` inscrit sur l'incident (B3a) restent des chaînes : `Incident.confirmed`
ne change pas de forme, et `decision_queue._floor` (`glorfindel/decision_queue.py:267`) et
`_root_compromise_floor` (`incident.get("confirmed")`, `glorfindel/agent.py:1295`) le lisent tels
quels. Un ensemble parallèle, `Incident.corroborated`, nomme ceux qui sont corroborés. Un incident
d'avant, sans cet ensemble, n'a aucun fait corroboré.

### 3.4 La fenêtre de temps

| Source | Fenêtre de la preuve | Pourquoi |
|---|---|---|
| Blobs de flux (brute force) | l'intervalle de la ligne agrégée : la période de la règle plus la marge d'ingestion (`window` de `poll_once`), élargie de `PROOF_SKEW_S` (120 s, `correlation.py:88`) de chaque côté. Une connexion dont un enregistrement tombe dans cet intervalle compte | la ligne agrégée ne date pas ses échecs (limite de COR2) ; deux horloges, celle de la VM et celle d'Azure (CR14) |
| Audit (sudo, compte, connexion) | l'instant de l'événement, lu dans `msg=audit(<s>.<ms>:<n>)` et non dans `TimeGenerated` (l'heure d'ingestion), à `SKEW_S` = 2 s de la ligne `Syslog` (`correlation.py:75`) | une seule horloge, celle de la VM (CR12) |

### 3.5 Une source en retard, en panne ou muette : une carte

L'étape ne conclut jamais sans lignes (A0). Chaque cas a son statut, et son texte sur la carte :

| Cas | Statut | Action disruptive |
|---|---|---|
| la preuve est trouvée dans la fenêtre | `corroborated` | possible (les autres gardes et le mode s'appliquent) |
| la source est vivante et ne montre rien | `uncorroborated` | carte |
| la preuve peut encore arriver, dans le délai d'attente de la source | `pending` | carte tout de suite ; l'action peut suivre (§3.6) |
| la lecture échoue (droit refusé, blob illisible, enregistrement mal formé), est coupée à sa borne, ou le plafond est atteint | `unknown` | carte |
| **la source est muette** : aucun enregistrement de flux pour l'interface de la VM depuis plusieurs minutes, quel que soit le port ou l'adresse (CR6) | `unknown` (« source muette ») | carte |
| aucune source déclarée pour cette famille | `uncorroborated` (« aucune source ») | carte |
| les adresses privées de la VM sont inconnues, ou l'une est portée par une autre VM | `unknown` | carte |
| une attribution de rôle sur le compte des flux, ou au-dessus, donne à l'identité d'une VM du registre une écriture de données ou `listKeys` (vérifié au démarrage et à chaque relecture de la configuration, CR15) | `unknown` (« compte des flux écrit depuis une VM ») | carte, pour toute ligne qui demande cette source |

Le test de vie distingue deux réponses : « la source dit non » et « la source se tait ». Une VM
exposée à Internet a des flux à toute heure. Une VM privée peut n'en avoir aucun, et voit alors
toutes ses lignes en `unknown` : une carte, à dire (CR6).

### 3.6 Attendre la preuve (Q3, retenue)

La ligne `Syslog` et l'enregistrement de flux n'arrivent pas au même moment (CR5, CR14). Proposition
retenue :

- **La carte d'abord.** La passe où la ligne arrive sans preuve envoie le signal, `pending`. La
  garde le retient, et la carte part tout de suite : « en attente de corroboration (journaux de
  flux, jusqu'à 10:45 UTC) ».
- **L'action quand la preuve arrive.** Le RulePoller garde l'entrée en attente dans son état
  (`rule_status.json`, `corroboration_pending`). **Une entrée par (VM, règle, adresse)**, bornée en
  durée (`wait_s` par source, fixé par CR5 pour les blobs et CR9 pour l'audit) et en nombre
  (`PENDING_MAX` par VM). Il la relit au plus toutes les 60 s, dans la même lecture par VM. Quand
  la preuve arrive avant l'échéance, il émet **un second signal au plus par entrée**,
  `corroborated`, qui repasse par tout le chemin : file de décision, modèle, gardes, mode, tirages.
  L'entrée est alors close.
- **Une liste d'attente pleine** : la nouvelle entrée en chasse la plus ancienne. Celle-ci garde sa
  carte, qui le dit (« attente abandonnée : liste pleine »). Rien ne part sans être dit.
- **Le second signal est de classe basse** dans la file de décision (SEC-A2), sauf s'il porte une
  compromission (COR1, critique). Sous le plafond d'appels au modèle, une détection basse retenue
  est une carte sans décision, jamais une action : le blocage attend alors son humain.
- **La file de décision ne doit pas l'avaler.** Une décision par VM, règle, gravité et source dans
  `DEDUP_WINDOW_S` (`glorfindel/decision_queue.py:49`), ouverte par la carte du premier signal,
  dédoublonnerait le second. Le signal corroboré est donc clé par (VM, règle, adresse), comme une
  compromission l'est par son adresse.
- **Un humain d'abord.** Une carte acquittée, rejetée ou approuvée par un humain avant la preuve
  **annule l'entrée** : aucun second signal. Approuvée, l'action a déjà eu lieu par l'humain ;
  rejetée, rien ne la refait seul.
- **La carte suit.** `escalations.record` tient l'arrivée de la preuve pour un changement matériel,
  comme la compromission de COR1. La carte en attente dit « corroborée à 10:21 UTC : action
  autonome exécutée ». Le second signal lit l'état (l'adresse déjà bloquée ?), jamais les cycles
  passés.
- **L'échéance passée sans preuve**, la carte reste, change de type (§3.2, point 4) et le dit :
  « aucune preuve avant 10:45 UTC ».

### 3.7 Ce qui est dit

- **Sur la carte** (raison, et le champ `corroboration` structuré pour la console et le bot), par
  exemple :
  - « Non corroborée : aucune connexion établie de 198.51.100.23 vers le port 22 de `<vm>` entre
    10:02 et 10:14 UTC (journaux de flux lus à 10:16). Une ligne Syslog peut être écrite par tout
    utilisateur de la VM : `block_suspicious_ip` retenue pour un humain. »
  - « Corroboration impossible : les journaux de flux n'ont pas été lus (<erreur>). Échec fermé. »
  - « Source muette : aucun flux de `<vm>` depuis 10 minutes. »
  - « Aucune source ne corrobore cette règle (Syslog, sudo) : une ligne Syslog seule ne fait jamais
    agir. »
- **Après une action autonome**, la notification et la ligne de debug portent la preuve : « corroborée
  par 3 connexions établies, 10:03–10:13 UTC ».
- **Compté** dans `rule_status.json` (`corroboration` : `required`, `corroborated`, `uncorroborated`,
  `pending`, `unknown`, `reads`), puis affiché dans le détail de la règle de la console et dans
  `glorfindel report` (« N actions autonomes sur Syslog, toutes corroborées »).

### 3.8 Le plancher B3a

Le plancher relève l'action à `isolate_vm` (`_root_compromise_floor`, `agent.py:1272`). Il passe
avant les gardes et reste tel quel. La garde de corroboration la retient ensuite, sauf si les
**deux** faits de l'incident sont corroborés par l'audit : la connexion réussie par
`USER_LOGIN res=success`, l'élévation comme le sudo (§3.9) : `USER_CMD`, ou l'`execve` à
uid = euid = 0 sur une image déclarée sans `USER_CMD` (Q6, retenue). Sinon la
carte propose `isolate_vm` et dit pourquoi : « Plancher déterministe (B3a) … ; faits non corroborés
hors de Syslog ». La compromission est toujours dite à un humain (COR1), corroborée ou non.

**Le plancher ne fait jamais moins que sans lui.** Cas : le modèle choisit `block_suspicious_ip`, le
blocage est corroboré par les flux, le plancher le relève à `isolate_vm`, et l'isolation est retenue
(faits non corroborés). Le choix : le blocage corroboré part seul, et la carte propose `isolate_vm`
en plus. C'est le mécanisme de `displaced` de B3a, à l'envers : l'action retenue attend son humain,
l'action prouvée ne l'attend pas. L'autre choix serait de tout retenir, et l'adresse resterait libre
pendant que la carte attend. **L'accord des tirages se juge sur l'action effectivement retenue** :
chaque tirage est relevé par le plancher (`_confirming_draws`, `glorfindel/agent.py:1565`), puis
ramené de la même façon au blocage corroboré. Sinon `_apply_agreement_guard` verrait des tirages
`isolate_vm` face à un `block_suspicious_ip` et retiendrait le blocage.

### 3.9 Lire un enregistrement d'audit strictement

Le canal A ne laisse écrire personne d'autre que root. Mais un enregistrement contient des chaînes que
l'utilisateur choisit : `comm`, les arguments d'`EXECVE`, les noms de `PATH`, `proctitle`. Le noyau
écrit une chaîne en hexadécimal dès qu'elle contient une espace, un guillemet ou un caractère de
contrôle. Une chaîne sans espace reste écrite entre guillemets : un fichier nommé `addr=203.0.113.5`
apparaît dans `name="addr=203.0.113.5"`. Le lecteur suit donc trois règles :

- le type en tête d'enregistrement (`^type=USER_AUTH msg=audit(…):`), jamais une sous-chaîne ;
- un champ lu à sa place, hors de toute valeur entre guillemets ;
- un enregistrement ambigu (deux fois le même champ, un type inattendu pour l'événement) ne
  corrobore rien.

Deux règles de plus :

- **un setuid n'est pas une élévation.** `passwd`, `chsh`, `mount` ou `su` lancés par un compte sans
  privilège donnent un `execve` à euid 0 sous son `auid`. La preuve d'un sudo est
  `USER_CMD res=success`, écrit par sudo. Sur une image dont sudo n'écrit pas `USER_CMD` (mesuré
  par image, CR8, et déclaré ; jamais décidé événement par événement, sans quoi l'absence d'un
  `USER_CMD` ouvrirait le second chemin), c'est un `execve` avec **uid = 0 et euid = 0** (sudo
  pose les deux avant de lancer la commande ; un setuid ne pose que l'euid), sous l'`auid` du compte,
  dont l'`exe` est le chemin de `COMMAND=` ;
- **la partie brute d'abord.** Avec `log_format = ENRICHED` (AUD1), auditd ajoute après le séparateur
  0x1d (ou `#035`, A7) des champs interprétés (`AUID="admin1"`, `UID="root"`). Le lecteur lit les
  champs de la partie brute, avant le séparateur. La partie enrichie ne sert qu'à nommer le compte
  sur la carte, jamais à prouver.

C'est la même discipline que le lecteur d'AUD1 (`glorfindel/auditd.py`). Les `USER_*` (`USER_AUTH`,
`USER_LOGIN`, `USER_CMD`, `ADD_USER`) sont envoyés au noyau par un programme qui tient
`CAP_AUDIT_WRITE`. Un utilisateur sans privilège ne peut pas en émettre (CR7). Le noyau y ajoute
`pid`, `uid`, `auid`, `ses`. Le texte `msg='…'` vient du programme lui-même.

### 3.10 La preuve d'une connexion, et ce qu'elle ne fait pas

- **Un flux autorisé ne prouve pas sa source.** `allow-ssh` est ouvert à `*`
  (`infra/terraform/network.tf:34-42`). Un SYN à adresse source usurpée y passe et donne un flux
  autorisé au nom de n'importe quelle adresse. La réponse de la VM part vers l'adresse usurpée, et la
  connexion ne s'établit jamais.
- **La table agrégée ne suffit pas (Q5).** Une ligne de `NTANetAnalytics` somme les flux d'une source
  vers un port de la VM sur l'intervalle de traffic analytics (10 min), sans port source :
  `BytesDestToSrc` est une somme. Des SYN usurpés reçoivent des SYN-ACK retransmis, des ACK usurpés
  reçoivent des RST : une poignée de paquets usurpés gonfle le volume. La taille moyenne des paquets
  y est au mieux un signal d'appoint (un pré-filtre), jamais la preuve.
- **La preuve, connexion par connexion (Q5, décidée : SEC-A3f).** Les blobs des VNet flow logs
  portent un enregistrement par 5-tuple (adresse et port source, adresse et port de destination,
  protocole), avec son état (début, suite, fin, refus) et les paquets et octets de chaque sens
  (CR14). Une connexion prouve l'adresse quand, pour **un même 5-tuple** de l'adresse de la ligne
  vers le port 22 de **l'une des adresses de l'une des interfaces de la VM du registre**
  (`private_ips` par interface, comme l'isolation les lit : `glorfindel/providers/azure/isolation.py:65`),
  en TCP :
  - le flux est **autorisé** (jamais un état de refus) ;
  - la VM a envoyé **plus qu'une poignée de main** : des octets et une taille moyenne de paquets
    au-delà de ce que font des SYN-ACK retransmis et des RST (~40 à 74 octets chacun) — la bannière
    et le `KEXINIT` de sshd en font des centaines ;
  - la source a envoyé **plus qu'une poignée de main** : sa bannière et son `KEXINIT`.

  Une source usurpée ne reçoit pas les numéros de séquence de la VM : elle ne fait pas répondre sshd
  par sa bannière, sur aucun 5-tuple. Les seuils (octets et taille moyenne, dans chaque sens) se
  règlent sur la mesure (CR13). Le port source écrit par sshd dans chaque ligne d'échec
  (`from <adresse> port <n>`) peut être rapproché de celui du 5-tuple : une preuve plus forte, à
  mesurer (CR13), qui demande de relire les ports des lignes (la règle livrée agrège par adresse).
- **Les flux prouvent qu'une adresse a parlé au port 22, pas qu'elle a échoué.** Une adresse vraiment
  connectée (un administrateur, un partenaire) peut être nommée dans des lignes qui ne sont pas les
  siennes. `never_block` protège les adresses déclarées. Le compte des échecs par l'audit
  (`USER_AUTH`) ferme ce cas là où le canal A existe.
- **L'audit ne tient pas contre root.** Un intrus root écrit `audit.log`. Les blobs de flux, eux,
  restent hors de sa portée **tant qu'aucune identité joignable depuis une VM surveillée n'a
  d'écriture sur leur compte** (CR15, §3.5).
- **Ce que la table agrégée lit est une autre question** (CR16) : COR2 lit `NTANetAnalytics`, que
  traffic analytics tire des mêmes blobs. Ce que traffic analytics fait d'un blob qu'il n'a pas
  écrit est à mesurer.
- **Le modèle peut toujours être trompé.** L'enquête (`investigate`, `agent.py:697-702`) lit
  `Syslog` pour le contexte du modèle. Une ligne forgée peut orienter son raisonnement. La garde ne
  lui fait pas confiance : seule l'action change de main.
- **Ce n'est pas une détection de la forgerie.** Une ligne non corroborée n'est pas une attaque
  prouvée de l'utilisateur local. C'est une détection qui demande un humain.

## 4. Ce que ça coûte

| | Avec la corroboration |
|---|---|
| **Blocage autonome d'un brute force sur une VM exposée** | quand les blobs prouvent la connexion. Les blobs sont complétés environ chaque minute (CR14) : la preuve arrive le plus souvent avant la ligne `Syslog` (P95 supposé 480 s, `expected_latency_s`), sinon quelques minutes après. La carte part toujours tout de suite (§3.6). Latence ajoutée attendue : de zéro à quelques minutes, à mesurer (CR5) |
| **Lecture des blobs** | Glorfindel lit, pour l'heure en cours, les blocs nouveaux du blob de l'interface de la VM, au plus une fois par minute et par VM qui en a besoin. Un rôle de lecture sur le **seul** compte de stockage des flux (`Storage Blob Data Reader`), une dépendance de plus (`azure-storage-blob`, `make lock` dans la même PR), un adaptateur sous `glorfindel/providers/azure/` (MC0). Coût : quelques transactions de lecture par minute et par VM, et le volume lu (des kilo-octets à quelques méga-octets par heure pour une VM exposée, CR14) — de l'ordre du centime par mois, à mesurer |
| **Sudo vers root, création de compte, commande sensible d'AUD1** | cartes jusqu'à SEC-A3e, puis autonomes possibles quand l'audit corrobore, à ±2 s, avec la latence d'un journal texte d'AMA (CR9) |
| **Plancher B3a** | carte qui propose `isolate_vm` tant que les deux faits ne sont pas corroborés par l'audit |
| **Collecte** | **rien de plus pour les flux** : les blobs sont déjà écrits au banc (rétention 7 jours). Leur coût n'est pas relevé dans `docs/operations.md` (« Coûts réels ») : à relever sur la facture (§5, geste 1). Canal d'audit : l'ingestion Analytics, 2,99 USD le Go en West Europe au-delà des 5 Go gratuits du mois (même tarif qu'AUD1). Estimation pour une VM exposée : ~5 000 tentatives SSH par jour × 2 enregistrements × ~400 octets, soit ~0,12 Go par mois, plus les `execve` des deux clés d'AUD1. Le banc reste sous 1 USD par mois, à mesurer (CR10). Le canal A remplaçant `local6` (Q7), le volume d'AUD1 dans `Syslog` disparaît |
| **Requêtes** | pour l'audit, une par VM et par passe quand une ligne en a besoin, plus les relectures en attente (au plus une par minute et par VM). Gratuites sur le niveau Analytics |
| **Appels au modèle** | aucun de plus pour la garde. Avec l'attente (SEC-A3c), une décision de plus **par adresse corroborée** (une entrée, un second signal au plus) : un appel, plus les tirages d'une action disruptive (`GLORFINDEL_DECISION_DRAWS`, 3 par défaut), dans la classe basse du plafond |
| **Le chemin `attack_started` (`respond`, exercices)** | **pas d'attente** sur ce chemin (§3.2). Comme les blobs arrivent en général avant la ligne `Syslog`, un T1110 d'exercice (BL1, Annatar depuis Orodruin) devrait être corroboré quand `poll_alert` le trouve ; s'il ne l'est pas, c'est une carte. À mesurer (CR5) avant de compter sur BL1. Un T1486 d'exercice (`Perf`) ne change pas |
| **Instantanés** | le plafond retenu (Q2) : un instantané autonome non corroboré au plus par VM et par heure, soit 24 par jour et par VM ; les suivants sont dits sur la carte. La file de décision seule ne borne pas assez le coût d'un flot de lignes forgées (lecture du code, à vérifier dans SEC-A3b) |
| **Indicateurs** | pour les techniques lues dans `Syslog`, « part contenue seule » dépend désormais des sources déclarées ; « temps pour contenir » d'un brute force dépend de CR5. C'est le prix de la décision. Le contenu seul du T1548.003 (BL1) suppose SEC-A3e |

## 5. Le protocole de mesure au banc (gestes de Jonathan)

Rien ici n'est fait par une session. Les requêtes KQL sont des lectures du workspace du banc (le
portail, « Logs »), que la session Banc peut aussi lancer si Jonathan le veut (modèle de menace,
§8). La lecture des blobs de flux est une lecture du compte de stockage du banc, avec l'identité de
Jonathan. Les gestes sur une VM se font par SSH, en lecture, sauf les lignes forgées de l'étape 3.
Les noms sont à remplacer, `<…>` ; rien de réel dans ce dépôt.

### 5.1 Les hypothèses

| | Hypothèse | Mesure | Si elle tient | Sinon |
|---|---|---|---|---|
| **CR1** | Un utilisateur sans privilège écrit une ligne `auth` étiquetée `sshd` (et `authpriv`/`sudo`, `local6`/`audisp-syslog`) qui arrive dans `Syslog` indistincte d'une vraie (`Facility`, `ProcessName`, `ProcessID` à son choix) | étape 3, requête M2 | le constat V-01 est mesuré | une colonne distingue l'émetteur : la noter, elle change le §2.3 |
| **CR2** | `_ResourceId` d'une ligne `Syslog` est posé par l'agent, jamais par la ligne. Un écrivain local n'atteint l'agent que par `/dev/log` ou par ses propres sockets | `ss -xlp`, `ss -tlnp` (les sockets de l'agent et leurs droits) ; une ligne au nom d'un autre hôte écrite sur `/dev/log`, puis M2 (`Computer`, `_ResourceId`) | rien | une ligne qui nomme une autre VM : un lot de routage, avant tout le reste |
| **CR3** | Aucun point d'entrée local de l'agent n'accepte des compteurs (`Perf`) d'un utilisateur | les mêmes `ss` | `Perf` reste dans la liste sûre | `Perf` sort de la liste sûre (Q4) |
| **CR4** | Les blobs de flux nomment l'adresse d'Internet telle quelle (pas traduite) et, en destination, l'une des adresses privées des interfaces de la VM, pour une VM à adresse publique | M1b, sur une heure | rien | lire la traduction, ou l'adresse publique de la VM |
| **CR5** | Toute fenêtre d'un vrai brute force (la règle, sur 7 jours) a au moins une connexion établie au sens de CR13 de son adresse vers le port 22 de la VM, à 120 s près ; le délai entre la fin de la fenêtre et l'arrivée de l'enregistrement dans le blob reste sous `wait_s` | M1a et M1b : la part corroborée, la distribution du délai (p50, p95, max) | `wait_s` = p95 arrondi | une part non corroborée : en comprendre la cause (port, NAT, IPv6, état des flux) avant le code |
| **CR6** | Une VM exposée a des enregistrements de flux à toute heure (test de vie) | M1b sur 24 h : les minutes sans aucun enregistrement pour l'interface | le test de vie à quelques minutes | relever sa durée, ou le faire porter sur le VNet |
| **CR7** | `/var/log/audit/audit.log` n'est écrit que par root (0600 ou 0640, `root:root` ou `root:adm`) ; un utilisateur sans privilège ne peut pas émettre d'enregistrement `USER_*` | `stat` du fichier et du répertoire ; en utilisateur sans privilège, `auditctl -m test` doit échouer (refus de l'outil ou du noyau), et rien ne doit apparaître dans `ausearch -m USER -ts recent` | le canal A tient contre un utilisateur local | le canal A n'est pas une corroboration : revoir Q1 |
| **CR8** | Sous Ubuntu, sshd et PAM écrivent `USER_AUTH`/`USER_LOGIN` avec `addr=` et `res=` ; sudo écrit `USER_CMD` ; useradd écrit `ADD_USER` | `sudo ausearch -m USER_AUTH,USER_LOGIN -ts today -i \| tail` ; `sudo ausearch -m USER_CMD -ts recent` après un `sudo -n true` ; `ADD_USER` après une création de compte de test (qui fait sa carte T1136) | la table du §2.1 tient | un type absent : la règle d'audit qui le remplace (`-w /etc/passwd`, l'`execve` de `root_command`), un lot de la session Infra |
| **CR9** | L'agent lit `audit.log` (en root seul) comme un journal texte, suit sa rotation par auditd, et l'envoie à une table personnalisée en quelques minutes ; ce qu'il faut de plus (point de collecte, version d'azurerm) | après SEC-A3d : M3, le délai entre l'instant de `msg=audit(…)` et `TimeGenerated` ; une rotation forcée (`sudo service auditd rotate`) | `wait_s` de l'audit = p95 arrondi | l'agent ne lit pas le fichier : un groupe de lecture (`log_group`), jamais un droit d'écriture |
| **CR10** | Le volume du canal A, filtré par la transformation, reste sous ~0,5 Go par mois au banc | M3 sur 24 h, puis 7 jours (`_BilledSize`) | rien | restreindre les types gardés, ou les règles d'audit |
| **CR11** | Une ligne forgée par `logger` n'apparaît pas dans la table d'audit | étape 3 refaite après SEC-A3d, M3 | le canal A tient | revoir Q1 |
| **CR12** | L'instant de `msg=audit(…)` d'un `sudo` et celui de sa ligne `Syslog` tombent à 2 s au plus l'un de l'autre | M3 et M2 pour un même `sudo -n true` | `SKEW_S` = 2 | relever la tolérance de l'audit seule |
| **CR13** | Une connexion de brute force, établie, porte dans chaque sens plus qu'une poignée de main : de la VM vers la source, des octets et une taille moyenne de paquets nettement au-dessus de SYN-ACK et de RST (~40 à 74 octets) ; de la source vers la VM, sa bannière. Une sonde qui ne fait que le SYN (un scanner de ports) reste en dessous. Le port source du 5-tuple est celui que sshd écrit dans la ligne | M1b : par 5-tuple, la distribution des octets et de la taille moyenne dans chaque sens, pour les adresses des fenêtres de M1a et pour les sondes sans échec dans `Syslog` ; le rapprochement des ports sur quelques fenêtres | les seuils, réglés entre les deux distributions | les distributions se chevauchent : la preuve repose sur le rapprochement des ports, ou sur `USER_AUTH` là où le canal d'audit existe |
| **CR14** | Les blobs des VNet flow logs : un blob par heure et par ressource, complété environ chaque minute ; chaque enregistrement porte l'instant, le 5-tuple, la direction, l'état (début, suite, fin, refus) et les paquets et octets de chaque sens ; l'identité d'Imladris (anciennement H0) peut les lire avec `Storage Blob Data Reader` sur le seul compte | M1b ; l'heure de dernière modification des blobs ; une lecture avec un rôle de lecture seul | rien | corriger le lecteur (version du format, champs) ; un délai plus long relève `wait_s` |
| **CR15** | Aucune identité joignable depuis une VM surveillée ne peut écrire dans le compte des flux : ni l'identité managée de la VM (par IMDS), ni une clé ou un SAS posés sur la VM ; aucune attribution, sur le compte ou héritée au-dessus (groupe de ressources, abonnement), d'un rôle de données en écriture ou d'un rôle de gestion qui porte `listKeys` ; `allowSharedKeyAccess` désactivé sur le compte | les attributions de rôle du compte et de ses portées parentes (lecture, `Reader`) ; la propriété `allowSharedKeyAccess` ; depuis une VM, avec son identité managée, une écriture d'essai refusée (403) dans le conteneur des flux | le compte des flux est une preuve | le compte n'est pas une preuve : SEC-A3f ne sort pas tant que ce n'est pas réglé. **Au banc, INF-FL (#654)** sépare le compte des flux de celui des exercices. `infra/terraform/tests/flow_logs.tftest.hcl` tient la propriété au plan : le flow log vise le compte des flux et plus celui des exercices ; aucune attribution d'une identité de VM ne porte sur lui ni au-dessus ; `shared_access_key_enabled = false`. `tests/unit/test_bench_flow_logs.py` lit, en plus, chaque attribution du module donnée à une VM. Les gestes et la vérification en lecture sont dans `docs/operations.md`, « Le compte des flux réseau (INF-FL) ». **Appliqué et mesuré au banc le 12/11 : CR15 tient.** Aucune des 15 attributions lues sur le compte et au-dessus ne porte une identité de VM ni du groupe ; `allowSharedKeyAccess` et `allowBlobPublicAccess` valent false ; l'écriture d'essai depuis gondolin est refusée (HTTP 403 `AuthorizationPermissionMismatch`). CF1 (Network Watcher écrit sans clé) et CF2 (traffic analytics lit sans clé) tiennent ; une perte unique, d'environ 46 s de flux, à la bascule (`docs/operations.md`, « Ce qui reste ouvert ») |
| **CR16** | Traffic analytics ne tire `NTANetAnalytics` que des blobs écrits par Network Watcher dans le conteneur des flux | Microsoft Learn ; au banc, après le lot Infra à part, rien à mesurer si CR15 tient (aucune autre identité n'y écrit) | rien | à dire dans `correlation.md` (COR2, `origin_proof: flows`) et dans le modèle de menace, par la session Glorfindel |

### 5.2 Les étapes

0. **L'état.** `auditd_enabled` est-il posé (`terraform.tfvars`) ? Les blobs de flux sont-ils écrits
   pour les VM du banc (le conteneur du compte de stockage) ? Pendant les étapes 3 et 4, la VM visée
   passe en `human_only` dans la console, pour qu'aucune action ne parte pendant la mesure.
1. **Le coût des flux** : relever sur la facture du mois les postes Network Watcher (flow logs),
   stockage des blobs et traffic analytics. Les écrire dans `docs/operations.md`, « Coûts réels »,
   par le lot SEC-A3f.
2. **Le vrai brute force, sans attaque** : M1a sur 7 jours, puis M1b sur les mêmes heures (CR4, CR5,
   CR6, CR13, CR14). C'est la preuve qu'un vrai brute force est corroboré : chaque fenêtre de la
   règle trouve une connexion établie de son adresse.
3. **La ligne forgée** : dix lignes de la forme d'un échec de sshd, écrites sous son étiquette par un
   compte sans privilège (le compte d'administration sans `sudo` suffit), avec une adresse de
   documentation (RFC 5737). Puis une ligne de la forme de sudo sous l'étiquette de sudo, et une ligne
   sous l'étiquette d'`audisp-syslog`. Les commandes sont données à Jonathan hors du dépôt. Ensuite :
   - M2 : les trois lignes sont dans `Syslog`, indistinctes (CR1) ;
   - M1b restreinte à cette adresse : **aucune connexion**. La ligne n'est pas corroborée ;
   - sur la VM : `ausearch -m USER_AUTH,USER_LOGIN -ts recent` ne montre **rien** pour cette adresse,
     et `ausearch -m USER_CMD` rien pour cette commande (CR8).
4. **auditd sur la VM**, en lecture : CR7, CR8, les `ss` de CR2 et CR3.
5. **Après SEC-A3d** (le canal A appliqué par Jonathan) : M3 (CR9, CR10, CR12), et l'étape 3 refaite
   (CR11).
6. **Après SEC-A3b, c, f et e sur Imladris** : la VM exposée revient en `non_disruptive`.
   - Un vrai brute force d'Internet donne une carte « en attente », ou directement un blocage
     autonome si la preuve est déjà là. Sa notification dit « corroborée par N connexions établies ».
   - L'étape 3 donne une carte « non corroborée » : rien n'est bloqué.
   - Un `sudo -i` d'un administrateur, s'il n'est pas attendu (ADM1), est corroboré par l'audit.
   - `glorfindel report` compte les cas.

### 5.3 Ce qui prouverait que la corroboration tient

| Cas | Attendu |
|---|---|
| Ligne `sshd` forgée, adresse qui ne se connecte jamais | `uncorroborated` : carte, aucun blocage, en `non_disruptive` |
| Vrai brute force d'Internet sur la VM exposée | `corroborated` (pour ≥ 95 % des fenêtres de M1a, avec une connexion établie au sens de CR13 ; tolérance à fixer avec Jonathan) ; blocage autonome dans `wait_s` |
| Sonde SYN seule (un scanner de ports), ou SYN à source usurpée | aucune connexion établie : `uncorroborated` |
| Ligne `sudo` forgée | `uncorroborated` : carte, aucune isolation |
| Ligne `audisp-syslog` forgée | absente de la table d'audit (CR11) ; carte sans action |
| Vrai `sudo -i` | `corroborated` par `USER_CMD` ou par l'`execve` à uid = euid = 0, à ±2 s |
| Source coupée (vérifié par les tests, sur de faux blobs et de faux journaux : lecture refusée, blob mal formé, plafond, aucun enregistrement) | `unknown` : carte, jamais une action |

### 5.4 Les requêtes et les lectures (principe)

**M1a, les fenêtres d'un brute force** (KQL, `Syslog` seul) :

```kusto
Syslog
| where TimeGenerated > ago(7d)
| where Facility == "auth" and ProcessName in ("sshd", "sshd-session")
| where SyslogMessage has "Failed password" or SyslogMessage has "Invalid user"
| where _ResourceId =~ "<id de ressource de la VM>"
| extend SourceIP = extract(@"from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) port \d+( ssh2)?( \[preauth\])?\]?\s*$", 1, SyslogMessage),
         SourcePort = toint(extract(@"port (\d+)( ssh2)?( \[preauth\])?\]?\s*$", 1, SyslogMessage))
| where isnotempty(SourceIP)
// Comme la règle : au moins 10 échecs d'une adresse dans une fenêtre de 10 minutes (des fenêtres
// fixes ici, glissantes dans la règle : une approximation).
| summarize Failed = count(), Ports = make_set(SourcePort, 100), Ingested = max(ingestion_time())
    by SourceIP, WinStart = bin(TimeGenerated, 10m)
| where Failed >= 10
| extend WinEnd = WinStart + 10m
| order by WinStart asc
```

**M1b, les connexions dans les blobs de flux** : télécharger, avec l'identité de Jonathan et un rôle
de lecture, les blobs horaires de la VM pour les heures de M1a (le conteneur des VNet flow logs du
compte de stockage du banc). Chaque blob est un document JSON ; les enregistrements par 5-tuple
sont des chaînes séparées par des virgules, sous `records[].flowRecords.flows[].flowGroups[]
.flowTuples[]` (CR14 : la forme exacte est à lire). Pour chaque fenêtre de M1a, relever :

- les 5-tuples de son adresse vers le port 22 de l'une des adresses privées des interfaces de la
  VM, autorisés, dans la fenêtre à ±120 s ;
- pour chacun, les paquets et octets de chaque sens, et la taille moyenne des paquets de la VM vers
  la source (CR13) ; si son port source est dans `Ports` de M1a ;
- le délai entre `WinEnd` et l'heure de dernière modification du blob qui porte le premier
  enregistrement (CR5) ;
- et, pour l'autre côté des seuils, les mêmes chiffres pour des adresses qui sondent le port 22
  sans aucun échec dans `Syslog`.

Le lot SEC-A3f livre le lecteur (`glorfindel/providers/azure/`) ; une commande de lecture seule qui
l'appelle sur un blob téléchargé sert alors à refaire M1b. **Le lecteur prend le compte par son id
de ressource**, jamais par son nom seul : la sortie `flow_logs_storage_account_id` de Celebrimbor
(INF-FL), ou le `storageId` du flow log lu sur Azure. Le nom d'un compte de stockage est global, et
celui du banc est écrit dans un dépôt public : n'importe qui peut créer un compte de ce nom, ailleurs,
si celui du banc disparaît. Un lecteur qui le prendrait par son nom lirait des flux que n'importe qui
écrit.

**M2, les lignes forgées telles qu'elles arrivent** :

```kusto
Syslog
| where TimeGenerated > ago(1h)
| where _ResourceId =~ "<id de ressource de la VM>"
| where SyslogMessage has "<198.51.100.x>" or SyslogMessage has "<compte>" or ProcessName == "audisp-syslog"
| project TimeGenerated, Computer, _ResourceId, Facility, SeverityLevel, ProcessName, ProcessID, HostIP, SyslogMessage
```

**M3, le canal d'audit** (après SEC-A3d ; table et colonnes à confirmer, CR9) :

```kusto
EregionAudit_CL
| where TimeGenerated > ago(1d)
| where _ResourceId =~ "<id de ressource de la VM>"
| extend Type = extract(@"^type=(\w+) msg=audit\(", 1, RawData),
         EventAt = unixtime_milliseconds_todatetime(todouble(extract(@"^type=\w+ msg=audit\((\d+\.\d+):", 1, RawData)) * 1000)
| summarize Lines = count(), Bytes = sum(_BilledSize), DelayP95 = percentile(TimeGenerated - EventAt, 95) by Type
```

## 6. Questions pour Jonathan, et ses décisions

### 6.1 Les décisions de Jonathan (09/11)

| | Question | Décision |
|---|---|---|
| Q1 | Le canal d'auditd | **le journal texte d'AMA** : `/var/log/audit/audit.log` vers une table à lui (option recommandée) |
| Q2 | L'instantané | **autonome sans corroboration, plafonné** : un non corroboré au plus par VM et par heure, 24 par jour et par VM (option recommandée) |
| Q3 | Le moment | **la carte d'abord, l'action à la preuve**, dans un délai borné par source (option recommandée) |
| Q4 | Quelles lignes | **la liste blanche par la forme de la requête** (option recommandée) |
| Q5 | La preuve d'un brute force | **la preuve stricte, connexion par connexion : les enregistrements par 5-tuple des blobs de flux (SEC-A3f)**. Ce n'était pas l'option recommandée (la taille moyenne des paquets dans `NTANetAnalytics`) |
| Q6 | Le plancher B3a | **les deux faits prouvés par l'audit** (option recommandée) |
| Q7 | Les règles d'AUD1 et de VM3 | **elles lisent la table d'audit** (option recommandée) |
| Q8 | L'approbation en un clic | **un clic pour `pending` et `unknown` seulement**, deux types de carte (option recommandée) |

### 6.2 Les questions, pour la trace

Telles qu'elles ont été posées, l'option recommandée en premier.

1. **Le canal d'auditd.** Celui d'AUD1 (`audisp-syslog` vers `Syslog`) est forgeable : il ne
   corrobore rien.
   - **(recommandé) A. Le journal texte d'AMA** : `/var/log/audit/audit.log` vers une table à lui, par
     un drapeau de Celebrimbor désactivé par défaut (SEC-A3d). Le fichier n'est écrit que par root.
   - B. Defender for Endpoint, pour un client qui l'a. Une licence, et rien au banc.
   - C. Pas d'audit : seuls les flux corroborent. Le sudo, la création de compte et B3a restent des
     cartes pour toujours.
2. **L'instantané.** Il est autonome et ne contient rien.
   - **(recommandé) Il reste autonome sans corroboration, plafonné.** Il ne change rien de joignable
     et garde la preuve. Une détection caractérisée garde sa carte (SEC4a). Un instantané non
     corroboré au plus par VM et par heure, soit 24 par jour.
   - Lui aussi exige la corroboration, et devient une carte sans elle.
3. **Le moment.**
   - **(recommandé) La carte d'abord, l'action quand la preuve arrive**, dans un délai borné par
     source (§3.6).
   - Retenir la détection jusqu'à la preuve : la carte arrive plus tard.
   - Ne jamais attendre : une ligne non corroborée à la passe reste une carte, et l'action ne suit pas.
4. **Quelles lignes demandent une corroboration.**
   - **(recommandé) Une liste blanche, par la forme de la requête** (§3.1). Une requête est exemptée
     seulement si chaque identifiant qui ouvre une expression tabulaire, où qu'il soit (tête,
     `let`, `join`, `lookup`, `union`, `in (…)`, `toscalar(…)`…), est dans une liste fermée (`Perf`,
     `StorageBlobLogs`, `NTANetAnalytics`, la table d'audit) ou un `let` sûr, et si chaque
     opérateur et chaque fonction appartient à une liste fermée reconnue (`search`, `table(`,
     `externaldata`, `mv-apply`, `fork`, une fonction enregistrée… n'y sont pas). Tout le reste
     demande une preuve : `Syslog`, une table inconnue, une règle du client ou une règle proposée.
     Le jugement est statique, avant toute requête.
   - Seules les règles livrées qui lisent `Syslog`. Une règle du client sur une table inconnue
     agirait alors sans preuve.
5. **La force de la preuve d'un brute force.**
   - **(recommandé) Un flux établi au moins, lu dans `NTANetAnalytics`** : un flux TCP autorisé de
     l'adresse vers le port 22 de la VM, dans la fenêtre, dont les paquets de la VM vers l'adresse
     ont une taille moyenne au-dessus d'un seuil, avec un volume minimal. Plus, là où le canal
     d'audit existe, des `USER_AUTH` en échec de cette adresse. — *non retenue (§3.10)*
   - Un flux autorisé, quels que soient ses octets, ou un volume seul (plus d'~1 Ko). Une poignée de
     SYN ou d'ACK usurpés corroborerait n'importe quelle adresse.
   - **La preuve stricte, connexion par connexion : les enregistrements par 5-tuple des blobs de
     flux (SEC-A3f).** Une lecture de plus (un rôle, une dépendance), une latence plus courte.
     *Retenue.*
   - Les `USER_AUTH` seuls. Ils attendent le canal d'audit : d'ici là, aucun blocage autonome.
   - Un nombre de flux cohérent avec le nombre d'échecs (au moins ⌈échecs / `MaxAuthTries`⌉). Cela
     dépend d'une colonne de comptage des flux à mesurer, et sshd peut être réglé autrement.
6. **Le plancher B3a.**
   - **(recommandé) Autonome seulement quand les deux faits sont corroborés par l'audit** : la
     connexion par `USER_LOGIN res=success`, l'élévation par l'`execve` en root. Sinon la carte
     propose `isolate_vm`.
   - Les flux suffisent pour la connexion. Mais ils ne distinguent pas un échec d'un succès.
7. **Les règles d'AUD1 et de VM3.**
   - **(recommandé) Elles lisent la table d'audit**, une fois CR9 à CR11 mesurés. Leur ligne n'a plus
     besoin de corroboration, et la facilité `local6` sort de la DCR (moins de volume).
   - Elles gardent `Syslog` et se font corroborer par la table, enregistrement par enregistrement :
     deux collectes du même fait.
8. **L'approbation en un clic d'une carte non corroborée.**
   - **(recommandé) En un clic pour `pending` et `unknown` seulement.** La preuve n'est pas encore
     là, ou n'a pas pu être lue : l'humain juge sur le reste. Pour `uncorroborated`, une source
     vivante a dit non : la carte propose l'action, mais l'approuver demande le geste explicite des
     cartes non approuvables (comme une compromission), avec la raison sous les yeux. Comme
     l'approbation se filtre par type, cela fait deux types, `corroboration_pending` (approuvable)
     et `uncorroborated_signal` (non approuvable), et une bascule de l'un à l'autre à l'échéance
     (§3.2, point 4).
   - En un clic dans tous les cas, comme `telemetry_gap`.
   - Jamais en un clic.

## 7. La suite en lots

Mutants réservés : **M4530–M4539 et M4579–M4587**, répartis ci-dessous. L'ordre :

1. les étapes 0 à 4 du §5 ;
2. SEC-A3a, indépendant ;
3. le lot Infra, à part : le compte des flux séparé de celui des exfiltrations (CR15). **SEC-A3f ne
   sort pas tant que le compte est partagé** ;
4. **SEC-A3b, SEC-A3c et SEC-A3f, dans la même version** : sans SEC-A3f, aucune source ne prouve un
   brute force, et il devient une carte ; sans SEC-A3c, une preuve arrivée après la ligne ne fait
   jamais agir ;
5. SEC-A3d, puis l'étape 5 ;
6. SEC-A3e ;
7. l'étape 6.

Chaque lot met à jour les **deux** lignes « S » du §4 du modèle de menace pour ce qu'il ferme :
celle de l'injection (« les règles ancrées filtrent sur l'étiquette que l'émetteur déclare ») et
celle de la corrélation (« l'étiquette `sshd` ne prouve pas l'émetteur »), ainsi que son point
« Ouvert ». SEC-A3b y rend, règle par règle, ce qui peut agir seul et sur quelle preuve. #632 se
ferme quand V-01 y passe dans « ce qui tient ».

| Lot | Session | Ce qu'il fait | Fini quand | Mutants |
|---|---|---|---|---|
| **SEC-A3a** — les bornes de la corrélation (commentaire de SEC-D sur #632) | Glorfindel | Borne à 64 caractères le service et le compte que la raison de `SessionOrigin` recopie, comme le sont ceux de `SuccessfulLogins`. Écrit pourquoi une ligne `session opened … by` est lue sous toute étiquette : elle ne peut qu'ajouter une carte (« compte pris par … »), jamais en retirer une, donc l'échec est fermé. | Tests : un service de 10 000 caractères est borné sur la raison ; une ligne de session forgée sous une étiquette étrangère fait une carte et n'écarte jamais un shell root. `correlation.md` dit le pourquoi. La ligne « S » du modèle de menace dit les bornes tenues. | M4530 (borne retirée) |
| **SEC-A3b** — le cœur | Glorfindel | `glorfindel/corroboration.py` : la liste blanche par la forme de la requête (§3.1, Q4), l'étape dans `poll_once` et sur le chemin de `respond`, le verdict lié à son adresse et à sa VM et rangé dans `GlorfindelState` (§3.3), la clé entrante retirée, l'interface d'une source de preuve (que SEC-A3f et SEC-A3e remplissent). Puis `_apply_corroboration_guard`, les types `corroboration_pending` et `uncorroborated_signal` (dans `_HELD_BY_TYPE` ; le premier seul dans `eregion_core/action_queue.APPROVABLE_TYPES` et la liste de la console, Q8), `Incident.corroborated`, le plancher B3a qui ne fait jamais moins (§3.8), le plafond d'instantanés (Q2), la clé `corroboration` de `glorfindel-config.yaml` (sources déclarées, lue strictement), les compteurs, la console, `report`. **Le geste de déploiement sur Imladris**, écrit dans `docs/operations.md` : déclarer la source de flux (et le rôle de lecture de SEC-A3f) dans le `glorfindel-config.yaml` d'Imladris avant la version qui porte ces lots (sans source déclarée, une détection de ces tables est une carte : §3.1, « Aucune dérogation »). | Tests sur une fausse source, en `non_disruptive`. **Le message utilisateur de `_build_user_message` est identique à l'octet avec et sans verdict.** Une ligne `sshd` sans preuve donne une carte, aucun blocage ; avec une preuve, `block_suspicious_ip` est autonome comme avant. Un verdict pour une autre adresse ou une autre VM que la cible est retenu. `Perf` et `StorageBlobLogs` ne changent pas ; `ransomware-disk-write` est exempté ; une requête qui joint `Syslog`, lit `Syslog` dans une sous-requête (`Perf | where Computer in (Syslog | …)`, `toscalar(…)`), nomme une table inconnue, une fonction, `search`, `externaldata` ou `mv-apply` ne l'est pas. Un verdict absent, une source en échec, coupée, au plafond, muette, une ligne de synthèse donnent une carte. Sur `respond`, même jugement. Une colonne ou une clé `corroboration` venue d'une règle ou de `runs/` est sans effet. B3a sans audit : le blocage corroboré part, la carte propose `isolate_vm`, et l'accord des tirages ne retient pas le blocage. Une carte `uncorroborated_signal` refuse l'approbation en un clic (`approval.py`, `action_queue.verbs`, la console) ; une carte `corroboration_pending` l'accepte. Docs à jour : `glorfindel.md`, `correlation.md`, `operations.md`, le modèle de menace (la carte, règle par règle, de ce qui peut agir seul). `changes/SEC-A3b.md`. | M4531 (garde retirée), M4532 (verdict absent lu comme corroboré), M4533 (source en échec lue comme corroborée), M4579 (verdict laissé dans le signal donné au modèle), M4580 (exemption par simple mention d'une table sûre ; le cas `in (Syslog | …)` le tue aussi), M4581 (verdict non comparé à l'adresse et à la VM visées), M4582 (clé `corroboration` entrante non retirée) |
| **SEC-A3c** — attendre la preuve (Q3) | Glorfindel | L'état `pending` borné (nombre, `wait_s` par source), la relecture au plus par minute, le second signal clé par (VM, règle, adresse) dans la file de décision, la carte mise à jour et son type changé à l'échéance. L'état survit à un redémarrage de la watch. | Tests. Une preuve qui arrive dans `wait_s` donne une action autonome et une carte mise à jour. Une preuve qui arrive après donne une carte « aucune preuve avant … », de type `uncorroborated_signal`, et aucune action. **Une carte acquittée, rejetée ou approuvée par un humain avant la preuve annule l'action en attente.** Une entrée par (VM, règle, adresse), un second signal au plus par entrée, de classe basse ; il n'est pas dédoublonné par SEC-A2. Une liste d'attente pleine chasse l'entrée la plus ancienne, et sa carte le dit. Après un redémarrage, rien n'est perdu ni rejoué en double. | M4535 (attente non bornée), M4536 (second signal dédoublonné) |
| **SEC-A3f** — la preuve d'une connexion par les blobs de flux (Q5) | Glorfindel, Infra | **Prérequis** : le lot Infra, à part, qui sépare le compte des flux (un compte dédié, ou le rôle des VM restreint au conteneur `exfil-target`), avec un `terraform test` « aucune identité de VM n'a de rôle sur le compte des flux » (CR15). Glorfindel : un lecteur des blobs horaires de toutes les interfaces de la VM, de préférence sur le lecteur de blobs existant (`eregion_core/exercise_channel.py` : REST, identité managée, sans clé partagée, ses bornes SEC5, SEC17, V-21, SEC14), sinon un adaptateur `glorfindel/providers/azure/flow_blobs.py` qui garde les mêmes bornes (et, s'il prend `azure-storage-blob`, ce SDK seulement là, MC0, la dépendance ajoutée à `pyproject.toml` et `make lock` dans la même PR). Il lit les blocs nouveaux, borné en octets et en enregistrements, avec un lecteur strict des 5-tuples (la version du format vérifiée ; un enregistrement mal formé, une version inconnue : `unknown`). Le critère de §3.10 : même 5-tuple, adresse de la ligne vers le port 22 de l'une des adresses de l'une des interfaces de la VM du registre, autorisé, plus qu'une poignée de main dans chaque sens (seuils de CR13) ; le rapprochement des ports si CR13 le retient. Le test de vie (CR6). **Au démarrage et à chaque relecture de la configuration**, la source est refusée (`unknown`, une carte) si une attribution sur le compte déclaré, ou au-dessus, nomme l'identité d'une VM du registre avec une écriture de données ou `listKeys` (le rôle `Reader` suffit à lire les attributions). Infra : le rôle `Storage Blob Data Reader` de l'identité d'Imladris sur le seul compte des flux (désactivé par défaut, CI4 si un fournisseur change). `docs/operations.md` : les gestes, le coût (§5, geste 1), le retour en arrière. | Le lot Infra à part est fusionné et appliqué, CR15 mesurée. Tests sur de faux blobs. Un SYN seul, des SYN-ACK retransmis, des RST en nombre sur un 5-tuple (une source usurpée) ne prouvent rien. Une connexion établie de l'adresse prouve, vers n'importe quelle adresse de n'importe quelle interface de la VM du registre. Un 5-tuple refusé, vers un autre port, vers l'adresse d'une autre VM ou depuis une autre adresse ne prouve rien ; une ligne dont `Computer` ou `HostIP` nomme une autre VM que celle du registre : seul le 5-tuple vers les adresses du registre compte. Un blob illisible, trop grand, d'une version inconnue, une lecture refusée (403) : `unknown`, une carte. Aucun blob récent : source muette. Une attribution d'écriture de données ou de `listKeys` à l'identité d'une VM du registre, sur le compte ou au-dessus : la source refusée, une carte. Le lecteur ne lit que le compte déclaré. | M4534 (adresse de la VM lue dans la ligne, `Computer` ou `HostIP`, au lieu des adresses du registre), M4583 (seuil par connexion retiré : une poignée de main prouve), M4586 (un 5-tuple refusé, ou vers un autre port, compté), M4587 (vérification des écrivains du compte retirée) |
| **SEC-A3d** — le canal d'audit au banc (Q1) | Infra | Derrière un drapeau désactivé (`audit_channel_enabled`) : la DCR d'un journal texte sur `/var/log/audit/audit.log`, la table `EregionAudit_CL` et sa transformation (les types gardés), les règles d'audit qui manquent (`identity`). Le contrat est testé sans Azure (`terraform test`, `tests/unit/test_bench_auditd.py`). Les gestes et le retour en arrière vont dans `docs/operations.md`. Un fournisseur Terraform nouveau, s'il en faut un (azapi), suit CI4 : `make providers-lock`, une PR, le plan de Jonathan. | Le plan contre un faux azurerm montre l'ajout, et rien quand le drapeau est faux. Le contrat entre le script, la DCR et le lecteur est le même dans les trois. Le chemin `audit.log` et ses droits sont écrits. Jonathan applique ; l'étape 5 du §5 est faite. | — (Terraform : le contrat de `terraform test`) |
| **SEC-A3e** — l'audit corrobore | Glorfindel | La source `audit` : la lecture stricte des enregistrements (§3.9), le sudo (`USER_CMD`, ou l'`execve` à uid = euid = 0 sur une image déclarée sans `USER_CMD`), la création de compte (`identity` ou `ADD_USER`), la connexion de B3a (`USER_LOGIN`), les `USER_AUTH` du brute force. Puis les règles d'AUD1 et de VM3 qui lisent la table (Q7). | Tests sur de faux enregistrements. Un sudo forgé donne une carte ; un vrai sudo, une isolation possible. **Un setuid (`passwd`, `chsh`) lancé par un compte sans privilège ne corrobore rien.** Un fichier nommé `addr=…`, un `comm` choisi, un argument qui imite un champ, ou un champ lu seulement dans la partie enrichie (après 0x1d) ne corroborent rien. Un compte différent ou un instant à plus de 2 s ne corroborent rien. B3a est autonome seulement avec les deux faits corroborés. Les règles d'AUD1 donnent les mêmes cartes depuis la table. Docs et modèle de menace à jour (les deux lignes « S ») : V-01 passe dans « ce qui tient ». | M4537 (sous-chaîne au lieu du champ), M4538 (compte non comparé), M4539 (tolérance de 2 s retirée), M4584 (uid réel non comparé : un setuid corrobore), M4585 (champ lu dans la partie enrichie) |

## 8. Sources

- La forme des enregistrements d'audit, `CAP_AUDIT_WRITE`, l'encodage hexadécimal des chaînes non
  sûres : `auditd(8)`, `auditctl(8)`, `ausearch(8)`, `audit.rules(7)`, et le format des
  enregistrements du projet Linux Audit. `USER_AUTH`, `USER_LOGIN` (sshd et PAM), `USER_CMD` (sudo),
  `ADD_USER` (shadow-utils) : la documentation de chaque programme. Hypothèses CR7, CR8, CR12.
- Les VNet flow logs (le format des blobs, les enregistrements par 5-tuple), traffic analytics et le
  schéma de `NTANetAnalytics` : Microsoft Learn (Network Watcher). Hypothèses F1–F4, CR4–CR6, CR13,
  CR14.
- Les journaux texte de l'agent Azure Monitor, les tables personnalisées et les transformations de
  DCR : Microsoft Learn (Azure Monitor). Hypothèses CR9, CR10.
- Les benchmarks CIS pour Linux, les règles d'audit `identity` et `user_emulation` : déjà cités par
  AUD1 (`correlation.md`, « Ce que ferme AUD1 »).
