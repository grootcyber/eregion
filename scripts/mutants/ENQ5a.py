"""ENQ5a (#1162): the three reads that judge a ransomware served at the harness — the loop's reader anchored
on the signal (glorfindel/enquiry/lecteur.py), how far a source ingested (catalog.outcome), the marker of a
read not served and an obligatory read waiting as a gap (loop.py), the vault the configuration's, an unknown
system never read empty; the predicates of T1486-H1 and H2 (predicats.py); the vault's reads, DOS4's code
(glorfindel/providers/azure/dossier_reads.py); the capture at the bench (scripts/capture_enquete.py) and the
harness that plays it (scripts/harness_enquete.py); never wired to the watch. M7443–M7462, measured by
tests/unit/test_enquiry_reads.py, test_enquiry_loop.py and test_capture_enquete.py. M7465–M7472 (the review
of 80b4fd7d): a read that tells its ingestion read `vide` without it; the crossing not the rule's; the
reads « after » without their five minutes, or past the moment they run; the horizon on another counter;
the cadence the largest; an IPv4 address left in a capture; the main checkout taken for a capture."""
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
     "    debut, fin = catalog.window(read, at)\n    return debut, min(",
     "    debut, fin = catalog.window(read, datetime.now(timezone.utc))\n    return debut, min("),
    ("M7446", "investigate's ago() left in the loop's query: a capture made a day later reads nothing of its "
     "episode (ENQ5a, §4)", LECTEUR,
     "    anchored = _AGO.sub(f\"TimeGenerated between ({_datetime(debut)} .. {_datetime(fin)})\", read.query)\n",
     "    anchored = read.query\n"),
    ("M7447", "how far the source ingested ignored: 25 minutes of delay said « nothing » once the declared "
     "latency passed (ENQ5a, EH10)", CATALOG,
     "    if at is not None and (ingere is not None or read.id in INGESTION_DITE):\n",
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
     "        if path == root or root in path.parents:\n            raise Refus(",
     "        if False:\n            raise Refus("),
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

MUTANTS += [
    ("M7465", "a read that tells its ingestion, and said nothing ingested or nothing at all, read `vide`: a "
     "capture 25 minutes late replayed at 600 s says « no write » (ENQ5a review, EH10)", CATALOG,
     "        if ingere is None or ingere < window(read, at)[1]:\n",
     "        if ingere is not None and ingere < window(read, at)[1]:\n"),
    ("M7466", "the first crossing on one sample past 25 MB/s whatever the step, not the shipped rule's: a "
     "lone peak before the crossing taken for its minute (ENQ5a review)", CATALOG,
     "| extend Pic = (Fine and Rate > 45000000) or (not(Fine) and Rate > 25000000)\n",
     "| extend Pic = CounterValue > 25000000\n"),
    ("M7467", "root_commands read up to the signal only: the root shell that follows the escalation never "
     "read (ENQ5a review)", CATALOG,
     "         MappingProxyType({LINUX: READS_HERE, WINDOWS: _NO_SUDO}), ahead=timedelta(minutes=5)),\n",
     "         MappingProxyType({LINUX: READS_HERE, WINDOWS: _NO_SUDO})),\n"),
    ("M7468", "a window read past the moment its query runs: an end in the future (ENQ5a review)", LECTEUR,
     "    return debut, min(fin, now) if now is not None else fin\n",
     "    return debut, fin\n"),
    ("M7469", "the horizon on every counter of the VM: its CPU said ingested past the window, its disk empty "
     "read `vide` (ENQ5a review)", CATALOG,
     "| where _ResourceId =~ {vm}\n| where ObjectName in (\"Logical Disk\", \"LogicalDisk\")\n"
     "| where CounterName == \"Disk Write Bytes/sec\"\n| summarize max(TimeGenerated));\n",
     "| where _ResourceId =~ {vm}\n| summarize max(TimeGenerated));\n"),
    ("M7470", "the cadence the largest count: one minute of seven samples makes every minute of six "
     "incomplete (ENQ5a review)", PRED,
     "    counts = Counter(m.echantillons for m in ms)\n    top = max(counts.values())\n"
     "    return max(n for n, c in counts.items() if c == top)\n",
     "    return max(m.echantillons for m in ms)\n"),
    ("M7471", "an IPv4 address of the bench left in a capture (ENQ5a review)", CAPTURE,
     "        return _IPV4.sub(lambda m: m.group(0) if m.group(0).startswith(_TEST_NETS)\n"
     "                         else self._stable(\"ip\", m.group(0)), text)\n",
     "        return text\n"),
    ("M7472", "a worktree's guard that knows its own folder only: a capture written in the main checkout "
     "(ENQ5a review)", CAPTURE,
     "    if common and Path(common).name == \".git\" and Path(common).parent.resolve() not in roots:\n",
     "    if False:\n"),
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
    "M7465": _C,
    "M7466": f"{_R}::test_the_first_crossing_is_the_shipped_rule_s_own",
    "M7467": f"{_R}::test_the_reads_after_the_escalation_run_five_minutes_past_the_signal_never_past_now",
    "M7468": f"{_R}::test_the_reads_after_the_escalation_run_five_minutes_past_the_signal_never_past_now",
    "M7469": f"{_R}::test_the_horizon_reads_the_series_own_counter",
    "M7470": f"{_R}::test_the_cadence_is_the_step_s_or_the_most_common_never_the_largest",
    "M7471": f"{_C}::test_ip_addresses_and_the_reads_not_made_are_hidden_too",
    "M7472": f"{_C}::test_a_capture_in_the_main_checkout_a_worktree_shares_is_refused",
}
