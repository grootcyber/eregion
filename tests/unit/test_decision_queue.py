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
import threading
import time

import pytest

from glorfindel import decision_queue as dq
from glorfindel import escalations
from glorfindel.config import DECISION_DRAWS
from glorfindel.decision_queue import DecisionGate, DecisionQueue, decide_or_card
from glorfindel.detection_rules import DetectionRule, RulePoller

SUB = "00000000-0000-0000-0000-0000000000cc"
# PRT1: one call each (human_only), the low decisions a minute admits — each reserves the draws of
# D-1 at its admission, and the last places of the low class cannot hold a reserve of three.
HUMAN_ONLY_LOWS = dq.LOW_CALLS_PER_MIN - DECISION_DRAWS + 1


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
    """The graph: counts what reached it (the model is behind it, nowhere else). By default each
    decision puts a card before a human (`escalate`), as in human_only — one call to the model
    (`decision_model`, as `decide` sets it), or `draws` (D-1)."""

    def __init__(self, draws: int = 0, **state) -> None:
        self.seen: list[dict] = []
        self.draws = draws
        self.state = {"escalate": True, "action": "isolate_vm", "decision_model": "example/model", **state}

    def __call__(self, data: dict) -> dict:
        self.seen.append(data)
        return {"signal": data, "decision_draws": [{}] * self.draws, **self.state}


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
        state, _why, _wait = decide_or_card(data, respond, gate)
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
    a ransomware detection still calls the model. PRT1: each low one reserves its draws — one call
    made each, `HUMAN_ONLY_LOWS` of them in the minute."""
    clock = _Clock()
    gate, respond = DecisionGate(clock=clock), _Respond()
    for i in range(20):
        decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), respond, gate)
    assert len(respond.seen) == HUMAN_ONLY_LOWS
    assert _counted(gate, clock)[1] <= dq.LOW_CALLS_PER_MIN
    state, why, _wait = decide_or_card(_ransomware(), respond, gate)
    assert state is not None and why == ""


def test_gravity_reads_the_severity_then_the_technique():
    assert dq.gravity(_ssh(1, severity="critical")) == dq.CRITICAL
    assert dq.gravity(_ransomware()) == dq.GRAVE
    assert dq.gravity(_det(ttp="T1041")) == dq.GRAVE
    assert dq.gravity(_ssh(1)) == dq.LOW


def _from_the_channel(ttp: str, severity: str = "critical") -> dict:
    """A line of the runs/ channel as the watch admits it (signal_origin.admit), then resolved by
    its rule: its gravity as the injector wrote it."""
    from glorfindel import signal_origin
    line = {"event": "attack_started", "signal_id": "20261106T100000Z_ab12_attack_started",
            "resource_id": _vm(), "resource_type": "vm", "ttp": ttp, "severity": severity,
            "timestamp": "2026-11-06T10:00:00+00:00",
            "raw_signal": {"attack_time": time.time() - 60},
            "context": {"run_id": "20261106T100000Z_ab12", "scenario": "x"}}
    admitted = signal_origin.admit(line, known={ttp})
    assert admitted.signal is not None, admitted.refused
    return {**admitted.signal, "event": "detection",
            "raw_signal": {**admitted.signal["raw_signal"], "detected_data": {"Computer": "vm-example-01"}}}


@pytest.mark.parametrize("ttp,cls", [("T1110.001", dq.LOW), ("T1486", dq.GRAVE)])
def test_a_line_of_the_channel_never_says_critical(ttp, cls):
    """SEC-E (V-08): the gravity a line of runs/ writes is kept as it is (the model reads it as
    before), never read by the queue: its class is its technique's — never the critical one, which
    passed before the grave ones and chased them out of a full queue."""
    data = _from_the_channel(ttp)
    assert data["severity"] == "critical"
    assert dq.gravity(data) == cls
    q = DecisionQueue(maxsize=1)
    q.put((_ransomware(), None, False))
    assert q.put((data, None, False)) is False             # a full queue keeps the grave one


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
    state, why, _wait = decide_or_card(_ssh(2), respond, gate)
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
    rules = [f"rule-{i}" for i in range(dq.LOW_CALLS_PER_MIN + 3)]
    for i, rule in enumerate(rules):
        decide_or_card(_det(rule, row={"SourceIP": f"203.0.113.{i}"}), respond, gate)
    assert len(respond.seen) == HUMAN_ONLY_LOWS                     # PRT1: each reserved its draws
    cards = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert len(cards) == len(rules) - HUMAN_ONLY_LOWS
    assert all(c["action"] == "" and not c["action_params"] for c in cards)
    assert all("plafond des appels au modèle" in c["reason"] for c in cards)
    clock.t += 61
    decide_or_card(_det("rule-late", row={"SourceIP": "203.0.113.99"}), respond, gate)
    assert len(respond.seen) == HUMAN_ONLY_LOWS + 1


def test_a_grave_detection_past_the_ceiling_waits_and_is_decided_when_the_room_comes_back():
    """Constat 2: a grave one past the ceiling is never a card — it waits in its queue."""
    clock, respond = _Clock(), _Respond()
    gate = DecisionGate(clock=clock, per_min=2, low_per_min=1)
    decide_or_card(_det("rule-a", "T1486", row={"x": "a"}), respond, gate)
    decide_or_card(_det("rule-b", "T1486", row={"x": "b"}), respond, gate)
    late = _det("rule-c", "T1486", row={"x": "c"})
    state, why, wait_s = decide_or_card(late, respond, gate)
    assert state is None and wait_s > 0 and "plafond" in why
    assert not [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    clock.t += 61
    state, _why, wait_s = decide_or_card(late, respond, gate)
    assert state is not None and wait_s == 0 and len(respond.seen) == 3


def test_six_low_decisions_of_three_draws_never_take_the_room_of_a_grave_one():
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    low = _Respond(draws=3)
    for i in range(6):
        decide_or_card(_det(f"rule-{i}", row={"x": str(i)}), low, gate)
    state, _why, wait_s = decide_or_card(_ransomware(), _Respond(), gate)
    assert state is not None and wait_s == 0
    # Even when the low class's draws filled the minute, the grave ones keep their own room.
    gate = DecisionGate(clock=clock, per_min=3, low_per_min=2)
    decide_or_card(_det("rule-x", row={"x": "x"}), low, gate)          # one decision, three calls
    state, _why, wait_s = decide_or_card(_ransomware(), _Respond(), gate)
    assert state is not None and wait_s == 0


def test_a_grave_detection_put_back_lets_the_others_through_until_its_moment():
    q = DecisionQueue()
    q.put_back((_ransomware(), None, False), 0.3)
    q.put((_ssh(1), None, False))
    assert q.get(timeout=1)[0]["context"]["rule_name"] == "ssh-brute-force"
    assert q.get(timeout=1)[0]["context"]["rule_name"] == "ransomware-disk-write"


# ── A compromise (COR1, B3a) is never lost to the bounds ───────────────────────────────────────

def _compromise(ip: str, **kw) -> dict:
    return _det(severity="critical", row={"Computer": "vm-example-01", "SourceIP": ip, "FailedAttempts": 12,
                                          "Correlation": "ssh-login-after-brute-force"}, **kw)


def _sudo(i: int = 0, **kw) -> dict:
    return _det("sudo-privilege-escalation", "T1548.003",
                row={"TimeGenerated": f"2026-11-06T10:00:0{i}Z", "SyslogMessage": f"x : USER=root ; COMMAND=/bin/c{i}"},
                **kw)


# ── SEC-E (#846; audit of 13/11, V-02; #644, points 1 and 2): the critical class, bounded ─────

def test_a_compromise_counts_as_a_grave_one_in_the_ceiling():
    """A critical detection (COR1) is no longer outside the ceiling: it takes the grave class's
    room, reserved but finite, and waits in its queue beyond it — never a card, never unheld."""
    clock, respond = _Clock(), _Respond(escalate=False, action="")      # judged « nothing »: no window
    gate = DecisionGate(clock=clock, per_min=2, low_per_min=1)
    for ip in ("198.51.100.7", "198.51.100.8"):
        state, _why, wait_s = decide_or_card(_compromise(ip), respond, gate)
        assert state is not None and wait_s == 0
    state, why, wait_s = decide_or_card(_compromise("198.51.100.9"), respond, gate)
    assert state is None and wait_s > 0 and "plafond" in why and "critique" in why
    assert not [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    clock.t += 61
    state, _why, wait_s = decide_or_card(_compromise("198.51.100.9"), respond, gate)
    assert state is not None and wait_s == 0


def test_a_compromise_is_deduplicated_by_vm_and_rule_the_address_for_the_card():
    """One decision of the model per VM and rule in the window, whatever the address: a flood of
    forged compromises from new addresses is one decision; each address is named on the card."""
    respond = _Respond()
    gate = DecisionGate(clock=_Clock())
    for i in range(20):
        decide_or_card(_compromise(f"198.51.100.{i}"), respond, gate)
    assert len(respond.seen) == 1
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert "19 dédoublonnées" in card["reason"] and "198.51.100.19" in card["reason"]


def test_a_flood_of_compromises_from_distinct_addresses_is_bounded():
    """No window opened (each decision judged « nothing », or failed): at most CRITICAL_ADDRESSES
    distinct addresses of one VM call the model in a window; the others are named on a card. The
    same address again, and another VM, are not held by it; past the window, it is open again."""
    clock, respond = _Clock(), _Respond(escalate=False, action="")
    gate = DecisionGate(clock=clock)
    for i in range(12):
        decide_or_card(_compromise(f"198.51.100.{i}"), respond, gate)
    assert len(respond.seen) == dq.CRITICAL_ADDRESSES
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert f"{12 - dq.CRITICAL_ADDRESSES} adresses au-delà du plafond" in card["reason"]
    state, _why, _wait = decide_or_card(_compromise("198.51.100.0"), respond, gate)   # an address known
    assert state is not None
    state, _why, _wait = decide_or_card(_compromise("198.51.100.50", vm=_vm("vm-example-02")), respond, gate)
    assert state is not None
    clock.t += dq.DEDUP_WINDOW_S + 1
    state, _why, _wait = decide_or_card(_compromise("198.51.100.60"), respond, gate)
    assert state is not None


def test_a_full_queue_of_compromises_never_chases_a_grave_detection():
    """The queue of a VM full of critical detections, then a ransomware detection: it enters, the
    newest critical one leaves (its card) — the reverse never: a queue full of grave detections
    refuses a critical one."""
    left: list = []
    q = DecisionQueue(on_drop=lambda item, why: left.append(item[0]))
    for i in range(dq.QUEUE_MAX):
        q.put((_compromise(f"198.51.100.{i}"), None, False))
    assert q.put((_ransomware(), None, False)) is True
    assert [d["raw_signal"]["first_result_row"]["SourceIP"] for d in left] == [f"198.51.100.{dq.QUEUE_MAX - 1}"]
    taken = [q.get()[0] for _ in range(q.qsize())]
    assert sum(1 for d in taken if d["ttp"] == "T1486") == 1
    graves = DecisionQueue(maxsize=3, on_drop=lambda item, why: left.append(item[0]))
    for _ in range(3):
        graves.put((_ransomware(), None, False))
    assert graves.put((_compromise("198.51.100.200"), None, False)) is False
    assert graves.put((_ransomware(), None, False)) is False       # a burst of graves: the newest says it
    assert graves.qsize() == 3


def test_a_held_detection_keeps_its_facts_and_the_pair_is_never_held(tmp_path):
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION
    from glorfindel.incidents import IncidentRegistry
    incidents = IncidentRegistry(path=tmp_path / "incidents.jsonl")
    respond = _Respond()
    gate = DecisionGate(clock=_Clock())
    decide_or_card(_sudo(1), respond, gate, incidents=incidents)
    state, _why, _wait = decide_or_card(_sudo(2), respond, gate, incidents=incidents)   # deduplicated
    assert state is None
    assert incidents.get_active(_vm()).confirmed == [ROOT_ELEVATION]
    # The brute force that succeeded, held too (its rule decided already): its fact is kept.
    decide_or_card(_compromise("198.51.100.7"), respond, gate, incidents=incidents)
    state, _why, _wait = decide_or_card(_compromise("198.51.100.8", run_id="watch-ssh-brute-force-2"),
                                        respond, gate, incidents=incidents)
    assert state is None
    assert set(incidents.get_active(_vm()).confirmed) == {LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION}


def test_the_pair_lifts_the_ceiling_only_never_the_window(tmp_path):
    """#644, point 2: B3a's pair complete on the VM, its detection is not held by the ceiling —
    once per pass of its rule —, but a decision that opened the window of its rule holds the
    next: the floor's card is there; no new call, pass after pass."""
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION
    from glorfindel.incidents import IncidentRegistry
    incidents = IncidentRegistry(path=tmp_path / "incidents.jsonl")
    incidents.get_or_create(_vm(), "T1548.003")
    incidents.confirm(_vm(), [ROOT_ELEVATION, LOGIN_AFTER_BRUTE_FORCE])
    clock = _Clock()
    gate = DecisionGate(clock=clock, per_min=0, low_per_min=0)
    # The floor's card beside the model's own action, run alone: the card alone opens the window.
    nothing = _Respond(escalate=False, action="")
    card = _Respond(escalate=False, action="snapshot", floor="Plancher déterministe (B3a) : …")
    first = _sudo(1)
    state, _why, _wait = decide_or_card(first, nothing, gate, incidents=incidents)     # past the ceiling
    assert state is not None
    same_pass = {**_sudo(2), "timestamp": first["timestamp"]}
    state, why, _wait = decide_or_card(same_pass, nothing, gate, incidents=incidents)
    assert state is None and "plafond" in why
    for i in range(3, 6):                                    # later passes: the floor's card each time
        clock.t += 30
        later = {**_sudo(i), "timestamp": f"2026-11-06T10:0{i}:00+00:00"}
        decide_or_card(later, card, gate, incidents=incidents)
    assert len(card.seen) == 1                               # its card opened the window
    assert dq.opens_window({"floor": "Plancher déterministe (B3a) : …", "escalate": False})


