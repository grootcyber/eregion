"""The Glorfindel config pushed to the hosted VM (Imladris): the local one, the default forced to
human_only, each VM's mode kept as it is on Imladris (BL1c, Jonathan's decision of 02/11), each level
kept or raised, never lowered (PRI2b, docs/design/classification.md §5.5, §5.6).

    python infra/glorfindel-host/host_config.py glorfindel-config.yaml OUT.yaml [--h0 Imladris.yaml]
        [--release RELEASE] [--human-only] [--to autonomy]

``make imladris-push`` reads Imladris's config and the release its containers run through the ssh
connection it already opens (``--h0``, ``--release``), and says, name by name, the mode and the level
sent and where they come from — read on the config written, never on what was meant.

- **Two readers held equal** (PR5): Glorfindel's strict reading (glorfindel/config.py, config_assets.py)
  and this one read the same sections, ``assets:`` and the former ``autonomy:``, with the same keys, the
  same modes, the same priorities and the same refusals: both formats in one file, a ``match`` twice
  (case ignored), an entry that says nothing, a key more, a value unknown. A config the watch would refuse
  is refused whole here too (``refusal``) — tests/unit/test_glorfindel_host.py holds the two equal.
- **The format Imladris's release reads** (the version guard): the version label of each container that
  mounts the config (``org.opencontainers.image.version``, the label the CD reads, ``deployed()``), read
  through ssh. Every one at ``ASSETS_SINCE`` or after: ``assets:`` is written, and an Imladris still in
  ``autonomy:`` is migrated by the push, at equal values, said. A release before, or one that does not
  read (no watch, a commit deployed by hand, no label): the former format, converted as
  ``glorfindel config migrate --to autonomy`` converts (``to_autonomy``), never a bolder mode; ``quiet``,
  ``standard`` and ``reason`` dropped, said. ``--to autonomy`` writes the former format whatever runs:
  the way back to a release that does not read ``assets:`` (docs/operations.md). An Imladris in
  ``assets:`` its watch would read, on a release before or unread: its levels kept (``critical: true``),
  never its modes (``human_only``: a release before refused the file already).
- **The modes (A0)**: the default always ``human_only``, ``allow_destructive`` always empty; the mode of
  each exact name kept from Imladris, the most prudent of its entries, as Imladris resolves it; a
  pattern's mode never carried, a VM Imladris does not know ``human_only``: never a mode bolder than in
  place. The local config's modes never reach Imladris.
- **The levels, never lowered (PR4)**: every level of Imladris kept, its patterns and its ``quiet``
  included (``quiet`` comes from Imladris only: posed by hand on the host); a level of the workstation
  pushed only when it lowers no name nor pattern cited in either config, compared by ``level_of`` as the
  watch resolves it; never a ``quiet``, never a pattern of the workstation that says ``standard`` (it
  could lower a VM no name shows). Imladris's config unread or refused: only the workstation's
  ``essential``, each essential of Imladris said lost or kept. An entry that carries only a level is
  pushed without a mode.
- **A config of the workstation the watch would refuse** (both formats, a key more…): nothing is sent,
  and said; absent, empty, not UTF-8 or not a YAML table: nothing sent, HUMAN_ONLY=1 included (an empty
  config pushed would take Imladris's backends away). **HUMAN_ONLY=1** (``--human-only``; only « 1 »):
  every VM back to ``human_only`` in one gesture, the levels as without it; never blocked by the release
  read nor by a local section the watch would refuse (none of its entries is then carried, said).
- What Imladris says reaches the operator's terminal printable only (``printable``).

Backends and exceptions stay as they are. No Glorfindel import: this runs on the operator's machine,
beside the Makefile.
"""
from __future__ import annotations

import fnmatch
import re
import sys
import unicodedata

import yaml

