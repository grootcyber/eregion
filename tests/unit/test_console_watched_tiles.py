"""IDT1 (#1182): Entra ID and the control plane on the map as a VM is (Jonathan, 25/11, on a mockup).

Their tile only came with a card: purple, then gone — its absence said nothing (watched and calm, or not
watched at all?). Now always there while their rules run (a rule of their source, enabled and bound to
a backend), first in the row, linked to DETECT only. Their health by their dot: red, a poll in error;
grey, no log for the watch's `silent_after_hours` (LOGF1, `log_freshness` in /api/watch/status) — never
a threshold of the page's; green otherwise. A watch before LOGF1: green or red, never grey. Unfolded, as
a VM's identity block (VMI1): where it is read, its logs' age, its rules, what is set aside (MID1).

Measured in a headless Chromium at 1600 × 1000 and 390 × 844 (the PR says how). The structure is read
in the page's text; the health rule (which table greys the tile, which one it names, a table put off by
the watch's budget) is run: the page's own functions in Node or a headless Chromium (tests/unit/js_engine.py),
on scenarios of `log_freshness` — the relecture of IDT1 found a text that a reversed sort left intact.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    m = re.search(r"\n(?:async )?function " + re.escape(name) + r"\(", JS)
    assert m, name
    return JS[m.start():].split("\n}\n", 1)[0]


def test_always_there_while_their_rules_run_first_in_the_row():
    watched = JS.split("const _WATCHED = {\n", 1)[1].split("\n};\n", 1)[0]
    assert "identity:      { tile: 'entra:identities', label: 'Entra ID — identities', source: 'azure_entra'," in watched
    assert "control_plane: { tile: 'plane:control', label: 'the control plane', source: 'azure_activity'," in watched
    assert "filter(r => r.source === w.source && r.enabled !== false)" in _fn("_watchedRules")
    # Bound to a backend: an unbound rule reads nothing.
    assert "return _watchedRules(kind).some(r => r.monitoring_backend_name); }" in JS
    render = _fn("_tileMap")                                 # TRID1: the map built apart
    assert "    if (!resourceMap.has(w.tile) && _isWatched(kind))\n" in render
    assert "resourceMap.set(w.tile, { resource_id: w.resource_id, vm_name: w.tile, label: w.label, states: [], kind });" in render
    assert "  resourceMap.clear(); _watchedFirst.forEach(([key, r]) => resourceMap.set(key, r));\n" in render


def test_its_health_a_poll_in_error_first_then_its_logs():
    health = _fn("_watchedHealth")
    # Its logs read before any early return: the block says them whatever the dot (review of IDT1, 1).
    assert health.index("const logs = _watchedLogs(kind, lf);") < health.index("if (failing) return")
    assert "  const failing = bound.find(r => r.last_error);\n  if (failing) return { state: 'error'," in health
    assert "  if (!logs) return { state: 'ok', said: '', logs: null, readAt };" in health
    assert health.index("if (failed) return { state: 'error'") < health.index("const silent =")


def test_the_grey_is_the_watch_s_threshold_never_the_page_s():
    health = _fn("_watchedHealth")
    assert "  const hours = Number(lf.silent_after_hours);\n" in health
    assert "LOG_SILENT" not in JS and not re.search(r"silent_after_hours\s*\|\|\s*\d", JS)


def test_the_dot_says_the_health_before_the_cards():
    node = _fn("_renderNsgNode")
    assert "const watched = Object.hasOwn(_WATCHED, resource.kind || '') && _isWatched(resource.kind);" in node
    assert ("const dotColor = health && health.state === 'error' ? 'var(--red)' : health && health.state === 'silent' ? 'var(--dim)'\n"
            "    : judgeOnly ? 'var(--blue)' : myEscs.length ? 'var(--purple)' : 'var(--green)';") in node
    assert "${watched ? `<div style=\"margin-top:4px;overflow-wrap:anywhere\">${_watchedLine(resource.kind, health)}</div>` : ''}" in node
    assert "${isExpanded && watched ? _watchedBlock(resource.kind, health) : ''}" in node


def test_folded_short_unfolded_whole():
    line = _fn("_watchedLine")
    assert "title=\"${_attr(health.said)}\">${health.state === 'error' ? '✗' : '⚠'} ${_attr(health.short)}</span>" in line
    block = _fn("_watchedBlock")
    for said in ("not read by this watch (a watch before LOGF1)", "'none in the window read'", "'bound to no backend'",
                 "'not read yet'", "`${Number(msi)} (Azure's own, MID1)`"):
        assert said in block, said
    assert "<span class=\"vm-id-h\">LOGS</span>${logs}" in block and "<span class=\"vm-id-h\">RULES</span>${rows}" in block


def test_the_page_reads_the_watch_s_status_the_header_holds():
    assert "      lastWatch = w;                      // IDT1" in CONSOLE
    assert "  function watchStatus() { return lastWatch; }\n" in CONSOLE
    assert "ruleTitle, cloudTitle, watchStatus };" in CONSOLE
    assert "const lf = Console.watchStatus()?.log_freshness;" in _fn("_watchedHealth")


def test_the_legend_says_a_watched_tile_s_grey_and_red():
    assert ("${dot('var(--dim)', 'unverifiable · maybe off · logs silent')}"
            "${dot('var(--red)', \"a rule or its logs' read in error (Entra ID, control plane)\")}") in _fn("_legend")
    assert "  .vm-id.watched { grid-template-columns: minmax(0, 1fr); row-gap: 0; }" in HTML
    # A token without a break (a URL in a rule's error) wraps inside the tile, folded and unfolded.
    assert "margin-top: 4px; overflow-wrap: anywhere; }" in HTML
    assert '`<div style="margin-top:4px;overflow-wrap:anywhere">${_watchedLine(resource.kind, health)}</div>`' in JS


def test_a_read_that_hangs_is_never_kept_green():
    """The relecture of LOGF1: a read of the logs that hangs stops moving `read_at` — what it said is no
    longer known. Past twice the watch's reading period, the tile says it, grey: never a stale green."""
    health = _fn("_watchedHealth")
    assert "const _LOGS_READ_STALE_MS = 2 * 15 * 60e3;" in JS
    assert "if (Number.isFinite(read) && Date.now() - read > _LOGS_READ_STALE_MS)" in health
    assert health.index("_LOGS_READ_STALE_MS)") < health.index("const failed = logs.find(")


