# Stratus — les garde-fous de l'abonnement de test dédié (R2b, #608).
# docs/design/stratus-cible.md, § 6. Gestes de l'opérateur, jamais une session ; plan montré
# avant. Trois garde-fous, tous ÉTEINTS par défaut (stratus_guardrails_enabled = false) :
#
#   G5  Azure Policy sur l'abonnement dédié  — le vrai plafond de coût et de surface :
#       régions / types / SKU autorisés (policies intégrées) + un refus maison d'une IP
#       publique sur une carte réseau (le Bastion n'est PAS concerné : son IP publique vit
#       sur la ressource bastionHosts, pas sur une NIC).
#   G6  Paramètre de diagnostic de l'abonnement dédié → Log Analytics du banc (catégorie
#       Administrative) : la watch voit les techniques SANS aucun droit sur l'abonnement
#       dédié. Pont à sens unique ; Imladris n'a rien sur l'abonnement dédié.
#   G7  Budget de l'abonnement dédié + groupe d'action HORS de cet abonnement (dans le groupe
#       d'Orodruin), pour que COLD/kill et « vider l'abonnement » ne le touchent pas.
#
# Le rôle fermé de Stratus (G3) et l'AUTHZ_READ_ONLY d'Orodruin sur l'abonnement dédié (G4)
# ne sont PAS ici : ils attendent la mesure des actions minimales par technique (M1). Les
# poser sur un rôle vide refuserait tout ; les poser larges aveuglerait la mesure.

# Le fournisseur de l'abonnement dédié. Vide (défaut) → subscription_id null → il retombe sur
# ARM_SUBSCRIPTION_ID (celui d'Orodruin), mais aucune ressource ne l'emploie (count 0), il
# reste inerte. Activé, var.stratus_subscription_id le vise. Jamais l'abonnement du banc : le
# check ci-dessous refuse déjà qu'il vaille celui d'Orodruin, et le contrat (orodruin.py)
# refuse en plus le banc, la VM et Imladris.
provider "azurerm" {
  alias = "stratus"
  features {}
  subscription_id = var.stratus_subscription_id != "" ? var.stratus_subscription_id : null
}

# Première ligne de défense contre le bloquant v1 (viser le mauvais abonnement) : activé, la
# cible doit être renseignée et DIFFÉRENTE de l'abonnement d'Orodruin. Le refus complet (banc,
# VM, Imladris) reste au contrat, qui le relit au démarrage.
check "stratus_subscription_is_dedicated" {
  assert {
    condition = !var.stratus_guardrails_enabled || (
      var.stratus_subscription_id != "" &&
      lower(var.stratus_subscription_id) != lower(data.azurerm_subscription.current.subscription_id)
    )
    error_message = "stratus_guardrails_enabled : renseigne stratus_subscription_id (l'abonnement de test DÉDIÉ), et jamais l'abonnement d'Orodruin — ce serait le bloquant v1 (droits atteignant tout le banc)."
  }
}

# ── G5 — Azure Policy ───────────────────────────────────────────────────────────────────────

# Le refus maison : une IP publique sur une carte réseau. La définition vit sur l'abonnement
# dédié (fournisseur stratus) pour que l'attribution du même abonnement puisse la viser.
resource "azurerm_policy_definition" "stratus_deny_nic_public_ip" {
  count        = var.stratus_guardrails_enabled ? 1 : 0
  provider     = azurerm.stratus
  name         = "eregion-stratus-deny-nic-public-ip"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Eregion Stratus — refuser une IP publique sur une carte réseau (le Bastion n'est pas concerné)"
  description  = "Une NIC avec une IP publique ouvrirait une sortie Internet contournant « Orodruin sans Internet ». L'IP publique du Bastion vit sur bastionHosts, pas sur une NIC : elle passe."

  policy_rule = jsonencode({
    if = {
      allOf = [
        { field = "type", equals = "Microsoft.Network/networkInterfaces" },
        { field = "Microsoft.Network/networkInterfaces/ipConfigurations[*].publicIPAddress.id", exists = "true" },
      ]
    }
    then = { effect = "deny" }
  })
}

resource "azurerm_subscription_policy_assignment" "stratus_deny_nic_public_ip" {
  count                = var.stratus_guardrails_enabled ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-deny-nic-pip"
  display_name         = "Eregion Stratus — pas d'IP publique sur une NIC"
  subscription_id      = "/subscriptions/${var.stratus_subscription_id}"
  policy_definition_id = azurerm_policy_definition.stratus_deny_nic_public_ip[0].id
}

# Régions autorisées (policy intégrée). Non posée tant que la liste est vide : une liste vide
# refuserait TOUTE création, y compris les ressources de la mesure. Rempli depuis M1.
resource "azurerm_subscription_policy_assignment" "stratus_allowed_locations" {
  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_locations) > 0 ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-locations"
  display_name         = "Eregion Stratus — régions autorisées"
  subscription_id      = "/subscriptions/${var.stratus_subscription_id}"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c"
  parameters = jsonencode({
    listOfAllowedLocations = { value = var.stratus_allowed_locations }
  })
}

