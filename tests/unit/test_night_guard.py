"""NOC1 (#1251): the night's guard — what a pull request the night fixed may not merge without Jonathan
(scripts/night_guard.py; docs/sessions.md, « La nuit »). Pure judgements on changes, then the same on a
throwaway git repository (no network, no GitHub)."""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("night_guard", ROOT / "scripts" / "night_guard.py")
ng = importlib.util.module_from_spec(_spec)
sys.modules["night_guard"] = ng
_spec.loader.exec_module(ng)
Change = ng.Change

TESTS_A = '''
def test_one():
    assert True


class TestBox:
    def test_two(self):
        assert True
'''

LOT = '''"""A lot's file."""
T = "glorfindel/x.py"
_T = "tests/unit/test_x.py"


def _pair(mid, new):
    return (mid, "a bug", T, "return 1\\n", new)


MUTANTS = [
    ("M1", "the first", T, "a = 1\\n", "a = 2\\n"),
    ("M2", "the second", T, "b = 1\\n", "b = 2\\n"),
    _pair("M3", "return 0\\n"),
]
MUTANTS += [("M4", "a rename", "docs/x.md", RENAME, "docs/y.md")]
TESTS = {f"M{n}": _T for n in range(1, 5)}
'''

SIZES = '''CAPS = {
    "glorfindel/cli.py": 2566,
    "glorfindel/agent.py": 3562,
}
SLACK = 100
MODULE_MAX = 300
PACKAGES = ("glorfindel/watch",)
'''

BUDGET = '''LOG_ANALYTICS = ReadBudget("Log Analytics", "GLORFINDEL_LA_BUDGET_PER_MIN", 120)
ARM = ReadBudget("ARM", "GLORFINDEL_ARM_BUDGET_PER_MIN", 60, floor=MINIMUM)
MINIMUM = 7
WINDOW_S = 60.0
'''

PYPROJECT = '''[project]
name = "eregion"
version = "0.6.11"
dependencies = ["click>=8"]

[project.optional-dependencies]
dev = ["pytest"]

[tool.pytest.ini_options]
addopts = "-q"

[tool.ruff]
line-length = 120
'''


def modified(path: str, old: str, new: str) -> Change:
    return Change(path, path, old, new)


def no_load(text, name):
    raise AssertionError("no lot's file in this change")


def judged(*changes: Change) -> list[str]:
    return ng.judge(list(changes), load=no_load)


# ── What asks nothing ────────────────────────────────────────────────────────────────────────────────

def test_a_change_that_asks_nothing_may_merge():
    """Product code changed, a test added, a test moved to another file, a ceiling's file untouched."""
    moved = '''
def test_two():
    assert True
'''
    assert judged(
        modified("glorfindel/x.py", "a = 1\n", "a = 2\n"),
        modified("tests/unit/test_a.py", TESTS_A, TESTS_A + "\n\ndef test_three():\n    assert True\n"),
        modified("tests/unit/test_b.py", "def test_two():\n    pass\n", ""),
        Change(None, "tests/unit/test_c.py", None, moved),
        modified("tests/unit/test_invariant_regressions.py", "", "def test_a_sequence_frozen():\n    pass\n"),
        modified("docs/sessions.md", "a\n", "b\n"),
    ) == []


# ── Tests: removed, renamed, out of the collection ───────────────────────────────────────────────────

def test_a_test_removed_or_renamed_is_refused_and_named_with_its_file():
    renamed = TESTS_A.replace("def test_one", "def test_first")
    said = judged(modified("tests/unit/test_a.py", TESTS_A, renamed))
    assert said == ["tests/unit/test_a.py: removes or renames the test test_one"]
    gone = TESTS_A.replace("    def test_two(self):\n        assert True\n", "    pass\n")
    assert judged(modified("tests/unit/test_a.py", TESTS_A, gone)) == [
        "tests/unit/test_a.py: removes or renames the test TestBox.test_two"]


def test_a_test_file_deleted_takes_its_tests_with_it():
    said = judged(Change("tests/unit/test_a.py", None, TESTS_A, None))
    assert said == ["tests/unit/test_a.py: removes or renames the test TestBox.test_two",
                    "tests/unit/test_a.py: removes or renames the test test_one"]


def test_a_test_file_renamed_keeps_its_tests():
    assert judged(Change("tests/unit/test_a.py", "tests/unit/test_b.py", TESTS_A, TESTS_A)) == []
    assert judged(Change("tests/unit/test_a.py", "tests/unit/b_test.py", TESTS_A, TESTS_A)) == []


