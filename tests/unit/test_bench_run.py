"""`make bench-run TARGET=<vm> SCENARIO=<id>`: a bench run in one command (MOB1, #686).

The steps are fakes (the preflight's verdict, the VM read on Azure, Orodruin, the report), and the
launch itself runs against a fake `ssh` and a fake `scp` first on PATH: nothing connects, nothing
reaches Azure, no attack. The oracles are written here: never in a code session (the variable, a
lot's worktree as the current directory or as the checkout), never without the target's name typed
— destructive or not —, never past a red preflight; the request carried is the one Dagorlad's reader
takes, the name typed beside it, removed from Orodruin at the end; each run named gets its report.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


bs = _load("bench_shared")
brun = _load("bench_run")
from eregion_core import exercise_request as xr  # noqa: E402
from eregion_core.exercise_plan import load_catalog  # noqa: E402

VM = "vm-celebrimbor-gondolin"
VM_ID = ("/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/"
         f"Microsoft.Compute/virtualMachines/{VM}")
CLEAN = {"PATH": os.environ.get("PATH", "")}
needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")


CLEAN_POINT = {"clean": True, "said": "le plus récent (09:00:00), pris après le dernier restore et hors de toute "
                                      "quarantaine", "point": 1.0, "vault": "rsv", "vault_rg": "rg"}


class FakeSteps:
    def __init__(self, preflight=0, hits=None, launch=(0, ["20261110T101500Z-t1486"]), report=0, point=None,
                 snapshot=None, rejudged=(True, "rejugé propre")):
        self.calls: list[tuple] = []
        self._preflight, self._launch, self._report = preflight, launch, report
        self._point = CLEAN_POINT if point is None else point
        self._snapshot = snapshot
        self._rejudged = rejudged
        self._hits = [{"rg": "rg-celebrimbor", "id": VM_ID}] if hits is None else hits
        self.sent: dict = {}

    def catalog(self):
        return load_catalog()

    def preflight(self, target):
        self.calls.append(("preflight", target))
        if isinstance(self._preflight, list):
            return self._preflight.pop(0)
        return self._preflight

    def point(self, target):
        self.calls.append(("point", target))
        if isinstance(self._point, Exception):
            raise self._point
        return self._point

    def rejudge(self, target, point):
        self.calls.append(("rejudge", target))
        return self._rejudged

    def snapshot(self, target, plan, say, token):
        self.calls.append(("snapshot", target))
        self.token = token
        if isinstance(self._snapshot, Exception):
            raise self._snapshot
        return 2.0

    def locate(self, target):
        self.calls.append(("locate", target))
        return self._hits

    def launch(self, folder, rid, say):
        self.calls.append(("launch", rid))
        self.sent = {p.name: json.loads(p.read_text()) for p in Path(folder).iterdir()}
        return self._launch

    def report(self, run_id, target):
        self.calls.append(("report", run_id, target))
        return self._report


def _main(steps, *answers, env=None, cwd=None, here=None, args=("--target", VM, "--scenario", "T1486"), tty=True):
    said: list[str] = []
    feed = list(answers)

    def ask(prompt):
        said.append(prompt)
        if not feed:
            raise EOFError
        return feed.pop(0)
    code = brun.main(list(args), {**CLEAN, **(env or {})}, cwd=cwd or Path("/"), here=here or Path("/"),
                     ask=ask, say=said.append, steps=steps, tty=tty)
    return code, "\n".join(said)


# ── never in a code session ───────────────────────────────────────────────────

@pytest.mark.parametrize("where", ["env", "cwd", "here"])
def test_a_code_session_is_refused_before_any_step(tmp_path, where):
    lot = tmp_path / "eregion" / ".claude" / "worktrees" / "lot-x"
    lot.mkdir(parents=True)
    steps = FakeSteps()
    code, out = _main(steps, VM, "o", env={"EREGION_AGENT_SESSION": "1"} if where == "env" else None,
                      cwd=lot if where == "cwd" else tmp_path, here=lot if where == "here" else tmp_path)
    assert code == 1 and "refusé" in out and "jamais une attaque" in out
    assert steps.calls == []


def test_without_a_terminal_nothing_is_read_and_nothing_is_launched():
    """A name « typed » through a pipe (`printf '<vm>\\no\\n' | make bench-run …`) is no name typed:
    refused before the preflight (MOB1, review round 1)."""
    steps = FakeSteps()
    code, out = _main(steps, VM, "o", tty=False)
    assert code == 1 and "pas de terminal" in out
    assert steps.calls == []


def test_the_guard_alone_passes_outside_a_session(tmp_path):
    assert brun.main(["--guard-only"], dict(CLEAN), cwd=tmp_path, here=tmp_path, say=lambda s: None) == 0
    assert brun.main(["--guard-only"], {"EREGION_AGENT_SESSION": "1"}, cwd=tmp_path, here=tmp_path,
                     say=lambda s: None) == 1


# ── the arguments ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("args", [("--scenario", "T1486"), ("--target", "VM;rm", "--scenario", "T1486"),
                                  ("--target", VM), ("--target", VM, "--scenario", "T9999"),
                                  ("--target", VM, "--scenario", "annatar/scenarios/azure/ransomware-vm.yaml")])
def test_a_target_and_a_catalogue_scenario_are_required(args):
    steps = FakeSteps()
    code, out = _main(steps, args=args)
    assert code == 2 and steps.calls == []


# ── the preflight, the name typed ─────────────────────────────────────────────

def test_a_red_preflight_asks_nothing_and_sends_nothing():
    steps = FakeSteps(preflight=1)
    code, out = _main(steps, VM, "o")
    assert code == 1 and "préflight est rouge" in out
    assert steps.calls == [("preflight", VM)]


@pytest.mark.parametrize("answers", [(), ("", "o"), ("vm-celebrimbor-bree", "o"), ("VM-CELEBRIMBOR-GONDOLIN", "o"),
                                     (VM, "n"), (VM,)])
def test_without_the_target_s_name_typed_nothing_is_sent(answers):
    steps = FakeSteps()
    code, out = _main(steps, *answers)
    assert code == 1
    assert [c[0] for c in steps.calls] == ["preflight", "locate"]


def test_the_name_is_typed_for_a_wire_nobody_calls_destructive_too():
    steps = FakeSteps()
    code, out = _main(steps, args=("--target", VM, "--scenario", "T1110.001"))
    assert code == 1 and "Tape le nom de la VM cible" in out and "aucun nom tapé" in out
    assert "launch" not in [c[0] for c in steps.calls]


@pytest.mark.parametrize("hits", [[], [{"rg": "a", "id": VM_ID}, {"rg": "b", "id": VM_ID.replace("rg-celebrimbor", "rg-other")}]])
def test_one_vm_of_that_name_or_nothing_is_asked(hits):
    steps = FakeSteps(hits=hits)
    code, out = _main(steps, VM, "o")
    assert code == 1 and "une seule attendue" in out
    assert [c[0] for c in steps.calls] == ["preflight", "locate"]


# ── the launch, then the report ───────────────────────────────────────────────

def test_the_request_and_the_name_typed_go_to_orodruin_then_each_run_is_reported():
    steps = FakeSteps()
    code, out = _main(steps, VM, "o")
    assert code == 0, out
    kinds = [c[0] for c in steps.calls]
    assert kinds == ["preflight", "locate", "point", "launch", "report"]
    rid = steps.calls[3][1]
    req = xr.read(steps.sent[f"{rid}.json"])
    assert [(w.experiment, w.target, w.rank) for w in req.wires] == [("T1486", VM_ID, 1)]
    assert xr.read_typed(steps.sent[f"{rid}.typed.json"], req) == {1: VM}
    assert steps.calls[4] == ("report", "20261110T101500Z-t1486", VM)
    assert "DESTRUCTIVE" in out
    assert f"make bench-restore TARGET={VM} RUN=20261110T101500Z-t1486" in out      # the run named


def test_dry_run_sends_nothing():
    steps = FakeSteps()
    code, out = _main(steps, VM, "o", env={"BENCH_DRY_RUN": "1"})
    assert code == 0 and "DRY_RUN : rien n'est envoyé" in out
    assert "launch" not in [c[0] for c in steps.calls]


def test_a_run_nobody_names_is_said_without_a_report():
    steps = FakeSteps(launch=(1, []))
    code, out = _main(steps, VM, "o")
    assert code == 1 and "aucun run" in out
    assert "report" not in [c[0] for c in steps.calls]


def test_a_failed_wire_or_report_is_a_failure():
    assert _main(FakeSteps(launch=(1, ["r1"])), VM, "o")[0] == 1
    assert _main(FakeSteps(report=1), VM, "o")[0] == 1


@pytest.fixture
def fake_orodruin(tmp_path):
    """`ssh` and `scp` that log their argv; scp copies to orodruin/; the ssh of the run prints what
    an injector prints (with rich's colours), then the runner's last line."""
    bindir, oro = tmp_path / "bin", tmp_path / "orodruin"
    bindir.mkdir()
    oro.mkdir()
    log = tmp_path / "calls.jsonl"
    common = (f"#!{sys.executable}\nimport json, os, shutil, sys\n"
              f"open({str(log)!r}, 'a').write(json.dumps({{'cmd': os.path.basename(sys.argv[0]), "
              "'argv': sys.argv[1:]}) + '\\n')\n")
    (bindir / "ssh").write_text(common + (
        "if 'exercise_runner' in sys.argv[-1]:\n"
        "    print('→ wire 1: technique T1486 on vm-celebrimbor-gondolin')\n"
        "    print('\\x1b[1mRun:\\x1b[0m 20261110T101500Z-t1486')\n"
        "    print('Request finished: 1/1 wire(s) run.')\n"))
    (bindir / "scp").write_text(common + (
        "for a in sys.argv[1:-1]:\n"
        f"    shutil.copy(a, {str(oro)!r}) if os.path.isfile(a) else None\n"))
    for f in ("ssh", "scp"):
        (bindir / f).chmod(0o755)

    def calls():
        return [json.loads(ln) for ln in log.read_text().splitlines()] if log.exists() else []
    return bindir, oro, calls


PINNED = ("ssh -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/k -o HostKeyAlgorithms=ssh-ed25519 "
          "orodruin@10.0.0.5")


def test_the_launch_carries_the_request_and_removes_the_name_typed(fake_orodruin, tmp_path, monkeypatch):
    bindir, oro, calls = fake_orodruin
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    folder = tmp_path / "req"
    folder.mkdir()
    req = xr.new([("T1486", VM_ID)])
    (folder / f"{req.id}.json").write_text(json.dumps(req.to_dict()))
    (folder / f"{req.id}.typed.json").write_text(json.dumps({"request": req.id, "typed": {"1": VM}}))
    steps = brun.Steps({"BENCH_ORO_SSH": PINNED, "BENCH_ORO_RUN_REQUEST": "docker run --rm img"})
    lines: list[str] = []
    code, runs = steps.launch(folder, req.id, lines.append)
    assert code == 0 and runs == ["20261110T101500Z-t1486"]
    seen = calls()
    assert [c["cmd"] for c in seen] == ["ssh", "scp", "ssh"]
    assert seen[0]["argv"][-1] == "mkdir -p requests && chmod 700 requests"
    assert seen[1]["argv"][-1] == "orodruin@10.0.0.5:requests/"
    assert "StrictHostKeyChecking=yes" in seen[1]["argv"]
    run = seen[2]["argv"][-1]
    assert run.startswith(f"trap 'rm -f requests/{req.id}.typed.json' EXIT HUP INT TERM; docker run --rm img ")
    assert run.endswith(f"python -m eregion_core.exercise_runner /app/requests/{req.id}.json")
    assert sorted(p.name for p in oro.iterdir()) == sorted([f"{req.id}.json", f"{req.id}.typed.json"])


@pytest.mark.parametrize("ssh", ["ssh -o StrictHostKeyChecking=accept-new orodruin@10.0.0.5", "", "ssh orodruin@"])
def test_an_orodruin_whose_host_key_is_not_pinned_gets_nothing(fake_orodruin, tmp_path, monkeypatch, ssh):
    bindir, oro, calls = fake_orodruin
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    steps = brun.Steps({"BENCH_ORO_SSH": ssh, "BENCH_ORO_RUN_REQUEST": "docker run --rm img"})
    with pytest.raises(RuntimeError):
        steps.launch(tmp_path, "r-20261110T101500Z-a1b2c3", print)
    assert calls() == []


# ── through make ──────────────────────────────────────────────────────────────

@pytest.fixture
def fake_world(tmp_path):
    """Every outside command a run could reach, each logging its call: none must be."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "calls.log"
    for name in ("ssh", "scp", "az", "terraform", "docker", "curl"):
        (bindir / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
        (bindir / name).chmod(0o755)
    return bindir, log


@needs_make
@pytest.mark.parametrize("target,args", [("bench-run", ["SCENARIO=T1486"]), ("bench-restore", ["BEFORE=2026-11-10T10:00:00+00:00"])])
def test_make_refuses_in_an_agent_session_before_anything_runs(fake_world, tmp_path, target, args):
    bindir, log = fake_world
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path),
           "EREGION_AGENT_SESSION": "1"}
    for k in ("TARGET", "SCENARIO", "BEFORE", "RUN"):
        env.pop(k, None)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"PYTHON={sys.executable}",
                          f"TARGET={VM}", *args], capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode != 0
    assert "jamais une attaque ni un restore" in res.stdout + res.stderr
    assert not log.exists() or log.read_text() == ""


