"""Lot R2BGb (#897) — un apply d'Orodruin ne détruit plus les garde-fous Stratus par omission.
`scripts/stratus_guard.py`, lancé avant orodruin-plan/up/lock, refuse de planifier si l'état porte des
ressources de garde-fou Stratus et que le drapeau `stratus_guardrails_enabled` est éteint (l'apply les
détruirait, count=0). Les mutants portent sur la garde (condition de refus, inversion du drapeau) et
sur la lecture du drapeau effectif (env, auto.tfvars). M6181–M6184. Mesurés par
tests/unit/test_stratus_guard.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
GUARD = "scripts/stratus_guard.py"

_T = "tests/unit/test_stratus_guard.py"
_REFUSE = f"{_T}::test_refuses_when_the_state_holds_guardrails_and_the_flag_is_off"
_ALLOW = f"{_T}::test_allows_when_the_flag_is_on"
_ENV = f"{_T}::test_the_flag_is_read_from_the_env"
_TFVARS = f"{_T}::test_the_flag_is_read_from_the_auto_tfvars"

_COND = "    if has_guardrails(resources) and not enabled:"

MUTANTS = [
    ("M6181", "the refusal is dropped — an apply that would destroy the Stratus guardrails is let "
     "through, so they are wiped by omission (R2BGb)",
     GUARD, _COND, "    if False:"),
    ("M6182", "the flag is read inverted — the guard refuses when the guardrails ARE enabled and "
     "lets an omission through when they are off (R2BGb)",
     GUARD, _COND, "    if has_guardrails(resources) and enabled:"),
    ("M6183", "the env flag is no longer read — TF_VAR_stratus_guardrails_enabled=true is ignored, "
     "so a legitimate apply is wrongly refused (R2BGb)",
     GUARD,
     '    if (environ.get("TF_VAR_stratus_guardrails_enabled") or "").strip().lower() in _TRUE:',
     "    if False:"),
    ("M6184", "the auto.tfvars flag is no longer read — stratus_guardrails_enabled = true in the "
     "tfvars is ignored, so a legitimate apply is wrongly refused (R2BGb)",
     GUARD,
     '    return bool(_TFVARS_ENABLED.search(tfvars_text or ""))',
     "    return False"),
]

TESTS = {
    "M6181": _REFUSE,
    "M6182": _ALLOW,
    "M6183": _ENV,
    "M6184": _TFVARS,
}
