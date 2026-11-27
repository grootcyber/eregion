# PIO1 (#1258) : la watch d'Imladris lit qui écrit sous Linux — la métrique OpenTelemetry
# process.disk.io de l'agent, par processus, dans l'espace de travail Azure Monitor du banc
# (infra/terraform/process_io.tf), en PromQL, par son point de requête
# (glorfindel/providers/azure/prometheus.py, la lecture process_write_io de l'enquête, à mesurer au
# banc). Un rôle, en lecture, attribué à l'identité managée de la VM (celle de la watch, et de la
# console et du bot, qui partagent le point de jeton de la VM), sur cet espace seul :
#   Monitoring Reader   `*/read` (et Microsoft.Support/*), à la portée de l'espace seul : il lit les
#                       réglages de l'espace et ses données, aucune écriture. Ce qui se lit : les
#                       métriques de l'invité des VM du banc, que l'invité forge (le nom d'un processus
#                       vient de /proc/[pid]/status) — docs/design/modele-de-menace.md.
# Pourquoi lui : Learn ne cite que Monitoring Reader et Monitoring Contributor pour lire un espace de
# travail Azure Monitor (« Manage access to Azure Monitor workspaces » : `*/read` « For workspaces,
# allows full unrestricted permissions to read the workspace settings and query data ») ; le
# « Monitoring Data Reader » de la page PromQL n'est plus dans la liste des rôles intégrés (lue le
# 27/11). Décision de Jonathan, 27/11 (voie A).
#
# **Le nom se résout au plan** : data "azurerm_role_definition", cherché à la portée de l'abonnement
# (la forme documentée par azurerm), puis role_definition_id. Un nom qui ne se résout pas arrête
# `make imladris-plan`, avant tout apply ; l'affectation reste à la portée de l'espace seul.
# **Hypothèses à mesurer au banc** (docs/operations.md, « Qui écrit sous Linux, au banc (PIO1) ») : que
# ce `*/read` suffise pour PromQL ; que le Reader qu'Imladris a déjà sur le groupe du banc (main.tf,
# bench_reader) ne suffise pas déjà, ce qui rendrait ce rôle redondant. S'il ne suffit pas, le lecteur
# dit PIO_DROIT (un 403), et la suite est un rôle personnalisé réduit à l'action de données
# microsoft.monitor/accounts/data/metrics/read, dans un lot à lui.
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

data "azurerm_role_definition" "watch_process_io" {
  count = var.watch_process_io_read_enabled ? 1 : 0
  name  = "Monitoring Reader"
  scope = data.azurerm_subscription.current.id
}

resource "azurerm_role_assignment" "watch_process_io" {
  count              = var.watch_process_io_read_enabled ? 1 : 0
  scope              = data.azurerm_monitor_workspace.bench[0].id
  role_definition_id = data.azurerm_role_definition.watch_process_io[0].id
  principal_id       = azurerm_linux_virtual_machine.host.identity[0].principal_id
}
