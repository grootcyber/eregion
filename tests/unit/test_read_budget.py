"""DOS4 (#1138; the decision of 24/11): the reads' budget the dossier shares with the detection
(`glorfindel/read_budget.py`) — the detection first, never refused nor delayed; the dossier reads only what
it leaves. No call reaches Azure: the RulePoller's detector is a stub.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from glorfindel import read_budget
from glorfindel.detection_rules import DetectionRule, RulePoller


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv(read_budget.ENV, raising=False)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_a_prudent_value_said_and_adjustable(monkeypatch):
    assert read_budget.per_min() == read_budget.DEFAULT_PER_MIN == 60
    monkeypatch.setenv(read_budget.ENV, "12")
    assert read_budget.per_min() == 12
    monkeypatch.setenv(read_budget.ENV, "0")
    assert read_budget.per_min() == 0 and not read_budget.ReadBudget().take(1)
    for raw in ("beaucoup", "-4"):
        monkeypatch.setenv(read_budget.ENV, raw)
        assert read_budget.per_min() == 60


def test_the_dossier_takes_only_what_the_minute_leaves_and_a_refusal_counts_nothing():
    clock = Clock()
    b = read_budget.ReadBudget(clock)
    assert b.take(50) and not b.take(11) and b.take(10)
    assert b.used() == {read_budget.DOSSIER: 60}
    clock.t += read_budget.WINDOW_S + 1
    assert b.used() == {} and b.take(60)


def test_the_detection_is_never_refused_and_leaves_the_dossier_nothing():
    """M7302: the detection's read asked of the budget like the dossier's — refused past it: the
    detection waits behind the dossier, the shared budget served first-come."""
    b = read_budget.ReadBudget(Clock())
    assert b.take(60)                                  # the dossier took the whole minute
    for _ in range(100):
        b.note()                                       # the detection, past the budget: never refused
    assert b.used() == {read_budget.DOSSIER: 60, read_budget.DETECTION: 100}
    assert not b.take(1)


def _poller(det) -> RulePoller:
    rule = DetectionRule(name="disk-write", source="azure_monitor", workspace_id="ws", query="Perf | limit 1",
                         ttp="T1486", resource_id="", auto_apply=True, monitoring_backend_name="law",
                         interval_s=30.0)
    poller = RulePoller([rule], lambda s: None, dry_run=True)
    poller._detector = lambda r: det
    return poller


def test_the_rulepoller_queries_whatever_the_dossier_took_and_notes_its_read(monkeypatch):
    """M7303: the RulePoller asking the budget before its query — a minute the dossier took whole, the
    detection skips its poll. The detection first: it is never refused nor slowed."""
    b = read_budget.ReadBudget(Clock())
    monkeypatch.setattr(read_budget, "BUDGET", b)
    assert b.take(60)
    det = MagicMock()
    det.run_query.return_value = []
    poller = _poller(det)
    started = time.monotonic()
    poller.poll_once(poller._rules[0])
    assert det.run_query.call_count == 1 and time.monotonic() - started < 2
    assert b.used()[read_budget.DETECTION] == 1
    assert not b.take(1)                               # and the dossier gets nothing of what it noted


def test_the_count_never_waits_on_a_read():
    """The lock is held to count, never across a read: the detection's note goes through while the
    dossier is between its take and its read."""
    b = read_budget.ReadBudget()
    done = threading.Event()
    assert b.take(5)
    t = threading.Thread(target=lambda: (b.note(), done.set()))
    t.start()
    assert done.wait(1)


def test_investigate_notes_its_queries_as_the_detection_s(monkeypatch):
    from glorfindel.enquiry import fixed
    b = read_budget.ReadBudget(Clock())
    monkeypatch.setattr(read_budget, "BUDGET", b)
    monkeypatch.setattr(fixed, "run_query", lambda ws, q: [])
    vm = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm"
    assert len(fixed.enquire({"MaxWrite": 70e6}, vm, "ws", unattributed=False).readings) == 3
    assert b.used() == {read_budget.DETECTION: 3}
    fixed.enquire({"MaxWrite": 70e6}, vm, "ws", unattributed=True)      # nothing run: nothing noted
    assert b.used() == {read_budget.DETECTION: 3}


def test_a_note_that_fails_never_costs_the_detection(monkeypatch):
    class Broken:
        def note(self, *a):
            raise RuntimeError("compteur cassé")
    monkeypatch.setattr(read_budget, "BUDGET", Broken())
    read_budget.note_detection()
