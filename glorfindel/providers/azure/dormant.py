"""An older version's isolation left on an NSG that governs nothing (ORPH2, #1113).

Before the placements (L24), an isolation wrote a deny any/any under two FIXED names — the
connector's `ISOLATION_RULE_NAME` (`glorfindel-isolation-deny-all`, inbound) and the same with
`-out` — on what was then the NIC's own NSG. Its state lost, the NIC taken off that NSG (our
quarantine, its tags lost, then left bare by someone), the pair stays on an NSG that governs no
NIC and no subnet: no release finds it (no NIC leads there), the orphan sweep neither (no NIC hash
in the name), and once that NSG is put back on a NIC, it cuts that VM.

The same version, on a subnet's NSG (shared), wrote its deny scoped to the VM's address under
names suffixed by the VM — `glorfindel-isolation-deny-all-<vm>` (inbound) and `-<vm>-out` — so
that several VMs could be isolated there. Left on an NSG that governs nothing since, they are as
forgotten: said too, the VM they named on the card (ORPH2b, #1126, Jonathan's decision, 24/11).

The name alone never proves whose it is (SEC-H: another tool, another Glorfindel host; the VM it
names, a hint only): it is said, never taken off — Jonathan's decision, 23/11. Read only; the
card is the watch's (glorfindel/dormant_isolations.py). Never another name: our quarantine's
(`glorfindel-quarantine-deny-*`), our placements' (`glorfindel-iso-*`, the orphan sweep's).
"""
from __future__ import annotations

from glorfindel.providers.azure.nsg import _rule_name
from glorfindel.providers.azure.sdk import _enum_text, _is_not_found
from glorfindel.response.ids import _parse_nsg_resource_id, _subscription_of
from glorfindel.response.policy import _ERR_MAX, _first_line


def _older_deny(r, isolation_name: str) -> dict | None:
    """One rule of an older version's isolation, by its name: a deny under a fixed name, or
    under a name suffixed by a VM (ORPH2b) — then `vm`, the VM it named, from the rule's own
    direction (`-<vm>-out` outbound; a VM named `…-out` inbound stays whole). None otherwise:
    an allow cuts nothing; any other name is no older isolation."""
    name = _rule_name(r)
    low, base = name.lower(), isolation_name.lower()
    if _enum_text(getattr(r, "access", "")) != "deny":
        return None
    direction = _enum_text(getattr(r, "direction", ""))
    rule = {"name": name, "direction": direction, "priority": getattr(r, "priority", None)}
    if low in (base, f"{base}-out"):
        return rule
    if not low.startswith(f"{base}-"):
        return None
    vm = name[len(base) + 1:]
    if direction == "outbound" and vm.lower().endswith("-out"):
        vm = vm[:-len("-out")]
    return {**rule, "vm": vm}


def _older_denies(nsg, isolation_name: str) -> list[dict]:
    """The denies of `nsg` under the names of an older version's isolation — fixed, or
    suffixed by a VM —, by name."""
    return sorted((d for d in (_older_deny(r, isolation_name) for r in (getattr(nsg, "security_rules", None) or []))
                   if d is not None), key=lambda r: r["name"].lower())


def _attached_ids(items) -> list[str]:
    return sorted(i.rstrip("/") for i in (getattr(x, "id", None) for x in (items or [])) if i)


def dormant_entry(nsg, isolation_name: str) -> dict:
    """What the card of one NSG says: its older-name denies, and what it governs now — the
    NICs and the subnets it is attached to, as Azure gives them on the NSG."""
    return {"nsg_id": nsg.id.rstrip("/"), "rules": _older_denies(nsg, isolation_name),
            "nics": _attached_ids(getattr(nsg, "network_interfaces", None)),
            "subnets": _attached_ids(getattr(nsg, "subnets", None))}


class DormantMixin:
    """The older version's names, fixed or suffixed by a VM, found on the NSG listing (part of
    AzureConnector)."""

    def find_dormant_isolations(self, nsgs: list | None = None, said=()) -> list[dict]:
        """Each NSG holding a deny under a name of an older version's isolation (fixed, or
        suffixed by a VM), with what it governs (`dormant_entry`) — the watch says those that
        govern nothing. And each NSG of `said` (the ids whose card stands): listed without
        them, `rules` empty; missing from the listing, read by its id — `gone` (404), else
        `unread` (why): a listing that leaves an NSG out proves nothing (A0), its card stays. `nsgs`: the NSGs the watch's
        pass already listed, else listed here. Raises if they can't be listed. Writes nothing."""
        if self.dry_run:
            return []
        self._ensure_clients()
        listing = list(self._network.network_security_groups.list_all() if nsgs is None else nsgs)
        asked = {str(s).rstrip("/").lower() for s in said or ()}
        out, seen = [], set()
        for nsg in listing:
            k = nsg.id.rstrip("/").lower()
            seen.add(k)
            entry = dormant_entry(nsg, self.ISOLATION_RULE_NAME)
            if entry["rules"] or k in asked:
                out.append(entry)
        out += [self._said_nsg(k) for k in sorted(asked - seen)]
        return out

    def _said_nsg(self, nsg_id: str) -> dict:
        """An NSG whose card stands, missing from the listing: read by its id."""
        target = _subscription_of(nsg_id)
        if not target or target.lower() != (self._subscription_id or "").lower():
            return {"nsg_id": nsg_id, "unread": f"abonnement {target or '?'}, Glorfindel lit {self._subscription_id}"}
        try:
            nsg = self._network.network_security_groups.get(*_parse_nsg_resource_id(nsg_id))
        except Exception as exc:
            if _is_not_found(exc):
                return {"nsg_id": nsg_id, "gone": True}
            return {"nsg_id": nsg_id, "unread": _first_line(exc)[:_ERR_MAX]}
        return dormant_entry(nsg, self.ISOLATION_RULE_NAME)
