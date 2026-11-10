"""REC1b (#679): the neutralization decided by the control plane alone. The instance view never
carries Run Command v1 (measured 09/11): the guest's word is information, its absence holds nothing,
present and contrary it holds the release; a Run Command the platform refused (Failed, Conflict,
OperationNotAllowed: on a deallocated VM, it never reached the guest) is none, whoever tried it —
any other failure of another principal still holds (REC1's rule m1), a code that can't be read too.
M4650–M4653, measured by tests/unit/test_recovery_watch.py (its targeted tests and its machine)."""
WATCH = "glorfindel/recovery_watch.py"
READ = "glorfindel/providers/azure/recovery.py"
_T = "tests/unit/test_recovery_watch.py"
_MACHINE = f"{_T}::test_never_a_release_without_a_recovery_proven_on_azure"

MUTANTS = [
    ("M4650", "any failed Run Command read as a refusal of the platform: an attacker's command after the "
     "neutralization that failed once it reached the guest, its settings in the VM model, never holds "
     "the release (REC1b)", READ,
     '    return _fold(status) == _REFUSED_STATUS and _error_code(props.get("statusMessage")) == _REFUSED_CODE\n',
     "    return True\n"),
    ("M4651", "the guest's word, present and contrary to the control plane, never read: a restored disk "
     "that says another command ran released all the same (REC1b)", WATCH,
     '    if cp is True and word.get("neutralized") is False:\n',
     "    if False:\n"),
    ("M4652", "the guest's word required again: on the bench the instance view never carries Run Command "
     "v1, every release held, the loop never closed by the restore alone (REC1b)", WATCH,
     "    neutralized = cp\n",
     '    neutralized = None if cp is True and word.get("neutralized") is None else cp\n'),
    ("M4653", "the Started of a refused operation taken with it whoever logged it: another principal's "
     "command, cut by the deallocation, hidden behind a refusal of the same operation id (REC1b)", READ,
     '        if all(_refused(e) or (_status(e) == "started" and _callers(e) == by and _utc(e.get("eventTimestamp")) <= until)\n',
     '        if all(_refused(e) or (_status(e) == "started" and _utc(e.get("eventTimestamp")) <= until)\n'),
]
TESTS = {
    "M4650": f"{_T}::test_another_failure_of_another_principal_holds_the_release "
             f"{_T}::test_a_refusal_is_read_where_the_activity_log_carries_it {_MACHINE}",
    "M4651": f"{_T}::test_the_word_of_the_guest_present_and_contrary_holds_the_release {_MACHINE}",
    "M4652": f"{_T}::test_a_view_without_run_command_and_a_control_plane_proof_lifts_once "
             f"{_T}::test_the_bench_of_09_11_lifts_with_the_restore_alone",
    "M4653": f"{_T}::test_a_refusal_is_read_where_the_activity_log_carries_it",
}
