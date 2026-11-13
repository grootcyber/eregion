"""CMD1 (#797) — no command Glorfindel proposes is invented.

The console proposed `glorfindel isolate <vm> --yes` and `glorfindel block <ip> <vm> --yes` for a held
card, the reassertion `glorfindel block <ip> <id>`, the console `glorfindel respond <id>` for an action it
does not run — and the CLI had neither `isolate` nor `block`, and `respond` takes a file of signals. The
console and the TUI gave `glorfindel ack <8 characters>`, which acknowledged nothing and said it did.

Here every command to copy written in the code — the console (`cliCommand`, the messages of `api.py`),
the reassertion, the watch (`agent.py`, `recovery_watch.py`, `readiness.py`, `tui.py`), the bot and the
CLI's own hints: every string of glorfindel/, eregion_console/ and eregion_core/, the page's scripts —
is read and held against the real CLI, Click's own tree: its command (and sub-command), each option
known to it, a value given to an option that takes one, a choice among its choices, its arguments
neither too many nor too few. A bare mention (« `glorfindel watch` ») names a command that exists; it
is not one to copy. An argument's placeholder is read for what it carries: a VM never stands where a
file of signals is asked, an id never where a VM's `<groupe>/<nom>` is (MSK3b).

No Azure call, no model call; nothing is imported from the console (read as text). Mutants M5205–M5219
(scripts/mutants/CMD1.py).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import click
import pytest

ROOT = Path(__file__).resolve().parents[2]
PY_DIRS = ("glorfindel", "eregion_console", "eregion_core")
JS_DIR = ROOT / "eregion_console" / "static"

# Prose, never a command (the section named « glorfindel »): file, the words.
PROSE = {
    ("eregion_console/sections.py", "glorfindel is always on"),
}

_START = re.compile(r"(?<![\w/.=-])glorfindel (?!commands?\b)([a-z][a-z-]*)")
SEP = " ← "
# Where a command to copy ends: a quote, a backtick, a line, a closing bracket, a double space, a dash or
# a comment after a space, a comma, semicolon or full stop before a space, the end of an HTML tag, rich's
# closing markup.
_END = re.compile(r"[`'\"\n)»>]|\s{2}|\s[—#(]|[,;.](\s|$)|</|\[/")
_HOLE = re.compile(r"⟨(\d+)⟩")
_ANGLE = re.compile(r"<[A-Za-z][^<>\s]*>")


def _rendered(node: ast.AST, holes: list[str]) -> str | None:
    """A string constant as it reads, or an f-string with each of its values a hole « ⟨n⟩ » —
    ``holes[n]`` the expression's source."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(str(v.value))
            else:
                holes.append(ast.unparse(v.value))
                out.append(f"⟨{len(holes) - 1}⟩")
        return "".join(out)
    return None


def _assigned(fn: ast.AST, before: int) -> dict[str, str]:
    """name → the source of its last plain assignment in this function before that line: a hole
    « {rid} » is read for what `rid` holds there (an id, or what `group_and_name` made of it)."""
    out: dict[str, str] = {}
    for n in sorted((n for n in ast.walk(fn) if isinstance(n, ast.Assign) and n.lineno < before),
                    key=lambda n: n.lineno):
        if len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            out[n.targets[0].id] = ast.unparse(n.value)
    return out


def _py_texts(path: Path):
    """(line, text, holes) of every string of a Python file — an f-string once, whole."""
    tree = ast.parse(path.read_text())
    inner: set[int] = set()
    owner: dict[int, ast.AST] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.JoinedStr):
            inner.update(id(v) for v in n.values)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for m in ast.walk(n):
                owner[id(m)] = n                   # the innermost wins: walked after its parent
    for n in ast.walk(tree):
        if id(n) in inner:
            continue
        holes: list[str] = []
        text = _rendered(n, holes)
        if text and "glorfindel " in text:
            fn = owner.get(id(n))
            names = _assigned(fn, n.lineno) if fn is not None else {}
            yield n.lineno, text, [_chain(h, names) for h in holes]


