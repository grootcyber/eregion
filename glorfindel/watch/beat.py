"""The watch's heartbeats, and the injectors' directory (SEC3, SEC5, SEC17, SEC19) — WCH1 (#1019): out of
glorfindel/cli.py's `watch()`, nothing changed in them.

Its own heartbeat, ~/.glorfindel/watch_heartbeat, read by the console, the CD of Imladris and a second
watch; a signed copy where the injectors read it, ~/.glorfindel/injectors/watch_heartbeat (V1). Both
removed on exit, so a fast restart never sees a phantom second watch.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from glorfindel.terminal import outside as _outside

# SEC3 (N-05): what the injectors' containers mount, read-only, as their ~/.glorfindel — the
# watch writes a copy of its heartbeat there, nothing else.
_INJECTORS_DIR = Path.home() / ".glorfindel" / "injectors"


def _make_injectors_dir(console) -> None:
    """SEC3: the directory the injectors mount (~/.glorfindel/injectors, their heartbeat), made
    first, as the operator: a `docker compose run annatar` on a fresh host would otherwise
    have docker create it, as root — and the watch could no longer write there."""
    try:
        _INJECTORS_DIR.mkdir(mode=0o755, parents=True, exist_ok=True)
        os.chmod(_INJECTORS_DIR, 0o755)      # theirs to read, whatever the umask
    except OSError as exc:
        console.print(f"[yellow]~/.glorfindel/injectors non créé ({_outside(exc)})[/yellow]")


def _write_watch_heartbeat(path: Path, at) -> None:
    """The watch's heartbeat, written at once (SEC17): a temp file beside it, renamed over it —
    never opened in place, so a reader (the injectors' gate, the console, the CD of Imladris, a second
    watch) never finds it empty or cut. In the mode it always had, 0644: read by other processes."""
    from glorfindel.response.state import _atomic_write_text
    _atomic_write_text(path, at.isoformat(), mode=0o644)


class Heartbeat:
    """The watch's two heartbeats and its key. Its paths are read when it is made, as the watch read
    them at its start: HOME, and the injectors' directory (a test's, under conftest)."""

    def __init__(self, console) -> None:
        self.console = console
        self._HEARTBEAT = Path.home() / ".glorfindel" / "watch_heartbeat"
        # SEC3 (N-05): the injectors' containers mount ~/.glorfindel/injectors/ only, read-only
        # — not the whole of ~/.glorfindel (escalations, isolation state, the client's rules).
        # The watch writes its heartbeat there too, the one thing they read (V1).
        self._INJECTOR_BEAT = _INJECTORS_DIR / "watch_heartbeat"
        self._key_said = ""

    def warn_if_another(self) -> None:
        """Warn if another watch process appears to be running (shared ~/.glorfindel/)."""
        if self._HEARTBEAT.exists():
            try:
                ts = datetime.fromisoformat(self._HEARTBEAT.read_text().strip())
                age_s = (datetime.now(timezone.utc) - ts).total_seconds()
                if age_s < 90:
                    self.console.print(
                        "[yellow]⚠ Another glorfindel watch appears to be running "
                        f"(heartbeat {int(age_s)}s ago).[/yellow]\n"
                        "  Running two watch processes on the same runs/ directory "
                        "will produce duplicate actions.\n"
                        "  Stop the other process or use 'make glorfindel-stop' if "
                        "using Docker Compose."
                    )
            except Exception:
                pass

    def _signer(self):
        """SEC19 (N-03): the watch's key, drawn at its first start (~/.eregion/watch-key, a directory
        only the watch mounts); its fingerprint said, for the operator to pin it on the injectors'
        side (make watch-key). Unavailable: the heartbeats go unsigned — the injectors refuse them.
        Said once until what it says changes."""
        from eregion_core import watch_key as _watch_key
        signer, why = _watch_key.shared()
        said = f"ok {signer.fingerprint}" if signer else why
        if said != self._key_said:
            self._key_said = said
            if signer:
                self.console.print(f"[dim]Clé de la watch : {signer.fingerprint} (make watch-key pour l'épingler)[/dim]")
            else:
                self.console.print(f"[red]Clé de la watch indisponible — battements non signés, les injecteurs "
                                   f"les refusent (SEC19) :[/red] {_outside(why)}")
        return signer

    def _write_heartbeat(self) -> None:
        at = datetime.now(timezone.utc)
        _write_watch_heartbeat(self._HEARTBEAT, at)
        try:
            from eregion_core.watch_gate import beat_body
            from glorfindel.response.state import _atomic_write_text
            # SEC5 (N-03): with the perimeter it watches (a digest of its subscription), which
            # the injectors compare with their own (eregion_core/watch_gate.py). For them to
            # read: nothing secret. SEC19: signed by the watch's key.
            _atomic_write_text(self._INJECTOR_BEAT, json.dumps(beat_body(at, signer=self._signer())), mode=0o644)
        except OSError as exc:          # a directory docker made as root: the watch goes on
            self.console.print(f"[yellow]Battement pour les injecteurs non écrit ({_outside(exc)}) — "
                               "`make glorfindel-start` crée ~/.glorfindel/injectors[/yellow]")

    def _remove_heartbeat(self) -> None:
        self._HEARTBEAT.unlink(missing_ok=True)
        try:   # the injectors' copy: never an error at stop (a file in its place, a root-owned beat)
            self._INJECTOR_BEAT.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _on_sigterm(_signum, _frame):
        raise SystemExit(0)

    def install(self) -> None:
        """Remove the heartbeat on exit so a fast restart (docker compose restart / stop+up)
        doesn't see a stale heartbeat and warn about a phantom second watch. Ctrl+C is
        handled by the loop; SIGTERM (docker stop) won't run its except block, so convert it to
        SystemExit which triggers atexit cleanup."""
        import atexit as _atexit
        import signal as _signalmod
        _atexit.register(self._remove_heartbeat)
        _signalmod.signal(_signalmod.SIGTERM, self._on_sigterm)
