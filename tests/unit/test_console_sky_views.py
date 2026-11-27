"""SKY8 (#1288): the three views of the 360° drawn alike (Jonathan, 27/11, on Imladris).

« none » drew the arc around its sectors a little wider than the grouped views (the orbit's RA + 56, 428, against the
satellites' ring + 88, 424): the circle a size larger when one changed « group by ». And in « none », Entra ID and the
control plane — tiles of their own — were stars like any VM, while a grouped view draws them as lone bodies, 1.8 times
as large, with their glow. One arc now in the three views, the sectors' names following it; a tile of its own the size
it is in a grouped view, in every view.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py), the sky drawn on the fake DOM of
tests/unit/test_console_sky_lines.py.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from tests.unit import js_engine
from tests.unit import test_console_sky_lines as _lines

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")

_VIEWS = _lines._MOUNT.split("(function (document, getComputedStyle, requestAnimationFrame) {", 1)[0] + r"""
(function (document, getComputedStyle, requestAnimationFrame) {
  SKY_SRC
  const fresh = () => { DRAW_SRC
    return InfraSkyDraw; };
  const base = { tenant: false, out: false, law: 'nb-law', nsg: 'nsg:web', vault: 'nb-rsv', s: { d: 'watched', p: 'ready', a: false, r: 'protected', w: [] } };
  const tiles = [{ ...base, key: 'identities', name: 'Entra ID — identities', own: 'identities', sub: '', tenant: true },
                 { ...base, key: 'vm-web-1', name: 'vm-web-1', own: '', sub: 's' }, { ...base, key: 'vm-web-2', name: 'vm-web-2', own: '', sub: 's' }];
  const lanes = { rg: [{ key: 'tenant', label: 'tenant', own: true, tiles: [tiles[0]] }, { key: 's/rg', label: 'rg', own: true, tiles: tiles.slice(1) }],
                  subscription: [{ key: 'tenant', label: 'tenant', own: true, tiles: [tiles[0]] }, { key: 's', label: 's', own: true, tiles: tiles.slice(1) }] };
  const out = {};
  for (const mode of ['none', 'subscription', 'rg']) {
    const D = fresh(), slot = new El('div'); root.appendChild(slot);
    D.mount(slot, { mode, tiles, lanes: mode === 'none' ? null : lanes[mode], sectors: { tenant: { label: 'tenant' }, s: { label: 's' } }, watch: 0,
      reduced: true, backends: { d: [{ id: 'nb-law', name: 'law' }], p: [{ id: 'nsg:web', name: 'nsg-web' }], r: [{ id: 'nb-rsv', name: 'rsv' }] },
      heartOf: () => null });
    const svg = slot.children[0], all = svg.all();
    const arcs = all.filter(e => e.tagName === 'path' && e.attrs['stroke-width'] === 1.2 || e.tagName === 'path' && e.attrs['stroke-width'] === '1.2').map(e => e.attrs.d);
    const own = all.find(e => e.dataset.a === 'identities'), glow = own && own.children.find(c => c.dataset.glow);
    // The sectors' names: a letter a text, rotated about where it stands.
    const names = all.filter(e => e.tagName === 'text' && /^rotate\(/.test(e.attrs.transform || '')).map(e => [Number(e.attrs.x), Number(e.attrs.y)]);
    out[mode] = { arcs, own: own ? own.style.transform : null, glow: glow ? glow.getAttribute('opacity') : null, names };
    slot.remove();
  }
  emit(JSON.stringify({ out, G: InfraSky.G }));
})({ createElementNS: (ns, tag) => new El(tag), documentElement: root }, () => ({ getPropertyValue: n => n.slice(2) }), () => 1);
"""


def _views() -> dict:
    return json.loads(js_engine.run(_VIEWS.replace("SKY_SRC", SKY).replace("DRAW_SRC", DRAW)))


def test_one_arc_in_the_three_views_the_sectors_names_on_it():
    got = _views()
    G, out = got["G"], got["out"]
    radii = {}
    for mode, v in out.items():
        assert v["arcs"], mode
        radii[mode] = {float(m) for d in v["arcs"] for m in re.findall(r"A([\d.]+),", d)}
        dist = {round(math.hypot(x - G["cx"], y - G["cy"])) for x, y in v["names"]} - {113, 123}   # not DETECT, PROTECT, RECOVER
        dist = {d for d in dist if d > G["RS"]}                                                 # the sectors' names, past the orbit
        assert dist and dist <= {G["RS"] + 88 + 9, G["RS"] + 88 + 20}, (mode, dist)   # their names follow the arc
    assert radii["none"] == radii["subscription"] == radii["rg"] == {G["RS"] + 88}   # one arc, never « none » wider


def test_a_tile_of_its_own_is_the_size_it_is_in_a_grouped_view_in_every_view():
    out = _views()["out"]
    for mode in ("none", "subscription", "rg"):
        assert out[mode]["own"] and out[mode]["own"].endswith("scale(1.800)"), (mode, out[mode]["own"])   # Entra ID, 1.8×
        assert out[mode]["glow"] == "0.14", mode                                                        # and its glow
