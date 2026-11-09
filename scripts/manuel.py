#!/usr/bin/env python3
"""manuel — the public manual: Eregion's state, component by component, on the project's site (MAN1, #664).

  python3 scripts/manuel.py build    docs/manuel/modules.yaml → docs/manuel/modules.json (make manuel)
  python3 scripts/manuel.py check    the manual valid, its JSON the YAML's own, every lot of changes/ named

`docs/manuel/modules.yaml` is the source a lot's pull request edits: the components, the stations
of their chains (`postes`), the release steps and the bricks. The page (`docs/manuel/index.html`)
reads `modules.json`, generated from it by this file: a page without a library reads JSON natively,
YAML badly — and a JSON written by hand would drift from it. The JSON is the YAML's own dump, frozen
by tests/unit/test_manuel.py.

The YAML is a strict subset, read here without a library (make release runs on python3 alone,
scripts/release.py reads it through `deliver`): top-level keys, each a list of flat mappings;
values double-quoted strings without « \\ » nor « " », integers, `null`, `true`, `false`, plain words
that start with a letter, and flow lists of plain words. Anything else is refused with its line;
the test compares this reader with PyYAML's on the real file.

**The public rule** (the preview Jonathan validated on 06/11, `docs/sessions.md`, « Le manuel
public ») is held here, by `problems`, so that the YAML itself never holds what the page must not
show: a security lot (`SEC-…`, `V-<n>`, `P-0…` in its lots) is a brick under a neutral name only,
« Durcissement de sécurité (#<issue>) », without a note nor a document; no brick has a field for an
operator's gesture or a review (only the keys of BRICK_KEYS); a note only on a brick delivered.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

YAML = "docs/manuel/modules.yaml"
JSON = "docs/manuel/modules.json"
CHANGES = "changes"

ETATS = ("prevue", "dev", "relecture", "main", "livree")
STEP_ETATS = ("publiee", "montage", "prevue")
NATURES = ("code", "ia", "garde", "humain", "option")
# The keys each section's items may have; required ones first. Nothing else — no `geste`, no
# `relecture`, no `attend`: what the private manual shows of the operator stays there.
COMPONENT_KEYS = {"id": True, "nom": True, "role": True, "doc": False}
POSTE_KEYS = {"id": True, "composant": True, "nom": True, "legende": True, "nature": True, "schema": True,
              "chaine": False}
STEP_KEYS = {"version": True, "nom": True, "etat": True, "derniere": False, "date": False, "resume": False}
BRICK_KEYS = {"id": True, "composant": True, "poste": True, "nom": True, "etat": True, "release": True,
              "version": False, "lots": False, "issue": False, "pr": False, "doc": False, "note": False}
SECTIONS = {"composants": COMPONENT_KEYS, "postes": POSTE_KEYS, "releases": STEP_KEYS, "briques": BRICK_KEYS}

# The private manual's rule (its pubBrick), on the lots: a finding of an audit, or its lot.
SENSIBLE = re.compile(r"(^|[^\w])(SEC-|V-\d|P-0)")
NEUTRAL = "Durcissement de sécurité"
ID = re.compile(r"[a-z][a-z0-9-]*")
LOT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
STEP = re.compile(r"\d+\.(?:\d+|x)")
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
DOC = re.compile(r"[A-Za-z0-9][\w./-]*")

_TOP = re.compile(r"([a-z]+):\s*")
_ITEM = re.compile(r"  - ([a-z_]+):(?: (.*))?")
_FIELD = re.compile(r"    ([a-z_]+):(?: (.*))?")
_PLAIN = re.compile(r"[A-Za-z][\w./-]*")
_YAML_WORDS = {"y", "n", "yes", "no", "on", "off", "true", "false", "null", "nan", "inf"}


class ManuelError(ValueError):
    """The YAML is outside the subset this file reads: its line and why."""


# ── the reader, and the writer of one value ─────────────────────────────────────────────

def _scalar(raw: str, where: str):
    raw = raw.strip()
    if raw == "null":
        return None
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"0|[1-9]\d*", raw):
        return int(raw)
    if raw.startswith('"'):
        if len(raw) < 2 or not raw.endswith('"') or '"' in raw[1:-1] or "\\" in raw:
            raise ManuelError(f"{where} : une chaîne entre guillemets droits, sans « \" » ni « \\ » dedans")
        return raw[1:-1]
    if raw.startswith("["):
        if not raw.endswith("]"):
            raise ManuelError(f"{where} : une liste tient sur sa ligne, [a, b]")
        inner = raw[1:-1].strip()
        items = [x.strip() for x in inner.split(",")] if inner else []
        for x in items:
            if not _PLAIN.fullmatch(x) or x.lower() in _YAML_WORDS:
                raise ManuelError(f"{where} : « {x} » — une liste ne tient que des mots simples")
        return items
    if _PLAIN.fullmatch(raw) and raw.lower() not in _YAML_WORDS:
        return raw
    raise ManuelError(f"{where} : « {raw} » — entre guillemets droits, s'il n'est pas un mot simple")


def load(text: str) -> dict:
    """The manual's YAML, read by its subset (module docstring); ManuelError otherwise."""
    data: dict = {}
    section = item = None
    for n, line in enumerate(text.split("\n"), 1):
        where = f"ligne {n}"
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "\t" in line:
            raise ManuelError(f"{where} : une tabulation")
        if m := _TOP.fullmatch(line):
            if m.group(1) in data:
                raise ManuelError(f"{where} : « {m.group(1)} » deux fois")
            section, item = m.group(1), None
            data[section] = []
        elif (m := _ITEM.fullmatch(line)) and section is not None:
            item = {}
            data[section].append(item)
            item[m.group(1)] = _scalar(m.group(2) or "", where) if m.group(2) is not None else None
        elif (m := _FIELD.fullmatch(line)) and item is not None:
            if m.group(1) in item:
                raise ManuelError(f"{where} : « {m.group(1)} » deux fois dans un même élément")
            item[m.group(1)] = _scalar(m.group(2) or "", where) if m.group(2) is not None else None
        else:
            raise ManuelError(f"{where} : hors du format du manuel (clé de tête, « - clé: », « clé: »)")
    return data


