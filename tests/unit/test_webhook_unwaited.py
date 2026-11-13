"""JUG2c (#788): without the bot, neither a cut's closure nor the reassertion waits for a webhook.

JUG2b (#768) took the fallback out of the watch's loop (`relay_pass`, its own thread), but two paths
still posted where they were: without the bot, a session cut's closure went by the webhook from
`vm_notices.say`, under the VM's lock (an isolation of that VM waited for the POST); and every card
the reassertion writes went by `escalations._notify` (`requests.post`, 5 s, the name's resolution
unbounded) from its thread — the reassertion of every VM waited for that webhook.

Now no webhook is waited for where it must not be (`vm_notices.must_defer`): under a VM's lock, or in
the reassertion's pass (`vm_notices.deferred`). There the notice is queued (`via: outbox`), once by
its key, and a pass of the watch posts it in its own thread, bounded, the name included — at once
where the watch serves the queue (`serve`, `_kick`), else at its next relay pass. A post that fails
leaves it in the queue, a try counted; a 2xx notes it sent, never said again.

On the in-memory Azure (tests/unit/fake_azure.py, DRN1's set-up), a fake webhook (`requests.post`
caught, held when a test says so): no cloud call, no model call, nothing sent.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from glorfindel import actions, escalations, vm_notices
from glorfindel.actions import _load_isolation_state, _vm_lock
from glorfindel.providers.azure import run_command
from glorfindel.reassert import reassert_pass

from . import test_drain_follow as _follow
from .test_drain_follow import _ACT, _WEB, _drain_cards

azure = _follow.azure          # web, its Run Commands held running (the quarantine of 09/11)

HOOK = "https://hooks.example.invalid/eregion"
# Long enough for a pass that does not wait, far below the 10 s a POST is bounded to (POST_DEADLINE_S).
QUICK_S = 3.0


class _Answer:
    def __init__(self, status: int = 200):
        self.status_code = status
        self.headers: dict = {}

    def json(self):
        return {}


@pytest.fixture(autouse=True)
def _no_drain_followed():
    run_command._FOLLOWED.clear()
    run_command._SUPERSEDED.clear()
    yield
    run_command._FOLLOWED.clear()
    run_command._SUPERSEDED.clear()


def _join(*names: str) -> None:
    for t in threading.enumerate():
        if t.name in names:
            t.join(10)


@pytest.fixture
def hook(monkeypatch):
    """The webhook set, the bot not. Every POST caught, none sent; `hold` set, a POST does not answer
    until the test (or its end) lets it go — 30 s at most: a pass it held fails, never hangs."""
    import requests
    for k in ("GLORFINDEL_DISCORD_BOT", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", HOOK)
    h = SimpleNamespace(sent=[], threads=[], answer=_Answer(), hold=threading.Event(),
                        release=threading.Event())

    def post(url, json=None, timeout=None):
        h.sent.append({"url": url, **(json or {})})
        h.threads.append(threading.current_thread().name)
        if h.hold.is_set():
            h.release.wait(30)
        return h.answer
    monkeypatch.setattr(requests, "post", post)
    yield h
    h.release.set()
    _join("webhook-post", "notice-outbox", "notice-detached", "pass")


def _in_a_thread(fn, *args) -> threading.Thread:
    """`fn(*args)` in a thread, waited for QUICK_S: alive after it, it waits for something."""
    t = threading.Thread(target=fn, args=args, daemon=True, name="pass")
    t.start()
    t.join(QUICK_S)
    return t


def _queued(kind: str) -> list[dict]:
    return [n for n in vm_notices._read() if n["kind"] == kind]


# ── the two paths of the issue ────────────────────────────────────────────────────────────────

def test_a_cut_s_closure_holds_neither_the_vm_s_lock_nor_the_reassertion(azure, hook, monkeypatch):
    """The webhook never answers: the reassertion reads the cut drained, writes it, and returns at
    once; the closure waits in the queue. The watch's relay pass posts it in its own thread — the VM's
    lock free all along, a second reassertion unhindered — and once its post ends it is noted sent,
    never said again."""
    f, c = azure
    out = c.isolate_vm(_WEB)
    f.end_run_commands()
    hook.hold.set()
    t = _in_a_thread(reassert_pass, c, _ACT)
    assert not t.is_alive(), "the reassertion waited for the webhook"
    assert hook.sent == []                                              # nothing posted from the pass
    assert _load_isolation_state(_WEB)["drain"]["status"] == "drained"
    [n] = _queued(vm_notices.CLOSURE_KIND)
    assert n["via"] == vm_notices.OUTBOX and n["queued"] is True
    assert n["key"] == f"drain:{_WEB.lower()}:{out['drain']['asked_at']}"
    # The watch's relay pass, its POST unanswered past the deadline: it returns, the post goes on.
    monkeypatch.setattr(vm_notices, "POST_DEADLINE_S", 0.2)
    assert vm_notices.relay_pass() == 0
    assert len(hook.sent) == 1 and hook.threads == ["webhook-post"]
    with _vm_lock("web", timeout=1):                                    # the VM's lock is free
        pass
    assert not _in_a_thread(reassert_pass, c, _ACT).is_alive()
    hook.release.set()
    _join("webhook-post")
    assert vm_notices.said(n["key"])["relayed"]["sent"] is True         # its late 2xx, noted
    vm_notices.relay_pass()
    reassert_pass(c, _ACT)
    vm_notices.relay_pass()
    assert len(hook.sent) == 1                                          # once


def test_a_card_the_reassertion_writes_under_the_vm_s_lock_is_queued_then_said_once(azure, hook):
    """The cut still running: its card « coupure en attente » is written under the VM's lock, from the
    reassertion's thread. Its notification is queued, by the card's id, then posted by the relay pass
    in the message the webhook always had — once, however many passes after."""
    f, c = azure
    c.isolate_vm(_WEB)
    hook.hold.set()
    assert not _in_a_thread(reassert_pass, c, _ACT).is_alive()
    [card] = _drain_cards("drain_pending")
    assert hook.sent == []
    [n] = _queued(vm_notices.CARD_KIND)
    assert n["key"] == f"card:{card['id']}" and n["via"] == vm_notices.OUTBOX
    hook.hold.clear()
    assert vm_notices.relay_pass() == 1
    [p] = hook.sent
    assert p["url"] == HOOK and p["text"] == escalations.card_payload(card)["text"]
    assert p["text"].startswith(":rotating_light: *Coupure des sessions en attente")
    reassert_pass(c, _ACT)
    assert vm_notices.relay_pass() == 0 and len(hook.sent) == 1


def test_a_card_the_reassertion_writes_outside_any_lock_waits_for_no_webhook(azure, hook):
    """A local state that does not read: the reassertion says it on a card, no VM's lock held — its
    pass still waits for no webhook."""
    f, c = azure
    actions._ISOLATION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    (actions._ISOLATION_STATE_DIR / "other--00000000.json").write_text('{"resource_id": ')
    hook.hold.set()
    assert not _in_a_thread(reassert_pass, c, _ACT).is_alive(), "the reassertion waited for the webhook"
    [card] = [e for e in escalations.pending() if e["signal_id"].startswith("state-unreadable-")]
    assert hook.sent == []
    assert [n["key"] for n in _queued(vm_notices.CARD_KIND)] == [f"card:{card['id']}"]


def test_under_a_vm_s_lock_alone_nothing_is_posted(hook):
    """Wherever the lock of a VM is held — the reassertion or not —, a closure and a card are queued."""
    hook.hold.set()
    started = time.monotonic()
    with _vm_lock("web"):
        assert vm_notices.must_defer()
        via = vm_notices.say(_WEB, "drain:k:1", vm_notices.CLOSURE_KIND, "Coupure des sessions aboutie", "dit")
        escalations.record(signal_id="s-1", resource_id=_WEB, action="isolate_vm",
                           escalation_type="verification_failed", reason="vérification échouée")
    assert time.monotonic() - started < QUICK_S
    assert via == "queued" and hook.sent == []
    assert not vm_notices.must_defer()                                  # the lock released
    hook.hold.clear()
    assert vm_notices.relay_pass() == 2 and len(hook.sent) == 2


def test_elsewhere_a_card_is_still_posted_at_once(hook):
    """The graph's cycle, the console, the CLI: no lock, no reassertion — posted at once, as always;
    bounded as every post since JUG2d (#799: its own thread, the name's resolution included)."""
    escalations.record(signal_id="s-2", resource_id=_WEB, action="isolate_vm",
                       escalation_type="mode_hold", reason="retenue")
    assert len(hook.sent) == 1 and hook.threads == ["webhook-post"]
    assert not vm_notices._read()


# ── once: never lost, never twice ─────────────────────────────────────────────────────────────

def test_a_queued_notice_the_webhook_refuses_stays_in_the_queue(hook):
    """A 500: back in the queue, a try counted — never given to a bot that is not there; the next
    pass says it, then never again."""
    with vm_notices.deferred():
        assert vm_notices.say(_WEB, "drain:k:2", vm_notices.CLOSURE_KIND, "Coupure", "dit") == "queued"
    hook.answer = _Answer(500)
    assert vm_notices.relay_pass() == 0
    n = vm_notices.said("drain:k:2")
    assert n["via"] == vm_notices.OUTBOX and n["tries"] == 1 and "relayed" not in n
    hook.answer = _Answer(200)
    assert vm_notices.relay_pass() == 1
    assert vm_notices.relay_pass() == 0
    assert len(hook.sent) == 2
    assert vm_notices.said("drain:k:2")["relayed"]["sent"] is True


def test_a_key_is_queued_once(hook):
    with vm_notices.deferred():
        assert vm_notices.say(_WEB, "drain:k:3", vm_notices.CLOSURE_KIND, "t", "dit") == "queued"
        assert vm_notices.say(_WEB, "drain:k:3", vm_notices.CLOSURE_KIND, "t", "redit") == "already"
    assert vm_notices.relay_pass() == 1 and len(hook.sent) == 1


def test_a_notice_already_posted_before_jug2c_is_never_said_again(hook):
    """A notice the webhook carried at once (`via: webhook`, never queued): no pass posts it."""
    vm_notices.say(_WEB, "drain:k:4", vm_notices.CLOSURE_KIND, "t", "dit")
    assert len(hook.sent) == 1 and vm_notices.said("drain:k:4")["via"] == "webhook"
    assert vm_notices.relay_pass() == 0 and len(hook.sent) == 1


def test_the_store_full_a_card_is_posted_from_a_thread_of_its_own(hook, monkeypatch):
    """The queue refused (a full disk): the card is still said, from a thread nobody waits for."""
    def full(notice):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vm_notices, "_record", full)
    hook.hold.set()
    started = time.monotonic()
    with _vm_lock("web"):
        escalations.record(signal_id="s-3", resource_id=_WEB, action="isolate_vm",
                           escalation_type="verification_failed", reason="vérification échouée")
    assert time.monotonic() - started < QUICK_S
    deadline = time.monotonic() + 5
    while not hook.sent and time.monotonic() < deadline:
        time.sleep(0.01)
    assert len(hook.sent) == 1 and hook.threads == ["webhook-post"]


