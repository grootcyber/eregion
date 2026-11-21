"""runs/ read as an input the watch does not trust (SEC3, SEC8, SEC18) — WCH1 (#1019): out of
glorfindel/cli.py, nothing changed in what it reads, refuses or says.

A line parsed (`_parse_signal_line`, `_parsed_or_said`), admitted or refused (`_admit_from_runs`,
`_refuse_from_runs`), the queue it waits in (`_queue_of`); the channel's bounds (`ChannelRoom`, SEC8);
the reader of Annatar's directory and its rate (`RunsChannel`).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from rich.markup import escape as _esc_markup

from glorfindel.terminal import outside as _outside


def _parse_signal_line(raw: str):
    """(data, Signal) for one JSONL line. Raises on a malformed line.

    Unknown keys are dropped (same filtering as the RulePoller dispatch) so a field
    added by a newer Annatar can't make Signal(**data) raise."""
    from eregion_core.signals import Signal
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    sig = Signal(**{k: data.get(k, "") for k in Signal.__dataclass_fields__})
    return data, sig


def _refuse_from_runs(console, data: dict, why: str, source: str) -> None:
    """A line of runs/ refused: said, and counted (glorfindel/signal_origin.py)."""
    from glorfindel import signal_origin
    console.print(f"[bold red]Signal refusé ({_esc_markup(source)}) :[/bold red] {_esc_markup(why)} "
                  "— rien n'est décidé (compté : ~/.glorfindel/channel_refusals.json)")
    signal_origin.refuse(data, why, source)


def _admit_from_runs(console, data: dict, source: str):
    """(data, Signal) the watch may decide on, for one line of runs/*_signals.jsonl — None
    when the line is refused (said: the log, the counter). SEC3 (#274),
    glorfindel/signal_origin.py."""
    from eregion_core.signals import Signal
    from glorfindel import signal_origin
    adm = signal_origin.admit(data)
    if adm.signal is None:
        _refuse_from_runs(console, data, adm.refused, source)
        return None
    if adm.dropped:
        console.print(f"[yellow]{_outside(source)} : champs ignorés ({_esc_markup(', '.join(adm.dropped[:8]))}) — "
                      "un injecteur ne les écrit pas[/yellow]")
    sig = Signal(**{k: adm.signal.get(k, "") for k in Signal.__dataclass_fields__})
    return adm.signal, sig


def _parsed_or_said(path: Path, line: str, say) -> list:
    """[(data, Signal)] for one line of runs/, or [] when it does not parse — said through
    `say`. One bad line used to kill the whole watch (json.loads / Signal(**) unguarded)."""
    try:
        return [_parse_signal_line(line.strip())]
    except Exception as exc:
        say(f"Ligne de signal ignorée ({path.name}) : {exc}")     # `say` escapes it (SEC-F)
        return []


def _queue_of(data: dict) -> str:
    """The watch's queue a signal waits in: its VM's — or, for a card of the control plane or of
    an identity filed on what it names (AL1c), its plane's: one queue each, as when they all
    waited in the anchor VM's, never a thread per NSG, group or identity, nor a wait behind a VM
    they have nothing to do with."""
    ctx = data.get("context") or {}
    target = ctx.get("target") if isinstance(ctx.get("target"), dict) else None
    if ctx.get("plane") in ("control", "identity") and target and target.get("kind") != "vm":
        return f"plane:{ctx['plane']}"
    return str(data.get("resource_id", "unknown"))


