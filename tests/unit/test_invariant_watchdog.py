"""CI13 (#986): a night of the invariant machines cut by its step's bound says its seed and where it
runs — the night of 20/11 was cut at 125 minutes after `collected 1 item`, nothing else.

The rule (tests/unit/invariant_watchdog.py) on environments of the test's own; the defaults read
against the bounds invariants.yml gives each machine's step; then measured, not read: this file's
own probes — a machine whose sequence never ends, a machine that ends — run in a pytest of its own,
the never-ending one killed (SIGKILL, as a bound cuts a step) once its log says what it must.
"""
from __future__ import annotations

import ast
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import yaml
from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, run_state_machine_as_test

from . import hypothesis_seed as hs
from . import invariant_watchdog as wd

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "invariants.yml"
PROBE = "EREGION_CI13_PROBE"       # the probes run only in the probe's pytest
HANG = "EREGION_CI13_HANG"         # the probe machine's sequence never ends while it is set
REACHED = "EREGION_CI13_REACHED"   # the probe machine's rule touches this file once it runs
SPOKE = "=== CI13 watchdog: the run goes on until its step's bound ==="


# ── The rule ─────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("examples", ["", "60", "200", "500", "not a number"])
def test_a_pull_request_and_a_push_never_arm_it(examples):
    """Their budgets (ci.yml: 200, 500; the local default 60), no seed drawn: the suite as before."""
    assert not wd.at_night({wd.EXAMPLES: examples} if examples else {}, drew=False)


@pytest.mark.parametrize("env, drew", [({wd.EXAMPLES: "10000"}, False), ({wd.EXAMPLES: "501"}, False),
                                       ({}, True), ({wd.EXAMPLES: "200"}, True)])
def test_a_night_arms_it_by_its_drawn_seed_or_its_budget(env, drew):
    assert wd.at_night(env, drew)


def test_its_minutes_come_from_a_variable_else_the_default():
    assert wd.minutes({}, 115) == 115
    assert wd.minutes({wd.VAR: " 90 "}, 115) == 90
    assert wd.minutes({wd.VAR: "0.05"}, 115) == 0.05
    for bad in ("soon", "0", "-3", "nan"):
        with pytest.raises(ValueError, match=wd.VAR):
            wd.minutes({wd.VAR: bad}, 115)


def _bounds() -> dict[str, int]:
    """Each machine's file, by the step of invariants.yml that runs it: its timeout-minutes."""
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["invariants"]["steps"]
    out = {}
    for step in steps:
        run = step.get("run", "")
        found = re.search(r"pytest (tests/unit/test_invariants\w*\.py)", run)
        if found:
            out[found.group(1)] = int(step["timeout-minutes"])
    return out


def _file_default(path: str) -> float:
    """A machine's file's INVARIANT_WATCHDOG_MINUTES, read from its source (no import: the
    machines are Glorfindel's), else the watchdog's default."""
    for node in ast.parse((ROOT / path).read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and getattr(node.targets[0], "id", None) == wd.MODULE_DEFAULT):
            return float(ast.literal_eval(node.value))
    return wd.DEFAULT_MINUTES


def test_each_machine_speaks_before_its_step_s_bound_backstop_included():
    """The words at the file's default, faulthandler's backstop LAG seconds later: both before the
    bound of the step that runs the file (Azure 125 min, AWS 45 on 20/11), with a minute left."""
    bounds = _bounds()
    assert set(bounds) == {"tests/unit/test_invariants.py", "tests/unit/test_invariants_aws.py"}, bounds
    for path, bound in bounds.items():
        at = _file_default(path)
        assert at + wd.LAG / 60 <= bound - 1, f"{path}: the watchdog at {at} min, its step cut at {bound}"
        assert at >= bound / 2, f"{path}: at {at} min, a healthy night of {bound} min is dumped midway"
    assert wd.DEFAULT_MINUTES + wd.LAG / 60 < 125


def test_it_speaks_its_minutes_after_the_run_began_not_after_its_test_did():
    """The bound counts from the step's start: the minutes too, from the run's (the conftest's
    import), whatever ran before the machine's test."""
    watch = wd.Watch(1, None, 2, started=100.0)
    assert watch.delay(130.0) == 90.0
    assert watch.delay(219.5) == 1.0          # past its time already: at once, never never


class _Config:
    def __init__(self, value):
        self.value = value

    def getini(self, name):
        assert name == "faulthandler_timeout"
        return self.value


@pytest.mark.parametrize("value, backstop", [(0, True), (0.0, True), ("", True), (None, True),
                                             (2400, False), ("480", False)])
def test_a_run_that_asked_pytest_s_faulthandler_keeps_it(value, backstop):
    """The release gate's `-o faulthandler_timeout=2400`: one faulthandler timer per process, and
    the watchdog's would replace pytest's, then cancel it."""
    assert wd.backstop_for(_Config(value)) is backstop


