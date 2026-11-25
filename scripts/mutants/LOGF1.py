"""LOGF1 (#1183): the watch says whether the workspace's logs still arrive. Each mutant takes a guard
back: a failed read written as « no log » (M7611), a failed read making a card « silent » (M7612), a card
at every pass of an episode (M7613), a card never closed when the logs come back (M7614), the threshold
taken whatever it reads (M7615), the reads off Log Analytics' budget (M7616), every table read at every
pass (M7617), the route without the field (M7618), a file of another form handed to the console as it is
(M7619), two tables silent folded into one card (M7620). After the review (25/11): an error's GUID or
URL shown, cut mid-id (M7641), a card for any table, Perf and Syslog included (M7642, the maintainer's
decision: the identity and the control plane only), a table no longer followed keeping its card (M7643),
a card the store cannot write stopping the pass (M7644), a `;` in a string cutting a statement (M7645),
the route broken by a module that raises (M7646), a budget of 1 letting no read through (M7647).
M7611–M7620 and M7641–M7647, measured by tests/unit/test_log_freshness.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
LF = "glorfindel/log_freshness.py"
ESC = "glorfindel/escalations.py"
API = "eregion_console/api.py"

_T = "tests/unit/test_log_freshness.py::"

MUTANTS = [
    ("M7611", "a read that failed written as a table read with no log (LOGF1)", LF,
     '        return {"last": None, "error": short_error(exc)}', '        return {"last": None, "error": None}'),
    ("M7612", "a read that failed is silent: a card « silent » on a 403 (LOGF1)", LF,
     '    if entry.get("error"):\n        return False\n    last = entry.get("last")',
     '    last = entry.get("last")'),
    ("M7613", "a card at every pass while the table stays silent (LOGF1)", LF,
     "                    if episode is None:\n                        self._open(table, e, now)",
     "                    self._open(table, e, now)"),
    ("M7614", "the card never closed when the logs come back (LOGF1)", LF,
     '                elif episode is not None and not e.get("error"):', "                elif False:"),
    ("M7615", "GLORFINDEL_LOG_SILENT_HOURS taken whatever it reads: 0, a negative, infinity (LOGF1)", LF,
     "    if math.isfinite(h) and MIN_H <= h <= MAX_H:", "    if h == h:"),
    ("M7616", "the reads off Log Analytics' budget: never left out, whatever the minute (LOGF1, DOS4)", LF,
     "        cap = self._budget.per_min()\n        if cap <= 0:", "        cap = 0\n        if cap <= 0:"),
    ("M7617", "every table read again at every pass of the watch, not every 15 min (LOGF1)", LF,
     "or (deferred is None and now - read >= EVERY_S)", "or (deferred is None and now - read >= 0)"),
    ("M7618", "/api/watch/status without the field: the console never greys a tile (LOGF1)", API,
     " | await asyncio.to_thread(_log_freshness)", ""),
    ("M7619", "a file of another form handed to the console as it is (LOGF1)", LF,
     "        field = _field_of(load(path))", "        field = load(path) or None"),
    ("M7620", "two tables silent folded into one card: the second never said (LOGF1)", ESC,
     '                and escalation_type != "logs_silent"\n', ""),
    ("M7641", "an error's text cut before it is masked: a workspace's or a tenant's id shown (LOGF1)", LF,
     "    line = _scrubbed(first)[:120]", "    line = first[:120]"),
    ("M7642", "a card logs_silent for any table followed, Perf and Syslog included (LOGF1, 25/11)", LF,
     "            if table not in self._carded:\n                continue\n", ""),
    ("M7643", "a table no longer followed: its episode dropped, its card left open (LOGF1)", LF,
     "        self._stale = {t: e for t, e in episodes.items() if t not in self._carded}",
     "        self._stale = {}"),
    ("M7644", "a card the store cannot write stops the pass: the file never written (LOGF1)", LF,
     "            except Exception as exc:\n                self._card_failure(table, exc)\n            else:",
     "            except ZeroDivisionError as exc:\n                self._card_failure(table, exc)\n            else:"),
    ("M7645", "a `;` in a text literal cuts the statement: a word of the string read for a table (LOGF1)", LF,
     """    code = _LITERALS.sub('""', _query_code(query))""", "    code = _query_code(query)"),
    ("M7646", "/api/watch/status broken by a freshness module that raises (LOGF1)", API,
     "console_field\"]).console_field()\n    except Exception:\n        return {}",
     "console_field\"]).console_field()\n    except ZeroDivisionError:\n        return {}"),
    ("M7647", "GLORFINDEL_LA_BUDGET_PER_MIN=1: half of it is 0, no read ever passes (LOGF1)", LF,
     "+ 1 > max(1, cap // 2):", "+ 1 > cap // 2:"),
]

TESTS = {
    "M7611": f"{_T}test_a_read_that_fails_is_an_error_never_no_log",
    "M7612": f"{_T}test_a_read_that_fails_is_an_error_never_no_log",
    "M7613": f"{_T}test_logs_silent_past_the_threshold_make_one_card_an_episode_and_per_table",
    "M7614": f"{_T}test_the_card_closes_when_the_logs_come_back_and_a_new_episode_makes_a_new_card",
    "M7615": f"{_T}test_the_threshold_is_read_strictly",
    "M7616": f"{_T}test_the_reads_are_on_the_budget_within_half_its_minute_and_never_refuse_the_detection",
    "M7617": f"{_T}test_each_table_is_read_every_15_minutes_not_at_every_pass",
    "M7618": f"{_T}test_the_route_carries_the_field_and_leaves_it_out_when_unreadable",
    "M7619": f"{_T}test_a_file_that_cannot_be_read_leaves_the_field_out",
    "M7620": f"{_T}test_logs_silent_past_the_threshold_make_one_card_an_episode_and_per_table",
    "M7641": f"{_T}test_a_read_that_fails_is_an_error_never_no_log",
    "M7642": f"{_T}test_only_the_identity_and_the_control_plane_open_a_card_the_others_stay_in_the_field",
    "M7643": f"{_T}test_a_table_no_longer_followed_has_its_episode_and_its_card_closed",
    "M7644": f"{_T}test_a_card_the_store_cannot_write_is_said_once_and_the_pass_still_writes_its_file",
    "M7645": f"{_T}test_a_semicolon_in_a_text_literal_never_cuts_a_statement",
    "M7646": f"{_T}test_the_route_stands_when_the_module_raises",
    "M7647": f"{_T}test_a_budget_of_one_still_lets_one_read_in_an_empty_minute",
}
