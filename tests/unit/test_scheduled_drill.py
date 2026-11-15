"""The drill of the week on Orodruin (DRL1a, eregion_core/scheduled_drill.py, docs/design/drill-banc.md
§2.3, §3.1, §3.2): an occurrence refuses in its order — disarmed, drill_changed, off_schedule,
no_permit, permit_mismatch, busy, too_soon, passive, watch, not_placed, not_bench, isolated,
not_ready, stopped — and nothing reaches the bench before the contract, the watch and the journal.
Plus the schedule's reader (eregion_core/drill.py), the runner's ``zones`` (exercise_plan,
exercise_runner) and the status's ``drill`` (exercise_request).

Every reader is a fake: a fake clock, a fake channel (the permit, its ETag), a fake Azure (the VMs,
their power, their Heartbeat, the start), a fake injector — no Azure, no model, the HOME of the
conftest. The oracles are written here, from the design, never from the code's markers.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from eregion_core import drill as dr
from eregion_core import drill_arming as da
from eregion_core import exercise_request as xr
from eregion_core import exercise_runner as er
from eregion_core import orodruin, runs_layout
from eregion_core import scheduled_drill as sd
from eregion_core.exercise import exercises_dir
from eregion_core.exercise_channel import Changed
from eregion_core.exercise_plan import Target, judge, load_catalog, plan

SUB = "00000000-0000-0000-0000-000000000000"
RG = f"/subscriptions/{SUB}/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/"
GONDOLIN = RG + "vm-celebrimbor-gondolin"
BENCH_RG = {"eregion-target": "celebrimbor"}
BENCH_TAGS = {"eregion-target": "celebrimbor", "eregion-zone": "bench"}
PROD_TAGS = {"eregion-target": "celebrimbor", "eregion-zone": "production"}
# Tuesday 17/11/2026, 19:05 UTC: five minutes into the schedule's window (tue 19:00).
T0 = datetime(2026, 11, 17, 19, 5, tzinfo=timezone.utc)
ARMED_AT = "2026-11-16T10:00:00+00:00"
SHIPPED = dr.shipped_dir() / "banc-hebdo.yaml"
SHA = dr.fingerprint(SHIPPED.read_bytes())
CAP = {"max_injections": 10, "max_run_s": 3600}


@pytest.fixture(autouse=True)
def _bench_subscription(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", SUB)


class Clock:
    def __init__(self, t=T0):
        self.t = t
        self.mono = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += timedelta(seconds=s)
        self.mono += s

    def monotonic(self):
        return self.mono


class Permits:
    """The channel's permit: a document and its ETag; a conditional write over another ETag (or
    over nothing) is refused, as Azure does (412)."""

    def __init__(self, doc=None):
        self.doc, self.etag, self.n = doc, ('"e1"' if doc is not None else ""), 1
        self.writes: list[tuple[dict, str]] = []
        self.reads = 0
        self.before_write = None

    def read(self):
        self.reads += 1
        return (dict(self.doc) if self.doc is not None else None), self.etag

    def write(self, doc, etag):
        if self.before_write:
            self.before_write()
        self.writes.append((doc, etag))
        if self.doc is None or etag != self.etag:
            raise Changed("412")
        self.n += 1
        self.doc, self.etag = dict(doc), f'"e{self.n}"'


class World:
    """Azure as Orodruin's identity reads it, the injector it launches, and the order of it all."""

    def __init__(self, tmp_path, clock, *, tags=BENCH_TAGS, power="deallocated", fresh_after_start=True):
        self.tmp, self.clock = tmp_path, clock
        self.events: list[str] = []
        self.tags = tags
        self.power_state = power
        self.fresh_after_start = fresh_after_start
        self.started: list[str] = []
        self.launched: list[tuple[list[str], dict]] = []
        self.statuses: list[dict] = []
        self.pulses: list[dict] = []
        self.held = ""
        self.watch_says = ""
        self.contract = orodruin.Verdict(orodruin.ARMED, [], dict(CAP))
        self.targets_read = 0
        self.retag_at = None
        self.vms = [{"resource_id": GONDOLIN, "name": "vm-celebrimbor-gondolin", "rg_tags": BENCH_RG,
                     "tags": dict(tags)}]
        self.sessions: list["Session"] = []

    def check(self):
        self.events.append("contract")
        return self.contract

    def watch(self):
        self.events.append("watch")
        return self.watch_says

    def isolated(self, rid):
        self.events.append("isolation")
        return self.held

    def power(self, rid):
        self.events.append("power")
        return self.power_state

    def start(self, rid):
        self.events.append("start")
        self.started.append(rid)
        self.power_state = "running"
        self.started_at = self.clock()
        self.clock.sleep(1)   # the call takes its time: the runner starts after it

    def heartbeat(self, rid):
        if self.power_state != "running":
            return None
        if self.started:
            return self.started_at + timedelta(seconds=60) if self.fresh_after_start else None
        return self.clock() - timedelta(seconds=60)

    def read_target(self, rid):
        self.targets_read += 1
        tags = PROD_TAGS if self.retag_at is not None and self.targets_read >= self.retag_at else self.tags
        return Target(rid, BENCH_RG, dict(tags)), "vm-celebrimbor-gondolin"

    def arm(self, run_id, injector, verdict=None, request=""):
        s = Session(self, run_id, request, verdict)
        self.sessions.append(s)
        return verdict, s

    def popen(self, argv, env=None, pass_fds=()):
        self.events.append("launch")
        self.launched.append((argv, env))
        return Wire(self, argv, env)


