"""MBV1 (#1175): the watch's own cards, the model breaker's first, seen in the console (Jonathan, 25/11,
on a mockup). Each mutant takes a piece back: a card without a resource given a tile again, without a
name (M7556), the node without its band (M7557), only the breaker's cards the watch's: another card
without a resource lost (M7558), a card whose resource is missing, not empty, lost (M7559), the reason cut
at two lines (M7560), an Ack refused told done (M7561), the window left as it was after an Ack (M7562),
the route the header reads counting none (M7563), the header's pill never shown (M7564), the window's Acks
too small for a finger (M7565). M7556–M7565, measured by tests/unit/test_console_watch_cards.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"
CON_JS = "eregion_console/static/console.js"
API = "eregion_console/api.py"

_T = "tests/unit/test_console_watch_cards.py::"

MUTANTS = [
    ("M7556", "a card without a resource given a tile again, without a name, never drawn (MBV1)", GF_JS,
     "    if (_isWatchCard(e)) return;           // MBV1: on the GLORFINDEL node, never a tile without a name\n", ""),
    ("M7557", "the GLORFINDEL node without the watch's band: its cards nowhere (MBV1, decision 1)", GF_JS,
     "    ${_watchBand()}\n  </div>`;", "  </div>`;"),
    ("M7558", "only the breaker's cards are the watch's: another card without a resource lost (MBV1, decision 3)", GF_JS,
     "function _watchCards() { return (_state?.escalations || []).filter(_isWatchCard); }",
     "function _watchCards() { return (_state?.escalations || []).filter(e => e.escalation_type === 'model_budget_tripped'); }"),
    ("M7559", "a card whose resource is missing, not empty, not the watch's: lost (MBV1)", GF_JS,
     "function _isWatchCard(e) { return !String((e && e.resource_id) || '').trim(); }",
     "function _isWatchCard(e) { return !!e && e.resource_id === ''; }"),
    ("M7560", "the reason of a watch's card cut at two lines (MBV1)", GF_HTML,
     "  .watch-card-why { white-space: normal; overflow-wrap: anywhere; color: var(--text); }",
     "  .watch-card-why { white-space: normal; overflow-wrap: anywhere; color: var(--text); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }"),
    ("M7561", "an Ack of the watch refused, told done (MBV1)", GF_JS,
     "      if (!res.ok || d.error) refused.push(String(d.error || d.detail || `HTTP ${res.status}`));\n      else ok++;",
     "      ok++;"),
    ("M7562", "the window of the watch's cards left as it was after an Ack (MBV1)", GF_JS,
     "    if (_watchCardsOpen()) _renderWatchCards();   // MBV1: an Ack, or a card come, said in the open window\n", ""),
    ("M7563", "the route the header reads counts no breaker: the pill never comes (MBV1, decision 2)", API,
     '    return {**_heartbeat(), "model_breaker": _model_breakers()}', '    return {**_heartbeat(), "model_breaker": 0}'),
    ("M7564", "the header's pill never shown, on any page (MBV1, decision 2)", CON_JS,
     "    pill.hidden = count === 0;", "    pill.hidden = true;"),
    ("M7565", "the Acks of the watch's cards 21 px high on a phone (MBV1)", GF_HTML,
     "    .watch-card button, .watch-all button { min-height: 44px; padding: 6px 16px; font-size: 13px; }\n", ""),
]

TESTS = {
    "M7556": f"{_T}test_a_card_without_a_resource_is_the_watch_s_never_a_tile_without_a_name",
    "M7557": f"{_T}test_the_node_shows_the_watch_s_cards_and_opens_them",
    "M7558": f"{_T}test_a_card_without_a_resource_is_the_watch_s_never_a_tile_without_a_name",
    "M7559": f"{_T}test_a_card_without_a_resource_is_the_watch_s_never_a_tile_without_a_name",
    "M7560": f"{_T}test_the_window_shows_each_reason_whole_and_its_steps",
    "M7561": f"{_T}test_an_ack_of_the_watch_reads_each_answer",
    "M7562": f"{_T}test_the_window_and_the_header_follow_the_state",
    "M7563": f"{_T}test_the_route_the_header_reads_counts_the_breakers_open",
    "M7564": f"{_T}test_the_header_says_the_breaker_on_every_page",
    "M7565": f"{_T}test_on_a_phone_the_band_and_the_acks_take_a_finger",
}
