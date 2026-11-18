"""B3a (#609) — a deterministic floor in the decision: a brute force that succeeded, then root,
on the same VM, and a card proposes isolate_vm, whatever the model chose.

The harness of H0's CD drew `block_suspicious_ip` one time in three on its paired case (a brute
force after a sudo to root on the same VM), above the gate: the source blocked, the VM where
root was taken left standing. Jonathan's decision (06/11): when the correlation (COR1) confirmed
both on one VM, `decide` proposes isolate_vm, and the card says why. Never in the prompt.

SEC-E (#846; Jonathan's decision of 15/11): both facts are read in lines the VM writes — until a
source the VM does not write proves them (SEC-A3), the floor only proposes, whatever the mode: a
card `floor_proposal` with isolate_vm, never an isolation run by the floor. The gates and the
draws judge the model's own choice (its action runs alone as they judged it, the floor's card
apart); a fact counts within its TTL, absolute; a release of the isolation forgets them.

No floor for a brute force alone, a sudo alone, two VMs, or failures the correlation never saw
succeed (neighbouring signals): the model's choice stands.

No Azure call, no model call (the model is patched, dry_run or a recording connector).
Mutants M4375–M4379 (scripts/mutants/B3a.py) and M5721–M5740 (scripts/mutants/SEC-E.py) are
measured here and in tests/unit/test_decision_queue.py; M6311–M6320 (scripts/mutants/SEC-Ec.py:
the reason says what one click approves) here.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eregion_core.action_queue import proposed_verbs
from glorfindel import agent
from glorfindel.config import AutonomyConfig
from glorfindel.incidents import IncidentRegistry
from tests.unit.test_dependency_failures import FakeMemory, LogAnalytics, Recorder, _agent, _cards

RID = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-b3a"
OTHER = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-b3b"
IP = "185.220.101.5"
SMOKE = Path(__file__).resolve().parents[2] / "scripts" / "llm_smoke.py"


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    for var in ("GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "GLORFINDEL_LLM_BASE_URL",
                "GLORFINDEL_CONFIDENCE_THRESHOLD", "GLORFINDEL_LLM_TIMEOUT_S",
                "GLORFINDEL_READ_ONLY", "GLORFINDEL_DECISION_DRAWS", "GLORFINDEL_INCIDENT_TTL_S"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    from eregion_core import llm_call
    monkeypatch.setattr(llm_call, "_AUTO_TOOL_CHOICE", set())
    monkeypatch.setattr(llm_call, "_NO_TEMPERATURE", set())
    import glorfindel.escalations as escalations
    monkeypatch.setattr(escalations, "notify_action", lambda **kw: None)
    monkeypatch.setattr(agent, "CycleMemory", FakeMemory)
    from glorfindel.actions import AzureConnector

    def no_azure(self):
        raise RuntimeError("no Azure client in tests (B3a)")
    monkeypatch.setattr(AzureConnector, "_ensure_clients", no_azure)


def _decision(action: str, confidence: float = 0.9, **fields) -> MagicMock:
    """The model, patched: a security_decision call that answers `action`."""
    call = MagicMock()
    call.function.arguments = json.dumps({
        "reasoning": f"r — {action}", "confidence": confidence, "action": action,
        "reversible": True, "explanation": "e", "escalate": False, "escalation_reason": "",
        "suggested_steps": [], **fields})
    resp = MagicMock()
    resp.choices[0].message.tool_calls = [call]
    resp.usage = None
    return resp


def _brute_force(rid: str = RID, *, succeeded: bool = True, **row_over) -> dict:
    """A RulePoller detection of `ssh-brute-force`; `succeeded`: marked by the correlation
    (COR1), a login from the same address seen after the failures."""
    row = {"Computer": rid.rsplit("/", 1)[-1], "_ResourceId": rid, "SourceIP": IP,
           "FailedAttempts": 47}
    if succeeded:
        row["Correlation"] = "ssh-login-after-brute-force"
        row["SuccessfulLogins"] = [{"account": "alice", "method": "password",
                                    "at": "2026-11-06T10:00:00+00:00"}]
    row.update(row_over)
    return {
        "signal_id": f"rule-ssh-brute-force-{rid[-3:]}", "event": "detection", "ttp": "T1110.001",
        "severity": "critical" if succeeded else "high", "resource_id": rid, "resource_type": "vm",
        "timestamp": "2026-11-06T10:05:00+00:00",
        "context": {"rule_name": "ssh-brute-force", "attribution": "asset",
                    "run_id": "watch-ssh-brute-force-20261106T100500Z"},
        "raw_signal": {"first_result_row": row},
    }


def _sudo(rid: str = RID, **context) -> dict:
    """A RulePoller detection of `sudo-privilege-escalation`: a sudo to a root shell."""
    return {
        "signal_id": f"rule-sudo-privilege-escalation-{rid[-3:]}", "event": "detection",
        "ttp": "T1548.003", "severity": "high", "resource_id": rid, "resource_type": "vm",
        "timestamp": "2026-11-06T10:04:00+00:00",
        "context": {"rule_name": "sudo-privilege-escalation", "attribution": "asset",
                    "run_id": "watch-sudo-privilege-escalation-20261106T100400Z", **context},
        "raw_signal": {"first_result_row": {
            "Computer": rid.rsplit("/", 1)[-1], "_ResourceId": rid, "ProcessName": "sudo",
            "SyslogMessage": "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash"}},
    }


def _incident(*confirmed: str, rid: str = RID, age_s: float = 0.0) -> dict:
    """The VM's incident as the registry hands it: each fact dated `age_s` ago (SEC-E)."""
    from datetime import datetime, timedelta, timezone
    at = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat()
    return {"incident_id": "i1", "resource_id": rid, "ttps": ["T1548.003", "T1110.001"],
            "started_at": "", "last_signal_at": "", "actions_taken": [], "signals_count": 2,
            "state": "active", "confirmed": list(confirmed), "confirmed_at": {f: at for f in confirmed}}