def test_a_held_brute_force_that_succeeded_writes_its_fact(tmp_path):
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE
    from glorfindel.incidents import IncidentRegistry
    incidents = IncidentRegistry(path=tmp_path / "incidents.jsonl")
    gate = DecisionGate(clock=_Clock())
    decide_or_card(_compromise("198.51.100.7"), _Respond(), gate)
    state, _why, _wait = decide_or_card(_compromise("198.51.100.7"), _Respond(), gate, incidents=incidents)
    assert state is None
    assert incidents.get_active(_vm()).confirmed == [LOGIN_AFTER_BRUTE_FORCE]


# ── The window: opened by a decision that contained or put a card before a human ──────────────

def test_a_decoy_judged_nothing_never_hides_the_next_line():
    gate = DecisionGate(clock=_Clock())
    nothing = _Respond(escalate=False, action="")
    decide_or_card(_ssh(1), nothing, gate)
    state, _why, _wait = decide_or_card(_ssh(2), nothing, gate)
    assert state is not None and len(nothing.seen) == 2


def test_a_failed_cycle_never_opens_the_window():
    gate = DecisionGate(clock=_Clock())
    failed = _Respond(cycle_error="decide: timeout")
    decide_or_card(_ssh(1), failed, gate)
    state, _why, _wait = decide_or_card(_ssh(2), failed, gate)
    assert state is not None and len(failed.seen) == 2


