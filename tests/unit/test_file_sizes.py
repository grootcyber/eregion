"""WCH1 (#1019): no file too big, no giant function — to test the most in unit tests (the maintainer's
decision, 21/11).

Two guards. The product's big files (`CAPS`) each hold a ceiling, set at their size when WCH1 landed: a
file over its ceiling fails here, and so does a file that slimmed well below it (more than `SLACK` lines):
its ceiling then comes down to its size, in the same change — the ratchet, a ceiling only ever goes
down. A change that must add to one of these files takes as many lines out of it first (into a module of
their own, as WCH1 did with the watch); raising a ceiling is no fix. And the package born of the split,
glorfindel/watch/: no module beyond MODULE_MAX lines, no function nor method beyond FUNCTION_MAX — a part
a test reaches alone stays one it can read whole.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Lines: each file's size after WCH1 — lowered as the file slims, never raised.
CAPS = {
    "glorfindel/cli.py": 2566,
    "glorfindel/agent.py": 3753,
    "eregion_console/api.py": 3853,
    "glorfindel/bot.py": 1904,
}
SLACK = 100            # a file this many lines under its ceiling: the ceiling comes down to its size
PACKAGES = ("glorfindel/watch",)
MODULE_MAX = 300
FUNCTION_MAX = 50


def lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def over_ceiling(root: Path, caps: dict[str, int]) -> list[str]:
    """Each file of `caps` over its ceiling, said with what to do."""
    return [f"{rel}: {n} lines, over its ceiling of {cap} — take {n - cap} line(s) out of it (a module of "
            "their own); a ceiling is never raised"
            for rel, cap in caps.items() if (n := lines(root / rel)) > cap]


def ceiling_to_lower(root: Path, caps: dict[str, int], slack: int = SLACK) -> list[str]:
    """Each file of `caps` more than `slack` lines under its ceiling: lower the ceiling (the ratchet)."""
    return [f"{rel}: {n} lines, {cap - n} under its ceiling of {cap} — lower it to {n} in CAPS "
            "(tests/unit/test_file_sizes.py): what slimmed stays slim"
            for rel, cap in caps.items() if cap - (n := lines(root / rel)) > slack]


def giants(root: Path, packages, module_max: int = MODULE_MAX, function_max: int = FUNCTION_MAX) -> list[str]:
    """Each module of `packages` beyond `module_max` lines, and each function — a method, a nested one
    too — beyond `function_max`, from its `def` to its last line."""
    out = []
    for pkg in packages:
        for path in sorted((root / pkg).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            if (n := lines(path)) > module_max:
                out.append(f"{rel}: {n} lines, over {module_max} — split it by concern")
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    size = node.end_lineno - node.lineno + 1
                    if size > function_max:
                        out.append(f"{rel}:{node.lineno}: {node.name}, {size} lines, over {function_max}")
    return out


def test_no_big_file_grows_past_its_ceiling():
    assert not over_ceiling(ROOT, CAPS)


def test_a_ceiling_comes_down_with_its_file():
    assert not ceiling_to_lower(ROOT, CAPS)


def test_no_module_nor_function_of_the_watch_is_a_giant():
    assert not giants(ROOT, PACKAGES)
    assert len(list((ROOT / "glorfindel/watch").glob("*.py"))) >= 8      # the package is there, read


# ── the guards themselves ─────────────────────────────────────────────────────────────────────

def _file(tmp_path, n: int) -> dict[str, int]:
    (tmp_path / "big.py").write_text("x = 1\n" * n)
    return {"big.py": 10}


def test_a_file_one_line_over_its_ceiling_fails(tmp_path):
    assert over_ceiling(tmp_path, _file(tmp_path, 10)) == []
    [said] = over_ceiling(tmp_path, _file(tmp_path, 11))
    assert said.startswith("big.py: 11 lines, over its ceiling of 10 — take 1 line(s) out of it")


def test_a_file_that_slimmed_past_the_slack_asks_for_its_ceiling_lowered(tmp_path):
    caps = _file(tmp_path, 5)
    assert ceiling_to_lower(tmp_path, caps, slack=5) == []                 # within the slack: as it is
    [said] = ceiling_to_lower(tmp_path, caps, slack=4)
    assert said.startswith("big.py: 5 lines, 5 under its ceiling of 10 — lower it to 5 in CAPS")
    assert ceiling_to_lower(tmp_path, _file(tmp_path, 12), slack=0) == []  # over: the other guard's


def test_a_method_and_a_nested_function_are_held_too(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    body = "        x = 1\n" * 4
    (pkg / "m.py").write_text("class A:\n    def method(self):\n" + body
                              + "def outer():\n    def inner():\n" + body + "    return inner\n")
    said = giants(tmp_path, ("pkg",), module_max=100, function_max=4)
    assert sorted(s.split(": ")[1].split(",")[0] for s in said) == ["inner", "method", "outer"]
    assert giants(tmp_path, ("pkg",), module_max=100, function_max=7) == []
    assert giants(tmp_path, ("pkg",), module_max=5, function_max=100) == ["pkg/m.py: 13 lines, over 5 — split it by concern"]


def test_check_paragraphs_finds_code_by_whole_lines_and_prose_by_parts():
    """The review of WCH1: in `--code` mode a line moved is found only as a whole line of the new
    code, never inside a longer one (`x = 1` is not found in `x = 10`); prose, rewrapped, is still
    found as a part of the corpus."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_paragraphs", ROOT / "scripts" / "check_paragraphs.py")
    cp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cp)

    def corpus(text: str, code: bool) -> str:
        return "\n".join(cp._norm(line, code) for line in text.split("\n"))

    old = "def f():\n    total = 1\n"
    assert [lost for _, lost in cp.missing(old, corpus("def f():\n    total = 10\n", True), True)] == [["total = 1"]]
    assert cp.missing(old, corpus("def f():\n    total = 1\n", True), True) == []
    assert cp.missing("the watch reads its rules", corpus("so the watch reads its rules again", False)) == []
