"""MEM2 (#1027): the memory of past cycles by keys and by date — one SQLite table, the standard library.

What `CycleMemory` opens when the switch says so (``GLORFINDEL_MEMORY=cles``, glorfindel/memory.py) —
off by default: until ENQ5 switches it on, after the harness's session (MEM-H) and Jonathan's run end
to end, the watch keeps the memory by distance (ChromaDB). The measure it rests on: MEM1,
docs/design/memoire.md (on Imladris's copy of 21/11, 92.9 % of the precedents bear the signal's
technique by the keys, 77.3 % by the distance).

**The same interface** as the memory by distance: `store`, `retrieve_similar`, `age_census`, `count`,
`said`. **The same cycles**: the same text (`memory._cycle_to_text`), the same metadata, under an
identifier drawn at storing — a cycle is added, never overwritten; the same date, by this host's clock
(SEC17), never by what the cycle carries.

**The rank** (`choose`): the cycles of the signal's rule first, then those of its VM, then those of its
technique, then a judged one (MEM2b), then the newest (by the date `store` gave; at equal dates, the one
stored last). **The
bounds**, the memory by distance's: real cycles only, for every signal (SEC4a) — never an exercise's,
nor one of unknown source; stored within the age bound (90 days by default, SEC17), one stored before
cycles were dated taking the B2 floor (`memory.B2_FLOOR`); one cycle per (signal_id, action, run_id), the
copies of a replayed `respond` folded; at most `memory.PER_VM` per VM, the signal's own included, the
cycles that name no VM counting as one VM, unknown (SEC-I). No distance: no embedding, no model.

**Where** (`DEFAULT_PATH`): ``~/.eregion/watch-memory/cycles.sqlite3`` — a directory only the watch's
service mounts (docker-compose.yml), made 0700 as the operator (Makefile, infra/glorfindel-host/
deploy.sh), like its register of the signed queue (FS1b). Never under ~/.glorfindel, which the console
and the bot mount in writing: what the model is shown as its past is written by the watch alone.
``make imladris-pull`` copies it with ~/.glorfindel.

**Refused at the opening**, nothing written: a folder (the memory by distance's store, ChromaDB's); a
file that holds a table that is not the memory's (a copy of ChromaDB's, the analysis index — IA1: the
analysis never shares the defender's memory, analysis/separation.py, which refuses in turn a file that
holds this table, ``cycles``). In an agent session, the operator's ~/.eregion is refused before it is
opened (eregion_core/store_guard.py; ``sqlite3.connect`` is one of the events its hook sees).

**The import** of a copy of the memory by distance, once (`glorfindel/memory_import.py`, Q3).

**The human verdict** (MEM2b, #1161, decision of Jonathan of 24/11): each precedent says the operator's
judgement of the card its cycle opened — the decision judged right (a real attack, or a false alarm when
the decision was to do nothing), judged wrong, unsure — with the day it was given, or « non jugé »; and
among the cycles of the same keys, a judged one comes before an unjudged one (`preferred`). Read when the
precedents are chosen (`card_verdicts`, the cards' store, glorfindel/escalations.py), never stored with
the cycle: a verdict comes after the decision. Only the verdict's word and its day, never the operator's
note: what the model reads of a card is bounded to a few fixed words. A precedent stays history (Q9): it
says what was decided and how it was judged, never the VM's state. The memory by distance gives none:
off, the message to the model is today's, to the byte.
"""
from __future__ import annotations

import contextlib
import json
import re
import sqlite3
import time
import uuid
from collections import Counter
from pathlib import Path

from eregion_core import store_guard
from glorfindel import memory
from glorfindel import verdict_cause
from glorfindel.verdict_cause import RESPONSES

