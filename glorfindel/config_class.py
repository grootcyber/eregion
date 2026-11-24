"""CFG4 (#1129): the class of a change to glorfindel-config.yaml — relax, tighten, or neutral — from the two
texts alone (docs/design/configuration-console.md, §5).

A pure function of the file before and after, read by the strict reading (A3): never the discovery (the
registry is within a compromised console's reach, and a VM it does not list that day would make its
exclusion « neutral », §5.3), never the name of the operation that made the change (a revert, an edit by
hand, the push: the same change has the same class). CFG3 takes it up for the view « Relaxed », CFG5 and
CFG6 for the queue.

- **Relax**: Glorfindel acts more alone, or sees less, or says less. Tighten: the reverse. Neutral: no
  effect on the defence (a reason reworded).
- **An exclusion added relaxes**, whatever the name, discovered or not; one removed tightens.
- **The mode**: a VM whose mode turns bolder relaxes, more prudent tightens. **An exact entry bolder than
  human_only relaxes even when it changes nothing today** (`latent`): under a pattern, or a default, that
  already gives that mode, it screens the VM — the day the pattern or the default goes back to human_only,
  the VM stays autonomous (§5.3).
- **`never_block`** (Q10): an address added that is one private host (/32, /128) tightens; a wider prefix
  or a public address relaxes; one removed relaxes (it becomes blockable again, and was protected).
- **To human_only en masse** (Q11): the default, or many VMs at once — it tightens and applies at once, but
  `loud`: said like a relaxation (« response disarmed on N VMs »). The class counts entries; **the loud
  announcement counts the VMs really touched** (CFG4b, #1136): `loud(before, after, vms)`, apart from the
  class, is the one reading that takes the discovery — the names the caller lists (edit_config reads the
  registry) —, so a pattern counts the VMs it designates, and a VM no discovery knows counts for nothing.
  The default to human_only is loud whatever the count. The class stays a function of the two texts.
- **Any other section changed** (backends, isolation, expected_sudo, networks, zones, memory,
  allow_destructive) is not classified here: it counts as relaxing, never as tightening.
- **A mixed change relaxes.**
"""
from __future__ import annotations

import ipaddress

import yaml

_PRUDENCE = {"human_only": 0, "non_disruptive": 1, "full_auto": 2}
# Q11: this many VMs turned more prudent in one change is « en masse ».
MASS_VMS = 5
# Q10: « un hôte privé » — the client's private ranges (RFC 1918, RFC 4193); any other address, a
# documentation range or the loopback too, counts as public: its addition relaxes.
_PRIVATE = tuple(ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))
_UNCLASSIFIED = ("monitoring_backends", "action_backends", "isolation", "expected_sudo", "networks",
                 "network_zones", "memory")


def _read(text: str):
    from glorfindel.config import _parse_config
    raw = (yaml.safe_load(text) if text.strip() else {}) or {}
    return raw, _parse_config(raw)


def _cover(cfg) -> dict:
    """Per pattern (case ignored): (every rule, the rules named) — what exceptions[] takes."""
    out: dict = {}
    for e in cfg.exceptions:
        every, named = out.get(e.asset_pattern.lower(), (False, frozenset()))
        out[e.asset_pattern.lower()] = (every or e.exclude_all, named | frozenset(e.exclude_rules))
    return out


def _exceptions(b, a, said) -> None:
    cb, ca = _cover(b), _cover(a)
    for pattern in sorted(set(cb) | set(ca)):
        (eb, nb), (ea, na) = cb.get(pattern, (False, frozenset())), ca.get(pattern, (False, frozenset()))
        added = (ea and not eb) or (not eb and bool(na - nb))
        removed = (eb and not ea) or (not ea and bool(nb - na))
        if added:
            said.append(("relax", f"exclusion added: {pattern}", False))
        if removed:
            said.append(("tighten", f"exclusion removed: {pattern}", False))


def _exact_mode(cfg, key: str):
    modes = [r.mode for r in cfg.autonomy.assets if r.match.lower() == key]
    return min(modes, key=lambda m: _PRUDENCE.get(m, 0)) if modes else None


