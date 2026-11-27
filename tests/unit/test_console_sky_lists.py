"""SKY6 (#1268): the lists in the sky — on a desktop, the 360° without the column (Jonathan, 27/11, on the mockup v26).

To judge, the feed and the legend in the room the circle leaves, the sky fitted to the window: a window with a column
beside the circle, the feed at the top left and To judge at the top right, at the edges, the legend at the bottom left
as wide as the circle lets it; a box nearly square, the three in its corners; a tall one, under the circle — never into
the orbit's labels. The bands at the sky's top, between the feed and To judge; « group by » in the column's header. The
column's own nodes are moved into the sky, never copied (JUG3's boxes and bar go with them), and back for the table, a
phone, the configuration. A click on a line (To judge, the feed) or on a target opens its bubble where the target is:
its state, what waits on it with the tile's own buttons and guards, « open its card ▸ » to the card of SKY4; the bubble
opens by itself for a card that came to judge or to approve, a minute, never while something is pinned.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py): the rules of the pure module, the page's
functions on neighbours of the test's.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]
BASE = STYLE.split("  @media (max-width: 759px) {\n", 1)[0]

# A list's height at a width, as the page would measure it: the legend wraps when narrow.
_HEIGHTS = r"""
const heightOf = (name, w) => name === 'legend' ? (w >= 600 ? 64 : w >= 300 ? 96 : 150) : name === 'feed' ? 120 : 92;
const off = (c, r) => { const L = r.left != null ? r.left : r.boxW - r.right - r.width, T = r.top != null ? r.top : r.boxH - r.bottom - r.h;
  const nx = Math.max(L, Math.min(c.x, L + r.width)), ny = Math.max(T, Math.min(c.y, T + r.h)); return Math.round(Math.hypot(nx - c.x, ny - c.y) - c.r); };
"""


def _lists(w, h):
    return json.loads(js_engine.run(SKY + _HEIGHTS + f"""
const box = {{ w: {w}, h: {h} }}, L = InfraSky.skyLists(box, heightOf), c = L.c;
const rect = (n, hh) => Object.assign({{ boxW: box.w, boxH: box.h, h: hh }}, L[n]);
emit(JSON.stringify({{ arr: L.arr, align: L.align, feed: L.feed, judge: L.judge, legend: L.legend, bands: L.bands,
  gap: {{ feed: off(c, rect('feed', heightOf('feed', L.feed.width))), judge: off(c, rect('judge', heightOf('judge', L.judge.width))),
          legend: off(c, rect('legend', heightOf('legend', L.legend.width))) }}, c }}));
"""))


def test_a_wide_window_the_feed_at_the_top_left_to_judge_at_the_top_right_the_legend_at_the_bottom_left():
    for w, h in ((1896, 874), (3416, 1234)):                 # a 24–27″ window, a 34″ one
        got = _lists(w, h)
        assert got["arr"] == "sides" and got["align"] == "xMidYMid"
        assert got["feed"]["left"] == 16 and got["feed"]["top"] == 16      # at the edges
        assert got["judge"]["right"] == 16 and got["judge"]["top"] == 16
        assert got["legend"]["left"] == 16 and got["legend"]["bottom"] == 14
        assert got["legend"]["width"] > got["feed"]["width"]                # wider than a column, as the circle lets it
        assert min(got["gap"].values()) >= 0, got["gap"]                    # never into the orbit's labels
        b = got["bands"]                                                     # between the feed and To judge
        assert b["left"] >= 16 + got["feed"]["width"] + 20 and b["left"] + b["width"] <= w - 16 - got["judge"]["width"] - 20
    assert _lists(3416, 1234)["legend"]["width"] == 1100                     # a 34″: room for one line a row


def test_a_box_nearly_square_the_three_in_its_corners_as_wide_as_each_corner_lets_it():
    for w, h in ((1696, 1234), (1056, 754)):                 # half a 34″, a vertical screen shared by two browsers
        got = _lists(w, h)
        assert got["arr"] == "corners" and got["align"] == "xMidYMid"
        assert got["feed"]["left"] == 10 and got["judge"]["right"] == 10 and got["legend"]["bottom"] == 10
        assert min(got["gap"].values()) >= 0, got["gap"]                    # each corner off the circle
    small = _lists(1056, 754)
    assert small["feed"]["width"] < 330 and small["legend"]["width"] < 430  # narrowed to its corner


def test_a_tall_box_the_circle_at_its_top_the_three_under_it():
    got = _lists(1056, 1714)                                 # a vertical screen
    assert got["arr"] == "below" and got["align"] == "xMidYMin"
    assert got["legend"]["top"] >= round(920 * 1056 / 1000)  # under the circle
    assert got["feed"]["top"] > got["legend"]["top"] and got["feed"]["left"] == 12 and got["judge"]["right"] == 12
    assert got["bands"]["left"] >= 12 and got["bands"]["width"] <= 760


def test_the_bubble_sits_beside_its_target_on_its_outer_side_off_the_lists():
    got = json.loads(js_engine.run(SKY + r"""
