"""MEM-H (#1028): the genre `precedents` of the harness (scripts/harness_precedents.py, `llm_smoke.py
--precedents`) — the same cases under three memories: none, by distance (ChromaDB), by keys (SQLite).

The model and `decide` are replaced here (or LiteLLM's call, end to end): what is checked is the harness
itself — the precedents are built by the harness, one fresh memory of each kind per case, never one case's
reaching another (M7032); the state decide is given differs by its precedents only; what moves between the
memories is counted (M7033), the overconfident errors by the CD's rule; nothing is run without its ceiling
(M7034). The memories are the watch's own code, in a throwaway directory. No Azure call, no model call.
"""
from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hp():
    return _load("harness_precedents")


@pytest.fixture(scope="module")
def hm():
    return _load("harness_meter")


@pytest.fixture(scope="module")
def smoke():
    return _load("llm_smoke")


@pytest.fixture(scope="module")
def table(hp):
    """Every case's precedents, under the two memories of the watch (built once: ChromaDB is slow)."""
    return hp.table_of(hp.CASES)


def test_each_case_names_its_rule_and_its_history_holds_the_memorys_bounds(hp):
    assert len({c["label"] for c in hp.CASES}) == len(hp.CASES)
    for i, case in enumerate(hp.CASES):
        assert case["kind"] in ("act", "caution") and case["ttp"] in hp.RULES
        if case["kind"] == "act":
            assert case["expected"]
        cycles = [c for _at, c in hp.history(case, i)]
        assert {c["run_id"] for c in cycles} == {f"memh-{i}"}
        assert any(c["source"] == "exercise" for c in cycles)                    # SEC4a: never given
        assert any(hp.NOW - at > 90 * hp.DAY for at, _c in hp.history(case, i))   # SEC17: never given
        assert sum(c["ttp"] == case["ttp"] for c in cycles) >= 3
    # The rules are the shipped ones.
    shipped = (ROOT / "glorfindel/rules/azure/detection_rules.yaml").read_text(encoding="utf-8")
    assert all(f"- name: {rule}\n" in shipped for rule in hp.RULES.values())


def test_each_memory_gives_its_cases_own_cycles_and_none_of_another(hp, table):
    """M7032: one fresh memory of each kind per case — it holds that case's history only, and gives
    none of another case's cycles, nor an exercise, nor one past the 90 days."""
    for i, case in enumerate(hp.CASES):
        got = table[case["label"]]
        assert got[hp.NONE] == {"precedents": [], "held": 0}
        for mode in (hp.DISTANCE, hp.KEYS):
            assert got[mode]["held"] == len(hp.HISTORY), (case["label"], mode)
            precedents = got[mode]["precedents"]
            assert len(precedents) == 3
            assert {p["run_id"] for p in precedents} == {f"memh-{i}"}, (case["label"], mode)
            assert all(p["source"] == "real" and hp.NOW - p["stored_at"] <= 90 * hp.DAY for p in precedents)
            assert len({p["resource_id"] for p in precedents}) == 3                # one per VM (SEC-I)


def test_the_keys_give_the_technique_and_the_distance_does_not_always(hp, table):
    """The history is built so that the two memories may choose otherwise (MEM1's measure): the keys give
    the case's technique, the distance not on every case."""
    other = 0
    for case in hp.CASES:
        keys = table[case["label"]][hp.KEYS]["precedents"]
        dist = table[case["label"]][hp.DISTANCE]["precedents"]
        assert all(p["ttp"] == case["ttp"] for p in keys)
        assert keys[0]["rule_name"] == hp.RULES[case["ttp"]]                     # the rule first
        other += [p["signal_id"] for p in keys] != [p["signal_id"] for p in dist]
    assert other >= 1


