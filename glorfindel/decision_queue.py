"""The watch's decision queue, bounded (SEC-A2, #631; audit of 06/11, V-03 and V-13).

Every detection the RulePoller dispatches waits in its VM's queue for a decision, and a decision
of the data plane is a call to the model (one in `human_only`, up to `decision_draws` when a
disruptive action would run alone). A row aggregated by its text columns is one detection per
value: a local account on a watched VM that writes lines with twenty new addresses each pass made
twenty detections per pass — 720 decisions an hour on one VM, ~2 160 calls, and a real ransomware
detection waited behind them for hours. Four bounds, before any call to the model:

- **the queue of a VM is bounded** (`QUEUE_MAX`): beyond, the least grave and newest detection
  waiting — or the one that comes, if it is no graver — leaves the queue; it gets a card without a
  decision of the model, said on the watch's console and counted on that card, never in silence.
  A detection of a grave technique (`GRAVE_TTPS`) never leaves it for another (SEC-E): it enters a
  queue full of critical ones, the newest of them leaves;
- **the gravest first** (`gravity`): a critical detection, then one of a grave technique
  (`GRAVE_TTPS`), then the others — each class first come, first served; a grave detection never
  waits behind a lower one (only behind the cycle in flight: its investigation, its draws, its
  action and its check, each bounded). Critical is the RulePoller's word only (a compromise,
  COR1, its rule's): a line of the runs/ channel never says it (SEC-E, V-08) — its class is its
  technique's;
- **one decision of the model per VM, rule, gravity and source in a window** (`DEDUP_WINDOW_S`),
  opened only by a decision that contained or put a card before a human: the other detections of
  that rule on that VM in the window are deduplicated — a card that names them, and no call. A
  critical one (COR1) too, whatever its address (SEC-E): the address is for the card;
- **a ceiling of distinct addresses** of the critical class per VM in a window
  (`CRITICAL_ADDRESSES`): beyond, a new address is a card, no call (SEC-E);
- **a ceiling of calls to the model per minute**, for the whole watch (`MODEL_CALLS_PER_MIN`),
  each class counted apart, draws included: the low class at most `LOW_CALLS_PER_MIN`, the grave
  ones — the critical ones with them (SEC-E) — the rest whatever the low class did. Beyond it a
  low detection is a card, never an action; a grave or a critical one waits in its queue until
  the room comes back.

The ceiling holds its bound (PRT1, #1060): a decision reserves, at its admission, every call it may
make (`reserve`: `decision_draws`, the first draw and the confirming ones of D-1, whatever its mode —
the mode, the readiness and the gates are read in `decide`, after the admission), counted while it
is in flight, and gives back, when it ends, what it did not make (`spent`, `calls_made`: one call in
human_only, or when a gate held the action before the draws) — the calls it made counted from its
end. The VMs' threads admitted together never pass the bound: at any moment the calls counted in the
last minute are at most `MODEL_CALLS_PER_MIN`, the low class's at most `LOW_CALLS_PER_MIN`, and the
grave ones keep the rest. A reserve is at most its class's room (a decision always fits in an empty
minute): with `GLORFINDEL_DECISION_DRAWS` above the grave ones' room (4), the draws beyond it are
counted after the decision, as before PRT1. What calls the model is counted (`calls_model`,
`MODEL_EVENTS`): a detection; an attack the monitoring missed (`detection_timeout`, a line of the
runs/ channel: its decision preserves the VM), counted and queued in its technique's class,
as any line of the channel — never grave by its event alone (SEC-E, V-08) — and never a card: beyond, it waits,
bounded by the channel's (`CHANNEL_QUEUED_PER_VM`) and its queue's (`QUEUE_MAX`); the release after a
verified restore (`recovery_complete`), counted and queued as a grave one whatever its technique —
never a card, it waits for its room, and never leaves its queue for another (`protected`); and a
rule proposal (`detection_missed`, an exercise:
counted as a low one; beyond, a card that says it was not made — nothing asks for it again). A call
that failed stays counted (the safe side); a decision of the code (an identity, the
control plane) takes no reserve, or gives it all back. `glorfindel respond`, run by hand, never passes
through the gate.

The bound of the critical class (SEC-E, #846), from these constants: one VM's critical detections
of one rule call the model at most `CRITICAL_ADDRESSES` times in a window — once, when the first
decision opens it —, each decision at most `decision_draws` calls, all inside the ceiling's room of
the grave class; and never one sends a detection of a grave technique out of a full queue.

What B3a's floor needs is never lost: a detection that confirms a fact on its VM (a brute force
that succeeded, a sudo to root) writes it on the VM's incident even when it is held, without
prolonging the incident (SEC-E); and once both are confirmed on the VM, its detection is never
held by the ceiling (one per pass of its rule and VM) — the dedup still holds it once a decision
opened the window (SEC-E, #644): the floor proposes, and its card is there. It is the only way past
the ceiling (PRT1), on a detection only: its calls are in the total — the low class gives way to
them —, never in the room of the grave ones; a line of the runs/ channel, once per VM and source in a
window.

Before this gate, the breaker in dollars (PRT2, #1160, glorfindel/model_budget.py, the watch's): what the
calls cost a day, judged before any reserve (`decide_or_card`, `budget`) — an ordinary beyond its budget is a
card, an exercise beyond its own a card that says the pause, a grave the code's path (its decision without
the model; `admit(code=True)`: the same pass, the dedup and the addresses hold it, never the ceiling, it makes
no call). The bounds above hold behind it unchanged.

A detection with no decision of the model is a card `undecided_detection` (`record_undecided`):
no action, no investigation, nothing in the memory; the card of a VM and a rule names the latest of
them, and how many there are, for each reason. Only what calls the model is held by these bounds:
a card of the control plane or of an identity is decided by the code (AL1, C2), never by the model.
"""
from __future__ import annotations

