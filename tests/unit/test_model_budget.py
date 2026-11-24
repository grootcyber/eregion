"""PRT2 (#1160): the watch's breaker in dollars — two envelopes, three buckets, the criticality in the config.

The maintainer's decisions of 23/11 and 24/11 (glorfindel/model_budget.py, its docstring): the real, 5 $ a
day; the exercises, 5 $ a day and 2 $ a campaign — exhausted, the exercise pauses, never the real; the
envelope by the event's source, and in zone production an « exercise » is the real; the graves' reserve,
proportional to the critical objects, a grave on a critical object never waits; the ordinaries, a part per
VM; each call at its real cost, checked before it, an unknown cost never 0, the overrun bounded by the share
of a decision admitted; the count survives the restart and resets at midnight UTC; exhausted, a grave goes
the code's path, an ordinary a card, an alert once; the provider's limit slows, then the code's path.

Every identifier is made up (repository public): 00000000-… GUIDs, example names. No Azure, no model: the
calls go to a fake LiteLLM, or `litellm.completion` patched.
"""
from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from eregion_core import llm_call
from glorfindel import decision_queue as dq
from glorfindel import escalations
from glorfindel import model_budget as mb
from glorfindel.config import AutonomyConfig, AutonomyRule
from glorfindel.decision_queue import DecisionGate, decide_or_card

SUB = "00000000-0000-0000-0000-0000000000cc"
DAY = 1_795_000_000.0          # 2026-11-18, a fixed moment of the day — never the test's
CRITICAL_VM = "vm-example-db"


def _vm(name: str = "vm-example-01") -> str:
    return f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/{name}"


def _det(rule="ssh-brute-force", ttp="T1110.001", *, vm="vm-example-01", **ctx) -> dict:
    return {"signal_id": f"rule-{rule}-{vm}", "event": "detection", "ttp": ttp, "severity": "high",
            "resource_id": _vm(vm), "resource_type": "vm", "timestamp": "2026-11-17T10:00:00+00:00",
            "context": {"rule_name": rule, "run_id": f"watch-{rule}-20261117T100000Z", "attribution": "asset",
                        **ctx},
            "raw_signal": {"detection_source": "azure_monitor",
                           "first_result_row": {"Computer": vm, "SourceIP": "203.0.113.7", "MaxWrite": 80.0}}}


def _grave(vm="vm-example-01", **ctx) -> dict:
    return _det("ransomware-disk-write", "T1486", vm=vm, **ctx)


class _Clock:
    def __init__(self, t: float = DAY) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class _LiteLLM:
    """A fake LiteLLM: counts its calls, prices each `cost` (None: LiteLLM cannot price it)."""

    def __init__(self, cost: float | None = 0.01, raises: Exception | None = None) -> None:
        self.cost, self.raises, self.calls = cost, raises, 0
        self.suppress_debug_info = False

    def completion(self, **kwargs):
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 2}}

    def completion_cost(self, completion_response=None, model=""):
        if self.cost is None:
            raise ValueError("model not mapped")
        return self.cost


class _Limit(Exception):
    status_code = 429


def _ledger(tmp_path, *, critical=(), source=None, zone=None, clock=None) -> mb.Ledger:
    autonomy = AutonomyConfig(assets=[AutonomyRule(match=m, mode="human_only", critical=True) for m in critical])
    ledger = mb.Ledger(tmp_path / "model_budget.json", clock=clock or _Clock(),
                       source=source or (lambda d: ("real", "")), zone=zone or (lambda rid: "bench"),
                       autonomy=lambda: autonomy)
    mb.install(ledger)
    return ledger


def _spend(ledger: mb.Ledger, data: dict, usd: float) -> None:
    """`usd` spent by one decision on `data`'s buckets, one call priced so — through the guard."""
    verdict = ledger.judge(data, 1)
    assert verdict.kind == "model", verdict
    ledger.bound(verdict, lambda _d: llm_call.completion_with_tool(_LiteLLM(cost=usd), "t", model="m"))(data)


def _exhaust(ledger: mb.Ledger) -> None:
    """The real's 5 $ spent, by graves on six VMs (0.90 $ each): the ordinaries never take the graves' part."""
    for i in range(6):
        _spend(ledger, _grave(f"vm-example-1{i}"), 0.9)


def _call(fake: _LiteLLM):
    return llm_call.completion_with_tool(fake, "security_decision", model="example/model")


def _cards(kind: str) -> list[dict]:
    if not escalations._STORE.exists():
        return []
    rows = [json.loads(line) for line in escalations._STORE.read_text().splitlines() if line.strip()]
    return [r for r in rows if r.get("escalation_type") == kind]


