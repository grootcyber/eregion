"""REC1 (#668): the watch reads on Azure the recovery of a VM it isolated, and lifts the isolation
through its own recovery_complete — never from a file another host wrote, never from the model.

On the in-memory Azure (fake_azure.FakeAzure: the vault's restore jobs, the VM's recovery points,
its power state, what Run Command v1 last said): a restore run from the workstation — its
neutralization by the real code, then the vault's job — makes the watch lift the isolation, once,
without the reassertion putting it back; a point not before the incident, a job that failed, a VM
that does not run lift nothing, and say so on one card. The machine at the end draws sequences of
isolations, points, restores, commands and passes: never a recovery_complete without a recovery
proven on Azure (R1), never two for one job nor two cards for one job and one reason (R2).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, event, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule, run_state_machine_as_test

from glorfindel import escalations, recovery_watch, reassert
from glorfindel.actions import AzureConnector, _load_isolation_state, active_isolations

from .fake_azure import FakeAzure, key, open_flows

VAULT = "rsv-test"
_NOW = time.time()


def _t(minutes: float) -> datetime:
    return datetime.fromtimestamp(_NOW + minutes * 60, tz=timezone.utc)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "s")
    monkeypatch.setenv("GLORFINDEL_BACKUP_VAULT", VAULT)
    monkeypatch.setattr(escalations, "_notify", lambda esc: None)


def _world(windows: bool = False):
    f = FakeAzure()
    nsg = f.add_nsg("rg-app", "nsg-web")
    sub = f.add_subnet("rg-net", "vnet", "app", nsg)
    vm = f.add_vm("rg-app", "web", [{"rg": "rg-app", "name": "web-nic", "ips": ["10.0.1.4"],
                                     "subnet": sub, "nsg": nsg}], os_type="Windows" if windows else "Linux")
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute, c._backup = f.network, f.compute, f.backup
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    return f, c, vm


def _isolated(f, c, vm) -> float:
    """The VM isolated by the watch; its isolation's moment."""
    c.isolate_vm(vm)
    return datetime.fromisoformat(_load_isolation_state(vm)["isolated_at"]).timestamp()


def _from_the_workstation(f, c, vm, point="p-clean", status="Completed", power="running",
                          neutralize=True, start=20, end=40, bag="time"):
    """What `glorfindel restore` does from the workstation: neutralize Run Command (the real
    code, on the fake), then the vault restores the point."""
    if neutralize:
        assert c._neutralize_run_command("rg-app", "web", f.compute.virtual_machines.get("rg-app", "web")) == {
            "run_command_neutralized": True}
    return f.restore(vm, point, _t(start), _t(end) if end is not None else None, status=status, bag=bag,
                     power=power)


def _pass(c, minutes: float = 60) -> tuple[list[dict], list[dict]]:
    out: list[dict] = []
    report = recovery_watch.recovery_pass(c, out.append, now=_NOW + minutes * 60)
    return out, report


def _mine() -> list[dict]:
    return [e for e in escalations.pending() if str(e.get("signal_id") or "").startswith("recovery-")]


def _points(f, vm):
    f.add_point(vm, "p-old", _t(-24 * 60))
    f.add_point(vm, "p-clean", _t(-60))
    f.add_point(vm, "p-during", _t(10))      # taken after the isolation: during the incident


# ── the restore proven: the release follows, once ─────────────────────────────────────────────

