"""Whether a rule under an earlier version's name is this NIC's to take off (SEC-H).

An earlier version ended our names with 6 or 8 hex of SHA-1: NICs named alike in VMs named alike meet
there, two VMs of two VNets often hold the same private address, and the NICs Azure lists are not all
of them (a scale set's are not listed): nothing read on Azure proves whose such a rule is. Only what is
proven is taken off (Jonathan's decision, 19/11) — a rule under an older name goes only when BOTH hold:
  - the VM's own state records that rule, on that NSG, for that NIC (a placement); and
  - the NIC's side of the rule (its destination inbound, its source outbound) names only addresses
    that placement recorded (`ips`, the address it had then: L26) or that the NIC holds now — each an
    address, never `*`, a range or a tag.
  - and no other VM's state records that rule on that NSG: under one name, two VMs' placements meet
    (their hash met), and the rule there is either's.
Anything else is left, and said with the command that takes it off by hand: on every path — the
release (`release_partial`), the undo of a placement by its name, the reset, the unblock, the
verifications (unknown, never verified), the NSG a bare NIC left, a deleted VM. Nothing here reads Azure
but `older_undo_refusal`, which reads the one rule a placement names. The new names (128 bits) are not
concerned: only Glorfindel writes them, for one NIC.
"""
from __future__ import annotations

import ipaddress

from glorfindel.providers.azure.nsg import _rule_name
from glorfindel.providers.azure.sdk import _enum_text


_OTHERS = ("others",)


def recorded_names(state: dict, blocks: list, resource_id: str = "") -> dict:
    """What this VM's own state records, by (NSG, NIC): for each placement (its isolation's by rules,
    its blocks'), the rule names it wrote and the addresses it addressed them to. The state is the
    VM's — found by its full id (SEC-H). Under `_OTHERS`: the (NSG, name) every OTHER VM's state
    records (`resource_id`, else the state's own)."""
    out: dict = {}
    rid = (resource_id or (state or {}).get("resource_id") or next(
        (e.get("resource_id") for e in blocks or [] if isinstance(e, dict) and e.get("resource_id")), "") or "")
    out[_OTHERS] = _claimed_by_others(str(rid))
    placements = [p for p in (state or {}).get("placements") or [] if isinstance(p, dict)]
    placements += [p for e in blocks or [] if isinstance(e, dict) for p in e.get("placements") or []
                   if isinstance(p, dict)]
    for p in placements:
        if p.get("kind") == "quarantine" or not p.get("nic_id") or not p.get("nsg_name"):
            continue
        names = {str(n).lower() for n in (p.get("rule_in"), p.get("rule_out"), p.get("rule")) if n}
        names |= {f"{n}-out" for n in names if not n.endswith("-out")}
        ips = {_address(ip) for ip in p.get("ips") or [] if isinstance(ip, str)} - {""}
        k = ((str(p.get("nsg_rg") or "").lower(), str(p["nsg_name"]).lower()), str(p["nic_id"]).rstrip("/").lower())
        out.setdefault(k, []).append((names, ips))
    return out


def _claimed_by_others(resource_id: str) -> set[tuple]:
    """(NSG, rule name) that the local state of another VM than `resource_id` records."""
    from glorfindel.response.state import active_blocks, active_isolations
    mine = resource_id.rstrip("/").lower()
    out: set[tuple] = set()
    for e in active_isolations() + active_blocks():
        if not mine or str(e.get("resource_id") or "").rstrip("/").lower() == mine:
            continue
        for p in e.get("placements") or []:
            if not isinstance(p, dict) or p.get("kind") == "quarantine" or not p.get("nsg_name"):
                continue
            k = (str(p.get("nsg_rg") or "").lower(), str(p["nsg_name"]).lower())
            for n in (p.get("rule_in"), p.get("rule_out"), p.get("rule")):
                if n:
                    out |= {(k, str(n).lower()), (k, f"{str(n).lower().removesuffix('-out')}-out")}
    return out