@needs_make
@pytest.mark.parametrize("target,args,from_env", [
    ("bench-run-go", ["SCENARIO=T1486"], {"TARGET": VM}),
    ("bench-run-go", [f"TARGET={VM}", "SCENARIO=T1486"], {"POINT_MAX_H": "1"}),
    ("bench-restore-go", [], {"TARGET": VM}),
    ("bench-restore-go", [f"TARGET={VM}"], {"RUN": "r1"}),
])
def test_the_internal_targets_refuse_a_variable_from_the_environment(fake_world, tmp_path, target, args, from_env):
    """`make bench-run-go` called directly: the origin checked again (review round 2). Make has read the
    addresses (terraform output, said in the Makefile) — never an ssh, an scp nor an az."""
    bindir, log = fake_world
    env = {k: v for k, v in os.environ.items() if k not in ("TARGET", "SCENARIO", "BEFORE", "RUN", "POINT_MAX_H")}
    env.update(PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path), **from_env)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, f"PYTHON={sys.executable}", *args],
                         capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode != 0 and "vient de l'environnement" in res.stderr, res.stdout + res.stderr
    calls = log.read_text().splitlines() if log.exists() else []
    assert not [c for c in calls if c.split()[0] in ("ssh", "scp", "az")], calls


@needs_make
def test_make_refuses_a_target_from_the_environment(fake_world, tmp_path):
    bindir, log = fake_world
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "HOME": str(tmp_path),
           "TARGET": VM}
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), "bench-run", f"PYTHON={sys.executable}",
                          "SCENARIO=T1486"], capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode != 0 and "vient de l'environnement" in res.stderr
    assert not log.exists() or log.read_text() == ""


