"""SKY4 (#1249): the 360°'s floating card and a centre that follows the estate (Jonathan, 26/11, on the mockup).

The panel beside the sky took a third of its width. Now:
  - the card is closed at rest — the sky takes the whole width, and each satellite says under its name what its
    module's block says of it (« 4 watched · 1 to judge », « 2 governed · 2 acted on », « 1 protected · 1 restoring »);
  - a click (a pin) opens it beside what was clicked: the tile itself, a system, a satellite, a module and its whole
    block. It keeps off Glorfindel's disc first, then off what was clicked, then is the nearest (InfraSky.placeCard);
    on a phone, under the circle. Escape, its ✕ or a click elsewhere closes it (SKY3); a hover only lights;
  - Glorfindel's ring and its satellites follow the estate: larger for a small one (140 % at 5 resources or fewer),
    tighter for a large one (80 % from 35), the size they always had at 25.
And SKY3's known limits: a mode's capabilities (#cap-popover) keep their own click and Escape, a field of the card its
Escape — run in tests/unit/test_console_sky_gestures.py.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py): the sky's pure logic, its draw on a DOM of the
test's, the page's card on neighbours of the test's.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]
PHONE = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]

# Around the whole sky — Glorfindel's satellites, the systems' orbit (336), the lone stars' (372): a target every 10°.
# The centre at its scale (InfraSky.size: a ring of 72, 88 for 17 resources, 101 for 5 or fewer — the relecture: the
# test held it at 72), in frames of a large screen (1 336, 1 280, 1 210), of a laptop (900, 844) and of a phone (470);
# a card of 360 × 420, and one taller than half the frame.
_PLACE = r"""
const S = InfraSky, out = {};
for (const ring of [72, 88, 101]) for (const [W, cw, ch] of [[1336, 360, 420], [1280, 360, 420], [1210, 360, 420], [1210, 360, 700],
                                                             [900, 360, 380], [844, 360, 380], [470, 360, 300]]) {
  const H = Math.round(W * 0.92), k = W / 1000, c = { x: 500 * k, y: 460 * k, r: (ring + 46) * k };
  let over = 0, covers = 0, outside = 0, docked = 0;
  for (const R of [172 * ring / 72, 336, 372]) for (let i = 0; i < 36; i++) {
    const a = i * Math.PI / 18, t = { x: c.x + Math.cos(a) * R * k - 10, y: c.y + Math.sin(a) * R * k - 10, w: 20, h: 20 };
    const p = S.placeCard({ w: W, h: H }, t, { w: cw, h: ch }, c);
    if (!p) { docked++; continue; }
    const d = Math.hypot(Math.max(p.left, Math.min(c.x, p.left + cw)) - c.x, Math.max(p.top, Math.min(c.y, p.top + ch)) - c.y);
    if (d < c.r) over++;
    if (p.left < t.x + t.w && p.left + cw > t.x && p.top < t.y + t.h && p.top + ch > t.y) covers++;
    if (p.left < 8 || p.top < 8 || p.left + cw > W - 8 || p.top + ch > H - 8) outside++;
  }
  out[`${ring}@${W}x${ch}`] = { over, covers, outside, docked };
}
// The window's band of a frame taller than it: the card held within it, never above the window's top.
out.band = S.placeCard({ w: 1400, h: 1300 }, { x: 1000, y: 340, w: 20, h: 20 }, { w: 340, h: 300 }, { x: 700, y: 650, r: 150 }, { y0: 300, y1: 900 });
// Right of the centre, room around it: beside it, on its outer side.
out.beside = S.placeCard({ w: 1400, h: 900 }, { x: 1000, y: 300, w: 20, h: 20 }, { w: 340, h: 300 }, { x: 700, y: 450, r: 150 });
out.scale = [1, 4, 5, 10, 25, 30, 35, 60, 'x'].map(n => S.scaleFor(n));
const g0 = [S.G.RG, S.G.RB];
out.size4 = [S.size(4), S.G.RG, S.G.RB]; out.size25 = [S.size(25), S.G.RG, S.G.RB]; out.size60 = [S.size(60), S.G.RG, S.G.RB];
out.g0 = g0;
emit(JSON.stringify(out));
"""


def _placed() -> dict:
    return json.loads(js_engine.run(SKY + _PLACE))


def test_the_card_keeps_off_glorfindel_and_off_what_was_clicked_all_around_the_sky():
    p = _placed()
    for ring in (72, 88, 101):
        for frame in ("1336x420", "1280x420", "1210x420", "1210x700"):        # a large screen: beside it, always
            assert p[f"{ring}@{frame}"] == {"over": 0, "covers": 0, "outside": 0, "docked": 0}, (ring, frame)
        for frame in ("900x380", "844x380", "470x300"):                         # no room off the disc: under the circle
            assert p[f"{ring}@{frame}"] == {"over": 0, "covers": 0, "outside": 0, "docked": 108}, (ring, frame)


def test_the_card_is_held_within_the_window_s_band_of_its_frame():
    b = _placed()["band"]
    assert 308 <= b["top"] <= 900 - 300 - 8, b                                  # never above the window's top


def test_the_card_opens_beside_what_was_clicked_on_its_outer_side():
    b = _placed()["beside"]
    assert b["left"] >= 1020 and abs(b["top"] + 150 - 310) <= 1                   # right of it, level with it


def test_the_centre_follows_the_estate_between_80_and_140_percent():
    p = _placed()
    assert p["scale"] == [1.4, 1.4, 1.4, 1.3, 1, 0.9, 0.8, 0.8, 1.4]   # a count not a number: none, the small estate's
    assert p["g0"] == [72, 172]                                        # the size it always had, untouched until asked
    assert p["size4"] == [1.4, 101, 241] and p["size25"] == [1, 72, 172] and p["size60"] == [0.8, 58, 138]


# The draw, mounted on a DOM of the test's: three tiles — the centre at 140 %; the satellites' lines; told where it is.
_MOUNT = r"""
function El(tag) { this.tagName = tag; this.attrs = {}; this.children = []; this.parentNode = null; this.style = {}; this.dataset = {}; this.textContent = ''; }
El.prototype.setAttribute = function (k, v) { v = String(v); if (k.startsWith('data-')) this.dataset[k.slice(5)] = v; else this.attrs[k] = v; };
El.prototype.getAttribute = function (k) { const v = k.startsWith('data-') ? this.dataset[k.slice(5)] : this.attrs[k]; return v === undefined ? null : v; };
El.prototype.appendChild = function (c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; };
El.prototype.remove = function () { const p = this.parentNode; if (p) { p.children = p.children.filter(x => x !== this); this.parentNode = null; } };
El.prototype.replaceChildren = function () { this.children.forEach(c => { c.parentNode = null; }); this.children = []; };
El.prototype.addEventListener = function () {};
El.prototype.getBoundingClientRect = function () { return this.rect || { left: 0, top: 0, width: 0, height: 0 }; };
El.prototype.all = function () { return this.children.flatMap(c => [c, ...c.all()]); };
El.prototype.contains = function (x) { for (let e = x; e; e = e.parentNode) if (e === this) return true; return false; };
El.prototype.querySelectorAll = function (sel) { const m = /^\[([\w-]+)\]$/.exec(sel); return this.all().filter(e => e.getAttribute(m[1]) !== null); };
El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
El.prototype.closest = function (sel) { const m = /^\[([\w-]+)\]$/.exec(sel); for (let e = this; e; e = e.parentNode) if (e.getAttribute(m[1]) !== null) return e; return null; };
Object.defineProperty(El.prototype, 'isConnected', { get() { let e = this; while (e.parentNode) e = e.parentNode; return e === root; } });
const root = new El('div');
let frameFn = null;
(function (document, getComputedStyle, requestAnimationFrame) {
  SKY_SRC
  DRAW_SRC
  const T = (key, s) => ({ key, name: key, own: '', sub: 's', tenant: false, out: false, law: 'nb-law', nsg: 'nsg:web', vault: 'nb-rsv', s });
  const tiles = [T('web-1', { d: 'judge', p: 'isolated', r: 'restoring' }), T('web-2', { d: 'watched', p: 'ready', r: 'protected' }),
                 T('web-3', { d: 'watched', p: 'ready', r: 'protected' })];
  const model = { mode: 'rg', tiles, lanes: [{ key: 's/rg', label: 'rg', own: true, tiles }], sectors: {}, watch: 0, reduced: false,
    backends: { d: [{ id: 'nb-law', name: 'law', sub: '3 watched · 1 to judge' }], p: [{ id: 'nsg:web', name: 'nsg-web', sub: '3 governed · 1 acted on' }],
                r: [{ id: 'nb-rsv', name: 'rsv', sub: '3 protected · 1 restoring' }] }, heartOf: () => null };
  const slot = new El('div'); root.appendChild(slot);
  let placed = 0;
  InfraSkyDraw.mount(slot, model, () => {}, () => { placed++; });
  const svg = slot.children[0], out = { placed_mount: placed };
  out.core = Number(svg.all().find(e => (e.attrs.class || '') === 'sky-heart').attrs.r);
  out.ring = InfraSky.G.RG;
  out.subs = svg.all().map(e => e.textContent).filter(t => / · |watched|governed|protected/.test(t)).sort();
  model.backends.d[0].sub = '3 watched'; InfraSkyDraw.mount(slot, model);        // a refresh: its line follows, no rebuild
  out.sub_after = svg.all().some(e => e.textContent === '3 watched') && !svg.all().some(e => e.textContent === '3 watched · 1 to judge');
  const before = placed; frameFn(16); frameFn(32); out.placed_frames = placed - before;   // the planets turn: told
  svg.rect = { left: 10, top: 20, width: 500, height: 460 };
  out.centre = InfraSkyDraw.centre();
  const star = svg.all().find(e => e.dataset.a === 'web-2'); star.rect = { left: 1, top: 2, width: 3, height: 4 };
  out.rect = InfraSkyDraw.rectOf({ a: 'web-2' }); out.none = InfraSkyDraw.rectOf(null);
  emit(JSON.stringify(out));
})({ createElementNS: (ns, tag) => new El(tag), documentElement: root }, () => ({ getPropertyValue: n => n.slice(2) }), f => { frameFn = f; return 1; });
"""


def _mounted() -> dict:
    return json.loads(js_engine.run(_MOUNT.replace("SKY_SRC", SKY).replace("DRAW_SRC", DRAW)))


def test_a_small_estate_gets_a_larger_centre():
    m = _mounted()
    assert m["ring"] == 101 and m["core"] == 24                         # 3 resources: 140 % (72 → 101, 17 → 24)


def test_each_satellite_says_what_its_block_says_under_its_name():
    m = _mounted()
    assert m["subs"] == ["3 governed · 1 acted on", "3 protected · 1 restoring", "3 watched · 1 to judge"]
    assert m["sub_after"] is True                                        # at the next refresh, as it is then


def test_the_page_is_told_where_the_card_goes_as_the_bodies_move():
    m = _mounted()
    assert m["placed_mount"] == 1 and m["placed_frames"] == 2            # at the mount, at each frame that moves
    assert m["centre"] == {"x": 260, "y": 250, "r": (101 + 46) * 0.5}    # Glorfindel's disc, in the page's pixels
    assert m["rect"] == {"left": 1, "top": 2, "width": 3, "height": 4} and m["none"] is None


# The page's card: placed by placeCard in its frame; on a phone, its CSS (under the circle).
_CARD = r"""
const style = {}, classes = new Set();
let scrolled = 0, measured = [];
// Its width as the CSS gives it: under the circle (`.docked`, width: auto), the frame's; floating, 340 — the second
// relecture: a fake width of 340 whatever its class hid a card docked for good.
const box = { hidden: false, offsetHeight: 300, style, scrollIntoView: () => { scrolled++; },
              get offsetWidth() { const w = classes.has('docked') ? wrapRect.width : 340; measured.push(w); return w; },
              classList: { toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c); }, remove: c => classes.delete(c) } };