def test_the_keys_precedents_say_their_verdict_and_the_distances_none(hp, table):
    """M7442 (MEM2b): the harness's verdicts never reach the keys — the session would replay MEM-H's passage
    1 without what it is replayed for. The modest write (EH12's case): the two former isolations of the
    keys are real attacks judged right — the one of 50 days that made the model drift on 24/11 included,
    the unfavourable case — and the rule's newest a false alarm judged right."""
    modest = next(c for c in hp.CASES if c["label"].startswith("modest disk write"))
    keys = table[modest["label"]][hp.KEYS]["precedents"]
    assert [(p["action"], p["verdict"], p["resource_id"].rsplit("/", 1)[-1]) for p in keys] == [
        ("no_action", "right", "vm-bench-a"), ("isolate_vm", "right", "vm-smoke"),
        ("isolate_vm", "right", "vm-bench-b")]
    assert keys[0]["summary"].endswith("décision jugée juste (fausse alerte)")
    assert all(p["summary"].endswith("décision jugée juste (vraie attaque)") for p in keys[1:])
    # Only the closed decision of vm-bench-b on another technique is never judged.
    unjudged = [h for h in hp.HISTORY if not h[6]]
    assert unjudged == [(3, "vm-bench-b", 2, True, "closed", "real", False)]
    for case in hp.CASES:
        for p in table[case["label"]][hp.DISTANCE]["precedents"]:
            assert "verdict" not in p and "verdict humain" not in p["summary"]      # as in production


def test_the_verdicts_leave_the_keys_choice_of_the_session_of_24_11(hp, table, tmp_path):
    """The passage 1 replayed as it was: the same cycles, the same choices of the keys — only what they
    say of their verdict is new."""
    def unjudged(mode, where, clock, **_kw):
        return hp.open_memory(mode, where, clock, verdicts=lambda: {})
    for i, case in enumerate(hp.CASES):
        before = hp.precedents_of(case, i, tmp_path, unjudged, modes=(hp.KEYS,))[hp.KEYS]["precedents"]
        now = table[case["label"]][hp.KEYS]["precedents"]
        assert [p["signal_id"] for p in before] == [p["signal_id"] for p in now], case["label"]
        assert all(p["summary"].endswith("non jugé") for p in before)
    assert [h[:6] for h in hp.HISTORY][:2] == [(2, "vm-smoke", 1, True, "contained", "real"),
                                                (40, "vm-smoke", 0, False, "contained", "real")]


def test_the_rank_prefers_a_judged_cycle_on_the_harness_history(hp, tmp_path):
    """The passage 1 does not exercise the preference (the same cycles are chosen, judged or not): here,
    outside the session, on the modest write's history — the rule's newest (closed, 6 days) left unjudged,
    its older isolation (20 days) judged wrong — the keys give the judged one first, said « jugée fausse »."""
    i, modest = next((i, c) for i, c in enumerate(hp.CASES) if c["label"].startswith("modest disk write"))
    wrong = {f"memh-{i}-3": {"verdict": "wrong", "at": "2026-10-29T00:00:00+00:00", "action": "isolate_vm"}}

    def judged(mode, where, clock, **_kw):
        return hp.open_memory(mode, where, clock, verdicts=lambda: wrong)
    keys = hp.precedents_of(modest, i, tmp_path, judged, modes=(hp.KEYS,))[hp.KEYS]["precedents"]
    assert [p["signal_id"] for p in keys][0] == f"memh-{i}-3"
    assert keys[0]["summary"].endswith("décision jugée fausse (fausse alerte, ou action disproportionnée)")
    assert hp.HISTORY[3][:2] == (20, "vm-bench-a") and hp.HISTORY[2][:2] == (6, "vm-bench-a")


def _fake_decide(seen):
    """Isolates at 0.9 when a precedent contained by isolation, else a snapshot held for a human."""
    def decide(state):
        seen.append(state)
        if any(p.get("action") == "isolate_vm" for p in state["past_cycles"]):
            return {"action": "isolate_vm", "confidence": 0.9, "escalate": False}
        return {"action": "snapshot", "confidence": 0.5, "escalate": True}
    return decide


