"""The loop's reader (ENQ5a, #1162; `docs/design/enquete-raisonnee.md` §4, §5.1): each read of the
catalogue run on its window **anchored on the signal's hour T**, by the code. **At the harness and the
capture only** (`scripts/capture_enquete.py`, the maintainer's hand): no module of the product imports
it; ENQ5b brings it to the watch, behind `GLORFINDEL_ENQUIRY`.

**The window comes from the code, never from the model** (§5.1): `catalog.window(read, T)`, [T − lookback,
T + ahead], its end never past the moment it runs (`root_commands` and `disk_write_after_escalation` read
five minutes past T: what follows the escalation). A KQL read of `investigate` keeps its text, to the byte,
for `investigate` (ENQ2); here its one
`TimeGenerated > ago(<lookback>)` becomes `TimeGenerated between (datetime(T − lookback) .. datetime(T))`
(`texte`) — a query with no such clause, or more than one, or whose `ago()` is not its `lookback`, is
refused (`NonAncrable`), never run on the read's own hour. A read that writes its window
(`{debut}`, `{fin}`: `perf_minute_series`) gets the same bounds. The query's own timespan is that window,
widened by a minute each side and by what the horizon reads past its end — never the API's default of
the last hours, which reads nothing of an episode captured a day later.

**What it returns**, as the loop reads it: the rows; `catalog.Lu` for `perf_minute_series` (its rows, and
`Horizon`: how far the table has ingested this VM's samples, EH10); None when the read failed (the query
raised, the adapter said `echec` or `refusee`). A read of ARM (`kind="arm"`) goes to the provider's
adapter (`connector.enquiry_reads`: the vault's reads of DOS4, the same code), with the vault the code
gave — never a value of the model's.

**The budgets of DOS4** (`glorfindel/read_budget.py`) are the watch's, so ENQ5b's (`compter`, the watch's
enquiry, `production.py`): each KQL query of this reader is noted on `LOG_ANALYTICS` (the detection's path —
never refused nor delayed, like `investigate`), each read of ARM takes from `ARM` before it runs — refused,
it is `refusee` (a `catalog.Reading` returned, which the loop keeps as is), a gap when the read is
obligatory —, and the calls it made past the first are counted once it returned. The harness and the
capture count nothing: they are not the watch.

**`heartbeat_gap`, corrected for the loop** (ENQ5b, §9.7): the loop runs its anchored text
(`catalog.ANCREES`), which writes its window and the end its table has delivered — never the text
`investigate` runs in ``fixed``, which stays origin/main's, to the byte.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Callable

from glorfindel import kql, read_budget
from glorfindel.enquiry import catalog

_AGO = re.compile(r"TimeGenerated > ago\((\d+)([mh])\)")
MARGE = timedelta(minutes=1)
HORIZON_APRES = timedelta(minutes=10)    # the horizon of perf_minute_series reads this far past its window
SERIE = "perf_minute_series"
ARM_REFUSE = "le budget de lectures ARM de la minute est tenu (GLORFINDEL_ARM_BUDGET_PER_MIN) : rien n'a été lu"


class NonAncrable(ValueError):
    """A KQL read whose window cannot be anchored on the signal: never run on the read's own hour."""


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _datetime(t: datetime) -> str:
    return f"datetime({_iso(t)})"


def bornes(read: catalog.Read, at: datetime, now: datetime | None = None) -> tuple[datetime, datetime]:
    """The window the query reads: `catalog.window(read, at)`, its end never past `now`."""
    debut, fin = catalog.window(read, at)
    return debut, min(fin, now) if now is not None else fin


