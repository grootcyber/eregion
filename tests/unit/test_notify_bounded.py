"""JUG2d (#799): without the bot, a card posted at once has its name's resolution bounded too; and
`check-ttl` says what it does.

JUG2c (#788) queued a card where no webhook may be waited for (a VM's lock, the reassertion's pass);
elsewhere — the graph's cycle, the console, the CLI — `escalations._notify` still posted it from its
caller's thread with `requests.post(url, timeout=5)`, which bounds the connection and the read, not the
name's resolution (`getaddrinfo`): a resolver that does not answer held the watch's cycle. Now that post
goes as every post of the notices (`vm_notices.post_webhook`): in a thread of its own, waited for
`POST_DEADLINE_S`, the resolution included — one post, never cut, never posted again, nothing queued.

`check-ttl` posts the card it queued outside the VM's lock (the relay pass, after `ttl_alerts`): an
isolation of that VM never waits for the webhook. And README, the Makefile's help, the command's help
and its card say it escalates — never that it releases (Q1).

No network: the webhook's `requests.post` is caught, or the name's resolution (`socket.getaddrinfo`)
held then refused; no cloud call, no model call.
"""
from __future__ import annotations

import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from glorfindel import escalations, vm_notices
from glorfindel.actions import _save_isolation_state, _vm_lock
from glorfindel.response.locks import holds_vm_lock

ROOT = Path(__file__).resolve().parents[2]
HOOK = "https://hooks.example.invalid/eregion"
_WEB = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/web"
# Long enough for a call that does not wait, far above the deadline the tests set (0.2 s).
QUICK_S = 3.0
_PROXIES = ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy")


class _Answer:
    def __init__(self, status: int = 200):
        self.status_code = status
        self.headers: dict = {}

    def json(self):
        return {}


def _join(*names: str) -> None:
    for t in threading.enumerate():
        if t.name in names:
            t.join(10)


