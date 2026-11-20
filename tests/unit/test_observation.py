"""Observation kit: the operator's verdict on each recommendation, and the report that
measures the false rate of disruptive ones — the number the autonomy decision rests on
(docs/observation.md)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from glorfindel import escalations

VM = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/{}"


def _card(vm="web", action="isolate_vm", kind="mode_hold", signal_id=None, rule="ransomware-disk-write"):
    return escalations.record(
        signal_id=signal_id or f"rule-{rule}-0123abcd", resource_id=VM.format(vm), action=action,
        escalation_type=kind, reason="r", rule_name=rule)


def test_a_verdict_is_kept_on_the_card_independent_of_ack():
    esc = _card()
    escalations.resolve(esc)
    e = escalations.set_verdict(esc, "wrong", note="apt cache")
    assert (e["verdict"], e["verdict_note"], e["status"]) == ("wrong", "apt cache", "resolved")
    assert next(x for x in escalations.all_escalations() if x["id"] == esc)["verdict"] == "wrong"


def test_a_verdict_by_prefix_refuses_what_it_cant_tell_apart():
    esc = _card()
    assert escalations.set_verdict(esc[:8], "right")["id"] == esc
    with pytest.raises(ValueError):
        escalations.set_verdict(esc[:3], "right")          # too short to be safe
    with pytest.raises(ValueError):
        escalations.set_verdict(esc, "maybe")              # not a verdict
    with pytest.raises(KeyError):
        escalations.set_verdict("ffffffffff", "right")


def test_the_rule_of_a_card_is_recorded_or_read_from_its_signal():
    assert escalations.rule_of({"rule_name": "ssh-brute-force"}) == "ssh-brute-force"
    assert escalations.rule_of({"signal_id": "rule-sudo-privilege-escalation-1a2b3c4d"}) == "sudo-privilege-escalation"
    assert escalations.rule_of({"signal_id": "run001_detection"}) == ""


def test_the_report_counts_decisions_once_and_measures_disruptive_false_rate():
    a = _card("web")
    _card("web")                                            # re-fire: same card, occurrences 2
    b = _card("db", action="block_suspicious_ip", rule="ssh-brute-force")
    c = _card("api", action="snapshot", kind="low_confidence", rule="account-creation")
    escalations.record(signal_id="posture-x", resource_id=VM.format("web"), action="backup",
                       escalation_type="posture_gap", reason="r")          # not a decision
    escalations.record(signal_id="reassert-web-1a2b3c4d", resource_id=VM.format("web"),
                       action="isolate_vm", escalation_type="verification_failed", reason="r")
    escalations.set_verdict(a, "right")
    escalations.set_verdict(b, "wrong")
    escalations.set_verdict(c, "unsure")
    r = escalations.observation_report()
    assert r["cards"] == 3 and r["judged"] == 3
    assert r["disruptive"] == {"right": 1, "wrong": 1, "unsure": 0, "unjudged": 0, "false_rate": 0.5}
    assert r["by_rule"]["ssh-brute-force"]["wrong"] == 1
    assert r["by_action"]["snapshot"]["unsure"] == 1


def test_the_report_has_no_rate_before_anything_is_judged_and_honours_since():
    _card()
    r = escalations.observation_report()
    assert r["disruptive"]["false_rate"] is None and r["disruptive"]["unjudged"] == 1
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert escalations.observation_report(future)["cards"] == 0


def test_the_cli_judges_and_reports():
    from glorfindel.cli import cli
    esc = _card()
    res = CliRunner().invoke(cli, ["verdict", esc[:8], "wrong", "--note", "nightly backup"])
    assert res.exit_code == 0, res.output
    res = CliRunner().invoke(cli, ["report", "--since", "all", "--json"])
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["disruptive"]["false_rate"] == 1.0
    res = CliRunner().invoke(cli, ["verdict", "nope00", "right"])
    assert res.exit_code == 1 and "no card" in res.output
    assert CliRunner().invoke(cli, ["report", "--since", "7x"]).exit_code != 0


def test_the_api_judges_and_reports(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from .console_client import console
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    client = console()
    esc = _card()
    assert client.post(f"/api/escalations/{esc}/verdict", json={"verdict": "right"}).json() == {
        "ok": True, "verdict": "right"}
    assert "error" in client.post(f"/api/escalations/{esc}/verdict", json={"verdict": "?"}).json()
    assert client.get("/api/report?since=all").json()["disruptive"]["right"] == 1
    assert "error" in client.get("/api/report?since=soon").json()


def test_a_card_carries_the_rule_of_its_detection():
    """escalate_to_human passes the RulePoller's rule name — the report groups by it."""
    from glorfindel.agent import escalate_to_human
    state = {"signal": {"signal_id": "rule-ssh-brute-force-1a2b3c4d", "resource_id": VM.format("web"),
                        "ttp": "T1110.001", "severity": "high", "event": "detection",
                        "raw_signal": {}, "context": {"run_id": "r", "rule_name": "ssh-brute-force"}},
             "past_cycles": [], "incident": None, "dry_run": False, "reasoning": "", "confidence": 0.9,
             "action": "block_suspicious_ip", "reversible": True, "explanation": "", "escalate": True,
             "escalation_reason": "held", "outcome": None, "mode_hold": True}
    with patch.object(escalations, "record") as rec:
        escalate_to_human(state)
    assert rec.call_args.kwargs["rule_name"] == "ssh-brute-force"


