"""CPT1 (#930): a row of the control plane that names neither its caller nor its resource is a card
of incomplete telemetry — `medium`, visible in TO JUDGE, never approvable, never dropped; a row that
names one of the two keeps its card; the card names the caller by the ids the rules draw from
`Claims` when `Caller` is empty. M6406–M6419, measured by tests/unit/test_control_plane_incomplete.py."""
RULES = "glorfindel/detection_rules.py"
AGENT = "glorfindel/agent.py"
QUEUE = "eregion_core/action_queue.py"
_T = "tests/unit/test_control_plane_incomplete.py"

MUTANTS = [
    ("M6406", "a row that names no one and nothing is dispatched high again (CPT1)", RULES,
     '        if unnamed:\n            signal["severity"] = "medium"\n', ""),
    ("M6407", "a high signal on a row that names no one and nothing makes a high card (CPT1)", AGENT,
     '    if incomplete:\n        signal = {**signal, "severity": "medium"}\n', ""),
    ("M6408", "a row that names no one and nothing is dropped in silence, no card (CPT1)", RULES,
     "                new = [r for r in krows if _row_identity(r) not in seen]\n",
     "                new = [r for r in krows if _row_identity(r) not in seen and not names_no_one(r)]\n"),
    ("M6409", "the card of incomplete telemetry typed as an approvable card (CPT1)", AGENT,
     '    "control_plane_incomplete": "control_plane_change",\n',
     '    "control_plane_incomplete": "telemetry_gap",\n'),
    ("M6410", "the control-plane card approvable in one click (CPT1)", QUEUE,
     'APPROVABLE_TYPES |= {"floor_proposal"}', 'APPROVABLE_TYPES |= {"floor_proposal", "control_plane_change"}'),
    ("M6411", "a row that names its caller only lowered to incomplete telemetry (CPT1)", RULES,
     "    if any(_said(row.get(c)) for c in CALLER_COLUMNS) or _claims_name_someone(row):\n        return False\n",
     ""),
    ("M6412", "a row that names its resource only lowered to incomplete telemetry (CPT1)", RULES,
     "    return not any(_said(row.get(c)) for c in RESOURCE_COLUMNS)\n", "    return True\n"),
    ("M6413", "a caller's object id from Claims unread: « appelant inconnu » again (CPT1)", AGENT,
     '    oid = str(row.get("CallerObjectId") or "").strip()\n', '    oid = ""\n'),
    ("M6414", "a caller's application id from Claims unread: « appelant inconnu » again (CPT1)", AGENT,
     '    app = str(row.get("CallerAppId") or "").strip()\n', '    app = ""\n'),
    ("M6415", "a row whose lines name several callers lowered to incomplete telemetry (CPT1)", RULES,
     '        if int(row.get("Callers") or 0) > 0:\n', "        if False:\n"),
    ("M6416", "a grave row without caller nor resource no longer kept apart (CPT1)", RULES,
     "    if _grave(row):\n        return False\n    try:\n", "    try:\n"),
    ("M6417", "a summary card lowered to incomplete telemetry (CPT1)", RULES,
     'not row.get("OperationNameValue") or row.get("OmittedOperations"):',
     'not row.get("OperationNameValue"):'),
    ("M6418", "the card of incomplete telemetry no longer says so (CPT1)", AGENT,
     "    if names_no_one(row):\n        # CPT1", "    if False:\n        # CPT1"),
    ("M6419", "the card of incomplete telemetry loses its type, mapped to none (CPT1)", AGENT,
     '    "control_plane_incomplete": "control_plane_change",\n', ""),
]
TESTS = {
    "M6406": f"{_T}::test_a_bare_line_on_each_rule_is_a_card_of_incomplete_telemetry",
    "M6407": f"{_T}::test_a_high_signal_on_a_bare_row_is_still_a_medium_card",
    "M6408": f"{_T}::test_a_bare_line_on_each_rule_is_a_card_of_incomplete_telemetry",
    "M6409": f"{_T}::test_the_card_of_incomplete_telemetry_is_never_approvable",
    "M6410": f"{_T}::test_the_card_of_incomplete_telemetry_is_never_approvable",
    "M6411": f"{_T}::test_names_no_one_reads_every_column_that_names_a_caller_or_a_resource",
    "M6412": f"{_T}::test_a_line_naming_only_its_resource_keeps_its_high_card",
    "M6413": f"{_T}::test_an_empty_caller_with_its_object_id_in_claims_is_named",
    "M6414": f"{_T}::test_an_empty_caller_with_only_an_application_id_is_named_as_an_application",
    "M6415": f"{_T}::test_a_row_whose_lines_name_several_callers_is_not_missing_telemetry",
    "M6416": f"{_T}::test_a_grave_row_is_never_lowered",
    "M6417": f"{_T}::test_a_summary_card_and_a_data_row_are_not_cards_of_incomplete_telemetry",
    "M6418": f"{_T}::test_a_bare_line_on_each_rule_is_a_card_of_incomplete_telemetry",
    "M6419": f"{_T}::test_a_bare_line_on_each_rule_is_a_card_of_incomplete_telemetry",
}
