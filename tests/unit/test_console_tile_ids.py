"""TRID1 (#1203): a tile is its asset, never its name — two VMs of one name in two subscriptions make two tiles.

Before, the map folded every VM, card and closed action of one name into the first tile of that name: a VM
of the watch's subscription and a VM of another one, both `web-1`, made one tile — its cards mixed, the other
subscription's card under the watch's VM, its buttons acting on it. Now the map's tiles are keyed by their
asset (`key`: the resource id, or the name a tile is filed by without one), two full ids compared without
their case (Azure's), a full id and a bare name by the name, as before. The order the operator dragged, kept
by name before, is read again as keys.

The map's construction runs as it is (`_tileMap`, taken out of renderInfra), with the helpers it reads, in
Node or a headless Chromium (tests/unit/js_engine.py). Measured in a headless Chromium (the PR says how).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")

PROD = "/subscriptions/abcdef01-0000-0000-0000-00000000cdef/resourceGroups/rg-web/providers/Microsoft.Compute/virtualMachines/"
DEV = "/subscriptions/aaaabbbb-1111-2222-3333-444455556666/resourceGroups/rg-dev/providers/Microsoft.Compute/virtualMachines/"

_TAKEN = ("_TARGET_KINDS", "_targetOf", "_IDENTITY_TILE", "_isIdentityCard", "_ENTRA_TABLES", "_WATCHED",
          "_watchedRules", "_isWatched", "_isIdentityId", "_ownTile", "_coversVm", "_onTile", "_isNsgId",
          "_isLocalState", "_isWatchCard", "_clusterKey", "_fullId", "_keyOf", "_sameAsset", "_cardTile", "_buildSlots",
          "_tileMap", "_ZONED", "_relTime", "_attr", "_handledLines")
_HARNESS = r"""
let _cfgData = { detection: { rules: [] } }, _tiles = new Map(), _cardOrder = [], _state = { handled: [] }, _nsgGlowCache = [];
const out = {};
const card = (id, rid, extra) => Object.assign({ id, resource_id: rid, action: 'isolate_vm', escalation_type: 'mode_hold' }, extra || {});
const known = [{ resource_id: PROD.replace('/resourceGroups/rg-web/', '/resourceGroups/RG-WEB/') + 'web-1', vm_name: 'web-1' }];
const discovered = [
  { name: 'web-1', resource_id: PROD + 'web-1', last_seen: 'x' },          // the same VM as the known one, its RG's case aside
  { name: 'web-1', resource_id: DEV + 'web-1', last_seen: 'y' },           // another subscription's, same name
  { name: 'db-1', resource_id: PROD.replace('rg-web', 'rg-data') + 'db-1', last_seen: 'z' },
];
const escs = [
  card('c-dev', DEV + 'web-1'),                                           // the other subscription's card
  card('c-prod', PROD + 'web-1'),
  card('c-bare', 'web-1'),                                                // a card filed by a bare name
  card('c-id', '/subscriptions/x/whatever', { target: { kind: 'identity' } }),
];
const handled = [{ resource_id: DEV + 'web-1' }, { resource_id: PROD + 'web-1' }];
const map = _tileMap(known, [], discovered, escs, handled);
_tiles = new Map([...map.values()].map(r => [r.key, r]));
out.keys = [...map.keys()];
out.names = [...map.values()].map(r => r.vm_name);
out.every_key_its_own = [...map.entries()].every(([k, r]) => r.key === k);
out.on_tile = Object.fromEntries([...map.values()].filter(r => !r.kind).map(r => [r.key, escs.filter(e => _onTile(e, r)).map(e => e.id)]));
out.card_tile = Object.fromEntries(escs.map(e => [e.id, (_cardTile(e) || {}).key || null]));
// The other subscription's VM undiscovered: its card, and an action closed on it, still make it a tile of
// its own — never folded into the watch's VM of the same name.
const prodOnly = [discovered[0]];
out.from_discovery = [..._tileMap([], [], [discovered[0], discovered[1]], [], []).keys()];   // the discovery alone
out.from_card = [..._tileMap([], [], prodOnly, [card('c-dev', DEV + 'web-1')], []).keys()];
out.from_handled = [..._tileMap([], [], prodOnly, [], [{ resource_id: DEV + 'web-1' }]).keys()];
// The order kept before held names: a name one tile's alone read as its key; a name two tiles share, left out.
_cardOrder = ['db-1', 'web-1', null];
out.slots = _buildSlots([...map.keys()]);
// The review of TRID1. Isolated, a VM keeps its tile and its place: its state file reads its group RG-A, the
// discovery rg-a.
const A = PROD.replace('rg-web', 'rg-a'), vm1 = { name: 'vm1', resource_id: A + 'vm1', last_seen: 'x' };
const vm2 = { name: 'vm2', resource_id: A + 'vm2', last_seen: 'x' };
const calm = _tileMap([], [], [vm1, vm2], [], []);
const isolated = _tileMap([], [{ resource_id: A.replace('rg-a', 'RG-A') + 'vm1', vm_name: 'vm1',
                                states: [{ type: 'isolated' }] }], [vm1, vm2], [], []);
