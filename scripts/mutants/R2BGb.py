"""Lot R2BGb (#897) — un apply d'Orodruin ne détruit plus les garde-fous Stratus par omission.
`scripts/stratus_guard.py`, lancé avant orodruin-plan/up/lock, refuse de planifier si l'état porte des
ressources de garde-fou Stratus et que le drapeau effectif (le `*.auto.tfvars` fait foi, comme
Terraform ; sinon l'env) est éteint. Les mutants portent sur la garde (condition de refus, inversion),
la lecture du drapeau (précédence fichier/env, valeur du fichier) et le code de retour de `main`.
M6181–M6186. Mesurés par tests/unit/test_stratus_guard.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
GUARD = "scripts/stratus_guard.py"

_T = "tests/unit/test_stratus_guard.py"
_REFUSE = f"{_T}::test_refuses_when_the_state_holds_guardrails_and_the_flag_is_off"
_ALLOW = f"{_T}::test_allows_when_the_flag_is_on"
_ENV = f"{_T}::test_the_flag_is_read_from_the_env"
_WINS = f"{_T}::test_the_auto_tfvars_wins_over_the_env"
_MAIN = f"{_T}::test_main_refuses_when_the_state_is_guarded_and_the_flag_is_off"
_OFF = f"{_T}::test_the_flag_is_off_when_neither_says_true"

_COND = "    if has_guardrails(resources) and not enabled:"
_ENVLINE = '    return (environ.get("TF_VAR_stratus_guardrails_enabled") or "").strip().lower() in _TRUE'

MUTANTS = [
    ("M6181", "the refusal is dropped — an apply that would destroy the Stratus guardrails is let "
     "through, so they are wiped by omission (R2BGb)",
     GUARD, _COND, "    if False:"),
    ("M6182", "the flag is read inverted — the guard refuses when the guardrails ARE enabled and "
     "lets an omission through when they are off (R2BGb)",
     GUARD, _COND, "    if has_guardrails(resources) and enabled:"),
    ("M6183", "the env flag is no longer read — TF_VAR_stratus_guardrails_enabled=true is ignored "
     "when no tfvars defines it, so a legitimate apply is wrongly refused (R2BGb)",
     GUARD, _ENVLINE, "    return False"),
    ("M6184", "the auto.tfvars no longer takes precedence — Terraform reads the file's false while "
     "the guard falls back to the env's true and lets the destruction through (R2BGb)",
     GUARD, "    if in_file:", "    if False:"),
    ("M6185", "main no longer returns a failing code — the Makefile `&&` never stops, so a "
     "destroying plan proceeds (R2BGb)",
     GUARD, "        return 1", "        return 0"),
    ("M6186", "the file flag's value is ignored — `false` in the tfvars is read as on, so the guard "
     "allows the destruction the file asked to avoid (R2BGb)",
     GUARD, '        return in_file.group(1) == "true"', "        return True"),
]

TESTS = {
    "M6181": _REFUSE,
    "M6182": _ALLOW,
    "M6183": _ENV,
    "M6184": _WINS,
    "M6185": _MAIN,
    "M6186": _OFF,
}