def test_what_runs_a_machine_arms_it_and_nothing_else():
    from types import SimpleNamespace as Item
    assert wd.runs_machine(Item(obj=test_probe_never_ends))
    assert not wd.runs_machine(Item(obj=test_probe_plain_after))
    assert not wd.runs_machine(Item(obj=None))


# ── In this process: the sequences counted, the words, everything put back ─────────────────────

_Probed = RuleBasedStateMachine     # a probe, no invariant machine of the suite (SEED1's MACHINE)


class _Counted(_Probed):
    @rule(n=st.integers(0, 3))
    def step(self, n):
        pass


def _read(fd: int) -> str:
    os.set_blocking(fd, False)
    chunks = []
    while True:
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode()


def test_armed_it_counts_the_sequences_speaks_and_puts_everything_back():
    before = RuleBasedStateMachine.__dict__["__init__"]
    r, w = os.pipe()
    try:
        watch = wd.Watch(w, 4242, 60, started=time.monotonic(), backstop=False, name="probe")
        watch.arm()
        assert RuleBasedStateMachine.__init__ is not before
        run_state_machine_as_test(_Counted, settings=settings(max_examples=7, stateful_step_count=2,
                                                             database=None, deadline=None))
        speaker = threading.Thread(target=watch.speak, name="ci13-watchdog")   # as its timer does
        speaker.start()
        speaker.join()
        watch.disarm()
        out = _read(r)
    finally:
        RuleBasedStateMachine.__init__ = before
        os.close(r)
        os.close(w)
    assert RuleBasedStateMachine.__dict__["__init__"] is before
    assert watch.begun >= 7
    assert f"{hs.VAR}=4242" in out and SPOKE in out
    assert f"{watch.begun} sequences begun" in out
    assert "(the main thread: the sequence)" in out and "test_armed_it_counts_the_sequences" in out
    assert re.search(rf"CI13: probe: {watch.begun} sequences in [\d.]+ min since the run began, the longest", out)


def test_disarmed_before_its_time_it_never_speaks():
    r, w = os.pipe()
    try:
        watch = wd.Watch(w, None, 0.02, started=time.monotonic(), backstop=True, name="probe")
        watch.arm()
        assert watch.backstop_armed
        watch.disarm()
        assert not watch.backstop_armed
        time.sleep(1.6)                      # past its 1.2 s
        out = _read(r)
    finally:
        os.close(r)
        os.close(w)
    assert SPOKE not in out and "CI13: probe: 0 sequences" in out


# ── The probes, run in a pytest of their own ──────────────────────────────────────────────────────

class _NeverEnds(_Probed):
    @rule()
    def never_ends(self):
        if os.environ.get(REACHED):
            Path(os.environ[REACHED]).touch()
        while os.environ.get(HANG):
            time.sleep(0.05)


def test_probe_never_ends():
    if not os.environ.get(PROBE):
        return
    run_state_machine_as_test(_NeverEnds, settings=settings(max_examples=5, stateful_step_count=2,
                                                            database=None, deadline=None))


def test_probe_plain_after():
    """A plain test after the machine: long enough for a watchdog left armed to speak in it."""
    if os.environ.get(PROBE):
        time.sleep(float(os.environ[PROBE]))


def _run(tmp_path: Path, env: dict, select: str, *, kill_when: str | None, wait: float,
         reached: Path | None = None, after: float = 0.0, more: tuple = ("-p", "no:xdist")) -> tuple[str, int]:
    """The probes in a pytest of their own, as the night runs it (no xdist unless `more` asks it,
    `-q`, pytest capturing: the watchdog's words must not need `-s`), its log a file. Killed by
    SIGKILL — a step cut by its bound — once its log holds `kill_when`, or `after` seconds once the
    probe's rule wrote `reached`, or after `wait` seconds: (the log, the exit code)."""
    log = tmp_path / f"run-{len(list(tmp_path.iterdir()))}.log"
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("GITHUB_", "PYTEST_", "HYPOTHESIS", "GLORFINDEL_INVARIANT", "EREGION_HYPOTHESIS"))
            and k != "CI"}
    if reached is not None:
        env = {**env, REACHED: str(reached)}
    with log.open("wb") as out:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", str(Path(__file__).relative_to(ROOT)), "-k", select, "-q",
             "-p", "no:cacheprovider", *more],
            cwd=ROOT, env={**base, **env}, stdout=out, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + wait
        seen = None
        while proc.poll() is None and time.monotonic() < deadline:
            if kill_when and kill_when in log.read_text(encoding="utf-8", errors="replace"):
                break
            if reached is not None and seen is None and reached.exists():
                seen = time.monotonic()
            if seen is not None and time.monotonic() - seen >= after:
                break
            time.sleep(0.2)
        if proc.poll() is None:
            proc.send_signal(signal.SIGKILL)
        code = proc.wait(timeout=30)
    return log.read_text(encoding="utf-8", errors="replace"), code


