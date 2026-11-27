# PIO1 (#1258) : qui écrit sous Linux — l'espace de travail Azure Monitor, la DCR à part de
# process.disk.io et leurs associations (process_io.tf), planifiés contre de faux azurerm, azapi, null
# et azuread : aucun appel à Azure. La CI le lance à chaque PR (ci.yml, job terraform-test, CI4) ; à la
# main :
#   terraform -chdir=infra/terraform init -backend=false -lockfile=readonly
#   terraform -chdir=infra/terraform test -filter=tests/process_io.tftest.hcl
# Deux cas : le drapeau à false (le défaut), dont le plan ne pose rien de PIO1 ; le drapeau à true, qui
# pose l'espace, une DCR qui ne collecte que process.disk.io vers lui, une association par VM du banc,
# et ne change pas la DCR de la règle. tests/unit/test_process_io.py tient le même contrat en lisant les
# fichiers.

mock_provider "azurerm" {
  # Monitoring Reader tel que l'abonnement le rendrait (l'identifiant du rôle intégré, Learn).
  mock_data "azurerm_role_definition" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/providers/Microsoft.Authorization/roleDefinitions/43d0d8ad-25c7-4714-9337-8ba259a9fe05"
    }
  }
  mock_resource "azurerm_monitor_workspace" {
    override_during = plan
    defaults = {
      id             = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Monitor/accounts/amw-celebrimbor"
      query_endpoint = "https://amw-celebrimbor-abcd.westus.prometheus.monitor.azure.com"
    }
  }
  mock_resource "azurerm_monitor_data_collection_rule" {
    override_during = plan
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Insights/dataCollectionRules/dcr-celebrimbor"
    }
  }
}
mock_provider "azapi" {}
mock_provider "null" {}
mock_provider "azuread" {}

variables {
  # La clé jetable du test d'ID1 (sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  # Hermétique face au terraform.tfvars de l'opérateur (qui peut les activer).
  activity_log_enabled        = false
  entra_logs_enabled          = false
  auditd_enabled              = false
  cron_logs_enabled           = false
  entra_test_identity_enabled = false
  entra_bench_unit_enabled    = false
  bench_reader_enabled        = false
  process_io_enabled          = false
}

run "off_nothing_of_pio1_is_planned" {
  command = plan

  assert {
    condition     = length(azurerm_monitor_workspace.process_io) + length(azapi_resource.process_io_dcr) + length(azurerm_monitor_data_collection_rule_association.process_io) + length(azurerm_role_assignment.process_io_operator_reader) + length(data.azurerm_role_definition.process_io_reader) == 0
    error_message = "une ressource de PIO1 est planifiée alors que process_io_enabled est à false"
  }
  assert {
    condition     = output.process_io_workspace_id == "" && output.process_io_query_endpoint == "" && output.process_io_workspace_name == ""
    error_message = "désactivé, une sortie de PIO1 nomme un espace"
  }
}

