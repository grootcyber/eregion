"""FRS1 (#904): one word, one meaning. « proven » is the catalogue's status — an entry measured on
the bench (STM1g, ``eregion_core.experiment``) — and only that. The coverage matrix's state for a
proof under 21 days old is « fresh » (Jonathan, 18/11): in the data (``state``, the summary's key),
in the matrix's page, on Dagorlad's red cards, in the overview and in ``eregion coverage``.

The value itself was renamed, not only its label: every reader of the matrix is the console's
(the test at the end proves it, over the files git tracks). Read here: the server's states, the
pages' tables of them, every word a page writes, and the CLI's output. No Azure, no LLM.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from click.testing import CliRunner  # noqa: E402

from .tracked_files import tracked  # noqa: E402

import eregion_console.api as api  # noqa: E402
from eregion_console import coverage as cov  # noqa: E402
from eregion_core.experiment import READY_STATUSES, is_ready  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "eregion_console" / "static"
DAY = cov.DAY
NOW = 2_000_000_000.0


def _state(days: float | None, runs=(), regressed=None) -> str:
    proof = None if days is None else {"at": NOW - days * DAY}
    return cov.state(list(runs), proof, regressed, NOW)


def _server_states() -> set[str]:
    """Every state the matrix can give a row: each branch of ``coverage.state``."""
    ages = {_state(d) for d in (0, 1, 5, 20, 20.99, 21, 25, 30, 30.01, 40, 400)}
    return ages | {_state(None, runs=[{}]), _state(None), _state(3, regressed={"held_by": "r"})}


def _catalogue_statuses() -> set[str]:
    schema = json.loads((REPO / "schemas" / "technique_catalog.schema.json").read_text())
    enums: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "status" and isinstance(v, dict) and "enum" in v:
                    enums.update(v["enum"])
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)
    return enums | set(READY_STATUSES)


# ── The server: the state and the summary ─────────────────────────────────────────────

@pytest.mark.parametrize("days", [0, 5, 20, 20.99])
def test_a_proof_under_21_days_is_fresh_never_proven(days):
    """M6261: the row's state for a proof under 21 days is ``fresh``."""
    assert _state(days) == "fresh"


@pytest.mark.parametrize("days, said", [(21, "aging"), (30, "aging"), (31, "stale")])
def test_an_older_proof_ages_as_before(days, said):
    assert _state(days) == said


def test_the_matrix_states_and_the_catalogue_statuses_share_no_word():
    """M6261, M6269: « proven » only for the catalogue, « fresh » never for it — the matrix's
    states and the catalogue's statuses (its schema, the predicate) are disjoint."""
    states, statuses = _server_states(), _catalogue_statuses()
    assert states == {"regressed", "fresh", "aging", "stale", "unproven", "never"}
    assert "proven" in statuses and "fresh" not in statuses
    assert states.isdisjoint(statuses), states & statuses
    assert is_ready("proven") and not is_ready("fresh")


def test_the_summary_counts_the_fresh_rows_under_fresh():
    """M6262: the summary's key is the state's word; no ``proven`` count beside the catalogue's."""
    rows = [{"id": f"T{i}", "in_catalog": True, "status": "implemented", "runs": 1, "state": s}
            for i, s in enumerate(["fresh", "fresh", "aging", "stale", "unproven", "regressed"])]
    s = cov._summary(rows)
    assert (s["fresh"], s["aging"], s["stale"], s["unproven"], s["never"]) == (2, 1, 1, 1, 0)
    assert s["regressed"] == ["T5"] and "proven" not in s


# ── The pages ─────────────────────────────────────────────────────────────────────────

def _table(js: str, start: str) -> str:
    i = js.index(start)
    return js[i:js.index("};", i)]


def test_the_matrix_page_labels_each_state_the_server_gives():
    """M6263, M6264: injector.js has a label for each state the server gives, and none other;
    the fresh one says « fresh »."""
    table = _table((STATIC / "injector.js").read_text(encoding="utf-8"), "const STATE = {")
    labels = dict(re.findall(r"^\s+(\w+): \{ cls: '\w+', label: '([^']+)'", table, re.M))
    assert set(labels) == _server_states()
    assert labels["fresh"] == "fresh"


