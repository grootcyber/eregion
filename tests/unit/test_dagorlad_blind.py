"""Glorfindel stays blind to Dagorlad (docs/design/console.md §7, « Glorfindel reste aveugle »; DG-b
review, point 9): a cycle of `decide` replayed with a request present — in the console's directory,
its names typed beside it, its status and Orodruin's verdict pulled into runs/orodruin/, its window
naming it — sends the model the same message, to the byte.

No Azure, no model: the message is built, never sent. Crosses components on purpose (Glorfindel's
message, the shared core's request): TOGETHER. The oracle is written here: the message without any
of it.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from eregion_core import drill as dr
from eregion_core import drill_arming as da
from eregion_core import exercise_request as xr
from glorfindel.agent import _build_user_message

VM = ("/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor"
      "/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin")
SIGNAL = {"signal_id": "s-1", "run_id": "watch-ransomware-1", "resource_id": VM, "event": "detection",
          "raw_signal": {"ttp": "T1486", "normalized_signal": {
              "indicator_key": "disk_write_mbps", "indicator_value": 212, "resource": "vm-celebrimbor-gondolin"}}}
PAST = [{"summary": "isolate_vm on vm-celebrimbor-gondolin, verified", "source": "exercise"}]


def test_a_request_present_changes_nothing_glorfindel_tells_the_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    console_dir = tmp_path / "home" / ".eregion" / "console" / "requests"
    monkeypatch.setenv(xr.REQUESTS_ENV, str(console_dir))
    (tmp_path / "runs").mkdir()
    before = _build_user_message(SIGNAL, PAST).encode()

    # The red side's plan, everywhere it may lie on a host where the watch runs.
    req = xr.new([("T1486", VM), ("vm-shutdown", VM)], now=datetime(2026, 10, 30, 8, tzinfo=timezone.utc))
    xr.write(req, console_dir)
    (console_dir / f"{req.id}.typed.json").write_text(json.dumps({"request": req.id, "typed": {"1": "vm-celebrimbor-gondolin"}}))
    pulled = tmp_path / "runs" / "orodruin"
    (pulled / "requests").mkdir(parents=True)
    (pulled / "contract.json").write_text(json.dumps({"verdict": "armed", "codes": [], "at": "2026-10-30T08:00:00+00:00"}))
    (pulled / "requests" / f"{req.id}.json").write_text(json.dumps({
        "request": req.id, "state": "running", "at": "2026-10-30T08:01:00+00:00", "codes": [],
        "wires": [{"rank": 1, "state": "running", "code": "", "runs": ["20261030T080100Z-ab12"], "result": ""},
                  {"rank": 2, "state": "queued", "code": "", "runs": [], "result": ""}]}))

    after = _build_user_message(SIGNAL, PAST).encode()
    assert after == before
    assert req.id.encode() not in after


def test_the_drill_of_the_week_present_changes_nothing_glorfindel_tells_the_model(tmp_path, monkeypatch):
    """DRL1 (docs/design/drill-banc.md §8.1): the drill's request status with its ``drill``, its pulse
    (runs/orodruin/drill.json), its permit, the drill and its expectations (expectations/banc-hebdo.yaml,
    in the watch's image) present on the watch's host — the message is the same, to the byte."""
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "runs").mkdir()
    signal = {**SIGNAL, "raw_signal": {"ttp": "T1136.001", "normalized_signal": {
        "indicator_key": "new_local_account", "indicator_value": 1, "resource": "vm-celebrimbor-gondolin"}}}
    before = _build_user_message(signal, PAST).encode()

    sha = dr.fingerprint((root / "drills" / "banc-hebdo.yaml").read_bytes())
    req = xr.new([("T1136.001", VM)], now=datetime(2026, 11, 17, 19, 1, tzinfo=timezone.utc))
    status = {"request": req.id, "state": "running", "at": "2026-11-17T19:02:00+00:00", "codes": [],
              "wires": [{"rank": 1, "state": "running", "code": "", "runs": ["20261117T190200Z-ab12"],
                         "result": ""}],
              "drill": {"name": "banc-hebdo", "sha256": sha, "occurrence": "2026-11-17T19:00:00+00:00"}}
    xr.read_status(status)
    pulled = tmp_path / "runs" / "orodruin"
    (pulled / "requests").mkdir(parents=True)
    (pulled / "requests" / f"{req.id}.json").write_text(json.dumps(status))
    pulse = da.pulse(state="armed", drill="banc-hebdo", sha256=sha, next_at="2026-11-24T19:00:00+00:00",
                     last={"at": "2026-11-17T19:01:00+00:00", "occurrence": "2026-11-17T19:00:00+00:00",
                           "state": "played", "code": "", "request": req.id},
                     image="abc123 sha256:00", at="2026-11-17T19:01:00+00:00")
    (pulled / "drill.json").write_text(json.dumps(pulse))
    (pulled / "drill-permit.json").write_text(json.dumps(
        {"drill": "banc-hebdo", "sha256": sha, "armed_at": "2026-11-16T10:00:00+00:00"}))
    for d in ("drills", "expectations"):
        (tmp_path / d).mkdir()
        shutil.copy(root / d / "banc-hebdo.yaml", tmp_path / d / "banc-hebdo.yaml")

    after = _build_user_message(signal, PAST).encode()
    assert after == before
    for seen in (b"banc-hebdo", sha.encode(), b"within_s", req.id.encode()):
        assert seen not in after


def test_a_verdict_proposed_changes_nothing_glorfindel_tells_the_model(tmp_path, monkeypatch):
    """VP1 (#615, docs/design/drill-banc.md §8.2): the watch's pass over the drill's files proposes a
    verdict on the expected exercise card, and the message of ``_build_user_message()`` stays the same,
    to the byte: the decision reads no card, nor anything VP1 reads."""
    from glorfindel import escalations
    from glorfindel import proposed_verdict as pv
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    runs = tmp_path / "runs"
    exp = pv.ex.load_file(root / "expectations" / "banc-hebdo.yaml").wires[0]
    signal = {**SIGNAL, "raw_signal": {"ttp": exp.experiment, "normalized_signal": {
        "indicator_key": "new_local_account", "indicator_value": 1, "resource": "vm-celebrimbor-gondolin"}}}
    before = _build_user_message(signal, PAST).encode()

    now = datetime.now(timezone.utc)
    run, req = "20261117T190200Z-ab12", "r-20261117T190000Z-abc123"
    sha = dr.fingerprint((root / "drills" / "banc-hebdo.yaml").read_bytes())
    (runs / "glorfindel" / "orodruin" / "requests").mkdir(parents=True)
    (runs / "glorfindel" / "orodruin" / "requests" / f"{req}.json").write_text(json.dumps({
        "request": req, "state": "finished", "at": now.isoformat(), "codes": [],
        "wires": [{"rank": 1, "state": "done", "code": "", "runs": [run], "result": "detected"}],
        "drill": {"name": "banc-hebdo", "sha256": sha, "occurrence": now.isoformat()}}))
    t0 = now.timestamp() - 60
    (runs / "glorfindel" / f"{run}.json").write_text(json.dumps({
        "scenario": "s", "run_id": run, "mitre": exp.experiment, "result": "PASS", "thresholds": {}, "checks": {},
        "metrics": {"kind": "technique", "injector": "annatar", "experiment_id": exp.experiment,
                    "resource_id": VM, "request": req, "attack_time": t0}}))
    window = {"run_id": run, "injector": "annatar", "kind": "technique", "experiment": exp.experiment,
              "targets": [VM.lower()], "start": datetime.fromtimestamp(t0 - 30, timezone.utc).isoformat(),
              "end": None, "expires": datetime.fromtimestamp(t0 + 3600, timezone.utc).isoformat(),
              "destructive": False, "request": req}
    card = escalations.record(f"rule-{exp.rule}-0123abcd", VM, "snapshot", "low_confidence", "held",
                              rule_name=exp.rule, source="exercise", exercise_run=run)
    assert pv.refresh(runs, windows=[window]) == 1
    assert next(e for e in escalations.all_escalations() if e["id"] == card)[escalations.PROPOSED_FIELD]

    after = _build_user_message(signal, PAST).encode()
    assert after == before
    for seen in (b"proposed", b"banc-hebdo", run.encode(), req.encode()):
        assert seen not in after


def test_the_drill_judged_changes_nothing_glorfindel_tells_the_model(tmp_path, monkeypatch):
    """DRL1b (#613, docs/design/drill-banc.md §8.1): what DRL1b reads and writes on the watch's host —
    the last pull's sight of the drill's blobs (``drill-seen.json``, the permit as the listing said it),
    the pulse kept, the status of the occurrence's request, and the verdict the watch's pass writes
    (``~/.glorfindel/drill_verdicts.json``), a ``not_run`` with its mention — and the message of
    ``_build_user_message()`` stays the same, to the byte."""
    from eregion_core import exercise_channel as xc
    from glorfindel import drill_watch
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    runs = tmp_path / "runs"
    signal = {**SIGNAL, "raw_signal": {"ttp": "T1136.001", "normalized_signal": {
        "indicator_key": "new_local_account", "indicator_value": 1, "resource": "vm-celebrimbor-gondolin"}}}
    before = _build_user_message(signal, PAST).encode()

    drill, sha = dr.loaded(root / "drills" / "banc-hebdo.yaml", dr.SHIPPED)
    o = drill.schedule.occurrence(datetime(2026, 11, 20, tzinfo=timezone.utc))
    oro = runs / "glorfindel" / "orodruin"
    oro.mkdir(parents=True)
    permit = {"drill": "banc-hebdo", "sha256": sha, "armed_at": "2026-11-10T10:00:00+00:00"}
    (oro / xc.SEEN_FILE).write_text(json.dumps({
        "at": o.isoformat(), "listed": True, "why": "", "listed_at": o.isoformat(), "unread_since": "",
        "permit": {"listed": True, "doc": permit, "why": ""},
        "pulse": {"listed": True, "modified": "2026-11-12T10:00:00+00:00", "why": ""}}))
    (oro / xc.PULSE_FILE).write_text(json.dumps(da.pulse(
        state="armed", drill="banc-hebdo", sha256=sha, next_at=o.isoformat(), image="abc123",
        at="2026-11-12T10:00:00+00:00")))
    v = drill_watch.refresh(runs, now=o.replace(hour=22), channel=True)
    assert (v["state"], v["mention"]) == ("not_run", True)
    assert drill_watch.load()["current"]["state"] == "not_run"

    after = _build_user_message(signal, PAST).encode()
    assert after == before
    for seen in (b"banc-hebdo", sha.encode(), b"not_run", b"permit"):
        assert seen not in after
