"""An older version's isolation left on an NSG that governs nothing (ORPH2, #1113).

Before the placements (L24), an isolation wrote a deny any/any under two FIXED names — the
connector's `ISOLATION_RULE_NAME` (`glorfindel-isolation-deny-all`, inbound) and the same with
`-out` — on what was then the NIC's own NSG. Its state lost, the NIC taken off that NSG (our
quarantine, its tags lost, then left bare by someone), the pair stays on an NSG that governs no
NIC and no subnet: no release finds it (no NIC leads there), the orphan sweep neither (no NIC hash
in the name), and once that NSG is put back on a NIC, it cuts that VM.

The name alone never proves whose it is (SEC-H: another tool, another Glorfindel host): it is
said, never taken off — Jonathan's decision, 23/11. Read only; the card is the watch's
(glorfindel/dormant_isolations.py).
"""
from __future__ import annotations

from glorfindel.providers.azure.nsg import _rule_name
from glorfindel.providers.azure.sdk import _enum_text, _is_not_found
from glorfindel.response.ids import _parse_nsg_resource_id, _subscription_of
from glorfindel.response.policy import _ERR_MAX, _first_line


def _fixed_denies(nsg, isolation_name: str) -> list[dict]:
    """The denies of `nsg` under the fixed names of an older version's isolation, by name."""
    fixed = {isolation_name.lower(), f"{isolation_name}-out".lower()}
    return sorted(({"name": _rule_name(r), "direction": _enum_text(getattr(r, "direction", "")),
                    "priority": getattr(r, "priority", None)}
                   for r in (getattr(nsg, "security_rules", None) or [])
                   if _rule_name(r).lower() in fixed and _enum_text(getattr(r, "access", "")) == "deny"),
                  key=lambda r: r["name"].lower())


def _attached_ids(items) -> list[str]:
    return sorted(i.rstrip("/") for i in (getattr(x, "id", None) for x in (items or [])) if i)


def dormant_entry(nsg, isolation_name: str) -> dict:
    """What the card of one NSG says: its fixed-name denies, and what it governs now — the
    NICs and the subnets it is attached to, as Azure gives them on the NSG."""
    return {"nsg_id": nsg.id.rstrip("/"), "rules": _fixed_denies(nsg, isolation_name),
            "nics": _attached_ids(getattr(nsg, "network_interfaces", None)),
            "subnets": _attached_ids(getattr(nsg, "subnets", None))}


class DormantMixin:
    """The older version's fixed names, found on the NSG listing (part of AzureConnector)."""

    def find_dormant_isolations(self, nsgs: list | None = None, said=()) -> list[dict]:
        """Each NSG holding a deny under a fixed name of an older version's isolation, with
        what it governs (`dormant_entry`) — the watch says those that govern nothing. And each
        NSG of `said` (the ids whose card stands): listed without them, `rules` empty; missing
        from the listing, read by its id — `gone` (404), else `unread` (why): a listing that
        leaves an NSG out proves nothing (A0), its card stays. `nsgs`: the NSGs the watch's
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
