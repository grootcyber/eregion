# PIO1 (#1258) : la watch d'Imladris lit en PromQL la métrique par processus de l'espace de travail
# Azure Monitor du banc — Monitoring Data Reader sur cet espace seul, pour l'identité managée de la VM,
# désactivé par défaut. Planifié contre de faux azurerm et azuread, aucun appel à Azure ; tous les
# identifiants sont des exemples. La CI le lance avec le reste du dossier (ci.yml, job terraform-test) ;
# à la main :
#   terraform -chdir=infra/glorfindel-host init -backend=false -lockfile=readonly
#   terraform -chdir=infra/glorfindel-host test -filter=tests/watch_process_io.tftest.hcl
# tests/unit/test_process_io.py tient le même contrat en lisant les fichiers.

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
  mock_data "azurerm_monitor_workspace" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Monitor/accounts/amw-celebrimbor"
    }
  }
  mock_data "azurerm_subscription" {
    defaults = {
      id        = "/subscriptions/00000000-0000-0000-0000-000000000000"
      tenant_id = "00000000-0000-0000-0000-0000000000f0"
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

# La VM d'Imladris, son identité managée telle qu'Azure la rendrait.
override_resource {
  target          = azurerm_linux_virtual_machine.host
  override_during = plan
  values = {
    identity = {
      principal_id = "00000000-0000-0000-0000-0000000000b1"
      tenant_id    = "00000000-0000-0000-0000-0000000000f0"
    }
  }
}

variables {
  # Une clé jetable (celle du test d'ID1 : sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
  # Hermétique face aux *.auto.tfvars de l'opérateur.
  watch_process_io_read_enabled = false
  watch_audit_log_read_enabled  = false
  identity_executor_enabled     = false
  restore_executor_enabled      = false
}

run "by_default_nothing_is_read_nor_given" {
  command = plan

  assert {
    condition     = length(azurerm_role_assignment.watch_process_io) == 0
    error_message = "par défaut, un rôle sur l'espace de travail Azure Monitor est donné à la watch"
  }
  assert {
    condition     = length(data.azurerm_monitor_workspace.bench) == 0
    error_message = "désactivé, l'espace de travail Azure Monitor du banc est lu quand même"
  }
  assert {
    condition     = output.watch_process_io_read == ""
    error_message = "désactivé, la sortie nomme un espace"
  }
}

run "enabled_monitoring_data_reader_on_the_workspace_alone_to_the_vms_identity" {
  command = plan

  variables {
    watch_process_io_read_enabled = true
  }

  assert {
    condition     = length(azurerm_role_assignment.watch_process_io) == 1 && azurerm_role_assignment.watch_process_io[0].role_definition_name == "Monitoring Data Reader"
    error_message = "activé, la watch ne reçoit pas exactement Monitoring Data Reader (une lecture plus large, une écriture)"
  }
  assert {
    condition     = azurerm_role_assignment.watch_process_io[0].scope == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Monitor/accounts/amw-celebrimbor"
    error_message = "le rôle est posé ailleurs que sur l'espace de travail Azure Monitor du banc (le groupe, l'abonnement)"
  }
  assert {
    condition     = azurerm_role_assignment.watch_process_io[0].principal_id == "00000000-0000-0000-0000-0000000000b1"
    error_message = "le rôle va à une autre identité que celle de la VM d'Imladris (la watch)"
  }
  assert {
    condition     = data.azurerm_monitor_workspace.bench[0].name == "amw-celebrimbor" && data.azurerm_monitor_workspace.bench[0].resource_group_name == "rg-celebrimbor"
    error_message = "l'espace relu n'est pas celui du banc, dans le groupe du banc"
  }
  assert {
    condition     = output.watch_process_io_read == azurerm_role_assignment.watch_process_io[0].scope
    error_message = "la sortie ne dit pas l'espace que la watch peut lire"
  }
  # Les droits de toujours ne changent pas : Reader sur le groupe, Log Analytics Reader sur le workspace.
  assert {
    condition     = azurerm_role_assignment.bench_reader.role_definition_name == "Reader" && azurerm_role_assignment.bench_logs_reader.role_definition_name == "Log Analytics Reader"
    error_message = "activer la lecture de l'espace change les droits de lecture du banc"
  }
  # Rien du tenant n'est créé avec lui : deux drapeaux, deux décisions.
  assert {
    condition     = length(azuread_app_role_assignment.watch_audit_log) == 0 && length(azuread_application.identity_executor) == 0
    error_message = "activer la lecture de l'espace donne une permission de Graph ou crée l'exécuteur d'identité"
  }
}
