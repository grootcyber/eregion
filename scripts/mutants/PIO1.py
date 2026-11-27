"""PIO1 (#1258): who writes under Linux — process_write_io, declared apart from what the model sees, read in
PromQL by the provider's adapter (read only, its refusals said, never taken for « nothing », its budget), the
guest's word for a process's name, the capture's reading kept out of what the harness replays, the
collection off by default. M8090–M8105, measured by tests/unit/test_process_io.py."""
PROM = 'glorfindel/providers/azure/prometheus.py'
CAT = 'glorfindel/enquiry/catalog.py'
CAP = 'scripts/capture_enquete.py'
VAR = 'infra/terraform/variables.tf'
_P = "tests/unit/test_process_io.py"

MUTANTS = [
    ('M8090', "process_write_io served with the catalogue's reads: the loop, the message and the dossier see it before it is measured (PIO1, Q8)", CAT,
     '         MappingProxyType({LINUX: READS_HERE, WINDOWS: PIO_WINDOWS}), kind="promql"),\n)})\n',
     '         MappingProxyType({LINUX: READS_HERE, WINDOWS: PIO_WINDOWS}), kind="promql"),\n)})\nREADS = MappingProxyType({**READS, **A_MESURER})\n'),
    ('M8091', "the process's name taken for the platform's word: its author no longer says the guest forges it (PIO1)", CAT,
     '         PROCESS_WRITE_IO, ("vm",), timedelta(minutes=5), PROM_LATENCY_S, GUEST_FORGEABLE,\n',
     '         PROCESS_WRITE_IO, ("vm",), timedelta(minutes=5), PROM_LATENCY_S, PLATFORM,\n'),
    ('M8092', "the VM's id matched with its case: the workspace's case differs from the registry's, and no series is found — the collection said absent where it arrives (PIO1)", PROM,
     '    return \'"(?i)\' + _RE2_META.sub(r"\\\\\\\\\\1", vm) + \'"\'\n',
     '    return \'"\' + _RE2_META.sub(r"\\\\\\\\\\1", vm) + \'"\'\n'),
    ('M8093', "the id's dots not escaped in the regex: a `.` matches any character, another VM's series could be read for this one (PIO1)", PROM,
     '_RE2_META = re.compile(r"([.()\\\\])")\n',
     '_RE2_META = re.compile(r"([()\\\\])")\n'),
    ('M8094', "the bytes read summed in place of the bytes written: a backup's reads taken for writes (PIO1)", CAT,
     '                    + \'", "\' + PROCESS_IO_RESOURCE + \'"=~{vm}, direction="write"}}[{duree}s])))\')\n',
     '                    + \'", "\' + PROCESS_IO_RESOURCE + \'"=~{vm}, direction="read"}}[{duree}s])))\')\n'),
    ('M8095', "a redirection followed: the identity's token sent to another host (PIO1)", PROM,
     '                             timeout=self._timeout, allow_redirects=False)\n',
     '                             timeout=self._timeout, allow_redirects=True)\n'),
    ('M8096', 'a 403 read as no series: the right absent said « the collection does not arrive » (PIO1)', PROM,
     '            raise Illisible(f"no right on the workspace ({status})", "right", status=status)\n',
     '            return []\n'),
    ('M8097', 'an absent workspace read as no series, never as a failure (PIO1)', PROM,
     '            raise Illisible("the workspace answered 404", "absent", status=status)\n',
     '            return []\n'),
    ('M8098', 'no series for the VM read as « nobody wrote »: a collection that does not arrive vouches for an absence (PIO1)', PROM,
     '    if not result:\n        return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.PIO_SANS_SERIE)\n',
     ''),
    ('M8099', 'an answer that is no vector read as no series (PIO1)', PROM,
     '            raise Illisible("the workspace\'s answer is not a PromQL vector", "error")\n',
     '            return []\n'),
    ('M8100', 'a value without a number dropped as zero: an unreadable answer read as « nobody wrote » (PIO1)', PROM,
     '        if not math.isfinite(octets):\n',
     '        if False:\n'),
    ('M8101', 'no workspace configured read as empty: « nobody wrote » where nothing was read (PIO1)', PROM,
     '        return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.PIO_SANS_ESPACE)\n',
     '        return catalog.Reading(read.id, catalog.VIDE)\n'),
    ('M8102', "the guest's name carried raw: its control characters and its length pass into the capture (PIO1)", PROM,
     '    text = "".join(ch for ch in str(raw) if unicodedata.category(ch)[0] != "C")[:NAME_MAX]\n',
     '    text = str(raw)\n'),
    ('M8103', 'the read budget never taken: the workspace queried past it (PIO1)', PROM,
     '    if not (budget or read_budget.PROMETHEUS).take(1, WHO):\n',
     '    if False:\n'),
    ('M8104', 'the reading to measure written among those the harness replays: a model sees it before it is measured (PIO1, Q8)', CAP,
     '    a_mesurer = mesurer(vm=vm, at=at, prom=prom, now=now)\n',
     '    a_mesurer = mesurer(vm=vm, at=at, prom=prom, now=now)\n    lectures.update({k: v["lignes"] for k, v in a_mesurer.items()})\n'),
    ('M8105', 'the collection on by default: a plan of the bench poses a workspace, a DCR and their cost unasked (PIO1)', VAR,
     '  description = "PIO1 : un espace de travail Azure Monitor, une DCR à part qui y envoie la métrique OpenTelemetry process.disk.io (les octets lus et écrits par processus) de chaque VM du banc, et leurs associations — la lecture process_write_io de l\'enquête, à mesurer au banc. La DCR de la règle reste intacte. Coût : à l\'échantillon ingéré (docs/operations.md). Défaut false."\n  type        = bool\n  default     = false\n',
     '  description = "PIO1 : un espace de travail Azure Monitor, une DCR à part qui y envoie la métrique OpenTelemetry process.disk.io (les octets lus et écrits par processus) de chaque VM du banc, et leurs associations — la lecture process_write_io de l\'enquête, à mesurer au banc. La DCR de la règle reste intacte. Coût : à l\'échantillon ingéré (docs/operations.md). Défaut false."\n  type        = bool\n  default     = true\n'),
]

