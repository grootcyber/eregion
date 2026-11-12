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


class _Answer:
    """A webhook's answer: Discord's 204 by default."""

    def __init__(self, status: int = 204, retry_after: float | None = None):
        self.status_code = status
        self.headers: dict = {}
        self._body = {"retry_after": retry_after} if retry_after is not None else {}

    def json(self):
        return self._body


@pytest.fixture
def answers() -> list:
    """What the fake webhook answers, in order (an _Answer, or an exception to raise); empty: 204."""
    return []


@pytest.fixture
def sleeps(monkeypatch) -> list:
    """The waits of the fallback, recorded, never slept."""
    waited: list[float] = []
    monkeypatch.setattr(vm_notices, "_sleep", waited.append)
    return waited


@pytest.fixture
def bot_set(monkeypatch, posts, answers, sleeps):
    """The bot configured (as compose tells the watch), a Discord webhook, the role to ping — and
    no heartbeat yet: the bot is mute until a test makes it alive. Every POST caught, none sent,
    answered from `answers`."""
    import requests
    monkeypatch.setenv("GLORFINDEL_DISCORD_BOT", "1")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", DISCORD_HOOK)
    monkeypatch.setenv("DISCORD_PING_ROLE", str(ROLE))
    bot_beat.clear()

    def post(url, json=None, timeout=None):
        posts.append({"url": url, **json})
        answer = answers.pop(0) if answers else _Answer()
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(requests, "post", post)
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


# ── a webhook that fails: never counted as said (JUG2 review) ─────────────────────────────────

@pytest.mark.parametrize("answer", [_Answer(429, retry_after=30), _Answer(404), _Answer(500),
                                    ConnectionError("network cut")])
def test_a_webhook_that_fails_gives_the_announcement_back_to_the_bot(azure, bot_set, answers, answer):
    """Refused, rate limited for long, unreachable: the announcement is not marked said — back to
    the bot, which posts it at its return, and its card pings the role."""
    answers.append(answer)
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_relayed(bot_set)) == 1                                  # tried
    n = _announcement()
    assert n["via"] == "bot" and "relayed" not in n
    [card] = _cards()
    _beat(0)                                                            # the bot back
    threads, said = _bot_returns(card)
    assert said == 1 and len(_pings(threads)) == 1                      # the announcement, the card's ping


def test_a_relay_that_failed_is_tried_again_at_the_next_pass(azure, bot_set, answers):
    answers.append(_Answer(503))
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    assert vm_notices.relay_pass() == 1                                 # the bot still mute
    msgs = _relayed(bot_set)
    assert len(msgs) == 2 and msgs[1]["content"].startswith(f"<@&{ROLE}> ")
    n = _announcement()
    assert n["via"] == "webhook" and n["relayed"]["sent"] is True
    assert vm_notices.relay_pass() == 0 and len(_relayed(bot_set)) == 2


def test_a_short_429_is_waited_for_once(azure, bot_set, answers, sleeps):
    answers.append(_Answer(429, retry_after=0.3))
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_relayed(bot_set)) == 2 and sleeps == [0.3]
    assert _announcement()["relayed"]["sent"] is True


def _three_actions_left_to_the_bot(c) -> None:
    _beat(0)
    for i in range(3):
        _respond(c, _ransomware(f"rule-ransomware-disk-write-0000b{i}b{i}"), "isolate_vm")
    _beat(bot_beat.MUTE_AFTER_S + 30)                                   # then the bot falls silent


