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
  `union`) is read for its first one only: the others are not followed.
- **The read** (`query`): a KQL query fixed by the code, one per table and per workspace —
  `<Table> | where TimeGenerated > ago(<window>) | summarize last = max(ingestion_time())`: when the last
  log *arrived* in the workspace, not when its event happened — a log that comes late is still a log
  that came. The window: twice the threshold, at least 24 h (`window_hours`). Every `EVERY_S` (15 min)
  for each table; on Log Analytics' budget of the watch (DOS4, glorfindel/read_budget.py), never more
  than half of its minute: the detection, which only notes its queries, keeps the other half — a table
  the budget leaves out is read again a minute later (`RETRY_S`), its last value kept.
- **What is written** (`state_file`, `~/.glorfindel/log_freshness.json`, written at once): per table,
  `last` (ISO, or null: read, no log in the window) and `error` (a read that failed: a 429, a 403, the
  network — never « no log »). The console reads it for `/api/watch/status` (`console_field`); a file it
  cannot read leaves the field out.
- **The card** (`TYPE`, `logs_silent`): a table read whose last log is older than
  `GLORFINDEL_LOG_SILENT_HOURS` (6 h by default, read strictly: `silent_after_hours`), or with none in the
  window, makes one card, without a resource (the watch's, MBV1), once an episode and per table; it closes
  when the logs come back. Not a decision (escalations._NOT_DECISIONS). A read that fails makes no card:
  it is said in the field, and once in the watch's log.

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
DEFAULT_H = 6.0
MIN_H, MAX_H = 1.0, 168.0          # an hour (the reads come every 15 min) to a week
MIN_WINDOW_H = 24.0
EVERY_S = 900.0                    # each table read again every 15 min
RETRY_S = 60.0                     # a table the budget left out: read again a minute later
TYPE = "logs_silent"
WHO = "freshness"                  # on Log Analytics' budget (read_budget.LOG_ANALYTICS)
DEFERRED = "non lue : budget Log Analytics de la watch tenu (DOS4), relue à la minute suivante"
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
# What opens a tabular expression without being a table.
_NOT_TABLES = {"union", "find", "search", "print", "range", "datatable", "externaldata", "evaluate",
               "materialize", "view", "toscalar", "let", "set", "declare", "pattern", "alias", "restrict",
               "true", "false", "null"}
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
    return DEFAULT_H, (f"{ENV}={raw[:20]} : lu comme {DEFAULT_H:g} h (un nombre de {MIN_H:g} à {MAX_H:g} "
                       "heures attendu : le défaut)")


def window_hours(h: float) -> float:
    """The window read: twice the threshold, at least 24 h — a table silent past the threshold still has
    its last log in it, until twice as long."""
    return max(MIN_WINDOW_H, 2 * h)


def _statements(query: str):
    from glorfindel.detection_rules import _query_code
    return [s.strip() for s in _query_code(query).split(";") if s.strip()]


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
    from glorfindel.detection_rules import _query_code
    code = _query_code(rule.query).lower()
    if rule.source == "azure_activity":
        return "AzureActivity"
    if rule.source == "azure_entra":
        found = [(code.find(t.lower()), t) for t in _ENTRA_TABLES if re.search(rf"\b{t.lower()}\b", code)]
        return min(found)[1] if found else None
    return None


def wanted(rules) -> list[tuple[str, str]]:
    """(workspace, table) for each table the rules enabled and bound to Log Analytics read, once each."""
    from glorfindel.detection_rules import pollable_rules
    from glorfindel.detectors import backend_type_of
    out: list[tuple[str, str]] = []
    for rule in pollable_rules(list(rules or [])):
        if backend_type_of(rule.source) != "azure_monitor":
            continue
        table = table_of(rule)
        if table and _IDENT.match(table) and (rule.workspace_id, table) not in out:
            out.append((rule.workspace_id, table))
    return out


def query(table: str, window_h: float) -> str:
    """The query, fixed by the code: when the table's last log arrived (its ingestion), in the window."""
    if not _IDENT.match(table or ""):
        raise ValueError(f"not a table name: {table!r}")
    return f"{table}\n| where TimeGenerated > ago({int(math.ceil(window_h))}h)\n| summarize last = max(ingestion_time())"


def _iso(value) -> str | None:
    """A datetime (or its ISO text) as ISO in UTC; None when empty or unreadable."""
    if value in (None, ""):
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


def short_error(exc: BaseException) -> str:
    """A failed read, in a few words: its HTTP status when it has one, its type, its first line."""
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    head = f"HTTP {status}" if status else type(exc).__name__
    line = (str(exc).strip().splitlines() or [""])[0][:120]
    return f"{head} — {line}" if line else head


def read_one(client, table: str, window_h: float, now: float) -> dict:
    """One table read: {"last": ISO | None, "error": None} — or {"last": None, "error": text} when the
    read failed: a failure is never « no log »."""
    end = datetime.fromtimestamp(now, timezone.utc)
    try:
        rows = client.run_query(query(table, window_h),
                                timespan=(end - timedelta(hours=window_h), end + timedelta(minutes=1)))
    except Exception as exc:
        return {"last": None, "error": short_error(exc)}
    lasts = [_iso(r.get("last")) for r in rows or [] if isinstance(r, dict)]
    lasts = [x for x in lasts if x]
    return {"last": max(lasts) if lasts else None, "error": None}


def merged(reads: dict) -> dict[str, dict]:
    """Per table, over its workspaces: the oldest last log (a workspace silent is the table silent), and
    the first error — what the console shows."""
    out: dict[str, dict] = {}
    for r in reads.values():
        t = out.setdefault(r["table"], {"last": None, "error": None, "_lasts": [], "_none": False})
        if r.get("error"):
            t["error"] = t["error"] or r["error"]
        elif r.get("last"):
            t["_lasts"].append(r["last"])
        else:
            t["_none"] = True
    for t in out.values():
        lasts, none = t.pop("_lasts"), t.pop("_none")
        t["last"] = None if none or not lasts else min(lasts)
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
        out[name] = {"last": last, "error": error}
    return {"read_at": read_at, "silent_after_hours": h, "tables": out}


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
    return [f"Vérifier dans l'espace de travail que la table {table} reçoit encore des journaux "
            f"({table} | summarize max(ingestion_time())).",
            "Entra ID (AuditLogs, journaux de connexion) : le paramètre de diagnostic du tenant vers cet "
            "espace de travail (Entra ID → Paramètres de diagnostic).",
            "AzureActivity : le paramètre de diagnostic de l'abonnement (Journal d'activité → Exporter).",
            "Perf, Syslog : l'agent de la VM et sa règle de collecte (DCR).",
            "La carte se ferme seule quand les journaux reviennent ; d'ici là, les règles qui lisent "
            "cette table tournent sur une table vide."]


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
        self._episodes = {t: e for t, e in (doc.get("episodes") or {}).items() if isinstance(e, dict)}
        self._said: dict[str, str] = {}

    @property
    def tables(self) -> list[tuple[str, str]]:
        return list(self._wanted)

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
        other half); 0: no threshold, the query noted."""
        cap = self._budget.per_min()
        if cap <= 0:
            self._budget.spend(1, WHO)
            return True
        if sum(self._budget.used().values()) + 1 > cap // 2:
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
        if not due:
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
        tables = merged(self._reads)
        self._errors_said(tables)
        self._cards(tables, now)
        doc = {"version": 1, "read_at": _stamp(now), "silent_after_hours": self.hours,
               "window_hours": window_hours(self.hours), "tables": tables, "reads": self._reads,
               "episodes": self._episodes}
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
                self._say(f"fraîcheur des journaux : lecture de {table} en échec ({e['error']}) — dite "
                          "dans la console, aucune carte « muets »")

    def _cards(self, tables: dict, now: float) -> None:
        """Silent past the threshold: one card an episode and per table; the logs back: closed. A read
        that failed neither opens nor closes one."""
        for table, e in tables.items():
            episode = self._episodes.get(table)
            if silent(e, now, self.hours):
                if episode is None:
                    self._open(table, e, now)
            elif episode is not None and not e.get("error"):
                self._close(table, episode)

    def _open(self, table: str, e: dict, now: float) -> None:
        since = (f"son dernier journal est arrivé le {e['last'][:16].replace('T', ' ')} UTC" if e.get("last")
                 else f"aucun journal arrivé dans les {window_hours(self.hours):g} dernières heures")
        reason = (f"Journaux muets : la table {table} ne reçoit plus rien — {since} (seuil {self.hours:g} h, "
                  f"{ENV}). Les règles qui la lisent tournent sans erreur sur une table vide : Glorfindel "
                  "ne voit plus ce qu'elles détectent.")
        card = self._record(signal_id=f"logs-silent-{table}-{int(now)}", resource_id="", action="",
                            escalation_type=TYPE, reason=reason, suggested_steps=_steps(table))
        self._episodes[table] = {"since": _stamp(now), "card": card}
        self._say(f"journaux muets : {table} — carte {str(card)[:8]} ({since})")

    def _close(self, table: str, episode: dict) -> None:
        card = str(episode.get("card") or "")
        if card and any(c.get("id") == card for c in self._pending()):
            self._resolve(card, note="journaux revenus (LOGF1)")
        del self._episodes[table]
        self._say(f"journaux revenus : {table}" + (f" — carte {card[:8]} fermée" if card else ""))
