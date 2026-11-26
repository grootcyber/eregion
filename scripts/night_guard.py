#!/usr/bin/env python3
"""night_guard — what the night may not merge without Jonathan (NOC1, #1251; docs/sessions.md, « La nuit »).

  night_guard.py check [--base origin/main] [--head REVIEWED] [--repo DIR]
      exit 0: nothing in the change asks for Jonathan, the night may merge it;
      exit 1: refused, each reason on a line — the pull request stays open, unmerged, with a comment
              that says why, and a line for Jonathan in the night's report;
      exit 2: the change could not be read (a ref unknown, git failing): refused as well.

The change is the pull request's diff against its base: from the merge base of BASE and HEAD to HEAD
(what the branch brings, never what main did since). HEAD is the commit the review read and the merge
is tied to (`gh pr merge --match-head-commit`), never the head read later. The night runs it before
each merge; a day session may run it too.

It refuses a change that:
- removes or renames a `test_*` function, or adds a skip, a skipif, an xfail (a marker or a call);
- removes a mutant from a `scripts/mutants/*.py`, or changes its `new` without its `old`;
- touches `.github/`, `requirements/`, a `.terraform.lock.hcl`, or the dependencies, the build or the
  pytest settings of `pyproject.toml`;
- touches an invariant's oracle: `tests/unit/test_invariants*.py`, `tests/unit/fake_azure.py`,
  `tests/unit/fake_aws.py` — a question for Jonathan, as INV7 and INV8 were;
- changes or removes a named threshold or ceiling: a module-level number of
  `tests/unit/test_file_sizes.py`, `tests/unit/test_docs_budget.py` or `glorfindel/read_budget.py`
  (the read budgets), in either direction — raising a ceiling loosens it, lowering a floor or a budget
  too, and the guard does not tell a floor from a ceiling;
- touches the night's own rails: `.claude/` (the skill, the agents), `scripts/night/`, this guard and
  its tests, `scripts/review_verdict.py`.

What it does not hold: a test whose body is emptied (its name kept), an assertion weakened, a mutant's
TESTS narrowed, a mutant of the harness's own blocks (`scripts/mutation_check.py`). The review reads
those; the guard catches the gestures that a reviewer could let pass at night. A lot's mutants file is
run to be read (as the harness and scripts/mutant_anchors.py run it), in a child process, isolated
(`python -I`), with a bound. Standard library only.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Paths the night never merges: (pattern, reason). A pattern ending in "/" is a directory.
PROTECTED = (
    (".github/workflows/", "touches a workflow (.github/workflows/): the sessions' App cannot push it"),
    (".github/", "touches .github/ (CODEOWNERS, the repository's settings)"),
    ("requirements/", "touches the locked dependencies (requirements/)"),
    ("*.terraform.lock.hcl", "touches a Terraform providers' lock (.terraform.lock.hcl)"),
    ("tests/unit/test_invariants*.py", "touches an invariant's oracle (the properties and their checks): "
                                       "a question for Jonathan, as INV7 and INV8"),
    ("tests/unit/fake_azure.py", "touches the fake Azure the invariants judge on: a question for Jonathan, "
                                 "as INV7 and INV8"),
    ("tests/unit/fake_aws.py", "touches the fake AWS the invariants judge on: a question for Jonathan"),
    (".claude/", "touches the night's own rails (.claude/: the skill, the agents, the settings)"),
    ("scripts/night/", "touches the night's own rails (scripts/night/: its unit, its settings)"),
    ("scripts/night_guard.py", "touches the night's own guard"),
    ("tests/unit/test_night_guard.py", "touches the night's own guard's tests"),
    ("scripts/review_verdict.py", "touches the review's verdict, which the merge reads"),
)
# pyproject.toml: the tables whose change the night never merges.
PYPROJECT = (("project", "dependencies"), ("project", "optional-dependencies"), ("build-system",),
             ("tool", "pytest"))
# The named thresholds: each module-level number of these files.
THRESHOLDS = ("tests/unit/test_file_sizes.py", "tests/unit/test_docs_budget.py", "glorfindel/read_budget.py")
MUTANTS_GLOB = "scripts/mutants/*.py"
# A skip, a skipif, an xfail: a marker (pytest.mark.…, mark.…), a call (pytest.skip(…)), unittest's.
SKIP = re.compile(r"\b(?:pytest\.|mark\.)(?:skip|skipif|xfail)\b|\bpytest\.importorskip\b"
                  r"|\bunittest\.(?:skip|skipIf|skipUnless|expectedFailure)\b|@(?:skip|skipIf|skipUnless|xfail)\b")
RENAMED = "<RENAME>"
# Run in a child process, isolated: a lot's file, its MUTANTS and CONTROL as JSON.
_LOADER = (
    "import json, runpy, sys\n"
    "ns = runpy.run_path(sys.argv[1], init_globals={'RENAME': " + repr(RENAMED) + "})\n"
    "out = []\n"
    "for m in list(ns.get('MUTANTS', [])) + list(ns.get('CONTROL', [])):\n"
    "    out.append([str(m[0]), str(m[2]), m[3] if isinstance(m[3], str) else repr(m[3]), str(m[4])])\n"
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
                out.append(f"pyproject.toml: changes [{'.'.join(keys)}] (the dependencies, the build or pytest's "
                           "settings)")
    return out


def _is_test_file(path: str | None) -> bool:
    return bool(path) and path.endswith(".py") and (
        path.startswith("tests/") or PurePosixPath(path).name.startswith("test_"))


def named_tests(text: str) -> Counter:
    """Each `test_*` function of a module, qualified by its classes (`TestX.test_y`)."""
    names: Counter = Counter()

    def walk(body, prefix):
        for node in body:
            if isinstance(node, ast.ClassDef):
                walk(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                names[f"{prefix}{node.name}"] += 1

    walk(ast.parse(text).body, "")
    return names


def removed_tests(changes: list[Change]) -> list[str]:
    """A test function gone (removed, or renamed: its old name gone), across every file the change touches
    (a test moved to another file keeps its name); a skip or an xfail more than before, file by file."""
    out, before, after, where = [], Counter(), Counter(), {}
    for c in changes:
        for side, path, text, into in (("before", c.old_path, c.old_text, before),
                                       ("after", c.new_path, c.new_text, after)):
            if not _is_test_file(path):
                continue
            try:
                names = named_tests(text or "")
                into.update(names)
                if into is before:
                    where.update({n: path for n in names if n not in where})
            except SyntaxError as e:
                out.append(f"{path}: unreadable {side} the change ({e.msg}, line {e.lineno}): its tests cannot be "
                           "counted")
        olds = len(SKIP.findall(c.old_text or "")) if _is_test_file(c.old_path) else 0
        news = len(SKIP.findall(c.new_text or "")) if _is_test_file(c.new_path) else 0
        if news > olds:
            out.append(f"{c.new_path}: adds {news - olds} skip, skipif or xfail")
    for name in sorted(before - after):
        out.append(f"{where[name]}: removes or renames the test {name}")
    return out


def load_mutants(text: str, name: str, timeout: float = 60.0) -> dict[str, tuple[str, str, str]]:
    """A lot's file's mutants, {id: (file, old, new)}, read by running it apart. ValueError when it cannot
    be read."""
    with tempfile.TemporaryDirectory(prefix="night-guard-") as tmp:
        path = Path(tmp) / PurePosixPath(name).name
        path.write_text(text, encoding="utf-8")
        try:
            run = subprocess.run([sys.executable, "-I", "-c", _LOADER, str(path)], cwd=tmp, capture_output=True,
                                 text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ValueError(f"not read within {timeout:.0f} s") from None
        if run.returncode != 0:
            last = (run.stderr.strip().splitlines() or ["?"])[-1]
            raise ValueError(last)
        try:
            return {m[0]: (m[1], m[2], m[3]) for m in json.loads(run.stdout)}
        except (ValueError, IndexError, TypeError) as e:
            raise ValueError(f"what it defines is not read ({e})") from None


def mutants(changes: list[Change], load=load_mutants) -> list[str]:
    """A mutant gone (from every lot's file the change touches: one moved to another file stays), or its
    `new` changed while its `old` stays: the bug it re-introduces is no longer the one it was measured on."""
    out, before, after = [], {}, {}
    for c in changes:
        for side, path, text, into in (("before", c.old_path, c.old_text, before),
                                       ("after", c.new_path, c.new_text, after)):
            if not path or not fnmatch.fnmatchcase(path, MUTANTS_GLOB):
                continue
            try:
                into.update(load(text or "", path))
            except ValueError as e:
                out.append(f"{path}: its mutants unreadable {side} the change ({e})")
    for mid in sorted(set(before) - set(after)):
        out.append(f"removes the mutant {mid}")
    for mid in sorted(set(before) & set(after)):
        (_f0, old0, new0), (_f1, old1, new1) = before[mid], after[mid]
        if new0 != new1 and old0 == old1:
            out.append(f"changes the mutant {mid}'s new text without its old one")
    return out


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
    return (protected_paths(changes) + pyproject(changes) + removed_tests(changes) + mutants(changes, load)
            + thresholds(changes))


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="night_guard.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check", help="judge what HEAD brings over BASE")
    check.add_argument("--base", default="origin/main")
    check.add_argument("--head", default="HEAD")
    check.add_argument("--repo", default=".")
    args = ap.parse_args(argv)
    try:
        changes = read_changes(Path(args.repo), args.base, args.head)
    except RuntimeError as e:
        print(_say(f"night guard: the change cannot be read ({e}): refused, nothing merged"))
        return 2
    reasons = judge(changes)
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
