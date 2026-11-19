"""DRL1e (part of #613): the follow-ups of DRL1c's and DRL1d's reviews — the scheduled start's state
said by `orodruin-drill-check` against the arming, the arming that guards Orodruin's shutdown of
23:00 UTC, the search for an apply enabling the scheduled start in every .tf of the module, and the
Makefile's run defs read up to the image (docs/design/drill-banc.md §16). M6481–M6490. Measured by
tests/unit/test_drill_ops.py and tests/unit/test_drill_autostart.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids);
its paths as plain strings.
"""
OPS = "infra/orodruin/drill_ops.py"
MK = "Makefile"
TOPS = "tests/unit/test_drill_ops.py"
TAUTO = "tests/unit/test_drill_autostart.py"
T = TOPS + "::"
A = TAUTO + "::"

_DISABLED = T + "test_the_check_says_armed_but_scheduled_start_disabled_re_arm"
_UNREAD = T + "test_an_unreadable_state_against_the_arming_is_said_never_taken_for_enabled"
_REFUSED = T + "test_the_arming_of_a_drill_that_overruns_23_utc_is_refused_and_writes_nothing"
_GUARD = T + "test_the_shutdown_guard_refuses_a_certain_cut_and_warns_at_the_limit"
_AFTER = T + "test_an_option_after_the_env_file_or_the_mounts_is_read_never_missed"
_PARITY = T + "test_the_drills_service_runs_with_the_options_of_annatars_runs_no_more_no_less"
_READS = T + "test_the_drills_reads_that_play_no_run_get_nothing_more_than_the_hardening"
_NO_APPLY = A + "test_no_apply_enables_the_scheduled_start"
_ANY_FILE = A + "test_an_apply_enabling_the_scheduled_start_from_any_file_of_the_module_fails_the_test"

MUTANTS = [
    ("M6481", "the check no longer reads the scheduled start's state: an armed drill whose Logic App an "
     "apply put back Disabled says « ✓ scheduled start », the occurrence missed silently (DRL1e)", OPS,
     "    state = autostart_state(wf)\n", '    state = "Enabled"\n'),
    ("M6482", "the check says the scheduled start's state without the arming: armed and Disabled passes "
     "(DRL1e)", OPS,
     "    state_ok, line = state_line(state, armed_here, unread, why)\n",
     "    state_ok, line = state_line(state, False, unread, why)\n"),
    ("M6483", "the arming's guard of the 23:00 UTC shutdown removed: a drill Orodruin's shutdown would cut "
     "is armed (DRL1e)", OPS,
     '    verdict, said = shutdown_guard(schedule)\n    if verdict == "refuse":\n        say(f"✗ {said} — nothing armed")',
     '    verdict, said = "", ""\n    if verdict == "refuse":\n        say(f"✗ {said} — nothing armed")'),
    ("M6484", "the guard counts the drill's hour, not its max_run_s: a drill whose budget runs past 23:00 "
     "UTC only warned (DRL1e)", OPS,
     "at - LEAD_MIN * 60, at + schedule.max_run_s, at + SERVICE_BOUND_S", "at - LEAD_MIN * 60, at, at + SERVICE_BOUND_S"),
    ("M6485", "the search for an apply enabling the scheduled start limited again to drill_autostart.tf: a "
     "local-exec from main.tf passes (DRL1e)", TAUTO,
     'for p in sorted(where.glob("*.tf"))}', 'for p in sorted(where.glob("drill_autostart.tf"))}'),
    ("M6486", "the search no longer looks for the Logic App named outside drill_autostart.tf: an external "
     "data source enabling it by az logic passes (DRL1e)", TAUTO,
     '        if name != "drill_autostart.tf":\n            for line in code.splitlines():',
     '        if False:\n            for line in code.splitlines():'),
    ("M6487", "the Makefile's run defs read again only up to --env-file: an option posed after it passes "
     "(DRL1e)", TOPS,
     '.split(" $(ORO_IMAGE)", 1)[0]\n    seg = re.sub(', '.split(" --env-file", 1)[0]\n    seg = re.sub('),
    ("M6488", "an option more on Annatar's runs, posed after --env-file in ORO_RUN: the drill diverges from "
     "the run by hand (DRL1e)", MK,
     "$(ORO_EXEC_HOME) --env-file orodruin.env $(call ORO_MOUNT,annatar) $(call ORO_MOUNT,orodruin) $(ORO_IMAGE)",
     "$(ORO_EXEC_HOME) --env-file orodruin.env --privileged $(call ORO_MOUNT,annatar) $(call ORO_MOUNT,orodruin) "
     "$(ORO_IMAGE)"),
    ("M6489", "the drill's reads given the exec tmpfs after --env-file in ORO_DRILL_RUN (DRL1e)", MK,
     "ORO_DRILL_RUN  = docker run --rm $(ORO_HARDEN) --env-file orodruin.env --pull never",
     "ORO_DRILL_RUN  = docker run --rm $(ORO_HARDEN) --env-file orodruin.env $(ORO_EXEC_HOME) --pull never"),
    ("M6490", "an unreadable state taken for enabled: armed, the Logic App unread, the check passes (DRL1e)",
     OPS, '        if state == "Enabled":\n            return True, "✓ scheduled start enabled',
     '        if state in ("Enabled", ""):\n            return True, "✓ scheduled start enabled'),
]

TESTS = {
    "M6481": _DISABLED,
    "M6482": _DISABLED,
    "M6483": _REFUSED,
    "M6484": _REFUSED + " " + _GUARD,
    "M6485": _NO_APPLY + " " + _ANY_FILE,
    "M6486": _ANY_FILE,
    "M6487": _AFTER,
    "M6488": _PARITY,
    "M6489": _READS,
    "M6490": _UNREAD,
}
