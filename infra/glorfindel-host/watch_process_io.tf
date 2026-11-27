# PIO1 (#1258) : la watch d'Imladris lit qui écrit sous Linux — la métrique OpenTelemetry
# process.disk.io de l'agent, par processus, dans l'espace de travail Azure Monitor du banc
# (infra/terraform/process_io.tf), en PromQL, par son point de requête
# (glorfindel/providers/azure/prometheus.py, la lecture process_write_io de l'enquête, à mesurer au
# banc). Un rôle, en lecture, attribué à l'identité managée de la VM (celle de la watch, et de la
# console et du bot, qui partagent le point de jeton de la VM), sur cet espace seul :
#   Monitoring Data Reader   l'action de données microsoft.monitor/accounts/data/metrics/read : lire les
#                            métriques de l'espace en PromQL. Rien n'est écrit. Ce qui se lit : les
#                            métriques de l'invité des VM du banc, que l'invité forge (le nom d'un
#                            processus vient de /proc/[pid]/status) — docs/design/modele-de-menace.md.
# Le rôle est pris par son nom, jamais par un identifiant écrit ici : Learn le nomme
# (https://learn.microsoft.com/en-us/azure/azure-monitor/metrics/prometheus-api-promql, « Assign the
# Monitoring Data Reader role to your app so that it can query data from your Azure Monitor workspace »),
# mais la liste des rôles intégrés de Learn ne le porte plus (lue le 27/11) : que ce nom se résolve au
# plan est la première chose à lire (docs/operations.md, « Qui écrit sous Linux, au banc (PIO1) »).
#
# Désactivé par défaut : `watch_process_io_read_enabled = true` dans watch_process_io.auto.tfvars
# (ignoré par git ; watch_process_io.auto.tfvars.example), une fois l'espace posé au banc
# (`make celebrimbor-process-io-up`), puis `make imladris-plan`, relu, puis `make imladris-up` — par
# Jonathan. L'espace est relu sur Azure par son nom (bench_monitor_workspace, la sortie
# process_io_workspace_name du banc) : un espace absent fait échouer le plan, jamais un rôle posé
# ailleurs. Désactivé, rien n'est lu ni attribué (`count`).

data "azurerm_monitor_workspace" "bench" {
  count               = var.watch_process_io_read_enabled ? 1 : 0
  name                = var.bench_monitor_workspace
  resource_group_name = data.azurerm_resource_group.bench.name
}

resource "azurerm_role_assignment" "watch_process_io" {
  count                = var.watch_process_io_read_enabled ? 1 : 0
  scope                = data.azurerm_monitor_workspace.bench[0].id
  role_definition_name = "Monitoring Data Reader"
  principal_id         = azurerm_linux_virtual_machine.host.identity[0].principal_id
}
