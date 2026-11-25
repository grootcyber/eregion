"""RSM2a (#1033): the hold read once, in the test's world (tests/unit/invariant_hold.py; docs/design/reaffirmation.md
§2.3, E1, E2, E5, E7). The machine's oracles now rest on one reading of what Glorfindel holds, NIC by NIC: intact,
gone, bypassed, unknown — from the fake Azure's rules, never from the code's verification (A0). L1 of a block is
judged by the content of its rules (a deny turned into an allow, Q2, or left on a former address is gone); L1 of an
isolation after every unfaulted pass (Q4); the world takes a subnet's NSG off it (E7). Each mutant puts back a way
the oracle could go wrong: M7043 reads a turned deny present (L1Nc's rule, the classification side); M7044 reads a
deny on a former address as held (the placement's recorded addresses instead of the NIC's own); M7045 cuts L1 of
an isolation out of the pass; M7046 reads the hold in the code's verification; M7047 never draws the subnet's NSG
taken off. The review of RSM2a (22/11): M7048 and M7049 widened the excuse of #1057 (a defect the machine found,
excused alone until its fix) — retired with that excuse by RSM3 (#1036, 24/11), which fixed the defect; M7078 reads a rule its trace still names out of reach once the state was lost. RSM2a's night (24/11, seed
439290643): M7463 keeps one NSG taken off per subnet again, the one « back » puts back, and forgets the first
once a « replaced » is followed by an « off ». Measured by tests/unit/test_invariant_hold.py (the oracle
both ways, the product made to lie or to keep silent) and the frozen sequence of L1Nc reversed."""
_HOLD = "tests/unit/invariant_hold.py"
_TI = "tests/unit/test_invariants.py"
_UNIT = "tests/unit/test_invariant_hold.py::"
_REG = "tests/unit/test_invariant_regressions.py::"
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
    ("M7078", "a rule a trace still names read out of reach once the test lost the VM's state: the entry names the "
              "NSG taken off its subnet, the unblock that forgets our rules there never judged (RSM2a, I7)",
     _TI, "        loose -= traced\n",
     "        loose -= traced if key(vm) not in self.state_lost_at else set()\n"),
    ("M7463", "one NSG taken off per subnet in `_loose`, the slot « back » puts back: a « replaced » then an « off » "
              "forget the first, our rules there, out of anything's reach, fail a true release (RSM2a's night, I3)",
     _TI, '        loose = set(getattr(self, "subnet_nsgs_off", {})) - attached\n',
     '        loose = {key(g) for g in getattr(self, "subnet_nsg_was", {}).values()} - attached\n'),
]
TESTS = {
    "M7043": (f"{_UNIT}test_a_block_intact_then_turned_reads_gone {_UNIT}test_an_isolation_turned_is_gone_and_one_moved_holds "
              f"{_L1NC}"),
    "M7044": f"{_UNIT}test_a_block_left_on_a_former_address_reads_gone_and_is_said",
    "M7045": f"{_UNIT}test_an_isolation_gone_and_unsaid_fails_l1",
    "M7046": f"{_UNIT}test_the_hold_is_read_in_the_world_never_in_the_verification",
    "M7047": f"{_UNIT}test_a_subnet_that_lost_its_nsg_leaves_the_perimeter_gone",
    "M7078": f"{_UNIT}test_a_rule_its_entry_still_names_stays_in_reach",
    "M7463": _REG + "test_a_release_is_not_failed_for_our_rules_on_a_subnet_nsg_replaced_then_taken_off",
}

# RSM3's night (25/11, run 45570501748, seed 290857850, red on macOS): two defects of this oracle, fixed here.
# M7571 has the release's reach read in a block entry again (an entry names an NSG for the unblock, never for
# the release); M7575 exempts a NIC left bare, whose rules the release sweeps everywhere. M7572 lifts the
# quarantine's leniency at the acknowledgement even behind a quarantine that holds (the proposed fix, as it
# was: a worse disappearance there unsaid); M7573 never lifts it (the night's L1); M7574 forgets the forensic
# access that opens the quarantine to the attacker.
_BEHIND = "    behind = _in_quarantine(nic) and (not at_ack or _quarantine_cuts_attacker(m, nic))\n"
_NIGHT = "tests/unit/test_invariant_regressions.py::test_the_night_of_25_11_"
_ACK = f"{_UNIT}test_an_acknowledged_block_behind_a_quarantine_turned_since"
MUTANTS += [
    ("M7571", "the release's reach read in the VM's block entry: an isolation rule on an NSG taken off its subnet, "
              "the state lost, read the release's to take off because the entry names that NSG — a true "
              "« released » failed (RSM3's night, I3)",
     _TI, '        skip |= self._loose(vm, "iso")', '        skip |= self._loose(vm, "block")'),
    ("M7572", "the quarantine's leniency lifted at the acknowledgement even behind a quarantine that holds: a "
              "deny read gone there, turned since, no worse — the disappearance unsaid (RSM3's night, L1)",
     _HOLD, _BEHIND, "    behind = _in_quarantine(nic) and not at_ack\n"),
    ("M7573", "the quarantine's leniency never lifted at the acknowledgement: behind an emptied quarantine a deny "
              "the code said gone read intact, then « worse » once turned (RSM3's night, L1)",
     _HOLD, _BEHIND, "    behind = _in_quarantine(nic)\n"),
    ("M7574", "the forensic access forgotten: a quarantine whole but open to the attacker read as cutting it off, "
              "its block's rules behind it read intact at the acknowledgement (RSM3's night, L1)",
     _HOLD, "    return not any(_nsg_allows(m.fake.nsgs[g], d,",
     "    return True or not any(_nsg_allows(m.fake.nsgs[g], d,"),
    ("M7575", "a NIC left bare exempted at the release: its rules on an NSG taken off its subnet read out of reach, "
              "while the release sweeps every NSG for them (RSM3's night, I3; `_away_split`)",
     _TI, "                if key(n) in swept:\n                    continue\n", ""),
]
TESTS.update({
    "M7571": (f"{_NIGHT}a_block_entry_is_not_the_releases_trace "
              f"{_NIGHT}a_release_after_the_quarantine_is_judged_the_same"),
    "M7572": f"{_ACK} {_UNIT}test_behind_a_quarantine_the_ack_reads_the_block_as_the_code_does",
    "M7573": f"{_ACK} {_NIGHT}an_acknowledged_loss_behind_an_emptied_quarantine",
    "M7574": f"{_ACK} {_UNIT}test_behind_a_quarantine_the_ack_reads_the_block_as_the_code_does",
    "M7575": f"{_NIGHT}a_bare_nics_rules_stay_the_releases {_NIGHT}a_block_entry_is_not_the_releases_trace",
})