def test_a_run_plays_each_case_under_the_three_memories_and_counts_what_moves(hp, hm, smoke, table, monkeypatch):
    """M7033: what moves between the memories is counted and said — never left out."""
    monkeypatch.setattr(hp, "table_of", lambda cases, opener=None: {c["label"]: table[c["label"]] for c in cases})
    seen, lines = [], []
    cases = [hp.CASES[2], hp.CASES[6]]          # sudo to root (act), the routine sudo (caution)
    meter = hm.Meter()
    r = hp.run("m/fake", 2, meter=meter, decide=_fake_decide(seen), state_of=smoke._state, judge=smoke._judge,
               distribution=smoke._distribution, cases=cases, say=lines.append)
    assert len(seen) == 2 * 2 * 3
    # decide's state differs by its precedents only: the harness's own state, its signal the one the memory
    # was searched with (the RulePoller's: its rule, its provider) — M7353.
    for state in seen:
        case = next(c for c in cases if c["ttp"] == state["signal"]["ttp"]
                    and c["row"] == state["signal"]["raw_signal"]["first_result_row"])
        base = smoke._state(case["ttp"], {"first_result_row": case["row"]})
        assert {**state, "past_cycles": []} == {**base, "signal": hp.signal_of(case)}
        assert state["signal"]["context"]["rule_name"] == hp.RULES[case["ttp"]]
        assert state["signal"]["provider"] == "azure"
    assert [len(s["past_cycles"]) for s in seen[:3]] == [0, 3, 3]
    assert [c["kind"] for c in meter.calls] == []                               # decide replaced: no call
    root, routine = r["cases"]
    assert {m: len(s) for m, s in root["slots"].items()} == {m: 2 for m in hp.MEMORIES}
    # none: a snapshot held; with precedents that isolated: an isolation — the decision moves.
    assert root["moves"]["aucune->cles"]["decision"] is True
    assert root["moves"]["aucune->cles"]["from"] == "snapshot" and root["moves"]["aucune->cles"]["to"] == "isolate_vm"
    assert root["moves"]["aucune->cles"]["confidence"] == pytest.approx(0.4)
    assert root["moves"]["distance->cles"]["decision"] is False
    t = r["totals"]
    assert t["pairs"]["aucune->cles"]["decisions_moved"] == 2 == t["pairs"]["aucune->distance"]["decisions_moved"]
    assert t["pairs"]["distance->cles"]["decisions_moved"] == 0
    assert t["pairs"]["aucune->cles"]["confidences_moved"] == 2
    # The routine sudo isolated at 0.9 with precedents: overconfident errors, by the CD's rule.
    assert t["memories"]["aucune"]["overconfident"] == 0 and t["memories"]["cles"]["overconfident"] == 2
    assert t["pairs"]["aucune->cles"]["drift"] and routine["label"] in t["pairs"]["aucune->cles"]["drift_cases"]
    said = "\n".join(lines)
    assert "aucune->cles: 2/2 decisions moved" in said and "MOVED (snapshot → isolate_vm)" in said
    assert "overconfident errors (the CD's rule) aucune 0 · distance 2 · cles 2" in said
    assert said.index("The precedents each memory gives") < said.index("[precedents]")
    json.dumps(r, default=str)                                                  # --json writes it


def test_what_moves_is_read_from_the_most_frequent_action_and_the_median_confidence(hp):
    a = [{"action": "isolate_vm", "confidence": 0.8, "good": True}] * 2 + [
        {"action": "snapshot", "confidence": 0.5, "good": False}]
    b = [{"action": "snapshot", "confidence": 0.55, "good": False}] * 2 + [
        {"action": "isolate_vm", "confidence": 0.9, "good": True}]
    mv = hp.move(a, b)
    assert mv == {"decision": True, "from": "isolate_vm", "to": "snapshot", "confidence": pytest.approx(-0.25),
                  "confidence_moved": True, "good": [2, 1]}
    assert hp.move(a, a)["decision"] is False and hp.move(a, a)["confidence_moved"] is False
    assert hp.move([], a) is None
    # A tie is broken by the name, never by the order drawn; a proposal under a ceiling is the action.
    assert hp._top([{"action": "snapshot"}, {"action": "isolate_vm"}]) == "isolate_vm"
    assert hp._top([{"action": "snapshot", "proposed": "isolate_vm"}]) == "isolate_vm"


def test_the_overconfidence_is_the_cds_own_rule(hp):
    cd = hp.cd_rule()
    assert cd is sys.modules["eregion_cd"] and hasattr(cd, "overconfident_drift")
    assert str(ROOT / "infra" / "glorfindel-host" / "cd") not in sys.path        # its path taken out after
    wrong = {"action": "isolate_vm", "confidence": 0.85, "good": False}
    right = {"action": "snapshot", "confidence": 0.85, "good": True}
    rows = [{"label": "c", "kind": "caution", "slots": {hp.NONE: [right] * 3, hp.DISTANCE: [right] * 3,
                                                          hp.KEYS: [wrong] * 3}}]
    t = hp.compare(rows)["totals"]
    assert t["memories"]["cles"]["overconfident"] == 3
    assert t["pairs"]["distance->cles"]["drift"].startswith("erreurs surconfiantes")
    assert t["pairs"]["aucune->distance"]["drift"] == "" and t["other_precedents"] == 0


