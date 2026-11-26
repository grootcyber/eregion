"""What `/api/state` says of the configuration for each VM the page can draw: its autonomy mode, and
since CFG2 (#1128) what `exceptions[]` takes from it. Read from glorfindel-config.yaml and the
detection rules, nothing written.

Taken out of `eregion_console/api.py` (CFG2): the file holds its ceiling (WCH1,
tests/unit/test_file_sizes.py), and a part a test reaches alone stays one it can read whole.
"""
from __future__ import annotations


def vm_names(discovered: list[dict], resources: list[dict], escalations: list[dict]) -> set[str]:
    """Every VM the page can render: discovered, isolated or blocked, or the target of a card."""
    names: set[str] = set()
    for a in discovered:
        n = a.get("name") or a.get("resource_id", "").split("/")[-1]
        if n:
            names.add(n)
    for r in resources:
        if r.get("vm_name"):
            names.add(r["vm_name"])
    for e in escalations:
        rid = e.get("resource_id", "")
        if rid:
            names.add(rid.split("/")[-1])
    return names


def _ids_by_name(discovered: list[dict], resources: list[dict]) -> dict[str, set]:
    ids: dict[str, set] = {}
    for a in discovered:
        if a.get("resource_id"):
            ids.setdefault(a.get("name") or a["resource_id"].split("/")[-1], set()).add(a["resource_id"])
    for r in resources:
        if r.get("vm_name") and r.get("resource_id"):
            ids.setdefault(r["vm_name"], set()).add(r["resource_id"])
    return ids


def autonomy(discovered: list[dict], resources: list[dict], escalations: list[dict]):
    """(modes, holds, default, config) — the mode resolved for EVERY VM the UI can render
    (discovered assets, isolated/blocked resources, and escalation targets). Resolving only
    discovered assets left escalation-only cards (e.g. a mode_hold target) falling back to the
    global default, so a per-asset override never showed in the card. A config that can't be
    read: what was resolved so far, the default human_only, and no config."""
    modes: dict[str, str] = {}
    holds: dict[str, dict] = {}   # configured autonomous, held by readiness (L6)
    default, acfg = "human_only", None
    try:
        from glorfindel.config import load_glorfindel_config
        acfg = load_glorfindel_config()
        default = acfg.autonomy.default
        from glorfindel.readiness import effective_mode
        # The gate reads readiness by resource id: so must the display (fifth review,
        # C4 — by name, homonyms showed "human_only" while one acted alone).
        rids = _ids_by_name(discovered, resources)
        for n in vm_names(discovered, resources, escalations):
            conf = acfg.autonomy.resolve(n)
            ids = sorted(rids.get(n, set()), key=str.lower)
            ids = list({i.lower(): i for i in ids}.values())
            if len(ids) > 1:
                # Homonyms: show the MOST permissive effective mode, and say it is ambiguous.
                found = [effective_mode(i, conf)[0] for i in ids]
                modes[n] = "non_disruptive" if "non_disruptive" in found else "human_only"
                holds[n] = {"reason": "ambiguous", "codes": [], "configured": conf,
                            "message": f"{len(ids)} VMs portent ce nom — modes : " + ", ".join(found)}
                continue
            modes[n], hold = effective_mode(ids[0] if ids else n, conf)
            if hold:
                holds[n] = hold
    except Exception:
        pass
    return modes, holds, default, acfg


