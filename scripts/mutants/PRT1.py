"""PRT1 (#1060): the watch's ceiling holds its bound — every call a decision may make reserved at its
admission and given back when it ends, the release after a restore and the rule proposal counted
(glorfindel/decision_queue.py). M7079–M7082, measured by tests/unit/test_decision_queue.py. M4528 and
M4571 (SEC-A2) follow the code: the ceiling's comparisons now carry the reserve."""
QUEUE = "glorfindel/decision_queue.py"
_T = "tests/unit/test_decision_queue.py"

MUTANTS = [
    ("M7079", "the reserve brought back to one call: five low decisions admitted together make fifteen calls "
     "for a bound of six (PRT1)", QUEUE,
     "        return max(1, min(decision_draws() or 1, room))\n",
     "        return 1\n"),
    ("M7080", "the reserve never given back: a decision in human_only keeps three places for its one call "
     "(PRT1)", QUEUE,
     "            used = calls_made(data, state, reserve)\n",
     "            used = max(reserve, calls_made(data, state, reserve))\n"),
    ("M7081", "the release after a restore not counted: its call to the model outside the ceiling (PRT1)", QUEUE,
     '"detection_timeout", "recovery_complete", "detection_missed"',
     '"detection_timeout", "detection_missed"'),
    ("M7082", "a low decision's reserve taken on the grave ones' four places: the low class checked for one "
     "call, the total for its reserve (PRT1)", QUEUE,
     "                    full = low + reserve > limit or n + reserve > self.per_min\n",
     "                    full = low >= limit or n + reserve > self.per_min\n"),
]
TESTS = {
    "M7079": f"{_T}::test_five_low_detections_admitted_by_concurrent_threads_never_pass_six_calls "
             f"{_T}::test_a_burst_never_passes_ten_calls_and_no_grave_is_lost",
    "M7080": f"{_T}::test_a_reserve_not_used_is_given_back_for_the_next "
             f"{_T}::test_a_burst_of_low_detections_never_uses_the_room_of_a_grave_one",
    "M7081": f"{_T}::test_a_release_after_a_restore_is_counted_and_waits_never_refused",
    "M7082": f"{_T}::test_a_low_reserve_never_takes_the_places_of_the_grave_ones",
}
