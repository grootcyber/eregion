"""The watch itself — WCH1 (#1019): `glorfindel watch`'s loop, out of glorfindel/cli.py, its state in
objects. Nothing changed in what it does: the same lines said, the same threads, in the same order.

`Watch.start` is the startup in its order; `Watch.tick` one turn of the loop (runs/ read, « Verify »
every 5 polls, the housekeeping every 30); `Watch.run_forever` the loop until Ctrl+C.
"""
from __future__ import annotations

import threading
import time

from rich.markup import escape as _esc_markup

from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch import beat as _beat, networks as _networks, rules as _rules, startup as _startup
from glorfindel.watch.beat import Heartbeat
from glorfindel.watch.dispatch import Dispatcher
from glorfindel.watch.housekeeping import Housekeeping
from glorfindel.watch.rules import Rules
from glorfindel.watch.runs_channel import RunsChannel

IDENTITY_EVERY = 5         # polls: « Verify » answered within ~10 s (IR1a)
HOUSEKEEPING_EVERY = 30    # polls: ~1 min at a 2 s interval


class Watch:
    """One watch: its options, its console and the lock its threads print under, and its parts —
    made by `start`, in the order the watch always made them."""

    def __init__(self, runs_dir: str, *, dry_run: bool, model: str, memory_path: str | None, interval: float,
                 rules_file: str | None, mode_override: str | None, console, show_signal, show_decision) -> None:
        self.runs_dir = runs_dir
        self.dry_run = dry_run
        self.model = model
        self.memory_path = memory_path
        self.interval = interval
        self.rules_file = rules_file
        self.mode_override = mode_override
        self.console = console
        self.show_signal = show_signal
        self.show_decision = show_decision
        self._output_lock = threading.Lock()
        self._ttl_check_counter = 0
        self.agent = self.dispatcher = self.channel = self.housekeeping = self.beat = self.rules = None

    def start(self) -> None:
        """Everything before the loop, in its order: what the watch checks, says and starts."""
        from glorfindel.agent import GlorfindelAgent      # first, as ever: before the logs are set up
        console, dry_run = self.console, self.dry_run
        _startup._setup_logging()
        _beat._make_injectors_dir(console)
        _startup._refuse_bad_config(console)
        ttl_h = _startup._watch_ttl_h(console)             # never stops the watch (TTL1)
        _startup._warm_up_and_migrate(console, dry_run)
        self.agent = GlorfindelAgent(
            dry_run=dry_run, model=self.model, memory_path=self.memory_path,
            autonomy_default=self.mode_override,
        )
        _startup._say_autonomy(console, self.agent, self.mode_override, dry_run)
        _startup._say_memory(console, getattr(self.agent, "memory", None))
        _startup._say_credentials(console, self.agent, dry_run)
        _networks.say_networks(console, dry_run)           # SEC2b: the client's network, its names
        # Private IP → VM: one Azure listing, cached 5 min, read by the RulePoller and by every
        # attack_started line alike (SEC4c) — a line used to list them all again.
        self.dispatcher = Dispatcher(console, self._output_lock, self.agent, dry_run=dry_run,
                                     show_signal=self.show_signal, show_decision=self.show_decision,
                                     ip_owners=None if dry_run else _rules._shared_private_ips())
        self.channel = RunsChannel(console, self._output_lock, self.runs_dir, self.dispatcher._dispatch)
        self.housekeeping = Housekeeping(
            console, self._output_lock, dry_run=dry_run, mode_override=self.mode_override,
            runs_dir=self.runs_dir, ttl_h=ttl_h, emit=self.dispatcher._emit_recovery,
            say_channel=self.channel._say_channel)
        self.beat = Heartbeat(console)
        self.beat.warn_if_another()
        _startup._start_action_queue(console, dry_run, self.beat._signer, self._say_queue, self.runs_dir)
        self.beat.install()
        self._start_services()
        self.dispatcher.watch_channel = _startup._open_return_channel(console, dry_run, self.runs_dir)
        _startup._register_own_writes(console, self.dispatcher.watch_channel, dry_run)
        self.rules = Rules(console, self.rules_file, dry_run=dry_run, mode_override=self.mode_override)
        self.rules.start(self.dispatcher._rule_dispatch, self.dispatcher._ip_owners)
        self.rules.start_audit()
        msg = (f"[bold]Glorfindel watching[/bold] [dim]{_outside(self.runs_dir)}/[/dim]  "
               f"(TTL={ttl_h}h, Ctrl+C to stop)")
        console.print(msg + "\n")
        self.beat._write_heartbeat()
        self._first_pass()

    def _first_pass(self) -> None:
        """Before the loop: the windows read (SEC14), and the view « Relaxed » started (CFG3) — in its own
        thread, so a long file never holds the start; its lines are said once it is written. A failure
        said, never the watch stopped."""
        for task in (self.housekeeping._observe_windows, self.housekeeping._publish_relaxed):
            try:
                task()
            except Exception as exc:   # the windows fall toward real; the watch goes on
                _say_failure(self.console, f"watch: {task.__name__} en erreur", exc)

    @staticmethod
    def _start_services() -> None:
        """H-1: an exercise window marks a VM only if this watch reads it enrolled — its tags and
        its resource group's, through Azure, cached (eregion_core/inscription.py). Without the
        read (no credential, no right), no window marks anything: every cycle is labelled real.
        JUG2c (#788): a notice queued where no webhook may be waited for (a VM's lock, the
        reassertion's pass) starts a pass at once, in its own thread — never left to the next minute."""
        from eregion_core import exercise as _exercise
        from eregion_core.inscription import TagEnrollment
        from glorfindel import vm_notices as _served_notices
        _exercise.set_enrollment_check(TagEnrollment())
        _served_notices.serve()

    def _say_queue(self, text: str) -> None:
        with self._output_lock:
            self.console.print(f"[cyan]{_esc_markup(text)}[/cyan]")

    def _each(self, tasks) -> None:
        """Each task on its own: one that keeps failing (an old isolation the subscription
        guard refuses…) no longer skips the others — the reassertion, the heartbeat — at every
        pass: the watch looked dead (fourth review, Q12)."""
        for _task in tasks:
            try:
                _task()
            except Exception as exc:
                _say_failure(self.console, f"watch: {_task.__name__} en erreur", exc, self._output_lock)

    def tick(self) -> None:
        """One turn of the loop: runs/ read; « Verify » every IDENTITY_EVERY polls; the housekeeping
        every HOUSEKEEPING_EVERY, each task in its order — the windows read after the heartbeat, the
        verdicts proposed after the windows (VP1)."""
        hk = self.housekeeping
        self.channel._poll()
        self._ttl_check_counter += 1
        if self._ttl_check_counter % IDENTITY_EVERY == 0:      # « Verify » answered within ~10 s (IR1a)
            self._each((hk._identity_checks,))
        if self._ttl_check_counter % HOUSEKEEPING_EVERY == 0:  # housekeeping every 30 polls (~1 min at 2s interval)
            self._each((
                hk._recoveries,         # REC1: its own thread, started here at most once a pass
                hk._door_facts,         # LEV2: information on the isolation card, its own thread
                hk._dossier_retention,  # DOS3: the dossiers 30 days after the lift, local, once an hour
                hk._relay_notices,      # JUG2: the bot mute, the webhook says the actions
                hk._expire_exposed,     # SEC2c: the exposed zone's blocks at 24 h, its own thread
                hk._check_ttl, hk._reconcile_jobs, hk._reassert, self.beat._write_heartbeat,
                hk._observe_windows,
                hk._propose_verdicts,   # VP1: after the windows are read, on the cards of the week
                hk._judge_drill,        # DRL1b: the drill of the week's verdict, for the bot and the console
                hk._publish_relaxed,    # CFG3: the view « Relaxed », written by the watch alone
            ))

    def run_forever(self) -> None:
        """The loop, until Ctrl+C: the poller stopped, the heartbeat removed."""
        try:
            while True:
                try:
                    self.tick()
                except Exception as exc:
                    # The daemon outlives a bad iteration (unreadable file, transient Azure
                    # error in the TTL/jobs housekeeping); the next poll retries. SEC-F: said escaped —
                    # printed raw, a tag the error quoted raised here, out of the loop: the watch died.
                    _say_failure(self.console, "watch: itération en erreur", exc, self._output_lock)
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.rules.stop()
            self.beat._remove_heartbeat()
            self.console.print("\n[dim]Watch stopped.[/dim]")


def run(runs_dir: str, **options) -> None:
    """`glorfindel watch`: a watch made, started, and run until Ctrl+C (glorfindel/cli.py)."""
    watch = Watch(runs_dir, **options)
    watch.start()
    watch.run_forever()
