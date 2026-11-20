#!/usr/bin/env bash
# ssh_opts.sh — the SSH options toward Imladris (V-32, SEC7, SEC-C), owned by .github/CODEOWNERS
# (CDI2, #922; Jonathan's decision of 19/11).
#
#   bash infra/glorfindel-host/ssh_opts.sh print <known_hosts> [<key>]
#   bash infra/glorfindel-host/ssh_opts.sh check <address> <user> <options>
#
# print: what the Makefile's HOST_SSH_OPTS holds — Imladris's key pinned, nothing accepted at first
#   contact: StrictHostKeyChecking=yes on the dedicated known_hosts alone (the one known_host.sh writes
#   from HOST_SSH_FINGERPRINT), ed25519, then the maintainer's key and IdentitiesOnly when HOST_SSH_KEY
#   is set. The same bytes the Makefile computed before CDI2, the trailing blank without a key
#   included. Exit 1, nothing printed, for a path that is not one (the Makefile then stops: $(error)).
# check: what an owned script runs before any gesture toward Imladris (install_from_workstation.sh,
#   sudo_from_workstation.sh), so as never to believe the Makefile, which is not owned:
#   - the address, an IPv4 address; the user, a Unix user name — « user@address » is ssh's last word
#     before the command, and a user « -oProxyCommand=… » would arrive as an option (review of CDI1);
#   - the options, the form print gives, word for word: ssh keeps the first value of an option, so a
#     check for « =yes » somewhere let « -o StrictHostKeyChecking=no » before it through (review of
#     CDI1), and so would any other option added (-F, ProxyCommand, ProxyJump, KnownHostsCommand…);
#   - the known_hosts they name: a regular file (never /dev/null), not empty, not the account's own or
#     the system's (~/.ssh/known_hosts, /etc/ssh/ssh_known_hosts: keys accepted elsewhere, for other
#     hosts), and holding a key for this address — the one imladris-known checked by its fingerprint.
#   Exit 0: go on; 1: refused, said on stderr, nothing ran.
# What it holds: a drift of the options, seen here. Not a hostile Makefile: it may not call this
# script, nor the owned scripts that call it (docs/design/modele-de-menace.md, §7).
# tests/unit/test_host_ssh_owned.py keeps it, against a fake ssh.
set -u
set -f          # the options are split on blanks, never globbed: as the Makefile split them

# A path: never an option, never ssh's %-tokens; letters, digits and -_./~@+ (ASCII, whatever the locale).
plain_path() { case "$1" in '' | -* | *[!-[:alnum:]_./~@+]*) return 1 ;; esac; }

case "${1:-}" in
  print)
    known=${2:-}
    key=${3:-}
    plain_path "$known" || { echo "✗ ssh_opts.sh : HOST_KNOWN_HOSTS « $known » n'est pas un chemin : rien ne part vers Imladris" >&2; exit 1; }
    [ -z "$key" ] || plain_path "$key" || { echo "✗ ssh_opts.sh : HOST_SSH_KEY « $key » n'est pas un chemin : rien ne part vers Imladris" >&2; exit 1; }
    printf '%s\n' "-o StrictHostKeyChecking=yes -o UserKnownHostsFile=$known -o HostKeyAlgorithms=ssh-ed25519 ${key:+-i $key -o IdentitiesOnly=yes}"
    exit 0 ;;
  check) ;;
  *) echo "✗ ssh_opts.sh : print ou check, pas « ${1:-} »" >&2; exit 1 ;;
esac

HOST_IP=${2:-}
HOST_USER=${3:-}
SSH_OPTS=${4:-}
ip_re='^[[:digit:]]{1,3}(\.[[:digit:]]{1,3}){3}$'
user_re='^[abcdefghijklmnopqrstuvwxyz_][abcdefghijklmnopqrstuvwxyz0123456789_-]*$'
[[ $HOST_IP =~ $ip_re ]] || { echo "✗ HOST_IP n'est pas une adresse IPv4 : rien ne part vers Imladris" >&2; exit 1; }
[[ $HOST_USER =~ $user_re ]] || { echo "✗ HOST_USER n'est pas un nom d'utilisateur Unix : rien ne part vers Imladris" >&2; exit 1; }

# The form print gives, word for word:
#   -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<path> -o HostKeyAlgorithms=ssh-ed25519
#   [-i <path> -o IdentitiesOnly=yes]
pinned_form() {
  # shellcheck disable=SC2086
  set -- $SSH_OPTS
  [ "$#" -eq 6 ] || [ "$#" -eq 10 ] || return 1
  [ "$1 $2" = "-o StrictHostKeyChecking=yes" ] || return 1
  [ "$3" = -o ] && case "$4" in UserKnownHostsFile=*) plain_path "${4#UserKnownHostsFile=}" ;; *) false ;; esac || return 1
  [ "$5 $6" = "-o HostKeyAlgorithms=ssh-ed25519" ] || return 1
  [ "$#" -eq 6 ] || { [ "$7" = -i ] && plain_path "$8" && [ "$9 ${10}" = "-o IdentitiesOnly=yes" ]; }
}
if ! pinned_form; then
  echo "✗ SSH_OPTS n'est pas la forme que calcule le Makefile (-o StrictHostKeyChecking=yes" \
       "-o UserKnownHostsFile=… -o HostKeyAlgorithms=ssh-ed25519, puis -i … -o IdentitiesOnly=yes ;" \
       "un chemin n'y a que lettres, chiffres et -_./~@+, sans accent sous la locale C) :" \
       "rien ne part vers Imladris" >&2
  exit 1
fi

# The known_hosts the options name, as ssh reads it (a leading ~ is the account's home).
# shellcheck disable=SC2086
set -- $SSH_OPTS
known=${4#UserKnownHostsFile=}
case "$known" in "~/"*) known="${HOME:-}/${known#\~/}" ;; esac
dedicated() {
  [ -f "$known" ] && [ -s "$known" ] || return 1
  # -ef: the same file, through any link.
  if [ "$known" -ef "${HOME:-/nonexistent}/.ssh/known_hosts" ] || [ "$known" -ef /etc/ssh/ssh_known_hosts ]; then
    return 1
  fi
  ssh-keygen -F "$HOST_IP" -f "$known" >/dev/null 2>&1
}
if ! dedicated; then
  echo "✗ UserKnownHostsFile=$known : pas le known_hosts dédié d'Imladris (un fichier, non vide, ni" \
       "~/.ssh/known_hosts ni /etc/ssh/ssh_known_hosts, qui tient la clé de $HOST_IP vérifiée par son" \
       "empreinte : make imladris-known l'écrit) : rien ne part vers Imladris" >&2
  exit 1
fi
exit 0
