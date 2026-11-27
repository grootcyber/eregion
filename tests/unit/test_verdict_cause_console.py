"""VRD1 (#1285): the console's verdict says why a « wrong » — a false alarm (nothing happened), or an action too
strong (the signal was real, the gesture too strong), offered only on a card that made a gesture.

The same buttons wherever a card is judged — TO JUDGE, its window, the bubble of the 360° — (`_verdictBtns`),
each calling its place's own action with the card's id, the verdict and the cause; the batch of JUG3 too, « too
strong » there only when every card checked made a gesture. A verdict once given is said with its cause
(`_verdictSaid`): « wrong · false alarm »; a « wrong » of before VRD1 reads « wrong », as it did. In English
(ENG1a). The page's own functions run as they are (tests/unit/js_engine.py); the rest read in the page's text,
as tests/unit/test_console_judge_batch.py does. The server's side: tests/unit/test_verdict_cause.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
OVERVIEW = (STATIC / "overview.js").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def _action(name: str) -> str:
    table = JS.split("const ACTIONS = {", 1)[1].split("\n};\n", 1)[0]
    line = next((row for row in table.splitlines() if row.strip().startswith(name + "(")), None)
    assert line, name
    return line


_RUN = r"""
FNS
const buttons = html => [...html.matchAll(/<button[^>]*data-on-click="(\w+)" data-click-args="([^"]*)"[^>]*>([^<]*)<\/button>/g)]
  .map(m => [m[1], JSON.parse(m[2].replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&')), m[3]]);
emit(JSON.stringify({
  gesture: buttons(_verdictBtns({ id: 'g1', gesture: true }, 'judgeCard')),
  none: buttons(_verdictBtns({ id: 'n1', gesture: false }, 'judgeFromBubble')),
  before: buttons(_verdictBtns({ id: 'o1' }, 'judgeFromModal')),
  said: [_verdictSaid({ verdict: 'wrong', verdict_cause: 'false_alarm' }), _verdictSaid({ verdict: 'wrong', verdict_cause: 'too_strong' }),
         _verdictSaid({ verdict: 'wrong' }), _verdictSaid({ verdict: 'wrong', verdict_cause: '__proto__' }),
         _verdictSaid({ verdict: 'right', verdict_cause: 'too_strong' }), _verdictSaid({ verdict: 'unsure' }), _verdictSaid({})],
}));
"""


def _run() -> dict:
    fns = js_engine.take(JS, "_attr", "_on", "_verdictBtns", "_CAUSE_SAID", "_verdictSaid")
    return json.loads(js_engine.run(_RUN.replace("FNS", fns)))


def test_too_strong_is_offered_only_on_a_card_that_made_a_gesture():
    """M8294: « too strong » offered on a card that made no gesture — the store refuses it, the operator told
    an error for a choice the page gave."""
    got = _run()
    assert got["gesture"] == [["judgeCard", ["g1", "right"], "✓ Right"],
                              ["judgeCard", ["g1", "wrong", "false_alarm"], "✗ False alarm"],
                              ["judgeCard", ["g1", "wrong", "too_strong"], "✗ Too strong"],
                              ["judgeCard", ["g1", "unsure"], "? Unsure"]]
    # On a detection without an action, a wrong is a false alarm: the one « wrong » offered.
    assert got["none"] == [["judgeFromBubble", ["n1", "right"], "✓ Right"],
                           ["judgeFromBubble", ["n1", "wrong", "false_alarm"], "✗ False alarm"],
                           ["judgeFromBubble", ["n1", "unsure"], "? Unsure"]]
    assert [b[1] for b in got["before"]] == [["o1", "right"], ["o1", "wrong", "false_alarm"], ["o1", "unsure"]]


def test_a_verdict_is_said_with_its_cause_and_one_of_before_as_it_was():
    assert _run()["said"] == ["wrong · false alarm", "wrong · too strong", "wrong", "wrong", "right", "unsure", ""]


def test_every_place_a_card_is_judged_gives_the_same_buttons_and_sends_the_cause():
    """M8295: the page that sends no cause — the operator clicked « too strong », the store wrote a bare wrong."""
    assert "${_verdictBtns(c, 'judgeCard')}" in _fn("renderToJudge")
    assert "${_verdictBtns(listed, 'judgeFromModal')}" in _fn("openJudgeCard")
    assert "${_verdictBtns(c, 'judgeFromBubble')}" in JS
    assert "'✗ Wrong'" not in JS and ">✗ Wrong<" not in JS           # no « wrong » without its cause any more
    judge = _fn("judgeCard")
    assert judge.startswith("\nasync function judgeCard(escId, verdict, cause, noteId) {")
    assert "_post(`/api/escalations/${_seg(escId)}/verdict`, { verdict, note, cause: cause || '' })" in judge
    assert "judgeFromModal(id, verdict, cause) { judgeCard(id, verdict, cause, 'judge-modal-note'); closeModal(); }," in JS
    assert "judgeFromBubble(id, verdict, cause) { judgeCard(id, verdict, cause, 'sky-judge-note-' + id); }," in JS
    # The batch: each card as its own button — its verdict, its cause.
    assert "_post(`/api/escalations/${_seg(id)}/verdict`, { verdict, note, cause: cause || '' })" in _fn("_judgeOne")
    assert "const { verdict, note, ids, cause } = B.ask;" in _fn("_runBatch")


def test_the_batch_offers_too_strong_only_when_every_card_checked_made_a_gesture():
    panel = _fn("_batchPanel")
    assert "${_on('click', 'askBatch', where, 'wrong', 'false_alarm')}>✗ False alarm</button>" in panel
    assert ("${[...B.picked].every(id => (_batchCard(id) || {}).gesture) ? `<button class=\"action\" "
            "style=\"color:var(--red)\" title=\"Wrong: the signal was real, the action too strong, for each\" "
            "${_on('click', 'askBatch', where, 'wrong', 'too_strong')}>✗ Too strong</button>` : ''}") in panel
    assert "(cause !== undefined && !_CAUSES.includes(cause))) return;" in _action("askBatch")
    # The summary and the outcome say the cause: « Judge 3 cards wrong · too strong? ».
    assert "_verdictSaid({ verdict: B.ask.verdict, verdict_cause: B.ask.cause })" in panel
    assert "_verdictSaid({ verdict: B.result.verdict, verdict_cause: B.result.cause })" in panel


def test_the_indicator_says_both_causes_count():
    assert "${Number(w30.false_alarm) || 0} false alarm · ${Number(w30.too_strong) || 0} too strong" in OVERVIEW
    assert "Both causes count: a false alarm (nothing happened) and an action too strong" in OVERVIEW
