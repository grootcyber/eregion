resource "azurerm_storage_account" "exfil" {
  name                     = local.exfil_storage_name
  resource_group_name      = azurerm_resource_group.celebrimbor.name
  location                 = azurerm_resource_group.celebrimbor.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = local.common_tags
}

# Staging SA du restore Azure Backup IaaS : Glorfindel (restore_from_backup) y
# stage les disques restaurés. SA dédié (pas de diag setting → n'alimente PAS le
# StorageWrite du LAW, contrairement à l'exfil), même région/souscription.
resource "azurerm_storage_account" "restore_staging" {
  name                     = local.staging_storage_name
  resource_group_name      = azurerm_resource_group.celebrimbor.name
  location                 = azurerm_resource_group.celebrimbor.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = local.common_tags
}

# INF-FL (#654) : le compte des flux réseau du banc, à lui seul. Network Watcher y écrit les blobs des
# VNet flow logs (monitoring.tf, le conteneur insights-logs-flowlogflowevent qu'il crée), traffic
# analytics les lit vers NTANetAnalytics, et SEC-A3f les lira comme la preuve d'une connexion
# (docs/design/corroboration.md, §3.10). Il tient tant qu'aucune identité joignable depuis une VM
# surveillée ne peut y écrire (CR15) :
#   - aucune attribution à l'identité d'une VM, ni sur lui, ni au-dessus (groupe, abonnement) : celle
#     des exercices (vm_storage_exfil, ci-dessous) porte sur le compte d'exfiltration seul ;
#   - pas de clé partagée (var.flow_logs_shared_key_enabled, false) : ni clé, ni SAS n'y valent ;
#   - aucun conteneur public.
# Tenu par tests/flow_logs.tftest.hcl (le plan) et tests/unit/test_bench_flow_logs.py (chaque
# attribution du module, lue dans les fichiers). Chiffrement par défaut (clés gérées par Microsoft :
# une clé du client qui tourne arrête les flow logs, dit Microsoft Learn), rétention dans le flow log.
resource "azurerm_storage_account" "flows" {
  name                            = local.flows_storage_name
  resource_group_name             = azurerm_resource_group.celebrimbor.name
  location                        = azurerm_resource_group.celebrimbor.location
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  shared_access_key_enabled       = var.flow_logs_shared_key_enabled
  allow_nested_items_to_be_public = false
  tags                            = local.common_tags
}

# Qui lit les blobs des flux : l'opérateur qui applique ce module (son az login), pour les mesures au
# banc (docs/design/corroboration.md, §5.4, M1b) — sans clé, son rôle Owner n'ouvre plus le plan de
# données. Une lecture, jamais une écriture ; l'identité de Glorfindel (H0) aura la sienne par SEC-A3f,
# dans son module. Aucune VM.
data "azurerm_client_config" "operator" {}

resource "azurerm_role_assignment" "flows_operator_reader" {
  scope                = azurerm_storage_account.flows.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = data.azurerm_client_config.operator.object_id
}

resource "azurerm_storage_container" "exfil" {
  name               = "exfil-target"
  storage_account_id = azurerm_storage_account.exfil.id
}

# VM managed identity needs to write blobs for exfil simulation — enrolled VMs only: a VM
# that no injector targets (bree, `enrolled: false`) has no exfil to simulate.
# INF-FL : sur le compte d'exfiltration SEUL, jamais au-dessus — le groupe porte aussi le compte des
# flux (ci-dessus), qu'un rôle hérité ouvrirait aux VM.
resource "azurerm_role_assignment" "vm_storage_exfil" {
  for_each             = { for k, v in local.vms : k => v if try(v.enrolled, true) }
  scope                = azurerm_storage_account.exfil.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_virtual_machine.baseline[each.key].identity[0].principal_id
}

# Diagnostic logs → LAW: StorageBlobLogs populated in seconds (vs 10 min for Traffic Analytics)
# CallerIpAddress in StorageBlobLogs gives us the source IP for block_suspicious_ip.
resource "azurerm_monitor_diagnostic_setting" "exfil_storage" {
  name                       = "diag-${local.project}-exfil${local.ns}"
  target_resource_id         = "${azurerm_storage_account.exfil.id}/blobServices/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.celebrimbor.id

  enabled_log {
    category = "StorageWrite"
  }
}
