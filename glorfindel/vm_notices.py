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

**It decides nothing.** The watch writes it, but the console and the bot mount `~/.glorfindel`
writable too (docs/design/file-actions-signee.md §1.5): a writer of theirs could add a notice, or
remove one. So a notice only tells whether a closure was said — never an outcome: the cut's
outcome is the one read on Azure, written in the isolation's state (glorfindel/drain_watch.py).
Forged, a notice can silence a closure (its key taken first) or have one said twice (its line
removed), or have the bot post an escaped text in a VM's thread; never declare a session cut (DRN2
review; docs/design/modele-de-menace.md, until FS1f). A store unreadable (bytes that are not
UTF-8) is read line by line, what does not read skipped: a closure may be said twice, never block
the follow of the cuts.

**An autonomous action's announcement** (JUG1, #760) goes the same way: `escalations.notify_action`
says it under the action's key (`escalations.executed_key`), kind `autonomous_action` — the bot
posts it in the VM's thread, beside the action's card to judge; without the bot, the webhook carries
it as it always did (its own message, `webhook`), the card's own notification quiet. Forged, a notice
of that key silences the announcement, never the card: the card decides on its own store.

**The bot mute, the webhook says it** (JUG2, #765). The bot configured but its container stopped, the
announcement waited for it, and a notice older than 24 h was lost. The bot now writes its heartbeat at
each turn (glorfindel/bot_beat.py); the watch reads it:

- **before saying an action** (`say`): the bot mute (no beat, or one older than
  `bot_beat.MUTE_AFTER_S`) and a webhook set, the notice is recorded `via: webhook`, `relayed`
  (when, why, whether it pinged), and the webhook says it in the channel — on a Discord webhook by
  Discord's own endpoint, the role `DISCORD_PING_ROLE` pinged, no other mention allowed
  (`allowed_mentions`), the text escaped as the bot escapes it; on another (Slack, Teams), its
  Slack message, no ping (a Discord role means nothing there);
- **at the passes after** (`relay_pass`, the watch's housekeeping, every ~1 min): a notice of an
  action left to the bot that the bot has not posted (its key absent from `bot_notices_posted.json`)
  goes by the webhook the same way when the bot reads mute — or, whatever its beat says, once it is
  older than `CONFIRM_S` (10 min): a beat forged fresh only delays. Within 24 h, as the bot's own.

Once per action: the notice rewritten `via: webhook` before the webhook is called, the bot never
posts it (`for_bot`, and read again before it posts one), after its return too. The card to judge
is the bot's to post at its return, in the VM's thread, with its buttons — without the ping when the
webhook pinged for it (`relayed_ping`). The webhook pings no one when the bot posted the card already
(its id in `bot_posted.json`): one ping per action. These two stores of the bot, and its beat,
decide only the announcement's path and its ping — never the card, written first, nor any state
(DRN2).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_STORE = Path.home() / ".glorfindel" / "vm_notices.jsonl"
# JUG2: what the bot posted, read by the watch to know what it still has to say — the bot's own
# stores (glorfindel/bot.py, `_NOTICES_POSTED_STORE`, `_POSTED_STORE`), the same files.
_BOT_NOTICES_POSTED = Path.home() / ".glorfindel" / "bot_notices_posted.json"
_BOT_CARDS_POSTED = Path.home() / ".glorfindel" / "bot_posted.json"
# The kind of an autonomous action's announcement (escalations.EXECUTED_TYPE).
ACTION_KIND = "autonomous_action"
# An announcement left to the bot and still not posted this long after goes by the webhook, whatever
# the bot's beat says (JUG2): a beat forged fresh delays the announcement, never silences it.
CONFIRM_S = 600
# As the bot (glorfindel/bot.py, `_NOTICE_MAX_AGE_H`): an older announcement is not said late.
RELAY_MAX_AGE_H = 24
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
    # Bytes that are not UTF-8 (a store damaged or written by another hand) never stop a reader:
    # replaced, their line no longer reads as JSON and is skipped (DRN2 review).
    for line in _STORE.read_bytes().decode("utf-8", errors="replace").splitlines():
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
        detail: dict | None = None, webhook: dict | None = None) -> str:
    """Say `text` of `resource_id`'s VM once for `key`: where it went (`bot`, `webhook`, `none`), or
    `already` when that key was said. Raises OSError when the store cannot be written (a full disk):
    the caller says it again at its next pass. `detail`: what it says, for the console — never read
    back as an outcome. `webhook`: the webhook's message when the caller has its own (an autonomous
    action's announcement, as it always was: JUG1), else `webhook_payload`."""
    notice = {"key": key, "resource_id": resource_id, "kind": kind, "title": title, "text": text,
              "level": level if level in LEVELS else "unknown", "via": _where(),
              "at": datetime.now(timezone.utc).isoformat()}
    if detail:
        notice["detail"] = detail
    why = relay_reason() if notice["via"] == "bot" and kind == ACTION_KIND else ""
    if why:
        _mark_relayed(notice, why)
    if not _record(notice):
        return "already"
    if why:
        post_webhook(*fallback(notice))
        return "relayed"
    if notice["via"] == "webhook":
        post_webhook(webhook or webhook_payload(notice), key)
    return notice["via"]


# ── JUG2 (#765): the bot mute, the webhook says the action ──────────────────────────────────────

def relay_reason(now: datetime | None = None) -> str:
    """Why an autonomous action's announcement goes by the webhook rather than the bot — the bot
    configured, a webhook set, and the bot mute (glorfindel/bot_beat.py: `absent`, `stale`…) — or ""."""
    from glorfindel import bot_beat
    from glorfindel.escalations import discord_bot_configured
    if not (discord_bot_configured() and os.environ.get("GLORFINDEL_WEBHOOK_URL", "")):
        return ""
    return bot_beat.mute(now)


def _ping_role() -> str:
    role = os.environ.get("DISCORD_PING_ROLE", "").strip()
    return role if role.isdigit() else ""


def _discord_url(url: str) -> str:
    """A Discord webhook's own endpoint (its `/slack` or `/github` suffix taken off), or "" when
    `url` is not a Discord webhook."""
    from urllib.parse import urlsplit, urlunsplit
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError:
        return ""
    if parts.scheme != "https" or not (host in ("discord.com", "discordapp.com")
                                       or host.endswith((".discord.com", ".discordapp.com"))):
        return ""
    path = parts.path.rstrip("/")
    if not path.startswith("/api/webhooks/"):
        return ""
    for suffix in ("/slack", "/github"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


def _card_posted(card: str) -> bool:
    """The bot posted this card already (its id in its `bot_posted.json`): its ping went."""
    if not card:
        return False
    try:
        return card in {str(i) for i in json.loads(_BOT_CARDS_POSTED.read_text())}
    except (OSError, ValueError, TypeError):
        return False


def _bot_posted_notices() -> set[str]:
    try:
        return {str(k) for k in json.loads(_BOT_NOTICES_POSTED.read_text())}
    except (OSError, ValueError, TypeError):
        return set()


def _mark_relayed(notice: dict, why: str, now: datetime | None = None) -> None:
    """The notice goes by the webhook: said so in it, with whether the role is pinged — a Discord
    webhook, a role set, the card not already posted by the bot (one ping per action)."""
    ping = bool(_ping_role() and _discord_url(os.environ.get("GLORFINDEL_WEBHOOK_URL", ""))
                and not _card_posted(str((notice.get("detail") or {}).get("card") or "")))
    notice["via"] = "webhook"
    notice["relayed"] = {"at": (now or datetime.now(timezone.utc)).isoformat(), "why": why, "ping": ping}


_RELAY_LINE = ("Le bot Discord se tait : annoncée ici par le webhook. La carte à juger est dans la "
               "console (TO JUDGE), et dans le fil de la VM au retour du bot.")


def fallback(notice: dict) -> tuple[dict, str, str]:
    """(payload, key, url) of a relayed announcement. A Discord webhook: Discord's own endpoint, the
    bot's message (every outside word escaped, SEC6), the role first when it is pinged, no other
    mention allowed. Another webhook: its Slack message, no mention."""
    url = os.environ.get("GLORFINDEL_WEBHOOK_URL", "")
    native = _discord_url(url)
    if not native:
        payload = webhook_payload(notice)
        payload["text"] += f"\n> {_RELAY_LINE}"
        return payload, notice["key"], url
    role = _ping_role() if (notice.get("relayed") or {}).get("ping") else ""
    head = f"<@&{role}> " if role else ""
    body = bot_message(notice)[: 1900 - len(head) - len(_RELAY_LINE)]
    return ({"content": f"{head}{body}\n*{_RELAY_LINE}*",
             "allowed_mentions": {"parse": [], "roles": [role] if role else []}}, notice["key"], native)


def relay_pass(now: datetime | None = None) -> int:
    """At the watch's housekeeping: each announcement of an action left to the bot and not posted by
    it, said by the webhook when the bot reads mute, or once it waited `CONFIRM_S` — once, marked
    before the webhook is called. Within `RELAY_MAX_AGE_H`. Returns the number said."""
    from datetime import timedelta

    from glorfindel.escalations import discord_bot_configured
    if not (discord_bot_configured() and os.environ.get("GLORFINDEL_WEBHOOK_URL", "")):
        return 0
    if not _STORE.exists():
        return 0
    from glorfindel import bot_beat
    from glorfindel.response.state import _atomic_write_text
    now = now or datetime.now(timezone.utc)
    mute = bot_beat.mute(now)
    posted = _bot_posted_notices()
    due: list[dict] = []
    with _lock():
        notices = _read()
        for n in notices:
            if n.get("kind") != ACTION_KIND or n.get("via") != "bot" or n["key"] in posted:
                continue
            try:
                at = datetime.fromisoformat(str(n.get("at")))
            except ValueError:
                continue
            at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
            if at < now - timedelta(hours=RELAY_MAX_AGE_H):
                continue
            why = mute or ("unconfirmed" if (now - at).total_seconds() >= CONFIRM_S else "")
            if why:
                _mark_relayed(n, why, now)
                due.append(n)
        if due:
            _atomic_write_text(_STORE, "\n".join(json.dumps(n, default=str) for n in notices) + "\n")
    for n in due:
        post_webhook(*fallback(n))
    return len(due)


def relay(notice: dict, why: str) -> None:
    """An announcement the store could not keep (a full disk), the bot mute: said by the webhook now,
    as `relay_pass` would — nothing recorded, so nothing tells the bot at its return (its card, if
    written, pings again)."""
    _mark_relayed(notice, why)
    post_webhook(*fallback(notice))


def relayed_ping(keys) -> bool:
    """The webhook pinged the role for one of these actions (`relayed.ping`): the card the bot posts
    at its return pings no more."""
    wanted = {k for k in (keys or []) if isinstance(k, str)}
    return bool(wanted) and any((n.get("relayed") or {}).get("ping") is True
                                for n in _read() if n["key"] in wanted)


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


def post_webhook(payload: dict, key: str = "", url: str = "") -> None:
    """`payload` to `url` (GLORFINDEL_WEBHOOK_URL when none), once: a webhook that fails is not retried."""
    url = url or os.environ.get("GLORFINDEL_WEBHOOK_URL", "")
    if not url:
        return
    try:
        import requests
        requests.post(url, json=payload, timeout=5)
    except Exception as exc:          # a notification never stops the watch
        log.warning("notice %s: webhook failed (%s)", key, exc)
