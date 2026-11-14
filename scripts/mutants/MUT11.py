"""MUT11 (#830): the five mutants the gate of the 0.5.13 saw survive (run 43597369855), each caught
again by a test aimed at its defect, added to its target (TESTS_ALSO; M4990's in its own lot's
TESTS, scripts/mutants/MSK2.py):
- M4990 (MSK2): since MSK3b (#792, 3e0849c6) a command names its VM « <groupe>/<nom> », which a
  homonym of another group never resolves: its test no longer reached the comparison. Now the same
  group and name in another subscription (tests/unit/test_cli_masking.py).
- M4894 (DRN2): since JUG2c (#793, dba3ac75) the reassertion's closure is said deferred: its test
  no longer reached the webhook's own branch. Now a notice said outside any lock, the bot alive
  (tests/unit/test_drain_closure.py, already its target whole).
- M17 (the per-VM lock): the machine meets its races by chance only (a multi-NIC VM, a shared NSG
  or NSGs of their own in quarantine, a few pairs of writers, a few interleavings): ten of them
  frozen, searched with the mutant applied (tests/unit/test_invariant_regressions.py).
- M38 and M1960: the machine meets their state by chance only (`a_hold_moved_under_it`'s `gone`,
  `kept_at_the_lift`'s unblock), some seeds never at 500; the frozen sequence that names each, which
  their target did not run, added.
Its own mutants, M5361–M5367: one writer left out of the VM's lock (M5361–M5363, M5366, M5367, each
caught by races of the same test, searched for it), and the properties of M4990 and M4894 under
another form (M5364, M5365).

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
CLI = "glorfindel/cli.py"
NOTICES = "glorfindel/vm_notices.py"
AZC = "glorfindel/providers/azure/connector.py"
_M = "tests/unit/test_cli_masking.py"
_R = "tests/unit/test_invariant_regressions.py"
_T = "tests/unit/test_drain_closure.py"
_RACES = f"{_R}::test_two_writers_on_one_vm_at_once_end_as_one_after_the_other"

# The writers that take the VM's lock (`_one_writer`), as the connector lists them.
_WRITERS = ("isolate_vm", "release_isolation", "block_suspicious_ip", "unblock_ip", "sweep_vm_rules")


def _writers_line(writers) -> str:
    return "for _name in (" + ", ".join(f'"{w}"' for w in writers) + "):\n"


def _left_out(writer: str) -> str:
    return _writers_line([w for w in _WRITERS if w != writer])


MUTANTS = [
    ("M5361", "the release left out of the VM's lock: a release runs beside an isolation, a reset or another "
     "release of the same VM, call by call (MUT11, M17 for one writer)", AZC,
     _writers_line(_WRITERS), _left_out("release_isolation")),
    ("M5362", "the unblock left out of the VM's lock: it runs beside a block of the same VM (MUT11)", AZC,
     _writers_line(_WRITERS), _left_out("unblock_ip")),
    ("M5363", "the reset left out of the VM's lock: it runs beside an isolation or a release of the same VM "
     "(MUT11)", AZC,
     _writers_line(_WRITERS), _left_out("sweep_vm_rules")),
    ("M5366", "the block left out of the VM's lock: it runs beside an unblock of the same VM (MUT11)", AZC,
     _writers_line(_WRITERS), _left_out("block_suspicious_ip")),
    ("M5367", "the isolation left out of the VM's lock: it runs beside a release or a reset of the same VM "
     "(MUT11)", AZC,
     _writers_line(_WRITERS), _left_out("isolate_vm")),
    ("M5364", "glorfindel pending compares the resolved VM by its group and name only: « restore rg/vm --yes » "
     "copied restores the same group and name of another subscription, asking nothing (MUT11, M4990's "
     "property)", CLI,
     '    if resolved.rstrip("/").lower() != str(resource_id or "").rstrip("/").lower():\n',
     '    if group_and_name(resolved) != group_and_name(str(resource_id or "")):\n'),
    ("M5365", "a closure or an action's announcement said by the webhook too while the bot is alive: posted "
     "twice, in the channel and in the VM's thread (MUT11, M4894's property)", NOTICES,
     '    if notice["via"] == "webhook":\n        post_webhook(webhook or webhook_payload(notice), key)\n',
     '    if notice["via"] == "webhook" or kind in RELAY_KINDS:\n'
     '        post_webhook(webhook or webhook_payload(notice), key)\n'),
]
TESTS = {
    **{mid: _RACES for mid in ("M5361", "M5362", "M5363", "M5366", "M5367")},
    "M5364": f"{_M}::test_pending_never_gives_a_group_and_name_that_take_the_vm_of_another_subscription",
    "M5365": f"{_T}::test_said_outside_the_lock_with_the_bot_alive_the_webhook_keeps_quiet",
}
TESTS_ALSO = {
    "M17": _RACES,
    "M38": f"{_R}::test_a_block_gone_behind_the_quarantine_is_said",
    "M1960": f"{_R}::test_the_machine_refuses_a_rule_kept_unsaid",
}
