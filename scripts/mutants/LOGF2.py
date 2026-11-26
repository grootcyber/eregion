"""LOGF2 (#1233): the silence of a table of Entra ID judged by Entra, read on Graph; a fallback to 7 days
without the right. Each mutant takes a guard back: the read of Graph no longer `$top=1` (M7849), no longer
newest first (M7850), a 403 taken for « Entra has nothing » (M7851), the comparison reversed (M7852), the
ingestion's delay ignored (M7853), Entra with nothing read as a silence (M7854), the fallback back to 24 h
(M7855), a failure of Graph judged as a comparison (M7856), a read of Graph that never takes its budget
(M7857), the window of a table of Entra back to LOGF1's (M7858), a 403 that closes a card the comparison
opened (M7859), the console's field taking a `judged` of any value (M7860). After the review (26/11): the
cutoff's filter removed (M7890), the raw last event read (M7891), a table with no equivalent judged by Graph
(M7892), a date past the cutoff believed (M7893), a read put off for ever kept (M7894, M7895). M7849–M7860
and M7890–M7895, measured by tests/unit/test_entra_freshness.py.

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
     "silent = not failed and event is not None and event > floor\n",
     "silent = not failed and event is not None and event < floor\n"),
    ("M7853", "the ingestion's delay ignored: an event on its way already a card (LOGF2)", EF,
     "INGEST_DELAY_S = 900.0 ", "INGEST_DELAY_S = 0.0 "),
    ("M7854", "Entra with nothing read as a silence: an empty list, and no log in the window, a card (LOGF2)",
     EF, "silent = not failed and event is not None and event > floor\n",
     "silent = not failed and (event is None or event > floor)\n"),
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
    # After the review (26/11): M7890–M7895.
    ("M7890", "the cutoff's filter removed: Entra's newest event read, a cut hidden by a tenant that writes "
     "every few minutes (LOGF2, review)", EL,
     '    return path, {**params, "$filter": f"{field} le {_odata(cutoff)}"}, field\n',
     "    return path, dict(params), field\n"),
    ("M7891", "the raw last event read (cutoff now): a card opened, or kept, on an event still on its way "
     "(LOGF2, review)", EF, "**entra_last.last_event(self._reader, table, now - INGEST_DELAY_S)}",
     "**entra_last.last_event(self._reader, table, now)}"),
    ("M7892", "a table of Entra with no equivalent on Graph judged by it: the service principals' sign-ins on "
     "the 7-day fallback, not LOGF1's 24 h (LOGF2, review)", EF,
     'if plane == "identity" and t in SOURCES}', 'if plane == "identity"}'),
    ("M7893", "a date of Graph past the cutoff believed (LOGF2, review)", EL,
     "    if at > cutoff + FUTURE_MARGIN_S:\n", "    if False:\n"),
    ("M7894", "a read put off by the budget for ever keeps its last value, never the fallback (LOGF2, review)", EF,
     "        if since is not None and now - since > STALE_S:\n", "        if False:\n"),
    ("M7895", "each deferral restarts the count: a budget held for ever never falls back (LOGF2, review)", EF,
     '"deferred_since": prev.get("deferred_since") or _stamp(now)}', '"deferred_since": _stamp(now)}'),
]

TESTS = {
    "M7849": f"{_T}test_the_graph_requests_are_fixed_top_1_newest_first_up_to_the_cutoff",
    "M7850": f"{_T}test_the_graph_requests_are_fixed_top_1_newest_first_up_to_the_cutoff",
    "M7851": f"{_T}test_what_a_read_answers_a_failure_never_nothing",
    "M7852": f"{_T}test_the_card_opens_when_entra_has_an_event_not_received_after_15_min",
    "M7853": f"{_T}test_an_event_within_the_ingestion_s_delay_is_never_a_card",
    "M7854": f"{_T}test_entra_with_nothing_is_never_a_card",
    "M7855": f"{_T}test_without_graph_the_threshold_of_entra_is_7_days",
    "M7856": f"{_T}test_without_graph_the_threshold_of_entra_is_7_days",
    "M7857": f"{_T}test_each_read_of_graph_is_taken_on_its_budget_and_put_off_when_held",
    "M7858": f"{_T}test_a_table_of_entra_judged_by_graph_is_read_over_14_days",
    "M7859": f"{_T}test_a_card_opened_by_the_comparison_is_not_closed_by_a_403",
    "M7860": f"{_T}test_the_console_s_field_carries_the_verdict_read_strictly",
    "M7890": f"{_T}test_the_graph_requests_are_fixed_top_1_newest_first_up_to_the_cutoff",
    "M7891": f"{_T}test_a_card_open_is_never_closed_by_a_more_recent_event",
    "M7892": f"{_T}test_a_table_with_no_equivalent_keeps_logf1_s_24_h",
    "M7893": f"{_T}test_a_date_past_the_cutoff_is_not_believed",
    "M7894": f"{_T}test_a_read_put_off_for_more_than_30_min_falls_back_and_says_it",
    "M7895": f"{_T}test_a_read_put_off_for_more_than_30_min_falls_back_and_says_it",
}
