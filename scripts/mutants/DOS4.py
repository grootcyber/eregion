"""DOS4 (#1138): the dossier's reads of Azure — their window anchored on the signal, each bounded, unreadable
never empty (glorfindel/providers/azure/dossier_reads.py); never for a detection attributed to no VM; the
budget shared with the detection, the detection first, a real dossier before an exercise, a critical object
never without its dossier (glorfindel/read_budget.py, glorfindel/dossier_pass.py); the steps 1, 1 bis, 2 and
the settling; the facts of the platform (glorfindel/dossier_platform.py); the catalogue's form (one
vocabulary of states, the sentinel of `raw`: glorfindel/enquiry/catalog.py, fixed.py); a block proposal
approved kept 30 days after its unblock (glorfindel/dossier.py). M7290–M7309, measured by
tests/unit/test_dossier_reads.py and tests/unit/test_read_budget.py."""
READS = "glorfindel/providers/azure/dossier_reads.py"
DOSSIER = "glorfindel/dossier.py"
LOCAL = "glorfindel/dossier_local.py"
PASS = "glorfindel/dossier_pass.py"
PLATFORM = "glorfindel/dossier_platform.py"
BUDGET = "glorfindel/read_budget.py"
RULES = "glorfindel/detection_rules.py"
CATALOG = "glorfindel/enquiry/catalog.py"
FIXED = "glorfindel/enquiry/fixed.py"
_T = "tests/unit/test_dossier_reads.py"
_B = "tests/unit/test_read_budget.py"

MUTANTS = [
    ("M7290", "the window anchored on the moment of the read, not on the signal: read late, the reads look "
     "past the minutes that mattered (DOS4)", READS,
     "            start, end = catalog.window(read, at)\n",
     "            start, end = catalog.window(read, now)\n"),
    ("M7291", "a read that fails said empty: « no backup job », « no gesture » where nothing was read (DOS4)",
     READS,
     "                out[read_id] = catalog.Reading(read_id, catalog.ECHEC, why=_first_line(exc))\n",
     "                out[read_id] = catalog.outcome(read, [], at=at, now=now)\n"),
    ("M7292", "the bound of the activity log's pages removed: a log longer than it read as all of it (DOS4)",
     READS,
     "            got, pages = self._arm_paged(url, params)\n",
     "            got, pages = self._arm_paged(url, params, bound=10**6)\n"),
    ("M7293", "a metrics' answer of another shape read as « no point » (DOS4)", READS,
     "            if not isinstance(series, list):\n"
     "                raise RuntimeError(\"réponse d'ARM mal formée : une métrique sans sa liste `timeseries`\")\n",
     "            if not isinstance(series, list):\n                continue\n"),
    ("M7294", "Resource Health answering without its state, read as a state (DOS4)", READS,
     '        if not isinstance(props, dict) or not props.get("availabilityState"):\n',
     "        if not isinstance(props, dict):\n"),
    ("M7295", "the bound of the vault's listing removed: a vault longer than it read as whole (DOS4)", READS,
     "            if seen > JOBS_MAX:\n",
     "            if False:\n"),
    ("M7296", "the attribution not read: the anchor VM of a detection attributed to no VM read on Azure (DOS4, "
     "the decision of 23/11)", DOSSIER,
     '    unattributed = ctx.get("attribution") == "unattributed"\n',
     "    unattributed = False\n"),
    ("M7297", "what still waits at T + 30 min written empty: « nothing » where the source delivered nothing (DOS4)",
     PASS,
     '            f = {**f, "etat": ILLISIBLE, "pourquoi": NOTHING_IN_30, "lu_a": now.isoformat()}\n',
     '            f = {**f, "etat": "vide", "lu_a": now.isoformat()}\n'),
    ("M7298", "a critical object dropped like any other: past 30 min without room, « not composed » (DOS4, the "
     "decision of 24/11)", PASS,
     '    if not doc.get("critique", True) and (t is None or now >= t + timedelta(seconds=SETTLE_S)):\n',
     "    if t is None or now >= t + timedelta(seconds=SETTLE_S):\n"),
    ("M7299", "the order of the dossiers lost: an older exercise reads before a real isolation (DOS4)", PASS,
     '    return (doc.get("source") == "exercise", not doc.get("critique", True), str(doc.get("T") or ""))\n',
     '    return (str(doc.get("T") or ""),)\n'),
    ("M7300", "a block proposal approved since not read by the retention: its dossier gone 30 days after the "
     "card, the address still blocked (DOS4)", DOSSIER,
     '    if doc.get("perimetre") == PROPOSITION and doc.get("action") == "block_suspicious_ip" and any(\n',
     "    if False and any(\n"),
    ("M7301", "the strict order not held: a dossier refused, the one behind it asks less and reads first (DOS4)",
     PASS,
     "            blocked = True                   # strict order: no dossier behind it reads in this pass\n",
     "            blocked = False\n"),
    ("M7302", "the detection's read refused past the budget like the dossier's: the detection behind the "
     "dossier (DOS4, the decision of 24/11)", BUDGET,
     "            self._spent.append((now, who, max(0, int(n))))\n",
     "            if sum(k for _, _, k in self._spent) + n > per_min():\n                return\n"
     "            self._spent.append((now, who, max(0, int(n))))\n"),
    ("M7303", "the RulePoller asking the budget before its query: a minute the dossier took, the detection "
     "skips its poll (DOS4)", RULES,
     "        read_budget.note_detection()\n        try:\n            now_dt = datetime.now(timezone.utc)\n",
     "        if not read_budget.BUDGET.take(1, read_budget.DETECTION):\n            return []\n"
     "        try:\n            now_dt = datetime.now(timezone.utc)\n"),
    ("M7304", "a raw None skipping its check again: the read not run, the value refused never said (DOS4, "
     "ENQ2's review)", FIXED,
     "            filled[p] = None if raw[p] is catalog.NO_OBJECT else value(catalog.PARAMS[p].check, raw[p])\n",
     "            filled[p] = None if raw[p] is catalog.NO_OBJECT or raw[p] is None else value(catalog.PARAMS[p].check, raw[p])\n"),
    ("M7305", "the two vocabularies apart again: a read in failure said empty on the card (DOS4)", CATALOG,
     '    ECHEC: "illisible", REFUSEE: "illisible", NON_PERMISE: "illisible"})\n',
     '    ECHEC: "vide", REFUSEE: "illisible", NON_PERMISE: "illisible"})\n'),
    ("M7306", "an empty answer before its window closed said empty, not waiting (DOS4)", PLATFORM,
     "        if complete(read_id, self.t, self.now):\n            return fact(code, id_, etat=VIDE,",
     "        if True:\n            return fact(code, id_, etat=VIDE,"),
    ("M7307", "a drain never confirmed written « read »: the sessions perhaps still open, said cut (DOS4, "
     "DRN1)", LOCAL,
     '    if case == "never":                # DOS4: never confirmed — perhaps cut, perhaps not: unknown\n',
     "    if False:\n"),
    ("M7308", "the row's time taken whatever it says: a forged hour steers the reads to a quiet window (DOS4)",
     DOSSIER,
     "    if at_row is not None and (at_signal is None or at_signal - ROW_BEFORE_S <= at_row <= at_signal + ROW_SKEW_S):\n",
     "    if at_row is not None:\n"),
    ("M7309", "anyone's gesture taken for Glorfindel's: a third party's extension said Glorfindel's own (DOS4)",
     PLATFORM,
     '    rows = [r for r in f.events() if mine & set(r.get("ids") or []) and (_when(r.get("at")) or since) >= since]\n',
     '    rows = [r for r in f.events() if (_when(r.get("at")) or since) >= since]\n'),
]

