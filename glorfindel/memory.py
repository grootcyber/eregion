"""The memory of past cycles: the precedents `load_context` gives the model (docs/glorfindel.md).

MEM2 (#1027, decision of Jonathan of 23/11): two memories behind one switch, ``GLORFINDEL_MEMORY``,
the operator's, read when a memory is opened (`CycleMemory`):

- ``distance`` — the default, unset or empty: today's memory, ChromaDB (`DistanceMemory`, below), the
  same rule, then the same VM, then the distance of the text. Off, nothing changes: the same store, the
  same precedents, the same message to the model, to the byte (tests/unit/test_memory_keys.py);
- ``cles`` — the memory by keys and by date (glorfindel/memory_keys.py, SQLite): the same rule, then
  the same VM, then the same technique, then the newest. Switched on with ENQ5 only, after the
  harness's session (MEM-H) and Jonathan's run end to end: measured before it is switched on.

Any other value keeps today's memory, and is said (on stderr, once): an unreadable switch never cuts
the memory, never makes the watch fall. It is an environment variable, not a key of the config: the
config is read strictly — an unknown value would refuse the whole file, and the watch would decide
every VM in human_only — and the console rewrites it (the autonomy of an asset); the switch is the
operator's alone, set where the watch starts (host.env on Imladris), and given to the watch only.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import uuid
from pathlib import Path

from eregion_core import store_guard

_DEFAULT_PATH = Path.home() / ".glorfindel" / "cycles"
# How many more cycles the retrieval reads than it returns, so that the copies of a
# replayed cycle, dropped, still leave N distinct ones.
_DUPLICATE_SLACK = 4
# SEC17 (V-12): how old a past cycle may be to be given as a precedent — 90 days unless the
# config says otherwise (`memory.max_age_days`, glorfindel/config.py), never more than ten years.
DEFAULT_MAX_AGE_DAYS = 90.0
MAX_AGE_CEILING_DAYS = 3650.0
_DAY_S = 86400
# SEC17 (V-12, decision of Jonathan, 03/11): the date given to a real cycle stored before cycles
# were dated (no `stored_at`). A cycle is `real` only since B2 — commit d4e51fa, 2026-10-16
# 14:30 +0200, « chaque cycle sait s'il vient d'un exercice » — and the only writer of this
# collection is `store`: before B2 no cycle carried `source`, and the search takes `source=real`
# only (a cycle without the field is left out by the filter). So no real cycle is older than B2.
# Midnight UTC that day, earlier than the commit: such a cycle is given an age at least its true
# one (A0), never today's, never a date it carries. With the default bound, kept until about
# 2027-01-14, then aged out.
B2_FLOOR = 1792108800          # 2026-10-16T00:00:00Z
# SEC-I (V-11): at most this many precedents from one VM. A local account on a VM provokes
# detections at will, and each decided one is stored: a flood of its cycles filled the three
# places of every detection of the same technique, on any VM. A cycle that names no VM (stored
# before SEC-I, or of a detection attributed to none) counts as one VM, unknown.
PER_VM = 1
# MEM2 (#1027): the switch, and the memories it names.
SWITCH = "GLORFINDEL_MEMORY"
DISTANCE, KEYS = "distance", "cles"
MODES = (DISTANCE, KEYS)
_said_switch: set[str] = set()


def memory_mode(env=None) -> tuple[str, str]:
    """(the memory the switch names, what is said of it — "" when nothing is). Unset or empty:
    ``distance``, today's. ``distance`` or ``cles``, spaces around aside: that one. Anything else:
    ``distance`` — today's memory, never none — and said."""
    raw = (os.environ if env is None else env).get(SWITCH)
    value = raw.strip() if isinstance(raw, str) else ""
    if value in MODES:
        return value, ""
    if not value:
        return DISTANCE, ""
    shown = "".join(c if c.isprintable() else "?" for c in raw)[:40]
    return DISTANCE, (f"{SWITCH}={shown!r} inconnu (attendu : {DISTANCE} ou {KEYS}) — la mémoire d'aujourd'hui "
                      f"({DISTANCE}) est gardée")


def CycleMemory(path: str | Path | None = None, max_age_days: float | None = None, clock=time.time,  # noqa: N802
                mode: str | None = None):
    """The memory of past cycles the switch names (MEM2): `DistanceMemory` (ChromaDB, today's) or, with
    ``GLORFINDEL_MEMORY=cles``, `memory_keys.KeyedMemory` (SQLite). ``mode`` given wins over the switch
    (a test, the harness). One interface: `store`, `retrieve_similar`, `age_census`, `count`, `said`."""
    if mode is None:
        mode, said = memory_mode()
        if said and said not in _said_switch:
            _said_switch.add(said)
            print(f"⚠ {said}", file=sys.stderr)
    if mode == KEYS:
        from glorfindel.memory_keys import KeyedMemory
        return KeyedMemory(path=path, max_age_days=max_age_days, clock=clock)
    if mode != DISTANCE:
        raise ValueError(f"une mémoire {DISTANCE} ou {KEYS} est attendue, pas {mode!r}")
    return DistanceMemory(path=path, max_age_days=max_age_days, clock=clock)


