"""CI8 (#566): ChromaDB's embedding model, fetched before the tests that use it.

    python scripts/chroma_model.py          # the CI: bash scripts/retry.sh python scripts/chroma_model.py

A step of its own, before the tests, the mutation or the invariants, so that its download alone is
retried (scripts/retry.sh) — never the tests. ChromaDB's default embedding function, called on a
word, fetches the model (about 80 MB, into ~/.cache/chroma) only when one of its files is missing,
checks the archive's SHA-256, and loads it as a test would (CI6b, scripts/mutation_check.py,
prepare_embedding_model). The cache restored, nothing leaves the runner.

Exits 0 when the model is ready, or when ChromaDB is not installed (nothing to fetch); otherwise
the error, and a non-zero exit, which retry.sh tries again.

FLK1 (#723): the test suite prepares it too, once per session (`prepare_once`, called by
tests/unit/conftest.py in each process, xdist's workers included), under a file lock beside the
model. On 11/11, in `pytest -n 4` with a throwaway HOME, two workers fetched it into the same
~/.cache/chroma at once: ChromaDB writes the archive in place, and removes it when its SHA-256
does not match — one worker removed the other's half-written file, which then failed on it
(FileNotFoundError on onnx.tar.gz). Under the lock, the first process fetches it, the others
wait, then find it there; a model already there is never fetched again (no network).
"""
from __future__ import annotations

import contextlib
import importlib
import sys
from pathlib import Path

EMBEDDING = "chromadb.utils.embedding_functions"
# Where chromadb 1.5.9 keeps its default model (ONNXMiniLM_L6_V2: DOWNLOAD_PATH, taken from
# Path.home() when it is imported), and the six files whose absence makes it fetch the model.
MODEL = Path(".cache") / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
FILES = ("config.json", "model.onnx", "special_tokens_map.json", "tokenizer_config.json",
         "tokenizer.json", "vocab.txt")
LOCK = ".eregion-prepare.lock"


def model_dir(home: Path | None = None) -> Path:
    """The folder of the model's files (the archive's ``onnx/``, extracted)."""
    return Path(home if home is not None else Path.home()) / MODEL / "onnx"


def ready(home: Path | None = None) -> bool:
    """The model there, as ChromaDB sees it: its six files, every one of them."""
    folder = model_dir(home)
    return all((folder / name).exists() for name in FILES)


@contextlib.contextmanager
def held(home: Path | None = None):
    """The file lock beside the model (flock: released when the process ends, even killed). The
    processes that prepare the model take it in turn; without fcntl (not POSIX), no lock."""
    try:
        import fcntl
    except ImportError:            # pragma: no cover — the suite runs on Linux and macOS
        yield
        return
    path = Path(home if home is not None else Path.home()) / MODEL.parent / LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def fetch() -> bool | None:
    """The model fetched when a file of it is missing, then loaded on a word: True; None when
    ChromaDB is not installed (nothing to fetch). Its error, raised."""
    try:
        functions = importlib.import_module(EMBEDDING)
    except ImportError:
        return None
    functions.DefaultEmbeddingFunction()(["eregion"])
    return True


def prepare_once(say=print, fetch=fetch) -> bool | None:
    """The model made ready by one process at a time, under the lock: True when it is there
    (already: nothing imported, nothing goes out; or fetched now), None when ChromaDB is not
    installed, False when it could not be fetched — said, with its error, never raised: the
    tests that need it fail on their own error, as before (CI6b)."""
    with held():
        if ready():
            return True
        try:
            return fetch()
        except Exception as exc:   # said, never a verdict
            say(f"ChromaDB's embedding model could not be prepared before the tests "
                f"({type(exc).__name__}: {exc}). The tests that embed a text fetch it themselves, "
                f"and fail on it if it cannot be. Without a network, put it in ~/.cache/chroma "
                f"first; if it is there but unreadable, remove ~/.cache/chroma/onnx_models (FLK1).")
            return False


def main() -> int:
    with held():
        if fetch() is None:
            print("ChromaDB is not installed: no model to fetch")
            return 0
    print("ChromaDB's embedding model: ready in ~/.cache/chroma (CI8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
