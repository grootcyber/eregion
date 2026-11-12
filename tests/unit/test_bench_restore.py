"""`make bench-restore TARGET=<vm> [BEFORE=…]`: the bench's restore from the workstation (MOB1, #686).

The steps are fakes (the VM read on Azure, the workstation's vault, `glorfindel restore`): nothing
reaches Azure. The oracles are written here: never in a code session; never without the console's
pair (its names said, never its values); `--before` the run's T0 — its attack_started, SEC4c — unless
BEFORE= is given, and never a moment ahead; `--keep-isolated` always, the lift being H0's; the VM's
name typed, then a dry run, then « [o/N] »; the restore under the console's pair alone.
"""
from __future__ import annotations

import importlib.util
import json
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
brs = _load("bench_restore")

VM = "vm-celebrimbor-gondolin"
VM_ID = ("/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-celebrimbor/providers/"
         f"Microsoft.Compute/virtualMachines/{VM}")
CONSOLE_ID, CONSOLE_SECRET = "console-client-id", "console-secret-value"
PAIR = {"EREGION_CONSOLE_AZURE_CLIENT_ID": CONSOLE_ID, "EREGION_CONSOLE_AZURE_CLIENT_SECRET": CONSOLE_SECRET,
        "AZURE_CLIENT_ID": "the-watch-s-id", "AZURE_CLIENT_SECRET": "the-watch-s-secret"}
NOW = 1_762_800_000.0          # 2025-11-10T18:40:00Z, after every moment of these tests
T0 = "2025-11-10T16:43:02.800000+00:00"


class FakeSteps:
    def __init__(self, hits=None, vault=("rsv-celebrimbor-erebor", "rg-celebrimbor", "stcelebrimborstaging"),
                 dry=0, real=0, report=0):
        self.calls: list[tuple] = []
        self._hits = [{"rg": "rg-celebrimbor", "id": VM_ID}] if hits is None else hits
        self._vault, self._dry, self._real, self._report = vault, dry, real, report

    def report(self, run_id, target):
        self.calls.append(("report", run_id, target))
        return self._report

    def locate(self, target):
        self.calls.append(("locate", target))
        return self._hits

    def vault(self):
        self.calls.append(("vault",))
        return self._vault

    def restore(self, argv, env):
        self.calls.append(("restore", argv, env))
        return self._dry if "--dry-run" in argv else self._real


@pytest.fixture
def runs(tmp_path):
    d = tmp_path / "runs" / "bench"
    d.mkdir(parents=True)

    def report(run_id, target=VM, t0=T0):
        # composed_at: when `make bench-report` wrote it, after the attack — never the moment.
        (d / f"{run_id}.json").write_text(json.dumps({"format": 1, "run_id": run_id, "target": target, "t0": t0,
                                                      "composed_at": "2025-11-10T18:30:00+00:00"}))
    return d, report


def _main(steps, runs_dir, *answers, env=None, cwd=None, here=None, args=("--target", VM), tty=True):
    said: list[str] = []
    feed = list(answers)

    def ask(prompt):
        said.append(prompt)
        if not feed:
            raise EOFError
        return feed.pop(0)
    base = {"PATH": "/usr/bin", **PAIR}
    code = brs.main(list(args), {**base, **(env or {})}, cwd=cwd or Path("/"), here=here or Path("/"),
                    runs_dir=runs_dir, ask=ask, say=said.append, steps=steps, now=NOW, tty=tty)
    return code, "\n".join(said)


def _restores(steps):
    return [c for c in steps.calls if c[0] == "restore"]


# ── never in a code session ───────────────────────────────────────────────────

@pytest.mark.parametrize("where", ["env", "cwd", "here"])
def test_a_code_session_is_refused_before_any_step(tmp_path, runs, where):
    d, report = runs
    report("r1")
    lot = tmp_path / "eregion" / ".claude" / "worktrees" / "lot-x"
    lot.mkdir(parents=True)
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o", env={"EREGION_AGENT_SESSION": "1"} if where == "env" else None,
                      cwd=lot if where == "cwd" else tmp_path, here=lot if where == "here" else tmp_path)
    assert code == 1 and "refusé" in out and "ni un restore" in out
    assert steps.calls == []


# ── the pair, the moment ──────────────────────────────────────────────────────

@pytest.mark.parametrize("missing", ["EREGION_CONSOLE_AZURE_CLIENT_ID", "EREGION_CONSOLE_AZURE_CLIENT_SECRET"])
def test_without_the_console_s_pair_nothing_is_restored(runs, missing):
    d, report = runs
    report("r1")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o", env={missing: " "})
    assert code == 1 and missing in out and "RST1" in out
    assert CONSOLE_SECRET not in out and steps.calls == []


