"""RDW1 (#994): a rule carries the ceiling of what its detection may lead to — ransomware-disk-write, on
the write rate alone, at most a snapshot and a card; the guard of `decide` after every gate that may
hold, before the mode, never releasing one; the model's proposal kept and said; the client's layer
lowering, never raising; the corroboration's hook; the console saying both proposals. One mutant per
property, M6833–M6847 and M6857–M6864, measured by tests/unit/test_rule_ceiling.py."""
AGENT = "glorfindel/agent.py"
CEILING = "glorfindel/rule_ceiling.py"
JS = "eregion_console/static/glorfindel.js"
QUEUE = "eregion_core/action_queue.py"
_T = "tests/unit/test_rule_ceiling.py"

MUTANTS = [
    ("M6833", "the guard removed: the vm-disk-write rows isolate in non_disruptive (RDW1)", AGENT,
     "    ceiling = _apply_rule_ceiling(d, signal)\n",
     "    ceiling = {}\n"),
    ("M6834", "the guard after the mode: in human_only, the mode holds the isolation and its card says "
     "'isolate_vm' recommended (RDW1)", AGENT,
     "    ceiling = _apply_rule_ceiling(d, signal)\n"
     "    _apply_never_block_guard(d, signal)\n"
     "    # ATT1 (#936): after every gate that may hold the decision, before the mode — on a detection\n"
     "    # that names no VM, its card is the attribution's, whatever held it first.\n"
     "    _apply_attribution_guard(d, signal)\n\n"
     "    mode_hold = _apply_autonomy_mode(d, mode, gate)\n",
     "    _apply_never_block_guard(d, signal)\n"
     "    _apply_attribution_guard(d, signal)\n\n"
     "    mode_hold = _apply_autonomy_mode(d, mode, gate)\n"
     "    ceiling = _apply_rule_ceiling(d, signal)\n"),
    ("M6835", "the client's layer raises the ceiling: a client copy that allows isolate_vm isolates (RDW1)",
     CEILING,
     "    allow = tuple(a for a in base.allow if a in client.allow)\n",
     "    allow = client.allow\n"),
    ("M6836", "a client copy that says no ceiling drops the shipped one (RDW1)", CEILING,
     "    if client is None:\n        return base\n",
     "    if client is None:\n        return None\n"),
    ("M6837", "the model's proposal lost from the card: neither the action nor its confidence kept (RDW1)",
     AGENT,
     "    return {k: ceiling[k] for k in (\"rule\", \"proposed\", \"confidence\", \"lowered\", \"allow\", \"why\") "
     "if k in ceiling}\n",
     "    return {k: ceiling[k] for k in (\"rule\", \"lowered\", \"allow\", \"why\") if k in ceiling}\n"),
    ("M6838", "the model's proposal lost from the reason: the card no longer says what was proposed (RDW1)",
     AGENT,
     "    text = (f\"Plafond de la règle « {name or '?'} » : {why}. Le modèle proposait '{action}' \"\n",
     "    text = (f\"Plafond de la règle « {name or '?'} » : {why}. \"\n"),
    ("M6839", "the ceiling's card absent: the snapshot run alone, nothing proposes the isolation nor says "
     "the ceiling (RDW1)", AGENT,
     "    ceiling_card = bool(ceiling) and not floor and not loose\n",
     "    ceiling_card = False\n"),
    ("M6840", "the ceiling unsaid on a held card: the mode's card says nothing of the model's proposal "
     "(RDW1)", AGENT,
     "    if ceiling and d[\"escalate\"] and not floor:\n"
     "        d[\"escalation_reason\"] = f\"{ceiling['reason']} — {d.get('escalation_reason') or ''}\".rstrip(\" —\")\n",
     "    if ceiling and d[\"escalate\"] and not floor:\n        pass\n"),
    ("M6841", "every rule capped: a rule without a ceiling no longer isolates (RDW1)", CEILING,
     "    if not isinstance(entry, dict) or KEY not in entry:\n        return None\n",
     "    if not isinstance(entry, dict) or KEY not in entry:\n        return LOWEST\n"),
    ("M6842", "the corroboration's hook ignored: a fact the rule names no longer lifts its ceiling (RDW1)",
     AGENT,
     "    if set(ceiling.lifted_by) & set(confirmed_facts(signal)):\n        return {}\n",
     ""),
    ("M6843", "the client's layer adds a lifting fact: the shipped ceiling lifted by the client (RDW1)",
     CEILING,
     "    lifted = tuple(f for f in base.lifted_by if f in client.lifted_by)\n",
     "    lifted = client.lifted_by\n"),
    ("M6844", "the rules unreadable: no ceiling, the isolation goes out (fail open) (RDW1)", AGENT,
     "        ceiling, unread = rule_ceiling.LOWEST, _first_line(exc)[:200]\n",
     "        ceiling, unread = None, _first_line(exc)[:200]\n"),
    ("M6845", "an attack_started that names no rule is not capped: Annatar's T1486 isolates alone (RDW1)",
     CEILING,
     "            if (query and rule_query == query) or (not query and ttp and rule_ttp == ttp):\n",
     "            if query and rule_query == query:\n"),
    ("M6846", "the console no longer says the ceiling: the card shows neither the model's proposal nor why "
     "(RDW1)", JS,
     "  return `${_targetNote(e, vmName)}${_ceilingNote(e)}\n",
     "  return `${_targetNote(e, vmName)}\n"),
    ("M6847", "the guard releases a hold before it: an isolation under the threshold becomes a snapshot run "
     "alone (RDW1)", AGENT,
     "    d[\"action\"] = lowered\n    d[\"reversible\"] = True\n    return record\n",
     "    d[\"action\"] = lowered\n    d[\"reversible\"] = True\n    d[\"escalate\"] = False\n    return record\n"),
    # Relecture (Jonathan, 20/11 : A, la carte du plafond propose l'isolement ; B, la mémoire garde la
    # proposition), et ses constats.
    ("M6857", "the memory keeps the action brought back: the model reads « T1486 → snapshot » in its past "
     "cycles (RDW1, B)", AGENT,
     "        \"action\": (state.get(\"ceiling\") or {}).get(\"proposed\") or state[\"action\"],\n",
     "        \"action\": state[\"action\"],\n"),
    ("M6858", "the ceiling's card not approvable: the isolation it proposes needs the CLI (RDW1, A)", QUEUE,
     "APPROVABLE_TYPES |= {\"ceiling_proposal\"}\n",
     ""),
    ("M6859", "the ceiling's card on a detection that names no VM: an isolation approvable on the VM the card "
     "is only filed on (RDW1, A; ATT1)", AGENT,
     "    ceiling_card = bool(ceiling) and not floor and not loose\n",
     "    ceiling_card = bool(ceiling) and not floor\n"),
    ("M6860", "the ceiling's card proposes nothing: the human has no one-click isolation (RDW1, A)", AGENT,
     "    action = \"isolate_vm\" if proposed == \"isolate_vm\" else \"\"\n",
     "    action = \"\"\n"),
    ("M6861", "the isolation run with the snapshot's commands: the command block isolates too (RDW1)", JS,
     "  return `# rule ceiling: the model proposed to isolate — its own card proposes it; only after judging: "
     "glorfindel isolate ${_vmArg(e.resource_id)} --yes\\n`;\n",
     "  return `# rule ceiling: the model proposed to isolate — its own card proposes it; only after judging:\\n"
     "glorfindel isolate ${_vmArg(e.resource_id)} --yes\\n`;\n"),
    ("M6862", "the shipped base gone read as no rule: no ceiling plays (fail open) (RDW1)", CEILING,
     "    if not dr._named(layers.base.get(\"rules\")):\n",
     "    if False:\n"),
    ("M6863", "the floor's reason names the snapshot the ceiling left as the model's choice (RDW1)", AGENT,
     "        floor = _floor_after_ceiling(floor, ceiling)\n",
     "        floor = f\"{floor} — {ceiling['reason']}\"\n"),
    ("M6864", "the ceiling's card never written: store_cycle forgets it (RDW1, A)", AGENT,
     "    _record_ceiling_card(state, source, exercise_run)\n",
     ""),
]
TESTS = {
    "M6833": f"{_T}::test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so",
    "M6834": f"{_T}::test_in_human_only_the_snapshot_is_held_and_the_isolation_proposed_beside_it",
    "M6835": f"{_T}::test_the_client_s_layer_never_raises_the_shipped_ceiling",
    "M6836": f"{_T}::test_a_client_rule_that_says_no_ceiling_keeps_the_shipped_one",
    "M6837": f"{_T}::test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so",
    "M6838": f"{_T}::test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so",
    "M6839": f"{_T}::test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so",
    "M6840": f"{_T}::test_in_human_only_the_snapshot_is_held_and_the_isolation_proposed_beside_it",
    "M6841": f"{_T}::test_a_rule_without_a_ceiling_isolates_as_before",
    "M6842": f"{_T}::test_a_fact_the_rule_names_lifts_its_ceiling",
    "M6843": f"{_T}::test_the_client_s_layer_never_raises_the_shipped_ceiling",
    "M6844": f"{_T}::test_rules_that_cannot_be_read_bring_the_decision_back_to_the_lowest",
    "M6845": f"{_T}::test_an_attack_started_resolved_by_the_rule_of_its_ttp_is_capped_too",
    "M6846": f"{_T}::test_the_console_says_both_proposals_and_the_reason_escaped",
    "M6847": f"{_T}::test_a_decision_held_before_stays_held_by_its_gate",
    "M6857": f"{_T}::test_the_memory_keeps_the_model_s_proposal",
    "M6858": f"{_T}::test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so",
    "M6859": f"{_T}::test_an_unattributed_detection_has_no_ceiling_card",
    "M6860": f"{_T}::test_the_human_isolates_from_the_card_in_one_gesture",
    "M6861": f"{_T}::test_the_card_s_command_names_the_isolation_left_to_a_human_never_on_a_loose_card",
    "M6862": f"{_T}::test_a_shipped_base_gone_or_empty_is_unreadable_never_no_ceiling",
    "M6863": f"{_T}::test_the_floor_comes_first_and_names_the_model_s_proposal",
    "M6864": f"{_T}::test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so",
}
