"""SEC-A1 (#630, V-02, V-21): what Glorfindel and Annatar read of runs/ is read as the channel is
read (eregion_core/channel_reader.py) — a regular file only, never through a link, never blocking,
bounded — and a refused file is said, never blocking: the exercise windows (``load_windows``, in
the watch's loop and at each decision), the signals ``glorfindel respond`` reads, a campaign's
manifest. And a local window is bounded in the past by its file's mtime, and the windows on one
VM, chained, by CHAIN_MAX_S.

Every read here returns within seconds: a read that blocks on a pipe fails the test, never hangs
the suite (``_quick``). Each FIFO is made in tmp_path.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from eregion_core import exercise, runs_layout
from eregion_core.channel_reader import FILE_BYTES, Refused
from eregion_core.exercise import (CHAIN_HORIZON_S, CHAIN_MAX_S, FUTURE_SKEW_S, GRACE_AFTER_S,
                                   WINDOW_BYTES, chain_refusal, covering_runs, load_windows,
                                   source_of, window_refusal)

VM = "/subscriptions/s/resourcegroups/rg-celebrimbor/providers/microsoft.compute/virtualmachines/vm-celebrimbor-gondolin"
OTHER = VM.replace("gondolin", "bree")
QUICK_S = 3


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _quick(fn, *fifos):
    """``fn()`` within QUICK_S seconds — else the reader left blocked on a pipe is let go (a
    writer opens it, then closes it: end of file) and the test fails."""
    box: dict = {}

    def run():
        try:
            box["out"] = fn()
        except BaseException as e:      # noqa: BLE001 — given back to the test
            box["exc"] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(QUICK_S)
    if t.is_alive():
        for f in fifos:
            with contextlib.suppress(OSError):
                os.close(os.open(f, os.O_WRONLY | os.O_NONBLOCK))
        t.join(QUICK_S)
        pytest.fail(f"the read did not return within {QUICK_S} s: it blocked on a pipe")
    if "exc" in box:
        raise box["exc"]
    return box.get("out")


def _window(rid="r1", *, start=None, end=None, targets=(VM,), lasts=3600, **kw):
    start = start or _now() - timedelta(minutes=1)
    return {"run_id": rid, "injector": "annatar", "kind": "technique", "experiment": "T1110.001",
            "targets": [t.lower() for t in targets], "start": start.isoformat(),
            "end": end.isoformat() if end else None,
            "expires": (start + timedelta(seconds=lasts)).isoformat(), "destructive": False, **kw}


def _put(directory, window, *, written=None):
    """A window as its injector writes it: at its end, else its start — or at ``written``."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{window['run_id']}.json"
    path.write_text(json.dumps(window))
    at = written or exercise._parse(window.get("end") or window.get("start"))
    os.utime(path, (at.timestamp(), at.timestamp()))
    return path


# ── 1. The windows, read as runs/ is read (V-02) ─────────────────────────────────────────────

def test_a_pipe_among_the_windows_never_blocks_the_watch_and_is_said(capsys):
    """M4520: a FIFO named like a window: the watch's loop (and each decision) would wait on it
    for good. Refused, said once; the other windows still read."""
    d = exercise.exercises_dir()
    _put(d, _window("r1"))
    fifo = d / "r0.json"
    os.mkfifo(fifo)
    assert [w["run_id"] for w in _quick(load_windows, fifo)] == ["r1"]
    assert "r0.json refused: never read: un tube nommé" in capsys.readouterr().out
    _quick(load_windows, fifo)
    assert "r0.json" not in capsys.readouterr().out                   # said once
    assert _quick(lambda: source_of(VM, _now()), fifo) == ("exercise", "r1")


def test_a_window_through_a_link_is_never_followed(tmp_path, capsys):
    """M4520: a link to a window elsewhere (or to any large file of the host): never followed —
    the window it points to marks nothing."""
    elsewhere = _put(tmp_path / "elsewhere", _window("r1"))
    d = exercise.exercises_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "r1.json").symlink_to(elsewhere)
    assert _quick(load_windows) == []
    assert "r1.json refused: never read: un lien, jamais suivi" in capsys.readouterr().out
    assert source_of(VM, _now()) == ("real", "")


def test_a_window_file_too_large_is_refused_never_read_whole(capsys):
    """M4520: a window is under 1 KiB; a file past WINDOW_BYTES is refused, never read into the
    watch's memory."""
    d = exercise.exercises_dir()
    _put(d, _window("r1", padding="x" * WINDOW_BYTES))
    assert _quick(load_windows) == []
    assert f"r1.json refused: never read: plus de {WINDOW_BYTES} octets" in capsys.readouterr().out


def test_close_window_reads_its_window_as_runs_is_read(tmp_path):
    """The injector closing its run: a pipe in its window's place is refused, nothing blocks."""
    fifo = tmp_path / "r9.json"
    os.mkfifo(fifo)
    assert _quick(lambda: exercise.close_window("r9", directory=tmp_path), fifo) is None


# ── 2. A local window's past is bounded by its file's mtime (V-21) ──────────────────────────

