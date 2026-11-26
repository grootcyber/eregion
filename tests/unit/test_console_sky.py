"""SKY1 (#1236): the map at 360° (Jonathan, 26/11, on a mockup).

Glorfindel at the centre, one node, its ring in three arcs; the backends as satellites drawn from their arc — the
workspaces, the NSGs (from /api/nsgs), the vaults — sized by what they serve, the smallest beyond six into one « +N »;
the estate around in systems that follow « group by » (a sun per resource group or per subscription, one star per
resource without a grouping), Entra ID and the control plane lone bodies; a sector per subscription, the tenant's at
the top. A line lights only when something happens: flowing while a human must act, a pulse while a restore runs,
from the backend that acts — out of reach, DETECT's only. A line never crosses Glorfindel.

The logic (`infra_sky.js`) runs as it is, in Node or a headless Chromium (tests/unit/js_engine.py); what the page
gives it (`_skyModel`) is run on stubbed neighbours. The drawing (`infra_sky_draw.js`) is measured in Chromium
(docs/design/console.md, « La vue à 360° »).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")
GROUPS = (STATIC / "infra_groups.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")

def _T(key: str, **kw) -> dict:
    """A tile as the page gives it: a VM of Prod in reach, calm, its workspace, its NSG and its vault known."""
    return {"key": key, "name": key.split("/")[-1], "own": "", "sub": "s-prod", "tenant": False, "out": False,
            "law": "nb-law", "nsg": "nsg:web", "vault": "nb-rsv", "s": {"d": "watched", "p": "ready", "a": False, "r": "protected"}, **kw}
_TILES = [
    _T("entra:identities", own="identity", tenant=True, sub="", nsg="", vault="", s={"d": "watched", "p": None, "a": False, "r": None}),
    _T("plane:control", own="control_plane", nsg="", vault="", s={"d": "watched", "p": None, "a": False, "r": None}),
    _T("/s/prod/rg-web/web-1"), _T("/s/prod/rg-web/web-2"), _T("/s/prod/rg-web/web-3"),
    _T("/s/prod/rg-data/data-1", law="nb-law2", nsg="nsg:data"),
    _T("/s/dev/rg-dev/dev-1", sub="s-dev", out=True, nsg="", vault="", s={"d": "judge", "p": None, "a": False, "r": None}),
]
_HARNESS = r"""
const S = InfraSky, out = {};
const by = Object.fromEntries(TILES.map(t => [t.key, t]));
const lanes = [
  { key: 'tenant', label: 'tenant', tiles: [by['entra:identities']] },
  { key: 's-prod/rg-web', label: 'Prod / rg-web', own: true, tiles: [by['/s/prod/rg-web/web-1'], by['/s/prod/rg-web/web-2'], by['/s/prod/rg-web/web-3']] },
  { key: 's-prod/rg-data', label: 'Prod / rg-data', own: true, tiles: [by['/s/prod/rg-data/data-1']] },
  { key: 's-prod', label: 'Prod', own: true, tiles: [by['plane:control']] },
  { key: 's-dev/rg-dev', label: 'Dev / rg-dev', out: true, tiles: [by['/s/dev/rg-dev/dev-1']] },
];
const sys = S.bodies(TILES, lanes, 'rg');
out.systems = sys.map(b => [b.id.split(':')[0], b.planets.length, b.lone ? b.lone.split(/[/:]/).pop() : '', b.sector]);
out.stars = S.bodies(TILES, lanes, 'none').map(b => b.id.split(':')[0]);
const L = S.layout(sys);
out.sectors = L.sectors.map(s => s.key);
const deg = a => Math.round(((a * 180 / Math.PI) % 360 + 360) % 360);
out.tenant_at = deg(L.bodies.find(b => b.sector === 'tenant').ang);
// Given last, the tenant still at the top.
const late = S.layout(sys.slice(1).concat([sys[0]]));
out.late = [late.sectors.map(s => s.key), deg(late.bodies.find(b => b.sector === 'tenant').ang)];
out.radii = L.bodies.map(b => Math.round(Math.hypot(b.pos[0] - S.G.cx, b.pos[1] - S.G.cy)));
const lone = S.layout(S.bodies(TILES, lanes, 'none'));
out.lone_radius = Math.round(Math.hypot(lone.bodies[0].pos[0] - S.G.cx, lone.bodies[0].pos[1] - S.G.cy));
const web = L.bodies.find(b => b.id === 'sys:s-prod/rg-web');
const p0 = S.planetAt(web, 0, 0), p0b = S.planetAt(web, 0, 10), p1 = S.planetAt(web, 1, 0);
out.planet = [Math.round(Math.hypot(p0[0] - web.pos[0], p0[1] - web.pos[1])), Math.round(web.pr), p0b[0] !== p0[0], p1[0] !== p0[0]];
// The satellites: beyond six, the smallest in a « +N ».
const many = Array.from({ length: 8 }, (_, i) => ({ id: 'nsg:' + i, name: 'nsg-' + i }));
const sats = S.satellites(many, id => 10 - Number(id.split(':')[1]));
out.sats = sats.map(b => b.name);
const placed = S.placeSatellites({ d: [], p: sats, r: [] });
out.sat_of = [S.satOf('nsg:0', placed), S.satOf('nsg:7', placed).startsWith('more:'), S.satOf('nsg:x', placed)];
// The lines of a tile.
const ln = (t, all) => S.linesOf(t, all).map(l => `${l.from}>${l.c}${l.wait ? '~' : ''}${l.pulse ? '*' : ''}${l.faint ? '.' : ''}`);
const T = s => ({ ...by['/s/prod/rg-web/web-1'], s: { d: 'watched', p: 'ready', a: false, r: 'protected', ...s } });
out.lines = {
  calm: ln(T({}), false), calm_all: ln(T({}), true),
  judge: ln(T({ d: 'judge' }), false), card: ln(T({ d: 'card' }), false),
  isolated: ln(T({ p: 'isolated' }), false), both: ln(T({ p: 'both' }), false), approve: ln(T({ a: true }), false),
  restoring: ln(T({ r: 'restoring' }), false),
  out: ln({ ...by['/s/dev/rg-dev/dev-1'], s: { d: 'judge', p: 'isolated', a: true, r: 'restoring' } }, true),
  no_nsg: ln({ ...T({ p: 'isolated' }), nsg: '' }, false),
};
out.tones = [{ p: 'isolated' }, { p: 'blocked' }, { r: 'restoring' }, { d: 'judge' }, { a: true }, {}].map(s => S.TONE(s));
// A line never crosses Glorfindel: across the circle, it keeps away from the ring.
const far = S.route(S.polar(-Math.PI / 2, S.G.RB), S.polar(Math.PI / 2, S.G.RS), S.laneOf(3, true), 0);
out.far_min = Math.round(Math.min(...far.map(q => Math.hypot(q[0] - S.G.cx, q[1] - S.G.cy))));
const near = S.route(S.polar(0, S.G.RB), S.polar(0.2, S.G.RS), S.laneOf(3, true), 0);
out.near = near.length;
const into = S.intoSystem(S.polar(0, S.G.RB), web.pos, web.pr, p0, S.laneOf(1, true), 0);
const end = into[into.length - 1];
out.into_end = Math.round(Math.hypot(end[0] - p0[0], end[1] - p0[1]));
out.into_jump = Math.round(Math.max(...into.slice(1).map((q, i) => Math.hypot(q[0] - into[i][0], q[1] - into[i][1]))));
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    return json.loads(js_engine.run(SKY + f"const TILES = {json.dumps(_TILES)};\n" + _HARNESS))