@pytest.fixture(autouse=True)
def _fresh():
    dq._SEEN.clear()
    yield
    dq._SEEN.clear()


def _decide(data, **kw):
    from glorfindel.agent import decide
    from .test_agent_nodes import _state
    return decide(_state(signal=data), model="example/model",
                  autonomy=kw.pop("autonomy", AutonomyConfig(default="non_disruptive")), **kw)


# ── The real exhausted: a grave goes the code's path, an ordinary a card ─────────────────────────────

def test_the_real_exhausted_a_grave_goes_the_code_s_path_without_a_call(tmp_path):
    """M7417, M7423: the real's 5 $ spent — a ransomware detection never reaches the model: `decide` builds
    its decision by the code (the snapshot, run alone on a non_disruptive VM, a card beside it that nothing
    is contained), and the gate takes no reserve for it."""
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    gate = DecisionGate()
    with patch("litellm.completion") as model:
        state, why, wait = decide_or_card(_grave(), _decide, gate, budget=ledger)
    model.assert_not_called()
    assert state["action"] == "snapshot" and state["escalate"] is False and state["decision_model"] == ""
    assert "sans appel au modèle" in state["uncontained"] and "budget du réel" in state["uncontained"]
    assert not state.get("cycle_error") and wait == 0.0
    assert gate._reserved == {} and len(gate._calls) == 0


def test_the_real_exhausted_an_ordinary_becomes_a_card(tmp_path):
    """M7417: an ordinary detection beyond the real's budget is a card `undecided_detection`, its kind the
    budget's — never a call, never an action."""
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    seen = []
    state, why, wait = decide_or_card(_det(), lambda d: seen.append(d), DecisionGate(), budget=ledger)
    assert state is None and not seen and "budget du modèle épuisé" in why
    card = _cards("undecided_detection")[-1]
    assert "au-delà du budget du réel" in card["reason"] and card["action"] == ""


def test_a_grave_on_a_human_only_vm_proposes_the_snapshot_and_a_release_stays_a_human_s(tmp_path):
    """The code's path judged as the model's decision: human_only holds the snapshot on its card; the release
    after a restore is a card for a human, the VM left isolated."""
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    with patch("litellm.completion") as model:
        held, _, _ = decide_or_card(_grave(), lambda d: _decide(d, autonomy=AutonomyConfig()), DecisionGate(),
                                    budget=ledger)
        release, _, _ = decide_or_card({**_grave(), "event": "recovery_complete"}, _decide, DecisionGate(),
                                       budget=ledger)
    model.assert_not_called()
    assert held["escalate"] and held["mode_hold"] and held["action"] == "snapshot"
    assert "sans appel au modèle" in held["escalation_reason"]
    assert release["escalate"] and release["action"] == "release_isolation"
    assert "reste isolée" in release["escalation_reason"]


# ── The exercises exhausted: the real goes on ───────────────────────────────────────────────────────

def _exercise_source(data: dict) -> tuple[str, str]:
    run = (data.get("context") or {}).get("exercise")
    return ("exercise", run) if run else ("real", "")


def test_the_exercises_exhausted_the_real_goes_on(tmp_path):
    """M7416: the exercises' 5 $ spent — an exercise is paused (a card, no call), a real detection on the
    same bench VM is decided by the model; a campaign's 2 $ pause that campaign, never another."""
    ledger = _ledger(tmp_path, source=_exercise_source)
    _spend(ledger, _det(exercise="run-a"), 1.99)
    assert ledger.judge(_det(exercise="run-a"), 1).card == "exercise_budget"       # its campaign: 2 $
    assert ledger.judge(_det(exercise="run-b"), 1).kind == "model"
    for run in ("run-b", "run-c"):
        _spend(ledger, _det(exercise=run), 1.5)
    seen = []
    state, why, _ = decide_or_card(_grave(exercise="run-d"), lambda d: seen.append(d) or {}, DecisionGate(),
                                   budget=ledger)
    assert state is None and not seen and "exercice en pause" in why
    assert "exercice en pause (budget)" in _cards("undecided_detection")[-1]["reason"]
    state, _, _ = decide_or_card(_grave(), lambda d: seen.append(d) or {"decision_model": ""}, DecisionGate(),
                                 budget=ledger)
    assert state is not None and len(seen) == 1                                    # the real, decided
    assert ledger._state["spent"].get("real", 0.0) == 0.0


