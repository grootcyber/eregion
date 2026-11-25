"""SUBN1 (#1190) : le nom lisible d'un abonnement, lu sur Azure Resource Manager.

`GET /subscriptions/{id}` rend son `displayName`, sous `Microsoft.Resources/subscriptions/read` : tout
rôle sur l'abonnement le donne, Reader suffit. La lecture se fait avec l'identité de la watch
(`DefaultAzureCredential`, comme `AzureConnector` : sur Imladris, son identité managée), en REST par
`requests` (déjà une dépendance de Glorfindel) : `azure-mgmt-resource` n'est pas dans l'image de la
watch, et sa version 26 n'a plus de `SubscriptionClient`. Aucune nouvelle dépendance.

Lecture seule. Un identifiant qui n'a pas la forme d'un GUID est refusé avant tout appel : il vient des
`resource_id` des VM découvertes (un texte de Log Analytics), jamais collé tel quel dans une URL. Une
réponse qui n'est pas un succès lève `ArmReadError`, son statut HTTP et le code d'erreur d'ARM seuls :
le message d'ARM, qui nomme l'appelant et la portée, n'est jamais repris.
"""
from __future__ import annotations

import re

from glorfindel.providers.azure.sdk import REST_TIMEOUT_S

ARM = "https://management.azure.com"
API_VERSION = "2022-12-01"
SUBSCRIPTION_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z", re.I)


class ArmReadError(RuntimeError):
    """Une lecture qu'ARM a refusée ou n'a pas rendue : son statut (`status_code`), lu par
    `log_freshness.short_error`."""

    def __init__(self, status_code: int, code: str = "") -> None:
        super().__init__(code or "no error code")
        self.status_code = status_code


class SubscriptionReader:
    """Lit le `displayName` d'un abonnement. `credential` : celui de la watch (par défaut, créé à la
    première lecture) ; `get` : le `requests.get` d'un test."""

    def __init__(self, credential=None, get=None) -> None:
        self._credential = credential
        self._get = get

    def _token(self) -> str:
        if self._credential is None:
            from azure.identity import DefaultAzureCredential
            self._credential = DefaultAzureCredential()
        return self._credential.get_token(f"{ARM}/.default").token

    def __call__(self, subscription_id: str) -> str:
        """Le `displayName` tel qu'ARM le rend (le nettoyage est celui de glorfindel/subscription_names.py).
        Lève sur un identifiant mal formé, un refus, une réponse sans nom."""
        if not SUBSCRIPTION_ID.match(subscription_id or ""):
            raise ValueError("not a subscription id")
        get = self._get
        if get is None:
            import requests
            get = requests.get
        r = get(f"{ARM}/subscriptions/{subscription_id}", params={"api-version": API_VERSION},
                headers={"Authorization": f"Bearer {self._token()}"}, timeout=REST_TIMEOUT_S)
        if not r.ok:
            code = ""
            try:
                code = str(((r.json() or {}).get("error") or {}).get("code") or "")
            except (ValueError, AttributeError):
                pass
            raise ArmReadError(r.status_code, code[:60])
        body = r.json()
        name = body.get("displayName") if isinstance(body, dict) else None
        if not isinstance(name, str):
            raise RuntimeError("ARM's answer has no displayName")
        return name