# ── VP1c (#920): a card's time without a time zone ─────────────────────────────────────────────
# Measured on VP1b's review, 19/11: TO JUDGE and the observation report raised `TypeError` on a card
# whose time carried no zone, as soon as `since` carried one — and the recurrence made TO JUDGE raise
# even without `since`. The whole list fell (`/api/to-judge`), and the report with it. Such a time is
# never compared to one with a zone, nor taken for UTC: the card stays in TO JUDGE, flagged.

def _redate(esc_id: str, when: str) -> None:
    lines = escalations._STORE.read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e["id"] == esc_id:
            e["timestamp"] = e["first_seen"] = e["last_seen"] = when
        out.append(json.dumps(e))
    escalations._STORE.write_text("\n".join(out) + "\n")


def _naive(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(timezone.utc) + delta).replace(tzinfo=None).isoformat()


def _ip_card(vm: str, ip: str = "198.51.100.7") -> str:
    return escalations.record(signal_id="rule-ssh-brute-force-0123abcd", resource_id=VM.format(vm),
                              action="block_suspicious_ip", escalation_type="mode_hold", reason="r",
                              rule_name="ssh-brute-force", action_params={"ip": ip, "port": 22})


def test_to_judge_keeps_a_card_without_a_time_zone_flagged_whatever_since():
    """Alone, with a `since`: kept — never left out of a window that cannot be decided — and said."""
    n = _card("web")
    _redate(n, _naive(-timedelta(days=30)))                 # a month ago, were it UTC: never guessed
    since = datetime.now(timezone.utc) - timedelta(days=7)
    [card] = escalations.to_judge(since)
    assert card["id"] == n and card["time_unreadable"] is True
    assert [c["id"] for c in escalations.to_judge()] == [n]


def test_to_judge_keeps_a_card_whose_time_cannot_be_read_flagged():
    """A time that cannot be read at all is no more left out than one without a zone."""
    n = _card("web")
    _redate(n, "yesterday at noon")
    [card] = escalations.to_judge(datetime.now(timezone.utc) - timedelta(days=7))
    assert card["id"] == n and card["time_unreadable"] is True


def test_to_judge_holds_cards_with_and_without_a_zone_on_one_ip_without_since():
    """Two cards on one IP, one without a zone: the recurrence compares nothing it cannot place —
    the list holds, the card without a zone first (no limit ever cuts it)."""
    a = _ip_card("web")
    n = _ip_card("db")
    _redate(n, _naive(-timedelta(hours=1)))
    cards = escalations.to_judge()
    assert [c["id"] for c in cards] == [n, a]
    assert [c["time_unreadable"] for c in cards] == [True, False]
    assert cards[0]["recurrence"] is None and cards[1]["recurrence"] is None
    assert [c["id"] for c in escalations.to_judge(limit=1)] == [n]


