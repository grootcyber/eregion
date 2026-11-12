"""HY2 (#769): the suite's throwaway HOME, and the photograph of the operator's ~/.glorfindel.

On 12/11, two tests wrote in the real ~/.glorfindel of the operator's workstation: DRN2's
vm_notices.jsonl, before its redirection was set; JUG2's bot_heartbeat.json, by a
`monkeypatch.undo()` that undid the conftest's redirection too. HY1's guard saw a write there only
where the folder did not exist when the suite started — a CI runner, never a workstation.

Now, as tests/unit/conftest.py is imported, before any module of the repository is (`enter`):

- HOME is a throwaway folder, made for the session: every path a module computes from it at its
  import (``Path.home() / ".glorfindel" / …``) lies under it, and so does every path a test, a
  forgotten redirection or an undone monkeypatch computes later — the subprocesses of the suite
  inherit it. The XDG_* folders of the operator's shell are dropped (they default under HOME).
  One thing is kept, by a link: ChromaDB's embedding model (`KEPT`, ~/.cache/chroma, some 80 MB
  fetched once — CI8, CI6b, FLK1), which a test that embeds a text loads; through the link it
  stays where the CI restores it and where it was fetched before. Nothing else of the real HOME
  is joinable through the throwaway one: no ~/.glorfindel, ~/.config, ~/.ssh, ~/.gitconfig.
- The operator's HOME, as it was, is kept in `REAL_VAR`; the throwaway one in `HOME_VAR`. A
  process that inherits both, its HOME still the throwaway one (an xdist worker of a controller
  that loaded this conftest, a pytest a test starts), uses them as they are; any other (a pytest
  a test starts with a HOME of its own) takes its HOME as the operator's and makes its own.
- The process that made the folder removes it when it is done (`leave`, at the session's end,
  and at its exit): the link removed, never what it points to.

The guard itself is in the conftest (`nothing_written_in_the_operators_store`): this module
gives it the photograph of a folder (names, sizes, dates — never a file's content) and its
changes.

If a module of the repository is imported before this conftest (a plugin, a script that imports
one, then runs pytest in its own interpreter), its paths were computed from the real HOME: the
session refuses to start (`Early`), it says which.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import NamedTuple

HOME_VAR = "EREGION_TEST_HOME"
REAL_VAR = "EREGION_TEST_REAL_HOME"
XDG = ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")
# What the throwaway HOME links to the real one, and why: ChromaDB's model, fetched once (CI8).
KEPT = (Path(".cache") / "chroma",)
STORE = ".glorfindel"
FIRST_PARTY = ("eregion_core", "glorfindel", "annatar", "gothmog", "eregion_console", "analysis")
# What a live Glorfindel of the workstation rewrites as it runs, every few seconds: the watch's
# heartbeat (eregion_core/watch_gate.py), its copy for the injectors, the bot's (glorfindel/bot_beat.py).
HEARTBEATS = ("watch_heartbeat", os.path.join("injectors", "watch_heartbeat"), "bot_heartbeat.json")


class Early(RuntimeError):
    """A module of the repository was imported before the throwaway HOME was set."""


class Sandbox(NamedTuple):
    """A plain tuple: this module is loaded by its path, outside sys.modules (no dataclass)."""
    home: Path       # the throwaway HOME
    real: Path       # the operator's HOME, as the session found it
    made: bool       # made by this process, which removes it

    @property
    def store(self) -> Path:
        """The operator's ~/.glorfindel."""
        return self.real / STORE


