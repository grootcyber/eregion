"""MEM2 (#1027): the precedents by keys and by date, on SQLite, behind a switch off by default.

- **The switch** (``GLORFINDEL_MEMORY``, glorfindel/memory.py): unset or empty, ``distance`` — today's
  memory, ChromaDB; ``cles``, the memory by keys. Any other value keeps today's memory, said once on
  stderr: never no memory, never the watch down (decision of Jonathan of 23/11).
- **Off, nothing changes**: on a case with precedents, the message to the model is the one of
  origin/main before MEM2 (its sha256, measured there, ae373809, on the same memory) — the same cycles,
  in the same order.
- **On**, the model is given the precedents by the keys: the same rule, the same VM, the same
  technique, then the newest; the bounds kept — real cycles only, 90 days (the B2 floor for an undated
  one), one cycle per (signal_id, action, run_id), one per VM.
- **Where**: ``~/.eregion/watch-memory/cycles.sqlite3``, mounted by the watch alone; a folder, or a file
  of another store (ChromaDB's, the analysis index), never opened as the memory.
- **The import** of a copy of the memory by distance, once (Q3): its cycles, their dates and their
  identifiers kept, an undated one left undated; run twice, the same table; a copy of the operator's
  store refused, as scripts/memory_replay.py refuses it.

No Azure call, no model call. Mutants M7024–M7031 (scripts/mutants/MEM2.py) are measured here.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from eregion_core import store_guard
from glorfindel import agent, memory, memory_import, memory_keys
from glorfindel.incidents import IncidentRegistry
from glorfindel.memory import CycleMemory, DistanceMemory
from glorfindel.memory_keys import KeyedMemory

from .memory_both import metas, raw_add

ROOT = Path(__file__).resolve().parents[2]
DAY = 86400
NOW = 1_795_000_000.0          # 2026-11-17, within 90 days of the B2 floor
B2 = memory.B2_FLOOR
SUB = "00000000-0000-0000-0000-0000000000aa"


def _vm(name: str) -> str:
    return f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/{name}"


class _Clock:
    def __init__(self, at: float = NOW):
        self.at = at

    def __call__(self) -> float:
        return self.at


def _cycle(sid: str, vm: str = "", rule: str = "", ttp: str = "T1110.001", **over) -> dict:
    return {"signal_id": sid, "run_id": f"run-{sid}", "ttp": ttp, "severity": "critical", "resource_type": "vm",
            "event": "detection", "reasoning": f"le raisonnement de {sid}", "action": "snapshot", "outcome": "ok",
            "source": "real", "confidence": 0.7, "resource_id": _vm(vm) if vm else "", "rule_name": rule, **over}


def _signal(vm: str = "vm-s", rule: str = "", ttp: str = "T1110.001", **context) -> dict:
    return {"signal_id": "sig-now", "event": "detection", "ttp": ttp, "severity": "critical", "resource_type": "vm",
            "provider": "azure", "resource_id": _vm(vm), "context": {"rule_name": rule, **context}, "raw_signal": {}}


def _keyed(tmp_path, clock=None, **kw) -> KeyedMemory:
    return CycleMemory(path=tmp_path / "keys.sqlite3", clock=clock or _Clock(), mode=memory.KEYS, **kw)


def _at(mem, clock: _Clock, cycle: dict, ago: float) -> None:
    now = clock.at
    clock.at = now - ago
    mem.store(cycle)
    clock.at = now


def _ids(found) -> list[str]:
    return [c["signal_id"] for c in found]


# ── 1. Off, the message to the model is today's, to the byte ─────────────────────────────────────

SIGNAL = {"signal_id": "sig-now", "event": "detection", "ttp": "T1110.001", "severity": "critical",
          "resource_type": "vm", "provider": "azure", "resource_id": _vm("vm-c"),
          "context": {"rule_name": "ssh-brute-force", "run_id": "watch-ssh-now"}, "raw_signal": {}}
# Five cycles, none of the signal's rule nor VM: the last key decides — the distance, or the keys.
FROZEN = [
    ("a-near-old", "vm-a", "sudo-privilege-escalation", "T1110.001", "critical", "detection", 10 * DAY),
    ("b-far-new", "vm-b", "", "T1548.003", "high", "detection", 1 * DAY),
    ("d-same-ttp-new", "vm-d", "", "T1110.001", "medium", "detection_timeout", 2 * DAY),
    ("e-other", "vm-e", "", "T1041", "low", "detection", 3 * 3600),
    ("f-other", "vm-f", "", "T1486", "high", "detection", 5 * DAY),
]
# Measured on origin/main (ae373809) before MEM2, the same memory, the same signal: the message
# `_build_user_message` writes with the precedents `load_context` gives.
FROZEN_SHA256 = "216c71d3da470356dd9f3c6516c35fd189c941361730692148a36186a4dd6f7d"
FROZEN_ORDER = ["a-near-old", "d-same-ttp-new", "e-other"]


def _frozen_memory(path, mode=None):
    clock = _Clock()
    mem = CycleMemory(path=path, clock=clock, mode=mode)
    for sid, vm, rule, ttp, severity, event, ago in FROZEN:
        _at(mem, clock, {"signal_id": sid, "run_id": f"run-{sid}", "ttp": ttp, "severity": severity,
                         "resource_type": "vm", "event": event, "reasoning": f"le raisonnement de {sid}",
                         "action": "snapshot", "outcome": "ok", "source": "real", "confidence": 0.7,
                         "resource_id": _vm(vm), "rule_name": rule}, ago)
    return mem


def _message(tmp_path, mem) -> tuple[list[str], str]:
    out = agent.load_context({"signal": SIGNAL, "past_cycles": [], "incident": None}, memory=mem,
                             incidents=IncidentRegistry(path=tmp_path / "inc.jsonl"))
    return _ids(out["past_cycles"]), agent._build_user_message(SIGNAL, out["past_cycles"])


@pytest.mark.parametrize("switch", [None, "", "distance", " distance "])
def test_off_the_message_to_the_model_is_todays_to_the_byte(tmp_path, monkeypatch, switch):
    """M7030: the switch off — unset, empty, `distance` — opens the memory by distance, ChromaDB: the
    precedents and the message of before MEM2, to the byte."""
    if switch is not None:
        monkeypatch.setenv(memory.SWITCH, switch)
    mem = _frozen_memory(tmp_path / "cycles")
    assert type(mem) is DistanceMemory
    order, message = _message(tmp_path, mem)
    assert order == FROZEN_ORDER
    assert hashlib.sha256(message.encode()).hexdigest() == FROZEN_SHA256


def test_on_the_model_is_given_the_precedents_by_the_keys(tmp_path, monkeypatch):
    """The same memory by keys: the cycles of the signal's technique first, the newest first, then the
    newest of the others — the same format, other cycles (what MEM-H measures, what ENQ5 switches on)."""
    monkeypatch.setenv(memory.SWITCH, "cles")
    mem = _frozen_memory(tmp_path / "keys.sqlite3")
    assert type(mem) is KeyedMemory
    order, message = _message(tmp_path, mem)
    assert order == ["d-same-ttp-new", "a-near-old", "e-other"]
    assert hashlib.sha256(message.encode()).hexdigest() != FROZEN_SHA256
    off = _message(tmp_path, _frozen_memory(tmp_path / "cycles", mode=memory.DISTANCE))[1]
    assert message.split("## Cycles passés similaires")[0] == off.split("## Cycles passés similaires")[0]
    assert message.count("**Cycle ") == off.count("**Cycle ") == 3


# ── 2. The switch: read, and never a reason for no memory ────────────────────────────────────────

@pytest.mark.parametrize("raw, mode, said", [
    (None, "distance", False), ("", "distance", False), ("  ", "distance", False),
    ("distance", "distance", False), ("cles", "cles", False), (" cles\n", "cles", False),
    ("clés", "distance", True), ("CLES", "distance", True), ("keys", "distance", True),
    ("1", "distance", True), ("off", "distance", True), ("cles,distance", "distance", True),
])
def test_the_switch_names_a_memory_and_says_an_unknown_value(raw, mode, said):
    env = {} if raw is None else {memory.SWITCH: raw}
    got, text = memory.memory_mode(env)
    assert got == mode
    assert bool(text) is said
    if said:
        assert text.startswith(f"{memory.SWITCH}=") and "inconnu" in text and "distance" in text


def test_an_unknown_switch_keeps_todays_memory_and_says_it_once(tmp_path, monkeypatch, capsys):
    """M7031: an unreadable switch cut the memory — the watch fell, or decided without precedent."""
    monkeypatch.setattr(memory, "_said_switch", set())
    monkeypatch.setenv(memory.SWITCH, "clés\x1b[31m")
    mem = CycleMemory(path=tmp_path / "cycles")
    assert type(mem) is DistanceMemory and mem.mode == memory.DISTANCE
    mem.store(_cycle("one", vm="vm-a"))
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["one"]
    CycleMemory(path=tmp_path / "cycles")
    err = capsys.readouterr().err
    assert err.count("inconnu") == 1 and "\x1b" not in err
    assert "la mémoire d'aujourd'hui (distance) est gardée" in err


def test_the_watchs_agent_opens_the_memory_the_switch_names(tmp_path, monkeypatch):
    off = agent.GlorfindelAgent(memory_path=str(tmp_path / "cycles"), dry_run=True, readiness_gate=False)
    assert type(off.memory) is DistanceMemory
    monkeypatch.setenv(memory.SWITCH, "cles")
    on = agent.GlorfindelAgent(dry_run=True, readiness_gate=False)
    assert type(on.memory) is KeyedMemory and on.memory.path == memory_keys.DEFAULT_PATH
    assert on.memory.max_age_days == 90
    monkeypatch.setenv(memory.SWITCH, "nonsense")
    assert type(agent.GlorfindelAgent(memory_path=str(tmp_path / "cycles"), dry_run=True,
                                      readiness_gate=False).memory) is DistanceMemory


def test_a_mode_given_badly_is_refused():
    with pytest.raises(ValueError, match="distance ou cles"):
        CycleMemory(mode="keys")


# ── 3. The rank: the rule, the VM, the technique, then the newest ────────────────────────────────

def test_a_cycle_of_the_signals_technique_comes_before_a_newer_one_of_another(tmp_path):
    """M7024: the technique out of the keys — the newest of any technique came first."""
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    _at(mem, clock, _cycle("same-ttp-old", vm="vm-a"), 30 * DAY)
    _at(mem, clock, _cycle("other-ttp-new", vm="vm-b", ttp="T1041"), 1 * DAY)
    assert _ids(mem.retrieve_similar(_signal(), n=1)) == ["same-ttp-old"]
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["same-ttp-old", "other-ttp-new"]
    assert _ids(mem.retrieve_similar(_signal(ttp="T1041"), n=1)) == ["other-ttp-new"]


def test_the_newest_comes_first_never_the_oldest_nor_the_order_of_the_store(tmp_path):
    """M7025: an old order (or the distance) in place of the newest. Stored out of their order: the
    newest by its date, then the others by theirs."""
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    _at(mem, clock, _cycle("middle", vm="vm-a"), 5 * DAY)
    _at(mem, clock, _cycle("newest", vm="vm-b", severity="low", event="detection_timeout"), 1 * DAY)
    _at(mem, clock, _cycle("oldest", vm="vm-c"), 20 * DAY)
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["newest", "middle", "oldest"]
    assert _ids(mem.retrieve_similar(_signal(), n=1)) == ["newest"]


def test_at_equal_dates_the_one_stored_last_comes_first(tmp_path):
    mem = _keyed(tmp_path)
    for sid in ("first", "second", "third"):
        raw_add(mem, f"cycle-{sid}", f"TTP: T1110.001 | {sid}", {"source": "real", "signal_id": sid,
                                                                  "action": "x", "run_id": "r", "ttp": "T1110.001",
                                                                  "resource_id": _vm(f"vm-{sid}").lower()})
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["third", "second", "first"]


def test_the_rule_then_the_vm_then_the_technique(tmp_path):
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    _at(mem, clock, _cycle("same-ttp", vm="vm-a"), 1 * DAY)
    _at(mem, clock, _cycle("same-vm", vm="vm-s", ttp="T1041"), 2 * DAY)
    _at(mem, clock, _cycle("same-rule", vm="vm-b", rule="ssh-brute-force", ttp="T1041"), 3 * DAY)
    assert _ids(mem.retrieve_similar(_signal(rule="ssh-brute-force"), n=3)) == ["same-rule", "same-vm", "same-ttp"]
    # Attributed to no VM: its anchor weighs nothing.
    unattributed = _signal(rule="ssh-brute-force", attribution="unattributed")
    assert _ids(mem.retrieve_similar(unattributed, n=3)) == ["same-rule", "same-ttp", "same-vm"]


def test_one_place_per_vm_whatever_floods_it(tmp_path):
    """M7026: the bound of one precedent per VM dropped — a VM whose local account provokes detections
    filled every place, its own and its neighbours' (SEC-I)."""
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    for i in range(20):
        _at(mem, clock, _cycle(f"flood-{i}", vm="vm-a"), i * 60)
    _at(mem, clock, _cycle("b-own", vm="vm-b"), 10 * DAY)
    found = mem.retrieve_similar(_signal(vm="vm-c"), n=3)
    assert _ids(found) == ["flood-0", "b-own"]
    assert _ids(mem.retrieve_similar(_signal(vm="vm-a"), n=3)) == ["flood-0", "b-own"]


