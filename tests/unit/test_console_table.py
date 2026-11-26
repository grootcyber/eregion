"""TBL1 (#1230): the infrastructure map as a table (Jonathan, 26/11, on a mockup).

A row per tile, its three modules as pills. The maintainer's condition: rows open each on its own, several at
once — an open row shows the tile in full. What asks for the eye (a detection to judge, a block, an isolation,
an action to approve, a restore) opens by itself; a row the operator folds stays folded until its next
incident. The totals filter. « tiles · table » is kept in this browser; on a phone the table by default
(Jonathan, 26/11: whatever the estate's size).

The logic (`infra_table.js`) runs as it is, in Node or a headless Chromium (tests/unit/js_engine.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
TABLE = (STATIC / "infra_table.js").read_text(encoding="utf-8")

_SUMMARIES = [
    {"key": "entra:identities", "d": "watched", "p": None, "a": False, "r": None},
    {"key": "plane:control", "d": "judge", "p": None, "a": False, "r": None},
    {"key": "/subscriptions/a/vm/bree", "d": "watched", "p": "blocked", "a": False, "r": "protected"},
    {"key": "/subscriptions/a/vm/gondolin", "d": "watched", "p": "isolated", "a": False, "r": "protected"},
    {"key": "/subscriptions/a/vm/twin", "d": "watched", "p": "ready", "a": True, "r": "restoring"},
    {"key": "/subscriptions/a/vm/calm", "d": "watched", "p": "ready", "a": False, "r": "protected"},
    {"key": "/subscriptions/b/vm/dev", "d": "watched", "p": None, "a": False, "r": None},
]
# Beside the map: a VM isolated and blocked, a card that is not a decision, an NSG — their pills and totals.
_MORE = [
    {"key": "/subscriptions/a/vm/both", "d": "watched", "p": "both", "a": False, "r": "protected"},
    {"key": "/subscriptions/a/vm/gap", "d": "card", "p": "ready", "a": False, "r": None},
    {"key": "/subscriptions/a/nsg/nsg-web", "d": None, "p": "ready", "a": False, "r": None},
    {"key": "/subscriptions/a/vm/unread", "d": "watched", "p": "ready", "a": False, "r": "unread"},
    {"key": "/subscriptions/a/vm/release", "d": "judge", "p": "isolated", "a": True, "r": "protected"},
]
_HARNESS = r"""
const out = {}, T = InfraTable;
const openKeys = rows => SUMS.filter(s => T.isOpen(s, rows)).map(s => s.key.split(/[/:]/).pop());
// What asks for the eye opens by itself; a calm row stays folded.
let rows = T.rows();
out.start = openKeys(rows);
// Several open at once: the operator opens two calm rows, nothing closes.
T.toggle(SUMS[5], rows); T.toggle(SUMS[6], rows);
out.two_more = openKeys(rows);
// Folding a row that asks: it stays folded across refreshes while its incident lasts…
T.toggle(SUMS[3], rows); T.settle(SUMS, rows); T.settle(SUMS, rows);
out.folded_kept = openKeys(rows).includes('gondolin');
// …and its next incident opens it again: the incident passed, then a new one.
const calmNow = SUMS.map(s => s.key.endsWith('gondolin') ? { ...s, p: 'ready' } : s);
T.settle(calmNow, rows);
out.reopened = T.isOpen(SUMS[3], rows);
// All, then none.
T.foldAll(SUMS, rows); out.none = openKeys(rows);
T.openAll(SUMS, rows); out.all = openKeys(rows).length;
// A row no longer on the map forgets its state.
T.settle(SUMS.slice(0, 2), rows); out.forgotten = [...rows.opened].length;
// The totals and the filters.
out.totals = T.totals(SUMS);
out.filtered = T.filtered(SUMS, 'isolated').map(s => s.key.split('/').pop());
out.bogus_filter = T.filtered(SUMS, 'toString').length;
// The view kept in the browser; the phone's default.
const box = {}; const mem = { getItem: k => (k in box ? box[k] : null), setItem: (k, v) => { box[k] = String(v); } };
out.phone = T.view(() => mem, true);
out.desk = T.view(() => mem, false);
out.saved = T.save(() => mem, 'tiles'); out.phone_after_save = T.view(() => mem, true); out.key = Object.keys(box);
out.bad_save = T.save(() => mem, 'everything');
out.throws = T.view(() => { throw new Error('denied'); }, true);
out.bogus_kept = T.view(() => ({ getItem: () => 'cards' }), false);
// The pills, and what the second map's rows ask and count.
out.cells = Object.fromEntries(SUMS.concat(MORE).map(s => { const c = T.cells(s); return [s.key.split(/[/:]/).pop(), { d: c.d, p: c.p, r: c.r }]; }));
out.dots = Object.fromEntries(SUMS.concat(MORE).map(s => [s.key.split(/[/:]/).pop(), T.cells(s).dot]));
out.more_ask = MORE.map(s => T.asks(s));
out.more_totals = T.totals(MORE);
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    return json.loads(js_engine.run(TABLE + f"const SUMS = {json.dumps(_SUMMARIES)}, MORE = {json.dumps(_MORE)};\n" + _HARNESS))


