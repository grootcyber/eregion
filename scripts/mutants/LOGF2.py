"""LOGF2 (#1233): the silence of a table of Entra ID judged by Entra, read on Graph; a fallback to 7 days
without the right. Each mutant takes a guard back: the read of Graph no longer `$top=1` (M7849), no longer
newest first (M7850), a 403 taken for « Entra has nothing » (M7851), the comparison reversed (M7852), the
ingestion's delay ignored (M7853), Entra with nothing read as a silence (M7854), the fallback back to 24 h
(M7855), a failure of Graph judged as a comparison (M7856), a read of Graph that never takes its budget
(M7857), the window of a table of Entra back to LOGF1's (M7858), a 403 that closes a card the comparison
opened (M7859), the console's field taking a `judged` of any value (M7860). M7849–M7860, measured by
tests/unit/test_entra_freshness.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
EL = "glorfindel/providers/azure/entra_last.py"
EF = "glorfindel/entra_freshness.py"
LF = "glorfindel/log_freshness.py"

_T = "tests/unit/test_entra_freshness.py::"

MUTANTS = [
    ("M7849", "the read of Entra's audit log no longer `$top=1`: a page of events for one date (LOGF2)", EL,
     '{"$top": "1", "$orderby": "activityDateTime desc"}', '{"$top": "10", "$orderby": "activityDateTime desc"}'),
    ("M7850", "the read of Entra's audit log oldest first: its first event taken for its last (LOGF2)", EL,
     '{"$top": "1", "$orderby": "activityDateTime desc"}', '{"$top": "1", "$orderby": "activityDateTime asc"}'),
    ("M7851", "a 403 taken for « Entra has nothing »: the right missing, never a card, never said (LOGF2)", EL,
     '    except Unreadable as exc:\n        return {"last": None, "error": _said(exc)}',
     '    except Unreadable as exc:\n        return {"last": None, "error": None}'),
    ("M7852", "the comparison reversed: a lost event never a card, a calm tenant one (LOGF2)", EF,
     "event is not None and event > floor and", "event is not None and event < floor and"),
    ("M7853", "the ingestion's delay ignored: an event on its way already a card (LOGF2)", EF,
     "and now - event > INGEST_DELAY_S)", "and now - event >= 0)"),
    ("M7854", "Entra with nothing read as a silence: an empty list, and no log in the window, a card (LOGF2)",
     EF, "silent = (not failed and event is not None and event > floor",
     "silent = (not failed and (event is None or event > floor)"),
    ("M7855", "the fallback back to 24 h: a calm tenant without the right, a card again after a day (LOGF2)", EF,
     "FALLBACK_H = 168.0 ", "FALLBACK_H = 24.0 "),
    ("M7856", "a failure of Graph judged as a comparison: without the right, never a card, even after 8 days "
     "(LOGF2)", EF, '    if graph is None or graph.get("error"):\n', "    if graph is None:\n"),
    ("M7857", "a read of Graph that never takes its budget: read whatever the minute holds (LOGF2)", EF,
     "        return self._budget.take(1, WHO)\n", "        return True\n"),
    ("M7858", "the window of a table of Entra back to LOGF1's: the last log of a calm tenant out of it (LOGF2)",
     LF, "return window_hours(FALLBACK_H if table in self._judged_by_entra else self.hours)",
     "return window_hours(self.hours)"),
    ("M7859", "a 403 closes a card the comparison opened: « logs back » while the event never came (LOGF2)", EF,
     "    return seen is None or seen < opened_on\n", "    return False\n"),
    ("M7860", "the console's field takes a `judged` of any value (LOGF2)", EF,
     '    return (("judged" not in e or e["judged"] in JUDGED)', '    return (("judged" not in e or True)'),
]

TESTS = {
    "M7849": f"{_T}test_the_graph_requests_are_fixed_top_1_newest_first",
    "M7850": f"{_T}test_the_graph_requests_are_fixed_top_1_newest_first",
    "M7851": f"{_T}test_what_a_read_answers_a_failure_never_nothing",
    "M7852": f"{_T}test_the_card_opens_when_entra_has_an_event_not_received_after_15_min",
    "M7853": f"{_T}test_an_event_within_the_ingestion_s_delay_is_never_a_card",
    "M7854": f"{_T}test_entra_with_nothing_is_never_a_card",
    "M7855": f"{_T}test_without_graph_the_threshold_of_entra_is_7_days",
    "M7856": f"{_T}test_without_graph_the_threshold_of_entra_is_7_days",
    "M7857": f"{_T}test_each_read_of_graph_is_taken_on_its_budget_and_put_off_when_held",
    "M7858": f"{_T}test_a_table_of_entra_is_read_over_14_days",
    "M7859": f"{_T}test_a_card_opened_by_the_comparison_is_not_closed_by_a_403",
    "M7860": f"{_T}test_the_console_s_field_carries_the_verdict_read_strictly",
}