def test_an_exercise_and_the_real_never_share_the_window(monkeypatch):
    monkeypatch.setattr(dq, "_source", lambda data: data["context"].get("src", "real"))
    respond, gate = _Respond(), DecisionGate(clock=_Clock())
    decide_or_card(_ssh(1, src="exercise"), respond, gate)
    decide_or_card(_ssh(2), respond, gate)
    assert len(respond.seen) == 2


def test_the_ceiling_counts_the_draws_of_a_decision():
    """A decision that drew three times (D-1, a disruptive action about to run alone) is three
    calls — and PRT1, reserved at its admission: a second one would make six for a bound of four
    (before PRT1, it was admitted, and its draws counted after it)."""
    clock, respond = _Clock(), _Respond(draws=3)
    gate = DecisionGate(clock=clock, per_min=4, low_per_min=4)
    decide_or_card(_det("rule-a", row={"x": "a"}), respond, gate)
    decide_or_card(_det("rule-b", row={"x": "b"}), respond, gate)
    decide_or_card(_det("rule-c", row={"x": "c"}), respond, gate)
    assert len(respond.seen) == 1 and _counted(gate, clock) == (3, 3)


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
    state, why, _wait = decide_or_card(named, respond, gate)
    assert state is None and respond.seen == [] and why == "même passe"
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert "1 même passe" in card["reason"]


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
    assert "forged28" in card["reason"] and "29 même passe" in card["reason"]
    assert "… et 9 ligne(s) de plus" in card["reason"]


