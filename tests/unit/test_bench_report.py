"""`make bench-report RUN=<run_id>`: the chronology of a bench run, composed alone (BNC1, #682).

On a fake bench (tests/unit/bench_world.py: `az`, `terraform`, `make`, and Imladris read by ssh through
scripts/bench_h0_reader.py, run for real on a fake Imladris), with the shapes measured on 09/11 (RAN1,
#665), the report composes again what was rebuilt by hand that night:
  - T0, the detection at 70,3 s, the isolation, the session drain 302 s, the verification read
    false, the neutralization 152 s, the restore job 15 min 17, the start held by the quarantine,
    the lift at T0 + 15 863 s, the guest agent `Ready`;
  - the Run Commands of the target, each caller a role (Orodruin, Imladris, the console, a human);
  - the same in JSON (runs/bench/<run_id>.json, or OUT=), and nothing else is written;
  - no identifier leaves: no GUID, no IP, no UPN — the output is scanned for them.
No Azure, no Imladris, no model.
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
        bw.rule("az", ["vm", "show", "--ids", bw.RID], [bw.NIC]),
        bw.rule("az", ["monitor", "activity-log", "list", "--resource-id", bw.RID], bw.activity_of(bw.RID)),
        bw.rule("az", ["monitor", "activity-log", "list", "--resource-id", bw.NIC], bw.activity_of(bw.NIC)),
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
    assert "| 4 | Imladris | 16:43:03 → 16:48:05 | Succeeded | 302 s | la coupure des sessions |" in md
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
    assert any("coupure des sessions par Imladris (302 s, Succeeded)" in x for x in whats)
    assert "| 15:49:23 → 16:15:00 | point de restauration pris (job de sauvegarde) |" in md


def test_the_isolation_state_gives_the_tenth_when_h0_still_holds_it(tmp_path):
    w = _world_0911(tmp_path, isolated=True)
    code, md, _, _ = _report(w)
    assert code == 0
    assert "| Isolement exécuté (NSG de quarantaine posé) | 16:43:02,8 | **96,8 s** | `isolated_at`, l'état d'isolation d'Imladris |" in md
    assert "| Coupure des sessions demandée | 16:43:03,3 | 97,3 s | `drains_at`, l'état d'Imladris |" in md


def test_no_identifier_leaves_the_report(tmp_path):
    w = _world_0911(tmp_path, isolated=True)
    code, md, err, out = _report(w)
    assert code == 0
    for text in (md, err, out.read_text(), out.with_suffix(".md").read_text()):
        assert leaks(text) == [], leaks(text)
    # the reader itself sent back no reasoning, no raw signal, no error text, no resource id
    calls = [c for c in w.calls() if c[0] == "ssh"]
    assert calls and all("reasoning" not in c[-1] for c in calls)


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
    assert ("le journal d'activité de vm-celebrimbor-gondolin : illisible (ERROR: AuthorizationFailed for <upn> on "
            "<ressource>)") in md
    assert "la vue d'instance : illisible" in md
    assert leaks(md) == []


def test_a_run_unknown_on_h0_refuses(tmp_path):
    w = _world_0911(tmp_path)
    (w.app / f"runs/glorfindel/{bw.RUN}.json").unlink()
    code, md, err, out = _report(w)
    assert code == 1 and md == "" and not out.exists()
    assert f"le rapport du run {bw.RUN} est absent d'Imladris" in err


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


# ── the review's findings (BNC1, round 1) ──────────────────────────────────────

def _h0_ssh(w: bw.World) -> list[list[str]]:
    import shlex
    return [shlex.split(c[-1]) for c in w.calls() if c[0] == "ssh" and any(bw.H0_IP in a for a in c)]


def test_the_h0_reader_runs_in_a_disposable_container_of_the_deployed_image(tmp_path):
    """Never inside the watch: `docker inspect` reads its image and mounts, then a `docker run` of that
    image, without network (no IMDS, no token), without capability, read-only, each mount readonly."""
    w = _world_0911(tmp_path)
    code, _, err, _ = _report(w)
    assert code == 0, err
    inspect, run = _h0_ssh(w)
    assert inspect[:2] == ["docker", "inspect"] and inspect[-1] == "eregion-watch"
    assert run[:2] == ["docker", "run"] and "exec" not in run
    i = run.index(bw.IMAGE)
    opts, after = run[:i], run[i:]
    assert after == [bw.IMAGE, "-", "report", bw.VM, bw.RUN]
    for pair in (["--network", "none"], ["--cap-drop", "ALL"], ["--security-opt", "no-new-privileges"],
                 ["--entrypoint", "python"]):
        assert any(opts[k:k + 2] == pair for k in range(len(opts))), pair
    assert "--rm" in opts and "--read-only" in opts and "-v" not in opts and "--privileged" not in opts
    mounts = [opts[k + 1] for k, o in enumerate(opts) if o == "--mount"]
    assert mounts and all(m.endswith(",readonly") and m.startswith("type=bind,") for m in mounts)
    targets = sorted(m.split("target=")[1].split(",")[0] for m in mounts)
    assert targets == ["/app/glorfindel-config.yaml", "/app/runs/bot", "/app/runs/console", "/app/runs/glorfindel",
                       "/root/.glorfindel"]


@pytest.mark.parametrize("mounts,why", [
    ([], "ne monte pas /app/runs/glorfindel"),
    ([{"Type": "bind", "Source": "/home/x/runs/glorfindel,type=volume", "Destination": "/app/runs/glorfindel"}],
     "pas un chemin attendu"),
    ([{"Type": "volume", "Source": "/var/lib/docker/volumes/x/_data", "Destination": "/app/runs/glorfindel"}],
     "ne monte pas /app/runs/glorfindel"),
    ([{"Type": "bind", "Source": "/home/x/../../etc", "Destination": "/app/runs/glorfindel"}], "pas un chemin attendu"),
])
def test_the_reader_s_mounts_are_refused_when_they_are_not_the_watch_s(mounts, why):
    with pytest.raises(RuntimeError, match=why):
        bs.reader_command(mounts, bw.IMAGE, "report", bw.VM, bw.RUN)
    with pytest.raises(RuntimeError, match="image"):
        bs.reader_command([], "eregion-glorfindel:latest", "report", bw.VM)


@pytest.mark.parametrize("ssh,known_rc", [
    (f"ssh -o StrictHostKeyChecking=accept-new glorfindel@{bw.H0_IP}", 0),
    (f"ssh glorfindel@{bw.H0_IP}", 0),
    (f"ssh {bw.PINNED} glorfindel@{bw.H0_IP}", 1),
    (f"ssh -o StrictHostKeyChecking=no {bw.PINNED} glorfindel@{bw.H0_IP}", 0),
    (f"ssh -o StrictHostKeyChecking=yes glorfindel@{bw.H0_IP}", 0),
])
def test_an_unverified_h0_host_key_sends_nothing(tmp_path, ssh, known_rc):
    w = _world_0911(tmp_path)
    w.rules.insert(0, bw.rule("make", ["glorfindel-host-known"], rc=known_rc,
                              err=f"✗ HOST_SSH_FINGERPRINT requis : la clé d'hôte de {bw.H0_IP}\n"))
    code, md, err, out = _report(w, env_extra={"BENCH_H0_SSH": ssh})
    assert code == 1 and md == "" and not out.exists()
    assert "clé d'hôte d'Imladris n'est pas vérifiée" in err and bw.H0_IP not in err
    assert not [c for c in w.calls() if c[0] == "ssh"]


def test_out_md_never_writes_over_the_json(tmp_path, monkeypatch):
    w = _world_0911(tmp_path)
    env = w.env()
    for k in ("PATH", "BENCH_FAKE_PLAN", "BENCH_FAKE_LOG"):
        monkeypatch.setenv(k, env[k])
    out = tmp_path / "out" / "x.md"
    import io
    from contextlib import redirect_stderr, redirect_stdout
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        code = br.main(["--run", bw.RUN, "--out", str(out), "--config", str(w.config)], env=env, now=NOW)
    assert code == 0
    assert json.loads((tmp_path / "out" / "x.json").read_text())["run_id"] == bw.RUN
    assert out.read_text().startswith("# Rapport du banc")


def test_a_cut_activity_log_is_said(tmp_path, monkeypatch):
    monkeypatch.setattr(br, "MAX_EVENTS", 3)
    w = _world_0911(tmp_path)
    code, md, _, _ = _report(w)
    assert code == 0
    assert ("le journal d'activité de vm-celebrimbor-gondolin : 3 événements lus, le plafond — la suite n'est pas "
            "lue, la chronologie peut être coupée") in md
    reads = [c for c in w.calls() if c[0] == "az" and "activity-log" in c]
    assert len(reads) == 2 and all("--resource-id" in c and "--resource-group" not in c for c in reads)


def test_an_unreadable_workstation_config_is_said_without_its_values(tmp_path):
    w = _world_0911(tmp_path)
    w.config.write_text(f"autonomy:\n  default: {bw.HUMAN_UPN}\nunknown_{bw.CONSOLE_APP.replace('-', '_')}: 1\n")
    code, md, err, _ = _report(w)
    assert code == 0, err
    assert "la configuration du poste : illisible (ConfigError) — les jobs du coffre ne sont pas lus" in md
    assert leaks(md + err) == []


def test_any_failure_is_said_masked_never_a_trace(tmp_path, monkeypatch):
    w = _world_0911(tmp_path)

    def broken(*a, **k):
        raise KeyError(f"{bw.HUMAN_UPN} {bw.RID} {bw.H0_OID}")
    monkeypatch.setattr(br, "compose", broken)
    code, md, err, out = _report(w)
    assert code == 1 and md == "" and not out.exists()
    assert err.startswith("✗ le rapport n'a pas pu être composé (KeyError: ") and "Traceback" not in err
    assert leaks(err) == []
