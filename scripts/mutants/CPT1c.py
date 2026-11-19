"""CPT1c (#940): a reply of the Activity Log out of the rule's schema — no operation, no caller, no
resource — is a card « réponse du journal illisible »: of a lower severity than high, never
approvable, never dropped, one per rule and poll with the number of its rows, said in the rule's
status; a grave row stays critical, a row of CPT1 stays « télémétrie incomplète ». M6536–M6545,
measured by tests/unit/test_control_plane_unreadable.py."""
RULES = "glorfindel/detection_rules.py"
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_control_plane_unreadable.py"

MUTANTS = [
    ("M6536", "the guard taken off: a reply out of schema is a high card that names no one again (CPT1c)",
     RULES, '            guard = self._plane(rule) == "control"\n', "            guard = False\n"),
    ("M6537", "the card of an unreadable reply typed as an approvable card (CPT1c)", AGENT,
     '    "control_plane_unreadable": "control_plane_change",\n',
     '    "control_plane_unreadable": "floor_proposal",\n'),
    ("M6538", "the card of an unreadable reply dispatched high (CPT1c)", RULES,
     '        unnamed = unnamed or (plane == "control" and not grave and unreadable_reply(row))\n',
     "        unnamed = unnamed\n"),
    ("M6539", "a high signal of an unreadable reply makes a high card (CPT1c)", AGENT,
     "    unreadable = _unreadable_reply(signal)\n", "    unreadable = False\n"),
    ("M6540", "one card per unreadable row, not one per rule and poll (CPT1c)", RULES,
     '                plan.append(("unreadable", None, [unreadable_card(unreadable)], []))\n',
     '                plan.append(("unreadable", None, [unreadable_card([r]) for r in unreadable], []))\n'),
    ("M6541", "a grave row out of schema folded into the medium card (CPT1c)", RULES,
     '    if not isinstance(row, dict) or row.get("OmittedOperations") or _grave(row):\n        return False\n'
     '    if any(_said(row.get(c)) for c in ("OperationNameValue",',
     '    if not isinstance(row, dict) or row.get("OmittedOperations"):\n        return False\n'
     '    if any(_said(row.get(c)) for c in ("OperationNameValue",'),
    ("M6542", "the unreadable rows marked sent without a card: lost (CPT1c)", RULES,
     '                plan.append(("unreadable", None, [unreadable_card(unreadable)], []))\n',
     "                pass\n"),
    ("M6543", "the rule's status no longer says its unreadable rows (CPT1c)", RULES,
     "            if unreadable:\n                # CPT1c: the reply out of the rule's schema, said",
     "            if False:\n                # CPT1c: the reply out of the rule's schema, said"),
    ("M6544", "a row of CPT1 (its operation alone) taken for an unreadable reply (CPT1c)", RULES,
     '    if any(_said(row.get(c)) for c in ("OperationNameValue", "CorrelationId", "ResourceGroup")):\n',
     '    if any(_said(row.get(c)) for c in ("CorrelationId", "ResourceGroup")):\n'),
    ("M6545", "the card no longer names the columns that are missing (CPT1c)", AGENT,
     '    if absent:\n        what += " Absentes : "', '    if False:\n        what += " Absentes : "'),
]
TESTS = {
    "M6536": f"{_T}::test_the_row_of_the_16_11_is_one_card_of_an_unreadable_reply",
    "M6537": f"{_T}::test_the_card_of_an_unreadable_reply_is_never_approvable",
    "M6538": f"{_T}::test_the_row_of_the_16_11_is_one_card_of_an_unreadable_reply",
    "M6539": f"{_T}::test_a_high_signal_of_the_16_11_replayed_is_a_medium_card",
    "M6540": f"{_T}::test_many_unreadable_rows_in_one_poll_are_one_card_with_their_number",
    "M6541": f"{_T}::test_a_grave_row_out_of_schema_stays_critical",
    "M6542": f"{_T}::test_the_row_of_the_16_11_is_one_card_of_an_unreadable_reply",
    "M6543": f"{_T}::test_the_row_of_the_16_11_is_one_card_of_an_unreadable_reply",
    "M6544": f"{_T}::test_a_row_of_cpt1_is_never_an_unreadable_reply",
    "M6545": f"{_T}::test_the_row_of_the_16_11_is_one_card_of_an_unreadable_reply",
}
