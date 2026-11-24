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
        rules = load_config(rules_path, glorfindel_cfg=cfg).rules if rules_path else []
        ids = _ids_by_name(discovered, resources)
        assets = [(n, sorted(ids.get(n, {""}))[0]) for n in sorted(vm_names(discovered, resources, escalations))]
        return {**of(cfg, rules, assets), "error": ""}
    except Exception as exc:
        return {"vms": {}, "count": None, "idle_entries": [], "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
