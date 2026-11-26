"""CFG4 (#1129): the round-trip write of glorfindel-config.yaml — a change applied to the text, never to a
dictionary dumped again (docs/design/configuration-console.md, §3.2).

`apply_change(text, op) → text` changes the one entry an operation of a closed list names and keeps every
other byte: comments, the order of the keys, quotes, blank lines. It splices the text where PyYAML's own
reading puts each node (`yaml.compose`, its start and end marks), so no library is added: what is not touched
is not written again. Three guards, each refusing before anything is written:

- the file must pass the strict reading first (A3): a file refused is corrected by hand, where the fault was
  made, never rewritten in silence (§3.3);
- the text produced is read back by PyYAML and must be the dictionary the operation asks for, exactly — a
  splice that would land elsewhere (an anchor, a key written twice, a layout this module does not know)
  is refused, never written;
- the result passes the strict reading (A3): `reason` too long, a line break, an address refused — nothing.

`digest(text)` is the version of a file: the SHA-256 of its bytes. `inverse(text, op)` is the operation that
undoes `op` applied to `text` (the history's revert, §3.4: `exclude` ↔ `unexclude`, `never_block_add` ↔
`never_block_remove`, `set_mode` → the previous mode or `unset_mode`). The class of a change (relax, tighten,
neutral) is glorfindel/config_class.py, from the two texts alone.

The operations write exact names only (Q7): a VM's name, never a pattern; a pattern written by hand stays as
it is, and is never changed nor removed here.

PRI2a (#1219): **each writer keeps the file's format** — `assets.list` and `assets.default_mode` in a file
written in `assets:`, `autonomy.assets` and `autonomy.default` in the former format, or in a file that has
neither. None migrates in silence: `migrate` is an operation of its own (glorfindel/config_migrate.py, the
command `glorfindel config migrate`). In `assets:`, setting a mode on an entry that gives only a priority adds
its `mode:`; unsetting the mode of an entry that gives a priority takes only its `mode:` away.
"""
from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
import re

import yaml

OPS = ("set_mode", "unset_mode", "set_default_mode", "exclude", "unexclude", "never_block_add", "never_block_remove",
       "migrate")
_ARGS = {"set_mode": {"vm", "mode"}, "unset_mode": {"vm"}, "set_default_mode": {"mode"}, "migrate": {"to"},
         "exclude": {"vm", "rules", "reason"}, "unexclude": {"vm"},
         "never_block_add": {"address"}, "never_block_remove": {"address"}}
# A VM's name as Azure gives it: letters, digits, `.`, `_`, `-` — no pattern character, no space.
_VM_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,79}")
_RULE_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,79}")
_PRUDENCE = {"human_only": 0, "non_disruptive": 1}
_NULL = "tag:yaml.org,2002:null"


