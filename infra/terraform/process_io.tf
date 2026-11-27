# Qui écrit sous Linux : la métrique par processus de l'agent (PIO1, #1258 ;
# docs/design/enquete-raisonnee.md §4.4, §9.7, proposition 1).
#
# Sous Linux, l'agent Azure Monitor ne porte aucun compteur `Process` vers Log Analytics : la
# lecture `top_write_processes` y est sans objet (glorfindel/enquiry/catalog.py). La seule voie de
# l'agent qui dise qui écrit est OpenTelemetry : `process.disk.io` (Sum, cumulative, attribut
# `direction` read|write ; l'exécutable, le pid, le propriétaire et la commande promus en dimensions
# — Microsoft Learn, « OpenTelemetry Guest OS Metrics reference »,
# https://learn.microsoft.com/en-us/azure/azure-monitor/vm/metrics-guest-reference). Ces métriques
# vont dans un espace de travail Azure Monitor (Microsoft.Monitor/accounts), lu en PromQL, jamais
# dans Log Analytics.
#
# Désactivé par défaut : `process_io_enabled = true` dans terraform.tfvars (variables.tf), puis
# `make celebrimbor-process-io-plan`, relu, puis `make celebrimbor-process-io-up` — par Jonathan
# (docs/operations.md, « Qui écrit sous Linux, au banc (PIO1) »). Ce que le drapeau pose, et rien
# d'autre :
#   - un espace de travail Azure Monitor (`amw-celebrimbor`) ;
#   - une DCR à part, `dcr-celebrimbor-process-io`, qui ne collecte que `process.disk.io` vers cet
#     espace. **La DCR de la règle (monitoring.tf) reste intacte** : ni flux, ni compteur, ni
#     destination de plus ;
#   - son association à chaque VM du banc (local.vms : gondolin, bree), sur le modèle de
#     azurerm_monitor_data_collection_rule_association.vm.
# **Aucun droit nouveau** (décision de Jonathan, 27/11 : « pas de rôle nouveau, mesurer ») : la watch lit
# l'espace avec le Reader qu'elle a déjà sur le groupe du banc (infra/glorfindel-host/main.tf,
# bench_reader), l'opérateur avec son Owner. Selon Learn, les rôles intégrés de lecture ne portent aucune
# action de données (Reader : `*/read` ; Monitoring Reader : `*/read`,
# `Microsoft.OperationalInsights/workspaces/search/action`, `Microsoft.Support/*`) : que `*/read` suffise
# pour PromQL est la seule hypothèse : le banc dit, sous l'Owner de l'opérateur, si une action de données
# est demandée, le run de bout en bout d'ENQ5b, sous l'identité de la watch, si `*/read` seul suffit
# (docs/operations.md). S'il ne suffit
# pas, la suite prévue est un rôle personnalisé réduit à microsoft.monitor/accounts/data/metrics/read,
# dans un lot à lui.
#
# **Pourquoi azapi, et pas azurerm_monitor_data_collection_rule.** Le flux est `Microsoft-
# OtelPerfMetrics`, sous la clé `dataSources.performanceCountersOTel`, avec une destination
# `monitoringAccounts` (l'exemple de DCR « Metrics-based experience » de Learn,
# https://learn.microsoft.com/en-us/azure/azure-monitor/vm/vm-enable-monitoring ; la référence ARM
# 2024-03-11, https://learn.microsoft.com/en-us/azure/templates/microsoft.insights/2024-03-11/
# datacollectionrules : ses `streams` n'acceptent que 'Microsoft-OtelPerfMetrics'). azurerm 4.81.0
# (la version de .terraform.lock.hcl) parle l'API 2023-03-11, qui n'a pas `performanceCountersOTel`
# (lu dans son code au tag v4.81.0, monitor_data_collection_rule_resource.go) : son bloc
# `performance_counter` sérialise toujours `performanceCounters`, et y mettre ce flux en ferait une
# source classique, au comportement ni documenté ni mesuré. Son bloc `destinations.monitor_account`
# existe, lui (monitor_account_id, name), mais seul ne suffit pas. azapi 2.13.0 connaît
# Microsoft.Insights/dataCollectionRules@2024-03-11 et `performanceCountersOTel` (son index de types
# au tag v2.13.0) : la même voie que la cible de Chaos Studio (chaos.tf), choisie avec Jonathan le
# 31/10 pour une propriété qu'azurerm ne sait pas déclarer.
#
# **Ce qui n'est pas mesuré** (docs/operations.md, la section PIO1, dit les contrôles) :
#   - le nom de la série et de ses dimensions en PromQL : Learn n'écrit que la forme pointée entre
#     guillemets (`{"system.cpu.utilization"}`, `by ("Microsoft.resourceid")`,
#     https://learn.microsoft.com/en-us/azure/azure-monitor/metrics/prometheus-resource-scoped-queries) ;
#     `{"process.disk.io"}` et `"process.executable.name"` en sont l'analogie, jamais lue au banc ;
#   - que `process.disk.io` soit collectée par l'agent Linux du banc : Learn la liste sans la dire
#     « Windows seul », et ne donne aucune version minimale. Le journal des versions de l'agent dit
#     « Added default dimensions (process ID, executable name, command, owner) to OpenTelemetry process
#     performance counters ingested to AMW » pour Linux 1.40.0 (février 2026) : une version au moins
#     égale est notre déduction, pas un fait documenté
#     (https://learn.microsoft.com/en-us/azure/azure-monitor/agents/azure-monitor-agent-extension-versions) ;
#   - qu'aucun rôle de plus ne soit demandé à l'identité de la VM pour envoyer vers l'espace : Learn
#     n'en demande aucun (l'identité managée seule, azure-monitor-agent-requirements), aucun n'est posé
#     ici ; si rien n'arrive, c'est le premier contrôle ;
#   - aucun point de collecte (DCE) : Learn n'en exige que pour Private Link
#     (data-collection-endpoint-overview), que la collecte par métriques ne prend pas.
#
# **Le nom d'un processus est forgeable** : il vient de /proc/[pid]/status, que le processus choisit
# (prctl, argv[0]). Root sur la VM nomme son chiffreur « waagent ». La lecture qui en vient
# (`process_write_io`) ne sert qu'à resserrer : aucune hypothèse qui relâche ne s'appuie sur le nom
# d'un agent de sauvegarde (§4.4).
#
# Coût (la page des prix d'Azure Monitor, « Metric samples ingested », par 10 millions
# d'échantillons ; 18 mois de rétention compris) : docs/operations.md, la section PIO1. Ordre de
# grandeur : 150 processus × 2 directions × 1 échantillon par minute, environ 13 millions
# d'échantillons par mois et par VM, soit environ 0,14 USD par VM et par mois à 0,11 USD les
# 10 millions (le prix de détail public d'octobre 2026, à relire sur la page).
#
# Désactivé, rien ne s'exécute : ni l'espace, ni la DCR, ni les associations (`count`, `for_each`).