class Session:
    def __init__(self, world, run_id, request, verdict):
        self.world, self.run_id, self.request = world, run_id, request
        self.max_injections = verdict.cap["max_injections"]
        self.calls = 0

    def before_call(self, action, target, detail=""):
        self.world.events.append(f"journal:{action}")
        self.calls += 1
        with open(orodruin.audit_path(), "a") as f:
            f.write(json.dumps({"ts": self.world.clock().isoformat(), "run_id": self.run_id,
                                "request": self.request, "action": action, "outcome": "about_to_call"}) + "\n")


class Wire:
    """A wire's injector: its window (naming the request), its report, its journal — then done."""

    def __init__(self, world, argv, env):
        self.world = world
        request = argv[argv.index("--request") + 1]
        own = runs_layout.dir_of("annatar", world.tmp / "runs")
        own.mkdir(parents=True, exist_ok=True)
        xdir = exercises_dir(own)
        xdir.mkdir(parents=True, exist_ok=True)
        rid = f"run-{len(world.launched)}"
        (xdir / f"{rid}.json").write_text(json.dumps({"run_id": rid, "request": request, "targets": [argv[3].lower()]}))
        (own / f"{rid}.json").write_text(json.dumps({"run_id": rid, "result": "PASS"}))
        self.returncode = None

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def send_signal(self, sig):
        pass

    def kill(self):
        pass


def _armed(tmp_path, **over) -> Path:
    doc = {"drill": "banc-hebdo", "sha256": SHA, "targets": ["vm-celebrimbor-gondolin"], "armed_at": ARMED_AT,
           "image": "abc123 sha256:00"}
    doc.update(over)
    path = tmp_path / "drill" / "armed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))
    return path


def _permit(**over):
    return {"drill": "banc-hebdo", "sha256": SHA, "armed_at": ARMED_AT, **over}


def _occurrence(tmp_path, *, world=None, clock=None, permits=None, armed=True, lock=er.request_lock, **kw):
    clock = clock or Clock()
    world = world or World(tmp_path, clock)
    permits = permits if permits is not None else Permits(_permit())
    if armed:
        _armed(tmp_path)
    occ = sd.Occurrence(
        armed_file=tmp_path / "drill" / "armed.json", catalog=load_catalog(), runs_dir=tmp_path / "runs",
        now=clock, sleep=clock.sleep, monotonic=clock.monotonic, say=lambda *_: None,
        read_permit=permits.read, write_permit=permits.write, publish_pulse=world.pulses.append,
        lock=lock, list_vms=lambda: world.vms, check=world.check, watch=world.watch,
        isolated=world.isolated, power=world.power, start=world.start, heartbeat=world.heartbeat,
        arm=world.arm, read_target=world.read_target, publish_status=lambda s: world.statuses.append(s.to_dict()),
        publish_contract=lambda v: None, popen=world.popen, **kw)
    return occ, world, permits, clock


