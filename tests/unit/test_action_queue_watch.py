"""FS1b (#563, docs/design/file-actions-signee.md §2.5–§2.13): the watch picks the signed action queue
up — on the in-memory Azure (tests/unit/fake_azure.py), from end to end: a request signed, deposited,
picked up, executed, and its receipt; then each refusal, a replay, a forged card, another service's
key, the flag absent, an unreadable register, a stop between the claim and the execution; the guards
of the console replayed by the watch; the console's and the bot's deposits.

The keys come from fixed seeds, or are drawn in tmp (tests/unit/conftest.py): never a real key. A
throwaway HOME, runs/ in tmp, no Azure, no network, no model. The oracles are the fake's flows and
the receipts the watch signs — never the code's markers (A0). Mutants M3975–M4014
(scripts/mutants/FS1b.py) are measured here and in test_action_queue.py.
"""
from __future__ import annotations

import collections
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

import eregion_core.action_queue as aq
import eregion_core.watch_key as watch_key
from glorfindel import approval, escalations, queue_watch
from glorfindel.actions import AzureConnector

from .fake_azure import ATTACKER, FakeAzure, open_flows, vm_id
from .test_invariants import _TEMPLATES, _rule

WATCH = watch_key.Signer(bytes(range(32)))
CONSOLE = watch_key.Signer(bytes(range(40, 72)))
BOT = watch_key.Signer(bytes(range(80, 112)))
STRANGER = watch_key.Signer(bytes(range(120, 152)))
PINS = {"console": CONSOLE.public, "bot": BOT.public}
WEB = vm_id("rg-app1", "web")
SIGNERS = {"console": CONSOLE, "bot": BOT}
DISCORD = {"via": "discord", "user": "111", "name": "an operator"}
ALLOWED = {"DISCORD_ALLOWED_USERS": "111"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    return make_world(tmp_path, monkeypatch)


def make_world(tmp_path, monkeypatch) -> dict:
    """web on a subnet whose NSG lets SSH in, a real connector on the in-memory Azure; runs/ and
    the watch's register in tmp; the watch's key signs its proposals; isolation by rules (also
    test_action_queue_async.py's world, FS1c)."""
    for var in ("GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "GLORFINDEL_READ_ONLY",
                "GLORFINDEL_APPROVAL_MAX_AGE_H", "DISCORD_ALLOWED_USERS", "DISCORD_ALLOWED_ROLES"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "s")
    monkeypatch.chdir(tmp_path)
    f = FakeAzure()
    subnet = f.add_subnet("rg-net", "vnet-hub", "app",
                          f.add_nsg("rg-net", "nsg-subnet", [_rule("allow-ssh", 100, _TEMPLATES["allow-ssh"])]))
    f.add_vm("rg-app1", "web", [{"rg": "rg-app1", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                 "nsg": f.add_nsg("rg-app1", "nsg-web-nic")}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    escalations.sign_proposals(lambda: WATCH)
    said: list[str] = []
    q = queue_watch.QueueWatch(WATCH, c, root=tmp_path / "runs", pins=PINS, say=said.append, inline=True,
                               environ=ALLOWED)
    return {"fake": f, "conn": c, "root": tmp_path / "runs", "q": q, "said": said, "tmp": tmp_path}


def _flows(w):
    f = w["fake"]
    return {x for x in open_flows({"nsgs": f.nsgs, "nics": f.nics, "subnets": f.subnets, "vms": f.vms}, WEB)
            if x[3] == ATTACKER}


def _rules(w) -> dict:
    return {n: dict(r) for g in w["fake"].nsgs.values() for n, r in g["rules"].items()}


def _card(action="isolate_vm", etype="mode_hold", ip="", port=None) -> dict:
    params = {k: v for k, v in (("ip", ip), ("port", port)) if v}
    cid = escalations.record(signal_id="watch-rule-1", resource_id=WEB, action=action, escalation_type=etype,
                             reason="held", action_params=params or None)
    return next(e for e in escalations.all_escalations() if e["id"] == cid)


def _ask(w, verb, *, service="console", signer=None, card=None, ip="", scope="", by=None, now=None,
         resource_id=WEB, lifetime_s=aq.MAX_LIFETIME_S, **kw) -> dict:
    signer = signer or SIGNERS[service]
    doc = aq.new_request(signer, service=service, verb=verb, resource_id=resource_id, ip=ip, scope=scope,
                         by=by if by is not None else ({"via": "console-token", "session": "0a1b2c3d"}
                                                       if service == "console" else DISCORD),
                         card=(card["id"], aq.digest(card["proposal"])) if card else None, now=now,
                         lifetime_s=lifetime_s, **kw)
    aq.deposit(doc, w["root"])
    return doc


def _receipt(w, doc, service=None) -> dict:
    got = aq.read_receipt(service or doc["service"], doc["id"], root=w["root"], watch_public=WATCH.public)
    assert got is not None, "no receipt"
    return got


def _code(w, doc) -> str:
    r = _receipt(w, doc)
    assert r["state"] == "refused", r
    return r["code"]


def _cards(etype) -> list[dict]:
    return [e for e in escalations.pending() if e["escalation_type"] == etype]


# ── From end to end ──────────────────────────────────────────────────────────────────

def test_an_approval_signed_deposited_picked_up_executed_and_answered(world):
    """The lot's case: a card the watch proposed, a request the console signed for it, the watch
    picks it up, isolates web on the fake, checks it, settles the card, and signs its receipt."""
    assert _flows(world)
    card = _card()
    doc = _ask(world, "isolate_vm", card=card)
    out = world["q"].poll()
    assert [r["state"] for r in out] == ["done"]
    assert not _flows(world), "web isolated"
    r = _receipt(world, doc)
    assert (r["state"], r["verb"], r["resource_id"], r["card"]) == ("done", "isolate_vm", WEB, card["id"])
    assert r["verification"]["verified"] is True
    assert "sig" in r and aq.watch_refusal(r, "receipt", WATCH.public) == ""
    assert aq.watch_refusal(r, "proposal", WATCH.public)          # a receipt never reads as a proposal
    assert doc["sig"] not in json.dumps(r)                          # never the request's signature
    assert card["id"] not in {e["id"] for e in escalations.pending()}, "the card settled"
    assert world["q"].poll() == [], "judged once"


def test_a_request_runs_once_however_often_it_is_polled_or_the_watch_restarts(world):
    card = _card()
    doc = _ask(world, "isolate_vm", card=card)
    world["q"].poll()
    again = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                                   say=lambda s: None)
    assert again.poll() == []
    assert _receipt(world, doc)["state"] == "done"


def test_a_block_runs_on_the_address_and_the_reach_of_the_card(world):
    card = _card("block_suspicious_ip", "low_confidence", ip=ATTACKER, port=22)
    doc = _ask(world, "block_ip", card=card, ip=ATTACKER, scope="vm")
    world["q"].poll()
    r = _receipt(world, doc)
    assert r["state"] == "done" and r["verification"]["verified"] is True, r
    assert not _flows(world)


def test_the_bot_reverts_a_card_whose_check_failed(world):
    world["conn"].isolate_vm(WEB)
    assert not _flows(world)
    card = _card("isolate_vm", "verification_failed")
    doc = _ask(world, "reset", service="bot", card=card)
    world["q"].poll()
    assert _receipt(world, doc)["state"] == "done"
    assert _flows(world), "web released"


def test_the_console_releases_resets_unblocks_and_promotes_what_the_watch_holds(world):
    c = world["conn"]
    c.block_suspicious_ip(ATTACKER, WEB)
    promote = _ask(world, "promote_block", ip=ATTACKER, scope="vm")
    world["q"].poll()
    assert _receipt(world, promote)["state"] == "done"
    assert approval.held_block(WEB, ATTACKER)["scoped"] is False
    unblock = _ask(world, "unblock_ip", ip=ATTACKER)
    world["q"].poll()
    assert _receipt(world, unblock)["state"] == "done" and _flows(world)
    c.isolate_vm(WEB)
    release = _ask(world, "release_isolation")
    world["q"].poll()
    assert _receipt(world, release)["state"] == "done" and _flows(world)
    c.isolate_vm(WEB)
    reset = _ask(world, "reset")
    world["q"].poll()
    assert _receipt(world, reset)["state"] == "done" and _flows(world)


def test_the_execution_holds_the_vms_lock(world, monkeypatch):
    """M: the request runs under _vm_lock — a write of the same VM by another writer waits."""
    import glorfindel.response.locks as locks
    held = []
    real = locks._vm_lock

    def spy(vm, timeout=None):
        held.append(vm)
        return real(vm, timeout)
    monkeypatch.setattr(locks, "_vm_lock", spy)
    card = _card()
    _ask(world, "isolate_vm", card=card)
    world["q"].poll()
    assert held and held[0] == "web"


# ── Each refusal, and nothing reaches Azure ─────────────────────────────────────────

def _untouched(world, doc, code):
    before = _rules(world)
    world["q"].poll()
    assert _code(world, doc) == code
    assert _rules(world) == before, "a refused request left a trace on Azure"


def test_an_unsigned_request_never_reaches_azure_and_makes_a_critical_card(world):
    card = _card()
    doc = _ask(world, "isolate_vm", card=card)
    doc.pop("sig")
    aq.deposit(doc, world["root"])
    _untouched(world, doc, "unsigned")
    (crit,) = _cards("queue_tampered")
    assert crit["severity"] == "critical" and crit["action"] == "none" and "unsigned" in crit["reason"]


def test_another_hands_key_a_field_changed_and_another_services_key_are_refused_critical(world):
    card = _card()
    stranger = _ask(world, "isolate_vm", card=card, signer=STRANGER)
    _untouched(world, stranger, "unknown_key")
    changed = _ask(world, "isolate_vm", card=card)
    changed["resource_id"] = vm_id("rg-app1", "other")
    aq.deposit(changed, world["root"])
    _untouched(world, changed, "bad_signature")
    other = _ask(world, "reset", service="bot", signer=CONSOLE, card=card)
    _untouched(world, other, "wrong_service")
    assert len(_cards("queue_tampered")) == 2, "one card per service and per hour"


def test_a_critical_card_at_most_once_per_service_and_per_hour(world):
    for _ in range(3):
        _untouched(world, _ask(world, "isolate_vm", signer=STRANGER), "unknown_key")
    (crit,) = _cards("queue_tampered")
    assert crit.get("occurrences", 1) == 1


def test_no_key_pinned_refuses_and_says_the_gesture(world):
    world["q"].pins = {"bot": BOT.public}
    doc = _ask(world, "isolate_vm", card=_card())
    _untouched(world, doc, "no_key_pinned")
    assert "EREGION_QUEUE_KEYS" in _receipt(world, doc)["reason"]
    assert not _cards("queue_tampered")


def test_the_bot_may_not_isolate(world):
    card = _card()
    doc = _ask(world, "isolate_vm", service="bot", card=card)
    _untouched(world, doc, "verb_not_allowed")
    assert _cards("queue_tampered")


def test_a_request_replayed_is_refused_critical(world):
    """Its receipt gone and the file written again (the same nonce): the register says it was
    seen — never run twice."""
    card = _card("snapshot", "low_confidence")
    doc = _ask(world, "release_isolation")
    world["q"].poll()
    aq.receipt_path("console", doc["id"], world["root"]).unlink()
    fresh = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                                   say=lambda s: None)
    fresh.poll()
    assert _code(world, doc) == "replayed"
    assert card and _cards("queue_tampered")


def test_an_expired_request_is_refused(world):
    doc = _ask(world, "isolate_vm", card=_card(), now=datetime.now(timezone.utc) - timedelta(seconds=200))
    _untouched(world, doc, "expired")


def test_a_name_that_is_not_its_nonce_is_never_read(world):
    doc = _ask(world, "isolate_vm", card=_card())
    path = aq.request_dir("console", world["root"]) / f"{doc['id']}.json"
    other = "f" * 32
    path.rename(path.with_name(f"{other}.json"))
    before = _rules(world)
    world["q"].poll()
    r = aq.read_receipt("console", other, root=world["root"])
    assert r["state"] == "refused" and r["code"] == "malformed" and _rules(world) == before
    (path.parent / "notanonce.json").write_text("{}")
    world["q"].poll()
    assert any("notanonce" in s for s in world["said"])


# ── The attachment: a forged card, a consumed proposal ───────────────────────────────

def test_a_forged_card_without_the_watchs_proposal_is_refused(world):
    escalations.sign_proposals(None)
    forged = _card()                      # written by another hand, with a proposal of its own
    escalations.sign_proposals(lambda: WATCH)
    forged["proposal"] = aq.sign_proposal(forged, STRANGER, datetime.now(timezone.utc))
    lines = [json.loads(x) for x in escalations._STORE.read_text().splitlines()]
    escalations._STORE.write_text("\n".join(json.dumps(forged if x["id"] == forged["id"] else x)
                                            for x in lines) + "\n")
    doc = _ask(world, "isolate_vm", card=forged)
    _untouched(world, doc, "proposal_mismatch")


def test_a_card_without_a_proposal_is_refused(world):
    escalations.sign_proposals(None)
    card = _card()
    doc = aq.new_request(CONSOLE, service="console", verb="isolate_vm", resource_id=WEB,
                         card=(card["id"], "sha256:" + "0" * 64))
    aq.deposit(doc, world["root"])
    _untouched(world, doc, "proposal_missing")


def test_an_isolation_without_its_card_is_refused(world):
    _untouched(world, _ask(world, "isolate_vm"), "proposal_missing")


def test_one_proposal_one_execution(world):
    card = _card("snapshot", "low_confidence")
    first = _ask(world, "isolate_vm", card=_card())
    world["q"].poll()
    assert _receipt(world, first)["state"] == "done"
    card = escalations.record(signal_id="watch-rule-9", resource_id=WEB, action="release_isolation",
                              escalation_type="release_hold", reason="held")
    card = next(e for e in escalations.all_escalations() if e["id"] == card)
    one = _ask(world, "release_isolation", card=card)
    world["q"].consumed.consume(aq.digest(card["proposal"]), card["id"], datetime.now(timezone.utc))
    _untouched(world, one, "proposal_consumed")


def test_a_card_settled_since_is_not_pending(world):
    card = _card()
    escalations.resolve(card["id"])
    _untouched(world, _ask(world, "isolate_vm", card=card), "card_not_pending")


def test_nothing_held_nothing_to_undo(world):
    for verb, ip in (("release_isolation", ""), ("reset", ""), ("unblock_ip", ATTACKER), ("promote_block", ATTACKER)):
        _untouched(world, _ask(world, verb, ip=ip), "nothing_to_undo")


def test_the_block_of_another_ip_is_never_the_one_acted_on(world):
    world["conn"].block_suspicious_ip(ATTACKER, WEB)
    _untouched(world, _ask(world, "unblock_ip", ip="198.51.100.7"), "nothing_to_undo")
    assert approval.held_block(WEB, ATTACKER)


# ── The guards of the console, replayed ──────────────────────────────────────────────

def test_the_age_of_an_approval_is_read_from_the_signed_proposal_never_from_last_seen(world, monkeypatch):
    """§7: the console can write last_seen; the watch reads the issued_at it signed."""
    monkeypatch.setenv("GLORFINDEL_APPROVAL_MAX_AGE_H", "0.01")      # 36 s
    card = _card()
    lines = [json.loads(x) for x in escalations._STORE.read_text().splitlines()]
    lines[-1]["last_seen"] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    escalations._STORE.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    later = datetime.now(timezone.utc) + timedelta(seconds=60)
    doc = _ask(world, "isolate_vm", card=card, now=later - timedelta(seconds=5))
    before = _rules(world)
    world["q"].poll(now=later)
    r = _receipt(world, doc)
    assert (r["state"], r["code"]) == ("refused", "guard") and "vieille" in r["reason"], r
    assert _rules(world) == before


def test_a_fresh_approval_passes_the_age(world, monkeypatch):
    monkeypatch.setenv("GLORFINDEL_APPROVAL_MAX_AGE_H", "0.01")
    doc = _ask(world, "isolate_vm", card=_card())
    world["q"].poll()
    assert _receipt(world, doc)["state"] == "done"


def test_the_one_click_approval_closed_is_closed_for_the_queue_too(world, monkeypatch):
    monkeypatch.setenv("GLORFINDEL_APPROVAL_MAX_AGE_H", "0")
    _untouched(world, _ask(world, "isolate_vm", card=_card()), "guard")


def test_a_restore_after_the_card_refuses_its_approval(world):
    from glorfindel import jobs
    card = _card()
    jobs._RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    (jobs._RECOVERY_DIR / "web.json").write_text(json.dumps(
        {"last_restore_at": (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()}))
    doc = _ask(world, "isolate_vm", card=card)
    _untouched(world, doc, "guard")
    assert "restore" in _receipt(world, doc)["reason"]


@pytest.mark.parametrize("record", ['["a list"]', '{"last_restore_at": "2026-11-05T09:00:00"}', "{not json",
                                    '{"other": 1}', '{"last_restore_at": 3}'])
def test_a_restore_record_there_but_unreadable_refuses_the_approval(world, record):
    """FS1b review: a restore record present but unreadable never reads as « no restore » — the
    approval is refused, for the console's direct click as for the watch's queue."""
    from eregion_console import api
    from glorfindel import jobs
    card = _card()
    jobs._RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    (jobs._RECOVERY_DIR / "web.json").write_text(record)
    assert "Restore illisible" in (api._approval_refusal(card, "web") or "")
    doc = _ask(world, "isolate_vm", card=card)
    _untouched(world, doc, "guard")
    assert "Restore illisible" in _receipt(world, doc)["reason"]


def test_a_restore_record_that_cannot_be_read_refuses_the_approval(world):
    from glorfindel import jobs
    (jobs._RECOVERY_DIR / "web.json").mkdir(parents=True)          # read_text: IsADirectoryError
    assert "Restore illisible" in (approval.approval_refusal(_card(), "web") or "")


def test_no_restore_record_is_no_restore(world):
    from glorfindel import jobs
    assert not (jobs._RECOVERY_DIR / "web.json").exists()
    assert approval.approval_refusal(_card(), "web") is None


@pytest.mark.parametrize("ip, scope", [("10.0.0.9", "vm"), ("168.63.129.16", "vm"), ("203.0.113.0/24", "vm"),
                                       ("*", "vm"), (ATTACKER, "everything"), (ATTACKER, "")])
def test_an_address_and_a_reach_are_judged_before_any_call(world, ip, scope):
    """§7: a proposal without an address lets the request name one — one host address, never of
    the never-block list, and a reach of vm or subnet."""
    card = _card("block_suspicious_ip", "low_confidence")
    _untouched(world, _ask(world, "block_ip", card=card, ip=ip, scope=scope), "guard")


def test_a_card_without_an_address_and_a_request_without_one_is_refused(world):
    card = _card("block_suspicious_ip", "low_confidence")
    _untouched(world, _ask(world, "block_ip", card=card, scope="vm"), "guard")


def test_a_vm_out_of_the_perimeter_is_refused(world):
    other = vm_id("rg-app1", "elsewhere")
    doc = _ask(world, "snapshot", resource_id=other)
    _untouched(world, doc, "guard")
    assert "périmètre" in _receipt(world, doc)["reason"]
    assert not approval.in_perimeter("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Storage/x/y")


def test_a_promotion_of_a_block_already_on_the_subnet_is_refused(world):
    world["conn"].block_suspicious_ip(ATTACKER, WEB, "subnet")
    _untouched(world, _ask(world, "promote_block", ip=ATTACKER, scope="vm"), "guard")


@pytest.mark.parametrize("environ, by, ok", [
    ({}, DISCORD, False),                                        # no copy of the list at the watch
    ({"DISCORD_ALLOWED_USERS": "222"}, DISCORD, False),          # another user
    (ALLOWED, {"via": "console-token", "user": "111", "name": ""}, False),
    (ALLOWED, DISCORD, True),
    ({"DISCORD_ALLOWED_ROLES": "999"}, DISCORD, True),           # a role: the bot's to read
])
def test_the_bots_human_is_read_against_the_watchs_own_copy(world, environ, by, ok):
    world["conn"].isolate_vm(WEB)
    world["q"].environ = environ
    card = _card("isolate_vm", "verification_failed")
    doc = _ask(world, "reset", service="bot", card=card, by=by)
    world["q"].poll()
    r = _receipt(world, doc)
    assert (r["state"] == "done") is ok, r
    if not ok:
        assert r["code"] == "guard"


def test_a_read_only_watch_refuses(world):
    world["q"].read_only = True
    _untouched(world, _ask(world, "isolate_vm", card=_card()), "read_only")


# ── The register ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("content", ["[" * 200_000, "{not json", '{"n": 3}', '{"' + "a" * 32 + '": "2026-11-05T09:00:00"}'])
def test_an_unreadable_register_refuses_and_never_raises(world, content):
    seen = aq.queue_dir() / "seen.json"
    seen.parent.mkdir(parents=True, exist_ok=True)
    seen.write_text(content)
    q = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                               say=lambda s: None)
    doc = _ask(world, "isolate_vm", card=_card())
    before = _rules(world)
    q.poll()
    assert _code(world, doc) == "seen_store_unavailable" and _rules(world) == before
    (card,) = _cards("queue_unavailable")
    assert card["severity"] != "critical"


def test_an_unreadable_register_of_proposals_refuses(world):
    consumed = aq.queue_dir() / "consumed.json"
    consumed.parent.mkdir(parents=True, exist_ok=True)
    consumed.write_text("[" * 200_000)
    q = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                               say=lambda s: None)
    doc = _ask(world, "isolate_vm", card=_card())
    q.poll()
    assert _code(world, doc) == "seen_store_unavailable"


