"""LOGF1 (#1183): the watch says whether the workspace's logs still arrive.

A diagnostic setting cut on the tenant or on the subscription, and the rules of Entra ID and of the
control plane keep polling without an error — on empty tables. Glorfindel is then blind, and did not say
so. Now the watch reads, for each table its rules read, when its last log arrived, and says it:

- **The tables** (`wanted`): those of the rules enabled and bound to a backend of Log Analytics
  (`pollable_rules`, `backend_type_of(source) == "azure_monitor"`: Perf, Syslog, AzureActivity, Entra's),
  once per workspace. A rule's table is the first table of its query (`first_table`: comments left out,
  the `let` names it defines never taken for a table, a `union` read for its first operand); a query the
  parse does not read falls back on what its detector knows (`AzureActivity` for `azure_activity`, the
  first table of Entra ID it names for `azure_entra`). A query that reads several tables (a `join`, a
  `union`) is read for its first one only: the others are not followed. Its comments and its text literals
  (quoted, `@"…"`, ```…```, masked `h"…"`) are read in one pass, left to right, before the statements are
  cut at `;`: a `;` in a string never cuts one, a `//` in a string (`"https://…"`) never cuts its line
  (LOGF1b). `_query_code` (glorfindel/detection_rules.py) is not used here and left as it is: it still
  cuts a line at a `//` in a string, for its other readers (`_reads_entra_table`, `_reads_activity_table`,
  `RulePoller._plane`, agent.py) — changing it changes how they read a query's plane, not this lot's.
- **The read** (`query`): a KQL query fixed by the code, one per table and per workspace —
  `<Table> | where TimeGenerated > ago(<window>) | summarize LastIngest = max(ingestion_time())`: when the
  last log *arrived* in the workspace, not when its event happened — a log that comes late is still a log
  that came. Its column is never a word of KQL: `last` was one, and every read failed in a 400
  BadArgumentError, its SyntaxError inside (LOGF1c; `COLUMN`, kept so by `kql.reserved_names`).
  The window: twice the threshold, at least 24 h (`window_hours`). Every `EVERY_S` (15 min) for each table; on Log Analytics' budget of the watch (DOS4, glorfindel/read_budget.py), never more
  than half of its minute: the detection, which only notes its queries, keeps the other half — a table
  the budget leaves out is read again a minute later (`RETRY_S`), its last value kept.
- **What is written** (`state_file`, `~/.glorfindel/log_freshness.json`, written at once): per table,
  `last` (ISO, or null: read, no log in the window), `error` (a read that failed: a 429, a 403, the
  network — never « no log »; its text without a GUID nor a URL, `short_error`: a workspace's, a tenant's
  or an application's id never shown; an Azure answer's deepest inner error said first, its cause —
  LOGF1c), `plane` (`identity`, `control`, `data`: `planes`) and, only for a
  table the budget left out at this pass whose kept read is a date, or that was never read (null),
  `deferred: true` — its `error` the deferral's (DEFERRED), which the console sets aside for `last`; a
  table left out otherwise keeps its last known state (a 403, a silence), never `deferred`, and neither a
  failure nor a silence of another workspace is hidden behind a deferral (LOGF1b, `merged`). The console reads it for
  `/api/watch/status` (`console_field`, each key checked strictly); a file it cannot read, or of another
  form, leaves the field out.
- **The card** (`TYPE`, `logs_silent`): only for a table of the identity plane (Entra ID) or of the
  control plane (`carded`, `plane_of_read`: the table itself when it names its plane — Entra ID's, the
  Activity Log's, a known table of the data plane —, else the rule's source, `plane_of`; a table two rules
  read on two planes takes a card over none, identity first) — the maintainer's decision of 25/11: Perf,
  Syslog, StorageBlobLogs are calm by nature and stay read, in the field, never on a card; a rule of
  Entra ID misfiled on Perf does not make Perf one (LOGF1b). Such a table read whose last log is older than
  `GLORFINDEL_LOG_SILENT_HOURS` (24 h by default, read strictly: `silent_after_hours`; a week of measure
  on the bench before it is tightened), or with none in the window, makes one card, without a resource
  (the watch's, MBV1), once an episode and per table; it closes when the logs come back, or when the table
  is no longer followed (a rule removed, or every rule: closed at the next pass; an episode whose card
  could not be closed stays in the file, closed at a later pass). A table left out by the budget with a
  date neither opens nor closes one. Not a decision
  (escalations._NOT_DECISIONS). A read that fails makes no card: it is said in the field, and once in the
  watch's log. A card the store cannot write (or close) is said once, never the pass stopped: the file
  is written whatever.

Nothing here reaches the model: the freshness enters neither the signal nor its message.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENV = "GLORFINDEL_LOG_SILENT_HOURS"
DEFAULT_H = 24.0                   # LOGF1, the maintainer's decision of 25/11 (6 h before)
MIN_H, MAX_H = 1.0, 168.0          # an hour (the reads come every 15 min) to a week
MIN_WINDOW_H = 24.0
EVERY_S = 900.0                    # each table read again every 15 min
RETRY_S = 60.0                     # a table the budget left out: read again a minute later
TYPE = "logs_silent"
WHO = "freshness"                  # on Log Analytics' budget (read_budget.LOG_ANALYTICS)
DEFERRED = "not read: the watch's Log Analytics budget is held (DOS4), read again the next minute"
UNFOLLOWED = "table no longer followed (LOGF1)"
BACK = "logs back (LOGF1)"
CARDED_PLANES = ("identity", "control")
PLANES = ("identity", "control", "data")   # the console's `plane`, in the order a table read twice takes
VERSION = 2                                # LOGF1b: `deferred` and `plane` per table
# The column the read names: never `last`, a word of KQL — Log Analytics answers that query a 400
# BadArgumentError, a SyntaxError inside (measured in the workspace's editor, 26/11: LOGF1c, #1212).
COLUMN = "LastIngest"
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
# What opens a tabular expression without being a table.
_NOT_TABLES = {"union", "find", "search", "print", "range", "datatable", "externaldata", "evaluate",
               "materialize", "view", "toscalar", "let", "set", "declare", "pattern", "alias", "restrict",
               "true", "false", "null"}
# The data plane's tables a rule may read (the VMs' logs, the metrics, the storage's): a rule of Entra ID
# or of the control plane on one of them is misfiled — the table stays `data`, never a card (LOGF1b).
_DATA_TABLES = re.compile(r"(?:Perf|Syslog|Heartbeat|Event|SecurityEvent|InsightsMetrics|VMConnection|VMProcess"
                          r"|VMBoundPort|VMComputer|AzureMetrics|CommonSecurityLog|W3CIISLog|ContainerLog(?:V2)?"
                          r"|Storage[A-Za-z]*Logs)\Z", re.I)
_ENTRA_TABLES = ("AuditLogs", "SigninLogs", "AADServicePrincipalSignInLogs",
                 "AADNonInteractiveUserSignInLogs", "AADManagedIdentitySignInLogs")


def state_file() -> Path:
    """Where the watch writes what it read, and the console reads it."""
    return Path.home() / ".glorfindel" / "log_freshness.json"


def silent_after_hours(environ=None) -> tuple[float, str]:
    """The threshold in hours, and what to say of the variable when it was not taken: a finite number
    from MIN_H to MAX_H; anything else (text, 0, a negative, NaN, infinity, out of the range) — the
    default, said."""
    raw = str((os.environ if environ is None else environ).get(ENV, "")).strip()
    if not raw:
        return DEFAULT_H, ""
    try:
        h = float(raw)
    except ValueError:
        h = math.nan
    if math.isfinite(h) and MIN_H <= h <= MAX_H:
        return h, ""
    return DEFAULT_H, (f"{ENV}={raw[:20]}: read as {DEFAULT_H:g} h (a number of hours from {MIN_H:g} to "
                       f"{MAX_H:g} expected: the default)")


def window_hours(h: float) -> float:
    """The window read: twice the threshold, at least 24 h — a table silent past the threshold still has
    its last log in it, until twice as long."""
    return max(MIN_WINDOW_H, 2 * h)


# KQL's text literals: a multi-line one (```…```, ~~~…~~~), a verbatim one (@"…", @'…': a quote doubled to
# be one), a plain one (its escapes read) — each masked or not (`h"…"`, `H@'…'`: the `h` a word of its own,
# never the end of a name). Emptied before a query is cut at `;`: a `;` in a string never cuts a statement.
_LITERALS = re.compile(r"(?:\b[hH])?(?:```.*?```|~~~.*?~~~|@\"(?:[^\"]|\"\")*\"|@'(?:[^']|'')*'"
                       r"|\"(?:[^\"\\\n]|\\.)*\"|'(?:[^'\\\n]|\\.)*')", re.S)
# A comment and a literal read in one pass, left to right: whichever opens first wins — a `//` in a string
# (`"https://…"`) never cuts its line, a quote in a comment (`// it's`) never opens a string (LOGF1b).
_LEXED = re.compile(r"(?P<comment>//[^\n]*)|(?P<literal>" + _LITERALS.pattern + ")", re.S)


def _code(query: str, literals: bool = True) -> str:
    """The query's code: its comments out, its text literals emptied (`""`) — or kept as they are
    (`literals=False`: the fallback of `table_of`, where `table("SigninLogs")` names its table)."""
    return _LEXED.sub(lambda m: "" if m.group("comment") is not None else ('""' if literals else m.group(0)),
                      query or "")


def _statements(query: str):
    return [s.strip() for s in _code(query).split(";") if s.strip()]


def _source_of(expr: str, defined: set[str]) -> str | None:
    """The table a tabular expression starts from, or None (a `let` name, a function, a keyword)."""
    m = re.match(r"\(?\s*([A-Za-z_][A-Za-z0-9_]*)\b\s*([(:]?)", expr)
    if not m:
        return None
    name, call = m.group(1), m.group(2)          # `(`: a function; `:`: a parameter of a let function
    if name.lower() == "union":
        rest = re.sub(r"^(?:\s*\w+\s*=\s*[\w\"']+)*", "", expr[m.end(1):])
        return _source_of(rest.strip(), defined)
    if call or name in defined or name.lower() in _NOT_TABLES:
        return None
    return name


def first_table(query: str) -> str | None:
    """The first table a KQL query reads (comments left out), or None."""
    defined: set[str] = set()
    for stmt in _statements(query or ""):
        m = re.match(r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", stmt, re.S)
        expr = m.group(2) if m else stmt
        table = _source_of(expr, defined)
        if m:
            defined.add(m.group(1))
        if table:
            return table
    return None


def table_of(rule) -> str | None:
    """A rule's table: the first of its query, else what its detector knows (AzureActivity, Entra's)."""
    table = first_table(rule.query)
    if table:
        return table
    code = _code(rule.query, literals=False).lower()    # `table("SigninLogs")`: the literal names it
    if rule.source == "azure_activity":
        return "AzureActivity"
    if rule.source == "azure_entra":
        found = [(code.find(t.lower()), t) for t in _ENTRA_TABLES if re.search(rf"\b{t.lower()}\b", code)]
        return min(found)[1] if found else None
    return None


def _followed(rules):
    """(rule, table) for each rule enabled and bound to Log Analytics whose table is read."""
    from glorfindel.detection_rules import pollable_rules
    from glorfindel.detectors import backend_type_of
    for rule in pollable_rules(list(rules or [])):
        if backend_type_of(rule.source) != "azure_monitor":
            continue
        table = table_of(rule)
        if table and _IDENT.match(table):
            yield rule, table


def plane_of_read(rule, table: str) -> str:
    """The plane of a table as a rule reads it: the table's own when it names one — Entra ID's
    (`identity`), the Activity Log's (`control`), a known table of the data plane (`data`: a rule of
    Entra ID or of the control plane misfiled on Perf never makes Perf a card, LOGF1b) —, else the rule's
    source (`plane_of`): a table of Entra ID the regex does not know (AADProvisioningLogs) read by a rule
    `azure_entra` is the identity plane, its card kept. As `RulePoller._plane` reads a query of another
    source."""
    from glorfindel.detection_rules import _reads_activity_table, _reads_entra_table
    from glorfindel.detectors import plane_of
    if _reads_entra_table(table):
        return "identity"
    if _reads_activity_table(table):
        return "control"
    if _DATA_TABLES.match(table):
        return "data"
    plane = plane_of(rule.source)
    return plane if plane in PLANES else "data"          # a plane this module does not know: no card


def planes(rules) -> dict[str, str]:
    """The plane of each table followed. A table two rules read on two planes (a table of no known plane,
    read by rules of two sources) takes the first of `PLANES` — a card over none: one rule that a silent
    table blinds is enough; identity before control, whatever the rules' order."""
    out: dict[str, str] = {}
    for rule, table in _followed(rules):
        plane, prev = plane_of_read(rule, table), out.get(table)
        if prev is None or PLANES.index(plane) < PLANES.index(prev):
            out[table] = plane
    return out