# ── the watch serves the queue ────────────────────────────────────────────────────────────────

def test_where_the_watch_serves_the_queue_a_pass_starts_at_once(hook, monkeypatch):
    monkeypatch.setattr(vm_notices, "_SERVED", True)
    with vm_notices.deferred():
        assert vm_notices.say(_WEB, "drain:k:5", vm_notices.CLOSURE_KIND, "t", "dit") == "queued"
    _join("notice-outbox")
    assert len(hook.sent) == 1 and hook.threads == ["webhook-post"]
    assert vm_notices.said("drain:k:5")["relayed"]["sent"] is True


def test_a_notice_queued_while_a_pass_runs_gets_a_pass_of_its_own(monkeypatch):
    """Queued after the running pass read the store: that pass starts one more at its end — never
    left to the next minute. Nothing queued meanwhile, none more."""
    started: list[int] = []
    monkeypatch.setattr(vm_notices, "_SERVED", True)
    monkeypatch.setattr(vm_notices, "_start_pass", lambda: started.append(1))
    monkeypatch.setattr(vm_notices, "_relay_pass", lambda now: (vm_notices._kick(), 0)[1])
    vm_notices.relay_pass()
    assert started == [1, 1]                                            # the kick's, then the pass's own
    started.clear()
    monkeypatch.setattr(vm_notices, "_relay_pass", lambda now: 0)
    vm_notices.relay_pass()
    assert started == []


