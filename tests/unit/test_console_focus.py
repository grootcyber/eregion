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
out.allowed = [{}, { dragging: true }, { modal: true }, { phone: true }].map(e => F.allowed(e));
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
    assert ran["allowed"] == [True, False, False, False]


def test_the_focus_waits_about_120_ms_and_never_flickers(ran):
    assert ran["delay"] == 120
    assert ran["before_delay"] == [] and ran["after_delay"] == ["A"]
    assert ran["a_to_b"] == ["A", "B"]                 # from A to B: never « nothing » in between
    assert ran["same"] == ["A", "B"]


def test_a_drag_or_a_window_takes_the_focus_off_at_once(ran):
    assert ran["now"] == ["A", "B", None] and ran["current"] is None


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


def test_a_tile_steps_back_by_its_filter_never_its_opacity_and_no_fade_for_less_motion():
    assert '.topo-graph.focus-on [id^="asset-"]:not(.lit), .topo-graph.focus-on .node-backend:not(.lit) { filter: opacity(.3); }' in HTML
    media = HTML.index("@media (prefers-reduced-motion: reduce)")
    line = HTML.index('#topo-svg path, .topo-graph [id^="asset-"], .topo-graph .node-backend { transition: none; }')
    assert media < line < media + 600                    # inside the block of less motion


def test_the_logic_is_pure():
    body = FOCUS.split("const InfraFocus", 1)[1]
    for word in ("document.", "window.", "setTimeout", "fetch(", "localStorage", "innerHTML"):
        assert word not in body, word
