"""AWS1b (#708): the oracle of I3 on AWS, not the adapter. An ENI someone left on `default`, whose
original nothing holds any more (the state never written, the quarantine group's tags lost), is
isolated again from `default` and released there: the analog of a NIC left bare. The oracle read
« a state held its original » from the `default` that re-isolation noted — a false alarm, seen on
the night of 10/11 (seed 894570835, 10 000 examples). It no longer counts that `default` — only
when the tags were already lost as the state was seen (the review, round 1: excused whatever that
moment, M606 by the tag went through). No defect in the adapter, so no mutant of it: three of the
oracle, as AWS1 did (M1950, M1951), measured by the frozen sequences
(tests/unit/test_invariant_regressions_aws.py)."""
AWS_INVARIANTS = "tests/unit/test_invariants_aws.py"
_REG = "tests/unit/test_invariant_regressions_aws.py::"
_HOLDS = ("        if not groups:\n"
          "            return False\n"
          "        if eni is None or eni[\"id\"] not in self.detached or sorted(groups) != [f\"sg-default-{eni['vpc']}\"]:\n"
          "            return True\n"
          "        rec = self.recorded_at.get(eni[\"id\"])\n"
          "        return rec is None or self.tags_lost_at.get(rec[1], -1) <= rec[0]\n")

MUTANTS = [
    ("M4751", "the I3 oracle on AWS reads any original a state holds as the ENI's: the `default` a "
              "re-isolation noted, its original lost, says « traceable » (AWS1b, the defect back)",
     AWS_INVARIANTS, _HOLDS, "        return bool(groups)\n"),
    ("M4752", "the I3 oracle on AWS reads any original that names `default` as nothing: a state that "
              "held the ENI's real original no longer makes it traceable (AWS1b, a fix that weakens)",
     AWS_INVARIANTS, _HOLDS,
     "        return bool(groups) and not (eni is not None and f\"sg-default-{eni['vpc']}\" in groups)\n"),
    ("M4753", "the I3 oracle on AWS excuses `default` alone on a detached ENI whenever its tags were "
              "lost: noted over a tag that still held the original (M606 by the tag), then the tags "
              "lost, the release on `default` goes through (AWS1b, the review's finding)",
     AWS_INVARIANTS, _HOLDS,
     "        return bool(groups) and not (eni is not None and eni[\"id\"] in self.detached\n"
     "                                     and sorted(groups) == [f\"sg-default-{eni['vpc']}\"])\n"),
]
TESTS = {
    "M4751": f"{_REG}test_an_eni_left_on_default_whose_original_nothing_holds_is_released_on_default",
    "M4752": f"{_REG}test_the_oracle_still_holds_an_original_a_state_had",
    "M4753": f"{_REG}test_the_oracle_sees_default_noted_over_a_tag_that_held_the_original",
}
# M606 (re-isolating an ENI left on `default` notes `default`) is caught by both counterparts:
# by the state (its tags lost, the state's real original), and by the tag (the tags lost after).
TESTS_ALSO = {"M606": f"{_REG}test_the_oracle_still_holds_an_original_a_state_had "
                      f"{_REG}test_a_reisolation_over_a_tag_that_holds_the_original_keeps_it"}
