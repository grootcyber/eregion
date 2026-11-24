# FS1g (#1127) : l'application de l'exécuteur de restore — son principal, « Eregion Glorfindel
# Restore » sur le seul groupe du banc (et celui du coffre s'il est distinct), son object id parmi
# les principaux qui restaurent (Restore Neutralize par VM de restore_vms, Restore Staging sur le
# seul compte de transit), la partie publique de son certificat — désactivée par défaut. Planifiée
# contre de faux azurerm et azuread, aucun appel à Azure ni à Graph ; tous les identifiants sont des
# exemples. À la main :
#   terraform -chdir=infra/glorfindel-host init -backend=false -lockfile=readonly
#   terraform -chdir=infra/glorfindel-host test
# tests/unit/test_restore_executor.py tient le même contrat en lisant les fichiers.

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
  mock_data "azurerm_resources" {
    defaults = {
      resources = [{
        id                  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborstaging"
        name                = "stcelebrimborstaging"
        type                = "Microsoft.Storage/storageAccounts"
        resource_group_name = "rg-celebrimbor"
        location            = "westeurope"
        tags                = {}
      }]
    }
  }
}

mock_provider "azuread" {}

# Le principal de l'exécuteur, connu dès le plan (un exemple).
override_resource {
  target          = azuread_service_principal.restore_executor
  override_during = plan
  values = {
    object_id = "bbbbbbbb-0000-0000-0000-0000000000e1"
  }
}

override_data {
  target = data.azurerm_virtual_machine.session_drain["vm-celebrimbor-gondolin"]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
  }
}

override_data {
  target = data.azurerm_virtual_machine.session_drain["vm-celebrimbor-bree"]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-bree"
  }
}

override_data {
  target = data.azurerm_virtual_machine.restore["vm-celebrimbor-gondolin"]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
  }
}

override_data {
  target = data.azurerm_virtual_machine.restore["vm-celebrimbor-bree"]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-bree"
  }
}

override_data {
  target = data.azurerm_resource_group.restore_vault[0]
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-vault"
  }
}

variables {
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
  restore_principals = {
    console = "aaaaaaaa-0000-0000-0000-000000000001"
  }
}

run "off_by_default_nothing_is_created" {
  command = plan

  assert {
    condition     = length(azuread_application.restore_executor) == 0 && length(azuread_service_principal.restore_executor) == 0 && length(azuread_application_certificate.restore_executor) == 0
    error_message = "éteint, l'application de l'exécuteur de restore est quand même créée"
  }
  assert {
    condition     = length(azurerm_role_assignment.restore_executor_restore) == 0
    error_message = "éteint, le rôle Restore est quand même attribué"
  }
  assert {
    condition     = toset(keys(azurerm_role_assignment.restore_neutralize)) == toset(["console/vm-celebrimbor-gondolin", "console/vm-celebrimbor-bree"]) && toset(keys(azurerm_role_assignment.restore_staging)) == toset(["console"])
    error_message = "éteint, l'exécuteur figure parmi les principaux qui restaurent"
  }
  assert {
    condition     = output.restore_executor_client_id == "" && output.restore_executor_object_id == ""
    error_message = "éteint, les sorties nomment un exécuteur"
  }
}