const box = { w: 1900, h: 900 }, c = { x: 950, y: 450 }, size = { w: 300, h: 120 };
const right = { x: 1300, y: 400, w: 40, h: 40 }, left = { x: 500, y: 400, w: 40, h: 40 };
const a = InfraSky.bubbleAt(box, right, size, c, []);                                    // right of the centre: further right
const b = InfraSky.bubbleAt(box, left, size, c, []);                                     // left of it: further left
const list = { x: 1350, y: 300, w: 400, h: 300 };
const d = InfraSky.bubbleAt(box, right, size, c, [list]);                                // a list there: its inner side
const e = InfraSky.bubbleAt(box, { x: 1870, y: 850, w: 20, h: 20 }, size, c, []);       // at the corner: held within
emit(JSON.stringify({ a, b, d, e }));
"""))
    assert got["a"]["left"] == 1356 and got["b"]["left"] == 500 - 300 - 16
    assert got["d"]["left"] + 300 <= 1350                    # off the list
    assert got["e"]["left"] + 300 <= 1900 - 8 and got["e"]["top"] + 120 <= 900 - 8


def test_the_card_keeps_off_the_lists():
    got = json.loads(js_engine.run(SKY + r"""
const box = { w: 1900, h: 900 }, t = { x: 1300, y: 400, w: 40, h: 40 }, card = { w: 340, h: 300 }, c = { x: 950, y: 450, r: 100 };
const free = InfraSky.placeCard(box, t, card, c, null, []);
const list = { x: 1350, y: 150, w: 520, h: 600 };
const kept = InfraSky.placeCard(box, t, card, c, null, [list]);
const over = p => p.left < list.x + list.w && p.left + card.w > list.x && p.top < list.y + list.h && p.top + card.h > list.y;
emit(JSON.stringify({ free, kept, freeOver: over(free), keptOver: over(kept) }));
"""))
    assert got["freeOver"] and not got["keptOver"]           # its first place was over the list: another taken


_FULL_ON = r"""
const mk = id => ({ id, parentElement: null, kids: [], append(...ns) { ns.forEach(n => { if (n.parentElement) n.parentElement.kids = n.parentElement.kids.filter(k => k !== n); n.parentElement = this; this.kids.push(n); }); } });
const col = mk('feed-col'), judge = mk('sky-judge'), feed = mk('sky-feed'), wrap = mk('sky-wrap'), topo = mk('topo-body');
const nodes = ['judge-head', 'judge-list', 'feed-head', 'feed-list'].map(mk), legend = mk('sky-legend');
col.append(...nodes); topo.append(wrap); topo.append(legend);
const all = [col, judge, feed, wrap, topo, legend, ...nodes];
const cls = new Set();
const doc = { getElementById: id => all.find(n => n.id === id) || null,
              body: { classList: { toggle: (c, on) => { if (on) cls.add(c); else cls.delete(c); } } } };
const run = (function (document) { FNS; return _skyFullOn; })(doc);
const where = () => ({ judge: nodes[1].parentElement.id, feed: nodes[3].parentElement.id, legend: legend.parentElement.id,
                       order: col.kids.map(k => k.id), full: cls.has('sky-full') });
const same = nodes[1];
run(true); const on = where(); const kept = doc.getElementById('judge-list') === same;
run(false); const off = where();
run(true); judge.id = 'gone'; run(true); const without = where();
emit(JSON.stringify({ on, kept, off, without }));
"""


def test_the_column_s_nodes_are_moved_into_the_sky_and_back_never_copied():
    """Driver's relecture: the same nodes, moved — their ids and listeners, JUG3's boxes and bar with them, never a copy."""
    got = json.loads(js_engine.run(_FULL_ON.replace("FNS", js_engine.take(JS, "_COL_NODES", "_skyFullOn"))))
    assert got["on"] == {"judge": "sky-judge", "feed": "sky-feed", "legend": "sky-wrap", "order": [], "full": True}
    assert got["kept"]                                       # the very node, not a copy
    assert got["off"] == {"judge": "feed-col", "feed": "feed-col", "legend": "topo-body",
                          "order": ["judge-head", "judge-list", "feed-head", "feed-list"], "full": False}
    assert got["without"]["full"] is False                   # no place in the sky: the column keeps them


def test_the_sky_takes_the_lists_on_a_desktop_s_360_only():
    got = json.loads(js_engine.run(js_engine.take(JS, "_skyFull") + r"""
