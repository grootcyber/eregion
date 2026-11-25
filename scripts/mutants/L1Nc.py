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
calls the oracle both ways: a deny turned after the ack is no worse, a rule gone since breaks it.

Re-anchored by RSM2a (#1033, 22/11): Q2 reversed L1Nc's rule — a deny turned into an allow is gone, by its
content in the test's world (`_block_hold`) — and the six keep their intent on the new `_ack_holds`: M5471
reads the raw bytes again (a deny moved to another priority, still refusing, reads « worse »); M5472 drops
the guard; M5473 drops « intact at the ack »; M5474 reads it backwards; M5475 asks it of every rule; M5476
counts a rule gone since « still said ». Measured by the frozen sequence, now three ways: turned, deleted,
moved."""
_TI = "tests/unit/test_invariants.py"
_FROZEN = ("tests/unit/test_invariant_regressions.py::"
           "test_a_block_deny_turned_after_an_acknowledged_perimeter_loss_is_said_again")

_GUARD = "        if any(state == INTACT and now.get(k) == GONE for k, state in then.items()):\n"
_WORSE = _GUARD + "            return False\n"

MUTANTS = [
    ("M5471", "the acknowledged ack judged by the raw bytes again: a deny moved to another priority, still a deny "
              "of every way, reads « worse » and demands a « disparu » card for a rule that holds (L1Nc, RSM2a)",
     _TI, _WORSE,
     "        if self._block_rules_now(vm) != getattr(self, \"acked_drift\", {}).get(vm):\n            return False\n"),
    ("M5472", "the disappearance guard dropped: a rule the ack read intact, gone since — deleted, turned — reads "
              "« no worse », the acknowledged card said again for nothing (L1Nc, complacent to L1N)",
     _TI, _WORSE, ""),
    ("M5473", "the intact-at-the-ack test dropped: a rule gone at the ack too — the perimeter pair already gone — "
              "reads « gone since », the ack over-tightened (L1Nc)",
     _TI, _GUARD,
     "        if any(now.get(k) == GONE for k, state in then.items()):\n"),
    ("M5474", "the disappearance read backwards (`== GONE` → `!= GONE`): a rule still intact reads « gone », the "
              "ack broken on a rule that held (L1Nc)",
     _TI, _GUARD,
     "        if any(state == INTACT and now.get(k) != GONE for k, state in then.items()):\n"),
    ("M5475", "the disappearance required of every rule the ack read intact (`any` → `all`): one deny turned among "
              "others still there reads « no worse », the acknowledged card said again for nothing (L1Nc, Q2)",
     _TI, _GUARD,
     "        if all(state == INTACT and now.get(k) == GONE for k, state in then.items()):\n"),
    ("M5476", "a rule gone since the ack read « still said » (`return False` → `return True`): the real new "
              "disappearance counted said by the acknowledgement, never told again (L1Nc, complacent to L1N)",
     _TI, _WORSE,
     _GUARD + "            return True\n"),
]
TESTS = {mid: _FROZEN for mid, *_ in MUTANTS}
