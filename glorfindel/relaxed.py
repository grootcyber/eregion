"""CFG3 (#1139): the view « Relaxed » — everything glorfindel-config.yaml relaxes, computed by the watch, read
by the console (docs/design/configuration-console.md, §6).

**What it shows**: each entry of the file that relaxes the defence — an exclusion (`exceptions[]`), a bold
mode (`assets.default_mode`, `assets.list[]` — or, in the former format, `autonomy.default`,
`autonomy.assets[]` —, latent ones included: an exact entry that changes nothing today but screens its VM
from the pattern and the default, §5.3), a priority lowered (PRI2a: an entry `quiet`, or `standard` under an
`essential` pattern — a label today, no effect on the defence), the client's `never_block`, the expected
administrators (`expected_sudo.admins[]`), the investigation access to an isolated VM
(`isolation.forensic_sources`), the exposed zones (`network_zones.exposed`), the expected origins
(`network_zones.expected_origins`, CFG3c: in force or not, by the switch the watch reads) and the named
networks these cite (SEC2), and a backend whose discovery is cut (`monitoring_backends[].discovery.enabled:
false`, CFG3b). Each with its reason (`reason`) when the entry has one, what a pattern or a named network
designates today, whether it is in force (`in_force`), and its author: « unknown » until the history (CFG5)
says who and when.

**Its class is CFG4's** (glorfindel/config_class.py, `classify`, a pure function of two texts): an entry is
in the view when the file without it, then with it, relaxes. An entry that another one already gives (a twin)
changes nothing when it alone is taken out: it is then classed alone in its list, and shown latent — the day
its twin goes, it relaxes. An entry that can't be classed is shown, never hidden. The discovery only says
what a pattern designates; it never decides what is shown (§5.3).

**Its writer: the watch alone** (`publish`, every minute), in `runs/glorfindel/config/relaxed.json` — the
watch's directory (SEC18), which the console mounts read-only. The console reads it (`load`), never computes
it, never writes it. A file the strict reading refuses, a registry of the discovery that can't be read, a view
absent, unreadable or old: each is said, never read as « nothing relaxed ».
"""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from eregion_core import runs_layout

# runs/glorfindel/config/relaxed.json, from the working directory as every reader of runs/ — the watch's
# directory, never ~/.glorfindel, which the console writes.
STORE_PARTS = ("config", "relaxed.json")
_STORE = runs_layout.dir_of(runs_layout.GLORFINDEL).joinpath(*STORE_PARTS)
VERSION = 1
# The watch writes the view every minute: five missed, it is said old (a watch stopped, or behind).
STALE_S = 300.0
# Who made each entry: unknown until the history of CFG5.
AUTHOR_UNKNOWN = "unknown"
_SHOWN_VMS = 10

# The lists whose each entry may relax, in the order the view shows them, and the kind of each line.
_LISTS = ((("assets", "list"), "mode"), (("autonomy", "assets"), "mode"),
          (("exceptions",), "exclusion"), (("never_block",), "never_block"),
          (("expected_sudo", "admins"), "expected_admins"), (("isolation", "forensic_sources"), "forensic_access"),
          (("network_zones", "exposed"), "exposed_zone"), (("network_zones", "expected_origins"), "expected_origin"))


# ── the entry's class: CFG4's, the file without it then with it ──────────────────────────────────

def _dump(raw: dict) -> str:
    import yaml
    return yaml.safe_dump(raw, sort_keys=False, allow_unicode=True) if raw else ""


def _drop(raw: dict, path: tuple) -> dict:
    """``raw`` without the element at ``path``, and without what its removal emptied (`exposed: []` is
    refused by the strict reading, and says nothing)."""
    out = copy.deepcopy(raw)
    *parents, last = path
    chain = [out]
    for k in parents:
        chain.append(chain[-1][k])
    del chain[-1][last]
    for holder, key in reversed(list(zip(chain[:-1], parents))):
        if holder[key] not in ([], {}, None):
            break
        del holder[key]
    return out


def _alone(raw: dict, path: tuple) -> tuple[dict, tuple]:
    """``raw`` with the list that holds ``path`` reduced to that one element, and its path there."""
    out = copy.deepcopy(raw)
    *parents, i = path
    holder = out
    for k in parents[:-1]:
        holder = holder[k]
    holder[parents[-1]] = [holder[parents[-1]][i]]
    return out, (*parents, 0)


