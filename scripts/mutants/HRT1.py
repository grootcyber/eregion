"""HRT1 (#1272): the watch leaves the header — said where Glorfindel is drawn, from one reading told to each place at
the same second; the return channel where its runs are (Jonathan, 27/11). Each mutant takes a piece back: the places
never told (M8175), a place that comes after the first read left blank until the next (M8176), a place's tone never
written — a missed beat said green (M8177), the table's GLORFINDEL without the watch (M8178), the overview's (M8179),
Dagorlad's from its own payload, another age than every other place (M8180), Dagorlad without the return channel
(M8181), a dead return channel said green (M8182); from the relecture: Dagorlad's head without V1, a run refused
said under a green watch (M8239), an age the return channel was not given said 0 s or NaN (M8240), the Runs view
without the watch (M8241), without V1 (M8242), a board unread that wipes Glorfindel's card (M8243), a place
rewritten every second whatever it says (M8244); from the second: the Runs view left grey after a read that failed,
the same answer again (M8245), the gate's uncached read of the heartbeat at each poll of /api/channel, Overview's too
(M8246), the console's look at the gate counted as an injector's (M8247). M8175–M8182 and M8239–M8247, measured by
tests/unit/test_console_watch_places.py and tests/unit/test_console_exercises.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
CO_JS = "eregion_console/static/console.js"
GF_JS = "eregion_console/static/glorfindel.js"
OV_JS = "eregion_console/static/overview.js"
DG_JS = "eregion_console/static/dagorlad.js"
IN_JS = "eregion_console/static/injector.js"
API = "eregion_console/api.py"

_T = "tests/unit/test_console_watch_places.py::"
_X = "tests/unit/test_console_exercises.py::"

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
    ("M8239", "Dagorlad's head without V1: a run refused said under a green watch (HRT1, relecture)", DG_JS,
     "    <div><b>GLORFINDEL</b> ${v1 ? `", "    <div><b>GLORFINDEL</b> ${false ? `"),
    ("M8240", "an age the return channel was not given said 0 s or NaN (HRT1, relecture)", CO_JS,
     "    const age = typeof c.age_s === 'number' && Number.isFinite(c.age_s) ? `${Math.round(c.age_s)}s ago` : 'age unknown';",
     "    const age = `${Number(c.age_s)}s ago`;"),
    ("M8241", "the Runs view without the watch (HRT1, relecture)", IN_JS,
     "    <span id=\"rn-watch\" style=\"color:var(--${esc(w.tone)})\" title=\"The watch's heartbeat (~/.glorfindel/watch_heartbeat)\">● ${esc(w.text)}</span>\n", ""),
    ("M8242", "the Runs view without V1: a run refused, not said where its runs are (HRT1, relecture)", IN_JS,
     "  const v1 = Console.gateSaid(err ? undefined : c.gate);", "  const v1 = null;"),
    ("M8243", "a board unread wipes Glorfindel's card: the watch and the return channel gone with it (HRT1, relecture)", DG_JS,
     "    blue.innerHTML = glorfindelCard(null);", "    blue.innerHTML = '';"),
    ("M8244", "a place rewritten every second whatever it says: its guards gone (HRT1, relecture)", CO_JS,
     "    if (el.textContent !== text) el.textContent = text;\n    if (el.style.color !== color) el.style.color = color;\n",
     "    el.textContent = text;\n    el.style.color = color;\n"),
    ("M8245", "the Runs view left grey after a read that failed: the same answer again never drawn (HRT1, relecture 2)", IN_JS,
     "    if (last[name] === text && !had) return false;", "    if (last[name] === text) return false;"),
    ("M8246", "the gate read at each poll of /api/channel, Overview's too: an uncached GET on the blob (HRT1, relecture 2)", API,
     "        **({\"gate\": await asyncio.to_thread(_watch_refusal)} if gate else {}),",
     "        **({\"gate\": await asyncio.to_thread(_watch_refusal)} if True else {}),"),
    ("M8247", "the console's look at the gate counted as an injector's: a replay refused for a run (HRT1, relecture 2)", API,
     "        return watch_gate.refusal(record=False)", "        return watch_gate.refusal()"),
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
    "M8239": f"{_T}test_dagorlad_s_glorfindel_says_the_console_s_watch_its_gate_and_the_return_channel",
    "M8240": f"{_T}test_the_return_channel_s_words",
    "M8241": f"{_T}test_the_runs_view_says_glorfindel_as_a_run_reads_it",
    "M8242": f"{_T}test_the_runs_view_says_glorfindel_as_a_run_reads_it",
    "M8243": f"{_T}test_a_board_unread_keeps_dagorlad_s_glorfindel_its_watch_and_its_return_channel",
    "M8244": f"{_T}test_a_place_is_written_only_when_its_words_or_its_tone_change",
    "M8245": f"{_T}test_the_runs_view_says_v1_again_once_a_failed_read_is_over",
    "M8246": f"{_X}test_channel_reads_the_gate_only_when_asked",
    "M8247": f"{_X}test_channel_says_v1_as_a_run_reads_it",
}