class EditRefused(ValueError):
    """An operation refused, nothing written: `code` (bad_op, bad_args, pattern, config_refused,
    not_found, exists, ambiguous, layout, mismatch, config_changed) and what to do."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def digest(text: str | bytes) -> str:
    """The version of a file (§3.3): the SHA-256 of its bytes."""
    data = text.encode("utf-8") if isinstance(text, str) else text
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ── the operations: their arguments, exact ───────────────────────────────────────────────────────

def _vm(args: dict) -> str:
    vm = args.get("vm")
    if not isinstance(vm, str) or not vm:
        raise EditRefused("bad_args", "vm : le nom exact d'une VM est attendu")
    if any(c in vm for c in "*?[]"):
        raise EditRefused("pattern", f"« {vm} » est un motif : la console n'écrit que des noms exacts (Q7) ; "
                                     "un motif s'écrit à la main")
    if not _VM_NAME.fullmatch(vm):
        raise EditRefused("bad_args", f"« {vm} » n'est pas un nom de VM (lettres, chiffres, . _ -)")
    return vm


def _mode(args: dict) -> str:
    mode = args.get("mode")
    if mode not in _PRUDENCE:
        raise EditRefused("bad_args", f"mode : human_only ou non_disruptive, pas {mode!r}")
    return mode


def _address(args: dict) -> str:
    raw = args.get("address")
    if not isinstance(raw, str):
        raise EditRefused("bad_args", "address : une adresse ou un préfixe CIDR (texte) est attendu")
    from glorfindel.config import validate_never_block
    accepted, rejected = validate_never_block([raw])
    if rejected:
        raise EditRefused("config_refused", f"never_block : {rejected[0][0]} — {rejected[0][1]}")
    return accepted[0]


def check_op(op: dict) -> tuple[str, dict]:
    """(name, args) of an operation of the closed list, its fields exact — never YAML."""
    if not isinstance(op, dict) or set(op) != {"op", "args"} or op["op"] not in OPS or not isinstance(op["args"], dict):
        raise EditRefused("bad_op", f"opération inconnue ou mal formée (opérations : {', '.join(OPS)})")
    name, args = op["op"], op["args"]
    if set(args) != _ARGS[name]:
        raise EditRefused("bad_args", f"{name} : champs attendus {', '.join(sorted(_ARGS[name]))}")
    if name == "exclude":
        rules, reason = args["rules"], args["reason"]
        if rules != "all" and not (isinstance(rules, list) and rules
                                   and all(isinstance(r, str) and _RULE_NAME.fullmatch(r) for r in rules)):
            raise EditRefused("bad_args", "rules : « all » ou une liste de noms de règles")
        if not isinstance(reason, str):
            raise EditRefused("bad_args", "reason : un texte est attendu")
    if name == "migrate" and args["to"] not in ("assets", "autonomy"):
        raise EditRefused("bad_args", "to: assets (the format of PRI2a) or autonomy (the former format)")
    return name, args


def form_paths(data: dict) -> tuple[str, str, str]:
    """PRI2a: (section, list, default) the writers use in this file — its own format, never migrated:
    ``assets``/``list``/``default_mode`` in a file written in `assets:`, the former format otherwise."""
    return ("assets", "list", "default_mode") if "assets" in (data or {}) else ("autonomy", "assets", "default")


# ── the expected dictionary: what the operation asks for ─────────────────────────────────────────

def _same(a, b) -> bool:
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()


def _exact(entries, field: str, vm: str) -> list[int]:
    return [i for i, e in enumerate(entries or []) if isinstance(e, dict) and _same(e.get(field), vm)]


def _canon(item) -> str | None:
    try:
        return str(ipaddress.ip_network(str(item).strip(), strict=False))
    except ValueError:
        return None


def expected(data: dict, name: str, args: dict) -> dict:
    """The dictionary `name` asks for, from the dictionary the file holds (refused: EditRefused)."""
    out = copy.deepcopy(data)
    sec, lst, dflt = form_paths(data)
    if name == "migrate":
        from glorfindel.config_migrate import migrated
        return migrated(data, args["to"])[0]
    if name in ("set_mode", "unset_mode"):
        vm = _vm(args)
        autonomy = out.get(sec) or {}                     # `autonomy:` with no value reads None
        if name == "set_mode":
            out[sec] = autonomy
        assets = autonomy.get(lst) or []
        named = _exact(assets, "match", vm)
        if name == "set_mode":
            mode = _mode(args)
            for i in named:
                assets[i]["mode"] = mode
            if not named:
                assets.append({"match": vm, "mode": mode})
            autonomy[lst] = assets
        else:
            named = [i for i in named if "mode" in assets[i]]
            if not named:
                raise EditRefused("not_found", f"{sec}.{lst} : aucune entrée ne nomme {vm}")
            for i in named:                               # PRI2a: an entry that gives a priority keeps it
                if "priority" in assets[i]:
                    del assets[i]["mode"]
            autonomy[lst] = [e for i, e in enumerate(assets) if i not in named or "priority" in e]
    elif name == "set_default_mode":
        mode = _mode(args)
        autonomy = out.get(sec)
        if autonomy is None:
            out[sec] = autonomy = {}
        autonomy[dflt] = mode
    elif name in ("exclude", "unexclude"):
        vm = _vm(args)
        entries = out.get("exceptions") or []
        named = _exact(entries, "asset_pattern", vm)
        if name == "exclude":
            if named:
                raise EditRefused("exists", f"exceptions : {vm} y est déjà ; la retirer d'abord (unexclude)")
            entry = {"asset_pattern": vm}
            entry.update({"exclude_all": True} if args["rules"] == "all" else {"exclude_rules": list(args["rules"])})
            if args["reason"]:
                entry["reason"] = args["reason"]
            out["exceptions"] = entries + [entry]
        else:
            if len(named) != 1:
                raise EditRefused("ambiguous" if named else "not_found",
                                  f"exceptions : {len(named)} entrée(s) nomment {vm} — une seule se retire ici")
            out["exceptions"] = [e for i, e in enumerate(entries) if i not in named]
    else:
        address = _address(args)
        items = out.get("never_block") or []
        at = [i for i, x in enumerate(items) if _canon(x) == address]
        if name == "never_block_add":
            if at:
                raise EditRefused("exists", f"never_block : {address} y est déjà")
            out["never_block"] = items + [address]
        else:
            if not at:
                raise EditRefused("not_found", f"never_block : {address} n'y est pas")
            out["never_block"] = [x for i, x in enumerate(items) if i not in at]
    return out


# ── the text: where each node is ─────────────────────────────────────────────────────────────────

class _Text:
    """The file's text, and the splices made to it (applied from the end, so marks stay true)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.nl = "\r\n" if "\r\n" in text else "\n"
        self.edits: list[tuple[int, int, str]] = []

    def line_start(self, index: int) -> int:
        return self.text.rfind("\n", 0, index) + 1

    def line_end(self, index: int) -> int:
        """Just after the newline of the line holding `index` (the end of the text without one)."""
        at = self.text.find("\n", index)
        return len(self.text) if at < 0 else at + 1

    def splice(self, start: int, end: int, new: str) -> None:
        self.edits.append((start, end, new))

    def insert_lines(self, at: int, lines: list[str]) -> None:
        """Whole lines at `at`, a line's start (or the text's end, a newline added before if missing)."""
        body = "".join(line + self.nl for line in lines)
        if at == len(self.text) and self.text and not self.text.endswith("\n"):
            body = self.nl + body
        self.splice(at, at, body)

    def result(self) -> str:
        out = self.text
        for start, end, new in sorted(self.edits, key=lambda e: (e[0], e[1]), reverse=True):
            out = out[:start] + new + out[end:]
        return out


