#!/usr/bin/env python3
"""night_guard — what the night may not merge without Jonathan (NOC1, #1251; docs/sessions.md, « La nuit »).

  night_guard.py check [--base origin/main] [--head REVIEWED] [--repo DIR] [--pr N]
      exit 0: nothing in the change asks for Jonathan, the night may merge it;
      exit 1: refused, each reason on a line — the pull request stays open, unmerged, with a comment
              that says why, and a line for Jonathan in the night's report;
      exit 2: the change could not be read (a ref unknown, git failing): refused as well.

The change is the pull request's diff against its base: from the merge base of BASE and HEAD to HEAD
(what the branch brings, never what main did since). HEAD is the commit the review read and the merge
is tied to (`gh pr merge --match-head-commit`), never the head read later. The night runs the guard of
origin/main (`git show origin/main:scripts/night_guard.py`), never the one of the branch it judges,
before each merge, with `--pr N`; a day session may run it too.

**First, what the CI did** (`--pr N`, the main rule since the review's second round: a list of what to
refuse always has holes). It reads, in the log of the PR's own CI (`ci.yml`, a `pull_request` run of the
repository itself, never of a fork, on HEAD) and in that of main's `push` run on the commit the PR's CI
merged into (`Merge HEAD into BASE`, as actions/checkout says it), for each « lint + tests » job (Python
3.11, 3.12):
- pytest's summary lines (« N passed, M skipped, K xfailed … in Ss »), summed over the job's runs of
  pytest: the tests collected (passed + failed + skipped + xfailed + xpassed + deselected) must not go
  down, the skipped nor the xfailed go up;
- the mutants that `scripts/mutant_anchors.py` counts (« N mutants and C of the control set »): neither
  number may go down.
A line that cannot be read is a refusal. That holds a test taken out of the run however it is done (a
file moved where pytest does not look, an `__init__` on a class, a skip's condition widened, a plugin), as
long as the CI ran it on Linux; and a mutant taken out of the measure (a lot's file renamed `_…`, moved
into a sub-directory).

**Then, what the diff says** (always): it refuses a change that:
- removes or renames a `test_*` function of a collected file (`test_*.py`, `*_test.py`; a class
  `Test*`) — a test whose file or class leaves that pattern counts as removed; a test moved to another
  collected file keeps its name;
- adds a skip, a skipif, an xfail, an importorskip, a `skipTest`, `__test__`, `collect_ignore*`,
  `pytestmark`, a collection hook, `del test_…` or an emptied `parametrize`, read on the syntax tree
  through the imports' aliases (`import pytest as pt`, `from pytest import skip`), each tied to the
  test (or the class, the module) it sits in — a skip moved from one test to another is one added;
- removes a mutant from a lot's file (`scripts/mutants/<name>.py`, as the harness selects them: no
  sub-directory, no `_` first), changes its `new` without its `old`, changes its file, moves it from
  MUTANTS to CONTROL (never red), or adds or changes its reason (the sixth field: `EQUIVALENT:`,
  `TIMING:`, `MULTI-HOST:` take a mutant out of the count); touches `scripts/mutants/_*` or a
  sub-directory of `scripts/mutants/`;
- touches `.github/`, `requirements/`, a `.terraform.lock.hcl`, a `conftest.py`, `pytest.ini`,
  `.pytest.ini`, `tox.ini`, `setup.cfg`, or the dependencies, the entry points (a `pytest11` plugin), the
  build, the pytest or the ruff settings of `pyproject.toml`; adds a module or a package at the
  repository's root (a `pytest.py` there hides pytest);
- touches an invariant's oracle (`tests/unit/test_invariants*.py`, `fake_azure.py`, `fake_aws.py`,
  `invariant_hold.py`) — a question for Jonathan, as INV7 and INV8 were — or the mutation's harness
  (`scripts/mutation_check.py`, `scripts/mutant_anchors.py`, `scripts/mutants/*.json`);
- changes or removes a named threshold or ceiling: a module-level number of
  `tests/unit/test_file_sizes.py`, `tests/unit/test_docs_budget.py` or `glorfindel/read_budget.py`, in
  either direction (raising a ceiling loosens it, lowering a floor or a budget too, and the guard does
  not tell one from the other), or `tests/unit/french_ceiling.json`;
- touches the night's own rails: `.claude/` (the skill, the agents), `scripts/night/`, this guard and
  its tests, `scripts/review_verdict.py`.

What it does not hold: a test whose body is emptied (its name kept), an assertion weakened, a
parametrize's cases cut down, a mutant's TESTS narrowed, a test skipped on Linux CI only through a
condition the counts would not see moving. The review reads those (docs/sessions.md, « La nuit », the
known limits). A lot's mutants file is read by running it, as the harness does: first its syntax tree
against an allowlist (the nodes, the attributes `replace`, `update`, `join`, `split`, `splitlines`,
`items`, the calls to `range`, `list` and the file's own functions, no decorator, no dunder — what the
tree's 285 files use, and nothing that reaches a frame or a builtin), then a child runs it, `python -I`,
its environment reduced to PATH and a throwaway HOME, under CPU, memory and file-size limits and a
timeout, given the same `RENAME` as the harness (an `object()`). That is no sandbox: the child keeps the
network and the user's rights. Standard library only.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import json
import math
import re
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Paths the night never merges: (pattern, reason). A pattern ending in "/" is a directory; one without
# "/" is a file's name anywhere.
PROTECTED = (
    (".github/workflows/", "touches a workflow (.github/workflows/): the sessions' App cannot push it"),
    (".github/", "touches .github/ (CODEOWNERS, the repository's settings)"),
    ("requirements/", "touches the locked dependencies (requirements/)"),
    ("*.terraform.lock.hcl", "touches a Terraform providers' lock (.terraform.lock.hcl)"),
    ("conftest.py", "touches a conftest.py: what pytest collects, skips or deselects"),
    ("pytest.ini", "touches pytest's settings (pytest.ini wins over pyproject.toml)"),
    (".pytest.ini", "touches pytest's settings (.pytest.ini)"),
    ("tox.ini", "touches pytest's settings (tox.ini)"),
    ("setup.cfg", "touches pytest's settings (setup.cfg)"),
    ("tests/unit/test_invariants*.py", "touches an invariant's oracle (the properties and their checks): "
                                       "a question for Jonathan, as INV7 and INV8"),
    ("tests/unit/fake_azure.py", "touches the fake Azure the invariants judge on: a question for Jonathan, "
                                 "as INV7 and INV8"),
    ("tests/unit/fake_aws.py", "touches the fake AWS the invariants judge on: a question for Jonathan"),
    ("tests/unit/invariant_hold.py", "touches what holds the invariants' oracle: a question for Jonathan"),
    ("tests/unit/french_ceiling.json", "touches the French output's ceilings"),
    ("scripts/mutation_check.py", "touches the mutation's harness (its marks, its count, its judgement)"),
    ("scripts/mutant_anchors.py", "touches the mutants' anchors check"),
    ("scripts/mutants/*.json", "touches the mutation's durations or its narrowed tests"),
    ("scripts/mutants/_*", "touches a helper of the lots' files, which the harness never selects"),
    ("scripts/mutants/*/*", "touches a sub-directory of scripts/mutants/, which the harness never reads"),
    (".claude/", "touches the night's own rails (.claude/: the skill, the agents, the settings)"),
    ("scripts/night/", "touches the night's own rails (scripts/night/: its unit, its settings)"),
    ("scripts/night_guard.py", "touches the night's own guard"),
    ("tests/unit/test_night_guard.py", "touches the night's own guard's tests"),
    ("scripts/review_verdict.py", "touches the review's verdict, which the merge reads"),
)
# pyproject.toml: the tables whose change the night never merges.
PYPROJECT = (("project", "dependencies"), ("project", "optional-dependencies"), ("build-system",),
             ("tool", "pytest"), ("project", "entry-points"), ("tool", "ruff"))
# The named thresholds: each module-level number of these files.
THRESHOLDS = ("tests/unit/test_file_sizes.py", "tests/unit/test_docs_budget.py", "glorfindel/read_budget.py")
# A lot's file, as the harness selects them (scripts/mutation_check.py, lot_files): no sub-directory,
# no `_` first.
LOT_FILE = re.compile(r"scripts/mutants/[^/_][^/]*\.py")
# pytest's default collection (pyproject.toml sets none of its own).
COLLECTED = ("test_*.py", "*_test.py")
# A name of pytest's or unittest's that takes a test out of the run, wherever it sits in a dotted path.
SKIP_WORDS = {"skip": "skip", "skipif": "skipif", "xfail": "xfail", "importorskip": "importorskip",
              "skipIf": "skipif", "skipUnless": "skipif", "expectedFailure": "xfail", "SkipTest": "skip"}
SKIP_ROOTS = ("pytest", "_pytest", "unittest")
COLLECTION_NAMES = ("__test__", "collect_ignore", "collect_ignore_glob", "pytestmark")
COLLECTION_HOOKS = ("pytest_collection_modifyitems", "pytest_ignore_collect", "pytest_collect_file",
                    "pytest_pycollect_makeitem", "pytest_generate_tests", "pytest_runtest_setup")
RENAMED = "<RENAME>"
# A lot's file never needs these: refused by name before it runs (the allowlist below refuses them too).
FORBIDDEN = {"open", "eval", "exec", "compile", "getattr", "setattr", "delattr", "globals", "locals", "vars",
             "breakpoint", "input", "exit", "quit", "help", "memoryview"}
# What a lot's file may hold: what the tree's 285 files use (26/11), and a few comparisons beside.
ALLOWED_NODES = {"Module", "Expr", "Assign", "AugAssign", "Constant", "Name", "Load", "Store", "List", "Tuple",
                 "Dict", "Set", "Subscript", "Slice", "BinOp", "Add", "Mult", "BitOr", "Compare", "Eq", "NotEq",
                 "In", "NotIn", "JoinedStr", "FormattedValue", "Call", "Attribute", "keyword", "Starred",
                 "ListComp", "DictComp", "GeneratorExp", "comprehension", "FunctionDef", "arguments", "arg",
                 "Return", "Pass"}
ALLOWED_ATTRS = {"replace", "update", "join", "split", "splitlines", "items"}
ALLOWED_CALLS = {"range", "list"}
CHILD_PATH = "/usr/bin:/bin"
# Run in a child process: a lot's file, its MUTANTS and CONTROL as JSON, the reason (sixth field) too.
_LOADER = (
    "import json, runpy, sys\n"
    "RENAME = object()\n"                                   # the harness's own: scripts/mutation_check.py
    "ns = runpy.run_path(sys.argv[1], init_globals={'RENAME': RENAME})\n"
    "out = []\n"
    "for kind in ('MUTANTS', 'CONTROL'):\n"
    "    for m in list(ns.get(kind, [])):\n"
    "        old = " + repr(RENAMED) + " if m[3] is RENAME else m[3] if isinstance(m[3], str) else repr(m[3])\n"
    "        out.append([str(m[0]), str(m[2]), old, str(m[4]), str(m[5]) if len(m) > 5 else '', kind])\n"
    "print(json.dumps(out))\n"
)


@dataclass(frozen=True)
class Change:
    """A file the change touches: its path before and after (None: added or deleted), its texts."""
    old_path: str | None
    new_path: str | None
    old_text: str | None = None
    new_text: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(p for p in (self.old_path, self.new_path) if p))


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if "/" not in pattern:
        return fnmatch.fnmatchcase(PurePosixPath(path).name, pattern)
    return fnmatch.fnmatchcase(path, pattern)


def protected_paths(changes: list[Change]) -> list[str]:
    out = []
    for c in changes:
        for path in c.paths:
            for pattern, why in PROTECTED:
                if _matches(path, pattern):
                    out.append(f"{path}: {why}")
                    break
    return list(dict.fromkeys(out))


def _table(doc: dict, keys: tuple[str, ...]):
    for k in keys:
        if not isinstance(doc, dict) or k not in doc:
            return None
        doc = doc[k]
    return doc


def pyproject(changes: list[Change]) -> list[str]:
    out = []
    for c in changes:
        if "pyproject.toml" not in c.paths:
            continue
        try:
            old = tomllib.loads(c.old_text or "") if c.old_path else {}
            new = tomllib.loads(c.new_text or "") if c.new_path else {}
        except tomllib.TOMLDecodeError as e:
            out.append(f"pyproject.toml: unreadable ({e}): its dependencies cannot be compared")
            continue
        for keys in PYPROJECT:
            if _table(old, keys) != _table(new, keys):
                out.append(f"pyproject.toml: changes [{'.'.join(keys)}] (the dependencies, the entry points, the "
                           "build, pytest's or ruff's settings)")
    return out


def root_modules(changes: list[Change]) -> list[str]:
    """A module or a package that appears at the repository's root: first on sys.path, it hides whatever
    shares its name (a pytest.py hides pytest)."""
    out = []
    for c in changes:
        new = c.new_path
        if not new or new == c.old_path:
            continue
        if ("/" not in new and new.endswith(".py")) or (new.count("/") == 1 and new.endswith("/__init__.py")):
            out.append(f"{new}: adds a module or a package at the repository's root, first on sys.path")
    return out


# ── Tests: collected, and taken out of the run ─────────────────────────────────────────────────────────

def _collected(path: str | None) -> bool:
    """A file pytest collects by its name."""
    if not path or not path.endswith(".py"):
        return False
    name = PurePosixPath(path).name
    return fnmatch.fnmatchcase(name, COLLECTED[0]) or fnmatch.fnmatchcase(name, COLLECTED[1])


def _scanned(path: str | None) -> bool:
    """A file whose skips count: a collected one, a conftest.py, any module under tests/."""
    return bool(path) and path.endswith(".py") and (
        _collected(path) or path.startswith("tests/") or PurePosixPath(path).name == "conftest.py")


def named_tests(text: str) -> Counter:
    """Each `test*` function pytest collects in a module: at its top level, or in a class `Test*`
    (`TestX.test_y`)."""
    names: Counter = Counter()

    def walk(body, prefix):
        for node in body:
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                walk(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                names[f"{prefix}{node.name}"] += 1

    walk(ast.parse(text).body, "")
    return names


def _aliases(tree: ast.AST) -> tuple[dict[str, str], bool]:
    """What each local name stands for (`pt` → `pytest`, `skip` → `pytest.skip`, `m = pytest.mark` →
    `pytest.mark`), and whether a star import of pytest or unittest puts every name in reach."""
    names: dict[str, str] = {root: root for root in SKIP_ROOTS}     # used without an import line of their own
    star = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    names[a.asname] = a.name
                else:
                    names[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                if a.name == "*":
                    star = star or node.module.split(".")[0] in SKIP_ROOTS
                else:
                    names[a.asname or a.name] = f"{node.module}.{a.name}"
    for _ in range(3):        # `m = pytest.mark`, then `s = m.skip`: chains, a few deep
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if (path := _path(node.value, names, star)) is not None:
                    names[node.targets[0].id] = path
    return names, star


def _path(node, names: dict[str, str], star: bool) -> str | None:
    """The dotted path an expression stands for, through the aliases; None when it is no module's."""
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        return f"pytest.{node.id}" if star else None
    if isinstance(node, ast.Attribute):
        base = _path(node.value, names, star)
        return None if base is None else f"{base}.{node.attr}"
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "getattr" and node.args:
            base = _path(node.args[0], names, star)
            if base is None:
                return None
            arg = node.args[1] if len(node.args) > 1 else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return f"{base}.{arg.value}"
            return f"{base}.<getattr>"
        return _path(node.func, names, star)
    return None


