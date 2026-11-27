"""VRD1 (#1285): a finer verdict — a « wrong » says why: a false alarm (nothing happened), or an action too
strong (the signal was real, the gesture too strong). Decision of Jonathan of 24/11, after the harness's
session MEM-H.

- **The form keeps the old one readable**: ``verdict`` stays the verdict; the cause is a field beside it,
  optional (glorfindel/verdict_cause.py). A « wrong » of before VRD1 carries none and reads as it read, in the
  store, the report, the memory, the console, the bot.
- **« Too strong » only after a gesture**: the store refuses it on a card that made none, whoever asks.
- **Three surfaces write it**: the console (`POST /api/escalations/<id>/verdict`, its pages:
  tests/unit/test_verdict_cause_console.py), the bot (glorfindel/bot_verdict.py), and the command
  (``glorfindel verdict … wrong --cause …``).
- **The report counts the two apart**; the rate of the disruptive ones judged wrong keeps its definition:
  both count in it.
- **The memory by keys says the cause**; the switch off, what the model sees is origin/main's to the byte.

No Azure call, no model call. Mutants M8286–M8295 (scripts/mutants/VRD1.py) are measured here and in
tests/unit/test_verdict_cause_console.py.
"""
from __future__ import annotations

import asyncio
import hashlib
import json

import pytest
from click.testing import CliRunner

from glorfindel import agent, escalations, memory, memory_keys, verdict_cause
from glorfindel.memory import DistanceMemory

from .test_memory_keys import FROZEN, FROZEN_ORDER, FROZEN_SHA256, _frozen_memory, _message
from .test_memory_verdicts import _at, _Clock, _cycle, _keyed, _signal, _vm

VM = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/{}"


def _card(vm: str = "web", action: str = "isolate_vm", sid: str | None = None) -> str:
    return escalations.record(signal_id=sid or f"rule-ransomware-disk-write-{hashlib.sha256(vm.encode()).hexdigest()[:8]}",
                              resource_id=VM.format(vm), action=action, escalation_type="mode_hold", reason="r",
                              rule_name="ransomware-disk-write")


def _stored(esc_id: str) -> dict:
    return next(e for e in escalations.all_escalations() if e["id"] == esc_id)


def _write_line(card: dict) -> str:
    """A card written in the store as a line of before VRD1, or by hand."""
    eid = escalations.record(signal_id=card["signal_id"], resource_id=VM.format(card["signal_id"]), action=card["action"],
                             escalation_type="mode_hold", reason="r")
    lines = [json.loads(x) for x in escalations._STORE.read_text().splitlines() if x.strip()]
    for e in lines:
        if e["id"] == eid:
            e.update(card)
    escalations._STORE.write_text("".join(json.dumps(e) + "\n" for e in lines))
    return eid


# ── 1. The store: the cause written with « wrong », never lost, never kept from a former verdict ────────

def test_a_cause_is_written_beside_the_verdict_and_read_back():
    """M8286: the cause lost at the writing — the operator said « too strong », the store kept a bare wrong."""
    esc = _card()
    e = escalations.set_verdict(esc, "wrong", "the backup of the night", cause="too_strong")
    assert (e["verdict"], e["verdict_cause"]) == ("wrong", "too_strong")
    stored = _stored(esc)
    assert (stored["verdict"], stored["verdict_cause"], stored["verdict_note"]) == (
        "wrong", "too_strong", "the backup of the night")
    assert verdict_cause.of(stored) == "too_strong" and verdict_cause.said(stored) == "wrong · too strong"
    other = _card("db")
    escalations.set_verdict(other, "wrong", cause="false_alarm")
    assert verdict_cause.said(_stored(other)) == "wrong · false alarm"


def test_a_card_judged_again_never_keeps_the_cause_of_its_former_verdict():
    """M8287: judged again (right, or a wrong without a cause), the card still said « too strong »."""
    esc = _card()
    escalations.set_verdict(esc, "wrong", cause="too_strong")
    escalations.set_verdict(esc, "right")
    assert "verdict_cause" not in _stored(esc) and verdict_cause.said(_stored(esc)) == "right"
    escalations.set_verdict(esc, "wrong", cause="false_alarm")
    escalations.set_verdict(esc, "wrong")
    assert "verdict_cause" not in _stored(esc) and verdict_cause.said(_stored(esc)) == "wrong"


