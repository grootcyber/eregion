"""HRT1 (#1272): the watch leaves the header (Jonathan, 27/11, one question at a time with the Console session).

The shared header says neither the watch's beat nor the return channel any more. The watch is said where Glorfindel is
drawn — the 360°'s heart (SKY2), the table's GLORFINDEL, the overview's GLORFINDEL row, Dagorlad's GLORFINDEL card —
from one reading (Console.watchSaid) told to each place at the same second (Console.onWatch): one age, one server's
`since`, a missed beat seen alike. The return channel where its runs are: the overview's CHANNELS row (its « published
beat »), Dagorlad's GLORFINDEL card (Console.channelSaid). A phone keeps it all, in its place: the table is its view.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py), on neighbours of the test's.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eregion_core import watch_gate, watch_key
from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
GF = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
OV = (STATIC / "overview.js").read_text(encoding="utf-8")
DG = (STATIC / "dagorlad.js").read_text(encoding="utf-8")
INJ = (STATIC / "injector.js").read_text(encoding="utf-8")
INJ_HTML = (STATIC / "injector.html").read_text(encoding="utf-8")

# console.js as it is, on a document, a fetch, the intervals and the clock of the test's.
_HEADER = r"""
const RealDate = Date; let clock = 1_000_000_000_000;
class FDate extends RealDate { constructor(...a) { super(...(a.length ? a : [clock])); } static now() { return clock; } }
const els = {};
const mk = id => ({ id, style: {}, textContent: '', innerHTML: '', hidden: false, title: '', classList: { add() {} }, addEventListener() {} });
// A place whose writes are counted, by setters: its words and its tone.
const counted = id => {
  const o = { id, writes: 0, _text: '', _color: '' };
  Object.defineProperty(o, 'textContent', { get: () => o._text, set: v => { o._text = v; o.writes++; } });
  o.style = {}; Object.defineProperty(o.style, 'color', { get: () => o._color, set: v => { o._color = v; o.writes++; } });
  return o;
};
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
  const a = counted('a'), b = counted('b');
  Console.onWatch(s => Console.paintWatch(a, s));
  Console.onWatch(s => Console.paintWatch(b, s, 'short'));
  const both = () => [a.textContent, a.style.color, b.textContent, b.style.color];
  const out = {};
  Console.init('overview');
  out.header = els['console-header'].innerHTML;
  await settle(); out.read = both(); out.writes = [a.writes];
  every[1000](); every[1000](); out.writes.push(a.writes);                // the same words, the same tone: nothing written
  clock += 9000; every[1000](); out.later = both(); out.writes.push(a.writes);   // the same second for both; the age only
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


def test_a_place_is_written_only_when_its_words_or_its_tone_change():
    # Counted by setters: its words and its tone at the first read, nothing at a second that changes neither, its
    # words alone when only the age moves.
    assert _header()["writes"] == [2, 2, 3]


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


# V1's words as the gate gives them (eregion_core/watch_gate.py), never a test's own: a heartbeat too old, one unsigned.
_AT = datetime(2026, 11, 27, 12, 0, 0, tzinfo=timezone.utc)


def _gates(monkeypatch) -> dict:
    stale = watch_gate.describe(watch_gate.Beat(watch_gate.CHANNEL, _AT - timedelta(seconds=552)), _AT)
    monkeypatch.setitem(watch_gate.READERS, "proof", watch_key.proof)          # the real proof (conftest: "")
    monkeypatch.setattr(watch_key, "pinned", lambda: (object(), ""))            # a key pinned, a bare date read
    unsigned = watch_gate.unsigned(watch_gate.Beat(watch_gate.CHANNEL, _AT, body=None), record=False)
    assert stale == "return channel: last heartbeat 9 min 12 s ago (2026-11-27 11:50:48 UTC)"
    assert unsigned.startswith("return channel: unsigned: a bare date")
    return {"stale": stale, "unsigned": unsigned}


# console.js as it is; its watch, the console's reading of the test's (12 s), never a payload's.
_REAL = r"""
const Real = Console;
const Fake = { ...Real, watchStatus: () => ({ status: 'running', since: 's', age_s: 12, seen: Date.now() }) };
const out = {};
(function (Console) {
  const els = {}, $ = id => els[id] || (els[id] = { id, innerHTML: '', textContent: '', scrollTop: 0 });
  const esc = Console.esc;
  FNS
  BODY
})(Fake);
emit(JSON.stringify(out));
"""


def _real(fns, body):
    return json.loads(js_engine.run(CONSOLE + _REAL.replace("FNS", fns).replace("BODY", body)))


