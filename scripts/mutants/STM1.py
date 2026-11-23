"""STM1 (STM1g's red counterpart, #894): Annatar's catalogue readers ask ``is_ready`` (implemented
or proven), never the word ``implemented`` alone — so a technique turned ``proven`` (measured on the
bench) does not vanish from the synthesis and the execution. The red counterpart of STM1g, which did
the blue readers. Reverting a reader to ``== "implemented"`` is caught by the static guard that reads
the whole code (tests/unit/test_catalog_ready.py), the catalogue filter also by a behavioural test.
M7133–M7136, measured by tests/unit/test_catalog_ready.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
CAT = "annatar/campaign/catalog.py"
SYN = "annatar/campaign/synthesizer.py"
DEC = "annatar/campaign/declared.py"
_T = "tests/unit/test_catalog_ready.py"
_READY = f"{_T}::test_red_ready_techniques_keeps_proven_drops_planned"
_NO_READER = f"{_T}::test_no_reader_compares_the_status_to_implemented_alone"

MUTANTS = [
    ("M7133", "ready_techniques drops a proven technique: back to the word implemented (STM1)",
     CAT, "if is_ready(e.get(\"status\"))]", "if e.get(\"status\") == \"implemented\"]"),
    ("M7134", "the synthesizer refuses a proven technique: back to the word implemented (STM1)",
     SYN, "    if not is_ready(entry.get(\"status\")):",
     "    if entry.get(\"status\") != \"implemented\":"),
    ("M7135", "a declared campaign refuses a proven technique: back to the word implemented (STM1)",
     DEC, "            if not is_ready(entry.get(\"status\")):",
     "            if entry.get(\"status\") != \"implemented\":"),
    ("M7136", "a declared fault refuses a proven one: back to the word implemented (STM1)",
     DEC, "    if not is_ready(doc.get(\"status\")):",
     "    if doc.get(\"status\") != \"implemented\":"),
]

TESTS = {
    "M7133": _READY,
    "M7134": _NO_READER,
    "M7135": _NO_READER,
    "M7136": _NO_READER,
}