def entry_class(raw: dict, path: tuple, full: str | None = None) -> dict:
    """The class of the entry at ``path`` (``classify``: class, latent, loud, reasons). A twin changes
    nothing taken out alone: classed alone in its list, then latent. Never classed: taken as relaxing."""
    from glorfindel.config_class import classify
    try:
        said = classify(_dump(_drop(raw, path)), _dump(raw) if full is None else full)
        if said["class"] == "neutral" and isinstance(path[-1], int):
            alone, at = _alone(raw, path)
            by_itself = classify(_dump(_drop(alone, at)), _dump(alone))
            if by_itself["class"] == "relax":
                said = {**by_itself, "latent": True,
                        "reasons": by_itself["reasons"] + ["another entry holds the same VM today: it relaxes the day that one goes"]}
        return said
    except Exception as exc:
        return {"class": "relax", "latent": False, "loud": False,
                "reasons": [f"not classified ({type(exc).__name__}): taken as relaxing"]}


# PRI2a (#1219): what a priority lowered does today — a label, never the defence (docs/design/classification.md §6).
PRIORITY_SAID = {"quiet": "quiet: shown grey, no effect on the defence today",
                 "standard": "standard: a pattern's level, may lower a VM another entry made essential"}


# CFG3c (#1154): what an expected origin does (glorfindel/lateral.py, `origin_rows`, read by the RulePoller) — only
# while the switch of the lateral movement is on, a variable of the watch alone (`GLORFINDEL_LATERAL`). Off, the
# key is read and checked, and changes nothing: the line says so, never shown in force.
EXPECTED_ON = ("expected origin: a detection of ssh-brute-force from it is set aside before any signal — said in the "
               "watch's log and counted (« N expected »), no card, never blocked")
EXPECTED_OFF = ("expected origin, without effect: GLORFINDEL_LATERAL is off in this watch — the day it is on, a "
                "detection of ssh-brute-force from it is set aside, said and counted, no card")


def lateral_switch() -> dict:
    """The switch of the lateral movement as this process reads it (`lateral.switch`): the watch's, since
    the watch alone computes the view — never the console's. ``said``: an unknown value, read as off."""
    from glorfindel import lateral
    on, said = lateral.switch()
    return {"name": lateral.SWITCH, "on": bool(on), "said": said}


# ── what an entry designates today ───────────────────────────────────────────────────────────────

def discovered() -> tuple[list[str] | None, str]:
    """The VM names of the discovery's registry, or (None, why): never an unreadable registry read as
    « no VM »."""
    from glorfindel import discovery
    path = discovery._CACHE_FILE
    try:
        if not path.exists():
            return None, "the discovery has not run (no registry)"
        items = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(items, list) or not all(isinstance(a, dict) for a in items):
            raise ValueError("not a list of assets")
    except Exception as exc:
        return None, f"registry unreadable ({type(exc).__name__}: {str(exc)[:120]})"
    return sorted({str(a.get("name") or "") for a in items} - {""}), ""


def _vms(pattern: str, names, why: str) -> dict:
    from glorfindel.config import vm_name_matches
    from glorfindel.exclusions import is_pattern
    if names is None:
        return {"vms": None, "said": f"not known: {why}"}
    hit = [n for n in names if vm_name_matches(n, pattern)]
    if not is_pattern(pattern):
        return {"vms": hit, "said": "found by the discovery" if hit else "not found by the discovery today"}
    shown = ", ".join(hit[:_SHOWN_VMS]) + (" …" if len(hit) > _SHOWN_VMS else "")
    return {"vms": hit, "said": f"{len(hit)} VM{'s' if len(hit) != 1 else ''} today" + (f": {shown}" if hit else "")}


def _decides(cfg, pattern: str, mode: str, name: str) -> bool:
    """Whether the mode entry (``pattern``, ``mode``) is the one `AutonomyConfig.resolve` reads for this VM:
    an exact entry wins over any pattern, the longest pattern over the others — and among entries tied,
    the most prudent mode, so the VM is the entry's only when `resolve` gives the entry's mode."""
    assets = [r for r in cfg.autonomy.assets if r.mode is not None]     # PRI2a: the entries that give a mode
    if any(r.match.lower() == name.lower() for r in assets):
        mine = pattern.lower() == name.lower()
    else:
        mine = len(pattern) == max((len(r.match) for r in assets if r.matches(name)), default=-1)
    return mine and cfg.autonomy.resolve(name) == mode


