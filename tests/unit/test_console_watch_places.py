"""HRT1 (#1272): the watch leaves the header (Jonathan, 27/11, one question at a time with the Console session).

The shared header says neither the watch's beat nor the return channel any more. The watch is said where Glorfindel is
drawn — the 360°'s heart (SKY2), the table's GLORFINDEL, the overview's GLORFINDEL row, Dagorlad's GLORFINDEL card —
from one reading (Console.watchSaid) told to each place at the same second (Console.onWatch): one age, one server's
`since`, a missed beat seen alike. The return channel where its runs are: the overview's CHANNELS row (its « published
beat »), Dagorlad's GLORFINDEL card (Console.channelSaid). A phone keeps it all, in its place: the table is its view.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py), on neighbours of the test's.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
GF = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
OV = (STATIC / "overview.js").read_text(encoding="utf-8")
DG = (STATIC / "dagorlad.js").read_text(encoding="utf-8")

# console.js as it is, on a document, a fetch, the intervals and the clock of the test's.
_HEADER = r"""
const RealDate = Date; let clock = 1_000_000_000_000;
class FDate extends RealDate { constructor(...a) { super(...(a.length ? a : [clock])); } static now() { return clock; } }
const els = {};
const mk = id => ({ id, style: {}, textContent: '', innerHTML: '', hidden: false, title: '', classList: { add() {} }, addEventListener() {}, writes: 0 });
const fakeDoc = { getElementById: id => els[id] || (els[id] = mk(id)) };
let watch = { status: 'running', since: 'S1', age_s: 12 };
const fakeFetch = async url => {
  if (url === '/api/watch/status') { if (watch instanceof Error) throw watch; return { ok: true, json: async () => watch }; }
  return { ok: true, json: async () => (url.startsWith('/api/to-judge') ? { cards: [] } : { sections: [] }) };
};
const every = {};
const fakeEvery = (fn, ms) => { every[ms] = fn; };
const settle = async () => { for (let i = 0; i < 30; i++) await null; };
(async function (document, fetch, setInterval, Date) {
  CONSOLE_SRC
  // Two places, as two pages' (or the table's and the heart's), each painted by Console.paintWatch.
  const a = mk('a'), b = mk('b');
  Console.onWatch(s => Console.paintWatch(a, s));
  Console.onWatch(s => Console.paintWatch(b, s, 'short'));
  const both = () => [a.textContent, a.style.color, b.textContent, b.style.color];
  const out = {};
  Console.init('overview');
  out.header = els['console-header'].innerHTML;
  await settle(); out.read = both();
  clock += 9000; every[1000](); out.later = both();                       // the same second for both
  const late = mk('late'); Console.onWatch(s => Console.paintWatch(late, s)); out.late = late.textContent;   // told at once
  clock += 100000; every[1000](); out.stale = both();                      // past the server's threshold, between two reads
  watch = new Error('HTTP 502'); every[15000](); await settle(); out.failed = both();
  emit(JSON.stringify(out));
})(fakeDoc, fakeFetch, fakeEvery, FDate);
"""


def _header():
    return json.loads(js_engine.run(_HEADER.replace("CONSOLE_SRC", CONSOLE)))


def test_the_header_says_neither_the_watch_nor_the_return_channel():
    header = _header()["header"]
    for gone in ("c-watch", "c-rc", "return channel", "watch…"):
        assert gone not in header, gone
    assert "c-breaker" in header and "c-clock" in header              # the breaker and the clock stay


def test_every_place_is_told_the_same_reading_at_the_same_second():
    got = _header()
    assert got["read"] == ["● watch · 12s ago", "var(--green)", "● 12s ago", "var(--green)"]
    assert got["later"] == ["● watch · 21s ago", "var(--green)", "● 21s ago", "var(--green)"]   # one age, ticking alike
    assert got["late"] == "● watch · 21s ago"                         # a place that comes later is told at once
    assert got["stale"][1] == got["stale"][3] == "var(--orange)" and "stale" in got["stale"][0]   # a missed beat, alike
    assert got["failed"] == ["● watch unknown", "var(--dim)", "● unknown", "var(--dim)"]


_PLACE = r"""
const _attr = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const esc = _attr;
let told = null, painted = [];
const Console = { watchSaid: () => ({ tone: 'orange', text: 'watch stale · 2m ago', short: 'stale · 2m ago', beat: '' }), watchStatus: () => ({}),
                  onWatch: cb => { told = cb; }, paintWatch: (el, s) => painted.push([el && el.id, s.text]),
                  channelSaid: rc => ({ tone: 'green', text: 'return channel · 10s ago', title: 'the heartbeat' }) };
