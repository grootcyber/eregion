"""CI13 (#986): a night of the invariant machines cut by its step's bound says where it ran.

On 20/11 the night's Azure step was cut at its 125 minutes with nothing in its log after
`collected 1 item`: no counterexample, no seed, no statistics. The seed is now said when the run
begins (tests/unit/conftest.py, SEED1); this watchdog says, before the bound, what the machine is
doing — so that a sequence that never ends, a shrinking that outlasts the step, and a runner slow
that day no longer look the same.

Armed only for a test that runs an invariant machine (its code calls `run_state_machine_as_test`),
and only for a night: a seed drawn for the run, or more sequences than a push's budget
(GLORFINDEL_INVARIANT_EXAMPLES above NIGHT_EXAMPLES). A pull request and a push (200 and 500,
derandomized) never arm it: the rest of the suite runs as before.

At WATCHDOG minutes after the run began (`GLORFINDEL_INVARIANT_WATCHDOG`, a decimal accepted; by
default the machine's file's INVARIANT_WATCHDOG_MINUTES, else DEFAULT_MINUTES — under the step's
bound, tests/unit/test_invariant_watchdog.py reads invariants.yml) it writes, on the stderr the
run began with (never captured by pytest):
- the run's seed and how to replay it (EREGION_HYPOTHESIS_SEED=<seed>), or that none was drawn;
- how many sequences the machine began, how long the current one has run, the longest before it;
- the stack of every thread, read by Python under the GIL (`sys._current_frames`): safe while the
  machine's threads run — faulthandler reads their frames without the GIL, and a process can die
  of it (CI12, `docs/operations.md`).
faulthandler stays the backstop: armed LAG seconds later, and cancelled once the words are
written, it dumps the stacks only when Python could not (the GIL never released). A run that set
pytest's own `faulthandler_timeout` (the release gate) keeps its own: the backstop is not armed.
The run is not stopped: a runner slow that day may still end before its bound.

When the test ends, armed, a line says how many sequences ran and the longest — the next night's
log tells a slow runner from a sequence that does not end.
"""
from __future__ import annotations

import faulthandler
import os
import sys
import threading
import time
import traceback

VAR = "GLORFINDEL_INVARIANT_WATCHDOG"         # minutes after the run began
EXAMPLES = "GLORFINDEL_INVARIANT_EXAMPLES"
MODULE_DEFAULT = "INVARIANT_WATCHDOG_MINUTES"  # a machine's file sets its own (its step's bound)
DEFAULT_MINUTES = 115.0     # under the Azure step's 125 min (invariants.yml)
NIGHT_EXAMPLES = 500        # a push's budget (ci.yml): above it, a night or a run by hand
LAG = 60.0                  # seconds between the words and faulthandler's backstop
SEED_VAR = "EREGION_HYPOTHESIS_SEED"
STACK_LIMIT = 60            # a thread's innermost frames: the rule, the product, Hypothesis's engine

STARTED = time.monotonic()  # loaded by the conftest, as the run begins


def at_night(env, drew: bool) -> bool:
    """A night, or a run by hand like it: a seed drawn for the run, or more sequences than a
    push's budget."""
    if drew:
        return True
    try:
        return int((env.get(EXAMPLES) or "0").strip()) > NIGHT_EXAMPLES
    except ValueError:
        return False


