variable "admin_ssh_public_key" {
  description = "Clé SSH publique de l'opérateur — la même que Celebrimbor (le Makefile passe infra/terraform/terraform.tfvars)."
  type        = string
  sensitive   = true
}

variable "subscription_id" {
  description = "Abonnement Azure. Vide (défaut) → le provider lit ARM_SUBSCRIPTION_ID. Jamais en dur dans le repo public."
  type        = string
  default     = ""
}

variable "operator_cidr" {
  description = "Seule source autorisée en SSH : ton adresse IPv4 publique, en /32. `make imladris-plan OPERATOR_CIDR=<ton IP>/32` ; sans valeur, le Makefile la lit sur un service tiers, la dit et la vérifie (scripts/operator_cidr.py)."
  type        = string

  # SEC-G (audit du 13/11, V-40) : une seule adresse IPv4 publique, en /32 — jamais une plage (0.0.0.0/1,
  # /24…), une IPv6 (la VM n'a qu'une adresse publique IPv4), ni une adresse des plages réservées
  # ci-dessous (les mêmes que scripts/operator_cidr.py, tests/unit/test_operator_cidr.py les garde égales).
  # L'adresse au préfixe de chaque plage a l'adresse de réseau de la plage : elle en est.
  validation {
    condition = can(regex("^(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])(\\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])){3}/32$", var.operator_cidr)) && try(alltrue([
      for r in ["0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.168.0.0/16", "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4"] :
      cidrhost("${split("/", var.operator_cidr)[0]}/${split("/", r)[1]}", 0) != cidrhost(r, 0)
    ]), false)
    error_message = "operator_cidr doit être ton adresse IPv4 publique en /32 (make … OPERATOR_CIDR=<ton IP>/32) : jamais une plage, une IPv6, une adresse privée ou réservée."
  }
}

variable "location" {
  description = "Région de la VM. francecentral (16/10, choix de Jonathan) ; elle peut différer de celle du banc (westeurope) : Glorfindel ne parle qu'aux API d'Azure."
  type        = string
  default     = "francecentral"
}

variable "vm_size" {
  description = "Taille de la VM — celle déployée le 16/10 : D2als_v6 (2 vCPU, 4 Go, ~61 €/mois en continu). B2s manquait de capacité en francecentral, et le quota Basv2 de l'abonnement est à 0 : avec 2 cœurs Basv2 accordés, passer à Standard_B2als_v2 (~27 €/mois, même RAM). Image construite en 2 min 44 s, ~300 Mo au repos."
  type        = string
  default     = "Standard_D2als_v6"
}

variable "admin_username" {
  description = "Utilisateur de la VM ; Glorfindel tourne sous son HOME (~/.glorfindel, ~/.cache/chroma)."
  type        = string
  default     = "glorfindel"
}

variable "eregion_repo" {
  description = "Dépôt cloné sur la VM."
  type        = string
  # L'ancien nom, gardé (REN1) : cloné au premier démarrage par custom_data, le changer remplace la
  # VM. Il ne sert plus qu'au clone : deploy.sh et le CD repointent origin vers le nom actuel du
  # dépôt avant tout fetch (SEC-C). Passe au nom actuel à la prochaine reconstruction d'Imladris (un
  # terraform apply, son plan relu, par Jonathan).
  default     = "https://github.com/Vanyar53/eregion.git"
}

variable "eregion_ref" {
  description = "Branche ou tag cloné au premier démarrage ; ensuite `make imladris-start` déploie un tag ou un commit, détaché (M-3). Changer cette valeur remplace la VM (custom_data)."
  type        = string
  default     = "main"
}

variable "bench_resource_group" {
  description = "Groupe du banc que Glorfindel lit (Celebrimbor, workspace default)."
  type        = string
  default     = "rg-celebrimbor"
}

