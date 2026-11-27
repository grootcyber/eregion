"""SKY5 (#1257): the 360°'s card on a phone, a sheet that rises from the bottom (Jonathan, 27/11, on the mockup).

Jonathan's choices: it opens to half the screen, the sky still seen above it, dimmed; dragged up, nearly all of it (92 %);
dragged down past a third, or by a quick swipe, it closes — else it comes back. Its whole head is dragged (the handle,
the name, its ✕ aside), 44 px high at least; its content scrolls inside it, to its very end: its height is what is seen
of it (on the mockup, a taller sheet pushed down left its last lines under the screen — Jonathan saw it). ✕, Escape or a
tap on the dimmed sky close it. And the satellites' words, short (« 8 VMs · 4 to judge », « 13 VMs · 2 acted »,
« 13 kept · 1 restoring »), the help line said for a phone.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py): the rule of the rests, the page's sheet on
neighbours of the test's.
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
PHONE = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]


def test_the_sheet_rests_at_half_then_nearly_all_and_closes_past_a_third():
    got = json.loads(js_engine.run(SKY + r"""
const R = InfraSky.SHEET_RESTS, f = InfraSky.sheetRest;
emit(JSON.stringify([R, f(0.55, 0, R), f(0.40, 0, R), f(0.30, 0, R), f(0.80, 0, R), f(0.70, 0.3, R),
                     f(0.60, 1.2, R), f(0.60, -1.2, R), f(0.92, 0.2, R), f(0.35, -1.2, R)]));
"""))
    rests, *after = got
    assert rests == [0.55, 0.92]
    assert after == [0.55,     # let go where it rests: there
                     0.55,     # a little down: back
                     0,        # past a third of half the screen: closed
                     0.92,     # nearer the top: the top
                     0.55,     # slowly down from 0.70: the nearest, half
                     0,        # a quick swipe down: closed
                     0.92,     # a quick swipe up: the top
                     0.92,     # at the top, a little down: still the top
                     0]        # past a third, though swiped up at the end: closed


_SHEET = r"""
const style = {}, classes = new Set(), handlers = {};
let unpins = 0;
const scrim = { hidden: true };
const box = { hidden: false, style, dataset: {}, offsetHeight: 0,
              classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) },
              addEventListener: (t, fn) => { (handlers[t] = handlers[t] || []).push(fn); } };
