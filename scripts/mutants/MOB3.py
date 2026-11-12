"""MOB3: what the bench of 11/11 measured — the hours of the workstation's tunnel said in UTC, and no command
toward Imladris printed by make (its address, its user, the key's path: pasted from the phone's terminal, the
line left as it was). M4816–M4818, measured by tests/unit/test_mobile.py and tests/unit/test_host_ssh.py."""
MOBILE = "scripts/mobile.py"
MAKEFILE = "Makefile"
_MOB = "tests/unit/test_mobile.py"
_SSH = "tests/unit/test_host_ssh.py"

MUTANTS = [
    ("M4816", "the tunnel's hours said « UTC » but read in the workstation's zone: « armé depuis … expire à … » "
     "is an hour of another zone, read on the phone (MOB3)", MOBILE,
     '    return time.strftime("%d/%m %H:%M UTC", time.gmtime(t))\n',
     '    return time.strftime("%d/%m %H:%M UTC", time.localtime(t))\n'),
    ("M4817", "make glorfindel-host-ssh prints its command again: the address of Imladris and the key's path "
     "shown, and the line left as it was once pasted (MOB3)", MAKEFILE,
     "glorfindel-host-ssh: glorfindel-host-known\n\t@$(HOST_SSH)\n",
     "glorfindel-host-ssh: glorfindel-host-known\n\t$(HOST_SSH)\n"),
    ("M4818", "the tunnel by hand (glorfindel-host-tunnel) prints its ssh: the address of Imladris shown, and a "
     "second tunnel held once pasted (MOB3)", MAKEFILE,
     "\t@ssh $(HOST_SSH_OPTS) -N -L 7007:127.0.0.1:7007 $(HOST_USER)@$(HOST_IP)\n",
     "\tssh $(HOST_SSH_OPTS) -N -L 7007:127.0.0.1:7007 $(HOST_USER)@$(HOST_IP)\n"),
]
TESTS = {
    "M4816": f"{_MOB}::test_the_hours_of_the_tunnel_are_said_in_utc_whatever_the_workstation_s_zone",
    "M4817": f"{_SSH}::test_make_glorfindel_host_ssh_prints_nothing_of_its_command "
             f"{_SSH}::test_no_command_toward_imladris_is_echoed_by_make",
    "M4818": f"{_SSH}::test_no_command_toward_imladris_is_echoed_by_make",
}
