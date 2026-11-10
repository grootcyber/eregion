"""MOB1 (#686): the bench driven from the phone — `make bench-run` and `make bench-restore` typed on the
workstation, in a terminal, never in an agent session, never without the target's name typed; the
restore before the run's T0 and keeping the isolation; `make orodruin-exercise` wanting a terminal too;
`make mobile-check` that sees a listener on every interface, a password admitted, a key handed by a
command, a forwarding wider than the phone's tunnel to 127.0.0.1:7007, a console port elsewhere than on
127.0.0.1. M4696–M4705, M4737–M4744 (review round 1: the console's tunnel on the private address went
with its target; M4703 is the terminal of bench-run now) and M4756–M4758 (review round 2), measured by tests/unit/test_bench_run.py,
tests/unit/test_bench_restore.py, tests/unit/test_mobile.py, tests/unit/test_exercise_request.py and
tests/unit/test_makefile_exercise.py."""
RUN = "scripts/bench_run.py"
RESTORE = "scripts/bench_restore.py"
MOBILE = "scripts/mobile.py"
SHARED = "scripts/bench_shared.py"
REQUEST = "eregion_core/exercise_request.py"
MAKEFILE = "Makefile"
_RUN = "tests/unit/test_bench_run.py"
_RES = "tests/unit/test_bench_restore.py"
_MOB = "tests/unit/test_mobile.py"
_XR = "tests/unit/test_exercise_request.py"
_MX = "tests/unit/test_makefile_exercise.py"

