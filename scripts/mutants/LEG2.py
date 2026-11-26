"""LEG2 (#1244): the 360°'s lines follow LEG1's rule — the colour says the action, the dotted flow that a human must
act (Jonathan, 26/11). Each mutant takes a piece back: an action Glorfindel took alone waiting for approval (M7975), a
card out of reach drawn by its action, as if the watch could act there (M7976), a check that failed not red (M7977), a
block waiting said another card (M7978), a restore waiting said another card (M7979), the tile's summary without what
waits on it (M7980), a restore waiting drawn from the NSG (M7981), out of reach every kind drawn (M7982), only verdicts
waiting not blue (M7983), the 360°'s legend lines hidden on a phone again (M7984). M7975–M7984, measured by
tests/unit/test_console_table.py, tests/unit/test_console_sky.py and tests/unit/test_console_legend.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"
SK_JS = "eregion_console/static/infra_sky.js"

_T = "tests/unit/test_console_table.py::"
_S = "tests/unit/test_console_sky.py::"
_L = "tests/unit/test_console_legend.py::"

MUTANTS = [
    ("M7975", "an action Glorfindel took alone waits for an approval: a dotted line for nothing to approve (LEG2)", GF_JS,
     "  if (_isExecuted(e)) return null;\n  if (oor) return 'detect';", "  if (oor) return 'detect';"),
    ("M7976", "a card out of reach drawn by its action, as if the watch could act there (LEG2)", GF_JS,
     "  if (_isExecuted(e)) return null;\n  if (oor) return 'detect';\n", "  if (_isExecuted(e)) return null;\n"),
    ("M7977", "a check that failed not red: drawn as another card (LEG2)", GF_JS,
     "    : (e.action === 'isolate_vm' || e.escalation_type === 'verification_failed') ? 'isolate'",
     "    : e.action === 'isolate_vm' ? 'isolate'"),
    ("M7978", "a block waiting said another card: purple, not orange (LEG2)", GF_JS,
     "    : e.action === 'block_suspicious_ip' ? 'block'\n", "    : e.action === 'block_suspicious_ip' ? 'other'\n"),
    ("M7979", "a restore waiting said another card: purple, from PROTECT (LEG2)", GF_JS,
     "  return e.action === 'restore_from_backup' ? 'restore'", "  return e.action === 'restore_from_backup' ? 'other'"),
    ("M7980", "the tile's summary without what waits on it: the 360° draws no card waiting (LEG2)", GF_JS,
     "    w: [...new Set(cards.map(e => _waitKind(e, oor)).filter(Boolean))],", "    w: [],"),
    ("M7981", "a restore waiting drawn from the NSG, not from its vault (LEG2)", SK_JS,
     "restore: ['vault', 'green'],", "restore: ['nsg', 'green'],"),
    ("M7982", "out of reach, every kind drawn: PROTECT's lines onto a tile the watch cannot act on (LEG2)", SK_JS,
     "(!t.out || k === 'detect')", "true"),
    ("M7983", "only verdicts waiting not blue: purple, as any card (LEG2)", SK_JS,
     "RANK(s) === 2 && verdict(s) ? 'verdict'", "false ? 'verdict'"),
    ("M7984", "the 360°'s legend lines hidden on a phone again, though it draws them there (LEG2)", GF_HTML,
     "    .topo-graph { padding: 10px; }\n", "    .legend .lg-lines { display: none; }\n    .topo-graph { padding: 10px; }\n"),
]

TESTS = {
    "M7975": f"{_T}test_what_waits_on_a_tile_by_the_kind_of_its_action",
    "M7976": f"{_T}test_what_waits_on_a_tile_by_the_kind_of_its_action",
    "M7977": f"{_T}test_what_waits_on_a_tile_by_the_kind_of_its_action",
    "M7978": f"{_T}test_what_waits_on_a_tile_by_the_kind_of_its_action",
    "M7979": f"{_T}test_what_waits_on_a_tile_by_the_kind_of_its_action",
    "M7980": f"{_T}test_what_waits_on_a_tile_by_the_kind_of_its_action",
    "M7981": f"{_S}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7982": f"{_S}test_a_line_lights_only_when_something_happens_from_the_backend_that_acts",
    "M7983": f"{_S}test_a_system_s_sun_takes_the_colour_of_the_worst_on_it",
    "M7984": f"{_L}test_the_360_s_legend_says_its_lines_on_a_phone_too",
}