def test_without_a_terminal_nothing_is_read_and_nothing_is_restored(runs):
    d, report = runs
    report("r1")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o", tty=False)
    assert code == 1 and "pas de terminal" in out and steps.calls == []


def test_before_defaults_to_the_t0_of_the_one_run_of_the_target(runs):
    d, report = runs
    report("r-new")
    report("r-bree", target="vm-celebrimbor-bree", t0="2025-11-10T17:00:00+00:00")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o")
    assert code == 0, out
    dry, real = _restores(steps)
    assert dry[1] == ["restore", VM_ID, "--before", T0, "--keep-isolated", "--dry-run"]
    assert real[1] == ["restore", VM_ID, "--before", T0, "--keep-isolated", "--wait", "--yes"]
    said = out.index("le T0 du run r-new")
    assert said < out.index("Tape le nom de la VM")                  # the run shown before the name


def test_two_runs_of_the_target_are_listed_never_chosen(runs):
    """The latest report is not the safe way of SEC4c: the operator names the run (MOB1, review round 1)."""
    d, report = runs
    report("r-old", t0="2025-11-09T10:00:00+00:00")
    report("r-new")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o")
    assert code == 1 and "2 rapports" in out and "r-old" in out and "r-new" in out and "RUN=" in out
    assert steps.calls == []


def test_run_names_its_report_and_before_wins(runs):
    d, report = runs
    report("r-old", t0="2025-11-09T10:00:00+00:00")
    report("r-new")
    steps = FakeSteps()
    assert _main(steps, d, VM, "o", env={"BENCH_RUN": "r-old"})[0] == 0
    assert _restores(steps)[0][1][3] == "2025-11-09T10:00:00+00:00"
    steps = FakeSteps()
    assert _main(steps, d, VM, "o", env={"BENCH_BEFORE": "2025-11-10T15:00:00Z", "BENCH_RUN": "r-old"})[0] == 0
    assert _restores(steps)[0][1][3] == "2025-11-10T15:00:00+00:00"


@pytest.mark.parametrize("env,said", [
    ({}, "aucun rapport de"),
    ({"BENCH_RUN": "r-none"}, "aucun rapport du run r-none"),
    ({"BENCH_RUN": "r-bree"}, "ne visait pas"),
    ({"BENCH_BEFORE": "2027-01-01T00:00:00+00:00"}, "futur"),
    ({"BENCH_BEFORE": "hier"}, "pas un instant"),
])
def test_no_moment_no_restore(runs, env, said):
    d, report = runs
    report("r-bree", target="vm-celebrimbor-bree")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o", env=env)
    assert code == 1 and said in out and steps.calls == []


def test_a_report_that_is_a_link_is_never_read(runs, tmp_path):
    d, _ = runs
    elsewhere = tmp_path / "planted.json"
    elsewhere.write_text(json.dumps({"run_id": "r-x", "target": VM, "t0": "2025-11-10T18:00:00+00:00"}))
    (d / "r-x.json").symlink_to(elsewhere)
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o")
    assert code == 1 and "aucun rapport de" in out and steps.calls == []


# ── the target, the name typed ────────────────────────────────────────────────

@pytest.mark.parametrize("answers", [(), ("", "o"), ("vm-celebrimbor-bree", "o"), ("Vm-Celebrimbor-Gondolin", "o")])
def test_without_the_vm_s_name_typed_nothing_is_restored(runs, answers):
    d, report = runs
    report("r1")
    steps = FakeSteps()
    code, out = _main(steps, d, *answers)
    assert code == 1 and _restores(steps) == []


@pytest.mark.parametrize("vault", [("", "", ""), ("rsv", "rg", "")])
def test_a_workstation_without_its_vault_or_staging_account_restores_nothing(runs, vault):
    d, report = runs
    report("r1")
    steps = FakeSteps(vault=vault)
    code, out = _main(steps, d, VM, "o")
    assert code == 1 and "glorfindel-config.yaml" in out and _restores(steps) == []


def test_one_vm_of_that_name_or_nothing(runs):
    d, report = runs
    report("r1")
    steps = FakeSteps(hits=[{"rg": "a", "id": VM_ID}, {"rg": "b", "id": VM_ID}])
    code, out = _main(steps, d, VM, "o")
    assert code == 1 and "une seule attendue" in out and _restores(steps) == []


# ── the dry run, then the restore, under the console's pair ──────────────────

