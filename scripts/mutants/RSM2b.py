"""RSM2b (#1034): the exemptions of L1, L3 and the bypass read in the test's journal, never in the code's marks
(docs/design/reaffirmation.md §5, E3; Q3 — Jonathan, 21/11; A0). The machine notes each operation of the
connector's it sees cut off or partial, once a write of its VM's state landed (`_held_by`), until it sees one
written whole; `_iso_held` and `_block_held` read that journal alone. Each mutant puts back a way the oracle
could go wrong: M7050 has a `partial` mark of the code exempt again (an isolation's, a block's); M7051 reads
`releasing_at` in the state; M7052 never finishes the journal (a hold written whole since still held); M7053
begins a hold on a fault alone (an isolation partial on its own, the product rightly leaving it, demanded).
Measured by tests/unit/test_invariant_journal.py: the product made to lie (a mark set by a defect) or to keep
silent, and a hold it rightly keeps."""
_TI = "tests/unit/test_invariants.py"
_J = "tests/unit/test_invariant_journal.py::"
_ISO = "        return vm in self.releasing or key(vm) in self.iso_held\n"
_BLOCK = "        return vm in self.unblocking or key(vm) in self.block_held\n"
_WHOLE_ISO = f"{_J}test_a_mark_a_defect_sets_on_a_whole_isolation_exempts_nothing"
_WHOLE_BLOCK = f"{_J}test_a_mark_a_defect_sets_on_a_whole_block_exempts_nothing"

MUTANTS = [
    ("M7050", "a `partial` mark of the code exempts again: a defect that marks a whole isolation or a whole block "
              "partial silences L1, L3 and the bypass for it (RSM2b, E3, A0)",
     _TI, (_ISO, _BLOCK),
     (_ISO.replace("\n", ' or bool((self._state(vm) or {}).get("partial"))\n'),
      _BLOCK.replace("\n", ' or any(e.get("partial") for e in actions._load_block_entries(vm))\n'))),
    ("M7051", "`releasing_at` read in the state: a defect that leaves a release's intent on a whole isolation "
              "silences L1 for it — I9's journal is the test's, its exemption the code's (RSM2b, E3)",
     _TI, _ISO, _ISO.replace("\n", ' or bool((self._state(vm) or {}).get("releasing_at"))\n')),
    ("M7052", "the journal never finished: an isolation or a block written whole since an operation cut off or "
              "partial still held, L1 silent on it for ever (RSM2b, E3; the shape of L1B's seed 777)",
     _TI, "                held.discard(vm)\n", "                pass\n"),
    ("M7053", "a hold begun by a fault alone: an isolation partial on its own (no fault played), the product rightly "
              "leaving it to the operator, demanded said (RSM2b, E3; ISO1's world)",
     _TI, "            elif any(d == directory and r == vm for d, r in landed):\n",
     "            elif self.chaos.fired and any(d == directory and r == vm for d, r in landed):\n"),
]
TESTS = {
    "M7050": f"{_WHOLE_ISO}[partial] {_WHOLE_BLOCK}[partial]",
    "M7051": f"{_WHOLE_ISO}[releasing_at]",
    "M7052": f"{_J}test_a_hold_ends_once_the_test_sees_it_written_whole",
    "M7053": f"{_J}test_a_partial_isolation_on_its_own_is_held_by_the_journal",
}