import itertools
import threading
import time
from collections import deque
from typing import Callable

# The detections that may wait in one queue (a VM's, or a plane's): ~ten rules × five cards and a
# summary each pass is far below; a queue that fills is a burst, and it is said.
QUEUE_MAX = 50
# One decision of the model per VM, rule and gravity in this window; the others, a card that names
# them. Five minutes: the window of the shipped rules' queries is ten, a pass every thirty seconds.
DEDUP_WINDOW_S = 300.0
# Calls to the model per minute, for the whole watch; the low class takes at most LOW_CALLS_PER_MIN
# of them — the rest is the room of the grave ones.
MODEL_CALLS_PER_MIN = 10
LOW_CALLS_PER_MIN = 6
# The techniques whose detection is grave whatever its row: the data is being destroyed or is
# leaving — every minute counts. By technique, never by the rule's text: a copy in the client's
# layer keeps the gravity of the technique it detects.
GRAVE_TTPS = frozenset({"T1486", "T1485", "T1490", "T1041", "T1567"})
# SEC-E (#846): the distinct addresses of the critical class (COR1) that may call the model for one
# VM in a window (`DEDUP_WINDOW_S`) — two compromises from two addresses are both decided, a flood of
# forged addresses is not; beyond, a card that names them.
CRITICAL_ADDRESSES = 3
# The lines a card of `undecided_detection` names, the latest first (as AUD1's fold, FOLD_MAX);
# beyond, their number.
CARD_ROWS = 20

# PRT1 (#1060): the events whose decision calls the model — a detection (the RulePoller's, an attack's
# resolved), an attack the monitoring missed and the release after a restore (`decide`), a rule
# proposal (`propose_detection_rule`).
MODEL_EVENTS = frozenset({"detection", "detection_timeout", "recovery_complete", "detection_missed"})
# A grave detection held only by the reserves of the decisions in flight: looked at again this soon.
IN_FLIGHT_RECHECK_S = 5.0

CRITICAL, GRAVE, LOW = 0, 1, 2
_CLASS_WORD = {CRITICAL: "critique", GRAVE: "grave", LOW: "basse"}
# B3a's pair: both confirmed on a VM, its floor proposes isolate_vm whatever the model chose.
_FLOOR_PAIR = frozenset({"login_after_brute_force", "root_elevation"})


def grave_technique(data: dict) -> bool:
    """A detection of a technique of `GRAVE_TTPS` (its sub-technique included), whatever its row."""
    ttp = str(data.get("ttp") or "").upper()
    return ttp in GRAVE_TTPS or ttp.split(".", 1)[0] in GRAVE_TTPS


def gravity(data: dict) -> int:
    """The class a detection waits in: CRITICAL (the RulePoller's severity says so — a compromise,
    COR1, its rule's own word), GRAVE (a technique of `GRAVE_TTPS`), LOW (the others). The severity
    of another detection — a line of the runs/ channel, resolved (SEC-E, V-08) — is never read: its
    class is its technique's."""
    if from_rulepoller(data) and str(data.get("severity") or "").lower() == "critical":
        return CRITICAL
    if grave_technique(data):
        return GRAVE
    return LOW


def _context(data: dict) -> dict:
    ctx = data.get("context")
    return ctx if isinstance(ctx, dict) else {}


def _row(data: dict) -> dict:
    raw = data.get("raw_signal") if isinstance(data.get("raw_signal"), dict) else {}
    row = raw.get("first_result_row") or raw.get("detected_data") or {}
    return row if isinstance(row, dict) else {}


