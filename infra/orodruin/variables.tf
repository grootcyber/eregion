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
  description = "Seule source autorisée en SSH, et admise au pare-feu du canal : ton adresse IPv4 publique, en /32. Sans valeur, le Makefile la lit sur un service tiers, la dit et la vérifie (scripts/operator_cidr.py)."
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
  description = "Région de la VM. Orodruin ne parle qu'aux API d'Azure : elle peut différer de celle du banc."
  type        = string
  default     = "francecentral"
}

variable "vm_size" {
  description = "Taille de la VM — à confirmer à l'étape 0 d'O1 (quota de la famille, restrictions de SKU, prix). Repli connu : D2als_v6 en francecentral (capacité et quota vérifiés par H0 le 16/10) ; éteinte entre les sessions (orodruin-stop), quelques euros par mois."
  type        = string
  default     = "Standard_D2als_v6"
}

variable "admin_username" {
  description = "Utilisateur de la VM ; les injecteurs tournent sous son HOME et n'en montent que ~/runs (aucun docker run ne monte ~/.annatar, SEC20)."
  type        = string
  default     = "orodruin"
}

variable "bench_resource_group" {
  description = "Le groupe du banc, seule portée des droits d'Orodruin (Celebrimbor, workspace default)."
  type        = string
  default     = "rg-celebrimbor"
}

variable "bench_id" {
  description = "La valeur du tag eregion-target des VM inscrites (O0) : seules elles reçoivent le droit d'agir d'Orodruin (SEC5). Vide (défaut) → tirée du groupe du banc : rg-celebrimbor → celebrimbor, rg-celebrimbor-<instance> → celebrimbor-<instance>, comme Celebrimbor la pose."
  type        = string
  default     = ""
}

variable "channel_retention_days" {
  description = "Jours après sa dernière écriture où un blob de bloc du canal (fenêtre, campagne, rapport de run, détection) est supprimé (SEC5, V-21). Doit dépasser la purge de la watch (7 jours après le dernier moment d'une fenêtre, soit 7 jours + 2 h 15 après sa dernière écriture)."
  type        = number
  default     = 9

  validation {
    condition     = var.channel_retention_days >= 8
    error_message = "channel_retention_days doit dépasser la purge de la watch (7 jours + 2 h 15) : au moins 8."
  }
}

variable "journal_retention_days" {
  description = "Jours où le journal d'Orodruin poussé dans le canal (audit/) est gardé (SEC5, V-29)."
  type        = number
  default     = 90
}

variable "watch_subnet_id" {
  description = "Sous-réseau du Glorfindel hébergé (H0), admis par le pare-feu du compte du canal (SEC5, V-31). Le Makefile le lit dans l'état de infra/glorfindel-host ; vide → H0 n'atteint plus le canal."
  type        = string
  default     = ""
}

variable "watch_public_ip" {
  description = "IP publique de H0, admise par le pare-feu du compte du canal si H0 n'est pas dans sa région (SEC5, V-31). Le Makefile la lit dans l'état de infra/glorfindel-host."
  type        = string
  default     = ""
}

variable "bench_workspace" {
  description = "Log Analytics du banc (le collecteur d'Annatar y lit le Heartbeat)."
  type        = string
  default     = "law-celebrimbor-amonsul"
}

variable "model_api_prefixes" {
  description = "Adresses de l'API du modèle autorisées en sortie. api.anthropic.com : 160.79.104.0/23, plage publiée par Anthropic (platform.claude.com/docs/en/api/ip-addresses) ; à mesurer depuis la VM."
  type        = list(string)
  default     = ["160.79.104.0/23"]
}

variable "egress_locked" {
  description = "Sortie fermée hors périmètre. false seulement pour le premier apply (installation de Docker) ; `make orodruin-lock` la referme. Ouverte, le contrat reste passive."
  type        = bool
  default     = true
}

variable "contract_reader" {
  description = "Lecture des attributions de rôle sur tout l'abonnement. Mesuré le 19/10 : sans elle, Azure ne liste que les attributions que l'identité peut lire (celle du workspace, pas celle du banc) — l'absence de droits ailleurs n'est pas prouvée, le contrat reste passive (identity_unprovable)."
  type        = bool
  default     = true
}

variable "storage_service_tag" {
  description = "Sortie vers le canal des fenêtres : le tag du stockage de la région d'Orodruin."
  type        = string
  default     = "Storage.FranceCentral"
}

variable "watch_principal_id" {
  description = "Identité managée du Glorfindel hébergé (H0) : lectrice du canal des fenêtres, rédactrice du canal retour (#159), sauf si watch_principal_ids la laisse de côté. Le Makefile la lit dans l'état de infra/glorfindel-host ; vide → pas de watch hébergée."
  type        = string
  default     = ""
}