def _chain(expr: str, names: dict[str, str]) -> str:
    """« vm ← rid ← _vm_for_a_command(esc['resource_id']) »: a name read back through what it was
    assigned, three steps at most."""
    links = [expr]
    while links[-1].isidentifier() and links[-1] in names and len(links) < 4 and names[links[-1]] not in links:
        links.append(names[links[-1]])
    return SEP.join(links)


def _js_holes(line: str, holes: list[str]) -> str:
    """A line of a script, each ``${…}`` of a template a hole (braces balanced: a value may hold a
    quote, ``||``, a nested template)."""
    out, i = [], 0
    while i < len(line):
        if line.startswith("${", i):
            depth, j = 1, i + 2
            while j < len(line) and depth:
                depth += {"{": 1, "}": -1}.get(line[j], 0)
                j += 1
            holes.append(line[i + 2:j - 1])
            out.append(f"⟨{len(holes) - 1}⟩")
            i = j
        else:
            out.append(line[i])
            i += 1
    return "".join(out)


def _js_texts(path: Path):
    for no, line in enumerate(path.read_text().splitlines(), 1):
        if line.lstrip().startswith("//") or "glorfindel " not in line:
            continue
        holes: list[str] = []
        text = _js_holes(line, holes).replace("\\n", "\n")
        yield no, text, holes


def _sources():
    for d in PY_DIRS:
        for path in sorted((ROOT / d).rglob("*.py")):
            yield path, _py_texts(path)
    for path in sorted(JS_DIR.glob("*.js")):
        yield path, _js_texts(path)


def proposed() -> list[tuple[str, str, list[str], list[str]]]:
    """(where, the command as written, its words, the holes) for every « glorfindel <word> » of the code."""
    out = []
    for path, texts in _sources():
        rel = str(path.relative_to(ROOT))
        for no, text, holes in texts:
            for m in _START.finditer(text):
                # A placeholder « <ip> », « <groupe>/<nom> » is one word: its « > » ends nothing.
                kept: list[str] = []
                rest = _ANGLE.sub(lambda p: kept.append(p.group(0)) or f"\x01{len(kept) - 1}\x02", text[m.end():])
                cut = _END.search(rest)
                rest = rest[:cut.start()] if cut else rest
                rest = re.sub("\x01(\\d+)\x02", lambda p: kept[int(p.group(1))], rest)
                said = text[m.start():m.end()] + rest
                if any(rel == f and said.startswith(p) for f, p in PROSE):
                    continue
                out.append((f"{rel}:{no}", said.strip(), [m.group(1), *rest.split()], holes))
    return out


def _hole(token: str, holes: list[str]) -> str | None:
    m = _HOLE.fullmatch(token)
    return holes[int(m.group(1))] if m else None


def _placeholder(token: str) -> bool:
    return bool(_HOLE.search(token)) or (token.startswith("<") and token.endswith(">"))


# What a hole or a placeholder carries, read from its expression or its words.
_A_VM = re.compile(r"group_and_name|_vmArg|_vm_for_a_command|\bvm(_arg|Arg|_name|Name)?\b|\brid\b|resource_?[iI]d|"
                   r"<groupe>/<nom>|<vm|<resource")
# A VM's full id, as the code holds it — the subscription in it (MSK2), a homonym of another group taken
# (MSK3b) — unless a command's form was made of it.
_NAMED = re.compile(r"group_and_name|_vmArg|_vm_for_a_command|_name_for_a_command|_short_name")
_RAW_ID = re.compile(r"\b(rid|resource_id|resourceId)\b")
VM_ARGS = ("resource_id", "vm")