out.calm_keys = [...calm.keys()]; out.isolated_keys = [...isolated.keys()];
out.isolated_states = (isolated.get(out.calm_keys[0]) || {}).states || [];
_tiles = new Map([...calm.values()].map(r => [r.key, r])); _cardOrder = [null, out.calm_keys[1], out.calm_keys[0]];
out.slots_calm = _buildSlots(out.calm_keys);
_tiles = new Map([...isolated.values()].map(r => [r.key, r]));
out.slots_isolated = _buildSlots(out.isolated_keys);
// Two entries of one VM that differ by their case only: one tile.
out.one_by_case = [..._tileMap([{ resource_id: A + 'vm1', vm_name: 'vm1' }],
                               [{ resource_id: A.toUpperCase() + 'VM1'.toLowerCase(), vm_name: 'vm1', states: [] }], [], [], []).keys()];
// A VM configured RG-WEB, its state RG-WEB (isolated), its discovery rg-web: one tile, its state kept — the
// discovery never takes the place of what was there.
const kept = _tileMap(known, [{ resource_id: known[0].resource_id, vm_name: 'web-1', states: [{ type: 'isolated' }] }],
                      [discovered[0]], [], []);
out.kept_states = [...kept.values()].map(r => (r.states || []).length);
// What Glorfindel closed: on its own VM only.
_tiles = new Map([...map.values()].map(r => [r.key, r]));
_state = { handled: [{ resource_id: DEV + 'web-1', resolution: 'released on dev' },
                     { resource_id: PROD + 'web-1', resolution: 'released on prod' }] };
out.handled_prod = _handledLines(PROD + 'web-1', 'web-1');
out.handled_dev = _handledLines(DEV + 'web-1', 'web-1');
// A name two tiles share is an empty slot — never given to the last of its tiles.
const ks = [...map.keys()];
_cardOrder = ['db-1', 'web-1']; const withShared = _buildSlots(ks);
_cardOrder = ['db-1', null]; const withEmpty = _buildSlots(ks);
out.shared_is_empty = JSON.stringify(withShared) === JSON.stringify(withEmpty);
// An NSG's glow: the VM it governs, by its id — never its namesake.
const els = {};
_nsgGlowCache = [[DEV + 'web-1']];
(function (document) {
  GLOW_FN
  _glowNsgVms(0, true);
})({ getElementById: id => (els[id] = els[id] || { on: false, classList: { toggle(c, on) { els[id].on = on; } } }) });
out.glowed = Object.entries(els).filter(([, e]) => e.on).map(([id]) => id);
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    harness = _HARNESS.replace("GLOW_FN", js_engine.take(JS, "_glowNsgVms"))
    script = (js_engine.take(JS, *_TAKEN) + f"const PROD = {json.dumps(PROD)};\nconst DEV = {json.dumps(DEV)};\n" + harness)
    return json.loads(js_engine.run(script))


def test_two_vms_of_one_name_in_two_subscriptions_are_two_tiles(ran):
    keys = [k for k, n in zip(ran["keys"], ran["names"]) if n == "web-1"]
    assert len(keys) == 2, ran["keys"]
    # The configured VM and its discovery, its group's case aside, are one tile — never two.
    assert sum(1 for k in ran["keys"] if k.lower() == (PROD + "web-1").lower()) == 1
    assert (DEV + "web-1").lower() in ran["keys"]                 # its key: the id, canonical (lower case)
    # The discovery alone sees both: two tiles, without a card or a closed action to tell them apart.
    assert ran["from_discovery"] == [(PROD + "web-1").lower(), (DEV + "web-1").lower()], ran["from_discovery"]
    assert ran["every_key_its_own"] is True
    # Closed actions and cards add no tile of their own for a VM already there.
    assert ran["names"].count("web-1") == 2 and "db-1" in ran["names"]


def test_an_undiscovered_namesake_is_still_a_tile_of_its_own(ran):
    """A card, or an action Glorfindel closed, on the other subscription's VM the discovery did not see."""
    for case in ("from_card", "from_handled"):
        assert ran[case] == [(PROD + "web-1").lower(), (DEV + "web-1").lower()], (case, ran[case])


