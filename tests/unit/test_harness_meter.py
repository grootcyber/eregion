"""HRN1 (#1065) — the harness measures the latency, the tokens and the cost of each call to the model.

scripts/harness_meter.py wraps `eregion_core.llm_call.completion_with_tool` for the length of a run of
scripts/llm_smoke.py. Here the model is never called: `litellm.completion` answers fabricated responses
with a fabricated `usage`, and the price is LiteLLM's own (`completion_cost`, its local map) or a fake.
What is checked: the latency noted around each call, the draws' with their decision's; the tokens read
in the `usage`; a cost LiteLLM cannot compute said unknown, never 0; a failed call counted apart; and the
attestation the same to the byte whether a run was measured or not (the measure never enters it).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "llm_smoke.py"


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("llm_smoke_hrn1", SMOKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def hm(smoke):
    return smoke.hm


def _response(action="isolate_vm", confidence=0.9, usage=(4200, 510), cache=None):
    """What LiteLLM hands back for a security_decision call; `usage` (in, out) or None."""
    args = {"reasoning": f"r — {action}", "confidence": confidence, "action": action, "reversible": True,
            "explanation": "e", "escalate": False, "escalation_reason": "", "suggested_steps": []}
    call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args)))
    used = None if usage is None else SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1],
                                                       cache_read_input_tokens=cache)
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))], usage=used)


def _call(slot, role, latency, cost, kind="act", ok=True, tokens=(4000, 500)):
    return {"slot": slot, "kind": kind, "role": role, "model": "m/a", "ok": ok, "latency_s": latency,
            "error": "" if ok else "Timeout", "input_tokens": tokens[0] if ok else None,
            "output_tokens": tokens[1] if ok else None, "cache_read_tokens": None, "cost_usd": cost}


# ── Per call ─────────────────────────────────────────────────────────────────────────────────────

def test_each_call_notes_its_latency_on_a_monotonic_clock_and_passes_through_unchanged(hm):
    ticks = iter([10.0, 12.5])
    meter = hm.Meter(clock=lambda: next(ticks), price=lambda litellm, resp, model: 0.012)
    seen = []
    resp = _response()

    def call(litellm, tool_name, **kw):
        seen.append((litellm, tool_name, kw))
        return resp
    with meter.slot("act"):
        got = meter.wrap(call)("LITELLM", "security_decision", model="m/a", temperature=0.0, max_tokens=4096)
    assert got is resp
    assert seen == [("LITELLM", "security_decision", {"model": "m/a", "temperature": 0.0, "max_tokens": 4096})]
    [c] = meter.calls
    assert (c["role"], c["kind"], c["ok"], c["latency_s"]) == ("decision", "act", True, 2.5)
    assert (c["input_tokens"], c["output_tokens"], c["cost_usd"]) == (4200, 510, 0.012)
    assert hm.Meter().calls == [] and hm.Meter()._clock is time.monotonic


def test_the_tokens_are_read_in_the_usage_and_unknown_without_it(hm):
    assert hm.tokens(_response(usage=(4200, 510), cache=3600)) == {
        "input_tokens": 4200, "output_tokens": 510, "cache_read_tokens": 3600}
    assert hm.tokens({"usage": {"prompt_tokens": 7, "completion_tokens": 3}})["input_tokens"] == 7
    for silent in (_response(usage=None), _response(usage=(0, 0)), SimpleNamespace(),
                   SimpleNamespace(usage=SimpleNamespace(prompt_tokens="many", completion_tokens=None))):
        assert hm.tokens(silent)["input_tokens"] is None and hm.tokens(silent)["output_tokens"] is None
    # No usage: no price asked — the cost is unknown with the tokens.
    asked = []
    meter = hm.Meter(price=lambda *a: asked.append(a) or 0.5)
    with meter.slot("act"):
        meter.wrap(lambda litellm, tool, **kw: _response(usage=None))(None, "security_decision", model="m/a")
    assert asked == [] and meter.calls[0]["cost_usd"] is None


def test_a_cost_litellm_cannot_compute_is_unknown_never_zero(hm):
    import litellm
    from litellm import ModelResponse
    priced = ModelResponse(model="claude-sonnet-4-6",
                           usage={"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200})
    cost = hm.litellm_cost(litellm, priced, "anthropic/claude-sonnet-4-6")
    assert isinstance(cost, float) and cost > 0
    unpriced = ModelResponse(model="x", usage={"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200})
    for model in ("anthropic/claude-hrn1-unmapped", "sim/hrn1-unpriced"):
        assert hm.litellm_cost(litellm, unpriced, model) is None
    assert hm.litellm_cost(SimpleNamespace(completion_cost=lambda **kw: float("nan")), priced, "m") is None
    assert hm.litellm_cost(SimpleNamespace(completion_cost=lambda **kw: -1.0), priced, "m") is None
    # A run with one call LiteLLM cannot price: its cost, its cost per decision — unknown, said so.
    calls = [_call(1, "decision", 1.0, 0.01), _call(2, "decision", 1.0, None)]
    s = hm.summarize(calls)
    assert s["cost_usd"] is None and s["cost_unknown"] == 1 and s["cost_known_usd"] == 0.01
    assert s["cost_per_decision_usd"] is None and s["cost_per_decision_with_draws_usd"] is None
    said = "\n".join(hm.report(hm.measure(calls), "m/a"))
    assert "Run cost   : unknown — LiteLLM cannot price 1/2 call(s) of m/a; $0.0100 on the 1 it prices" in said
    assert "per decision unknown" in said and "$0.0000" not in said
    # A known 0 (a local model LiteLLM prices free) stays 0.
    free = hm.summarize([_call(1, "decision", 1.0, 0.0)])
    assert free["cost_usd"] == 0.0 and free["cost_unknown"] == 0


def test_a_failed_call_is_counted_apart(hm):
    ticks = iter([0.0, 30.0])
    meter = hm.Meter(clock=lambda: next(ticks), price=lambda *a: 0.02)

    def boom(litellm, tool, **kw):
        raise TimeoutError("provider")
    with meter.slot("act"), pytest.raises(TimeoutError):
        meter.wrap(boom)(None, "security_decision", model="m/a")
    [c] = meter.calls
    assert (c["ok"], c["error"], c["latency_s"], c["cost_usd"]) == (False, "TimeoutError", 30.0, None)
    calls = [_call(1, "decision", 2.0, 0.01), c]
    s = hm.summarize(calls)
    assert (s["calls"], s["failed"]) == (1, 1)
    assert s["latency_s"] == {"median": 2.0, "p95": 2.0, "max": 2.0}, "the failed call in no figure"
    assert s["cost_usd"] == 0.01 and s["cost_unknown"] == 0
    said = hm.report(hm.measure(calls), "m/a")
    assert "1 call(s), 1 failed" in said[1] and said[-1].startswith("Failed     : 1 call(s)")


def test_the_draws_are_measured_with_their_decision(hm):
    """A disruptive decision costs its draws (D-1): their latency and their cost are the decision's."""
    calls = [_call(1, "decision", 2.0, 0.010), _call(1, "draw", 9.0, 0.012), _call(1, "draw", 7.0, 0.011),
             _call(2, "decision", 3.0, 0.009, kind="caution")]
    s = hm.summarize(calls)
    assert s["latency_s"]["max"] == 9.0 and s["latency_s"]["median"] == 5.0 and s["latency_s"]["p95"] == 9.0
    assert s["draws"] == 2 and s["calls"] == 4
    assert s["cost_per_decision_usd"] == pytest.approx((0.010 + 0.009) / 2)
    assert s["cost_per_decision_with_draws_usd"] == pytest.approx((0.033 + 0.009) / 2)
    assert s["cost_usd"] == pytest.approx(0.042)
    m = hm.measure(calls)
    assert list(m["by_kind"]) == ["act", "caution"]
    act = m["by_kind"]["act"]
    assert act["latency_s"] == {"median": 7.0, "p95": 9.0, "max": 9.0}
    assert act["cost_per_decision_with_draws_usd"] == pytest.approx(0.033)
    assert act["cost_per_decision_usd"] == pytest.approx(0.010)
    line = hm.line("act", act)
    assert line.startswith("act        3 call(s) (2 draws)") and "max 9.0s" in line
    assert "per decision $0.0330 ($0.0100 without the draws)" in line


