"""FS1a (#551, docs/design/file-actions-signee.md §2.4): the proposal the watch signs on each card
that holds an action — with its own key (SEC19), under eregion.action-queue/1 — and its check
(§2.8, step 10). Nobody reads it yet to act (FS1b): the console and the bot keep their direct call.

The keys come from fixed seeds, or are drawn in tmp (tests/unit/conftest.py): never a real key. A
throwaway HOME, the store in tmp, no Azure, no network, no model. Mutants M3878–M3879, M3945–M3954
(scripts/mutants/FS1a.py) are measured here.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import eregion_core.action_queue as aq
import eregion_core.watch_key as watch_key
from glorfindel import escalations

WATCH = watch_key.Signer(bytes(range(32)))
STRANGER = watch_key.Signer(bytes(range(120, 152)))
CONSOLE = watch_key.Signer(bytes(range(40, 72)))
BOT = watch_key.Signer(bytes(range(80, 112)))
VM = "/subscriptions/00000000-0000-0000-0000-00000000aaaa/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test"
IP = "203.0.113.9"


@pytest.fixture
def watch():
    """The watch's process: its key signs the proposals of the cards it writes."""
    escalations.sign_proposals(lambda: WATCH)
    return WATCH


def _card(cid: str) -> dict:
    return next(e for e in escalations.all_escalations() if e["id"] == cid)


def _record(action="isolate_vm", etype="mode_hold", ip="", **kw) -> str:
    return escalations.record(signal_id="watch-rule-1", resource_id=VM, action=action,
                              escalation_type=etype, reason="held", action_params={"ip": ip} if ip else None,
                              **kw)


def _request(card: dict, verb: str, signer=CONSOLE, service="console", ip="", resource_id=VM) -> aq.Request:
    doc = aq.new_request(signer, service=service, verb=verb, resource_id=resource_id, ip=ip,
                         card=(card["id"], aq.digest(card["proposal"])) if card.get("proposal") else (card["id"], "sha256:" + "0" * 64))
    return aq.verify_request(json.dumps(doc).encode(), service=service,
                             pins={"console": CONSOLE.public, "bot": BOT.public},
                             now=datetime.now(timezone.utc), seen=aq.MemorySeen(), rate=aq.Rate())


def _refusal(card, request, **kw) -> str:
    with pytest.raises(aq.Refused) as e:
        aq.proposal_refusal(card, request, watch_public=WATCH.public, **kw)
    return e.value.code


# ── The watch signs what it proposes ─────────────────────────────────────────────────

def test_a_card_the_watch_writes_that_holds_an_action_carries_its_signed_proposal(watch):
    card = _card(_record())
    p = card["proposal"]
    assert tuple(sorted(p)) == tuple(sorted(aq.PROPOSAL_FIELDS))
    assert (p["kind"], p["card"], p["action"], p["resource_id"], p["escalation_type"], p["ip"], p["port"]) == \
        ("proposal", card["id"], "isolate_vm", VM, "mode_hold", "", None)
    assert p["key"] == WATCH.fingerprint
    assert aq.watch_refusal(p, "proposal", WATCH.public) == ""
    assert not watch_key.holds(WATCH.public, watch_key.DOMAIN_BEAT, p)     # never read as a heartbeat
    assert aq.proposal_refusal(card, _request(card, "isolate_vm"), watch_public=WATCH.public) is None


def test_the_proposal_binds_the_address_and_the_port(watch):
    cid = escalations.record(signal_id="watch-rule-2", resource_id=VM, action="block_suspicious_ip",
                             escalation_type="low_confidence", reason="held",
                             action_params={"ip": IP, "port": 22})
    card = _card(cid)
    assert (card["proposal"]["ip"], card["proposal"]["port"]) == (IP, 22)
    assert aq.proposal_refusal(card, _request(card, "block_ip", ip=IP), watch_public=WATCH.public) is None
    assert aq.proposal_refusal(card, _request(card, "block_ip"), watch_public=WATCH.public) is None
    assert _refusal(card, _request(card, "block_ip", ip="198.51.100.1")) == "proposal_mismatch"
    # The port the console's approval takes from the card (threat_port): changed on the card after
    # the proposal, the request no longer runs (M3950).
    req = _request(card, "block_ip", ip=IP)
    for port in (3389, None, "22"):
        changed = {**card, "action_params": {"ip": IP, "port": port}}
        assert _refusal(changed, req) == "proposal_mismatch", port
    assert aq.proposal_refusal({**card, "action_params": {"ip": IP, "port": 22}}, req,
                               watch_public=WATCH.public) is None


