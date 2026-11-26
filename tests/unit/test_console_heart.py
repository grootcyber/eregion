"""SKY2 (#1241): the watch at the heart of the 360° (Jonathan, 26/11).

The white heart of Glorfindel in the 360° becomes the watch: green while it runs, orange stale, red stopped, grey
unknown — the header's pill's tones —, its age under the name (« 12s ago », « stale · 3m ago »), a beat at each of
the watch's beats. One source for the header and the 360° (`watchSaid`), never two that disagree; the age goes on
between two reads of the watch (every 15 s), second by second.

From the relecture (Driver, first round): a beat is the server's (`since`, its heartbeat's time), never computed
from the browser's clock — a stopped watch beat at each read, a running one beat once too often every ~17 min; a
read that failed stays « watch unknown » until a read succeeds (it went green again at the next second); a running
watch is said stale past the server's 90 s between two reads, as the server would at its next. And the behaviour
is run, not read: the header with a `fetch` of the test's, the 360° mounted on a DOM of the test's.

Run in Node or a headless Chromium (tests/unit/js_engine.py): no network, no Azure, no model.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.unit import js_engine

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "eregion_console" / "static"
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
API = (ROOT / "eregion_console" / "api.py").read_text(encoding="utf-8")

S1, S2 = "2026-11-26T10:00:00+00:00", "2026-11-26T10:01:00+00:00"

_RUN = r"""
const T0 = 1_000_000;
const run = (w, now) => watchSaid(w, now);
const said = [
  run({ status: 'running', since: 'S1', age_s: 12, seen: T0 }, T0),
  run({ status: 'running', since: 'S1', age_s: 12, seen: T0 }, T0 + 9000),       // nine seconds later, not read again
  run({ status: 'stale', age_s: 600, seen: T0 }, T0 + 180000),                   // three minutes later
  run({ status: 'stopped', seen: T0 }, T0),
  run({ status: 'what', age_s: 3 }, T0),
  run(null, T0),
  run({ status: 'running', since: 'S2', age_s: 4, seen: T0 + 15000 }, T0 + 15000),   // read again: a new beat
  run({ status: 'running', since: 'S1', age_s: 80, seen: T0 }, T0 + 9000),       // 89 s: still running
  run({ status: 'running', since: 'S1', age_s: 80, seen: T0 }, T0 + 14000),      // 94 s between two reads: stale
  run({ status: 'stopped', seen: T0 + 15000 }, T0 + 15000),                      // stopped, read again
  run({ status: 'unknown', seen: T0 }, T0),
  run({ status: 'running', since: 'S1', age_s: 12, seen: T0, failed: true }, T0),   // a read that failed
  run({ status: 'running', since: 'S1', age_s: 89, seen: T0 }, T0 + 600),        // 89.6 s: under the server's 90, running
];
emit(JSON.stringify(said));
""".replace("'S1'", repr(S1)).replace("'S2'", repr(S2))


def _said() -> list:
    return json.loads(js_engine.run(js_engine.take(CONSOLE, "WATCH_STALE_S", "watchSaid") + _RUN))


def test_the_watch_says_its_tone_and_its_age_the_header_s_words():
    s = _said()
    assert s[0] == {"tone": "green", "text": "watch · 12s ago", "short": "12s ago", "beat": S1}
    assert s[1]["text"] == "watch · 21s ago" and s[1]["beat"] == S1          # its age goes on, its beat stays
    assert s[2]["tone"] == "orange" and s[2]["text"] == "watch stale · 13m ago" and s[2]["short"] == "stale · 13m ago"
    assert s[3]["tone"] == "red" and s[3]["text"] == "watch stopped" and s[3]["short"] == "stopped"
    assert s[4]["tone"] == "dim" and s[4]["text"] == "watch what"             # an unknown status: grey
    assert s[5] == {"tone": "dim", "text": "watch unknown", "short": "unknown", "beat": ""}
    assert s[6]["beat"] == S2                                                  # read again after a beat: a new beat


def test_a_beat_is_the_server_s_and_only_a_running_watch_s():
    s = _said()
    assert [x["beat"] for x in (s[2], s[3], s[9], s[10], s[11])] == [""] * 5   # stale, stopped (twice), unknown, failed
    assert s[11] == {"tone": "dim", "text": "watch unknown", "short": "unknown", "beat": ""}   # failed: whatever was read


def test_past_the_server_s_threshold_a_running_watch_is_said_stale_between_two_reads():
    s = _said()
    assert s[7]["tone"] == "green" and s[7]["text"] == "watch · 89s ago" and s[7]["beat"] == S1
    assert s[8] == {"tone": "orange", "text": "watch stale · 2m ago", "short": "stale · 2m ago", "beat": ""}
    assert s[12]["tone"] == "green" and s[12]["beat"] == S1          # the threshold on the age unrounded, as the server's
    # The threshold is the server's: one number, read in both.
    server = API.split("def _heartbeat() -> dict:", 1)[1].split("\ndef ", 1)[0]
    limit = re.search(r"if age_s < (\d+):", server)
    page = re.search(r"^const WATCH_STALE_S = (\d+);", CONSOLE, re.M)
    assert limit and page and int(limit.group(1)) == int(page.group(1)) == 90


# The header, run: console.js as it is, a document, a fetch, the intervals and the clock of the test's. A read
# that succeeds, the clock that ticks, a read that fails, the next second, a read that succeeds again.
_HEADER = r"""
const RealDate = Date; let clock = 1_000_000_000_000;
class FDate extends RealDate { constructor(...a) { super(...(a.length ? a : [clock])); } static now() { return clock; } }
const els = {};
const fakeDoc = { getElementById: id => els[id] || (els[id] = { id, style: {}, textContent: '', innerHTML: '', hidden: false,
  title: '', classList: { add() {} }, addEventListener() {} }) };