# ── BNC3a (#753): the report, once the run's cycle is written ─────────────────

def test_the_report_waits_for_the_run_s_cycle(monkeypatch):
    import bench_report
    seen = []
    monkeypatch.setattr(bench_report, "main", lambda argv, env: seen.append((argv, env)) or 0)
    env = dict(CLEAN)
    assert brun.Steps(env).report("20261110T101500Z-t1486", VM) == 0
    assert seen == [(["--run", "20261110T101500Z-t1486", "--target", VM, "--wait", "cycle"], env)]


@needs_make
def test_bench_restore_is_given_imladris_s_ssh_for_its_report(fake_world, tmp_path):
    """The report after the lift reads Imladris: `bench-restore-go` hands the script its ssh command, as
    `bench-run-go` does — the script stands for python here, and prints what it was given."""
    bindir, log = fake_world
    (bindir / "terraform").write_text(f'#!/bin/sh\necho "terraform $*" >> "{log}"\necho 192.0.2.10\n')
    script = tmp_path / "python"
    script.write_text('#!/bin/sh\necho "H0=$BENCH_H0_SSH"\n')
    script.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("TARGET", "SCENARIO", "BEFORE", "RUN", "POINT_MAX_H")}
    env.update(PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path))
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), "bench-restore-go", f"PYTHON={script}",
                          f"TARGET={VM}"], capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "H0=ssh " in res.stdout and res.stdout.strip().endswith("@192.0.2.10")
    calls = log.read_text().splitlines() if log.exists() else []
    assert not [c for c in calls if c.split()[0] in ("ssh", "scp", "az", "docker")], calls


