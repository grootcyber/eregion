"""GRP1 (#1189): the infrastructure map grouped by subscription or by resource group, and what is out of reach
(Jonathan, 25/11, on a mockup, option B).

Several workspaces see VMs of several subscriptions, and the map mixed them without saying so — while a
watch acts only in its own. Now a selector « group by » (none, subscription, resource group), kept in the
browser; grouped, a lane each; a tile of another subscription than the watch's out of reach: dashed, its
chip, no line from PROTECT, no button that writes in Azure — its cards still judged.

The logic (`infra_groups.js`: a tile's place, out of reach, the lanes, the choice kept) is run as it is, in
Node or a headless Chromium (tests/unit/js_engine.py); how the page draws it is read in its text. Measured
in a headless Chromium at 1600 × 1000 and 390 × 844 (the PR says how).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
GROUPS = (STATIC / "infra_groups.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")

WATCH = "abcdef01…cdef"                      # /api/config's, masked (SEC1)
PROD = "/subscriptions/abcdef01-0000-0000-0000-00000000cdef"
DEV = "/subscriptions/AAAABBBB-1111-2222-3333-444455556666"   # its case is Azure's, any


def _vm(name: str, sub: str, rg: str) -> dict:
    return {"vm_name": name, "resource_id": f"{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"}


_TILES = [_vm("dev-1", DEV, "rg-dev"), {"vm_name": "entra:identities", "kind": "identity", "resource_id": "entra:identities"},
          _vm("web-1", PROD, "rg-web"), {"vm_name": "plane:control", "kind": "control_plane", "resource_id": "control-plane"},
          _vm("db-1", PROD, "rg-data"), _vm("web-2", PROD, "RG-WEB"), {"vm_name": "lone", "resource_id": "discovered:lone"},
          _vm("same", PROD.upper(), "rg-web")]
_NAMES = {"abcdef01…cdef": {"name": "Production", "error": None}, "aaaabbbb…6666": {"name": "Dev <b>", "error": None}}
_HARNESS = r"""
const out = {};
const lanes = (mode, watch, names) => InfraGroups.lanes(TILES, mode, watch, names).map(l =>
  ({ label: l.label, title: l.title, own: !!l.own, out: !!l.out, tiles: l.tiles.map(t => t.vm_name) }));
out.oor = Object.fromEntries(TILES.map(t => [t.vm_name, InfraGroups.outOfReach(t, WATCH)]));
out.oor_unknown_watch = TILES.some(t => InfraGroups.outOfReach(t, ''));
out.by_sub = lanes('subscription', WATCH, NAMES);
out.by_rg = lanes('rg', WATCH, NAMES);
out.no_names = lanes('subscription', WATCH, null);
out.name_error = lanes('subscription', WATCH, { 'aaaabbbb…6666': { name: null, error: 'HTTP 403' }, 'abcdef01…cdef': 'x' });
out.unknown_watch = lanes('subscription', '', NAMES);
// The choice kept: a storage of the test's, one that throws, one that forgets, a value not of the list.
const box = {}; const mem = { getItem: k => (k in box ? box[k] : null), setItem: (k, v) => { box[k] = String(v); } };
out.saved = InfraGroups.save(() => mem, 'rg'); out.loaded = InfraGroups.load(() => mem); out.key = Object.keys(box);
out.bogus = InfraGroups.load(() => ({ getItem: () => 'everything' }));
out.throws_load = InfraGroups.load(() => { throw new Error('denied'); });
out.throws_save = InfraGroups.save(() => ({ setItem: () => { throw new Error('quota'); } }), 'rg');
out.empty = InfraGroups.load(() => ({ getItem: () => null }));
out.modes = InfraGroups.MODES;
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    script = (GROUPS + f"const TILES = {json.dumps(_TILES)};\nconst WATCH = {json.dumps(WATCH)};\n"
              + f"const NAMES = {json.dumps(_NAMES)};\n" + _HARNESS)
    return json.loads(js_engine.run(script))


