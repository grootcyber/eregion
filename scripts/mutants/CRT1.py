"""CRT1 (#1215): a VM's priority shown — the tile, the page Config, the note of the former format, the view
« Relaxed », the watch's start (docs/design/classification.md §7, §8.2). Each mutant takes a piece back: the
mark never posed (M7771), a pattern ignored by the console (M7772), the reserve copied instead of the budget's
reckoning (M7773), the line at the watch's start muted (M7774), `ESSENTIAL` in red (M7775), the mode gone from
the mark (M7776), the line « may be isolated on its own » false (M7777), `quiet` not grey (M7778), the note of
the former format gone from the page Config (M7779), the kind `priority` of the view « Relaxed » under its raw
name (M7780). M7771–M7780, measured by tests/unit/test_console_priorities.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
PRIO_JS = "eregion_console/static/priorities.js"
GF_JS = "eregion_console/static/glorfindel.js"
HTML = "eregion_console/static/glorfindel.html"
STATE = "eregion_console/config_state.py"
START = "glorfindel/watch/startup.py"

_T = "tests/unit/test_console_priorities.py::"

MUTANTS = [
    ("M7771", "the mark never posed: an essential VM's tile says its mode alone (CRT1)", PRIO_JS,
     "function _priorityMark(level, modeHtml) {\n  if (level !== 'essential' && level !== 'quiet') return modeHtml;\n",
     "function _priorityMark(level, modeHtml) {\n  return modeHtml;\n"),
    ("M7772", "a pattern ignored: the console reads a VM's level by its exact entry only, `vm-erp-*` makes none "
     "essential (CRT1)", STATE,
     "                if (lvl := acfg.autonomy.level_of(n)) != STANDARD}\n",
     "                if (lvl := next((r.priority for r in acfg.autonomy.assets if r.priority and r.match.lower() "
     "== n.lower()), STANDARD)) != STANDARD}\n"),
    ("M7773", "the reserve copied: the page's figure no longer the budget's reckoning (its envelope, its cap) (CRT1)",
     STATE,
     "        reserve, floor, part = reserve_of(count)\n",
     "        reserve, floor, part = 1.0 + 0.5 * count, 1.0, 0.5 * count\n"),
    ("M7774", "the line of the priorities at the watch's start muted (CRT1)", START,
     "        if said := priorities_line(_autonomy):\n",
     "        if said := \"\":\n"),
    ("M7775", "ESSENTIAL in red: an alarm colour on a VM's priority (CRT1, Q2)", HTML,
     "  .prio-mark.essential { color: var(--text); background: transparent; border: 1px solid var(--cyan); }\n",
     "  .prio-mark.essential { color: var(--red); background: transparent; border: 1px solid var(--red); }\n"),
    ("M7776", "the combination with the mode absent from the tile: ESSENTIAL alone, the mode dropped (CRT1, Q4)",
     PRIO_JS,
     "    + `<span class=\"prio-sep\">·</span>${modeHtml}</span>`;\n",
     "    + '</span>';\n"),
    ("M7777", "the line « may be isolated on its own » false: said of the essential VMs in human_only (CRT1, Q4)",
     STATE,
     "        if autonomy.level_of(n) == ESSENTIAL and (mode := autonomy.resolve(n)) != \"human_only\":\n",
     "        if autonomy.level_of(n) == ESSENTIAL and (mode := autonomy.resolve(n)) == \"human_only\":\n"),
    ("M7778", "quiet not grey: its mark as loud as any text (CRT1, Q2)", HTML,
     "  .prio-mark.quiet { color: var(--dim); font-weight: 400; }\n",
     "  .prio-mark.quiet { color: var(--text); font-weight: 400; }\n"),
    ("M7779", "the note of the former format gone from the page Config (CRT1, PRI2a)", PRIO_JS,
     "  if (!notes.length) return '';\n",
     "  return '';\n"),
    ("M7780", "the kind `priority` of the view « Relaxed » under its raw name (CRT1)", GF_JS,
     "  priority: 'priority level',",
     "  priority: 'priority',"),
]
TESTS = {
    "M7771": _T + "test_the_tile_marks_essential_beside_the_mode_and_nothing_for_standard",
    "M7772": _T + "test_the_level_of_each_vm_is_the_watch_s_reading_a_pattern_included",
    "M7773": _T + "test_the_reserve_comes_from_the_budget_s_one_reckoning",
    "M7774": _T + "test_the_watch_says_the_priorities_at_its_start",
    "M7775": _T + "test_quiet_is_grey_and_essential_never_an_alarm_colour",
    "M7776": _T + "test_the_tile_marks_essential_beside_the_mode_and_nothing_for_standard",
    "M7777": _T + "test_an_essential_vm_that_may_be_isolated_on_its_own_is_said_and_none_otherwise",
    "M7778": _T + "test_quiet_is_grey_and_essential_never_an_alarm_colour",
    "M7779": _T + "test_the_note_of_the_former_format_heads_the_config_page",
    "M7780": _T + "test_the_relaxed_view_labels_the_priority_kind_its_text_the_watch_s",
}