def test_a_card_is_on_its_asset_s_tile_never_on_a_namesake(ran):
    prod_key = next(k for k in ran["keys"] if k.lower() == (PROD + "web-1").lower())
    on = ran["on_tile"]
    dev_key = (DEV + "web-1").lower()
    assert "c-dev" in on[dev_key] and "c-dev" not in on[prod_key]
    assert "c-prod" in on[prod_key] and "c-prod" not in on[dev_key]
    # A card filed by a bare name: on the tiles of that name, as before (it says no subscription).
    assert "c-bare" in on[prod_key]
    assert ran["card_tile"]["c-dev"] == dev_key and ran["card_tile"]["c-prod"] == prod_key
    assert ran["card_tile"]["c-id"] == "entra:identities"


def test_the_order_kept_by_name_is_read_again_as_keys(ran):
    db_key = next(k for k, n in zip(ran["keys"], ran["names"]) if n == "db-1")
    slots = ran["slots"]
    assert slots[0] == db_key, slots                       # a name one tile's alone: its key, its place kept
    assert "web-1" not in slots                            # a name two tiles share: left out, both placed
    assert sorted(s for s in slots if s) == sorted(ran["keys"])


def test_isolated_a_vm_keeps_its_tile_and_its_place(ran):
    """The review of TRID1: the key, canonical — a state file read `RG-A` and the discovery `rg-a`, one key; the
    operator's order and fold kept."""
    assert ran["isolated_keys"] == ran["calm_keys"], (ran["calm_keys"], ran["isolated_keys"])
    assert ran["isolated_states"] == [{"type": "isolated"}]
    assert ran["slots_isolated"] == ran["slots_calm"]
    assert len(ran["one_by_case"]) == 1, ran["one_by_case"]
    assert ran["kept_states"] == [1], ran["kept_states"]          # discovered with another case: its state kept


def test_what_glorfindel_closed_is_on_its_own_vm_only(ran):
    assert "released on prod" in ran["handled_prod"] and "released on dev" not in ran["handled_prod"]
    assert "released on dev" in ran["handled_dev"] and "released on prod" not in ran["handled_dev"]


def test_a_shared_name_of_the_kept_order_is_an_empty_slot(ran):
    assert ran["shared_is_empty"] is True


def test_an_nsg_glows_the_vm_it_governs_never_its_namesake(ran):
    assert ran["glowed"] == ["asset-" + (DEV + "web-1").lower()], ran["glowed"]


def test_a_tile_out_of_reach_never_takes_the_watch_s_vm_s_restore_decisions_or_release():
    """Read by name (the watch's subscription): a restore in course, the VM's decisions, a release in flight —
    never on a namesake out of reach; a restore that gives its id, on its own VM only."""
    vm = JS.split("function _renderAssetNode(", 1)[1].split("\n}\n", 1)[0]
    assert "  const _restore    = _isOor(resource) ? null : restoreByVm[vm_name];" in vm
    assert "_restore && (!_fullId(_restore.resource_id) || _sameAsset(resource, _restore.resource_id, vm_name)) ? _restore : null;" in vm
    assert "  const cached = oor ? null : _actionsCache[vm_name];" in vm
    assert "(_pendingActions.has(vm_name) && !oor) ? 's-releasing'" in vm
    # A card's window opened by its tile's key.
    assert "${_on('click', 'showEscModal', tile ? tile.key : vmName)}" in JS


def test_the_page_keys_its_tiles_its_folds_its_drags_and_its_windows():
    assert "  resourceMap.forEach((r, key) => { r.key = key; });" in JS
    assert "  _tiles = new Map([...resourceMap.values()].map(r => [r.key, r]));" in JS
    assert "  const resourceMap = _tileMap(knownResources, resources, discovered, vmEscs, _state.handled);" in JS
    assert JS.count('id="asset-${_attr(key)}"') == 3 and 'id="asset-${_attr(vm_name)}"' not in JS
    assert JS.count("${_on('dragstart', 'dragVm', key)}") == 3 and JS.count("${_on('click', 'toggleAsset', key)}") == 3
    assert "_currentVmNames = [...resourceMap.values()].map(r => r.key);" in JS
    modal = JS.split("function showEscModal(key) {", 1)[1].split("\n}\n", 1)[0]
    assert "  const tile = _tiles.get(key);\n  const vmName = tile ? tile.vm_name : key;" in modal
    edges = JS.split("function _drawTopologyEdges() {", 1)[1].split("\n}\n", 1)[0]
    assert "const tile    = _tiles.get(el.id.slice('asset-'.length)) || {};" in edges
    assert "const disc = discovered.find(d => _sameAsset(tile, d.resource_id, d.name));" in edges
    assert "const vmRes = resources.find(r => _sameAsset(tile, r.resource_id, r.vm_name));" in edges
    # Out of reach, no vault of the watch's: never counted among its unprotected VMs.
    assert "filter(r => !r.is_nsg && !r.kind && !_isOor(r))" in JS
    # The VM's actions still go to the server by its name: it resolves a VM by name (said in the PR).
    assert "${_on('click', 'confirmRelease', vm_name)}" in JS
