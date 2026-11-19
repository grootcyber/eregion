"""The drill of the week from the operator's machine (DRL1a, infra/orodruin/drill_ops.py,
docs/design/drill-banc.md §2.1, §3.1, §5.1): `make orodruin-drill-check`, `-arm`, `-disarm`, the
three steps the kill gains, and the contract with the scheduled start of DRL1c (a Logic App).

Orodruin is a fake SSH (a callable that records each command and answers it), Azure a fake `az rest`
(the Logic App), the channel a fake blob container (the permit, the pulse): nothing connects, nothing
reaches Azure, no model. The oracles are written here, from the design.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import eregion_core.orodruin as orodruin
from eregion_core import drill as dr
from eregion_core import drill_arming as da
from eregion_core import exercise_channel as xc

ROOT = Path(__file__).resolve().parents[2]
ORO_DIR = ROOT / "infra" / "orodruin"
SUB = "00000000-0000-0000-0000-000000000000"
LOGIC = f"/subscriptions/{SUB}/resourceGroups/rg-orodruin/providers/Microsoft.Logic/workflows/la-orodruin-drill"
CHANNEL = "https://storodruin.blob.core.windows.net/exercises"
CRED = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="tok"))
NOW = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc)
SHA = dr.fingerprint((dr.shipped_dir() / "banc-hebdo.yaml").read_bytes())
FP = {"drill": "banc-hebdo", "sha256": SHA, "day": "tue", "at": "19:00", "on_calendar": "Tue *-*-* 19:00:00 UTC",
      "max_injections": 6, "max_run_s": 1800}
needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")


def _load(name: str):
    sys.path.insert(0, str(ORO_DIR))
    spec = importlib.util.spec_from_file_location(name, ORO_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ops():
    return _load("drill_ops")


@pytest.fixture(scope="module")
def kill_script():
    return _load("kill")


def _workflow(day="Tuesday", hour=18, minute=40, **rec):
    return {"id": LOGIC, "properties": {"state": "Disabled", "definition": {"triggers": {"weekly": {
        "type": "Recurrence", "recurrence": {"frequency": "Week", "interval": 1, "timeZone": "UTC",
                                             "schedule": {"weekDays": [day], "hours": [hour], "minutes": [minute]},
                                             **rec}}}}}}


class Logic:
    """`az rest` on the Logic App: GET reads it (or 404, or another failure), POST enable/disable."""

    def __init__(self, workflow=None, fail=""):
        self.workflow, self.fail = workflow, fail
        self.calls: list[tuple[str, str]] = []
        self.order: list[str] | None = None

    def __call__(self, args):
        method, url = args[args.index("--method") + 1], args[args.index("--url") + 1]
        path = url.split("?")[0]
        self.calls.append((method, path.rsplit("/", 1)[-1]))
        if self.order is not None:
            self.order.append(f"az {method} {path.rsplit('/', 1)[-1]}")
        if self.fail:
            raise RuntimeError(f"az rest --method {method} … exit 1: {self.fail}")
        if method == "get":
            if self.workflow is None:
                raise RuntimeError("az rest --method get … exit 3: (ResourceNotFound) The Resource was not found")
            return json.dumps(self.workflow)
        if path.endswith("/enable"):
            self.workflow["properties"]["state"] = "Enabled"
        elif path.endswith("/disable"):
            self.workflow["properties"]["state"] = "Disabled"
        return ""

    @property
    def state(self):
        return self.workflow["properties"]["state"] if self.workflow else None


class Channel:
    """The exercises container: the permit and the pulse, read, written, removed."""

    def __init__(self, blobs=None, fail_put=False):
        self.blobs = dict(blobs or {})
        self.fail_put = fail_put
        self.order: list[str] | None = None

    def _name(self, url):
        return url.split(CHANNEL + "/", 1)[1]

    def get(self, url, headers=None, params=None, timeout=None):
        name = self._name(url)
        if name not in self.blobs:
            return SimpleNamespace(ok=False, status_code=404, content=b"", headers={})
        return SimpleNamespace(ok=True, status_code=200, content=json.dumps(self.blobs[name]).encode(),
                               headers={"ETag": '"e1"'})

    def put(self, url, headers=None, data=None, timeout=None):
        if self.order is not None:
            self.order.append(f"put {self._name(url)}")
        if self.fail_put:
            return SimpleNamespace(ok=False, status_code=403)
        self.blobs[self._name(url)] = json.loads(data)
        return SimpleNamespace(ok=True, status_code=201)

    def delete(self, url, headers=None, timeout=None):
        if self.order is not None:
            self.order.append(f"delete {self._name(url)}")
        name = self._name(url)
        if name not in self.blobs:
            return SimpleNamespace(ok=False, status_code=404)
        del self.blobs[name]
        return SimpleNamespace(ok=True, status_code=202)


class Oro:
    """Orodruin by SSH: each command recorded; the image answers the fingerprint and the dry check;
    `fail` makes the commands holding one of its words fail."""

    def __init__(self, fp=FP, armed=None, fail=(), order=None):
        self.fp, self.armed, self.fail = fp, armed, tuple(fail)
        self.commands: list[str] = []
        self.files: dict[str, str] = {}
        self.order = order

    def __call__(self, command, stdin=None):
        self.commands.append(command)
        if self.order is not None:
            self.order.append(f"ssh {command.split()[0]}")
        if any(w in command for w in self.fail):
            return 1, "", "permission denied"
        if "scheduled_drill fingerprint" in command:
            return 0, json.dumps(self.fp) + "\n", ""
        if "scheduled_drill check" in command:
            return 0, "✓ the drill banc-hebdo in this image\n", ""
        if command.startswith("test -f drill/armed.json"):
            return (0, json.dumps(self.armed), "") if self.armed else (1, "", "")
        if command.startswith("head -c 200 .eregion-image"):
            return 0, "abc123 sha256:00\n", ""
        if stdin is not None:
            self.files[command] = stdin
        return 0, "", ""

    @property
    def writes(self):
        return [c for c in self.commands if not (c.startswith("test -f") or c.startswith("head -c")
                                                  or "scheduled_drill" in c)]


def _arm(ops, oro, logic, channel, targets=("vm-celebrimbor-gondolin",), said=None):
    said = [] if said is None else said
    code = ops.arm("banc-hebdo", list(targets), oro=oro, oro_run="docker run …", user="orodruin",
                   logic_id=LOGIC, channel=CHANNEL, run=logic, credential=CRED, put=channel.put,
                   now=lambda: NOW, say=said.append)
    return code, said


def _disarm(ops, oro, logic, channel, said=None, **kw):
    said = [] if said is None else said
    code = ops.disarm(oro=oro, logic_id=kw.pop("logic_id", LOGIC), channel=CHANNEL, run=logic, credential=CRED,
                      get=channel.get, put=channel.put, delete=channel.delete, now=lambda: NOW,
                      say=said.append, **kw)
    return code, said


def _armed_pulse():
    return da.pulse(state="armed", drill="banc-hebdo", sha256=SHA, next_at="2026-11-17T19:00:00+00:00",
                    image="abc123 sha256:00", at=NOW.isoformat())


# ── The kill: seven steps, in their order (§3.1) ─────────────────────────────────────

ORDER = ["revoke", "disable_start", "remove_permit", "cancel", "stop", "close", "disarm"]


def _step(order, name, error=None):
    def step():
        order.append(name)
        if error:
            raise error
    return step


def _kill(order, failing=""):
    steps = {n: _step(order, n, RuntimeError("403") if n == failing else None) for n in ORDER}
    return orodruin.kill(steps["revoke"], steps["cancel"], steps["stop"], steps["close"],
                         disable_start=steps["disable_start"], remove_permit=steps["remove_permit"],
                         disarm=steps["disarm"])


def test_the_kill_revokes_then_disables_the_start_removes_the_permit_then_stops_and_says_disarmed():
    order = []
    assert _kill(order) == []
    assert order == ORDER


@pytest.mark.parametrize("failing", ORDER)
def test_a_failed_step_of_the_kill_is_reported_and_never_stops_the_next(failing):
    order = []
    failures = _kill(order, failing)
    assert order == ORDER
    assert len(failures) == 1 and failures[0].startswith(f"{failing}:")


def _kill_steps(ops, logic, channel, said=None, logic_id=LOGIC, channel_url=CHANNEL, lines=None):
    lines = [] if lines is None else lines
    return ops.kill_steps(logic_id, channel=channel_url, run=logic, credential=CRED, get=channel.get,
                          put=channel.put, delete=channel.delete, say=lines.append, now=lambda: NOW,
                          said=said), lines


def test_the_kills_drill_steps_disable_the_start_remove_the_permit_and_write_disarmed_killed(ops):
    logic = Logic(_workflow())
    logic.workflow["properties"]["state"] = "Enabled"
    channel = Channel({xc.PERMIT_BLOB: {"drill": "banc-hebdo", "sha256": SHA, "armed_at": NOW.isoformat()},
                       xc.DRILL_BLOB: _armed_pulse()})
    said = {}
    steps, lines = _kill_steps(ops, logic, channel, said)
    for name in ("disable_start", "remove_permit", "disarm"):
        steps[name]()
    assert logic.state == "Disabled" and ("post", "disable") in logic.calls
    assert xc.PERMIT_BLOB not in channel.blobs
    pulse = da.read_pulse(channel.blobs[xc.DRILL_BLOB])
    assert (pulse["state"], pulse["reason"]) == ("disarmed", "killed")
    # What the armed pulse said is kept: the drill, its fingerprint.
    assert (pulse["drill"], pulse["sha256"]) == ("banc-hebdo", SHA)
    assert ops.summary(said) == "drill: scheduled start disabled, permit removed; refused until re-armed"


@pytest.mark.parametrize("logic_id, workflow", [("", None), (LOGIC, None)])
def test_no_scheduled_start_is_said_never_a_disabling(ops, logic_id, workflow):
    """DRL1c not applied (no output), or its Logic App gone (404): « no scheduled start », no POST."""
    logic, channel, said = Logic(workflow), Channel(), {}
    steps, lines = _kill_steps(ops, logic, channel, said, logic_id=logic_id)
    steps["disable_start"]()
    steps["remove_permit"]()
    assert not [c for c in logic.calls if c[0] == "post"]
    assert any("no scheduled start" in line for line in lines)
    summary = ops.summary(said)
    assert "disabled" not in summary and "permit removed" not in summary
    assert summary == "drill: no scheduled start, no permit in the channel; refused until re-armed"


@pytest.mark.parametrize("logic_id, fail", [(LOGIC, "AuthorizationFailed"), ("unreadable", "")])
def test_a_scheduled_start_that_does_not_read_is_a_failure_never_an_absence(ops, logic_id, fail):
    """The Logic App unreadable (403, az login lapsed), or Terraform's state unreadable (the sentinel):
    the kill's step fails, and the kill says it."""
    logic = Logic(_workflow(), fail=fail)
    steps, lines = _kill_steps(ops, logic, Channel(), {}, logic_id=logic_id)
    failures = orodruin.kill(lambda: None, lambda: None, lambda: None, lambda: None,
                             disable_start=steps["disable_start"])
    assert len(failures) == 1 and failures[0].startswith("disable_start:")
    assert not any("no scheduled start" in line for line in lines)


