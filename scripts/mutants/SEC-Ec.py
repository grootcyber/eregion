"""SEC-Ec (#913): the rest of SEC-E's review — the reason of B3a's floor, on a detection that does
not name the VM, says what one click approves there (glorfindel/agent.py, _root_compromise_floor):
the mode's card (`mode_hold`, human_only) approves the model's snapshot, never an isolation; the
attribution's card (`unattributed_signal`) approves nothing, whatever gate held the decision before
(never_block, the release precondition…). M6311–M6317, measured by tests/unit/test_root_floor.py.
SEC-Ed (#954) retired M6311, M6312, M6314 and M6317 with what they measured: on such a detection the
attribution guard holds the snapshot too, so the mode holds nothing there (no card of the mode, no
reason of its own) and every gate that held an action before is the guard's already; M6313 and M6315
follow the code, measured where the guard does not hold (an action that is not autonomous)."""
AGENT = "glorfindel/agent.py"
AQ = "eregion_core/action_queue.py"
_F = "tests/unit/test_root_floor.py"

MUTANTS = [
    ("M6313", "the rewrite of held_by removed: an action the guard does not hold, on an unattributed "
     "detection, never the attribution's card (SEC-Ec)", AGENT,
     '        d["escalate"] = True\n        d["held_by"] = "attribution"\n        return (f"{facts_said}',
     '        d["escalate"] = True\n        return (f"{facts_said}'),
    ("M6315", "the floor's type on a detection that does not name the VM: the held action approvable in "
     "one click on a VM it may not concern (SEC-Ec)", AGENT,
     '        d["escalate"] = True\n        d["held_by"] = "attribution"\n        return (f"{facts_said}',
     '        d["escalate"] = True\n        d["held_by"] = "floor"\n        return (f"{facts_said}'),
    ("M6316", "the attribution's card proposed to the queue: a verb signed on a card the approval refuses "
     "(SEC-Ec)", AQ,
     'APPROVABLE_TYPES |= {"floor_proposal"}\n',
     'APPROVABLE_TYPES |= {"floor_proposal", "unattributed_signal"}\n'),
]
TESTS = {
    "M6313": f"{_F}::test_an_action_the_guard_does_not_hold_then_the_attribution",
    "M6315": f"{_F}::test_an_action_the_guard_does_not_hold_then_the_attribution "
             f"{_F}::test_an_unattributed_snapshot_never_runs_and_gets_no_floor_s_card",
    # ATT1 (#936): the attribution's card is refused by its type before the list is read, and
    # proposed nothing (`unattributed_aim`) — the list itself is held by its own test.
    "M6316": f"{_F}::test_a_protected_address_then_the_attribution "
             f"{_F}::test_a_release_hold_then_the_attribution "
             "tests/unit/test_attribution_prime.py::test_the_attribution_s_card_is_no_approvable_type",
}