# ── PRT1 (#1060): the ceiling holds — every call a decision may make reserved at its admission ──

def _counted(gate: DecisionGate, clock) -> tuple[int, int]:
    """(the calls the gate counts in the last minute, reserves in flight and the floor's included;
    the low class's, the floor's apart)."""
    with gate._lock:
        return gate._recent(clock() if callable(clock) else clock)[:2]


class _Drawn:
    """The graph, the model behind it: each decision makes `calls(data)` calls (one, or the draws of
    D-1), logged at their moment; and at each call, what the gate counts — in flight, its reserve with
    the others' — noted: « at any moment » is read there."""

    def __init__(self, gate: DecisionGate, clock: _Clock, calls) -> None:
        self.gate, self.clock, self.calls = gate, clock, calls
        self.log: list[float] = []
        self.seen: list[dict] = []
        self.counted: list[tuple[int, int]] = []

    def __call__(self, data: dict) -> dict:
        self.seen.append(data)
        self.counted.append(_counted(self.gate, self.clock.t))
        k = self.calls(data)
        self.log.extend([self.clock.t] * max(1, k))
        return {"signal": data, "escalate": True, "action": "isolate_vm", "decision_model": "example/model",
                "decision_draws": [{}] * k}

    def most_in_a_minute(self) -> int:
        return max((sum(1 for u in self.log if t - 60.0 < u <= t) for t in self.log), default=0)


def _all_at_once(items: list[dict], gate: DecisionGate, respond) -> list[tuple]:
    """The VMs' threads all at once: each detection is admitted (or not) while those before it are
    still in flight — none ends before the last one passed the gate. (state, why, wait_s) of each."""
    out: list = [None] * len(items)

    def go(i: int) -> None:
        if i == len(items):
            return
        reached = []

        def r(data):
            reached.append(True)
            go(i + 1)
            return respond(data)
        out[i] = decide_or_card(items[i], r, gate)
        if not reached:
            go(i + 1)
    go(0)
    return out


