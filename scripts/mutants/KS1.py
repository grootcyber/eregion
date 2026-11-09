"""KS1 (#648): the stop of a campaign read fail-closed. The runner re-reads its manifest's
kill_switch before each run (annatar/campaign/runner.py, `_stop_requested`): a manifest the
bounded reader refuses (SEC-A1: a pipe, a link, a file too large) or that cannot be read (not
JSON, nested too deep, an I/O error) stops the campaign, said once and recorded in the
manifest (`stop_reason`); a manifest gone asks nothing. M4573–M4575.

Each caught by tests/unit/test_campaign_runner.py.
"""
RUNNER = "annatar/campaign/runner.py"
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
    ("M4575", "a manifest gone read as a stop: a campaign whose manifest is rewritten stops for nothing (KS1)",
     RUNNER,
     "        except FileNotFoundError:\n            return None\n",
     "        except FileNotFoundError:\n            return KILL_SWITCH_UNREADABLE\n"),
]
TESTS = {mid: _TESTS for mid in ("M4573", "M4574", "M4575")}
