"""HRN1 (#1065): each call of the harness to the model, measured — its latency, its tokens, its cost.

The harness (scripts/llm_smoke.py) calls the model through one function,
`eregion_core.llm_call.completion_with_tool`: the decision (`decide`, its first draw then the
confirming draws of D-1) and the rule proposals (`detection_authoring.author_rule`). `Meter.installed`
puts a measuring wrapper in its place for the length of a run, and takes it out after. The wrapper
passes every argument through unchanged and returns the model's response as it came: what the model
sees does not change, only what the harness notes.

Per call:
- its **latency**: a monotonic clock around the call, what `decide` waits for it (LiteLLM's own
  retries and a refused forced choice included). The confirming draws run in threads, each timed;
- its **tokens**: the `usage` of LiteLLM's response, `prompt_tokens` and `completion_tokens`. No
  usage, or an input of 0 tokens (no real call reads nothing), is said unknown;
- its **cost**: what LiteLLM can price for this model (`litellm.completion_cost`). A model LiteLLM
  cannot price, or tokens unknown, is a cost **unknown** (None) — never 0: a 0 would make a run look
  free, and PRT2's breaker would read it so. A known 0 (a local model, ollama/…) stays 0;
- a call that **fails** (an exception) is counted apart: its latency is kept, it is in neither the
  latency, nor the tokens, nor the cost of the others.

Roles: in a slot (one run of one case: one `decide`), the first decision call is the `decision`, the
others its `draws`; a rule proposal is a `proposal`; a turn of the enquiry's loop (ENQ4, its tool
`enquete`) is an `enquiry` — its latency is the latency of a turn, which recalibrates N and T (Q2). Nothing here is written into the attestation
(requirements/harness.json): `llm_smoke.harness_pass` keeps its fields, the measure goes to the
report and to --json only.

HRN2 (#1079): a run's ceiling (`Budget`), for the model's probe on Imladris — checked before each call,
a call refused never made: over its measured cost, or over its bound of calls, the run stops and says
why. An unknown cost is a possible overrun, never 0 (`Budget`).
"""
from __future__ import annotations

import math
import threading
import time
from contextlib import contextmanager

DECISION, DRAW, PROPOSAL, ENQUIRY = "decision", "draw", "proposal", "enquiry"
_DECISION_TOOL = "security_decision"
_ENQUIRY_TOOL = "enquete"             # glorfindel/enquiry/message.py, OUTIL


def _field(obj, name):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _count(value) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or value < 0:
        return None
    return int(value)


def tokens(response) -> dict:
    """{input_tokens, output_tokens, cache_read_tokens} read from the response's `usage`; None
    where it says nothing. An input of 0 is no usage: both said unknown."""
    usage = _field(response, "usage")
    inp, out = _count(_field(usage, "prompt_tokens")), _count(_field(usage, "completion_tokens"))
    if not inp:
        inp = out = None
    return {"input_tokens": inp, "output_tokens": out,
            "cache_read_tokens": _count(_field(usage, "cache_read_input_tokens"))}


def litellm_cost(litellm, response, model: str) -> float | None:
    """What LiteLLM prices this call, in dollars; None when it cannot (a model it has not mapped,
    a response it cannot read) — an unknown cost, never 0."""
    try:
        cost = litellm.completion_cost(completion_response=response, model=model)
    except Exception:
        return None
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
        return None
    return float(cost)


class OverBudget(Exception):
    """A call the run's ceiling refused (HRN2): never made."""


