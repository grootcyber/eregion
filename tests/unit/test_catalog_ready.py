"""STM1g (#894): a catalogue entry ``proven`` (measured on the bench, STM1) counts exactly as an
``implemented`` one in every blue reader — the console's coverage, indicators and board, the
shared core's plan, drills and proposal, Glorfindel's rules proposed — and a ``planned`` one stays
out everywhere. One predicate says it (``eregion_core.experiment.is_ready``); no blue reader
compares the status to ``"implemented"`` alone, which the code read here holds.

No Azure, no LLM: in-memory catalogues and run reports written to a tmp directory.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eregion_core import run_report as rr
from eregion_core.experiment import READY_STATUSES, is_ready
from eregion_core.exercise_plan import Experiment

REPO = Path(__file__).resolve().parents[2]
NOW = 1_800_000_000.0
DAY = 86400.0
READY = ("implemented", "proven")


# ── The predicate ──────────────────────────────────────────────────────────────────────

def test_proven_counts_as_implemented_and_planned_never():
    assert READY_STATUSES == ("implemented", "proven")
    assert is_ready("implemented") and is_ready("proven")
    for status in ("planned", "", None, "Implemented", "proved", 1, ["implemented"], {"implemented": 1}):
        assert not is_ready(status), status


# ── No blue reader compares the status to "implemented" alone ───────────────────────────

# The blue code: Glorfindel, the shared core, the console (its pages' scripts too), the analysis,
# the scripts. Annatar and Gothmog are STM1's (the red session's); the mutants' files and the
# mutation blocks hold the code as it was, on purpose.
BLUE = ("glorfindel", "eregion_core", "eregion_console", "analysis", "scripts")
LEFT_OUT = ("scripts/mutants/", "scripts/mutation_check.py")
_WORD = r"""["']implemented["']"""
# A comparison to the word (==, !=, ===, !==, either side), or a membership in a literal that
# holds it (`in ("implemented", …)`) — the predicate's own tuple aside.
ALONE = re.compile(rf"(?:===?|!==?)\s*{_WORD}|{_WORD}\s*(?:===?|!==?)"
                   rf"|\bin\s*[(\[{{][^)\]}}]*{_WORD}")


def _blue_files():
    for top in BLUE:
        for path in sorted((REPO / top).rglob("*")):
            rel = path.relative_to(REPO).as_posix()
            if path.suffix in (".py", ".js", ".html") and path.is_file() and not rel.startswith(LEFT_OUT):
                yield rel, path


def _alone(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()
            if ALONE.search(line) and "READY_STATUSES =" not in line]


def test_the_reader_of_the_code_sees_each_old_form():
    """The lines this lot changed, as they were: each one is seen."""
    old = [
        'for e in sorted(catalog.values(), key=lambda e: (e.status != "implemented", e.kind)):',
        '    if experiment.status != "implemented":',
        '    implemented = {e["id"] for e in techniques if e.get("status") == "implemented"}',
        "  const rank = r => (r.state === 'regressed' ? 0 : r.status === 'implemented' || r.runs ? 1 : 2);",
        "${r.status && r.status !== 'implemented' ? ' · ' + esc(r.status) : ''}",
        '    if "implemented" == entry.get("status"):',
        '    if entry.get("status") in ("implemented", "planned"):',
        '    if status not in ["implemented"]:',
    ]
    for line in old:
        assert _alone(line), line
    for line in ('READY_STATUSES = ("implemented", "proven")', 't["implemented"] += is_ready(e.status)',
                 '"implemented": sum(1 for r in catalog if is_ready(r["status"]))}',
                 "${Number(s.implemented)} implemented"):
        assert not _alone(line), line


def test_no_blue_reader_compares_the_status_to_implemented_alone():
    found = {rel: hits for rel, path in _blue_files() if (hits := _alone(path.read_text(encoding="utf-8")))}
    assert found == {}, f"compare through eregion_core.experiment.is_ready: {found}"


# Every reader found on origin/main (e0ca688d), by file: how many times it asks the predicate.
# A reader that stops asking it (back to a word, or gone) fails here; a new one is added here.
READERS = {
    "eregion_console/board.py": 3,
    "eregion_console/coverage.py": 5,
    "eregion_console/indicators.py": 1,
    "eregion_core/drill.py": 1,
    "eregion_core/exercise_plan.py": 1,
    "eregion_core/proposal.py": 1,
    "glorfindel/detection_authoring.py": 1,
    # SEC-A4b (#660): the harness's proposal cases, implemented or proven (merged with STM1g).
    "scripts/llm_smoke.py": 1,
}


def test_every_reader_asks_the_one_predicate():
    asked = {rel: path.read_text(encoding="utf-8").count("is_ready(")
             for rel, path in _blue_files() if rel != "eregion_core/experiment.py"}
    assert {rel: n for rel, n in asked.items() if n} == READERS


def test_the_matrix_page_reads_the_servers_word():
    """The page of the matrix (injector.js) ranks, greys and labels a row by the row's ``ready``,
    which the server computes with the predicate — never by the status's word."""
    js = (REPO / "eregion_console/static/injector.js").read_text(encoding="utf-8")
    assert js.count("r.ready || r.runs") == 2
    assert "r.status && !r.ready" in js


# ── The console ────────────────────────────────────────────────────────────────────────

def _entry(status: str, eid="T1053.003", kind="technique", rtype="azure_vm", destructive=False,
           engine="atomic", tactic="persistence") -> Experiment:
    return Experiment(id=eid, kind=kind, name="an entry", resource_type=rtype, status=status,
                      destructive=destructive, engine=engine, tactic=tactic)


def _red(status: str) -> list[dict]:
    from eregion_console import board
    catalog = {e.id: e for e in (_entry("planned", eid="T1003"), _entry(status),
                                 _entry("implemented", eid="T1110.001", tactic="credential-access"))}
    sections = {"sections": [{"id": "annatar", "active": True}, {"id": "gothmog", "active": True}]}
    return board.red_cards(catalog, [], sections)


@pytest.mark.parametrize("status", READY)
def test_the_board_hands_a_proven_card_as_an_implemented_one(status):
    cards = _red(status)
    assert [c["id"] for c in cards] == ["T1053.003", "T1110.001", "T1003"]   # ready first, planned last
    card = cards[0]
    assert card["available"] is True and card["why"] == "" and card["status"] == status
    assert cards[-1]["available"] is False and cards[-1]["why"] == "planned in the catalogue"


def test_the_board_counts_a_proven_entry_of_another_type():
    from eregion_console import board
    catalog = {e.id: e for e in (_entry("proven", eid="a", rtype="storage"),
                                 _entry("implemented", eid="b", rtype="storage"),
                                 _entry("planned", eid="c", rtype="storage"))}
    assert board.other_types(catalog) == [{"type": "storage", "entries": 3, "implemented": 2}]


def _report(tmp: Path, run_id: str, ttp: str, at: float, detection: str = "detected") -> tuple[str, Path]:
    path = tmp / f"{run_id}.json"
    path.write_text(json.dumps({
        "scenario": f"scenario {ttp}", "run_id": run_id, "mitre": ttp, "result": "PASS",
        "metrics": {**rr.identity("technique", "annatar", ttp), "attack_time": at,
                    "detection": detection, "detection_latency_s": 90.0},
        "thresholds": {}, "checks": {}}))
    return run_id, path


def _catalog(status: str) -> list[dict]:
    return [{"kind": "technique", "id": "T1053.003", "status": status, "name": "Cron",
             "resource_type": "azure_vm"},
            {"kind": "technique", "id": "T1003", "status": "planned", "name": "Dump",
             "resource_type": "azure_vm"},
            {"kind": "technique", "id": "T1110.001", "status": "implemented", "name": "Brute force",
             "resource_type": "azure_vm"}]


def _runs(tmp_path: Path) -> list[dict]:
    """A detected run of the entry under test, and one of the planned entry, two days ago."""
    reports = dict((_report(tmp_path, "r1", "T1053.003", NOW - 2 * DAY),
                    _report(tmp_path, "r2", "T1003", NOW - 2 * DAY)))
    return rr.read_reports(reports)


def _matrix(tmp_path: Path, status: str) -> dict:
    from eregion_console import coverage as cov
    return cov.matrix(_runs(tmp_path), [], _catalog(status), NOW)


@pytest.mark.parametrize("status", READY)
def test_the_matrix_counts_a_proven_technique_as_an_implemented_one(tmp_path, status):
    m = _matrix(tmp_path, status)
    row = {r["id"]: r for r in m["techniques"]}
    assert row["T1053.003"]["ready"] is True and row["T1003"]["ready"] is False
    s = m["summary"]["techniques"]
    assert s["catalog"] == 3 and s["implemented"] == 2
    # Counted: the two ready rows (one run, one none), and the planned one only because it ran.
    assert (s["unproven"], s["never"]) == (2, 1)
    assert [x["ttp"] for x in m["stalest"]] == ["T1053.003", "T1110.001"]
    assert m["evolution"][-1]["implemented_detected"] == 1 and m["evolution"][-1]["catalog_detected"] == 2


def test_the_matrix_is_the_same_whether_implemented_or_proven(tmp_path):
    def strip(m):
        for r in m["techniques"]:
            r.pop("status")
        return m
    assert strip(_matrix(tmp_path, "proven")) == strip(_matrix(tmp_path, "implemented"))


@pytest.mark.parametrize("status", READY)
def test_a_proven_technique_never_run_is_a_gap_of_the_proof(status):
    from eregion_console import coverage as cov
    s = cov.matrix([], [], _catalog(status), NOW)["summary"]["techniques"]
    assert s["implemented"] == 2 and s["never"] == 2


def test_a_planned_technique_never_run_is_no_gap_of_the_proof():
    from eregion_console import coverage as cov
    m = cov.matrix([], [], _catalog("planned"), NOW)
    s = m["summary"]["techniques"]
    assert s["implemented"] == 1 and s["never"] == 1
    assert [x["ttp"] for x in m["stalest"]] == ["T1110.001"]


@pytest.mark.parametrize("status", READY)
def test_the_indicators_count_a_proven_technique_as_an_implemented_one(tmp_path, status):
    from eregion_console import indicators as ind
    out = ind.compute(_runs(tmp_path), [], [], _catalog(status), {}, {}, float("inf"), NOW)
    assert out["coverage"]["implemented"] == 2
    assert out["coverage"]["implemented_detected"] == 1 and out["coverage"]["catalog_detected"] == 2
    assert [x["ttp"] for x in out["stalest"]] == ["T1053.003", "T1110.001"]


def test_the_indicators_leave_a_planned_technique_out(tmp_path):
    from eregion_console import indicators as ind
    out = ind.compute(_runs(tmp_path), [], [], _catalog("planned"), {}, {}, float("inf"), NOW)
    assert out["coverage"]["implemented"] == 1 and out["coverage"]["implemented_detected"] == 0


# ── The shared core ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", READY)
def test_the_plan_judges_a_proven_wire_as_an_implemented_one(status):
    from eregion_core.exercise_plan import judge
    catalog = {"T1053.003": _entry(status), "T1003": _entry("planned", eid="T1003")}
    assert judge("T1053.003", "/x/vm", None, catalog=catalog).code != "not_implemented"
    planned = judge("T1003", "/x/vm", None, catalog=catalog)
    assert planned.code == "not_implemented" and "planned in the catalogue" in planned.reason


@pytest.mark.parametrize("status", READY)
def test_a_scheduled_drill_takes_a_proven_technique_as_an_implemented_one(status):
    from eregion_core.drill import eligible
    assert eligible(_entry(status)) == ""
    assert eligible(_entry("planned")) == "T1053.003 is planned in the catalogue"


@pytest.mark.parametrize("status", READY)
def test_annatars_proposal_chains_a_proven_technique_as_an_implemented_one(status):
    from eregion_core.proposal import chain
    catalog = {e.id: e for e in (_entry(status), _entry("planned", eid="T1003"),
                                 _entry("implemented", eid="T1059.004", tactic="execution"))}
    assert chain(catalog) == ["T1059.004", "T1053.003"]


# ── Glorfindel ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status", READY)
def test_glorfindel_proposes_a_rule_for_a_proven_technique_as_an_implemented_one(status):
    from glorfindel.detection_authoring import techniques_needing_rules
    catalog = {"T1053.003": {"ttp": "T1053.003", "status": status},
               "T1003": {"ttp": "T1003", "status": "planned"},
               "T1110.001": {"ttp": "T1110.001", "status": "implemented"}}
    assert [e["ttp"] for e in techniques_needing_rules(catalog, {"T1110.001"})] == ["T1053.003"]
    assert [e["ttp"] for e in techniques_needing_rules(catalog, set(), include_planned=True)] == \
        ["T1053.003", "T1003", "T1110.001"]
