"""DRN2 (#754): the session cut announced pending gets one closure, its outcome and when it was read.

On the bench, 12/11, the cut of gondolin's isolation ran 304 s on Azure: the autonomous isolation's
notification said « coupure en attente … suivie », the reassertion read it drained at its next
pass (« reassert drain … → drained ») — and no message ever said so; the card stayed on « en
attente ». Now every cut the watch announced pending is closed once, by its nonce: in the VM's
Discord thread when the bot is configured, else by the webhook — cut, refused, sessions left open,
never ended, or no longer followed —, even after a restart of the watch or of the bot.

On the in-memory Azure (tests/unit/fake_azure.py: a Run Command held running, then ended by the
test), a fake webhook (`requests.post` caught) and a fake Discord thread: no cloud call, no model
call, nothing sent.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from azure.core.exceptions import HttpResponseError

from glorfindel import drain_watch, escalations, vm_notices
from glorfindel.actions import _load_isolation_state
from glorfindel.providers.azure import run_command
from glorfindel.reassert import reassert_pass

from .fake_azure import _error
from . import test_drain_follow as _follow
from .test_drain_follow import _ACT, _WEB, _cycle, _drain_cards

azure = _follow.azure          # the in-memory Azure of DRN1: web, its Run Commands held running

HOOK = "https://hooks.example.invalid/eregion"


@pytest.fixture(autouse=True)
def _no_drain_followed():
    run_command._FOLLOWED.clear()
    run_command._SUPERSEDED.clear()
    yield
    run_command._FOLLOWED.clear()
    run_command._SUPERSEDED.clear()


@pytest.fixture
def posts(monkeypatch):
    """The webhook set, the bot not: every POST caught, none sent."""
    import requests
    for k in ("GLORFINDEL_DISCORD_BOT", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", HOOK)
    sent: list[dict] = []
    monkeypatch.setattr(requests, "post", lambda url, json=None, timeout=None: sent.append({"url": url, **json}))
    return sent


@pytest.fixture
def bot_on(monkeypatch, posts):
    """The bot configured (as compose tells the watch): the webhook keeps quiet for the notices."""
    monkeypatch.setenv("GLORFINDEL_DISCORD_BOT", "1")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    return posts


def _closures(sent: list[dict]) -> list[str]:
    """The closures among what the webhook carried (a card's notification is not one)."""
    return [p["text"] for p in sent
            if "*Coupure des sessions aboutie*" in p["text"] or "*Coupure des sessions : " in p["text"]]


def _notices() -> list[dict]:
    return [n for n in vm_notices._read() if n["kind"] == "drain_closed"]


# ── the bench of 12/11 ─────────────────────────────────────────────────────────────────────────

def test_a_cut_read_drained_at_the_next_pass_is_closed_once_by_the_webhook(azure, posts):
    """The bench: pending at its first wait, the cycle verified on the NSG, the cut ended before the
    next pass — no pending card ever written, and until DRN2 no message either."""
    f, c = azure
    out = c.isolate_vm(_WEB)
    assert _cycle(c, out)["outcome"]["drain_case"] == "pending"
    f.end_run_commands()
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "Coupure des sessions aboutie" in text and "`web`" in text
    assert "relue 0 s après la demande" in text and "sessions coupées, isolement vérifié" in text
    assert posts[0]["url"] == HOOK and not _drain_cards()
    assert _load_isolation_state(_WEB)["drain"]["status"] == "drained"
    [n] = _notices()
    assert n["key"] == drain_watch.closure_key(_WEB, out["drain"]["asked_at"]) and n["via"] == "webhook"
    assert n["detail"]["outcome"] == "drained" and n["level"] == "ok"
    reassert_pass(c, _ACT)
    reassert_pass(c, _ACT)
    assert len(_closures(posts)) == 1                                   # once


def test_a_cut_that_waited_a_pass_closes_its_card_and_its_announcement(azure, posts):
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    [card] = _drain_cards("drain_pending")
    assert not _closures(posts)                                         # still running: nothing closed
    f.end_run_commands()
    reassert_pass(c, _ACT)
    [closed] = [e for e in escalations.all_escalations() if e["id"] == card["id"]]
    assert closed["status"] == "resolved"
    assert len(_closures(posts)) == 1 and "aboutie" in _closures(posts)[0]


# ── every outcome ─────────────────────────────────────────────────────────────────────────────

def test_a_cut_that_fails_after_its_first_wait_is_closed_as_such(azure, posts):
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands(error=_error(HttpResponseError, 409, "(Conflict) The VM agent is not responding"))
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "Coupure des sessions : sessions restées ouvertes" in text and "relue" in text
    assert "vérification échouée" in text and "Conflict" in text
    [card] = _drain_cards("verification_failed")
    assert card["drain_case"] == "open"
    assert _notices()[0]["level"] == "failed"
    reassert_pass(c, _ACT)
    assert len(_closures(posts)) == 1


def test_a_cut_that_never_ends_is_closed_without_a_conclusion(azure, posts, monkeypatch):
    f, c = azure
    c.isolate_vm(_WEB)
    monkeypatch.setattr(drain_watch, "DRAIN_DEADLINE_S", 0.0)
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "coupure jamais aboutie" in text and "peut-être pas été coupées" in text
    assert _notices()[0]["level"] == "unknown" and _notices()[0]["detail"]["outcome"] == "never"
    reassert_pass(c, _ACT)
    assert len(_closures(posts)) == 1


def test_a_vm_released_before_the_end_of_its_cut_says_it_is_no_longer_followed(azure, posts):
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    c.release_isolation(_WEB)
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "plus suivie" in text and "levée avant sa fin" in text and "journal d'activité" in text
    assert c.followed_drains() == []
    reassert_pass(c, _ACT)
    assert len(_closures(posts)) == 1


def test_a_vm_released_before_any_pass_still_closes_what_it_announced(azure, posts):
    """No pending card ever written (released within the pass): the poller alone names the cut."""
    f, c = azure
    c.isolate_vm(_WEB)
    c.release_isolation(_WEB)
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "plus suivie" in text


# ── once, whatever restarts ───────────────────────────────────────────────────────────────────

def test_a_restart_during_the_cut_closes_it_once(azure, posts):
    """The poller lost: nothing was read — the closure never says « relue » (DRN2 review)."""
    f, c = azure
    c.isolate_vm(_WEB)
    run_command._FOLLOWED.clear()                                       # the watch restarted
    reassert_pass(c, _ACT)
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "coupure jamais aboutie" in text and "redémarrée" in text
    assert "relue" not in text.split(" — ")[0] and " s après la demande" in text


def test_a_watch_stopped_between_the_state_and_its_closure_says_it_at_the_next_pass(azure, posts, monkeypatch):
    """The outcome read on Azure written with its closure due, the closure not said (the watch
    stopped, or the store full): after the restart, the poller gone, the mark says it — once, from
    the state; never a « jamais aboutie » card after the cut ended."""
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands()
    real = vm_notices._record

    def full(notice):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vm_notices, "_record", full)
    report = reassert_pass(c, _ACT)
    state = _load_isolation_state(_WEB)
    assert state["drain"]["status"] == "drained"                        # read on Azure, written
    assert state["drain_closure_due"]["key"] == drain_watch.closure_key(_WEB, state["drain"]["asked_at"])
    assert any(r.get("outcome") == "failed" and "non dite" in r["detail"] for r in report)
    assert not _closures(posts) and not c.followed_drains()
    monkeypatch.setattr(vm_notices, "_record", real)
    run_command._FOLLOWED.clear()                                       # the restart
    reassert_pass(c, _ACT)
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "aboutie" in text and "relue 0 s" in text
    assert "drain_closure_due" not in _load_isolation_state(_WEB)
    assert not _drain_cards() and not [e for e in escalations.pending() if "jamais aboutie" in e["reason"]]