def _network(net, snap) -> dict:
    if not net.is_object:
        return {"ranges": list(net.cidrs), "said": f"named network {net.name}: {', '.join(net.cidrs)}"}
    ranges, why = snap.resolve(net)
    return {"ranges": ranges, "said": f"named network {net.name}, {net.written()}: " + (", ".join(ranges) or why)}


def _range(text: str, cfg, snap, validate) -> dict:
    net = cfg.networks.get(text.strip())
    if net is not None:
        return _network(net, snap)
    ok, bad = validate([text])
    return {"ranges": ok, "said": ", ".join(ok) if ok else f"never applied: {bad[0][1] if bad else 'not a range'}"}


def _canonical(values) -> tuple[list[str], list[tuple[str, str]]]:
    import ipaddress
    try:
        return [str(ipaddress.ip_network(str(values[0]).strip(), strict=False))], []
    except ValueError:
        return [], [(str(values[0]), "not a range")]


# ── the lines ────────────────────────────────────────────────────────────────────────────────────

def _what(kind: str, item, cfg, switch: dict) -> tuple[str, str]:
    """(the object, what is relaxed of it) of an entry as written."""
    if kind in ("mode", "priority"):
        return str(item.get("match")), " · ".join(
            ([f"mode {item.get('mode')}"] if "mode" in item else [])
            + ([PRIORITY_SAID.get(item.get("priority"), f"priority {item.get('priority')}")]
               if "priority" in item else []))
    if kind == "exclusion":
        rules = item.get("exclude_rules") or []
        return str(item.get("asset_pattern")), ("excluded from every rule applied to all VMs" if item.get("exclude_all")
                                                else "excluded from " + ", ".join(map(str, rules)))
    if kind == "expected_admins":
        origins = item.get("origins") or []
        return str(item.get("match")), ("sudo to root expected of " + ", ".join(map(str, item.get("accounts") or []))
                                        + (f", from {', '.join(map(str, origins))}" if origins else ""))
    if kind == "forensic_access":
        return str(item), "reaches an isolated VM on ports " + ", ".join(map(str, cfg.isolation.forensic_ports))
    if kind == "exposed_zone":
        return str(item), "exposed zone: a block of one host runs there again"
    if kind == "expected_origin":
        return str(item), EXPECTED_ON if switch["on"] else EXPECTED_OFF
    return str(item), "never blocked"


def _designates(kind: str, item, obj: str, cfg, names, why: str, snap) -> dict:
    from glorfindel.config import validate_forensic_sources, validate_never_block
    if kind == "mode" and names is not None and "mode" in item:   # the VMs whose mode it is, never another's
        return _vms(obj, [n for n in names if _decides(cfg, obj, str(item.get("mode")), n)], why)
    if kind in ("mode", "priority", "exclusion", "expected_admins"):
        return _vms(obj, names, why)
    validate = {"never_block": validate_never_block, "forensic_access": validate_forensic_sources}.get(kind, _canonical)
    return _range(obj, cfg, snap, validate)


def _line(kind: str, where: str, obj: str, what: str, said: dict, reason: str, designates: dict,
          cites: list | None = None, in_force: bool = True) -> dict:
    return {"kind": kind, "where": where, "object": obj, "what": what, "reason": reason,
            "latent": bool(said.get("latent")), "why": list(said.get("reasons") or []),
            "designates": designates, "by": AUTHOR_UNKNOWN, "since": "", "cites": cites or [],
            "in_force": in_force}


def _default_line(raw: dict, cfg, names, why: str) -> list[dict]:
    if cfg.autonomy.default == "human_only":
        return []
    where = ("assets", "default_mode") if cfg.autonomy.form == "assets" else ("autonomy", "default")
    said = entry_class(raw, where)
    if said["class"] != "relax":
        return []
    if names is None:
        gov = {"vms": None, "said": f"not known: {why}"}
    else:
        hit = [n for n in names if not any(r.matches(n) for r in cfg.autonomy.assets if r.mode is not None)]
        gov = {"vms": hit, "said": f"governs {len(hit)} VM{'s' if len(hit) != 1 else ''} today"}
    return [_line("default_mode", ".".join(where), "default", f"mode {cfg.autonomy.default}", said, "", gov)]