let watch = { status: 'running', since: 'S1', age_s: 12, subscriptions: { names: { s1: 'prod' } } };
const fakeFetch = async url => {
  if (url === '/api/watch/status') { if (watch instanceof Error) throw watch; return { ok: true, json: async () => watch }; }
  return { ok: true, json: async () => (url.startsWith('/api/to-judge') ? { cards: [] } : { sections: [] }) };
};
const every = {};
const fakeEvery = (fn, ms) => { every[ms] = fn; };
const settle = async () => { for (let i = 0; i < 30; i++) await null; };
(async function (document, fetch, setInterval, Date) {
  CONSOLE_SRC
  const pill = () => [els['c-watch-label'].textContent, els['c-watch-dot'].style.color || ''];
  const seen = [];
  Console.init('glorfindel');
  await settle();
  seen.push(pill());                                   // read: running, 12 s
  clock += 9000; every[1000]();
  seen.push(pill());                                   // nine seconds later, not read again: 21 s
  watch = new Error('HTTP 502'); every[15000](); await settle();
  seen.push(pill());                                   // the read failed
  clock += 1000; every[1000]();
  seen.push(pill());                                   // the next second: still unknown
  const kept = Console.watchStatus();
  seen.push([String(!!kept.failed), (kept.subscriptions || {}).names ? 'kept' : 'lost']);   // IDT1's fields kept
  watch = { status: 'running', since: 'S2', age_s: 3 }; every[15000](); await settle();
  seen.push(pill());                                   // read again
  seen.push([String(!!Console.watchStatus().failed), '']);
  emit(JSON.stringify(seen));
})(fakeDoc, fakeFetch, fakeEvery, FDate);
""".replace("'S1'", repr(S1)).replace("'S2'", repr(S2))


def test_the_header_says_the_watch_second_by_second_and_a_failed_read_stays_unknown():
    seen = json.loads(js_engine.run(_HEADER.replace("CONSOLE_SRC", CONSOLE)))
    assert seen[0] == ["watch · 12s ago", "var(--green)"]
    assert seen[1] == ["watch · 21s ago", "var(--green)"]         # the age goes on with the clock
    assert seen[2] == ["watch unknown", "var(--dim)"]             # the read failed: said at once
    assert seen[3] == ["watch unknown", "var(--dim)"]             # never green again at the next second
    assert seen[4] == ["true", "kept"]                            # what was read kept for the page (IDT1)
    assert seen[5] == ["watch · 3s ago", "var(--green)"]          # a read that succeeds: running again
    assert seen[6] == ["false", ""]


# The 360°, mounted: infra_sky.js and infra_sky_draw.js as they are, on a DOM of the test's (in a function's scope:
# a Chromium's own document never seen). heartOf gives what the test says; each mount paints the heart once, and a
# frame past a second paints it again. A beat: its core's class set to « sky-heart sky-beat ».
_MOUNT = r"""
function El(tag) {
  this.tagName = tag; this.attrs = {}; this.children = []; this.parentNode = null; this.style = {}; this.dataset = {};
  this.textContent = ''; this.beats = 0;
}
El.prototype.setAttribute = function (k, v) {
  v = String(v);
  if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = v; else this.attrs[k] = v;
  if (k === 'class' && v.split(' ').includes('sky-beat')) this.beats++;
};
El.prototype.getAttribute = function (k) {
  const v = k.startsWith('data-') ? this.dataset[k.slice(5)] : this.attrs[k];
  return v === undefined ? null : v;
};
El.prototype.appendChild = function (c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; };
El.prototype.remove = function () { const p = this.parentNode; if (p) { p.children = p.children.filter(x => x !== this); this.parentNode = null; } };
El.prototype.replaceChildren = function () { this.children.forEach(c => { c.parentNode = null; }); this.children = []; };
El.prototype.addEventListener = function () {};
El.prototype.getBoundingClientRect = function () { return { x: 0, y: 0, width: 0, height: 0 }; };
El.prototype.all = function () { return this.children.flatMap(c => [c, ...c.all()]); };
El.prototype.querySelectorAll = function (sel) {
  const m = /^\[([\w-]+)\]$/.exec(sel); if (!m) throw new Error('selector ' + sel);
  return this.all().filter(e => e.getAttribute(m[1]) !== null);
};
El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
El.prototype.closest = function (sel) {
  const m = /^\[([\w-]+)\]$/.exec(sel);
  for (let e = this; e; e = e.parentNode) if (e.getAttribute(m[1]) !== null) return e;
  return null;
};
Object.defineProperty(El.prototype, 'isConnected', { get() { let e = this; while (e.parentNode) e = e.parentNode; return e === root; } });
const root = new El('div');
const fakeDoc = { createElementNS: (ns, tag) => new El(tag), documentElement: root };
const styleOf = () => ({ getPropertyValue: n => n.slice(2) });   // a tone's colour: its own name
let frameFn = null;
const fakeRaf = f => { frameFn = f; return 1; };
(function (document, getComputedStyle, requestAnimationFrame) {
  SKY_SRC
  const fresh = () => {                                   // a page of its own for each scenario
    DRAW_SRC
    return InfraSkyDraw;
  };
  const out = {};
  for (const [name, reduced, said] of SCENARIOS) {
    const InfraSkyDraw = fresh(), slot = new El('div'); root.appendChild(slot);
    let i = 0, asked = 0;
    const model = { mode: 'none', tiles: [], lanes: [], sectors: {}, backends: { d: [], p: [], r: [] }, watch: 0, reduced,
                    heartOf: () => { asked++; return said[Math.min(i, said.length - 1)]; } };
    InfraSkyDraw.mount(slot, model);                      // built once: the first read
    const svg = slot.children[0], core = svg.all().find(e => (e.attrs.class || '').split(' ')[0] === 'sky-heart');
    const nodes = svg.all().length, beats = [core.beats];
    for (i = 1; i < said.length; i++) { InfraSkyDraw.mount(slot, model); beats.push(core.beats); }
    const before = asked;
    frameFn(1500); frameFn(1700);                          // a frame past a second paints the heart, one within it does not
    out[name] = { beats, fill: core.attrs.fill, text: svg.all().find(e => e.textContent === said[said.length - 1].short) ? said[said.length - 1].short : '',
                  same_nodes: svg.all().length === nodes, per_frame: asked - before };
    slot.remove();
  }
  emit(JSON.stringify(out));
})(fakeDoc, styleOf, fakeRaf);
"""

_R = lambda since, age="12s ago": {"tone": "green", "short": age, "beat": since}   # noqa: E731
_SCENARIOS = [
    ["same", False, [_R(S1), _R(S1, "13s ago"), _R(S1, "14s ago")]],
    ["new", False, [_R(S1), _R(S2, "3s ago"), _R(S2, "4s ago")]],
    ["reduced", True, [_R(S1), _R(S2, "3s ago")]],
    ["stopped", False, [_R(S1), {"tone": "red", "short": "stopped", "beat": ""},
                        {"tone": "red", "short": "stopped", "beat": ""}]],
]


def _mounted() -> dict:
    script = (_MOUNT.replace("SCENARIOS", json.dumps(_SCENARIOS)).replace("SKY_SRC", SKY).replace("DRAW_SRC", DRAW))
    return json.loads(js_engine.run(script))


def test_the_360_s_heart_beats_once_at_each_new_beat_of_the_watch():
    m = _mounted()
    assert m["same"]["beats"] == [0, 0, 0]                 # the first read, then the same beat read again: nothing
    assert m["new"]["beats"] == [0, 1, 1]                  # a new beat: one, and only one
    assert m["reduced"]["beats"] == [0, 0]                 # less motion: none
    assert m["stopped"]["beats"] == [0, 0, 0]              # a stopped watch read again: none
    assert m["new"]["fill"] == "green" and m["stopped"]["fill"] == "red"   # its tone
    assert m["same"]["text"] == "14s ago" and m["stopped"]["text"] == "stopped"   # its age under the name
    assert all(x["same_nodes"] for x in m.values())        # the heart writes on its nodes, never a new one
    assert all(x["per_frame"] == 1 for x in m.values())    # second by second, not at each frame


def test_the_header_and_the_360_say_it_from_one_source():
    show = CONSOLE.split("  function showWatch() {", 1)[1].split("\n  }\n", 1)[0]
    assert "const s = watchSaid(lastWatch, Date.now()), color = `var(--${s.tone})`;" in show
    assert "watchStatus, watchSaid };" in CONSOLE
    assert ".sky-flow, .sky-pulse, .sky-beat { animation: none; }" in HTML   # less motion: the CSS too