def _decide(signal: dict, resp, incident: dict | None = None, mode: str = "non_disruptive"):
    state = {"signal": signal, "past_cycles": [], "incident": incident, "dry_run": True,
             "telemetry_gaps": []}
    with patch("litellm.completion", return_value=resp) as llm:
        out = agent.decide(state, model="anthropic/claude-test",
                           autonomy=AutonomyConfig(default=mode))
    return out, llm


# ── The floor plays ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("signal,kept", [
    (_brute_force(), agent.ROOT_ELEVATION),           # root first, then the brute force seen succeed
    (_sudo(), agent.LOGIN_AFTER_BRUTE_FORCE),         # the brute force seen succeed, then root
], ids=["brute-force-after-root", "root-after-brute-force"])
def test_a_block_is_raised_to_isolate_vm_and_says_why(signal, kept):
    """In human_only, the model blocks the source: the card proposes isolate_vm in its place —
    the floor's own type —, says why, and nothing runs."""
    out, llm = _decide(signal, _decision("block_suspicious_ip"), _incident(kept), mode="human_only")
    assert out["action"] == "isolate_vm" and out["escalate"] is True, out.get("escalation_reason")
    assert out["held_by"] == "floor" and out["floor_card"] is False
    assert out["floor"].startswith("Plancher déterministe (B3a)")
    assert "'block_suspicious_ip'" in out["floor"] and "jamais exécutée par le plancher" in out["floor"]
    assert out["escalation_reason"].startswith(out["floor"])      # the card says it
    assert llm.call_count == 1                                      # nothing about to run alone
    if signal["ttp"] == "T1110.001":
        assert IP in out["floor"]


def test_no_action_is_raised_to_isolate_vm():
    """« Nothing », in non_disruptive: a card that proposes isolate_vm, never an isolation."""
    out, llm = _decide(_brute_force(), _decision("no_action"), _incident(agent.ROOT_ELEVATION))
    assert out["action"] == "isolate_vm" and out["escalate"] is True and out["held_by"] == "floor"
    assert "'no_action'" in out["floor"] and llm.call_count == 1


# ── SEC-E: the floor proposes, it never runs ─────────────────────────────────────────────

@pytest.mark.parametrize("answer", ["block_suspicious_ip", "snapshot"])
def test_the_models_own_action_runs_as_its_gates_judged_it_and_the_floor_proposes(answer):
    """non_disruptive, a VM ready: the model's own action runs alone — its draws its own,
    unraised —, and the floor's card is apart (`floor_card`), never an isolation run."""
    out, llm = _decide(_brute_force(), _decision(answer), _incident(agent.ROOT_ELEVATION))
    assert out["action"] == answer and out["escalate"] is False
    assert out["floor_card"] is True and out["held_by"] == ""
    assert "exécuté seul" in out["floor"] and "une carte propose l'isolation" in out["floor"]
    assert out["explanation"].startswith(out["floor"])
    assert out["uncontained"] == ""                         # one card says it: the floor's
    if answer == "block_suspicious_ip":
        assert [x["action"] for x in out["decision_draws"]] == [answer] * 3 and llm.call_count == 3


def test_the_draws_judge_the_models_choice_never_the_raised_action():
    """The first draw blocks, the two others answer « nothing »: they disagree on the model's
    choice — held (unstable), never agreed by a floor that raised each to isolate_vm; the card
    then proposes isolate_vm, the floor's."""
    resp = [_decision("block_suspicious_ip"), _decision("no_action"), _decision("no_action")]
    state = {"signal": _brute_force(), "past_cycles": [], "dry_run": True, "telemetry_gaps": [],
             "incident": _incident(agent.ROOT_ELEVATION)}
    with patch("litellm.completion", side_effect=resp):
        out = agent.decide(state, model="anthropic/claude-test",
                           autonomy=AutonomyConfig(default="non_disruptive"))
    assert [x["action"] for x in out["decision_draws"]] == ["block_suspicious_ip", "no_action", "no_action"]
    assert out["action"] == "isolate_vm" and out["escalate"] is True and out["held_by"] == "floor"
    assert "Décision instable" in out["escalation_reason"]