TABLE = "cycles"
DEFAULT_PATH = Path.home() / ".eregion" / "watch-memory" / "cycles.sqlite3"
# How long a writer waits for another (the watch, and `respond` or an import by hand at once).
BUSY_S = 30.0
# The memory's own tables: a file holding any other is not opened.
OWN_TABLES = frozenset({TABLE, "imports"})
_SCHEMA = (
    # stored_at NULL: a cycle stored before SEC17 (imported), dated by the B2 floor at retrieval.
    f"CREATE TABLE IF NOT EXISTS {TABLE} (seq INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE, "
    "source TEXT NOT NULL, stored_at INTEGER, rule_name TEXT NOT NULL, resource_id TEXT NOT NULL, "
    "ttp TEXT NOT NULL, signal_id TEXT NOT NULL, action TEXT NOT NULL, run_id TEXT NOT NULL, "
    "document TEXT NOT NULL, meta TEXT NOT NULL)",
    f"CREATE INDEX IF NOT EXISTS {TABLE}_real ON {TABLE} (source, stored_at)",
    # Each import of a copy (glorfindel/memory_import.py): what it read, when, what it did.
    "CREATE TABLE IF NOT EXISTS imports (seq INTEGER PRIMARY KEY, source TEXT NOT NULL, at REAL NOT NULL, "
    "imported INTEGER NOT NULL, kept INTEGER NOT NULL)",
)


# MEM2b: the verdicts that judge a decision (glorfindel/escalations.py, VERDICTS) — `unsure` is said,
# never preferred; the actions that respond to a threat, for which « judged right » says a real attack, are
# glorfindel/verdict_cause.py's RESPONSES (VRD1: a gesture, the only place an action can be too strong).
JUDGED = ("right", "wrong")
# VRD1 (#1285): what a « wrong » says when its cause is known — the same for a card that made a gesture or
# not (a false alarm: nothing happened); « too strong » only after a gesture (verdict_cause.of).
WRONG_SAID = {verdict_cause.FALSE_ALARM: "fausse alerte : rien ne s'était passé",
              verdict_cause.TOO_STRONG: "action trop forte : le signal était vrai, le geste trop fort"}
UNJUDGED = "verdict humain : non jugé"
UNREAD = "verdict humain : inconnu (les cartes ne se lisent pas)"
# MEM2b (decision of Jonathan of 24/11): the memory by keys asked for and not opened — the watch falls
# back on the memory by distance, and says it on its banner and on this card (glorfindel/watch/startup.py).
FALLBACK_TYPE = "memory_fallback"
FALLBACK_RESOURCE = "~/.eregion/watch-memory"


class NotTheMemory(ValueError):
    """A path the memory by keys does not open: a folder, a file of another store, a file that is no
    SQLite database."""


def _text(value) -> str:
    return value if isinstance(value, str) else ""


def rank(c: dict, rule: str, vm: str, ttp: str) -> tuple:
    """The keys of a candidate (``rule``, ``vm``, ``ttp``, ``at``, ``seq``): the signal's rule, its VM,
    its technique, then the newest — at equal dates, the one stored last."""
    return (not rule or c["rule"] != rule, not vm or c["vm"] != vm, not ttp or c["ttp"] != ttp,
            -c["at"], -c["seq"])


def preferred(c: dict, rule: str, vm: str, ttp: str) -> tuple:
    """`rank`, a judged candidate (``judged``, MEM2b) before an unjudged one of the same rule, VM and
    technique — never before one that shares more of the keys — then the newest."""
    keys = rank(c, rule, vm, ttp)
    return keys[:3] + (not c.get("judged"),) + keys[3:]


def choose(candidates, rule: str, vm: str, ttp: str, n: int = 3) -> list[dict]:
    """The precedents the keys give, in their order (`preferred`): ``n`` at most, one per ``key``
    (signal_id, action, run_id), at most ``memory.PER_VM`` per ``vm`` ("" — no VM named — one VM, unknown).
    Shared with the replay (scripts/memory_replay.py, its ranking ``keys``): what it measures is this code."""
    out, seen, per_vm = [], set(), Counter()
    for c in sorted(candidates, key=lambda c: preferred(c, rule, vm, ttp)):
        if len(out) == n:
            break
        if c["key"] in seen or per_vm[c["vm"]] >= memory.PER_VM:
            continue
        seen.add(c["key"])
        per_vm[c["vm"]] += 1
        out.append(c)
    return out


