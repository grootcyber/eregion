"""LOGF1b (#1191): the logs' freshness — a table the budget left out, the plane of each table, and the
limits LOGF1's review left. Each mutant takes a guard back: a table left out never said `deferred`
(M7671), a table read by two rules taking the last rule's plane (M7672), a rule of Entra ID misfiled on
Perf making Perf a card (M7673), the console's new keys taken whatever their form (M7674), an episode
whose card could not be closed dropped from the file (M7675), a dashed GUID stuck to a hex character
shown (M7676), a masked literal's `h` read for a table (M7677), a `//` in a string cutting its line
(M7678), the watch with no rule leaving its episodes open (M7679), a stale card closed and still held as
failed (M7680). M7671–M7680, measured by tests/unit/test_log_freshness.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
LF = "glorfindel/log_freshness.py"
LT = "glorfindel/watch/log_tasks.py"

_T = "tests/unit/test_log_freshness.py::"

MUTANTS = [
    ("M7671", "a table the budget left out never said `deferred`: the console reads its error as a failure (LOGF1b)",
     LF, '            t["error"], t["deferred"] = DEFERRED, True', '            t["error"] = DEFERRED'),
    ("M7672", "a table read by two rules of two planes takes the last rule's: its card lost (LOGF1b)", LF,
     "        if prev is None or PLANES.index(plane) < PLANES.index(prev):", "        if True:"),
    ("M7673", "a rule of Entra ID or of the control plane misfiled on Perf makes Perf a card (LOGF1b)", LF,
     '    if _DATA_TABLES.match(table):\n        return "data"\n', ""),
    ("M7674", "the console's new keys taken whatever their form: `deferred: \"true\"`, `plane: \"network\"` (LOGF1b)",
     LF, "        if not _new_keys_ok(e):\n            return None\n", ""),
    ("M7675", "an episode whose card could not be closed dropped from the file: its card left open (LOGF1b)", LF,
     '"episodes": {**self._stale, **self._episodes}}', '"episodes": self._episodes}'),
    ("M7676", "a dashed GUID stuck to a hex character shown in an error (LOGF1b)", LF,
     '_GUID = re.compile(r"[0-9a-f]{8}-', '_GUID = re.compile(r"(?<![0-9a-f])[0-9a-f]{8}-'),
    ("M7677", "a masked literal (`h'…'`) leaves its `h`, read for a table (LOGF1b)", LF,
     '_LITERALS = re.compile(r"(?:\\b[hH])?(?:', '_LITERALS = re.compile(r"(?:'),
    ("M7678", "a `//` in a string cuts its line: the table after it never read (LOGF1b)", LF,
     """else '""', query or "")""",
     """else '""', "\\n".join(x.split("//", 1)[0] for x in (query or "").splitlines()))"""),
    ("M7679", "the watch with no rule returns early: the episodes of its file never closed (LOGF1b)", LT,
     "        if self.dry_run:\n            return\n", "        if self.dry_run or not rules:\n            return\n"),
    ("M7680", "a stale card closed after a failure still held as failed (LOGF1b)", LF,
     "            else:\n                self._card_failed.discard(table)     # closed",
     "            else:\n                pass     # closed"),
]

TESTS = {
    "M7671": f"{_T}test_a_table_the_budget_left_out_is_deferred_its_last_value_kept_and_a_table_read_has_no_key",
    "M7672": f"{_T}test_a_table_read_by_two_rules_of_two_planes_takes_a_card_over_none_identity_first",
    "M7673": f"{_T}test_a_rule_of_entra_or_of_the_control_plane_misfiled_on_a_data_table_opens_no_card",
    "M7674": f"{_T}test_the_new_keys_of_another_form_leave_the_whole_field_out",
    "M7675": f"{_T}test_an_episode_whose_card_could_not_be_closed_is_written_back_and_closed_later",
    "M7676": f"{_T}test_a_guid_with_its_dashes_is_masked_even_stuck_to_a_hex_character",
    "M7677": f"{_T}test_a_masked_literal_is_a_literal_never_its_h_read_for_a_table",
    "M7678": f"{_T}test_a_double_slash_in_a_string_cuts_nothing_and_a_quote_in_a_comment_opens_nothing",
    "M7679": f"{_T}test_every_rule_removed_the_watch_still_closes_the_episodes_of_its_file",
    "M7680": f"{_T}test_a_stale_card_closed_after_a_failure_is_no_longer_held_as_failed",
}
