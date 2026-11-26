"""MOB4 (#972): the Glorfindel page on a phone — one section at a time under 760 px (Jonathan, 20/11,
on a mockup, option A). Each mutant takes a piece back: the tab bar shown on a large screen too
(M6683), the phone's rules applied up to 1960 px (M6684), the left column kept at 390 px (M6685),
the infra shown beside To judge (M6686), the feed below To judge (M6687), the list to judge cut at
45vh (M6688), the edges drawn on a phone (M6689), the cards kept at 260 px (M6690), the infra by
default though cards wait (M6691), the operator's pick lost at the next render (M6692), a name
outside the three taken for a tab (M6693), the badge and the default not following the cards
(M6694), the tabs not in the closed table of actions (M6695), the header left on one line (M6696),
the configuration opened behind To judge (M6697), the wide windows wider than the screen
(M6710), the configuration taking precedence over a tap (M6711), the page as high as the large
viewport (M6712). M6683–M6697 and M6710–M6712, measured by
tests/unit/test_console_phone.py. OCT1 (#1240) took off M6689: no edges left to hide on a phone.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"
HTML = "eregion_console/static/glorfindel.html"
CSS = "eregion_console/static/console.css"

_T = "tests/unit/test_console_phone.py::"

MUTANTS = [
    ("M6683", "the tab bar shown on a large screen too (MOB4)", HTML,
     "  #m-tabs { display: none; }\n", ""),
    ("M6684", "the phone's rules applied up to 1960 px: the large screen changed (MOB4)", HTML,
     "  @media (max-width: 759px) {\n", "  @media (max-width: 1959px) {\n"),
    ("M6685", "the left column kept at 390 px on a phone: the infra at 0 px again (MOB4)", HTML,
     "    #feed-col { width: auto; flex: 1; min-height: 0; border-right: 0; }\n", ""),
    ("M6686", "the infra shown beside To judge on a phone (MOB4)", HTML,
     '    body[data-m="judge"] #incidents-col, body[data-m="feed"] #incidents-col, body[data-m="infra"] #feed-col { display: none; }\n',
     '    body[data-m="infra"] #feed-col { display: none; }\n'),
    ("M6687", "the feed below To judge, To judge above the feed: two sections at once (MOB4)", HTML,
     '    body[data-m="judge"] #feed-head, body[data-m="judge"] #feed-list,\n'
     '    body[data-m="feed"] #judge-head, body[data-m="feed"] #judge-list { display: none; }\n',
     ""),
    ("M6688", "the list to judge cut at 45vh on a phone, half the screen empty (MOB4)", HTML,
     '    body[data-m="judge"] #judge-list { max-height: none; flex: 1; border-bottom: 0; }\n', ""),
    ("M6690", "the cards kept at 260 px on a phone (MOB4; OCT1: an open row's tile, the 360°'s panel)", HTML,
     "    .node-asset { flex: 1 1 100%; max-width: none; min-width: 0; }\n", ""),
    ("M6691", "the infra by default though cards wait to be judged (MOB4)", JS,
     "  const tab = _mobileTab || (_toJudge.length ? 'judge' : 'infra');\n", "  const tab = _mobileTab || 'infra';\n"),
    ("M6692", "the operator's pick lost at the next render: the default again (MOB4)", JS,
     "  const tab = _mobileTab || (_toJudge.length ? 'judge' : 'infra');\n", "  const tab = (_toJudge.length ? 'judge' : 'infra');\n"),
    ("M6693", "a name outside the three taken for a tab: every section hidden (MOB4)", JS,
     "  if (!_MOBILE_TABS.includes(which)) return;\n", ""),
    ("M6694", "the badge and the default not following the cards to judge (MOB4)", JS,
     "  _showMobileTab();                              // the phone's default tab and its badge (MOB4)\n", ""),
    ("M6695", "the tabs not in the closed table of actions: a tap does nothing (MOB4, #257)", JS,
     "  mobileTab,                                      // a phone's section, picked in its tab bar (MOB4)\n", ""),
    ("M6696", "the header left on one line on a phone: it runs off the right edge (MOB4)", CSS,
     "  header.console { flex-wrap: wrap; gap: 4px 10px; padding: 6px 10px; }\n", ""),
    ("M6697", "the configuration opened behind To judge on a phone, when cards wait (MOB4)", JS,
     "  if (_configMode) _mobileTab = 'infra';   // a phone opens the configuration in the infra's tab (MOB4)\n", ""),
    ("M6710", "the wide windows (the card to judge) wider than the screen again (MOB4, review)", HTML,
     "    .modal, .modal.wide { min-width: 0; max-width: none;", "    .modal { min-width: 0; max-width: none;"),
    ("M6711", "the configuration takes precedence again: To judge and Feed do not answer on /config (MOB4, review)", JS,
     "  const tab = _mobileTab || (_toJudge.length ? 'judge' : 'infra');\n",
     "  const tab = _configMode ? 'infra' : (_mobileTab || (_toJudge.length ? 'judge' : 'infra'));\n"),
    ("M6712", "the page as high as the large viewport, under a phone's browser bar (MOB4, review)", HTML,
     "    body { height: 100dvh; }                           /* 100vh: the large viewport, under the browser's bar */\n", ""),
]

TESTS = {
    "M6683": f"{_T}test_nothing_changes_above_760_px",
    "M6684": f"{_T}test_nothing_changes_above_760_px",
    "M6685": f"{_T}test_one_section_at_a_time_its_own_scroll",
    "M6686": f"{_T}test_one_section_at_a_time_its_own_scroll",
    "M6687": f"{_T}test_one_section_at_a_time_its_own_scroll",
    "M6688": f"{_T}test_one_section_at_a_time_its_own_scroll",
    "M6690": f"{_T}test_the_infra_on_a_phone_stacked_without_its_edges",
    "M6691": f"{_T}test_the_default_tab_then_the_operators_pick",
    "M6692": f"{_T}test_the_default_tab_then_the_operators_pick",
    "M6693": f"{_T}test_the_default_tab_then_the_operators_pick",
    "M6694": f"{_T}test_the_tab_follows_the_cards_the_configuration_and_the_first_render",
    "M6695": f"{_T}test_the_default_tab_then_the_operators_pick",
    "M6696": f"{_T}test_the_header_on_one_or_two_lines_on_a_phone",
    "M6697": f"{_T}test_the_tab_follows_the_cards_the_configuration_and_the_first_render",
    "M6710": f"{_T}test_the_infra_on_a_phone_stacked_without_its_edges",
    "M6711": f"{_T}test_a_tap_on_to_judge_answers_in_the_configuration_too",
    "M6712": f"{_T}test_the_infra_on_a_phone_stacked_without_its_edges",
}
