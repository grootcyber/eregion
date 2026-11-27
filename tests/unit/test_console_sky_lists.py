"""SKY6 (#1268): the lists in the sky — on a desktop, the 360° without the column (Jonathan, 27/11, on the mockup v26).

To judge, the feed and the legend in the room the circle leaves, the sky fitted to the window: a window with a column
beside the circle, the feed at the top left and To judge at the top right, at the edges, the legend at the bottom left
as wide as the circle lets it; a box nearly square, the circle at the right and the three at the left, To judge at
the top (SKY7; its corners until then); a tall one, under the circle — never into the orbit's labels. The bands at the sky's top, between the feed and To judge; « group by » in the column's header. The
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


def _lists(w, h, tall=False):
    heights = _HEIGHTS if not tall else _HEIGHTS.replace("name === 'feed' ? 120 : 92", "name === 'feed' ? 2400 : 1800")
    return json.loads(js_engine.run(SKY + heights + f"""
const box = {{ w: {w}, h: {h} }}, L = InfraSky.skyLists(box, heightOf), c = L.c;
const hh = n => Math.min(heightOf(n, L[n].width), L[n].maxH || Infinity);       // as tall as it may be: past it, it scrolls
const rect = n => Object.assign({{ boxW: box.w, boxH: box.h, h: hh(n) }}, L[n]);
emit(JSON.stringify({{ arr: L.arr, align: L.align, feed: L.feed, judge: L.judge, legend: L.legend, bands: L.bands,
  gap: {{ feed: off(c, rect('feed')), judge: off(c, rect('judge')), legend: off(c, rect('legend')) }},
  inBox: ['feed', 'judge', 'legend'].every(n => hh(n) <= box.h), c }}));
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


def test_a_box_nearly_square_the_circle_at_the_right_the_three_at_the_left():
    """SKY7 (#1282; Jonathan 27/11, « Cercle à droite », « To judge, puis le fil »): in its corners until then (SKY6)."""
    for w, h in ((1696, 1234), (1056, 754)):                 # half a 34″, a vertical screen shared by two browsers
        got = _lists(w, h)
        assert got["arr"] == "left" and got["align"] == "xMaxYMid"
        assert got["c"]["x"] > w / 2 and got["c"]["x"] + got["c"]["r"] <= w + 1         # at the right, within the box
        assert got["judge"]["left"] == 10 and got["judge"]["top"] == 10                  # To judge at the top
        assert got["feed"]["left"] == 10 and got["feed"]["top"] > got["judge"]["top"]   # the feed under it
        assert got["legend"]["left"] == 10 and got["legend"]["bottom"] == 10             # the legend at the bottom
        assert min(got["gap"].values()) >= 0, got["gap"]                    # each off the circle
    small = _lists(1056, 754)
    assert small["judge"]["width"] <= 300 and small["legend"]["width"] <= 430


