"""B4a (#991, part of #75): the observation report by confidence band and by rule × band, each cell
with its count and too few said; the share judged right above the gate's threshold; where the cards
come from. M6815–M6819, M6855, measured by tests/unit/test_observation.py."""
CAL = "glorfindel/calibration.py"
_T = "tests/unit/test_observation.py::"

MUTANTS = [
    ("M6815", "each band shifted: its bottom left out, its top taken — 0.7 counted under 0.7 (B4a)", CAL,
     "        if bottom <= confidence < top:\n",
     "        if bottom < confidence <= top:\n"),
    ("M6816", "the configured threshold ignored: the report counts above 0.7 whatever the gate uses (B4a)", CAL,
     "    return confidence_threshold()\n",
     "    return 0.7\n"),
    ("M6817", "a share said on any count: three cards judged right read 100 %, never « too few » (B4a)", CAL,
     "    too_few = judged < FEW_JUDGED\n",
     "    too_few = judged == 0\n"),
    ("M6818", "a card attributed to no VM counted where its anchor VM is: the bench's (B4a)", CAL,
     '    if unattributed(e) is not None:\n        return UNKNOWN\n',
     ""),
    ("M6855", "only the SLF1 shape of a card attributed to no VM is unknown: the older unattributed_signal counted at the bench (B4a, review)", CAL,
     '    if unattributed(e) is not None:\n',
     '    if isinstance(e.get("attribution"), dict) and e["attribution"].get("state") == "unattributed":\n'),
    ("M6819", "the band read from the first decision, not the confidence the card showed when judged (B4a)", CAL,
     '    c = e.get("confidence")\n',
     '    c = e.get("first_confidence", e.get("confidence"))\n'),
]
TESTS = {
    "M6815": _T + "test_each_band_holds_its_bottom_never_its_top_and_the_last_holds_one",
    "M6816": _T + "test_above_the_threshold_counts_what_the_gate_would_let_through_at_its_configured_value",
    "M6817": (_T + "test_a_share_is_said_on_ten_judged_cards_never_under "
              + _T + "test_the_cli_says_each_band_with_its_count_and_too_few_never_a_percentage"),
    "M6818": _T + "test_provenance_the_bench_is_its_perimeter_read_from_the_card_alone",
    "M6819": _T + "test_the_band_is_the_confidence_the_card_showed_when_judged_never_its_first",
    "M6855": _T + "test_provenance_a_card_held_by_the_attribution_guard_before_slf1_is_unknown",
}