# glorfindel/config.py VALID_AUTONOMY_MODES (full_auto is deferred: refused there, not kept
# here), VALID_PRIORITIES — tests/unit/test_glorfindel_host.py holds them equal.
KNOWN_MODES = ("human_only", "non_disruptive")
KNOWN_PRIORITIES = ("essential", "standard", "quiet")
# glorfindel/config.py _ASSETS_KEYS, _ASSETS_ENTRY_KEYS (assets:), _AUTONOMY_KEYS, _AUTONOMY_ASSET_KEYS
# (the former format), REASON_MAX — held equal by the same test.
ASSETS_KEYS = ("default_mode", "allow_destructive", "list")
ASSET_KEYS = ("match", "mode", "priority", "reason")
AUTONOMY_KEYS = ("default", "assets", "allow_destructive")
AUTONOMY_ASSET_KEYS = ("match", "mode", "critical")
REASON_MAX = 200
# The first release that reads assets: (PRI2a and PRI2b, one release) — held to the CHANGELOG by the test.
ASSETS_SINCE = (0, 6, 10)
# The containers that mount glorfindel-config.yaml (docker-compose.yml): the watch first, which must be read.
CONTAINERS = ("eregion-watch", "eregion-war-room", "eregion-bot", "eregion-restore")
# The CD's TAG_RE (infra/glorfindel-host/cd/eregion_cd.py): the form a release labels its image with.
VERSION_RE = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
ESSENTIAL, STANDARD, QUIET = KNOWN_PRIORITIES
HUMAN = "human_only"
KEPT = "kept from Imladris"
_PRUDENCE = {"human_only": 0, "non_disruptive": 1}
_RANK = {QUIET: 0, STANDARD: 1, ESSENTIAL: 2}
_PATTERN = set("*?[]")


class Refused(Exception):
    """The push stops: nothing is sent, and the message says why."""


# ── the reading, as the watch's (PR5) ────────────────────────────────────────────────────────────

def parse_h0(text: str | None) -> tuple[dict | None, str]:
    """Imladris's config as a table, before any refusal: ``(config, "")``, or ``(None, why)`` when it is not
    one — ``host_config`` then judges it (``refusal``), and names the essential VMs a refusal loses."""
    if text is None or not text.strip():
        return None, "absent, empty or unread"
    try:
        cfg = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, "unreadable (YAML)"
    if not isinstance(cfg, dict):
        return None, "of an unknown shape"
    return cfg, ""


def read_h0(text: str | None, reads_assets: bool = True) -> tuple[dict | None, str]:
    """Imladris's config, as the push read it: ``(config, "")``, or ``(None, why)`` when it cannot be
    trusted — then nothing of it is kept."""
    cfg, why = parse_h0(text)
    if cfg is None:
        return None, why
    why = refusal(cfg, reads_assets)
    return (None, why) if why else (cfg, "")


def read_local(text: str | None):
    """The workstation's config, as the push reads it: absent, empty, not UTF-8 or not YAML — Refused, even
    under HUMAN_ONLY=1: an empty config pushed would take Imladris's backends, exceptions and isolation away."""
    if text is None or not text.strip():
        raise Refused("the workstation's config unread (absent, empty or not UTF-8): nothing sent")
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        raise Refused("the workstation's config unreadable (YAML): nothing sent") from None


def refusal(cfg: dict, reads_assets: bool = True) -> str:
    """Why this config keeps nothing — "" when it can be read. What Glorfindel's strict reading refuses at
    the watch's start (glorfindel/config_assets.py, ``check_sections``) is refused whole: a config the
    watch would not run is no config whose modes and levels are kept — never one VM dropped and the
    others kept (a watch that would not run made one that acts). ``reads_assets``: whether the release
    that reads it knows ``assets:`` (a release before refuses the section)."""
    if "autonomy" in cfg and "assets" in cfg:
        return "of an unknown shape (assets: and the former autonomy: in one file, both formats)"
    if "assets" in cfg:
        if not reads_assets:
            return "of an unknown shape (assets:, which Imladris's release does not read)"
        return _assets_refusal(cfg["assets"])
    return _autonomy_refusal(cfg.get("autonomy"))