def test_lists_taller_than_the_box_are_held_off_the_circle_and_scroll():
    """The relecture: in the corners, a feed of 52 lines had no maxH and a sqrt of a negative (NaN) — over the drawing,
    over the legend, the bands left where they were. Held: as tall as each may be, never into the circle, never NaN."""
    for w, h in ((1256, 900), (1056, 754), (1696, 1234), (1896, 874), (3416, 1234)):
        got = _lists(w, h, tall=True)
        assert min(got["gap"].values()) >= 0, (w, h, got["gap"])
        assert got["inBox"], (w, h)
        assert json.dumps(got).count("null") <= 3 and "NaN" not in json.dumps(got)   # finite places (a maxH may be none)
        assert isinstance(got["bands"]["left"], int) and got["bands"]["width"] >= 0
    # SKY7: the circle at the right, the feed under To judge — To judge as tall as 45 % of the box, the feed the rest
    # down to the legend, as wide as the circle lets it there (at least 200 px).
    for w, h in ((1256, 900), (1696, 1234)):
        got = _lists(w, h, tall=True)
        j, f = got["judge"], got["feed"]
        assert j["maxH"] == int(h * 0.45) and f["top"] == 10 + j["maxH"] + 14 and f["width"] >= 200
        assert f["maxH"] >= h - f["top"] - 150 - 24 and f["maxH"] >= 250
    # A legend taller than half the box: its corner reaches the centre's height — the whole radius kept off, never a sqrt
    # of a negative (the relecture, M8185: a window hardly taller than its legend, beside a wide one); the circle at the
    # right, held to a third of the box, it scrolls (SKY7).
    legend = json.loads(js_engine.run(SKY + _HEIGHTS.replace("name === 'legend' ? (w >= 600 ? 64 : w >= 300 ? 96 : 150)",
                                                             "name === 'legend' ? 900") + """
const low = InfraSky.skyLists({ w: 3416, h: 420 }, heightOf), left = InfraSky.skyLists({ w: 1056, h: 754 }, heightOf);
emit(JSON.stringify({ low: low.legend, arr: low.arr, left: left.legend, feed: left.feed }));
"""))
    assert legend["arr"] == "sides" and "NaN" not in json.dumps(legend) and legend["low"]["width"] >= 200
    assert legend["left"]["maxH"] == 754 // 3 and legend["feed"]["maxH"] >= 754 - legend["feed"]["top"] - 754 // 3 - 24


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
const edge = { x: 1700, y: 400, w: 60, h: 40 };                                          // its outer side, held, over it
const f = InfraSky.bubbleAt(box, edge, size, c, []);
emit(JSON.stringify({ a, b, d, e, f }));
"""))
    assert got["a"]["left"] == 1356 and got["b"]["left"] == 500 - 300 - 16
    assert got["d"]["left"] + 300 <= 1350                    # off the list
    assert got["e"]["left"] + 300 <= 1900 - 8 and got["e"]["top"] + 120 <= 900 - 8
    assert got["f"]["left"] + 300 <= 1700                    # held within the box, it would cover its target: its inner side


_ROOM = r"""
const box = { w: 1256, h: 617 }, c = { x: 628, y: 308 }, size = { w: 340, h: 370 };
const lists = [{ x: 16, y: 16, w: 300, h: 240 }, { x: 940, y: 16, w: 300, h: 200 }, { x: 16, y: 470, w: 420, h: 133 }, { x: 336, y: 10, w: 584, h: 50 }];
const over = r => lists.some(o => r.left < o.x + o.w && r.left + size.w > o.x && r.top < o.y + o.h && r.top + r.h > o.y);
const t = { x: 40, y: 320, w: 20, h: 20 };
const whole = InfraSky.bubbleAt(box, t, size, c, lists, size.h), shorter = InfraSky.bubbleAt(box, t, size, c, lists);
const none = InfraSky.bubbleAt(box, { x: 40, y: 300, w: 20, h: 20 }, size, c, lists);
emit(JSON.stringify({ whole: whole.clear, shorter: [shorter.clear, shorter.h, over(shorter)], none: none.clear }));
"""


def test_a_tall_bubble_is_made_shorter_to_find_room_off_the_lists_or_says_there_is_none():
    """The second relecture: a bubble of 370 px (its verdicts) in a box of 1256 × 617 with its lists — held at the box's top,
    it lay over To judge or the feed. The tallest that finds a place off the lists; none: said (clear false)."""
    got = json.loads(js_engine.run(SKY + _ROOM))
    assert got["whole"] is False                              # at its full height, no place off the lists
    assert got["shorter"][0] is True and got["shorter"][1] < 370 and got["shorter"][2] is False
    assert got["none"] is False


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
const mk = id => ({ id, parentElement: null, kids: [], attrs: {}, hasAttribute(n) { return n in this.attrs; }, removeAttribute(n) { delete this.attrs[n]; }, append(...ns) { ns.forEach(n => { if (n.parentElement) n.parentElement.kids = n.parentElement.kids.filter(k => k !== n); n.parentElement = this; this.kids.push(n); }); } });
const col = mk('feed-col'), judge = mk('sky-judge'), feed = mk('sky-feed'), wrap = mk('sky-wrap'), topo = mk('topo-body');
const nodes = ['judge-head', 'judge-list', 'feed-head', 'feed-list'].map(mk), legend = mk('sky-legend');
col.append(...nodes); topo.append(wrap); topo.append(legend);
const all = [col, judge, feed, wrap, topo, legend, ...nodes];
const cls = new Set();
const doc = { getElementById: id => all.find(n => n.id === id) || null, querySelectorAll: () => [],
              body: { classList: { toggle: (c, on) => { if (on) cls.add(c); else cls.delete(c); } } } };
let _skyFeedClip = '';                                        // SKY7: the feed's clip, let go with its style
const run = (function (document) { FNS; return _skyFullOn; })(doc);
const where = () => ({ judge: nodes[1].parentElement.id, feed: nodes[3].parentElement.id, legend: legend.parentElement.id,
                       order: col.kids.map(k => k.id), full: cls.has('sky-full') });
const same = nodes[1];
run(true); const on = where(); const kept = doc.getElementById('judge-list') === same;
legend.attrs.style = 'left: 16px; width: 620px'; judge.attrs.style = 'right: 16px';    // placed in the sky
run(false); const off = where(); off.styles = [legend, judge].map(n => 'style' in n.attrs);
run(true); judge.id = 'gone'; run(true); const without = where();
emit(JSON.stringify({ on, kept, off, without }));
"""


