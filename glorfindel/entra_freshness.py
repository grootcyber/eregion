"""LOGF2 (#1233): the silence of a table of Entra ID, judged by Entra — by Graph —; a fallback to 7 days
without the right.

**Why.** In 0.6.9, `logs_silent` (LOGF1, glorfindel/log_freshness.py) opened on AuditLogs after 26 h
without a log, on the threshold of 24 h: a false alarm. AuditLogs receives a log only when the directory
changes, and the bench's tenant is calm (44 events in 7 days, measured by the maintainer, its diagnostic
setting sending them). The maintainer's decision of 26/11, on a mockup: « Graph, and the fallback to 7
days ».

**The rule**, for a table of the identity plane that has an equivalent on Graph v1.0 (`judged_tables`:
AuditLogs, SigninLogs), every 15 min with its freshness:
  - **Entra read** (`judged: "entra"`): Graph is asked for Entra's last event **older than the ingestion's
    delay** (`INGEST_DELAY_S`, 15 min — a hypothesis, to measure on the bench): `$filter=<date> le <now − 15
    min>`, `$top=1`. The card opens only when that event is more recent than the last log the workspace
    received — the event happened, had time to arrive, and did not. It closes only when the last log
    received catches up with it: an event of the last minutes never closes it, a tenant whose events come
    every few minutes never hides a cut (LOGF2's review). With no log in the window read, the window's start
    stands for the last log: an event older than the window says nothing. Entra with no such event (an empty
    list): never a card. A calm tenant is never an alert.
  - **Entra not read** (`judged: "fallback"`): a 403 (`AuditLog.Read.All` missing), Graph unreadable, a date
    of Graph past the cutoff (glorfindel/providers/azure/entra_last.py), a read the Graph budget put off
    before it was ever made, or put off for more than `STALE_S` (twice `EVERY_S`) — the threshold of the
    table becomes `FALLBACK_H` (7 days), said on the tile (« Graph unread: … — threshold 7 days »), never
    « nothing ». A card opened by the comparison stays open on a fallback until the workspace holds a log as
    recent as the event that opened it.
  A table of Entra with no equivalent on Graph v1.0 (the service principals', the non-interactive, the
  managed identities' sign-ins: Graph's beta only) is not judged here: it keeps LOGF1's threshold, 24 h by
  default (the maintainer's decision of 26/11). AzureActivity and the data plane keep LOGF1's threshold too;
  AzureActivity by the Activity Log's API is a later lot.

**One tenant**: Graph is read with the watch's identity, in its own tenant. A workspace that receives the
logs of another tenant (a diagnostic setting of another tenant, Lighthouse, TEN1) would be compared with the
wrong tenant: a known limit, not checked here (docs/design/modele-de-menace.md).

**The window** of a table of Entra: twice the fallback (14 days), whatever is judged — the comparison
needs the last log received even when the tenant was calm for days.

**The budget**: Graph's (`read_budget.GRAPH`, DOS4's model): one `take` before each read; refused, the
read is put off a minute (`RETRY_S`), its last value kept — for `STALE_S` at most, then the fallback, said.

**Written** (glorfindel/log_freshness.py, `~/.glorfindel/log_freshness.json`): the reads of Graph, per
table (`graph`), kept across a restart; and on each table of the console's field: `judged`, `silent` (the
watch's verdict, which the tile follows), `entra_last` (judged by Entra) or `graph_error` and
`threshold_hours` (the fallback).

Nothing here reaches the model.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

INGEST_DELAY_S = 900.0             # Entra ID → the workspace: an event not received after 15 min is lost
                                   # (a hypothesis: to measure on the bench)
FALLBACK_H = 168.0                 # without Graph, a table of Entra is silent after 7 days
EVERY_S = 900.0                    # each table read again on Graph every 15 min, with its freshness
RETRY_S = 60.0                     # put off by Graph's budget: read again a minute later
STALE_S = 2 * EVERY_S              # put off longer than this: the fallback, said
WHO = "freshness"
JUDGED = ("entra", "fallback")
DEFERRED = "not read yet: the watch's Graph budget is held (LOGF2), read again the next minute"
STALE = "not read for 30 min: the watch's Graph budget is held (LOGF2)"


def judged_tables(planes: dict) -> set[str]:
    """The tables judged by Entra: of the identity plane, with an equivalent on Graph v1.0 — the others
    (Graph's beta only) keep LOGF1's threshold."""
    from glorfindel.providers.azure.entra_last import SOURCES
    return {t for t, plane in planes.items() if plane == "identity" and t in SOURCES}


def _epoch(iso) -> float | None:
    if not isinstance(iso, str) or not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def verdict(entry: dict, graph: dict | None, now: float, window_h: float) -> dict:
    """A table of Entra, judged: {"judged", "silent", "entra_last" | ("graph_error", "threshold_hours")}.
    `entry`: the table as the workspace answered ({"last", "error"}); `graph`: its read on Graph, or None.
    A read of the workspace that failed is never silent: it is unknown."""
    failed = bool(entry.get("error"))
    seen = _epoch(entry.get("last"))
    if graph is None or graph.get("error"):
        why = (graph or {}).get("error") or DEFERRED
        silent = not failed and (seen is None or now - seen > FALLBACK_H * 3600)
        return {"judged": "fallback", "silent": silent, "graph_error": why, "threshold_hours": FALLBACK_H}
    event = _epoch(graph.get("last"))
    floor = seen if seen is not None else now - window_h * 3600
    # `event` is Entra's last event older than the ingestion's delay (the read's cutoff): it should be there.
    silent = not failed and event is not None and event > floor
    return {"judged": "entra", "silent": silent, "entra_last": graph.get("last")}


def holds(episode: dict, entry: dict, judged: dict) -> bool:
    """An episode opened by the comparison, on a fallback since: kept open until the workspace holds a
    log as recent as the event that opened it — a 403 never closes a card on « logs back »."""
    opened_on = _epoch(episode.get("entra_last"))
    if judged.get("judged") != "fallback" or opened_on is None:
        return False
    seen = _epoch(entry.get("last"))
    return seen is None or seen < opened_on


def field_ok(e: dict) -> bool:
    """LOGF2's keys of a table in the console's field, read strictly — each absent from a file before
    LOGF2 (or of a table not judged by Entra)."""
    def iso_or_none(k):
        return k not in e or e[k] is None or _epoch(e[k]) is not None
    hours = e.get("threshold_hours")
    return (("judged" not in e or e["judged"] in JUDGED)
            and ("silent" not in e or isinstance(e["silent"], bool))
            and iso_or_none("entra_last")
            and ("graph_error" not in e or e["graph_error"] is None or isinstance(e["graph_error"], str))
            and ("threshold_hours" not in e or (not isinstance(hours, bool) and isinstance(hours, (int, float))
                                                and math.isfinite(hours))))


FIELD_KEYS = ("judged", "silent", "entra_last", "graph_error", "threshold_hours")


class EntraReads:
    """Entra's last event per table, read on Graph every EVERY_S (a read put off by the budget: RETRY_S
    later), kept between passes and across a restart (`saved`, the file's `graph`)."""

    def __init__(self, tables, reader, budget=None, saved: dict | None = None) -> None:
        from glorfindel import read_budget
        self.tables = sorted(set(tables))
        self._reader = reader
        self._budget = budget or read_budget.GRAPH
        self.reads = {t: r for t, r in (saved or {}).items() if t in self.tables and isinstance(r, dict)}

    def due(self, now: float) -> list[str]:
        out = []
        for table in self.tables:
            r = self.reads.get(table) or {}
            read, deferred = _epoch(r.get("read_at")), _epoch(r.get("deferred_at"))
            if (deferred is not None and now - deferred >= RETRY_S) \
                    or (deferred is None and (read is None or now - read >= EVERY_S)):
                out.append(table)
        return out

    def _room(self) -> bool:
        cap = self._budget.per_min()
        if cap <= 0:
            self._budget.spend(1, WHO)
            return True
        return self._budget.take(1, WHO)

    def read_due(self, now: float) -> None:
        from glorfindel.providers.azure import entra_last
        for table in self.due(now):
            if not self._room():
                prev = self.reads.get(table) or {"read_at": None, "last": None, "error": DEFERRED}
                self.reads[table] = {**prev, "deferred_at": _stamp(now),
                                     "deferred_since": prev.get("deferred_since") or _stamp(now)}
                continue
            self.reads[table] = {"read_at": _stamp(now),
                                 **entra_last.last_event(self._reader, table, now - INGEST_DELAY_S)}

    def of(self, table: str, now: float) -> dict | None:
        """The read of `table` the verdict takes: its last, None (never read) — or, put off by the budget
        for more than STALE_S, an error: the fallback, said."""
        r = self.reads.get(table)
        if not r:
            return None
        since = _epoch(r.get("deferred_since"))
        if since is not None and now - since > STALE_S:
            return {"last": None, "error": STALE}
        return {"last": r.get("last"), "error": r.get("error")}
