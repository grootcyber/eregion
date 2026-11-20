"""G1d: a fault never starts while an exercise window on one of its targets still runs.

A fault's window runs from its start to its end, plus the grace (``GRACE_AFTER_S``, 15 min:
eregion_core/exercise.py ``last_moment``) — the time a detection on its target still counts for
it. A decision that falls after the next fault on that target started, and still inside the
first one's window, leaves the first unmeasured (analysis/fault_rate.py): on 20/11, three faults
on gondolin 5 to 13 min apart left two of them unmeasured and the third taken for an attack it
was not. The next fault on a target therefore waits for the previous window's last moment, and
the refusal says until when, in UTC.

The windows read are Gothmog's own, where ``open_window`` writes them on this host (SEC18:
``runs/gothmog/exercises``, or ``EREGION_EXERCISES_DIR``), and only a fault's (``injector``
gothmog, or none said): a fault waits for the previous fault, never for a technique — a Dagorlad
request chains a technique and a fault on one VM on purpose (DG-b). Read strictly, nothing written:

- no directory there: no window was ever written — the run may go;
- a directory that cannot be listed, a path there that is no directory, a file that cannot be read
  (``read_regular``: a regular file only, never a link, at most ``WINDOW_BYTES``) or holds no
  window (no start, expiry or targets): refused — what cannot be read is never « no window »;
- a tombstone (``purged_at``, a window emptied long after its last moment) is no window.

A target is compared without its case, by its full id and by its VM's name, in union: a VM of
another topology (``rg-celebrimbor-*``, which the inscription admits) holds the next fault as the
bench's does — refusing more, never less.

Nothing purges this directory (the watch purges only its own): past MAX_WINDOW_FILES windows,
every fault refuses — the README says what to do.

``eregion_core.exercise.load_windows`` is not used here: it skips what it cannot read, and purges
in the directory it is given.
"""
from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from eregion_core import runs_layout
from eregion_core.channel_reader import read_regular
from eregion_core.exercise import MAX_WINDOW_FILES, WINDOW_BYTES, exercises_dir, last_moment


def windows_dir() -> Path:
    """Where this host's Gothmog writes its windows — ``open_window``'s own directory."""
    return exercises_dir(runs_layout.dir_of(runs_layout.GOTHMOG))


def vm_ids(names: list[str], subscription_id: str, resource_group: str) -> list[str]:
    """The full resource ids of the VMs a fault declares, as a window holds its targets."""
    return [f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            f"/providers/Microsoft.Compute/virtualMachines/{name}" for name in names]


def _keys(target) -> set[str]:
    """A target as it is compared: its id and its VM's name (the id's last segment), lower case."""
    text = str(target).lower().rstrip("/")
    return {text, text.rsplit("/", 1)[-1]}


def busy_refusal(targets: list[str], now: datetime, directory: Path | None = None) -> str:
    """'' when no window on one of ``targets`` (full ids, or VM names) still runs at ``now``;
    else why, and until when (UTC). Fail closed on what cannot be read (the module's docstring)."""
    directory = windows_dir() if directory is None else directory
    try:
        st = os.lstat(directory)
    except FileNotFoundError:
        return ""                                    # no window ever written on this host
    except OSError as e:
        return f"window: the exercise windows cannot be read ({type(e).__name__}) — not run"
    if not stat.S_ISDIR(st.st_mode):
        return "window: the exercise windows' place is no directory — not run"
    try:
        paths = sorted(p for p in directory.iterdir() if p.suffix == ".json")
    except OSError as e:
        return f"window: the exercise windows cannot be listed ({type(e).__name__}) — not run"
    if len(paths) > MAX_WINDOW_FILES:
        return f"window: more than {MAX_WINDOW_FILES} exercise windows, not all read — not run"
    keys = set().union(*(_keys(t) for t in targets))
    busy: list[tuple[datetime, str]] = []
    for path in paths:
        try:
            data, _ = read_regular(path, WINDOW_BYTES)
            window = json.loads(data.decode("utf-8"))
        except (OSError, ValueError, RecursionError) as e:
            return f"window: {path.name} cannot be read ({type(e).__name__}) — not run"
        if not isinstance(window, dict):
            return f"window: {path.name} holds no window — not run"
        if window.get("purged_at"):
            continue                                 # a tombstone: no window left
        if window.get("injector") not in (None, "gothmog"):
            # A fault waits for the previous fault: a Dagorlad request chains a technique and a
            # fault on one VM on purpose (DG-b). One that does not say its injector counts.
            continue
        last, aimed = last_moment(window), window.get("targets")
        if last is None or not isinstance(aimed, list):
            return f"window: {path.name} has no readable start, expiry or targets — not run"
        if keys & set().union(*(_keys(t) for t in aimed)) and last > now:
            busy.append((last, str(window.get("run_id") or path.stem)))
    if not busy:
        return ""
    last, run_id = max(busy)
    last = last.astimezone(timezone.utc)
    return (f"window: the exercise {run_id} on this target runs until {last:%Y-%m-%d %H:%M} UTC, "
            "its grace included — a decision meanwhile could be its; wait until then")