def checked_max_age(days) -> float:
    """``days`` as a bound of age: a finite number, positive, at most the ceiling — else ValueError."""
    if isinstance(days, bool) or not isinstance(days, (int, float)):
        raise ValueError(f"un nombre de jours est attendu, pas {days!r}")
    if not math.isfinite(days) or not 0 < days <= MAX_AGE_CEILING_DAYS:
        raise ValueError(f"un nombre de jours entre 0 (exclu) et {MAX_AGE_CEILING_DAYS:g} est attendu, pas {days}")
    return float(days)


class DistanceMemory:
    """Persistent vector store for Glorfindel decision cycles — the memory by distance (ChromaDB),
    today's: what `CycleMemory` opens while the switch is off (MEM2).

    Each cycle is (signal → reasoning → action → outcome).
    At decision time, retrieve the N most similar past cycles as context.
    No model weights change — the LLM learns from context, not fine-tuning.
    """

    def __init__(self, path: str | Path | None = None, max_age_days: float | None = None,
                 clock=time.time):
        import chromadb

        # SEC17 (V-12): the age past which a cycle is no precedent; the clock that dates a cycle
        # when it is stored, and measures its age at retrieval — Glorfindel's, never the signal's.
        self.max_age_days = checked_max_age(DEFAULT_MAX_AGE_DAYS if max_age_days is None else max_age_days)
        self._clock = clock
        storage_path = Path(path) if path else _DEFAULT_PATH
        # HY2b (#791): ChromaDB writes its store from Rust, which the guard's audit hook never sees —
        # in an agent session, the operator's ~/.glorfindel/cycles is refused before it is opened.
        store_guard.check(storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(storage_path))
        self._collection = self._client.get_or_create_collection(
            name="cycles",
            metadata={"hnsw:space": "cosine"},
        )
        self.path = storage_path

    mode = DISTANCE

    def said(self) -> str:
        """Which memory this is, and where (MEM2): `glorfindel memory-stats`."""
        return f"memory by distance (ChromaDB): {self.path}"

    def store(self, cycle: dict) -> None:
        """Persist a completed cycle, under an identifier of its own (SEC4a, V-12).

        Drawn here, never taken from the signal: a cycle is added, never overwritten.
        The copies of a replayed cycle are folded at retrieval (`retrieve_similar`)."""
        cycle_id = f"cycle-{uuid.uuid4().hex}"
        document = _cycle_to_text(cycle)
        self._collection.add(
            ids=[cycle_id],
            documents=[document],
            metadatas=[{
                "ttp": cycle.get("ttp", ""),
                "action": cycle.get("action", ""),
                "outcome": str(cycle.get("outcome", "")),
                "signal_id": cycle.get("signal_id", ""),
                "run_id": cycle.get("run_id", ""),
                # B2: `exercise` or `real` (eregion_core/exercise.py) — shown to the model
                # with each past cycle, and what the retrieval filters on (SEC4a).
                "source": cycle.get("source", ""),
                "exercise_run": cycle.get("exercise_run", ""),
                "event": cycle.get("event", ""),
                "detection_s": cycle.get("detection_s", 0),
                "action_s": cycle.get("action_s", 0),
                "confidence": float(cycle.get("confidence", 0.0)),
                "past_cycles_used": json.dumps(cycle.get("past_cycles_used", [])),
                # SEC17 (V-12): when the cycle was stored, by this host's clock — its age at
                # retrieval. Never taken from the cycle: a log line does not date a precedent.
                "stored_at": int(self._clock()),
                # SEC-I (V-11): the VM (lowered: one key whatever the case it came in) and the
                # rule of the cycle, which the retrieval weighs and bounds — never shown to the
                # model (its text is the document); and whether its signal was corroborated by
                # a source the VM does not write. None is before SEC-A3 (#632): every cycle is
                # stored as not corroborated, and said so; the retrieval does not filter on it
                # yet — it would leave every decision without a precedent.
                "resource_id": _vm_key(cycle.get("resource_id")),
                "rule_name": str(cycle.get("rule_name") or ""),
                "corroborated": cycle.get("corroborated") is True,
            }],
        )

    def _cutoff(self) -> int:
        """The oldest ``stored_at`` a precedent may carry (SEC17, V-12)."""
        return int(self._clock() - self.max_age_days * _DAY_S)

    def _b2_within(self) -> bool:
        """Whether a cycle dated by the B2 floor (stored before SEC17) is still within the bound."""
        return B2_FLOOR >= self._cutoff()

    def retrieve_similar(self, signal: dict, n: int = 3) -> list[dict]:
        """Return the N past cycles most similar to this signal — real cycles only, for
        every signal (SEC4a, V-12), and of a bounded age (SEC17, V-12).

        A cycle stored more than ``max_age_days`` ago is no precedent: a year-old decision
        weighed as much as yesterday's. One stored before SEC17 carries no date: it is dated by
        the B2 floor (``B2_FLOOR``, an age at least its true one), given while that floor is
        within the bound, left out after. Nothing is erased: ``age_census`` counts what the age
        leaves out, and `glorfindel report` says it.

        An exercise's cycle, or one of unknown source (recorded before B2, labelling
        unreadable), is never a precedent. Not for an exercise either: what the model is
        shown must not tell it whether the current signal is one (the prompt says it is
        not given). The cost: a bench's memory, made of exercises, shows nothing.

        One cycle per (signal_id, action, run_id), the most similar: a `respond` replayed
        on the same file stores its cycles again (the identifiers are drawn, never the
        signal's), and the same cycle never fills the N places.

        SEC-I (V-11): the VM and the rule weigh in, and one VM is bounded. A cycle of the same
        rule comes first, then one of the same VM, then the text's distance (technique, gravity,
        type, event, provider); and at most ``PER_VM`` cycles of any one VM, the signal's own
        included — a VM whose local account provokes detections at will no longer fills the
        places of its neighbours, nor its own. Each search past a VM at its bound reads the
        others (a flood of one VM's cycles never hides the rest), a bounded number of times.
        A cycle stored before SEC-I names no VM, and a filter cannot leave out a key a cycle
        lacks: once the VM unknown is at its bound, the search past it reads the whole memory
        (its cycles would otherwise fill every place it reads, and hide the other VMs) —
        nothing stored is rewritten for it."""
        if self._collection.count() == 0:
            return []
        query_text = _signal_to_text(signal)
        size = min(n * _DUPLICATE_SLACK, self._collection.count())
        vm, rule = _signal_vm(signal), _signal_rule(signal)
        pool: dict[str, tuple] = {}

        def gather(extra: dict | None, wide: bool = False) -> int:
            before = len(pool)
            for cid, row in self._search(query_text, self._collection.count() if wide else size, extra):
                pool.setdefault(cid, row)
            return len(pool) - before

        gather(None)
        if vm:
            gather({"resource_id": vm})
        if rule:
            gather({"rule_name": rule})

        def rank(row: tuple) -> tuple:
            distance, _doc, meta = row
            return (not rule or meta.get("rule_name") != rule,
                    not vm or meta.get("resource_id") != vm, distance)

        cycles, seen, per_vm = [], set(), {}
        for _ in range(n + 1):
            for distance, doc, meta in sorted(pool.values(), key=rank):
                if len(cycles) == n:
                    break
                key = (meta.get("signal_id", ""), meta.get("action", ""), meta.get("run_id", ""))
                owner = _vm_key(meta.get("resource_id"))
                if key in seen or per_vm.get(owner, 0) >= PER_VM:
                    continue
                seen.add(key)
                per_vm[owner] = per_vm.get(owner, 0) + 1
                cycles.append((rank((distance, doc, meta)), {"summary": doc, **meta}))
            full = sorted(v for v, c in per_vm.items() if c >= PER_VM)
            # The VM unknown at its bound: its cycles (no `resource_id`) pass any `$nin` — read
            # past them, the whole memory.
            if len(cycles) == n or not full or not gather({"resource_id": {"$nin": full}}, wide="" in full):
                break
        return [c for _r, c in sorted(cycles, key=lambda pair: pair[0])]

    def _search(self, query_text: str, size: int, extra: dict | None) -> list[tuple[str, tuple]]:
        """The real cycles within the age bound nearest to ``query_text``, narrowed by ``extra``
        (a metadata filter, or None): (id, (distance, document, metadata)), nearest first."""
        def where(*terms: dict) -> dict:
            terms = tuple(t for t in terms if t)
            return terms[0] if len(terms) == 1 else {"$and": list(terms)}

        include = ["documents", "metadatas", "distances"]
        res = self._collection.query(
            query_texts=[query_text], n_results=size, include=include,
            where=where({"source": "real"}, {"stored_at": {"$gte": self._cutoff()}}, extra))
        found = [(cid, (d, doc, meta)) for cid, d, doc, meta in
                 zip(res["ids"][0], res["distances"][0], res["documents"][0], res["metadatas"][0])]
        if self._b2_within():
            # The undated ones (stored before SEC17), dated by the B2 floor — which is within the
            # bound: the filter cannot name a missing field, so they are read among the real ones.
            real = self._collection.query(query_texts=[query_text], n_results=size, include=include,
                                          where=where({"source": "real"}, extra))
            found += [(cid, (d, doc, meta)) for cid, d, doc, meta in
                      zip(real["ids"][0], real["distances"][0], real["documents"][0], real["metadatas"][0])
                      if not _dated(meta)]
            found.sort(key=lambda item: item[1][0])
        return found

    def count(self) -> int:
        return self._collection.count()

    def age_census(self) -> dict:
        """The real cycles — the only ones a search can give — by age (SEC17, V-12): ``within``
        the bound, ``too_old`` (stored before it: left out of the search, never erased). Among
        them, ``b2_dated``: stored before SEC17, no date of their own, dated by the B2 floor."""
        cutoff = self._cutoff()
        got = self._collection.get(where={"source": "real"}, include=["metadatas"])
        within = too_old = b2_dated = 0
        for meta in got.get("metadatas") or []:
            at = _stored_at(meta or {})
            b2_dated += not _dated(meta or {})
            if at >= cutoff:
                within += 1
            else:
                too_old += 1
        return {"max_age_days": self.max_age_days, "real": within + too_old,
                "within": within, "too_old": too_old, "b2_dated": b2_dated,
                "b2_floor": "2026-10-16"}