def exclusions(cfg, discovered: list[dict] | None, resources: list[dict], escalations: list[dict],
               rules_path) -> dict:
    """CFG2 (#1128): each VM `exceptions[]` takes, and the Overview's counts
    (glorfindel/exclusions.py); ``discovered`` None: read from the discovery's registry. A config,
    rules or registry that can't be read: said, never an empty view that would read as « nothing
    excluded »."""
    try:
        if discovered is None:
            from glorfindel.discovery import AssetRegistry
            discovered = AssetRegistry().to_dicts()
        from glorfindel.config import load_glorfindel_config
        from glorfindel.detection_rules import load_config
        from glorfindel.exclusions import exclusions as of
        cfg = cfg if cfg is not None else load_glorfindel_config()
        if not rules_path:
            # No rules read: never a band saying « no detection watches it » on what is not known.
            return {"vms": {}, "count": None, "idle_entries": [], "error": "rules file not found"}
        rules = load_config(rules_path, glorfindel_cfg=cfg).rules
        ids = _ids_by_name(discovered, resources)
        backends = {a.get("name"): a.get("monitoring_backend") or "" for a in discovered if a.get("name")}
        assets = [(n, sorted(ids.get(n, {""}))[0], backends.get(n, ""))
                  for n in sorted(vm_names(discovered, resources, escalations))]
        return {**of(cfg, rules, assets), "error": ""}
    except Exception as exc:
        return {"vms": {}, "count": None, "idle_entries": [], "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


# ── CRT1 (#1215): the priority shown, read as the watch reads it ─────────────────────────────────────────────
# docs/design/classification.md §7: a VM's priority (`level_of`) sets what Glorfindel spends on it and its rank in
# the queues of the calls to the model, never what it detects nor what it does alone. Shown, never written here
# (the file by hand, then the signed queue: CFG5); the reserve from the budget's one reckoning, never copied.

SHOWN_VMS = 10      # the VMs a pattern designates, named on its line (the form of the view « Relaxed »)


def levels(acfg, discovered: list[dict], resources: list[dict], escalations: list[dict]) -> dict[str, str]:
    """Each VM the page can render whose priority is not the default — its level by `level_of`, the watch's own
    reading. A config that cannot be read: none (every VM standard, as the budget then counts it)."""
    if acfg is None:
        return {}
    try:
        from glorfindel.config import STANDARD
        return {n: lvl for n in sorted(vm_names(discovered, resources, escalations))
                if (lvl := acfg.autonomy.level_of(n)) != STANDARD}
    except Exception:
        return {}


def _discovered() -> tuple[list[str] | None, str]:
    """(the names the discovery knows, why not) — None and why when its registry cannot be read."""
    try:
        from glorfindel.discovery import AssetRegistry
        return sorted({n for a in AssetRegistry().to_dicts()
                       if (n := a.get("name") or str(a.get("resource_id") or "").split("/")[-1])}), ""
    except Exception as exc:
        return None, f"discovery not read ({type(exc).__name__})"


def _designates(autonomy, rule, names: list[str] | None, why: str) -> dict:
    """What an entry designates today, by the discovery: the VMs it covers whose level is the entry's (an exact
    entry of another level takes its VM out of a pattern) — what it designates, never what decides the level."""
    from glorfindel.exclusions import is_pattern
    if names is None:
        return {"vms": None, "said": f"not known: {why}"}
    hit = [n for n in names if rule.matches(n) and autonomy.level_of(n) == rule.priority]
    if not is_pattern(rule.match):
        return {"vms": hit, "said": "found by the discovery" if hit else "not found by the discovery today"}
    shown = ", ".join(hit[:SHOWN_VMS]) + (" …" if len(hit) > SHOWN_VMS else "")
    return {"vms": hit, "said": f"{len(hit)} VM{'s' if len(hit) != 1 else ''} today" + (f": {shown}" if hit else "")}


def isolable(autonomy, names: list[str] | None) -> list[dict]:
    """Q4: each essential VM whose mode (`resolve`: its entry, the patterns, the default) lets Glorfindel isolate
    it on its own — the combination said, never corrected: the mode stays the one decision. The discovered VMs,
    and the names an entry writes exactly (a VM the discovery does not know yet)."""
    from glorfindel.config import ESSENTIAL
    from glorfindel.exclusions import is_pattern
    named = [*(names or []), *(r.match for r in autonomy.assets if not is_pattern(r.match))]
    out = []
    for n in sorted({n.lower(): n for n in named}.values(), key=str.lower):
        if autonomy.level_of(n) == ESSENTIAL and (mode := autonomy.resolve(n)) != "human_only":
            out.append({"vm": n, "mode": mode,
                        "said": f"{n} may be isolated on its own ({mode}): its service stops while it is isolated"})
    return out


def priorities(autonomy, names: list[str] | None = None, why: str = "", *, discover: bool = True) -> dict:
    """The section « Priorities » of the page Config (§7.2): the entries that carry a priority, by level, and what
    each designates today; the graves' reserve the essential entries keep (`model_budget.reserve_of`, the
    ledger's own reckoning); the essential VMs that may be isolated on their own. ``names`` None and
    ``discover``: read from the discovery's registry. Read only: nothing written."""
    try:
        from glorfindel.config import ESSENTIAL, QUIET, STANDARD
        from glorfindel.model_budget import reserve_of
        if names is None and discover:
            names, why = _discovered()
        by_level = {lvl: [{"match": r.match, "reason": r.reason, "designates": _designates(autonomy, r, names, why)}
                          for r in autonomy.assets if r.priority == lvl]
                    for lvl in (ESSENTIAL, QUIET, STANDARD)}
        count = autonomy.critical_count()
        reserve, floor, part = reserve_of(count)
        return {"levels": by_level, "essential_count": count,
                "reserve": {"usd": reserve, "floor_usd": floor, "essential_usd": part},
                "isolable": isolable(autonomy, names), "discovery": why if names is None else "", "error": ""}
    except Exception as exc:
        return {"levels": {}, "essential_count": None, "reserve": None, "isolable": [], "discovery": "",
                "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