# CFG3b (#1148): what a backend's discovery cut does (glorfindel/discovery.py, `_discover_all` skips it): its
# registry is never refreshed for it — a VM new to it is never seen, so no rule applied to all VMs watches it
# (`RulePoller._targets` reads the registry) and the posture never checks it; the VMs it knew stay as they were
# last seen, never evicted. A rule written for one VM is not bound to the discovery.
DISCOVERY_OFF = ("a VM new to this backend is never seen — no rule applied to all VMs watches it, no posture "
                 "check; the VMs it already knows stay as last seen, never evicted")


def _backend_vms(backend: str, names, why: str) -> dict:
    """What a backend whose discovery is cut holds today: the VMs the registry keeps for it, as last seen."""
    from glorfindel import discovery
    if names is None:
        return {"vms": None, "said": f"not known: {why}"}
    try:
        items = json.loads(discovery._CACHE_FILE.read_text(encoding="utf-8"))
        hit = sorted({str(a.get("name") or "") for a in items if a.get("monitoring_backend") == backend} - {""})
    except Exception as exc:
        return {"vms": None, "said": f"not known: registry unreadable ({type(exc).__name__})"}
    return {"vms": hit, "said": f"{len(hit)} VM{'s' if len(hit) != 1 else ''} known to it, as last seen"}


def _discovery_lines(raw: dict, cfg, names, why: str, full: str) -> list[dict]:
    """A backend whose discovery the file cuts (`discovery.enabled: false`, by the strict reading): a line when
    CFG4's class of the key says it relaxes. `enabled: true` written, or left to its default, is no line."""
    out = []
    for i, backend in enumerate(cfg.monitoring_backends):
        if backend.discovery.enabled:
            continue
        said = entry_class(raw, ("monitoring_backends", i, "discovery", "enabled"), full)
        if said["class"] != "relax":
            continue
        # No reason: a backend carries none (the strict reading refuses the key, `_MONITORING_KEYS`).
        out.append(_line("discovery_off", f"monitoring_backends[{i}].discovery.enabled", backend.name,
                         DISCOVERY_OFF, said, "", _backend_vms(backend.name, names, why)))
    return out


def _named_networks(lines: list[dict], cfg, snap) -> list[dict]:
    """A named network takes the class of its most relaxing use (§5.3): listed when a line of the view
    cites it."""
    out = []
    for name, net in sorted(cfg.networks.items()):
        citing = [ln for ln in lines if name in ln["cites"]]
        if citing:
            said = {"latent": all(ln["latent"] for ln in citing),
                    "reasons": [f"cited by {ln['where']}" for ln in citing]}
            out.append(_line("named_network", f"networks.{name}", name, f"named network: {net.written()}", said, "",
                             _network(net, snap), in_force=any(ln["in_force"] for ln in citing)))
    return out


def entries(raw: dict, cfg, names, why: str, snap, switch: dict | None = None) -> list[dict]:
    """Every line of the view, from the file read (``raw`` and its strict reading ``cfg``) — and, for an
    expected origin, the switch of the lateral movement (``switch``, `lateral_switch`: the watch's)."""
    switch = switch or lateral_switch()
    lines = _default_line(raw, cfg, names, why)
    full = _dump(raw)
    for path, listed in _LISTS:
        holder = raw
        for k in path:
            holder = holder.get(k) if isinstance(holder, dict) else None
        for i, item in enumerate(holder if isinstance(holder, list) else []):
            said = entry_class(raw, (*path, i), full)
            if said["class"] != "relax":
                continue
            # PRI2a: an entry of assets.list that gives a priority only is a line of its own kind.
            kind = "priority" if listed == "mode" and isinstance(item, dict) and "mode" not in item else listed
            obj, what = _what(kind, item, cfg, switch)
            reason = str(item.get("reason") or "") if isinstance(item, dict) else ""
            named = (item.get("origins") or []) if kind == "expected_admins" else [obj.strip()]
            lines.append(_line(kind, f"{'.'.join(path)}[{i}]", obj, what, said, reason,
                               _designates(kind, item, obj, cfg, names, why, snap),
                               [str(n).strip() for n in named if str(n).strip() in cfg.networks],
                               in_force=switch["on"] if kind == "expected_origin" else True))
    lines += _discovery_lines(raw, cfg, names, why, full)
    return lines + _named_networks(lines, cfg, snap)


