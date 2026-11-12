"""BNC3b (#770): the bench in one gesture — the calm and « restore d'abord » verified by the preflight,
the clean point read after the confirmation and taken by the route of the 📸 button, the preflight
replayed. M5040–M5059, measured by tests/unit/test_bench_preflight.py, tests/unit/test_bench_run.py and
tests/unit/test_bench_snapshot.py."""
HIST = "scripts/bench_history.py"
SNAP = "scripts/bench_snapshot.py"
RUN = "scripts/bench_run.py"
PRE = "scripts/bench_preflight.py"
READER = "scripts/bench_h0_reader.py"
_P = "tests/unit/test_bench_preflight.py"
_N = "tests/unit/test_bench_run.py"
_S = "tests/unit/test_bench_snapshot.py"

MUTANTS = [
    ("M5040", "the calm held after 5 minutes, not 10: the VM's start and a previous run still write (BNC3b)",
     HIST, "CALM_S = 600.0\n", "CALM_S = 300.0\n"),
    ("M5041", "a Run Command whose end is not read counts at its start: one still running is taken for calm "
     "(BNC3b)", HIST,
     '    return now if now - op["start"] < RUN_COMMAND_MAX_S else op["start"]\n',
     '    return op["start"]\n'),
    ("M5042", "an activity log cut at its bound read as whole: a ✓ on a read that misses (BNC3b)", HIST,
     "            if len(got) >= MAX_EVENTS:\n",
     "            if len(got) > 10 * MAX_EVENTS:\n"),
    ("M5043", "a run of the current Orodruin left out of « restore d'abord » whatever its technique: the list "
     "filtered on Orodruin's identity, a T1486 without a restore attacked again (BNC3b, Q3b)", HIST,
     '        elif rc["role"] == "orodruin" and technique(rc):\n',
     '        elif rc["role"] == "orodruin":\n'),
    ("M5044", "only the injectors' callers count: a Run Command by hand, by the console or by an unknown caller "
     "left out (BNC3b, « quel que soit l'appelant »)", HIST,
     "        destructive.append(rc)\n",
     '        destructive.append(rc) if rc["role"] in ("orodruin", "h0") else None\n'),
    ("M5045", "Imladris's drain window widened to an hour: any Run Command of Imladris near an isolation left "
     "out (BNC3b, Q3c: [−2 min, +7 min])", HIST,
     '                          and s - DRAIN_BEFORE_S <= rc["start"] <= s + DRAIN_AFTER_S), None)\n',
     '                          and s - DRAIN_BEFORE_S <= rc["start"] <= s + 3600), None)\n'),
    ("M5046", "one isolation answers every Run Command of Imladris in its window: one drain, many commands "
     "(BNC3b)", HIST,
     "            match = next((i for i, s in enumerate(starts) if i not in taken\n",
     "            match = next((i for i, s in enumerate(starts) if True\n"),
    ("M5047", "an isolation not verified answers a drain (BNC3b, §3.1: « un cycle compte s'il est vérifié »)",
     HIST, '        if x.get("source") == "watch" and x.get("verified") is True:\n',
     '        if x.get("source") == "watch":\n'),
    ("M5048", "a VM older than the horizon and never restored read from its creation: runs beyond the 89 days "
     "unseen, a ✓ (BNC3b)", HIST,
     "    if created is not None and now - created <= HORIZON_S:\n",
     "    if created is not None:\n"),
    ("M5049", "a point taken before the VM's last restore kept: the restore would bring back what it undid "
     "(BNC3b, §3.1 criterion 1)", HIST,
     "    if point <= since.end:\n",
     "    if point < since.start - HORIZON_S:\n"),
    ("M5050", "a quarantine whose lift is not read taken for closed: a point taken in it kept (BNC3b, §3.1 "
     "criterion 2)", HIST,
     "        if point >= s and (e is None or point < e):\n",
     "        if e is not None and s <= point < e:\n"),
    ("M5051", "a lift of the console or the bot ends a quarantine whatever its status: a release in part taken "
     "for a release (BNC3b)", HIST,
     '        held = x.get("verified") is True if x.get("source") == "watch" else str(x.get("status") or "") in LIFTED\n',
     "        held = True\n"),
    ("M5052", "the history reader marks the watch's isolations as the console's: their start guessed, no drain "
     "of Imladris ever answered (BNC3b)", READER,
     '                isolations.append({"timestamp": str(doc.get("timestamp") or ""), "source": "watch",\n',
     '                isolations.append({"timestamp": str(doc.get("timestamp") or ""), "source": "console",\n'),
    ("M5053", "the forward may ride a multiplexed master: killing the client leaves the forward open (BNC3b, "
     "« fermé dans tous les cas »)", SNAP,
     '            "-o", "ControlMaster=no", "-o", "ControlPath=none",\n',
     '            "-o", "ServerAliveInterval=60",\n'),
    ("M5054", "the forward left open after the request (BNC3b)", SNAP,
     "    def __exit__(self, *exc) -> bool:\n        self.close()\n",
     "    def __exit__(self, *exc) -> bool:\n        pass\n"),
    ("M5055", "the environment's proxy taken: the console's token carried elsewhere than the loopback (BNC3b)",
     SNAP, "    return urllib.request.build_opener(urllib.request.ProxyHandler({}))\n",
     "    return urllib.request.build_opener()\n"),
    ("M5056", "under FS1, only `not_taken` and `untrusted` stop the run: a request refused or failed goes on "
     "to Orodruin (BNC3b)", SNAP,
     '        if state in FINAL_REFUSALS or state == "expired" or not doc.get("ok") or state != "done":\n',
     '        if state in ("not_taken", "untrusted"):\n'),
    ("M5057", "a job cancelled or completed with warnings taken for a point: only `Failed` stops (BNC3b)", SNAP,
     '        if status and status != "InProgress":\n',
     '        if status == "Failed":\n'),
    ("M5058", "the preflight not replayed after the wait for the point: up to 60 min unchecked before the "
     "attack (BNC3b)", RUN,
     "            if replayed != 0:\n",
     "            if False:\n"),
    ("M5059", "the console's token read in host.env without its guard: a code session would get it (BNC3b)",
     "Makefile", "\t@$(CONSOLE_GUARD) bench-run\n", "\t@true\n"),
]
TESTS = {
    "M5040": f"{_P}::test_the_calm_not_held_is_a_failure_that_says_the_minutes_left",
    "M5041": f"{_P}::test_a_run_command_still_running_breaks_the_calm",
    "M5042": f"{_P}::test_an_activity_log_unread_or_cut_is_never_calm_nor_restored",
    "M5043": f"{_P}::test_a_run_command_since_the_last_restore_asks_for_a_restore_first",
    "M5044": f"{_P}::test_a_run_command_since_the_last_restore_asks_for_a_restore_first",
    "M5045": f"{_P}::test_a_run_command_of_imladris_outside_a_drain_counts",
    "M5046": f"{_P}::test_a_run_command_of_imladris_outside_a_drain_counts",
    "M5047": f"{_P}::test_a_run_command_of_imladris_outside_a_drain_counts",
    "M5048": f"{_P}::test_no_restore_read_within_the_horizon_is_a_failure",
    "M5049": f"{_S}::test_a_point_from_before_the_last_restore_is_refused",
    "M5050": f"{_S}::test_a_point_taken_in_a_quarantine_is_refused",
    "M5051": f"{_S}::test_a_lift_of_the_console_ends_a_quarantine_only_when_it_held",
    "M5052": f"{_P}::test_a_drain_of_imladris_at_a_verified_isolation_is_left_out",
    "M5053": f"{_S}::test_the_forward_is_opened_pinned_without_a_master_and_closed_after",
    "M5054": f"{_S}::test_the_forward_is_opened_pinned_without_a_master_and_closed_after",
    "M5055": f"{_S}::test_no_proxy_is_ever_taken",
    "M5056": f"{_S}::test_under_fs1_each_final_refusal_stops",
    "M5057": f"{_S}::test_a_job_that_fails_stops",
    "M5058": f"{_N}::test_a_red_replayed_preflight_stops_the_run_just_before_the_attack",
    "M5059": f"{_N}::test_the_console_s_token_is_refused_to_a_code_session_by_its_guard",
}
