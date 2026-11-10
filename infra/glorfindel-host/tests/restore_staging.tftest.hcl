# RST1 : les clés du compte de transit du restore (listKeys, le droit lié qu'un restore vérifie là),
# sur le seul compte restore_staging_storage, pour chaque principal qui restaure (restore_principals)
# — planifiées contre un faux azurerm, aucun appel à Azure. La CI le lance à chaque PR (ci.yml, job
# terraform-test, avec le reste du dossier tests/) ; à la main :
#   terraform -chdir=infra/glorfindel-host init -backend=false -lockfile=readonly
#   terraform -chdir=infra/glorfindel-host test
# Les cas : le compte du dépôt (restore.auto.tfvars) ; une attribution par principal, à la portée du
# compte, jamais au groupe, jamais à l'identité de H0 ; sans principal ou sans compte, rien ; le
# compte cherché dans le groupe du banc ; un chemin ou un nom qui n'est pas celui d'un compte, refusé.
# tests/unit/test_glorfindel_host.py tient le même contrat en lisant les fichiers.

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
  mock_data "azurerm_storage_account" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborstaging"
    }
  }
  # Les VM de restore_vms et session_drain_vms : une portée qu'azurerm sait lire (un id au hasard
  # échoue au plan) ; ces attributions ont leurs propres tests.
  mock_data "azurerm_virtual_machine" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
    }
  }
}

# IR1b : le module lit azuread (identity_executor.tf, désactivé) : un faux, jamais Graph.
mock_provider "azuread" {}

variables {
  # Une clé jetable (celle du test d'ID1 : sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
  # Deux principaux d'exemple (aucun réel) : la console et le bot.
  restore_principals = {
    console = "aaaaaaaa-0000-0000-0000-000000000001"
    bot     = "aaaaaaaa-0000-0000-0000-000000000002"
  }
}

run "the_repositorys_staging_account_gets_the_keys_right_for_each_principal" {
  command = plan

  assert {
    condition     = var.restore_staging_storage == "stcelebrimborstaging"
    error_message = "restore.auto.tfvars ne nomme pas le compte de transit du banc"
  }
  assert {
    condition     = toset(keys(azurerm_role_assignment.restore_staging)) == toset(["bot", "console"])
    error_message = "les clés du compte de transit ne vont pas à la console et au bot"
  }
  assert {
    condition     = alltrue([for a in azurerm_role_assignment.restore_staging : a.scope == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborstaging"])
    error_message = "les clés ne sont pas attribuées à la portée du seul compte de transit"
  }
  assert {
    condition     = alltrue([for a in azurerm_role_assignment.restore_staging : a.scope != data.azurerm_resource_group.bench.id])
    error_message = "les clés sont attribuées sur tout le groupe du banc"
  }
  assert {
    condition     = alltrue([for a in azurerm_role_assignment.restore_staging : a.role_definition_name == "Eregion Glorfindel Restore Staging" && a.principal_type == "ServicePrincipal"])
    error_message = "les clés ne sont pas le rôle « Eregion Glorfindel Restore Staging », à un principal de service"
  }
  assert {
    condition     = azurerm_role_assignment.restore_staging["console"].principal_id == "aaaaaaaa-0000-0000-0000-000000000001" && azurerm_role_assignment.restore_staging["bot"].principal_id == "aaaaaaaa-0000-0000-0000-000000000002"
    error_message = "les clés ne vont pas aux principaux qui restaurent"
  }
  assert {
    condition     = data.azurerm_storage_account.restore_staging[0].name == "stcelebrimborstaging" && data.azurerm_storage_account.restore_staging[0].resource_group_name == "rg-celebrimbor"
    error_message = "le compte de transit n'est pas cherché par son nom dans le groupe du banc"
  }
  # La neutralisation, elle, reste VM par VM : le compte de transit n'y change rien.
  assert {
    condition     = length(azurerm_role_assignment.restore_neutralize) == 4
    error_message = "le compte de transit a changé la neutralisation"
  }
}

run "without_a_principal_nothing_is_given" {
  command = plan

  variables {
    restore_principals = {}
  }

  assert {
    condition     = length(azurerm_role_assignment.restore_staging) == 0
    error_message = "sans principal qui restaure, les clés sont quand même attribuées"
  }
}

run "without_a_staging_account_nothing_is_read_nor_given" {
  command = plan

  variables {
    restore_staging_storage = ""
  }

  assert {
    condition     = length(azurerm_role_assignment.restore_staging) == 0 && length(data.azurerm_storage_account.restore_staging) == 0
    error_message = "sans compte de transit, un compte est lu ou des clés attribuées"
  }
}

run "h0_s_own_identity_never_gets_the_keys" {
  command = plan

  override_resource {
    target          = azurerm_linux_virtual_machine.host
    override_during = plan
    values = {
      identity = {
        type         = "SystemAssigned"
        principal_id = "11111111-1111-1111-1111-111111111111"
        tenant_id    = "22222222-2222-2222-2222-222222222222"
      }
    }
  }

  variables {
    restore_vms = []
    restore_principals = {
      console = "11111111-1111-1111-1111-111111111111"
    }
  }

  expect_failures = [azurerm_role_assignment.restore_staging]
}

run "a_path_for_the_staging_account_is_refused" {
  command = plan

  variables {
    restore_staging_storage = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborstaging"
  }

  expect_failures = [var.restore_staging_storage]
}

run "a_name_that_is_no_storage_account_s_is_refused" {
  command = plan

  variables {
    restore_staging_storage = "St-Celebrimbor"
  }

  expect_failures = [var.restore_staging_storage]
}
