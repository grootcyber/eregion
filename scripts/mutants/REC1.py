"""REC1 (#668): the watch reads on Azure the recovery of a VM it isolated, and lifts it through its
own recovery_complete — only for a restore job that succeeded, after the isolation, whose point
precedes the incident, the VM running; once per job; the guest's word of Run Command read after the
restore, never before. M4615–M4619, measured by tests/unit/test_recovery_watch.py (its targeted tests
and its machine, R1 and R2). After the review (B1, M2, M4), M4628–M4632: a restore in place proven by
the control plane (its type, the VM's OS disk created during the job), the neutralization by the
activity log (the last Run Command before the job a restoring principal's, none of another after),
the job's container, a release running left alone. Round 2 (m1, m2), M4639–M4641: another's command after the
neutralization whatever its status, an activity log past its bound."""
WATCH = "glorfindel/recovery_watch.py"
READ = "glorfindel/providers/azure/recovery.py"
_T = "tests/unit/test_recovery_watch.py"
_MACHINE = f"{_T}::test_never_a_release_without_a_recovery_proven_on_azure"

MUTANTS = [
    ("M4615", "a restore job that failed or was cancelled read as finished: the VM released on a disk "
     "never restored (REC1)", WATCH,
     '    if status.lower() != "completed":\n        return card("failed",',
     '    if False:\n        return card("failed",'),
    ("M4616", "the point restored never compared with the start of the incident: a point taken during "
     "the attack, the attack restored and the VM released (REC1)", WATCH,
     "    if first is None or at is None or at >= first:\n",
     "    if first is None or at is None:\n"),
    ("M4617", "the VM's power state never read: released while it does not run, nothing to prove the "
     "restored disk booted (REC1)", WATCH,
     '    if power != "running":\n',
     "    if False:\n"),
    ("M4618", "the job's record of an emission never read: each pass emits the same recovery again "
     "(REC1)", WATCH,
     '    if done.get("emitted") or done.get("said") in _TERMINAL:\n',
     '    if done.get("said") in _TERMINAL:\n'),
    ("M4619", "Run Command's word from before the restore believed: the old disk's guest could write "
     "the harmless output, the release autonomous on a disk that replays the attacker's command "
     "(REC1)", READ,
     "        if end is None or latest[0] <= end:\n",
     "        if end is None:\n"),
    # The review (B1, M2, M4): a restore in place, the neutralization by the control plane, the
    # container, a release running.
    ("M4628", "a restore elsewhere (« Restore disks », a new VM) read as a recovery of the isolated VM: "
     "released while it keeps the infected disk (REC1, review B1)", WATCH,
     "    if not in_place:\n",
     "    if False:\n"),
    ("M4629", "the neutralization taken from the guest's word alone: an attacker's command printing the "
     "public marker, or root writing it, makes the release autonomous on a reinfected VM (REC1, review B1)",
     WATCH,
     "    cp, cp_why = neutralized_by_the_control_plane(obs, start if start is not None else end, restore_principals())\n",
     '    cp, cp_why = True, ""\n'),
    ("M4630", "any Run Command of a principal that restores before the job enough: an attacker's after the "
     "neutralization, the last one the disk replays, never looked at (REC1, review B1)", WATCH,
     "    if not ours(before[-1]):\n",
     "    if not any(ours(r) for r in before):\n"),
    ("M4631", "a job naming no container read as this VM's on a point found by its time: a homonym's "
     "restore (REC1, review M2)", WATCH,
     '    if not job.get("container_named") and point.get("by") != "id":\n',
     "    if False:\n"),
    ("M4632", "a release running read again by the pass: its recovery_complete emitted beside it (REC1, "
     "review M4)", WATCH,
     ('    if not rid or isolated_at is None or iso.get("releasing_at"):\n',
      '            if not state or state.get("isolated_at") != iso.get("isolated_at") or state.get("releasing_at"):\n'),
     ("    if not rid or isolated_at is None:\n",
      '            if not state or state.get("isolated_at") != iso.get("isolated_at"):\n')),
    # The second review (round 2, m1, m2): a command that never finished, an activity log too long.
    ("M4639", "the activity log's Run Commands kept only when they succeeded: an attacker's command cut "
     "by the deallocation, or failed, after the neutralization — replayed by the restored disk — never "
     "seen (REC1, round 2 m1)", READ,
     "            if op != RUN_COMMAND_OP or rid != want or at is None:\n",
     '            if op != RUN_COMMAND_OP or status != "Succeeded" or rid != want or at is None:\n'),
    ("M4640", "an activity log longer than its bound read as all read: the last command, past the last "
     "page, never seen (REC1, round 2 m2)", READ,
     '        raise RuntimeError(f"journal d\'activité : plus de {ACTIVITY_PAGES} pages, la suite n\'est pas lue")\n',
     "        return events\n"),
    ("M4641", "another's Run Command read only after the job began: one between the neutralization and "
     "the restore, the model's last, never seen (REC1, round 2 m1)", WATCH,
     '    other = next((r for r in runs if _epoch(r["at"]) > neutralized_at and not ours(r)), None)\n',
     '    other = next((r for r in runs if _epoch(r["at"]) >= job_start and not ours(r)), None)\n'),
]
TESTS = {
    "M4615": f"{_T}::test_a_job_that_did_not_succeed_lifts_nothing {_MACHINE}",
    "M4616": f"{_T}::test_a_point_after_the_incident_lifts_nothing_and_says_it_once "
             f"{_T}::test_the_first_detection_before_the_isolation_dates_the_incident {_MACHINE}",
    "M4617": f"{_T}::test_a_stopped_vm_lifts_nothing_says_it_once_then_lifts_once_started {_MACHINE}",
    "M4618": f"{_T}::test_twice_the_same_pass_emits_once_while_the_vm_is_still_isolated {_MACHINE}",
    "M4619": f"{_T}::test_a_word_of_run_command_from_before_the_restore_proves_nothing",
    "M4628": f"{_T}::test_a_restore_elsewhere_lifts_nothing_and_says_the_vm_was_not_restored {_MACHINE}",
    "M4629": f"{_T}::test_a_restore_without_neutralization_whose_attacker_prints_the_marker_lifts_nothing "
             f"{_T}::test_root_rewriting_the_word_after_the_restore_proves_nothing {_MACHINE}",
    "M4630": f"{_T}::test_an_attacker_command_after_the_neutralization_lifts_nothing "
             f"{_T}::test_the_control_plane_reads_who_ran_each_command {_MACHINE}",
    "M4631": f"{_T}::test_a_job_naming_no_container_lifts_only_by_the_id_of_its_point {_MACHINE}",
    "M4632": f"{_T}::test_a_release_running_is_left_to_it",
    "M4639": f"{_T}::test_a_command_of_another_that_never_finished_after_the_neutralization_proves_nothing "
             f"{_MACHINE}",
    "M4640": f"{_T}::test_an_activity_log_longer_than_its_bound_is_unreadable_never_all_read",
    "M4641": f"{_T}::test_a_command_of_another_that_never_finished_after_the_neutralization_proves_nothing "
             f"{_T}::test_the_control_plane_reads_who_ran_each_command {_MACHINE}",
}