TESTS = {
    "M7290": f"{_T}::test_the_window_is_anchored_on_the_signal_never_on_the_read",
    "M7291": f"{_T}::test_a_read_that_fails_is_unreadable_never_empty",
    "M7292": f"{_T}::test_a_cut_activity_log_is_unreadable_never_complete",
    "M7293": f"{_T}::test_a_metrics_answer_of_another_shape_is_unreadable",
    "M7294": f"{_T}::test_a_health_answer_without_its_state_is_unreadable",
    "M7295": f"{_T}::test_a_vault_past_its_bound_is_unreadable",
    "M7296": f"{_T}::test_a_detection_attributed_to_no_vm_is_never_read_on_azure_and_says_it",
    "M7297": f"{_T}::test_what_is_still_waiting_at_30_min_is_unreadable_never_empty",
    "M7298": f"{_T}::test_a_critical_object_is_never_without_its_dossier",
    "M7299": f"{_T}::test_a_real_isolation_reads_before_an_exercise",
    "M7300": f"{_T}::test_a_block_proposal_approved_keeps_its_dossier_until_30_days_after_the_unblock",
    "M7301": f"{_T}::test_a_dossier_refused_lets_none_behind_it_read",
    "M7302": f"{_B}::test_the_detection_is_never_refused_and_leaves_the_dossier_nothing",
    "M7303": f"{_B}::test_the_rulepoller_queries_whatever_the_dossier_took_and_notes_its_read",
    "M7304": f"{_T}::test_a_raw_none_goes_through_its_check_only_the_sentinel_skips_it",
    "M7305": f"{_T}::test_one_vocabulary_the_seven_states_of_a_read_and_the_five_words_of_a_fact "
             f"{_T}::test_a_read_that_fails_is_unreadable_never_empty",
    "M7306": f"{_T}::test_step_1_bis_reads_again_what_was_not_delivered_and_settles_at_30_min",
    "M7307": f"{_T}::test_a_drain_never_confirmed_is_unreadable",
    "M7308": f"{_T}::test_a_forged_row_time_never_steers_the_window",
    "M7309": f"{_T}::test_a_vm_read_whole_gives_its_facts_with_their_source_author_and_measure",
}
