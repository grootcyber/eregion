"""The reads' budget, shared by the detection and the dossier (DOS4, #1138; the maintainer's decision of 24/11,
`docs/design/dossier-isolation.md` §7, §12).

**The detection first, always.** One count of the reads the watch made in the last minute, the
detection's and the dossier's together. The detection's — each query of the RulePoller, each query of
`investigate` — is only noted (`note`): never refused, never delayed, whatever the count; it may go past
the budget alone. The dossier takes (`take`) before it reads, and is refused when what the minute already
holds, plus what it asks, passes the budget: it reads only what the detection leaves.

**A prudent value, said, adjustable.** `GLORFINDEL_READ_BUDGET_PER_MIN`, 60 reads a minute by default:
well under the limits Azure documents for one identity (Log Analytics, about 200 queries in 30 s; ARM, a
bucket of 250 reads refilled 25 a second, per subscription) — documentation, not a measure. The figure
is set after the bench measures them (DH14, `docs/design/dossier-isolation.md` §9). 0: the dossier reads
nothing of Azure (its step 0 stays whole); a malformed or negative value: the default. One count for the
APIs of ARM and of Log Analytics together, the prudent side: the bench may split it.

Counted by each process, as the watch runs: a `glorfindel respond` beside it counts its own. The lock is
held only to count, never across a read: the detection never waits behind the dossier.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

DEFAULT_PER_MIN = 60
ENV = "GLORFINDEL_READ_BUDGET_PER_MIN"
WINDOW_S = 60.0
DETECTION, DOSSIER = "detection", "dossier"


def per_min() -> int:
    """GLORFINDEL_READ_BUDGET_PER_MIN (60; 0: the dossier reads nothing); malformed or negative: 60."""
    raw = os.environ.get(ENV, "").strip()
    try:
        n = int(raw) if raw else DEFAULT_PER_MIN
    except ValueError:
        return DEFAULT_PER_MIN
    return n if n >= 0 else DEFAULT_PER_MIN


class ReadBudget:
    """The reads of the last WINDOW_S seconds, by who made them."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._spent: deque[tuple[float, str, int]] = deque()

    def _purge(self, now: float) -> None:
        while self._spent and self._spent[0][0] <= now - WINDOW_S:
            self._spent.popleft()

    def note(self, n: int = 1, who: str = DETECTION) -> None:
        """Reads already made — the detection's: never refused, never waiting on anything but the count."""
        now = self._clock()
        with self._lock:
            self._purge(now)
            self._spent.append((now, who, max(0, int(n))))

    def take(self, n: int, who: str = DOSSIER) -> bool:
        """`n` reads for `who`, if the minute leaves room for them after what is already spent — the
        detection's first. Refused: nothing is counted."""
        now, cap = self._clock(), per_min()
        with self._lock:
            self._purge(now)
            if sum(k for _, _, k in self._spent) + n > cap:
                return False
            self._spent.append((now, who, n))
            return True

    def used(self) -> dict[str, int]:
        """{who: reads} of the last minute."""
        now = self._clock()
        with self._lock:
            self._purge(now)
            out: dict[str, int] = {}
            for _, who, k in self._spent:
                out[who] = out.get(who, 0) + k
            return out


BUDGET = ReadBudget()


def note_detection(n: int = 1) -> None:
    """A read of the detection, noted — never raises: the detection never pays for the count."""
    try:
        BUDGET.note(n, DETECTION)
    except Exception:
        pass