const fakeDoc = { getElementById: id => ({ 'sky-scrim': scrim, 'sky-panel': box, 'sky-wrap': {} }[id] || null) };
const fakeWin = { innerHeight: 800 };
let phone = true;
const _isPhone = () => phone;
const InfraSkyDraw = { unpin: () => { unpins++; }, pinned: () => null };
const head = { setPointerCapture() {} };
const at = (el, button) => ({ closest: sel => (sel === '.sky-card-head' ? el : sel === 'button' ? (button ? {} : null) : null) });
const fire = (t, ev) => (handlers[t] || []).forEach(fn => fn(ev));
(function (document, window) {
  SKY_SRC
  PAGE_FNS
  const out = {};
  _sheetShow(box, true); out.open = [style.height, scrim.hidden, classes.has('anim')];      // half the screen, the sky dimmed
  _sheetListen(box); _sheetListen(box); out.listened = (handlers.pointerdown || []).length;   // once
  // Its head dragged up 400 px: the top rest.
  fire('pointerdown', { target: at(head), clientY: 400, timeStamp: 0, pointerId: 1 });
  fire('pointermove', { clientY: 200, timeStamp: 400 }); fire('pointermove', { clientY: 100, timeStamp: 800 });
  fire('pointerup', {}); out.up = style.height;
  // From a button of the head (its ✕): no drag.
  fire('pointerdown', { target: at(head, true), clientY: 400, timeStamp: 900, pointerId: 1 });
  fire('pointermove', { clientY: 790, timeStamp: 1300 }); fire('pointerup', {}); out.from_button = [style.height, unpins];
  // Pressed on its content, not on its head: the content scrolls, the sheet stays (the relecture: « head = box » dragged it).
  fire('pointerdown', { target: at(null), clientY: 100, timeStamp: 1400, pointerId: 1 });
  fire('pointermove', { clientY: 500, timeStamp: 1500 }); fire('pointermove', { clientY: 780, timeStamp: 1600 });
  fire('pointerup', {}); out.from_body = [style.height, unpins];
  // A phone's width left at 92 %, then come back: dragged from what it shows, half the screen — never from 92 % (the
  // relecture: a drag of 10 px jumped back there).
  phone = false; _skyPlaceCard(); out.left_phone = [style.height, _sheetH];
  phone = true; _skyPlaceCard();
  fire('pointerdown', { target: at(head), clientY: 400, timeStamp: 1700, pointerId: 1 });
  fire('pointermove', { clientY: 410, timeStamp: 1900 }); fire('pointerup', {}); out.back = style.height;
  // Dragged down past a third: closed — let go of its pin.
  fire('pointerdown', { target: at(head), clientY: 100, timeStamp: 2000, pointerId: 1 });
  fire('pointermove', { clientY: 500, timeStamp: 2600 }); fire('pointermove', { clientY: 780, timeStamp: 3200 });
  fire('pointerup', {}); out.down = unpins;
  // Closed: the scrim hidden, its height let go; a desktop never drags it.
  _sheetShow(box, false); out.closed = [style.height, scrim.hidden];
  phone = false; _sheetShow(box, true); fire('pointerdown', { target: at(head), clientY: 400, timeStamp: 4000, pointerId: 1 });
  fire('pointermove', { clientY: 100, timeStamp: 4400 }); fire('pointerup', {}); out.desktop = style.height;
  emit(JSON.stringify(out));
})(fakeDoc, fakeWin);
"""


def test_the_sheet_opens_to_what_is_seen_of_it_and_its_head_drags_it():
    fns = js_engine.take(JS, "_sheetLen", "_sheetShow", "_sheetListen", "_skyPlaceCard")
    script = _SHEET.replace("SKY_SRC", SKY).replace("PAGE_FNS", "let _sheetH = 0;\n" + fns)
    got = json.loads(js_engine.run(script))
    # Its height in dvh, what is seen of the screen as it is: a screen that grows shorter or turns keeps it within, its
    # ✕ in reach (the relecture, in px: opened at 92 % in 390×844 then 390×700, its top at −76 px).
    assert got["open"] == ["55.0dvh", False, True]      # half the screen, the sky dimmed, rising
    assert got["listened"] == 1
    assert got["up"] == "92.0dvh"                       # dragged up: 92 %
    assert got["from_button"] == ["92.0dvh", 0]         # from its ✕: no drag, nothing closed
    assert got["from_body"] == ["92.0dvh", 0]           # from its content: no drag, nothing closed
    assert got["left_phone"] == ["", 0]                 # a desktop's width: its card floats, no sheet's height
    assert got["back"] == "55.0dvh"                     # back on a phone, a drag of 10 px: half, as shown
    assert got["down"] == 1                             # dragged down past a third: closed
    assert got["closed"] == ["", True]
    assert got["desktop"] == "55.0dvh"                  # a desktop opens it so, never drags it (its card floats there)


_OPEN = r"""
let focused = 0, shown = [];
const xbtn = { focus: () => { focused++; } };
const box = { hidden: true, childElementCount: 0, scrollTop: 0, style: {}, replaceChildren() {}, set innerHTML(v) { this.childElementCount = 1; },
              contains: () => false, querySelector: sel => (sel === '.sky-card-x' ? xbtn : null), querySelectorAll: () => [] };
const doc = { getElementById: id => (id === 'sky-panel' ? box : null), activeElement: null };
let phone = true, focus = { a: 'k' };
const InfraSkyDraw = { pinned: () => focus, focusOn() {} };
let _skyModelLast = { tiles: [], lanes: [], backends: { d: [], p: [], r: [] } }, _skyRest = '', _skyCtx = {};
const _tiles = new Map([['k', { key: 'k', vm_name: 'web-1' }]]);
const _unfolded = () => '<div class="node-asset">tile</div>', _skyPlaceCard = () => {}, _isOor = () => false;
const _applyReadOnlyGuards = () => {}, _writesBlocked = () => '', _isPhone = () => phone, _sheetShow = (b, on) => { shown.push(on); };
const run = (function (document) { PANEL_FNS; return _skyPanel; })(doc);
run(); const out = { phone: [shown.slice(), focused] };
focus = null; run(); out.closed = shown.slice();
phone = false; focus = { a: 'k' }; shown = []; focused = 0; run(); out.desk = [shown.slice(), focused];
emit(JSON.stringify(out));
"""


def test_on_a_phone_the_tile_rises_and_the_keyboard_s_focus_goes_to_its_close():
    fns = js_engine.take(JS, "_attr", "_on", "_WRITE_HANDLERS", "_OOR_DROPS", "_dropWrites", "_skyFocusSig", "_SKY_CARD_X",
                         "_skyCardName", "_skyPanelHtml", "_skyPanel")
    got = json.loads(js_engine.run(SKY + _OPEN.replace("PANEL_FNS", "let _skyPanelLast = '', _skyGuardLast = '', _moduleBlocks = {}, _skyCardOf = null;\n" + fns)))
    assert got["phone"] == [[True], 1]                  # opened on a phone: the sheet rises, the focus on its ✕
    assert got["closed"] == [True, False]               # let go: the sheet goes
    assert got["desk"] == [[], 0]                       # a desktop: its card floats, the focus left where it is


_REWRITE = r"""
let tile = 'one';
const bodies = [];
const box = { hidden: true, childElementCount: 0, scrollTop: 0, style: {}, replaceChildren() {},
              set innerHTML(v) { this.childElementCount = 1; bodies.push({ scrollTop: 0, html: v }); },
              contains: () => false, querySelector: sel => (sel === '.sky-card-body' ? bodies[bodies.length - 1] || null : null),
              querySelectorAll: () => [] };
