"""Lot R2BY (#608) — stager dans le mirror hors-ligne les providers que les techniques UTILISENT
sans les déclarer (implicites : `random` via `random_password`), mesuré au banc : sans eux, le
warmup échoue (`provider … was not found`). Les mutants portent sur le staging des implicites et
sur le refus fail-closed d'un implicite non épinglé. M6061–M6062. Mesurés par
tests/unit/test_stratus_build.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
BUILD = "scripts/stratus_build.py"

_LAYOUT = "tests/unit/test_stratus_build.py::test_build_lays_out_the_verified_tree"
_REFUSE = ("tests/unit/test_stratus_build.py::test_implicit_providers_refuses_an_unpinned_one")

MUTANTS = [
    ("M6061", "the implicitly-used providers are not staged into the offline mirror — the warmup "
     "fails offline (`provider not found`) (R2BY)",
     BUILD,
     "    providers = {**declared, **implicit_providers(submodule, set(declared))}",
     "    providers = {**declared}"),
    ("M6062", "an implicitly-used provider with no pin is staged unverified instead of refused "
     "(R2BY)", BUILD, "        if ptype not in IMPLICIT_VERSIONS:", "        if False:"),
]

TESTS = {
    "M6061": _LAYOUT,
    "M6062": _REFUSE,
}