def _content_end(node) -> int:
    """The index just after a node's last character of content — never its trailing comments: a block
    collection's end mark is the next token's start, past them."""
    if isinstance(node, yaml.ScalarNode) or getattr(node, "flow_style", False):
        return node.end_mark.index
    if isinstance(node, yaml.MappingNode):
        return max((max(_content_end(k), _content_end(v)) for k, v in node.value), default=node.start_mark.index)
    return max((_content_end(i) for i in node.value), default=node.start_mark.index)


def _key(mapping, name: str):
    found = [(k, v) for k, v in mapping.value if isinstance(k, yaml.ScalarNode) and k.value == name]
    return found[0] if found else (None, None)


def _check_layout(text: str):
    """The composed root, or EditRefused: several documents, an anchor or an alias, a key written twice,
    a root that is not a block mapping."""
    try:
        if any(isinstance(e, yaml.AliasEvent) or getattr(e, "anchor", None) for e in yaml.parse(text)):
            raise EditRefused("layout", "ancres et alias YAML : ce fichier s'édite à la main")
        root = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        raise EditRefused("config_refused", f"YAML illisible : {exc}") from exc
    if root is None:
        return None
    if not isinstance(root, yaml.MappingNode) or root.flow_style:
        raise EditRefused("layout", "la racine du fichier doit être une table en bloc")

    def walk(node):
        if isinstance(node, yaml.ScalarNode) and node.style in ("|", ">"):
            # A block scalar's end mark runs past its last line, over the comments after it: brought back
            # to its last character that is not blank, so that nothing spliced after it moves them.
            end = node.end_mark.index
            while end > node.start_mark.index and text[end - 1] in " \t\r\n":
                end -= 1
            m = node.end_mark
            node.end_mark = yaml.Mark(m.name, end, m.line, m.column, m.buffer, m.pointer)
        if isinstance(node, yaml.MappingNode):
            keys = [k.value for k, _ in node.value if isinstance(k, yaml.ScalarNode)]
            if len(keys) != len(set(keys)):
                raise EditRefused("layout", "une clé écrite deux fois : ce fichier s'édite à la main")
            for _, v in node.value:
                walk(v)
        elif isinstance(node, yaml.SequenceNode):
            for i in node.value:
                walk(i)
    walk(root)
    return root