def test_dagorlad_s_glorfindel_says_the_console_s_watch_its_gate_and_the_return_channel(monkeypatch):
    gates = _gates(monkeypatch)
    got = _real("const S = { channel: { return_channel: { configured: true, alive: true, age_s: 10 } } };\n"
                + js_engine.take(DG, "glorfindelCard"), f"""
  const g = {{ rules: 3, backends: ['law'], default_mode: 'human_only', watch: {{ age_s: 52 }} }};
  out.live = glorfindelCard({{ ...g, gate: '' }});
  out.stale = glorfindelCard({{ ...g, gate: {json.dumps(gates["stale"])} }});
  out.unsigned = glorfindelCard({{ ...g, gate: {json.dumps(gates["unsigned"])} }});""")
    live = got["live"]
    assert 'id="dg-watch"' in live and "● watch · 12s ago" in live    # the console's reading, never its payload's 52 s
    assert "<b>GLORFINDEL</b> <span id=\"dg-watch\"" in live          # a live watch behind a run: said at its head
    assert "no live watch" not in live and 'class="err' not in live
    assert 'id="dg-rc"' in live and "● return channel · 10s ago" in live
    for name in ("stale", "unsigned"):
        card = html.unescape(got[name])
        head = card.split("</div>", 1)[0]
        # V1 at its head, in red — then why, as the gate says it — then the watch, the return channel.
        assert "<b>GLORFINDEL</b>" in head and "● no live watch for a run" in head and "color:var(--red)" in head, name
        assert 'id="dg-watch"' not in head, name
        why = card.index(gates[name])
        assert card.index("no live watch for a run") < why < card.index('id="dg-watch"') < card.index('id="dg-rc"'), name
        assert "● watch · 12s ago" in card and "3 rules" in card, name
    got = _place(js_engine.take(DG, "watchListen"), "watchListen(); told({ text: 'watch · 3s ago' }); out.painted = painted;")
    assert got["painted"] == [["dg-watch", "watch · 3s ago"]]


def test_a_board_unread_keeps_dagorlad_s_glorfindel_its_watch_and_its_return_channel(monkeypatch):
    gate = _gates(monkeypatch)["stale"]
    got = _real(js_engine.take(DG, "glorfindelCard", "renderBoard"), f"""
  let S = {{ err: '/api/dagorlad/board — HTTP 502', channel: {{ gate: {json.dumps(gate)},
             return_channel: {{ configured: true, alive: false, age_s: 400 }} }} }};
  renderBoard(); out.red = $('red-list').innerHTML; out.blue = $('blue-list').innerHTML;
  S = {{ err: 'HTTP 502', channel: {{ return_channel: {{ configured: true, error: 'the console did not answer' }} }} }};
  renderBoard(); out.both = $('blue-list').innerHTML;""")
    assert "HTTP 502" in got["red"]
    blue = html.unescape(got["blue"])
    assert 'id="dg-watch"' in blue and "● watch · 12s ago" in blue    # the watch, the board unread all the same
    assert 'id="dg-rc"' in blue and "● return channel · 400s ago" in blue
    assert "● no live watch for a run" in blue and gate in blue      # V1 from /api/channel
    assert "rules" not in blue and "NaN" not in blue and "undefined" not in blue   # nothing the board did not say
    both = got["both"]
    assert "● run gate unknown" in both and "● return channel unreadable" in both and 'id="dg-watch"' in both
    # V1 asked of /api/channel (a fresh read of the heartbeat) only when the board, which says it, is unread.
    assert "const c = await getJSON(S.err ? '/api/channel?gate=1' : '/api/channel').catch(() => null);" in DG


def test_the_runs_view_says_glorfindel_as_a_run_reads_it(monkeypatch):
    gates = _gates(monkeypatch)
    assert '<section id="rn-glorfindel"' in INJ_HTML                 # at the head of the runs, above the indicators
    assert INJ_HTML.index('id="rn-glorfindel"') < INJ_HTML.index('<section id="ind"')
    init = INJ.split("(function init() {", 1)[1]
    assert "refreshGlorfindel();" in init and "setInterval(refreshGlorfindel, 30000);" in init
    assert "async function refreshGlorfindel() { await load('chan', '/api/channel?gate=1', renderGlorfindel); }" in INJ
    got = _real(js_engine.take(INJ, "renderGlorfindel"), f"""
  const S = {{ errors: {{}}, chan: {{ gate: '', return_channel: {{ configured: true, alive: true, age_s: 10 }} }} }};
  renderGlorfindel(); out.live = $('rn-glorfindel').innerHTML;
  S.chan = {{ gate: {json.dumps(gates["unsigned"])}, return_channel: {{ configured: true, alive: false, age_s: null }} }};
  renderGlorfindel(); out.refused = $('rn-glorfindel').innerHTML;
  S.errors.chan = '/api/channel — HTTP 502';
  renderGlorfindel(); out.unread = $('rn-glorfindel').innerHTML;""")
    live = got["live"]
    assert "<b>GLORFINDEL</b>" in live and 'id="rn-watch"' in live and "● watch · 12s ago" in live
    assert 'id="rn-rc"' in live and "● return channel · 10s ago" in live and "no live watch" not in live
    refused = html.unescape(got["refused"])
    # In the Board card's words: V1 first, in red, then the watch and the return channel, then why.
    assert 'class="rn-gate" style="color:var(--red)"' in refused and "● no live watch for a run" in refused
    assert refused.index("no live watch for a run") < refused.index('id="rn-watch"') < refused.index('id="rn-rc"') \
        < refused.index(gates["unsigned"])
    assert "● return channel · age unknown" in refused
    unread = got["unread"]
    assert "● run gate unknown" in unread and "● return channel unreadable" in unread and "● watch · 12s ago" in unread
    got = _place(js_engine.take(INJ, "glorfindelListen"),
                 "const $ = id => document.getElementById(id);\n  glorfindelListen(); told({ text: 'watch · 3s ago' }); out.painted = painted;")
    assert got["painted"] == [["rn-watch", "watch · 3s ago"]]