def test_to_judge_witness_cards_with_a_zone_newest_first_window_held():
    """The witness: cards with a zone, as before — newest first by the time itself, an old one out of
    the window, none flagged. An offset other than UTC is ordered by the moment, never the string."""
    old, a, b = _card("old"), _card("a"), _card("b")
    now = datetime.now(timezone.utc)
    _redate(old, (now - timedelta(days=9)).isoformat())
    _redate(a, (now - timedelta(hours=2)).isoformat())
    _redate(b, (now - timedelta(hours=1)).astimezone(timezone(timedelta(hours=-5))).isoformat())
    cards = escalations.to_judge(now - timedelta(days=7))
    assert [c["id"] for c in cards] == [b, a]
    assert not any(c["time_unreadable"] for c in cards)


def test_a_since_without_a_time_zone_is_refused_never_compared():
    with pytest.raises(ValueError):
        escalations.to_judge(datetime.now())
    with pytest.raises(ValueError):
        escalations.observation_report(datetime.now())


def test_the_report_leaves_out_a_card_without_a_time_zone_and_says_it():
    """With a `since`: whether it lies in the window is not known — left out of the counts, said in
    `undated`. Without one, there is no window to decide: counted."""
    _card("web")
    n = _card("db")
    _redate(n, _naive())
    r = escalations.observation_report(datetime.now(timezone.utc) - timedelta(days=7))
    assert (r["cards"], r["undated"]) == (1, 1)
    r = escalations.observation_report()
    assert (r["cards"], r["undated"]) == (2, 0)


def test_the_report_witness_cards_with_a_zone():
    _card("web")
    old = _card("db")
    _redate(old, (datetime.now(timezone.utc) - timedelta(days=9)).isoformat())
    r = escalations.observation_report(datetime.now(timezone.utc) - timedelta(days=7))
    assert (r["cards"], r["undated"]) == (1, 0)


def test_the_cli_report_says_the_cards_without_a_time_zone_left_out():
    from glorfindel.cli import cli
    _redate(_card("db"), _naive())
    with patch("glorfindel.expected_sudo.summary", return_value={}), \
            patch("glorfindel.cli._print_expected_sudo"), patch("glorfindel.cli._print_memory"), \
            patch("glorfindel.cli._print_auditd"), patch("glorfindel.memory.age_census", return_value={}):
        res = CliRunner().invoke(cli, ["report", "--since", "7d"])
    assert res.exit_code == 0, res.output
    assert "1 card(s) left out: their time carries no time zone" in res.output


def test_recurrence_compares_only_times_with_a_zone():
    """A card without a zone has no recurrence (where it lies is not known), and is never counted in
    another's — whatever the order of the cards."""
    now = datetime.now(timezone.utc)
    naive = {"id": "n", "first_seen": (now - timedelta(hours=1)).replace(tzinfo=None).isoformat(),
             "action_params": {"ip": "198.51.100.7"}}
    zoned = {"id": "z", "first_seen": (now - timedelta(hours=2)).isoformat(), "action_params": {"ip": "198.51.100.7"}}
    me = {"id": "m", "first_seen": now.isoformat(), "action_params": {"ip": "198.51.100.7"}}
    assert escalations.recurrence(naive, [naive, zoned, me]) is None
    r = escalations.recurrence(me, [naive, zoned, me])
    assert r["previous"] == 1 and r["last_id"] == "z"
    r = escalations.recurrence(me, [zoned, naive, me])
    assert r["previous"] == 1 and r["last_id"] == "z"


def test_recurrence_witness_the_last_of_several_by_its_time():
    now = datetime.now(timezone.utc)
    ip = {"ip": "198.51.100.7"}
    first = {"id": "f", "first_seen": (now - timedelta(hours=3)).isoformat(), "action_params": ip}
    last = {"id": "l", "first_seen": (now - timedelta(hours=1)).astimezone(timezone(timedelta(hours=2))).isoformat(),
            "action_params": ip}
    me = {"id": "m", "first_seen": now.isoformat(), "action_params": ip}
    r = escalations.recurrence(me, [last, first, me])
    assert r == {"previous": 2, "last_id": "l", "last_seen": last["first_seen"], "last_verdict": None}


def test_pending_shows_a_card_without_a_time_zone_its_age_unknown():
    """`glorfindel pending` computed the card's age against an aware now: the card was said
    unreadable. It is shown, its time as written, its age unknown — never guessed."""
    from glorfindel.cli import cli
    n = _card("web")
    when = _naive()
    _redate(n, when)
    res = CliRunner().invoke(cli, ["pending"])
    assert res.exit_code == 0, res.output
    assert "illisible" not in res.output and "age unknown" in res.output