def is_older_name(name: str) -> bool:
    """A name an earlier version wrote: ended (before `-out`) by 6 or 8 hex of SHA-1."""
    mark = str(name or "").lower().removesuffix("-out").rsplit("-", 1)[-1]
    return len(mark) in (6, 8) and all(c in "0123456789abcdef" for c in mark)


def _address(value: str) -> str:
    """One host address, normalized ("" for anything else: `*`, a range, a tag)."""
    text = str(value or "").strip()
    if "/" in text:
        try:
            net = ipaddress.ip_network(text, strict=False)
        except ValueError:
            return ""
        return str(net.network_address) if net.num_addresses == 1 else ""
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        return ""


def _own_side(rule) -> list[str]:
    side = "destination" if _enum_text(getattr(rule, "direction", "")) == "inbound" else "source"
    single = getattr(rule, f"{side}_address_prefix", None)
    return ([single] if single else []) + list(getattr(rule, f"{side}_address_prefixes", None) or [])


def older_taken(rule, nsg_rg: str, nsg_name: str, nic_id: str, current_ips, placed: dict) -> bool:
    """The rule (under an older name of this NIC) is the NIC's to take off: its state records it on
    this NSG for this NIC, and its side of it names only addresses that placement recorded or the NIC
    holds now. See the module."""
    k = ((nsg_rg.lower(), nsg_name.lower()), nic_id.rstrip("/").lower())
    name = _rule_name(rule).lower()
    values = [_address(v) for v in _own_side(rule)]
    if not values:
        return False                       # no address on its side: every address
    if (k[0], name) in placed.get(_OTHERS, set()):
        return False                       # another VM's state records it there too
    now = {_address(ip) for ip in current_ips or []} - {""}
    return any(name in names and set(values) <= (ips | now) for names, ips in placed.get(k, []))


def older_judge(nsg_rg: str, nsg_name: str, nic_id: str, current_ips, placed: dict):
    """`older_taken` for one NIC's view of one NSG: `judge(rule) -> bool`."""
    return lambda rule: older_taken(rule, nsg_rg, nsg_name, nic_id, current_ips, placed)


def older_left(nsg_rg: str, nsg_name: str, rule, nic_short: str, unverified: str) -> str:
    """What a rule under an older name left in place says: why, and how to take it off by hand."""
    name = _rule_name(rule)
    return (f"{nsg_rg}/{nsg_name}/{name} laissée : nom d'une version antérieure (partagé par les cartes dont le "
            f"hash s'est rencontré), que l'état de la VM n'enregistre pas pour {nic_short} à ces adresses — rien "
            f"ne prouve qu'elle est la sienne. Si elle l'est : az network nsg rule delete -g {nsg_rg} "
            f"--nsg-name {nsg_name} -n {name} ; {unverified}")


def older_undo_refusal(network, nsg_rg: str, nsg_name: str, name: str, nic_id: str, nic_short: str,
                       placed: dict, unverified: str) -> str:
    """Before a placement's rule is taken off by its name: "" to go on; else why it stays (said). Only
    for an older name — the rule under it read and judged (`older_taken`): written over since by a
    homonym whose hash met, it is no longer the placement's. Gone (404): nothing to take off."""
    if not is_older_name(name):
        return ""
    from glorfindel.providers.azure.sdk import _is_not_found
    try:
        rule = network.security_rules.get(nsg_rg, nsg_name, name)
    except Exception as exc:
        if _is_not_found(exc):
            return ""
        return f"{nsg_rg}/{nsg_name}/{name} : règle d'un nom d'une version antérieure illisible ({str(exc)[:120]}), {unverified}"
    if older_taken(rule, nsg_rg, nsg_name, nic_id, (), placed):
        return ""
    return older_left(nsg_rg, nsg_name, rule, nic_short, unverified)
