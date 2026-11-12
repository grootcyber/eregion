"""FLK1 (#723): ChromaDB's embedding model, fetched by one process at a time (scripts/chroma_model.py:
`held`, `wrap`, `lock_downloads`; tests/unit/conftest.py, `chroma_model`). Mutants M4790–M4794,
M4810–M4813.

On 11/11, in `pytest -n 4` with a throwaway HOME, two workers fetched the model into the same
~/.cache/chroma at once — test_agent_nodes.py through a real CycleMemory, test_containment.py
through the campaign report's index — and ChromaDB, which writes the archive in place and removes it
when its SHA-256 does not match, removed the other's half-written file: FileNotFoundError on
onnx.tar.gz. The suite now wraps ChromaDB's own check-then-fetch in a file lock, lazily: only a
session that embeds a text fetches the model. Here, no network and no real model: fake ChromaDBs
whose check-then-fetch writes six files in place, slowly, when one is missing — as ChromaDB does.
"""
import fcntl
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import textwrap
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "chroma_model.py"
_spec = importlib.util.spec_from_file_location("chroma_model", SCRIPT)
chroma_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chroma_model)


def test_the_locked_chromadb_has_what_the_suite_wraps_and_this_session_wrapped_it():
    """The guard of a ChromaDB upgrade: the module, the class, the method the suite wraps, and the
    model's place beside the lock (onnx_models/). Imported here, it is wrapped by this session's
    conftest — at import when it came after the fixture, at once when before."""
    pytest.importorskip("chromadb")
    module = importlib.import_module(chroma_model.TARGET)
    cls = getattr(module, chroma_model.CLASS)
    method = getattr(cls, chroma_model.METHOD)
    assert callable(method)
    assert Path(cls.DOWNLOAD_PATH).parent.parts[-3:] == chroma_model.MODELS.parts
    assert getattr(method, "_flk1_locked", False), "this session's fetches of the model are not locked"


def _fake_module(download_path: Path, check):
    module = types.ModuleType("flk1_fake_onnx")

    class ONNXMiniLM_L6_V2:
        DOWNLOAD_PATH = download_path

        def _download_model_if_not_exists(self):
            return check(self)

    module.ONNXMiniLM_L6_V2 = ONNXMiniLM_L6_V2
    return module


def _lock_is_held(folder: Path) -> bool:
    """Another open file description of the lock cannot take it: someone holds it."""
    with open(folder / chroma_model.LOCK, "a") as other:
        try:
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(other, fcntl.LOCK_UN)
        return False


def test_chromadb_s_check_then_fetch_runs_under_the_lock(tmp_path):
    models = tmp_path / ".cache" / "chroma" / "onnx_models"
    seen = []
    module = _fake_module(models / "all-MiniLM-L6-v2", lambda self: seen.append(_lock_is_held(models)) or "ok")
    assert chroma_model.wrap(module) is True
    assert module.ONNXMiniLM_L6_V2()._download_model_if_not_exists() == "ok"
    assert seen == [True]
    assert chroma_model.wrap(module) is True           # wrapped once, never twice (a lock in a lock)
    module.ONNXMiniLM_L6_V2()._download_model_if_not_exists()
    assert seen == [True, True] and not _lock_is_held(models)


def test_a_chromadb_without_the_method_is_said(tmp_path):
    module = types.ModuleType("flk1_fake_onnx")
    module.ONNXMiniLM_L6_V2 = type("ONNXMiniLM_L6_V2", (), {})
    said = []
    assert chroma_model.wrap(module, say=said.append) is False
    assert len(said) == 1 and chroma_model.METHOD in said[0] and "unlocked" in said[0]