def _skip_kind(path: str | None) -> str | None:
    if not path or path.split(".")[0] not in SKIP_ROOTS:
        return None
    for word in path.split(".")[1:]:
        if word in SKIP_WORDS:
            return SKIP_WORDS[word]
        if word == "<getattr>":
            return "getattr"
    return None


def _digest(node) -> str:
    return hashlib.sha256(ast.dump(node).encode()).hexdigest()[:10]


def skips(text: str) -> set[tuple[str, str]]:
    """Each way a module takes a test out of the run, as (where, what): where is the test, the class or the
    function it sits in (`TestX.test_y`, `_helper`), or `<module>`."""
    tree = ast.parse(text)
    names, star = _aliases(tree)
    found: set[tuple[str, str]] = set()

    def visit(node, scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            inner = node.name if scope == "<module>" else f"{scope}.{node.name}"
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in COLLECTION_HOOKS:
                found.add((inner, f"the collection hook {node.name} ({_digest(node)})"))
            for child in ast.iter_child_nodes(node):
                visit(child, inner)
            return
        if isinstance(node, (ast.Call, ast.Attribute, ast.Name)):
            if (kind := _skip_kind(_path(node, names, star))) is not None:
                found.add((scope, kind))
        if isinstance(node, ast.Attribute) and node.attr == "skipTest":
            found.add((scope, "skipTest"))
        if isinstance(node, ast.Call):
            func = node.func
            target = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if target == "parametrize":
                values = node.args[1] if len(node.args) > 1 else next(
                    (k.value for k in node.keywords if k.arg == "argvalues"), None)
                if isinstance(values, (ast.List, ast.Tuple, ast.Set)) and not values.elts:
                    found.add((scope, "an empty parametrize"))
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                    and func.value.id in COLLECTION_NAMES:
                found.add((scope, f"{func.value.id}.{func.attr}(…) ({_digest(node)})"))
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                name = t.id if isinstance(t, ast.Name) else t.attr if isinstance(t, ast.Attribute) else ""
                if name in COLLECTION_NAMES:
                    found.add((scope, f"{name} = … ({_digest(node)})"))
        if isinstance(node, ast.Delete):
            for t in node.targets:
                name = t.id if isinstance(t, ast.Name) else t.attr if isinstance(t, ast.Attribute) else ""
                if name.startswith("test"):
                    found.add((scope, f"del {name}"))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, "<module>")
    return found


