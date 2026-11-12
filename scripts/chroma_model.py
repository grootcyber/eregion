"""CI8 (#566): ChromaDB's embedding model, fetched before the tests that use it.

    python scripts/chroma_model.py          # the CI: bash scripts/retry.sh python scripts/chroma_model.py

A step of its own, before the tests, the mutation or the invariants, so that its download alone is
retried (scripts/retry.sh) — never the tests. ChromaDB's default embedding function, called on a
word, fetches the model (about 80 MB, into ~/.cache/chroma) only when one of its files is missing,
checks the archive's SHA-256, and loads it as a test would (CI6b, scripts/mutation_check.py,
prepare_embedding_model). The cache restored, nothing leaves the runner.

Exits 0 when the model is ready, or when ChromaDB is not installed (nothing to fetch); otherwise
the error, and a non-zero exit, which retry.sh tries again.

FLK1 (#723): one fetch at a time, under a file lock beside the model (`held`). On 11/11, in
`pytest -n 4` with a throwaway HOME, two workers fetched the model into the same ~/.cache/chroma
at once: ChromaDB writes the archive in place, and removes it when its SHA-256 does not match —
one worker removed the other's half-written file, which then failed on it (FileNotFoundError on
onnx.tar.gz). Three places take the lock: this script, the harness's preparation (CI6b), and the
test suite, lazily — tests/unit/conftest.py calls `lock_downloads` in each process, which wraps
ChromaDB's own check-then-fetch (`ONNXMiniLM_L6_V2._download_model_if_not_exists`) in the lock,
when ChromaDB is imported. The first process that needs the model fetches it; the others wait,
then find it by ChromaDB's own check. A session that never embeds a text fetches nothing.
"""
from __future__ import annotations

import contextlib
import functools
import importlib
import os
import sys
import threading
from pathlib import Path

EMBEDDING = "chromadb.utils.embedding_functions"
# Where chromadb keeps its default model: Path.home()/.cache/chroma/onnx_models/<model>
# (ONNXMiniLM_L6_V2.DOWNLOAD_PATH). The lock is beside the models, in onnx_models/.
MODELS = Path(".cache") / "chroma" / "onnx_models"
LOCK = ".eregion-prepare.lock"
# The module, class and method that check the model's files and fetch it when one is missing
# (chromadb 1.5.9) — what the suite wraps in the lock; tests/unit/test_chroma_model.py checks the
# locked version still has them.
TARGET = "chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2"
CLASS = "ONNXMiniLM_L6_V2"
METHOD = "_download_model_if_not_exists"


def lock_dir(home: Path | None = None) -> Path:
    """The folder of the lock: ~/.cache/chroma/onnx_models."""
    return Path(home if home is not None else Path.home()) / MODELS


def _in_process(path: Path) -> dict:
    """This process's hold on the lock at ``path``, shared by every copy of this module (the
    conftest, the harness and a test each load their own, by its path): a thread lock, and how
    deep the hold goes."""
    registry = sys.__dict__.setdefault("_eregion_flk1_locks", {})
    return registry.setdefault(os.path.abspath(path), {"thread": threading.RLock(), "depth": 0})


@contextlib.contextmanager
def held(folder: Path | None = None, say=print):
    """The file lock in ``folder`` (default ~/.cache/chroma/onnx_models): flock, released when the
    process ends, even killed. Without fcntl (not POSIX), no lock. A lock that cannot be taken —
    a cache not writable (one root still owns, from the old image: make fix-state-ownership) — is
    said, and the body runs without it, as before FLK1: never an error of its own.

    Re-entrant in a process: the harness's preparation or CI8's step holds it, then ChromaDB's
    check-then-fetch, wrapped by the suite, asks for it again — a second flock on the same file,
    by another open file description, would wait on itself for ever. The threads of a process
    take it in turn."""
    path = Path(folder if folder is not None else lock_dir()) / LOCK
    mine = _in_process(path)
    with mine["thread"]:
        if mine["depth"]:
            mine["depth"] += 1
            try:
                yield
            finally:
                mine["depth"] -= 1
            return
        mine["depth"] = 1
        try:
            with _flock(path, say):
                yield
        finally:
            mine["depth"] = 0


