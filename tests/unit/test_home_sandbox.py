"""HY2 (#769): the suite never touches the operator's real ~/.glorfindel, even on a workstation where
it exists and a Glorfindel writes there.

tests/unit/home_sandbox.py makes HOME a throwaway folder as tests/unit/conftest.py is imported; the
conftest's `nothing_written_in_the_operators_store` guards the real folder. Here: the HOME of this
session, a module of the repository importing under it, what is linked to the real HOME (ChromaDB's
model alone), the folder's photograph and its changes, no `monkeypatch.undo()` left in the tests —
and the guard itself, measured in pytests of their own over an operator simulated in tmp (a HOME of
their own, with its ~/.glorfindel already there): never this workstation's. Mutants M5015–M5019
(scripts/mutants/HY2.py).
"""
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def _sandbox_module():
    spec = importlib.util.spec_from_file_location("_hy2_home_sandbox", HERE / "home_sandbox.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hs = _sandbox_module()


def _conftest():
    return next(m for m in list(sys.modules.values())
                if getattr(m, "__file__", None) and Path(m.__file__).resolve() == HERE / "conftest.py")


# --- This session's HOME ----------------------------------------------------------------------------

def test_this_session_s_home_is_a_throwaway_folder_never_the_operator_s():
    sandbox = _conftest().SANDBOX
    home = Path.home()
    assert home == sandbox.home == Path(os.environ[hs.HOME_VAR])
    assert Path(os.environ[hs.REAL_VAR]) == sandbox.real != home
    assert home.name.startswith("eregion-test-home-")
    assert home.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    assert not (home / ".glorfindel").resolve().is_relative_to(sandbox.store.resolve())
    assert not any(os.environ.get(name) for name in hs.XDG)


def test_a_write_through_path_home_lands_under_the_throwaway_home():
    """What DRN2's and JUG2's tests did on 12/11 — a path computed from HOME, at a module's import
    or later — now lies under the throwaway HOME: a module of the repository loaded afresh in this
    process, and in a fresh interpreter (a subprocess inherits the throwaway HOME)."""
    sandbox = _conftest().SANDBOX
    spec = importlib.util.spec_from_file_location("_hy2_bot_beat", ROOT / "glorfindel" / "bot_beat.py")
    bot_beat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bot_beat)
    assert bot_beat._STORE == sandbox.home / ".glorfindel" / "bot_heartbeat.json"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONPATH"] = str(ROOT)
    out = subprocess.run([sys.executable, "-c", "import glorfindel.bot_beat as b, glorfindel.vm_notices as v;"
                          " print(b._STORE); print(v._STORE)"], env=env, capture_output=True, text=True,
                         check=True, timeout=60).stdout.split()
    assert out == [str(sandbox.home / ".glorfindel" / "bot_heartbeat.json"),
                   str(sandbox.home / ".glorfindel" / "vm_notices.jsonl")]
    probe = Path.home() / ".glorfindel" / "hy2-probe.json"
    # Never written where the sandbox does not hold (a mutant of it): the operator's folder.
    assert hs.inside(probe, hs.roots_of(sandbox.store)) is None and Path.home() == sandbox.home
    try:
        probe.parent.mkdir(exist_ok=True)
        probe.write_text("{}")
        assert probe.resolve().is_relative_to(sandbox.home.resolve())
        assert not (sandbox.store / probe.name).exists()
    finally:
        probe.unlink(missing_ok=True)


def test_the_only_link_to_the_real_home_is_chroma_s_model():
    sandbox = _conftest().SANDBOX
    links = {}
    for top, dirs, files in os.walk(sandbox.home):
        for name in dirs + files:
            path = Path(top) / name
            if path.is_symlink():
                links[str(path.relative_to(sandbox.home))] = os.readlink(path)
    assert links == {str(rel): str(sandbox.real / rel) for rel in hs.KEPT}


# --- enter, leave ------------------------------------------------------------------------------------

def _operator(tmp_path) -> Path:
    real = tmp_path / "operator"
    (real / ".glorfindel").mkdir(parents=True)
    return real


