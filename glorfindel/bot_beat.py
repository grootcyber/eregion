"""The Discord bot's heartbeat: the bot writes it at each turn, the watch reads it before an autonomous
action's announcement goes to the bot (JUG2, #765).

Since JUG1 (#760) an action taken alone is announced in its VM's thread when the bot is configured —
nothing by the webhook. The bot's container stopped, nothing said it any more: its card and its
notice waited for the bot, and a notice older than 24 h was lost. Now the bot writes
`~/.glorfindel/bot_heartbeat.json` (`{"at": …}`) at each turn of its loop (every 5 s, once its
channel is read), removes it when it stops — a SIGTERM too (`docker stop`: glorfindel/bot.py,
`_stop_on_sigterm`); a SIGKILL or a host cut leave it, and the fallback then waits for it to age
(`MUTE_AFTER_S`, then the watch's next pass) — and the watch reads it:

- **alive**: dated less than `MUTE_AFTER_S` ago (180 s, some 36 turns: a turn held by Discord's rate
  limits stays alive) — the announcement goes to the bot, as in JUG1;
- **mute**: absent, older, unreadable, or dated in the future beyond `FUTURE_SLACK_S` — the watch
  announces the action by the webhook (glorfindel/vm_notices.py, `say` and `relay_pass`).

**It decides only the announcement's path.** The bot and the console mount `~/.glorfindel` writable
(docs/design/file-actions-signee.md §1.5): a beat forged fresh holds the announcement for the bot —
for `MUTE_AFTER_S` once written, for `vm_notices.CONFIRM_S` at most if a writer keeps it fresh (an
announcement the bot has not posted by then goes by the webhook whatever the beat says); a beat dated
in the future reads mute. A beat removed or aged sends the announcement by the webhook while the bot
lives: in the channel rather than the thread, and the bot does not post it a second time (save a
post of the bot in flight at that moment: vm_notices.py, its known limits). Never the
card to judge, written before any beat is read, nor any state: the watch's alone (DRN2).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_STORE = Path.home() / ".glorfindel" / "bot_heartbeat.json"
# A bot silent this long is mute: its turn is 5 s (glorfindel/bot.py, `_watch_escalations`).
MUTE_AFTER_S = 180
# A beat dated after now by more than this is not a beat: a forged one would hold the fallback forever.
FUTURE_SLACK_S = 30


def write(now: datetime | None = None) -> None:
    """The bot's beat, written whole (a temp file renamed over it): never read cut."""
    from glorfindel.response.state import _atomic_write_text
    at = now or datetime.now(timezone.utc)
    _atomic_write_text(_STORE, json.dumps({"at": at.isoformat()}))


def clear() -> None:
    """The bot stopping: its beat removed, the watch reads it mute at once. Never an error."""
    try:
        _STORE.unlink(missing_ok=True)
    except OSError:
        pass


def mute(now: datetime | None = None) -> str:
    """Why the bot is mute (`absent`, `unreadable`, `stale`, `future`), or "" when it is alive."""
    now = now or datetime.now(timezone.utc)
    try:
        raw = _STORE.read_bytes()
    except FileNotFoundError:
        return "absent"
    except OSError:
        return "unreadable"
    try:
        at = datetime.fromisoformat(str(json.loads(raw.decode("utf-8", errors="replace"))["at"]))
    except (ValueError, TypeError, KeyError):
        return "unreadable"
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    age = (now - at).total_seconds()
    if age < -FUTURE_SLACK_S:
        return "future"
    return "stale" if age > MUTE_AFTER_S else ""
