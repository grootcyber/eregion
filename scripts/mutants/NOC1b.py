"""NOC1b (#1269): the night's guard covers the whole invariant machine — the journal, the hold, the sequences
frozen, the nights' watchdog (scripts/night_guard.py, PROTECTED; docs/sessions.md, « La nuit »). Jonathan's
decision of 27/11: « Oui, avec les régressions ». M8160 puts the old pattern back (`test_invariants*`, with an
« s »): the regressions, the journal, the hold's tests and the watchdog's merge at night. M8161 takes
`invariant_watchdog.py` out of the list. M8162 widens the pattern past the machine: a neighbour
(`test_investigate.py`) is refused. M8163 narrows it to `test_invariant_*`: the oracle itself
(`test_invariants.py`) merges at night. Then, at the coordinator's word: M8164 takes the nights' seed
(`tests/unit/hypothesis_seed.py`, SEED1) out of the list, M8165 the night unit's tests
(`tests/unit/test_night_unit.py`). After the review's first round: M8166 holds a companion by its exact
name again (a package of the same name hides it), M8167 takes the tests' packages (`__init__.py`) out, M8168
the compiled modules (`*.pyc`), M8170 the seed's tests (`tests/unit/test_hypothesis_seed.py`). M8169 is left
unused: the closure test (`test_every_module_the_machine_imports_is_held`) holds no line of the guard that the
per-file tests do not already hold, so no mutant of the guard tells it apart. Measured by
tests/unit/test_night_guard.py. After the review's second round: M8183 lets a file directly under tests/ through
(pytest puts tests/ before the root), M8184 an extension module (`*.so`).
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
     '    ("tests/unit/invariant_watchdog*", "touches the nights\' watchdog of the invariant machine (CI13, which "\n'
     '                                       "settles NGT1): a question for Jonathan"),\n',
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

MUTANTS += [
    ("M8164", "the nights' seed taken out of the list: a night changes the seed to escape one that fails (NOC1b, "
              "SEED1)", GUARD,
     '    ("tests/unit/hypothesis_seed*", "touches the seed the invariant nights draw (SEED1): a question for '
     'Jonathan"),\n',
     ""),
    ("M8165", "the night unit's tests taken out of the list: a night weakens the tests of its own rails (NOC1b)",
     GUARD,
     '    ("tests/unit/test_night_unit.py", "touches the night\'s own rails (tests/unit/test_night_unit.py: its '
     'unit\'s "\n'
     '                                      "tests)"),\n',
     ""),
]

# The review's first round (59c56a27, « changes »): what hides a companion of the machine from its imports.
MUTANTS += [
    ("M8166", "a companion held by its exact name, not its prefix: tests/unit/fake_azure/__init__.py, a package "
              "Python prefers, hides fake_azure.py from the machine and merges at night (NOC1b)", GUARD,
     '    ("tests/unit/fake_azure*", "touches the fake Azure',
     '    ("tests/unit/fake_azure.py", "touches the fake Azure'),
    ("M8167", "a package of the tests no longer held: an __init__.py under tests/ changes what a relative import "
              "finds, at night (NOC1b)", GUARD,
     '    ("tests/*/__init__.py", "touches a package of the tests (__init__.py): what a relative import finds"),\n',
     ""),
    ("M8168", "a compiled module no longer held: a .pyc without its source, added with `git add -f`, is imported "
              "in its place, at night (NOC1b)", GUARD,
     '    ("*.py[co]", "touches a compiled module (.pyc): one without its source is imported in its place"),\n',
     ""),
    ("M8170", "the seed's tests taken out of the list: a night weakens the tests that catch SEED1's mutants "
              "(NOC1b)", GUARD,
     '    ("tests/unit/test_hypothesis_seed.py", "touches the tests of the seed the invariant nights draw (SEED1): a "'
     '\n'
     '                                           "question for Jonathan"),\n',
     ""),
]

# The review's second round (90708a8b, « changes »): what hides a name from the whole machine.
MUTANTS += [
    ("M8183", "a file directly under tests/ let through: in prepend mode pytest puts tests/ before the root, and a "
              "tests/hypothesis.py that empties run_state_machine_as_test merges at night (NOC1b)", GUARD,
     '        elif new.startswith("tests/") and new.count("/") == 1:\n',
     "        elif False:\n"),
    ("M8184", "an extension module let through: a glorfindel/actions.cpython-312-x86_64-linux-gnu.so, which Python "
              "imports before actions.py and .gitignore does not ignore, merges at night (NOC1b)", GUARD,
     '    ("*.so", "touches an extension module (.so): Python imports it before a source of the same name"),\n',
     ""),
]

TESTS = {f"M{n}": _T for n in [*range(8160, 8169), 8170, 8183, 8184]}