# ── The health rule, run (the relecture of IDT1) ───────────────────────────────────────────────────────
# The page's own functions, a harness around them: each scenario a `log_freshness` (ages in hours, `null`
# for no log in the window), the rules of the sample. What comes back: the state, the short reason, the
# folded line and the unfolded block as text.

_TAKEN = ("_ZONED", "_relTime", "_attr", "_ENTRA_TABLES", "_WATCHED", "_watchedRules", "_LOGS_READ_STALE_MS",
          "_isWatched", "_ageSaid", "_watchedLogs", "_logAt", "_silentLogs", "_watchedHealth", "_watchedLine",
          "_watchedBlock")
_RULES = [{"name": "entra-a", "source": "azure_entra", "enabled": True, "monitoring_backend_name": "law",
           "title": "Credential added to <y>"},
          {"name": "activity-a", "source": "azure_activity", "enabled": True, "monitoring_backend_name": "law"}]
_DEFERRED = "not read: the watch's Log Analytics budget is held (DOS4), read again the next minute"
_SCENARIOS = {
    # Jonathan, 25/11: a fresh table never hides a silent one — the tile greys, and names the silent one.
    "fresh_and_silent": {"tables": {"AuditLogs": {"last_h": 1}, "SigninLogs": {"last_h": 30}}},
    # Several silent: the one silent the longest is named; none in the window is older than any.
    "two_silent_dated": {"tables": {"AuditLogs": {"last_h": 30}, "SigninLogs": {"last_h": 50}}},
    "three_silent_one_empty": {"tables": {"AuditLogs": {"last_h": 30}, "SigninLogs": {"last_h": 50},
                                          "AADServicePrincipalSignInLogs": {"last_h": None}}},
    "all_fresh": {"tables": {"AuditLogs": {"last_h": 1}, "SigninLogs": {"last_h": 3}}},
    "none_in_window": {"tables": {"AuditLogs": {"last_h": None}}},
    "threshold_6": {"hours": 6, "tables": {"AuditLogs": {"last_h": 9}}},
    "threshold_24": {"tables": {"AuditLogs": {"last_h": 9}}},
    # Its plane (LOGF1b): a table of another plane never greys it; one of its plane, whatever its name, does.
    "plane_other": {"tables": {"Perf": {"last_h": 50, "plane": "data"}, "AuditLogs": {"last_h": 1, "plane": "identity"}}},
    "plane_named": {"tables": {"AuditLogs": {"last_h": 1, "plane": "identity"},
                               "EntraCustomLogs": {"last_h": 40, "plane": "identity"}}},
    # A watch before LOGF1b: Entra's five tables by name, never another.
    "by_name": {"tables": {"AuditLogs": {"last_h": 1}, "AADManagedIdentitySignInLogs": {"last_h": 40}}},
    "by_name_other": {"tables": {"AuditLogs": {"last_h": 1}, "Perf": {"last_h": 40}}},
    "control_silent": {"kind": "control_plane", "tables": {"AzureActivity": {"last_h": 30}, "AuditLogs": {"last_h": 1}}},
    "control_ignores_entra": {"kind": "control_plane", "tables": {"AzureActivity": {"last_h": 1}, "SigninLogs": {"last_h": 40}}},
    # Put off by the budget: never a read in error; its last log judged; never read yet, neither red nor grey.
    "deferred_fresh": {"tables": {"AuditLogs": {"last_h": 1, "deferred": True, "error": _DEFERRED}}},
    "deferred_never_read": {"tables": {"AuditLogs": {"last_h": None, "deferred": True, "error": _DEFERRED},
                                       "SigninLogs": {"last_h": 1}}},
    "deferred_old": {"tables": {"AuditLogs": {"last_h": 30, "deferred": True, "error": _DEFERRED}}},
    "read_error": {"tables": {"AuditLogs": {"last_h": 1}, "SigninLogs": {"last_h": None, "error": "HTTP 403 forbidden"}}},
    "rule_error": {"rules": [{**_RULES[0], "last_error": "HTTP 403 forbidden"}],
                   "tables": {"AuditLogs": {"last_h": 1}}},
    "read_hangs": {"read_min": 40, "tables": {"AuditLogs": {"last_h": 1}}},
    "no_field": {"field": False},
    # Not of the field's form: left out, never read as silent.
    "malformed": {"tables": {"AuditLogs": {"last_h": 1}, "SigninLogs": {"error": None},
                             "AADServicePrincipalSignInLogs": "x"}},
    "escaped": {"tables": {"<x>": {"last_h": 40, "plane": "identity"}}},
    # LOGF2: a table of Entra judged by the watch on Graph — its verdict followed, never the page's 24 h.
    "entra_calm": {"tables": {"AuditLogs": {"last_h": 30, "plane": "identity", "judged": "entra",
                                            "silent": False, "entra_h": 31}}},
    "entra_lost": {"tables": {"AuditLogs": {"last_h": 30, "plane": "identity", "judged": "entra",
                                            "silent": True, "entra_h": 2}}},
    "graph_unread": {"tables": {"AuditLogs": {"last_h": 30, "plane": "identity", "judged": "fallback",
                                              "silent": False, "threshold_hours": 168,
                                              "graph_error": "no right on Graph (HTTP 403 Authorization_RequestDenied)"}}},
    "graph_unread_silent": {"tables": {"AuditLogs": {"last_h": None, "plane": "identity", "judged": "fallback",
                                                     "silent": True, "threshold_hours": 168,
                                                     "graph_error": "Graph did not answer in time"}}},
}
_HARNESS = r"""
let _cfgData = null, WS = null;
const Console = { watchStatus: () => WS };
const iso = h => new Date(Date.now() - h * 3600e3).toISOString();
const out = {};
for (const [name, sc] of Object.entries(SCENARIOS)) {
  _cfgData = { detection: { rules: sc.rules || RULES }, azure: { tenant_id: 'abcd…1234', subscription_id: 'efgh…5678' } };
  if (sc.field === false) WS = { status: 'running' };
  else {
    const tables = {};
    for (const [t, e] of Object.entries(sc.tables)) {
      if (!e || typeof e !== 'object' || !Object.hasOwn(e, 'last_h')) { tables[t] = e; continue; }
      const { last_h, entra_h, ...rest } = e;
      tables[t] = { error: null, ...rest, last: last_h === null ? null : iso(last_h),
                    ...(entra_h === undefined ? {} : { entra_last: iso(entra_h) }) };
    }
    WS = { status: 'running', log_freshness: { read_at: iso((sc.read_min ?? 1) / 60), silent_after_hours: sc.hours ?? 24, tables } };
  }
  const kind = sc.kind || 'identity';
  const h = _watchedHealth(kind);
  out[name] = { state: h.state, short: h.short || '', said: h.said || '', line: _watchedLine(kind, h), block: _watchedBlock(kind, h) };
}
emit(JSON.stringify(out));
"""