def test_what_asks_for_the_eye_opens_by_itself_a_calm_row_stays_folded(ran):
    assert ran["start"] == ["control", "bree", "gondolin", "twin"], ran["start"]


def test_rows_open_each_on_its_own_several_at_once(ran):
    """The maintainer's condition: opening a row closes no other."""
    assert ran["two_more"] == ["control", "bree", "gondolin", "twin", "calm", "dev"], ran["two_more"]


def test_a_folded_row_stays_folded_until_its_next_incident(ran):
    assert ran["folded_kept"] is False
    assert ran["reopened"] is True


def test_all_or_none_and_a_row_gone_forgets_its_state(ran):
    assert ran["none"] == [] and ran["all"] == 7
    assert ran["forgotten"] == 2


def test_the_totals_filter_the_rows(ran):
    assert ran["totals"] == {"judge": 1, "approve": 1, "isolated": 1, "blocked": 1, "restoring": 1}
    assert ran["filtered"] == ["gondolin"]
    assert ran["bogus_filter"] == 7                     # a filter not of the list keeps every row


def test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone(ran):
    assert ran["phone"] == "table" and ran["desk"] == "tiles"      # the phone's default, whatever its size
    assert ran["saved"] is True and ran["phone_after_save"] == "tiles" and ran["key"] == ["glorfindel_infra_view"]
    assert ran["bad_save"] is False
    assert ran["throws"] == "table" and ran["bogus_kept"] == "tiles"


def test_a_row_says_each_module_in_a_pill_a_dash_where_it_does_not_reach(ran):
    c = ran["cells"]
    assert c["identities"] == {"d": ["watched", "quiet"], "p": ["—", "none"], "r": ["—", "none"]}
    assert c["control"]["d"] == ["to judge", "wait"]
    assert c["bree"]["p"] == ["blocked", "orange"] and c["gondolin"]["p"] == ["isolated", "red"]
    assert c["twin"]["p"] == ["to approve", "wait"] and c["twin"]["r"] == ["restoring", "green"]
    assert c["calm"] == {"d": ["watched", "quiet"], "p": ["ready", "quiet"], "r": ["protected", "quiet"]}
    assert c["dev"]["p"] == ["—", "none"]                        # out of reach: PROTECT does not reach it
    assert c["both"]["p"] == ["isolated · blocked", "red"]
    assert c["gap"]["d"] == ["a card", "wait"] and c["nsg-web"]["d"] == ["—", "none"]
    assert c["unread"]["r"] == ["not read", "none"]              # the vaults' inventory not read: never « — »
    assert c["release"]["p"] == ["isolated · to approve", "wait"]   # what is done, never hidden by what waits


def test_a_row_s_dot_is_the_worst_on_it(ran):
    assert ran["dots"] == {"identities": "quiet", "control": "wait", "bree": "orange", "gondolin": "red", "twin": "green",
                           "calm": "quiet", "dev": "quiet", "both": "red", "gap": "wait", "nsg-web": "quiet", "unread": "quiet",
                           "release": "red"}