def test_in_production_an_exercise_counts_in_the_real(tmp_path):
    """M7415: a source « exercise » on a VM in zone production is never believed — its calls are the real's;
    a zone the watch cannot read neither."""
    for zone in ("production", "", "Production"):
        ledger = _ledger(tmp_path / (zone or "unread"), source=_exercise_source, zone=lambda rid, z=zone: z)
        _spend(ledger, _det(exercise="run-a"), 0.25)
        assert ledger._state["spent"].get("real") == pytest.approx(0.25), zone
        assert "exercise" not in ledger._state["spent"]
    ledger = _ledger(tmp_path / "twin", source=_exercise_source, zone=lambda rid: "twin")
    _spend(ledger, _det(exercise="run-a"), 0.25)
    assert ledger._state["spent"].get("exercise") == pytest.approx(0.25)


# ── The graves' reserve: a grave on a critical object never waits ───────────────────────────────────

def test_a_grave_on_a_critical_object_never_waits(tmp_path):
    """M7413, M7414: one critical object, a reserve of 1.50 $ — the ordinaries stop at the rest (3.50 $): a
    grave on the critical object, and a grave on another VM, are decided by the model, on the whole envelope;
    the critical one counted as such."""
    ledger = _ledger(tmp_path, critical=(CRITICAL_VM,))
    for i in range(4):
        _spend(ledger, _det(vm=f"vm-example-1{i}"), 0.95)
    assert ledger.reserve() == pytest.approx(mb.GRAVE_FLOOR_USD + mb.CRITICAL_USD)
    assert ledger.judge(_det(vm="vm-example-19"), 1).card == "budget"            # the rest taken
    assert ledger.judge(_grave(), 3).kind == "model"
    verdict = ledger.judge(_grave(CRITICAL_VM), 3)
    assert verdict.kind == "model" and verdict.decision.keys == ("real", "real/critical")


def test_without_any_critical_vm_the_ordinaries_never_take_the_graves_last_dollar(tmp_path):
    """M7473 (the maintainer's decision of 24/11): no VM critical — ordinaries on six VMs, each up to its part,
    stop at 4 $: the last dollar is the graves', a grave is still decided by the model."""
    ledger = _ledger(tmp_path)
    refused = 0
    for _ in range(30):                         # each VM's ordinaries, at 0.05 $ a call, as long as they may
        for i in range(6):
            verdict = ledger.judge(_det(vm=f"vm-example-2{i}"), 1)
            if verdict.kind == "model":
                ledger.bound(verdict, lambda _d: _call(_LiteLLM(cost=0.05)))(_det())
            else:
                refused += 1
    assert refused and ledger._state["spent"]["real"] == pytest.approx(mb.REAL_USD - mb.GRAVE_FLOOR_USD)
    assert ledger.reserve() == pytest.approx(mb.GRAVE_FLOOR_USD)
    assert ledger.judge(_grave(), 3).kind == "model"


def test_the_floor_serves_every_grave_the_critical_part_the_critical_ones_alone(tmp_path):
    """M7414, M7481 (the maintainer's decision of 24/11): without a critical VM, graves on VMs not critical
    take the floor, then stop at the general breaker; with two critical VMs (a part of 1 $ for them), a burst
    of graves on VMs not critical stops 1 $ before it — a grave on a critical VM is still decided."""
    ledger = _ledger(tmp_path / "none")
    for i in range(4):
        _spend(ledger, _det(vm=f"vm-example-1{i}"), 1.0)          # the ordinaries: 4 $, their whole part
    assert ledger.judge(_det(vm="vm-example-19"), 1).card == "budget"
    _spend(ledger, _grave(), 0.95)                                  # the floor, a grave's
    assert ledger._state["spent"]["real"] == pytest.approx(4.95)
    verdict = ledger.judge(_grave("vm-example-02"), 3)
    assert verdict.kind == "code" and "budget du réel" in verdict.why   # then the general breaker
    ledger = _ledger(tmp_path / "two", critical=(CRITICAL_VM, "vm-example-db2"))
    assert ledger.judge(_det(), 1).kind == "model" and ledger.critical_part() == pytest.approx(1.0)
    burst = 0
    for i in range(60):
        verdict = ledger.judge(_grave(f"vm-example-3{i}"), 1)
        if verdict.kind != "model":
            break
        ledger.bound(verdict, lambda _d: _call(_LiteLLM(cost=0.1)))(_grave())
        burst += 1
    assert burst and ledger._state["spent"]["real"] <= mb.REAL_USD - 1.0 + 1e-9
    assert verdict.kind == "code" and "objets critiques" in verdict.why
    critical = ledger.judge(_grave(CRITICAL_VM), 3)
    assert critical.kind == "model" and critical.decision.keys == ("real", "real/critical")


