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
          "_isLocalState", "_isWatchCard", "_clusterKey", "_fullId", "_sameAsset", "_cardTile", "_buildSlots",
          "_tileMap")
_HARNESS = r"""
let _cfgData = { detection: { rules: [] } }, _tiles = new Map(), _cardOrder = [];
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
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    script = (js_engine.take(JS, *_TAKEN) + f"const PROD = {json.dumps(PROD)};\nconst DEV = {json.dumps(DEV)};\n" + _HARNESS)
    return json.loads(js_engine.run(script))


def test_two_vms_of_one_name_in_two_subscriptions_are_two_tiles(ran):
    keys = [k for k, n in zip(ran["keys"], ran["names"]) if n == "web-1"]
    assert len(keys) == 2, ran["keys"]
    # The configured VM and its discovery, its group's case aside, are one tile — never two.
    assert sum(1 for k in ran["keys"] if k.lower() == (PROD + "web-1").lower()) == 1
    assert DEV + "web-1" in ran["keys"]
    # The discovery alone sees both: two tiles, without a card or a closed action to tell them apart.
    assert ran["from_discovery"] == [PROD + "web-1", DEV + "web-1"], ran["from_discovery"]
    assert ran["every_key_its_own"] is True
    # Closed actions and cards add no tile of their own for a VM already there.
    assert ran["names"].count("web-1") == 2 and "db-1" in ran["names"]


def test_an_undiscovered_namesake_is_still_a_tile_of_its_own(ran):
    """A card, or an action Glorfindel closed, on the other subscription's VM the discovery did not see."""
    for case in ("from_card", "from_handled"):
        assert ran[case] == [PROD + "web-1", DEV + "web-1"], (case, ran[case])


def test_a_card_is_on_its_asset_s_tile_never_on_a_namesake(ran):
    prod_key = next(k for k in ran["keys"] if k.lower() == (PROD + "web-1").lower())
    on = ran["on_tile"]
    assert "c-dev" in on[DEV + "web-1"] and "c-dev" not in on[prod_key]
    assert "c-prod" in on[prod_key] and "c-prod" not in on[DEV + "web-1"]
    # A card filed by a bare name: on the tiles of that name, as before (it says no subscription).
    assert "c-bare" in on[prod_key]
    assert ran["card_tile"]["c-dev"] == DEV + "web-1" and ran["card_tile"]["c-prod"] == prod_key
    assert ran["card_tile"]["c-id"] == "entra:identities"


def test_the_order_kept_by_name_is_read_again_as_keys(ran):
    db_key = next(k for k, n in zip(ran["keys"], ran["names"]) if n == "db-1")
    slots = ran["slots"]
    assert slots[0] == db_key, slots                       # a name one tile's alone: its key, its place kept
    assert "web-1" not in slots                            # a name two tiles share: left out, both placed
    assert sorted(s for s in slots if s) == sorted(ran["keys"])


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
