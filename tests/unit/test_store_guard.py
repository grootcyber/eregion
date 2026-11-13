"""HY2b (#791): a probe of an agent session, outside the suite, never writes in the operator's real
~/.glorfindel — the write refused and said before it happens (eregion_core/store_guard.py).

Measured over an operator simulated in tmp, never this workstation's: each probe is a fresh
interpreter whose system home (pwd) is a folder of tmp_path with its ~/.glorfindel already there, and
which imports Glorfindel as a probe does, then writes through it (vm_notices.say, the store of 12/11;
CycleMemory, ChromaDB's store, written from Rust). Its code is a copy of the repository's packages in
tmp — the operator's from a checkout of his own, a session's from a lot's worktree — so that the
measure does not depend on where the suite runs. An agent session's probe (EREGION_AGENT_SESSION, a
lot's worktree as its folder or as the checkout of its code) is refused and says it; the operator's,
and a probe with a throwaway HOME, write as before. Then what a write is, where it is placed, and who
imports the guard first. Mutants M5150–M5159, M5190–M5194 (scripts/mutants/HY2b.py).
"""
import ast
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# The variable the repository's settings give its sessions (docs/sessions.md, SEC12): written here,
# so that the probes measure the base too, where eregion_core/store_guard.py is not.
SESSION_VAR = "EREGION_AGENT_SESSION"

# The probe: its system home made the simulated operator's (argv[1]), then Glorfindel imported and a
# notice said — what DRN2's probes did on 12/11 — or (argv[3] `memory`) the memory of cycles opened in
# the operator's ~/.glorfindel/cycles, there already. `swallow`: the probe catches the OSError.
PROBE = textwrap.dedent("""
    import sys, types
    import pwd
    pwd.getpwuid = lambda uid: types.SimpleNamespace(pw_dir=sys.argv[1])
    try:
        if sys.argv[3] == "memory":
            from glorfindel.memory import CycleMemory
            CycleMemory(path=sys.argv[1] + "/.glorfindel/cycles")
            print("via memory")
        else:
            import glorfindel.vm_notices as v
            print("via", v.say("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm",
                                "hy2b-probe", "info", "probe", "a probe's notice"))
    except OSError as exc:
        if sys.argv[2] != "swallow":
            raise
        print("swallowed", type(exc).__name__)
    """)
# The packages a probe imports, copied for its code (glorfindel imports eregion_core first).
PACKAGES = ("eregion_core", "glorfindel")


def _operator(tmp_path) -> Path:
    """The operator simulated: his ~/.glorfindel there already, one file in it, and its cycles/."""
    real = tmp_path / "operator"
    (real / ".glorfindel" / "cycles").mkdir(parents=True)
    (real / ".glorfindel" / "escalations.jsonl").write_text("{}\n")
    return real


def _checkout(where: Path) -> Path:
    """The repository's packages a probe imports, copied in ``where`` (its code's checkout)."""
    for package in PACKAGES:
        shutil.copytree(ROOT / package, where / package, ignore=shutil.ignore_patterns("__pycache__"))
    return where