def carded(rules) -> set[str]:
    """The tables followed that open a card `logs_silent`: those of the identity and the control plane
    (the maintainer's decision of 25/11). The others are read and said in the field, never on a card."""
    return {table for table, plane in planes(rules).items() if plane in CARDED_PLANES}


def wanted(rules) -> list[tuple[str, str]]:
    """(workspace, table) for each table the rules enabled and bound to Log Analytics read, once each."""
    out: list[tuple[str, str]] = []
    for rule, table in _followed(rules):
        if (rule.workspace_id, table) not in out:
            out.append((rule.workspace_id, table))
    return out


def query(table: str, window_h: float) -> str:
    """The query, fixed by the code: when the table's last log arrived (its ingestion), in the window —
    its column `COLUMN`, never a word of KQL (glorfindel/kql.py, `reserved_names`)."""
    if not _IDENT.match(table or ""):
        raise ValueError(f"not a table name: {table!r}")
    return (f"{table}\n| where TimeGenerated > ago({int(math.ceil(window_h))}h)\n"
            f"| summarize {COLUMN} = max(ingestion_time())")


def _iso(value) -> str | None:
    """A datetime (or its ISO text) as ISO in UTC; None when empty or unreadable."""
    if value in (None, ""):
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


# What an error's text may carry and the console never shows: a URL (azure-core's network error repeats
# requests', `…/v1/workspaces/<id>/query`), a GUID (a workspace's, a tenant's, an application's: an
# azure-identity error names them), with or without its dashes. Masked before the text is cut: cut first,
# a GUID's start would no longer be read as one, and would show.
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s'\"<>()\[\]{}]+", re.I)
# With its dashes, masked wherever it stands (a hex character stuck to it hides nothing, LOGF1b); without
# them, only 32 hex characters on their own — never a part of a longer hash.
_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                   r"|(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", re.I)