def _text(markup: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup))).strip()


@pytest.fixture(scope="module")
def ran() -> dict:
    script = (js_engine.take(JS, *_TAKEN) + f"const RULES = {json.dumps(_RULES)};\n"
              + f"const SCENARIOS = {json.dumps(_SCENARIOS)};\n" + _HARNESS)
    return json.loads(js_engine.run(script))


def test_a_fresh_table_never_hides_a_silent_one(ran):
    """Jonathan, 25/11: grey as soon as one of its tables is silent — the watch's card opens for it."""
    r = ran["fresh_and_silent"]
    assert r["state"] == "silent" and r["short"] == "SigninLogs: its last log 30h ago", r
    assert "SigninLogs silent" in r["said"] and "does the tenant's diagnostic setting still send it?" in r["said"]
    assert ran["all_fresh"]["state"] == "ok"
    # Calm: the folded line shows its oldest log, never its newest.
    assert _text(ran["all_fresh"]["line"]) == "1 rule · logs 3h ago", ran["all_fresh"]["line"]


def test_the_table_named_is_the_one_silent_the_longest(ran):
    assert ran["two_silent_dated"]["short"] == "SigninLogs: its last log 50h ago", ran["two_silent_dated"]
    r = ran["three_silent_one_empty"]
    assert r["short"] == "AADServicePrincipalSignInLogs: no log for 24 h or more", r
    assert "(and 2 more tables)" in r["said"], r


