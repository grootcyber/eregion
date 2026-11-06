"""SEC-A2 (#631; audit of 06/11, V-03 and V-13): the watch's decision queue, bounded — its size,
the gravest first, one decision of the model per VM, rule and gravity in a window, a ceiling of
calls per minute; the older lines of a pass named on a card (glorfindel/decision_queue.py,
glorfindel/detection_rules.py). One mutant per property, M4525–M4529, measured by
tests/unit/test_decision_queue.py."""
QUEUE = "glorfindel/decision_queue.py"
RULES = "glorfindel/detection_rules.py"
_T = "tests/unit/test_decision_queue.py"

MUTANTS = [
    ("M4525", "the queue of a VM without a bound: a burst grows it, nothing leaves, nothing said (SEC-A2)",
     QUEUE,
     "            if len(self._heap) >= self._max:\n",
     "            if False:\n"),
    ("M4526", "no dedup: each detection of the same rule on the same VM calls the model (SEC-A2)",
     QUEUE,
     "                if at is not None and now - at < self.window_s:\n",
     "                if False:\n"),
    ("M4527", "first come, first served whatever the gravity: a ransomware detection waits behind a "
     "forged burst (SEC-A2)", QUEUE,
     "        self._classify = classify or (lambda item: gravity(item[0]))\n",
     "        self._classify = classify or (lambda item: LOW)\n"),
    ("M4528", "no ceiling of calls per minute: a burst on twenty VMs calls the model twenty times (SEC-A2)",
     QUEUE,
     "            if n >= limit:\n",
     "            if False:\n"),
    ("M4529", "the older lines of a pass marked sent unsaid: a decoy line after the real one hides it "
     "(SEC-A2, V-13)", RULES,
     "                    if others:\n",
     "                    if False:\n"),
]
TESTS = {
    "M4525": f"{_T}::test_the_queue_is_bounded_and_what_leaves_it_is_a_card",
    "M4526": f"{_T}::test_a_deduplicated_detection_costs_no_call_and_is_named_on_a_card "
             f"{_T}::test_a_forged_burst_never_delays_a_grave_detection",
    "M4527": f"{_T}::test_a_forged_burst_never_delays_a_grave_detection",
    "M4528": f"{_T}::test_the_ceiling_of_calls_holds_and_beyond_it_a_card_never_an_action "
             f"{_T}::test_a_burst_of_low_detections_never_uses_the_room_of_a_grave_one",
    "M4529": f"{_T}::test_a_decoy_line_after_the_real_one_never_hides_it",
}