def test_a_test_whose_file_or_class_leaves_the_collection_counts_as_removed():
    """pytest collects `test_*.py` and `*_test.py`, classes `Test*`: a file renamed `helpers_a.py`, or a
    class renamed `Box`, takes its tests out of the run, though their names stay."""
    said = judged(Change("tests/unit/test_a.py", "tests/unit/helpers_a.py", TESTS_A, TESTS_A))
    assert said == ["tests/unit/test_a.py: removes or renames the test TestBox.test_two",
                    "tests/unit/test_a.py: removes or renames the test test_one"]
    said = judged(modified("tests/unit/test_a.py", TESTS_A, TESTS_A.replace("class TestBox", "class Box")))
    assert said == ["tests/unit/test_a.py: removes or renames the test TestBox.test_two"]


def test_a_test_in_a_file_that_is_not_collected_is_none_to_remove():
    helper = "def test_like_helper():\n    pass\n"
    assert judged(modified("tests/unit/js_engine.py", helper, "")) == []


# ── Tests: taken out of the run ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("added, kind", [
    ("@pytest.mark.skip(reason='later')\n", "skip"),
    ("@pytest.mark.skipif(sys.platform == 'linux', reason='x')\n", "skipif"),
    ("@pytest.mark.xfail(strict=False)\n", "xfail"),
    ("@unittest.skip('later')\n", "skip"),
    ("@unittest.expectedFailure\n", "xfail"),
])
def test_a_skip_or_an_xfail_added_is_refused_and_tied_to_its_test(added, kind):
    new = TESTS_A.replace("def test_one", added + "def test_one")
    assert judged(modified("tests/unit/test_a.py", TESTS_A, new)) == [f"tests/unit/test_a.py: adds {kind} to test_one"]


@pytest.mark.parametrize("imports, line, kind", [
    ("import pytest as pt\n", "    pt.skip('x')\n", "skip"),
    ("from pytest import skip\n", "    skip('x')\n", "skip"),
    ("from pytest import skip as later\n", "    later('x')\n", "skip"),
    ("from pytest import mark\n", "    mark.xfail(run=False)\n", "xfail"),
    ("import pytest\nm = pytest.mark\nx = m.xfail\n", "    x()\n", "xfail"),
    ("import pytest\n", "    pytest.importorskip('nothing')\n", "importorskip"),
    ("from _pytest.outcomes import skip\n", "    skip('x')\n", "skip"),
    ("from pytest import *\n", "    skip('x')\n", "skip"),
    ("import pytest\n", "    getattr(pytest, 'sk' + 'ip')('x')\n", "getattr"),
    ("import pytest\n", "    getattr(pytest.mark, 'xfail')\n", "xfail"),
])
def test_a_skip_through_an_alias_or_getattr_is_refused(imports, line, kind):
    old = imports + "\n\ndef test_one():\n    assert True\n"
    new = imports + "\n\ndef test_one():\n" + line + "    assert True\n"
    assert judged(modified("tests/unit/test_a.py", old, new)) == [f"tests/unit/test_a.py: adds {kind} to test_one"]


def test_a_skip_test_of_unittest_is_refused():
    old = "import unittest\n\n\nclass TestBox(unittest.TestCase):\n    def test_two(self):\n        assert True\n"
    new = old.replace("        assert True\n", "        self.skipTest('later')\n")
    assert judged(modified("tests/unit/test_a.py", old, new)) == [
        "tests/unit/test_a.py: adds skipTest to TestBox.test_two"]


@pytest.mark.parametrize("added, kind", [
    ("__test__ = False\n", "__test__ = …"),
    ("pytestmark = getattr(pytest.mark, 'sk' + 'ip')\n", "pytestmark = …"),
    ("collect_ignore_glob = ['*']\n", "collect_ignore_glob = …"),
    ("collect_ignore.append('test_a.py')\n", "collect_ignore.append(…)"),
    ("del test_one\n", "del test_one"),
])
def test_what_takes_a_module_out_of_the_collection_is_refused(added, kind):
    said = judged(modified("tests/unit/test_a.py", "import pytest\n" + TESTS_A, "import pytest\n" + TESTS_A + added))
    assert any(r.startswith(f"tests/unit/test_a.py: adds {kind}") and r.endswith("to <module>") for r in said), said


