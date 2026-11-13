"""HY2b (#791): a probe of an agent session never writes in the operator's real ~/.glorfindel.

HY2 (#769) holds the suite: tests/unit/conftest.py makes HOME a throwaway folder and watches the real
~/.glorfindel. A probe launched outside the suite escapes both: on 12/11, 52 probes run from a file
placed outside tests/unit/ wrote three files of a test there (vm_notices.jsonl and its lock, a
restore job's lock). The rule was in the prompts; nothing held it.

Now, as eregion_core is imported (glorfindel/__init__.py and eregion_console/__init__.py import it
first), in an agent session only, an audit hook refuses every write under the operator's real
~/.glorfindel before it happens, and says it on stderr (once per path) — a PermissionError, which
Glorfindel's code meets as it meets a read-only disk.

- **An agent session**: EREGION_AGENT_SESSION set (the repository's settings give it to every session
  of Claude Code launched in ~/eregion, and to the sub-agents they start — docs/sessions.md, SEC12), or
  a current folder in a lot's worktree (.claude/worktrees/) — the rule of scripts/bench_shared.py's
  `session_refusal`. Anywhere else (the operator's terminal, his containers, the watch, Imladris, the
  CI) nothing is installed: no hook, no cost, every write as before.
- **The operator's ~/.glorfindel**: under the home the system gives the user (pwd), whatever HOME
  says — as given and resolved. A probe with a throwaway HOME (HOME=$(mktemp -d)) writes in its own;
  the suite's throwaway HOME (HY2) is one too.
- **A write**: what HY1's audit sees (tests/unit/conftest.py, `_written`), plus chmod and chown — a
  file opened for writing (open, pathlib, os.open), a folder made or removed, a file removed, renamed
  or replaced, a link made, its times, size or mode changed, shutil.rmtree, sqlite3.connect. A path is
  placed as given and resolved (a link into the folder is seen). A mkdir of a folder that is there
  writes nothing: left to fail by itself (os.makedirs(exist_ok=True)).

Not seen (a guard against error, never against a session that wants to: the same Unix user): what a C
or Rust library writes once its file is open, or by itself (sqlite's pages, ChromaDB 1.x's store, a
write through a descriptor, mmap); a path relative to a dir_fd; a process that imports no module of
the repository (a shell's `>`, a script of its own); a session launched without the repository's
settings and outside a worktree.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

STORE = ".glorfindel"
SESSION_VAR = "EREGION_AGENT_SESSION"
DOC = "docs/operations.md, « Une sonde d'agent n'écrit jamais dans le vrai ~/.glorfindel »"

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
# The audit events of a write other than `open`: the positions of the paths written, then of the
# dir_fd arguments. A path relative to a dir_fd cannot be placed: skipped (HY1's table, and chmod, chown).
_EVENTS = {
    "os.mkdir": ((0,), (2,)),
    "os.rmdir": ((0,), (1,)),
    "os.remove": ((0,), (1,)),              # os.unlink too
    "os.rename": ((0, 1), (2, 3)),          # os.replace, shutil.move on one file system
    "os.symlink": ((1,), (2,)),
    "os.link": ((1,), (2, 3)),
    "os.utime": ((0,), (3,)),               # Path.touch() on a file that exists
    "os.truncate": ((0,), ()),
    "os.chmod": ((0,), (2,)),
    "os.chown": ((0,), (3,)),
    "shutil.rmtree": ((0,), ()),
    "sqlite3.connect": ((0,), ()),          # it may create the file
}
_WATCHED = frozenset(_EVENTS) | {"open"}

# Once installed: why, and the roots it guards. One hook per interpreter, never removed.
_installed: dict = {}
_said: set = set()


class Refused(PermissionError):
    """A write in the operator's ~/.glorfindel, refused in an agent session (HY2b)."""