def test_cycles_that_name_no_vm_count_as_one_vm_unknown(tmp_path):
    mem = _keyed(tmp_path)
    for i in range(5):
        raw_add(mem, f"cycle-legacy-{i}", f"TTP: T1110.001 | legacy {i}",
                {"source": "real", "signal_id": f"legacy-{i}", "action": "x", "run_id": "r", "ttp": "T1110.001",
                 "stored_at": int(NOW) - i})
    mem.store(_cycle("b-own", vm="vm-b"))
    assert sorted(_ids(mem.retrieve_similar(_signal(), n=3))) == ["b-own", "legacy-0"]


def test_a_cycle_older_than_the_bound_is_no_precedent(tmp_path):
    """M7027: the age out of the search — a year-old decision weighed as much as yesterday's."""
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    _at(mem, clock, _cycle("a-year-ago", vm="vm-a"), 365 * DAY)
    _at(mem, clock, _cycle("day-91", vm="vm-b"), 91 * DAY)
    _at(mem, clock, _cycle("day-89", vm="vm-c"), 89 * DAY)
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["day-89"]
    assert mem.count() == 3                                   # nothing erased
    assert _ids(_keyed(tmp_path, clock, max_age_days=400).retrieve_similar(_signal(), n=3)) == [
        "day-89", "day-91", "a-year-ago"]
    assert mem.age_census() == {"max_age_days": 90.0, "real": 3, "within": 1, "too_old": 2, "b2_dated": 0,
                                "b2_floor": "2026-10-16"}


