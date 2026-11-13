"""SNP1b (#801): the vault's job the console names is checked before it is followed — at its first `az
backup job show`, a backup of the target (its VM, its operation `Backup`), and an `rsv:` name of another
vault or group than the operator's stops the run, from `vault_job` or `job_id`, saying what differs.
M5245–M5249, measured by tests/unit/test_bench_snapshot.py (`bench_snapshot.take`, `az_json` and the
clock faked)."""
SNAP = "scripts/bench_snapshot.py"
_S = "tests/unit/test_bench_snapshot.py"

MUTANTS = [
    ("M5245", "the named job's VM never compared: another VM's backup followed to Completed, the target's "
     "point read where none was taken (SNP1b)", SNAP,
     "    if vm and vm.lower() != target.lower():\n",
     "    if False:\n"),
    ("M5246", "the named job's operation never compared: a restore or a configuration followed to Completed "
     "as a backup (SNP1b)", SNAP,
     '    if op and op != "Backup":\n',
     "    if False:\n"),
    ("M5247", "a named job whose VM does not read taken for the target's: nothing contradicts it, nothing "
     "proves it (SNP1b)", SNAP,
     '    if not vm:\n        out.append("sa VM ne se lit pas")\n',
     '    if False:\n        out.append("sa VM ne se lit pas")\n'),
    ("M5248", "an `rsv:` name of another vault given by `job_id` replaced, in silence, by the job looked for "
     "by its time (SNP1b)", SNAP,
     '    if not asked and str(given.get("job_id") or "").lower().startswith("rsv:"):\n',
     "    if False:\n"),
    ("M5249", "the stop says the vault and the group both, whatever differs: the operator looks in the wrong "
     "place (SNP1b)", SNAP,
     '             if got.lower() != str(want or "").lower()]\n',
     "             if True]\n"),
    # SNP1b, review round 1: the check at the first show, the read in error read again, the namesake
    ("M5265", "the named job checked only once it is Completed: another VM's job followed up to 60 min "
     "before the stop (SNP1b review)", SNAP,
     "            if why:\n",
     '            if why and status == "Completed":\n'),
    ("M5266", "a read of the job in error never read again: one passing error of `az` stops the run (SNP1b "
     "review)", SNAP,
     "            if failures >= JOB_READ_FAILURES:\n",
     "            if failures >= 1:\n"),
    ("M5267", "the errors of the job's reads counted across the good ones: errors far apart stop the run as "
     "if in a row (SNP1b review)", SNAP,
     "            failures = 0\n",
     "            pass\n"),
    ("M5268", "the job's container never compared: a namesake of another group, deleted, its backup left in "
     "the vault, followed as the target's (SNP1b review)", SNAP,
     "    if container and vm_rg and not container.endswith(",
     "    if False and not container.endswith("),
    ("M5269", "a named job whose operation does not read taken for a backup: nothing contradicts it, nothing "
     "proves it (SNP1b review)", SNAP,
     '    if not op:\n        out.append("son opération ne se lit pas")\n',
     '    if False:\n        out.append("son opération ne se lit pas")\n'),
]
TESTS = {
    "M5245": f"{_S}::test_a_named_job_of_another_vm_or_operation_stops_at_its_first_show_and_is_never_followed",
    "M5246": f"{_S}::test_a_named_job_of_another_vm_or_operation_stops_at_its_first_show_and_is_never_followed",
    "M5247": f"{_S}::test_a_named_job_whose_vm_or_operation_does_not_read_stops",
    "M5248": f"{_S}::test_a_rsv_name_of_another_vault_or_group_stops_whether_named_by_vault_job_or_job_id",
    "M5249": f"{_S}::test_a_rsv_name_of_another_vault_or_group_stops_whether_named_by_vault_job_or_job_id",
    "M5265": f"{_S}::test_a_named_job_of_another_vm_or_operation_stops_at_its_first_show_and_is_never_followed",
    "M5266": f"{_S}::test_a_read_in_error_is_read_again_and_the_job_followed_to_completed",
    "M5267": f"{_S}::test_a_read_in_error_is_read_again_and_the_job_followed_to_completed",
    "M5268": f"{_S}::test_a_namesake_of_another_group_whose_backup_stayed_in_the_vault_stops",
    "M5269": f"{_S}::test_a_named_job_whose_vm_or_operation_does_not_read_stops",
}