@contextlib.contextmanager
def _flock(path: Path, say):
    """The lock between processes."""
    try:
        import fcntl
    except ImportError:            # pragma: no cover — the suite runs on Linux and macOS
        yield
        return
    try:
        # Where a link leads, made (HY2: the suite's throwaway HOME links ~/.cache/chroma to the
        # real one, which may not be there yet; through a dangling link, mkdir fails).
        Path(os.path.realpath(path.parent)).mkdir(parents=True, exist_ok=True)
        lock = open(path, "a")
    except OSError as exc:         # said, never a verdict
        say(f"ChromaDB's model: the lock {path} could not be taken ({type(exc).__name__}: {exc}); "
            f"the model is fetched without it, as before FLK1 — two processes may fetch it at once. "
            f"A cache root owns: make fix-state-ownership.")
        lock = None
    if lock is None:               # outside the except: an error of the body is never chained to it
        yield
        return
    with lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def wrap(module, say=print) -> bool:
    """ChromaDB's check-then-fetch, wrapped in the lock: True when wrapped (now or before), False
    when this ChromaDB has no such method — said: its fetches are then not serialized."""
    cls = getattr(module, CLASS, None)
    original = getattr(cls, METHOD, None) if cls is not None else None
    if not callable(original):
        say(f"ChromaDB's model: {CLASS}.{METHOD} is not in {getattr(module, '__name__', module)} — "
            f"this ChromaDB fetches its model unlocked, two processes may fetch it at once; "
            f"see scripts/chroma_model.py (FLK1).")
        return False
    if getattr(original, "_flk1_locked", False):
        return True

    @functools.wraps(original)
    def locked(self, *args, **kwargs):
        with held(Path(self.DOWNLOAD_PATH).parent, say=say):
            return original(self, *args, **kwargs)

    locked._flk1_locked = True
    setattr(cls, METHOD, locked)
    return True


class _ThenWrap:
    """The module's own loader, then `wrap` once it has run."""

    def __init__(self, loader, then):
        self._loader, self._then = loader, then

    def __getattr__(self, name):
        return getattr(self._loader, name)

    def create_module(self, spec):
        return self._loader.create_module(spec)

    def exec_module(self, module):
        self._loader.exec_module(module)
        self._then(module)


class _OnImport:
    """A finder that finds nothing itself: the target's spec as the other finders give it, its
    loader followed by `then`. Once only."""

    def __init__(self, target: str, then):
        self.target, self.then, self.done = target, then, False

    def find_spec(self, name, path=None, target=None):
        if self.done or name != self.target:
            return None
        self.done = True
        for finder in sys.meta_path:
            find = getattr(finder, "find_spec", None)
            if finder is self or find is None:
                continue
            spec = find(name, path, target)
            if spec is not None:
                if spec.loader is not None:
                    spec.loader = _ThenWrap(spec.loader, self.then)
                return spec
        return None


def lock_downloads(say=print, target: str = TARGET) -> bool | None:
    """In this process, ChromaDB's fetches of its model taken under the lock: wrapped now when
    ChromaDB is imported already (True, or False when the method is missing — said), else when
    it is (None: nothing imported here, nothing fetched)."""
    module = sys.modules.get(target)
    if module is not None:
        return wrap(module, say)
    sys.meta_path.insert(0, _OnImport(target, lambda m: wrap(m, say)))
    return None


def fetch() -> bool | None:
    """The model fetched when a file of it is missing, then loaded on a word: True; None when
    ChromaDB is not installed (nothing to fetch). Its error, raised."""
    try:
        functions = importlib.import_module(EMBEDDING)
    except ImportError:
        return None
    functions.DefaultEmbeddingFunction()(["eregion"])
    return True


def main() -> int:
    with held():
        if fetch() is None:
            print("ChromaDB is not installed: no model to fetch")
            return 0
    print("ChromaDB's embedding model: ready in ~/.cache/chroma (CI8)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