# WC1 (#523) : sans H0, la watch d'un poste ou d'une équipe parle à Orodruin. Chacune de ces
# identités lit le canal des fenêtres (`exercises`) et écrit le canal retour (`watch`), rien
# d'autre. null (défaut) → la seule watch hébergée, watch_principal_id, comme avant WC1.
variable "watch_principal_ids" {
  description = "Les identités des watches qui écrivent le canal retour et lisent celui des fenêtres : l'object id de leur principal de service (jamais son client id), ou de l'identité managée de H0. null (défaut) → [watch_principal_id]. Le Makefile la passe par WATCH_PRINCIPALS=<id>[,<id>…], sur la ligne de commande seulement."
  type        = list(string)
  default     = null

  validation {
    condition     = alltrue([for id in(var.watch_principal_ids == null ? [] : var.watch_principal_ids) : can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", id))])
    error_message = "watch_principal_ids : des object ids d'Entra ID (un GUID chacun), rien d'autre."
  }

  validation {
    condition     = var.watch_principal_ids == null ? true : length(var.watch_principal_ids) == length(distinct([for id in var.watch_principal_ids : lower(id)]))
    error_message = "watch_principal_ids : une identité nommée deux fois (la casse ne compte pas) — la seconde attribution échouerait à l'apply."
  }
}

# IDI1 (#546) : la lecture de Microsoft Graph, pour la garde des identités d'Entra ID (R2).
variable "graph_read_enabled" {
  description = "Les rôles d'application Microsoft Graph Application.Read.All et RoleManagement.Read.Directory pour l'identité d'Orodruin : la garde d'une identité d'Entra ID lit l'application, son principal, ses permissions et ses rôles d'annuaire (IDI1). Rien d'autre dans Graph — le contrat le relit dans son jeton. L'apply demande un az login Administrateur des rôles privilégiés (ou général). Défaut false."
  type        = bool
  default     = false
  nullable    = false
}

# ── R2b (#608) : les garde-fous de l'abonnement de test dédié de Stratus ────────────────────
# docs/design/stratus-cible.md, § 6 (gestes G5, G6, G7). Posés par l'opérateur (jamais une
# session), plan montré avant. Tout est VIDE/ÉTEINT par défaut : un apply normal d'Orodruin
# n'y touche pas (count 0, fournisseur stratus inerte). Le rôle fermé (G3), l'AUTHZ_READ_ONLY
# d'Orodruin (G4) et le credential fédéré (G2) sont posés par R2BGc (M1 mesuré) : ils s'ARMENT en
# renseignant stratus_principal_id (G3) et stratus_client_id (G2) — vides, le squelette existe
# sans attribution ni confiance. Valeurs réelles jamais dans le dépôt — en variables, à l'apply.
variable "stratus_guardrails_enabled" {
  description = "Pose les garde-fous de l'abonnement de test dédié de Stratus : les caps Azure Policy (G5), le paramètre de diagnostic (G6), le budget (G7), le rôle fermé de Stratus (G3, sa définition) et l'AUTHZ_READ_ONLY d'Orodruin (G4). Défaut false : rien ne s'exécute. Le rôle fermé ne s'ATTRIBUE à Stratus que si stratus_principal_id est donné ; le credential fédéré (G2) ne se pose que si stratus_client_id est donné."
  type        = bool
  default     = false
  nullable    = false
}

variable "stratus_subscription_id" {
  description = "L'abonnement de test dédié de Stratus — vide par défaut, jamais en dur dans le dépôt public. Ici, une precondition (terraform_data.stratus_guard) refuse déjà qu'il vaille l'abonnement d'Orodruin. Le contrat (eregion_core/orodruin.py) le refusera EN PLUS (R2c) s'il vaut le banc, la VM ou Imladris — ce refus-là n'existe pas encore."
  type        = string
  default     = ""

  # Un GUID nu, jamais la forme chemin « /subscriptions/<guid> » : sans ce contrôle, l'abonnement
  # d'Orodruin écrit en chemin contournerait la precondition (qui compare des chaînes brutes).
  validation {
    condition     = var.stratus_subscription_id == "" || can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.stratus_subscription_id))
    error_message = "stratus_subscription_id : un GUID d'abonnement nu (sans « /subscriptions/ »), ou vide."
  }
}

variable "stratus_allowed_locations" {
  description = "G5 — régions autorisées sur l'abonnement dédié (policy intégrée « Allowed locations »). Vide (défaut) → la règle n'est pas posée (une liste vide refuserait TOUTE création). Rempli par l'opérateur à partir de la mesure M1."
  type        = list(string)
  default     = []
}

