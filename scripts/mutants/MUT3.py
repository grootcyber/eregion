"""MUT3 (#599): the 17 survivors that held the 0.5.7 release gate red — there at the 0.5.6 gate too,
held since CI6e. Jonathan's decision (06/11): a FIXED-ONLY mutant is caught by the suite — its fixed
sequence of tests/unit/test_invariant_regressions.py is added to its target (TESTS_ALSO), the machine
kept; CI6e's rule unchanged for every other mutant.

- Caught by a fixed sequence: M10, M23, M24, M34, M35, M39, M40, M1961, M1963 (FIXED-ONLY), M41 (flaky).
- Caught by a unit test that already held its property: M36.
- Killed by a test of their own: M3153 (since L1O, a perimeter's `pair` reaches the narrowing only when
  its write fails again — the test the mutant named no longer went there), M3282 (`_back` has its own
  loop since L1H: `_read_both` serves `_worse` alone, whose side the test the mutant named never read),
  M1552 (the NIC was always named elsewhere — placements kept, the block's state: the kept `known_nics`
  counts once the block's state is lost too; its test's name falls in the mutant's `-k deleted_vm`) and
  M613 (the instance's lock held around every write AWS receives, the property itself).
- Rewritten in the harness: M864 called `_held_in_quarantine`, no longer imported by quarantine.py since
  SEC4b — a NameError, an isolation that failed safe, never the bug it names; with the module's own name
  (`_held_or_unreadable`), test_a_429_on_our_tag_doesnt_overwrite_a_valid_original catches it.
- M1645, taken for equivalent at first, is not (MUT3's review): a re-block clears the entry's marks
  but not the episode open in memory, and the uncovered card's mark under the same alert then reads the
  pair's next disappearance « already said ». Killed by a test of its own.
The two mutants of this lot hold M3282's and M3153's properties under another form (M4290, M4291).
"""
_RA = "glorfindel/reassert.py"
_RS = "glorfindel/reassert_said.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_RE = "tests/unit/test_reassert.py::"