def calls_model(data: dict) -> bool:
    """An event of `MODEL_EVENTS`, of the data plane: its decision is the model's. A card of the
    control plane or of an identity is decided by the code (AL1, C2)."""
    return data.get("event") in MODEL_EVENTS and _context(data).get("plane") not in ("control", "identity")


def call_class(data: dict) -> int:
    """The class a decision's calls count in, and its queue's (PRT1): the release after a verified
    restore as a grave one — never refused, it waits for its room —, a rule proposal (an exercise)
    as a low one, whatever its technique; any other, its gravity — an attack the monitoring missed
    (`detection_timeout`, from a line of the runs/ channel) too: in its technique's class, as any line of the channel —
    never grave by its event alone (SEC-E, V-08); beyond the ceiling, it waits all the same (`admit`)."""
    event = data.get("event")
    if event == "recovery_complete":
        return GRAVE
    if event == "detection_missed":
        return LOW
    return gravity(data)


def protected(item: tuple) -> bool:
    """What never leaves a full queue for another (SEC-E, PRT1): a detection of a grave technique,
    the release after a restore — never a rule proposal, a low one whatever its technique."""
    data = item[0]
    if data.get("event") == "detection_missed":
        return False
    return grave_technique(data) or data.get("event") == "recovery_complete"


def calls_made(data: dict, state, reserved: int) -> int:
    """The calls a decision made, read on its state (PRT1). What cannot be read keeps its reserve, the
    safe side: a cycle that failed (a call that failed stays counted; a graph that raised lost what it
    drew), a state that is none. A rule proposal: one when its author was asked (`proposed_rule`),
    none when it was skipped or blocked before. A decision: none when the model was never reached
    (`decision_model` unset: `decide` read an identity or the control plane in depth), else its draws
    (`decision_draws`: the first and the confirming ones of D-1), or the first alone."""
    if not isinstance(state, dict) or state.get("cycle_error"):
        return reserved
    if data.get("event") == "detection_missed":
        return 1 if state.get("proposed_rule") is not None else 0
    turns = _enquiry_calls(state)            # ENQ5b: the turns its enquiry made, whatever became of decide
    if not state.get("decision_model"):
        return turns
    return max(1, len(state.get("decision_draws") or [])) + turns


def enquiry_turns(data: dict) -> int:
    """The turns a decision's enquiry may make (ENQ5b, `GLORFINDEL_ENQUIRY=loop`: N + 1), else 0."""
    from glorfindel.enquiry import interrupteur
    return interrupteur.tours(data)


def _enquiry_calls(state: dict) -> int:
    enquete = state.get("enquete")
    calls = enquete.get("appels") if isinstance(enquete, dict) else 0
    return calls if isinstance(calls, int) and not isinstance(calls, bool) and calls > 0 else 0


def from_rulepoller(data: dict) -> bool:
    """A detection of the RulePoller: its synthetic run (`watch-<rule>-<ts>`) and its rule."""
    ctx = _context(data)
    return str(ctx.get("run_id") or "").startswith("watch-") and bool(ctx.get("rule_name"))


def facts_of(data: dict) -> list[str]:
    """What this detection confirms on its VM (B3a, `agent.confirmed_facts`)."""
    from glorfindel.agent import confirmed_facts
    try:
        return confirmed_facts(data)
    except Exception:
        return []


def _source(data: dict) -> str:
    from glorfindel.agent import _cycle_source
    return _cycle_source(data)[0]


def opens_window(state) -> bool:
    """A decision the dedup's window may stand on: it contained (an isolation or a block that ran,
    or the VM already contained) or it put a card before a human — never a cycle that failed, nor
    a decision with no action and no card (a decoy line judged « nothing » never hides the next)."""
    if not isinstance(state, dict) or state.get("cycle_error"):
        return False
    if state.get("escalate") or (state.get("outcome") or {}).get("status") == "escalated":
        return True
    # SEC-E: the floor's card (B3a) beside an action that ran alone, or a compromise's (COR1).
    if state.get("floor") or (state.get("outcome") or {}).get("compromise_card"):
        return True
    if (state.get("outcome") or {}).get("executed") and state.get("action") in ("isolate_vm", "block_suspicious_ip"):
        return True
    try:
        from glorfindel.agent import _contained_now
        return bool(_contained_now(state.get("signal") or {})[0])
    except Exception:
        return False