def test_without_a_channel_the_permit_and_the_pulse_are_failures(ops):
    steps, _ = _kill_steps(ops, Logic(None), Channel(), {}, channel_url="")
    with pytest.raises(RuntimeError, match="permit"):
        steps["remove_permit"]()
    with pytest.raises(RuntimeError, match="pulse"):
        steps["disarm"]()


def _drill_kill(kill_script, monkeypatch, capsys, workflow, permit):
    """kill.py's main, its four steps faked away: the drill's three run for real on fakes."""
    logic = Logic(workflow)
    monkeypatch.setattr(kill_script, "az", logic)
    gone = {"permit": permit}

    def delete_drill(name, **kw):
        was, gone["permit"] = gone["permit"], False
        return was
    monkeypatch.setattr(kill_script.drill_ops.xc, "delete_drill", delete_drill)
    monkeypatch.setattr(kill_script.drill_ops, "write_pulse", lambda doc, **kw: None)
    monkeypatch.setattr(kill_script.drill_ops, "disarmed_pulse", lambda reason, **kw: {})

    def fake_kill(*steps, **drill):
        for name in ("disable_start", "remove_permit", "disarm"):
            drill[name]()
        return []
    monkeypatch.setattr(kill_script, "kill", fake_kill)
    code = kill_script.main(["oid-1", "/subscriptions/x/vm", "--subscription", SUB, "--channel", CHANNEL,
                             "--drill-autostart", LOGIC])
    return code, capsys.readouterr().out.strip().splitlines()


