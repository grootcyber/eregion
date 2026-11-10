"""LEV2 (#690): the isolation card says the door's facts — who acted on the VM, their rights — for
information only. What comes from Azure (an extension's name, a caller's UPN) reaches the page as
text: /api/state carries it as data, the page writes it through `_attr` (#254,
tests/unit/test_console_escaping.py holds the whole page). Crosses components (the console over
Glorfindel's facts): TOGETHER.
"""
from __future__ import annotations

from datetime import datetime, timezone

from glorfindel import door_facts
from glorfindel.actions import _save_isolation_state

from .console_client import console

VM = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
EVIL = '<img src=x onerror="fetch(`/api/reset/web`)">'


class _Reader:
    """A connector that reads an actor whose names are an attacker's."""

    def observed_actors(self, resource_id, since, until="", disks=(), rules_at_isolation=None):
        return {"verdict": "seen", "since": since, "until": NOW.isoformat(), "reads": [], "unreadable": [],
                "notes": [], "scopes": [resource_id],
                "actors": [{"ids": [EVIL, "11111111-1111-1111-1111-111111111111"], "role": "", "gestures": [
                    {"at": NOW.isoformat(), "operation": "Microsoft.Compute/virtualMachines/extensions/write",
                     "resource": VM + "/extensions/" + EVIL, "kind": "vm_child", "status": "Succeeded"}]}]}

    def observed_rights(self, ids, resource_id, scopes=(), deleted=None, reading=None):
        return {"verdict": "unreadable", "held": [], "groups": [],
                "unreadable": [f"« {EVIL} » sur un groupe de ressources à un groupe : H0 n'en lit pas les membres"]}


def test_the_isolation_card_carries_the_facts_as_data_for_information():
    _save_isolation_state(VM, {"resource_id": VM, "isolated_at": NOW.isoformat(), "placements": [],
                               "disks_at_isolation": {"ids": [VM.replace("virtualMachines/web", "disks/web-os")]}})
    door_facts.facts_pass(_Reader(), now=NOW.timestamp())
    state = console().get("/api/state").json()
    [res] = [r for r in state["resources"] if r["resource_id"] == VM]
    [iso] = [s for s in res["states"] if s["type"] == "isolated"]
    door = iso["door"]
    assert door["for_information"] is True and door["verdict"] == "seen"
    assert door["actors"][0]["ids"][0] == EVIL                  # data, the page escapes it
    assert door["actors"][0]["rights"] == "unreadable"
    assert iso["disks_at_isolation"] == [VM.replace("virtualMachines/web", "disks/web-os")]


def test_a_card_never_read_says_nothing_and_an_old_state_has_no_disks():
    _save_isolation_state(VM, {"resource_id": VM, "isolated_at": NOW.isoformat(), "placements": []})
    state = console().get("/api/state").json()
    [iso] = [s for r in state["resources"] for s in r["states"] if s["type"] == "isolated"]
    assert iso["door"] is None and iso["disks_at_isolation"] == []


def test_the_page_writes_the_facts_through_its_escape():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[2] / "eregion_console/static/glorfindel.js").read_text()
    body = js.split("function _doorNote(s) {", 1)[1].split("\n}\n", 1)[0]
    assert 'title="${_attr(lines.join(' in body
    assert js.count("${_doorNote(s)}") == 3                     # every isolated badge
