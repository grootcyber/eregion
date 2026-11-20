"""CDI2 (#922): what the Makefile's recipes do to Imladris as root, or to decide which host key ssh trusts,
lives in scripts the CODEOWNERS owns — the CD's sudo recipes (infra/glorfindel-host/cd/sudo_from_workstation.sh),
the host key's check (infra/glorfindel-host/known_host.sh), the SSH options (infra/glorfindel-host/ssh_opts.sh),
that each owned script checks itself. M6571–M6585: a weakened option accepted, the refusal of a drift
removed, a gesture lost or swapped, a recipe back in the Makefile, a path forgotten from the CODEOWNERS."""
OPTS = "infra/glorfindel-host/ssh_opts.sh"
SUDO = "infra/glorfindel-host/cd/sudo_from_workstation.sh"
INSTALL = "infra/glorfindel-host/cd/install_from_workstation.sh"
KNOWN = "infra/glorfindel-host/known_host.sh"
OWNERS = ".github/CODEOWNERS"
MAKE = "Makefile"
_T = "tests/unit/test_host_ssh_owned.py::"
_I = "tests/unit/test_host_cd_install.py::"
_C = "tests/unit/test_codeowners.py::"

MUTANTS = [
    # A weakened option accepted: the known_hosts the options name, unread.
    ("M6571", "the known_hosts the options name taken as it comes: UserKnownHostsFile=/dev/null goes (CDI2)", OPTS,
     "if ! dedicated; then\n",
     "if false; then\n"),
    ("M6572", "the account's own known_hosts taken for the dedicated one: keys accepted elsewhere trusted (CDI2)",
     OPTS,
     '  if [ "$known" -ef "${HOME:-/nonexistent}/.ssh/known_hosts" ] || [ "$known" -ef /etc/ssh/ssh_known_hosts ]; '
     "then\n    return 1\n  fi\n",
     ""),
    ("M6573", "a known_hosts without Imladris's key taken: never the one imladris-known checked (CDI2)", OPTS,
     '  ssh-keygen -F "$HOST_IP" -f "$known" >/dev/null 2>&1\n',
     "  true\n"),
    # The refusal of a drift removed: the owned scripts believe the Makefile again.
    ("M6574", "the sudo recipes' script believes the Makefile's SSH options: no check before sudo (CDI2)", SUDO,
     'bash "$(dirname "$0")/../ssh_opts.sh" check "$HOST_IP" "$HOST_USER" "$SSH_OPTS" || exit 1\n',
     ""),
    ("M6575", "the installation's script believes the Makefile's SSH options: no check before install.sh (CDI2)",
     INSTALL,
     'bash "$HERE/../ssh_opts.sh" check "$HOST_IP" "$HOST_USER" "$SSH_OPTS" || exit 1\n',
     ""),
    # A gesture lost, or swapped.
    ("M6576", "a gesture lost: the timer turned on, its next run no longer shown (CDI2)", SUDO,
     "  enable)    gesture='sudo systemctl enable --now eregion-cd.timer && systemctl list-timers eregion-cd.timer "
     "--no-pager' ;;\n",
     "  enable)    gesture='sudo systemctl enable --now eregion-cd.timer' ;;\n"),
    ("M6577", "the TTY lost: sudo cannot ask for its password (CDI2)", SUDO,
     'ssh -t $SSH_OPTS "$HOST_USER@$HOST_IP" "$gesture"\n',
     'ssh $SSH_OPTS "$HOST_USER@$HOST_IP" "$gesture"\n'),
    ("M6578", "the gestures swapped: make imladris-cd-disable turns the timer on (CDI2)", MAKE,
     "bash infra/glorfindel-host/cd/sudo_from_workstation.sh disable\n",
     "bash infra/glorfindel-host/cd/sudo_from_workstation.sh enable\n"),
    # A recipe back in the Makefile, owned by no line: the same bytes reach ssh, only the owned tests see it.
    ("M6579", "sudo back in the Makefile: make imladris-cd-uninstall runs it on Imladris, owned by no line (CDI2)",
     MAKE,
     '\t@HOST_IP="$(HOST_IP)" HOST_USER="$(HOST_USER)" SSH_OPTS="$(HOST_SSH_OPTS)" bash '
     "infra/glorfindel-host/cd/sudo_from_workstation.sh uninstall\n",
     "\t@ssh -t $(HOST_SSH_OPTS) $(HOST_USER)@$(HOST_IP) 'sudo bash .eregion-cd/install.sh --remove'\n"),
    ("M6580", "the SSH options back in the Makefile, owned by no line (CDI2)", MAKE,
     'HOST_SSH_OPTS  = $(or $(shell bash infra/glorfindel-host/ssh_opts.sh print "$(HOST_KNOWN_HOSTS)" '
     '"$(HOST_SSH_KEY)"),$(error infra/glorfindel-host/ssh_opts.sh n\'a rien rendu : rien ne part vers Imladris))\n',
     "HOST_SSH_OPTS  = -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$(HOST_KNOWN_HOSTS) "
     "-o HostKeyAlgorithms=ssh-ed25519 $(SSH_KEY_OPTS)\n"),
    ("M6581", "the options' script printing nothing, ssh goes without them: no pinned key (CDI2)", MAKE,
     ",$(error infra/glorfindel-host/ssh_opts.sh n'a rien rendu : rien ne part vers Imladris))\n",
     ",)\n"),
    ("M6582", "the maintainer's key path printed as it comes: -i -oProxyCommand=… reaches ssh (CDI2)", OPTS,
     '    [ -z "$key" ] || plain_path "$key" || { echo "✗ ssh_opts.sh : HOST_SSH_KEY « $key » n\'est pas un chemin '
     ': rien ne part vers Imladris" >&2; exit 1; }\n',
     ""),
    ("M6583", "the host key's check writes the key nowhere: /dev/null taken for the dedicated known_hosts (CDI2)",
     KNOWN,
     'if { [ -e "$file" ] && [ ! -f "$file" ]; } || [ "$file" -ef "${HOME:-/nonexistent}/.ssh/known_hosts" ] \\\n'
     "   || [ \"$file\" -ef /etc/ssh/ssh_known_hosts ]; then\n",
     "if false; then\n"),
    # A path forgotten from the CODEOWNERS: the pull request that changes it no longer waits for Jonathan.
    ("M6584", "the SSH options' script forgotten from the CODEOWNERS (CDI2)", OWNERS,
     "/infra/glorfindel-host/ssh_opts.sh      @grootcyber\n",
     ""),
    ("M6585", "the host key's check forgotten from the CODEOWNERS (CDI2)", OWNERS,
     "/infra/glorfindel-host/known_host.sh    @grootcyber\n",
     ""),
]
TESTS = {
    "M6571": _T + "test_weakened_options_are_refused_before_any_call",
    "M6572": _T + "test_the_account_s_own_known_hosts_is_refused",
    "M6573": _T + "test_a_known_hosts_without_imladris_s_key_is_refused",
    "M6574": _T + "test_weakened_options_are_refused_before_any_call",
    "M6575": _I + "test_the_script_never_goes_without_the_pinned_key",
    "M6576": _T + "test_each_sudo_recipe_sends_ssh_the_same_arguments_to_the_byte",
    "M6577": _T + "test_each_sudo_recipe_sends_ssh_the_same_arguments_to_the_byte",
    "M6578": _T + "test_each_sudo_recipe_sends_ssh_the_same_arguments_to_the_byte",
    "M6579": _T + "test_sudo_is_run_on_imladris_only_by_the_owned_script " + _C
    + "test_what_acts_on_imladris_from_the_makefile_lives_in_owned_scripts",
    "M6580": _T + "test_the_makefile_takes_its_options_from_the_owned_script " + _C
    + "test_the_host_key_s_check_and_the_ssh_options_are_owned",
    "M6581": _T + "test_when_the_script_prints_nothing_make_stops_and_no_ssh_goes",
    "M6582": _T + "test_a_path_that_is_not_one_prints_nothing",
    "M6583": _T + "test_imladris_known_refuses_a_known_hosts_that_is_not_dedicated_before_asking",
    "M6584": _C + "test_every_file_a_credentialed_job_runs_is_owned " + _C
    + "test_the_host_key_s_check_and_the_ssh_options_are_owned",
    "M6585": _C + "test_every_file_a_credentialed_job_runs_is_owned " + _C
    + "test_the_host_key_s_check_and_the_ssh_options_are_owned",
}