const doc = { getElementById: id => ({ id }) };
(function (document) {
  FNS
  const out = {};
  BODY
  emit(JSON.stringify(out));
})(doc);
"""


def _place(fns, body):
    return json.loads(js_engine.run(_PLACE.replace("FNS", fns).replace("BODY", body)))


def test_the_table_s_glorfindel_says_the_watch_and_listens():
    fns = js_engine.take(GF, "_agentWatch", "_renderAgentNode", "_agentWatchListen")
    got = _place("let _auditData = null, _auditStale = null, _backupStale = null; const _watchBand = () => '';\n" + fns, r"""
  out.node = _renderAgentNode([], [], [], []);
  _agentWatchListen(); told({ text: 'watch · 3s ago' }); out.painted = painted;""")
    assert 'id="agent-watch" style="color:var(--orange)">● watch stale · 2m ago</span>' in got["node"]
    assert "modules" in got["node"]                                   # under GLORFINDEL and its modules
    assert got["painted"] == [["agent-watch", "watch · 3s ago"]]      # second by second, as every place


def test_the_overview_s_glorfindel_says_the_watch_and_listens():
    fns = js_engine.take(OV, "watchLine", "glorfindelRow", "watchListen")
    got = _place("const D = { judge: [], sections: {} }; const exclusionLine = () => '';\n" + fns, r"""
  out.row = glorfindelRow({});
  watchListen(); told({ text: 'watch · 3s ago' }); out.painted = painted;""")
    assert 'id="ov-watch" style="color:var(--orange)"' in got["row"] and "● watch stale · 2m ago" in got["row"]
    assert got["painted"] == [["ov-watch", "watch · 3s ago"]]


def test_dagorlad_s_glorfindel_says_the_console_s_watch_its_gate_and_the_return_channel():
    real = js_engine.run(CONSOLE + r"""
const S = { channel: { return_channel: { configured: true, alive: true, age_s: 10 } } }, esc = Console.esc;
const Real = Console;
(function () {
  const Console = { watchSaid: Real.watchSaid, channelSaid: Real.channelSaid,
                    watchStatus: () => ({ status: 'running', since: 's', age_s: 12, seen: Date.now() }) };
  FNS
  emit(JSON.stringify(glorfindelCard({ gate: 'no live watch: the heartbeat is 9m old', rules: 3, backends: ['law'], default_mode: 'human_only',
                                       watch: { age_s: 52 } })));
})();
""".replace("FNS", js_engine.take(DG, "glorfindelCard")))
    card = json.loads(real)
    assert 'id="dg-watch"' in card and "● watch · 12s ago" in card    # the console's reading, never its payload's 52 s
    assert 'id="dg-rc"' in card and "● return channel · 10s ago" in card
    assert "no live watch: the heartbeat is 9m old" in card           # V1: a run refused all the same, said under it
    got = _place(js_engine.take(DG, "watchListen"), "watchListen(); told({ text: 'watch · 3s ago' }); out.painted = painted;")
    assert got["painted"] == [["dg-watch", "watch · 3s ago"]]


def test_the_return_channel_s_words():
    got = json.loads(js_engine.run(CONSOLE + r"""
const c = Console.channelSaid;
emit(JSON.stringify([c(undefined), c({ configured: false }), c({ configured: true, error: 'AuthorizationFailed' }),
                     c({ configured: true, alive: true, age_s: 10 }), c({ configured: true, alive: false, age_s: 400 })].map(x => [x.tone, x.text])));
"""))
    assert got == [["dim", "return channel off"], ["dim", "return channel off"], ["red", "return channel unreadable"],
                   ["green", "return channel · 10s ago"], ["yellow", "return channel · 400s ago"]]


def test_the_overview_keeps_the_return_channel_in_its_channels_row():
    row = OV.split("\nfunction channelsRow() {", 1)[1].split("\n}\n", 1)[0]
    assert "published beat ${dur(rc.age_s)} ago" in row and "return channel unreadable" in row