def _scrubbed(text: str) -> str:
    """`text` without a URL nor a GUID: « <url> », « <id> »."""
    return _GUID.sub("<id>", _URL.sub("<url>", text))


_INNER_LABEL = "Inner error:"
INNER_MAX = 160


def _inner_nodes(exc: BaseException) -> list[dict]:
    """The inner errors of an Azure answer, outermost first: those of its `error` (azure-core's
    `HttpResponseError.error`, its `innererror`, nested), else those its text writes after « Inner error: »
    (the same JSON, azure-core's `message_details`) — none: []."""
    start = getattr(getattr(exc, "error", None), "innererror", None)
    if not isinstance(start, dict):
        text = str(exc)
        at = text.find(_INNER_LABEL)
        try:
            start = json.JSONDecoder().raw_decode(text[at + len(_INNER_LABEL):].lstrip())[0] if at >= 0 else None
        except ValueError:
            start = None
    nodes: list[dict] = []
    while isinstance(start, dict) and start and len(nodes) < 8:
        nodes.append(start)
        start = start.get("innererror")
    return nodes


def _inner(exc: BaseException) -> str:
    """The deepest inner error that says something: « code: message » (its message's first line), masked
    (`_scrubbed`), then cut at INNER_MAX — Log Analytics' 400 BadArgumentError hides its cause there (a
    SyntaxError, LOGF1c). None: ''."""
    for node in reversed(_inner_nodes(exc)):
        code = str(node.get("code") or "").strip()
        message = (str(node.get("message") or "").strip().splitlines() or [""])[0]
        said = ": ".join(x for x in (code, message) if x)
        if said:
            return _scrubbed(said)[:INNER_MAX]
    return ""


