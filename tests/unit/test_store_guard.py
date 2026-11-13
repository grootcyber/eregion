"""HY2b (#791), HY2c (#800): a probe of an agent session, outside the suite, never writes in the
operator's real ~/.glorfindel, ~/.eregion or ~/.annatar — the write refused and said before it happens
(eregion_core/store_guard.py).

Measured over an operator simulated in tmp, never this workstation's: each probe is a fresh
interpreter whose system home (pwd) is a folder of tmp_path with its ~/.glorfindel already there, and
which imports Glorfindel as a probe does, then writes through it (vm_notices.say, the store of 12/11;
CycleMemory, ChromaDB's store, written from Rust). Its code is a copy of the repository's packages in
tmp — the operator's from a checkout of his own, a session's from a lot's worktree — so that the
measure does not depend on where the suite runs. An agent session's probe (EREGION_AGENT_SESSION, a
lot's worktree as its folder or as the checkout of its code) is refused and says it; the operator's,
and a probe with a throwaway HOME, write as before. Then what a write is, where it is placed, and who
imports the guard first. Mutants M5150–M5159, M5190–M5194 (scripts/mutants/HY2b.py).

HY2c: the same probes over ~/.eregion (the watch's key drawn when absent, a service's key of the queue,
the queue's register, the analysis index, ChromaDB's) and ~/.annatar (its shell's history); the folder
named in the refusal; leaving the worktree said to the operator alone, never offered to a probe.
Mutants M5235–M5244 (scripts/mutants/HY2c.py).
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
# HY2c: what writes under ~/.eregion and ~/.annatar, each step on its own, its outcome printed. Its
# folders are the HOME's (the watch's own defaults: argv[2] `-`), or those of the home named in
# argv[2] — a probe whose HOME is a throwaway one, writing in the operator's by its path. argv[3]
# `analysis`: the analysis index opened too (ChromaDB's, written from Rust).
EREGION_PROBE = textwrap.dedent("""
    import sys, types
    import pwd
    pwd.getpwuid = lambda uid: types.SimpleNamespace(pw_dir=sys.argv[1])
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from eregion_core import action_queue, watch_key
    if sys.argv[2] != "-":
        home = Path(sys.argv[2])
        watch_key.KEY_DIR = home / ".eregion" / "watch-key"
        action_queue.KEY_ROOT = home / ".eregion"
        action_queue.QUEUE_DIR = home / ".eregion" / "watch-queue"
    else:
        home = Path.home()
    now = datetime.now(timezone.utc)

    def annatar():
        with open(home / ".annatar" / ".bash_history", "a") as f:
            f.write("hy2c-probe\\n")

    steps = {
        "key": lambda: watch_key.load_or_create(),
        "service": lambda: action_queue.load_service_key("console"),
        "queue": lambda: action_queue.SeenFile().claim("hy2c-nonce", now + timedelta(minutes=5), now),
        "annatar": annatar,
    }
    for name, step in steps.items():
        try:
            step()
            print(name, "written")
        except Exception as exc:
            print(name, "refused", type(exc).__name__)
    if len(sys.argv) > 3:
        try:
            from analysis import campaign_report
            campaign_report._collection()
            print("analysis written")
        except OSError as exc:
            print("analysis refused", type(exc).__name__)
    """)
# The packages a probe imports, copied for its code (glorfindel imports eregion_core first); analysis
# (HY2c, its index) reads a run's detections through annatar.
PACKAGES = ("eregion_core", "glorfindel", "analysis", "annatar")
# The operator's folders the probes photograph (eregion_core/store_guard.py, STORES).
STORES = (".glorfindel", ".eregion", ".annatar")


def _operator(tmp_path) -> Path:
    """The operator simulated: his ~/.glorfindel there already, one file in it, and its cycles/; his
    ~/.eregion with the console's folder and the queue's (the watch's key not drawn yet) and the
    analysis index's; his ~/.annatar and its shell's history."""
    real = tmp_path / "operator"
    (real / ".glorfindel" / "cycles").mkdir(parents=True)
    (real / ".glorfindel" / "escalations.jsonl").write_text("{}\n")
    for held in ("console", "watch-queue"):
        (real / ".eregion" / held).mkdir(mode=0o700, parents=True)
    (real / ".eregion" / "analysis" / "chroma").mkdir(parents=True)
    (real / ".annatar").mkdir()
    (real / ".annatar" / ".bash_history").write_text("ls\n")
    return real


def _checkout(where: Path) -> Path:
    """The repository's packages a probe imports, copied in ``where`` (its code's checkout)."""
    for package in PACKAGES:
        shutil.copytree(ROOT / package, where / package, ignore=shutil.ignore_patterns("__pycache__"))
    return where


def _shot(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*"))} if root.exists() else {}


def _shots(home: Path) -> dict:
    """The operator's three folders, photographed (names, sizes, dates)."""
    return {store: _shot(home / store) for store in STORES}


