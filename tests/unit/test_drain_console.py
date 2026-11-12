"""DRN2 (#754): the isolation card of the console says what became of the session cut — pending, then
its outcome, in the closure's own words (glorfindel/vm_notices.py: the text the notification said).
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


def test_a_cut_closed_after_its_first_wait_says_the_closure_s_words():
    said = "Coupure des sessions aboutie sur web, relue 327 s après la demande : sessions coupées."
    vm_notices.say(VM, drain_watch.closure_key(VM, ASKED), "drain_closed", "Coupure des sessions aboutie",
                   said, level="ok", detail={"outcome": "drained", "after_s": 327.4})
    view = _view({"status": "drained", "after_s": 327, "asked_at": ASKED}, drain_ended_at="2026-11-12T09:24:12+00:00")
    assert view == {"case": "drained", "ended_at": "2026-11-12T09:24:12+00:00", "after_s": 327, "said": said}


def test_a_cut_that_failed_says_its_case_even_without_a_closure():
    view = _view({"status": "failed", "never": True, "error": "statut non relu", "asked_at": ASKED},
                 drain_ended_at="2026-11-12T09:50:00+00:00")
    assert view["case"] == "never" and view["said"].startswith("coupure jamais aboutie : ")
    assert "after_s" not in view


def test_a_cut_ended_within_its_first_wait_adds_nothing_to_the_card():
    assert _view({"status": "drained"}) == {}
    assert _view({}) == {}


def test_the_page_writes_the_cut_through_its_escape():
    js = (Path(__file__).resolve().parents[2] / "eregion_console/static/glorfindel.js").read_text()
    body = js.split("function _drainNote(s) {", 1)[1].split("\n}\n", 1)[0]
    assert 'title="${_attr(why)}"' in body and "d.said" in body
    assert "return out + _drainNote(s);" in js            # on every ISOLATED badge, by _healthNote
