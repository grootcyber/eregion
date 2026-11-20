"""MID1 (#981): the certificate Azure puts on a managed identity it creates is no high card — set aside
from `entra-credential-added`, by the tenant's principal that does it, and said.

When a resource gets a system-assigned managed identity (a Logic App, a VM, a function), Azure creates
its service principal and puts a certificate on it. Entra ID logs it: « Add service principal », on a
`ServicePrincipal`, by the principal « Managed Service Identity » of the tenant (`InitiatedBy.app`:
its `servicePrincipalId` — the rule's `ActorId` —, its appId left empty), a credential
`KeyType=AsymmetricX509Cert, KeyUsage=Verify, DisplayName=CN=<guid>`. On Imladris, on 20/11, the drill's
Logic App made five such cards (six rows), one per creation, each time another principal: judged Wrong.

A row of the shipped `entra-credential-added` is set aside only when **all** of it holds:

- its `ActorId` is, without case, the object id of the tenant's « Managed Service Identity » principal,
  configured outside the repository (``EREGION_ENTRA_MSI_ACTOR_ID``, the watch's environment, Imladris's
  host.env — as CAN2's canary appid). **Never by its name**: `ActorName` is a display name, which anyone
  may give an application; the principal's object id in the tenant is Entra's, written by Entra;
- its operation is « Add service principal », its target type « ServicePrincipal »;
- every credential it added (`CredentialAdded`, the JSON text of the query's `tostring(Added)`) is a
  certificate of usage `Verify`: a key description `[KeyIdentifier=…, KeyType=AsymmetricX509Cert,
  KeyUsage=Verify, …]`, each key once. A secret (`Password`), another usage, a federated credential (an
  object, not a key description), a text unreadable or empty: the row stays a card;
- it is not marked as Glorfindel's (`GlorfindelIdentity`, `GlorfindelManaged`, set by `prepare_rows`):
  a credential added on Glorfindel's identity stays critical, whoever its author.

Without an id configured, or with one that is no object id, nothing is set aside, and it is said: in the
rule's status (``config``), once in the watch's log. What is set aside is counted in the rule's status
(``msi_certificate``), said in the watch's log, and shown on the rule's line in the console; never
silent. Only the shipped rule, by its name and its query to the byte (ATT1's shape, the RulePoller's
`shipped_query`): a rule of the client's layer that computes its columns otherwise keeps its cards.
The shipped query does not change (P1).
"""
from __future__ import annotations

import json
import os
import re

RULE = "entra-credential-added"
VARIABLE = "EREGION_ENTRA_MSI_ACTOR_ID"
OPERATION = "add service principal"
TARGET_TYPE = "serviceprincipal"
REASON = ("the certificate Azure puts on a managed identity it creates: by the tenant's « Managed Service "
          f"Identity » principal ({VARIABLE}), « Add service principal » on a ServicePrincipal, every "
          "credential an AsymmetricX509Cert of usage Verify (MID1)")
# The longest CredentialAdded text read: a managed identity's certificate is one key description of a
# few hundred characters; a text past it is not read (the row stays a card).
ADDED_MAX = 16 * 1024
_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# One key description, as Entra writes it in KeyDescription: `[Key=value, Key=value, …]`.
_DESCRIPTION = re.compile(r"\[(.*)\]", re.DOTALL)
_PAIR = re.compile(r"\s*([A-Za-z]+)=([^,\]]*)\s*")


def actor_id(environ=None) -> tuple[str, str]:
    """(the configured principal's object id, lowercase, or "", the problem: "" | "unset" |
    "malformed"). Read from the watch's environment at each pass. Never raises."""
    environ = os.environ if environ is None else environ
    try:
        value = str(environ.get(VARIABLE) or "").strip().lower()
    except Exception:
        return "", "unset"
    if not value:
        return "", "unset"
    if not _GUID.fullmatch(value):
        return "", "malformed"
    return value, ""


def _description(text) -> dict | None:
    """The pairs of one key description, or None — not one, a key twice (a display name that would
    carry `, KeyType=…` of its own), a pair unreadable."""
    if not isinstance(text, str):
        return None
    m = _DESCRIPTION.fullmatch(text.strip())
    if m is None:
        return None
    pairs: dict[str, str] = {}
    for part in m.group(1).split(","):
        p = _PAIR.fullmatch(part)
        if p is None:
            return None
        key = p.group(1).lower()
        if key in pairs:
            return None
        pairs[key] = p.group(2).strip()
    return pairs


def certificates_only(added) -> bool:
    """True when every credential the row added is a certificate of usage Verify — and there is one at
    least. `added`: the JSON text of the query's array (its list, read as well). Never raises."""
    if isinstance(added, str):
        if len(added) > ADDED_MAX:
            return False
        try:
            added = json.loads(added)
        except (ValueError, RecursionError):
            return False
    if not isinstance(added, list) or not added:
        return False
    for entry in added:
        pairs = _description(entry)
        if pairs is None:
            return False
        if pairs.get("keytype", "").lower() != "asymmetricx509cert":
            return False
        if pairs.get("keyusage", "").lower() != "verify":
            return False
    return True


def is_managed_identity_certificate(row, msi: str) -> bool:
    """Every condition of the module's docstring, on one row of the shipped rule."""
    if not msi or not isinstance(row, dict):
        return False
    if row.get("GlorfindelIdentity") is True or row.get("GlorfindelManaged") is True:
        return False
    if str(row.get("ActorId") or "").strip().lower() != msi:
        return False
    if str(row.get("EntraOperation") or "").strip().lower() != OPERATION:
        return False
    if str(row.get("TargetType") or "").strip().lower() != TARGET_TYPE:
        return False
    return certificates_only(row.get("CredentialAdded"))


def set_aside(rule_name: str, rows: list[dict], environ=None) -> tuple[list[dict], dict | None]:
    """(the rows that stay cards, what was said — None for any rule but the shipped one). Said:
    ``rows`` set aside, ``config`` the id's problem ("" when configured), ``reason``."""
    if rule_name != RULE:
        return rows, None
    msi, problem = actor_id(environ)
    # Without an id (problem said), `is_managed_identity_certificate` refuses every row: an empty id
    # would otherwise match a row whose ActorId the log left empty.
    kept = [r for r in rows if not is_managed_identity_certificate(r, msi)]
    return kept, {"rows": len(rows) - len(kept), "config": problem, "reason": REASON}
