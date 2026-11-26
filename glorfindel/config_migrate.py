"""PRI2a (#1219): `glorfindel config migrate` — the former format `autonomy:` written as `assets:`, at equal values
(docs/design/classification.md, §5.4), and back (`--to autonomy`, §5.6: the way back to a release that does
not read `assets:`).

- **Through CFG4's writer** (glorfindel/config_edit.py, the operation `migrate`): in round trip — the section
  replaced where it stands, every other byte kept (the comments inside it are not carried over: said) —,
  under the file's lock, refused on a file the strict reading refuses or on a result it would refuse.
- **At equal values** (PR7): `autonomy.default` → `default_mode`, `allow_destructive` as it is, each entry of
  `autonomy.assets` an entry of `list` with its mode, `critical: true` → `priority: essential`. The former
  format's duplicates (one name or pattern twice, case ignored) are merged into one entry: the mode the
  former format gave them (the most prudent, AUC), the highest priority — said. CFG4 classes the migration
  neutral; one it would not class neutral is refused, nothing written.
- **Back to the former format**: `default_mode` → `autonomy.default`, each entry that carries a mode with its
  mode, `essential` → `critical: true`. The former format needs a mode on each entry: an `essential` entry
  without one gets the mode its VM has (`resolve`), `human_only` for a pattern — never a bolder mode.
  `quiet`, `standard` and `reason` have no former equivalent: dropped, and said, with every name whose mode or
  priority changes.
- **Imladris**: the push (`make imladris-push`) does not read `assets:` yet; the command says it.
"""
from __future__ import annotations

import copy
import difflib
import json

import click

_BARE = ("human_only", "non_disruptive", "essential", "standard", "quiet")
HUMAN = "human_only"
IMLADRIS = ("Imladris: do not push this file yet — make imladris-push does not read assets: until its next "
            "change, and a watch of an older release refuses the section. Keep pushing a file in the former "
            "format (glorfindel config migrate --to autonomy), or migrate Imladris's file on the host.")


def _is_pattern(name: str) -> bool:
    return any(c in name for c in "*?[")


def _changes(before, after) -> list[str]:
    """Every name or pattern cited whose mode or priority differs between the two models."""
    out = []
    for key in sorted({r.match.lower() for r in (*before.assets, *after.assets)}):
        if (m0 := before.resolve(key)) != (m1 := after.resolve(key)):
            out.append(f"{key}: mode {m0} to {m1}")
        if (p0 := before.level_of(key)) != (p1 := after.level_of(key)):
            out.append(f"{key}: priority {p0} to {p1}")
    return out


def _to_assets(data: dict, cfg) -> tuple[dict, list[str]]:
    from glorfindel.config import ESSENTIAL, _most_prudent
    groups: dict[str, list] = {}
    for i, r in enumerate(cfg.assets):
        groups.setdefault(r.match.lower(), []).append((i, r))
    entries, notes = [], []
    for members in groups.values():
        rules = [r for _, r in members]
        entry = {"match": rules[0].match, "mode": _most_prudent(rules)}
        if any(r.priority == ESSENTIAL for r in rules):
            entry["priority"] = ESSENTIAL
        entries.append(entry)
        if len(members) > 1:
            notes.append(f"autonomy.assets{[i for i, _ in members]} name the same VM or pattern ({rules[0].match}): "
                         f"merged into one entry — mode {entry['mode']}, the one the former format read"
                         + (", priority essential" if "priority" in entry else ""))
    notes += [f"autonomy.assets[{i}] critical: true written priority: essential"
              for i, r in enumerate(cfg.assets) if r.priority == ESSENTIAL]
    section: dict = {"default_mode": cfg.default}
    if "allow_destructive" in (data.get("autonomy") or {}):
        section["allow_destructive"] = list(cfg.allow_destructive)
    if entries:
        section["list"] = entries
    return section, notes


def _to_autonomy(data: dict, cfg) -> tuple[dict, list[str]]:
    from glorfindel.config import ESSENTIAL
    entries, notes = [], []
    for i, r in enumerate(cfg.assets):
        where = f"assets.list[{i}] ({r.match})"
        if r.reason:
            notes.append(f"{where}: its reason dropped — the former format has none")
        if r.priority not in (None, ESSENTIAL):
            notes.append(f"{where}: priority {r.priority} dropped — the former format has only critical: true")
        if r.mode is not None:
            entry = {"match": r.match, "mode": r.mode}
        elif r.priority != ESSENTIAL:
            continue
        elif _is_pattern(r.match):
            entry = {"match": r.match, "mode": HUMAN}
            notes.append(f"{where}: essential without a mode, a pattern — written human_only, never bolder than "
                         "the mode of the VMs it covers")
        else:
            entry = {"match": r.match, "mode": cfg.resolve(r.match)}
            notes.append(f"{where}: essential without a mode — written with the mode it has, {entry['mode']}")
        if r.priority == ESSENTIAL:
            entry["critical"] = True
        entries.append(entry)
    section: dict = {"default": cfg.default}
    if "allow_destructive" in (data.get("assets") or {}):
        section["allow_destructive"] = list(cfg.allow_destructive)
    if entries:
        section["assets"] = entries
    return section, notes