def test_the_register_is_written_durably_before_it_answers(tmp_path, monkeypatch):
    """§7: the file fsync'd, then its directory — a nonce claimed survives a crash of the host."""
    synced = []
    real = os.fsync

    def spy(fd):
        import stat as _stat
        synced.append("dir" if _stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        return real(fd)
    monkeypatch.setattr(os, "fsync", spy)
    now = datetime.now(timezone.utc)
    assert aq.SeenFile(tmp_path / "seen.json").claim("a" * 32, now + timedelta(seconds=60), now)
    assert synced == ["file", "dir"]
    synced.clear()
    assert aq.ConsumedFile(tmp_path / "consumed.json").consume("sha256:" + "a" * 64, "c1", now)
    assert synced == ["file", "dir"]
    assert not aq.ConsumedFile(tmp_path / "consumed.json").consume("sha256:" + "a" * 64, "c1", now)


def test_the_claims_of_a_service_are_bounded_before_the_register(world):
    """§7: a service's key, compromised, never fills the register: past its rate, a request is
    refused before its nonce is claimed."""
    claimed = []

    class Counting(aq.MemorySeen):
        def claim(self, nonce, until, now):
            claimed.append(nonce)
            return super().claim(nonce, until, now)
    q = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                               say=lambda s: None, seen=Counting(), rate=aq.Rate(per_min=3))
    docs = [_ask(world, "unblock_ip", ip=ATTACKER) for _ in range(5)]
    q.poll()
    codes = sorted(_receipt(world, d)["code"] for d in docs)
    assert codes.count("rate_limited") == 2 and len(claimed) == 3