run "on_one_workspace_one_dcr_of_process_disk_io_every_bench_vm" {
  command = plan

  variables {
    process_io_enabled = true
  }

  # La DCR de PIO1 telle qu'Azure la nommerait (connue au plan : l'association la lit).
  override_resource {
    target          = azapi_resource.process_io_dcr
    override_during = plan
    values = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Insights/dataCollectionRules/dcr-celebrimbor-process-io"
    }
  }

  assert {
    condition     = length(azurerm_monitor_workspace.process_io) == 1 && azurerm_monitor_workspace.process_io[0].name == "amw-celebrimbor"
    error_message = "activé, l'espace de travail Azure Monitor du banc n'est pas planifié une fois, sous son nom"
  }
  assert {
    condition     = length(azapi_resource.process_io_dcr) == 1 && azapi_resource.process_io_dcr[0].type == "Microsoft.Insights/dataCollectionRules@2024-03-11"
    error_message = "la DCR de PIO1 n'est pas une DCR de l'API 2024-03-11 (la première qui porte performanceCountersOTel)"
  }
  assert {
    condition     = azapi_resource.process_io_dcr[0].name == "dcr-celebrimbor-process-io"
    error_message = "la DCR de PIO1 n'est pas une DCR à part (son nom est celui d'une autre)"
  }
  # Ce qu'elle collecte : process.disk.io, et rien d'autre, par le flux OpenTelemetry de l'invité.
  assert {
    condition     = azapi_resource.process_io_dcr[0].body.properties.dataSources.performanceCountersOTel[0].counterSpecifiers == ["process.disk.io"]
    error_message = "la DCR de PIO1 collecte autre chose que process.disk.io (chaque métrique se paie à l'échantillon)"
  }
  assert {
    condition     = azapi_resource.process_io_dcr[0].body.properties.dataSources.performanceCountersOTel[0].streams == ["Microsoft-OtelPerfMetrics"]
    error_message = "la source de PIO1 n'envoie pas le flux Microsoft-OtelPerfMetrics"
  }
  assert {
    condition     = keys(azapi_resource.process_io_dcr[0].body.properties.dataSources) == ["performanceCountersOTel"]
    error_message = "la DCR de PIO1 porte une autre source que performanceCountersOTel (Perf, Syslog : ceux de la DCR de la règle)"
  }
  # Où elle l'envoie : l'espace de travail Azure Monitor, jamais Log Analytics.
  assert {
    condition     = azapi_resource.process_io_dcr[0].body.properties.destinations.monitoringAccounts[0].accountResourceId == azurerm_monitor_workspace.process_io[0].id
    error_message = "la DCR de PIO1 n'envoie pas vers l'espace de travail Azure Monitor du banc"
  }
  assert {
    condition     = keys(azapi_resource.process_io_dcr[0].body.properties.destinations) == ["monitoringAccounts"]
    error_message = "la DCR de PIO1 a une autre destination que l'espace de travail Azure Monitor (Log Analytics)"
  }
  assert {
    condition = (length(azapi_resource.process_io_dcr[0].body.properties.dataFlows) == 1
      && azapi_resource.process_io_dcr[0].body.properties.dataFlows[0].streams == ["Microsoft-OtelPerfMetrics"]
    && azapi_resource.process_io_dcr[0].body.properties.dataFlows[0].destinations == ["amw-dest"])
    error_message = "le flux de PIO1 ne va pas de Microsoft-OtelPerfMetrics à l'espace, seul"
  }
  # Chaque VM du banc, et elles seules, associée à cette DCR.
  assert {
    condition     = keys(azurerm_monitor_data_collection_rule_association.process_io) == keys(azurerm_linux_virtual_machine.baseline)
    error_message = "la DCR de PIO1 n'est pas associée à chaque VM du banc, et à elles seules"
  }
  assert {
    condition = alltrue([for k, a in azurerm_monitor_data_collection_rule_association.process_io :
    a.data_collection_rule_id == azapi_resource.process_io_dcr[0].id && a.name == "dcra-celebrimbor-${k}-process-io"])
    error_message = "une association de PIO1 ne vise pas la DCR de PIO1, ou prend le nom de celle de la règle"
  }
  # La DCR de la règle reste intacte : ses flux, sa destination, ses associations.
  assert {
    condition     = toset(azurerm_monitor_data_collection_rule.celebrimbor.data_flow[0].streams) == toset(["Microsoft-Perf", "Microsoft-Syslog"])
    error_message = "la DCR de la règle change de flux avec PIO1"
  }
  assert {
    condition     = length(azurerm_monitor_data_collection_rule.celebrimbor.destinations[0].monitor_account) == 0
    error_message = "la DCR de la règle reçoit une destination Azure Monitor avec PIO1"
  }
  assert {
    condition = alltrue([for k, a in azurerm_monitor_data_collection_rule_association.vm :
    a.data_collection_rule_id == azurerm_monitor_data_collection_rule.celebrimbor.id])
    error_message = "les associations de la DCR de la règle changent avec PIO1"
  }
  assert {
    condition     = output.process_io_query_endpoint == "https://amw-celebrimbor-abcd.westus.prometheus.monitor.azure.com" && output.process_io_workspace_name == "amw-celebrimbor"
    error_message = "la sortie ne dit pas le point de requête PromQL ni le nom de l'espace"
  }
  # La lecture de l'opérateur (son az login) : Monitoring Reader, résolu au plan, sur l'espace seul.
  assert {
    condition = (length(data.azurerm_role_definition.process_io_reader) == 1
      && data.azurerm_role_definition.process_io_reader[0].name == "Monitoring Reader"
    && data.azurerm_role_definition.process_io_reader[0].scope == data.azurerm_subscription.bench.id)
    error_message = "le rôle de l'opérateur n'est pas Monitoring Reader, cherché dans l'abonnement du banc"
  }
  assert {
    condition = (length(azurerm_role_assignment.process_io_operator_reader) == 1
      && azurerm_role_assignment.process_io_operator_reader[0].role_definition_id == "/subscriptions/00000000-0000-0000-0000-000000000000/providers/Microsoft.Authorization/roleDefinitions/43d0d8ad-25c7-4714-9337-8ba259a9fe05"
    && azurerm_role_assignment.process_io_operator_reader[0].scope == azurerm_monitor_workspace.process_io[0].id)
    error_message = "l'opérateur ne reçoit pas Monitoring Reader (résolu au plan) sur l'espace seul"
  }
  assert {
    condition     = length(azurerm_monitor_diagnostic_setting.activity_log) == 0 && length(azurerm_virtual_machine_extension.auditd) == 0
    error_message = "PIO1 entraîne le journal d'activité ou auditd"
  }
}