def _registry(tmp_path) -> list[dict]:
    path = sd.registry_path(tmp_path / "runs")
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


# ── The occurrence that plays ──────────────────────────────────────────────────────────

def test_an_occurrence_starts_its_target_journaled_first_then_plays_and_says_it(tmp_path):
    occ, world, permits, _ = _occurrence(tmp_path)
    out = occ.run()
    assert out["state"] == "played", out
    # The contract and the watch judged, the isolation read, the journal, then the start; the wire last.
    ev = world.events
    assert ev.index("watch") < ev.index("isolation") < ev.index("journal:start_vm") < ev.index("start") \
        < ev.index("launch")
    assert ev.index("contract") < ev.index("start")
    assert world.started == [GONDOLIN]
    assert world.sessions[0].run_id.endswith("-start") and world.sessions[0].request == occ.request.id
    # The permit rewritten as it was, over the very blob read (If-Match).
    assert permits.writes == [(_permit(), '"e1"')]
    # The pulse: played, the occurrence and the request said, nothing of the target.
    pulse = da.read_pulse(world.pulses[-1])
    assert pulse["state"] == "armed" and pulse["last"]["state"] == "played"
    assert pulse["last"]["request"] == occ.request.id and "gondolin" not in json.dumps(pulse)
    assert pulse["next"] == (T0.replace(minute=0) + timedelta(days=7)).isoformat()
    assert json.loads(sd.pulse_path(tmp_path / "runs").read_text()) == pulse


def test_the_start_is_counted_in_the_cap_the_runner_is_given(tmp_path):
    occ, world, _, _ = _occurrence(tmp_path)
    occ.run()
    _, env = world.launched[0]
    # The drill's 6 calls, less the start's: the wire may make 5.
    assert env[orodruin.MAX_INJECTIONS_ENV] == "5"
    assert int(env[orodruin.MAX_RUN_S_ENV]) <= 1800


def test_a_running_target_is_never_started_and_the_wire_keeps_the_drills_cap(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock, power="running")
    occ, world, _, _ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["state"] == "played"
    assert world.started == [] and "journal:start_vm" not in world.events
    assert world.launched[0][1][orodruin.MAX_INJECTIONS_ENV] == "6"


def test_the_request_status_carries_the_drill_and_its_reader_takes_it(tmp_path):
    occ, world, _, _ = _occurrence(tmp_path)
    occ.run()
    last = world.statuses[-1]
    assert last["drill"] == {"name": "banc-hebdo", "sha256": SHA, "occurrence": T0.replace(minute=0).isoformat()}
    assert xr.read_status(json.loads(json.dumps(last))) == last
    assert last["state"] == "finished" and last["wires"][0]["state"] == "done"


def test_the_wire_runs_under_the_occurrences_lock_never_busy(tmp_path):
    occ, world, _, _ = _occurrence(tmp_path)
    assert occ.run()["state"] == "played"
    assert world.statuses[-1]["codes"] == []
    assert er.LOCK_FD_ENV in world.launched[0][1]
    assert er.LOCK_FD_ENV not in os.environ   # given back as it was


