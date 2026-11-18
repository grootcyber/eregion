"""Lot MSI1 (#608) — le provider azurerm authentifie le warmup par l'identité managée de l'hôte.
Sur un Orodruin armé le conteneur durci ne porte QUE l'identité managée (pas de secret de principal
de service, pas d'Azure CLI) : sans directive, le provider ne trouve aucun credential hors-ligne et
l'échoue. `azure_provider_env` pose ARM_USE_MSI + l'abonnement + le tenant, sans jamais forcer MSI
par-dessus un secret présent. Les mutants portent sur la garde du secret, la pose d'ARM_USE_MSI, la
garde « abonnement ET tenant », et la fusion de la directive par l'exécuteur. M6101–M6104.
Mesurés par tests/unit/test_annatar_stratus.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et TESTS
(ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
ENGINE = "annatar/engines/stratus.py"
HOST = "annatar/executors/stratus_host.py"

_T = "tests/unit/test_annatar_stratus.py"
_SP = f"{_T}::test_azure_provider_env_leaves_service_principal_auth_untouched"
_MSI = f"{_T}::test_azure_provider_env_uses_msi_when_only_a_managed_identity"
_BOTH = f"{_T}::test_azure_provider_env_sets_nothing_without_both_subscription_and_tenant"
_MERGE = f"{_T}::test_executor_hands_the_warmup_the_managed_identity_directive"

MUTANTS = [
    ("M6101", "the service-principal-secret guard is bypassed — MSI is forced over working "
     "credentials, breaking a developer run that authenticates by its secret (MSI1)",
     ENGINE,
     "    if any(environ.get(k) for k in _SP_SECRET_ENV):",
     "    if False and any(environ.get(k) for k in _SP_SECRET_ENV):"),
    ("M6102", "ARM_USE_MSI is never set — the azurerm provider is not told to use the managed "
     "identity, so the warmup finds no credential offline and fails (MSI1)",
     ENGINE,
     '    return {ARM_USE_MSI_ENV: "true", ARM_SUBSCRIPTION_ENV: sub, ARM_TENANT_ENV: tenant}',
     "    return {ARM_SUBSCRIPTION_ENV: sub, ARM_TENANT_ENV: tenant}"),
    ("M6103", "only one of the subscription/tenant is required — a half-configured provider "
     "(a None tenant) is handed to Terraform instead of leaving auth unchanged (MSI1)",
     ENGINE,
     "    if not (sub and tenant):",
     "    if not (sub or tenant):"),
    ("M6104", "the executor drops the identity directive — ARM_USE_MSI never reaches the warmup "
     "subprocess, so the provider on an armed Orodruin cannot authenticate (MSI1)",
     HOST,
     "        return {**os.environ, **overrides, **identity}",
     "        return {**os.environ, **overrides}"),
]

TESTS = {
    "M6101": _SP,
    "M6102": _MSI,
    "M6103": _BOTH,
    "M6104": _MERGE,
}
