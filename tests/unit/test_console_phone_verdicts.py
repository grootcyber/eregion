"""MOB5 (#975): verdicts a finger can hit on a phone, and the verdict proposed never cut off.

Jonathan asked for bigger verdict buttons (20/11): they were 54 × 16 px on a phone (the review of
MOB4). Under 760 px, in the list TO JUDGE and the card of JUG1 (`.judge-actions`), the three buttons
44 px high on one row, the note on its own line above them in 16 px (under 16 px, Safari on iOS
zooms on the field at each tap); Confirm and Refuse of a verdict proposed (VP1) 44 px high too.

Found while measuring them, a defect at every width: Confirm and Refuse sat inside the line of the
proposal, cut at two lines by its inline style; a proposal of an ordinary length put them below the
cut — hidden in the list TO JUDGE, at 1440 px too (measured: 2 of 2). They now sit under the line,
in a container of their own (`.judge-proposed`). The one change of MOB5 above 760 px.

Measured in a headless Chromium at 390 × 844 and 1440 × 900 (the PR says how); read here in the
page's text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]
PHONE = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]


def test_on_a_phone_the_verdicts_are_44_px_high_the_note_16_px():
    assert "    .judge-actions { flex-wrap: wrap; gap: 8px; }" in PHONE
    assert "    .judge-actions input { flex: 1 1 100%; font-size: 16px; padding: 8px 10px; }" in PHONE
    assert "    .judge-actions button { flex: 1 1 0; min-height: 44px; font-size: 13px; padding: 6px 4px; }" in PHONE
    assert "    .judge-proposed button { flex: 1 1 0; min-height: 44px; font-size: 13px; padding: 6px 10px; }" in PHONE


def test_the_list_and_the_card_of_jug1_share_the_verdicts_row():
    # One class for both: the rule above holds for each.
    assert JS.count('<div class="judge-actions" ${_on(\'click\', \'stop\')}>') == 1
    assert '<div class="judge-actions" style="margin-top:8px">${verdicts}</div>' in JS


def test_confirm_and_refuse_sit_under_the_line_of_the_proposal_never_in_it():
    line = JS.split("function _proposedLine(c, inModal) {", 1)[1].split("\n}\n", 1)[0]
    # The line is cut at two lines; its buttons follow it, in their own container.
    assert ("the decision stays yours</div>\n      <div class=\"judge-proposed\" ${_on('click', 'stop')}>"
            "<button class=\"action\" style=\"color:var(--green)\"") in line
    assert "✗ Refuse</button></div>`;" in line
    assert "<span ${_on('click', 'stop')}><button" not in line
    # At every width: the container is outside the phone's block.
    base = STYLE.split("  @media (max-width: 759px) {\n", 1)[0]
    assert "  .judge-proposed { display: flex; gap: 5px; margin-top: 3px; }" in base
