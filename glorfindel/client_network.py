"""The client's network as the discovery read it (SEC2b, #1089; decisions of 23/11, 3, 4 and 9).

The discovery (glorfindel/discovery.py) reads, read-only, on the watch's subscription: the address
spaces of the VNets and of their subnets, and the client's public IPs — every public IP and public IP
prefix (a NIC's, a NAT gateway's, a load balancer's frontend, one not attached), and the frontends of
the load balancers, public and private (glorfindel/providers/azure/client_network.py). Kept beside the
registry, in ~/.glorfindel/client_network.json, with the time of the read and what could not be read.

An address of the client's network is never blocked (glorfindel/response/policy.py, `protection`).

**A list that can't be trusted** (decision 4): never read, unreadable, its last read failed, a read
partial, or older than `MAX_AGE_S` — `Snapshot.degraded` says which, and the guard says it on every
card that holds a block, the watch on its banner and on a card of its own (`CARD_TYPE`). Blocks
outside the Internet are refused all the same: the shipped private ranges and `never_block` stay
protected, and what an older read listed stays protected too (the most prudent wins); an address
neither private nor known of the client stays blockable — during the outage, an address of a VNet
outside the private ranges, never read, can be blocked again: said.

**A named network's object** (`{vnet: …}`, `{subnet: …}`, glorfindel/config_networks.py) is resolved
here, by its exact name — two VNets of one name are no exact name: unresolved, like a name not found,
which counts as a list that can't be trusted. Each change of what a name designates is said, on the
console and on Discord (a card, `CHANGE_TYPE`), and in the watch's log.

**Its writer**: the watch. The console and the bot mount ~/.glorfindel writable too
(docs/design/file-actions-signee.md §1.5): forged, the file can add addresses never blocked, or leave
out the client's own — docs/design/modele-de-menace.md, SEC2.
"""
from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("glorfindel.client_network")

_STORE = Path.home() / ".glorfindel" / "client_network.json"

# The proposal of SEC2b: read every 10 minutes; a list older than an hour is no longer trusted —
# six reads missed, never one Azure hiccup. Its address spaces move with a deployment, not a minute.
READ_INTERVAL_S = 600.0
MAX_AGE_S = 3600.0

CARD_TYPE = "client_network_unreadable"
CHANGE_TYPE = "network_changed"
CARD_RESOURCE = "client-network"

_KIND_WORDS = {
    "nic": "IP publique d'une carte réseau",
    "nat_gateway": "IP publique de la passerelle NAT",
    "load_balancer": "IP publique d'un frontal d'équilibreur",
    "load_balancer_private": "frontal privé de l'équilibreur",
    "gateway": "IP publique d'une passerelle",
    "unattached": "IP publique non associée",
    "other": "IP publique",
}


def _short(rid: str) -> str:
    return str(rid or "").rstrip("/").rsplit("/", 1)[-1]


def _net(text) -> str:
    """A range read back from the store, canonical — "" when it is not one."""
    try:
        return str(ipaddress.ip_network(str(text).strip(), strict=False))
    except ValueError:
        return ""


