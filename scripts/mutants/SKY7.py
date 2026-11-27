"""SKY7 (#1282): the feed in the sky as wide as its lines, each stopped at the arc (Jonathan, 27/11, « Jusqu'à
l'anneau »). Each mutant takes a piece back: the feed held at its corner's width, the names cut again (M8248); as wide
as its lines over To judge (M8249); a line touching the arc (M8250); a line over a label (M8251); the list's box over
the arc (M8252); a line cut in its digits deep in its corner (M8253); a VM's name cut of its « vm- » in the sky again (M8254, Jonathan:
« Le nom entier partout »); every line
written again at each pass (M8255); a long feed crushed, its lines over one another (M8256); out of the sky, its lines
kept as narrow as the sky had them (M8257); on a small screen (Jonathan: « Cercle à droite », « To judge, puis le
fil », the circle a little smaller): the circle left in the middle (M8258), drawn centred all the same (M8259), the
feed over To judge (M8260), the circle never smaller, a line cut beside it (M8261), as small as it takes (M8262), the
drawing not following the lists (M8263), a tile's card over a list when there is room between them (M8264), the bands
over To judge (M8265); from the relecture: the bands over a feed wider than To judge (M8296), out of the sky the
drawing left at the right and smaller (M8297), the drawing aligned and its labels read before it is drawn (M8298).
M8248–M8265 and M8296–M8298, measured by tests/unit/test_console_sky_feed.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SKY_JS = "eregion_console/static/infra_sky.js"
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"
DRAW_JS = "eregion_console/static/infra_sky_draw.js"

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
    ("M8254", "a VM's name cut of its « vm- » in the sky again: another name than the bubble's, To judge's, the card's (SKY7)", DRAW_JS,
     "      label(17, 4, String(t.name || t.key), t.out", "      label(17, 4, String(t.name || t.key).replace(/^vm-/, ''), t.out"),
    ("M8255", "every line of the feed written again at each pass (SKY7)", GF_JS,
     "    if (r.style.maxWidth !== v) r.style.maxWidth = v;", "    r.style.maxWidth = v;"),
    ("M8256", "a long feed crushed in the sky: its lines over one another (SKY7)", GF_HTML,
     "overflow: hidden; flex-shrink: 0; }", "overflow: hidden; }"),
    ("M8257", "out of the sky, the feed's lines kept as narrow as the sky had them (SKY7)", GF_JS,
     "    document.querySelectorAll('#feed-list .feed-entry').forEach(r => { if (r.style.maxWidth) r.style.maxWidth = ''; });   // SKY7\n", ""),
    ("M8258", "on a small screen, the circle left in the middle: the lists at the left over it (SKY7)", SKY_JS,
     "      c.x = box.w - (G.W - G.cx) * f.k; c.r = RL * f.k;", "      c.r = RL * f.k;"),
    ("M8259", "on a small screen, the circle drawn centred all the same (SKY7)", SKY_JS,
     "      out.arr = 'left'; out.align = 'xMaxYMid';", "      out.arr = 'left';"),
    ("M8260", "on a small screen, the feed at the top, over To judge (SKY7)", SKY_JS,
     "      const top = 10 + jd.h + 14, fd =", "      const top = 10, fd ="),
    ("M8261", "on a small screen, the circle never smaller: a line of the feed cut beside it (SKY7)", SKY_JS,
     "      f.k = Math.max(f.k * (1 - SHRINK_MAX), Math.min(f.k, (box.w - 10 - LEFT_COL - LINE_GAP) / (G.W - G.cx + arcG)));\n", ""),
    ("M8262", "on a small screen, the circle as small as it takes (SKY7)", SKY_JS,
     "      f.k = Math.max(f.k * (1 - SHRINK_MAX), Math.min(", "      f.k = Math.max(0, Math.min("),
    ("M8263", "the drawing not following the lists: the circle drawn at its full size (SKY7)", GF_JS,
     "InfraSkyDraw.align(L.align, L.padY);", "InfraSkyDraw.align(L.align);"),
    ("M8264", "a tile's card over a list when there is room between them (SKY7)", SKY_JS,
     "    const byLists = (avoid || []).flatMap(o => [[o.x, o.y + o.h + gap], [o.x, o.y - h - gap]]);", "    const byLists = [];"),
    ("M8265", "on a small screen, the bands over To judge (SKY7)", SKY_JS,
     "    const l = out.arr === 'left' ? out.judge.left + Math.max(out.judge.width, out.feed.width) + 20 :", "    const l = out.arr === 'left' ? 10 :"),
    ("M8296", "on a small screen, the bands over a feed wider than To judge (SKY7, relecture)", SKY_JS,
     "Math.max(out.judge.width, out.feed.width) + 20", "out.judge.width + 20"),
    ("M8297", "out of the sky, the drawing left at the right and smaller: 24 px of nothing on a phone (SKY7, relecture)", GF_JS,
     "    if (typeof InfraSkyDraw !== 'undefined') InfraSkyDraw.align('xMidYMid', 0);  // the drawing centred, at its size\n", ""),
    ("M8298", "the drawing aligned and its labels read before it is drawn: at its first drawing, another group by (SKY7, relecture)", GF_JS,
     "  InfraSkyDraw.mount(document.getElementById('sky-slot'), _skyModelLast, _skyPanel, _skyPlaceCard);\n  _skyDrawn();\n",
     "  InfraSkyDraw.mount(document.getElementById('sky-slot'), _skyModelLast, _skyPanel, _skyPlaceCard);\n"),
]

TESTS = {
    "M8248": f"{_T}test_the_feed_is_as_wide_as_its_lines_short_of_to_judge",
    "M8249": f"{_T}test_the_feed_is_as_wide_as_its_lines_short_of_to_judge",
    "M8250": f"{_T}test_a_line_keeps_off_the_arc_at_its_own_height_and_off_the_labels_beside_it",
    "M8251": f"{_T}test_a_line_keeps_off_the_arc_at_its_own_height_and_off_the_labels_beside_it",
    "M8252": f"{_T}test_the_list_s_box_is_clipped_where_it_would_cross_the_arc",
    "M8253": f"{_T}test_the_feed_is_as_tall_as_its_lines_keep_their_time_action_and_share",
    "M8254": f"{_T}test_a_vm_s_name_is_its_azure_name_everywhere_in_the_sky",
    "M8255": f"{_T}test_each_line_is_written_as_wide_as_its_room_and_only_when_it_changes",
    "M8256": f"{_T}test_a_long_feed_scrolls_in_the_sky_never_crushed",
    "M8257": f"{_T}test_out_of_the_sky_the_lines_are_as_wide_as_their_list_again",
    "M8258": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8259": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8260": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8261": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8262": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8263": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8264": f"{_T}test_a_tile_s_card_finds_the_room_between_the_lists_at_the_left",
    "M8265": f"{_T}test_the_feed_is_as_wide_as_its_lines_short_of_to_judge",
    "M8296": f"{_T}test_on_a_small_screen_the_circle_at_the_right_a_little_smaller_the_three_at_the_left",
    "M8297": f"{_T}test_out_of_the_sky_the_lines_are_as_wide_as_their_list_again",
    "M8298": f"{_T}test_once_drawn_the_sky_is_aligned_and_its_lines_read_its_labels_again",
}
