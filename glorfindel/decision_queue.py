"""The watch's decision queue, bounded (SEC-A2, #631; audit of 06/11, V-03 and V-13).

Every detection the RulePoller dispatches waits in its VM's queue for a decision, and a decision
of the data plane is a call to the model (one in `human_only`, up to `decision_draws` when a
disruptive action would run alone). A row aggregated by its text columns is one detection per
value: a local account on a watched VM that writes lines with twenty new addresses each pass made
twenty detections per pass — 720 decisions an hour on one VM, ~2 160 calls, and a real ransomware
detection waited behind them for hours. Four bounds, before any call to the model:

- **the queue of a VM is bounded** (`QUEUE_MAX`): beyond, the least grave and newest detection
  waiting — or the one that comes, if it is no graver — leaves the queue; it gets a card without a
  decision of the model, said on the watch's console and counted on that card, never in silence;
- **the gravest first** (`gravity`): a critical detection, then one of a grave technique
  (`GRAVE_TTPS`), then the others — each class first come, first served; a grave detection never
  waits behind a lower one (only behind the cycle in flight: its investigation, its draws, its
  action and its check, each bounded);
- **one decision of the model per VM, rule, gravity and source in a window** (`DEDUP_WINDOW_S`),
  opened only by a decision that contained or put a card before a human: the other detections of
  that rule on that VM in the window are deduplicated — a card that names them, and no call. A
  critical one (COR1) is keyed by its address too: one decision per address;
- **a ceiling of calls to the model per minute**, for the whole watch (`MODEL_CALLS_PER_MIN`),
  each class counted apart, draws included: the low class at most `LOW_CALLS_PER_MIN`, the grave
  ones the rest whatever the low class did. Beyond it a low detection is a card, never an action;
  a grave one waits in its queue until the room comes back; a critical one is never held by it.

What B3a's floor needs is never lost: a detection that confirms a fact on its VM (a brute force
that succeeded, a sudo to root) writes it on the VM's incident even when it is held; and once both
are confirmed on the VM, its detection is never held (one per pass of its rule and VM) — the floor,
deterministic, plays outside the bounds.

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
# The lines a card of `undecided_detection` names, the latest first (as AUD1's fold, FOLD_MAX);
# beyond, their number.
CARD_ROWS = 20

CRITICAL, GRAVE, LOW = 0, 1, 2
_CLASS_WORD = {CRITICAL: "critique", GRAVE: "grave", LOW: "basse"}
# B3a's pair: both confirmed on a VM, its floor isolates whatever the model chose.
_FLOOR_PAIR = frozenset({"login_after_brute_force", "root_elevation"})


def gravity(data: dict) -> int:
    """The class a detection waits in: CRITICAL (its severity says so — a compromise, COR1), GRAVE
    (a technique of `GRAVE_TTPS`), LOW (the others)."""
    if str(data.get("severity") or "").lower() == "critical":
        return CRITICAL
    ttp = str(data.get("ttp") or "").upper()
    if ttp in GRAVE_TTPS or ttp.split(".", 1)[0] in GRAVE_TTPS:
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
    """A detection of the data plane: its decision is the model's. A card of the control plane or
    of an identity is decided by the code (AL1, C2)."""
    return data.get("event") == "detection" and _context(data).get("plane") not in ("control", "identity")


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
    that comes, when it is no graver — is handed to `on_drop(item, why)`, which says it. `put_back`
    puts a detection back in its place, held until a moment (a grave one, the ceiling reached):
    meanwhile, the others are taken."""

    def __init__(self, maxsize: int | None = None,
                 on_drop: Callable[[tuple, str], None] | None = None,
                 classify: Callable[[tuple], int] | None = None) -> None:
        self._max = QUEUE_MAX if maxsize is None else maxsize
        self._on_drop = on_drop
        self._classify = classify or (lambda item: gravity(item[0]))
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
            worst = max(self._heap)
            if cls < worst[0]:
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
    calls per minute — for every queue of the watch. `admit` reserves one call; `spent` adds the
    others a decision drew (the draws of D-1), and opens the dedup's window when the decision
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
        # (moment, low class?) of each call of the last minute.
        self._calls: deque[tuple[float, bool]] = deque()

    def _key(self, data: dict) -> tuple:
        cls = gravity(data)
        # COR1: one decision per address — a compromise from another address is another one.
        addr = str(_row(data).get("SourceIP") or "") if cls == CRITICAL else ""
        return (str(data.get("resource_id") or "").lower(), str(_context(data).get("rule_name") or ""),
                cls, _source(data), addr)

    def _recent(self, now: float) -> tuple[int, int]:
        """(all the calls of the last minute, the low class's)."""
        while self._calls and self._calls[0][0] <= now - 60.0:
            self._calls.popleft()
        return len(self._calls), sum(1 for _, low in self._calls if low)

    def room_in(self) -> float:
        """Seconds until a call of the last minute ages out (at least one tenth)."""
        with self._lock:
            if not self._calls:
                return 0.1
            return max(0.1, 60.0 - (self._clock() - self._calls[0][0]))

    def _floor(self, data: dict, confirmed: list[str], now: float) -> bool:
        """B3a's pair confirmed on the VM with this detection's facts: never held — once per pass
        of its rule and VM (its moment)."""
        if not _FLOOR_PAIR <= set(confirmed) | set(facts_of(data)):
            return False
        key = (str(data.get("resource_id") or "").lower(), str(_context(data).get("rule_name") or ""),
               str(data.get("timestamp") or ""))
        if key in self._floored:
            return False
        self._floored[key] = now
        for k in [k for k, t in self._floored.items() if now - t >= self.window_s]:
            del self._floored[k]
        return True

    def admit(self, data: dict, confirmed: list[str] | None = None) -> tuple[str, str]:
        """("", "") when the detection may call the model (one call reserved); else (kind, why):
        `same_pass`, `dedup`, `ceiling` — a card —, or `wait` — a grave one, the ceiling reached:
        back in its queue until the room comes back. `confirmed`: what the VM's incident holds."""
        if not calls_model(data):
            return "", ""
        # V-13: the older lines of a pass, named beside its newest — never the model's.
        if _context(data).get("card_only"):
            return "same_pass", str(_context(data)["card_only"])
        now = self._clock()
        key = self._key(data)
        cls = key[2]
        with self._lock:
            if not self._floor(data, confirmed or [], now):
                if from_rulepoller(data):
                    at = self._decided.get(key)
                    if at is not None and now - at < self.window_s:
                        return "dedup", (
                            f"dédoublonnée : la règle {key[1]} a déjà eu une décision du modèle sur cette "
                            f"VM il y a {int(now - at)} s, pour une détection de même gravité (une par "
                            f"fenêtre de {int(self.window_s)} s)")
                n, low = self._recent(now)
                if cls == LOW:
                    limit = self.low_per_min
                    full = low >= limit or n >= self.per_min
                elif cls == GRAVE:
                    limit = self.per_min
                    full = n >= limit and (n - low) >= self.per_min - self.low_per_min
                else:
                    limit, full = self.per_min, False          # COR1: never held by the ceiling
                if full:
                    return ("ceiling" if cls == LOW else "wait"), (
                        f"plafond des appels au modèle atteint ({n} dans la dernière minute, dont {low} "
                        f"de gravité basse ; au plus {limit} pour une détection de gravité "
                        f"{_CLASS_WORD[cls]})")
            self._calls.append((now, cls == LOW))
            return "", ""

    def spent(self, data: dict, state: dict | None) -> None:
        """The calls a decision drew beyond the one `admit` reserved (the draws of D-1); and the
        dedup's window, opened by a decision that contained or put a card before a human."""
        if not calls_model(data) or not isinstance(state, dict):
            return
        more = max(0, len(state.get("decision_draws") or []) - 1)
        opens = from_rulepoller(data) and opens_window(state)
        key = self._key(data) if opens else None
        now = self._clock()
        with self._lock:
            self._calls.extend([(now, gravity(data) == LOW)] * more)
            if key is not None:
                self._decided[key] = now
                for k in [k for k, t in self._decided.items() if now - t >= self.window_s]:
                    del self._decided[k]


