"""SEED1 (#655): one seed for every Hypothesis test of a run — drawn anew where the run must look
somewhere new, fixed where it must be stable or replayed — and said, so that a failure replays by it.

In CI, Hypothesis loads its own `ci` profile (the variable `CI`, set by GitHub Actions), which sets
`derandomize=True`: each test draws from a seed computed on its own source (`function_digest`), the
invariant machines on their class's. Measured (09/11, Hypothesis 6.170.10): under it, the same
sequences run after run, and `--hypothesis-seed=N` changes nothing — the derandomization comes first
(`get_random_for_wrapped_test`). What does come first is a test's own seed (`@seed`, the attribute
`_hypothesis_internal_use_seed`): that is what this module sets, on each Hypothesis test the run
collected and on `RuleBasedStateMachine` itself (every machine inherits it; `run_state_machine_as_test`
reads it from the machine's class). It leaves each test's settings as they are — the machines'
database (GLORFINDEL_INVARIANT_DB) is still read and written; `--hypothesis-seed` would have turned
it off.

What a run asks, by EREGION_HYPOTHESIS_SEED:
- a number: that seed (a replay; scripts/mutation_check.py gives each round its own);
- `draw`: a seed drawn for this run;
- `profile`: Hypothesis's own way, even on a run that would draw (in CI, derandomized);
- nothing: drawn on GitHub for a scheduled or dispatched run (the night's invariants, the release
  gate) — a pull request and a push keep the `ci` profile, derandomized, stable (Jonathan, 09/11);
  anywhere else, Hypothesis's own way (in CI derandomized, on a workstation at random).
A drawn seed goes into the environment, so that a process the run starts — an xdist worker — draws
the same; an xdist worker whose controller did not load this conftest takes it from the run's id
(`testrunuid`, the same for each worker). It is said at the end of the run, on each failing
property test, and in the step's summary on GitHub (by the process that drew it).
"""
from __future__ import annotations

import os
import re
import secrets

VAR = "EREGION_HYPOTHESIS_SEED"
DRAW = "draw"
PROFILE = "profile"     # asked in words: Hypothesis's own way, even where the run would draw
# The GitHub events whose runs draw a seed when none is asked: the night's, a run by hand. A pull
# request and a push stay derandomized.
DRAWN_ON = ("schedule", "workflow_dispatch")
BOUND = 10**9           # a seed drawn: below it, short enough to read and type
NUMBER = re.compile(r"\d{1,19}")


def wanted(env) -> int | str | None:
    """What the run asks: a seed (int), DRAW, or None — Hypothesis's own way. A value that is
    neither a number nor `draw` is an error, never read as nothing: a typo must not derandomize."""
    raw = (env.get(VAR) or "").strip()
    if raw:
        if raw.lower() == DRAW:
            return DRAW
        if raw.lower() == PROFILE:
            return None
        if NUMBER.fullmatch(raw):
            return int(raw)
        raise ValueError(f"{VAR}={raw!r}: a seed (a whole number), {DRAW!r} or {PROFILE!r}")
    if env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_EVENT_NAME") in DRAWN_ON:
        return DRAW
    return None


def drawn(uid: str | None = None) -> int:
    """A seed for this run: from the xdist run's id when one is given (each worker the same), else
    at random."""
    if uid:
        try:
            return int(uid, 16) % BOUND
        except ValueError:
            return int.from_bytes(uid.encode(), "big") % BOUND
    return secrets.randbelow(BOUND)


def resolve(env, uid: str | None = None) -> tuple[int | None, bool]:
    """(the seed of this run or None, whether this process drew it)."""
    asked = wanted(env)
    if asked == DRAW:
        return drawn(uid), True
    return asked, False


def is_property_test(fn) -> bool:
    """A test function Hypothesis runs (@given): it carries `is_hypothesis_test`."""
    return bool(getattr(fn, "is_hypothesis_test", False))


def apply(seed: int, functions) -> int:
    """The seed, set on each Hypothesis test of `functions` that has none of its own, and on every
    invariant machine: the number of tests seeded."""
    from hypothesis.stateful import RuleBasedStateMachine
    RuleBasedStateMachine._hypothesis_internal_use_seed = seed
    seeded = 0
    for fn in functions:
        fn = getattr(fn, "__func__", fn)
        if is_property_test(fn) and getattr(fn, "_hypothesis_internal_use_seed", None) is None:
            fn._hypothesis_internal_use_seed = seed
            seeded += 1
    return seeded


def runs_hypothesis(item) -> bool:
    """A test of the run that draws through Hypothesis: a property test, or a test of a module
    that defines an invariant machine."""
    if is_property_test(getattr(getattr(item, "obj", None), "__func__", getattr(item, "obj", None))):
        return True
    module = getattr(item, "module", None)
    if module is None:
        return False
    from hypothesis.stateful import RuleBasedStateMachine
    return any(isinstance(v, type) and issubclass(v, RuleBasedStateMachine) and v is not RuleBasedStateMachine
               for v in vars(module).values())


def said(seed: int) -> str:
    """The line a run says: its seed, and how to replay it."""
    return (f"Hypothesis seed {seed} for every property test and invariant machine of this run (SEED1) — "
            f"replay: {VAR}={seed} python -m pytest <the same tests>")


def write_summary(seed: int, env=os.environ) -> None:
    """The seed in the GitHub step's summary, when there is one; never a reason to fail."""
    path = env.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as out:
            out.write(f"\n**{said(seed)}**\n")
    except OSError:
        pass
