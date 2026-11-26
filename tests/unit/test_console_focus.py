"""FOC1 (#1231): the focus in the infrastructure map (Jonathan, 26/11, on a mockup).

A tile hovered, or given the keyboard's focus, stays sharp and its lines come to the front, a little thicker; the
other tiles and lines step back to about 30 %. A backend hovered: its lines and the tiles they reach. About 120 ms
of delay, so that the map never flickers from one tile to the next; no focus while a tile is dragged, while a
window is open, or on a phone. A click still unfolds a tile.

The logic (`infra_focus.js`) runs as it is, in Node or a headless Chromium (tests/unit/js_engine.py); what the page
ties to it (`_focusOf`, the lines' ends, the drag, the window) is read in glorfindel.js.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
FOCUS = (STATIC / "infra_focus.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")

# The lines as the map draws them: Glorfindel to its backends, then the backends to the tiles.
_LINES = [
    {"k": "", "b": "nb-law-prod"}, {"k": "", "b": "module-protect"}, {"k": "", "b": "nb-rsv"},
    {"k": "/s/a/vm/bree", "b": "nb-law-prod"}, {"k": "/s/a/vm/bree", "b": "module-protect"}, {"k": "/s/a/vm/bree", "b": "nb-rsv"},
    {"k": "/s/a/vm/gondolin", "b": "nb-law-prod"}, {"k": "/s/a/vm/gondolin", "b": "module-protect"},
    {"k": "entra:identities", "b": "nb-law-prod"},
]
_HARNESS = r"""
const out = {}, F = InfraFocus;
const pick = r => r && { lines: [...r.lines], tiles: [...r.tiles].sort(), nodes: [...r.nodes].sort() };
out.none = F.lit(null, LINES);
out.tile = pick(F.lit({ tile: '/s/a/vm/gondolin' }, LINES));
out.backend = pick(F.lit({ backend: 'module-protect' }, LINES));
out.alone = pick(F.lit({ tile: 'discovered:x' }, LINES));
out.allowed = [{}, { dragging: true }, { modal: true }, { phone: true }, { view: 'tiles' }, { view: 'table' }, { view: 'sky' }].map(e => F.allowed(e));
// Fake timers: the time is ours.
let now = 0, seq = 0; const timers = new Map();
const later = (f, ms) => { const id = ++seq; timers.set(id, { at: now + ms, f }); return id; };
const cancel = id => timers.delete(id);
const tick = ms => { now += ms; for (const [id, t] of [...timers]) if (t.at <= now) { timers.delete(id); t.f(); } };
const applied = [];
const S = F.scheduler(later, cancel, f => applied.push(f ? (f.tile || f.backend) : null));
S.want({ tile: 'A' }); tick(60); out.before_delay = applied.slice();
tick(80); out.after_delay = applied.slice();
// From A to B through the gap between them: never « nothing » in between.
S.want(null); tick(40); S.want({ tile: 'B' }); tick(200); out.a_to_b = applied.slice();
// Wanted again while it is the current one: nothing redrawn.
S.want({ tile: 'B' }); tick(200); out.same = applied.slice();
// The same focus wanted again while it waits (a child of the tile crossed): the delay runs on.
S.want({ tile: 'D' }); tick(60); S.want({ tile: 'D' }); tick(70); out.child = applied.slice(-1)[0];
// A drag: at once, and what was pending never comes after.
S.want({ tile: 'C' }); tick(30); S.now(null); tick(300); out.now = applied.slice(); out.current = S.current();
out.delay = F.DELAY;
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    return json.loads(js_engine.run(FOCUS + f"const LINES = {json.dumps(_LINES)};\n" + _HARNESS))


def test_nothing_focused_nothing_steps_back(ran):
    assert ran["none"] is None


def test_a_tile_lights_itself_its_lines_and_the_nodes_they_leave(ran):
    assert ran["tile"] == {"lines": [6, 7], "tiles": ["/s/a/vm/gondolin"], "nodes": ["module-protect", "nb-law-prod"]}


