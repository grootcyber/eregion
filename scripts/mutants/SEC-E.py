"""SEC-E (#846): the decision bounded before the lines of the VM, until SEC-A3 — B3a's floor
proposes isolate_vm on a card, never runs it, whatever the mode, and the draws judge the model's own
choice (glorfindel/agent.py); its facts dated, a TTL of their own, absolute, forgotten at a release,
never prolonged by a held detection (glorfindel/incidents.py, glorfindel/gestures.py); the critical
class counted as a grave one in the ceiling, deduplicated by VM and rule, a ceiling of distinct
addresses, never chasing a detection of a grave technique out of a full queue, the gravity of a line
of the runs/ channel its technique's (glorfindel/decision_queue.py). M5721–M5740, and M5910–M5911
(the review: a detection that does not name the VM keeps the attribution's card; only the release
after a restore forgets the facts — numbers handed by the Orchestre), measured by
tests/unit/test_root_floor.py and tests/unit/test_decision_queue.py. M4375, M4401 (B3a) and M4567,
M4568 (SEC-A2) retired with what they measured; M4526 and M4570 (SEC-A2) follow the code, and M5910
too (SEC-Ec, #913: the redundant `or held_by == "attribution"` removed)."""
AGENT = "glorfindel/agent.py"
INC = "glorfindel/incidents.py"
GEST = "glorfindel/gestures.py"
QUEUE = "glorfindel/decision_queue.py"
AQ = "eregion_core/action_queue.py"
_F = "tests/unit/test_root_floor.py"
_Q = "tests/unit/test_decision_queue.py"

