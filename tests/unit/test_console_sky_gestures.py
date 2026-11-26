"""SKY3 (#1246): the 360°'s hover and its pin, as Jonathan found them on Imladris (26/11).

Two defects of the 360° shipped in 0.6.11:
  - entering the big circle greyed everything. Above all, the sky read what the pointer was on up to the page: its
    <body> carries a data-m of its own (the phone's tab, « judge »), and an empty spot of the sky took a focus on that
    « module » — measured on the sample, everything dimmed. It reads within the sky only now. And a system answered the
    pointer on a transparent disc of 1.3 times its orbit plus 14 px. Its reach is now its orbit
    (plus 6 px), and a hover waits a moment (140 ms) before it dims the rest: the pointer that only passes, entering
    the sky or going from one body to the next, lights nothing; leaving the sky is at once, the keyboard too;
  - a pinned selection stayed when the click was elsewhere (the feed): only a click in the sky let it go. A click
    outside the sky and its panel — a window aside — now lets go, and Escape too, unless a window is open.

The draw runs as it is (infra_sky.js, infra_sky_draw.js) on a DOM and timers of the test's, in Node or a headless
Chromium (tests/unit/js_engine.py), inside a function's scope: a Chromium's own document never seen. The page's
handlers (`_skyClickAway`, `_skyEscape`) run as they are, on events of the test's.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")


def _T(key: str, **kw) -> dict:
    return {"key": key, "name": key.split("/")[-1], "own": "", "sub": "s-prod", "tenant": False, "out": False,
            "law": "nb-law", "nsg": "nsg:web", "vault": "nb-rsv", "s": {"d": "watched", "p": "ready", "a": False, "r": "protected"}, **kw}


_TILES = [
    _T("entra:identities", own="identity", tenant=True, sub="", nsg="", vault="", s={"d": "watched", "p": None, "a": False, "r": None}),
    _T("/s/prod/rg-web/web-1"), _T("/s/prod/rg-web/web-2"),
]

_MOUNT = r"""
function El(tag) {
  this.tagName = tag; this.attrs = {}; this.children = []; this.parentNode = null; this.style = {}; this.dataset = {};
  this.textContent = ''; this.handlers = {};
}
El.prototype.setAttribute = function (k, v) {
  v = String(v);
  if (k.startsWith('data-')) this.dataset[k.slice(5)] = v; else this.attrs[k] = v;
};
El.prototype.getAttribute = function (k) {
  const v = k.startsWith('data-') ? this.dataset[k.slice(5)] : this.attrs[k];
  return v === undefined ? null : v;
};
El.prototype.appendChild = function (c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; };
El.prototype.remove = function () { const p = this.parentNode; if (p) { p.children = p.children.filter(x => x !== this); this.parentNode = null; } };
El.prototype.replaceChildren = function () { this.children.forEach(c => { c.parentNode = null; }); this.children = []; };
El.prototype.addEventListener = function (type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); };
El.prototype.fire = function (type, target, key) { (this.handlers[type] || []).forEach(fn => fn({ target, key, preventDefault() {} })); };
El.prototype.getBoundingClientRect = function () { return { x: 0, y: 0, width: 0, height: 0 }; };
El.prototype.all = function () { return this.children.flatMap(c => [c, ...c.all()]); };
El.prototype.contains = function (x) { for (let e = x; e; e = e.parentNode) if (e === this) return true; return false; };
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
root.dataset.m = 'judge';                       // the page's <body>: its own data-m, the phone's tab
const fakeDoc = { createElementNS: (ns, tag) => new El(tag), documentElement: root };
let clock = 0, timers = [], nextId = 1;
const later = (fn, ms) => { const id = nextId++; timers.push({ id, at: clock + ms, fn }); return id; };
const forget = id => { timers = timers.filter(t => t.id !== id); };
const advance = ms => { clock += ms; const due = timers.filter(t => t.at <= clock); timers = timers.filter(t => t.at > clock); due.forEach(t => t.fn()); };
(function (document, getComputedStyle, requestAnimationFrame, setTimeout, clearTimeout) {
  SKY_SRC
  DRAW_SRC
  const lanes = [{ key: 'tenant', label: 'tenant', tiles: [TILES[0]] },
                 { key: 's-prod/rg-web', label: 'Prod / rg-web', own: true, tiles: [TILES[1], TILES[2]] }];
  const model = { mode: 'rg', tiles: TILES, lanes, sectors: {}, backends: { d: [{ id: 'nb-law', name: 'law' }],
    p: [{ id: 'nsg:web', name: 'nsg-web' }], r: [{ id: 'nb-rsv', name: 'rsv' }] }, watch: 0, reduced: true, heartOf: () => null };
  const slot = new El('div'); root.appendChild(slot);
  InfraSkyDraw.mount(slot, model);
  const svg = slot.children[0], out = {};
  const planet = svg.all().find(e => e.dataset.a === TILES[1].key).children[0];   // its own reach: a child of the planet
  const sky = svg.children[0].children[0];                                      // a star of the sky: nothing of the map
  const sun = svg.all().find(e => e.dataset.s);
  const body = InfraSky.layout(InfraSky.bodies(TILES, lanes, 'rg')).bodies.find(b => b.planets.length);
  out.reach = [Number(sun.children[0].attrs.r), body.pr];
  const f = () => JSON.stringify(InfraSkyDraw.focus());
  // A hover waits: nothing at once, nothing at 100 ms, the planet at 140.
  svg.fire('mouseover', planet); out.at0 = f(); advance(100); out.at100 = f(); advance(40); out.at140 = f();
  svg.fire('mouseleave'); out.left = f();                                       // leaving the sky: at once
  // The pointer that only passes: over the planet, then onto the sky before 140 ms — nothing lit, ever.
  svg.fire('mouseover', planet); advance(60); svg.fire('mouseover', sky); advance(400); out.passed = f();
  // Out of the sky before 140 ms: the hover it was going to give, never given.
  svg.fire('mouseover', planet); advance(60); svg.fire('mouseleave'); advance(400); out.out_early = f();
  // An empty spot of the sky, the page around it carrying a data-m of its own: nothing lit, ever.
  svg.fire('mouseover', sky); advance(400); out.blank = f(); svg.fire('mouseover', svg); advance(400); out.blank_svg = f();
  // The keyboard and a click: at once.
  svg.fire('focusin', planet); out.keyboard = f(); svg.fire('mouseleave');
  svg.fire('click', planet); out.pinned = JSON.stringify(InfraSkyDraw.pinned());
  InfraSkyDraw.unpin(); out.unpinned = JSON.stringify(InfraSkyDraw.pinned());
  emit(JSON.stringify(out));
})(fakeDoc, () => ({ getPropertyValue: n => n.slice(2) }), () => 1, later, forget);
"""


def _gestures() -> dict:
    script = (_MOUNT.replace("TILES", "TILES_").replace("SKY_SRC", SKY).replace("DRAW_SRC", DRAW))
    return json.loads(js_engine.run(f"const TILES_ = {json.dumps(_TILES)};\n" + script))


def test_a_system_answers_the_pointer_on_its_orbit_only():
    g = _gestures()
    reach, orbit = g["reach"]
    assert reach == orbit + 6, (reach, orbit)               # before: 1.3 times its orbit, plus 14 px


def test_a_hover_waits_a_moment_before_it_dims_the_rest():
    g, key = _gestures(), json.dumps({"a": _TILES[1]["key"]}, separators=(",", ":"))
    assert g["at0"] == "null" and g["at100"] == "null" and g["at140"] == key
    assert g["left"] == "null"                               # leaving the sky: at once


def test_a_pointer_that_only_passes_lights_nothing():
    g = _gestures()
    assert g["passed"] == "null"                             # over a planet, onto the sky before 140 ms
    assert g["out_early"] == "null"                          # out of the sky before 140 ms


def test_an_empty_spot_of_the_sky_lights_nothing_whatever_the_page_carries():
    """The page's <body> carries a data-m of its own (the phone's tab): read as a module, an empty spot of the sky took
    a focus on « judge », no module, and dimmed everything — what Jonathan saw entering the circle."""
    g = _gestures()
    assert g["blank"] == "null" and g["blank_svg"] == "null"


def test_the_keyboard_and_a_click_do_not_wait():
    g, key = _gestures(), json.dumps({"a": _TILES[1]["key"]}, separators=(",", ":"))
    assert g["keyboard"] == key and g["pinned"] == key and g["unpinned"] == "null"


_PAGE = r"""
let pinned = null, unpins = 0, open = false;
const InfraSkyDraw = { pinned: () => pinned, unpin: () => { unpins++; pinned = null; } };
const fakeDoc = { getElementById: id => (id === 'modal' ? { classList: { contains: c => c === 'open' && open } } : null) };
const at = ids => ({ composedPath: () => ids.map(id => ({ id })) });
(function (document) {
  PAGE_FNS
  const out = {}, pin = () => { pinned = { a: 'k' }; unpins = 0; };
  pin(); _skyClickAway(at(['', 'sky-panel', 'sky-wrap', 'topo-body', ''])); out.in_panel = unpins;   // a button of the panel
  pin(); _skyClickAway(at(['', 'sky-slot', 'sky-wrap'])); out.in_sky = unpins;                      // the sky's own (it pins)
  pin(); _skyClickAway(at(['', 'modal-confirm', 'modal'])); out.in_window = unpins;                 // a window it opened
  pin(); _skyClickAway(at(['', 'feed-list', 'feed-col', ''])); out.in_feed = unpins;                // the feed: lets go
  pin(); _skyClickAway({}); out.no_path = unpins;                                                   // no path: elsewhere
  pinned = null; unpins = 0; _skyClickAway(at(['feed-list'])); out.nothing_pinned = unpins;
  pin(); _skyEscape({ key: 'Escape' }); out.escape = unpins;
  pin(); open = true; _skyEscape({ key: 'Escape' }); out.escape_window = unpins; open = false;
  pin(); _skyEscape({ key: 'a' }); out.other_key = unpins;
  emit(JSON.stringify(out));
})(fakeDoc);
"""


def _page() -> dict:
    return json.loads(js_engine.run(_PAGE.replace("PAGE_FNS", js_engine.take(JS, "_skyClickAway", "_skyEscape"))))


def test_a_click_elsewhere_lets_go_never_one_in_the_sky_its_panel_or_a_window():
    p = _page()
    assert p["in_panel"] == 0 and p["in_sky"] == 0 and p["in_window"] == 0
    assert p["in_feed"] == 1 and p["no_path"] == 1 and p["nothing_pinned"] == 0


def test_escape_lets_go_unless_a_window_is_open():
    p = _page()
    assert p["escape"] == 1 and p["escape_window"] == 0 and p["other_key"] == 0


def test_the_page_listens_on_the_whole_document():
    assert "document.addEventListener('click', _skyClickAway);" in JS
    assert "document.addEventListener('keydown', _skyEscape);" in JS