let wrapRect = { left: 100, top: 50, width: 1400, height: 900 }, colRect = { top: 0, bottom: 1000 };
const wrap = { getBoundingClientRect: () => wrapRect }, col = { getBoundingClientRect: () => colRect };
const fakeDoc = { getElementById: id => (id === 'sky-panel' ? box : id === 'sky-wrap' ? wrap : id === 'topo-graph' ? col : null) };
let _skyDock = { w: -1, docked: false };
let phone = false, centre = { x: 800, y: 500, r: 150 }, target = { left: 1100, top: 350, width: 20, height: 20 };
const _isPhone = () => phone;
const InfraSkyDraw = { pinned: () => ({ a: 'k' }), rectOf: () => target, centre: () => centre };
(function (document, window) {
  SKY_SRC
  PAGE_FNS
  const out = {};
  _skyPlaceCard(true); out.desk = [style.left, style.top, classes.has('docked'), scrolled];
  // The column scrolled (#topo-graph, its top at 79 under the column's header), the frame's top 400 px above the window:
  // the card held within what is seen of the column, never under its header.
  wrapRect = { left: 100, top: -400, width: 1400, height: 1300 }; colRect = { top: 79, bottom: 760 };
  target = { left: 1100, top: -300, width: 20, height: 20 }; centre = { x: 800, y: 250, r: 150 };
  _skyPlaceCard(true); out.band = style.top;
  target = { left: 1100, top: 700, width: 20, height: 20 }; _skyPlaceCard(true); out.band_low = style.top;   // near the column's foot
  wrapRect = { left: 100, top: 50, width: 1400, height: 900 }; colRect = { top: 0, bottom: 1000 }; target = { left: 1100, top: 350, width: 20, height: 20 };
  phone = true; _skyPlaceCard(); out.phone = [style.left, style.top];
  // A narrow frame: no room off the disc — under the circle, brought into view when it opens only.
  phone = false; wrapRect = { left: 100, top: 50, width: 700, height: 640 }; centre = { x: 450, y: 370, r: 140 };
  _skyPlaceCard(true); out.docked = [style.left, style.top, classes.has('docked'), scrolled];
  measured = []; _skyPlaceCard(); out.again = [scrolled, measured.length];  // the bodies move, the same width: it stays, unmeasured
  // The frame widened (the window too): decided again, measured floating — beside its tile, no longer under the circle.
  wrapRect = { left: 100, top: 50, width: 1400, height: 900 }; centre = { x: 800, y: 500, r: 150 };
  measured = []; _skyPlaceCard(); out.widened = [style.left, classes.has('docked'), measured];
  box.hidden = true; style.left = 'x'; _skyPlaceCard(); out.closed = style.left;
  emit(JSON.stringify(out));
})(fakeDoc, { innerHeight: 1000 });
"""


def test_the_page_places_the_card_in_its_frame_and_leaves_it_to_its_css_on_a_phone():
    script = _CARD.replace("SKY_SRC", SKY).replace("PAGE_FNS", js_engine.take(JS, "_skyPlaceCard"))
    got = json.loads(js_engine.run(script))
    assert got["desk"] == ["1034px", "160px", False, 0]   # beside it in the frame: 1100 − 100 + 20 + 14, level with it
    assert 479 + 8 <= int(got["band"][:-2]) <= 760 + 400 - 300 - 8   # within the column seen: under its header (79), above its foot
    assert int(got["band_low"][:-2]) <= 760 + 400 - 300 - 8          # near the column's foot: never below it
    assert got["phone"] == ["", ""]                    # a phone: under the circle, by its CSS
    assert got["docked"] == ["", "", True, 1]          # no room off the disc: under the circle, brought into view
    assert got["again"] == [1, 0]                      # placed again as the bodies move: never scrolled, never measured
    assert got["widened"] == ["1034px", False, [340]]  # the frame widened: measured floating (340), beside it again
    assert got["closed"] == "x"                        # closed: nothing moved


_MODULE = r"""
let _moduleBlocks = { p: '<div class="topo-module">PROTECT block: nsg-web, 2 NSGs</div>' }, _skyRest = '<div>modules</div>';
const _tiles = new Map(), _skyCtx = {};
FNS
const m = { tiles: [], lanes: [], backends: { d: [], p: [{ id: 'nsg:web', name: 'nsg-web' }], r: [] } };
emit(JSON.stringify([_skyPanelHtml({ m: 'p' }, m), _skyPanelHtml({ m: 'judge' }, m), _skyPanelHtml({ m: 'toString' }, m)]));
"""


def test_a_module_s_card_holds_its_whole_block_and_a_focus_on_no_module_the_modules():
    fns = js_engine.take(JS, "_attr", "_skyPanelHtml")
    mod, judge, bogus = json.loads(js_engine.run(SKY + _MODULE.replace("FNS", fns)))
    assert "PROTECT block: nsg-web, 2 NSGs" in mod and "nsg-web" in mod
    assert judge.endswith("<div>modules</div>") and bogus.endswith("<div>modules</div>")


def test_what_cannot_wait_for_a_click_is_said_above_the_sky_and_the_card_s_css():
    sky = JS.split("\nfunction _renderSky(", 1)[1].split("\n}\n", 1)[0]
    assert "${_groupBar('sky')}${_inertBanner()}${_exclusionsBand()}${_auditBand()}" in sky   # detection inert, at rest
    assert 'class="sky-hint"' in sky and "hidden></aside>" in sky                               # closed at the start
    assert "  .sky-wrap { position: relative; }" in STYLE and "  .sky-panel[hidden] { display: none; }" in STYLE
    assert "    .sky-panel { position: static; width: auto; max-height: none;" in PHONE         # a phone: under the circle


# The card's guards, run as they are: writes blocked (read-only, the queue), its tile's buttons that write disabled, its
# ✕ not; closed from within, the keyboard's focus back on what was pinned (the relecture of SKY4).
_GUARDED = r"""
let focus = { a: 'k' }, active = null, focusedOn = null;
const mk = action => ({ tagName: 'BUTTON', disabled: false, title: '', inside: true, getAttribute: k => (k === 'data-on-click' ? action : null) });
const buttons = [mk('confirmRelease'), mk('doSnapshot'), mk('skyUnpin'), mk('judgeCard')];
const box = { childElementCount: 0, scrollTop: 0, hidden: true, style: {}, replaceChildren() { this.childElementCount = 0; },
  set innerHTML(v) { this.childElementCount = 1; }, contains: e => !!e && e.inside === true, querySelector: () => null,
  querySelectorAll: sel => (sel === 'button' ? buttons : []) };
