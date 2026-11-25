"""LEG1 (#1181): the map's lines and legend say the same thing (Jonathan, 25/11, on a mockup). Each mutant
takes a piece back: an action taken alone drawing a dotted line (M7591), a VM isolated orange again
(M7592), a block done in long dashes again (M7593), a card waiting that does not flow (M7594), a detection
to judge drawn from PROTECT again (M7595), a restore in cyan again (M7596), a tile of detections purple
again (M7597), a VM restoring blue again (M7598), a legend not read from the marks drawn (M7599), the
motion kept for whoever asks for less (M7600). M7591–M7600, measured by tests/unit/test_console_legend.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_legend.py::"

MUTANTS = [
    ("M7591", "an action Glorfindel took alone draws a dotted line, as if it waited for approval (LEG1)", GF_JS,
     "  if (_isExecuted(e)) return null;\n", ""),
    ("M7592", "a VM isolated drawn orange again, not the red of its dot and border (LEG1)", GF_JS,
     "asset.x + (vmBlk ? 6 : 0), asset.top, _mark('isolate').color, '', 2, 0.9));",
     "asset.x + (vmBlk ? 6 : 0), asset.top, 'var(--orange)', '', 2, 0.9));"),
    ("M7593", "a block done drawn in long dashes again (LEG1)", GF_JS,
     "asset.x - (vmIso ? 6 : 0), asset.top, _mark('block').color, '', 2, 0.9));",
     "asset.x - (vmIso ? 6 : 0), asset.top, _mark('block').color, '6,4', 2, 0.9));"),
    ("M7594", "a card waiting drawn solid: nothing says it waits (LEG1)", GF_JS,
     "asset.top, edge.color, '', own ? 3 : 2.5, 0.9, 'edge-wait'));", "asset.top, edge.color, '', own ? 3 : 2.5, 0.9, ''));"),
    ("M7595", "a detection to judge drawn from PROTECT again (LEG1)", GF_JS,
     "from: key === 'restore' ? 'recover' : key === 'detect' ? 'detect' : 'protect'",
     "from: key === 'restore' ? 'recover' : 'protect'"),
    ("M7596", "a restore in cyan again, not the green of RECOVER (LEG1)", GF_JS,
     "  { key: 'restore', color: 'var(--green)',", "  { key: 'restore', color: 'var(--cyan)', "),
    ("M7597", "a tile of detections purple again while a verdict waits (LEG1)", GF_JS,
     "${judgeOnly ? 's-judge' : myEscs.length ? 's-incident' : 's-clean'}", "${myEscs.length ? 's-incident' : 's-clean'}"),
    ("M7598", "a VM restoring blue again (LEG1)", GF_HTML,
     "  .node-asset.s-restoring { border-color: var(--green);", "  .node-asset.s-restoring { border-color: var(--blue); "),
    ("M7599", "the legend's waiting line not read from the marks drawn: one purple « escalation » (LEG1)", GF_JS,
     "${_ACTION_MARKS.map(m => sw(ln(m.color, 'edge-wait'), m.wait)).join('')}", "${sw(ln('var(--purple)', 'edge-wait'), 'escalation')}"),
    ("M7600", "the lines flow and the tiles pulse for whoever asks for less motion (LEG1)", GF_HTML,
     "    .edge-wait, .dot-pulse, .node-asset.s-restoring, .node-asset.s-releasing { animation: none; }\n", ""),
]

TESTS = {
    "M7591": f"{_T}test_an_action_taken_alone_draws_no_dotted_line",
    "M7592": f"{_T}test_a_state_done_is_solid_in_its_action_s_colour",
    "M7593": f"{_T}test_a_state_done_is_solid_in_its_action_s_colour",
    "M7594": f"{_T}test_a_card_waiting_flows_toward_its_tile_once_per_tile_and_kind",
    "M7595": f"{_T}test_a_card_says_what_it_asks_by_its_colour_from_its_module",
    "M7596": f"{_T}test_one_table_for_the_marks_drawn_and_said",
    "M7597": f"{_T}test_a_tile_of_detections_is_blue_while_a_verdict_waits",
    "M7598": f"{_T}test_a_state_done_is_solid_in_its_action_s_colour",
    "M7599": f"{_T}test_one_table_for_the_marks_drawn_and_said",
    "M7600": f"{_T}test_still_for_whoever_asks_for_less_motion",
}
