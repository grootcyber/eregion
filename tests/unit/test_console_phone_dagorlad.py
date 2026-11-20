"""MOB5 (#975): Overview and Dagorlad on a phone — the follow of MOB4 (the Glorfindel page).

Jonathan's decisions of 20/11, on a mockup. Measured at 390 × 844 (mobile emulation, the sample):
on main the three pages were zoomed out to 908 px; with MOB4's header Overview fits already, but
Dagorlad's board (a grid of 360 px | 1fr | 380 px) ran to 920 px and its Runs view's columns
(the windows, the campaigns at 1 px each, the matrix at 500 px) to 724 px.
- The board, under 760 px: three tabs, Red, Targets, Plan. The gesture is the board's own — a tap on
  a red card (pick), then on a target (aim): a red card picked opens Targets under a banner that
  names it, a wire laid opens the plan, its badge the wires' count. The drag's handle and the wires
  drawn between the columns are left out; the plan lists the wires.
- The Runs view, under 760 px: three tabs, Windows, Campaigns, Coverage (a link to a campaign opens
  its tab), the matrix's rows folded on two lines.
- Overview: nothing to change; its CSS holds no fixed width beyond a phone's.
Above 760 px nothing changes. Measured in a headless Chromium (the PR says how); read here in the
pages' text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
DAG_HTML = (STATIC / "dagorlad.html").read_text(encoding="utf-8")
DAG_JS = (STATIC / "dagorlad.js").read_text(encoding="utf-8")
RUN_HTML = (STATIC / "injector.html").read_text(encoding="utf-8")
RUN_JS = (STATIC / "injector.js").read_text(encoding="utf-8")
OV_HTML = (STATIC / "overview.html").read_text(encoding="utf-8")


def style(html: str) -> str:
    return html.split("<style>", 1)[1].split("</style>", 1)[0]


def phone(html: str) -> str:
    """The phone's block, and what follows it in the stylesheet (nothing, it is the last)."""
    css = style(html)
    assert css.count("@media") == 1, "one media query, the phone's"
    block, tail = css.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)
    assert tail.strip() == "", tail[:200]
    return block


def body(js: str, head: str) -> str:
    assert head in js, head
    return js.split(head, 1)[1].split("\n}\n", 1)[0]


# ── The board ─────────────────────────────────────────────────────────────────────────

def test_the_board_has_three_tabs_red_targets_plan():
    bar = DAG_HTML.split('<nav id="m-tabs" role="tablist" aria-label="The board\'s columns">', 1)[1].split("</nav>", 1)[0]
    for tab, label in (("red", "Red"), ("blue", "Targets"), ("plan", "Plan")):
        assert (f'<button type="button" role="tab" id="m-tab-{tab}" aria-selected="false" data-on-click="mobileTab" '
                f"data-click-args='[\"{tab}\"]'>{label}") in bar, tab
    assert '<span id="m-plan-badge" class="m-badge" hidden></span>' in bar
    assert '<div id="m-picked" hidden></div>' in DAG_HTML
    assert DAG_HTML.index('<nav id="m-tabs"') < DAG_HTML.index('<main id="board">')


def test_the_board_on_a_phone_one_column_at_a_time_without_the_wires():
    css, block = style(DAG_HTML), phone(DAG_HTML)
    assert "  #m-tabs, #m-picked { display: none; }\n  @media (max-width: 759px) {\n" in css
    assert "    #col-mid, #wires, #pills, .handle { display: none; }" in block
    assert '    body[data-m="red"] #col-blue, body[data-m="blue"] #col-red, body[data-m="plan"] #board { display: none; }' in block
    assert ('    body[data-m="red"] #weekly, body[data-m="red"] #drills, body[data-m="red"] #plan,\n'
            '    body[data-m="blue"] #weekly, body[data-m="blue"] #drills, body[data-m="blue"] #plan { display: none; }') in block
    assert '    body[data-m="plan"] #plan { flex: 1; height: auto; min-height: 0; }' in block
    assert "    body { height: 100dvh; }" in block
    assert "    #m-picked:not([hidden]) { display: block;" in block