def removed_tests(changes: list[Change]) -> list[str]:
    """A collected test gone (removed, renamed, its file or class out of the collection), across every
    file the change touches (a test moved to another collected file keeps its name); and each skip added,
    tied to where it sits."""
    out, before, after, where = [], Counter(), Counter(), {}
    for c in changes:
        key = c.new_path or c.old_path
        skipped = {}
        for side, path, text, into in (("before", c.old_path, c.old_text, before),
                                       ("after", c.new_path, c.new_text, after)):
            try:
                if _collected(path):
                    names = named_tests(text or "")
                    into.update(names)
                    if into is before:
                        where.update({n: path for n in names if n not in where})
                skipped[side] = skips(text or "") if _scanned(path) else set()
            except SyntaxError as e:
                out.append(f"{path}: unreadable {side} the change ({e.msg}, line {e.lineno}): its tests cannot be "
                           "counted")
                skipped[side] = set()
        for scope, kind in sorted(skipped["after"] - skipped["before"]):
            out.append(f"{key}: adds {kind} to {scope}")
    for name in sorted(before - after):
        out.append(f"{where[name]}: removes or renames the test {name}")
    return out


# ── Mutants ────────────────────────────────────────────────────────────────────────────────────────────

def _dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def precheck(tree: ast.AST) -> None:
    """A lot's file holds strings, tuples, a helper at most: refused before it runs unless each node, each
    attribute and each call is on the allowlist (ALLOWED_NODES, ALLOWED_ATTRS, ALLOWED_CALLS and the file's
    own functions), with no decorator and no dunder. That keeps out what the tree's files never need — an
    import, a frame reached through a generator, a builtin by its name; it is a check of the text, no
    sandbox (the child still runs with the user's rights). ValueError says what."""
    for node in ast.walk(tree):          # by name first: an import, a builtin that reaches out, a dunder
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError(f"an import, line {node.lineno}: refused before running")
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN or _dunder(node.id)):
            raise ValueError(f"{node.id}, line {node.lineno}: refused before running")
        if isinstance(node, ast.Attribute) and _dunder(node.attr):
            raise ValueError(f".{node.attr}, line {node.lineno}: refused before running")
    own = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for node in ast.walk(tree):          # then the allowlist
        kind = type(node).__name__
        line = getattr(node, "lineno", "?")
        if kind not in ALLOWED_NODES:
            raise ValueError(f"{kind}, line {line}: refused before running")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise ValueError(f"a decorator, line {line}: refused before running")
        if isinstance(node, ast.Attribute) and node.attr not in ALLOWED_ATTRS:
            raise ValueError(f".{node.attr}, line {line}: refused before running")
        if isinstance(node, ast.Call):
            func = node.func
            if not (isinstance(func, ast.Attribute) or (isinstance(func, ast.Name)
                                                        and (func.id in ALLOWED_CALLS or func.id in own))):
                raise ValueError(f"a call to {ast.unparse(func)}, line {line}: refused before running")