const doc = { getElementById: id => (id === 'sky-panel' ? box : null), activeElement: null };
const InfraSkyDraw = { pinned: () => ({ a: 'k' }), focusOn() {} };
let _skyModelLast = { tiles: [], lanes: [], backends: { d: [], p: [], r: [] } }, _skyRest = '', _skyCtx = {};
const _tiles = new Map([['k', { key: 'k', vm_name: 'web-1' }]]);
const _unfolded = () => `<div class="node-asset">tile ${tile}</div>`, _skyPlaceCard = () => {}, _isOor = () => false;
const _applyReadOnlyGuards = () => {}, _writesBlocked = () => '', _isPhone = () => false, _sheetShow = () => {};
const run = (function (document) { PANEL_FNS; return _skyPanel; })(doc);
run(); bodies[0].scrollTop = 120;                    // the operator reads down its tile
tile = 'two'; run();                                  // a refresh rewrites it
emit(JSON.stringify([bodies.length, bodies[1].scrollTop, bodies[1].html.includes('tile two')]));
"""


def test_a_rewritten_card_keeps_where_its_body_was_read():
    """The relecture: rewritten at a refresh (its tile changed), the card's body is put back where it was read — on a
    phone, the sheet's content scrolls inside it, its head stays."""
    fns = js_engine.take(JS, "_attr", "_on", "_WRITE_HANDLERS", "_OOR_DROPS", "_dropWrites", "_skyFocusSig", "_SKY_CARD_X",
                         "_skyCardName", "_skyPanelHtml", "_skyPanel")
    got = json.loads(js_engine.run(SKY + _REWRITE.replace("PANEL_FNS", "let _skyPanelLast = '', _skyGuardLast = '', _moduleBlocks = {}, _skyCardOf = null;\n" + fns)))
    assert got == [2, 120, True]                        # rewritten once, its body where it was


def test_the_card_s_head_names_what_it_is_of():
    got = json.loads(js_engine.run(js_engine.take(JS, "_skyCardName") + r"""
const _tiles = new Map([['k', { key: 'k', vm_name: 'web-1' }], ['e', { key: 'e', label: 'Entra ID — identities' }]]);
const m = { lanes: [{ key: 's/rg', label: 'Prod / rg-web' }], backends: { d: [{ id: 'nb-law', name: 'law-prod' }], p: [], r: [] } };
emit(JSON.stringify([_skyCardName({ a: 'k' }, m), _skyCardName({ a: 'e' }, m), _skyCardName({ s: 'sys:s/rg' }, m),
  _skyCardName({ b: 'nb-law' }, m), _skyCardName({ b: 'more:a|b|c' }, m), _skyCardName({ m: 'p' }, m), _skyCardName({ m: 'judge' }, m)]));
"""))
    assert got == ["web-1", "Entra ID — identities", "Prod / rg-web", "law-prod", "3 more", "PROTECT", "Glorfindel"]