run "on_restore_on_the_bench_group_alone" {
  command = plan

  variables {
    restore_executor_enabled = true
  }

  assert {
    condition     = length(azuread_application.restore_executor) == 1 && azuread_application.restore_executor[0].sign_in_audience == "AzureADMyOrg"
    error_message = "allumé, l'application n'est pas une application mono-tenant"
  }
  assert {
    condition     = toset(keys(azurerm_role_assignment.restore_executor_restore)) == toset(["bench"])
    error_message = "le rôle Restore ne va pas au seul groupe du banc"
  }
  assert {
    condition     = azurerm_role_assignment.restore_executor_restore["bench"].scope == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor" && azurerm_role_assignment.restore_executor_restore["bench"].role_definition_name == "Eregion Glorfindel Restore" && azurerm_role_assignment.restore_executor_restore["bench"].principal_id == "bbbbbbbb-0000-0000-0000-0000000000e1"
    error_message = "le rôle Restore n'est pas « Eregion Glorfindel Restore », au groupe du banc, au principal de l'exécuteur"
  }
  assert {
    condition     = toset([for k, a in azurerm_role_assignment.restore_neutralize : k if a.principal_id == "bbbbbbbb-0000-0000-0000-0000000000e1"]) == toset(["executor/vm-celebrimbor-gondolin", "executor/vm-celebrimbor-bree"])
    error_message = "la neutralisation ne va pas à l'exécuteur sur chaque VM de restore_vms"
  }
  assert {
    condition     = alltrue([for k, a in azurerm_role_assignment.restore_neutralize : endswith(a.scope, "/virtualMachines/${split("/", k)[1]}") && a.role_definition_name == "Eregion Glorfindel Restore Neutralize"])
    error_message = "la neutralisation de l'exécuteur n'est pas à la portée de chaque VM"
  }
  assert {
    condition     = azurerm_role_assignment.restore_staging["executor"].principal_id == "bbbbbbbb-0000-0000-0000-0000000000e1" && endswith(azurerm_role_assignment.restore_staging["executor"].scope, "/storageAccounts/stcelebrimborstaging") && azurerm_role_assignment.restore_staging["executor"].role_definition_name == "Eregion Glorfindel Restore Staging"
    error_message = "Restore Staging ne va pas à l'exécuteur sur le seul compte de transit"
  }
  assert {
    condition     = length(azuread_application_certificate.restore_executor) == 0
    error_message = "un certificat est posé sans sa partie publique"
  }
  assert {
    condition     = toset(keys(azurerm_role_assignment.restore_neutralize)) == toset(["console/vm-celebrimbor-gondolin", "console/vm-celebrimbor-bree", "executor/vm-celebrimbor-gondolin", "executor/vm-celebrimbor-bree"])
    error_message = "l'exécuteur a remplacé les principaux du poste, ou en a ajouté d'autres"
  }
}

run "on_with_a_distinct_vault_group_restore_there_too" {
  command = plan

  variables {
    restore_executor_enabled     = true
    restore_vault_resource_group = "rg-vault"
  }

  assert {
    condition     = toset(keys(azurerm_role_assignment.restore_executor_restore)) == toset(["bench", "vault"])
    error_message = "le rôle Restore ne va pas au groupe du banc et à celui du coffre"
  }
  assert {
    condition     = azurerm_role_assignment.restore_executor_restore["vault"].scope == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-vault"
    error_message = "le rôle Restore n'est pas au groupe du coffre"
  }
}

run "a_vault_group_that_is_the_benchs_gives_one_assignment" {
  command = plan

  variables {
    restore_executor_enabled     = true
    restore_vault_resource_group = "RG-Celebrimbor"
  }

  assert {
    condition     = toset(keys(azurerm_role_assignment.restore_executor_restore)) == toset(["bench"]) && length(data.azurerm_resource_group.restore_vault) == 0
    error_message = "le groupe du banc, nommé comme coffre, donne deux attributions"
  }
}

run "the_certificates_public_part_alone" {
  command = plan

  variables {
    restore_executor_enabled     = true
    restore_executor_certificate = "-----BEGIN CERTIFICATE-----\nMIIBexample\n-----END CERTIFICATE-----\n"
  }

  assert {
    condition     = length(azuread_application_certificate.restore_executor) == 1 && azuread_application_certificate.restore_executor[0].type == "AsymmetricX509Cert"
    error_message = "la partie publique du certificat n'est pas posée"
  }
}

run "a_private_key_is_refused" {
  command = plan

  variables {
    restore_executor_enabled     = true
    restore_executor_certificate = "-----BEGIN CERTIFICATE-----\nx\n-----END CERTIFICATE-----\n-----BEGIN PRIVATE KEY-----\ny\n-----END PRIVATE KEY-----\n"
  }

  expect_failures = [var.restore_executor_certificate]
}

run "a_path_for_the_vault_group_is_refused" {
  command = plan

  variables {
    restore_vault_resource_group = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-vault"
  }

  expect_failures = [var.restore_vault_resource_group]
}
