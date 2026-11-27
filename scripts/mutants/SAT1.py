"""SAT1 (#1271): the vault's satellite reads the inventory as the RECOVER block does, and never says 0 when it does not
know (Jonathan, on Imladris: « 0 protected » beside « ✓ Backup · 8 RP »). Each mutant takes a piece back: an item's name
read raw, Azure's « VM;iaasvmcontainerv2;<rg>;<vm> » never its VM (M8171), an inventory in error read as empty
(M8172), the satellite's « 0 kept » for an inventory not read (M8173), its card's « 0 resource » (M8174).
M8171–M8174, measured by tests/unit/test_console_vault_sat.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_vault_sat.py::"

MUTANTS = [
    ("M8171", "an item's name read raw: Azure's « VM;iaasvmcontainerv2;<rg>;<vm> » never its VM — the satellite at 0 (SAT1, Imladris)", GF_JS,
     "  return items.some(it => _backupVmName(it).toLowerCase() === n);",
     "  return items.some(it => ((it.name || (it.resource_id || '').split('/').pop() || '').toLowerCase()) === n);"),
    ("M8172", "an inventory in error read as an empty one: every VM said unprotected (SAT1)", GF_JS,
     "  if (!items || _vaultUnread()) return null;", "  if (!items) return null;"),
    ("M8173", "the vault's satellite says « 0 kept » for an inventory not read (SAT1)", GF_JS,
     "    if (m === 'r' && _vaultUnread()) return _vaultUnread();          // SAT1: its inventory not read — never « 0 kept »\n", ""),
    ("M8174", "the vault's card says « 0 resource » for an inventory not read (SAT1)", GF_JS,
     "    const unread = satIds.length === 1 && (all.find(b => b.id === satIds[0]) || {}).k === 'r' ? _vaultUnread() : '';",
     "    const unread = '';"),
]

TESTS = {
    "M8171": f"{_T}test_an_item_named_as_azure_lists_it_is_its_vm_the_block_s_count_and_the_sky_s_the_same",
    "M8172": f"{_T}test_an_inventory_not_read_says_nothing_never_false",
    "M8173": f"{_T}test_the_vault_s_satellite_says_when_its_inventory_is_not_read",
    "M8174": f"{_T}test_the_vault_s_card_says_when_its_inventory_is_not_read_and_why",
}
