"""SEC-I (#850): the enquiry scoped by the registry's VM, never the line's host name, and none on a
detection attributed to no VM (glorfindel/agent.py); the correlation without its fallback on the host
name (glorfindel/correlation.py); the blob exfiltration rule on written writes only, the log-tampering
rule setting a writer aside only on an event of one SYSCALL record (glorfindel/rules/azure/
detection_rules.yaml); the memory weighing the VM and the rule, one precedent per VM, the VM and the
rule stored, never an anchor's, no cycle said corroborated (glorfindel/memory.py, glorfindel/agent.py).
M5821–M5840, measured by tests/unit/test_enquiry_memory.py."""
AGENT = "glorfindel/agent.py"
COR = "glorfindel/correlation.py"
RULES = "glorfindel/rules/azure/detection_rules.yaml"
MEM = "glorfindel/memory.py"
_T = "tests/unit/test_enquiry_memory.py"

MUTANTS = [
    ("M5821", "one query of the enquiry scoped by the line's host name again (SEC-I, V-09)", AGENT,
     "| where _ResourceId =~ {vm}\n// sudo logs to authpriv (measured under AMA).\n",
     "| where Computer == {vm}\n// sudo logs to authpriv (measured under AMA).\n"),
    ("M5822", "the enquiry takes the line's Computer for the VM again (SEC-I, V-09)", AGENT,
     "    vm_lit = None if unattributed else value(kql.resource_id, rid)\n",
     '    vm_lit = None if unattributed else value(kql.name, str(first_row.get("Computer") or vm))\n'),
    ("M5823", "the anchor of a detection attributed to no VM enquired on as the VM (SEC-I, V-09)", AGENT,
     "    vm_lit = None if unattributed else value(kql.resource_id, rid)\n",
     "    vm_lit = value(kql.resource_id, rid)\n"),
    ("M5824", "the correlation falls back on the host name when the row has no _ResourceId (SEC-I, V-09)",
     COR,
     "    except kql.UnsafeValue:\n        return None\n\n\n# ── The sessions",
     "    except kql.UnsafeValue:\n        try:\n"
     "            return f\"Computer == {kql.literal(kql.name(row.get('Computer')))}\"\n"
     "        except kql.UnsafeValue:\n            return None\n\n\n# ── The sessions"),
    ("M5825", "a refused blob write counts as an exfiltration again (SEC-I, V-10)", RULES,
     "      | where toint(StatusCode) between (200 .. 299)\n",
     ""),
    ("M5826", "the log-tamper rule counts lines, not distinct records: a line delivered twice makes a card "
     "(SEC-I, V-24, review)", RULES,
     "      | extend Alone = Syscalls == 1\n",
     "      | extend Alone = Tampers == 1\n"),
    ("M5827", "Tampers > 0 again: an event of two SYSCALL records still set aside (SEC-I, V-24)", RULES,
     "      | extend Alone = Syscalls == 1\n",
     "      | extend Alone = Syscalls > 0\n"),
    ("M5828", "a daemon's record added to the event sets it aside again (SEC-I, V-24)", RULES,
     "      | where not(Alone and Daemons > 0)\n",
     "      | where Daemons == 0\n"),
    ("M5829", "a session writer's record added to the event sets it aside again (SEC-I, V-24)", RULES,
     "      | where not(Alone and Sessions > 0 and Entries > 0 and SessionFiles == Entries)\n",
     "      | where not(Sessions > 0 and Entries > 0 and SessionFiles == Entries)\n"),
    ("M5830", "the VM's own cycles not searched by its id: a flood hides them (SEC-I, V-11)", MEM,
     '        if vm:\n            gather({"resource_id": vm})\n',
     ""),
    ("M5831", "the VM absent from the similarity: a nearer cycle of another VM first (SEC-I, V-11)", MEM,
     '                    not vm or meta.get("resource_id") != vm, distance)\n',
     "                    distance)\n"),
    ("M5832", "no bound per VM: a flood of one VM's cycles fills every place (SEC-I, V-11)", MEM,
     "                if key in seen or per_vm.get(owner, 0) >= PER_VM:\n",
     "                if key in seen:\n"),
    ("M5833", "no search past a VM at its bound: a flood hides the other VMs' cycles (SEC-I, V-11)", MEM,
     '            if len(cycles) == n or not full or not gather({"resource_id": {"$nin": full}}, wide="" in full):\n',
     "            if True:\n"),
    ("M5834", "a cycle stored without its VM: every cycle one VM unknown (SEC-I, V-11)", MEM,
     '                "resource_id": _vm_key(cycle.get("resource_id")),\n',
     '                "resource_id": "",\n'),
    ("M5835", "the anchor of an unattributed detection stored as its VM (SEC-I, V-11)", AGENT,
     '        "resource_id": "" if (signal.get("context") or {}).get("attribution") == "unattributed"\n'
     '                       else signal.get("resource_id", ""),\n',
     '        "resource_id": signal.get("resource_id", ""),\n'),
    ("M5836", "the rule absent from the similarity (SEC-I, V-11)", MEM,
     '            return (not rule or meta.get("rule_name") != rule,\n'
     '                    not vm or meta.get("resource_id") != vm, distance)\n',
     '            return (not vm or meta.get("resource_id") != vm, distance)\n'),
    ("M5837", "a cycle stored as corroborated when nothing corroborated it (SEC-I, V-11)", MEM,
     '                "corroborated": cycle.get("corroborated") is True,\n',
     '                "corroborated": True,\n'),
    ("M5838", "the VM keyed in the case it came in: the registry's and the row's never meet (SEC-I)", MEM,
     '    return resource_id.rstrip("/").lower() if isinstance(resource_id, str) else ""\n',
     '    return resource_id.rstrip("/") if isinstance(resource_id, str) else ""\n'),
    ("M5840", "the search past the VM unknown reads as few as before: cycles stored before SEC-I hide the "
     "other VMs (SEC-I, V-11, review)", MEM,
     'gather({"resource_id": {"$nin": full}}, wide="" in full)',
     'gather({"resource_id": {"$nin": full}})'),
    ("M5839", "the anchor of an unattributed signal weighed as its VM (SEC-I, V-11)", MEM,
     '    if (signal.get("context") or {}).get("attribution") == "unattributed":\n        return ""\n'
     '    return _vm_key(signal.get("resource_id"))\n',
     '    return _vm_key(signal.get("resource_id"))\n'),
]

