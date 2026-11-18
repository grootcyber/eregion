"""FRS1 (#904): « proven » is the catalogue's status (measured on the bench, STM1g) and only that;
the coverage matrix's state for a proof under 21 days old is « fresh » — its value, its summary's
key, its labels on the matrix's page and on Dagorlad's red cards, the words of the overview and of
``eregion coverage``. Each mutant brings « proven » back for the freshness, lets « fresh » into the
catalogue's statuses, or adds a reader of the matrix outside the console (the reason the value
could be renamed). M6261–M6270, measured by tests/unit/test_fresh_proven.py. M1807 (C1) follows
the code.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
COV = "eregion_console/coverage.py"
INJ = "eregion_console/static/injector.js"
DAG = "eregion_console/static/dagorlad.js"
CLI = "eregion_console/cli.py"
CORE = "eregion_core/experiment.py"

_T = "tests/unit/test_fresh_proven.py"

MUTANTS = [
    # ── The server ──
    ("M6261", "a proof under 21 days says « proven » again: two meanings for one word (FRS1)", COV,
     '        return "fresh" if age < AGING_DAYS * DAY else "aging"',
     '        return "proven" if age < AGING_DAYS * DAY else "aging"'),
    ("M6262", "the matrix's summary counts the fresh rows under « proven » (FRS1)", COV,
     '    for s in ("fresh", "aging", "stale", "unproven", "never"):\n',
     '    for s in ("proven", "aging", "stale", "unproven", "never"):\n'),
    # ── The matrix's page ──
    ("M6263", "the matrix's page knows a « proven » state, not the fresh one (FRS1)", INJ,
     "  fresh: { cls: 'ok', label: 'fresh',", "  proven: { cls: 'ok', label: 'proven',"),
    ("M6264", "the matrix's page labels a fresh row « proven » (FRS1)", INJ,
     "label: 'fresh'", "label: 'proven'"),
    ("M6265", "the counter above the matrix says « proven » for the fresh rows (FRS1)", INJ,
     "${num(s.fresh)} fresh</span>", "${num(s.fresh)} proven</span>"),
    ("M6266", "the counter above the matrix reads the old key: its fresh rows counted 0 (FRS1)", INJ,
     "${num(s.fresh)} fresh</span>", "${num(s.proven)} fresh</span>"),
    # ── Dagorlad's red cards ──
    ("M6267", "a red card's proof chip says « proven » for a fresh proof (FRS1)", DAG,
     "  fresh: ['c-ok', 'fresh'],", "  proven: ['c-ok', 'proven'],"),
    # ── The command ──
    ("M6268", "eregion coverage says « never proven » again for the rows without a proof (FRS1)", CLI,
     'f"no proof {s[\'never\'] + s[\'unproven\']}")', 'f"never proven {s[\'never\'] + s[\'unproven\']}")'),
    # ── The catalogue's word ──
    ("M6269", "« fresh » taken for a catalogue status: the predicate counts it ready (FRS1)", CORE,
     'READY_STATUSES = ("implemented", "proven")\n', 'READY_STATUSES = ("implemented", "proven", "fresh")\n'),
    # ── Only the console reads the matrix ──
    ("M6270", "a reader of the matrix outside the console: the renamed value would break it unseen (FRS1)",
     CORE,
     "# The status of a catalogue entry (STM1g, #894): ``planned`` — nothing runs it yet;\n",
     "# The status of a catalogue entry (STM1g, #894; GET /api/coverage reads its rows' states):"
     " ``planned`` — nothing runs it yet;\n"),
]

TESTS = {mid: _T for mid, *_ in MUTANTS}
