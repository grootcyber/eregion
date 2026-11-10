"""The door's facts, read for each isolated VM and said on its isolation card — for information
only (LEV2, #690; docs/design/levee-probation.md §4, §13 point 6).

Every GLORFINDEL_DOOR_FACTS_INTERVAL_S (900 s; 0: off), for each isolation of its state, the watch
reads on Azure who acted on the VM by the control plane (`observed_actors`, the adapter) from
LOOKBACK_DAYS before the isolation until now, and whether each of them keeps a right that opens the
door again (`observed_rights`). It writes what it read in ~/.glorfindel/door/<vm>.json, which the
console shows on the isolation card. NOTHING here lifts or holds: no release, no card, no signal,
nothing the model sees — the lift reads none of it (LEV3 will judge these facts, at the lift, over
the window that starts before the point restored). A read that fails is written as unreadable,
never as « nobody ».

The file is the watch's alone; a facts file of a VM no longer isolated is removed at the next pass.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

FACTS_DIR = Path.home() / ".glorfindel" / "door"
# §4.3: 7 days before the point restored. Before a restore, the isolation is the moment known.
LOOKBACK_DAYS = 7.0
# Rights read for at most this many actors in one pass (the reads are shared; the rest is said).
MAX_ACTORS = 8
# When each VM was last read, in this process, by its isolation: a file that can't be written
# (a full disk) never makes the pass read Azure again at every round of the watch.
_LAST_READ: dict[str, tuple[str, float]] = {}


def interval_s() -> float:
    """How often the facts are read again (GLORFINDEL_DOOR_FACTS_INTERVAL_S, 900 s; 0: off)."""
    try:
        return float(os.environ.get("GLORFINDEL_DOOR_FACTS_INTERVAL_S", "") or 900.0)
    except ValueError:
        return 900.0


def _file(resource_id: str) -> Path:
    import hashlib
    rid = str(resource_id or "").rstrip("/").lower()
    name = "".join(c if c.isalnum() or c in "-_." else "_" for c in rid.rsplit("/", 1)[-1])[:64]
    return FACTS_DIR / f"{name}-{hashlib.sha256(rid.encode()).hexdigest()[:8]}.json"


def load(resource_id: str) -> dict | None:
    """The facts last read for this VM, or None (absent, unreadable, another VM's)."""
    try:
        data = json.loads(_file(resource_id).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if str(data.get("resource_id") or "").rstrip("/").lower() != str(resource_id or "").rstrip("/").lower():
        return None
    return data


def _epoch(text) -> float | None:
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).timestamp()


def _since(isolated_at: str) -> str:
    at = _epoch(isolated_at)
    if at is None:
        return ""
    return datetime.fromtimestamp(at - LOOKBACK_DAYS * 86400, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_facts(connector, iso: dict, now: float) -> dict:
    """The facts of one isolated VM, read on Azure now: its actors, each with its rights."""
    rid = str(iso.get("resource_id") or "")
    disks = list(((iso.get("disks_at_isolation") or {}).get("ids")) or [])
    base = {"resource_id": rid, "isolated_at": iso.get("isolated_at", ""),
            "read_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(), "for_information": True}
    since = _since(iso.get("isolated_at", ""))
    if not since:
        return {**base, "verdict": "unreadable", "actors": [], "unreadable": ["moment de l'isolement illisible"]}
    try:
        until = datetime.fromtimestamp(now, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        seen = connector.observed_actors(rid, since, until=until, disks=disks,
                                         rules_at_isolation=iso.get("nsg_rules_at_isolation") or None)
    except NotImplementedError:
        raise
    except Exception as exc:                  # whatever broke: unreadable, never « nobody »
        return {**base, "since": since, "verdict": "unreadable", "actors": [],
                "unreadable": [f"acteurs illisibles : {str(exc)[:160]}"]}
    actors = list(seen.get("actors") or [])
    reading: dict = {}                         # the reads of this pass, shared by its actors (the adapter's)
    for i, a in enumerate(actors):
        if i >= MAX_ACTORS:
            a["rights"] = {"verdict": "unreadable", "unreadable": [f"plus de {MAX_ACTORS} acteurs : droits non lus"]}
            continue
        try:
            a["rights"] = connector.observed_rights(a.get("ids") or [], rid, scopes=seen.get("scopes") or (),
                                                    reading=reading)
        except Exception as exc:
            a["rights"] = {"verdict": "unreadable", "unreadable": [f"droits illisibles : {str(exc)[:160]}"]}
    return {**base, "since": seen.get("since", since), "until": seen.get("until", ""),
            "verdict": seen.get("verdict", "unreadable"), "actors": actors,
            "unreadable": list(seen.get("unreadable") or []), "notes": list(seen.get("notes") or []),
            "reads": list(seen.get("reads") or []),
            "rights_reads": [r for v in reading.values() for r in (getattr(v, "reads", None) or [])]}


def facts_pass(connector, now: float | None = None) -> list[dict]:
    """One pass: the facts of each isolated VM whose facts are older than interval_s() (or of
    another isolation), read and written. [{"vm", "verdict", "actors"}] of what was read. Raises
    nothing but an OSError of a file that could not be written (said by the watch)."""
    from glorfindel.actions import active_isolations
    from glorfindel.response.state import _atomic_write_text

    now = time.time() if now is None else now
    every = interval_s()
    isolations = active_isolations()
    keep = {_file(str(i.get("resource_id") or "")).name for i in isolations if i.get("resource_id")}
    if FACTS_DIR.is_dir():
        for f in FACTS_DIR.glob("*.json"):
            if f.name not in keep:
                f.unlink(missing_ok=True)      # a VM released: its facts go with it
    report = []
    for iso in isolations:
        rid = str(iso.get("resource_id") or "")
        if not rid or iso.get("releasing_at"):
            continue
        last, key = load(rid), rid.rstrip("/").lower()
        if last and last.get("isolated_at") == iso.get("isolated_at") and \
                now - (_epoch(last.get("read_at")) or 0) < every:
            continue
        held = _LAST_READ.get(key)
        if held and held[0] == iso.get("isolated_at") and now - held[1] < every:
            continue                           # read this interval already: its file was not written
        try:
            facts = read_facts(connector, iso, now)
        except NotImplementedError:
            return report                      # the provider can't say: nothing written
        _LAST_READ[key] = (str(iso.get("isolated_at") or ""), now)
        FACTS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        _atomic_write_text(_file(rid), json.dumps(facts, indent=1, sort_keys=True))
        report.append({"vm": rid.rsplit("/", 1)[-1], "verdict": facts["verdict"], "actors": len(facts["actors"])})
    return report


def card_view(resource_id: str) -> dict | None:
    """What the isolation card shows of the facts: the verdict, when, and each actor — its ids, its
    role, its gestures (operation, kind, time, status), its rights' verdict and why. None: never
    read. Text from Azure stays text: the console escapes it."""
    f = load(resource_id)
    if not f:
        return None
    actors = []
    for a in f.get("actors") or []:
        r = a.get("rights") or {}
        actors.append({
            "ids": [str(i) for i in a.get("ids") or []][:4],
            "role": str(a.get("role") or ""),
            "gestures": [{k: str(g.get(k) or "") for k in ("at", "operation", "kind", "status")}
                         for g in (a.get("gestures") or [])][:12],
            "rights": str(r.get("verdict") or "unreadable"),
            "held": [f"{h.get('role', '')} ({h.get('scope', '')})" for h in r.get("held") or []][:6],
            "why": [str(w) for w in r.get("unreadable") or []][:6],
        })
    return {"verdict": str(f.get("verdict") or "unreadable"), "read_at": str(f.get("read_at") or ""),
            "since": str(f.get("since") or ""), "unreadable": [str(w) for w in f.get("unreadable") or []][:6],
            "actors": actors, "for_information": True}