class Budget:
    """A run's ceiling (HRN2): `max_usd` of measured cost, `max_calls` calls — never a run without a bound.

    Checked before each call (`admit`): the bound of calls reached, or the cost charged so far at the
    ceiling, and the call is refused, the run stopped (`stopped` says why). A call's cost is charged once
    it returns (`settle`): what LiteLLM priced; an unknown cost (a model it cannot price, a failed call) is
    a possible overrun, never 0 — each is charged max_usd / max_calls, so that calls of unknown cost alone
    stop the run at its bound of calls, and fewer when some are priced. The confirming draws of one
    decision run in threads: the ceiling may be passed by what they cost, two calls at most."""

    def __init__(self, max_usd: float, max_calls: int):
        if not (isinstance(max_usd, (int, float)) and math.isfinite(max_usd) and max_usd > 0) or int(max_calls) < 1:
            raise ValueError("a ceiling above 0 $ and a bound of one call at least")
        self.max_usd, self.max_calls = float(max_usd), int(max_calls)
        self.per_unknown = self.max_usd / self.max_calls
        self.calls = self.unknown = 0
        self.known_usd = 0.0
        self.stopped = ""

    def charged(self) -> float:
        return self.known_usd + self.unknown * self.per_unknown

    def admit(self) -> bool:
        if not self.stopped:
            if self.calls >= self.max_calls:
                self.stopped = f"the bound of {self.max_calls} call(s) reached"
            elif self.charged() >= self.max_usd:
                self.stopped = (f"the ceiling of ${self.max_usd:.2f} reached: ${self.known_usd:.4f} measured"
                                + (f", {self.unknown} call(s) of unknown cost counted ${self.per_unknown:.4f} each"
                                   if self.unknown else ""))
        if self.stopped:
            return False
        self.calls += 1
        return True

    def settle(self, cost: float | None) -> None:
        if cost is None:
            self.unknown += 1
        else:
            self.known_usd += cost

    def said(self) -> dict:
        return {"max_usd": self.max_usd, "max_calls": self.max_calls, "calls": self.calls,
                "known_usd": round(self.known_usd, 6), "unknown": self.unknown,
                "charged_usd": round(self.charged(), 6), "stopped": self.stopped}


def run_bound(cases: int, runs: int, draws: int) -> int:
    """The most calls a run of the decision's harness makes: each run of each case one decision, and its
    confirming draws when it isolates or blocks (GLORFINDEL_DECISION_DRAWS in all) — 18 × 3 × 3 = 162."""
    return max(1, cases) * max(1, runs) * max(1, draws)


class Meter:
    """The calls of one run of the harness, on one model. `clock` and `price` are injectable (tests);
    `budget` (HRN2), the run's ceiling: a call it refuses raises OverBudget, never made."""

    def __init__(self, clock=time.monotonic, price=litellm_cost, budget: Budget | None = None):
        self.calls: list[dict] = []
        self._clock, self._price = clock, price
        self._lock = threading.Lock()
        self._slot: dict | None = None
        self._slots = 0
        self.budget = budget

    @property
    def stopped(self) -> str:
        return self.budget.stopped if self.budget else ""

    def _admit(self) -> None:
        if self.budget is None:
            return
        with self._lock:
            admitted = self.budget.admit()
        if not admitted:
            raise OverBudget(self.budget.stopped)

    def _settle(self, cost: float | None) -> None:
        if self.budget is not None:
            with self._lock:
                self.budget.settle(cost)

    @contextmanager
    def slot(self, kind: str):
        """One run of one case (`kind`: its genre): its calls are numbered in it."""
        with self._lock:
            self._slots += 1
            self._slot = {"id": self._slots, "kind": kind, "decisions": 0}
        try:
            yield
        finally:
            with self._lock:
                self._slot = None

    def _role(self, tool_name: str) -> tuple[str, int, str]:
        with self._lock:
            slot = self._slot or {"id": 0, "kind": "", "decisions": 0}
            if tool_name == _ENQUIRY_TOOL:
                role = ENQUIRY
            elif tool_name != _DECISION_TOOL:
                role = PROPOSAL
            else:
                role = DECISION if slot["decisions"] == 0 else DRAW
                slot["decisions"] += 1
            return role, slot["id"], slot["kind"]

    def _note(self, record: dict) -> None:
        with self._lock:
            self.calls.append(record)

    def wrap(self, call):
        """`call` (completion_with_tool), measured: same arguments, same response, same exception."""
        def measured(litellm, tool_name, *args, **kwargs):
            self._admit()
            role, slot, kind = self._role(tool_name)
            model = str(kwargs.get("model", ""))
            base = {"slot": slot, "kind": kind, "role": role, "model": model}
            t0 = self._clock()
            try:
                response = call(litellm, tool_name, *args, **kwargs)
            except Exception as exc:
                self._note({**base, "ok": False, "latency_s": self._clock() - t0, "error": type(exc).__name__,
                            "input_tokens": None, "output_tokens": None, "cache_read_tokens": None,
                            "cost_usd": None})
                self._settle(None)
                raise
            latency = self._clock() - t0
            used = tokens(response)
            cost = self._price(litellm, response, model) if used["input_tokens"] is not None else None
            self._note({**base, "ok": True, "latency_s": latency, "error": "", **used, "cost_usd": cost})
            self._settle(cost)
            return response
        return measured

    @contextmanager
    def installed(self):
        """completion_with_tool measured for the length of the block, put back after (read at call time
        by decide, its draws and author_rule)."""
        from eregion_core import llm_call
        shipped = llm_call.completion_with_tool
        llm_call.completion_with_tool = self.wrap(shipped)
        try:
            yield self
        finally:
            llm_call.completion_with_tool = shipped