def _shot(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*"))} if root.exists() else {}


# The two checkouts a probe's code comes from: the operator's own (~/eregion), a lot's worktree.
CODE = {"operator": "home/eregion", "worktree": "w/.claude/worktrees/lot-code"}
SCENARIOS = {
    # name: (EREGION_AGENT_SESSION, current folder, HOME — None: the operator's, how the probe ends,
    #        the checkout of its code, what it writes)
    "agent": ("1", "elsewhere", None, "raise", "operator", "notice"),
    "worktree": (None, "w/.claude/worktrees/lot-x", None, "swallow", "operator", "notice"),
    "operator": (None, "elsewhere", None, "raise", "operator", "notice"),
    "throwaway": ("1", "elsewhere", "probe-home", "raise", "operator", "notice"),
    "memory": ("1", "elsewhere", None, "swallow", "operator", "memory"),
}


@pytest.fixture(scope="module")
def probes(tmp_path_factory):
    """The probes, at once (each its own interpreter): their outcome and the stores after."""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("PYTEST_", "EREGION_TEST_")) and k != SESSION_VAR}
    base["ANONYMIZED_TELEMETRY"] = "False"     # ChromaDB's, never sent from a test
    driver = tmp_path_factory.mktemp("driver") / "probe.py"
    driver.write_text(PROBE)
    codes = tmp_path_factory.mktemp("code")
    checkouts = {k: _checkout(codes / v) for k, v in CODE.items()}
    runs = {}
    for name, (session, where, home, end, code, what) in SCENARIOS.items():
        tmp = tmp_path_factory.mktemp(name)
        operator = _operator(tmp)
        cwd = tmp / where
        cwd.mkdir(parents=True)
        own = tmp / home if home else operator
        own.mkdir(exist_ok=True)
        env = {**base, "HOME": str(own), "PYTHONPATH": str(checkouts[code])}
        if session:
            env[SESSION_VAR] = session
        before = _shot(operator / ".glorfindel")
        proc = subprocess.Popen([sys.executable, str(driver), str(operator), end, what], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        runs[name] = (proc, operator, own, before)
    out = {}
    for name, (proc, operator, own, before) in runs.items():
        stdout, stderr = proc.communicate(timeout=240)
        out[name] = {"code": proc.returncode, "out": stdout, "err": stderr, "operator": operator,
                     "own": own, "before": before, "after": _shot(operator / ".glorfindel")}
    return out


def _said(run) -> str:
    return f"code {run['code']}\nstdout:\n{run['out'][-2000:]}\nstderr:\n{run['err'][-3000:]}"


def test_an_agent_session_s_probe_is_refused_before_it_writes_and_says_so(probes):
    """12/11 again: a probe of an agent session imports Glorfindel and says a notice, its HOME the
    operator's. Refused: nothing created, nor its lock; the refusal names the file and why."""
    run = probes["agent"]
    assert run["code"] != 0, _said(run)
    assert run["after"] == run["before"], _said(run)
    assert "HY2b : écriture refusée" in run["err"], _said(run)
    assert str(run["operator"] / ".glorfindel") in run["err"], _said(run)
    assert SESSION_VAR in run["err"], _said(run)
    assert "PermissionError" in run["err"] or "Refused" in run["err"], _said(run)


def test_a_probe_from_a_lot_s_worktree_is_refused_and_said_even_when_it_swallows_the_error(probes):
    """No EREGION_AGENT_SESSION (a session launched without the repository's settings), its current
    folder a lot's worktree: refused too. The probe catches the OSError: stderr says it all the same."""
    run = probes["worktree"]
    assert run["code"] == 0 and "swallowed" in run["out"], _said(run)
    assert run["after"] == run["before"], _said(run)
    assert "HY2b : écriture refusée" in run["err"] and "worktree" in run["err"], _said(run)


def test_the_memory_of_cycles_is_refused_before_chromadb_opens_it(probes):
    """ChromaDB 1.x writes its store from Rust, which the audit hook never sees: with the operator's
    ~/.glorfindel/cycles there already, an agent session's CycleMemory would create its sqlite and
    its index there (review of HY2b, round 1). Refused before ChromaDB opens it, and said — even when
    the probe swallows the error (`glorfindel report`'s age_census does)."""
    run = probes["memory"]
    assert run["after"] == run["before"], _said(run)          # no chroma.sqlite3, no index
    assert run["code"] == 0 and "swallowed" in run["out"], _said(run)
    assert "HY2b : écriture refusée" in run["err"], _said(run)
    assert str(run["operator"] / ".glorfindel" / "cycles") in run["err"], _said(run)


def test_the_operator_writes_as_before(probes):
    """The operator's terminal (no EREGION_AGENT_SESSION, outside a worktree) — his containers, the
    watch and Imladris alike: nothing installed, the notice written in his ~/.glorfindel."""
    run = probes["operator"]
    assert run["code"] == 0 and "via none" in run["out"], _said(run)
    assert "HY2b" not in run["err"], _said(run)
    store = run["operator"] / ".glorfindel" / "vm_notices.jsonl"
    assert "hy2b-probe" in store.read_text(), _said(run)


def test_a_probe_with_a_throwaway_home_writes_in_its_own(probes):
    """What the rule asks of a probe: HOME=$(mktemp -d). Its writes land there; the operator's folder
    is untouched."""
    run = probes["throwaway"]
    assert run["code"] == 0 and "via none" in run["out"], _said(run)
    assert "HY2b" not in run["err"], _said(run)
    assert "hy2b-probe" in (run["own"] / ".glorfindel" / "vm_notices.jsonl").read_text()
    assert run["after"] == run["before"], _said(run)


# --- Who is an agent session ---------------------------------------------------------------------------

def test_an_agent_session_is_its_variable_or_a_lot_s_worktree_never_the_operator(tmp_path):
    from eregion_core import store_guard as sg
    (tmp_path / ".claude" / "worktrees" / "lot" / "sub").mkdir(parents=True)
    (tmp_path / "eregion").mkdir()
    assert sg.SESSION_VAR in sg.why_guarded({sg.SESSION_VAR: "1"}, tmp_path / "eregion")
    assert "worktree" in sg.why_guarded({}, tmp_path / ".claude" / "worktrees" / "lot" / "sub")
    assert sg.why_guarded({}, tmp_path / "eregion") == ""
    assert sg.why_guarded({sg.SESSION_VAR: ""}, tmp_path / ".claude") == ""


# --- What a write is, where it is placed ----------------------------------------------------------------

def test_a_write_is_any_opening_for_writing_and_every_change_of_the_tree_never_a_read(tmp_path):
    from eregion_core import store_guard as sg
    store = str(tmp_path / ".glorfindel")
    f = os.path.join(store, "x.json")
    for mode in ("w", "a", "x", "r+", "ab", "wb"):
        assert sg.written("open", (f, mode, 0)) == [f], mode
    assert sg.written("open", (f, "r", 0)) == [] and sg.written("open", (f, "rb", 0)) == []
    assert sg.written("open", (f, None, os.O_RDONLY)) == []
    assert sg.written("open", (f, None, os.O_WRONLY | os.O_CREAT)) == [f]
    assert sg.written("os.rename", ("/elsewhere/t", f, -1, -1)) == ["/elsewhere/t", f]
    assert sg.written("os.remove", (f, -1)) == [f]
    assert sg.written("os.chmod", (f, 0o600, -1)) == [f]
    assert sg.written("os.remove", ("x.json", 3)) == []          # relative to a dir_fd: not placed
    assert sg.written("sqlite3.connect", (f"file:{f}?mode=rwc",)) == [f]
    assert sg.written("sqlite3.connect", (":memory:",)) == []
    assert sg.written("os.listdir", (store,)) == []
    os.mkdir(store)                                              # a folder there: mkdir writes nothing
    assert sg.written("os.mkdir", (store, 0o700, -1)) == []
    assert sg.written("os.mkdir", (os.path.join(store, "new"), 0o700, -1)) == [os.path.join(store, "new")]


def test_a_path_is_placed_in_the_store_as_given_or_resolved_never_beside_it(tmp_path):
    from eregion_core import store_guard as sg
    real = tmp_path / "operator"
    (real / ".glorfindel").mkdir(parents=True)
    link, other = tmp_path / "home-link", tmp_path / "other-link"
    link.symlink_to(real)
    other.symlink_to(real)
    roots = sg.roots_of(link)
    assert roots == (str(link / ".glorfindel"), str(real / ".glorfindel"))
    assert sg.placed(link / ".glorfindel" / "a", roots) == str(link / ".glorfindel" / "a")
    assert sg.placed(real / ".glorfindel" / "b", roots)
    assert sg.placed(other / ".glorfindel" / "c", roots) == str(other / ".glorfindel" / "c")  # resolved
    assert sg.placed(real / ".glorfindel", roots)                                       # the folder itself
    assert sg.placed(real / ".glorfindel-old" / "d", roots) is None                     # beside it
    assert sg.placed(tmp_path / "probe-home" / ".glorfindel" / "e", roots) is None
    assert sg.placed(3, roots) is None
    said = sg.refusal("open", (str(real / ".glorfindel" / "f"), "w", 0), roots, "why")
    assert said.startswith("HY2b : écriture refusée") and "why" in said and "HOME=$(mktemp -d)" in said
    assert sg.refusal("open", (str(real / ".glorfindel" / "f"), "r", 0), roots, "why") is None


# --- Who imports it first --------------------------------------------------------------------------------

def _first_import(path: Path) -> str:
    body = ast.parse(path.read_text(encoding="utf-8")).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    node = body[0]
    if isinstance(node, ast.Import):
        return node.names[0].name
    return f"from {node.module}" if isinstance(node, ast.ImportFrom) else type(node).__name__


def test_every_writer_of_glorfindel_s_state_imports_the_guard_first():
    """A script that imports Glorfindel, or the console, has the guard before any module of theirs
    computes a path; eregion_core installs it as it is imported (its own writers: exercise_seen.json)."""
    assert _first_import(ROOT / "glorfindel" / "__init__.py") == "eregion_core"
    assert _first_import(ROOT / "eregion_console" / "__init__.py") == "eregion_core"
    core = (ROOT / "eregion_core" / "__init__.py").read_text(encoding="utf-8")
    assert "from eregion_core import store_guard as _store_guard\n\n_store_guard.install()\n" in core