def _no_bot(monkeypatch) -> None:
    for k in ("GLORFINDEL_DISCORD_BOT", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", HOOK)


@pytest.fixture
def hook(monkeypatch):
    """The webhook set, the bot not. Every POST caught, none sent; `hold` set, a POST does not answer
    until the test (or its end) lets it go — 30 s at most. Each POST notes whether the lock of the VM
    `web` was free while it ran (taken from its own thread, 0.5 s at most)."""
    import requests
    _no_bot(monkeypatch)
    h = SimpleNamespace(sent=[], threads=[], free=[], answer=_Answer(), hold=threading.Event(),
                        release=threading.Event())

    def post(url, json=None, timeout=None):
        h.sent.append({"url": url, **(json or {})})
        h.threads.append(threading.current_thread().name)
        try:
            with _vm_lock("web", timeout=0.5):
                h.free.append(True)
        except TimeoutError:
            h.free.append(False)
        if h.hold.is_set():
            h.release.wait(30)
        return h.answer
    monkeypatch.setattr(requests, "post", post)
    yield h
    h.release.set()
    _join("webhook-post", "notice-outbox", "notice-detached", "graph")


def _record(reason: str = "retenue") -> str:
    return escalations.record(signal_id="s-1", resource_id=_WEB, action="isolate_vm",
                              escalation_type="mode_hold", reason=reason)


def _card(cid: str) -> dict:
    return next(e for e in escalations.pending() if e["id"] == cid)


# ── the post at once, bounded ─────────────────────────────────────────────────────────────────

def test_a_name_that_never_resolves_holds_the_graph_s_cycle_no_longer_than_the_bound(monkeypatch):
    """The issue's path: the graph's cycle escalates (`escalate_to_human`, no lock, no reassertion), the
    webhook's name never resolves — `getaddrinfo` held, then refused. The node returns once the post's
    deadline is past, the resolution still running in the post's own thread; its card is written."""
    from glorfindel.agent import escalate_to_human

    from .test_agent_nodes import _state
    _no_bot(monkeypatch)
    for k in _PROXIES:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(vm_notices, "POST_DEADLINE_S", 0.2)
    resolving, release = threading.Event(), threading.Event()
    asked: list[str] = []

    def never_resolves(host, *args, **kwargs):
        asked.append(host)
        resolving.set()
        release.wait(30)
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
    monkeypatch.setattr(socket, "getaddrinfo", never_resolves)
    state = _state(action="restore_from_backup", escalation_reason="à valider")
    t = threading.Thread(target=escalate_to_human, args=(state,), daemon=True, name="graph")
    try:
        t.start()
        t.join(QUICK_S)
        assert resolving.is_set(), "the card's post never started"
        assert not t.is_alive(), "the graph's cycle waited for the webhook's name"
        assert asked == ["hooks.example.invalid"]
    finally:
        release.set()
        t.join(10)
        _join("webhook-post")
    assert [e["escalation_type"] for e in escalations.pending()] == ["destructive_action"]
    assert vm_notices._read() == []                                     # posted at once, never queued


def test_a_card_posted_at_once_is_said_once_past_the_deadline(hook, monkeypatch):
    """The webhook does not answer: `record` returns at the deadline, the post goes on in its thread —
    never cut, never posted again. Its message is the card's, as always (`card_payload`)."""
    monkeypatch.setattr(vm_notices, "POST_DEADLINE_S", 0.2)
    hook.hold.set()
    started = time.monotonic()
    cid = _record()
    assert time.monotonic() - started < QUICK_S
    assert hook.threads == ["webhook-post"]                             # never from the caller's thread
    hook.release.set()
    _join("webhook-post")
    [p] = hook.sent
    assert p["url"] == HOOK and p["text"] == escalations.card_payload(_card(cid))["text"]
    assert vm_notices._read() == []
    assert vm_notices.relay_pass() == 0 and len(hook.sent) == 1         # once


def test_a_card_the_webhook_refuses_is_not_posted_again(hook):
    """A 500 at once: said in the log, as before — no queue, no second post by a pass."""
    hook.answer = _Answer(500)
    _record()
    _join("webhook-post")
    assert len(hook.sent) == 1
    assert vm_notices._read() == []
    assert vm_notices.relay_pass() == 0 and len(hook.sent) == 1


# ── check-ttl: its queued card posted outside the VM's lock ───────────────────────────────────

def test_check_ttl_posts_its_queued_card_outside_the_vm_s_lock(hook, monkeypatch):
    """`check-ttl` writes its card under the VM's lock — queued (JUG2c) — and posts it from the relay
    pass it runs once `ttl_alerts` let go of the lock: the pass runs holding no VM's lock, and the lock
    of `web` is free while the webhook is called — an isolation of that VM waits for no webhook."""
    from click.testing import CliRunner

    from glorfindel.cli import cli
    _save_isolation_state("web", {"resource_id": _WEB, "isolated_at": "2026-10-06T08:00:00+00:00",
                                  "placements": []})
    held: list[bool] = []
    real = vm_notices.relay_pass

    def relay_pass(now=None):
        held.append(holds_vm_lock())
        return real(now)
    monkeypatch.setattr(vm_notices, "relay_pass", relay_pass)
    r = CliRunner().invoke(cli, ["check-ttl", "--ttl", "4"])
    assert r.exit_code == 0, r.output
    [card] = [e for e in escalations.pending() if e["escalation_type"] == "ttl_exceeded"]
    assert [p["text"] for p in hook.sent] == [escalations.card_payload(card)["text"]]
    assert held == [False]                                              # one pass, outside the lock
    assert hook.free == [True]                                          # the VM's lock free at its post
    assert vm_notices.said(f"card:{card['id']}")["relayed"]["sent"] is True


# ── what check-ttl says it does ───────────────────────────────────────────────────────────────

def _lines(rel: str, needle: str) -> list[str]:
    return [ln for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines() if needle in ln]


def test_readme_and_the_makefile_say_check_ttl_escalates():
    """Q1: past the TTL an isolation is escalated, never released — README, the Makefile's help."""
    [cmd] = _lines("README.md", "glorfindel check-ttl  ")
    assert "escalate" in cmd and "release isolations" not in cmd
    [env] = _lines("README.md", "GLORFINDEL_ISOLATION_TTL_H=4")
    assert "auto-release" not in env and "never" in env
    [helpline] = _lines("Makefile", "make glorfindel-check-ttl ")
    assert "Escalate" in helpline and "Release" not in helpline


def test_check_ttl_s_help_and_its_card_never_say_released():
    from click.testing import CliRunner

    from glorfindel.cli import cli
    out = CliRunner().invoke(cli, ["check-ttl", "--help"]).output
    assert "auto-release" not in out and "never a release" in " ".join(out.split())
    label = escalations._ESCALATION_LABELS["ttl_exceeded"]
    assert "jamais levée" in label and "levée à" not in label