class ChannelRoom:
    """SEC8: what the runs/ channel may start — the searches in flight (one per VM and technique,
    CHANNEL_POLLS in all), its lines waiting per VM (CHANNEL_QUEUED_PER_VM), the VMs it names
    (CHANNEL_VMS). Beyond, a line is refused and said, never a thread or a queue grown. The
    RulePoller's detections are never held by these bounds. The bounds are read when the watch
    starts; `queues` are the watch's queues (a VM that has one is already named)."""

    def __init__(self, queues: dict) -> None:
        from eregion_core.channel_reader import CHANNEL_POLLS, CHANNEL_QUEUED_PER_VM, CHANNEL_VMS
        self.CHANNEL_POLLS, self.CHANNEL_QUEUED_PER_VM, self.CHANNEL_VMS = (
            CHANNEL_POLLS, CHANNEL_QUEUED_PER_VM, CHANNEL_VMS)
        self._resource_queues = queues
        self._channel_lock = threading.Lock()
        self._channel_polls: set[tuple[str, str]] = set()
        self._channel_waiting: dict[str, int] = {}
        self._channel_vms: set[str] = set()

    def _channel_room(self, data: dict) -> tuple[str, tuple | None]:
        """(why the line is refused — "" when it has room —, the search it takes) for a line
        of runs/ (SEC8). Taken under the lock: the room is counted as it is given."""
        key = str(data.get("resource_id", "unknown")).lower()
        search = (key, str(data.get("ttp") or "")) if data.get("event") == "attack_started" else None
        with self._channel_lock:
            if key not in self._channel_vms and key not in self._resource_queues and len(self._channel_vms) >= self.CHANNEL_VMS:
                return f"le canal nomme déjà {self.CHANNEL_VMS} VM : une de plus est refusée", None
            if search is not None:
                if search in self._channel_polls:
                    return "une recherche de cette technique sur cette VM est déjà en cours", None
                if len(self._channel_polls) >= self.CHANNEL_POLLS:
                    return f"{self.CHANNEL_POLLS} recherches du canal déjà en cours : une de plus est refusée", None
                self._channel_polls.add(search)
            else:
                if self._channel_waiting.get(key, 0) >= self.CHANNEL_QUEUED_PER_VM:
                    return (f"{self.CHANNEL_QUEUED_PER_VM} lignes du canal attendent déjà pour cette VM : "
                            "une de plus est refusée"), None
                self._channel_waiting[key] = self._channel_waiting.get(key, 0) + 1
            self._channel_vms.add(key)
        return "", search

    def _free_search(self, search) -> None:
        """A search of the channel ended: its room given back."""
        with self._channel_lock:
            self._channel_polls.discard(search)

    def _free_line(self, key: str) -> None:
        """A line of the channel decided (or left a full queue): its room given back."""
        with self._channel_lock:
            self._channel_waiting[key] = max(0, self._channel_waiting.get(key, 0) - 1)


class RunsChannel:
    """SEC8 (#414): runs/ read as an input the watch does not trust — a regular file only,
    never a link, never blocking; a bounded read per file and per poll, a bounded rate
    (eregion_core/channel_reader.py). Files there at startup: read from their end. SEC18 (N-05): an
    injector's signals are read from Annatar's own directory only; what is anywhere else in runs/
    (the former layout, another writer's file in a writer's directory) is never read, and said
    (eregion_core/runs_layout.py). Each line admitted is handed to `dispatch`."""

    def __init__(self, console, lock, runs_dir, dispatch) -> None:
        from eregion_core import runs_layout as _layout
        from eregion_core.channel_reader import ChannelReader
        self.console = console
        self._output_lock = lock
        self._dispatch = dispatch
        self._channel = ChannelReader(_layout.dir_of(_layout.ANNATAR, runs_dir), self._say_channel)
        self._channel.track_existing()

    def _say_channel(self, text: str, kind: str = "refused") -> None:
        with self._output_lock:
            if kind == "new":
                self.console.print(f"[dim]{_esc_markup(text)}[/dim]")
            else:
                self.console.print(f"[yellow]{_esc_markup(text)}[/yellow]")

    def _poll(self) -> None:
        for path, line in self._channel.poll():
            for data, _sig in _parsed_or_said(path, line, self._say_channel):
                # SEC3 (#274): runs/ is written by the injectors too — only what they emit,
                # each for what it is (glorfindel/signal_origin.py).
                admitted = _admit_from_runs(self.console, data, path.name)
                if admitted is not None:
                    self._dispatch(*admitted, source=path.name)   # non-blocking — a worker takes over
        over = self._channel.budget.report()
        if over:
            self._say_rate(over)

    def _say_rate(self, over: dict) -> None:
        """The channel's rate passed in the last minute: said in one line, counted; nothing decided."""
        from eregion_core.channel_reader import PER_WRITER_PER_MIN
        from glorfindel import signal_origin as _origin
        n = sum(lines for lines, _ in over.values())
        passed = sum(nbytes for _, nbytes in over.values())
        files = ", ".join(f"{name} ({k})" for name, (k, _) in sorted(over.items())[:5])
        why = (f"débit du canal dépassé (au plus {PER_WRITER_PER_MIN} lignes par fichier et par "
               "minute) : non admis")
        what = " et ".join(x for x in (f"{n} ligne(s) refusée(s)" if n else "",
                                       f"{passed} octet(s) non lus" if passed else "") if x)
        with self._output_lock:
            self.console.print(f"[bold red]Canal runs/ :[/bold red] {what}, {_esc_markup(why)} — "
                               f"{_esc_markup(files)}{' …' if len(over) > 5 else ''} ; rien n'est décidé "
                               "(compté : ~/.glorfindel/channel_refusals.json)")
        _origin.refuse({"event": "(débit)"}, why, files, count=max(n, 1))
