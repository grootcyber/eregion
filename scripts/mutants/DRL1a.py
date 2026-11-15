"""DRL1a (#613): the drill of the week on Orodruin's side — its timer, its arming, its guards
(docs/design/drill-banc.md §9, the mutants of DRL1a, none dropped). M5406–M5425 and M5466–M5470.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids),
optionally TESTS_ALSO and CONTROL; its paths as plain strings.
"""
SD = "eregion_core/scheduled_drill.py"
RUNNER = "eregion_core/exercise_runner.py"
DRILL = "eregion_core/drill.py"
EXERCISE = "eregion_core/exercise.py"
ARMING = "eregion_core/drill_arming.py"
ORODRUIN = "eregion_core/orodruin.py"
OPS = "infra/orodruin/drill_ops.py"
AGENT = "glorfindel/agent.py"
T = "tests/unit/test_scheduled_drill.py::"
OPS_T = "tests/unit/test_drill_ops.py::"
X = "tests/unit/test_drill_expectations.py::"

MUTANTS = [
    # 1
    ("M5406", "the drill's fingerprint never compared with the arming's: a drill changed by a release plays "
     "without a re-arming (DRL1a)", SD,
     '        if sha != armed["sha256"]:\n',
     "        if False:\n"),
    # 2
    ("M5407", "the zone production admitted at the runner's first judgment: zones not passed to judge (DRL1a)",
     RUNNER,
     "scope=self.scope, zones=self.zones,\n",
     "scope=self.scope,\n"),
    # 3
    ("M5408", "the zone production admitted at the recheck before each wire: zones ignored in _recheck (DRL1a)",
     RUNNER,
     "                  else load_catalog(), watch_refusal=\"\", fault_targets=faults, scope=self.scope,\n"
     "                  zones=self.zones)\n",
     "                  else load_catalog(), watch_refusal=\"\", fault_targets=faults, scope=self.scope)\n"),
    # 4
    ("M5409", "a destructive technique admitted as a scheduled drill's wire (DRL1a)", DRILL,
     "    if experiment.destructive is not False:\n",
     "    if False:\n"),
    # 5
    ("M5410", "off_schedule skipped: a start of the service by hand, any hour, plays (DRL1a)", SD,
     "        if (now - self.planned).total_seconds() > WINDOW_S:\n",
     "        if False:\n"),
    # 6
    ("M5411", "the registry of the occurrences read before the lock: two occurrences side by side both "
     "read it empty (DRL1a)", SD,
     "        stack = contextlib.ExitStack()\n"
     "        try:\n"
     "            fd = stack.enter_context(self.lock(f\"drill {drill.name}\"))\n"
     "        except er.Busy as e:\n"
     "            return self._end(\"refused\", \"busy\", str(e))\n"
     "        with stack:\n"
     "            return self._locked(fd)\n"
     "\n"
     "    def _locked(self, fd: int) -> dict:\n"
     "        last, why = self._last_played()\n",
     "        early = self._last_played()\n"
     "        stack = contextlib.ExitStack()\n"
     "        try:\n"
     "            fd = stack.enter_context(self.lock(f\"drill {drill.name}\"))\n"
     "        except er.Busy as e:\n"
     "            return self._end(\"refused\", \"busy\", str(e))\n"
     "        with stack:\n"
     "            return self._locked(fd, early)\n"
     "\n"
     "    def _locked(self, fd: int, early=None) -> dict:\n"
     "        last, why = early\n"),
    # 7
    ("M5412", "the registry written before off_schedule: a start by hand spends the week (DRL1a)", SD,
     "        self.planned = drill.schedule.occurrence(now)\n",
     "        self.planned = drill.schedule.occurrence(now)\n        self._mark_played()\n"),
    # 8
    ("M5413", "the lock's descriptor not handed to the runner: busy at every occurrence (DRL1a)", SD,
     "        os.environ[er.LOCK_FD_ENV] = str(fd)   # the runner holds this very lock: never Busy\n",
     "        pass\n"),
    # 9
    ("M5414", "a permit absent taken for an arming: an absence that opens (DRL1a)", SD,
     '            return "no_permit", "no permit in the channel: removed by a kill or a disarming, or expired — re-arm"\n',
     '            return "", ""\n'),
    # 10
    ("M5415", "a permit that is not the local arming's admitted (DRL1a)", SD,
     "        if permit != da.permit_of(self.armed):\n",
     "        if False:\n"),
    # 11
    ("M5416", "the permit rewritten without If-Match: a permit the kill removed is recreated (DRL1a)", SD,
     "xc.publish_drill(xc.PERMIT_BLOB, doc, if_match=etag))\n",
     "xc.publish_drill(xc.PERMIT_BLOB, doc))\n"),
    # 12
    ("M5417", "the kill leaves the scheduled start active: it says it, never disables it (DRL1a)", OPS,
     "        set_autostart(logic_id, False, run)\n        said[\"disable_start\"] = \"scheduled start disabled\"\n",
     "        said[\"disable_start\"] = \"scheduled start disabled\"\n"),
    # 13
    ("M5418", "the kill leaves the permit in the channel (DRL1a)", OPS,
     "        gone = xc.delete_drill(xc.PERMIT_BLOB, channel=channel, credential=cred(), delete=delete)\n",
     "        gone = False\n"),
    # 14
    ("M5419", "the kill leaves drill.json armed: Imladris would raise not_run (DRL1a)", OPS,
     "        write_pulse(disarmed_pulse(\"killed\", channel=channel, credential=c, get=get, now=now),\n"
     "                    channel=channel, credential=c, put=put)\n",
     ""),
    # 15
    ("M5420", "the target started before the journal (before_call) says it (DRL1a)", SD,
     "            session.before_call(\"start_vm\", rid, f\"drill {self.drill.name}: its target was "
     "{state or 'not running'}\")\n",
     "            self.start(rid)\n"
     "            session.before_call(\"start_vm\", rid, f\"drill {self.drill.name}: its target was "
     "{state or 'not running'}\")\n"),
    # 16
    ("M5421", "the start not counted in the cap handed to the runner (DRL1a)", SD,
     "            self.start_calls += 1\n",
     "            pass\n"),
    # 17
    ("M5422", "an occurrence missed caught up at the next boot: the timer Persistent (DRL1a)", OPS,
     '        "Persistent=false\\n"\n',
     '        "Persistent=true\\n"\n'),
    # 18
    ("M5423", "scheduled_drill reads the expectations: Orodruin knows what the watch should see (DRL1a)", SD,
     "from eregion_core import orodruin, runs_layout, watch_gate\n",
     "from eregion_core import orodruin, runs_layout, watch_gate\nfrom eregion_core import expectations  # noqa: F401\n"),
    # 19
    ("M5424", "the expectations written into the request's status: its drill names the rule awaited (DRL1a)", SD,
     '        info = {"name": self.drill.name, "sha256": self.sha, "occurrence": self.planned.isoformat()}\n',
     '        info = {"name": self.drill.name, "sha256": self.sha, "occurrence": self.planned.isoformat(),\n'
     '                "rule": "t1136-001-local-account-creation-linux-v1"}\n'),
    # 20
    ("M5425", "_build_user_message() sees the drill: its pulse in the message (DRL1a)", AGENT,
     "    lines.append(json.dumps(signal, indent=2, default=str))\n",
     "    lines.append(json.dumps(signal, indent=2, default=str))\n"
     "    if os.path.exists(\"runs/orodruin/drill.json\"):\n"
     "        lines.append(Path(\"runs/orodruin/drill.json\").read_text())\n"),
    # 21
    ("M5466", "all admitted as an armed drill's target: a VM enrolled later becomes one without a gesture "
     "(DRL1a)", ARMING,
     '        if not isinstance(n, str) or not _VM_NAME.fullmatch(n) or n.lower() == "all":\n',
     "        if not isinstance(n, str) or not _VM_NAME.fullmatch(n):\n"),
    # 22
    ("M5467", "the SIGTERM handler raises while a wire is awaited: the wire killed, its window open (DRL1a)", SD,
     "            self._relay(child)\n            return\n        if self._launching or not first:\n",
     "            self._relay(child)\n        if self._launching:\n"),
    # 23
    ("M5468", "a wire's window opened for MAX_DURATION_S, not its time left (DRL1a)", EXERCISE,
     "    return float(min(int(raw) + WIRE_MARGIN_S, MAX_DURATION_S))\n",
     "    return float(MAX_DURATION_S)\n"),
    # After the review (round 1): the kill's order, and Terraform's state unreadable taken for absent.
    ("M5469", "the kill disables the scheduled start after the VM is stopped, not right after the "
     "revocation (DRL1a)", ORODRUIN,
     '        if name == "cancel":   # DRL1: right after the revocation, before the VM is stopped\n',
     '        if name == "close":   # DRL1: right after the revocation, before the VM is stopped\n'),
    ("M5470", "Terraform's state unreadable taken for « no scheduled start »: the kill succeeds, the Logic "
     "App stays enabled (DRL1a)", "Makefile",
     "autostart-id 2>/dev/null || echo unreadable))\n",
     "autostart-id 2>/dev/null || echo))\n"),
]
TESTS = {
    "M5406": T + "test_a_drill_whose_fingerprint_changed_is_refused_until_re_armed",
    "M5407": T + "test_a_target_in_production_is_not_bench_though_the_production_rule_would_admit_it",
    "M5408": T + "test_the_runners_recheck_holds_its_zones_before_each_wire",
    "M5409": T + "test_a_scheduled_drill_plays_a_public_non_destructive_technique_on_the_bench_alone",
    "M5410": T + "test_a_start_off_its_hour_plays_nothing_and_writes_nothing_before",
    "M5411": T + "test_the_registry_is_read_once_the_lock_is_held_never_before",
    "M5412": T + "test_a_start_off_its_hour_plays_nothing_and_writes_nothing_before",
    "M5413": T + "test_the_wire_runs_under_the_occurrences_lock_never_busy",
    "M5414": T + "test_no_permit_in_the_channel_closes",
    "M5415": T + "test_a_permit_that_is_not_the_armings_is_refused",
    "M5416": T + "test_the_permit_is_rewritten_by_default_only_over_the_blob_read",
    "M5417": OPS_T + "test_the_kills_drill_steps_disable_the_start_remove_the_permit_and_write_disarmed_killed",
    "M5418": OPS_T + "test_the_kills_drill_steps_disable_the_start_remove_the_permit_and_write_disarmed_killed",
    "M5419": OPS_T + "test_the_kills_drill_steps_disable_the_start_remove_the_permit_and_write_disarmed_killed",
    "M5420": T + "test_an_occurrence_starts_its_target_journaled_first_then_plays_and_says_it",
    "M5421": T + "test_the_start_is_counted_in_the_cap_the_runner_is_given",
    "M5422": OPS_T + "test_the_arming_writes_the_arming_the_units_the_timer_then_the_permit_the_start_and_the_pulse",
    "M5423": X + "test_orodruins_drill_and_runner_never_import_the_expectations_reader",
    "M5424": T + "test_the_request_status_carries_the_drill_and_its_reader_takes_it",
    "M5425": "tests/unit/test_dagorlad_blind.py::"
             "test_the_drill_of_the_week_present_changes_nothing_glorfindel_tells_the_model",
    "M5466": T + "test_an_arming_names_its_vms_never_all",
    "M5467": T + "test_sigterm_during_a_wire_is_relayed_awaited_and_the_occurrence_is_stopped",
    "M5468": T + "test_a_window_of_a_wire_is_bounded_by_the_time_its_runner_left_it",
    "M5469": OPS_T + "test_the_kill_revokes_then_disables_the_start_removes_the_permit_then_stops_and_says_disarmed",
    "M5470": OPS_T + "test_the_kill_reads_the_scheduled_start_in_three_cases_never_an_unreadable_state_for_none",
}