def test_a_proposal_without_a_port_refuses_a_card_that_gained_one(watch):
    card = _card(_record(action="block_suspicious_ip", etype="mode_hold", ip=IP))
    assert card["proposal"]["port"] is None
    req = _request(card, "block_ip", ip=IP)
    assert _refusal({**card, "action_params": {"ip": IP, "port": 22}}, req) == "proposal_mismatch"


def test_a_request_bound_to_another_card_finds_no_card_waiting(watch):
    """M3954: the card the watch reads is the one the request names, by its id."""
    one, other = _card(_record()), _card(_record(action="snapshot"))
    assert _refusal(other, _request(one, "isolate_vm")) == "card_not_pending"


def test_a_card_verification_failed_proposes_its_reset_alone(watch):
    card = _card(_record(etype="verification_failed"))
    assert aq.proposed_verbs(card["proposal"]) == {"reset"}
    assert aq.proposal_refusal(card, _request(card, "reset", signer=BOT, service="bot"),
                               watch_public=WATCH.public) is None
    assert _refusal(card, _request(card, "isolate_vm")) == "proposal_mismatch"


@pytest.mark.parametrize("action,etype", [
    ("isolate_vm", "control_plane_change"), ("isolate_vm", "identity_change"),
    ("isolate_vm", "unattributed_signal"), ("restore_from_backup", "destructive_action"),
    ("investigate_detection_gap", "detection_blocked"), ("snapshot", "posture_gap"),
    ("delete_resource", "mode_hold"),
])
def test_a_card_that_holds_no_action_a_human_may_run_carries_none(watch, action, etype):
    assert "proposal" not in _card(_record(action=action, etype=etype))


def test_a_card_the_console_the_bot_or_the_cli_writes_carries_none():
    """No signer installed: the process is not the watch's."""
    assert "proposal" not in _card(_record())


def test_a_signer_that_fails_never_stops_the_card(watch):
    escalations.sign_proposals(lambda: None)                 # the key unavailable
    assert "proposal" not in _card(_record())

    def broken():
        raise RuntimeError("cryptography gone")
    escalations.sign_proposals(broken)
    assert "proposal" not in _card(_record(action="snapshot"))


def test_a_card_seen_again_keeps_its_proposal_until_it_is_older_than_an_age(watch, monkeypatch):
    """FS1b (§7): re-signed at each refresh, the proposal changed its digest under a request just
    named for it (``proposal_mismatch``). Kept while it stands and is younger than
    RESIGN_AFTER_S; past it, signed again — the age of an approval, read from its issued_at,
    stays right."""
    cid = _record()
    first = _card(cid)["proposal"]
    assert _record() == cid                                  # the same card, seen again
    assert _card(cid)["proposal"] == first
    assert escalations.refresh(cid, "said again")
    assert _card(cid)["proposal"] == first
    monkeypatch.setattr(escalations, "RESIGN_AFTER_S", 0)
    assert _record() == cid
    again = _card(cid)["proposal"]
    assert again["seq"] > first["seq"] and aq.digest(again) != aq.digest(first)
    assert aq.watch_refusal(again, "proposal", WATCH.public) == ""
    assert escalations.refresh(cid, "said again")
    assert _card(cid)["proposal"]["seq"] > again["seq"]


def test_a_card_changed_by_a_refresh_is_never_signed_from_what_it_says_now(watch, monkeypatch):
    """SEC-B (audit du 06/11, V-06; M5426): a refresh signs again from what the watch signed, never from
    the card as the store gives it — its port changed there, the proposal keeps the watch's, and the
    card no longer matches it: nothing runs. Past the age too."""
    cid = escalations.record(signal_id="watch-rule-2", resource_id=VM, action="block_suspicious_ip",
                             escalation_type="low_confidence", reason="held", action_params={"ip": IP, "port": 22})
    first = _card(cid)["proposal"]
    assert escalations.refresh(cid, "said again", action_params={"ip": IP, "port": 2222})
    assert _card(cid)["proposal"] == first
    monkeypatch.setattr(escalations, "RESIGN_AFTER_S", 0)
    assert escalations.refresh(cid, "said again", action_params={"ip": IP, "port": 2222},
                               resource_id=VM + "-other")
    again = _card(cid)["proposal"]
    assert again["seq"] > first["seq"], "signed again past its age"
    assert (again["port"], again["resource_id"], again["ip"]) == (22, VM, IP), "the watch's own fields"
    assert _refusal(_card(cid), _request(_card(cid), "block_ip", ip=IP)) == "proposal_mismatch"


