#!/bin/bash
# sudo_from_workstation.sh — `make imladris-cd-enable`, `-cd-disable`, `-cd-uninstall` (H1, #244): from
# the maintainer's workstation, with his access to Imladris, the CD's timer turned on or off, or the
# CD removed, by sudo on the VM, in a TTY (sudo may ask for the password). infra/glorfindel-host/README.md,
# « Le CD d'Imladris ».
#
# CDI2 (#922; Jonathan's decision of 19/11): the three recipes lived in the Makefile, which
# .github/CODEOWNERS does not own (decision of 18/11) — a change there changed what sudo runs on
# Imladris, without the approval of a code owner. They live here now, under /infra/glorfindel-host/cd/,
# owned with the rest of the CD, as the installation does (install_from_workstation.sh, CDI1); each
# target only checks Imladris's key (imladris-known), then calls this script.
#
#   HOST_IP=… HOST_USER=… SSH_OPTS="…" bash infra/glorfindel-host/cd/sudo_from_workstation.sh enable|disable|uninstall
#   … sudo_from_workstation.sh probe-enable|probe-disable   the model's probe's timer (HRN2, #1079)
#
# From the Makefile, what it computes — nothing recomputed here: HOST_IP (terraform output), HOST_USER,
# SSH_OPTS (HOST_SSH_OPTS, printed by infra/glorfindel-host/ssh_opts.sh). Checked before any gesture by
# ssh_opts.sh check, since the Makefile is not owned: the address, the user, the options word for word,
# the dedicated known_hosts they name (a file, not empty, holding Imladris's key) — a drift caught,
# never a hostile Makefile, that may not call this script at all (docs/design/modele-de-menace.md, §7).
#
# One gesture each, the one the recipe made, to the byte:
#   enable     sudo systemctl enable --now eregion-cd.timer && systemctl list-timers eregion-cd.timer --no-pager
#   disable    sudo systemctl disable --now eregion-cd.timer
#   uninstall  sudo bash .eregion-cd/install.sh --remove   (the probe's units too, HRN2)
#   probe-enable   sudo systemctl enable --now harness-probe.timer && systemctl list-timers harness-probe.timer --no-pager
#   probe-disable  sudo systemctl disable --now harness-probe.timer
# tests/unit/test_host_ssh_owned.py keeps them, against a fake ssh.
set -eu
set -f          # SSH_OPTS is split on blanks, never globbed: what the Makefile passes, as it was

case "${1:-}" in
  enable)    gesture='sudo systemctl enable --now eregion-cd.timer && systemctl list-timers eregion-cd.timer --no-pager' ;;
  disable)   gesture='sudo systemctl disable --now eregion-cd.timer' ;;
  uninstall) gesture='sudo bash .eregion-cd/install.sh --remove' ;;
  probe-enable)  gesture='sudo systemctl enable --now harness-probe.timer && systemctl list-timers harness-probe.timer --no-pager' ;;
  probe-disable) gesture='sudo systemctl disable --now harness-probe.timer' ;;
  *) echo "✗ sudo_from_workstation.sh : enable, disable, uninstall, probe-enable ou probe-disable, pas « ${1:-} » : rien ne part vers Imladris" >&2
     exit 2 ;;
esac

HOST_IP="${HOST_IP:-}"
[ -n "$HOST_IP" ] || { echo "Pas de VM : make imladris-up d'abord"; exit 1; }
target="imladris-cd-$1"
case "$1" in probe-*) target="imladris-$1" ;; esac
HOST_USER="${HOST_USER:?HOST_USER manque (make $target le passe)}"
SSH_OPTS="${SSH_OPTS:?SSH_OPTS manque (make $target le passe : la clé épinglée d’Imladris)}"
bash "$(dirname "$0")/../ssh_opts.sh" check "$HOST_IP" "$HOST_USER" "$SSH_OPTS" || exit 1

# shellcheck disable=SC2086  # SSH_OPTS: a word list, split as the Makefile split it
ssh -t $SSH_OPTS "$HOST_USER@$HOST_IP" "$gesture"