def _render(value, indent: int) -> list[str]:
    """Lines of YAML for a new list item (a table of scalars, or a scalar) at `indent`: strings in
    double quotes (JSON's escaping is YAML's), booleans bare, the mode bare."""
    def scalar(v) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, list):
            return "[" + ", ".join(scalar(x) for x in v) + "]"
        if isinstance(v, str) and v in _PRUDENCE:
            return v
        return json.dumps(v, ensure_ascii=False)
    pad = " " * indent
    if not isinstance(value, dict):
        return [f"{pad}- {scalar(value)}"]
    keys = list(value)
    return [f"{pad}- {keys[0]}: {scalar(value[keys[0]])}"] + [f"{pad}  {k}: {scalar(value[k])}" for k in keys[1:]]


def _new_key_lines(name: str, value, indent: int) -> list[str]:
    if isinstance(value, list):
        return [f"{' ' * indent}{name}:"] + [line for v in value for line in _render(v, indent + 2)]
    if isinstance(value, dict):
        return [f"{' ' * indent}{name}:"] + [line for k, v in value.items() for line in _new_key_lines(k, v, indent + 2)]
    return [f"{' ' * indent}{name}: {_render(value, 0)[0][2:]}"]


def _put_key(t: _Text, mapping, name: str, value, root: bool = False) -> None:
    """A key absent from `mapping` (None: the empty file), written after its content, its value in block."""
    if mapping is None:
        t.insert_lines(len(t.text), _new_key_lines(name, value, 0))
        return
    if mapping.flow_style or not mapping.value:
        raise EditRefused("layout", "une table écrite en ligne ({…}) : ce fichier s'édite à la main")
    indent = 0 if root else mapping.value[0][0].start_mark.column
    t.insert_lines(t.line_end(_content_end(mapping)), _new_key_lines(name, value, indent))


def _colon_after(t: _Text, key) -> int:
    at = t.text.index(":", key.end_mark.index)
    return at + 1


def _append(t: _Text, key, node, item) -> None:
    """`item` at the end of the list `node` of `key` (an empty value: the list begins)."""
    if isinstance(node, yaml.ScalarNode):
        if node.tag != _NULL:
            raise EditRefused("layout", f"« {key.value} » n'est pas une liste")
        if node.start_mark.index != node.end_mark.index:              # `~`, `null`: from the colon
            t.splice(_colon_after(t, key), node.end_mark.index, "")
        t.insert_lines(t.line_end(key.end_mark.index), _render(item, key.start_mark.column + 2))
        return
    if not isinstance(node, yaml.SequenceNode):
        raise EditRefused("layout", f"« {key.value} » n'est pas une liste")
    if node.flow_style:
        if isinstance(item, dict):
            if node.value:
                raise EditRefused("layout", f"« {key.value} » écrite en ligne ([…]) : ce fichier s'édite à la main")
            t.splice(_colon_after(t, key), node.end_mark.index, "")
            t.insert_lines(t.line_end(key.end_mark.index), _render(item, key.start_mark.column + 2))
            return
        text = _render(item, 0)[0][2:]
        if node.value:
            t.splice(_content_end(node.value[-1]), _content_end(node.value[-1]), ", " + text)
        else:
            t.splice(node.start_mark.index + 1, node.start_mark.index + 1, text)
        return
    at = t.line_end(_content_end(node.value[-1]))
    t.insert_lines(at, _render(item, node.start_mark.column))


def _remove(t: _Text, key, node, gone: list[int]) -> None:
    """The items `gone` of the list `node` of `key` — their lines, never the comments after them; a
    list left empty is written `[]`."""
    if node.flow_style:
        if len(gone) == 1 and len(node.value) > 1:             # one item: its text and one separator
            i = gone[0]
            if i:
                t.splice(_content_end(node.value[i - 1]), _content_end(node.value[i]), "")
            else:
                t.splice(node.value[0].start_mark.index, node.value[1].start_mark.index, "")
            return
        keep = [i for i in range(len(node.value)) if i not in gone]
        kept = ", ".join(t.text[node.value[i].start_mark.index:_content_end(node.value[i])] for i in keep)
        t.splice(node.start_mark.index + 1, node.end_mark.index - 1, kept)
        return
    for i in gone:
        item = node.value[i]
        dash = t.text.rfind("-", 0, item.start_mark.index)
        t.splice(t.line_start(dash), t.line_end(_content_end(item)), "")
    if len(gone) == len(node.value):
        at = _colon_after(t, key)
        t.splice(at, at, " []")