MUTANTS = [
    ("M4290", "a rule left out of this check read as deleted: only the card's keys compared (MUT3, M3282's "
              "other form)", _RS,
     "    return [(before[k], after[k]) for k in sorted(before.keys() & after.keys())]\n",
     "    return [(before[k], after.get(k)) for k in sorted(before.keys())]\n"),
    ("M4291", "a perimeter whose write failed again skips its narrowing: the same rules gone again after a "
              "refused card, unsaid (MUT3, M3153's other form)", _RA,
     "    if b.get(\"drift_alerted_at\") and _missing(verification) and not never_covered:\n",
     "    if b.get(\"drift_alerted_at\") and _missing(verification) and not never_covered "
     "and not (pair or {}).get(\"error\"):\n"),
]
TESTS = {
    "M4290": f"{_RE}test_a_rule_this_check_did_not_read_is_never_read_deleted",
    "M4291": f"{_RE}test_a_perimeter_whose_write_fails_again_narrows_its_baseline_before_a_refused_card",
}
TESTS_ALSO = {
    # FIXED-ONLY: the machine alone doesn't find them, their fixed sequence does (Jonathan, 06/11).
    "M10": f"{_REG}test_a_nic_whose_subnet_cant_be_read_is_neither_covered_nor_uncovered",
    "M23": f"{_REG}test_two_hosts_an_unblock_behind_the_quarantine_finds_the_block_on_x",
    "M24": f"{_REG}test_a_reset_reads_the_original_from_the_state_and_marks_what_it_left",
    "M34": f"{_REG}test_an_old_state_names_its_rules_for_the_verification_too",
    "M35": f"{_REG}test_an_interrupted_reset_is_a_release_under_way",
    "M39": f"{_REG}test_a_reset_puts_a_bare_nics_original_back_from_the_state",
    "M40": f"{_REG}test_a_block_on_a_deleted_nsg_is_gone_not_unreadable",
    "M1961": f"{_REG}test_a_block_under_its_second_name_is_found_without_its_state",
    "M1963": f"{_REG}test_a_release_after_a_lost_state_and_a_cut_isolation_says_what_it_keeps",
    # Flaky (the machine found it one round in two): its fixed sequence is there already.
    "M41": f"{_REG}test_a_reset_sweeps_the_original_it_puts_back",
    # Flaky at the 0.5.9 release gate (MUT5: survives the machine on seed 89917386, caught on 89917387):
    # L26's sequence, and the bare NIC's that MUT5 froze beside it.
    "M21": f"{_REG}test_a_block_hidden_behind_the_quarantine_is_not_a_block "
           f"{_REG}test_a_block_on_an_nsg_taken_off_its_nic_is_not_a_block",
    # Flaky at the 0.5.9 release gate (MUT6: the machine alone catches it on seed 766752177,
    # lets it through on 766752178): Q7's sequence, frozen by MUT6.
    "M09": f"{_REG}test_a_quarantine_whose_state_and_tag_are_lost_is_not_released_bare",
    # Survived the AWS machine at the 0.5.9 release gate (MUT6: both rounds, seeds 276700698
    # and 276700699): U2's sequence on AWS, frozen by MUT6.
    "M606": "tests/unit/test_invariant_regressions_aws.py::"
            "test_a_reisolation_of_an_eni_left_on_default_keeps_its_original",
    # Flaky at the 0.5.9 release gate (MUT8: survives the machine on seed 873889299, caught on
    # 873889300): already caught by M35's frozen sequence (a reset cut off after its first write
    # on Azure, then a reassertion) and by the unit tests of a release and an unblock in progress.
    "M13": f"{_REG}test_an_interrupted_reset_is_a_release_under_way "
           f"{_RE}test_a_release_in_progress_is_not_put_back "
           f"{_RE}test_an_unblock_in_progress_is_not_put_back",
    # Flaky at the 0.5.9 release gate (MUT9: survives the machine on seed 637433568, caught on
    # 637433567): A0's own frozen sequences — an older version's fixed-name deny-all, its state
    # lost, on an NSG shared since or whose sharing can't be read — and the unit test of a release
    # without state that leaves it, said, on another VM's NSG.
    "M33": f"{_REG}test_an_old_isolation_on_an_nsg_shared_since_is_not_released "
           f"{_REG}test_an_old_isolation_is_not_released_when_its_nsg_cant_be_read "
           "tests/unit/test_glorfindel.py::test_release_isolation_without_state_sweeps_every_nic",
    # Flaky on the first night of MUT7 (MUT10, #715: survives the machine on seed 356818481, caught
    # on the two others): A0's own frozen sequence — another host putting the quarantine back during
    # the release, which only the read-back after the write tells — and the unit test of a release
    # whose write Azure didn't apply, the original not back on the NIC.
    "M14": f"{_REG}test_a_release_undone_by_another_host_is_not_reported_released "
           "tests/unit/test_glorfindel.py::test_release_checks_the_original_came_back",
    # The unit test that holds its property, outside its target.
    "M36": "tests/unit/test_glorfindel.py::test_an_old_state_file_is_moved_before_it_is_rewritten",
    # Their tests of their own.
    "M3153": f"{_RE}test_a_perimeter_whose_write_fails_again_narrows_its_baseline_before_a_refused_card",
    "M3282": f"{_RE}test_a_rule_this_check_did_not_read_is_never_read_deleted",
    # Not equivalent (MUT3's review): a re-block clears the entry's marks, not the episode open in
    # memory — the uncovered card's mark then silences the pair's next disappearance.
    "M1645": f"{_RE}test_a_reblock_then_an_uncovered_card_never_silences_the_pairs_next_disappearance",
    # The AWS machine's races never showed the instance's lock gone: its property, held directly.
    "M613": "tests/unit/test_aws_adapter.py::test_every_write_of_an_operation_holds_the_instances_lock",
}
