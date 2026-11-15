"""Lot #844 — la carte d'identité de la 0.6.0, côté annuaire : l'adaptateur de la bibliothèque
publique épinglée élargi aux techniques d'annuaire (entra-id.<tactique>.<nom>, annatar/engines/
stratus.py), une technique d'annuaire jouable par `annatar run`, et la validation d'authoring des
scénarios d'annuaire (annatar/runner/parser.py, schemas/experiment.schema.json) — une cible
d'annuaire agit dans le tenant, sans groupe de ressources. M5600–M5602.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
STRATUS = "annatar/engines/stratus.py"
PARSER = "annatar/runner/parser.py"

_RESOLVE = ("tests/unit/test_annatar_stratus.py::"
            "test_resolve_accepts_an_entra_id_technique")
_TARGET = ("tests/unit/test_annatar_stratus.py::"
           "test_parser_accepts_an_entra_id_target_without_a_resource_group")

MUTANTS = [
    ("M5600", "the adapter no longer accepts a directory technique id (entra-id dropped from the "
     "id grammar, #844)", STRATUS,
     r'    r"^(?:azure|entra-id)\.[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")',
     r'    r"^(?:azure)\.[a-z0-9]+(?:-[a-z0-9]+)*\.[a-z0-9]+(?:-[a-z0-9]+)*$")'),
    ("M5601", "the directory-target relaxation inverted: a directory scenario wrongly needs a "
     "resource group, every other one no longer does (#844)", PARSER,
     '.get("type") != "entra_id" and "resource_group"',
     '.get("type") == "entra_id" and "resource_group"'),
    ("M5602", "the resource-group requirement never fires: a control-plane scenario without a "
     "group is wrongly accepted (#844)", PARSER,
     'if data["target"].get("type") != "entra_id" and',
     "if False and"),
]

TESTS = {
    "M5600": _RESOLVE,
    "M5601": _TARGET,
    "M5602": _TARGET,
}