def _set_scalar(t: _Text, node, value: str) -> None:
    quote = node.style if node.style in ("'", '"') else ""
    t.splice(node.start_mark.index, node.end_mark.index, f"{quote}{value}{quote}")


def _drop_key(t: _Text, mapping, name: str) -> None:
    """PRI2a: the line of the key `name` of a block mapping, its scalar value with it — never its first key
    (the line of the list's dash): that layout is edited by hand."""
    key, node = _key(mapping, name)
    if mapping.flow_style or key is mapping.value[0][0] or not isinstance(node, yaml.ScalarNode):
        raise EditRefused("layout", f"{name}: this entry's layout is edited by hand")
    t.splice(t.line_start(key.start_mark.index), t.line_end(_content_end(node)), "")


def _fill_empty_flow_map(t: _Text, key, node, name: str, value) -> None:
    """`autonomy: {}` → `autonomy:` and the new key in block below it."""
    t.splice(_colon_after(t, key), node.end_mark.index, "")
    t.insert_lines(t.line_end(key.end_mark.index), _new_key_lines(name, value, key.start_mark.column + 2))


def _section(t: _Text, root, name: str, inner: str, value) -> None:
    """`name.inner` set to `value` (a list's first item, or a scalar), `name` created if absent."""
    key, node = _key(root, name) if root is not None else (None, None)
    if key is None:
        _put_key(t, root, name, {inner: value}, root=True)
        return
    if isinstance(node, yaml.ScalarNode) and node.tag == _NULL:
        if node.start_mark.index != node.end_mark.index:              # `~`, `null`: from the colon
            t.splice(_colon_after(t, key), node.end_mark.index, "")
        t.insert_lines(t.line_end(key.end_mark.index), _new_key_lines(inner, value, key.start_mark.column + 2))
        return
    if not isinstance(node, yaml.MappingNode):
        raise EditRefused("layout", f"« {name} » n'est pas une table")
    if node.flow_style:
        if node.value:
            raise EditRefused("layout", f"« {name} » écrite en ligne ({{…}}) : ce fichier s'édite à la main")
        _fill_empty_flow_map(t, key, node, inner, value)
        return
    _put_key(t, node, inner, value)


def _list(t: _Text, parent, name: str):
    return _key(parent, name) if parent is not None else (None, None)


def _splice(text: str, data: dict, name: str, args: dict, want: dict) -> str:
    t = _Text(text)
    root = _check_layout(text)
    sec, lst, dflt = form_paths(data)
    if name == "migrate":
        from glorfindel.config_migrate import splice_section
        splice_section(t, root, "autonomy" if args["to"] == "assets" else "assets", args["to"], want[args["to"]])
    elif name in ("set_mode", "unset_mode"):
        akey, anode = _list(t, root, sec)
        skey, snode = _key(anode, lst) if isinstance(anode, yaml.MappingNode) else (None, None)
        entries = (data.get(sec) or {}).get(lst) or []
        named = _exact(entries, "match", args["vm"])
        if name == "set_mode":
            if named:
                for i in named:
                    _, mnode = _key(snode.value[i], "mode")
                    if mnode is not None:
                        _set_scalar(t, mnode, args["mode"])
                    elif sec == "assets":              # PRI2a: an entry that gives only a priority
                        _put_key(t, snode.value[i], "mode", args["mode"])
                    else:
                        raise EditRefused("layout", "une entrée d'autonomy.assets sans mode")
            elif skey is None:
                _section(t, root, sec, lst, [want[sec][lst][-1]])
            else:
                _append(t, skey, snode, want[sec][lst][-1])
        else:
            named = [i for i in named if "mode" in entries[i]]
            for i in [i for i in named if "priority" in entries[i]]:
                _drop_key(t, snode.value[i], "mode")
            if gone := [i for i in named if "priority" not in entries[i]]:
                _remove(t, skey, snode, gone)
    elif name == "set_default_mode":
        akey, anode = _list(t, root, sec)
        dkey, dnode = _key(anode, dflt) if isinstance(anode, yaml.MappingNode) else (None, None)
        if dnode is not None and isinstance(dnode, yaml.ScalarNode) and dnode.tag != _NULL:
            _set_scalar(t, dnode, args["mode"])
        elif dnode is not None:
            raise EditRefused("layout", f"{sec}.{dflt} sans valeur : ce fichier s'édite à la main")
        else:
            _section(t, root, sec, dflt, args["mode"])
    else:
        field = "exceptions" if name in ("exclude", "unexclude") else "never_block"
        key, node = _list(t, root, field)
        if name in ("exclude", "never_block_add"):
            item = want[field][-1]
            if key is None:
                _put_key(t, root, field, [item], root=True)
            else:
                _append(t, key, node, item)
        else:
            before = data.get(field) or []
            at = (_exact(before, "asset_pattern", args["vm"]) if field == "exceptions"
                  else [i for i, x in enumerate(before) if _canon(x) == _address(args)])
            _remove(t, key, node, at)
    return t.result()


