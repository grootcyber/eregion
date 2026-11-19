"""SEC-Hb (#947): I7 red on CI py3.12 — a bare NIC whose original only a quarantine NSG outside the
configured group records (our own isolation made in the VM's group before `quarantine_rg` was set, its
state lost). The refusal stands (SEC-H); the way out it says is one the operator can take: our tag on our
group's quarantine NSG when it exists, else the NSG put back on the NIC by hand, in the NIC's own group,
the NSG for the operator to name (glorfindel/providers/azure/quarantine_origin.py). M6491–M6495.
Measured by tests/unit/test_full_id_keys.py and the two sequences frozen in
tests/unit/test_invariant_regressions.py (the operator runs the command said: I7).
"""
QOR = "glorfindel/providers/azure/quarantine_origin.py"
_K = "tests/unit/test_full_id_keys.py"
_R = "tests/unit/test_invariant_regressions.py"

MUTANTS = [
    ("M6491", "the way out says our tag on an NSG that doesn't exist: the operator can't get out, I7 (SEC-Hb)",
     QOR,
     '            way = (f"poser le tag {key}=<id du NSG> sur {name} ({q_rg})" if nsg is not None else\n',
     '            way = (f"poser le tag {key}=<id du NSG> sur {name} ({q_rg})" if True else\n'),
    ("M6492", "the other group's choice written into the command: a copy and paste puts the decoy's NSG on "
              "(SEC-Hb)", QOR,
     '                   f"az network nic update -g {nic_rg} -n {nic_name} --network-security-group <id du NSG>")',
     '                   f"az network nic update -g {nic_rg} -n {nic_name} --network-security-group {value}")'),
    ("M6493", "the command names the VM's group, not the NIC's: it fails on a NIC of another group (SEC-Hb)",
     QOR,
     '            nic_rg, nic_name = _nic_rg_and_name(t0["nic_id"])\n',
     '            nic_rg, nic_name = vm_rg, _nic_rg_and_name(t0["nic_id"])[1]\n'),
    ("M6494", "our group's quarantine NSG there, our tag no longer said: the way that keeps the record (SEC-Hb)",
     QOR,
     '            way = (f"poser le tag {key}=<id du NSG> sur {name} ({q_rg})" if nsg is not None else\n',
     '            way = (f"poser le tag {key}=<id du NSG> sur {name} ({q_rg})" if False else\n'),
    ("M6495", "our group holding no quarantine NSG, another group's tag followed: the refusal relaxed, a decoy "
              "chooses (SEC-Hb)", QOR,
     "        if elsewhere:\n            where, value = elsewhere[0]\n",
     "        if elsewhere and nsg is None:\n"
     '            return elsewhere[0][1], {"nsg_rg": _parse_nsg_resource_id(elsewhere[0][0])[0],\n'
     '                                     "nsg_name": name, "nsg_id": elsewhere[0][0]}\n'
     "        if elsewhere:\n            where, value = elsewhere[0]\n"),
]

TESTS = {
    "M6491": f"{_K}::test_with_no_quarantine_nsg_in_our_group_the_conflict_says_the_nsg_put_back_by_hand "
             f"{_R}::test_a_bare_nics_quarantine_outside_the_configured_group_says_a_way_out_that_exists",
    "M6492": f"{_K}::test_with_no_quarantine_nsg_in_our_group_the_conflict_says_the_nsg_put_back_by_hand",
    "M6493": f"{_K}::test_with_no_quarantine_nsg_in_our_group_the_conflict_says_the_nsg_put_back_by_hand",
    "M6494": f"{_K}::test_the_conflict_says_our_tag_when_our_groups_quarantine_nsg_exists",
    "M6495": f"{_K}::test_with_no_quarantine_nsg_in_our_group_the_conflict_says_the_nsg_put_back_by_hand "
             f"{_R}::test_a_bare_nics_quarantine_outside_the_configured_group_says_a_way_out_that_exists",
}
