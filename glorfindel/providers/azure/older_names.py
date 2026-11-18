"""Whether a rule under an earlier version's name is this NIC's, on an NSG the NIC does not carry
(SEC-H, review): the NSG a bare NIC left, or any NSG of the subscription for a deleted VM.

An earlier version ended our names with 6 or 8 hex of SHA-1: NICs named alike in VMs named alike meet
there, and on an NSG read through no NIC, nothing says whose a name is. Two VMs of two VNets often hold
the same private address (10.0.0.4): a deny aimed at it is no proof either. Such a rule is this NIC's
only when
  (a) the VM's own state records it on this NSG for this NIC (`recorded_names`), or
  (b) it is a deny aimed at the NIC's addresses that covers the address of no other live NIC this NSG
      governs (attached to it, or on one of its subnets) — the VM's own NICs aside.
Anything else is left and said. Read only; the NICs listed once per operation (`cache`).
"""
from __future__ import annotations

from glorfindel.providers.azure.nsg import _deny_applies, _rule_name
from glorfindel.response.ids import _parse_nsg_resource_id


def recorded_names(state: dict, blocks: list) -> dict[tuple, set[str]]:
    """The rule names this VM's own state records, by (NSG, NIC): its isolation's placements and
    its blocks'. The state is the VM's — found by its full id (SEC-H) —, so a name it records for a
    NIC is that NIC's, an older one included: whatever it covers now, it is ours to take off."""
    out: dict[tuple, set[str]] = {}
    placements = [p for p in (state or {}).get("placements") or [] if isinstance(p, dict)]
    placements += [p for e in blocks or [] if isinstance(e, dict) for p in e.get("placements") or []
                   if isinstance(p, dict)]
    for p in placements:
        if p.get("kind") == "quarantine" or not p.get("nic_id") or not p.get("nsg_name"):
            continue
        names = {str(n).lower() for n in (p.get("rule_in"), p.get("rule_out"), p.get("rule")) if n}
        names |= {f"{n}-out" for n in names if not n.endswith("-out")}
        k = ((str(p.get("nsg_rg") or "").lower(), str(p["nsg_name"]).lower()), str(p["nic_id"]).rstrip("/").lower())
        out.setdefault(k, set()).update(names)
    return out


def _governed(network, cache: dict, nsg) -> dict[str, str]:
    """address → NIC (lowercase) of every live NIC this NSG governs: attached to it, or on one of its
    subnets. Raises when the NICs can't be listed."""
    if "older_nics" not in cache:
        cache["older_nics"] = list(network.network_interfaces.list_all())
    nsg_key = (getattr(nsg, "id", "") or "").rstrip("/").lower()
    subnets = {s.id.rstrip("/").lower() for s in (getattr(nsg, "subnets", None) or []) if getattr(s, "id", None)}
    out: dict[str, str] = {}
    for n in cache["older_nics"]:
        own = (getattr(getattr(n, "network_security_group", None), "id", None) or "").rstrip("/").lower()
        for cfg in getattr(n, "ip_configurations", None) or []:
            subnet = (getattr(getattr(cfg, "subnet", None), "id", None) or "").rstrip("/").lower()
            ip = getattr(cfg, "private_ip_address", None)
            if ip and (own == nsg_key or subnet in subnets):
                out[ip] = n.id.rstrip("/").lower()
    return out


def older_not_ours(network, cache: dict, nsg, rule, nic_id: str, ips: list[str] | None,
                   recorded: dict, own_nics=()) -> str:
    """Why a rule under an older name on `nsg` is not this NIC's to take off ("" when it is): see
    the module. `ips`: the NIC's addresses (a deleted VM's: those its records give it); `own_nics`:
    the VM's live NICs, never "another"."""
    n_rg, n_name = _parse_nsg_resource_id(nsg.id)
    k = ((n_rg.lower(), n_name.lower()), nic_id.rstrip("/").lower())
    if _rule_name(rule).lower() in recorded.get(k, set()):
        return ""                                                   # (a) its state records it there
    if not ips:
        return "aucune adresse ne la lie à cette carte"
    if not _deny_applies(rule, ips):
        return "elle ne refuse pas les adresses de la carte"
    try:
        held = _governed(network, cache, nsg)
    except Exception:
        return "les cartes de l'abonnement ne se lisent pas : on ne sait pas qui d'autre elle refuse"
    mine = {o.rstrip("/").lower() for o in (nic_id, *own_nics) if o}
    other = sorted(ip for ip, nid in held.items() if nid not in mine and _deny_applies(rule, [ip]))
    if other:                                                       # (b) another live NIC behind it
        return (f"elle refuse aussi {other[0]}, l'adresse d'une autre carte que ce NSG gouverne — "
                "peut-être son homonyme, dont le hash a rencontré le sien")
    return ""