def test_the_column_s_nodes_are_moved_into_the_sky_and_back_never_copied():
    """Driver's relecture: the same nodes, moved — their ids and listeners, JUG3's boxes and bar with them, never a copy."""
    got = json.loads(js_engine.run(_FULL_ON.replace("FNS", js_engine.take(JS, "_COL_NODES", "_skyFullOn"))))
    assert got["on"] == {"judge": "sky-judge", "feed": "sky-feed", "legend": "sky-wrap", "order": [], "full": True}
    assert got["kept"]                                       # the very node, not a copy
    assert got["off"] == {"judge": "feed-col", "feed": "feed-col", "legend": "topo-body",
                          "order": ["judge-head", "judge-list", "feed-head", "feed-list"], "full": False,
                          "styles": [False, False]}      # their places let go (the relecture: a phone kept the legend's 620 px)
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
const _tiles = new Map([['k', { key: 'k', vm_name: 'web-1' }], ['o', { key: 'o', vm_name: 'dev-1' }], ['a', { key: 'a', vm_name: 'web-2' }]]);
const _onTile = (e, r) => e.on === r.key, _isOor = r => r.key === 'o', _writesBlocked = () => blocked;
const _toJudge = [{ id: 'j1', on: 'k', action: 'isolate_vm', confidence: 0.88, explanation: 'shadow copies deleted' },
                  { id: 'x1', on: 'k', action: 'block_suspicious_ip', action_params: { ip: '203.0.113.7', port: 22 }, exercise: true, exercise_run: 'run-42',
                    time_unreadable: true, proposed_verdict: { verdict: 'right', drill: 'drill-ssh', rule: 'ssh-brute-force', after_s: 12, within_s: 60 } },
                  { id: 'j2', on: 'a', action: 'block_suspicious_ip', explanation: 'a scan, acknowledged' }];
