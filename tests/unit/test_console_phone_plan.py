"""DGB1: Dagorlad's Plan tab by the finger, on a phone — the follow of MOB5 (#975).

Measured at 390 × 844 (mobile emulation, the sample) on main: in the Plan tab, every button — the plan's
Request and Clear, Stop all, the drills' Show, Save, Ask Annatar, Import, Load — 17 px high; the drill's
fields in 11 px (Safari on iOS zooms on them at each tap); the plan's table 449 px wide on a screen of 390, a
wire's ✕ beyond its edge (x 431–453), reached only by scrolling the plan sideways. Now, under 760 px: the
buttons 44 px high (MOB5's rule for the verdicts), a table's ✕ 44 × 44 px, the fields in 16 px, a wire on
its own lines — its ✕ at the end of the second, on the screen. Above 760 px nothing changes (measured at
1600 px: 17 px, 11 px, as before). Measured in a headless Chromium (the PR says how); read here in the
page's text.
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
DAG_HTML = (STATIC / "dagorlad.html").read_text(encoding="utf-8")
DAG_JS = (STATIC / "dagorlad.js").read_text(encoding="utf-8")


def _style() -> str:
    return DAG_HTML.split("<style>", 1)[1].split("</style>", 1)[0]


def _phone() -> str:
    """The phone's block — the stylesheet's only media query, and its last."""
    css = _style()
    assert css.count("@media") == 1
    block, tail = css.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)
    assert tail.strip() == ""
    return block


def test_the_plan_tab_s_buttons_44_px_high_stop_all_among_them():
    phone = _phone()
    assert "    #plan button.mini, #drills button.mini, #weekly button.mini { min-height: 44px; padding: 6px 12px; font-size: 13px; }" in phone
    # Stop all, Request, Clear, a drill's Load: all `button.mini` of the three sections the Plan tab shows.
    for action in ("stopAll", "request", "clear", "loadDrill", "saveOpen", "askOpen", "importOpen", "toggleDrills"):
        assert re.search(r'<button type="button" class="mini[^"]*" \$\{_on\(\'click\', \'' + action + r"'", DAG_JS), action
    assert "body[data-m=\"plan\"] #plan { flex: 1; height: auto; min-height: 0; }" in phone


def test_a_table_s_cross_44_by_44_and_the_fields_in_16_px():
    phone = _phone()
    assert "    #plan td button.mini, #drills td button.mini, #weekly td button.mini { min-width: 44px; }" in phone
    assert ("    #plan input, #plan textarea, #plan select, #drills input, #drills textarea, #drills select,\n"
            "    #weekly input, #weekly textarea, #weekly select { font-size: 16px; padding: 8px 10px; }") in phone


def test_a_wire_on_its_own_lines_its_cross_on_the_screen():
    phone = _phone()
    assert "    #plan table.t, #plan table.t tbody { display: block; }" in phone
    assert "    #plan table.t tr { display: flex; flex-wrap: wrap; align-items: center;" in phone
    # What to expect on the second line, the ✕ at its end — never beyond the screen's edge.
    assert "    #plan table.t td.wrap { flex: 1 1 calc(100% - 52px); order: 1; }" in phone
    assert "    #plan table.t td:last-child { order: 2; margin-left: auto; }" in phone
    # The ✕ is the last cell of a wire's row, and of a wire to place.
    assert DAG_JS.count("<td><button type=\"button\" class=\"mini\" ${_on('click', 'unplace', p)}") == 1
    assert "    <td>${k >= 0 && !S.request ? `<button type=\"button\" class=\"mini\" ${_on('click', 'unwire', k)}" in DAG_JS


def test_above_a_phone_nothing_changes():
    css = _style()
    wide = css.split("  @media (max-width: 759px) {\n", 1)[0]
    assert "  button.mini {\n    background: var(--bg2); border: 1px solid var(--border); cursor: pointer;\n    font-size: 10px; padding: 2px 7px; border-radius: 4px;\n  }" in wide
    assert "min-height: 44px" not in wide and "#plan table.t" not in wide
