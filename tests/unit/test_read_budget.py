"""DOS4 (#1138; the maintainer's decisions of 24/11): the reads' budgets, one per service
(`glorfindel/read_budget.py`) — Log Analytics for the detection's KQL, never refused nor delayed; ARM for
the dossier, which takes before it reads; neither takes from the other's; each held said once an episode.
No call reaches Azure: the RulePoller's detector is a stub.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from glorfindel import read_budget
from glorfindel.detection_rules import DetectionRule, RulePoller

ENVS = ("GLORFINDEL_LA_BUDGET_PER_MIN", "GLORFINDEL_ARM_BUDGET_PER_MIN")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for env in ENVS + ("GLORFINDEL_READ_BUDGET_PER_MIN",):
        monkeypatch.delenv(env, raising=False)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _budgets(monkeypatch, clock=None):
    clock = clock or Clock()
    la = read_budget.ReadBudget("Log Analytics", ENVS[0], 120, clock=clock)
    arm = read_budget.ReadBudget("ARM", ENVS[1], 60, floor=read_budget.MINIMUM, clock=clock)
    monkeypatch.setattr(read_budget, "LOG_ANALYTICS", la)
    monkeypatch.setattr(read_budget, "ARM", arm)
    return la, arm, clock


def test_two_budgets_each_with_its_variable_and_its_default(monkeypatch):
    assert read_budget.LOG_ANALYTICS.per_min() == 120 and read_budget.ARM.per_min() == 60
    assert read_budget.LOG_ANALYTICS.env == "GLORFINDEL_LA_BUDGET_PER_MIN"
    assert read_budget.ARM.env == "GLORFINDEL_ARM_BUDGET_PER_MIN"
    monkeypatch.setenv(ENVS[1], "12")
    assert read_budget.ARM.per_min() == 12
    monkeypatch.setenv(ENVS[1], "0")
    assert read_budget.ARM.per_min() == 0 and not read_budget.ARM.take(1)
    for raw in ("beaucoup", "-4"):
        monkeypatch.setenv(ENVS[1], raw)
        assert read_budget.ARM.per_min() == 60 and "le défaut" in read_budget.ARM.note()
    assert not hasattr(read_budget, "per_min") and not hasattr(read_budget, "BUDGET")


def test_an_arm_budget_under_one_pass_is_raised_to_it_and_said_at_the_start(monkeypatch):
    """M7339: an ARM budget under one pass of a dossier taken as set — a take of 7 refused on an empty
    minute, forever: no dossier ever reads, a critical one waits for good."""
    from glorfindel import dossier_pass
    assert read_budget.MINIMUM == sum(dossier_pass.CALLS.values())
    monkeypatch.setenv(ENVS[1], "3")
    assert read_budget.ARM.per_min() == read_budget.MINIMUM
    assert read_budget.ReadBudget("ARM", ENVS[1], 60, floor=read_budget.MINIMUM).take(read_budget.MINIMUM)
    said = read_budget.notes()
    assert said == [f"{ENVS[1]}=3 : lu comme 7 lectures par minute (au moins une passe d'un dossier, 7 appels)"]


def test_the_watch_says_the_budgets_raised_at_its_start(monkeypatch):
    import io

    from rich.console import Console

    from glorfindel.watch.housekeeping import Housekeeping
    monkeypatch.setenv(ENVS[1], "2")
    out = io.StringIO()
    Housekeeping(Console(file=out, width=300), threading.Lock(), dry_run=True, mode_override=None,
                 runs_dir="runs", ttl_h=24, emit=lambda *_: None, say_channel=lambda *_: None)
    assert "GLORFINDEL_ARM_BUDGET_PER_MIN=2 : lu comme 7" in out.getvalue()


def test_the_dossier_takes_only_what_the_minute_leaves_and_a_refusal_counts_nothing(monkeypatch):
    _, arm, clock = _budgets(monkeypatch)
    assert arm.take(50) and not arm.take(11) and arm.take(10)
    assert arm.used() == {read_budget.DOSSIER: 60}
    clock.t += read_budget.WINDOW_S + 1
    assert arm.used() == {} and arm.take(60)


def test_the_detection_is_never_refused_on_its_budget(monkeypatch):
    """M7302: the detection's query refused past Log Analytics' budget, like a take."""
    la, _, _ = _budgets(monkeypatch)
    for _ in range(300):
        read_budget.note_detection()                    # past the threshold: never refused
    assert la.used() == {read_budget.DETECTION: 300} and la.held()


def test_the_detection_never_takes_from_arm(monkeypatch):
    la, arm, _ = _budgets(monkeypatch)
    for _ in range(500):
        read_budget.note_detection()
    assert arm.used() == {} and arm.take(read_budget.MINIMUM)
    assert set(la.used()) == {read_budget.DETECTION}


def _poller(det) -> RulePoller:
    rule = DetectionRule(name="disk-write", source="azure_monitor", workspace_id="ws", query="Perf | limit 1",
                         ttp="T1486", resource_id="", auto_apply=True, monitoring_backend_name="law",
                         interval_s=30.0)
    poller = RulePoller([rule], lambda s: None, dry_run=True)
    poller._detector = lambda r: det
    return poller


def test_the_rulepoller_queries_whatever_its_budget_holds_and_notes_its_query(monkeypatch):
    """M7303: the RulePoller asking its budget before its query — a minute past the threshold, the
    detection skips its poll. It is never refused nor slowed."""
    la, arm, _ = _budgets(monkeypatch)
    la.spend(500)
    det = MagicMock()
    det.run_query.return_value = []
    poller = _poller(det)
    started = time.monotonic()
    poller.poll_once(poller._rules[0])
    assert det.run_query.call_count == 1 and time.monotonic() - started < 2
    assert la.used()[read_budget.DETECTION] == 501 and arm.used() == {}


def test_the_count_never_waits_on_a_read():
    b = read_budget.ReadBudget("ARM", ENVS[1], 60)
    done = threading.Event()
    assert b.take(5)
    t = threading.Thread(target=lambda: (b.spend(), done.set()))
    t.start()
    assert done.wait(1)


def test_investigate_notes_its_queries_on_log_analytics(monkeypatch):
    from glorfindel.enquiry import fixed
    la, arm, _ = _budgets(monkeypatch)
    monkeypatch.setattr(fixed, "run_query", lambda ws, q: [])
    vm = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm"
    assert len(fixed.enquire({"MaxWrite": 70e6}, vm, "ws", unattributed=False).readings) == 3
    assert la.used() == {read_budget.DETECTION: 3} and arm.used() == {}
    fixed.enquire({"MaxWrite": 70e6}, vm, "ws", unattributed=True)      # nothing run: nothing noted
    assert la.used() == {read_budget.DETECTION: 3}


def test_a_note_that_fails_never_costs_the_detection(monkeypatch):
    class Broken:
        def spend(self, *a):
            raise RuntimeError("compteur cassé")
    monkeypatch.setattr(read_budget, "LOG_ANALYTICS", Broken())
    read_budget.note_detection()


def test_a_budget_held_is_said_once_an_episode(monkeypatch):
    """M7341: the pressure said at every minute it lasts — the watch's log drowned, the episode lost."""
    la, arm, clock = _budgets(monkeypatch)
    p = read_budget.Pressure((la, arm))
    assert p.lines() == []
    la.spend(130)
    first = p.lines()
    assert len(first) == 1 and "Log Analytics tenu : 130 appel(s)" in first[0] and "DH14" in first[0]
    assert p.lines() == []                                 # the same episode: said once
    assert not arm.take(61)
    assert len(p.lines()) == 1                             # ARM's own episode
    clock.t += read_budget.WINDOW_S + 1
    assert p.lines() == []                                 # both over
    la.spend(130)
    assert len(p.lines()) == 1                             # a new episode: said again
