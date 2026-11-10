"""DRN1 (#677): the session drain under the quarantine — waited what it waited, then read on Azure.

On the bench, 09/11, the drain of an autonomous isolation ran 302 s on Azure (Started, Accepted,
Succeeded); the watch waited 300 s, read an empty output, and said the isolation unverified while
the NSG held and the cut succeeded 2 s later. Now the VM's worker still waits 300 s, then the drain
is pending; the isolation keeps its NSG verdict, and the reassertion's pass reads the Run Command's
status again: one card « coupure en attente » while it runs, closed once the sessions are cut, or
replaced by a card that says « coupure refusée », « sessions restées ouvertes » or « coupure jamais
aboutie ». The restore's neutralization reads its status the same way.

On the in-memory Azure (tests/unit/fake_azure.py: a Run Command held running, then ended by the
test): no cloud call, no model call.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from azure.core.exceptions import HttpResponseError

from glorfindel import actions, config, drain_watch, escalations, readiness
from glorfindel.actions import AzureConnector, _load_isolation_state
from glorfindel.agent import _platform_note, verify_action
from glorfindel.config import AutonomyConfig
from glorfindel.providers.azure import run_command
from glorfindel.reassert import reassert_pass
from glorfindel.response.policy import drain_case, isolation_verdict

from .fake_azure import FakeAzure, _error, vm_id

_ACT = AutonomyConfig(default="non_disruptive")
_WEB = vm_id("rg-app1", "web")


@pytest.fixture(autouse=True)
def _no_drain_followed():
    """The drains the process follows are a module's (the watch's): none from another test."""
    run_command._FOLLOWED.clear()
    yield
    run_command._FOLLOWED.clear()


@pytest.fixture
def azure(tmp_path, monkeypatch):
    """web on its own NSG, isolation by rules; its Run Commands held running (the quarantine of
    09/11), the real drain."""
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text("isolation:\n  quarantine_nsg: false\n")
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [cfg])
    f = FakeAzure()
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", None)
    nsg = f.add_nsg("rg-app1", "nsg-web")
    f.add_vm("rg-app1", "web", [{"rg": "rg-app1", "name": "web-nic", "ips": ["10.0.0.4"],
                                 "subnet": subnet, "nsg": nsg}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    readiness.record_assessment(readiness._verdict("web", []), _WEB)
    f.hold_run_commands = True
    return f, c


def _drain_cards(kind: str | None = None) -> list[dict]:
    return [e for e in escalations.pending() if e["signal_id"].startswith("reassert-drain-")
            and (kind is None or e["escalation_type"] == kind)]


def _cycle(c, out: dict) -> dict:
    """The agent's verify_action on the isolation it just ran."""
    state = {"action": "isolate_vm", "signal": {"resource_id": _WEB}, "outcome": {**out, "executed": True},
             "escalation_reason": ""}
    return verify_action(state, connector=c)


# ── the first wait: what it was ────────────────────────────────────────────────────────────────

def test_the_worker_waits_for_the_drain_what_it_waited_before():
    """« La watch n'est pas bloquée plus longtemps qu'aujourd'hui sur une VM » : 300 s, then pending."""
    from tests.unit.test_glorfindel import _RID
    c = AzureConnector(dry_run=False)
    c._compute = MagicMock()
    c._compute.virtual_machines.get.return_value.storage_profile.os_disk.os_type = "Linux"
    poller = c._compute.virtual_machines.begin_run_command.return_value
    poller.done.return_value = False
    poller.status.return_value = "InProgress"
    out = c.drain_connections(_RID)
    assert poller.result.call_args.kwargs == {"timeout": 300}
    assert run_command.DRAIN_FIRST_WAIT_S == 300
    assert out["status"] == "pending" and out["azure_status"] == "InProgress" and out["waited_s"] == 300
    assert "illisible" not in str(out)


def test_a_poll_read_at_the_deadline_is_never_an_output():
    """`result(timeout)` at its deadline returns the last poll (no output): the bench's « sortie de
    Run Command illisible ». Not done, it is never read."""
    poller = MagicMock()
    poller.result.return_value = MagicMock(value=None)
    poller.done.return_value = False
    assert run_command.wait(poller, 5) == (False, None)


# ── on the in-memory Azure ─────────────────────────────────────────────────────────────────────

