"""MEM-H (#1028): the harness of the precedents (scripts/harness_precedents.py, `llm_smoke.py --precedents`)
— the same cases under three memories, none, by distance, by keys. M7032: one case's memory reaching
another's; M7033: what moves between the memories left uncounted; M7034: the genre run without its
ceiling. Measured by tests/unit/test_harness_precedents.py."""
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
]

TESTS = {
    "M7032": f"{_T}::test_each_memory_gives_its_cases_own_cycles_and_none_of_another",
    "M7033": f"{_T}::test_a_run_plays_each_case_under_the_three_memories_and_counts_what_moves",
    "M7034": f"{_T}::test_nothing_runs_without_the_ceiling",
}