# The two checkouts a probe's code comes from: the operator's own (~/eregion), a lot's worktree.
CODE = {"operator": "home/eregion", "worktree": "w/.claude/worktrees/lot-code"}
SCENARIOS = {
    # name: (EREGION_AGENT_SESSION, current folder, HOME — None: the operator's, how the probe ends,
    #        the checkout of its code, what it writes)
    "agent": ("1", "elsewhere", None, "raise", "operator", "notice"),
    "worktree": (None, "w/.claude/worktrees/lot-x", None, "swallow", "operator", "notice"),
    "code": (None, "elsewhere", None, "swallow", "worktree", "notice"),
    "operator": (None, "elsewhere", None, "raise", "operator", "notice"),
    "throwaway": ("1", "elsewhere", "probe-home", "raise", "operator", "notice"),
    "memory": ("1", "elsewhere", None, "swallow", "operator", "memory"),
    # HY2c: ~/.eregion and ~/.annatar — `eregion` writes the HOME's; `eregion@operator`, the operator's
    # by its path, whatever HOME says; `+analysis` opens the analysis index too.
    "eregion": ("1", "elsewhere", None, "swallow", "operator", "eregion+analysis"),
    "eregion-worktree": (None, "w/.claude/worktrees/lot-y", None, "swallow", "operator", "eregion"),
    "eregion-pinned": ("1", "elsewhere", "probe-home", "swallow", "operator", "eregion@operator"),
    "eregion-operator": (None, "elsewhere", None, "swallow", "operator", "eregion+analysis"),
    "eregion-throwaway": ("1", "elsewhere", "probe-home", "swallow", "operator", "eregion"),
}