# ── A stop between the claim and the execution ──────────────────────────────────────

@pytest.mark.parametrize("state", ["received", "accepted"])
def test_a_stop_between_the_claim_and_the_end_is_never_run_again(world, state):
    card = _card()
    doc = _ask(world, "isolate_vm", card=card)
    q = world["q"]
    q._receipt("console", doc["id"], state, now=datetime.now(timezone.utc))      # then the watch stops
    q.seen.claim(doc["id"], datetime.now(timezone.utc) + timedelta(seconds=150), datetime.now(timezone.utc))
    before = _rules(world)
    fresh = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                                   say=lambda s: None)
    assert fresh.recover() == 1
    fresh.poll()
    r = _receipt(world, doc)
    assert (r["state"], r["code"]) == ("failed", "interrupted") and _rules(world) == before
    assert not _cards("queue_tampered"), "the watch's own stop is no forgery"


class Crash(BaseException):
    """A kill of the watch's process: no except Exception catches it."""


def test_a_kill_right_after_the_claim_is_said_interrupted_never_a_replay(world):
    """The nonce claimed, then the watch killed: its receipt says ``received`` — the next start says
    it failed, never judges it again (it would read ``replayed``, a critical card for its own stop)."""
    class Killed(aq.MemorySeen):
        def claim(self, nonce, until, now):
            super().claim(nonce, until, now)
            raise Crash()
    seen = Killed()
    q = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                               say=lambda s: None, seen=seen)
    doc = _ask(world, "isolate_vm", card=_card())
    with pytest.raises(Crash):
        q.judge("console", aq.request_dir("console", world["root"]) / f"{doc['id']}.json", datetime.now(timezone.utc))
    assert aq.read_receipt("console", doc["id"], root=world["root"])["state"] == "received"
    seen.claim = aq.MemorySeen.claim.__get__(seen)
    fresh = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                                   say=lambda s: None, seen=seen)
    before = _rules(world)
    assert fresh.recover() == 1
    fresh.poll()
    assert (_receipt(world, doc)["state"], _receipt(world, doc)["code"]) == ("failed", "interrupted")
    assert _rules(world) == before and not _cards("queue_tampered")


