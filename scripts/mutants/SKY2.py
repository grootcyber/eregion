"""SKY2 (#1241): the watch at the heart of the 360° (Jonathan, 26/11). Each mutant takes a piece back: a running watch
not green (M7960), its age frozen between two reads (M7961), a stale watch's age said in seconds as minutes (M7962),
the header's pill no longer second by second (M7963), the 360°'s heart not the watch's tone (M7964), the 360° given no
heart (M7965), an unknown status said green (M7966). Measured by tests/unit/test_console_heart.py and
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
     "  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[w.status] || 'dim';",
     "  const tone = { running: 'blue', stale: 'orange', stopped: 'red' }[w.status] || 'dim';"),
    ("M7961", "the watch's age frozen between two reads (SKY2)", CO_JS,
     "  const extra = w.seen ? Math.max(0, (now - w.seen) / 1000) : 0;", "  const extra = 0;"),
    ("M7962", "a stale watch's age in seconds said as minutes (SKY2)", CO_JS,
     "    : w.status === 'stale' ? `watch stale · ${Math.round(age / 60)}m ago` : `watch ${w.status || 'unknown'}`;",
     "    : w.status === 'stale' ? `watch stale · ${age}m ago` : `watch ${w.status || 'unknown'}`;"),
    ("M7963", "the header's pill no longer second by second (SKY2)", CO_JS,
     "    showWatch();                          // SKY2: the watch's age goes on with the clock\n", ""),
    ("M7964", "the 360°'s heart not the watch's tone (SKY2)", SD_JS,
     "    if (L.core.getAttribute('fill') !== col) L.core.setAttribute('fill', col);\n", ""),
    ("M7965", "the 360° given no heart: its core grey forever (SKY2)", GF_JS,
     "    heartOf: () => Console.watchSaid(Console.watchStatus(), Date.now()),\n", ""),
    ("M7966", "an unknown status said green (SKY2)", CO_JS,
     "  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[w.status] || 'dim';",
     "  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[w.status] || 'green';"),
]

TESTS = {
    "M7960": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7961": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7962": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
    "M7963": f"{_H}test_the_header_says_it_from_the_same_source_second_by_second",
    "M7964": f"{_H}test_the_360_s_heart_is_the_watch_and_beats_with_it",
    "M7965": f"{_S}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M7966": f"{_H}test_the_watch_says_its_tone_and_its_age_the_header_s_words",
}