def _mode_ok(value) -> bool:
    return isinstance(value, str) and value in KNOWN_MODES


def _texts_ok(value) -> bool:
    return value is None or (isinstance(value, list) and all(isinstance(v, str) for v in value))


def _match_ok(entry: dict) -> bool:
    return isinstance(entry.get("match"), str) and bool(entry["match"].strip())


def _reason_ok(value) -> bool:
    """CFG2's form, as the watch reads it: one line, no control character, at most REASON_MAX characters."""
    if value is None:
        return True
    return (isinstance(value, str) and len(value) <= REASON_MAX
            and not any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in value))


def _assets_refusal(raw) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, dict):
        return "of an unknown shape (assets: is not a table)"
    if set(raw) - set(ASSETS_KEYS):
        return "of an unknown shape (assets: a key more)"
    if "default_mode" in raw and not _mode_ok(raw["default_mode"]):
        return "of an unknown shape (assets.default_mode outside the known modes)"
    if not _texts_ok(raw.get("allow_destructive")):
        return "of an unknown shape (assets.allow_destructive is not a list of names)"
    entries = raw.get("list")
    if entries is not None and not isinstance(entries, list):
        return "of an unknown shape (assets.list is not a list)"
    seen: set[str] = set()
    for i, a in enumerate(entries or []):
        why = _entry_refusal(a)
        if why:
            return f"of an unknown shape (assets.list[{i}] {why})"
        if a["match"].lower() in seen:
            return f"of an unknown shape (assets.list[{i}]: one entry per name or pattern, case ignored)"
        seen.add(a["match"].lower())
    return ""


def _entry_refusal(a) -> str:
    if not isinstance(a, dict):
        return "is not a table match, mode, priority, reason"
    if set(a) - set(ASSET_KEYS):
        return "has other keys than match, mode, priority and reason"
    if not _match_ok(a):
        return "has no match"
    if "mode" not in a and "priority" not in a:
        return "says nothing: neither a mode nor a priority"
    if "mode" in a and not _mode_ok(a["mode"]):
        return "has a mode outside the known modes"
    if "priority" in a and not (isinstance(a["priority"], str) and a["priority"] in KNOWN_PRIORITIES):
        return "has a priority outside essential, standard and quiet"
    if not _reason_ok(a.get("reason")):
        return "has a reason that is not one line of at most 200 characters"
    return ""


def _autonomy_refusal(autonomy) -> str:
    if autonomy is None:
        return ""
    if not isinstance(autonomy, dict):
        return "of an unknown shape (autonomy)"
    if set(autonomy) - set(AUTONOMY_KEYS):
        return "of an unknown shape (autonomy: a key more)"
    if "default" in autonomy and not _mode_ok(autonomy["default"]):
        return "of an unknown shape (autonomy.default outside the known modes)"
    if not _texts_ok(autonomy.get("allow_destructive")):
        return "of an unknown shape (autonomy.allow_destructive is not a list of names)"
    entries = autonomy.get("assets")
    if entries is not None and not isinstance(entries, list):
        return "of an unknown shape (autonomy.assets is not a list)"
    for a in entries or []:
        if not isinstance(a, dict):
            return "of an unknown shape (an entry of autonomy.assets is not a table match, mode)"
        if set(a) - set(AUTONOMY_ASSET_KEYS):
            return "of an unknown shape (an entry of autonomy.assets has other keys than match, mode and critical)"
        if not _match_ok(a):
            return "of an unknown shape (an entry of autonomy.assets has no match)"
        if not _mode_ok(a.get("mode")):
            return "of an unknown shape (an entry of autonomy.assets outside the known modes)"
        if "critical" in a and not isinstance(a["critical"], bool):
            return "of an unknown shape (an entry of autonomy.assets whose critical is neither true nor false)"
    return ""