def _limits(timeout: float):
    def apply():
        import resource
        cpu = math.ceil(timeout) + 1
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    return apply


def load_mutants(text: str, name: str, timeout: float = 60.0, run=subprocess.run) -> dict[str, tuple]:
    """A lot's file's mutants, {id: (file, old, new, reason, MUTANTS or CONTROL)}, read by running it apart
    once its syntax tree is checked. ValueError when it cannot be read."""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise ValueError(f"SyntaxError: {e.msg}, line {e.lineno}") from None
    precheck(tree)
    with tempfile.TemporaryDirectory(prefix="night-guard-") as tmp:
        path = Path(tmp) / PurePosixPath(name).name
        path.write_text(text, encoding="utf-8")
        try:
            done = run([sys.executable, "-I", "-c", _LOADER, str(path)], cwd=tmp, capture_output=True, text=True,
                       timeout=timeout, env={"PATH": CHILD_PATH, "HOME": tmp}, preexec_fn=_limits(timeout))
        except subprocess.TimeoutExpired:
            raise ValueError(f"not read within {timeout:.0f} s") from None
        if done.returncode != 0:
            last = (done.stderr.strip().splitlines() or [f"exit {done.returncode}"])[-1]
            raise ValueError(last)
        try:
            return {m[0]: (m[1], m[2], m[3], m[4], m[5]) for m in json.loads(done.stdout)}
        except (ValueError, IndexError, TypeError) as e:
            raise ValueError(f"what it defines is not read ({e})") from None


