"""The logs' freshness in the watch's housekeeping — LOGF1 (#1183): whether the workspace's logs still
arrive, for each table its rules read (glorfindel/log_freshness.py).

Every minute, a cheap look in memory: a table is due every 15 min (a minute after the budget left it
out). Then a pass in a thread of its own, one at a time (`Solo`): a workspace that does not answer never
holds the loop. Never in dry-run (no Azure). A mixin of `Housekeeping`: it reads its console, its lock and
its dry-run; `follow_logs` hands it the rules the watch polls, once they are loaded.
"""
from __future__ import annotations

from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch.passes import Solo


class LogTasks:
    """The logs' freshness part of `Housekeeping`."""

    def _init_logs(self) -> None:
        self._freshness = None
        self._freshness_thread = Solo("log-freshness")

    def follow_logs(self, rules) -> None:
        """The rules the watch polls (glorfindel/watch/rules.py): their tables followed from now on. None
        (every rule removed): nothing read, but the episodes of the file closed with their card (LOGF1b)."""
        if self.dry_run:
            return
        try:
            from glorfindel.log_freshness import Freshness
            self._freshness = Freshness(rules, say=self._say_logs)
        except Exception as exc:      # said, never the watch stopped: its tiles keep their colour
            _say_failure(self.console, "watch: logs' freshness not followed", exc, self._output_lock)

    def _say_logs(self, line: str) -> None:
        with self._output_lock:
            self.console.print(f"[yellow]{_outside(line)}[/yellow]")

    def _log_freshness(self) -> None:
        """LOGF1: the tables due read in their own thread (or a table no longer followed closed) — nothing
        to do, nothing started."""
        f = self._freshness
        if self.dry_run or f is None or self._freshness_thread.busy() or not f.has_work():
            return
        self._freshness_thread.start(self._freshness_run)

    def _freshness_run(self) -> None:
        try:
            self._freshness.pass_once()
        except Exception as exc:
            _say_failure(self.console, "watch: logs' freshness failed", exc, self._output_lock)
