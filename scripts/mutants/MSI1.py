"""Lot MSI1 (#608) — le provider azurerm authentifie le warmup par l'identité managée de l'hôte.
Sur un Orodruin armé le conteneur durci ne porte QUE l'identité managée système (aucun credential de
principal de service, pas d'Azure CLI) : sans directive, le provider ne trouve aucun credential
hors-ligne et l'échoue. `azure_provider_env` pose ARM_USE_MSI + l'abonnement + le tenant, sans jamais
forcer MSI par-dessus un credential présent (secret, certificat, jeton fédéré — tous portent un
client id que l'identité managée n'a pas), en écartant les valeurs blanches, et exige l'abonnement ET
le tenant. Les mutants portent sur la garde du credential, la pose d'ARM_USE_MSI, la garde « les deux
requis », la fusion par l'exécuteur, le filtrage du blanc, la détection des formes de SP et les
sources du tenant. M6101–M6108. Mesurés par tests/unit/test_annatar_stratus.py.

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
_BLANK = f"{_T}::test_azure_provider_env_ignores_blank_values"
_FORMS = f"{_T}::test_azure_provider_env_leaves_every_service_principal_form_untouched"
_AZTENANT = f"{_T}::test_azure_provider_env_accepts_the_azure_tenant_name"

_GUARD = '    if any((environ.get(k) or "").strip() for k in _SP_CREDENTIAL_ENV):'

MUTANTS = [
    ("M6101", "the service-principal-credential guard is bypassed — MSI is forced over working "
     "credentials, breaking a developer run that authenticates by its secret (MSI1)",
     ENGINE, _GUARD,
     '    if False and any((environ.get(k) or "").strip() for k in _SP_CREDENTIAL_ENV):'),
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
     "        return {**base, **overrides, **identity}",
     "        return {**base, **overrides}"),
    ("M6105", "a blank value is taken for the subscription/tenant — a whitespace EREGION_TENANT_ID "
     "yields ARM_TENANT_ID='  ' and the provider fails opaquely instead of no-op (MSI1)",
     ENGINE,
     '        value = (environ.get(name) or "").strip()',
     "        value = environ.get(name) or \"\""),
    ("M6106", "the credential guard treats a blank secret as present — an empty AZURE_CLIENT_SECRET "
     "(orodruin.env warns of it) wrongly blocks MSI on an armed host (MSI1)",
     ENGINE, _GUARD,
     "    if any(k in environ for k in _SP_CREDENTIAL_ENV):"),
    ("M6107", "a certificate service principal is no longer detected — MSI is forced while the "
     "contract would evaluate the certificate identity: evaluated ≠ acting (MSI1)",
     ENGINE,
     '    "ARM_CLIENT_CERTIFICATE_PATH", "AZURE_CLIENT_CERTIFICATE_PATH",  # by certificate',
     "    # by certificate (dropped)"),
    ("M6108", "AZURE_TENANT_ID is dropped as a tenant source — a control-plane technique that names "
     "only it no-ops silently and the warmup fails as before MSI1 (MSI1)",
     ENGINE,
     '_TENANT_SRC = ("ARM_TENANT_ID", "EREGION_TENANT_ID", "AZURE_TENANT_ID")',
     '_TENANT_SRC = ("ARM_TENANT_ID", "EREGION_TENANT_ID")'),
]

TESTS = {
    "M6101": _SP,
    "M6102": _MSI,
    "M6103": _BOTH,
    "M6104": _MERGE,
    "M6105": _BLANK,
    "M6106": _BLANK,
    "M6107": _FORMS,
    "M6108": _AZTENANT,
}
