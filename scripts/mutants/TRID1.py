"""TRID1 (#1203): a tile is its asset, never its name — two VMs of one name in two subscriptions make two
tiles. Each mutant takes a piece back: the discovery folded by name again (M7727), two ids compared with their
case — one VM twice (M7728), an undiscovered namesake's card folded into the watch's VM (M7729), and an action
closed on it (M7730), a card on its namesake's tile (M7731), the tile a card is drawn to found by name (M7732),
the page's tiles keyed by name (M7733), a tile without its key (M7734), the order kept by name lost (M7735),
a tile's place in the page by its name (M7736), its discovery's line found by name (M7737), a VM out of reach
counted among the unprotected (M7738) — M7733, M7736–M7738 read in the page's text (they live in renderInfra and
the edges, not run); the review of TRID1: what Glorfindel closed shown on the namesake (M7739), a restore on a
tile out of reach (M7740), a restore that gives its id on the namesake (M7781), the decisions on a tile out of
reach (M7782), a key that keeps its case: an isolated VM moves (M7783), a state merged by its exact id (M7784), a
name two tiles share given to one of them (M7785), a release in flight on the namesake out of reach (M7786), an
NSG's glow on the namesake (M7787), a card's window opened by name (M7788). M7727–M7740 and M7781–M7788, measured
by tests/unit/test_console_tile_ids.py.

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
    ("M7733", "the page's tiles keyed by name: a window opens the namesake's cards — read in the page's text (TRID1)", GF_JS,
     "  _tiles = new Map([...resourceMap.values()].map(r => [r.key, r]));",
     "  _tiles = new Map([...resourceMap.values()].map(r => [r.vm_name, r]));"),
    ("M7734", "a tile without its key (TRID1)", GF_JS,
     "  resourceMap.forEach((r, key) => { r.key = key; });          // TRID1: the tile's key, its asset's\n", ""),
    ("M7735", "the order the operator dragged, kept by name, lost (TRID1)", GF_JS,
     "  const slots = _cardOrder.map(s => (s && !keySet.has(s) && named.get(s)) || s);",
     "  const slots = [..._cardOrder];"),
    ("M7736", "a VM tile's place in the page by its name: two tiles, one id — read in the page's text (TRID1)", GF_JS,
     "    id=\"asset-${_attr(key)}\"${oor ? ' data-oor=\"1\"' : ''}\n    draggable=\"true\"\n    ${_on('dragstart', 'dragVm', key)}\n    ${_on('dragend', 'dragEnd')}\n    ${_on('dragover', 'dragOver')}\n    ${_on('dragleave', 'dragLeave')}\n    ${_on('drop', 'dropOn', slotIdx)}>\n    <div class=\"node-asset-header\" ${_on('click', 'toggleAsset', key)}>\n      <div style=\"display:flex;align-items:center;gap:6px\">\n        ${dot}",
     "    id=\"asset-${_attr(vm_name)}\"${oor ? ' data-oor=\"1\"' : ''}\n    draggable=\"true\"\n    ${_on('dragstart', 'dragVm', key)}\n    ${_on('dragend', 'dragEnd')}\n    ${_on('dragover', 'dragOver')}\n    ${_on('dragleave', 'dragLeave')}\n    ${_on('drop', 'dropOn', slotIdx)}>\n    <div class=\"node-asset-header\" ${_on('click', 'toggleAsset', key)}>\n      <div style=\"display:flex;align-items:center;gap:6px\">\n        ${dot}"),
    ("M7737", "a tile's DETECT line from its namesake's discovery — read in the page's text (TRID1)", GF_JS,
     "    const disc = discovered.find(d => _sameAsset(tile, d.resource_id, d.name));",
     "    const disc = discovered.find(d => d.name === vmName);"),
    ("M7738", "a VM out of reach counted among the watch's unprotected — read in the page's text (TRID1)", GF_JS,
     "filter(r => !r.is_nsg && !r.kind && !_isOor(r))", "filter(r => !r.is_nsg && !r.kind)"),
    ("M7739", "what Glorfindel closed shown on the namesake of another subscription (TRID1, its review)", GF_JS,
     "h.resource_id === resource_id || _sameAsset(tile, h.resource_id, (h.resource_id || '').split('/').pop()));",
     "h.resource_id === resource_id || (h.resource_id || '').split('/').pop() === name);"),
    ("M7740", "a restore in course on a tile out of reach: its dot pulses green, its line cut (TRID1, its review)", GF_JS,
     "  const _restore    = _isOor(resource) ? null : restoreByVm[vm_name];", "  const _restore    = restoreByVm[vm_name];"),
    ("M7781", "a restore that gives its id shown on the namesake (TRID1, its review)", GF_JS,
     "_restore && (!_fullId(_restore.resource_id) || _sameAsset(resource, _restore.resource_id, vm_name)) ? _restore : null;",
     "_restore;"),
    ("M7782", "the watch's VM's decisions on its namesake out of reach (TRID1, its review)", GF_JS,
     "  const cached = oor ? null : _actionsCache[vm_name];", "  const cached = _actionsCache[vm_name];"),
    ("M7783", "a key that keeps its case: isolated, a VM moves and loses its fold (TRID1, its review)", GF_JS,
     "function _keyOf(rid) { return _fullId(rid) ? String(rid).toLowerCase() : String(rid || ''); }",
     "function _keyOf(rid) { return String(rid || ''); }"),
    ("M7784", "a state merged by its exact id: an isolated VM read RG-A, a second tile (TRID1, its review)", GF_JS,
     "    if (resourceMap.has(_keyOf(r.resource_id))) resourceMap.get(_keyOf(r.resource_id)).states = r.states;\n    else resourceMap.set(_keyOf(r.resource_id), r);",
     "    if (resourceMap.has(r.resource_id)) resourceMap.get(r.resource_id).states = r.states;\n    else resourceMap.set(r.resource_id, r);"),
    ("M7785", "a name two tiles share, of the order kept, given to the last of them (TRID1, its review)", GF_JS,
     "named.set(n, named.has(n) ? null : k);", "named.set(n, k);"),
    ("M7786", "a release in flight shown on the namesake out of reach (TRID1, its review)", GF_JS,
     "(_pendingActions.has(vm_name) && !oor) ? 's-releasing'", "_pendingActions.has(vm_name) ? 's-releasing'"),
    ("M7787", "an NSG's glow on the namesake of the VM it governs (TRID1, its review)", GF_JS,
     "(t.key === id || _sameAsset(t, id, id.split('/').pop()))", "(t.key === id || t.vm_name === id.split('/').pop())"),
    ("M7788", "a card's window opened by its VM's name: the namesake's cards (TRID1, its review)", GF_JS,
     "${_on('click', 'showEscModal', tile ? tile.key : vmName)}", "${_on('click', 'showEscModal', vmName)}"),
]

TESTS = {
    "M7727": f"{_T}test_two_vms_of_one_name_in_two_subscriptions_are_two_tiles",
    "M7728": f"{_T}test_isolated_a_vm_keeps_its_tile_and_its_place",
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
    "M7739": f"{_T}test_what_glorfindel_closed_is_on_its_own_vm_only",
    "M7740": f"{_T}test_a_tile_out_of_reach_never_takes_the_watch_s_vm_s_restore_decisions_or_release",
    "M7781": f"{_T}test_a_tile_out_of_reach_never_takes_the_watch_s_vm_s_restore_decisions_or_release",
    "M7782": f"{_T}test_a_tile_out_of_reach_never_takes_the_watch_s_vm_s_restore_decisions_or_release",
    "M7783": f"{_T}test_isolated_a_vm_keeps_its_tile_and_its_place",
    "M7784": f"{_T}test_isolated_a_vm_keeps_its_tile_and_its_place",
    "M7785": f"{_T}test_a_shared_name_of_the_kept_order_is_an_empty_slot",
    "M7786": f"{_T}test_a_tile_out_of_reach_never_takes_the_watch_s_vm_s_restore_decisions_or_release",
    "M7787": f"{_T}test_an_nsg_glows_the_vm_it_governs_never_its_namesake",
    "M7788": f"{_T}test_a_tile_out_of_reach_never_takes_the_watch_s_vm_s_restore_decisions_or_release",
}