def minutes(env, default: float) -> float:
    """The minutes after the run began when the watchdog speaks: the variable's, else the
    default. A value that is not a positive number is an error, never read as nothing."""
    raw = (env.get(VAR) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if not value > 0:
        raise ValueError(f"{VAR}={raw!r}: minutes after the run began, a positive number")
    return value


def backstop_for(config) -> bool:
    """faulthandler's backstop, unless the run asked pytest's own (`faulthandler_timeout`): one
    timer per process, which the watchdog's would replace, then cancel."""
    try:
        return not float(config.getini("faulthandler_timeout") or 0) > 0
    except (TypeError, ValueError):
        return True


def runs_machine(item) -> bool:
    """A test that runs an invariant machine: its code calls `run_state_machine_as_test`."""
    fn = getattr(item, "obj", None)
    fn = getattr(fn, "__func__", fn)
    code = getattr(fn, "__code__", None)
    return code is not None and "run_state_machine_as_test" in code.co_names


def stacks(skip: int | None = None) -> str:
    """Every thread's stack (its STACK_LIMIT innermost frames), read under the GIL; `skip`: the
    watchdog's own thread."""
    names = {t.ident: t.name for t in threading.enumerate()}
    main = threading.main_thread().ident
    out = []
    for ident, frame in sys._current_frames().items():
        if ident == skip:
            continue
        mark = " (the main thread: the sequence)" if ident == main else ""
        out.append(f"Thread {names.get(ident, '?')} ({ident}){mark}, most recent call last:\n")
        out.extend(traceback.format_stack(frame, limit=STACK_LIMIT))
    return "".join(out)


class Watch:
    """The watchdog of one machine's test: `arm()` before it, `disarm()` after."""

    def __init__(self, fd: int, seed, at_minutes: float, *, started: float = STARTED,
                 backstop: bool = True, name: str = ""):
        self.fd = fd
        self.seed = seed
        self.at_minutes = at_minutes
        self.started = started
        self.backstop = backstop
        self.name = name
        self.begun = 0
        self.current = None          # monotonic time the current sequence began
        self.longest = 0.0
        self.longest_n = 0
        self.timer = None
        self.backstop_armed = False
        self._init = None

    # The sequences: each machine's __init__ is one (generation, replay, shrinking alike).
    def began(self) -> None:
        now = time.monotonic()
        self._close(now)
        self.begun += 1
        self.current = now

    def _close(self, now: float) -> None:
        if self.current is not None and now - self.current > self.longest:
            self.longest, self.longest_n = now - self.current, self.begun

    def _write(self, text: str) -> None:
        try:
            os.write(self.fd, text.encode("utf-8", "replace"))
        except OSError:
            pass

    def replay(self) -> str:
        if self.seed is None:
            return ("no seed set for this run (Hypothesis's own way): its database, when kept, "
                    "replays what it found")
        return f"seed {self.seed} — replay: {SEED_VAR}={self.seed} python -m pytest <the same tests>"

    def speak(self) -> None:
        """The words before the bound: the seed, the sequences, every thread's stack."""
        now = time.monotonic()
        current = f"the current one for {now - self.current:.1f} s" if self.current else "none yet"
        longest = (f"the longest before it {self.longest:.1f} s (sequence {self.longest_n})" if self.longest_n
                   else "none ended before it")
        self._write(
            f"\n=== CI13 watchdog: {(now - self.started) / 60:.1f} min since the run began "
            f"({VAR}={self.at_minutes:g}), {self.name} still running ===\n"
            f"{self.replay()}\n"
            f"{self.begun} sequences begun, {current}; {longest}\n"
            f"{stacks(threading.get_ident())}"
            f"=== CI13 watchdog: the run goes on until its step's bound ===\n")
        if self.backstop_armed:
            faulthandler.cancel_dump_traceback_later()
            self.backstop_armed = False

    def delay(self, now: float) -> float:
        """The seconds from `now` to the words: `at_minutes` after the run began (a second at least)."""
        return max(1.0, self.started + self.at_minutes * 60 - now)

    def arm(self) -> None:
        from hypothesis.stateful import RuleBasedStateMachine
        delay = self.delay(time.monotonic())
        self._init = RuleBasedStateMachine.__dict__.get("__init__")
        original = RuleBasedStateMachine.__init__

        def counted(machine, *args, **kwargs):
            self.began()
            original(machine, *args, **kwargs)
        RuleBasedStateMachine.__init__ = counted
        self.timer = threading.Timer(delay, self.speak)
        self.timer.daemon = True
        self.timer.name = "ci13-watchdog"
        self.timer.start()
        if self.backstop:
            faulthandler.dump_traceback_later(delay + LAG, repeat=False, file=self.fd, exit=False)
            self.backstop_armed = True

    def disarm(self) -> None:
        from hypothesis.stateful import RuleBasedStateMachine
        if self.timer is not None:
            self.timer.cancel()
        if self.backstop_armed:
            faulthandler.cancel_dump_traceback_later()
            self.backstop_armed = False
        if self._init is not None:
            RuleBasedStateMachine.__init__ = self._init
        elif "__init__" in RuleBasedStateMachine.__dict__:
            del RuleBasedStateMachine.__init__
        self._close(time.monotonic())
        self._write(f"\nCI13: {self.name}: {self.begun} sequences in {(time.monotonic() - self.started) / 60:.1f} "
                    f"min since the run began, the longest {self.longest:.1f} s (sequence {self.longest_n})\n")