def _foreign_tables(path: Path) -> list[str]:
    """The tables of the file at ``path`` that are not the memory's — read by a connection read only. A
    file that is no SQLite database is refused (`NotTheMemory`), nothing written."""
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=BUSY_S)
    try:
        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    except sqlite3.DatabaseError as exc:
        raise NotTheMemory(f"{path} n'est pas une base SQLite ({exc}) : jamais la mémoire par clés ; rien n'y "
                           "est écrit.") from None
    finally:
        db.close()
    return sorted(n for n in names if n not in OWN_TABLES and not n.startswith("sqlite_"))


class KeyedMemory:
    """The memory of past cycles by keys and by date (the module's docstring)."""

    mode = memory.KEYS

    fallback = ""             # MEM2b: never a fallback — it is the memory the switch asked for

    def __init__(self, path: str | Path | None = None, max_age_days: float | None = None, clock=time.time,
                 verdicts=None):
        self.max_age_days = memory.checked_max_age(
            memory.DEFAULT_MAX_AGE_DAYS if max_age_days is None else max_age_days)
        self._clock = clock
        # MEM2b: where the human verdicts are read — the cards' (`card_verdicts`), or the harness's own.
        self._verdicts = verdicts or card_verdicts
        self.path = Path(path) if path else DEFAULT_PATH
        store_guard.check(self.path)
        if self.path.is_dir():
            raise NotTheMemory(f"{self.path} est un dossier (le magasin de ChromaDB ?) : la mémoire par clés "
                               "est un fichier SQLite (…/cycles.sqlite3) ; rien n'est ouvert.")
        if self.path.is_file() and (foreign := _foreign_tables(self.path)):
            raise NotTheMemory(f"{self.path} tient d'autres tables que la mémoire ({', '.join(foreign)}) : "
                               "jamais la mémoire d'un autre magasin ; rien n'y est écrit.")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self._db() as db:
            for statement in _SCHEMA:
                db.execute(statement)

    @contextlib.contextmanager
    def _db(self):
        """One connection per use, committed at the end — the watch decides in several threads."""
        db = sqlite3.connect(str(self.path), timeout=BUSY_S)
        try:
            with db:
                yield db
        finally:
            db.close()

    def said(self) -> str:
        """Which memory this is, and where: `glorfindel memory-stats`, the watch's banner."""
        return f"memory by keys (SQLite, {memory.SWITCH}={memory.KEYS}): {self.path}"

    def _row(self, cid: str, document: str, meta: dict) -> tuple:
        at = meta.get("stored_at")
        return (cid, _text(meta.get("source")), int(at) if memory._dated(meta) else None,
                _text(meta.get("rule_name")), memory._vm_key(meta.get("resource_id")), _text(meta.get("ttp")),
                _text(meta.get("signal_id")), _text(meta.get("action")), _text(meta.get("run_id")),
                document, json.dumps(meta, ensure_ascii=False, sort_keys=True))

    def _insert(self, db, rows) -> int:
        """``rows`` (id, document, metadata) added — one whose id is there already kept as it is."""
        before = db.total_changes
        db.executemany(f"INSERT OR IGNORE INTO {TABLE} (id, source, stored_at, rule_name, resource_id, ttp, "
                       "signal_id, action, run_id, document, meta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       [self._row(cid, document, meta) for cid, document, meta in rows])
        return db.total_changes - before

    def store(self, cycle: dict) -> None:
        """Persist a completed cycle, under an identifier of its own (SEC4a): the memory by distance's
        metadata (glorfindel/memory.py, `DistanceMemory.store`), dated by this host's clock (SEC17)."""
        meta = {
            "ttp": cycle.get("ttp", ""),
            "action": cycle.get("action", ""),
            "outcome": str(cycle.get("outcome", "")),
            "signal_id": cycle.get("signal_id", ""),
            "run_id": cycle.get("run_id", ""),
            "source": cycle.get("source", ""),
            "exercise_run": cycle.get("exercise_run", ""),
            "event": cycle.get("event", ""),
            "detection_s": cycle.get("detection_s", 0),
            "action_s": cycle.get("action_s", 0),
            "confidence": float(cycle.get("confidence", 0.0)),
            "past_cycles_used": json.dumps(cycle.get("past_cycles_used", [])),
            "stored_at": int(self._clock()),
            "resource_id": memory._vm_key(cycle.get("resource_id")),
            "rule_name": str(cycle.get("rule_name") or ""),
            "corroborated": cycle.get("corroborated") is True,
        }
        with self._db() as db:
            self._insert(db, [(f"cycle-{uuid.uuid4().hex}", memory._cycle_to_text(cycle), meta)])

    def add_imported(self, rows, source: str) -> tuple[int, int]:
        """Cycles of a copy of the memory by distance (glorfindel/memory_import.py), in their order:
        (added, kept — already there, by their id). The import is recorded with the source it read."""
        rows = list(rows)
        with self._db() as db:
            added = self._insert(db, rows)
            db.execute("INSERT INTO imports (source, at, imported, kept) VALUES (?, ?, ?, ?)",
                       (source, float(self._clock()), added, len(rows) - added))
        return added, len(rows) - added

    def imports(self) -> list[dict]:
        with self._db() as db:
            return [{"source": s, "at": at, "imported": i, "kept": k}
                    for s, at, i, k in db.execute("SELECT source, at, imported, kept FROM imports ORDER BY seq")]

    def _cutoff(self) -> int:
        """The oldest date a precedent may carry (SEC17)."""
        return int(self._clock() - self.max_age_days * memory._DAY_S)

    def _read_verdicts(self) -> dict | None:
        """The human verdicts by signal (`card_verdicts`), or None when they cannot be read — said on
        each precedent (`UNREAD`), never read as « none judged »."""
        try:
            return self._verdicts()
        except Exception:
            return None

    def retrieve_similar(self, signal: dict, n: int = 3) -> list[dict]:
        """The ``n`` precedents of this signal by the keys (`choose`): real cycles, within the age
        bound (an undated one at the B2 floor), each as the memory by distance gives it —
        ``{"summary": its text, **its metadata}`` — and, MEM2b, its human verdict: said at the end of
        its text (`verdict_said`), and in ``verdict`` and ``verdict_at`` ("" when none)."""
        rule, vm, ttp = memory._signal_rule(signal), memory._signal_vm(signal), _text(signal.get("ttp"))
        verdicts = self._read_verdicts()
        judged = verdicts or {}
        with self._db() as db:
            candidates = [
                {"seq": seq, "rule": r, "vm": v, "ttp": t, "key": (sid, action, run),
                 "at": float(memory.B2_FLOOR if at is None else at),
                 "judged": (judged.get(sid) or {}).get("verdict") in JUDGED}
                for seq, r, v, t, at, sid, action, run in db.execute(
                    f"SELECT seq, rule_name, resource_id, ttp, stored_at, signal_id, action, run_id FROM {TABLE} "
                    "WHERE source = 'real' AND COALESCE(stored_at, ?) >= ?", (memory.B2_FLOOR, self._cutoff()))]
            chosen = [c["seq"] for c in choose(candidates, rule, vm, ttp, n)]
            if not chosen:
                return []
            rows = {seq: (document, meta) for seq, document, meta in db.execute(
                f"SELECT seq, document, meta FROM {TABLE} WHERE seq IN ({', '.join('?' * len(chosen))})", chosen)}
        out = []
        for seq in chosen:
            meta = json.loads(rows[seq][1])
            verdict = judged.get(meta.get("signal_id"))
            said = UNREAD if verdicts is None else verdict_said(verdict, meta.get("action"))
            out.append({"summary": f"{rows[seq][0]} | {said}", **meta,
                        "verdict": (verdict or {}).get("verdict", ""), "verdict_at": (verdict or {}).get("at", "")})
        return out

    def count(self) -> int:
        with self._db() as db:
            return db.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]

    def age_census(self) -> dict:
        """The real cycles by age, as the memory by distance counts them (`DistanceMemory.age_census`)."""
        cutoff = self._cutoff()
        with self._db() as db:
            dates = [at for (at,) in db.execute(f"SELECT stored_at FROM {TABLE} WHERE source = 'real'")]
        within = sum(float(memory.B2_FLOOR if at is None else at) >= cutoff for at in dates)
        return {"max_age_days": self.max_age_days, "real": len(dates), "within": within,
                "too_old": len(dates) - within, "b2_dated": sum(at is None for at in dates),
                "b2_floor": "2026-10-16"}


