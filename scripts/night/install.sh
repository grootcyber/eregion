#!/usr/bin/env bash
# Eregion (NOC1, #1251) — the night's Orchestre on the workstation: a systemd --user timer at 05:30 UTC
# that runs Claude Code without a terminal (`claude -p "/elrond night"`) at the repository's root, where
# the App's identity, the worktrees and the elrond skill live (docs/sessions.md, « La nuit »).
#
#   bash scripts/night/install.sh [install]   write the units into ~/.config/systemd/user/, enable the timer
#   bash scripts/night/install.sh uninstall   stop and disable the timer, remove the units (the log stays)
#   bash scripts/night/install.sh status      the timer, the last pass, the end of its log
#
# Run again, `install` writes the units anew (a new mode, a new budget, claude moved) and reloads systemd.
# Jonathan's gesture, never a session's: install and uninstall refuse in an agent session
# (EREGION_AGENT_SESSION) and in a lot's worktree; status only reads. DRY_RUN=1 shows the units filled, writes nothing, starts nothing.
#
# The settings it reads (the environment, or `make night-install VAR=…`):
#   NIGHT_MODE         the permission mode of the pass: auto (recommended) or dontAsk. Never
#                      bypassPermissions: refused here, and the unit never names it.
#   NIGHT_BUDGET_USD   the pass's cap (claude --max-budget-usd), 30 by default.
#   CLAUDE_BIN         claude's path; by default what `command -v claude` finds.
set -euo pipefail

UNIT_DIR="${HOME}/.config/systemd/user"
STATE_DIR="${HOME}/.local/state/eregion-night"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
NAMES=(eregion-night.service eregion-night.timer)

die() { echo "night-install: $*" >&2; exit 1; }

guard() {
  [ -z "${EREGION_AGENT_SESSION:-}" ] || die "refused in an agent session (EREGION_AGENT_SESSION): Jonathan's gesture"
  case "${REPO}/" in
    */.claude/worktrees/*) die "refused in a lot's worktree (${REPO}): run it from the main checkout" ;;
  esac
}

# A value written into a unit: a plain path or word, never a space, a quote, a % or a $.
plain() {
  printf '%s' "$2" | grep -Eq '^[A-Za-z0-9/._+-]+$' || die "$1 is not a plain value: ${2}"
}

fill() {
  local src="$1"
  sed -e "s|@REPO@|${REPO}|g" -e "s|@CLAUDE@|${CLAUDE}|g" -e "s|@MODE@|${MODE}|g" \
      -e "s|@BUDGET@|${BUDGET}|g" -e "s|@PATH@|${UNIT_PATH}|g" "${src}"
}

install_units() {
  MODE="${NIGHT_MODE:-auto}"
  case "${MODE}" in
    auto|dontAsk) ;;
    *) die "NIGHT_MODE=${MODE}: auto or dontAsk only (never bypassPermissions; docs/sessions.md, the night)" ;;
  esac
  BUDGET="${NIGHT_BUDGET_USD:-30}"
  printf '%s' "${BUDGET}" | grep -Eq '^[1-9][0-9]{0,3}$' || die "NIGHT_BUDGET_USD=${BUDGET}: a whole number of dollars, 1 to 9999"
  CLAUDE="${CLAUDE_BIN:-$(command -v claude || true)}"
  [ -n "${CLAUDE}" ] && [ -x "${CLAUDE}" ] || die "claude not found: install Claude Code, or give CLAUDE_BIN=/path/to/claude"
  UNIT_PATH="${HOME}/.local/bin:$(dirname "${CLAUDE}"):/usr/local/bin:/usr/bin:/bin"
  for v in REPO CLAUDE UNIT_PATH; do plain "${v}" "${!v//:/}"; done
  [ -f "${REPO}/.claude/settings.local.json" ] \
    || echo "night-install: ⚠ ${REPO}/.claude/settings.local.json absent: the pass would run without the App's identity (docs/sessions.md, SEC12)" >&2
  if [ "${DRY_RUN:-}" = 1 ]; then
    for n in "${NAMES[@]}"; do
      echo "# ~/.config/systemd/user/${n} (DRY_RUN=1: nothing written, nothing started)"
      fill "${HERE}/${n}"
      echo
    done
    return 0
  fi
  mkdir -p "${UNIT_DIR}" "${STATE_DIR}"
  for n in "${NAMES[@]}"; do
    fill "${HERE}/${n}" > "${UNIT_DIR}/${n}.tmp"
    mv -f "${UNIT_DIR}/${n}.tmp" "${UNIT_DIR}/${n}"
  done
  systemctl --user daemon-reload
  systemctl --user enable --now eregion-night.timer
  echo "night-install: ✓ the timer is on (05:30 UTC), mode ${MODE}, cap ${BUDGET} \$; its log: ${STATE_DIR}/night.log"
  echo "night-install: under WSL, the pass runs only while the distribution runs (loginctl enable-linger, docs/sessions.md)"
}

uninstall_units() {
  if [ "${DRY_RUN:-}" = 1 ]; then
    echo "DRY_RUN=1: would stop and disable eregion-night.timer, then remove ${NAMES[*]} from ${UNIT_DIR}"
    return 0
  fi
  systemctl --user disable --now eregion-night.timer 2>/dev/null || true
  systemctl --user stop eregion-night.service 2>/dev/null || true
  for n in "${NAMES[@]}"; do rm -f "${UNIT_DIR}/${n}"; done
  systemctl --user daemon-reload
  echo "night-install: ✓ removed (the log stays: ${STATE_DIR}/night.log)"
}

status_units() {
  echo "timer: $(systemctl --user is-enabled eregion-night.timer 2>/dev/null || echo absent)"
  systemctl --user list-timers eregion-night.timer --no-pager 2>/dev/null | sed -n '1,2p' || true
  systemctl --user show eregion-night.service -p Result -p ExecMainStatus -p ExecMainExitTimestamp --no-pager 2>/dev/null || true
  if [ -f "${STATE_DIR}/night.log" ]; then
    tail -n 15 "${STATE_DIR}/night.log" | sed 's/^/  | /'
  else
    echo "no pass yet (${STATE_DIR}/night.log)"
  fi
}

case "${1:-install}" in
  install) guard; install_units ;;
  uninstall) guard; uninstall_units ;;
  status) status_units ;;
  *) die "install, uninstall or status" ;;
esac