let view = 'sky', phone = false, _configMode = false;
const _infraView = () => view, _isPhone = () => phone;
const out = [_skyFull()];
view = 'table'; out.push(_skyFull()); view = 'sky';
phone = true; out.push(_skyFull()); phone = false;
_configMode = true; out.push(_skyFull());
emit(JSON.stringify(out));
"""))
    assert got == [True, False, False, False]                # the 360° on a desktop; never the table, a phone, the configuration


def test_the_table_and_the_configuration_take_the_column_back_first():
    render = JS.split("\nfunction renderInfra() {", 1)[1].split("\n}\n", 1)[0]
    table = render.split("// OCT1 (#1240): else the table", 1)[1]
    assert table.index("_skyFullOn(false); _infraTools('');") < table.index("body.innerHTML = `")   # out before it is written over
    rebuilt = render.split("if (!graph || !list.contains(graph) || !body) {", 1)[1]
    assert rebuilt.index("_skyFullOn(false);") < rebuilt.index("list.innerHTML = ")
    config = JS.split("\nfunction toggleConfig() {", 1)[1].split("\n}\n", 1)[0]
    assert "if (_configMode) { _skyFullOn(false); _infraTools(''); }" in config and "if (!_configMode) renderInfra();" in config


_LINES = r"""
const pins = [];
const InfraSkyDraw = { pinTo: f => pins.push(f) };
let full = true, modal = 0;
const _skyFull = () => full;
const _tiles = new Map([['k1', { key: 'k1', vm_name: 'vm-Web-01' }], ['k2', { key: 'k2', vm_name: 'vm-data-01' }]]);
const _escById = { e1: { id: 'e1', on: 'k2' } }, _toJudge = [{ id: 'e1', on: 'k2' }, { id: 'e9', on: 'nowhere' }];
const _onTile = (e, r) => e.on === r.key;
const doc = { getElementById: id => { modal++; throw new Error('the modal: ' + id); } };
const row = vm => ({ target: { closest: () => ({ dataset: { vm } }) } });
(function (document) {
  FNS
  const out = {};
  openJudgeCard('e1'); out.judge = pins.slice();                                         // its tile's bubble
  try { openJudgeCard('e9'); out.no_tile = 'returned'; } catch (e) { out.no_tile = pins.length === 1 ? 'went on' : 'pinned'; }   // no tile: on to its window, as before
  _feedLineClick(row('VM-WEB-01')); out.feed = pins.slice(1);                            // its VM's, whatever the case
  _feedLineClick(row('vm-gone')); _feedLineClick(row(undefined)); out.feed_none = pins.length;
  full = false; _feedLineClick(row('vm-web-01')); out.table = pins.length;                          // the table: nothing pinned
  emit(JSON.stringify(out));
})(doc);
"""


def test_a_line_of_to_judge_or_of_the_feed_opens_its_tile_s_bubble_in_the_sky():
    fns = js_engine.take(JS, "_tileOfCard", "_tileOfVm", "openJudgeCard", "_feedLineClick")
    got = json.loads(js_engine.run(_LINES.replace("FNS", fns)))
    assert got["judge"] == [{"a": "k2"}]
    assert got["no_tile"] == "went on"
    assert got["feed"] == [{"a": "k1"}]
    assert got["feed_none"] == 2 and got["table"] == 2


_BUBBLE = r"""
let writes = 0, focused = [], active = null, blocked = '', full = true, pinned = { a: 'k' };
const btn = (on) => ({ tagName: 'BUTTON', attrs: { 'data-on-click': on }, disabled: false, removed: false,
  getAttribute(n) { return this.attrs[n] || null; }, remove() { this.removed = true; }, closest: () => null });
let buttons = [];
const el = { hidden: true, dataset: {}, style: {}, offsetWidth: 300, offsetHeight: 120, childElementCount: 0,
  set innerHTML(v) { writes++; this.childElementCount = 1; this.html = v; buttons = [...v.matchAll(/data-on-click="(\w+)"/g)].map(m => btn(m[1])); },
  replaceChildren() { this.childElementCount = 0; buttons = []; }, contains: x => x === active,
  querySelectorAll: () => buttons };