# ── What the report says ─────────────────────────────────────────────────────────────────────────

def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _mean(values: list) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) / len(known) if known else None


def _sum_or_unknown(values: list) -> float | None:
    """A sum of costs: unknown as soon as one is — never a partial sum given for the whole."""
    if not values or any(v is None for v in values):
        return None
    return sum(values)


def _median(values: list[float]) -> float:
    from statistics import median
    return median(values)


def _mean_or_unknown(values: list) -> float | None:
    if not values or any(v is None for v in values):
        return None
    return sum(values) / len(values)


def summarize(calls: list[dict]) -> dict:
    """The figures of a set of calls (a genre, or the whole run). Failed calls counted apart."""
    ok = [c for c in calls if c["ok"]]
    lat = [c["latency_s"] for c in ok]
    slots: dict[int, list[dict]] = {}
    for c in ok:
        slots.setdefault(c["slot"], []).append(c)
    firsts = [[c for c in s if c["role"] in (DECISION, PROPOSAL)] for s in slots.values()]
    firsts = [f for f in firsts if f]
    costs = [c["cost_usd"] for c in ok]
    turns = [c["latency_s"] for c in ok if c["role"] == ENQUIRY]
    return {
        "unit": "proposal" if calls and all(c["role"] == PROPOSAL for c in calls) else "decision",
        "calls": len(ok), "failed": len(calls) - len(ok),
        "draws": sum(1 for c in ok if c["role"] == DRAW),
        # ENQ4: the enquiry's turns, and the latency of one (median, p95, max).
        "turns": len(turns),
        "turn_latency_s": ({"median": _median(turns), "p95": _p95(turns), "max": max(turns)} if turns else None),
        "latency_s": ({"median": _median(lat), "p95": _p95(lat), "max": max(lat)} if lat else None),
        "input_tokens_mean": _mean([c["input_tokens"] for c in ok]),
        "output_tokens_mean": _mean([c["output_tokens"] for c in ok]),
        "tokens_unknown": sum(1 for c in ok if c["input_tokens"] is None),
        # Per decision (one slot): its decision call alone (neither its draws nor, for the genre enquete,
        # its enquiry's turns — PRT2), then every call of the slot.
        "cost_per_decision_usd": _mean_or_unknown([_sum_or_unknown([c["cost_usd"] for c in f]) for f in firsts]),
        "cost_per_decision_with_draws_usd": _mean_or_unknown(
            [_sum_or_unknown([c["cost_usd"] for c in s]) for s in slots.values()]),
        "cost_usd": _sum_or_unknown(costs),
        "cost_unknown": sum(1 for c in costs if c is None),
        "cost_known_usd": sum(c for c in costs if c is not None),
    }


def measure(calls: list[dict]) -> dict:
    """By genre of case (in the order met), then the whole run; and every call (--json)."""
    kinds: list[str] = []
    for c in calls:
        if c["kind"] not in kinds:
            kinds.append(c["kind"])
    return {"by_kind": {k: summarize([c for c in calls if c["kind"] == k]) for k in kinds},
            "all": summarize(calls), "calls": calls}


def _usd(value: float | None) -> str:
    return "unknown" if value is None else f"${value:.4f}"


