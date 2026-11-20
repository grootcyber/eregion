"""The public IP of each network interface, read for the audit (IPS1a, #931): read-only, one
`publicIPAddresses.get` per address and per call, in the address's own resource group.

A read that fails never fails the audit: the address is said `null`, with its reason (`error`, in
French) and its code (`code`, IPS2a: what a page tests). A read address carries no code.
"""
from __future__ import annotations

from glorfindel.providers.azure.restore_rights import masked
from glorfindel.providers.azure.sdk import _is_iam_error, _is_not_found
from glorfindel.response.ids import _parse_vm_resource_id
from glorfindel.response.policy import _first_line

# How much of Azure's refusal the card carries: its first line, without an id.
_REASON_MAX = 200

NOT_FOUND = "introuvable"
NOT_ALLOCATED = "pas d'adresse allouée (une IP dynamique sur une VM arrêtée ?)"

# The code of a failed read (IPS2a, #950), beside its French text: a page tests it, never the text.
FORBIDDEN, GONE, UNALLOCATED, UNREADABLE = "forbidden", "not_found", "not_allocated", "unreadable"
CODES = (FORBIDDEN, GONE, UNALLOCATED, UNREADABLE)


def _read_failure(exc: BaseException) -> tuple[str, str]:
    """(code, reason) of an address that could not be read: a refusal, a missing resource, or
    Azure's words."""
    if _is_not_found(exc):
        return GONE, NOT_FOUND
    said = masked(_first_line(exc))[:_REASON_MAX]
    if _is_iam_error(str(exc)) or getattr(exc, "status_code", None) == 403:
        return FORBIDDEN, f"lecture refusée (droits) : {said}"
    return UNREADABLE, f"illisible : {said}"


def public_ip_ids(nic) -> list[str]:
    """The public IP ids on the NIC's IP configurations, each once, in their order."""
    out: list[str] = []
    for c in getattr(nic, "ip_configurations", None) or []:
        pip = getattr(getattr(c, "public_ip_address", None), "id", None)
        if pip and pip.lower() not in {p.lower() for p in out}:
            out.append(pip)
    return out


def read_public_ips(network, ids: list[str], cache: dict) -> list[dict]:
    """`[{"address": …}]` for these ids, or `{"address": None, "error": …, "code": …}` for one that
    can't be read (`code` in CODES). `cache` (lowercase id → element) holds what this call already
    read: an address is read once, however many NICs name it."""
    out: list[dict] = []
    for pid in ids or []:
        k = pid.lower()
        if k not in cache:
            try:
                rg, name = _parse_vm_resource_id(pid)
                address = getattr(network.public_ip_addresses.get(rg, name), "ip_address", None)
                cache[k] = ({"address": address} if address
                            else {"address": None, "error": NOT_ALLOCATED, "code": UNALLOCATED})
            except Exception as exc:
                code, reason = _read_failure(exc)
                cache[k] = {"address": None, "error": reason, "code": code}
        out.append(dict(cache[k]))
    return out