const doc = { getElementById: id => (id === 'sky-panel' ? box : null), get activeElement() { return active; } };
const InfraSkyDraw = { focus: () => focus, pinned: () => focus, focusOn: f => { focusedOn = f; } };
let _skyModelLast = { tiles: [], lanes: [], backends: { d: [], p: [], r: [] } }, _skyRest = '', _skyCtx = {}, _state = { read_only: true };
const _tiles = new Map([['k', { key: 'k', vm_name: 'web-1' }]]);
const _unfolded = () => '<div class="node-asset">tile</div>', _skyPlaceCard = () => {}, _isOor = () => false;
const run = (function (document) { PANEL_FNS; return _skyPanel; })(doc);
run();
const out = { disabled: buttons.map(b => [b.getAttribute('data-on-click'), b.disabled, b.title !== '']) };
active = buttons[2]; focus = null; run(); out.focus_back = JSON.stringify(focusedOn);      // closed from its ✕
focus = { a: 'k' }; run(); active = null; focusedOn = null; focus = null; run(); out.focus_kept = focusedOn;   // closed from elsewhere
emit(JSON.stringify(out));
"""


def test_the_card_s_writes_are_disabled_when_writes_are_blocked_and_the_focus_comes_back_on_close():
    fns = js_engine.take(JS, "_attr", "_on", "_WRITE_HANDLERS", "_OOR_DROPS", "_dropWrites", "_writesBlocked", "_applyReadOnlyGuards",
                         "_skyFocusSig", "_SKY_CARD_X", "_skyPanelHtml", "_skyPanel")
    got = json.loads(js_engine.run(SKY + _GUARDED.replace("PANEL_FNS", "let _skyPanelLast = '', _skyGuardLast = '', _moduleBlocks = {}, _skyCardOf = null;\n" + fns)))
    assert got["disabled"] == [["confirmRelease", True, True], ["doSnapshot", True, True], ["skyUnpin", False, False],
                               ["judgeCard", False, False]]                    # a write, disabled and said why; a verdict, not
    assert got["focus_back"] == '{"a":"k"}'                                     # closed from within: back on what was pinned
    assert got["focus_kept"] is None                                            # closed from elsewhere: the focus left where it is
