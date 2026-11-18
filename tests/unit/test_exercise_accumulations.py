"""SEC-A1b (#642): what accumulates around the exercise windows is bounded — the watch's record of
the windows it saw, the directory the pull writes, the files of a writer the watch follows — and
the cut past a bound is fair and said once. And the guards next to them: the local heartbeat read
as runs/ is read, the injectors' own guard held before a window marks a card, the kill that sees
every window of the channel, a campaign's manifest read bounded, the console's chain without the
windows it refused.

Mutants M5781–M5800 (scripts/mutants/SEC-A1b.py) are measured here. No Azure call: the channel is
in memory (tests/unit/fake_container.py), the tags come from a fake ``get``. Every read that could
block on a pipe returns within seconds (``_quick``), never hangs the suite.
"""
from __future__ import annotations

import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from eregion_core import exercise, runs_layout
from eregion_core import exercise_channel as channel
from eregion_core.channel_reader import ChannelReader, Refused
from eregion_core.exercise import load_windows
from tests.unit.fake_container import CRED, URL, FakeContainer
from tests.unit.test_bounded_reads import _quick

VM = "/subscriptions/s/resourcegroups/rg-celebrimbor/providers/microsoft.compute/virtualmachines/vm-celebrimbor-gondolin"
PROD = VM.replace("rg-celebrimbor", "rg-prod")
ELSEWHERE = VM.replace("/subscriptions/s/", "/subscriptions/other/")
KILL = Path(__file__).resolve().parents[2] / "infra" / "orodruin" / "kill.py"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _window(rid="r1", *, start=None, end=None, targets=(VM,), lasts=3600, injector="annatar",
            kind="technique", **kw):
    start = start or _now() - timedelta(minutes=1)
    return {"run_id": rid, "injector": injector, "kind": kind, "experiment": "T1110.001",
            "targets": [t.lower() for t in targets], "start": start.isoformat(),
            "end": end.isoformat() if end else None,
            "expires": (start + timedelta(seconds=lasts)).isoformat(), "destructive": False, **kw}