def quote(value) -> str:
    """A value as the YAML writes it: what `load` reads back as the same value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(value) + "]"
    if _PLAIN.fullmatch(value) and value.lower() not in _YAML_WORDS:
        return value   # a word (an état, an id), as the file writes it
    return f'"{value}"'


def to_json(data: dict) -> str:
    """The JSON the page reads: the YAML's own data, nothing added."""
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


# ── the schema, and the public rule ─────────────────────────────────────────────────────

def sensible(brick: dict) -> bool:
    """A brick of a security lot: its lots name an audit's finding or its lot."""
    return bool(SENSIBLE.search(" ".join(brick.get("lots") or [])))


def neutral_name(brick: dict) -> str:
    issue = brick.get("issue")
    return f"{NEUTRAL} (#{issue})" if isinstance(issue, int) else NEUTRAL


def _items(data: dict, name: str, problems: list[str]) -> list[dict]:
    items = data.get(name)
    if not isinstance(items, list) or not items:
        problems.append(f"{name} : une liste non vide")
        return []
    keys = SECTIONS[name]
    for i, it in enumerate(items):
        label = f"{name}[{i}] ({it.get('id') or it.get('version') or '?'})"
        for k in it:
            if k not in keys:
                problems.append(f"{label} : le champ « {k} » n'existe pas (permis : {', '.join(keys)})")
        for k, required in keys.items():
            if required and (it.get(k) is None or it.get(k) == ""):
                problems.append(f"{label} : « {k} » manque")
    return items


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def problems(data: dict, root: Path | None = None) -> list[str]:
    """Why this manual is refused — [] when it holds. With `root`, each document must exist there."""
    out: list[str] = []
    if not isinstance(data, dict) or set(data) != set(SECTIONS):
        return [f"les sections du manuel sont {', '.join(SECTIONS)}, et elles seules"]
    comps = _items(data, "composants", out)
    postes = _items(data, "postes", out)
    steps = _items(data, "releases", out)
    bricks = _items(data, "briques", out)

    comp_ids = [c.get("id") for c in comps]
    for c in comps:
        if not (isinstance(c.get("id"), str) and ID.fullmatch(c["id"])):
            out.append(f"composant {c.get('id')!r} : un id en minuscules, lettres, chiffres, tirets")
    poste_of = {}
    for p in postes:
        if not (isinstance(p.get("id"), str) and ID.fullmatch(p["id"])):
            out.append(f"poste {p.get('id')!r} : un id en minuscules, lettres, chiffres, tirets")
        if p.get("composant") not in comp_ids:
            out.append(f"poste {p.get('id')} : le composant « {p.get('composant')} » n'existe pas")
        if p.get("nature") not in NATURES:
            out.append(f"poste {p.get('id')} : la nature est l'une de {', '.join(NATURES)}")
        poste_of[p.get("id")] = p.get("composant")
    versions = [s.get("version") for s in steps]
    for s in steps:
        v = s.get("version")
        if not (isinstance(v, str) and STEP.fullmatch(v)):
            out.append(f"release {v!r} : X.Y ou X.x")
        if s.get("etat") not in STEP_ETATS:
            out.append(f"release {v} : l'état est l'un de {', '.join(STEP_ETATS)}")
        last = s.get("derniere")
        if s.get("etat") == "publiee" and not (isinstance(last, str) and VERSION.fullmatch(last)):
            out.append(f"release {v} : publiée, elle dit sa dernière version (X.Y.Z)")
        if s.get("etat") != "publiee" and last is not None:
            out.append(f"release {v} : pas de dernière version avant d'être publiée")
        if s.get("date") is not None and not (isinstance(s["date"], str) and DAY.fullmatch(s["date"])):
            out.append(f"release {v} : une date AAAA-MM-JJ")
    if sum(s.get("etat") == "montage" for s in steps) > 1:
        out.append("une seule release en montage à la fois")
    for name, ids in (("composants", comp_ids), ("postes", [p.get("id") for p in postes]),
                      ("releases", versions), ("briques", [b.get("id") for b in bricks])):
        twice = sorted({x for x in ids if ids.count(x) > 1}, key=str)
        if twice:
            out.append(f"{name} : {', '.join(map(str, twice))} deux fois")

    for b in bricks:
        label = f"brique {b.get('id')}"
        if not (isinstance(b.get("id"), str) and ID.fullmatch(b["id"])):
            out.append(f"{label} : un id en minuscules, lettres, chiffres, tirets")
        if b.get("composant") not in comp_ids:
            out.append(f"{label} : le composant « {b.get('composant')} » n'existe pas")
        if b.get("poste") not in poste_of:
            out.append(f"{label} : le poste « {b.get('poste')} » n'existe pas")
        elif poste_of[b["poste"]] != b.get("composant"):
            out.append(f"{label} : le poste « {b['poste']} » est à {poste_of[b['poste']]}, pas à {b.get('composant')}")
        if b.get("etat") not in ETATS:
            out.append(f"{label} : l'état est l'un de {', '.join(ETATS)}")
        if b.get("release") not in versions:
            out.append(f"{label} : la release « {b.get('release')} » n'est pas une étape du manuel")
        version = b.get("version")
        if b.get("etat") == "livree" and not (isinstance(version, str) and VERSION.fullmatch(version)):
            out.append(f"{label} : livrée, elle dit sa version (X.Y.Z)")
        if b.get("etat") != "livree" and version is not None:
            out.append(f"{label} : une version seulement quand elle est livrée")
        lots = b.get("lots")
        if lots is not None and not (isinstance(lots, list) and all(isinstance(x, str) and LOT.fullmatch(x) for x in lots)):
            out.append(f"{label} : ses lots, une liste de noms de lot")
        for k in ("issue", "pr"):
            if b.get(k) is not None and not (isinstance(b[k], int) and not isinstance(b[k], bool) and b[k] > 0):
                out.append(f"{label} : « {k} », un numéro")
        doc = b.get("doc")
        if doc is not None:
            if not (isinstance(doc, str) and DOC.fullmatch(doc) and ".." not in doc):
                out.append(f"{label} : « doc », un chemin du dépôt")
            elif root is not None and not (root / doc).exists():
                out.append(f"{label} : « {doc} » n'existe pas dans le dépôt")
        if not _text(b.get("nom")):
            out.append(f"{label} : un nom")
        # The public rule: nothing said of what is not delivered, nothing of a security lot.
        if b.get("note") is not None and b.get("etat") != "livree":
            out.append(f"{label} : une note seulement sur une brique livrée")
        if sensible(b):
            if b.get("nom") != neutral_name(b):
                out.append(f"{label} : un lot de sécurité s'appelle « {neutral_name(b)} », rien d'autre")
            if b.get("note") is not None:
                out.append(f"{label} : un lot de sécurité n'a pas de note")
            if doc is not None and doc != "SECURITY.md":
                out.append(f"{label} : un lot de sécurité ne renvoie qu'à SECURITY.md")
    for c in comps:
        doc = c.get("doc")
        if doc is not None and root is not None and not (isinstance(doc, str) and (root / doc).exists()):
            out.append(f"composant {c.get('id')} : « {doc} » n'existe pas dans le dépôt")
    return out