def test_the_confidence_kept_is_the_models_on_its_own_choice():
    """The card says the confidence the model gave its own choice — never one in the isolation."""
    out, _ = _decide(_brute_force(), _decision("no_action", confidence=0.93),
                     _incident(agent.ROOT_ELEVATION))
    assert out["confidence"] == 0.93 and "'no_action' (confiance 93%, sur ce choix)" in out["floor"]


@pytest.mark.parametrize("mode", ["non_disruptive", "human_only"])
@pytest.mark.parametrize("answer", ["block_suspicious_ip", "no_action", "snapshot"])
def test_the_floor_never_isolates_whatever_the_mode(mode, answer):
    """Through the graph, the pair on the VM, every mode: no isolation written — a card proposes
    it (`floor_proposal`, isolate_vm, approvable), the model's own action as its gates judged it."""
    conn = Recorder()
    agent_ = _agent(conn, autonomy=AutonomyConfig(default=mode))
    _respond(agent_, _sudo(), _decision("no_action"))
    _respond(agent_, _brute_force(), _decision(answer))
    assert "isolate_vm" not in conn.writes()
    [card] = [c for c in _cards() if c["escalation_type"] == agent.FLOOR_TYPE]
    assert card["action"] == "isolate_vm" and "Plancher déterministe (B3a)" in card["reason"]
    from eregion_core.action_queue import APPROVABLE_TYPES
    assert agent.FLOOR_TYPE in APPROVABLE_TYPES
    ran = mode == "non_disruptive" and answer == "block_suspicious_ip"     # a snapshot writes no rule
    assert conn.writes() == ([answer] if ran else [])


@pytest.mark.parametrize("via", ["unattributed", "appliance"])
@pytest.mark.parametrize("answer", ["block_suspicious_ip", "no_action"])
def test_a_detection_that_does_not_name_the_vm_keeps_the_attributions_card(via, answer):
    """The pair live on the VM, and a detection the RulePoller could not tie to it — anchored
    there, or a call from behind an appliance (SEC-A4): the card stays `unattributed_signal`,
    never approvable in one click (approval_refusal), never the floor's; the floor is said in its
    reason, and the row's address is never told as a fact of this VM."""
    from glorfindel.approval import approval_refusal
    ctx = {"attribution": "unattributed", "candidates": ["vm-b3a"]}
    if via == "appliance":
        ctx.update(attribution_via="appliance", appliance="vm-hub-fw")
    signal = _brute_force()
    signal["context"] = {**signal["context"], **ctx}
    both = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE)
    out, _ = _decide(signal, _decision(answer), both)
    assert out["escalate"] is True and out["held_by"] == "attribution" and out["floor_card"] is False
    assert out["action"] == answer and "ne nomme pas cette VM" in out["floor"]
    assert IP not in out["floor"]
    agent.escalate_to_human({**out, "dry_run": False})
    [card] = [c for c in _cards() if c["resource_id"] == RID]
    assert card["escalation_type"] == "unattributed_signal"
    assert approval_refusal(card, "vm-b3a")


def test_an_unattributed_snapshot_run_alone_gets_no_floor():
    """The model's snapshot runs alone on an unattributed detection: no floor's card on a VM the
    detection may not concern."""
    signal = _sudo(attribution="unattributed")
    out, _ = _decide(signal, _decision("snapshot"), _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE))
    assert out["floor"] == "" and out["floor_card"] is False and out["action"] == "snapshot"


# ── SEC-Ec: the reason says what one click approves; every earlier hold the attribution's ───

def _unattributed(signal: dict) -> dict:
    signal["context"] = {**signal["context"], "attribution": "unattributed", "candidates": ["vm-b3a"]}
    return signal


def test_an_unattributed_snapshot_held_by_the_mode_says_what_one_click_approves():
    """human_only, the pair live, a detection that does not name the VM, the model's snapshot: the
    card stays the mode's (`mode_hold`), approvable for the snapshot only — never an isolation —,
    and its reason says so, never « rien ne s'y approuve en un clic » (SEC-Ec, #913)."""
    from glorfindel.approval import approval_refusal
    both = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE)
    out, _ = _decide(_sudo(attribution="unattributed"), _decision("snapshot"), both, mode="human_only")
    assert out["escalate"] is True and out["mode_hold"] is True and out["floor_card"] is False
    assert out["action"] == "snapshot" and out["held_by"] == "attribution"
    assert "ne nomme pas cette VM" in out["floor"] and "rien ne s'y approuve" not in out["floor"]
    assert "seul 'snapshot' s'y approuve en un clic, jamais l'isolation" in out["floor"]
    assert "la carte reste celle du mode human_only" in out["floor"]
    agent.escalate_to_human({**out, "dry_run": False})
    [card] = [c for c in _cards() if c["resource_id"] == RID]
    assert card["escalation_type"] == "mode_hold" and card["action"] == "snapshot"
    assert card["reason"].startswith(out["floor"])
    assert approval_refusal(card, "vm-b3a") is None
    assert proposed_verbs(card) == {"snapshot"}                 # the snapshot, never an isolation


