"""VRD1 (#1285): a finer verdict — a « wrong » says why, a false alarm or an action too strong (decision of
Jonathan of 24/11). Each mutant takes a piece back: the cause lost at the writing (M8286), a card judged
again keeping its former cause (M8287), « too strong » taken without a gesture (M8288), a verdict of before
unreadable (M8289), the report that confuses the two causes (M8290), the bot that writes another cause than
the one clicked (M8291), a message of before VRD1 whose ✗ Wrong answers « interaction failed » after a
restart (M8292), the cause shown to the model with MEM2's switch off (M8293), the page that offers « too
strong » without a gesture (M8294), the page that sends no cause (M8295). M8286–M8295, measured by
tests/unit/test_verdict_cause.py and tests/unit/test_verdict_cause_console.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
ESC = "glorfindel/escalations.py"
CAUSE = "glorfindel/verdict_cause.py"
BOT = "glorfindel/bot.py"
BOT_VERDICT = "glorfindel/bot_verdict.py"
MEMORY = "glorfindel/memory.py"
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_verdict_cause.py::"
_C = "tests/unit/test_verdict_cause_console.py::"
_KEYS = '__import__("glorfindel.memory_keys", fromlist=["_"])'

MUTANTS = [
    ("M8286", "the cause lost at the writing: « too strong » said, a bare wrong kept (VRD1)", ESC,
     "    if why:\n        e[verdict_cause.FIELD] = why\n",
     "    if False:\n        e[verdict_cause.FIELD] = why\n"),
    ("M8287", "a card judged again keeps the cause of its former verdict (VRD1)", ESC,
     "        e.pop(verdict_cause.FIELD, None)\n",
     "        pass\n"),
    ("M8288", "« too strong » taken on a card that made no gesture (VRD1)", CAUSE,
     "    if cause == TOO_STRONG and not gesture(action):\n",
     "    if False:\n"),
    ("M8289", "a verdict of before unreadable: a wrong without the field makes the report fall (VRD1)", CAUSE,
     "    cause = e.get(FIELD)\n",
     "    cause = e[FIELD]\n"),
    ("M8290", "the report confuses the two causes: every cause counted a false alarm (VRD1)", CAUSE,
     "        into[of(e) or UNSAID] += 1\n",
     "        into[FALSE_ALARM if of(e) else UNSAID] += 1\n"),
    ("M8291", "the bot writes another cause than the one clicked (VRD1)", BOT_VERDICT,
     'esc_module.set_verdict(self.esc["id"], self.verdict, "", cause=self.cause or None)',
     'esc_module.set_verdict(self.esc["id"], self.verdict, "", cause=(self.cause and verdict_cause.FALSE_ALARM) or None)'),
    ("M8292", "a message of before VRD1 given back without its ✗ Wrong: « interaction failed » (VRD1)", BOT,
     "self.add_view(EscalationView(waiting[esc_id], legacy=True), message_id=message_id)",
     "self.add_view(EscalationView(waiting[esc_id]), message_id=message_id)"),
    ("M8293", "the cause shown to the model with MEM2's switch off: the distance says the cards' verdicts (VRD1)",
     MEMORY,
     '                cycles.append((rank((distance, doc, meta)), {"summary": doc, **meta}))\n',
     f'                cycles.append((rank((distance, doc, meta)), {{"summary": doc + " | " + {_KEYS}.verdict_said('
     f'{_KEYS}.card_verdicts().get(meta.get("signal_id")), meta.get("action")), **meta}}))\n'),
    ("M8294", "the page offers « too strong » on a card that made no gesture (VRD1)", GF_JS,
     "    + (c.gesture ? `<button",
     "    + (true ? `<button"),
    ("M8295", "the page sends no cause: « too strong » clicked, a bare wrong written (VRD1)", GF_JS,
     "_post(`/api/escalations/${_seg(escId)}/verdict`, { verdict, note, cause: cause || '' });",
     "_post(`/api/escalations/${_seg(escId)}/verdict`, { verdict, note, cause: '' });"),
]
TESTS = {
    "M8286": f"{_T}test_a_cause_is_written_beside_the_verdict_and_read_back",
    "M8287": f"{_T}test_a_card_judged_again_never_keeps_the_cause_of_its_former_verdict",
    "M8288": f"{_T}test_too_strong_is_refused_on_a_card_that_made_no_gesture",
    "M8289": f"{_T}test_a_wrong_of_before_or_written_by_hand_reads_as_a_wrong_whose_cause_is_unsaid",
    "M8290": f"{_T}test_the_report_counts_the_false_alarms_and_the_actions_too_strong_apart",
    "M8291": f"{_T}test_the_bot_writes_the_cause_clicked_never_another",
    "M8292": f"{_T}test_a_message_of_before_vrd1_keeps_its_wrong_once_the_bot_restarted",
    "M8293": f"{_T}test_off_the_model_sees_origin_mains_message_to_the_byte_whatever_the_causes",
    "M8294": f"{_C}test_too_strong_is_offered_only_on_a_card_that_made_a_gesture",
    "M8295": f"{_C}test_every_place_a_card_is_judged_gives_the_same_buttons_and_sends_the_cause",
}
