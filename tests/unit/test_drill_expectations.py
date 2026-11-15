"""The drill of the week and what the watch should see, kept apart and held together (DRL1a,
docs/design/drill-banc.md §1.1, §1.2, §8.1):

- each scheduled drill of drills/ against the catalogue — conditions 1 to 3 of §1.1: implemented,
  non-destructive, a public library — and against its expectations (expectations/<drill>.yaml): one
  per wire, at its rank, of its experiment; each expectation's rule in the shipped base, enabled, of
  the same ttp. A drill that no longer holds fails the PR that breaks it: the catalogue changed, the
  atomic retired, the rule renamed;
- the separation in the structure: the injectors' image copies drills/, never expectations/;
  Glorfindel's copies both; neither eregion_core/scheduled_drill.py nor exercise_runner.py imports
  the expectations' reader — read in a process of its own, transitively;
- the expectations' one reader, exact.

Reads the repository's files: no Azure, no model. Crosses components on purpose (the shared core's
drill, Glorfindel's base of rules, both Dockerfiles): TOGETHER.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from eregion_core import drill as dr
from eregion_core import expectations as ex
from eregion_core.exercise_plan import load_catalog

REPO = Path(__file__).resolve().parents[2]
RULES = REPO / "glorfindel" / "rules" / "azure" / "detection_rules.yaml"


def _scheduled() -> list[dr.Drill]:
    out = [dr.load_file(p, dr.SHIPPED) for p in sorted(dr.shipped_dir().glob("*.yaml"))]
    return [d for d in out if d.schedule is not None]


def _rules() -> dict[str, dict]:
    doc = yaml.safe_load(RULES.read_text(encoding="utf-8")) or {}
    return {r["name"]: r for r in doc.get("rules") or [] if isinstance(r, dict) and r.get("name")}


def test_the_weekly_drill_is_shipped_scheduled_and_has_its_expectations():
    names = {d.name for d in _scheduled()}
    assert "banc-hebdo" in names
    assert {p.stem for p in ex.shipped_dir().glob("*.yaml")} == names


@pytest.mark.parametrize("drill", _scheduled(), ids=lambda d: d.name)
def test_each_wire_of_a_scheduled_drill_holds_against_the_catalogue(drill):
    catalog = load_catalog()
    for w in drill.wires:
        e = catalog.get(w.experiment)
        assert e is not None, w.experiment
        assert e.kind == "technique" and e.status == "implemented", e.id
        assert e.destructive is False, e.id
        assert e.engine in ("atomic", "stratus"), e.id
        assert w.zone == "bench"


@pytest.mark.parametrize("drill", _scheduled(), ids=lambda d: d.name)
def test_each_expectation_names_an_enabled_rule_of_its_ttp_one_per_wire_at_its_rank(drill):
    exp = ex.load_file(ex.shipped_dir() / f"{drill.name}.yaml")
    assert exp.drill == drill.name
    assert [(e.rank, e.experiment) for e in exp.wires] == [(i, w.experiment) for i, w in enumerate(drill.wires, 1)]
    rules = _rules()
    for e in exp.wires:
        rule = rules.get(e.rule)
        assert rule is not None, f"{e.rule} is not a rule of the shipped base"
        assert rule.get("enabled") is True, e.rule
        assert rule.get("ttp") == e.experiment, e.rule


# ── The separation, in the structure ─────────────────────────────────────────────────

def _copied(dockerfile: Path) -> set[str]:
    out, cur = set(), ""
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        if not cur and line.strip().startswith("#"):
            continue
        cur += line.rstrip("\\") + " " if line.endswith("\\") else line
        if line.endswith("\\"):
            continue
        words = cur.split()
        cur = ""
        if words and words[0].upper() in ("COPY", "ADD"):
            out |= {w.rstrip("/") for w in words[1:-1] if not w.startswith("--")}
    return out


def test_the_injectors_image_copies_the_drills_never_the_expectations():
    annatar = _copied(REPO / "annatar" / "Dockerfile")
    assert "drills" in annatar
    assert not any(c == "expectations" or c.startswith("expectations/") or c in (".", "*") for c in annatar)


def test_glorfindels_image_copies_both():
    assert {"drills", "expectations"} <= _copied(REPO / "glorfindel" / "Dockerfile")


@pytest.mark.parametrize("module", ["eregion_core.scheduled_drill", "eregion_core.exercise_runner"])
def test_orodruins_drill_and_runner_never_import_the_expectations_reader(module):
    code = f"import sys; import {module}; print('eregion_core.expectations' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"


# ── The expectations' one reader ─────────────────────────────────────────────────────

def _doc(**over):
    doc = yaml.safe_load((ex.shipped_dir() / "banc-hebdo.yaml").read_text())
    doc.update(over)
    return doc


@pytest.mark.parametrize("over, said", [
    ({"extra": 1}, "never holds"),
    ({"drill": "Banc Hebdo"}, "drill's name"),
    ({"wires": []}, "1 to"),
    ({"wires": [{"rank": 2, "experiment": "T1136.001", "rule": "r", "within_s": 900}]}, "rank"),
    ({"wires": [{"rank": 1, "experiment": "T1136.001", "rule": "r", "within_s": 0}]}, "within_s"),
    ({"wires": [{"rank": 1, "experiment": "T1136.001", "rule": "r", "within_s": True}]}, "within_s"),
    ({"wires": [{"rank": 1, "experiment": "T1136.001", "rule": "R/1", "within_s": 900}]}, "rule"),
    ({"wires": [{"rank": 1, "experiment": "T1136.001", "rule": "r", "within_s": 900, "decision": "x"}]}, "never holds"),
])
def test_the_expectations_reader_refuses_what_they_never_hold(over, said):
    with pytest.raises(ex.ExpectationsRefused, match=said):
        ex.read(_doc(**over))


def test_expectations_are_read_bounded_never_through_a_link_named_for_their_drill(tmp_path):
    (tmp_path / "elsewhere.yaml").write_text(yaml.safe_dump(_doc()))
    (tmp_path / "banc-hebdo.yaml").symlink_to(tmp_path / "elsewhere.yaml")
    with pytest.raises(ex.ExpectationsRefused, match="unreadable"):
        ex.load_file(tmp_path / "banc-hebdo.yaml")
    (tmp_path / "other.yaml").write_text(yaml.safe_dump(_doc()))
    with pytest.raises(ex.ExpectationsRefused, match="holds the expectations"):
        ex.load_file(tmp_path / "other.yaml")
