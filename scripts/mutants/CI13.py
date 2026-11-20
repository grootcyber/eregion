"""CI13 (#986): a night of the invariant machines cut by its step's bound says its seed and where it
runs. The seed is said as the run begins (tests/unit/conftest.py); at night only — a seed drawn, or
more sequences than a push's — a watchdog speaks before each machine's step's bound: the seed, the
sequences begun, every thread's stack, faulthandler as its backstop (tests/unit/invariant_watchdog.py).
M6800–M6809; the review: M6856 (a seed drawn by the xdist controller, known drawn by its workers).

Caught by tests/unit/test_invariant_watchdog.py: the rule, the defaults read against invariants.yml's
bounds, and its probes in a pytest of their own — a sequence that never ends, killed by SIGKILL as
a bound cuts a step.
"""
WATCHDOG = "tests/unit/invariant_watchdog.py"
CONFTEST = "tests/unit/conftest.py"
AZURE = "tests/unit/test_invariants.py"
AWS = "tests/unit/test_invariants_aws.py"
_T = "tests/unit/test_invariant_watchdog.py::"

MUTANTS = [
    ("M6800", "the seed said at the end of the run only: a step cut by its bound never says it (CI13, the defect back)",
     CONFTEST,
     "        print(hypothesis_seed.said(seed), flush=True)\n",
     "        pass\n"),
    ("M6801", "the watchdog armed outside the night: a push's 500 sequences, even the local 60, watched (CI13)",
     WATCHDOG,
     '        return int((env.get(EXAMPLES) or "0").strip()) > NIGHT_EXAMPLES\n',
     '        return int((env.get(EXAMPLES) or "0").strip()) >= 0\n'),
    ("M6802", "the watchdog never armed: a night cut by its bound says nothing of where it ran (CI13)",
     CONFTEST,
     "            config.stash[_WATCH_FD] = os.dup(2)\n",
     "            pass\n"),
    ("M6803", "Azure's watchdog past its step's 125 minutes: the step is cut before it speaks (CI13)",
     AZURE,
     "INVARIANT_WATCHDOG_MINUTES = 115\n",
     "INVARIANT_WATCHDOG_MINUTES = 130\n"),
    ("M6804", "AWS's watchdog at Azure's minutes: its step, cut at 45, never hears it (CI13)",
     AWS,
     "INVARIANT_WATCHDOG_MINUTES = 40\n",
     "INVARIANT_WATCHDOG_MINUTES = 115\n"),
    ("M6805", "faulthandler's backstop a quarter of an hour after the words: past the bound when Python could not speak (CI13)",
     WATCHDOG,
     "LAG = 60.0                  # seconds between the words and faulthandler's backstop\n",
     "LAG = 900.0                 # seconds between the words and faulthandler's backstop\n"),
    ("M6806", "the watchdog's minutes counted from its test's start, not the run's: what ran before eats the margin (CI13)",
     WATCHDOG,
     "        return max(1.0, self.started + self.at_minutes * 60 - now)\n",
     "        return max(1.0, self.at_minutes * 60)\n"),
    ("M6807", "the watchdog left armed after its machine: it speaks, stacks and all, in a test that is not one (CI13)",
     CONFTEST,
     "    if watch is not None:\n        watch.disarm()\n",
     "    if watch is not None:\n        pass\n"),
    ("M6808", "the backstop armed over pytest's own faulthandler_timeout: the release gate's timer replaced, then cancelled (CI13)",
     WATCHDOG,
     '        return not float(config.getini("faulthandler_timeout") or 0) > 0\n',
     "        return True\n"),
    ("M6809", "the sequence's own stack left out of the words, the watchdog's said in its place (CI13)",
     WATCHDOG,
     '            f"{stacks(threading.get_ident())}"\n',
     '            f"{stacks(threading.main_thread().ident)}"\n'),
    # The review (20/11).
    ("M6856", "a drawn seed passed to the xdist workers as a number only: each worker reads it given, "
              "and a night under xdist arms no watchdog below 500 sequences (CI13)",
     CONFTEST,
     "    if drew:\n        os.environ[hypothesis_seed.DRAWN_VAR] = str(seed)\n",
     "    if drew:\n        pass\n"),
]
TESTS = {
    "M6800": f"{_T}test_measured_a_step_cut_by_its_bound_has_said_its_seed_and_the_sequence_that_runs",
    "M6801": f"{_T}test_a_pull_request_and_a_push_never_arm_it",
    "M6802": f"{_T}test_measured_a_step_cut_by_its_bound_has_said_its_seed_and_the_sequence_that_runs",
    "M6803": f"{_T}test_each_machine_speaks_before_its_step_s_bound_backstop_included",
    "M6804": f"{_T}test_each_machine_speaks_before_its_step_s_bound_backstop_included",
    "M6805": f"{_T}test_each_machine_speaks_before_its_step_s_bound_backstop_included",
    "M6806": f"{_T}test_it_speaks_its_minutes_after_the_run_began_not_after_its_test_did",
    "M6807": f"{_T}test_measured_a_machine_that_ends_is_disarmed_and_says_its_longest_sequence",
    "M6808": f"{_T}test_a_run_that_asked_pytest_s_faulthandler_keeps_it",
    "M6809": f"{_T}test_armed_it_counts_the_sequences_speaks_and_puts_everything_back",
    "M6856": f"{_T}test_measured_under_xdist_a_worker_knows_its_controller_drew_the_seed",
}
