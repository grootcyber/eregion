from __future__ import annotations

import json
from pathlib import Path

from eregion_core.signals import Signal


def load_signals(path: str | Path) -> list[Signal]:
    """Load all signals from a JSONL file produced by Annatar — read as runs/ is read (SEC-A1,
    V-02: ``eregion_core.channel_reader.read_text``): a regular file only, never through a link,
    never blocking, at most FILE_BYTES. A pipe, a link, a file too large raise
    ``channel_reader.Refused`` (an OSError), never read."""
    from eregion_core.channel_reader import read_text
    signals = []
    for line in read_text(path).split("\n"):   # JSONL: \n ends a line, never U+2028
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        signals.append(Signal(**data))
    return signals


def load_latest_signals(run_id: str, runs_dir: str | Path | None = None) -> list[Signal]:
    """A run's signals, from Annatar's own directory (SEC18, ``runs/annatar``) by default."""
    if runs_dir is None:
        from eregion_core import runs_layout
        runs_dir = runs_layout.dir_of(runs_layout.ANNATAR)
    path = Path(runs_dir) / f"{run_id}_signals.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No signals file for run: {run_id}")
    return load_signals(path)
