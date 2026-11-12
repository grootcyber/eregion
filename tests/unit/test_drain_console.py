"""DRN2 (#754): the isolation card of the console says what became of the session cut — pending, then
its outcome, from the isolation's state alone (the outcome read on Azure), never from the notices' store.
Until DRN2, `/api/state` carried the drain and the page showed nothing of it: on the bench, 12/11,
the console said « quarantine NSG ✓ » and Discord « coupure en attente », never its end. What comes
from the watch reaches the page as data, written through `_attr` (#254,
tests/unit/test_console_escaping.py holds the whole page). Crosses components: TOGETHER.
"""
from __future__ import annotations

from pathlib import Path

from glorfindel import drain_watch, vm_notices
from glorfindel.actions import _save_isolation_state

from .console_client import console

VM = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
ASKED = "2026-11-12T09:18:45.600000+00:00"


def _view(drain: dict, **state) -> dict:
    _save_isolation_state(VM, {"resource_id": VM, "isolated_at": ASKED, "placements": [], "drain": drain, **state})
    body = console().get("/api/state").json()
    [iso] = [s for r in body["resources"] for s in r["states"] if s["type"] == "isolated"]
    return iso["drain_view"]


def test_a_cut_pending_is_said_pending():
    assert _view({"status": "pending", "asked_at": ASKED}) == {"case": "pending", "ended_at": ""}


def test_a_cut_closed_after_its_first_wait_says_its_outcome_from_the_state():
    view = _view({"status": "drained", "after_s": 327, "asked_at": ASKED}, drain_ended_at="2026-11-12T09:24:12+00:00")
    said = "Coupure des sessions aboutie, relue 327 s après la demande : sessions coupées, isolement vérifié."
    assert view == {"case": "drained", "ended_at": "2026-11-12T09:24:12+00:00", "after_s": 327, "said": said}


def test_a_cut_that_failed_says_its_case_even_without_a_closure():
    view = _view({"status": "failed", "never": True, "error": "statut non relu", "asked_at": ASKED},
                 drain_ended_at="2026-11-12T09:50:00+00:00")
    assert view["case"] == "never" and view["said"].startswith("coupure jamais aboutie : ")
    assert "after_s" not in view


def test_a_forged_notice_never_changes_the_card():
    """The store is written by the console and the bot too (DRN2 review): a forged notice — another
    outcome, or the same outcome with other words and another duration — changes neither the chip
    nor its sentence: the card is the state's alone."""
    vm_notices.say(VM, drain_watch.closure_key(VM, ASKED), "drain_closed", "Coupure des sessions aboutie",
                   "tout va bien", level="ok", detail={"outcome": "drained", "after_s": 1})
    view = _view({"status": "failed", "never": True, "error": "statut non relu", "asked_at": ASKED},
                 drain_ended_at="2026-11-12T09:50:00+00:00")
    assert view["case"] == "never" and "tout va bien" not in view["said"] and "after_s" not in view
    other = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/db"
    vm_notices.say(other, drain_watch.closure_key(other, ASKED), "drain_closed", "Coupure des sessions : "
                   "coupure jamais aboutie", "rien à voir ici", level="unknown",
                   detail={"outcome": "never", "after_s": 9999})
    _save_isolation_state(other, {"resource_id": other, "isolated_at": ASKED, "placements": [],
                                  "drain": {"status": "failed", "never": True, "error": "statut non relu",
                                            "asked_at": ASKED}, "drain_ended_at": "2026-11-12T09:50:00+00:00"})
    body = console().get("/api/state").json()
    [iso] = [s for r in body["resources"] if r["resource_id"] == other for s in r["states"]
             if s["type"] == "isolated"]
    assert iso["drain_view"]["case"] == "never" and "rien à voir" not in iso["drain_view"]["said"]
    assert "after_s" not in iso["drain_view"]


def test_a_status_with_no_case_says_nothing():
    """AWS: no session cut (`unavailable`) — never a « aboutie » sentence (DRN2 review)."""
    assert _view({"status": "unavailable", "reason": "pas de coupure sur AWS"},
                 drain_ended_at="2026-11-12T09:50:00+00:00") == {}


def test_a_cut_ended_within_its_first_wait_adds_nothing_to_the_card():
    assert _view({"status": "drained"}) == {}
    assert _view({}) == {}


def test_the_page_writes_the_cut_through_its_escape():
    js = (Path(__file__).resolve().parents[2] / "eregion_console/static/glorfindel.js").read_text()
    body = js.split("function _drainNote(s) {", 1)[1].split("\n}\n", 1)[0]
    assert 'title="${_attr(why)}"' in body and "d.said" in body
    assert "return out + _drainNote(s);" in js            # on every ISOLATED badge, by _healthNote