def test_none_in_the_window_is_silent_and_the_threshold_is_the_watch_s(ran):
    assert ran["none_in_window"]["state"] == "silent", ran["none_in_window"]
    assert ran["none_in_window"]["short"] == "AuditLogs: no log for 24 h or more"
    assert ran["threshold_6"]["state"] == "silent" and ran["threshold_24"]["state"] == "ok"


def test_its_tables_are_its_plane_s(ran):
    """LOGF1b's `plane`: a table of another plane never greys the tile, one of its plane does whatever its
    name; from a watch before it, the five tables of Entra ID by name, AzureActivity for the control plane."""
    assert ran["plane_other"]["state"] == "ok", ran["plane_other"]
    assert ran["plane_named"]["short"] == "EntraCustomLogs: its last log 40h ago", ran["plane_named"]
    assert ran["by_name"]["short"] == "AADManagedIdentitySignInLogs: its last log 40h ago", ran["by_name"]
    assert ran["by_name_other"]["state"] == "ok", ran["by_name_other"]
    assert ran["control_silent"]["short"] == "AzureActivity: its last log 30h ago", ran["control_silent"]
    assert ran["control_ignores_entra"]["state"] == "ok", ran["control_ignores_entra"]


def test_a_table_put_off_by_the_budget_is_no_read_in_error(ran):
    assert ran["deferred_fresh"]["state"] == "ok", ran["deferred_fresh"]
    r = ran["deferred_never_read"]
    assert r["state"] == "ok" and "AuditLogs not read yet" in _text(r["block"]), r
    assert ran["deferred_old"]["short"] == "AuditLogs: its last log 30h ago", ran["deferred_old"]