def test_the_restore_runs_under_the_console_s_pair_alone(runs):
    d, report = runs
    report("r1")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o")
    assert code == 0
    for _, argv, env in _restores(steps):
        assert "--keep-isolated" in argv
        assert env["AZURE_CLIENT_ID"] == CONSOLE_ID and env["AZURE_CLIENT_SECRET"] == CONSOLE_SECRET
        assert env["GLORFINDEL_READ_ONLY"] == "0"
    assert CONSOLE_SECRET not in out and "la paire de la console" in out and "--keep-isolated" in out


def test_dry_run_a_failed_dry_run_or_a_no_stop_before_the_restore(runs):
    d, report = runs
    report("r1")
    steps = FakeSteps()
    assert _main(steps, d, VM, env={"BENCH_DRY_RUN": "1"})[0] == 0
    assert [("--dry-run" in c[1]) for c in _restores(steps)] == [True]
    steps = FakeSteps(dry=1)
    assert _main(steps, d, VM, "o")[0] == 1
    assert len(_restores(steps)) == 1
    steps = FakeSteps()
    assert _main(steps, d, VM, "n")[0] == 1
    assert len(_restores(steps)) == 1


def test_the_restore_s_own_failure_is_the_command_s(runs):
    d, report = runs
    report("r1")
    assert _main(FakeSteps(real=3), d, VM, "o")[0] == 3


def test_the_restore_argv_always_keeps_the_isolation():
    for dry in (True, False):
        argv = brs.restore_argv(VM_ID, T0, dry=dry)
        assert argv[:5] == ["restore", VM_ID, "--before", T0, "--keep-isolated"]


# ── BNC3a (#753): the report, after the lift ──────────────────────────────────

def test_the_restore_done_the_report_follows_the_lift_of_the_run(runs):
    d, report = runs
    report("r1")
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o")
    assert code == 0, out
    assert [c[0] for c in steps.calls] == ["locate", "vault", "restore", "restore", "report"]
    assert steps.calls[-1] == ("report", "r1", VM)
    assert "il suit la levée par Imladris, en lecture, 30 min au plus" in out


def test_the_report_is_the_run_of_run_even_with_before(runs):
    d, report = runs
    report("r-old", t0="2025-11-09T10:00:00+00:00")
    report("r-new")
    steps = FakeSteps()
    assert _main(steps, d, VM, "o", env={"BENCH_BEFORE": "2025-11-10T15:00:00Z", "BENCH_RUN": "r-old"})[0] == 0
    assert steps.calls[-1] == ("report", "r-old", VM)


def test_before_without_run_names_no_run_and_composes_no_report(runs):
    d, _ = runs
    steps = FakeSteps()
    code, out = _main(steps, d, VM, "o", env={"BENCH_BEFORE": "2025-11-10T15:00:00Z"})
    assert code == 0, out
    assert "report" not in [c[0] for c in steps.calls]
    assert "BEFORE= sans RUN= ne nomme aucun run, aucun rapport n'est composé" in out


@pytest.mark.parametrize("env,answers,real", [({"BENCH_DRY_RUN": "1"}, (VM,), 0), ({}, (VM, "n"), 0),
                                              ({}, (VM, "o"), 3)])
def test_no_restore_done_no_report(runs, env, answers, real):
    d, report = runs
    report("r1")
    steps = FakeSteps(real=real)
    _main(steps, d, *answers, env=env)
    assert "report" not in [c[0] for c in steps.calls]


def test_the_restore_done_and_the_report_failed_is_said_and_a_failure(runs):
    d, report = runs
    report("r1")
    code, out = _main(FakeSteps(report=1), d, VM, "o")
    assert code == 1
    assert "le restore a abouti ; le rapport n'a pas pu être composé : make bench-report RUN=r1" in out


def test_the_report_waits_for_the_lift_under_the_operator_s_environment(monkeypatch):
    """`--wait lift`, the run and the target; the environment the operator's — never the console's
    pair, which is the restore's alone (pair_env)."""
    import bench_report
    seen = []
    monkeypatch.setattr(bench_report, "main", lambda argv, env: seen.append((argv, env)) or 0)
    env = {"PATH": "/usr/bin", **PAIR}
    assert brs.Steps(env).report("r1", VM) == 0
    (argv, given), = seen
    assert argv == ["--run", "r1", "--target", VM, "--wait", "lift"]
    assert given is env and given["AZURE_CLIENT_ID"] == "the-watch-s-id" and "GLORFINDEL_READ_ONLY" not in given