def test_a_pytestmark_changed_is_refused_one_kept_is_not():
    old = "import pytest\npytestmark = pytest.mark.slow\n" + TESTS_A
    assert judged(modified("tests/unit/test_a.py", old, old + "\n\ndef test_three():\n    pass\n")) == []
    said = judged(modified("tests/unit/test_a.py", old, old.replace("mark.slow", "mark.skip")))
    assert said and all(s.endswith("to <module>") for s in said) and any("adds skip" in s for s in said), said


def test_an_emptied_parametrize_is_refused():
    old = "import pytest\n\n\n@pytest.mark.parametrize('x', [1, 2])\ndef test_x(x):\n    assert x\n"
    said = judged(modified("tests/unit/test_a.py", old, old.replace("[1, 2]", "[]")))
    assert said == ["tests/unit/test_a.py: adds an empty parametrize to test_x"]


def test_a_collection_hook_added_or_changed_is_refused_wherever_it_is():
    hook = "def pytest_collection_modifyitems(config, items):\n    items[:] = []\n"
    said = judged(modified("tests/unit/helpers.py", "", hook))
    assert len(said) == 1 and said[0].startswith(
        "tests/unit/helpers.py: adds the collection hook pytest_collection_modifyitems ("), said


def test_a_skip_in_the_unit_tests_conftest_is_refused_twice():
    """tests/unit/conftest.py: protected by its name, and the skip it adds said too."""
    old = "import pytest\n\n\n@pytest.fixture\ndef box():\n    return 1\n"
    new = old.replace("    return 1\n", "    pytest.skip('later')\n")
    said = judged(modified("tests/unit/conftest.py", old, new))
    assert said == ["tests/unit/conftest.py: touches a conftest.py: what pytest collects, skips or deselects",
                    "tests/unit/conftest.py: adds skip to box"]


def test_a_skip_moved_from_one_test_to_another_is_one_added():
    old = TESTS_A.replace("def test_one", "@pytest.mark.skip\ndef test_one")
    moved = TESTS_A.replace("    def test_two", "    @pytest.mark.skip\n    def test_two")
    assert judged(modified("tests/unit/test_a.py", old, moved)) == [
        "tests/unit/test_a.py: adds skip to TestBox.test_two"]


def test_one_more_skip_on_another_test_beside_one_already_there_is_refused():
    old = TESTS_A.replace("def test_one", "@pytest.mark.skip\ndef test_one")
    new = old.replace("    def test_two", "    @pytest.mark.xfail\n    def test_two")
    assert judged(modified("tests/unit/test_a.py", old, new)) == ["tests/unit/test_a.py: adds xfail to TestBox.test_two"]


def test_a_skip_kept_a_file_renamed_or_a_word_skip_in_a_string_asks_nothing():
    old = TESTS_A.replace("def test_one", "@pytest.mark.skip\ndef test_one")
    assert judged(Change("tests/unit/test_a.py", "tests/unit/test_b.py", old, old)) == []
    assert judged(modified("tests/unit/test_a.py", old, old + "\n\ndef test_three():\n    pass\n")) == []
    words = TESTS_A + '\n\ndef test_flags():\n    assert "--skip-machine-baseline" and "skip_reason"\n'
    assert judged(modified("tests/unit/test_a.py", TESTS_A, words)) == []


def test_a_test_file_unreadable_is_refused():
    said = judged(modified("tests/unit/test_a.py", TESTS_A, "def test_one(:\n"))
    assert said[0].startswith("tests/unit/test_a.py: unreadable after the change")
    assert said[1:] == ["tests/unit/test_a.py: removes or renames the test TestBox.test_two",
                        "tests/unit/test_a.py: removes or renames the test test_one"]


# ── Mutants ──────────────────────────────────────────────────────────────────────────────────────────

def test_a_lot_s_file_is_read_apart_with_its_helpers_renames_and_reasons():
    got = ng.load_mutants(LOT, "scripts/mutants/X1.py")
    assert got == {"M1": ("glorfindel/x.py", "a = 1\n", "a = 2\n", ""), "M2": ("glorfindel/x.py", "b = 1\n", "b = 2\n", ""),
                   "M3": ("glorfindel/x.py", "return 1\n", "return 0\n", ""),
                   "M4": ("docs/x.md", ng.RENAMED, "docs/y.md", "")}
    marked = LOT.replace('"b = 2\\n"),', '"b = 2\\n", "EQUIVALENT: the same"),')
    assert ng.load_mutants(marked, "scripts/mutants/X1.py")["M2"][3] == "EQUIVALENT: the same"
    with pytest.raises(ValueError, match="NameError"):
        ng.load_mutants("MUTANTS = [UNKNOWN]\n", "scripts/mutants/X2.py")