# ── BNC3b (#770): the clean point, the route of the 📸 button, the preflight replayed ──

DIRTY_POINT = {"clean": False, "said": "le plus récent (09:00:00) est pris dans une quarantaine (depuis 08:50:00, "
                                       "sans levée lue)", "point": 1.0, "vault": "rsv", "vault_rg": "rg"}


def _journal(steps, *answers, **kw):
    """The run's journal: each step of the fake, and each question asked, in their order."""
    feed = list(answers)
    journal = steps.calls

    def ask(prompt):
        journal.append(("ask", prompt))
        if not feed:
            raise EOFError
        return feed.pop(0)
    said: list[str] = []
    code = brun.main(["--target", VM, "--scenario", "T1486"], {**CLEAN, **kw.get("env", {})}, cwd=Path("/"),
                     here=Path("/"), ask=ask, say=said.append, steps=steps, tty=True)
    return code, [c[0] for c in journal], "\n".join(said)


def test_a_clean_point_is_kept_and_read_after_the_confirmation():
    steps = FakeSteps()
    code, kinds, out = _journal(steps, VM, "o")
    assert code == 0, out
    assert kinds == ["preflight", "locate", "ask", "ask", "point", "launch", "report"]
    assert "✓ le point : gardé" in out and "snapshot" not in kinds


