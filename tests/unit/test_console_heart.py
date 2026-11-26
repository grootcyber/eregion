"""SKY2 (#1241): the watch at the heart of the 360° (Jonathan, 26/11).

The white heart of Glorfindel in the 360° becomes the watch: green while it runs, orange stale, red stopped, grey
unknown — the header's pill's tones —, its age under the name (« 12s ago », « stale · 3m ago »), a beat at each of
the watch's beats. One source for the header and the 360° (`watchSaid`), never two that disagree; the age goes on
between two reads of the watch (every 15 s), second by second.

`watchSaid` runs as it is, in Node or a headless Chromium (tests/unit/js_engine.py); what ties the header and the
360° to it is read in their pages.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")

_RUN = r"""
const T0 = 1_000_000;
const said = [
  watchSaid({ status: 'running', age_s: 12, seen: T0 }, T0),
  watchSaid({ status: 'running', age_s: 12, seen: T0 }, T0 + 9000),       // nine seconds later, not read again
  watchSaid({ status: 'stale', age_s: 600, seen: T0 }, T0 + 180000),     // three minutes later
  watchSaid({ status: 'stopped', age_s: 7200, seen: T0 }, T0),
  watchSaid({ status: 'what', age_s: 3 }, T0),
  watchSaid(null, T0),
  watchSaid({ status: 'running', age_s: 4, seen: T0 + 15000 }, T0 + 15000),   // read again: a new beat
];
emit(JSON.stringify(said));
"""


def _said() -> list:
    return json.loads(js_engine.run(js_engine.take(CONSOLE, "watchSaid") + _RUN))


def test_the_watch_says_its_tone_and_its_age_the_header_s_words():
    s = _said()
    assert s[0] == {"tone": "green", "text": "watch · 12s ago", "short": "12s ago", "beat": 988}
    assert s[1]["text"] == "watch · 21s ago" and s[1]["beat"] == 988        # its age goes on, its beat stays
    assert s[2]["tone"] == "orange" and s[2]["text"] == "watch stale · 13m ago" and s[2]["short"] == "stale · 13m ago"
    assert s[3]["tone"] == "red" and s[3]["text"] == "watch stopped" and s[3]["short"] == "stopped"
    assert s[4]["tone"] == "dim" and s[4]["text"] == "watch what"           # an unknown status: grey
    assert s[5] == {"tone": "dim", "text": "watch unknown", "short": "unknown", "beat": 0}
    assert s[6]["beat"] == 1011 and s[6]["beat"] != s[0]["beat"]            # read again after a beat: a new beat


def _fn(src: str, name: str) -> str:
    m = re.search(r"^  (?:async )?function " + re.escape(name) + r"\(", src, re.M)
    assert m, name
    return src[m.start():].split("\n  }\n", 1)[0]


def test_the_header_says_it_from_the_same_source_second_by_second():
    show = _fn(CONSOLE, "showWatch")
    assert "const s = watchSaid(lastWatch, Date.now()), color = `var(--${s.tone})`;" in show
    assert "label.textContent = s.text;" in show
    assert "lastWatch = { ...w, seen: Date.now() };" in _fn(CONSOLE, "refreshWatch")
    assert "    showWatch();                          // SKY2: the watch's age goes on with the clock" in _fn(CONSOLE, "tick")
    assert "watchStatus, watchSaid };" in CONSOLE


def test_the_360_s_heart_is_the_watch_and_beats_with_it():
    heart = DRAW.split("  function heart() {", 1)[1].split("\n  }\n", 1)[0]
    assert "if (L.core.getAttribute('fill') !== col) L.core.setAttribute('fill', col);" in heart
    assert "L.heart.setAttribute('fill', col); L.heart.textContent = h.short;" in heart
    assert "if (lastBeat && !M.reduced)" in heart                          # no beat for less motion, nor at the first read
    assert "    if (now - heartAt >= 1000) { heartAt = now; heart(); }" in DRAW
    assert ".sky-flow, .sky-pulse, .sky-beat { animation: none; }" in HTML
