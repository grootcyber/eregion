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

On an NSG that governs the NIC (`view_judge`), the same names, read by the release, the unblock and the
reset: (a), or covering no other live NIC that NSG governs — whatever it covers now, its address moved
since (L26), turned into an allow or not (A0).
"""
from __future__ import annotations

from glorfindel.providers.azure.nsg import _deny_applies, _rule_name, _side_covers
from glorfindel.providers.azure.sdk import _enum_text
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


class OlderUnread(RuntimeError):
    """Whose a rule under an older name is can't be read (the NSG, the NICs): neither taken off nor
    read gone — said, the operation unverified."""


def view_judge(network, cache: dict, nsg_rg: str, nsg_name: str, nic_id: str, recorded: dict, own_nics=()):
    """For an NSG that governs the NIC: `judge(rule) -> bool`, whether a deny under one of its older
    names is the NIC's to take off — whatever it covers now (its address moved since: L26), as long as
    the state records it there, or it covers no other live NIC that NSG governs. Two NICs met on those
    names: a deny of an older name the NIC's address took over, or a homonym's on an NSG two VNets
    share, aimed at an address another live NIC holds, stays (SEC-H). The NSG read once, by its id;
    unreadable, nothing older is taken."""
    k = ((nsg_rg.lower(), nsg_name.lower()), nic_id.rstrip("/").lower())
    mine = {o.rstrip("/").lower() for o in (nic_id, *own_nics) if o}

    def judge(rule) -> bool:
        if _rule_name(rule).lower() in recorded.get(k, set()):
            return True
        try:
            key = ("older_nsg", nsg_rg.lower(), nsg_name.lower())
            if key not in cache:
                cache[key] = network.network_security_groups.get(nsg_rg, nsg_name)
            held = _governed(network, cache, cache[key])
        except Exception as exc:
            # Unknown, never « not ours »: read so, a verification said released with the pair there.
            raise OlderUnread(f"{nsg_name} : {_rule_name(rule)}, d'un nom d'une version antérieure, n'a pu être "
                              f"jugée (NSG ou cartes illisibles : {str(exc)[:120]})") from exc
        return not any(nid not in mine and _own_side_covers(rule, ip) for ip, nid in held.items())
    return judge


def _own_side_covers(rule, ip: str) -> bool:
    """The NIC's side of a rule (destination inbound, source outbound) takes `ip` in — a deny, or one
    turned into an allow: either way it is that NIC's flows it decides."""
    side = "destination" if _enum_text(getattr(rule, "direction", "")) == "inbound" else "source"
    return _side_covers(rule, side, [ip])
