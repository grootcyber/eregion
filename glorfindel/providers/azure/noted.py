"""What an isolation notes of the VM, for the lift after a restore (LEV2, #690;
docs/design/levee-probation.md §8, Q16): its disks, the original ones a restore in place leaves as
evidence, and the rules of each customer NSG the isolation read — both from the reads the isolation
made anyway, never a call more (the machine of the invariants counts its faults by call)."""
from __future__ import annotations


def disks_at_isolation(vm, previous: dict | None) -> dict:
    """The VM's managed disks, noted at its isolation (LEV2, docs/design/levee-probation.md §8):
    {"os": id, "data": [ids], "ids": [all]} — or {"ids": [], "why"} when the VM read names none.
    A state that already notes them keeps its own: a VM isolated again before its release has the
    disks of its first isolation, those a restore in place leaves as evidence. Read from the VM
    the isolation already read, never written to (Glorfindel never touches them)."""
    kept = (previous or {}).get("disks_at_isolation")
    if isinstance(kept, dict) and kept.get("ids"):
        return kept
    storage = getattr(vm, "storage_profile", None)
    os_disk = str(getattr(getattr(getattr(storage, "os_disk", None), "managed_disk", None), "id", "") or "")
    data = [str(getattr(getattr(d, "managed_disk", None), "id", "") or "")
            for d in getattr(storage, "data_disks", None) or []]
    data = [d for d in data if d]
    if not os_disk and not data:
        return {"ids": [], "why": "la VM lue à l'isolement ne nomme aucun disque managé"}
    return {"os": os_disk, "data": data, "ids": [d for d in [os_disk, *data] if d]}


def nsg_rules_at_isolation(seen: dict, previous: dict | None, resource_id: str) -> dict:
    """The rules of each customer NSG the isolation read, noted with it (Q16, LEV2): {NSG id,
    lowercase: {rule name, lowercase: rule_record}}. A rule DELETED later from a shared NSG is judged
    on what it covered then (glorfindel/providers/azure/door.py). An NSG the state already notes
    keeps its first list. Read by the plan anyway: no call more."""
    from glorfindel.providers.azure.door_rules import rule_record
    from glorfindel.response.ids import _subscription_of
    sub = _subscription_of(resource_id)
    out: dict = {}
    for (rg, name), rules in seen.items():
        if not rg or not name:
            continue
        nid = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/networkSecurityGroups/{name}"
        out[nid.lower()] = {str(getattr(r, "name", "") or "").lower(): rule_record(r) for r in rules or []}
    kept = (previous or {}).get("nsg_rules_at_isolation")
    if isinstance(kept, dict):
        out.update({k: v for k, v in kept.items() if isinstance(v, dict)})
    return out