def test_an_open_local_window_dated_back_is_refused_by_its_files_mtime(capsys):
    """M4523: written now, dated 110 minutes back (within MAX_DURATION_S): refused — before, only
    its future was bounded, and a reader without the watch's record believed it."""
    now = _now()
    w = _window(start=now - timedelta(minutes=110))
    assert "antedated" in window_refusal(w, now, declared_at=now)
    assert window_refusal(w, now, declared_at=now - timedelta(minutes=110)) == ""   # written then
    assert window_refusal(w, now, declared_at=now - timedelta(minutes=110) + timedelta(seconds=FUTURE_SKEW_S)) == ""
    _put(exercise.exercises_dir(), w, written=now)
    assert _quick(load_windows) == []
    assert "antedated" in capsys.readouterr().out
    assert source_of(VM, now - timedelta(minutes=100)) == ("real", "")


def test_a_closed_window_is_bounded_by_its_end_written_at_its_closure():
    """The injector writes its window again when it closes it: its end, not its start, is what its
    file's mtime bounds — a run of an hour closed now is believed; one closed long before it was
    written is not."""
    now = _now()
    ran = _window(start=now - timedelta(minutes=60), end=now)
    assert window_refusal(ran, now, declared_at=now) == ""
    stale = _window(start=now - timedelta(minutes=60), end=now - timedelta(minutes=50))
    assert "its end is 3000 s before its file was written" in window_refusal(stale, now, declared_at=now)


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """The real layout (SEC18): each injector's directory, and the watch's, under tmp."""
    monkeypatch.delenv("EREGION_EXERCISES_DIR", raising=False)
    monkeypatch.setattr(runs_layout, "ROOT", tmp_path / "runs")
    return tmp_path / "runs"


def test_a_channel_created_in_an_injectors_directory_does_not_lift_the_bound(layout):
    """M4523: only the watch's pull writes channel_created, in the watch's own directory. A window
    in an injector's directory carrying one of its own is local: its file's mtime bounds it."""
    now = _now()
    forged = _window(start=now - timedelta(minutes=110), channel_created=(now - timedelta(minutes=110)).isoformat())
    _put(runs_layout.dir_of("annatar", layout) / "exercises", forged, written=now)
    assert _quick(load_windows) == []
    assert "antedated" in window_refusal(forged, now, declared_at=now, local=True)


def test_a_window_pulled_late_keeps_the_channels_bound(layout):
    """In the watch's own directory, a window pulled from the channel is bounded by its blob's
    creation (SEC5): pulled an hour after it closed, written now, it is still believed."""
    now = _now()
    pulled = _window(start=now - timedelta(minutes=90), end=now - timedelta(minutes=60),
                     channel_created=(now - timedelta(minutes=90)).isoformat())
    _put(runs_layout.dir_of("glorfindel", layout) / "exercises", pulled, written=now)
    assert [w["run_id"] for w in _quick(load_windows)] == ["r1"]


# ── 3. The windows chained on one VM (V-21) ─────────────────────────────────────────────────

def _chain(n, *, every=timedelta(hours=2), runs=timedelta(minutes=110), vm=VM, name="c"):
    first = _now() - every * n
    return [_window(f"{name}{i}", start=first + every * i, end=first + every * i + runs, targets=(vm,),
                    lasts=7200) for i in range(n)]


def test_windows_chained_on_a_vm_mark_it_no_more_past_chain_max(capsys):
    """M4524: each window within MAX_DURATION_S, one after the other: without a bound together, a
    VM stays in exercise for good. Past CHAIN_MAX_S within CHAIN_HORIZON_S, the window that goes
    over, and those after it, mark it no more; the earlier ones keep their mark."""
    ws = _chain(6)
    spans = [(exercise._parse(w["start"]), exercise.last_moment(w)) for w in ws]
    assert chain_refusal(ws[2], VM, ws) == ""
    assert "chained" in chain_refusal(ws[3], VM, ws)          # 8 h 05 covered: past CHAIN_MAX_S
    inside = [s + timedelta(minutes=30) for s, _ in spans]
    assert source_of(VM, inside[1], windows=ws) == ("exercise", "c1")
    assert source_of(VM, inside[4], windows=ws) == ("real", "")
    assert source_of(VM, inside[5], windows=ws, run_id="c5") == ("real", "")   # nor its run_id
    assert covering_runs(VM, inside[5], ws) == []
    assert "window c4 marks" in capsys.readouterr().out
    # Another VM's windows count apart.
    other = _chain(2, vm=OTHER, name="o")
    assert source_of(OTHER, exercise._parse(other[1]["start"]) + timedelta(minutes=30),
                     windows=ws + other) == ("exercise", "o1")


def test_a_campaign_of_short_runs_on_one_vm_stays_within_the_chain():
    """Ten runs of ten minutes, one after the other, each with its grace: well within CHAIN_MAX_S."""
    ws = _chain(10, every=timedelta(minutes=12), runs=timedelta(minutes=10))
    assert all(chain_refusal(w, VM, ws) == "" for w in ws)
    assert CHAIN_MAX_S < CHAIN_HORIZON_S and CHAIN_MAX_S > 2 * (7200 + GRACE_AFTER_S)