def test_a_restore_from_the_workstation_lifts_the_isolation_once_without_reassertion(tmp_path, monkeypatch):
    """Fini quand (1): the watch sees the restore on Azure, its graph releases (non_disruptive),
    the reassertion puts nothing back, and a second pass emits nothing."""
    from glorfindel.agent import _build_graph
    from glorfindel.config import AutonomyConfig
    from glorfindel.memory import CycleMemory
    from .test_agent_nodes import _mock_llm_response

    monkeypatch.chdir(tmp_path)
    f, c, vm = _world()
    design = open_flows(f.snapshot(), vm)
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    signals, report = _pass(c)
    assert [r["outcome"] for r in report] == ["emitted"] and len(signals) == 1
    sig = signals[0]
    assert sig["event"] == "recovery_complete" and sig["resource_id"] == vm
    assert sig["raw_signal"]["run_command_neutralized"] is True
    assert sig["raw_signal"]["recovery_point_time"] == _t(-60).isoformat()

    graph = _build_graph(CycleMemory(path=tmp_path / "cycles"), c, "claude-test",
                         autonomy=AutonomyConfig(default="non_disruptive"))
    state = {"signal": sig, "past_cycles": [], "incident": None, "dry_run": False, "reasoning": "",
             "confidence": 0.0, "action": "", "reversible": True, "explanation": "", "escalate": False,
             "escalation_reason": "", "suggested_steps": [], "outcome": None}
    with patch("litellm.completion") as llm:
        llm.return_value = _mock_llm_response("release_isolation")
        final = graph.invoke(state)
    assert final["action"] == "release_isolation" and final["escalate"] is False
    assert final["outcome"]["status"] != "escalated"
    assert _load_isolation_state(vm) is None and active_isolations() == []
    assert open_flows(f.snapshot(), vm) == design

    writes = len(f.journal)
    reassert.reassert_pass(c, AutonomyConfig(default="non_disruptive"))
    assert len(f.journal) == writes, "the reassertion wrote after the release"
    assert open_flows(f.snapshot(), vm) == design
    again, report = _pass(c, minutes=70)
    assert again == [] and report == [] and _mine() == []


def test_twice_the_same_pass_emits_once_while_the_vm_is_still_isolated():
    """Before its queue releases it, the VM is still isolated: a second pass on the same job emits
    nothing (one record per job, written before the signal leaves)."""
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    first, _ = _pass(c, 60)
    second, report = _pass(c, 61)
    assert len(first) == 1 and second == [] and report == []
    assert recovery_watch.seen(vm, f.jobs[0]["name"]).get("emitted")


def test_the_signal_carries_what_the_workstation_gives_and_nothing_more():
    """The model reads the same recovery_complete as on the workstation (cli._build_recovery_signal):
    same fields, same raw_signal keys — no new text before the model (_build_user_message unchanged)."""
    from glorfindel.cli import _build_recovery_signal
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    mine = _pass(c)[0][0]
    theirs = _build_recovery_signal(vm, {"recovery_point_time": "x", "run_command_neutralized": True}, 1200)
    assert set(mine) == set(theirs)
    assert set(mine["raw_signal"]) == set(theirs["raw_signal"])
    assert set(mine["context"]) == set(theirs["context"])
    from glorfindel.signal_origin import vouched
    assert vouched(mine)


def test_in_human_only_the_release_is_a_card(tmp_path, monkeypatch):
    """« Autonome dans les modes qui la permettent, une carte sinon » : the graph's mode."""
    from glorfindel.agent import _build_graph
    from glorfindel.config import AutonomyConfig
    from glorfindel.memory import CycleMemory
    from .test_agent_nodes import _mock_llm_response

    monkeypatch.chdir(tmp_path)
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    sig = _pass(c)[0][0]
    graph = _build_graph(CycleMemory(path=tmp_path / "cycles"), c, "claude-test",
                         autonomy=AutonomyConfig(default="human_only"))
    with patch("litellm.completion") as llm:
        llm.return_value = _mock_llm_response("release_isolation")
        final = graph.invoke({"signal": sig, "past_cycles": [], "incident": None, "dry_run": False,
                              "reasoning": "", "confidence": 0.0, "action": "", "reversible": True,
                              "explanation": "", "escalate": False, "escalation_reason": "",
                              "suggested_steps": [], "outcome": None})
    assert final["escalate"] is True and final["outcome"]["escalation_type"] == "mode_hold"
    assert _load_isolation_state(vm) is not None


# ── nothing proven: a card, no release ───────────────────────────────────────────────────────