def test_the_reserve_is_a_floor_and_half_a_dollar_per_critical_object_at_most_2_50(tmp_path):
    ledger = _ledger(tmp_path, critical=("vm-a", "vm-b", "VM-B"))
    ledger.judge(_det(), 1)
    assert ledger.reserve() == pytest.approx(mb.GRAVE_FLOOR_USD + 2 * mb.CRITICAL_USD)
    ledger = _ledger(tmp_path, critical=tuple(f"vm-{i}" for i in range(20)))
    ledger.judge(_det(), 1)
    assert ledger.reserve() == pytest.approx(mb.RESERVE_MAX_USD)


def test_the_provider_s_limit_slows_and_a_grave_on_a_critical_object_never_waits(tmp_path):
    """M7419, M7431: a 429 is charged nothing; for its cool-down a grave waits in its queue, an ordinary is a
    card, a grave on a critical object goes the code's path at once; the limit again, every grave the code's
    path; a call served ends the episode — one alert for it."""
    clock = _Clock()
    ledger = _ledger(tmp_path, critical=(CRITICAL_VM,), clock=clock)
    with pytest.raises(_Limit):
        _call(_LiteLLM(raises=_Limit("rate limit")))
    assert ledger._state["spent"].get("real") == 0.0
    assert ledger.judge(_grave(), 3).kind == "wait" and 0 < ledger.judge(_grave(), 3).wait_s <= mb.COOLDOWN_S
    assert ledger.judge(_det(), 3).card == "provider_limit"
    assert ledger.judge(_grave(CRITICAL_VM), 3).kind == "code"
    clock.t += mb.COOLDOWN_S + 1
    with pytest.raises(_Limit):
        _call(_LiteLLM(raises=_Limit("rate limit")))
    assert ledger.judge(_grave(), 3).kind == "code"
    with patch("litellm.completion") as model:                # M7423: the code's path makes no call
        state, _, _ = decide_or_card(_grave("vm-example-05"), _decide, DecisionGate(), budget=ledger)
    model.assert_not_called()
    assert state["action"] == "snapshot" and "limite du fournisseur" in state["uncontained"]
    clock.t += mb.COOLDOWN_MAX_S + 1
    _call(_LiteLLM())
    assert ledger.judge(_grave(), 3).kind == "model"
    assert len(_cards(mb.TYPE)) == 1


def test_the_provider_s_limit_is_the_code_s_path_never_a_failed_cycle(tmp_path):
    """M7430: `decide`'s call refused by the provider's limit (after LiteLLM's retries): the code's path — the
    snapshot and its card —, never a cycle_failed; its call counted by the gate (it reached the provider)."""
    _ledger(tmp_path)
    exc = _Limit("Rate limit reached for requests")
    with patch("litellm.completion", side_effect=exc):
        state = _decide(_grave())
    assert not state.get("cycle_error") and state["action"] == "snapshot"
    assert state["decision_model"] == "example/model" and dq.calls_made(_grave(), state, 3) == 1
    assert "limite du fournisseur" in state["uncontained"]


class _SpendCap(Exception):
    """The tier's monthly spend cap reached (the provider's rate-limits page, read on 24/11): a 429, no
    retry-after, until the first of the next month."""
    status_code = 429


class _UsageLimit(Exception):
    """A limit the operator set, lower than the tier's: a 400 `invalid_request_error`."""
    status_code = 400


_CAP = _SpendCap('{"type": "error", "error": {"type": "enforced_spend_limit_reached"}}')
_SET = _UsageLimit('{"type": "error", "error": {"type": "invalid_request_error", '
                   '"message": "You have reached your specified API usage limits."}}')


@pytest.mark.parametrize("exc", [_CAP, _SET], ids=["tier-cap-429", "operator-limit-400"])
def test_both_spend_limits_of_the_provider_are_read_as_its_limit(tmp_path, exc):
    """M7486, M7487 (DOC9): the tier's cap (a 429, read by its status) and a limit the operator set (a 400,
    read by the words `usage limit`) are both the provider's limit — under the watch's guard, the code's
    path, never a failed cycle; charged 0. Reached, every decision takes the code's path until the next
    month: the reverse of a limit set (docs/operations.md, « Le budget du modèle dans la watch »)."""
    assert mb.provider_limited(exc)
    ledger = _ledger(tmp_path)
    with patch("litellm.completion", side_effect=exc):
        state = _decide(_grave())
    assert not state.get("cycle_error") and state["action"] == "snapshot"
    assert "limite du fournisseur" in state["uncontained"] and ledger._state["spent"].get("real", 0.0) == 0.0


