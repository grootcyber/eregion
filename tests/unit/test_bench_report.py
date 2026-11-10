"""`make bench-report RUN=<run_id>`: the chronology of a bench run, composed alone (BNC1, #682).

On a fake bench (tests/unit/bench_world.py: `az`, `terraform`, `make`, and H0 read by ssh through
scripts/bench_h0_reader.py, run for real on a fake H0), with the shapes measured on 09/11 (RAN1,
#665), the report composes again what was rebuilt by hand that night:
  - T0, the detection at 70,3 s, the isolation, the session drain 302 s, the verification read
    false, the neutralization 152 s, the restore job 15 min 17, the start held by the quarantine,
    the lift at T0 + 15 863 s, the guest agent `Ready`;
  - the Run Commands of the target, each caller a role (Orodruin, H0, the console, a human);
  - the same in JSON (runs/bench/<run_id>.json, or OUT=), and nothing else is written;
  - no identifier leaves: no GUID, no IP, no UPN — the output is scanned for them.
No Azure, no H0, no model.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_world as bw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bs = _load("bench_shared")
br = _load("bench_report")

NOW = datetime(2026, 11, 9, 21, 20, tzinfo=timezone.utc)
GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
UPN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def leaks(text: str) -> list[str]:
    """Every identifier the text still holds: a GUID, an IPv4, a UPN, a secret, an ARM id."""
    return (GUID.findall(text) + IP.findall(text) + UPN.findall(text)
            + [s for s in (bw.SECRET, "/subscriptions/") if s in text])


def _h0_0911(w: bw.World, isolated: bool = False) -> None:
    t0 = datetime.fromisoformat(bw.ts("16:41:26")).timestamp()
    w.write(f"runs/glorfindel/{bw.RUN}.json", {
        "scenario": "ransomware-vm", "run_id": bw.RUN, "mitre": "T1486", "result": "detected",
        "metrics": {"attack_time": bw.ts("16:41:26"), "detection": "detected", "detection_latency_s": 70.3,
                    "request": bw.REQUEST, "resource_id": bw.RID, "injector": "annatar"}})
    debug = w.write("runs/glorfindel/watch-ransomware-disk-write-1_debug.jsonl", "\n".join(json.dumps(x) for x in [
        {"timestamp": bw.ts("16:42:40"), "action": "", "escalate": False, "exercise_run": "another-run",
         "signal": {"event": "detection", "resource_id": bw.BREE}},
        {"timestamp": "2026-11-09T16:48:05.400000+00:00", "action": "isolate_vm", "escalate": False,
         "exercise_run": bw.RUN, "confidence": 0.82,
         "reasoning": f"vu {bw.LEAKED_IP} et {bw.HUMAN_UPN} sur {bw.RID}",
         "signal": {"event": "detection", "resource_id": bw.RID, "raw_signal": {"ip": bw.LEAKED_IP}},
         "outcome": {"executed": True, "verified": False, "action_s": 305, "status": "partial",
                     "error": f"sortie de Run Command illisible {bw.H0_OID}"}},
    ]) + "\n")
    os.utime(debug, (t0 + 1000, t0 + 1000))
    w.write("runs/console/manual_actions.jsonl", json.dumps({
        "timestamp": bw.ts("21:05:49"), "action": "release_isolation", "confidence": 1.0,
        "signal": {"resource_id": bw.RID}, "outcome": {"status": "released"}}) + "\n")
    if isolated:
        w.write(".glorfindel/isolation/vm-celebrimbor-gondolin--abc123.json", {
            "resource_id": bw.RID, "isolated_at": "2026-11-09T16:43:02.812000+00:00",
            "drains_at": ["2026-11-09T16:43:03.312000+00:00"],
            "placements": [{"nsg_name": "nsg-glorfindel-quarantine-x", "nic_id": bw.NIC}]}, home=True)


def _world_0911(tmp_path, isolated: bool = False) -> bw.World:
    w = bw.World(tmp_path)
    _h0_0911(w, isolated)
    w.rules = [
        bw.rule("make", ["glorfindel-host-known"], err=f"  ✓ Clé d'hôte de {bw.H0_IP} vérifiée par son empreinte\n"),
        bw.rule("terraform", ["~infra/glorfindel-host", "principal_id"], bw.H0_OID),
        bw.rule("terraform", ["~infra/orodruin", "principal_id"], bw.ORO_OID),
        bw.rule("az", ["vm", "list"], [{"name": bw.VM, "rg": bw.RG, "id": bw.RID},
                                       {"name": "vm-celebrimbor-bree", "rg": bw.RG, "id": bw.BREE}]),
        bw.rule("az", ["monitor", "activity-log", "list"], bw.activity_0911()),
        bw.rule("az", ["backup", "job", "list"], bw.jobs_0911()),
        bw.rule("az", ["vm", "get-instance-view"], bw.VIEW_0911),
    ]
    return w


def _report(w: bw.World, *args: str, env_extra: dict | None = None):
    env = w.env(**(env_extra or {}))
    out = w.tmp / "out" / f"{bw.RUN}.json"
    import io
    from contextlib import redirect_stderr, redirect_stdout
    so, se = io.StringIO(), io.StringIO()
    old = dict(os.environ)
    os.environ.update({"PATH": env["PATH"], "BENCH_FAKE_PLAN": env["BENCH_FAKE_PLAN"],
                       "BENCH_FAKE_LOG": env["BENCH_FAKE_LOG"]})
    try:
        with redirect_stdout(so), redirect_stderr(se):
            code = br.main(["--run", bw.RUN, "--out", str(out), "--config", str(w.config), *args], env=env, now=NOW)
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, so.getvalue(), se.getvalue(), out


def test_the_0911_chronology_is_composed_again(tmp_path):
    w = _world_0911(tmp_path)
    code, md, err, out = _report(w)
    assert code == 0, err
    doc = json.loads(out.read_text())
    figs = {f["key"]: f for f in doc["figures"]}
    assert doc["t0"].startswith("2026-11-09T16:41:26")
    assert doc["request"] == bw.REQUEST
    # T0, the detection, the isolation (H0's network write: its state is gone, released)
    assert "| T0 | 16:41:26 | 0 s |" in md
    assert "| Détection | 16:42:36 | **70,3 s** |" in md
    assert figs["isolation"]["at"].startswith("2026-11-09T16:43:02")
    # the drain: asked, done on Azure in 302 s; the verification read false
    assert "| Coupure aboutie sur Azure | 16:48:05 | 399 s | journal d'activité : Succeeded, 302 s après sa soumission |" in md
    assert "| Vérification relue, **fausse** | 16:48:05,4 | 399,4 s |" in md
    assert "`action_s` = 305" in md
    # the neutralization 152 s, the job 15 min 17, the start held, the lift, the agent
    assert "| Neutralisation (console) | 17:07:22 → 17:09:54 | — | journal d'activité, Succeeded, 152 s |" in md
    assert "| Job de restore | 20:34:25 → 20:49:42 | — | le coffre : `Completed`, **15 min 17** |" in md
    assert "| Démarrage après restore | 20:50:19 → 21:06:05 |" in md
    assert "| Levée (service rendu) | 21:05:49 | **15 863 s (4 h 24 min 23 s)** |" in md
    assert "| Agent invité `Ready` | 21:06:30 |" in md
    assert "- le job : **15 min 17** ;" in md
    assert "- le démarrage : **15 min 46**, retenu par la quarantaine jusqu'à la levée." in md
    assert doc["restore_time"] == {"job_s": 917.0, "start_s": 946.0, "held_by_quarantine": True}


def test_the_run_commands_say_their_callers_as_roles(tmp_path):
    w = _world_0911(tmp_path)
    code, md, _, out = _report(w)
    assert code == 0
    rcs = json.loads(out.read_text())["run_commands"]
    assert [(r["caller"], r["status"], r["what"]) for r in rcs] == [
        ("orodruin", "Succeeded", "les préparatifs de l'attaque (mise en place, contrôle d'intégrité)"),
        ("orodruin", "Succeeded", "les préparatifs de l'attaque (mise en place, contrôle d'intégrité)"),
        ("orodruin", "Succeeded", "l'attaque"),
        ("h0", "Succeeded", "la coupure des sessions"),
        ("console", "Succeeded", "la neutralisation"),
        ("console", "Failed", "une tentative refusée"),
        ("console", "Failed", "une tentative refusée"),
        ("console", "Failed", "une tentative refusée"),
        ("human", "Succeeded", "une Run Command humaine"),
    ]
    assert [r["duration_s"] for r in rcs][:5] == [22.0, 21.0, 61.0, 302.0, 152.0]
    assert "| 4 | H0 | 16:43:03 → 16:48:05 | Succeeded | 302 s | la coupure des sessions |" in md
    assert "| 6 | console | 20:09:29 → 20:09:29 | Failed (`Conflict`) | 0 s | une tentative refusée |" in md
    assert "| 9 | un humain |" in md
    # bree's Run Command and the unknown principal's ListServiceSas are not the target's Run Commands
    assert len(rcs) == 9


def test_the_chronology_is_in_order_and_says_the_point_and_the_failed_job(tmp_path):
    w = _world_0911(tmp_path)
    _, md, _, out = _report(w)
    tl = json.loads(out.read_text())["timeline"]
    assert [x["at"] for x in tl] == sorted(x["at"] for x in tl)
    whats = [x["what"] for x in tl]
    assert whats[0] == "point de restauration pris (job de sauvegarde)"
    assert "**T0**, l'attaque" in whats and "**levée**" in whats
    assert any(x.startswith("job de restore Failed (4,5 s)") for x in whats)
    assert any(x.startswith("désallocation de vm-celebrimbor-gondolin") for x in whats)
    assert any("coupure des sessions par H0 (302 s, Succeeded)" in x for x in whats)
    assert "| 15:49:23 → 16:15:00 | point de restauration pris (job de sauvegarde) |" in md


def test_the_isolation_state_gives_the_tenth_when_h0_still_holds_it(tmp_path):
    w = _world_0911(tmp_path, isolated=True)
    code, md, _, _ = _report(w)
    assert code == 0
    assert "| Isolement exécuté (NSG de quarantaine posé) | 16:43:02,8 | **96,8 s** | `isolated_at`, l'état d'isolation de H0 |" in md
    assert "| Coupure des sessions demandée | 16:43:03,3 | 97,3 s | `drains_at`, l'état de H0 |" in md


def test_no_identifier_leaves_the_report(tmp_path):
    w = _world_0911(tmp_path, isolated=True)
    code, md, err, out = _report(w)
    assert code == 0
    for text in (md, err, out.read_text(), out.with_suffix(".md").read_text()):
        assert leaks(text) == [], leaks(text)
    # the reader itself sent back no reasoning, no raw signal, no error text, no resource id
    calls = [c for c in w.calls() if c[0] == "ssh"]
    assert calls and all("eregion-watch" in c[-1] for c in calls)


def test_the_h0_reader_sends_back_names_never_ids(tmp_path):
    w = _world_0911(tmp_path, isolated=True)
    env = w.env()
    res = subprocess.run([sys.executable, "-", "report", bw.VM, bw.RUN], input=(ROOT / "scripts/bench_h0_reader.py").read_text(),
                         capture_output=True, text=True, cwd=w.app, env={**env, "HOME": str(w.home), "PYTHONPATH": str(ROOT)},
                         timeout=60)
    assert res.returncode == 0, res.stderr
    assert leaks(res.stdout) == [] and "reasoning" not in res.stdout and "raw_signal" not in res.stdout
    doc = json.loads(res.stdout)
    assert doc["run"]["target"] == bw.VM and len(doc["cycles"]) == 1 and len(doc["lifts"]) == 1


def test_a_watch_release_with_rec1_is_the_lift(tmp_path):
    w = _world_0911(tmp_path)
    (w.app / "runs/console/manual_actions.jsonl").unlink()
    t0 = datetime.fromisoformat(bw.ts("16:41:26")).timestamp()
    f = w.write("runs/glorfindel/watch-recovery-1_debug.jsonl", json.dumps({
        "timestamp": bw.ts("21:01:00"), "action": "release_isolation", "escalate": False,
        "signal": {"event": "recovery_complete", "resource_id": bw.RID},
        "outcome": {"executed": True, "verified": True, "verified_at": bw.ts("21:01:12")}}) + "\n")
    os.utime(f, (t0 + 1000, t0 + 1000))
    code, md, _, _ = _report(w)
    assert code == 0
    assert "| Levée (service rendu) | 21:01:12 | **15 586 s (4 h 19 min 46 s)** | le cycle `recovery_complete` de la watch (REC1), `verified=True` |" in md


def test_what_could_not_be_read_is_said(tmp_path):
    w = _world_0911(tmp_path)
    w.rules = [r for r in w.rules if "activity-log" not in r["has"] and "get-instance-view" not in r["has"]]
    w.rules.append(bw.rule("az", ["monitor", "activity-log"], rc=1,
                           err=f"ERROR: AuthorizationFailed for {bw.HUMAN_UPN} on /subscriptions/{bw.SUB}/x\n"))
    code, md, _, _ = _report(w)
    assert code == 0
    assert "## Ce qui n'a pas pu être lu" in md
    assert "le journal d'activité : illisible (ERROR: AuthorizationFailed for <upn> on <ressource>)" in md
    assert "la vue d'instance : illisible" in md
    assert leaks(md) == []


def test_a_run_unknown_on_h0_refuses(tmp_path):
    w = _world_0911(tmp_path)
    (w.app / f"runs/glorfindel/{bw.RUN}.json").unlink()
    code, md, err, out = _report(w)
    assert code == 1 and md == "" and not out.exists()
    assert f"le rapport du run {bw.RUN} est absent de H0" in err


@pytest.mark.parametrize("bad", ["", "$(touch x)", "a b", "-rf"])
def test_a_run_id_that_is_not_one_is_refused_before_anything(tmp_path, bad):
    w = _world_0911(tmp_path)
    env = w.env()
    code = br.main([f"--run={bad}", "--config", str(w.config)], env=env, now=NOW)
    assert code == 2 and w.calls() == []


def test_the_target_composes_the_command_without_expanding_it(tmp_path):
    make = shutil.which("make")
    if make is None:
        pytest.skip("make not installed")
    w = bw.World(tmp_path)
    w.rules = [bw.rule("terraform", ["public_ip"], bw.H0_IP)]
    env = w.env()
    (w.bin / "make").unlink()                       # the real make, the fake terraform
    res = subprocess.run([make, "-n", "-s", "--no-print-directory", "-C", str(ROOT), "bench-report",
                          f"RUN=$(touch {tmp_path}/never)", "TARGET=vm-celebrimbor-gondolin", "OUT=x.json"],
                         capture_output=True, text=True, timeout=60, env=env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == ".venv/bin/python scripts/bench_report.py"
    assert not (tmp_path / "never").exists()