class DecisionQueue:
    """A VM's queue: the gravest first, first come first served in a class; bounded.

    `put` never blocks: beyond `maxsize`, the least grave and newest waiting detection — or the one
    that comes, when it is no graver — is handed to `on_drop(item, why)`, which says it. A detection
    of a grave technique (`protect`, SEC-E) never leaves for another: it enters a full queue in the
    place of the least grave and newest of the others, and is the one that leaves only when every
    detection waiting is one too. `put_back` puts a detection back in its place, held until a moment
    (a grave one, the ceiling reached): meanwhile, the others are taken."""

    def __init__(self, maxsize: int | None = None,
                 on_drop: Callable[[tuple, str], None] | None = None,
                 classify: Callable[[tuple], int] | None = None,
                 protect: Callable[[tuple], bool] | None = None) -> None:
        self._max = QUEUE_MAX if maxsize is None else maxsize
        self._on_drop = on_drop
        # PRT1: a release after a restore waits as a grave one, and never leaves for another (`protected`).
        self._classify = classify or (lambda item: call_class(item[0]))
        self._protect = protect or protected
        self._heap: list[tuple[int, int, tuple]] = []
        self._held: dict[int, float] = {}
        self._seq = itertools.count()
        self._back = itertools.count(-1, -1)
        self._cond = threading.Condition()
        self.dropped = 0

    def _enter(self, entry: tuple[int, int, tuple]):
        """Under the lock: the entry in, or the entry that leaves (None when none leaves)."""
        cls = entry[0]
        dropped = None
        if len(self._heap) >= self._max:
            # SEC-E: never a detection of a grave technique for another — the others leave first.
            others = [e for e in self._heap if not self._protect(e[2])]
            worst = max(others) if others else None
            if worst is not None and (self._protect(entry[2]) or cls < worst[0]):
                self._heap.remove(worst)
                self._held.pop(worst[1], None)
                self._heap.append(entry)
                dropped = worst
            else:
                dropped = entry
            self.dropped += 1
        else:
            self._heap.append(entry)
        self._cond.notify()
        return dropped

    def _said(self, dropped) -> None:
        if dropped is not None and self._on_drop is not None:
            self._on_drop(dropped[2], (
                f"la file de cette VM tient déjà {self._max} détections : celle-ci, de gravité "
                f"{_CLASS_WORD.get(dropped[0], dropped[0])}, en sort sans décision du modèle"))

    def put(self, item: tuple) -> bool:
        """False when the item did not enter (the queue full, and it is no graver)."""
        entry = (self._classify(item), next(self._seq), item)
        with self._cond:
            dropped = self._enter(entry)
            if dropped is entry:
                self._held.pop(entry[1], None)
        self._said(dropped)
        return dropped is not entry

    def put_back(self, item: tuple, hold_s: float) -> bool:
        """`item` back in the queue, before the others of its class, not taken before `hold_s`."""
        entry = (self._classify(item), next(self._back), item)
        with self._cond:
            self._held[entry[1]] = time.monotonic() + max(0.0, hold_s)
            dropped = self._enter(entry)
            if dropped is entry:
                self._held.pop(entry[1], None)
        self._said(dropped)
        return dropped is not entry

    def _ready(self, now: float):
        ready = [e for e in self._heap if self._held.get(e[1], 0.0) <= now]
        return min(ready) if ready else None

    def get(self, timeout: float | None = None) -> tuple:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while True:
                now = time.monotonic()
                entry = self._ready(now)
                if entry is not None:
                    self._heap.remove(entry)
                    self._held.pop(entry[1], None)
                    return entry[2]
                waits = [t - now for t in self._held.values()]
                if deadline is not None:
                    if now >= deadline:
                        raise TimeoutError("decision queue empty")
                    waits.append(deadline - now)
                self._cond.wait(min(waits) if waits else None)

    def qsize(self) -> int:
        with self._cond:
            return len(self._heap)

    def task_done(self) -> None:
        """Kept for the worker written for `queue.Queue`."""