def _put(directory, window, *, written=None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{window['run_id']}.json"
    path.write_text(json.dumps(window))
    at = written or exercise._parse(window.get("end") or window.get("start"))
    os.utime(path, (at.timestamp(), at.timestamp()))
    return path


@pytest.fixture
def record(tmp_path):
    return tmp_path / "glorfindel" / "exercise_seen.json"


# ── 1. The watch's record (#642 point 1) ────────────────────────────────────────────────

def test_a_window_names_a_bounded_number_of_bounded_targets():
    """M5781: a window of 64 KiB of targets made an entry of 64 KiB in the watch's record, kept a
    week. At most MAX_TARGETS targets, each at most TARGET_CHARS characters — else refused."""
    many = [VM.replace("gondolin", f"vm{i}") for i in range(exercise.MAX_TARGETS)]
    assert exercise.window_refusal(_window(targets=many)) == ""
    assert "MAX_TARGETS" in exercise.window_refusal(_window(targets=[*many, VM]))
    assert "MAX_TARGETS" in exercise.window_refusal(_window(targets=[VM + "x" * exercise.TARGET_CHARS]))


def test_a_run_id_is_bounded_and_every_writer_keeps_its_share():
    """The run_id bounds an entry of the record (RUN_ID_CHARS); the record holds every writer's
    full share of the largest entries, so one writer never takes another's room."""
    assert exercise.window_refusal(_window("r" * exercise.RUN_ID_CHARS)) == ""
    assert "RUN_ID_CHARS" in exercise.window_refusal(_window("r" * (exercise.RUN_ID_CHARS + 1)))
    now = _now().isoformat()
    largest = {"r" * exercise.RUN_ID_CHARS: {
        "seen": now, "channel": True, "fields": "f" * 64, "end": now, "writer": "glorfindel",
        "start": now, "expires": now, "target_keys": ["k" * 16] * exercise.MAX_TARGETS}}
    assert len(json.dumps(largest, separators=(",", ":"))) + 1 <= exercise.ENTRY_BYTES
    assert exercise.RECORD_BYTES >= exercise.RECORD_WRITERS * exercise.RECORD_PER_WRITER * exercise.ENTRY_BYTES
    assert exercise.RECORD_WRITERS >= len(runs_layout.INJECTORS) + 2     # the watch's own, and ""


def test_a_pulled_window_starts_within_its_blobs_creation():
    """A window is written when it opens: pulled, it may start no more than FUTURE_SKEW_S after its
    blob was created — what lets the kill leave an old blob unread."""
    now = _now()
    w = _window(start=now)
    assert exercise.window_refusal({**w, "channel_created": now.isoformat()}) == ""
    late = (now - timedelta(seconds=exercise.FUTURE_SKEW_S + 60)).isoformat()
    assert "after it was declared" in exercise.window_refusal({**w, "channel_created": late})


def test_the_record_keeps_digests_and_dates_never_what_the_window_wrote(tmp_path, record):
    """M5782: an entry keeps a digest of each target and dates written again in one spelling —
    never the targets themselves, never a date of 1 000 digits."""
    d = tmp_path / "x"
    now = _now()
    start = now - timedelta(minutes=1)
    w = _window(start=start)
    w["start"] = start.strftime("%Y-%m-%dT%H:%M:%S.") + "0" * 900 + "+00:00"   # one long spelling
    _put(d, w, written=start)
    assert [x["run_id"] for x in load_windows(d, now=now, seen=record)] == ["r1"]
    text = record.read_text()
    assert "gondolin" not in text and "0" * 50 not in text
    entry = json.loads(text)["r1"]
    assert entry["target_keys"] == [exercise._key(VM)] and entry["start"] == start.isoformat()
    # The chain counts the record's spans by those digests.
    assert exercise._record_spans["r1"][0] == frozenset({exercise._key(VM)})


def test_a_record_of_before_keeps_counting_its_targets_digested(tmp_path, record):
    """A record written before SEC-A1b kept the targets themselves: digested at the next read."""
    d = tmp_path / "x"
    now = _now()
    old = {"seen": (now - timedelta(hours=3)).isoformat(), "fields": "f", "end": None,
           "start": (now - timedelta(hours=3)).isoformat(),
           "expires": (now - timedelta(hours=1)).isoformat(), "targets": [VM]}
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"old": old}))
    _put(d, _window(start=now - timedelta(minutes=1)), written=now - timedelta(minutes=1))
    load_windows(d, now=now, seen=record)
    entry = json.loads(record.read_text())["old"]
    assert "targets" not in entry and entry["target_keys"] == [exercise._key(VM)]
    assert "old" in exercise._record_spans


def test_the_pull_writes_down_only_a_window(record):
    """M5783: ``note_pulled`` wrote down any blob of JSON with a run_id — a blob of 1 MiB, a whole
    entry of 0.9 MiB. Only a window the watch believes, with the date of its blob."""
    exercise.note_pulled(record, {"run_id": "junk", "padding": "x" * 4096})
    exercise.note_pulled(record, {**_window("r2"), "targets": "not a list",
                                  "channel_created": _now().isoformat()})
    exercise.note_pulled(record, _window("r3"))                       # no channel_created
    assert not record.exists() or json.loads(record.read_text()) == {}
    exercise.note_pulled(record, {**_window("r1"), "channel_created": _now().isoformat()})
    entry = json.loads(record.read_text())["r1"]
    assert entry["channel"] is True and entry["writer"] == runs_layout.GLORFINDEL


