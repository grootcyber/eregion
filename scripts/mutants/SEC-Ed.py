"""SEC-Ed (#954; Jonathan, 19/11): the snapshot of a detection attributed to no VM is never approvable in
one click, nor run alone, whatever the confidence and the mode — the attribution guard holds it
(glorfindel/agent.py), the approval refuses it everywhere (eregion_core/action_queue.py
`VM_AIMED_ACTIONS`, glorfindel/approval.py, the signed queue, the bot, the console), and the card
says the human chooses the VM to snapshot. M6546–M6555, measured by
tests/unit/test_attribution_prime.py."""
AGENT = "glorfindel/agent.py"
AQ = "eregion_core/action_queue.py"
JS = "eregion_console/static/glorfindel.js"
_T = "tests/unit/test_attribution_prime.py"
_ANY = f"{_T}::test_an_unattributed_snapshot_is_the_attribution_s_card_whatever_the_confidence_and_the_mode"
_OLD = f"{_T}::test_an_old_mode_hold_snapshot_card_is_refused_by_the_server_the_queue_and_the_bot"
_RUN = f"{_T}::test_an_unattributed_snapshot_never_runs_on_the_anchor"

MUTANTS = [
    ("M6546", "the snapshot out of the attribution guard: held by the mode (approvable) or run alone on "
     "the VM the card is filed on (SEC-Ed)", AGENT,
     '_ATTRIBUTION_HELD |= {"snapshot"}\n', ""),
    ("M6547", "the snapshot out of the actions aimed at the VM: a mode_hold snapshot's card written before "
     "SEC-Ed approvable in one click (SEC-Ed)", AQ,
     'VM_AIMED_ACTIONS |= {"snapshot"}\n', ""),
    ("M6548", "the mode before the attribution guard: a snapshot on an unattributed detection the mode's "
     "card again (SEC-Ed)", AGENT,
     "    _apply_attribution_guard(d, signal)\n\n    mode_hold = _apply_autonomy_mode(d, mode, gate)\n",
     "\n    mode_hold = _apply_autonomy_mode(d, mode, gate)\n    _apply_attribution_guard(d, signal)\n"),
    ("M6549", "a mode_hold card read as approvable whatever its attribution: an unattributed snapshot (or "
     "isolation) approved in one click (SEC-Ed)", AQ,
     '    return isinstance(a, dict) and a.get("state") == "unattributed" and card.get("action") in VM_AIMED_ACTIONS\n',
     '    return (isinstance(a, dict) and a.get("state") == "unattributed" and card.get("action") in VM_AIMED_ACTIONS\n'
     '            and card.get("escalation_type") != "mode_hold")\n'),
    ("M6550", "the server accepts an unattributed snapshot: the console's route and the queue's guard run "
     "it on the VM the card is filed on (SEC-Ed)", "glorfindel/approval.py",
     "    if action_queue.unattributed_aim(esc):\n",
     '    if action_queue.unattributed_aim(esc) and esc.get("action") != "snapshot":\n'),
    ("M6551", "the signed queue skips the approval's guard for a snapshot: a request on an old proposal "
     "reaches the vault (SEC-Ed)", "glorfindel/queue_watch.py",
     '        if card is not None and req.verb != "reset":\n',
     '        if card is not None and req.verb not in ("reset", "snapshot"):\n'),
    ("M6552", "the bot may ask a snapshot: its request on an unattributed card judged by one guard only "
     "(SEC-Ed)", AQ,
     '    "bot": frozenset({"reset"}),\n',
     '    "bot": frozenset({"reset", "snapshot"}),\n'),
    ("M6553", "the console's « Approve & execute » back on an unattributed snapshot's card (SEC-Ed)", JS,
     "const _VM_AIMED = new Set(['isolate_vm', 'block_suspicious_ip', 'release_isolation', 'revoke_temp_access', 'snapshot']);\n",
     "const _VM_AIMED = new Set(['isolate_vm', 'block_suspicious_ip', 'release_isolation', 'revoke_temp_access']);\n"),
    ("M6554", "the card no longer says the human chooses the VM to snapshot (SEC-Ed)", AGENT,
     '    if d["action"] == "snapshot":\n        # SEC-Ed (#954): the human chooses the VM to capture',
     '    if False:\n        # SEC-Ed (#954): the human chooses the VM to capture'),
    ("M6555", "a snapshot no gate held passes the attribution guard: run alone on the VM the card is filed "
     "on in non_disruptive (SEC-Ed)", AGENT,
     '    if d["action"] not in _ATTRIBUTION_HELD:\n        return\n',
     '    if d["action"] not in _ATTRIBUTION_HELD or (d["action"] == "snapshot" and not d["escalate"]):\n'
     "        return\n"),
]
TESTS = {
    "M6546": f"{_ANY} {_T}::test_the_guard_holds_the_approval_s_own_set",
    "M6547": f"{_OLD} {_T}::test_the_guard_holds_the_approval_s_own_set",
    "M6548": _ANY,
    "M6549": f"{_OLD} {_T}::test_a_mode_hold_on_an_unattributed_detection_approves_nothing",
    "M6550": f"{_OLD} {_T}::test_the_console_s_approve_route_refuses_an_old_unattributed_snapshot",
    "M6551": _OLD,
    "M6552": _OLD,
    "M6553": f"{_T}::test_the_page_offers_no_approval_nor_snapshot_on_an_unattributed_snapshot "
             f"{_T}::test_the_guard_holds_the_approval_s_own_set",
    "M6554": _ANY,
    "M6555": f"{_RUN} {_ANY}",
}