def read_release(text: str | None) -> tuple[bool, str]:
    """``(reads assets:, what is said)`` from the lines ``/<container> <version label>`` that the push reads
    on Imladris (``docker inspect``): ``assets:`` only when the watch is read and every container read runs
    a release at ``ASSETS_SINCE`` or after — anything else, the former format, which every release reads."""
    runs: dict[str, str] = {}
    for line in (text or "").splitlines():
        name, _, version = line.strip().partition(" ")
        if name.lstrip("/") in CONTAINERS:
            runs[name.lstrip("/")] = version.strip()
    if CONTAINERS[0] not in runs:
        return False, "Imladris's release unreadable (no version read from its watch)"
    since = "v" + ".".join(map(str, ASSETS_SINCE))
    for name, version in runs.items():
        m = VERSION_RE.fullmatch(version)
        if m is None:
            return False, f"Imladris's release unreadable ({name}: {version or 'no version'}, not a release)"
        if tuple(int(g) for g in m.groups()) < ASSETS_SINCE:
            return False, f"Imladris runs {version} ({name}), before {since}: it reads autonomy: only"
    return True, f"Imladris runs {runs[CONTAINERS[0]]}: it reads assets:"


# ── the model, as the watch resolves it ──────────────────────────────────────────────────────────

def rules_of(cfg: dict | None) -> list[dict]:
    """The entries of a config ``refusal`` accepts, both formats in one shape: ``{match, mode?, priority?,
    reason?}`` — the former ``critical: true`` read as ``priority: essential``."""
    cfg = cfg or {}
    if "assets" in cfg:
        return [dict(a) for a in (cfg["assets"] or {}).get("list") or []]
    out = []
    for a in (cfg.get("autonomy") or {}).get("assets") or []:
        out.append({"match": a["match"], "mode": a["mode"], **({"priority": ESSENTIAL} if a.get("critical") else {})})
    return out


def _governing(rules: list[dict], name: str, key: str, tied):
    """Q6, as glorfindel/config.py ``_by_specificity``: among the entries that carry ``key``, the exact ones
    (case ignored), else the longest pattern that covers the name — ``tied`` picks among those as specific."""
    name = name.lower()
    carrying = [r for r in rules if r.get(key) is not None]
    exact = [r[key] for r in carrying if r["match"].lower() == name]
    if exact:
        return tied(exact)
    matches = [r for r in carrying if fnmatch.fnmatchcase(name, r["match"].lower())]
    if not matches:
        return None
    longest = max(len(r["match"]) for r in matches)
    return tied([r[key] for r in matches if len(r["match"]) == longest])


def resolve(rules: list[dict], name: str, default: str = HUMAN) -> str:
    """The mode the watch gives the name: the most prudent among those as specific."""
    mode = _governing(rules, name, "mode", lambda modes: min(modes, key=_PRUDENCE.__getitem__))
    return default if mode is None else mode


def level_of(rules: list[dict], name: str) -> str:
    """The level the watch gives the name: the highest among those as specific; none, standard."""
    level = _governing(rules, name, "priority", lambda levels: max(levels, key=_RANK.__getitem__))
    return STANDARD if level is None else level


def _is_pattern(name: str) -> bool:
    return bool(_PATTERN & set(name))


