"""DRN1 (#677): the session drain under the quarantine — still running at its first wait, it is
pending, never read as an output; the isolation keeps its NSG verdict; the reassertion's pass reads
its status again on Azure, says « coupure en attente » on one card, closes it once the sessions are
cut, says a cut that never ends (its deadline, or a restart that lost the poller); its cards never
fold into another card of the reassertion; the restore's neutralization still running is never
read as done. M4646–M4649 and M4672–M4675, measured by tests/unit/test_drain_follow.py and the
invariant machine (L4)."""
ISO = "glorfindel/providers/azure/isolation.py"
RESTORE = "glorfindel/providers/azure/restore.py"
POLICY = "glorfindel/response/policy.py"
WATCH = "glorfindel/drain_watch.py"
ESC = "glorfindel/escalations.py"
_T = "tests/unit/test_drain_follow.py"
_MACHINE = "tests/unit/test_invariants.py::test_isolation_invariants"

MUTANTS = [
    ("M4646", "a drain still running at its first wait read as done: the last poll's empty output, "
     "« sortie de Run Command illisible », the isolation unverified (DRN1, bench 09/11)", ISO,
     "            if not done:\n"
     "                return run_command.pending(resource_id, poller, asked, run_command.DRAIN_FIRST_WAIT_S)\n",
     ""),
    ("M4647", "a drain pending read as sessions left open: the isolation unverified while the NSG holds "
     "and the cut runs (DRN1)", POLICY,
     '    if verification.get("verified") is True and case == "pending":\n'
     '        return {**verification, "drain": drain, "drain_case": case}\n',
     ""),
    ("M4648", "a drain still running on Azure said on no card: the sessions perhaps open, unsaid (DRN1)",
     WATCH,
     '    sid = drain_sid(vm, rid)\n    if any(e.get("escalation_type") == PENDING_TYPE for e in _cards(sid)):\n',
     '    sid = drain_sid(vm, rid)\n    if True:\n'),
    ("M4649", "a cut that ended leaves its « coupure en attente » card open: the isolation verified, "
     "the card still says it waits (DRN1)", WATCH,
     "        for e in waiting:\n            escalations.resolve(e[\"id\"], note=note)\n",
     "        pass\n"),
    ("M4672", "a drain's deadline never reached: a cut that never ends said waiting for ever (DRN1)",
     WATCH,
     "        if elapsed is None or elapsed < DRAIN_DEADLINE_S:\n",
     "        if True:\n"),
    ("M4673", "a drain the watch no longer follows (a restart) read as a cut: sessions perhaps open, "
     "said cut (DRN1)", WATCH,
     '        ended = {**drain, "status": "failed", "never": True,\n'
     '                 "error": ("statut non relu',
     '        ended = {**drain, "status": "drained",\n'
     '                 "error": ("statut non relu'),
    ("M4674", "the drain's card folded into another card of the reassertion on the VM: one reason "
     "written over the other (DRN1)", ESC,
     '                and _drain_follow(e.get("signal_id")) == _drain_follow(signal_id)\n',
     ""),
    ("M4675", "the restore's harmless command still running at its deadline read as neutralized: the "
     "restored disk may replay the attacker's command, the release not held (DRN1, T13)", RESTORE,
     "            if not done:\n                return self._neutralize_pending(poller)\n",
     ""),
]
TESTS = {
    "M4646": f"{_T}::test_the_worker_waits_for_the_drain_what_it_waited_before "
             f"{_T}::test_a_cut_that_ends_after_its_first_wait_gives_a_verified_isolation",
    "M4647": f"{_T}::test_a_cut_that_ends_after_its_first_wait_gives_a_verified_isolation",
    "M4648": f"{_T}::test_a_cut_that_ends_after_its_first_wait_gives_a_verified_isolation {_MACHINE}",
    "M4649": f"{_T}::test_a_cut_that_ends_after_its_first_wait_gives_a_verified_isolation",
    "M4672": f"{_T}::test_a_cut_that_never_ends_is_said_so",
    "M4673": f"{_T}::test_the_watch_restarted_during_the_cut_says_it_was_not_read",
    "M4674": f"{_T}::test_the_drain_card_never_folds_into_another_card_of_the_reassertion",
    "M4675": f"{_T}::test_the_neutralization_still_running_reads_its_status_on_azure",
}
