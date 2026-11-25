"""IDT1 (#1182): Entra ID and the control plane on the map as a VM is (Jonathan, 25/11, on a mockup). Each
mutant takes a piece back: the tile only with a card again (M7601), rules bound to nothing taken as watched
(M7602), the tiles not first in the row (M7603), a watch before LOGF1 shown grey (M7604), a read that
failed taken as « no log » (M7605), a threshold of the page's (M7606), a table read and empty not silent
(M7607), the health not on the dot (M7608), a poll in error hidden (M7609), the page never reading the
watch's status (M7610), a read that hangs kept green (M7649). M7601–M7610 and M7649, measured by tests/unit/test_console_watched_tiles.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
CON_JS = "eregion_console/static/console.js"

_T = "tests/unit/test_console_watched_tiles.py::"

MUTANTS = [
    ("M7601", "Entra ID's tile only with a card again: its absence says nothing (IDT1)", GF_JS,
     "    if (!resourceMap.has(w.tile) && _isWatched(kind))\n", "    if (false)\n"),
    ("M7602", "rules bound to no backend taken as watched: a tile that reads nothing (IDT1)", GF_JS,
     "return _watchedRules(kind).some(r => r.monitoring_backend_name); }", "return _watchedRules(kind).length > 0; }"),
    ("M7603", "the watched tiles not first in the row (IDT1)", GF_JS,
     "  resourceMap.clear(); _watchedFirst.forEach(([key, r]) => resourceMap.set(key, r));\n", ""),
    ("M7604", "a watch before LOGF1 shown grey, as if its logs were silent (IDT1)", GF_JS,
     "typeof lf.tables !== 'object') return { state: 'ok', said: '', logs: null };",
     "typeof lf.tables !== 'object') return { state: 'silent', short: 'no log', said: 'no log', logs: null };"),
    ("M7605", "a read of the logs that failed taken as « no log »: grey, not red (IDT1)", GF_JS,
     "  if (logs.every(l => l.error)) return { state: 'error', short: 'its logs not read', said: `logs not read: ${String(logs[0].error).slice(0, 160)}`, logs };\n", ""),
    ("M7606", "a threshold of the page's own, not the watch's (IDT1)", GF_JS,
     "  const hours = Number(lf.silent_after_hours);\n", "  const hours = 6;\n"),
    ("M7607", "a table read with no log in the window not silent (IDT1)", GF_JS,
     "(newest === undefined || Date.now() - newest > hours * 3600e3)", "(newest !== undefined && Date.now() - newest > hours * 3600e3)"),
    ("M7608", "the tile's health not on its dot: a poll in error green (IDT1)", GF_JS,
     "  const dotColor = health && health.state === 'error' ? 'var(--red)' : health && health.state === 'silent' ? 'var(--dim)'\n    : judgeOnly",
     "  const dotColor = judgeOnly"),
    ("M7609", "a rule's poll in error hidden: the tile says its logs only (IDT1)", GF_JS,
     "  if (failing) return { state: 'error',", "  if (false) return { state: 'error',"),
    ("M7610", "the page never reads the watch's status the header holds: never grey (IDT1)", CON_JS,
     "      lastWatch = w;                      // IDT1: what a page reads of the watch (its logs' freshness)\n", ""),
    ("M7649", "a read of the logs that hangs kept green: `read_at` frozen, the tile still says fresh (IDT1, LOGF1's relecture)", GF_JS,
     "  if (Number.isFinite(readAt) && Date.now() - readAt > _LOGS_READ_STALE_MS)\n", "  if (false)\n"),
]

TESTS = {
    "M7601": f"{_T}test_always_there_while_their_rules_run_first_in_the_row",
    "M7602": f"{_T}test_always_there_while_their_rules_run_first_in_the_row",
    "M7603": f"{_T}test_always_there_while_their_rules_run_first_in_the_row",
    "M7604": f"{_T}test_its_health_a_poll_in_error_first_then_its_logs",
    "M7605": f"{_T}test_its_health_a_poll_in_error_first_then_its_logs",
    "M7606": f"{_T}test_the_grey_is_the_watch_s_threshold_never_the_page_s",
    "M7607": f"{_T}test_the_grey_is_the_watch_s_threshold_never_the_page_s",
    "M7608": f"{_T}test_the_dot_says_the_health_before_the_cards",
    "M7609": f"{_T}test_its_health_a_poll_in_error_first_then_its_logs",
    "M7610": f"{_T}test_the_page_reads_the_watch_s_status_the_header_holds",
    "M7649": f"{_T}test_a_read_that_hangs_is_never_kept_green",
}