# ── The card without a decision of the model ──────────────────────────────────────────────────

_SEEN_LOCK = threading.Lock()
# (vm, rule, source) → the latest detections without a decision, and the count of each reason.
_SEEN: dict[tuple, tuple[deque, dict]] = {}
_KIND_WORD = {"dedup": "dédoublonnées", "same_pass": "même passe", "ceiling": "au-delà du plafond",
              "full": "file pleine"}

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


def record_undecided(data: dict, kind: str, why: str, *, dry_run: bool = False) -> str:
    """A detection that does not call the model (dedup, ceiling, queue full): a card
    `undecided_detection`, no action — one per VM and rule, naming its latest detections
    (`CARD_ROWS`) and how many there are for each reason. Its id, or "" in dry-run."""
    ctx = _context(data)
    rule = str(ctx.get("rule_name") or "")
    raw = data.get("raw_signal") if isinstance(data.get("raw_signal"), dict) else {}
    labels, n = row_labels(raw.get("first_result_row") or raw.get("detected_data") or {})
    from glorfindel.agent import _card_target, _cycle_source
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
        suggested_steps=[
            "Lire les lignes que la carte nomme : chacune est une détection que le modèle n'a pas vue.",
            "Une rafale de lignes forgées par un compte local de la VM se dédoublonne ainsi : "
            "chercher qui les écrit, et la vraie détection parmi elles.",
            "Agir à la main si l'une d'elles le demande : aucune action ne part seule d'une "
            "détection non décidée, et cette carte n'en propose aucune.",
        ],
        ttp=str(data.get("ttp") or ""),
        severity=str(data.get("severity") or ""),
        rule_name=rule,
        source=source,
        exercise_run=exercise_run,
        target=_card_target(data),
    )