def mutants(changes: list[Change], load=load_mutants) -> list[str]:
    """A mutant gone (from every lot's file the change touches: one moved to another file stays), its `new`
    changed while its `old` stays, its file changed, or a reason added or changed (a known survivor is no
    longer counted): the bug it re-introduces is no longer the one it was measured on."""
    out, before, after = [], {}, {}
    for c in changes:
        for side, path, text, into in (("before", c.old_path, c.old_text, before),
                                       ("after", c.new_path, c.new_text, after)):
            if not path or not LOT_FILE.fullmatch(path):
                continue
            try:
                into.update(load(text or "", path))
            except ValueError as e:
                out.append(f"{path}: its mutants unreadable {side} the change ({e})")
    for mid in sorted(set(before) - set(after)):
        out.append(f"removes the mutant {mid}")
    for mid in sorted(set(before) & set(after)):
        (file0, old0, new0, why0, kind0), (file1, old1, new1, why1, kind1) = before[mid], after[mid]
        if new0 != new1 and old0 == old1:
            out.append(f"changes the mutant {mid}'s new text without its old one")
        if file0 != file1:
            out.append(f"changes the mutant {mid}'s file ({file0} -> {file1})")
        if kind0 == "MUTANTS" and kind1 == "CONTROL":
            out.append(f"moves the mutant {mid} into the control set, which is never red")
        if why1 and why1 != why0:
            out.append(f"gives the mutant {mid} a reason ({why1[:40]}…): a known survivor is no longer counted")
    for mid in sorted(set(after) - set(before)):
        if after[mid][3]:
            out.append(f"adds the mutant {mid} with a reason ({after[mid][3][:40]}…): born uncounted")
    return out


