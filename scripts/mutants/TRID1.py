"""TRID1 (#1203): a tile is its asset, never its name — two VMs of one name in two subscriptions make two
tiles. Each mutant takes a piece back: the discovery folded by name again (M7727), two ids compared with their
case — one VM twice (M7728), an undiscovered namesake's card folded into the watch's VM (M7729), and an action
closed on it (M7730), a card on its namesake's tile (M7731), the tile a card is drawn to found by name (M7732),
the page's tiles keyed by name (M7733), a tile without its key (M7734), the order kept by name lost (M7735),
a tile's place in the page by its name (M7736), its discovery's line found by name (M7737), a VM out of reach
counted among the unprotected (M7738). M7727–M7738, measured by tests/unit/test_console_tile_ids.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_tile_ids.py::"

MUTANTS = [
    ("M7727", "the discovery folded by name again: two VMs of one name, one tile (TRID1)", GF_JS,
     "    const existing = [...resourceMap.values()].find(r => _sameAsset(r, d.resource_id, d.name));",
     "    const existing = [...resourceMap.values()].find(r => r.vm_name === d.name);"),
    ("M7728", "two ids compared with their case: one VM twice on the map (TRID1)", GF_JS,
     "return String(r.resource_id).toLowerCase() === String(rid).toLowerCase();",
     "return r.resource_id === rid;"),
    ("M7729", "an undiscovered namesake's card folded into the watch's VM (TRID1)", GF_JS,
     "    const exists = [...resourceMap.values()].some(r => _sameAsset(r, e.resource_id, vmName));",
     "    const exists = [...resourceMap.values()].some(r => r.vm_name === vmName);"),
    ("M7730", "an action closed on an undiscovered namesake folded into the watch's VM (TRID1)", GF_JS,
     "![...resourceMap.values()].some(r => _sameAsset(r, h.resource_id, name)))",
     "![...resourceMap.values()].some(r => r.vm_name === name))"),
    ("M7731", "a card on its namesake's tile: another subscription's card under the watch's VM (TRID1)", GF_JS,
     "e.resource_id === r.resource_id || _sameAsset(r, e.resource_id, e.resource_id.split('/').pop())",
     "e.resource_id === r.resource_id || e.resource_id.split('/').pop() === r.vm_name"),
    ("M7732", "the tile a card is drawn to found by name: its line on the namesake (TRID1)", GF_JS,
     "find(t => !t.kind && _sameAsset(t, rid, rid.split('/').pop())) || null;",
     "find(t => !t.kind && t.vm_name === rid.split('/').pop()) || null;"),
    ("M7733", "the page's tiles keyed by name: a window opens the namesake's cards (TRID1)", GF_JS,
     "  _tiles = new Map([...resourceMap.values()].map(r => [r.key, r]));",
     "  _tiles = new Map([...resourceMap.values()].map(r => [r.vm_name, r]));"),
    ("M7734", "a tile without its key (TRID1)", GF_JS,
     "  resourceMap.forEach((r, key) => { r.key = key; });          // TRID1: the tile's key, its asset's\n", ""),
    ("M7735", "the order the operator dragged, kept by name, lost (TRID1)", GF_JS,
     "  const slots = _cardOrder.map(s => (s && !keySet.has(s) && named.get(s)) || s);",
     "  const slots = [..._cardOrder];"),
    ("M7736", "a VM tile's place in the page by its name: two tiles, one id (TRID1)", GF_JS,
     "    id=\"asset-${_attr(key)}\"${oor ? ' data-oor=\"1\"' : ''}\n    draggable=\"true\"\n    ${_on('dragstart', 'dragVm', key)}\n    ${_on('dragend', 'dragEnd')}\n    ${_on('dragover', 'dragOver')}\n    ${_on('dragleave', 'dragLeave')}\n    ${_on('drop', 'dropOn', slotIdx)}>\n    <div class=\"node-asset-header\" ${_on('click', 'toggleAsset', key)}>\n      <div style=\"display:flex;align-items:center;gap:6px\">\n        ${dot}",
     "    id=\"asset-${_attr(vm_name)}\"${oor ? ' data-oor=\"1\"' : ''}\n    draggable=\"true\"\n    ${_on('dragstart', 'dragVm', key)}\n    ${_on('dragend', 'dragEnd')}\n    ${_on('dragover', 'dragOver')}\n    ${_on('dragleave', 'dragLeave')}\n    ${_on('drop', 'dropOn', slotIdx)}>\n    <div class=\"node-asset-header\" ${_on('click', 'toggleAsset', key)}>\n      <div style=\"display:flex;align-items:center;gap:6px\">\n        ${dot}"),
    ("M7737", "a tile's DETECT line from its namesake's discovery (TRID1)", GF_JS,
     "    const disc = discovered.find(d => _sameAsset(tile, d.resource_id, d.name));",
     "    const disc = discovered.find(d => d.name === vmName);"),
    ("M7738", "a VM out of reach counted among the watch's unprotected (TRID1)", GF_JS,
     "filter(r => !r.is_nsg && !r.kind && !_isOor(r))", "filter(r => !r.is_nsg && !r.kind)"),
]

TESTS = {
    "M7727": f"{_T}test_two_vms_of_one_name_in_two_subscriptions_are_two_tiles",
    "M7728": f"{_T}test_two_vms_of_one_name_in_two_subscriptions_are_two_tiles",
    "M7729": f"{_T}test_an_undiscovered_namesake_is_still_a_tile_of_its_own",
    "M7730": f"{_T}test_an_undiscovered_namesake_is_still_a_tile_of_its_own",
    "M7731": f"{_T}test_a_card_is_on_its_asset_s_tile_never_on_a_namesake",
    "M7732": f"{_T}test_a_card_is_on_its_asset_s_tile_never_on_a_namesake",
    "M7733": f"{_T}test_the_page_keys_its_tiles_its_folds_its_drags_and_its_windows",
    "M7734": f"{_T}test_two_vms_of_one_name_in_two_subscriptions_are_two_tiles",
    "M7735": f"{_T}test_the_order_kept_by_name_is_read_again_as_keys",
    "M7736": f"{_T}test_the_page_keys_its_tiles_its_folds_its_drags_and_its_windows",
    "M7737": f"{_T}test_the_page_keys_its_tiles_its_folds_its_drags_and_its_windows",
    "M7738": f"{_T}test_the_page_keys_its_tiles_its_folds_its_drags_and_its_windows",
}
