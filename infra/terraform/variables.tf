variable "admin_ssh_public_key" {
  description = "SSH public key for VM access (set in terraform.tfvars)"
  type        = string
  sensitive   = true
}

variable "subscription_id" {
  description = "Azure subscription id. Vide (défaut) → le provider lit ARM_SUBSCRIPTION_ID de l'env (mappé depuis AZURE_SUBSCRIPTION_ID par le Makefile). Jamais en dur dans le repo public."
  type        = string
  default     = ""
}

variable "vm_shutdown_email" {
  description = "Adresse prévenue 15 min avant l'extinction automatique des VMs. Dans terraform.tfvars (ignoré par git), jamais dans config.yaml (suivi, repo public). Vide → pas de notification."
  type        = string
  default     = ""
}

variable "topo_filter" {
  description = "Surcharge des topologies actives (depuis `make celebrimbor-up TOPO=a,b`). Vide = on respecte topologies.<name>.enabled du config.yaml."
  type        = list(string)
  default     = []
}

# ── Les journaux du plan de contrôle et d'Entra ID → le workspace du banc (ID1) ──────────
# Deux paramètres de diagnostic qui ne vivent pas dans le groupe du banc : l'un sur
# l'ABONNEMENT (activity_log.tf), l'autre sur le TENANT Entra ID (entra_logs.tf).
# Désactivés par défaut. Les activer est une décision de l'opérateur sur SON abonnement et
# SON tenant : dans terraform.tfvars (ignoré par git, persistant) — jamais dans config.yaml
# (suivi, repo public : un fork qui applique enverrait les journaux de son tenant sans
# l'avoir décidé), ni en `-var` d'une seule commande (le prochain apply sans lui retirerait
# le paramètre). Posés par l'instance canonique seule (workspace Terraform "default") ;
# ailleurs, sans effet, et dit (check "diagnostic_settings_on_the_canonical_instance").
# Commandes, droits, coût, mesures : docs/operations.md, « Les journaux d'activité et
# d'Entra ID au banc (ID1) ».

