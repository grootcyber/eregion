"""MEM-H (#1028): the harness of the precedents (scripts/harness_precedents.py, `llm_smoke.py --precedents`)
— the same cases under three memories, none, by distance, by keys. M7032: one case's memory reaching
another's; M7033: what moves between the memories left uncounted; M7034: the genre run without its
ceiling. Its review (M7350–M7353): the memories drawn one after another, the last one cut by the ceiling;
the stores left behind; a draw the ceiling cut counted overconfident; decide given another signal than the
one the memory was searched with. Measured by tests/unit/test_harness_precedents.py."""
_H = "scripts/harness_precedents.py"
_T = "tests/unit/test_harness_precedents.py"

MUTANTS = [
    ("M7032", "one case's memory reaches another's: every case stores its history in the same memory (MEM-H)",
     _H,
     '        where = root / f"cas-{index}" / mode\n',
     "        where = root / mode\n"),
    ("M7033", "what moves between the memories left uncounted: the decision never said moved (MEM-H)", _H,
     '    return {"decision": ta != tb, "from": ta, "to": tb, "confidence": delta,\n',
     '    return {"decision": False, "from": ta, "to": tb, "confidence": delta,\n'),
    ("M7034", "the genre of the precedents run without its ceiling: paid calls with no bound (MEM-H, HRN2)",
     "scripts/llm_smoke.py",
     "    if why or not ceiling:\n"
     '        print(why or "--precedents: never without its ceiling (--max-usd) — nothing run")\n',
     "    if why:\n"
     '        print(why or "--precedents: never without its ceiling (--max-usd) — nothing run")\n'),
    ("M7350", "the memories drawn one after another, each over every case: a ceiling reached leaves the last "
     "one (cles, C3 or C5) undrawn — paid for the others alone (MEM-H review)", _H,
     "    return [(i, m) for i in range(cases) for _ in range(runs) for m in MEMORIES]\n",
     "    return [(i, m) for m in MEMORIES for i in range(cases) for _ in range(runs)]\n"),
    ("M7351", "the throwaway directory of the stores never removed: the harness's memories left behind "
     "(MEM-H review)", _H,
     '    with tempfile.TemporaryDirectory(prefix="eregion-memh-") as tmp:\n',
     '    if tmp := tempfile.mkdtemp(prefix="eregion-memh-"):\n'),
    ("M7352", "a draw the ceiling cut, forced wrong with its confidence kept, counted as an overconfident "
     "error (MEM-H review)", _H,
     '    return [(bool(s.get("good")), _action(s), s.get("confidence")) for s in slots if not s.get("cut")]\n',
     '    return [(bool(s.get("good")), _action(s), s.get("confidence")) for s in slots]\n'),
    ("M7353", "decide given the harness's bare signal, not the one the memory was searched with "
     "(MEM-H review)", _H,
     '    return {**state, "signal": signal_of(case), "past_cycles": [dict(p) for p in past]}\n',
     '    return {**state, "past_cycles": [dict(p) for p in past]}\n'),
]

TESTS = {
    "M7032": f"{_T}::test_each_memory_gives_its_cases_own_cycles_and_none_of_another",
    "M7033": f"{_T}::test_a_run_plays_each_case_under_the_three_memories_and_counts_what_moves",
    "M7034": f"{_T}::test_nothing_runs_without_the_ceiling",
    "M7350": f"{_T}::test_a_ceiling_reached_leaves_the_three_memories_drawn_alike",
    "M7351": f"{_T}::test_the_stores_are_removed_once_the_precedents_are_read",
    "M7352": f"{_T}::test_a_draw_the_ceiling_cut_is_a_failure_never_an_overconfident_error",
    "M7353": f"{_T}::test_a_run_plays_each_case_under_the_three_memories_and_counts_what_moves",
}