def unnamed_fragments(root: Path, data: dict) -> list[str]:
    """The lots of changes/ whose brick does not say they are on main: a lot's pull request brings
    its fragment (changes/<LOT>.md) and moves its brick to `main` in the same tree (MAN1)."""
    where = root / CHANGES
    on_main = {lot for b in data.get("briques") or [] if b.get("etat") == "main" for lot in b.get("lots") or []}
    lots = sorted(p.stem for p in where.glob("*.md") if p.name != "README.md") if where.is_dir() else []
    return [lot for lot in lots if lot not in on_main]


# ── the release: the bricks on main delivered (scripts/release.py prepare) ─────────────

def _blocks(lines: list[str], section: str) -> list[tuple[int, int]]:
    """Each item of `section`: (its first line, the line after its last), in `lines`."""
    out, start, inside = [], None, False
    for i, line in enumerate(lines):
        if _TOP.fullmatch(line):
            if start is not None:
                out.append((start, i))
                start = None
            inside = line.startswith(f"{section}:")
            continue
        if inside and _ITEM.fullmatch(line):
            if start is not None:
                out.append((start, i))
            start = i
    if start is not None:
        out.append((start, len(lines)))
    # An item ends at its last field: the blank lines and comments after it stay outside.
    trimmed = []
    for a, b in out:
        while b > a + 1 and not _FIELD.fullmatch(lines[b - 1]):
            b -= 1
        trimmed.append((a, b))
    return trimmed


