"""ATT1 (#936): the attribution guard primes over any hold before it — a card on a detection attributed
to no VM is never approvable in one click (the server, the signed queue, the console, the bot), its
suggested commands never name the VM it is filed on, and the exclusion of the watch's return channel
is the shipped rule's only. One mutant per property, M6451–M6465, measured by
tests/unit/test_attribution_prime.py; M6449–M6450 (from MUT14's range, the relecture's two findings): the
title of an unattributed card said done, the model's steps shown without their note."""
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_attribution_prime.py"
_HELD = f"{_T}::test_an_unattributed_detection_held_before_is_the_attribution_s_card"
_FORGED = f"{_T}::test_no_approvable_type_runs_an_unattributed_isolation"
_PAGE = f"{_T}::test_the_page_offers_no_one_click_approval_on_an_unattributed_card"

MUTANTS = [
    ("M6449", "the console's title of an unattributed card back to its past label: « VM isolated from "
     "network » for an isolation nothing ran (ATT1)", "eregion_console/static/glorfindel.js",
     "  const loose = _looseTitle(e);\n  if (loose) return loose;\n",
     "  const loose = _looseTitle(e);\n"),
    ("M6450", "`glorfindel pending` shows the model's steps of an unattributed card without saying they "
     "aim at the VM it is filed on (ATT1)", "glorfindel/cli.py",
     "        loose_steps = _esc_steps.unattributed(e)\n        if loose_steps is not None:\n",
     "        loose_steps = _esc_steps.unattributed(e)\n        if False:\n"),
    ("M6451", "the attribution guard leaves at once when a gate before it held the decision: a "
     "low_confidence card on an unattributed detection, approvable (ATT1)", AGENT,
     "    if d[\"action\"] not in _ATTRIBUTION_HELD:\n        return\n",
     "    if d[\"escalate\"] or d[\"action\"] not in _ATTRIBUTION_HELD:\n        return\n"),
    ("M6452", "the attribution guard back before the never_block guard: a protected address on an "
     "unattributed detection is the never_block's card, not the attribution's (ATT1)", AGENT,
     "    _apply_never_block_guard(d, signal)\n"
     "    # ATT1 (#936): after every gate that may hold the decision, before the mode — on a detection\n"
     "    # that names no VM, its card is the attribution's, whatever held it first.\n"
     "    _apply_attribution_guard(d, signal)\n",
     "    _apply_attribution_guard(d, signal)\n"
     "    _apply_never_block_guard(d, signal)\n"),
    ("M6453", "the reason of the hold before lost: the card no longer says what held it first (ATT1)",
     AGENT,
     "        \"(ou bloquer au périmètre) avant d'agir.\"\n        + (f\" — {before}\" if before else \"\")\n",
     "        \"(ou bloquer au périmètre) avant d'agir.\"\n"),
    ("M6454", "the release of the isolation out of what the guard holds: an unattributed release a "
     "release_hold, approvable (ATT1)", AGENT,
     "_ATTRIBUTION_HELD = frozenset(_VM_TARGETED_ACTIONS | {\"block_suspicious_ip\", \"release_isolation\"})\n",
     "_ATTRIBUTION_HELD = frozenset(_VM_TARGETED_ACTIONS | {\"block_suspicious_ip\"})\n"),
    ("M6455", "the server's refusal taken off: an unattributed isolation on an approvable type runs in "
     "one click (ATT1)", "glorfindel/approval.py",
     "    if action_queue.unattributed_aim(esc):\n",
     "    if False:\n"),
    ("M6456", "the watch signs a proposal on an unattributed card that holds an action aimed at its VM "
     "(ATT1)", "glorfindel/escalations.py",
     "        if action_queue.unattributed_aim(e):    # ATT1: never a proposal on a VM the detection does not name\n"
     "            return False\n",
     ""),
    ("M6457", "the signed queue proposes the verb of an unattributed card's action (ATT1)",
     "eregion_core/action_queue.py",
     "    if unattributed_aim(card):              # ATT1: its VM is an anchor, never aimed at\n"
     "        return frozenset()\n",
     ""),
    ("M6458", "an unattributed card read by its type only: any other type that says it is unattributed "
     "approvable (ATT1)", "eregion_core/action_queue.py",
     "    return isinstance(a, dict) and a.get(\"state\") == \"unattributed\" and card.get(\"action\") in VM_AIMED_ACTIONS\n",
     "    return False\n"),
    ("M6459", "the console's « Approve & execute » back on an unattributed card (ATT1)",
     "eregion_console/static/glorfindel.js",
     "    && !(e.action === 'snapshot' && e.escalation_type === 'low_confidence')\n    && !_aimsLoose(e);\n",
     "    && !(e.action === 'snapshot' && e.escalation_type === 'low_confidence');\n"),
    ("M6460", "the console's « 📸 Snapshot » back on an unattributed card: the VM it is filed on "
     "snapshotted (ATT1)", "eregion_console/static/glorfindel.js",
     "  return e.action === 'snapshot' && e.escalation_type === 'low_confidence' && !_unattributed(e);\n",
     "  return e.action === 'snapshot' && e.escalation_type === 'low_confidence';\n"),
    ("M6461", "the console's command names the VM an unattributed card is filed on (ATT1)",
     "eregion_console/static/glorfindel.js",
     "  const loose = _unattributed(esc);\n  if (loose) {\n",
     "  const loose = _unattributed(esc);\n  if (false) {\n"),
    ("M6462", "`glorfindel pending` suggests a command on the VM an unattributed card is filed on (ATT1)",
     "glorfindel/cli.py",
     "    unnamed = _esc.unattributed(e)\n    if unnamed is not None:\n",
     "    unnamed = _esc.unattributed(e)\n    if False:\n"),
    ("M6463", "the bot's command names the VM an unattributed card is filed on (ATT1)", "glorfindel/bot.py",
     "    loose = esc_module.unattributed(esc)\n    if loose is not None:\n        # ATT1 (#936)",
     "    loose = None\n    if loose is not None:\n        # ATT1 (#936)"),
    ("M6464", "the snapshot step of an unattributed card names the VM it is filed on (ATT1)", AGENT,
     "    if action == \"snapshot\" and loose is not None:\n",
     "    if False:\n"),
    ("M6465", "the exclusion of the watch's return channel applied to an override of the client's "
     "layer that computes a wider Known (ATT1)", "glorfindel/detection_rules.py",
     "            if own_channel.is_shipped(rule.query, rule.name):\n",
     "            if True:\n"),
]
TESTS = {
    "M6449": f"{_T}::test_the_page_never_says_an_unattributed_card_s_action_done",
    "M6450": f"{_T}::test_the_model_s_steps_of_an_unattributed_card_are_said_aimed_at_the_anchor",
    "M6451": _HELD,
    "M6452": _HELD,
    "M6453": _HELD,
    "M6454": f"{_T}::test_the_guard_holds_the_approval_s_own_set {_HELD}",
    "M6455": _FORGED,
    "M6456": _FORGED,
    "M6457": _FORGED,
    "M6458": _FORGED,
    "M6459": _PAGE,
    "M6460": _PAGE,
    "M6461": f"{_T}::test_the_page_s_command_never_names_the_vm_of_an_unattributed_card",
    "M6462": f"{_T}::test_glorfindel_pending_never_names_the_vm_an_unattributed_card_is_filed_on",
    "M6463": f"{_T}::test_the_bot_never_names_nor_aims_at_the_vm_of_an_unattributed_card",
    "M6464": f"{_T}::test_the_card_s_snapshot_step_never_names_the_vm_it_is_filed_on",
    "M6465": f"{_T}::test_an_override_of_the_rule_sets_nothing_aside",
}