def test_outside_the_watch_a_queued_notice_waits_for_its_pass(monkeypatch):
    started: list[int] = []
    monkeypatch.setattr(vm_notices, "_start_pass", lambda: started.append(1))
    vm_notices._kick()
    assert started == []


def test_the_watch_serves_the_queue():
    cli = (Path(__file__).resolve().parents[2] / "glorfindel" / "cli.py").read_text(encoding="utf-8")
    assert "_served_notices.serve()" in cli


# ── what a queued notice says ─────────────────────────────────────────────────────────────────

def test_an_action_queued_for_the_webhook_pings_no_one(hook, monkeypatch):
    """Without the bot an action was never a ping (JUG1): queued, still none."""
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", "https://discord.com/api/webhooks/123/fake-token/slack")
    monkeypatch.setenv("DISCORD_PING_ROLE", "4242")
    with vm_notices.deferred():
        via = escalations.notify_action("isolate_vm", _WEB, "run-1", 0.9, "isolée seule", True,
                                        key="executed:x")
    assert via == "queued" and hook.sent == []
    assert vm_notices.relay_pass() == 1
    [p] = hook.sent
    assert "4242" not in str(p) and p["url"].endswith("/slack")
    assert vm_notices.said("executed:x")["relayed"]["ping"] is False