def migrated(data: dict, to: str) -> tuple[dict, list[str]]:
    """(the file's dictionary in the format ``to`` — `assets` or `autonomy` —, what the migration says). The
    file must pass the strict reading, in the other format (EditRefused otherwise)."""
    from glorfindel.config import _parse_config
    from glorfindel.config_edit import EditRefused
    old = "autonomy" if to == "assets" else "assets"
    if to in data:
        raise EditRefused("exists", f"the file is already written in {to}: — nothing to migrate")
    if old not in data:
        raise EditRefused("not_found", f"no {old}: in the file — nothing to migrate")
    cfg = _parse_config(data).autonomy
    section, notes = (_to_assets if to == "assets" else _to_autonomy)(data, cfg)
    out = {k: copy.deepcopy(v) for k, v in data.items() if k != old}
    out[to] = section
    return out, notes + _changes(cfg, _parse_config(out).autonomy)


# ── the text: the section replaced where it stands ───────────────────────────────────────────────

def _scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and value in _BARE:
        return value
    return json.dumps(value, ensure_ascii=False)


def section_lines(name: str, value, indent: int = 0) -> list[str]:
    """The YAML lines of a section of the file (tables, lists of tables of scalars, scalars) — a list empty
    written `[]`."""
    pad = " " * indent
    if isinstance(value, dict):
        return [f"{pad}{name}:"] + [line for k, v in value.items() for line in section_lines(k, v, indent + 2)]
    if not isinstance(value, list):
        return [f"{pad}{name}: {_scalar(value)}"]
    if not value:
        return [f"{pad}{name}: []"]
    out = [f"{pad}{name}:"]
    for item in value:
        if not isinstance(item, dict):
            out.append(f"{pad}  - {_scalar(item)}")
            continue
        keys = list(item)
        out.append(f"{pad}  - {keys[0]}: {_scalar(item[keys[0]])}")
        out += [f"{pad}    {k}: {_scalar(item[k])}" for k in keys[1:]]
    return out


def splice_section(t, root, old: str, new: str, value) -> None:
    """The top-level section ``old`` replaced, where it stands, by ``new`` (glorfindel/config_edit.py's text)."""
    import yaml
    from glorfindel.config_edit import _NULL, EditRefused, _content_end, _key
    key, node = _key(root, old) if root is not None else (None, None)
    if key is None:
        raise EditRefused("not_found", f"no {old}: in the file — nothing to migrate")
    empty = isinstance(node, yaml.ScalarNode) and node.tag == _NULL and node.start_mark.index == node.end_mark.index
    end = t.line_end(key.end_mark.index if empty else _content_end(node))
    t.splice(t.line_start(key.start_mark.index), end, "".join(
        line + t.nl for line in section_lines(new, value, key.start_mark.column)))


def comments_inside(text: str, root, old: str) -> bool:
    """Whether the section ``old`` holds a comment the migration does not carry over."""
    from glorfindel.config_edit import _content_end, _key
    key, node = _key(root, old) if root is not None else (None, None)
    return key is not None and "#" in text[key.start_mark.index:_content_end(node)]


# ── the command ──────────────────────────────────────────────────────────────────────────────────

@click.group("config")
def config_group():
    """glorfindel-config.yaml: its format."""


@config_group.command("migrate")
@click.option("--to", "to", type=click.Choice(["assets", "autonomy"]), default="assets", show_default=True,
              help="assets: the format of this release; autonomy: the former one, for a release that does not "
                   "read assets:")
@click.option("--path", "path", default=None, type=click.Path(dir_okay=False),
              help="the file (default: the one the watch reads)")
@click.option("--yes", is_flag=True, help="write without asking, once the change is shown")
def migrate(to: str, path: str | None, yes: bool) -> None:
    """Write glorfindel-config.yaml in the other format, at equal values: the change shown, then written."""
    from pathlib import Path

    import yaml

    from glorfindel.config import _DEFAULT_PATHS, edit_config
    from glorfindel.config_class import classify
    from glorfindel.config_edit import EditRefused, _check_layout, apply_change, digest
    cfg_path = Path(path) if path else next((p for p in _DEFAULT_PATHS if p.exists()), None)
    if cfg_path is None or not cfg_path.exists():
        raise click.ClickException("no glorfindel-config.yaml found: nothing to migrate")
    raw = cfg_path.read_bytes()
    text = raw.decode("utf-8")
    op = {"op": "migrate", "args": {"to": to}}
    try:
        new = apply_change(text, op)
        _, notes = migrated(yaml.safe_load(text) or {}, to)
        lost = comments_inside(text, _check_layout(text), "autonomy" if to == "assets" else "assets")
    except EditRefused as exc:
        raise click.ClickException(f"{cfg_path}: {exc}") from None
    click.echo("".join(difflib.unified_diff(text.splitlines(True), new.splitlines(True), str(cfg_path),
                                            f"{cfg_path} ({to}:)")))
    said = classify(text, new)
    for note in notes + (["the comments inside the former section are not carried over"] if lost else []):
        click.echo(f"  note: {note}")
    click.echo(f"  class: {said['class']}" + ("" if said["class"] == "neutral" else f" — {'; '.join(said['reasons'])}"))
    if to == "assets":
        click.echo(f"  {IMLADRIS}")
    if not yes and not click.confirm(f"Write {cfg_path}?", default=False):
        raise click.Abort()
    try:
        out = edit_config(cfg_path, op, base=digest(raw), vms=[])
    except EditRefused as exc:
        raise click.ClickException(f"{cfg_path}: {exc}") from None
    except OSError as exc:              # a config mounted read-only (EROFS), or not ours to write (EACCES)
        raise click.ClickException(f"{cfg_path} can't be written ({exc.strerror or type(exc).__name__}): nothing "
                                   "is written (a config mounted read-only, as in the watch's container, is migrated elsewhere)") from None
    click.echo(f"written: {cfg_path} ({out['before'][:15]}… → {out['after'][:15]}…), class {out['class']}")
