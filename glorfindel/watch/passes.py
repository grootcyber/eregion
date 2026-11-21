"""The watch's passes over Azure, each in a thread of its own — WCH1 (#1019): out of glorfindel/cli.py,
nothing changed in what they do or say.

`_watch_reassert_pass`, `_watch_recovery_pass`, `_watch_door_pass`: one pass each, never raising, what it
reads said once until it changes (the `seen`/`said` the watch keeps between passes). `Solo`: one thread of
a kind at a time. `interval_s`: a pass's interval, read from its variable.
"""
from __future__ import annotations

import contextlib
import os
import threading

from rich.markup import escape as _esc_markup


def interval_s(name: str) -> float:
    """A pass's interval in seconds, read from its variable (GLORFINDEL_REASSERT_INTERVAL_S,
    GLORFINDEL_RECOVERY_INTERVAL_S): 60 when unset, and when it does not read as a number — never a
    watch stopped on it."""
    try:
        return float(os.environ.get(name, "60"))
    except ValueError:
        return 60.0


class Solo:
    """One thread of a kind at a time (its name): a pass still running is never started again."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._thread: threading.Thread | None = None

    def busy(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    def start(self, target) -> None:
        self._thread = threading.Thread(target=target, daemon=True, name=self.name)
        self._thread.start()


def _watch_reassert_pass(console, connector, mode_override=None, lock=None, seen: dict | None = None) -> list[dict]:
    """One reassertion pass of the watch (its own thread, every
    GLORFINDEL_REASSERT_INTERVAL_S): the recorded isolations and blocks, and our
    quarantine NSGs whatever the local state says — a state lost is what that check is
    for (I1F, #226: the pass stopped before any Azure call when nothing was recorded).
    Never raises. An unreadable configuration is said once until it reads again (`seen`
    is the watch's memory between passes), not every minute."""
    from glorfindel.reassert import reassert_pass
    lock = lock if lock is not None else contextlib.nullcontext()
    seen = seen if seen is not None else {}
    try:
        from glorfindel.config import load_glorfindel_config as _lgc
        autonomy = _lgc().autonomy              # fresh: a console mode change applies
        if mode_override:
            autonomy.default = mode_override    # --mode stays pinned, as in decide
        seen.pop("config_error", None)
    except Exception as exc:
        # Unreadable config: the mode loaded when the watch started may be stale —
        # alert only, never act on it (seventh review, U4).
        autonomy = None
        if seen.get("config_error") != str(exc):
            seen["config_error"] = str(exc)
            with lock:
                console.print(f"[yellow]reassert: config illisible, alertes seulement ({exc})[/yellow]")
    report: list[dict] = []
    try:
        report = reassert_pass(connector, autonomy)
        for r in report:
            target = r["vm"] + (f" {r['ip']}" if r.get("ip") else "")
            with lock:
                console.print(f"[yellow]reassert {r['kind']} {target} → {r['outcome']}[/yellow]")
    except Exception as exc:
        with lock:
            console.print(f"[red]reassert pass failed:[/red] {exc}")
    return report


def _watch_recovery_pass(console, connector, emit, lock=None, said: dict | None = None) -> list[dict]:
    """One pass of the watch over the recoveries it can read on Azure (REC1, #668; its own
    thread, every GLORFINDEL_RECOVERY_INTERVAL_S): a restore of an isolated VM proven there
    hands its recovery_complete to `emit` (the VM's queue). Never raises. What it can't read is
    said once until it changes (`said`, the watch's memory between passes)."""
    from glorfindel.recovery_watch import recovery_pass
    lock = lock if lock is not None else contextlib.nullcontext()
    said = said if said is not None else {}
    report: list[dict] = []
    try:
        report = recovery_pass(connector, emit)
    except Exception as exc:
        with lock:
            console.print(f"[red]recovery pass failed:[/red] {_esc_markup(str(exc))}")
        return report
    for r in report:
        if r["outcome"] == "wait":
            continue
        if r["outcome"] == "unreadable":
            if said.get(r["vm"]) == r["detail"]:
                continue
            said[r["vm"]] = r["detail"]
        with lock:
            console.print(f"[cyan]reprise {_esc_markup(r['vm'])} {_esc_markup(r['job'])} → "
                          f"{r['outcome']}[/cyan] {_esc_markup(r['detail'])}")
    return report


def _watch_door_pass(console, connector, lock=None, said: dict | None = None) -> list[dict]:
    """One pass of the door's facts (LEV2, #690): who acted on each isolated VM, and their rights,
    written for its isolation card — information only, nothing lifts or holds. Never raises; what
    it read is said once until it changes (`said`)."""
    from glorfindel.door_facts import facts_pass
    lock = lock if lock is not None else contextlib.nullcontext()
    said = said if said is not None else {}
    try:
        report = facts_pass(connector)
    except Exception as exc:
        with lock:
            console.print(f"[red]door facts pass failed:[/red] {_esc_markup(str(exc))}")
        return []
    for r in report:
        if said.get(r["vm"]) == (r["verdict"], r["actors"]):
            continue
        said[r["vm"]] = (r["verdict"], r["actors"])
        with lock:
            console.print(f"[cyan]porte {_esc_markup(r['vm'])} → {r['verdict']} "
                          f"({r['actors']} acteur(s), pour information)[/cyan]")
    return report