def test_five_low_detections_admitted_by_concurrent_threads_never_pass_six_calls():
    """The defect (PRT1): `admit` reserved one call, the draws counted after — five brute forces
    admitted together by five VMs' threads made fifteen calls for a bound of six."""
    gate = DecisionGate()
    release, lock = threading.Event(), threading.Lock()
    calls: list[int] = []
    arrived, done = [], []

    def respond(data):
        with lock:
            arrived.append(data)
        release.wait(10)
        with lock:
            calls.extend([1] * 3)                      # the first draw and two confirming ones
        return {"signal": data, "escalate": True, "action": "isolate_vm", "decision_model": "example/model",
                "decision_draws": [{}] * 3}

    def one(i):
        out = decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), respond, gate)
        with lock:
            done.append(out)

    threads = [threading.Thread(target=one, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with lock:
            if len(arrived) + len(done) == 5:          # each in flight, or its card written
                break
        time.sleep(0.01)
    release.set()
    for t in threads:
        t.join(10)
    assert len(calls) <= dq.LOW_CALLS_PER_MIN and len(arrived) == 2
    assert sum(1 for state, _w, _s in done if state is None) == 3
    assert len([c for c in _cards() if c["escalation_type"] == "undecided_detection"]) == 3


def _burst(order: str) -> list[dict]:
    """8 graves, 3 medium, 2 low, 5 benign — each on its VM."""
    graves = [_ransomware(vm=_vm(f"vm-grave-{i:02d}")) for i in range(8)]
    lows = [_det(f"rule-{sev}-{i}", "T1110.001", vm=_vm(f"vm-{sev}-{i:02d}"), severity=sev,
                 row={"SourceIP": f"203.0.113.{10 * j + i}"})
            for j, (sev, n) in enumerate((("medium", 3), ("low", 2), ("informational", 5))) for i in range(n)]
    return graves + lows if order == "graves-first" else lows + graves


@pytest.mark.parametrize("order", ["graves-first", "lows-first"])
def test_a_burst_never_passes_ten_calls_and_no_grave_is_lost(order):
    """PRT1: « 8 graves, 3 medium, 2 low, 5 benign » arriving at once on eighteen VMs: never more than
    ten calls in a minute, the low class never more than six, at any moment; every grave decided in
    the end — waiting, never a card —; a low one beyond, a card."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    respond = _Drawn(gate, clock, lambda d: 3 if d["ttp"] == "T1486" or d["severity"] == "medium" else 1)
    pending = _burst(order)
    for _ in range(30):
        results = _all_at_once(pending, gate, respond)
        waiting = [d for d, (state, _why, wait_s) in zip(pending, results) if wait_s]
        assert all(d["ttp"] == "T1486" for d in waiting)
        pending = waiting
        if not pending:
            break
        clock.t += 20
    assert not pending
    assert sum(1 for d in respond.seen if d["ttp"] == "T1486") == 8
    assert respond.most_in_a_minute() <= dq.MODEL_CALLS_PER_MIN
    assert all(n <= dq.MODEL_CALLS_PER_MIN and low <= dq.LOW_CALLS_PER_MIN for n, low in respond.counted)
    cards = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert cards and all(c["ttp"] != "T1486" for c in cards)


def test_a_reserve_not_used_is_given_back_for_the_next():
    """Two low decisions in flight hold the low class's six places — a third is a card; both end in
    human_only (one call each): their places come back, the next one is admitted."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    out: dict = {}

    def then(*rest):           # while this one is in flight, the next one comes
        def respond(data):
            if rest:
                out[rest[0]["resource_id"]] = decide_or_card(rest[0], then(*rest[1:]), gate)
            return {"signal": data, "escalate": True, "decision_model": "example/model", "decision_draws": []}
        return respond
    second, third = _ssh(2, vm=_vm("vm-example-02")), _ssh(3, vm=_vm("vm-example-03"))
    decide_or_card(_ssh(1), then(second, third), gate)
    assert out[second["resource_id"]][0] is not None
    assert out[third["resource_id"]][0] is None and "plafond" in out[third["resource_id"]][1]
    assert _counted(gate, clock) == (2, 2)
    state, _why, _wait = decide_or_card(_ssh(4, vm=_vm("vm-example-04")), _Respond(), gate)
    assert state is not None


def test_a_low_reserve_never_takes_the_places_of_the_grave_ones():
    """Four human_only decisions leave four calls of the low class; a fifth would reserve three more:
    seven — on the grave ones' four places. A card; and two graves of three draws still fit."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    respond = _Drawn(gate, clock, lambda d: 3 if d["ttp"] == "T1486" else 0)
    for i in range(4):
        decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), respond, gate)
    state, why, _wait = decide_or_card(_ssh(5, vm=_vm("vm-example-05")), respond, gate)
    assert state is None and "plafond" in why
    for i in range(2):
        state, _why, wait_s = decide_or_card(_ransomware(vm=_vm(f"vm-grave-{i:02d}")), respond, gate)
        assert state is not None and wait_s == 0
    assert all(n <= dq.MODEL_CALLS_PER_MIN and low <= dq.LOW_CALLS_PER_MIN for n, low in respond.counted)
    assert _counted(gate, clock) == (10, 4)


def _recovery(vm: str | None = None) -> dict:
    """A release after a verified restore, as recovery_watch builds it (REC1)."""
    return {"signal_id": "20261106T100000Z_ab12_recovery_complete", "event": "recovery_complete",
            "timestamp": "2026-11-06T10:00:00+00:00", "provider": "azure", "resource_id": vm or _vm(),
            "resource_type": "vm", "ttp": "", "severity": "low",
            "raw_signal": {"recovery_point_time": "2026-11-06 09:00:00+00:00", "restore_time_s": 1200,
                           "run_command_neutralized": True},
            "context": {"run_id": "20261106T100000Z_ab12"}}


def _missed(ttp: str = "T1486") -> dict:
    """A rule proposal (an exercise's miss, `detection_missed`), as the runs/ channel admits it."""
    return {"signal_id": "20261106T100000Z_ab12_detection_missed", "event": "detection_missed",
            "timestamp": "2026-11-06T10:00:00+00:00", "provider": "azure", "resource_id": _vm(),
            "resource_type": "vm", "ttp": ttp, "severity": "high",
            "raw_signal": {"detection_source": "azure_monitor"},
            "context": {"run_id": "20261106T100000Z_ab12", "scenario": "x", "detection_timeout_s": 300}}


def test_a_release_after_a_restore_is_counted_and_waits_never_refused():
    """`recovery_complete` calls the model (`decide`, release_isolation): counted, as a grave one —
    the minute full, it waits for its room, never a card."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    for i in range(3):
        decide_or_card(_ransomware(vm=_vm(f"vm-grave-{i:02d}")), _Respond(draws=3), gate)
    state, why, wait_s = decide_or_card(_recovery(), _Respond(), gate)
    assert state is None and wait_s > 0 and "plafond" in why
    assert not [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    clock.t += 61
    state, _why, wait_s = decide_or_card(_recovery(), _Respond(), gate)
    assert state is not None and wait_s == 0
    assert _counted(gate, clock) == (1, 0)


def test_a_rule_proposal_is_counted_as_a_low_one_and_beyond_it_a_card():
    """`detection_missed` calls the model (`propose_detection_rule`): counted in the low class,
    whatever its technique; the low class full, it is said on a card, never lost in silence."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    for i in range(2):
        decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), _Respond(draws=3), gate)
    state, why, wait_s = decide_or_card(_missed(), _Respond(), gate)
    assert state is None and wait_s == 0 and "plafond" in why
    [card] = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert card["ttp"] == "T1486" and "plafond des appels au modèle" in card["reason"]
    assert "proposition de règle non faite (plafond) : relancer le scénario" in card["reason"]
    assert any("Relancer le scénario" in step for step in card["suggested_steps"])
    clock.t += 61
    proposed = _Respond(proposed_rule={"query": "Syslog"}, decision_model="")
    state, _why, _wait = decide_or_card(_missed(), proposed, gate)
    assert state is not None and _counted(gate, clock) == (1, 1)


def test_the_floor_stays_the_only_way_past_the_ceiling():
    """B3a's pair confirmed on the VM: its detection passes the full minute, once per pass — the
    only overflow —, its calls in the total, never in the room of the grave ones: a grave one
    still fits."""
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    for i in range(2):
        decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), _Respond(draws=3), gate)
    pair = [ROOT_ELEVATION, LOGIN_AFTER_BRUTE_FORCE]
    first = _sudo(1)
    kind, _why, *_ = gate.admit(first, pair)
    assert kind == ""
    gate.spent(first, {"decision_model": "example/model", "decision_draws": [{}] * 3}, *_)
    kind, why, *_ = gate.admit({**_sudo(2), "timestamp": first["timestamp"]}, pair)   # same pass
    assert kind == "ceiling" and "plafond" in why
    assert _counted(gate, clock) == (9, 6)
    state, _why, wait_s = decide_or_card(_ransomware(), _Respond(draws=3), gate)
    assert state is not None and wait_s == 0