@pytest.mark.parametrize("verdict, cause", [("right", "false_alarm"), ("unsure", "too_strong"),
                                            ("wrong", "maybe"), ("wrong", 3)])
def test_a_cause_goes_with_wrong_only_and_is_one_of_two(verdict, cause):
    esc = _card()
    with pytest.raises(ValueError):
        escalations.set_verdict(esc, verdict, cause=cause)
    assert "verdict" not in _stored(esc)                     # nothing written


@pytest.mark.parametrize("action", ["", "none", "monitor", "improve_detection", "release_isolation"])
def test_too_strong_is_refused_on_a_card_that_made_no_gesture(action):
    """M8288: « too strong » accepted without a gesture — a detection for a human, a decision to do nothing,
    cannot have acted too strongly. On it, a wrong is a false alarm."""
    esc = _card(action=action)
    with pytest.raises(ValueError, match="no gesture"):
        escalations.set_verdict(esc, "wrong", cause="too_strong")
    assert "verdict" not in _stored(esc)
    assert escalations.set_verdict(esc, "wrong", cause="false_alarm")["verdict_cause"] == "false_alarm"


@pytest.mark.parametrize("action", sorted(verdict_cause.RESPONSES))
def test_too_strong_is_taken_after_any_gesture(action):
    assert verdict_cause.gesture(action)
    esc = _card(action=action)
    assert escalations.set_verdict(esc, "wrong", cause="too_strong")["verdict_cause"] == "too_strong"


def test_the_gesture_is_the_memorys_reading_of_a_response():
    """One definition: the actions for which « judged right » says a real attack (MEM2b) are those after which
    an action can be too strong (VRD1)."""
    assert memory_keys.RESPONSES is verdict_cause.RESPONSES
    assert {"isolate_vm", "block_suspicious_ip", "snapshot", "restore_from_backup"} <= verdict_cause.RESPONSES
    assert "release_isolation" not in verdict_cause.RESPONSES


# ── 2. A verdict of before reads as it read ─────────────────────────────────────────────────────────────

def test_a_wrong_of_before_or_written_by_hand_reads_as_a_wrong_whose_cause_is_unsaid():
    """M8289: a verdict of before unreadable — a « wrong » without the field, or with one the code never
    wrote, made the report, the list to judge and the memory fall."""
    old = _write_line({"signal_id": "rule-old-0123abcd", "action": "isolate_vm", "verdict": "wrong",
                       "verdict_at": "2026-10-20T08:00:00+00:00"})
    forged = _write_line({"signal_id": "rule-forged-0123abcd", "action": "", "verdict": "wrong",
                          "verdict_at": "2026-10-21T08:00:00+00:00", "verdict_cause": "too_strong"})
    junk = _write_line({"signal_id": "rule-junk-0123abcd", "action": "isolate_vm", "verdict": "wrong",
                        "verdict_at": "2026-10-22T08:00:00+00:00", "verdict_cause": {"x": 1}})
    right = _write_line({"signal_id": "rule-right-0123abcd", "action": "isolate_vm", "verdict": "right",
                         "verdict_at": "2026-10-22T08:00:00+00:00", "verdict_cause": "too_strong"})
    for eid in (old, forged, junk):
        assert verdict_cause.of(_stored(eid)) == "" and verdict_cause.said(_stored(eid)) == "wrong"
    assert verdict_cause.said(_stored(right)) == "right"
    r = escalations.observation_report()
    assert r["causes"] == {"false_alarm": 0, "too_strong": 0, "unsaid": 3}
    assert r["disruptive"]["causes"] == {"false_alarm": 0, "too_strong": 0, "unsaid": 2}
    assert r["disruptive"]["false_rate"] == 2 / 3
    verdicts = memory_keys.card_verdicts()
    assert verdicts["rule-old-0123abcd"] == {"verdict": "wrong", "at": "2026-10-20T08:00:00+00:00",
                                              "action": "isolate_vm"}               # the shape of before
    assert "cause" not in verdicts["rule-forged-0123abcd"] and "cause" not in verdicts["rule-junk-0123abcd"]
    # The memory says MEM2b's text, to the letter.
    assert memory_keys.verdict_said(verdicts["rule-old-0123abcd"], "isolate_vm") == (
        "verdict humain du 2026-10-20 : décision jugée fausse (fausse alerte, ou action disproportionnée)")
    assert memory_keys.verdict_said(verdicts["rule-forged-0123abcd"], "") == (
        "verdict humain du 2026-10-21 : décision jugée fausse (il fallait agir)")