variable "stratus_allowed_resource_types" {
  description = "G5 — types de ressources autorisés (policy intégrée « Allowed resource types »). Vide (défaut) → non posée. Doit inclure Microsoft.Network/bastionHosts ET Microsoft.Network/publicIPAddresses (le Bastion et son IP publique, pour le lien partageable). Rempli depuis les besoins connus des techniques."
  type        = list(string)
  default     = []
}

variable "stratus_allowed_vm_skus" {
  description = "G5 — SKU de VM autorisés (policy intégrée « Allowed virtual machine size SKUs », qui ne vise que VM/VMSS — pas le Bastion, qui est un type de ressource, pas un SKU de VM). Vide (défaut) → non posée. Rempli depuis les SKU des VM de test."
  type        = list(string)
  default     = []
}

variable "stratus_bench_workspace_id" {
  description = "G6 — l'id complet du Log Analytics du banc (…/workspaces/<nom>), cible du paramètre de diagnostic de l'abonnement dédié (catégorie Administrative). Vide (défaut) → le paramètre n'est pas posé. Fourni par l'opérateur (p. ex. `terraform -chdir=infra/terraform output`), via un -var-file ou un *.auto.tfvars ; jamais en dur. Le workspace doit vivre pendant toute la mesure (il part avec celebrimbor-down)."
  type        = string
  default     = ""
}

variable "stratus_monthly_budget" {
  description = "G7 — plafond du budget mensuel de l'abonnement dédié, en devise du compte. 0 (défaut) → pas de budget. Le budget est une NOTIFICATION, évaluée avec 8–24 h de retard — ce n'est pas un plafond temps réel (le vrai plafond est l'Azure Policy G5)."
  type        = number
  default     = 0

  validation {
    condition     = var.stratus_monthly_budget >= 0
    error_message = "stratus_monthly_budget : un montant positif, ou 0 pour ne pas poser de budget."
  }
}

variable "stratus_budget_start_date" {
  description = "G7 — début de la période du budget, au format AAAA-MM-01T00:00:00Z (le 1er d'un mois présent ou à venir, exigé par Azure). Vide (défaut) → pas de budget. L'opérateur le règle à l'apply."
  type        = string
  default     = ""

  validation {
    condition     = var.stratus_budget_start_date == "" || can(regex("^[0-9]{4}-[0-9]{2}-01T00:00:00Z$", var.stratus_budget_start_date))
    error_message = "stratus_budget_start_date : AAAA-MM-01T00:00:00Z (le 1er d'un mois), ou vide."
  }
}

variable "stratus_budget_contact_emails" {
  description = "G7 — adresses prévenues par le groupe d'action du budget. Le groupe d'action vit HORS de l'abonnement dédié (dans le groupe d'Orodruin), pour que COLD/kill et « vider l'abonnement » ne le touchent pas. Vide (défaut) : le groupe d'action est posé sans destinataire (à compléter)."
  type        = list(string)
  default     = []
}

# ── R2BGc (#608) — l'identité de Stratus : à qui le rôle fermé (G3) est attribué, et depuis qui on
#    devient Stratus (G2). Vides par défaut : le squelette existe sans attribution ni confiance.

variable "stratus_principal_id" {
  description = "G3 — l'object id du principal de service de l'identité DÉDIÉE de Stratus (jamais son client id), à qui le rôle fermé (les actions minimales mesurées) est attribué sur l'abonnement dédié seulement. Vide (défaut) : le rôle est DÉFINI mais non attribué. Valeur réelle jamais dans le dépôt."
  type        = string
  default     = ""

  validation {
    condition     = var.stratus_principal_id == "" || can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.stratus_principal_id))
    error_message = "stratus_principal_id : un object id d'Entra ID (un GUID), ou vide."
  }
}

variable "stratus_client_id" {
  description = "G2 — le client id (application id) de l'app DÉDIÉE de Stratus, pour poser le credential fédéré qui fait confiance à l'identité managée d'Orodruin (on ne devient Stratus que depuis Orodruin). Vide (défaut) : pas de credential fédéré. L'id de RESSOURCE de l'app (/applications/<object id>) est lu par data.azuread_application, jamais écrit en dur. Valeur réelle jamais dans le dépôt."
  type        = string
  default     = ""

  validation {
    condition     = var.stratus_client_id == "" || can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.stratus_client_id))
    error_message = "stratus_client_id : un client id d'Entra ID (un GUID), ou vide."
  }
}
