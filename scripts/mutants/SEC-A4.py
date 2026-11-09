"""SEC-A4 (#633; audit of 06/11, V-04 and V-05): what a detection row is attributed by — never its
host name (V-04: a rule whose rows carry neither `_ResourceId` nor `CallerIpAddress` refused at
load and at approval), never an appliance's address (V-05: a VM that forwards packets is marked,
every action held on a call made from behind it). M4540–M4544, measured by
tests/unit/test_rule_routing.py. M1335 and M1363 (the host name's reading) retired with it."""
READERS = "glorfindel/providers/azure/readers.py"
RULES = "glorfindel/detection_rules.py"
PROPOSED = "glorfindel/proposed_rules.py"
AGENT = "glorfindel/agent.py"
_T = "tests/unit/test_rule_routing.py"

MUTANTS = [
    ("M4540", "IP forwarding never read: an exfiltration through a hub's appliance pinned on the "
     "appliance, whose isolation cuts the hub (SEC-A4, V-05)", READERS,
     '            if getattr(nic, "enable_ip_forwarding", None) is True:\n',
     "            if False:\n"),
    ("M4541", "a row routed by its host name again: root on a VM names another, which is isolated "
     "(SEC-A4, V-04)", RULES,
     "        ip = _caller_ip(row)\n        owner = (self._owners() or {}).get(ip) if ip else None\n"
     "        if owner and not appliance_of(owner):\n",
     '        comp = row.get("Computer")\n'
     "        hit = next((t for t in self.by_rid.values() if isinstance(comp, str) and comp\n"
     '                    and t[1].lower() == comp.split(".")[0].lower()), None)\n'
     "        if hit:\n"
     "            return True, hit\n"
     "        ip = _caller_ip(row)\n        owner = (self._owners() or {}).get(ip) if ip else None\n"
     "        if owner and not appliance_of(owner):\n"),
    ("M4542", "a rule whose rows name no VM but by their host name loaded (SEC-A4, V-04)", RULES,
     '        refused = routing_refusal(item.get("source", "azure_monitor"), item.get("query") or "")\n',
     '        refused = ""\n'),
    ("M4543", "a proposed rule routed by the host name approved into the client's layer (SEC-A4, V-04)",
     PROPOSED,
     '    refused = routing_refusal(proposal.get("source") or "azure_monitor", query) or routing_refusal("azure_monitor", query)\n',
     '    refused = ""\n'),
    ("M4544", "a call from behind an appliance holds only the isolation and the block: a snapshot, a "
     "release run on the appliance, the card says nothing of where to look (SEC-A4, V-05)", AGENT,
     '    if ctx.get("attribution") == "unattributed" and ctx.get("attribution_via") == "appliance":\n',
     "    if False:\n"),
]
TESTS = {
    "M4540": f"{_T}::test_the_connector_marks_every_address_of_a_vm_that_forwards "
             f"{_T}::test_an_exfiltration_through_the_appliance_is_never_pinned_on_it",
    "M4541": f"{_T}::test_a_row_named_only_by_its_host_name_routes_to_no_vm",
    "M4542": f"{_T}::test_a_rule_routed_by_its_host_name_is_refused_at_load",
    "M4543": f"{_T}::test_an_approval_of_a_rule_routed_by_its_host_name_is_refused_clearly",
    "M4544": f"{_T}::test_an_exfiltration_through_the_appliance_is_never_pinned_on_it "
             f"{_T}::test_an_attack_started_through_the_appliance_holds_everything",
}
