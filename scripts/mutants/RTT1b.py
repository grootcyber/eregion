"""RTT1b (#1174): a detection-only card titled by its rule, in the console (Jonathan, 25/11, on a mockup).
Each mutant takes a piece back: the rule's title ignored (M7546), the neutral title saying a change again
(M7547), a rule's title over an action's label (M7548), a title over 80 characters shown (M7549), a title with a
control character shown (M7550), the tile's line saying the type, not the rule (M7551), a group titled by its first
card's rule (M7552), its context line by its first card's (M7553), the window « ×N » by its first card's
(M7554), a tile of its own named by its key (M7555). M7546–M7555, measured by
tests/unit/test_console_rule_titles.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
CON_JS = "eregion_console/static/console.js"

_T = "tests/unit/test_console_rule_titles.py::"

MUTANTS = [
    ("M7546", "a detection-only card's rule title ignored: the family's title again for all (RTT1b)", GF_JS,
     "if (_DETECTION_ONLY.has(e.escalation_type)) return _ruleTitle(e) || _ESC_TITLES[e.escalation_type];",
     "if (_DETECTION_ONLY.has(e.escalation_type)) return _ESC_TITLES[e.escalation_type];"),
    ("M7547", "the neutral title says a change again, of a sign-in too (RTT1b)", GF_JS,
     "  identity_change:      'Entra ID detection',\n", "  identity_change:      'Entra ID identity change',\n"),
    ("M7548", "a rule's title over an action's label, on any card (RTT1b)", GF_JS,
     "if (_DETECTION_ONLY.has(e.escalation_type)) return _ruleTitle(e) || _ESC_TITLES[e.escalation_type];",
     "if (_ruleTitle(e) || _DETECTION_ONLY.has(e.escalation_type)) return _ruleTitle(e) || _ESC_TITLES[e.escalation_type];"),
    ("M7549", "a rule's title over 80 characters shown, though the Python shows the neutral one (RTT1b)", CON_JS,
     "!t.trim() || [...t].length > RULE_TITLE_MAX || /", "!t.trim() || /"),
    ("M7550", "a rule's title with a control character shown, though the Python refuses it (RTT1b)", CON_JS,
     " || /[\\p{C}\\u2028\\u2029]/u.test(t)) return '';", ") return '';"),
    ("M7551", "the tile's line says the type, never the rule (RTT1b)", GF_JS,
     "  return t && t !== _ESC_TITLES[e.escalation_type] ? `${t} (detection only)` : escLabel(e.escalation_type);",
     "  return escLabel(e.escalation_type);"),
    ("M7552", "a group of several rules titled by its first card's rule (RTT1b)", GF_JS,
     "  const shared = _sharedRuleTitle(group);\n  if (shared) return shared;\n", "  return escTitle(e);\n"),
    ("M7553", "a group's context line says its first card's rule for all (RTT1b)", GF_JS,
     "_escCtx(e, pct, isModeHold || isWriteBlocked || isActionFailed, _sharedRuleTitle(group))",
     "_escCtx(e, pct, isModeHold || isWriteBlocked || isActionFailed)"),
    ("M7554", "the window « ×N » titled by its first card's rule (RTT1b)", GF_JS,
     "_sharedTitle(members.map(id => _escById[id]))", "escTitle(e)"),
    ("M7555", "the card of JUG1 names a tile of its own by its key, « plane:control » (RTT1b)", GF_JS,
     "${_unattributed(e) ? 'not attributed' : (_tileSaid(e) || vmName)}", "${_unattributed(e) ? 'not attributed' : vmName}"),
]

TESTS = {
    "M7546": f"{_T}test_a_detection_only_card_is_titled_by_its_rule_else_by_its_family",
    "M7547": f"{_T}test_a_detection_only_card_is_titled_by_its_rule_else_by_its_family",
    "M7548": f"{_T}test_a_detection_only_card_is_titled_by_its_rule_else_by_its_family",
    "M7549": f"{_T}test_the_rule_s_title_is_read_again_as_the_python_reads_it",
    "M7550": f"{_T}test_the_rule_s_title_is_read_again_as_the_python_reads_it",
    "M7551": f"{_T}test_the_tile_says_the_rule_s_title_detection_only",
    "M7552": f"{_T}test_a_group_takes_the_rule_s_title_only_when_all_its_cards_share_it",
    "M7553": f"{_T}test_a_group_takes_the_rule_s_title_only_when_all_its_cards_share_it",
    "M7554": f"{_T}test_a_group_takes_the_rule_s_title_only_when_all_its_cards_share_it",
    "M7555": f"{_T}test_a_tile_of_its_own_is_named_by_its_label_never_its_key",
}