def test_a_burst_of_actions_loses_none(azure, bot_set, monkeypatch, sleeps):
    """Three actions left to the bot, the bot then mute: one pass says them all, spaced — a webhook
    that answers 429 to two posts with no wait between them (Discord's limits) loses none."""
    import requests
    f, c = azure
    _three_actions_left_to_the_bot(c)
    waited_since_last = [True]
    monkeypatch.setattr(vm_notices, "_sleep", lambda s: (sleeps.append(s), waited_since_last.__setitem__(0, True)))

    def limited(url, json=None, timeout=None):
        bot_set.append({"url": url, **json})
        ok, waited_since_last[0] = waited_since_last[0], False
        return _Answer() if ok else _Answer(429, retry_after=30)
    monkeypatch.setattr(requests, "post", limited)
    assert vm_notices.relay_pass() == 3
    assert len(_relayed(bot_set)) == 3 and sleeps == [vm_notices.RELAY_SPACING_S] * 2
    assert all(n["relayed"]["sent"] is True for n in vm_notices._read())


def test_a_pass_rate_limited_leaves_the_rest_to_the_next(azure, bot_set, answers):
    """A 429 that asks for 30 s: the pass stops there, nothing marked said; the next one says all."""
    f, c = azure
    _three_actions_left_to_the_bot(c)
    answers.extend([_Answer(429, retry_after=30)])
    assert vm_notices.relay_pass() == 0
    assert len(_relayed(bot_set)) == 1                                  # one tried, the others kept
    assert [n["via"] for n in vm_notices._read()] == ["bot"] * 3
    assert vm_notices.relay_pass() == 3 and len(_relayed(bot_set)) == 4


def test_a_relay_never_noted_sent_is_said_again_rather_than_never(azure, bot_set, monkeypatch):
    """The watch stopped mid-send, or its note refused (a full disk): the mark stays without `sent` —
    taken back after RESEND_AFTER_S, said again; meanwhile the card's ping is not silenced."""
    real_settle, noted = vm_notices._settle, [False]
    monkeypatch.setattr(vm_notices, "_settle", lambda outcome: real_settle(outcome) if noted[0] else None)
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    n = _announcement()
    assert n["via"] == "webhook" and "sent" not in n["relayed"]
    [card] = _cards()
    assert not vm_notices.relayed_ping(card["action_keys"])
    assert vm_notices.relay_pass() == 0 and len(_relayed(bot_set)) == 1
    noted[0] = True
    later = datetime.now(timezone.utc) + timedelta(seconds=vm_notices.RESEND_AFTER_S + 5)
    assert vm_notices.relay_pass(later) == 1 and len(_relayed(bot_set)) == 2
    assert vm_notices.relayed_ping(card["action_keys"])


def test_a_forged_notice_can_silence_the_card_s_ping_never_the_card(azure, bot_set):
    """A line forged in the store, under the action's key, relayed, pinged and sent: the bot posts
    the card, without a ping — the card is still there (DRN2, docs/design/modele-de-menace.md)."""
    from glorfindel.agent import _executed_key
    vm_notices._record({"key": _executed_key({"signal": _ransomware(), "action": "isolate_vm"}),
                        "kind": vm_notices.ACTION_KIND, "via": "webhook", "at": "2026-11-12T00:00:00+00:00",
                        "relayed": {"ping": True, "sent": True}})
    f, c = azure
    _beat(0)
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    threads, said = _bot_returns(card)
    assert threads[WEB.lower()].sent[0]["embed"].title.startswith("✅") and _pings(threads) == []


def test_a_slack_fallback_keeps_the_card_and_the_run_with_a_long_explanation(azure, bot_set, monkeypatch):
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", "https://hooks.example.invalid/eregion")
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm", explanation="chiffrement " * 300)
    [card] = _cards()
    [sent] = bot_set
    assert f"Carte à juger : {card['id'][:8]}" in sent["text"]
    assert "Run watch-ransomware-disk-write-20261112T091600Z" in sent["text"]


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
    ("https://discord.com/api/v10/webhooks/1/t/slack", "https://discord.com/api/v10/webhooks/1/t"),
    ("https://discord.com/api/v9/webhooks/1/t", "https://discord.com/api/v9/webhooks/1/t"),
    ("https://discord.com/api/vx/webhooks/1/t", ""),
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
    installed: list[bool] = []
    monkeypatch.setattr(bot, "_stop_on_sigterm", lambda: installed.append(True))   # not in this worker
    with pytest.raises(RuntimeError):
        bot.run()
    assert bot_beat.mute() == "absent" and installed == [True]


