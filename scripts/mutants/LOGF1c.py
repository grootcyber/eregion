"""LOGF1c (#1212): the logs' freshness read failed on every table in 0.6.8 — its column named `last`, a word
of KQL, a SyntaxError that Log Analytics answers in a 400 BadArgumentError — and `short_error` kept only
the first line, the inner error lost. Each mutant takes a guard back: the column a word of KQL again
(M7751), the read taking `last` while the query names another column (M7752), the inner error lost
(M7753), the inner error of a text alone never read (M7754), the inner error unmasked (M7755), the
outermost inner error said for the deepest (M7756), the inner error uncut (M7757), the guard blind to a
name after a comma (M7758), the guard letting `last` through (M7759), the guard reading a comparison for
a name (M7760). M7751–M7760, measured by tests/unit/test_log_freshness.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
LF = "glorfindel/log_freshness.py"
KQ = "glorfindel/kql.py"

_T = "tests/unit/test_log_freshness.py::"

MUTANTS = [
    ("M7751", "the freshness column named `last` again, a word of KQL: every read a 400 (LOGF1c)", LF,
     'COLUMN = "LastIngest"', 'COLUMN = "last"'),
    ("M7752", "the read takes `last` from its rows while the query names LastIngest: nothing read (LOGF1c)", LF,
     "lasts = [_iso(r.get(COLUMN))", 'lasts = [_iso(r.get("last"))'),
    ("M7753", "short_error loses the inner error: a 400 said « invalid properties », its SyntaxError unsaid (LOGF1c)",
     LF, '" — ".join(x for x in (head, _inner(exc), line) if x)', '" — ".join(x for x in (head, line) if x)'),
    ("M7754", "an error whose text alone carries « Inner error: » never read for it (LOGF1c)", LF,
     "        at = text.find(_INNER_LABEL)\n", "        at = -1\n"),
    ("M7755", "the inner error unmasked: a GUID, a URL shown (LOGF1c)", LF,
     "            return _scrubbed(said)[:INNER_MAX]", "            return said[:INNER_MAX]"),
    ("M7756", "the outermost inner error said for the deepest: the SyntaxError's cause lost (LOGF1c)", LF,
     "    for node in reversed(_inner_nodes(exc)):", "    for node in _inner_nodes(exc):"),
    ("M7757", "the inner error never cut (LOGF1c)", LF,
     "            return _scrubbed(said)[:INNER_MAX]", "            return _scrubbed(said)"),
    ("M7758", "the guard blind to a name after a comma: `summarize n = count(), last = max(x)` passes (LOGF1c)", KQ,
     r'project(?:-rename)?|by)\b|,)\s*', r'project(?:-rename)?|by)\b)\s*'),
    ("M7759", "the guard lets `last` through: 0.6.8's query passes (LOGF1c)", KQ,
     '"nulls", "first", "last", "let"', '"nulls", "first", "let"'),
    ("M7760", "the guard reads a comparison (`last == 1`) for a name (LOGF1c)", KQ,
     r'\s*=(?![=~])")', r'\s*=")'),
]

TESTS = {
    "M7751": f"{_T}test_the_query_names_no_word_of_kql_and_the_guard_was_red_on_0_6_8",
    "M7752": f"{_T}test_the_read_takes_its_value_under_the_column_the_query_names",
    "M7753": f"{_T}test_short_error_says_the_deepest_inner_error_of_an_azure_answer",
    "M7754": f"{_T}test_short_error_reads_the_inner_error_from_the_text_when_the_exception_has_no_error",
    "M7755": f"{_T}test_the_inner_error_is_masked_cut_and_the_deepest_that_says_something",
    "M7756": f"{_T}test_short_error_says_the_deepest_inner_error_of_an_azure_answer",
    "M7757": f"{_T}test_the_inner_error_is_masked_cut_and_the_deepest_that_says_something",
    "M7758": f"{_T}test_the_guard_reads_a_name_before_its_equal_sign_never_a_comparison",
    "M7759": f"{_T}test_the_query_names_no_word_of_kql_and_the_guard_was_red_on_0_6_8",
    "M7760": f"{_T}test_the_guard_reads_a_name_before_its_equal_sign_never_a_comparison",
}