@pytest.mark.parametrize("pair", [True, False], ids=["pair-live", "no-pair"])
def test_a_protected_address_then_the_attribution(pair):
    """An unattributed detection whose address is on the never-block list: the never-block guard
    holds the block (`protected_address`); with the pair live, the floor's attribution branch makes
    it the attribution's (`unattributed_signal`) — both refused by the approval (SEC-Ec, #913)."""
    from glorfindel.approval import approval_refusal
    signal = _unattributed(_brute_force(SourceIP="10.0.0.5"))
    incident = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE) if pair else None
    out, _ = _decide(signal, _decision("block_suspicious_ip"), incident)
    assert out["escalate"] is True and out["action"] == "block_suspicious_ip"
    assert out["held_by"] == ("attribution" if pair else "never_block")
    agent.escalate_to_human({**out, "dry_run": False})
    [card] = [c for c in _cards() if c["resource_id"] == RID]
    assert card["escalation_type"] == ("unattributed_signal" if pair else "protected_address")
    assert approval_refusal(card, "vm-b3a") and proposed_verbs(card) == frozenset()
    if pair:
        assert "rien ne s'y approuve en un clic" in card["reason"]


@pytest.mark.parametrize("pair", [True, False], ids=["pair-live", "no-pair"])
def test_a_release_hold_then_the_attribution(pair):
    """An unattributed detection, the model releases the isolation: the release precondition holds
    it (`release_hold`, approvable); with the pair live, the floor's attribution branch makes it
    the attribution's (`unattributed_signal`), refused by the approval — the more prudent (SEC-Ec)."""
    from glorfindel.approval import approval_refusal
    signal = _unattributed(_brute_force())
    incident = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE) if pair else None
    out, _ = _decide(signal, _decision("release_isolation"), incident)
    assert out["escalate"] is True and out["action"] == "release_isolation"
    assert out["held_by"] == ("attribution" if pair else "release_precondition")
    agent.escalate_to_human({**out, "dry_run": False})
    [card] = [c for c in _cards() if c["resource_id"] == RID]
    assert card["escalation_type"] == ("unattributed_signal" if pair else "release_hold")
    assert bool(approval_refusal(card, "vm-b3a")) is pair
    assert proposed_verbs(card) == (frozenset() if pair else {"release_isolation"})
    if pair:
        assert "rien ne s'y approuve en un clic" in card["reason"]


@pytest.mark.parametrize("pair", [True, False], ids=["pair-live", "no-pair"])
def test_a_low_confidence_hold_then_the_attribution(pair):
    """An unattributed detection, the model's snapshot under the threshold: the confidence gate
    holds it (`low_confidence`, approvable); with the pair live, the attribution's card — the mode
    never held it, so the card is not the mode's (SEC-Ec, docs/glorfindel.md)."""
    from glorfindel.approval import approval_refusal
    incident = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE) if pair else None
    out, _ = _decide(_sudo(attribution="unattributed"), _decision("snapshot", confidence=0.2),
                     incident, mode="human_only")
    assert out["escalate"] is True and out["mode_hold"] is False and out["action"] == "snapshot"
    assert out["held_by"] == ("attribution" if pair else "confidence")
    agent.escalate_to_human({**out, "dry_run": False})
    [card] = [c for c in _cards() if c["resource_id"] == RID]
    assert card["escalation_type"] == ("unattributed_signal" if pair else "low_confidence")
    assert bool(approval_refusal(card, "vm-b3a")) is pair
    assert proposed_verbs(card) == (frozenset() if pair else {"snapshot"})


def test_the_message_to_the_model_is_the_same_to_the_byte():
    """The floor is in the code, never in the prompt: the same detection, with and without the
    pair on its incident (and the facts' dates), sends the model the same messages."""
    def sent(incident):
        state = {"signal": _brute_force(), "past_cycles": [], "dry_run": True, "telemetry_gaps": [],
                 "incident": incident}
        with patch("litellm.completion", return_value=_decision("no_action")) as llm:
            agent.decide(state, model="anthropic/claude-test", autonomy=AutonomyConfig(default="human_only"))
        return json.dumps(llm.call_args.kwargs["messages"], sort_keys=True, default=str)
    bare = _incident()
    assert sent(_incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE)) == sent(bare)


def test_a_model_that_isolates_keeps_its_choice():
    """Already at the floor: nothing raised, nothing claimed — its own words stay."""
    out, _ = _decide(_brute_force(), _decision("isolate_vm"), _incident(agent.ROOT_ELEVATION))
    assert out["action"] == "isolate_vm" and out["escalate"] is False
    assert out["floor"] == "" and out["explanation"] == "e"


def test_the_gates_still_judge_the_isolation():
    """A low confidence holds the model's block as it would anywhere: the card is the floor's,
    proposes isolate_vm, and says both."""
    out, _ = _decide(_brute_force(), _decision("block_suspicious_ip", confidence=0.4),
                     _incident(agent.ROOT_ELEVATION))
    assert out["action"] == "isolate_vm" and out["escalate"] is True
    assert out["held_by"] == "floor"
    assert "Low confidence" in out["escalation_reason"] and "Plancher" in out["escalation_reason"]


