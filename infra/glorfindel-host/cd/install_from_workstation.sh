#!/bin/bash
# install_from_workstation.sh — `make imladris-cd-install` (H1, #244): from the maintainer's
# workstation, with his access to Imladris, the CD's agent copied to ~/.eregion-cd/ on the VM, and its
# systemd units installed there with sudo (install.sh). infra/glorfindel-host/README.md, « Le CD
# d'Imladris ».
#
# CDI1 (#918; Jonathan's decision of 18/11): the recipe lived in the Makefile, which .github/CODEOWNERS
# does not own — a change there changed what goes to Imladris and what sudo runs there, without the
# approval of a code owner. It lives here now, under /infra/glorfindel-host/cd/, owned with the rest;
# the target only checks Imladris's key (imladris-known), then calls this script.
#
#   HOST_IP=… HOST_USER=… SSH_OPTS="…" CD_FILES="…" bash infra/glorfindel-host/cd/install_from_workstation.sh
#
# From the Makefile, what it computes — nothing recomputed here: HOST_IP (terraform output), HOST_USER,
# SSH_OPTS (HOST_SSH_OPTS: the pinned key, StrictHostKeyChecking=yes on HOST_KNOWN_HOSTS alone),
# CD_FILES (HOST_CD_FILES). Two of them checked before any gesture, since the Makefile is not owned:
# SSH_OPTS must be the form it computes, word for word, CD_FILES the list owned here (OWNED_FILES) —
# a drift caught, never a hostile Makefile, that may not call this script at all. Run from the root of
# the checkout, as make runs it: CD_FILES and `git rev-parse HEAD` are read there.
#
# The gestures, in this order, each stopping the installation when it fails, as the recipe did:
#   1. #deploy's webhook and the mention, read here (eregion_cd.py export-discord-env) — never the bot's token;
#   2. ~/.eregion-cd created on Imladris, 700;
#   3. the files copied there (scp);
#   4. cosign (CI3: published_image.py, version and sha256 pinned) downloaded by the VM itself, from
#      sigstore's release on GitHub, and kept only if its sha256 is the pinned one;
#   5. discord.env written under umask 077, from stdin;
#   6. installed-from: the commit installed from (git rev-parse HEAD) — a failed rev-parse writes it
#      empty and goes on, as the recipe did (no pipefail): the agent then says once in #deploy that it
#      cannot tell when to update itself;
#   7. sudo bash .eregion-cd/install.sh, in a TTY (sudo may ask for the password).
# tests/unit/test_host_cd_install.py keeps them, against a fake ssh and a fake scp.
set -eu
set -f          # the lists below are split on blanks, never globbed: what the Makefile passes, as it was

HOST_IP="${HOST_IP:-}"
[ -n "$HOST_IP" ] || { echo "Pas de VM : make imladris-up d'abord"; exit 1; }
HOST_USER="${HOST_USER:?HOST_USER manque (make imladris-cd-install le passe)}"
# The address and the user go into « user@address », ssh's last word before the command: a user
# « -oProxyCommand=… » arrives as an option (review of CDI1, round 2). Their forms only, in ASCII
# whatever the locale: an IPv4 address (terraform output, as the Makefile greps it), a Unix user name.
ip_re='^[[:digit:]]{1,3}(\.[[:digit:]]{1,3}){3}$'
user_re='^[abcdefghijklmnopqrstuvwxyz_][abcdefghijklmnopqrstuvwxyz0123456789_-]*$'
[[ $HOST_IP =~ $ip_re ]] || { echo "✗ HOST_IP n'est pas une adresse IPv4 : rien ne part vers Imladris" >&2; exit 1; }
[[ $HOST_USER =~ $user_re ]] || { echo "✗ HOST_USER n'est pas un nom d'utilisateur Unix : rien ne part vers Imladris" >&2; exit 1; }
SSH_OPTS="${SSH_OPTS:?SSH_OPTS manque (make imladris-cd-install le passe : la clé épinglée d’Imladris)}"
CD_FILES="${CD_FILES:?CD_FILES manque (make imladris-cd-install le passe)}"
# V-32 (SEC-C): SSH_OPTS taken only in the form the Makefile computes (HOST_SSH_OPTS), word for word:
#   -o StrictHostKeyChecking=yes -o UserKnownHostsFile=<path> -o HostKeyAlgorithms=ssh-ed25519
#   [-i <path> -o IdentitiesOnly=yes]
# Anything else refuses, before any gesture: ssh keeps the first value of an option, so a check for
# « =yes » somewhere let « -o StrictHostKeyChecking=no » before it through (review of CDI1), and so
# would any other option added (-F, ProxyCommand, ProxyJump, KnownHostsCommand…). What it holds: a
# drift of the options, visible here. Not a hostile Makefile: it chooses the known_hosts file, it runs
# the key's check (imladris-known, infra/glorfindel-host/known_host.sh, neither owned), and it may not
# call this script at all (docs/design/modele-de-menace.md, §7).
plain_path() { case "$1" in '' | -* | *[!-[:alnum:]_./~@+]*) return 1 ;; esac; }
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
# What goes to ~/.eregion-cd/: this list, owned here, the Makefile's HOST_CD_FILES checked against it,
# never taken as it comes. scp copies by base name: a list from elsewhere could put any file of the
# checkout under an agent's name, or one that Python imports before the standard library next to
# eregion_cd.py — run by the timer. A file added to the CD is added here, in an owned pull request.
OWNED_FILES="infra/glorfindel-host/cd/eregion_cd.py infra/glorfindel-host/cd/install.sh \
infra/glorfindel-host/cd/eregion-cd.service infra/glorfindel-host/cd/eregion-cd.timer \
infra/glorfindel-host/deploy.sh scripts/notify_discord.py glorfindel/chat_text.py scripts/published_image.py"
# shellcheck disable=SC2086
[ "$(printf '%s ' $CD_FILES)" = "$OWNED_FILES " ] || {
  echo "✗ CD_FILES n'est pas la liste des fichiers du CD ($0, OWNED_FILES) : rien ne part vers Imladris" >&2
  exit 1
}
HERE=$(dirname "$0")
TO="$HOST_USER@$HOST_IP"

# shellcheck disable=SC2086  # SSH_OPTS and CD_FILES: word lists, split as the Makefile split them
on_imladris() { ssh $SSH_OPTS "$TO" "$1"; }

lines=$(python3 "$HERE/eregion_cd.py" export-discord-env) || exit 1
on_imladris 'mkdir -p .eregion-cd && chmod 700 .eregion-cd'
# shellcheck disable=SC2086
scp -q $SSH_OPTS $CD_FILES "$TO:.eregion-cd/"
on_imladris 'python3 .eregion-cd/published_image.py install-cosign .eregion-cd/cosign'
printf '%s\n' "$lines" | on_imladris 'umask 077 && cat > .eregion-cd/discord.env'
git rev-parse HEAD | on_imladris 'cat > .eregion-cd/installed-from'
# shellcheck disable=SC2086
ssh -t $SSH_OPTS "$TO" 'sudo bash .eregion-cd/install.sh'
