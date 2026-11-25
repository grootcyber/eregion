"""RTT1b (#1174): a detection-only card titled by its rule, in the console (Jonathan, 25/11, on a mockup).

Three cards « Entra ID identity change » came from `entra-sp-unusual-signin`, a sign-in: nothing was
changed. Their title came from their type (`identity_change`, `control_plane_change`). Jonathan's
decisions: 1 A, the title a rule declares, carried on the card (`rule_title`, RTT1a writes it); 2 A,
the eleven rules (Entra ID and the control plane); 3, English everywhere. The type and its guards do
not change. Absent — a card from before, a rule of the client's own without one —, the family's
neutral title: « Entra ID detection », « Control-plane detection ».

The console's part: the line of TO JUDGE, the tile, the card of JUG1, the window « ×N ». A group (one
action) folds detection-only cards of several rules: it takes the rule's title only when all its cards
share it; else the neutral title and how many rules. Found while measuring: the card of JUG1 and the
window « ×N » named a tile of its own by its key (`plane:control`, `entra:identities`): by its label now.

Measured in a headless Chromium at 1440 × 900 and 390 × 844 (the PR says how); read here in the page's
text: no browser in the suite.
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
INJECTOR = (STATIC / "injector.js").read_text(encoding="utf-8")
API = (Path(__file__).resolve().parents[2] / "eregion_console" / "api.py").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def test_a_detection_only_card_is_titled_by_its_rule_else_by_its_family():
    title = _fn("escTitle")
    rule = "if (_DETECTION_ONLY.has(e.escalation_type)) return _ruleTitle(e) || _ESC_TITLES[e.escalation_type];"
    assert rule in title
    # After the unattributed card's own title (ATT1), before an action's label.
    assert title.index("if (loose) return loose;") < title.index(rule) < title.index("ACTION_LABELS[e.action]")
    assert "const _DETECTION_ONLY = new Set(['control_plane_change', 'identity_change']);" in JS
    assert "  control_plane_change: 'Control-plane detection',   // RTT1" in JS
    assert "  identity_change:      'Entra ID detection',\n" in JS
    for old in ("'Entra ID identity change'", "'Control-plane change'", "identity changed (detection only)",
                "control plane changed (detection only)"):
        assert old not in JS, old


def test_the_rule_s_title_is_read_again_as_the_python_reads_it():
    # glorfindel/rule_title.py, `shown`: a string, not empty, at most 80 characters, on one line, no
    # control or invisible character — else the neutral title; any other type, ''. Never more shown.
    rt = CONSOLE.split("  function ruleTitle(card) {\n", 1)[1].split("\n  }\n", 1)[0]
    assert "if (!card || !Object.hasOwn(CLOUD_NEUTRAL, card.escalation_type)) return '';" in rt
    assert ("if (typeof t !== 'string' || !t.trim() || [...t].length > RULE_TITLE_MAX || "
            "/[\\p{C}\\u2028\\u2029]/u.test(t)) return '';") in rt
    assert "return t.split(/\\s+/).filter(Boolean).join(' ');" in rt
    assert "  const RULE_TITLE_MAX = 80;\n" in CONSOLE
    assert ("  const CLOUD_NEUTRAL = { identity_change: 'Entra ID detection', control_plane_change: "
            "'Control-plane detection' };") in CONSOLE
    assert "return { init, onSections, setJudgeCount, setBreakers, hms, esc, section, ruleTitle, cloudTitle, watchStatus };" in CONSOLE
    # One rule for every page: the page Glorfindel reads the header's.
    assert "function _ruleTitle(e) { return Console.ruleTitle(e); }" in JS


def test_the_tile_says_the_rule_s_title_detection_only():
    said = _fn("_escSaid")
    assert "_DETECTION_ONLY.has(e.escalation_type) && (title === undefined ? _ruleTitle(e) : title)" in said
    assert "return t && t !== _ESC_TITLES[e.escalation_type] ? `${t} (detection only)` : escLabel(e.escalation_type);" in said
    assert "[ttp, pct, sev, rule, _attr(_escSaid(e, title))]" in _fn("_escCtx")
    assert "  control_plane_change: 'control plane, detection only',\n  identity_change:     'Entra ID, detection only',\n" in JS


def test_a_group_takes_the_rule_s_title_only_when_all_its_cards_share_it():
    shared = _fn("_sharedTitle")
    assert "if (!_DETECTION_ONLY.has(e.escalation_type)) return escTitle(e);" in shared
    assert "const shared = _sharedRuleTitle(group);\n  if (shared) return shared;" in shared
    assert "${rules > 1 ? ` · ${rules} rules` : ''}" in shared
    assert "return titles.size === 1 ? [...titles][0] : '';" in _fn("_sharedRuleTitle")
    group = _fn("_renderEscGroup")
    assert "\n    : _sharedTitle(group);\n" in group
    # Its context line: the shared title, or the type — never one card's title for all.
    assert "_escCtx(e, pct, isModeHold || isWriteBlocked || isActionFailed, _sharedRuleTitle(group), _groupRules(group).size > 1)" in group
    # The window « ×N » (JUG3) the same.
    assert "_sharedTitle(members.map(id => _escById[id]))" in _fn("openJudgeGroup")


def test_a_tile_of_its_own_is_named_by_its_label_never_its_key():
    said = _fn("_tileSaid")
    assert "return own ? ((_tiles.get(own) || {}).label || own) : '';" in said
    assert "${_unattributed(e) ? 'not attributed' : (_tileSaid(e) || vmName)}" in _fn("openJudgeCard")
    assert "×${members.length} — ${_tileSaid(e) || String(e.resource_id || '').split('/').pop()}" in _fn("openJudgeGroup")


def test_the_line_of_to_judge_and_the_outcome_take_the_card_s_own_title():
    # TO JUDGE's line and JUG3's outcome lines: each card its own title (escTitle), the rule's when it has one.
    assert "const what = (c.action ? actionLabelVerb(c.action) : escTitle(c)) + target + pct;" in JS
    assert "${c.action ? actionLabelVerb(c.action) : escTitle(c)}${on ? ' — ' + on : ''}" in _fn("_batchLabel")


def test_an_exercise_s_cards_in_runs_carry_and_show_the_rule_s_title():
    assert '"rule_title": esc_module.card_title(e)})' in API          # read again, never the field raw
    assert "<td>${esc(Console.cloudTitle(c) || c.escalation_type)}</td>" in INJECTOR


def test_the_console_and_the_python_read_a_title_alike():
    """The console never shows more than the Python (glorfindel/rule_title.py): the same neutral titles,
    the same bound — in the header's script and in the page's own titles."""
    from glorfindel import rule_title
    neutral = re.search(r"const CLOUD_NEUTRAL = \{ identity_change: '([^']+)', control_plane_change: '([^']+)' \};", CONSOLE)
    assert neutral and {"identity_change": neutral.group(1), "control_plane_change": neutral.group(2)} == rule_title.NEUTRAL
    assert f"  const RULE_TITLE_MAX = {rule_title.MAX_LEN};\n" in CONSOLE
    for etype, title in rule_title.NEUTRAL.items():
        assert re.search(rf"  {etype}: +'{re.escape(title)}',", JS), etype


def test_the_tile_s_window_titles_a_group_as_its_tile_does():
    """The relecture of RTT1b: the tile said « Entra ID detection · 3 rules », its window « Entra ID unusual
    sign-in ×3 » — the first card's. The window now takes the group's title and context as the tile does."""
    win = _fn("showEscModal")
    assert "      : _sharedTitle(group);   // RTT1b: as its tile titles it\n" in win
    assert "_escCtx(e, '', isModeHold || isWriteBlocked || isActionFailed, _sharedRuleTitle(group), _groupRules(group).size > 1)" in win


def test_a_group_counts_only_its_detection_only_cards_rules_and_names_none_for_several():
    rules = _fn("_groupRules")
    assert ("group.filter(x => _DETECTION_ONLY.has(x.escalation_type)).map(x => x.rule_name || _ruleTitle(x))"
            ".filter(Boolean)") in rules
    assert "const rules = _groupRules(group).size;" in _fn("_sharedTitle")
    ctx = _fn("_escCtx")
    assert "function _escCtx(e, pct, lean, title, manyRules) {" in ctx
    assert "e.rule_name && !manyRules ? 'rule ' + _attr(e.rule_name) : ''" in ctx


def test_a_forged_card_type_never_raises_where_a_title_is_read():
    """A store's line written by hand may carry any type: a list is not even a key. The title is read on
    /api/exercises (card_title): it must never raise there."""
    from glorfindel import rule_title
    for etype in (["identity_change"], {"a": 1}, 3, None):
        assert rule_title.shown({"escalation_type": etype, "rule_title": "x"}) == ""
        assert rule_title.for_card("entra-sp-unusual-signin", etype) == ""
    assert rule_title.shown({"escalation_type": "identity_change", "rule_title": None}) == "Entra ID detection"
