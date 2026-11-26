"""TOPO1 (#927): the infrastructure map of the Glorfindel page holds while it scrolls, however many
cards. Each mutant brings back a piece of what was measured in a headless Chromium: the edges placed
in the screen's coordinates, `scrollTop` pixels above their card at every refresh made while
scrolled (M6386); the scroll container replaced at every refresh, cutting a scroll in progress
(M6387); the edges not drawn again when the map changes size (M6388); the last edges left on a map
with nothing to draw from, now that the layer outlives a render (M6389); what a refresh replaces
given a box of its own, the layers no longer the column's (M6390). M6386–M6390, measured by
tests/unit/test_console_topology.py. OCT1 (#1240) took off M6386, M6388 and M6389: the edges they measured
went with the tiles' view (no svg, no points, no ResizeObserver left).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"
HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_topology.py::"

MUTANTS = [
    ("M6387", "the scroll container built again at every refresh: a scroll in progress cut (TOPO1, the defect "
              "back)", JS,
     "  if (!graph || !list.contains(graph) || !body) {\n",
     "  if (true) {\n"),
    ("M6390", "what a refresh replaces given a box of its own: the layers no longer the column's, the legend "
              "no longer at its foot (TOPO1)", HTML,
     "  .topo-body { display: contents; }\n",
     ""),
]

TESTS = {
    "M6387": f"{_T}test_the_scroll_container_outlives_a_refresh",
    "M6390": f"{_T}test_what_a_refresh_replaces_has_no_box_of_its_own",
}
