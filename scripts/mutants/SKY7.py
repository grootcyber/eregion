"""SKY7 (#1282): the feed in the sky as wide as its lines, each stopped at the arc (Jonathan, 27/11, « Jusqu'à
l'anneau »). Each mutant takes a piece back: the feed held at its corner's width, the names cut again (M8248); as wide
as its lines over To judge (M8249); a line touching the arc (M8250); a line over a label (M8251); the list's box over
the arc (M8252); a line cut in its digits deep in its corner (M8253); « vm- » said in the sky (M8254); every line
written again at each pass (M8255); a long feed crushed, its lines over one another (M8256); out of the sky, its lines
kept as narrow as the sky had them (M8257). M8248–M8257, measured by tests/unit/test_console_sky_feed.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SKY_JS = "eregion_console/static/infra_sky.js"
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_sky_feed.py::"

MUTANTS = [
    ("M8248", "the feed held at its corner's width: a VM's name cut again (SKY7)", SKY_JS,
     "        out.feed.width = Math.max(out.feed.width, Math.min(Math.ceil(feed.natural), Math.floor(room)));\n", ""),
    ("M8249", "the feed as wide as its lines over To judge (SKY7)", SKY_JS,
     "Math.min(Math.ceil(feed.natural), Math.floor(room))", "Math.ceil(feed.natural)"),
    ("M8250", "a line of the feed touching the arc: no gap kept (SKY7)", SKY_JS,
     "    const r = R + LINE_GAP, dy =", "    const r = R, dy ="),
    ("M8251", "a line of the feed over a label the sky draws beside it (SKY7)", SKY_JS,
     "right = Math.min(right, k.left - LINE_GAP);", "right = Math.min(right, Infinity);"),
    ("M8252", "the feed's box over the arc: never clipped (SKY7)", SKY_JS,
     "    if (!(w > 0 && h > 0) || Math.hypot(nx - x, ny - y) >= r) return '';", "    return '';"),
    ("M8253", "the feed as deep as its corner: a line cut in its time, its action, its share (SKY7)", SKY_JS,
     "          out.feed.maxH = Math.max(60, Math.min(out.feed.maxH || Infinity, deep));\n", ""),
    ("M8254", "« vm- » said in the sky: the room it takes from the name (SKY7)", GF_HTML,
     "  body.sky-full #feed-list .feed-vm-pre { display: none; }", "  body.sky-full #feed-list .feed-vm-pre { display: inline; }"),
    ("M8255", "every line of the feed written again at each pass (SKY7)", GF_JS,
     "    if (r.style.maxWidth !== v) r.style.maxWidth = v;", "    r.style.maxWidth = v;"),
    ("M8256", "a long feed crushed in the sky: its lines over one another (SKY7)", GF_HTML,
     "overflow: hidden; flex-shrink: 0; }", "overflow: hidden; }"),
    ("M8257", "out of the sky, the feed's lines kept as narrow as the sky had them (SKY7)", GF_JS,
     "    document.querySelectorAll('#feed-list .feed-entry').forEach(r => { if (r.style.maxWidth) r.style.maxWidth = ''; });   // SKY7\n", ""),
]

TESTS = {
    "M8248": f"{_T}test_the_feed_is_as_wide_as_its_lines_short_of_to_judge",
    "M8249": f"{_T}test_the_feed_is_as_wide_as_its_lines_short_of_to_judge",
    "M8250": f"{_T}test_a_line_keeps_off_the_arc_at_its_own_height_and_off_the_labels_beside_it",
    "M8251": f"{_T}test_a_line_keeps_off_the_arc_at_its_own_height_and_off_the_labels_beside_it",
    "M8252": f"{_T}test_the_list_s_box_is_clipped_where_it_would_cross_the_arc",
    "M8253": f"{_T}test_the_feed_is_as_tall_as_its_lines_keep_their_time_action_and_share",
    "M8254": f"{_T}test_a_vm_s_name_in_the_sky_says_no_vm_prefix_the_table_its_name_whole",
    "M8255": f"{_T}test_each_line_is_written_as_wide_as_its_room_and_only_when_it_changes",
    "M8256": f"{_T}test_a_long_feed_scrolls_in_the_sky_never_crushed",
    "M8257": f"{_T}test_out_of_the_sky_the_lines_are_as_wide_as_their_list_again",
}