def _floor_respond(data):
    return {"signal": data, "escalate": False, "action": "", "decision_model": "example/model",
            "decision_draws": [{}] * 3}


def test_the_floor_s_calls_count_the_low_class_gives_way_the_grave_ones_keep_their_room():
    """The floor's calls are counted in the total (review of PRT1): three floors of three draws on
    three rules — nine calls —, a low detection is a card; never in the room of the grave ones:
    a ransomware detection still fits."""
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    pair = [ROOT_ELEVATION, LOGIN_AFTER_BRUTE_FORCE]
    for i, rule in enumerate(("sudo-a", "sudo-b", "sudo-c")):
        floor = _det(rule, "T1548.003", row={"SyslogMessage": f"x : USER=root ; COMMAND=/bin/c{i}"})
        kind, _why, ticket = gate.admit(floor, pair)
        assert kind == ""
        gate.spent(floor, _floor_respond(floor), ticket)
    assert _counted(gate, clock) == (9, 0)
    state, why, _wait = decide_or_card(_ssh(1, vm=_vm("vm-example-02")), _Respond(), gate)
    assert state is None and "plafond" in why
    state, _why, wait_s = decide_or_card(_ransomware(vm=_vm("vm-grave-00")), _Respond(draws=3), gate)
    assert state is not None and wait_s == 0


def test_a_floor_of_the_runs_channel_once_per_vm_and_source_in_a_window():
    """Not the RulePoller's (a line of runs/, each its moment): its floor once per VM and source in a
    window — the next lines go through the ceiling."""
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION
    clock = _Clock()
    gate = DecisionGate(clock=clock, per_min=0, low_per_min=0)
    pair = [ROOT_ELEVATION, LOGIN_AFTER_BRUTE_FORCE]
    lines = [{**_sudo(i, run_id="20261106T100000Z_ab12"), "timestamp": f"2026-11-06T10:0{i}:00+00:00"}
             for i in range(3)]
    kind, _why, ticket = gate.admit(lines[0], pair)
    assert kind == ""
    gate.spent(lines[0], _floor_respond(lines[0]), ticket)
    for line in lines[1:]:
        kind, why, _t = gate.admit(line, pair)
        assert kind == "ceiling" and "plafond" in why
    clock.t += dq.DEDUP_WINDOW_S + 1
    kind, _why, _t = gate.admit(lines[2], pair)
    assert kind == ""