TESTS = {
    "M5821": f"{_T}::test_every_enquiry_query_is_scoped_by_the_resource_id "
             f"{_T}::test_a_line_whose_host_name_and_resource_id_diverge_is_enquired_on_the_registrys_vm",
    "M5822": f"{_T}::test_a_line_whose_host_name_and_resource_id_diverge_is_enquired_on_the_registrys_vm",
    "M5823": f"{_T}::test_an_unattributed_detection_runs_no_enquiry",
    "M5824": f"{_T}::test_the_correlation_scope_is_the_resource_id_only "
             f"{_T}::test_a_brute_force_row_without_its_resource_id_is_left_unchecked",
    "M5825": f"{_T}::test_a_refused_write_moved_nothing",
    "M5826": f"{_T}::test_a_record_the_agent_delivers_twice_is_one_record",
    "M5827": f"{_T}::test_a_daemons_record_added_to_the_event_no_longer_sets_it_aside",
    "M5828": f"{_T}::test_a_daemons_record_added_to_the_event_no_longer_sets_it_aside",
    "M5829": f"{_T}::test_a_known_writers_record_added_to_the_event_no_longer_sets_it_aside",
    "M5830": f"{_T}::test_the_vms_own_cycle_is_found_past_a_flood_of_nearer_ones",
    "M5831": f"{_T}::test_a_cycle_of_the_same_vm_comes_before_a_nearer_one_of_another",
    "M5832": f"{_T}::test_a_flood_of_one_vms_cycles_takes_one_place_on_its_neighbours",
    "M5833": f"{_T}::test_another_vms_cycle_is_found_past_a_flood_of_nearer_ones",
    "M5834": f"{_T}::test_a_flood_of_one_vms_cycles_takes_one_place_on_its_neighbours",
    "M5835": f"{_T}::test_the_anchor_of_an_unattributed_detection_is_never_stored_as_its_vm",
    "M5836": f"{_T}::test_a_cycle_of_the_same_rule_comes_before_a_nearer_one_of_another",
    "M5837": f"{_T}::test_a_cycle_keeps_its_vm_rule_and_says_it_was_not_corroborated",
    "M5838": f"{_T}::test_a_cycle_keeps_its_vm_rule_and_says_it_was_not_corroborated "
             f"{_T}::test_the_vms_own_cycle_is_found_past_a_flood_of_nearer_ones",
    "M5839": f"{_T}::test_an_unattributed_signal_is_weighed_by_no_vm",
    "M5840": f"{_T}::test_more_cycles_that_name_no_vm_than_a_search_reads_never_hide_the_other_vms",
}