const doc = { getElementById: id => (id === 'sky-bubble' ? el : null), get activeElement() { return active; } };
const InfraSkyDraw = { pinned: () => pinned, focusOn: f => focused.push(f) };
let _skyModelLast = { tiles: [{ key: 'k', s: { p: 'isolated' } }, { key: 'o', s: {} }] };
const _skyCtx = { vmEscs: [{ id: 'e1', on: 'k' }, { id: 'e2', on: 'o' }] };
const _tiles = new Map([['k', { key: 'k', vm_name: 'web-1' }], ['o', { key: 'o', vm_name: 'dev-1' }]]);
const _onTile = (e, r) => e.on === r.key, _isOor = r => r.key === 'o', _writesBlocked = () => blocked;
const _groupEscs = escs => escs.map(e => [e]);
const _renderEscGroup = (g, r) => `<div><button data-on-click="doApproveAction">▶ Approve &amp; execute</button><button data-on-click="doAckAll">✓ Ack</button></div>`;
const _skyFull = () => full, _skyPlaceBubble = () => {};
let _skyCardFull = false, _skyAuto = null, _skyBubbleLast = '', _skyBubbleGuard = '', _skyBubbleOf = null;
(function (document) {
  FNS
  const out = {};
  _skyBubble(); out.open = [el.hidden, writes, el.html.includes('ISOLATED'), el.html.includes('Approve'), el.html.includes('open its card')];
  _skyBubble(); _skyBubble(); out.at_rest = writes;                                                   // nothing rewritten at rest
  blocked = 'read-only'; _skyBubble(); out.read_only = buttons.filter(b => b.disabled).map(b => b.attrs['data-on-click']);
  blocked = ''; pinned = { a: 'o' }; _skyBubble(); out.out_of_reach = buttons.filter(b => !b.removed).map(b => b.attrs['data-on-click']);
  active = buttons[0]; pinned = null; _skyBubble(); out.closed = [el.hidden, focused];                // closed from within
  pinned = { a: 'k' }; _skyCardFull = true; _skyBubble(); out.card_open = el.hidden;                  // its card open: no bubble
  _skyCardFull = false; full = false; _skyBubble(); out.table = el.hidden;
  emit(JSON.stringify(out));
})(doc);
"""


def test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards():
    fns = js_engine.take(JS, "_attr", "_on", "_WRITE_HANDLERS", "_OOR_DROPS", "_dropWrites", "_applyReadOnlyGuards", "_skyFocusSig",
                         "_skyBubbleKey", "_skyBubbleHtml", "_skyBubble")
    got = json.loads(js_engine.run(_BUBBLE.replace("FNS", fns)))
    assert got["open"] == [False, 1, True, True, True]       # its state, its card's buttons, « open its card ▸ »
    assert got["at_rest"] == 1
    assert "doApproveAction" in got["read_only"] and "skyBubbleClose" not in got["read_only"]
    assert "doApproveAction" not in got["out_of_reach"] and "skyBubbleClose" in got["out_of_reach"]   # nothing written out of reach
    assert got["closed"] == [True, [{"a": "o"}]]             # the focus back on what it was on
    assert got["card_open"] is True and got["table"] is True


_AUTO = r"""
let clock = Date.parse('2026-11-27T12:00:00Z'), pinned = null, timers = [];
const Date_ = { now: () => clock, parse: s => Date.parse(s) };
const setTimeout_ = (fn, ms) => { timers.push({ fn, at: clock + ms }); return timers.length; };
const InfraSkyDraw = { pinned: () => pinned };
const _tiles = new Map([['k', { key: 'k' }], ['j', { key: 'j' }]]);
const _onTile = (e, r) => e.on === r.key, _isHeld = e => e.held, _skyFull = () => true, _skyBubble = () => {};
let _toJudge = [{ id: 'v1' }], _skySeen = null, _skyAuto = null, _skyAutoT = 0, _skyCardFull = false;
const ago = s => new Date(clock - s * 1000).toISOString();
(function (Date, setTimeout, clearTimeout) {
  SKY_SRC
  FNS
  const out = {};
  _skyAsks({ vmEscs: [{ id: 'old', on: 'k', held: true, created_at: ago(300) }] }); out.old = _skyAuto;            // a page's old card: no news
  _skyAsks({ vmEscs: [{ id: 'h1', on: 'k', held: true, created_at: ago(10) }] }); out.fresh = _skyAuto && [_skyAuto.key, _skyAuto.until - clock];
  _skyAuto = null; _skyAsks({ vmEscs: [{ id: 'h1', on: 'k', held: true, created_at: ago(12) }] }); out.again = _skyAuto;   // seen: once
  pinned = { a: 'j' }; _skyAsks({ vmEscs: [{ id: 'v1', on: 'j', created_at: ago(5) }] }); out.pinned = _skyAuto;           // pinned: none
  pinned = null; _skyAsks({ vmEscs: [{ id: 'v2', on: 'j', verdict: 'right', created_at: ago(5) }] }); out.judged = _skyAuto;
  _skyAuto = { key: 'k', until: clock + 60000, held: false };
  clock += 30000; out.key_30s = _skyBubbleKey(); _skyAutoEnd(); out.kept_30s = !!_skyAuto;
  clock += 31000; out.key_61s = _skyBubbleKey(); _skyAutoEnd(); out.gone_61s = _skyAuto;
  _skyAuto = { key: 'k', until: clock - 1, held: true }; _skyAutoEnd(); out.held = !!_skyAuto;                     // under the pointer
  emit(JSON.stringify(out));
})(Date_, setTimeout_, () => {});
"""


def test_a_card_that_comes_to_judge_or_to_approve_opens_its_bubble_by_itself_for_a_minute():
    fns = js_engine.take(JS, "_skyNew", "_skyAsks", "_skyAutoEnd", "_skyBubbleKey")
    got = json.loads(js_engine.run(_AUTO.replace("SKY_SRC", SKY).replace("FNS", fns)))
    assert got["old"] is None                                # a card of five minutes, found at the load: no news
    assert got["fresh"] == ["k", 60000]                      # its tile's bubble, a minute
    assert got["again"] is None and got["pinned"] is None and got["judged"] is None
    assert got["key_30s"] == "k" and got["kept_30s"] is True
    assert got["key_61s"] is None and got["gone_61s"] is None
    assert got["held"] is True                               # kept while the pointer is on it


def test_group_by_goes_into_the_header_written_only_when_it_changes():
    got = json.loads(js_engine.run(r"""
