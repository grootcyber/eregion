"""What the watch says of a VM outside a card: a notice, once per key, in the VM's Discord thread
when the bot is configured, else by the webhook (DRN2, #754).

On the bench, 12/11, the session cut of gondolin's isolation ran 304 s on Azure: the autonomous
isolation's notification said « coupure en attente … suivie », the reassertion read it drained at
the next pass — and no message ever said so. A notice closes what an announcement left open:

- **once per key** (`key`: what it closes, its nonce in it — the cut's `asked_at`): recorded in
  `~/.glorfindel/vm_notices.jsonl` before it goes anywhere; a second `say` of the same key says
  nothing, after a restart of the watch too. At most once: a webhook that fails is not retried.
- **where**: the bot configured (`escalations.discord_bot_configured`), the bot posts it in the
  VM's thread (glorfindel/bot.py, `_post_notices`: the notices it posted kept in
  `bot_notices_posted.json`); else the webhook (GLORFINDEL_WEBHOOK_URL); neither, it is recorded
  only (`via: none`), and what it says stays on the console's card.
- **what**: a title and a text written by Glorfindel, with names from Azure (a VM's, a status) —
  made inert at the post (glorfindel/chat_text.py, SEC6), never before: the store keeps the text.

The store is written by the watch only; the console and the bot mount `~/.glorfindel` writable
too, so a notice there is as trusted as a card of the escalations' store (the same frontier,
docs/design/modele-de-menace.md). JUG1 puts the autonomous actions' announcements in the VM's
thread the same way: `say(resource_id, key, kind, title, text, level)`.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_STORE = Path.home() / ".glorfindel" / "vm_notices.jsonl"
# The notices kept, newest last: a key older than these could be said again — a cut's closure is
# written in the isolation's state long before (glorfindel/drain_watch.py).
KEPT = 500
# What a notice's level shows: (Discord, the webhook's Slack format).
LEVELS = {"ok": ("✅", ":white_check_mark:"), "failed": ("🚨", ":rotating_light:"),
          "unknown": ("⚠️", ":warning:")}


def _lock():
    from glorfindel.response.locks import _file_lock
    return _file_lock(_STORE.with_name(_STORE.name + ".lock"))


def _read() -> list[dict]:
    if not _STORE.exists():
        return []
    out = []
    for line in _STORE.read_text().splitlines():
        try:
            n = json.loads(line)
        except ValueError:
            continue
        if isinstance(n, dict) and isinstance(n.get("key"), str):
            out.append(n)
    return out


def said(key: str) -> dict | None:
    """The notice recorded under `key`, or None."""
    return next((n for n in _read() if n["key"] == key), None)


def _record(notice: dict) -> bool:
    """Under the store's lock: the notice appended, False when its key is already there."""
    from glorfindel.response.state import _atomic_write_text
    with _lock():
        notices = _read()
        if any(n["key"] == notice["key"] for n in notices):
            return False
        notices = (notices + [notice])[-KEPT:]
        _atomic_write_text(_STORE, "\n".join(json.dumps(n, default=str) for n in notices) + "\n")
    return True


def _where() -> str:
    from glorfindel.escalations import discord_bot_configured
    if discord_bot_configured():
        return "bot"
    return "webhook" if os.environ.get("GLORFINDEL_WEBHOOK_URL", "") else "none"


def say(resource_id: str, key: str, kind: str, title: str, text: str, level: str = "unknown",
        detail: dict | None = None) -> str:
    """Say `text` of `resource_id`'s VM once for `key`: where it went (`bot`, `webhook`, `none`), or
    `already` when that key was said. Raises OSError when the store cannot be written (a full disk):
    the caller says it again at its next pass. `detail`: what the caller reads back of it (a cut's
    outcome, after a restart)."""
    notice = {"key": key, "resource_id": resource_id, "kind": kind, "title": title, "text": text,
              "level": level if level in LEVELS else "unknown", "via": _where(),
              "at": datetime.now(timezone.utc).isoformat()}
    if detail:
        notice["detail"] = detail
    if not _record(notice):
        return "already"
    if notice["via"] == "webhook":
        _post_webhook(notice)
    return notice["via"]


def for_bot() -> list[dict]:
    """The notices the bot posts, oldest first."""
    return [n for n in _read() if n.get("via") == "bot"]


def _short(resource_id) -> str:
    return str(resource_id or "").rstrip("/").rsplit("/", 1)[-1] or "?"


def bot_message(notice: dict) -> str:
    """The notice as the bot posts it in the VM's thread: every outside word escaped (SEC6)."""
    from glorfindel.chat_text import discord_code, discord_text
    icon = LEVELS.get(notice.get("level"), LEVELS["unknown"])[0]
    return (f"{icon} **{discord_text(notice.get('title', ''))}** · {discord_code(_short(notice.get('resource_id')))}\n"
            f"> {discord_text(' '.join(str(notice.get('text', '')).split())[:1500])}")


def webhook_payload(notice: dict) -> dict:
    """The notice in the webhook's (Slack) format: one line each, no link nor mention (SEC6)."""
    from glorfindel.chat_text import webhook_code, webhook_text
    icon = LEVELS.get(notice.get("level"), LEVELS["unknown"])[1]
    return {"text": (f"{icon} *{webhook_text(notice.get('title', ''))}*  |  "
                     f"`{webhook_code(_short(notice.get('resource_id')))}`\n"
                     f"> {webhook_text(str(notice.get('text', ''))[:800])}")}


def _post_webhook(notice: dict) -> None:
    url = os.environ.get("GLORFINDEL_WEBHOOK_URL", "")
    if not url:
        return
    try:
        import requests
        requests.post(url, json=webhook_payload(notice), timeout=5)
    except Exception as exc:          # a notification never stops the watch
        log.warning("notice %s: webhook failed (%s)", notice.get("key"), exc)
