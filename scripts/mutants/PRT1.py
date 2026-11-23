"""PRT1 (#1060): the watch's ceiling holds its bound — every call a decision may make reserved at its
admission and given back when it ends, the release after a restore and the rule proposal counted
(glorfindel/decision_queue.py). M7079–M7082, and from its review M7083–M7088 (the floor on a detection
only and in the total, the reserve given back when the graph raises, the look again while decisions are in
flight, the attack missed counted, the release protected in its queue), measured by
tests/unit/test_decision_queue.py; and from its second review M7089–M7090 (spent under one lock, the
attack missed in its technique's class, SEC-E V-08 kept). M4527, M4528, M4571 and M4572 (SEC-A2) follow the
code."""
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
    # The review's (M7083–M7088).
    ("M7083", "the floor on what is not a detection: a release, a rule proposal, an attack missed pass the "
     "ceiling uncounted on a VM whose pair is confirmed (PRT1, review)", QUEUE,
     '        if data.get("event") != "detection":\n            return False\n'
     "        if not _FLOOR_PAIR <= set(confirmed) | set(facts_of(data)):\n",
     "        if not _FLOOR_PAIR <= set(confirmed) | set(facts_of(data)):\n"),
    ("M7084", "the floor's calls out of the total: counted nowhere, the low class never gives way (PRT1, "
     "review)", QUEUE,
     "        n = sum(r for r, _, _ in held)\n",
     "        n = sum(r for r, _, fl in held if not fl)\n"),
    ("M7085", "the reserve given back only when the decision ends: a graph that raises leaves it in flight "
     "for good (PRT1, review)", QUEUE,
     "    state = None\n    try:\n        state = respond(data)\n    finally:\n"
     "        gate.spent(data, state, ticket)",
     "    state = respond(data)\n    if True:\n        gate.spent(data, state, ticket)"),
    ("M7086", "a grave detection held by reserves in flight looks again a minute later: their end gives "
     "their places back unseen (PRT1, review)", QUEUE,
     "IN_FLIGHT_RECHECK_S = 5.0\n",
     "IN_FLIGHT_RECHECK_S = 60.0\n"),
    ("M7087", "an attack the monitoring missed not counted: its call to the model outside the ceiling (PRT1, "
     "review)", QUEUE,
     '{"detection", "detection_timeout", ',
     '{"detection", '),
    ("M7088", "a release after a restore unprotected in its queue: put back to wait, it leaves a full queue "
     "for a card (PRT1, review)", QUEUE,
     '    return grave_technique(data) or data.get("event") == "recovery_complete"\n',
     "    return grave_technique(data)\n"),
    # The second review's (M7089, M7090).
    ("M7089", "spent's two locks again: while it reads the window, its decision counted nowhere — a third low "
     "one admitted beside two in flight (PRT1, review)", QUEUE,
     "        model = calls_model(data)\n"
     "        opens = model and from_rulepoller(data) and opens_window(state)\n"
     "        key = self._key(data) if opens else None\n"
     "        now = self._clock()\n"
     "        with self._lock:\n"
     "            held = self._reserved.pop(ticket, None) if ticket else None\n"
     "            if held is None and not model:\n"
     "                return\n",
     "        model = calls_model(data)\n"
     "        with self._lock:\n"
     "            held = self._reserved.pop(ticket, None) if ticket else None\n"
     "        if held is None and not model:\n"
     "            return\n"
     "        opens = model and from_rulepoller(data) and opens_window(state)\n"
     "        key = self._key(data) if opens else None\n"
     "        now = self._clock()\n"
     "        with self._lock:\n"),
    ("M7090", "an attack the monitoring missed in the grave class: a flood of lines of the runs/ channel takes "
     "the grave ones' room, a ransomware detection waits (PRT1, review; SEC-E, V-08)", QUEUE,
     '    if event == "recovery_complete":\n        return GRAVE\n',
     '    if event in ("recovery_complete", "detection_timeout"):\n        return GRAVE\n'),
]
TESTS = {
    "M7079": f"{_T}::test_five_low_detections_admitted_by_concurrent_threads_never_pass_six_calls "
             f"{_T}::test_a_burst_never_passes_ten_calls_and_no_grave_is_lost",
    "M7080": f"{_T}::test_a_reserve_not_used_is_given_back_for_the_next "
             f"{_T}::test_a_burst_of_low_detections_never_uses_the_room_of_a_grave_one",
    "M7081": f"{_T}::test_a_release_after_a_restore_is_counted_and_waits_never_refused",
    "M7082": f"{_T}::test_a_low_reserve_never_takes_the_places_of_the_grave_ones",
    "M7083": f"{_T}::test_the_floor_is_a_detection_s_only",
    "M7084": f"{_T}::test_the_floor_s_calls_count_the_low_class_gives_way_the_grave_ones_keep_their_room "
             f"{_T}::test_the_floor_stays_the_only_way_past_the_ceiling",
    "M7085": f"{_T}::test_respond_raising_keeps_its_reserve",
    "M7086": f"{_T}::test_a_grave_one_held_by_reserves_in_flight_looks_again_soon",
    "M7087": f"{_T}::test_an_attack_the_monitoring_missed_waits_in_its_technique_s_class_never_a_card",
    "M7088": f"{_T}::test_a_release_waiting_never_leaves_a_full_queue_for_another",
    "M7089": f"{_T}::test_spent_counts_its_decision_under_one_lock",
    "M7090": f"{_T}::test_a_flood_of_timeouts_of_the_channel_never_delays_a_grave_detection",
}