def test_the_systems_follow_the_grouping_and_a_tile_of_its_own_is_a_lone_body(ran):
    assert ran["systems"] == [["lone", 0, "identities", "tenant"], ["sys", 3, "", "s-prod"], ["sys", 1, "", "s-prod"],
                              ["lone", 0, "control", "s-prod"], ["sys", 1, "", "s-dev"]]
    assert ran["stars"] == ["star"] * 7                       # without a grouping: one star per resource


def test_a_sector_per_subscription_the_tenant_s_at_the_top(ran):
    assert ran["sectors"] == ["tenant", "s-prod", "s-dev"]
    assert ran["tenant_at"] == 270                              # straight up
    assert ran["late"] == [["tenant", "s-prod", "s-dev"], 270]   # given last, still first and at the top
    assert set(ran["radii"]) == {336} and ran["lone_radius"] == 372


def test_a_planet_turns_on_its_orbit_each_at_its_place(ran):
    distance, orbit, turned, apart = ran["planet"]
    assert distance == orbit and turned and apart


def test_beyond_six_the_smallest_satellites_go_into_one(ran):
    assert ran["sats"] == ["nsg-0", "nsg-1", "nsg-2", "nsg-3", "nsg-4", "+3"]
    assert ran["sat_of"] == ["nsg:0", True, ""]