def test_the_kill_says_what_its_drill_steps_did_last_never_a_disabling_that_did_not_happen(
        kill_script, monkeypatch, capsys):
    code, out = _drill_kill(kill_script, monkeypatch, capsys, None, False)
    assert code == 0
    assert out[-1] == "drill: no scheduled start, no permit in the channel; refused until re-armed"
    assert "drill: no scheduled start (DRL1c not applied, or gone)" in out
    enabled = _workflow()
    enabled["properties"]["state"] = "Enabled"
    code, out = _drill_kill(kill_script, monkeypatch, capsys, enabled, True)
    assert code == 0 and out[-1] == "drill: scheduled start disabled, permit removed; refused until re-armed"
    # Each step's own line first, the summary after them.
    assert out.index("drill: scheduled start disabled") < out.index("drill: permit removed") < len(out) - 1


# ── The scheduled start of DRL1c: its contract ─────────────────────────────────────

def test_the_scheduled_start_is_read_as_one_weekly_recurrence_in_utc(ops):
    assert ops.autostart_at(_workflow()) == ("tue", "18:40")
    for bad in (_workflow(frequency="Day"), _workflow(interval=2), _workflow(timeZone="Romance Standard Time")):
        with pytest.raises(ValueError):
            ops.autostart_at(bad)
    two = _workflow()
    two["properties"]["definition"]["triggers"]["other"] = {"type": "Request"}
    with pytest.raises(ValueError):
        ops.autostart_at(two)


@pytest.mark.parametrize("day, at, want", [("tue", "19:00", ("tue", "18:40")), ("mon", "00:10", ("sun", "23:50"))])
def test_the_scheduled_start_is_the_drills_hour_less_20_min_across_midnight(ops, day, at, want):
    assert ops.expected_at(dr.Schedule(day, at, 6, 1800)) == want


@pytest.mark.parametrize("outputs, want", [
    ("{}", ""),                                                        # DRL1c not applied
    (json.dumps({"public_ip": {"value": "10.0.0.5"}}), ""),
    (json.dumps({"drill_autostart_id": {"value": None}}), ""),
    (json.dumps({"drill_autostart_id": {"value": LOGIC}}), LOGIC),
    (json.dumps({"drill_autostart_id": {"value": "/subscriptions/x/other"}}), "unreadable"),
    (json.dumps({"drill_autostart_id": "nope"}), "unreadable"),
    ("", "unreadable"),                                                # the state did not read
    ("Error: Backend initialization required", "unreadable"),
    ("[]", "unreadable"),
])
def test_terraforms_output_is_read_in_three_cases_never_an_unreadable_state_for_an_absence(ops, outputs, want):
    assert ops.autostart_id(outputs) == want


# ── check: nothing written ─────────────────────────────────────────────────────────

def test_the_dry_check_writes_nothing_on_orodruin_nor_on_azure(ops):
    oro, logic, said = Oro(), Logic(_workflow()), []
    code = ops.check("banc-hebdo", [], oro=oro, oro_run="docker run …", logic_id=LOGIC, run=logic,
                     say=said.append)
    assert code == 0, said
    assert oro.writes == [] and all(m == "get" for m, _ in logic.calls)
    assert any("scheduled start" in s and "✓" in s for s in said)


@pytest.mark.parametrize("workflow, said_", [(None, "apply first"), (_workflow(hour=19, minute=0), "apply first")])
def test_the_dry_check_says_a_scheduled_start_absent_or_at_another_hour(ops, workflow, said_):
    oro, said = Oro(), []
    code = ops.check("banc-hebdo", [], oro=oro, oro_run="", logic_id=LOGIC, run=Logic(workflow), say=said.append)
    assert code == 1 and any(said_ in s for s in said) and oro.writes == []