variable "session_drain_vms" {
  description = "SEC11 (R-03) : les VM du groupe du banc que Glorfindel défend et dont il coupe les sessions à l'isolation — « Eregion Glorfindel Session Drain » (Run Command) sur chacune, jamais sur le groupe. Gardée dans session_drain.auto.tfvars (commité). Vide (défaut) : aucune coupure. Le rôle doit exister dans le tenant (docs/operations.md, « Identités Azure »)."
  type        = list(string)
  default     = []

  # Une VM chacune une fois, la casse ignorée comme Azure ignore celle d'un nom de VM (SEC17) :
  # ["vm-a", "VM-A"] ferait deux attributions sur la même VM, la seconde refusée à l'apply (409).
  validation {
    condition     = length(var.session_drain_vms) == length(distinct([for n in var.session_drain_vms : lower(n)])) && alltrue([for n in var.session_drain_vms : can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", n))])
    error_message = "session_drain_vms : des noms de VM, chacun une fois (la casse ignorée)."
  }
}

variable "session_drain_principals" {
  description = "SEC17 (relecture) : les principaux du poste qui isolent eux-mêmes ce qu'un humain approuve, et coupent donc les sessions — la console (son object id, jamais son appId) : { console = \"<object id>\" }. « Eregion Glorfindel Session Drain » sur chaque VM de session_drain_vms, comme à H0, jamais sur le groupe. Pas le bot : il n'isole pas (Restore, Revert). Hors du dépôt : principals.auto.tfvars, ignoré par git. Jamais l'identité de H0, qui l'a déjà. Vide (défaut) : rien de plus."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for k, v in var.session_drain_principals : can(regex("^[a-z][a-z0-9-]{0,31}$", k)) && can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", v))]) && length(values(var.session_drain_principals)) == length(distinct([for v in values(var.session_drain_principals) : lower(v)]))
    error_message = "session_drain_principals : un nom (console) vers l'object id d'un principal, chacun une fois."
  }
}

variable "restore_vms" {
  description = "SEC17 : les VM du groupe du banc que le restore défend — « Eregion Glorfindel Restore Neutralize » (Run Command, la neutralisation de la dernière commande avant l'échange des disques) sur chacune, pour chaque principal de restore_principals, jamais sur le groupe. Gardée dans restore.auto.tfvars (commité). Une VM hors de la liste est restaurée quand même ; sa neutralisation est refusée, et dite sur la carte. Le rôle doit exister dans le tenant (docs/operations.md, « Identités Azure »)."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.restore_vms) == length(distinct([for n in var.restore_vms : lower(n)])) && alltrue([for n in var.restore_vms : can(regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", n))])
    error_message = "restore_vms : des noms de VM, chacun une fois (la casse ignorée)."
  }
}

variable "restore_principals" {
  description = "SEC17 : les principaux qui restaurent — celui de la console et celui du bot (leur object id, jamais leur appId), nommés : { console = \"<object id>\", bot = \"<object id>\" }. Hors du dépôt : principals.auto.tfvars, ignoré par git, sur le poste de l'opérateur (principals.auto.tfvars.example). Jamais l'identité de H0 : Glorfindel hébergé ne restaure pas. Vide (défaut) : aucune neutralisation attribuée."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for k, v in var.restore_principals : can(regex("^[a-z][a-z0-9-]{0,31}$", k)) && can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", v))]) && length(values(var.restore_principals)) == length(distinct([for v in values(var.restore_principals) : lower(v)]))
    error_message = "restore_principals : un nom (console, bot) vers l'object id d'un principal, chacun une fois."
  }

  # FS1g : « executor » est le nom que restore_executor.tf donne à l'exécuteur de restore — nommé ici,
  # merge l'écraserait sans rien dire.
  validation {
    condition     = !contains(keys(var.restore_principals), "executor")
    error_message = "restore_principals : « executor » est réservé à l'exécuteur de restore (restore_executor_enabled), jamais nommé à la main."
  }
}

variable "restore_staging_storage" {
  description = "RST1 : le compte de transit du restore (restore_staging_storage de la config de Glorfindel), dans le groupe du banc — « Eregion Glorfindel Restore Staging » (listKeys, le droit lié qu'un restore vérifie là) sur ce seul compte, pour chaque principal de restore_principals, jamais sur le groupe. Gardé dans restore.auto.tfvars (commité). Vide (défaut) : rien d'attribué. Le rôle doit exister dans le tenant (docs/operations.md, « Identités Azure »)."
  type        = string
  default     = ""

  # Un nom de compte de stockage Azure (3 à 24 minuscules et chiffres), jamais un chemin ni un id.
  validation {
    condition     = var.restore_staging_storage == "" || can(regex("^[a-z0-9]{3,24}$", var.restore_staging_storage))
    error_message = "restore_staging_storage : le nom d'un compte de stockage (3 à 24 minuscules et chiffres), jamais un chemin."
  }
}

variable "bench_workspace" {
  description = "Log Analytics du banc."
  type        = string
  default     = "law-celebrimbor-amonsul"
}

variable "identity_executor_enabled" {
  description = "IR1b (#572) : l'application de l'exécuteur d'identité dans Entra ID, son principal, Application.ReadWrite.OwnedBy et User.RevokeSessions.All de Microsoft Graph, Log Analytics Reader sur le workspace du banc (identity_executor.tf). Faux (défaut) : rien dans le tenant. Vrai : identity_executor.auto.tfvars (ignoré par git), appliqué par Jonathan, qui consent les permissions (docs/operations.md, « L'exécuteur d'identité »)."
  type        = bool
  default     = false
}

variable "identity_executor_certificate" {
  description = "IR1b : la partie publique du certificat de l'exécuteur (PEM, « BEGIN CERTIFICATE »), sa clé tirée sur H0, jamais ici. Vide (défaut) : aucun identifiant, l'exécuteur ne peut pas se connecter. Jamais une clé privée : le plan la refuse."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_executor_certificate == "" || (strcontains(var.identity_executor_certificate, "-----BEGIN CERTIFICATE-----") && !strcontains(upper(var.identity_executor_certificate), "PRIVATE KEY"))
    error_message = "identity_executor_certificate : la partie publique d'un certificat (PEM, BEGIN CERTIFICATE), jamais une clé privée."
  }
}

