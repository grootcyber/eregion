# La corroboration avant toute action autonome (SEC-A3, #632) — conception

> **Statut : conception, 09/11.** Rien n'est codé. Ce document prépare les lots SEC-A3a à SEC-A3e
> (§7). Les huit questions du §6 attendent Jonathan, une à la fois. Les mesures du §5 sont ses
> gestes, au banc, avant le code : décision du 09/11, « mesurer au banc quelles sources sont
> disponibles avant d'écrire le code ».
>
> **La décision de Jonathan (09/11, issue #632).** Une action autonome exige une corroboration par
> une source qu'un utilisateur local ne peut pas écrire : un enregistrement auditd du noyau pour ce
> qui se passe sur la VM, un flux réseau pour une adresse distante. Sans corroboration, la détection
> reste vue. Elle devient une carte pour un humain, jamais une action.
>
> **Lié** : [`correlation.md`](correlation.md) (COR1, COR2, AUD1, B3a), le modèle de menace
> ([`modele-de-menace.md`](modele-de-menace.md), §4, ligne « S »), [`docs/glorfindel.md`](../glorfindel.md)
> (les gardes de `decide`), [`docs/operations.md`](../operations.md) (F1–F4, A1–A13, les coûts).
>
> **Règle de lecture.** Ce qui est lu dans le dépôt est une affirmation, avec son fichier et sa ligne
> (au commit `eef16bc7`). Ce qui est dit de Linux (auditd, PAM, sshd, sudo), de l'agent Azure Monitor
> et des journaux de flux vient de leur documentation publique : c'est une **hypothèse**, numérotée
> CR1 à CR13 (§5), à mesurer au banc. Ces numéros ne se confondent ni avec A1–A13 d'AUD1, ni avec
> B1–B5 et F1–F4 de COR2 (`docs/operations.md`), qu'ils réutilisent quand ils le peuvent.

## 0. En bref

- **Le constat (V-01).** Les règles livrées lisent `Syslog` et prennent l'étiquette d'une ligne
  (`ProcessName`) pour la preuve de son émetteur. Tout utilisateur local d'une VM écrit dans
  `Syslog` sous l'étiquette qu'il choisit. Quatre de ces règles peuvent faire agir Glorfindel seul,
  en `non_disruptive` : le brute force SSH (bloquer une adresse), le sudo vers root (isoler la VM),
  et, si le modèle est assez sûr de lui, la création de compte et la commande sensible d'AUD1. Le
  plancher B3a s'y ajoute : un brute force réussi, puis root, donne `isolate_vm`.
- **Le point dur.** Le chemin d'auditd posé par AUD1 n'est pas une corroboration. Ses lignes arrivent
  dans `Syslog`, par `audisp-syslog`, sur la facilité `local6`. Une ligne écrite par `logger` sous
  cette étiquette y arrive aussi. AUD1 le dit lui-même (`infra/terraform/auditd.tf:17-23`).
  « Un enregistrement du noyau » ne tient que par un canal que l'utilisateur local ne peut pas
  écrire : le fichier `/var/log/audit/audit.log`, que seul root écrit, lu par l'agent comme un
  journal texte, vers une table à lui. C'est une collecte nouvelle (Q1).
- **Ce qui est déjà là.** Les journaux de flux du VNet du banc, avec traffic analytics à 10 minutes,
  arrivent dans le workspace (`NTANetAnalytics`, `infra/terraform/monitoring.tf:109-131`). COR2 sait
  déjà les lire (`glorfindel/correlation.py:105`). Ils corroborent le brute force, et rien d'autre
  aujourd'hui.
- **Le mécanisme.** Le code juge, jamais le modèle. Une étape du RulePoller cherche la preuve, hors du
  verrou, comme COR1, COR2 et AUD1. Son verdict voyage à côté du signal, jamais dedans : il arrive
  dans l'état du graphe (`GlorfindelState`), comme `telemetry_gaps`, et n'atteint jamais le prompt.
  Une garde de `decide` retient toute action disruptive dont le verdict n'est pas « corroborée » pour
  l'adresse et la VM qu'elle viserait. Un verdict absent, une source en panne, en retard ou muette :
  une carte (A0).
- **Le prix.** Le blocage autonome d'un brute force continue, mais 10 à 20 minutes plus tard
  (traffic analytics écrit par lots), avec une carte tout de suite (Q3). Le sudo vers root, la
  création de compte et la commande sensible d'AUD1 deviennent des cartes, jusqu'au canal d'audit
  (SEC-A3d, SEC-A3e). Le coût de
  collecte reste faible : les flux sont déjà payés, et le canal d'audit est estimé sous 1 USD par
  mois au banc (CR10).

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

### 1.2 Ce qui peut faire agir seul

Une action est autonome quand elle passe toutes les gardes de `decide` (`docs/glorfindel.md`, « Gates
extraits en helpers ») et que la VM est en `non_disruptive` (`human_only` par défaut). Les actions
disruptives sont `isolate_vm` et `block_suspicious_ip` (`_DISRUPTIVE_AUTONOMOUS`,
`glorfindel/agent.py:745`, qui nomme aussi `revoke_temp_access`, retirée des actions autonomes et
jamais exécutable). Le garde-fou du signal non caractérisé (`_apply_signal_guardrail`,
`glorfindel/agent.py:1150`) les retient déjà sur une ligne qui ne porte aucun indicateur curé
(`RECOGNIZED_INDICATOR_KEYS`, `glorfindel/detection_rules.py:185`). Une ligne caractérisée passe
cette garde, et c'est alors le modèle, sa confiance et l'accord de ses tirages qui décident. Un
instantané (`snapshot`) n'est pas disruptif : le garde-fou du signal non caractérisé ne le retient
pas (le mode `human_only` et la porte de confiance, si).

## 2. Règle par règle

### 2.1 La table

« Forgeable » : un utilisateur local, sans privilège, peut faire naître la ligne qui déclenche la
règle. « Disruptif seul » : une action disruptive peut partir sans humain aujourd'hui, en
`non_disruptive`.

| Règle livrée (`detection_rules.yaml`) | Table lue | Forgeable | Disruptif seul | Corroboration non forgeable | Au banc |
|---|---|---|---|---|---|
| `ransomware-disk-write` (T1486, l. 29) | `Perf` | non : l'agent lit les compteurs du noyau (CR3) | oui (`disk_write_rate_bps`) | aucune requise | — |
| `data-exfiltration-blob` (T1041, l. 82) | `StorageBlobLogs` | non : écrite par Azure Storage | oui (`caller_ip`) | aucune requise | — |
| `ssh-brute-force` (T1110.001, l. 104) | `Syslog` `auth`, `sshd` | **oui** | **oui** (`failed_auth_count`) : bloquer l'adresse que la ligne nomme | **flux réseau** : un flux TCP autorisé de l'adresse vers le port 22 de la VM, dans la fenêtre, **dont les paquets de la VM vers l'adresse ont une taille moyenne de bannière, pas de SYN-ACK** (`NTANetAnalytics`, CR13) : une connexion établie, qu'une source usurpée n'obtient pas (§3.10). En plus, si le canal d'audit existe : `USER_AUTH`/`USER_LOGIN` `res=failed` `addr=<adresse>` écrits par sshd (CR8) | **flux : oui** (VNet flow logs et traffic analytics 10 min). Audit : non |
| `sudo-privilege-escalation` (T1548.003, l. 133) | `Syslog` `authpriv`, `sudo` | **oui** | **oui** (`privilege_escalation`) : isoler | **audit** : `USER_CMD` `res=success`, écrit par sudo lui-même (CR8) ; sur une image dont sudo n'en écrit pas (décidé par image, jamais par événement), l'`execve` de la commande avec **uid = 0 et euid = 0** sous l'`auid` du compte (clé `root_command`, `exe` = le chemin de `COMMAND=`), à ±2 s. Un `execve` à euid 0 seul ne suffit pas : un programme setuid (`passwd`, `chsh`, `mount`) lancé par n'importe quel compte en a un (§3.9) | **non** : les règles d'audit d'AUD1 sont posables (drapeau désactivé), mais leur canal est `Syslog` (§2.3) |
| COR1 → B3a (`login_after_brute_force` + `root_elevation`, `glorfindel/agent.py:1272`) | `Syslog` (`Accepted` de sshd, sudo) | **oui**, les deux faits | **oui** : `isolate_vm` au moins | la connexion : `USER_LOGIN` `res=success` `addr=<adresse>` de sshd (CR8). Les flux ne distinguent pas un échec d'un succès. L'élévation : comme le sudo | **non** |
| `t1136-001-local-account-creation-linux-v1` (l. 217) | `Syslog` `auth`, `useradd` | **oui** | possible : caractérisée (`account_creation`, `_CURATED_SYSLOG_PATTERNS`, l. 220) ; c'est la confiance qui tranche (35 % mesurés, BL1) | **audit** : la surveillance du CIS `-w /etc/passwd -p wa -k identity` (`exe=/usr/sbin/useradd`, `auid` non requis : Run Command est vu), ou `ADD_USER` écrit par useradd (CR8) | **non** : règle d'audit nouvelle et canal nouveau |
| `auditd-sensitive-root-command` (T1059.004, l. 179) | `Syslog` `local6`, `audisp-syslog` | **oui** (AUD1 le dit) | **oui** (`root_command`) | **le même enregistrement par le canal d'audit** (même `msg=audit(<instant>:<numéro>)`), ou la règle qui lit directement la table d'audit (Q7) | **non** |
| `t1053-003-cron-crontab-replace` (l. 260) | `Syslog` `cron` | oui | non : `syslog_event` non curé, le garde-fou retient | — (si un jour curée : `-w /var/spool/cron/crontabs -k cron`) | — |
| `t1070-002-log-tamper` (l. 289), `t1059-004-shell-from-world-writable` (l. 371) | `Syslog` `local6` | oui | non : aucun indicateur curé (repli générique) | — (lire la table d'audit, Q7) | — |
| Plan de contrôle (`AzureActivity`, l. 440-770) et identités (Entra ID, l. 771-925) | écrites par Azure | non | non : décision construite par le code, jamais autonome (AL1, C2) | — | — |

L'instantané reste possible sur toutes ces lignes. Q2 tranche s'il demande aussi une corroboration.

### 2.2 Les règles qui n'en ont pas besoin, et pourquoi

- **`Perf`.** L'agent lit `/proc` et l'écrit lui-même. Un utilisateur local peut **provoquer** une
  écriture disque réelle (`dd`). C'est un fait réel, pas une ligne forgée : ce cas est hors de V-01.
  Le seuil de la règle et le mode le tiennent (`human_only` par défaut, isolation réversible). CR3
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
| **A. Le journal texte d'AMA** : `/var/log/audit/audit.log`, en root seul (CR7), vers une table à lui (`EregionAudit_CL`, nom à fixer), avec une transformation de la DCR qui ne garde que les types utiles | root (auditd) seul | une table personnalisée, une DCR de journal texte, peut-être un point de collecte (CR9) ; l'ingestion (CR10) | **recommandé** (Q1) |
| B. Les propriétés de confiance de journald ou de rsyslog (`_UID`, `_EXE`, posées par le noyau), recopiées dans le message | — | un gabarit rsyslog à tenir sur chaque VM ; l'agent ne les range dans aucune colonne | fragile : non retenu |
| C. Microsoft Defender for Endpoint (`DeviceLogonEvents`, `DeviceProcessEvents`) | son capteur, en root | une licence par serveur | pour un client qui l'a déjà, plus tard |
| D. `VMConnection` (VM insights, agent de dépendances) | son agent, en root | un agent de plus, sa DCR | réseau vu de la VM seulement : non retenu en premier |

Le canal A tient contre un utilisateur sans privilège, pas contre root : root écrit le fichier. Les
flux sont pris hors de la VM, et root ne les écrit pas non plus. Mais **ils ne prouvent pas la source
d'un paquet** : un SYN à adresse source usurpée passe `allow-ssh` (ouvert à `*`) et donne un flux
autorisé au nom de n'importe quelle adresse. Seuls des paquets de la VM vers l'adresse plus gros que
des SYN-ACK et des RST, en moyenne, supposent une connexion TCP établie (CR13, §3.10). Les deux sources ne protègent donc
pas la même chose : §3.9 et §3.10.

### 2.4 Ce qui est collecté, d'après le dépôt

| Source | Où dans le dépôt | État au banc |
|---|---|---|
| `Syslog` `auth`, `authpriv`, `syslog`, `daemon` | `monitoring.tf:47` | collecté |
| `Syslog` `local6` (auditd par `audisp-syslog`) | `auditd.tf`, drapeau `auditd_enabled` | désactivé par défaut. Son état réel n'est pas dans le dépôt : `docs/operations.md` dit « rien ici n'a été planifié ni appliqué » (geste 0, §5) |
| VNet flow logs et traffic analytics 10 min → `NTANetAnalytics` | `monitoring.tf:109-131` | collecté. Le commentaire de la ressource nomme encore `AzureNetworkAnalytics_CL`, la table des NSG flow logs retirés : à corriger par la session Infra |
| `MicrosoftAzureBastionAuditLogs` | aucun (COR2 la lit si un client la déclare) | pas de Bastion au banc |
| `/var/log/audit/audit.log` vers une table | aucun | **nouveau** (SEC-A3d) |
| Règles d'audit `identity` (`-w /etc/passwd`…) | aucune dans `infra/terraform/scripts/auditd.sh`. `vm3_auditd.sh` pose `log_tamper` et `shell_exec`, sans extension pour le lancer | **nouveau** |
| `VMConnection`, Defender for Endpoint | aucun | non collecté |

Les VM du baseline ont une adresse publique et SSH ouvert à tous (`allow-ssh`, priorité 1000,
`infra/terraform/network.tf:34-42`). Des scanners d'Internet y font donc de vrais brute force en
continu. Le §5 s'en sert : il mesure la corroboration d'un vrai brute force sans lancer d'attaque.

## 3. Le mécanisme

### 3.1 Le principe

- **Le code, jamais le modèle.** La preuve est cherchée par une requête écrite dans le code, avec
  des valeurs vérifiées puis écrites en littéraux KQL (`kql.literal`, SEC4c). Le verdict n'entre
  jamais dans le prompt. `_build_user_message` écrit le signal entier (`json.dumps(signal)`,
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
  dépend de Q2. La levée d'isolation n'est pas concernée : elle n'est autonome que sur le
  `recovery_complete` de Glorfindel lui-même (SEC3).
- **Aucune dérogation.** La décision ne prévoit pas d'opt-out. Un déploiement sans source déclarée
  voit les lignes de ces tables en cartes.

### 3.2 Où : une étape du RulePoller, une garde de `decide`

1. **L'étape** (`glorfindel/corroboration.py`, nouveau) tourne dans `poll_once`
   (`glorfindel/detection_rules.py:1572`), après le routage et l'écart d'ADM1, à côté de
   `correlation.settle` (l. 1617). Elle tourne hors du verrou, et une faute ne fait jamais tomber la
   passe : elle devient un verdict `unknown` et la passe continue, comme `faults`. Elle interroge la
   source **pour la VM du registre** (la ressource où la ligne a été routée), jamais pour celle
   qu'écrit la ligne, comme COR2. Elle fait une requête par VM et par source pour toutes les lignes
   de la passe, dans un plafond par règle et par passe (`QUERIES_PER_POLL`, à part de celui de la
   corrélation). Au-delà du plafond : `unknown`. Une ligne de synthèse, qui en nomme d'autres
   (`_data_summary`, `glorfindel/detection_rules.py:1206` ; `auditd.fold`), n'est jamais corroborée :
   elle porte plusieurs adresses ou plusieurs commandes. L'étape prouve l'adresse **lue dans la
   ligne** (`detected_data` ou `first_result_row`), jamais `context.suspicious_ip`. Si `context` en
   nomme une autre, `_extract_suspicious_ip` la préfère, et la comparaison du point 4 retient
   l'action.
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
   `held_by = "corroboration"`, qui donne le type `uncorroborated_signal` (`_HELD_BY_TYPE`, l. 756).
   L'approbation en un clic dépend de Q8. Elle se filtre **par type de carte** :
   `eregion_core/action_queue.APPROVABLE_TYPES` (l. 72, lu l. 606), `glorfindel/approval.py:66` et
   la liste de la console, que `tests/unit/test_action_proposal.py` garde identiques. Le statut ne
   s'y lit pas. L'option recommandée de Q8 demande donc **deux types** : `corroboration_pending`
   (statut `pending` ou `unknown`, approuvable) et `uncorroborated_signal` (une source vivante a dit
   non, non approuvable). La carte change de type quand le statut change : à l'échéance de
   l'attente (§3.6), `pending` devient `uncorroborated`, et la carte passe à `uncorroborated_signal`
   (`escalations.record`, changement matériel). L'autre voie serait de lire le statut dans
   `approval.py` et dans la console : deux contrôles à tenir au lieu d'une liste. Une action déjà retenue par une garde
   plus tôt garde son type, et sa raison gagne la phrase de la corroboration, comme le fait la garde
   de télémétrie.

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
  source: flows                  # flows | audit | none
  window: [<début UTC>, <fin UTC>]
  evidence: {flows: 12, first: <UTC>, last: <UTC>}    # borné : des nombres et des instants
  why: "aucun flux de 198.51.100.23 vers le port 22 de <vm> entre 10:02 et 10:14 UTC"
```

**Un verdict absent vaut `uncorroborated`** quand l'action est disruptive : c'est l'échec fermé.
Seule l'étape écrit `not_required`, après avoir lu la requête.

Les faits que `confirm_facts` inscrit sur l'incident (B3a) restent des chaînes : `Incident.confirmed`
ne change pas de forme, et `decision_queue._floor` (`glorfindel/decision_queue.py:267`) et
`_root_compromise_floor` (`incident.get("confirmed")`, `glorfindel/agent.py:1295`) le lisent tels quels. Un ensemble parallèle,
`Incident.corroborated`, nomme ceux qui sont corroborés. Un incident d'avant, sans cet ensemble, n'a
aucun fait corroboré.

### 3.4 La fenêtre de temps

| Source | Fenêtre de la preuve | Pourquoi |
|---|---|---|
| Flux (brute force) | l'intervalle de la ligne agrégée : la période de la règle plus la marge d'ingestion (`window` de `poll_once`), élargie de `PROOF_SKEW_S` (120 s, `correlation.py:88`) de chaque côté. Un flux dont `FlowStartTime`–`FlowEndTime` touche cet intervalle compte | la ligne agrégée ne date pas ses échecs (limite de COR2) ; deux horloges, celle de la VM et celle d'Azure, plus les blobs d'une minute (F3) |
| Audit (sudo, compte, connexion) | l'instant de l'événement, lu dans `msg=audit(<s>.<ms>:<n>)` et non dans `TimeGenerated` (l'heure d'ingestion), à `SKEW_S` = 2 s de la ligne `Syslog` (`correlation.py:75`) | une seule horloge, celle de la VM (CR12) |

### 3.5 Une source en retard, en panne ou muette : une carte

L'étape ne conclut jamais sans lignes (A0). Chaque cas a son statut, et son texte sur la carte :

| Cas | Statut | Action disruptive |
|---|---|---|
| la preuve est trouvée dans la fenêtre | `corroborated` | possible (les autres gardes et le mode s'appliquent) |
| la source est vivante et ne montre rien | `uncorroborated` | carte |
| la preuve peut encore arriver (traffic analytics par lots), dans le délai d'attente de la source | `pending` | carte tout de suite ; l'action peut suivre (§3.6) |
| la requête échoue, est coupée à sa limite, ou le plafond de requêtes est atteint | `unknown` | carte |
| **la source est muette** : aucune ligne pour cette VM sur la dernière heure, quel que soit le port ou l'adresse | `unknown` (« source muette ») | carte |
| aucune source déclarée pour cette famille | `uncorroborated` (« aucune source ») | carte |
| la VM n'a pas de nom dans la source (`DestVm` vide, F1) | `unknown` | carte |

Le test de vie distingue deux réponses : « la source dit non » et « la source se tait ». Une VM
exposée à Internet a des flux à toute heure. Une VM privée peut n'en avoir aucun, et voit alors
toutes ses lignes en `unknown` : une carte, à dire (CR6).

### 3.6 Attendre la preuve (Q3)

Traffic analytics écrit par lots de 10 minutes (F4). La ligne `Syslog` d'un brute force arrive
souvent avant le flux qui la prouve. Sans attente, ce brute force serait presque toujours une carte,
et le blocage autonome disparaîtrait. Proposition :

- **La carte d'abord.** La passe où la ligne arrive sans preuve envoie le signal, `pending`. La
  garde le retient, et la carte part tout de suite : « en attente de corroboration (journaux de
  flux, jusqu'à 10:45 UTC) ».
- **L'action quand la preuve arrive.** Le RulePoller garde l'entrée en attente dans son état
  (`rule_status.json`, `corroboration_pending`). **Une entrée par (VM, règle, adresse)**, bornée en
  durée (`wait_s` par source : 1 800 s pour les flux, 600 s pour l'audit, à fixer par CR5 et CR9) et
  en nombre (`PENDING_MAX` par VM). Il la relit au plus toutes les 60 s, dans la même requête par VM.
  Quand la preuve arrive avant l'échéance, il émet **un second signal au plus par entrée**,
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
- **L'échéance passée sans preuve**, la carte reste et le dit : « aucune preuve avant 10:45 UTC ».

### 3.7 Ce qui est dit

- **Sur la carte** (raison, et le champ `corroboration` structuré pour la console et le bot), par
  exemple :
  - « Non corroborée : aucun flux réseau de 198.51.100.23 vers le port 22 de `<vm>` entre 10:02 et
    10:14 UTC (journaux de flux lus à 10:31). Une ligne Syslog peut être écrite par tout utilisateur
    de la VM : `block_suspicious_ip` retenue pour un humain. »
  - « Corroboration impossible : les journaux de flux n'ont pas été lus (<erreur>). Échec fermé. »
  - « Source muette : aucun flux de `<vm>` depuis une heure. »
  - « Aucune source ne corrobore cette règle (Syslog, sudo) : une ligne Syslog seule ne fait jamais
    agir. »
- **Après une action autonome**, la notification et la ligne de debug portent la preuve : « corroborée
  par 12 flux autorisés, 10:03–10:13 UTC ».
- **Compté** dans `rule_status.json` (`corroboration` : `required`, `corroborated`, `uncorroborated`,
  `pending`, `unknown`, `queries`), puis affiché dans le détail de la règle de la console et dans
  `glorfindel report` (« N actions autonomes sur Syslog, toutes corroborées »).

### 3.8 Le plancher B3a

Le plancher relève toujours l'action à `isolate_vm` (`_root_compromise_floor`, `agent.py:1272`). Il
passe avant les gardes et reste tel quel. La garde de corroboration la retient ensuite, sauf si les
**deux** faits de l'incident sont corroborés : la connexion réussie par `USER_LOGIN res=success`,
l'élévation par l'audit (Q6). Sinon la carte propose `isolate_vm` et dit pourquoi : « Plancher
déterministe (B3a) … ; faits non corroborés hors de Syslog ». La compromission est toujours dite à un
humain (COR1), corroborée ou non.

**Le plancher ne fait jamais moins que sans lui.** Cas : le modèle choisit `block_suspicious_ip`, le
blocage est corroboré par les flux, le plancher le relève à `isolate_vm`, et l'isolation est retenue
(faits non corroborés). Le choix proposé : le blocage corroboré part seul, et la carte propose
`isolate_vm` en plus. C'est le mécanisme de `displaced` de B3a, à l'envers : l'action retenue
attend son humain, l'action prouvée ne l'attend pas. L'autre choix serait de tout retenir, et
l'adresse resterait libre pendant que la carte attend. **L'accord des tirages se juge sur l'action
effectivement retenue** : chaque tirage est relevé par le plancher (`_confirming_draws`,
`glorfindel/agent.py:1565`), puis ramené de la même façon au blocage corroboré. Sinon
`_apply_agreement_guard` verrait des tirages `isolate_vm` face à un `block_suspicious_ip` et
retiendrait le blocage.

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

### 3.10 Ce qu'elle ne fait pas

- **Un flux autorisé ne prouve pas sa source.** `allow-ssh` est ouvert à `*`
  (`infra/terraform/network.tf:34-42`). Un SYN à adresse source usurpée y passe et donne un flux `A`
  au nom de n'importe quelle adresse. La réponse de la VM part vers l'adresse usurpée, et la
  connexion ne s'établit jamais.
- **Une ligne de `NTANetAnalytics` agrège.** Elle somme les flux d'une source vers un port de la VM
  sur l'intervalle de traffic analytics (10 min), sans port source : `BytesDestToSrc` est une somme.
  Un volume seul ne prouve donc rien. Quelques SYN usurpés reçoivent des SYN-ACK retransmis (jusqu'à
  5 fois, ~60 octets chacun), des ACK usurpés reçoivent des RST : une poignée de paquets usurpés
  dépasse 1 Ko. La preuve porte donc sur la **taille moyenne des paquets de la VM vers la source**
  (`BytesDestToSrc / PacketsDestToSrc`), au-dessus d'un seuil à mesurer (CR13), en plus d'un
  volume minimal. Un SYN-ACK ou un RST fait ~40 à 74 octets ; la bannière et le `KEXINIT` de sshd
  en font des centaines. Des paquets usurpés ne font que baisser cette moyenne, jamais la monter :
  seule une vraie connexion depuis l'adresse la porte au-dessus du seuil. C'est la preuve
  recommandée (Q5). La preuve stricte, connexion par connexion, demande les enregistrements par
  5-tuple des blobs de flux (SEC-A3f).
- **Les flux prouvent qu'une adresse a parlé au port 22, pas qu'elle a échoué.** Un compte local voit
  les adresses vraiment connectées (`/proc/net/tcp`, `ss`). Il peut écrire dix échecs au nom de l'une
  d'elles, un administrateur ou un partenaire, et la faire bloquer : ses flux sont réels et établis.
  `never_block` protège les adresses déclarées. Le compte des échecs par l'audit (`USER_AUTH`, Q5)
  ferme ce cas là où le canal A existe.
- **L'audit ne tient pas contre root.** Un intrus root écrit `audit.log`. Il peut faire isoler sa
  propre VM (réversible) ou corroborer un sudo. Les flux, eux, restent hors de sa portée.
- **Le modèle peut toujours être trompé.** L'enquête (`investigate`, `agent.py:697-702`) lit
  `Syslog` pour le contexte du modèle. Une ligne forgée peut orienter son raisonnement. La garde ne
  lui fait pas confiance : seule l'action change de main.
- **Ce n'est pas une détection de la forgerie.** Une ligne non corroborée n'est pas une attaque
  prouvée de l'utilisateur local. C'est une détection qui demande un humain.

## 4. Ce que ça coûte

| | Aujourd'hui | Avec la corroboration |
|---|---|---|
| **Blocage autonome d'un brute force sur une VM exposée** | à la passe qui suit l'ingestion `Syslog` (P95 supposé 480 s, `expected_latency_s`) | **continue** quand les flux corroborent, après le lot de traffic analytics : 10 à 20 minutes de plus en supposant F4 (moins de ~20 min, une heure au pire selon Microsoft Learn). La carte part toujours tout de suite (§3.6). Si F4 dépasse ~20 min, lire les blobs de flux d'une minute directement est un lot à part (§7, SEC-A3f) |
| **Sudo vers root, création de compte, commande sensible d'AUD1** | autonomes possibles en `non_disruptive` | cartes jusqu'à SEC-A3e, puis autonomes quand l'audit corrobore, à ±2 s, avec la latence d'un journal texte d'AMA (CR9) |
| **Plancher B3a** | `isolate_vm` autonome | carte qui propose `isolate_vm` tant que les deux faits ne sont pas corroborés par l'audit |
| **Collecte** | VNet flow logs et traffic analytics déjà en place au banc. Leur coût n'est pas relevé dans `docs/operations.md` (« Coûts réels ») : à relever sur la facture (§5, geste 1) | **rien de plus pour les flux.** Canal d'audit : l'ingestion Analytics, 2,99 USD le Go en West Europe au-delà des 5 Go gratuits du mois (même tarif qu'AUD1). Estimation pour une VM exposée : ~5 000 tentatives SSH par jour × 2 enregistrements × ~400 octets, soit ~0,12 Go par mois, plus les `execve` des deux clés d'AUD1. Le banc reste sous 1 USD par mois, à mesurer (CR10). Si le canal A remplace `local6` (Q7), le volume d'AUD1 dans `Syslog` disparaît |
| **Requêtes** | — | une par VM, par source et par passe quand une ligne en a besoin, plus les relectures en attente (au plus une par minute et par VM). Gratuites sur le niveau Analytics |
| **Appels au modèle** | — | aucun de plus pour la garde. Avec l'attente (SEC-A3c), une décision de plus **par adresse corroborée** (une entrée, un second signal au plus) : un appel, plus les tirages d'une action disruptive (`GLORFINDEL_DECISION_DRAWS`, 3 par défaut), dans la classe basse du plafond |
| **Le chemin `attack_started` (`respond`, exercices)** | une détection d'exercice peut contenir seule en `non_disruptive` | **pas d'attente** sur ce chemin (§3.2) : un T1110 d'exercice (BL1, Annatar depuis Orodruin) est presque toujours vu avant ses flux, donc une carte. Le contenu seul d'un brute force ne se mesure plus par `respond` ; il se mesure par la watch (le RulePoller attend). Concevoir l'attente sur ce chemin est possible (relire jusqu'à `wait_s` après la détection), mais allonge l'exercice d'autant : non proposé ici, à décider si BL1 en a besoin. Un T1486 d'exercice (`Perf`) ne change pas |
| **Instantanés sous un flot forgé** (si Q2 le garde autonome) | — | sans plafond, la file de décision seule laisse jusqu'à une décision par VM, règle, gravité et source toutes les 300 s : 288 par jour et par règle, ~1 150 par jour et par VM pour les quatre règles `Syslog` caractérisées, davantage par des compromissions forgées (une décision par adresse). Lecture du code, à vérifier dans SEC-A3b. Proposé : un instantané autonome **non corroboré au plus par VM et par heure**, soit 24 par jour et par VM ; les suivants sont dits sur la carte |
| **Indicateurs** | — | « part contenue seule » baisse pour les techniques lues dans `Syslog` sur un déploiement sans source, et « temps pour contenir » s'allonge pour le brute force. C'est le prix de la décision. Le contenu seul du T1548.003, que mesure BL1, attend SEC-A3e |

## 5. Le protocole de mesure au banc (gestes de Jonathan)

Rien ici n'est fait par une session. Les requêtes KQL sont des lectures du workspace du banc (le
portail, « Logs »), que la session Banc peut aussi lancer si Jonathan le veut (modèle de menace,
§8). Les gestes sur une VM se font par SSH, en lecture, sauf les lignes forgées de l'étape 3. Les
noms sont à remplacer, `<…>` ; rien de réel dans ce dépôt.

### 5.1 Les hypothèses

| | Hypothèse | Mesure | Si elle tient | Sinon |
|---|---|---|---|---|
| **CR1** | Un utilisateur sans privilège écrit une ligne `auth` étiquetée `sshd` (et `authpriv`/`sudo`, `local6`/`audisp-syslog`) qui arrive dans `Syslog` indistincte d'une vraie (`Facility`, `ProcessName`, `ProcessID` à son choix) | étape 3, requête M2 | le constat V-01 est mesuré | une colonne distingue l'émetteur : la noter, elle change le §2.3 |
| **CR2** | `_ResourceId` d'une ligne `Syslog` est posé par l'agent, jamais par la ligne. Un écrivain local n'atteint l'agent que par `/dev/log` ou par ses propres sockets | `ss -xlp`, `ss -tlnp` (les sockets de l'agent et leurs droits) ; une ligne au nom d'un autre hôte écrite sur `/dev/log`, puis M2 (`Computer`, `_ResourceId`) | rien | une ligne qui nomme une autre VM : un lot de routage, avant tout le reste |
| **CR3** | Aucun point d'entrée local de l'agent n'accepte des compteurs (`Perf`) d'un utilisateur | les mêmes `ss` | `Perf` reste dans la liste sûre | `Perf` sort de la liste sûre (Q4) |
| **CR4** | F1–F4 de COR2 valent pour les flux entrants d'Internet vers le port 22 : `DestVm` = `<groupe>/<vm>`, `DestPort == 22`, `FlowStatus == "A"`. L'adresse d'Internet peut être dans `SrcPublicIps` (une liste, sa forme à lire) plutôt que dans `SrcIp`, que COR2 lit seul | requête F de `docs/operations.md`, sur 24 h, avec `SrcPublicIps` | rien | lire `SrcPublicIps` aussi, dans le lecteur des flux (COR2 compris) |
| **CR5** | Toute ligne d'un vrai brute force (la règle, sur 7 jours) a au moins un flux autorisé de son adresse vers le port 22 de la VM dans sa fenêtre élargie de 120 s ; le délai entre la ligne `Syslog` et la ligne de flux reste sous `wait_s` | requête M1 : la part corroborée et la distribution du délai (p50, p95, max) | `wait_s` = p95 arrondi | une part non corroborée : en comprendre la cause (port, NAT, IPv6) avant le code |
| **CR6** | Une VM exposée a des lignes de flux à toute heure (test de vie) | requête M4 : les heures sans aucune ligne, sur 7 jours | le test de vie à 1 h | relever la durée du test de vie, ou le faire porter sur le VNet |
| **CR7** | `/var/log/audit/audit.log` n'est écrit que par root (0600 ou 0640, `root:root` ou `root:adm`) ; un utilisateur sans privilège ne peut pas émettre d'enregistrement `USER_*` | `stat` du fichier et du répertoire ; en utilisateur sans privilège, `auditctl -m test` doit échouer (refus de l'outil ou du noyau), et rien ne doit apparaître dans `ausearch -m USER -ts recent` | le canal A tient contre un utilisateur local | le canal A n'est pas une corroboration : revoir Q1 |
| **CR8** | Sous Ubuntu, sshd et PAM écrivent `USER_AUTH`/`USER_LOGIN` avec `addr=` et `res=` ; sudo écrit `USER_CMD` ; useradd écrit `ADD_USER` | `sudo ausearch -m USER_AUTH,USER_LOGIN -ts today -i \| tail` ; `sudo ausearch -m USER_CMD -ts recent` après un `sudo -n true` ; `ADD_USER` après une création de compte de test (qui fait sa carte T1136) | la table du §2.1 tient | un type absent : la règle d'audit qui le remplace (`-w /etc/passwd`, l'`execve` de `root_command`), un lot de la session Infra |
| **CR9** | L'agent lit `audit.log` (en root seul) comme un journal texte, suit sa rotation par auditd, et l'envoie à une table personnalisée en quelques minutes ; ce qu'il faut de plus (point de collecte, version d'azurerm) | après SEC-A3d : M3, le délai entre l'instant de `msg=audit(…)` et `TimeGenerated` ; une rotation forcée (`sudo service auditd rotate`) | `wait_s` de l'audit = p95 arrondi | l'agent ne lit pas le fichier : un groupe de lecture (`log_group`), jamais un droit d'écriture |
| **CR10** | Le volume du canal A, filtré par la transformation, reste sous ~0,5 Go par mois au banc | M3 sur 24 h, puis 7 jours (`_BilledSize`) | rien | restreindre les types gardés, ou les règles d'audit |
| **CR11** | Une ligne forgée par `logger` n'apparaît pas dans la table d'audit | étape 3 refaite après SEC-A3d, M3 | le canal A tient | revoir Q1 |
| **CR12** | L'instant de `msg=audit(…)` d'un `sudo` et celui de sa ligne `Syslog` tombent à 2 s au plus l'un de l'autre | M3 et M2 pour un même `sudo -n true` | `SKEW_S` = 2 | relever la tolérance de l'audit seule |
| **CR13** | `NTANetAnalytics` porte les octets et paquets de chaque sens (`BytesDestToSrc`, `PacketsDestToSrc`), sommés par source, port de destination et intervalle. Sur un vrai brute force, connexion établie, la taille moyenne des paquets de la VM vers la source dépasse nettement celle d'un SYN-ACK ou d'un RST (~40 à 74 octets) : la bannière et le `KEXINIT` de sshd font des centaines d'octets. Des SYN ou des ACK usurpés ne donnent que des paquets de cette petite taille | M1 (`MeanOut`, `Established`) sur les vrais brute force : la distribution de la taille moyenne, et celle des flux du port 22 qui n'ont jamais de connexion établie (les scanners de ports, SYN seul) | le seuil de taille moyenne, et le volume minimal, réglés entre les deux distributions | les deux distributions se chevauchent, ou les colonnes manquent : la preuve stricte passe aux blobs par 5-tuple (SEC-A3f), ou à `USER_AUTH` (Q5) ; les flux agrégés seuls ne bloquent plus |

### 5.2 Les étapes

0. **L'état.** `auditd_enabled` est-il posé (`terraform.tfvars`) ? Les flux arrivent-ils (requête F) ?
   Pendant l'étape 3, la VM visée passe en `human_only` dans la console. Sinon le code d'aujourd'hui
   bloquerait seul l'adresse de documentation (sans effet hors de la VM, mais une règle NSG à lever
   par `glorfindel unblock`).
1. **Le coût des flux** : relever sur la facture du mois les postes Network Watcher (flow logs) et
   traffic analytics, et l'ingestion de `NTANetAnalytics` (`_BilledSize`, M4). Les écrire dans
   `docs/operations.md`, « Coûts réels », par le lot SEC-A3b.
2. **Le vrai brute force, sans attaque** : M1 sur 7 jours (CR4, CR5, CR6). C'est la preuve qu'un vrai
   brute force est corroboré : chaque ligne de la règle trouve ses flux.
3. **La ligne forgée** : dix lignes de la forme d'un échec de sshd, écrites sous son étiquette par un
   compte sans privilège (le compte d'administration sans `sudo` suffit), avec une adresse de
   documentation (RFC 5737). Puis une ligne de la forme de sudo sous l'étiquette de sudo, et une ligne
   sous l'étiquette d'`audisp-syslog`. Les commandes sont données à Jonathan hors du dépôt. Ensuite :
   - M2 : les trois lignes sont dans `Syslog`, indistinctes (CR1) ;
   - la règle `ssh-brute-force` les voit à la passe suivante (la carte, en `human_only`) ;
   - M1 restreinte à cette adresse : **aucun flux**. La ligne n'est pas corroborée ;
   - sur la VM : `ausearch -m USER_AUTH,USER_LOGIN -ts recent` ne montre **rien** pour cette adresse,
     et `ausearch -m USER_CMD` rien pour cette commande (CR8).
4. **auditd sur la VM**, en lecture : CR7, CR8, les `ss` de CR2 et CR3.
5. **Après SEC-A3d** (le canal A appliqué par Jonathan) : M3 (CR9, CR10, CR12), et l'étape 3 refaite
   (CR11).
6. **Après SEC-A3b, c et e sur H0** : la VM exposée revient en `non_disruptive`.
   - Un vrai brute force d'Internet donne une carte « en attente », puis, quand les flux arrivent, un
     blocage autonome. Sa notification dit « corroborée par N flux ».
   - L'étape 3 donne une carte « non corroborée » : rien n'est bloqué.
   - Un `sudo -i` d'un administrateur, s'il n'est pas attendu (ADM1), est corroboré par l'audit.
   - `glorfindel report` compte les cas.

### 5.3 Ce qui prouverait que la corroboration tient

| Cas | Attendu |
|---|---|
| Ligne `sshd` forgée par `logger`, adresse qui ne se connecte jamais | `uncorroborated` : carte, aucun blocage, en `non_disruptive` |
| Vrai brute force d'Internet sur la VM exposée | `corroborated` (pour ≥ 95 % des fenêtres de M1, avec une taille moyenne des paquets de la VM au-dessus du seuil de CR13 ; tolérance à fixer avec Jonathan) ; blocage autonome dans `wait_s` |
| Ligne `sudo` forgée | `uncorroborated` : carte, aucune isolation |
| Ligne `audisp-syslog` forgée | absente de la table d'audit (CR11) ; carte sans action |
| Vrai `sudo -i` | `corroborated` par l'`execve` de `root_command` à ±2 s |
| Source coupée (vérifié par les tests, sur de faux journaux : requête en échec, table vide, plafond) | `unknown` : carte, jamais une action |

### 5.4 Les requêtes (principe)

**M1, un brute force et ses flux** (`<vm>` est le nom ARM, `<groupe>/<vm>` celui de `DestVm`) :

```kusto
let rows = Syslog
| where TimeGenerated > ago(7d)
| where Facility == "auth" and ProcessName in ("sshd", "sshd-session")
| where SyslogMessage has "Failed password" or SyslogMessage has "Invalid user"
| where _ResourceId =~ "<id de ressource de la VM>"
| extend SourceIP = extract(@"from (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) port \d+( ssh2)?( \[preauth\])?\]?\s*$", 1, SyslogMessage)
| where isnotempty(SourceIP)
// Comme la règle : au moins 10 échecs d'une adresse dans une fenêtre de 10 minutes (des fenêtres
// fixes ici, glissantes dans la règle : une approximation).
| summarize Failed = count() by SourceIP, WinStart = bin(TimeGenerated, 10m)
| where Failed >= 10
| extend WinEnd = WinStart + 10m;
let flows = NTANetAnalytics
| where TimeGenerated > ago(7d)
| where SubType == "FlowLog" and DestPort == 22 and L4Protocol == "T" and FlowStatus == "A"
| where DestVm =~ "<groupe>/<vm>"
// L'adresse d'Internet dans SrcIp ou dans SrcPublicIps (CR4 : la forme de cette colonne est à lire).
| extend Src = iff(isnotempty(SrcIp), SrcIp, extract(@"^(\d{1,3}(?:\.\d{1,3}){3})", 1, tostring(SrcPublicIps)))
| project Src, FlowStartTime, FlowEndTime, Ingested = TimeGenerated, BytesDestToSrc, PacketsDestToSrc;
rows
| join kind=leftouter flows on $left.SourceIP == $right.Src
// Un flux qui recouvre la fenêtre à ±120 s.
| extend Overlaps = isnotnull(FlowStartTime) and FlowStartTime <= WinEnd + 120s and FlowEndTime >= WinStart - 120s
| summarize Corroborated = countif(Overlaps) > 0,
            Bytes = sumif(BytesDestToSrc, Overlaps), Packets = sumif(PacketsDestToSrc, Overlaps),
            FirstIngested = minif(Ingested, Overlaps)
            by SourceIP, WinStart, WinEnd
// CR13 : la taille moyenne des paquets de la VM vers la source, et un volume minimal ; <seuil> et
// <volume> à régler sur cette mesure même.
| extend MeanOut = iff(Packets > 0, todouble(Bytes) / Packets, real(null))
| extend Established = MeanOut > <seuil> and Bytes > <volume>
// Le délai : de la fin de la fenêtre à l'ingestion du premier flux qui la recouvre.
| extend Delay = FirstIngested - WinEnd
| summarize Windows = count(), Corroborated = countif(Corroborated), Established = countif(Established),
            MeanOutP5 = percentile(MeanOut, 5), MeanOutP50 = percentile(MeanOut, 50),
            p50 = percentile(Delay, 50), p95 = percentile(Delay, 95), Max = max(Delay)
```

La même requête, sans la jointure aux échecs (`NTANetAnalytics` seul, port 22, par adresse et
fenêtre), donne la distribution de `MeanOut` des adresses qui ne font que sonder le port : l'autre
côté du seuil.

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

**M4, le test de vie et le volume des flux** :

```kusto
NTANetAnalytics
| where TimeGenerated > ago(7d)
| where SubType == "FlowLog" and DestVm =~ "<groupe>/<vm>"
| summarize Rows = count(), Bytes = sum(_BilledSize) by bin(TimeGenerated, 1h)
| order by TimeGenerated asc
```

## 6. Questions pour Jonathan

Une à la fois, l'option recommandée en premier.

1. **Le canal d'auditd.** Celui d'AUD1 (`audisp-syslog` vers `Syslog`) est forgeable : il ne
   corrobore rien.
   - **(recommandé) A. Le journal texte d'AMA** : `/var/log/audit/audit.log` vers une table à lui, par
     un drapeau de Celebrimbor désactivé par défaut (SEC-A3d). Le fichier n'est écrit que par root.
   - B. Defender for Endpoint, pour un client qui l'a. Une licence, et rien au banc.
   - C. Pas d'audit : seuls les flux corroborent. Le sudo, la création de compte et B3a restent des
     cartes pour toujours.
2. **L'instantané.** Il est autonome et ne contient rien.
   - **(recommandé) Il reste autonome sans corroboration, plafonné.** Il ne change rien de joignable
     et garde la preuve. Une détection caractérisée garde sa carte (SEC4a). Sous un flot forgé, la
     file de décision seule laisserait ~1 150 instantanés par jour et par VM, davantage par des
     compromissions forgées (§4) : un instantané non corroboré au plus par VM et par heure, soit 24
     par jour.
   - Lui aussi exige la corroboration, et devient une carte sans elle.
3. **Le moment.**
   - **(recommandé) La carte d'abord, l'action quand la preuve arrive**, dans un délai borné par
     source (§3.6). Sans attente, le blocage autonome du brute force disparaît, puisque les flux
     arrivent après la ligne.
   - Retenir la détection jusqu'à la preuve : la carte arrive 10 à 20 minutes plus tard.
   - Ne jamais attendre : une ligne non corroborée à la passe reste une carte, et l'action ne suit pas.
4. **Quelles lignes demandent une corroboration.**
   - **(recommandé) Une liste blanche, par la forme de la requête** (§3.1). Une requête est exemptée
     seulement si chaque identifiant qui ouvre une expression tabulaire, où qu'il soit (tête,
     `let`, `join`, `lookup`, `union`, `in (…)`, `toscalar(…)`…), est dans une liste fermée (`Perf`,
     `StorageBlobLogs`, `NTANetAnalytics`, la table d'audit) ou un `let` sûr, et si chaque
     opérateur et chaque fonction appartient à une liste fermée reconnue (`search`, `table(`,
     `externaldata`, `mv-apply`, `fork`, une fonction enregistrée… n'y sont pas). Tout le reste demande une preuve : `Syslog`, une table inconnue, une
     règle du client ou une règle proposée. Le jugement est statique, avant toute requête.
   - Seules les règles livrées qui lisent `Syslog`. Une règle du client sur une table inconnue
     agirait alors sans preuve.
5. **La force de la preuve d'un brute force.**
   - **(recommandé) Un flux établi au moins** : un flux TCP autorisé de l'adresse vers le port 22 de
     la VM, dans la fenêtre, dont les paquets de la VM vers l'adresse ont une taille moyenne
     au-dessus du seuil de CR13, avec un volume minimal. La ligne agrège (§3.10) : des paquets
     usurpés ne font que baisser cette moyenne, et une source usurpée n'obtient pas de connexion
     établie. Plus, là où le canal d'audit existe, des `USER_AUTH` en échec
     de cette adresse : ils ferment le cas de l'adresse d'un administrateur, vraiment connectée,
     nommée dans une ligne forgée (§3.10).
   - Un flux autorisé, quels que soient ses octets, ou un volume seul (plus d'~1 Ko). Une poignée de
     SYN ou d'ACK usurpés corroborerait n'importe quelle adresse.
   - La preuve stricte, connexion par connexion : les enregistrements par 5-tuple des blobs de flux
     (SEC-A3f). Une collecte de plus, une latence plus courte.
   - Les `USER_AUTH` seuls. Ils attendent le canal d'audit : d'ici là, aucun blocage autonome.
   - Un nombre de flux cohérent avec le nombre d'échecs (au moins ⌈échecs / `MaxAuthTries`⌉). Cela
     dépend d'une colonne de comptage des flux à mesurer, et sshd peut être réglé autrement.
6. **Le plancher B3a.**
   - **(recommandé) Autonome seulement quand les deux faits sont corroborés par l'audit** : la
     connexion par `USER_LOGIN res=success`, l'élévation par l'`execve` en root. Sinon la carte
     propose `isolate_vm`.
   - Les flux suffisent pour la connexion. Mais ils ne distinguent pas un échec d'un succès : une
     ligne `Accepted` forgée au nom d'un vrai scanner ferait isoler la VM.
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

Mutants réservés : **M4530–M4539 et M4579–M4585**, répartis ci-dessous. L'ordre :

1. les étapes 0 à 4 du §5 ;
2. SEC-A3a, indépendant ;
3. SEC-A3b et SEC-A3c, dans la même version : b seul ferait du brute force une carte ;
4. SEC-A3d, puis l'étape 5 ;
5. SEC-A3e ;
6. l'étape 6.

Chaque lot met à jour les **deux** lignes « S » du §4 du modèle de menace pour ce qu'il ferme :
celle de l'injection (« les règles ancrées filtrent sur l'étiquette que l'émetteur déclare ») et
celle de la corrélation (« l'étiquette `sshd` ne prouve pas l'émetteur »), ainsi que son point
« Ouvert ». #632 se ferme quand V-01 y passe dans « ce qui tient ».

| Lot | Session | Ce qu'il fait | Fini quand | Mutants |
|---|---|---|---|---|
| **SEC-A3a** — les bornes de la corrélation (commentaire de SEC-D sur #632) | Glorfindel | Borne à 64 caractères le service et le compte que la raison de `SessionOrigin` recopie, comme le sont ceux de `SuccessfulLogins`. Écrit pourquoi une ligne `session opened … by` est lue sous toute étiquette : elle ne peut qu'ajouter une carte (« compte pris par … »), jamais en retirer une, donc l'échec est fermé. | Tests : un service de 10 000 caractères est borné sur la raison ; une ligne de session forgée sous une étiquette étrangère fait une carte et n'écarte jamais un shell root. `correlation.md` dit le pourquoi. La ligne « S » du modèle de menace dit les bornes tenues. | M4530 (borne retirée) |
| **SEC-A3b** — le cœur, et les flux pour le brute force | Glorfindel | `glorfindel/corroboration.py` : la liste blanche par la forme de la requête (§3.1, Q4), l'étape dans `poll_once` et sur le chemin de `respond`, le verdict lié à son adresse et à sa VM et rangé dans `GlorfindelState` (§3.3), la clé entrante retirée, la source `flows` (VM du registre, `SrcIp` et `SrcPublicIps`, taille moyenne et volume de CR13, `kql.literal`, fenêtre §3.4, test de vie, plafond). Puis `_apply_corroboration_guard` et les types `uncorroborated_signal` et `corroboration_pending` (dans `_HELD_BY_TYPE` ; le second seul dans `eregion_core/action_queue.APPROVABLE_TYPES` et la liste de la console, selon Q8), `Incident.corroborated`, le plancher B3a qui ne fait jamais moins (§3.8), le plafond d'instantanés (Q2), la clé `corroboration` de `glorfindel-config.yaml` (sources déclarées, lue strictement ; la même lecture des flux que `expected_sudo.origin_proof: flows` de COR2, une seule fonction), les compteurs, la console, `report`. **Le geste de déploiement sur H0** : déclarer `corroboration: {flows: …}` dans le `glorfindel-config.yaml` de H0 avant la version qui porte le lot, sinon gondolin et bree perdent tout blocage autonome ; écrit dans `docs/operations.md`. | Tests sur de faux journaux, en `non_disruptive`. **Le message utilisateur de `_build_user_message` est identique à l'octet avec et sans verdict.** Une ligne `sshd` sans flux, ou avec des flux dont la taille moyenne des paquets de la VM reste sous le seuil de CR13 (des SYN-ACK et des RST, quel que soit leur volume), donne une carte, aucun blocage. Avec un flux établi, `block_suspicious_ip` est autonome comme avant. Un verdict pour une autre adresse ou une autre VM que la cible est retenu. `Perf` et `StorageBlobLogs` ne changent pas ; `ransomware-disk-write` est exempté ; une requête qui joint `Syslog`, lit `Syslog` dans une sous-requête (`Perf | where Computer in (Syslog | …)`, `toscalar(…)`), nomme une table inconnue, une fonction, `search`, `externaldata` ou `mv-apply` ne l'est pas. Un verdict absent, une requête en échec, coupée, au plafond, une source muette, une ligne de synthèse donnent une carte. Sur `respond`, même jugement. Une colonne ou une clé `corroboration` venue d'une règle ou de `runs/` est sans effet. B3a sans audit : le blocage corroboré part, la carte propose `isolate_vm`, et l'accord des tirages ne retient pas le blocage. Une carte `uncorroborated_signal` refuse l'approbation en un clic (`approval.py`, `action_queue.verbs`, la console) ; une carte `corroboration_pending` l'accepte (selon Q8). Docs à jour : `glorfindel.md`, `correlation.md`, `operations.md` (déclarer la source, coût des flux), modèle de menace. `changes/SEC-A3b.md`. | M4531 (garde retirée), M4532 (verdict absent lu comme corroboré), M4533 (source en échec lue comme corroborée), M4534 (VM de la ligne au lieu de celle du registre), M4579 (verdict laissé dans le signal donné au modèle), M4580 (exemption par simple mention d'une table sûre ; le cas `in (Syslog | …)` le tue aussi), M4581 (verdict non comparé à l'adresse et à la VM visées), M4582 (clé `corroboration` entrante non retirée), M4583 (seuil d'octets ou de taille moyenne de CR13 retiré) |
| **SEC-A3c** — attendre la preuve (si Q3 tranche ainsi) | Glorfindel | L'état `pending` borné (nombre, `wait_s` par source), la relecture au plus par minute, le second signal clé par sa preuve dans la file de décision, la carte mise à jour, l'échéance dite. L'état survit à un redémarrage de la watch. | Tests. Une preuve qui arrive dans `wait_s` donne une action autonome et une carte mise à jour. Une preuve qui arrive après donne une carte « aucune preuve avant … » et aucune action. **Une carte acquittée, rejetée ou approuvée par un humain avant la preuve annule l'action en attente.** Une entrée par (VM, règle, adresse), un second signal au plus par entrée, de classe basse ; il n'est pas dédoublonné par SEC-A2. Une liste d'attente pleine chasse l'entrée la plus ancienne, et sa carte le dit. Après un redémarrage, rien n'est perdu ni rejoué en double. | M4535 (attente non bornée), M4536 (second signal dédoublonné) |
| **SEC-A3d** — le canal d'audit au banc (si Q1 = A) | Infra | Derrière un drapeau désactivé (`audit_channel_enabled`) : la DCR d'un journal texte sur `/var/log/audit/audit.log`, la table `EregionAudit_CL` et sa transformation (les types gardés), les règles d'audit qui manquent (`identity`). Le contrat est testé sans Azure (`terraform test`, `tests/unit/test_bench_auditd.py`). Les gestes et le retour en arrière vont dans `docs/operations.md`. Un fournisseur Terraform nouveau, s'il en faut un (azapi), suit CI4 : `make providers-lock`, une PR, le plan de Jonathan. | Le plan contre un faux azurerm montre l'ajout, et rien quand le drapeau est faux. Le contrat entre le script, la DCR et le lecteur est le même dans les trois. Le chemin `audit.log` et ses droits sont écrits. Jonathan applique ; l'étape 5 du §5 est faite. | — (Terraform : le contrat de `terraform test`) |
| **SEC-A3e** — l'audit corrobore | Glorfindel | La source `audit` : la lecture stricte des enregistrements (§3.9), le sudo (`execve` de `root_command` ou `USER_CMD`), la création de compte (`identity` ou `ADD_USER`), la connexion de B3a (`USER_LOGIN`), les `USER_AUTH` du brute force (Q5). Puis les règles d'AUD1 et de VM3 qui lisent la table (Q7). | Tests sur de faux enregistrements. Un sudo forgé donne une carte ; un vrai sudo (`USER_CMD`, ou `execve` à uid = euid = 0), une isolation possible. **Un setuid (`passwd`, `chsh`) lancé par un compte sans privilège ne corrobore rien.** Un fichier nommé `addr=…`, un `comm` choisi, un argument qui imite un champ, ou un champ lu seulement dans la partie enrichie (après 0x1d) ne corroborent rien. Un compte différent ou un instant à plus de 2 s ne corroborent rien. B3a est autonome seulement avec les deux faits corroborés. Les règles d'AUD1 donnent les mêmes cartes depuis la table. Docs et modèle de menace à jour (les deux lignes « S ») : V-01 passe dans « ce qui tient ». | M4537 (sous-chaîne au lieu du champ), M4538 (compte non comparé), M4539 (tolérance de 2 s retirée), M4584 (uid réel non comparé : un setuid corrobore), M4585 (champ lu dans la partie enrichie) |
| SEC-A3f — les flux à la minute (seulement si CR5 dépasse ~20 min) | Glorfindel, Infra | Lire les blobs des VNet flow logs (une minute) dans le compte de stockage, par un adaptateur `glorfindel/providers/azure/` et un rôle de lecture sur ce seul compte. | à écrire si la mesure le demande | à réserver |

## 8. Sources

- La forme des enregistrements d'audit, `CAP_AUDIT_WRITE`, l'encodage hexadécimal des chaînes non
  sûres : `auditd(8)`, `auditctl(8)`, `ausearch(8)`, `audit.rules(7)`, et le format des
  enregistrements du projet Linux Audit. `USER_AUTH`, `USER_LOGIN` (sshd et PAM), `USER_CMD` (sudo),
  `ADD_USER` (shadow-utils) : la documentation de chaque programme. Hypothèses CR7, CR8, CR12.
- Les VNet flow logs, traffic analytics et le schéma de `NTANetAnalytics` : Microsoft Learn (Network
  Watcher). Hypothèses F1–F4 et CR4–CR6.
- Les journaux texte de l'agent Azure Monitor, les tables personnalisées et les transformations de
  DCR : Microsoft Learn (Azure Monitor). Hypothèses CR9, CR10.
- Les benchmarks CIS pour Linux, les règles d'audit `identity` et `user_emulation` : déjà cités par
  AUD1 (`correlation.md`, « Ce que ferme AUD1 »).