class DecisionGate:
    """What may call the model now: the dedup by VM, rule, gravity and source, and the ceiling of
    calls per minute — for every queue of the watch. `admit` reserves every call a decision may make
    (PRT1); `spent` gives back what it did not make, and opens the dedup's window when the decision
    contained or put a card before a human."""

    def __init__(self, *, window_s: float | None = None, per_min: int | None = None,
                 low_per_min: int | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.window_s = DEDUP_WINDOW_S if window_s is None else window_s
        self.per_min = MODEL_CALLS_PER_MIN if per_min is None else per_min
        self.low_per_min = LOW_CALLS_PER_MIN if low_per_min is None else low_per_min
        self._clock = clock
        self._lock = threading.Lock()
        self._decided: dict[tuple, float] = {}
        self._floored: dict[tuple, float] = {}
        # SEC-E: (VM, source) → {address: moment} of the critical detections admitted in a window.
        self._addresses: dict[tuple, dict[str, float]] = {}
        # (moment, low class?, floor?) of each call made in the last minute, counted from the end of
        # its decision; the floor's apart, never in the room of the others (PRT1).
        self._calls: deque[tuple[float, bool, bool]] = deque()
        # PRT1: ticket → (reserve, low class?, floor?) of each decision in flight — counted until it
        # ends, however long it takes.
        self._reserved: dict[int, tuple[int, bool, bool]] = {}
        self._tickets = itertools.count(1)

    def _key(self, data: dict) -> tuple:
        # SEC-E (V-02): by VM, rule, gravity and source — a compromise (COR1) too, whatever its
        # address: an address is for the card, never a new decision.
        return (str(data.get("resource_id") or "").lower(), str(_context(data).get("rule_name") or ""),
                gravity(data), _source(data))

    def _address_refused(self, data: dict, key: tuple, now: float) -> str:
        """SEC-E (V-02): why a critical detection's address may not call the model — "" when it may.
        At most `CRITICAL_ADDRESSES` distinct addresses per VM and source in a window."""
        addr = str(_row(data).get("SourceIP") or "")
        seen = self._addresses.setdefault((key[0], key[3]), {})
        for a in [a for a, t in seen.items() if now - t >= self.window_s]:
            del seen[a]
        if addr in seen or len(seen) < CRITICAL_ADDRESSES:
            return ""
        return (f"{len(seen)} adresses distinctes ont déjà eu une décision du modèle sur cette VM pour une "
                f"compromission dans les {int(self.window_s)} s (au plus {CRITICAL_ADDRESSES}) : celle-ci "
                "est nommée sur la carte, sans appel")

    def _admitted(self, data: dict, key: tuple, now: float) -> None:
        if key[2] == CRITICAL:
            self._addresses.setdefault((key[0], key[3]), {})[str(_row(data).get("SourceIP") or "")] = now

    def _recent(self, now: float) -> tuple[int, int, int]:
        """(the calls of the last minute and the reserves in flight, the low class's, the floor's).
        The floor's are in the total — the low class gives way to them — and never in the room of
        the grave ones (PRT1)."""
        while self._calls and self._calls[0][0] <= now - 60.0:
            self._calls.popleft()
        held = [(1, low, floor) for _, low, floor in self._calls]
        held += list(self._reserved.values())
        n = sum(r for r, _, _ in held)
        return n, sum(r for r, low, fl in held if low and not fl), sum(r for r, _, fl in held if fl)

    def reserve(self, data: dict, cls: int) -> int:
        """The calls a decision may make (PRT1): a rule proposal, one; a decision of `decide`,
        `decision_draws` (malformed: one — every disruptive action held, no draw), whatever its mode:
        read in `decide`, after the admission. Never more than its class's room — a decision always
        fits in an empty minute —, never less than one."""
        if data.get("event") == "detection_missed":
            return 1
        from glorfindel.config import decision_draws
        room = self.low_per_min if cls == LOW else self.per_min - self.low_per_min
        if turns := enquiry_turns(data):     # ENQ5b: a decision with an enquiry reserves its turns too
            return max(1, min((decision_draws() or 1) + turns, room))
        return max(1, min(decision_draws() or 1, room))

    @staticmethod
    def share(data: dict) -> int:
        """The calls a decision may make, whatever its class's room (PRT2: its share of the budget in
        dollars, which passes once it is admitted): a rule proposal one, a decision `decision_draws`."""
        if data.get("event") == "detection_missed":
            return 1
        from glorfindel.config import decision_draws
        return max(1, decision_draws() or 1) + enquiry_turns(data)      # ENQ5b: and its enquiry's turns

    def room_in(self) -> float:
        """Seconds until a call of the last minute ages out (at least one tenth) — at most
        `IN_FLIGHT_RECHECK_S` while a decision is in flight: its end may give its reserve back."""
        with self._lock:
            soon = IN_FLIGHT_RECHECK_S if self._reserved else 60.0
            if not self._calls:
                return 0.1 if not self._reserved else soon
            return max(0.1, min(soon, 60.0 - (self._clock() - self._calls[0][0])))

    def _floor(self, data: dict, confirmed: list[str], now: float) -> bool:
        """B3a's pair confirmed on the VM with this detection's facts: never held by the ceiling —
        once per pass of its rule and VM (its moment). The dedup still holds it (SEC-E, #644): once a
        decision opened the window, the floor's card is there. A detection only, as `decide`'s floor
        (PRT1): never a release, a rule proposal, an attack the monitoring missed. Not the
        RulePoller's (a line of the runs/ channel): once per VM and source in a window."""
        if data.get("event") != "detection":
            return False
        if not _FLOOR_PAIR <= set(confirmed) | set(facts_of(data)):
            return False
        vm = str(data.get("resource_id") or "").lower()
        key = ((vm, str(_context(data).get("rule_name") or ""), str(data.get("timestamp") or ""))
               if from_rulepoller(data) else (vm, "", _source(data)))
        at = self._floored.get(key)
        if at is not None and now - at < self.window_s:
            return False
        self._floored[key] = now
        for k in [k for k, t in self._floored.items() if now - t >= self.window_s]:
            del self._floored[k]
        return True

    def admit(self, data: dict, confirmed: list[str] | None = None, *, code: bool = False) -> tuple[str, str, int]:
        """("", "", ticket) when the detection may call the model — its reserve counted (`reserve`,
        PRT1) until `spent(data, state, ticket)` —; else (kind, why, 0): `same_pass`, `dedup`,
        `addresses`, `ceiling` — a card —, or `wait` — a grave or a critical one, or a release after
        a restore, the ceiling reached: back in its queue until the room comes back. What does not
        call the model reserves nothing: ("", "", 0). `confirmed`: what the VM's incident holds, live.
        `code` (PRT2): the decision goes the code's path, the budget in dollars refused its calls — the
        same pass, the dedup and the addresses hold it as before; the ceiling never (it makes no call):
        ("", "", 0)."""
        if not calls_model(data):
            return "", "", 0
        # V-13: the older lines of a pass, named beside its newest — never the model's.
        if _context(data).get("card_only"):
            return "same_pass", str(_context(data)["card_only"]), 0
        now = self._clock()
        key = self._key(data)
        cls = call_class(data)
        with self._lock:
            if from_rulepoller(data):
                at = self._decided.get(key)
                if at is not None and now - at < self.window_s:
                    return "dedup", (
                        f"dédoublonnée : la règle {key[1]} a déjà eu une décision du modèle sur cette "
                        f"VM il y a {int(now - at)} s, pour une détection de même gravité (une par "
                        f"fenêtre de {int(self.window_s)} s)"), 0
                if cls == CRITICAL:
                    why = self._address_refused(data, key, now)
                    if why:
                        return "addresses", why, 0
            if code:
                self._admitted(data, key, now)
                return "", "", 0
            reserve = self.reserve(data, cls)
            floor = True
            if not self._floor(data, confirmed or [], now):
                floor = False
                n, low, fl = self._recent(now)
                if cls == LOW:
                    limit = self.low_per_min
                    full = low + reserve > limit or n + reserve > self.per_min
                else:
                    # SEC-E (V-02): a critical one counts as a grave one — the room reserved, finite.
                    limit = self.per_min
                    full = n + reserve > limit and (n - low - fl) + reserve > self.per_min - self.low_per_min
                if full:
                    what = ("proposition de règle non faite (plafond) : relancer le scénario — "
                            if data.get("event") == "detection_missed" else "")
                    # PRT1: an attack the monitoring missed is never a card — it waits, in its class.
                    waits = cls != LOW or data.get("event") == "detection_timeout"
                    return ("wait" if waits else "ceiling"), (
                        f"{what}plafond des appels au modèle atteint ({n} dans la dernière minute, "
                        f"décisions en cours comprises, dont {low} de gravité basse ; celle-ci en réserve "
                        f"{reserve} ; au plus {limit} pour une détection de gravité {_CLASS_WORD[cls]})"), 0
            self._admitted(data, key, now)
            ticket = next(self._tickets)
            self._reserved[ticket] = (reserve, cls == LOW, floor)
            return "", "", ticket

    def spent(self, data: dict, state: dict | None, ticket: int = 0) -> None:
        """A decision ended (PRT1): its reserve given back, the calls it made (`calls_made`) counted
        from now — the safe side: never before they were made; and the dedup's window, opened by a
        decision that contained or put a card before a human. Its ticket first: a reserve is never
        left in flight, whatever its data became — taken and its calls counted under one lock: the
        decision is never counted nowhere (what reads files, the window and the key, before it)."""
        model = calls_model(data)
        opens = model and from_rulepoller(data) and opens_window(state)
        key = self._key(data) if opens else None
        now = self._clock()
        with self._lock:
            held = self._reserved.pop(ticket, None) if ticket else None
            if held is None and not model:
                return
            reserve, low, floor = held or (0, call_class(data) == LOW, False)
            used = calls_made(data, state, reserve)
            self._calls.extend([(now, low, floor)] * used)
            if key is not None:
                self._decided[key] = now
                for k in [k for k, t in self._decided.items() if now - t >= self.window_s]:
                    del self._decided[k]


# ── The card without a decision of the model ──────────────────────────────────────────────────

_SEEN_LOCK = threading.Lock()
# (vm, rule, source) → the latest detections without a decision, and the count of each reason.
_SEEN: dict[tuple, tuple[deque, dict]] = {}
_KIND_WORD = {"dedup": "dédoublonnées", "same_pass": "même passe", "ceiling": "au-delà du plafond",
              "full": "file pleine", "addresses": "adresses au-delà du plafond",
              # PRT2: the budget in dollars (glorfindel/model_budget.py).
              "budget": "au-delà du budget du réel", "exercise_budget": "exercice en pause (budget)",
              "provider_limit": "limite du fournisseur"}

_LABEL_COLUMNS = ("SourceIP", "CallerIpAddress", "IPAddress", "LoginAccount", "Account", "TargetAccount",
                  "UserName", "AuditCommand", "SyslogMessage", "_ResourceId")


def row_label(row: dict) -> str:
    """One line for a row on a card: its time and the columns that tell it apart, cut short."""
    if not isinstance(row, dict):
        return ""
    parts = [str(row.get("TimeGenerated") or "")] if row.get("TimeGenerated") else []
    for col in _LABEL_COLUMNS:
        v = row.get(col)
        if isinstance(v, str) and v:
            parts.append(f"{col}={v[:120]}")
    if not parts:
        parts = [f"{k}={v[:60]}" for k, v in sorted(row.items())
                 if isinstance(v, str) and v][:4]
    return " ".join(parts)[:300]


def row_labels(row: dict) -> tuple[list[str], int]:
    """The rows a signal carries, one line each, and how many they are: its own, or — a summary
    (SEC2, V-13) — each row it names, at most `CARD_ROWS`, then how many it leaves out."""
    if not isinstance(row, dict):
        return [], 1
    omitted = row.get("OmittedRows")
    if not isinstance(omitted, list) or not omitted:
        return [row_label(row)], 1
    labels = [row_label(r) for r in omitted[:CARD_ROWS]]
    try:
        total = max(int(row.get("OmittedCount") or 0), len(omitted))
    except (TypeError, ValueError):
        total = len(omitted)
    if total > len(labels):
        labels.append(f"… et {total - len(labels)} ligne(s) de plus")
    return labels, total


_UNDECIDED_STEPS = (
    "Lire les lignes que la carte nomme : chacune est une détection que le modèle n'a pas vue.",
    "Une rafale de lignes forgées par un compte local de la VM se dédoublonne ainsi : "
    "chercher qui les écrit, et la vraie détection parmi elles.",
    "Agir à la main si l'une d'elles le demande : aucune action ne part seule d'une "
    "détection non décidée, et cette carte n'en propose aucune.",
)
# PRT1: a rule proposal beyond the ceiling is not made, and nothing asks for it again.
_MISSED_STEPS = (
    "Aucune règle n'a été proposée : le plafond des appels au modèle était atteint, et rien ne "
    "redemande la proposition.",
    "Relancer le scénario de l'exercice quand la watch est plus calme : sa détection manquée "
    "redemandera une proposition de règle.",
    "Ou écrire la règle à la main dans la couche du client, pour la technique que la carte nomme.",
)
# PRT2: a detection the budget in dollars, or the provider's limit, kept from the model.
_BUDGET_STEPS = (
    "Lire la détection : le modèle ne l'a pas vue, son budget du jour (ou la limite du fournisseur) "
    "est atteint ; aucune action n'en est partie.",
    "Agir à la main si elle le demande. Le budget se remet à zéro à minuit UTC ; le relever se fait "
    "par les variables GLORFINDEL_MODEL_* et un redémarrage de la watch (docs/operations.md).",
    "Un exercice en pause reprend avec le budget du jour suivant ; le réel n'attend jamais un exercice.",
)
_BUDGET_KINDS = ("budget", "exercise_budget", "provider_limit")


def record_undecided(data: dict, kind: str, why: str, *, dry_run: bool = False) -> str:
    """A detection that does not call the model (dedup, ceiling, queue full): a card
    `undecided_detection`, no action — one per VM and rule, naming its latest detections
    (`CARD_ROWS`) and how many there are for each reason. Its id, or "" in dry-run."""
    ctx = _context(data)
    rule = str(ctx.get("rule_name") or "")
    raw = data.get("raw_signal") if isinstance(data.get("raw_signal"), dict) else {}
    labels, n = row_labels(raw.get("first_result_row") or raw.get("detected_data") or {})
    from glorfindel.agent import _card_attribution, _card_target, _cycle_source
    source, exercise_run = _cycle_source(data)
    key = (str(data.get("resource_id") or "").lower(), rule, source)
    with _SEEN_LOCK:
        latest, counts = _SEEN.setdefault(key, (deque(maxlen=CARD_ROWS + 1), {}))
        for label in reversed(labels or [""]):
            latest.appendleft(f"[{_KIND_WORD.get(kind, kind)}] {label}".strip())
        counts[kind] = counts.get(kind, 0) + n
        named = list(latest)
        said = ", ".join(f"{n} {_KIND_WORD.get(k, k)}" for k, n in sorted(counts.items()))
    if dry_run:
        return ""
    reason = (
        f"Détection non décidée par le modèle — {why}. Aucune action, ni enquête : triage humain. "
        f"Règle {rule or '(sans règle)'}, technique {data.get('ttp') or '?'}. Depuis le démarrage "
        f"de la watch : {said}. Les plus récentes : " + " · ".join(named))
    from glorfindel import escalations
    return escalations.record(
        signal_id=str(data.get("signal_id") or ""),
        resource_id=str(data.get("resource_id") or ""),
        action="",
        escalation_type="undecided_detection",
        reason=reason,
        run_id=str(ctx.get("run_id") or ""),
        suggested_steps=list(_BUDGET_STEPS if kind in _BUDGET_KINDS else _MISSED_STEPS
                             if data.get("event") == "detection_missed" else _UNDECIDED_STEPS),
        ttp=str(data.get("ttp") or ""),
        severity=str(data.get("severity") or ""),
        rule_name=rule,
        source=source,
        exercise_run=exercise_run,
        target=_card_target(data),
        attribution=_card_attribution(data),        # SLF1: a detection attributed to no VM says so
    )



def keep_facts(data: dict, incidents) -> None:
    """A held detection's facts on its VM's incident (B3a): the floor of a later detection reads
    them as it would have read a decided one's. Never a signal of the incident (SEC-E, V-03): its
    TTL is not prolonged, its count not raised — an incident is opened for them only when the VM
    has none. Never raises."""
    facts = facts_of(data)
    if not facts or incidents is None:
        return
    try:
        incidents.confirm(str(data.get("resource_id") or ""), facts, ttp=str(data.get("ttp") or ""),
                          open_new=True)
    except Exception:
        pass


def _confirmed_on_vm(data: dict, incidents) -> list[str]:
    if incidents is None or not calls_model(data):
        return []
    try:
        inc = incidents.get_active(str(data.get("resource_id") or ""))
    except Exception:
        return []
    from glorfindel.incidents import live_facts
    return live_facts(inc) if inc is not None else []


def decide_or_card(data: dict, respond: Callable[[dict], dict], gate: DecisionGate, *,
                   dry_run: bool = False, incidents=None, budget=None) -> tuple[dict | None, str, float]:
    """One detection taken from its queue: (state, why, wait_s). The decision (`respond`, the
    graph); or — same pass, dedup, ceiling of the low class — its card without a decision of the
    model, and no call; or — a grave one, the ceiling reached — `wait_s` > 0: back in its queue
    until the room comes back. A held detection's facts go to its VM's incident (B3a).

    `budget` (PRT2, glorfindel/model_budget.py, the watch's): judged first, before the gate takes a
    reserve — an ordinary beyond its budget, an exercise beyond its own, a card; a grave one, the code's
    path (`respond` all the same, its calls refused: `decide` builds its decision without the model);
    the provider's limit, a grave one waits its cool-down. Admitted, its share is the decision's while
    `respond` runs (`bound`), and given back at its end."""
    try:
        verdict = budget.judge(data, DecisionGate.share(data)) if budget is not None and calls_model(data) else None
    except Exception:       # never a detection lost to the breaker: its calls still checked one by one
        verdict = None
    if verdict is not None and verdict.kind in ("card", "wait"):
        keep_facts(data, incidents)         # B3a: its facts never lost, whatever held it
        if verdict.kind == "wait":
            return None, verdict.why, verdict.wait_s
        record_undecided(data, verdict.card, verdict.why, dry_run=dry_run)
        return None, verdict.why, 0.0
    code = verdict is not None and verdict.kind == "code"
    try:
        kind, why, ticket = gate.admit(data, _confirmed_on_vm(data, incidents), code=code)
    except BaseException:
        if verdict is not None:
            budget.done(verdict)            # PRT2: a share never left in flight, whatever raised
        raise
    if kind:
        if verdict is not None:
            budget.done(verdict)            # PRT2: never admitted — its share given back
        keep_facts(data, incidents)
        if kind == "wait":
            return None, why, gate.room_in()
        record_undecided(data, kind, why, dry_run=dry_run)
        return None, why, 0.0
    if verdict is not None:
        respond = budget.bound(verdict, respond)    # PRT2: its share given back at its end, raised or not
    state = None
    try:
        state = respond(data)
    finally:
        gate.spent(data, state, ticket)     # PRT1: its reserve given back, whether it ended or raised
    return state, "", 0.0
