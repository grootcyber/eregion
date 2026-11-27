"""SKY8 (#1288): the three views of the 360° drawn alike (Jonathan, 27/11, on Imladris). Each mutant takes a piece back:
« none » drawing its arc wider than the grouped views (M8299), the sectors' names off the arc in « none » (M8300), a
tile of its own (Entra ID, the control plane) a star like any VM in « none » (M8301), without its glow (M8302).
M8299–M8302, measured by tests/unit/test_console_sky_views.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
DRAW_JS = "eregion_console/static/infra_sky_draw.js"

_T = "tests/unit/test_console_sky_views.py::"

MUTANTS = [
    ("M8299", "« none » drawing its arc wider than the grouped views: the circle a size larger (SKY8)", DRAW_JS,
     "      const r = S.arcR(), big", "      const r = S.arcR() + (grouped() ? 0 : 4), big"),
    ("M8300", "the sectors' names off the arc in « none » (SKY8)", DRAW_JS,
     "rt = r + (below ? 20 : 9);", "rt = RO + (grouped() ? (below ? 108 : 97) : (below ? 74 : 64));"),
    ("M8301", "in « none », Entra ID and the control plane stars like any VM: not the size they are grouped (SKY8)", DRAW_JS,
     "lone = !planet && (grouped() || !!t.own),", "lone = !planet && grouped(),"),
    ("M8302", "in « none », Entra ID and the control plane without their glow (SKY8)", DRAW_JS,
     "      const lone = (grouped() || !!t.own) && !!bodyOf.get(t.key)?.lone,", "      const lone = grouped() && !!bodyOf.get(t.key)?.lone,"),
]

TESTS = {
    "M8299": f"{_T}test_one_arc_in_the_three_views_the_sectors_names_on_it",
    "M8300": f"{_T}test_one_arc_in_the_three_views_the_sectors_names_on_it",
    "M8301": f"{_T}test_a_tile_of_its_own_is_the_size_it_is_in_a_grouped_view_in_every_view",
    "M8302": f"{_T}test_a_tile_of_its_own_is_the_size_it_is_in_a_grouped_view_in_every_view",
}