def test_a_card_refused_leaves_the_cut_pending_and_says_nothing(azure, posts, monkeypatch):
    """The card first (L1A): refused, neither the state nor the closure — the next pass says both."""
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands(error=_error(HttpResponseError, 409, "(Conflict) agent"))
    real = escalations.record

    def full(**kw):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(escalations, "record", full)
    reassert_pass(c, _ACT)
    assert _load_isolation_state(_WEB)["drain"]["status"] == "pending" and not _closures(posts)
    monkeypatch.setattr(escalations, "record", real)
    reassert_pass(c, _ACT)
    assert len(_closures(posts)) == 1 and _load_isolation_state(_WEB)["drain"]["status"] == "failed"


# ── a notice decides nothing: the console and the bot write ~/.glorfindel too ─────────────────

def _forge(key: str, drain: dict) -> None:
    """What a writer of the console or the bot could append to the store."""
    import json
    line = {"key": key, "resource_id": _WEB, "kind": "drain_closed", "title": "Coupure des sessions aboutie",
            "text": "tout va bien", "level": "ok", "via": "bot", "at": "2026-11-12T09:24:12+00:00",
            "detail": {"outcome": "drained", "drain": drain}}
    vm_notices._STORE.parent.mkdir(parents=True, exist_ok=True)
    with vm_notices._STORE.open("a") as fh:
        fh.write(json.dumps(line) + "\n")


