"""The hold read once, in the test's world (RSM2a, #1033; docs/design/reaffirmation.md §2.3, E1, E2, E5, E7).

What Glorfindel holds — an isolation of a VM, its block of the attacker — read NIC by NIC from the fake
Azure's own rules (`fake_azure`), never from the code's verification nor from its marks (A0). The note's
table is the reference (Q1, Jonathan's decision of 21/11):

- **intact**: a rule of the hold that still refuses what it must, by its content — a deny, every protocol
  and port, the attacker (any peer, for an isolation) on its side, each of its NIC's addresses as they are
  now on the other (anyone, for a perimeter pair) — on an NSG that governs the NIC;
- **gone**: absent; present but refusing no longer what it must — turned into an allow (Q2: gone, as the
  code reads it), narrowed to a port or a protocol, aimed at an address its NIC no longer has —; or lying
  on an NSG that no longer governs the NIC (its own NSG taken off it, the subnet's taken off the subnet: E7);
- **bypassed**: intact, but a rule of someone else's evaluated before it lets through what it refuses —
  judged by the flows, the hold's intact rules evaluated first (`bypassed()` in the machine, L1V);
- **unknown**: on an NSG the identity can't read (a role removed: `fake.unreadable`; one out of sight, I1S).

Two leniencies, each where the code reads more than a name can tell, and each the safe way (they make the
oracle demand less, never more): a NIC in our quarantine has its block's rules read wherever they lie — the
code reads them behind it, for the lift to come (`held_missing`, A0) —, and an isolation of a NIC is any of
our isolation denies that cuts it off by content, its two directions possibly on two NSGs (the code wants
both on one, under its names: one of ours a homonym's, or an earlier version's, is still ours here).
"""
from __future__ import annotations

from dataclasses import dataclass

from glorfindel import actions

from .fake_azure import ATTACKER, _side, key, nsg_id

INTACT, GONE, BYPASSED, UNKNOWN = "intacte", "partie", "contournée", "inconnue"


@dataclass(frozen=True)
class Piece:
    """One rule of a hold, where it lies (the NSG's key, the rule's lowercase name), the NICs it holds
    (their keys), its direction, whether it is the perimeter pair's, and its state in the test's world."""
    nsg: str
    name: str
    nics: frozenset
    direction: str
    perimeter: bool
    state: str


def _values(rule: dict, side: str) -> list[str]:
    return [v for v in [rule.get(f"{side}_address_prefix")] + list(rule.get(f"{side}_address_prefixes") or []) if v]


def _anyone(rule: dict, side: str) -> bool:
    values = _values(rule, side)
    return not values or any(v.strip().lower() in ("*", "any") for v in values)


def refuses(rule: dict | None, direction: str, peer: str | None, own: list[str] | None) -> bool:
    """The rule refuses every way in `direction`: a deny, every protocol, every port; on the peer's side
    `peer` (anyone, when None); on the NIC's side each of `own` (anyone, when None). The test's own
    restatement of a rule's content (`fake_azure._side`), never the code's helpers."""
    if rule is None or str(rule.get("access", "")).lower() != "deny":
        return False
    if str(rule.get("direction", "")).lower() != direction:
        return False
    if str(rule.get("protocol") or "*").lower() not in ("*", "any"):
        return False
    ports = [rule.get("destination_port_range")] + list(rule.get("destination_port_ranges") or [])
    if not any(str(p or "").strip().lower() in ("*", "any", "0-65535") for p in ports):
        return False
    peer_side, own_side = ("source", "destination") if direction == "inbound" else ("destination", "source")
    if not (_anyone(rule, peer_side) if peer is None else _side(rule, peer_side, peer)):
        return False
    return _anyone(rule, own_side) if own is None else all(_side(rule, own_side, ip) for ip in own)


def unreadable(m, nsg: str | None) -> bool:
    """An NSG the identity can't read now: its role removed (`fake.unreadable`), or out of sight (I1S)."""
    return bool(nsg) and (key(nsg) in m.fake.unreadable or key(nsg) in getattr(m, "out_of_sight", {}))


def _chain(m, nic: dict) -> set[str]:
    """The NSGs that govern the NIC now: its own, its subnet's."""
    return {key(g) for g in (nic["nsg"], m.fake.subnets[key(nic["subnet"])]["nsg"]) if g}


def _in_quarantine(nic: dict) -> bool:
    return bool(nic["nsg"]) and actions._is_quarantine_nsg(nic["nsg"])


def _rule(m, nsg: str, name: str) -> dict | None:
    return m.fake.nsgs.get(nsg, {}).get("rules", {}).get(name.lower())


def _placement_state(m, nsg: str, name: str, direction: str, nic: dict, recorded: list | None) -> str:
    """A placement's rule for its NIC: unknown where an NSG is unread, gone unless it refuses the attacker
    for the NIC's addresses as they are now — never those the placement recorded (`recorded`: a NIC whose
    address changed is open at the new one, L26) —, on an NSG that governs the NIC (behind our quarantine,
    wherever it lies)."""
    if unreadable(m, nsg) or any(unreadable(m, g) for g in _chain(m, nic)):
        return UNKNOWN
    if not refuses(_rule(m, nsg, name), direction, ATTACKER, list(nic["ips"])):
        return GONE
    if nsg not in _chain(m, nic) and not _in_quarantine(nic):
        return GONE
    return INTACT