def test_enter_makes_a_throwaway_home_and_leave_removes_it_never_what_it_links(tmp_path):
    real = _operator(tmp_path)
    model = real / ".cache" / "chroma" / "onnx_models" / "model.onnx"
    model.parent.mkdir(parents=True)
    model.write_text("weights")
    env = {"HOME": str(real), "XDG_CACHE_HOME": str(real / ".cache"), "XDG_CONFIG_HOME": str(real / ".config")}
    (tmp_path / "t").mkdir()
    sandbox = hs.enter(env, modules={}, tmp=str(tmp_path / "t"))
    assert sandbox.made and sandbox.real == real and sandbox.store == real / ".glorfindel"
    assert env["HOME"] == str(sandbox.home) == env[hs.HOME_VAR] and env[hs.REAL_VAR] == str(real)
    assert "XDG_CACHE_HOME" not in env and "XDG_CONFIG_HOME" not in env
    assert (sandbox.home / ".cache" / "chroma" / "onnx_models" / "model.onnx").read_text() == "weights"
    assert not (sandbox.home / ".glorfindel").exists()
    hs.leave(sandbox, env)
    assert not sandbox.home.exists()
    assert model.read_text() == "weights"
    assert env == {"HOME": str(real)}


def test_a_missing_model_is_linked_and_never_made_here(tmp_path):
    """A session that embeds nothing makes no ~/.cache in the real HOME; FLK1's lock makes the
    folder where the link leads, at the first fetch (scripts/chroma_model.py, `_flock`)."""
    real = _operator(tmp_path)
    env = {"HOME": str(real)}
    sandbox = hs.enter(env, modules={}, tmp=str(tmp_path))
    try:
        assert not (real / ".cache").exists()
        spec = importlib.util.spec_from_file_location("_hy2_chroma_model", ROOT / "scripts" / "chroma_model.py")
        chroma_model = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chroma_model)
        with chroma_model.held(sandbox.home / ".cache" / "chroma" / "onnx_models", say=pytest.fail):
            pass
        assert (real / ".cache" / "chroma" / "onnx_models" / chroma_model.LOCK).is_file()
    finally:
        hs.leave(sandbox, env)


def test_a_process_that_inherits_the_throwaway_home_keeps_it_and_leaves_it_be(tmp_path):
    real, home = _operator(tmp_path), tmp_path / "throwaway"
    home.mkdir()
    env = {"HOME": str(home), hs.HOME_VAR: str(home), hs.REAL_VAR: str(real)}
    sandbox = hs.enter(env, modules={"glorfindel": object()})   # imported already: its paths are home's
    assert sandbox == hs.Sandbox(home, real, made=False)
    hs.leave(sandbox, env)
    assert home.is_dir() and env["HOME"] == str(home)


def test_a_home_of_its_own_is_the_operator_s_whatever_was_inherited(tmp_path):
    """A pytest a test starts with a HOME of its own (test_chroma_model.py, the operator below):
    that HOME is the real one there, the markers inherited from this session notwithstanding."""
    real, stale = _operator(tmp_path), tmp_path / "stale"
    stale.mkdir()
    env = {"HOME": str(real), hs.HOME_VAR: str(stale), hs.REAL_VAR: "/nowhere"}
    sandbox = hs.enter(env, modules={}, tmp=str(tmp_path))
    try:
        assert sandbox.made and sandbox.real == real and sandbox.home != stale
    finally:
        hs.leave(sandbox, env)


def test_a_module_of_the_repository_imported_first_stops_the_session(tmp_path):
    env = {"HOME": str(_operator(tmp_path))}
    with pytest.raises(hs.Early, match="glorfindel.bot_beat"):
        hs.enter(env, modules={"pytest": object(), "glorfindel.bot_beat": object()}, tmp=str(tmp_path))
    assert env == {"HOME": str(tmp_path / "operator")} and not list(tmp_path.glob("eregion-test-home-*"))


# --- The photograph ----------------------------------------------------------------------------------

def test_the_photograph_says_what_was_created_changed_or_removed(tmp_path):
    store = _operator(tmp_path) / ".glorfindel"
    (store / "isolation").mkdir()
    (store / "isolation" / "vm.json").write_text("{}")
    (store / "escalations.jsonl").write_text("a\n")
    (store / "gone.json").write_text("{}")
    assert hs.photograph(tmp_path / "nowhere") is None
    before = hs.photograph(store)
    assert set(before) == {"isolation", os.path.join("isolation", "vm.json"), "escalations.jsonl", "gone.json"}
    assert hs.changes(before, hs.photograph(store)) == []
    with open(store / "escalations.jsonl", "a") as f:
        f.write("b\n")
    (store / "isolation" / "other.json").write_text("{}")
    (store / "gone.json").unlink()
    assert hs.changes(before, hs.photograph(store)) == [
        "escalations.jsonl (changed)", "gone.json (removed)", f"{os.path.join('isolation', 'other.json')} (created)"]


