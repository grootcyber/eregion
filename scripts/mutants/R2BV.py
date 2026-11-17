"""R2BV (#608): the Stratus control-plane injector pinned to the official v2.38.1 release. The
committed PIN carries the binary digest the adapter checks before every phase. R2BW (#608) then
changed the provenance from a downloaded release binary to one BUILT from the vendored submodule
(the pinned commit + our patch), so the recorded digest is now the built one — this mutant stays
valid, re-anchored to that value. M5671 measured by tests/unit/test_annatar_stratus.py
(test_repo_pin_records_the_stratus_binary: the committed digest is the one the adapter verifies)."""
PIN = "annatar/stratus/PIN"

MUTANTS = [
    ("M5671", "the committed Stratus binary digest left at a wrong value (R2BV)", PIN,
     "#   834976c9df9584c8d02e9559139cc4ca9a46af658134c160b2b1205d0d8db21e  stratus",
     "#   0000000000000000000000000000000000000000000000000000000000000000  stratus"),
]

TESTS = {
    "M5671": "tests/unit/test_annatar_stratus.py::test_repo_pin_records_the_stratus_binary",
}
