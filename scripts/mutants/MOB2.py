"""MOB2: the workstation's tunnel to the console of Imladris, armed on demand for 12 h at most (decision of
Jonathan, 11/11) — never by a code session, never at boot, never without a limit of time, its port on
127.0.0.1 alone; the console's token never printed to a code session. M4776–M4780, measured by
tests/unit/test_mobile.py."""
MOBILE = "scripts/mobile.py"
MAKEFILE = "Makefile"
_MOB = "tests/unit/test_mobile.py"

MUTANTS = [
    ("M4776", "the tunnel's guard read and not obeyed: a code session sets, arms or removes the "
     "workstation's tunnel to the console (MOB2)", MOBILE,
     "    if guard(target, env, cwd, here, never=NEVER_TUNNEL, say=say):\n",
     "    if False:\n"),
    ("M4777", "the console's token printed to a code session: make console-url, glorfindel-host-url and "
     "glorfindel-host-tunnel without their guard (MOB2)", MAKEFILE,
     "CONSOLE_GUARD  = python3 scripts/mobile.py guard\n",
     "CONSOLE_GUARD  = true\n"),
    ("M4778", "a unit with an [Install] section read as the model's: `systemctl enable` starts the tunnel "
     "at boot, without a gesture, and mobile-check says nothing (MOB2)", MOBILE,
     '    if "Install" in sections:\n',
     "    if False:\n"),
    ("M4779", "a unit without a limit of time read as the model's: RuntimeMaxSec absent, infinite or "
     "beyond 12 h passes mobile-check and mobile-tunnel-on arms it (MOB2)", MOBILE,
     "    if longest is None or not 1 <= longest <= WINDOW_S:\n",
     "    if False:\n"),
    ("M4780", "a forward bound to every interface read as 127.0.0.1: the tunnel exposes the console of "
     "Imladris to the LAN and the tailnet (MOB2)", MOBILE,
     '        return "sur toutes les interfaces"\n',
     '        return ""\n'),
]
TESTS = {
    "M4776": f"{_MOB}::test_a_code_session_never_sets_nor_arms_the_tunnel",
    "M4777": f"{_MOB}::test_make_refuses_in_an_agent_session_before_anything_runs",
    "M4778": f"{_MOB}::test_a_unit_other_than_the_model_is_a_fail {_MOB}::test_on_refuses_a_unit_mobile_check_refuses",
    "M4779": f"{_MOB}::test_a_unit_other_than_the_model_is_a_fail {_MOB}::test_make_mobile_check_sees_an_unbounded_unit",
    "M4780": f"{_MOB}::test_a_unit_other_than_the_model_is_a_fail {_MOB}::test_on_refuses_a_unit_mobile_check_refuses",
}