def texte(read: catalog.Read, valeurs: dict, at: datetime, now: datetime | None = None) -> str:
    """The KQL of `read`, its values as literals (`kql.literal`, after their check), its window anchored
    on `at`, its end at most `now`. Raises NonAncrable when the window cannot be anchored."""
    debut, fin = bornes(read, at, now)
    lits = {p: kql.literal(valeurs[p]) for p in read.params}
    query = catalog.ANCREES.get(read.id) or read.query     # ENQ5b: the loop's own text, when the read has one
    if "{debut}" in query or "{fin}" in query:
        marks = {"latence": f"{int(read.latency_s)}s"} if "{latence}" in query else {}
        return query.format(**lits, debut=_datetime(debut), fin=_datetime(fin), **marks)
    found = _AGO.findall(read.query)
    if len(found) != 1:
        raise NonAncrable(f"{read.id} : {len(found)} clause(s) ago(), une seule s'ancre")
    n, unit = found[0]
    if timedelta(**{"minutes" if unit == "m" else "hours": int(n)}) != read.lookback:
        raise NonAncrable(f"{read.id} : son ago() n'est pas son lookback")
    anchored = _AGO.sub(f"TimeGenerated between ({_datetime(debut)} .. {_datetime(fin)})", read.query)
    return anchored.format(**lits)


def timespan(read: catalog.Read, at: datetime, now: datetime | None = None) -> tuple[datetime, datetime]:
    """The query's timespan: its window, a minute wider each side, and what its horizon reads past it."""
    debut, fin = bornes(read, at, now)
    return debut - MARGE, fin + MARGE + (HORIZON_APRES if read.id == SERIE else timedelta(0))


def serie(rows: list) -> catalog.Lu:
    """`perf_minute_series`' answer: its minutes, and its `Horizon` row — how far the table ingested; a
    row there but null is « nothing ingested » (`dit`), never « not said »."""
    minutes, horizon, dit = [], None, False
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and row.get("Minute") in (None, ""):
            dit = True
            horizon = catalog._when(row.get("Horizon")) or horizon
        else:
            minutes.append(row)
    return catalog.Lu(minutes, horizon, dit)


class Lecteur:
    """`lecteur(read, valeurs)` for the loop, anchored on `at`. `kql(query, timespan)` runs a query (its
    rows; it raises when it fails); `arm` is the provider's connector (`enquiry_reads`), given the vault
    the code checked (`valeurs["vault"]`), by its name and its group. Each call is noted in `faites`."""

    def __init__(self, at: datetime, *, kql: Callable | None = None, arm=None,
                 now: Callable[[], datetime] | None = None, compter: bool = False):
        self.at, self.kql, self.arm, self.compter = at, kql, arm, compter
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.faites: list[tuple[str, str]] = []

    def __call__(self, read: catalog.Read, valeurs: dict):
        if read.kind == "kql":
            return self._kql(read, valeurs)
        if read.kind == "arm":
            return self._arm(read, valeurs)
        return None                                       # a kind it does not know: failed, never empty

    def _kql(self, read: catalog.Read, valeurs: dict):
        if self.kql is None:
            return None
        now = self.now()
        try:
            query = texte(read, valeurs, self.at, now)
        except NonAncrable:
            return None
        self.faites.append((read.id, query))
        if self.compter:                     # the watch's: noted on Log Analytics, never refused nor delayed
            read_budget.note_detection()
        try:
            rows = self.kql(query.strip(), timespan(read, self.at, now))
        except Exception:
            return None
        if not isinstance(rows, list):
            return None
        return serie(rows) if read.id == SERIE else rows

    def _arm(self, read: catalog.Read, valeurs: dict):
        if self.arm is None:
            return None
        if self.compter and not read_budget.ARM.take(1, read_budget.ENQUETE):
            return catalog.Reading(read.id, catalog.REFUSEE, why=ARM_REFUSE)      # never run: refused, said
        self.faites.append((read.id, read.query))
        parts = str(valeurs.get("vault") or "").split("/")
        try:
            readings, calls = self.arm.enquiry_reads(valeurs["vm"], self.at, vault=parts[-1], vault_rg=parts[4],
                                                     only=[read.id], now=self.now())
        except Exception:
            return None
        if self.compter and isinstance(calls, int) and calls > 1:
            read_budget.ARM.spend(calls - 1, read_budget.ENQUETE)         # its calls past the one taken
        lu = readings.get(read.id) if isinstance(readings, dict) else None
        if lu is None or lu.etat in (catalog.ECHEC, catalog.REFUSEE, catalog.NON_PERMISE):
            return None
        return list(lu.rows) if lu.etat == catalog.LIGNES else []
