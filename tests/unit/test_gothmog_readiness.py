"""G1b: the preflight says whether a fault could run, and be seen — before the bench session spends
ten minutes of noise on it. Past the gate (targets, steady state), three reads, nothing written:
Orodruin's own rights to start and cancel this experiment (`make orodruin-lock YES=1` grants
them, experiment by experiment), the Chaos agent installed on each VM the experiment reaches
through it, and each series the fault's effect reads collected on each target. One not held, or
unreadable: not ready. Mutants M6586–M6605 (scripts/mutants/G1b.py) are measured here.

The bench in memory is G1's (tests/unit/test_gothmog_noise.py), with the agent's samples already
in Perf before the fault — or none, a counter collected under other names."""
import re
from datetime import timedelta
from pathlib import Path

import pytest

from gothmog.engines.chaos_studio import (
    AGENT_INSTALLED, CHAOS_AGENT_EXTENSION, CHAOS_AGENT_TYPE, EXPERIMENT_WRITES, ChaosStudio,
    agent_vms, chaos_agent_status, held)
from gothmog.probes import COLLECTED_WINDOW
from gothmog.runner.engine import Engine
from tests.unit.test_gothmog import (  # noqa: F401  (bench: the fixture, by its name)
    GRANTED, SUB, TARGET, VM, Cred, Resp, World, _audit, _experiment, _no_window, bench)
from tests.unit.test_gothmog_noise import AGENT, CPU, DISK, MB, Noise, _noise

ROOT = Path(__file__).resolve().parents[2]
READS = GRANTED[:1]                       # the group's reads, no chaos role: orodruin-lock not run
START, CANCEL = EXPERIMENT_WRITES


class Idle(Noise):
    """G1's bench before the fault: the agent's samples already in Perf, ``idle`` every 10 s over
    the last hour — none when ``idle`` is None (the counter collected under other names).
    ``peak_fails``: an effect query answers 429."""

    def __init__(self, clock, *, idle=2 * MB, peak_fails=False, **kw):
        kw.setdefault("agent", AGENT_INSTALLED)
        super().__init__(clock, **kw)
        self.idle, self.peak_fails = idle, peak_fails

    def _samples(self):
        out = super()._samples()
        if self.idle is not None:
            t = self.clock.t - timedelta(hours=1)
            while t <= self.clock.t:
                out.append((t, self.idle))
                t += timedelta(seconds=self.step_s)
        return [(t, v) for t, v in out if t + timedelta(seconds=self.lag_s) <= self.clock.t]

    def _query(self, kql):
        if self.peak_fails and "Peak" in kql:
            raise RuntimeError("HTTP 429 TooManyRequests on POST …/query")
        return super()._query(kql)


@pytest.fixture
def idle(bench, tmp_path):  # noqa: F811  (the imported fixture)
    """(clock, world factory, engine factory) on G0's bench; the world is ``Idle`` unless given."""
    clock, _, _ = bench
    state = {}

    def make(cls=Idle, **kw):
        state["world"] = cls(clock, **kw)
        return state["world"]

    def engine():
        factory = lambda session: ChaosStudio(session, credential=Cred(), http=state["world"],  # noqa: E731
                                              subscription_id=SUB)
        return Engine(bench_factory=factory, runs_dir=tmp_path / "runs" / "gothmog", sleep=clock.sleep,
                      now=clock.now)
    return clock, make, engine


def _ready(out) -> dict:
    return {r["name"]: r for r in out.report["ready"]}


def _fails_on(w, suffix: str, nth: int):
    """The ``nth`` GET whose path ends with ``suffix`` answers 429; the ones before it are read."""
    route, seen = w._route, []

    def flaky(method, url, params, body=None):
        if method == "get" and url.lower().endswith(suffix.lower()):
            seen.append(url)
            if len(seen) == nth:
                return Resp(429, {"error": {"code": "TooManyRequests"}})
        return route(method, url, params, body)
    w._route = flaky
    return w


