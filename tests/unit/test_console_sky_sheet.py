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
const fakeDoc = { getElementById: id => (id === 'sky-scrim' ? scrim : null) };
const fakeWin = { innerHeight: 800 };
let phone = true;
const _isPhone = () => phone;
const InfraSkyDraw = { unpin: () => { unpins++; } };
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
    script = _SHEET.replace("SKY_SRC", SKY).replace("PAGE_FNS", js_engine.take(JS, "_sheetShow", "_sheetListen").replace(
        "function _sheetShow", "let _sheetH = 0;\nfunction _sheetShow", 1))
    got = json.loads(js_engine.run(script))
    assert got["open"] == ["440px", False, True]        # 55 % of 800: its height what is seen, the sky dimmed, rising
    assert got["listened"] == 1
    assert got["up"] == "736px"                         # dragged up: 92 %
    assert got["from_button"] == ["736px", 0]           # from its ✕: no drag, nothing closed
    assert got["down"] == 1                             # dragged down past a third: closed
    assert got["closed"] == ["", True]
    assert got["desktop"] == "440px"                    # a desktop opens it so, never drags it (its card floats there)


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
    assert "min-height: 52px; touch-action: none;" in PHONE                                # its head, to the thumb
    assert "    .sky-scrim:not([hidden]) { display: block; position: fixed; inset: 0;" in PHONE
    assert "    .sky-panel.anim { transition: none; }" in STYLE                            # still, for less motion


def test_a_refresh_gives_the_focus_back_without_scrolling_the_column():
    """SKY5 (Jonathan, on Imladris): in the table, at the foot of the column, each refresh scrolled it back to the top —
    the button of « table » kept the focus, and renderInfra gave it back by focus(), which scrolls an element into view.
    Measured in Chromium: #topo-graph's scrollTop 2 399, then 0; given back with preventScroll, 2 399 still. The
    selector's, the view's and a row's focus, in the 360° and in the table."""
    render = JS.split("\nfunction renderInfra() {", 1)[1].split("\n}\n", 1)[0]
    for name, key in (("_grpFocus", "grp"), ("_viewFocus", "view"), ("_rowFocus", "row")):
        given = f"b.dataset.{key} === {name})?.focus("
        assert render.count(given) >= 1, name
        assert render.count(given + "{ preventScroll: true });") == render.count(given), name   # never a focus() that scrolls
    assert render.count("?.focus();") == 0