def test_a_cut_that_ends_after_its_first_wait_gives_a_verified_isolation(azure):
    f, c = azure
    out = c.isolate_vm(_WEB)
    assert out["drain"]["status"] == "pending" and out["drain"]["azure_status"] == "InProgress"
    assert _load_isolation_state(_WEB)["drain"]["status"] == "pending"
    cycle = _cycle(c, out)
    assert cycle["outcome"]["verified"] is True and cycle["escalate"] is False
    assert cycle["outcome"]["drain_case"] == "pending"
    reassert_pass(c, _ACT)
    [card] = _drain_cards()
    assert card["escalation_type"] == "drain_pending" and card["action"] == "review_drain"
    assert card["reason"].startswith("Coupure en attente sur web") and card["drain_case"] == "pending"
    reassert_pass(c, _ACT)
    assert [e["occurrences"] for e in _drain_cards()] == [1]          # one card, not one a minute
    f.end_run_commands()
    report = reassert_pass(c, _ACT)
    assert not _drain_cards() and not [e for e in escalations.pending() if e["escalation_type"] == "verification_failed"]
    [closed] = [e for e in escalations.all_escalations() if e["id"] == card["id"]]
    assert closed["status"] == "resolved" and "isolement vérifié" in closed["resolution"]
    assert _load_isolation_state(_WEB)["drain"]["status"] == "drained"
    assert any(r["kind"] == "drain" and r["outcome"] == "drained" for r in report)
    assert c.follow_drain(_WEB) is None                               # forgotten once it ended


def test_a_cut_that_never_ends_is_said_so(azure, monkeypatch):
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    [pending] = _drain_cards("drain_pending")
    monkeypatch.setattr(drain_watch, "DRAIN_DEADLINE_S", 0.0)
    reassert_pass(c, _ACT)
    [card] = _drain_cards()
    assert card["escalation_type"] == "verification_failed" and card["action"] == "isolate_vm"
    assert "coupure jamais aboutie" in card["reason"] and "toujours en cours sur Azure" in card["reason"]
    assert card["drain_case"] == "never"
    [closed] = [e for e in escalations.all_escalations() if e["id"] == pending["id"]]
    assert closed["status"] == "resolved" and "jamais aboutie" in closed["resolution"]
    drain = _load_isolation_state(_WEB)["drain"]
    assert drain["never"] is True and drain_case(drain) == "never"
    assert c.follow_drain(_WEB) is None                               # given up
    reassert_pass(c, _ACT)
    assert len(_drain_cards()) == 1                                   # said once


def test_the_watch_restarted_during_the_cut_says_it_was_not_read(azure):
    """A restart loses the poller: never read as a cut — said, the activity log to read."""
    f, c = azure
    c.isolate_vm(_WEB)
    run_command._FOLLOWED.clear()
    reassert_pass(c, _ACT)
    [card] = _drain_cards()
    assert card["escalation_type"] == "verification_failed" and "coupure jamais aboutie" in card["reason"]
    assert "redémarrée" in card["reason"] and "journal d'activité" in card["reason"]


def test_a_cut_refused_is_said_as_refused(azure):
    f, c = azure

    def chaos(op, phase, write):
        if op == "vm.run_command" and phase == "before":
            raise _error(HttpResponseError, 403, "(AuthorizationFailed) the client does not have "
                                                 "authorization to perform action runCommand/action")
    f.chaos = chaos
    out = c.isolate_vm(_WEB)
    assert out["drain"]["refused"] is True
    cycle = _cycle(c, out)
    assert cycle["outcome"]["verified"] is False and cycle["outcome"]["drain_case"] == "refused"
    assert "coupure refusée : " in cycle["escalation_reason"] and "Session Drain" in cycle["escalation_reason"]
    reassert_pass(c, _ACT)
    assert not _drain_cards()                                         # said by the cycle's own card


def test_sessions_left_open_are_said_as_such():
    from tests.unit.test_glorfindel import _drain_connector, _RID
    out = _drain_connector("glorfindel-drain-remaining=2").drain_connections(_RID)
    verdict = isolation_verdict({"verified": True}, {"drain": out})
    assert verdict["verified"] is False and verdict["drain_case"] == "open"
    assert verdict["error"].startswith("sessions restées ouvertes : ") and "2 connexion(s)" in verdict["error"]
    windows = isolation_verdict({"verified": True}, {"drain": {"status": "unsupported", "note": "Windows"}})
    assert windows["error"].startswith("sessions restées ouvertes : ") and "non coupées" in windows["error"]


