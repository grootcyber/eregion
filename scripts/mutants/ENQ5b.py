"""ENQ5b (#1284): the enquiry in production, behind GLORFINDEL_ENQUIRY (glorfindel/enquiry/interrupteur.py) —
`fixed` the default, origin/main to the byte; `loop`, the loop in the watch (production.py), `decide` with its
enquiry (decision.py), the memory per object (memoire.py), the reader's budgets (lecteur.py), the gate's
reserve (decision_queue.py), heartbeat_gap corrected for the loop (catalog.py). One mutant at least per
property of the line « ENQ5 » of §13 (`docs/design/enquete-raisonnee.md`), one for `fixed` changed, one for
the end of heartbeat_gap at T bare. M8266–M8285, measured by tests/unit/test_enquiry_production.py."""
SWITCH = "glorfindel/enquiry/interrupteur.py"
PROD = "glorfindel/enquiry/production.py"
DEC = "glorfindel/enquiry/decision.py"
MEM = "glorfindel/enquiry/memoire.py"
LECTEUR = "glorfindel/enquiry/lecteur.py"
CATALOG = "glorfindel/enquiry/catalog.py"
QUEUE = "glorfindel/decision_queue.py"
AGENT = "glorfindel/agent.py"
_P = "tests/unit/test_enquiry_production.py"

MUTANTS = [
    ("M8266", "the switch ignored: GLORFINDEL_ENQUIRY=loop asked, today's enquiry runs (ENQ5b)", SWITCH,
     "    if not boucle():\n        return None\n    from glorfindel.enquiry import production\n",
     "    return None\n    from glorfindel.enquiry import production\n"),
    ("M8267", "a `sans_objet` counted as a gap: a ransomware under Linux never contained alone again (ENQ5b, §7.2)",
     DEC,
     "        if etat in (catalog.ECHEC, catalog.REFUSEE) and x.get(\"d_office\"):\n",
     "        if etat in (catalog.ECHEC, catalog.REFUSEE, catalog.SANS_OBJET) and x.get(\"d_office\"):\n"),
    ("M8268", "a `non_permise` counted as a gap: a line makes the model ask an unknown id, and the contention is "
     "held (ENQ5b, §7.2)", DEC,
     "        if etat in (catalog.ECHEC, catalog.REFUSEE) and x.get(\"d_office\"):\n",
     "        if etat in (catalog.ECHEC, catalog.REFUSEE, catalog.NON_PERMISE) and (x.get(\"d_office\")\n"
     "                                                                         or etat == catalog.NON_PERMISE):\n"),
    ("M8269", "an obligatory read still waiting not counted: the absence pushes toward the action (ENQ5b, §7.2)", DEC,
     "        elif etat == catalog.EN_ATTENTE and x.get(\"obligatoire\"):\n",
     "        elif False:\n"),
    ("M8270", "the model's verdict wins over the code's predicate (ENQ5b, §6.3 step 3)", DEC,
     "            verdict, par = du_code, \"code\"\n",
     "            verdict, par = dit, \"code\"\n"),
    ("M8271", "a read not done on this cycle accepted as a proof (ENQ5b, §6.3)", DEC,
     "            elif lu is None:\n                ko.append(f\"{rid} : aucune lecture faite sur ce cycle\")\n",
     "            elif lu is None:\n                ok.append(rid)\n"),
    ("M8272", "the trigger of the guard read in the citations: a relaxing hypothesis the code confirmed lifts the "
     "proposal on a grave technique (ENQ5b, §7.3)", DEC,
     "    said = _phrase(d[\"action\"], signal, enquete)\n",
     "    if any(h.get(\"verdict\") == \"confirme\" for h in enquete.get(\"hypotheses\") or []):\n"
     "        return floor, ceiling\n"
     "    said = _phrase(d[\"action\"], signal, enquete)\n"),
    ("M8273", "the floor executes: a snapshot run alone becomes an autonomous isolation (ENQ5b, §7.3)", DEC,
     "    if d[\"escalate\"]:\n        before = d[\"action\"]\n",
     "    if True:\n        before = d[\"action\"]\n"),
    ("M8274", "a decision with an enquiry admitted without the reserve of its turns (ENQ5b, §5.1, PRT1)", QUEUE,
     "        if turns := enquiry_turns(data):     # ENQ5b: a decision with an enquiry reserves its turns too\n",
     "        if turns := 0:\n"),
    ("M8275", "the memory of an object read for another: a file's own object taken for the one asked (ENQ5b, §5.5)",
     MEM,
     ("    if data is None or str(data.get(\"vm\", \"\")).rstrip(\"/\").lower() != str(vm).rstrip(\"/\").lower() \\\n"
      "            or data.get(\"regle\") != regle:\n",
      "    return ref_.montrable(ref, vm=vm, regle=regle, now=now)\n"),
     ("    if data is None:\n",
      "    return ref_.montrable(ref, vm=ref.vm, regle=ref.regle, now=now)\n")),
    ("M8276", "an unknown system read as Linux: a read that depends on it run, its empty answer an absence "
     "(ENQ5b, §9.6)", PROD,
     "            return os_ if os_ in catalog.SYSTEMS else \"\"\n",
     "            return os_ or catalog.LINUX\n"),
    ("M8277", "`fixed` changed: the decision's tool gains the loop's field without an enquiry (ENQ5b)", SWITCH,
     "        return message, prompt, tool\n",
     "        return message, prompt, __import__(\"glorfindel.enquiry.decision\", fromlist=[\"outil\"]).outil(tool)\n"),
    ("M8278", "the end of heartbeat_gap at T bare: beats 25 minutes late read as an agent cut (ENQ5b, §9.7)",
     CATALOG,
     "| union (print TimeGenerated = tenue)\n",
     "| union (print TimeGenerated = fin)\n"),
    ("M8279", "a read of the vault not taken on the ARM budget before it runs (ENQ5b, §9.6)", LECTEUR,
     "        if self.compter and not read_budget.ARM.take(1, read_budget.ENQUETE):\n",
     "        if False:\n"),
    ("M8280", "the enquiry's KQL queries not noted on the Log Analytics budget (ENQ5b, §9.6)", LECTEUR,
     "            read_budget.note_detection()\n",
     "            pass\n"),
    ("M8281", "the turns the enquiry made not counted when the decision ends (ENQ5b, PRT1)", QUEUE,
     "    return max(1, len(state.get(\"decision_draws\") or [])) + turns\n",
     "    return max(1, len(state.get(\"decision_draws\") or []))\n"),
    ("M8282", "a turn refused by the breaker, and decide calls the model all the same (ENQ5b, §5.1, PRT2)", AGENT,
     "    if refused := (state.get(\"enquete\") or {}).get(\"refusee\"):",
     "    if refused := \"\":"),
    ("M8283", "a read not served counted as a gap: « not yet » taken for a failure (ENQ5b, §9.6)", DEC,
     "        if not isinstance(x, dict) or not x.get(\"servie\", True):\n",
     "        if not isinstance(x, dict):\n"),
    ("M8284", "the floor plays on a detection that names no VM: an isolation proposed on the VM the card is only "
     "filed on (ENQ5b, §7.3, ATT1)", DEC,
     "    if (signal.get(\"context\") or {}).get(\"attribution\") == \"unattributed\":\n"
     "        return floor, ceiling                        # the attribution's card",
     "    if False:\n"
     "        return floor, ceiling                        # the attribution's card"),
    ("M8285", "« as usual » said receivable on a grave technique: the habit offered where it never holds (ENQ5b, "
     "§5.5 rule 2)", PROD,
     "        \"habitude_recevable\": ref_.habitude_recevable(ref, technique) if ref is not None else \"\",\n",
     "        \"habitude_recevable\": \"\",\n"),
]

