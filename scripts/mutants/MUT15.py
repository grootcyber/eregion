"""MUT15 (#967, the 0.6.2 release gate, run 44704078162): M01 and M605 each survived one round of two,
at 500 sequences. Neither is a defect of the code: each was left to the machine's draw. So were five
other AWS mutants (M603, M607, M609, M611, M616): each is given its case too, below.

M01 ("rule name without the NIC hash", scripts/mutation_check.py) matches its text once since SEC-H
(c4972304, #901), as M2343 did (MUT14): the new names end with 128 bits (`_nic_mark`), and its line,
`base = f"{prefix}-{vm_name}-{nic_short}-{_nic_hash(nic_id, 6)}"`, is now the one of `_older_rule_bases`,
the names 0.6.1 wrote, read never written. Mutated, the older names lose their mark: an isolation 0.6.1
placed is no longer read as one (`verify_isolation` says it is not there), and two homonyms meet on every
older name. The suite placed the older names by the code's own `_older_rule_bases`
(tests/unit/test_wide_marks.py, `_older_base`; the machine's `an_earlier_version_isolates_or_blocks`):
mutated, it wrote what it read, and nothing told. The machine met it only where a homonym's earlier
isolation and another VM's crossed. MUT13's eight frozen sequences for M01 pass under it (14 of 14
parameters): they were written for the names of their time, the line M6651 mutates now.

- test_wide_marks.py places the older names as 0.6.1 wrote them (`_v061_base`, its code copied, never
  asked of this version): 27 of its tests fail under M01, two of them its target (TESTS_ALSO).
- M6651 measures again the new names' line, which no mutant aimed at since SEC-H: homonyms share a name.
  MUT13's eight sequences catch it, each by an invariant of the machine in one parameter at least (12
  of 14 fail: 11 by I3 or I4, one by a rule's name; the 429's `reduced` two pass, its `as found` two
  fail by I4). They are its target, with the lab's sequence (V-15) of test_wide_marks.py, and leave
  M01's (scripts/mutants/MUT13.py).

M605 ("an ENI someone left on `default` is not given its original back", MC1) had the AWS machine for its
target alone (MUT13 named it among those no frozen sequence catches). No lot of the 0.6.2 touched AWS:
the chain that shows it (an isolation, the ENI moved onto `default` by someone, a release) is drawn in
some sequences only. Its case by hand, with its state and with the tag alone, in
tests/unit/test_aws_adapter.py (TESTS_ALSO); test_an_eni_left_on_default_gets_the_operator_s_group_when
_its_own_was_deleted caught it on the way, but was not in its target.

Then the other AWS mutants MUT13 left to the machine's draw (the Orchestre's word, before the review):
each gets the deterministic case of its defect, in tests/unit/test_aws_adapter.py (TESTS_ALSO); none
needed the machine or an oracle touched.
- M603 (the quarantine off by the configuration ignored), M611 (a release that failed clears its state),
  M616 (verify_isolation vouches for another account's instance): their case was written already —
  test_no_isolation_without_the_quarantine_group_nor_with_an_unreadable_config,
  test_an_unknown_original_keeps_the_eni_in_quarantine_and_says_which_tag (its state kept, said failed),
  test_another_account_another_region_or_no_arn_is_refused —, red under each, never in its target.
- M607 (an ENI already in quarantine: what it carries read as its original): isolated again, alone in
  the quarantine or with a group someone put next to ours — under M607 the release puts the quarantine
  back, or the group added, and says released.
- M609 (a verification that can't read an ENI says isolated): the quarantine group refused at its read
  — under M609 the verification says True.

Range handed by the Orchestre: M6651–M6655.
"""
NET = "glorfindel/providers/azure/network.py"
_AZ = "tests/unit/test_invariant_regressions.py"
_WM = "tests/unit/test_wide_marks.py"
_AWS = "tests/unit/test_aws_adapter.py"

# The frozen sequences MUT13 gave M01, written before SEC-H: they catch M6651 (an oracle of the machine).
_SEQUENCES = (
    "test_a_deleted_vms_rule_on_a_vm_glorfindel_isolates_waits_for_its_release",
    "test_a_merged_block_whose_pair_another_vm_wrote_again_after_its_card_is_said",
    "test_a_perimeter_block_a_429_cut_short_never_says_reached_a_nic_another_perimeter_cuts_off",
    "test_a_release_after_a_lost_state_and_a_cut_isolation_says_what_it_keeps",
    "test_a_vm_rule_back_then_gone_again_beside_a_lifted_perimeter_is_said",
    "test_an_acknowledged_drift_whose_turned_pair_another_perimeter_wrote_again_is_said",
    "test_an_interrupted_release_after_an_ip_change_opens_the_new_owner",
    "test_the_teardown_frees_the_vms_whatever_mode_the_last_rule_left",
)

MUTANTS = [
    ("M6651", "rule name without the NIC mark under the new names: homonyms share a name (MUT15, M01's "
     "line since SEC-H)", NET,
     '        base = f"{prefix}-{vm_name}-{nic_short}-{mark}"\n',
     '        base = f"{prefix}-{vm_name}-{nic_short}"\n'),
]
TESTS = {"M6651": " ".join([f"{_WM}::test_the_release_of_one_never_takes_off_the_others_deny",
                            f"{_WM}::test_an_isolation_never_writes_over_the_others_rule",
                            *(f"{_AZ}::{name}" for name in _SEQUENCES)])}
TESTS_ALSO = {
    "M01": f"{_WM}::test_the_older_names_read_are_those_the_earlier_version_wrote "
           f"{_WM}::test_an_isolation_under_the_older_names_is_verified_then_lifted",
    "M605": f"{_AWS}::test_an_eni_someone_took_onto_default_gets_its_original_back",
    "M603": f"{_AWS}::test_no_isolation_without_the_quarantine_group_nor_with_an_unreadable_config",
    "M607": f"{_AWS}::test_an_eni_isolated_again_keeps_the_original_it_had_before_the_quarantine",
    "M609": f"{_AWS}::test_a_verification_that_cannot_read_the_quarantine_group_never_says_isolated",
    "M611": f"{_AWS}::test_an_unknown_original_keeps_the_eni_in_quarantine_and_says_which_tag",
    "M616": f"{_AWS}::test_another_account_another_region_or_no_arn_is_refused",
}
