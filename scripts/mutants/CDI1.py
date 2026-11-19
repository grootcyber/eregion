"""CDI1 (#918): the installation of Imladris's CD lives in a script the CODEOWNERS owns
(infra/glorfindel-host/cd/install_from_workstation.sh); `make imladris-cd-install` only checks the host
key, then calls it. M6351–M6360: a gesture removed, the order changed, umask removed, the stop at a
failed gesture lost, the TTY lost, a refusal of what the Makefile passes lost, the recipe back in the
Makefile."""
SCRIPT = "infra/glorfindel-host/cd/install_from_workstation.sh"
# Re-anchored (CDI2, #922): the checks of the address, the user and SSH_OPTS moved, line for line, into
# infra/glorfindel-host/ssh_opts.sh, which the script calls before any gesture.
OPTS = "infra/glorfindel-host/ssh_opts.sh"
_TEST = "tests/unit/test_host_cd_install.py"

MUTANTS = [
    ("M6351", "a gesture removed: cosign no longer downloaded by the VM, install.sh refuses the agent (CDI1)", SCRIPT,
     "on_imladris 'python3 .eregion-cd/published_image.py install-cosign .eregion-cd/cosign'\n",
     ""),
    ("M6352", "a gesture removed: ~/.eregion-cd, where discord.env goes, no longer made 700 (CDI1)", SCRIPT,
     "on_imladris 'mkdir -p .eregion-cd && chmod 700 .eregion-cd'\n",
     "on_imladris 'mkdir -p .eregion-cd'\n"),
    ("M6353", "the order changed: cosign downloaded before the files are copied (CDI1)", SCRIPT,
     'scp -q $SSH_OPTS $CD_FILES "$TO:.eregion-cd/"\n'
     "on_imladris 'python3 .eregion-cd/published_image.py install-cosign .eregion-cd/cosign'\n",
     "on_imladris 'python3 .eregion-cd/published_image.py install-cosign .eregion-cd/cosign'\n"
     'scp -q $SSH_OPTS $CD_FILES "$TO:.eregion-cd/"\n'),
    ("M6354", "umask removed: discord.env, the webhook of #deploy, written readable by every account (CDI1)", SCRIPT,
     "on_imladris 'umask 077 && cat > .eregion-cd/discord.env'\n",
     "on_imladris 'cat > .eregion-cd/discord.env'\n"),
    ("M6355", "the recipe back in the Makefile, owned by no line of the CODEOWNERS (CDI1)", "Makefile",
     '\t@HOST_IP="$(HOST_IP)" HOST_USER="$(HOST_USER)" SSH_OPTS="$(HOST_SSH_OPTS)" CD_FILES="$(HOST_CD_FILES)" '
     "bash infra/glorfindel-host/cd/install_from_workstation.sh\n",
     '\t@test -n "$(HOST_IP)" || { echo "Pas de VM : make imladris-up d\'abord"; exit 1; }\n'
     "\t@lines=$$(python3 infra/glorfindel-host/cd/eregion_cd.py export-discord-env) || exit 1; \\\n"
     "\t $(HOST_SSH) 'mkdir -p .eregion-cd && chmod 700 .eregion-cd' && \\\n"
     "\t scp -q $(HOST_SSH_OPTS) $(HOST_CD_FILES) $(HOST_USER)@$(HOST_IP):.eregion-cd/ && \\\n"
     "\t $(HOST_SSH) 'python3 .eregion-cd/published_image.py install-cosign .eregion-cd/cosign' && \\\n"
     "\t printf '%s\\n' \"$$lines\" | $(HOST_SSH) 'umask 077 && cat > .eregion-cd/discord.env' && \\\n"
     "\t git rev-parse HEAD | $(HOST_SSH) 'cat > .eregion-cd/installed-from'\n"
     "\t@$(HOST_SSH_TTY) 'sudo bash .eregion-cd/install.sh'\n"),
    ("M6356", "the stop at a failed gesture lost: install.sh run as root after a copy that failed (CDI1)", SCRIPT,
     "set -eu\n",
     "set -u\n"),
    ("M6357", "the webhook unread and the installation goes on: discord.env written empty (CDI1)", SCRIPT,
     'lines=$(python3 "$HERE/eregion_cd.py" export-discord-env) || exit 1\n',
     'lines=$(python3 "$HERE/eregion_cd.py" export-discord-env) || true\n'),
    ("M6358", "the TTY lost: sudo cannot ask for its password, install.sh never runs (CDI1)", SCRIPT,
     "ssh -t $SSH_OPTS \"$TO\" 'sudo bash .eregion-cd/install.sh'\n",
     "ssh $SSH_OPTS \"$TO\" 'sudo bash .eregion-cd/install.sh'\n"),
    ("M6359", "SSH options taken as they come: a key accepted at first contact (CDI1)", OPTS,
     "if ! pinned_form; then\n",
     "if false; then\n"),
    ("M6360", "the Makefile's list of files taken as it comes: any file of the checkout under an agent's name "
     "(CDI1)", SCRIPT,
     '[ "$(printf \'%s \' $CD_FILES)" = "$OWNED_FILES " ] || {\n',
     "true || {\n"),
]
# The review's first round: the form of SSH_OPTS checked word for word — ssh keeps an option's first value.
MUTANTS += [
    ("M6361", "an option added after the whole form, the key's included: -o ProxyCommand=… or -F … goes "
     "(CDI1 review)", OPTS,
     '  [ "$#" -eq 6 ] || [ "$#" -eq 10 ] || return 1\n',
     ""),
    ("M6362", "the first value of StrictHostKeyChecking unread: « no » first wins in ssh (CDI1 review)", OPTS,
     '  [ "$1 $2" = "-o StrictHostKeyChecking=yes" ] || return 1\n',
     ""),
    ("M6363", "the known_hosts option unread: -o KnownHostsCommand=… in its place goes (CDI1 review)", OPTS,
     '  [ "$3" = -o ] && case "$4" in UserKnownHostsFile=*) plain_path "${4#UserKnownHostsFile=}" ;; *) false ;; '
     "esac || return 1\n",
     ""),
    ("M6364", "the host key algorithm unread: -o ProxyCommand=… in its place goes (CDI1 review)", OPTS,
     '  [ "$5 $6" = "-o HostKeyAlgorithms=ssh-ed25519" ] || return 1\n',
     ""),
    ("M6365", "the key's options unread: -i … -o ProxyCommand=… goes (CDI1 review)", OPTS,
     '  [ "$#" -eq 6 ] || { [ "$7" = -i ] && plain_path "$8" && [ "$9 ${10}" = "-o IdentitiesOnly=yes" ]; }\n',
     '  [ "$#" -eq 6 ] || [ "$7" = -i ]\n'),
]
# The review's second round: « user@address », ssh's last word, never an option; the key's path, a path.
MUTANTS += [
    ("M6381", "the address taken as it comes: « -oProxyCommand=… » reaches ssh as an option (CDI1 review 2)",
     OPTS,
     '[[ $HOST_IP =~ $ip_re ]] || { echo "✗ HOST_IP n\'est pas une adresse IPv4 : rien ne part vers Imladris" >&2;'
     " exit 1; }\n",
     ""),
    ("M6382", "the user taken as it comes: « -oProxyCommand=… » reaches ssh as an option (CDI1 review 2)", OPTS,
     '[[ $HOST_USER =~ $user_re ]] || { echo "✗ HOST_USER n\'est pas un nom d\'utilisateur Unix : rien ne part vers'
     ' Imladris" >&2; exit 1; }\n',
     ""),
    ("M6383", "the key's path unread: « -i -F » or a %-token goes (CDI1 review 2)", OPTS,
     '[ "$7" = -i ] && plain_path "$8" && [ "$9 ${10}"',
     '[ "$7" = -i ] && [ "$9 ${10}"'),
]
TESTS = {mid: _TEST for mid, *_ in MUTANTS}