def test_the_help_line_says_on_a_phone_what_happens_there_and_the_sheet_s_css():
    sky = JS.split("\nfunction _renderSky(", 1)[1].split("\n}\n", 1)[0]
    assert "its tile rises from the bottom · swipe it down to close" in sky and "its card opens beside it" in sky
    assert "    .sky-hint-desk { display: none; } .sky-hint-phone { display: inline; }" in PHONE
    assert "  .sky-hint-phone { display: none; }" in STYLE                                 # a desktop: its own line
    assert "    .sky-card-body { flex: 1 1 auto; overflow-y: auto; overscroll-behavior: contain;" in PHONE   # scrolls inside
    assert "min-height: 52px;\n                     touch-action: none;" in PHONE         # its head, to the thumb
    assert "    .sky-card-x { float: none; margin: 0; min-width: 44px; min-height: 44px;" in PHONE   # MOB5: a finger's 44 px
    assert "    .sky-scrim:not([hidden]) { display: block; position: fixed; inset: 0;" in PHONE
    # A desktop's card as SKY4 made it (the relecture: a head of 23 px, the name said twice): its ✕ floats, no head.
    desk = STYLE.split("  @media (max-width: 759px) {\n", 1)[0]
    assert "  .sky-card-head { display: contents; }\n  .sky-card-name { display: none; }" in desk
    assert "  .sky-card-x { float: right; margin: -2px 0 4px 8px;" in desk
    assert "    .sky-card-head { display: flex;" in PHONE and "    .sky-card-name { display: block;" in PHONE


def test_less_motion_stills_the_sheet_after_its_transition_in_the_phone_s_block():
    """The relecture: the motion's block came before the phone's, of the same weight — the phone's transition won, the
    sheet still moved for whoever asks for less motion. Its stillness now after its transition, in the phone's block
    (the stylesheet's last), and nowhere before it, where it would lose again."""
    moving = PHONE.index("    .sky-panel.anim { transition: height")
    still = PHONE.index("    @media (prefers-reduced-motion: reduce) { .sky-panel.anim { transition: none; } }")
    assert still > moving
    assert ".sky-panel.anim" not in PHONE[still:].split("\n", 1)[1]                    # nothing after it moves it again
    assert ".sky-panel.anim" not in STYLE.split("  @media (max-width: 759px) {\n", 1)[0]


def test_a_refresh_gives_the_focus_back_without_scrolling_the_column():
    """SKY5 (Jonathan, on Imladris): in the table, at the foot of the column, each refresh scrolled it back to the top —
    the button of « table » kept the focus, and renderInfra gave it back by focus(), which scrolls an element into view.
    Measured in Chromium: #topo-graph's scrollTop 2 399, then 0; given back with preventScroll, 2 399 still. The
    selector's, the view's and a row's focus, in the 360° and in the table: renderInfra run, focus() spied on."""
    got = json.loads(js_engine.run(_REFOCUS.replace("RENDER", js_engine.take(JS, "renderInfra"))))
    still = {"preventScroll": True}
    assert got["table"] == [["grp", still], ["view", still], ["row", still]]
    assert got["sky"] == [["grp", still], ["view", still]]


_REFOCUS = r"""
const calls = [];
const btn = (k, v) => ({ dataset: { [k]: v }, focus: opts => calls.push([k, opts === undefined ? null : opts]) });
const kept = [btn('grp', 'rg'), btn('view', 'table'), btn('row', 'r1'), btn('row', 'r2')];
const body = { set innerHTML(v) {}, querySelectorAll: sel => { const k = (sel.match(/^\[data-(\w+)\]$/) || [])[1]; return k ? kept.filter(b => k in b.dataset) : []; } };
const graph = { querySelector: () => body }, list = { contains: () => true, querySelectorAll: () => [] };
const doc = { activeElement: { dataset: { grp: 'rg', view: 'table', row: 'r1' } },
              getElementById: id => ({ 'incidents-list': list, 'topo-graph': graph, 'topo-body': body }[id] || null) };
let view = 'table';
let _configMode = false, _cfgData = {}, _state = { resources: [], escalations: [], restores: [], discovered_assets: [] };
let _escById, _rulesCache, _coverageCache, _nsgGlowCache, _tiles, _cardVmNames;
const _collapsedVms = new Set(), _expandedVms = new Set();
const _tileMap = () => new Map(), _isOor = () => false, _onTile = () => false, _infraView = () => view;
const _settleTable = () => {}, _renderSky = () => {}, _renderModules = () => '', _groupBar = () => '', _renderAgentNode = () => '';
const _exclusionsBand = () => '', _auditBand = () => '', _assetsHtml = () => '', _legend = () => '', _dropWrites = () => {};
const _applyReadOnlyGuards = () => {};
const run = (function (document) { RENDER; return renderInfra; })(doc);
run(); const table = calls.splice(0);
view = 'sky'; run(); const sky = calls.splice(0);
emit(JSON.stringify({ table, sky }));
"""