# ── Ready: said, nothing written ───────────────────────────────────────────────────────

def test_a_noise_ready_to_run_says_each_thing_it_read_and_writes_nothing(idle):
    clock, make, engine = idle
    w = make()
    out = engine().preflight("vm-disk-write")
    assert out.result == "OK", out.error
    ready = _ready(out)
    assert set(ready) == {f"{DISK} start", f"{DISK} cancel", "vm-celebrimbor-gondolin chaos agent",
                          "vm-celebrimbor-gondolin disk-writes-above-the-rule"}
    assert all(r["ok"] for r in ready.values())
    # Read where the run would write: the rights at the experiment's own scope.
    assert ("get", f"/subscriptions/{SUB}/resourceGroups/rg-celebrimbor/providers/Microsoft.Chaos"
                   f"/experiments/{DISK}/providers/Microsoft.Authorization/permissions") in w.calls
    assert all(m == "get" or p.endswith("/api/query") for m, p in w.calls)
    assert w.writes == [] and _audit() == [] and _no_window()
    # The effect's own query, over the last minutes — not the fault's window, there is none.
    assert w.windows == [(clock.t - COLLECTED_WINDOW, clock.t)]


def test_an_idle_series_is_collected_far_below_its_threshold(idle):
    """Idle, the disk writes 2 MB/s: 43 MB/s under the rule — a number all the same, collected.
    The threshold is the run's to ask, once the noise is there."""
    _, make, engine = idle
    make(idle=2 * MB)
    assert _ready(engine().preflight("vm-disk-write"))[
        "vm-celebrimbor-gondolin disk-writes-above-the-rule"]["ok"]
    make(experiment=_noise(name=CPU, urn="urn:csci:microsoft:agent:cpuPressure/1.0"), idle=3)
    out = engine().preflight("vm-cpu-pressure")
    assert out.result == "OK", out.error
    assert _ready(out)["vm-celebrimbor-gondolin cpu-load-seen"]["observed"] == "collected"


# ── Not ready: refused, said ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("perms, missing", [
    (READS, (START, CANCEL)),
    (READS + [{"actions": [START], "notActions": []}], (CANCEL,)),
    (READS + [{"actions": [CANCEL], "notActions": []}], (START,)),
])
def test_without_orodruin_lock_the_preflight_says_a_start_would_be_refused(idle, perms, missing):
    """The contract arms on G0's experiment alone: a new one, applied after the last
    `make orodruin-lock YES=1`, would answer 403 to the start — or start, and never cancel."""
    _, make, engine = idle
    make(perms=perms)
    out = engine().preflight("vm-disk-write")
    assert out.result == "REFUSED"
    for action in missing:
        verb = action.rsplit("/", 2)[-2]
        assert _ready(out)[f"{DISK} {verb}"]["ok"] is False
        assert f"{DISK} {verb} not held: make orodruin-lock YES=1" in out.error


def test_a_right_its_role_takes_back_is_not_held():
    """An entry is one role: its notActions take from its own actions, not from another's."""
    wide = [{"actions": ["Microsoft.Chaos/experiments/*"], "notActions": [START]}]
    assert not held(START, wide) and held(CANCEL, wide)
    assert held(START, wide + [{"actions": [START], "notActions": []}])
    assert not held(START, [{"actions": ["microsoft.chaos/experiments/start/actions"]}, "x"])


@pytest.mark.parametrize("answer", ["403", "next page", "no list"])
def test_rights_that_cannot_be_read_are_not_held(idle, answer):
    """Never « not held » on an answer that lists nothing: unreadable, not orodruin-lock."""
    _, make, engine = idle
    if answer == "403":
        w = make(fail={"/providers/Microsoft.Authorization/permissions": 403})
    else:
        w = make()
        route = w._route

        def odd(method, url, params, body=None):
            r = route(method, url, params, body)
            if url.endswith("/permissions"):
                r._body = ({**r._body, "nextLink": url + "?$skiptoken=2"} if answer == "next page"
                           else {})
            return r
        w._route = odd
    out = engine().preflight("vm-disk-write")
    assert out.result == "REFUSED"
    assert _ready(out)[f"{DISK} rights"]["observed"].startswith("unreadable: RuntimeError")