def test_chromadb_imported_after_the_fixture_is_wrapped_when_it_is(tmp_path, monkeypatch):
    (tmp_path / "flk1_later_onnx.py").write_text(textwrap.dedent("""
        class ONNXMiniLM_L6_V2:
            DOWNLOAD_PATH = None

            def _download_model_if_not_exists(self):
                return "checked"
    """))
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "flk1_later_onnx", raising=False)
    before = list(sys.meta_path)
    try:
        assert chroma_model.lock_downloads(target="flk1_later_onnx") is None     # not imported yet
        module = importlib.import_module("flk1_later_onnx")
        assert getattr(module.ONNXMiniLM_L6_V2._download_model_if_not_exists, "_flk1_locked", False)
        assert module.ONNXMiniLM_L6_V2.__module__ == "flk1_later_onnx"
    finally:
        sys.meta_path[:] = before
        sys.modules.pop("flk1_later_onnx", None)


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes anywhere")
def test_a_cache_that_is_not_writable_is_said_and_chromadb_goes_on_as_before(tmp_path):
    """A ~/.cache/chroma root still owns (the old image: make fix-state-ownership): the lock cannot
    be made. Said; ChromaDB's own check runs as before FLK1 — the model there, nothing more; the
    model missing, ChromaDB's own error, never the lock's."""
    cache = tmp_path / ".cache" / "chroma"
    present = cache / "onnx_models" / "all-MiniLM-L6-v2"
    present.mkdir(parents=True)
    said = []

    def check(self):
        if not Path(self.DOWNLOAD_PATH).exists():
            raise PermissionError("chromadb's own: cannot make the model's folder")
        return "there"

    there = _fake_module(present, check)
    assert chroma_model.wrap(there, say=said.append)
    absent = _fake_module(tmp_path / "ro" / "onnx_models" / "all-MiniLM-L6-v2", check)
    assert chroma_model.wrap(absent, say=said.append)
    (tmp_path / "ro").mkdir()
    os.chmod(present.parent, 0o555)
    os.chmod(tmp_path / "ro", 0o555)
    try:
        assert there.ONNXMiniLM_L6_V2()._download_model_if_not_exists() == "there"
        assert len(said) == 1 and "could not be taken" in said[0]
        with pytest.raises(PermissionError, match="chromadb's own"):
            absent.ONNXMiniLM_L6_V2()._download_model_if_not_exists()
        assert len(said) == 2 and "could not be taken" in said[1]
    finally:
        os.chmod(present.parent, 0o755)
        os.chmod(tmp_path / "ro", 0o755)


_WAITER = textwrap.dedent("""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("chroma_model", sys.argv[1])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    print("started", flush=True)
    with m.held(sys.argv[2]):
        open(sys.argv[3], "a").write("in\\n")
    print("done", flush=True)
""")