@pytest.mark.parametrize("event", ["detection_missed", "recovery_complete", "detection_timeout"])
def test_the_floor_is_a_detection_s_only(event):
    """`decide`'s floor plays on a detection only: on a VM whose pair is confirmed, a rule proposal,
    a release, an attack the monitoring missed are counted and held by the ceiling as any other."""
    from glorfindel.agent import LOGIN_AFTER_BRUTE_FORCE, ROOT_ELEVATION
    gate = DecisionGate(clock=_Clock(), per_min=0, low_per_min=0)
    pair = [ROOT_ELEVATION, LOGIN_AFTER_BRUTE_FORCE]
    data = {"detection_missed": _missed(), "recovery_complete": _recovery(),
            "detection_timeout": {**_ssh(1, run_id="20261106T100000Z_ab12"), "event": "detection_timeout"}}[event]
    kind, why, ticket = gate.admit(data, pair)
    assert kind in ("ceiling", "wait") and "plafond" in why and ticket == 0


def test_calls_made_reads_the_state_the_safe_side_when_it_cannot():
    det, missed = _ssh(1), _missed()
    assert dq.calls_made(det, {"decision_model": "m", "decision_draws": [{}] * 3}, 3) == 3
    assert dq.calls_made(det, {"decision_model": "m", "decision_draws": []}, 3) == 1        # human_only
    assert dq.calls_made(det, {"decision_draws": []}, 3) == 0              # the model never reached
    assert dq.calls_made(det, {"decision_model": "m", "cycle_error": "decide: timeout"}, 3) == 3
    assert dq.calls_made(det, {"cycle_error": "graph: boom"}, 3) == 3
    assert dq.calls_made(det, None, 3) == 3
    assert dq.calls_made(missed, {"proposed_rule": {"query": "x"}}, 1) == 1
    assert dq.calls_made(missed, {"proposed_rule": None, "outcome": {"status": "skipped"}}, 1) == 0
    assert dq.calls_made(missed, {"cycle_error": "graph: author"}, 1) == 1


def test_a_decision_that_never_reaches_the_model_gives_its_reserve_back():
    """A detection read as an identity or the control plane only in depth by `decide` (C2, AL1):
    its decision is the code's, `decision_model` unset — its whole reserve comes back."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    code = _Respond(decision_model="")
    for i in range(8):
        state, _why, _wait = decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), code, gate)
        assert state is not None
    assert _counted(gate, clock) == (0, 0)


def test_respond_raising_keeps_its_reserve():
    """A decision that raised: what it drew cannot be read — its reserve stays counted."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)

    def boom(_data):
        raise RuntimeError("graph")
    with pytest.raises(RuntimeError):
        decide_or_card(_ssh(1), boom, gate)
    assert _counted(gate, clock) == (3, 3)
    clock.t += 61                                  # counted from its end, given back: never in flight
    assert _counted(gate, clock) == (0, 0) and not gate._reserved


