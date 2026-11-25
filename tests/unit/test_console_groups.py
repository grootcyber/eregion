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
out.same_name = lanes('subscription', WATCH, { 'abcdef01…cdef': { name: 'Prod', error: null }, 'aaaabbbb…6666': { name: 'prod', error: null } });
out.same_name_rg = lanes('rg', WATCH, { 'abcdef01…cdef': { name: 'Prod', error: null }, 'aaaabbbb…6666': { name: 'Prod', error: null } });
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


def test_two_subscriptions_of_one_name_never_two_lanes_said_alike(ran):
    """The relecture of GRP1: SUBN1 serves the names Azure gives — two subscriptions may bear one."""
    assert [lane["label"] for lane in ran["same_name"]][1:3] == ["Prod (abcdef01…cdef) · Glorfindel acts here",
                                                                "prod (aaaabbbb…6666) · seen, out of reach"]
    assert "Prod (aaaabbbb…6666) / rg-dev · out of reach" in [lane["label"] for lane in ran["same_name_rg"]]
    # One name, one subscription: no id beside it.
    assert ran["by_sub"][1]["label"] == "Production · Glorfindel acts here"


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
    # Jonathan, 25/11: its chip says what is left — detect only —, and a card held on it never « pending approval ».
    assert '>OUT OF REACH · DETECT ONLY</span>' in _fn("_oorChip")
    held = _fn("_heldWord")     # judged by the tile it is shown on (OOR1, tests/unit/test_console_oor.py)
    assert "  if (oor) return 'out of reach: detect only';" in held
    assert held.index("out of reach: detect only") < held.index("'pending approval'")
    # The writes taken off, never only disabled: on its tile, in its windows.
    assert "if (_OOR_DROPS.includes(b.getAttribute('data-on-click') || '')) b.remove();" in _fn("_dropWrites")
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


# ── The page's glue, run (the relecture of GRP1: a text test let `_watchSub` return '' unseen) ────────────
# The page's own functions taken as they are, infra_groups.js beside them, a /api/config of the test's and a
# root of fake buttons (no DOM in Node): what the page reads of the watch's subscription, what it takes off.

_GLUE = ("_attr", "_on", "_watchSub", "_isOor", "_WRITE_HANDLERS", "_OOR_DROPS", "_dropWrites", "_SUB_UNKNOWN",
         "_GROUP_SAID", "_groupBar")
_GLUE_HARNESS = r"""
let _cfgData = null, _cfgFailed = false, _groupBy = 'none';
const dev = { vm_name: 'dev-1', resource_id: DEV + '/resourceGroups/rg-dev/providers/Microsoft.Compute/virtualMachines/dev-1' };
const prod = { vm_name: 'web-1', resource_id: PROD + '/resourceGroups/rg-web/providers/Microsoft.Compute/virtualMachines/web-1' };
const out = {};
const read = cfg => { _cfgData = cfg; return { sub: _watchSub(), dev: _isOor(dev), prod: _isOor(prod), bar: _groupBar() }; };
out.configured = read({ azure: { subscription_id: WATCH, tenant_id: 'ffffffff…eeee' } });
out.no_subscription = read({ azure: { subscription_id: '', tenant_id: 'ffffffff…eeee' } });
_cfgFailed = true; out.no_config = read(null); _cfgFailed = false;   // OOR1: /api/config not readable
// A root of fake buttons: each its action, removed or kept.
const made = ['doApproveAction', 'doSnapshot', 'confirmRelease', 'openActivation', 'approveActionAndClose',
              'doAckAll', 'judgeCard', 'openCommandModal', 'showEscModal', ''];
const kept = [];
const buttons = made.map(a => ({ getAttribute: k => (k === 'data-on-click' ? a : null), remove() { this.gone = true; }, a }));
_dropWrites({ querySelectorAll: sel => (sel === 'button' ? buttons : []) });
out.kept = buttons.filter(b => !b.gone).map(b => b.a);
out.read_only_list = _WRITE_HANDLERS.includes('openActivation');
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def glue() -> dict:
    script = (GROUPS + js_engine.take(JS, *_GLUE) + f"const WATCH = {json.dumps(WATCH)};\nconst DEV = {json.dumps(DEV)};\n"
              + f"const PROD = {json.dumps(PROD)};\n" + _GLUE_HARNESS)
    return json.loads(js_engine.run(script))


def test_the_page_reads_the_watch_s_subscription_where_config_puts_it(glue):
    c = glue["configured"]
    assert c["sub"] == WATCH and c["dev"] is True and c["prod"] is False, c
    assert "subscription unknown" not in c["bar"]


def test_the_watch_s_subscription_unknown_keeps_every_action_and_the_bar_says_it(glue):
    """Driver's decision on the relecture: a VM of the watch never loses its actions on a datum missing."""
    for case in ("no_subscription", "no_config"):
        r = glue[case]
        assert r["sub"] == "" and r["dev"] is False and r["prod"] is False, (case, r)
        assert "the watch&#39;s subscription unknown: nothing said out of reach" in r["bar"], (case, r["bar"])


def test_out_of_reach_takes_off_the_writes_and_the_activation_never_the_verdicts(glue):
    assert glue["kept"] == ["doAckAll", "judgeCard", "openCommandModal", "showEscModal", ""], glue["kept"]
    # « Review & turn on » off a tile out of reach, never off a VM in read-only (that list is the guard's).
    assert glue["read_only_list"] is False


def test_no_fixed_line_from_recover_onto_a_tile_out_of_reach():
    """A vault reads its items by name: a VM of another subscription bearing the name of one in it."""
    assert "    if (reach && _vmProtected(vmName) === true) recoverBackends.forEach(b => {" in _fn("_drawTopologyEdges")