# ── Named thresholds ───────────────────────────────────────────────────────────────────────────────────

def _number(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        n = _number(node.operand)
        return None if n is None else (-n if isinstance(node.op, ast.USub) else n)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Add, ast.Sub)):
        a, b = _number(node.left), _number(node.right)
        if a is None or b is None:
            return None
        return a * b if isinstance(node.op, ast.Mult) else a + b if isinstance(node.op, ast.Add) else a - b
    return None


def named_numbers(text: str) -> dict[str, float]:
    """Each number a module-level assignment holds, by where it is: `SLACK`, `CAPS['glorfindel/cli.py']`,
    `ARM(2)`, `ARM(floor=)`."""
    found: dict[str, float] = {}

    def walk(node, at):
        if (n := _number(node)) is not None:
            found[at] = n
        elif isinstance(node, ast.Dict):
            for i, (k, v) in enumerate(zip(node.keys, node.values)):
                key = repr(k.value) if isinstance(k, ast.Constant) else str(i)
                walk(v, f"{at}[{key}]")
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for i, v in enumerate(node.elts):
                walk(v, f"{at}[{i}]")
        elif isinstance(node, ast.Call):
            for i, v in enumerate(node.args):
                walk(v, f"{at}({i})")
            for kw in node.keywords:
                walk(kw.value, f"{at}({kw.arg}=)")

    for stmt in ast.parse(text).body:
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets, value = [stmt.target], stmt.value
        else:
            continue
        for t in targets:
            if isinstance(t, ast.Name):
                walk(value, t.id)
    return found


def thresholds(changes: list[Change]) -> list[str]:
    out = []
    for c in changes:
        for path in c.paths:
            if path not in THRESHOLDS:
                continue
            if path != c.new_path:
                out.append(f"{path}: removed or renamed, and its named thresholds with it")
                continue
            try:
                old = named_numbers(c.old_text or "") if c.old_path == path else {}
                new = named_numbers(c.new_text or "")
            except SyntaxError as e:
                out.append(f"{path}: unreadable ({e.msg}): its thresholds cannot be compared")
                continue
            for at in sorted(old):
                if at not in new:
                    out.append(f"{path}: removes the threshold {at} ({old[at]:g})")
                elif new[at] != old[at]:
                    how = "raises" if new[at] > old[at] else "lowers"
                    out.append(f"{path}: {how} the threshold {at} ({old[at]:g} -> {new[at]:g})")
    return out


def judge(changes: list[Change], load=load_mutants) -> list[str]:
    """Every reason the night may not merge this change without Jonathan; none: it may."""
    return (protected_paths(changes) + pyproject(changes) + root_modules(changes) + removed_tests(changes)
            + mutants(changes, load) + thresholds(changes))


