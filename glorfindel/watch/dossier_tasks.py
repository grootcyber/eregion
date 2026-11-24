"""The dossiers' tasks of the watch's housekeeping — WCH2 (#1150): out of glorfindel/watch/housekeeping.py,
nothing changed in what each does, says, or when.

DOS3 (#1043): the dossiers kept 30 days after the lift (Q7), the pass local and once an hour. DOS4 (#1138):
the dossiers' reads of Azure, in a thread of their own, on their own ARM budget (glorfindel/dossier_pass.py,
glorfindel/read_budget.py); the budgets said at the start, each held once an episode after. A mixin of
`Housekeeping`: it reads its console, its lock, its dry-run and its connector.
"""
from __future__ import annotations

import time

from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch.passes import Solo


class DossierTasks:
    """The dossiers' part of `Housekeeping`: their retention, their reads of Azure, their budgets."""

    def _init_dossier(self) -> None:
        # DOS3 (#1043): the dossiers kept 30 days after the lift (Q7), the pass local and once an hour.
        self._last_dossier_retention = 0.0
        # DOS4 (#1138): the dossiers' reads of Azure, their own thread, on their own ARM budget
        # (glorfindel/dossier_pass.py, glorfindel/read_budget.py); the budgets said (`_say_budgets`).
        self._dossier_thread = Solo("dossier")
        self._pressure = self._say_budgets()

    def _dossier_retention(self) -> None:
        """DOS3 (#1043): a dossier's VM lifted, its clock starts; 30 days later, its file goes (Q7) —
        local files only, once every RETENTION_EVERY_S (glorfindel/dossier.py, ``retention_pass``)."""
        from glorfindel import dossier
        if time.time() - self._last_dossier_retention < dossier.RETENTION_EVERY_S:
            return
        self._last_dossier_retention = time.time()
        removed = dossier.retention_pass()
        if removed:
            with self._output_lock:
                self.console.print(f"[dim]{removed} dossier(s) retiré(s) : 30 jours après la levée (DOS3)[/dim]")

    def _say_budgets(self):
        """DOS4: a budget's value raised or not read, said at the start; each held, once an episode after."""
        from glorfindel import read_budget
        for line in read_budget.notes():
            self.console.print(f"[yellow]{_outside(line)}[/yellow]")
        return read_budget.Pressure()

    def _dossier_reads(self) -> None:
        """DOS4 (#1138): the reads of Azure of each dossier, after its step 0 — never in dry-run; a cheap
        local look first: no thread when no dossier is on disk. Each budget held said once an episode."""
        from glorfindel import dossier
        for line in self._pressure.lines():
            with self._output_lock:
                self.console.print(f"[yellow]{_outside(line)}[/yellow]")
        if self.dry_run or self._dossier_thread.busy() or not dossier.DOSSIER_DIR.is_dir():
            return
        self._dossier_thread.start(self._dossier_run)

    def _dossier_run(self) -> None:
        from glorfindel import dossier_pass
        try:
            report = dossier_pass.reads_pass(self.ttl_connector)
        except Exception as exc:
            _say_failure(self.console, "watch: lectures du dossier en erreur", exc, self._output_lock)
            return
        for r in report:
            if r["issue"] != "lu" or r["etape"] == "1":
                with self._output_lock:
                    self.console.print(f"[dim]dossier {_outside(r['vm'])} : étape {r['etape']} → {r['issue']}[/dim]")
