"""The local reads of the watch's housekeeping — WCH2 (#1150): out of glorfindel/watch/housekeeping.py,
nothing changed in what each does, says, or when.

Every minute, nothing here reaches Azure: the exercise windows (SEC14) and what runs/ holds out of its
writers' places (SEC18), the verdicts proposed (VP1), the drill of the week judged (DRL1b), and the view
« Relaxed » (CFG3), that one in a thread of its own. A mixin of `Housekeeping`: it reads its console, its
lock, its runs/, its --mode and its runs/ channel.
"""
from __future__ import annotations

from glorfindel.terminal import outside as _outside, say_failure as _say_failure
from glorfindel.watch.passes import Solo


class LocalReads:
    """The local part of `Housekeeping`: the windows, the verdicts, the drill, the view « Relaxed »."""

    def _init_relaxed(self) -> None:
        # CFG3 (#1139): the view « Relaxed », computed in a thread of its own; its lines said once, at the start.
        self._relaxed_thread = Solo("relaxed-view")
        self._relaxed_said = False

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