def test_a_point_after_the_incident_lifts_nothing_and_says_it_once():
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm, point="p-during")
    signals, report = _pass(c)
    assert signals == [] and [r["outcome"] for r in report] == ["card"]
    assert len(_mine()) == 1 and "n'est pas antérieur" in _mine()[0]["reason"]
    assert _mine()[0]["escalation_type"] == "release_hold" and _mine()[0]["action"] == "review_recovery"
    again, report = _pass(c, 90)
    assert again == [] and report == [] and len(_mine()) == 1
    assert _load_isolation_state(vm) is not None


@pytest.mark.parametrize("status", ["Failed", "Cancelled", "CompletedWithWarnings"])
def test_a_job_that_did_not_succeed_lifts_nothing(status):
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm, status=status)
    signals, report = _pass(c)
    assert signals == [] and [r["outcome"] for r in report] == ["card"]
    assert status in _mine()[0]["reason"] and "aucune levée" in _mine()[0]["reason"]
    assert _pass(c, 90) == ([], []) and len(_mine()) == 1


def test_a_stopped_vm_lifts_nothing_says_it_once_then_lifts_once_started():
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm, power="deallocated")
    signals, report = _pass(c, 45)                          # 5 min after the job: it may be starting
    assert signals == [] and _mine() == [] and report[0]["outcome"] == "wait"
    signals, report = _pass(c, 60)
    assert signals == [] and [r["outcome"] for r in report] == ["card"]
    assert "ne tourne pas" in _mine()[0]["reason"]
    assert _pass(c, 70) == ([], []) and len(_mine()) == 1
    # Started: the restored disk boots and replays the VM model's last command (the harmless one).
    v = f.vms[key(vm)]
    v["power"], v["said"] = "running", {"message": v["last_output"], "time": _t(71)}
    signals, report = _pass(c, 80)
    assert len(signals) == 1 and [r["outcome"] for r in report] == ["emitted"]
    assert _mine() == [], "the stopped card closed once the recovery is proven"


def test_a_point_the_job_does_not_name_lifts_nothing():
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm, bag="none")
    signals, _ = _pass(c)
    assert signals == [] and "ne se lit pas" in _mine()[0]["reason"]


def test_a_point_named_by_its_id_is_read_from_the_vault():
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm, bag="id")
    assert len(_pass(c)[0]) == 1
    f2, c2, vm2 = _world()
    _isolated(f2, c2, vm2)
    _points(f2, vm2)
    _from_the_workstation(f2, c2, vm2, point="p-during", bag="id")
    assert _pass(c2)[0] == []


def test_the_first_detection_before_the_isolation_dates_the_incident(monkeypatch):
    """A point between the first detection of the VM's pending card and its isolation was taken
    during the incident: no release (the rule of --before, restore_plan.incident_start)."""
    f, c, vm = _world()
    escalations.record(signal_id="det-1", resource_id=vm, action="isolate_vm", escalation_type="mode_hold",
                       reason="ransomware")
    from glorfindel import restore_plan
    first = datetime.fromisoformat(escalations.pending()[0]["first_seen"]).timestamp()
    # Isolated 30 min after the card: what an approval in human_only does.
    _isolated(f, c, vm)
    state = _load_isolation_state(vm)
    from glorfindel.actions import _save_isolation_state
    _save_isolation_state(vm, {**state, "isolated_at": datetime.fromtimestamp(first + 1800, tz=timezone.utc).isoformat()})
    f.add_point(vm, "p-between", datetime.fromtimestamp(first + 600, tz=timezone.utc))
    _from_the_workstation(f, c, vm, point="p-between", start=40, end=60)
    start, why = restore_plan.incident_start(vm)
    assert start == first and "première détection" in why
    signals, _ = _pass(c, 80)
    assert signals == [] and "n'est pas antérieur" in _mine()[0]["reason"]


def test_no_job_a_running_job_or_a_job_before_the_isolation_say_nothing():
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    assert _pass(c) == ([], [])
    f.restore(vm, "p-clean", _t(-30), _t(-10))              # before the isolation: another incident's
    assert _pass(c) == ([], [])
    _from_the_workstation(f, c, vm, end=None)               # still running
    assert _pass(c) == ([], []) and _mine() == []


