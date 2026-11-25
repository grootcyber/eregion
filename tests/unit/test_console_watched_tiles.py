"""IDT1 (#1182): Entra ID and the control plane on the map as a VM is (Jonathan, 25/11, on a mockup).

Their tile only came with a card: purple, then gone — its absence said nothing (watched and calm, or not
watched at all?). Now always there while their rules run (a rule of their source, enabled and bound to
a backend), first in the row, linked to DETECT only. Their health by their dot: red, a poll in error;
grey, no log for the watch's `silent_after_hours` (LOGF1, `log_freshness` in /api/watch/status) — never
a threshold of the page's; green otherwise. A watch before LOGF1: green or red, never grey. Unfolded, as
a VM's identity block (VMI1): where it is read, its logs' age, its rules, what is set aside (MID1).

Measured in a headless Chromium at 1600 × 1000 and 390 × 844 (the PR says how); read here in the
page's text: no browser in the suite.
"""
from __future__ import annotations

import re
from pathlib import Path

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
    render = _fn("renderInfra")
    assert "    if (!resourceMap.has(w.tile) && _isWatched(kind))\n" in render
    assert "resourceMap.set(w.tile, { resource_id: w.resource_id, vm_name: w.tile, label: w.label, states: [], kind });" in render
    assert "  resourceMap.clear(); _watchedFirst.forEach(([key, r]) => resourceMap.set(key, r));\n" in render


def test_its_health_a_poll_in_error_first_then_its_logs():
    health = _fn("_watchedHealth")
    assert "  const failing = bound.find(r => r.last_error);\n  if (failing) return { state: 'error'," in health
    # A watch before LOGF1: green, never grey.
    assert ("  if (!lf || typeof lf !== 'object' || !lf.tables || typeof lf.tables !== 'object') "
            "return { state: 'ok', said: '', logs: null };") in health
    # A read that failed is never « no log ».
    assert "  if (logs.every(l => l.error)) return { state: 'error', short: 'its logs not read'," in health
    assert health.index("logs.every(l => l.error)") < health.index("const silent =")


def test_the_grey_is_the_watch_s_threshold_never_the_page_s():
    health = _fn("_watchedHealth")
    assert "  const hours = Number(lf.silent_after_hours);\n" in health
    # `last: null` without error: read, and no log in the window — silent too.
    assert "const silent = hours > 0 && (newest === undefined || Date.now() - newest > hours * 3600e3);" in health
    assert "LOG_SILENT" not in JS and not re.search(r"silent_after_hours\s*\|\|\s*\d", JS)


def test_the_dot_says_the_health_before_the_cards():
    node = _fn("_renderNsgNode")
    assert "const watched = Object.hasOwn(_WATCHED, resource.kind || '') && _isWatched(resource.kind);" in node
    assert ("const dotColor = health && health.state === 'error' ? 'var(--red)' : health && health.state === 'silent' ? 'var(--dim)'\n"
            "    : judgeOnly ? 'var(--blue)' : myEscs.length ? 'var(--purple)' : 'var(--green)';") in node
    assert "${watched ? `<div style=\"margin-top:4px\">${_watchedLine(resource.kind, health)}</div>` : ''}" in node
    assert "${isExpanded && watched ? _watchedBlock(resource.kind, health) : ''}" in node


def test_folded_short_unfolded_whole():
    line = _fn("_watchedLine")
    assert "title=\"${_attr(health.said)}\">${health.state === 'error' ? '✗' : '⚠'} ${_attr(health.short)}</span>" in line
    block = _fn("_watchedBlock")
    for said in ("'not read by this watch (before LOGF1)'", "'none in the window read'", "'bound to no backend'",
                 "`${Number(msi)} (Azure's own, MID1)`"):
        assert said in block, said
    assert "<span class=\"vm-id-h\">LOGS</span>${logs}" in block and "<span class=\"vm-id-h\">RULES</span>${rows}" in block


def test_the_page_reads_the_watch_s_status_the_header_holds():
    assert "      lastWatch = w;                      // IDT1" in CONSOLE
    assert "  function watchStatus() { return lastWatch; }\n" in CONSOLE
    assert "ruleTitle, cloudTitle, watchStatus };" in CONSOLE
    assert "const lf = Console.watchStatus()?.log_freshness;" in _fn("_watchedHealth")


def test_the_legend_says_a_watched_tile_s_grey_and_red():
    assert "${dot('var(--dim)', 'unverifiable · maybe off · logs silent')}${dot('var(--red)', 'a rule in error (Entra ID, control plane)')}" in _fn("_legend")
    assert "  .vm-id.watched { grid-template-columns: minmax(0, 1fr); row-gap: 0; }" in HTML