def _parse(at: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class Snapshot:
    """The store as read: `state` one of fresh, stale, partial, failed, absent, unreadable."""
    state: str
    read_at: str = ""
    age_s: float | None = None
    vnets: tuple = ()
    public_ips: tuple = ()
    prefixes: tuple = ()
    frontends: tuple = ()
    unread: tuple = ()
    error: str = ""
    named: dict = field(default_factory=dict)

    def degraded(self) -> str:
        """Why this list can't be trusted, "" when it can (decision 4)."""
        if self.state == "absent":
            return "liste du réseau du client jamais lue (la découverte du réseau n'a pas tourné)"
        if self.state == "unreadable":
            return f"liste du réseau du client illisible ({self.error})"
        if self.state == "failed":
            return (f"dernière lecture du réseau du client en échec ({self.error})"
                    + (f" — la liste lue à {self.read_at[:16]} gardée" if self.read_at else ""))
        if self.state == "stale":
            return (f"liste du réseau du client périmée (lue il y a {int((self.age_s or 0) // 60)} min, "
                    f"limite {int(MAX_AGE_S // 60)} min)")
        if self.state == "partial":
            parts = "; ".join(f"{u.get('what')} : {u.get('error')}" for u in self.unread)
            return f"lecture du réseau du client partielle ({parts})"
        return ""

    def entries(self) -> list[tuple[str, str]]:
        """(range, what it is) of every address the read listed: the VNets, then the public IPs and
        prefixes, then the load balancers' frontends."""
        out: list[tuple[str, str]] = []
        for v in self.vnets:
            out += [(p, f"VNet {v.get('name')}") for p in map(_net, v.get("prefixes") or []) if p]
            for s in v.get("subnets") or []:
                out += [(p, f"sous-réseau {v.get('name')}/{s.get('name')}")
                        for p in map(_net, s.get("prefixes") or []) if p]
        for p in self.public_ips + self.prefixes:
            cidr = _net(p.get("address") or p.get("prefix"))
            owner = _short(p.get("attached_to") or p.get("id"))
            if cidr:
                out.append((cidr, f"{_KIND_WORDS.get(p.get('kind'), _KIND_WORDS['other'])} {owner}".strip()))
        for f in self.frontends:
            if cidr := _net(f.get("address")):
                out.append((cidr, f"{_KIND_WORDS['load_balancer_private']} {_short(f.get('lb'))}"))
        return out

    def resolve(self, net) -> tuple[list[str], str]:
        """(ranges, "") of a named network's object, by its exact name — or ([], why)."""
        if self.state in ("absent", "unreadable") or (self.state == "failed" and not self.read_at):
            return [], "réseau du client non lu"
        want_vnet, _, want_subnet = (net.subnet or net.vnet).partition("/")
        found = [v for v in self.vnets if str(v.get("name", "")).lower() == want_vnet.lower()]
        if not found:
            return [], f"VNet « {want_vnet} » introuvable"
        if len(found) > 1:
            return [], f"{len(found)} VNet portent le nom « {want_vnet} » : aucun nom exact"
        if not net.subnet:
            return [p for p in map(_net, found[0].get("prefixes") or []) if p], ""
        subnets = [s for s in found[0].get("subnets") or [] if str(s.get("name", "")).lower() == want_subnet.lower()]
        if len(subnets) != 1:
            return [], f"sous-réseau « {net.subnet} » introuvable"
        return [p for p in map(_net, subnets[0].get("prefixes") or []) if p], ""

    def origins_of(self, objects) -> list[str]:
        """The ranges of `objects` for an expected origin (ADM1, COR1): from a fresh, whole read only —
        an origin relaxes a card, so never from a list too old. Unresolved: nothing expected of it."""
        if self.state != "fresh":
            return []
        return [c for n in objects for c in self.resolve(n)[0]]


def load(now: datetime | None = None, path: Path | None = None) -> Snapshot:
    """The store, read and judged. Never raises: what can't be read is a state (decision 4)."""
    path = path or _STORE
    if not path.exists():
        return Snapshot(state="absent")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("pas une table JSON")
        lists = {k: tuple(x for x in data.get(k) or [] if isinstance(x, dict))
                 for k in ("vnets", "public_ips", "prefixes", "frontends", "unread")}
    except (OSError, ValueError) as exc:
        return Snapshot(state="unreadable", error=f"{type(exc).__name__}: {str(exc)[:160]}")
    read_at = str(data.get("read_at") or "")
    when = _parse(read_at)
    age = ((now or datetime.now(timezone.utc)) - when).total_seconds() if when else None
    error = str(data.get("error") or "")
    if error:
        state = "failed"
    elif when is None:
        state, error = "unreadable", "heure de lecture absente"
    elif age is None or age > MAX_AGE_S:
        state = "stale"
    else:
        state = "partial" if lists["unread"] else "fresh"
    named = data.get("named") if isinstance(data.get("named"), dict) else {}
    return Snapshot(state=state, read_at=read_at if when else "", age_s=age, error=error, named=named, **lists)


def save(read: dict, at: datetime, networks: dict | None = None, path: Path | None = None) -> Snapshot:
    """Write a read of the provider (`vnets`, `public_ips`, `prefixes`, `frontends`, `unread`) as the
    list now known, with what each named network's object designates — the snapshot it makes."""
    from glorfindel.response.state import _atomic_write_text
    body = {k: list(read.get(k) or []) for k in ("vnets", "public_ips", "prefixes", "frontends", "unread")}
    body["read_at"] = at.isoformat()
    snap = Snapshot(state="fresh", read_at=body["read_at"], age_s=0.0,
                    **{k: tuple(v) for k, v in body.items() if k != "read_at"})
    body["named"] = {n.name: (snap.resolve(n)[0] or None) for n in (networks or {}).values() if n.is_object}
    _atomic_write_text(path or _STORE, json.dumps(body, indent=1, default=str))
    return load(at, path)


def note_failure(why: str, at: datetime, path: Path | None = None) -> Snapshot:
    """A read that failed: the list known so far kept, said failed — never an empty list."""
    from glorfindel.response.state import _atomic_write_text
    path = path or _STORE
    try:
        body = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        body = body if isinstance(body, dict) else {}
    except (OSError, ValueError):
        body = {}
    body.update(error=why[:300], failed_at=at.isoformat())
    _atomic_write_text(path, json.dumps(body, indent=1, default=str))
    return load(at, path)
