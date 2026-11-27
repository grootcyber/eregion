"""The reads' budgets, one per service (DOS4, #1138; the maintainer's decision of 24/11, after the review;
`docs/design/dossier-isolation.md` §7, §12).

**Two budgets, each counting its own real calls, a minute at a time:**
- **Log Analytics** (`LOG_ANALYTICS`, `GLORFINDEL_LA_BUDGET_PER_MIN`, 120 by default): the KQL queries of
  the detection — each query of the RulePoller, each query of `investigate`. The detection only notes
  them (`note`): it is never refused nor delayed. Its budget is a threshold: past it, the pressure is
  said in the watch's log, once an episode (`pressure`). 120 is under a third of the 400 queries a
  minute Azure documents for one identity (about 200 in 30 s), and five times what the shipped rules
  query (about 24 a minute) — documentation, not a measure (DH14).
- **ARM** (`ARM`, `GLORFINDEL_ARM_BUDGET_PER_MIN`, 60 by default): the dossier's reads of Azure. The
  dossier takes (`take`) before it reads, and is refused when the minute does not leave room. 60 is
  about eight passes of a dossier a minute, under 5 % of the 25 reads a second ARM documents refilling
  per subscription — a bucket the watch's other readers share (LEV2's door, REC1's recoveries, the
  reassertion), which this lot does not count (a known limit, §7). A value under one pass of a dossier
  (`MINIMUM`, 7 calls) would never let one read: it is raised to it, and said at the start (`notes`).

- **Graph** (`GRAPH`, `GLORFINDEL_GRAPH_BUDGET_PER_MIN`, 30 by default; LOGF2, #1233): the reads of the logs'
  freshness on Microsoft Graph — Entra ID's last event, one `$top=1` per table of Entra every 15 min (two
  tables today). The freshness takes (`take`) before it reads, and is put off a minute when the minute does
  not leave room. 30 is far above what it reads (a few a quarter of an hour) and under the throttling Graph
  documents for its reports — documentation, not a measure. The watch's other reads of Graph (the plan of an
  identity card, its check, IR1a) are not counted here (a known limit).

- **Prometheus** (`PROMETHEUS`, `GLORFINDEL_PROM_BUDGET_PER_MIN`, 30 by default; PIO1, #1258): the PromQL
  queries of an Azure Monitor workspace — `process_write_io`, who writes under Linux
  (`glorfindel/providers/azure/prometheus.py`). The reader takes (`take`) before it queries, and is refused
  (`refusee`, said) when the minute does not leave room. One query a read; 30 is far above what a measure at
  the bench reads, and far under any throttling the documentation names — documentation, not a measure.

**Apart.** The detection never takes from ARM, the dossier never from Log Analytics: neither waits on
the other. 0 on ARM: the dossier reads nothing of Azure (its step 0 stays whole); 0 on Log Analytics: no
threshold, nothing said. A malformed or negative value: the default, said. Counted by each process; the
lock is held to count, never across a read.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

WINDOW_S = 60.0
DETECTION, DOSSIER = "detection", "dossier"
# The calls of one dossier's step 1 (glorfindel/dossier_pass.py, CALLS): below it, an ARM budget that is
# not 0 would never let a dossier read.
MINIMUM = 7


class ReadBudget:
    """The calls of the last WINDOW_S seconds to one service, by who made them; its cap read from `env`."""

    def __init__(self, service: str, env: str, default: int, floor: int = 0, clock=time.monotonic) -> None:
        self.service, self.env, self.default, self.floor = service, env, default, floor
        self._clock = clock
        self._lock = threading.Lock()
        self._spent: deque[tuple[float, str, int]] = deque()
        self._refused_at: float | None = None

    def per_min(self) -> int:
        """The cap: its variable, else the default; malformed or negative: the default; not 0 and under the
        floor: the floor."""
        raw = os.environ.get(self.env, "").strip()
        try:
            n = int(raw) if raw else self.default
        except ValueError:
            return self.default
        if n < 0:
            return self.default
        return max(n, self.floor) if n else 0

    def note(self) -> str:
        """What the start of the watch says of this budget: its cap, and a value set that was not taken."""
        raw = os.environ.get(self.env, "").strip()
        cap = self.per_min()
        if raw and raw != str(cap):
            return (f"{self.env}={raw[:20]} : lu comme {cap} lectures par minute ("
                    + (f"au moins une passe d'un dossier, {self.floor} appels" if raw.isdigit() and int(raw) < self.floor
                       else "valeur illisible ou négative : le défaut") + ")")
        return ""

    def _purge(self, now: float) -> None:
        while self._spent and self._spent[0][0] <= now - WINDOW_S:
            self._spent.popleft()

    def spend(self, n: int = 1, who: str = DETECTION) -> None:
        """Calls already made: counted, never refused, never waiting on anything but the count."""
        now = self._clock()
        with self._lock:
            self._purge(now)
            self._spent.append((now, who, max(0, int(n))))

    def take(self, n: int, who: str = DOSSIER) -> bool:
        """`n` calls for `who`, if the minute leaves room for them. Refused: nothing is counted, and the
        refusal is remembered for `held`."""
        now, cap = self._clock(), self.per_min()
        with self._lock:
            self._purge(now)
            if sum(k for _, _, k in self._spent) + n > cap:
                self._refused_at = now
                return False
            self._spent.append((now, who, n))
            return True

    def used(self) -> dict[str, int]:
        """{who: calls} of the last minute."""
        now = self._clock()
        with self._lock:
            self._purge(now)
            out: dict[str, int] = {}
            for _, who, k in self._spent:
                out[who] = out.get(who, 0) + k
            return out

    def held(self) -> bool:
        """The budget is held: the minute passed its cap (a threshold), or refused a take."""
        cap, now = self.per_min(), self._clock()
        refused = self._refused_at is not None and now - self._refused_at < WINDOW_S
        return refused or (cap > 0 and sum(self.used().values()) >= cap)


LOG_ANALYTICS = ReadBudget("Log Analytics", "GLORFINDEL_LA_BUDGET_PER_MIN", 120)
ARM = ReadBudget("ARM", "GLORFINDEL_ARM_BUDGET_PER_MIN", 60, floor=MINIMUM)
GRAPH = ReadBudget("Graph", "GLORFINDEL_GRAPH_BUDGET_PER_MIN", 30)
PROMETHEUS = ReadBudget("Prometheus", "GLORFINDEL_PROM_BUDGET_PER_MIN", 30)


def note_detection(n: int = 1) -> None:
    """A KQL query of the detection, noted on Log Analytics' budget — never raises, never refused: the
    detection never pays for the count."""
    try:
        LOG_ANALYTICS.spend(n, DETECTION)
    except Exception:
        pass


def notes() -> list[str]:
    """What the start of the watch says of the budgets (a value raised or not read)."""
    return [n for n in (LOG_ANALYTICS.note(), ARM.note(), GRAPH.note(), PROMETHEUS.note()) if n]


class Pressure:
    """Each budget held said once an episode: an episode starts when it is held, ends when it is not."""

    def __init__(self, budgets=None) -> None:
        self._budgets = budgets
        self._held: set[str] = set()

    def lines(self) -> list[str]:
        out = []
        for b in self._budgets or (LOG_ANALYTICS, ARM, GRAPH, PROMETHEUS):
            if b.held():
                if b.service not in self._held:
                    self._held.add(b.service)
                    used = b.used()
                    out.append(f"budget de lectures {b.service} tenu : {sum(used.values())} appel(s) dans la "
                               f"minute ({', '.join(f'{k} {v}' for k, v in sorted(used.items())) or 'aucun'}) sur "
                               f"{b.per_min()} ({b.env}) — DH14")
            else:
                self._held.discard(b.service)
        return out
