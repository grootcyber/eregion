"""The exposed zone (SEC2c, #1107; decisions of 23/11, 6, 7 and 8): where a block of ONE host is possible
again.

`network_zones.exposed` (glorfindel/config_zones.py) is the fourth layer of `policy.address_layers`:
after Azure's platform and the loopback, after `never_block`, after the expected origins (SEC2d, 0.7);
before the rest of the client's network, never blocked. An address the zone holds is blockable — by the
agent alone only where the attacked VM's mode lets a block of the Internet run alone (decide's gate of the
mode: `human_only` never blocks alone), by an approval, by the command line — **only when the code says it
designates one host** (`judge`), from the configuration and the discovery, never from what the target
writes (a line of its log):

- the client's list is trusted: fresh, whole, every listing of this version read — a list that can't be
  trusted refuses every block outside the Internet (decision 4), the exposed zone's too;
- never an address the discovery knows as shared (`shared`): a NAT gateway's public IP, a load balancer's
  frontend (public or private), a gateway's (VPN, application gateway, bastion, firewall), a public IP held
  by nothing or by what the read does not tell, an address of a public prefix (more than one address);
- never an appliance: a VM one of whose NICs forwards packets (`enable_ip_forwarding`, as the rule poller
  reads it — SEC-A4, `private_ip_owners`), each of its addresses, private and public;
- never an address two VMs hold (two VNets reuse one);
- never an address Azure reserves in a subnet the discovery read (its first four, its last in IPv4), nor
  the zone's own network or broadcast address;
- **in the client's VNets, one host only on a proof** (the review of SEC2c, `_unproven_in_vnet`): a NIC
  the listing reads holds it, in a subnet read that Azure does not reserve to a service
  (`RESERVED_SUBNETS`, held whole). An address no known NIC holds — Azure Firewall's, Bastion's, a VPN
  gateway's private address, an Application Gateway's private frontend (not read by its name: held as no
  NIC's), a uniform scale set's instance — or outside every subnet read is held. An address outside every
  VNet and every public IP of the client — a partner's host — is one.

Otherwise the address stays the client's network: a card for a human (`protected_address`), the
connector refusing the block, the reason saying why.

**The block expires** (decision 7): a block written on an address of the zone carries `mark` in its entry
(~/.glorfindel/blocks/<vm>.json, `exposed`): the zone, when it expires (`EXPIRY_S`, 24 h), and who held the
address then (`holder_of`). The watch lifts it at the deadline, or as soon as the discovery sees the address
held by another VM (glorfindel/exposed_blocks.py).
"""
from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timedelta, timezone

from glorfindel.response.policy import CLIENT, EXPOSED, Protection

logger = logging.getLogger("glorfindel.exposed_zone")

EXPIRY_S = 24 * 3600.0          # decision 7: a block of the exposed zone is lifted after 24 h, then re-judged

_SHARED_WORDS = {
    "nat_gateway": "IP publique d'une passerelle NAT",
    "load_balancer": "IP publique d'un frontal d'équilibreur",
    "gateway": "IP publique d'une passerelle (VPN, passerelle applicative, bastion, pare-feu)",
    "unattached": "IP publique que rien ne tient",
    "other": "IP publique dont la lecture ne dit pas ce qui la tient",
}


def _addr(text):
    try:
        a = ipaddress.ip_address(str(text).strip())
    except ValueError:
        return None
    return a.ipv4_mapped if a.version == 6 and a.ipv4_mapped is not None else a


def _vm_of(snap) -> dict[str, str]:
    """NIC id (lowercase) → the VM it is attached to (lowercase; the NIC's own id when on none)."""
    return {str(n.get("id", "")).rstrip("/").lower(): str(n.get("vm") or n.get("id") or "").rstrip("/").lower()
            for n in snap.nics}


def _forwarders(snap) -> set[str]:
    """The VMs (lowercase) one of whose NICs forwards packets: appliances."""
    by_nic = _vm_of(snap)
    return {by_nic[str(n.get("id", "")).rstrip("/").lower()] for n in snap.nics if n.get("forwarding") is True}


def holders(snap) -> dict:
    """Address → the VMs (lowercase ids) that hold it: a NIC's private addresses, a NIC's public IP."""
    by_nic = _vm_of(snap)
    out: dict = {}
    for n in snap.nics:
        vm = by_nic[str(n.get("id", "")).rstrip("/").lower()]
        for ip in n.get("private_ips") or []:
            if (a := _addr(ip)) is not None:
                out.setdefault(a, set()).add(vm)
    for p in snap.public_ips:
        nic = str(p.get("attached_to") or "").rstrip("/").lower()
        if p.get("kind") == "nic" and (a := _addr(p.get("address"))) is not None:
            out.setdefault(a, set()).add(by_nic.get(nic, nic))
    return out


