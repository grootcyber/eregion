"""CRD1 (#1011): an unusual sign-in of a service principal proposes to remove the one credential it used
— kept by the shipped query (`make_set(ServicePrincipalCredentialKeyId, 5)`, projected as
CredentialKeyIds), read as the SDK hands it on (its JSON text, by `own_channel.json_of`) —; several,
none, a value that is no keyId or a text illegible: the principal disabled, as before. And E-6.
M6942–M6951 and M7000–M7004 (the review), measured by tests/unit/test_signin_credential.py (the shipped query, then the SDK's
objects, the RulePoller and the plan) and tests/unit/test_identity_plan.py."""
ITEMS = "glorfindel/providers/azure/entra_items.py"
PLAN = "glorfindel/providers/azure/entra_plan.py"
RULES = "glorfindel/rules/azure/detection_rules.yaml"
_T = "tests/unit/test_signin_credential.py::"
_PROJECTED = "BaselineDays, CredentialKeyIds, FederatedSignIns"
_LOST = "BaselineDays, FederatedSignIns"

MUTANTS = [
    ("M6942", "the credential lost by the shipped query: its set gathered, never projected — the plan "
     "always disables the principal (CRD1)", RULES, _PROJECTED, _LOST),
    ("M6943", "a keyId Graph finds on neither object still proposed for removal (a federated sign-in's, or "
     "one already removed): the principal never disabled (CRD1)", ITEMS,
     "            used, why_not = \"\", (\"ni l'application",
     "            items.append(_remove_credential(\"applications\", _param(\"id de l'objet\", \"\", \"\", \"absent\"), "
     "key_p, \"\", name))\n            used, why_not = used, (\"ni l'application"),
    ("M6944", "several credentials taken for one by the query: a set of one, the first sign-in's key "
     "proposed for removal while another still signs in (CRD1)", RULES,
     "make_set(ServicePrincipalCredentialKeyId, 5)", "make_set(ServicePrincipalCredentialKeyId, 1)"),
    ("M6945", "several credentials taken for one by the reader: the first of the set proposed for "
     "removal (CRD1)", ITEMS,
     "    if len(value) > 1:\n", "    if len(value) > 5:\n"),
    ("M6946", "a sign-in that named no credential left out of the set: the key of the other proposed "
     "for removal, the unnamed one still signs in (CRD1)", ITEMS,
     "    if len(value) > 1:\n", "    value = [v for v in value if v]\n    if len(value) > 1:\n"),
    ("M6947", "the removal proposed without a credential: a keyId never read, the principal never "
     "disabled (CRD1)", ITEMS,
     "    used, why_not = used_credential(row)\n",
     "    used, why_not = used_credential(row)\n    used = used or \"<keyId>\"\n"),
    ("M6948", "a credential that is no GUID accepted: a field of the log in the removal's command "
     "(CRD1)", ITEMS,
     "    key = guid(first) if isinstance(first, str) else \"\"\n",
     "    key = str(first).strip().lower()\n"),
    ("M6949", "the JSON text not decoded: the SDK's text never read as a set, the plan always "
     "disables the principal (CRD1)", ITEMS,
     "    if isinstance(value, str):\n        value = json_of(value)\n", ""),
    ("M6950", "the JSON text decoded without its net: an illegible text raises out of the plan "
     "(CRD1)", ITEMS,
     "        value = json_of(value)\n", "        value = __import__(\"json\").loads(value)\n"),
    ("M7000", "never_target not asked of the sign-in's subject: a listed principal's used credential removed "
     "by default, its reason never said (CRD1, review)", PLAN,
     "            extra = next((w for w in (protected(x) for x in subject) if w), \"\")\n",
     "            extra = \"\"\n"),
    ("M7001", "the removal of a sign-in's credential not counted as a cut: a listed principal's plan without "
     "IR1f's check first (CRD1, review)", PLAN,
     "_SIGNIN_CUTS = _CUTS + (\"entra_remove_credential\",)", "_SIGNIN_CUTS = _CUTS"),
    ("M7002", "the list unreadable, a verb whose target's id is not read stays the executor's (CRD1, review)",
     PLAN,
     "            if not extra and not i[\"target\"].get(\"id\") and getattr(protected, \"unreadable\", False):\n",
     "            if False:\n"),
    ("M7003", "a federated sign-in's keyId proposed for removal: the count read, never heeded (CRD1, review)",
     ITEMS, "    if federated != 0:\n", "    if federated < 0:\n"),
    ("M7004", "the federated sign-ins lost by the shipped query: counted, never projected (CRD1, review)",
     RULES, "BaselineDays, CredentialKeyIds, FederatedSignIns, CorrelationId",
     "BaselineDays, CredentialKeyIds, CorrelationId"),
    ("M6951", "E-6 back: « Bloquer la connexion de le principal de service » (CRD1)", ITEMS,
     "        f\"Bloquer la connexion {_of(label)} ", "        f\"Bloquer la connexion de {label} "),
]
TESTS = {
    "M6942": _T + "test_one_credential_used_proposes_its_removal",
    "M6943": _T + "test_a_key_id_graph_finds_on_neither_object_proposes_to_disable",
    "M6944": _T + "test_two_credentials_used_propose_to_disable_the_principal",
    "M6945": _T + "test_two_credentials_used_propose_to_disable_the_principal",
    "M6946": _T + "test_a_sign_in_that_names_no_credential_beside_one_that_does_is_two",
    "M6947": _T + "test_no_credential_named_proposes_to_disable_the_principal",
    "M6948": _T + "test_a_value_that_is_no_key_id_proposes_nothing_more_than_disabling",
    "M6949": _T + "test_one_credential_used_proposes_its_removal",
    "M6950": _T + "test_an_illegible_text_proposes_to_disable_the_principal_and_never_raises",
    "M7000": _T + "test_a_listed_principal_s_used_credential_is_never_removed_by_default",
    "M7001": _T + "test_a_listed_principal_s_used_credential_is_never_removed_by_default",
    "M7002": _T + "test_an_unreadable_list_an_empty_target_of_another_card_is_a_human_s_too",
    "M7003": _T + "test_a_federated_sign_in_proposes_to_disable_the_principal",
    "M7004": _T + "test_the_query_counts_the_federated_sign_ins",
    "M6951": _T + "test_through_the_poller_two_credentials_the_card_proposes_to_disable",
}
