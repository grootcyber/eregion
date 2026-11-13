"""SNP1 (#789): the console's snapshot names the vault's job — `vault_job`, `rsv:<vault>/<group>/<name>`,
beside Glorfindel's own record (`job_id`, unchanged), in the direct route's answer and in the watch's receipt
under FS1 — and the bench follows that job, looking for it by its time only without it. M5145–M5149,
measured by tests/unit/test_bench_snapshot.py (the console's real route behind the forward) and
tests/unit/test_action_queue_async.py (the watch's signed receipt, the console's answer)."""
API = "eregion_console/api.py"
WATCH = "glorfindel/queue_watch.py"
SNAP = "scripts/bench_snapshot.py"
_S = "tests/unit/test_bench_snapshot.py"
_Q = "tests/unit/test_action_queue_async.py"

MUTANTS = [
    ("M5145", "the direct route names no vault's job: the bench looks for the job it asked for by its time "
     "again (SNP1)", API,
     '    return {"status": "started", "job_id": job["job_id"], "vault_job": _vault_job(job.get("snap_id")),\n',
     '    return {"status": "started", "job_id": job["job_id"], "vault_job": "",\n'),
    ("M5146", "under FS1, the watch's receipt names no vault's job: the console cannot say it (SNP1)", WATCH,
     '                        "vault_job": vault_job(job.get("snap_id"))}, None, ""\n',
     '                        "vault_job": ""}, None, ""\n'),
    ("M5147", "the console relays the receipt's vault's job unread: a dry run's id, or a shape that is no job "
     "of the vault, said as one (SNP1)", API,
     "        out.update(status=\"started\", job_id=result.get(\"job_id\"), vault_job=vault_job(result.get(\"vault_job\")),\n",
     "        out.update(status=\"started\", job_id=result.get(\"job_id\"), vault_job=result.get(\"vault_job\") or \"\",\n"),
    ("M5148", "a job the console names in another vault than the operator's taken for none: the job of the VM "
     "looked for by its time instead, the point read where it never lands (SNP1)", SNAP,
     "        if not name:\n            raise RuntimeError(\"la console nomme un job qui n'est pas du coffre du poste",
     "        if False:\n            raise RuntimeError(\"la console nomme un job qui n'est pas du coffre du poste"),
    ("M5149", "the bench reads `job_id` alone, never the vault's job the console names: looked for by its time "
     "as before SNP1", SNAP,
     '    asked = given.get("vault_job") or ""\n',
     '    asked = ""\n'),
]
TESTS = {
    "M5145": f"{_S}::test_the_console_names_the_vault_s_job_and_the_bench_follows_it_without_looking_for_it_by_time",
    "M5146": f"{_Q}::test_the_receipt_of_a_snapshot_names_the_vault_s_job_beside_glorfindel_s_record",
    "M5147": f"{_Q}::test_a_receipt_that_names_no_vault_job_is_answered_with_none",
    "M5148": f"{_S}::test_a_vault_job_the_bench_cannot_follow_stops_and_is_never_looked_for_by_its_time",
    "M5149": f"{_S}::test_under_fs1_the_vault_s_job_of_the_receipt_is_followed",
}