def to_autonomy(entries: list[dict], default: str = HUMAN) -> tuple[list[dict], list[tuple[str, str]]]:
    """The entries of ``assets.list`` in the former format, as glorfindel/config_migrate.py ``_to_autonomy``
    converts them (§5.6; the test holds the two equal): each entry that carries a mode with it, ``essential``
    as ``critical: true``; an ``essential`` entry without a mode with the mode its name has (``resolve``),
    ``human_only`` for a pattern — never a bolder mode; ``quiet``, ``standard`` and ``reason`` dropped."""
    out, notes = [], []
    for r in entries:
        name = r["match"]
        if r.get("reason"):
            notes.append((name, "its reason dropped: the former format has none"))
        if r.get("priority") not in (None, ESSENTIAL):
            notes.append((name, f"priority {r['priority']} dropped: the former format has only critical: true"))
        if r.get("mode") is not None:
            entry = {"match": name, "mode": r["mode"]}
        elif r.get("priority") != ESSENTIAL:
            continue
        elif _is_pattern(name):
            entry = {"match": name, "mode": HUMAN}
            notes.append((name, "essential without a mode, a pattern: written human_only"))
        else:
            entry = {"match": name, "mode": resolve(entries, name, default)}
            notes.append((name, f"essential without a mode: written with the mode it has, {entry['mode']}"))
        if r.get("priority") == ESSENTIAL:
            entry["critical"] = True
        out.append(entry)
    return out, notes


# ── what the push sends ──────────────────────────────────────────────────────────────────────────

def _carried(h0_rules: list[dict], human_only: bool) -> dict[str, dict]:
    """Imladris's entries the push keeps, one per name or pattern (case ignored): its level, the highest of
    its entries, patterns and quiet included; its reason; the mode of an exact name, the most prudent of its
    entries — a pattern's mode never, no mode at all under HUMAN_ONLY=1."""
    out: dict[str, dict] = {}
    for r in h0_rules:
        e = out.setdefault(r["match"].lower(), {"match": r["match"]})
        if r.get("priority") is not None:
            e["priority"] = max(e.get("priority", r["priority"]), r["priority"], key=_RANK.__getitem__)
        if r.get("reason") and "reason" not in e:
            e["reason"] = r["reason"]
        if r.get("mode") is not None and not human_only and not _is_pattern(r["match"]):
            e["mode"] = min(e.get("mode", r["mode"]), r["mode"], key=_PRUDENCE.__getitem__)
    return out


def _local_levels(rules: list[dict]) -> dict[str, tuple[str, str]]:
    """The workstation's levels: {name or pattern, case ignored: (its spelling, the highest of its entries)}."""
    out: dict[str, tuple[str, str]] = {}
    for r in rules:
        if r.get("priority") is not None:
            key = r["match"].lower()
            spelled, level = out.get(key, (r["match"], r["priority"]))
            out[key] = (spelled, max(level, r["priority"], key=_RANK.__getitem__))
    return out


def _not_pushed(name: str, level: str, h0_read: bool) -> str:
    """Why a level of the workstation is never pushed, whatever Imladris holds — "" when it may be."""
    if level == QUIET:
        return "quiet from the workstation: not pushed — quiet comes from Imladris only"
    if level == STANDARD and _is_pattern(name):
        return "standard on a pattern from the workstation: not pushed — it could lower a VM no name shows"
    if level != ESSENTIAL and not h0_read:
        return f"{level} from the workstation: not pushed — Imladris's levels unread"
    return ""


def _lowered(h0_rules: list[dict], rules: list[dict], cited: list[str]) -> str:
    """PR4: the first name or pattern cited whose level ``rules`` gives lower than Imladris does — "" none."""
    return next((n for n in cited if _RANK[level_of(rules, n)] < _RANK[level_of(h0_rules, n)]), "")


def _levels(pushed: dict[str, dict], h0_rules: list[dict], local: list[dict], h0_read: bool) -> list[tuple[str, str]]:
    """The workstation's levels added to ``pushed`` (in place) when they lower nothing; what was not, said."""
    cited = list(dict.fromkeys(r["match"].lower() for r in (*h0_rules, *local)))
    said = []
    for key, (name, level) in _local_levels(local).items():
        if why := _not_pushed(name, level, h0_read):
            said.append((name, why))
            continue
        before = pushed.get(key)
        entry = dict(before or {"match": name})
        entry["priority"] = level
        pushed[key] = entry
        if lowered := _lowered(h0_rules, list(pushed.values()), cited):
            said.append((name, f"{level} from the workstation lowers {lowered} on Imladris: not pushed"))
            if before is None:
                del pushed[key]
            else:
                pushed[key] = before
        elif before is None or before.get("priority") != entry["priority"]:
            said.append((name, f"{level} from the workstation"))
    return said


