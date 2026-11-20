# DCR1 (#985) : les compteurs de performance de la DCR du banc, sous les noms que l'agent Azure Monitor
# reconnaît sous Linux — planifiés contre de faux azurerm, azapi, null et azuread : aucun appel à Azure.
# La CI le lance à chaque PR (ci.yml, job terraform-test, CI4) ; à la main :
#   terraform -chdir=infra/terraform init -backend=false -lockfile=readonly
#   terraform -chdir=infra/terraform test -filter=tests/perf_counters.tftest.hcl
# La liste est figée telle quelle : le processeur et le réseau sous leurs objets Linux (Processor(*),
# Network(*) : https://learn.microsoft.com/en-us/azure/azure-monitor/vm/metrics-guest-reference,
# onglet Linux), le disque sous son nom de toujours, mesuré au banc. Les noms Windows, déclarés jusqu'au
# 20/11 et jamais collectés, n'y reviennent pas. tests/unit/test_bench_perf_counters.py tient le même
# contrat en lisant les fichiers, et vérifie que chaque VM associée à cette DCR est une VM Linux.

mock_provider "azurerm" {}
mock_provider "azapi" {}
mock_provider "null" {}
mock_provider "azuread" {}

variables {
  # La clé jetable du test d'ID1 (sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  # Hermétique face au terraform.tfvars de l'opérateur.
  activity_log_enabled        = false
  entra_logs_enabled          = false
  auditd_enabled              = false
  cron_logs_enabled           = false
  entra_test_identity_enabled = false
  entra_bench_unit_enabled    = false
  bench_reader_enabled        = false
}

run "linux_counters_the_disk_kept_the_windows_names_gone" {
  command = plan

  assert {
    condition = azurerm_monitor_data_collection_rule.celebrimbor.data_sources[0].performance_counter[0].counter_specifiers == tolist([
      "\\LogicalDisk(*)\\Disk Write Bytes/sec",
      "\\LogicalDisk(*)\\Disk Read Bytes/sec",
      "\\Network(*)\\Total Bytes Transmitted",
      "\\Processor(*)\\% Processor Time",
    ])
    error_message = "la DCR du banc ne déclare plus la liste figée de DCR1 (disque, réseau et processeur Linux)"
  }
  assert {
    condition = length([for c in azurerm_monitor_data_collection_rule.celebrimbor.data_sources[0].performance_counter[0].counter_specifiers :
    c if strcontains(c, "_Total") || strcontains(c, "Network Interface")]) == 0
    error_message = "un nom Windows (l'instance _Total, l'objet Network Interface) est revenu dans la DCR du banc : l'agent Linux ne le collecte pas"
  }
  assert {
    condition     = azurerm_monitor_data_collection_rule.celebrimbor.data_sources[0].performance_counter[0].streams == tolist(["Microsoft-Perf"])
    error_message = "les compteurs de la DCR du banc ne vont plus vers Microsoft-Perf (la table Perf)"
  }
  assert {
    condition     = contains(azurerm_monitor_data_collection_rule.celebrimbor.data_flow[0].streams, "Microsoft-Perf")
    error_message = "aucun flux de la DCR du banc ne porte Microsoft-Perf vers le workspace"
  }
  assert {
    condition     = keys(azurerm_monitor_data_collection_rule_association.vm) == keys(azurerm_linux_virtual_machine.baseline)
    error_message = "la DCR du banc est associée à autre chose que les VM Linux du banc"
  }
}
