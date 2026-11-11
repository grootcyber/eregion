"""MUT7 (#699): the mutants only an invariant machine kills, measured each night on seeds drawn
(scripts/mutation_night.py), and the workflow that opens an issue for a fragile one
(.github/workflows/mutants-night.yml, pushed by Jonathan).

Here on mutants, test files and runs written by the test: no test suite runs, nothing is copied but a
file of the test's own. The workflow's issue step runs against a fake `gh`: nothing leaves.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
NIGHT_YML = ROOT / ".github" / "workflows" / "mutants-night.yml"


def _load():
    spec = importlib.util.spec_from_file_location("mutation_night_mut7", ROOT / "scripts" / "mutation_night.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mutation_night_mut7"] = mod
    spec.loader.exec_module(mod)
    return mod


night = _load()
mc = night.mc

# A machine's file, as the harness reads one. Its first lines written so that this file is not one:
# mutation_check reads, line by line, a file that imports Hypothesis or defines a machine.
MACHINE_FILE = '''_FROM_ hypothesis.stateful import RuleBasedStateMachine, run_state_machine_as_test


_CLASS_ FakeMachine(RuleBasedStateMachine):
    pass


class LongerMachine(FakeMachine):
    pass


def test_the_machine():
    run_state_machine_as_test(FakeMachine)


def test_a_plain_one():
    assert True


TestLonger = LongerMachine.TestCase
'''.replace("_FROM_", "from").replace("_CLASS_", "class")
PLAIN_FILE = '''def test_c():
    assert True


def test_d():
    assert True
'''
# A fixed file that draws (Hypothesis, no machine): its first line written as MACHINE_FILE's.
DRAWING_FILE = '''_FROM_ hypothesis import given, strategies


@given(strategies.integers())
def test_h(n):
    assert True
'''.replace("_FROM_", "from")
M, F, H = "tests/unit/test_m.py", "tests/unit/test_f.py", "tests/unit/test_h.py"


@pytest.fixture(autouse=True)
def _sources(monkeypatch):
    """The test files the harness reads, the test's own; ChromaDB's model never prepared."""
    monkeypatch.setattr(mc, "_SOURCES", {M: MACHINE_FILE, F: PLAIN_FILE, H: DRAWING_FILE,
                                         "tests/unit/gone.py": None})
    monkeypatch.setattr(night, "_MACHINE_TESTS", {})
    monkeypatch.setattr(mc, "prepare_embedding_model", lambda say=print: None)


# ── which mutants: the machine's test reached, nothing else, or beside fixed tests ───────────

def test_a_files_machine_tests_are_those_that_run_one_of_its_machines():
    assert night.machine_tests(M) == {"test_the_machine", "TestLonger"}
    assert night.machine_tests(F) == frozenset()
    assert night.machine_tests("tests/unit/gone.py") is None


@pytest.mark.parametrize("target, machine, fixed", [
    (M, [M], []),                                                   # the file whole
    (f"{M}::test_the_machine", [f"{M}::test_the_machine"], []),     # its machine's test
    (f"{M}::TestLonger::runTest", [f"{M}::TestLonger::runTest"], []),
    (f"{M}::test_a_plain_one", [], [f"{M}::test_a_plain_one"]),     # a plain test of a machine's file
    (f"{M} {F}::test_c", [M], [f"{F}::test_c"]),
    (f"{F} -k the_machine {M}", [M], [F]),
    (f"{F} -k plain {M}", [], [F, M]),                              # the -k leaves the machine out
    (f"{F}::test_c", [], [f"{F}::test_c"]),
])
def test_a_target_splits_into_what_runs_a_machine_and_its_fixed_tests(target, machine, fixed):
    """MUT7: the rule, node by node — file by file, test_recovery_watch.py's plain tests read as its
    machine (mutation_check.machine)."""
    assert night.split(target)[:2] == (machine, fixed)


def _mutant(mid, why=None):
    m = (mid, f"bug {mid}", "code.py", f"line {mid}\n", f"LINE {mid}\n")
    return (*m, why) if why else m


def test_the_night_takes_each_counted_mutant_whose_target_runs_a_machine():
    mutants = [_mutant("M1"), _mutant("M2"), _mutant("M3"), _mutant("M4", "EQUIVALENT: no behaviour"),
               _mutant("M5", "TIMING: a race"), _mutant("M6")]
    tests = {"M1": M, "M2": f"{M} {F}::test_c", "M3": f"{F}::test_c", "M4": M, "M5": M,
             "M6": f"{M}::test_a_plain_one"}
    got = {i["mutant"][0]: i for i in night.chosen(mutants, tests)}
    assert sorted(got) == ["M1", "M2", "M5"]
    assert got["M1"]["kind"] == night.ALONE and got["M1"]["fixed"] == ""
    assert got["M2"]["kind"] == night.BESIDE and got["M2"]["fixed"] == f"{F}::test_c" and got["M2"]["machine"] == M


def test_the_trees_list_reads_the_invariant_machines():
    """On this tree: every mutant chosen runs a machine; the mutants of the invariants alone are
    ALONE; a target of test_recovery_watch.py that never names its machine's test is out."""
    items = night.chosen(night.mc.MUTANTS, night.mc.TESTS)
    assert items and all(night.split(i["target"])[0] for i in items)
    alone = [i for i in items if i["kind"] == night.ALONE]
    assert alone and all(not night.split(i["target"])[1] for i in alone)
    for m in night.mc.MUTANTS:
        t = night.mc.TESTS.get(m[0], night.mc.INVARIANTS)
        if t.startswith("tests/unit/test_recovery_watch.py::") and "test_never_a_release" not in t:
            assert m[0] not in {i["mutant"][0] for i in items}, m[0]