# ── No floor: the model's choice stands ─────────────────────────────────────────────────

def test_a_brute_force_alone_keeps_the_models_choice():
    """Seen succeed, but no root on this VM: the block stands."""
    for incident in (None, _incident(), _incident(agent.LOGIN_AFTER_BRUTE_FORCE)):
        out, _ = _decide(_brute_force(), _decision("block_suspicious_ip"), incident)
        assert out["action"] == "block_suspicious_ip" and out["floor"] == ""


def test_a_sudo_alone_keeps_the_models_choice():
    for incident in (None, _incident(), _incident(agent.ROOT_ELEVATION)):
        out, _ = _decide(_sudo(), _decision("snapshot"), incident)
        assert out["action"] == "snapshot" and out["floor"] == ""


def test_neighbouring_signals_the_correlation_never_confirmed_keep_the_models_choice():
    """Failures alone, or logins the correlation could not read, next to a sudo to root: no
    login confirmed — the block stands."""
    unchecked = _brute_force(succeeded=False, LoginCheck={"status": "unchecked", "why": "plafond"})
    for signal in (_brute_force(succeeded=False), unchecked):
        out, _ = _decide(signal, _decision("block_suspicious_ip"), _incident(agent.ROOT_ELEVATION))
        assert out["action"] == "block_suspicious_ip" and out["floor"] == ""
    assert agent.confirmed_facts(_brute_force(succeeded=False)) == []
    assert agent.confirmed_facts(unchecked) == []


def test_two_vms_keep_the_models_choice():
    """Root on another VM: an incident of another resource is never this VM's."""
    out, _ = _decide(_brute_force(), _decision("block_suspicious_ip"),
                     _incident(agent.ROOT_ELEVATION, rid=OTHER))
    assert out["action"] == "block_suspicious_ip" and out["floor"] == ""


def test_what_confirms_nothing():
    """A timeout, an attack_started, an unattributed detection (anchored on a VM it does not
    name): nothing confirmed on this VM."""
    assert agent.confirmed_facts(_sudo()) == [agent.ROOT_ELEVATION]
    assert agent.confirmed_facts(_brute_force()) == [agent.LOGIN_AFTER_BRUTE_FORCE]
    assert agent.confirmed_facts({**_sudo(), "event": "detection_timeout"}) == []
    assert agent.confirmed_facts({**_sudo(), "event": "attack_started"}) == []
    assert agent.confirmed_facts(_sudo(attribution="unattributed")) == []
    out, _ = _decide({**_brute_force(), "event": "detection_timeout"},
                     _decision("block_suspicious_ip"), _incident(agent.ROOT_ELEVATION))
    assert out["floor"] == ""


@pytest.mark.parametrize("event", ["recovery_complete", "detection_timeout"])
def test_only_a_detection_is_floored(event):
    """An incident holding both facts, and a signal that is no detection: the release after a
    completed restore, a timeout — the model's choice stands (never re-isolated by the floor)."""
    both = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE)
    out, _ = _decide({**_sudo(), "event": event}, _decision("release_isolation"), both)
    assert out["action"] == "release_isolation" and out["floor"] == ""
    # The same incident, a detection: floored (the control).
    out, _ = _decide(_sudo(), _decision("release_isolation"), both)
    assert out["action"] == "isolate_vm" and out["floor"]


def test_the_reason_fits_the_choice_set_aside():
    """« Bloquer la source… » only when the model blocked (the card in its place, human_only)."""
    both = _incident(agent.ROOT_ELEVATION)
    blocked, _ = _decide(_brute_force(), _decision("block_suspicious_ip"), both, mode="human_only")
    assert "bloquer la source" in blocked["floor"]
    for answer in ("no_action", "snapshot", "restore_from_backup"):
        out, _ = _decide(_brute_force(), _decision(answer), both, mode="human_only")
        assert "bloquer la source" not in out["floor"], answer


def test_an_action_only_a_human_approves_is_kept_on_a_card():
    """The model proposes a restore: the card proposes isolate_vm, and the restore is never lost
    — said in the reason, kept in the state. Nothing runs, in non_disruptive too."""
    out, _ = _decide(_brute_force(), _decision("restore_from_backup"), _incident(agent.ROOT_ELEVATION))
    assert out["action"] == "isolate_vm" and out["escalate"] is True
    assert out["floor_displaced"] == "restore_from_backup"
    assert "'restore_from_backup' reste proposée à un humain" in out["floor"]
    conn = Recorder()
    agent_ = _agent(conn, autonomy=AutonomyConfig(default="non_disruptive"))
    _respond(agent_, _sudo(), _decision("no_action"))
    final = _respond(agent_, _brute_force(), _decision("restore_from_backup"))
    assert conn.writes() == [] and final["floor_displaced"] == "restore_from_backup"
    card = next(c for c in _cards() if c["action"] == "isolate_vm")
    assert card["escalation_type"] == agent.FLOOR_TYPE
    assert "restore_from_backup" in card["reason"] and "Plancher déterministe (B3a)" in card["reason"]