# ── What the CI did: the counts of the PR's run against main's ─────────────────────────────────────────

CI_JOBS = ("lint + tests (py3.11)", "lint + tests (py3.12)")
COLLECTED_KEYS = ("passed", "failed", "skipped", "xfailed", "xpassed", "deselected")
SUMMARY_LINE = re.compile(r"\b\d+ (?:passed|failed|skipped|xfailed|xpassed|deselected|errors?)\b[^\n]* in "
                          r"\d+(?:\.\d+)?s\b")
SUMMARY_PART = re.compile(r"\b(\d+) (passed|failed|skipped|xfailed|xpassed|deselected|errors?|warnings?)\b")
ANCHORS_LINE = re.compile(r"\b(\d+) mutants and (\d+) of the control set\b")
MERGED = re.compile(r"\bMerge ([0-9a-f]{40}) into ([0-9a-f]{40})\b")
BASE_CONCLUSIONS = ("success", "failure")      # main red is what the night fixes: its counts still read


def pytest_counts(log: str) -> dict[str, int] | None:
    """pytest's summary lines of a job's log, summed (each run of pytest in the job), with `collected`;
    None when the log holds none."""
    total: Counter = Counter()
    lines = 0
    for line in log.splitlines():
        if not SUMMARY_LINE.search(line):
            continue
        lines += 1
        for n, word in SUMMARY_PART.findall(line):
            total[{"errors": "error", "warnings": "warning"}.get(word, word)] += int(n)
    if not lines:
        return None
    total["collected"] = sum(total[k] for k in COLLECTED_KEYS)
    total["lines"] = lines
    return dict(total)


def mutant_counts(log: str) -> tuple[int, int] | None:
    """What scripts/mutant_anchors.py counted in a job's log: (mutants, the control set); None unread."""
    found = ANCHORS_LINE.findall(log)
    return (int(found[-1][0]), int(found[-1][1])) if found else None


def compare_counts(job: str, base: dict | None, head: dict | None) -> list[str]:
    if base is None or head is None:
        return [f"{job}: pytest's summary line not read on {'main' if base is None else 'the PR'}: the tests run "
                "cannot be compared"]
    out = []
    if head["collected"] < base["collected"]:
        out.append(f"{job}: {base['collected'] - head['collected']} test(s) fewer collected than on main "
                   f"({base['collected']} -> {head['collected']})")
    for key in ("skipped", "xfailed"):
        if head.get(key, 0) > base.get(key, 0):
            out.append(f"{job}: {key} goes up ({base.get(key, 0)} -> {head.get(key, 0)})")
    return out


def compare_mutants(job: str, base: tuple | None, head: tuple | None) -> list[str]:
    if base is None or head is None:
        return [f"{job}: the mutants' count (mutant_anchors.py) not read on {'main' if base is None else 'the PR'}"]
    out = []
    if head[0] < base[0]:
        out.append(f"{job}: {base[0] - head[0]} mutant(s) fewer measured than on main ({base[0]} -> {head[0]})")
    if head[1] < base[1]:
        out.append(f"{job}: the control set goes down ({base[1]} -> {head[1]})")
    return out