const actionLabelVerb = a => ({ isolate_vm: 'Isolate VM', block_suspicious_ip: 'Block IP' }[a] || a), escTitle = c => c.title || '?';
const _groupEscs = escs => escs.map(e => [e]);
const _renderEscGroup = (g, r) => `<div><button data-on-click="doApproveAction">▶ Approve &amp; execute</button><button data-on-click="doAckAll">✓ Ack</button></div>`;
const _skyFull = () => full, _skyPlaceBubble = () => {};
let _skyCardFull = false, _skyAuto = null, _skyBubbleLast = '', _skyBubbleGuard = '', _skyBubbleOf = null;
(function (document) {
  FNS
  const out = {};
  _skyBubble(); out.open = [el.hidden, writes, el.html.includes('ISOLATED'), el.html.includes('Approve'), el.html.includes('open its card')];
  out.judge = [el.html.includes("data-on-click=\"judgeFromBubble\""), el.html.includes('shadow copies deleted'), el.html.includes('sky-judge-note-j1'), el.html.includes('Isolate VM 88%')];
  out.list_says = { exercise: el.html.includes('⚑ exercise · run'), untimed: el.html.includes('time unreadable'), ip: el.html.includes('Block IP 203.0.113.7:22'),
                    proposed: [el.html.includes('data-on-click="confirmProposedFromBubble"'), el.html.includes('data-on-click="refuseProposedFromBubble"'), el.html.includes('FromModal')] };
  _skyBubble(); _skyBubble(); out.at_rest = writes;                                                   // nothing rewritten at rest
  blocked = 'read-only'; _skyBubble(); out.read_only = buttons.filter(b => b.disabled).map(b => b.attrs['data-on-click']);
  blocked = ''; pinned = { a: 'o' }; _skyBubble(); out.out_of_reach = buttons.filter(b => !b.removed).map(b => b.attrs['data-on-click']);
  pinned = { a: 'a' }; _skyBubble(); out.acked = [el.html.includes('nothing waits here'), el.html.includes('a scan, acknowledged'), buttons.filter(b => b.attrs['data-on-click'] === 'judgeFromBubble').length];
  pinned = { a: 'o' }; _skyBubble();
  active = buttons[0]; pinned = null; _skyBubble(); out.closed = [el.hidden, focused];                // closed from within
  pinned = { a: 'k' }; _skyCardFull = true; _skyBubble(); out.card_open = el.hidden;                  // its card open: no bubble
  _skyCardFull = false; full = false; _skyBubble(); out.table = el.hidden;
  emit(JSON.stringify(out));
})(doc);
"""


def test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards():
    fns = js_engine.take(JS, "_attr", "_on", "_WRITE_HANDLERS", "_OOR_DROPS", "_dropWrites", "_applyReadOnlyGuards", "_skyFocusSig",
                         "_UNTIMED", "_proposedLine", "_skyBubbleKey", "_skyBubbleHtml", "_skyBubble")
    got = json.loads(js_engine.run(_BUBBLE.replace("FNS", fns)))
    assert got["open"] == [False, 1, True, True, True]       # its state, its card's buttons, « open its card ▸ »
    assert got["at_rest"] == 1
    assert "doApproveAction" in got["read_only"] and "skyBubbleClose" not in got["read_only"]
    assert "doApproveAction" not in got["out_of_reach"] and "skyBubbleClose" in got["out_of_reach"]   # nothing written out of reach
    assert got["closed"] == [True, [{"a": "o"}]]             # the focus back on what it was on
    # JUG1 in the sky (the relecture): its tile's cards to judge, their explanation, a note of its own, three verdicts —
    # an acknowledged one too, never « nothing waits here ».
    assert got["judge"] == [True, True, True, True]
    assert got["acked"] == [False, True, 3]
    # All the list says of a card to judge (the second relecture): its exercise — judged « wrong » without it, an exercise's
    # card would pass for a false alarm —, its time unreadable, the IP a block targets, the verdict a drill proposes with
    # buttons of the bubble's own (its note), never the modal's.
    assert got["list_says"] == {"exercise": True, "untimed": True, "ip": True, "proposed": [True, True, False]}
    assert got["card_open"] is True and got["table"] is True


_AUTO = r"""
let clock = Date.parse('2026-11-27T12:00:00Z'), pinned = null, timers = [], modalOpen = false, _state = {};
const Date_ = { now: () => clock + 120000, parse: s => Date.parse(s) };      // the browser's clock, two minutes ahead
const setTimeout_ = (fn, ms) => { timers.push({ fn, at: clock + ms }); return timers.length; };
const doc = { getElementById: id => (id === 'modal' ? { classList: { contains: c => c === 'open' && modalOpen } } : null) };
const InfraSkyDraw = { pinned: () => pinned };
const _tiles = new Map([['k', { key: 'k' }], ['j', { key: 'j' }]]);
const _onTile = (e, r) => e.on === r.key, _isHeld = e => e.held, _skyFull = () => true, _skyBubble = () => {};
let _toJudge = [{ id: 'v1' }], _skySeen = null, _skyAuto = null, _skyAutoT = 0, _skyCardFull = false;
const ago = s => new Date(clock - s * 1000).toISOString(), iso = t => new Date(t).toISOString();   // the server's clock
(function (Date, setTimeout, clearTimeout, document) {
  SKY_SRC
  FNS
  const out = {};
  _skyAsks({ vmEscs: [{ id: 'early', on: 'k', held: true, created_at: ago(5) }] }); out.before_state = [_skySeen, _skyAuto];
  _state = { now: iso(clock) };
  _skyAsks({ vmEscs: [{ id: 'found', on: 'k', held: true, created_at: ago(5) }] }); out.found = _skyAuto;           // the first state's
  _skyAsks({ vmEscs: [{ id: 'old', on: 'k', held: true, created_at: ago(300) }] }); out.old = _skyAuto;              // five minutes old
  _skyAsks({ vmEscs: [{ id: 'h1', on: 'k', held: true, created_at: ago(10) }] }); out.fresh = _skyAuto && [_skyAuto.key, _skyAuto.until - Date.now()];
  _skyAuto = null; _skyAsks({ vmEscs: [{ id: 'h1', on: 'k', held: true, created_at: ago(12) }] }); out.again = _skyAuto;   // seen: once
  pinned = { a: 'j' }; _skyAsks({ vmEscs: [{ id: 'v1', on: 'j', created_at: ago(5) }] }); out.pinned = _skyAuto;           // pinned: none
  pinned = null; _skyAsks({ vmEscs: [{ id: 'v2', on: 'j', verdict: 'right', created_at: ago(5) }] }); out.judged = _skyAuto;
  modalOpen = true; _skyAsks({ vmEscs: [{ id: 'h3', on: 'j', held: true, created_at: ago(3) }] }); out.modal = _skyAuto; modalOpen = false;
  _skyAuto = { key: 'k', until: Date.now() + 60000, held: false };
  clock += 30000; out.key_30s = _skyBubbleKey(); _skyAutoEnd(); out.kept_30s = !!_skyAuto;
  clock += 31000; out.key_61s = _skyBubbleKey(); _skyAutoEnd(); out.gone_61s = _skyAuto;
  _skyAuto = { key: 'k', until: Date.now() - 1, held: true }; _skyAutoEnd(); out.held = !!_skyAuto;                    // under the pointer
  emit(JSON.stringify(out));
})(Date_, setTimeout_, () => {}, doc);
"""


def test_a_card_that_comes_to_judge_or_to_approve_opens_its_bubble_by_itself_for_a_minute():
    fns = js_engine.take(JS, "_skyNew", "_skyAsks", "_skyAutoEnd", "_skyBubbleKey")
    got = json.loads(js_engine.run(_AUTO.replace("SKY_SRC", SKY).replace("FNS", fns)))
    assert got["before_state"] == [None, None]               # no state read yet: nothing taken as seen, nothing opened
    assert got["found"] is None                              # the cards a page finds when it loads: no news, however young
    assert got["old"] is None                                # five minutes old: no news
    assert got["fresh"] == ["k", 60000]                      # by the server's clock (the browser's two minutes ahead)
    assert got["again"] is None and got["pinned"] is None and got["judged"] is None
    assert got["modal"] is None                              # never under an open window (the relecture)
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


_SCROLL = r"""
const lists = { 'judge-list': { scrollTop: 300 }, 'feed-list': { scrollTop: 120 } };
// A container measured without its maxHeight lets its list grow: the list scrolls back to its top, as a browser does.
const box = (list, h) => ({ offsetHeight: h, style: new Proxy({}, { set(o, k, v) { o[k] = v; if (k === 'maxHeight' && v === '' && list) lists[list].scrollTop = 0; return true; } }) });
const els = { 'sky-wrap': { clientWidth: 1256, clientHeight: 900, dataset: {} }, 'sky-judge': box('judge-list', 300), 'sky-feed': box('feed-list', 400),
              'sky-legend': box(null, 90), 'sky-bands': { style: {} }, ...lists };