MUTANTS = [
    ("M4696", "bench-run's guard read and not obeyed: an agent session, or a lot's worktree, launches an "
     "attack on the bench (MOB1)", RUN,
     '    if refusal:\n        say(f"✗ make bench-run refusé',
     '    if False:\n        say(f"✗ make bench-run refusé'),
    ("M4697", "the name typed for bench-run never compared to the target: any name, then « o », sends the "
     "request (MOB1)", RUN,
     "    if got != wire.target_name:\n",
     "    if False:\n"),
    ("M4698", "a red preflight read as green: the request asked and sent past a ✗ (MOB1)", RUN,
     "    if steps.preflight(target) != 0:\n",
     "    if steps.preflight(target) is None:\n"),
    ("M4699", "bench-restore's guard read and not obeyed: an agent session restores a VM under the "
     "console's pair (MOB1)", RESTORE,
     '    if refusal:\n        say(f"✗ make bench-restore refusé',
     '    if False:\n        say(f"✗ make bench-restore refusé'),
    ("M4700", "the VM's name typed for bench-restore never compared: another name restores it all the same "
     "(MOB1)", RESTORE,
     "    if got != name:\n",
     "    if False:\n"),
    ("M4701", "--keep-isolated dropped: the workstation's restore releases the VM in its own process, under "
     "its own configuration, and H0 puts the isolation back (MOB1)", RESTORE,
     '    return ["restore", resource_id, "--before", moment, "--keep-isolated",\n',
     '    return ["restore", resource_id, "--before", moment,\n'),
    ("M4702", "the default --before taken from when the report was composed, after the attack: the point "
     "restored may hold the attack (SEC4c, MOB1)", RESTORE,
     '        found.append((t0, str(doc.get("t0")), rid))\n',
     '        found.append((t0, str(doc.get("composed_at") or doc.get("t0")), rid))\n'),
    ("M4703", "bench-run without a terminal read on: a name piped (`printf … | make bench-run`) is taken for "
     "a name typed (MOB1, review round 1)", RUN,
     '    if not (sys.stdin.isatty() if tty is None else tty):\n        say("✗ pas de terminal : le nom de la cible',
     '    if False:\n        say("✗ pas de terminal : le nom de la cible'),
    ("M4704", "a listener on every interface read as on the private address: mobile-check passes an SSH "
     "server open to the LAN (MOB1)", MOBILE,
     '    if addr in ("*", "0.0.0.0", "::", ""):\n        return "every"\n',
     '    if addr in ("*", "0.0.0.0", "::", ""):\n        return "private"\n'),
    ("M4705", "the password left out of what mobile-check reads: PasswordAuthentication yes passes "
     "(MOB1)", MOBILE,
     '    ("passwordauthentication", "no"),\n',
     ''),
    ("M4737", "bench-restore without a terminal read on: a name piped restores the VM under the console's "
     "pair (MOB1, review round 1)", RESTORE,
     '    if not (sys.stdin.isatty() if tty is None else tty):\n        say("✗ pas de terminal : le nom de la VM',
     '    if False:\n        say("✗ pas de terminal : le nom de la VM'),
    ("M4738", "orodruin-exercise's names read from a pipe: a request carried to Orodruin with names nobody "
     "typed (MOB1, review round 1)", REQUEST,
     '    if not (sys.stdin.isatty() if tty is None else tty):\n        print("✗ no terminal',
     '    if False:\n        print("✗ no terminal'),
    ("M4739", "the Makefile's guard line gone: an agent session's bench-run expands H0's and Orodruin's "
     "commands (terraform output) before any guard (MOB1, review round 1)", MAKEFILE,
     "\t@$(PYTHON) scripts/$(subst -,_,$@).py --guard-only\n",
     "\t@true\n"),
    ("M4740", "the guard blind to a lot's worktree: a session without its variable, in its worktree, "
     "launches an attack or a restore (MOB1, review round 1)", SHARED,
     '        if ".claude" in parts and "worktrees" in parts[parts.index(".claude"):]:\n',
     "        if False:\n"),
    ("M4741", "AllowTcpForwarding yes or all read as local: the phone forwards through the workstation, "
     "remote ports included (MOB1, review round 1)", MOBILE,
     '    if fwd == "local":\n',
     '    if fwd in ("local", "yes", "all"):\n'),
    ("M4742", "PermitOpen any, or more than the console, read as the console alone: the phone's tunnel "
     "opens onto H0's or Orodruin's SSH (MOB1, review round 1)", MOBILE,
     '    if opens == [f"127.0.0.1:{console_port}"]:\n',
     '    if f"127.0.0.1:{console_port}" in opens or opens == ["any"]:\n'),
    ("M4743", "the console's port on the private address read as on 127.0.0.1: the tailnet reaches the "
     "console without the phone's key (MOB1, review round 1)", MOBILE,
     '    bad = sorted({kind(a, private) for a in console if a not in CONSOLE_LOOPBACK})\n',
     '    bad = sorted({kind(a, private) for a in console if a not in CONSOLE_LOOPBACK} - {"private"})\n'),
    ("M4744", "AuthorizedKeysCommand left out of what mobile-check reads: keys handed by a command pass "
     "(MOB1, review round 1)", MOBILE,
     '    ("authorizedkeyscommand", "none"),\n',
     ''),
    ("M4756", "orodruin-exercise's terminal checked only once the request is pulled from H0 and a drill's "
     "VMs read on Azure (MOB1, review round 2)", MAKEFILE,
     '\t@[ -t 0 ] || { echo "✗ pas de terminal : les noms des cibles',
     '\t@true || { echo "✗ pas de terminal : les noms des cibles'),
    ("M4757", "socket, agent and X11 forwarding left out of what mobile-check reads: an SSH server that "
     "relays them passes (MOB1, review round 2)", MOBILE,
     "    for key, want in REQUIRED + NO_RELAY:\n",
     "    for key, want in REQUIRED:\n"),
    ("M4758", "the origin of the variables not checked again in the internal -go targets: `make "
     "bench-run-go` called directly takes TARGET or POINT_MAX_H from the environment (MOB1, review round 2)",
     MAKEFILE,
     "\t@$(MOB1_ORIGIN)\n\t@$(PYTHON) scripts/$(subst -,_,$(@:-go=)).py\n",
     "\t@$(PYTHON) scripts/$(subst -,_,$(@:-go=)).py\n"),
]
TESTS = {
    "M4696": f"{_RUN}::test_a_code_session_is_refused_before_any_step",
    "M4697": f"{_RUN}::test_without_the_target_s_name_typed_nothing_is_sent",
    "M4698": f"{_RUN}::test_a_red_preflight_asks_nothing_and_sends_nothing",
    "M4699": f"{_RES}::test_a_code_session_is_refused_before_any_step",
    "M4700": f"{_RES}::test_without_the_vm_s_name_typed_nothing_is_restored",
    "M4701": f"{_RES}::test_before_defaults_to_the_t0_of_the_one_run_of_the_target "
             f"{_RES}::test_the_restore_argv_always_keeps_the_isolation",
    "M4702": f"{_RES}::test_before_defaults_to_the_t0_of_the_one_run_of_the_target",
    "M4703": f"{_RUN}::test_without_a_terminal_nothing_is_read_and_nothing_is_launched",
    "M4704": f"{_MOB}::test_an_ssh_server_listening_elsewhere_than_the_private_address_is_seen "
             f"{_MOB}::test_make_mobile_check_sees_every_interface_a_password_and_a_wide_tunnel",
    "M4705": f"{_MOB}::test_a_password_or_another_way_in_admitted_is_seen "
             f"{_MOB}::test_make_mobile_check_sees_every_interface_a_password_and_a_wide_tunnel",
    "M4737": f"{_RES}::test_without_a_terminal_nothing_is_read_and_nothing_is_restored",
    "M4738": f"{_XR}::test_confirm_wants_a_terminal",
    "M4739": f"{_RUN}::test_make_refuses_in_an_agent_session_before_anything_runs",
    "M4740": f"{_RUN}::test_a_code_session_is_refused_before_any_step "
             f"{_RES}::test_a_code_session_is_refused_before_any_step",
    "M4741": f"{_MOB}::test_forwarding_is_the_phone_s_local_tunnel_alone "
             f"{_MOB}::test_make_mobile_check_sees_every_interface_a_password_and_a_wide_tunnel",
    "M4742": f"{_MOB}::test_the_tunnel_opens_onto_the_console_alone "
             f"{_MOB}::test_make_mobile_check_sees_every_interface_a_password_and_a_wide_tunnel",
    "M4743": f"{_MOB}::test_the_console_s_port_listens_on_127_0_0_1_alone",
    "M4744": f"{_MOB}::test_a_password_or_another_way_in_admitted_is_seen",
    "M4756": f"{_MX}::test_without_a_terminal_nothing_is_read_before_the_refusal "
             f"{_MX}::test_names_piped_instead_of_typed_send_nothing",
    "M4757": f"{_MOB}::test_a_password_or_another_way_in_admitted_is_seen",
    "M4758": f"{_RUN}::test_the_internal_targets_refuse_a_variable_from_the_environment",
}
