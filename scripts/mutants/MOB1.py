"""MOB1 (#686): the bench driven from the phone — `make bench-run` and `make bench-restore` typed on the
workstation, never in an agent session, never without the target's name typed; the restore before the
run's T0 and keeping the isolation; the console's tunnel on the private address alone; `make
mobile-check` that sees a listener on every interface and a password admitted. M4696–M4705, measured by
tests/unit/test_bench_run.py, tests/unit/test_bench_restore.py and tests/unit/test_mobile.py."""
RUN = "scripts/bench_run.py"
RESTORE = "scripts/bench_restore.py"
MOBILE = "scripts/mobile.py"
_RUN = "tests/unit/test_bench_run.py"
_RES = "tests/unit/test_bench_restore.py"
_MOB = "tests/unit/test_mobile.py"

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
     '            best = (t0, str(doc.get("t0")), rid)\n',
     '            best = (t0, str(doc.get("composed_at") or doc.get("t0")), rid)\n'),
    ("M4703", "any IPv4 taken for the private address: the console's port bound to the LAN, or to every "
     "interface (MOB1)", MOBILE,
     "    if ip.version != 4 or ip not in TAILNET_V4:\n",
     "    if ip.version != 4:\n"),
    ("M4704", "a listener on every interface read as on the private address: mobile-check passes an SSH "
     "server open to the LAN (MOB1)", MOBILE,
     '    if addr in ("*", "0.0.0.0", "::", ""):\n        return "every"\n',
     '    if addr in ("*", "0.0.0.0", "::", ""):\n        return "private"\n'),
    ("M4705", "the password left out of what mobile-check reads: PasswordAuthentication yes passes "
     "(MOB1)", MOBILE,
     'REQUIRED = (("passwordauthentication", "no"), ("kbdinteractiveauthentication", "no"),\n',
     'REQUIRED = (("kbdinteractiveauthentication", "no"),\n'),
]
TESTS = {
    "M4696": f"{_RUN}::test_a_code_session_is_refused_before_any_step",
    "M4697": f"{_RUN}::test_without_the_target_s_name_typed_nothing_is_sent",
    "M4698": f"{_RUN}::test_a_red_preflight_asks_nothing_and_sends_nothing",
    "M4699": f"{_RES}::test_a_code_session_is_refused_before_any_step",
    "M4700": f"{_RES}::test_without_the_vm_s_name_typed_nothing_is_restored",
    "M4701": f"{_RES}::test_before_defaults_to_the_t0_of_the_latest_run_of_the_target "
             f"{_RES}::test_the_restore_argv_always_keeps_the_isolation",
    "M4702": f"{_RES}::test_before_defaults_to_the_t0_of_the_latest_run_of_the_target",
    "M4703": f"{_MOB}::test_the_private_address_is_one_tailnet_ipv4_or_none "
             f"{_MOB}::test_the_console_tunnel_opens_nothing_without_the_private_address",
    "M4704": f"{_MOB}::test_an_ssh_server_listening_elsewhere_than_the_private_address_is_seen "
             f"{_MOB}::test_make_mobile_check_sees_every_interface_and_a_password",
    "M4705": f"{_MOB}::test_a_password_or_another_method_admitted_is_seen "
             f"{_MOB}::test_make_mobile_check_sees_every_interface_and_a_password",
}