@pytest.mark.parametrize("text, said", [
    ("import os\nMUTANTS = []\n", "an import, line 1"),
    ("from pathlib import Path\nMUTANTS = []\n", "an import, line 1"),
    ("MUTANTS = [open('/etc/passwd').read()]\n", "open, line 1"),
    ("MUTANTS = []\neval('1')\n", "eval, line 2"),
    ("MUTANTS = []\nexec('1')\n", "exec, line 2"),
    ("MUTANTS = []\ncompile('1', 'x', 'exec')\n", "compile, line 2"),
    ("MUTANTS = [getattr(str, 'upper')]\n", "getattr, line 1"),
    ("MUTANTS = [__file__]\n", "__file__, line 1"),
    ("MUTANTS = [().__class__]\n", ".__class__, line 1"),
    ("MUTANTS = [__builtins__]\n", "__builtins__, line 1"),
])
def test_a_lot_s_file_that_reaches_out_is_refused_before_it_runs(text, said):
    def never(*a, **k):
        raise AssertionError("ran a file the syntax tree refuses")
    with pytest.raises(ValueError, match=f"^{re.escape(said)}: refused before running$"):
        ng.load_mutants(text, "scripts/mutants/X3.py", run=never)


def test_every_lot_s_file_of_the_tree_passes_the_syntax_check():
    """Nothing the tree holds needs what the check refuses: a refusal says a file reaching out."""
    files = sorted((ROOT / "scripts" / "mutants").glob("*.py"))
    assert len(files) > 200
    for p in files:
        ng.precheck(ast.parse(p.read_text(encoding="utf-8")))


def test_the_child_runs_isolated_with_a_bare_environment_and_limits():
    seen = {}

    def run(args, **kw):
        seen.update(args=args, **kw)
        return subprocess.CompletedProcess(args, 0, stdout="[]", stderr="")
    assert ng.load_mutants("MUTANTS = []\n", "scripts/mutants/X4.py", timeout=7, run=run) == {}
    assert seen["args"][:3] == [sys.executable, "-I", "-c"] and seen["timeout"] == 7
    assert seen["env"] == {"PATH": "/usr/bin:/bin", "HOME": seen["cwd"]}
    assert callable(seen["preexec_fn"]) and "night-guard-" in seen["cwd"]


def test_a_lot_s_file_that_never_ends_is_cut_at_its_timeout():
    with pytest.raises(ValueError, match=r"^not read within 1 s$"):
        ng.load_mutants("while True:\n    pass\n", "scripts/mutants/X6.py", timeout=1)


def _lot(**mutants) -> dict:
    return {mid: (spec[2] if len(spec) > 2 else "glorfindel/x.py", spec[0], spec[1], spec[3] if len(spec) > 3 else "")
            for mid, spec in mutants.items()}


def _judge_lots(loads, *changes):
    return ng.mutants(list(changes) or [modified("scripts/mutants/X1.py", "old", "new")], load=lambda t, n: loads[t])


def test_a_mutant_removed_is_refused():
    assert _judge_lots({"old": _lot(M1=("a", "b"), M2=("c", "d")), "new": _lot(M1=("a", "b"))}) == [
        "removes the mutant M2"]


def test_a_mutant_s_new_text_changed_without_its_old_is_refused():
    assert _judge_lots({"old": _lot(M1=("a", "b")), "new": _lot(M1=("a", "B"))}) == [
        "changes the mutant M1's new text without its old one"]


def test_a_mutant_s_file_changed_is_refused():
    assert _judge_lots({"old": _lot(M1=("a", "b")), "new": _lot(M1=("a", "b", "glorfindel/y.py"))}) == [
        "changes the mutant M1's file (glorfindel/x.py -> glorfindel/y.py)"]


