"""DRN1 (#677): the session drain under the quarantine — still running at its first wait, it is
pending, never read as an output; the isolation keeps its NSG verdict; the reassertion's pass reads
its status again on Azure, says « coupure en attente » on one card, closes it once the sessions are
cut, says a cut that never ends (its deadline, or a restart that lost the poller); its cards never
fold into another card of the reassertion; the restore's neutralization still running is never
read as done. M4646–M4649 and M4672–M4675, measured by tests/unit/test_drain_follow.py and the
invariant machine (L4). After the review (round 1), M4715–M4719: the card before the state, the
drain's nonce, the reassertion off, a separator no VM name holds, the poller of a VM released."""
ISO = "glorfindel/providers/azure/isolation.py"
RESTORE = "glorfindel/providers/azure/restore.py"
RUN = "glorfindel/providers/azure/run_command.py"
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
     '        return {**verification, "drain": drain, "drain_case": case}\n',
     "        pass\n"),
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
    # After the review (round 1).
    ("M4715", "the state written before the card: a card refused, the outcome said nowhere and the "
     "pending card closed with a false note (DRN1 review, L1A)", WATCH,
     "    _say_ended(vm, rid, ended, report)\n"
     "    _save_isolation_state(rid, {**state, \"drain\": ended, \"drain_ended_at\": now.isoformat()})\n",
     "    _save_isolation_state(rid, {**state, \"drain\": ended, \"drain_ended_at\": now.isoformat()})\n"
     "    _say_ended(vm, rid, ended, report)\n"),
    ("M4716", "the drain's nonce ignored: another process's isolation (glorfindel respond) said cut from "
     "this watch's poller (DRN1 review)", RUN,
     '        if entry is None or (asked_at is not None and entry.get("asked_at") != asked_at):\n',
     "        if entry is None:\n"),
    ("M4717", "the reassertion off, a pending cut still verified: nothing reads it again, unsaid "
     "(DRN1 review)", POLICY,
     "        if not drain_followed():\n",
     "        if False:\n"),
    ("M4718", "the cut's cards under `reassert-drain-`: the reassertion's card of a VM named drain-web "
     "read as one of them (DRN1 review)", ESC,
     '_DRAIN_FOLLOW = "reassert-drain:"\n',
     '_DRAIN_FOLLOW = "reassert-drain-"\n'),
    ("M4719", "the poller of a VM released kept: read later as another drain's outcome (DRN1 review)",
     WATCH,
     '            if not isinstance(drain, dict) or drain.get("status") != "pending":\n'
     "                drop(rid)\n",
     '            if not isinstance(drain, dict) or drain.get("status") != "pending":\n'
     "                pass\n"),
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
    "M4715": f"{_T}::test_the_card_is_written_before_the_state",
    "M4716": f"{_T}::test_another_process_s_isolation_is_never_read_from_this_poller",
    "M4717": f"{_T}::test_with_the_reassertion_off_a_pending_cut_is_not_verified",
    "M4718": f"{_T}::test_a_vm_named_drain_web_keeps_its_reassertion_card_apart_from_its_cut",
    "M4719": f"{_T}::test_a_released_vm_s_poller_is_dropped",
}
