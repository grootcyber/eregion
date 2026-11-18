"""VP1 (#615): the verdict proposed on an expected exercise card, in Discord — shown (its text through
glorfindel/chat_text.py), confirmed in one click (it becomes the clicker's verdict), refused (gone,
the card still to judge); never on another card. No Discord reached: the views are built, their
callbacks run on fakes."""
import asyncio

import pytest

pytest.importorskip("discord")

from glorfindel import bot, escalations  # noqa: E402

VM = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-one"
PROPOSAL = {"verdict": "right", "on": "detection", "drill": "banc-hebdo", "rule": "a-rule_*x*", "rank": 1,
            "run": "r1", "request": "r-20261117T190000Z-abc123", "sha256": "0" * 64, "within_s": 900,
            "after_s": 130, "at": "2026-11-17T19:05:00+00:00"}


def _exercise_card(**kw) -> str:
    esc_id = escalations.record("rule-a-rule-0123abcd", VM, "snapshot", "low_confidence", "held",
                                rule_name="a-rule", source=kw.pop("source", "exercise"), exercise_run="r1")
    escalations.note_proposals({esc_id: {"proposed": dict(PROPOSAL)}})
    return esc_id


def _stored(esc_id: str) -> dict:
    return next(e for e in escalations.all_escalations() if e["id"] == esc_id)


def _buttons(esc):
    async def build():
        return [i for i in bot.EscalationView(esc).children if isinstance(i, bot._ProposedButton)]
    return asyncio.run(build())


class _Response:
    def __init__(self):
        self.edited = None

    async def edit_message(self, **kw):
        self.edited = kw

    async def send_message(self, *a, **kw):
        raise AssertionError(f"no error expected: {a}")


class _Followup:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class _Interaction:
    def __init__(self):
        self.response, self.followup = _Response(), _Followup()
        self.channel = None
        self.user = type("U", (), {"display_name": "jonathan"})()


def _click(esc, what):
    interaction = _Interaction()

    async def click():
        view = bot.EscalationView(esc)
        button = next(i for i in view.children if isinstance(i, bot._ProposedButton) and i.what == what)
        await button.callback(interaction)
        return view
    return asyncio.run(click()), interaction


def test_the_proposal_is_shown_escaped_with_its_two_buttons():
    esc = _stored(_exercise_card())
    _, fields = bot._embed_body(esc)
    said = dict((n, v) for n, v, _ in fields)["Verdict proposé"]
    assert "`right`" in said and "`a-rule_*x*`" in said and "130 s" in said and "proportionnée" in said
    assert [b.what for b in _buttons(esc)] == ["confirm", "refuse"]
    assert all(b.custom_id.startswith(bot._JUDGE_PREFIX) for b in _buttons(esc))
    assert "proposed:right" in bot._card_signature(esc)


def test_a_card_without_a_proposal_has_no_such_button_and_says_why():
    esc_id = escalations.record("rule-a-rule-0123abcd", VM, "snapshot", "low_confidence", "held",
                                rule_name="a-rule", source="exercise", exercise_run="r1")
    escalations.note_proposals({esc_id: {"why": {"code": "rule", "said": "the card's rule *is* not it"}}})
    esc = _stored(esc_id)
    assert _buttons(esc) == []
    said = dict((n, v) for n, v, _ in bot._embed_body(esc)[1])["Pas de verdict proposé"]
    assert said == "the card's rule \\*is\\* not it"


def test_a_real_card_carrying_a_forged_proposal_shows_nothing_of_it():
    esc = {**_stored(_exercise_card()), "source": "real"}
    assert _buttons(esc) == []
    assert "Verdict proposé" not in dict((n, v) for n, v, _ in bot._embed_body(esc)[1])
    assert bot._proposed_state(esc) == ""


def test_confirm_makes_it_the_clickers_verdict_and_acknowledges_the_card():
    esc_id = _exercise_card()
    view, interaction = _click(_stored(esc_id), "confirm")
    stored = _stored(esc_id)
    assert (stored["verdict"], stored["verdict_from"], stored["status"]) == ("right", "proposed", "resolved")
    assert all(b.disabled for b in view.children)
    assert "jugé par **jonathan**" in interaction.followup.sent[0]


def test_refuse_erases_it_the_card_still_to_judge():
    esc_id = _exercise_card()
    _, interaction = _click(_stored(esc_id), "refuse")
    stored = _stored(esc_id)
    assert escalations.PROPOSED_FIELD not in stored and stored.get("verdict") is None
    assert stored["status"] == "pending"
    rebuilt = interaction.response.edited["view"]
    assert not [i for i in rebuilt.children if isinstance(i, bot._ProposedButton)]
    assert "refusé" in interaction.followup.sent[0]


def test_a_settled_message_greys_the_proposals_buttons_too():
    async def build():
        return [i.custom_id for i in bot._SettledView("abcdef0123").children]
    ids = asyncio.run(build())
    assert f"{bot._JUDGE_PREFIX}confirm_abcdef01" in ids and f"{bot._JUDGE_PREFIX}refuse_abcdef01" in ids