let writes = 0, active = null;
const tools = { id: 'infra-tools', dataset: {}, set innerHTML(v) { writes++; this.html = v; }, contains: x => x === active,
                querySelectorAll: () => [{ dataset: { grp: 'rg' }, focus: o => { tools.focused = o; } }] };
const head = { insertBefore: () => {} };
const doc = { getElementById: id => ({ 'right-col-header': head, 'infra-tools': tools }[id] || null), get activeElement() { return active; } };
(function (document) {
  FNS
  _infraTools('<b>bar</b>'); _infraTools('<b>bar</b>');
  active = { dataset: { grp: 'rg' } }; _infraTools('<b>bar, pressed</b>');
  emit(JSON.stringify([writes, tools.focused || null]));
})(doc);
""".replace("FNS", js_engine.take(JS, "_infraTools"))))
    assert got == [2, {"preventScroll": True}]               # once, then again only when changed — its pressed button's focus kept


def test_the_legend_in_the_sky_folds_to_its_two_lines_of_lines_beside_its_name():
    legend = JS.split("\nfunction _legend(view) {", 1)[1].split("\n}\n", 1)[0]
    rows = [r.split("</span>", 1)[0] for r in legend.split('<span class="lg-h">')[1:]]
    assert rows == ["MODULES", "WAITING", "DONE", "DOTS", "TILES"]           # folded: the 2nd and 3rd kept
    assert ("body.sky-full #sky-legend.folded .legend > .lg-row:nth-child(1), "
            "body.sky-full #sky-legend.folded .legend > .lg-row:nth-child(n+4) { display: none; }") in BASE
    html = JS.split("\nfunction _skyLegendHtml() {", 1)[1].split("\n}\n", 1)[0]
    assert html.index("LEGEND <button") < html.index("_legend()")            # « more » beside its name
    assert "localStorage.setItem('eregion.skyLegend'" in JS                  # kept per browser


def test_the_table_and_a_phone_are_left_as_they_were():
    """Every rule of SKY6 that touches a node of the page is under body.sky-full: without the class (the table, a phone, the
    configuration), nothing changes. The phone's block stays the stylesheet's last (test_console_phone)."""
    block = BASE.split("/* ── SKY6 (#1268", 1)[1].split("/* ── A phone (MOB4", 1)[0]
    for line in block.splitlines():
        rule = line.strip()
        if not rule or rule.startswith("/*") or rule.startswith("*") or "{" not in rule or rule.startswith("."):
            continue
        selectors = rule.split("{", 1)[0]
        if selectors.startswith("#infra-tools"):
            continue                                         # the header's own slot, empty without the sky
        assert all(s.strip().startswith("body.sky-full") for s in selectors.split(",")), rule
    assert "@media" not in block