def test_a_kill_during_the_execution_leaves_it_accepted_then_interrupted(world, monkeypatch):
    def killed(rid):
        raise Crash()
    monkeypatch.setattr(world["conn"], "isolate_vm", killed)
    doc = _ask(world, "isolate_vm", card=_card())
    with pytest.raises(Crash):
        world["q"].poll()
    assert aq.read_receipt("console", doc["id"], root=world["root"])["state"] == "accepted"
    fresh = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, inline=True,
                                   say=lambda s: None)
    assert fresh.recover() == 1 and _receipt(world, doc)["code"] == "interrupted"


def test_a_proposal_that_failed_is_consumed_all_the_same(world, monkeypatch):
    """One proposal, one execution — a failed one too: the card still waits, a second request for
    it is refused, never run again."""
    monkeypatch.setattr(world["conn"], "isolate_vm", lambda rid: (_ for _ in ()).throw(RuntimeError("boom")))
    card = _card()
    first = _ask(world, "isolate_vm", card=card)
    world["q"].poll()
    assert _receipt(world, first)["state"] == "failed"
    assert card["id"] in {e["id"] for e in escalations.pending()}
    second = _ask(world, "isolate_vm", card=card)
    world["q"].poll()
    assert _code(world, second) == "proposal_consumed"


def test_the_bot_asks_through_its_card_only(world):
    world["conn"].isolate_vm(WEB)
    _untouched(world, _ask(world, "reset", service="bot"), "proposal_missing")


