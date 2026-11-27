"""SKY3 (#1246): the 360°'s hover and its pin, as Jonathan found them on Imladris (26/11). Each mutant takes a piece
back: a system answering the pointer far beyond its orbit (M7985), a hover that does not wait (M7986), a pending hover
never cancelled, a pointer that passes lighting what it passed (M7987), the sky left with a hover still to come
(M7988), a click elsewhere that does not let go (M7989), a click in the panel that lets go (M7990), Escape that does
not let go (M7991), Escape that lets go under an open window (M7992); the main cause, found after: what the pointer is
on read up to the page, whose <body> carries a data-m of its own (M7993), and for the modules alone (M7994).
M7985–M7994, measured by tests/unit/test_console_sky_gestures.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
SD_JS = "eregion_console/static/infra_sky_draw.js"
GF_JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_sky_gestures.py::"

MUTANTS = [
    ("M7985", "a system answers the pointer on 1.3 times its orbit plus 14 px again (SKY3)", SD_JS,
     "      el('circle', { cx: x, cy: y, r: b.pr + 6, fill: 'transparent' }, g);",
     "      el('circle', { cx: x, cy: y, r: b.pr * 1.3 + 14, fill: 'transparent' }, g);"),
    ("M7986", "a hover that does not wait: the pointer that passes dims everything (SKY3)", SD_JS,
     "    hoverTimer = setTimeout(() => set(h, pin), HOVER_MS);", "    set(h, pin);"),
    ("M7987", "a pending hover never cancelled: what the pointer passed, lit after it (SKY3)", SD_JS,
     "    clearTimeout(hoverTimer);\n    if (same(h, hover)) return;", "    if (same(h, hover)) return;"),
    ("M7988", "the sky left with a hover still to come: lit once the pointer is gone (SKY3)", SD_JS,
     "    svg.addEventListener('mouseleave', () => { clearTimeout(hoverTimer); set(null, pin); });",
     "    svg.addEventListener('mouseleave', () => { set(null, pin); });"),
    ("M7989", "a click elsewhere does not let go: the pin stays (SKY3)", GF_JS,
     "  InfraSkyDraw.unpin();\n}\nfunction _skyEscape(ev) {", "}\nfunction _skyEscape(ev) {"),
    ("M7990", "a click in the panel lets go: its own buttons unpin it (SKY3)", GF_JS,
     "  if (path.some(n => n && (n.id === 'sky-wrap' || n.id === 'modal' || n.id === 'cap-popover'))) return;",
     "  if (path.some(n => n && (n.id === 'modal' || n.id === 'cap-popover'))) return;"),
    ("M7991", "Escape does not let go (SKY3)", GF_JS,
     "  InfraSkyDraw.unpin();\n}\n// The whole document listens", "}\n// The whole document listens"),
    ("M7992", "Escape lets go under an open window, whose Escape is its own (SKY3)", GF_JS,
     "  if (document.getElementById('modal')?.classList.contains('open')) return;\n  // SKY4: a mode's",
     "  // SKY4: a mode's"),
    ("M7993", "what the pointer is on read up to the page: an empty spot of the sky takes the <body>'s data-m for a module (SKY3)", SD_JS,
     "    const up = sel => { const x = e.closest(sel); return x && svg && svg.contains(x) ? x : null; };",
     "    const up = sel => e.closest(sel);"),
    ("M7994", "a module read up to the page: the <body>'s data-m, the phone's tab, taken for one (SKY3)", SD_JS,
     "const a = up('[data-a]'), s = up('[data-s]'), b = up('[data-b]'), m = up('[data-m]');",
     "const a = up('[data-a]'), s = up('[data-s]'), b = up('[data-b]'), m = e.closest('[data-m]');"),
]

TESTS = {
    "M7985": f"{_T}test_a_system_answers_the_pointer_on_its_orbit_only",
    "M7986": f"{_T}test_a_hover_waits_a_moment_before_it_dims_the_rest",
    "M7987": f"{_T}test_a_pointer_that_only_passes_lights_nothing",
    "M7988": f"{_T}test_a_pointer_that_only_passes_lights_nothing",
    "M7989": f"{_T}test_a_click_elsewhere_lets_go_never_one_in_the_sky_its_panel_or_a_window",
    "M7990": f"{_T}test_a_click_elsewhere_lets_go_never_one_in_the_sky_its_panel_or_a_window",
    "M7991": f"{_T}test_escape_lets_go_unless_a_window_is_open",
    "M7992": f"{_T}test_escape_lets_go_unless_a_window_is_open",
    "M7993": f"{_T}test_an_empty_spot_of_the_sky_lights_nothing_whatever_the_page_carries",
    "M7994": f"{_T}test_an_empty_spot_of_the_sky_lights_nothing_whatever_the_page_carries",
}
