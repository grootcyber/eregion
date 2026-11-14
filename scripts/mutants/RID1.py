"""Lot #819 — la carte d'identité de la 0.6.0 : un scénario de plan de contrôle (bibliothèque
publique épinglée) jouable par `annatar run`, et la validation d'authoring des scénarios Stratus
dans le parser (annatar/runner/parser.py) — une technique du plan de contrôle n'est pas une VM.
M5160–M5163.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
PARSER = "annatar/runner/parser.py"

_VM = ("tests/unit/test_annatar_stratus.py::"
       "test_stratus_scenario_on_a_vm_target_is_refused")
_VALID = ("tests/unit/test_annatar_stratus.py::"
          "test_fic_identity_scenario_is_valid_and_resolves_to_the_catalog")
_OTHER = ("tests/unit/test_annatar_stratus.py::"
          "test_stratus_authoring_checks_do_not_touch_other_engines")

MUTANTS = [
    ("M5160", "a stratus scenario with a VM target type not refused (#819)", PARSER,
     'target.get("type") == "azure_vm"', "False"),
    ("M5161", "a vm_name on a stratus scenario's control-plane target not refused (#819)", PARSER,
     'target.get("vm_name")', "False"),
    ("M5162", "the VM-target guard inverted: a well-formed control-plane scenario refused (#819)",
     PARSER, "if isinstance(target, dict) and (", "if isinstance(target, dict) and not ("),
    ("M5163", "the stratus authoring check wrongly applied to every engine (#819)", PARSER,
     '        if engine == "stratus":', "        if True:"),
]

TESTS = {
    "M5160": _VM,
    "M5161": _VM,
    "M5162": _VALID,
    "M5163": _OTHER,
}