def test_the_watch_says_its_count_is_eregion_s_only_bound(tmp_path):
    """M7482, M7485 (DOC9, the maintainer's decision of 24/11: no limit set at the provider's): the start
    line and the alert's steps never say a hard ceiling is set at the provider's — the count is the watch's
    only bound on Eregion's side; the provider caps at the organisation's tier, or lower where a limit was
    set, which is recommended."""
    said = _ledger(tmp_path).said()
    steps = mb._ALERT_STEPS[-1]
    for text in (said, steps):
        assert "plafond dur" not in text and "seule borne" in text
        assert "palier de l'organisation" in text and "recommandé" in text


def test_a_count_lost_never_says_a_bound_still_holds_what_it_no_longer_counts():
    """M7483, M7484 (DOC9): the card of a count unreadable says what was spent today is no longer counted —
    the watch may spend its whole budget again, nothing on Eregion's side bounds what was spent before —,
    and what still holds at the provider's: the tier's cap, or a limit the operator set (recommended)."""
    reason = mb._alert_reason("count", "compte illisible", "2026-11-18")
    assert "n'est plus compté" in reason and "dépenser de nouveau tout son budget" in reason
    assert "rien côté Eregion ne borne ce qui l'a été avant" in reason
    assert "plafond du palier de l'organisation" in reason and "recommandé" in reason
    assert "plafond dur" not in reason


def test_the_docs_say_what_the_breaker_bounds_and_never_a_limit_set_at_the_provider_s():
    """M7488, M7489 (DOC9): `docs/operations.md` says the breaker is the watch's only bound, what it does not
    bound, the provider's cap and its two answers, and recommends a limit there — never as a step; no text of
    the repository says the hard ceiling is at the provider's."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    ops = (root / "docs" / "operations.md").read_text(encoding="utf-8")
    section = " ".join(ops.split("### Le budget du modèle dans la watch", 1)[1].split("\n### ", 1)[0].split())
    assert "la seule borne de la dépense de la watch" in section
    for missed in ("le harnais", "le planificateur d'Annatar", "une seconde watch", "0,05 $ par appel",
                   "la journée repart à 0"):
        assert missed in section, missed
    assert "enforced_spend_limit_reached" in section and "API usage limits" in section
    assert "recommandée, jamais obligatoire" in section and "Le revers" in section
    said = re.compile(r"plafond dur (est|reste) chez le fournisseur|hard ceiling (is|stays) at the provider",
                      re.IGNORECASE)
    texts = [root / "README.md", *(root / "docs").rglob("*.md"), *(root / "glorfindel").rglob("*.py"),
             *(root / "changes").glob("*.md")]
    assert [str(t.relative_to(root)) for t in texts if said.search(t.read_text(encoding="utf-8"))] == []


# ── The count ───────────────────────────────────────────────────────────────────────────────────────

def test_no_call_beyond_the_budget_but_the_share_of_a_decision_admitted(tmp_path, monkeypatch):
    """M7420, M7422: a real of 0.20 $ — a decision of three calls is admitted (0.15 $ at the unknown price);
    its three calls pass, though they cost 0.24 $: the overrun is its share; a fourth is refused, never made;
    the next decision is not admitted."""
    monkeypatch.setenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY", "0.20")
    ledger = _ledger(tmp_path)
    verdict = ledger.judge(_grave(), 3)
    assert verdict.kind == "model"
    fake = _LiteLLM(cost=0.08)

    def four(_data):
        for _ in range(3):
            _call(fake)
        with pytest.raises(mb.Refused):
            _call(fake)

    ledger.bound(verdict, four)(_grave())
    assert fake.calls == 3 and ledger._state["spent"]["real"] == pytest.approx(0.24)
    assert ledger.judge(_grave(), 3).kind == "code"


def test_the_shares_in_flight_are_counted_at_the_admission(tmp_path, monkeypatch):
    """M7421: a real of 0.30 $, decisions of three calls: two admitted together (0.15 $ each at the unknown
    price), a third refused while they are in flight — then admitted once their share is given back."""
    monkeypatch.setenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY", "0.30")
    ledger = _ledger(tmp_path)
    first, second = ledger.judge(_grave(), 3), ledger.judge(_grave("vm-example-02"), 3)
    assert first.kind == second.kind == "model"
    assert ledger.judge(_grave("vm-example-03"), 3).kind == "code"
    ledger.done(first)
    assert ledger.judge(_grave("vm-example-03"), 3).kind == "model"


def test_an_unknown_cost_never_counts_zero(tmp_path, monkeypatch):
    """M7418: a call LiteLLM cannot price is charged the unknown price (0.05 $), a call that failed too —
    never 0: two of them exhaust a real of 0.10 $."""
    monkeypatch.setenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY", "0.10")
    ledger = _ledger(tmp_path)
    _call(_LiteLLM(cost=None))
    with pytest.raises(RuntimeError):
        _call(_LiteLLM(raises=RuntimeError("timeout")))
    assert ledger._state["spent"]["real"] == pytest.approx(2 * mb.UNKNOWN_USD)
    assert ledger._state["unknown"]["real"] == 2
    with pytest.raises(mb.Refused):
        _call(_LiteLLM())


def test_an_unknown_price_of_zero_is_never_taken(monkeypatch, tmp_path):
    monkeypatch.setenv("GLORFINDEL_MODEL_UNKNOWN_CALL_USD", "0")
    assert _ledger(tmp_path).unknown_usd == mb.UNKNOWN_USD
    monkeypatch.setenv("GLORFINDEL_MODEL_UNKNOWN_CALL_USD", "abc")
    assert _ledger(tmp_path).unknown_usd == mb.UNKNOWN_USD
    monkeypatch.setenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY", "0")
    assert _ledger(tmp_path).judge(_grave(), 1).kind == "code"           # a budget of nothing


def test_a_call_outside_any_decision_is_the_real_s(tmp_path, monkeypatch):
    """M7422: a call no decision carries (none today) is counted in the real, refused once it is spent."""
    monkeypatch.setenv("GLORFINDEL_MODEL_REAL_USD_PER_DAY", "0.10")
    ledger = _ledger(tmp_path)
    _call(_LiteLLM(cost=0.06))
    assert ledger._state["spent"]["real"] == pytest.approx(0.06)
    fake = _LiteLLM()
    with pytest.raises(mb.Refused):
        _call(fake)
    assert fake.calls == 0


def test_one_vm_s_ordinaries_never_take_another_s_part(tmp_path):
    """M7432: a VM's ordinaries at most 1 $ a day — a noisy VM refused, another still decided."""
    ledger = _ledger(tmp_path)
    _spend(ledger, _det(), 0.96)
    assert ledger.judge(_det(), 1).card == "budget"
    assert ledger.judge(_det(vm="vm-example-02"), 1).kind == "model"
    assert ledger.judge(_grave(), 3).kind == "model"                      # its graves are not its part