def line(name: str, s: dict) -> str:
    """One genre on one line: « act  12 calls (6 draws) · latency med 3.1s p95 4.0s max 4.2s · tokens
    in 4210 out 530 (mean) · per decision $0.0181 ($0.0102 the decision call alone) » — the call alone,
    without the draws nor the enquiry's turns (PRT2: « without the draws » said less than it took out)."""
    head = f"{name:<10} {s['calls']} call(s)"
    if s["draws"]:
        head += f" ({s['draws']} draws)"
    if s.get("turns"):
        t = s["turn_latency_s"]
        head += (f" ({s['turns']} enquiry turns, med {t['median']:.1f}s p95 {t['p95']:.1f}s "
                 f"max {t['max']:.1f}s a turn)")
    if s["failed"]:
        head += f", {s['failed']} failed"
    lat = s["latency_s"]
    parts = [head, (f"latency med {lat['median']:.1f}s p95 {lat['p95']:.1f}s max {lat['max']:.1f}s"
                    if lat else "latency —")]
    if s["input_tokens_mean"] is None:
        parts.append("tokens unknown (no usage)")
    else:
        parts.append(f"tokens in {s['input_tokens_mean']:.0f} out {s['output_tokens_mean'] or 0:.0f} (mean)"
                     + (f", {s['tokens_unknown']} without usage" if s["tokens_unknown"] else ""))
    per = f"per {s['unit']} {_usd(s['cost_per_decision_with_draws_usd'])}" + _known(s, " over the genre")
    if s["draws"] or s.get("turns"):
        per += f" ({_usd(s['cost_per_decision_usd'])} the decision call alone)"
    parts.append(per)
    return " · ".join(parts)


def _known(s: dict, over: str = "") -> str:
    """Beside a cost unknown, the part known — « ($0.0100 known over the genre) » — when there is one (HRN2)."""
    return (f" (${s['cost_known_usd']:.4f} known{over})"
            if s.get("cost_usd") is None and s.get("cost_known_usd") else "")


def run_cost_line(s: dict, model: str) -> str:
    """The run's cost, said unknown when one call is unpriced — why, counted apart: no usage (no price was
    asked), or no price (LiteLLM cannot price the model) — with what is known beside it."""
    if s["cost_usd"] is not None:
        return f"Run cost   : {_usd(s['cost_usd'])} over {s['calls']} call(s) (LiteLLM's price for {model})."
    if not s["calls"]:          # every call failed: nothing answered, nothing priced
        return (f"Run cost   : unknown — no call of {model} answered"
                + (f" ({s['failed']} failed, each a cost unknown)" if s["failed"] else "") + ".")
    known = s["calls"] - s["cost_unknown"]
    no_usage = min(s["tokens_unknown"], s["cost_unknown"])
    why = ", ".join(w for w in (f"{no_usage} without usage" if no_usage else "",
                                f"{s['cost_unknown'] - no_usage} LiteLLM cannot price"
                                if s["cost_unknown"] > no_usage else "") if w)
    return (f"Run cost   : unknown — {s['cost_unknown']}/{s['calls']} call(s) of {model} unpriced ({why})"
            + (f"; ${s['cost_known_usd']:.4f} on the {known} priced" if known else "")
            + " (the tokens above, times the provider's price).")


def leaderboard_line(model: str, s: dict | None) -> str:
    """One model in the leaderboard: its median latency per call, its cost per decision, its run."""
    if not s:
        return f"{model:<28} —"
    lat = s["latency_s"]
    return (f"{model:<28} med {lat['median']:.1f}s p95 {lat['p95']:.1f}s" if lat else f"{model:<28} latency —") + (
        f" · per decision {_usd(s['cost_per_decision_with_draws_usd'])} · run {_usd(s['cost_usd'])}{_known(s)}"
        + (f" · {s['failed']} failed" if s["failed"] else ""))


def report(m: dict, model: str) -> list[str]:
    """The block printed after a model's run: each genre, the whole, the run's cost, the failures."""
    out = ["Cost & latency (HRN1) — per call; failed calls apart, in none of the figures:"]
    out += ["  " + line(k, s) for k, s in m["by_kind"].items()]
    out.append("  " + line("all", m["all"]))
    out.append(run_cost_line(m["all"], model))
    if m["all"]["failed"]:
        out.append(f"Failed     : {m['all']['failed']} call(s) to the model failed (counted apart).")
    return out
