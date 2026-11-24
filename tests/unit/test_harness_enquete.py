"""ENQ4 (#1085): the genre `enquete` of the harness (scripts/harness_enquete.py, `llm_smoke.py --enquete`).

The loop runs on recorded reads, then today's `decide` on what it read; here the model and `decide` are
always replaced: what is checked is the harness itself — every case records each read it permits, the
recorded reader serves them as fixed, the turns of the loop are measured as `enquiry` calls (the latency
of a turn, HRN1's meter), and nothing of it reaches the attestation. No Azure call, no model call.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from glorfindel.enquiry import knowledge, loop

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def he():
    return _load("harness_enquete")


@pytest.fixture(scope="module")
def hm():
    return _load("harness_meter")


@pytest.fixture(scope="module")
def smoke():
    return _load("llm_smoke")


def test_each_case_records_every_read_it_permits_and_no_other(he):
    base = knowledge.charger()
    for case in he.CASES:
        servies, _ = loop.permises(base.pour(case["regle"], case["ttp"]), case["systeme"], detection=case["row"],
                                   vm=he.RID, coffre=he.VAULT_RID)
        assert set(case["lectures"]) == set(servies), case["label"]
        assert case["expect"] in ("contain", "caution", "act")
        if case["expect"] == "act":
            assert case["allowed"]


def test_the_cases_are_those_of_the_note_the_catalogue_can_serve(he):
    labels = " ".join(c["label"] for c in he.CASES)
    for n in ("case 1", "case 2", "case 3)", "case 3b", "case 3c", "case 4", "case 5a", "case 5b", "case 6",
              "case 7"):
        assert n in labels
    grave = [c for c in he.CASES if c["ttp"] == "T1486"]
    assert all(c["expect"] in ("contain", "caution") for c in grave)
    # Cases 1 and 3 carry the same benign human verdict: case 3 is where « as usual » would mislead.
    assert he.CASES[0]["reference"] is he.CASES[2]["reference"]


def test_the_recorded_reader_serves_what_the_case_fixed(he):
    r = he.Enregistre({"root_commands": [{"m": 1}], "heartbeat_gap": None}, delai_s=0)
    read = type("R", (), {"id": "root_commands"})()
    rows = r(read, {"vm": "x"})
    rows[0]["m"] = 2                                        # a copy: the case stays as fixed
    assert r(read, {"vm": "x"}) == [{"m": 1}]
    assert r(type("R", (), {"id": "heartbeat_gap"})(), {}) is None
    assert r.lues[0] == ("root_commands", {"vm": "x"})
    # ENQ5a: a read the case did not record is a failure, never an empty answer.
    assert r(type("R", (), {"id": "vault_jobs"})(), {}) is None


class _Fake:
    """The model of the loop: one read, then a conclusion that claims « as usual »."""

    def __init__(self):
        self.calls = 0

    def __call__(self, prompt, texte, outil, timeout):
        self.calls += 1
        props = outil["function"]["parameters"]["properties"]
        if "id" in props:
            return {"geste": "lire", "id": props["id"]["enum"][0]}
        return {"geste": "conclure", "comme_d_habitude": True, "hypotheses": []}


def test_a_run_judges_the_decision_on_what_the_loop_read_and_says_the_loop(he, hm):
    seen = []

    def decide(state):
        seen.append(state)
        return {"action": "snapshot", "escalate": True, "confidence": 0.6,
                "ceiling": {"proposed": "isolate_vm"} if state["signal"]["ttp"] == "T1486" else {}}

    def etat(ttp, raw):
        return {"signal": {"ttp": ttp, "raw_signal": raw}}

    lines = []
    cases = [he.CASES[2], he.CASES[6]]
    r = he.run("m/fake", 2, meter=hm.Meter(), decide=decide, etat=etat, modele=_Fake(),
               budget=loop.Budget(n=2, t=5), read_delay=0, cases=cases, say=lines.append)
    assert [c["label"] for c in r["cases"]] == [c["label"] for c in cases]
    grave, brute = r["cases"]
    assert all(s["good"] for s in grave["slots"])           # under the ceiling, its own proposal counts
    assert not any(s["good"] for s in brute["slots"])       # a snapshot is not a block
    e = grave["slots"][0]["enquete"]
    assert e["fin"] == loop.CONCLUE and e["habitude"] is False and e["habitude_ecartee"]
    # ENQ5a: T1486's three obligatory reads are served, recorded; the code's predicates judge them.
    assert {k: e["lectures"][k] for k in ("perf_minute_series", "vault_jobs", "vault_activity")} == {
        "perf_minute_series": "lignes", "vault_jobs": "lignes", "vault_activity": "vide"}
    assert e["verdicts_code"] == {"T1486-H1": "confirme", "T1486-H2": "infirme"}
    assert r["totals"]["predicats"]["T1486-H1"]["confirme"] == 2
    assert any(line.startswith("Predicates :") and "T1486-H1 confirme 2" in line for line in lines)
    # decide reads only what the loop ran: never a read announced, not served — today's message would
    # say « aucun résultat » for a read that never ran.
    ctx = seen[0]["signal"]["raw_signal"]["investigative_context"]
    assert set(ctx) == {"root_commands", "heartbeat_gap", "perf_minute_series", "vault_jobs", "vault_activity"}
    assert seen[0]["telemetry_gaps"] == []
    for state in seen:
        sent = state["signal"]["raw_signal"]["investigative_context"]
        assert not set(sent) & (set(knowledge.ANNONCEES) | {"top_write_processes", "backup_agent_check"})
    # Without a sheet, the base enquiry ran first, by the code (the brute force's login read).
    assert brute["slots"][0]["enquete"]["lectures"]["successful_auth_from_ip"] == "vide"
    # Claimed every time, refused every time: a grave technique (case 3), no reference (case 5a).
    assert r["totals"]["habitude_reclamee_refusee"] == 4 and r["totals"]["slots"] == 4
    assert brute["slots"][0]["enquete"]["habitude_ecartee"] != e["habitude_ecartee"]
    assert any(line.startswith("Enquiry    :") for line in lines)
    json.dumps(r, default=str)                              # --json writes it


def test_a_case_that_breaks_is_a_failed_slot_never_a_crash(he, hm):
    def boom(state):
        raise RuntimeError("provider down")
    r = he.run("m/fake", 1, meter=hm.Meter(), decide=boom, etat=lambda t, raw: {"signal": {}}, modele=_Fake(),
               read_delay=0, cases=[he.CASES[0]], say=lambda *_: None)
    assert r["cases"][0]["slots"][0]["good"] is False


@pytest.mark.parametrize("expect, out, good", [
    ({"expect": "contain"}, {"action": "snapshot", "ceiling": {"proposed": "isolate_vm"}}, True),
    ({"expect": "contain"}, {"action": "snapshot", "escalate": True}, False),
    ({"expect": "caution"}, {"action": "isolate_vm", "escalate": True}, True),
    ({"expect": "caution"}, {"action": "isolate_vm"}, False),
    ({"expect": "act", "allowed": {"block_suspicious_ip"}}, {"action": "block_suspicious_ip"}, True),
    ({"expect": "contain", "steer": {"no_action"}}, {"action": "no_action"}, False),
])
def test_the_judgment_of_a_case(he, expect, out, good):
    assert he.judge(expect, out)[0] is good


def test_the_meter_calls_a_turn_of_the_loop_an_enquiry_and_says_its_latency(hm):
    ticks = iter([0.0, 2.0, 10.0, 15.0, 20.0, 21.0])
    m = hm.Meter(clock=lambda: next(ticks), price=lambda *a: 0.01)

    class R:
        usage = {"prompt_tokens": 3000, "completion_tokens": 200}

    call = m.wrap(lambda litellm, tool, **kw: R())
    with m.slot("enquete"):
        call(None, "enquete", model="m/a")
        call(None, "enquete", model="m/a")
        call(None, "security_decision", model="m/a")
    assert [c["role"] for c in m.calls] == ["enquiry", "enquiry", "decision"]
    s = hm.summarize(m.calls)
    assert s["turns"] == 2 and s["turn_latency_s"] == {"median": 3.5, "p95": 5.0, "max": 5.0}
    assert "2 enquiry turns" in hm.line("enquete", s)
    assert hm.summarize([c for c in m.calls if c["role"] == "decision"])["turn_latency_s"] is None


def test_the_model_of_the_harness_is_called_through_the_meter_bounded_by_t(he, monkeypatch):
    from eregion_core import llm_call
    got = {}

    class Fn:
        arguments = json.dumps({"geste": "lire", "id": "heartbeat_gap"})

    class Msg:
        tool_calls = [type("C", (), {"function": Fn})()]

    def fake(litellm, tool_name, **kw):
        got.update(kw, tool_name=tool_name)
        return type("Resp", (), {"choices": [type("Ch", (), {"message": Msg})()]})()

    monkeypatch.setattr(llm_call, "completion_with_tool", fake)
    monkeypatch.setitem(sys.modules, "litellm", type(sys)("litellm"))
    tour = he.modele_litellm("m/a")
    tool = {"function": {"name": "enquete"}}
    assert tour("P", "M", tool, 12.5) == {"geste": "lire", "id": "heartbeat_gap"}
    assert got["tool_name"] == "enquete" and got["timeout"] == 12.5 and got["num_retries"] == 0
    assert got["temperature"] == 0.0 and got["messages"][0] == {"role": "system", "content": "P"}
    Msg.tool_calls = []
    assert tour("P", "M", tool, 3) is None


@pytest.mark.parametrize("extra", [["--attest", "x.json"], ["--kinds", "act"], ["--pass-out", "p.json"],
                                   ["--proposals"]])
def test_the_enquiry_genre_never_attests_refused_before_any_call(smoke, monkeypatch, extra, capsys):
    monkeypatch.setattr(smoke, "_load_meter", lambda *a: pytest.fail("loaded: a call could follow"))
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--enquete", "--models", "m/a", *extra])
    assert smoke.main() == 2
    assert "nothing run" in capsys.readouterr().out


def _litellm_response(args: dict):
    from types import SimpleNamespace
    call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args)))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))],
                           usage=SimpleNamespace(prompt_tokens=3000, completion_tokens=200,
                                                 cache_read_input_tokens=None))


def test_the_enquiry_session_stops_at_its_ceiling(smoke, monkeypatch, tmp_path, capsys):
    """HRN2's ceiling on --enquete: checked before each call, a turn of the loop as a call of decide;
    once reached, no call more, the session cut, exit 3 — no attestation (refused anyway)."""
    calls = []

    def completion(**kw):
        calls.append(kw["tools"][0]["function"]["name"])
        if kw["tools"][0]["function"]["name"] == "enquete":
            return _litellm_response({"geste": "conclure"})
        return _litellm_response({"reasoning": "r", "confidence": 0.5, "action": "snapshot", "reversible": True,
                                  "explanation": "e", "escalate": True, "escalation_reason": "x",
                                  "suggested_steps": []})

    monkeypatch.setattr("litellm.completion", completion)
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response, model: 0.02)
    out = tmp_path / "enquete.json"
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--enquete", "--models", "anthropic/claude-test",
                                      "--runs", "1", "--read-delay", "0", "--max-usd", "0.1",
                                      "--json", str(out)])
    assert smoke.main() == 3
    assert len(calls) == 5                                  # 5 × 0.02 $ = the ceiling: the 6th never made
    assert "enquete" in calls and "security_decision" in calls
    run = json.loads(out.read_text(encoding="utf-8"))["models"][0]
    assert run["stopped"] and run["ceiling"]["calls"] == 5 and run["ceiling"]["max_usd"] == 0.1
    assert len(run["cases"]) < len(_load("harness_enquete").CASES)
    # The run in course when the ceiling refused a call is never a good one, and Judgment never counts it.
    cut = run["cases"][-1]["slots"][-1]
    assert cut["good"] is False and "ceiling" in cut["why"]
    done = [s for c in run["cases"] for s in c["slots"]]
    assert run["totals"]["good"] == sum(1 for s in done if s["good"]) == len(done) - 1
    out = capsys.readouterr().out
    assert "stopped at its ceiling" in out and f"Judgment   : {len(done) - 1}/{len(done)}" in out


def test_a_broken_decide_that_escalates_is_never_a_good_call(he, hm):
    """Outside any ceiling: decide failed (no tool call), its fallback escalates — on a « caution » case it
    must not pass for good judgment (llm_smoke's <no-tool-call>)."""
    r = he.run("m/fake", 1, meter=hm.Meter(), decide=lambda s: {"action": "", "escalate": True},
               etat=lambda t, raw: {"signal": {}}, modele=_Fake(), read_delay=0, cases=[he.CASES[0]],
               say=lambda *_: None)
    slot = r["cases"][0]["slots"][0]
    assert he.CASES[0]["expect"] == "caution" and slot["good"] is False and "<no-tool-call>" in slot["why"]
    assert r["totals"]["good"] == 0


def test_the_session_s_bound_of_calls_counts_the_loop_s_turns(he):
    assert he.run_bound(3, 4, 3) == len(he.CASES) * 3 * 8 == 240


def test_a_ceiling_that_is_none_is_refused_before_any_call(smoke, monkeypatch, capsys):
    monkeypatch.setattr(smoke, "_load_meter", lambda *a: pytest.fail("loaded: a call could follow"))
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--enquete", "--models", "m/a", "--max-usd", "0"])
    assert smoke.main() == 2 and "nothing run" in capsys.readouterr().out


def test_make_llm_compare_enquete_runs_the_genre_with_its_budget():
    if shutil.which("make") is None:
        pytest.skip("make not installed")
    out = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "llm-compare", "MODELS=m/a",
                          "RUNS=3", "ENQUETE=1", "ENQ_N=3", "ENQ_T=45",
                          "JSON_OUT=/home/op/eregion-banc/enquete-2026-11-24.json"],
                         capture_output=True, text=True, timeout=60).stdout
    assert ("scripts/llm_smoke.py --enquete --models m/a --runs 3 --budget-n 3 --budget-t 45 --max-usd 3 "
            "--json /home/op/eregion-banc/enquete-2026-11-24.json") in out
    assert "harness_attest" not in out
    # The ceiling is the session's by default, MAX_USD and MAX_CALLS when given (HRN2).
    other = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "llm-compare", "MODELS=m/a",
                            "ENQUETE=1", "MAX_USD=1.5", "MAX_CALLS=60"],
                           capture_output=True, text=True, timeout=60).stdout
    assert "--enquete --models m/a --runs 3 --max-usd 1.5 --max-calls 60" in other
