"""TOPO1b (#949): the readiness audit not read, said once above the cards of the infra map.

Jonathan's decision of 19/11, on a mockup (« ip ? » on every card set aside): when /api/audit
cannot be read at all, a band above the cards — « ⚠ Readiness audit not read: <reason> · checks
and addresses unknown on every card · next try within 5 min ». The last good audit kept (a
refresh failed after one), the band says when it was read: « cards show the read of HH:MM:SS
UTC ». Before, the cards lost their checks and their addresses in silence, and only the dot of
the GLORFINDEL node went red; an HTTP error with a JSON body (a 404, a 422 `{detail}`) was read as
an audit without VMs.

Measured in a headless Chromium on the sample console (the PR says how); read here in the page's
text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")


def body(head: str) -> str:
    assert head in JS, head
    return JS.split(head, 1)[1].split("\n}\n", 1)[0]


def test_the_band_sits_above_the_cards_of_the_map():
    infra = body("function renderInfra() {")
    assert "      ${_auditBand()}\n\n      <!-- Layer 3 — Assets -->\n      <div class=\"topo-assets\" id=\"topo-assets\">" in infra


def test_an_audit_not_read_at_all_says_the_cards_know_nothing():
    band = body("function _auditBand() {")
    assert "if (_auditData?.error)" in band
    assert ("⚠ Readiness audit not read: ${_attr(_auditData.error)} <span class=\"topo-band-dim\">· checks and "
            "addresses unknown on every card · next try within 5 min</span>") in band


def test_the_last_good_audit_kept_the_band_says_when_it_was_read():
    band = body("function _auditBand() {")
    # Stale first: a refresh failed after a good audit, the cards still show that one.
    assert band.index("if (_auditStale) {") < band.index("if (_auditData?.error)")
    assert "const when = _auditLastRun ? `cards show the read of ${_attr(fmtTime(_auditLastRun))}` : 'cards show the last read';" in band
    assert "⚠ Readiness audit not read: ${_attr(_auditStale)} <span class=\"topo-band-dim\">· ${when}</span>" in band
    # Nothing to say: nothing said.
    assert band.rstrip().endswith("return '';")


def test_an_answer_that_is_not_an_audit_is_a_failure():
    refresh = body("async function refreshAuditData() {")
    assert "if (!r.ok) throw new Error(`HTTP ${r.status}`);" in refresh
    assert "if (!Array.isArray(d?.audits)) throw new Error('the answer holds no audit');" in refresh
    assert refresh.index("if (!r.ok)") < refresh.index("_auditData    = d;") < refresh.index("_auditLastRun = new Date().toISOString();")


def test_an_audit_read_again_takes_the_band_away():
    refresh = body("async function refreshAuditData() {")
    good = refresh.split("_auditData    = d;", 1)[1].split("} catch (e) {", 1)[0]
    assert "_auditStale   = null;" in good


def test_the_band_is_above_the_edges_and_never_a_card():
    rule = HTML.split(".topo-band {", 1)[1].split("}", 1)[0]
    assert "position: relative; z-index: 1;" in rule
    assert re.search(r"color: var\(--orange\)", rule)
