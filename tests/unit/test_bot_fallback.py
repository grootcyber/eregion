"""JUG2 (#765): the Discord bot mute, the webhook says an autonomous action — once, the role pinged.

Since JUG1 (#760) an action Glorfindel takes alone is announced in its VM's thread when the bot is
configured, nothing by the webhook. Its container stopped, nothing said it any more: its card and its
notice waited for the bot, and a notice older than 24 h was lost. Now the bot writes a heartbeat at
each turn (glorfindel/bot_beat.py) and the watch reads it:

- the bot mute (no beat, or one older than `MUTE_AFTER_S`), the webhook says the action in the
  channel, the role pinged — Discord's own endpoint, no other mention allowed;
- the bot alive, nothing changes from JUG1;
- the bot back, nothing twice: it never posts an announcement the webhook said, and its card, posted
  in the VM's thread with its buttons, pings no more when the webhook pinged;
- a beat forged fresh only delays (an announcement the bot has not posted in `CONFIRM_S` goes by the
  webhook), one dated in the future reads mute; the card never depends on it.

The cycles go through the real graph, on the in-memory Azure (tests/unit/fake_azure.py), the model
patched, a fake webhook (`requests.post` caught) and a fake Discord thread: no cloud call, no model
call, nothing sent.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from glorfindel import bot_beat, escalations, vm_notices

from . import test_judge_card as _jug1
from .test_judge_card import EVIL, ROLE, WEB, _cards, _ransomware, _respond, _scanner, _Thread

# JUG1's set-up, the same here: the hermetic run (autouse), the in-memory Azure, the fake webhook.
hermetic, azure, posts = _jug1.hermetic, _jug1.azure, _jug1.posts

DISCORD_HOOK = "https://discord.com/api/webhooks/123/fake-token/slack"
NATIVE = "https://discord.com/api/webhooks/123/fake-token"


@pytest.fixture
def bot_set(monkeypatch, posts):
    """The bot configured (as compose tells the watch), a Discord webhook, the role to ping — and
    no heartbeat yet: the bot is mute until a test makes it alive."""
    monkeypatch.setenv("GLORFINDEL_DISCORD_BOT", "1")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", DISCORD_HOOK)
    monkeypatch.setenv("DISCORD_PING_ROLE", str(ROLE))
    bot_beat.clear()
    return posts


def _beat(seconds_ago: float, now: datetime | None = None) -> None:
    bot_beat.write((now or datetime.now(timezone.utc)) - timedelta(seconds=seconds_ago))


def _relayed(sent: list[dict]) -> list[dict]:
    """What the webhook carried by Discord's own endpoint (the fallback)."""
    return [p for p in sent if p["url"] == NATIVE]


def _announcement() -> dict:
    [n] = [n for n in vm_notices._read() if n["kind"] == escalations.EXECUTED_TYPE]
    return n


def _bot(threads: dict):
    """The bot, its threads in `threads` (by lowercased resource id), its role ROLE."""
    pytest.importorskip("discord")
    from glorfindel import bot
    b = bot.GlorfindelBot(channel_id=1, ping_role=ROLE)

    async def thread(channel, rid, ping=True):
        if rid.lower() not in threads:
            threads[rid.lower()] = _Thread()
            if ping and b.ping_role:
                await threads[rid.lower()].send(f"<@&{b.ping_role}> Incident opened on `x`",
                                                allowed_mentions=b._role_mentions())
        return threads[rid.lower()]
    b._get_or_create_thread = thread
    return b


def _pings(threads: dict) -> list[dict]:
    return [m for t in threads.values() for m in t.sent if f"<@&{ROLE}>" in str(m.get("content") or "")]


def _bot_returns(card: dict) -> tuple[dict, int]:
    """The bot back: one turn — its new cards, then its notices — as `_watch_escalations` runs it."""
    threads: dict = {}
    b = _bot(threads)

    async def turn():
        await b._post_escalation(None, card)
        return await b._post_notices(None)
    return threads, asyncio.run(turn())


