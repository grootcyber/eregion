"""DRL1f (#963, part of #613): the drill's Logic App starts at an hour that ends in « Z », the form Azure
requires of a Recurrence's startTime in time zone UTC (InvalidWorkflowTriggerRecurrence at the apply, read on
the bench on 20/11; docs/design/drill-banc.md §14). M6636–M6640, each caught by
tests/unit/test_drill_autostart.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids); its paths
as plain strings.
"""
TPL = "infra/orodruin/drill_autostart.json"
T = "tests/unit/test_drill_autostart.py::"

_START = T + "test_a_trigger_in_utc_starts_at_an_hour_ending_in_z"
_LINE = '                "startTime": "2026-01-01T00:00:00Z",\n'

MUTANTS = [
    ("M6636", "the startTime without its Z: Azure refuses the template in UTC, `make orodruin-up` and "
     "`orodruin-lock` fail (DRL1f)", TPL, _LINE, '                "startTime": "2026-01-01T00:00:00",\n'),
    ("M6637", "the startTime with an offset « +00:00 » for UTC: not the « Z » Azure asks for (DRL1f)", TPL,
     _LINE, '                "startTime": "2026-01-01T00:00:00+00:00",\n'),
    ("M6638", "the startTime a date alone: no hour, no Z (DRL1f)", TPL, _LINE,
     '                "startTime": "2026-01-01",\n'),
    ("M6639", "the startTime with a space for its T: not « yyyy-MM-ddTHH:mm:ssZ » (DRL1f)", TPL, _LINE,
     '                "startTime": "2026-01-01 00:00:00Z",\n'),
    ("M6640", "the startTime dropped from the trigger in UTC: the time zone is said to hold only with a start "
     "(DRL1f)", TPL, _LINE, ""),
]
TESTS = {
    "M6636": _START,
    "M6637": _START,
    "M6638": _START,
    "M6639": _START,
    "M6640": _START,
}
