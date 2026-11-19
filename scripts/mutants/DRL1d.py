"""DRL1d (#613): the drill of the week runs with the options of Annatar's runs on Orodruin —
ORO_HARDEN then ORO_EXEC_HOME, read in the Makefile, no more, no less (docs/design/drill-banc.md
§15). M5991–M6000. Measured by tests/unit/test_drill_ops.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids);
its paths as plain strings.
"""
OPS = "infra/orodruin/drill_ops.py"
MK = "Makefile"
T = "tests/unit/test_drill_ops.py::"

_COPIES = T + "test_the_drills_hardening_is_the_makefiles_oro_harden_and_its_exec_home_oro_exec_home"
_PARITY = T + "test_the_drills_service_runs_with_the_options_of_annatars_runs_no_more_no_less"
_HOME = T + "test_the_drills_run_home_is_the_exec_tmpfs_where_the_adapter_builds_it_and_tmp_stays_noexec"
_READS = T + "test_the_drills_reads_that_play_no_run_get_nothing_more_than_the_hardening"

MUTANTS = [
    ("M5991", "the exec tmpfs dropped from the drill's service: hardened only, the control-plane library's "
     "Terraform cannot execute its providers, the drill fails where the run by hand passes (DRL1d)", OPS,
     "--name {CONTAINER} {RUN_OPTS} ", "--name {CONTAINER} {HARDEN} "),
    ("M5992", "/tmp made executable in the drill's hardening (DRL1d)", OPS,
     'HARDEN = "--read-only --tmpfs /tmp --cap-drop ALL',
     'HARDEN = "--read-only --tmpfs /tmp:exec --cap-drop ALL'),
    ("M5993", "the drill's exec tmpfs mounted elsewhere than where the adapter builds the run HOME: the HOME "
     "lands on /tmp, noexec (DRL1d)", OPS,
     'EXEC_HOME = "--tmpfs /stratus-home:exec"', 'EXEC_HOME = "--tmpfs /drill-home:exec"'),
    ("M5994", "the drill's HOME pointed elsewhere by the environment, on noexec /tmp (DRL1d)", OPS,
     '        f"--env-file orodruin.env {mounts}', '        f"-e HOME=/tmp --env-file orodruin.env {mounts}'),
    ("M5995", "the drill's root no longer read-only (DRL1d)", OPS,
     'HARDEN = "--read-only --tmpfs /tmp', 'HARDEN = "--tmpfs /tmp'),
    ("M5996", "the parity loses ORO_EXEC_HOME: Annatar's run by hand without the exec tmpfs, the drill "
     "with it (DRL1d)", MK,
     "ORO_RUN        = $(ORO_DIRS) docker run --rm $(ORO_HARDEN) $(ORO_EXEC_HOME) --env-file",
     "ORO_RUN        = $(ORO_DIRS) docker run --rm $(ORO_HARDEN) --env-file"),
    ("M5997", "one option more on the drill's service than on Annatar's runs: a capability added (DRL1d)", OPS,
     'RUN_OPTS = f"{HARDEN} {EXEC_HOME}"', 'RUN_OPTS = f"{HARDEN} {EXEC_HOME} --cap-add SYS_ADMIN"'),
    ("M5998", "the drill's reads (fingerprint, check), which play no run, given the exec tmpfs (DRL1d)", MK,
     "ORO_DRILL_RUN  = docker run --rm $(ORO_HARDEN) --env-file",
     "ORO_DRILL_RUN  = docker run --rm $(ORO_HARDEN) $(ORO_EXEC_HOME) --env-file"),
    ("M5999", "the Makefile's hardening gains an option the drill's copy does not follow (DRL1d)", MK,
     "ORO_HARDEN     = --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true",
     "ORO_HARDEN     = --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true "
     "--pids-limit 512"),
    ("M6000", "the drill's no-new-privileges dropped (DRL1d)", OPS,
     '--cap-drop ALL --security-opt no-new-privileges:true"', '--cap-drop ALL"'),
]

TESTS = {
    "M5991": _PARITY,
    "M5992": _COPIES + " " + _HOME,
    "M5993": _COPIES + " " + _HOME,
    "M5994": _HOME,
    "M5995": _COPIES + " " + _HOME,
    "M5996": _PARITY,
    "M5997": _PARITY,
    "M5998": _READS,
    "M5999": _COPIES,
    "M6000": _COPIES + " " + _HOME,
}