def _gh(args: list[str]) -> str:
    run = subprocess.run(["gh", *args], capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {run.stderr.strip() or run.returncode}")
    return run.stdout


def _ci_run(gh, *, event: str, commit: str, branch: str, conclusions=("success",)) -> dict | None:
    runs = json.loads(gh(["run", "list", "--workflow", "ci.yml", "--event", event, "--commit", commit, "--branch",
                          branch, "--json", "databaseId,headSha,headBranch,event,conclusion", "--limit", "20"]))
    for r in runs:      # newest first
        if r.get("headSha") == commit and r.get("event") == event and r.get("headBranch") == branch \
                and r.get("conclusion") in conclusions:
            return r
    return None


def _job_logs(gh, run_id) -> dict[str, str]:
    jobs = json.loads(gh(["run", "view", str(run_id), "--json", "jobs"])).get("jobs") or []
    return {j["name"]: gh(["run", "view", str(run_id), "--job", str(j["databaseId"]), "--log"])
            for j in jobs if j.get("name") in CI_JOBS}


def measure(pr: int, head: str, gh=_gh) -> list[str]:
    """The counts of the PR's own CI on HEAD against main's push run on the commit that CI merged into:
    every reason they give to wait for Jonathan."""
    view = json.loads(gh(["pr", "view", str(pr), "--json", "isCrossRepository,headRefOid,headRefName,baseRefName"]))
    if view.get("isCrossRepository") is not False:
        return [f"PR #{pr} does not come from the repository itself (a fork, or unsaid): its CI is not read"]
    if view.get("headRefOid") != head:
        return [f"PR #{pr}'s head ({str(view.get('headRefOid'))[:12]}) is not the commit reviewed ({head[:12]})"]
    if view.get("baseRefName") != "main":
        return [f"PR #{pr} does not merge into main ({view.get('baseRefName')})"]
    run = _ci_run(gh, event="pull_request", commit=head, branch=view.get("headRefName") or "")
    if run is None:
        return [f"no green CI run of PR #{pr} on {head[:12]} (ci.yml, pull_request): nothing to compare"]
    heads = _job_logs(gh, run["databaseId"])
    merged = {m for log in heads.values() for m in MERGED.findall(log)}
    if len(merged) != 1 or next(iter(merged))[0] != head:
        return [f"the commit PR #{pr}'s CI merged into is not read (« Merge {head[:12]} into … »): nothing to "
                "compare"]
    base = next(iter(merged))[1]
    main_run = _ci_run(gh, event="push", commit=base, branch="main", conclusions=BASE_CONCLUSIONS)
    if main_run is None:
        return [f"no run of main's push CI on {base[:12]}, the commit PR #{pr}'s CI merged into: nothing to compare"]
    bases = _job_logs(gh, main_run["databaseId"])
    out = []
    for job in CI_JOBS:
        if job not in heads or job not in bases:
            out.append(f"{job}: its log not read on {'the PR' if job not in heads else 'main'}")
            continue
        out += compare_counts(job, pytest_counts(bases[job]), pytest_counts(heads[job]))
        out += compare_mutants(job, mutant_counts(bases[job]), mutant_counts(heads[job]))
    return out


# ── Git ────────────────────────────────────────────────────────────────────────────────────────────────

def _git(repo: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {run.stderr.strip() or run.returncode}")
    return run.stdout


def _show(repo: Path, ref: str, path: str) -> str:
    run = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True)
    if run.returncode != 0:
        raise RuntimeError(f"git show {ref}:{path}: {run.stderr.decode(errors='replace').strip()}")
    return run.stdout.decode("utf-8", errors="replace")


def read_changes(repo: Path, base: str, head: str) -> list[Change]:
    """What HEAD brings over its merge base with BASE, file by file, renames found."""
    head = _git(repo, "rev-parse", "--verify", f"{head}^{{commit}}").strip()
    since = _git(repo, "merge-base", base, head).strip()
    fields = _git(repo, "diff", "--name-status", "-M", "-z", since, head).split("\0")
    out, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i]
        if status[0] in "RC":
            old, new, i = fields[i + 1], fields[i + 2], i + 3
        else:
            old = new = fields[i + 1]
            i += 2
            if status[0] == "A":
                old = None
            elif status[0] == "D":
                new = None
        out.append(Change(old, new, _show(repo, since, old) if old else None, _show(repo, head, new) if new else None))
    return out


def _say(text: str) -> str:
    # The output becomes a comment on the pull request: it never carries a review's key.
    return text.replace("<!--", "&lt;!--")


def main(argv: list[str] | None = None, gh=_gh) -> int:
    ap = argparse.ArgumentParser(prog="night_guard.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="judge what HEAD brings over BASE")
    check.add_argument("--base", default="origin/main")
    check.add_argument("--head", default="HEAD")
    check.add_argument("--repo", default=".")
    check.add_argument("--pr", type=int, default=0,
                       help="the PR whose CI is measured against main's (the night always gives it)")
    args = ap.parse_args(argv)
    try:
        changes = read_changes(Path(args.repo), args.base, args.head)
        head = _git(Path(args.repo), "rev-parse", "--verify", f"{args.head}^{{commit}}").strip()
        counted = measure(args.pr, head, gh) if args.pr else []
    except (RuntimeError, ValueError) as e:
        print(_say(f"night guard: the change cannot be read ({e}): refused, nothing merged"))
        return 2
    reasons = counted + judge(changes)
    if not args.pr:
        print("night guard: the CI's counts not measured (no --pr): the diff's reading alone")
    if reasons:
        print(_say(f"night guard: merge refused without Jonathan ({len(reasons)} reason(s), "
                   f"{len(changes)} file(s) read):"))
        for r in reasons:
            print(_say(f"- {r}"))
        return 1
    print(f"night guard: nothing asks for Jonathan ({len(changes)} file(s) read): the night may merge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
