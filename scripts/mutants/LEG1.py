"""LEG1 (#1181): the map's lines and legend say the same thing (Jonathan, 25/11, on a mockup). Each mutant
takes a piece back: an action taken alone drawing a dotted line (M7591), a VM isolated orange again
(M7592), a block done in long dashes again (M7593), a card waiting that does not flow (M7594), a detection
to judge drawn from PROTECT again (M7595), a restore in cyan again (M7596), a tile of detections purple
again (M7597), a VM restoring blue again (M7598), a legend not read from the marks drawn (M7599), the
motion kept for whoever asks for less (M7600); from the relecture: the lines waiting over one another (M7631, M7632),
every line purple (M7633), a block as « other » (M7634), the badge RESTORING blue (M7635), a VM's detections purple (M7636),
a line from no module (M7637), a restore drawn nowhere (M7638), the legend's lines on a phone (M7639), the badge pulsing
for less motion (M7640). M7591–M7600 and M7631–M7640, measured by tests/unit/test_console_legend.py.

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
     "asset.x + _waitDx(edge.key), asset.top, edge.color, '', own ? 3 : 2.5, 0.9, 'edge-wait'));",
     "asset.x + _waitDx(edge.key), asset.top, edge.color, '', own ? 3 : 2.5, 0.9, ''));"),
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
     "    .edge-wait, .dot-pulse, .node-asset.s-restoring, .node-asset.s-releasing, .badge.restoring { animation: none; }\n", ""),
    ("M7631", "every kind waiting arrives at the same point: the last drawn covers the others (LEG1, relecture)", GF_JS,
     "const _WAIT_DX = { detect: -30, isolate: 14, block: 22, other: 30, restore: 46 };", "const _WAIT_DX = { detect: 14, isolate: 14, block: 14, other: 14, restore: 14 };"),
    ("M7632", "a restore in course arrives among the lines waiting (LEG1, relecture)", GF_JS,
     "const _RESTORING_DX = 38;", "const _RESTORING_DX = 14;"),
    ("M7633", "every card's line purple: the colour no longer says the action (LEG1, relecture)", GF_JS,
     "return { key, color: _mark(key).color,", "return { key, color: 'var(--purple)',"),
    ("M7634", "a block waiting drawn as « other card » (LEG1, relecture)", GF_JS,
     "    : e.action === 'block_suspicious_ip' ? 'block'\n", "    : e.action === 'block_suspicious_ip' ? 'other'\n"),
    ("M7635", "the badge RESTORING blue again, its tile green (LEG1, relecture)", GF_HTML,
     "  .badge.restoring { background: color-mix(in srgb, var(--green) 12%, var(--bg)); color: var(--green);",
     "  .badge.restoring { background: color-mix(in srgb, var(--green) 12%, var(--bg)); color: var(--blue); "),
    ("M7636", "a VM whose only cards are detections to judge purple, its line blue (LEG1, relecture)", GF_JS,
     "                   : myEscs.length  ? (judgeOnly ? 's-judge' : 's-incident')   // LEG1: detections to judge, blue\n",
     "                   : myEscs.length  ? 's-incident'\n"),
    ("M7637", "an isolation or a block waiting drawn from no module (LEG1, relecture)", GF_JS,
     "      : nbNsg;\n", "      : null;\n"),
    ("M7638", "a restore in course drawn nowhere (LEG1, relecture)", GF_JS,
     "  const restoring = new Set(restores.map(r => r.vm_name));\n", "  const restoring = new Set();\n"),
    ("M7639", "the legend's lines shown on a phone, which draws none (LEG1, relecture)", GF_HTML,
     "    .legend .lg-lines { display: none; }                /* LEG1: their legend neither */\n", ""),
    ("M7640", "the badge RESTORING pulses for whoever asks for less motion (LEG1, relecture)", GF_HTML,
     ".node-asset.s-releasing, .badge.restoring { animation: none; }", ".node-asset.s-releasing { animation: none; }"),
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
    "M7631": f"{_T}test_each_line_arrives_apart_never_one_over_another",
    "M7632": f"{_T}test_each_line_arrives_apart_never_one_over_another",
    "M7633": f"{_T}test_the_colour_drawn_is_the_action_s",
    "M7634": f"{_T}test_the_colour_drawn_is_the_action_s",
    "M7635": f"{_T}test_the_dots_and_tiles_lines_and_the_restoring_badge",
    "M7636": f"{_T}test_a_vm_s_detections_to_judge_are_blue_after_its_states",
    "M7637": f"{_T}test_each_line_arrives_apart_never_one_over_another",
    "M7638": f"{_T}test_a_state_done_is_solid_in_its_action_s_colour",
    "M7639": f"{_T}test_no_line_on_a_phone_nor_its_legend",
    "M7640": f"{_T}test_still_for_whoever_asks_for_less_motion",
}