def keep_facts(data: dict, incidents) -> None:
    """A held detection's facts on its VM's incident (B3a): the floor of a later detection reads
    them as it would have read a decided one's. Never raises."""
    facts = facts_of(data)
    if not facts or incidents is None:
        return
    rid = str(data.get("resource_id") or "")
    try:
        incidents.get_or_create(resource_id=rid, ttp=str(data.get("ttp") or ""))
        incidents.confirm(rid, facts)
    except Exception:
        pass


def _confirmed_on_vm(data: dict, incidents) -> list[str]:
    if incidents is None or not calls_model(data):
        return []
    try:
        inc = incidents.get_active(str(data.get("resource_id") or ""))
    except Exception:
        return []
    kept = getattr(inc, "confirmed", None) if inc is not None else None
    return list(kept) if isinstance(kept, list) else []


def decide_or_card(data: dict, respond: Callable[[dict], dict], gate: DecisionGate, *,
                   dry_run: bool = False, incidents=None) -> tuple[dict | None, str, float]:
    """One detection taken from its queue: (state, why, wait_s). The decision (`respond`, the
    graph); or — same pass, dedup, ceiling of the low class — its card without a decision of the
    model, and no call; or — a grave one, the ceiling reached — `wait_s` > 0: back in its queue
    until the room comes back. A held detection's facts go to its VM's incident (B3a)."""
    kind, why = gate.admit(data, _confirmed_on_vm(data, incidents))
    if kind:
        keep_facts(data, incidents)
        if kind == "wait":
            return None, why, gate.room_in()
        record_undecided(data, kind, why, dry_run=dry_run)
        return None, why, 0.0
    state = respond(data)
    gate.spent(data, state)
    return state, "", 0.0