def test_each_writer_has_at_most_its_share_of_the_record(tmp_path, record, monkeypatch, capsys):
    """M5784: past RECORD_PER_WRITER entries of one writer, a window not written down is not
    believed (fail closed: its cycles fall toward real); another writer keeps its room."""
    monkeypatch.setattr(exercise, "RECORD_PER_WRITER", 2)
    d = tmp_path / "x"
    now = _now()
    for i in range(3):
        _put(d, _window(f"r{i}", start=now - timedelta(minutes=1)), written=now - timedelta(minutes=1))
    assert [w["run_id"] for w in load_windows(d, now=now, seen=record)] == ["r0", "r1"]
    assert "RECORD_PER_WRITER" in capsys.readouterr().out
    assert sorted(json.loads(record.read_text())) == ["r0", "r1"]
    # The channel's windows are another writer: their room is their own.
    exercise.note_pulled(record, {**_window("p1"), "channel_created": now.isoformat()})
    assert "p1" in json.loads(record.read_text())


def test_the_record_is_read_as_runs_is_read(tmp_path, record):
    """M5785: the record was read by its name — a pipe in its place held the watch's loop. Read by
    the bounded reader: refused at once, every window it should bound not believed."""
    d = tmp_path / "x"
    now = _now()
    _put(d, _window(start=now - timedelta(minutes=1)), written=now - timedelta(minutes=1))
    record.parent.mkdir(parents=True)
    os.mkfifo(record)
    assert _quick(lambda: load_windows(d, now=now, seen=record), record) == []
    assert _quick(lambda: exercise.noted_pulled(record), record) == set()


def test_a_record_past_its_bound_is_never_written(tmp_path, record, monkeypatch):
    """The record is at most RECORD_BYTES: a write past it is refused, its windows not believed."""
    monkeypatch.setattr(exercise, "RECORD_BYTES", 100)
    d = tmp_path / "x"
    now = _now()
    _put(d, _window(start=now - timedelta(minutes=1)), written=now - timedelta(minutes=1))
    assert load_windows(d, now=now, seen=record) == []
    assert not record.exists()


# ── 2. The pulled windows (SEC-A1b) ────────────────────────────────────────────────────────────

def _pull(c, d, **kw):
    return channel.pull(d, channel=URL, credential=CRED, get=c.get, **kw)


def test_the_pull_refuses_a_blob_that_is_no_window(tmp_path, record):
    """M5786: a blob that is no window — not JSON, JSON of another shape, a run_id not its name —
    was written to the watch's directory and never purged. Refused at the pull, said, and not
    downloaded again."""
    c, d = FakeContainer(), tmp_path / "own"
    c.put(f"{URL}/junk.json", data=b"not json " * 100)
    c.put(f"{URL}/shape.json", data=json.dumps({"run_id": "shape", "start": "x"}).encode())
    c.put(f"{URL}/name.json", data=json.dumps(_window("other")).encode())
    c.put(f"{URL}/r1.json", data=json.dumps(_window("r1")).encode())
    said: list[str] = []
    assert _pull(c, d, say=said.append, seen=record) == 1
    assert sorted(os.listdir(d)) == ["r1.json"]
    assert sum("refused, not pulled" in s for s in said) == 3
    gets = len(c.gets)
    _pull(c, d, say=said.append, seen=record)
    assert len(c.gets) == gets                          # refused already: not downloaded again


def test_the_pull_refuses_a_blob_past_window_bytes(tmp_path):
    """M5787: a window is under 1 KiB; a blob of 1 MiB was pulled whole. Past WINDOW_BYTES, not
    pulled."""
    c, d = FakeContainer(), tmp_path / "own"
    big = _window("r1", padding="x" * (exercise.WINDOW_BYTES + 1))
    c.put(f"{URL}/r1.json", data=json.dumps(big).encode())
    said: list[str] = []
    assert _pull(c, d, say=said.append) == 0
    assert not (d / "r1.json").exists() and any("more than" in s for s in said)