def test_a_backend_lights_its_lines_and_the_tiles_they_reach(ran):
    assert ran["backend"] == {"lines": [1, 4, 7], "tiles": ["/s/a/vm/bree", "/s/a/vm/gondolin"], "nodes": ["module-protect"]}


def test_a_tile_without_a_line_still_stays_sharp(ran):
    assert ran["alone"] == {"lines": [], "tiles": ["discovered:x"], "nodes": []}


def test_no_focus_while_dragging_in_a_window_or_on_a_phone(ran):
    assert ran["allowed"] == [True, False, False, False, True, False, False]   # the focus is the tiles' only


def test_the_focus_waits_about_120_ms_and_never_flickers(ran):
    assert ran["delay"] == 120
    assert ran["before_delay"] == [] and ran["after_delay"] == ["A"]
    assert ran["a_to_b"] == ["A", "B"]                 # from A to B: never « nothing » in between
    assert ran["same"] == ["A", "B"]


def test_the_same_focus_wanted_again_while_it_waits_keeps_its_delay(ran):
    """A child of the tile crossed asks for the same focus: it comes 120 ms after the first ask, not after the last."""
    assert ran["child"] == "D"


def test_a_drag_or_a_window_takes_the_focus_off_at_once(ran):
    assert ran["now"] == ["A", "B", "D", None] and ran["current"] is None   # C, pending, never came


# ── What the page ties to it ─────────────────────────────────────────────────────────────────────────────
def _fn(name: str) -> str:
    m = re.search(r"^function " + re.escape(name) + r"\(", JS, re.M)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def test_the_page_loads_the_logic_before_it():
    assert HTML.index('<script src="/static/infra_focus.js"></script>') < HTML.index('<script src="/static/glorfindel.js"></script>')


def test_every_line_onto_a_tile_says_the_tile_and_the_node_it_leaves():
    """Each line onto a tile is drawn after its tile (K) and the node it leaves (B) are set: none says another's."""
    edges = _fn("_drawTopologyEdges")
    assert 'data-k="${_attr(K)}" data-b="${_attr(B)}"' in edges          # escaped: a key comes from outside
    assert "    K = el.id.slice('asset-'.length);              // FOC1: the lines below reach this tile" in edges
    assert "    K = vm;\n" in edges                                        # a card's waiting line
    for b in ("B = 'module-protect';", "B = `nb-${b.name}`;", "B = `nb-${recoverBackends[0].name}`;",
              "B = disc ? `nb-${disc.monitoring_backend}` : detectBackends.length ? `nb-${detectBackends[0].name}` : '';"):
        assert b in edges, b
    assert edges.count("      B = 'module-protect';") == 2                # an NSG's tile, a VM's PROTECT lines
    assert "_applyFocus();" in edges                    # the focus survives a redraw


# A page of our own, in a scope of its own: Chromium has its document and Element already.
_DOM = r"""
class FakeEl { constructor(id, parent) { this.id = id; this.parent = parent; }
  closest(sel) { for (let e = this; e; e = e.parent) { if (sel.includes('asset-') && /^asset-/.test(e.id)) return e;
    if (sel.includes('nb-') && (/^nb-/.test(e.id) || e.id === 'module-protect')) return e; } return null; } }
const body = new FakeEl('topo-body', null);
body.contains = e => { for (let x = e; x; x = x.parent) if (x === body) return true; return false; };
const doc = { getElementById: id => (id === 'topo-body' ? body : null) };
const tile = new FakeEl('asset-/s/a/vm/bree', body), inTile = new FakeEl('', tile);
const nb = new FakeEl('nb-law-prod', body), prot = new FakeEl('module-protect', body);
const gap = new FakeEl('', body), outside = new FakeEl('asset-elsewhere', null);
const focusOf = (function (document, Element) { FOCUS_OF; return _focusOf; })(doc, FakeEl);
emit(JSON.stringify([inTile, nb, prot, gap, outside, 'text'].map(e => focusOf(e))));
"""


def test_what_is_under_the_pointer_a_tile_a_backend_or_nothing_of_the_map():
    got = json.loads(js_engine.run(_DOM.replace("FOCUS_OF", js_engine.take(JS, "_focusOf"))))
    assert got == [{"tile": "/s/a/vm/bree"}, {"backend": "nb-law-prod"}, {"backend": "module-protect"}, None, None, None]