# ── the bot mute: the webhook says it, once, the role pinged ───────────────────────────────────

def test_the_bot_stopped_the_webhook_says_the_action_once_with_the_role_pinged(azure, bot_set):
    """No heartbeat (the bot's container stopped, or never started): the action said in the channel
    by Discord's own endpoint, the role first, no other mention allowed — once, the card written."""
    f, c = azure
    final = _respond(c, _ransomware(), "isolate_vm")
    assert final["outcome"]["verified"] is True
    [card] = _cards()
    [msg] = _relayed(bot_set)
    assert len(bot_set) == 1                                            # nothing else in the channel
    assert msg["content"].startswith(f"<@&{ROLE}> ✅ **VM isolée du réseau ✓** · `web`")
    assert f"Carte à juger : {card['id'][:8]}" in msg["content"] and "Le bot Discord se tait" in msg["content"]
    assert msg["allowed_mentions"] == {"parse": [], "roles": [str(ROLE)]}
    n = _announcement()
    assert n["via"] == "webhook" and n["relayed"]["why"] == "absent" and n["relayed"]["ping"] is True
    assert vm_notices.for_bot() == []                                   # nothing left for the bot
    assert vm_notices.relay_pass() == 0 and len(bot_set) == 1           # the next pass: nothing more


def test_a_heartbeat_older_than_the_threshold_reads_mute(azure, bot_set):
    f, c = azure
    _beat(bot_beat.MUTE_AFTER_S + 5)
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_relayed(bot_set)) == 1 and _announcement()["relayed"]["why"] == "stale"


def test_a_block_taken_alone_is_said_the_same_way(azure, bot_set):
    f, c = azure
    _respond(c, _scanner(), "block_suspicious_ip")
    [msg] = _relayed(bot_set)
    assert msg["content"].startswith(f"<@&{ROLE}> ") and "203.0.113.9" not in msg["allowed_mentions"]["roles"]


def test_the_threshold_said_in_the_code_is_three_minutes():
    """The doc says 3 min (docs/glorfindel.md): some 36 turns of the bot (5 s each)."""
    assert bot_beat.MUTE_AFTER_S == 180 and vm_notices.CONFIRM_S == 600
    now = datetime.now(timezone.utc)
    _beat(bot_beat.MUTE_AFTER_S - 10, now)
    assert bot_beat.mute(now) == ""
    _beat(bot_beat.MUTE_AFTER_S + 1, now)
    assert bot_beat.mute(now) == "stale"


# ── the bot alive: nothing changes from JUG1 ───────────────────────────────────────────────────

def test_the_bot_alive_nothing_changes(azure, bot_set):
    """A fresh beat: the announcement left to the bot, nothing by the webhook — at the passes after
    too, as long as the bot lives and the announcement has not waited `CONFIRM_S`."""
    f, c = azure
    _beat(5)
    _respond(c, _ransomware(), "isolate_vm")
    assert bot_set == []
    n = _announcement()
    assert n["via"] == "bot" and "relayed" not in n
    _beat(0)
    assert vm_notices.relay_pass() == 0 and bot_set == []
    [card] = _cards()
    threads, said = _bot_returns(card)
    assert said == 1 and len(_pings(threads)) == 1                      # JUG1: the card pings, once


# ── the bot back: nothing twice ────────────────────────────────────────────────────────────────

def test_the_bot_back_posts_the_card_without_a_second_ping_and_never_the_announcement(azure, bot_set):
    """The webhook said the action and pinged: the bot, back, posts the card in the VM's thread with
    its buttons, pinging no one, and never the announcement — after its restart too."""
    pytest.importorskip("discord")
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    _beat(0)                                                            # the bot back
    threads, said = _bot_returns(card)
    assert said == 0                                                    # the announcement: never twice
    [msg] = threads[WEB.lower()].sent                                   # one message: the card
    assert msg["embed"].title.startswith("✅ VM isolée du réseau") and msg["content"] is None
    assert "allowed_mentions" not in msg and _pings(threads) == []
    assert len(_relayed(bot_set)) == 1


