"""Lot R2BG (Partie de #608) — les garde-fous de l'abonnement de test dédié de Stratus, en
Terraform (infra/orodruin/stratus_guardrails.tf, variables.tf). Des bugs réinjectés un à un,
chacun attrapé par un test de tests/unit/test_stratus_guardrails.py. M5650–M5656.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
GUARD = "infra/orodruin/stratus_guardrails.tf"
VARS = "infra/orodruin/variables.tf"

_DIAG = ("tests/unit/test_stratus_guardrails.py::"
         "test_the_diagnostic_setting_routes_only_administrative_to_the_bench_workspace")
_AG_OUTSIDE = ("tests/unit/test_stratus_guardrails.py::"
               "test_the_budget_action_group_lives_outside_the_dedicated_subscription")
_CHECK = ("tests/unit/test_stratus_guardrails.py::"
          "test_a_check_refuses_pointing_at_orodruins_own_subscription")
_EMPTY_LIST = ("tests/unit/test_stratus_guardrails.py::"
               "test_the_allow_list_policies_do_not_fire_on_an_empty_list")
_DENY = ("tests/unit/test_stratus_guardrails.py::"
         "test_a_custom_policy_denies_a_public_ip_on_a_nic")
_OFF = ("tests/unit/test_stratus_guardrails.py::"
        "test_the_guardrails_are_off_by_default")
_NO_ROLE = ("tests/unit/test_stratus_guardrails.py::"
            "test_no_closed_role_is_granted_here_yet")

MUTANTS = [
    ("M5650", "the subscription diagnostic setting routes a wrong category (the watch would miss "
     "the techniques — Administrative is what AL1 reads)", GUARD,
     '    category = "Administrative"',
     '    category = "Security"'),
    ("M5651", "the budget's action group is glued to the dedicated subscription (stratus provider) "
     "— COLD/kill and « emptying the subscription » would then remove it", GUARD,
     '  name                = "ag-eregion-stratus-budget"',
     '  provider            = azurerm.stratus\n  name                = "ag-eregion-stratus-budget"'),
    ("M5652", "the check's inequality inverted: the guardrails would be allowed to point at "
     "Orodruin's own subscription (the v1 blocker)", GUARD,
     "      lower(var.stratus_subscription_id) != lower(data.azurerm_subscription.current.subscription_id)",
     "      lower(var.stratus_subscription_id) == lower(data.azurerm_subscription.current.subscription_id)"),
    ("M5653", "the allowed-locations policy no longer guarded on a non-empty list: an empty list "
     "in deny mode would refuse every creation", GUARD,
     "  count                = var.stratus_guardrails_enabled && length(var.stratus_allowed_locations) > 0 ? 1 : 0",
     "  count                = var.stratus_guardrails_enabled ? 1 : 0"),
    ("M5654", "the public-IP-on-a-NIC policy audits instead of denies (a NIC public IP would open "
     "an Internet egress bypassing « Orodruin without Internet »)", GUARD,
     '    then = { effect = "deny" }',
     '    then = { effect = "audit" }'),
    ("M5655", "the guardrails default on (not inert): a normal Orodruin apply would touch the "
     "dedicated subscription", VARS,
     'variable "stratus_guardrails_enabled" {\n'
     '  description = "Pose les garde-fous R2b (Azure Policy G5, paramètre de diagnostic G6, '
     'budget G7) sur l\'abonnement de test dédié de Stratus. Défaut false : rien ne s\'exécute. '
     'N\'active PAS le rôle fermé de Stratus (G3, après mesure)."\n'
     "  type        = bool\n"
     "  default     = false",
     'variable "stratus_guardrails_enabled" {\n'
     '  description = "Pose les garde-fous R2b (Azure Policy G5, paramètre de diagnostic G6, '
     'budget G7) sur l\'abonnement de test dédié de Stratus. Défaut false : rien ne s\'exécute. '
     'N\'active PAS le rôle fermé de Stratus (G3, après mesure)."\n'
     "  type        = bool\n"
     "  default     = true"),
    ("M5656", "a closed Stratus role (G3) is written here, before the minimal per-technique "
     "actions are measured (M1)", GUARD,
     "# Stratus — les garde-fous de l'abonnement de test dédié (R2b, #608).",
     "# Stratus — les garde-fous de l'abonnement de test dédié (R2b, #608).\n"
     'resource "azurerm_role_definition" "stratus_closed_premature" {}'),
]

TESTS = {
    "M5650": _DIAG,
    "M5651": _AG_OUTSIDE,
    "M5652": _CHECK,
    "M5653": _EMPTY_LIST,
    "M5654": _DENY,
    "M5655": _OFF,
    "M5656": _NO_ROLE,
}
