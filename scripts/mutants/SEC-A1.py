"""SEC-A1 (#630, V-02, V-21): what Glorfindel and Annatar read of runs/ is read as the channel is
read (eregion_core/channel_reader.py) — the exercise windows, the signals `glorfindel respond`
reads, a campaign's manifest —, a local window is bounded in the past by its file's mtime, and the
windows chained on one VM by CHAIN_MAX_S. M4520–M4524.

Each caught by tests/unit/test_bounded_reads.py: a read that blocks on a pipe fails there within
seconds, never hangs the run.
"""
EXERCISE = "eregion_core/exercise.py"
SIGNALS = "glorfindel/signals.py"
MANIFEST = "annatar/campaign/manifest.py"
_TESTS = "tests/unit/test_bounded_reads.py"

MUTANTS = [
    ("M4520", "the windows read by name again: a pipe stops the watch's loop, a link is followed (SEC-A1)",
     EXERCISE,
     '    data, st = read_regular(path, WINDOW_BYTES)\n'
     '    return json.loads(data.decode("utf-8")), datetime.fromtimestamp(st.st_mtime, timezone.utc)\n',
     '    return (json.loads(path.read_text(encoding="utf-8")),\n'
     '            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))\n'),
    ("M4521", "the signals `glorfindel respond` reads opened by name: a pipe blocks it, a link is followed (SEC-A1)",
     SIGNALS,
     "    for line in read_text(path).splitlines():\n",
     "    for line in open(path):\n"),
    ("M4522", "a campaign's manifest read by name: a pipe blocks the runner and the replay (SEC-A1)",
     MANIFEST,
     '        return cls.from_dict(read_json(Path(campaign_dir) / "manifest.json"))\n',
     '        return cls.from_dict(json.loads((Path(campaign_dir) / "manifest.json").read_text()))\n'),
    ("M4523", "a local window bounded toward the future only: written now, dated back, it is believed (SEC-A1)",
     EXERCISE,
     "    if declared_at is not None and (local or CHANNEL_CREATED not in window):\n",
     "    if False:\n"),
    ("M4524", "the windows on one VM chained without a bound: a VM stays in exercise for good (SEC-A1)",
     EXERCISE,
     "    if covered > CHAIN_MAX_S:\n",
     "    if False:\n"),
]
TESTS = {mid: _TESTS for mid in ("M4520", "M4521", "M4522", "M4523", "M4524")}
