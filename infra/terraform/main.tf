terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    # G1 : la cible Microsoft-Agent de Chaos Studio (chaos.tf), qu'azurerm ne sait pas déclarer.
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
    # IDI1 : l'identité de test du banc dans Entra ID (entra_identity.tf), désactivée par défaut.
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.5"
}

# subscription_id : jamais en dur (repo public). Résolu, dans l'ordre :
#   1. var.subscription_id (terraform.tfvars ou TF_VAR_subscription_id) ;
#   2. sinon null → le provider lit ARM_SUBSCRIPTION_ID de l'env.
# Le Makefile mappe l'AZURE_SUBSCRIPTION_ID de .envrc → ARM_SUBSCRIPTION_ID.
provider "azurerm" {
  # INF-FL (#654) : le compte des flux réseau refuse la clé partagée (storage.tf). Sans ce drapeau,
  # le provider lit les propriétés de file d'attente et de site statique de CHAQUE compte par le plan
  # de données, avec la clé (storage_use_azuread n'est pas posé) : un compte sans clé fait échouer
  # chaque plan (403 KeyBasedAuthenticationNotPermitted ; azurerm 4.81.0,
  # storage_account_resource.go, et le guide du bloc features). Aucun compte du module n'a
  # queue_properties ni static_website, ce à quoi le drapeau est destiné ; tout le reste passe par
  # Azure Resource Manager (les conteneurs par storage_account_id). Hypothèse à relire au plan :
  # aucun changement sur les comptes d'exfiltration et de transit.
  features {
    storage {
      data_plane_available = false
    }
  }
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}

provider "azapi" {
  subscription_id = var.subscription_id != "" ? var.subscription_id : null
}

# Le az login de l'opérateur, jamais un principal, lié au tenant de l'abonnement du banc : un az
# login posé sur un autre tenant n'écrit pas hors du banc, il échoue (relecture d'IDI1). Ne sert qu'à
# entra_identity.tf. La lecture de l'abonnement, sans count, ne change rien au plan : une lecture.
data "azurerm_subscription" "bench" {}

provider "azuread" {
  tenant_id = data.azurerm_subscription.bench.tenant_id
}

# Baseline resource group — porte le nom canonique sur le workspace "default",
# suffixé "-<instance>" sur tout autre workspace (stack éphémère).
#
# IDI1 : il nomme aussi l'identité de test du banc qu'il inscrit (eregion-identities,
# entra_identity.tf) — la clé ARM de l'inscription d'une identité ; sans l'identité, rien de plus.
resource "azurerm_resource_group" "celebrimbor" {
  name     = local.base_rg
  location = local.cfg.location
  tags     = merge(local.common_tags, local.identity_tags)
}
