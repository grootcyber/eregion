"""NOC1 (#1251): the night's guard — what a pull request the night fixed may not merge without Jonathan
(scripts/night_guard.py; docs/sessions.md, « La nuit »). Pure judgements on changes, then the same on a
throwaway git repository (no network, no GitHub)."""
from __future__ import annotations

import ast
import importlib.util
import json
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
        modified("tests/unit/test_investigate.py", "", "def test_a_case_added():\n    pass\n"),
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
    assert got == {"M1": ("glorfindel/x.py", "a = 1\n", "a = 2\n", "", "MUTANTS"),
                   "M2": ("glorfindel/x.py", "b = 1\n", "b = 2\n", "", "MUTANTS"),
                   "M3": ("glorfindel/x.py", "return 1\n", "return 0\n", "", "MUTANTS"),
                   "M4": ("docs/x.md", ng.RENAMED, "docs/y.md", "", "MUTANTS")}
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


@pytest.mark.parametrize("text, said", [
    ("MUTANTS = [(x for x in [1]).gi_frame]\n", ".gi_frame, line 1"),
    ("MUTANTS = [sorted([2, 1])]\n", "a call to sorted, line 1"),
    ("MUTANTS = [str.upper('a')]\n", ".upper, line 1"),
    ("def f():\n    return 1\n\n\nMUTANTS = [f()()]\n", "a call to f(), line 5"),
    ("MUTANTS = [lambda: 1]\n", "Lambda, line 1"),
    ("class X:\n    pass\n", "ClassDef, line 1"),
    ("@list\ndef f():\n    pass\n", "a decorator, line 2"),
    ("MUTANTS = [1 if RENAME else 2]\n", "IfExp, line 1"),
    ("def f():\n    return 1\n\n\nf = print\nMUTANTS = [f('x')]\n", "f rebound, line 5"),
    ("def g(range):\n    return range('x')\n", "range rebound, line 1"),
    ("MUTANTS = [range('x') for range in [print]]\n", "range rebound, line 1"),
    ("list = print\nMUTANTS = [list('x')]\n", "list rebound, line 1"),
    ("def list():\n    pass\n", "list redefined, line 1"),
])
def test_what_the_allowlist_does_not_name_is_refused_before_it_runs(text, said):
    def never(*a, **k):
        raise AssertionError("ran a file the allowlist refuses")
    with pytest.raises(ValueError, match=f"^{re.escape(said)}: refused before running$"):
        ng.load_mutants(text, "scripts/mutants/X3.py", run=never)


def test_rename_is_the_harness_s_own_object_never_a_string():
    """One form in the child and another in the harness would let a file show each its own MUTANTS."""
    got = ng.load_mutants('MUTANTS = [("M1", "b", "f", RENAME, "g")]\n', "scripts/mutants/X7.py")
    assert got == {"M1": ("f", ng.RENAMED, "g", "", "MUTANTS")}
    with pytest.raises(ValueError, match="AttributeError"):
        ng.load_mutants('MUTANTS = [("M1", "b", "f", RENAME.replace("a", "b"), "g")]\n', "scripts/mutants/X7.py")


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
        ng.load_mutants("MUTANTS = [x for x in range(1000000000000) if x != x]\n", "scripts/mutants/X6.py", timeout=1)