@pytest.mark.parametrize("status", [None, "ProvisioningState/failed", "ProvisioningState/creating"])
def test_a_chaos_agent_not_installed_is_not_ready(idle, status):
    _, make, engine = idle
    make(agent=status)
    out = engine().preflight("vm-disk-write")
    assert out.result == "REFUSED"
    r = _ready(out)["vm-celebrimbor-gondolin chaos agent"]
    assert r["ok"] is False and r["observed"] == (status or "absent")
    assert "vm-celebrimbor-gondolin chaos agent" in out.error


def test_an_agent_that_cannot_be_read_is_not_installed(idle):
    """The gate read the VM (its tags, then its steady state); the preflight's own read answers 429."""
    _, make, engine = idle
    _fails_on(make(), "/virtualmachines/vm-celebrimbor-gondolin", 3)
    out = engine().preflight("vm-disk-write")
    assert out.result == "REFUSED"
    assert _ready(out)["vm-celebrimbor-gondolin chaos agent"]["observed"].startswith(
        "unreadable: RuntimeError: HTTP 429")


def test_the_agent_is_asked_on_the_experiment_the_gate_validated(idle):
    """Review 1: read again, an experiment answering ``{}`` named no agent target — no agent
    asked, and a VM without one was ready. The experiment is read once, by the gate."""
    _, make, engine = idle
    w = make(agent=None)
    route, reads = w._route, []

    def emptied(method, url, params, body=None):
        if method == "get" and url.endswith(f"/experiments/{DISK}"):
            reads.append(url)
            if len(reads) > 1:
                return Resp(200, {})
        return route(method, url, params, body)
    w._route = emptied
    out = engine().preflight("vm-disk-write")
    assert out.result == "REFUSED"
    assert _ready(out)["vm-celebrimbor-gondolin chaos agent"]["observed"] == "absent"
    assert len(reads) == 1
    assert out.report["experiment"]["agents"] == [VM]


def test_a_series_never_collected_under_the_effect_s_names_is_not_ready(idle):
    """A counter not collected under the effect's names (the 20/11 DCR declared the CPU under its
    Windows name, which the Linux agent never collects): the query finds nothing — the noise would
    run ten minutes, unseen."""
    _, make, engine = idle
    make(experiment=_noise(name=CPU, urn="urn:csci:microsoft:agent:cpuPressure/1.0"), idle=None)
    out = engine().preflight("vm-cpu-pressure")
    assert out.result == "REFUSED"
    r = _ready(out)["vm-celebrimbor-gondolin cpu-load-seen"]
    assert r["ok"] is False and r["observed"] == "nothing in the last 30 min under these names"
    assert "cpu-load-seen" in out.error


def test_a_series_that_cannot_be_read_is_not_collected(idle):
    _, make, engine = idle
    make(peak_fails=True)
    out = engine().preflight("vm-disk-write")
    assert out.result == "REFUSED"
    r = _ready(out)["vm-celebrimbor-gondolin disk-writes-above-the-rule"]
    assert r["ok"] is False and r["observed"].startswith("unreadable: RuntimeError: HTTP 429")


# ── What each fault asks ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fault, engine_ref, duration", [
    ("vm-shutdown", "exp-celebrimbor-gondolin-shutdown", "PT5M"),
    ("vm-restart", "exp-celebrimbor-gondolin-restart", "PT1M"),
])
def test_a_fault_on_the_vm_itself_asks_its_rights_and_no_agent_nor_series(bench, fault, engine_ref, duration):  # noqa: F811
    """A shutdown's target is the VM itself, its effect the VM seen down (ARM): its rights only."""
    _, world, engine = bench
    world(experiment=_experiment(name=engine_ref, duration=duration))
    out = engine().preflight(fault)
    assert out.result == "OK", out.error
    assert set(_ready(out)) == {f"{engine_ref} start", f"{engine_ref} cancel"}
    world(experiment=_experiment(name=engine_ref, duration=duration), perms=READS)
    assert engine().preflight(fault).result == "REFUSED"