MUTANTS = [
    ("M5721", "the floor runs the isolation: a forged pair isolates the VM alone in non_disruptive (SEC-E, V-03)",
     AGENT,
     '    d["escalate"] = True\n    d["held_by"] = "floor"\n',
     '    d["held_by"] = ""\n'),
    ("M5722", "the draws judged on an action raised to isolate_vm, never the model's own choice (SEC-E, V-03)",
     AGENT,
     "        x, raw_conf = _parse_decision(resp)\n        _apply_executable_guard(x)\n",
     '        x, raw_conf = _parse_decision(resp)\n        x["action"] = "isolate_vm"\n'
     "        _apply_executable_guard(x)\n"),
    ("M5723", "a human's release forgets nothing: the floor proposes again on the VM a human judged (SEC-E, V-03)",
     GEST,
     "        IncidentRegistry().forget_facts(resource_id)\n",
     "        pass\n"),
    ("M5724", "the watch's release after a restore forgets nothing (SEC-E, V-03)", AGENT,
     "            incidents.forget_facts(resource_id)\n",
     "            pass\n"),
    ("M5725", "the facts forgotten only under the id's exact case: the RulePoller's lowercase incident kept "
     "(SEC-E)", INC,
     '        want = str(resource_id or "").rstrip("/").lower()\n',
     '        want = str(resource_id or "")\n'),
    ("M5726", "a fact without a TTL of its own: it lives as long as the incident, each signal prolonging it "
     "(SEC-E, V-03)", INC,
     "        if at is not None and 0 <= (now - at).total_seconds() < FACT_TTL_S:\n",
     "        if isinstance(fact, str):\n"),
    ("M5727", "a fact confirmed again is dated again: forged lines keep it alive (SEC-E, V-03)", INC,
     "            kept = {f: dates[f] for f in live}\n",
     "            kept = {}\n"),
    ("M5728", "a held detection prolongs the incident again (SEC-E, V-03)", QUEUE,
     '    try:\n        incidents.confirm(str(data.get("resource_id") or ""), facts,',
     '    try:\n        incidents.get_or_create(str(data.get("resource_id") or ""))\n'
     '        incidents.confirm(str(data.get("resource_id") or ""), facts,'),
    ("M5729", "the critical class outside the ceiling again (SEC-E, V-02, #644 point 1)", QUEUE,
     "                    # SEC-E (V-02): a critical one counts as a grave one — the room reserved, finite.\n"
     "                    limit = self.per_min\n",
     "                    limit = self.per_min if cls == GRAVE else 10 ** 9\n"),
    ("M5730", "any class chases another out of a full queue, a grave one's detection included (SEC-E, V-02)",
     QUEUE,
     "            others = [e for e in self._heap if not self._protect(e[2])]\n",
     "            others = list(self._heap)\n"),
    ("M5731", "a grave detection refused by a queue full of critical ones (SEC-E, V-02)", QUEUE,
     "(self._protect(entry[2]) or cls < worst[0])",
     "cls < worst[0]"),
    ("M5732", "a compromise deduplicated by its address again: a new address, a new decision (SEC-E, V-02)",
     QUEUE,
     "                gravity(data), _source(data))\n",
     '                gravity(data), _source(data), str(_row(data).get("SourceIP") or ""))\n'),
    ("M5733", "no ceiling of distinct addresses: a flood of compromises that open no window, one call each "
     "(SEC-E, V-02)", QUEUE,
     "        if addr in seen or len(seen) < CRITICAL_ADDRESSES:\n",
     "        if True:\n"),
    ("M5734", "the addresses of a window never age: a VM silenced for the whole watch (SEC-E)", QUEUE,
     "        for a in [a for a, t in seen.items() if now - t >= self.window_s]:\n            del seen[a]\n",
     ""),
    ("M5735", "the gravity of a runs/ line copied: an injector's « critical » passes before the grave ones "
     "(SEC-E, V-08)", QUEUE,
     '    if from_rulepoller(data) and str(data.get("severity") or "").lower() == "critical":\n',
     '    if str(data.get("severity") or "").lower() == "critical":\n'),
    ("M5736", "the pair of B3a lifts the dedup too: its exemption never ends once the floor played (SEC-E, "
     "#644 point 2)", QUEUE,
     "            if from_rulepoller(data):\n                at = self._decided.get(key)\n",
     "            if from_rulepoller(data) and not _FLOOR_PAIR <= set(confirmed or []) | set(facts_of(data)):\n"
     "                at = self._decided.get(key)\n"),
    ("M5737", "the floor's card never written beside the model's own action run alone (SEC-E)", AGENT,
     "    _record_floor_card(state, source, exercise_run)\n", ""),
    ("M5738", "the floor's card filed as a mode hold in human_only: read as a policy hold of the model's "
     "action (SEC-E)", AGENT,
     '    elif state.get("held_by") == "floor":\n        escalation_type = FLOOR_TYPE\n',
     "    elif False:\n        escalation_type = FLOOR_TYPE\n"),
    ("M5739", "the floor's card not approvable: its isolation never one click away (SEC-E)", AQ,
     'APPROVABLE_TYPES |= {"floor_proposal"}\n', ""),
    ("M5740", "the floor's card opens no window: its pair calls the model pass after pass (SEC-E, #644 "
     "point 2)", QUEUE,
     '    if state.get("floor") or (state.get("outcome") or {}).get("compromise_card"):\n',
     '    if (state.get("outcome") or {}).get("compromise_card"):\n'),
    ("M5910", "the floor's card on a detection that does not name the VM: an unattributed or appliance "
     "card made approvable in one click (SEC-E, review)", AGENT,
     '    if (signal.get("context") or {}).get("attribution") == "unattributed":\n        if not d["escalate"]',
     '    if False:\n        if not d["escalate"]'),
    ("M5911", "any release by the watch forgets the facts: a release the model chose on a detection wipes a "
     "compromise's (SEC-E, review)", AGENT,
     '            and state["signal"].get("event") == "recovery_complete"):\n',
     "            ):\n"),
]
TESTS = {
    "M5721": f"{_F}::test_no_action_is_raised_to_isolate_vm {_F}::test_the_floor_never_isolates_whatever_the_mode",
    "M5722": f"{_F}::test_the_draws_judge_the_models_choice_never_the_raised_action "
             f"{_F}::test_the_models_own_action_runs_as_its_gates_judged_it_and_the_floor_proposes",
    "M5723": f"{_F}::test_a_human_release_forgets_the_facts",
    "M5724": f"{_F}::test_the_watch_forgets_the_facts_when_it_releases",
    "M5725": f"{_F}::test_the_facts_are_forgotten_at_a_release",
    "M5726": f"{_F}::test_a_fact_counts_within_its_ttl_never_prolonged_by_the_signals_of_the_vm "
             f"{_F}::test_the_registry_keeps_what_was_confirmed",
    "M5727": f"{_F}::test_a_fact_counts_within_its_ttl_never_prolonged_by_the_signals_of_the_vm",
    "M5728": f"{_F}::test_a_held_detection_never_prolongs_the_incident",
    "M5729": f"{_Q}::test_a_compromise_counts_as_a_grave_one_in_the_ceiling",
    "M5730": f"{_Q}::test_a_full_queue_of_compromises_never_chases_a_grave_detection",
    "M5731": f"{_Q}::test_a_full_queue_of_compromises_never_chases_a_grave_detection",
    "M5732": f"{_Q}::test_a_compromise_is_deduplicated_by_vm_and_rule_the_address_for_the_card",
    "M5733": f"{_Q}::test_a_flood_of_compromises_from_distinct_addresses_is_bounded",
    "M5734": f"{_Q}::test_a_flood_of_compromises_from_distinct_addresses_is_bounded",
    "M5735": f"{_Q}::test_a_line_of_the_channel_never_says_critical",
    "M5736": f"{_Q}::test_the_pair_lifts_the_ceiling_only_never_the_window",
    "M5737": f"{_F}::test_non_disruptive_isolates_and_the_compromise_card_says_the_floor "
             f"{_F}::test_the_floor_never_isolates_whatever_the_mode",
    "M5738": f"{_F}::test_human_only_runs_nothing_and_the_card_proposes_isolate_vm",
    "M5739": f"{_F}::test_the_floor_never_isolates_whatever_the_mode",
    "M5740": f"{_Q}::test_the_pair_lifts_the_ceiling_only_never_the_window",
    "M5910": f"{_F}::test_a_detection_that_does_not_name_the_vm_keeps_the_attributions_card "
             f"{_F}::test_an_unattributed_snapshot_never_runs_and_gets_no_floor_s_card",
    "M5911": f"{_F}::test_a_release_the_model_chose_on_a_detection_keeps_the_facts",
}
