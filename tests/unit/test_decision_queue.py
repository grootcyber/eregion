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
    """The graph: counts what reached it (the model is behind it, nowhere else). By default each
    decision puts a card before a human (`escalate`), as in human_only."""

    def __init__(self, draws: int = 0, **state) -> None:
        self.seen: list[dict] = []
        self.draws = draws
        self.state = {"escalate": True, "action": "isolate_vm", **state}

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
    a ransomware detection still calls the model."""
    gate, respond = DecisionGate(clock=_Clock()), _Respond()
    for i in range(20):
        decide_or_card(_ssh(i, vm=_vm(f"vm-example-{i:02d}")), respond, gate)
    assert len(respond.seen) == dq.LOW_CALLS_PER_MIN
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
    assert len(respond.seen) == dq.LOW_CALLS_PER_MIN
    cards = [c for c in _cards() if c["escalation_type"] == "undecided_detection"]
    assert len(cards) == 3 and all(c["action"] == "" and not c["action_params"] for c in cards)
    assert all("plafond des appels au modèle" in c["reason"] for c in cards)
    clock.t += 61
    decide_or_card(_det("rule-late", row={"SourceIP": "203.0.113.99"}), respond, gate)
    assert len(respond.seen) == dq.LOW_CALLS_PER_MIN + 1


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
