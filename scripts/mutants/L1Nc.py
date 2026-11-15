"""L1Nc (#795): the oracle of an acknowledged block drift, loosened and over-tightened in turn. The night
« Invariants (deep) » stayed red on L1 after the two product fixes (#796, #809): a merged block (perimeter +
the VM), its perimeter pair gone and the loss acknowledged, then one of the VM's own denies — still present on
its dedicated NSG, in force at the ack — turned into an allow. The product says that, a bypass, by its own
« contourné » card; but `_ack_holds` compared the entry's rules to the acknowledgement by their raw bytes
(`_block_rules_now != seen`) and read the ack broken, demanding a « disparu » card for a rule that had not
vanished. The fix: L1 is about rules gone — the ack holds while no rule it saw present has vanished since (a
turned-but-present rule is a bypass, judged elsewhere), and still breaks on a real new disappearance (L1N
stays strict). The oracle's own mutants: M5471/M5473/M5474 each over-tighten it back (a turn, or a rule
absent at the ack too, read « worse » again); M5472/M5475/M5476 each loosen it until a rule truly gone reads
« no worse » — complacent to L1N. Measured by the frozen sequence (test_invariant_regressions.py), which
calls the oracle both ways: a deny turned after the ack is no worse, a rule gone since breaks it."""
_TI = "tests/unit/test_invariants.py"
_FROZEN = ("tests/unit/test_invariant_regressions.py::"
           "test_a_block_deny_turned_after_an_acknowledged_perimeter_loss_is_no_worse")

_VANISH = ("        now = self._block_rules_now(vm)\n"
           "        if any(r is not None and now.get(k) is None for k, r in seen.items()):\n"
           "            return False\n")
_GUARD = ("        if any(r is not None and now.get(k) is None for k, r in seen.items()):\n")

MUTANTS = [
    ("M5471", "the acknowledged ack judged by the raw bytes again (`_block_rules_now != seen`): a deny turned "
              "into an allow, still present, reads « worse » and demands a « disparu » card for a bypass (L1Nc, "
              "the defect back)",
     _TI, _VANISH,
     "        if self._block_rules_now(vm) != seen:\n            return False\n"),
    ("M5472", "the disappearance guard dropped: a named rule the ack saw present, gone from Azure since, reads "
              "« no worse », the acknowledged card said again for nothing (L1Nc, complacent to L1N)",
     _TI, _GUARD + "            return False\n", ""),
    ("M5473", "the present-at-the-ack test dropped (`r is not None`): a rule absent at the ack too — the "
              "perimeter pair already gone — reads « gone since », the ack over-tightened (L1Nc)",
     _TI, _GUARD,
     "        if any(now.get(k) is None for k, r in seen.items()):\n"),
    ("M5474", "the disappearance read backwards (`is None` → `is not None`): a rule still present reads « gone », "
              "the ack broken on a rule that held (L1Nc)",
     _TI, _GUARD,
     "        if any(r is not None and now.get(k) is not None for k, r in seen.items()):\n"),
    ("M5475", "the disappearance required of every named rule (`any` → `all`): one rule gone among others still "
              "there reads « no worse », the acknowledged card said again for nothing (L1Nc, complacent to L1N)",
     _TI, _GUARD,
     "        if all(r is not None and now.get(k) is None for k, r in seen.items()):\n"),
    ("M5476", "a rule gone since the ack read « still said » (`return False` → `return True`): the real new "
              "disappearance counted said by the acknowledgement, never told again (L1Nc, complacent to L1N)",
     _TI, _GUARD + "            return False\n",
     _GUARD + "            return True\n"),
]
TESTS = {mid: _FROZEN for mid, *_ in MUTANTS}
