"""CRD1 (#1011): an unusual sign-in of a service principal proposes to remove the one credential it used
— kept by the shipped query (`make_set(ServicePrincipalCredentialKeyId, 5)`, projected as
CredentialKeyIds), read as the SDK hands it on (its JSON text, by `own_channel.json_of`) —; several,
none, a value that is no keyId or a text illegible: the principal disabled, as before. And E-6.
M6942–M6951, measured by tests/unit/test_signin_credential.py (the shipped query, then the SDK's
objects, the RulePoller and the plan) and tests/unit/test_identity_plan.py."""
ITEMS = "glorfindel/providers/azure/entra_items.py"
RULES = "glorfindel/rules/azure/detection_rules.yaml"
_T = "tests/unit/test_signin_credential.py::"
_PROJECTED = "                SignIns, BaselineSignIns, BaselineDays, CredentialKeyIds, CorrelationId\n"
_LOST = "                SignIns, BaselineSignIns, BaselineDays, CorrelationId\n"

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
    "M6951": _T + "test_through_the_poller_two_credentials_the_card_proposes_to_disable",
}