def block_pieces(m, vm: str) -> list[Piece]:
    """Each rule the VM's block of the attacker names — its placements, in and out, and, merged with it or
    alone, its perimeter pair — with the NICs it holds and its state. Empty without a block. A placement of
    a NIC that is no longer the VM's is left out, as the code leaves it."""
    entry = next((e for e in actions._load_block_entries(vm) if e.get("ip") == ATTACKER), None)
    if entry is None:
        return []
    nics = {key(n["id"]): n for n in m._nics(vm)} if key(vm) in m.fake.vms else {}     # a VM deleted: none
    out = []
    for p in entry.get("placements") or []:
        if not p.get("rule"):
            continue
        nsg = key(nsg_id(p["nsg_rg"], p["nsg_name"]))
        nic = nics.get(key(p.get("nic_id") or ""))
        held = [nic] if nic else [n for n in nics.values() if not p.get("nic_id") and set(p.get("ips") or []) & set(n["ips"])]
        for name, direction in ((p["rule"], "inbound"), (f'{p["rule"]}-out', "outbound")):
            for n in held:
                out.append(Piece(nsg, name.lower(), frozenset({key(n["id"])}), direction, False,
                                 _placement_state(m, nsg, name, direction, n, p.get("ips"))))
    if entry.get("scoped") is False and entry.get("rule") and "/" in (entry.get("nsg") or ""):
        nsg = key(nsg_id(*entry["nsg"].split("/", 1)))
        # The pair holds the VM's NICs it governs: on its subnet, or carrying it as their own NSG (I5S). None
        # any more — the subnet's NSG taken off, or another put in its place (E7) — it holds nothing: gone.
        governed = frozenset(k for k, n in nics.items() if nsg in _chain(m, n))
        for name, direction in ((entry["rule"], "inbound"), (f'{entry["rule"]}-out', "outbound")):
            if unreadable(m, nsg):
                state = UNKNOWN
            elif not refuses(_rule(m, nsg, name), direction, ATTACKER, None) or not governed:
                state = GONE
            else:
                state = INTACT
            out.append(Piece(nsg, name.lower(), governed, direction, True, state))
    return out


def block_rules(m, vm: str) -> dict[tuple[str, str], str]:
    """Each rule of the VM's block, (NSG, name) → its state: a rule read two ways (a placement named for two
    NICs) reads unknown if either is unread (A0: never gone on a guess), else gone if either is gone."""
    out: dict = {}
    rank = {UNKNOWN: 0, GONE: 1, INTACT: 2}
    for p in block_pieces(m, vm):
        k = (p.nsg, p.name)
        out[k] = p.state if k not in out or rank[p.state] < rank[out[k]] else out[k]
    return out


def _held(pieces: list[Piece]) -> str | None:
    """A NIC's state from the pieces that hold it: intact if one of ours refuses each direction, unknown if
    one of them is unread, gone otherwise; None when nothing of the hold is meant to hold it."""
    if not pieces:
        return None
    if all(any(p.state == INTACT and p.direction == d for p in pieces) for d in ("inbound", "outbound")):
        return INTACT
    return UNKNOWN if any(p.state == UNKNOWN for p in pieces) else GONE


def block_nics(m, vm: str) -> dict[str, str]:
    """NIC by NIC (its short name), the state of the VM's block: intact, gone, unknown — a NIC nothing of the
    block is meant to hold (one added since, one off its perimeter) is left out."""
    pieces = block_pieces(m, vm)
    out = {}
    for n in m._nics(vm) if key(vm) in m.fake.vms else []:
        state = _held([p for p in pieces if key(n["id"]) in p.nics])
        if state:
            out[n["id"].rsplit("/", 1)[-1]] = state
    return out


def _isolating(m, nsg: str, nic: dict) -> dict[str, set]:
    """Our isolation denies on this NSG that cut the NIC off, by direction: every protocol and port, any peer,
    each of the NIC's addresses."""
    found: dict[str, set] = {"inbound": set(), "outbound": set()}
    for name, r in m.fake.nsgs.get(nsg, {}).get("rules", {}).items():
        if not name.startswith("glorfindel-iso"):
            continue
        for direction in found:
            if refuses(r, direction, None, list(nic["ips"])):
                found[direction].add((nsg, name))
    return found


def isolation_hold(m, vm: str) -> tuple[dict[str, str], set]:
    """NIC by NIC (its short name), the state of the VM's isolation — intact: our quarantine NSG on it, whole
    (`_quarantine_intact`, the test's reading), or our denies cutting it off both ways on the NSGs that govern
    it; unknown: one of those NSGs unread; gone otherwise. And our denies found intact, for `bypassed()`."""
    states, intact = {}, set()
    for n in m._nics(vm):
        short = n["id"].rsplit("/", 1)[-1]
        chain = _chain(m, n)
        if any(unreadable(m, g) for g in chain):
            states[short] = UNKNOWN
            continue
        if _in_quarantine(n) and m._quarantine_intact(key(n["nsg"])):
            states[short] = INTACT
            continue
        found: dict[str, set] = {"inbound": set(), "outbound": set()}
        for g in sorted(chain):
            for d, rules in _isolating(m, g, n).items():
                found[d] |= rules
        if found["inbound"] and found["outbound"]:
            states[short] = INTACT
            intact |= found["inbound"] | found["outbound"]
        else:
            states[short] = GONE
    return states, intact
