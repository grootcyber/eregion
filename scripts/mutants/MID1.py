"""MID1 (#981): the certificate Azure puts on a managed identity it creates, set aside from the shipped
entra-credential-added by the object id of the tenant's « Managed Service Identity » principal, never its
name — every other author, operation, target or credential a card, Glorfindel's marks first, nothing set
aside without the id, counted and said. One mutant per property, M6750–M6764, measured by
tests/unit/test_entra_msi.py and tests/unit/test_glorfindel_host.py."""
MSI = "glorfindel/providers/azure/entra_msi.py"
RULES = "glorfindel/detection_rules.py"
HOST_ENV = "infra/glorfindel-host/host_env.py"
JS = "eregion_console/static/glorfindel.js"
_T = "tests/unit/test_entra_msi.py"
_H = "tests/unit/test_glorfindel_host.py"

MUTANTS = [
    ("M6750", "the principal recognised by its name: any application named « Managed Service Identity » "
     "sets its certificates aside (MID1)", MSI,
     "    if str(row.get(\"ActorId\") or \"\").strip().lower() != msi:\n",
     "    if str(row.get(\"ActorName\") or \"\").strip().lower() != \"managed service identity\":\n"),
    ("M6751", "the operation not checked: a certificate added by « Update application » set aside (MID1)", MSI,
     "    if str(row.get(\"EntraOperation\") or \"\").strip().lower() != OPERATION:\n        return False\n",
     ""),
    ("M6752", "the key type not checked: a secret added by the principal set aside (MID1)", MSI,
     "        if pairs.get(\"keytype\", \"\").lower() != \"asymmetricx509cert\":\n            return False\n",
     ""),
    ("M6753", "set aside without an id: an id left empty matches a row whose ActorId the log left empty "
     "(MID1)", MSI,
     "    if not msi or not isinstance(row, dict):\n",
     "    if not isinstance(row, dict):\n"),
    ("M6754", "the count lost: the rows set aside no longer counted in the rule's status (MID1)", RULES,
     "                    \"rows\": was[\"msi_certificate_count\"] + msi[\"rows\"],\n",
     "                    \"rows\": was[\"msi_certificate_count\"],\n"),
    ("M6755", "Glorfindel's marks passed over: a certificate added on its identity set aside (MID1)", MSI,
     "    if row.get(\"GlorfindelIdentity\") is True or row.get(\"GlorfindelManaged\") is True:\n"
     "        return False\n",
     ""),
    ("M6756", "the usage not checked: a certificate of another usage set aside (MID1)", MSI,
     "        if pairs.get(\"keyusage\", \"\").lower() != \"verify\":\n            return False\n",
     ""),
    ("M6757", "the target type not checked: a certificate added to an application set aside (MID1)", MSI,
     "    if str(row.get(\"TargetType\") or \"\").strip().lower() != TARGET_TYPE:\n        return False\n",
     ""),
    ("M6758", "a key twice in a description read as its last one: a display name forges the key type "
     "(MID1)", MSI,
     "        if key in pairs:\n            return None\n",
     ""),
    ("M6759", "the first credential only: a certificate beside a secret sets the secret aside too (MID1)", MSI,
     "    for entry in added:\n",
     "    for entry in added[:1]:\n"),
    ("M6760", "an id that is no object id taken as one: nothing said, the problem hidden (MID1)", MSI,
     "    if not _GUID.fullmatch(value):\n        return \"\", \"malformed\"\n",
     ""),
    ("M6761", "any rule of that name: a rule of the client's layer that changed its query sets aside "
     "(MID1, ATT1's shape)", RULES,
     "            if cls is not None and shipped_query(rule.name, rule.query):\n",
     "            if cls is not None:\n"),
    ("M6762", "the ActorId compared with its case: the principal's id written in capitals by the log "
     "keeps its cards (MID1)", MSI,
     "    if str(row.get(\"ActorId\") or \"\").strip().lower() != msi:\n",
     "    if str(row.get(\"ActorId\") or \"\").strip() != msi:\n"),
    ("M6763", "--check no longer refuses an id that is no object id: pushed, the watch sets nothing aside "
     "(MID1)", HOST_ENV,
     "    if problem := msi_problem(model_value(env.get(MSI_ACTOR, \"\"))):     # MID1: refused\n"
     "        raise SystemExit(f\"{dst}: {problem}\")\n",
     ""),
    ("M6764", "the rule's line in the console no longer says the rows set aside (MID1)", JS,
     "      ${own}\n      ${msi}\n",
     "      ${own}\n"),
]
TESTS = {
    "M6750": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6751": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6752": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6753": f"{_T}::test_without_a_valid_id_nothing_is_set_aside_and_it_is_said",
    "M6754": f"{_T}::test_the_rows_of_the_20_11_make_no_card_and_are_counted_and_said",
    "M6755": f"{_T}::test_glorfindel_s_identity_comes_first_whoever_the_author",
    "M6756": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6757": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6758": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6759": f"{_T}::test_every_counter_case_stays_a_high_card",
    "M6760": f"{_T}::test_without_a_valid_id_nothing_is_set_aside_and_it_is_said",
    "M6761": f"{_T}::test_only_the_shipped_rule_to_the_byte_sets_aside",
    "M6762": f"{_T}::test_the_actor_id_is_compared_without_case",
    "M6763": f"{_H}::test_check_refuses_an_msi_principal_that_is_no_object_id_never_its_value",
    "M6764": f"{_T}::test_the_console_counts_the_rows_set_aside_on_the_rule",
}