def host_config(cfg: dict, h0: dict | None = None, *, h0_why: str = "", human_only: bool = False,
                reads_assets: bool = False, release_why: str = "", to: str = "") -> tuple[dict, list[tuple]]:
    """``(config to push, report)`` — the report: ``(name, mode sent, level sent, where it comes from)``, read
    on the config written, and ``("*", "", "", what)`` for what concerns every VM. ``h0`` is checked by
    ``refusal`` here too: a caller that did not go through ``read_h0`` gets the same rule. Raises Refused
    when the workstation's config is one the watch would refuse (not under HUMAN_ONLY=1)."""
    if not isinstance(cfg, dict):
        raise Refused("the workstation's config is not a YAML table: nothing sent")
    raw, levels_only = h0, False
    if h0 is not None and (why := refusal(h0, reads_assets)):
        if not reads_assets and "assets" in h0 and not refusal(h0, True):
            levels_only = True          # an assets: file its watch reads if the release does: levels kept
        else:
            h0, h0_why = None, why
    fmt = "assets" if reads_assets and to != "autonomy" else "autonomy"
    report: list[tuple] = [("*", "", "", _format_said(fmt, reads_assets, release_why, to))]
    if human_only:
        report.append(("*", HUMAN, "", "HUMAN_ONLY=1: every VM back to human_only"))
    if h0 is None:
        report.append(("*", HUMAN, "", f"Imladris's config {h0_why or 'unread'}: every VM in human_only"))
    elif levels_only:
        report.append(("*", HUMAN, "", "Imladris's config is in assets:, which its release may not read: its "
                                       "levels kept, its modes not carried — every VM in human_only"))
    elif fmt == "assets" and "autonomy" in h0:
        report.append(("*", "", "", "Imladris: autonomy: migrated to assets:, at equal values"))
    local = _local_rules(cfg, human_only, report)
    h0_rules = rules_of(h0)
    pushed = _carried(h0_rules, human_only or levels_only)
    said = _levels(pushed, h0_rules, local, h0 is not None)
    entries = [e for e in pushed.values() if "mode" in e or "priority" in e]
    out = {k: v for k, v in cfg.items() if k not in ("autonomy", "assets")}
    if fmt == "assets":
        out["assets"] = {"default_mode": HUMAN, "allow_destructive": [], "list": entries}
    else:
        converted, notes = to_autonomy(entries)
        out["autonomy"] = {"default": HUMAN, "allow_destructive": [], "assets": converted}
        said += notes
    if why := refusal(out, fmt == "assets"):              # never what the watch of Imladris would refuse
        raise Refused(f"the config computed would be refused ({why}): nothing sent")
    lost = _essentials_of(raw) if h0 is None and isinstance(raw, dict) else []
    modes_why = "HUMAN_ONLY=1" if human_only else LEVELS_ONLY if levels_only else ""
    return out, report + _rows(out, h0_rules, local, said, modes_why, lost)


LEVELS_ONLY = "its level kept from Imladris, its mode not (its release may not read assets:)"


def _essentials_of(cfg: dict) -> list[str]:
    """The names and patterns a config refused says essential — read as far as it reads, to say each one lost."""
    out = []
    for section, key in (("assets", "list"), ("autonomy", "assets")):
        items = cfg[section].get(key) if isinstance(cfg.get(section), dict) else None
        for a in items if isinstance(items, list) else []:
            if (isinstance(a, dict) and isinstance(a.get("match"), str) and a["match"].strip()
                    and (a.get("priority") == ESSENTIAL or a.get("critical") is True)):
                out.append(a["match"])
    return list(dict.fromkeys(out))


