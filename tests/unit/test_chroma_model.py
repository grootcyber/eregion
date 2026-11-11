"""FLK1 (#723): ChromaDB's embedding model, made ready once per test session (scripts/chroma_model.py,
`prepare_once`; tests/unit/conftest.py, `chroma_model`). Mutants M4790–M4794.

On 11/11, in `pytest -n 4` with a throwaway HOME, two workers fetched the model into the same
~/.cache/chroma at once — test_agent_nodes.py through a real CycleMemory, test_containment.py
through the campaign report's index — and ChromaDB, which writes the archive in place and removes it
when its SHA-256 does not match, removed the other's half-written file: FileNotFoundError on
onnx.tar.gz. Here, no network and no real model: a fake ``chromadb`` whose embedding writes its six
files in place, slowly, when one is missing — as ChromaDB does.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "chroma_model.py"
_spec = importlib.util.spec_from_file_location("chroma_model", SCRIPT)
chroma_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chroma_model)


def _model(home: Path, files=chroma_model.FILES) -> None:
    folder = chroma_model.model_dir(home)
    folder.mkdir(parents=True, exist_ok=True)
    for name in files:
        (folder / name).write_text("END")


def _never():
    raise AssertionError("fetched: the model was there")


def test_a_model_already_there_is_neither_fetched_nor_loaded(tmp_path, monkeypatch):
    """Without a network: the six files there, nothing is imported, nothing goes out."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _model(tmp_path)
    assert chroma_model.ready() and chroma_model.prepare_once(fetch=_never) is True


@pytest.mark.parametrize("missing", chroma_model.FILES)
def test_a_model_missing_one_of_its_files_is_fetched(tmp_path, monkeypatch, missing):
    """ChromaDB fetches the model when any of its six files is missing: so does the preparation."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _model(tmp_path, [f for f in chroma_model.FILES if f != missing])
    fetched = []
    assert not chroma_model.ready()
    assert chroma_model.prepare_once(fetch=lambda: fetched.append(1) or True) is True
    assert fetched == [1]


def test_a_preparation_that_fails_is_said_never_raised(tmp_path, monkeypatch):
    """No network: said, with its error — the tests that embed then fail on their own, as before."""
    monkeypatch.setenv("HOME", str(tmp_path))
    said = []

    def offline():
        raise OSError("no network")

    assert chroma_model.prepare_once(say=said.append, fetch=offline) is False
    assert len(said) == 1 and "could not be prepared" in said[0] and "OSError: no network" in said[0]


_WAITER = textwrap.dedent("""
    import importlib.util, os, sys
    spec = importlib.util.spec_from_file_location("chroma_model", sys.argv[1])
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    def fetch():
        open(sys.argv[2], "a").write("fetched\\n")
        return True

    print(m.prepare_once(fetch=fetch))
""")


def test_a_second_process_waits_for_the_first_then_finds_the_model_there(tmp_path):
    """The lock: while one process prepares the model, another waits — never fetches it beside it —
    then looks again, under the lock, and finds it there: nothing fetched twice."""
    home, log = tmp_path / "home", tmp_path / "fetched.log"
    home.mkdir()
    env = {**os.environ, "HOME": str(home)}
    with chroma_model.held(home):
        proc = subprocess.Popen([sys.executable, "-c", _WAITER, str(SCRIPT), str(log)], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            time.sleep(1.5)
            assert proc.poll() is None, f"did not wait for the lock: {proc.stdout.read()}"
            assert not log.exists(), "fetched while the first process held the lock"
            _model(home)          # the first process's preparation, done
        except BaseException:
            proc.kill()
            raise
    out, _ = proc.communicate(timeout=60)
    assert proc.returncode == 0 and out.strip() == "True", out
    assert not log.exists(), "fetched again, the model there"


# A fake ChromaDB: its embedding fetches the model when one of its six files is missing, writing
# each in place, slowly (about 1.5 s in all), and reads them back — a half-written one is an error.
_FAKE = textwrap.dedent('''
    import os
    import time
    from pathlib import Path

    FILES = ("config.json", "model.onnx", "special_tokens_map.json", "tokenizer_config.json",
             "tokenizer.json", "vocab.txt")


    def folder():
        return Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2" / "onnx"


    class DefaultEmbeddingFunction:
        def __call__(self, input):
            here = folder()
            if not all((here / f).exists() for f in FILES):
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
            for f in FILES:
                if not (here / f).read_text().endswith("END"):
                    raise RuntimeError(f"{f}: half-written")
            return [[0.0] for _ in input]
''')

_SCENARIO = textwrap.dedent('''
    import pytest
    from pathlib import Path

    FILES = ("config.json", "model.onnx", "special_tokens_map.json", "tokenizer_config.json",
             "tokenizer.json", "vocab.txt")


    @pytest.mark.parametrize("n", range(6))
    def test_it_embeds(n):
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        here = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2" / "onnx"
        assert all((here / f).exists() for f in FILES), "the model was not ready before the test"
        assert DefaultEmbeddingFunction()(["eregion"]) == [[0.0]]
''')


def test_the_suite_prepares_the_model_once_before_its_tests_with_workers_in_parallel(tmp_path):
    """The defect, as it was: a session in `-n 3`, an empty HOME, every test embedding a text.
    With the conftest's preparation, the model is there before each test, and fetched once."""
    pytest.importorskip("xdist")
    repo, home, fake = tmp_path / "repo", tmp_path / "home", tmp_path / "fake"
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "scripts").mkdir()
    home.mkdir()
    for rel in ("tests/unit/conftest.py", "tests/unit/hypothesis_seed.py", "scripts/chroma_model.py"):
        shutil.copy(ROOT / rel, repo / rel)
    (repo / "tests" / "unit" / "test_scenario.py").write_text(_SCENARIO)
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    package = fake / "chromadb" / "utils"
    package.mkdir(parents=True)
    (fake / "chromadb" / "__init__.py").write_text("")
    (package / "__init__.py").write_text("")
    (package / "embedding_functions.py").write_text(_FAKE)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    log = tmp_path / "fetched.log"
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(HOME=str(home), FAKE_CHROMA_LOG=str(log), PYTHONPATH=os.pathsep.join([str(fake), str(ROOT)]))
    proc = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/test_scenario.py", "-q", "-n", "3",
                           "-p", "no:randomly", "-p", "no:cacheprovider"],
                          cwd=repo, env=env, capture_output=True, text=True, timeout=180)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out[-3000:]
    assert "6 passed" in out, out[-3000:]
    assert len(log.read_text().splitlines()) == 1, log.read_text()

