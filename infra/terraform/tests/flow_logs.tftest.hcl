# INF-FL (#654) : le compte des flux réseau, à lui seul — planifié contre de faux azurerm, azapi, null
# et azuread : aucun appel à Azure ni à Graph ; tous les identifiants sont des exemples. À la main :
#   terraform -chdir=infra/terraform init -backend=false -lockfile=readonly
#   terraform -chdir=infra/terraform test -filter=tests/flow_logs.tftest.hcl
# La CI le lance à chaque PR (ci.yml, job terraform-test, CI4). La propriété (CR15,
# docs/design/corroboration.md) : le flow log écrit dans le compte des flux, plus dans celui des
# exercices ; aucune identité de VM n'a d'attribution sur le compte des flux ni au-dessus (le groupe,
# l'abonnement) ; la clé partagée y est refusée. tests/unit/test_bench_flow_logs.py lit, lui, chaque
# attribution du module dans les fichiers — une attribution ajoutée ailleurs, que ce plan ne nomme pas.

mock_provider "azurerm" {
  mock_data "azurerm_subscription" {
    defaults = {
      id        = "/subscriptions/00000000-0000-0000-0000-000000000000"
      tenant_id = "00000000-0000-0000-0000-0000000000f0"
    }
  }
}
mock_provider "azapi" {}
mock_provider "null" {}
mock_provider "azuread" {}

# Connus dès le plan : les portées et les principaux que les assertions comparent.
override_resource {
  target          = azurerm_resource_group.celebrimbor
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor"
  }
}

override_resource {
  target          = azurerm_storage_account.flows
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborflows"
  }
}

override_resource {
  target          = azurerm_storage_account.exfil
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborexfil"
  }
}

override_resource {
  target          = azurerm_storage_account.restore_staging
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Storage/storageAccounts/stcelebrimborstaging"
  }
}

override_resource {
  target          = azurerm_monitor_data_collection_rule.celebrimbor
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Insights/dataCollectionRules/dcr-celebrimbor"
  }
}

# L'identité de chaque VM du banc (un même principal d'exemple pour toutes : ce qui compte est qu'il
# soit celui d'une VM).
override_resource {
  target          = azurerm_linux_virtual_machine.baseline
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-baseline"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-0000000000c1"
      tenant_id    = "00000000-0000-0000-0000-0000000000f0"
    }
  }
}

override_resource {
  target          = azurerm_linux_virtual_machine.multinic
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-multinic"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-0000000000c2"
      tenant_id    = "00000000-0000-0000-0000-0000000000f0"
    }
  }
}

override_resource {
  target          = azurerm_linux_virtual_machine.sharednsg
  override_during = plan
  values = {
    id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-sharednsg"
    identity = {
      type         = "SystemAssigned"
      principal_id = "00000000-0000-0000-0000-0000000000c3"
      tenant_id    = "00000000-0000-0000-0000-0000000000f0"
    }
  }
}

override_data {
  target          = data.azurerm_client_config.operator
  override_during = plan
  values = {
    object_id = "00000000-0000-0000-0000-0000000000d1"
    tenant_id = "00000000-0000-0000-0000-0000000000f0"
  }
}

variables {
  # La clé jetable du test d'ID1 (sa clé privée n'a jamais été gardée).
  admin_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHJsmbq1cw7yKD96VpcLp0pc+ghC6Shc4ZG5t9jktOyi id1-test"
  # Hermétique face au terraform.tfvars de l'opérateur (qui peut les activer, ou rouvrir la clé du
  # compte des flux, le retour en arrière d'INF-FL) ; le défaut lui-même est tenu par
  # tests/unit/test_bench_flow_logs.py.
  activity_log_enabled         = false
  entra_logs_enabled           = false
  auditd_enabled               = false
  entra_test_identity_enabled  = false
  entra_bench_unit_enabled     = false
  bench_reader_enabled         = false
  flow_logs_shared_key_enabled = false
  topo_filter                  = []
}

run "the_flow_log_writes_to_the_flows_account_never_the_exercises_one" {
  command = plan

  assert {
    condition     = azurerm_network_watcher_flow_log.celebrimbor.storage_account_id == azurerm_storage_account.flows.id
    error_message = "le flow log n'écrit pas dans le compte des flux"
  }
  assert {
    condition     = azurerm_network_watcher_flow_log.celebrimbor.storage_account_id != azurerm_storage_account.exfil.id
    error_message = "le flow log écrit encore dans le compte des exercices d'exfiltration"
  }
  assert {
    condition     = azurerm_network_watcher_flow_log.celebrimbor.storage_account_id != azurerm_storage_account.restore_staging.id
    error_message = "le flow log écrit dans le compte de transit du restore"
  }
  assert {
    condition = (azurerm_storage_account.flows.name != azurerm_storage_account.exfil.name
    && azurerm_storage_account.flows.name != azurerm_storage_account.restore_staging.name)
    error_message = "le compte des flux porte le nom d'un autre compte du banc : c'est le même"
  }
}