def _dated(meta: dict) -> bool:
    """The cycle carries the date `store` gave it (SEC17)."""
    at = meta.get("stored_at")
    return isinstance(at, (int, float)) and not isinstance(at, bool) and math.isfinite(at)


def _stored_at(meta: dict) -> float:
    """When the cycle was stored — its own date, else the B2 floor: never later than the truth."""
    return float(meta["stored_at"]) if _dated(meta) else float(B2_FLOOR)


def age_census(path: str | Path | None = None, max_age_days: float | None = None, mode: str | None = None) -> dict:
    """``CycleMemory.age_census`` for `glorfindel report`, without making a memory where there is
    none (``absent``); a memory that cannot be read is said (``error``), never counted as empty. The
    memory the switch names (MEM2): the census of the keys' table when it is on."""
    if (memory_mode()[0] if mode is None else mode) == KEYS:
        from glorfindel import memory_keys
        return memory_keys.age_census(path, max_age_days)
    storage_path = Path(path) if path else _DEFAULT_PATH
    days = checked_max_age(DEFAULT_MAX_AGE_DAYS if max_age_days is None else max_age_days)
    if not storage_path.is_dir():
        return {"max_age_days": days, "absent": True}
    try:
        return CycleMemory(path=storage_path, max_age_days=days).age_census()
    except Exception as exc:  # chromadb missing, a store it cannot open
        return {"max_age_days": days, "error": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"}


def _vm_key(resource_id) -> str:
    """A VM as the memory keys it (SEC-I): its resource id, lowered, without a trailing slash;
    "" when there is none (a cycle stored before SEC-I, or one attributed to no VM)."""
    return resource_id.rstrip("/").lower() if isinstance(resource_id, str) else ""


def _signal_vm(signal: dict) -> str:
    """The VM a signal is about, for the memory (SEC-I): "" when the RulePoller attributed it to
    none — its resource id is then an anchor, never the VM the detection is about."""
    if (signal.get("context") or {}).get("attribution") == "unattributed":
        return ""
    return _vm_key(signal.get("resource_id"))


def _signal_rule(signal: dict) -> str:
    """The rule that found it (the RulePoller's), "" for any other signal."""
    rule = (signal.get("context") or {}).get("rule_name")
    return rule if isinstance(rule, str) else ""


def _signal_to_text(signal: dict) -> str:
    return (
        f"TTP: {signal.get('ttp')} | "
        f"severity: {signal.get('severity')} | "
        f"resource_type: {signal.get('resource_type')} | "
        f"event: {signal.get('event')} | "
        f"provider: {signal.get('provider')}"
    )


def _cycle_to_text(cycle: dict) -> str:
    return (
        f"TTP: {cycle.get('ttp')} | "
        f"severity: {cycle.get('severity')} | "
        f"resource_type: {cycle.get('resource_type')} | "
        f"event: {cycle.get('event')} | "
        f"action: {cycle.get('action')} | "
        f"reasoning: {cycle.get('reasoning', '')[:200]} | "
        f"outcome: {cycle.get('outcome')}"
    )