@pytest.mark.parametrize("reason", ["EQUIVALENT: the same code", "TIMING: test_race", "MULTI-HOST: two hosts"])
def test_a_reason_added_or_changed_on_a_mutant_is_refused(reason):
    said = _judge_lots({"old": _lot(M1=("a", "b")), "new": _lot(M1=("a", "b", "glorfindel/x.py", reason))})
    assert said == [f"gives the mutant M1 a reason ({reason[:40]}…): a known survivor is no longer counted"]
    said = _judge_lots({"old": _lot(M1=("a", "b", "glorfindel/x.py", "TIMING: x")),
                        "new": _lot(M1=("a", "b", "glorfindel/x.py", reason))})
    assert said == [f"gives the mutant M1 a reason ({reason[:40]}…): a known survivor is no longer counted"]
    said = _judge_lots({"old": {}, "new": _lot(M9=("a", "b", "glorfindel/x.py", reason))})
    assert said == [f"adds the mutant M9 with a reason ({reason[:40]}…): born uncounted"]


def test_a_reason_kept_or_taken_off_asks_nothing():
    marked = _lot(M1=("a", "b", "glorfindel/x.py", "TIMING: x"))
    assert _judge_lots({"old": marked, "new": marked}) == []
    assert _judge_lots({"old": marked, "new": _lot(M1=("a", "b"))}) == []


def test_a_mutant_moved_with_its_code_or_to_another_lot_s_file_asks_nothing():
    loads = {"old": _lot(M1=("a", "b")), "moved": _lot(M1=("a2", "b2")), "": {}}
    assert _judge_lots(loads, modified("scripts/mutants/X1.py", "old", "moved")) == []
    assert _judge_lots(loads, Change("scripts/mutants/X1.py", None, "old", None),
                       Change(None, "scripts/mutants/X2.py", None, "moved")) == []


def test_a_lot_s_file_unreadable_is_refused():
    def load(text, name):
        if text == "new":
            raise ValueError("SyntaxError: invalid syntax")
        return _lot(M1=("a", "b"))
    said = ng.mutants([modified("scripts/mutants/X1.py", "old", "new")], load=load)
    assert said[0] == "scripts/mutants/X1.py: its mutants unreadable after the change (SyntaxError: invalid syntax)"
    assert "removes the mutant M1" in said


def test_a_mutant_removed_or_marked_through_the_real_loader():
    fewer = LOT.replace('    ("M2", "the second", T, "b = 1\\n", "b = 2\\n"),\n', "")
    assert ng.judge([modified("scripts/mutants/X1.py", LOT, fewer)]) == ["removes the mutant M2"]
    marked = LOT.replace('"b = 2\\n"),', '"b = 2\\n", "EQUIVALENT: the same"),')
    assert ng.judge([modified("scripts/mutants/X1.py", LOT, marked)]) == [
        "gives the mutant M2 a reason (EQUIVALENT: the same…): a known survivor is no longer counted"]


# ── Paths, pyproject ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path, said", [
    (".github/workflows/mutants.yml", "touches a workflow"),
    (".github/CODEOWNERS", "touches .github/"),
    ("requirements/dev.txt", "locked dependencies"),
    ("infra/terraform/.terraform.lock.hcl", "providers' lock"),
    ("tests/unit/test_invariants.py", "invariant's oracle"),
    ("tests/unit/test_invariants_aws.py", "invariant's oracle"),
    ("tests/unit/fake_azure.py", "fake Azure"),
    ("tests/unit/fake_aws.py", "fake AWS"),
    ("tests/unit/invariant_hold.py", "invariants' oracle"),
    ("tests/unit/french_ceiling.json", "French output's ceilings"),
    ("scripts/mutation_check.py", "mutation's harness"),
    ("scripts/mutant_anchors.py", "anchors check"),
    ("scripts/mutants/narrowed.json", "narrowed tests"),
    ("conftest.py", "a conftest.py"),
    ("tests/unit/conftest.py", "a conftest.py"),
    ("infra/orodruin/tests/conftest.py", "a conftest.py"),
    ("pytest.ini", "pytest.ini wins"),
    (".pytest.ini", ".pytest.ini"),
    ("tox.ini", "tox.ini"),
    ("setup.cfg", "setup.cfg"),
    (".claude/skills/elrond/SKILL.md", "night's own rails"),
    ("scripts/night/eregion-night.service", "night's own rails"),
    ("scripts/night_guard.py", "night's own guard"),
    ("tests/unit/test_night_guard.py", "night's own guard"),
    ("scripts/review_verdict.py", "review's verdict"),
])
def test_a_protected_path_is_refused_added_changed_or_deleted(path, said):
    for change in (modified(path, "a\n", "b\n"), Change(None, path, None, "b\n"), Change(path, None, "a\n", None)):
        out = ng.protected_paths([change])
        assert len(out) == 1 and out[0].startswith(f"{path}: ") and said in out[0], out