_STOPPED_BOT = """
import time
from glorfindel import bot, bot_beat

def run(self, token, log_handler=None):
    bot_beat.write()
    time.sleep(60)

bot.GlorfindelBot.run = run
bot.run()
"""


def test_docker_stop_removes_the_beat(tmp_path):
    """JUG2 review: `docker stop` sends SIGTERM to `glorfindel bot`, PID 1 of its container, where
    Python had no handler — the beat stayed, the fallback waited 3 min and a pass. A real process,
    its HOME under tmp, sent SIGTERM: its beat removed."""
    pytest.importorskip("discord")
    import os
    import signal
    import subprocess
    import sys
    import time
    root = Path(__file__).resolve().parents[2]
    home = tmp_path / "home"
    beat = home / ".glorfindel" / "bot_heartbeat.json"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "stopped_bot.py").write_text(_STOPPED_BOT)
    env = {k: v for k, v in os.environ.items() if k != "EREGION_ACTION_QUEUE"}
    env.update(HOME=str(home), PYTHONPATH=str(root), DISCORD_BOT_TOKEN="fake-token", DISCORD_CHANNEL_ID="1")
    proc = subprocess.Popen([sys.executable, str(scripts / "stopped_bot.py")], cwd=root, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 60
        while not beat.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        assert beat.exists(), "the bot never wrote its beat"
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert not beat.exists()


def test_the_sigterm_handler_stops_as_a_ctrl_c():
    """discord.py's `Client.run` returns on a KeyboardInterrupt: the handler raises one."""
    pytest.importorskip("discord")
    import signal

    from glorfindel import bot
    old = signal.getsignal(signal.SIGTERM)
    try:
        bot._stop_on_sigterm()
        assert signal.getsignal(signal.SIGTERM) is bot._on_sigterm
        with pytest.raises(KeyboardInterrupt):
            bot._on_sigterm(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGTERM, old)


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


# ── JUG2b (#768): the fallback never holds the watch's loop ───────────────────────────────────

def _left_to_the_bot(key: str = "action:never-answered") -> None:
    """An action's announcement the bot never posted, recorded now: due at the next pass, the bot mute."""
    vm_notices._record({"key": key, "resource_id": WEB, "kind": vm_notices.ACTION_KIND,
                        "title": "VM isolée du réseau", "text": "isolée seule", "level": "ok", "via": "bot",
                        "at": datetime.now(timezone.utc).isoformat()})


def _join(*names: str) -> None:
    import threading
    for t in threading.enumerate():
        if t.name in names:
            t.join(10)


def test_a_webhook_that_never_answers_holds_neither_the_watch_s_beat_nor_its_reassertion(
        tmp_path, monkeypatch, bot_set):
    """The real loop of `glorfindel watch`, its sleeps counted: an announcement due, the bot mute, a
    webhook that never answers (no deadline either: the POST holds as long as it will). At the
    housekeeping after, the POST still waiting, the watch writes its heartbeat and starts its
    reassertion — before JUG2b, the loop waited 10 to 25 s per announcement."""
    import atexit
    import signal as signalmod
    import threading
    import time
    from types import SimpleNamespace

    import requests
    from click.testing import CliRunner

    from eregion_core import watch_channel as wc
    from glorfindel import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(wc.CHANNEL_ENV, raising=False)
    monkeypatch.delenv("EREGION_ACTION_QUEUE", raising=False)
    monkeypatch.setenv("GLORFINDEL_REASSERT_INTERVAL_S", "0.000001")    # at each housekeeping
    monkeypatch.setenv("GLORFINDEL_RECOVERY_INTERVAL_S", "0")
    monkeypatch.setenv("GLORFINDEL_DOOR_FACTS_INTERVAL_S", "0")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(cli, "_INJECTORS_DIR", home / ".glorfindel" / "injectors")
    runs = tmp_path / "runs"
    (runs / "annatar").mkdir(parents=True)
    monkeypatch.setattr("eregion_core.watch_channel.start_local", lambda *a, **k: None)

    class _Connector:
        def __init__(self, dry_run=False):
            pass

        def private_ip_owners(self):
            return {}

    class _Agent:
        def __init__(self, **kw):
            self.autonomy = SimpleNamespace(default="human_only", assets=[])
            self.config_error = ""
            self.connector = SimpleNamespace(permission_mode=lambda: "read_write")

    monkeypatch.setattr("glorfindel.actions.AzureConnector", _Connector)
    monkeypatch.setattr("glorfindel.actions.warm_up_azure_sdk", lambda: None)
    monkeypatch.setattr("glorfindel.agent.GlorfindelAgent", _Agent)
    monkeypatch.setattr(cli, "_find_rules_file", lambda: None)
    monkeypatch.setattr("eregion_core.inscription.TagEnrollment", lambda *a, **k: (lambda rid: True))
    monkeypatch.setattr(atexit, "register", lambda *a, **k: None)
    monkeypatch.setattr(signalmod, "signal", lambda *a, **k: None)

    _left_to_the_bot()
    entered, answered, release = threading.Event(), threading.Event(), threading.Event()

    def never(url, json=None, timeout=None):
        entered.set()
        release.wait(30)         # never answers — 30 s at most: a loop it held fails, never hangs
        answered.set()
        raise requests.ConnectionError("no answer")
    monkeypatch.setattr(requests, "post", never)
    monkeypatch.setattr(vm_notices, "_wait", lambda done, s: done.wait())

    def waiting() -> bool:
        return entered.is_set() and not answered.is_set()
    beats: list[bool] = []
    reasserts: list[bool] = []
    real_beat = cli._write_watch_heartbeat
    monkeypatch.setattr(cli, "_write_watch_heartbeat", lambda path, at: (beats.append(waiting()), real_beat(path, at)))
    monkeypatch.setattr(cli, "_watch_reassert_pass", lambda *a, **k: reasserts.append(waiting()))
    real_sleep, calls = time.sleep, [0]

    def _sleep(s):
        # The watch loop's own sleep only (--interval 0): a housekeeping every 30 polls.
        if threading.current_thread() is not threading.main_thread() or s != 0:
            return real_sleep(s)
        calls[0] += 1
        if calls[0] == 30:                       # the first housekeeping done: its relay under way
            deadline = time.monotonic() + 10
            while (not entered.is_set() or any(t.name == "reassert" for t in threading.enumerate())) \
                    and time.monotonic() < deadline:
                real_sleep(0.01)
        if calls[0] == 60:                       # the second one done
            raise KeyboardInterrupt
        return None

    monkeypatch.setattr(cli.time, "sleep", _sleep)
    try:
        result = CliRunner().invoke(cli.cli, ["watch", str(runs), "--interval", "0"])
    finally:
        release.set()
        _join("relay-notices", "webhook-post", "reassert")
    assert result.exit_code == 0, result.output
    assert entered.is_set()
    assert True in beats, beats                  # a heartbeat written while the POST waited
    assert True in reasserts, reasserts          # and a reassertion started
    n = vm_notices.said("action:never-answered")
    assert n["via"] == "bot" and n["tries"] == 1     # unreachable: back to the bot, one try counted


def test_one_relay_pass_at_a_time(azure, bot_set):
    """A pass running, another called (a thread started again): it does nothing."""
    f, c = azure
    _three_actions_left_to_the_bot(c)
    assert vm_notices._PASS.acquire(blocking=False)
    try:
        assert vm_notices.relay_pass() == 0 and bot_set == []
    finally:
        vm_notices._PASS.release()
    assert vm_notices.relay_pass() == 3


def _name_unresolved():
    import requests
    from urllib3.exceptions import MaxRetryError, NameResolutionError
    return requests.ConnectionError(MaxRetryError(None, "/api/webhooks/123/fake-token",
                                                  NameResolutionError("discord.com", None, OSError("EAI_AGAIN"))))


def _connection_refused():
    import requests
    from urllib3.exceptions import MaxRetryError, NewConnectionError
    return requests.ConnectionError(MaxRetryError(None, "/api/webhooks/123/fake-token",
                                                  NewConnectionError(None, "Connection refused")))


def _cut_while_reading():
    import requests
    from urllib3.exceptions import ProtocolError
    return requests.ConnectionError(ProtocolError("Connection aborted.", ConnectionResetError(104, "reset")))


@pytest.mark.parametrize("make,unsent", [
    (lambda: __import__("requests").ConnectTimeout("connect timeout"), True),
    (_name_unresolved, True),
    (_connection_refused, True),
    (lambda: __import__("requests").ReadTimeout("read timeout"), False),
    (_cut_while_reading, False),
    (lambda: TimeoutError("no answer within 10 s"), False),           # the deadline: ambiguous
])
def test_what_left_nothing_is_told_from_what_may_have_been_delivered(bot_set, monkeypatch, make, unsent):
    import requests
    exc = make()

    def raising(url, json=None, timeout=None):
        raise exc
    monkeypatch.setattr(requests, "post", raising)
    assert vm_notices._post({"content": "x"}, "k", NATIVE) == ("unsent" if unsent else "unreachable")


@pytest.mark.parametrize("make", [lambda: __import__("requests").ConnectTimeout("unreachable"),
                                  _name_unresolved, lambda: __import__("requests").ReadTimeout("lost")])
def test_a_pass_stops_at_a_webhook_unreachable(azure, bot_set, answers, make):
    """No answer, or nothing left: the pass stops there — the rest back to the bot, said at the next
    pass."""
    f, c = azure
    _three_actions_left_to_the_bot(c)
    answers.append(make())
    assert vm_notices.relay_pass() == 0
    assert len(_relayed(bot_set)) == 1                                  # one tried, the others kept
    assert [n["via"] for n in vm_notices._read()] == ["bot"] * 3
    assert vm_notices.relay_pass() == 3 and len(_relayed(bot_set)) == 4


def test_a_pass_stops_at_a_webhook_that_refuses(azure, bot_set, answers):
    """A 404 (a webhook deleted): the next posts would go to the same one — the pass stops there."""
    f, c = azure
    _three_actions_left_to_the_bot(c)
    answers.append(_Answer(404))
    assert vm_notices.relay_pass() == 0 and len(_relayed(bot_set)) == 1
    assert [n["via"] for n in vm_notices._read()] == ["bot"] * 3
    assert vm_notices.relay_pass() == 3 and len(_relayed(bot_set)) == 4


def test_a_network_cut_counts_no_try(azure, bot_set, answers):
    """Five passes where nothing left (the connection not made in time, the name not resolved): no
    try counted — the network back, the webhook says the announcement, its ping with it."""
    import requests
    answers.extend([requests.ConnectTimeout("network cut")] * 3 + [_name_unresolved(), _connection_refused()])
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")                            # the first post: nothing left
    for _ in range(4):
        assert vm_notices.relay_pass() == 0
    assert len(_relayed(bot_set)) == 5 and "tries" not in _announcement()
    assert vm_notices.relay_pass() == 1                                 # a 204: said
    msgs = _relayed(bot_set)
    assert len(msgs) == 6 and msgs[-1]["content"].startswith(f"<@&{ROLE}> ")
    assert _announcement()["relayed"]["sent"] is True


def test_a_pass_starts_no_post_once_its_budget_spent(azure, bot_set, monkeypatch):
    import requests
    f, c = azure
    _three_actions_left_to_the_bot(c)
    clock = [0.0]
    monkeypatch.setattr(vm_notices, "_monotonic", lambda: clock[0])

    def slow(url, json=None, timeout=None):
        bot_set.append({"url": url, **json})
        clock[0] += vm_notices.RELAY_PASS_BUDGET_S                     # each answer takes the budget
        return _Answer()
    monkeypatch.setattr(requests, "post", slow)
    assert vm_notices.relay_pass() == 1 and len(_relayed(bot_set)) == 1
    assert [n["via"] for n in vm_notices._read()].count("bot") == 2     # the rest back to the bot
    assert vm_notices.relay_pass() == 1 and vm_notices.relay_pass() == 1 and len(_relayed(bot_set)) == 3


def test_a_post_without_an_answer_by_its_deadline_is_unreachable(bot_set, monkeypatch):
    """The name's resolution, the connection or the read held past `POST_DEADLINE_S`: the post is
    abandoned, `unreachable` — the caller goes on."""
    import threading

    import requests
    release = threading.Event()

    def held(url, json=None, timeout=None):
        release.wait(5)
        return _Answer()
    monkeypatch.setattr(requests, "post", held)
    monkeypatch.setattr(vm_notices, "POST_DEADLINE_S", 0.05)
    try:
        assert vm_notices._post({"content": "x"}, "k", NATIVE) == "unreachable"
    finally:
        release.set()
        _join("webhook-post")


def test_each_post_is_bounded_to_connect_and_to_read(bot_set, monkeypatch):
    import requests
    seen: list = []
    monkeypatch.setattr(requests, "post", lambda url, json=None, timeout=None: (seen.append(timeout), _Answer())[1])
    assert vm_notices._post({"content": "x"}, "k", NATIVE) == "sent"
    assert seen == [(vm_notices.CONNECT_TIMEOUT_S, vm_notices.READ_TIMEOUT_S)]
    assert vm_notices.CONNECT_TIMEOUT_S + vm_notices.READ_TIMEOUT_S <= vm_notices.POST_DEADLINE_S


def test_the_bound_said_in_the_doc_holds_and_ends_before_a_mark_is_taken_back():
    """docs/glorfindel.md: a pass lasts at most its budget and one notice — spacing, a POST, a short
    429's wait, a second POST — some 86 s, under `RESEND_AFTER_S`: its marks never taken back while
    it runs."""
    one = vm_notices.RELAY_SPACING_S + 2 * vm_notices.POST_DEADLINE_S + vm_notices.RETRY_MAX_S
    assert vm_notices.RELAY_PASS_BUDGET_S + one == 85.5 < vm_notices.RESEND_AFTER_S
    assert vm_notices.RELAY_MAX_TRIES == 3


# ── JUG2b: the tries of a notice are capped ───────────────────────────────────────────────────

@pytest.mark.parametrize("lost", ["read timeout", "502"])
def test_a_webhook_whose_answer_is_lost_says_it_three_times_at_most(azure, bot_set, answers, lost, caplog):
    """Delivered perhaps, its answer lost (a read timeout, a 502 from the edge): said again, its
    ping with it, `RELAY_MAX_TRIES` times at most — then the bot's, no new webhook, said once in the
    log; its card, at the bot's return, pings."""
    import logging

    import requests
    caplog.set_level(logging.WARNING, logger=vm_notices.log.name)
    answers.extend([requests.ReadTimeout("answer lost") if lost == "read timeout" else _Answer(502)] * 6)
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")                            # the first try
    assert vm_notices.relay_pass() == 0 and vm_notices.relay_pass() == 0
    assert len(_relayed(bot_set)) == 3
    assert vm_notices.relay_pass() == 0 and vm_notices.relay_pass() == 0
    assert len(_relayed(bot_set)) == 3                                  # the cap: no new webhook
    assert all(m["content"].startswith(f"<@&{ROLE}> ") for m in _relayed(bot_set))
    n = _announcement()
    assert n["via"] == "bot" and n["tries"] == vm_notices.RELAY_MAX_TRIES and "relayed" not in n
    later = datetime.now(timezone.utc) + timedelta(seconds=vm_notices.CONFIRM_S + 60)
    assert vm_notices.relay_pass(later) == 0 and len(_relayed(bot_set)) == 3
    capped = [r for r in caplog.records if "says it no more" in r.getMessage()]
    assert len(capped) == 1 and n["key"] in capped[0].getMessage()
    [card] = _cards()
    _beat(0)
    threads, said = _bot_returns(card)
    assert said == 1 and len(_pings(threads)) == 1                      # the bot says it, its card pings


@pytest.mark.parametrize("answer", [_Answer(404), _Answer(429, retry_after=30)])
def test_a_refusal_counts_no_try(azure, bot_set, answers, answer):
    """A 404, a long 429: nothing delivered, nothing to ping twice — no try counted; the passes go on
    trying, one post each (a webhook back from a rate limit says it)."""
    answers.extend([answer] * 5)
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    for _ in range(4):
        assert vm_notices.relay_pass() == 0
    assert len(_relayed(bot_set)) == 5 and "tries" not in _announcement()
    assert vm_notices.relay_pass() == 1


def test_a_mark_taken_back_counts_a_try(azure, bot_set, monkeypatch):
    """The watch stopped mid-send: its post may have gone — taken back, it counts one."""
    real_settle, noted = vm_notices._settle, [False]
    monkeypatch.setattr(vm_notices, "_settle", lambda outcome: real_settle(outcome) if noted[0] else None)
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    noted[0] = True
    later = datetime.now(timezone.utc) + timedelta(seconds=vm_notices.RESEND_AFTER_S + 5)
    assert vm_notices.relay_pass(later) == 1
    n = _announcement()
    assert n["tries"] == 1 and n["relayed"]["sent"] is True


@pytest.mark.parametrize("tries", ["3", True, -9, None])
def test_tries_that_do_not_read_count_none(tries):
    assert vm_notices._tries({"tries": tries}) == 0


# ── JUG2b: the SIGTERM handler put back ───────────────────────────────────────────────────────

def test_the_bot_puts_the_sigterm_handler_back_when_it_stops(monkeypatch):
    """`docker stop` is read as a Ctrl-C while the bot runs; once it stopped, the handler it found
    is back — a caller that goes on (a test's worker) keeps its own."""
    pytest.importorskip("discord")
    import signal

    from glorfindel import bot
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    monkeypatch.delenv("EREGION_ACTION_QUEUE", raising=False)
    before = signal.getsignal(signal.SIGTERM)
    during: list = []
    monkeypatch.setattr(bot.GlorfindelBot, "run",
                        lambda self, token, log_handler=None: during.append(signal.getsignal(signal.SIGTERM)))
    try:
        bot.run()
        assert during == [bot._on_sigterm]
        assert signal.getsignal(signal.SIGTERM) == before
    finally:
        if before is not None:
            signal.signal(signal.SIGTERM, before)


# ── JUG2b: a cut's closure falls back too, never pinging (Jonathan, 12/11) ────────────────────

ASKED = "2026-11-12T20:00:00+00:00"


def _closed(ended: dict):
    from glorfindel import drain_watch
    return lambda: drain_watch._say_closed("web", WEB, {**ended, "asked_at": ASKED}, 12, [])


def _unfollowed():
    from glorfindel import drain_watch
    drain_watch._say_unfollowed(WEB, ASKED, "levée")


CLOSURES = {
    "drained": (_closed({"status": "drained"}), "✅ **Coupure des sessions aboutie**"),
    "refused": (_closed({"status": "failed", "refused": True, "error": "403"}), "🚨 **Coupure des sessions"),
    "open": (_closed({"status": "partial", "error": "ss -K"}), "🚨 **Coupure des sessions"),
    "never": (_closed({"status": "failed", "never": True, "error": "non relu"}), "⚠️ **Coupure des sessions"),
    "unfollowed": (_unfollowed, "⚠️ **Coupure des sessions"),
}


@pytest.mark.parametrize("outcome", sorted(CLOSURES))
def test_the_bot_mute_every_closure_goes_once_by_the_webhook_without_a_ping(bot_set, outcome):
    """Drained too: each closure of a cut recorded for the bot — never posted from the reassertion —
    then said once in the channel by the next pass, Discord's own endpoint, no mention at all; the
    bot back never posts it."""
    from glorfindel import drain_watch
    say, head = CLOSURES[outcome]
    say()
    say()                                                               # said again: nothing more
    assert bot_set == [] and [n["via"] for n in vm_notices._read()] == ["bot"]
    assert vm_notices.relay_pass() == 1
    [msg] = _relayed(bot_set)
    assert len(bot_set) == 1 and msg["content"].startswith(head) and "<@&" not in msg["content"]
    assert msg["allowed_mentions"] == {"parse": [], "roles": []}
    assert "Le bot Discord se tait" in msg["content"] and "TO JUDGE" not in msg["content"]
    [n] = vm_notices._read()
    assert n["key"] == drain_watch.closure_key(WEB, ASKED) and n["kind"] == vm_notices.CLOSURE_KIND
    assert n["via"] == "webhook" and n["relayed"]["ping"] is False and n["relayed"]["sent"] is True
    assert vm_notices.relay_pass() == 0 and len(bot_set) == 1 and vm_notices.for_bot() == []
    _beat(0)                                                            # the bot back
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_notices(None)) == 0 and threads == {}