# ── Through the harness: the real decide, its draws in threads ────────────────────────────────────

def test_decide_and_each_of_its_draws_pass_through_the_meter(smoke, monkeypatch, capsys):
    from eregion_core import llm_call
    shipped = llm_call.completion_with_tool

    def model(**kw):
        time.sleep(0.01)
        return _response("isolate_vm", 0.9, usage=(4200, 510))
    monkeypatch.setattr("litellm.completion", model)
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response, model: 0.02)
    monkeypatch.delenv("GLORFINDEL_DECISION_DRAWS", raising=False)
    res = smoke._run_one("anthropic/claude-test", 1, {"act"})
    assert llm_call.completion_with_tool is shipped, "the meter taken out after the run"
    calls = res["measure"]["calls"]
    decisions = [c for c in calls if c["role"] == "decision"]
    draws = [c for c in calls if c["role"] == "draw"]
    acts = sum(1 for sc in smoke.SCENARIOS if sc["kind"] == "act")
    assert len(decisions) == acts and len({c["slot"] for c in decisions}) == acts
    assert draws, "an isolation drawn again (D-1) — its draws measured"
    assert all(c["latency_s"] >= 0.01 and c["ok"] for c in calls)
    assert all((c["input_tokens"], c["output_tokens"], c["cost_usd"]) == (4200, 510, 0.02) for c in calls)
    act = res["measure"]["by_kind"]["act"]
    assert act["draws"] == len(draws) and act["calls"] == len(calls)
    assert act["cost_per_decision_with_draws_usd"] == pytest.approx(0.02 * len(calls) / acts)
    out = capsys.readouterr().out
    assert "Cost & latency (HRN1)" in out and "Run cost   : $" in out and "without the draws" in out


