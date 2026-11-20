"""CI12 (#899): ci.yml's Linux job runs Azure's invariant machine alone, after the rest of the suite,
at the same budget and with the same database — among four processes it outlasted 8 min on Python
3.12, and the stack faulthandler wrote then killed its worker (docs/operations.md, « La CI au bon
endroit »). M6236–M6243, with Jonathan's patch of the workflow (the App of the sessions has no
Workflows right); measured by tests/unit/test_workflows.py. M1441, M3588 and M4191 follow the lines
they mutate.
"""
CI = ".github/workflows/ci.yml"
_W = "tests/unit/test_workflows.py::"
_ALONE = _W + "test_ci12_azure_s_machine_runs_alone_after_the_rest_at_the_push_budget"
_REPLAYS = _W + "test_a_push_replays_the_failures_the_night_kept_on_both_machines"
_HANG = _W + "test_a_hang_of_the_ci_tests_says_where_it_waits"
_FOUR = _W + "test_ci10b_the_suite_runs_in_four_processes_from_the_dev_lock"

_NAME = "      - name: Azure's invariant machine (alone, after the rest)\n"
_IF = "        if: ${{ !cancelled() && steps.tests.outcome != 'skipped' }}\n"
_BUDGET = "          GLORFINDEL_INVARIANT_EXAMPLES: ${{ github.event_name == 'pull_request' && '200' || '500' }}\n"
_DB = "          GLORFINDEL_INVARIANT_DB: .hypothesis-invariants\n"
_RUN = "        run: python -m pytest tests/unit/test_invariants.py -q -o faulthandler_timeout=480\n"
_STEP = _NAME + _IF + "        env:\n" + _BUDGET + _DB + _RUN

MUTANTS = [
    ("M6236", "the suite in four processes runs Azure's machine again: past 8 min on 3.12, the stack written "
     "kills its worker (CI12)", CI,
     "--dist load --ignore=tests/unit/test_invariants.py -o faulthandler_timeout=480\n",
     "--dist load -o faulthandler_timeout=480\n"),
    ("M6237", "Azure's machine left out of the suite and run by no step: a push proves it nowhere (CI12)", CI,
     _STEP, ""),
    ("M6238", "Azure's machine at 500 sequences on each push of a pull request (CI12)", CI,
     _BUDGET + _DB + _RUN, '          GLORFINDEL_INVARIANT_EXAMPLES: "500"\n' + _DB + _RUN),
    ("M6239", "Azure's machine without the night's database: the failures it kept are never replayed on a "
     "push (CI12)", CI, _BUDGET + _DB + _RUN, _BUDGET + _RUN),
    ("M6240", "Azure's machine skipped when the rest is red: one red test hides the machine's verdict (CI12)",
     CI, _NAME + _IF, _NAME),
    ("M6241", "Azure's machine run after a red lint, the suite skipped: a second red that says nothing "
     "(CI12)", CI, _IF, "        if: ${{ !cancelled() }}\n"),
    ("M6242", "Azure's machine back among four processes, in its own step: its 8 min outlasted again (CI12)",
     CI, _RUN, "        run: python -m pytest tests/unit/test_invariants.py -q -n 4 --dist load "
     "-o faulthandler_timeout=480\n"),
    ("M6243", "Azure's machine hangs without saying where: no stack before the job's bound (CI12)", CI,
     _RUN, "        run: python -m pytest tests/unit/test_invariants.py -q\n"),
]
TESTS = {
    "M6236": f"{_ALONE} {_REPLAYS} {_FOUR}",
    "M6237": f"{_ALONE} {_REPLAYS}",
    "M6238": f"{_ALONE} {_REPLAYS}",
    "M6239": f"{_ALONE} {_REPLAYS}",
    "M6240": _ALONE,
    "M6241": _ALONE,
    "M6242": _ALONE,
    "M6243": f"{_ALONE} {_HANG}",
}
