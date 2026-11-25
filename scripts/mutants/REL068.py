"""REL068 (the 0.6.8 release gate, 25/11, run 45684580730, 2 000 sequences): an I7 of the oracle of RSM2a, fixed in
`_loose` (tests/unit/test_invariants.py). An NSG taken off a subnet is out of the lift's reach for a VM when it
governs none of that VM's NICs — never only when it governs nothing at all: the unblock and the release read the
NSGs that govern the VM's NICs, never one because it governs another VM. A NIC of the VM with no NSG at all keeps
the stricter judgement: the unblock may look for its rules on every NSG (`_unplaced_blocks`). Each mutant puts back
a way the oracle could go wrong: M7712 asks the NSG to govern nothing anywhere again (the gate's I7: web's rules on
an NSG given to api, cut by a crash before their entry, judged left by the unblock); M7713 drops the stricter
judgement of a bare NIC (its rules on another VM's NSG read out of reach, while the unblock sweeps every NSG for
them). Measured by the two frozen sequences of tests/unit/test_invariant_regressions.py."""
_TI = "tests/unit/test_invariants.py"
_GATE = "tests/unit/test_invariant_regressions.py::test_the_068_gate_"

MUTANTS = [
    ("M7712", "an NSG taken off a subnet out of reach only when it governs nothing at all: web's rules on an NSG "
              "given to another VM, cut by a crash before their entry, judged left by the unblock (the 0.6.8 "
              "gate, I7)",
     _TI, '        loose = set(getattr(self, "subnet_nsgs_off", {})) - governs_it\n',
     '        loose = set(getattr(self, "subnet_nsgs_off", {})) - attached\n'),
    ("M7713", "a bare NIC's rules on another VM's NSG read out of the unblock's reach, while it sweeps every NSG for "
              "them (`_unplaced_blocks`): an unblock that forgets that sweep never judged (the 0.6.8 gate, I7)",
     _TI, "                if g in attached and key(n) in self.fake.nics and self.fake.nics[key(n)][\"nsg\"] is None:\n"
          "                    continue                        # a bare NIC's: loose only if it governs nothing "
          "(REL068)\n", ""),
]
TESTS = {
    "M7712": f"{_GATE}a_crashed_blocks_rules_on_an_nsg_given_to_another_vm_are_out_of_reach",
    "M7713": f"{_GATE}a_bare_nics_rules_on_an_nsg_given_to_another_vm_stay_the_unblocks",
}