def test_a_live_glorfindel_is_told_by_its_heartbeats(tmp_path):
    store = _operator(tmp_path) / ".glorfindel"
    (store / "rule_status.json").write_text("{}")
    before = hs.photograph(store)
    (store / "rule_status.json").write_text('{"x": 1}')
    assert not hs.a_glorfindel_lives(before, hs.photograph(store))
    for beat in hs.HEARTBEATS:
        (store / beat).parent.mkdir(exist_ok=True)
        (store / beat).write_text("now")
        assert hs.a_glorfindel_lives(before, hs.photograph(store)), beat
        (store / beat).unlink()


def test_a_path_is_placed_in_the_store_as_given_or_resolved(tmp_path):
    store = _operator(tmp_path) / ".glorfindel"
    link = tmp_path / "home-link"
    link.symlink_to(store.parent)
    roots = hs.roots_of(link / ".glorfindel")
    assert hs.inside(store / "vm_notices.jsonl", roots) == "vm_notices.jsonl"
    assert hs.inside(link / ".glorfindel" / "a" / "b", roots) == os.path.join("a", "b")
    assert hs.inside(link / ".glorfindel", roots) == "."
    assert hs.inside(tmp_path / "operator" / ".glorfindel-old" / "x", roots) is None
    assert hs.inside(3, roots) is None and hs.inside(None, roots) is None


# --- No monkeypatch.undo() ---------------------------------------------------------------------------

def undo_calls(source: str) -> list[int]:
    """The lines of ``source`` that call an ``undo`` method (``….undo(``), in its code alone — a
    comment, a docstring or a string that names it is no call."""
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline)
              if t.type not in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                                tokenize.DEDENT)]
    return [b.start[0] for a, b, c in zip(tokens, tokens[1:], tokens[2:])
            if a.string == "." and b.type == tokenize.NAME and b.string == "undo" and c.string == "("]


def test_no_test_undoes_the_monkeypatch():
    """JUG2's test, on 12/11: its `monkeypatch.undo()` undid the conftest's redirection, and the bot's
    heartbeat went to the real ~/.glorfindel. A fixture that changes something for a while takes its
    own `pytest.MonkeyPatch.context()` (tests/unit/test_mobile.py, `far_zone`)."""
    found = [f"{path.relative_to(ROOT)}:{n}" for path in sorted((ROOT / "tests").rglob("*.py"))
             for n in undo_calls(path.read_text(encoding="utf-8"))]
    assert found == []


def test_the_scan_sees_an_undo_and_only_a_call():
    assert undo_calls("monkeypatch.undo()\nx = 1\nmp . undo (\n)\n") == [1, 3]
    assert undo_calls('"""`monkeypatch.undo()`"""\n# mp.undo()\ns = "a.undo()"\nundo()\nx.undo\n') == []


# --- The guard, over an operator simulated in tmp ---------------------------------------------------------

