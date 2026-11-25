"""MAC1 (#1178): the night of 24/11 red on macOS only (run 45406956708, seed 397333194): « I9: the
reassertion isolated …/batch again mid-release ». The oracle's, not the product's: the order macOS lists a
directory in (APFS, by a hash of each name) gave the reassertion the lock of two homonyms in a row, and
the release of one, refused at the VM's lock after its wait, stayed « under way » in the machine's
journal — the isolation the reassertion then put back, read as undoing it. The journal now ends a lift
that wrote nothing to Azure in a race, as `_release` does alone, by the fake's journal by thread
(`_refused_lifts_started_nothing`). The product is unchanged; this mutant holds the refusal it makes.
M7576: a writer refused at the VM's lock after its wait goes on without it, beside the reassertion that
holds it — the release of batch released all the same. Measured by the sequence frozen in
tests/unit/test_invariant_regressions.py, in macOS's order (`apfs_listing_order`).
M7577 (the review's safe way): a write by a thread of neither operation no longer holds the journal —
a failed lift that may have made it leaves « under way ». The oracle's own guard, mutated in the test:
measured by the unit test of the journal (`test_a_lift_leaves_under_way_only_when_it_started_nothing`)."""
AZC = "glorfindel/providers/azure/connector.py"
_REFUSED = ("tests/unit/test_invariant_regressions.py::"
            "test_a_release_refused_at_the_lock_in_a_race_is_not_under_way")
_JOURNAL = ("tests/unit/test_invariant_regressions.py::"
            "test_a_lift_leaves_under_way_only_when_it_started_nothing")
_MACHINE = "tests/unit/test_invariants.py"

MUTANTS = [
    ("M7576", "a writer refused at the VM's lock after its wait goes on without it, beside the writer that "
     "holds it (MAC1, SEC-H)", AZC,
     '        with _vm_lock(rid.rstrip("/").rsplit("/", 1)[-1], timeout=writer_wait_s()):   # bounded (SEC-H)\n'
     "            return method(self, *args, **kwargs)\n",
     '        lock = _vm_lock(rid.rstrip("/").rsplit("/", 1)[-1], timeout=writer_wait_s())\n'
     "        try:\n"
     "            lock.__enter__()\n"
     "        except TimeoutError:\n"
     "            return method(self, *args, **kwargs)\n"
     "        try:\n"
     "            return method(self, *args, **kwargs)\n"
     "        finally:\n"
     "            lock.__exit__(None, None, None)\n"),
    ("M7577", "a write the race ties to neither operation no longer holds the journal: a failed lift that "
     "may have made it leaves « under way » (MAC1, the safe way)", _MACHINE,
     "    if wrote - {name for name, _ in ops}:\n        return\n",
     "    if False:\n        return\n"),
]
TESTS = {"M7576": _REFUSED, "M7577": _JOURNAL}