def test_an_undated_cycle_takes_the_b2_floor(tmp_path):
    clock = _Clock(B2 + 10 * DAY)
    mem = _keyed(tmp_path, clock)
    raw_add(mem, "cycle-legacy", "TTP: T1110.001 | legacy", {"source": "real", "signal_id": "legacy",
                                                               "action": "x", "run_id": "r", "ttp": "T1110.001"})
    mem.store(_cycle("dated", vm="vm-a"))
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["dated", "legacy"]
    clock.at = B2 + 91 * DAY
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["dated"]
    assert mem.age_census()["b2_dated"] == 1


def test_an_exercise_or_a_cycle_of_unknown_source_is_never_a_precedent(tmp_path):
    """M7028: an exercise's cycle given — what the model reads would tell it the bench's drills (SEC4a)."""
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    _at(mem, clock, _cycle("drill", vm="vm-a", source="exercise"), 60)
    _at(mem, clock, _cycle("unknown", vm="vm-b", source=""), 60)
    _at(mem, clock, _cycle("real", vm="vm-c"), 5 * DAY)
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["real"]
    assert mem.retrieve_similar(_signal(exercise_run="x"), n=3)[0]["source"] == "real"
    assert mem.age_census()["real"] == 1


def test_the_copies_of_a_replayed_cycle_are_folded(tmp_path):
    """M7029: a copy not folded — a `respond` replayed on the same file stores its cycles again, and
    the same cycle filled the places."""
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    for ago in (60, 120, 180):
        _at(mem, clock, _cycle("replayed", vm="vm-a"), ago)
    # The same cycle stored before SEC-I, by the same run replayed: it named no VM — the bound per VM
    # does not hold it, the fold does.
    raw_add(mem, "cycle-replayed-before-sec-i", memory._cycle_to_text(_cycle("replayed")),
            {"source": "real", "signal_id": "replayed", "action": "snapshot", "run_id": "run-replayed",
             "ttp": "T1110.001", "stored_at": int(NOW) - 240})
    _at(mem, clock, _cycle("other", vm="vm-b"), DAY)
    assert _ids(mem.retrieve_similar(_signal(), n=3)) == ["replayed", "other"]
    assert mem.count() == 5