def test_a_forged_queued_card_posts_only_escaped_text(hook):
    """The console and the bot write ~/.glorfindel too: a card forged in the queue is written at its
    post as `_notify` writes a card — every outside word escaped (SEC6)."""
    vm_notices._record({"key": "card:forged", "resource_id": _WEB, "kind": vm_notices.CARD_KIND,
                        "title": "t", "text": "t", "level": "failed", "via": vm_notices.OUTBOX,
                        "queued": True, "at": "2099-01-01T00:00:00+00:00",
                        "detail": {"card": {"action": "isolate_vm", "escalation_type": "mode_hold",
                                            "reason": "<!channel> @everyone [a](https://evil.example)"}}})
    vm_notices._record({"key": "card:forged-2", "resource_id": _WEB, "kind": vm_notices.CARD_KIND,
                        "title": "t", "text": "<!here>", "level": "failed", "via": vm_notices.OUTBOX,
                        "queued": True, "at": "2099-01-01T00:00:00+00:00", "detail": {"card": "?"}})
    vm_notices.relay_pass()
    texts = [p["text"] for p in hook.sent]
    assert len(texts) == 2
    assert all("<!channel>" not in t and "<!here>" not in t and "](https" not in t for t in texts)
    assert "‹!channel›" in texts[0]


def test_holds_vm_lock_says_whether_this_thread_holds_one():
    from glorfindel.response.locks import holds_vm_lock
    assert not holds_vm_lock()
    with _vm_lock("web"):
        assert holds_vm_lock()
        with _vm_lock("web"):
            assert holds_vm_lock()
        assert holds_vm_lock()
        seen: list[bool] = []
        t = threading.Thread(target=lambda: seen.append(holds_vm_lock()))
        t.start()
        t.join()
        assert seen == [False]                                          # another thread's, not this one's
    assert not holds_vm_lock()