# ── check: the scheduled start's state, against the arming (DRL1e) ───────────────────

ARMED = {"drill": "banc-hebdo", "sha256": SHA, "targets": ["vm-celebrimbor-gondolin"],
         "armed_at": "2026-11-16T10:00:00+00:00", "image": "abc123 sha256:00"}


def _check(ops, oro, logic):
    said = []
    code = ops.check("banc-hebdo", [], oro=oro, oro_run="docker run …", logic_id=LOGIC, run=logic, say=said.append)
    return code, said


def _with_state(state):
    wf = _workflow()
    if state is None:
        del wf["properties"]["state"]
    else:
        wf["properties"]["state"] = state
    return wf


def test_the_check_says_armed_but_scheduled_start_disabled_re_arm(ops):
    """An apply that redeployed the Logic App put it back Disabled: armed.json says armed, and the
    check says it — never « ✓ scheduled start » alone, the missed occurrence seen only at Imladris's
    not_run (DRL1e, M6481, M6482). Nothing written."""
    oro, logic = Oro(armed=ARMED), Logic(_with_state("Disabled"))
    code, said = _check(ops, oro, logic)
    assert code == 1, said
    assert any(s.startswith("✗ armed but scheduled start disabled: re-arm") for s in said), said
    assert oro.writes == [] and all(m == "get" for m, _ in logic.calls)
    # One read of the Logic App: its hour and its state, the same GET.
    assert logic.calls == [("get", "la-orodruin-drill")]


def test_the_check_says_the_scheduled_start_enabled_for_the_armed_drill(ops):
    oro, logic = Oro(armed=ARMED), Logic(_with_state("Enabled"))
    code, said = _check(ops, oro, logic)
    assert code == 0, said
    assert "✓ scheduled start enabled: it wakes Orodruin for the armed drill" in said
    assert not any("re-arm" in s for s in said)


@pytest.mark.parametrize("workflow, fail, why", [
    (_workflow(), "AuthorizationFailed", "AuthorizationFailed"),     # the GET refused: az login, a 403
    (_with_state(None), "", "no properties.state"),                    # read, its state absent
    (_with_state("Suspended"), "", "'Suspended'"),                     # a state that does not wake it
])
def test_an_unreadable_state_against_the_arming_is_said_never_taken_for_enabled(ops, workflow, fail, why):
    """The Logic App unreadable, or its state absent or another than Enabled/Disabled: the check says
    the state does not read, exits 1, and still says the arming and the dry check (DRL1e)."""
    oro, logic = Oro(armed=ARMED), Logic(workflow, fail=fail)
    code, said = _check(ops, oro, logic)
    assert code == 1, said
    line = next(s for s in said if s.startswith("✗ armed but the scheduled start's state does not read"))
    assert why in line and "never taken for enabled" in line
    assert any(s.startswith("✓ arming: banc-hebdo") for s in said)
    assert any("scheduled_drill check" in c for c in oro.commands) and oro.writes == []


def test_the_check_without_an_arming_says_the_state_and_fails_only_on_the_rest(ops):
    """Nothing armed: Disabled is the state the disarming leaves, said; Enabled wakes Orodruin for
    nothing, a warning — neither fails the check."""
    for state, line in (("Disabled", "· scheduled start disabled (nothing armed)"),
                        ("Enabled", "! scheduled start enabled with nothing armed")):
        code, said = _check(ops, Oro(), Logic(_with_state(state)))
        assert code == 0 and any(s.startswith(line) for s in said), said


# ── The shutdown of 23:00 UTC: the arming refuses a drill it would cut (DRL1e) ───────────

@pytest.mark.parametrize("day, at, max_run_s, want", [
    ("tue", "19:00", 1800, ""),          # the shipped drill: ends 19:30, its service 20:01:30
    ("tue", "22:30", 1800, "refuse"),    # its budget ends at 23:00 itself
    ("tue", "22:50", 1800, "refuse"),    # ends 23:20
    ("tue", "23:10", 60, "refuse"),      # woken 22:50, shut down at 23:00 before its hour
    ("sun", "22:50", 600, "refuse"),     # across the week's end: Sunday's shutdown
    ("tue", "22:00", 1800, "warn"),      # its budget ends 22:30, its service's ceiling 23:01:30
    ("tue", "21:59", 1800, "warn"),      # the ceiling and the stop's grace end 23:00:30
    ("tue", "21:58", 1800, ""),          # they end 22:59:30
    ("mon", "00:10", 3600, ""),          # woken Sunday 23:50, after Sunday's shutdown
    ("tue", "23:20", 600, "refuse"),     # woken at 23:00, the shutdown's own minute
    ("tue", "23:30", 3600, ""),          # woken 23:10, after the shutdown; ends 00:30
])
def test_the_shutdown_guard_refuses_a_certain_cut_and_warns_at_the_limit(ops, day, at, max_run_s, want):
    verdict, why = ops.shutdown_guard(dr.Schedule(day, at, 6, max_run_s))
    assert verdict == want, (day, at, max_run_s, why)
    assert (why == "") == (want == "")
    if want:
        assert "23:00 UTC" in why


def _arm_at(ops, at, max_run_s, autostart):
    fp = {**FP, "at": at, "max_run_s": max_run_s, "on_calendar": f"Tue *-*-* {at}:00 UTC"}
    oro, logic, channel = Oro(fp=fp), Logic(_workflow(hour=autostart[0], minute=autostart[1])), Channel()
    code, said = _arm(ops, oro, logic, channel)
    return code, said, oro, logic, channel


