"""SKY6 (#1268): the lists in the sky — on a desktop, the 360° without the column, To judge, the feed and the legend in
the room the circle leaves, the bubble (Jonathan, 27/11, on the mockup v26). Each mutant takes a piece back:
- the lists' places: always the wide window's (M8140), a corner not narrowed to its room (M8141), the legend at
  its full width over the orbit (M8142), the bands at the sky's left edge, under the feed (M8143);
- the bubble's and the card's places: the bubble on its inner side first (M8144), over the lists (M8145), the
  card over them (M8146);
- the column's nodes: left in the sky for the table (M8147), never given back to the column (M8148), the sky's
  layout on a phone (M8149);
- the lines: a line of To judge to its window (M8150), a line of the feed to nothing (M8151);
- the bubble: its card at once (M8152), out of reach its writes kept (M8153), read-only its writes on (M8154),
  rewritten at rest (M8155), closed from within its focus lost (M8156);
- by itself: for a page's old cards (M8157), while something is pinned (M8158), past its minute (M8159);
- from the relecture: a corner's list into the circle, by a NaN (M8185) or by its height (M8186), the bubble without
  its cards to judge (M8187), the lists back at their top (M8188), their places kept out of the sky (M8189), the
  bubble over its target (M8190), the card under the circle (M8191), a bubble under an open window (M8192);
- from the second: a tall bubble never shorter (M8225), one by itself with no room (M8226), its height unbounded
  (M8227), the bubble's card without its proposed verdict (M8228), its exercise (M8229), its IP (M8230), its time
  unreadable (M8232), the card over a tall window's lists (M8231).
M8140–M8159, M8185–M8192 and M8225–M8232, measured by tests/unit/test_console_sky_lists.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SK_JS = "eregion_console/static/infra_sky.js"
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_sky_lists.py::"

MUTANTS = [
    ("M8140", "the lists always in a wide window's places, in a box nearly square too (SKY6)", SK_JS,
     "    if (f.side >= SIDE_MIN) {", "    if (true) {"),
    ("M8141", "a corner's list never narrowed to the room its corner leaves: into the orbit (SKY6)", SK_JS,
     "        const r = room(w, h);\n        if (w <= r) break;", "        const r = room(w, h);\n        break;"),   # SKY7: corner()'s, not column()'s
    ("M8142", "the legend at its full width in a wide window, over the orbit's labels (SKY6)", SK_JS,
     "      const lg = corner('legend', false, Math.min(1100, box.w - 2 * EDGE), 14, ww);",
     "      const lg = { w: Math.min(1100, box.w - 2 * EDGE), h: heightOf('legend', Math.min(1100, box.w - 2 * EDGE)) };"),
    ("M8143", "the bands at the sky's left edge, under the feed (SKY6)", SK_JS,
     "atTop ? out.feed.left + out.feed.width + 20 : 12;", "12;"),   # SKY7: the bands right of To judge at « left »
    ("M8144", "the bubble on its target's inner side first, toward Glorfindel (SKY6)", SK_JS,
     "const out = right ? t.x + t.w + gap : t.x - w - gap, inn = right ? t.x - w - gap : t.x + t.w + gap;",
     "const inn = right ? t.x + t.w + gap : t.x - w - gap, out = right ? t.x - w - gap : t.x + t.w + gap;"),
    ("M8145", "the bubble over the lists (SKY6)", SK_JS,
     "    const clear = ([x, y], h) => (lists || []).every(", "    const clear = ([x, y], h) => [].every("),
    ("M8146", "the card over the lists (SKY6)", SK_JS,
     "+ over(p) * 5e3 +", "+ 0 +"),
    ("M8147", "the table written over the sky with the column's nodes in it: To judge and the feed lost (SKY6)", GF_JS,
     "  _skyFullOn(false); _infraTools('');\n  body.innerHTML = `", "  body.innerHTML = `"),
    ("M8148", "the column's nodes never given back to the column (SKY6)", GF_JS,
     "    if (col && nodes.some(n => n && n.parentElement !== col)) col.append(...nodes.filter(Boolean));   // in their order\n", ""),
    ("M8149", "the sky's layout on a phone: its tabs without To judge and the feed (SKY6)", GF_JS,
     "function _skyFull() { return _infraView() === 'sky' && !_isPhone() && !_configMode; }",
     "function _skyFull() { return _infraView() === 'sky' && !_configMode; }"),
    ("M8150", "a line of To judge in the sky opens its window, not its tile's bubble (SKY6)", GF_JS,
     "  if (_skyFull() && typeof InfraSkyDraw !== 'undefined') { const r = _tileOfCard(escId);",
     "  if (false) { const r = _tileOfCard(escId);"),
    ("M8151", "a line of the feed in the sky opens nothing (SKY6)", GF_JS,
     "  if (r) InfraSkyDraw.pinTo({ a: r.key });\n}\ndocument.getElementById('feed-list').addEventListener('click', _feedLineClick);",
     "}\ndocument.getElementById('feed-list').addEventListener('click', _feedLineClick);"),
    ("M8152", "a tile clicked in the sky opens its card at once, never its bubble first (SKY6, Jonathan on the mockup)", GF_JS,
     "  if (f) return f.a && !_skyCardFull ? f.a : null;", "  if (f) return null;"),
    ("M8153", "the bubble of a tile out of reach keeps its writes (SKY6)", GF_JS,
     "      if (oor) _dropWrites(el);                                    // out of reach, nothing written (GRP1)\n", ""),
    ("M8154", "the bubble's writes on, read-only (SKY6)", GF_JS,
     "      _applyReadOnlyGuards(el);\n      _skyBubbleLast = sig;", "      _skyBubbleLast = sig;"),
    ("M8155", "the bubble rewritten at each render, at rest (SKY6)", GF_JS,
     "  if (sig !== _skyBubbleLast || !el.childElementCount) {", "  if (true) {"),
    ("M8156", "the bubble closed from within: the keyboard's focus lost (SKY6)", GF_JS,
     "      if (inside && was) InfraSkyDraw.focusOn({ a: was });       // closed from within: the focus back on what it was on\n", ""),
    ("M8157", "a bubble by itself for the cards a page finds when it loads (SKY6)", GF_JS,
     "  const seen = _skySeen, fresh = asks.filter(e => !seen.has(e.id) && _skyNew(e, now));", "  const seen = _skySeen, fresh = asks.filter(e => !seen.has(e.id));"),
    ("M8158", "a bubble by itself while something is pinned (SKY6)", GF_JS,
     "  if (!fresh.length || !_skyFull() || InfraSkyDraw.pinned() || document", "  if (!fresh.length || !_skyFull() || document"),
    ("M8159", "a bubble by itself that stays past its minute (SKY6)", GF_JS,
     "  _skyAuto = null; _skyBubble();\n}\nfunction _skyBubbleListen(el) {", "  _skyBubble();\n}\nfunction _skyBubbleListen(el) {"),
    # The relecture (Opus 5.5, on 2aa53806).
    ("M8185", "a corner's list that reaches the centre's height: a sqrt of a negative, NaN, the list over the drawing (SKY6, the relecture)", SK_JS,
     "const dx = dy >= c.r ? 0 : dy <= 0 ? c.r : Math.sqrt(c.r * c.r - dy * dy);", "const dx = dy >= c.r ? 0 : Math.sqrt(c.r * c.r - dy * dy);"),
    ("M8186", "a corner's list as tall as its content: a feed of 52 lines over the circle and the legend (SKY6, the relecture)", SK_JS,
     "      return { w, h: Math.min(h, cap), maxH: Number.isFinite(cap) ? cap : null };", "      return { w, h, maxH: null };"),
    ("M8187", "the bubble without its tile's cards to judge: one acknowledged said « nothing waits here », no verdict (SKY6, the relecture)", GF_JS,
     "    + (verdicts ? `<div class=\"sky-bubble-h\">TO JUDGE</div>${verdicts}` : '')", "    + ''"),
    ("M8188", "To judge and the feed back at their top at each refresh (SKY6, the relecture)", GF_JS,
     "  kept.forEach(([e, top]) => { if (e.scrollTop !== top) e.scrollTop = top; });\n", ""),
    ("M8189", "the lists' places kept out of the sky: a phone's legend at a desktop's width (SKY6, the relecture)", GF_JS,
     "    [legend, document.getElementById('sky-bands'), judge, feed].forEach(e => { if (e && e.hasAttribute && e.hasAttribute('style')) e.removeAttribute('style'); });", ""),
    ("M8190", "the bubble held within the box over its own target (SKY6, the relecture)", SK_JS,
     "      const q = at(h).find(p => clear(p, h) && !covers(p, h));", "      const q = at(h).find(p => clear(p, h));"),
    ("M8191", "in the sky, the card laid under the circle, out of the window (SKY6, the relecture)", GF_JS,
     "    || (full ? InfraSky.placeCard(frame, target, card, { x: c.x - w.left, y: c.y - w.top, r: 0 }, band, avoid) : null);", "    || null;"),
    ("M8192", "a bubble by itself under an open window (SKY6, the relecture)", GF_JS,
     " || document.getElementById('modal')?.classList.contains('open')) return;", ") return;"),
    # The second relecture (Opus 5.5, on ad7f7a40).
    ("M8225", "a tall bubble never made shorter: held at the box's top, over To judge or the feed (SKY6, the second relecture)", SK_JS,
     "    const lo = Math.min(size.h, least || 140);", "    const lo = size.h;"),
    ("M8226", "a bubble by itself opened with no room off the lists (SKY6, the second relecture)", GF_JS,
     "  if (!at.clear && el.dataset.auto) { _skyAuto = null; el.hidden = true; el.replaceChildren(); el.dataset.auto = ''; _skyBubbleLast = _skyBubbleGuard = ''; return; }\n", ""),
    ("M8227", "the bubble as tall as its content: its height never bounded to its room (SKY6, the second relecture)", GF_JS,
     "  if (el.style.maxHeight !== most) el.style.maxHeight = most;\n  if (el.style.left", "  if (el.style.left"),
    ("M8228", "the bubble without the verdict a drill proposes: no Confirm, no Refuse (SKY6, the second relecture)", GF_JS,
     "${exercise}${proposed}${why", "${exercise}${why"),
    ("M8229", "the bubble without its card's exercise: judged « wrong », an exercise taken for a false alarm (SKY6, the second relecture)", GF_JS,
     "${untimed}${exercise}${proposed}", "${untimed}${proposed}"),
    ("M8230", "the bubble's card without the IP its block targets (SKY6, the second relecture)", GF_JS,
     "const what = (c.action ? actionLabelVerb(c.action) : escTitle(c)) + target + pct, why", "const what = (c.action ? actionLabelVerb(c.action) : escTitle(c)) + pct, why"),
    ("M8231", "in a tall window, the card laid over the lists under the circle (SKY6, the second relecture)", GF_JS,
     "  const under = full && wrap.dataset.arr === 'below' && avoid && avoid.length ? Math.min(...avoid.filter(o => o.y > w.height / 2).map(o => o.y), y1) : y1;",
     "  const under = y1;"),
    ("M8232", "the bubble's card without its time unreadable (SKY6, the second relecture)", GF_JS,
     "</div>${untimed}${exercise}", "</div>${exercise}"),
]

TESTS = {
    "M8140": f"{_T}test_a_box_nearly_square_the_circle_at_the_right_the_three_at_the_left",
    "M8141": f"{_T}test_a_wide_window_the_feed_at_the_top_left_to_judge_at_the_top_right_the_legend_at_the_bottom_left",   # SKY7: the legend's corner
    "M8142": f"{_T}test_a_wide_window_the_feed_at_the_top_left_to_judge_at_the_top_right_the_legend_at_the_bottom_left",
    "M8143": f"{_T}test_a_wide_window_the_feed_at_the_top_left_to_judge_at_the_top_right_the_legend_at_the_bottom_left",
    "M8144": f"{_T}test_the_bubble_sits_beside_its_target_on_its_outer_side_off_the_lists",
    "M8145": f"{_T}test_the_bubble_sits_beside_its_target_on_its_outer_side_off_the_lists",
    "M8146": f"{_T}test_the_card_keeps_off_the_lists",
    "M8147": f"{_T}test_the_table_and_the_configuration_take_the_column_back_first",
    "M8148": f"{_T}test_the_column_s_nodes_are_moved_into_the_sky_and_back_never_copied",
    "M8149": f"{_T}test_the_sky_takes_the_lists_on_a_desktop_s_360_only",
    "M8150": f"{_T}test_a_line_of_to_judge_or_of_the_feed_opens_its_tile_s_bubble_in_the_sky",
    "M8151": f"{_T}test_a_line_of_to_judge_or_of_the_feed_opens_its_tile_s_bubble_in_the_sky",
    "M8152": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8153": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8154": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8155": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8156": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8157": f"{_T}test_a_card_that_comes_to_judge_or_to_approve_opens_its_bubble_by_itself_for_a_minute",
    "M8158": f"{_T}test_a_card_that_comes_to_judge_or_to_approve_opens_its_bubble_by_itself_for_a_minute",
    "M8159": f"{_T}test_a_card_that_comes_to_judge_or_to_approve_opens_its_bubble_by_itself_for_a_minute",
    "M8185": f"{_T}test_lists_taller_than_the_box_are_held_off_the_circle_and_scroll",
    "M8186": f"{_T}test_lists_taller_than_the_box_are_held_off_the_circle_and_scroll",
    "M8187": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8188": f"{_T}test_the_lists_keep_where_they_were_read_when_they_are_placed_again",
    "M8189": f"{_T}test_the_column_s_nodes_are_moved_into_the_sky_and_back_never_copied",
    "M8190": f"{_T}test_the_bubble_sits_beside_its_target_on_its_outer_side_off_the_lists",
    "M8191": f"{_T}test_in_the_sky_the_card_is_never_laid_under_the_circle",
    "M8192": f"{_T}test_a_card_that_comes_to_judge_or_to_approve_opens_its_bubble_by_itself_for_a_minute",
    "M8225": f"{_T}test_a_tall_bubble_is_made_shorter_to_find_room_off_the_lists_or_says_there_is_none",
    "M8226": f"{_T}test_the_bubble_is_held_off_the_lists_in_every_arrangement_and_by_itself_opens_only_with_room",
    "M8227": f"{_T}test_the_bubble_is_held_off_the_lists_in_every_arrangement_and_by_itself_opens_only_with_room",
    "M8228": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8229": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8230": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
    "M8231": f"{_T}test_in_a_tall_window_the_card_is_held_above_the_lists",
    "M8232": f"{_T}test_the_bubble_shows_what_waits_with_the_tile_s_buttons_and_the_card_s_guards",
}