def test_a_closure_never_waits_for_the_webhook(bot_set, monkeypatch):
    """JUG2b review: a closure is said from the reassertion, under its VM's lock — the bot mute and a
    webhook that never answers, `_say_closed` returns at once, nothing posted: the next relay pass,
    in its own thread, says it."""
    import threading

    import requests
    entered, release = threading.Event(), threading.Event()

    def never(url, json=None, timeout=None):
        entered.set()
        release.wait(30)
        return _Answer()
    monkeypatch.setattr(requests, "post", never)
    try:
        CLOSURES["drained"][0]()
        assert not entered.is_set()                                     # no POST started
        [n] = vm_notices._read()
        assert n["via"] == "bot" and "relayed" not in n
    finally:
        release.set()
        _join("webhook-post")


def test_the_bot_alive_a_closure_stays_in_the_vm_s_thread(bot_set):
    _beat(0)
    CLOSURES["drained"][0]()
    assert bot_set == [] and [n["via"] for n in vm_notices.for_bot()] == ["bot"]
    assert vm_notices.relay_pass() == 0 and bot_set == []
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_notices(None)) == 1
    [msg] = threads[WEB.lower()].sent
    assert msg["content"].startswith("✅ **Coupure des sessions aboutie**") and _pings(threads) == []


def test_a_closure_left_to_the_bot_then_mute_goes_by_the_webhook_at_the_next_pass(bot_set, answers):
    """The bot alive at the closure, mute before its post: the next pass says it, no ping — and a
    webhook that fails gives it back to the bot, as an action's announcement."""
    _beat(0)
    CLOSURES["never"][0]()
    _beat(bot_beat.MUTE_AFTER_S + 30)
    answers.append(_Answer(500))
    assert vm_notices.relay_pass() == 0 and vm_notices.for_bot()        # failed: back to the bot
    assert vm_notices.relay_pass() == 1
    msgs = _relayed(bot_set)
    assert len(msgs) == 2 and all("<@&" not in m["content"] for m in msgs)
    _beat(0)
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_notices(None)) == 0 and threads == {}


def test_the_closure_s_kind_is_the_one_the_drain_writes():
    src = (Path(__file__).resolve().parents[2] / "glorfindel" / "drain_watch.py").read_text(encoding="utf-8")
    assert src.count(f'"{vm_notices.CLOSURE_KIND}"') == 2 and vm_notices.CLOSURE_KIND in vm_notices.RELAY_KINDS