def enter(environ=None, modules=None, tmp: str | None = None) -> Sandbox:
    """HOME made a throwaway folder in ``environ`` (os.environ), or the one this run made already."""
    environ = os.environ if environ is None else environ
    if modules is None:
        import sys
        modules = sys.modules
    current = environ.get("HOME") or os.path.expanduser("~")
    mine, real = environ.get(HOME_VAR), environ.get(REAL_VAR)
    if mine and real and mine == current and os.path.isdir(mine):
        return Sandbox(Path(mine), Path(real), made=False)
    early = sorted(m for m in modules if m.split(".")[0] in FIRST_PARTY)
    if early:
        raise Early("HY2: modules of the repository imported before the test suite's throwaway HOME "
                    f"was set — their paths may name the real ~/{STORE}: {', '.join(early[:8])}")
    home = Path(tempfile.mkdtemp(prefix="eregion-test-home-", dir=tmp))
    for rel in KEPT:
        _link(Path(current) / rel, home / rel)
    environ["HOME"] = str(home)
    environ[HOME_VAR] = str(home)
    environ[REAL_VAR] = current
    for name in XDG:
        environ.pop(name, None)
    return Sandbox(home, Path(current), made=True)


def _link(target: Path, link: Path) -> None:
    """``link`` to ``target``, whether the target exists or not: never made here (a session that
    embeds nothing makes no ~/.cache). ChromaDB's fetch, under FLK1's lock, makes it first
    (scripts/chroma_model.py, `_flock` makes the lock's folder where the link leads), where it was
    made before HY2. A link that cannot be made: none — the throwaway HOME keeps its own, empty."""
    try:
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        pass


def leave(sandbox: Sandbox, environ=None) -> None:
    """The throwaway HOME removed by the process that made it (its links, never their targets),
    and HOME the operator's again in ``environ`` (the XDG_* it dropped stay dropped)."""
    if not sandbox.made or not sandbox.home.exists():
        return
    environ = os.environ if environ is None else environ
    shutil.rmtree(sandbox.home, ignore_errors=True)
    if environ.get("HOME") == str(sandbox.home):
        environ["HOME"] = str(sandbox.real)
    for name in (HOME_VAR, REAL_VAR):
        environ.pop(name, None)


def photograph(root: Path) -> dict[str, tuple[int, int]] | None:
    """Every file and folder under ``root`` (links not followed): its path relative to ``root``,
    its size and its mtime (ns). Never a file's content. None when ``root`` does not exist."""
    root = Path(root)
    if not root.is_dir():
        return None
    shot: dict[str, tuple[int, int]] = {}
    for top, dirs, files in os.walk(root, onerror=lambda e: None):
        for name in dirs + files:
            path = os.path.join(top, name)
            try:
                st = os.lstat(path)
            except OSError:
                continue
            shot[os.path.relpath(path, root)] = (-1 if name in dirs else st.st_size, st.st_mtime_ns)
    return shot


def changes(before: dict | None, after: dict | None) -> list[str]:
    """What changed between two photographs: each path, created, changed or removed."""
    before, after = before or {}, after or {}
    out = [f"{rel} (created)" for rel in after if rel not in before]
    out += [f"{rel} (changed)" for rel in after if rel in before and after[rel] != before[rel]
            and after[rel][0] != -1]     # a folder's mtime moves with its files: they are said
    out += [f"{rel} (removed)" for rel in before if rel not in after]
    return sorted(out)


def a_glorfindel_lives(before: dict | None, after: dict | None) -> bool:
    """True when one of a live Glorfindel's heartbeats moved between the two photographs: a watch
    or a bot of the workstation wrote in the folder while the suite ran."""
    before, after = before or {}, after or {}
    return any(before.get(rel) != after.get(rel) for rel in HEARTBEATS if rel in before or rel in after)


def inside(path, roots: tuple[str, ...]) -> str | None:
    """``path`` (as given, made absolute) relative to the one of ``roots`` it lies under ("." for
    the root itself), or None."""
    if isinstance(path, int) or path is None:
        return None
    try:
        full = os.path.abspath(os.fsdecode(path))
    except (TypeError, ValueError):
        return None
    for root in roots:
        if full == root:
            return "."
        if full.startswith(root + os.sep):
            return full[len(root) + 1:]
    return None


def roots_of(store: Path) -> tuple[str, ...]:
    """The store as given, and resolved (a HOME reached through a link)."""
    given = os.path.abspath(store)
    return tuple(dict.fromkeys((given, os.path.realpath(given))))
