"""MEM2 (#1027): the precedents by keys and by date, on SQLite, behind a switch off by default
(glorfindel/memory_keys.py, glorfindel/memory.py) — the technique in the keys, the newest first, one
place per VM, the age, no exercise, the copies folded; off, the message unchanged; an unreadable
switch never cuts the memory. M7024–M7031."""
_K = "glorfindel/memory_keys.py"
_M = "glorfindel/memory.py"
_T = "tests/unit/test_memory_keys.py"
_RANK = ('    return (not rule or c["rule"] != rule, not vm or c["vm"] != vm, not ttp or c["ttp"] != ttp,\n'
         '            -c["at"], -c["seq"])\n')
_BOUNDS = '        if c["key"] in seen or per_vm[c["vm"]] >= memory.PER_VM:\n'

MUTANTS = [
    ("M7024", "the technique out of the keys: the newest of any technique comes first (MEM2)", _K,
     _RANK, '    return (not rule or c["rule"] != rule, not vm or c["vm"] != vm,\n            -c["at"], -c["seq"])\n'),
    ("M7025", "an old order in place of the newest: the oldest precedents given (MEM2)", _K,
     _RANK, _RANK.replace('-c["at"], -c["seq"]', 'c["at"], c["seq"]')),
    ("M7026", "the bound of one precedent per VM dropped: a flooded VM fills every place (MEM2)", _K,
     _BOUNDS, '        if c["key"] in seen:\n'),
    ("M7027", "the age out of the search: a year-old cycle is a precedent (MEM2)", _K,
     "(memory.B2_FLOOR, self._cutoff()))]", "(memory.B2_FLOOR, 0))]"),
    ("M7028", "an exercise's cycle, or one of unknown source, given as a precedent (MEM2)", _K,
     "\"WHERE source = 'real' AND COALESCE(stored_at, ?) >= ?\"", "\"WHERE 1 AND COALESCE(stored_at, ?) >= ?\""),
    ("M7029", "the copies of a replayed cycle not folded: one cycle takes several places (MEM2)", _K,
     _BOUNDS, '        if per_vm[c["vm"]] >= memory.PER_VM:\n'),
    ("M7030", "the switch off opens the memory by keys: the message to the model changes (MEM2)", _M,
     '    if not value:\n        return DISTANCE, ""\n', '    if not value:\n        return KEYS, ""\n'),
    ("M7031", "an unreadable switch cuts the memory: no memory opened, the watch down (MEM2)", _M,
     "    return DISTANCE, (f\"{SWITCH}={shown!r} inconnu", "    return \"\", (f\"{SWITCH}={shown!r} inconnu"),
]
TESTS = {
    "M7024": f"{_T}::test_a_cycle_of_the_signals_technique_comes_before_a_newer_one_of_another",
    "M7025": f"{_T}::test_the_newest_comes_first_never_the_oldest_nor_the_order_of_the_store",
    "M7026": f"{_T}::test_one_place_per_vm_whatever_floods_it",
    "M7027": f"{_T}::test_a_cycle_older_than_the_bound_is_no_precedent",
    "M7028": f"{_T}::test_an_exercise_or_a_cycle_of_unknown_source_is_never_a_precedent",
    "M7029": f"{_T}::test_the_copies_of_a_replayed_cycle_are_folded",
    "M7030": f"{_T}::test_off_the_message_to_the_model_is_todays_to_the_byte",
    "M7031": f"{_T}::test_an_unknown_switch_keeps_todays_memory_and_says_it_once",
}