def test_the_arming_of_a_drill_that_overruns_23_utc_is_refused_and_writes_nothing(ops):
    """The drill tue 22:50, 30 min: its scheduled start right (22:30), but its budget ends 23:20,
    after Orodruin's shutdown — refused, nothing on Orodruin, nothing in the channel, nothing enabled
    (DRL1e, M6483, M6484)."""
    code, said, oro, logic, channel = _arm_at(ops, "22:50", 1800, (22, 30))
    assert code == 1 and said[-1].endswith("nothing armed"), said
    assert "shutdown of 23:00 UTC" in said[-1] and "would be cut" in said[-1]
    assert oro.writes == [] and channel.blobs == {}
    assert not [c for c in logic.calls if c[0] == "post"]


def test_the_arming_at_the_limit_of_23_utc_warns_and_goes_on(ops):
    """The drill tue 22:00, 30 min: its budget ends 22:30, its service's ceiling after 23:00 — a
    warning said before the steps, and the arming goes on (DRL1e)."""
    code, said, oro, logic, channel = _arm_at(ops, "22:00", 1800, (21, 40))
    assert code == 0, said
    warn = [i for i, s in enumerate(said) if s.startswith("! ")]
    assert len(warn) == 1 and "23:00 UTC" in said[warn[0]] and "may be cut" in said[warn[0]]
    assert warn[0] < min(i for i, s in enumerate(said) if s.startswith("✓ "))
    assert logic.state == "Enabled"


def test_the_check_says_the_shutdown_guard(ops):
    """The check says the same guard, and a refusal fails it."""
    fp = {**FP, "at": "22:50", "max_run_s": 1800}
    said = []
    code = ops.check("banc-hebdo", [], oro=Oro(fp=fp), oro_run="", logic_id=LOGIC,
                     run=Logic(_workflow(hour=22, minute=30)), say=said.append)
    assert code == 1 and any(s.startswith("✗ the drill (tue 22:50 UTC") for s in said), said
    code, said = _check(ops, Oro(), Logic(_workflow()))
    assert code == 0 and "✓ Orodruin's shutdown of 23:00 UTC: the drill ends before it" in said


def test_the_service_s_ceiling_the_guard_counts_is_the_unit_s_own(ops):
    """The guard counts RuntimeMaxSec and the stop's grace as the service says them."""
    service = ops.units(dr.Schedule("tue", "19:00", 6, 1800), "orodruin")[ops.SERVICE]
    assert f"RuntimeMaxSec={ops.RUNTIME_MAX_S}\n" in service
    assert f"docker stop --time {ops.STOP_S} " in service
    assert (ops.RUNTIME_MAX_S, ops.STOP_S) == (3600, 90)


# ── arm: refused before anything is written, else each step said ───────────────────

@pytest.mark.parametrize("workflow", [None, _workflow(hour=19, minute=0), _workflow(day="Wednesday"),
                                      _workflow(frequency="Day")])
def test_the_arming_refuses_apply_first_and_writes_nothing(ops, workflow):
    """The Logic App absent, at the drill's own hour, on another day, or not weekly: « apply first »,
    nothing on Orodruin, nothing in the channel, nothing enabled."""
    oro, logic, channel = Oro(), Logic(workflow), Channel()
    code, said = _arm(ops, oro, logic, channel)
    assert code == 1 and any("apply first" in s for s in said) and said[-1].endswith("nothing armed")
    assert oro.writes == [] and channel.blobs == {}
    assert not [c for c in logic.calls if c[0] == "post"]


def test_an_unreadable_scheduled_start_refuses_the_arming(ops):
    oro, channel = Oro(), Channel()
    code, said = _arm(ops, oro, Logic(_workflow(), fail="AuthorizationFailed"), channel)
    assert code == 1 and oro.writes == [] and channel.blobs == {}


def test_the_arming_writes_the_arming_the_units_the_timer_then_the_permit_the_start_and_the_pulse(ops):
    order: list[str] = []
    oro, logic, channel = Oro(order=order), Logic(_workflow()), Channel()
    logic.order = channel.order = order
    code, said = _arm(ops, oro, logic, channel)
    assert code == 0, said
    armed = json.loads(next(v for k, v in oro.files.items() if "armed.json" in k))
    assert da.read_armed(armed)["targets"] == ["vm-celebrimbor-gondolin"] and armed["sha256"] == SHA
    assert any("umask 077" in c for c in oro.commands)
    unit = next(v for k, v in oro.files.items() if "eregion-drill.timer" in k)
    assert "OnCalendar=Tue *-*-* 19:00:00 UTC" in unit and "Persistent=false" in unit
    assert channel.blobs[xc.PERMIT_BLOB] == da.permit_of(armed)
    assert logic.state == "Enabled"
    assert da.read_pulse(channel.blobs[xc.DRILL_BLOB])["state"] == "armed"
    # On Orodruin first, then the operator's writes: the permit, the scheduled start, the pulse.
    writes = [o for o in order if not o.startswith("az get")]
    assert writes.index("put orodruin/drill-permit.json") > max(i for i, o in enumerate(writes) if o.startswith("ssh"))
    assert writes[-3:] == ["put orodruin/drill-permit.json", "az post enable", "put orodruin/drill.json"]


@pytest.mark.parametrize("fails, done", [("systemctl enable", 3), ("permit", 4)])
def test_an_arming_that_fails_midway_says_it_is_partial_and_goes_no_further(ops, fails, done):
    oro = Oro(fail=(fails,) if fails != "permit" else ())
    logic, channel = Logic(_workflow()), Channel(fail_put=fails == "permit")
    code, said = _arm(ops, oro, logic, channel)
    assert code == 1
    assert any("the arming is partial" in s for s in said)
    assert sum(1 for s in said if s.startswith("✓")) == done
    # Never the scheduled start enabled after a step that failed.
    assert logic.state == "Disabled"


