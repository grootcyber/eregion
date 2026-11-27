"""HRT1 (#1272): the watch leaves the header — said where Glorfindel is drawn, from one reading told to each place at
the same second; the return channel where its runs are (Jonathan, 27/11). Each mutant takes a piece back: the places
never told (M8175), a place that comes after the first read left blank until the next (M8176), a place's tone never
written — a missed beat said green (M8177), the table's GLORFINDEL without the watch (M8178), the overview's (M8179),
Dagorlad's from its own payload, another age than every other place (M8180), Dagorlad without the return channel
(M8181), a dead return channel said green (M8182). M8175–M8182, measured by tests/unit/test_console_watch_places.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
CO_JS = "eregion_console/static/console.js"
GF_JS = "eregion_console/static/glorfindel.js"
OV_JS = "eregion_console/static/overview.js"
DG_JS = "eregion_console/static/dagorlad.js"

_T = "tests/unit/test_console_watch_places.py::"

MUTANTS = [
    ("M8175", "the places never told the watch: each frozen at its first drawing (HRT1)", CO_JS,
     "    watchers.forEach(cb => { try { cb(s, lastWatch); } catch (_) { /* a place's own error, never the others' */ } });\n", ""),
    ("M8176", "a place that comes after the first read left blank until the next second (HRT1)", CO_JS,
     "    if (lastWatch) { try { cb(watchSaid(lastWatch, Date.now()), lastWatch); } catch (_) { /* its own */ } }\n", ""),
    ("M8177", "a place's tone never written: a missed beat said in the colour of the last read (HRT1)", CO_JS,
     "    if (el.style.color !== color) el.style.color = color;\n", ""),
    ("M8178", "the table's GLORFINDEL without the watch's beat (HRT1)", GF_JS,
     "    </div>\n    ${_agentWatch()}", "    </div>"),
    ("M8179", "the overview's GLORFINDEL without the watch's beat (HRT1)", OV_JS,
     "    ${watchLine()}\n", ""),
    ("M8180", "Dagorlad's GLORFINDEL from its own payload: another age than every other place (HRT1)", DG_JS,
     "  const w = Console.watchSaid(Console.watchStatus(), Date.now())", "  const w = Console.watchSaid(g.watch, Date.now())"),
    ("M8181", "Dagorlad's GLORFINDEL without the return channel its runs read (HRT1)", DG_JS,
     "    <div class=\"bmeta\" id=\"dg-rc\" style=\"color:var(--${esc(rc.tone)})\" title=\"${esc(rc.title)}\">● ${esc(rc.text)}</div>\n", ""),
    ("M8182", "a dead return channel said green: a run that reads it as no watch, said alive (HRT1)", CO_JS,
     "    return { tone: c.alive ? 'green' : 'yellow',", "    return { tone: 'green',"),
]

TESTS = {
    "M8175": f"{_T}test_every_place_is_told_the_same_reading_at_the_same_second",
    "M8176": f"{_T}test_every_place_is_told_the_same_reading_at_the_same_second",
    "M8177": f"{_T}test_every_place_is_told_the_same_reading_at_the_same_second",
    "M8178": f"{_T}test_the_table_s_glorfindel_says_the_watch_and_listens",
    "M8179": f"{_T}test_the_overview_s_glorfindel_says_the_watch_and_listens",
    "M8180": f"{_T}test_dagorlad_s_glorfindel_says_the_console_s_watch_its_gate_and_the_return_channel",
    "M8181": f"{_T}test_dagorlad_s_glorfindel_says_the_console_s_watch_its_gate_and_the_return_channel",
    "M8182": f"{_T}test_the_return_channel_s_words",
}
