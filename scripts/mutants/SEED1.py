"""SEED1 (#655): a Hypothesis seed per round, said and replayable. The conftest sets the run's seed on
every property test and invariant machine (tests/unit/hypothesis_seed.py): drawn at night and at the
release gate, none on a pull request or a push; scripts/mutation_check.py gives round r of a run on
seed S the seed S + r - 1, said and written. M4588–M4592; the review: M4597–M4599 (a test's own
@seed kept, the seed said under a failing property test, the xdist workers on the seed said).

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
    # The review (09/11).
    ("M4597", "the run's seed written over a test's own @seed: its author's replay lost (SEED1)",
     SEED,
     '        if is_property_test(fn) and getattr(fn, "_hypothesis_internal_use_seed", None) is None:\n',
     "        if is_property_test(fn):\n"),
    ("M4598", "the seed said under a plain test's failure, not under the property test that drew (SEED1)",
     CONFTEST,
     "    if seed is not None and report.failed and hypothesis_seed.runs_hypothesis(item):\n",
     "    if seed is not None and report.failed and not hypothesis_seed.runs_hypothesis(item):\n"),
    ("M4599", "a drawn seed kept from the processes the run starts: each xdist worker draws another than the one said (SEED1)",
     CONFTEST,
     "    os.environ[hypothesis_seed.VAR] = str(seed)\n",
     "    pass\n"),
]
TESTS = {
    "M4588": f"{_RULE}::test_a_pull_request_and_a_push_keep_the_profile_derandomized",
    "M4589": f"{_SHARDS}::test_each_round_runs_on_a_seed_of_its_own_said_and_written",
    "M4590": f"{_RULE}::test_measured_a_push_replays_its_sequences_the_night_and_a_seed_do_not",
    "M4591": f"{_SHARDS}::test_each_run_gets_the_seed_given_and_never_one_it_inherited",
    "M4592": f"{_RULE}::test_measured_the_drawn_seed_reaches_the_step_summary_once",
    "M4597": f"{_RULE}::test_a_test_seeded_by_its_own_hand_keeps_its_seed",
    "M4598": f"{_RULE}::test_measured_a_failing_property_test_says_its_seed_under_its_failure",
    "M4599": f"{_RULE}::test_measured_every_xdist_worker_draws_on_the_seed_the_run_says",
}