# ── the watch computes and writes; the console reads ─────────────────────────────────────────────

def _config_path() -> Path | None:
    from glorfindel import config
    return next((p for p in config._DEFAULT_PATHS if p.exists()), None)


def _read_bytes(path: Path) -> bytes:
    """The file's bytes under the shared lock (never half of an in-place write): its digest is that of
    the bytes, as CFG4's `base` is."""
    from glorfindel.config import _flock
    with open(path, "rb") as f:
        _flock(f, exclusive=False)
        return f.read()


def _override(mode_override: str | None) -> dict | None:
    """`glorfindel watch --mode`: the default mode of this session, whatever the file says — said in the view."""
    if not mode_override:
        return None
    return {"mode": mode_override, "said": f"the watch runs with --mode {mode_override}: every VM the default "
                                          f"governs is in {mode_override} for this session, whatever the file says"}


def compute(now: datetime | None = None, cfg_path: Path | None = None, mode_override: str | None = None,
            switch: dict | None = None) -> dict:
    """The view, from the file and the discovery (module docstring), and the switch of the lateral movement
    as the watch reads it (``lateral``). ``entries`` None: not computed — the file refused or unreadable,
    said in ``config``."""
    from glorfindel import client_network
    from glorfindel.config_class import _read
    from glorfindel.config_edit import digest
    now = now or datetime.now(timezone.utc)
    switch = switch or lateral_switch()
    view: dict = {"v": VERSION, "at": now.isoformat(), "computed_at": now.isoformat(), "entries": None,
                  "count": None, "override": _override(mode_override), "lateral": switch}
    path = cfg_path or _config_path()
    names, why = discovered()
    view["discovery"] = {"state": "read" if names is not None else "not_read", "error": why,
                         "vms": None if names is None else len(names)}
    if path is None:
        view["config"] = {"path": "", "state": "absent", "digest": "", "error": ""}
        raw, cfg = _read("")
    else:
        try:
            data = _read_bytes(path)
            view["config"] = {"path": str(path), "state": "read", "digest": digest(data), "error": ""}
            raw, cfg = _read(data.decode("utf-8"))
        except Exception as exc:
            view["config"] = {"path": str(path), "state": "refused", "digest": view.get("config", {}).get("digest", ""),
                              "error": f"{type(exc).__name__}: {str(exc)[:400]}"}
            return view
    snap = client_network.load(now) if any(n.is_object for n in cfg.networks.values()) else None
    view["entries"] = entries(raw if isinstance(raw, dict) else {}, cfg, names, why, snap, switch)
    view["count"] = len(view["entries"])
    return view


# The cost (the review of CFG3): each entry is classed on the whole file, twice parsed — quadratic, 6.6 s for
# 204 entries. The view is computed again only when what it reads changed (`inputs`), or once every
# RECOMPUTE_S; between, the last view is written again with its `at`, so that it reads fresh.
RECOMPUTE_S = 600.0
_LAST: dict = {}


def _stat(path: Path) -> tuple:
    try:
        st = path.stat()
        return (str(path), st.st_mtime_ns, st.st_size)
    except OSError as exc:
        return (str(path), type(exc).__name__)


def inputs(cfg_path: Path | None = None, mode_override: str | None = None, switch: dict | None = None) -> tuple:
    """What the view is computed from: the file's digest, the discovery's registry and the client's
    network (their stat), the session's --mode, and the switch of the lateral movement (CFG3c: read by the
    watch at each pass — a switch changed, at the watch's restart, computes the view again)."""
    from glorfindel import client_network, discovery
    from glorfindel.config_edit import digest
    path = cfg_path or _config_path()
    try:
        seen = digest(_read_bytes(path)) if path is not None else ""
    except OSError as exc:
        seen = type(exc).__name__
    switch = switch or lateral_switch()
    return (str(path or ""), seen, _stat(discovery._CACHE_FILE), _stat(client_network._STORE), mode_override or "",
            switch["on"], switch["said"])