def test_the_watch_directory_is_bounded_its_closures_still_come(tmp_path, monkeypatch):
    """M5788: past MAX_PULLED_FILES files (or MAX_PULLED_BYTES) in the watch's directory, no new
    window is pulled, said; the closure of one pulled already still comes."""
    monkeypatch.setattr(channel, "MAX_PULLED_FILES", 2)
    c, d = FakeContainer(), tmp_path / "own"
    windows = [_window(f"r{i}") for i in range(3)]
    for w in windows:
        c.put(f"{URL}/{w['run_id']}.json", data=json.dumps(w).encode())
    said: list[str] = []
    assert _pull(c, d, say=said.append) == 2
    assert sorted(os.listdir(d)) == ["r0.json", "r1.json"]
    assert sum("no new window pulled" in s for s in said) == 1
    os.utime(d / "r0.json", (0, 0))                     # older than its closure
    c.put(f"{URL}/r0.json", data=json.dumps({**windows[0], "end": _now().isoformat()}).encode())
    assert _pull(c, d, say=said.append) == 1
    assert json.loads((d / "r0.json").read_text())["end"]
    # Said once while it lasts — not at every pull (every 30 s).
    assert sum("no new window pulled" in s for s in said) == 1
    _pull(c, d, say=said.append)
    assert sum("no new window pulled" in s for s in said) == 1
    # Room again (a window purged), then full again: said once more.
    (d / "r1.json").unlink()
    c.put(f"{URL}/r3.json", data=json.dumps(_window("r3")).encode())
    c.put(f"{URL}/r4.json", data=json.dumps(_window("r4")).encode())
    _pull(c, d, say=said.append)
    assert sum("no new window pulled" in s for s in said) == 2


def test_what_is_no_window_in_the_watch_directory_is_purged(capsys):
    """M5789: a file of the watch's own directory that is no window (not JSON, too large, a pipe)
    was refused at every read and stayed for good: purged as a window is, its tombstone left."""
    d = exercise.exercises_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "junk.json").write_text("not json")
    (d / "list.json").write_text("[]")
    os.mkfifo(d / "pipe.json")
    _put(d, _window("r1"))
    assert [w["run_id"] for w in _quick(load_windows, d / "pipe.json")] == ["r1"]
    for name in ("junk.json", "list.json", "pipe.json"):
        tomb = json.loads((d / name).read_text())
        assert tomb["purged_at"] and tomb["run_id"] == name[:-5], name
    assert [w["run_id"] for w in load_windows()] == ["r1"]


def test_a_tombstone_goes_once_purge_after_s_old():
    """A tombstone kept the channel's copy from coming back; PURGE_AFTER_S after the purge, the blob
    is gone from the channel (9 days of retention), and the tombstone too."""
    d = exercise.exercises_dir()
    now = _now()
    old = now - timedelta(seconds=exercise.PURGE_AFTER_S + 60)
    _put(d, {"run_id": "old", "purged_at": old.isoformat()}, written=old)
    _put(d, {"run_id": "new", "purged_at": now.isoformat()}, written=now)
    load_windows(now=now)
    assert sorted(os.listdir(d)) == ["new.json"]


# ── 3. The files the watch follows (SEC-A1b) ───────────────────────────────────────────────────

def _signals(d, name, lines=1):
    path = d / f"{name}_signals.jsonl"
    with open(path, "a") as f:
        for i in range(lines):
            f.write(json.dumps({"n": i, "name": name}) + "\n")
    return path


def test_the_reader_follows_the_newest_files_only(tmp_path, monkeypatch):
    """M5790: the reader kept every name it ever saw, and looked at each one at every poll. At most
    TRACKED_MAX of a writer's files, the newest; the others said once, a name gone forgotten."""
    monkeypatch.setattr("eregion_core.channel_reader.TRACKED_MAX", 2)
    said: list[str] = []
    reader = ChannelReader(tmp_path, lambda text, kind: said.append(text))
    names = [f"2026111{i}T000000Z" for i in range(4)]
    for n in names:
        _signals(tmp_path, n)
    got = reader.poll()
    assert sorted(p.name for p in reader.offsets) == [f"{n}_signals.jsonl" for n in names[2:]]
    assert {line for _, line in got} == {json.dumps({"n": 0, "name": n}) for n in names[2:]}
    assert sum("plus suivis" in s for s in said) == 1
    reader.poll()
    assert sum("plus suivis" in s for s in said) == 1    # said once while it lasts
    (tmp_path / f"{names[3]}_signals.jsonl").unlink()
    reader.poll()
    assert tmp_path / f"{names[3]}_signals.jsonl" not in reader.offsets


