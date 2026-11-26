"""NOC1 (#1251): the night's guard — what a pull request the night fixed may not merge without Jonathan
(scripts/night_guard.py; docs/sessions.md, « La nuit »). Pure judgements on changes, then the same on a
throwaway git repository (no network, no GitHub)."""
from __future__ import annotations

import importlib.util
import os
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


# ── Tests: removed, renamed, skipped ─────────────────────────────────────────────────────────────────

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


@pytest.mark.parametrize("added", [
    "@pytest.mark.skip(reason='later')\n",
    "@pytest.mark.skipif(sys.platform == 'linux', reason='x')\n",
    "@pytest.mark.xfail(strict=False)\n",
    "@mark.xfail\n",
    "@unittest.skip('later')\n",
])
def test_a_skip_or_an_xfail_added_is_refused(added):
    new = TESTS_A.replace("def test_one", added + "def test_one")
    assert judged(modified("tests/unit/test_a.py", TESTS_A, new)) == ["tests/unit/test_a.py: adds 1 skip, skipif or xfail"]


def test_a_skip_called_in_a_test_is_refused_too():
    new = TESTS_A.replace("    assert True\n", "    pytest.skip('no network')\n", 1)
    assert judged(modified("tests/unit/test_a.py", TESTS_A, new)) == ["tests/unit/test_a.py: adds 1 skip, skipif or xfail"]


def test_one_more_skip_beside_one_already_there_is_refused():
    old = TESTS_A.replace("def test_one", "@pytest.mark.skip\ndef test_one")
    new = old.replace("    def test_two", "    @pytest.mark.xfail\n    def test_two")
    assert judged(modified("tests/unit/test_a.py", old, new)) == ["tests/unit/test_a.py: adds 1 skip, skipif or xfail"]


def test_a_skip_that_only_moves_or_a_word_skip_in_a_string_asks_nothing():
    old = TESTS_A.replace("def test_one", "@pytest.mark.skip\ndef test_one")
    moved = TESTS_A.replace("    def test_two", "    @pytest.mark.skip\n    def test_two")
    assert judged(modified("tests/unit/test_a.py", old, moved)) == []
    words = TESTS_A + '\n\ndef test_flags():\n    assert "--skip-machine-baseline" and "skip_reason"\n'
    assert judged(modified("tests/unit/test_a.py", TESTS_A, words)) == []


def test_a_test_file_unreadable_is_refused():
    said = judged(modified("tests/unit/test_a.py", TESTS_A, "def test_one(:\n"))
    assert said[0].startswith("tests/unit/test_a.py: unreadable after the change")
    assert said[1:] == ["tests/unit/test_a.py: removes or renames the test TestBox.test_two",
                        "tests/unit/test_a.py: removes or renames the test test_one"]


# ── Mutants ──────────────────────────────────────────────────────────────────────────────────────────

def test_a_lot_s_file_is_read_apart_with_its_helpers_and_renames():
    got = ng.load_mutants(LOT, "scripts/mutants/X1.py")
    assert got == {"M1": ("glorfindel/x.py", "a = 1\n", "a = 2\n"), "M2": ("glorfindel/x.py", "b = 1\n", "b = 2\n"),
                   "M3": ("glorfindel/x.py", "return 1\n", "return 0\n"),
                   "M4": ("docs/x.md", ng.RENAMED, "docs/y.md")}
    with pytest.raises(ValueError, match="NameError"):
        ng.load_mutants("MUTANTS = [UNKNOWN]\n", "scripts/mutants/X2.py")


def _lot(**mutants) -> dict:
    return {mid: ("glorfindel/x.py", old, new) for mid, (old, new) in mutants.items()}


def test_a_mutant_removed_is_refused():
    before = _lot(M1=("a", "b"), M2=("c", "d"))
    after = _lot(M1=("a", "b"))
    loads = {"old": before, "new": after}
    said = ng.mutants([modified("scripts/mutants/X1.py", "old", "new")], load=lambda text, name: loads[text])
    assert said == ["removes the mutant M2"]


def test_a_mutant_s_new_text_changed_without_its_old_is_refused():
    loads = {"old": _lot(M1=("a", "b")), "new": _lot(M1=("a", "B"))}
    said = ng.mutants([modified("scripts/mutants/X1.py", "old", "new")], load=lambda text, name: loads[text])
    assert said == ["changes the mutant M1's new text without its old one"]


def test_a_mutant_moved_with_its_code_or_to_another_file_asks_nothing():
    loads = {"old": _lot(M1=("a", "b")), "moved": _lot(M1=("a2", "b2")), "": {}}
    assert ng.mutants([modified("scripts/mutants/X1.py", "old", "moved")], load=lambda t, n: loads[t]) == []
    assert ng.mutants([Change("scripts/mutants/X1.py", None, "old", None),
                       Change(None, "scripts/mutants/X2.py", None, "moved")], load=lambda t, n: loads[t]) == []


def test_a_lot_s_file_unreadable_is_refused():
    def load(text, name):
        if text == "new":
            raise ValueError("SyntaxError: invalid syntax")
        return _lot(M1=("a", "b"))
    said = ng.mutants([modified("scripts/mutants/X1.py", "old", "new")], load=load)
    assert said[0] == "scripts/mutants/X1.py: its mutants unreadable after the change (SyntaxError: invalid syntax)"
    assert "removes the mutant M1" in said


def test_a_mutant_removed_through_the_real_loader():
    fewer = LOT.replace('    ("M2", "the second", T, "b = 1\\n", "b = 2\\n"),\n', "")
    assert ng.judge([modified("scripts/mutants/X1.py", LOT, fewer)]) == ["removes the mutant M2"]


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
