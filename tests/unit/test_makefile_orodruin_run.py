"""ORU1 (#608): `make orodruin-run SCENARIO=<name> [DRY_RUN=1]` — play one scenario on an armed
Orodruin, guarded. Read from the Makefile, like tests/unit/test_makefile_campaign.py: no make, no
ssh, no Azure. Plus the session guard (scripts/orodruin_run.py) refusing a code session.
"""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")

_spec = importlib.util.spec_from_file_location(
    "orodruin_run", ROOT / "scripts" / "orodruin_run.py")
orodruin_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(orodruin_run)


def _recipe(target: str) -> list[str]:
    lines = MAKEFILE.splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if ln == f"{target}:" or ln.startswith(f"{target}: "))
    recipe = []
    for line in lines[start + 1:]:
        if not line.startswith("\t"):
            break
        recipe.append(line)
    return recipe


def test_orodruin_run_exists_and_is_phony():
    assert re.search(r"^orodruin-run:( orodruin-known)?$", MAKEFILE, re.M), "orodruin-run missing"
    phony = MAKEFILE.split(".PHONY:", 1)[1].split("\n\n", 1)[0]
    assert "orodruin-run" in phony, "orodruin-run not in .PHONY"


def test_orodruin_run_plays_one_scenario_in_the_orodruin_image():
    run = "\n".join(_recipe("orodruin-run"))
    # the scenario is run by annatar in the pinned Orodruin image, over ssh
    assert "$(ORO_RUN) annatar run $(SCENARIO)" in run
    assert "--yes$(ORO_WITHOUT)" in run
    # DRY_RUN=1 adds --dry-run (no cloud call), nothing otherwise
    assert "$(if $(filter 1,$(DRY_RUN)), --dry-run)" in run
    # a live Glorfindel is needed unless WITHOUT_GLORFINDEL (V1) — carried by ORO_WITHOUT
    assert "$(ORO_WITHOUT)" in run


def test_orodruin_run_guards_before_any_ssh():
    recipe = _recipe("orodruin-run")
    ssh_i = next(i for i, ln in enumerate(recipe) if ln.lstrip("\t").startswith("ssh "))
    guard_i = next(i for i, ln in enumerate(recipe) if "scripts/orodruin_run.py --guard-only" in ln)
    scen_i = next(i for i, ln in enumerate(recipe) if "SCENARIO invalide" in ln)
    # the name is validated, then the session guard runs, both before the ssh
    assert scen_i < ssh_i and guard_i < ssh_i, "a check or the guard runs after the ssh"
    assert any("SCENARIO=<nom de scénario> requis" in ln for ln in recipe[:ssh_i])
    assert any('DRY_RUN invalide' in ln for ln in recipe[:ssh_i])


def test_orodruin_run_has_its_help_line():
    help_ = "\n".join(_recipe("help"))
    assert "make orodruin-run" in help_


def test_guard_refuses_a_code_session(monkeypatch):
    monkeypatch.setenv("EREGION_AGENT_SESSION", "1")
    assert orodruin_run.main(["--guard-only"]) == 1


def test_guard_passes_an_operator_shell(monkeypatch, tmp_path, capsys):
    # not a code session, not a lot's worktree: the guard lets it through (0), says nothing.
    # (``here`` and the cwd are forced to a clean path so this passes from a worktree too.)
    monkeypatch.delenv("EREGION_AGENT_SESSION", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(orodruin_run.bs, "REPO", tmp_path)
    assert orodruin_run.main(["--guard-only"]) == 0
    assert capsys.readouterr().err == ""