# ── What infra_groups.js decides, run ──────────────────────────────────────────────────────────────────

def test_out_of_reach_is_another_subscription_than_the_watch_s(ran):
    oor = ran["oor"]
    assert oor["dev-1"] is True
    # The watch's own, whatever the case of its id; the tenant; the control plane's own tile; no id: never.
    for name in ("web-1", "web-2", "db-1", "same", "entra:identities", "plane:control", "lone"):
        assert oor[name] is False, name
    # Compared without its case: the key SUBN1 names a lane by is the masked id in lower case.
    assert ran["by_sub"][2]["label"] == "Dev <b> · seen, out of reach"
    # The watch's subscription unknown (/api/config without it): nothing is said out of reach.
    assert ran["oor_unknown_watch"] is False


def test_by_subscription_the_tenant_the_watch_s_the_others_the_unknown(ran):
    lanes = ran["by_sub"]
    assert [lane["label"] for lane in lanes] == ["tenant", "Production · Glorfindel acts here",
                                                 "Dev <b> · seen, out of reach", "subscription unknown"]
    assert [lane["tiles"] for lane in lanes] == [["entra:identities"], ["web-1", "plane:control", "db-1", "web-2", "same"],
                                                 ["dev-1"], ["lone"]]
    assert [(lane["own"], lane["out"]) for lane in lanes] == [(False, False), (True, False), (False, True), (False, False)]
    assert lanes[2]["title"] == ("subscription aaaabbbb…6666 (Dev <b>) — not the watch's: it acts only in its own")


def test_by_resource_group_a_lane_per_group_the_control_plane_with_its_subscription(ran):
    lanes = ran["by_rg"]
    assert [lane["label"] for lane in lanes] == ["tenant", "Production", "Production / rg-data", "Production / rg-web",
                                                 "Dev <b> / rg-dev · out of reach", "subscription unknown"]
    # A group's name is read without its case (Azure's): one lane for rg-web and RG-WEB, named by the first seen.
    assert lanes[3]["tiles"] == ["web-1", "web-2", "same"]
    assert lanes[1]["tiles"] == ["plane:control"]


def test_a_lane_named_by_subn1_else_by_its_masked_id(ran):
    assert [lane["label"] for lane in ran["no_names"]][1:3] == ["abcdef01…cdef · Glorfindel acts here",
                                                               "aaaabbbb…6666 · seen, out of reach"]
    lanes = ran["name_error"]
    assert lanes[1]["label"] == "abcdef01…cdef · Glorfindel acts here"   # an entry not of the form: no name
    assert lanes[2]["label"] == "aaaabbbb…6666 · seen, out of reach"
    assert "its name not read: HTTP 403" in lanes[2]["title"]
    # The watch's subscription unknown: no lane says where Glorfindel acts, none out of reach.
    assert not any(lane["own"] or lane["out"] for lane in ran["unknown_watch"])
    assert [lane["label"] for lane in ran["unknown_watch"]][1:3] == ["Dev <b>", "Production"]


def test_the_choice_kept_in_the_browser_and_a_storage_that_fails_said_by_nothing(ran):
    assert ran["modes"] == ["none", "subscription", "rg"]
    assert ran["saved"] is True and ran["loaded"] == "rg" and ran["key"] == ["glorfindel_group_by"]
    assert ran["bogus"] == "none" and ran["empty"] == "none" and ran["throws_load"] == "none"
    assert ran["throws_save"] is False


def test_the_logic_is_pure():
    """No page, no request, no global but its own: what the page draws is decided where the suite runs it."""
    for word in ("document.", "window.", "fetch(", "localStorage", "innerHTML", "_cfgData", "Console."):
        assert word not in GROUPS.split("const InfraGroups")[1], word
    assert GROUPS.count("const InfraGroups = (() => {") == 1


# ── How the page draws it, read ────────────────────────────────────────────────────────────────────────

