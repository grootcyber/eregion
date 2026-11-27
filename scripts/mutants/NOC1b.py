"""NOC1b (#1269): the night's guard covers the whole invariant machine — the journal, the hold, the sequences
frozen, the nights' watchdog (scripts/night_guard.py, PROTECTED; docs/sessions.md, « La nuit »). Jonathan's
decision of 27/11: « Oui, avec les régressions ». M8160 puts the old pattern back (`test_invariants*`, with an
« s »): the regressions, the journal, the hold's tests and the watchdog's merge at night. M8161 takes
`invariant_watchdog.py` out of the list. M8162 widens the pattern past the machine: a neighbour
(`test_investigate.py`) is refused. M8163 narrows it to `test_invariant_*`: the oracle itself
(`test_invariants.py`) merges at night. Measured by tests/unit/test_night_guard.py.
"""
GUARD = "scripts/night_guard.py"
_T = "tests/unit/test_night_guard.py"
_PATTERN = '    ("tests/unit/test_invariant*.py", "touches the invariant machine,'

MUTANTS = [
    ("M8160", "the old pattern, with its « s »: a sequence frozen, the journal, the hold's tests or the "
              "watchdog's merge at night without Jonathan (NOC1b)", GUARD,
     _PATTERN,
     '    ("tests/unit/test_invariants*.py", "touches the invariant machine,'),
    ("M8161", "the nights' watchdog taken out of the list: the helper that settles NGT1 merges at night (NOC1b)",
     GUARD,
     '    ("tests/unit/invariant_watchdog.py", "touches the nights\' watchdog of the invariant machine (CI13, which "\n'
     '                                         "settles NGT1): a question for Jonathan"),\n',
     ""),
    ("M8162", "the pattern widened past the machine: a neighbour (test_investigate.py) refused at night "
              "(NOC1b)", GUARD,
     _PATTERN,
     '    ("tests/unit/test_inv*.py", "touches the invariant machine,'),
    ("M8163", "the pattern narrowed to test_invariant_*: the oracle itself (test_invariants.py) merges at night "
              "(NOC1b)", GUARD,
     _PATTERN,
     '    ("tests/unit/test_invariant_*.py", "touches the invariant machine,'),
]

TESTS = {f"M{n}": _T for n in range(8160, 8164)}