def _lot(**mutants) -> dict:
    return {mid: (spec[2] if len(spec) > 2 else "glorfindel/x.py", spec[0], spec[1], spec[3] if len(spec) > 3 else "",
                  spec[4] if len(spec) > 4 else "MUTANTS")
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


def test_a_mutant_moved_into_the_control_set_is_refused():
    said = _judge_lots({"old": _lot(M1=("a", "b")), "new": _lot(M1=("a", "b", "glorfindel/x.py", "", "CONTROL"))})
    assert said == ["moves the mutant M1 into the control set, which is never red"]
    control = LOT.replace("MUTANTS += [", "CONTROL = [")
    assert ng.judge([modified("scripts/mutants/X1.py", LOT, control)]) == [
        "moves the mutant M4 into the control set, which is never red"]


@pytest.mark.parametrize("new", ["scripts/mutants/_X1.py", "scripts/mutants/old/X1.py"])
def test_a_lot_s_file_moved_where_the_harness_does_not_read_takes_its_mutants_out(new):
    said = ng.judge([Change("scripts/mutants/X1.py", new, LOT, LOT)])
    assert said[0].startswith(f"{new}: touches ")
    assert said[1:] == [f"removes the mutant M{n}" for n in range(1, 5)]


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
    ("tests/unit/invariant_watchdog.py", "nights' watchdog"),
    ("tests/unit/hypothesis_seed.py", "the seed the invariant nights draw (SEED1): a question for Jonathan"),
    ("tests/unit/test_hypothesis_seed.py", "the tests of the seed the invariant nights draw (SEED1): a question "
                                           "for Jonathan"),
    ("tests/unit/french_ceiling.json", "French output's ceilings"),
    ("scripts/mutation_check.py", "mutation's harness"),
    ("scripts/mutant_anchors.py", "anchors check"),
    ("scripts/mutants/narrowed.json", "narrowed tests"),
    ("scripts/mutants/_helpers.py", "a helper of the lots' files"),
    ("scripts/mutants/old/NOC1.py", "a sub-directory of scripts/mutants/"),
    ("conftest.py", "a conftest.py"),
    ("tests/unit/conftest.py", "a conftest.py"),
    ("infra/orodruin/tests/conftest.py", "a conftest.py"),
    ("pytest.ini", "pytest.ini wins"),
    (".pytest.ini", ".pytest.ini"),
    ("tox.ini", "tox.ini"),
    ("setup.cfg", "setup.cfg"),
    (".claude/skills/elrond/SKILL.md", "night's own rails"),
    ("scripts/night/eregion-night.service", "night's own rails"),
    ("tests/unit/test_night_unit.py", "night's own rails (tests/unit/test_night_unit.py"),
    ("scripts/night_guard.py", "night's own guard"),
    ("tests/unit/test_night_guard.py", "night's own guard"),
    ("scripts/review_verdict.py", "review's verdict"),
])
def test_a_protected_path_is_refused_added_changed_or_deleted(path, said):
    for change in (modified(path, "a\n", "b\n"), Change(None, path, None, "b\n"), Change(path, None, "a\n", None)):
        out = ng.protected_paths([change])
        assert len(out) == 1 and out[0].startswith(f"{path}: ") and said in out[0], out


@pytest.mark.parametrize("path", ["pytest.py", "hypothesis.py", "pytest/__init__.py", "_pytest/__init__.py"])
def test_a_module_or_a_package_added_at_the_root_is_refused(path):
    assert judged(Change(None, path, None, "")) == [
        f"{path}: adds a module or a package at the repository's root, first on sys.path"]
    assert judged(Change("tools/x.py", path, "", "")) == [
        f"{path}: adds a module or a package at the repository's root, first on sys.path"]


@pytest.mark.parametrize("path", ["tests/hypothesis.py", "tests/glorfindel.py", "tests/glorfindel",
                                  "tests/eregion_core.py", "tests/pytest.cpython-312-x86_64-linux-gnu.so"])
def test_a_file_added_directly_under_tests_is_refused(path):
    """tests/ is no package, tests/unit/ is: in prepend mode pytest puts tests/ before the root on sys.path, and a
    tests/hypothesis.py (or a link tests/glorfindel) hides that name from the whole machine (NOC1b)."""
    said = f"{path}: adds a file directly under tests/, which pytest puts before the root on sys.path"
    assert said in judged(Change(None, path, None, ""))
    assert said in judged(Change("docs/x.py", path, "", ""))


def test_nothing_sits_directly_under_tests_today():
    """Read on the files themselves, not on git: the mutation's harness runs on a copy without .git."""
    assert (ROOT / "tests" / "unit").is_dir()
    assert [p.name for p in (ROOT / "tests").iterdir() if not p.is_dir() or p.is_symlink()] == []


def test_a_module_deeper_or_one_already_at_the_root_asks_nothing():
    assert judged(Change(None, "glorfindel/new.py", None, ""), Change(None, "tools/x/__init__.py", None, ""),
                  modified("setup.py", "a", "b"), Change(None, "README.txt", None, "")) == []


def test_a_file_moved_out_of_a_protected_place_is_refused():
    out = ng.protected_paths([Change("requirements/dev.txt", "docs/dev.txt", "a", "a")])
    assert out == ["requirements/dev.txt: touches the locked dependencies (requirements/)"]


# The whole invariant machine (NOC1b, #1269, Jonathan's decision of 27/11: « Oui, avec les régressions »).
MACHINE = ("tests/unit/test_invariants.py", "tests/unit/test_invariants_aws.py", "tests/unit/test_invariant_journal.py",
           "tests/unit/test_invariant_hold.py", "tests/unit/test_invariant_regressions.py",
           "tests/unit/test_invariant_regressions_aws.py", "tests/unit/test_invariant_watchdog.py")