# ── the rotation: a mutant's night is its id's, the whole list in seven nights ──────────────

def test_a_mutants_night_is_fixed_by_its_id_alone():
    ids = [f"M{i}" for i in range(500)]
    nights = {mid: night.part_of(mid) for mid in ids}
    assert set(nights.values()) == set(range(1, night.PARTS + 1))
    assert {mid: night.part_of(mid) for mid in ids[:10]} == {mid: nights[mid] for mid in ids[:10]}


def test_seven_nights_in_a_row_are_each_night_once():
    """M4734: tonight's share comes round, every one of the seven, in any seven days in a row."""
    start = datetime.date(2026, 11, 10)
    days = [night.tonight(day=start + datetime.timedelta(days=d)) for d in range(night.PARTS)]
    assert sorted(days) == list(range(1, night.PARTS + 1))


@pytest.mark.parametrize("text, parsed", [("all", None), ("3/7", (3, 7)), ("1/1", (1, 1))])
def test_a_part_is_auto_all_or_k_of_n(text, parsed):
    assert night.parse_part(text) == parsed
    assert night.parse_part("auto") == (night.tonight(), night.PARTS)


@pytest.mark.parametrize("text", ["0/7", "8/7", "x", "", "3", "-1/7"])
def test_a_part_that_is_not_one_is_refused(text):
    with pytest.raises(Exception):
        night.parse_part(text)


# ── a night measured, end to end: CAUGHT n/n, flaky, SURVIVES, said with their replay ──────────

SEED = 100


def _world(monkeypatch, tmp_path, catches: dict, fixed_catches=(), base_fails=None, drawn=None):
    """main()'s copy and its pytest runs replaced. `catches`: {id: the seeds the machine catches it
    on}; `fixed_catches`: the ids its fixed tests catch. `drawn`: {id: the seeds a fixed part that
    draws catches it on} — given, MH is there too, beside such a part. Each run noted (copy, target,
    seed)."""
    mutants = [_mutant("MA"), _mutant("MB"), _mutant("MC"), _mutant("MD"), _mutant("ME", "TIMING: a race"),
               _mutant("MF")] + ([_mutant("MH")] if drawn is not None else [])
    drawn = drawn or {}
    monkeypatch.setattr(mc, "MUTANTS", mutants)
    monkeypatch.setattr(mc, "TESTS", {"MA": M, "MB": M, "MC": f"{M} {F}::test_c", "MD": f"{M} {F}::test_d",
                                      "ME": M, "MF": f"{F}::test_c", "MH": f"{M} {H}::test_h"})
    monkeypatch.setattr(mc, "load_durations", lambda path=None, say=print: mc.no_durations())
    monkeypatch.setattr(mc, "_copy_repo", lambda dest: (dest.mkdir(parents=True), (dest / "code.py").write_text(
        "".join(m[3] for m in mutants))))
    runs: list = []

    def pytest_(copy, examples, target, *more, seed=None):
        runs.append((copy.name, target, seed))
        if copy.name == "base":
            return types.SimpleNamespace(stdout="", returncode=1 if base_fails and base_fails(target, seed) else 0)
        code = (copy / "code.py").read_text()
        mid = next(m[0] for m in mutants if f"LINE {m[0]}" in code)
        caught = ((F in target and mid in fixed_catches) or (H in target and seed in drawn.get(mid, ()))
                  or (M in target and seed in catches.get(mid, ())))
        return types.SimpleNamespace(stdout="", returncode=1 if caught else 0)
    monkeypatch.setattr(mc, "_pytest", pytest_)
    return runs


