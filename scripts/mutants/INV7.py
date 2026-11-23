"""INV7 (#1099): I7 red at the 0.6.5 release gate (seed 132150572), an oracle's: a NIC left bare whose
original nothing records, its NSG deleted by the customer, was left by the operator's first step to a tag
written on every quarantine NSG of ours — one of a group the configuration no longer names among them, which
the release never follows (SEC-H). The operator now puts that NSG back as designed, then on the NIC. What the
release still owes in that world — the configured group changed, our quarantine NSG left in the former one —
stays measured: the NIC it still carries is brought back by our tag on THAT NSG, wherever the configuration
points now (glorfindel/providers/azure/release.py). M7157–M7158.
Measured by the sequence frozen in tests/unit/test_invariant_regressions.py, and by the machine: M7157 at 60
sequences, M7158 by the frozen sequence alone (the machine at 60 doesn't draw it, 23/11).
"""
REL = "glorfindel/providers/azure/release.py"
_R = "tests/unit/test_invariant_regressions.py"
_I = "tests/unit/test_invariants.py"

MUTANTS = [
    ("M7157", "the original of a NIC in quarantine read on the configured group's NSG, not on the one it "
              "carries: our quarantine left in a former group, the NIC stays in it for ever (INV7)", REL,
     '                        original = self._original_from_tags(q, t0["nic_id"])\n',
     '                        original = self._original_from_tags(\n'
     '                            {**q, "nsg_rg": self._quarantine_settings()[1] or rg}, t0["nic_id"])\n'),
    ("M7158", "SEC-H's refusal stretched to the quarantine NSG a NIC carries: outside the configured group, "
              "never left — the NIC kept in quarantine though our own tag on it says its original (INV7)", REL,
     '                    original = _recorded_original(t0["nic_id"])\n'
     '                    if original is _UNKNOWN:\n',
     '                    if q["nsg_rg"].lower() != (self._quarantine_settings()[1] or rg).lower():\n'
     '                        raise OriginalUnknown("quarantaine hors du groupe configuré : jamais suivie")\n'
     '                    original = _recorded_original(t0["nic_id"])\n'
     '                    if original is _UNKNOWN:\n'),
]

TESTS = {
    "M7157": f"{_R}::test_a_bare_nic_whose_nsg_was_deleted_gets_it_back_though_our_quarantine_group_changed {_I}",
    "M7158": f"{_R}::test_a_bare_nic_whose_nsg_was_deleted_gets_it_back_though_our_quarantine_group_changed {_I}",
}
