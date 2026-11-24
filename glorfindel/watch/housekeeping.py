"""What the watch does beside reading runs/ — WCH1 (#1019): out of glorfindel/cli.py's `watch()`, nothing
changed in what each task does, says, or when.

Every minute (30 polls at 2 s): the recoveries, the door's facts, the dossiers' retention (DOS3, once an
hour), the notices the bot did not post, the TTL, the jobs, the reassertion, the exercise windows, the
proposed verdicts, the drill of the week; every 5 polls, the identity checks the console asked for. A
task that reaches Azure, Graph or a webhook runs in a thread of its own, one at a time (`Solo`): none
ever holds the loop.
"""
from __future__ import annotations

import time

from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch import passes
from glorfindel.watch.passes import Solo, interval_s


class Housekeeping:
    """The watch's periodic tasks and the memory they keep between passes. `emit` hands a
    recovery_complete to its VM's queue; `say_channel` says a line of the runs/ channel."""

    def __init__(self, console, lock, *, dry_run: bool, mode_override, runs_dir, ttl_h: float,
                 emit, say_channel) -> None:
        from glorfindel.actions import AzureConnector
        self.console = console
        self._output_lock = lock
        self.dry_run = dry_run
        self.mode_override = mode_override
        self.runs_dir = runs_dir
        self.ttl_h = ttl_h
        self._emit_recovery = emit
        self._say_channel = say_channel
        self.ttl_connector = AzureConnector(dry_run=dry_run)
        # Reassert isolations/blocks whose rules vanished from Azure (terraform apply on an
        # NSG with inline rules, removal in the portal): re-apply once, then alert only.
        self._reassert_every_s = interval_s("GLORFINDEL_REASSERT_INTERVAL_S")
        self._last_reassert = time.time()
        self._reassert_thread = Solo("reassert")
        self._reassert_seen: dict = {}
        # IR1a: the console's « Verify » on an identity card — the watch reads Graph, read only, and
        # notes « held », « not held » or « unreadable » on the card's thread. In its own thread, one
        # at a time: a Graph that does not answer never stalls the loop.
        self._identity_thread = Solo("identity-checks")
        # REC1 (#668): the recovery of a VM this watch isolated, read on Azure — a restore run from
        # another host (Imladris never restores, SEC17) proven there hands the VM's queue its own
        # recovery_complete. In its own thread, one pass at a time.
        self._recovery_every_s = interval_s("GLORFINDEL_RECOVERY_INTERVAL_S")
        self._last_recovery = 0.0
        self._recovery_thread = Solo("recoveries")
        self._recovery_said: dict = {}
        # LEV2 (#690): the door's facts of each isolated VM — who acted on it by the control plane,
        # and whether they keep their rights — read on Azure and written for its isolation card, for
        # information only: nothing here lifts or holds. Its own thread, one pass at a time; how often
        # each VM is read again is the pass's (GLORFINDEL_DOOR_FACTS_INTERVAL_S, 900 s; 0: off).
        self._door_thread = Solo("door-facts")
        self._door_said: dict = {}
        # DOS3 (#1043): the dossiers kept 30 days after the lift (Q7), the pass local and once an hour.
        self._last_dossier_retention = 0.0
        # DOS4 (#1138): the dossiers' reads of Azure, their own thread, on their own ARM budget
        # (glorfindel/dossier_pass.py, glorfindel/read_budget.py); the budgets said (`_say_budgets`).
        self._dossier_thread = Solo("dossier")
        self._pressure = self._say_budgets()
        self._relay_thread = Solo("relay-notices")
        # SEC2c (#1107): the blocks of the exposed zone lifted at 24 h, or once another VM holds the address —
        # read from their entries (a restart keeps the deadline), lifted in a thread of their own.
        self._expiry_thread = Solo("exposed-expiry")
        # CFG3 (#1139): the view « Relaxed », computed in a thread of its own; its lines said once, at the start.
        self._relaxed_thread = Solo("relaxed-view")
        self._relaxed_said = False

    # ── TTL and jobs: local, cheap ─────────────────────────────────────────────────────────────

    def _check_ttl(self) -> None:
        """Past the TTL an isolation is escalated, never released (fourth review, Q1)."""
        if self.dry_run:
            return
        from glorfindel.reassert import ttl_alerts
        for a in ttl_alerts(self.ttl_h):
            with self._output_lock:
                self.console.print(f"[yellow]⚠ TTL exceeded[/yellow] — {_outside(a['vm'])} isolated {a['age_h']:.1f}h "
                                   f"(limit {self.ttl_h}h): escalated, NOT released")

    def _reconcile_jobs(self) -> None:
        """Move InProgress snapshot/restore jobs to a terminal state. Without this a
        fire-and-forget job lingers 'InProgress' forever if nobody opens the jobs view
        to --refresh it (a real snapshot sat InProgress for 10 days)."""
        from glorfindel import jobs as _jobs
        if not any(j.get("status") == "InProgress" for j in _jobs.all_jobs()):
            return  # cheap local check — no Azure call when nothing is pending
        for j in _jobs.reconcile_jobs(None if self.dry_run else self.ttl_connector):
            vm_short = j.get("resource_id", "").rsplit("/", 1)[-1]
            self.console.print(f"[dim]Job {_outside(j.get('type'))} {_outside(vm_short)} → "
                               f"{_outside(j.get('status'))}[/dim]")

    # ── the passes, each in its own thread ─────────────────────────────────────────────────────

    def _reassert(self) -> None:
        """Start a reassertion pass in its own thread: a re-application cuts sessions
        through Run Command (up to 300 s) and used to stall the main loop — no new
        signal read, no TTL check, no heartbeat meanwhile (third review, details)."""
        if self.dry_run or self._reassert_every_s <= 0 or getattr(self.ttl_connector, "read_only", False):
            return
        if time.time() - self._last_reassert < self._reassert_every_s:
            return
        if self._reassert_thread.busy():
            return      # the previous pass is still running: never two at once
        self._last_reassert = time.time()
        self._reassert_thread.start(self._reassert_pass)

    def _reassert_pass(self) -> None:
        passes._watch_reassert_pass(self.console, self.ttl_connector, self.mode_override, self._output_lock,
                                    self._reassert_seen)

    def _identity_checks(self) -> None:
        if self.dry_run:
            return
        from glorfindel import escalations as _escs
        if not _escs.identity_checks_requested():
            return                       # cheap local check — no Graph call when nothing waits
        if self._identity_thread.busy():
            return
        self._identity_thread.start(self._identity_run)

    def _identity_run(self) -> None:
        from glorfindel.identity_checks import run_requested
        try:
            for r in run_requested():
                with self._output_lock:
                    self.console.print(f"[dim]Vérification d'identité {_outside(r['id'][:8])} : "
                                       f"{_outside(r['verdict'])}[/dim]")
        except Exception as exc:
            _say_failure(self.console, "watch: vérification d'identité en erreur", exc, self._output_lock)

    def _recoveries(self) -> None:
        if self.dry_run or self._recovery_every_s <= 0:
            return
        if time.time() - self._last_recovery < self._recovery_every_s:
            return
        if self._recovery_thread.busy():
            return
        self._last_recovery = time.time()
        self._recovery_thread.start(self._recovery_pass)

    def _recovery_pass(self) -> None:
        passes._watch_recovery_pass(self.console, self.ttl_connector, self._emit_recovery, self._output_lock,
                                    self._recovery_said)

    def _door_facts(self) -> None:
        from glorfindel.door_facts import interval_s as _door_every
        if self.dry_run or _door_every() <= 0:
            return
        if self._door_thread.busy():
            return
        self._door_thread.start(self._door_pass)

    def _door_pass(self) -> None:
        passes._watch_door_pass(self.console, self.ttl_connector, self._output_lock, self._door_said)

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

    def _relay_notices(self) -> None:
        """JUG2 (#765): every minute, an autonomous action's announcement — and a cut's closure
        (JUG2b) — left to the Discord bot and not posted by it, the bot mute (its heartbeat absent or
        stale) or the notice waiting for 10 min, said by the webhook, once (glorfindel/vm_notices.py,
        ``relay_pass``). JUG2b (#768): in its own thread, one pass at a time — a webhook that does not
        answer never holds this loop (runs/ read, the heartbeat, the reassertion, the TTL, « Verify »)."""
        if self._relay_thread.busy():
            return      # the previous pass is still running: never two at once
        self._relay_thread.start(self._relay_run)

    def _relay_run(self) -> None:
        from glorfindel import vm_notices as _vm_notices
        try:
            said = _vm_notices.relay_pass()
        except Exception as exc:
            _say_failure(self.console, "watch: _relay_notices en erreur", exc, self._output_lock)
            return
        if said:
            with self._output_lock:
                self.console.print(f"[yellow]{said} notice(s) dite(s) par le webhook : le bot Discord "
                                   "se tait (JUG2)[/yellow]")

    def _expire_exposed(self) -> None:
        """SEC2c (#1107): every minute, the blocks of the exposed zone due — their 24 h past, or the address
        held by another VM — lifted and said (glorfindel/exposed_blocks.py); a lift that fails, tried again
        at the next pass. A cheap local read first: no thread, no Azure call when none is recorded."""
        from glorfindel import exposed_blocks
        if self.dry_run or self._expiry_thread.busy() or not exposed_blocks.marked():
            return
        self._expiry_thread.start(self._expiry_run)

    def _expiry_run(self) -> None:
        from glorfindel import exposed_blocks
        try:
            report = exposed_blocks.expiry_pass(self.ttl_connector)
        except Exception as exc:
            _say_failure(self.console, "watch: expiration des blocages de la zone exposée en erreur", exc,
                         self._output_lock)
            return
        for r in report:
            if r["outcome"] in ("lifted", "failed"):
                with self._output_lock:
                    self.console.print(f"[yellow]zone exposée : {_outside(r['ip'])} sur {_outside(r['vm'])} → "
                                       f"{r['outcome']}[/yellow] ({_outside(r['why'])})")

    # ── the exercise windows, the verdicts, the drill: local reads ─────────────────────────────

    def _observe_windows(self) -> None:
        """SEC14 (V-20): the windows read every minute — a window written on this host is
        written down in the watch's own state within a minute, and bounded by that moment
        (eregion_core/exercise.py, ``observe``). SEC18: and what runs/ holds out of its writers'
        places, said once (``runs_layout.say_strays``)."""
        from eregion_core import exercise as _exercise, runs_layout as _layout
        _exercise.observe()
        _layout.say_strays(self.runs_dir, lambda text: self._say_channel(f"Canal runs/ : {text}"))

    def _propose_verdicts(self) -> None:
        """VP1 (#615): every minute, the exercise cards of the week still to judge, held to what the
        drill of the week expected (its copy and its expectations in this image, Orodruin's status,
        the run's report, the window) — a verdict proposed on the expected one, why not on the others
        (glorfindel/proposed_verdict.py). Never a verdict given; the decision never reads it."""
        from glorfindel import proposed_verdict
        # VP1b: a card the pass cannot assess is skipped and said once, here — the others still proposed.
        proposed_verdict.refresh(self.runs_dir, say=lambda text: self._say_channel(f"Verdict proposé : {text}"))

    def _judge_drill(self) -> None:
        """DRL1b (#613): every minute, the drill of the week judged — its last occurrence's verdict,
        the absence alarm, by the code over what this host pulled (glorfindel/drill_watch.py), kept for
        the bot and the console. Never the model; the decision never reads it."""
        from glorfindel import drill_watch
        drill_watch.refresh(self.runs_dir)

    def _publish_relaxed(self) -> None:
        """CFG3 (#1139): every minute, the view « Relaxed » — what glorfindel-config.yaml relaxes, classed by
        CFG4's pure function — written in the watch's own directory (glorfindel/relaxed.py): local, no
        Azure call, computed again only when what it reads changed. In a thread of its own, one pass at a
        time: classing a long file takes seconds, never the loop's (« Verify », IR1a). The console reads it
        there, read-only; it never computes nor writes it."""
        if self._relaxed_thread.busy():
            return
        self._relaxed_thread.start(self._relaxed_run)

    def _relaxed_run(self) -> None:
        from glorfindel import relaxed
        try:
            view = relaxed.publish(mode_override=self.mode_override)
        except Exception as exc:
            _say_failure(self.console, "watch: vue « Relaxed » non écrite (runs/glorfindel/config/)", exc,
                         self._output_lock)
            return
        if self._relaxed_said:
            return
        self._relaxed_said = True            # §6: said once, at the start — its lines, bounded, escaped
        style = {"info": "[dim]{}[/dim]", "line": "[dim]  · {}[/dim]", "warn": "[yellow]⚠ {}[/yellow]"}
        with self._output_lock:
            for level, text in relaxed.start_lines(view):
                self.console.print(style[level].format(_outside(text)))