CATCHES = {"MA": {100, 101, 102}, "MB": {101}, "MC": {100, 101, 102}, "MD": set(), "ME": set()}


def test_a_night_says_a_mutant_caught_on_every_seed_and_a_fragile_one_with_its_replay(tmp_path, monkeypatch,
                                                                                       capsys):
    """MUT7's « fini quand »: on cases of the test, a mutant caught on every seed (MA), a flaky one
    (MB, caught on one seed of three) and one beside fixed tests that miss it (MD), each said with
    the command that replays it on the seed it survived on."""
    _world(monkeypatch, tmp_path, CATCHES, fixed_catches={"MC"})
    out, said_to = tmp_path / "night.json", tmp_path / "github_output"
    assert night.main(["--seed", str(SEED), "--seeds", "3", "--jobs", "2", "--json", str(out),
                       "--output", str(said_to)]) == 0
    said = capsys.readouterr().out
    doc = json.loads(out.read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in doc["rows"]}
    assert sorted(rows) == ["MA", "MB", "MC", "MD", "ME"]                  # MF runs no machine
    assert (rows["MA"]["verdict"], rows["MA"]["detail"]) == ("CAUGHT", "3/3")
    assert (rows["MB"]["verdict"], rows["MB"]["detail"], rows["MB"]["survived_on"]) == ("flaky", "1/3", [100, 102])
    assert (rows["MC"]["verdict"], rows["MC"]["by"]) == ("CAUGHT", "fixed")
    assert (rows["MD"]["verdict"], rows["MD"]["survived_on"]) == ("SURVIVES", [100, 101, 102])
    assert rows["ME"]["verdict"] == "SURVIVES" and rows["ME"]["known"] == "TIMING"
    assert doc["fragile"] == ["MB", "MD"] and doc["seeds"] == [100, 101, 102] and doc["examples"] == 500
    assert "MA  CAUGHT    3/3" in said and "MB  flaky     1/3" in said
    for s in (100, 102):
        assert f"replay MB (seed {s}): python scripts/mutation_check.py --only MB --seed {s} --examples 500 --rounds 1" in said
    assert "replay MB (seed 101)" not in said and "replay MA" not in said and "replay ME" not in said
    assert "--only MB --seed 100 --seeds 3 --examples 500" in said
    assert said_to.read_text() == "fragile=MB:1/3:100,102 MD:0/3:100,101,102\nexamples=500\n"


def test_a_mutant_its_fixed_tests_catch_never_runs_its_machine(tmp_path, monkeypatch):
    """BESIDE: the fixed tests first, once; caught, the machine is not run on it (MC). Not caught,
    the machine alone on each seed (MD)."""
    runs = _world(monkeypatch, tmp_path, CATCHES, fixed_catches={"MC"})
    night.main(["--seed", str(SEED), "--json", str(tmp_path / "n.json")])
    assert [r for r in runs if r[0] == "MC"] == [("MC", f"{F}::test_c", 100)]
    assert [r for r in runs if r[0] == "MD"] == [("MD", f"{F}::test_d", 100)] + [("MD", M, s) for s in (100, 101, 102)]


def test_a_fixed_part_that_draws_is_no_fixed_killer_its_whole_target_runs_on_each_seed(tmp_path, monkeypatch):
    """M4736: a fixed part that draws (Hypothesis) catches the mutant on one seed only. Run once, on
    the first, it would say it CAUGHT 3/3 by its fixed tests — a false green. It never runs alone:
    the whole target runs on each seed, and the mutant is flaky."""
    runs = _world(monkeypatch, tmp_path, CATCHES, fixed_catches={"MC"}, drawn={"MH": {100}})
    out = tmp_path / "n.json"
    assert night.main(["--seed", str(SEED), "--only", "MH", "--json", str(out)]) == 0
    mine = [r for r in runs if r[0] == "MH"]
    assert mine == [("MH", f"{H}::test_h {M}", s) for s in (100, 101, 102)]
    (row,) = json.loads(out.read_text(encoding="utf-8"))["rows"]
    assert (row["verdict"], row["detail"], row["by"], row["survived_on"]) == ("flaky", "1/3", "machine", [101, 102])


