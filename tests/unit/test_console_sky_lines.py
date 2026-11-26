"""LEG2 (#1244), its relecture: the 360°'s lines as they are drawn — a line waiting never lost under a line done.

The rule (linesOf) gave a VM isolated, whose check failed, two lines from its NSG: the red of the isolation and the red
dotted flow of its check — a common case (glorfindel's reassertion files `verification_failed`). Drawn, the second
took the first's key (its stroke was not in it) and its very path (a lane's step is by colour): one solid line, the
waiting lost. Its stroke is in its key now, and a line waiting runs a step beside the line done of its colour.

And a system's sun: at the same rank, a card waiting colours its ring before a verdict — never the order of its tiles.

The draw runs as it is (infra_sky.js, infra_sky_draw.js) on a DOM of the test's, in Node or a headless Chromium
(tests/unit/js_engine.py), inside a function's scope.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")

_MOUNT = r"""
function El(tag) { this.tagName = tag; this.attrs = {}; this.children = []; this.parentNode = null; this.style = {}; this.dataset = {}; this.textContent = ''; }
El.prototype.setAttribute = function (k, v) { v = String(v); if (k.startsWith('data-')) this.dataset[k.slice(5)] = v; else this.attrs[k] = v; };
El.prototype.getAttribute = function (k) { const v = k.startsWith('data-') ? this.dataset[k.slice(5)] : this.attrs[k]; return v === undefined ? null : v; };
El.prototype.appendChild = function (c) { if (c.parentNode) c.remove(); c.parentNode = this; this.children.push(c); return c; };
El.prototype.remove = function () { const p = this.parentNode; if (p) { p.children = p.children.filter(x => x !== this); this.parentNode = null; } };
El.prototype.replaceChildren = function () { this.children.forEach(c => { c.parentNode = null; }); this.children = []; };
El.prototype.addEventListener = function () {};
El.prototype.getBoundingClientRect = function () { return { left: 0, top: 0, width: 0, height: 0 }; };
El.prototype.all = function () { return this.children.flatMap(c => [c, ...c.all()]); };
El.prototype.contains = function (x) { for (let e = x; e; e = e.parentNode) if (e === this) return true; return false; };
El.prototype.querySelectorAll = function (sel) { const m = /^\[([\w-]+)\]$/.exec(sel); return this.all().filter(e => e.getAttribute(m[1]) !== null); };
El.prototype.querySelector = function (sel) { return this.querySelectorAll(sel)[0] || null; };
El.prototype.closest = function (sel) { const m = /^\[([\w-]+)\]$/.exec(sel); for (let e = this; e; e = e.parentNode) if (e.getAttribute(m[1]) !== null) return e; return null; };
Object.defineProperty(El.prototype, 'isConnected', { get() { let e = this; while (e.parentNode) e = e.parentNode; return e === root; } });
const root = new El('div');
(function (document, getComputedStyle, requestAnimationFrame) {
  SKY_SRC
  const fresh = () => { DRAW_SRC
    return InfraSkyDraw; };
  const T = (key, s) => ({ key, name: key, own: '', sub: 's', tenant: false, out: false, law: 'nb-law', nsg: 'nsg:web', vault: 'nb-rsv', s });
  const draw = (tiles, mode) => {
    const D = fresh(), slot = new El('div'); root.appendChild(slot);
    D.mount(slot, { mode, tiles, lanes: mode === 'none' ? null : [{ key: 's/rg', label: 'rg', own: true, tiles }], sectors: {}, watch: 0,
      reduced: true, backends: { d: [{ id: 'nb-law', name: 'law' }], p: [{ id: 'nsg:web', name: 'nsg-web' }], r: [{ id: 'nb-rsv', name: 'rsv' }] },
      heartOf: () => null });
    const svg = slot.children[0];
    const paths = svg.all().filter(e => e.tagName === 'path' && e.dataset.gen).map(e => ({ d: e.attrs.d, stroke: e.attrs.stroke, cls: e.attrs.class || '' }));
    const ring = (svg.all().find(e => e.dataset.s) || { children: [] }).children.find(c => c.attrs['stroke-width'] === '2.4');
    slot.remove();
    return { paths, ring: ring ? ring.attrs.stroke : '' };
  };
  const out = {};
  // An isolation whose check failed; a block with another to approve: two lines each, one of them flowing.
  out.isolated = draw([T('web-1', { d: 'watched', p: 'isolated', a: true, r: 'protected', w: ['isolate'] })], 'none').paths;
  out.blocked = draw([T('web-1', { d: 'watched', p: 'blocked', a: true, r: 'protected', w: ['block'] })], 'none').paths;
  // A sun: a verdict and a card waiting, at the same rank — in either order, the card's colour.
  const v = T('web-1', { d: 'judge', p: 'ready', a: false, r: 'protected', w: ['detect'] });
  const c = T('web-2', { d: 'card', p: 'ready', a: false, r: 'protected', w: ['other'] });
  out.ring = [draw([v, c], 'rg').ring, draw([c, v], 'rg').ring, draw([v], 'rg').ring];
  emit(JSON.stringify(out));
})({ createElementNS: (ns, tag) => new El(tag), documentElement: root }, () => ({ getPropertyValue: n => n.slice(2) }), () => 1);
"""


def _drawn() -> dict:
    return json.loads(js_engine.run(_MOUNT.replace("SKY_SRC", SKY).replace("DRAW_SRC", DRAW)))


def test_a_line_waiting_is_drawn_beside_the_line_done_of_its_colour_never_under_it():
    d = _drawn()
    for case, colour in (("isolated", "red"), ("blocked", "orange")):
        mine = [p for p in d[case] if p["stroke"] == colour]
        assert len(mine) == 2, (case, mine)                                   # two paths: the line done, the line waiting
        assert sorted(p["cls"] for p in mine) == ["", "sky-flow"], (case, mine)
        assert mine[0]["d"] != mine[1]["d"], case                             # a step apart: never one under the other


def test_a_sun_s_ring_takes_a_card_waiting_before_a_verdict_whatever_the_order():
    ring = _drawn()["ring"]
    assert ring[0] == ring[1] == "purple"                                     # a card waits: purple, in either order
    assert ring[2] == "blue"                                                  # only a verdict: blue
