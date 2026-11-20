"""MOB5 (#975): Overview and Dagorlad on a phone (Jonathan, 20/11, on a mockup). Each mutant takes a
piece back: the board's tabs shown on a large screen (M6698), its phone's rules applied up to 1960 px
(M6699), the wires and the drag's handle on a phone (M6700), two columns of the board at once
(M6701), the plan below the red cards and the targets (M6702), a red card picked not opening the
targets (M6703), a wire laid not opening the plan (M6704), the banner of the card picked never shown
(M6705), a name outside the three taken for a board's tab (M6706), a tap on a Runs tab ignored
(M6707), the matrix's rows not folded (M6708), the three columns of Runs at once (M6709), the verdicts too small for a finger (M6713), the note
that makes Safari zoom (M6714), Confirm and Refuse too small (M6730), Confirm and Refuse back in the
line cut at two lines (M6731, the defect at every width). M6698–M6709, M6713, M6714, M6730 and
M6731, measured by tests/unit/test_console_phone_dagorlad.py and tests/unit/test_console_phone_verdicts.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
DAG_HTML = "eregion_console/static/dagorlad.html"
DAG_JS = "eregion_console/static/dagorlad.js"
RUN_HTML = "eregion_console/static/injector.html"
RUN_JS = "eregion_console/static/injector.js"
GF_HTML = "eregion_console/static/glorfindel.html"
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_phone_dagorlad.py::"
_V = "tests/unit/test_console_phone_verdicts.py::"

MUTANTS = [
    ("M6698", "the board's tabs and banner shown on a large screen too (MOB5)", DAG_HTML,
     "  #m-tabs, #m-picked { display: none; }\n", ""),
    ("M6699", "the board's phone rules applied up to 1960 px: the large screen changed (MOB5)", DAG_HTML,
     "  @media (max-width: 759px) {\n", "  @media (max-width: 1959px) {\n"),
    ("M6700", "the wires and the drag's handle on a phone, across one column (MOB5)", DAG_HTML,
     "    #col-mid, #wires, #pills, .handle { display: none; }\n", ""),
    ("M6701", "two columns of the board at once on a phone (MOB5)", DAG_HTML,
     '    body[data-m="red"] #col-blue, body[data-m="blue"] #col-red, body[data-m="plan"] #board { display: none; }\n', ""),
    ("M6702", "the plan below the red cards and the targets on a phone (MOB5)", DAG_HTML,
     '    body[data-m="red"] #weekly, body[data-m="red"] #drills, body[data-m="red"] #plan,\n'
     '    body[data-m="blue"] #weekly, body[data-m="blue"] #drills, body[data-m="blue"] #plan { display: none; }\n', ""),
    ("M6703", "a red card picked does not open the targets: the next tap has nowhere to go (MOB5)", DAG_JS,
     "    if (_PHONE.matches && S.picked !== null) S.mobileTab = 'blue';   // a phone: on to the targets (MOB5)\n", ""),
    ("M6704", "a wire laid does not open the plan (MOB5)", DAG_JS,
     "    if (_PHONE.matches) S.mobileTab = 'plan';                         // a phone: on to the plan (MOB5)\n", ""),
    ("M6705", "the banner of the red card picked never shown: which card is taken is not said (MOB5)", DAG_JS,
     "bar.hidden = !(r && tab === 'blue');", "bar.hidden = true;"),
    ("M6706", "a name outside the three taken for a board's tab: every column hidden (MOB5)", DAG_JS,
     "  mobileTab(which) {\n    if (!_MOBILE_TABS.includes(which)) return;\n", "  mobileTab(which) {\n"),
    ("M6707", "a tap on a Runs tab ignored: the windows only (MOB5)", RUN_JS,
     "  const t = ev.target.closest('[data-toggle],[data-delivered],[data-report],[data-mtab]');\n",
     "  const t = ev.target.closest('[data-toggle],[data-delivered],[data-report]');\n"),
    ("M6708", "the matrix's rows not folded on a phone: cut at the right edge (MOB5)", RUN_HTML,
     "    .cat { grid-template-columns: 12px 78px minmax(0, 1fr); }\n", ""),
    ("M6709", "the three columns of Runs at once on a phone, two of them 1 px wide (MOB5)", RUN_HTML,
     '    body[data-m="ex"] #col-camp, body[data-m="ex"] #col-side, body[data-m="camp"] #col-ex,\n'
     '    body[data-m="camp"] #col-side, body[data-m="side"] #col-ex, body[data-m="side"] #col-camp { display: none; }\n', ""),
    ("M6713", "the verdicts 16 px high on a phone again: too small for a finger (MOB5)", GF_HTML,
     "    .judge-actions button { flex: 1 1 0; min-height: 44px; font-size: 13px; padding: 6px 4px; }\n", ""),
    ("M6714", "the note under 16 px on a phone: Safari on iOS zooms on it at each tap (MOB5)", GF_HTML,
     "    .judge-actions input { flex: 1 1 100%; font-size: 16px; padding: 8px 10px; }\n",
     "    .judge-actions input { flex: 1 1 100%; font-size: 13px; padding: 8px 10px; }\n"),
    ("M6730", "Confirm and Refuse of a verdict proposed 16 px high on a phone (MOB5)", GF_HTML,
     "    .judge-proposed button { flex: 1 1 0; min-height: 44px; font-size: 13px; padding: 6px 10px; }\n", ""),
    ("M6731", "Confirm and Refuse back inside the line of the proposal, cut with it: hidden in the list, at "
              "any width (MOB5, the defect back)", GF_JS,
     "the decision stays yours</div>\n      <div class=\"judge-proposed\" ${_on('click', 'stop')}>",
     "the decision stays yours\n      <div class=\"judge-proposed\" ${_on('click', 'stop')}>"),
]

TESTS = {
    "M6698": f"{_T}test_the_board_on_a_phone_one_column_at_a_time_without_the_wires",
    "M6699": f"{_T}test_the_board_on_a_phone_one_column_at_a_time_without_the_wires",
    "M6700": f"{_T}test_the_board_on_a_phone_one_column_at_a_time_without_the_wires",
    "M6701": f"{_T}test_the_board_on_a_phone_one_column_at_a_time_without_the_wires",
    "M6702": f"{_T}test_the_board_on_a_phone_one_column_at_a_time_without_the_wires",
    "M6703": f"{_T}test_a_tap_on_a_red_card_opens_the_targets_a_tap_on_a_target_the_plan",
    "M6704": f"{_T}test_a_tap_on_a_red_card_opens_the_targets_a_tap_on_a_target_the_plan",
    "M6705": f"{_T}test_the_tabs_the_badge_and_the_banner_follow_the_board",
    "M6706": f"{_T}test_a_tap_on_a_red_card_opens_the_targets_a_tap_on_a_target_the_plan",
    "M6707": f"{_T}test_a_tap_on_a_runs_tab_one_of_three_never_another",
    "M6708": f"{_T}test_the_runs_view_on_a_phone_one_column_and_the_matrix_folded",
    "M6709": f"{_T}test_the_runs_view_on_a_phone_one_column_and_the_matrix_folded",
    "M6713": f"{_V}test_on_a_phone_the_verdicts_are_44_px_high_the_note_16_px",
    "M6714": f"{_V}test_on_a_phone_the_verdicts_are_44_px_high_the_note_16_px",
    "M6730": f"{_V}test_on_a_phone_the_verdicts_are_44_px_high_the_note_16_px",
    "M6731": f"{_V}test_confirm_and_refuse_sit_under_the_line_of_the_proposal_never_in_it",
}