def test_both_memories_keep_the_same_metadata_and_give_the_same_shape(tmp_path):
    cycle = _cycle("one", vm="VM-A", rule="ssh-brute-force", past_cycles_used=["x"], exercise_run="")
    found = {}
    for mode, path in ((memory.DISTANCE, tmp_path / "cycles"), (memory.KEYS, tmp_path / "keys.sqlite3")):
        mem = CycleMemory(path=path, clock=_Clock(), mode=mode)
        mem.store(cycle)
        [meta] = metas(mem)
        [found[mode]] = mem.retrieve_similar(_signal(vm="vm-a"), n=3)
        assert meta["resource_id"] == _vm("vm-a").lower() and meta["corroborated"] is False
        assert meta["stored_at"] == int(NOW)
    assert found[memory.DISTANCE] == found[memory.KEYS]
    assert found[memory.KEYS]["summary"] == memory._cycle_to_text(cycle)


def test_the_replay_measures_the_code_of_the_keys(tmp_path):
    """scripts/memory_replay.py's ranking `keys` is `memory_keys.choose`: what the memory gives."""
    mem = _frozen_memory(tmp_path / "keys.sqlite3", mode=memory.KEYS)
    with mem._db() as db:
        rows = list(db.execute("SELECT seq, rule_name, resource_id, ttp, stored_at, signal_id, action, run_id "
                               "FROM cycles"))
    candidates = [{"seq": s, "rule": r, "vm": v, "ttp": t, "at": float(at), "key": (sid, a, run)}
                  for s, r, v, t, at, sid, a, run in rows]
    chosen = memory_keys.choose(candidates, "ssh-brute-force", memory._vm_key(_vm("vm-c")), "T1110.001")
    assert [c["key"][0] for c in chosen] == _ids(mem.retrieve_similar(SIGNAL, n=3))
    replay = (ROOT / "scripts" / "memory_replay.py").read_text()
    assert '"keys": [p["i"] for p in memory_keys.choose(eligible, c["rule"], c["vm"], c["ttp"], n)]' in replay