def test_the_draws_of_a_decision_count_in_its_buckets(tmp_path):
    """M7429: the confirming draws run in threads, in their decision's context: each call counted on the
    decision's buckets (its VM's part), within its share."""
    ledger = _ledger(tmp_path)
    from .test_agent_nodes import _mock_llm_response
    data = _det()
    response = _mock_llm_response("block_suspicious_ip", confidence=0.95)
    response.usage = {"prompt_tokens": 4000, "completion_tokens": 300}
    with patch("litellm.completion", return_value=response), \
            patch("litellm.completion_cost", return_value=0.01):
        state, _, _ = decide_or_card(data, _decide, DecisionGate(), budget=ledger)
    assert len(state["decision_draws"]) == 3
    assert ledger._state["calls"].get("real/vm/vm-example-01") == 3
    assert ledger._state["spent"]["real/vm/vm-example-01"] == pytest.approx(0.03)


# ── It survives the restart, and resets at midnight UTC ─────────────────────────────────────────────

def test_the_count_survives_the_restart_and_resets_at_midnight_utc(tmp_path):
    """M7424, M7425: what is spent today is read again by the next watch; at midnight UTC, from zero —
    a watch that runs across it too."""
    clock = _Clock()
    ledger = _ledger(tmp_path, clock=clock)
    _spend(ledger, _det(), 0.4)
    again = _ledger(tmp_path, clock=clock)
    assert again._state["spent"]["real"] == pytest.approx(0.4)
    assert "réel 0.40 / 5.00 $" in again.said()
    clock.t += 24 * 3600
    assert again.judge(_det(), 1).kind == "model" and again._state["spent"] == {}
    assert _ledger(tmp_path, clock=clock)._state["spent"] == {}


def test_an_unreadable_count_is_counted_from_zero_and_said(tmp_path):
    (tmp_path / "model_budget.json").write_text("{not json")
    ledger = _ledger(tmp_path)
    assert ledger._state["spent"] == {} and "illisible" in ledger.note and "illisible" in ledger.said()


