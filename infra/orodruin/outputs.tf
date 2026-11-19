# DRL1c (#613) — le contrat de DRL1a (docs/design/drill-banc.md §11) : l'id de la Logic App du démarrage
# planifié, que le Makefile lit par `terraform output -json` (infra/orodruin/drill_ops.py autostart-id).
output "drill_autostart_id" {
  description = "DRILL_AUTOSTART — la Logic App qui réveille Orodruin avant le drill de la semaine : créée Disabled, activée par orodruin-drill-arm, désactivée par -disarm et le kill."
  value       = local.autostart_outputs.workflowId.value
}

output "public_ip" {
  description = "IP publique de la VM (SSH depuis operator_cidr seulement)."
  value       = azurerm_public_ip.host.ip_address
}

output "ssh" {
  value = "ssh ${var.admin_username}@${azurerm_public_ip.host.ip_address}"
}

output "principal_id" {
  description = "Identité managée de la VM — ce que orodruin-kill révoque."
  value       = azurerm_linux_virtual_machine.host.identity[0].principal_id
}

output "vm_id" {
  description = "La VM que orodruin-kill désalloue."
  value       = azurerm_linux_virtual_machine.host.id
}

output "workspace_id" {
  description = "Log Analytics du banc, pour la cible des scénarios."
  value       = data.azurerm_log_analytics_workspace.bench.workspace_id
}

output "channel_url" {
  description = "EREGION_EXERCISE_CHANNEL — dans orodruin.env et dans le host.env de Glorfindel."
  value       = "${azurerm_storage_account.channel.primary_blob_endpoint}${azurerm_storage_container.exercises.name}"
}

output "channel_scope" {
  description = "EREGION_CHANNEL_SCOPE — dans orodruin.env : la portée que le contrat accepte hors du banc."
  value       = azurerm_storage_container.exercises.id
}

output "watch_channel_url" {
  description = "EREGION_WATCH_CHANNEL — dans orodruin.env et dans le host.env de Glorfindel (#159)."
  value       = "${azurerm_storage_account.channel.primary_blob_endpoint}${azurerm_storage_container.watch.name}"
}

output "watch_channel_scope" {
  description = "EREGION_WATCH_CHANNEL_SCOPE — dans orodruin.env : le contrat n'y accepte qu'un rôle de lecture."
  value       = azurerm_storage_container.watch.id
}

# IDI1 (#546) : ce que la garde d'une identité d'Entra ID sait avant de lire — dans orodruin.env.
# Les valeurs ne vont jamais dans le dépôt : `terraform -chdir=infra/orodruin output -raw <nom>`.
output "tenant_id" {
  description = "EREGION_TENANT_ID — le tenant du banc (celui de l'abonnement) : une identité d'un autre tenant est refusée."
  value       = data.azurerm_subscription.current.tenant_id
}

output "operator_object_id" {
  description = "EREGION_OPERATOR_OBJECT_ID — l'opérateur qui applique (son az login) : jamais une cible ; sans lui, la garde refuse toute identité."
  value       = data.azurerm_client_config.operator.object_id
}

output "protected_identities" {
  description = "EREGION_PROTECTED_IDENTITIES — l'identité d'Orodruin et celles des watches (H0, les watches listées) : jamais des cibles."
  value       = join(",", distinct(compact(concat([lower(azurerm_linux_virtual_machine.host.identity[0].principal_id)], local.watch_writers))))
}

# R2b (#608) — ce que les garde-fous ont posé sur l'abonnement de test dédié (null si éteint).
# Pour la passe de mesure et le rapport ; valeurs jamais recopiées dans le dépôt.
output "stratus_diagnostic_setting_id" {
  description = "G6 — l'id du paramètre de diagnostic de l'abonnement dédié (catégorie Administrative → workspace du banc), ou null."
  value       = one(azurerm_monitor_diagnostic_setting.stratus_activity_log[*].id)
}

output "stratus_budget_action_group_id" {
  description = "G7 — le groupe d'action du budget, posé HORS de l'abonnement dédié (groupe d'Orodruin), ou null."
  value       = one(azurerm_monitor_action_group.stratus_budget[*].id)
}

output "stratus_policy_assignment_ids" {
  description = "G5 — les attributions de policy posées sur l'abonnement dédié (refus IP publique sur NIC, et selon les listes : régions, types, SKU)."
  value = compact([
    one(azurerm_subscription_policy_assignment.stratus_deny_nic_public_ip[*].id),
    one(azurerm_subscription_policy_assignment.stratus_allowed_locations[*].id),
    one(azurerm_subscription_policy_assignment.stratus_allowed_resource_types[*].id),
    one(azurerm_subscription_policy_assignment.stratus_allowed_vm_skus[*].id),
  ])
}
