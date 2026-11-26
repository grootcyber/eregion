"""SKY2 (#1241): the watch at the heart of the 360° (Jonathan, 26/11). Each mutant takes a piece back: a running watch
not green (M7960), its age frozen between two reads (M7961), a stale watch's age said in seconds as minutes (M7962),
the header's pill no longer second by second (M7963), the 360°'s heart not the watch's tone (M7964), the 360° given no
heart (M7965), an unknown status said green (M7966); from the relecture: a stopped watch beating at each read
(M7967), a read that failed said green again at the next second (M7968, M7969, M7974), a running watch green past the
server's threshold between two reads (M7970), the heart beating at each read of the same beat (M7971), never beating
(M7972), beating for less motion (M7973). Measured by tests/unit/test_console_heart.py and
tests/unit/test_console_sky.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
CO_JS = "eregion_console/static/console.js"
SD_JS = "eregion_console/static/infra_sky_draw.js"
GF_JS = "eregion_console/static/glorfindel.js"

_H = "tests/unit/test_console_heart.py::"
_S = "tests/unit/test_console_sky.py::"

MUTANTS = [
    ("M7960", "a running watch not green (SKY2)", CO_JS,
     "  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[status] || 'dim';",
     "  const tone = { running: 'blue', stale: 'orange', stopped: 'red' }[status] || 'dim';"),
    ("M7961", "the watch's age frozen between two reads (SKY2)", CO_JS,
     "  const extra = w.seen ? Math.max(0, (now - w.seen) / 1000) : 0;", "  const extra = 0;"),
    ("M7962", "a stale watch's age in seconds said as minutes (SKY2)", CO_JS,
     "    : status === 'stale' ? `watch stale · ${Math.round(age / 60)}m ago` : `watch ${status || 'unknown'}`;",
     "    : status === 'stale' ? `watch stale · ${age}m ago` : `watch ${status || 'unknown'}`;"),
    ("M7963", "the header's pill no longer second by second (SKY2)", CO_JS,
     "    showWatch();                          // SKY2: the watch's age goes on with the clock\n", ""),
    ("M7964", "the 360°'s heart not the watch's tone (SKY2)", SD_JS,
     "    if (L.core.getAttribute('fill') !== col) L.core.setAttribute('fill', col);\n", ""),
    ("M7965", "the 360° given no heart: its core grey forever (SKY2)", GF_JS,
     "    heartOf: () => Console.watchSaid(Console.watchStatus(), Date.now()),\n", ""),
    ("M7966", "an unknown status said green (SKY2)", CO_JS,
     "  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[status] || 'dim';",
     "  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[status] || 'green';"),
    ("M7967", "a stopped watch beats at each read: its beat from the browser's clock (SKY2, relecture)", CO_JS,
     "  const beat = status === 'running' && typeof w.since === 'string' ? w.since : '';",
     "  const beat = w.seen ? String(Math.round(w.seen / 1000 - (Number(w.age_s) || 0))) : '';"),
    ("M7968", "a read that failed said as the last that succeeded (SKY2, relecture)", CO_JS,
     "  if (!w || typeof w !== 'object' || w.failed) return", "  if (!w || typeof w !== 'object') return"),
    ("M7969", "a read that failed keeps the last read as it was: green again at the next second (SKY2, relecture)", CO_JS,
     "      lastWatch = { ...(lastWatch || {}), failed: true, seen: Date.now() };", "      lastWatch = lastWatch;"),
    ("M7970", "a running watch said green past the server's threshold between two reads (SKY2, relecture)", CO_JS,
     "  const status = w.status === 'running' && raw >= WATCH_STALE_S ? 'stale' : w.status;",
     "  const status = w.status;"),
    ("M7971", "the heart beats at each read, the same beat read again (SKY2, relecture)", SD_JS,
     "    if (h.beat && h.beat !== lastBeat) {", "    if (h.beat) {"),
    ("M7972", "the heart never keeps the beat it saw: it never beats (SKY2, relecture)", SD_JS,
     "      lastBeat = h.beat;\n", ""),
    ("M7973", "the heart beats for whoever asks for less motion (SKY2, relecture)", SD_JS,
     "      if (lastBeat && !M.reduced) {", "      if (lastBeat) {"),
    ("M7974", "a read that failed not said until the next second (SKY2, relecture)", CO_JS,
     "      lastWatch = { ...(lastWatch || {}), failed: true, seen: Date.now() };   // SKY2: unknown until a read succeeds; the rest kept (IDT1)\n      showWatch();\n",
     "      lastWatch = { ...(lastWatch || {}), failed: true, seen: Date.now() };   // SKY2: unknown until a read succeeds; the rest kept (IDT1)\n"),
]

TESTS = {
    "M7960": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7961": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7962": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7963": f"{_H}test_the_header_says_the_watch_second_by_second_and_a_failed_read_stays_unknown",
    "M7964": f"{_H}test_the_360_s_heart_beats_once_at_each_new_beat_of_the_watch",
    "M7965": f"{_S}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M7966": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7967": f"{_H}test_a_beat_is_the_server_s_and_only_a_running_watch_s",
    "M7968": f"{_H}test_a_beat_is_the_server_s_and_only_a_running_watch_s",
    "M7969": f"{_H}test_the_header_says_the_watch_second_by_second_and_a_failed_read_stays_unknown",
    "M7970": f"{_H}test_past_the_server_s_threshold_a_running_watch_is_said_stale_between_two_reads",
    "M7971": f"{_H}test_the_360_s_heart_beats_once_at_each_new_beat_of_the_watch",
    "M7972": f"{_H}test_the_360_s_heart_beats_once_at_each_new_beat_of_the_watch",
    "M7973": f"{_H}test_the_360_s_heart_beats_once_at_each_new_beat_of_the_watch",
    "M7974": f"{_H}test_the_header_says_the_watch_second_by_second_and_a_failed_read_stays_unknown",
}