@pytest.mark.parametrize("value", ["all", "ALL", "vm-a,all", ""])
def test_targets_all_is_refused_before_anything(ops, value, tmp_path):
    env = {"EREGION_DRILL": "banc-hebdo", "EREGION_DRILL_TARGETS": value, "DRILL_ORO_SSH": "ssh orodruin@10.0.0.5"}
    code = ops.main(["arm"], env=env, cwd=str(tmp_path), here=str(tmp_path))
    assert code == 1


def test_the_arming_is_refused_in_a_lots_session(ops, tmp_path):
    env = {"EREGION_AGENT_SESSION": "1", "EREGION_DRILL": "banc-hebdo", "EREGION_DRILL_TARGETS": "vm-a"}
    assert ops.main(["arm"], env=env, cwd=str(tmp_path), here=str(tmp_path)) == 1


# ── disarm: each step said, exit 1 if one fails ─────────────────────────────────────

def _armed_channel():
    return Channel({xc.PERMIT_BLOB: {"drill": "banc-hebdo", "sha256": SHA, "armed_at": NOW.isoformat()},
                    xc.DRILL_BLOB: _armed_pulse()})


def test_the_disarming_does_and_says_each_of_its_steps(ops):
    oro, logic, channel = Oro(), Logic(_workflow()), _armed_channel()
    logic.workflow["properties"]["state"] = "Enabled"
    code, said = _disarm(ops, oro, logic, channel)
    assert code == 0 and said[-1] == "disarmed"
    assert any("systemctl disable --now eregion-drill.timer" in c for c in oro.commands)
    assert any(c.startswith("rm -f drill/armed.json") for c in oro.commands)
    assert xc.PERMIT_BLOB not in channel.blobs and logic.state == "Disabled"
    pulse = da.read_pulse(channel.blobs[xc.DRILL_BLOB])
    assert (pulse["state"], pulse["reason"]) == ("disarmed", "operator")
    for what in ("the timer disabled", "the arming removed", "the permit: permit removed",
                 "the scheduled start: scheduled start disabled", "the pulse"):
        assert any(s.startswith(f"✓ {what}") for s in said), (what, said)


@pytest.mark.parametrize("fails", ["systemctl", "rm -f drill/armed.json", "logic", "pulse"])
def test_a_step_of_the_disarming_that_fails_exits_1_and_the_others_are_still_done(ops, fails):
    oro = Oro(fail=(fails,) if fails not in ("logic", "pulse") else ())
    logic = Logic(_workflow(), fail="AuthorizationFailed" if fails == "logic" else "")
    channel = _armed_channel()
    channel.fail_put = fails == "pulse"
    code, said = _disarm(ops, oro, logic, channel)
    assert code == 1 and "INCOMPLETE" in said[-1]
    assert sum(1 for s in said if s.startswith("✗")) == 2   # the step, and the summary
    assert xc.PERMIT_BLOB not in channel.blobs      # the permit removed whatever failed


def test_the_disarming_without_a_scheduled_start_says_so_and_succeeds(ops):
    code, said = _disarm(ops, Oro(), Logic(None), _armed_channel())
    assert code == 0 and any("no scheduled start" in s for s in said)


def test_the_disarming_with_terraforms_state_unreadable_fails_never_no_scheduled_start(ops):
    code, said = _disarm(ops, Oro(), Logic(_workflow()), _armed_channel(), logic_id="unreadable")
    assert code == 1 and not any("no scheduled start" in s for s in said)


def test_the_disarming_without_orodruin_still_removes_the_permit_and_the_start_and_says_what_it_missed(ops):
    logic, channel = Logic(_workflow()), _armed_channel()
    logic.workflow["properties"]["state"] = "Enabled"
    code, said = _disarm(ops, None, logic, channel, unreached="no address: Orodruin stopped")
    assert code == 1
    assert xc.PERMIT_BLOB not in channel.blobs and logic.state == "Disabled"
    missed = [s for s in said if s.startswith("✗ the timer") or s.startswith("✗ the arming")]
    assert len(missed) == 2 and all("Orodruin not reached (no address: Orodruin stopped)" in s for s in missed)


def test_the_disarming_by_its_command_goes_on_without_an_address(ops, monkeypatch, tmp_path):
    seen = {}

    def disarm(**kw):
        seen.update(kw)
        return 1
    monkeypatch.setattr(ops, "disarm", disarm)
    env = {"DRILL_ORO_SSH": "ssh -o X=y orodruin@", "DRILL_AUTOSTART": LOGIC, "DRILL_CHANNEL": CHANNEL}
    assert ops.main(["disarm"], env=env, cwd=str(tmp_path), here=str(tmp_path)) == 1
    assert seen["oro"] is None and "no address" in seen["unreached"]
    env = {"DRILL_ORO_SSH": "ssh orodruin@10.0.0.5", "DRILL_ORO_UNREACHED": "its host key not verified"}
    ops.main(["disarm"], env=env, cwd=str(tmp_path), here=str(tmp_path))
    assert seen["oro"] is None and seen["unreached"] == "its host key not verified"
    # The arming and the check never go on without Orodruin.
    for cmd in ("check", "arm"):
        env = {"DRILL_ORO_SSH": "ssh orodruin@", "EREGION_DRILL": "banc-hebdo", "EREGION_DRILL_TARGETS": "vm-a"}
        assert ops.main([cmd], env=env, cwd=str(tmp_path), here=str(tmp_path)) == 1


