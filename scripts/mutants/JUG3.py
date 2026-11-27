"""JUG3 (#980): judging several cards at once (Jonathan, 20/11, on a mockup). Each mutant takes a piece
back: a card's box that opens the card (M6734), a batch written without its summary (M6735), a card
judged and never acknowledged (M6736), a card acknowledged with its verdict refused (M6737), an
acknowledgement refused told done (M6738), the cards judged without waiting for each (M6739), a card
that failed let go (M6740), the note kept for the next batch (M6741), a card judged since the summary
written over (M6742), a verdict outside the three (M6743), cards of several rules not warned of
(M6744), « to judge ×1 » (M6745), the group's window without its cards once they are acknowledged
(M6746), another window written by the group's batch (M6747), the 30 s redraw dropping what is typed
(M6748), the box out of a finger's reach on a phone (M6765), the bar's note that makes Safari zoom
(M6766), the group's window never redrawn with the list (M6767); from the review: the list not read again
letting the batch through (M6780), a list refused taken as read (M6781), two batches at once
(M6782, M6784), the group's window reset under its batch (M6783), the phone's box under the line's
next rows (M6785), the outcome's lines alike (M6786), a tile's link too small for a finger (M6787).
M6734–M6748, M6765–M6767 and M6780–M6787, measured by tests/unit/test_console_judge_batch.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_judge_batch.py::"

MUTANTS = [
    ("M6734", "a card's box in TO JUDGE opens the card: the click goes on to its line (JUG3)", GF_JS,
     "<label class=\"judge-pick\" ${_on('click', 'stop')} title=\"Check it, to judge several cards at once\">",
     "<label class=\"judge-pick\" title=\"Check it, to judge several cards at once\">"),
    ("M6735", "a batch written as soon as its verdict is chosen: no summary (JUG3, decision 1)", GF_JS,
     "B.ask = { verdict, cause: cause || '', note: B.note.trim(), ids: [...B.picked] }; B.result = null; _batchRender(where); }",
     "B.ask = { verdict, cause: cause || '', note: B.note.trim(), ids: [...B.picked] }; B.result = null; _runBatch(where); }"),
    ("M6736", "a card judged in a batch never acknowledged, unlike its own button (JUG3)", GF_JS,
     "    const r = await _post(`/api/action/ack/${_seg(id)}`);\n",
     "    const r = { ok: true, json: async () => ({}) };\n"),
    ("M6737", "a card acknowledged though its verdict was refused (JUG3)", GF_JS,
     "if (!r.ok || d.error) return { state: 'fail', why: String(d.error || d.detail || `HTTP ${r.status}`) };",
     "if (false) return { state: 'fail', why: String(d.error || d.detail || `HTTP ${r.status}`) };"),
    ("M6738", "an acknowledgement refused told done: the card said acknowledged (JUG3, decision 4)", GF_JS,
     "if (!r.ok || d.error) return { state: 'unacked', why: String(d.error || d.detail || `HTTP ${r.status}`) };",
     "if (!r.ok || d.error) return { state: 'ok' };"),
    ("M6739", "the cards of a batch judged without waiting for each: every answer unread (JUG3)", GF_JS,
     "    lines.push({ id, label, note: !!note, ...(await _judgeOne(id, verdict, note, cause)) });\n",
     "    _judgeOne(id, verdict, note, cause); lines.push({ id, label, note: !!note, state: 'ok' });\n"),
    ("M6740", "a card that failed let go: nothing left checked to try again (JUG3, decision 4)", GF_JS,
     "  B.picked = new Set(lines.filter(l => l.state === 'fail').map(l => l.id));",
     "  B.picked = new Set();"),
    ("M6741", "the note of a batch kept, and sent with the next one (JUG3)", GF_JS,
     "  if (!B.picked.size) B.note = '';\n", ""),
    ("M6742", "a card judged since the summary (the bot, another tab) written over (JUG3)", GF_JS,
     "    if (!_toJudge.some(c => c.id === id)) { lines.push({ id, label, note: !!note, state: 'gone' }); continue; }\n", ""),
    ("M6743", "a verdict outside the three asked of the cards checked (JUG3)", GF_JS,
     "if (!Object.hasOwn(_batch, where) || !_VERDICTS.includes(verdict) || (cause !== undefined",
     "if (!Object.hasOwn(_batch, where) || (cause !== undefined"),
    ("M6744", "cards of several rules in one selection, not warned of (JUG3, decision 2)", GF_JS,
     "${rules.size > 1 ? `<div class=\"judge-mixed\">", "${false ? `<div class=\"judge-mixed\">"),
    ("M6745", "« to judge ×1 »: a tile's single card opens a window of one (JUG3)", GF_JS,
     "    ? (toJudgeHere.length > 1\n", "    ? (toJudgeHere.length > 0\n"),
    ("M6746", "the group's window reads only the state: its acknowledged cards turn to « ? », « no rule » (JUG3)", GF_JS,
     "  const card = id => _batchCard(id) || B.cards[id] || null;\n",
     "  const card = id => _batchCard(id);\n"),
    ("M6747", "the group's batch writes its window into another one opened since (JUG3)", GF_JS,
     "function _batchRender(where) { where === 'group' ? _judgeGroupAgain() : renderToJudge(); }",
     "function _batchRender(where) { where === 'group' ? _renderJudgeGroup() : renderToJudge(); }"),
    ("M6748", "the 30 s redraw of TO JUDGE drops a card's note and the focus: the keyboard closes (JUG3)", GF_JS,
     "  _retype(list, typed);\n  // ?card=<id>: scrolled to once", "  // ?card=<id>: scrolled to once"),
    ("M6765", "a card's box out of a finger's reach on a phone: a hit area of 20 px (JUG3, decision 3)", GF_HTML,
     "    .judge-pick { padding: 12px 16px 12px 8px; margin: -12px 0 -12px -8px; align-self: center; position: relative; z-index: 1; }\n", ""),
    ("M6766", "the batch's note under 16 px on a phone: Safari on iOS zooms on it at each tap (JUG3)", GF_HTML,
     "    .judge-bar input { flex: 1 1 100%; font-size: 16px; padding: 8px 10px; }\n",
     "    .judge-bar input { flex: 1 1 100%; font-size: 10px; padding: 8px 10px; }\n"),
    ("M6767", "the group's window never redrawn with the list: a card judged elsewhere keeps its box (JUG3)", GF_JS,
     "_toJudge = cards; renderToJudge(); _judgeGroupAgain(); Console.setJudgeCount(cards.length);",
     "_toJudge = cards; renderToJudge(); Console.setJudgeCount(cards.length);"),
    ("M6780", "the list not read again lets the batch through: a card judged elsewhere written over (JUG3, review)", GF_JS,
     "    if (!fresh) { lines.push({ id, label, note: !!note, state: 'fail', why: 'the list could not be read again' }); continue; }\n", ""),
    ("M6781", "a list refused by the server taken as read again (JUG3, review)", GF_JS,
     "    if (!r.ok) return null;\n    const q = await r.json();\n", "    const q = await r.json();\n"),
    ("M6782", "a batch asked while another runs: the same cards judged twice at once (JUG3, review)", GF_JS,
     "if (!B.picked.size) return; if (_batchRunning()) { toast('⏳ A batch is being judged: wait for its end'); return; } B.ask =",
     "if (!B.picked.size) return; B.ask ="),
    ("M6783", "the group's window reset under its batch when opened again (JUG3, review)", GF_JS,
     "  // Its batch running: the window opened again as it is (its group, its progress), never reset under it.\n  if (!B.running) {\n",
     "  // Its batch running: the window opened again as it is (its group, its progress), never reset under it.\n  if (true) {\n"),
    ("M6784", "a summary confirmed while another batch runs: two batches at once (JUG3, review)", GF_JS,
     "  if (!B.ask) return;\n  if (_batchRunning()) { toast('⏳ A batch is being judged: wait for its end'); return; }\n",
     "  if (!B.ask) return;\n"),
    ("M6785", "the phone's box under the line's next rows: the area's last rows open the card (JUG3, review)", GF_HTML,
     "align-self: center; position: relative; z-index: 1; }", "align-self: center; }"),
    ("M6786", "the outcome's lines alike for two cards of one action on one VM (JUG3, review)", GF_JS,
     "${on ? ' — ' + on : ''} · ${String(c.id || '').slice(0, 8)}`;", "${on ? ' — ' + on : ''}`;"),
    ("M6787", "a tile's « to judge ▸ » 16 px high on a phone (JUG3, review)", GF_HTML,
     "    a.judge-link { position: relative; z-index: 1; padding: 14px 10px; margin: -14px -10px -14px auto; }\n", ""),
]

TESTS = {
    "M6734": f"{_T}test_each_card_has_a_box_and_the_box_never_opens_the_card",
    "M6735": f"{_T}test_nothing_is_written_before_the_summary",
    "M6736": f"{_T}test_each_card_gets_its_verdict_then_its_acknowledgement_each_answer_read",
    "M6737": f"{_T}test_each_card_gets_its_verdict_then_its_acknowledgement_each_answer_read",
    "M6738": f"{_T}test_each_card_gets_its_verdict_then_its_acknowledgement_each_answer_read",
    "M6739": f"{_T}test_one_card_after_the_other_never_at_once",
    "M6740": f"{_T}test_a_card_that_fails_is_said_and_stays_checked_the_note_goes_with_its_batch",
    "M6741": f"{_T}test_a_card_that_fails_is_said_and_stays_checked_the_note_goes_with_its_batch",
    "M6742": f"{_T}test_a_card_judged_since_the_summary_is_left_as_it_was",
    "M6743": f"{_T}test_nothing_is_written_before_the_summary",
    "M6744": f"{_T}test_cards_of_several_rules_in_one_selection_are_warned_of",
    "M6745": f"{_T}test_a_tile_opens_its_group_from_two_cards_to_judge",
    "M6746": f"{_T}test_the_group_window_ranged_by_rule_keeps_its_cards",
    "M6747": f"{_T}test_the_group_window_is_written_only_while_it_is_the_one_open",
    "M6748": f"{_T}test_the_30_s_redraw_keeps_what_is_typed_and_where",
    "M6765": f"{_T}test_on_a_phone_a_finger_hits_the_box",
    "M6766": f"{_T}test_on_a_phone_the_bar_takes_a_finger_and_its_note_no_zoom",
    "M6767": f"{_T}test_the_group_window_is_written_only_while_it_is_the_one_open",
    "M6780": f"{_T}test_a_list_not_read_again_writes_nothing",
    "M6781": f"{_T}test_a_list_not_read_again_writes_nothing",
    "M6782": f"{_T}test_one_batch_at_a_time_for_the_page",
    "M6783": f"{_T}test_one_batch_at_a_time_for_the_page",
    "M6784": f"{_T}test_one_batch_at_a_time_for_the_page",
    "M6785": f"{_T}test_on_a_phone_a_finger_hits_the_box",
    "M6786": f"{_T}test_the_lines_of_the_outcome_are_told_apart",
    "M6787": f"{_T}test_on_a_phone_a_tile_s_link_to_judge_takes_a_finger",
}