@pytest.mark.parametrize("answers", [(VM, "n"), ("vm-celebrimbor-bree", "o"), ()])
def test_nothing_is_read_nor_written_for_the_point_before_the_confirmation(answers):
    """A name mistyped, or « N »: neither the point read, nor the 📸, nor Orodruin."""
    steps = FakeSteps(point=DIRTY_POINT)
    code, kinds, _ = _journal(steps, *answers)
    assert code == 1
    assert not {"point", "snapshot", "launch"} & set(kinds), kinds


def test_a_point_not_clean_takes_the_snapshot_route_then_the_preflight_is_replayed():
    steps = FakeSteps(point=DIRTY_POINT)
    code, kinds, out = _journal(steps, VM, "o")
    assert code == 0, out
    assert kinds == ["preflight", "locate", "ask", "ask", "point", "snapshot", "rejudge", "preflight", "launch",
                     "report"]
    last_ask = max(i for i, k in enumerate(kinds) if k == "ask")
    assert kinds.index("snapshot") > last_ask                    # nothing written before the confirmation
    assert "route du bouton 📸" in out and "le préflight rejoué" in out


@pytest.mark.parametrize("why", ["la demande d'instantané : not_taken", "la demande d'instantané : untrusted",
                                 "la demande d'instantané : refused (point_refused)", "la demande d'instantané : failed",
                                 "la demande d'instantané : expired", "le job du coffre : Failed",
                                 "le job du coffre n'est pas Completed en 60 min",
                                 "le jeton de la console manque"])