def _autonomy(b, a, said) -> None:
    pb, pa = _PRUDENCE.get(b.autonomy.default, 0), _PRUDENCE.get(a.autonomy.default, 0)
    if pa > pb:
        said.append(("relax", f"default mode to {a.autonomy.default}", False))
    elif pa < pb:
        said.append(("tighten", f"default mode to {a.autonomy.default}: every VM it governs", False))
        said.append(("loud", "response disarmed on the VMs the default governs", False))
    turned = 0
    for key in sorted({r.match.lower() for r in (*b.autonomy.assets, *a.autonomy.assets)}):
        eb, ea = _PRUDENCE.get(b.autonomy.resolve(key), 0), _PRUDENCE.get(a.autonomy.resolve(key), 0)
        mb, ma = _exact_mode(b, key), _exact_mode(a, key)
        if ea > eb:
            said.append(("relax", f"{key}: mode to {a.autonomy.resolve(key)}", False))
        elif ea < eb:
            turned += 1
            said.append(("tighten", f"{key}: mode to {a.autonomy.resolve(key)}", False))
        elif ma != mb:
            if ma is not None and _PRUDENCE.get(ma, 0) > 0:
                said.append(("relax", f"{key}: an exact entry {ma} screens it from the pattern and the default", True))
            elif mb is not None and _PRUDENCE.get(mb, 0) > 0:
                said.append(("tighten", f"{key}: its exact entry {mb} no longer screens it", True))
            elif ma is not None:
                said.append(("tighten", f"{key}: an exact entry human_only holds it", True))
            else:
                # A pattern's entry gone: the VMs it held change today, never a latent relaxation.
                said.append(("relax", f"{key}: its entry human_only no longer holds it", not _is_pattern(key)))
    if turned >= MASS_VMS:
        said.append(("loud", f"response disarmed on {turned} VMs", False))


def _is_pattern(key: str) -> bool:
    return any(c in key for c in "*?[")


def _addresses(raw) -> set:
    out = set()
    for item in raw.get("never_block") or []:
        try:
            out.add(ipaddress.ip_network(str(item).strip(), strict=False))
        except ValueError:
            out.add(str(item))
    return out


def _never_block(rb, ra, said) -> None:
    nb, na = _addresses(rb), _addresses(ra)
    for item in sorted(na - nb, key=str):
        one_private_host = (isinstance(item, (ipaddress.IPv4Network, ipaddress.IPv6Network))
                            and item.prefixlen == item.max_prefixlen
                            and any(item.version == n.version and item.subnet_of(n) for n in _PRIVATE))
        said.append(("tighten" if one_private_host else "relax", f"never_block: {item} added", False))
    for item in sorted(nb - na, key=str):
        said.append(("relax", f"never_block: {item} removed, blockable again", False))


def _others(rb, ra, said) -> None:
    for section in _UNCLASSIFIED:
        if rb.get(section) != ra.get(section):
            said.append(("relax", f"{section} changed: not classified, taken as relaxing", False))
    if (rb.get("autonomy") or {}).get("allow_destructive") != (ra.get("autonomy") or {}).get("allow_destructive"):
        said.append(("relax", "autonomy.allow_destructive changed: not classified, taken as relaxing", False))


def classify(before: str, after: str) -> dict:
    """The class of the change from `before` to `after` (module docstring): ``class`` (relax, tighten,
    neutral), ``latent`` (it relaxes only by an entry that changes nothing today), ``loud`` (to human_only
    en masse, Q11), and ``reasons``. A text the strict reading refuses raises ConfigError.

    ``loud``: counted in entries (CFG4), it is not the announcement; the announcement is `loud()`, and it is
    the one edit_config returns."""
    rb, b = _read(before)
    ra, a = _read(after)
    said: list[tuple[str, str, bool]] = []
    _exceptions(b, a, said)
    _autonomy(b, a, said)
    _never_block(rb, ra, said)
    _others(rb, ra, said)
    relax = [s for s in said if s[0] == "relax"]
    tighten = [s for s in said if s[0] == "tighten"]
    kind = "relax" if relax else "tighten" if tighten else "neutral"
    return {"class": kind, "latent": bool(relax) and all(s[2] for s in relax),
            "loud": any(s[0] == "loud" for s in said),
            "reasons": [s[1] for s in said if s[0] != "loud"]}


def loud(before: str, after: str, vms) -> str | None:
    """CFG4b (#1136), Q11: the loud announcement of a change to human_only, or None. Loud when the default
    turns to human_only, or when MASS_VMS or more of the VMs known today (``vms``, the names the caller
    lists) are really touched: their mode was bolder before, human_only after. A pattern counts each VM it
    designates; a name in the file the caller does not list counts for nothing; a VM already human_only is
    not touched. Apart from classify: the class never reads the list. ``vms`` None (the caller could not
    read its list, or it is empty: Jonathan, 24/11): the entries of the file are counted instead, as CFG4
    — the announcement is never lost; its sentence then counts « entries »."""
    _, b = _read(before)
    _, a = _read(after)
    unit = "VMs"
    if vms is None:
        vms, unit = [r.match for r in (*b.autonomy.assets, *a.autonomy.assets)], "entries"
    names = sorted({str(v).strip().lower() for v in vms} - {""})
    touched = [n for n in names
               if _PRUDENCE.get(b.autonomy.resolve(n), 0) > 0 and _PRUDENCE.get(a.autonomy.resolve(n), 0) == 0]
    default = _PRUDENCE.get(b.autonomy.default, 0) > 0 and _PRUDENCE.get(a.autonomy.default, 0) == 0
    if default:
        return f"response disarmed on {len(touched)} {unit}, and on every VM the default governs"
    if len(touched) >= MASS_VMS:
        return f"response disarmed on {len(touched)} {unit}"
    return None