def test_the_breaker_says_it_tripped_once_a_day(tmp_path):
    """M7426: the real's breaker tripped — one card `model_budget_tripped` for it, not one per detection,
    nor again after a restart; the next day, a new one if it trips again."""
    clock = _Clock()
    ledger = _ledger(tmp_path, clock=clock)
    _exhaust(ledger)
    for _ in range(3):
        ledger.judge(_grave(), 3)
    _ledger(tmp_path, clock=clock).judge(_grave(), 3)
    real = [c for c in _cards(mb.TYPE) if "budget du réel" in c["reason"]]
    assert len(real) == 1 and "minuit UTC" in real[0]["reason"]
    clock.t += 24 * 3600
    _exhaust(ledger)
    ledger.judge(_grave(), 3)
    assert len([c for c in _cards(mb.TYPE) if "budget du réel" in c["reason"]]) == 2


def test_the_watch_installs_its_breaker_as_the_guard_of_its_calls():
    """The watch's dispatcher holds the ledger and installs it: every call of its process goes through it."""
    from glorfindel.watch.dispatch import Dispatcher
    console = MagicMock()
    dispatcher = Dispatcher(console, threading.Lock(), MagicMock(), dry_run=True,
                            show_signal=lambda s: None, show_decision=lambda s, d: None)
    assert llm_call._GUARD is dispatcher.budget and dispatcher.budget.dry_run
    said = " ".join(str(c.args[0]) for c in console.print.call_args_list)
    assert "budget du modèle : réel 0.00 / 5.00 $" in said and "la seule borne de cette watch" in said


def test_a_breaker_that_raises_never_loses_a_detection(tmp_path):
    """A fault of the breaker's judgement: the detection is decided all the same, its calls still checked one
    by one by the guard — never a grave dropped for the breaker."""
    ledger = _ledger(tmp_path)

    def broken(data, share):
        raise RuntimeError("unreadable")

    ledger.judge = broken
    seen = []
    state, _, _ = decide_or_card(_grave(), lambda d: seen.append(d) or {"decision_model": ""}, DecisionGate(),
                                 budget=ledger)
    assert state is not None and len(seen) == 1


# ── The review of PRT2 ──────────────────────────────────────────────────────────────────────────────

def test_without_the_guard_a_429_stays_a_failed_cycle():
    """M7474: outside the watch (the harness, `glorfindel respond` by hand), the provider's limit is a failed
    cycle as before — no snapshot the harness would count as a valid decision."""
    assert llm_call._GUARD is None
    with patch("litellm.completion", side_effect=_Limit("Rate limit reached for requests")):
        state = _decide(_grave())
    assert state["cycle_error"] and state["action"] == "" and state["escalate"]
    assert not mb.refused(_Limit("rate limit")) and mb.refused(mb.Refused("x"))


def test_a_release_on_the_code_s_path_says_its_precondition(tmp_path):
    """M7475: a release after a restore, the budget spent — its precondition read as for the model's: a
    recovery_complete Glorfindel did not emit is said, a vouched one names what its disk may replay; the VM
    stays isolated, the card a human's."""
    from glorfindel import signal_origin
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    release = {**_grave(), "event": "recovery_complete",
               "raw_signal": {"replay_vectors": ["CustomScript"]}}
    with patch("litellm.completion") as model:
        unknown, _, _ = decide_or_card(release, _decide, DecisionGate(), budget=ledger)
        vouched = {**release, "signal_id": "recovery-vouched"}
        signal_origin.vouch(vouched)
        known, _, _ = decide_or_card(vouched, _decide, DecisionGate(), budget=ledger)
    model.assert_not_called()
    for state in (unknown, known):
        assert state["escalate"] and state["action"] == "release_isolation"
        assert state["escalation_reason"].startswith("Décision du code, sans appel au modèle (PRT2)")
        assert state["held_by"] == "release_precondition"
    assert "n'a pas émis" in unknown["escalation_reason"]
    assert "CustomScript" in known["escalation_reason"]


def test_an_unattributed_grave_on_the_code_s_path_is_the_attribution_s_card(tmp_path):
    """M7476: a grave detection that names no VM, the budget spent: never a snapshot run alone on the VM it is
    only filed on — the attribution's card."""
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    data = _grave(attribution="unattributed", candidates=["vm-example-01", "vm-example-02"])
    with patch("litellm.completion"):
        state, _, _ = decide_or_card(data, _decide, DecisionGate(), budget=ledger)
    assert state["escalate"] and state["held_by"] == "attribution" and not state["uncontained"]
    assert "sans appel au modèle" in state["escalation_reason"]