@pytest.mark.parametrize("path", MACHINE)
def test_each_file_of_the_invariant_machine_is_refused_and_said_a_question_for_jonathan(path):
    """A sequence frozen, the journal's exemptions, the hold's tests, the watchdog's: none merges at night."""
    for change in (modified(path, "a\n", "b\n"), Change(None, path, None, "b\n"), Change(path, None, "a\n", None),
                   Change(path, "tests/unit/test_moved.py", "a\n", "a\n")):
        out = ng.protected_paths([change])
        assert len(out) == 1 and out[0].startswith(f"{path}: ") and "invariant machine" in out[0] \
            and "a question for Jonathan" in out[0], out
    said = judged(modified(path, "", "def test_a_sequence_frozen():\n    pass\n"))
    assert said and said[0].startswith(f"{path}: touches the invariant machine"), said


def test_the_machine_s_list_is_the_tree_s():
    """Every test file of the machine in the tree is in MACHINE, and each one exists: the list never goes stale."""
    tree = sorted(f"tests/unit/{p.name}" for p in (ROOT / "tests" / "unit").glob("test_invariant*.py"))
    assert tree == sorted(MACHINE)
    for name in ("invariant_watchdog.py", "hypothesis_seed.py", "test_hypothesis_seed.py", "test_night_unit.py",
                 "__init__.py"):
        assert (ROOT / "tests" / "unit" / name).exists(), name


def _resolve(base: Path, parts: list[str]) -> Path | None:
    """The module `parts` under `base`: its .py, or its package's directory; None when it is not a module."""
    target = base.joinpath(*parts) if parts else base
    if target.with_suffix(".py").is_file() and parts:
        return target.with_suffix(".py")
    return target if target.is_dir() else None