def test_a_grave_one_held_by_reserves_in_flight_looks_again_soon():
    """Three grave decisions in flight hold the minute — no call made yet: the fourth waits, and looks
    again within `IN_FLIGHT_RECHECK_S`, not a minute later: their end may give their reserve back."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    for i in range(3):
        kind, _why, _t = gate.admit(_ransomware(vm=_vm(f"vm-grave-{i:02d}")))
        assert kind == ""
    state, why, wait_s = decide_or_card(_ransomware(vm=_vm("vm-grave-03")), _Respond(), gate)
    assert state is None and "plafond" in why and not gate._calls
    assert 0 < wait_s <= dq.IN_FLIGHT_RECHECK_S <= 5


def test_an_attack_the_monitoring_missed_waits_in_its_technique_s_class_never_a_card():
    """`detection_timeout` calls the model (`decide`, a snapshot that preserves the VM): counted in
    its technique's class (SEC-E, V-08: a line of the runs/ channel), and beyond the ceiling it
    waits for its room — even a low one, never a card."""
    clock = _Clock()
    gate = DecisionGate(clock=clock)
    for i in range(3):
        decide_or_card(_ransomware(vm=_vm(f"vm-grave-{i:02d}")), _Respond(draws=3), gate)
    missed = {**_ssh(1, run_id="20261106T100000Z_ab12"), "event": "detection_timeout"}
    state, why, wait_s = decide_or_card(missed, _Respond(), gate)
    assert state is None and wait_s > 0 and "plafond" in why
    assert not [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    clock.t += 61
    state, _why, wait_s = decide_or_card(missed, _Respond(), gate)
    assert state is not None and wait_s == 0 and _counted(gate, clock) == (1, 1)


def _timeout(i: int, ttp: str = "T1059.004") -> dict:
    """An attack the monitoring missed, from a line of the runs/ channel (`resolve_attack_started`)."""
    return {**_det(f"rule-{i}", ttp, vm=_vm(f"vm-channel-{i:02d}"), row={"x": str(i)},
                   run_id="20261106T100000Z_ab12"), "event": "detection_timeout"}


def test_a_flood_of_timeouts_of_the_channel_never_delays_a_grave_detection():
    """SEC-E (V-08), kept by PRT1: a line an injector wrote never takes the grave ones' room. Timeouts
    of a low technique in flight hold the low class; the next waits — never a card —, and a ransomware
    detection of the RulePoller still fits; in a queue, it passes before them."""
    gate = DecisionGate(clock=_Clock())
    for i in range(2):
        kind, _why, _t = gate.admit(_timeout(i))
        assert kind == ""
    kind, why, _t = gate.admit(_timeout(2))
    assert kind == "wait" and "plafond" in why
    kind, _why, _t = gate.admit(_ransomware())
    assert kind == ""
    q = DecisionQueue()
    for i in range(5):
        q.put((_timeout(i), None, False))
    q.put((_ransomware(), None, False))
    assert q.get()[0]["ttp"] == "T1486"


def test_spent_counts_its_decision_under_one_lock(monkeypatch):
    """`spent` reads the window (`opens_window`, files) before its lock, then takes its reserve back and
    counts its calls under one: while it reads, its reserve still holds its places — a third low
    decision is never admitted beside two in flight."""
    gate = DecisionGate(clock=_Clock())
    first, second, third = (_ssh(i, vm=_vm(f"vm-example-{i:02d}")) for i in range(3))
    tickets = [gate.admit(d)[2] for d in (first, second)]
    entered, release = threading.Event(), threading.Event()
    real = dq.opens_window

    def slow(state):
        entered.set()
        release.wait(10)
        return real(state)
    monkeypatch.setattr(dq, "opens_window", slow)
    state = {"signal": first, "escalate": True, "decision_model": "example/model",
             "decision_draws": [{}] * 3}
    t = threading.Thread(target=gate.spent, args=(first, state, tickets[0]))
    t.start()
    assert entered.wait(10)
    counted = _counted(gate, gate._clock)
    kind, _why, _t = gate.admit(third)
    release.set()
    t.join(10)
    assert counted == (6, 6) and kind == "ceiling"
    assert _counted(gate, gate._clock)[1] <= dq.LOW_CALLS_PER_MIN


def test_a_release_waiting_never_leaves_a_full_queue_for_another():
    """A `recovery_complete` put back to wait: it is queued as a grave one and never leaves for
    another — a queue full of low detections, or of critical ones, keeps it."""
    left: list = []
    low = DecisionQueue(maxsize=3, on_drop=lambda item, why: left.append(item[0]))
    for i in range(3):
        low.put((_ssh(i), None, False))
    assert low.put_back((_recovery(), None, False), 1.0) is True
    critical = DecisionQueue(maxsize=3, on_drop=lambda item, why: left.append(item[0]))
    for i in range(3):
        critical.put((_compromise(f"198.51.100.{i}"), None, False))
    assert critical.put_back((_recovery(), None, False), 1.0) is True
    assert all(d["event"] == "detection" for d in left) and len(left) == 2
    # A rule proposal is a low one whatever its technique: never protected (`protected`).
    assert dq.protected((_ransomware(), None, False)) and dq.protected((_recovery(), None, False))
    assert not dq.protected((_missed("T1486"), None, False))


def test_a_ticket_is_given_back_whatever_its_data_became():
    """`spent` takes the ticket first: a detection that no longer reads as one of the model's (its
    plane said after the admission) leaves no reserve in flight."""
    gate = DecisionGate(clock=_Clock())
    data = _ssh(1)
    kind, _why, ticket = gate.admit(data)
    assert kind == "" and gate._reserved
    gate.spent({**data, "context": {**data["context"], "plane": "control"}}, None, ticket)
    assert not gate._reserved


# ── The watch: its workers take their detections through the queue and the gate ───────────────

def test_the_watch_decides_through_the_gate_and_says_a_card(tmp_path, monkeypatch):
    """The watch (dry-run), three attacks on three VMs, a ceiling of one low call a minute: one
    decision reaches the graph, the two others are said without a decision of the model."""
    from .test_signal_origin import _line, _run_watch
    monkeypatch.setattr(dq, "LOW_CALLS_PER_MIN", 1)
    lines = [_line("attack_started", signal_id=f"a{i}", resource_id=_vm(f"vm-example-{i:02d}"),
                   ttp="T1110.001", severity="high",
                   raw_signal={"attack_time": time.time() - 60}) for i in range(3)]
    responded, _polled, out = _run_watch(tmp_path, monkeypatch, lines, expect=1, slow_respond=0.3)
    assert len(responded) == 1, out
    flat = " ".join(out.split())
    assert flat.count("Non décidée par le modèle") == 2 and "plafond des appels au modèle" in flat
