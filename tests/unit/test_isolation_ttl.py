"""TTL1 (#812): the isolation's TTL read in one place, for the watch and for `check-ttl`.

Found by JUG2d's review. The TTL came two ways that did not agree on 0: `GLORFINDEL_ISOLATION_TTL_H=0`
escalated every isolation at once (`float("0")` is 0), while `check-ttl --ttl 0` was silently the
variable or 4 h (`ttl or …`). A negative value passed too, and an unreadable variable raised a
ValueError that stopped the watch at its start.

Jonathan's decision (14/11): 0 keeps its meaning, « escalate everything », by the option as by the
variable; only negative values are refused. `check-ttl` refuses a negative or unreadable TTL (its
reason, code 1, nothing escalated); the watch never stops for a TTL: it says it, and keeps 4 h.
`reassert.ttl_alerts` is unchanged: it escalates, it releases nothing (Q1).

No cloud call, no model call: the isolations are state files under the throwaway home.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from glorfindel import config, escalations
from glorfindel.actions import _load_isolation_state, _save_isolation_state, active_isolations
from glorfindel.cli import _watch_ttl_h, cli

ROOT = Path(__file__).resolve().parents[2]
ENV = "GLORFINDEL_ISOLATION_TTL_H"
_WEB = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/web"


@pytest.fixture(autouse=True)
def _no_ttl(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)


def _isolated(minutes_ago: float = 1.0) -> None:
    """`web`, isolated a minute ago: far under the 4 h default, past a TTL of 0."""
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    _save_isolation_state("web", {"resource_id": _WEB, "isolated_at": since.isoformat(), "placements": []})


def _ttl_cards() -> list[dict]:
    return [e for e in escalations.pending() if e["escalation_type"] == "ttl_exceeded"]


def _check_ttl(*args: str):
    return CliRunner().invoke(cli, ["check-ttl", *args])


# ── the one reading ───────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,ttl", [(None, 4.0), ("", 4.0), ("  ", 4.0), ("0", 0.0), ("0.0", 0.0),
                                     ("2.5", 2.5), (" 8 ", 8.0), ("-0", 0.0)])
def test_the_variable_read(raw, ttl, monkeypatch):
    if raw is not None:
        monkeypatch.setenv(ENV, raw)
    assert config.isolation_ttl_h() == ttl


@pytest.mark.parametrize("raw,why", [("-1", "négatif"), ("-0.01", "négatif"), ("abc", "illisible"),
                                     ("4h", "illisible"), ("nan", "illisible"), ("4,5", "illisible")])
def test_a_negative_or_unreadable_variable_is_refused(raw, why, monkeypatch):
    monkeypatch.setenv(ENV, raw)
    with pytest.raises(config.TTLRefused) as refused:
        config.isolation_ttl_h()
    assert why in str(refused.value) and ENV in str(refused.value)


@pytest.mark.parametrize("env", [None, "8", "-1", "abc"])
def test_the_option_wins_when_given_zero_included(env, monkeypatch):
    """`--ttl 0` is 0, not the variable nor 4 h — and the variable is not read at all once it is given."""
    if env is not None:
        monkeypatch.setenv(ENV, env)
    assert config.isolation_ttl_h(0.0) == 0.0
    assert config.isolation_ttl_h(3.0) == 3.0


@pytest.mark.parametrize("option,why", [(-1.0, "négatif"), (-0.5, "négatif"), (float("nan"), "illisible")])
def test_a_negative_option_is_refused(option, why):
    with pytest.raises(config.TTLRefused) as refused:
        config.isolation_ttl_h(option)
    assert why in str(refused.value) and "--ttl" in str(refused.value)


# ── check-ttl ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("env", [None, "8"])
def test_check_ttl_zero_escalates_every_isolation_at_once(env, monkeypatch):
    """`--ttl 0` as the variable at 0: the isolation of a minute ago escalated now — the option wins
    over a variable of 8 h. Escalated, never released (Q1): its state stays, marked alerted."""
    if env is not None:
        monkeypatch.setenv(ENV, env)
    _isolated()
    r = _check_ttl("--ttl", "0")
    assert r.exit_code == 0, r.output
    [card] = _ttl_cards()
    assert card["resource_id"] == _WEB and card["action"] == "review_isolation"
    assert [i["resource_id"] for i in active_isolations()] == [_WEB]       # still isolated
    assert _load_isolation_state(_WEB)["ttl_alerted_at"]
    assert "escalated, not released" in r.output


def test_check_ttl_with_the_variable_at_zero_does_the_same(monkeypatch):
    monkeypatch.setenv(ENV, "0")
    _isolated()
    r = _check_ttl()
    assert r.exit_code == 0, r.output
    assert len(_ttl_cards()) == 1 and [i["resource_id"] for i in active_isolations()] == [_WEB]


def test_check_ttl_without_a_ttl_keeps_four_hours():
    _isolated()
    r = _check_ttl()
    assert r.exit_code == 0, r.output
    assert _ttl_cards() == [] and "older than 4.0h" in r.output


@pytest.mark.parametrize("args,env", [(("--ttl", "-1"), None), (("--ttl=-0.5",), None),
                                      (("--ttl", "-1", "--dry-run"), None), ((), "-2"), ((), "abc"),
                                      ((), "nan"), (("--dry-run",), "abc")])
def test_check_ttl_refuses_a_negative_or_unreadable_ttl(args, env, monkeypatch):
    """Refused with its reason, code 1, nothing escalated — the isolation untouched."""
    if env is not None:
        monkeypatch.setenv(ENV, env)
    _isolated(minutes_ago=60 * 24)                    # past any TTL a refusal could fall back to
    r = _check_ttl(*args)
    assert r.exit_code == 1, r.output
    assert "TTL refusé" in r.output and "rien n'est escaladé" in r.output
    assert ("négatif" if (env or "-").startswith("-") else "illisible") in r.output
    assert _ttl_cards() == [] and "ttl_alerted_at" not in _load_isolation_state(_WEB)


def test_check_ttl_s_option_wins_over_an_unreadable_variable(monkeypatch):
    monkeypatch.setenv(ENV, "abc")
    _isolated()
    r = _check_ttl("--ttl", "5")
    assert r.exit_code == 0, r.output
    assert _ttl_cards() == []


# ── the watch ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,ttl", [(None, 4.0), ("0", 0.0), ("2.5", 2.5)])
def test_the_watch_reads_a_valid_ttl_as_it_is(raw, ttl, monkeypatch, capsys):
    if raw is not None:
        monkeypatch.setenv(ENV, raw)
    assert _watch_ttl_h() == ttl
    assert "TTL refusé" not in capsys.readouterr().out


@pytest.mark.parametrize("raw,why", [("-1", "négatif"), ("abc", "illisible"), ("nan", "illisible")])
def test_the_watch_says_a_refused_ttl_and_keeps_four_hours(raw, why, monkeypatch, capsys, caplog):
    monkeypatch.setenv(ENV, raw)
    with caplog.at_level(logging.WARNING, logger="glorfindel.ttl"):
        assert _watch_ttl_h() == config.ISOLATION_TTL_H == 4.0
    out = " ".join(capsys.readouterr().out.split())
    assert "TTL refusé" in out and why in out and "la watch garde 4 h" in out
    [logged] = [r.getMessage() for r in caplog.records if r.name == "glorfindel.ttl"]
    assert why in logged and "la watch garde 4 h" in logged


@pytest.mark.parametrize("raw", ["-1", "abc"])
def test_the_watch_never_stops_for_a_ttl(raw, monkeypatch, tmp_path):
    """The watch goes past its TTL's reading — before, `float(...)` raised before the loop — and says it at
    its start: before the agent is even built."""
    monkeypatch.setenv(ENV, raw)
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [tmp_path / "absent.yaml"])
    runs = tmp_path / "runs"
    runs.mkdir()

    class Started(Exception):
        pass

    def started(*a, **k):
        raise Started("the watch went on")
    monkeypatch.setattr("glorfindel.agent.GlorfindelAgent", started)
    monkeypatch.setattr("glorfindel.actions.migrate_state_files", lambda: 0)
    r = CliRunner().invoke(cli, ["watch", str(runs), "--dry-run"])
    # The CLI says any error as « ✗ <type>: … »: the watch reached the agent, no ValueError before it.
    assert "Started: the watch went on" in r.output and "ValueError" not in r.output, r.output
    assert "TTL refusé" in r.output and "la watch garde 4 h" in " ".join(r.output.split())


def test_the_watch_and_check_ttl_read_the_ttl_by_the_same_function(monkeypatch):
    """One reading (TTL1): `config.isolation_ttl_h`, the option given to it by `check-ttl`."""
    seen: list = []

    def reading(option=None):
        seen.append(option)
        return 7.0
    monkeypatch.setattr(config, "isolation_ttl_h", reading)
    assert _watch_ttl_h() == 7.0
    r = _check_ttl("--ttl", "0")
    assert r.exit_code == 0 and "older than 7.0h" in r.output, r.output
    assert seen == [None, 0.0]


# ── what the doc says ─────────────────────────────────────────────────────────────────────────

def _lines(rel: str, needle: str) -> list[str]:
    return [ln for ln in (ROOT / rel).read_text(encoding="utf-8").splitlines() if needle in ln]


def test_the_help_of_ttl_says_zero_and_negative():
    out = " ".join(_check_ttl("--help").output.split())
    assert "0 escalates every isolation at once" in out and "negative value is refused" in out
    assert "wins over GLORFINDEL_ISOLATION_TTL_H" in out


def test_envrc_readme_and_operations_say_zero_and_negative():
    envrc = (ROOT / ".envrc.example").read_text(encoding="utf-8")
    assert "0 ne désactive rien" in envrc and "négative ou illisible" in envrc and "garde 4 h" in envrc
    [readme] = _lines("README.md", "GLORFINDEL_ISOLATION_TTL_H=4")
    assert "0: every isolation escalated at once" in readme and "negative or unreadable" in readme
    lines = (ROOT / "docs/operations.md").read_text(encoding="utf-8").splitlines()
    [at] = [i for i, ln in enumerate(lines) if "GLORFINDEL_ISOLATION_TTL_H=4" in ln]
    ops = " ".join(ln.lstrip(" #") for ln in lines[at:at + 3])        # the line and its two continuations
    assert "0 : toutes escaladées tout de suite" in ops and "négatif ou illisible" in ops
