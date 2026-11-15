"""The service's stop reaches the wire (DRL1a, docs/design/drill-banc.md §3.1, « L'arrêt du service »):
SIGTERM to the drill (eregion_core/scheduled_drill.py) is relayed to its wire, never raised while the
wire is awaited; the wire (`annatar wire`, annatar/cli.py) takes it once — SIGTERM ignored from then
on, then raised —, closes its window and ends; no SIGKILL before 75 s; the occurrence is ``stopped``.
And the wire's window opened for the time its runner left it, never MAX_DURATION_S unasked.

One test on real processes: the drill's ``launch`` in a process of its own, a wire that sleeps in
another — the real handler of each. No Azure, no model. Crosses components on purpose (the drill of
the shared core, Annatar's wire): TOGETHER.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

REPO = Path(__file__).resolve().parents[2]
VM = ("/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor"
      "/providers/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin")
REQ = "r-20261117T190000Z-abcdef"


@pytest.fixture(autouse=True)
def _bench_subscription(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")

WIRE = textwrap.dedent(f"""
    import sys, time
    from pathlib import Path
    sys.path.insert(0, {str(REPO)!r})
    from annatar.cli import Terminated, stop_on_sigterm
    from eregion_core.exercise import close_window, open_window
    d = Path(sys.argv[1])
    stop_on_sigterm()
    open_window("run-1", injector="annatar", kind="technique", experiment="T1136.001",
                targets=[{VM!r}], directory=d)
    (d / "ready").write_text("1")
    try:
        try:
            time.sleep(120)
        finally:
            close_window("run-1", injector="annatar", directory=d)
            (d / "closed").write_text("1")
    except Terminated:
        sys.exit(143)
""")

DRILL = textwrap.dedent(f"""
    import json, sys, time
    sys.path.insert(0, {str(REPO)!r})
    from eregion_core import scheduled_drill as sd
    out, wire, d = sys.argv[1], sys.argv[2], sys.argv[3]
    kept = {{}}
    def popen(argv, **kw):
        import subprocess
        kept["p"] = subprocess.Popen(argv, **kw)
        return kept["p"]
    occ = sd.Occurrence(catalog={{}}, power=lambda r: "", start=lambda r: None, heartbeat=lambda r: None,
                        popen=popen, say=lambda *_: None)
    occ.install()
    t0 = time.monotonic()
    try:
        occ.launch([sys.executable, wire, d], {{}})
        state = "ended"
    except sd.Stopped:
        state = "stopped"
    json.dump({{"state": state, "child": kept["p"].returncode, "s": time.monotonic() - t0}}, open(out, "w"))
""")


def test_a_sigterm_during_a_sleeping_wire_reaches_it_its_window_closes_no_sigkill(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "wire.py").write_text(WIRE)
    (scripts / "drill.py").write_text(DRILL)
    d = tmp_path / "windows"
    d.mkdir()
    out = tmp_path / "out.json"
    drill = subprocess.Popen([sys.executable, str(scripts / "drill.py"), str(out), str(scripts / "wire.py"), str(d)],
                             cwd=tmp_path)
    try:
        deadline = time.monotonic() + 30
        while not (d / "ready").exists():
            assert time.monotonic() < deadline, "the wire never started"
            assert drill.poll() is None, "the drill ended before its wire started"
            time.sleep(0.05)
        drill.send_signal(signal.SIGTERM)            # systemd's stop, as tini relays it
        assert drill.wait(timeout=60) == 0
    finally:
        if drill.poll() is None:
            drill.kill()
    said = json.loads(out.read_text())
    assert said["state"] == "stopped"
    assert said["child"] == 143                   # its own exit, never -9 (a SIGKILL)
    assert said["s"] < 75
    assert (d / "closed").exists()
    [window] = [json.loads(p.read_text()) for p in d.glob("run-1.json")]
    assert window["end"] is not None


# ── `annatar wire` itself: the handler, one shot ───────────────────────────────────────

def _executor():
    ex = MagicMock()
    ex.resource_id = VM
    tags = {"eregion-target": "celebrimbor", "eregion-zone": "bench"}
    ex.get_resource_group_tags.return_value = dict(tags)
    ex.get_vm_tags.return_value = dict(tags)
    ex.get_vm_name.return_value = "vm-celebrimbor-gondolin"
    ex.check_preflight.return_value = []
    ex.verify_restore_integrity.return_value = True
    ex.run_script.return_value = ""
    return ex


def _wire_under(tmp_path, monkeypatch, wait):
    from annatar.cli import cli
    from annatar.runner.engine import Engine
    monkeypatch.chdir(tmp_path)
    before = signal.getsignal(signal.SIGTERM)
    try:
        with patch.object(Engine, "_get_executor_collector", return_value=(_executor(), MagicMock())), \
             patch.object(Engine, "_wait_and_emit_feedback", side_effect=wait):
            res = CliRunner().invoke(cli, ["wire", "T1110.001", VM, "--request", REQ], catch_exceptions=False)
        after = signal.getsignal(signal.SIGTERM)
    finally:
        signal.signal(signal.SIGTERM, before)
    return res, after


def _windows(tmp_path):
    from eregion_core.exercise import exercises_dir
    d = exercises_dir()
    return [json.loads(p.read_text()) for p in d.glob("*.json")] if d.exists() else []


def test_annatar_wire_takes_sigterm_once_closes_its_window_and_says_it(tmp_path, monkeypatch):
    def term(*_a, **_k):
        os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(1)      # delivered at the next bytecode: never reached past this

    res, after = _wire_under(tmp_path, monkeypatch, term)
    assert res.exit_code == 143, res.output
    assert "stopped (SIGTERM)" in " ".join(res.output.split())
    assert after == signal.SIG_IGN               # a second signal never cuts the finally
    [window] = _windows(tmp_path)
    assert window["end"] is not None and window["request"] == REQ


@pytest.mark.parametrize("left, lasts", [("1500", 1800), ("7200", 7200), ("", 7200)])
def test_a_wires_window_lasts_its_time_left_plus_five_minutes_never_past_the_bound(tmp_path, monkeypatch, left, lasts):
    if left:
        monkeypatch.setenv("EREGION_MAX_RUN_S", left)
    else:
        monkeypatch.delenv("EREGION_MAX_RUN_S", raising=False)
    res, _ = _wire_under(tmp_path, monkeypatch, None)
    assert res.exit_code == 0, res.output
    [window] = _windows(tmp_path)
    start, expires = (datetime.fromisoformat(window[k]) for k in ("start", "expires"))
    assert (expires - start).total_seconds() == lasts