def age_census(path: str | Path | None = None, max_age_days: float | None = None) -> dict:
    """`KeyedMemory.age_census` for `glorfindel report`: no memory made where there is none
    (``absent``); one that cannot be read said (``error``), never counted as empty."""
    where = Path(path) if path else DEFAULT_PATH
    days = memory.checked_max_age(memory.DEFAULT_MAX_AGE_DAYS if max_age_days is None else max_age_days)
    if not where.exists():
        return {"max_age_days": days, "absent": True}
    try:
        return KeyedMemory(path=where, max_age_days=days).age_census()
    except Exception as exc:  # a folder, another store's file, a file that is no database
        return {"max_age_days": days, "error": f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"}


# ── MEM2b: the human verdict of a precedent, and the fallback said ───────────────────────────────────

def card_verdicts() -> dict[str, dict]:
    """The human verdict of each cycle that opened a card, by its signal: ``{signal_id: {"verdict",
    "at", "action"}}`` — the verdict given on the card (`escalations.set_verdict`, a proposal confirmed
    included, never a proposal alone: VP1's own field), the latest when a signal has several cards.
    A detection seen again and folded into an earlier card (its occurrences) has a signal of its own:
    its cycle is not judged by that card. An unreadable store raises: the precedents say it."""
    from glorfindel import escalations
    out: dict[str, dict] = {}
    for e in escalations.all_escalations():
        if not escalations.is_decision(e):       # the observation's reading: a decision's card only
            continue
        sid, verdict = e.get("signal_id"), e.get("verdict")
        if not isinstance(sid, str) or not sid or verdict not in escalations.VERDICTS:
            continue
        at = str(e.get("verdict_at") or "")
        if sid not in out or at >= out[sid]["at"]:
            # VRD1: the cause of a « wrong » when the operator said it — none on a verdict of before.
            out[sid] = {"verdict": verdict, "at": at, "action": str(e.get("action") or ""),
                        **({"cause": c} if (c := verdict_cause.of(e)) else {})}
    return out


def verdict_said(verdict: dict | None, action) -> str:
    """What a precedent says of its human verdict: « non jugé », or the day and the judgement — judged
    right, a real attack when the decision responded (`RESPONSES`, the card's action, else the cycle's),
    a false alarm when it did nothing; judged wrong — its cause when the operator said it (VRD1: a false
    alarm, an action too strong; `WRONG_SAID`), else as before VRD1 (a false alarm or a response out of
    proportion, or a threat left without a response); unsure. History, never the VM's state."""
    if not verdict:
        return UNJUDGED
    acted = (verdict.get("action") or _text(action)) in RESPONSES
    day = str(verdict.get("at") or "")[:10]
    day = day if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day) else "?"    # a date, never another text
    cause = verdict.get("cause") if verdict.get("cause") in WRONG_SAID else ""
    judgement = {
        "right": "décision jugée juste (" + ("vraie attaque" if acted else "fausse alerte") + ")",
        "wrong": "décision jugée fausse (" + (WRONG_SAID[cause] if cause else
                                             "fausse alerte, ou action disproportionnée" if acted
                                             else "il fallait agir") + ")",
    }.get(verdict.get("verdict"), "incertain")
    return f"verdict humain du {day} : {judgement}"


def fallback_card(why: str) -> None:
    """The card of the memory by keys not opened (`why`), at the watch's start — or, opened, the card a
    former start left, closed. Never a reason to stop the watch."""
    from glorfindel import escalations
    try:
        if not why:
            # Only when a former start left one: a start with nothing to close never rewrites the store.
            if any(e.get("escalation_type") == FALLBACK_TYPE for e in escalations.pending()):
                escalations.resolve_by_resource(FALLBACK_RESOURCE, "none")
            return
        escalations.record(
            signal_id="memory-fallback", resource_id=FALLBACK_RESOURCE, action="none",
            escalation_type=FALLBACK_TYPE, severity="high", source="real", reason=why,
            suggested_steps=["Lire la cause sur la carte et dans les journaux de la watch (son démarrage)",
                             "Un dossier ~/.eregion/watch-memory à root : make fix-state-ownership, puis "
                             "relancer la watch",
                             "La carte se ferme seule au démarrage suivant, la mémoire par clés ouverte"])
    except Exception:   # a card never stops the watch
        pass
