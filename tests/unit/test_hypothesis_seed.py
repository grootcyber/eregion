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


def _probe(tmp_path: Path, env: dict) -> tuple[dict, str]:
    """The probe in a pytest of its own, as GitHub runs it: (what it drew, its output)."""
    out = tmp_path / f"draws-{len(list(tmp_path.iterdir()))}.json"
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("GITHUB_", "PYTEST_", "HYPOTHESIS")) and k not in ("CI", hs.VAR)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", f"{Path(__file__).relative_to(ROOT)}", "-k", "probe", "-q",
         "-p", "no:cacheprovider", "-p", "no:xdist"],
        cwd=ROOT, env={**base, PROBE: str(out), **env}, capture_output=True, text=True, timeout=300)
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
