"""LOGF2 (#1233): when Entra ID's last event happened, read on Microsoft Graph — so that the silence of a
table of Entra in the workspace is judged by Entra itself (glorfindel/entra_freshness.py).

**The reads**, one per table, always `$top=1`, a GET of `graph.GraphReader` and nothing else (read only by
construction; no SDK of its own, MC0):
  - `AuditLogs` ↔ `GET /auditLogs/directoryAudits?$top=1&$orderby=activityDateTime desc`, its
    `activityDateTime`;
  - `SigninLogs` ↔ `GET /auditLogs/signIns?$top=1&$orderby=createdDateTime desc`, its `createdDateTime`
    (v1.0 lists the interactive sign-ins only, as SigninLogs holds; `createdDateTime` supports `$orderby`,
    and its list is already in that order).
The right: `AuditLog.Read.All` (application), for both — Microsoft's documentation of each list. The
sign-ins also need a tenant licensed Entra ID P1 or P2: a tenant without answers a 403, read as any 403.

**No equivalent** (`NO_EQUIVALENT`): the service principals' sign-ins (AADServicePrincipalSignInLogs)
are listed by Graph's beta only (`$filter=signInEventTypes/any(t: t eq 'servicePrincipal')`); the
non-interactive and the managed identities' sign-ins the same. `GraphReader` reads v1.0 and nothing else:
these tables are said « no equivalent on Graph v1.0 », never read, never « nothing ».

**What a read answers** (`last_event`): {"last": ISO in UTC, "error": None} — Entra's last event; {"last":
None, "error": None} — Graph answered an empty list: Entra has no event in its retention; {"last": None,
"error": text} — a 403 (the right missing), any other failure, an answer of another form: never « nothing ».
The text is in English, built from the failure's kind, its HTTP status and Graph's filtered error code —
never Graph's own message, never an id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from glorfindel.providers.azure.graph import Unreadable

RIGHT = "AuditLog.Read.All"
# table → (the collection, its query, the field of its date). Always $top=1, newest first.
SOURCES = {
    "AuditLogs": ("/auditLogs/directoryAudits", {"$top": "1", "$orderby": "activityDateTime desc"},
                  "activityDateTime"),
    "SigninLogs": ("/auditLogs/signIns", {"$top": "1", "$orderby": "createdDateTime desc"}, "createdDateTime"),
}
_BETA_ONLY = "no equivalent on Graph v1.0 (its sign-ins are listed by Graph's beta only)"
NO_EQUIVALENT = {
    "AADServicePrincipalSignInLogs": _BETA_ONLY,
    "AADNonInteractiveUserSignInLogs": _BETA_ONLY,
    "AADManagedIdentitySignInLogs": _BETA_ONLY,
}
OTHER = "no equivalent on Graph read by the watch"


def request(table: str) -> tuple[str, dict, str] | None:
    """The read of a table on Graph — (path, params, the field of its date) —, or None: no equivalent."""
    src = SOURCES.get(table)
    return (src[0], dict(src[1]), src[2]) if src else None


def no_equivalent(table: str) -> str:
    """Why a table is not read on Graph ('' when it is)."""
    return "" if table in SOURCES else NO_EQUIVALENT.get(table, OTHER)


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


def _iso(value) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def last_event(reader, table: str, deadline: float | None = None) -> dict:
    """Entra's last event for `table` (module docstring): {"last", "error"}."""
    req = request(table)
    if req is None:
        return {"last": None, "error": no_equivalent(table)}
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
    last = _iso(first.get(field)) if isinstance(first, dict) else None
    if last is None:
        return {"last": None, "error": f"Graph's answer unreadable (no {field})"}
    return {"last": last, "error": None}