def test_a_table_judged_by_entra_follows_the_watch_s_verdict_and_says_both_dates(ran):
    """LOGF2: a calm tenant never greys the tile, its 30 h of silence past the page's 24 h; an event of Entra
    not received does, named; the block says the workspace's last log next to Entra's last event."""
    calm = ran["entra_calm"]
    assert calm["state"] == "ok", calm
    assert "AuditLogs 30h ago · Entra ID 31h ago" in _text(calm["block"]), calm["block"]
    lost = ran["entra_lost"]
    assert lost["state"] == "silent" and lost["short"] == "AuditLogs: Entra ID's last event 2h ago, not received", lost
    assert "AuditLogs 30h ago · Entra ID 2h ago" in _text(lost["block"])


def test_graph_unread_the_tile_says_its_fallback_to_7_days(ran):
    """LOGF2: without the right (a 403), or Graph unreadable — « Graph unread: … threshold 7 days »."""
    r = ran["graph_unread"]
    assert r["state"] == "ok", r
    assert ("AuditLogs 30h ago · Graph unread: no right on Graph (HTTP 403 Authorization_RequestDenied) — "
            "threshold 7 days") in _text(r["block"]), r["block"]
    s = ran["graph_unread_silent"]
    assert s["state"] == "silent" and s["short"] == "AuditLogs: no log for 7 days or more", s
    assert "Graph unread: Graph did not answer in time — threshold 7 days" in _text(s["block"])


def test_a_read_in_error_is_red_and_named(ran):
    r = ran["read_error"]
    assert r["state"] == "error" and r["short"] == "SigninLogs not read", r
    assert "SigninLogs not read: HTTP 403 forbidden" in r["said"]


def test_the_block_says_its_logs_whatever_the_dot(ran):
    """Review of IDT1, 1: « before LOGF1 » only of the field absent — a rule in error or a read that hangs
    still shows the ages, and when the watch read them."""
    for name in ("rule_error", "read_hangs"):
        block = _text(ran[name]["block"])
        assert "before LOGF1" not in block and "AuditLogs 1h ago" in block, (name, block)
    assert ran["rule_error"]["state"] == "error"
    assert ran["read_hangs"]["state"] == "silent" and "read 40m ago" in _text(ran["read_hangs"]["block"])
    assert ran["no_field"]["state"] == "ok"
    assert "LOGS not read by this watch (a watch before LOGF1)" in _text(ran["no_field"]["block"])


def test_an_entry_not_of_the_field_s_form_is_left_out(ran):
    r = ran["malformed"]
    assert r["state"] == "ok" and "SigninLogs" not in _text(r["block"]), r


def test_a_rule_s_title_and_every_outside_text_escaped(ran):
    block = ran["all_fresh"]["block"]
    assert "entra-a Credential added to &lt;y&gt; · polling" in re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", block))
    for r in ran.values():
        for markup in (r["line"], r["block"]):
            assert "<x>" not in markup and "<y>" not in markup, markup