run "the_flows_account_refuses_the_shared_key_and_public_containers" {
  command = plan

  assert {
    condition     = azurerm_storage_account.flows.shared_access_key_enabled == false
    error_message = "le compte des flux accepte la clé partagée : une clé ou un SAS y écrirait"
  }
  assert {
    condition     = azurerm_storage_account.flows.allow_nested_items_to_be_public == false
    error_message = "le compte des flux permet un conteneur public"
  }
  assert {
    condition     = azurerm_storage_account.flows.account_tier == "Standard"
    error_message = "le compte des flux n'est pas Standard (Network Watcher refuse Premium)"
  }
  assert {
    condition     = azurerm_storage_account.flows.location == azurerm_resource_group.celebrimbor.location
    error_message = "le compte des flux n'est pas dans la région du VNet"
  }
}

run "no_vm_identity_is_granted_the_flows_account_nor_above_it" {
  command = plan

  # Une attribution « sur le compte des flux ou au-dessus » : sa portée est le compte, ou un préfixe
  # de son id (le groupe, l'abonnement) — un rôle hérité y vaut autant.
  assert {
    condition = alltrue([
      for ra in concat(values(azurerm_role_assignment.vm_storage_exfil), values(azurerm_role_assignment.ama_dcr)) :
      !(lower(ra.scope) == lower(azurerm_storage_account.flows.id)
      || startswith(lower(azurerm_storage_account.flows.id), "${lower(ra.scope)}/"))
    ])
    error_message = "l'identité d'une VM du banc a une attribution sur le compte des flux, ou au-dessus"
  }
  assert {
    condition     = alltrue([for ra in values(azurerm_role_assignment.vm_storage_exfil) : ra.scope == azurerm_storage_account.exfil.id])
    error_message = "l'écriture des exercices ne porte plus sur le seul compte d'exfiltration"
  }
  # Le compte des exercices garde ce qu'il faut aux exercices : l'écriture des VM inscrites.
  assert {
    condition     = keys(azurerm_role_assignment.vm_storage_exfil) == ["gondolin"]
    error_message = "l'écriture des exercices n'est plus celle des seules VM inscrites (gondolin, pas bree)"
  }
  assert {
    condition = alltrue([for ra in values(azurerm_role_assignment.vm_storage_exfil) :
    ra.role_definition_name == "Storage Blob Data Contributor" && ra.principal_id == "00000000-0000-0000-0000-0000000000c1"])
    error_message = "l'écriture des exercices n'est plus le rôle de données de l'identité de la VM"
  }
}

run "the_operator_alone_reads_the_flows_account" {
  command = plan

  assert {
    condition = (azurerm_role_assignment.flows_operator_reader.scope == azurerm_storage_account.flows.id
      && azurerm_role_assignment.flows_operator_reader.role_definition_name == "Storage Blob Data Reader"
    && azurerm_role_assignment.flows_operator_reader.principal_id == "00000000-0000-0000-0000-0000000000d1")
    error_message = "la lecture des flux ne va pas à l'opérateur, en lecture seule, sur le seul compte des flux"
  }
}

run "the_test_topologies_vms_are_not_granted_it_either" {
  command = plan

  variables {
    topo_filter = ["multinic", "sharednsg"]
  }

  assert {
    condition     = length(azurerm_role_assignment.multinic_ama_dcr) == 1 && length(azurerm_role_assignment.sharednsg_ama_dcr) > 0
    error_message = "les topologies de test ne sont pas planifiées : le cas n'est pas éprouvé"
  }
  assert {
    condition = alltrue([
      for ra in concat(azurerm_role_assignment.multinic_ama_dcr, values(azurerm_role_assignment.sharednsg_ama_dcr), values(azurerm_role_assignment.ama_dcr), values(azurerm_role_assignment.vm_storage_exfil)) :
      !(lower(ra.scope) == lower(azurerm_storage_account.flows.id)
      || startswith(lower(azurerm_storage_account.flows.id), "${lower(ra.scope)}/"))
    ])
    error_message = "l'identité d'une VM d'une topologie de test a une attribution sur le compte des flux, ou au-dessus"
  }
}

run "traffic_analytics_and_retention_as_before" {
  command = plan

  assert {
    condition = (azurerm_network_watcher_flow_log.celebrimbor.enabled
      && azurerm_network_watcher_flow_log.celebrimbor.retention_policy[0].enabled
    && azurerm_network_watcher_flow_log.celebrimbor.retention_policy[0].days == 7)
    error_message = "la rétention du flow log n'est plus celle d'avant (7 jours)"
  }
  assert {
    condition = (azurerm_network_watcher_flow_log.celebrimbor.traffic_analytics[0].enabled
    && azurerm_network_watcher_flow_log.celebrimbor.traffic_analytics[0].interval_in_minutes == 10)
    error_message = "traffic analytics n'est plus celui d'avant (activé, 10 minutes)"
  }
}

# Le retour en arrière, si Network Watcher n'écrit pas sans clé : la clé rouverte, et rien d'autre.
run "the_rollback_reopens_the_key_and_nothing_else" {
  command = plan

  variables {
    flow_logs_shared_key_enabled = true
  }

  assert {
    condition     = azurerm_storage_account.flows.shared_access_key_enabled == true
    error_message = "flow_logs_shared_key_enabled = true ne rouvre pas la clé du compte des flux"
  }
  assert {
    condition     = azurerm_network_watcher_flow_log.celebrimbor.storage_account_id == azurerm_storage_account.flows.id
    error_message = "le retour en arrière renvoie les flux vers un autre compte"
  }
}
