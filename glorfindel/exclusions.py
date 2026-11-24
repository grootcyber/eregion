"""CFG2 (#1128): what `exceptions[]` takes from a VM, said — never a VM gone silent.

An exclusion takes a VM out of the rules applied to every discovered VM (`auto_apply`), and out of
those rules only: a rule written for the VM (`assets: [<resource_id>]`) still watches it
(`RulePoller._targets`, glorfindel/detection_rules.py). Before CFG2 the console said nothing of it
on the card, and its audit counted such a rule « exclue ». Here, from the file and the rules alone
(nothing written, nothing read from Azure), for each VM a pattern or its name takes:

- ``all``: an entry says ``exclude_all`` — every rule applied to every VM, posture included;
- ``rules``: the rules applied to every VM it no longer watches (in the rules' order);
- ``auto_total``: how many such rules there are, enabled;
- ``still_watching``: the enabled rules written for this VM, which still watch it;
- ``posture``: the posture check set aside too (`posture` counts as a rule, glorfindel/posture.py);
- ``unknown``: names in ``exclude_rules`` that no rule bears (a typo excludes nothing);
- ``entries``: each entry that takes it — its pattern, its reason (``""``: none given), whether it
  is a pattern rather than the VM's name;
- ``said``: the band of its card, one line, the text the console writes through ``_attr``.

The view is read from the file the watch read at its start: an exclusion written since takes effect at
the watch's next start (the RulePoller keeps the config it read) — said in the console's band title.
"""
from __future__ import annotations

_PATTERN_CHARS = "*?["


def is_pattern(text: str) -> bool:
    """A pattern of fnmatch (`vm-dev-*`), not a VM's name: it may take a VM created tomorrow."""
    return any(c in text for c in _PATTERN_CHARS)


def _own(rule, vm_name: str, resource_id: str) -> bool:
    """A rule written for this VM — by its resource id, or by its name when the id is unknown."""
    rid = (getattr(rule, "resource_id", "") or "").rstrip("/").lower()
    if rid and resource_id:
        return rid == resource_id.rstrip("/").lower()
    name = (getattr(rule, "asset_name", "") or "") or rid.split("/")[-1]
    return bool(name) and name.lower() == vm_name.lower()


def exclusion_of(cfg, vm_name: str, resource_id: str, rules) -> dict | None:
    """What `exceptions[]` takes from this VM (module docstring), or None: no entry takes it."""
    entries = [e for e in getattr(cfg, "exceptions", None) or [] if e.matches(vm_name)]
    if not entries:
        return None
    on = [r for r in rules if getattr(r, "enabled", True)]
    auto = [r for r in on if getattr(r, "auto_apply", False)]
    excluded = [r.name for r in auto if any(e.excludes_rule(r.name) for e in entries)]
    known = {r.name for r in rules} | {"posture"}
    view = {
        "all": any(e.exclude_all for e in entries),
        "rules": excluded,
        "auto_total": len(auto),
        "still_watching": [r.name for r in on if not getattr(r, "auto_apply", False)
                           and _own(r, vm_name, resource_id)],
        "posture": any(e.excludes_rule("posture") for e in entries),
        "unknown": sorted({n for e in entries for n in e.exclude_rules if n not in known}),
        "entries": [{"pattern": e.asset_pattern, "reason": e.reason, "by_pattern": is_pattern(e.asset_pattern)}
                    for e in entries],
    }
    view["said"] = said(view)
    return view


def _rules(n: int) -> str:
    return f"{n} rule{'s' if n != 1 else ''}"


def said(view: dict) -> str:
    """The band of an excluded VM's card: what is taken from it, why, and what still watches it."""
    total, gone = view["auto_total"], view["rules"]
    if view["all"]:
        head = f"EXCLUDED from all {_rules(total)} applied to every VM"
    elif gone:
        head = f"EXCLUDED from {', '.join(gone)} ({len(gone)} of the {_rules(total)} applied to every VM)"
    else:
        head = "EXCLUDED from no rule applied to every VM"
    parts = [head + (", and from the posture checks" if view["posture"] else "")]
    reasons = [e["reason"] for e in view["entries"] if e["reason"]]
    parts.append(" · ".join(f"« {r} »" for r in reasons) if reasons else "no reason given (written by hand)")
    patterns = [e["pattern"] for e in view["entries"] if e["by_pattern"]]
    if patterns:
        parts.append("by the pattern " + ", ".join(patterns))
    own = view["still_watching"]
    if own:
        parts.append(f"{_rules(len(own))} written for it still watch{'es' if len(own) == 1 else ''} it: "
                     + ", ".join(own))
    elif view["all"] or (total and len(gone) == total):
        parts.append("no rule written for it: no detection watches it")
    if view["unknown"]:
        parts.append("names no rule: " + ", ".join(view["unknown"]))
    return " — ".join(parts)


def exclusions(cfg, rules, assets) -> dict:
    """Each VM of ``assets`` ((name, resource_id) pairs) that `exceptions[]` takes, by name — and the
    counts the Overview shows: ``vms`` (every one), ``all`` (from every rule), ``partial`` (from some),
    and the entries that take no VM known today (a pattern, a VM not discovered yet)."""
    vms: dict[str, dict] = {}
    for name, rid in assets:
        if name and name not in vms:
            view = exclusion_of(cfg, name, rid or "", rules)
            if view is not None:
                vms[name] = view
    names = [n for n, _ in assets if n]
    idle = [e.asset_pattern for e in getattr(cfg, "exceptions", None) or []
            if not any(e.matches(n) for n in names)]
    return {"vms": vms, "count": {"vms": len(vms), "all": sum(1 for v in vms.values() if v["all"]),
                                  "partial": sum(1 for v in vms.values() if not v["all"])},
            "idle_entries": idle}