def short_error(exc: BaseException) -> str:
    """A failed read, in a few words: its HTTP status when it has one, its type, the deepest inner error
    of an Azure answer when it has one (`_inner`: what a 400 BadArgumentError hides, its SyntaxError), its
    first line — each masked (`_scrubbed`), then cut. The inner error comes first: the console cuts the
    text, and the cause is what it keeps."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    head = f"HTTP {status}" if status else type(exc).__name__
    first = (str(exc).strip().splitlines() or [""])[0]
    line = _scrubbed(first)[:120]
    return " — ".join(x for x in (head, _inner(exc), line) if x)


def read_one(client, table: str, window_h: float, now: float) -> dict:
    """One table read: {"last": ISO | None, "error": None} — or {"last": None, "error": text} when the
    read failed: a failure is never « no log »."""
    end = datetime.fromtimestamp(now, timezone.utc)
    try:
        rows = client.run_query(query(table, window_h),
                                timespan=(end - timedelta(hours=window_h), end + timedelta(minutes=1)))
    except Exception as exc:
        return {"last": None, "error": short_error(exc)}
    lasts = [_iso(r.get(COLUMN)) for r in rows or [] if isinstance(r, dict)]
    lasts = [x for x in lasts if x]
    return {"last": max(lasts) if lasts else None, "error": None}


def merged(reads: dict, planes: dict | None = None) -> dict[str, dict]:
    """Per table, over its workspaces: the oldest last log (a workspace silent is the table silent), the
    first error, and its plane (`data` when none is known) — what the console shows. A read the budget
    left out (`deferred_at`) keeps its last read: the table is `deferred: true` only when what it keeps is
    a date, or when it was never read (`last: null`, its `error` the placeholder DEFERRED) — its `error` then
    the deferral's, which the console sets aside for `last`. Anywhere else the table keeps its last known
    state: a read that failed (a 403) is still its error, a read with no log still silent, never
    `deferred` — the tile never green on a table silent nor on one that failed (LOGF1b). A failure, or a
    silence, of another workspace is never hidden behind a deferral either."""
    out: dict[str, dict] = {}
    for r in reads.values():
        t = out.setdefault(r["table"], {"last": None, "error": None, "_lasts": [], "_none": False,
                                        "_unread": False, "_deferred": False})
        deferred, error = bool(r.get("deferred_at")), r.get("error")
        if deferred and error == DEFERRED and not r.get("last"):
            t["_unread"] = t["_deferred"] = True             # left out before its first read
        elif error and error != DEFERRED:
            t["error"] = t["error"] or error                  # its last read failed, deferred or not
        elif r.get("last"):
            t["_lasts"].append(r["last"])
            t["_deferred"] = t["_deferred"] or deferred
        else:
            t["_none"] = True                                 # a real read, no log in the window
    for table, t in out.items():
        lasts, none, unread, deferred = t.pop("_lasts"), t.pop("_none"), t.pop("_unread"), t.pop("_deferred")
        t["last"] = None if none or unread or not lasts else min(lasts)
        if deferred and not t["error"] and not none:
            t["error"], t["deferred"] = DEFERRED, True
        t["plane"] = (planes or {}).get(table, "data")
    return out


def silent(entry: dict, now: float, h: float) -> bool:
    """A table read whose last log is older than the threshold, or with none in the window. A read that
    failed is never silent: it is unknown."""
    if entry.get("error"):
        return False
    last = entry.get("last")
    if not last:
        return True
    return now - datetime.fromisoformat(last).timestamp() > h * 3600


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def _epoch(value) -> float | None:
    iso = _iso(value)
    return datetime.fromisoformat(iso).timestamp() if iso else None


def load(path: Path | None = None) -> dict:
    """What the watch last wrote, or {} (absent, unreadable, of another form)."""
    try:
        doc = json.loads((path or state_file()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _field_of(doc: dict) -> dict | None:
    """The console's field from the file, checked whole: None when any part is not of its form."""
    tables, h, read_at = doc.get("tables"), doc.get("silent_after_hours"), doc.get("read_at")
    if not isinstance(tables, dict) or not isinstance(read_at, str) or _iso(read_at) is None:
        return None
    if isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h):
        return None
    out = {}
    for name, e in tables.items():
        if not (isinstance(name, str) and isinstance(e, dict)):
            return None
        last, error = e.get("last"), e.get("error")
        if not (last is None or (isinstance(last, str) and _iso(last))) or not (error is None or isinstance(error, str)):
            return None
        if not _new_keys_ok(e):
            return None
        out[name] = {"last": last, "error": error, **{k: e[k] for k in ("deferred", "plane") if k in e}}
    return {"read_at": read_at, "silent_after_hours": h, "tables": out}


