"""RSM2a (#1033): the hold read once, in the test's world (tests/unit/invariant_hold.py; docs/design/reaffirmation.md
§2.3, E1, E2, E5, E7). The machine's oracles now rest on one reading of what Glorfindel holds, NIC by NIC: intact,
gone, bypassed, unknown — from the fake Azure's rules, never from the code's verification (A0). L1 of a block is
judged by the content of its rules (a deny turned into an allow, Q2, or left on a former address is gone); L1 of an
isolation after every unfaulted pass (Q4); the world takes a subnet's NSG off it (E7). Each mutant puts back a way
the oracle could go wrong: M7043 reads a turned deny present (L1Nc's rule, the classification side); M7044 reads a
deny on a former address as held (the placement's recorded addresses instead of the NIC's own); M7045 cuts L1 of
an isolation out of the pass; M7046 reads the hold in the code's verification; M7047 never draws the subnet's NSG
taken off. M7048–M7049 are left free for a correction. Measured by tests/unit/test_invariant_hold.py (the oracle
both ways, the product made to lie or to keep silent) and the frozen sequence of L1Nc reversed."""
_HOLD = "tests/unit/invariant_hold.py"
_TI = "tests/unit/test_invariants.py"
_UNIT = "tests/unit/test_invariant_hold.py::"
_L1NC = ("tests/unit/test_invariant_regressions.py::"
         "test_a_block_deny_turned_after_an_acknowledged_perimeter_loss_is_said_again")

_ACCESS = ('    if rule is None or str(rule.get("access", "")).lower() != "deny":\n'
           "        return False\n")
_OWN = ('    if not refuses(_rule(m, nsg, name), direction, ATTACKER, list(nic["ips"])):\n'
        "        return GONE\n")
_ISOLATED = '        if found["inbound"] and found["outbound"]:\n'

MUTANTS = [
    ("M7043", "a deny of ours turned into an allow read present: its block not gone by its content, the "
              "acknowledgement of its disappearance read unbroken (RSM2a, Q2: L1Nc's rule back)",
     _HOLD, _ACCESS, "    if rule is None:\n        return False\n"),
    ("M7044", "a deny left on a former address read as held: the addresses the placement recorded read instead "
              "of the NIC's own now, a block open at the new one never vanished for L1 (RSM2a, L26)",
     _HOLD, _OWN,
     '    if not refuses(_rule(m, nsg, name), direction, ATTACKER, list(recorded or nic["ips"])):\n'
     "        return GONE\n"),
    ("M7045", "L1 of an isolation cut out of the pass: an isolation undone by a `terraform apply`, drawn alone, "
              "never required said (RSM2a, E5, Q4)",
     _TI, "            self._isolations_said()\n", ""),
    ("M7046", "the hold read in the code's verification: a block's rule gone only when `verify_block_ip` names "
              "it missing, an isolation gone only when `verify_isolation` says no — the oracle trusts what it "
              "judges (RSM2a, A0)",
     _HOLD,
     (_OWN, _ISOLATED),
     ('    said = m.connector.verify_block_ip(ATTACKER, next(v for v in m.live if key(nic["id"]) in '
      '{key(x) for x in m.fake.vms[key(v)]["nics"]}))\n'
      '    if name.lower() in {str(r).split(" ")[0].lower() for r in said.get("missing_rules") or []}:\n'
      "        return GONE\n",
      '        if m.connector.verify_isolation(vm).get("verified") is not False:\n')),
    ("M7047", "the subnet's NSG never taken off by the world: a perimeter pair on an NSG that governs nothing "
              "never drawn (RSM2a, E7)",
     _TI, '        k = data.draw(st.sampled_from(sorted(self.fake.subnets)), label="subnet")\n',
     '        return\n        k = data.draw(st.sampled_from(sorted(self.fake.subnets)), label="subnet")\n'),
]
TESTS = {
    "M7043": (f"{_UNIT}test_a_block_intact_then_turned_reads_gone {_UNIT}test_an_isolation_turned_is_gone_and_one_moved_holds "
              f"{_L1NC}"),
    "M7044": f"{_UNIT}test_a_block_left_on_a_former_address_reads_gone_and_is_said",
    "M7045": f"{_UNIT}test_an_isolation_gone_and_unsaid_fails_l1",
    "M7046": f"{_UNIT}test_the_hold_is_read_in_the_world_never_in_the_verification",
    "M7047": f"{_UNIT}test_a_subnet_that_lost_its_nsg_leaves_the_perimeter_gone",
}