def test_a_homonym_in_another_group_is_never_read():
    f, c, vm = _world()
    other = f.add_vm("rg-other", "web", [{"rg": "rg-other", "name": "web-nic-2", "ips": ["10.0.2.4"],
                                          "subnet": f.subnets[next(iter(f.subnets))]["id"], "nsg": None}])
    _isolated(f, c, vm)
    f.add_point(other, "p-other", _t(-60))
    f.restore(other, "p-other", _t(20), _t(40))
    assert _pass(c) == ([], [])


def test_a_restore_without_the_neutralization_is_released_by_no_one():
    """The drain was the last Run Command: the restored disk replays it, not the harmless one —
    neutralized False, the release precondition holds the release (as on the workstation)."""
    from glorfindel.agent import _apply_release_precondition
    f, c, vm = _world()
    _isolated(f, c, vm)                                     # its drain: the VM model's last command
    _points(f, vm)
    _from_the_workstation(f, c, vm, neutralize=False)
    sig = _pass(c)[0][0]
    assert sig["raw_signal"]["run_command_neutralized"] is False
    d = {"escalate": False, "action": "release_isolation"}
    _apply_release_precondition(d, sig)
    assert d["escalate"] is True and d["held_by"] == "release_precondition"


def test_a_word_of_run_command_from_before_the_restore_proves_nothing():
    """The marker read before the restore's end (written by the guest of the old disk, perhaps):
    the watch waits for the restored disk's word, then, none, says the neutralization unknown."""
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    v = f.vms[key(vm)]
    v["said"] = {"message": v["last_output"], "time": _t(30)}  # before the job's end (40)
    assert _pass(c, 50)[0] == []                            # within the wait: nothing yet
    sig = _pass(c, 60)[0][0]                                # past it: unknown
    assert sig["raw_signal"]["run_command_neutralized"] is None


def test_a_replayable_extension_holds_the_release_and_is_named():
    from glorfindel.agent import _apply_release_precondition
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    f.vms[key(vm)]["extensions"].append(("CustomScript", "Microsoft.Azure.Extensions", "CustomScript"))
    _from_the_workstation(f, c, vm, neutralize=False)
    c._neutralize_run_command("rg-app", "web", f.compute.virtual_machines.get("rg-app", "web"))
    v = f.vms[key(vm)]
    v["said"] = {"message": v["last_output"], "time": _t(41)}
    sig = _pass(c)[0][0]
    assert sig["raw_signal"]["run_command_neutralized"] is False
    assert sig["raw_signal"]["replay_vectors"] == ["extension CustomScript"]
    d = {"escalate": False, "action": "release_isolation"}
    _apply_release_precondition(d, sig)
    assert "CustomScript" in d["escalation_reason"]


def test_a_job_ended_moments_ago_waits_for_the_process_that_restored():
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    signals, report = _pass(c, 43)                          # 3 min after the end: the grace
    assert signals == [] and report[0]["outcome"] == "wait"
    assert len(_pass(c, 46)[0]) == 1


def test_a_restore_claimed_on_this_host_is_left_to_it(monkeypatch):
    from glorfindel import jobs
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm)
    monkeypatch.setattr(jobs, "restore_in_progress", lambda name: "un restore part d'ici")
    assert _pass(c) == ([], [])


def test_without_a_vault_or_an_isolation_nothing_is_read(monkeypatch):
    f, c, vm = _world()
    calls = []
    c.observed_restore = lambda *a, **k: calls.append(a) or {"job": None}
    assert _pass(c) == ([], []) and calls == []             # nothing isolated: no Azure call
    _isolated(f, c, vm)
    monkeypatch.delenv("GLORFINDEL_BACKUP_VAULT")
    assert _pass(c) == ([], []) and calls == []


def test_an_unreadable_vault_is_said_never_a_release():
    f, c, vm = _world()
    _isolated(f, c, vm)

    def refused(*a, **k):
        raise RuntimeError("(AuthorizationFailed) backupJobs/read")
    f.backup.backup_jobs.list = refused
    signals, report = _pass(c)
    assert signals == [] and report[0]["outcome"] == "unreadable" and "AuthorizationFailed" in report[0]["detail"]


