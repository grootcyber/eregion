"""The client's network as the discovery read it (SEC2b, #1089; decisions of 23/11, 3, 4 and 9).

The discovery (glorfindel/discovery.py) reads, read-only, on the watch's subscription: the address
spaces of the VNets and of their subnets, and the client's public IPs — every public IP and public IP
prefix (a NIC's, a NAT gateway's, a load balancer's frontend, one not attached), and the frontends of
the load balancers, public and private (glorfindel/providers/azure/client_network.py) — and (SEC2c) the
network interfaces, their VM, their addresses and whether they forward packets: what tells one host of
the exposed zone (glorfindel/exposed_zone.py). A store written before SEC2c, without them, tells none. Kept in the
watch's own directory, `runs/glorfindel/network/client_network.json` (`STORE_PARTS`), with the time of
the read and what could not be read — never in ~/.glorfindel (below, « Its writer »).

An address of the client's network is never blocked (glorfindel/response/policy.py, `protection`).

**A list that can't be trusted** (decision 4): never read, unreadable, its last read failed, a read
partial (a listing not read keeps the value of the read before, `save`), dated more than
`FUTURE_SKEW_S` ahead, or older than `MAX_AGE_S` — `Snapshot.degraded` says which, and the guard says it on every
card that holds a block, the watch on its banner and on a card of its own (`CARD_TYPE`). Blocks
outside the Internet are refused all the same: the shipped private ranges and `never_block` stay
protected, and what an older read listed stays protected too (the most prudent wins); an address
neither private nor known of the client stays blockable — during the outage, an address of a VNet
outside the private ranges, never read, can be blocked again: said.

**A named network's object** (`{vnet: …}`, `{subnet: …}`, glorfindel/config_networks.py) is resolved
here, by its exact name — two VNets of one name are no exact name: unresolved, like a name not found,
which counts as a list that can't be trusted. Each change of what a name designates is said, on the
console and on Discord (a card, `CHANGE_TYPE`), and in the watch's log.

**Its writer: the watch alone.** The ranges that decide the guard are never read from a file the console
writes: the console and the bot mount ~/.glorfindel writable (docs/design/file-actions-signee.md §1.5),
and a range taken out of a file there would have made its address blockable, with no request. The list
lives in `runs/glorfindel/`, which the watch alone mounts writable (SEC18); the console mounts it
read-only, the bot its `network/` subdirectory only, read-only (docker-compose.yml) — the CLI they run
reads it there too. docs/design/modele-de-menace.md, §2.
"""
from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from eregion_core import runs_layout

logger = logging.getLogger("glorfindel.client_network")

# runs/glorfindel/network/client_network.json, from the working directory as every reader of runs/ (the
# services' /app; the operator's checkout) — the watch's directory, never ~/.glorfindel.
STORE_PARTS = ("network", "client_network.json")
_STORE = runs_layout.dir_of(runs_layout.GLORFINDEL).joinpath(*STORE_PARTS)

# The proposal of SEC2b: read every 10 minutes; a list older than an hour is no longer trusted —
# six reads missed, never one Azure hiccup. Its address spaces move with a deployment, not a minute.
READ_INTERVAL_S = 600.0
MAX_AGE_S = 3600.0
FUTURE_SKEW_S = 60.0      # a read time further ahead than this: the list is not trusted
_LISTS = ("vnets", "public_ips", "prefixes", "frontends", "nics")   # nics: SEC2c, the exposed zone's hosts

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
    nics: tuple = ()          # SEC2c: each NIC's VM, private addresses, and whether it forwards packets
    unread: tuple = ()
    error: str = ""
    named: dict = field(default_factory=dict)
    kept: dict = field(default_factory=dict)     # a listing not read: the time its kept value was read
    listed: tuple = ()        # SEC2c: the listings the store holds (a version before SEC2c wrote no `nics`)

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
            parts = "; ".join(f"{u.get('what')} : {u.get('error')}"
                              + (f" — la liste lue à {self.kept[u['key']][:16]} gardée"
                                 if self.kept.get(u.get("key")) else "") for u in self.unread)
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


# The review of SEC2b (SEC2c, reprise 1): the last write of the list that failed in this process (a
# directory docker made as root, a disk full), by its path — "" once a write passes. Read back by `load`:
# the guard of the watch then says « liste non écrite », never « jamais lue », and an older file still on
# disk is no fresh list. Another process (the console, the CLI) reads the disk alone: the watch's card
# says it there (glorfindel/client_network_watch.py).
_UNWRITTEN: dict[str, str] = {}


