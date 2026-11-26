"""LEG1 (#1181): the map's lines and legend say the same thing (Jonathan, 25/11, on a mockup).

The legend had not moved since the start; the map had: five colours of a card's line, a grey dot, the
tiles' borders, a dashed tile. A block waiting read « isolated », a rule proposed « detect », and a card
on Entra ID drew a purple line from PROTECT. Jonathan's rule:
  - the colour says the action — red isolate (or a check failed), orange block, green restore (the
    colour of RECOVER), blue what the detection asks (a verdict, a rule), purple any other card;
  - the stroke says where it stands — dotted and flowing toward the tile while a human must act, solid
    once done; an action Glorfindel took alone draws no dotted line, only its verdict waits;
  - a VM isolated red everywhere, a block done solid orange, a restore green everywhere;
  - the legend in five lines, read from the same table the map draws from.

Measured in a headless Chromium at 1600 × 1000 and 390 × 844 (the PR says how); read here in the
page's text: no browser in the suite.

OCT1 (#1240): the tiles' view and its lines gone. What stays here: the table of the marks, the legend, the
tiles' colours; the table's legend without lines (it draws none). The 360° draws the lines (test_console_sky.py),
and LEG2 (#1244) brings them to these colours.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]


def _fn(name: str) -> str:
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def test_one_table_for_the_marks_drawn_and_said():
    table = JS.split("const _ACTION_MARKS = [\n", 1)[1].split("\n];\n", 1)[0]
    for key, color in (("isolate", "red"), ("block", "orange"), ("restore", "green"), ("detect", "blue"),
                       ("other", "purple")):
        assert re.search(rf"\{{ key: '{key}', +color: 'var\(--{color}\)',", table), key
    legend = _fn("_legend")
    assert "${_ACTION_MARKS.map(m => sw(ln(m.color, 'edge-wait'), m.wait)).join('')}" in legend
    assert "${_ACTION_MARKS.filter(m => m.done).map(m => sw(ln(m.color), m.done)).join('')}" in legend
    for line in ("MODULES", "WAITING", "DONE", "DOTS", "TILES"):
        assert f'<span class="lg-h">{line}</span>' in legend, line
    assert "      ${_legend('table')}`;\n" in JS and "document.getElementById('sky-legend').innerHTML = _legend();" in JS
    assert "━━ escalation" not in JS and "Edges :" not in JS          # the legend of before, gone


def test_the_legend_s_waiting_line_flows():
    assert "  .edge-wait { stroke-dasharray: 3 5; animation: edge-flow 1.1s linear infinite; }" in STYLE
    assert "  @keyframes edge-flow { to { stroke-dashoffset: -16; } }" in STYLE


def test_a_tile_restoring_is_green():
    # A restore in course: its tile green and pulsing (its line, the 360°'s: test_console_sky.py).
    assert "  .node-asset.s-restoring { border-color: var(--green);" in STYLE
    assert "restoreInfo   ? `<span class=\"dot-pulse\" style=\"color:var(--green)\">●</span>`" in JS


def test_a_tile_of_detections_is_blue_while_a_verdict_waits():
    node = _fn("_renderNsgNode")
    assert "const judgeOnly = myEscs.length > 0 && myEscs.every(e => _DETECTION_ONLY.has(e.escalation_type));" in node
    assert "${judgeOnly ? 's-judge' : myEscs.length ? 's-incident' : 's-clean'}" in node
    assert "  .node-asset.s-judge     { border: 2px solid var(--blue);" in STYLE


def test_still_for_whoever_asks_for_less_motion():
    block = STYLE.split("  @media (prefers-reduced-motion: reduce) {\n", 1)[1].split("\n  }\n", 1)[0]
    assert ".edge-wait, .dot-pulse, .node-asset.s-restoring, .node-asset.s-releasing, .badge.restoring { animation: none; }" in block


def test_a_vm_s_detections_to_judge_are_blue_after_its_states():
    node = _fn("_renderAssetNode")
    assert "const judgeOnly = myEscs.length > 0 && myEscs.every(e => _DETECTION_ONLY.has(e.escalation_type));" in node
    assert node.index("? 's-restoring'") < node.index("? 's-isolated'") < node.index("? 's-blocked'") < node.index("(judgeOnly ? 's-judge' : 's-incident')")
    assert "myEscs.length ? `<span style=\"color:${judgeOnly ? 'var(--blue)' : 'var(--purple)'}\">●</span>`" in node
    assert "judgeOnly ? 'var(--blue)' : myEscs.length ? 'var(--purple)' : 'var(--green)'" in _fn("_renderNsgNode")


def test_the_dots_and_tiles_lines_and_the_restoring_badge():
    legend = _fn("_legend")
    for said in ("dot('var(--green)', 'clean')", "dot('var(--purple)', 'a card waits')", "dot('var(--blue)', 'a verdict waits')",
                 "dot('var(--red)', 'isolated')", "dot('var(--orange)', 'blocked')", "dot('var(--green)', 'restoring', 'dot-pulse')",
                 # IDT1: the grey of a watched tile's silent logs, and the red of its rule in error, on the same line.
                 "dot('var(--dim)', 'unverifiable · maybe off · logs silent')",
                 "dot('var(--red)', \"a rule or its logs' read in error (Entra ID, control plane)\")", "box('var(--green)', 'dot-pulse', 'restoring')",
                 "box('var(--orange)', 'dot-pulse', 'lifting')", "box('var(--dim)', 'lg-dash', 'excluded · out of reach')"):
        assert said in legend, said
    assert ".badge.restoring { background: color-mix(in srgb, var(--green) 12%, var(--bg)); color: var(--green);" in STYLE


def test_no_line_on_a_phone_nor_its_legend():
    phone = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]
    assert "    .legend .lg-lines { display: none; }" in phone
    assert _fn("_legend").count('<div class="lg-row lg-lines">') == 3


def test_the_table_s_legend_says_no_line():
    """OCT1 (#1240): the table draws no line — its legend says the dots and the tiles only; the 360°'s, all five.
    Run as it is (tests/unit/js_engine.py)."""
    script = js_engine.take(JS, "_ACTION_MARKS", "_legend") + r"""
const heads = html => [...html.matchAll(/<span class="lg-h">(\w+)<\/span>/g)].map(m => m[1]);
emit(JSON.stringify([heads(_legend('table')), heads(_legend()), (_legend('table').match(/lg-lines/g) || []).length]));
"""
    table, sky, lines = json.loads(js_engine.run(script))
    assert table == ["DOTS", "TILES"] and lines == 0
    assert sky == ["MODULES", "WAITING", "DONE", "DOTS", "TILES"]
