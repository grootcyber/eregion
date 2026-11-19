"""SEC-Ec (#913): the rest of SEC-E's review — the reason of B3a's floor, on a detection that does
not name the VM, says what one click approves there (glorfindel/agent.py, _root_compromise_floor):
the mode's card (`mode_hold`, human_only) approves the model's snapshot, never an isolation; the
attribution's card (`unattributed_signal`) approves nothing, whatever gate held the decision before
(never_block, the release precondition…). M6311–M6317, measured by tests/unit/test_root_floor.py."""
AGENT = "glorfindel/agent.py"
AQ = "eregion_core/action_queue.py"
_F = "tests/unit/test_root_floor.py"

MUTANTS = [
    ("M6311", "the false reason back: the mode's card approvable for the snapshot says « rien ne s'y "
     "approuve en un clic » (SEC-Ec)", AGENT,
     "        if mode_hold:\n            return (f\"{facts_said} — mais cette détection ne nomme pas cette VM",
     "        if False:\n            return (f\"{facts_said} — mais cette détection ne nomme pas cette VM"),
    ("M6312", "the mode's hold never handed to the floor: its reason says the attribution's card (SEC-Ec)",
     AGENT,
     "    floor = _root_compromise_floor(d, signal, incident, mode_hold=mode_hold)\n",
     "    floor = _root_compromise_floor(d, signal, incident, mode_hold=False)\n"),
    ("M6313", "the rewrite of held_by removed: a protected address keeps its type, a release hold its "
     "approval (SEC-Ec)", AGENT,
     '        d["escalate"] = True\n        d["held_by"] = "attribution"\n        if mode_hold:\n',
     '        d["escalate"] = True\n        if mode_hold:\n'),
    ("M6314", "an earlier gate keeps its hold: a release held on an unattributed detection approvable in "
     "one click (SEC-Ec)", AGENT,
     '        d["escalate"] = True\n        d["held_by"] = "attribution"\n        if mode_hold:\n',
     '        d["escalate"] = True\n        d["held_by"] = d.get("held_by") or "attribution"\n'
     "        if mode_hold:\n"),
    ("M6315", "the floor's type on a detection that does not name the VM: the held action approvable in "
     "one click on a VM it may not concern (SEC-Ec)", AGENT,
     '        d["escalate"] = True\n        d["held_by"] = "attribution"\n        if mode_hold:\n',
     '        d["escalate"] = True\n        d["held_by"] = "floor"\n        if mode_hold:\n'),
    ("M6316", "the attribution's card proposed to the queue: a verb signed on a card the approval refuses "
     "(SEC-Ec)", AQ,
     'APPROVABLE_TYPES |= {"floor_proposal"}\n',
     'APPROVABLE_TYPES |= {"floor_proposal", "unattributed_signal"}\n'),
    ("M6317", "the mode's hold before the floor's type no more: the snapshot's card turned into the "
     "attribution's, its reason false the other way (SEC-Ec)", AGENT,
     '    elif state.get("mode_hold"):\n        escalation_type = "mode_hold"\n',
     '    elif state.get("mode_hold") and state.get("held_by") != "attribution":\n'
     '        escalation_type = "mode_hold"\n'),
]
TESTS = {
    "M6311": f"{_F}::test_an_unattributed_snapshot_held_by_the_mode_says_what_one_click_approves",
    "M6312": f"{_F}::test_an_unattributed_snapshot_held_by_the_mode_says_what_one_click_approves",
    # ATT1 (#936): the attribution guard now holds an unattributed block or release first — the
    # floor's own rewrite is seen where the guard does not hold: the snapshot under the threshold.
    "M6313": f"{_F}::test_a_protected_address_then_the_attribution "
             f"{_F}::test_a_release_hold_then_the_attribution {_F}::test_a_low_confidence_hold_then_the_attribution",
    "M6314": f"{_F}::test_a_release_hold_then_the_attribution {_F}::test_a_low_confidence_hold_then_the_attribution",
    "M6315": f"{_F}::test_a_protected_address_then_the_attribution "
             f"{_F}::test_a_release_hold_then_the_attribution",
    # ATT1 (#936): the attribution's card is refused by its type before the list is read, and
    # proposed nothing (`unattributed_aim`) — the list itself is held by its own test.
    "M6316": f"{_F}::test_a_protected_address_then_the_attribution "
             f"{_F}::test_a_release_hold_then_the_attribution "
             "tests/unit/test_attribution_prime.py::test_the_attribution_s_card_is_no_approvable_type",
    "M6317": f"{_F}::test_an_unattributed_snapshot_held_by_the_mode_says_what_one_click_approves",
}