def test_a_drag_and_a_window_take_the_focus_off_and_a_tile_takes_the_keyboard():
    assert "    _focusSched.now(null);                        // FOC1: no focus while a tile is dragged" in JS
    assert "if (window.MutationObserver) new MutationObserver(() => { if (_focusEnv().modal) _focusSched.now(null); })" in JS
    assert len(re.findall(r'return `<div class="node-asset [^\n]*" tabindex="0"\n    id="asset-', JS)) == 3   # a VM's, an NSG's or one of its own, a cluster's
    assert "document.addEventListener('focusin', _focusMove);" in JS
    assert "document.addEventListener('mouseout', ev => { if (!ev.relatedTarget) _focusSched.want(null); });" in JS   # out of the window


def test_a_tile_steps_back_by_its_filter_never_its_opacity_and_no_fade_for_less_motion():
    assert '.topo-graph.focus-on [id^="asset-"]:not(.lit), .topo-graph.focus-on .node-backend:not(.lit) { filter: opacity(.3); }' in HTML
    media = HTML.index("@media (prefers-reduced-motion: reduce)")
    line = HTML.index('#topo-svg path, .topo-graph [id^="asset-"], .topo-graph .node-backend { transition: none; }')
    assert media < line < media + 600                    # inside the block of less motion


def test_the_logic_is_pure():
    body = FOCUS.split("const InfraFocus", 1)[1]
    for word in ("document.", "window.", "setTimeout", "fetch(", "localStorage", "innerHTML"):
        assert word not in body, word


