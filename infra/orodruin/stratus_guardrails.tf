# Stratus — les garde-fous de l'abonnement de test dédié (R2b, #608).
# docs/design/stratus-cible.md, § 6. Gestes de l'opérateur, jamais une session ; plan montré
# avant. Trois garde-fous, tous ÉTEINTS par défaut (stratus_guardrails_enabled = false) :
#
#   G5  Azure Policy sur l'abonnement dédié  — le vrai plafond de coût et de surface :
#       régions / types / SKU de VM autorisés (policies intégrées) + un refus maison d'une IP
#       publique sur une carte réseau (le Bastion n'est PAS concerné : son IP publique est une
#       ressource publicIPAddresses attachée au bastionHosts, jamais une IP portée par une NIC).
#   G6  Paramètre de diagnostic de l'abonnement dédié → Log Analytics du banc (catégorie
#       Administrative) : la watch voit les techniques SANS aucun droit sur l'abonnement
#       dédié. Pont à sens unique ; Imladris n'a rien sur l'abonnement dédié.
#   G7  Budget de l'abonnement dédié + groupe d'action HORS de cet abonnement (dans le groupe
#       d'Orodruin), pour que COLD/kill et « vider l'abonnement » ne le touchent pas.
#
# Le rôle fermé de Stratus (G3), l'AUTHZ_READ_ONLY d'Orodruin sur l'abonnement dédié (G4) et le
# credential fédéré « on ne devient Stratus que depuis Orodruin » (G2) sont posés plus bas (R2BGc,
# #608), maintenant que les actions minimales par technique sont mesurées (M1, Étape 1 au réel).

# Le fournisseur de l'abonnement dédié. Vide (défaut) → subscription_id null → il retombe sur
# ARM_SUBSCRIPTION_ID (celui d'Orodruin), mais aucune ressource ne l'emploie (count 0), il
# reste inerte. Activé, var.stratus_subscription_id le vise. Jamais l'abonnement du banc : la
# precondition ci-dessous refuse déjà qu'il vaille celui d'Orodruin, et le contrat (orodruin.py)
# le refusera en plus (R2c) s'il vaut le banc, la VM ou Imladris.
provider "azurerm" {
  alias           = "stratus"
  subscription_id = var.stratus_subscription_id != "" ? var.stratus_subscription_id : null
  features {}
}

# Première ligne de défense contre le bloquant v1 (viser le mauvais abonnement) : activé, la
# cible doit être renseignée et DIFFÉRENTE de l'abonnement d'Orodruin. En Terraform, un `check`
# raté n'est qu'un AVERTISSEMENT (l'apply continue) — le refus est donc une `precondition`, sur
# une ressource dont dépendent les garde-fous (cf. infra/terraform/bench_reader.tf) : un plan
# qui vise le mauvais abonnement échoue avant de rien poser. Le refus complet (banc, VM,
# Imladris) viendra du contrat (R2c), relu au démarrage. Cette ressource est inerte (aucun
# appel au cloud) et n'a pas de count : elle porte seule la garde, les autres en dépendent.
resource "terraform_data" "stratus_guard" {
  input = var.stratus_subscription_id

  lifecycle {
    precondition {
      condition = !var.stratus_guardrails_enabled || (
        var.stratus_subscription_id != "" &&
        lower(var.stratus_subscription_id) != lower(data.azurerm_subscription.current.subscription_id)
      )
      error_message = "stratus_guardrails_enabled : renseigne stratus_subscription_id (l'abonnement de test DÉDIÉ), et jamais l'abonnement d'Orodruin — ce serait le bloquant v1 (droits atteignant tout le banc)."
    }
  }
}

# ── G5 — Azure Policy ───────────────────────────────────────────────────────────────────────

