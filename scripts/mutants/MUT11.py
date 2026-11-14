"""MUT11 (#830): the five mutants the gate of the 0.5.13 saw survive (run 43597369855), each caught
again by a test aimed at its defect. No mutant of its own (M5361–M5370 kept for it); its tests
added to the mutants they catch:
- M4990 (MSK2): since MSK3b (#792, 3e0849c6) a command names its VM « <groupe>/<nom> », which a
  homonym of another group never resolves: its test no longer reached the comparison. Now the same
  group and name in another subscription (tests/unit/test_cli_masking.py).
- M4894 (DRN2): since JUG2c (#793, dba3ac75) the reassertion's closure is said deferred: its test
  no longer reached the webhook's own branch. Now a notice said outside any lock, the bot alive
  (tests/unit/test_drain_closure.py, already its target whole).

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
_M = "tests/unit/test_cli_masking.py"

MUTANTS: list = []
TESTS: dict = {}
TESTS_ALSO = {
    "M4990": f"{_M}::test_pending_never_gives_a_group_and_name_that_take_the_vm_of_another_subscription",
}
