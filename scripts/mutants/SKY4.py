"""SKY4 (#1249): the 360°'s floating card and a centre that follows the estate (Jonathan, 26/11, on the mockup). Each
mutant takes a piece back: a centre of one size whatever the estate (M7995), a centre without bounds (M7996), the draw
never asking its size (M7997), its heart not following it (M7998), a card over Glorfindel (M7999), a card over what was
clicked (M8000), a card opened by a hover (M8001), a card left open with nothing pinned (M8002), a card never placed
(M8003), a card without its ✕ (M8004), a module's card without its block (M8005), a focus on no module breaking the
card (M8006), satellites with nothing to say (M8007), a line said once and never again (M8008), the card left behind
by the bodies that move (M8009), Escape in a field of the card closing it (M8010); found at the measure: a pin under
the pointer never told to the page — the card neither opening nor closing (M8011); a click in a mode's capabilities
letting go (M8012), and their Escape (M8013). M7995–M8013, measured by
tests/unit/test_console_sky_card.py, tests/unit/test_console_sky.py and tests/unit/test_console_sky_gestures.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SK_JS = "eregion_console/static/infra_sky.js"
SD_JS = "eregion_console/static/infra_sky_draw.js"
GF_JS = "eregion_console/static/glorfindel.js"

_C = "tests/unit/test_console_sky_card.py::"
_S = "tests/unit/test_console_sky.py::"
_G = "tests/unit/test_console_sky_gestures.py::"

MUTANTS = [
    ("M7995", "a centre of one size whatever the estate (SKY4)", SK_JS,
     "Math.min(1.4, 1 + (25 - (Number(n) || 0)) * 0.02)", "Math.min(1.4, 1)"),
    ("M7996", "a centre without bounds: huge for a tiny estate, a dot for a large one (SKY4)", SK_JS,
     "const scaleFor = n => Math.max(0.8, Math.min(1.4,", "const scaleFor = n => Math.max(0.1, Math.min(9,"),
    ("M7997", "the draw never asks its size: the centre of 25 resources for every estate (SKY4)", SD_JS,
     "    FC = S.size(M.tiles.length);", "    FC = 1;"),
    ("M7998", "the watch's heart left at its old size in a larger centre (SKY4)", SD_JS,
     "    L.core = el('circle', { cx: G.cx, cy: G.cy, r: Math.round(17 * FC),", "    L.core = el('circle', { cx: G.cx, cy: G.cy, r: 17,"),
    ("M7999", "a card that goes over Glorfindel: its disc not weighed (SKY4)", SK_JS,
     "const score = p => into(p) * 1e5 +", "const score = p => 0 +"),
    ("M8000", "a card over what was clicked: its tile hidden by its own card (SKY4)", SK_JS,
     "(covers(p) ? 1e4 : 0)", "0"),
    ("M8001", "a card opened by a hover: it follows the pointer (SKY4)", GF_JS,
     "  const f = InfraSkyDraw.pinned();\n  if (!f) {", "  const f = InfraSkyDraw.focus();\n  if (!f) {"),
    ("M8002", "a card left open, its last tile shown, nothing pinned (SKY4)", GF_JS,
     "    if (!box.hidden) { box.hidden = true; box.replaceChildren(); }\n", ""),
    ("M8003", "a card never placed: at the frame's corner, whatever was clicked (SKY4)", GF_JS,
     "  _skyPlaceCard();\n}\n// SKY4: the card's ✕", "}\n// SKY4: the card's ✕"),
    ("M8004", "a card without its ✕ (SKY4)", GF_JS,
     "const html = _SKY_CARD_X + _skyPanelHtml(f, _skyModelLast)", "const html = _skyPanelHtml(f, _skyModelLast)"),
    ("M8005", "a module's card without its block: the alerts of the modules nowhere in the 360° (SKY4)", GF_JS,
     "${Object.hasOwn(_moduleBlocks, f.m) ? _moduleBlocks[f.m] : ''}", "${''}"),
    ("M8006", "a focus on no module breaking the card (SKY3's known limit; SKY4)", GF_JS,
     "  if (f && f.m && Object.hasOwn(m.backends, f.m)) {", "  if (f && f.m) {"),
    ("M8007", "satellites with nothing to say under their name: the module's block closed, nothing in its place (SKY4)", GF_JS,
     ", err: b.reachable === false, sub: subOf('d', 'nb-' + b.name) })),", ", err: b.reachable === false })),"),
    ("M8008", "a satellite's line said once, never again (SKY4)", SD_JS,
     "const t = subs.get(id) || ''; if (e.textContent !== t) e.textContent = t;", "const t = subs.get(id) || '';"),
    ("M8009", "the card left behind by the bodies that move (SKY4)", SD_JS,
     "    if (moving) { place(); lines(); onPlace(); }", "    if (moving) { place(); lines(); }"),
    ("M8010", "Escape in a field of the card closes it, the note typed lost (SKY3's known limit; SKY4)", GF_JS,
     "  if (t && typeof t.closest === 'function' && t.closest('#sky-panel') && /^(SELECT|INPUT|TEXTAREA)$/.test(t.tagName || '')) return;\n",
     ""),
    ("M8011", "a pin under the pointer never told to the page: the card neither opens nor closes (SKY4, at the measure)", SD_JS,
     "    else if (!same(pinned, pin)) onFocus(focusNow());", ""),
    ("M8012", "a click in a mode's capabilities lets go of the card (SKY3's known limit; SKY4)", GF_JS,
     " || n.id === 'modal' || n.id === 'cap-popover'))) return;", " || n.id === 'modal'))) return;"),
    ("M8013", "Escape in a mode's capabilities closes the card too, not only them (SKY3's known limit; SKY4)", GF_JS,
     "  if (document.getElementById('cap-popover')?.style.display === 'block') return;\n", ""),
]

TESTS = {
    "M7995": f"{_C}test_the_centre_follows_the_estate_between_80_and_140_percent",
    "M7996": f"{_C}test_the_centre_follows_the_estate_between_80_and_140_percent",
    "M7997": f"{_C}test_a_small_estate_gets_a_larger_centre",
    "M7998": f"{_C}test_a_small_estate_gets_a_larger_centre",
    "M7999": f"{_C}test_the_card_keeps_off_glorfindel_and_off_what_was_clicked_all_around_the_sky",
    "M8000": f"{_C}test_the_card_keeps_off_glorfindel_and_off_what_was_clicked_all_around_the_sky",
    "M8001": f"{_S}test_the_panel_is_written_only_when_it_changes_never_under_a_field_and_out_of_reach_writes_nothing",
    "M8002": f"{_S}test_the_panel_is_written_only_when_it_changes_never_under_a_field_and_out_of_reach_writes_nothing",
    "M8003": f"{_S}test_the_panel_is_written_only_when_it_changes_never_under_a_field_and_out_of_reach_writes_nothing",
    "M8004": f"{_S}test_the_panel_is_written_only_when_it_changes_never_under_a_field_and_out_of_reach_writes_nothing",
    "M8005": f"{_C}test_a_module_s_card_holds_its_whole_block_and_a_focus_on_no_module_the_modules",
    "M8006": f"{_C}test_a_module_s_card_holds_its_whole_block_and_a_focus_on_no_module_the_modules",
    "M8007": f"{_S}test_the_page_gives_the_lanes_the_sectors_and_the_backends",
    "M8008": f"{_C}test_each_satellite_says_what_its_block_says_under_its_name",
    "M8009": f"{_C}test_the_page_is_told_where_the_card_goes_as_the_bodies_move",
    "M8010": f"{_G}test_the_page_listens_on_the_whole_document",
    "M8011": f"{_G}test_a_pin_under_the_pointer_is_told_to_the_page",
    "M8012": f"{_G}test_the_page_listens_on_the_whole_document",
    "M8013": f"{_G}test_the_page_listens_on_the_whole_document",
}
