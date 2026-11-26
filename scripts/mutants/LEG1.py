"""LEG1 (#1181): the map's lines and legend say the same thing (Jonathan, 25/11, on a mockup). Each mutant
takes a piece back: an action taken alone drawing a dotted line (M7591), a VM isolated orange again
(M7592), a block done in long dashes again (M7593), a card waiting that does not flow (M7594), a detection
to judge drawn from PROTECT again (M7595), a restore in cyan again (M7596), a tile of detections purple
again (M7597), a VM restoring blue again (M7598), a legend not read from the marks drawn (M7599), the
motion kept for whoever asks for less (M7600); from the relecture: the lines waiting over one another (M7631, M7632),
every line purple (M7633), a block as « other » (M7634), the badge RESTORING blue (M7635), a VM's detections purple (M7636),
a line from no module (M7637), a restore drawn nowhere (M7638), the legend's lines on a phone (M7639), the badge pulsing
for less motion (M7640). M7591–M7600 and M7631–M7640, measured by tests/unit/test_console_legend.py.

OCT1 (#1240) took off the tiles' view and its lines. Taken off with them: M7593, M7631, M7632, M7637 (how a line of
the tiles' view ran and arrived: the 360° routes a lane per backend, SKY1's M7911, and draws no dash); M7591, M7594,
M7595, M7633, M7634 (a card waiting drawn in its action's colour, from its module: the 360° draws every waiting card
purple — LEG2, #1244, brings the rule there). Moved onto the 360°, measured by tests/unit/test_console_sky.py: M7592
(an isolation red), M7638 (a restore in course drawn).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"
SK_JS = "eregion_console/static/infra_sky.js"

_T = "tests/unit/test_console_legend.py::"
_S = "tests/unit/test_console_sky.py::"

MUTANTS = [
    ("M7592", "a VM isolated drawn orange again, not the red of its dot and border (LEG1; OCT1: in the 360°)", SK_JS,
     "      if (s.p === 'isolated' || s.p === 'both') out.push({ from: nsg, c: 'red' });",
     "      if (s.p === 'isolated' || s.p === 'both') out.push({ from: nsg, c: 'orange' });"),
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
    ("M7635", "the badge RESTORING blue again, its tile green (LEG1, relecture)", GF_HTML,
     "  .badge.restoring { background: color-mix(in srgb, var(--green) 12%, var(--bg)); color: var(--green);",
     "  .badge.restoring { background: color-mix(in srgb, var(--green) 12%, var(--bg)); color: var(--blue); "),
    ("M7636", "a VM whose only cards are detections to judge purple, its line blue (LEG1, relecture)", GF_JS,
     "                   : myEscs.length  ? (judgeOnly ? 's-judge' : 's-incident')   // LEG1: detections to judge, blue\n",
     "                   : myEscs.length  ? 's-incident'\n"),
    ("M7638", "a restore in course drawn nowhere (LEG1, relecture; OCT1: in the 360°)", SK_JS,
     "    if (!t.out && s.r === 'restoring') out.push(", "    if (false) out.push("),
    ("M7639", "the legend's lines shown on a phone, which draws none (LEG1, relecture)", GF_HTML,
     "    .legend .lg-lines { display: none; }                /* LEG1: their legend neither */\n", ""),
    ("M7640", "the badge RESTORING pulses for whoever asks for less motion (LEG1, relecture)", GF_HTML,
     ".node-asset.s-releasing, .badge.restoring { animation: none; }", ".node-asset.s-releasing { animation: none; }"),
]

TESTS = {
    "M7592": f"{_S}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7596": f"{_T}test_one_table_for_the_marks_drawn_and_said",
    "M7597": f"{_T}test_a_tile_of_detections_is_blue_while_a_verdict_waits",
    "M7598": f"{_T}test_a_tile_restoring_is_green",
    "M7599": f"{_T}test_one_table_for_the_marks_drawn_and_said",
    "M7600": f"{_T}test_still_for_whoever_asks_for_less_motion",
    "M7635": f"{_T}test_the_dots_and_tiles_lines_and_the_restoring_badge",
    "M7636": f"{_T}test_a_vm_s_detections_to_judge_are_blue_after_its_states",
    "M7638": f"{_S}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7639": f"{_T}test_no_line_on_a_phone_nor_its_legend",
    "M7640": f"{_T}test_still_for_whoever_asks_for_less_motion",
}
