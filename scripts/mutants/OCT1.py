"""OCT1 (#1240): the tiles' view removed (Jonathan, 26/11) — the map is the 360° and the table, on a phone, a small
and a large screen. Each mutant takes a piece back: the tiles' view offered again (M7943), a browser that kept it
given a page without its view (M7944), the table's legend saying lines it does not draw (M7945), the page asking the
table's legend for every line (M7946), a tile left out of the table (M7947), no word when there is no tile (M7948).
M7943–M7948, measured by tests/unit/test_console_table.py and tests/unit/test_console_legend.py.

The other lots' mutants that read the tiles' view are taken off or moved, each with its reason in its own file:
FOC1 (the whole lot, its file gone), GRP1 (M7656; M7704 moved), LEG1 (M7591, M7593, M7631–M7634, M7637; M7592,
M7594, M7595, M7638 moved), MOB4 (M6689), SKY1 (M7941), TOPO1 (M6386, M6388, M6389), TOPO1b (M6506–M6508), TRID1 (M7735,
M7785); re-anchored where their rule still lives: IPS1b (M6441), MOB4 (M6690), TBL1 (M7875, M7917), TOPO1 (M6387),
TOPO1b (M6509), TRID1 (M7736, M7737). TRID1's M7735 and M7785 go with the order the operator dragged, no longer
read: Jonathan's call (26/11) is an order set in the table, a lot of its own later (TBL2, #1247).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
TB_JS = "eregion_console/static/infra_table.js"

_T = "tests/unit/test_console_table.py::"
_L = "tests/unit/test_console_legend.py::"

MUTANTS = [
    ("M7943", "the tiles' view offered again (OCT1)", TB_JS,
     "  const VIEWS = ['sky', 'table'];", "  const VIEWS = ['sky', 'tiles', 'table'];"),
    ("M7944", "a browser that kept the tiles' view given it, a view no longer drawn (OCT1)", TB_JS,
     "    if (VIEWS.includes(kept)) return kept;", "    if (VIEWS.includes(kept) || kept === 'tiles') return kept;"),
    ("M7945", "the table's legend says the lines it does not draw (OCT1)", GF_JS,
     "  const lines = view === 'table' ? '' : `", "  const lines = `"),
    ("M7946", "the page asks the table's legend for every line (OCT1)", GF_JS,
     "      ${_legend('table')}`;", "      ${_legend()}`;"),
    ("M7947", "a tile left out of the table (OCT1)", GF_JS,
     "  return _tableHtml(tiles, ctx);\n}", "  return _tableHtml(tiles.slice(1), ctx);\n}"),
    ("M7948", "no tile, no word: an empty table instead of what is missing (OCT1)", GF_JS,
     "  if (!tiles.length) {\n    const msg = hasBackends", "  if (false) {\n    const msg = hasBackends"),
]

TESTS = {
    "M7943": f"{_T}test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone",
    "M7944": f"{_T}test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone",
    "M7945": f"{_L}test_the_table_s_legend_says_no_line",
    "M7946": f"{_L}test_one_table_for_the_marks_drawn_and_said",
    "M7947": f"{_T}test_the_layer_under_the_modules_is_every_tile_a_row_or_what_is_missing",
    "M7948": f"{_T}test_the_layer_under_the_modules_is_every_tile_a_row_or_what_is_missing",
}
