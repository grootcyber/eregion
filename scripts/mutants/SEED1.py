"""SEED1 (#655): a Hypothesis seed per round, said and replayable. The conftest sets the run's seed on
every property test and invariant machine (tests/unit/hypothesis_seed.py): drawn at night and at the
release gate, none on a pull request or a push; scripts/mutation_check.py gives round r of a run on
seed S the seed S + r - 1, said and written. M4588–M4592.

Caught by tests/unit/test_hypothesis_seed.py (the rule, and its measure in a pytest of its own under
CI=true) and tests/unit/test_mutation_shards.py (the rounds' seeds).
"""
SEED = "tests/unit/hypothesis_seed.py"
CONFTEST = "tests/unit/conftest.py"
HARNESS = "scripts/mutation_check.py"
_RULE = "tests/unit/test_hypothesis_seed.py"
_SHARDS = "tests/unit/test_mutation_shards.py"

MUTANTS = [
    ("M4588", "a push draws a seed: the CI of main no longer stable, a red on it no longer the same twice (SEED1)",
     SEED,
     'DRAWN_ON = ("schedule", "workflow_dispatch")\n',
     'DRAWN_ON = ("schedule", "workflow_dispatch", "push")\n'),
    ("M4589", "every round on the run's one seed: the gate's two rounds replay one set of sequences again (SEED1)",
     HARNESS,
     "    return [seed + r for r in range(max(0, rounds))]\n",
     "    return [seed for r in range(max(0, rounds))]\n"),
    ("M4590", "the seed set on the property tests only: the invariant machines stay derandomized at night (SEED1)",
     SEED,
     "    RuleBasedStateMachine._hypothesis_internal_use_seed = seed\n",
     "    RuleBasedStateMachine._hypothesis_internal_use_seed = None\n"),
    ("M4591", "a run of the harness takes the seed its environment had: no --seed, every round on one inherited seed (SEED1)",
     HARNESS,
     "    env.pop(SEED_VAR, None)\n    if seed is not None:\n",
     "    if seed is not None:\n"),
    ("M4592", "each round of the harness writes its seed into the job's summary: thousands of lines, the drawn one lost (SEED1)",
     CONFTEST,
     '    if drew and os.environ.get("PYTEST_XDIST_WORKER", "gw0") == "gw0":\n',
     '    if os.environ.get("PYTEST_XDIST_WORKER", "gw0") == "gw0":\n'),
]
TESTS = {
    "M4588": f"{_RULE}::test_a_pull_request_and_a_push_keep_the_profile_derandomized",
    "M4589": f"{_SHARDS}::test_each_round_runs_on_a_seed_of_its_own_said_and_written",
    "M4590": f"{_RULE}::test_measured_a_push_replays_its_sequences_the_night_and_a_seed_do_not",
    "M4591": f"{_SHARDS}::test_each_run_gets_the_seed_given_and_never_one_it_inherited",
    "M4592": f"{_RULE}::test_measured_the_drawn_seed_reaches_the_step_summary_once",
}
