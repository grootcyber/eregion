"""ENQ5a (#1162): the three reads that judge a ransomware served at the harness — the loop's reader anchored
on the signal (glorfindel/enquiry/lecteur.py), how far a source ingested (catalog.outcome), the marker of a
read not served and an obligatory read waiting as a gap (loop.py), the vault the configuration's, an unknown
system never read empty; the predicates of T1486-H1 and H2 (predicats.py); the vault's reads, DOS4's code
(glorfindel/providers/azure/dossier_reads.py); the capture at the bench (scripts/capture_enquete.py) and the
harness that plays it (scripts/harness_enquete.py); never wired to the watch. M7443–M7462, measured by
tests/unit/test_enquiry_reads.py, test_enquiry_loop.py and test_capture_enquete.py."""
CATALOG = "glorfindel/enquiry/catalog.py"
LOOP = "glorfindel/enquiry/loop.py"
LECTEUR = "glorfindel/enquiry/lecteur.py"
PRED = "glorfindel/enquiry/predicats.py"
CAPTURE = "scripts/capture_enquete.py"
HARNESS = "scripts/harness_enquete.py"
_R = "tests/unit/test_enquiry_reads.py"
_L = "tests/unit/test_enquiry_loop.py"
_C = "tests/unit/test_capture_enquete.py"

MUTANTS = [
    ("M7443", "a read not served said served: its marker lost, taken for a « sans objet » — « never » where it "
     "is « not yet » (ENQ5a, §4.3)", LOOP,
     "                           servie=False)\n",
     "                           servie=True)\n"),
    ("M7444", "an obligatory read still waiting reaches decide as « aucun résultat », no gap: the absence "
     "pushes toward the action (ENQ5a, §7.2)", LOOP,
     "        return self._echecs() + [r.id for r in self.lectures.values()\n"
     "                                 if r.etat == catalog.EN_ATTENTE and r.id in self.obligatoires]\n",
     "        return self._echecs()\n"),
    ("M7445", "the window counted from the read's own hour, not from the signal's: a read run late reads past "
     "the minutes that mattered (ENQ5a, §4)", LECTEUR,
     "    debut, fin = catalog.window(read, at)\n    lits = ",
     "    debut, fin = catalog.window(read, datetime.now(timezone.utc))\n    lits = "),
    ("M7446", "investigate's ago() left in the loop's query: a capture made a day later reads nothing of its "
     "episode (ENQ5a, §4)", LECTEUR,
     "    anchored = _AGO.sub(f\"TimeGenerated between ({_datetime(debut)} .. {_datetime(fin)})\", read.query)\n",
     "    anchored = read.query\n"),
    ("M7447", "how far the source ingested ignored: 25 minutes of delay said « nothing » once the declared "
     "latency passed (ENQ5a, EH10)", CATALOG,
     "    if at is not None and ingere is not None:\n",
     "    if False:\n"),
    ("M7448", "the vault taken from the detected line, not from the configuration: a line names the vault "
     "read (ENQ5a, §5.1)", LOOP,
     "            \"vault\": coffre}\n",
     "            \"vault\": (detection.get(\"vault\") if isinstance(detection, dict) else \"\") or coffre}\n"),
    ("M7449", "an unknown system taken for Windows: the Process counter read, its empty answer taken for an "
     "absence (ENQ5a, §4.1)", LOOP,
     "            if why := catalog.says(read, self.systeme):\n",
     "            if why := catalog.says(read, self.systeme or catalog.WINDOWS):\n"),
    ("M7450", "T1486-H1 judged on a minute not whole, or not ingested past: half a minute's samples confirm "
     "(ENQ5a, fiche T1486)", PRED,
     "        return m.echantillons >= self.cadence[m.volume] and self.ingeree(m.debut)\n",
     "        return True\n"),
    ("M7451", "T1486-H1 infirmed on one minute: the attack of 09/11, 18.4 then 59.4, infirmed at its first "
     "(ENQ5a, fiche T1486)", PRED,
     "        for debut in (m1, m1 + MINUTE):\n",
     "        for debut in (m1,):\n"),
    ("M7452", "the model's verdict wins over the coded predicate's (ENQ5a, §6.3 step 3)", LOOP,
     "            verdict, par = du_code, \"code\"\n",
     "            verdict, par = dit, \"code\"\n"),
    ("M7453", "T1486-H2 confirmed by a backup's job alone, H1 not infirmed: the hour of the backup covers the "
     "attack (ENQ5a, §9.2 case 3)", PRED,
     "    if v1 == INFIRME and partis:\n",
     "    if partis:\n"),
    ("M7454", "T1486-H2's job taken after the first sample: a backup started once the writes began explains "
     "them (ENQ5a, fiche T1486)", PRED,
     "                    and t0 - JOB_AVANT <= start <= t0:\n",
     "                    and start <= t0 + JOB_AVANT:\n"),
    ("M7455", "« no backup job » read before the vault's listing is whole: a job just started not listed yet "
     "infirms T1486-H2 (ENQ5a, DH2)", PRED,
     "    return lu.etat == catalog.LIGNES and now >= catalog.window(read, at)[1] + timedelta(seconds=read.latency_s)\n",
     "    return lu.etat == catalog.LIGNES\n"),
    ("M7456", "a module of the product imports the enquiry's lab: the predicates loaded by investigate "
     "(ENQ5a, never wired to the watch before ENQ5b)", "glorfindel/enquiry/fixed.py",
     "from glorfindel.enquiry import catalog\n",
     "from glorfindel.enquiry import catalog, predicats  # noqa: F401\n"),
    ("M7457", "a read of the vault kept among its writes: the activity log drowned in its reads (ENQ5a, EH8)",
     "glorfindel/providers/azure/dossier_reads.py",
     "                if not r[\"operation\"].lower().endswith(\"/read\")]\n",
     "                ]\n"),
    ("M7458", "a capture written in the repository: the bench's names enter it (ENQ5a)", CAPTURE,
     "    if path == ROOT or ROOT in path.parents:\n        raise Refus(",
     "    if False:\n        raise Refus("),
    ("M7459", "the capture anchored on the moment it runs, not on the episode's hour: it reads nothing of the "
     "episode (ENQ5a)", CAPTURE,
     "    lire = lecteur_.Lecteur(at, kql=kql_run, arm=arm, now=now)\n",
     "    lire = lecteur_.Lecteur(datetime.now(timezone.utc), kql=kql_run, arm=arm, now=now)\n"),
    ("M7460", "the bench's names kept in a capture by default: a VM, a subscription, an operator's address "
     "leave the bench (ENQ5a)", CAPTURE,
     "    cache = (lambda v: v) if args.keep_names else Pseudonymes(\n",
     "    cache = (lambda v: v) if True else Pseudonymes(\n"),
    ("M7461", "a capture replayed with its hindsight: rows ingested after the moment of the decision shown "
     "to it (ENQ5a, EH10)", HARNESS,
     "    kept = [r for r in rows if (_quand(r.get(\"IngereA\")) or now) <= now]\n",
     "    kept = rows\n"),
    ("M7462", "the harness reads a folder of the repository as captures (ENQ5a)", HARNESS,
     "    if root == ROOT or ROOT in root.parents:\n        raise CaptureRefusee(",
     "    if False:\n        raise CaptureRefusee("),
]