def test_the_card_still_pings_when_the_webhook_could_not(azure, bot_set, monkeypatch):
    """A Slack webhook (a Discord role means nothing there): its message without a ping — the card,
    at the bot's return, pings the role, once per action."""
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", "https://hooks.example.invalid/eregion")
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    [sent] = bot_set
    assert sent["url"] == "https://hooks.example.invalid/eregion" and "content" not in sent
    assert sent["text"].startswith(":white_check_mark: *VM isolée du réseau ✓*") and "<@&" not in sent["text"]
    assert "Le bot Discord se tait" in sent["text"]
    assert _announcement()["relayed"]["ping"] is False
    threads, said = _bot_returns(card)
    assert said == 0 and len(_pings(threads)) == 1


def test_a_bot_that_falls_silent_after_the_action_is_relayed_at_the_next_pass(azure, bot_set):
    """Alive when the action ran, mute before it posted: the watch's next pass says it by the
    webhook, once, the role pinged; the bot back posts the card without a ping."""
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    assert bot_set == [] and _announcement()["via"] == "bot"
    _beat(bot_beat.MUTE_AFTER_S + 30)                                   # its last beat, aged
    assert vm_notices.relay_pass() == 1
    [msg] = _relayed(bot_set)
    assert msg["content"].startswith(f"<@&{ROLE}> ") and _announcement()["relayed"]["why"] == "stale"
    assert vm_notices.relay_pass() == 0 and len(bot_set) == 1           # once
    [card] = _cards()
    _beat(0)
    threads, said = _bot_returns(card)
    assert said == 0 and _pings(threads) == []


def test_a_card_the_bot_posted_already_keeps_its_one_ping(azure, bot_set):
    """The bot posted the card (and its ping), then fell silent before its notice: the webhook says
    the action, pinging no one."""
    pytest.importorskip("discord")
    from glorfindel import bot
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    bot._save_posted({card["id"]})
    _beat(bot_beat.MUTE_AFTER_S + 30)
    assert vm_notices.relay_pass() == 1
    [msg] = _relayed(bot_set)
    assert "<@&" not in msg["content"] and msg["allowed_mentions"] == {"parse": [], "roles": []}


def test_an_announcement_the_bot_posted_is_never_said_again(azure, bot_set):
    """Posted by the bot (its key in bot_notices_posted.json), then the bot mute: nothing by the
    webhook."""
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    threads, said = _bot_returns(card)
    assert said == 1
    _beat(bot_beat.MUTE_AFTER_S + 30)
    later = datetime.now(timezone.utc) + timedelta(seconds=vm_notices.CONFIRM_S + 60)
    assert vm_notices.relay_pass() == 0 and vm_notices.relay_pass(later) == 0 and bot_set == []


def test_the_bot_reads_the_announcement_again_just_before_its_post(azure, bot_set, monkeypatch):
    """The bot read its notices, then the watch said one by the webhook: the bot skips it."""
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    read_before = vm_notices.for_bot()
    _beat(bot_beat.MUTE_AFTER_S + 30)
    assert vm_notices.relay_pass() == 1
    monkeypatch.setattr(vm_notices, "for_bot", lambda: read_before)
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_notices(None)) == 0 and threads == {}


def test_an_announcement_older_than_a_day_is_not_said_late(azure, bot_set):
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    later = datetime.now(timezone.utc) + timedelta(hours=vm_notices.RELAY_MAX_AGE_H, minutes=5)
    assert vm_notices.relay_pass(later) == 0 and bot_set == []


# ── a forged beat only delays; the card never depends on it ───────────────────────────────────