def test_a_file_moved_out_of_a_protected_place_is_refused():
    out = ng.protected_paths([Change("requirements/dev.txt", "docs/dev.txt", "a", "a")])
    assert out == ["requirements/dev.txt: touches the locked dependencies (requirements/)"]


def test_the_regressions_and_a_workflow_s_namesake_elsewhere_are_not_protected():
    assert ng.protected_paths([modified("tests/unit/test_invariant_regressions.py", "a", "b"),
                               modified("docs/github/workflows.md", "a", "b"),
                               modified("scripts/mutants/NOC1.py", "a", "b")]) == []


def test_pyproject_s_dependencies_build_and_pytest_settings_are_refused_its_version_is_not():
    bump = PYPROJECT.replace('version = "0.6.11"', 'version = "0.6.12"').replace("line-length = 120", "line-length = 100")
    assert judged(modified("pyproject.toml", PYPROJECT, bump)) == []
    for old, new, table in (('dependencies = ["click>=8"]', 'dependencies = ["click>=8", "x"]', "project.dependencies"),
                            ('dev = ["pytest"]', 'dev = ["pytest<9"]', "project.optional-dependencies"),
                            ('addopts = "-q"', 'addopts = "-q --deselect tests/unit/test_a.py"', "tool.pytest")):
        said = judged(modified("pyproject.toml", PYPROJECT, PYPROJECT.replace(old, new)))
        assert said == [f"pyproject.toml: changes [{table}] (the dependencies, the build or pytest's settings)"], said
    said = judged(modified("pyproject.toml", PYPROJECT, PYPROJECT + "[build-system]\nrequires = ['x']\n"))
    assert said and "[build-system]" in said[0]
    assert judged(modified("pyproject.toml", PYPROJECT, "[project\n"))[0].startswith("pyproject.toml: unreadable")


# ── Named thresholds ─────────────────────────────────────────────────────────────────────────────────

def test_a_ceiling_raised_or_lowered_is_refused_in_either_direction():
    up = SIZES.replace("2566", "2600")
    assert judged(modified("tests/unit/test_file_sizes.py", SIZES, up)) == [
        "tests/unit/test_file_sizes.py: raises the threshold CAPS['glorfindel/cli.py'] (2566 -> 2600)"]
    down = SIZES.replace("MODULE_MAX = 300", "MODULE_MAX = 250")
    assert judged(modified("tests/unit/test_file_sizes.py", SIZES, down)) == [
        "tests/unit/test_file_sizes.py: lowers the threshold MODULE_MAX (300 -> 250)"]


def test_a_threshold_removed_is_refused_one_added_or_a_word_changed_is_not():
    gone = SIZES.replace('    "glorfindel/agent.py": 3562,\n', "")
    assert judged(modified("tests/unit/test_file_sizes.py", SIZES, gone)) == [
        "tests/unit/test_file_sizes.py: removes the threshold CAPS['glorfindel/agent.py'] (3562)"]
    more = SIZES.replace('    "glorfindel/agent.py": 3562,\n', '    "glorfindel/agent.py": 3562,\n    "x.py": 10,\n')
    words = more.replace('"glorfindel/watch"', '"glorfindel/watch", "glorfindel/response"')
    assert judged(modified("tests/unit/test_file_sizes.py", SIZES, words)) == []


def test_the_docs_budget_and_the_read_budgets_are_named_thresholds():
    assert judged(modified("tests/unit/test_docs_budget.py", "BUDGET_BYTES = 25 * 1024\n",
                           "BUDGET_BYTES = 26 * 1024\n")) == [
        "tests/unit/test_docs_budget.py: raises the threshold BUDGET_BYTES (25600 -> 26624)"]
    said = judged(modified("glorfindel/read_budget.py", BUDGET, BUDGET.replace(", 120)", ", 240)")
                           .replace("MINIMUM = 7", "MINIMUM = 5")))
    assert said == ["glorfindel/read_budget.py: raises the threshold LOG_ANALYTICS(2) (120 -> 240)",
                    "glorfindel/read_budget.py: lowers the threshold MINIMUM (7 -> 5)"]
    said = judged(Change("glorfindel/read_budget.py", None, BUDGET, None))
    assert said == ["glorfindel/read_budget.py: removed or renamed, and its named thresholds with it"]


