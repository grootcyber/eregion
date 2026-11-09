"""CAN3 (#673): the azurerm canary's OIDC sign-ins set aside from `entra-sp-unusual-signin` in the
bench's client layer (infra/glorfindel-host/client_rules.bench.yaml), by its principal and its
federated credential together; its appid taken from the watch's environment (`env_guids`, CAN2's
mechanism and variable). One mutant per condition of the exclusion, M4636–M4638, measured by
tests/unit/test_canary_signin.py."""
BENCH = "infra/glorfindel-host/client_rules.bench.yaml"
_TESTS = "tests/unit/test_canary_signin.py"

MUTANTS = [
    ("M4636", "the canary's principal set aside whatever its credential: its sign-in by a secret or a "
     "certificate makes no card (CAN3)", BENCH,
     "      | where not(AppId =~ \"${EREGION_RULE_CANARY_APPID}\"\n"
     "            and ClientCredentialType =~ \"federatedIdentityCredential\"\n"
     "            and isnotempty(FederatedCredentialId))\n",
     "      | where not(AppId =~ \"${EREGION_RULE_CANARY_APPID}\")\n"),
    ("M4637", "any principal's federated sign-in set aside, not the canary's alone (CAN3)", BENCH,
     "      | where not(AppId =~ \"${EREGION_RULE_CANARY_APPID}\"\n"
     "            and ClientCredentialType",
     "      | where not(ClientCredentialType"),
    ("M4638", "a sign-in said federated but naming no federated credential set aside (CAN3)", BENCH,
     "            and ClientCredentialType =~ \"federatedIdentityCredential\"\n"
     "            and isnotempty(FederatedCredentialId))\n",
     "            and ClientCredentialType =~ \"federatedIdentityCredential\")\n"),
]
TESTS = {
    "M4636": f"{_TESTS}::test_the_canary_s_principal_by_another_credential_makes_a_card",
    "M4637": f"{_TESTS}::test_another_principal_s_federated_sign_in_makes_a_card",
    "M4638": f"{_TESTS}::test_the_canary_s_principal_by_another_credential_makes_a_card",
}
