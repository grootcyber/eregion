"""MOB2: the workstation's tunnel to the console of Imladris, armed on demand for 12 h at most (decision of
Jonathan, 11/11) — never by a code session, never at boot, never without a limit of time, its port on
127.0.0.1 alone; the console's token never printed to a code session. M4776–M4780, and M4784–M4786 (review
round 1: what systemd loaded, the deadline that bounds the unit alone), measured by tests/unit/test_mobile.py."""
MOBILE = "scripts/mobile.py"
MAKEFILE = "Makefile"
UNIT = "infra/poste/eregion-console-tunnel.service"
_MOB = "tests/unit/test_mobile.py"

MUTANTS = [
    ("M4776", "the tunnel's guard read and not obeyed: a code session sets, arms or removes the "
     "workstation's tunnel to the console (MOB2)", MOBILE,
     "    if guard(target, env, cwd, here, never=NEVER_TUNNEL, say=say):\n",
     "    if False:\n"),
    ("M4777", "the console's token printed to a code session: make console-url, imladris-url and "
     "imladris-tunnel without their guard (MOB2)", MAKEFILE,
     "CONSOLE_GUARD  = python3 scripts/mobile.py guard\n",
     "CONSOLE_GUARD  = true\n"),
    ("M4778", "a unit with an [Install] section read as the model's: `systemctl enable` starts the tunnel "
     "at boot, without a gesture, and imladris-tunnel-check says nothing (MOB2)", MOBILE,
     '    if "Install" in sections:\n',
     "    if False:\n"),
    ("M4779", "a unit without a limit of time read as the model's: RuntimeMaxSec absent, infinite or "
     "beyond 12 h passes imladris-tunnel-check and imladris-tunnel-on arms it (MOB2)", MOBILE,
     "    if longest is None or not 1 <= longest <= WINDOW_S:\n",
     "    if False:\n"),
    ("M4780", "a forward bound to every interface read as 127.0.0.1: the tunnel exposes the console of "
     "Imladris to the LAN and the tailnet (MOB2)", MOBILE,
     '        return "sur toutes les interfaces"\n',
     '        return ""\n'),
    # Review round 1: what systemd loaded read beside the file; the unit bounded alone by its deadline.
    ("M4784", "imladris-tunnel-check reads the file, not what systemd loaded: a drop-in, another file, an infinite "
     "RuntimeMaxUSec or a unit that pulls the tunnel in pass (MOB2, review round 1)", MOBILE,
     "    lines += loaded_lines(state, fragment)\n",
     ""),
    ("M4785", "the unit's ExecCondition takes a deadline any distance ahead: a deadline written for days "
     "starts the tunnel beyond 12 h (MOB2, review round 1)", UNIT,
     ' && [ "$$end" -le $$((now + 43200)) ]\' deadline @DEADLINE@\n',
     "' deadline @DEADLINE@\n"),
    ("M4786", "ssh no longer under timeout until the deadline: a run lasts until RuntimeMaxSec, past the "
     "deadline (MOB2, review round 1)", UNIT,
     'exec /usr/bin/timeout "$$left" "$$@"\'',
     'exec "$$@"\''),
    # Review round 2: under timeout, MainPID is timeout's and its child ssh listens.
    ("M4787", "the listener compared with MainPID alone: under timeout, an armed and healthy tunnel is said "
     "not to hold 127.0.0.1:7007, and one held by its child is never seen (MOB2, review round 2)", MOBILE,
     '    pids = unit_pids(run, state.get("ControlGroup", ""), state.get("MainPID", ""))\n',
     '    pids = {state.get("MainPID", "")}\n'),
]
TESTS = {
    "M4776": f"{_MOB}::test_a_code_session_never_sets_nor_arms_the_tunnel",
    "M4777": f"{_MOB}::test_make_refuses_in_an_agent_session_before_anything_runs",
    "M4778": f"{_MOB}::test_a_unit_other_than_the_model_is_a_fail {_MOB}::test_on_refuses_a_unit_mobile_check_refuses",
    "M4779": f"{_MOB}::test_a_unit_other_than_the_model_is_a_fail {_MOB}::test_make_mobile_check_sees_an_unbounded_unit",
    "M4780": f"{_MOB}::test_a_unit_other_than_the_model_is_a_fail {_MOB}::test_on_refuses_a_unit_mobile_check_refuses",
    "M4784": f"{_MOB}::test_what_systemd_loaded_is_read_beside_the_file",
    "M4785": f"{_MOB}::test_the_deadline_refuses_a_start_past_it",
    "M4786": f"{_MOB}::test_ssh_runs_under_timeout_until_the_deadline",
    "M4787": f"{_MOB}::test_the_listener_of_ssh_under_timeout_is_the_unit_s",
}
