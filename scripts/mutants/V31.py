"""Lot V31 (#889) — durcissement de l'exécuteur du plan de contrôle (suite de l'audit du 13/11).
Trois gestes : l'environnement transmis au binaire tiers et à Terraform est MINIMAL (seuls la
chaîne d'outils et la portée Azure non secrète sont hérités ; la clé du modèle et les canaux sont
écartés) ; une technique ne s'exécute que si le catalogue la marque `implemented` ou `proven`
(un `planned` est refusé avant résolution) ; le nom de groupe et l'abonnement sont validés avant
d'entrer dans le chemin ARM lu par la garde d'inscription. Les mutants portent sur ces trois gardes.
M6021–M6024. Mesurés par tests/unit/test_annatar_stratus.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
ENGINE = "annatar/engines/stratus.py"
HOST = "annatar/executors/stratus_host.py"

_T = "tests/unit/test_annatar_stratus.py"
_MIN = f"{_T}::test_executor_env_is_minimal_and_drops_host_secrets"
_PLAN = f"{_T}::test_resolve_refuses_a_planned_technique"
_RG = f"{_T}::test_resource_group_tags_refuses_a_malformed_group_name"
_GUID = f"{_T}::test_resource_group_tags_refuses_a_non_guid_subscription"

MUTANTS = [
    ("M6021", "the whole host environment is passed to the control-plane subprocess again — a "
     "secret (the model key, a watch key) leaks to the third-party binary and Terraform (V31)",
     HOST,
     "        return {**base, **overrides, **identity}",
     "        return {**os.environ, **overrides, **identity}"),
    ("M6022", "the catalog status gate is bypassed — a `planned` technique (design only, not "
     "reviewed-ready) resolves and reaches a run with the identity's rights (V31)",
     ENGINE,
     "    if status not in _RUNNABLE_STATUS:",
     "    if status not in _RUNNABLE_STATUS and False:"),
    ("M6023", "the resource-group name is no longer validated — a name with a '/' or '..' enters "
     "the ARM path and could read a different group's tags (V31)",
     HOST,
     '    if not _RG_NAME.fullmatch(rg) or rg.endswith("."):',
     "    if False:"),
    ("M6024", "the subscription id is no longer held to a GUID before the ARM path — a crafted "
     "value enters the request (V31)",
     HOST,
     '    if not _GUID.fullmatch(str(subscription_id or "")):',
     "    if False:"),
]

TESTS = {
    "M6021": _MIN,
    "M6022": _PLAN,
    "M6023": _RG,
    "M6024": _GUID,
}
