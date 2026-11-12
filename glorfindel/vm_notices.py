"""What the watch says of a VM outside a card: a notice, once per key, in the VM's Discord thread
when the bot is configured, else by the webhook (DRN2, #754).

On the bench, 12/11, the session cut of gondolin's isolation ran 304 s on Azure: the autonomous
isolation's notification said « coupure en attente … suivie », the reassertion read it drained at
the next pass — and no message ever said so. A notice closes what an announcement left open:

- **once per key** (`key`: what it closes, its nonce in it — the cut's `asked_at`): recorded in
  `~/.glorfindel/vm_notices.jsonl` before it goes anywhere; a second `say` of the same key says
  nothing, after a restart of the watch too. A webhook that fails is not tried again — a short 429
  waited for once (`_post`) — but where the bot is configured and mute (JUG2, JUG2b, below).
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

Once per action: the notice rewritten `via: webhook` before the webhook is called, the bot does
not post it (`for_bot`, and read again before it posts one), after its return too. The card to judge
is the bot's to post at its return, in the VM's thread, with its buttons — without the ping when the
webhook pinged for it (`relayed_ping`). The webhook pings no one when the bot posted the card already
(its id in `bot_posted.json`): one ping per action. These two stores of the bot, and its beat,
decide only the announcement's path and its ping — never the card, written first, nor any state
(DRN2).

**A webhook that fails is never counted as said** (JUG2 review). Only a 2xx answer is a post
(`_post`); then the notice is noted `relayed.sent`, and only a notice noted sent silences the card's
ping. Refused (a 404, a 500), unreachable, or rate limited (a 429 waited for once when it asks no
longer than `RETRY_MAX_S`), the notice goes back to the bot (`via: bot`, `relayed` removed): the next
pass tries again, or the bot posts it and its card pings at its return — a rare double rather than a
silence. A pass spaces its posts (`RELAY_SPACING_S`) and leaves the rest to the next one after a 429.
A mark never noted sent (the watch stopped mid-send, its note refused) is taken back after
`RESEND_AFTER_S`.

**A cut's closure falls back too** (JUG2b, #768, decided by Jonathan on 12/11): every closure of a
session cut (DRN2, kind `drain_closed`: drained, refused, sessions left open, never ended, no longer
followed — a drained one too) goes the same way as an action's announcement (`RELAY_KINDS`): the same
beat, the same passes, a webhook that fails gives it back to the bot, once per closure. **Never a
ping**: only an action taken alone pings (JUG1). It decides nothing either: the cut's outcome is the
one read on Azure, in the isolation's state.

**The fallback never holds the watch** (JUG2b). The watch runs `relay_pass` in a thread of its own
(glorfindel/cli.py, `_relay_notices`), one pass at a time (`_PASS`, and the thread not started again
while one runs): its loop — `runs/` read, its heartbeat, the reassertion, the TTL, « Verify » — never
waits for a webhook. Each POST is bounded: `CONNECT_TIMEOUT_S` to connect, `READ_TIMEOUT_S` to read,
and `POST_DEADLINE_S` for the whole of it, the name's resolution included (`_send`: the POST in a
thread its caller waits for). A pass stops at the first webhook rate limited or unreachable (no
answer, or none within the deadline): the rest goes back to the bot, or to the next pass; and it
starts no post once it has run `RELAY_PASS_BUDGET_S`. A pass therefore lasts at most the budget and
one notice — 0.5 s of spacing, a POST, a short 429's wait, a second POST: some 86 s, in its own
thread. **The tries of a notice are capped**: a post that went without an answer saying it was
refused (unreachable, a 5xx) may have been delivered — counted (`tries`, beside `relayed`, which goes
when the notice goes back to the bot; a mark taken back counts one too), and after `RELAY_MAX_TRIES`
the webhook says it no more: the notice waits for the bot. A refusal (a 4xx, a 429) delivered nothing
and counts none.

Known limits: a webhook that delivered but whose answer was lost has the notice said again, an
action's ping with it, `RELAY_MAX_TRIES` times at most; a network cut that long leaves it to the bot
(an action's card is in the console). A post abandoned at its deadline may still reach the webhook.
A post of the bot in flight while the watch relays (the beat aged, or `CONFIRM_S`
reached, during a `thread.send` held by Discord's rate limits) says the announcement twice, in the
thread and in the channel; the same race on the card's post can ping twice. A notice forged in the
store under an action's key, relayed and noted sent, silences the announcement and can silence the
card's ping too — never the card. A notice forged with its tries at the cap silences the fallback the
same way, never the bot's post.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
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
# The kind of a session cut's closure (glorfindel/drain_watch.py, DRN2).
CLOSURE_KIND = "drain_closed"
# What falls back on the webhook when the bot is mute: an action's announcement (JUG2), a cut's
# closure (JUG2b). Only the first pings.
RELAY_KINDS = (ACTION_KIND, CLOSURE_KIND)
# An announcement left to the bot and still not posted this long after goes by the webhook, whatever
# the bot's beat says (JUG2): a beat forged fresh delays the announcement, never silences it.
CONFIRM_S = 600
# As the bot (glorfindel/bot.py, `_NOTICE_MAX_AGE_H`): an older announcement is not said late.
RELAY_MAX_AGE_H = 24
# JUG2 review: between two relayed announcements of one pass (Discord's webhooks take some 5
# requests in 2 s); a 429 is waited for once when it asks no longer than RETRY_MAX_S, else the rest
# of the pass waits for the next one.
RELAY_SPACING_S = 0.5
RETRY_MAX_S = 5.0
# A notice marked relayed but never noted sent (the watch stopped mid-send, its note refused) is
# taken back this long after: said again rather than never.
RESEND_AFTER_S = 120
# JUG2b (#768): each POST bounded — to connect and to read (requests' own timeouts), and the whole of
# it, the name's resolution included, by the deadline its caller waits for (`_send`).
CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 5.0
POST_DEADLINE_S = 10.0
# A pass starts no post once it has run this long: the rest goes back to the bot, or the next pass.
RELAY_PASS_BUDGET_S = 60.0
# A relayed notice whose post may have been delivered without its answer (unreachable, a 5xx) is
# tried this many times at most: then it waits for the bot, no new webhook (an action's ping each try).
RELAY_MAX_TRIES = 3
# What a post answered: `sent` (2xx), `limited` (a 429 still refused), `refused` (another 4xx: nothing
# delivered), `failed` (a 5xx, an odd answer), `unreachable` (no answer, or none within the deadline).
# The last two may have been delivered: they count a try.
MAYBE_DELIVERED = ("failed", "unreachable")
_sleep = time.sleep
_monotonic = time.monotonic
_PASS = threading.Lock()        # one relay pass at a time, whoever calls it
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
    why = relay_reason() if notice["via"] == "bot" and kind in RELAY_KINDS else ""
    if why:
        _mark_relayed(notice, why)
    if not _record(notice):
        return "already"
    if why:
        # Sent, it is noted sent; refused or unreachable, the notice goes back to the bot — the
        # next pass tries again, or the bot posts it at its return (JUG2 review: never a silence).
        result = _post(*fallback(notice))
        _settle({key: result})
        return "relayed" if result == "sent" else "bot"
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
    if not re.match(r"/api(/v\d+)?/webhooks/", path):
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
    """The notice goes by the webhook: said so in it, with whether the role is pinged — an action's
    announcement only (a cut's closure never pings: JUG1, JUG2b), a Discord webhook, a role set, the
    card not already posted by the bot (one ping per action)."""
    ping = bool(notice.get("kind") == ACTION_KIND
                and _ping_role() and _discord_url(os.environ.get("GLORFINDEL_WEBHOOK_URL", ""))
                and not _card_posted(str((notice.get("detail") or {}).get("card") or "")))
    notice["via"] = "webhook"
    notice["relayed"] = {"at": (now or datetime.now(timezone.utc)).isoformat(), "why": why, "ping": ping}


_RELAY_LINE = ("Le bot Discord se tait : annoncée ici par le webhook. La carte à juger est dans la "
               "console (TO JUDGE), et dans le fil de la VM au retour du bot.")
# JUG2b: a cut's closure has no card to judge of its own — its isolation's card is in the console.
_CLOSURE_LINE = ("Le bot Discord se tait : dite ici par le webhook. L'isolement de la VM et ses cartes "
                 "sont dans la console.")


def _relay_line(notice: dict) -> str:
    return _RELAY_LINE if notice.get("kind") == ACTION_KIND else _CLOSURE_LINE


def fallback(notice: dict) -> tuple[dict, str, str]:
    """(payload, key, url) of a relayed announcement. A Discord webhook: Discord's own endpoint, the
    bot's message (every outside word escaped, SEC6), the role first when it is pinged, no other
    mention allowed. Another webhook: its Slack message, no mention."""
    url = os.environ.get("GLORFINDEL_WEBHOOK_URL", "")
    native = _discord_url(url)
    line = _relay_line(notice)
    if not native:
        payload = webhook_payload(notice)     # the card and the run first in its text (JUG2 review)
        payload["text"] += f"\n> {line}"
        return payload, notice["key"], url
    role = _ping_role() if (notice.get("relayed") or {}).get("ping") else ""
    head = f"<@&{role}> " if role else ""
    body = bot_message(notice)[: 1900 - len(head) - len(line)]
    return ({"content": f"{head}{body}\n*{line}*",
             "allowed_mentions": {"parse": [], "roles": [role] if role else []}}, notice["key"], native)


def relay_pass(now: datetime | None = None) -> int:
    """At the watch's housekeeping, in a thread of its own (JUG2b): each notice left to the bot and
    not posted by it — an action's announcement, a cut's closure (`RELAY_KINDS`) — said by the
    webhook when the bot reads mute, or once it waited `CONFIRM_S`; marked before the webhook is
    called, noted sent once the webhook answered 2xx; refused, unreachable or rate limited, given back
    to the bot (the next pass tries again, or the bot posts it at its return). Spaced by
    `RELAY_SPACING_S`; a webhook rate limited (a 429 that asks for longer than `RETRY_MAX_S`) or
    unreachable leaves the rest of the pass to the next one, and so does `RELAY_PASS_BUDGET_S` spent.
    A notice tried `RELAY_MAX_TRIES` times waits for the bot. A notice marked but never noted sent
    (`RESEND_AFTER_S`) is taken back first. Within `RELAY_MAX_AGE_H`. One pass at a time: called while
    another runs, it does nothing. Returns the number sent."""
    if not _PASS.acquire(blocking=False):
        return 0
    try:
        return _relay_pass(now)
    finally:
        _PASS.release()


def _tries(n: dict) -> int:
    """The posts of a relayed notice that may have been delivered (0 when unread)."""
    t = n.get("tries")
    return t if isinstance(t, int) and not isinstance(t, bool) and t > 0 else 0


def _relay_pass(now: datetime | None) -> int:
    from datetime import timedelta

    from glorfindel.escalations import discord_bot_configured
    if not (discord_bot_configured() and os.environ.get("GLORFINDEL_WEBHOOK_URL", "")):
        return 0
    if not _STORE.exists():
        return 0
    from glorfindel import bot_beat
    now = now or datetime.now(timezone.utc)
    mute = bot_beat.mute(now)
    posted = _bot_posted_notices()
    due: list[dict] = []
    with _lock():
        notices = _read()
        changed = False
        for n in notices:
            if n.get("kind") not in RELAY_KINDS:
                continue
            if _unsent_since(n, now) >= RESEND_AFTER_S:
                n["via"] = "bot"            # marked, never noted sent: weighed again below
                n.pop("relayed", None)
                n["tries"] = _tries(n) + 1  # its post may have gone (JUG2b)
                changed = True
            if n.get("via") != "bot" or n["key"] in posted:
                continue
            if _tries(n) >= RELAY_MAX_TRIES:
                continue                    # tried enough: the bot's, no new webhook (JUG2b)
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
        if due or changed:
            _write(notices)
    outcome: dict[str, str] = {}
    stop = False
    started = _monotonic()
    for i, n in enumerate(due):
        if i and _monotonic() - started >= RELAY_PASS_BUDGET_S:
            stop = True                     # the pass's budget spent (JUG2b)
        if stop:                            # the rest back to the bot, or the next pass
            outcome[n["key"]] = "skipped"
            continue
        if i:
            _sleep(RELAY_SPACING_S)
        result = _post(*fallback(n))
        outcome[n["key"]] = result
        stop = result in ("limited", "unreachable")
    if outcome:
        _settle(outcome)
    return sum(r == "sent" for r in outcome.values())


def _unsent_since(n: dict, now: datetime) -> float:
    """Seconds since a notice was marked relayed without being noted sent (0 when it was sent, or
    is not relayed)."""
    r = n.get("relayed")
    if not isinstance(r, dict) or r.get("sent") is True:
        return 0.0
    try:
        at = datetime.fromisoformat(str(r.get("at")))
    except ValueError:
        return float(RESEND_AFTER_S)
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    return (now - at).total_seconds()


def _write(notices: list[dict]) -> None:
    from glorfindel.response.state import _atomic_write_text
    _atomic_write_text(_STORE, "\n".join(json.dumps(n, default=str) for n in notices) + "\n")


def _settle(outcome: dict[str, str]) -> None:
    """Under the store's lock: each relayed notice noted sent (`outcome`: what `_post` answered), or
    given back to the bot (`via: bot`, `relayed` removed) — a try counted when its post may have been
    delivered (`MAYBE_DELIVERED`, JUG2b). Never raises: a note refused (a full disk) leaves the mark,
    taken back after `RESEND_AFTER_S` — said twice rather than never."""
    try:
        with _lock():
            notices = _read()
            for n in notices:
                if n["key"] not in outcome or not isinstance(n.get("relayed"), dict):
                    continue
                result = outcome[n["key"]]
                if result == "sent":
                    n["relayed"]["sent"] = True
                else:
                    n["via"] = "bot"
                    n.pop("relayed")
                    if result in MAYBE_DELIVERED:
                        n["tries"] = _tries(n) + 1
            _write(notices)
    except OSError as exc:
        log.warning("notices: relayed announcements not noted (%s)", exc)


def relay(notice: dict, why: str) -> bool:
    """An announcement the store could not keep (a full disk), the bot mute: said by the webhook now,
    as `relay_pass` would — nothing recorded, so nothing tells the bot at its return (its card, if
    written, pings again). True when the webhook took it."""
    _mark_relayed(notice, why)
    return _post(*fallback(notice)) == "sent"


def relayed_ping(keys) -> bool:
    """The webhook pinged the role for one of these actions — `relayed.ping`, and noted `sent`: the
    card the bot posts at its return pings no more. A notice forged so in the store can silence the
    card's ping too — never the card (DRN2)."""
    wanted = {k for k in (keys or []) if isinstance(k, str)}
    return bool(wanted) and any((n.get("relayed") or {}).get("ping") is True
                                and (n.get("relayed") or {}).get("sent") is True
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


def _retry_after(resp) -> float | None:
    """The seconds a 429 asks to wait: its `Retry-After` header, else Discord's `retry_after`."""
    try:
        value = (getattr(resp, "headers", None) or {}).get("Retry-After")
        if value is None:
            value = resp.json().get("retry_after")
        return max(0.0, float(value))
    except Exception:
        return None


def _wait(done: threading.Event, seconds: float) -> bool:
    return done.wait(seconds)


def _send(url: str, payload: dict):
    """`requests.post`, bounded: `CONNECT_TIMEOUT_S` to connect and `READ_TIMEOUT_S` to read, and the
    whole of it — the name's resolution included, which requests does not bound — `POST_DEADLINE_S`:
    the POST in a thread of its own, waited for that long (JUG2b). Past it, TimeoutError: the post is
    abandoned, its answer never read (it may still reach the webhook)."""
    box: dict = {}
    done = threading.Event()

    def run() -> None:
        try:
            import requests
            box["answer"] = requests.post(url, json=payload, timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S))
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()
    threading.Thread(target=run, daemon=True, name="webhook-post").start()
    if not _wait(done, POST_DEADLINE_S):
        raise TimeoutError(f"no answer within {POST_DEADLINE_S:g} s")
    if "error" in box:
        raise box["error"]
    return box["answer"]


def _post(payload: dict, key: str = "", url: str = "") -> str:
    """`payload` to `url` (GLORFINDEL_WEBHOOK_URL when none): `sent` on a 2xx answer only (JUG2
    review: a 429, a 404, a network cut are no announcement), `limited` on a 429 still refused after
    one wait of at most `RETRY_MAX_S`, `refused` on another 4xx, `unreachable` without an answer
    within `POST_DEADLINE_S` (`_send`), `failed` otherwise. Never raises."""
    url = url or os.environ.get("GLORFINDEL_WEBHOOK_URL", "")
    if not url:
        return "failed"
    for attempt in (0, 1):
        try:
            resp = _send(url, payload)
        except Exception as exc:          # a notification never stops the watch
            log.warning("notice %s: webhook unreachable (%s)", key, exc)
            return "unreachable"
        status = getattr(resp, "status_code", None)
        if isinstance(status, int) and 200 <= status < 300:
            return "sent"
        if status == 429:
            wait = _retry_after(resp)
            if attempt == 0 and wait is not None and wait <= RETRY_MAX_S:
                _sleep(wait)
                continue
            log.warning("notice %s: webhook rate limited", key)
            return "limited"
        log.warning("notice %s: webhook answered %s", key, status)
        return "refused" if isinstance(status, int) and 400 <= status < 500 else "failed"
    return "failed"


def post_webhook(payload: dict, key: str = "", url: str = "") -> bool:
    """`payload` to `url` (GLORFINDEL_WEBHOOK_URL when none): True when the webhook took it (2xx).
    A short 429 is tried again once (`_post`: it asks no longer than `RETRY_MAX_S`); otherwise a
    webhook that fails is not tried again — outside the fallback, nothing says it later."""
    return _post(payload, key, url) == "sent"
