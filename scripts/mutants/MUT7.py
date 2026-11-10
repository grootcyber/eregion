"""MUT7 (#699): the mutants only an invariant machine kills, measured each night on seeds drawn
(scripts/mutation_night.py). M4731–M4736 (M4736 from its review), measured by
tests/unit/test_mutation_night.py."""
_N = "scripts/mutation_night.py"
_T = "tests/unit/test_mutation_night.py::"

MUTANTS = [
    ("M4731", "a node of a machine's file read as its machine, whatever test it names: the machine "
              "taken for the killer of a mutant only a plain test holds (MUT7, the rule node by node)", _N,
     "            runs = any(p in found for p in parts)\n",
     "            runs = bool(found)\n"),
    ("M4732", "a mutant beside fixed tests taken as caught by them, unmeasured: the table alone, a "
              "frozen sequence that misses it hiding its machine's miss (MUT7)", _N,
     "    elif fixed and _caught(copy, examples, fixed, seeds[0]):\n",
     "    elif fixed:\n"),
    ("M4733", "a mutant caught on some seeds said CAUGHT: the flaky one never reaches its issue (MUT7)", _N,
     "    verdict = \"CAUGHT\" if k == n else (\"flaky\" if k else \"SURVIVES\")\n",
     "    verdict = \"CAUGHT\" if k else (\"flaky\" if k else \"SURVIVES\")\n"),
    ("M4734", "tonight's share drawn on six nights: the seventh's mutants never measured (MUT7)", _N,
     "    return day.toordinal() % parts + 1\n",
     "    return day.toordinal() % (parts - 1) + 1\n"),
    ("M4735", "a fragile mutant's replay on the night's first seed, not the one it survived on (MUT7)", _N,
     "{mc.replay_of(r['id'], s, examples, 1)}",
     "{mc.replay_of(r['id'], seed, examples, 1)}"),
    ("M4736", "a fixed part that draws taken for a fixed killer: run once, on the first seed, it says "
              "CAUGHT n/n by its fixed tests a mutant it catches on that seed only — a false green "
              "(MUT7, review)", _N,
     "    if fixed and mc.chance(fixed):\n",
     "    if False:\n"),
]
TESTS = {
    "M4731": f"{_T}test_a_target_splits_into_what_runs_a_machine_and_its_fixed_tests",
    "M4732": f"{_T}test_a_night_says_a_mutant_caught_on_every_seed_and_a_fragile_one_with_its_replay",
    "M4733": f"{_T}test_a_night_says_a_mutant_caught_on_every_seed_and_a_fragile_one_with_its_replay",
    "M4734": f"{_T}test_seven_nights_in_a_row_are_each_night_once",
    "M4735": f"{_T}test_a_night_says_a_mutant_caught_on_every_seed_and_a_fragile_one_with_its_replay",
    "M4736": f"{_T}test_a_fixed_part_that_draws_is_no_fixed_killer_its_whole_target_runs_on_each_seed",
}
