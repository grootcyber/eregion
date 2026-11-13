"""HY2b (#791), HY2c (#800): a probe of an agent session never writes in the operator's real
~/.glorfindel, ~/.eregion or ~/.annatar.

HY2 (#769) holds the suite: tests/unit/conftest.py makes HOME a throwaway folder and watches the real
~/.glorfindel. A probe launched outside the suite escapes both: on 12/11, 52 probes run from a file
placed outside tests/unit/ wrote three files of a test there (vm_notices.jsonl and its lock, a
restore job's lock). The rule was in the prompts; nothing held it.

Now, as eregion_core is imported (glorfindel/__init__.py and eregion_console/__init__.py import it
first), in an agent session only, an audit hook refuses every write under the operator's real
~/.glorfindel, ~/.eregion and ~/.annatar (`STORES`) before it happens, and says it on stderr (once per
path), naming the folder refused — a PermissionError, which Glorfindel's code meets as it meets a
read-only disk. ~/.eregion holds the watch's signing key (watch-key/, drawn when absent), the queue's
service keys (console/, bot/) and the queue itself (watch-queue/), the console's token, its requests
and its drills, the analysis index; ~/.annatar, Annatar's shell (HY2c, Jonathan's decision of 13/11).

- **An agent session**: EREGION_AGENT_SESSION set (the repository's settings give it to every session
  of Claude Code launched in ~/eregion, and to the sub-agents they start — docs/sessions.md, SEC12), a
  current folder in a lot's worktree (.claude/worktrees/), or code that runs from one (this module's
  file there) — the rule of scripts/bench_shared.py's `session_refusal`. Anywhere else (the
  operator's terminal, his containers, the watch, the bot, Imladris, the CI) nothing is installed:
  no hook, no cost, every write as before. Leaving the worktree is never a way out offered to a
  probe (HY2c): refused for its current folder, the line says it to the operator alone — who may
  have run the command by hand from a worktree — and says that a probe has no such way.
- **The operator's folders**: ~/.glorfindel, ~/.eregion and ~/.annatar under the home the system
  gives the user (pwd), whatever HOME says — as given and resolved. A probe with a throwaway HOME
  (HOME=$(mktemp -d)) writes in its own; the suite's throwaway HOME (HY2) is one too.
- **A write**: what HY1's audit sees (tests/unit/conftest.py, `_written`), plus chmod and chown — a
  file opened for writing (open, pathlib, os.open), a folder made or removed, a file removed, renamed
  or replaced, a link made, its times, size or mode changed, shutil.rmtree, sqlite3.connect. A path is
  placed as given and resolved (a link into the folder is seen). A mkdir of a folder that is there
  writes nothing: left to fail by itself (os.makedirs(exist_ok=True)).
  The writers of ~/.eregion that open no file through `open` go through these events, each seen:
  the watch's key and the services' (eregion_core/watch_key.py: os.mkdir, os.open with O_EXCL,
  os.link, os.chmod), the queue's registers and requests (channel_reader.write_file: mkstemp,
  os.chmod, os.replace), the console's token (os.open, os.replace), a drill (mkstemp, os.replace,
  os.link), an exercise request (os.open).
- **A store a native library writes by itself** (ChromaDB 1.x's, from Rust, unseen by the hook): its
  opener calls `check(path)` first, which refuses the opening itself — the memory of cycles under
  ~/.glorfindel (glorfindel/memory.py, CycleMemory), the analysis index under ~/.eregion
  (analysis/campaign_report.py, `_collection`). The only two.

Not seen (a guard against error, never against a session that wants to: the same Unix user): what a C
or Rust library writes once its file is open, or by itself, when its opener does not call `check`
(sqlite's pages, a write through a descriptor, mmap); a path relative to a dir_fd; a process that imports no module of
the repository (a shell's `>`, a script of its own — the Makefile's `annatar-shell`, which makes
~/.annatar's two files, is one; scripts/mobile.py and scripts/published_image.py, which write under
~/.eregion and import none, are others); a session launched without the repository's settings and
outside a worktree.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

STORE = ".glorfindel"
# The operator's folders guarded (HY2c, #800: ~/.eregion and ~/.annatar too, Jonathan's decision of 13/11).
STORES = (STORE, ".eregion", ".annatar")
SESSION_VAR = "EREGION_AGENT_SESSION"
DOC = "docs/operations.md, « Une sonde d'agent n'écrit jamais dans le vrai ~/.glorfindel, ~/.eregion ni ~/.annatar »"
# Why a process is a session's, when its variable is not set: where it runs, or where its code is.
WORKTREE_CWD = "le worktree d'un lot (.claude/worktrees/)"
WORKTREE_CODE = "le code d'un worktree de lot (.claude/worktrees/)"

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
    """A write in the operator's ~/.glorfindel, ~/.eregion or ~/.annatar, refused in an agent session
    (HY2b, HY2c)."""


def _in_worktree(where) -> bool:
    """``where`` lies in a lot's worktree (.claude/worktrees/), resolved."""
    try:
        parts = Path(where).resolve().parts
    except OSError:   # a current folder removed
        return False
    if ".claude" in parts and "worktrees" in parts[parts.index(".claude"):]:
        return True
    return False


