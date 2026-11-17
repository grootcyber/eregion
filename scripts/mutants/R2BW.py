"""Lot R2BW (#608) — construire l'injecteur de plan de contrôle DEPUIS le submodule vendoré (le
dépôt OFFICIEL DataDog/stratus-red-team épinglé, + notre patch en repo) au lieu de télécharger le
binaire. Les mutants portent sur la logique NOUVELLE du build : la garde de reproductibilité (le
sha du binaire construit doit égaler le PIN) et la garde de divergence des versions de providers
lues dans le submodule. M5681–M5682. (verify() et le refus fail-closed sans checksum restent
mesurés par R2BS, réancrés sur scripts/stratus_build.py.)

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
BUILD = "scripts/stratus_build.py"

_REPRO = ("tests/unit/test_stratus_build.py::"
          "test_build_refuses_a_non_reproducible_binary")
_DIVERGE = ("tests/unit/test_stratus_build.py::"
            "test_required_providers_refuses_divergent_pins")

MUTANTS = [
    ("M5681", "a built binary whose sha256 does not match the PIN is not refused — a "
     "non-reproducible build or a changed submodule/patch slips through (R2BW)",
     BUILD, "    if want and sha != want:", "    if False:"),
    ("M5682", "two azure techniques pinning different versions of the same provider is not "
     "refused — the staged provider version becomes order-dependent (R2BW)",
     BUILD, "            if prev is not None and prev != pver:", "            if False:"),
]

TESTS = {
    "M5681": _REPRO,
    "M5682": _DIVERGE,
}
