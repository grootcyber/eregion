"""The client's network, read for the guard of the blocks (SEC2b, #1089): read-only, on the watch's
subscription, what the identity's Reader role sees — four paged listings, nothing written.

- `virtualNetworks.listAll`: each VNet's address space and its subnets' prefixes;
- `publicIPAddresses.listAll`: every public IP allocated, and what holds it (a NIC, a NAT gateway, a
  load balancer's frontend, a gateway, none);
- `publicIPPrefixes.listAll`: every public prefix (a NAT gateway's, for one);
- `loadBalancers.listAll`: the frontends' private addresses (their public ones are above).

A listing refused or failing never fails the others: it is said (`unread`, its code and its reason,
as the audit says a public IP it can't read, IPS2a) and the list is partial — a list that can't be
trusted (glorfindel/client_network.py). What a Reader role scoped below the subscription does not see,
Azure leaves out of a listing without a word: the read lists what the watch can see, never more.
"""
from __future__ import annotations

from glorfindel.providers.azure.public_ips import _read_failure


def _pip_kind(pip) -> str:
    """What holds a public IP: a NIC's, a NAT gateway's, a load balancer's frontend, a gateway's."""
    if getattr(getattr(pip, "nat_gateway", None), "id", None):
        return "nat_gateway"
    holder = str(getattr(getattr(pip, "ip_configuration", None), "id", None) or "").lower()
    if not holder:
        return "unattached"
    for marker, kind in (("/networkinterfaces/", "nic"), ("/loadbalancers/", "load_balancer"),
                         ("gateways/", "gateway"), ("/bastionhosts/", "gateway"), ("/azurefirewalls/", "gateway")):
        if marker in holder:
            return kind
    return "other"


def _pip_holder(pip) -> str:
    """The resource that holds a public IP (its NIC, its gateway, its load balancer), "" when none."""
    nat = getattr(getattr(pip, "nat_gateway", None), "id", None)
    held = str(getattr(getattr(pip, "ip_configuration", None), "id", None) or "")
    for part in ("/ipConfigurations/", "/frontendIPConfigurations/", "/ipconfigurations/",
                 "/frontendipconfigurations/"):
        held = held.split(part, 1)[0]
    return str(nat or held)


def _space_prefixes(obj) -> list[str]:
    """An address space's or a subnet's prefixes, each once, in their order."""
    space = getattr(obj, "address_space", None)
    out = list(getattr(space, "address_prefixes", None) or []) if space is not None else []
    out += [getattr(obj, "address_prefix", None)] + list(getattr(obj, "address_prefixes", None) or [])
    return list(dict.fromkeys(p for p in out if p))


def _read_vnets(network) -> list[dict]:
    return [{"id": v.id, "name": v.name, "prefixes": _space_prefixes(v),
             "subnets": [{"name": s.name, "prefixes": _space_prefixes(s)} for s in getattr(v, "subnets", None) or []]}
            for v in network.virtual_networks.list_all()]


def _read_public_ips(network) -> list[dict]:
    return [{"id": p.id, "address": p.ip_address, "kind": _pip_kind(p), "attached_to": _pip_holder(p)}
            for p in network.public_ip_addresses.list_all() if getattr(p, "ip_address", None)]


def _read_public_prefixes(network) -> list[dict]:
    return [{"id": p.id, "prefix": p.ip_prefix, "kind": "nat_gateway" if getattr(
                getattr(p, "nat_gateway", None), "id", None) else "other",
             "attached_to": str(getattr(getattr(p, "nat_gateway", None), "id", None) or "")}
            for p in network.public_ip_prefixes.list_all() if getattr(p, "ip_prefix", None)]


def _read_frontends(network) -> list[dict]:
    return [{"id": f.id, "address": f.private_ip_address, "lb": lb.id}
            for lb in network.load_balancers.list_all()
            for f in getattr(lb, "frontend_ip_configurations", None) or []
            if getattr(f, "private_ip_address", None)]


CLIENT_NETWORK_READS = (("vnets", "VNet", _read_vnets), ("public_ips", "IP publiques", _read_public_ips),
                        ("prefixes", "préfixes d'IP publiques", _read_public_prefixes),
                        ("frontends", "frontaux d'équilibreur", _read_frontends))


def read_client_network(network) -> dict:
    """`{"vnets", "public_ips", "prefixes", "frontends": [...], "unread": [{what, code, error}]}` —
    each listing on its own: one refused is said, the others read."""
    out: dict = {"unread": []}
    for key, what, read in CLIENT_NETWORK_READS:
        try:
            out[key] = read(network)
        except Exception as exc:
            code, reason = _read_failure(exc)
            out[key] = []
            out["unread"].append({"what": what, "key": key, "code": code, "error": reason})
    return out


class ClientNetworkMixin:
    """The client's network (part of AzureConnector)."""

    def client_network(self) -> dict:
        """`read_client_network` on the subscription; {} in a dry run (nothing read)."""
        if self.dry_run:
            return {}
        self._ensure_clients()
        return read_client_network(self._network)