# ── 3. The report: the two causes apart, both in the rate ───────────────────────────────────────────────

def test_the_report_counts_the_false_alarms_and_the_actions_too_strong_apart():
    """M8290: the observation that confuses the two causes — every « wrong » with a cause counted a false
    alarm."""
    judged = [("a", "isolate_vm", "wrong", "too_strong"), ("b", "block_suspicious_ip", "wrong", "too_strong"),
              ("c", "isolate_vm", "wrong", "false_alarm"), ("d", "isolate_vm", "wrong", None),
              ("e", "isolate_vm", "right", None), ("f", "snapshot", "wrong", "too_strong"),
              ("g", "", "wrong", "false_alarm")]
    for vm, action, verdict, cause in judged:
        escalations.set_verdict(_card(vm, action), verdict, cause=cause)
    r = escalations.observation_report()
    assert r["causes"] == {"false_alarm": 2, "too_strong": 3, "unsaid": 1}
    d = r["disruptive"]
    assert d["causes"] == {"false_alarm": 1, "too_strong": 2, "unsaid": 1}
    # Both causes count in the rate of the disruptive ones judged wrong (VRD1), each said apart.
    assert (d["right"], d["wrong"], d["false_rate"]) == (1, 4, 0.8)
    assert (d["false_alarm_rate"], d["too_strong_rate"]) == (0.2, 0.4)


def test_the_report_and_the_monday_summary_say_the_two_causes():
    from glorfindel import bot_verdict
    from glorfindel.cli import cli
    escalations.set_verdict(_card("a"), "wrong", cause="too_strong")
    escalations.set_verdict(_card("b"), "wrong", cause="false_alarm")
    escalations.set_verdict(_card("c"), "wrong")
    out = CliRunner().invoke(cli, ["report", "--since", "all"])
    assert out.exit_code == 0, out.output
    said = " ".join(out.output.split())                     # the terminal's width folds the lines
    assert "wrong: 1 false alarm · 1 too strong · 1 cause unsaid" in said
    assert "false rate 100%, both causes counted" in said
    as_json = json.loads(CliRunner().invoke(cli, ["report", "--since", "all", "--json"]).output)
    assert as_json["disruptive"]["causes"] == {"false_alarm": 1, "too_strong": 1, "unsaid": 1}
    d = escalations.observation_report()["disruptive"]
    assert bot_verdict.causes_said(d) == " (1 false alarm · 1 too strong · 1 cause unsaid)"
    assert bot_verdict.causes_said({"false_rate": None}) == ""                  # a report of before


# ── 4. The command and the console's route ──────────────────────────────────────────────────────────────

def test_the_command_writes_the_cause_and_refuses_too_strong_without_a_gesture():
    from glorfindel.cli import cli
    esc = _card()
    res = CliRunner().invoke(cli, ["verdict", esc[:8], "wrong", "--cause", "too_strong"])
    assert res.exit_code == 0, res.output
    assert "wrong · too strong" in res.output and _stored(esc)["verdict_cause"] == "too_strong"
    bare = _card("db", action="")
    res = CliRunner().invoke(cli, ["verdict", bare[:8], "wrong", "--cause", "too_strong"])
    assert res.exit_code == 1 and "no gesture" in res.output and "verdict" not in _stored(bare)
    res = CliRunner().invoke(cli, ["verdict", bare[:8], "wrong"])                  # a wrong without a cause
    assert res.exit_code == 0 and "verdict_cause" not in _stored(bare)