@pytest.fixture(scope="module")
def probes(tmp_path_factory):
    """The probes, at once (each its own interpreter): their outcome and the stores after."""
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("PYTEST_", "EREGION_TEST_")) and k != SESSION_VAR}
    base["ANONYMIZED_TELEMETRY"] = "False"     # ChromaDB's, never sent from a test
    base.pop("EREGION_ANALYSIS_INDEX", None)   # the index under the HOME's ~/.eregion (HY2c)
    driver = tmp_path_factory.mktemp("driver") / "probe.py"
    driver.write_text(PROBE)
    eregion_driver = driver.with_name("eregion_probe.py")
    eregion_driver.write_text(EREGION_PROBE)
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
        before = _shots(operator)
        if what.startswith("eregion"):
            argv = [str(eregion_driver), str(operator), str(operator) if "@operator" in what else "-"]
            argv += ["analysis"] if "+analysis" in what else []
        else:
            argv = [str(driver), str(operator), end, what]
        proc = subprocess.Popen([sys.executable, *argv], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        runs[name] = (proc, operator, own, before)
    out = {}
    for name, (proc, operator, own, before) in runs.items():
        stdout, stderr = proc.communicate(timeout=240)
        out[name] = {"code": proc.returncode, "out": stdout, "err": stderr, "operator": operator,
                     "own": own, "before": before, "after": _shots(operator)}
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
    # its variable stays wherever it runs: leaving the worktree is no way out, never said
    assert "hors du worktree" not in run["err"], _said(run)


def test_a_probe_from_a_lot_s_worktree_is_refused_and_said_even_when_it_swallows_the_error(probes):
    """No EREGION_AGENT_SESSION (a session launched without the repository's settings), its current
    folder a lot's worktree: refused too. The probe catches the OSError: stderr says it all the same."""
    run = probes["worktree"]
    assert run["code"] == 0 and "swallowed" in run["out"], _said(run)
    assert run["after"] == run["before"], _said(run)
    assert "HY2b : écriture refusée" in run["err"] and "worktree" in run["err"], _said(run)
    assert "~/.glorfindel de l'opérateur" in run["err"], _said(run)
    # HY2c: leaving the worktree said to the operator alone, never offered to the probe
    assert "Pour l'opérateur seulement" in run["err"], _said(run)
    assert "Une sonde d'agent, elle, ne sort jamais du worktree" in run["err"], _said(run)
    assert "ou lance la commande hors du worktree" not in run["err"], _said(run)


def test_a_probe_that_runs_a_lot_s_worktree_code_from_elsewhere_is_refused_and_said(probes):
    """No EREGION_AGENT_SESSION, its folder elsewhere, but its code a lot's worktree's (the checkout
    it runs from, scripts/bench_shared.py's `here`): refused too, and said. The operator's code comes
    from ~/eregion: his probe writes (test_the_operator_writes_as_before)."""
    run = probes["code"]
    assert run["code"] == 0 and "swallowed" in run["out"], _said(run)
    assert run["after"] == run["before"], _said(run)
    assert "HY2b : écriture refusée" in run["err"] and "le code d'un worktree" in run["err"], _said(run)
    assert "hors du worktree" not in run["err"], _said(run)


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


# --- HY2c: ~/.eregion and ~/.annatar ------------------------------------------------------------------

def _step(run, name: str) -> str:
    """What the probe printed of a step: `written`, `refused …`, or '' (never reached)."""
    for line in run["out"].splitlines():
        if line.startswith(name + " "):
            return line[len(name) + 1:]
    return ""


def test_an_agent_session_s_probe_never_draws_the_watch_s_key_in_the_operator_s_eregion(probes):
    """~/.eregion/watch-key: the code draws a key when there is none (SEC19). An agent session's probe,
    its HOME the operator's, would have drawn the watch's signing key there: refused before its folder
    is made, said, the folder named."""
    run = probes["eregion"]
    assert _step(run, "key").startswith("refused"), _said(run)
    assert not (run["operator"] / ".eregion" / "watch-key").exists(), _said(run)
    said = [line for line in run["err"].splitlines()
            if line.startswith("HY2b : ") and str(run["operator"] / ".eregion" / "watch-key") in line]
    assert said, _said(run)
    assert said[0].startswith("HY2b : écriture refusée dans le ~/.eregion de l'opérateur"), _said(run)
    assert SESSION_VAR in said[0], _said(run)


def test_an_agent_session_s_probe_never_writes_a_service_key_nor_the_queue_in_the_operator_s_eregion(probes):
    """The console's key of the signed queue (its folder there, the key drawn by os.open with O_EXCL then
    published by a link) and the watch's register of nonces (mkstemp, then os.replace): neither passes
    through `open`, both are refused before anything is written."""
    run = probes["eregion"]
    assert _step(run, "service").startswith("refused"), _said(run)
    assert _step(run, "queue").startswith("refused"), _said(run)
    assert run["after"][".eregion"] == run["before"][".eregion"], _said(run)
    assert str(run["operator"] / ".eregion" / "console") in run["err"], _said(run)
    assert str(run["operator"] / ".eregion" / "watch-queue") in run["err"], _said(run)


def test_an_agent_session_s_probe_never_writes_in_the_operator_s_annatar(probes):
    """~/.annatar holds the shell of Annatar (its .bashrc, its history): a probe appending to it is
    refused, and the refusal names ~/.annatar."""
    run = probes["eregion"]
    assert _step(run, "annatar").startswith("refused"), _said(run)
    assert (run["operator"] / ".annatar" / ".bash_history").read_text() == "ls\n"
    assert run["after"][".annatar"] == run["before"][".annatar"], _said(run)
    assert "HY2b : écriture refusée dans le ~/.annatar de l'opérateur" in run["err"], _said(run)


def test_the_analysis_index_is_refused_before_chromadb_opens_it_in_the_operator_s_eregion(probes):
    """The analysis index (~/.eregion/analysis/chroma, there already): ChromaDB writes it from Rust,
    out of the hook's sight. Refused before it is opened: no sqlite, no index there."""
    run = probes["eregion"]
    assert _step(run, "analysis").startswith("refused"), _said(run)
    assert run["after"] == run["before"], _said(run)
    assert str(run["operator"] / ".eregion" / "analysis" / "chroma") in run["err"], _said(run)


def test_the_operator_s_eregion_is_guarded_whatever_home_says(probes):
    """A probe with a throwaway HOME that writes in the operator's ~/.eregion and ~/.annatar by their
    path (a getpwuid, a path written whole): refused all the same — the folders are the system home's."""
    run = probes["eregion-pinned"]
    for name in ("key", "service", "queue", "annatar"):
        assert _step(run, name).startswith("refused"), (name, _said(run))
    assert run["after"] == run["before"], _said(run)
    assert not list((run["own"]).rglob("*")), _said(run)


def test_from_a_worktree_the_way_out_is_said_to_the_operator_never_offered_to_the_probe(probes):
    """Refused for its current folder (a lot's worktree): the line names ~/.eregion, and leaving the
    worktree is said to the operator alone — never as a way out for a probe of an agent session."""
    run = probes["eregion-worktree"]
    assert _step(run, "key").startswith("refused"), _said(run)
    assert run["after"] == run["before"], _said(run)
    assert "~/.eregion de l'opérateur" in run["err"] and "le worktree d'un lot" in run["err"], _said(run)
    assert "Pour l'opérateur seulement, s'il a lancé lui-même cette commande" in run["err"], _said(run)
    assert "Une sonde d'agent, elle, ne sort jamais du worktree" in run["err"], _said(run)
    assert "ou lance la commande hors du worktree" not in run["err"], _said(run)


def test_the_operator_writes_his_eregion_and_annatar_as_before(probes):
    """The operator's terminal (no EREGION_AGENT_SESSION, outside a worktree) — the watch, the bot, his
    containers and Imladris alike: the watch's key drawn, the console's, the register, the history, the
    analysis index, all written in his own folders, nothing said."""
    run = probes["eregion-operator"]
    for name in ("key", "service", "queue", "annatar", "analysis"):
        assert _step(run, name) == "written", (name, _said(run))
    assert "HY2b" not in run["err"], _said(run)
    eregion = run["operator"] / ".eregion"
    assert (eregion / "watch-key" / "watch_ed25519").stat().st_size == 32
    assert (eregion / "console" / "queue_ed25519").exists()
    assert "hy2c-nonce" in (eregion / "watch-queue" / "seen.json").read_text()
    assert "hy2c-probe" in (run["operator"] / ".annatar" / ".bash_history").read_text()
    assert any((eregion / "analysis" / "chroma").iterdir())


def test_a_probe_with_a_throwaway_home_draws_its_key_and_its_queue_in_its_own(probes):
    """The suite's HOME (HY2) and a probe's HOME=$(mktemp -d): an agent session's key, queue and history
    land under it; the operator's folders untouched."""
    run = probes["eregion-throwaway"]
    for name in ("key", "service", "queue"):
        assert _step(run, name) == "written", (name, _said(run))
    # its HOME holds no ~/.annatar: the history is not there to append to — never the guard's refusal
    assert _step(run, "annatar") == "refused FileNotFoundError", _said(run)
    assert "HY2b" not in run["err"], _said(run)
    own = run["own"] / ".eregion"
    assert (own / "watch-key" / "watch_ed25519").stat().st_size == 32
    assert (own / "console" / "queue_ed25519").exists()
    assert "hy2c-nonce" in (own / "watch-queue" / "seen.json").read_text()
    assert run["after"] == run["before"], _said(run)


# --- Who is an agent session ---------------------------------------------------------------------------

def test_an_agent_session_is_its_variable_or_a_lot_s_worktree_never_the_operator(tmp_path):
    from eregion_core import store_guard as sg
    lot = tmp_path / ".claude" / "worktrees" / "lot" / "sub"
    lot.mkdir(parents=True)
    (tmp_path / "eregion" / "eregion_core").mkdir(parents=True)
    mine = tmp_path / "eregion" / "eregion_core" / "store_guard.py"       # the operator's code
    assert sg.SESSION_VAR in sg.why_guarded({sg.SESSION_VAR: "1"}, tmp_path / "eregion", mine)
    assert sg.why_guarded({}, lot, mine) == sg.WORKTREE_CWD
    assert sg.why_guarded({}, tmp_path / "eregion", lot / "store_guard.py") == sg.WORKTREE_CODE
    assert sg.why_guarded({}, tmp_path / "eregion", mine) == ""
    assert sg.why_guarded({sg.SESSION_VAR: ""}, tmp_path / ".claude", mine) == ""


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
    assert roots[:2] == (str(link / ".glorfindel"), str(real / ".glorfindel"))   # HY2c: then the others
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


def test_the_operator_s_eregion_and_annatar_are_placed_as_given_or_resolved_and_named(tmp_path):
    """HY2c: three folders guarded, each as given and resolved; a folder beside them (~/.eregion-cd,
    ~/.eregion-image, ~/.annatar2) never; the refusal names the folder the file lies in."""
    from eregion_core import store_guard as sg
    real = tmp_path / "operator"
    real.mkdir()
    link = tmp_path / "home-link"
    link.symlink_to(real)
    roots = sg.roots_of(link)
    assert roots == tuple(str(h / s) for s in (".glorfindel", ".eregion", ".annatar") for h in (link, real))
    for store in (".eregion", ".annatar"):
        assert sg.placed(link / store / "a", roots) == str(link / store / "a")
        assert sg.placed(real / store / "b", roots) == str(real / store / "b")
        assert sg.placed(real / store, roots)
    for beside in (".eregion-cd", ".eregion-image", ".annatar2"):
        assert sg.placed(real / beside / "x", roots) is None
    assert sg.placed(tmp_path / "probe-home" / ".eregion" / "watch-key" / "k", roots) is None
    for store in (".glorfindel", ".eregion", ".annatar"):
        said = sg.refusal("open", (str(real / store / "f"), "w", 0), roots, "why")
        assert said.startswith(f"HY2b : écriture refusée dans le ~/{store} de l'opérateur ({real / store / 'f'})")
    linked = sg.refusal("open", (str(tmp_path / "home-link" / ".eregion" / "g"), "a", 0), roots, "why")
    assert "~/.eregion de l'opérateur" in linked


def test_leaving_the_worktree_is_said_to_the_operator_alone_never_to_a_probe():
    """HY2c: refused for its current folder, the line says leaving the worktree to the operator alone,
    and that a probe never does; refused for its variable or its code, it says nothing of it."""
    from eregion_core import store_guard as sg
    said = sg.message("/h/.eregion/x", sg.WORKTREE_CWD, ".eregion")
    assert said.endswith(sg.OPERATOR_ONLY) and "Pour l'opérateur seulement" in said
    assert "ou lance la commande hors du worktree" not in said
    assert "Une sonde prend un HOME jetable (HOME=$(mktemp -d) python …) ou va dans la suite" in said
    for why in (sg.WORKTREE_CODE, f"une session d'agent ({sg.SESSION_VAR})"):
        other = sg.message("/h/.eregion/x", why, ".eregion")
        assert "Pour l'opérateur" not in other and "hors du worktree" not in other


def test_a_key_published_by_a_link_or_a_file_replaced_is_a_write():
    """HY2c: what writes ~/.eregion without `open` — the watch's key published by os.link, a register
    replaced by os.replace, a folder made by os.mkdir — is each a write."""
    from eregion_core import store_guard as sg
    key = "/h/.eregion/watch-key/watch_ed25519"
    assert sg.written("os.link", ("/h/.eregion/watch-key/.tmp", key, -1, -1)) == [key]
    assert sg.written("os.link", ("t", "k", 3, 4)) == []           # relative to a dir_fd: not placed
    seen = "/h/.eregion/watch-queue/seen.json"
    assert sg.written("os.rename", ("/h/.eregion/watch-queue/.seen.json.x", seen, -1, -1))[1] == seen
    assert sg.written("open", (key, None, os.O_WRONLY | os.O_CREAT | os.O_EXCL)) == [key]


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