def _format_said(fmt: str, reads_assets: bool, release_why: str, to: str) -> str:
    release = release_why or "Imladris's release unread"
    if fmt == "assets":
        return f"{release} — assets: written"
    if to == "autonomy" and reads_assets:
        return f"{release} — --to autonomy: the former format written (the way back)"
    return f"{release} — the former format autonomy: written, which every release reads until 1.0"


def _local_rules(cfg: dict, human_only: bool, report: list) -> list[dict]:
    """The workstation's entries — its config refused as the watch would refuse it: the push stops, but
    under HUMAN_ONLY=1, which none of its entries then reaches (said)."""
    why = refusal(cfg)
    if not why:
        return rules_of(cfg)
    if not human_only:
        raise Refused(f"the workstation's config is {why}: the watch would refuse it — nothing sent")
    report.append(("*", HUMAN, "", f"the workstation's config is {why}: none of its entries carried (HUMAN_ONLY=1)"))
    return []


def _rows(out: dict, h0_rules: list[dict], local: list[dict], said: list[tuple[str, str]],
          modes_why: str, lost: list[str]) -> list[tuple]:
    """One row per name or pattern cited, its mode and its level read on the config written — never what
    was meant: the report says what Imladris's watch will read; each essential of a refused Imladris too."""
    written = rules_of(out)
    lost_keys = {n.lower() for n in lost}
    rows = []
    for r in (*h0_rules, *local, *({"match": n} for n in lost)):
        key, name = r["match"].lower(), r["match"]
        if key in {row[0].lower() for row in rows}:
            continue
        on_h0 = [h for h in h0_rules if h["match"].lower() == key]
        if key in lost_keys:
            why = ("essential on Imladris, kept by the workstation's" if level_of(written, name) == ESSENTIAL
                   else "essential on Imladris, lost: its config refused")
        elif not on_h0:
            why = "unknown to Imladris"
        elif modes_why:
            why = modes_why
        elif any(h.get("mode") for h in on_h0):
            why = "a pattern on Imladris, its mode not carried" if _is_pattern(name) else KEPT
        else:
            why = "its level kept from Imladris, no mode of its own there"
        notes = [n for k, n in said if k.lower() == key]
        rows.append((name, resolve(written, name), level_of(written, name), "; ".join([why, *notes])))
    return rows


def printable(text) -> str:
    """What Imladris's config says, shown in the operator's terminal: printable characters only — a
    name read on Imladris never carries an escape sequence to it."""
    return "".join(c if c.isprintable() else "?" for c in str(text))


def render(report) -> list[str]:
    report = [tuple(printable(x) for x in row) for row in report]
    width = max([len(row[0]) for row in report] + [10])
    return [f"  {name:<{width}}  {mode:<15} {level:<10} {why}" for name, mode, level, why in report] or [
        "  no VM with a mode of its own: all in human_only (the default)"]


def _read(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="host_config.py")
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--h0", default=None, help="the config in place on Imladris, read by the push")
    ap.add_argument("--release", default=None, help="the version labels of Imladris's containers, read by the push")
    ap.add_argument("--human-only", action="store_true", help="every VM in human_only (HUMAN_ONLY=1)")
    ap.add_argument("--to", choices=["autonomy"], default="", help="the former format, whatever Imladris runs")
    args = ap.parse_args(argv)
    reads_assets, release_why = read_release(_read(args.release))
    h0, why = parse_h0(_read(args.h0))
    try:
        cfg = read_local(_read(args.src))
        out, report = host_config(cfg, h0, h0_why=why, human_only=args.human_only, reads_assets=reads_assets,
                                  release_why=release_why, to=args.to)
    except Refused as exc:
        print(f"  ✗ {exc}", file=sys.stderr)
        return 1
    with open(args.dst, "w", encoding="utf-8") as f:
        yaml.safe_dump(out, f, sort_keys=False)
    print("  Sent to Imladris (the default: human_only):")
    print("\n".join(render(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