def test_a_second_process_waits_for_the_one_that_holds_the_lock(tmp_path):
    """While one process holds the lock (fetching the model), another waits — never fetches beside
    it. A handshake, not a guess: the parent waits for the child's « started », said just before it
    asks for the lock."""
    folder, log = tmp_path / "onnx_models", tmp_path / "in.log"
    with chroma_model.held(folder):
        proc = subprocess.Popen([sys.executable, "-c", _WAITER, str(SCRIPT), str(folder), str(log)],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            assert proc.stdout.readline().strip() == "started"
            time.sleep(0.5)
            assert proc.poll() is None and not log.exists(), "did not wait for the lock"
        except BaseException:
            proc.kill()
            raise
    out, _ = proc.communicate(timeout=60)
    assert proc.returncode == 0 and out.strip() == "done", out
    assert log.read_text() == "in\n"


_NESTED = textwrap.dedent("""
    import importlib.util, sys
    def load(name):
        spec = importlib.util.spec_from_file_location(name, sys.argv[1])
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    harness, suite = load("as_the_harness_loads_it"), load("as_the_conftest_loads_it")
    with harness.held(sys.argv[2]):
        with suite.held(sys.argv[2]):
            print("nested", flush=True)
""")


def test_a_process_that_holds_the_lock_takes_it_again_without_waiting_on_itself(tmp_path):
    """The harness's preparation (or CI8's step) holds the lock, then ChromaDB's check-then-fetch,
    wrapped by the suite, asks for it again — each by its own copy of the module. A second flock on
    another open file description would wait on itself for ever: seen when this lot first ran
    test_mutation_shards.py."""
    proc = subprocess.run([sys.executable, "-c", _NESTED, str(SCRIPT), str(tmp_path / "onnx_models")],
                          capture_output=True, text=True, timeout=20)   # waiting on itself: killed here
    assert proc.returncode == 0 and proc.stdout.strip() == "nested", proc.stdout + proc.stderr


# A fake ChromaDB: its check-then-fetch, as chromadb 1.5.9's, fetches the model when one of its six
# files is missing, writing each in place, slowly (about 1.5 s in all); its embedding reads them back
# — a half-written one is an error.
_FAKE_ONNX = textwrap.dedent('''
    import os
    import time
    from pathlib import Path

    FILES = ("config.json", "model.onnx", "special_tokens_map.json", "tokenizer_config.json",
             "tokenizer.json", "vocab.txt")


    class ONNXMiniLM_L6_V2:
        DOWNLOAD_PATH = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"

        def __call__(self, input):
            self._download_model_if_not_exists()
            for f in FILES:
                if not (self.DOWNLOAD_PATH / "onnx" / f).read_text().endswith("END"):
                    raise RuntimeError(f"{f}: half-written")
            return [[0.0] for _ in input]

        def _download_model_if_not_exists(self):
            here = self.DOWNLOAD_PATH / "onnx"
            if all((here / f).exists() for f in FILES):
                return
            with open(os.environ["FAKE_CHROMA_LOG"], "a") as log:
                log.write(f"fetched by {os.getpid()}\\n")
            here.mkdir(parents=True, exist_ok=True)
            for f in FILES:
                with open(here / f, "w") as out:
                    for _ in range(5):
                        out.write("x" * 10)
                        out.flush()
                        time.sleep(0.05)
                    out.write("END")
''')
_FAKE_FUNCTIONS = textwrap.dedent('''
    class DefaultEmbeddingFunction:
        def __call__(self, input):
            from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
            return ONNXMiniLM_L6_V2()(input)
''')

# Each worker's first test waits for the three to be there, then all embed at once: unlocked, all
# three find the model missing and fetch it — every time, not by chance.
_SCENARIO = textwrap.dedent('''
    import os
    import time
    from pathlib import Path

    import pytest

    _met = []


    def _all_three_here():
        if _met:
            return
        barrier = Path(os.environ["FAKE_CHROMA_BARRIER"])
        (barrier / os.environ.get("PYTEST_XDIST_WORKER", "main")).touch()
        deadline = time.monotonic() + 30
        while len(list(barrier.iterdir())) < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        _met.append(1)


    @pytest.mark.parametrize("n", range(6))
    def test_it_embeds(n):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        _all_three_here()
        assert DefaultEmbeddingFunction()(["eregion"]) == [[0.0]]
''')
_NO_EMBEDDING = "def test_it_embeds_nothing():\n    assert True\n"


def _session(tmp_path, scenario: str, *args) -> tuple[subprocess.CompletedProcess, Path]:
    """A session of the suite's conftest, in a throwaway repository, on a fake ChromaDB, with an
    empty HOME."""
    repo, home, fake, barrier = (tmp_path / n for n in ("repo", "home", "fake", "barrier"))
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "scripts").mkdir()
    home.mkdir()
    barrier.mkdir()
    for rel in ("tests/unit/conftest.py", "tests/unit/hypothesis_seed.py", "tests/unit/home_sandbox.py",
                "scripts/chroma_model.py"):
        shutil.copy(ROOT / rel, repo / rel)
    (repo / "tests" / "unit" / "test_scenario.py").write_text(scenario)
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    functions = fake / "chromadb" / "utils" / "embedding_functions"
    functions.mkdir(parents=True)
    (fake / "chromadb" / "__init__.py").write_text("")
    (fake / "chromadb" / "utils" / "__init__.py").write_text("")
    (functions / "__init__.py").write_text(_FAKE_FUNCTIONS)
    (functions / "onnx_mini_lm_l6_v2.py").write_text(_FAKE_ONNX)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    log = tmp_path / "fetched.log"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(HOME=str(home), FAKE_CHROMA_LOG=str(log), FAKE_CHROMA_BARRIER=str(barrier),
               PYTHONPATH=os.pathsep.join([str(fake), str(ROOT)]))
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/test_scenario.py", "-q",
                           "-p", "no:randomly", "-p", "no:cacheprovider", *args],
                          cwd=repo, env=env, capture_output=True, text=True, timeout=180)
    return proc, log


def test_workers_that_embed_at_once_fetch_the_model_once(tmp_path):
    """The defect, as it was: three workers, an empty HOME, each embedding a text at the same
    moment. Under the conftest's lock, the first fetches the model, the others wait, then find it."""
    pytest.importorskip("xdist")
    proc, log = _session(tmp_path, _SCENARIO, "-n", "3", "--dist", "load")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0 and "6 passed" in out, out[-3000:]
    assert len(log.read_text().splitlines()) == 1, log.read_text()


def test_a_session_that_embeds_nothing_fetches_nothing(tmp_path):
    """Lazily: a session whose tests never embed a text (a CI job without the model's cache, a
    local run of a few files) never fetches the model, nor goes out."""
    proc, log = _session(tmp_path, _NO_EMBEDDING)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0 and "1 passed" in out, out[-3000:]
    assert not log.exists() and not (tmp_path / "home" / ".cache").exists()
