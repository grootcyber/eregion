"""TOPO1 (#927): the infrastructure map of the Glorfindel page holds while it scrolls, however many
cards. Each mutant brings back a piece of what was measured in a headless Chromium: the edges placed
in the screen's coordinates, `scrollTop` pixels above their card at every refresh made while
scrolled (M6386); the scroll container replaced at every refresh, cutting a scroll in progress
(M6387); the edges not drawn again when the map changes size (M6388); the last edges left on a map
with nothing to draw from, now that the layer outlives a render (M6389); what a refresh replaces
given a box of its own, the layers no longer the column's (M6390). M6386–M6390, measured by
tests/unit/test_console_topology.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"
HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_topology.py::"

MUTANTS = [
    ("M6386", "an edge placed in the screen's coordinates: drawn while scrolled, it falls `scrollTop` pixels "
              "above its card (TOPO1, the defect back)", JS,
     "  const oy = base.top  + graph.clientTop  - graph.scrollTop;\n",
     "  const oy = base.top  + graph.clientTop;\n"),
    ("M6387", "the scroll container built again at every refresh: a scroll in progress cut (TOPO1, the defect "
              "back)", JS,
     "  if (!graph || !list.contains(graph) || !body || !graph.querySelector('#topo-svg')) {\n",
     "  if (true) {\n"),
    ("M6388", "the map no longer watched: resized, its edges stay where the last render put them (TOPO1, the "
              "defect back)", JS,
     "  _topoResize.observe(graph);\n",
     ""),
    ("M6389", "nothing to draw from, the last edges left on the map: its layer outlives a render (TOPO1)", JS,
     "  if (!agent) { svg.innerHTML = ''; return; }\n",
     "  if (!agent) return;\n"),
    ("M6390", "what a refresh replaces given a box of its own: the layers no longer the column's, the legend "
              "no longer at its foot (TOPO1)", HTML,
     "  .topo-body { display: contents; }\n",
     ""),
]

TESTS = {
    "M6386": f"{_T}test_an_edge_is_placed_in_the_contents_coordinates_scrolled_or_not",
    "M6387": f"{_T}test_the_scroll_container_and_its_edges_outlive_a_refresh",
    "M6388": f"{_T}test_the_edges_are_drawn_again_when_the_map_or_its_cards_change_size",
    "M6389": f"{_T}test_with_nothing_to_draw_from_the_last_edges_are_taken_off",
    "M6390": f"{_T}test_what_a_refresh_replaces_has_no_box_of_its_own",
}