def test_the_consoles_route_writes_the_cause_and_answers_as_before_without_one(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    client = console()
    esc = _card()
    assert client.post(f"/api/escalations/{esc}/verdict", json={"verdict": "wrong", "cause": "too_strong"}).json() == {
        "ok": True, "verdict": "wrong", "cause": "too_strong"}
    assert _stored(esc)["verdict_cause"] == "too_strong"
    assert client.post(f"/api/escalations/{esc}/verdict", json={"verdict": "right"}).json() == {
        "ok": True, "verdict": "right"}                                          # the answer of before
    bare = _card("db", action="")
    said = client.post(f"/api/escalations/{bare}/verdict", json={"verdict": "wrong", "cause": "too_strong"}).json()
    assert "no gesture" in said["error"] and "verdict" not in _stored(bare)
    assert "error" in client.post(f"/api/escalations/{bare}/verdict", json={"verdict": "wrong", "cause": "x"}).json()
    # What TO JUDGE says of each card: whether it made a gesture — what the page offers « too strong » on.
    listed = {c["id"]: c["gesture"] for c in client.get("/api/to-judge?since=7d").json()["cards"]}
    assert listed == {bare: False}
    fresh = _card("api")
    assert {c["id"]: c["gesture"] for c in escalations.to_judge()}[fresh] is True


def test_the_asked_body_is_read_as_texts():
    assert verdict_cause.asked({"verdict": "wrong", "note": "n", "cause": "false_alarm"}) == ("wrong", "n", "false_alarm")
    assert verdict_cause.asked({"verdict": "right"}) == ("right", "", "")
    assert verdict_cause.asked(None) == ("", "", "")
    assert verdict_cause.asked({"verdict": "wrong", "cause": 7}) == ("wrong", "", "7")


# ── 5. The bot: the cause clicked, never another ────────────────────────────────────────────────────────

class _Response:
    async def edit_message(self, **kw):
        self.edited = kw

    async def send_message(self, *a, **kw):
        self.sent = a


class _Followup:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class _Interaction:
    def __init__(self):
        self.response, self.followup, self.channel = _Response(), _Followup(), None
        self.user = type("U", (), {"display_name": "jonathan"})()


def _click(esc_id: str, pick) -> _Interaction:
    from glorfindel import bot
    interaction = _Interaction()

    async def go():
        view = bot.EscalationView(_stored(esc_id))
        await next(i for i in view.children if pick(i)).callback(interaction)
    asyncio.run(go())
    return interaction


@pytest.mark.parametrize("cause, label", [("false_alarm", "✗ False alarm"), ("too_strong", "✗ Too strong")])
def test_the_bot_writes_the_cause_clicked_never_another(cause, label):
    """M8291: the bot that writes another cause than the one chosen — « too strong » clicked, a false alarm
    written (or the reverse)."""
    pytest.importorskip("discord")
    from glorfindel import bot
    esc = _card()
    said = _click(esc, lambda i: isinstance(i, bot._VerdictButton) and i.cause == cause)
    stored = _stored(esc)
    assert (stored["verdict"], stored["verdict_cause"], stored["status"]) == ("wrong", cause, "resolved")
    assert said.followup.sent == [f"{label} — jugé par **jonathan**"]
    assert bot._card_state_line(stored).startswith(f"jugée wrong · {verdict_cause.WORDS[cause]}")


def test_the_bot_offers_too_strong_only_after_a_gesture_and_its_ids_are_judges():
    pytest.importorskip("discord")
    from glorfindel import bot

    async def build(esc):
        return [(i.verdict, i.cause, i.custom_id, i.label) for i in bot.EscalationView(esc).children
                if isinstance(i, bot._VerdictButton)]
    bare = _card("db", action="")
    got = asyncio.run(build(_stored(bare)))
    assert [(v, c) for v, c, _, _ in got] == [("right", ""), ("wrong", "false_alarm"), ("unsure", "")]
    assert [cid for _, _, cid, _ in got] == [f"glorfindel_verdict_{w}_{bare[:8]}" for w in ("right", "false_alarm", "unsure")]
    assert all(bot._button_kind(cid) == "judge" for _, _, cid, _ in got)
    # A settled message knows every id a card's message can carry, the causes' too.
    ids = {getattr(i, "custom_id", "") for i in asyncio.run(_settled(bot, bare)).children}
    assert {f"glorfindel_verdict_{w}_{bare[:8]}" for w in ("false_alarm", "too_strong", "wrong")} <= ids


async def _settled(bot, esc_id):
    return bot._SettledView(esc_id)


def test_a_message_of_before_vrd1_keeps_its_wrong_once_the_bot_restarted():
    """M8292: the view given back to a message posted before VRD1 lacked its ✗ Wrong — a click on it, after a
    redeploy, answered « interaction failed ». It writes a wrong without a cause, as it did."""
    pytest.importorskip("discord")
    from glorfindel import bot
    esc = _card()
    b = bot.GlorfindelBot(channel_id=1, ping_role=None)
    b._messages = {esc: 77}
    added = []
    b.add_view = lambda view, message_id=None: added.append((view, message_id))
    assert b._restore_views() == 1
    [(view, mid)] = added
    old = f"glorfindel_verdict_wrong_{esc[:8]}"
    assert mid == 77 and old in {getattr(i, "custom_id", "") for i in view.children}
    interaction = _Interaction()

    async def go():
        await next(i for i in view.children if getattr(i, "custom_id", "") == old).callback(interaction)
    asyncio.run(go())
    stored = _stored(esc)
    assert stored["verdict"] == "wrong" and "verdict_cause" not in stored
    # The message drawn again (its card changed): today's buttons, never the ✗ Wrong of before.
    drawn = {getattr(i, "custom_id", "") for i in bot._build_view(_stored(_card("db"))).children}
    assert not any(cid.startswith("glorfindel_verdict_wrong_") for cid in drawn)


def test_the_bots_signature_of_a_card_is_the_one_of_before():
    """« One signature, today's »: a card's signature does not change for VRD1 — no message edited for it alone."""
    pytest.importorskip("discord")
    from glorfindel import bot
    esc = _card()
    assert bot._card_signature(_stored(esc)) == "pending||1"
    escalations.set_verdict(esc, "wrong", cause="too_strong")
    assert bot._card_signature(_stored(esc)) == "pending|wrong|1"


# ── 6. The memory: the cause said by the keys, nothing new for the model with the switch off ────────────

def test_the_keys_say_the_cause_when_the_operator_said_it(tmp_path):
    clock = _Clock()
    mem = _keyed(tmp_path, clock)
    for sid, vm in (("strong", "vm-a"), ("alarm", "vm-b"), ("bare", "vm-c")):
        _at(mem, clock, _cycle(sid, vm), 10 * 86400)
    for sid, vm, cause in (("strong", "vm-a", "too_strong"), ("alarm", "vm-b", "false_alarm"), ("bare", "vm-c", None)):
        eid = escalations.record(signal_id=sid, resource_id=_vm(vm), action="isolate_vm",
                                 escalation_type="low_confidence", reason="à juger", source="real", ttp="T1486")
        day = escalations.set_verdict(eid, "wrong", cause=cause)["verdict_at"][:10]
    found = {p["signal_id"]: p["summary"] for p in mem.retrieve_similar(_signal(), n=3)}
    head = f" | verdict humain du {day} : décision jugée fausse ("
    assert found["strong"].endswith(head + "action trop forte : le signal était vrai, le geste trop fort)")
    assert found["alarm"].endswith(head + "fausse alerte : rien ne s'était passé)")
    assert found["bare"].endswith(head + "fausse alerte, ou action disproportionnée)")          # MEM2b's, as before
    message = agent._build_user_message(_signal(), mem.retrieve_similar(_signal(), n=3))
    assert "action trop forte" in message


def test_off_the_model_sees_origin_mains_message_to_the_byte_whatever_the_causes(tmp_path, monkeypatch):
    """M8293: the cause shown to the model with MEM2's switch off — the memory by distance said the cards'
    verdicts. Off, the precedents and the message are those of before MEM2, to the byte, every cycle judged
    with a cause."""
    monkeypatch.delenv(memory.SWITCH, raising=False)
    mem = _frozen_memory(tmp_path / "cycles")
    assert type(mem) is DistanceMemory
    for i, (sid, vm, *_rest) in enumerate(FROZEN):
        eid = escalations.record(signal_id=sid, resource_id=_vm(vm), action="snapshot",
                                 escalation_type="low_confidence", reason="r", source="real")
        escalations.set_verdict(eid, "wrong", cause=("too_strong", "false_alarm")[i % 2])
    order, message = _message(tmp_path, mem)
    assert order == FROZEN_ORDER
    assert hashlib.sha256(message.encode()).hexdigest() == FROZEN_SHA256
    assert "verdict humain" not in message
    # On, the same cycles say their cause: the change waits for ENQ5b's run end to end.
    on = _message(tmp_path, _frozen_memory(tmp_path / "keys.sqlite3", mode=memory.KEYS))[1]
    assert "action trop forte" in on and "fausse alerte : rien ne s'était passé" in on