# ── 4. Where it lives, what it never opens ───────────────────────────────────────────────────────

def test_its_default_lies_where_the_watch_alone_writes():
    """~/.eregion/watch-memory — never under ~/.glorfindel, which the console and the bot mount in
    writing (docker-compose.yml)."""
    source = (ROOT / "glorfindel" / "memory_keys.py").read_text()
    assert 'DEFAULT_PATH = Path.home() / ".eregion" / "watch-memory" / "cycles.sqlite3"\n' in source
    assert memory_keys.DEFAULT_PATH.name == "cycles.sqlite3"     # the suite's, in tmp (conftest)
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())["services"]
    holders = {name for name, s in compose.items()
               if any(v.split(":")[0] == "${HOME}/.eregion/watch-memory" for v in s.get("volumes") or [])}
    assert holders == {"watch"}
    assert "${HOME}/.eregion/watch-memory:/root/.eregion/watch-memory" in compose["watch"]["volumes"]
    assert {name for name, s in compose.items() if memory.SWITCH in (s.get("environment") or {})} == {"watch"}
    assert compose["watch"]["environment"][memory.SWITCH] == "${GLORFINDEL_MEMORY:-}"


def test_its_directory_is_made_before_compose_mounts_it_and_copied_by_the_pull():
    make = (ROOT / "Makefile").read_text()
    for target in ("glorfindel-start:", "glorfindel-restart:", "glorfindel-dev:"):
        block = make.split(f"\n{target}", 1)[1].split("\n\n", 1)[0]
        assert "mkdir -p -m 700 $(HOME)/.eregion/watch-key $(HOME)/.eregion/bot $(HOME)/.eregion/watch-queue " \
               "$(HOME)/.eregion/watch-memory" in block, target
    team = make.split("\nteam-start:", 1)[1].split("\n\n", 1)[0]
    assert '"$(TEAM_DIR)/.eregion/watch-queue" "$(TEAM_DIR)/.eregion/watch-memory"' in team
    deploy = (ROOT / "infra" / "glorfindel-host" / "deploy.sh").read_text()
    start = deploy.split("\nstart() {", 1)[1].split("\n}", 1)[0]
    assert '"$HOME/.eregion/watch-queue" "$HOME/.eregion/watch-memory"' in start
    pull = make.split("\nimladris-pull:", 1)[1].split("\n\n", 1)[0]
    assert "test ! -d .eregion/watch-memory || echo .eregion/watch-memory" in pull