TESTS = {
    'M8090': f'{_P}::test_declared_apart_never_in_the_reads_the_loop_serves {_P}::test_the_loop_never_permits_it_and_says_it_not_served',
    'M8091': f'{_P}::test_declared_apart_never_in_the_reads_the_loop_serves',
    'M8092': f'{_P}::test_the_promql_reads_the_writes_of_the_vm_by_executable_the_first_n',
    'M8093': f'{_P}::test_the_promql_reads_the_writes_of_the_vm_by_executable_the_first_n',
    'M8094': f'{_P}::test_the_promql_reads_the_writes_of_the_vm_by_executable_the_first_n',
    'M8095': f'{_P}::test_one_post_to_the_query_api_with_the_identity_and_no_redirection',
    'M8096': f'{_P}::test_a_refusal_of_the_workspace_is_a_failure_said',
    'M8097': f'{_P}::test_a_refusal_of_the_workspace_is_a_failure_said',
    'M8098': f'{_P}::test_no_series_for_the_vm_is_sans_objet_never_empty',
    'M8099': f'{_P}::test_an_answer_unreadable_is_a_failure_never_nothing',
    'M8100': f'{_P}::test_an_answer_unreadable_is_a_failure_never_nothing',
    'M8101': f'{_P}::test_no_workspace_is_sans_objet_and_nothing_queried {_P}::test_without_the_endpoint_it_is_said_sans_objet_and_nothing_queried',
    'M8102': f'{_P}::test_the_name_is_carried_as_the_guest_wrote_it_bounded_whatever_the_label_s_case',
    'M8103': f'{_P}::test_the_budget_is_taken_before_the_query_and_refused_said {_P}::test_the_module_s_budget_is_the_reader_s_and_the_watch_says_it',
    'M8104': f'{_P}::test_the_capture_reads_it_apart_never_in_what_the_harness_plays',
    'M8105': f'{_P}::test_the_collection_is_off_by_default_and_collects_process_disk_io_alone',
}