def holder_of(ip: str, snap) -> str:
    """Who holds `ip` now: the VMs' ids, sorted, joined by « , » — "" when the read knows none."""
    return ",".join(sorted(holders(snap).get(_addr(ip), set())))


def _shared_said(addr, snap) -> str:
    """What the discovery knows `addr` as, when it designates more than one host — "" otherwise."""
    for p in snap.public_ips:
        if _addr(p.get("address")) == addr and p.get("kind") != "nic":
            return f"{_SHARED_WORDS.get(p.get('kind'), _SHARED_WORDS['other'])} ({_short(p.get('attached_to') or p.get('id'))})"
    for f in snap.frontends:
        if _addr(f.get("address")) == addr:
            return f"frontal privé de l'équilibreur {_short(f.get('lb'))}"
    for p in snap.prefixes:
        try:
            if addr in ipaddress.ip_network(str(p.get("prefix")), strict=False):
                return f"adresse du préfixe public {_short(p.get('id'))} (plusieurs adresses)"
        except ValueError:
            continue
    return ""


def _short(rid) -> str:
    return str(rid or "").rstrip("/").rsplit("/", 1)[-1]


def _reserved(addr, zone: str, snap) -> str:
    """An address Azure reserves in a subnet the discovery read, or the zone's network or broadcast."""
    for v in snap.vnets:
        for s in v.get("subnets") or []:
            for prefix in s.get("prefixes") or []:
                try:
                    net = ipaddress.ip_network(str(prefix), strict=False)
                except ValueError:
                    continue
                if addr.version == net.version and addr in net:
                    rank = int(addr) - int(net.network_address)
                    if rank < 4 or (net.version == 4 and addr == net.broadcast_address):
                        return f"adresse réservée par Azure dans le sous-réseau {v.get('name')}/{s.get('name')}"
    net = ipaddress.ip_network(zone, strict=False)
    if net.version == 4 and net.prefixlen <= 30 and addr in (net.network_address, net.broadcast_address):
        return f"adresse de réseau ou de diffusion de la zone {zone}"
    return ""


def not_one_host(addr, zone: str, snap) -> str:
    """Why `addr`, in the exposed range `zone`, does not designate one host — "" when it does."""
    from glorfindel.client_network import _LISTS
    if missing := [k for k in _LISTS if k not in snap.listed]:
        return (f"lecture du réseau du client sans {', '.join(missing)} (écrite par une version antérieure) : "
                "un seul hôte non vérifiable avant la prochaine lecture")
    if said := _shared_said(addr, snap):
        return f"{said} : pas un seul hôte"
    known = _vm_of(snap)
    for p in snap.public_ips:
        if (_addr(p.get("address")) == addr and p.get("kind") == "nic"
                and str(p.get("attached_to") or "").rstrip("/").lower() not in known):
            return ("IP publique d'une carte réseau que la lecture des cartes ne connaît pas : un seul hôte "
                    "non vérifiable")
    held = holders(snap).get(addr, set())
    names = ", ".join(_short(v) for v in sorted(held))
    if held & _forwarders(snap):
        return f"adresse d'une appliance ({names} : une carte qui transfère les paquets) : pas un seul hôte"
    if len(held) > 1:
        return f"tenue par {len(held)} VM ({names}) : pas un seul hôte"
    return _reserved(addr, zone, snap) or _unproven_in_vnet(addr, snap, held)


# The subnets Azure reserves to its own services — a VPN or ExpressRoute gateway, Azure Firewall, Bastion,
# Route Server: their private addresses are on no NIC the listing reads. Held whole (the review of SEC2c).
RESERVED_SUBNETS = frozenset({"gatewaysubnet", "azurefirewallsubnet", "azurefirewallmanagementsubnet",
                              "azurebastionsubnet", "routeserversubnet"})