def test_a_draw_the_ceiling_cut_is_a_failure_never_an_overconfident_error(hp):
    """M7352: the draw the ceiling cut keeps its confidence, and counts as a failed call — never as an
    overconfident error, nor in a drift by the CD's rule."""
    cut = {"action": "isolate_vm", "confidence": 0.95, "good": False, "cut": "the bound of 5 call(s) reached"}
    right = {"action": "snapshot", "confidence": 0.5, "good": True}
    rows = [{"label": "c", "kind": "caution", "slots": {hp.NONE: [right], hp.DISTANCE: [right],
                                                          hp.KEYS: [right, cut]}}]
    t = hp.compare(rows)["totals"]
    assert t["memories"]["cles"] == {"good": 1, "slots": 2, "overconfident": 0}
    assert t["pairs"]["distance->cles"]["drift"] == ""


class _CutMeter:
    """A meter whose ceiling is reached in its `after`-th slot (HRN2's `stopped`)."""

    def __init__(self, after: int):
        self.after, self.n, self.stopped, self.kinds = after, 0, "", []

    @contextmanager
    def slot(self, kind: str):
        self.n += 1
        self.kinds.append(kind)
        try:
            yield
        finally:
            if self.n >= self.after:
                self.stopped = f"the bound of {self.after} call(s) reached"


@pytest.mark.parametrize("genre", ["decision", "enquete"])
def test_a_ceiling_reached_leaves_the_three_memories_drawn_alike(hp, smoke, table, monkeypatch, genre):
    """M7350: the cases outside, each run of a case under the three memories in turn — cut at its ceiling,
    the session has drawn every memory alike (one draw apart), never C5 (`cles`, the target) left undrawn."""
    meter = _CutMeter(after=8)              # 2 cases × 2 runs × 3 memories = 12 draws, cut at the 8th
    if genre == "decision":
        monkeypatch.setattr(hp, "table_of", lambda cases, opener=None: {c["label"]: table[c["label"]] for c in cases})
        r = hp.run("m/fake", 2, meter=meter, decide=_fake_decide([]), state_of=smoke._state, judge=smoke._judge,
                   distribution=smoke._distribution, cases=[hp.CASES[2], hp.CASES[6]], say=lambda *_: None)
    else:
        he = _load("harness_enquete")
        r = hp.run_enquete("m/fake", 2, he=he, meter=meter, distribution=smoke._distribution,
                           say=lambda *_: None, decide=_fake_decide([]), cases=[he.CASES[5], he.CASES[8]],
                           etat=lambda ttp, raw: smoke._state(ttp, raw), modele=_Fake(), read_delay=0)
    drawn = {m: sum(len(c["slots"][m]) for c in r["cases"]) for m in hp.MEMORIES}
    assert drawn == {"aucune": 3, "distance": 3, "cles": 2}
    assert [k.rsplit("/", 1)[1] for k in meter.kinds] == list(hp.MEMORIES) * 2 + ["aucune", "distance"]
    cut = [s for c in r["cases"] for m in hp.MEMORIES for s in c["slots"][m] if s.get("cut")]
    assert len(cut) == 1 and cut[0]["good"] is False and r["stopped"]


def test_the_stores_are_removed_once_the_precedents_are_read(hp, monkeypatch, tmp_path):
    """M7351: the memories live under a throwaway directory, made under tempfile's own, gone once read."""
    import tempfile
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    opened = []

    def opener(mode, where, clock, **kw):
        opened.append(where)
        return hp.open_memory(mode, where, clock, **kw)

    got = hp.table_of([hp.CASES[1]], opener)
    assert len(got[hp.CASES[1]["label"]][hp.KEYS]["precedents"]) == 3
    assert len(opened) == 2 and all(tmp_path in w.parents for w in opened)
    assert list(tmp_path.iterdir()) == []


def test_nothing_runs_without_the_ceiling(smoke, monkeypatch, capsys):
    """M7034: --precedents never runs without --max-usd — refused before anything is loaded."""
    monkeypatch.setattr(smoke, "_load_meter", lambda *a: pytest.fail("loaded: a call could follow"))
    for extra in ([], ["--enquete"]):
        monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--precedents", "--models", "m/a", *extra])
        assert smoke.main() == 2
        assert "never without its ceiling" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [["--attest", "x.json"], ["--kinds", "act"], ["--pass-out", "p.json"],
                                   ["--reference", "r.json"], ["--proposals"], ["--max-usd", "0"]])