def why_guarded(env=None, cwd=None, here=None) -> str:
    """Why this process is an agent session's, or '' (the operator's: nothing is guarded).

    The rule of scripts/bench_shared.py's `session_refusal`: the variable, then the current folder,
    then the checkout this code runs from (``here``, this module's own file by default) — a probe
    run from elsewhere that imports a worktree's code is a session's; the operator's comes from
    ~/eregion."""
    env = os.environ if env is None else env
    if env.get(SESSION_VAR):
        return f"une session d'agent ({SESSION_VAR})"
    try:
        cwd = os.getcwd() if cwd is None else cwd
    except OSError:   # a current folder removed
        cwd = None
    if cwd is not None and _in_worktree(cwd):
        return WORKTREE_CWD
    if _in_worktree(Path(__file__) if here is None else here):
        return WORKTREE_CODE
    return ""


def operator_home() -> Path:
    """The home the system gives this user, whatever HOME says (a probe's throwaway HOME, the suite's)."""
    try:
        import pwd
        return Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (ImportError, KeyError, OSError):   # no passwd entry (a container's UID): HOME then
        return Path(os.path.expanduser("~"))


def roots_of(home) -> tuple[str, ...]:
    """The operator's folders (``STORES``), each as given and resolved (a home reached through a link)."""
    roots = []
    for store in STORES:
        given = os.path.abspath(os.path.join(os.fspath(home), store))
        roots += [given, os.path.realpath(given)]
    return tuple(dict.fromkeys(roots))


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


def located(path, roots: tuple[str, ...]) -> tuple[str, str] | None:
    """``path`` made absolute and the name of the folder it lies in (``.eregion``), when it lies in
    one of ``roots`` (the root itself included), as given or resolved; else None."""
    if path is None or isinstance(path, int):
        return None
    try:
        full = os.path.abspath(os.fsdecode(path))
    except (TypeError, ValueError):
        return None
    for candidate in dict.fromkeys((full, os.path.realpath(full))):
        for root in roots:
            if candidate == root or candidate.startswith(root + os.sep):
                return full, os.path.basename(root)
    return None


def placed(path, roots: tuple[str, ...]) -> str | None:
    """``path`` made absolute, when it lies in one of ``roots``; else None."""
    found = located(path, roots)
    return None if found is None else found[0]


# Said to the operator alone, when the refusal comes from the current folder (HY2c): he may have run
# the command by hand from a lot's worktree. Never a way out offered to a probe of an agent session.
OPERATOR_ONLY = (" Pour l'opérateur seulement, s'il a lancé lui-même cette commande depuis ce worktree : "
                 "qu'il la relance hors de lui. Une sonde d'agent, elle, ne sort jamais du worktree pour "
                 "écrire là.")


def message(full: str, why: str, store: str = STORE) -> str:
    """The line said of a write refused at ``full``, in the operator's ``store``: the folder, the file,
    why, and what a probe does."""
    operator = OPERATOR_ONLY if why == WORKTREE_CWD else ""
    return (f"HY2b : écriture refusée dans le ~/{store} de l'opérateur ({full}) — {why}. "
            "Une sonde prend un HOME jetable (HOME=$(mktemp -d) python …) ou va dans la suite "
            f"(tests/unit/) ; {DOC}.{operator}")


def refusal(event: str, args, roots: tuple[str, ...], why: str) -> str | None:
    """What is said of this event when it writes in ``roots``, or None."""
    for path in written(event, args):
        found = located(path, roots)
        if found is not None:
            return message(found[0], why, found[1])
    return None


def _say(said: str) -> None:
    """``said`` on stderr, once per line."""
    if said not in _said:
        _said.add(said)
        try:
            sys.stderr.write(said + "\n")
            sys.stderr.flush()
        except Exception:   # a closed stderr: the exception still says it
            pass


def _hook(event, args):
    if event not in _WATCHED:
        return
    said = refusal(event, args, _installed["roots"], _installed["why"])
    if said is None:
        return
    _say(said)
    raise Refused(said)


def check(path) -> None:
    """Refuse, before it is opened, a store that a native library writes by itself (ChromaDB 1.x
    writes its sqlite and its index from Rust, which the audit hook never sees): ``path`` in one of
    the operator's folders, in an agent session, is said and raises Refused. Elsewhere, nothing."""
    roots = guarded()
    if not roots:
        return
    found = located(path, roots)
    if found is None:
        return
    said = message(found[0], _installed["why"], found[1])
    _say(said)
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
