"""MOB4 (#972): the Glorfindel page on a phone — one section at a time, under 760 px.

Jonathan's decision of 20/11, on a mockup (option A): under 760 px, three tabs under the header —
To judge, Infra, Feed —, one section shown at a time with its own scroll; by default To judge when
cards wait, else the infra, until the operator picks a tab. The infra's modules stacked, its cards
one under the other, without the edges; the console's header on one or two lines. Above 760 px
nothing changes. Measured: at 390 px the left column (TO JUDGE and LIVE FEED) took the screen, its
width fixed at 390 px, the infra had 0 px, the header ran off the right edge.

Measured in a headless Chromium in mobile emulation at 390 × 844 and at 1440 × 900 (the PR says
how); read here in the page's text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
CSS = (STATIC / "console.css").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]
PHONE = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0] if "  @media (max-width: 759px) {\n" in STYLE else ""


def body(head: str) -> str:
    assert head in JS, head
    return JS.split(head, 1)[1].split("\n}\n", 1)[0]


def test_three_tabs_under_the_header_each_naming_its_section():
    bar = HTML.split('<nav id="m-tabs" role="tablist" aria-label="Sections">', 1)[1].split("</nav>", 1)[0]
    for tab in ("judge", "infra", "feed"):
        assert (f'<button type="button" role="tab" id="m-tab-{tab}" aria-selected="false" data-on-click="mobileTab" '
                f"data-click-args='[\"{tab}\"]'>") in bar, tab
    assert '<span id="m-judge-badge" class="m-badge" hidden></span>' in bar
    assert HTML.index('<nav id="m-tabs"') < HTML.index("<main>")
    # The sections the tabs show, named.
    assert '<div class="col-header" id="judge-head">TO JUDGE' in HTML
    assert '<div class="col-header" id="feed-head">LIVE FEED' in HTML


def test_nothing_changes_above_760_px():
    # One rule outside the phone's block: the bar hidden. The block is the stylesheet's last: a media
    # query adds no weight, so a base rule written after it would win (#feed-col's 390 px).
    assert "  #m-tabs { display: none; }\n  @media (max-width: 759px) {\n" in STYLE
    assert STYLE.count("@media") == 1 and PHONE
    assert STYLE.rstrip().endswith("}\n  }") or STYLE.rstrip().endswith("}")
    assert STYLE.index("@media (max-width: 759px)") > STYLE.index("  #feed-col {\n    width: 390px;")
    assert STYLE.index("@media (max-width: 759px)") > STYLE.index("  .node-asset {\n")
    tail = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[1]
    assert tail.strip() == "", tail[:200]


def test_one_section_at_a_time_its_own_scroll():
    assert "    #feed-col { width: auto; flex: 1; min-height: 0; border-right: 0; }" in PHONE
    assert ('    body[data-m="judge"] #incidents-col, body[data-m="feed"] #incidents-col, '
            'body[data-m="infra"] #feed-col { display: none; }') in PHONE
    assert ('    body[data-m="judge"] #feed-head, body[data-m="judge"] #feed-list,\n'
            '    body[data-m="feed"] #judge-head, body[data-m="feed"] #judge-list { display: none; }') in PHONE
    assert '    body[data-m="judge"] #judge-list { max-height: none; flex: 1; border-bottom: 0; }' in PHONE


def test_the_infra_on_a_phone_stacked_without_its_edges():
    assert "    .topo-svg { display: none; }" in PHONE
    assert "    .topo-modules { flex-direction: column; align-items: stretch; }" in PHONE
    assert "    .node-asset, .node-asset-empty { flex: 1 1 100%; max-width: none; min-width: 0; }" in PHONE
    assert "    .modal { min-width: 0; width: calc(100vw - 24px); }" in PHONE


def test_the_default_tab_then_the_operators_pick():
    show = body("function _showMobileTab() {")
    assert "const tab = _configMode ? 'infra' : (_mobileTab || (_toJudge.length ? 'judge' : 'infra'));" in show
    assert "document.body.dataset.m = tab;" in show
    # ARIA by its property: setAttribute is refused in the console's pages (#254).
    assert "if (b) b.ariaSelected = String(t === tab);" in show and "setAttribute" not in show
    assert "badge.textContent = _toJudge.length ? String(Number(_toJudge.length)) : ''; badge.hidden = !_toJudge.length;" in show
    pick = body("function mobileTab(which) {")
    assert pick.lstrip().startswith("if (!_MOBILE_TABS.includes(which)) return;")
    assert "const _MOBILE_TABS = ['judge', 'infra', 'feed'];" in JS
    actions = JS.split("const ACTIONS = {", 1)[1].split("\n};\n", 1)[0]
    assert re.search(r"^  mobileTab,", actions, re.M)


def test_the_tab_follows_the_cards_the_configuration_and_the_first_render():
    assert "  _showMobileTab();                              // the phone's default tab and its badge (MOB4)\n" in body("function renderToJudge() {")
    assert "  _showMobileTab();                // a phone shows the configuration" in body("function toggleConfig() {")
    init = JS.split("(async function init() {", 1)[1]
    assert init.lstrip().startswith("_showMobileTab();")


def test_the_header_on_one_or_two_lines_on_a_phone():
    block = CSS.split("@media (max-width: 759px) {", 1)[1].split("\n}\n", 1)[0]
    assert "  header.console { flex-wrap: wrap; gap: 4px 10px; padding: 6px 10px; }" in block
    assert "  header.console .ver, header.console .sep, header.console .spacer, header.console #c-clock { display: none; }" in block
    assert CSS.count("@media") == 1


def test_the_console_role_says_the_phone():
    role = (ROOT / "CLAUDE_CONSOLE.md").read_text(encoding="utf-8")
    assert "Mobile = non-prioritaire" not in role
    assert "Sous 760 px (un téléphone)" in role
