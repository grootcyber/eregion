"""LOGF2 (#1233): Entra ID's last event that should already be in the workspace, read on Microsoft Graph — so
that the silence of a table of Entra in the workspace is judged by Entra itself (glorfindel/entra_freshness.py).

**The reads**, one per table, always `$top=1`, a GET of `graph.GraphReader` and nothing else (read only by
construction; no SDK of its own, MC0). Each reads the last event **older than the ingestion's delay**
(`cutoff`: now − 15 min) — an event of the last minutes is still on its way, and a tenant whose events come
every few minutes would otherwise always show one « too recent to judge » (LOGF2's review):
  - `AuditLogs` ↔ `GET /auditLogs/directoryAudits?$top=1&$orderby=activityDateTime desc&$filter=activityDateTime
    le <cutoff>`, its `activityDateTime` (`$filter` in `ge`/`le`, `$top` and `$orderby` documented on v1.0);
  - `SigninLogs` ↔ `GET /auditLogs/signIns?$top=1&$filter=createdDateTime le <cutoff>`, its `createdDateTime`
    — v1.0 lists the interactive sign-ins only (as SigninLogs holds), already newest first, and documents
    `$top`, `$filter` and `$skiptoken` on that list: no `$orderby`.
The right: `AuditLog.Read.All` (application), for both — Microsoft's documentation of each list. The
sign-ins also need a tenant licensed Entra ID P1 or P2: a tenant without answers a 403, read as any 403.

**No equivalent** (`request` None): the service principals' sign-ins (AADServicePrincipalSignInLogs), the
non-interactive and the managed identities' — listed by Graph's beta only (`signInEventTypes`), and
`GraphReader` reads v1.0 alone. These tables are never read on Graph: they keep LOGF1's threshold (24 h by
default), the maintainer's decision of 26/11.

**What a read answers** (`last_event`): {"last": ISO in UTC, "error": None} — Entra's last event up to the
cutoff; {"last": None, "error": None} — Graph answered an empty list: Entra has no such event in its retention;
{"last": None, "error": text} — a 403 (the right missing), any other failure, an answer of another form, a
date past the cutoff by more than `FUTURE_MARGIN_S`: never « nothing ». The text is in English, built from the
failure's kind, its HTTP status and Graph's filtered error code — never Graph's own message, never an id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from glorfindel.providers.azure.graph import Unreadable

RIGHT = "AuditLog.Read.All"
FUTURE_MARGIN_S = 300.0            # a date past the cutoff by more than 5 min: an answer not believed
# table → (the collection, its fixed parameters, the field of its date). Always $top=1, newest first.
SOURCES = {
    "AuditLogs": ("/auditLogs/directoryAudits", {"$top": "1", "$orderby": "activityDateTime desc"},
                  "activityDateTime"),
    "SigninLogs": ("/auditLogs/signIns", {"$top": "1"}, "createdDateTime"),
}


def _odata(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def request(table: str, cutoff: float) -> tuple[str, dict, str] | None:
    """The read of a table on Graph — (path, params, the field of its date) — for its last event at or before
    `cutoff` (an epoch), or None: no equivalent on Graph v1.0."""
    src = SOURCES.get(table)
    if not src:
        return None
    path, params, field = src
    return path, {**params, "$filter": f"{field} le {_odata(cutoff)}"}, field


def _said(exc: Unreadable) -> str:
    """An Unreadable, in English: its kind, its status, Graph's filtered code — never its message."""
    code = f" {exc.code}" if exc.code else ""
    if exc.kind == "right":
        return (f"no right on Graph (HTTP {exc.status}{code}: {RIGHT} missing, or a sign-in log without "
                "Entra ID P1/P2)" if exc.status else "no token for Graph")
    if exc.kind == "delay":
        return "Graph did not answer in time"
    if exc.kind == "off":
        return "Graph not read (no reader: a dry run, the tests)"
    return f"Graph answered HTTP {exc.status}{code}" if exc.status else "Graph's answer unreadable"


def _epoch(value) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def last_event(reader, table: str, cutoff: float, deadline: float | None = None) -> dict:
    """Entra's last event for `table` at or before `cutoff` (module docstring): {"last", "error"}."""
    req = request(table, cutoff)
    if req is None:
        return {"last": None, "error": "no equivalent on Graph v1.0"}
    path, params, field = req
    try:
        body = reader.get(path, params, deadline=deadline)
    except Unreadable as exc:
        return {"last": None, "error": _said(exc)}
    except Exception as exc:              # a reader's bug is said, never taken for an answer
        return {"last": None, "error": f"Graph: {type(exc).__name__}"}
    if body is None:                      # a 404 on a collection: not an answer
        return {"last": None, "error": "Graph answered HTTP 404"}
    items = body.get("value") if isinstance(body, dict) else None
    if not isinstance(items, list):
        return {"last": None, "error": "Graph's answer unreadable (no list)"}
    if not items:
        return {"last": None, "error": None}
    first = items[0]
    at = _epoch(first.get(field)) if isinstance(first, dict) else None
    if at is None:
        return {"last": None, "error": f"Graph's answer unreadable (no {field})"}
    if at > cutoff + FUTURE_MARGIN_S:
        return {"last": None, "error": f"Graph's answer unreadable ({field} past the cutoff)"}
    return {"last": datetime.fromtimestamp(at, timezone.utc).isoformat(), "error": None}
