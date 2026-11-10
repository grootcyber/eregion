"""AWS1b (#708): the oracle of I3 on AWS, not the adapter. An ENI someone left on `default`, whose
original nothing holds any more (the state never written, the quarantine group's tags lost), is
isolated again from `default` and released there: the analog of a NIC left bare. The oracle read
« a state held its original » from the `default` that re-isolation noted — a false alarm, seen on
the night of 10/11 (seed 894570835, 10 000 examples). No defect in the adapter, so no mutant of
it: two of the oracle, as AWS1 did (M1950, M1951), measured by the two frozen sequences
(tests/unit/test_invariant_regressions_aws.py)."""
AWS_INVARIANTS = "tests/unit/test_invariants_aws.py"
_REG = "tests/unit/test_invariant_regressions_aws.py::"
_HOLDS = ("        return bool(groups) and not (eni is not None and eni[\"id\"] in self.detached\n"
          "                                     and sorted(groups) == [f\"sg-default-{eni['vpc']}\"])\n")

MUTANTS = [
    ("M4751", "the I3 oracle on AWS reads any original a state holds as the ENI's: the `default` a "
              "re-isolation noted, its original lost, says « traceable » (AWS1b, the defect back)",
     AWS_INVARIANTS, _HOLDS, "        return bool(groups)\n"),
    ("M4752", "the I3 oracle on AWS reads any original that names `default` as nothing: a state that "
              "held the ENI's real original no longer makes it traceable (AWS1b, the fix that weakens)",
     AWS_INVARIANTS, _HOLDS,
     "        return bool(groups) and not (eni is not None and f\"sg-default-{eni['vpc']}\" in groups)\n"),
]
TESTS = {
    "M4751": f"{_REG}test_an_eni_left_on_default_whose_original_nothing_holds_is_released_on_default",
    "M4752": f"{_REG}test_the_oracle_still_holds_an_original_a_state_had",
}
# The counterpart catches M606 too (re-isolating an ENI left on `default` notes `default`): its
# tags lost, the state's real original kept by the re-isolation is what the release puts back.
TESTS_ALSO = {"M606": f"{_REG}test_the_oracle_still_holds_an_original_a_state_had"}