def test_windows_older_than_the_horizon_no_longer_count():
    """The chain is counted over CHAIN_HORIZON_S: a VM exercised a day ago may be again."""
    ws = _chain(4)
    later = _window("late", start=_now() + timedelta(seconds=CHAIN_HORIZON_S), lasts=3600)
    assert "chained" in chain_refusal(ws[3], VM, ws)
    assert chain_refusal(later, VM, ws + [later]) == ""


# ── 4. The signals `glorfindel respond` reads (V-02) ────────────────────────────────────────

def _signal_line() -> str:
    return json.dumps({"signal_id": "s1", "ttp": "T1110.001", "event": "attack_started", "provider": "azure",
                       "resource_type": "vm", "resource_id": VM, "severity": "high",
                       "timestamp": _now().isoformat()})


def test_the_signals_are_read_as_runs_is_read(tmp_path):
    """M4521: a pipe, a link, a file too large: Refused at once, never read."""
    from glorfindel.signals import load_signals
    fifo = tmp_path / "r1_signals.jsonl"
    os.mkfifo(fifo)
    with pytest.raises(Refused, match="un tube nommé"):
        _quick(lambda: load_signals(fifo), fifo)
    real = tmp_path / "real.jsonl"
    real.write_text(_signal_line() + "\n")
    assert len(load_signals(real)) == 1
    link = tmp_path / "link_signals.jsonl"
    link.symlink_to(real)
    with pytest.raises(Refused, match="un lien"):
        _quick(lambda: load_signals(link))
    big = tmp_path / "big_signals.jsonl"
    with open(big, "wb") as f:
        f.truncate(FILE_BYTES + 1)                         # sparse: nothing written
    with pytest.raises(Refused, match="plus de"):
        _quick(lambda: load_signals(big))


def test_respond_says_a_refused_signals_file_and_stops(tmp_path):
    """M4521: `glorfindel respond` on a pipe says it, exits 1, never waits."""
    from glorfindel.cli import cli
    fifo = tmp_path / "r1_signals.jsonl"
    os.mkfifo(fifo)
    result = _quick(lambda: CliRunner().invoke(cli, ["respond", str(fifo), "--dry-run"]), fifo)
    assert result.exit_code == 1
    assert "refusé : un tube nommé — jamais lu" in result.output


# ── 5. A campaign's manifest (V-02) ─────────────────────────────────────────────────────────

def _campaign(tmp_path, *, how):
    cdir = tmp_path / "runs" / "annatar" / "campaigns" / "20260630T200000Z"
    cdir.mkdir(parents=True)
    target = cdir / "manifest.json"
    if how == "fifo":
        os.mkfifo(target)
    elif how == "link":
        elsewhere = tmp_path / "elsewhere.json"
        elsewhere.write_text(json.dumps({"campaign_id": "20260630T200000Z"}))
        target.symlink_to(elsewhere)
    else:
        with open(target, "wb") as f:
            f.truncate(2 * 1024 * 1024)
    return cdir, target


@pytest.mark.parametrize("how,why", [("fifo", "un tube nommé"), ("link", "un lien"), ("big", "plus de")])
def test_a_campaigns_manifest_is_read_as_runs_is_read(tmp_path, how, why):
    """M4522: Annatar's runner, its CLI and Glorfindel's replay read the manifest bounded."""
    from annatar.campaign.manifest import CampaignManifest
    from glorfindel import campaign_replay
    cdir, target = _campaign(tmp_path, how=how)
    with pytest.raises(Refused, match=why):
        _quick(lambda: CampaignManifest.load(cdir), target)
    # The replay: a pipe is no manifest (``find_campaign``: not a file), the others refused.
    with pytest.raises(FileNotFoundError if how == "fifo" else Refused):
        _quick(lambda: campaign_replay.replay_campaign(cdir.name, runs_dir=tmp_path / "runs", write=False),
               target)


def test_the_clis_say_a_refused_manifest(tmp_path):
    """M4522: `glorfindel replay-campaign` and `annatar campaign list` say it, never wait."""
    from annatar.cli import cli as annatar_cli
    from glorfindel.cli import cli as glorfindel_cli
    cdir, target = _campaign(tmp_path / "linked", how="link")
    out = _quick(lambda: CliRunner().invoke(
        glorfindel_cli, ["replay-campaign", cdir.name, "--runs-dir", str(tmp_path / "linked" / "runs"), "--dry-run"]))
    assert out.exit_code == 1 and "refused" in out.output and "un lien" in out.output
    cdir, target = _campaign(tmp_path, how="fifo")
    out = _quick(lambda: CliRunner().invoke(
        annatar_cli, ["campaign", "list", "--runs-dir", str(tmp_path / "runs" / "annatar")]), target)
    assert out.exit_code == 0 and "manifest refused" in out.output
    out = _quick(lambda: CliRunner().invoke(
        annatar_cli, ["campaign", "show", cdir.name, "--runs-dir", str(tmp_path / "runs" / "annatar")]), target)
    assert out.exit_code == 1 and "Manifest refused" in out.output
