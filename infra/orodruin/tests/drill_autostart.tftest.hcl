# DRL1c (#613, docs/design/drill-banc.md §5.1, §11) : le démarrage planifié du drill de la semaine, et
# l'extinction de 23:00 UTC (drill_autostart.tf, drill_autostart.json).
# - la Logic App créée Disabled, par le modèle même (Terraform ne relit jamais son état) ;
# - son seul déclencheur, une Recurrence hebdomadaire en UTC, à l'heure de drill_autostart_at ;
# - son rôle : une seule action, start/action, assignable dans le groupe d'Orodruin, attribué à la VM
#   d'Orodruin seule, à l'identité que le déploiement rend ;
# - l'extinction quotidienne, 23:00 UTC ; la sortie drill_autostart_id, au contrat de DRL1a.
# Planifié contre un faux azurerm, aucun appel à Azure ; tous les identifiants sont des exemples. À la main :
#   terraform -chdir=infra/orodruin init -backend=false -lockfile=readonly
#   terraform -chdir=infra/orodruin test -filter=tests/drill_autostart.tftest.hcl

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
    }
  }
  mock_data "azurerm_client_config" {
    defaults = {
      object_id = "00000000-0000-0000-0000-0000000000ee"
    }
  }
}

mock_provider "azurerm" {
  alias = "stratus"
}

mock_provider "azuread" {}

override_resource {
  target          = azurerm_resource_group.host
  override_during = plan
  values = {
    id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin"
    location = "francecentral"
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

# Ce que rendrait le déploiement (ses sorties workflowId et principalId), un exemple.
override_resource {
  target          = azurerm_resource_group_template_deployment.drill_autostart
  override_during = plan
  values = {
    output_content = "{\"workflowId\":{\"type\":\"String\",\"value\":\"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Logic/workflows/logic-orodruin-drill\"},\"principalId\":{\"type\":\"String\",\"value\":\"00000000-0000-0000-0000-0000000000c0\"}}"
  }
}

variables {
  # Une clé jetable (celle du test d'ID1 : sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  operator_cidr        = "203.0.113.7/32"
}

run "the_scheduled_start_is_created_disabled_on_its_one_weekly_trigger" {
  command = plan

  assert {
    condition     = length(jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources) == 1
    error_message = "le modèle du démarrage planifié pose autre chose que la Logic App"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].type == "Microsoft.Logic/workflows"
    error_message = "le démarrage planifié n'est pas un Microsoft.Logic/workflows"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.state == "Disabled"
    error_message = "la Logic App n'est pas créée Disabled : un apply la réveillerait sans armement"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].identity.type == "SystemAssigned"
    error_message = "la Logic App n'a pas sa propre identité managée"
  }
  assert {
    condition     = keys(jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.definition.triggers) == ["weekly"]
    error_message = "la Logic App n'a pas un seul déclencheur"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.definition.triggers.weekly.type == "Recurrence"
    error_message = "son déclencheur n'est pas une Recurrence"
  }
  assert {
    condition = (
      jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.definition.triggers.weekly.recurrence.frequency == "Week"
      && jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.definition.triggers.weekly.recurrence.interval == 1
      && jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.definition.triggers.weekly.recurrence.timeZone == "UTC"
    )
    error_message = "sa récurrence n'est pas hebdomadaire, toutes les semaines, en UTC"
  }
  # DRL1f (#963) : en UTC, Azure exige un startTime « yyyy-MM-ddTHH:mm:ssZ » (InvalidWorkflowTriggerRecurrence
  # au banc le 20/11) ; ce faux azurerm ne déploie rien et ne le verrait pas.
  assert {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$", jsondecode(azurerm_resource_group_template_deployment.drill_autostart.template_content).resources[0].properties.definition.triggers.weekly.recurrence.startTime))
    error_message = "son startTime n'est pas « yyyy-MM-ddTHH:mm:ssZ » : Azure refuse le modèle en UTC sans le Z"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).weekDay.value == "Tuesday"
    error_message = "le démarrage planifié ne tombe pas le mardi"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).hour.value == 18 && jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).minute.value == 40
    error_message = "le démarrage planifié n'est pas à 18:40 UTC (le drill de 19:00 moins 20 min)"
  }
  assert {
    condition     = jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).vmId.value == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Compute/virtualMachines/vm-orodruin"
    error_message = "la Logic App ne démarre pas la VM d'Orodruin"
  }
  assert {
    condition     = output.drill_autostart_id == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Logic/workflows/logic-orodruin-drill"
    error_message = "la sortie drill_autostart_id n'est pas l'id de la Logic App"
  }
}