def _new_keys_ok(e: dict) -> bool:
    """LOGF1b's keys, read strictly: `deferred` a boolean, `plane` one of PLANES — each absent from a file
    of LOGF1 (before them), which the watch rewrites at its next read."""
    return (("deferred" not in e or isinstance(e["deferred"], bool))
            and ("plane" not in e or (isinstance(e["plane"], str) and e["plane"] in PLANES)))


def console_field(path: Path | None = None) -> dict:
    """`/api/watch/status`'s field: {"log_freshness": {...}} — {} when the watch wrote nothing yet, is of
    a version before LOGF1, or its file cannot be read: the console then greys nothing. Never raises."""
    try:
        field = _field_of(load(path))
    except Exception:
        field = None
    return {"log_freshness": field} if field is not None else {}


def _default_client(workspace_id: str):
    """The plain Log Analytics reader of the workspace (glorfindel/providers/azure/monitor.py, through
    the detectors' registry): the query read as written, no detector's marks on its rows."""
    from glorfindel.detectors import detector_for
    return detector_for("azure_monitor", workspace_id=workspace_id)


def _steps(table: str) -> list[str]:
    return [f"Check in the workspace that the table {table} still receives logs "
            f"(`{table} | summarize max(ingestion_time())`).",
            "Entra ID (AuditLogs, the sign-in logs): the tenant's diagnostic setting to this workspace "
            "(Entra ID → Diagnostic settings).",
            "AzureActivity: the subscription's diagnostic setting (Activity log → Export Activity Logs).",
            "The card closes by itself when the logs come back; until then, the rules that read this "
            "table run on an empty table."]