def test_the_watch_pass_says_what_it_did_and_never_raises(capsys):
    from glorfindel.cli import _watch_recovery_pass
    f, c, vm = _world()
    _isolated(f, c, vm)
    _points(f, vm)
    _from_the_workstation(f, c, vm, status="Failed")
    out = []
    _watch_recovery_pass(c, out.append)
    assert out == [] and "card" in capsys.readouterr().out

    def boom(*a, **k):
        raise OSError("disque plein")
    with patch.object(recovery_watch, "recovery_pass", boom):
        assert _watch_recovery_pass(c, out.append) == []
    assert "disque plein" in capsys.readouterr().out


def test_a_windows_vm_is_read_the_same_way_and_held_as_on_the_workstation():
    """The word of RunCommandWindows is read like Linux's. But Run Command v1's Windows handler
    (`Microsoft.CPlat.Core` `RunCommandWindows`) is not in `_REPLAY_SAFE_EXTENSIONS` (only
    `runcommandlinux` and v2's handlers): the workstation's restore holds it as a replay vector,
    and the watch the same — the release held, the card naming it. A gap older than REC1, left
    as it is (said in its report)."""
    f, c, vm = _world(windows=True)
    _isolated(f, c, vm)
    _points(f, vm)
    assert c._neutralize_run_command("rg-app", "web", f.compute.virtual_machines.get("rg-app", "web"))[
        "replay_vectors"] == ["extension RunCommandWindows"]
    f.restore(vm, "p-clean", _t(20), _t(40))
    iso = _load_isolation_state(vm)["isolated_at"]
    assert c.observed_restore(vm, iso, vault=VAULT)["run_command"]["neutralized"] is True
    raw = _pass(c)[0][0]["raw_signal"]
    assert raw["run_command_neutralized"] is False and raw["replay_vectors"] == ["extension RunCommandWindows"]


def test_the_bag_and_the_word_are_read_as_azure_writes_them():
    from glorfindel.providers.azure.recovery import _bag_times, _sections
    at = datetime(2026, 11, 9, 14, 5, 7, tzinfo=timezone.utc)
    assert at in _bag_times("11/9/2026 2:05:07 PM")
    assert at in _bag_times("2026-11-09T14:05:07Z")
    assert _bag_times("pas une date") == []
    assert _sections("Enable succeeded: \n[stdout]\nglorfindel: run command neutralized\n\n[stderr]\n") == (
        "glorfindel: run command neutralized", "")
    assert _sections("glorfindel: run command neutralized") == ("glorfindel: run command neutralized", "")
    assert _sections("[stdout]\nx\n[stderr]\nerr") == ("x", "err")


def test_a_dry_run_reads_nothing():
    c = AzureConnector(dry_run=True)
    assert c.observed_restore("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/v",
                              _t(0).isoformat(), vault=VAULT) == {"job": None, "dry_run": True}


def test_a_vm_of_another_subscription_is_never_read():
    from glorfindel.response.policy import WrongSubscriptionError
    f, c, vm = _world()
    with pytest.raises(WrongSubscriptionError):
        c.observed_restore(vm.replace("/subscriptions/s/", "/subscriptions/t/"), _t(0).isoformat(), vault=VAULT)


# ── the machine: R1, R2 ──────────────────────────────────────────────────────────────────────