def test_the_matrix_summary_reads_the_servers_keys_and_says_fresh():
    """M6265, M6266: the counter above the matrix reads keys the summary has, and writes
    « fresh » — the aging ones apart, since they are not fresh."""
    js = (STATIC / "injector.js").read_text(encoding="utf-8")
    i = js.index("$('cat-count').innerHTML")
    line = js[i:js.index("}).join(' │ ')", i)]
    rows = [{"id": "T", "in_catalog": True, "status": "implemented", "runs": 1, "state": "fresh"}]
    keys = set(cov._summary(rows))
    assert set(re.findall(r"\bs\.(\w+)", line)) <= keys, set(re.findall(r"\bs\.(\w+)", line)) - keys
    assert "${num(s.fresh)} fresh</span>" in line and "${num(s.aging)} aging</span>" in line


def test_a_red_card_labels_each_state_the_server_gives():
    """M6267: Dagorlad's red card (its proof chip) knows every state, the fresh one « fresh »."""
    table = _table((STATIC / "dagorlad.js").read_text(encoding="utf-8"), "const PROOF = {")
    labels = dict(re.findall(r"(\w+): \['[\w-]*', '([^']+)'\]", table))
    assert set(labels) == _server_states() | {"unknown"}
    assert labels["fresh"] == "fresh"


def _shown(text: str) -> str:
    """A page's script or markup without its comments: what it may write."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def test_no_page_of_the_console_writes_proven():
    """M6268 (the overview's words too): the console writes « proven » for the catalogue's
    status only — and no page writes the status word itself: it shows ``r.status`` as the
    server sends it. A word « proven » in a page's code is the freshness come back."""
    found = {}
    for path in sorted([*STATIC.glob("*.js"), *STATIC.glob("*.html")]):
        hits = [ln for ln in _shown(path.read_text(encoding="utf-8")).splitlines()
                if re.search(r"\bproven\b", ln, re.I)]
        if hits:
            found[path.name] = hits
    assert found == {}


def test_eregion_coverage_says_fresh_and_never_proven(monkeypatch):
    """M6268: the command's table and its last line — the state as the server gives it."""
    from eregion_console.cli import cli
    now = NOW
    proof = {"run_id": "r1", "at": "2033-05-18T03:33:20+00:00", "age_s": 5 * 86400}
    matrix = {
        "techniques": [{"id": "T1110.001", "state": _state(5), "in_catalog": True, "history": [],
                        "last_run": {"at": proof["at"], "outcome": "detected"}, "last_proof": proof}],
        "faults": [],
        "summary": {"techniques": {"implemented": 1, "fresh": 1, "aging": 0, "stale": 0, "unproven": 0,
                                   "never": 0, "regressed": []},
                    "faults": {"regressed": []}},
        "evolution": [], "window_days": 30, "future": []}
    monkeypatch.setattr(api, "coverage_matrix", lambda now=now: matrix)
    out = CliRunner().invoke(cli, ["coverage"])
    assert out.exit_code == 0, out.output
    assert re.search(r"T1110\.001\s+fresh\s", out.output), out.output
    assert not re.search(r"\bproven\b", out.output, re.I), out.output


# ── No reader of the matrix outside the console ───────────────────────────────────────

# What reads the matrix: its route, its module, its CLI, the board's route that carries its states.
_ENTRIES = ("/api/coverage", "eregion_console.coverage", "eregion_console import coverage",
            "coverage_matrix", "eregion coverage", "/api/dagorlad/board", "board.proofs")
# Where a word about it is no reader: the console itself, the tests, the prose (docs, changes,
# the CHANGELOG, the roles' files) and the mutants, which copy the console's lines.
_NOT_READERS = ("eregion_console/", "tests/", "docs/", "changes/", "scripts/mutants/")
_NOT_READER_FILES = ("scripts/mutation_check.py",)


def test_only_the_console_reads_the_matrix_so_its_value_was_renamed():
    """M6270: the state's value changed with its label (FRS1, the sheet's step 3) because no
    other component reads it. A file tracked outside the console (git's list, or the tree in
    the mutants' copy: tests/unit/tracked_files.py) that names the matrix's
    route, module or command is a reader the rename would break: it fails here."""
    readers = {}
    for rel in tracked(REPO):
        if rel.startswith(_NOT_READERS) or rel in _NOT_READER_FILES or rel.endswith(".md"):
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        if hits := [e for e in _ENTRIES if e in text]:
            readers[rel] = hits
    assert readers == {}, f"a reader of the coverage matrix outside the console: {readers}"