@pytest.mark.parametrize("asked, why", [("MF", "runs no invariant machine"), ("MZ", "no mutant of this tree")])
def test_an_only_outside_the_list_is_said_never_dropped_in_silence(tmp_path, monkeypatch, capsys, asked, why):
    runs = _world(monkeypatch, tmp_path, CATCHES)
    assert night.main(["--seed", str(SEED), "--only", f"MA,{asked}"]) == 2
    said = capsys.readouterr().out
    assert f"--only {asked}: not in the list" in said and why in said and "--only MA:" not in said
    assert runs == []


def test_without_a_file_a_fragile_mutant_makes_the_run_red(tmp_path, monkeypatch, capsys):
    _world(monkeypatch, tmp_path, CATCHES, fixed_catches={"MC"})
    assert night.main(["--seed", str(SEED), "--only", "MA,MB"]) == 1
    capsys.readouterr()
    assert night.main(["--seed", str(SEED), "--only", "MA,MC"]) == 0
    assert "0 fragile" in capsys.readouterr().out


def test_a_night_takes_its_share_only(tmp_path, monkeypatch, capsys):
    runs = _world(monkeypatch, tmp_path, CATCHES, fixed_catches={"MC"})
    k = night.part_of("MA")
    night.main(["--seed", str(SEED), "--part", f"{k}/{night.PARTS}", "--json", str(tmp_path / "n.json")])
    measured = {r[0] for r in runs if r[0] != "base"}
    assert "MA" in measured and all(night.part_of(mid) == k for mid in measured)


def test_each_machine_runs_unmutated_on_each_seed_and_the_fixed_tests_once(tmp_path, monkeypatch):
    runs = _world(monkeypatch, tmp_path, CATCHES, fixed_catches={"MC"})
    night.main(["--seed", str(SEED), "--json", str(tmp_path / "n.json")])
    assert sorted((t, s) for c, t, s in runs if c == "base") == sorted(
        [(M, 100), (M, 101), (M, 102), (f"{F}::test_c {F}::test_d", 100)])


def test_an_unmutated_machine_red_on_one_seed_makes_the_night_no_measure(tmp_path, monkeypatch, capsys):
    """A seed on which the unmutated machine fails would catch every mutant: nothing is measured, said."""
    runs = _world(monkeypatch, tmp_path, CATCHES, base_fails=lambda target, seed: target == M and seed == 101)
    assert night.main(["--seed", str(SEED), "--json", str(tmp_path / "n.json")]) == 2
    assert "fails on seed 101" in capsys.readouterr().out and not (tmp_path / "n.json").exists()
    assert {r[0] for r in runs} == {"base"}


def test_a_part_that_collects_no_test_is_no_catch(tmp_path, monkeypatch, capsys):
    _world(monkeypatch, tmp_path, CATCHES)
    monkeypatch.setattr(mc, "_pytest", lambda copy, examples, target, *more, seed=None: types.SimpleNamespace(
        stdout="", returncode=night.NO_TEST))
    assert night.main(["--seed", str(SEED), "--only", "MA"]) == 2
    assert "collects no test" in capsys.readouterr().out


def test_the_list_measures_nothing(tmp_path, monkeypatch, capsys):
    _world(monkeypatch, tmp_path, CATCHES)
    monkeypatch.setattr(mc, "_copy_repo", lambda dest: pytest.fail("copied"))
    monkeypatch.setattr(mc, "_pytest", lambda *a, **k: pytest.fail("ran"))
    assert night.main(["--list"]) == 0
    said = capsys.readouterr().out
    assert "5 mutants run an invariant machine: 3 alone" in said and f"night {night.part_of('MA')}/7" in said


@pytest.mark.parametrize("n", ["0", "-1", "x"])
def test_no_seed_is_refused(n, capsys):
    with pytest.raises(SystemExit) as exc:
        night.main(["--seeds", n, "--list"])
    assert exc.value.code == 2 and "a number of seeds" in capsys.readouterr().err


# ── the workflow (pushed by Jonathan: absent from a branch the App pushes, these skip) ─────────

def _workflow() -> dict:
    if not NIGHT_YML.exists():
        pytest.skip("mutants-night.yml: pushed by Jonathan (MUT7), not here")
    doc = yaml.safe_load(NIGHT_YML.read_text(encoding="utf-8"))
    doc["on"] = doc.get("on", doc.pop(True, None))
    return doc