class RecoveryMachine(RuleBasedStateMachine):
    """Isolations, points, restores (every status, every bag, the VM left on or off), Run Commands
    (the harmless one, an attacker's), starts, passes over time — and, after each pass, the release
    the graph would make (neutralized) or none (held). The oracles are the test's own journal: the
    jobs it created, the moments it isolated, the commands it ran."""

    def __init__(self):
        super().__init__()
        self.minutes = 0.0
        self.emitted: list[tuple[str, str]] = []
        self.iso_at: dict[str, float] = {}            # VM → when the test saw it isolated
        self.jobs: list[dict] = []                    # the test's own record of each restore
        self.last_cmd: dict[str, str] = {}
        # What the VM's word of Run Command is, by the test's journal: what a boot replayed (the
        # VM model's last command then), or None once a command spoke after it.
        self.boot_word: dict[str, str | None] = {}

    @initialize()
    def build(self):
        import shutil
        import tempfile
        from pathlib import Path
        import glorfindel.actions as actions
        self.home = Path(tempfile.mkdtemp())
        actions._ISOLATION_STATE_DIR = self.home / "isolation"
        escalations._STORE = self.home / "escalations.jsonl"
        recovery_watch.RECOVERIES_FILE = self.home / "recoveries.json"
        self._cleanup = lambda: shutil.rmtree(self.home, ignore_errors=True)
        self.f, self.c, vm = _world()
        sub = next(iter(self.f.subnets.values()))["id"]
        other = self.f.add_vm("rg-app", "db", [{"rg": "rg-app", "name": "db-nic", "ips": ["10.0.1.5"],
                                               "subnet": sub, "nsg": None}])
        self.vms = [vm, other]
        # Both isolated, each with a clean point, one just before the incident and one during it:
        # the sequences then spend their steps on restores, commands and time.
        for i in (0, 1):
            self.isolate(i)
            for before in (60, 5, -10):
                self.point(i, before)

    def teardown(self):
        getattr(self, "_cleanup", lambda: None)()

    def _now(self) -> float:
        return _NOW + self.minutes * 60

    @rule(i=st.integers(0, 1))
    def isolate(self, i):
        vm = self.vms[i]
        if vm in self.iso_at:
            return
        self.c.isolate_vm(vm)
        rg, name = vm.split("/")[4], vm.rsplit("/", 1)[-1]
        self.last_cmd[vm] = "drain"
        self.boot_word[vm] = None
        state = _load_isolation_state(vm)
        # The isolation's moment as the test sees it: the test's clock when it is ahead.
        at = max(datetime.fromisoformat(state["isolated_at"]).timestamp(), self._now())
        from glorfindel.actions import _save_isolation_state
        _save_isolation_state(vm, {**state, "isolated_at": datetime.fromtimestamp(at, tz=timezone.utc).isoformat()})
        self.iso_at[vm] = at
        assert rg and name

    @rule(i=st.integers(0, 1), before=st.sampled_from([-30, -5, 5, 60]))
    def point(self, i, before):
        vm = self.vms[i]
        ref = self.iso_at.get(vm, self._now())
        name = f"p-{len(self.f.points.get(key(vm), []))}"
        self.f.add_point(vm, name, datetime.fromtimestamp(ref - before * 60, tz=timezone.utc))

    @rule(i=st.integers(0, 1), harmless=st.booleans())
    def run_command(self, i, harmless):
        vm = self.vms[i]
        from azure.mgmt.compute.models import RunCommandInput
        text = "glorfindel: run command neutralized" if harmless else "attacker"
        self.c._compute.virtual_machines.begin_run_command(
            "rg-app", vm.rsplit("/", 1)[-1], RunCommandInput(command_id="RunShellScript", script=[f"echo '{text}'"]))
        self.last_cmd[vm] = "harmless" if harmless else "attacker"
        self.boot_word[vm] = None

    @rule(i=st.integers(0, 1), data=st.data(), start=st.sampled_from([-10, 2, 10]),
          status=st.sampled_from(["Completed", "Completed", "Failed", "Cancelled", "InProgress"]),
          bag=st.sampled_from(["time", "time", "id", "none"]), power=st.sampled_from(["running", "running", "deallocated"]))
    def restore(self, i, data, start, status, bag, power):
        vm = self.vms[i]
        pts = self.f.points.get(key(vm), [])
        if not pts:
            return
        p = data.draw(st.sampled_from(pts), label="point")
        begin = self._now() + start * 60
        end = None if status == "InProgress" else begin + 15 * 60
        name = self.f.restore(vm, p["name"], datetime.fromtimestamp(begin, tz=timezone.utc),
                              datetime.fromtimestamp(end, tz=timezone.utc) if end else None,
                              status="Completed" if status == "InProgress" else status, bag=bag, power=power)
        self.jobs.append({"vm": vm, "name": name, "start": begin, "end": end, "status": status,
                          "point": p["time"].timestamp(), "named": bag != "none"})
        if status == "Completed" and power == "running" and vm in self.last_cmd:
            self.boot_word[vm] = self.last_cmd[vm]

    @rule(i=st.integers(0, 1))
    def start_vm(self, i):
        v = self.f.vms[key(self.vms[i])]
        if v["power"] != "running":
            v["power"] = "running"
            if v["last_output"]:
                v["said"] = {"message": v["last_output"], "time": datetime.fromtimestamp(self._now(), tz=timezone.utc)}
                self.boot_word[self.vms[i]] = self.last_cmd.get(self.vms[i])

    @rule(minutes=st.sampled_from([6, 16, 30]))
    def recovery_pass(self, minutes):
        self.minutes += minutes
        isolated = {vm for vm in self.vms if _load_isolation_state(vm) is not None}
        out: list[dict] = []
        for r in recovery_watch.recovery_pass(self.c, out.append, now=self._now()):
            event(f"recovery {r['outcome']}")
        for sig in out:
            vm = sig["resource_id"]
            assert vm in isolated, f"R1: a recovery_complete for {vm}, not isolated"
            mine = [j for j in self.jobs if j["vm"] == vm and j["start"] > self.iso_at[vm]]
            assert mine, f"R1: a recovery_complete for {vm} without a restore after its isolation"
            last = max(mine, key=lambda j: j["start"])
            assert last["status"] == "Completed" and last["end"] is not None, f"R1: {last}"
            assert last["named"] and last["point"] < self.iso_at[vm], f"R1: point not before the incident: {last}"
            assert self.f.vms[key(vm)]["power"] == "running", "R1: the VM does not run"
            if sig["raw_signal"]["run_command_neutralized"] is True:
                assert self.boot_word.get(vm) == "harmless", (
                    f"R1: neutralized, yet the disk's word is {self.boot_word.get(vm)}")
            assert (vm, last["name"]) not in self.emitted, f"R2: twice for {last['name']}"
            self.emitted.append((vm, last["name"]))
            if sig["raw_signal"]["run_command_neutralized"] is True:
                # What the graph does in non_disruptive: the release; held otherwise.
                self.c.release_isolation(vm)
                self.iso_at.pop(vm, None)

    @invariant()
    def one_card_per_job_and_reason(self):
        ids = [e["signal_id"] for e in escalations.pending() if str(e.get("signal_id") or "").startswith("recovery-")]
        assert len(ids) == len(set(ids)), f"R2: two cards for one job and one reason: {ids}"
        vms = [i.rsplit("-", 3)[0] for i in ids]
        assert len(vms) == len(set(vms)), f"R2: two of its cards pending on one VM: {ids}"


def test_never_a_release_without_a_recovery_proven_on_azure(monkeypatch):
    import glorfindel.actions as actions
    monkeypatch.setattr(actions, "_ISOLATION_STATE_DIR", actions._ISOLATION_STATE_DIR)
    monkeypatch.setattr(escalations, "_STORE", escalations._STORE)
    monkeypatch.setattr(recovery_watch, "RECOVERIES_FILE", recovery_watch.RECOVERIES_FILE)
    run_state_machine_as_test(RecoveryMachine, settings=settings(
        max_examples=int(os.environ.get("GLORFINDEL_INVARIANT_EXAMPLES", "60")),
        stateful_step_count=int(os.environ.get("GLORFINDEL_INVARIANT_STEPS", "30")),
        deadline=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]))


def test_the_watch_runs_the_pass_in_its_housekeeping():
    """The watch starts the pass from its loop, in a thread of its own, off in a dry run or at 0."""
    import inspect
    from glorfindel import cli
    src = inspect.getsource(cli.watch.callback)
    assert "_recoveries()" in src and 'GLORFINDEL_RECOVERY_INTERVAL_S", "60"' in src
    assert "if dry_run or _recovery_every_s <= 0:" in src and 'name="recoveries"' in src
