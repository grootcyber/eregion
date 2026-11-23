"""DOS3b (#1063; `docs/design/dossier-isolation.md` §4.6, §12, the decisions of 23/11): the dossier of a block
of an internal address.

A block executed alone has no dossier, but for an internal address (`glorfindel/dossier_block.py`); one
that cannot be read is neither said internal nor public — its dossier not composed, and said. Kept 30 days
after the unblock seen, never removed while the block holds nor while a block state cannot be read. The
message to the model unchanged to the byte. Mutants M7091–M7094 (`scripts/mutants/DOS3b.py`). No call
reaches Azure nor a model.
"""
from __future__ import annotations

import copy
import hashlib
import json
from unittest.mock import patch

import pytest

from glorfindel import agent, dossier, dossier_block
from glorfindel.config import AutonomyConfig
from tests.unit.test_cycle_line import MESSAGE_SHA256, PAST, USER_SHA256, _bree, _llm
from tests.unit.test_cycle_line import hermetic  # noqa: F401 — its autouse fixture, here too
from tests.unit.test_dependency_failures import FakeMemory
from tests.unit.test_dossier import NOW, VM, _compose, _isolated, _proposed, _signal
from tests.unit.test_dossier import _no_cap  # noqa: F401 — its autouse fixture, here too

DAY = 86400
OTHER = VM.replace("vm-dos3", "vm-other")


def _blocked(ip: str | None = "10.0.2.7", **kw) -> dict:
    """A cycle whose block ran and was verified; the address said by the connector (`outcome.ip`)."""
    outcome = {"status": "blocked", "executed": True, "verified": True, "method": "nsg_rule",
               "verified_at": "2026-11-10T02:37:00+00:00", "scoped": True, "resource_id": VM}
    if ip is not None:
        outcome["ip"] = ip
    state = _isolated(action="block_suspicious_ip", outcome=outcome)
    state.update(kw)
    return state


def _block_state(ip: str = "10.0.2.7", rid: str = VM) -> None:
    from glorfindel.response import state as st
    st._save_block_state(rid.rsplit("/", 1)[-1], ip, rid, placements=[])


def _unblocked(ip: str = "10.0.2.7", rid: str = VM) -> None:
    from glorfindel.response import state as st
    st._clear_block_state(rid, ip)


def _doc(name: str) -> dict:
    return json.loads((dossier.DOSSIER_DIR / name).read_text())


# ── « Interne », en code ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ip, rng", [
    ("10.0.2.7", "10.0.0.0/8"), ("172.16.3.4", "172.16.0.0/12"), ("172.31.255.254", "172.16.0.0/12"),
    ("192.168.1.1", "192.168.0.0/16"), ("100.64.0.1", "100.64.0.0/10"), ("100.127.255.1", "100.64.0.0/10"),
    ("169.254.10.10", "169.254.0.0/16"), ("127.0.0.1", "127.0.0.0/8"), ("fd00::1", "fc00::/7"),
    ("fe80::1", "fe80::/10"), ("::1", "::1/128"), ("::ffff:10.1.2.3", "10.0.0.0/8"), (" 10.9.9.9 ", "10.0.0.0/8"),
])
def test_an_internal_address_says_its_range(ip, rng):
    classe, par = dossier_block.classify(ip)
    assert classe == "interne" and par.startswith(f"{rng} : ")


@pytest.mark.parametrize("ip", ["203.0.113.7", "8.8.8.8", "172.32.0.1", "172.15.255.255", "100.128.0.1",
                                "100.63.255.255", "11.0.0.1", "192.169.0.1", "2001:db8::1", "::ffff:203.0.113.9"])
def test_a_public_address_is_public(ip):
    """M7091: a public address said internal."""
    assert dossier_block.classify(ip) == ("publique", "")


@pytest.mark.parametrize("ip", ["", None, "   ", "not-an-ip", "10.0.0.0/8", "10.0.0.256", "*", "Internet"])
def test_an_address_that_cannot_be_read_is_neither_internal_nor_public(ip):
    """M7094: an unreadable address said public."""
    classe, par = dossier_block.classify(ip)
    assert classe == "illisible" and par


# ── Le périmètre ─────────────────────────────────────────────────────────────────────────────────