def test_the_registry_is_written_under_the_lock_before_the_judgment(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    seen = []

    def check():
        seen.append(_registry(tmp_path))
        raise RuntimeError("the contract reader crashes")

    world.check = check
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    with pytest.raises(RuntimeError):
        occ.run()
    assert seen and len(seen[0]) == 1 and seen[0][0]["drill"] == "banc-hebdo"


# ── Refused before the request, in the order of §2.3 ────────────────────────────────

def test_disarmed_nothing_runs_nothing_is_published(tmp_path):
    occ, world, permits, _ = _occurrence(tmp_path, armed=False)
    assert occ.run()["code"] == "disarmed"
    assert world.pulses == [] and permits.reads == 0 and _registry(tmp_path) == []


def test_a_drill_whose_fingerprint_changed_is_refused_until_re_armed(tmp_path):
    occ, world, permits, _ = _occurrence(tmp_path, armed=False)
    _armed(tmp_path, sha256="0" * 64)
    out = occ.run()
    assert out["code"] == "drill_changed"
    assert permits.reads == 0 and permits.writes == [] and world.launched == []
    pulse = da.read_pulse(world.pulses[-1])
    assert pulse["state"] == "disarmed" and pulse["reason"] == "drill_changed"


def test_the_drill_is_read_from_the_image_shipped_layer_never_the_instances(tmp_path, monkeypatch):
    # A drill of the console's instance under the same name never takes the shipped one's place.
    inst = tmp_path / "console-drills"
    inst.mkdir(parents=True, exist_ok=True)
    (inst / "banc-hebdo.yaml").write_text(yaml.safe_dump({
        "name": "banc-hebdo", "author": "operator", "updated": "2026-11-01T00:00:00+00:00",
        "wires": [{"experiment": "T1486", "target": {"name": "vm-celebrimbor-gondolin"}}]}))
    occ, world, *_ = _occurrence(tmp_path)
    assert occ.run()["state"] == "played"
    assert world.launched[0][0][2] == "T1136.001"


def test_a_start_off_its_hour_plays_nothing_and_writes_nothing_before(tmp_path):
    occ, world, permits, _ = _occurrence(tmp_path, clock=Clock(T0 + timedelta(minutes=40)))
    assert occ.run()["code"] == "off_schedule"
    assert permits.reads == 0 and permits.writes == [] and _registry(tmp_path) == []
    assert world.events == []


def test_a_start_by_hand_on_another_day_is_off_schedule(tmp_path):
    occ, *_ = _occurrence(tmp_path, clock=Clock(T0 - timedelta(days=1)))
    assert occ.run()["code"] == "off_schedule"


def test_no_permit_in_the_channel_closes(tmp_path):
    occ, world, permits, _ = _occurrence(tmp_path, permits=Permits(None))
    assert occ.run()["code"] == "no_permit"
    assert permits.writes == [] and _registry(tmp_path) == [] and world.events == []


@pytest.mark.parametrize("doc", [_permit(sha256="1" * 64), _permit(armed_at="2026-11-01T00:00:00+00:00"),
                                 _permit(drill="sentinelle"), {"drill": "banc-hebdo"}])
def test_a_permit_that_is_not_the_armings_is_refused(tmp_path, doc):
    occ, world, permits, _ = _occurrence(tmp_path, permits=Permits(doc))
    assert occ.run()["code"] == "permit_mismatch"
    assert permits.writes == [] and world.launched == []


def test_a_permit_unreadable_is_refused_never_taken_for_present(tmp_path):
    permits = Permits(_permit())
    permits.read = lambda: (_ for _ in ()).throw(RuntimeError("HTTP 403"))
    occ, world, *_ = _occurrence(tmp_path, permits=permits)
    assert occ.run()["code"] == "permit_mismatch" and world.launched == []


def test_a_permit_removed_between_its_read_and_its_rewrite_is_never_recreated(tmp_path):
    permits = Permits(_permit())

    def removed():
        permits.doc, permits.etag = None, ""

    permits.before_write = removed
    occ, world, *_ = _occurrence(tmp_path, permits=permits)
    assert occ.run()["code"] == "no_permit"
    assert permits.doc is None and world.launched == [] and _registry(tmp_path) == []


def test_another_run_holding_the_lock_is_busy_and_the_week_is_not_spent(tmp_path):
    occ, world, *_ = _occurrence(tmp_path)
    with er.request_lock("campaign C1"):
        out = occ.run()
    assert out["code"] == "busy"
    assert _registry(tmp_path) == [] and world.launched == []


def test_an_occurrence_played_this_week_is_too_soon(tmp_path):
    path = sd.registry_path(tmp_path / "runs")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"drill": "banc-hebdo", "played": (T0 - timedelta(days=2)).isoformat()}) + "\n")
    occ, world, *_ = _occurrence(tmp_path)
    assert occ.run()["code"] == "too_soon"
    assert world.launched == [] and len(_registry(tmp_path)) == 1


