"""The dossier of a block of an internal address (DOS3b, #1063; `docs/design/dossier-isolation.md` §4.6, §12,
the decisions of 23/11).

**A block executed alone has no dossier, but for an internal address**: a block is reversible, and its
card, its reasoning and its decision line (DOS2) already say why. An internal address is another matter —
« what did it cut? » counts, and the dossier keeps the cycle's facts for the human who asks.

**Internal**, in code: the private ranges (RFC 1918, and IPv6's unique local), the shared space of carrier
NAT (100.64.0.0/10), the link local, the loopback. **Not** the networks the discovery knows: the registry
of assets (`glorfindel/discovery.py`) keeps a VM's name, id and backend, never its VNet nor its subnets —
an address of the client's network outside these ranges reads public, until the discovery keeps them.
Today SEC2 refuses to block any of these ranges (`response/policy.py`, `NEVER_BLOCK_SHIPPED`): the scope
holds them all the same, should a provider or that list ever let one through.

**An address that cannot be read is never said internal nor public**: its dossier is not composed, and
says why (`compose: false`, never silence).

**Held** (the retention, Q7): while a block of the same VM and the same address is recorded
(`~/.glorfindel/blocks/`); the clock of 30 days starts at the first pass that sees it gone (the unblock).
Nothing moves while a block state cannot be read. Local files only: no call, no model; no gate imports it.
"""
from __future__ import annotations

import ipaddress

INTERNE, PUBLIQUE, ILLISIBLE = "interne", "publique", "illisible"
INTERNAL = (
    ("10.0.0.0/8", "privée (RFC 1918)"), ("172.16.0.0/12", "privée (RFC 1918)"),
    ("192.168.0.0/16", "privée (RFC 1918)"), ("100.64.0.0/10", "partage d'adresses (RFC 6598)"),
    ("169.254.0.0/16", "lien local"), ("127.0.0.0/8", "boucle locale"),
    ("fc00::/7", "privée d'IPv6 (RFC 4193)"), ("fe80::/10", "lien local d'IPv6"), ("::1/128", "boucle locale"),
)
_NETWORKS = tuple((ipaddress.ip_network(net), net, said) for net, said in INTERNAL)


def classify(ip) -> tuple[str, str]:
    """(`interne`, the range and what it is) | (`publique`, "") | (`illisible`, why) — one host address,
    read strictly; an IPv4 address written as IPv6 is that IPv4 address."""
    text = str(ip if ip is not None else "").strip()
    if not text:
        return ILLISIBLE, "aucune adresse dite par l'issue ni par le signal"
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return ILLISIBLE, f"ni une adresse IPv4 ni une adresse IPv6 : {text[:80]!r}"
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    for net, name, said in _NETWORKS:
        if addr.version == net.version and addr in net:
            return INTERNE, f"{name} : {said}"
    return PUBLIQUE, ""


def blocked_ip(state: dict) -> str:
    """The address the cycle blocked: the connector's own word (`outcome.ip`), else the signal's — the
    card's (`agent._executed_ip`)."""
    from glorfindel.agent import _executed_ip
    return _executed_ip(state)


def address(state: dict) -> dict:
    """The header's fields of a block: the address as read, its class, and by what (the range, or why)."""
    ip = blocked_ip(state)
    classe, par = classify(ip)
    return {"ip": str(ip or "")[:80], "adresse": classe, "adresse_par": par}


def canonical(ip) -> str:
    text = str(ip if ip is not None else "").strip()
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return text.lower()
    return str(addr.ipv4_mapped if addr.version == 6 and addr.ipv4_mapped is not None else addr)


def held(doc: dict, blocks: list[dict]) -> bool:
    """The dossier's block still recorded: an active block of its VM and its address (`active_blocks`). An
    address that could not be read is held by any block of its VM — which one is unknown."""
    rid, vm = str(doc.get("resource_id") or "").rstrip("/").lower(), str(doc.get("vm") or "").lower()
    mine, unread = canonical(doc.get("ip")), doc.get("adresse") == ILLISIBLE
    for b in blocks:
        theirs = str(b.get("resource_id") or "").rstrip("/").lower()
        if (theirs == rid if theirs else str(b.get("vm_name") or "").lower() == vm) and (
                unread or canonical(b.get("ip")) == mine):
            return True
    return False
