# LOGF2 (#1233) : la watch d'Imladris lit le journal d'audit d'Entra ID — AuditLog.Read.All de Microsoft
# Graph, attribué à l'identité managée de la VM, désactivé par défaut. Planifié contre de faux azurerm et
# azuread, aucun appel à Azure ni à Graph ; tous les identifiants sont des exemples. La CI le lance avec
# le reste du dossier (ci.yml, job terraform-test) ; à la main :
#   terraform -chdir=infra/glorfindel-host init -backend=false -lockfile=readonly
#   terraform -chdir=infra/glorfindel-host test -filter=tests/watch_audit_log.tftest.hcl
# tests/unit/test_entra_freshness.py tient le même contrat en lisant les fichiers.

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

# Microsoft Graph tel que le tenant le publie : son principal et quelques-uns de ses rôles
# d'application, lectures larges et écritures comprises — la watch ne doit en prendre qu'un.
mock_provider "azuread" {
  mock_data "azuread_application_published_app_ids" {
    defaults = {
      result = { MicrosoftGraph = "00000000-0000-0000-0000-0000000000a9" }
    }
  }
  mock_data "azuread_service_principal" {
    defaults = {
      object_id = "00000000-0000-0000-0000-0000000000a8"
      app_role_ids = {
        "AuditLog.Read.All"                  = "00000000-0000-0000-0000-0000000000c1"
        "Directory.Read.All"                 = "00000000-0000-0000-0000-0000000000c2"
        "User.Read.All"                      = "00000000-0000-0000-0000-0000000000c3"
        "Application.ReadWrite.OwnedBy"      = "00000000-0000-0000-0000-0000000000d1"
        "User.RevokeSessions.All"            = "00000000-0000-0000-0000-0000000000d2"
        "RoleManagement.ReadWrite.Directory" = "00000000-0000-0000-0000-0000000000d4"
      }
    }
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
  # Hermétique face à un watch_audit_log.auto.tfvars ou un identity_executor.auto.tfvars de l'opérateur.
  watch_audit_log_read_enabled = false
  identity_executor_enabled    = false
}

run "by_default_nothing_in_the_tenant" {
  command = plan

  assert {
    condition     = length(azuread_app_role_assignment.watch_audit_log) == 0
    error_message = "par défaut, une permission de Graph est donnée à la watch"
  }
  assert {
    condition     = length(data.azuread_service_principal.watch_audit_log_msgraph) == 0 && length(data.azuread_application_published_app_ids.watch_audit_log) == 0
    error_message = "désactivé, le tenant est lu quand même"
  }
  assert {
    condition     = length(output.watch_audit_log_read) == 0
    error_message = "désactivé, la sortie dit une permission"
  }
}

run "enabled_audit_log_read_all_alone_to_the_vms_identity" {
  command = plan

  variables {
    watch_audit_log_read_enabled = true
  }

  assert {
    condition     = toset(keys(azuread_app_role_assignment.watch_audit_log)) == toset(["AuditLog.Read.All"])
    error_message = "activé, la watch ne reçoit pas exactement AuditLog.Read.All"
  }
  assert {
    condition     = toset([for a in azuread_app_role_assignment.watch_audit_log : a.app_role_id]) == toset(["00000000-0000-0000-0000-0000000000c1"])
    error_message = "la permission donnée n'est pas AuditLog.Read.All (une lecture plus large, une écriture)"
  }
  assert {
    condition     = alltrue([for a in azuread_app_role_assignment.watch_audit_log : a.principal_object_id == "00000000-0000-0000-0000-0000000000b1"])
    error_message = "la permission va à une autre identité que celle de la VM d'Imladris (la watch)"
  }
  assert {
    condition     = alltrue([for a in azuread_app_role_assignment.watch_audit_log : a.resource_object_id == "00000000-0000-0000-0000-0000000000a8"])
    error_message = "la permission est prise sur un autre principal que Microsoft Graph"
  }
  assert {
    condition     = join(",", output.watch_audit_log_read) == "AuditLog.Read.All"
    error_message = "la sortie ne dit pas la permission attribuée"
  }
  # Rien de l'exécuteur d'identité n'est créé avec elle : deux drapeaux, deux décisions.
  assert {
    condition     = length(azuread_app_role_assignment.identity_executor) == 0 && length(azuread_application.identity_executor) == 0
    error_message = "activer la lecture du journal d'audit crée l'exécuteur d'identité"
  }
}