variable "activity_log_enabled" {
  description = "Journal d'activité de l'abonnement (catégorie Administrative) → le workspace du banc : la table AzureActivity des règles d'AL1. Droit : écrire un paramètre de diagnostic sur l'abonnement (Monitoring Contributor). Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

variable "entra_logs_enabled" {
  description = "Journaux d'Entra ID du tenant (AuditLogs, ServicePrincipalSignInLogs) → le workspace du banc : les tables des règles de C2. Tout le tenant, pas seulement le banc. Droit : rôle d'Entra Administrateur de la sécurité (ou général), pas un rôle Azure. Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

# ── Une identité de test du banc dans Entra ID, inscrite (IDI1, #546) ───────────────────
# Désactivée par défaut ; dans terraform.tfvars, jamais en `-var` d'une seule commande (le prochain
# apply sans lui la détruirait). entra_identity.tf, docs/operations.md.
variable "entra_test_identity_enabled" {
  description = "Une application et son principal de service dans le tenant du banc, mono-tenant, sans secret, inscrits par les deux clés (ses tags Graph eregion-target et eregion-zone, eregion-identities sur le groupe du banc) : la cible des techniques d'identité (R2). Instance canonique seule. Droit : créer une application (Développeur d'applications, ou plus). Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

# ── auditd sur les VM du banc, ses lignes vers le workspace (AUD1, #408) ────────────────
# Désactivé par défaut ; dans terraform.tfvars (persistant), jamais en `-var` d'une seule commande
# (le prochain apply sans lui retirerait l'extension et la facilité). auditd.tf, docs/operations.md.
variable "auditd_enabled" {
  description = "auditd sur les VM du banc (la règle du CIS user_emulation, et root_command : les commandes d'un shell root sous l'auid de connexion), ses lignes par audisp-syslog vers local6, que la DCR envoie à Syslog : la règle auditd-sensitive-root-command de Glorfindel. Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

# ── Qui écrit sous Linux, par auditd : les montres d'écriture (WRT1, #1275) ─────────────
# Désactivées par défaut, et sans effet sans auditd_enabled (auditd.tf) ; dans terraform.tfvars,
# jamais en `-var`. Les dossiers suivis : une liste bornée, chacun un chemin absolu simple, jamais un
# système de fichiers virtuel ni un dossier de journaux ou de fichiers temporaires (le volume).
variable "auditd_write_watch_enabled" {
  description = "WRT1 : des montres d'écriture auditd sur les dossiers de auditd_write_watch_dirs (l'exécutable, l'uid, l'auid et le pid de chaque ouverture en écriture, création, renommage, suppression ou troncature, jamais chaque write()), et le battement de la montre (un minuteur systemd qui écrit toutes les 5 minutes dans /var/lib/eregion/write-watch) : la lecture process_write_audit de l'enquête, à mesurer au banc. Posées par la même extension qu'auditd (scripts/auditd.sh, puis scripts/auditd_write.sh) ; sans effet si auditd_enabled est à false. Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

variable "auditd_write_watch_dirs" {
  description = "WRT1 : les dossiers que suivent les montres d'écriture (récursifs), 1 à 8 chemins absolus. Le défaut est celui du banc : les comptes (/home, /root), les données servies (/srv, /var/www), les sauvegardes locales (/var/backups : celle du site de bree à 01:30) et le disque de T1486 (/mnt/testdata). Un dossier absent de la VM est sauté, et dit dans la sortie de l'extension."
  type        = list(string)
  default     = ["/home", "/root", "/srv", "/var/www", "/var/backups", "/mnt/testdata"]
  nullable    = false

  validation {
    condition     = length(var.auditd_write_watch_dirs) >= 1 && length(var.auditd_write_watch_dirs) <= 8 && length(distinct(var.auditd_write_watch_dirs)) == length(var.auditd_write_watch_dirs)
    error_message = "auditd_write_watch_dirs : de 1 à 8 dossiers, chacun une seule fois."
  }
  validation {
    condition     = alltrue([for d in var.auditd_write_watch_dirs : can(regex("^(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+$", d)) && length(d) <= 120])
    error_message = "auditd_write_watch_dirs : des chemins absolus simples (lettres, chiffres, . _ -, aucun composant qui commence par un point, ni / final, 120 caractères au plus) : aucun espace, aucun motif, aucun ..."
  }
  validation {
    condition     = alltrue([for d in var.auditd_write_watch_dirs : !can(regex("^/(proc|sys|dev|run|tmp|var/tmp|var/log|var/lib/eregion)(/|$)", d))])
    error_message = "auditd_write_watch_dirs : ni /proc, /sys, /dev, /run (virtuels), ni /tmp, /var/tmp, /var/log (le volume ; /var/log est aux règles de VM3), ni /var/lib/eregion (le battement de la montre)."
  }
}

# ── VM3 (#548) : la facilité cron dans la DCR du banc ──────────────────────────────────
# Pour la règle t1053-003-cron-crontab-replace : crontab écrit « REPLACE » en facilité cron, que
# la DCR du banc ne collecte PAS par défaut. Désactivé par défaut ; dans terraform.tfvars, jamais
# en `-var` d'une seule commande (le prochain apply sans lui retirerait la facilité). monitoring.tf.
variable "cron_logs_enabled" {
  description = "Ajoute la facilité cron à la DCR du banc (monitoring.tf), pour la détection de persistance cron (T1053.003, VM3). Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

# G1 : les VM qui reçoivent le bruit bénin (chaos.tf). La source de vérité reste chaos.noise_vms
# du config.yaml ; cette variable ne sert qu'à le remplacer le temps d'un plan — ce que fait
# tests/chaos_noise.tftest.hcl, un local ne se remplaçant pas dans un test. Un second moyen
# d'allumer le bruit, réservé aux tests : jamais dans terraform.tfvars ni par TF_VAR_.
variable "chaos_noise_vms" {
  description = "Remplace chaos.noise_vms du config.yaml (G1) quand elle est donnée ; null (défaut) : le config.yaml."
  type        = list(string)
  default     = null
}

# ── INF-FL (#654) : la clé partagée du compte des flux réseau ─────────────────────────────
# false (le défaut) : allowSharedKeyAccess désactivé sur le compte des flux (storage.tf) — aucune clé,
# aucun SAS n'y vaut, seule une identité Entra ID autorisée y lit ou écrit (CR15,
# docs/design/corroboration.md). Que Network Watcher y écrive et que traffic analytics y lise sans
# clé est une HYPOTHÈSE à mesurer au banc après l'apply (docs/operations.md, « Le compte des flux
# réseau (INF-FL) ») : la FAQ de Network Watcher dit qu'il essaie une clé, puis un jeton. Si la mesure
# montre qu'aucun blob n'arrive, true est le retour en arrière, dans terraform.tfvars — jamais en
# `-var` d'une seule commande (le prochain apply sans lui la refermerait) : les blobs ne sont alors
# plus une preuve au sens de CR15, et la conception doit le dire avant SEC-A3f.
variable "flow_logs_shared_key_enabled" {
  description = "INF-FL : la clé partagée (allowSharedKeyAccess) du compte des flux réseau. Défaut false : seules des identités Entra ID y accèdent. true seulement si la mesure au banc montre que Network Watcher n'y écrit pas sans elle (docs/operations.md, « Le compte des flux réseau (INF-FL) »)."
  type        = bool
  default     = false
  nullable    = false
}

# ── PIO1 (#1258) : qui écrit sous Linux, la métrique par processus de l'agent ────────────────
# Désactivé par défaut ; dans terraform.tfvars (persistant), jamais en `-var` d'une seule commande (le
# prochain apply sans lui retirerait l'espace, la DCR et leurs associations). process_io.tf,
# docs/operations.md, « Qui écrit sous Linux, au banc (PIO1) ».
variable "process_io_enabled" {
  description = "PIO1 : un espace de travail Azure Monitor, une DCR à part qui y envoie la métrique OpenTelemetry process.disk.io (les octets lus et écrits par processus) de chaque VM du banc, et leurs associations — la lecture process_write_io de l'enquête, à mesurer au banc. La DCR de la règle reste intacte. Coût : à l'échantillon ingéré (docs/operations.md). Défaut false."
  type        = bool
  default     = false
  nullable    = false
}