def _unproven_in_vnet(addr, snap, held: set) -> str:
    """An address of the client's VNets is one host only on a proof: a NIC the listing reads holds it, in a
    subnet the discovery read that Azure does not reserve to a service. Held otherwise — the private
    addresses of Azure Firewall, Bastion, a VPN gateway, an Application Gateway's private frontend, a
    uniform scale set's instances are on no NIC of `networkInterfaces.listAll` (the review of SEC2c): « no
    NIC known » is never « one host ». An address outside every VNet (a partner's, a public IP of the
    client's NIC) is judged by the public listings above."""
    in_vnet = False
    for v in snap.vnets:
        for prefix in v.get("prefixes") or []:
            try:
                in_vnet = in_vnet or (addr in ipaddress.ip_network(str(prefix), strict=False))
            except (ValueError, TypeError):
                continue
    subnet = None
    for v in snap.vnets:
        for s in v.get("subnets") or []:
            for prefix in s.get("prefixes") or []:
                try:
                    if addr in ipaddress.ip_network(str(prefix), strict=False):
                        subnet = (v.get("name"), str(s.get("name") or ""))
                except (ValueError, TypeError):
                    continue
    if subnet is not None and subnet[1].lower() in RESERVED_SUBNETS:
        return (f"sous-réseau {subnet[0]}/{subnet[1]}, réservé par Azure à un service (passerelle, pare-feu, "
                "bastion) : pas un seul hôte")
    if not in_vnet and subnet is None:
        return ""
    if subnet is None:
        return "adresse d'un VNet du client hors de tout sous-réseau lu : un seul hôte non vérifiable"
    if not held:
        return (f"aucune carte réseau connue ne la tient dans {subnet[0]}/{subnet[1]} (un pare-feu, un "
                "bastion, une passerelle, un groupe identique de VM ?) : un seul hôte non vérifiable")
    return ""


def contents(zone: str, snap) -> list[str]:
    """What the exposed range `zone` holds that is no single host, as the watch says it at its start: the
    shared addresses the discovery read in it, the appliances' addresses."""
    net = ipaddress.ip_network(zone, strict=False)
    found = [a for a in {_addr(p.get("address")) for p in snap.public_ips}
             | {_addr(f.get("address")) for f in snap.frontends} | set(holders(snap))
             if a is not None and a.version == net.version and a in net]
    out = [f"{a} ({why.removesuffix(' : pas un seul hôte')})" for a in sorted(found)
           if (why := not_one_host(a, zone, snap)) and "réservée" not in why and "diffusion" not in why]
    for p in snap.prefixes:
        try:
            other = ipaddress.ip_network(str(p.get("prefix")), strict=False)
        except ValueError:
            continue
        if other.version == net.version and other.overlaps(net):
            out.append(f"{other} (préfixe public {_short(p.get('id'))}, plusieurs adresses)")
    return out


def judge(addr, zone: str, source: str, snap, degraded: str) -> Protection:
    """An address the exposed range `zone` holds: EXPOSED (blockable) when it designates one host and the
    client's list is trusted; else held as the client's network, its source saying why."""
    why = ("liste du réseau du client non fiable" if degraded else "") or not_one_host(addr, zone, snap)
    if why:
        return Protection(entry=zone, layer=CLIENT, source=f"{source} — {why}", degraded=degraded)
    return Protection(entry=zone, layer=EXPOSED, source=source)


def mark(ip: str, now: datetime | None = None) -> dict | None:
    """What a block's entry keeps of the exposed zone (`exposed`), None when `ip` is not one of its hosts:
    the zone, its source, when the block expires, who held the address.

    Judged again a moment after `blockable_ip` (the connector keeps its anchored call): **never a block of
    the zone without its deadline** (the review of SEC2c). The judgement fails (the config, the list), or
    the zone now holds the address back (the list degraded between the two, a NAT gateway read since):
    ProtectedAddressError — the block refused before any write, never written as an Internet one."""
    from glorfindel.client_network import load
    from glorfindel.response.policy import ProtectedAddressError, _first_line, protection
    try:
        snap = load()
        held = protection(ip, snap=snap)
    except Exception as exc:
        raise ProtectedAddressError(
            f"blocage de {ip} refusé : sa zone ne se juge plus au moment de l'écrire ({_first_line(exc)}) — "
            "jamais un blocage de la zone exposée sans son échéance") from exc
    if held.layer == CLIENT and held.source.startswith("zone exposée"):
        raise ProtectedAddressError(
            f"blocage de {ip} refusé : réseau du client ({held.entry}, {held.source}) — jugée de nouveau au "
            "moment de l'écrire, la zone exposée la retient")
    if held.layer != EXPOSED:
        return None
    now = now or datetime.now(timezone.utc)
    return {"zone": held.entry, "source": held.source, "at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=EXPIRY_S)).isoformat(), "holder": holder_of(ip, snap)}
