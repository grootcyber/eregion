"""MBV1 (#1175): the watch's own cards, the model breaker's first, seen in the console.

A card `model_budget_tripped` (PRT2) says the model breaker tripped: until 00:00 UTC a detection may
not be seen by the model. It is written without a resource (`resource_id: ""`), and it was nowhere in
the console: not a decision (out of TO JUDGE), and the tile it was given had no name and was never
drawn (measured in a headless Chromium on 0.6.7). Jonathan's decisions (25/11, on a mockup):
  1. on the GLORFINDEL node, a red band that opens them — each reason whole, its steps, its Ack;
  2. on every page, a pill in the header beside the watch while one is open, that leads to them;
  3. a card the page cannot place is never lost: any card without a resource is the watch's.

Measured in a headless Chromium at 1440 × 900 and 390 × 844 with the touch (the PR says how); read
here in the page's text (no browser in the suite), and the route the header reads, called.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from glorfindel import escalations as esc

from .console_client import console

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
CONSOLE = (STATIC / "console.js").read_text(encoding="utf-8")
CSS = (STATIC / "console.css").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]
PHONE = STYLE.split("  @media (max-width: 759px) {\n", 1)[1].split("\n  }\n", 1)[0]


def _fn(src: str, name: str) -> str:
    m = re.search(r"\n\s*(?:async )?function " + re.escape(name) + r"\(", src)
    assert m, name
    return src[m.start():].split("\n}\n", 1)[0] if src is JS else src[m.start():].split("\n  }\n", 1)[0]


def _breaker(signal_id: str) -> str:
    return esc.record(signal_id=signal_id, resource_id="", action="", escalation_type="model_budget_tripped",
                      reason="Disjoncteur du modèle sauté : jusqu'à minuit UTC, une ordinaire devient une carte.",
                      suggested_steps=["Lire les cartes du jour."])


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir()
    return console()


def test_the_route_the_header_reads_counts_the_breakers_open(client):
    assert client.get("/api/watch/status").json()["model_breaker"] == 0
    first = _breaker("model-budget-2026-11-25-real/rest")
    _breaker("model-budget-2026-11-25-count")
    esc.record(signal_id="s-1", resource_id="/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-a",
               action="snapshot", escalation_type="low_confidence", reason="a decision")
    w = client.get("/api/watch/status").json()
    assert w["model_breaker"] == 2
    assert w["status"] == "stopped"                     # whatever the heartbeat says, the breakers said
    esc.resolve(first, note="ack")
    assert client.get("/api/watch/status").json()["model_breaker"] == 1


def test_a_store_that_cannot_be_read_counts_none_and_keeps_the_heartbeat(client, monkeypatch):
    def broken():
        raise OSError("unreadable")
    monkeypatch.setattr(esc, "pending", broken)
    assert client.get("/api/watch/status").json() == {"status": "stopped", "model_breaker": 0}


def test_a_card_without_a_resource_is_the_watch_s_never_a_tile_without_a_name():
    assert "function _isWatchCard(e) { return !String((e && e.resource_id) || '').trim(); }" in JS
    # Whatever its type: a card the page cannot place is never lost.
    assert "function _watchCards() { return (_state?.escalations || []).filter(_isWatchCard); }" in JS
    loop = JS.split("  vmEscs.forEach(e => {\n", 1)[1].split("\n  });\n", 1)[0]
    assert loop.index("if (_isWatchCard(e)) return;") < loop.index("const own = _ownTile(e);")


def test_the_node_shows_the_watch_s_cards_and_opens_them():
    node = _fn(JS, "_renderAgentNode")
    assert "    ${_watchBand()}\n  </div>`;" in node
    band = _fn(JS, "_watchBand")
    assert "if (!cards.length) return '';" in band
    assert "`MODEL BREAKER ×${Number(breakers)}`" in band
    assert "<button type=\"button\" class=\"node-watch\" ${_on('click', 'openWatchCards')}" in band   # a key opens it too
    assert "  openWatchCards, ackWatchCards,  " in JS
    assert "  model_budget_tripped: 'Model breaker tripped',\n" in JS


def test_the_window_shows_each_reason_whole_and_its_steps():
    win = _fn(JS, "_renderWatchCards")
    assert "<div class=\"watch-card-why\">${_attr(e.reason || '')}</div>" in win
    assert "e.suggested_steps.filter(x => typeof x === 'string' && x.trim())" in win
    assert "steps.map(x => `<li>${_attr(x)}</li>`)" in win
    assert "${_on('click', 'ackWatchCards', e.id)}>✓ Ack</button>" in win
    # Never cut: a breaker's reason says what stops and until when.
    assert "  .watch-card-why { white-space: normal; overflow-wrap: anywhere; color: var(--text); }" in STYLE
    assert "line-clamp" not in STYLE.split(".watch-card-why", 1)[1].split("}", 1)[0]


def test_an_ack_of_the_watch_reads_each_answer():
    ack = _fn(JS, "ackWatchCards")
    assert "split(',').filter(id => _watchCards().some(e => e.id === id));" in ack     # only the watch's
    assert "for (const id of wanted) {" in ack
    assert "if (!res.ok || d.error) refused.push(String(d.error || d.detail || `HTTP ${res.status}`));" in ack
    assert "toast(refused.length ? `⚠ ${ok} of ${wanted.length} acknowledged — ${refused[0]}`" in ack
    assert "await refreshState();" in ack
    assert "if (!wanted.length) { toast('Already closed'); await refreshState(); return; }" in ack


def test_the_window_and_the_header_follow_the_state():
    state = _fn(JS, "refreshState")
    assert "if (_watchCardsOpen()) _renderWatchCards();" in state
    assert "Console.setBreakers(_watchCards().filter(e => e.escalation_type === 'model_budget_tripped').length);" in state
    assert "m.classList.contains('open') && m.dataset.owner === 'watch-cards'" in _fn(JS, "_watchCardsOpen")


def test_the_header_says_the_breaker_on_every_page():
    assert ('<a class="hstat c-breaker" id="c-breaker" href="/glorfindel?watch" hidden title="The model breaker '
            'tripped') in CONSOLE
    assert "      setBreakers(w.model_breaker);\n" in CONSOLE
    breakers = CONSOLE.split("  function setBreakers(n) {\n", 1)[1].split("\n  }\n", 1)[0]
    assert "const count = Math.max(0, Math.floor(Number(n) || 0));" in breakers
    assert "pill.hidden = count === 0;" in breakers
    assert "return { init, onSections, setJudgeCount, setBreakers, hms, esc, section, ruleTitle, cloudTitle, watchStatus, watchSaid };" in CONSOLE
    # From another page, the link opens them on the page Glorfindel; on it, in place.
    assert "else if (new URLSearchParams(location.search).has('watch')) openWatchCards();" in JS
    assert "Console.init(_IS_CONFIG ? 'config' : 'glorfindel', { onBreaker: () => openWatchCards() });" in JS
    assert "$('c-breaker').addEventListener('click', ev => { ev.preventDefault(); opts.onBreaker(); });" in CONSOLE
    for page in ("overview.js", "dagorlad.js", "injector.js"):
        assert "Console.init(" in (STATIC / page).read_text(encoding="utf-8"), page
    assert "header.console .c-breaker { color: var(--red);" in CSS


def test_on_a_phone_the_band_and_the_acks_take_a_finger():
    assert "    .node-watch { min-height: 44px; font-size: 12px; align-items: center; }" in PHONE
    assert "    .watch-card button, .watch-all button { min-height: 44px; padding: 6px 16px; font-size: 13px; }" in PHONE


def test_an_ack_closes_the_card_never_the_breaker_and_nothing_says_otherwise():
    """The relecture of MBV1: the pill said « until it is acknowledged » — the Ack closes the card
    (escalations.resolve); the breaker resets at 00:00 UTC (model_budget._roll), a provider's limit once a
    call is served. An operator acknowledging would think the model back."""
    pill = CONSOLE.split('id="c-breaker"', 1)[1].split(">", 1)[0]
    assert ("The model breaker tripped: until 00:00 UTC (a provider's limit: until a call is served), a detection "
            "may not be seen by the model. An Ack closes the card, not the breaker.") in pill
    assert ("const _BREAKER_ACK = 'An Ack closes the card, not the breaker: the model comes back at 00:00 UTC "
            "(a provider\\'s limit: once a call is served).';") in JS
    assert "? `<div class=\"watch-note\">${_BREAKER_ACK}</div>` : ''" in _fn(JS, "_renderWatchCards")
    for page in (CONSOLE, JS):
        for promise in ("until it is acknowledged", "until acknowledged", "Ack to re", "acknowledge to re"):
            assert promise not in page, promise
