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
# SSH_OPTS (HOST_SSH_OPTS, printed by infra/glorfindel-host/ssh_opts.sh: the pinned key,
# StrictHostKeyChecking=yes on HOST_KNOWN_HOSTS alone), CD_FILES (HOST_CD_FILES). Checked before any
# gesture, since the Makefile is not owned: SSH_OPTS by ssh_opts.sh check (the form it prints, word for
# word, and the dedicated known_hosts it names: CDI2), CD_FILES against the list owned here (OWNED_FILES) —
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
SSH_OPTS="${SSH_OPTS:?SSH_OPTS manque (make imladris-cd-install le passe : la clé épinglée d’Imladris)}"
CD_FILES="${CD_FILES:?CD_FILES manque (make imladris-cd-install le passe)}"
# V-32 (SEC-C): the address, the user and SSH_OPTS checked by infra/glorfindel-host/ssh_opts.sh, owned
# too (CDI2, #922), before any gesture — the address an IPv4 address and the user a Unix user name
# (« user@address » is ssh's last word before the command: a user « -oProxyCommand=… » arrives as an
# option, review of CDI1, round 2); the options the form it prints for the Makefile, word for word (ssh
# keeps the first value of an option: a check for « =yes » somewhere let « -o StrictHostKeyChecking=no »
# before it through, review of CDI1); the known_hosts they name, the dedicated one, a file, not empty,
# holding Imladris's key (CDI2). What it holds: a drift, visible there. Not a hostile Makefile: it may
# not call this script at all (docs/design/modele-de-menace.md, §7).
HERE=$(dirname "$0")
bash "$HERE/../ssh_opts.sh" check "$HOST_IP" "$HOST_USER" "$SSH_OPTS" || exit 1

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