TESTS = {
    "M7443": f"{_L}::test_an_obligatory_read_not_served_carries_its_marker_never_sans_objet_s_never",
    "M7444": f"{_R}::test_an_obligatory_read_still_waiting_is_a_gap_an_optional_one_never",
    "M7445": f"{_R}::test_the_minute_series_is_read_from_five_minutes_before_the_signal_to_three_after",
    "M7446": _R,
    "M7447": f"{_R}::test_an_empty_answer_waits_until_its_source_has_ingested_the_end_of_its_window",
    "M7448": f"{_R}::test_the_vault_is_the_configuration_s_never_the_model_s_and_unknown_it_is_refused",
    "M7449": f"{_R}::test_an_unknown_system_never_stops_t1486_s_reads_and_never_reads_a_counter_empty",
    "M7450": f"{_R}::test_h1_never_confirms_on_a_minute_not_whole_nor_ingested",
    "M7451": f"{_R}::test_h1_infirms_only_on_two_minutes_of_every_volume_each_under_15",
    "M7452": f"{_L}::test_a_predicate_s_verdict_is_the_code_s_never_the_model_s",
    "M7453": f"{_R}::test_h2_never_confirms_without_h1_infirmed",
    "M7454": f"{_R}::test_h2_counts_only_a_backup_of_the_five_minutes_before_the_first_sample",
    "M7455": f"{_R}::test_h2_infirms_on_no_job_only_once_the_vault_s_jobs_are_read_whole",
    "M7456": f"{_L}::test_no_module_of_the_product_imports_the_loop",
    "M7457": f"{_R}::test_the_vault_s_activity_is_its_log_and_its_children_s_its_reads_set_aside",
    "M7458": f"{_C}::test_a_capture_inside_the_repository_is_refused_before_any_call",
    "M7459": f"{_C}::test_the_capture_reads_each_read_of_the_catalogue_anchored_on_the_signal",
    "M7460": f"{_C}::test_no_name_guid_nor_mail_of_the_bench_is_left_in_the_capture",
    "M7461": f"{_C}::test_a_capture_replayed_early_shows_only_what_had_been_ingested",
    "M7462": f"{_C}::test_the_harness_never_reads_captures_inside_the_repository",
}
