"""SEC-A2 (#631; audit of 06/11, V-03 and V-13): the watch's decision queue, bounded.

A local account on a watched VM writes lines with new values each pass: each one was a detection,
a decision, a call to the model, in a FIFO per VM without a ceiling — and a real ransomware
detection waited behind them. Here: a forged burst never delays a grave detection; the queue is
bounded, and what leaves it is said and counted; one decision of the model per VM, rule and gravity
in a window, a deduplicated detection costs no call; a ceiling of calls per minute holds, and
beyond it a card, never an action; the older lines of a pass are named on a card, none marked sent
unsaid, and the model sees the newest as before.

Every identifier is made up (repository public): documentation addresses (RFC 5737), 00000000-…
GUIDs, example names. No Azure, no model: `respond` is a fake that counts — the graph, and the
model behind it, is reached through it alone.
"""
from __future__ import annotations

import json
import time

import pytest

from glorfindel import decision_queue as dq
from glorfindel import escalations
from glorfindel.decision_queue import DecisionGate, DecisionQueue, decide_or_card
from glorfindel.detection_rules import DetectionRule, RulePoller

SUB = "00000000-0000-0000-0000-0000000000cc"


def _vm(name: str = "vm-example-01") -> str:
    return f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/{name}"


def _det(rule: str = "ssh-brute-force", ttp: str = "T1110.001", *, vm: str | None = None,
         severity: str = "high", row: dict | None = None, **ctx) -> dict:
    """A detection as the RulePoller dispatches it."""
    return {"signal_id": f"rule-{rule}-{abs(hash((rule, json.dumps(row, sort_keys=True, default=str)))):08x}",
            "event": "detection", "ttp": ttp, "severity": severity, "resource_id": vm or _vm(),
            "resource_type": "vm", "provider": "azure", "timestamp": "2026-11-06T10:00:00+00:00",
            "context": {"rule_name": rule, "run_id": f"watch-{rule}-20261106T100000Z",
                        "asset_name": "vm-example-01", "attribution": "asset", **ctx},
            "raw_signal": {"detection_source": "azure_monitor", "first_result_row": row or {}}}


def _ssh(i: int, **kw) -> dict:
    return _det(row={"Computer": "vm-example-01", "SourceIP": f"203.0.113.{i}", "FailedAttempts": 10}, **kw)


def _ransomware(**kw) -> dict:
    return _det("ransomware-disk-write", "T1486", row={"Computer": "vm-example-01", "MaxWrite": 80.0}, **kw)


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class _Respond:
    """The graph: counts what reached it (the model is behind it, nowhere else)."""

    def __init__(self, draws: int = 0) -> None:
        self.seen: list[dict] = []
        self.draws = draws

    def __call__(self, data: dict) -> dict:
        self.seen.append(data)
        return {"signal": data, "decision_draws": [{}] * self.draws}


def _cards() -> list[dict]:
    if not escalations._STORE.exists():
        return []
    return [json.loads(line) for line in escalations._STORE.read_text().splitlines() if line.strip()]


@pytest.fixture(autouse=True)
def _fresh_cards():
    dq._SEEN.clear()
    yield
    dq._SEEN.clear()


def _drain(q: DecisionQueue, gate: DecisionGate, respond) -> list[str]:
    """The worker: every item, in the queue's order — (outcome, rule) of each."""
    out = []
    while q.qsize():
        data, _sig, _ch = q.get()
        state, _why = decide_or_card(data, respond, gate)
        out.append(("decided" if state is not None else "card", data["context"]["rule_name"]))
    return out


# ── A forged burst never delays a grave detection ───────────────────────────────────────────────

def test_a_forged_burst_never_delays_a_grave_detection():
    q, gate, respond = DecisionQueue(), DecisionGate(clock=_Clock()), _Respond()
    for i in range(40):                       # twenty new addresses a pass, two passes
        q.put((_ssh(i), None, False))
    q.put((_ransomware(), None, False))      # the real one, last in
    order = _drain(q, gate, respond)
    assert order[0] == ("decided", "ransomware-disk-write")
    # And the burst costs one decision of the model, the rest is a card.
    assert [r["context"]["rule_name"] for r in respond.seen] == ["ransomware-disk-write", "ssh-brute-force"]


def test_a_burst_of_low_detections_never_uses_the_room_of_a_grave_one():
    """The ceiling is for the whole watch: twenty VMs under the burst use the low class's room;
    a ransomware detection still calls the model."""
    gate, respond = DecisionGate(clock=_Clock()), _Respond()
    for i in range(20):
        decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), respond, gate)
    assert len(respond.seen) == dq.LOW_CALLS_PER_MIN
    state, why = decide_or_card(_ransomware(), respond, gate)
    assert state is not None and why == ""


def test_gravity_reads_the_severity_then_the_technique():
    assert dq.gravity(_ssh(1, severity="critical")) == dq.CRITICAL
    assert dq.gravity(_ransomware()) == dq.GRAVE
    assert dq.gravity(_det(ttp="T1041")) == dq.GRAVE
    assert dq.gravity(_ssh(1)) == dq.LOW