def test_an_action_only_a_human_approves_is_said_when_the_cycle_escalates():
    """In human_only nothing runs: the card proposes isolate_vm and its reason names the
    restore the model proposed."""
    conn = Recorder()
    agent_ = _agent(conn, autonomy=AutonomyConfig(default="human_only"))
    _respond(agent_, _sudo(), _decision("no_action"))
    final = _respond(agent_, _brute_force(), _decision("restore_from_backup"))
    assert conn.writes() == [] and final["action"] == "isolate_vm"
    card = next(c for c in _cards() if c["action"] == "isolate_vm")
    assert "restore_from_backup" in card["reason"]
    assert not [c for c in _cards() if c["action"] == "restore_from_backup"]


# ── Through the graph: the incident keeps the facts; the mode applies ────────────────────

def _respond(agent_, signal, resp):
    with patch("litellm.completion", return_value=resp), \
            patch("glorfindel.detectors.detector_for", return_value=LogAnalytics(fail=False)):
        return agent_.respond(signal)


def test_human_only_runs_nothing_and_the_card_proposes_isolate_vm():
    """The sudo, then the brute force seen succeed, on the same VM in human_only: nothing is
    written; the card proposes isolate_vm and says the floor."""
    conn = Recorder()
    agent_ = _agent(conn, autonomy=AutonomyConfig(default="human_only"))
    _respond(agent_, _sudo(), _decision("snapshot"))
    final = _respond(agent_, _brute_force(), _decision("block_suspicious_ip"))
    assert conn.writes() == []
    assert final["action"] == "isolate_vm" and final["escalate"] is True and final["mode_hold"]
    assert sorted(final["incident"]["confirmed"]) == sorted(
        [agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE])
    card = next(c for c in _cards() if c["action"] == "isolate_vm")
    assert card["escalation_type"] == agent.FLOOR_TYPE           # the floor's, whatever the mode
    assert "Plancher déterministe (B3a)" in card["reason"]


def test_non_disruptive_isolates_and_the_compromise_card_says_the_floor():
    """The same set-up in non_disruptive: the model's block runs as its gates judged it, the
    isolation does not — the floor's card proposes it — and the compromise's card (COR1) says
    the floor."""
    conn = Recorder()
    agent_ = _agent(conn, autonomy=AutonomyConfig(default="non_disruptive"))
    _respond(agent_, _sudo(), _decision("no_action"))
    final = _respond(agent_, _brute_force(), _decision("block_suspicious_ip"))
    assert final["action"] == "block_suspicious_ip" and final["escalate"] is False
    assert conn.writes() == ["block_suspicious_ip"]
    card = next(c for c in _cards() if c["escalation_type"] == "account_compromised")
    assert "block_suspicious_ip" in card["reason"] and "Plancher déterministe (B3a)" in card["reason"]
    [floor] = [c for c in _cards() if c["escalation_type"] == agent.FLOOR_TYPE]
    assert floor["action"] == "isolate_vm" and floor["reason"] == final["floor"]


def test_two_vms_through_the_graph_keep_the_models_block():
    """Root on one VM, the brute force seen succeed on another: two incidents, no floor."""
    conn = Recorder()
    agent_ = _agent(conn, autonomy=AutonomyConfig(default="non_disruptive"))
    _respond(agent_, _sudo(OTHER), _decision("no_action"))
    final = _respond(agent_, _brute_force(RID), _decision("block_suspicious_ip"))
    assert final["action"] == "block_suspicious_ip" and final["floor"] == ""
    assert conn.writes() == ["block_suspicious_ip"]


def test_the_registry_keeps_what_was_confirmed(tmp_path):
    """`confirm` adds to the VM's active incident, once; no active incident, nothing; a row
    written before B3a (no `confirmed`) still reads — and one written before SEC-E (no date) holds
    no live fact."""
    from glorfindel.incidents import live_facts
    reg = IncidentRegistry(path=tmp_path / "inc.jsonl")
    assert reg.confirm(RID, [agent.ROOT_ELEVATION]) is None
    reg.get_or_create(RID, "T1548.003")
    reg.confirm(RID, [agent.ROOT_ELEVATION])
    reg.confirm(RID, [agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE])
    assert reg.get_active(RID).confirmed == [agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE]
    assert live_facts(reg.get_active(RID)) == [agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE]
    assert reg.get_active(OTHER) is None
    row = json.loads((tmp_path / "inc.jsonl").read_text())
    row.pop("confirmed_at")
    (tmp_path / "inc.jsonl").write_text(json.dumps(row) + "\n")
    assert live_facts(reg.get_active(RID)) == []
    row.pop("confirmed")
    (tmp_path / "inc.jsonl").write_text(json.dumps(row) + "\n")
    assert reg.get_active(RID).confirmed == []