def test_a_second_start_in_the_same_window_is_too_soon(tmp_path):
    occ, world, *_ = _occurrence(tmp_path)
    assert occ.run()["state"] == "played"
    again, world2, *_ = _occurrence(tmp_path, clock=Clock(T0 + timedelta(minutes=10)))
    assert again.run()["code"] == "too_soon"
    assert world2.launched == []


def test_last_weeks_occurrence_does_not_stop_this_weeks(tmp_path):
    path = sd.registry_path(tmp_path / "runs")
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"drill": "banc-hebdo", "played": (T0 - timedelta(days=7)).isoformat()}) + "\n")
    occ, *_ = _occurrence(tmp_path)
    assert occ.run()["state"] == "played"


def test_a_registry_that_cannot_be_read_plays_nothing(tmp_path):
    path = sd.registry_path(tmp_path / "runs")
    path.parent.mkdir(parents=True)
    path.write_text("not json\n")
    occ, world, *_ = _occurrence(tmp_path)
    assert occ.run()["code"] == "too_soon" and world.launched == []


def test_two_occurrences_side_by_side_play_once(tmp_path):
    """The registry is read under the lock: the second, started while the first holds it, is busy;
    started after, it reads the first's line — never both reading it empty."""
    first, w1, *_ = _occurrence(tmp_path)
    second, w2, *_ = _occurrence(tmp_path)
    inner = {}

    def launch_then_second(argv, env=None, pass_fds=()):
        # Another process: the descriptor handed down to this one's wire is not its own.
        held = os.environ.pop(er.LOCK_FD_ENV)
        try:
            inner["out"] = second.run()
        finally:
            os.environ[er.LOCK_FD_ENV] = held
        return Wire(w1, argv, env)

    w1.popen = launch_then_second
    first.popen = launch_then_second
    assert first.run()["state"] == "played"
    assert inner["out"]["code"] == "busy"
    assert w2.launched == []


# ── Refused at the judgment, then skipped (§3.1, 2–6) ───────────────────────────────

