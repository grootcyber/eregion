"""A detection to its VM's queue, and the queue's thread (SEC-A2, SEC-F, SEC8) — WCH1 (#1019): out of
glorfindel/cli.py's `watch()`, nothing changed in what it decides, shows or says.

Signals from different resource_ids are processed in parallel; signals from the same resource_id are
serialized (a queue per resource, the gravest first). attack_started: its search in a thread of its own.
"""
from __future__ import annotations

import threading

from rich.markup import escape as _esc_markup

from eregion_core.signals import Signal
from glorfindel import decision_queue as _dq
from glorfindel import model_budget as _mb
from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch.runs_channel import ChannelRoom, _queue_of, _refuse_from_runs


class Dispatcher:
    """Per-resource dispatch: resource_id → its decision queue — bounded, the gravest first
    (SEC-A2, glorfindel/decision_queue.py); one gate for the whole watch: one decision of the
    model per VM, rule and gravity in a window, a ceiling of calls per minute. `show_signal` and
    `show_decision` are the CLI's own displays (a signal's head, a decision). `watch_channel`, the
    return channel, is set once it is open — before any line is read."""

    def __init__(self, console, lock, agent, *, dry_run: bool, show_signal, show_decision,
                 ip_owners=None) -> None:
        self.console = console
        self._output_lock = lock
        self.agent = agent
        self.dry_run = dry_run
        self._signal_head = show_signal
        self._render_decision = show_decision
        self._resource_queues: dict[str, _dq.DecisionQueue] = {}
        self._decision_gate = _dq.DecisionGate()
        # PRT2: the breaker in dollars, before the gate; the guard of every call of the watch.
        self.budget = _mb.Ledger(dry_run=dry_run)
        _mb.install(self.budget)
        console.print(f"[dim]{_esc_markup(self.budget.said())}[/dim]")     # its two envelopes, at the start
        self.room = ChannelRoom(self._resource_queues)
        self._ip_owners = ip_owners
        self.watch_channel = None

    # ── a VM's queue and its thread ────────────────────────────────────────────────────────────

    def _get_or_start_worker(self, resource_id: str) -> "_dq.DecisionQueue":
        """Return the resource queue, starting its worker thread if needed.

        Keyed case-insensitively: the RulePoller carries the lowercase id from the
        Heartbeat, Annatar and the CLI the canonical one — two workers for the same VM
        ran two decisions in parallel instead of in series (real run, 2026-10-05)."""
        key = resource_id.lower()
        if key not in self._resource_queues:
            q = _dq.DecisionQueue(on_drop=lambda item, why: self._left(resource_id, key, item, why))
            self._resource_queues[key] = q
            vm_short = resource_id.split("/")[-1]
            t = threading.Thread(
                target=self._worker, args=(q, key), daemon=True, name=f"glorf-{vm_short}"
            )
            t.start()
        return self._resource_queues[key]

    def _left(self, resource_id: str, key: str, item, why: str) -> None:
        """SEC-A2: a detection out of a full queue — its card without a decision of the
        model, said here; never in silence."""
        _data, _sig, _from_channel = item
        try:
            _dq.keep_facts(_data, getattr(self.agent, "incidents", None))     # B3a: never lost
            _dq.record_undecided(_data, "full", why, dry_run=self.dry_run)
            with self._output_lock:
                self.console.print(f"[bold red]File pleine ({_esc_markup(str(resource_id))}) :[/bold red] "
                                   f"{_outside(_sig.signal_id)} — {_esc_markup(why)} ; carte "
                                   "undecided_detection")
        except Exception as e:
            _say_failure(self.console, f"Error recording {_sig.signal_id}", e, self._output_lock)
        finally:
            if _from_channel:
                self.room._free_line(key)

    def _one(self, q, key: str, item) -> None:
        """One detection of this VM's queue: shown, decided (or its card), the decision shown.
        SEC-F: what is shown never stands between a detection and its decision — an error
        of display is said, and the decision is taken all the same."""
        _data, _sig, _from_channel = item
        waiting = False
        try:
            try:
                with self._output_lock:
                    self._signal_head(_sig)
                    self.console.print(f"  Event    : {_outside(_sig.event)}  |  "
                                       f"Resource: {_outside(_sig.resource_type)}\n")
            except Exception as e:
                _say_failure(self.console, "Affichage du signal en erreur", e, self._output_lock)
            # SEC-A2: dedup and ceiling before any call — a card, never an action;
            # a grave detection past the ceiling waits in its queue for the room.
            state, why, wait_s = _dq.decide_or_card(
                _data, self.agent.respond, self._decision_gate, dry_run=self.dry_run,
                incidents=getattr(self.agent, "incidents", None), budget=self.budget)
            if wait_s:
                q.put_back(item, wait_s)   # left at once if the queue is full: said, counted
                waiting = True
            with self._output_lock:
                self._say_decided(_sig, state, why, wait_s)
        finally:
            # Put back, it still waits (or left by `_left`, which counted it): its channel
            # line counts until it is decided.
            if _from_channel and not waiting:
                self.room._free_line(key)
            q.task_done()

    def _say_decided(self, _sig, state, why: str, wait_s) -> None:
        """What became of one detection, said under the output lock (held by the caller)."""
        if wait_s:
            self.console.print(f"[yellow]En attente du plafond ({int(wait_s)} s) :[/yellow] "
                               f"{_esc_markup(why)}\n")
        elif state is None:
            self.console.print(f"[yellow]Non décidée par le modèle :[/yellow] "
                               f"{_esc_markup(why)} — carte undecided_detection\n")
        else:
            # SEC-Fc: the decision is taken — its action, its cycle stored by
            # `respond` — before it is shown. Its display failing is said as
            # such, never as « Error processing »: nothing left to process.
            try:
                self._render_decision(state, self.dry_run)
            except Exception as e:
                _say_failure(self.console, f"Décision prise pour {_sig.signal_id}, "
                             "son affichage a échoué", e)   # the lock held already
            self.console.print()

    def _worker(self, q, key: str) -> None:
        """This VM's decision thread (SEC-F): it never ends but on its queue's end. Whatever one
        detection raised — its decision, its display — is said, escaped, by `_say_failure`,
        which never raises in turn: an `except` that printed the error raw raised again on the
        tag it quoted, and the thread died in silence — its queue without a consumer, every
        later detection of the VM undecided until the watch restarted."""
        while True:
            item = q.get()
            if item is None:
                break
            try:
                self._one(q, key, item)
            except Exception as e:
                _say_failure(self.console, f"Error processing {getattr(item[1], 'signal_id', '?')}",
                             e, self._output_lock)

    # ── a signal to its queue ──────────────────────────────────────────────────────────────────

    def _dispatch(self, data: dict, sig: Signal, source: str = "") -> None:
        """Route signal to its resource worker queue.

        attack_started: spawns a poll thread immediately — polling runs in parallel
        per resource, not serialized in the queue. When polling resolves, the
        resulting detection/timeout signal is enqueued for decide+execute.

        All other events go directly to the resource queue (serialized per resource).

        `source`: the file of runs/ the line comes from — bounded by `_channel_room` (SEC8).
        """
        resource_id = data.get("resource_id", "unknown")
        search = None
        if source:
            refused, search = self.room._channel_room(data)
            if refused:
                _refuse_from_runs(self.console, data, refused, source)
                return

        if data.get("event") == "attack_started":
            vm_short = resource_id.split("/")[-1]
            t = threading.Thread(
                target=self._poll_then_free, args=(data, sig, resource_id, search), daemon=True,
                name=f"poll-{vm_short}-{str(sig.signal_id)[-6:]}",
            )
            t.start()
            return

        self._get_or_start_worker(_queue_of(data)).put((data, sig, bool(source)))

    def _poll_then_free(self, data: dict, sig: Signal, resource_id: str, search) -> None:
        try:
            self._poll_and_enqueue(data, sig, resource_id)
        finally:
            if search is not None:
                self.room._free_search(search)

    def _poll_and_enqueue(self, data: dict, sig: Signal, resource_id: str) -> None:
        """An attack_started line's search, in its own thread: its detection (or its timeout)
        enqueued for its VM's decision."""
        src = data.get("raw_signal", {}).get("detection_source", "azure_monitor")
        try:
            with self._output_lock:
                self._signal_head(sig)
                self.console.print(f"  Event    : attack_started → polling {_outside(src)}...\n")
        except Exception as e:      # SEC-F: never a search left for a display
            _say_failure(self.console, "Affichage du signal en erreur", e, self._output_lock)
        try:
            # Imported here, in the try: a failure to import is said and escalated as any
            # failure of the search, never a thread that dies in silence (review of WCH1).
            from glorfindel.agent import resolve_attack_started
            # The row is read as the RulePoller reads it, the private IPs included
            # (SEC4a), from the listing it reads too (SEC4c).
            resolved = resolve_attack_started(data, ip_owners=self._ip_owners)
        except Exception as exc:
            # A persistent backend failure raises (detectors no longer swallow
            # it). This thread used to die with it: the attack was never
            # enqueued, and nothing said detection had been blind.
            try:
                from glorfindel.agent import record_cycle_failure
                record_cycle_failure(data, exc, stage="detection", dry_run=self.dry_run)
            except Exception as unrecorded:     # the agent itself unloadable: said, never silent
                _say_failure(self.console, f"Détection impossible pour {sig.signal_id}, et son escalade "
                             f"non enregistrée ({type(unrecorded).__name__})", exc, self._output_lock)
                return
            _say_failure(self.console, f"Détection impossible pour {sig.signal_id} "
                         "(escalade cycle_failed enregistrée)", exc, self._output_lock)
            return
        if self.watch_channel is not None and hasattr(self.watch_channel, "note_poll"):
            self.watch_channel.note_poll(resolved)   # SEC18: the local verdict; never raises
        resolved_sig = Signal(**{k: resolved.get(k, getattr(sig, k, ""))
                                 for k in sig.__dataclass_fields__})
        self._get_or_start_worker(resource_id).put((resolved, resolved_sig, False))

    def _rule_dispatch(self, signal_data: dict) -> None:
        """A detection of the RulePoller: noted on the return channel (memory only, never raises),
        then to its queue — never held by the runs/ channel's bounds."""
        if self.watch_channel is not None:
            self.watch_channel.note(signal_data)  # memory only, never raises
        sig = Signal(**{
            k: signal_data.get(k, "")
            for k in Signal.__dataclass_fields__
        })
        self._dispatch(signal_data, sig)

    def _emit_recovery(self, signal_data: dict) -> None:
        """REC1 (#668): a recovery proven on Azure, its recovery_complete handed to the VM's queue."""
        self._dispatch(signal_data, Signal(**{k: signal_data.get(k, "") for k in Signal.__dataclass_fields__}))