run "its_hour_comes_from_drill_autostart_at" {
  command = plan
  variables {
    drill_autostart_at = "sun 00:05"
  }

  assert {
    condition = (
      jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).weekDay.value == "Sunday"
      && jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).hour.value == 0
      && jsondecode(azurerm_resource_group_template_deployment.drill_autostart.parameters_content).minute.value == 5
    )
    error_message = "l'heure du démarrage planifié n'est pas celle de drill_autostart_at"
  }
}

run "an_hour_that_is_not_one_is_refused" {
  command = plan
  variables {
    drill_autostart_at = "tue 24:00"
  }
  expect_failures = [var.drill_autostart_at]
}

run "a_day_spelled_out_is_refused" {
  command = plan
  variables {
    drill_autostart_at = "Tuesday 18:40"
  }
  expect_failures = [var.drill_autostart_at]
}

run "an_hour_without_its_day_is_refused" {
  command = plan
  variables {
    drill_autostart_at = "18:40"
  }
  expect_failures = [var.drill_autostart_at]
}

run "its_role_starts_orodruin_and_nothing_else" {
  command = plan

  assert {
    condition     = tolist(azurerm_role_definition.drill_autostart.permissions[0].actions) == tolist(["Microsoft.Compute/virtualMachines/start/action"])
    error_message = "le rôle du démarrage planifié porte autre chose que start/action"
  }
  assert {
    condition     = length(coalesce(azurerm_role_definition.drill_autostart.permissions[0].not_actions, [])) == 0 && length(coalesce(azurerm_role_definition.drill_autostart.permissions[0].data_actions, [])) == 0
    error_message = "le rôle du démarrage planifié porte autre chose que start/action"
  }
  assert {
    condition     = tolist(azurerm_role_definition.drill_autostart.assignable_scopes) == tolist(["/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin"])
    error_message = "le rôle du démarrage planifié est assignable ailleurs que dans le groupe d'Orodruin"
  }
  assert {
    condition     = azurerm_role_assignment.drill_autostart.scope == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Compute/virtualMachines/vm-orodruin"
    error_message = "le rôle du démarrage planifié n'est pas attribué à la portée de la VM d'Orodruin seule"
  }
  assert {
    condition     = azurerm_role_assignment.drill_autostart.principal_id == "00000000-0000-0000-0000-0000000000c0"
    error_message = "le rôle du démarrage planifié n'est pas attribué à l'identité de la Logic App"
  }
}

run "orodruin_is_shut_down_every_day_at_23_utc" {
  command = plan

  assert {
    condition     = azurerm_dev_test_global_vm_shutdown_schedule.host.enabled && azurerm_dev_test_global_vm_shutdown_schedule.host.daily_recurrence_time == "2300" && azurerm_dev_test_global_vm_shutdown_schedule.host.timezone == "UTC"
    error_message = "Orodruin ne s'éteint pas chaque jour à 23:00 UTC"
  }
  assert {
    condition     = azurerm_dev_test_global_vm_shutdown_schedule.host.virtual_machine_id == "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-orodruin/providers/Microsoft.Compute/virtualMachines/vm-orodruin"
    error_message = "l'extinction de 23:00 UTC ne vise pas la VM d'Orodruin"
  }
}