def test_a_line_lights_only_when_something_happens_from_the_backend_that_acts(ran):
    ln = ran["lines"]
    assert ln["calm"] == []
    assert ln["calm_all"] == ["nb-law>blue.", "nsg:web>orange.", "nb-rsv>green."]
    assert ln["judge"] == ["nb-law>purple~"] and ln["card"] == ["nb-law>purple~"]
    assert ln["isolated"] == ["nsg:web>red"] and ln["both"] == ["nsg:web>red", "nsg:web>orange"]
    assert ln["approve"] == ["nsg:web>purple~"]
    assert ln["restoring"] == ["nb-rsv>green*"]
    assert ln["out"] == ["nb-law>purple~"]                       # out of reach: DETECT's only
    assert ln["no_nsg"] == ["p:arc>red"]                         # its NSG unknown: from the PROTECT arc


def test_a_system_s_sun_takes_the_colour_of_the_worst_on_it(ran):
    assert ran["tones"] == ["red", "orange", "green", "wait", "wait", "quiet"]


def test_a_line_never_crosses_glorfindel_and_reaches_its_planet_without_a_jump(ran):
    assert ran["far_min"] >= 160                                 # the ring is 72; a satellite at 172
    assert ran["near"] == 25                                     # a near target: one curve
    assert ran["into_end"] == 0 and ran["into_jump"] < 40


def test_the_logic_is_pure_and_the_drawing_writes_no_markup():
    body = SKY.split("const InfraSky", 1)[1]
    for word in ("document.", "window.", "fetch(", "localStorage", "innerHTML", "setTimeout"):
        assert word not in body, word
    assert "innerHTML" not in DRAW and "insertAdjacentHTML" not in DRAW
    names = re.findall(r"case '([^']+)': e\.setAttribute\('\1', v\); break;", DRAW)
    assert names and not [n for n in names if re.match(r"(on|href|src|style$|xlink)", n)], names