def test_the_queues_thread_never_dies_in_silence(world, monkeypatch):
    """A pass that raises is said, and the thread goes on to the next."""
    monkeypatch.setattr(world["q"], "poll", lambda now=None: (_ for _ in ()).throw(RuntimeError("disk gone")))
    world["q"].one_pass()
    assert any("passage en erreur" in s and "disk gone" in s for s in world["said"])


def test_a_crash_in_the_execution_says_failed_and_never_raises(world, monkeypatch):
    monkeypatch.setattr(world["conn"], "isolate_vm", lambda rid: (_ for _ in ()).throw(RuntimeError("boom")))
    doc = _ask(world, "isolate_vm", card=_card())
    world["q"].poll()
    r = _receipt(world, doc)
    assert r["state"] == "failed" and "boom" in r["reason"]


# ── The status ───────────────────────────────────────────────────────────────────────

def test_the_status_is_signed_and_says_the_posture_and_the_pins(world):
    world["q"].refused["unsigned"] += 1
    world["q"].status(datetime.now(timezone.utc), force=True)
    st = aq.read_status(root=world["root"], watch_public=WATCH.public)
    assert st["posture"] == "write" and st["pins"] == {"console": CONSOLE.fingerprint, "bot": BOT.fingerprint}
    assert st["refused"] == {"unsigned": 1}
    assert aq.read_status(root=world["root"], watch_public=STRANGER.public) is None


# ── The flag ─────────────────────────────────────────────────────────────────────────

def test_without_the_flag_the_watch_reads_no_queue(world, monkeypatch):
    monkeypatch.delenv(aq.FLAG_ENV, raising=False)
    _ask(world, "isolate_vm", card=_card())
    assert queue_watch.start(world["conn"], lambda: WATCH, root=world["root"]) is None
    for value in ("0", "true", "yes", " 1"):
        monkeypatch.setenv(aq.FLAG_ENV, value)
        assert not aq.enabled()
    assert not aq.receipts_dir(world["root"]).exists()


def test_the_watch_command_starts_its_queue_only_behind_the_flag(tmp_path, monkeypatch):
    from tests.unit.test_signal_origin import _run_watch
    started = []
    monkeypatch.setattr(queue_watch.QueueWatch, "start", lambda self: started.append(self))
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-00000000aaaa")
    (tmp_path / "off").mkdir()
    (tmp_path / "on").mkdir()
    _run_watch(tmp_path / "off", monkeypatch, [], 0)
    assert started == []
    monkeypatch.setenv(aq.FLAG_ENV, "1")
    _run_watch(tmp_path / "on", monkeypatch, [], 0)
    assert len(started) == 1 and started[0].signer.fingerprint == watch_key.load_or_create().fingerprint


def _console(world, monkeypatch):
    from eregion_console import api
    from .console_client import console
    monkeypatch.setattr(api, "_RUNS", world["root"])
    return api, console()


class _Picker:
    """The watch's queue picked up in a thread while a route waits for its receipt."""

    def __init__(self, q):
        self.q, self.stop = q, threading.Event()
        self.t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self.stop.is_set():
            self.q.poll()
            time.sleep(0.05)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.t.join(5)


def test_without_the_flag_the_console_calls_as_before_and_deposits_nothing(world, monkeypatch):
    pytest.importorskip("fastapi")
    api, client = _console(world, monkeypatch)
    monkeypatch.setattr(aq, "TAKE_S", 0.5)          # a mutant that deposits fails fast, never hangs
    calls = []
    monkeypatch.setattr(AzureConnector, "isolate_vm", lambda self, rid: calls.append(rid) or {"status": "isolated"})
    monkeypatch.setattr(api, "_verify_approved", lambda *a, **k: {"verified": True})
    card = _card()
    out = client.post(f"/api/action/approve/{card['id']}", json={}).json()
    assert out.get("ok") and calls == [WEB] and "via" not in out
    assert not aq.request_dir("console", world["root"]).exists()


def _followed(client, out: dict, timeout_s: float = 10.0) -> dict:
    """FS1c: the route answered at once with its request; the page follows its receipt."""
    assert out.get("pending") and out["via"] == "queue" and out["request"], out
    deadline = time.monotonic() + timeout_s
    while True:
        got = client.get(f"/api/queue/{out['request']}").json()
        if not got.get("pending") or time.monotonic() > deadline:
            return got
        time.sleep(0.05)


def test_with_the_flag_a_click_gives_a_request_the_watch_and_the_route_answers(world, monkeypatch):
    """§4.3, the end to end: an approval click → a request signed by the console's key → the watch
    → its receipt → the answer the page follows (FS1c). The console never calls Azure."""
    pytest.importorskip("fastapi")
    api, client = _console(world, monkeypatch)
    monkeypatch.setenv(aq.FLAG_ENV, "1")
    console_key = aq.load_service_key("console")
    world["q"].pins = {"console": console_key.public, "bot": BOT.public}
    monkeypatch.setattr(AzureConnector, "__init__", lambda *a, **k: pytest.fail("the console built a connector"))
    card = _card()
    with _Picker(world["q"]):
        out = _followed(client, client.post(f"/api/action/approve/{card['id']}", json={}).json())
    assert out.get("ok") and out["via"] == "queue", out
    assert out["verification"]["verified"] is True
    assert not _flows(world)
    r = _receipt(world, {"service": "console", "id": out["request"]})
    assert r["state"] == "done"
    assert not (aq.request_dir("console", world["root"]) / f"{out['request']}.json").exists(), "withdrawn"
    lines = (world["root"] / "console" / "manual_actions.jsonl").read_text().splitlines()
    assert json.loads(lines[-1])["outcome"]["via"] == "queue"


def test_with_the_flag_a_refusal_is_the_routes_error(world, monkeypatch):
    pytest.importorskip("fastapi")
    api, client = _console(world, monkeypatch)
    monkeypatch.setenv(aq.FLAG_ENV, "1")
    world["q"].pins = {"console": aq.load_service_key("console").public}
    world["q"].read_only = True
    card = _card()
    with _Picker(world["q"]):
        out = _followed(client, client.post(f"/api/action/approve/{card['id']}", json={}).json())
    assert out["refused"] == "read_only" and "error" in out and _flows(world)


def test_with_the_flag_and_no_watch_the_console_says_it(world, monkeypatch):
    pytest.importorskip("fastapi")
    from eregion_console import action_requests
    monkeypatch.setenv(aq.FLAG_ENV, "1")
    out = action_requests.ask("release_isolation", WEB, root=world["root"], by={"via": "console-token"},
                              take_s=0.3, poll_s=0.05)
    assert "did not take the request" in out["error"]
    assert not list(aq.request_dir("console", world["root"]).glob("*.json")), "withdrawn"


class _Thread:
    """A Discord thread as the bot writes in it: what it was told, in order."""

    def __init__(self):
        self.said: list[str] = []

    async def send(self, text):
        self.said.append(text)


