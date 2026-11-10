"""Run Command's long operation: waited a first time, then its status read on Azure (DRN1, #677).

Measured on the bench, 09/11: under the quarantine, the session drain took 302 s on Azure
(Started, Accepted, Succeeded) and the console's neutralization 152 s; out of it, a Run Command
took 11 to 61 s. The watch waited 300 s, then read the poller's result: `LROPoller.result(timeout)`
returns at its deadline without raising, with what the last poll said — no output —, and the
drain read « sortie de Run Command illisible »: the isolation unverified, the cut done 2 s later.

An operation not done at the first wait is now said pending, never read. The drain's poller is
kept in this process (the watch, which alone runs isolations: the agent, the action queue, the
reassertion) and its status read again by the reassertion's pass (glorfindel/drain_watch.py)
until it ends, or its deadline (drain_watch.DRAIN_DEADLINE_S). The first wait stays 300 s: the VM's
worker is not held longer than before. A restart of the watch loses the poller: said, never
read as a cut. The status is the poller's — it keeps polling Azure in its own thread.
"""
from __future__ import annotations

import re
import threading
import time

# What the VM's worker waits for the drain (as before DRN1): past it, the drain is pending.
DRAIN_FIRST_WAIT_S = 300.0
# What the restore waits for its harmless command (as before DRN1): 152 s measured under it.
NEUTRALIZE_WAIT_S = 600.0


def wait(poller, timeout_s: float):
    """(done, result): the operation waited up to `timeout_s`. Not done: (False, None) — what
    `result(timeout)` returned then is the last poll, never an output. Done: its result — read
    again when it ended just after the wait (the first read was then the last poll's); a failed
    operation raises. Without a wait (a pass that reads it again), done is asked first: a result
    read before would be the last poll's if the operation ended in between."""
    if not timeout_s:
        if not poller.done():
            return False, None
        return True, poller.result(timeout=0)
    start = time.monotonic()
    result = poller.result(timeout=timeout_s)
    if not poller.done():
        return False, None
    if timeout_s and time.monotonic() - start >= timeout_s:
        result = poller.result(timeout=0)
    return True, result


def azure_status(poller) -> str:
    """The operation's status as the poller last read it on Azure (InProgress, Succeeded…);
    "" when it can't say."""
    try:
        status = poller.status()
    except Exception:
        return ""
    return status if isinstance(status, str) else ""


def output(result) -> str:
    """What the Run Command printed: its messages, joined."""
    return " ".join(str(getattr(v, "message", "") or "") for v in (getattr(result, "value", None) or []))


def drain_outcome(result) -> dict:
    """The drain's outcome, from its Run Command's output (it counts what is left, loudly)."""
    text = output(result)
    if "glorfindel-drain-remaining=error" in text:
        return {"status": "failed", "error": "sessions restantes non comptées (`ss` absent ou en erreur)"}
    m = re.search(r"glorfindel-drain-remaining=(\d+)", text)
    if m is None:
        return {"status": "failed", "error": "sortie de Run Command illisible"}
    remaining = int(m.group(1))
    if remaining:
        return {"status": "partial", "remaining": remaining,
                "error": f"{remaining} connexion(s) encore établie(s) après ss -K"}
    return {"status": "drained"}


# The drains still running on Azure, by VM id (lowercase): their poller, when each was asked.
_FOLLOWED: dict[str, dict] = {}
_LOCK = threading.Lock()


def pending(resource_id: str, poller, asked: float, waited_s: float) -> dict:
    """The drain not done at its first wait: its poller kept, the outcome says so."""
    with _LOCK:
        _FOLLOWED[resource_id.rstrip("/").lower()] = {"poller": poller, "asked": asked}
    from datetime import datetime, timezone
    status = azure_status(poller)
    return {"status": "pending", "waited_s": round(waited_s),
            "asked_at": datetime.fromtimestamp(asked, timezone.utc).isoformat(),
            **({"azure_status": status} if status else {}),
            "note": (f"coupure en attente : Run Command toujours en cours sur Azure après "
                     f"{round(waited_s)} s ({status or 'statut non lu'}) — suivie, son statut relu "
                     "à chaque passe de la réaffirmation")}


class DrainFollowMixin:
    """The drain's status read again on Azure after its first wait (part of AzureConnector)."""

    def follow_drain(self, resource_id: str) -> dict | None:
        """The drain of `resource_id` this process still follows: its outcome once it ended
        (then forgotten), `{"status": "pending", …}` while it runs; None when this process
        follows none (the watch restarted since, or no drain was pending)."""
        key = resource_id.rstrip("/").lower()
        with _LOCK:
            entry = _FOLLOWED.get(key)
        if entry is None:
            return None
        poller = entry["poller"]
        elapsed = round(time.time() - entry["asked"])
        try:
            done, result = wait(poller, 0)
        except Exception as e:
            # Accepted, then failed on Azure: not a refusal (that comes at the request).
            from glorfindel.response.policy import _ERR_MAX, _first_line
            self.drop_drain(resource_id)
            return {"status": "failed", "after_s": elapsed, "azure_status": azure_status(poller) or "Failed",
                    "error": f"Run Command en échec sur Azure après {elapsed} s : {_first_line(e)}"[:_ERR_MAX]}
        if not done:
            status = azure_status(poller)
            return {"status": "pending", "after_s": elapsed, **({"azure_status": status} if status else {})}
        self.drop_drain(resource_id)
        return {**drain_outcome(result), "after_s": elapsed}

    def drop_drain(self, resource_id: str) -> None:
        """Stop following a drain (ended, given up, its VM released)."""
        with _LOCK:
            _FOLLOWED.pop(resource_id.rstrip("/").lower(), None)