def test_the_genre_never_attests_refused_before_any_call(smoke, monkeypatch, extra, capsys):
    monkeypatch.setattr(smoke, "_load_meter", lambda *a: pytest.fail("loaded: a call could follow"))
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--precedents", "--models", "m/a", "--max-usd", "3", *extra])
    assert smoke.main() == 2
    assert "nothing run" in capsys.readouterr().out


def _response(args: dict):
    from types import SimpleNamespace
    call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args)))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[call]))],
                           usage=SimpleNamespace(prompt_tokens=4000, completion_tokens=300,
                                                 cache_read_input_tokens=None))


_SNAPSHOT = {"reasoning": "r", "confidence": 0.5, "action": "snapshot", "reversible": True, "explanation": "e",
             "escalate": True, "escalation_reason": "x", "suggested_steps": []}


def test_the_session_says_its_ceiling_first_then_the_precedents_reach_the_model(smoke, hp, table, monkeypatch,
                                                                                tmp_path, capsys):
    """End to end, LiteLLM's call replaced: the ceiling said before the first call, each decision measured
    under its memory's genre, the message to the model carrying the memory's precedents — none under
    `aucune` — and the comparison written (--json)."""
    monkeypatch.setattr(hp, "table_of", lambda cases, opener=None: {c["label"]: table[c["label"]] for c in cases})
    monkeypatch.setattr(smoke, "_load_meter", lambda name="harness_meter": hp if name == "harness_precedents"
                        else _load(name))
    messages = []

    def completion(**kw):
        messages.append(kw["messages"][-1]["content"])
        return _response(_SNAPSHOT)

    monkeypatch.setattr("litellm.completion", completion)
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response, model: 0.01)
    out = tmp_path / "precedents.json"
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--precedents", "--models", "anthropic/claude-test",
                                      "--runs", "1", "--max-usd", "5", "--json", str(out)])
    assert smoke.main() == 0
    said = capsys.readouterr().out
    assert said.index("Ceiling    : 63 call(s) at most") < said.index("Precedents (MEM-H)")
    assert "Estimate   : at the reference run's price" in said
    assert len(messages) == len(hp.CASES) * 3
    for i, message in enumerate(messages):
        if i % 3 == 0:
            assert "Aucun cycle passé disponible" in message
        else:
            assert message.count("**Cycle ") == 3 and "[RÉEL]" in message
    run = json.loads(out.read_text(encoding="utf-8"))
    assert run["mode"] == "precedents"
    r = run["models"][0]
    assert r["ceiling"]["max_usd"] == 5 and r["ceiling"]["calls"] == len(messages)
    assert set(r["measure"]["by_kind"]) == {f"precedents/{m}" for m in hp.MEMORIES}
    assert len(r["cases"]) == len(hp.CASES) and r["totals"]["pairs"]["aucune->cles"]["decisions_moved"] == 0
    assert all(set(c["slots"]) == set(hp.MEMORIES) for c in r["cases"])
    assert r["cases"][0]["precedents"]["cles"][0]["vm"] == "vm-bench-a"


def test_the_session_stops_at_its_ceiling(smoke, hp, table, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(hp, "table_of", lambda cases, opener=None: {c["label"]: table[c["label"]] for c in cases})
    monkeypatch.setattr(smoke, "_load_meter", lambda name="harness_meter": hp if name == "harness_precedents"
                        else _load(name))
    calls = []
    monkeypatch.setattr("litellm.completion", lambda **kw: calls.append(1) or _response(_SNAPSHOT))
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response, model: 0.02)
    out = tmp_path / "p.json"
    monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--precedents", "--models", "anthropic/claude-test",
                                      "--runs", "1", "--max-usd", "0.1", "--json", str(out)])
    assert smoke.main() == 3
    assert len(calls) == 5
    r = json.loads(out.read_text(encoding="utf-8"))["models"][0]
    assert r["stopped"] and r["ceiling"]["calls"] == 5
    cut = [s for c in r["cases"] for slots in c["slots"].values() for s in slots if s.get("cut")]
    assert len(cut) == 1 and cut[0]["good"] is False
    assert "stopped at its ceiling" in capsys.readouterr().out


