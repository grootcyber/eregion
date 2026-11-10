"""RST1 (#680): the restore from the console — its rights read before the VM is touched, Azure's
refusal said whole and without an id, no list of LUNs on a restore in place, a job already
finished read with its error. M4654–M4663, measured by tests/unit/test_restore_console.py."""
RESTORE = "glorfindel/providers/azure/restore.py"
RIGHTS = "glorfindel/providers/azure/restore_rights.py"
BACKUP = "glorfindel/providers/azure/backup.py"
_T = "tests/unit/test_restore_console.py"

MUTANTS = [
    ("M4654", "a right the restore needs, read as missing, refuses nothing: the VM neutralized and "
     "deallocated before Azure refuses the trigger (RST1)", RESTORE,
     '        elif rights["missing"]:\n            raise RuntimeError(rights_refusal(rights["missing"]))\n',
     '        elif False:\n            raise RuntimeError(rights_refusal(rights["missing"]))\n'),
    ("M4655", "the staging account's keys left out of what a restore needs: the 09/11 refusal comes "
     "back, after the deallocation (RST1)", RIGHTS,
     '    ("staging", STAGING_LIST_KEYS, "Eregion Glorfindel Restore Staging"),\n',
     ""),
    ("M4656", "a role's notActions ignored: a right it takes back read as held (RST1)", RIGHTS,
     '        and not any(fnmatch.fnmatch(a, str(x).lower()) for x in (p.get("notActions") or []))\n',
     ""),
    ("M4657", "Run Command missing on the VM refuses the restore: a VM outside restore_vms is no "
     "longer restored (SEC17, RST1)", RESTORE,
     '        elif not rights["run_command"]:\n            # SEC17: not a refusal',
     '        elif not rights["run_command"]:\n            raise RuntimeError("Run Command")\n            # SEC17: not a refusal'),
    ("M4658", "the trigger's refusal cut at 300 characters again: the missing action lost, the ids "
     "said (RST1)", RESTORE,
     "                f\"Restore trigger failed — {explain_refusal(r.status_code, r.text)}. Aucun restore \"\n",
     "                f\"Restore trigger failed — {r.status_code}: {r.text[:300]}. Aucun restore \"\n"),
    ("M4659", "Azure's words said with their ids: subscription, object id (RST1)", RIGHTS,
     '    return _GUID.sub("<id>", out)\n',
     "    return str(text or \"\")\n"),
    ("M4660", "restoreDiskLunList sent again on OriginalLocation: the job fails in 4.5 s, code 400625 "
     "(RST1)", RESTORE,
     '                "targetResourceGroupId": None,\n',
     '                "targetResourceGroupId": None,\n'
     '                "restoreDiskLunList": [d.lun for d in (vm.storage_profile.data_disks or [])],\n'),
    ("M4661", "the job search keeps an InProgress job only: a job failed at once reads « not found "
     "after trigger » (RST1)", BACKUP,
     '                if status not in ("InProgress", *FINISHED_JOB_STATUSES):\n',
     '                if status != "InProgress":\n'),
    ("M4662", "a restore job found failed is tracked as running: its error unsaid, the VM left "
     "deallocated (RST1)", RESTORE,
     "        status = getattr(restore_job.properties, \"status\", \"\")\n        if status in FAILED_JOB_STATUSES:\n",
     "        status = getattr(restore_job.properties, \"status\", \"\")\n        if False:\n"),
    ("M4663", "a previous attempt's failed job, minutes before the trigger, taken for this one "
     "(RST1)", BACKUP,
     "                if status != \"InProgress\" and (start is None or start < finished_not_before):\n"
     "                    continue\n",
     ""),
]
TESTS = {
    "M4654": f"{_T}::test_a_missing_right_refuses_the_restore_before_any_write_on_the_vm_and_names_it",
    "M4655": f"{_T}::test_the_staging_account_s_right_names_its_role",
    "M4656": f"{_T}::test_a_right_taken_back_by_notactions_is_missing_a_wildcard_holds",
    "M4657": f"{_T}::test_run_command_missing_on_the_vm_is_no_refusal",
    "M4658": f"{_T}::test_a_linked_refusal_names_the_action_and_the_kind_of_scope_without_an_id",
    "M4659": f"{_T}::test_another_refusal_is_said_whole_its_ids_masked {_T}::test_a_job_s_errors_are_masked",
    "M4660": f"{_T}::test_a_restore_in_place_sends_no_list_of_luns",
    "M4661": f"{_T}::test_a_restore_job_already_failed_is_read_with_its_error "
             f"{_T}::test_a_snapshot_whose_job_fails_at_once_says_so",
    "M4662": f"{_T}::test_a_restore_job_already_failed_is_read_with_its_error",
    "M4663": f"{_T}::test_a_previous_attempt_s_failed_job_is_never_taken_for_this_one",
}
