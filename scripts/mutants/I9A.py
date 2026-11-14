"""I9A (#823): the night of 14/11 read the reassertion putting back the operator's isolation as undoing a
release (« I9: the reassertion isolated …/web again mid-release »). web's release left its NIC in quarantine
(its original unknown); isolated again, nothing to write to Azure, the isolation recorded itself whole, then
crashed in its drain. The oracle's, not the product's: the machine's journal ended a release only on an
isolation that wrote to Azure; now also on one that wrote the VM's state (`chaotic_write`, A0). The product
is unchanged; these mutants hold the two sides of the corrected journal.
M5321: a release left partial (`release_failed`) no longer holds the reassertion — the journal must still
see an isolation cut off before its state as leaving the release under way (I9 binding). M5322: an
isolation recorded whole keeps the release's mark — the operator's isolation no longer put back once its
quarantine is taken off. Measured by the sequences frozen in tests/unit/test_invariant_regressions.py."""
REASSERT = "glorfindel/reassert.py"
ISOLATION = "glorfindel/providers/azure/isolation.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_CUT = f"{_REG}test_an_isolation_cut_off_before_its_state_leaves_the_release"

MUTANTS = [
    ("M5321", "a release left partial no longer holds the reassertion: a quarantine taken off is put back on "
     "the VM whose release the operator ran (I9A, I9)", REASSERT,
     '    if _held_by_an_operation(iso, "release_failed", "releasing_at"):\n',
     '    if _held_by_an_operation(iso, "partial", "releasing_at"):\n'),
    ("M5322", "an isolation recorded whole keeps the mark of the release it supersedes: the operator's "
     "isolation never put back once its quarantine is taken off (I9A)", ISOLATION,
     "            **_kept_legacy(previous, rg),\n        })\n",
     "            **_kept_legacy(previous, rg),\n"
     '            **{k: previous[k] for k in ("release_failed",) if k in (previous or {})},\n        })\n'),
]
TESTS = {"M5321": _CUT, "M5322": _CUT}