const doc = { getElementById: id => els[id] || null };
const InfraSkyDraw = { align() {} }, _skyFull = () => true;
// SKY7: the feed's widths and its lines, the page's own (tests/unit/test_console_sky_feed.py).
const _skyModelLast = null, _groupBy = 'rg', _skyFeedWidths = () => ({ natural: NaN, least: NaN }), _skyFeedLines = () => {};
let _skyLayout = null;
(function (document) {
  SKY_SRC
  FNS
  _skyLists();
  emit(JSON.stringify([lists['judge-list'].scrollTop, lists['feed-list'].scrollTop, els['sky-wrap'].dataset.arr]));
})(doc);
"""


def test_the_lists_keep_where_they_were_read_when_they_are_placed_again():
    """The relecture: measured without their maxHeight at each refresh, To judge scrolled back to its top (300 → 0)."""
    got = json.loads(js_engine.run(_SCROLL.replace("SKY_SRC", SKY).replace("FNS", js_engine.take(JS, "_skyLists"))))
    assert got == [300, 120, "left"]


_FALLBACK = r"""
const style = {}, classes = new Set();
const box = { hidden: false, offsetWidth: 340, offsetHeight: 300, style, classList: { contains: c => classes.has(c), remove: c => classes.delete(c), toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c); } }, scrollIntoView() {} };
const wrap = { dataset: { arr: 'corners' }, getBoundingClientRect: () => ({ left: 0, top: 0, width: 640, height: 640, right: 640, bottom: 640 }) };
const doc = { getElementById: id => ({ 'sky-panel': box, 'sky-wrap': wrap }[id] || null) };
const win = { innerHeight: 640 };
let full = true, _sheetH = 0, _skyDock = { w: -1, docked: false };
const InfraSkyDraw = { pinned: () => ({ a: 'k' }), centre: () => ({ x: 320, y: 320, r: 300 }), rectOf: () => ({ left: 420, top: 310, width: 20, height: 20, right: 440, bottom: 330 }) };
const _isPhone = () => false, _skyFull = () => full, _skyListRects = () => [];
(function (document, window) {
  SKY_SRC
  FNS
  _skyPlaceCard(true); const sky = [classes.has('docked'), style.left || '', style.top || ''];
  full = false; _skyPlaceCard(true); const table = classes.has('docked');
  emit(JSON.stringify({ sky, table }));
})(doc, win);
"""


def test_in_the_sky_the_card_is_never_laid_under_the_circle():
    """Nowhere off the disc (a large centre in a small window): in the sky, over the disc's edge then — the sky fills the
    window, nothing lies under the circle; elsewhere (no sky), under it, as SKY4 did."""
    got = json.loads(js_engine.run(_FALLBACK.replace("SKY_SRC", SKY).replace("FNS", js_engine.take(JS, "_skyPlaceCard"))))
    assert got["sky"][0] is False and got["sky"][1].endswith("px") and got["sky"][2].endswith("px")
    assert got["table"] is True


_PLACE_BUBBLE = r"""
let _skyAuto = { key: 'k' }, _skyBubbleLast = 'x', _skyBubbleGuard = 'y', target = { left: 40, top: 320, width: 20, height: 20, right: 60, bottom: 340 };
const el = { hidden: false, dataset: { key: 'k', auto: '' }, style: {}, offsetWidth: 340, offsetHeight: 200, scrollHeight: 600, replaceChildren() { this.emptied = true; } };
const wrap = { dataset: { arr: 'corners' }, getBoundingClientRect: () => ({ left: 0, top: 0, width: 1256, height: 617, right: 1256, bottom: 617 }) };
const doc = { getElementById: id => ({ 'sky-bubble': el, 'sky-wrap': wrap }[id] || null) };
const InfraSkyDraw = { rectOf: () => target, systemOf: () => null, centre: () => ({ x: 628, y: 308, r: 120 }) };
const lists = [{ x: 16, y: 16, w: 300, h: 240 }, { x: 940, y: 16, w: 300, h: 200 }, { x: 16, y: 470, w: 420, h: 133 }, { x: 336, y: 10, w: 584, h: 50 }];
const _skyListRects = () => lists;
(function (document) {
  SKY_SRC
  FNS
  const out = {};
  _skyPlaceBubble(); out.clicked = [el.hidden, el.style.maxHeight, el.style.left, el.style.top];
  target = { left: 40, top: 300, width: 20, height: 20, right: 60, bottom: 320 };                    // no room at all
  _skyPlaceBubble(); out.clicked_no_room = el.hidden;                                                   // a clicked one: shown
  el.dataset.auto = '1'; _skyPlaceBubble(); out.auto_no_room = [el.hidden, _skyAuto, !!el.emptied];    // by itself: none
  emit(JSON.stringify(out));
})(doc);
"""


def test_the_bubble_is_held_off_the_lists_in_every_arrangement_and_by_itself_opens_only_with_room():
    got = json.loads(js_engine.run(_PLACE_BUBBLE.replace("SKY_SRC", SKY).replace("FNS", js_engine.take(JS, "_skyPlaceBubble"))))
    hidden, most, left, top = got["clicked"]
    assert hidden is False and most.endswith("px") and int(most[:-2]) < 370 and left.endswith("px")   # shorter, its content scrolls
    assert got["clicked_no_room"] is False                    # a click: it opens all the same, off its target
    assert got["auto_no_room"] == [True, None, True]          # by itself, with no room off the lists: not at all


_CARD_TALL = r"""
const style = {}, classes = new Set();
const box = { hidden: false, offsetWidth: 340, offsetHeight: 300, style, classList: { contains: c => classes.has(c), remove: c => classes.delete(c), toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c); } }, scrollIntoView() {} };
const wrap = { dataset: { arr: 'below' }, getBoundingClientRect: () => ({ left: 0, top: 0, width: 880, height: 1300, right: 880, bottom: 1300 }) };
const doc = { getElementById: id => ({ 'sky-panel': box, 'sky-wrap': wrap }[id] || null) };
const win = { innerHeight: 1300 };
let _sheetH = 0, _skyDock = { w: -1, docked: false };
// The circle at the top (0–810), the lists under it from 820 — the target at the circle's foot.
const InfraSkyDraw = { pinned: () => ({ a: 'k' }), centre: () => ({ x: 440, y: 405, r: 380 }), rectOf: () => ({ left: 600, top: 760, width: 20, height: 20, right: 620, bottom: 780 }) };
const _isPhone = () => false, _skyFull = () => true, _skyListRects = () => [{ x: 12, y: 820, w: 856, h: 80 }, { x: 12, y: 910, w: 422, h: 380 }, { x: 446, y: 910, w: 422, h: 380 }];
(function (document, window) {
  SKY_SRC
  FNS
  _skyPlaceCard(true);
  emit(JSON.stringify([parseFloat(style.top) + 300, classes.has('docked')]));
})(doc, win);
"""


def test_in_a_tall_window_the_card_is_held_above_the_lists():
    """The relecture: at 900 × 1400, « open its card ▸ » laid the card over the feed, 721 px from its target."""
    bottom, docked = json.loads(js_engine.run(_CARD_TALL.replace("SKY_SRC", SKY).replace("FNS", js_engine.take(JS, "_skyPlaceCard"))))
    assert docked is False and bottom <= 820
