"""Persistent incident registry — groups signals by resource_id within a TTL window.

What a detection confirmed on its VM (B3a, #609: `Incident.confirmed`) lives on the incident, each
fact with its date (`confirmed_at`) and a TTL of its own, absolute (SEC-E, #846): `FACT_TTL_S` after
it was confirmed, whatever the signals of the VM since — the incident's TTL slides with each signal,
a fact's never does. A fact without a date (a row written before SEC-E) is no longer one. And a
release of the VM's isolation forgets them (`forget_facts`): a human who lifted it judged the VM.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# SEC-E (#846): how long a fact confirmed on a VM counts for B3a's floor, from its confirmation —
# never prolonged by another signal of the VM, nor by a detection held by the decision queue. Fifteen
# minutes: the pair's two detections (a sudo to root, a brute force seen succeed) come from rules
# polled every 30 s over a window of ten, with up to 480 s of Syslog latency.
FACT_TTL_S = 900


def _parse(at) -> datetime | None:
    try:
        when = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)


def live_facts(incident, now: datetime | None = None) -> list[str]:
    """The facts of `incident` (an Incident, or its dict) still within their TTL (`FACT_TTL_S`, from
    their confirmation): a fact without a date, or older, is none. Never raises."""
    get = incident.get if isinstance(incident, dict) else (lambda k, d=None: getattr(incident, k, d))
    facts = get("confirmed") or []
    dates = get("confirmed_at") or {}
    if not isinstance(facts, list) or not isinstance(dates, dict):
        return []
    now = now or datetime.now(timezone.utc)
    live = []
    for fact in facts:
        at = _parse(dates.get(fact)) if isinstance(fact, str) else None
        if at is not None and 0 <= (now - at).total_seconds() < FACT_TTL_S:
            live.append(fact)
    return live


@dataclass
class Incident:
    incident_id: str
    resource_id: str
    ttps: list
    started_at: str          # ISO8601
    last_signal_at: str      # ISO8601
    actions_taken: list      # [{action, timestamp, outcome_status}]
    signals_count: int
    state: str               # "active" | "resolved"
    # What a detection on this VM confirmed (B3a, #609: `agent.confirmed_facts`) — never
    # shown to the model; a row written before B3a has none.
    confirmed: list = field(default_factory=list)
    # When each fact was confirmed (SEC-E, #846): its TTL, absolute, runs from there.
    confirmed_at: dict = field(default_factory=dict)


class IncidentRegistry:
    """Incident state grouped by resource_id, persisted to JSONL, TTL-bounded.

    Same resource_id within the TTL window = same incident.
    Past TTL or resolved = new incident on next signal.

    Several writers: the worker threads of one watch, and other processes — the watch and
    `glorfindel respond` each hold a registry on the same file. Each read-modify-write holds
    a thread lock and an flock on `<file>.lock`, and the file is rewritten whole (temporary
    file + os.replace, owner-only): no incident lost between two writers, no reader ever sees
    half a file (SEC13, V-10 — as the escalations store, SEC3).
    TTL controlled by GLORFINDEL_INCIDENT_TTL_S env var (default 300s).
    """

    _DEFAULT_TTL_S = 300
    _DEFAULT_PATH = Path.home() / ".glorfindel" / "incidents.jsonl"

    def __init__(
        self,
        path: Path | str | None = None,
        ttl_s: int | None = None,
    ):
        self._path = Path(path) if path else self._DEFAULT_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._ttl_s = ttl_s or int(
            os.environ.get("GLORFINDEL_INCIDENT_TTL_S") or self._DEFAULT_TTL_S
        )
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def _locked(self):
        """This registry's threads, then every process writing the same file."""
        from glorfindel.response.locks import _file_lock
        with self._lock, _file_lock(self._path.with_name(self._path.name + ".lock")):
            yield

    def get_or_create(self, resource_id: str, ttp: str = "") -> Incident:
        """Return the active incident for resource_id, or open a new one."""
        with self._locked():
            rows = self._load_all()
            active = self._find_active(resource_id, rows)
            if active is not None:
                if ttp and ttp not in active.ttps:
                    active.ttps.append(ttp)
                active.signals_count += 1
                active.last_signal_at = _now_iso()
                self._write_all(rows)
                return active

            inc = Incident(
                incident_id=str(uuid.uuid4())[:8],
                resource_id=resource_id,
                ttps=[ttp] if ttp else [],
                started_at=_now_iso(),
                last_signal_at=_now_iso(),
                actions_taken=[],
                signals_count=1,
                state="active",
            )
            self._write_all(rows + [inc])
            return inc

    def confirm(self, resource_id: str, facts: list[str], *, ttp: str = "",
                open_new: bool = False) -> Incident | None:
        """Add what a detection confirmed on this VM to its active incident (B3a, #609), each fact
        dated (SEC-E, #846): a fact still live keeps its date — confirmed again, it is not prolonged —,
        an expired one is dropped, or dated anew when this detection confirms it again. Never a
        signal of the incident: neither its count nor its last signal move (a detection the decision
        queue held does not prolong the incident). `open_new`: with no active incident, open one for
        these facts (that held detection, the first on its VM). Returns the incident, or None when
        the VM has none (and none was opened)."""
        with self._locked():
            rows = self._load_all()
            active = self._find_active(resource_id, rows)
            created = active is None
            if created:
                if not open_new or not facts:
                    return None
                active = Incident(
                    incident_id=str(uuid.uuid4())[:8], resource_id=resource_id,
                    ttps=[ttp] if ttp else [], started_at=_now_iso(), last_signal_at=_now_iso(),
                    actions_taken=[], signals_count=1, state="active")
                rows.append(active)
            now = datetime.now(timezone.utc)
            live = live_facts(active, now)
            dates = active.confirmed_at if isinstance(active.confirmed_at, dict) else {}
            kept = {f: dates[f] for f in live}
            for f in facts:
                if f not in kept:
                    kept[f] = now.isoformat()
            if created or list(kept) != active.confirmed or kept != dates:
                active.confirmed, active.confirmed_at = list(kept), kept
                self._write_all(rows)
            return active

    def forget_facts(self, resource_id: str) -> int:
        """SEC-E (#846): a release of this VM's isolation — what its incidents confirmed is forgotten
        (B3a's floor no longer reads it), the incidents themselves kept. Compared as Azure does, case
        and trailing slash aside (the RulePoller carries a lowercase id, the CLI the canonical one).
        Returns how many incidents had facts."""
        want = str(resource_id or "").rstrip("/").lower()
        with self._locked():
            rows = self._load_all()
            had = [inc for inc in rows if str(inc.resource_id or "").rstrip("/").lower() == want
                   and (inc.confirmed or inc.confirmed_at)]
            for inc in had:
                inc.confirmed, inc.confirmed_at = [], {}
            if had:
                self._write_all(rows)
            return len(had)

    def record_action(
        self,
        incident_id: str,
        action: str,
        outcome_status: str,
        investigative_context: dict | None = None,
    ) -> None:
        """Append an action record to the incident.

        investigative_context: the raw_signal.investigative_context dict from the
        cycle that triggered this action — stored so subsequent LLM cycles can see
        what was investigated before the action was taken.
        """
        with self._locked():
            rows = self._load_all()
            for inc in rows:
                if inc.incident_id == incident_id:
                    entry: dict = {
                        "action": action,
                        "timestamp": _now_iso(),
                        "outcome_status": outcome_status,
                    }
                    if investigative_context:
                        entry["investigative_context"] = investigative_context
                    inc.actions_taken.append(entry)
                    break
            self._write_all(rows)

    def resolve(self, incident_id: str) -> None:
        """Mark an incident as resolved (will not be returned by get_or_create)."""
        with self._locked():
            rows = self._load_all()
            for inc in rows:
                if inc.incident_id == incident_id:
                    inc.state = "resolved"
                    break
            self._write_all(rows)

    def get_active(self, resource_id: str) -> Incident | None:
        """Return the active incident for resource_id if one exists within TTL. A read: the
        file is only ever replaced whole, so no lock is needed to read a whole one."""
        with self._lock:
            return self._find_active(resource_id, self._load_all())

    # ── Private ────────────────────────────────────────────────────────────────

    def _find_active(self, resource_id: str, rows: list[Incident]) -> Incident | None:
        now = datetime.now(timezone.utc)
        for inc in reversed(rows):
            if inc.resource_id != resource_id or inc.state != "active":
                continue
            age_s = (now - datetime.fromisoformat(inc.last_signal_at)).total_seconds()
            if age_s <= self._ttl_s:
                return inc
        return None

    def _load_all(self) -> list[Incident]:
        if not self._path.exists():
            return []
        rows: list[Incident] = []
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(Incident(**json.loads(line)))
                except Exception:
                    pass
        return rows

    def _write_all(self, rows: list[Incident]) -> None:
        """The whole registry, through a temporary file: owner-only (0600), never half-written."""
        from glorfindel.response.state import _atomic_write_text
        _atomic_write_text(self._path, "".join(json.dumps(asdict(inc), default=str) + "\n" for inc in rows))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
