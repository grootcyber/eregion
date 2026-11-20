"""JUG3 (#980): judging several cards at once (Jonathan, 20/11, on a mockup, one question at a time).

Cards checked in TO JUDGE, or in the window of a tile's group (« to judge ×N »), then one verdict
and one note for all:
  1. a summary before anything is written: the count by rule, the note;
  2. the group's window ranged by rule, « select this rule », « select all »;
  3. by the finger on a phone: a box of 20 px in a hit area of 44 × 44 px, the bar's verdicts 44 px
     high, its note in 16 px;
  4. a card that fails is said, card by card, and the others go on: it stays checked.
Each card gets exactly what its own button gives it — its verdict and the note, then its
acknowledgement —, one card after the other. Never an action, never a verdict proposed (VP1)
confirmed in the operator's place.

Found while measuring it in a headless Chromium, and held here:
  - the list redraws every 30 s: what is typed (a card's note, the batch's) and the focus stay;
  - the server takes a second verdict (as a card's own button does): the list is read again at
    the confirmation, and a card judged since the summary (the bot, another tab) is left as it was;
  - an acknowledged card leaves the state: the group's window keeps its cards from its opening;
  - the group's window is written only while it is the one open.

Measured at 1440 × 900 and at 390 × 844 with the touch (the PR says how); read here in the page's
text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]
PHONE = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]


def _fn(name: str) -> str:
    """The body of a page function, by its declaration."""
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def _action(name: str) -> str:
    """One entry of the closed ACTIONS table."""
    table = JS.split("const ACTIONS = {", 1)[1].split("\n};\n", 1)[0]
    line = next((row for row in table.splitlines() if row.strip().startswith(name + "(")), None)
    assert line, name
    return line


def test_each_card_has_a_box_and_the_box_never_opens_the_card():
    body = _fn("renderToJudge")
    # The line opens its card (JUG1): its box swallows the click, its change checks it.
    assert ("<label class=\"judge-pick\" ${_on('click', 'stop')} title=\"Check it, to judge several cards at once\">"
            "<input type=\"checkbox\" aria-label=\"Check this card\"${_batch.list.picked.has(c.id) ? ' checked' : ''} "
            "${_on('change', 'pickJudge', c.id)}></label>") in body
    assert "<label class=\"judge-all\" ${_on('click', 'stop')}><input type=\"checkbox\"" in body
    assert body.rstrip().count("_batchPanel('list')") == 2      # the bar, with cards and without
    # A checked card gone from the list (judged elsewhere, older than 7 days) is let go.
    assert "for (const id of [..._batch.list.picked]) if (!_toJudge.some(c => c.id === id)) _batch.list.picked.delete(id);" in body


def test_a_box_is_read_only_from_a_checkbox():
    for name in ("pickJudge", "pickAllJudge", "pickGroup", "pickGroupRule", "pickGroupAll"):
        assert "if (_target instanceof HTMLInputElement && _target.type === 'checkbox')" in _action(name), name


def test_nothing_is_written_before_the_summary():
    ask = _action("askBatch")
    # The verdict, one of three, asked of the cards checked: the summary drawn, nothing sent.
    assert "if (!Object.hasOwn(_batch, where) || !_VERDICTS.includes(verdict)) return;" in ask
    assert "const _VERDICTS = ['right', 'wrong', 'unsure'];" in JS
    assert "B.ask = { verdict, note: B.note.trim(), ids: [...B.picked] }; B.result = null; _batchRender(where); }" in ask
    assert "_runBatch" not in ask and "_post" not in ask
    # Only the summary's button runs it.
    panel = _fn("_batchPanel")
    assert panel.count("'runBatch'") == 1
    assert "<button class=\"action\" ${_on('click', 'runBatch', where)}>Judge ${Number(n)} ${_attr(B.ask.verdict)}</button>" in panel
    assert "runBatch(where) { if (Object.hasOwn(_batch, where)) _runBatch(where); }," in JS


def test_the_summary_counts_by_rule_and_says_the_note():
    panel = _fn("_batchPanel")
    assert "B.ask.ids.forEach(id => { const r = _batchRule(_batchCard(id)); byRule[r] = (byRule[r] || 0) + 1; });" in panel
    assert "${Object.entries(byRule).map(([r, k]) => `${Number(k)} × ${_attr(r)}`).join(' · ')}" in panel
    assert "${B.ask.note ? 'note: ' + _attr(B.ask.note) : 'no note'}" in panel


def test_cards_of_several_rules_in_one_selection_are_warned_of():
    panel = _fn("_batchPanel")
    assert "const rules = new Set([...B.picked].map(id => _batchRule(_batchCard(id))));" in panel
    assert "${rules.size > 1 ? `<div class=\"judge-mixed\">⚠ ${Number(rules.size)} rules in the selection</div>` : ''}" in panel


def test_each_card_gets_its_verdict_then_its_acknowledgement_each_answer_read():
    one = _fn("_judgeOne")
    verdict = one.index("_post(`/api/escalations/${_seg(id)}/verdict`, { verdict, note })")
    ack = one.index("_post(`/api/action/ack/${_seg(id)}`)")
    assert verdict < ack
    # A verdict refused: never acknowledged. An ack refused: said, never told done.
    assert "if (!r.ok || d.error) return { state: 'fail', why: String(d.error || d.detail || `HTTP ${r.status}`) };" in one
    assert "if (!r.ok || d.error) return { state: 'unacked', why: String(d.error || d.detail || `HTTP ${r.status}`) };" in one
    assert one.rstrip().endswith("return { state: 'ok' };")
    # Nothing else: no action, no verdict proposed confirmed in the operator's place.
    assert one.count("_post(") == 2
    batch = _fn("_runBatch") + _fn("_batchPanel")
    for never in ("/api/action/approve", "confirm-proposed", "confirmProposed", "/execute"):
        assert never not in batch, never


def test_one_card_after_the_other_never_at_once():
    run = _fn("_runBatch")
    assert "for (const [k, id] of ids.entries()) {" in run
    assert "lines.push({ id, label, note: !!note, ...(await _judgeOne(id, verdict, note)) });" in run
    assert "Promise.all" not in run


def test_a_card_that_fails_is_said_and_stays_checked_the_note_goes_with_its_batch():
    run = _fn("_runBatch")
    assert "B.picked = new Set(lines.filter(l => l.state === 'fail').map(l => l.id));" in run
    assert "if (!B.picked.size) B.note = '';" in run
    panel = _fn("_batchPanel")
    assert "judged ${_attr(v)}, not acknowledged — ${_attr(l.why)} (Ack it on its tile)" in panel
    assert "not judged — ${_attr(l.why)} (still checked)" in panel


def test_a_card_judged_since_the_summary_is_left_as_it_was():
    run = _fn("_runBatch")
    # The list read again before the first card; a card no longer in it is never written.
    assert run.index("await refreshObservation();") < run.index("for (const [k, id] of ids.entries()) {")
    assert "if (!_toJudge.some(c => c.id === id)) { lines.push({ id, label, note: !!note, state: 'gone' }); continue; }" in run
    assert "left as it was — no longer to judge (judged elsewhere since the summary?)" in _fn("_batchPanel")


def test_a_tile_opens_its_group_from_two_cards_to_judge():
    group = _fn("_renderEscGroup")
    assert "const toJudgeHere = group.filter(x => !x.verdict && _toJudge.some(c => c.id === x.id));" in group
    assert ("toJudgeHere.length > 1\n      ? `<a class=\"judge-link\" ${_on('click', 'openJudgeGroup', "
            "toJudgeHere.map(x => x.id).join(','))}") in group
    # Its window before « judged »: the card on top judged, others of the group still to judge.
    assert group.index("toJudgeHere.length > 1") < group.index("judged: ${_attr(e.verdict)}")


def test_the_group_window_ranged_by_rule_keeps_its_cards():
    opener = _fn("openJudgeGroup")
    assert "const members = String(idsCsv || '').split(',').filter(id => _escById[id]);" in opener
    assert "cards: Object.fromEntries(members.map(id => [id, _batchCard(id)])), given: {} });" in opener
    assert "document.getElementById('modal').dataset.owner = 'judge-group';" in opener
    win = _fn("_renderJudgeGroup")
    # An acknowledged card leaves the state: the window reads the cards it opened on.
    assert "const card = id => _batchCard(id) || B.cards[id] || null;" in win
    assert "B.ids.forEach(id => { const r = _batchRule(card(id)); if (!byRule.has(r)) byRule.set(r, []); byRule.get(r).push(id); });" in win
    assert "select this rule</label>" in win and "${_on('change', 'pickGroupRule', rule)}" in win
    assert "select all ${Number(judgeable.length)}</label>" in win
    assert "given ? 'judged: ' + _attr(given) : 'not in TO JUDGE'" in win
    assert "if (B.given) for (const l of lines) if (l.state === 'ok' || l.state === 'unacked') B.given[l.id] = verdict;" in _fn("_runBatch")


def test_the_group_window_is_written_only_while_it_is_the_one_open():
    assert "function _batchRender(where) { where === 'group' ? _judgeGroupAgain() : renderToJudge(); }" in JS
    again = _fn("_judgeGroupAgain")
    assert "m.classList.contains('open') && m.dataset.owner === 'judge-group'" in again
    assert "document.getElementById('modal-title').textContent === _batch.group.title) _renderJudgeGroup();" in again
    # Redrawn with the list: a card judged elsewhere loses its box.
    assert "_toJudge = q.cards; renderToJudge(); _judgeGroupAgain(); Console.setJudgeCount(q.cards.length);" in JS


def test_the_30_s_redraw_keeps_what_is_typed_and_where():
    body = _fn("renderToJudge")
    assert "const typed = list ? _typed(list) : null;" in body
    assert body.count("_retype(list, typed);") == 2
    assert "_retype(list, typed);\n  // ?card=<id>: scrolled to once" in body
    win = _fn("_renderJudgeGroup")
    assert "const typed = _typed(body);" in win and "_retype(body, typed);" in win
    typed, retype = _fn("_typed"), _fn("_retype")
    assert "querySelectorAll('input[id^=\"judge-note-\"]')" in typed       # a card's note, its text
    assert "a.type !== 'checkbox'" in typed                                 # the field the operator is in
    assert "i.focus({ preventScroll: true });" in retype
    # The batch's note keeps its text by itself (_batch.<where>.note): never an old text put back.
    assert "value=\"${_attr(B.note)}\" ${_on('input', 'batchNote', where)}" in _fn("_batchPanel")


def test_on_a_phone_a_finger_hits_the_box():
    assert "    .judge-pick { padding: 12px 16px 12px 8px; margin: -12px 0 -12px -8px; align-self: center; }" in PHONE
    assert "    .judge-pick input, .judge-all input, .judge-rule input { width: 20px; height: 20px; }" in PHONE
    assert "    .judge-all { font-size: 12px; min-height: 44px; }" in PHONE
    assert "    .judge-rule label { min-height: 44px; font-size: 12px; }" in PHONE


def test_on_a_phone_the_bar_takes_a_finger_and_its_note_no_zoom():
    assert "    .judge-bar input { flex: 1 1 100%; font-size: 16px; padding: 8px 10px; }" in PHONE
    assert "    .judge-bar button, .judge-confirm-row button { flex: 1 1 0; min-height: 44px; font-size: 13px; }" in PHONE


def test_the_bar_stays_at_the_foot_of_the_list():
    base = STYLE.split("  @media (max-width: 759px) {\n", 1)[0]
    assert "  .judge-bar, .judge-confirm, .judge-batch-result { position: sticky; bottom: 0" in base