def test_the_bot_deposits_its_revert_behind_the_flag(world, monkeypatch):
    """FS1c: deposited, then the receipt followed without a thread held — each state said."""
    pytest.importorskip("discord")
    import asyncio
    from glorfindel import bot
    monkeypatch.setenv(aq.FLAG_ENV, "1")
    world["q"].pins = {"console": CONSOLE.public, "bot": aq.load_service_key("bot").public}
    world["conn"].isolate_vm(WEB)
    card = _card("isolate_vm", "verification_failed")
    user = type("U", (), {"id": 111, "display_name": "an operator"})()
    thread = _Thread()
    with _Picker(world["q"]):
        code, said = asyncio.run(bot._queue_revert(card, user, thread, poll_s=0.02))
    assert code == 0 and "done" in said, said
    assert _flows(world)
    assert (world["root"] / "bot" / "queue").is_dir()
    assert "déposée" in thread.said[0], thread.said


def test_without_the_flag_the_bots_revert_runs_the_cli(world, monkeypatch):
    pytest.importorskip("discord")
    from glorfindel import bot
    ran = []
    monkeypatch.setattr(bot, "_run_cli", lambda args: ran.append(args) or (0, "ok"))
    monkeypatch.setattr(bot, "_deposit_reset", lambda *a: pytest.fail("deposited without the flag"))
    button = bot._ExecuteButton.__new__(bot._ExecuteButton)
    button.cli_args, button.esc = ["revert", WEB, "--yes"], {"id": "c1"}
    assert button._queued() is False
    assert button._run(None) == (0, "ok") and ran == [["revert", WEB, "--yes"]]


# ── Who mounts what ──────────────────────────────────────────────────────────────────