def unwritten(why: str, path: Path | None = None) -> None:
    """Note (`why`) or clear ("") the last write of the list that failed, in this process."""
    key = str(path or _STORE)
    if why:
        _UNWRITTEN[key] = why
    else:
        _UNWRITTEN.pop(key, None)


def load(now: datetime | None = None, path: Path | None = None) -> Snapshot:
    """The store, read and judged. Never raises: what can't be read is a state (decision 4)."""
    path = path or _STORE
    failed_write = _UNWRITTEN.get(str(path), "")
    if not path.exists():
        return Snapshot(state="failed", error=failed_write) if failed_write else Snapshot(state="absent")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("pas une table JSON")
        lists = {k: tuple(x for x in data.get(k) or [] if isinstance(x, dict))
                 for k in _LISTS + ("unread",)}
    except (OSError, ValueError) as exc:
        return Snapshot(state="unreadable", error=f"{type(exc).__name__}: {str(exc)[:160]}")
    read_at = str(data.get("read_at") or "")
    when = _parse(read_at)
    age = ((now or datetime.now(timezone.utc)) - when).total_seconds() if when else None
    error = failed_write or str(data.get("error") or "")
    kept = data.get("kept") if isinstance(data.get("kept"), dict) else {}
    if error:
        state = "failed"
    elif when is None:
        state, error = "unreadable", "heure de lecture absente"
    elif age is not None and age < -FUTURE_SKEW_S:
        # A read « in the future » is no fresh one: a clock wrong, or a file written ahead (review).
        state, error = "unreadable", f"heure de lecture dans le futur ({read_at[:19]})"
    elif age is None or age > MAX_AGE_S:
        state = "stale"
    else:
        state = "partial" if lists["unread"] else "fresh"
    named = data.get("named") if isinstance(data.get("named"), dict) else {}
    return Snapshot(state=state, read_at=read_at if when else "", age_s=age, error=error, named=named,
                    kept=kept, listed=tuple(k for k in _LISTS if k in data), **lists)


def _stored(path: Path) -> dict:
    """The store as written, {} when absent or unreadable."""
    try:
        body = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return {}
    return body if isinstance(body, dict) else {}


def save(read: dict, at: datetime, networks: dict | None = None, path: Path | None = None) -> Snapshot:
    """Write a read of the provider (`vnets`, `public_ips`, `prefixes`, `frontends`, `unread`) as the
    list now known, with what each named network's object designates — the snapshot it makes.

    A listing the read could not make (`unread`, its `key`) keeps what the store before held for it, with
    the time that value was read (`kept`): a 429 on the public IPs never empties them — a NAT gateway's
    address the read before protected stays protected (the review of SEC2b)."""
    from glorfindel.response.state import _atomic_write_text
    path = path or _STORE
    body = {k: list(read.get(k) or []) for k in _LISTS + ("unread",)}
    before, kept = _stored(path), {}
    before_kept = before.get("kept") if isinstance(before.get("kept"), dict) else {}   # SEC2c, reprise 2
    for k in {u.get("key") for u in body["unread"]} & set(_LISTS):
        if isinstance(before.get(k), list) and before[k]:
            body[k] = before[k]
            kept[k] = str(before_kept.get(k) or before.get("read_at") or "")
    body["read_at"], body["kept"] = at.isoformat(), kept
    snap = Snapshot(state="fresh", read_at=body["read_at"], age_s=0.0, listed=_LISTS,
                    **{k: tuple(body[k]) for k in _LISTS + ("unread",)})
    body["named"] = {n.name: (snap.resolve(n)[0] or None) for n in (networks or {}).values() if n.is_object}
    _atomic_write_text(path, json.dumps(body, indent=1, default=str))
    return load(at, path)


def note_failure(why: str, at: datetime, path: Path | None = None) -> Snapshot:
    """A read that failed: the list known so far kept, said failed — never an empty list."""
    from glorfindel.response.state import _atomic_write_text
    path = path or _STORE
    body = _stored(path)
    body.update(error=why[:300], failed_at=at.isoformat())
    _atomic_write_text(path, json.dumps(body, indent=1, default=str))
    return load(at, path)