def test_a_block_of_a_private_address_is_composed():
    """M7092: an internal block out of the scope."""
    assert dossier.scope(_blocked(), True) == ("blocage", "block_suspicious_ip")
    doc = _compose(_blocked())
    assert doc["perimetre"] == "blocage" and doc["executee"] is True and doc["compose"] is True
    assert doc["ip"] == "10.0.2.7" and doc["adresse"] == "interne" and doc["adresse_par"].startswith("10.0.0.0/8")
    facts = {f["code"]: f for f in doc["faits"]}
    assert list(facts) == ["F3c", "F4c", "F5b", "F5c", "F6a", "F6b", "F6c", "F6d", "F6e", "F6f", "F6g", "F6h"]
    assert facts["F5c"]["etat"] == "lu" and facts["F5c"]["dit"] == "blocage vérifié sur Azure (nsg_rule)"
    assert facts["F5b"]["etat"] == "sans_objet"


def test_the_address_comes_from_the_signal_when_the_outcome_does_not_say_it():
    state = _blocked(None, signal=_signal(detected_data={"SourceIP": "192.168.4.20"}))
    assert _compose(state)["ip"] == "192.168.4.20"


def test_a_block_of_a_public_address_has_no_dossier():
    for ip in ("203.0.113.7", "2001:db8::7"):
        assert dossier.scope(_blocked(ip), True) == ("", "")
        assert dossier.at_cycle_end(_blocked(ip), True, "real", "", now=NOW) == ""
    assert not dossier.DOSSIER_DIR.exists() or not list(dossier.DOSSIER_DIR.glob("*.json"))


@pytest.mark.parametrize("ip", [None, "not-an-ip", "10.0.0.0/24"])
def test_an_unreadable_address_is_neither_composed_nor_lost(ip):
    """M7094: never said public (no dossier at all, silence), never composed as internal; the cycle never
    pays for it (at_cycle_end never raises)."""
    name = dossier.at_cycle_end(_blocked(ip), True, "real", "", now=NOW)
    assert name
    doc = _doc(name)
    assert doc["perimetre"] == "blocage" and doc["adresse"] == "illisible" and doc["compose"] is False
    assert doc["faits"] == [] and doc["pourquoi"].startswith("adresse bloquée illisible (")
    assert "ni interne ni publique" in doc["pourquoi"]


def test_an_unreadable_address_is_not_counted_against_the_ceiling(monkeypatch):
    monkeypatch.setenv("GLORFINDEL_DOSSIER_MAX_PER_H", "1")
    dossier.at_cycle_end(_blocked("not-an-ip"), True, "real", "", now=NOW)
    other = _blocked(signal={**_signal(), "signal_id": "rule-x-0000000c"})
    assert _doc(dossier.at_cycle_end(other, True, "real", "", now=NOW))["compose"] is True


@pytest.mark.parametrize("state", [
    _blocked(dry_run=True),
    _blocked(outcome={"status": "dry_run", "executed": True, "ip": "10.0.2.7"}),
    _blocked(outcome={"status": "no_op", "executed": True, "ip": "10.0.2.7"}),
])
def test_a_block_that_did_not_run_has_none(state):
    assert dossier.at_cycle_end(state, True, "real", "", now=NOW) == ""


def test_a_block_of_the_control_plane_has_none():
    assert dossier.at_cycle_end(_blocked(), False, "real", "", now=NOW) == ""


def test_a_proposed_block_keeps_its_dossier_whatever_its_address():
    """Q2 unchanged: a card that proposes a block without executing it, public address or not."""
    state = _proposed(action="block_suspicious_ip", signal=_signal(detected_data={"SourceIP": "203.0.113.7"}))
    assert _compose(state)["perimetre"] == "proposition"


def test_the_block_s_dossier_never_enters_the_signal():
    state = _blocked(signal=_bree())
    before = copy.deepcopy(state)
    assert dossier.at_cycle_end(state, True, "real", "", now=NOW)
    assert state == before
    assert hashlib.sha256(agent._build_user_message(state["signal"], PAST).encode()).hexdigest() == USER_SHA256


def test_a_block_cycle_with_its_dossier_leaves_the_message_to_the_model_unchanged_to_the_byte():
    state = {**_blocked(signal=_bree()), "past_cycles": PAST, "incident": None, "telemetry_gaps": [],
             "reasoning": "Brute force interne.", "explanation": ""}
    mem = FakeMemory()
    with patch("glorfindel.escalations.notify_action"):
        out = agent.store_cycle(state, memory=mem)
    assert [_doc(f.name)["perimetre"] for f in dossier.DOSSIER_DIR.glob("*.json")] == ["blocage"]
    seen: list[dict] = []

    def completion(**kw):
        seen.append(kw)
        return _llm("snapshot")
    with patch("litellm.completion", side_effect=completion):
        agent.decide({"signal": out["signal"], "past_cycles": PAST, "incident": None, "dry_run": True,
                      "telemetry_gaps": []}, model="anthropic/claude-test",
                     autonomy=AutonomyConfig(default="human_only"))
    blob = json.dumps({"messages": seen[0]["messages"], "tools": seen[0]["tools"]}, sort_keys=True,
                      ensure_ascii=False)
    assert hashlib.sha256(blob.encode()).hexdigest() == MESSAGE_SHA256
    assert "dossier" not in json.dumps(mem.stored[0]) and "dossier" not in json.dumps(out["signal"])