def test_the_meter_is_taken_out_when_the_run_breaks(hm):
    from eregion_core import llm_call
    shipped = llm_call.completion_with_tool
    with pytest.raises(RuntimeError):
        with hm.Meter().installed():
            assert llm_call.completion_with_tool is not shipped
            raise RuntimeError("stop")
    assert llm_call.completion_with_tool is shipped


def test_the_rule_proposals_are_measured_by_prompt(smoke, monkeypatch):
    def model(**kw):
        args = {"analysis": "a", "rule_name": "r", "interval_s": 60, "explanation": "e", "confidence": 0.7,
                "proposed_query": "Syslog | summarize n = count() by Computer, _ResourceId"}
        call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args)))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))],
                               usage=SimpleNamespace(prompt_tokens=2100, completion_tokens=300))
    monkeypatch.setattr("litellm.completion", model)
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response, model: 0.004)
    out = smoke.run_proposals("sim/model", 1)
    by = out["measure"]["by_kind"]
    n = len(smoke.proposal_cases())
    assert list(by) == ["before", "after"]
    assert all(s["unit"] == "proposal" and s["calls"] == n and s["draws"] == 0 for s in by.values())
    assert by["after"]["cost_per_decision_with_draws_usd"] == pytest.approx(0.004)
    assert out["measure"]["all"]["cost_usd"] == pytest.approx(0.004 * 2 * n)
    assert "per proposal $0.0040" in smoke.hm.line("after", by["after"])


# ── The report, the JSON, never the attestation ──────────────────────────────────────────────────

MODEL = "anthropic/claude-sonnet-5-5"


