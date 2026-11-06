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
  waits behind a lower one (only behind the decision in flight, bounded by the model's timeout);
- **one decision of the model per VM, rule and gravity in a window** (`DEDUP_WINDOW_S`): the other
  detections of that rule on that VM in the window are deduplicated — a card that names them,
  without a decision of the model, and no call;
- **a ceiling of calls to the model per minute**, for the whole watch (`MODEL_CALLS_PER_MIN`), of
  which the low class takes at most `LOW_CALLS_PER_MIN`: a burst of low detections never uses the
  room of a grave one. Beyond: a card without a decision of the model, never an action.

A detection with no decision of the model is a card `undecided_detection` (`record_undecided`):
no action, no investigation, nothing in the memory; the card of a VM and a rule names the latest of
them, and how many there are, for each reason. Only what calls the model is held by these bounds:
a card of the control plane or of an identity is decided by the code (AL1, C2), never by the model.
"""
from __future__ import annotations

import heapq
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


def calls_model(data: dict) -> bool:
    """A detection of the data plane: its decision is the model's. A card of the control plane or
    of an identity is decided by the code (AL1, C2)."""
    return data.get("event") == "detection" and _context(data).get("plane") not in ("control", "identity")


def from_rulepoller(data: dict) -> bool:
    """A detection of the RulePoller: its synthetic run (`watch-<rule>-<ts>`) and its rule."""
    ctx = _context(data)
    return str(ctx.get("run_id") or "").startswith("watch-") and bool(ctx.get("rule_name"))


class DecisionQueue:
    """A VM's queue: the gravest first, first come first served in a class; bounded.

    `put` never blocks: beyond `maxsize`, the least grave and newest waiting detection — or the one
    that comes, when it is no graver — is handed to `on_drop(item, why)`, which says it."""

    def __init__(self, maxsize: int | None = None,
                 on_drop: Callable[[tuple, str], None] | None = None,
                 classify: Callable[[tuple], int] | None = None) -> None:
        self._max = QUEUE_MAX if maxsize is None else maxsize
        self._on_drop = on_drop
        self._classify = classify or (lambda item: gravity(item[0]))
        self._heap: list[tuple[int, int, tuple]] = []
        self._seq = itertools.count()
        self._cond = threading.Condition()
        self.dropped = 0

    def put(self, item: tuple) -> bool:
        """False when the item did not enter (the queue full, and it is no graver)."""
        cls = self._classify(item)
        dropped = None
        with self._cond:
            entry = (cls, next(self._seq), item)
            if len(self._heap) >= self._max:
                worst = max(self._heap)
                if cls < worst[0]:
                    self._heap.remove(worst)
                    heapq.heapify(self._heap)
                    heapq.heappush(self._heap, entry)
                    dropped = worst
                else:
                    dropped = entry
                self.dropped += 1
            else:
                heapq.heappush(self._heap, entry)
            self._cond.notify()
        if dropped is not None and self._on_drop is not None:
            self._on_drop(dropped[2], (
                f"la file de cette VM tient déjà {self._max} détections : celle-ci, de gravité "
                f"{_CLASS_WORD.get(dropped[0], dropped[0])}, en sort sans décision du modèle"))
        return dropped is None or dropped[2] is not item

    def get(self, timeout: float | None = None) -> tuple:
        with self._cond:
            if not self._cond.wait_for(lambda: self._heap, timeout):
                raise TimeoutError("decision queue empty")
            return heapq.heappop(self._heap)[2]

    def qsize(self) -> int:
        with self._cond:
            return len(self._heap)

    def task_done(self) -> None:
        """Kept for the worker written for `queue.Queue`."""


class DecisionGate:
    """What may call the model now: the dedup by VM, rule and gravity, and the ceiling of calls per
    minute — for every queue of the watch. `admit` reserves one call; `spent` adds the others a
    decision drew (the draws of D-1)."""

    def __init__(self, *, window_s: float | None = None, per_min: int | None = None,
                 low_per_min: int | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.window_s = DEDUP_WINDOW_S if window_s is None else window_s
        self.per_min = MODEL_CALLS_PER_MIN if per_min is None else per_min
        self.low_per_min = LOW_CALLS_PER_MIN if low_per_min is None else low_per_min
        self._clock = clock
        self._lock = threading.Lock()
        self._decided: dict[tuple, float] = {}
        self._calls: deque[float] = deque()

    def _key(self, data: dict) -> tuple:
        return (str(data.get("resource_id") or "").lower(), str(_context(data).get("rule_name") or ""),
                gravity(data))

    def _recent_calls(self, now: float) -> int:
        while self._calls and self._calls[0] <= now - 60.0:
            self._calls.popleft()
        return len(self._calls)

    def admit(self, data: dict) -> tuple[str, str]:
        """("", "") when the detection may call the model (one call reserved); else (kind, why) —
        `dedup` or `ceiling` — and it must not."""
        if not calls_model(data):
            return "", ""
        # V-13: the older lines of a pass, named beside its newest — never the model's.
        if _context(data).get("card_only"):
            return "dedup", str(_context(data)["card_only"])
        now = self._clock()
        with self._lock:
            key = self._key(data)
            if from_rulepoller(data):
                at = self._decided.get(key)
                if at is not None and now - at < self.window_s:
                    return "dedup", (
                        f"dédoublonnée : la règle {key[1]} a déjà eu une décision du modèle sur cette VM "
                        f"il y a {int(now - at)} s, pour une détection de même gravité (une par fenêtre "
                        f"de {int(self.window_s)} s)")
            cls = key[2]
            limit = self.low_per_min if cls == LOW else self.per_min
            n = self._recent_calls(now)
            if n >= limit:
                return "ceiling", (
                    f"plafond des appels au modèle atteint ({n} dans la dernière minute ; au plus "
                    f"{limit} pour une détection de gravité {_CLASS_WORD[cls]})")
            self._calls.append(now)
            if from_rulepoller(data):
                self._decided[key] = now
                for k in [k for k, t in self._decided.items() if now - t >= self.window_s]:
                    del self._decided[k]
            return "", ""

    def spent(self, data: dict, state: dict | None) -> None:
        """The calls a decision drew beyond the one `admit` reserved (the draws of D-1)."""
        if not calls_model(data) or not isinstance(state, dict):
            return
        more = max(0, len(state.get("decision_draws") or []) - 1)
        if more:
            now = self._clock()
            with self._lock:
                self._calls.extend([now] * more)


# ── The card without a decision of the model ──────────────────────────────────────────────────

_SEEN_LOCK = threading.Lock()
# (vm, rule, source) → the latest detections without a decision, and the count of each reason.
_SEEN: dict[tuple, tuple[deque, dict]] = {}
_KIND_WORD = {"dedup": "dédoublonnées", "ceiling": "au-delà du plafond", "full": "file pleine"}

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


def decide_or_card(data: dict, respond: Callable[[dict], dict], gate: DecisionGate, *,
                   dry_run: bool = False) -> tuple[dict | None, str]:
    """One detection taken from its queue: the decision (`respond`, the graph), or — dedup or
    ceiling — its card without a decision of the model, and no call. (state, why)."""
    kind, why = gate.admit(data)
    if kind:
        record_undecided(data, kind, why, dry_run=dry_run)
        return None, why
    state = respond(data)
    gate.spent(data, state)
    return state, ""