def test_the_agent_is_read_only_on_the_vms_it_reaches():
    both = {"properties": {"selectors": [{"type": "List", "targets": [{"id": TARGET}, {"id": AGENT}]}]}}
    assert agent_vms(_noise()) == [VM] and agent_vms(both) == [VM]
    assert agent_vms(_experiment()) == []
    view = {"properties": {"instanceView": {"extensions": [
        {"name": "AzureMonitorLinuxAgent", "type": "Microsoft.Azure.Monitor.AzureMonitorLinuxAgent",
         "statuses": [{"code": AGENT_INSTALLED}]},
        {"name": "ChaosLinuxAgent", "statuses": [{"code": "ProvisioningState/failed"}]}]}}}
    assert chaos_agent_status(view) == "ProvisioningState/failed"
    assert chaos_agent_status({"properties": {"instanceView": {}}}) == "absent"


def test_the_names_read_are_those_celebrimbor_and_orodruin_declare():
    """The extension the preflight looks for is the one Celebrimbor installs, and the rights it
    asks are the ones Orodruin's chaos role grants — a rename on one side, and it says so."""
    chaos = (ROOT / "infra/terraform/chaos.tf").read_text()
    ext = re.search(r'resource "azurerm_virtual_machine_extension" "chaos_agent" \{(.*?)\n\}', chaos, re.S).group(1)
    fields = dict(re.findall(r'^\s*(name|publisher|type)\s*=\s*"([^"]+)"', ext, re.M))
    assert fields["name"].lower() == CHAOS_AGENT_EXTENSION
    assert f"{fields['publisher']}.{fields['type']}".lower() == CHAOS_AGENT_TYPE
    oro = (ROOT / "infra/orodruin/main.tf").read_text()
    role = re.search(r'resource "azurerm_role_definition" "injector_chaos" \{(.*?)\n\}', oro, re.S).group(1)
    assert sorted(re.findall(r'"(Microsoft\.Chaos/[^"]+)"', role)) == sorted(EXPERIMENT_WRITES)


class LinuxPerf(Idle):
    """G1f: Perf as the Linux agent fills it on gondolin, measured on 21/11 after DCR1's apply —
    Processor / % Processor Time under the instances total, cpu0, cpu1. A CPU query reads its
    samples only if it asks for one of those instances by name, as Log Analytics would."""

    INSTANCES = ("total", "cpu0", "cpu1")

    def _query(self, kql):
        if "Peak" in kql and "'Processor'" in kql:
            asked = re.findall(r"InstanceName == '([^']+)'", kql)
            if not asked or not set(asked) & set(self.INSTANCES):
                return {"Tables": [{"TableName": "Table_0", "Columns": [{"ColumnName": "Peak"}],
                                    "Rows": [[None]]}]}
        return super()._query(kql)


def test_the_cpu_load_is_read_under_its_linux_instance_and_the_preflight_lets_it_run(idle):
    """G1f: on 21/11 the CPU arrived under the instance « total », not the Windows « _Total »: the
    preflight's series of vm-cpu-pressure is collected, the fault no longer refused for it."""
    _, make, engine = idle
    make(cls=LinuxPerf, experiment=_noise(name=CPU, urn="urn:csci:microsoft:agent:cpuPressure/1.0"), idle=3)
    out = engine().preflight("vm-cpu-pressure")
    assert out.result == "OK", out.error
    assert _ready(out)["vm-celebrimbor-gondolin cpu-load-seen"]["observed"] == "collected"