def test_the_named_files_still_hold_numbers_and_the_protected_oracles_exist():
    """The lists never go stale silently: each file the guard names is in the tree, and holds numbers."""
    for rel in ng.THRESHOLDS:
        assert ng.named_numbers((ROOT / rel).read_text(encoding="utf-8")), rel
    for rel in ("tests/unit/fake_azure.py", "tests/unit/fake_aws.py", "tests/unit/test_invariants.py",
                "tests/unit/invariant_hold.py", "tests/unit/french_ceiling.json", "scripts/mutation_check.py",
                "scripts/mutant_anchors.py", "tests/unit/conftest.py",
                "scripts/review_verdict.py", ".github/workflows/mutants.yml"):
        assert (ROOT / rel).exists(), rel


# ── On a git repository ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def repo(tmp_path, monkeypatch):
    """main with a test file; a branch from it."""
    for k in list(os.environ):
        if k.startswith("GIT_"):
            monkeypatch.delenv(k)
    home = tmp_path / "home"
    home.mkdir()
    for k, v in {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"), "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t",
                 "GIT_COMMITTER_EMAIL": "t@example.org"}.items():
        monkeypatch.setenv(k, v)
    work = tmp_path / "work"
    git(tmp_path, "init", "-q", "-b", "main", str(work))
    (work / "tests" / "unit").mkdir(parents=True)
    (work / "tests" / "unit" / "test_a.py").write_text(TESTS_A, encoding="utf-8")
    (work / "app.py").write_text("a = 1\n", encoding="utf-8")
    git(work, "add", ".")
    git(work, "commit", "-qm", "init")
    git(work, "switch", "-qc", "lot/x")
    return work


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def commit(work, rel, text, msg="change"):
    path = work / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is None:
        git(work, "rm", "-q", rel)
    else:
        path.write_text(text, encoding="utf-8")
        git(work, "add", rel)
    git(work, "commit", "-qm", msg)
    return git(work, "rev-parse", "HEAD").strip()


def test_a_branch_that_asks_nothing_exits_0(repo, capsys):
    head = commit(repo, "app.py", "a = 2\n")
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head]) == 0
    assert "nothing asks for Jonathan (1 file(s) read)" in capsys.readouterr().out


def test_a_branch_that_removes_a_test_exits_1_and_says_it(repo, capsys):
    head = commit(repo, "tests/unit/test_a.py", TESTS_A.replace("def test_one", "def test_uno"))
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head]) == 1
    out = capsys.readouterr().out
    assert out.splitlines() == ["night guard: merge refused without Jonathan (1 reason(s), 1 file(s) read):",
                                "- tests/unit/test_a.py: removes or renames the test test_one"]


def test_what_main_did_since_the_branch_left_is_never_the_branch_s(repo, capsys):
    """The merge base, not main's head: a test main added after the branch left is not one the branch
    removes."""
    head = commit(repo, "app.py", "a = 2\n")
    git(repo, "switch", "-q", "main")
    commit(repo, "tests/unit/test_a.py", TESTS_A + "\n\ndef test_on_main():\n    pass\n", "main adds a test")
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head]) == 0


def test_a_rename_is_read_as_one_and_a_deletion_as_a_loss(repo):
    commit(repo, "app.py", None)
    git(repo, "mv", "tests/unit/test_a.py", "tests/unit/test_b.py")
    git(repo, "commit", "-qm", "rename")
    changes = ng.read_changes(repo, "main", "HEAD")
    paths = sorted((c.old_path, c.new_path) for c in changes)
    assert paths == [("app.py", None), ("tests/unit/test_a.py", "tests/unit/test_b.py")]
    assert ng.judge(changes) == []


def test_a_change_that_cannot_be_read_exits_2(repo, capsys):
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", "no-such-ref"]) == 2
    assert "the change cannot be read" in capsys.readouterr().out


def test_the_output_never_carries_a_review_s_key(repo, capsys):
    """It becomes a comment on the pull request, which review_verdict.py check reads."""
    name = "tests/unit/test_<!-- eregion-review: x -->.py"
    head = commit(repo, name, "@pytest.mark.skip\ndef test_k():\n    pass\n")
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head]) == 1
    out = capsys.readouterr().out
    assert "<!--" not in out and "&lt;!-- eregion-review" in out