TESTS = {
    "M8266": f"{_P}::test_the_switch_on_loop_runs_the_enquiry_in_investigate",
    "M8267": f"{_P}::test_a_sans_objet_read_is_never_a_gap",
    "M8268": f"{_P}::test_a_non_permise_read_is_never_a_gap",
    "M8269": f"{_P}::test_an_obligatory_read_still_waiting_is_a_gap",
    "M8270": f"{_P}::test_the_codes_predicate_wins_over_the_models_verdict",
    "M8271": f"{_P}::test_a_read_not_done_is_never_taken_for_a_proof",
    "M8272": f"{_P}::test_the_trigger_never_reads_the_citations",
    "M8273": f"{_P}::test_the_floor_never_runs_the_isolation_it_proposes",
    "M8274": f"{_P}::test_a_decision_with_an_enquiry_is_admitted_with_the_reserve_of_its_turns",
    "M8275": f"{_P}::test_the_memory_of_an_object_is_never_read_for_another",
    "M8276": f"{_P}::test_the_vms_system_comes_from_the_discovery_never_from_the_line",
    "M8277": f"{_P}::test_fixed_sends_origin_mains_message_prompt_and_tool_to_the_byte",
    "M8278": f"{_P}::test_the_loops_heartbeat_gap_writes_its_window_and_never_closes_it_at_t_bare",
    "M8279": f"{_P}::test_a_vault_read_the_arm_budget_refuses_is_refused_and_a_gap",
    "M8280": f"{_P}::test_each_kql_query_is_noted_on_log_analytics_never_refused",
    "M8281": f"{_P}::test_the_turns_made_are_counted_when_the_decision_ends",
    "M8282": f"{_P}::test_a_turn_refused_by_the_breaker_stops_the_enquiry_and_decide_takes_the_codes_path",
    "M8283": f"{_P}::test_a_read_not_served_and_a_read_the_model_asked_are_never_gaps",
    "M8284": f"{_P}::test_the_floor_is_the_attributions_on_a_detection_that_names_no_vm_and_steps_behind_other_cards",
    "M8285": f"{_P}::test_the_message_carries_the_sheet_the_enquiry_and_the_last_enquiry_in_their_order",
}