def test_each_refusal_of_the_snapshot_stops_the_run_before_orodruin(why):
    steps = FakeSteps(point=DIRTY_POINT, snapshot=RuntimeError(why))
    code, kinds, out = _journal(steps, VM, "o")
    assert code == 1
    assert "launch" not in kinds and kinds.count("preflight") == 1
    assert why in out and "rien n'est envoyé à Orodruin" in out


def test_a_red_replayed_preflight_stops_the_run_just_before_the_attack():
    steps = FakeSteps(point=DIRTY_POINT, preflight=[0, 1])
    code, kinds, out = _journal(steps, VM, "o")
    assert code == 1
    assert kinds[-3:] == ["snapshot", "rejudge", "preflight"] and "launch" not in kinds
    assert "Le point pris reste" in out


def test_a_point_that_cannot_be_read_is_no_clean_point():
    steps = FakeSteps(point=RuntimeError("az: boom"))
    code, kinds, out = _journal(steps, VM, "o")
    assert code == 1 and "launch" not in kinds and "snapshot" not in kinds
    assert "illisible" in out


def test_dry_run_reads_the_point_and_takes_none():
    steps = FakeSteps(point=DIRTY_POINT)
    code, kinds, out = _journal(steps, VM, "o", env={"BENCH_DRY_RUN": "1"})
    assert code == 0, out
    assert "point" in kinds and "snapshot" not in kinds and "launch" not in kinds
    assert "sans DRY_RUN, un nouveau par la route du bouton 📸" in out


FAKE_TOKEN = "fake-console-tok-K4"


def _checkout(tmp_path, under: Path | None = None) -> Path:
    """The operator's checkout, outside a lot's worktree — or under one (`under`): the guard of a code
    session reads where the scripts run from (bench_shared.session_refusal)."""
    root = (under or tmp_path) / "checkout"
    for rel in ("Makefile", "scripts/mobile.py", "scripts/bench_shared.py"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, root / rel)
    return root


def _spy_python(tmp_path) -> Path:
    spy = tmp_path / "python"
    spy.write_text('#!/bin/sh\necho "ARGV=$0 $*"\necho "TOK=$BENCH_CONSOLE_TOKEN"\n')
    spy.chmod(0o755)
    return spy


@needs_make
@pytest.mark.parametrize("where", ["env", "worktree"])
def test_the_console_s_token_is_refused_to_a_code_session_by_its_guard(fake_world, tmp_path, where):
    """BNC3b: bench-run-go reads the console's token in host.env — after CONSOLE_GUARD, which refuses a
    code session before anything is read: no token printed, the script never run."""
    bindir, log = fake_world
    host_env = tmp_path / "host.env"
    host_env.write_text(f"EREGION_CONSOLE_TOKEN={FAKE_TOKEN}\n")
    root = _checkout(tmp_path, tmp_path / "eregion" / ".claude" / "worktrees" / "lot-x" if where == "worktree" else None)
    env = {k: v for k, v in os.environ.items() if k not in ("TARGET", "SCENARIO", "BEFORE", "RUN", "POINT_MAX_H",
                                                            "EREGION_AGENT_SESSION")}
    env.update(PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path))
    if where == "env":
        env["EREGION_AGENT_SESSION"] = "1"
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(root), "bench-run-go",
                          f"PYTHON={_spy_python(tmp_path)}", f"TARGET={VM}", "SCENARIO=T1486", f"HOST_ENV={host_env}"],
                         capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode != 0
    assert "make bench-run refusé" in res.stdout + res.stderr, res.stdout + res.stderr
    assert FAKE_TOKEN not in res.stdout + res.stderr and "TOK=" not in res.stdout