def test_a_file_back_among_the_newest_is_followed_from_its_end(tmp_path, monkeypatch):
    """M5800: a file no longer followed that comes back among the newest (the newer ones deleted)
    is followed from its end — what it held is never replayed as new lines."""
    monkeypatch.setattr("eregion_core.channel_reader.TRACKED_MAX", 1)
    reader = ChannelReader(tmp_path, lambda text, kind: None)
    old = _signals(tmp_path, "20261110T000000Z", lines=3)
    reader.track_existing()
    new = _signals(tmp_path, "20261111T000000Z")
    reader.poll()
    assert old not in reader.offsets and new in reader.offsets
    new.unlink()
    assert reader.poll() == []                           # its three old lines: not replayed
    assert reader.offsets[old] == old.stat().st_size
    with open(old, "a") as f:
        f.write('{"n": "fresh"}\n')
    assert [line for _, line in reader.poll()] == ['{"n": "fresh"}']


# ── 4. The cut at MAX_WINDOW_FILES (#642 point 3) ───────────────────────────────────────────

@pytest.fixture
def layout(tmp_path, monkeypatch):
    """runs/ as on a host (SEC18): each injector's directory, and the watch's."""
    monkeypatch.delenv("EREGION_EXERCISES_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    return {w: runs_layout.dir_of(w) / "exercises" for w in (*runs_layout.INJECTORS, runs_layout.GLORFINDEL)}


def test_each_directory_takes_its_turn_in_the_cut(layout, monkeypatch):
    """M5791: the cut followed the paths' order — a flood in Annatar's directory pushed out
    Gothmog's windows and the watch's. Each directory its turn, the watch's first, the newest
    first."""
    monkeypatch.setattr(exercise, "MAX_WINDOW_FILES", 3)
    for i in range(5):
        _put(layout["annatar"], _window(f"a{i}"))
    _put(layout["gothmog"], _window("g1", injector="gothmog", kind="fault"))
    ids = {w["run_id"] for w in load_windows()}
    assert ids == {"a4", "a3", "g1"}
    _put(layout["glorfindel"], _window("w1"))
    assert {w["run_id"] for w in load_windows()} == {"w1", "a4", "g1"}


def test_the_cut_is_said_once_while_the_flood_lasts(layout, monkeypatch, capsys):
    """M5792: the cut was said again at each read whose count changed — a growing flood, a line a
    minute. Said once while it lasts, again once it ended and came back."""
    monkeypatch.setattr(exercise, "MAX_WINDOW_FILES", 2)
    for i in range(3):
        _put(layout["annatar"], _window(f"a{i}"))
    load_windows()
    assert capsys.readouterr().out.count("past MAX_WINDOW_FILES") == 1
    _put(layout["annatar"], _window("a3"))
    load_windows()
    assert "past MAX_WINDOW_FILES" not in capsys.readouterr().out
    for i in range(3):
        (layout["annatar"] / f"a{i}.json").unlink()
    load_windows()
    _put(layout["annatar"], _window("a5"))
    _put(layout["annatar"], _window("a6"))
    load_windows()
    assert capsys.readouterr().out.count("past MAX_WINDOW_FILES") == 1


# ── 5. The console's chain (#642 point 4) ───────────────────────────────────────────────────

def test_a_window_the_reader_refused_never_chains_another():
    """M5793: the console counted in the chain the windows it refused itself — a run of refused
    windows took the next believed one out of the exercise."""
    now = _now()
    refused = [{**_window(f"x{i}", start=now - timedelta(hours=2 * (6 - i)), lasts=7200),
                "refusal": "antedated"} for i in range(6)]
    fresh = _window("fresh", start=now - timedelta(minutes=1))
    assert exercise.covering_runs(VM, now, [*refused, fresh]) == ["fresh"]
    believed = [{k: v for k, v in w.items() if k != "refusal"} for w in refused]
    assert "fresh" not in exercise.covering_runs(VM, now, [*believed, fresh])


# ── 6. A campaign's manifest (KS1) ──────────────────────────────────────────────────────────

def test_a_campaign_manifest_is_read_as_runs_is_read(tmp_path):
    """M5794: the manifest a campaign publishes to Imladris was read by its name: a pipe in its
    place held the run. Refused at once."""
    cdir = tmp_path / "runs" / "annatar" / "campaigns" / "C1"
    cdir.mkdir(parents=True)
    os.mkfifo(cdir / "manifest.json")
    with pytest.raises(Refused):
        _quick(lambda: channel.campaign_blobs(cdir), cdir / "manifest.json")
    with pytest.raises(Refused):
        _quick(lambda: channel.unpublished_runs(cdir), cdir / "manifest.json")


# ── 7. The local heartbeat (SEC-A1b) ───────────────────────────────────────────────────────────

def test_the_local_heartbeat_is_read_as_runs_is_read(tmp_path, monkeypatch):
    """M5795: the heartbeat was read by its name: a pipe in its place held a run between two of
    its steps. Refused at once — « unreadable », no watch."""
    from eregion_core import watch_gate
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    beat = tmp_path / "home" / ".glorfindel" / "watch_heartbeat"
    beat.parent.mkdir(parents=True)
    os.mkfifo(beat)
    got = _quick(watch_gate.local_beat, beat)
    assert got.at is None and "unreadable" in got.why
    os.unlink(beat)
    beat.write_text("x" * (watch_gate.BEAT_BYTES + 1))
    assert "unreadable" in watch_gate.local_beat().why


def test_the_console_and_the_bot_mount_the_injectors_heartbeat_read_only():
    """SEC-A1b: the console and the bot mount ~/.glorfindel in writing — never the directory of the
    heartbeat the injectors read, which only the watch writes; Imladris makes it before compose."""
    import yaml
    root = Path(__file__).resolve().parents[2]
    services = yaml.safe_load((root / "docker-compose.yml").read_text())["services"]
    ro = "${HOME}/.glorfindel/injectors:/root/.glorfindel/injectors:ro"
    for name in ("war-room", "bot"):
        assert ro in services[name]["volumes"], name
    assert ro not in services["watch"]["volumes"]
    assert 'mkdir -p "$HOME/.glorfindel/injectors"' in (root / "infra/glorfindel-host/deploy.sh").read_text()


# ── 8. The marking of a card (SEC-A1b) ─────────────────────────────────────────────────────────

class _Zones:
    def __init__(self, zone):
        self._zone = zone

    def __call__(self, rid):
        return True

    def zone(self, rid):
        return self._zone


@pytest.mark.parametrize("zone", ["Production", "production ", "prod", "PROD", ""])
def test_a_zone_not_written_exactly_marks_nothing(zone):
    """M5796: only the value « production » exactly was held to the production rule — a VM tagged
    « Production » took a fault's mark. The injectors' check_zone: a zone exactly one of
    bench, twin, production, or nothing is marked."""
    now = _now()
    for change in ({"destructive": True}, {"kind": "fault"}, {}):
        w = {**_window(start=now - timedelta(minutes=1)), **change}
        assert exercise.covering_runs(VM, now, [w], enrolled=_Zones(zone)) == [], change
    assert exercise.covering_runs(VM, now, [{**_window(start=now - timedelta(minutes=1)),
                                             "kind": "fault"}], enrolled=_Zones("twin")) == ["r1"]


TWIN = VM.replace("rg-celebrimbor", "rg-twin").replace("gondolin", "twin1")


def _tags_get(url, headers=None, params=None, timeout=None):
    """The tags of each VM and of its group: enrolled, in the zone its group says."""
    zone = "production" if "rg-prod" in url else "twin" if "rg-twin" in url else "bench"
    return SimpleNamespace(ok=True, status_code=200,
                           json=lambda: {"tags": {"eregion-target": "celebrimbor", "eregion-zone": zone}})


def _marks(check, target, **change):
    now = _now()
    w = {**_window(start=now - timedelta(minutes=1), targets=[target]), **change}
    return exercise.covering_runs(target, now, [w], enrolled=check) == ["r1"]


@pytest.fixture
def tags(monkeypatch):
    from eregion_core.inscription import Scope, TagEnrollment
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "s")
    check = TagEnrollment(credential=CRED, get=_tags_get)
    assert check.scope == Scope(sandbox="celebrimbor", subscription_id="s")
    return check


