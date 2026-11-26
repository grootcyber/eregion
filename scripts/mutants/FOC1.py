"""FOC1 (#1231): the focus in the infrastructure map (Jonathan, 26/11, on a mockup). Each mutant takes a piece back:
a tile's focus lighting none of its lines (M7878), a backend's not lighting the tiles it reaches (M7879), nor the
nodes a tile's lines leave (M7880), a focus while a tile is dragged (M7881), while a window is open (M7882), on a
phone (M7883), no delay (M7884), the move from one tile to the next through « nothing » (M7885), a pending focus
that comes after a drag (M7886), a line onto a tile without its key (M7887), a drag that keeps the focus (M7888),
anything under the pointer taken for the map's (M7889). Measured by tests/unit/test_console_focus.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
FO_JS = "eregion_console/static/infra_focus.js"
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_focus.py::"

MUTANTS = [
    ("M7878", "a tile's focus lights none of its lines (FOC1)", FO_JS,
     "      if (focus.tile ? l.k === focus.tile : l.b === focus.backend) {", "      if (!focus.tile && l.b === focus.backend) {"),
    ("M7879", "a backend's focus leaves the tiles it reaches in the back (FOC1)", FO_JS,
     "        if (l.k) tiles.add(l.k);\n", ""),
    ("M7880", "a tile's focus leaves the nodes its lines leave in the back (FOC1)", FO_JS,
     "        if (l.b) nodes.add(l.b);\n", ""),
    ("M7881", "a focus while a tile is dragged (FOC1)", FO_JS,
     "  function allowed(env) { return !env.dragging && !env.modal && !env.phone; }",
     "  function allowed(env) { return !env.modal && !env.phone; }"),
    ("M7882", "a focus while a window is open (FOC1)", FO_JS,
     "  function allowed(env) { return !env.dragging && !env.modal && !env.phone; }",
     "  function allowed(env) { return !env.dragging && !env.phone; }"),
    ("M7883", "a focus on a phone, where no line is drawn (FOC1)", FO_JS,
     "  function allowed(env) { return !env.dragging && !env.modal && !env.phone; }",
     "  function allowed(env) { return !env.dragging && !env.modal; }"),
    ("M7884", "no delay: the map flickers from one tile to the next (FOC1)", FO_JS,
     "        timer = later(() => { timer = null; current = focus || null; apply(current); }, DELAY);",
     "        current = focus || null; apply(current);"),
    ("M7885", "a focus pending never cancelled: the move from A to B through « nothing » (FOC1)", FO_JS,
     "        if (timer !== null) { cancel(timer); timer = null; }\n        if (same(focus, current)) return;",
     "        if (same(focus, current)) return;"),
    ("M7886", "a focus pending comes after a drag has taken it off (FOC1)", FO_JS,
     "      now(focus) {\n        if (timer !== null) { cancel(timer); timer = null; }", "      now(focus) {"),
    ("M7887", "a tile's lines drawn without its key: the focus never lights them (FOC1)", GF_JS,
     "    K = el.id.slice('asset-'.length);              // FOC1: the lines below reach this tile\n", ""),
    ("M7888", "a drag that keeps the focus (FOC1)", GF_JS,
     "    _focusSched.now(null);                        // FOC1: no focus while a tile is dragged\n", ""),
    ("M7889", "anything under the pointer taken for the map's: a tile of a window focused (FOC1)", GF_JS,
     "  if (!(el instanceof Element) || !body || !body.contains(el)) return null;", "  if (!(el instanceof Element)) return null;"),
]

TESTS = {
    "M7878": f"{_T}test_a_tile_lights_itself_its_lines_and_the_nodes_they_leave",
    "M7879": f"{_T}test_a_backend_lights_its_lines_and_the_tiles_they_reach",
    "M7880": f"{_T}test_a_tile_lights_itself_its_lines_and_the_nodes_they_leave",
    "M7881": f"{_T}test_no_focus_while_dragging_in_a_window_or_on_a_phone",
    "M7882": f"{_T}test_no_focus_while_dragging_in_a_window_or_on_a_phone",
    "M7883": f"{_T}test_no_focus_while_dragging_in_a_window_or_on_a_phone",
    "M7884": f"{_T}test_the_focus_waits_about_120_ms_and_never_flickers",
    "M7885": f"{_T}test_the_focus_waits_about_120_ms_and_never_flickers",
    "M7886": f"{_T}test_a_drag_or_a_window_takes_the_focus_off_at_once",
    "M7887": f"{_T}test_every_line_onto_a_tile_says_the_tile_and_the_node_it_leaves",
    "M7888": f"{_T}test_a_drag_and_a_window_take_the_focus_off_and_a_tile_takes_the_keyboard",
    "M7889": f"{_T}test_what_is_under_the_pointer_a_tile_a_backend_or_nothing_of_the_map",
}
