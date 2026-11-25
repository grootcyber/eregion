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
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]


def _fn(name: str) -> str:
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


EDGES = _fn("_drawTopologyEdges")


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
    assert "      ${_legend()}`;\n" in JS
    assert "━━ escalation" not in JS and "Edges :" not in JS          # the legend of before, gone


def test_a_card_says_what_it_asks_by_its_colour_from_its_module():
    edge = _fn("_cardEdge")
    assert "const key = e.action === 'restore_from_backup' ? 'restore'" in edge
    assert ": (e.action === 'isolate_vm' || e.escalation_type === 'verification_failed') ? 'isolate'" in edge
    assert ": (e.action === 'improve_detection' || _DETECTION_ONLY.has(e.escalation_type)) ? 'detect'" in edge
    assert "from: key === 'restore' ? 'recover' : key === 'detect' ? 'detect' : 'protect'" in edge
    # A detection to judge, a rule: from DETECT — never the purple line from PROTECT of before.
    assert ": edge.from === 'detect' ? pt(document.getElementById(`nb-${detectBackends[0]?.name}`))" in EDGES
    assert "var(--cyan)" not in EDGES


def test_an_action_taken_alone_draws_no_dotted_line():
    assert "  if (_isExecuted(e)) return null;\n" in _fn("_cardEdge")
    assert "    const edge = _cardEdge(e);\n    if (!edge) return;\n" in EDGES


def test_a_card_waiting_flows_toward_its_tile_once_per_tile_and_kind():
    assert "asset.x + _waitDx(edge.key), asset.top, edge.color, '', own ? 3 : 2.5, 0.9, 'edge-wait'));" in EDGES
    assert "if (!asset || drawn.has(`${vm}|${edge.key}`)) return;" in EDGES
    assert "  .edge-wait { stroke-dasharray: 3 5; animation: edge-flow 1.1s linear infinite; }" in STYLE
    assert "  @keyframes edge-flow { to { stroke-dashoffset: -16; } }" in STYLE


def test_a_state_done_is_solid_in_its_action_s_colour():
    assert "asset.x + (vmBlk ? 6 : 0), asset.top, _mark('isolate').color, '', 2, 0.9));" in EDGES
    assert "asset.x - (vmIso ? 6 : 0), asset.top, _mark('block').color, '', 2, 0.9));" in EDGES
    assert "'6,4'" not in EDGES                                       # a block done: no more long dashes
    # A restore in course: green from RECOVER, solid; its tile green and pulsing.
    assert "if (restoring.has(vmName) && recoverBackends.length) {" in EDGES
    assert "asset.x + _RESTORING_DX, asset.top, _mark('restore').color, '', 2, 0.9));" in EDGES
    assert "  const restoring = new Set(restores.map(r => r.vm_name));\n" in EDGES
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


def test_each_line_arrives_apart_never_one_over_another():
    """The relecture: isolate, block and « other » waiting all came from PROTECT to the same point — the last
    drawn covered the others (measured on a screenshot since, not in the DOM alone)."""
    assert "function _waitDx(key) { return 14 + 8 * _ACTION_MARKS.findIndex(m => m.key === key); }" in JS
    assert "const _RESTORING_DX = -18;" in JS
    keys = re.findall(r"\{ key: '(\w+)',", JS.split("const _ACTION_MARKS = [\n", 1)[1].split("\n];\n", 1)[0])
    waits = [14 + 8 * i for i in range(len(keys))]
    states = {-6, 0, 6, -18}                                  # blocked, alone, isolated, restoring
    assert len(set(waits)) == len(waits) and not set(waits) & states
    # From PROTECT: the module of what is isolated or blocked.
    assert "      : nbNsg;\n" in EDGES


def test_the_colour_drawn_is_the_action_s():
    edge = _fn("_cardEdge")
    assert "return { key, color: _mark(key).color," in edge
    assert "    : e.action === 'block_suspicious_ip' ? 'block'\n" in edge


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
                 "dot('var(--dim)', 'unverifiable · maybe off')", "box('var(--green)', 'dot-pulse', 'restoring')",
                 "box('var(--orange)', 'dot-pulse', 'lifting')", "box('var(--dim)', 'lg-dash', 'excluded')"):
        assert said in legend, said
    assert ".badge.restoring { background: color-mix(in srgb, var(--green) 12%, var(--bg)); color: var(--green);" in STYLE


def test_no_line_on_a_phone_nor_its_legend():
    phone = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]
    assert "    .topo-svg { display: none; }" in phone
    assert "    .legend .lg-lines { display: none; }" in phone
    assert _fn("_legend").count('<div class="lg-row lg-lines">') == 3
