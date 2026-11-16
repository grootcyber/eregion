# R2BG (#608) — les garde-fous de l'abonnement de test dédié de Stratus (stratus_guardrails.tf),
# éprouvés par un VRAI plan : inertes par défaut (zéro ressource, sorties nulles), et la
# precondition qui refuse de viser l'abonnement d'Orodruin fait échouer le plan. Contre de faux
# fournisseurs, aucun appel à Azure ; tous les identifiants sont des exemples.
# À la main :
#   terraform -chdir=infra/orodruin init -backend=false -lockfile=readonly
#   terraform -chdir=infra/orodruin test
# tests/unit/test_stratus_guardrails.py tient le même contrat en lisant le fichier.

mock_provider "azurerm" {
  mock_data "azurerm_resource_group" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor"
    }
  }
  mock_data "azurerm_log_analytics_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.OperationalInsights/workspaces/law-celebrimbor"
    }
  }
  mock_data "azurerm_subscription" {
    defaults = {
      id              = "/subscriptions/00000000-0000-0000-0000-000000000000"
      subscription_id = "00000000-0000-0000-0000-000000000000"
      tenant_id       = "00000000-0000-0000-0000-0000000000f0"
    }
  }
  mock_data "azurerm_client_config" {
    defaults = {
      object_id = "00000000-0000-0000-0000-0000000000ee"
    }
  }
}

# Le fournisseur aliasé des garde-fous : sans ce faux, Terraform configurerait le vrai.
mock_provider "azurerm" {
  alias = "stratus"
}

mock_provider "azuread" {}

override_resource {
  target          = azurerm_storage_container.exercises
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Storage/storageAccounts/storodruinexample/blobServices/default/containers/exercises"
  }
}

override_resource {
  target          = azurerm_storage_container.watch
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Storage/storageAccounts/storodruinexample/blobServices/default/containers/watch"
  }
}

override_resource {
  target          = azurerm_linux_virtual_machine.host
  override_during = plan
  values = {
    id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Compute/virtualMachines/vm-orodruin"
    identity = { principal_id = "00000000-0000-0000-0000-0000000000a0", tenant_id = "00000000-0000-0000-0000-0000000000f0" }
  }
}

variables {
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
  watch_principal_id   = "00000000-0000-0000-0000-0000000000b0"
  watch_subnet_id      = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-glorfindel/providers/Microsoft.Network/virtualNetworks/vnet-glorfindel/subnets/snet-glorfindel"
  graph_read_enabled   = false
}

# Par défaut : aucun garde-fou posé, les sorties nulles. Un apply normal d'Orodruin n'y touche pas.
run "off_by_default_poses_nothing" {
  command = plan

  assert {
    condition     = length(azurerm_policy_definition.stratus_deny_nic_public_ip) == 0 && length(azurerm_subscription_policy_assignment.stratus_deny_nic_public_ip) == 0
    error_message = "éteint, un refus d'IP publique est posé"
  }
  assert {
    condition     = length(azurerm_subscription_policy_assignment.stratus_allowed_locations) == 0 && length(azurerm_subscription_policy_assignment.stratus_allowed_resource_types) == 0 && length(azurerm_subscription_policy_assignment.stratus_allowed_vm_skus) == 0
    error_message = "éteint, une policy de liste autorisée est posée"
  }
  assert {
    condition     = length(azurerm_monitor_diagnostic_setting.stratus_activity_log) == 0 && length(azurerm_consumption_budget_subscription.stratus) == 0 && length(azurerm_monitor_action_group.stratus_budget) == 0
    error_message = "éteint, un paramètre de diagnostic, un budget ou un groupe d'action est posé"
  }
  assert {
    condition     = output.stratus_diagnostic_setting_id == null && output.stratus_budget_action_group_id == null && length(output.stratus_policy_assignment_ids) == 0
    error_message = "éteint, une sortie des garde-fous n'est pas nulle"
  }
}

# La precondition refuse de viser l'abonnement d'Orodruin (ici l'abonnement du faux) : le plan
# échoue — un `check` n'aurait fait qu'avertir.
run "refuses_orodruins_own_subscription" {
  command = plan

  variables {
    stratus_guardrails_enabled = true
    stratus_subscription_id    = "00000000-0000-0000-0000-000000000000"
  }

  expect_failures = [
    terraform_data.stratus_guard,
  ]
}

# La forme chemin « /subscriptions/<guid> » est refusée à la validation de la variable : sans ce
# refus, l'abonnement d'Orodruin écrit en chemin contournerait la precondition (comparaison brute).
run "refuses_the_subscription_id_in_path_form" {
  command = plan

  variables {
    stratus_guardrails_enabled = true
    stratus_subscription_id    = "/subscriptions/00000000-0000-0000-0000-000000000000"
  }

  expect_failures = [
    var.stratus_subscription_id,
  ]
}

# Activé sur un abonnement DÉDIÉ (distinct) : les garde-fous se posent, chacun une fois —
# l'inverse exact du défaut (on asserte les comptes ; les ids de sortie ne sont connus qu'après apply).
run "a_dedicated_subscription_poses_each_guardrail" {
  command = plan

  variables {
    stratus_guardrails_enabled = true
    stratus_subscription_id    = "11111111-1111-1111-1111-111111111111"
    stratus_bench_workspace_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.OperationalInsights/workspaces/law-celebrimbor"
    stratus_monthly_budget     = 100
    stratus_budget_start_date  = "2026-12-01T00:00:00Z"
    stratus_allowed_locations  = ["francecentral"]
  }

  assert {
    condition     = length(azurerm_policy_definition.stratus_deny_nic_public_ip) == 1 && length(azurerm_subscription_policy_assignment.stratus_deny_nic_public_ip) == 1
    error_message = "activé, le refus d'IP publique sur une NIC n'est pas posé"
  }
  # La règle décodée (jsonencode de constantes, connue au plan) : « au moins une ipConfig » est
  # bien un not{ … notLike « * » } en deny — sans l'enveloppe not, la policy serait inversée.
  assert {
    condition     = jsondecode(azurerm_policy_definition.stratus_deny_nic_public_ip[0].policy_rule).if.allOf[1].not.notLike == "*" && jsondecode(azurerm_policy_definition.stratus_deny_nic_public_ip[0].policy_rule).then.effect == "deny"
    error_message = "le refus d'IP publique n'est pas un not{ … notLike « * » } en deny (la policy serait inversée)"
  }
  assert {
    condition     = length(azurerm_subscription_policy_assignment.stratus_allowed_locations) == 1
    error_message = "activé avec une liste de régions, la policy de régions n'est pas posée"
  }
  assert {
    condition     = length(azurerm_monitor_diagnostic_setting.stratus_activity_log) == 1 && length(azurerm_consumption_budget_subscription.stratus) == 1 && length(azurerm_monitor_action_group.stratus_budget) == 1
    error_message = "activé, le diagnostic, le budget ou son groupe d'action n'est pas posé"
  }
  # Les listes vides restent non posées (une liste vide en deny refuserait tout).
  assert {
    condition     = length(azurerm_subscription_policy_assignment.stratus_allowed_resource_types) == 0 && length(azurerm_subscription_policy_assignment.stratus_allowed_vm_skus) == 0
    error_message = "une liste autorisée vide a quand même posé sa policy"
  }
}