# ── The Makefile: the scheduled start read from Terraform, the disarming without Orodruin ──

def _fake_bin(tmp_path, terraform: str):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    tf = bindir / "terraform"
    tf.write_text("#!/bin/sh\n" + terraform)
    tf.chmod(0o755)
    return bindir


@needs_make
@pytest.mark.parametrize("terraform, want", [
    ('case "$*" in *-json*) echo "{}";; *) exit 1;; esac\n', '--drill-autostart ""'),
    ('case "$*" in *-json*) echo \'{"drill_autostart_id": {"value": "' + LOGIC + '"}}\';; *) exit 1;; esac\n',
     f'--drill-autostart "{LOGIC}"'),
    ("echo 'Error: state unreadable' >&2; exit 1\n", '--drill-autostart "unreadable"'),
])
def test_the_kill_reads_the_scheduled_start_in_three_cases_never_an_unreadable_state_for_none(
        tmp_path, terraform, want):
    bindir = _fake_bin(tmp_path, terraform)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path)}
    res = subprocess.run(["make", "-n", "-s", "--no-print-directory", "-C", str(ROOT), "orodruin-kill",
                          f"PYTHON={sys.executable}"], capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode == 0, res.stderr
    assert want in res.stdout


@needs_make
def test_the_disarming_target_runs_without_orodruin_and_says_why(tmp_path):
    bindir = _fake_bin(tmp_path, 'case "$*" in *-json*) echo "{}";; *) exit 1;; esac\n')
    log = tmp_path / "python.log"
    fake_py = bindir / "python"
    fake_py.write_text(f"#!/bin/sh\nprintf '%s|%s\\n' \"$*\" \"$DRILL_ORO_UNREACHED\" >> {log}\n")
    fake_py.chmod(0o755)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path)}
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), "orodruin-drill-disarm",
                          f"PYTHON={fake_py}"], capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode == 0, res.stderr
    lines = log.read_text().splitlines()
    assert lines[-1].startswith("infra/orodruin/drill_ops.py disarm|no address")


# ── The service's docker run: the options of Annatar's runs on Orodruin (DRL1d) ──────────
#
# The drill plays Annatar's runs (a technique, never a fault in v1: eregion_core/drill.py, eligible),
# the control-plane library's among them, whose Terraform executes its providers under the run HOME.
# Its service runs as ORO_RUN does: ORO_HARDEN then ORO_EXEC_HOME, read in the Makefile, no more,
# no less; /tmp stays noexec; the run HOME is where the adapter builds it.

# The drill's own launch options, never execution options (with their argument for the second set).
_LAUNCH_FLAGS = {"--rm", "--init"}
_LAUNCH_ARGS = {"--pull", "--name", "--env-file", "-v"}


def _makefile() -> str:
    return (ROOT / "Makefile").read_text(encoding="utf-8")


def _make_var(name: str, text: str) -> str:
    """A Makefile definition's value, ``NAME = …`` or ``NAME := …`` (a target's ``export`` too)."""
    import re
    m = re.search(rf"(?m)^{re.escape(name)}\s*:?=(.*)$", text)
    assert m, f"{name} not defined in the Makefile"
    return m.group(1).strip()


def _expand(value: str, text: str) -> str:
    """A Makefile value's simple variables expanded as make does (``$(X)``, recursively)."""
    import re
    for _ in range(5):
        value = re.sub(r"\$\(([A-Z_]+)\)", lambda m: _make_var(m.group(1), text), value)
    assert "$(" not in value, value
    return value


# What a Makefile run def carries that is not an execution option, each with its argument: its
# configuration, its mounts, its pull policy (``$(call ORO_MOUNT,…)`` is a mount too).
_DEF_LAUNCH_ARGS = {"--env-file", "-v", "--pull"}


def _run_options(definition: str, text: str) -> list[str]:
    """The execution options of a Makefile ``docker run --rm … $(ORO_IMAGE)`` definition, expanded:
    every word up to the image, ``--env-file``, ``-v``, ``$(call ORO_MOUNT,…)`` and ``--pull``
    set apart — an option after ``--env-file`` is read too (DRL1e)."""
    import re
    assert definition.count("docker run --rm ") == 1 and " $(ORO_IMAGE)" in definition, definition
    seg = definition.split("docker run --rm ", 1)[1].split(" $(ORO_IMAGE)", 1)[0]
    seg = re.sub(r"\$\(call ORO_MOUNT,[a-z]+\)", " ", seg)
    words, out, i = _expand(seg, text).split(), [], 0
    while i < len(words):
        if words[i] in _DEF_LAUNCH_ARGS:
            i += 2
        else:
            out.append(words[i])
            i += 1
    return out


def _exec_start(ops) -> list[str]:
    import shlex
    service = ops.units(dr.Schedule("tue", "19:00", 6, 1800), "orodruin")[ops.SERVICE]
    starts = [ln for ln in service.splitlines() if ln.startswith("ExecStart=")]
    assert len(starts) == 1, starts
    argv = shlex.split(starts[0].split("=", 1)[1])
    assert argv[:2] == ["/usr/bin/docker", "run"], argv
    return argv


def _drill_options(argv: list[str], image: str) -> list[str]:
    """What the service's docker run carries beyond its launch options, up to the image."""
    rest, i = [], 2
    while argv[i] != image:
        if argv[i] in _LAUNCH_FLAGS:
            i += 1
        elif argv[i] in _LAUNCH_ARGS:
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    return rest