def test_confirm_facts_on_a_resolved_attack_started(tmp_path):
    """respond mode: an attack_started resolved by poll_detection confirms what the
    detection found, after load_context opened the incident."""
    reg = IncidentRegistry(path=tmp_path / "inc.jsonl")
    inc = reg.get_or_create(RID, "T1548.003")
    from dataclasses import asdict
    state = {"signal": _sudo(), "incident": asdict(inc)}
    out = agent.confirm_facts(state, incidents=reg)
    assert out["incident"]["confirmed"] == [agent.ROOT_ELEVATION]
    # Unresolved (still an attack_started), or no incident: unchanged.
    same = {"signal": {**_sudo(), "event": "attack_started"}, "incident": asdict(inc)}
    assert agent.confirm_facts(same, incidents=reg) is same
    alone = {"signal": _sudo(), "incident": None}
    assert agent.confirm_facts(alone, incidents=reg) is alone


# ── SEC-E: the facts — a TTL of their own, absolute; forgotten at a release ──────────────

def _both(reg: IncidentRegistry, rid: str = RID) -> None:
    reg.get_or_create(rid, "T1548.003")
    reg.confirm(rid, [agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE])


def _age(reg_path: Path, seconds: float) -> None:
    """Every fact of the file dated `seconds` earlier (a clock gone by)."""
    from datetime import datetime, timedelta
    rows = [json.loads(x) for x in reg_path.read_text().splitlines() if x.strip()]
    for row in rows:
        row["confirmed_at"] = {f: (datetime.fromisoformat(at) - timedelta(seconds=seconds)).isoformat()
                               for f, at in row.get("confirmed_at", {}).items()}
    reg_path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_a_fact_counts_within_its_ttl_never_prolonged_by_the_signals_of_the_vm(tmp_path):
    """The incident lives on (each signal of the VM prolongs it), its facts do not: past
    FACT_TTL_S from their confirmation, the floor no longer plays. Confirmed again while live, a
    fact keeps its date; once expired, a new confirmation dates it anew."""
    from glorfindel.incidents import FACT_TTL_S, live_facts
    path = tmp_path / "inc.jsonl"
    reg = IncidentRegistry(path=path)
    _both(reg)
    first = dict(reg.get_active(RID).confirmed_at)
    reg.confirm(RID, [agent.ROOT_ELEVATION])
    assert reg.get_active(RID).confirmed_at == first            # confirmed again: not prolonged
    _age(path, FACT_TTL_S + 1)
    reg.get_or_create(RID, "T1110.001")                         # a signal: the incident lives on
    from dataclasses import asdict
    inc = asdict(reg.get_active(RID))
    assert inc["state"] == "active" and live_facts(inc) == []
    out, _ = _decide(_sudo(), _decision("no_action"), inc)
    assert out["floor"] == "" and out["action"] != "isolate_vm"
    reg.confirm(RID, [agent.ROOT_ELEVATION])                    # confirmed anew: dated anew
    assert live_facts(reg.get_active(RID)) == [agent.ROOT_ELEVATION]


def test_a_held_detection_never_prolongs_the_incident(tmp_path):
    """The decision queue writes a held detection's facts (B3a) without a signal of the incident:
    neither its last signal nor its count move."""
    from glorfindel import decision_queue as dq
    reg = IncidentRegistry(path=tmp_path / "inc.jsonl")
    reg.get_or_create(RID, "T1110.001")
    before = reg.get_active(RID)
    dq.keep_facts(_sudo(), reg)
    after = reg.get_active(RID)
    assert after.confirmed == [agent.ROOT_ELEVATION]
    assert (after.last_signal_at, after.signals_count) == (before.last_signal_at, before.signals_count)
    # No incident at all: one opened for the facts, once.
    dq.keep_facts(_sudo(OTHER), reg)
    dq.keep_facts(_sudo(OTHER), reg)
    assert reg.get_active(OTHER).signals_count == 1 and reg.get_active(OTHER).confirmed == [agent.ROOT_ELEVATION]


def test_the_facts_are_forgotten_at_a_release(tmp_path):
    """`forget_facts`: whatever the case of the id, every incident of the VM, nothing else."""
    reg = IncidentRegistry(path=tmp_path / "inc.jsonl")
    _both(reg)
    _both(reg, OTHER)
    assert reg.forget_facts(RID.upper() + "/") == 1
    assert reg.get_active(RID).confirmed == [] and reg.get_active(RID).state == "active"
    assert reg.get_active(OTHER).confirmed != []


def test_the_watch_forgets_the_facts_when_it_releases(tmp_path):
    """The release after a restore (execute_action): released whole, the facts go; in part, they
    stay."""
    reg = IncidentRegistry(path=tmp_path / "inc.jsonl")
    _both(reg)
    state = {"signal": {**_sudo(), "event": "recovery_complete"}, "action": "release_isolation",
             "incident": None}
    partial = MagicMock()
    partial.release_isolation.return_value = {"status": "release_partial", "failed": ["x"]}
    agent.execute_action(state, connector=partial, incidents=reg)
    assert reg.get_active(RID).confirmed != []
    agent.execute_action(state, connector=Recorder(), incidents=reg)
    assert reg.get_active(RID).confirmed == []