def test_only_the_watch_mounts_its_register_and_none_another_services_key():
    import yaml
    from pathlib import Path
    compose = yaml.safe_load((Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text())["services"]
    holders = {name: {v.split(":")[0] for v in s.get("volumes") or [] if "/.eregion/" in v}
               for name, s in compose.items()}
    assert {n for n, vs in holders.items() if "${HOME}/.eregion/watch-queue" in vs} == {"watch"}
    assert {n for n, vs in holders.items() if "${HOME}/.eregion/bot" in vs} == {"bot"}
    assert {n for n, vs in holders.items() if "${HOME}/.eregion/console" in vs} == {"war-room"}
    assert {n for n, vs in holders.items() if "${HOME}/.eregion/watch-key" in vs} == {"watch"}
    env = compose["watch"]["environment"]
    assert env["EREGION_QUEUE_KEYS"] == "${EREGION_QUEUE_KEYS:-}"
    assert env["DISCORD_ALLOWED_USERS"] == "${DISCORD_ALLOWED_USERS:-}"


def test_the_bots_and_the_registers_directories_are_made_before_compose_mounts_them():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    make = (root / "Makefile").read_text()
    deploy = (root / "infra" / "glorfindel-host" / "deploy.sh").read_text()
    for target in ("glorfindel-start:", "glorfindel-restart:", "glorfindel-dev:"):
        block = make.split(f"\n{target}", 1)[1].split("\n\n", 1)[0]
        assert "$(HOME)/.eregion/bot $(HOME)/.eregion/watch-queue" in block, target
    assert 'mkdir -p -m 700 "$HOME/.eregion/bot" "$HOME/.eregion/watch-queue"' in deploy
    start = deploy.split("\nstart() {", 1)[1].split("\n}", 1)[0]
    assert start.index("mkdir -p runs/glorfindel/queue") < start.index("docker compose --profile bot up")
    assert "mkdir -p runs/glorfindel/queue" in make.split("RUNS_DIRS =", 1)[1].split("\n#", 1)[0]
    team = make.split("\nteam-start:", 1)[1].split("\n\n", 1)[0]
    made = team.index('mkdir -p "$(TEAM_DIR)/runs/glorfindel/queue"')
    assert team.index('test ! -L "$$d"') < made < team.index("up -d watch war-room")
    assert '"$(TEAM_DIR)/.eregion/bot" "$(TEAM_DIR)/.eregion/watch-queue"' in team


# ── SEC-B (audit du 06/11) : la cible signée, la relève qui ne se fige pas, une watch par HOME,
#    les lignes illisibles du magasin ──────────────────────────────────────────────────────────

def test_what_runs_is_the_target_the_watch_signed_never_the_requests_spelling(world, monkeypatch):
    """V-08 (M5430): the guards, the VM's lock, the connector and the receipt take the proposal's
    target — even were the attachment to admit another spelling of it (here, let through)."""
    monkeypatch.setattr(aq, "proposal_refusal", lambda *a, **k: None)
    called = []
    real = world["conn"].isolate_vm
    monkeypatch.setattr(world["conn"], "isolate_vm", lambda rid: called.append(rid) or real(rid))
    card = _card()
    doc = _ask(world, "isolate_vm", card=card, resource_id=WEB.upper())
    world["q"].poll()
    r = _receipt(world, doc)
    assert r["state"] == "done" and r["resource_id"] == WEB, r
    assert called == [WEB], "the connector got the proposal's target, at the byte"


def test_a_request_named_in_another_case_than_its_proposal_is_refused(world):
    """V-08 (M5431): the request and the proposal compared at the byte — nothing reaches Azure."""
    card = _card()
    _untouched(world, _ask(world, "isolate_vm", card=card, resource_id=WEB.upper()), "proposal_mismatch")


@pytest.mark.parametrize("field", ["resource_id", "ip", "scope"])
def test_an_identifier_out_of_ascii_is_refused_and_said(world, field):
    """V-08 (M5432): a character out of ASCII — one whose case folds into ASCII, here — never compared,
    never acted on: its own code of the closed list."""
    kelvin = "K"
    assert kelvin.lower() == "k", "the fold the comparison at the byte closes"
    card = _card("block_suspicious_ip", "low_confidence", ip=ATTACKER)
    values = {"resource_id": WEB[:-1] + kelvin, "ip": ATTACKER + kelvin, "scope": "vm" + kelvin}
    kw = {"resource_id": WEB, "ip": ATTACKER, "scope": "vm", field: values[field]}
    doc = _ask(world, "block_ip", card=card, **kw)
    _untouched(world, doc, "not_ascii")
    assert field in _receipt(world, doc)["reason"]
    assert "not_ascii" in aq.REFUSALS and not aq.Refused("not_ascii").critical


class _Gate:
    """The watch's executions held at will: ``_run`` records each request's verb, the first one
    waits for ``gate``."""

    def __init__(self, q, monkeypatch):
        self.ran: list[str] = []
        self.entered = threading.Event()
        self.gate = threading.Event()
        self.done = threading.Semaphore(0)

        def run(service, req, card, ctx):
            self.ran.append(req.verb)
            if len(self.ran) == 1:
                self.entered.set()
                assert self.gate.wait(30), "the gate never opened"
            self.done.release()
            return {}
        monkeypatch.setattr(q, "_run", run)

    def wait_done(self, n: int) -> None:
        for _ in range(n):
            assert self.done.acquire(timeout=30), "an execution never ended"


@pytest.fixture
def threaded(world, monkeypatch):
    """The watch's queue with its workers — one at a time (IN_FLIGHT 1), never inline; web isolated
    and the attacker blocked on it, so that a release, an unblock and a promotion have their hold."""
    monkeypatch.setattr(queue_watch, "IN_FLIGHT", 1)
    monkeypatch.setattr(queue_watch, "STATUS_EVERY_S", 0)
    q = queue_watch.QueueWatch(WATCH, world["conn"], root=world["root"], pins=PINS, say=world["said"].append,
                               environ=ALLOWED)
    world["conn"].isolate_vm(WEB)
    world["conn"].block_suspicious_ip(ATTACKER, WEB)
    yield q
    q.stop()


def _poll_within(q, seconds: float = 10.0, now=None) -> None:
    """One poll, in a thread of its own: it must end within ``seconds`` — the relève never waits for
    an execution."""
    t = threading.Thread(target=q.poll, kwargs={"now": now}, daemon=True)
    t.start()
    t.join(seconds)
    assert not t.is_alive(), "the poll waited for an execution"


def _first_held(world, q, monkeypatch) -> "_Gate":
    g = _Gate(q, monkeypatch)
    _ask(world, "unblock_ip", ip=ATTACKER)
    _poll_within(q)
    assert g.entered.wait(10), "the first execution never started"
    return g


def test_judging_never_waits_for_an_execution(world, threaded, monkeypatch):
    """V-09 (M5433): every execution taken, a request deposited is judged, accepted and its receipt
    written at once — it waits for its turn in the wait list, never the poll."""
    g = _first_held(world, threaded, monkeypatch)
    second = _ask(world, "release_isolation")
    _poll_within(threaded)
    assert _receipt(world, second)["state"] == "accepted"
    assert threaded.busy() == {"running": 1, "waiting": 1}
    g.gate.set()
    g.wait_done(2)
    assert g.ran == ["unblock_ip", "release_isolation"]


def test_the_status_is_written_again_while_every_execution_is_taken(world, threaded, monkeypatch):
    """V-09 (M5434): the watch's signed status stays fresh while all its executions are taken — the
    console keeps its buttons; the status says what runs and what waits."""
    g = _first_held(world, threaded, monkeypatch)
    later = datetime.now(timezone.utc) + timedelta(seconds=30)
    _ask(world, "release_isolation", now=later)
    _poll_within(threaded, now=later)
    st = aq.read_status(root=world["root"], watch_public=WATCH.public)
    assert st["at"] == later.astimezone(timezone.utc).isoformat(timespec="milliseconds"), st
    assert st["executions"] == {"running": 1, "waiting": 1, "slots": 1, "backlog": queue_watch.BACKLOG}
    g.gate.set()
    g.wait_done(2)


def test_a_containment_runs_before_a_lift_that_waited_longer(world, threaded, monkeypatch):
    """V-09 (M5435): the wait list is in priority — a promotion of a block (it contains) runs before
    a release (it lifts) deposited before it."""
    g = _first_held(world, threaded, monkeypatch)
    _ask(world, "release_isolation")
    _poll_within(threaded)
    _ask(world, "promote_block", ip=ATTACKER, scope="vm")
    _poll_within(threaded)
    g.gate.set()
    g.wait_done(3)
    assert g.ran == ["unblock_ip", "promote_block", "release_isolation"]


def test_a_request_whose_life_ends_while_it_waits_is_refused_and_said(world, threaded, monkeypatch):
    """V-09 (M5436): its turn come after its end of life, it is refused (``no_slot``), its receipt says
    it — never run late, never left to expire in silence. Its proposal is not consumed: asked again,
    it may run."""
    g = _first_held(world, threaded, monkeypatch)
    card = _card()
    late = _ask(world, "isolate_vm", card=card)
    _poll_within(threaded)
    assert _receipt(world, late)["state"] == "accepted"
    threaded.clock = lambda: datetime.now(timezone.utc) + timedelta(seconds=aq.MAX_LIFETIME_S + 5)
    g.gate.set()
    g.wait_done(1)
    threaded._backlog.join()
    assert _code(world, late) == "no_slot" and g.ran == ["unblock_ip"]
    assert aq.digest(card["proposal"]) not in threaded.consumed.digests()


class _CountedUnderLock(collections.Counter):
    """The refusals counted — and every count that was not made under the watch's lock."""

    def __init__(self, q):
        super().__init__()
        self.q, self.bare = q, []

    def __setitem__(self, key, value):
        if not self.q._lock.locked():
            self.bare.append(key)
        super().__setitem__(key, value)


def test_the_refusals_are_counted_under_the_lock_by_the_releve_and_the_workers(world, threaded, monkeypatch):
    """SEC-B: the relève and the workers both refuse (``no_slot`` is a worker's) — every count is made
    under the watch's lock, never lost from the signed status."""
    threaded.refused = counted = _CountedUnderLock(threaded)
    g = _first_held(world, threaded, monkeypatch)
    late = _ask(world, "isolate_vm", card=_card())
    forged = _ask(world, "release_isolation", signer=BOT)          # the relève refuses it
    _poll_within(threaded)
    assert _receipt(world, forged)["state"] == "refused"
    threaded.clock = lambda: datetime.now(timezone.utc) + timedelta(seconds=aq.MAX_LIFETIME_S + 5)
    g.gate.set()
    g.wait_done(1)
    threaded._backlog.join()
    assert _code(world, late) == "no_slot"
    assert counted["no_slot"] == 1 and sum(counted.values()) == 2, counted
    assert counted.bare == [], counted.bare
    st = threaded.status(datetime.now(timezone.utc), force=True)
    assert st["refused"] == {"no_slot": 1, **{k: 1 for k in counted if k != "no_slot"}}, st["refused"]


def test_a_full_wait_list_refuses_at_once(world, threaded, monkeypatch):
    """V-09 (M5444): the wait list is bounded — full, a request is refused at once (``busy``), said."""
    monkeypatch.setattr(queue_watch, "BACKLOG", 1)
    g = _first_held(world, threaded, monkeypatch)
    waits = _ask(world, "release_isolation")
    _poll_within(threaded)
    full = _ask(world, "promote_block", ip=ATTACKER, scope="vm")
    _poll_within(threaded)
    assert _receipt(world, waits)["state"] == "accepted"
    assert _code(world, full) == "busy"
    g.gate.set()
    g.wait_done(2)


def test_a_second_watch_on_the_same_home_is_refused(world, monkeypatch):
    """V-10 (M5439): with the queue, one watch per HOME — another holds it (here, another opening of
    the lock: flock tells them apart as two processes): the start raises, says why, picks nothing up."""
    import fcntl
    monkeypatch.setenv(aq.FLAG_ENV, "1")
    monkeypatch.setattr(queue_watch.QueueWatch, "start", lambda self: None)
    lock = aq.queue_dir() / queue_watch.WATCH_LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as other:
        fcntl.flock(other, fcntl.LOCK_EX)
        with pytest.raises(queue_watch.SecondWatch, match="une autre watch"):
            queue_watch.start(world["conn"], lambda: WATCH, root=world["root"])
    q = queue_watch.start(world["conn"], lambda: WATCH, root=world["root"])
    assert q is not None and lock.read_text() == str(os.getpid())
    os.close(q._hold)


def test_the_watch_command_refuses_to_run_beside_another(tmp_path, monkeypatch):
    """V-10 (M5445): the watch command, the queue on and another watch holding it, says it and stops
    with an error — before its first heartbeat."""
    from tests.unit.test_signal_origin import _run_watch
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-00000000aaaa")
    monkeypatch.setenv(aq.FLAG_ENV, "1")

    def refused(*a, **k):
        raise queue_watch.SecondWatch("une autre watch relève déjà la file d'actions de ce HOME")
    monkeypatch.setattr(queue_watch, "start", refused)
    _, _, output = _run_watch(tmp_path, monkeypatch, [], 0, exit_code=1)
    assert "Watch refusée" in output and "une autre watch" in output


# V-12: a line of the store that is not a card.
_NOT_CARDS = ["{not json", '["a list"]', "42", '"text"', "null", "\udcff\udcfe",
              # an object a byte that is not UTF-8 spoils — raw (read in surrogateescape), and escaped
              # in its JSON: a card no reader could write out again (/api/state, a log)
              '{"id": "esc-raw", "status": "pending", "resource_id": "vm-raw", "reason": "\udcff"}',
              '{"id": "esc-esc", "status": "pending", "resource_id": "vm-esc", "reason": "\\udcff"}']


def _spoil(*lines: str) -> list[str]:
    """The store with lines that are not cards, written before its own: as bytes."""
    store = escalations._STORE
    kept = store.read_bytes().decode("utf-8", "surrogateescape").splitlines() if store.exists() else []
    store.write_bytes(("\n".join(list(lines) + kept) + "\n").encode("utf-8", "surrogateescape"))
    return list(lines)


def _still_there(lines: list[str]) -> None:
    text = escalations._STORE.read_bytes().decode("utf-8", "surrogateescape").splitlines()
    for line in lines:
        assert line in text, f"{line!r} lost in a rewrite"


def test_pending_passes_over_a_line_that_is_not_a_card_and_says_it_once(world, caplog):
    """V-12 (M5440): ``pending`` reads the cards around it; the line said once, by its length and its
    digest — never its text — however often the store is read."""
    card = _card()
    bad = _spoil(*_NOT_CARDS)
    with caplog.at_level("WARNING", logger="glorfindel.escalations"):
        assert [e["id"] for e in escalations.pending()] == [card["id"]]
        assert [e["id"] for e in escalations.pending()] == [card["id"]]
        assert [e["id"] for e in escalations.all_escalations()] == [card["id"]]
    said = [r.getMessage() for r in caplog.records if "pas une carte" in r.getMessage()]
    assert len(said) == len(_NOT_CARDS), said
    assert not any("not json" in s or "a list" in s for s in said)
    _still_there(bad)


def test_resolve_closes_its_card_and_keeps_the_line_that_is_not_one(world):
    """V-12 (M5441): ``resolve`` never fails on it, never loses it in its rewrite."""
    card = _card()
    bad = _spoil(*_NOT_CARDS)
    escalations.resolve(card["id"], note="done")
    assert not escalations.pending()
    _still_there(bad)


def test_resolve_by_resource_closes_its_cards_and_keeps_the_line_that_is_not_one(world):
    """V-12 (M5442): ``resolve_by_resource`` never fails on it, never loses it."""
    _card()
    bad = _spoil(*_NOT_CARDS)
    assert escalations.resolve_by_resource(WEB.upper(), "isolate_vm") == 1
    assert not escalations.pending()
    _still_there(bad)


@pytest.mark.parametrize("read", ["refresh", "record", "set_verdict", "card_of", "resolve_by_proposal",
                                  "note_identity_check"])
def test_every_reader_of_the_store_passes_over_a_line_that_is_not_a_card(world, read):
    """Every read of the store tolerates it, and every rewrite keeps it."""
    card = _card()
    bad = _spoil(*_NOT_CARDS)
    calls = {
        "refresh": lambda: escalations.refresh(card["id"], "said again"),
        "record": lambda: escalations.record(signal_id="watch-rule-1", resource_id=WEB, action="isolate_vm",
                                             escalation_type="mode_hold", reason="again"),
        "set_verdict": lambda: escalations.set_verdict(card["id"], "right"),
        "card_of": lambda: escalations.card_of(card["id"]),
        "resolve_by_proposal": lambda: escalations.resolve_by_proposal("p-1"),
        "note_identity_check": lambda: escalations.note_identity_check(card["id"], {"requested_at": ""}),
    }
    calls[read]()
    _still_there(bad)
    assert [e["id"] for e in escalations.all_escalations()] == [card["id"]]


def test_an_action_done_says_done_whatever_the_store_holds(world):
    """V-12: lines that are not cards in the store — the action done, its receipt says ``done``, its
    card settled, the lines kept."""
    card = _card()
    bad = _spoil(*_NOT_CARDS)
    doc = _ask(world, "isolate_vm", card=card)
    world["q"].poll()
    assert _receipt(world, doc)["state"] == "done"
    assert card["id"] not in {e["id"] for e in escalations.pending()}
    _still_there(bad)


def test_a_card_that_cannot_be_settled_never_makes_an_action_done_say_failed(world, monkeypatch):
    """V-12 (M5443): the store that cannot be rewritten (a full disk) — the action done says ``done``,
    and the watch says the card stays open."""
    def full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(escalations, "resolve", full)
    doc = _ask(world, "isolate_vm", card=_card())
    world["q"].poll()
    r = _receipt(world, doc)
    assert r["state"] == "done" and r["verification"]["verified"] is True, r
    assert not _flows(world)
    assert any("non réglée" in s and "reste ouverte" in s for s in world["said"])


def test_the_consoles_state_stands_with_a_line_that_is_not_a_card(world, monkeypatch):
    """V-12: ``/api/state`` reads the pending cards — it answers, the line passed over."""
    pytest.importorskip("fastapi")
    api, client = _console(world, monkeypatch)
    card = _card()
    _spoil(*_NOT_CARDS)
    got = client.get("/api/state")
    assert got.status_code == 200, got.text[:300]
    assert card["id"] in got.text
    assert "esc-raw" not in got.text and "esc-esc" not in got.text    # the spoiled objects passed over
