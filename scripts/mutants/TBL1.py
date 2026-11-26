"""TBL1 (#1230): the infrastructure map as a table (Jonathan, 26/11, on a mockup), and the review of LANE1. Each
mutant takes a piece back: an NSG alone in its group taken for a lane without a VM (M7866), a group's own tile
taken for one that holds a VM (M7867), opening a row closing the others (M7868), a folded row reopened at the
next refresh (M7869), a fold kept past its incident (M7870), the table never the phone's default (M7871), a
stored view not of the list taken (M7872); the page: an action held never said to approve (M7873), a VM isolated
and blocked said isolated only (M7874), an open row without its tile (M7875), a total that filters nothing
(M7876), the table's folds never settled at a refresh (M7877). Measured by tests/unit/test_console_groups.py and
tests/unit/test_console_table.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GR_JS = "eregion_console/static/infra_groups.js"
TB_JS = "eregion_console/static/infra_table.js"
GF_JS = "eregion_console/static/glorfindel.js"

_G = "tests/unit/test_console_groups.py::"
_T = "tests/unit/test_console_table.py::"

MUTANTS = [
    ("M7866", "an NSG alone in its group taken for a lane without a VM: its PROTECT line across the small lanes (TBL1, LANE1's review)", GR_JS,
     "    const vm = l => (l.tiles.some(t => !t.kind) ? 0 : 1);", "    const vm = l => (l.tiles.some(t => !t.kind && !t.is_nsg) ? 0 : 1);"),
    ("M7867", "a group's own tile taken for one that holds a VM: its lane first (TBL1, LANE1's review)", GR_JS,
     "    const vm = l => (l.tiles.some(t => !t.kind) ? 0 : 1);", "    const vm = l => (l.tiles.some(t => !t.kind || t.kind === 'resource_group') ? 0 : 1);"),
    ("M7868", "opening a row closes the others: one row at a time again (TBL1)", TB_JS,
     "    else { rows.opened.add(s.key); rows.folded.delete(s.key); }",
     "    else { rows.opened.clear(); rows.opened.add(s.key); rows.folded.delete(s.key); }"),
    ("M7869", "a row the operator folded reopened at the next refresh while its incident lasts (TBL1)", TB_JS,
     "    for (const s of summaries) if (!asks(s)) rows.folded.delete(s.key);", "    for (const s of summaries) rows.folded.delete(s.key);"),
    ("M7870", "a fold kept past its incident: the next incident stays folded (TBL1)", TB_JS,
     "    for (const s of summaries) if (!asks(s)) rows.folded.delete(s.key);", ""),
    ("M7871", "the table never the phone's default (TBL1)", TB_JS,
     "    return phone && count > PHONE_TABLE_OVER ? 'table' : 'tiles';", "    return 'tiles';"),
    ("M7872", "a stored view not of the list taken (TBL1)", TB_JS,
     "    if (VIEWS.includes(kept)) return kept;", "    if (kept) return kept;"),
    ("M7873", "an action held never said to approve: its row neither opens nor counts (TBL1)", GF_JS,
     "    a: !oor && cards.some(_isHeld),", "    a: false,"),
    ("M7874", "a VM isolated and blocked said isolated only: out of the blocked total (TBL1)", GF_JS,
     "    p: oor || own ? null : iso && blk ? 'both' : iso ? 'isolated' : blk ? 'blocked' : 'ready',",
     "    p: oor || own ? null : iso ? 'isolated' : blk ? 'blocked' : 'ready',"),
    ("M7875", "an open row without its tile: the maintainer's condition lost (TBL1)", GF_JS,
     "  return open ? `${row}<div class=\"tbl-open\">${_tileHtml(r, slotIdx, ctx)}</div>` : row;", "  return row;"),
    ("M7876", "a total that filters nothing: every row kept under it (TBL1)", GF_JS,
     "  const shown = new Set(InfraTable.filtered(sums, _tableFilter).map(s => s.key));", "  const shown = new Set(sums.map(s => s.key));"),
    ("M7877", "the table's folds never settled at a refresh: a row folded once stays folded at its next incident (TBL1)", GF_JS,
     "  InfraTable.settle(sums, _tableRows);\n", ""),
]

TESTS = {
    "M7866": f"{_G}test_a_lane_without_a_vm_comes_after_every_lane_that_holds_one",
    "M7867": f"{_G}test_a_lane_without_a_vm_comes_after_every_lane_that_holds_one",
    "M7868": f"{_T}test_rows_open_each_on_its_own_several_at_once",
    "M7869": f"{_T}test_a_folded_row_stays_folded_until_its_next_incident",
    "M7870": f"{_T}test_a_folded_row_stays_folded_until_its_next_incident",
    "M7871": f"{_T}test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone_beyond_8",
    "M7872": f"{_T}test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone_beyond_8",
    "M7873": f"{_T}test_a_row_reads_its_tile_as_the_tile_does",
    "M7874": f"{_T}test_a_row_reads_its_tile_as_the_tile_does",
    "M7875": f"{_T}test_an_open_row_shows_its_tile_in_full_a_folded_one_nothing",
    "M7876": f"{_T}test_a_total_keeps_its_rows_only",
    "M7877": f"{_T}test_the_table_s_fold_lasts_while_the_incident_does_and_the_next_one_opens_it",
}
