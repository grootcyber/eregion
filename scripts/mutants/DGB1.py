"""DGB1: Dagorlad's Plan tab by the finger, on a phone (the follow of MOB5, #975). Each mutant takes a piece
back: the buttons 17 px high again (M7706), the plan's own — Stop all, Request, Clear — left out (M7707), a
table's ✕ narrow again (M7708), the fields under 16 px, zoomed by Safari at each tap (M7709), the plan's table
wider than the phone, a wire's ✕ beyond its edge (M7710). M7706–M7710, measured by
tests/unit/test_console_phone_plan.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
DAG_HTML = "eregion_console/static/dagorlad.html"

_T = "tests/unit/test_console_phone_plan.py::"

MUTANTS = [
    ("M7706", "the Plan tab's buttons 17 px high again on a phone (DGB1)", DAG_HTML,
     "#weekly button.mini { min-height: 44px; padding: 6px 12px; font-size: 13px; }",
     "#weekly button.mini { padding: 6px 12px; font-size: 13px; }"),
    ("M7707", "the plan's own buttons left out — Stop all, Request, Clear 17 px high (DGB1)", DAG_HTML,
     "    #plan button.mini, #drills button.mini, #weekly button.mini { min-height: 44px;",
     "    #drills button.mini, #weekly button.mini { min-height: 44px;"),
    ("M7708", "a table's ✕ narrow again on a phone (DGB1)", DAG_HTML,
     "    #plan td button.mini, #drills td button.mini, #weekly td button.mini { min-width: 44px; }\n", ""),
    ("M7709", "the fields under 16 px: Safari on iOS zooms on them at each tap (DGB1)", DAG_HTML,
     "#weekly select { font-size: 16px; padding: 8px 10px; }", "#weekly select { font-size: 11px; padding: 8px 10px; }"),
    ("M7710", "the plan's table wider than the phone again, a wire's ✕ beyond its edge (DGB1)", DAG_HTML,
     "    #plan table.t tr { display: flex; flex-wrap: wrap; align-items: center;",
     "    #plan table.t tr { flex-wrap: wrap; align-items: center;"),
]

TESTS = {
    "M7706": f"{_T}test_the_plan_tab_s_buttons_44_px_high_stop_all_among_them",
    "M7707": f"{_T}test_the_plan_tab_s_buttons_44_px_high_stop_all_among_them",
    "M7708": f"{_T}test_a_table_s_cross_44_by_44_and_the_fields_in_16_px",
    "M7709": f"{_T}test_a_table_s_cross_44_by_44_and_the_fields_in_16_px",
    "M7710": f"{_T}test_a_wire_on_its_own_lines_its_cross_on_the_screen",
}