# ── What the page gives the sky (glorfindel.js `_skyModel`, run on stubbed neighbours) ─────────────────────────
_RID = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-web/providers/Microsoft.Compute/virtualMachines/"
_PAGE = r"""
let _groupBy = 'rg', _tableSums = [];
const _watchSub = () => '00000000…0000';
const Console = { watchStatus: () => ({ subscriptions: { names: { '00000000…0000': { name: 'Prod' } } } }) };
const _state = { discovered_assets: [{ name: 'web-2', resource_id: RID + 'web-2', monitoring_backend: 'law-web' }] };
const _cfgData = { monitoring_backends: [{ name: 'law-prod', reachable: true }, { name: 'law-web', reachable: false }],
                   assets: [{ type: 'azure_backup_vault', name: 'rsv-prod' }] };
const _nsgItems = { nsgs: [{ nsg: 'nsg-web', vms: [RID.toUpperCase() + 'WEB-1', RID + 'web-2'] }, { nsg: 'nsg-empty', vms: [] }] };
const _backupItems = { vault: 'rsv-prod', items: [] };
const _isOor = r => false;
const _vmProtected = n => (n === 'web-1' ? true : n === 'web-2' ? null : false);
const _watchCards = () => [{}, {}];
const TILES = [
  { key: (RID + 'web-1').toLowerCase(), resource_id: RID + 'web-1', vm_name: 'web-1', states: [] },
  { key: (RID + 'web-2').toLowerCase(), resource_id: RID + 'web-2', vm_name: 'web-2', states: [] },
  { key: 'entra:identities', vm_name: 'entra:identities', kind: 'identity', label: 'Entra ID — identities' },
  { key: 'nsg-x', vm_name: 'nsg-x', is_nsg: true, resource_id: RID.replace('Compute/virtualMachines', 'Network/networkSecurityGroups') + 'nsg-x' },
];
const m = (function (window) { SKY_MODEL; return _skyModel(TILES); })({ matchMedia: () => ({ matches: true }) });
const pick = t => [t.name, t.own, t.law, t.nsg, t.vault, t.tenant];
emit(JSON.stringify({ tiles: m.tiles.map(pick), lanes: (m.lanes || []).map(l => [l.label, l.tiles.length]),
  sectors: m.sectors, backends: m.backends, watch: m.watch, reduced: m.reduced, mode: m.mode }));
"""


@pytest.fixture(scope="module")
def model() -> dict:
    taken = js_engine.take(JS, "_fullId", "_sameAsset", "_skyModel")
    script = GROUPS + SKY + f"const RID = {json.dumps(_RID)};\n" + _PAGE.replace("SKY_MODEL", taken)
    return json.loads(js_engine.run(script))


def test_the_page_gives_each_tile_its_log_source_its_nsg_and_its_vault(model):
    web1, web2, entra, nsg = model["tiles"]
    assert web1 == ["web-1", "", "nb-law-prod", "nsg:nsg-web", "nb-rsv-prod", False]     # the NSG by its id, any case
    assert web2 == ["web-2", "", "nb-law-web", "nsg:nsg-web", "", False]                 # its workspace: the discovery's
    assert entra == ["Entra ID — identities", "identity", "nb-law-prod", "", "", True]
    assert nsg[3] == "nsg:nsg-x" and nsg[4] == ""                                          # an NSG's tile: itself


def test_the_page_gives_the_lanes_the_sectors_and_the_backends(model):
    assert model["mode"] == "rg" and model["watch"] == 2 and model["reduced"] is True
    assert ["tenant", 1] in model["lanes"]
    assert any(v["label"].startswith("Prod") and v["own"] for v in model["sectors"].values())
    assert model["backends"]["d"] == [{"id": "nb-law-prod", "name": "law-prod", "err": False},
                                      {"id": "nb-law-web", "name": "law-web", "err": True}]
    assert model["backends"]["p"] == [{"id": "nsg:nsg-web", "name": "nsg-web"}]           # an NSG that governs nothing: none
    assert model["backends"]["r"] == [{"id": "nb-rsv-prod", "name": "rsv-prod"}]


def test_the_page_draws_the_sky_in_its_own_place_kept_across_renders():
    render = re.search(r"^function renderInfra\(\) \{.*?\n\}\n", JS, re.S | re.M).group(0)
    assert "if (view === 'sky') {" in render and "_renderSky(body, resourceMap" in render
    sky = re.search(r"^function _renderSky\(.*?\n\}\n", JS, re.S | re.M).group(0)
    assert "if (!body.querySelector('#sky-wrap'))" in sky                    # the SVG kept: its motion never restarts
    assert "InfraSkyDraw.mount(document.getElementById('sky-slot'), _skyModelLast, _skyPanel);" in sky
    assert "return head('the tile') + _unfolded(r, " in JS                    # the panel: the tile itself, unfolded
    assert HTML.index('<script src="/static/infra_sky.js"></script>') < HTML.index('<script src="/static/glorfindel.js"></script>')
    assert HTML.index('<script src="/static/infra_sky_draw.js"></script>') < HTML.index('<script src="/static/glorfindel.js"></script>')
