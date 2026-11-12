"""BNC3a (#753): the bench's report composed after the run's cycle and after the lift — `make bench-run`
waits for the run's cycle on Imladris, `make bench-restore` follows the lift, both in reading and
bounded; the vault's jobs of the day read. M4880–M4889, measured by tests/unit/test_bench_report.py,
tests/unit/test_bench_run.py and tests/unit/test_bench_restore.py."""
REPORT = "scripts/bench_report.py"
RUN = "scripts/bench_run.py"
RESTORE = "scripts/bench_restore.py"
_R = "tests/unit/test_bench_report.py"
_N = "tests/unit/test_bench_run.py"
_S = "tests/unit/test_bench_restore.py"

MUTANTS = [
    ("M4880", "the vault's jobs read up to today's date: the day's jobs left out, yesterday's night backup "
     "taken for the morning's clean point (BNC3a, the defect of 12/11 back)", REPORT,
     '    return (now.astimezone(timezone.utc) + timedelta(days=1)).strftime("%d-%m-%Y")\n',
     '    return now.astimezone(timezone.utc).strftime("%d-%m-%Y")\n'),
    ("M4881", "`make bench-run` composes its report at once, before the run's cycle is written (BNC3a, the "
     "defect of 12/11 back)", RUN,
     '        return bench_report.main(["--run", run_id, "--target", target, "--wait", "cycle"], self.env)\n',
     '        return bench_report.main(["--run", run_id, "--target", target], self.env)\n'),
    ("M4882", "the wait for the cycle ends on the run's report alone: composed before the watch closes its "
     "cycle (BNC3a)", REPORT,
     '    return not _detected(run) or any(c.get("kind") == "run" for c in h0.get("cycles") or [])\n',
     "    return True\n"),
    ("M4883", "the lift followed for an hour, not thirty minutes (BNC3a: the bound of 12/11)", REPORT,
     "LIFT_WAIT_S = 1800.0\n",
     "LIFT_WAIT_S = 3600.0\n"),
    ("M4884", "a report composed before the run's cycle says « une action retenue, ou une recommandation » — "
     "false, the VM was isolated (BNC3a, the defect of 12/11 back)", REPORT,
     "        elif _detected(run):\n",
     "        elif False:\n"),
    ("M4885", "`make bench-restore` composes no report after the restore: the operator types `make "
     "bench-report` himself (BNC3a)", RESTORE,
     "    if steps.report(report_run, target) != 0:\n",
     "    if False:\n"),
    ("M4886", "`make bench-restore`'s report composed at once, without following the lift (BNC3a)", RESTORE,
     '        return bench_report.main(["--run", run_id, "--target", target, "--wait", "lift"], self.env)\n',
     '        return bench_report.main(["--run", run_id, "--target", target], self.env)\n'),
    ("M4887", "a lift held because the VM does not run (`stopped`) ends the wait: the watch reads again and "
     "releases once it runs, the report composed before (BNC3a)", REPORT,
     '            or any(h.get("kind") != "stopped" for h in h0.get("holds") or []))\n',
     '            or bool(h0.get("holds")))\n'),
    ("M4888", "`bench-restore-go` without Imladris's ssh: the report after the lift reads nothing (BNC3a)",
     "Makefile",
     "bench-run-go bench-restore-go: export BENCH_H0_SSH = $(HOST_SSH)\n",
     "bench-run-go: export BENCH_H0_SSH = $(HOST_SSH)\n"),
    ("M4889", "one failed read of Imladris ends the wait: the report composed on the view before, the cycle "
     "or the lift missed (BNC3a)", REPORT,
     "        except RuntimeError:\n"
     "            failed += 1\n"
     "            continue\n",
     "        except RuntimeError:\n"
     "            failed += 1\n"
     "            break\n"),
]
TESTS = {
    "M4880": f"{_R}::test_the_vault_s_jobs_of_the_day_are_read",
    "M4881": f"{_N}::test_the_report_waits_for_the_run_s_cycle",
    "M4882": f"{_R}::test_bench_run_s_report_waits_for_the_run_s_cycle_then_reads_azure",
    "M4883": f"{_R}::test_the_wait_for_the_lift_is_bounded_at_thirty_minutes",
    "M4884": f"{_R}::test_a_report_composed_before_the_run_s_cycle_says_it_is_not_yet_written",
    "M4885": f"{_S}::test_the_restore_done_the_report_follows_the_lift_of_the_run",
    "M4886": f"{_S}::test_the_report_waits_for_the_lift_under_the_operator_s_environment",
    "M4887": f"{_R}::test_a_lift_held_by_the_watch_ends_the_wait_and_is_said",
    "M4888": f"{_N}::test_bench_restore_is_given_imladris_s_ssh_for_its_report",
    "M4889": f"{_R}::test_await_reads_again_until_ready_and_keeps_the_view_before_a_failed_read",
}
