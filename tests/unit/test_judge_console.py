"""JUG1 (#760): the console shows each card to judge — a line of TO JUDGE opens its card, and a tile
that folds several cards shows every one of them, each readable and judged on its own.

On the bench, 12/11, 10:58 UTC: the six cards of an NSG were folded on its tile (« ×6 ») and its
details showed the first only; a line of TO JUDGE did not open; only Discord showed each card. And
the card « exécutée » of an action taken alone (glorfindel/agent.py, `_record_executed`) reaches the
page with what it says: its mode, its check, its evidence.

The page has no JS runtime here (no browser, no node): its code is read, as tests/unit/test_console.py
reads it; what reaches it from the watch is data, written through `_attr` (#254 —
tests/unit/test_console_escaping.py holds the whole page). Crosses components: TOGETHER.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from glorfindel import escalations  # noqa: E402

from .console_client import console  # noqa: E402

VM = "/subscriptions/s/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/web"
JS = Path(__file__).resolve().parents[2] / "eregion_console/static/glorfindel.js"


@pytest.fixture(autouse=True)
def _here(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir()


def _executed_card(signal_id: str = "rule-ransomware-disk-write-0000c0c0") -> str:
    from glorfindel.agent import _record_executed
    state = {
        "signal": {"signal_id": signal_id, "event": "detection", "ttp": "T1486", "severity": "high",
                   "resource_id": VM, "context": {"rule_name": "ransomware-disk-write", "run_id": "r"},
                   "raw_signal": {"first_result_row": {"Computer": "web", "MaxWrite": 147000000}}},
        "action": "isolate_vm", "confidence": 0.92, "explanation": "Écritures disque massives.",
        "autonomy_mode": "non_disruptive", "dry_run": False, "escalate": False,
        "outcome": {"executed": True, "status": "isolated", "verified": True, "method": "nsg_check",
                    "verified_at": datetime.now(timezone.utc).isoformat(), "nics_covered": 1},
    }
    return _record_executed(state, "real", "")


def _js() -> str:
    return JS.read_text()


def _function(js: str, head: str) -> str:
    start = js.index(head)
    return js[start:js.index("\n}\n", start)]


# ── what the page is sent ──────────────────────────────────────────────────────────────────────

def test_to_judge_carries_what_its_card_says():
    """A line opens its card even once acknowledged (no longer in /api/state): TO JUDGE carries the
    card's steps and, for an action taken alone, what it did and how it was checked."""
    cid = _executed_card()
    escalations.resolve(cid)                                            # acknowledged, not judged
    [card] = console().get("/api/to-judge").json()["cards"]
    assert card["id"] == cid and card["escalation_type"] == escalations.EXECUTED_TYPE
    assert card["executed"]["mode"] == "non_disruptive" and card["executed"]["verification"]["verified"] is True
    assert "MaxWrite: 147000000" in card["executed"]["evidence"]
    assert card["suggested_steps"] and "glorfindel release rg-app/web --yes" in card["suggested_steps"][0]


def test_the_indicator_counts_an_action_taken_alone_judged_wrong():
    """« Actions disruptives à tort » (/api/indicators, 30 days): the card judged wrong counts."""
    cid = _executed_card()
    escalations.set_verdict(cid, "wrong", "")
    body = console().get("/api/indicators").json()
    assert body["wrong"]["days_30"] == {"rate": 1.0, "judged": 1, "wrong": 1}


def test_the_card_on_its_tile_says_it_ran_and_holds_nothing_to_approve():
    js = _js()
    assert "function _isExecuted(e) { return e.escalation_type === 'autonomous_action'; }" in js
    assert "autonomous_action" not in re.search(r"const _HELD_TYPES = new Set\(\[(.*?)\]\);", js).group(1)
    group = _function(js, "function _renderEscGroup(group)")
    assert ": _isExecuted(e)     ? `${actionLabel(e.action)} — done alone, to judge`" in group
    cmd = _function(js, "function cliCommand(esc)")
    assert "if (_isExecuted(esc)) {" in cmd and "glorfindel release ${vm} --yes" in cmd
    assert cmd.count("const vm = _vmArg(rid);") == 2           # <groupe>/<nom> (MSK3b)
    assert "glorfindel unblock ${ip} ${vm} --yes" in cmd


# ── a line of TO JUDGE opens its card ──────────────────────────────────────────────────────────

def test_a_line_of_to_judge_opens_its_card():
    js = _js()
    render = _function(js, "function renderToJudge()")
    assert "id=\"judge-${id}\" ${_on('click', 'openJudgeCard', c.id)}" in render
    # Its note, its buttons and the run's link keep their click: the line does not open under them.
    assert "<div class=\"judge-actions\" ${_on('click', 'stop')}>" in render
    assert "encodeURIComponent(c.exercise_run)}\" ${_on('click', 'stop')}>" in render
    actions = js[js.index("const ACTIONS = {"):js.index("\n};\n", js.index("const ACTIONS = {"))]
    assert "\n  openJudgeCard," in actions
    assert "judgeFromModal(id, verdict) { judgeCard(id, verdict, 'judge-modal-note'); closeModal(); }," in actions


