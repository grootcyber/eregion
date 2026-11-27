"""SKY5 (#1257): the 360°'s card on a phone, a sheet that rises from the bottom, and the satellites' words, short
(Jonathan, 27/11, on the mockup). Each mutant takes a piece back: every tile of a workspace counted as a VM (M8078), the
words of before (M8079, M8080), a sheet dragged past a third that comes back (M8081), a quick swipe down that does not
close it (M8082), a quick swipe up that stops half-way (M8083), a sheet as tall as its top rest pushed down — its last
lines under the screen, what Jonathan saw on the mockup (M8084), the sky not dimmed (M8085), a drag from its ✕ (M8086),
a sheet dragged down that never lets go of its pin (M8087), the keyboard's focus left behind the sheet (M8088), the
help line of a desktop on a phone (M8089); found by Jonathan on Imladris with it: the satellites scaled with the ring,
out to the systems' orbit (M8106), the table scrolled back to the top at each refresh by the focus given back — to the
view's button (M8107), to a row (M8108). M8078–M8089 and M8106–M8108, measured by tests/unit/test_console_sky_sheet.py,
tests/unit/test_console_sky.py and tests/unit/test_console_sky_card.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SK_JS = "eregion_console/static/infra_sky.js"
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_sky_sheet.py::"
_S = "tests/unit/test_console_sky.py::"

MUTANTS = [
    ("M8078", "every tile of a workspace counted as a VM: Entra ID and an NSG's tile among them (SKY5)", GF_JS,
     "vms = mine.filter(t => t.vm).length;", "vms = mine.length;"),
    ("M8079", "an NSG's words of before: « acted on » (SKY5)", GF_JS,
     "{ d: 'to judge', p: 'acted', r: 'restoring' }[m]", "{ d: 'to judge', p: 'acted on', r: 'restoring' }[m]"),
    ("M8080", "a vault's words of before: « protected », not « kept » (SKY5)", GF_JS,
     "const n = m === 'r' ? `${Number(mine.length)} kept`", "const n = m === 'r' ? `${Number(mine.length)} protected`"),
    ("M8081", "a sheet dragged down past a third that comes back (SKY5)", SK_JS,
     "    if (speed > 0.9 || frac < low * 2 / 3) return 0;", "    if (speed > 0.9) return 0;"),
    ("M8082", "a quick swipe down that does not close the sheet (SKY5)", SK_JS,
     "    if (speed > 0.9 || frac < low * 2 / 3) return 0;", "    if (frac < low * 2 / 3) return 0;"),
    ("M8083", "a quick swipe up that stops half-way (SKY5)", SK_JS,
     "    if (speed < -0.9) return top;\n", ""),
    ("M8084", "a sheet as tall as its top rest, pushed down: its last lines under the screen (SKY5, Jonathan on the mockup)", GF_JS,
     "box.classList.add('anim'); box.style.height = Math.round(_sheetH * window.innerHeight) + 'px';",
     "box.classList.add('anim'); box.style.height = Math.round(InfraSky.SHEET_RESTS[1] * window.innerHeight) + 'px';"),
    ("M8085", "the sky not dimmed behind the sheet: no tap closes it there (SKY5)", GF_JS,
     "  if (scrim && scrim.hidden === on) scrim.hidden = !on;\n", ""),
    ("M8086", "a drag from the sheet's ✕: closing it drags it (SKY5)", GF_JS,
     "    if (!head || ev.target.closest('button')) return;", "    if (!head) return;"),
    ("M8087", "a sheet dragged down that never lets go of its pin: the card still open (SKY5)", GF_JS,
     "    if (!rest) { InfraSkyDraw.unpin(); return; }", "    if (!rest) { return; }"),
    ("M8088", "the keyboard's focus left behind the sheet when it rises (SKY5)", GF_JS,
     "_sheetShow(box, true); box.querySelector('.sky-card-x')?.focus({ preventScroll: true }); }", "_sheetShow(box, true); }"),
    ("M8089", "the help line of a desktop on a phone: « opens beside it » (SKY5)", GF_HTML,
     "    .sky-hint-desk { display: none; } .sky-hint-phone { display: inline; }\n", ""),
    ("M8106", "the satellites scaled with the ring: out to the systems' orbit, their words under its bodies (SKY5, Jonathan on Imladris)", SK_JS,
     "G.RB = G.RG + (RB0 - RG0);", "G.RB = Math.round(RB0 * f);"),
    ("M8107", "the view's button given its focus back by a scroll: the table back to the top at each refresh (SKY5, Jonathan on Imladris)", GF_JS,
     "  if (_viewFocus) [...body.querySelectorAll('[data-view]')].find(b => b.dataset.view === _viewFocus)?.focus({ preventScroll: true });\n  if (_rowFocus)",
     "  if (_viewFocus) [...body.querySelectorAll('[data-view]')].find(b => b.dataset.view === _viewFocus)?.focus();\n  if (_rowFocus)"),
    ("M8108", "a row given its focus back by a scroll: the table brought back to it at each refresh (SKY5)", GF_JS,
     "b.dataset.row === _rowFocus)?.focus({ preventScroll: true });", "b.dataset.row === _rowFocus)?.focus();"),
]

TESTS = {
    "M8078": f"{_S}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M8079": f"{_S}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M8080": f"{_S}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M8081": f"{_T}test_the_sheet_rests_at_half_then_nearly_all_and_closes_past_a_third",
    "M8082": f"{_T}test_the_sheet_rests_at_half_then_nearly_all_and_closes_past_a_third",
    "M8083": f"{_T}test_the_sheet_rests_at_half_then_nearly_all_and_closes_past_a_third",
    "M8084": f"{_T}test_the_sheet_opens_to_what_is_seen_of_it_and_its_head_drags_it",
    "M8085": f"{_T}test_the_sheet_opens_to_what_is_seen_of_it_and_its_head_drags_it",
    "M8086": f"{_T}test_the_sheet_opens_to_what_is_seen_of_it_and_its_head_drags_it",
    "M8087": f"{_T}test_the_sheet_opens_to_what_is_seen_of_it_and_its_head_drags_it",
    "M8088": f"{_T}test_on_a_phone_the_tile_rises_and_the_keyboard_s_focus_goes_to_its_close",
    "M8089": f"{_T}test_the_help_line_says_on_a_phone_what_happens_there_and_the_sheet_s_css",
    "M8106": "tests/unit/test_console_sky_card.py::test_the_centre_follows_the_estate_between_80_and_140_percent",
    "M8107": f"{_T}test_a_refresh_gives_the_focus_back_without_scrolling_the_column",
    "M8108": f"{_T}test_a_refresh_gives_the_focus_back_without_scrolling_the_column",
}
