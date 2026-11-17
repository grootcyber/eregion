"""R2BV (#608): the Stratus control-plane injector pinned to the official v2.38.1 release — the
warmup VM SKU of azure.execution.vm-run-command fixed upstream (Standard_F2 -> Standard_D2as_v7
with a Gen2 image, DataDog #1016). The committed PIN carries the v2.38.1 binary digest the
adapter checks before every phase; the stage script and the adapter name v2.38.1. M5671 measured
by tests/unit/test_annatar_stratus.py (test_repo_pin_records_the_stratus_binary: the committed
digest is the one the adapter verifies)."""
PIN = "annatar/stratus/PIN"

MUTANTS = [
    ("M5671", "the committed Stratus binary digest left at a wrong value (R2BV)", PIN,
     "#   b37130e21e82c23373a021c4f22bbe86714bc154bac8f4633b2544143e09564d  stratus",
     "#   0000000000000000000000000000000000000000000000000000000000000000  stratus"),
]

TESTS = {
    "M5671": "tests/unit/test_annatar_stratus.py::test_repo_pin_records_the_stratus_binary",
}