def test_a_beat_forged_fresh_only_delays_the_webhook(azure, bot_set):
    """A writer of ~/.glorfindel (the console, the bot) keeps the beat fresh while no bot posts:
    the announcement waits — at most `CONFIRM_S` — then goes by the webhook; the card is there
    from the start."""
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_cards()) == 1 and escalations.to_judge()                 # the card, whatever the beat
    t0 = datetime.fromisoformat(_announcement()["at"])
    before = t0 + timedelta(seconds=vm_notices.CONFIRM_S - 30)
    _beat(0, before)
    assert vm_notices.relay_pass(before) == 0 and bot_set == []
    at = t0 + timedelta(seconds=vm_notices.CONFIRM_S + 1)
    _beat(0, at)                                                        # still kept fresh
    assert vm_notices.relay_pass(at) == 1
    assert _announcement()["relayed"]["why"] == "unconfirmed" and len(_relayed(bot_set)) == 1


def test_a_beat_dated_in_the_future_reads_mute(azure, bot_set):
    """Written once far ahead, it would hold the announcement forever: it is no beat."""
    f, c = azure
    bot_beat.write(datetime.now(timezone.utc) + timedelta(days=365))
    assert bot_beat.mute() == "future"
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_relayed(bot_set)) == 1 and _announcement()["relayed"]["why"] == "future"


@pytest.mark.parametrize("raw", [b"", b"not json", b"[]", b'{"at": 3}', b'{"no": "at"}', b"\xff\xfe"])
def test_a_beat_that_does_not_read_is_mute(raw):
    bot_beat._STORE.parent.mkdir(parents=True, exist_ok=True)
    bot_beat._STORE.write_bytes(raw)
    assert bot_beat.mute() == "unreadable"


def test_the_card_is_written_whatever_the_beat(azure, bot_set):
    """Mute or alive, forged or not: the card to judge is written first, on the watch's own store —
    the beat decides only the announcement's path."""
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    bot_beat.clear()
    _respond(c, _ransomware("rule-ransomware-disk-write-0000j2j2"), "isolate_vm")
    assert len(_cards()) == 2 and len(escalations.to_judge()) == 2
    assert [n["via"] for n in vm_notices._read()] == ["bot", "webhook"]


# ── where there is nothing to fall back to, and the full disk ─────────────────────────────────

def test_without_a_webhook_the_announcement_waits_for_the_bot(azure, bot_set, monkeypatch):
    monkeypatch.delenv("GLORFINDEL_WEBHOOK_URL")
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    n = _announcement()
    assert n["via"] == "bot" and "relayed" not in n and bot_set == []
    assert vm_notices.relay_pass() == 0


def test_without_the_bot_the_webhook_says_it_as_in_jug1(azure, posts):
    """No bot configured: the beat is never read — JUG1's webhook message, its Slack format."""
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    [sent] = posts
    assert sent["text"].startswith(":robot_face: *VM isolée du réseau* ✓") and "relayed" not in _announcement()
    assert vm_notices.relay_pass() == 0


def test_a_notice_store_full_the_bot_mute_still_pings_by_the_webhook(azure, bot_set, monkeypatch):
    """The notices' store refuses (a full disk), the card written, the bot mute: the webhook says the
    action now, the role pinged — the card, posted at the bot's return, pings again (nothing
    recorded tells it: docs/glorfindel.md, a known limit)."""
    def full(notice):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vm_notices, "_record", full)
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_cards()) == 1
    [msg] = _relayed(bot_set)
    assert msg["content"].startswith(f"<@&{ROLE}> ✅")


def test_a_ping_role_that_is_not_an_id_pings_no_one(azure, bot_set, monkeypatch):
    monkeypatch.setenv("DISCORD_PING_ROLE", "@everyone")
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [msg] = _relayed(bot_set)
    assert "@everyone" not in msg["content"] and msg["allowed_mentions"] == {"parse": [], "roles": []}


