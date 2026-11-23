"""HRN2 (#1079): the model's probe, once a week on Imladris (infra/glorfindel-host/cd/harness_probe.py), judged
by the CD's own rule (eregion_cd.overconfident_drift), each run bounded (scripts/harness_meter.py, Budget).
M7115–M7119: a drift unsaid, the rule read backwards; a case without an overconfident draw counted as a drift;
the ceiling ignored; an unknown cost counted 0 in the ceiling; the probe writing outside its folder. M7121–M7122
(its review): two probes at once; nothing in common said « aucune dérive ».
Measured by tests/unit/test_harness_probe.py and tests/unit/test_harness_meter.py."""
PROBE = "infra/glorfindel-host/cd/harness_probe.py"
CD = "infra/glorfindel-host/cd/eregion_cd.py"
METER = "scripts/harness_meter.py"
_P = "tests/unit/test_harness_probe.py"
_M = "tests/unit/test_harness_meter.py"

MUTANTS = [
    ("M7115", "the CD's rule read backwards by the probe: the reference judged against the run — the drift of "
     "23/11 unsaid (HRN2)", PROBE,
     "    drift, moved = cd.overconfident_drift({lb: c[lb] for lb in both}, {lb: r[lb] for lb in both})\n",
     "    drift, moved = cd.overconfident_drift({lb: r[lb] for lb in both}, {lb: c[lb] for lb in both})\n"),
    ("M7116", "a case without an overconfident draw counted newly overconfident: a steady model said to drift "
     "(HRN2)", CD,
     "    new_over = [lb for lb in c if any(map(_overconfident, c[lb][1])) and not any(map(_overconfident, "
     "r[lb][1]))]\n",
     "    new_over = [lb for lb in c if not any(map(_overconfident, r[lb][1]))]\n"),
    ("M7117", "the ceiling of dollars ignored: a run that costs more never stops (HRN2)", METER,
     "            elif self.charged() >= self.max_usd:\n",
     "            elif False:\n"),
    ("M7118", "an unknown cost counted 0 in the ceiling: a run LiteLLM cannot price stops at its bound of "
     "calls only (HRN2)", METER,
     "        return self.known_usd + self.unknown * self.per_unknown\n",
     "        return self.known_usd\n"),
    ("M7119", "the probe's report written beside the watch's state, its retention over ~/.glorfindel (HRN2)",
     PROBE,
     'REPORTS = cd.HOME / ".glorfindel" / "harness-probe"\n',
     'REPORTS = cd.HOME / ".glorfindel"\n'),
    # After the review of HRN2 (M7121–M7122, handed out by the Orchestre).
    ("M7121", "two probes at once: the second erases the first one's out dir and runs again (HRN2, review)",
     PROBE,
     "            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n",
     "            pass\n"),
    ("M7122", "a run without a case in common with the attestation said « aucune dérive » (HRN2, review)", PROBE,
     "    if not both:\n",
     "    if False:\n"),
]
TESTS = {
    "M7115": f"{_P}::test_the_drift_of_23_11_is_said_with_the_cases_that_moved",
    "M7116": f"{_P}::test_a_run_like_its_reference_says_no_drift_in_one_short_line "
             f"{_P}::test_one_case_newly_overconfident_is_noise_two_are_a_drift",
    "M7117": f"{_M}::test_the_ceiling_stops_the_run_at_its_measured_cost "
             f"{_M}::test_the_harness_stops_at_its_ceiling_and_writes_no_pass",
    "M7118": f"{_M}::test_an_unknown_cost_is_a_possible_overrun_never_zero",
    "M7119": f"{_P}::test_nothing_is_written_outside_its_folder_and_no_mode_changes",
    "M7121": f"{_P}::test_two_probes_never_run_at_once",
    "M7122": f"{_P}::test_a_run_without_a_case_in_common_is_no_measure_with_the_mention",
}
