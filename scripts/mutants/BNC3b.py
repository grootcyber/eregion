"""BNC3b (#770): the bench in one gesture — the calm and « restore d'abord » verified by the preflight,
the clean point read after the confirmation and taken by the route of the 📸 button, the preflight
replayed. M5040–M5059, M5065–M5074 (the review's first round) and M5083–M5087 (its second), measured by tests/unit/test_bench_preflight.py, tests/unit/test_bench_run.py and
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
     '        elif rc["role"] == "orodruin" and id(rc) in held:\n',
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
    # The review's first round: M5065–M5074.
    ("M5065", "a restore whose job's detail does not say « in place » counts as the last restore: a « Restore "
     "disks » made by hand leaves the VM encrypted, and « restore d'abord » says ✓ (BNC3b review)", HIST,
     "        if not said_in_place(detail):\n",
     "        if False:\n"),
    ("M5066", "a restore whose VM's OS disk was not created during the job counts as the last restore: the "
     "VM's disks never swapped (BNC3b review)", HIST,
     "        if not disk_created_during(created, job):\n",
     "        if False:\n"),
    ("M5067", "every restore completed is the last restore, in place or not (BNC3b review, the defect back)", HIST,
     "        if verdict is True:\n",
     "        if True:\n"),
    ("M5068", "no start read and the VM's creation unread: the calm says ✓ (BNC3b review)", HIST,
     "    if started is None:\n        if created is None:\n",
     "    if started is None:\n        if False:\n"),
    ("M5069", "a write on the VM (its creation) is no start for the calm: a VM recreated 3 min ago is calm "
     "(BNC3b review)", HIST,
     '             # its creation, or any write on it: counted as a start, to be prudent (BNC3b review)\n'
     '             "microsoft.compute/virtualmachines/write")\n',
     "             )\n"),
    ("M5070", "the end of the last restore is no start for the calm (BNC3b review)", HIST,
     "    moments = [_last_moment(o, now) for o in starts] + ([restored] if restored is not None else [])\n",
     "    moments = [_last_moment(o, now) for o in starts]\n"),
    ("M5071", "a line of Orodruin's journal answers every Run Command in its window: a T1486 whose journal was "
     "lost borrows the line of a drill before it (BNC3b review, the defect back)", HIST,
     '            match = next((r for r in free if id(r) not in out and at - JOURNAL_AFTER_S <= r["start"] <= at + '
     'JOURNAL_BEFORE_S),\n'
     "                         None)\n"
     "            if match is not None:\n"
     "                out[id(match)] = rid\n",
     "            for r in free:\n"
     '                if at - JOURNAL_AFTER_S <= r["start"] <= at + JOURNAL_BEFORE_S:\n'
     "                    out[id(r)] = rid\n"),
    ("M5072", "an isolation of the console closed by a lift before its own line, after its start taken 10 min "
     "early (BNC3b review)", HIST,
     "        end = next((t for t in lifts if t > line_at), None)\n",
     "        end = next((t for t in lifts if t > s), None)\n"),
    ("M5073", "a line of a cycle file that is not JSON skipped silently: a quarantine cut away unsaid (BNC3b "
     "review)", READER,
     "    if bad:\n",
     "    if False:\n"),
    ("M5074", "`make bench-run-go` called directly takes TARGET or POINT_MAX_H from the environment: its origin "
     "not checked again (BNC3b review: M4758 lost bench-run-go)", "Makefile",
     "bench-run-go:\n\t@$(MOB1_ORIGIN)\n\t@$(CONSOLE_GUARD) bench-run\n",
     "bench-run-go:\n\t@$(CONSOLE_GUARD) bench-run\n"),
    # The review's second round: M5083–M5087.
    ("M5083", "the « Job Type » read without folding its key: Azure's key with a trailing space (measured) not "
     "found, every restore of RST1 refused (BNC3b review round 2)", HIST,
     '    return " ".join(folded.get("job type", "").split())\n',
     '    return str(bag.get("Job Type", ""))\n'),
    ("M5084", "any restore of disks taken for one in place: a « Restore disks » made by hand counts as the last "
     "restore (BNC3b review round 2)", HIST,
     "    return job_type(detail).lower() in IN_PLACE_TYPES\n",
     '    return "disks" in job_type(detail).lower()\n'),
    ("M5085", "the jobs not filtered by their container: the restore of another VM of that name, in another "
     "group, counts for this one (BNC3b review round 2)", HIST,
     "        if container and want and not container.endswith(want):\n",
     "        if False:\n"),
    ("M5086", "any OS disk taken for the restored one, whenever created (BNC3b review round 2: DISK_AFTER_END_S)",
     HIST,
     '    return created is not None and job["start"] < created <= end + DISK_AFTER_END_S\n',
     "    return created is not None\n"),
    ("M5087", "the point the 📸 route took, judged again and found in a quarantine, kept: the attack goes on "
     "(BNC3b review round 2)", RUN,
     "            if not clean:\n",
     "            if False:\n"),
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
    "M5065": f"{_P}::test_a_restore_not_proven_in_place_is_no_last_restore",
    "M5066": f"{_P}::test_a_restore_not_proven_in_place_is_no_last_restore",
    "M5067": f"{_P}::test_a_restore_not_proven_in_place_is_no_last_restore",
    "M5068": f"{_P}::test_no_start_read_and_a_creation_unread_is_never_calm",
    "M5069": f"{_P}::test_a_write_or_a_restore_is_a_start_for_the_calm",
    "M5070": f"{_P}::test_a_write_or_a_restore_is_a_start_for_the_calm",
    "M5071": f"{_P}::test_a_run_of_orodruin_without_its_own_journal_line_is_destructive",
    "M5072": f"{_S}::test_a_lift_before_the_line_of_a_console_isolation_never_closes_it",
    "M5073": f"{_S}::test_a_history_that_reads_in_part_is_no_quarantine_absent",
    "M5074": f"{_N}::test_the_internal_targets_refuse_a_variable_from_the_environment",
    "M5083": f"{_P}::test_a_restore_of_rst1_is_proven_in_place_by_the_measured_job_type",
    "M5084": f"{_P}::test_a_restore_not_proven_in_place_is_no_last_restore",
    "M5085": f"{_P}::test_a_restore_of_another_vm_of_that_name_is_no_restore_of_this_one",
    "M5086": f"{_P}::test_a_restore_not_proven_in_place_is_no_last_restore",
    "M5087": f"{_N}::test_a_point_taken_but_judged_again_not_clean_stops_the_run",
}