# Types de ressources autorisés (policy intégrée). Doit inclure Microsoft.Network/bastionHosts
# pour le lien partageable. Non posée tant que la liste est vide (même raison).
resource "azurerm_subscription_policy_assignment" "stratus_allowed_resource_types" {
  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_resource_types) > 0 ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-res-types"
  display_name         = "Eregion Stratus — types de ressources autorisés"
  subscription_id      = "/subscriptions/${var.stratus_subscription_id}"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/a08ec900-254a-4555-9bf5-e42af04b5c5c"
  parameters = jsonencode({
    listOfResourceTypesAllowed = { value = var.stratus_allowed_resource_types }
  })
}

# SKU de VM autorisés (policy intégrée) : inclure le SKU du Bastion Standard/Premium. Non posée
# tant que la liste est vide.
resource "azurerm_subscription_policy_assignment" "stratus_allowed_vm_skus" {
  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_vm_skus) > 0 ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-vm-skus"
  display_name         = "Eregion Stratus — SKU de VM autorisés"
  subscription_id      = "/subscriptions/${var.stratus_subscription_id}"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/cccc23c7-8427-4f53-ad12-b6a63eb452b3"
  parameters = jsonencode({
    listOfAllowedSKUs = { value = var.stratus_allowed_vm_skus }
  })
}

# ── G6 — le paramètre de diagnostic (abonnement dédié → workspace du banc) ───────────────────
# La catégorie Administrative seule (ce que lisent les règles AL1, comme activity_log.tf du
# banc). Cible = l'abonnement dédié tout entier. Non posé tant que l'id du workspace du banc
# n'est pas donné. Le pont est à sens unique : Imladris lit ce workspace, il n'a aucun droit
# sur l'abonnement dédié.
resource "azurerm_monitor_diagnostic_setting" "stratus_activity_log" {
  count                      = var.stratus_guardrails_enabled && var.stratus_bench_workspace_id != "" ? 1 : 0
  provider                   = azurerm.stratus
  name                       = "diag-eregion-stratus-activity"
  target_resource_id         = "/subscriptions/${var.stratus_subscription_id}"
  log_analytics_workspace_id = var.stratus_bench_workspace_id

  enabled_log {
    category = "Administrative"
  }
}

# ── G7 — le budget + le groupe d'action HORS de l'abonnement dédié ───────────────────────────
# Le groupe d'action vit dans le groupe d'Orodruin (fournisseur par défaut) : « vider
# l'abonnement » (kill) et COLD ne touchent que l'abonnement dédié, donc ils l'épargnent.
resource "azurerm_monitor_action_group" "stratus_budget" {
  count               = var.stratus_guardrails_enabled && var.stratus_monthly_budget > 0 ? 1 : 0
  name                = "ag-eregion-stratus-budget"
  resource_group_name = azurerm_resource_group.host.name
  short_name          = "stratusbgt"
  tags                = local.tags

  dynamic "email_receiver" {
    for_each = var.stratus_budget_contact_emails
    content {
      name          = "op-${email_receiver.key}"
      email_address = email_receiver.value
    }
  }
}

# Le budget sur l'abonnement dédié (fournisseur stratus). Évalué avec 8–24 h de retard : une
# notification, pas un plafond. Posé seulement avec un montant et un début de période.
resource "azurerm_consumption_budget_subscription" "stratus" {
  count           = var.stratus_guardrails_enabled && var.stratus_monthly_budget > 0 && var.stratus_budget_start_date != "" ? 1 : 0
  provider        = azurerm.stratus
  name            = "budget-eregion-stratus"
  subscription_id = "/subscriptions/${var.stratus_subscription_id}"
  amount          = var.stratus_monthly_budget
  time_grain      = "Monthly"

  time_period {
    start_date = var.stratus_budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Actual"
    contact_groups = [azurerm_monitor_action_group.stratus_budget[0].id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted"
    contact_groups = [azurerm_monitor_action_group.stratus_budget[0].id]
  }
}