# Each scenario: (the operator's ~/.glorfindel before the run — None: there is none, as in CI —, the
# test, whether the run fails, what it says, pytest's arguments if any). The tests read the operator's
# HOME as the conftest kept it (EREGION_TEST_REAL_HOME): a path computed from the real HOME.
_STORE = 'Path(os.environ["EREGION_TEST_REAL_HOME"]) / ".glorfindel"'
SCENARIOS = {
    # DRN2's case: a store written in full in the operator's folder, which exists.
    "a_test_writes_there": ({"escalations.jsonl": "old\n"}, f"""
        import os
        from pathlib import Path
        def test_it():
            with open({_STORE} / "vm_notices.jsonl", "a") as f:
                f.write("{{}}")
            with open({_STORE} / "escalations.jsonl", "a") as f:
                f.write("new")
        """, True, ("the test suite wrote in the operator's", "vm_notices.jsonl (tests/unit/test_scenario.py::test_it)",
                    "escalations.jsonl (tests/unit/test_scenario.py::test_it)")),
    # JUG2's case: the conftest's redirections undone; the module's path computed under the throwaway HOME.
    "an_undone_monkeypatch": ({}, f"""
        import os
        from pathlib import Path
        import glorfindel.bot_beat as bot_beat
        def test_it(monkeypatch):
            monkeypatch.undo()
            bot_beat.write()
            assert bot_beat._STORE.is_file()
            assert not ({_STORE} / "bot_heartbeat.json").exists()
            assert Path.home() != Path(os.environ["EREGION_TEST_REAL_HOME"])
        """, False, ""),
    # A subprocess of a test, no Glorfindel running: only the photograph sees it.
    "a_subprocess_writes_there": ({"rule_status.json": "{}"}, f"""
        import os, subprocess, sys
        from pathlib import Path
        def test_it():
            subprocess.run([sys.executable, "-c", "import sys; open(sys.argv[1], 'w').write('x')",
                            str({_STORE} / "notes.json")], check=True)
        """, True, ("the test suite changed the operator's", "its heartbeats did not move", "notes.json (created)")),
    # A Glorfindel of the workstation runs (here a process that rewrites its heartbeat and a store,
    # as the watch does): said, never a verdict.
    "a_live_glorfindel": ({"watch_heartbeat": "then", "rule_status.json": "{}"}, f"""
        import os, subprocess, sys, time
        from pathlib import Path
        def test_it():
            time.sleep(0.05)
            subprocess.run([sys.executable, "-c", "import sys, pathlib; d = pathlib.Path(sys.argv[1]);"
                            " (d / 'watch_heartbeat').write_text('now'); (d / 'rule_status.json').write_text('{{1}}')",
                            str({_STORE})], check=True)
        """, False, ("a heartbeat moved", "rule_status.json (changed)")),
    # CI: no ~/.glorfindel at the start, one at the end (HY1's check, kept).
    "none_before_one_after": (None, f"""
        import os, subprocess, sys
        from pathlib import Path
        def test_it():
            subprocess.run([sys.executable, "-c", "import os, sys; os.makedirs(sys.argv[1])", str({_STORE})],
                           check=True)
        """, True, "the test suite wrote outside its sandbox"),
    # Written as the module is imported, its tests all deselected: the end of the session checks.
    "at_collection_no_test_run": ({}, f"""
        import os
        from pathlib import Path
        ({_STORE} / "incidents.jsonl").write_text("x")
        def test_it():
            pass
        """, True, "incidents.jsonl (outside a test)", ("-k", "nothing_matches")),
}


def _operator_repo(tmp: Path, store: dict | None, test: str) -> tuple[Path, Path, Path]:
    repo, real, temp = tmp / "repo", tmp / "operator", tmp / "tmp"
    (repo / "tests" / "unit").mkdir(parents=True)
    for name in ("conftest.py", "hypothesis_seed.py", "home_sandbox.py"):
        shutil.copy(HERE / name, repo / "tests" / "unit" / name)
    (repo / "tests" / "unit" / "test_scenario.py").write_text(textwrap.dedent(test))
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    real.mkdir()
    temp.mkdir()
    if store is not None:
        (real / ".glorfindel").mkdir()
        for name, text in store.items():
            (real / ".glorfindel" / name).write_text(text)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    return repo, real, temp


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_the_guard_fails_a_run_that_writes_in_an_operator_s_store_and_only_then(tmp_path):
    """The operator's folder exists already (a workstation), or not (CI): a test that writes there,
    a subprocess with no Glorfindel running, a module at collection fail the run and say the file;
    an undone monkeypatch writes under the throwaway HOME; a live Glorfindel is said, never a verdict.
    Each run removes its throwaway HOME."""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith("PYTEST_") and k not in (hs.HOME_VAR, hs.REAL_VAR)}
    runs = {}
    for name, (store, test, _, _, *args) in SCENARIOS.items():   # at once: each its own interpreter
        repo, real, temp = _operator_repo(tmp_path / name, store, test)
        env = {**base, "HOME": str(real), "TMPDIR": str(temp), "PYTHONPATH": str(ROOT)}
        runs[name] = (subprocess.Popen(
            [sys.executable, "-m", "pytest", "tests/unit/test_scenario.py", "-q", "-p", "no:randomly",
             "-p", "no:cacheprovider", "-W", "always::pytest.PytestWarning", *(args[0] if args else ())],
            cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True), temp)
    outcomes = {name: (proc.wait(timeout=240), proc.stdout.read(), temp) for name, (proc, temp) in runs.items()}
    for name, (_, _, fails, says, *_) in SCENARIOS.items():
        code, out, temp = outcomes[name]
        assert (code != 0) is fails, f"{name}:\n{out[-3000:]}"
        for said in (says,) if isinstance(says, str) else says:
            assert said in out, f"{name}: {said!r} not said:\n{out[-3000:]}"
        assert not list(temp.glob("eregion-test-home-*")), f"{name}: its throwaway HOME left behind"