def _set(lines: list[str], block: tuple[int, int], key: str, value, after: str) -> tuple[int, int]:
    """`key: value` in the item `block`: its line replaced, or written after `after`'s line."""
    a, b = block
    text = f"    {key}: {quote(value)}"
    first = _ITEM.fullmatch(lines[a])
    if first and first.group(1) == key:
        lines[a] = f"  - {key}: {quote(value)}"
        return block
    for i in range(a + 1, b):
        m = _FIELD.fullmatch(lines[i])
        if m and m.group(1) == key:
            lines[i] = text
            return block
    at = next((i for i in range(a, b) if (m := (_FIELD.fullmatch(lines[i]) or _ITEM.fullmatch(lines[i])))
               and m.group(1) == after), b - 1)
    lines.insert(at + 1, text)
    return a, b + 1


def _field(lines: list[str], block: tuple[int, int], key: str):
    for i in range(block[0], block[1]):
        m = _FIELD.fullmatch(lines[i]) or _ITEM.fullmatch(lines[i])
        if m and m.group(1) == key:
            return _scalar(m.group(2) or "", f"ligne {i + 1}") if m.group(2) is not None else None
    return None


def deliver(text: str, version: str, day: str) -> tuple[str, list[str]]:
    """The manual once X.Y.Z is cut: each brick on `main` becomes `livree` with that version, and
    the step X.Y if the manual has one (else its release is kept); that step becomes `publiee`,
    its last version X.Y.Z, dated; if it was the one `montage`, the next step still `prevue`
    takes its place. Returns the new text and the bricks delivered. The text is edited line by
    line, comments and order kept; ManuelError if what it reads back is not what it meant."""
    m = VERSION.fullmatch(version)
    if not m:
        raise ManuelError(f"« {version} » n'est pas X.Y.Z")
    step = f"{m.group(1)}.{m.group(2)}"
    before = load(text)
    lines = text.split("\n")
    steps = [s.get("version") for s in before.get("releases") or []]
    delivered = []
    for block in reversed(_blocks(lines, "briques")):   # from the end: an insert moves nothing above
        if _field(lines, block, "etat") != "main":
            continue
        delivered.append(_field(lines, block, "id"))
        block = _set(lines, block, "etat", "livree", "etat")
        if step in steps:
            block = _set(lines, block, "release", step, "etat")
        _set(lines, block, "version", version, "release")
    delivered.reverse()
    blocks = _blocks(lines, "releases")
    for n, block in enumerate(blocks):
        if _field(lines, block, "version") != step:
            continue
        was = _field(lines, block, "etat")
        later = blocks[n + 1:]
        if was == "montage" and later and _field(lines, later[0], "etat") == "prevue":
            _set(lines, later[0], "etat", "montage", "nom")
        block = _set(lines, block, "etat", "publiee", "nom")
        block = _set(lines, block, "derniere", version, "etat")
        _set(lines, block, "date", day, "derniere")
        break
    out = "\n".join(lines)
    after = load(out)
    # What it reads back: the same manual, but for the fields it meant to change.
    want = json.loads(json.dumps(before))
    for b in want["briques"]:
        if b.get("etat") == "main":
            b.update({"etat": "livree", "version": version, **({"release": step} if step in steps else {})})
    for i, s in enumerate(want["releases"]):
        if s.get("version") == step:
            if s.get("etat") == "montage" and i + 1 < len(want["releases"]) and want["releases"][i + 1].get("etat") == "prevue":
                want["releases"][i + 1]["etat"] = "montage"
            s.update({"etat": "publiee", "derniere": version, "date": day})
            break
    if after != want:
        raise ManuelError("le manuel relu après la release n'est pas celui attendu : rien n'est écrit")
    return out, delivered


# ── the command ─────────────────────────────────────────────────────────────────────────

def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (["build"], ["check"]):
        print(__doc__.split("\n\n", 1)[0])
        return 2
    root = _root()
    try:
        data = load((root / YAML).read_text(encoding="utf-8"))
    except (OSError, ManuelError) as e:
        print(f"✗ {YAML} : {e}")
        return 1
    found = problems(data, root)
    for p in found:
        print(f"✗ {p}")
    if found:
        return 1
    if argv == ["build"]:
        (root / JSON).write_text(to_json(data), encoding="utf-8")
        print(f"{JSON} écrit depuis {YAML} ({len(data['briques'])} briques)")
        return 0
    stale = not (root / JSON).is_file() or (root / JSON).read_text(encoding="utf-8") != to_json(data)
    if stale:
        print(f"✗ {JSON} n'est pas celui de {YAML} : make manuel")
    missing = unnamed_fragments(root, data)
    for lot in missing:
        print(f"✗ changes/{lot}.md : aucune brique sur main ne nomme {lot} dans ses lots")
    return 1 if stale or missing else 0


if __name__ == "__main__":
    sys.exit(main())