# ── The page's focus, run as it is on a page of our own (Chromium has its document: a scope of its own) ───────
_PAGE_DOM = r"""
class CL { constructor() { this.s = new Set(); } add(c) { this.s.add(c); } remove(c) { this.s.delete(c); }
  toggle(c, on) { (on === undefined ? !this.s.has(c) : on) ? this.s.add(c) : this.s.delete(c); } contains(c) { return this.s.has(c); } }
class FakeEl {
  constructor(tag, id, parent, data) { this.tag = tag; this.id = id || ''; this.parent = parent || null; this.kids = [];
    this.classList = new CL(); this.dataset = data || {}; if (parent) parent.kids.push(this); }
  all() { return this.kids.flatMap(k => [k, ...k.all()]); }
  querySelectorAll(sel) { const a = this.all(); return sel === '.lit' ? a.filter(e => e.classList.contains('lit')) : sel === 'path' ? a.filter(e => e.tag === 'path') : []; }
  appendChild(c) { if (c.parent) c.parent.kids = c.parent.kids.filter(k => k !== c); c.parent = this; this.kids.push(c); return c; }
  closest(sel) { for (let e = this; e; e = e.parent) { if (sel.includes('asset-') && /^asset-/.test(e.id)) return e;
    if (sel.includes('nb-') && (/^nb-/.test(e.id) || e.id === 'module-protect')) return e; } return null; }
  contains(e) { for (let x = e; x; x = x.parent) if (x === this) return true; return false; }
}
const root = new FakeEl('div', 'root'), graph = new FakeEl('div', 'topo-graph', root), svg = new FakeEl('svg', 'topo-svg', graph);
const body = new FakeEl('div', 'topo-body', graph), modal = new FakeEl('div', 'modal', root);
const tA = new FakeEl('div', 'asset-A', body), inA = new FakeEl('span', '', tA), tB = new FakeEl('div', 'asset-B', body);
new FakeEl('div', 'nb-law', body); new FakeEl('div', 'module-protect', body); new FakeEl('div', 'nb-rsv', body);
[['', 'nb-law'], ['A', 'nb-law'], ['B', 'module-protect'], ['A', 'module-protect']].forEach(([k, b], i) => new FakeEl('path', 'p' + i, svg, { k, b }));
const doc = { body: new FakeEl('body', ''), getElementById: id => [root, ...root.all()].find(e => e.id === id) || null };
const win = { matchMedia: () => ({ matches: false }) };
let now = 0, seq = 0; const timers = new Map();
const later = (f, ms) => { const id = ++seq; timers.set(id, { at: now + ms, f }); return id; };
const cancel = id => timers.delete(id);
const tick = ms => { now += ms; for (const [id, t] of [...timers]) if (t.at <= now) { timers.delete(id); t.f(); } };
let VIEW = 'tiles';
const page = (function (document, window, Element) {
  let _focus = null;
  const _infraView = () => VIEW;
  const _focusSched = InfraFocus.scheduler(later, cancel, f => { _focus = f; _applyFocus(); });
  PAGE_FNS
  return { set: f => { _focus = f; }, apply: () => _applyFocus(), move: target => _focusMove({ target }) };
})(doc, win, FakeEl);
const lit = () => [root, ...root.all()].filter(e => e.classList.contains('lit')).map(e => e.id).sort();
const out = {};
page.set({ tile: 'A' }); page.apply();
out.on = graph.classList.contains('focus-on'); out.lit = lit(); out.order = svg.kids.map(e => e.id);
modal.classList.add('open'); page.apply();
out.window_on = graph.classList.contains('focus-on'); out.window_lit = lit();
modal.classList.remove('open');
page.move(inA); tick(130); out.moved = [graph.classList.contains('focus-on'), lit()];
page.move(tB); tick(130); out.moved_b = lit();
page.move(root); tick(130); out.left = graph.classList.contains('focus-on');
// The table: a focus there before, then a backend hovered above the rows — nothing steps back, nothing lit.
page.set({ tile: 'A' }); page.apply(); VIEW = 'table'; page.apply();
out.table_cleared = [graph.classList.contains('focus-on'), lit()];
const nb = [root, ...root.all()].find(e => e.id === 'nb-law');
page.move(nb); tick(130); out.table_backend = [graph.classList.contains('focus-on'), lit()];
VIEW = 'tiles';
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def page() -> dict:
    fns = js_engine.take(JS, "_focusEnv", "_isPhone", "_focusOf", "_focusMove", "_applyFocus")
    return json.loads(js_engine.run(FOCUS + _PAGE_DOM.replace("PAGE_FNS", fns)))


def test_a_focus_lights_its_tile_its_lines_and_their_nodes_and_brings_its_lines_to_the_front(page):
    assert page["on"] is True
    assert page["lit"] == ["asset-A", "module-protect", "nb-law", "p1", "p3"]
    assert page["order"] == ["p0", "p2", "p1", "p3"]                    # its lines last: in front


def test_no_focus_is_drawn_while_a_window_is_open(page):
    assert page["window_on"] is False and page["window_lit"] == []


def test_the_pointer_moves_the_focus_from_tile_to_tile_and_out_of_the_map(page):
    assert page["moved"] == [True, ["asset-A", "module-protect", "nb-law", "p1", "p3"]]
    assert page["moved_b"] == ["asset-B", "module-protect", "p2"]
    assert page["left"] is False


def test_in_the_table_hovering_a_backend_dims_nothing(page):
    assert page["table_cleared"] == [False, []]                          # its passage takes the focus off
    assert page["table_backend"] == [False, []]                          # a backend above the rows: nothing dims


def test_the_focus_is_applied_as_the_map_is_rebuilt_and_the_keyboard_s_tile_kept():
    render = _fn("renderInfra")
    assert "      ${_legend()}`;\n  _applyFocus();                                    // FOC1: the new tiles lit at once" in render
    assert "const _tileFocus = /^asset-/.test(document.activeElement?.id || '') ? document.activeElement.id : '';" in render
    assert "if (_tileFocus) document.getElementById(_tileFocus)?.focus({ preventScroll: true });" in render


def test_the_console_stands_without_its_focus_script_and_says_one_phone():
    assert "const _focusSched = typeof InfraFocus === 'undefined' ? { want() {}, now() {}, current: () => null }" in JS
    assert "if (!graph || !svg || typeof InfraFocus === 'undefined') return;" in _fn("_applyFocus")
    assert len(re.findall(r"^function _isPhone\(", JS, re.M)) == 1