def test_a_release_the_model_chose_on_a_detection_keeps_the_facts(tmp_path):
    """A release the model chose on a detection (not the release after a restore): the facts of a
    compromise stay — only a human's release, or the watch's after a restore, forgets them."""
    reg = IncidentRegistry(path=tmp_path / "inc.jsonl")
    _both(reg)
    state = {"signal": _sudo(), "action": "release_isolation", "incident": None}
    agent.execute_action(state, connector=Recorder(), incidents=reg)
    assert set(reg.get_active(RID).confirmed) == {agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE}


def test_a_human_release_forgets_the_facts(monkeypatch):
    """`glorfindel release` (the console's and the bot's too), `reset` and a request of the queue
    (glorfindel/gestures.py): the human judged the VM — its next detection is judged anew."""
    from click.testing import CliRunner
    from types import SimpleNamespace
    from glorfindel import cli, gestures
    reg = IncidentRegistry()                       # the watch's, redirected by the conftest
    monkeypatch.setattr(cli, "_record_manual_action", lambda *a, **k: None)
    monkeypatch.setattr("glorfindel.gestures.release_needed", lambda c, rid: True)

    def connector(status):
        return lambda dry_run=False: SimpleNamespace(
            dry_run=dry_run, release_isolation=lambda rid: {"status": status, "failed": []})
    for status, kept in (("release_partial", True), ("released", False)):
        _both(reg)
        monkeypatch.setattr("glorfindel.actions.AzureConnector", connector(status))
        CliRunner().invoke(cli.cli, ["release", RID, "--yes"])
        assert bool(reg.get_active(RID).confirmed) is kept, status
    _both(reg)
    gestures.reset_apply(connector("released")(), RID, [{"resource_id": RID}], [])
    assert reg.get_active(RID).confirmed == []
    _both(reg)
    gestures.released(RID)
    assert reg.get_active(RID).confirmed == []


# ── The harness (scripts/llm_smoke.py): it runs the whole decide ─────────────────────────

@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("llm_smoke_b3a", SMOKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _harness_runs(smoke, sc: dict, row: dict, incident: dict | None, runs: int = 3) -> list[str]:
    """The harness's own loop for one case (its `_state`, its call to decide, its judge), the
    model patched to answer block_suspicious_ip every time."""
    verdicts = []
    for _ in range(runs):
        state = smoke._state(sc["ttp"], {"first_result_row": row}, sc.get("past"), incident)
        with patch("litellm.completion", return_value=_decision("block_suspicious_ip")):
            out = agent.decide(state, model="anthropic/claude-test",
                               autonomy_override="non_disruptive")
        good, _ = smoke._judge(sc, out["action"], bool(out.get("escalate")), bool(out.get("floor")))
        verdicts.append((out["action"], good))
    return verdicts


def test_the_harness_paired_case_as_written_is_neighbouring_signals(smoke):
    """The paired case 2/2 names a sudo in its incident but no login after the brute force
    (failures only, no COR1 mark, no confirmed facts): the floor does not play there."""
    sc = next(s for s in smoke.SCENARIOS if s.get("pair") and s.get("incident"))
    assert "Correlation" not in sc["row"] and "confirmed" not in sc["incident"]
    assert _harness_runs(smoke, sc, sc["row"], sc["incident"]) == [("block_suspicious_ip", False)] * 3


def test_the_harness_floor_case_is_the_paired_case_seen_succeed(smoke):
    """The harness's floor case (B3a): the brute force of the pair 2/2, marked by COR1, its
    incident holding the confirmed sudo — nothing else differs."""
    after = next(s for s in smoke.SCENARIOS if s.get("pair") and s.get("incident"))
    floor = next(s for s in smoke.SCENARIOS if s["kind"] == "floor")
    assert floor["ttp"] == after["ttp"] and floor["expected"] == {"isolate_vm"}
    assert {k: v for k, v in floor["row"].items()
            if k not in ("Correlation", "SuccessfulLogins")} == after["row"]
    assert floor["row"]["Correlation"] == "ssh-login-after-brute-force"
    assert {k: v for k, v in floor["incident"].items()
            if k not in ("confirmed", "confirmed_at")} == after["incident"]
    assert floor["incident"]["confirmed"] == [agent.ROOT_ELEVATION]


@pytest.mark.parametrize("answer", ["block_suspicious_ip", "no_action", "snapshot"])
def test_the_harness_floor_case_passes_three_times_in_three(smoke, answer, capsys):
    """The harness end to end (`_run_one`, its decide, its judge), the model patched to answer
    the same wrong action every time: 3/3 good — the floor, inside decide, proposes isolate_vm
    (SEC-E: on a card, never run by the floor); the model's own action as its gates judged it."""
    with patch("litellm.completion", return_value=_decision(answer)):
        res = smoke._run_one("anthropic/claude-test", 3, {"floor"})
    [case] = res["cases"]
    assert [(s["good"], s["floor"]) for s in case["slots"]] == [(True, True)] * 3
    shown = "isolate_vm" if answer == "no_action" else answer
    assert [s["action"] for s in case["slots"]] == [shown] * 3
    sc = next(s for s in smoke.SCENARIOS if s["kind"] == "floor")
    runs = [(a, g) for a, g in _harness_runs(smoke, sc, sc["row"], sc["incident"])]
    assert all(good for _a, good in runs)