def check(words: list[str], holes: list[str], root: click.Group) -> str:
    """Why this command is not one the CLI takes — "" when it is."""
    cmd: click.Command = root
    path = []
    words = list(words)
    while isinstance(cmd, click.Group) and words and words[0] in cmd.commands:
        path.append(words.pop(0))
        cmd = cmd.commands[path[-1]]
    if cmd is root or (isinstance(cmd, click.Group) and words and not words[0].startswith("-")
                       and not any(isinstance(p, click.Argument) for p in cmd.params)):
        return f"no command « glorfindel {' '.join(path + words[:1])} »"
    args = [p for p in cmd.params if isinstance(p, click.Argument)]
    opts = {o: p for p in cmd.params if isinstance(p, click.Option) for o in (*p.opts, *p.secondary_opts)}
    given: list[str] = []
    only_args = False
    i = 0
    while i < len(words):
        w = words[i]
        i += 1
        if w == "--" and not only_args:
            only_args = True
            continue
        if w.startswith("-") and not only_args and not _placeholder(w):
            name, _, value = w.partition("=")
            if name == "--help":
                continue
            p = opts.get(name)
            if p is None:
                return f"« {name} » is no option of glorfindel {' '.join(path)}"
            if p.is_flag or p.count:
                continue
            if not value:
                if i >= len(words):
                    if not given:
                        continue          # a mention (« `glorfindel restore --before` »): the option exists
                    return f"« {name} » takes a value, none given"
                value = words[i]
                i += 1
            if isinstance(p.type, click.Choice) and not _placeholder(value):
                bad = [v for v in value.split("|") if v not in p.type.choices]
                if bad:
                    return f"« {name} {value} »: not among {', '.join(p.type.choices)}"
            continue
        if len(given) >= len(args):
            if _placeholder(w):
                return f"« {w} »: one argument too many for glorfindel {' '.join(path)}"
            break                                  # prose after the command: it ends there
        a = args[len(given)]
        given.append(w)
        if isinstance(a.type, click.Choice) and not _placeholder(w):
            bad = [v for v in w.split("|") if v not in a.type.choices]
            if bad:
                return f"« {w} »: not among {', '.join(a.type.choices)} ({a.name})"
        carried = _hole(w, holes)
        links = carried.split(SEP) if carried is not None else [w]
        if a.name not in VM_ARGS and _placeholder(w) and _A_VM.search(links[0]):
            return f"« {links[0]} » is a VM, where glorfindel {' '.join(path)} takes its {a.name}"
        if (a.name in VM_ARGS and carried is not None and _RAW_ID.search(links[-1])
                and not any(_NAMED.search(x) for x in links)):
            return f"« {carried} » is a VM's full id: a command to copy names it by <groupe>/<nom> (MSK3b)"
    if not given:
        return ""         # a mention (« `glorfindel restore --wait` writes… »): the command, its options exist
    missing = [a.name for a in args[len(given):] if a.required]
    if missing:
        return f"glorfindel {' '.join(path)}: {', '.join(missing)} missing"
    return ""


@pytest.fixture(scope="module")
def cli_tree():
    from glorfindel.cli import cli
    return cli


def test_the_code_proposes_commands_to_check(cli_tree):
    """The reader finds them where the operator reads them — never an empty list that proves nothing."""
    found = {where.split(":")[0] for where, *_ in proposed()}
    for f in ("eregion_console/static/glorfindel.js", "eregion_console/api.py", "glorfindel/reassert.py",
              "glorfindel/agent.py", "glorfindel/recovery_watch.py", "glorfindel/readiness.py", "glorfindel/tui.py",
              "glorfindel/cli.py", "glorfindel/bot.py"):
        assert f in found, f


def test_every_proposed_command_exists_with_its_arguments(cli_tree):
    wrong = [f"{where}: {said!r} — {why}" for where, said, words, holes in proposed()
             if (why := check(words, holes, cli_tree))]
    assert not wrong, "\n".join(wrong)


