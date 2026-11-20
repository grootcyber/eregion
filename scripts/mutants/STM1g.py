"""STM1g (#894): the blue readers of the catalogue count ``proven`` as ``implemented`` — one predicate,
``eregion_core.experiment.is_ready``, asked by the console (coverage matrix, indicators, Dagorlad's
board), the shared core (the plan's judgement, the scheduled drill, Annatar's proposal) and
Glorfindel (the techniques a rule is proposed for). Each mutant brings back a reader that compares
the status to « implemented » alone — a technique turned ``proven`` would vanish there — or a
predicate that forgets ``proven``, or lets ``planned`` in. M6161–M6175, measured by
tests/unit/test_catalog_ready.py. M1818, M1985 and M3565 (C1, DG-a, DG-e) follow the code.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
CORE = "eregion_core/experiment.py"
BOARD = "eregion_console/board.py"
COV = "eregion_console/coverage.py"
IND = "eregion_console/indicators.py"
PLAN = "eregion_core/exercise_plan.py"
DRILL = "eregion_core/drill.py"
PROP = "eregion_core/proposal.py"
AUTH = "glorfindel/detection_authoring.py"

_T = "tests/unit/test_catalog_ready.py"

MUTANTS = [
    # ── The predicate (the shared core) ──
    ("M6161", "the predicate forgets proven: a technique measured on the bench vanishes from every blue "
     "reader (STM1g)", CORE,
     'READY_STATUSES = ("implemented", "proven")\n', 'READY_STATUSES = ("implemented",)\n'),
    ("M6162", "the predicate lets a planned entry in: nothing runs it, yet it is counted, played and "
     "proposed (STM1g)", CORE,
     "    return isinstance(status, str) and status in READY_STATUSES\n",
     "    return isinstance(status, str) and bool(status)\n"),
    # ── The console ──
    ("M6163", "Dagorlad's board greys a proven card: no handle, « proven in the catalogue » (STM1g)", BOARD,
     "        if not is_ready(e.status):\n            why =",
     '        if e.status != "implemented":\n            why ='),
    ("M6164", "Dagorlad's board sorts a proven card among the planned ones (STM1g)", BOARD,
     "key=lambda e: (not is_ready(e.status), e.kind", 'key=lambda e: (e.status != "implemented", e.kind'),
    ("M6165", "a proven entry of another target type not counted among the implemented (STM1g)", BOARD,
     '            t["implemented"] += is_ready(e.status)\n',
     '            t["implemented"] += e.status == "implemented"\n'),
    ("M6166", "the matrix's row says a proven technique not ready: the page greys it as planned (STM1g)", COV,
     '        "ready": is_ready(entry.get("status")),\n',
     '        "ready": entry.get("status") == "implemented",\n'),
    ("M6167", "the matrix's summary leaves a proven technique never run out of the proof's gaps (STM1g)", COV,
     '    counted = [r for r in rows if is_ready(r["status"]) or r["runs"]]\n',
     '    counted = [r for r in rows if r["status"] == "implemented" or r["runs"]]\n'),
    ("M6168", "the matrix's summary counts a proven technique out of the implemented (STM1g)", COV,
     '           "implemented": sum(1 for r in catalog if is_ready(r["status"]))}',
     '           "implemented": sum(1 for r in catalog if r["status"] == "implemented")}'),
    ("M6169", "the coverage's evolution leaves a proven technique detected out of the implemented ones (STM1g)",
     COV,
     '    implemented = {e["id"] for e in catalog if e["kind"] == "technique" and is_ready(e.get("status"))}\n',
     '    implemented = {e["id"] for e in catalog if e["kind"] == "technique" and e.get("status") == "implemented"}\n'),
    ("M6170", "the stalest proofs forget a proven technique: its proof ages unsaid (STM1g)", COV,
     '    stalest = sorted((r for r in techniques if is_ready(r["status"])),\n',
     '    stalest = sorted((r for r in techniques if r["status"] == "implemented"),\n'),
    ("M6171", "the coverage indicator counts a proven technique out of the implemented ones (STM1g)", IND,
     '    implemented = {e["id"] for e in techniques if is_ready(e.get("status"))}',
     '    implemented = {e["id"] for e in techniques if e.get("status") == "implemented"}'),
    # ── The shared core's readers ──
    ("M6172", "the plan refuses a proven wire as not implemented: Orodruin would never play it (STM1g)", PLAN,
     "    if not is_ready(e.status):\n", '    if e.status != "implemented":\n'),
    ("M6173", "a scheduled drill refuses a proven technique as not implemented (STM1g)", DRILL,
     "    if not is_ready(experiment.status):\n", '    if experiment.status != "implemented":\n'),
    ("M6174", "Annatar's proposal leaves a proven technique out of its chain (STM1g)", PROP,
     'if e.kind == "technique" and is_ready(e.status) and', 'if e.kind == "technique" and e.status == "implemented" and'),
    # ── Glorfindel ──
    ("M6175", "Glorfindel proposes no rule for a proven technique with none (STM1g)", AUTH,
     '        if not is_ready(entry.get("status")) and not include_planned:\n',
     '        if entry.get("status") != "implemented" and not include_planned:\n'),
]

TESTS = {mid: _T for mid, *_ in MUTANTS}
