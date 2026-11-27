"""I7b (#1265): the teardown's operator does what the card asks after a release too. Seed 1048 at 60
found on `main` 71cfa7aa a release of the teardown that rightly kept a deny of web of rg-app2 behind
one of our rules turned into an allow — the turned rule named, its putting back asked —, with nobody
to do it: the operator put the turned rules back before the releases only, while the NIC the turned
rule now opens (web of rg-app1, given its old address) sat in the quarantine, out of that NSG; an
earlier release of the teardown brought it back under it. The oracle, not the product: after each
release that keeps something, the operator puts back the turned rules the oracle finds behind the
VM's denies (the test's journal: `tampered`, `deleted`, the naming convention — A0), each said, and
the release runs again. Each mutant puts back a way the teardown could go wrong: M8135 never puts
them back after a release (as on `main`); M8136 does it for a deleted VM's release only; M8137 reads
only a deleted VM's denies (the orphans, I5Q's), never a live one's aimed at another NIC's address.
Measured by the frozen sequence of the seed (tests/unit/test_invariant_regressions.py), web of
rg-app2 live as Hypothesis reduced it, and deleted as in the unreduced run."""
_TI = "tests/unit/test_invariants.py"
_SEQ = ("tests/unit/test_invariant_regressions.py::"
        "test_the_sequence_of_seed_1048_a_turned_rule_brought_back_over_a_nic_by_an_earlier_release")
_STEP = "            out = self._turned_behind_put_back(vm, out)     # what an earlier release brought back (I7b)\n"
_CUTTING = ("            cutting = self._cutting_orphans() | self._cutting_others()   "
            "# a deleted VM's denies, a live one's\n")

MUTANTS = [
    ("M8135", "the teardown's operator puts the turned rules back before the releases only: a NIC an earlier "
              "release brings back under one, the next release keeps its deny, said, for ever — I7 (I7b, #1265)",
     _TI, _STEP, "            pass\n"),
    ("M8136", "the turned rules put back after a deleted VM's release only: a live VM's deny kept behind its "
              "own turned rule, said, never freed — the teardown that puts back the deleted VMs' alone (I7b)",
     _TI, _STEP, _STEP.replace("(vm, out)", "(vm, out) if vm in self.deleted else out")),
    ("M8137", "after a release, only a deleted VM's denies read (the orphans): a live VM's, aimed at the address "
              "another NIC took, holds its turned rule back unseen, never put back (I7b)",
     _TI, _CUTTING, _CUTTING.replace(" | self._cutting_others()", "")),
]
TESTS = {
    "M8135": f"{_SEQ}[live] {_SEQ}[deleted]",
    "M8136": f"{_SEQ}[live]",
    "M8137": f"{_SEQ}[live]",
}