# ── a one-off command, without the watch (JUG2c review) ───────────────────────────────────────

def _isolated_long_ago(vm: str = "web") -> None:
    from glorfindel.actions import _save_isolation_state
    rid = f"/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/{vm}"
    _save_isolation_state(vm, {"resource_id": rid, "isolated_at": "2026-10-06T08:00:00+00:00",
                               "placements": []})


def test_check_ttl_from_cron_says_its_card_to_the_webhook(hook):
    """`glorfindel check-ttl` (« Safe to run from cron », `make glorfindel-check-ttl` in a container of
    its own): its card is written under the VM's lock, so its notification is queued — no watch to
    post it, the command posts it before it ends, outside the lock, once."""
    from click.testing import CliRunner

    from glorfindel.cli import cli
    _isolated_long_ago()
    r = CliRunner().invoke(cli, ["check-ttl", "--ttl", "4"])
    assert r.exit_code == 0, r.output
    [card] = [e for e in escalations.pending() if e["escalation_type"] == "ttl_exceeded"]
    assert [p["text"] for p in hook.sent] == [escalations.card_payload(card)["text"]]
    assert hook.threads == ["webhook-post"]                              # bounded, as every post
    assert vm_notices.said(f"card:{card['id']}")["relayed"]["sent"] is True
    assert CliRunner().invoke(cli, ["check-ttl", "--ttl", "4"]).exit_code == 0
    assert len(hook.sent) == 1                                          # once


def test_check_ttl_waits_for_no_webhook_beyond_its_bound(hook, monkeypatch):
    """The webhook never answers: the command ends once its post is past the deadline."""
    from click.testing import CliRunner

    from glorfindel.cli import cli
    _isolated_long_ago()
    monkeypatch.setattr(vm_notices, "POST_DEADLINE_S", 0.2)
    hook.hold.set()
    started = time.monotonic()
    r = CliRunner().invoke(cli, ["check-ttl", "--ttl", "4"])
    assert r.exit_code == 0, r.output
    assert time.monotonic() - started < QUICK_S
    assert len(hook.sent) == 1


def test_a_queued_notice_the_webhook_keeps_failing_is_tried_three_times_then_no_more(hook):
    """A webhook that answers 500 every time: three posts, a try each (`RELAY_MAX_TRIES`), then no
    pass posts it again — never a card a minute for 24 h."""
    with vm_notices.deferred():
        assert vm_notices.say(_WEB, "drain:k:6", vm_notices.CLOSURE_KIND, "Coupure", "dit") == "queued"
    hook.answer = _Answer(500)
    for _ in range(vm_notices.RELAY_MAX_TRIES):
        assert vm_notices.relay_pass() == 0
    assert len(hook.sent) == vm_notices.RELAY_MAX_TRIES
    n = vm_notices.said("drain:k:6")
    assert n["tries"] == vm_notices.RELAY_MAX_TRIES and n["via"] == vm_notices.OUTBOX
    assert vm_notices.relay_pass() == 0
    assert len(hook.sent) == vm_notices.RELAY_MAX_TRIES                 # the fourth pass posts nothing


def test_at_the_cap_the_log_says_where_a_queued_notice_stays(caplog):
    """Queued for the webhook, the bot not configured: at the cap it waits for no bot — the log says
    it is said no more, but in the console."""
    import logging
    queued = {"key": "card:x", "queued": True, "tries": vm_notices.RELAY_MAX_TRIES - 1}
    relayed = {"key": "action:y", "tries": vm_notices.RELAY_MAX_TRIES - 1}
    with caplog.at_level(logging.WARNING, logger=vm_notices.log.name):
        vm_notices._count_try(queued)
        vm_notices._count_try(relayed)
    [q, r] = [rec.getMessage() for rec in caplog.records if rec.name == vm_notices.log.name]
    assert "card:x" in q and "waits for the bot" not in q and "console" in q
    assert "action:y" in r and "waits for the bot" in r