variable "restore_executor_enabled" {
  description = "FS1g (#1127) : l'application de l'exécuteur de restore dans Entra ID, son principal, « Eregion Glorfindel Restore » sur le groupe du banc (et celui du coffre s'il est distinct), et son object id parmi les principaux qui restaurent (Restore Neutralize par VM de restore_vms, Restore Staging sur le compte de transit) — restore_executor.tf. Faux (défaut) : rien dans le tenant. Vrai : restore_executor.auto.tfvars (ignoré par git), appliqué par Jonathan (docs/operations.md, « L'exécuteur de restore »)."
  type        = bool
  default     = false
}

variable "restore_executor_certificate" {
  description = "FS1g : la partie publique du certificat de l'exécuteur de restore (PEM, « BEGIN CERTIFICATE »), sa clé tirée sur l'hôte, jamais ici. Vide (défaut) : aucun identifiant, l'exécuteur ne peut pas se connecter. Jamais une clé privée : le plan la refuse ; jamais un secret client (il vivrait dans l'état)."
  type        = string
  default     = ""

  validation {
    condition     = var.restore_executor_certificate == "" || (strcontains(var.restore_executor_certificate, "-----BEGIN CERTIFICATE-----") && !strcontains(upper(var.restore_executor_certificate), "PRIVATE KEY"))
    error_message = "restore_executor_certificate : la partie publique d'un certificat (PEM, BEGIN CERTIFICATE), jamais une clé privée."
  }
}

variable "restore_vault_resource_group" {
  description = "FS1g : le groupe du coffre du banc, quand il n'est pas celui du banc — l'exécuteur de restore y reçoit aussi « Eregion Glorfindel Restore ». Vide (défaut), ou le groupe du banc : le seul groupe du banc."
  type        = string
  default     = ""

  validation {
    condition     = var.restore_vault_resource_group == "" || can(regex("^[A-Za-z0-9._()-]{1,90}$", var.restore_vault_resource_group))
    error_message = "restore_vault_resource_group : le nom d'un groupe de ressources, jamais un chemin."
  }
}