def test_a_tap_on_a_red_card_opens_the_targets_a_tap_on_a_target_the_plan():
    assert "const _PHONE = window.matchMedia('(max-width: 759px)');" in DAG_JS
    actions = DAG_JS.split("const ACTIONS = {", 1)[1].split("\n};\n", 1)[0]
    pick = actions.split("  pick(i) {", 1)[1].split("\n  },\n", 1)[0]
    assert "    if (_PHONE.matches && S.picked !== null) S.mobileTab = 'blue';" in pick
    aim = actions.split("  aim(j) {", 1)[1].split("\n  },\n", 1)[0]
    assert aim.index("addWire(r.id, t.resource_id, t.name);") < aim.index("    if (_PHONE.matches) S.mobileTab = 'plan';")
    tab = actions.split("  mobileTab(which) {", 1)[1].split("\n  },\n", 1)[0]
    assert tab.lstrip().startswith("if (!_MOBILE_TABS.includes(which)) return;")
    assert "const _MOBILE_TABS = ['red', 'blue', 'plan'];" in DAG_JS


def test_the_tabs_the_badge_and_the_banner_follow_the_board():
    show = body(DAG_JS, "function _showMobileTab() {")
    assert "const tab = _MOBILE_TABS.includes(S.mobileTab) ? S.mobileTab : 'red';" in show
    assert "if (b) b.ariaSelected = String(t === tab);" in show and "setAttribute" not in show
    assert "badge.textContent = n ? String(Number(n)) : ''; badge.hidden = !n;" in show
    assert "bar.textContent = r ? `${r.id} picked — tap a target` : ''; bar.hidden = !(r && tab === 'blue');" in show
    for head in ("function renderBoard() {", "function renderPlan() {"):
        assert body(DAG_JS, head).rstrip().endswith("_showMobileTab();                              // a phone's tabs, badge and banner (MOB5)")
    assert "  _showMobileTab();          // a phone: the red column until the board is read (MOB5)\n  loadBoard()" in DAG_JS


# ── The Runs view ─────────────────────────────────────────────────────────────────────

def test_the_runs_view_has_three_tabs_windows_campaigns_coverage():
    bar = RUN_HTML.split('<nav id="m-tabs" role="tablist" aria-label="The runs\' columns">', 1)[1].split("</nav>", 1)[0]
    for tab, label in (("ex", "Windows"), ("camp", "Campaigns"), ("side", "Coverage")):
        assert f'<button type="button" role="tab" id="m-tab-{tab}" aria-selected="false" data-mtab="{tab}">{label}</button>' in bar
    assert RUN_HTML.index('<nav id="m-tabs"') < RUN_HTML.index('<main id="main">')


def test_the_runs_view_on_a_phone_one_column_and_the_matrix_folded():
    css, block = style(RUN_HTML), phone(RUN_HTML)
    assert "  #m-tabs { display: none; }\n  @media (max-width: 759px) {\n" in css
    assert ('    body[data-m="ex"] #col-camp, body[data-m="ex"] #col-side, body[data-m="camp"] #col-ex,\n'
            '    body[data-m="camp"] #col-side, body[data-m="side"] #col-ex, body[data-m="side"] #col-camp { display: none; }') in block
    assert "    #col-side { width: auto; }" in block
    assert "    .cat { grid-template-columns: 12px 78px minmax(0, 1fr); }" in block
    assert "    .cat .hist { grid-column: 2; }\n    .cat .last { grid-column: 3; text-align: left; }" in block


def test_a_tap_on_a_runs_tab_one_of_three_never_another():
    assert "const _MOBILE_TABS = ['ex', 'camp', 'side'];" in RUN_JS
    # A link to a campaign opens its tab; else the windows.
    assert "let _mobileTab = S.focus && S.focus.startsWith('c:') ? 'camp' : 'ex';" in RUN_JS
    assert "  const t = ev.target.closest('[data-toggle],[data-delivered],[data-report],[data-mtab]');" in RUN_JS
    assert "    if (_MOBILE_TABS.includes(t.dataset.mtab)) { _mobileTab = t.dataset.mtab; _showMobileTab(); }" in RUN_JS
    show = body(RUN_JS, "function _showMobileTab() {")
    assert "if (b) b.ariaSelected = String(t === _mobileTab);" in show and "setAttribute" not in show


# ── Overview ──────────────────────────────────────────────────────────────────────────

def test_overview_holds_no_fixed_width_beyond_a_phone():
    # Measured at 390 px with MOB4's header: nothing beyond the screen. Kept so: no width, minimum
    # width or grid track fixed over 360 px in its stylesheet.
    css = style(OV_HTML)
    # A maximum width is no constraint on a phone: only a width or a minimum one.
    widths = [int(w) for w in re.findall(r"(?<![\w-])(?:min-)?width:\s*(\d+)px", css)]
    tracks = [int(w) for w in re.findall(r"minmax\((\d+)px", css)] + [int(w) for w in re.findall(r"grid-template-columns:\s*(\d+)px", css)]
    assert widths + tracks and max(widths + tracks) <= 360, sorted(widths + tracks)[-3:]
