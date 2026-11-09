"""REC1 (#668): the watch reads on Azure the recovery of a VM it isolated, and lifts it through its
own recovery_complete — only for a restore job that succeeded, after the isolation, whose point
precedes the incident, the VM running; once per job; the neutralization of Run Command read from
what the restored disk said after the restore, never before. M4615–M4619, measured by
tests/unit/test_recovery_watch.py (its targeted tests and its machine, R1 and R2)."""
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
     "    if start is None or at is None or at >= start:\n",
     "    if start is None or at is None:\n"),
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
]
TESTS = {
    "M4615": f"{_T}::test_a_job_that_did_not_succeed_lifts_nothing {_MACHINE}",
    "M4616": f"{_T}::test_a_point_after_the_incident_lifts_nothing_and_says_it_once "
             f"{_T}::test_the_first_detection_before_the_isolation_dates_the_incident {_MACHINE}",
    "M4617": f"{_T}::test_a_stopped_vm_lifts_nothing_says_it_once_then_lifts_once_started {_MACHINE}",
    "M4618": f"{_T}::test_twice_the_same_pass_emits_once_while_the_vm_is_still_isolated {_MACHINE}",
    "M4619": f"{_T}::test_a_word_of_run_command_from_before_the_restore_proves_nothing",
}
