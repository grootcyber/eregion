"""ORPH2b (#1126): the names an older version suffixed by a VM (`glorfindel-isolation-deny-all-<vm>`,
`-<vm>-out`: its deny scoped to the VM's address on a subnet's NSG), left on an NSG that governs no NIC and
no subnet, are said as ORPH2 says the fixed names — the same card, the same mark, never taken off (SEC-H) —
and the card names the VM they named. Never our quarantine's names, never an allow. M7219–M7225, measured
by tests/unit/test_dormant_isolation.py; M7263–M7264: the review of ORPH2b.
"""
FIND = "glorfindel/providers/azure/dormant.py"
PASS = "glorfindel/dormant_isolations.py"
_T = "tests/unit/test_dormant_isolation.py"

MUTANTS = [
    ("M7219", "the names suffixed by a VM not read: an older isolation of a subnet's NSG detached since, "
              "said by nothing, as before ORPH2b", FIND,
     "    if not low.startswith(f\"{base}-\"):\n"
     "        return None\n",
     "    if True:\n"
     "        return None\n"),
    ("M7220", "any name of ours taken for an older isolation: our quarantine NSG, left empty by a release, "
              "said as an older isolation (ORPH2b)", FIND,
     "    if not low.startswith(f\"{base}-\"):\n",
     "    if not low.startswith(\"glorfindel-\"):\n"),
    ("M7221", "the VM read from the name alone: the outbound rule's `-out` kept, the card names a VM "
              "`<vm>-out` that never was (ORPH2b)", FIND,
     "        vm = vm[:-len(\"-out\")]\n",
     "        pass\n"),
    ("M7222", "the VMs the suffixed names named left out of what the card says of whose they were: it "
              "says neither the fixed names nor a VM (ORPH2b)", PASS,
     "    vms = sorted({r[\"vm\"] for r in e[\"rules\"] if r.get(\"vm\")}, key=str.lower)\n",
     "    vms = []\n"),
    ("M7223", "names compared with their case: Azure's hold none, a rule written `Glorfindel-Isolation-…` "
              "said by nothing (ORPH2b)", FIND,
     "    low, base = name.lower(), isolation_name.lower()\n",
     "    low, base = name, isolation_name\n"),
    ("M7224", "what the card says compared on the fixed names only: a suffixed rule taken off by hand, "
              "the card still names it (ORPH2b)", PASS,
     "    return {\"rules\": sorted(r[\"name\"].lower() for r in e[\"rules\"]),\n",
     "    return {\"rules\": sorted(r[\"name\"].lower() for r in e[\"rules\"] if not r.get(\"vm\")),\n"),
    ("M7225", "each rule on the card without the VM it named: the operator told the rules, not which VM "
              "each one cut (ORPH2b)", PASS,
     "                     + (f\", VM {r['vm']}\" if r.get(\"vm\") else \"\") + \")\" for r in e[\"rules\"])\n",
     "                     + \")\" for r in e[\"rules\"])\n"),
    ("M7263", "the VM's `-out` stripped whatever the rule's direction: a VM named `…-out` isolated "
              "inbound said as another VM (the review of ORPH2b)", FIND,
     "    if direction == \"outbound\" and vm.lower().endswith(\"-out\"):\n",
     "    if vm.lower().endswith(\"-out\"):\n"),
    ("M7264", "the fixed outbound name read as a suffixed one: `glorfindel-isolation-deny-all-out` said "
              "as an isolation of a VM `out` (the review of ORPH2b)", FIND,
     "    if low in (base, f\"{base}-out\"):\n",
     "    if low == base:\n"),
]

TESTS = {
    "M7219": f"{_T}::test_the_names_suffixed_by_a_vm_are_said_once_and_nothing_is_taken_off",
    "M7220": f"{_T}::test_our_quarantine_rules_are_never_an_older_isolation",
    "M7221": f"{_T}::test_a_subnet_nsg_detached_since_is_said_with_the_vm_it_named",
    "M7222": f"{_T}::test_a_card_says_the_fixed_names_and_the_vms_together",
    "M7223": f"{_T}::test_a_subnet_nsg_detached_since_is_said_with_the_vm_it_named",
    "M7224": f"{_T}::test_a_suffixed_rule_taken_off_by_hand_replaces_the_card",
    "M7225": f"{_T}::test_the_names_suffixed_by_a_vm_are_said_once_and_nothing_is_taken_off",
    "M7263": f"{_T}::test_a_subnet_nsg_detached_since_is_said_with_the_vm_it_named",
    "M7264": f"{_T}::test_the_narrow_world_is_said_once_and_nothing_is_taken_off",
}
