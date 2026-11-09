"""KS1 (#648): the stop of a campaign read fail-closed. The runner re-reads its manifest's
kill_switch before each run and before each write of the manifest (annatar/campaign/runner.py,
`_stop_requested`, `_save`), kept once seen: a manifest gone, refused by the bounded reader
(SEC-A1: a pipe, a link, a file too large) or that cannot be read (not JSON, nested too deep, an
I/O error, a kill_switch neither true nor false) stops the campaign, said once and recorded in
the manifest (`stop_reason`). M4573–M4575; the review: M4576–M4578.

Each caught by tests/unit/test_campaign_runner.py.
"""
RUNNER = "annatar/campaign/runner.py"
MANIFEST = "annatar/campaign/manifest.py"
_TESTS = "tests/unit/test_campaign_runner.py"

MUTANTS = [
    ("M4573", "a kill switch the bounded reader refuses read as \"go on\": a link or a pipe in its place lets the campaign run (KS1)",
     RUNNER,
     '            return f"{KILL_SWITCH_UNREADABLE} (refused: {exc})"\n',
     "            return None\n"),
    ("M4574", "an unreadable kill switch swallowed in silence: not JSON, an I/O error, the campaign goes on (KS1)",
     RUNNER,
     '            return f"{KILL_SWITCH_UNREADABLE} ({type(exc).__name__})"\n',
     "            return None\n"),
    ("M4575", "a manifest gone read as \"go on\": a campaign deleted from outside plays its next scenarios (KS1)",
     RUNNER,
     '            return f"{KILL_SWITCH_UNREADABLE} (manifest gone)"\n',
     "            return None\n"),
    ("M4576", "the manifest written without the stop read first: a kill switch set during a run is overwritten (KS1)",
     RUNNER,
     "        stop = self._pending_stop or self._stop_requested()\n        if stop is not None:\n"
     "            self._stop(m, stop)\n",
     "        stop = self._pending_stop\n        if stop is not None:\n"
     "            self._stop(m, stop)\n"),
    ("M4577", "a kill_switch null read as \"go on\" (KS1)",
     RUNNER,
     "        if switch is False:\n            return None\n",
     "        if not switch:\n            return None\n"),
    ("M4578", "a kill_switch that is not a boolean loaded as one (KS1)",
     MANIFEST,
     '            kill_switch=d.get("kill_switch") is True,\n',
     '            kill_switch=d.get("kill_switch", False),\n'),
]
TESTS = {mid: _TESTS for mid in ("M4573", "M4574", "M4575", "M4576", "M4577", "M4578")}