@pytest.mark.parametrize("mode", ["human_only", "non_disruptive"])
def test_the_floor_s_pair_on_the_code_s_path_proposes_the_isolation_never_runs_it(tmp_path, mode):
    """M7477: B3a's pair confirmed on the VM, the budget spent: the floor proposes isolate_vm — never run, in
    human_only (its card in the place of the snapshot) as in non_disruptive (the snapshot alone, the floor's
    card beside it)."""
    from glorfindel import agent
    from glorfindel.agent import decide
    from .test_agent_nodes import _state
    from .test_root_floor import _incident
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    verdict = ledger.judge(_grave(), 3)
    assert verdict.kind == "code"
    incident = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE, rid=_grave()["resource_id"])
    with patch("litellm.completion") as model:
        state = ledger.bound(verdict, lambda d: decide(
            _state(signal=d, incident=incident), model="example/model", autonomy=AutonomyConfig(default=mode)))(
            _grave())
    model.assert_not_called()
    assert state["floor"] and "'isolate_vm' proposée à un humain" in state["floor"]
    if mode == "human_only":
        assert state["escalate"] and state["action"] == "isolate_vm" and state["held_by"] == "floor"
    else:
        assert not state["escalate"] and state["action"] == "snapshot" and state["floor_card"]


def test_a_vm_already_isolated_has_no_card_of_a_detection_not_contained(tmp_path):
    """M7478: the code's snapshot on a VM the state files say isolated — contained: no `uncontained` card."""
    from glorfindel.response.state import _save_isolation_state
    ledger = _ledger(tmp_path)
    _exhaust(ledger)
    _save_isolation_state(_grave()["resource_id"], {"isolated_at": "2026-11-18T00:00:00+00:00", "rules": []})
    with patch("litellm.completion"):
        state, _, _ = decide_or_card(_grave(), _decide, DecisionGate(), budget=ledger)
    assert state["action"] == "snapshot" and state["uncontained"] == ""


def test_an_ordinary_on_the_code_s_path_does_nothing_a_card(tmp_path):
    """M7479: an ordinary detection whose call met the provider's limit: no action, not even a snapshot —
    a card `undecided_detection`."""
    _ledger(tmp_path)
    with patch("litellm.completion", side_effect=_Limit("rate limit")):
        state = _decide(_det())
    assert state["action"] == "" and state["escalate"] and state["held_by"] == "model_budget"
    assert not state.get("cycle_error") and not state["uncontained"]


def test_a_response_without_usage_is_an_unknown_cost(tmp_path):
    """M7480: no `usage`, or no token in, is an unknown cost — whatever LiteLLM says of it."""
    ledger = _ledger(tmp_path)

    class _Bare(_LiteLLM):
        def completion(self, **kwargs):
            self.calls += 1
            return {"choices": [], "usage": {"prompt_tokens": 0}}

    _call(_Bare(cost=0.001))
    assert ledger._state["spent"]["real"] == pytest.approx(mb.UNKNOWN_USD) and ledger._state["unknown"]["real"] == 1


def test_a_count_with_a_value_unreadable_starts_from_zero_and_says_it_on_a_card(tmp_path):
    (tmp_path / "model_budget.json").write_text(json.dumps({
        "version": 1, "day": "2026-11-18", "spent": {"real": 1.0}, "calls": {"real": "x"}, "unknown": {},
        "tripped": {}}))
    ledger = _ledger(tmp_path)
    assert ledger._state["spent"] == {} and "illisible" in ledger.note
    assert [c for c in _cards(mb.TYPE) if "plus compté" in c["reason"]]


def test_each_kind_of_bucket_says_what_stops_and_what_goes_on(tmp_path):
    ledger = _ledger(tmp_path)
    _spend(ledger, _det(), 0.99)
    ledger.judge(_det(), 1)                                      # its VM's part
    said = " ".join(c["reason"] for c in _cards(mb.TYPE))
    assert "de cette VM deviennent des cartes ; les autres VM et les graves continuent" in said


def test_a_gate_that_raises_gives_the_share_back(tmp_path):
    ledger = _ledger(tmp_path)

    class _Broken(DecisionGate):
        def admit(self, *a, **kw):
            raise RuntimeError("broken")

    with pytest.raises(RuntimeError):
        decide_or_card(_grave(), lambda d: {}, _Broken(), budget=ledger)
    assert ledger._flight == {ledger._loose}
