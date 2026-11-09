"""SEED1 (#655): the run's Hypothesis seed — drawn at night and at the release gate, given to each
round by scripts/mutation_check.py, none on a pull request or a push (Jonathan, 09/11).

The policy (tests/unit/hypothesis_seed.py) on environments of the test's own; then measured, not
read: this file's own probe — a property test and an invariant machine that write what they drew —
run in a pytest of its own under Hypothesis's `ci` profile (CI=true), as GitHub runs it. A push and a
pull request draw what they drew before SEED1, the same run after run; the night two different sets;
a seed given the same set each time, another seed another set.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, run_state_machine_as_test

from . import hypothesis_seed as hs

ROOT = Path(__file__).resolve().parents[2]
PROBE = "EREGION_SEED1_PROBE"      # where the probe writes what it drew (only in the probe's run)


def _gh(event: str, **more) -> dict:
    return {"CI": "true", "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": event, **more}


@pytest.mark.parametrize("event", ["pull_request", "push", "merge_group"])
def test_a_pull_request_and_a_push_keep_the_profile_derandomized(event):
    assert hs.wanted(_gh(event)) is None
    assert hs.resolve(_gh(event)) == (None, False)


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch"])
def test_the_night_and_a_run_by_hand_draw_a_seed(event):
    assert hs.wanted(_gh(event)) == hs.DRAW
    first, drew = hs.resolve(_gh(event))
    assert drew and isinstance(first, int) and 0 <= first < hs.BOUND
    # Two nights, two seeds (one chance in a billion to meet).
    assert {hs.resolve(_gh(event))[0] for _ in range(5)} | {first} != {first}


def test_a_seed_given_wins_over_the_event_and_is_a_replay():
    assert hs.resolve(_gh("schedule", **{hs.VAR: "570502938"})) == (570502938, False)
    assert hs.resolve(_gh("push", **{hs.VAR: " 7 "})) == (7, False)
    assert hs.wanted(_gh("push", **{hs.VAR: "draw"})) == hs.DRAW
    assert hs.wanted({hs.VAR: "DRAW"}) == hs.DRAW
    # Asked in words: Hypothesis's own way, even at night (in CI, derandomized).
    assert hs.resolve(_gh("schedule", **{hs.VAR: "profile"})) == (None, False)


@pytest.mark.parametrize("value", ["seven", "-1", "1.5", "12 13"])
def test_a_seed_that_reads_as_none_is_an_error_never_nothing(value):
    """A typo must not derandomize the night without a word."""
    with pytest.raises(ValueError, match=hs.VAR):
        hs.wanted({hs.VAR: value})


def test_outside_github_hypothesis_keeps_its_own_way():
    assert hs.wanted({}) is None
    assert hs.wanted({"CI": "true", "GITHUB_EVENT_NAME": "schedule"}) is None     # not on GitHub


def test_each_xdist_worker_takes_the_same_seed_from_the_run_id():
    uid = "3f2c9a0e5b7d4c1a9e8f7a6b5c4d3e2f"
    assert hs.drawn(uid) == hs.drawn(uid) == int(uid, 16) % hs.BOUND
    assert hs.drawn("not-hex") == hs.drawn("not-hex")


def test_the_harness_and_the_conftest_name_one_variable():
    spec = importlib.util.spec_from_file_location("mutation_check_seed1", ROOT / "scripts" / "mutation_check.py")
    mc = importlib.util.module_from_spec(spec)
    sys.modules["mutation_check_seed1"] = mc
    spec.loader.exec_module(mc)
    assert mc.SEED_VAR == hs.VAR and mc.SEED_BOUND == hs.BOUND


def test_the_summary_is_written_when_there_is_one(tmp_path):
    summary = tmp_path / "summary.md"
    hs.write_summary(41, {"GITHUB_STEP_SUMMARY": str(summary)})
    assert "Hypothesis seed 41" in summary.read_text() and f"{hs.VAR}=41" in summary.read_text()
    hs.write_summary(41, {})                                   # none: nothing, no error
    hs.write_summary(41, {"GITHUB_STEP_SUMMARY": str(tmp_path / "no" / "such")})   # unwritable: no error


# ── The probe: what a property test and a machine draw, written where the outer test says ───────

_DRAWS: dict[str, list] = {"given": [], "machine": []}


def _write_probe() -> None:
    path = os.environ.get(PROBE)
    if path:
        Path(path).write_text(json.dumps(_DRAWS), encoding="utf-8")


@settings(max_examples=8, database=None)
@given(st.integers(0, 10**12))
def test_probe_a_property(n):
    if os.environ.get(PROBE):
        _DRAWS["given"].append(n)
        _write_probe()


# A probe, no invariant machine of the suite: scripts/mutation_check.py (MACHINE) takes a class
# written on RuleBasedStateMachine by its name for one, and the release gate's shards leave those
# to its invariants job.
_Probed = RuleBasedStateMachine


class _ProbeMachine(_Probed):
    @rule(n=st.integers(0, 10**12))
    def draw(self, n):
        _DRAWS["machine"].append(n)


def test_probe_a_machine():
    if not os.environ.get(PROBE):
        return
    run_state_machine_as_test(_ProbeMachine, settings=settings(max_examples=4, stateful_step_count=3,
                                                               database=None, deadline=None))
    _write_probe()


FAIL = "EREGION_SEED1_PROBE_FAIL"   # the failing probes fail only when it is set


@settings(max_examples=3, database=None)
@given(st.integers())
def test_failing_probe_property(n):
    assert not os.environ.get(FAIL), "a property test failing on purpose (SEED1's probe)"


def test_failing_probe_plain():
    assert not os.environ.get(FAIL), "a plain test failing on purpose (SEED1's probe)"


@settings(max_examples=5, database=None)
@given(st.integers(0, 10**12))
def test_xdist_probe_draws(n):
    """Under `--dist each`, every worker runs it: each writes the seed it holds and what it drew."""
    path = os.environ.get(PROBE)
    if path:
        out = Path(f"{path}.{os.environ.get('PYTEST_XDIST_WORKER', 'none')}")
        seen = (json.loads(out.read_text(encoding="utf-8")) if out.exists()
                else {"seed": test_xdist_probe_draws._hypothesis_internal_use_seed, "draws": []})
        seen["draws"].append(n)
        out.write_text(json.dumps(seen), encoding="utf-8")


def _run_probe(tmp_path: Path, env: dict, select: str, *more: str) -> tuple[subprocess.CompletedProcess, Path]:
    """Probes of this file in a pytest of its own, as GitHub runs it — the outer run's GitHub, pytest
    and seed variables left out: (the run, the file its probes write)."""
    out = tmp_path / f"draws-{len(list(tmp_path.iterdir()))}.json"
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("GITHUB_", "PYTEST_", "HYPOTHESIS")) and k not in ("CI", hs.VAR, FAIL)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", f"{Path(__file__).relative_to(ROOT)}", "-k", select, "-q",
         "-p", "no:cacheprovider", *(more or ("-p", "no:xdist"))],
        cwd=ROOT, env={**base, PROBE: str(out), **env}, capture_output=True, text=True, timeout=300)
    return proc, out


def _probe(tmp_path: Path, env: dict) -> tuple[dict, str]:
    """The drawing probes: (what they drew, the run's output)."""
    proc, out = _run_probe(tmp_path, env, "probe_a_")
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8")), proc.stdout


def test_measured_a_push_replays_its_sequences_the_night_and_a_seed_do_not(tmp_path):
    """Under the `ci` profile, as GitHub runs it. A push draws what a pull request draws, the same
    twice, and says no seed: derandomized as before. Two nights draw two different sets, each its
    seed said. A seed given draws the same set twice (the replay), another seed another set — the
    machines as the property tests: the seed reaches both."""
    push1, said_push = _probe(tmp_path, _gh("push"))
    push2, _ = _probe(tmp_path, _gh("push"))
    pr, _ = _probe(tmp_path, _gh("pull_request"))
    assert push1 == push2 == pr and push1["given"] and push1["machine"]
    assert "Hypothesis seed" not in said_push

    night1, said1 = _probe(tmp_path, _gh("schedule"))
    night2, said2 = _probe(tmp_path, _gh("schedule"))
    assert night1["given"] != night2["given"] and night1["machine"] != night2["machine"]
    assert night1 != push1
    seed1 = int(said1.split("Hypothesis seed ", 1)[1].split()[0])
    assert f"{hs.VAR}={seed1}" in said1 and said1 != said2

    replay, said_replay = _probe(tmp_path, _gh("push", **{hs.VAR: str(seed1)}))
    assert replay == night1, "a night's seed, given, replays the night's sequences"
    assert f"Hypothesis seed {seed1}" in said_replay
    other, _ = _probe(tmp_path, _gh("push", **{hs.VAR: str(seed1 + 1)}))
    assert other["given"] != night1["given"] and other["machine"] != night1["machine"]


def test_measured_the_drawn_seed_reaches_the_step_summary_once(tmp_path):
    summary = tmp_path / "summary.md"
    _, said = _probe(tmp_path, _gh("schedule", GITHUB_STEP_SUMMARY=str(summary)))
    seed = int(said.split("Hypothesis seed ", 1)[1].split()[0])
    assert summary.read_text().count(f"Hypothesis seed {seed} ") == 1
    given_summary = tmp_path / "given.md"
    _probe(tmp_path, _gh("schedule", GITHUB_STEP_SUMMARY=str(given_summary), **{hs.VAR: "5"}))
    assert not given_summary.exists(), "a seed given (a round of the harness) writes no summary"


def test_measured_a_failing_property_test_says_its_seed_under_its_failure(tmp_path):
    """Under a failing property test, its section: the seed and how to replay it — under xdist the
    only place the log says it (the controller does not load this conftest). Never under a plain
    test's failure; never without a seed (a push)."""
    proc, _ = _run_probe(tmp_path, _gh("push", **{hs.VAR: "5", FAIL: "1"}), "failing_probe")
    assert proc.returncode == 1, proc.stdout[-3000:]
    prop, plain = proc.stdout.split(" test_failing_probe_plain ", 1)
    assert "test_failing_probe_property" in prop and "Hypothesis seed (SEED1)" in prop
    assert "Hypothesis seed 5 for every property test" in prop and f"{hs.VAR}=5" in prop
    assert "Hypothesis seed (SEED1)" not in plain.split("short test summary")[0]
    pushed, _ = _run_probe(tmp_path, _gh("push", **{FAIL: "1"}), "failing_probe")
    assert pushed.returncode == 1 and "Hypothesis seed" not in pushed.stdout


def test_what_draws_through_hypothesis_says_its_seed_and_nothing_else():
    from types import SimpleNamespace as Item
    from . import test_invariants
    assert hs.runs_hypothesis(Item(obj=test_probe_a_property))
    assert hs.runs_hypothesis(Item(obj=test_probe_a_machine))          # it runs a machine
    assert hs.runs_hypothesis(Item(obj=test_invariants.test_isolation_invariants))
    assert not hs.runs_hypothesis(Item(obj=test_failing_probe_plain))  # beside a machine, draws nothing
    assert not hs.runs_hypothesis(Item(obj=None))


def test_a_test_seeded_by_its_own_hand_keeps_its_seed(monkeypatch):
    """`@seed` written on a test is its author's replay: the run's seed never overwrites it."""
    from hypothesis import seed as own_seed
    monkeypatch.setattr(RuleBasedStateMachine, "_hypothesis_internal_use_seed",
                        getattr(RuleBasedStateMachine, "_hypothesis_internal_use_seed", None), raising=False)

    @own_seed(123)
    @given(st.integers())
    def kept(n):
        pass

    @given(st.integers())
    def seeded(n):
        pass

    assert hs.apply(7, [kept, seeded, None, lambda: None]) == 1
    assert kept._hypothesis_internal_use_seed == 123 and seeded._hypothesis_internal_use_seed == 7
    assert RuleBasedStateMachine._hypothesis_internal_use_seed == 7


def test_measured_every_xdist_worker_draws_on_the_seed_the_run_says(tmp_path):
    """`-n 2 --dist each`, a night: both workers run the probe, both on the seed the controller drew
    and said, and draw the same values."""
    proc, out = _run_probe(tmp_path, _gh("schedule"), "xdist_probe", "-n", "2", "--dist", "each")
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-2000:]
    said = int(proc.stdout.split("Hypothesis seed ", 1)[1].split()[0])
    gw0, gw1 = (json.loads(Path(f"{out}.{w}").read_text(encoding="utf-8")) for w in ("gw0", "gw1"))
    assert gw0["seed"] == gw1["seed"] == said
    assert gw0["draws"] == gw1["draws"] and gw0["draws"]
