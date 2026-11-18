"""Lot ORU1 (#608) — `make orodruin-run SCENARIO=<nom> [DRY_RUN=1]` : jouer UN scénario sur Orodruin
armé, en une commande gardée. Les mutants portent sur la garde de session (une session ne lance
jamais une attaque) et sur l'honnêteté du DRY_RUN (il ne doit jamais partir pour de vrai). M6041–M6042.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
GUARD = "scripts/orodruin_run.py"
MK = "Makefile"

_REFUSE = ("tests/unit/test_makefile_orodruin_run.py::test_guard_refuses_a_code_session")
_DRY = ("tests/unit/test_makefile_orodruin_run.py::"
        "test_orodruin_run_plays_one_scenario_in_the_orodruin_image")

MUTANTS = [
    ("M6041", "the session guard of make orodruin-run is bypassed — a code session could launch "
     "an attack (ORU1)", GUARD, "    if refusal:", "    if False:"),
    ("M6042", "make orodruin-run DRY_RUN=1 would run for real — the --dry-run is dropped (ORU1)",
     MK,
     "annatar run $(SCENARIO)$(if $(filter 1,$(DRY_RUN)), --dry-run) --yes$(ORO_WITHOUT)",
     "annatar run $(SCENARIO) --yes$(ORO_WITHOUT)"),
]

TESTS = {
    "M6041": _REFUSE,
    "M6042": _DRY,
}