# ── The queue is bounded: what leaves it is said and counted ────────────────────────────────────

def test_the_queue_is_bounded_and_what_leaves_it_is_a_card():
    left: list = []
    q = DecisionQueue(on_drop=lambda item, why: (left.append(why),
                                                  dq.record_undecided(item[0], "full", why)))
    for i in range(dq.QUEUE_MAX + 7):
        q.put((_ssh(i), None, False))
    assert q.qsize() == dq.QUEUE_MAX and q.dropped == 7 and len(left) == 7
    assert all(f"{dq.QUEUE_MAX} détections" in why for why in left)
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert card["occurrences"] == 7 and card["action"] == ""
    assert "7 file pleine" in card["reason"] and "203.0.113.56" in card["reason"]


def test_a_grave_detection_enters_a_full_queue_the_newest_low_one_leaves():
    left: list = []
    q = DecisionQueue(maxsize=3, on_drop=lambda item, why: left.append(item[0]))
    for i in range(3):
        q.put((_ssh(i), None, False))
    assert q.put((_ransomware(), None, False)) is True
    assert [d["raw_signal"]["first_result_row"]["SourceIP"] for d in left] == ["203.0.113.2"]
    assert q.put((_ssh(9), None, False)) is False          # no graver: it is the one that leaves
    assert left[-1]["raw_signal"]["first_result_row"]["SourceIP"] == "203.0.113.9"
    assert q.get()[0]["context"]["rule_name"] == "ransomware-disk-write"


# ── One decision per VM, rule and gravity in a window: a deduplicated detection costs no call ─

def test_a_deduplicated_detection_costs_no_call_and_is_named_on_a_card():
    clock, respond = _Clock(), _Respond()
    gate = DecisionGate(clock=clock)
    decide_or_card(_ssh(1), respond, gate)
    clock.t += 30
    state, why = decide_or_card(_ssh(2), respond, gate)
    assert state is None and "dédoublonnée" in why
    assert len(respond.seen) == 1
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert card["action"] == "" and card["rule_name"] == "ssh-brute-force"
    assert "203.0.113.2" in card["reason"] and "1 dédoublonnées" in card["reason"]


def test_the_dedup_holds_one_rule_one_vm_one_gravity_one_window():
    clock, respond = _Clock(), _Respond()
    gate = DecisionGate(clock=clock)
    decide_or_card(_ssh(1), respond, gate)
    decide_or_card(_ssh(2, vm=_vm("vm-example-02")), respond, gate)                 # another VM
    decide_or_card(_det("sudo-privilege-escalation", "T1548.003",
                        row={"SyslogMessage": "x"}), respond, gate)                  # another rule
    decide_or_card(_ssh(3, severity="critical"), respond, gate)                     # graver: COR1
    assert len(respond.seen) == 4
    clock.t += dq.DEDUP_WINDOW_S + 61
    decide_or_card(_ssh(4), respond, gate)                                          # window past
    assert len(respond.seen) == 5


def test_a_detection_of_an_injector_is_never_deduplicated():
    """Only the RulePoller's (its `watch-` run): an exercise's detection is its run's measure."""
    respond, gate = _Respond(), DecisionGate(clock=_Clock())
    decide_or_card(_ssh(1), respond, gate)
    decide_or_card(_ssh(2, run_id="20261106T100000Z_ab12"), respond, gate)
    assert len(respond.seen) == 2


def test_the_control_plane_is_never_held():
    """Decided by the code (AL1, C2), never by the model: neither dedup nor ceiling."""
    respond, gate = _Respond(), DecisionGate(clock=_Clock(), per_min=0, low_per_min=0)
    for i in range(3):
        decide_or_card(_det("nsg-change-outside-glorfindel", "T1562.007", plane="control",
                            row={"OperationNameValue": "x", "CorrelationId": str(i)}), respond, gate)
    assert len(respond.seen) == 3


# ── A ceiling of calls per minute: beyond, a card, never an action ──────────────────────────────

def test_the_ceiling_of_calls_holds_and_beyond_it_a_card_never_an_action():
    clock, respond = _Clock(), _Respond()
    gate = DecisionGate(clock=clock)
    rules = [f"rule-{i}" for i in range(dq.MODEL_CALLS_PER_MIN + 3)]
    for i, rule in enumerate(rules):
        decide_or_card(_det(rule, "T1486", row={"MaxWrite": 60.0 + i}), respond, gate)
    assert len(respond.seen) == dq.MODEL_CALLS_PER_MIN
    cards = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert len(cards) == 3 and all(c["action"] == "" and not c["action_params"] for c in cards)
    assert all("plafond des appels au modèle" in c["reason"] for c in cards)
    clock.t += 61
    decide_or_card(_det("rule-late", "T1486", row={"MaxWrite": 90.0}), respond, gate)
    assert len(respond.seen) == dq.MODEL_CALLS_PER_MIN + 1