class _Fake:
    """The model of the enquiry's loop: concludes at once."""

    def __call__(self, prompt, texte, outil, timeout):
        props = outil["function"]["parameters"]["properties"]
        if "id" in props:
            return {"geste": "lire", "id": props["id"]["enum"][0]}
        return {"geste": "conclure", "hypotheses": []}


def test_the_enquiry_runs_under_the_three_memories(hp, hm, smoke, monkeypatch):
    """C4, C5, C6: the enquiry's loop under each memory, its decide given the memory's precedents — none
    under `aucune`, as ENQ4 plays it — each in its genre of the meter; what moves, counted."""
    he = _load("harness_enquete")
    seen = []
    cases = [he.CASES[5], he.CASES[8]]                      # ransomware by day (case 4), the sudo (case 6)
    meter = hm.Meter()
    lines = []
    r = hp.run_enquete("m/fake", 1, he=he, meter=meter, distribution=smoke._distribution, say=lines.append,
                       decide=_fake_decide(seen), etat=lambda ttp, raw: smoke._state(ttp, raw), modele=_Fake(),
                       read_delay=0, cases=cases)
    assert set(r["memories"]) == set(hp.MEMORIES)
    # The cases outside, each under the three memories in turn.
    assert [len(s["past_cycles"]) for s in seen] == [0, 3, 3, 0, 3, 3]
    for i, s in enumerate(seen):
        assert {p["run_id"] for p in s["past_cycles"]} <= {f"memh-{i // 3}"}
        case = cases[i // 3]
        # decide's signal: the RulePoller's, with the reads the loop built in it — under every memory.
        assert s["signal"]["context"]["rule_name"] == case["regle"] and s["signal"]["provider"] == "azure"
        assert "investigative_context" in s["signal"]["raw_signal"]
    assert r["totals"]["pairs"]["aucune->cles"]["decisions_moved"] == 2
    assert any("=== the enquiry under the memory « cles » ===" in line for line in lines)
    assert r["memories"]["cles"]["totals"]["slots"] == 2
    # Under `aucune`, decide is given no precedent, like `he.run` without `passe`.
    alone = []
    he.run("m/fake", 1, meter=hm.Meter(), decide=_fake_decide(alone), etat=lambda t, raw: smoke._state(t, raw),
           modele=_Fake(), read_delay=0, cases=cases, say=lambda *_: None)
    assert [s["past_cycles"] for s in alone] == [seen[0]["past_cycles"], seen[3]["past_cycles"]] == [[], []]


def test_the_bounds_of_the_genre(hp):
    assert hp.run_bound(len(hp.CASES), 3, 3) == 7 * 3 * 3 * 3 == 189
    lines = hp.ceiling_lines(189, 3.0, 189)
    assert "189 call(s) at most" in lines[0] and "$3.00" in lines[0]
    assert "≈ $1.34" in lines[1] and "the bound ≈ $1.72" in lines[1]
    # The enquiry's passage: ENQ4's estimate of a passage, times the three memories — the documentation's.
    enq = hp.ceiling_lines(720, 8.0, 720, enquete=True)
    assert "$3.00 to $7.50" in enq[1] and "ENQ4's estimate" in enq[1]
    doc = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
    assert "3 à 7,5 $" in doc and "environ 1 à 2,5 $ par passage" in doc


def test_make_llm_compare_precedents_runs_the_genre_with_its_ceiling():
    if shutil.which("make") is None:
        pytest.skip("make not installed")

    def dry(*args):
        return subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "llm-compare", "MODELS=m/a",
                               *args], capture_output=True, text=True, timeout=60).stdout
    assert ("scripts/llm_smoke.py --precedents --models m/a --runs 3 --max-usd 3 "
            "--json /home/op/eregion-banc/precedents-2026-11-24.json") in dry(
        "PRECEDENTS=1", "JSON_OUT=/home/op/eregion-banc/precedents-2026-11-24.json")
    assert "--precedents --models m/a --runs 3 --max-usd 2 --max-calls 50" in dry("PRECEDENTS=1", "MAX_USD=2",
                                                                                  "MAX_CALLS=50")
    assert "--enquete --precedents --models m/a --runs 3 --max-usd 8" in dry("PRECEDENTS=1", "ENQUETE=1")
    assert "--attest refused" in dry("PRECEDENTS=1", "ATTEST=1")
    assert "harness_attest" not in dry("PRECEDENTS=1", "ATTEST=1")