# The Runs view's line through its own reads (load, the page's): a read that fails, then the same answer as before it.
_RUNS_READS = r"""
const Real = Console;
const Fake = { ...Real, watchStatus: () => ({ status: 'stopped', since: '', age_s: 4000, seen: Date.now() }) };
(async function (Console) {
  const els = {}, $ = id => els[id] || (els[id] = { id, innerHTML: '' });
  const esc = Console.esc, S = { errors: {} }, last = {}, asked = [];
  const answer = ANSWER, replies = [answer, new Error('HTTP 502'), answer];
  const getJSON = async url => { asked.push(url); const r = replies.shift(); if (r instanceof Error) throw r; return JSON.parse(JSON.stringify(r)); };
  FNS
  const out = { asked };
  await refreshGlorfindel(); out.first = $('rn-glorfindel').innerHTML;
  await refreshGlorfindel(); out.failed = $('rn-glorfindel').innerHTML;
  await refreshGlorfindel(); out.again = $('rn-glorfindel').innerHTML;
  emit(JSON.stringify(out));
})(Fake);
"""


def test_the_runs_view_says_v1_again_once_a_failed_read_is_over(monkeypatch):
    # The watch stopped, the return channel off: /api/channel answers the same at each read. A 502 between two: the
    # line says it unknown, then V1 again at the next read — never left grey on an answer that did not change.
    gate = _gates(monkeypatch)["stale"]
    answer = json.dumps({"gate": gate, "return_channel": {"configured": False}})
    got = json.loads(js_engine.run(CONSOLE + _RUNS_READS.replace("ANSWER", answer)
                                   .replace("FNS", js_engine.take(INJ, "load", "refreshGlorfindel", "renderGlorfindel"))))
    assert got["asked"] == ["/api/channel?gate=1"] * 3
    assert "● no live watch for a run" in got["first"] and "● watch stopped" in got["first"]
    assert "● run gate unknown" in got["failed"] and "● return channel unreadable" in got["failed"]
    assert got["again"] == got["first"]                               # V1 said again, in red: the error is over


def test_the_return_channel_s_words():
    got = json.loads(js_engine.run(CONSOLE + r"""
const c = Console.channelSaid;
emit(JSON.stringify([c(undefined), c({ configured: false }), c({ configured: true, error: 'AuthorizationFailed' }),
                     c({ configured: true, alive: true, age_s: 10 }), c({ configured: true, alive: false, age_s: 400 }),
                     c({ configured: true, alive: true, age_s: null }), c({ configured: true, alive: false })].map(x => [x.tone, x.text])));
"""))
    assert got == [["dim", "return channel off"], ["dim", "return channel off"], ["red", "return channel unreadable"],
                   ["green", "return channel · 10s ago"], ["yellow", "return channel · 400s ago"],
                   ["green", "return channel · age unknown"], ["yellow", "return channel · age unknown"]]   # never 0 s, never NaN


def test_v1_s_words():
    got = json.loads(js_engine.run(CONSOLE + r"""
const g = Console.gateSaid;
emit(JSON.stringify([g(''), g('return channel: last heartbeat never (absent)'), g(undefined), g(null)]));
"""))
    assert got[0] is None                                             # a live watch stands behind a run: nothing said
    assert got[1] == {"tone": "red", "text": "no live watch for a run", "title": "return channel: last heartbeat never (absent)"}
    assert got[2]["tone"] == got[3]["tone"] == "dim" and got[2]["text"] == "run gate unknown"   # unread, said


def test_the_overview_keeps_the_return_channel_in_its_channels_row():
    row = OV.split("\nfunction channelsRow() {", 1)[1].split("\n}\n", 1)[0]
    assert "published beat ${dur(rc.age_s)} ago" in row and "return channel unreadable" in row
