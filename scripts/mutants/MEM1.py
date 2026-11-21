"""MEM1 (#1016): the memory of decisions replayed on a copy of a store (scripts/memory_replay.py) — the
code's ranking, the B2 floor, the share of the same technique, the operator's store refused, nothing
of a cycle printed. M6957–M6961."""
_S = "scripts/memory_replay.py"
_T = "tests/unit/test_memory_replay.py"

MUTANTS = [
    ("M6957", "the replay gives a VM every place: the bound of one precedent per VM dropped (MEM1)", _S,
     '        if c["key"] in seen or per_vm[c["vm"]] >= memory.PER_VM:\n',
     '        if c["key"] in seen:\n'),
    ("M6958", "an undated cycle dated by the epoch, not by the B2 floor: no precedent of a dated signal (MEM1)", _S,
     '"at": memory._stored_at(meta),',
     '"at": float(meta.get("stored_at") or 0),'),
    ("M6959", "the share of the same technique counted per signal, not per precedent given (MEM1)", _S,
     "            given[name] += len(chosen)\n",
     "            given[name] += bool(chosen)\n"),
    ("M6960", "the operator's store opened when HOME is a throwaway one: only HOME's folders refused (MEM1)", _S,
     "    homes = (store_guard.operator_home(), Path.home()) if homes is None else homes\n",
     "    homes = (Path.home(),) if homes is None else homes\n"),
    ("M6961", "the name of a rule the client wrote printed as is (MEM1)", _S,
     '    return name if name in shipped else "(other)"\n',
     "    return name\n"),
]
TESTS = {
    "M6957": f"{_T}::test_one_precedent_per_vm_at_most_the_unknown_vm_counting_as_one",
    "M6958": f"{_T}::test_an_undated_cycle_is_dated_by_the_b2_floor",
    "M6959": f"{_T}::test_the_share_of_precedents_bearing_the_signal_technique",
    "M6960": f"{_T}::test_the_operator_store_is_refused_before_anything_is_opened",
    "M6961": f"{_T}::test_nothing_of_a_cycle_reaches_the_output",
}
