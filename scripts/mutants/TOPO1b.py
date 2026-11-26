"""TOPO1b (#949): the readiness audit not read, said once above the cards of the infra map (Jonathan,
19/11, on a mockup), and the four remarks of TOPO1's review. Each mutant brings back what was
there: the band left out of the map (M6501), an audit not read at all left unsaid (M6502), the band
of a kept audit without the time of its read (M6503), the reason written raw (M6504), an HTTP error
with a JSON body read as an audit without VMs (M6505), a browser without ResizeObserver breaking the render (M6506), the
row of cards no longer observed (M6507), every observation drawing — the draw of more, every 5 s
(M6508), the shell checked by its container only (M6509), the band staying after a good audit
(M6510). M6501–M6510, measured by tests/unit/test_console_audit_band.py and
tests/unit/test_console_topology.py (M6504 also by tests/unit/test_console_escaping.py). OCT1 (#1240) took
off M6506, M6507 and M6508: the ResizeObserver of the edges they measured went with the tiles' view.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"

_B = "tests/unit/test_console_audit_band.py::"
_T = "tests/unit/test_console_topology.py::"

MUTANTS = [
    ("M6501", "the band left out of the map: an audit not read, the cards silent again (TOPO1b)", JS,
     "      ${_auditBand()}\n\n      <!-- Layer 3 — Assets -->\n",
     "      <!-- Layer 3 — Assets -->\n"),
    ("M6502", "an audit not read at all left unsaid: only the dot of the GLORFINDEL node goes red (TOPO1b)", JS,
     "  if (_auditData?.error)\n    return `<div class=\"topo-band\" role=\"status\">",
     "  if (false)\n    return `<div class=\"topo-band\" role=\"status\">"),
    ("M6503", "the band of a kept audit without the time of its read (TOPO1b)", JS,
     "    const when = _auditLastRun ? `cards show the read of ${_attr(fmtTime(_auditLastRun))}` : 'cards show the last read';\n",
     "    const when = 'cards show the last read';\n"),
    ("M6504", "the reason of a failed audit written raw into the page (TOPO1b, #254)", JS,
     "⚠ Readiness audit not read: ${_attr(_auditData.error)} <span",
     "⚠ Readiness audit not read: ${_auditData.error} <span"),
    ("M6505", "an HTTP error with a JSON body (a 404, a 422 {detail}) read as an audit without VMs: every card "
              "silent, no band (TOPO1b)", JS,
     "    if (!r.ok) throw new Error(`HTTP ${r.status}`);\n",
     ""),
    ("M6509", "the shell checked by its container only: #topo-body missing, the render throws (TOPO1b, "
              "review of TOPO1)", JS,
     "  if (!graph || !list.contains(graph) || !body) {\n",
     "  if (!graph || !list.contains(graph)) {\n"),
    ("M6510", "the band stays after a good audit: the kept one is never let go (TOPO1b)", JS,
     "    _auditLastRun = new Date().toISOString();\n    _auditStale   = null;\n",
     "    _auditLastRun = new Date().toISOString();\n"),
]

TESTS = {
    "M6501": f"{_B}test_the_band_sits_above_the_cards_of_the_map",
    "M6502": f"{_B}test_an_audit_not_read_at_all_says_the_cards_know_nothing",
    "M6503": f"{_B}test_the_last_good_audit_kept_the_band_says_when_it_was_read",
    "M6504": f"{_B}test_an_audit_not_read_at_all_says_the_cards_know_nothing tests/unit/test_console_escaping.py",
    "M6505": f"{_B}test_an_answer_that_is_not_an_audit_is_a_failure",
    "M6509": f"{_T}test_the_scroll_container_outlives_a_refresh",
    "M6510": f"{_B}test_an_audit_read_again_takes_the_band_away",
}
