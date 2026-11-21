"""WCH1 (#1019): the watch's loop out of glorfindel/cli.py (glorfindel/watch/), each part reached alone, and a
guard of size on the big files. M7005–M7019: a part of the loop that no longer does what it decides (a
cadence, an order, a guard, a fallback), and the guard that lets a file or a function through. Measured
by tests/unit/test_watch_loop.py and tests/unit/test_file_sizes.py. The 38 mutants that took a text of
`watch()` in glorfindel/cli.py for their anchor moved with it, in the harness and in their lots' files
(TTL1, JUG2b, SEC-B, SEC-F, SEC-Fc)."""
LOOP = "glorfindel/watch/loop.py"
PASSES = "glorfindel/watch/passes.py"
HOUSE = "glorfindel/watch/housekeeping.py"
DISPATCH = "glorfindel/watch/dispatch.py"
RULES = "glorfindel/watch/rules.py"
BEAT = "glorfindel/watch/beat.py"
SIZES = "tests/unit/test_file_sizes.py"
_T = "tests/unit/test_watch_loop.py"
_S = "tests/unit/test_file_sizes.py"

MUTANTS = [
    ("M7005", "the housekeeping stops at the first task that fails: the reassertion and the heartbeat "
     "skipped at every pass, the watch looks dead (WCH1, Q12 back)", LOOP,
     '                _say_failure(self.console, f"watch: {_task.__name__} en erreur", exc, self._output_lock)\n',
     '                _say_failure(self.console, f"watch: {_task.__name__} en erreur", exc, self._output_lock)\n'
     "                return\n"),
    ("M7006", "« Verify » read every minute only, never within ~10 s (WCH1, IR1a)", LOOP,
     "        if self._ttl_check_counter % IDENTITY_EVERY == 0:",
     "        if self._ttl_check_counter % HOUSEKEEPING_EVERY == 0:"),
    ("M7007", "the verdicts proposed before the windows are read: a card judged on last minute's windows "
     "(WCH1, VP1)", LOOP,
     "                hk._observe_windows,\n"
     "                hk._propose_verdicts,   # VP1: after the windows are read, on the cards of the week\n",
     "                hk._propose_verdicts,   # VP1: after the windows are read, on the cards of the week\n"
     "                hk._observe_windows,\n"),
    ("M7008", "a pass still running started again: two reassertions, two relays at once (WCH1)", PASSES,
     "        return t is not None and t.is_alive()\n",
     "        return False\n"),
    ("M7009", "a pass interval that does not read as a number stops the watch at its start (WCH1)", PASSES,
     "    except ValueError:\n        return 60.0\n",
     "    except KeyError:\n        return 60.0\n"),
    ("M7010", "the first recovery pass a full interval after the start: a restore proven meanwhile waits "
     "(WCH1, REC1)", HOUSE,
     "        self._last_recovery = 0.0\n",
     "        self._last_recovery = time.time()\n"),
    ("M7011", "the reassertion started on read-only credentials: every re-application fails (WCH1)", HOUSE,
     '        if self.dry_run or self._reassert_every_s <= 0 or getattr(self.ttl_connector, "read_only", False):\n',
     "        if self.dry_run or self._reassert_every_s <= 0:\n"),
    ("M7012", "a line of runs/ out of a full queue still counts: the VM's channel lines refused for good "
     "(WCH1, SEC8)", DISPATCH,
     "            if _from_channel:\n                self.room._free_line(key)\n",
     "            pass\n"),
    ("M7013", "the rules' poller kept only once discovery started: a failure after it leaves it running "
     "past Ctrl+C (WCH1)", RULES,
     "                self._rule_poller = RulePoller(rules, rule_dispatch, dry_run=dry_run, ip_owners=ip_owners,\n"
     "                                               topology=None if dry_run else _shared_topology())\n"
     "                self._rule_poller.start()\n"
     "                self._start_discovery(_glorfindel_cfg)\n",
     "                poller = RulePoller(rules, rule_dispatch, dry_run=dry_run, ip_owners=ip_owners,\n"
     "                                    topology=None if dry_run else _shared_topology())\n"
     "                poller.start()\n"
     "                self._start_discovery(_glorfindel_cfg)\n"
     "                self._rule_poller = poller\n"),
    ("M7014", "a VM's queue keyed by its id as written: two workers, two decisions of one VM in parallel "
     "(WCH1, real run 2026-10-05 back)", DISPATCH,
     "        key = resource_id.lower()\n",
     "        key = resource_id\n"),
    ("M7015", "the guard of size lets a file over its ceiling through, up to the slack (WCH1)", SIZES,
     "for rel, cap in caps.items() if (n := lines(root / rel)) > cap]",
     "for rel, cap in caps.items() if (n := lines(root / rel)) > cap + SLACK]"),
    ("M7016", "the ratchet asks for no lower ceiling: a file that slimmed may grow back (WCH1)", SIZES,
     "for rel, cap in caps.items() if cap - (n := lines(root / rel)) > slack]",
     "for rel, cap in caps.items() if cap - (n := lines(root / rel)) > cap]"),
    ("M7017", "the function guard reads a module's top level only: a giant method passes (WCH1)", SIZES,
     '            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):\n',
     '            for node in ast.parse(path.read_text(encoding="utf-8")).body:\n'),
    ("M7018", "the watch's key said at every heartbeat, not once until it changes (WCH1, SEC19)", BEAT,
     "        if said != self._key_said:\n",
     "        if True:\n"),
    ("M7019", "Ctrl+C leaves the heartbeat: a fast restart warns of a phantom second watch (WCH1)", LOOP,
     "            self.beat._remove_heartbeat()\n",
     ""),
]
TESTS = {
    "M7005": f"{_T}::test_a_task_that_keeps_failing_never_skips_the_others",
    "M7006": f"{_T}::test_a_tick_reads_runs_says_verify_every_5_polls_and_keeps_house_every_30",
    "M7007": f"{_T}::test_the_windows_are_read_after_the_heartbeat_and_the_verdicts_proposed_after_the_windows",
    "M7008": f"{_T}::test_one_thread_of_a_kind_at_a_time "
             f"{_T}::test_the_notices_relay_never_holds_the_loop_and_runs_one_pass_at_a_time",
    "M7009": f"{_T}::test_a_pass_interval_that_does_not_read_keeps_a_minute",
    "M7010": f"{_T}::test_the_first_recovery_pass_runs_at_the_first_housekeeping_then_every_interval",
    "M7011": f"{_T}::test_the_reassertion_never_starts_where_it_must_not",
    "M7012": f"{_T}::test_a_detection_out_of_a_full_queue_is_said_carded_and_frees_its_line",
    "M7013": f"{_T}::test_the_poller_is_kept_and_stopped_even_when_what_follows_it_fails",
    "M7014": f"{_T}::test_one_worker_per_vm_whatever_the_case_of_its_id",
    "M7015": f"{_S}::test_a_file_one_line_over_its_ceiling_fails",
    "M7016": f"{_S}::test_a_file_that_slimmed_past_the_slack_asks_for_its_ceiling_lowered",
    "M7017": f"{_S}::test_a_method_and_a_nested_function_are_held_too",
    "M7018": f"{_T}::test_the_watch_key_is_said_once_until_what_it_says_changes",
    "M7019": f"{_T}::test_a_bad_iteration_is_said_and_the_loop_goes_on_until_ctrl_c",
}