def test_a_cut_that_fails_on_azure_after_its_first_wait_says_the_sessions_stayed_open(azure):
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    f.end_run_commands(error=_error(HttpResponseError, 409, "(Conflict) The VM agent is not responding"))
    reassert_pass(c, _ACT)
    [card] = _drain_cards()
    assert card["escalation_type"] == "verification_failed" and card["drain_case"] == "open"
    assert "sessions restées ouvertes : " in card["reason"] and "en échec sur Azure" in card["reason"]
    assert "Conflict" in card["reason"]


def test_a_failure_after_the_first_wait_counts_as_a_containment_that_did_not_hold(azure):
    """BL1 (analysis/containment.py): the cycle verified on the NSG, then the cut that failed —
    never counted « contenu seul »."""
    from analysis.containment import not_holding
    f, c = azure
    c.isolate_vm(_WEB)
    f.end_run_commands(error=_error(HttpResponseError, 409, "(Conflict) agent"))
    reassert_pass(c, _ACT)
    assert not_holding(_WEB, 0.0, 4e9, escalations.all_escalations()) is not None


def test_a_pending_card_never_counts_against_the_containment(azure):
    from analysis.containment import not_holding
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    f.end_run_commands()
    reassert_pass(c, _ACT)
    assert not_holding(_WEB, 0.0, 4e9, escalations.all_escalations()) is None


def test_a_vm_released_while_its_cut_waits_closes_the_card(azure):
    f, c = azure
    c.isolate_vm(_WEB)
    reassert_pass(c, _ACT)
    assert _drain_cards("drain_pending")
    c.release_isolation(_WEB)
    report = reassert_pass(c, _ACT)
    assert not _drain_cards()
    assert any(r["kind"] == "drain" and r["outcome"] == "closed" for r in report)


def test_the_drain_card_never_folds_into_another_card_of_the_reassertion(azure, monkeypatch):
    """A rule of the isolation gone (the reassertion's verification_failed card on the VM) and the
    cut that never ended: two cards, each its own reason."""
    f, c = azure
    c.isolate_vm(_WEB)
    gone = escalations.record(signal_id="reassert-web-12345678", resource_id=_WEB, action="isolate_vm",
                              escalation_type="verification_failed", reason="les règles ont disparu")
    monkeypatch.setattr(drain_watch, "DRAIN_DEADLINE_S", 0.0)
    reassert_pass(c, _ACT)
    [other] = [e for e in escalations.pending() if e["id"] == gone]
    assert other["reason"] == "les règles ont disparu" and other.get("occurrences", 1) == 1
    assert len(_drain_cards("verification_failed")) == 1


def test_a_dry_run_follows_nothing(azure):
    f, c = azure
    c.isolate_vm(_WEB)
    c.dry_run = True
    report: list = []
    drain_watch.follow_drains(c, report)
    assert report == [] and not _drain_cards()


# ── what the operator reads ────────────────────────────────────────────────────────────────────

def test_the_autonomous_isolation_s_notification_says_the_cut_is_pending():
    note = _platform_note({"drain": {"status": "pending", "note": "coupure en attente : Run Command…"}})
    assert note.startswith("coupure en attente")
    assert _platform_note({"drain": {"status": "drained"}}) == ""


def test_glorfindel_list_says_the_cut_is_pending():
    from glorfindel.cli import _state_warnings
    out = _state_warnings({"drain": {"status": "pending", "asked_at": "2026-11-09T16:43:03+00:00"}},
                          "release_failed")
    assert any(w.startswith("session cut pending") for w in out)


# ── the restore's neutralization: the same reading ─────────────────────────────────────────────

def test_the_neutralization_still_running_reads_its_status_on_azure(azure):
    f, c = azure
    vm = f.compute.virtual_machines.get("rg-app1", "web")
    out = c._neutralize_run_command("rg-app1", "web", vm)
    assert out["run_command_neutralized"] is False and out["run_command_pending"] is True
    assert out["run_command_status"] == "InProgress" and "statut relu : InProgress" in out["run_command_error"]
    assert "run_command_refused" not in out
    f.hold_run_commands = False
    assert c._neutralize_run_command("rg-app1", "web", vm)["run_command_neutralized"] is True


def test_the_neutralization_waits_what_it_waited_before():
    assert run_command.NEUTRALIZE_WAIT_S == 600


def test_actions_facade_reads_the_new_module():
    assert actions.DrainFollowMixin is run_command.DrainFollowMixin