def test_the_ceiling_counts_the_draws_of_a_decision():
    """A decision that drew three times (D-1, a disruptive action about to run alone) is three
    calls."""
    clock, respond = _Clock(), _Respond(draws=3)
    gate = DecisionGate(clock=clock, per_min=4, low_per_min=4)
    decide_or_card(_det("rule-a", row={"x": "a"}), respond, gate)
    decide_or_card(_det("rule-b", row={"x": "b"}), respond, gate)
    decide_or_card(_det("rule-c", row={"x": "c"}), respond, gate)
    assert len(respond.seen) == 2


# ── V-13: the older lines of a pass named on a card, the model sees the newest as before ────────

class _Det:
    def __init__(self, rows):
        self.rows = rows

    def run_query(self, query, timespan=None):
        return [dict(r) for r in self.rows]


class _Registry:
    def for_backend(self, _name):
        return [type("A", (), {"name": "vm-example-01", "resource_id": _vm()})()]


def test_a_decoy_line_after_the_real_one_never_hides_it():
    rule = DetectionRule(name="t1053-003-cron-crontab-replace", source="azure_monitor", workspace_id="ws",
                         query="Syslog | where TimeGenerated > ago(10m)", ttp="T1053.003", resource_id="",
                         interval_s=30, auto_apply=True, monitoring_backend_name="law")
    real = {"Computer": "vm-example-01", "_ResourceId": _vm(), "TimeGenerated": "2026-11-06T10:00:00Z",
            "SyslogMessage": "(root) REPLACE (root) — /tmp/.x/payload"}
    decoy = {"Computer": "vm-example-01", "_ResourceId": _vm(), "TimeGenerated": "2026-11-06T10:00:01Z",
             "SyslogMessage": "(alice) REPLACE (alice)"}
    sent: list = []
    p = RulePoller([rule], sent.append)
    p._detector = lambda _r: _Det([real, decoy])
    p._registry = _Registry()
    p.poll_once(rule)
    q, gate, respond = DecisionQueue(), DecisionGate(clock=_Clock()), _Respond()
    for s in sent:
        q.put((s, None, False))
    _drain(q, gate, respond)
    # The model sees the newest line, as it is: nothing added to what it reads.
    [seen] = respond.seen
    assert seen["raw_signal"]["first_result_row"] == decoy
    assert "card_only" not in seen["context"]
    # The real one, marked sent, is named on a card — never said nowhere.
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert "/tmp/.x/payload" in card["reason"] and "même passe" in card["reason"]
    assert card["rule_name"] == "t1053-003-cron-crontab-replace"


def test_the_lines_of_a_pass_named_beside_the_newest_never_call_the_model():
    """Even when the newest is past the ceiling and the room comes back: the card-only signal is
    never the model's."""
    respond = _Respond()
    gate = DecisionGate(clock=_Clock())
    named = _det("t1136-001-local-account-creation-linux-v1", "T1136.001",
                 row={"TimeGenerated": "2026-11-06T10:00:00Z", "SyslogMessage": "useradd x"},
                 card_only="même passe")
    state, why = decide_or_card(named, respond, gate)
    assert state is None and respond.seen == [] and why == "même passe"


def test_a_pass_of_many_lines_names_them_on_the_card_and_counts_them():
    rows = [{"Computer": "vm-example-01", "_ResourceId": _vm(), "TimeGenerated": f"2026-11-06T10:{i:02d}:00Z",
             "SyslogMessage": f"useradd -m forged{i}"} for i in range(30)]
    rule = DetectionRule(name="t1136-001-local-account-creation-linux-v1", source="azure_monitor",
                         workspace_id="ws", query="Syslog", ttp="T1136.001", resource_id="", interval_s=30,
                         auto_apply=True, monitoring_backend_name="law")
    sent: list = []
    p = RulePoller([rule], sent.append)
    p._detector = lambda _r: _Det(rows)
    p._registry = _Registry()
    p.poll_once(rule)
    assert len(sent) == 2
    decide_or_card(sent[1], _Respond(), DecisionGate(clock=_Clock()))
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert "forged28" in card["reason"] and "29 dédoublonnées" in card["reason"]
    assert "… et 9 ligne(s) de plus" in card["reason"]


# ── The watch: its workers take their detections through the queue and the gate ───────────────

def test_the_watch_decides_through_the_gate_and_says_a_card(tmp_path, monkeypatch):
    """The watch (dry-run), three attacks on three VMs, a ceiling of one call a minute: one
    decision reaches the graph, the two others are said without a decision of the model."""
    from .test_signal_origin import _line, _run_watch
    monkeypatch.setattr(dq, "MODEL_CALLS_PER_MIN", 1)
    lines = [_line("attack_started", signal_id=f"a{i}", resource_id=_vm(f"vm-example-{i:02d}"),
                   raw_signal={"attack_time": time.time() - 60}) for i in range(3)]
    responded, _polled, out = _run_watch(tmp_path, monkeypatch, lines, expect=1, slow_respond=0.3)
    assert len(responded) == 1, out
    flat = " ".join(out.split())
    assert flat.count("Non décidée par le modèle") == 2 and "plafond des appels au modèle" in flat