def publish(now: datetime | None = None, path: Path | None = None, cfg_path: Path | None = None,
            mode_override: str | None = None) -> dict:
    """The watch's pass (every minute, in a thread of its own): the view computed again when what it reads
    changed (``inputs``) or RECOMPUTE_S passed, else the last one with its ``at`` — then written whole (a
    temporary file renamed: the console never reads half of it). Raises when it can't be written."""
    now = now or datetime.now(timezone.utc)
    switch = lateral_switch()              # read once: the key and the view say the same switch
    key = inputs(cfg_path, mode_override, switch)
    last = _LAST.get("view")
    if (last is not None and _LAST.get("inputs") == key
            and (now - datetime.fromisoformat(last["computed_at"])).total_seconds() < RECOMPUTE_S):
        view = {**last, "at": now.isoformat()}
    else:
        view = compute(now, cfg_path, mode_override, switch)
    _LAST.update(inputs=key, view=view)
    path = path or _STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}")
    tmp.write_text(json.dumps(view, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    return view


def start_lines(view: dict, most: int = 20) -> list[tuple[str, str]]:
    """What the watch says of the view at its start (§6): (level, text) — its count, each line (at most
    ``most``), the --mode of the session; the file refused. Raw text: the watch escapes it."""
    out: list[tuple[str, str]] = []
    if (view.get("override") or {}).get("said"):
        out.append(("warn", view["override"]["said"]))
    if (view.get("lateral") or {}).get("said"):
        out.append(("warn", view["lateral"]["said"]))
    if view.get("entries") is None:
        return out + [("warn", f"Relaxed non calculée : {view['config'].get('error')}")]
    out.append(("info", f"Relaxed : {len(view['entries'])} entrée(s) relâchée(s) — ⚙ Config ▸ Relaxed"))
    for e in view["entries"][:most]:
        out.append(("line", f"{e['object']} — {e['kind']} : {e['what']}" + (" (latent)" if e["latent"] else "")
                    + ("" if e.get("in_force", True) else " (sans effet)")
                    + (f" · « {e['reason']} »" if e["reason"] else " · sans raison")
                    + f" · {(e.get('designates') or {}).get('said', '')}"))
    if len(view["entries"]) > most:
        out.append(("line", f"… et {len(view['entries']) - most} de plus, sur ⚙ Config ▸ Relaxed"))
    return out


def _said(view: dict | None, state: str, age_s, error: str) -> str:
    if state == "absent":
        return ("the watch has not written the view (runs/glorfindel/config/relaxed.json): a watch older "
                "than CFG3, or not started — what is relaxed is not known")
    if state == "unreadable":
        return f"the view can't be read ({error}) — what is relaxed is not known"
    cfg = view["config"]
    if cfg.get("state") == "refused":
        return f"glorfindel-config.yaml refused by the strict reading ({cfg.get('error')}) — what is relaxed is not known"
    if state == "stale":
        return f"computed {int(age_s // 60)} min ago: the watch has not refreshed it since (stopped, or behind)"
    return ""


def load(now: datetime | None = None, path: Path | None = None, cfg_path: Path | None = None) -> dict:
    """The view as the watch wrote it, judged — read only, never computed here. ``state``: fresh, stale,
    absent, unreadable, refused; ``said``: what is wrong, "" when nothing is; ``file_changed``: the file
    read here is not the one the view was computed from (the watch recomputes it within a minute)."""
    now = now or datetime.now(timezone.utc)
    path = path or _STORE
    out: dict = {"state": "absent", "said": "", "view": None, "age_s": None, "file_changed": None}
    if not path.exists():
        out["said"] = _said(None, "absent", None, "")
        return out
    try:
        view = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(view, dict) or view.get("v") != VERSION or not isinstance(view.get("config"), dict):
            raise ValueError("not a view of this version")
        if view["config"].get("state") != "refused" and not (
                isinstance(view.get("entries"), list) and all(isinstance(e, dict) for e in view["entries"])):
            raise ValueError("its entries are not a list")
        at = datetime.fromisoformat(str(view.get("at")))
        at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    except Exception as exc:
        out.update(state="unreadable", said=_said(None, "unreadable", None, f"{type(exc).__name__}: {str(exc)[:200]}"))
        return out
    age = (now - at).total_seconds()
    state = "refused" if view["config"].get("state") == "refused" else "stale" if age > STALE_S else "fresh"
    out.update(state=state, view=view, age_s=int(age), said=_said(view, state, age, ""))
    seen = cfg_path or _config_path()
    if seen is not None and view["config"].get("digest"):
        from glorfindel.config_edit import digest
        try:
            out["file_changed"] = digest(_read_bytes(seen)) != view["config"]["digest"]
        except OSError:
            out["file_changed"] = None
    return out
