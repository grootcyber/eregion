"""A rule of an NSG, and whether it reaches a VM (LEV2, #690; docs/design/levee-probation.md §4.1):
on a shared NSG only a rule that covers the VM is a gesture on it. Read from an SDK object, a
request body of the activity log, or what the isolation noted (`nsg_rules_at_isolation`)."""
from __future__ import annotations

import ipaddress
import json


def _k(resource_id) -> str:
    return str(resource_id or "").strip().rstrip("/").lower()


def _side(rule: dict, side: str) -> tuple[list[str], list[str]]:
    """(prefixes, ASG ids) of one side of a rule, from an SDK object's fields or a request body's."""
    pre = [rule.get(f"{side}_address_prefix")] + list(rule.get(f"{side}_address_prefixes") or [])
    asgs = [a if isinstance(a, str) else a.get("id") if isinstance(a, dict) else getattr(a, "id", None)
            for a in (rule.get(f"{side}_application_security_groups") or [])]
    return [str(p) for p in pre if p], [_k(a) for a in asgs if a]


def _rule_fields(source) -> dict | None:
    """A rule as {direction, source_…, destination_…}: from an SDK object, or a request body
    (`{"properties": {"direction", "sourceAddressPrefix", …}}`, camelCase). None: nothing read."""
    if source is None:
        return None
    if isinstance(source, str):
        try:
            source = json.loads(source)
        except ValueError:
            return None
    if isinstance(source, dict):
        p = source.get("properties") if isinstance(source.get("properties"), dict) else source
        camel = {"direction": "direction",
                 "sourceAddressPrefix": "source_address_prefix",
                 "sourceAddressPrefixes": "source_address_prefixes",
                 "destinationAddressPrefix": "destination_address_prefix",
                 "destinationAddressPrefixes": "destination_address_prefixes",
                 "sourceApplicationSecurityGroups": "source_application_security_groups",
                 "destinationApplicationSecurityGroups": "destination_application_security_groups"}
        out = {snake: p.get(c, p.get(snake)) for c, snake in camel.items()}
        return out if any(v for v in out.values()) else None
    fields = ("direction", "source_address_prefix", "source_address_prefixes", "destination_address_prefix",
              "destination_address_prefixes", "source_application_security_groups",
              "destination_application_security_groups")
    out = {f: getattr(source, f, None) for f in fields}
    out["direction"] = str(getattr(out["direction"], "value", out["direction"]) or "")
    return out


def rule_record(rule) -> dict:
    """A rule of an NSG as the isolation notes it (`nsg_rules_at_isolation`, Q16): its name, its
    direction, its prefixes and ASG ids — plain JSON, read back by rule_covers."""
    out: dict = {"name": str(getattr(rule, "name", "") or "")}
    for key, value in (_rule_fields(rule) or {}).items():
        if key.endswith("application_security_groups"):
            ids = [a if isinstance(a, str) else a.get("id") if isinstance(a, dict) else getattr(a, "id", None)
                   for a in value or []]
            out[key] = [str(i) for i in ids if i]
        elif key.endswith("prefixes"):
            out[key] = [str(x) for x in value or []]
        else:
            out[key] = str(value) if value not in (None, "") else None
    return out


def rule_covers(rule: dict | None, ips: list[str], asgs: set[str]) -> bool:
    """The rule reaches the VM: its destination (inbound) or source (outbound) holds one of its
    addresses, `*`, a tag (not evaluated: it counts), a prefix holding one, or one of its ASGs. A
    rule that can't be read, or names neither side, counts."""
    if not rule:
        return True
    d = str(rule.get("direction") or "").lower()
    sides = ["destination"] if d == "inbound" else ["source"] if d == "outbound" else ["destination", "source"]
    named = False
    for side in sides:
        prefixes, side_asgs = _side(rule, side)
        named = named or bool(prefixes or side_asgs)
        if set(side_asgs) & asgs:
            return True
        for p in prefixes:
            if p.strip().lower() in ("*", "any"):
                return True
            try:
                net = ipaddress.ip_network(p.strip(), strict=False)
            except ValueError:
                return True                   # a service tag: VirtualNetwork, or one not evaluated here
            if any(_in(ip, net) for ip in ips):
                return True
    return not named


def _in(ip: str, net) -> bool:
    try:
        return ipaddress.ip_address(ip) in net
    except ValueError:
        return False
