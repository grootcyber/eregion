"""Lot R2BG (Partie de #608) — les garde-fous de l'abonnement de test dédié de Stratus, en
Terraform (infra/orodruin/stratus_guardrails.tf, variables.tf). Des bugs réinjectés un à un,
chacun attrapé par un test de tests/unit/test_stratus_guardrails.py. M5650–M5659.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
GUARD = "infra/orodruin/stratus_guardrails.tf"
VARS = "infra/orodruin/variables.tf"

_DIAG = ("tests/unit/test_stratus_guardrails.py::"
         "test_the_diagnostic_setting_routes_only_administrative_to_the_bench_workspace")
_AG_OUTSIDE = ("tests/unit/test_stratus_guardrails.py::"
               "test_the_budget_action_group_lives_outside_the_dedicated_subscription")
_PRECOND = ("tests/unit/test_stratus_guardrails.py::"
            "test_a_precondition_refuses_pointing_at_orodruins_own_subscription")
_EMPTY_LIST = ("tests/unit/test_stratus_guardrails.py::"
               "test_the_allow_list_policies_do_not_fire_on_an_empty_list")
_DENY = ("tests/unit/test_stratus_guardrails.py::"
         "test_a_custom_policy_denies_a_public_ip_on_a_nic")
_OFF = ("tests/unit/test_stratus_guardrails.py::"
        "test_the_guardrails_are_off_by_default")
# M5656 (« un rôle fermé écrit avant la mesure M1 ») et son test _NO_ROLE ont été retirés par
# R2BGc (#608) : le rôle fermé G3/G4/G2 est maintenant écrit ici (M1 mesuré), l'invariant « pas
# encore de rôle » n'a plus lieu d'être. Les nouveaux invariants vivent dans scripts/mutants/R2BGc.py.
_ALIAS = ("tests/unit/test_stratus_guardrails.py::"
          "test_the_alias_provider_targets_the_dedicated_subscription")
_PROVIDER_EACH = ("tests/unit/test_stratus_guardrails.py::"
                  "test_every_dedicated_subscription_resource_declares_the_stratus_provider")
_NIC_ANY = ("tests/unit/test_stratus_guardrails.py::"
            "test_the_nic_public_ip_policy_matches_any_ip_config")
_GUID = ("tests/unit/test_stratus_guardrails.py::"
         "test_the_subscription_id_is_validated_as_a_guid")
_DEPEND = ("tests/unit/test_stratus_guardrails.py::"
           "test_every_dedicated_subscription_resource_depends_on_the_guard")

MUTANTS = [
    ("M5650", "the subscription diagnostic setting routes a wrong category (the watch would miss "
     "the techniques — Administrative is what AL1 reads)", GUARD,
     '    category = "Administrative"',
     '    category = "Security"'),
    ("M5651", "the budget's action group is glued to the dedicated subscription (stratus provider) "
     "— COLD/kill and « emptying the subscription » would then remove it", GUARD,
     '  name                = "ag-eregion-stratus-budget"',
     '  provider            = azurerm.stratus\n  name                = "ag-eregion-stratus-budget"'),
    ("M5652", "the precondition's inequality inverted: the guardrails would be allowed to point at "
     "Orodruin's own subscription (the v1 blocker)", GUARD,
     "        lower(var.stratus_subscription_id) != lower(data.azurerm_subscription.current.subscription_id)",
     "        lower(var.stratus_subscription_id) == lower(data.azurerm_subscription.current.subscription_id)"),
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
     'ne se pose que si stratus_client_id est donné."\n'
     "  type        = bool\n"
     "  default     = false",
     'ne se pose que si stratus_client_id est donné."\n'
     "  type        = bool\n"
     "  default     = true"),
    # M5656 retiré par R2BGc (#608) : il injectait un rôle fermé « prématuré » et s'appuyait sur
    # l'invariant « pas encore de rôle ici », que R2BGc lève (le rôle G3/G4/G2 est maintenant écrit,
    # M1 mesuré). Les invariants du rôle fermé vivent dans scripts/mutants/R2BGc.py.
    ("M5657", "the aliased provider is repointed at Orodruin's own subscription variable "
     "(var.subscription_id) instead of the dedicated one", GUARD,
     '  subscription_id = var.stratus_subscription_id != "" ? var.stratus_subscription_id : null',
     '  subscription_id = var.subscription_id != "" ? var.subscription_id : null'),
    ("M5658", "a dedicated-subscription resource (the public-IP policy definition) loses its "
     "azurerm.stratus provider and falls back to Orodruin's subscription", GUARD,
     "provider     = azurerm.stratus",
     "provider     = azurerm.default"),
    ("M5659", "the public-IP-on-a-NIC match reverts to the naive « all ipConfigs » form "
     "(notLike → like): a NIC with one public and one private ipConfig would slip past", GUARD,
     'notLike = "*"',
     'like    = "*"'),
    ("M5660", "the `not { … }` wrapper of the NIC rule is dropped (not → allOf): the policy "
     "inverts — a fully-private NIC is denied, a 100%-public one passes", GUARD,
     "not = {",
     "allOf = {"),
    ("M5661", "stratus_subscription_id loses its GUID format validation (regex → true): the path "
     "form /subscriptions/<guid> would slip past and bypass the precondition", VARS,
     'can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.stratus_subscription_id))',
     "true"),
    ("M5662", "a dedicated-subscription resource (the diagnostic setting) reads "
     "var.stratus_subscription_id directly again instead of the guard's validated output", GUARD,
     'terraform_data.stratus_guard.output}"\n  log_analytics_workspace_id',
     'var.stratus_subscription_id}"\n  log_analytics_workspace_id'),
]

TESTS = {
    "M5650": _DIAG,
    "M5651": _AG_OUTSIDE,
    "M5652": _PRECOND,
    "M5653": _EMPTY_LIST,
    "M5654": _DENY,
    "M5655": _OFF,
    "M5657": _ALIAS,
    "M5658": _PROVIDER_EACH,
    "M5659": _NIC_ANY,
    "M5660": _NIC_ANY,
    "M5661": _GUID,
    "M5662": _DEPEND,
}
