"""IML1 (#688): the VM that carries Glorfindel is Imladris, and « H0 » never names it outside the history
(scripts/host_name.py); `make imladris-<x>` is `make glorfindel-host-<x>`. M4710–M4714.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
GUARD = "scripts/host_name.py"
T = "tests/unit/test_host_name.py::"

MUTANTS = [
    ("M4710", "every file read as history: H0 names the host anywhere, and nothing says so (IML1)", GUARD,
     "    if rel in HISTORY:\n",
     "    if True:\n"),
    ("M4711", "any H0 at the head of a list of lots read as a lot: « le CD de H0, H1 » kept (IML1)", GUARD,
     "    if _HEAD.search(before) and _NEXT.search(after):\n",
     "    if _NEXT.search(after):\n"),
    ("M4712", "the first mention never read: Imladris named without « anciennement H0 » (IML1)", GUARD,
     '        if rel.endswith(".md") and first_mention_unsaid(text):\n',
     "        if False:\n"),
    ("M4713", "a lot's phrase on a line keeps every H0 of the line, the host's too (IML1)", GUARD,
     "            if i <= start and end <= i + len(phrase):\n",
     "            if True:\n"),
    ("M4714", "the alias gone: make imladris-<x> has no rule (IML1)", "Makefile",
     "imladris-%: glorfindel-host-% ;\n",
     ""),
]
TESTS = {
    "M4710": T + "test_the_history_is_the_one_exception_for_the_name",
    "M4711": T + "test_h0_as_the_host_is_said",
    "M4712": T + "test_the_first_mention_of_a_document_says_it_was_h0",
    "M4713": T + "test_h0_as_the_host_is_said",
    "M4714": T + "test_make_imladris_is_make_glorfindel_host",
}