def test_a_folder_or_another_stores_file_is_never_opened_as_the_memory(tmp_path):
    chroma = tmp_path / "cycles"
    CycleMemory(path=chroma, mode=memory.DISTANCE)
    with pytest.raises(memory_keys.NotTheMemory, match="un dossier"):
        CycleMemory(path=chroma, mode=memory.KEYS)
    sqlite = chroma / "chroma.sqlite3"
    was = sqlite.read_bytes()
    with pytest.raises(memory_keys.NotTheMemory, match="d'autres tables"):
        CycleMemory(path=sqlite, mode=memory.KEYS)
    assert sqlite.read_bytes() == was
    other = tmp_path / "index.sqlite"
    db = sqlite3.connect(other)
    with db:
        db.execute("CREATE TABLE campaign_runs (seq INTEGER PRIMARY KEY, run_id TEXT)")
    db.close()
    was = other.read_bytes()
    with pytest.raises(memory_keys.NotTheMemory, match="campaign_runs"):
        CycleMemory(path=other, mode=memory.KEYS)
    assert other.read_bytes() == was
    assert memory_keys.age_census(path=other)["error"].startswith("NotTheMemory")


def test_its_census_makes_no_memory_where_there_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv(memory.SWITCH, "cles")
    where = tmp_path / "never" / "cycles.sqlite3"
    assert memory.age_census(path=where) == {"max_age_days": 90.0, "absent": True}
    assert not where.parent.exists()
    assert memory.age_census() == {"max_age_days": 90.0, "absent": True}
    assert not memory_keys.DEFAULT_PATH.exists()


def test_the_operators_memory_is_refused_in_an_agent_session(tmp_path, monkeypatch):
    """HY2b: in an agent session the operator's ~/.eregion is refused before it is opened."""
    operator = tmp_path / "operator"
    monkeypatch.setattr(store_guard, "guarded", lambda: store_guard.roots_of(operator))
    monkeypatch.setattr(store_guard, "_installed", {"why": "test", "roots": store_guard.roots_of(operator)})
    target = operator / ".eregion" / "watch-memory" / "cycles.sqlite3"
    with pytest.raises(store_guard.Refused):
        CycleMemory(path=target, mode=memory.KEYS)
    assert not target.parent.exists()


# ── 5. What is said: memory-stats, the report, the watch ─────────────────────────────────────────