def why_guarded(env=None, cwd=None) -> str:
    """Why this process is an agent session's, or '' (the operator's: nothing is guarded)."""
    env = os.environ if env is None else env
    if env.get(SESSION_VAR):
        return f"une session d'agent ({SESSION_VAR})"
    try:
        parts = Path(cwd or os.getcwd()).resolve().parts
    except OSError:   # a current folder removed
        return ""
    if ".claude" in parts and "worktrees" in parts[parts.index(".claude"):]:
        return "le worktree d'un lot (.claude/worktrees/)"
    return ""


def operator_home() -> Path:
    """The home the system gives this user, whatever HOME says (a probe's throwaway HOME, the suite's)."""
    try:
        import pwd
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, OSError):   # no passwd entry (a container's UID): HOME then
        return Path(os.path.expanduser("~"))


def roots_of(home) -> tuple[str, ...]:
    """The operator's ~/.glorfindel, as given and resolved (a home reached through a link)."""
    given = os.path.abspath(os.path.join(os.fspath(home), STORE))
    return tuple(dict.fromkeys((given, os.path.realpath(given))))


def written(event: str, args) -> list:
    """The paths an audit event writes (created, changed, renamed or removed), as given."""
    if event == "open":
        path, mode, flags = args
        writes = any(c in mode for c in "wax+") if isinstance(mode, str) else bool((flags or 0) & _WRITE_FLAGS)
        return [path] if writes else []
    if event not in _EVENTS:
        return []
    paths, dir_fds = _EVENTS[event]
    if any(args[i] not in (None, -1) for i in dir_fds if i < len(args)):
        return []
    if event == "sqlite3.connect":
        db = args[0]
        if not isinstance(db, (str, bytes, os.PathLike)):
            return []
        db = os.fsdecode(db)
        if db.startswith("file:"):
            db = db[5:].split("?")[0]
        return [] if db in ("", ":memory:") else [db]
    found = [args[i] for i in paths if i < len(args)]
    if event == "os.mkdir":   # a folder that is there: nothing written, mkdir fails by itself
        found = [p for p in found if not (isinstance(p, (str, bytes, os.PathLike)) and os.path.isdir(p))]
    return found


def placed(path, roots: tuple[str, ...]) -> str | None:
    """``path`` made absolute, when it lies in one of ``roots`` (the root itself included), as given
    or resolved; else None."""
    if path is None or isinstance(path, int):
        return None
    try:
        full = os.path.abspath(os.fsdecode(path))
    except (TypeError, ValueError):
        return None
    for candidate in dict.fromkeys((full, os.path.realpath(full))):
        for root in roots:
            if candidate == root or candidate.startswith(root + os.sep):
                return full
    return None


def refusal(event: str, args, roots: tuple[str, ...], why: str) -> str | None:
    """What is said of this event when it writes in ``roots``, or None."""
    for path in written(event, args):
        full = placed(path, roots)
        if full is not None:
            return (f"HY2b : écriture refusée dans le ~/{STORE} de l'opérateur ({full}) — {why}. "
                    "Une sonde prend un HOME jetable (HOME=$(mktemp -d) python …) ou va dans la suite "
                    f"(tests/unit/) ; {DOC}.")
    return None


def _hook(event, args):
    if event not in _WATCHED:
        return
    said = refusal(event, args, _installed["roots"], _installed["why"])
    if said is None:
        return
    if said not in _said:
        _said.add(said)
        try:
            sys.stderr.write(said + "\n")
            sys.stderr.flush()
        except Exception:   # a closed stderr: the exception still says it
            pass
    raise Refused(said)


def install(env=None, cwd=None, home=None) -> str:
    """The guard installed in an agent session's process: why, or '' (the operator's: nothing)."""
    if _installed:
        return _installed["why"]
    why = why_guarded(env, cwd)
    if not why:
        return ""
    _installed.update(why=why, roots=roots_of(operator_home() if home is None else home))
    sys.addaudithook(_hook)
    return why


def guarded() -> tuple[str, ...]:
    """The roots this process guards: none outside an agent session."""
    return tuple(_installed.get("roots", ()))
