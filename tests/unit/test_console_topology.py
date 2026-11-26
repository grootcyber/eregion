"""TOPO1 (#927): the infrastructure map (/glorfindel) holds while it scrolls, however many cards.

Three glitches, measured in a headless Chromium on the sample bench with thirty more VMs:
the edges were drawn in the screen's coordinates while their svg scrolls with the cards, so
every 5-second refresh made while scrolled put each edge `scrollTop` pixels above its card
(400 px off, scrolled by 400); the refresh replaced the scroll container itself, cutting a
scroll in progress; and nothing drew the edges again when the map changed size (11 of 34 off
after a resize). Now the container outlives a refresh, only what it holds is replaced.

OCT1 (#1240): the tiles' view and its edges gone — their svg, their points, their ResizeObserver
with them. What stays: the scroll container that outlives a refresh, for the table and the 360°.

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


def test_the_scroll_container_outlives_a_refresh():
    infra = body("function renderInfra() {")
    # The shell (container + what a refresh replaces) is built only when one of its two elements is
    # missing — #topo-body checked too (TOPO1b, #949: before, a missing #topo-body threw a TypeError).
    assert "let body  = graph && graph.querySelector('#topo-body');" in infra
    guard = "if (!graph || !list.contains(graph) || !body) {"
    assert guard in infra
    shell = infra.split(guard, 1)[1].split("\n  }\n", 1)[0]
    assert 'list.innerHTML = `<div class="topo-graph" id="topo-graph"><div class="topo-body" id="topo-body"></div></div>`;' in shell
    assert "body  = document.getElementById('topo-body');" in shell
    assert infra.count("list.innerHTML") == 1
    # A refresh replaces the content of #topo-body only, never an element of the shell.
    assert "  body.innerHTML = `" in infra
    refresh = infra.split("  body.innerHTML = `", 1)[1]
    assert 'id="topo-graph"' not in refresh and 'id="topo-body"' not in refresh
    # OCT1: no edges' layer, nothing that draws or watches it.
    assert "topo-svg" not in JS and "topo-svg" not in HTML and "ResizeObserver" not in JS
    # Nothing puts the map's scroll back by hand any more: it is never lost.
    assert "_savedScroll" not in infra and "_newGraph" not in infra
    # The NSG list's own scroll is inside what is replaced: still put back.
    assert "if (_newNsg) _newNsg.scrollTop = _savedNsgScroll;" in infra


def test_what_a_refresh_replaces_has_no_box_of_its_own():
    assert re.search(r"\.topo-body\s*\{\s*display:\s*contents;\s*\}", HTML)
