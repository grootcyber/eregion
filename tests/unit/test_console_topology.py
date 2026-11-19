"""TOPO1 (#927): the infrastructure map (/glorfindel) holds while it scrolls, however many cards.

Three glitches, measured in a headless Chromium on the sample bench with thirty more VMs:
the edges were drawn in the screen's coordinates while their svg scrolls with the cards, so
every 5-second refresh made while scrolled put each edge `scrollTop` pixels above its card
(400 px off, scrolled by 400); the refresh replaced the scroll container itself, cutting a
scroll in progress; and nothing drew the edges again when the map changed size (11 of 34 off
after a resize). Now the container and its svg outlive a refresh, only what they hold is
replaced, the points are the content's, and a ResizeObserver draws again, once a frame at most.

Read in the page's text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")


def body(head: str) -> str:
    assert head in JS, head
    return JS.split(head, 1)[1].split("\n}\n", 1)[0]


def test_an_edge_is_placed_in_the_contents_coordinates_scrolled_or_not():
    draw = body("function _drawTopologyEdges() {")
    assert "const ox = base.left + graph.clientLeft - graph.scrollLeft;" in draw
    assert "const oy = base.top  + graph.clientTop  - graph.scrollTop;" in draw
    pt = draw.split("function pt(el, side) {", 1)[1].split("\n  }\n", 1)[0]
    for line in ("const x = r.left - ox + r.width / 2;", "top:    r.top    - oy,",
                 "bottom: r.bottom - oy,", "left:   r.left   - ox,", "right:  r.right  - ox,"):
        assert line in pt, line
    # No point left in the screen's coordinates.
    assert "- base.top" not in pt and "- base.left" not in pt


def test_the_scroll_container_and_its_edges_outlive_a_refresh():
    infra = body("function renderInfra() {")
    # The shell (container + svg + what a refresh replaces) is built only when one of its three
    # elements is missing — #topo-body and #topo-svg checked too (TOPO1b, #949: before, a missing
    # #topo-body threw a TypeError).
    assert "let body  = graph && graph.querySelector('#topo-body');" in infra
    guard = "if (!graph || !list.contains(graph) || !body || !graph.querySelector('#topo-svg')) {"
    assert guard in infra
    shell = infra.split(guard, 1)[1].split("\n  }\n", 1)[0]
    assert ('list.innerHTML = `<div class="topo-graph" id="topo-graph"><svg class="topo-svg" id="topo-svg">'
            '</svg><div class="topo-body" id="topo-body"></div></div>`;') in shell
    assert "body  = document.getElementById('topo-body');" in shell
    assert infra.count("list.innerHTML") == 1
    # A refresh replaces the content of #topo-body only, never an element of the shell.
    assert "  body.innerHTML = `" in infra
    refresh = infra.split("  body.innerHTML = `", 1)[1]
    assert 'id="topo-graph"' not in refresh and 'id="topo-svg"' not in refresh and 'id="topo-body"' not in refresh
    # Nothing puts the map's scroll back by hand any more: it is never lost.
    assert "_savedScroll" not in infra and "_newGraph" not in infra
    # The NSG list's own scroll is inside what is replaced: still put back.
    assert "if (_newNsg) _newNsg.scrollTop = _savedNsgScroll;" in infra


def test_what_a_refresh_replaces_has_no_box_of_its_own():
    assert re.search(r"\.topo-body\s*\{\s*display:\s*contents;\s*\}", HTML)


def test_the_edges_are_drawn_again_when_the_map_or_its_cards_change_size():
    infra = body("function renderInfra() {")
    assert infra.rstrip().endswith("_watchTopology(graph);\n  _queueTopologyEdges();\n  _applyReadOnlyGuards(list);")
    assert "requestAnimationFrame(_drawTopologyEdges)" not in infra
    queue = body("function _queueTopologyEdges() {")
    assert "if (_topoDrawQueued) return;" in queue
    assert "requestAnimationFrame(() => { _topoDrawQueued = false; _drawTopologyEdges(); });" in queue
    watch = body("function _watchTopology(graph) {")
    assert "new ResizeObserver(_onTopologyResize)" in watch
    # The row of the last render let go, the map and the new row watched.
    assert watch.index("_topoResize.disconnect();") < watch.index("_topoResize.observe(graph);")
    assert "  const assets = document.getElementById('topo-assets');\n  if (assets) _topoResize.observe(assets);" in watch


def test_a_browser_without_resizeobserver_still_draws_at_each_render():
    # TOPO1b (#949, review of TOPO1): the guard comes first — without it, `new ResizeObserver`
    # throws, and the render stops before its edges are queued.
    watch = body("function _watchTopology(graph) {")
    assert watch.lstrip().startswith("if (typeof ResizeObserver !== 'function') return;\n")
    infra = body("function renderInfra() {")
    assert infra.index("_watchTopology(graph);") < infra.index("_queueTopologyEdges();")


def test_a_refresh_draws_its_edges_once_a_resize_draws_them_again():
    # TOPO1b (#949, review of TOPO1): each render observes its new row, and an observation starts
    # with a notification — drawn on it, every refresh drew twice. A size already seen draws
    # nothing; a size changed (a resize, a card grown without a render) draws again.
    seen = body("function _onTopologyResize(entries) {")
    assert "const role = e.target.id === 'topo-graph' ? 'graph' : 'assets';" in seen
    assert "const size = `${Math.round(e.contentRect.width)}x${Math.round(e.contentRect.height)}`;" in seen
    assert "if (_topoSeen[role] !== size) { _topoSeen[role] = size; changed = true; }" in seen
    assert seen.rstrip().endswith("if (changed) _queueTopologyEdges();")


def test_with_nothing_to_draw_from_the_last_edges_are_taken_off():
    draw = body("function _drawTopologyEdges() {")
    assert "if (!agent) { svg.innerHTML = ''; return; }" in draw