def apply_change(text: str, op: dict) -> str:
    """The text with `op` applied (module docstring) — refused (EditRefused): nothing to write."""
    from glorfindel.config import ConfigError, _parse_config
    name, args = check_op(op)
    try:
        data = yaml.safe_load(text) if text.strip() else {}
        _parse_config(data or {})
    except (yaml.YAMLError, ConfigError) as exc:
        raise EditRefused("config_refused", f"le fichier est refusé par la lecture stricte — à corriger à la "
                                            f"main d'abord : {exc}") from exc
    data = data or {}
    want = expected(data, name, args)
    new = _splice(text, data, name, args, want)
    try:
        got = yaml.safe_load(new) or {}
    except yaml.YAMLError as exc:
        raise EditRefused("mismatch", f"le texte écrit ne se relit pas : {exc}") from exc
    if got != want:
        raise EditRefused("mismatch", "le texte écrit ne dit pas ce que l'opération demande : rien n'est écrit")
    try:
        _parse_config(got)
    except ConfigError as exc:
        raise EditRefused("config_refused", f"le résultat serait refusé par la lecture stricte : {exc}") from exc
    if name == "migrate" and args["to"] == "assets":
        from glorfindel.config_class import classify
        said = classify(text, new)
        if said["class"] != "neutral":     # PR7: never a migration that changes a mode or a level
            raise EditRefused("mismatch", "the migration would change the defence (" + "; ".join(said["reasons"])
                              + "): nothing is written")
    return new


def inverse(text: str, op: dict) -> dict:
    """The operation that undoes `op` applied to `text` (§3.4)."""
    name, args = check_op(op)
    data = (yaml.safe_load(text) if text.strip() else {}) or {}
    sec, lst, dflt = form_paths(data)
    autonomy = data.get(sec) or {}
    if name == "migrate":
        return {"op": "migrate", "args": {"to": "autonomy" if args["to"] == "assets" else "assets"}}
    if name in ("set_mode", "unset_mode"):
        named = [e for e in autonomy.get(lst) or [] if isinstance(e, dict) and _same(e.get("match"), args["vm"])
                 and "mode" in e]
        if not named:
            return {"op": "unset_mode", "args": {"vm": args["vm"]}}
        mode = min((e.get("mode") for e in named), key=lambda m: _PRUDENCE.get(m, 0))
        return {"op": "set_mode", "args": {"vm": args["vm"], "mode": mode}}
    if name == "set_default_mode":
        return {"op": "set_default_mode", "args": {"mode": autonomy.get(dflt) or "human_only"}}
    if name == "exclude":
        return {"op": "unexclude", "args": {"vm": args["vm"]}}
    if name == "unexclude":
        named = [e for e in data.get("exceptions") or [] if isinstance(e, dict) and _same(e.get("asset_pattern"), args["vm"])]
        if len(named) != 1:
            raise EditRefused("ambiguous" if named else "not_found",
                              f"exceptions : {len(named)} entrée(s) nomment {args['vm']} — une seule se retire ici")
        entry = named[0]
        rules = "all" if entry.get("exclude_all") else list(entry.get("exclude_rules") or [])
        return {"op": "exclude", "args": {"vm": entry["asset_pattern"], "rules": rules,
                                          "reason": str(entry.get("reason") or "")}}
    other = "never_block_remove" if name == "never_block_add" else "never_block_add"
    return {"op": other, "args": {"address": args["address"]}}