def test_the_night_runs_tonights_share_at_the_gates_budget_every_night():
    doc = _workflow()
    (cron,) = [c["cron"] for c in doc["on"]["schedule"]]
    assert cron.split()[2:] == ["*", "*", "*"]                         # every day
    job = doc["jobs"]["night"]
    assert isinstance(job["timeout-minutes"], int) and 0 < job["timeout-minutes"] <= 180
    (step,) = [s for s in job["steps"] if "scripts/mutation_night.py" in (s.get("run") or "")]
    run = " ".join(step["run"].split())
    for part in ('--part "$PART"', '--seeds "$SEEDS"', "--examples 500", "--json night.json",
                 '--output "$GITHUB_OUTPUT"'):
        assert part in run, part
    assert step["env"]["PART"] == "${{ inputs.part || 'auto' }}" and step["env"]["SEEDS"] == "${{ inputs.seeds || '3' }}"
    assert job["outputs"]["fragile"] == "${{ steps.night.outputs.fragile }}" and step["id"] == "night"


def test_the_night_is_announced_when_red():
    _workflow()
    notify = yaml.safe_load((ROOT / ".github" / "workflows" / "notify.yml").read_text(encoding="utf-8"))
    on = notify.get("on", notify.get(True))
    assert "Fragile mutants" in on["workflow_run"]["workflows"]


def _issue_step() -> dict:
    (step,) = _workflow()["jobs"]["issues"]["steps"]
    return step


def _fake_gh(tmp_path: Path, open_issues: list) -> Path:
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (tmp_path / "issues.json").write_text(json.dumps(open_issues))
    gh = bin_ / "gh"
    gh.write_text(f'#!/usr/bin/env bash\nprintf "gh %s\\n" "$*" >> {tmp_path}/log\n'
                  f'if [ "$1 $2" = "issue list" ]; then cat {tmp_path}/issues.json; fi\n')
    gh.chmod(0o755)
    return bin_


def _run_issue_step(tmp_path: Path, fragile: str, open_issues=(), examples="500"):
    bin_ = _fake_gh(tmp_path, list(open_issues))
    env = {"PATH": f"{bin_}:{os.environ.get('PATH', '')}", "HOME": str(tmp_path), "FRAGILE": fragile,
           "EXAMPLES": examples, "RUN_URL": "https://example.invalid/run/1", "SHA": "abc123",
           "GH_TOKEN": "x", "GH_REPO": "owner/repo"}
    res = subprocess.run(["bash", "-e", "-c", _issue_step()["run"]], env=env, capture_output=True, text=True,
                         timeout=60, cwd=tmp_path)
    log = tmp_path / "log"
    return res, (log.read_text() if log.exists() else "")


def test_a_fragile_mutant_opens_its_issue_with_its_seeds_and_replay_and_the_run_is_red(tmp_path):
    res, log = _run_issue_step(tmp_path, "M21:1/3:89917386,89917388")
    assert res.returncode == 1 and "a new issue" in res.stdout, res
    assert "gh issue create --title Mutation : M21 échappe à une graine de la machine des invariants" in log
    for s in ("89917386", "89917388"):
        assert f"python scripts/mutation_check.py --only M21 --seed {s} --examples 500 --rounds 1" in log
    assert "https://example.invalid/run/1" in log and "TESTS_ALSO" in log and "--label" not in log


def test_a_fragile_mutant_whose_issue_is_open_comments_it_and_the_run_stays_green(tmp_path):
    title = "Mutation : M09 échappe à une graine de la machine des invariants"
    res, log = _run_issue_step(tmp_path, "M09:0/3:5,6,7", [{"number": 41, "title": title}])
    assert res.returncode == 0, res
    assert "gh issue comment 41 --body" in log and "issue create" not in log


@pytest.mark.parametrize("fragile, examples", [
    ("M21:1/3:5; rm -rf /", "500"), ("M21:1/3:", "500"), ("$(id):1/3:5", "500"), ("M21:1/3:5", "500 x"),
    ("M21:1/3:5\nM09:1/3:6", "500"),
])
def test_what_the_night_said_out_of_its_form_writes_nothing(tmp_path, fragile, examples):
    res, log = _run_issue_step(tmp_path, fragile, examples=examples)
    assert res.returncode == 1 and "not of its form" in res.stdout and log == "", res