def test_a_forged_closure_never_writes_the_outcome(azure, posts):
    """A notice « drained » forged under the cut's key while its Run Command still runs: the state
    stays pending and the poller is kept. After a restart, nothing is read: the outcome written is
    `never` (« jamais aboutie »), never the forged « drained ». What the forger can do: silence the
    closure."""
    f, c = azure
    out = c.isolate_vm(_WEB)
    _forge(drain_watch.closure_key(_WEB, out["drain"]["asked_at"]), {"status": "drained"})
    reassert_pass(c, _ACT)
    assert _load_isolation_state(_WEB)["drain"]["status"] == "pending" and c.followed_drains()
    assert _drain_cards("drain_pending")
    run_command._FOLLOWED.clear()                                       # a restart too: never taken from it
    f.end_run_commands(error=_error(HttpResponseError, 409, "(Conflict) The VM agent is not responding"))
    reassert_pass(c, _ACT)
    drain = _load_isolation_state(_WEB)["drain"]
    assert drain["status"] == "failed" and drain.get("never") is True   # not read: never « drained »
    [card] = _drain_cards("verification_failed")
    assert "jamais aboutie" in card["reason"]
    assert not _closures(posts)                                         # silenced, the card says it


def test_an_unreadable_store_never_stops_the_follow(azure, posts):
    """Bytes that are not UTF-8 in the store (a hand, a disk): read line by line, the follow goes on."""
    f, c = azure
    c.isolate_vm(_WEB)
    vm_notices._STORE.parent.mkdir(parents=True, exist_ok=True)
    vm_notices._STORE.write_bytes(b"\xff\xfe{not json\n")
    f.end_run_commands()
    report = reassert_pass(c, _ACT)
    assert not [r for r in report if r.get("vm") == "?"]                # the follow did not fail
    assert _load_isolation_state(_WEB)["drain"]["status"] == "drained"
    assert len(_closures(posts)) == 1


def test_a_store_that_raises_never_stops_the_bot(bot_on, monkeypatch):
    def denied():
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(vm_notices, "for_bot", denied)
    b, _ = _bot({})
    assert asyncio.run(b._post_notices(None)) == 0


# ── a cut asked again before its end ──────────────────────────────────────────────────────────

def test_a_cut_asked_again_before_its_end_closes_the_first_as_taken_again(azure, posts):
    """The same watch isolates the VM anew while its first cut still runs, and the second waits too:
    the first poller replaced — its closure « reprise avant sa fin », once; the second followed."""
    f, c = azure
    first = c.isolate_vm(_WEB)["drain"]["asked_at"]
    second = c.isolate_vm(_WEB)["drain"]["asked_at"]
    assert first != second and c.drain_asked_at(_WEB) == second
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "plus suivie" in text and "reprise avant sa fin" in text
    assert [n["key"] for n in _notices()] == [drain_watch.closure_key(_WEB, first)]
    assert c.superseded_drains() == []
    f.end_run_commands()
    reassert_pass(c, _ACT)
    reassert_pass(c, _ACT)
    assert [n["key"] for n in _notices()] == [drain_watch.closure_key(_WEB, first),
                                              drain_watch.closure_key(_WEB, second)]


def test_a_cut_taken_again_by_one_that_ended_in_time_is_closed_as_taken_again(azure, posts):
    f, c = azure
    c.isolate_vm(_WEB)
    f.hold_run_commands = False
    assert c.isolate_vm(_WEB)["drain"]["status"] == "drained"           # the second within its first wait
    reassert_pass(c, _ACT)
    [text] = _closures(posts)
    assert "reprise avant sa fin" in text and c.followed_drains() == []