class Freshness:
    """The reads of the logs' freshness and the memory they keep — between passes, and across a restart
    of the watch (the file: the reads, the episodes and their cards).

    `client_for(workspace)` gives what reads a workspace (`run_query`); `budget`, Log Analytics' budget
    (read_budget.LOG_ANALYTICS); `record`, `resolve` and `pending`, the cards' store
    (glorfindel/escalations.py); `say`, a line in the watch's log."""

    def __init__(self, rules, *, client_for=None, budget=None, clock=time.time, path: Path | None = None,
                 record=None, resolve=None, pending=None, say=None, environ=None) -> None:
        from glorfindel import escalations, read_budget
        self._wanted = wanted(rules)
        self._planes = planes(rules)
        self._carded = {t for t, plane in self._planes.items() if plane in CARDED_PLANES}
        self._client_for = client_for or _default_client
        self._clients: dict[str, object] = {}
        self._budget = budget or read_budget.LOG_ANALYTICS
        self._clock = clock
        self._path = path
        self._record = record or escalations.record
        self._resolve = resolve or escalations.resolve
        self._pending = pending or escalations.pending
        self._say = say or (lambda line: None)
        self.hours, self.note = silent_after_hours(environ)
        doc = load(path)
        keys = {f"{ws}|{t}" for ws, t in self._wanted}
        self._reads = {k: r for k, r in (doc.get("reads") or {}).items()
                       if k in keys and isinstance(r, dict) and r.get("table")}
        episodes = {t: e for t, e in (doc.get("episodes") or {}).items() if isinstance(e, dict)}
        # A table no longer followed, or that no longer opens a card (a rule removed, changed): its
        # episode closed at the next pass, its card with it, never left open on a table nobody reads.
        self._stale = {t: e for t, e in episodes.items() if t not in self._carded}
        self._episodes = {t: e for t, e in episodes.items() if t in self._carded}
        self._said: dict[str, str] = {}
        self._card_failed: set[str] = set()

    @property
    def tables(self) -> list[tuple[str, str]]:
        return list(self._wanted)

    def has_work(self, now: float | None = None) -> bool:
        """A pass to make: a table due, or an episode of a table no longer followed to close."""
        return bool(self._stale) or bool(self.due(now))

    def due(self, now: float | None = None) -> list[tuple[str, str]]:
        """The (workspace, table) to read now: never read, read EVERY_S ago, or left out by the budget
        RETRY_S ago."""
        now = self._clock() if now is None else now
        out = []
        for ws, table in self._wanted:
            r = self._reads.get(f"{ws}|{table}") or {}
            deferred, read = _epoch(r.get("deferred_at")), _epoch(r.get("read_at"))
            if read is None or (deferred is not None and now - deferred >= RETRY_S) \
                    or (deferred is None and now - read >= EVERY_S):
                out.append((ws, table))
        return out

    def _room(self) -> bool:
        """One query on Log Analytics' budget, within half of its minute (the detection keeps the
        other half), one at least: a cap of 1 still lets one read in a minute that is empty (the
        detection only notes its queries, never refused: it loses nothing); 0: no threshold, the query
        noted."""
        cap = self._budget.per_min()
        if cap <= 0:
            self._budget.spend(1, WHO)
            return True
        if sum(self._budget.used().values()) + 1 > max(1, cap // 2):
            return False
        return self._budget.take(1, WHO)

    def _read(self, ws: str, table: str, now: float) -> None:
        key = f"{ws}|{table}"
        if not self._room():
            # Left out by the budget: its last value kept (none yet: « not read »), read again soon.
            prev = self._reads.get(key) or {"workspace": ws, "table": table, "read_at": _stamp(now),
                                             "last": None, "error": DEFERRED}
            self._reads[key] = {**prev, "deferred_at": _stamp(now)}
            return
        if ws not in self._clients:
            self._clients[ws] = self._client_for(ws)
        self._reads[key] = {"workspace": ws, "table": table, "read_at": _stamp(now),
                            **read_one(self._clients[ws], table, window_hours(self.hours), now)}

    def pass_once(self) -> dict | None:
        """The tables due read, the cards opened or closed, the file written; None when none was due."""
        now = self._clock()
        due = self.due(now)
        if not due and not self._stale:
            return None
        if self.note:
            self._say(self.note)
            self.note = ""
        for ws, table in due:
            try:
                self._read(ws, table, now)
            except Exception as exc:       # a client that cannot be made: an error, never « no log »
                self._reads[f"{ws}|{table}"] = {"workspace": ws, "table": table, "read_at": _stamp(now),
                                                "last": None, "error": short_error(exc)}
        tables = merged(self._reads, self._planes)
        self._errors_said(tables)
        self._close_stale()
        self._cards(tables, now)
        # The episodes of the tables no longer followed whose card could not be closed, written too: read
        # back, they fall in `_stale` again, their card closed at a later pass (LOGF1b).
        doc = {"version": VERSION, "read_at": _stamp(now), "silent_after_hours": self.hours,
               "window_hours": window_hours(self.hours), "tables": tables, "reads": self._reads,
               "episodes": {**self._stale, **self._episodes}}
        from glorfindel.response.state_files import _atomic_write_text
        _atomic_write_text(self._path or state_file(), json.dumps(doc, indent=1, sort_keys=True))
        return doc

    def _errors_said(self, tables: dict) -> None:
        """A read that fails, said once in the watch's log until the table reads again."""
        for table, e in tables.items():
            if not e.get("error"):
                self._said.pop(table, None)
            elif e["error"] != DEFERRED and table not in self._said:
                self._said[table] = e["error"]
                self._say(f"logs' freshness: the read of {table} failed ({e['error']}) — shown in the "
                          "console, no “logs silent” card")

    def _close_stale(self) -> None:
        """The episodes of the tables no longer followed (nor carded), closed with their card."""
        for table, episode in list(self._stale.items()):
            try:
                self._close(table, episode, note=UNFOLLOWED, store=self._stale)
            except Exception as exc:
                self._card_failure(table, exc)
            else:
                self._card_failed.discard(table)     # closed: a later failure is said again (LOGF1b)

    def _cards(self, tables: dict, now: float) -> None:
        """Silent past the threshold, a table of the identity or the control plane: one card an episode
        and per table; the logs back: closed. A read that failed neither opens nor closes one. A card the
        store cannot write is said once, the next tables still seen, the file still written."""
        for table, e in tables.items():
            if table not in self._carded:
                continue
            episode = self._episodes.get(table)
            try:
                if silent(e, now, self.hours):
                    if episode is None:
                        self._open(table, e, now)
                elif episode is not None and not e.get("error"):
                    self._close(table, episode)
            except Exception as exc:
                self._card_failure(table, exc)
            else:
                self._card_failed.discard(table)

    def _card_failure(self, table: str, exc: BaseException) -> None:
        """A card not written (or not closed): said once until it is, tried again at the next pass."""
        if table not in self._card_failed:
            self._card_failed.add(table)
            self._say(f"logs' freshness: the card of {table} could not be written ({short_error(exc)}) "
                      "— tried again at the next pass")

    def _open(self, table: str, e: dict, now: float) -> None:
        since = (f"its last log arrived at {e['last'][:16].replace('T', ' ')} UTC" if e.get("last")
                 else f"no log arrived in the last {window_hours(self.hours):g} hours")
        reason = (f"Logs silent: the table {table} receives nothing anymore — {since} (threshold "
                  f"{self.hours:g} h, `{ENV}`). The rules that read it run without an error on an empty table: "
                  "Glorfindel no longer sees what they detect.")
        card = self._record(signal_id=f"logs-silent-{table}-{int(now)}", resource_id="", action="",
                            escalation_type=TYPE, reason=reason, suggested_steps=_steps(table))
        self._episodes[table] = {"since": _stamp(now), "card": card}
        self._say(f"logs silent: {table} — card {str(card)[:8]} ({since})")

    def _close(self, table: str, episode: dict, note: str = BACK, store: dict | None = None) -> None:
        card = str(episode.get("card") or "")
        if card and any(c.get("id") == card for c in self._pending()):
            self._resolve(card, note=note)
        del (self._episodes if store is None else store)[table]
        head = f"logs back: {table}" if store is None else f"{table}: {note}"
        self._say(head + (f" — card {card[:8]} closed" if card else ""))