def test_the_sentinel_in_production_is_marked_by_a_non_destructive_technique_only(tags):
    """Decision of 18/11: the marking follows the injectors' guard. A technique declared
    non-destructive is held as Annatar holds its target — its subscription and its group —, the
    tags decide the rest: the sentinel, in zone production outside the bench, is marked (O0)."""
    assert _marks(tags, PROD)
    assert not _marks(tags, PROD, destructive=True)
    assert not _marks(tags, PROD, destructive=None)
    assert not _marks(tags, PROD, kind="fault")


def test_a_twin_outside_the_bench_is_marked_by_its_tags(tags):
    """A twin outside rg-celebrimbor*: a non-destructive technique marks it, by its tags."""
    assert _marks(tags, TWIN)
    assert tags(TWIN) is True and tags.zone(TWIN) == "twin"


def test_a_fault_or_a_destructive_gesture_marks_the_bench_only(tags):
    """M5797: a fault, or a gesture nobody declared non-destructive, keeps the bench's perimeter —
    its subscription, its groups —, as Gothmog and a destructive run are held: a twin outside the
    bench, a VM of another subscription, tagged by mistake, are never marked by them."""
    assert _marks(tags, VM, kind="fault") and _marks(tags, VM, destructive=True)
    for target in (TWIN, ELSEWHERE):
        assert not _marks(tags, target, kind="fault"), target
        assert not _marks(tags, target, destructive=True), target
        assert tags(target) is True                     # enrolled by its tags all the same
    exercise.set_enrollment_check(tags)
    now = _now()
    w = {**_window(start=now - timedelta(minutes=1), targets=[TWIN]), "kind": "fault"}
    assert exercise.source_of(TWIN, now, run_id="r1", windows=[w]) == ("real", "")
    # A technique declared non-destructive: the subscription and the group of its target.
    assert _marks(tags, ELSEWHERE)


