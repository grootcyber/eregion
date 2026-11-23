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
others its `draws`; a rule proposal is a `proposal`. Nothing here is written into the attestation
(requirements/harness.json): `llm_smoke.harness_pass` keeps its fields, the measure goes to the
report and to --json only.
"""
from __future__ import annotations

import math
import threading
import time
from contextlib import contextmanager

DECISION, DRAW, PROPOSAL = "decision", "draw", "proposal"
_DECISION_TOOL = "security_decision"


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


class Meter:
    """The calls of one run of the harness, on one model. `clock` and `price` are injectable (tests)."""

    def __init__(self, clock=time.monotonic, price=litellm_cost):
        self.calls: list[dict] = []
        self._clock, self._price = clock, price
        self._lock = threading.Lock()
        self._slot: dict | None = None
        self._slots = 0

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
            if tool_name != _DECISION_TOOL:
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
                raise
            latency = self._clock() - t0
            used = tokens(response)
            cost = self._price(litellm, response, model) if used["input_tokens"] is not None else None
            self._note({**base, "ok": True, "latency_s": latency, "error": "", **used, "cost_usd": cost})
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
    return {
        "unit": "proposal" if calls and all(c["role"] == PROPOSAL for c in calls) else "decision",
        "calls": len(ok), "failed": len(calls) - len(ok),
        "draws": sum(1 for c in ok if c["role"] == DRAW),
        "latency_s": ({"median": _median(lat), "p95": _p95(lat), "max": max(lat)} if lat else None),
        "input_tokens_mean": _mean([c["input_tokens"] for c in ok]),
        "output_tokens_mean": _mean([c["output_tokens"] for c in ok]),
        "tokens_unknown": sum(1 for c in ok if c["input_tokens"] is None),
        # Per decision (one slot): its first call alone, then with its confirming draws.
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
    in 4210 out 530 (mean) · per decision $0.0181 ($0.0102 without the draws) »."""
    head = f"{name:<10} {s['calls']} call(s)"
    if s["draws"]:
        head += f" ({s['draws']} draws)"
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
    per = f"per {s['unit']} {_usd(s['cost_per_decision_with_draws_usd'])}"
    if s["draws"]:
        per += f" ({_usd(s['cost_per_decision_usd'])} without the draws)"
    parts.append(per)
    return " · ".join(parts)


def run_cost_line(s: dict, model: str) -> str:
    """The run's cost, said unknown when one call could not be priced — with what is known beside it."""
    if s["cost_usd"] is not None:
        return f"Run cost   : {_usd(s['cost_usd'])} over {s['calls']} call(s) (LiteLLM's price for {model})."
    known = s["calls"] - s["cost_unknown"]
    return (f"Run cost   : unknown — LiteLLM cannot price {s['cost_unknown']}/{s['calls']} call(s) of {model}"
            + (f"; ${s['cost_known_usd']:.4f} on the {known} it prices" if known else "")
            + " (the tokens above, times the provider's price).")


def leaderboard_line(model: str, s: dict | None) -> str:
    """One model in the leaderboard: its median latency per call, its cost per decision, its run."""
    if not s:
        return f"{model:<28} —"
    lat = s["latency_s"]
    return (f"{model:<28} med {lat['median']:.1f}s p95 {lat['p95']:.1f}s" if lat else f"{model:<28} latency —") + (
        f" · per decision {_usd(s['cost_per_decision_with_draws_usd'])} · run {_usd(s['cost_usd'])}"
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
