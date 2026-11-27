"""WRT1 (#1275): who writes under Linux, by auditd — the write watches (off by default, `w` alone, posed by
AUD1's extension), and `process_write_audit`, their reader, declared apart from what the model sees: the VM's
lines alone in the signal's window, the beat never a writer and alone a witness of an absence, an event of two
SYSCALL records never attributed, a file's name never kept, its refusals said, its budget, the capture's reading
kept out of what the harness replays. M8193–M8206, measured by tests/unit/test_auditd_write.py."""
CAT = 'glorfindel/enquiry/catalog.py'
WRT = 'glorfindel/auditd_write.py'
CAP = 'scripts/capture_enquete.py'
VAR = 'infra/terraform/variables.tf'
SH = 'infra/terraform/scripts/auditd_write.sh'
_P = "tests/unit/test_auditd_write.py"

MUTANTS = [
    ('M8193', "process_write_audit served with the catalogue's reads: the loop, the message and the dossier see it before it is measured (WRT1, Q8)", CAT,
     '         MappingProxyType({LINUX: READS_HERE, WINDOWS: WRT_WINDOWS})),\n)}})\n',
     '         MappingProxyType({LINUX: READS_HERE, WINDOWS: WRT_WINDOWS})),\n)}})\nREADS = MappingProxyType({**READS, **A_MESURER})\n'),
    ('M8194', "the query not scoped to the VM: another VM's writers, or a host named like it, read for this one (WRT1)", CAT,
     '| where TimeGenerated between ({debut} .. {horizon})\n| where _ResourceId =~ {vm}\n',
     '| where TimeGenerated between ({debut} .. {horizon})\n'),
    ('M8195', "the writers read up to the beat's horizon: what was written after the signal counted as what led to it (WRT1)", CAT,
     '| where Battement or TimeGenerated <= {fin}\n',
     '| where Battement or TimeGenerated <= {horizon}\n'),
    ('M8196', "the beat taken for a writer: the timer's shell named among who modified files, and no absence ever vouched for (WRT1)", CAT,
     '| extend Battement = WatchKey == "eregion_write_beat"\n',
     '| extend Battement = WatchKey == "eregion_write_beat_"\n'),
    ('M8197', "no beat read as « nobody wrote »: a watch not set, or whose lines do not arrive, vouches for an absence (WRT1)", WRT,
     '    return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.WRT_SANS_MONTRE)\n',
     '    return catalog.Reading(read.id, catalog.VIDE)\n'),
    ('M8198', "a beat that stopped before the window's end vouches for the window: a VM switched off or an auditd stopped reads « nobody wrote » (WRT1)", WRT,
     '    if beat is not None and beat >= fin:\n',
     '    if beat is not None:\n'),
    ('M8199', "the write watches on by default: a plan of the bench changes the extension of every VM, and its cost, unasked (WRT1)", VAR,
     ' Posées par la même extension qu\'auditd (scripts/auditd.sh, puis scripts/auditd_write.sh) ; sans effet si auditd_enabled est à false. Défaut false."\n  type        = bool\n  default     = false\n',
     ' Posées par la même extension qu\'auditd (scripts/auditd.sh, puis scripts/auditd_write.sh) ; sans effet si auditd_enabled est à false. Défaut false."\n  type        = bool\n  default     = true\n'),
    ('M8200', "an event of two SYSCALL records attributed: a line written at a real event's serial chooses its writer (WRT1)", CAT,
     '| extend Writer = iff(Syscalls == 1, Writer, "");\n',
     '| extend Writer = Writer;\n'),
    ('M8201', "the file's name kept in the paths: a document's name leaves the workspace in the capture (WRT1)", WRT,
     '    pattern = "*" + ("." + ext.group(1) if ext else "")\n',
     '    pattern = base\n'),
    ('M8202', "the attribute changes watched too (`wa`): every chmod, chown and date a copy sets doubles the lines, and the cost (WRT1)", SH,
     '      echo "-a always,exit -F arch=b64 -F dir=$d -F perm=w -k eregion_write"\n',
     '      echo "-a always,exit -F arch=b64 -F dir=$d -F perm=wa -k eregion_write"\n'),
    ('M8203', "a failed query read as « nobody wrote »: a 403 or a missing Syslog table vouches for an absence (WRT1)", WRT,
     '        return catalog.Reading(read.id, catalog.ECHEC, why=f"{_pourquoi(exc)} ({type(exc).__name__})")\n',
     '        return catalog.Reading(read.id, catalog.VIDE)\n'),
    ('M8204', "an answer that is no list read as an empty one: an unreadable answer reads « no writer » (WRT1)", WRT,
     '    if not isinstance(rows, list):\n        return catalog.Reading(read.id, catalog.ECHEC, why=catalog.WRT_ILLISIBLE)\n',
     '    if not isinstance(rows, list):\n        rows = []\n'),
    ('M8205', "the read budget never taken: the workspace queried past it (WRT1, DOS4)", WRT,
     '    if not (budget or read_budget.LOG_ANALYTICS).take(1, WHO):\n',
     '    if False:\n'),
    ('M8206', "the reading to measure written among those the harness replays: a model sees it before it is measured (WRT1, Q8)", CAP,
     '    a_mesurer = {**a_mesurer, **mesurer_audit(vm=vm, at=at, kql_run=kql_run, now=now, systeme=systeme)}\n',
     '    a_mesurer = {**a_mesurer, **mesurer_audit(vm=vm, at=at, kql_run=kql_run, now=now, systeme=systeme)}\n    lectures.update({k: v["lignes"] for k, v in a_mesurer.items()})\n'),
]

TESTS = {
    'M8193': f'{_P}::test_declared_apart_never_in_the_reads_the_loop_serves {_P}::test_the_loop_never_permits_it',
    'M8194': f'{_P}::test_only_the_vm_s_lines_its_watch_s_keys_in_local6_from_the_plugin',
    'M8195': f'{_P}::test_the_window_is_the_signal_s_and_its_end_is_never_past',
    'M8196': f'{_P}::test_who_modified_files_by_executable_the_most_files_first {_P}::test_no_writer_and_the_beat_past_the_window_is_empty',
    'M8197': f'{_P}::test_no_beat_is_sans_objet_never_empty {_P}::test_the_capture_without_the_beat_says_sans_objet',
    'M8198': f'{_P}::test_a_beat_that_stopped_before_the_end_is_sans_objet',
    'M8199': f'{_P}::test_off_by_default_and_without_effect_off_auditd',
    'M8200': f'{_P}::test_an_event_with_two_syscall_records_is_never_attributed',
    'M8201': f'{_P}::test_paths_are_their_folder_and_extension_never_the_file_s_name',
    'M8202': f'{_P}::test_one_contract_the_fragment_the_catalogue_the_query',
    'M8203': f'{_P}::test_a_failed_query_is_a_failure_said_never_nothing',
    'M8204': f'{_P}::test_an_answer_unreadable_is_a_failure_never_nothing',
    'M8205': f'{_P}::test_the_budget_is_taken_before_the_query_and_refused_said {_P}::test_the_module_s_budget_is_log_analytics',
    'M8206': f'{_P}::test_the_capture_reads_it_apart_never_in_what_the_harness_plays',
}
