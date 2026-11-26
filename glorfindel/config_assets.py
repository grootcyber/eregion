"""PRI2a (#1219): the section `assets:` and its former format `autonomy:`, read strictly (A3) into one model —
`AutonomyConfig` (glorfindel/config.py), whose entries carry a mode, a priority, or both
(docs/design/classification.md, §5).

```yaml
assets:
  default_mode: human_only        # the former autonomy.default; human_only when absent
  allow_destructive: []           # the former autonomy.allow_destructive
  list:                           # the former autonomy.assets
    - match: vm-db-prod
      mode: non_disruptive        # optional: without it, the other entries, then default_mode
      priority: essential         # optional: without it, the other entries, then standard
      reason: the ERP database    # optional, one line (CFG2's form)
```

- **An entry** has a `match` (a name or a pattern, case ignored) and at least one of `mode` and `priority`:
  one that says neither is refused, so is any other key, and so is the same `match` twice (case ignored) —
  one entry per name or pattern. An unknown priority (`critical`, a typo) or mode is refused.
- **The former format** (`autonomy:`, read until the 1.0): each entry of `autonomy.assets` carries its mode,
  and `critical: true` is read as `priority: essential` (PRT2). Its duplicates are still read as before
  (the most prudent mode, AUC). A note says it, in English: at the watch's start and in `/api/config` —
  never an error. `glorfindel config migrate` writes the new format (glorfindel/config_migrate.py).
- **Both formats in one file**: refused, whether they agree or not — two places that say a VM's mode are two
  truths.

Every problem is said at once (`check.bad`); a file refused is refused whole, as the rest of the file.
"""
from __future__ import annotations

import difflib

FORMER_NOTE = "autonomy: is the former format of assets: — migrate it (glorfindel config migrate)"
BOTH = ("assets: and the former autonomy: in one file — two places for the same modes: keep assets:, and remove "
        "autonomy: once its entries are in assets: (glorfindel config migrate writes it from a file that holds "
        "autonomy: alone)")


def critical_note(i: int) -> str:
    return f"autonomy.assets[{i}] says `critical: true`, the former name of priority: essential"


def check_sections(data: dict, sections: dict, check):
    """The one model of the two formats (module docstring): `assets:`, else the former `autonomy:` with its
    notes, else the defaults."""
    from glorfindel.config import AutonomyConfig
    if "autonomy" in data and "assets" in data:
        check.bad("assets", BOTH)
        return AutonomyConfig()
    if "assets" in data:
        return _check_assets(sections["assets"], check)
    autonomy = _check_autonomy(sections["autonomy"], check)
    if "autonomy" in data:
        autonomy.form = "autonomy"
        autonomy.notes = [FORMER_NOTE] + autonomy.notes
    return autonomy


def _mode(check, value, where: str) -> str | None:
    from glorfindel.config import _shown, _validate_mode
    if not isinstance(value, str):
        check.bad(where, f"un mode (texte) est attendu, pas {_shown(value)}")
        return None
    try:
        return _validate_mode(value, where=where)
    except ValueError as exc:
        check.problems.append(str(exc))
        return None


def _priority(check, raw: dict, where: str) -> str | None:
    from glorfindel.config import VALID_PRIORITIES, _shown
    value = raw.get("priority")
    if not isinstance(value, str):
        check.bad(f"{where}.priority", f"a priority (text) is expected, not {_shown(value)}")
        return None
    if value in VALID_PRIORITIES:
        return value
    close = difflib.get_close_matches(value, list(VALID_PRIORITIES), n=1, cutoff=0.6)
    hint = f" — did you mean \"{close[0]}\"?" if close else ""
    check.bad(f"{where}.priority", f"unknown priority {_shown(value)}{hint} (priorities: {', '.join(VALID_PRIORITIES)})")
    return None


def _check_assets(raw: dict, check):
    """`assets:` (module docstring): `default_mode`, `allow_destructive`, `list`."""
    from glorfindel.config import (_ASSETS_ENTRY_KEYS, _ASSETS_KEYS, AutonomyConfig, AutonomyRule, _check_reason,
                                   _shown)
    check.keys(raw, "assets", _ASSETS_KEYS)
    default = _mode(check, raw.get("default_mode", "human_only"), "assets.default_mode") or "human_only"
    rules: list = []
    seen: dict[str, int] = {}
    for i, a in enumerate(check.items(raw.get("list"), "assets.list")):
        where = f"assets.list[{i}]"
        if not isinstance(a, dict):
            check.bad(where, f"a table (match, mode, priority, reason) is expected, not {_shown(a)}")
            continue
        check.keys(a, where, _ASSETS_ENTRY_KEYS)
        match = check.text(a, "match", where, required=True)
        if "mode" not in a and "priority" not in a:
            check.bad(where, "an entry that says nothing: give it a mode, a priority, or both")
            continue
        mode = _mode(check, a["mode"], f"{where}.mode") if "mode" in a else None
        priority = _priority(check, a, where) if "priority" in a else None
        reason = _check_reason(a, where, check)
        if match.lower() in seen:
            check.bad(f"{where}.match", f"one entry per name or pattern: {_shown(match)} is already "
                                        f"assets.list[{seen[match.lower()]}] (case ignored)")
            continue
        seen[match.lower()] = i
        if ("mode" in a and mode is None) or ("priority" in a and priority is None):
            continue
        rules.append(AutonomyRule(match=match, mode=mode, priority=priority, reason=reason))
    return AutonomyConfig(default=default, assets=rules,
                          allow_destructive=check.texts(raw, "allow_destructive", "assets"), form="assets")


def _check_autonomy(raw: dict, check):
    """The former format: `autonomy.default`, `autonomy.assets` (each with its mode; `critical: true` read as
    `priority: essential`), `autonomy.allow_destructive`."""
    from glorfindel.config import (ESSENTIAL, _AUTONOMY_ASSET_KEYS, _AUTONOMY_KEYS, AutonomyConfig, AutonomyRule,
                                   _shown)
    check.keys(raw, "autonomy", _AUTONOMY_KEYS)
    default = _mode(check, raw.get("default", "human_only"), "autonomy.default") or "human_only"
    assets = []
    notes = []
    for i, a in enumerate(check.items(raw.get("assets"), "autonomy.assets")):
        where = f"autonomy.assets[{i}]"
        if not isinstance(a, dict):
            check.bad(where, f"une table (match, mode, critical) est attendue, pas {_shown(a)}")
            continue
        check.keys(a, where, _AUTONOMY_ASSET_KEYS)
        match = check.text(a, "match", where, required=True)
        if "mode" not in a:
            check.bad(f"{where}.mode", "obligatoire")
            continue
        m = _mode(check, a["mode"], f"autonomy.assets[match={match or '?'}]")
        # PRT2 (#1160): true or false without quotes — a text, a number, a key left empty: said, refused.
        critical = check.flag(a, "critical", where, False)
        if "critical" in a and a["critical"] is None:
            check.bad(f"{where}.critical", "true ou false est attendu, et la clé est vide ici")
        if critical:
            notes.append(critical_note(i))
        if m is not None:
            assets.append(AutonomyRule(match=match, mode=m, priority=ESSENTIAL if critical else None))
    return AutonomyConfig(
        default=default,
        assets=assets,
        allow_destructive=check.texts(raw, "allow_destructive", "autonomy"),
        notes=notes,
    )