def test_a_proposal_of_another_key_on_a_card_seen_again_is_signed_again(watch):
    cid = _record()
    store = escalations._STORE
    lines = [json.loads(x) for x in store.read_text().splitlines()]
    lines[0]["proposal"] = aq.sign_proposal(lines[0], STRANGER, datetime.now(timezone.utc))
    store.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    _record()
    assert _card(cid)["proposal"]["key"] == WATCH.fingerprint


def test_a_card_written_before_fs1_gets_its_proposal_when_the_watch_sees_it_again():
    cid = _record()
    assert "proposal" not in _card(cid)
    escalations.sign_proposals(lambda: WATCH)
    _record()
    assert aq.watch_refusal(_card(cid)["proposal"], "proposal", WATCH.public) == ""


def test_the_watch_command_signs_its_proposals_with_its_own_key(tmp_path, monkeypatch):
    """The watch's process installs its signer: a card it writes after carries the proposal its
    key signed — the key drawn at its first start (SEC19)."""
    from tests.unit.test_signal_origin import _run_watch
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-00000000aaaa")
    _run_watch(tmp_path, monkeypatch, [], 0)
    card = _card(_record())
    key = watch_key.load_or_create()
    assert card["proposal"]["key"] == key.fingerprint
    assert aq.watch_refusal(card["proposal"], "proposal", key.public) == ""


# ── What the check refuses ───────────────────────────────────────────────────────────

def test_a_forged_card_without_a_proposal_is_refused():
    card = _card(_record())                                   # written with no proposal
    assert _refusal(card, _request(card, "isolate_vm")) == "proposal_missing"


def test_a_proposal_signed_by_another_key_is_refused(watch):
    """M3878: a proposal forged with another key, the request naming it."""
    card = _card(_record())
    card["proposal"] = aq.sign_proposal(card, STRANGER, datetime.now(timezone.utc))
    assert _refusal(card, _request(card, "isolate_vm")) == "proposal_mismatch"


def test_a_proposal_relabelled_with_the_watch_s_fingerprint_does_not_hold(watch):
    card = _card(_record())
    forged = {k: v for k, v in card["proposal"].items() if k != "sig"}
    forged["action"] = "isolate_vm"
    forged["sig"] = STRANGER.sign(aq.DOMAIN_QUEUE, forged)
    card["proposal"] = forged
    assert _refusal(card, _request(card, "isolate_vm")) == "proposal_mismatch"


def test_a_request_naming_another_proposal_is_refused(watch):
    """M3879: the digest the request names is the card's proposal's, or nothing runs."""
    card = _card(_record())
    req = _request(card, "isolate_vm")
    stale = aq.Request(**{**req.__dict__, "proposal": "sha256:" + "ab" * 32})
    assert _refusal(card, stale) == "proposal_mismatch"
    cid = card["id"]
    _record()                                                 # seen again, young: kept (FS1b)
    assert aq.proposal_refusal(_card(cid), req, watch_public=WATCH.public) is None
    escalations.RESIGN_AFTER_S, kept = 0, escalations.RESIGN_AFTER_S
    try:
        _record()                                             # past the age: a new proposal
    finally:
        escalations.RESIGN_AFTER_S = kept
    assert _refusal(_card(cid), req) == "proposal_mismatch"


@pytest.mark.parametrize("field,value", [
    ("action", "snapshot"), ("resource_id", VM + "-other"), ("escalation_type", "release_hold"),
    ("action_params", {"ip": IP}),
])
def test_a_card_changed_since_its_proposal_is_refused(watch, field, value):
    card = _card(_record())
    req = _request(card, "isolate_vm")
    card[field] = value
    assert _refusal(card, req) == "proposal_mismatch"


def test_a_proposal_copied_onto_another_card_is_refused(watch):
    one, other = _card(_record()), _card(_record(action="snapshot"))
    other["proposal"] = one["proposal"]
    other["action"] = one["action"]
    assert _refusal(other, _request(other, "isolate_vm")) == "proposal_mismatch"


def test_a_proposal_tampered_after_its_signature_is_refused(watch):
    card = _card(_record())
    card["proposal"]["resource_id"] = VM + "-other"
    card["resource_id"] = VM + "-other"
    assert _refusal(card, _request(card, "isolate_vm", resource_id=VM + "-other")) == "proposal_mismatch"