def test_a_key_is_said_once():
    first = vm_notices.say(_WEB, "drain:x:1", "drain_closed", "t", "dit")
    assert first == "none" and vm_notices.say(_WEB, "drain:x:1", "drain_closed", "t", "redit") == "already"
    assert [n["text"] for n in vm_notices._read()] == ["dit"]


def test_the_store_keeps_its_last_notices(monkeypatch):
    monkeypatch.setattr(vm_notices, "KEPT", 3)
    for i in range(5):
        vm_notices.say(_WEB, f"k{i}", "drain_closed", "t", str(i))
    assert [n["key"] for n in vm_notices._read()] == ["k2", "k3", "k4"]


# ── where it goes: the VM's thread when the bot is configured ─────────────────────────────────

def test_with_the_bot_configured_the_closure_waits_for_the_bot_and_the_webhook_keeps_quiet(azure, bot_on):
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands()
    reassert_pass(c, _ACT)
    assert not _closures(bot_on)
    [n] = vm_notices.for_bot()
    assert n["via"] == "bot" and "aboutie" in n["text"]


class _Thread:
    def __init__(self):
        self.sent: list = []

    async def send(self, content=None, **kw):
        self.sent.append(content if content is not None else kw)


def _bot(threads: dict):
    pytest.importorskip("discord")
    from glorfindel import bot
    b = bot.GlorfindelBot(channel_id=1, ping_role=4242)
    opened: list = []

    async def thread(channel, rid, ping=True):
        opened.append((rid, ping))
        return threads.setdefault(rid, _Thread())
    b._get_or_create_thread = thread
    return b, opened


def test_the_bot_posts_the_closure_in_the_vm_s_thread_once_even_after_its_restart(azure, bot_on):
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands()
    reassert_pass(c, _ACT)
    threads: dict = {}
    b, opened = _bot(threads)
    b._threads = {_WEB.upper(): 77}                                     # the VM's thread, its cards' key
    assert asyncio.run(b._post_notices(None)) == 1
    assert opened == [(_WEB.upper(), False)]                            # its thread, the role not pinged
    [msg] = threads[_WEB.upper()].sent
    assert msg.startswith("✅ **Coupure des sessions aboutie** · `web`") and "relue 0 s" in msg
    assert asyncio.run(b._post_notices(None)) == 0
    again, _ = _bot(threads)                                            # the bot restarted
    assert asyncio.run(again._post_notices(None)) == 0
    assert len(threads[_WEB.upper()].sent) == 1


def test_a_post_that_fails_is_tried_again_at_the_next_turn(bot_on):
    vm_notices.say(_WEB, "drain:k:1", "drain_closed", "Coupure des sessions aboutie", "dit", level="ok")
    b, _ = _bot({})

    async def down(channel, rid, ping=True):
        raise RuntimeError("Discord down")
    b._get_or_create_thread = down
    assert asyncio.run(b._post_notices(None)) == 0
    threads: dict = {}
    b2, _ = _bot(threads)
    assert asyncio.run(b2._post_notices(None)) == 1


def test_an_old_notice_is_not_posted(bot_on, monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    monkeypatch.setattr(vm_notices, "for_bot", lambda: [{
        "key": "drain:k:old", "resource_id": _WEB, "kind": "drain_closed", "title": "t",
        "text": "il y a deux jours", "level": "unknown", "via": "bot", "at": old}])
    threads: dict = {}
    b, _ = _bot(threads)
    assert asyncio.run(b._post_notices(None)) == 0 and not threads


# ── what reaches a chat is inert ──────────────────────────────────────────────────────────────

EVIL_VM = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/[x](https://evil.example)"


def test_the_bot_s_message_escapes_what_comes_from_outside():
    msg = vm_notices.bot_message({"resource_id": EVIL_VM, "title": "Coupure", "level": "ok",
                                  "text": "@everyone [support](https://evil.example) <@&1>"})
    assert "@everyone" not in msg and "\\[support\\]\\(https://evil.example\\)" in msg
    assert "\\<@&1\\>" in msg


def test_the_webhook_s_text_escapes_what_comes_from_outside():
    text = vm_notices.webhook_payload({"resource_id": EVIL_VM, "title": "Coupure", "level": "failed",
                                       "text": "<!channel> [a](https://evil.example)\nligne"})["text"]
    assert "<!channel>" not in text and "‹!channel›" in text and "](https" not in text
    assert text.startswith(":rotating_light: *Coupure*") and "\nligne" not in text