def _cut_night(log: str) -> str:
    """What a night cut by its bound must have said: the seed as the run began, then the
    watchdog's words with that seed, the sequences begun and the main thread's stack down to the
    rule that runs. Its words."""
    begun = re.search(rf"Hypothesis seed (\d+) for every property test.*replay: {hs.VAR}=(\d+) ", log)
    assert begun and begun.group(1) == begun.group(2), log[-3000:]
    seed = begun.group(1)
    assert log.index(begun.group(0)) < log.index("=== CI13 watchdog:"), "the seed is said before the watchdog"
    words = log[log.index("=== CI13 watchdog:"):]
    assert f"seed {seed} — replay: {hs.VAR}={seed} python -m pytest" in words
    assert re.search(r"\b(1 sequence|[2-9]\d* sequences|1\d+ sequences) begun, the current one for [\d.]+ s",
                     words), words[:2000]
    assert "(the main thread: the sequence)" in words
    main = words.split("(the main thread: the sequence)", 1)[1].split("\nThread ", 1)[0]
    assert "in never_ends" in main and "test_invariant_watchdog.py" in main, words[:4000]
    assert SPOKE in words
    return words


@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="a bound cuts a step by SIGKILL here")
def test_measured_a_step_cut_by_its_bound_has_said_its_seed_and_the_sequence_that_runs(tmp_path):
    """The night of 20/11 again, small: a seed drawn, a sequence that never ends, the watchdog at
    3 s, the process killed once it spoke. Its log holds the seed — said as the run began, before
    any test, copied as is — and the watchdog's words: the same seed, the sequences begun, and the
    stack of the main thread down to the rule that runs."""
    log, code = _run(tmp_path, {PROBE: "0", HANG: "1", hs.VAR: "draw", wd.VAR: "0.05"}, "probe_never_ends",
                     kill_when=SPOKE, wait=60)
    assert code == -signal.SIGKILL, log[-3000:]
    _cut_night(log)


@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="a bound cuts a step by SIGKILL here")
def test_measured_under_xdist_a_worker_knows_its_controller_drew_the_seed(tmp_path):
    """`-n 2`, a seed drawn, no budget: the controller draws and says it, each worker gets it as a
    number — and that it was drawn (DRAWN_VAR). The worker running the machine arms the watchdog,
    whose words reach the run's log (a worker's stderr is the controller's) with the same seed."""
    log, code = _run(tmp_path, {PROBE: "0", HANG: "1", hs.VAR: "draw", wd.VAR: "0.1"}, "probe_never_ends",
                     kill_when=SPOKE, wait=90, more=("-n", "2"))
    assert code == -signal.SIGKILL, log[-3000:]
    _cut_night(log)


def test_a_seed_drawn_upstream_is_the_very_seed_given():
    assert hs.drawn_upstream({hs.DRAWN_VAR: "41"}, 41)
    assert hs.drawn_upstream({hs.DRAWN_VAR: " 41 "}, 41)
    assert not hs.drawn_upstream({hs.DRAWN_VAR: "41"}, 42), "another run's draw counts for nothing"
    assert not hs.drawn_upstream({hs.DRAWN_VAR: "41"}, None)
    assert not hs.drawn_upstream({}, 41), "a seed given (a replay, a round of the harness) was not drawn"


@pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="a bound cuts a step by SIGKILL here")
def test_measured_a_push_cut_by_its_bound_says_nothing_more(tmp_path):
    """A push (500 sequences, no seed): the same sequence that never ends, killed 6 s after its rule
    began — twice the watchdog's 3 s — the watchdog never armed, nothing said, as before CI13. The
    rule must have been reached: a run that never got there proves nothing."""
    reached = tmp_path / "reached"
    log, code = _run(tmp_path, {PROBE: "0", HANG: "1", wd.EXAMPLES: "500", wd.VAR: "0.05"},
                     "probe_never_ends", kill_when=None, wait=90, reached=reached, after=6)
    assert reached.exists(), f"the probe's rule was never reached:\n{log[-3000:]}"
    assert code == -signal.SIGKILL, log[-3000:]
    assert "CI13 watchdog" not in log and "CI13: " not in log and "Hypothesis seed" not in log, log[-3000:]


def test_measured_a_machine_that_ends_is_disarmed_and_says_its_longest_sequence(tmp_path):
    """A night by its budget (no seed): the machine ends, then a plain test outlasts the watchdog's
    3 s — the watchdog never speaks there; the machine's line says its sequences and the longest."""
    log, code = _run(tmp_path, {PROBE: "6", wd.EXAMPLES: "1000", wd.VAR: "0.05"},
                     "probe_never_ends or probe_plain_after", kill_when=None, wait=120)
    assert code == 0, log[-3000:]
    assert "=== CI13 watchdog" not in log, log[-3000:]
    assert re.search(r"CI13: \S+::test_probe_never_ends: [1-9]\d* sequences in [\d.]+ min since the run "
                     r"began, the longest [\d.]+ s", log), log[-3000:]
    assert "CI13: " not in log.split("test_probe_never_ends:", 1)[1].split("\n", 1)[1]