def _result(model, measured: bool):
    draw = {"action": "isolate_vm", "confidence": 0.85, "escalate": False, "held_by": "", "good": True,
            "temperature": None, "draws": []}
    cases = [{"label": "ransomware — sustained disk write (T1486)", "kind": "act", "pair": "", "expected": [],
              "incident": None, "slots": [dict(draw) for _ in range(3)]}]
    r = {"model": model, "integration": 3, "judgment": 3, "slots": 3, "overconf": 0, "cases": cases}
    if measured:
        calls = [_call(i, "decision", 2.5, 0.0123) for i in range(1, 4)] + [_call(1, "draw", 3.1, 0.0119)]
        import importlib.util as iu
        spec = iu.spec_from_file_location("hm_t", ROOT / "scripts" / "harness_meter.py")
        hm = iu.module_from_spec(spec)
        spec.loader.exec_module(hm)
        r["measure"] = hm.measure(calls)
    return r


def _main(smoke, monkeypatch, argv, result):
    monkeypatch.setattr(smoke, "_launchable_ttps", lambda: set())
    monkeypatch.setattr(smoke, "_run_one", lambda model, runs, kinds: result(model))
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", *argv])
    return smoke.main()


def _keys(obj) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def test_the_attestation_is_the_same_to_the_byte_with_or_without_the_measure(smoke, monkeypatch, tmp_path):
    """The measure goes to the report and to --json, never into requirements/harness.json: the CD of
    Imladris verifies its bytes (signed) and its fields — a measured run writes the same file."""
    lock = tmp_path / "ref.txt"
    lock.write_text("litellm==1.86.1\n")
    ref = tmp_path / "reference.json"
    ref.write_text(json.dumps(smoke.harness_pass([_result(MODEL, False)], 3, lock, "v0.6.4")))
    written = {}
    for measured in (False, True):
        out = tmp_path / f"harness-{measured}.json"
        assert _main(smoke, monkeypatch, ["--models", MODEL, "--runs", "3", "--reference", str(ref),
                                          "--attest", str(out)], lambda m: _result(m, measured)) == 0
        written[measured] = out.read_bytes()
    assert written[True] == written[False]
    att = json.loads(written[True])
    assert not _keys(att) & {"measure", "latency_s", "cost_usd", "input_tokens", "output_tokens", "calls",
                             "by_kind"}
    # --pass-out (the reference side) too.
    passes = {}
    for measured in (False, True):
        out = tmp_path / f"pass-{measured}.json"
        assert _main(smoke, monkeypatch, ["--models", MODEL, "--runs", "3", "--lock", str(lock),
                                          "--pass-out", str(out)], lambda m: _result(m, measured)) == 0
        passes[measured] = out.read_bytes()
    assert passes[True] == passes[False]


def test_the_json_and_the_leaderboard_carry_the_measure(smoke, monkeypatch, tmp_path, capsys):
    out = tmp_path / "reference.json"
    assert _main(smoke, monkeypatch, ["--models", f"{MODEL},m/b", "--runs", "3", "--json", str(out)],
                 lambda m: _result(m, True)) == 0
    said = capsys.readouterr().out
    assert "COST & LATENCY (HRN1)" in said and "per decision $0.0163 · run $0.0488" in said
    models = json.loads(out.read_text(encoding="utf-8"))["models"]
    m = models[0]["measure"]
    assert m["all"]["calls"] == 4 and m["all"]["draws"] == 1 and len(m["calls"]) == 4
    assert m["by_kind"]["act"]["latency_s"]["max"] == 3.1


def test_make_llm_compare_keeps_the_measure_in_json_out():
    import shutil
    import subprocess
    if shutil.which("make") is None:
        pytest.skip("make not installed")
    out = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "llm-compare", "MODELS=m/a",
                          "RUNS=3", "JSON_OUT=reference.json"], capture_output=True, text=True, timeout=60).stdout
    assert "scripts/llm_smoke.py --models m/a --runs 3 --json reference.json" in out
    assert "harness_attest" not in out and "--attest" not in out
