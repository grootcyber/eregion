"""IML1 (#688): the VM that carries Glorfindel is Imladris, and « H0 » never names it outside the history
(scripts/host_name.py); `make imladris-<x>` is `make glorfindel-host-<x>`. M4710–M4714; after the
review (round 1), M4771–M4772 (a kept text gone unsaid, the first cell of any table read as a lot).

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
GUARD = "scripts/host_name.py"
T = "tests/unit/test_host_name.py::"

MUTANTS = [
    ("M4710", "every file read as history: H0 names the host anywhere, and nothing says so (IML1)", GUARD,
     "    if rel in HISTORY:\n",
     "    if True:\n"),
    ("M4711", "any H0 at the head of a list read as a lot: « H0 et O1 tirent l'image » kept (IML1)", GUARD,
     "    if _HEAD.search(before) and _NEXT.match(after):\n",
     "    if _HEAD.search(before) and _LIST_GOES_ON.match(after):\n"),
    ("M4712", "the first mention never read: Imladris named without « anciennement H0 » (IML1)", GUARD,
     '        if rel.endswith(".md") and not rel.startswith(FIRST_MENTION_NOT) and first_mention_unsaid(text):\n',
     "        if False:\n"),
    ("M4713", "a lot's phrase on a line keeps every H0 of the line, the host's too (IML1)", GUARD,
     "            if i <= start and end <= i + len(text):\n",
     "            if True:\n"),
    ("M4714", "the alias gone: make imladris-<x> has no rule (IML1)", "Makefile",
     "imladris-%: glorfindel-host-% ;\n",
     ""),
]
MUTANTS += [
    ("M4771", "a kept text renamed unsaid: the KQL comment changes the rule's WL1 fingerprint (IML1 review)",
     GUARD,
     "            if kept not in text:\n",
     "            if False:\n"),
    ("M4772", "the first cell of any table read as a lot: « | H0 | 10.0.0.4 | » kept (IML1 review)", GUARD,
     "    if lot_table and _CELL_BEFORE.match(before) and _CELL_AFTER.match(after):\n",
     "    if _CELL_BEFORE.match(before) and _CELL_AFTER.match(after):\n"),
]
TESTS = {
    "M4710": T + "test_the_history_is_the_one_exception_for_the_name",
    "M4711": T + "test_h0_as_the_host_is_said",
    "M4712": T + "test_the_first_mention_of_a_document_says_it_was_h0",
    "M4713": T + "test_h0_as_the_host_is_said",
    "M4714": T + "test_make_imladris_is_make_glorfindel_host",
    "M4771": T + "test_a_kept_text_renamed_or_a_quotation_its_source_no_longer_says_is_said",
    "M4772": T + "test_the_first_cell_is_a_lot_in_a_table_of_lots_only",
}