def test_a_zone_written_otherwise_marks_nothing_outside_the_bench(tags, monkeypatch):
    """Whatever the branch: a zone not written exactly marks nothing."""
    monkeypatch.setattr(tags, "zone", lambda rid: "Production")
    for change in ({}, {"kind": "fault"}, {"destructive": True}):
        assert not _marks(tags, PROD, **change), change
        assert not _marks(tags, VM, **change), change


def test_a_perimeter_names_its_subscription(tags):
    """Without a subscription, the bench's perimeter names none: nothing is marked by a fault."""
    from eregion_core.inscription import Scope, TagEnrollment
    assert TagEnrollment(credential=CRED, get=_tags_get, scope=Scope()).perimeter(VM)
    assert TagEnrollment(credential=CRED, get=_tags_get, scope=Scope()).perimeter(VM, bench=False) == ""


# ── 9. The kill sees every window (SEC-A1b) ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def kill_script():
    spec = importlib.util.spec_from_file_location("orodruin_kill_a1b", KILL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _close(kill_script, c, said):
    *_, close = kill_script.steps("oid-1", VM, subscription="s", channel=URL, run=lambda a: "[]",
                                  credential=CRED, get=c.get, put=c.put, say=said.append,
                                  inflight=[], now=_now())
    return close


def test_the_kill_closes_a_window_listed_past_a_pulls_bounds(kill_script, monkeypatch):
    """M5798: the close step made one pull — MAX_BLOBS names, MAX_DOWNLOADS blobs, by name — and
    said « no exercise window open » with the open one listed after them. It reads the whole
    channel, page after page."""
    monkeypatch.setattr(channel, "MAX_BLOBS", 4)
    monkeypatch.setattr(channel, "MAX_DOWNLOADS", 3)
    c = FakeContainer(page_size=3)
    now = _now()
    for i in range(8):
        closed = _window(f"a{i}", start=now - timedelta(minutes=30), end=now - timedelta(minutes=20))
        c.put(f"{URL}/a{i}.json", data=json.dumps(closed).encode())
    c.put(f"{URL}/z9.json", data=json.dumps(_window("z9", start=now - timedelta(minutes=5))).encode())
    said: list[str] = []
    _close(kill_script, c, said)()
    assert json.loads(c.body("z9.json"))["closed_by"] == "orodruin-kill"
    assert not any("no exercise window open" in s for s in said)


def test_the_kill_fails_when_the_channel_cannot_be_listed_whole(kill_script, monkeypatch):
    """M5799: past what the kill may list (KILL_MAX_BLOBS), the step fails — never « no window
    open » from a listing cut."""
    monkeypatch.setattr(channel, "KILL_MAX_BLOBS", 3)
    c = FakeContainer(page_size=2)
    now = _now()
    for i in range(5):
        closed = _window(f"a{i}", start=now - timedelta(minutes=30), end=now - timedelta(minutes=20))
        c.put(f"{URL}/a{i}.json", data=json.dumps(closed).encode())
    said: list[str] = []
    with pytest.raises(RuntimeError, match="not all seen"):
        _close(kill_script, c, said)()
    assert not any("no exercise window open" in s for s in said)


def test_the_kill_leaves_unread_only_a_blob_that_can_no_longer_be_open(kill_script):
    """A blob created more than MAX_DURATION_S + FUTURE_SKEW_S (and the margin) ago carries no
    window open now: not downloaded. Every other one is — exhaustive on what can be open."""
    c = FakeContainer()
    now = _now()
    old = now - timedelta(seconds=exercise.MAX_DURATION_S + exercise.FUTURE_SKEW_S
                          + channel.KILL_MARGIN_S + 60)
    edge = now - timedelta(seconds=exercise.MAX_DURATION_S + exercise.FUTURE_SKEW_S)
    c.put(f"{URL}/old.json", data=json.dumps(_window("old", start=old, lasts=7200)).encode())
    c.put(f"{URL}/edge.json", data=json.dumps(_window("edge", start=edge, lasts=7200)).encode())
    c.put(f"{URL}/open.json", data=json.dumps(_window("open", start=now - timedelta(minutes=5))).encode())
    said: list[str] = []
    _close(kill_script, c, said)()
    assert "old.json" not in c.gets and {"edge.json", "open.json"} <= set(c.gets)
    assert json.loads(c.body("open.json"))["closed_by"] == "orodruin-kill"


def test_a_window_gone_between_the_listing_and_its_download_fails_closed(kill_script, monkeypatch):
    """A blob listed, then gone before its download (404): the step fails — run the kill again."""
    c = FakeContainer()
    c.put(f"{URL}/a1.json", data=json.dumps(_window("a1")).encode())
    real_get = c.get

    def get(url, headers=None, params=None, timeout=None, stream=None):
        if not params:
            c.blobs.pop(url.rsplit("/", 1)[1], None)        # deleted after the listing
        return real_get(url, headers=headers, params=params, timeout=timeout)
    c.get = get
    with pytest.raises(RuntimeError, match="HTTP 404"):
        _close(kill_script, c, [])()


def test_the_kill_fails_on_a_window_it_cannot_download(kill_script):
    """A window the kill cannot download is unseen: the step fails."""
    c = FakeContainer()
    c.put(f"{URL}/a1.json", data=json.dumps(_window("a1")).encode())
    c.refused.add("a1.json")
    with pytest.raises(RuntimeError, match="not every window"):
        _close(kill_script, c, [])()
