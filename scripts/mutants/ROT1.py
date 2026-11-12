"""ROT1 (#737): a pair's secret turned in one command, verified before the old one goes, a failure
leaving all in place, refused in a code session; its end reminded by Imladris's CD in #deploy at
J-14, J-7, J-1 and on the day, once per tier. M4828–M4835, measured by tests/unit/test_pair_rotate.py."""
ROTATE = "scripts/pair_rotate.py"
CD = "infra/glorfindel-host/cd/eregion_cd.py"
_T = "tests/unit/test_pair_rotate.py"

MUTANTS = [
    ("M4828", "the new secret's verification not heeded: a secret that never connects written into .envrc, the "
     "service restarted on it, and the old one removed — the pair cut (ROT1)", ROTATE,
     "    ok, why = verify(tenant, app_id, new, ctx)\n    if not ok:\n",
     "    ok, why = verify(tenant, app_id, new, ctx)\n    if False:\n"),
    ("M4829", "a service that does not restart on the new secret: .envrc not put back from its copy, the "
     "workstation left on a secret then removed (ROT1)", ROTATE,
     "    write_atomic(ctx.envrc, t.text, t.mode)\n    back = [",
     "    back = ["),
    ("M4830", "the refusal of a code session gone: an agent turns a secret and writes it (ROT1)", ROTATE,
     "    why = bs.session_refusal(ctx.env, ctx.cwd, ctx.here, never=NEVER)\n",
     "    why = \"\"\n"),
    ("M4831", "the new secret verified by `az login -p`: the secret on a command line, seen by `ps` (ROT1)", ROTATE,
     "    ok, why = verify(tenant, app_id, new, ctx)\n",
     "    ok, why = run([ctx.az, \"login\", \"--service-principal\", \"-u\", app_id, \"-p\", new, \"--tenant\", tenant],"
     " env).ok, \"az login\"\n"),
    ("M4832", "the service recreated with the environment of before: it keeps the old secret, which is then "
     "removed (ROT1)", ROTATE,
     "        if not recreate(s, new_env, ctx):\n",
     "        if not recreate(s, env, ctx):\n"),
    ("M4833", "the rewritten .envrc readable by all: its mode not kept (ROT1)", ROTATE,
     "            os.fchmod(fd, mode)\n",
     "            os.fchmod(fd, 0o644)\n"),
    ("M4834", "the tiers sent never saved: the same reminder posted at every pass of the timer, and again after "
     "a reboot (ROT1)", CD,
     "            save_reminders(doc)\n",
     "            pass\n"),
    ("M4835", "the tier read one day late: the J-14 reminder leaves at J-13, the day-itself one never (ROT1)", CD,
     "        if days_left <= tier:\n",
     "        if days_left < tier:\n"),
]
TESTS = {
    "M4828": f"{_T}::test_a_new_secret_that_does_not_connect_is_removed_and_nothing_else_moves",
    "M4829": f"{_T}::test_a_service_that_does_not_restart_on_the_new_secret_puts_everything_back",
    "M4830": f"{_T}::test_refused_in_a_code_session_before_anything",
    "M4831": f"{_T}::test_a_rotation_adds_verifies_writes_restarts_removes_the_old_one_and_notes_the_end",
    "M4832": f"{_T}::test_a_rotation_adds_verifies_writes_restarts_removes_the_old_one_and_notes_the_end",
    "M4833": f"{_T}::test_the_rewritten_envrc_keeps_its_mode",
    "M4834": f"{_T}::test_the_reminders_leave_at_j14_j7_j1_and_on_the_day_once_per_tier_even_after_a_restart",
    "M4835": f"{_T}::test_the_reminders_leave_at_j14_j7_j1_and_on_the_day_once_per_tier_even_after_a_restart",
}