def test_the_opened_card_shows_its_details_and_its_verdict():
    js = _js()
    opened = _function(js, "function openJudgeCard(escId)")
    # The card as TO JUDGE carries it, completed by the store's pending card when there is one.
    assert "const listed = _toJudge.find(c => c.id === escId);" in opened
    assert "Object.assign({}, listed || {}, _escById[escId] || {})" in opened
    # What the card says, the same body as on its tile.
    assert "${_cardBody(e, vmName)}${_cardSteps(e)}" in opened
    for verdict in ("right", "wrong", "unsure"):
        assert f"_on('click', 'judgeFromModal', e.id, '{verdict}')" in opened
    assert '<input id="judge-modal-note"' in opened
    judge = _function(js, "async function judgeCard(escId, verdict, noteId)")
    assert "document.getElementById(noteId || 'judge-note-' + escId)" in judge


# ── a tile that folds several cards shows each one ────────────────────────────────────────────

def test_a_folded_tile_shows_every_card_each_judged_on_its_own():
    """The NSG's six cards, 12/11: every card of the group through `_cardDetail`, its own reason,
    its own explanation, its own way to its verdict — never the first one's alone."""
    js = _js()
    modal = _function(js, "function showEscModal(vmName)")
    assert "const body = count > 1" in modal
    assert "${group.map(g => _cardDetail(g, vmName, true)).join('')}" in modal
    assert "${_cardDetail(e, vmName, false)}${query}${steps}" in modal
    assert "${_attr(e.reason || '')}" not in modal                        # the first's reason only: gone
    detail = _function(js, "function _cardDetail(e, vmName, own)")
    for said in ("_attr(escTitle(e))", "_attr(String(e.id || '').slice(0, 8))", "_judgeWay(e)", "_escCtx(e, ",
                 "${_cardBody(e, vmName)}${rest}"):
        assert said in detail, said
    body = _function(js, "function _cardBody(e, vmName)")
    for said in ("_attr(e.reason || '')", "_attr(e.explanation)", "_executedDetail(e)", "_targetNote(e, vmName)"):
        assert said in body, said
    assert "• ${_attr(st)}</div>" in _function(js, "function _cardSteps(e)")
    way = _function(js, "function _judgeWay(e)")
    assert "_on('click', 'openJudgeCard', e.id)" in way and "judged: ${_attr(e.verdict)}" in way
    assert "_NOT_DECISIONS.has(e.escalation_type)" in _function(js, "function _isDecisionCard(e)")


def test_an_action_taken_alone_shows_its_mode_its_check_and_its_evidence():
    js = _js()
    detail = _function(js, "function _executedDetail(e)")
    assert "if (!_isExecuted(e) || !x || typeof x !== 'object') return '';" in detail
    assert "mode ${_attr(x.mode || '?')}" in detail
    assert ".filter(Boolean).map(w => _attr(w)).join(' · ')" in detail
    assert "• ${_attr(w)}</div>" in detail and "${_attr(x.note)}" in detail


def test_two_identity_cards_on_their_tile_keep_each_their_plan_and_its_verify():
    """JUG1 review: the identities' cards fold on one tile (`identity_change`, no action); folded,
    each one showed its steps only — its plan and its « Verify » (IR1a) gone. Each card of a group
    keeps its own plan, else its steps, and its proposed query."""
    for n, name in enumerate(("app-a", "app-b")):
        escalations.record(f"rule-entra-credential-added-0000c{n}c{n}", f"entra:identities/{name}", "",
                           "identity_change", f"Entra ID : identifiant ajouté à {name}.",
                           identity_plan={"items": [{"n": 1, "what": f"révoquer {name}", "by": "executor"}]},
                           target={"kind": "identity", "name": name})
    cards = [e for e in console().get("/api/state").json()["escalations"]
             if e["escalation_type"] == "identity_change"]
    assert sorted(e["identity_plan"]["items"][0]["what"] for e in cards) == ["révoquer app-a", "révoquer app-b"]
    js = _js()
    detail = _function(js, "function _cardDetail(e, vmName, own)")
    assert "const rest = own ? `${e.identity_plan ? _identityPlan(e) : _cardSteps(e)}${_cardQuery(e)}` : '';" in detail
    assert "${head}${_cardBody(e, vmName)}${rest}" in detail
    plan = js[js.index("function _identityPlan(e)"):js.index("function _cardDetail(")]
    assert "_on('click', 'verifyIdentity'" in plan
    assert "${_attr(e.proposed_query.trim())}</pre>" in _function(js, "function _cardQuery(e)")


def test_an_action_taken_alone_is_never_acknowledged_with_a_card_of_another_type():
    """JUG1 review: a held isolation and an isolation taken alone on the same VM share an action —
    one group, and its Ack acknowledged the card to judge unread. Never grouped together."""
    group = _function(_js(), "function _groupEscs(escs)")
    assert "const kind = _isExecuted(e) ? `executed|${origin}` : origin;" in group
    assert "map.get(kind).push(e);" in group