def test_the_relayed_announcement_escapes_what_comes_from_outside(azure, bot_set):
    """The model's words, Azure's names: escaped as the bot escapes them (SEC6) — the role the one
    mention, and the only one allowed."""
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm", explanation=EVIL)
    [msg] = _relayed(bot_set)
    body = msg["content"].removeprefix(f"<@&{ROLE}> ")
    assert "@everyone" not in body and "\\[support\\]\\(https://evil.example\\)" in body
    assert "\\<@&1\\>" in body and not re.search(r"(?<!\\)<@&", body)    # shown, never a mention
    assert msg["allowed_mentions"] == {"parse": [], "roles": [str(ROLE)]} and len(msg["content"]) <= 2000


@pytest.mark.parametrize("url,native", [
    (DISCORD_HOOK, NATIVE),
    (NATIVE, NATIVE),
    ("https://discordapp.com/api/webhooks/1/t/slack?thread_id=9", "https://discordapp.com/api/webhooks/1/t?thread_id=9"),
    ("https://ptb.discord.com/api/webhooks/1/t/github", "https://ptb.discord.com/api/webhooks/1/t"),
    ("http://discord.com/api/webhooks/1/t/slack", ""),
    ("https://discord.com.evil.example/api/webhooks/1/t/slack", ""),
    ("https://evil.example/discord.com/api/webhooks/1/t/slack", ""),
    ("https://notdiscord.com/api/webhooks/1/t/slack", ""),
    ("https://discord.com/channels/1/2", ""),
    ("https://hooks.slack.com/services/T/B/x", ""),
    ("https://[::1", ""),
])
def test_only_a_discord_webhook_gets_discord_s_own_endpoint(url, native):
    assert vm_notices._discord_url(url) == native


# ── the bot's beat: written at each turn, removed when it stops ───────────────────────────────

def test_the_bot_writes_its_beat_at_each_turn_once_its_channel_is_read(monkeypatch):
    pytest.importorskip("discord")
    from glorfindel import bot
    b = bot.GlorfindelBot(channel_id=1, ping_role=None)
    turns = {"n": 0}

    async def sleep(_s):
        turns["n"] += 1
        if turns["n"] == 1:
            assert bot_beat.mute() == "absent"                          # no channel yet: no beat
        if turns["n"] == 3:
            raise asyncio.CancelledError

    channels = iter([None, type("C", (), {"name": "alerts"})()])
    monkeypatch.setattr(b, "get_channel", lambda _id: next(channels))
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)

    async def nothing(*a, **k):
        return 0
    monkeypatch.setattr(b, "_post_notices", nothing)
    monkeypatch.setattr(b, "_post_weekly", nothing)
    monkeypatch.setattr(bot.esc_module, "pending", lambda: [])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(b._watch_escalations())
    assert bot_beat.mute() == ""


def test_the_bot_stopping_removes_its_beat(monkeypatch):
    pytest.importorskip("discord")
    from glorfindel import bot
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    monkeypatch.delenv("EREGION_ACTION_QUEUE", raising=False)

    def run(self, token, log_handler=None):
        bot_beat.write()
        raise RuntimeError("gateway closed")
    monkeypatch.setattr(bot.GlorfindelBot, "run", run)
    with pytest.raises(RuntimeError):
        bot.run()
    assert bot_beat.mute() == "absent"


# ── the stores: the bot's files, read by the watch ────────────────────────────────────────────

def test_the_watch_reads_the_files_the_bot_writes():
    root = Path(__file__).resolve().parents[2] / "glorfindel"
    bot_src = (root / "bot.py").read_text(encoding="utf-8")
    notices_src = (root / "vm_notices.py").read_text(encoding="utf-8")
    for name in ("bot_notices_posted.json", "bot_posted.json"):
        line = f'Path.home() / ".glorfindel" / "{name}"'
        assert line in bot_src and line in notices_src
    assert vm_notices.ACTION_KIND == escalations.EXECUTED_TYPE


def test_the_watch_relays_at_its_housekeeping():
    cli = (Path(__file__).resolve().parents[2] / "glorfindel" / "cli.py").read_text(encoding="utf-8")
    assert "                        _relay_notices()" in cli and "_vm_notices.relay_pass()" in cli