@needs_make
def test_the_console_s_token_reaches_the_script_by_its_environment_never_its_argv(fake_world, tmp_path):
    bindir, log = fake_world
    host_env = tmp_path / "host.env"
    host_env.write_text(f"GLORFINDEL_WARROOM_TOKEN=old\nEREGION_CONSOLE_TOKEN={FAKE_TOKEN}  # le jeton\n")
    env = {k: v for k, v in os.environ.items() if k not in ("TARGET", "SCENARIO", "BEFORE", "RUN", "POINT_MAX_H",
                                                            "EREGION_AGENT_SESSION")}
    env.update(PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}", HOME=str(tmp_path))
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(_checkout(tmp_path)), "bench-run-go",
                          f"PYTHON={_spy_python(tmp_path)}", f"TARGET={VM}", "SCENARIO=T1486", f"HOST_ENV={host_env}"],
                         capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    argv = next(x for x in res.stdout.splitlines() if x.startswith("ARGV="))
    assert argv.endswith("scripts/bench_run.py") and FAKE_TOKEN not in argv
    assert f"TOK={FAKE_TOKEN}" in res.stdout.splitlines()
    # no host.env: an empty token, the script still runs (it asks for the token only for a 📸)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(_checkout(tmp_path / "b")), "bench-run-go",
                          f"PYTHON={_spy_python(tmp_path)}", f"TARGET={VM}", "SCENARIO=T1486",
                          f"HOST_ENV={tmp_path / 'absent.env'}"], capture_output=True, text=True, env=env, timeout=60)
    assert res.returncode == 0 and "TOK=" in res.stdout.splitlines(), res.stdout + res.stderr


def test_the_steps_hand_the_point_and_the_snapshot_to_their_module(monkeypatch):
    import bench_snapshot
    seen = []
    monkeypatch.setattr(bench_snapshot, "judge",
                        lambda target, env, config: seen.append(("judge", target, config)) or DIRTY_POINT)
    monkeypatch.setattr(bench_snapshot, "take",
                        lambda target, env, plan, say, token: seen.append(("take", target, plan)) or 3.0)
    steps = brun.Steps(dict(CLEAN))
    assert steps.point(VM) is DIRTY_POINT
    assert steps.snapshot(VM, DIRTY_POINT, print, "t") == 3.0
    assert seen[0][:2] == ("judge", VM) and seen[0][2].endswith("glorfindel-config.yaml")
    assert seen[1] == ("take", VM, DIRTY_POINT)


def test_the_console_s_token_is_taken_out_of_every_child_s_environment(monkeypatch):
    """BNC3b review: read once by bench-run, then out of the environment of az, ssh, scp and the
    preflight — the 📸 route alone takes it, as an argument."""
    monkeypatch.setenv(brun.TOKEN_ENV, "tok-Q")
    env = {**CLEAN, brun.TOKEN_ENV: "tok-Q"}
    steps = FakeSteps(point=DIRTY_POINT)
    said: list[str] = []
    feed = [VM, "o"]
    code = brun.main(["--target", VM, "--scenario", "T1486"], env, cwd=Path("/"), here=Path("/"),
                     ask=lambda p: feed.pop(0), say=said.append, steps=steps, tty=True)
    assert code == 0, said
    assert brun.TOKEN_ENV not in env and brun.TOKEN_ENV not in os.environ
    assert steps.token == "tok-Q"
    assert brun.TOKEN_ENV not in brun.Steps({brun.TOKEN_ENV: "x", "A": "1"}).env
    assert "tok-Q" not in "\n".join(said)


def test_a_point_taken_but_judged_again_not_clean_stops_the_run():
    """BNC3b review: the point the 📸 route took is judged again — an isolation opened during the job, a
    quarantine still open: refused, nothing goes to Orodruin."""
    steps = FakeSteps(point=DIRTY_POINT, rejudged=(False, "le plus récent (10:00:00) est pris dans une quarantaine "
                                                          "(depuis 09:50:00, sans levée lue)"))
    code, kinds, out = _journal(steps, VM, "o")
    assert code == 1
    assert kinds[-2:] == ["snapshot", "rejudge"] and "launch" not in kinds
    assert "le point pris, rejugé" in out and "quarantaine" in out