def _fn(name: str) -> str:
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def test_the_page_loads_the_logic_before_it_and_the_selector_acts():
    assert ('<script src="/static/console.js"></script>\n<script src="/static/infra_groups.js"></script>\n'
            '<script src="/static/glorfindel.js"></script>') in HTML
    assert "let _groupBy = InfraGroups.load(() => localStorage);" in JS
    sel = _fn("setGroupBy")
    assert "if (!InfraGroups.MODES.includes(g)) return;" in sel and "InfraGroups.save(() => localStorage, g);" in sel
    assert "  setGroupBy,                                     // the tiles grouped" in JS
    bar = _fn("_groupBar")
    assert "aria-pressed=\"${g === _groupBy ? 'true' : 'false'}\" ${_on('click', 'setGroupBy', g)}" in bar


def test_grouped_the_tiles_go_in_lanes_their_names_escaped():
    render = _fn("renderInfra")
    assert "      ${_groupBar()}\n      <!-- Layer 1 — Agent -->" in render
    assert "          if (_groupBy !== 'none') return _lanesHtml(slots, tileOf, ctx);" in render
    lanes = _fn("_lanesHtml")
    assert "InfraGroups.lanes([...slotOf.keys()].map(tileOf), _groupBy, _watchSub(), names)" in lanes
    assert 'title="${_attr(l.title)}">${_attr(l.label)}</div>' in lanes
    assert "const names = Console.watchStatus()?.subscriptions?.names;" in lanes
    # The focus a keyboard gave the selector, kept across the redraw.
    assert "const _grpFocus = document.activeElement?.dataset?.grp;" in render


def test_a_tile_out_of_reach_says_it_and_offers_nothing_to_write():
    for fn in ("_renderAssetNode", "_renderNsgNode", "_renderClusterNode"):
        body = _fn(fn)
        assert "_isOor(" in body and "${oor ? ' oor' : ''}" in body and "${oor ? ' data-oor=\"1\"' : ''}" in body, fn
    vm = _fn("_renderAssetNode")
    assert "const modeBadge = oor ? _oorChip(oor) : holdChip + (modeHold" in vm
    assert "const modeSelector = isExpanded && !oor" in vm
    assert "${_oorChip(oor)}" in _fn("_renderNsgNode") and "${_oorChip(oor)}" in _fn("_renderClusterNode")
    # The writes taken off, never only disabled: on its tile, in its windows.
    assert "if (_WRITE_HANDLERS.includes(b.getAttribute('data-on-click') || '')) b.remove();" in _fn("_dropWrites")
    assert "  list.querySelectorAll('.node-asset.oor').forEach(_dropWrites);" in _fn("renderInfra")
    assert "  if (_isOor(tile)) _dropWrites(bodyEl);" in _fn("showEscModal")
    assert "  if (_isOor(r || { resource_id: want })) _dropWrites(body);" in _fn("showBlocks")
    assert _fn("renderInfra").index("forEach(_dropWrites)") < _fn("renderInfra").index("_watchTopology(graph);")


def test_no_line_from_protect_onto_a_tile_out_of_reach():
    edges = _fn("_drawTopologyEdges")
    assert "const reach   = !el.dataset.oor;" in edges
    assert "if (nbNsg && reach) lines.push(" in edges and "    if (nbNsg && reach) {" in edges
    assert "if (edge.from !== 'detect' && tileEl.dataset.oor) return;" in edges


def test_the_legend_and_the_phone_say_it():
    assert "${box('var(--dim)', 'lg-dash', 'excluded · out of reach')}" in _fn("_legend")
    phone = HTML.split("@media (max-width: 759px) {", 1)[1]
    assert ".grp-bar button { flex: 1 1 0; min-height: 44px; font-size: 12px; }" in phone
    assert ".grp-lane { border: 0; padding: 0; flex: 1 1 100%; }" in phone
    assert "  .node-asset.oor { border-style: dashed; }" in HTML and "  .grp-lane.out { border-style: dashed; }" in HTML