def test_isolated_and_blocked_counts_in_both_a_card_not_a_decision_asks_but_is_not_to_judge(ran):
    assert ran["more_ask"] == [True, True, False, False, True]
    assert ran["more_totals"] == {"judge": 1, "approve": 1, "isolated": 2, "blocked": 1, "restoring": 0}


def test_the_logic_is_pure():
    body = TABLE.split("const InfraTable", 1)[1]
    for word in ("document.", "window.", "fetch(", "localStorage", "innerHTML", "_cfgData", "Console."):
        assert word not in body, word


# ── The page: what a row reads of its tile, and the table it draws (glorfindel.js, run as it is) ────────────
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
GROUPS = (STATIC / "infra_groups.js").read_text(encoding="utf-8")
_PAGE = ("_attr", "_on", "_fullId", "_sameAsset", "_NOT_DECISIONS", "_tileSummary", "_settleTable", "_tableHtml",
         "_tableRow", "_unfolded")
_RID = "/subscriptions/a/resourcegroups/rg/providers/microsoft.compute/virtualmachines/"
_TILES = [
    {"key": _RID + "bree", "resource_id": _RID + "bree", "vm_name": "bree",
     "states": [{"type": "isolated"}, {"type": "blocked", "ip": "203.0.113.4"}]},
    {"key": _RID + "gondolin", "resource_id": _RID + "gondolin", "vm_name": "gondolin", "states": []},
    {"key": _RID + "twin", "resource_id": _RID + "twin", "vm_name": "twin", "states": []},
    {"key": _RID + "sentinel", "resource_id": _RID + "sentinel", "vm_name": "sentinel", "states": []},
    {"key": _RID + "gap", "resource_id": _RID + "gap", "vm_name": "gap", "states": []},
    {"key": _RID + "wide", "resource_id": _RID + "wide", "vm_name": "wide", "states": [{"type": "blocked", "scoped": False}]},
    {"key": _RID + "dev", "resource_id": "/subscriptions/b/resourcegroups/rg/providers/microsoft.compute/virtualmachines/dev",
     "vm_name": "dev", "states": [], "oor": True},
]
_ESCS = [
    {"id": "e1", "resource_id": _RID + "gondolin", "escalation_type": "mode_hold", "action": "isolate_vm", "held": True},
    {"id": "e2", "resource_id": _RID + "gap", "escalation_type": "posture_gap", "action": "none"},
    {"id": "e3", "resource_id": "/subscriptions/b/resourcegroups/rg/providers/microsoft.compute/virtualmachines/dev",
     "escalation_type": "mode_hold", "action": "isolate_vm", "held": True},
]
# The page's neighbours, stubbed: a card is on the tile of its id (_onTile), held when it says so (_isHeld), a tile
# out of reach when it says so (_isOor); the vaults' inventory per name (_vmProtected: null, not read); the tile
# drawn as its name and its fold (_tileHtml); one VM essential (_priorityOf). What is run is the page's own.
_PAGE_HARNESS = r"""
let _groupBy = 'none', _tableFilter = '', _tableSums = [];
const _expandedVms = new Set(), _state = { priority_levels: { gondolin: 'essential' } };
const _priorityOf = (levels, vm) => (levels && levels[vm]) || 'standard';
const _PRIORITY_TIP = { essential: 'its grave detections keep the reserve', quiet: 'shown quiet' };
const _tableRows = InfraTable.rows();
let _cfgData = { assets: [{ type: 'azure_backup_vault', name: 'rsv' }] };
const _watchSub = () => '';
const Console = { watchStatus: () => null };
const _isOor = r => !!r.oor;
const _onTile = (e, r) => e.resource_id === r.resource_id;
const _isHeld = e => e.held === true;
const _vmProtected = n => ({ bree: true, gondolin: true, gap: true, wide: true, twin: true, sentinel: null })[n] ?? false;
const _tileHtml = r => `<div id="asset-${r.key}">TILE ${r.vm_name} ${_expandedVms.has(r.key) ? 'unfolded' : 'folded'}</div>`;
const ctx = { vmEscs: ESCS, detEscs: [], restoreByVm: { twin: { resource_id: TILES[2].resource_id } } };
const tileOf = k => TILES.find(t => t.key === k), slots = TILES.map(t => t.key).concat([null]);
const out = {};
const name = k => k.split('/').pop();
const opened = html => [...html.matchAll(/data-row="([^"]+)" aria-expanded="true"/g)].map(m => name(m[1]));
const drawn = html => [...html.matchAll(/TILE (\w+) (\w+)/g)].map(m => m[1] + ' ' + m[2]);
const render = () => { _settleTable(TILES, ctx); return _tableHtml(slots, tileOf, ctx); };   // as renderInfra does
const rowsOf = html => [...html.matchAll(/data-row="([^"]+)"/g)].map(m => name(m[1]));
out.sums = Object.fromEntries(TILES.map(r => { const s = _tileSummary(r, ctx); return [r.vm_name, [s.d, s.p, s.a, s.r]]; }));
let html = render();
out.opened = opened(html); out.drawn = drawn(html); out.fold_left = [..._expandedVms];
const row = (html.match(/<button type="button" class="tbl-row[^>]*gondolin"[\s\S]*?<\/button>/) || [''])[0];
out.prio = row.includes('class="prio-mark essential" title="its grave detections keep the reserve">ESSENTIAL</span>');
out.prio_elsewhere = (html.match(/prio-mark/g) || []).length;
_tableFilter = 'isolated'; out.filtered = rowsOf(render());
// Its total falls to 0: the filter goes, every row comes back.
const iso = TILES[0].states; TILES[0].states = []; out.filter_gone = rowsOf(render()).length; out.filter_after = _tableFilter;
TILES[0].states = iso; _tableFilter = '';
// gondolin folded while its action waits; it stays folded; its incident passes; a new one opens it again.
InfraTable.toggle(_tableSums.find(s => name(s.key) === 'gondolin'), _tableRows);
out.folded = opened(render()).includes('gondolin');
const held = ESCS.splice(0, 1);
render();
ESCS.unshift(...held);
out.reopened = opened(render()).includes('gondolin');
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def page() -> dict:
    script = (GROUPS + TABLE + js_engine.take(JS, *_PAGE)
              + f"const TILES = {json.dumps(_TILES)}, ESCS = {json.dumps(_ESCS)};\n" + _PAGE_HARNESS)
    return json.loads(js_engine.run(script))


def test_a_row_reads_its_tile_as_the_tile_does(page):
    s = page["sums"]
    assert s["bree"] == ["watched", "both", False, "protected"]       # isolated and blocked: both, in both totals
    assert s["gondolin"] == ["judge", "ready", True, "protected"]     # an action held: to approve
    assert s["twin"] == ["watched", "ready", False, "restoring"]
    assert s["sentinel"] == ["watched", "ready", False, "unread"]     # the vaults' inventory not read
    assert s["gap"] == ["card", "ready", False, "protected"]          # a card that is not a decision
    assert s["wide"] == ["watched", "ready", False, "protected"]      # a subnet-wide block: its NSG's, not the VM's
    assert s["dev"] == ["judge", None, False, None]                   # out of reach: nothing to approve, no vault


def test_an_open_row_shows_its_tile_in_full_a_folded_one_nothing(page):
    assert page["opened"] == ["bree", "gondolin", "twin", "gap", "dev"], page["opened"]
    assert page["drawn"] == [f"{n} unfolded" for n in page["opened"]]   # unfolded: its mode, its Release, its cards
    assert page["fold_left"] == []                                       # the tiles view's fold left as it was


def test_a_closed_row_says_its_vm_s_priority_beside_its_name(page):
    assert page["prio"] is True and page["prio_elsewhere"] == 1


def test_a_total_keeps_its_rows_only(page):
    assert page["filtered"] == ["bree"]


def test_a_filter_whose_total_falls_to_0_goes_and_every_row_comes_back(page):
    assert page["filter_gone"] == 7 and page["filter_after"] == ""


def test_the_table_s_fold_lasts_while_the_incident_does_and_the_next_one_opens_it(page):
    assert page["folded"] is False and page["reopened"] is True