def _imports(path: Path, root: Path) -> list[tuple[Path, list[str], list[str]]]:
    """What a file imports of tests/unit/: (the directory it starts from, the module's parts, the names
    imported from it) — relative (`from .x import`, `from . import x`, `from ..x import`) or absolute
    (`import tests.unit.x`, `from tests.unit.x import`, `from tests.unit import x`, `from unit.x import`)."""
    unit = root / "tests" / "unit"
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.level:
            base = path.parent
            for _ in range(node.level - 1):
                base = base.parent
            out.append((base, node.module.split(".") if node.module else [], [a.name for a in node.names]))
            continue
        dotted = [a.name for a in node.names] if isinstance(node, ast.Import) else \
            [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
        names = [a.name for a in node.names] if isinstance(node, ast.ImportFrom) else []
        for name in dotted:
            parts = name.split(".")
            if parts[:2] == ["tests", "unit"]:
                out.append((unit, parts[2:], names))
            elif parts[0] == "unit":
                out.append((unit, parts[1:], names))
    return out


def machine_closure(root: Path) -> set[str]:
    """Every file the invariant machine reaches through its imports of tests/unit/, relative to `root`: the
    closure from tests/unit/test_invariant*.py, a package taken whole (each of its files, its sub-modules
    and their own imports followed)."""
    unit = root / "tests" / "unit"
    todo, scanned, reached = sorted(unit.glob("test_invariant*.py")), set(), set()
    while todo:
        f = todo.pop()
        if f in scanned:
            continue
        scanned.add(f)
        reached.add(f.relative_to(root).as_posix())
        for base, parts, names in _imports(f, root):
            module = _resolve(base, parts)
            assert module is not None, f"{f.relative_to(root)}: imports {'.'.join(parts)}, which the test cannot find"
            subs = [_resolve(module, [n]) for n in names] if module.is_dir() else []
            if not parts:   # `from . import x`: x a module of the package, or a name of its __init__.py
                found = [m for m in subs if m] or [module / "__init__.py"]
                found += [module / "__init__.py"] if None in subs else []
            else:           # `from .x import y`: the module x (a package whole), y a sub-module of it if it is one
                found = [module] + [m for m in subs if m]
            for m in found:
                if m.is_dir():
                    for g in sorted(m.rglob("*")):
                        if g.is_file():
                            reached.add(g.relative_to(root).as_posix())
                            if g.suffix == ".py":
                                todo.append(g)
                else:
                    todo.append(m)
    return reached


def _unheld(root: Path) -> list[str]:
    return [rel for rel in sorted(machine_closure(root)) if not ng.protected_paths([modified(rel, "a", "b")])]


def test_every_module_the_machine_imports_is_held():
    """The closure of the imports of tests/unit/test_invariant*.py, relative and absolute: each file reached (a
    fake, the hold, the watchdog, the seed, one frozen sequence another reads, each file of a package) is refused
    at night. A companion added to the machine (an invariant_journal.py, a fake_gcp/ package) fails here until
    the guard holds it (NOC1b)."""
    reached = machine_closure(ROOT)
    assert {f"tests/unit/{n}" for n in ("fake_azure.py", "fake_aws.py", "invariant_hold.py",
                                        "invariant_watchdog.py", "hypothesis_seed.py")} <= reached
    assert _unheld(ROOT) == []


@pytest.mark.parametrize("files, unheld", [
    ({"test_invariant_x.py": "from .fake_gcp import X\n", "fake_gcp.py": "X = 1\n"}, ["tests/unit/fake_gcp.py"]),
    ({"test_invariant_x.py": "from .fake_gcp import X\n", "fake_gcp/__init__.py": "from .core import X\n",
      "fake_gcp/core.py": "X = 1\n"}, ["tests/unit/fake_gcp/core.py"]),
    ({"test_invariant_x.py": "from . import fake_gcp\n", "fake_gcp/__init__.py": "",
      "fake_gcp/core.py": "X = 1\n"}, ["tests/unit/fake_gcp/core.py"]),
    ({"test_invariant_x.py": "from tests.unit.fake_gcp2 import X\n", "fake_gcp2.py": "X = 1\n"},
     ["tests/unit/fake_gcp2.py"]),
    ({"test_invariant_x.py": "import tests.unit.fake_gcp2\n", "fake_gcp2.py": "X = 1\n"}, ["tests/unit/fake_gcp2.py"]),
    ({"test_invariant_x.py": "from tests.unit import fake_gcp2\n", "fake_gcp2.py": "X = 1\n"},
     ["tests/unit/fake_gcp2.py"]),
    ({"test_invariant_x.py": "from unit.fake_gcp2 import X\n", "fake_gcp2.py": "X = 1\n"}, ["tests/unit/fake_gcp2.py"]),
    ({"test_invariant_x.py": "from .fake_azure import X\n", "fake_azure.py": "from .helper_x import Y\n",
      "helper_x.py": "Y = 1\n"}, ["tests/unit/helper_x.py"]),
])
def test_the_closure_finds_a_companion_however_it_is_imported(tmp_path, files, unheld):
    """The probes, on a tree of their own: a module, a package (each of its files), an absolute import, a
    companion of a companion — each reached, and said unheld until the guard holds it. The machine's own test
    file is held by its pattern, a package's __init__.py by `tests/*/__init__.py`."""
    unit = tmp_path / "tests" / "unit"
    for rel, text in {"__init__.py": "", **files}.items():
        (unit / rel).parent.mkdir(parents=True, exist_ok=True)
        (unit / rel).write_text(text, encoding="utf-8")
    assert _unheld(tmp_path) == unheld


@pytest.mark.parametrize("prefix", ["fake_azure", "fake_aws", "invariant_hold", "invariant_watchdog",
                                    "hypothesis_seed"])
def test_a_package_or_a_link_of_a_companion_s_name_is_refused(prefix):
    """Python prefers a package to a module of the same name: tests/unit/fake_azure/__init__.py would hide
    fake_azure.py from the machine's `from .fake_azure import …`; a link tests/unit/fake_azure too."""
    for path in (f"tests/unit/{prefix}/__init__.py", f"tests/unit/{prefix}", f"tests/unit/{prefix}.pyc",
                 f"tests/unit/{prefix}/x.py"):
        out = ng.protected_paths([Change(None, path, None, "")])
        assert len(out) == 1 and out[0].startswith(f"{path}: ") and "a question for Jonathan" in out[0], out


@pytest.mark.parametrize("path", ["tests/unit/__init__.py", "tests/__init__.py", "tests/integration/__init__.py",
                                  "tests/unit/sub/__init__.py"])
def test_a_package_of_the_tests_is_refused(path):
    for change in (modified(path, "", "x = 1\n"), Change(None, path, None, ""), Change(path, None, "", None)):
        out = ng.protected_paths([change])
        assert len(out) == 1 and "a package of the tests" in out[0], out


@pytest.mark.parametrize("path, said", [
    ("pytest.pyc", "compiled module"),
    ("tests/unit/test_a.pyo", "compiled module"),
    ("glorfindel/x.pyc", "compiled module"),
    ("tests/unit/__pycache__/fake_azure.cpython-312.pyc", "compiled module"),
    ("tests/unit/__pycache__/notes.txt", "__pycache__/"),
    ("__pycache__/x", "__pycache__/"),
    ("tests/unit/__pycache__", "a link"),
    ("glorfindel/actions.cpython-312-x86_64-linux-gnu.so", "extension module (.so)"),
    ("tests/unit/fake_x.so", "extension module (.so)"),
    ("glorfindel/actions.cp312-win_amd64.pyd", "extension module (.pyd)"),
])
def test_a_compiled_module_or_a_pycache_is_refused(path, said):
    """An unchecked-hash .pyc, added with `git add -f` despite .gitignore, can be imported instead of its source."""
    out = ng.protected_paths([Change(None, path, None, "")])
    assert len(out) == 1 and said in out[0], out


@pytest.mark.parametrize("path", ["tests/unit/test_investigate.py", "tests/unit/test_inventory.py",
                                  "tests/unit/test_integrity.py", "tests/test_invariant_x.py",
                                  "tests/unit/invariant_notes.md", "docs/test_invariant_hold.py",
                                  "tests/unit/fake_graph.py", "tests/unit/fake_oci.py", "glorfindel/__init__.py",
                                  "tests/unit/test_hypothesis.py", "tests/unit/pycache.md"])
def test_a_neighbour_outside_the_machine_is_not_protected(path):
    assert ng.protected_paths([modified(path, "a", "b")]) == []


def test_a_workflow_s_namesake_elsewhere_and_a_lot_s_file_are_not_protected():
    assert ng.protected_paths([modified("docs/github/workflows.md", "a", "b"),
                               modified("scripts/mutants/NOC1.py", "a", "b")]) == []


def test_pyproject_s_dependencies_build_and_pytest_settings_are_refused_its_version_is_not():
    bump = PYPROJECT.replace('version = "0.6.11"', 'version = "0.6.12"')
    assert judged(modified("pyproject.toml", PYPROJECT, bump)) == []
    for old, new, table in (('dependencies = ["click>=8"]', 'dependencies = ["click>=8", "x"]', "project.dependencies"),
                            ('dev = ["pytest"]', 'dev = ["pytest<9"]', "project.optional-dependencies"),
                            ('addopts = "-q"', 'addopts = "-q --deselect tests/unit/test_a.py"', "tool.pytest"),
                            ("line-length = 120", 'line-length = 120\nignore = ["F811"]', "tool.ruff"),
                            ('dev = ["pytest"]', 'dev = ["pytest"]\n\n[project.entry-points.pytest11]\nx = "x"',
                             "project.entry-points")):
        said = judged(modified("pyproject.toml", PYPROJECT, PYPROJECT.replace(old, new)))
        assert said == [f"pyproject.toml: changes [{table}] (the dependencies, the entry points, the build, pytest's "
                        "or ruff's settings)"], said
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
                "tests/unit/invariant_hold.py", "tests/unit/invariant_watchdog.py", "tests/unit/french_ceiling.json",
                "scripts/mutation_check.py",
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
    assert out.splitlines() == ["night guard: the CI's counts not measured (no --pr): the diff's reading alone",
                                "night guard: merge refused without Jonathan (1 reason(s), 1 file(s) read):",
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


# ── What the CI did: the counts ──────────────────────────────────────────────────────────────────────

HEAD = "a" * 40
BASE = "b" * 40


def ci_log(job="lint + tests (py3.12)", passed=10700, skipped=8, xfailed=0, deselected=0, mutants=6163, control=32,
           head=HEAD, base=BASE, merged=True, anchors=True, summary=True):
    """A job's log as `gh run view --job … --log` gives it: job, step, timestamp, line."""
    at = "2026-11-27T05:00:00.0000000Z"
    rows = []
    if merged:
        rows.append(("Run actions/checkout", f"HEAD is now at 1234567 Merge {head} into {base}"))
    if anchors:
        rows.append(("Mutants anchored to this tree", f"{mutants} mutants and {control} of the control set "
                                                       "(285 lot file(s) in scripts/mutants/), 0 fault(s)"))
    rows.append(("Provider boundary", "3 passed in 0.52s"))
    rows.append(("Tests", f"4 workers [{passed} items]"))
    if summary:
        parts = [f"{passed} passed", f"{skipped} skipped"] + ([f"{xfailed} xfailed"] if xfailed else []) + (
            [f"{deselected} deselected"] if deselected else []) + ["44 warnings"]
        rows.append(("Tests", ", ".join(parts) + " in 180.52s (0:03:00)"))
    rows.append(("Azure's invariant machine", "1 passed in 300.01s (0:05:00)"))
    return "\n".join(f"{job}\t{step}\t{at} {line}" for step, line in rows) + "\n"


class FakeGh:
    """gh, as the guard calls it: the PR, its CI's run, main's push run, their jobs and logs. Never GitHub."""

    def __init__(self, pr=None, pr_runs=None, main_runs=None, head=None, base=None):
        self.pr = pr if pr is not None else {"isCrossRepository": False, "headRefOid": HEAD, "headRefName": "lot/n1",
                                             "baseRefName": "main"}
        self.pr_runs = pr_runs if pr_runs is not None else [
            {"databaseId": 1, "headSha": HEAD, "headBranch": "lot/n1", "event": "pull_request", "conclusion": "success"}]
        self.main_runs = main_runs if main_runs is not None else [
            {"databaseId": 2, "headSha": BASE, "headBranch": "main", "event": "push", "conclusion": "success"}]
        self.logs = {"1": head or {}, "2": base or {}}
        self.calls = []

    def __call__(self, args):
        self.calls.append(args)
        if args[:2] == ["pr", "view"]:
            return json.dumps(self.pr)
        if args[:2] == ["run", "list"]:
            event = args[args.index("--event") + 1]
            return json.dumps(self.pr_runs if event == "pull_request" else self.main_runs)
        if args[:2] == ["run", "view"] and "--log" in args:
            run, job = args[args.index("--job") + 1].split(":")
            return self.logs[run].get(job, ci_log(job))
        if args[:2] == ["run", "view"]:
            return json.dumps({"jobs": [{"name": n, "databaseId": f"{args[2]}:{n}"} for n in ng.CI_JOBS]})
        raise AssertionError(args)


def logs(**kw):
    return {job: ci_log(job, **kw) for job in ng.CI_JOBS}


SLUG = "o/eregion"


def measured(gh, added=0):
    return ng.measure(7, HEAD, gh, slug=SLUG, added=added)


def test_pytest_s_summary_lines_are_summed_over_a_job_s_runs():
    got = ng.pytest_counts(ci_log(passed=100, skipped=2, xfailed=1, deselected=3))
    assert got["passed"] == 104 and got["skipped"] == 2 and got["xfailed"] == 1 and got["deselected"] == 3
    assert got["collected"] == 107 and got["lines"] == 3 and got["warning"] == 44     # deselected: not run
    assert ng.pytest_counts(ci_log(summary=False))["lines"] == 2
    assert ng.pytest_counts("no summary here\n4 workers [10 items]\n") is None
    assert ng.mutant_counts(ci_log(mutants=6163, control=32)) == (6163, 32)
    assert ng.mutant_counts(ci_log(anchors=False)) is None


def test_the_counts_as_on_main_or_more_tests_may_merge():
    assert measured(FakeGh(head=logs(passed=10701), base=logs())) == []
    assert measured(FakeGh(head=logs(), base=logs())) == []


def test_fewer_tests_collected_than_on_main_is_refused():
    said = measured(FakeGh(head=logs(passed=10690), base=logs()))
    assert said == [f"{job}: the tests run go from 10712 to 10702 though the diff adds 0 by name: a test left the run"
                    for job in ng.CI_JOBS]


def test_a_test_skipped_or_deselected_instead_of_run_is_refused_by_the_counts():
    said = measured(FakeGh(head=logs(passed=10699, skipped=9), base=logs()))
    assert said == [f"{job}: skipped goes up (8 -> 9)" for job in ng.CI_JOBS]
    said = measured(FakeGh(head=logs(passed=10699, xfailed=1), base=logs()))
    assert said == [f"{job}: xfailed goes up (0 -> 1)" for job in ng.CI_JOBS]
    said = measured(FakeGh(head=logs(passed=10699, deselected=1), base=logs()))
    assert said == [r for job in ng.CI_JOBS for r in (
        f"{job}: the tests run go from 10712 to 10711 though the diff adds 0 by name: a test left the run",
        f"{job}: deselected goes up (0 -> 1)")]


def test_a_deselected_test_put_back_or_removed_asks_nothing():
    """A deselected test is no test run: one fewer deselected is never one fewer run."""
    assert measured(FakeGh(head=logs(), base=logs(deselected=1))) == []


def test_fewer_mutants_or_a_smaller_control_set_than_on_main_is_refused():
    said = measured(FakeGh(head=logs(mutants=6137), base=logs()))
    assert said == [f"{job}: 26 mutant(s) fewer measured than on main (6163 -> 6137)" for job in ng.CI_JOBS]
    said = measured(FakeGh(head=logs(control=31), base=logs()))
    assert said == [f"{job}: the control set goes down (32 -> 31)" for job in ng.CI_JOBS]
    assert measured(FakeGh(head=logs(mutants=6170, control=33), base=logs())) == []


def test_a_summary_or_a_count_that_cannot_be_read_is_refused():
    said = measured(FakeGh(head=logs(summary=False, merged=True), base=logs()))
    assert said == [f"{job}: pytest's summary lines read on 3 step(s) on main, 2 on the PR: a run cut short is "
                    "never compared" for job in ng.CI_JOBS]
    head = {job: "\n".join(line for line in ci_log(job).splitlines() if "passed" not in line) for job in ng.CI_JOBS}
    said = measured(FakeGh(head=head, base=logs()))
    assert said[0] == f"{ng.CI_JOBS[0]}: pytest's summary line not read on the PR: the tests run cannot be compared"
    said = measured(FakeGh(head=logs(anchors=False), base=logs()))
    assert said == [f"{job}: the mutants' count (mutant_anchors.py) not read on the PR" for job in ng.CI_JOBS]
    base = {job: "\n".join(line for line in ci_log(job).splitlines() if "passed" not in line) for job in ng.CI_JOBS}
    said = measured(FakeGh(head=logs(), base=base))
    assert said[0].endswith("not read on main: the tests run cannot be compared")


def test_a_test_out_of_the_run_covered_by_a_test_added_is_refused():
    """The review's third round, B1: a class given an __init__ (its test out of the run) and a test added
    beside it leave the count where it was: the diff's tests added by name must show on top of main's."""
    said = measured(FakeGh(head=logs(), base=logs()), added=1)
    assert said == [f"{job}: the tests run go from 10712 to 10712 though the diff adds 1 by name: a test left the run"
                    for job in ng.CI_JOBS]
    assert measured(FakeGh(head=logs(passed=10701), base=logs()), added=1) == []
    assert measured(FakeGh(head=logs(passed=10703), base=logs()), added=1) == []    # a parametrize: more than one


def test_main_s_run_cut_short_is_never_compared():
    """The review's third round, C1: a base log without its « Tests » summary would count 4 tests on main."""
    base = {job: "\n".join(line for line in ci_log(job).splitlines() if "\tTests\t" not in line or "workers" in line)
            for job in ng.CI_JOBS}
    said = measured(FakeGh(head=logs(), base=base))
    assert said == [f"{job}: pytest's summary lines read on 2 step(s) on main, 3 on the PR: a run cut short is never "
                    "compared" for job in ng.CI_JOBS]


def test_a_summary_line_a_test_prints_in_its_step_is_never_the_one_read():
    """capsys.disabled() prints in the step without xdist: only the last summary of each step counts."""
    forged = {job: ci_log(job).replace(
        f"{job}\tProvider boundary\t2026-11-27T05:00:00.0000000Z 3 passed in 0.52s",
        f"{job}\tProvider boundary\t2026-11-27T05:00:00.0000000Z 500 passed in 1.00s\n"
        f"{job}\tProvider boundary\t2026-11-27T05:00:00.0000000Z 3 passed in 0.52s") for job in ng.CI_JOBS}
    assert ng.pytest_counts(forged[ng.CI_JOBS[0]])["collected"] == 10712
    said = measured(FakeGh(head=forged, base=logs()), added=1)
    assert said and all("a test left the run" in r for r in said)


def test_the_tests_added_by_name_are_counted_in_collected_files_under_tests_only():
    assert ng.added_tests([modified("tests/unit/test_a.py", TESTS_A, TESTS_A + "\n\ndef test_three():\n    pass\n")]) == 1
    assert ng.added_tests([Change(None, "tests/unit/test_c.py", None, TESTS_A)]) == 2
    moved = [modified("tests/unit/test_a.py", TESTS_A, ""), Change(None, "tests/unit/test_b.py", None, TESTS_A)]
    assert ng.added_tests(moved) == 0
    assert ng.added_tests([Change(None, "tests/unit/helpers.py", None, TESTS_A),
                           Change(None, "infra/x/test_x.py", None, TESTS_A)]) == 0


def test_every_gh_call_names_the_repository_of_origin():
    gh = FakeGh(head=logs(), base=logs())
    assert measured(gh) == []
    assert gh.calls and all(c[-2:] == ["--repo", SLUG] for c in gh.calls)
    with pytest.raises(ValueError, match="not said"):
        ng.measure(7, HEAD, FakeGh(), slug="")


@pytest.mark.parametrize("url, slug", [
    ("https://github.com/grootcyber/eregion.git", "grootcyber/eregion"),
    ("https://github.com/grootcyber/eregion", "grootcyber/eregion"),
    ("git@github.com:grootcyber/eregion.git", "grootcyber/eregion"),
])
def test_the_repository_is_read_on_origin(repo, url, slug):
    git(repo, "remote", "add", "origin", url)
    assert ng.repo_slug(repo) == slug


def test_an_origin_that_is_no_github_repository_cannot_be_read(repo):
    git(repo, "remote", "add", "origin", "https://example.org/x.git")
    with pytest.raises(RuntimeError, match="no GitHub repository"):
        ng.repo_slug(repo)


def test_a_pr_from_a_fork_or_unsaid_is_never_read():
    for cross in (True, None):
        gh = FakeGh(pr={"isCrossRepository": cross, "headRefOid": HEAD, "headRefName": "main", "baseRefName": "main"})
        assert measured(gh) == [
            "PR #7 does not come from the repository itself (a fork, or unsaid): its CI is not read"]
        assert [c[:2] for c in gh.calls] == [["pr", "view"]]


def test_the_runs_read_are_the_pr_s_own_on_the_head_and_main_s_push_on_what_it_merged_into():
    gh = FakeGh(pr_runs=[{"databaseId": 9, "headSha": HEAD, "headBranch": "main", "event": "pull_request",
                          "conclusion": "success"}])
    assert measured(gh) == [f"no green CI run of PR #7 on {HEAD[:12]} (ci.yml, pull_request): nothing to compare"]
    gh = FakeGh(pr_runs=[{"databaseId": 1, "headSha": HEAD, "headBranch": "lot/n1", "event": "pull_request",
                          "conclusion": "failure"}])
    assert measured(gh)[0].startswith("no green CI run of PR #7")
    assert measured(FakeGh(head=logs(merged=False), base=logs()))[0].startswith(
        "the commit PR #7's CI merged into is not read")
    assert measured(FakeGh(head=logs(head="c" * 40), base=logs()))[0].startswith(
        "the commit PR #7's CI merged into is not read")
    gh = FakeGh(main_runs=[{"databaseId": 2, "headSha": "d" * 40, "headBranch": "main", "event": "push",
                            "conclusion": "success"}])
    assert measured(gh) == [f"no run of main's push CI on {BASE[:12]}, the commit PR #7's CI merged into: "
                                       "nothing to compare"]
    red_main = FakeGh(main_runs=[{"databaseId": 2, "headSha": BASE, "headBranch": "main", "event": "push",
                                  "conclusion": "failure"}], head=logs(), base=logs())
    assert measured(red_main) == []          # main red is what the night fixes: its counts still read
    gh = FakeGh(pr={"isCrossRepository": False, "headRefOid": "e" * 40, "headRefName": "lot/n1", "baseRefName": "main"})
    assert measured(gh)[0].startswith("PR #7's head (eeeeeeeeeeee) is not the commit reviewed")
    assert [c for c in gh.calls if c[:2] == ["run", "list"]] == []       # nothing read past a head that moved


def test_check_with_a_pr_measures_its_ci_before_reading_its_diff(repo, capsys):
    git(repo, "remote", "add", "origin", "https://github.com/o/eregion.git")
    head = commit(repo, "app.py", "a = 2\n")
    gh = FakeGh(pr={"isCrossRepository": False, "headRefOid": head, "headRefName": "lot/x", "baseRefName": "main"},
                pr_runs=[{"databaseId": 1, "headSha": head, "headBranch": "lot/x", "event": "pull_request",
                          "conclusion": "success"}], head=logs(head=head, passed=10600), base=logs(head=head))
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head, "--pr", "7"], gh=gh) == 1
    out = capsys.readouterr().out
    assert "lint + tests (py3.11): the tests run go from 10712 to 10612 though the diff adds 0 by name" in out
    gh = FakeGh(pr=gh.pr, pr_runs=gh.pr_runs, head=logs(head=head), base=logs(head=head))
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head, "--pr", "7"], gh=gh) == 0
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head]) == 0
    assert "the CI's counts not measured (no --pr)" in capsys.readouterr().out
    # the tests the branch adds by name reach the count: added, though the CI shows none of them
    head = commit(repo, "tests/unit/test_c.py", "def test_c():\n    pass\n")
    gh = FakeGh(pr={**gh.pr, "headRefOid": head}, pr_runs=[{**gh.pr_runs[0], "headSha": head}],
                head=logs(head=head), base=logs(head=head))
    assert ng.main(["check", "--repo", str(repo), "--base", "main", "--head", head, "--pr", "7"], gh=gh) == 1
    assert "though the diff adds 1 by name: a test left the run" in capsys.readouterr().out

