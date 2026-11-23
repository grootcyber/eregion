"""SEC-A2 (#631; audit of 06/11, V-03 and V-13): the watch's decision queue, bounded — its size,
the gravest first, one decision of the model per VM, rule, gravity and source in a window, a
ceiling of calls per minute; the older lines of a pass named on a card (glorfindel/decision_queue.py,
glorfindel/detection_rules.py). One mutant per property, M4525–M4529, measured by
tests/unit/test_decision_queue.py; M4567–M4572, the review's: a compromise never held by the ceiling
and keyed by its address, the facts of B3a kept and its pair never held, the grave class's own room,
the window opened only by a decision that contained or put a card before a human. M4567 (a compromise never
held by the ceiling) and M4568 (a compromise keyed by its address) retired by SEC-E (#846), which reverses
both — its own measure, scripts/mutants/SEC-E.py (M5729, M5732); M4570 measures the pair's exemption from
the ceiling only (SEC-E, #644 point 2). M4528 and M4571 follow the code: the ceiling's comparisons carry
the reserve of PRT1 (#1060, scripts/mutants/PRT1.py)."""
QUEUE = "glorfindel/decision_queue.py"
RULES = "glorfindel/detection_rules.py"
_T = "tests/unit/test_decision_queue.py"

MUTANTS = [
    ("M4525", "the queue of a VM without a bound: a burst grows it, nothing leaves, nothing said (SEC-A2)",
     QUEUE,
     "        if len(self._heap) >= self._max:\n",
     "        if False:\n"),
    ("M4526", "no dedup: each detection of the same rule on the same VM calls the model (SEC-A2)",
     QUEUE,
     "                if at is not None and now - at < self.window_s:\n",
     "                if False:\n"),
    ("M4527", "first come, first served whatever the gravity: a ransomware detection waits behind a "
     "forged burst (SEC-A2)", QUEUE,
     "        self._classify = classify or (lambda item: gravity(item[0]))\n",
     "        self._classify = classify or (lambda item: LOW)\n"),
    ("M4528", "no ceiling of calls per minute for the low class: a burst on twenty VMs calls the model "
     "twenty times (SEC-A2)", QUEUE,
     "                    full = low + reserve > limit or n + reserve > self.per_min\n",
     "                    full = False\n"),
    ("M4529", "the older lines of a pass marked sent unsaid: a decoy line after the real one hides it "
     "(SEC-A2, V-13)", RULES,
     "                    if others:\n",
     "                    if False:\n"),
    ("M4569", "a held detection's facts never written on its VM's incident: B3a's pair never complete "
     "(SEC-A2, review)", QUEUE,
     "        keep_facts(data, incidents)\n",
     "        pass\n"),
    ("M4570", "B3a's pair complete on the VM, its detection held by the ceiling: the floor never plays "
     "(SEC-A2, review; SEC-E)", QUEUE,
     "            if not self._floor(data, confirmed or [], now):\n",
     "            if True:\n"),
    ("M4571", "the grave class without a room of its own: the low class's draws fill the minute, a "
     "ransomware detection waits (SEC-A2, review)", QUEUE,
     "                    full = n + reserve > limit and (n - low) + reserve > self.per_min - self.low_per_min\n",
     "                    full = n + reserve > limit\n"),
    ("M4572", "the window opened by any decision: a decoy judged « nothing » hides the real line "
     "after it (SEC-A2, review)", QUEUE,
     "        opens = from_rulepoller(data) and opens_window(state)\n",
     "        opens = from_rulepoller(data)\n"),
]
TESTS = {
    "M4525": f"{_T}::test_the_queue_is_bounded_and_what_leaves_it_is_a_card",
    "M4526": f"{_T}::test_a_deduplicated_detection_costs_no_call_and_is_named_on_a_card "
             f"{_T}::test_a_forged_burst_never_delays_a_grave_detection",
    "M4527": f"{_T}::test_a_forged_burst_never_delays_a_grave_detection",
    "M4528": f"{_T}::test_the_ceiling_of_calls_holds_and_beyond_it_a_card_never_an_action "
             f"{_T}::test_a_burst_of_low_detections_never_uses_the_room_of_a_grave_one",
    "M4529": f"{_T}::test_a_decoy_line_after_the_real_one_never_hides_it",
    "M4569": f"{_T}::test_a_held_detection_keeps_its_facts_and_the_pair_is_never_held "
             f"{_T}::test_a_held_brute_force_that_succeeded_writes_its_fact",
    "M4570": f"{_T}::test_the_pair_lifts_the_ceiling_only_never_the_window",
    "M4571": f"{_T}::test_six_low_decisions_of_three_draws_never_take_the_room_of_a_grave_one",
    "M4572": f"{_T}::test_a_decoy_judged_nothing_never_hides_the_next_line",
}