def test_a_proposal_with_a_field_more_is_refused(watch):
    card = _card(_record())
    card["proposal"] = {**card["proposal"], "extra": 1}
    assert _refusal(card, _request(card, "isolate_vm")) == "proposal_mismatch"


def test_a_request_for_another_verb_or_target_than_the_card_is_refused(watch):
    card = _card(_record())
    assert _refusal(card, _request(card, "snapshot")) == "proposal_mismatch"
    assert _refusal(card, _request(card, "isolate_vm", resource_id=VM + "-other")) == "proposal_mismatch"
    # SEC-B (audit du 06/11, V-08; M5430): the request and the proposal compared at the byte — the
    # console and the bot copy the proposal's target; another case is another request.
    assert _refusal(card, _request(card, "isolate_vm", resource_id=VM.upper())) == "proposal_mismatch"


def test_a_card_that_no_longer_waits_is_refused(watch):
    card = _card(_record())
    req = _request(card, "isolate_vm")
    escalations.resolve(card["id"])
    assert _refusal(_card(card["id"]), req) == "card_not_pending"
    assert _refusal(None, req) == "card_not_pending"


def test_a_request_without_a_card_has_no_proposal_to_check(watch):
    card = _card(_record())
    req = _request(card, "isolate_vm")
    bare = aq.Request(**{**req.__dict__, "card_id": None, "proposal": None})
    assert _refusal(card, bare) == "proposal_missing"


def test_a_proposal_runs_once(watch):
    card = _card(_record())
    req = _request(card, "isolate_vm")
    assert _refusal(card, req, consumed={req.proposal}) == "proposal_consumed"


def test_a_proposal_s_signature_never_reads_as_a_request(watch):
    """The watch's proposal, offered as a request of the console whose key is the watch's own."""
    p = _card(_record())["proposal"]
    with pytest.raises(aq.Refused) as e:
        aq.verify_request(json.dumps(p).encode(), service="console", pins={"console": WATCH.public},
                          now=datetime.now(timezone.utc), seen=aq.MemorySeen(), rate=aq.Rate())
    assert e.value.code == "malformed"
    as_request = {**aq.new_request(WATCH, service="console", verb="isolate_vm", resource_id=VM)}
    as_request["sig"] = WATCH.sign(aq.DOMAIN_QUEUE, {k: v for k, v in as_request.items() if k != "sig"})
    with pytest.raises(aq.Refused) as e:
        aq.verify_request(json.dumps(as_request).encode(), service="console", pins={"console": WATCH.public},
                          now=datetime.now(timezone.utc), seen=aq.MemorySeen(), rate=aq.Rate())
    assert e.value.code == "bad_signature"


# ── One list of the cards one may approve ────────────────────────────────────────────

def test_the_cards_proposed_are_those_the_console_approves_in_one_click():
    from eregion_console import api
    from glorfindel import bot
    assert aq.APPROVABLE_TYPES == api._APPROVABLE_TYPES
    for etype in api._ANCHORED_TYPES | bot._ANCHORED_TYPES:
        for action in aq.VERB_OF_ACTION:
            assert not aq.proposable({"escalation_type": etype, "action": action})
    assert set(aq.VERB_OF_ACTION.values()) <= set(aq.VERBS)


def test_the_decision_never_reads_the_proposal():
    """FS1a, FS1b: the proposal is read to act by the watch's queue only (glorfindel/queue_watch.py)
    — behind EREGION_ACTION_QUEUE=1, which tests/unit/test_action_queue_watch.py holds; the
    decision never reads it."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    text = (root / "glorfindel/agent.py").read_text()
    assert "action_queue" not in text and '"proposal"' not in text


def test_an_old_proposal_signed_long_ago_still_says_when(watch):
    """The proposal carries when the watch proposed it: FS1b reads the card's age from it, never
    from what the console can write beside it."""
    card = _card(_record())
    issued = datetime.fromisoformat(card["proposal"]["issued_at"])
    assert abs(issued - datetime.now(timezone.utc)) < timedelta(seconds=30)


# ── SEC-B (audit du 06/11, V-06) : re-signée depuis l'état de la watch seulement ────────────────

def _rewrite(cid: str, change) -> None:
    """Another writer of the store (the console, the bot, the CLI) rewrites the card ``cid``."""
    store = escalations._STORE
    lines = [json.loads(x) for x in store.read_text().splitlines()]
    for x in lines:
        if x["id"] == cid:
            change(x)
    store.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def _forge(**card) -> str:
    """A card another hand writes — no proposal of the watch's, whatever it holds."""
    escalations.sign_proposals(None)
    try:
        return escalations.record(**{"signal_id": "watch-rule-1", "resource_id": VM, "action": "isolate_vm",
                                     "escalation_type": "mode_hold", "reason": "forged", **card})
    finally:
        escalations.sign_proposals(lambda: WATCH)


