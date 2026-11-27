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
#   CLAUDE_BIN         claude's path; by default what `command -v claude` finds. Never inside an editor's
#                      extension (~/.vscode-server/extensions/, ~/.vscode/extensions/,
#                      ~/.cursor-server/extensions/): its path changes at each update of the extension, and
#                      the timer would lose it. install refuses it; DRY_RUN=1 says it (NOC1c).
#
# The subscription, never an API key (NOC1c, #1276): the unit unsets the key's variables
# (UnsetEnvironment), and install refuses a settings file the pass reads that sets one, or an
# apiKeyHelper (a settings file's env block passes before the shell's); DRY_RUN=1 says it.
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

# The PATH written into the unit: each directory once, in its first place (claude often lives in
# ~/.local/bin, which comes first anyway).
dedupe_path() {
  local out="" d parts
  IFS=: read -ra parts <<< "$1"
  for d in "${parts[@]}"; do
    [ -n "${d}" ] || continue
    case ":${out}:" in
      *":${d}:"*) ;;
      *) out="${out:+${out}:}${d}" ;;
    esac
  done
  printf '%s' "${out}"
}

# A refusal of install, said as a warning under DRY_RUN=1 (which writes nothing anyway).
refuse() {
  if [ "${DRY_RUN:-}" = 1 ]; then
    echo "night-install: ⚠ $* (DRY_RUN=1: said, not refused)" >&2
  else
    die "$*"
  fi
}

# claude inside an editor's extension: a versioned directory, gone at the extension's next update.
check_claude_path() {
  local p
  for p in "${CLAUDE}" "$(readlink -f "${CLAUDE}" 2>/dev/null || true)"; do
    case "${p}" in
      "${HOME}/.vscode-server/extensions/"*|"${HOME}/.vscode/extensions/"*|"${HOME}/.cursor-server/extensions/"*)
        refuse "claude is ${p}, inside an editor's extension: its path changes at each update of the extension and the timer would lose it. Install the CLI apart (curl -fsSL https://claude.ai/install.sh | bash puts it in ~/.local/bin/claude), then run again, or give CLAUDE_BIN=~/.local/bin/claude (docs/sessions.md, the night)"
        return 0 ;;
    esac
  done
}

# The variables the unit unsets, read from the unit itself: one list, one place.
AUTH_KEYS="$(sed -n 's/^UnsetEnvironment=//p' "${HERE}/eregion-night.service")"

# A settings file the pass reads that sets a key's variable (its env block passes before the shell's), or
# an apiKeyHelper: the pass would be billed on that key. Only the names are said, never a value.
check_settings_keys() {
  local f names alt
  alt="$(printf '%s' "apiKeyHelper ${AUTH_KEYS}" | tr ' ' '|')"
  for f in "${HOME}/.claude/settings.json" "${REPO}/.claude/settings.json" "${REPO}/.claude/settings.local.json"; do
    [ -f "${f}" ] || continue
    names="$(grep -oE "\"(${alt})\"[[:space:]]*:" "${f}" | grep -oE '[A-Za-z_]+' | sort -u | tr '\n' ' ' || true)"
    [ -z "${names}" ] || refuse "${f} sets ${names% }: the pass would run on that key, not on the subscription (docs/sessions.md, the night). Take it out of that file"
  done
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
  check_claude_path
  check_settings_keys
  UNIT_PATH="$(dedupe_path "${HOME}/.local/bin:$(dirname "${CLAUDE}"):/usr/local/bin:/usr/bin:/bin")"
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