def test_a_passive_contract_refuses_and_nothing_reaches_the_bench(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    world.contract = orodruin.Verdict(orodruin.PASSIVE, [{"code": "network_open", "detail": "x"}], {})
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["code"] == "passive"
    assert world.started == [] and world.launched == [] and "journal:start_vm" not in world.events
    assert world.statuses[-1]["state"] == "refused"
    assert len(_registry(tmp_path)) == 1   # the week is played: a refusal spends it


def test_no_live_watch_is_read_again_ten_minutes_then_refused_before_any_start(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    world.watch_says = "no heartbeat for 3 min"
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["code"] == "watch"
    assert clock.t - T0 >= timedelta(minutes=10)
    assert world.started == [] and "isolation" not in world.events


def test_a_watch_back_within_the_ten_minutes_plays(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    calls = {"n": 0}

    def watch():
        calls["n"] += 1
        return "deploying" if calls["n"] < 3 else ""

    world.watch = watch
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["state"] == "played"


@pytest.mark.parametrize("vms", [[], "twice"])
def test_a_name_armed_that_is_not_one_enrolled_vm_is_not_placed(tmp_path, vms):
    clock = Clock()
    world = World(tmp_path, clock)
    world.vms = [] if vms == [] else world.vms * 2
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["code"] == "not_placed"
    assert world.events == [] and world.launched == []


def test_a_target_in_production_is_not_bench_though_the_production_rule_would_admit_it(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock, tags=PROD_TAGS)
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["code"] == "not_bench"
    assert world.started == [] and world.launched == []
    # The production rule alone admits a non-destructive technique there: the drill is stricter.
    t = Target(GONDOLIN, BENCH_RG, dict(PROD_TAGS))
    assert judge("T1136.001", GONDOLIN, t, catalog=load_catalog()).code == ""


def test_a_drill_cap_over_the_declared_one_is_refused(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    world.contract = orodruin.Verdict(orodruin.ARMED, [], {"max_injections": 4, "max_run_s": 3600})
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    assert occ.run()["code"] == "over_cap" and world.launched == [] and world.started == []


def test_a_target_held_by_glorfindel_is_never_started_and_its_wire_skipped(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    world.held = "isolation rule on its NIC"
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    out = occ.run()
    assert out == {**out, "state": "skipped", "code": "isolated"}
    assert world.started == [] and "power" not in world.events and world.launched == []


def test_a_target_started_without_a_fresh_heartbeat_is_not_ready(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock, fresh_after_start=False)
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    out = occ.run()
    assert (out["state"], out["code"]) == ("skipped", "not_ready")
    assert world.started == [GONDOLIN] and world.launched == []
    assert clock.t - T0 >= timedelta(minutes=10)


def test_a_target_retagged_production_before_its_wire_is_refused_by_the_recheck(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock, power="running")
    world.retag_at = 3   # read at the first judgment, at the run's, then before the wire
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    out = occ.run()
    assert out["state"] == "skipped" and out["code"] == "refused_now"
    assert world.launched == []


# ── SIGTERM (§3.1, the service's stop) ───────────────────────────────────────────────

class Sleeper:
    """A wire that sleeps: it ends ``after`` seconds after SIGTERM, or never (None)."""

    def __init__(self, clock, after=5.0):
        self.clock, self.after = clock, after
        self.signals, self.killed, self.term_at = [], False, None
        self.returncode = None

    def wait(self, timeout=None):
        if self.killed:
            self.returncode = -9
            return -9
        if self.term_at is not None and self.after is not None and self.clock.mono - self.term_at >= self.after:
            self.returncode = 143
            return 143
        self.clock.sleep(timeout or 1.0)
        if self.on_tick:
            self.on_tick()
        raise subprocess.TimeoutExpired("annatar", timeout)

    on_tick = None

    def send_signal(self, sig):
        self.signals.append(sig)
        self.term_at = self.clock.mono

    def kill(self):
        self.killed = True


def _stopping(tmp_path, after):
    clock = Clock()
    occ, world, _, _ = _occurrence(tmp_path, clock=clock)
    child = Sleeper(clock, after)
    ticks = {"n": 0}

    def tick():
        ticks["n"] += 1
        if ticks["n"] == 3:
            occ.on_term()    # systemd's stop, while the wire is awaited: never a raise
    child.on_tick = tick
    occ.popen = lambda argv, env=None, pass_fds=(): child
    return occ, world, child, clock


def test_sigterm_during_a_wire_is_relayed_awaited_and_the_occurrence_is_stopped(tmp_path):
    import signal
    occ, world, child, clock = _stopping(tmp_path, after=5.0)
    out = occ.run()
    assert out["state"] == "stopped"
    assert child.signals == [signal.SIGTERM] and not child.killed
    assert da.read_pulse(world.pulses[-1])["last"]["state"] == "stopped"
    # The request, its wire failed, finished: the runner ran nothing after it.
    assert world.statuses[-1]["state"] == "finished" and world.statuses[-1]["wires"][0]["state"] == "failed"


def test_a_wire_that_ignores_sigterm_is_killed_only_after_75_s(tmp_path):
    occ, world, child, clock = _stopping(tmp_path, after=None)
    out = occ.run()
    assert out["state"] == "stopped" and child.killed
    assert clock.mono - child.term_at >= sd.STOP_WAIT_S


def test_sigterm_outside_a_wire_raises_and_the_occurrence_is_stopped(tmp_path):
    clock = Clock()
    world = World(tmp_path, clock)
    occ, *_ = _occurrence(tmp_path, world=world, clock=clock)
    orig = world.power

    def power(rid):
        occ.on_term()
        return orig(rid)

    occ.power = power
    out = occ.run()
    assert out["state"] == "stopped" and world.started == [] and world.launched == []


def test_sigterm_before_a_wire_launches_nothing(tmp_path):
    occ, world, *_ = _occurrence(tmp_path)
    occ.stop_at = 1.0
    with pytest.raises(sd.Stopped):
        occ.launch(["annatar", "wire", "T1136.001", GONDOLIN, "--request", "r-x"], {})
    assert world.launched == []


# ── The schedule's reader (eregion_core/drill.py) ────────────────────────────────────

def _doc(**over):
    doc = yaml.safe_load(SHIPPED.read_text())
    doc.update(over)
    return doc


def test_the_weekly_drill_reads_with_its_schedule():
    d, sha = dr.loaded(SHIPPED, dr.SHIPPED)
    assert sha == SHA
    assert d.schedule == dr.Schedule("tue", "19:00", 6, 1800)
    assert d.schedule.on_calendar() == "Tue *-*-* 19:00:00 UTC"
    assert d.schedule.occurrence(T0) == T0.replace(minute=0)
    assert d.schedule.occurrence(T0.replace(hour=18)) == T0.replace(minute=0) - timedelta(days=7)


@pytest.mark.parametrize("schedule, said", [
    ({"day": "tuesday", "at": "19:00", "max_injections": 6, "max_run_s": 1800}, "day"),
    ({"day": "tue", "at": "7pm", "max_injections": 6, "max_run_s": 1800}, "HH:MM"),
    ({"day": "tue", "at": "24:00", "max_injections": 6, "max_run_s": 1800}, "HH:MM"),
    ({"day": "tue", "at": "19:00", "max_injections": 21, "max_run_s": 1800}, "CEILING_INJECTIONS"),
    ({"day": "tue", "at": "19:00", "max_injections": 6, "max_run_s": 7201}, "CEILING_RUN_S"),
    ({"day": "tue", "at": "19:00", "max_injections": True, "max_run_s": 1800}, "max_injections"),
    ({"day": "tue", "at": "19:00", "max_injections": 6}, "lacks"),
    ({"day": "tue", "at": "19:00", "max_injections": 6, "max_run_s": 1800, "targets": "all"}, "never holds"),
])
def test_a_schedule_awry_is_refused(schedule, said):
    with pytest.raises(dr.DrillRefused, match=said):
        dr.read(_doc(schedule=schedule), dr.SHIPPED)


@pytest.mark.parametrize("wires, said", [
    ([{"experiment": "T1136.001", "target": {"zone": "production"}}], "bench"),
    ([{"experiment": "T1136.001", "target": {"zone": "twin"}}], "bench"),
    ([{"experiment": "T1486", "target": {"zone": "bench"}}], "non-destructive"),
    ([{"experiment": "vm-shutdown", "target": {"zone": "bench"}}], "not a technique"),
    ([{"experiment": "T1110.001", "target": {"zone": "bench"}}], "public library"),
    ([{"experiment": "T9999", "target": {"zone": "bench"}}], "catalogue"),
])
def test_a_scheduled_drill_plays_a_public_non_destructive_technique_on_the_bench_alone(wires, said):
    with pytest.raises(dr.DrillRefused, match=said):
        dr.read(_doc(wires=wires), dr.SHIPPED, load_catalog())


def test_only_a_shipped_drill_is_scheduled_and_the_others_shipped_carry_none():
    inst = {"name": "mine", "author": "operator", "updated": "2026-11-01T00:00:00+00:00",
            "schedule": _doc()["schedule"], "wires": [{"experiment": "T1136.001", "target": {"name": "vm-x"}}]}
    with pytest.raises(dr.DrillRefused, match="only a shipped drill"):
        dr.read(inst, dr.INSTANCE)
    for name in ("sentinelle", "bl1-reponse"):
        assert dr.load_file(dr.shipped_dir() / f"{name}.yaml", dr.SHIPPED).schedule is None
        doc = yaml.safe_load((dr.shipped_dir() / f"{name}.yaml").read_text())
        with pytest.raises(dr.DrillRefused):
            dr.read({**doc, "schedule": _doc()["schedule"]}, dr.SHIPPED)


def test_the_fingerprint_is_the_whole_file_byte_for_byte(tmp_path):
    copy = tmp_path / "banc-hebdo.yaml"
    copy.write_bytes(SHIPPED.read_bytes() + b"# a comment\n")
    assert dr.loaded(copy, dr.SHIPPED)[1] != SHA


def test_the_image_catalogue_is_read_again_at_each_occurrence(tmp_path):
    from dataclasses import replace
    catalog = load_catalog()
    catalog["T1136.001"] = replace(catalog["T1136.001"], destructive=True)
    clock = Clock()
    occ, world, permits, _ = _occurrence(tmp_path, clock=clock)
    occ.catalog = catalog
    out = occ.run()
    assert out["code"] in ("drill_changed", "not_eligible")
    assert world.launched == [] and permits.writes == []


# ── The runner's zones and the plan's not_bench (exercise_plan, exercise_runner) ────

def test_the_plan_refuses_a_zone_outside_the_ones_given_and_dg_b_by_default_is_unchanged():
    t = {GONDOLIN.lower(): Target(GONDOLIN, BENCH_RG, dict(PROD_TAGS))}
    catalog = load_catalog()
    assert plan([("T1136.001", GONDOLIN)], t, catalog=catalog)[0].code == ""
    assert plan([("T1136.001", GONDOLIN)], t, catalog=catalog, zones=("bench",))[0].code == "not_bench"
    assert "not_bench" in __import__("eregion_core.exercise_plan", fromlist=["REFUSALS"]).REFUSALS
    assert "not_ready" in er.SKIPS


def test_the_runners_recheck_holds_its_zones_before_each_wire(tmp_path):
    reads = {"n": 0}

    def read_target(rid):
        reads["n"] += 1
        return Target(rid, BENCH_RG, dict(PROD_TAGS if reads["n"] > 1 else BENCH_TAGS)), "vm-celebrimbor-gondolin"

    launched = []
    r = er.Runner(check=lambda: orodruin.Verdict(orodruin.ARMED, [], dict(CAP)), watch=lambda: "",
                  read_target=read_target, fault_targets=lambda: {}, isolated=lambda rid: "",
                  launch=lambda argv, env: launched.append(argv) or 0, publish=lambda s: None,
                  publish_contract=lambda v: None, catalog=load_catalog(), runs_dir=tmp_path / "runs",
                  say=lambda *_: None, zones=("bench",))
    status = r.run(xr.new([("T1136.001", GONDOLIN)]), {})
    assert launched == [] and status.wires[0].code == "refused_now"


def test_a_window_of_a_wire_is_bounded_by_the_time_its_runner_left_it():
    from eregion_core.exercise import MAX_DURATION_S, wire_window_s
    assert wire_window_s({"EREGION_MAX_RUN_S": "1500"}) == 1800
    assert wire_window_s({"EREGION_MAX_RUN_S": str(MAX_DURATION_S)}) == MAX_DURATION_S
    assert wire_window_s({}) == MAX_DURATION_S
    assert wire_window_s({"EREGION_MAX_RUN_S": "x"}) == MAX_DURATION_S


@pytest.mark.parametrize("change", [{"name": "Banc"}, {"sha256": "x"}, {"occurrence": "tuesday"},
                                    {"target": GONDOLIN}])
def test_the_statuss_drill_is_read_exactly(change):
    doc = {"request": "r-20261117T190500Z-abcdef", "state": "finished", "at": T0.isoformat(), "codes": [],
           "wires": [], "drill": {"name": "banc-hebdo", "sha256": SHA, "occurrence": T0.isoformat(), **change}}
    with pytest.raises(xr.RequestRefused):
        xr.read_status(doc)


# ── The arming's documents (eregion_core/drill_arming.py) ───────────────────────────

@pytest.mark.parametrize("targets", [["all"], [], ["ALL"], ["vm-a", "VM-A"], ["/subscriptions/x"]])
def test_an_arming_names_its_vms_never_all(targets):
    with pytest.raises(da.ArmingRefused):
        da.read_armed({"drill": "banc-hebdo", "sha256": SHA, "targets": targets, "armed_at": ARMED_AT, "image": ""})


@pytest.mark.parametrize("value", ["all", "", "vm-a,all", " , "])
def test_targets_all_is_refused_at_the_arming(value):
    with pytest.raises(da.ArmingRefused):
        da.parse_targets(value)


def test_the_permit_is_the_armings_name_fingerprint_and_time_nothing_else():
    armed = {"drill": "banc-hebdo", "sha256": SHA, "targets": ["vm-a"], "armed_at": ARMED_AT, "image": "x"}
    assert da.permit_of(armed) == {"drill": "banc-hebdo", "sha256": SHA, "armed_at": ARMED_AT}
    with pytest.raises(da.ArmingRefused):
        da.read_permit({**da.permit_of(armed), "targets": ["vm-a"]})