def test_memory_stats_says_the_memory_the_switch_opens(tmp_path, monkeypatch):
    from glorfindel.cli import cli
    res = CliRunner().invoke(cli, ["memory-stats"])
    assert res.exit_code == 0, res.output
    said = " ".join(res.output.split())
    assert "Cycles in memory: 0" in said and "memory by distance (ChromaDB)" in said
    monkeypatch.setenv(memory.SWITCH, "cles")
    mem = CycleMemory()
    mem.store(_cycle("one", vm="vm-a"))
    res = CliRunner().invoke(cli, ["memory-stats"])
    assert res.exit_code == 0, res.output
    said = " ".join(res.output.split())
    assert "Cycles in memory: 1" in said and "memory by keys (SQLite, GLORFINDEL_MEMORY=cles)" in said
    assert "Memory: 1 real cycle(s), 1 within 90 days" in said
    res = CliRunner().invoke(cli, ["report", "--since", "all", "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["memory"]["real"] == 1


def test_the_watch_says_the_memory_by_keys_and_nothing_when_off(tmp_path):
    from rich.console import Console

    from glorfindel.watch import startup
    console = Console(record=True, width=200)
    startup._say_memory(console, CycleMemory(path=tmp_path / "cycles", mode=memory.DISTANCE))
    startup._say_memory(console, None)
    assert console.export_text() == ""
    startup._say_memory(console, _keyed(tmp_path))
    said = console.export_text()
    assert "Memory: memory by keys (SQLite, GLORFINDEL_MEMORY=cles)" in said and "keys.sqlite3" in said


# ── 6. The import of a copy, once ────────────────────────────────────────────────────────────────

def _chroma_copy(tmp_path) -> Path:
    """A memory by distance written by the real code, then copied — as make imladris-pull brings one."""
    clock = _Clock()
    orig = tmp_path / "orig"
    mem = CycleMemory(path=orig, clock=clock, mode=memory.DISTANCE)
    _at(mem, clock, _cycle("new", vm="vm-a"), 1 * DAY)
    _at(mem, clock, _cycle("old", vm="vm-b", rule="ssh-brute-force"), 30 * DAY)
    _at(mem, clock, _cycle("drill", vm="vm-c", source="exercise"), 2 * DAY)
    raw_add(mem, "cycle-legacy", "TTP: T1110.001 | legacy", {"source": "real", "signal_id": "legacy",
                                                               "action": "x", "run_id": "r", "ttp": "T1110.001"})
    copy = tmp_path / "copy" / "cycles"
    shutil.copytree(orig, copy)
    return copy


def test_the_import_brings_every_cycle_its_date_and_its_id_once(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
    copy, dest = _chroma_copy(tmp_path), tmp_path / "out" / "cycles.sqlite3"
    said: list[str] = []
    assert memory_import.run(copy, dest, say=said.append) == 0
    assert "4 cycle(s), dont 3 réel(s) et 1 sans date" in said[1] and said[2].startswith("4 cycle(s) importé(s) ; 0")
    mem = KeyedMemory(path=dest, clock=_Clock())
    got = {m["signal_id"]: m for m in metas(mem)}
    assert set(got) == {"new", "old", "drill", "legacy"}
    assert got["new"]["stored_at"] == int(NOW - DAY) and "stored_at" not in got["legacy"]
    # The order of their dates: the undated one (the B2 floor) first.
    assert [m["signal_id"] for m in metas(mem)] == ["legacy", "old", "drill", "new"]
    with mem._db() as db:
        ids = {r[0] for r in db.execute("SELECT id FROM cycles")}
    chroma = DistanceMemory(path=copy)._collection.get()["ids"]
    assert ids == set(chroma)
    assert _ids(mem.retrieve_similar(_signal(rule="ssh-brute-force"), n=3)) == ["old", "new", "legacy"]
    # Run twice: the same table, the import recorded each time.
    said.clear()
    assert memory_import.run(copy, dest, say=said.append) == 0
    assert said[2].startswith("0 cycle(s) importé(s) ; 4 déjà dans la table")
    assert mem.count() == 4
    assert [(i["imported"], i["kept"]) for i in mem.imports()] == [(4, 0), (0, 4)]
    assert mem.imports()[0]["source"] == str(copy.resolve())


def test_the_import_refuses_the_operators_store_a_link_to_it_and_what_is_no_store(tmp_path, monkeypatch, capsys):
    operator = tmp_path / "operator"
    monkeypatch.setattr(store_guard, "operator_home", lambda: operator)
    live = operator / ".glorfindel" / "cycles"
    CycleMemory(path=live, mode=memory.DISTANCE)
    dest = tmp_path / "out.sqlite3"
    assert memory_import.main([str(live), "--to", str(dest)]) == 2
    assert "~/.glorfindel de l'opérateur" in capsys.readouterr().out
    linked = tmp_path / "copy-linked"
    linked.mkdir()
    (linked / "chroma.sqlite3").symlink_to(live / "chroma.sqlite3")
    assert memory_import.main([str(linked), "--to", str(dest)]) == 2
    assert "mène par un lien" in capsys.readouterr().out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert memory_import.main([str(empty), "--to", str(dest)]) == 2
    assert "pas la copie d'un magasin" in capsys.readouterr().out and list(empty.iterdir()) == []
    copy = _chroma_copy(tmp_path / "c")
    assert memory_import.main([str(copy), "--to", str(copy / "in.sqlite3")]) == 2
    assert "dans la copie" in capsys.readouterr().out
    assert memory_import.main([str(copy), "--to", str(copy)]) == 2
    assert not dest.exists()


def test_the_import_writes_by_default_into_the_watchs_memory(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONYMIZED_TELEMETRY", raising=False)
    copy = _chroma_copy(tmp_path)
    assert memory_import.main([str(copy)]) == 0
    assert KeyedMemory().count() == 4
    monkeypatch.setenv(memory.SWITCH, "cles")
    assert _ids(CycleMemory(clock=_Clock()).retrieve_similar(_signal(vm="vm-a"), n=1)) == ["new"]

