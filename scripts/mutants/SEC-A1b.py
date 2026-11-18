"""SEC-A1b (#642): what accumulates around the exercise windows is bounded — the watch's record of
the windows it saw, the directory the pull writes, the files of a writer the watch follows —, the
cut past a bound fair and said once; the local heartbeat read as runs/ is read, the injectors'
own guard held before a window marks a card, the kill that sees every window of the channel, a
campaign's manifest read bounded, the console's chain without the windows it refused.
M5781–M5800.

Each caught by tests/unit/test_exercise_accumulations.py: a read that blocks on a pipe fails there
within seconds, never hangs the run.
"""
EXERCISE = "eregion_core/exercise.py"
CHANNEL = "eregion_core/exercise_channel.py"
READER = "eregion_core/channel_reader.py"
GATE = "eregion_core/watch_gate.py"
_TESTS = "tests/unit/test_exercise_accumulations.py"

MUTANTS = [
    ("M5781", "a window names targets without a bound: its entry in the watch's record as large as it (SEC-A1b)",
     EXERCISE,
     "    if len(targets) > MAX_TARGETS or any(len(t) > TARGET_CHARS for t in targets):\n",
     "    if False:\n"),
    ("M5782", "the watch's record keeps the targets themselves, not their digests (SEC-A1b)",
     EXERCISE,
     '            "target_keys": [_key(t) for t in window.get("targets") or [] if isinstance(t, str)]}\n',
     '            "target_keys": [t for t in window.get("targets") or [] if isinstance(t, str)]}\n'),
    ("M5783", "the pull writes down any blob with a run_id in the watch's record (SEC-A1b)",
     EXERCISE,
     "    if window_refusal(window) or _iso(window.get(CHANNEL_CREATED)) is None:\n",
     "    if False:\n"),
    ("M5784", "a writer fills the watch's record without a share of its own (SEC-A1b)",
     EXERCISE,
     "                if held.get(writer, 0) >= RECORD_PER_WRITER:",
     "                if False:"),
    ("M5785", "the watch's record read by its name: a pipe in its place holds the watch's loop (SEC-A1b)",
     EXERCISE,
     "        data, _ = read_regular(registry, RECORD_BYTES)\n",
     "        data = registry.read_bytes()\n"),
    ("M5786", "the pull writes a blob that is no window to the watch's directory (SEC-A1b)",
     CHANNEL,
     "        if why := window_shape_refusal(name, shaped):\n",
     "        if False:\n"),
    ("M5787", "the pull downloads a window of 1 MiB whole (SEC-A1b)",
     CHANNEL,
     '            r, body = fetch(get, f"{url}/{name}", headers, limit=WINDOW_BYTES, what=f"window {name}",\n',
     '            r, body = fetch(get, f"{url}/{name}", headers, what=f"window {name}",\n'),
    ("M5788", "the watch's directory of pulled windows grows without a bound (SEC-A1b)",
     CHANNEL,
     "            if room[0] >= MAX_PULLED_FILES or room[1] >= MAX_PULLED_BYTES:\n",
     "            if False:\n"),
    ("M5789", "what is no window in the watch's directory stays there for good (SEC-A1b)",
     EXERCISE,
     "            if path.parent == own and _not_a_window(e):\n",
     "            if False:\n"),
    ("M5790", "the watch follows every file a writer ever wrote, looked at each poll (SEC-A1b)",
     READER,
     "        older = listed[:-TRACKED_MAX]\n",
     "        older = []\n"),
    ("M5791", "the cut at MAX_WINDOW_FILES follows the paths: a flood in one directory pushes another's out (SEC-A1b)",
     EXERCISE,
     "    paths = [p for turn in zip_longest(*lists) for p in turn if p is not None]\n",
     "    paths = [p for listed in lists for p in listed]\n"),
    ("M5792", "the cut said again at each read of a growing flood (SEC-A1b)",
     EXERCISE,
     "        if key not in _flooded:\n",
     "        if True:\n"),
    ("M5793", "the console's chain counts the windows it refused (SEC-A1b)",
     EXERCISE,
     '        if not isinstance(w, dict) or w.get("refusal") or vm not in (w.get("targets") or []) \\\n',
     '        if not isinstance(w, dict) or vm not in (w.get("targets") or []) \\\n'),
    ("M5794", "a campaign's manifest published to Imladris read by its name: a pipe holds the run (SEC-A1b)",
     CHANNEL,
     '    manifest = read_json(cdir / "manifest.json")   # KS1, SEC-A1b: what is published to Imladris, read bounded\n',
     '    manifest = __import__("json").loads((cdir / "manifest.json").read_text(encoding="utf-8"))\n'),
    ("M5795", "the local heartbeat read by its name: a pipe holds a run between two steps (SEC-A1b)",
     GATE,
     "        text = read_text(path, BEAT_BYTES).strip()\n",
     "        text = path.read_text().strip()\n"),
    ("M5796", "a zone written « Production » takes a fault's mark (SEC-A1b)",
     EXERCISE,
     '    if not check_zone(z, kind=str(window.get("kind") or ""), destructive=False).allowed:\n',
     "    if False:\n"),
    ("M5797", "a fault or a destructive gesture marks a VM outside the bench's perimeter, by its tags alone (SEC-A1b)",
     EXERCISE,
     '        on_bench = window.get("kind") != "technique" or window.get("destructive") is not False\n',
     "        on_bench = False\n"),
    ("M5798", "the kill reads the channel as a pull does: the windows listed past its bounds unseen (SEC-A1b)",
     CHANNEL,
     "    for blob in _whole_listing(get, url, headers, limit):\n",
     '    for blob in _blobs(get, url, headers, delimiter="/", say=say):\n'),
    ("M5799", "the kill takes a listing cut for the whole channel (SEC-A1b)",
     CHANNEL,
     "            if seen > limit:\n",
     "            if False:\n"),
    ("M5800", "a file no longer followed replays its lines when it comes back among the newest (SEC-A1b)",
     READER,
     "            if path in self._untracked:          # among the newest again: from its end\n",
     "            if False:\n"),
]
TESTS = {mid: _TESTS for mid, *_ in MUTANTS}