locals {
  process_io_enabled = var.process_io_enabled
  # Les VM du banc qui envoient leurs métriques par processus : toutes celles du baseline, ou aucune.
  process_io_vms = { for k, v in local.vms : k => v if local.process_io_enabled }
  # La seule métrique collectée : les octets lus et écrits par processus. Les autres métriques de
  # l'invité (system.*) restent hors de cette DCR : chacune se paie à l'échantillon.
  process_io_counters = ["process.disk.io"]
  process_io_stream   = "Microsoft-OtelPerfMetrics"
}

resource "azurerm_monitor_workspace" "process_io" {
  count               = local.process_io_enabled ? 1 : 0
  name                = "amw-${local.project}${local.ns}"
  resource_group_name = azurerm_resource_group.celebrimbor.name
  location            = azurerm_resource_group.celebrimbor.location
  tags                = local.common_tags
}

resource "azapi_resource" "process_io_dcr" {
  count     = local.process_io_enabled ? 1 : 0
  type      = "Microsoft.Insights/dataCollectionRules@2024-03-11"
  name      = "dcr-${local.project}-process-io${local.ns}"
  parent_id = azurerm_resource_group.celebrimbor.id
  location  = azurerm_resource_group.celebrimbor.location
  tags      = local.common_tags

  body = {
    properties = {
      description = "PIO1 : process.disk.io par processus vers l'espace de travail Azure Monitor du banc (la DCR de la règle reste intacte)."
      dataSources = {
        performanceCountersOTel = [{
          name                       = "otel-process-io"
          streams                    = [local.process_io_stream]
          samplingFrequencyInSeconds = 60
          counterSpecifiers          = local.process_io_counters
        }]
      }
      destinations = {
        monitoringAccounts = [{
          name              = "amw-dest"
          accountResourceId = azurerm_monitor_workspace.process_io[0].id
        }]
      }
      dataFlows = [{
        streams      = [local.process_io_stream]
        destinations = ["amw-dest"]
      }]
    }
  }
}

resource "azurerm_monitor_data_collection_rule_association" "process_io" {
  for_each                = local.process_io_vms
  name                    = "dcra-${local.project}-${each.key}-process-io${local.ns}"
  target_resource_id      = azurerm_linux_virtual_machine.baseline[each.key].id
  data_collection_rule_id = azapi_resource.process_io_dcr[0].id
}
