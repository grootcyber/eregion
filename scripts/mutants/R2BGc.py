"""Lot R2BGc (Partie de #608) — G3/G4/G2 de Stratus en Terraform (infra/orodruin/
stratus_guardrails.tf, variables.tf) : le rôle fermé mesuré (actions EN LIGNE, lues par
scripts/identity_map.py), l'AUTHZ_READ_ONLY d'Orodruin sur l'abonnement dédié, le credential
fédéré. Des bugs réinjectés un à un, chacun attrapé par un test de
tests/unit/test_stratus_guardrails.py. M4448–M4460.

M4461–M4469 restent réservés aux pièces suivantes de R2c (refus du contrat sur un abonnement qui
heurte le banc/la VM/Imladris, scope Stratus + kind:fault, le bac à sable durci) — après la mesure.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
GUARD = "infra/orodruin/stratus_guardrails.tf"

_T = "tests/unit/test_stratus_guardrails.py::"
_WILDCARD = _T + "test_the_closed_role_has_no_wildcard_and_no_authorization_action"
_MEASURED = _T + "test_the_closed_role_carries_the_measured_actions"
_BELT = _T + "test_the_closed_role_keeps_the_not_actions_belt"
_G3_SCOPE = _T + "test_the_closed_role_definition_is_scoped_to_the_dedicated_subscription"
_G3_ASSIGN = _T + "test_the_closed_role_is_assigned_only_with_a_principal_and_as_a_service_principal"
_G4_EXACT = _T + "test_orodruins_role_on_the_dedicated_subscription_is_exactly_authz_read"
_G4_ASSIGN = _T + "test_orodruins_authz_read_is_assigned_to_its_own_managed_identity"
_G2_TRUST = _T + "test_the_federated_credential_trusts_orodruins_identity_only"

MUTANTS = [
    ("M4448", "a wildcard sneaks into the closed role's actions — Stratus could do anything on a "
     "whole provider, not only the measured verbs (R2c boundary broken)", GUARD,
     '      "Microsoft.Compute/disks/delete",',
     '      "Microsoft.Compute/*",'),
    ("M4449", "a Microsoft.Authorization action sneaks into the closed role — Stratus could grant "
     "itself roles (the one family the role must never hold)", GUARD,
     '      "Microsoft.Compute/disks/read",',
     '      "Microsoft.Authorization/roleAssignments/write",'),
    ("M4450", "a join action is swapped for a duplicate read — the count stays 31 but Stratus can "
     "no longer attach the public IP to the Bastion (a measured action silently lost)", GUARD,
     '      "Microsoft.Network/publicIPAddresses/join/action",',
     '      "Microsoft.Network/publicIPAddresses/read",'),
    ("M4451", "a measured write action is dropped (runCommand) — the closed-role cycle would fail a "
     "step and the role no longer carries the 31 measured actions", GUARD,
     '      "Microsoft.Compute/virtualMachines/runCommand/action",\n',
     ''),
    ("M4452", "the not_actions belt loses diagnosticSettings/write — the protocol's belt (§ 6 "
     "point 2) would no longer strip that write should a wildcard ever enter the Actions", GUARD,
     '      "Microsoft.Insights/diagnosticSettings/write",\n',
     ''),
    ("M4453", "the closed role definition loses its azurerm.stratus provider and falls back to "
     "Orodruin's own subscription (the v1 blocker: rights on the whole bench)", GUARD,
     '  provider    = azurerm.stratus\n  name        = "eregion-stratus-closed"',
     '  provider    = azurerm\n  name        = "eregion-stratus-closed"'),
    ("M4454", "the closed role is assigned as a User instead of a ServicePrincipal — Azure would "
     "wait for a principal that is not one (wrong principal type)", GUARD,
     '  principal_type     = "ServicePrincipal"',
     '  principal_type     = "User"'),
    ("M4455", "the closed role assignment loses its principal gate — it would try to assign the "
     "role with an empty principal id (apply error, or a dangling grant)", GUARD,
     '  count              = var.stratus_guardrails_enabled && var.stratus_principal_id != "" ? 1 : 0',
     "  count              = var.stratus_guardrails_enabled ? 1 : 0"),
    ("M4456", "Orodruin's AUTHZ role on the dedicated subscription gains roleAssignments/write — it "
     "could grant roles there, far beyond the read-only the contract allows (M5)", GUARD,
     '      "Microsoft.Authorization/roleAssignments/read",\n'
     '      "Microsoft.Authorization/roleDefinitions/read",',
     '      "Microsoft.Authorization/roleAssignments/read",\n'
     '      "Microsoft.Authorization/roleAssignments/write",\n'
     '      "Microsoft.Authorization/roleDefinitions/read",'),
    ("M4457", "Orodruin's AUTHZ read is assigned to Stratus's principal instead of Orodruin's own "
     "managed identity — the wrong identity gets the read (M5 would prove nothing)", GUARD,
     "  principal_id       = azurerm_linux_virtual_machine.host.identity[0].principal_id",
     "  principal_id       = var.stratus_principal_id"),
    ("M4458", "the federated credential's issuer hardcodes a tenant GUID instead of reading it from "
     "the client's config — brittle, and could trust the wrong tenant", GUARD,
     '  issuer         = "https://login.microsoftonline.com/${data.azurerm_subscription.current.tenant_id}/v2.0"',
     '  issuer         = "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0"'),
    ("M4459", "the federated credential's subject is Stratus's principal instead of Orodruin's "
     "identity — anyone but Orodruin could become Stratus (M3/M4 broken)", GUARD,
     "  subject        = azurerm_linux_virtual_machine.host.identity[0].principal_id",
     "  subject        = var.stratus_principal_id"),
    ("M4460", "the federated credential loses its client-id gate — it would try to look up an empty "
     "app and post a credential without the dedicated identity", GUARD,
     '  count          = var.stratus_guardrails_enabled && var.stratus_client_id != "" ? 1 : 0',
     "  count          = var.stratus_guardrails_enabled ? 1 : 0"),
]

TESTS = {
    "M4448": _WILDCARD,
    "M4449": _WILDCARD,
    "M4450": _MEASURED,
    "M4451": _MEASURED,
    "M4452": _BELT,
    "M4453": _G3_SCOPE,
    "M4454": _G3_ASSIGN,
    "M4455": _G3_ASSIGN,
    "M4456": _G4_EXACT,
    "M4457": _G4_ASSIGN,
    "M4458": _G2_TRUST,
    "M4459": _G2_TRUST,
    "M4460": _G2_TRUST,
}