# Le refus maison : une IP publique sur une carte réseau. La définition vit sur l'abonnement
# dédié (fournisseur stratus) pour que l'attribution du même abonnement puisse la viser.
resource "azurerm_policy_definition" "stratus_deny_nic_public_ip" {
  count        = var.stratus_guardrails_enabled ? 1 : 0
  depends_on   = [terraform_data.stratus_guard]
  provider     = azurerm.stratus
  name         = "eregion-stratus-deny-nic-public-ip"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Eregion Stratus — refuser une IP publique sur une carte réseau (le Bastion n'est pas concerné)"
  description  = "Une NIC avec une IP publique ouvrirait une sortie Internet contournant « Orodruin sans Internet ». L'IP publique du Bastion est une ressource publicIPAddresses attachée au bastionHosts, pas une IP portée par une NIC : elle passe."

  # « au moins une » ipConfig avec une IP publique = not(toutes sans). La forme [*]…exists ne
  # refuserait que si TOUTES les ipConfigs en ont une — une NIC à deux ipConfigs (une sans, une
  # avec) passerait ; `not { … notLike "*" }` attrape le cas « au moins une ».
  policy_rule = jsonencode({
    if = {
      allOf = [
        { field = "type", equals = "Microsoft.Network/networkInterfaces" },
        {
          not = {
            field   = "Microsoft.Network/networkInterfaces/ipConfigurations[*].publicIPAddress.id"
            notLike = "*"
          }
        },
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
  subscription_id      = "/subscriptions/${terraform_data.stratus_guard.output}"
  policy_definition_id = azurerm_policy_definition.stratus_deny_nic_public_ip[0].id
}

# Régions autorisées (policy intégrée). Non posée tant que la liste est vide : une liste vide
# refuserait TOUTE création, y compris les ressources de la mesure. Rempli depuis M1.
resource "azurerm_subscription_policy_assignment" "stratus_allowed_locations" {
  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_locations) > 0 ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-locations"
  display_name         = "Eregion Stratus — régions autorisées"
  subscription_id      = "/subscriptions/${terraform_data.stratus_guard.output}"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c"
  parameters = jsonencode({
    listOfAllowedLocations = { value = var.stratus_allowed_locations }
  })
}

# Types de ressources autorisés (policy intégrée). Doit inclure Microsoft.Network/bastionHosts
# ET Microsoft.Network/publicIPAddresses (le Bastion et son IP publique, pour le lien
# partageable). Non posée tant que la liste est vide (même raison).
resource "azurerm_subscription_policy_assignment" "stratus_allowed_resource_types" {
  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_resource_types) > 0 ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-res-types"
  display_name         = "Eregion Stratus — types de ressources autorisés"
  subscription_id      = "/subscriptions/${terraform_data.stratus_guard.output}"
  policy_definition_id = "/providers/Microsoft.Authorization/policyDefinitions/a08ec900-254a-4555-9bf5-e42af04b5c5c"
  parameters = jsonencode({
    listOfResourceTypesAllowed = { value = var.stratus_allowed_resource_types }
  })
}

# SKU de VM autorisés (policy intégrée « Allowed virtual machine size SKUs ») : les SKU des VM
# de test seules — cette policy ne vise que VM/VMSS (le Bastion est un type, pas un SKU de VM :
# il passe par les types autorisés ci-dessus). Non posée tant que la liste est vide.
resource "azurerm_subscription_policy_assignment" "stratus_allowed_vm_skus" {
  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_vm_skus) > 0 ? 1 : 0
  provider             = azurerm.stratus
  name                 = "eregion-stratus-vm-skus"
  display_name         = "Eregion Stratus — SKU de VM autorisés"
  subscription_id      = "/subscriptions/${terraform_data.stratus_guard.output}"
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
  target_resource_id         = "/subscriptions/${terraform_data.stratus_guard.output}"
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
  subscription_id = "/subscriptions/${terraform_data.stratus_guard.output}"
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

# ── R2BGc (#608) — G3 le rôle fermé de Stratus, G4 l'AUTHZ_READ_ONLY d'Orodruin, G2 le credential
#    fédéré. docs/design/stratus-cible.md, § 6 et § protocole. Posés maintenant que les actions
#    minimales par technique sont mesurées (M1, Étape 1 au réel). Gestes de l'opérateur, jamais une
#    session ; plan montré avant. Tout s'éteint à stratus_guardrails_enabled = false (count 0).

# ── G3 — le rôle fermé de Stratus ───────────────────────────────────────────────────────────
# Les 19 actions mesurées (écritures / suppressions / actions des deux techniques) + les 9
# lectures (le journal d'activité ne trace NI les lectures NI les contrôles d'accès — ajouts
# fermes) + les 3 join. AUCUNE action Microsoft.Authorization, AUCUN joker : la liste est fermée,
# le joker est interdit à la source (test_the_closed_role_has_no_wildcard… + mutant M4448) ET une
# ceinture not_actions le retirerait s'il entrait (protocole § 6 point 2 ; chaque not_action est
# nommée dans la ligne « stratus » de la matrice §3). Les actions sont EN LIGNE : scripts/identity_map.py
# les lit (§3.0 de docs/design/identites.md) ; ajouter une lecture candidate pendant le cycle = une
# ligne ici + sa ligne en §3.0 + un plan et un apply (jamais une variable surchargeable).
resource "azurerm_role_definition" "stratus_closed" {
  count       = var.stratus_guardrails_enabled ? 1 : 0
  provider    = azurerm.stratus
  name        = "eregion-stratus-closed"
  scope       = "/subscriptions/${terraform_data.stratus_guard.output}"
  description = "Stratus (Eregion R2c) : les actions minimales mesurées des techniques, sur l'abonnement dédié seulement. Aucune action Microsoft.Authorization — on ne s'élargit pas depuis Stratus."

  permissions {
    actions = [
      # Les 19 de M1 — écritures, suppressions, actions des deux techniques.
      "Microsoft.Compute/disks/delete",
      "Microsoft.Compute/virtualMachines/delete",
      "Microsoft.Compute/virtualMachines/write",
      "Microsoft.Compute/virtualMachines/runCommand/action",
      "Microsoft.Network/bastionHosts/write",
      "Microsoft.Network/bastionHosts/delete",
      "Microsoft.Network/bastionHosts/createShareableLinks/action",
      "Microsoft.Network/bastionHosts/getShareableLinks/action",
      "Microsoft.Network/bastionHosts/deleteShareableLinks/action",
      "Microsoft.Network/networkInterfaces/write",
      "Microsoft.Network/networkInterfaces/delete",
      "Microsoft.Network/publicIPAddresses/write",
      "Microsoft.Network/publicIPAddresses/delete",
      "Microsoft.Network/virtualNetworks/write",
      "Microsoft.Network/virtualNetworks/delete",
      "Microsoft.Network/virtualNetworks/subnets/write",
      "Microsoft.Network/virtualNetworks/subnets/delete",
      "Microsoft.Resources/subscriptions/resourceGroups/write",
      "Microsoft.Resources/subscriptions/resourceGroups/delete",
      # Les 9 lectures — par type écrit + celles du contrat.
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Network/virtualNetworks/read",
      "Microsoft.Network/virtualNetworks/subnets/read",
      "Microsoft.Network/networkInterfaces/read",
      "Microsoft.Network/publicIPAddresses/read",
      "Microsoft.Network/bastionHosts/read",
      "Microsoft.Compute/virtualMachines/read",
      "Microsoft.Compute/disks/read",
      "Microsoft.Insights/diagnosticSettings/read",
      # Les 3 join.
      "Microsoft.Network/virtualNetworks/subnets/join/action",
      "Microsoft.Network/networkInterfaces/join/action",
      "Microsoft.Network/publicIPAddresses/join/action",
    ]
    # La ceinture (protocole § 6 point 2) : sur une liste fermée sans joker elle ne retire rien
    # aujourd'hui, mais elle retirerait un joker s'il entrait. Chaque not_action est nommée dans la
    # matrice §3 (ligne « stratus »), exigé par scripts/identity_map.py.
    not_actions = [
      "Microsoft.Insights/diagnosticSettings/write",
      "Microsoft.Insights/diagnosticSettings/delete",
      "Microsoft.Consumption/*",
      "Microsoft.CostManagement/*",
      "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/write",
      "Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/delete",
    ]
  }

  assignable_scopes = ["/subscriptions/${terraform_data.stratus_guard.output}"]
}

# L'attribution à Stratus ne se pose qu'avec l'object id de son principal (vide → rôle défini, non
# attribué). principal_type explicite : pas d'attente de cohérence côté Azure pour un SP connu.
resource "azurerm_role_assignment" "stratus_closed" {
  count              = var.stratus_guardrails_enabled && var.stratus_principal_id != "" ? 1 : 0
  provider           = azurerm.stratus
  scope              = "/subscriptions/${terraform_data.stratus_guard.output}"
  role_definition_id = azurerm_role_definition.stratus_closed[0].role_definition_resource_id
  principal_id       = var.stratus_principal_id
  principal_type     = "ServicePrincipal"
}

# ── G4 — l'AUTHZ_READ_ONLY d'Orodruin sur l'abonnement dédié ─────────────────────────────────
# Orodruin doit prouver, depuis l'abonnement dédié, qu'il n'y a AUCUN droit dessus (M5 : une liste
# vide ≠ absence de droit — Azure ne liste que ce que l'appelant peut lire). Ce rôle lui donne
# EXACTEMENT roleAssignments/read + roleDefinitions/read, comme contract_reader sur le banc. Reader
# casserait le contrat (eregion_core/orodruin.py, AUTHZ_READ_ONLY) : trop large.
resource "azurerm_role_definition" "stratus_contract_reader" {
  count       = var.stratus_guardrails_enabled ? 1 : 0
  provider    = azurerm.stratus
  name        = "eregion-orodruin-stratus-contract-reader"
  scope       = "/subscriptions/${terraform_data.stratus_guard.output}"
  description = "Orodruin (Eregion R2c) : lire ses propres attributions sur l'abonnement dédié de Stratus, pour prouver le contrat (M5). Rien d'autre."

  permissions {
    actions = [
      "Microsoft.Authorization/roleAssignments/read",
      "Microsoft.Authorization/roleDefinitions/read",
    ]
    not_actions = []
  }

  assignable_scopes = ["/subscriptions/${terraform_data.stratus_guard.output}"]
}

resource "azurerm_role_assignment" "stratus_contract_reader" {
  count              = var.stratus_guardrails_enabled ? 1 : 0
  provider           = azurerm.stratus
  scope              = "/subscriptions/${terraform_data.stratus_guard.output}"
  role_definition_id = azurerm_role_definition.stratus_contract_reader[0].role_definition_resource_id
  principal_id       = azurerm_linux_virtual_machine.host.identity[0].principal_id
}

# ── G2 — le credential fédéré : on ne devient Stratus que depuis Orodruin ─────────────────────
# L'app de Stratus fait confiance à un jeton d'Entra ID dont le SUJET est l'identité managée
# d'Orodruin : le bac à sable échange le jeton de l'identité d'Orodruin contre un jeton de l'app
# Stratus (ARM_USE_OIDC, WorkloadIdentityCredential). JAMAIS l'identité managée d'Orodruin
# directement : elle n'a aucun rôle sur l'abonnement dédié (M4). azidentity (DefaultAzureCredential)
# retomberait sinon sur l'identité managée — AZURE_TOKEN_CREDENTIALS=WorkloadIdentityCredential l'en
# empêche (défense en profondeur), mais la frontière reste « aucun rôle » (M4). L'apply ÉCRIT sur
# l'app (Graph) : il tourne sous le login de l'opérateur, jamais sous l'identité d'Orodruin
# (GRAPH_READ_ONLY intact). L'id de ressource de l'app est lu (data), jamais écrit en dur.
data "azuread_application" "stratus" {
  count     = var.stratus_guardrails_enabled && var.stratus_client_id != "" ? 1 : 0
  client_id = var.stratus_client_id
}

resource "azuread_application_federated_identity_credential" "stratus_from_orodruin" {
  count          = var.stratus_guardrails_enabled && var.stratus_client_id != "" ? 1 : 0
  application_id = data.azuread_application.stratus[0].id
  display_name   = "orodruin-sandbox"
  description    = "Eregion R2c : on ne devient Stratus que depuis le bac à sable d'Orodruin (son identité managée comme sujet). Posé sous le login de l'opérateur."
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://login.microsoftonline.com/${data.azurerm_subscription.current.tenant_id}/v2.0"
  subject        = azurerm_linux_virtual_machine.host.identity[0].principal_id
}