@pytest.mark.parametrize("command,why", [
    (["isolate", "⟨0⟩", "--yes"], ""),
    (["block", "⟨1⟩", "⟨0⟩", "--yes"], ""),
    (["block", "⟨1⟩", "⟨0⟩", "--scope", "vm", "--yes"], ""),
    (["block", "⟨1⟩", "⟨0⟩", "--scope", "vm|subnet"], ""),
    (["block", "⟨1⟩", "⟨0⟩", "--scope", "nic"], "not among"),
    (["block", "⟨1⟩", "--yes"], "missing"),
    (["release", "⟨0⟩", "⟨1⟩"], "one argument too many"),
    (["isolate", "⟨0⟩", "--force"], "no option"),
    (["respond", "⟨0⟩"], "is a VM"),
    (["respond", "runs/annatar/x_signals.jsonl"], ""),
    (["release", "⟨2⟩", "--yes"], "full id"),
    (["status"], "no command"),
    (["rules", "check", "--live"], ""),
    (["rules", "verify"], "no command"),
    (["restore", "⟨0⟩", "--before"], "takes a value"),
    (["verdict", "⟨1⟩", "right|wrong|unsure"], ""),
    (["verdict", "⟨1⟩", "right|maybe"], "not among"),
    (["unblock", "--yes", "--", "⟨1⟩", "⟨0⟩"], ""),
    (["respond"], ""),                               # a bare mention
])
def test_the_reader_tells_a_command_the_cli_takes(cli_tree, command, why):
    """The checker itself: what it lets through, what it refuses — a hole « ⟨n⟩ » for each value."""
    holes = ["group_and_name(rid)", "ip", "rid"]
    said = check(command, holes, cli_tree)
    assert (why in said) if why else said == "", said


def test_isolate_and_block_are_commands_of_the_cli(cli_tree):
    """CMD1: the gestures the console's card and the reassertion propose — with `--dry-run` and `--yes`,
    as `release` and `unblock`; `block` with its reach."""
    for name, args in (("isolate", ["resource_id"]), ("block", ["ip", "resource_id"])):
        cmd = cli_tree.commands[name]
        assert [p.name for p in cmd.params if isinstance(p, click.Argument)] == args
        flags = {p.name for p in cmd.params if isinstance(p, click.Option) and p.is_flag}
        assert {"dry_run", "yes"} <= flags
    scope = next(p for p in cli_tree.commands["block"].params if p.name == "scope")
    assert list(scope.type.choices) == ["vm", "subnet"] and scope.default == "vm"


def test_an_action_the_console_does_not_run_is_sent_to_commands_that_exist(cli_tree):
    """`respond <id>` takes a file of signals: never proposed for a VM — the card read, made by hand,
    acknowledged."""
    source = (ROOT / "eregion_console" / "api.py").read_text()
    assert "glorfindel respond" not in source
    tree = ast.parse(source)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_not_run_here")
    ns: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "api.py", "exec"), ns)  # its words, no import
    said = ns["_not_run_here"]({"action": "revoke_temp_access", "id": "0123456789abcdef"})
    assert "glorfindel pending" in said and "glorfindel ack 01234567" in said
    for m in _START.finditer(said):
        assert m.group(1) in cli_tree.commands, said


def test_the_anchored_cards_are_one_set(cli_tree):
    """AL1: the CLI's direct gesture refuses the VM a card is only anchored on — the console's, the
    bot's and the TUI's own set, never one that parts."""
    from glorfindel import gestures

    def _set(rel: str) -> set:
        tree = ast.parse((ROOT / rel).read_text())
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", "") == "_ANCHORED_TYPES" for t in n.targets))
        return set(ast.literal_eval(node.value))
    for rel in ("eregion_console/api.py", "glorfindel/bot.py", "glorfindel/tui.py"):
        assert _set(rel) == set(gestures.ANCHORED_TYPES), rel
    js = (JS_DIR / "glorfindel.js").read_text()
    m = re.search(r"const _ANCHORED_TYPES = new Set\(\[([^\]]*)\]\)", js)
    assert m and set(re.findall(r"'([a-z_]+)'", m.group(1))) == set(gestures.ANCHORED_TYPES)
