"""Fetch Orodruin's managed-identity assertion for the federated Stratus exchange (R2c pièce 4B).

Run on the HOST side of an armed Orodruin — in a short-lived container on the default bridge, where
the IMDS is reachable — BEFORE the Stratus run, which runs on the ``eregion-stratus-sandbox`` network
where the IMDS is DROPped (pièce 3). This prints Orodruin's managed-identity token for the exchange
audience (``api://AzureADTokenExchange``) to stdout; the Makefile (``orodruin-stratus``) writes it to
a host file and mounts it read-only into the sandbox run, where ``stratus_run_env``
(``annatar/engines/stratus.py``) turns it into ``ARM_USE_OIDC`` so the azurerm provider exchanges the
assertion for a Stratus token on the DEDICATED subscription — never Orodruin's managed identity (the
IMDS is unreachable from the sandbox) nor the bench.

The assertion is Orodruin's own managed-identity token: the federated identity credential posed by
R2BGc (G2) trusts Orodruin's identity as the subject, so only an assertion minted by it is exchanged.
This runs as ``python -m annatar.executors.stratus_assertion``; a read that fails exits non-zero, so
the Makefile writes no file and the run never starts with a stale or empty assertion (fail closed).
"""
from __future__ import annotations

import sys
from collections.abc import Callable

# The audience of the assertion: Orodruin's managed identity federates to the Stratus app through
# api://AzureADTokenExchange (the Workload Identity exchange audience). Measured at Étape 2 (19/11):
# Entra returns a token whose aud is the exchange app's GUID for this resource; the azurerm provider
# accepts it. The token is requested for the ``/.default`` scope of that audience.
EXCHANGE_AUDIENCE = "api://AzureADTokenExchange"


def fetch_assertion(get_token: Callable[[str], str] | None = None) -> str:
    """Orodruin's managed-identity token for the exchange audience — the federated assertion.

    ``get_token(scope) -> token`` is injected in the tests; the default uses the host's managed
    identity (``DefaultAzureCredential``), which on an armed Orodruin reaches the IMDS (this runs on
    the default bridge, not the sandbox). An empty token is a failure, never a value — the run must
    not start without a real assertion (fail closed)."""
    if get_token is None:  # pragma: no cover - the real credential, never in the tests
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential()
        get_token = lambda scope: cred.get_token(scope).token  # noqa: E731
    token = (get_token(f"{EXCHANGE_AUDIENCE}/.default") or "").strip()
    if not token:
        raise RuntimeError(
            "the managed-identity assertion for the federated exchange is empty — the Stratus run "
            "must not start without it (fail closed)"
        )
    return token


def main() -> int:
    sys.stdout.write(fetch_assertion())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