def test_a_card_another_hand_wrote_is_never_signed_by_a_refresh(watch, monkeypatch):
    """M5426, M5428: the reassertion refreshes a card it finds by its signal — one another writer of
    the store made, that holds an action: the watch signs nothing on it, past any age."""
    monkeypatch.setattr(escalations, "RESIGN_AFTER_S", 0)
    cid = _forge(resource_id=VM + "-chosen")
    assert escalations.refresh(cid, "seen again")
    assert "proposal" not in _card(cid)


def test_a_card_whose_proposal_was_replaced_is_never_signed_again(watch, monkeypatch):
    """M5428: the watch signed this card; another writer replaced its proposal since — a refresh
    signs nothing again, even from what the watch remembers: the card no longer carries its own."""
    cid = _record()
    _rewrite(cid, lambda x: x.update(proposal=aq.sign_proposal(x, STRANGER, datetime.now(timezone.utc))))
    monkeypatch.setattr(escalations, "RESIGN_AFTER_S", 0)
    assert escalations.refresh(cid, "seen again")
    assert _card(cid)["proposal"]["key"] == STRANGER.fingerprint
    _rewrite(cid, lambda x: x.pop("proposal"))
    assert escalations.refresh(cid, "seen again")
    assert "proposal" not in _card(cid)


def test_a_refresh_signs_from_what_the_watch_signed_never_from_the_card(watch, monkeypatch):
    """M5426: the card's target rewritten in the store under its proposal — past the age, the watch
    signs again its own target, never the one the card now says."""
    cid = _record()
    first = _card(cid)["proposal"]
    _rewrite(cid, lambda x: x.update(resource_id=VM + "-chosen", action_params={"ip": IP, "port": 22}))
    monkeypatch.setattr(escalations, "RESIGN_AFTER_S", 0)
    assert escalations.refresh(cid, "seen again")
    again = _card(cid)["proposal"]
    assert again["seq"] > first["seq"]
    assert (again["resource_id"], again["ip"], again["port"], again["card"]) == (VM, "", None, cid)


def test_the_watch_remembers_its_proposals_by_the_card_it_drew_never_by_the_signal(watch, monkeypatch):
    """M5427: a card of the same signal (predictable: the reassertion's ids are), its proposal copied
    from the watch's own card — a refresh signs nothing on it: the watch's memory is by the card's id,
    which it drew."""
    cid = _record()
    own = _card(cid)["proposal"]
    other = _forge(resource_id=VM + "-other")             # its signal, the watch's card's
    assert other != cid and _card(other)["signal_id"] == _card(cid)["signal_id"]
    _rewrite(other, lambda x: x.update(proposal=own))
    monkeypatch.setattr(escalations, "RESIGN_AFTER_S", 0)
    assert escalations.refresh(other, "seen again")
    assert _card(other)["proposal"] == own, "never signed for the copy"
    assert _refusal(_card(other), _request(_card(other), "isolate_vm")) == "proposal_mismatch"


def test_a_decision_folded_into_a_card_signs_its_own_port_never_the_cards(watch):
    """M5429 (§2.4, « Une nuance »): a card another hand wrote that waits, with a port of its choosing;
    the watch then decides the same block — folded into that card, the proposal signs the watch's
    port, and the card says it: what runs is the watch's decision, its port included."""
    cid = _forge(action="block_suspicious_ip", escalation_type="low_confidence",
                 action_params={"ip": IP, "port": 3389})
    same = escalations.record(signal_id="watch-rule-2", resource_id=VM, action="block_suspicious_ip",
                              escalation_type="low_confidence", reason="held", action_params={"ip": IP, "port": 22})
    assert same == cid
    card = _card(cid)
    assert (card["proposal"]["port"], card["action_params"]["port"]) == (22, 22)
    assert aq.proposal_refusal(card, _request(card, "block_ip", ip=IP), watch_public=WATCH.public) is None


def test_the_watch_never_signs_a_target_out_of_ascii(watch):
    """SEC-B: a request is compared with the proposal at the byte, and one out of ASCII is refused —
    the watch signs none."""
    cid = escalations.record(signal_id="watch-rule-3", resource_id=VM[:-1] + "K", action="isolate_vm",
                             escalation_type="mode_hold", reason="held")
    assert "proposal" not in _card(cid)