def _tmpfs(argv: list[str]) -> dict[str, list[str]]:
    """Each ``--tmpfs`` of a docker run: its path, its mount options."""
    out = {}
    for i, a in enumerate(argv):
        if a == "--tmpfs":
            path, _, opts = argv[i + 1].partition(":")
            out[path] = [o for o in opts.split(",") if o]
    return out


def test_the_drills_hardening_is_the_makefiles_oro_harden_and_its_exec_home_oro_exec_home(ops):
    """The two copies, word for word: HARDEN is ORO_HARDEN, EXEC_HOME is ORO_EXEC_HOME, and the
    service's options are the one then the other (M5992, M5993, M5995, M5999, M6000)."""
    text = _makefile()
    assert ops.HARDEN.split() == _make_var("ORO_HARDEN", text).split()
    assert ops.EXEC_HOME.split() == _make_var("ORO_EXEC_HOME", text).split()
    assert ops.RUN_OPTS.split() == ops.HARDEN.split() + ops.EXEC_HOME.split()


def test_the_drills_service_runs_with_the_options_of_annatars_runs_no_more_no_less(ops):
    """The service's docker run carries ORO_RUN's options, read in the Makefile and expanded:
    ORO_HARDEN then ORO_EXEC_HOME — one dropped, or one more, and the drill diverges from the run
    that passes by hand (M5991, M5996, M5997). Every Annatar run def of the Makefile carries the
    same: ORO_RUN is Annatar's run."""
    text = _makefile()
    want = _run_options(_make_var("ORO_RUN", text), text)
    assert want == _make_var("ORO_HARDEN", text).split() + _make_var("ORO_EXEC_HOME", text).split()
    for other in ("ORO_RUN_REQUEST", "bench-preflight: export BENCH_ORO_RUN", "bench-run-go: export BENCH_ORO_RUN"):
        assert _run_options(_make_var(other, text), text) == want, other
    argv = _exec_start(ops)
    assert _drill_options(argv, ops.IMAGE) == want
    # The same configuration and image as ORO_RUN.
    oro_run = _make_var("ORO_RUN", text)
    assert argv[argv.index("--env-file") + 1] == oro_run.split("--env-file ", 1)[1].split()[0]
    assert ops.IMAGE == _make_var("ORO_IMAGE", text) and oro_run.endswith("$(ORO_IMAGE)")


def test_the_drills_run_home_is_the_exec_tmpfs_where_the_adapter_builds_it_and_tmp_stays_noexec(ops):
    """One executable tmpfs, at the path where Annatar's adapter builds the run HOME (its EXEC_HOME),
    and no HOME given another way (M5993, M5994); /tmp a tmpfs without exec (M5992); the root
    read-only, no capability, no privilege gained (M5995, M6000)."""
    from annatar.executors import stratus_host
    argv = _exec_start(ops)
    mounts = _tmpfs(argv)
    assert {p for p, o in mounts.items() if "exec" in o} == {stratus_host.EXEC_HOME}, mounts
    assert mounts[stratus_host.EXEC_HOME] == ["exec"]
    assert "/tmp" in mounts and "exec" not in mounts["/tmp"], mounts
    opts = _drill_options(argv, ops.IMAGE)
    assert "--read-only" in opts and opts[opts.index("--cap-drop") + 1] == "ALL"
    assert opts[opts.index("--security-opt") + 1] == "no-new-privileges:true"
    assert not any(o.startswith(("--privileged", "--cap-add")) for o in opts)
    assert not any(a in ("-e", "--env") or a.startswith(("--env=", "HOME=")) for a in argv)


def test_the_drills_reads_that_play_no_run_get_nothing_more_than_the_hardening():
    """fingerprint and check (ORO_DRILL_RUN) play no Annatar run: ORO_HARDEN alone, never the exec
    tmpfs — as the contract's and Gothmog's runs (M5998)."""
    text = _makefile()
    assert _run_options(_make_var("ORO_DRILL_RUN", text), text) == _make_var("ORO_HARDEN", text).split()


@pytest.mark.parametrize("after", ["--cap-add SYS_ADMIN", "--privileged", "--tmpfs /tmp:exec", "-e HOME=/tmp"])
def test_an_option_after_the_env_file_or_the_mounts_is_read_never_missed(after):
    """The reading goes up to the image, not to ``--env-file``: an option posed after the
    configuration or among the mounts, in ORO_RUN or ORO_DRILL_RUN, is an execution option, and the
    parity sees it (DRL1e, M6487); the launch options alone are set apart."""
    text = _makefile()
    want = _make_var("ORO_HARDEN", text).split() + _make_var("ORO_EXEC_HOME", text).split()
    for where in ("--env-file orodruin.env ", "$(call ORO_MOUNT,annatar) ", "/app/requests:ro "):
        definition = ("$(ORO_DIRS) docker run --rm $(ORO_HARDEN) $(ORO_EXEC_HOME) --env-file orodruin.env "
                      "$(call ORO_MOUNT,annatar) -v $$HOME/requests:/app/requests:ro --pull never $(ORO_IMAGE)")
        assert definition.count(where) == 1
        definition = definition.replace(where, f"{where}{after} ", 1)
        assert _run_options(definition, text) == want + after.split(), definition
    plain = "docker run --rm $(ORO_HARDEN) --env-file orodruin.env $(call ORO_MOUNT,gothmog) --pull never $(ORO_IMAGE)"
    assert _run_options(plain, text) == _make_var("ORO_HARDEN", text).split()