# ── La rétention : 30 jours après le déblocage vu ────────────────────────────────────────────────

def test_a_block_s_dossier_is_kept_while_blocked_and_30_days_after_the_unblock():
    _block_state()
    name = dossier.at_cycle_end(_blocked(), True, "real", "", now=NOW)
    assert dossier.retention_pass(now=NOW + 40 * DAY) == 0 and _doc(name)["leve_vu_a"] == ""
    _unblocked()
    assert dossier.retention_pass(now=NOW + 41 * DAY) == 0 and _doc(name)["leve_vu_a"]
    assert dossier.retention_pass(now=NOW + 70 * DAY) == 0 and (dossier.DOSSIER_DIR / name).exists()
    assert dossier.retention_pass(now=NOW + 71.1 * DAY) == 1 and not (dossier.DOSSIER_DIR / name).exists()


def test_a_block_still_held_is_never_removed():
    """M7093: the retention without waiting for the unblock — the clock started at the first pass."""
    _block_state()
    name = dossier.at_cycle_end(_blocked(), True, "real", "", now=NOW)
    for days in (1, 31, 62, 400):
        assert dossier.retention_pass(now=NOW + days * DAY) == 0
        assert _doc(name)["leve_vu_a"] == ""


def test_a_block_written_another_way_still_holds_it():
    """The address as the block state wrote it, the dossier as it read it: the same address."""
    _block_state("::ffff:10.0.2.7")
    name = dossier.at_cycle_end(_blocked(), True, "real", "", now=NOW)
    dossier.retention_pass(now=NOW + 40 * DAY)
    assert _doc(name)["leve_vu_a"] == ""


def test_a_block_blocked_again_stops_the_clock():
    _block_state()
    name = dossier.at_cycle_end(_blocked(), True, "real", "", now=NOW)
    _unblocked()
    dossier.retention_pass(now=NOW + DAY)
    assert _doc(name)["leve_vu_a"]
    _block_state()
    dossier.retention_pass(now=NOW + 2 * DAY)
    assert _doc(name)["leve_vu_a"] == ""


def test_another_address_or_another_vm_does_not_hold_it():
    _block_state("10.0.2.8")
    _block_state("10.0.2.7", OTHER)
    name = dossier.at_cycle_end(_blocked(), True, "real", "", now=NOW)
    dossier.retention_pass(now=NOW + DAY)
    assert _doc(name)["leve_vu_a"]
    assert dossier.retention_pass(now=NOW + 32 * DAY) == 1


def test_an_unreadable_address_is_held_by_any_block_of_its_vm():
    _block_state("10.0.2.8")
    name = dossier.at_cycle_end(_blocked("not-an-ip"), True, "real", "", now=NOW)
    assert dossier.retention_pass(now=NOW + 40 * DAY) == 0 and _doc(name)["leve_vu_a"] == ""
    _unblocked("10.0.2.8")
    dossier.retention_pass(now=NOW + 41 * DAY)
    assert _doc(name)["leve_vu_a"]


def test_nothing_moves_on_a_block_s_dossier_while_a_block_state_cannot_be_read():
    """Whose block holds is unknown: the block's dossier waits; an isolation's goes on."""
    from glorfindel.response import state as st
    block = dossier.at_cycle_end(_blocked(), True, "real", "", now=NOW)
    proposal = dossier.at_cycle_end(_proposed(signal={**_signal(), "signal_id": "rule-x-0000000d"}), True,
                                    "real", "", now=NOW)
    st._BLOCK_STATE_DIR.mkdir(parents=True, exist_ok=True)
    (st._BLOCK_STATE_DIR / "vm-dos3--00000000.json").write_text("[{cut")
    assert dossier.retention_pass(now=NOW + DAY) == 0
    assert _doc(block)["leve_vu_a"] == "" and _doc(proposal)["leve_vu_a"]
    assert dossier.retention_pass(now=NOW + 90 * DAY) == 1
    assert (dossier.DOSSIER_DIR / block).exists() and not (dossier.DOSSIER_DIR / proposal).exists()


def test_the_block_s_module_reads_no_cloud_and_imports_no_dossier():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "glorfindel" / "dossier_block.py").read_text(encoding="utf-8")
    assert not any(w in text for w in ("azure.", "litellm", "providers.azure", "detector_for", "run_query",
                                       "glorfindel.dossier ", "from glorfindel import dossier\n"))
