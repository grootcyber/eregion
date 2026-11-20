"""Observation kit: the operator's verdict on each recommendation, and the report that
measures the false rate of disruptive ones — the number the autonomy decision rests on
(docs/observation.md)."""
from __future__ import annotations

import itertools
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
    # B4a: the same tables by confidence and by provenance as `glorfindel report --json`.
    assert {"by_confidence", "by_rule_confidence", "above_threshold", "by_provenance"} <= set(
        client.get("/api/report?since=all").json())
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


# ── B4a (#991): the report by confidence, by rule × band, above the gate's threshold, by provenance ─
# Before B4a the report counted the verdicts by action and by rule, never by confidence: the gate's
# threshold rested on no measure — what share of the decisions at 0.9 is judged right was not known.

SUB = "00000000-0000-0000-0000-0000000000b4"
ON_BENCH = f"/subscriptions/{SUB}/resourceGroups/rg-celebrimbor/providers/Microsoft.Compute/virtualMachines/{{}}"
IN_A_PARK = f"/subscriptions/{SUB}/resourceGroups/rg-shop/providers/Microsoft.Compute/virtualMachines/{{}}"
_seq = itertools.count()


@pytest.fixture
def gate(monkeypatch):
    """The gate's threshold and the bench as the tests set them — never the developer's shell."""
    monkeypatch.delenv("GLORFINDEL_CONFIDENCE_THRESHOLD", raising=False)
    monkeypatch.delenv("EREGION_BENCH", raising=False)
    return monkeypatch


def _decided(confidence, verdict=None, *, rule="ssh-brute-force", where=VM, **kw) -> str:
    """A decision card of its own (a VM of its own: never folded into another), judged when `verdict`."""
    n = next(_seq)
    esc = escalations.record(signal_id=f"rule-{rule}-{n:08x}", resource_id=where.format(f"vm{n}"),
                             action="isolate_vm", escalation_type="mode_hold", reason="r", rule_name=rule,
                             confidence=confidence, **kw)
    if verdict:
        escalations.set_verdict(esc, verdict)
    return esc


def _set(esc_id: str, **fields) -> None:
    """Fields of a card written as an older version, or another writer, would have left them."""
    out = []
    for line in escalations._STORE.read_text().splitlines():
        e = json.loads(line)
        if e["id"] == esc_id:
            e.update(fields)
        out.append(json.dumps(e))
    escalations._STORE.write_text("\n".join(out) + "\n")


def _report_cli(*args):
    from glorfindel.cli import cli
    with patch("glorfindel.expected_sudo.summary", return_value={}), \
            patch("glorfindel.cli._print_expected_sudo"), patch("glorfindel.cli._print_memory"), \
            patch("glorfindel.cli._print_auditd"), patch("glorfindel.memory.age_census", return_value={}):
        res = CliRunner().invoke(cli, ["report", "--since", "all", *args], env={"COLUMNS": "200"})
    assert res.exit_code == 0, res.output
    return res.output


def test_each_band_holds_its_bottom_never_its_top_and_the_last_holds_one(gate):
    for c in (0.49, 0.5, 0.69, 0.7, 0.79, 0.8, 0.89, 0.9, 1.0):
        _decided(c, "right")
    bands = escalations.observation_report()["by_confidence"]
    assert list(bands) == ["(0, 0.5)", "[0.5, 0.7)", "[0.7, 0.8)", "[0.8, 0.9)", "[0.9, 1]"]
    assert [b["right"] for b in bands.values()] == [1, 2, 2, 2, 2]


def test_a_share_is_said_on_ten_judged_cards_never_under(gate):
    """Each cell says its count; under ten judged, no share: `too_few`. An unsure verdict is judged,
    never judged right; a card not judged is in neither."""
    for verdict in ["right"] * 8 + ["wrong"]:
        _decided(0.95, verdict)
    _decided(0.95)
    cell = escalations.observation_report()["by_confidence"]["[0.9, 1]"]
    assert (cell["judged"], cell["unjudged"], cell["too_few"], cell["right_share"]) == (9, 1, True, None)
    _decided(0.95, "unsure")
    cell = escalations.observation_report()["by_confidence"]["[0.9, 1]"]
    assert (cell["right"], cell["wrong"], cell["unsure"], cell["unjudged"]) == (8, 1, 1, 1)
    assert (cell["judged"], cell["too_few"], cell["right_share"]) == (10, False, 0.8)


def test_the_band_is_the_confidence_the_card_showed_when_judged_never_its_first(gate):
    """A re-fire whose confidence moved rewrites the card's reason, explanation and confidence together —
    the first kept in `first_confidence`, shown by no console, bot or CLI. The verdict given after
    judges what the card showed."""
    card = dict(signal_id="rule-ssh-brute-force-0000aaaa", resource_id=VM.format("web"), action="isolate_vm",
                escalation_type="mode_hold", rule_name="ssh-brute-force")
    esc = escalations.record(**card, reason="first", confidence=0.6)
    escalations.record(**card, reason="later", confidence=0.95)
    e = escalations.card_of(esc)
    assert (e["first_confidence"], e["confidence"], e["reason"]) == (0.6, 0.95, "later")
    escalations.set_verdict(esc, "right")
    r = escalations.observation_report()
    assert r["by_confidence"]["[0.9, 1]"]["right"] == 1
    assert r["by_confidence"]["[0.5, 0.7)"]["judged"] == 0 and r["confidence_unknown"]["judged"] == 0


def test_a_card_rewritten_after_its_verdict_has_no_confidence_judged(gate):
    """`glorfindel verdict` leaves the card pending: a re-fire may rewrite it after. The confidence judged
    is then no longer on the card — out of the bands, counted apart, never guessed. Judged again, it
    judges what the card shows."""
    card = dict(signal_id="rule-ssh-brute-force-0000bbbb", resource_id=VM.format("db"), action="isolate_vm",
                escalation_type="mode_hold", rule_name="ssh-brute-force", reason="r")
    esc = escalations.record(**card, confidence=0.6)
    escalations.set_verdict(esc, "right")
    _set(esc, verdict_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat())
    escalations.record(**card, confidence=0.95)
    r = escalations.observation_report()
    assert r["confidence_unknown"]["right"] == 1
    assert sum(b["judged"] for b in r["by_confidence"].values()) == 0
    _set(esc, verdict_at="yesterday")                       # unreadable: the order is not known
    assert escalations.observation_report()["confidence_unknown"]["right"] == 1
    escalations.set_verdict(esc, "right")
    assert escalations.observation_report()["by_confidence"]["[0.9, 1]"]["right"] == 1


def test_a_card_without_a_confidence_of_the_model_is_left_out_of_the_bands_and_counted(gate):
    """0 is record's default — a failed cycle, a detection without a decision of the model —, which the
    console and the bot show as no confidence. Nor is a confidence what is no number of (0, 1]."""
    _decided(0.0, "wrong")
    escalations.set_verdict(escalations.record(
        signal_id="rule-ssh-brute-force-0000cccc", resource_id=VM.format("failed"), action="",
        escalation_type="cycle_failed", reason="the model's call failed", rule_name="ssh-brute-force"), "unsure")
    for odd in ("0.9", True, float("nan"), 1.5, -0.2, None):
        _set(_decided(0.9, "right"), confidence=odd)
    r = escalations.observation_report()
    assert (r["confidence_unknown"]["judged"], r["confidence_unknown"]["right"]) == (8, 6)
    assert sum(b["judged"] + b["unjudged"] for b in r["by_confidence"].values()) == 0
    assert r["by_rule_confidence"] == {} and r["above_threshold"]["judged"] == 0
    assert r["by_rule"]["ssh-brute-force"]["right"] == 6     # the other tables count them as before


def test_above_the_threshold_counts_what_the_gate_would_let_through_at_its_configured_value(gate):
    gate.setenv("GLORFINDEL_CONFIDENCE_THRESHOLD", "0.85")
    _decided(0.84, "wrong")
    _decided(0.85, "right")                         # the gate's own comparison: at the threshold, through
    _decided(0.9, "right")
    _decided(0.95)
    a = escalations.observation_report()["above_threshold"]
    assert (a["threshold"], a["right"], a["wrong"], a["unjudged"], a["judged"]) == (0.85, 2, 0, 1, 2)
    assert (a["too_few"], a["right_share"]) == (True, None)
    gate.delenv("GLORFINDEL_CONFIDENCE_THRESHOLD")
    a = escalations.observation_report()["above_threshold"]
    assert (a["threshold"], a["wrong"], a["judged"]) == (0.7, 1, 3)        # unset: the gate's 0.7


def test_a_malformed_threshold_lets_nothing_above_it_and_is_said(gate):
    gate.setenv("GLORFINDEL_CONFIDENCE_THRESHOLD", "O.95")
    _decided(0.99, "right")
    r = escalations.observation_report()
    assert r["above_threshold"]["threshold"] is None
    assert (r["above_threshold"]["judged"], r["above_threshold"]["unjudged"]) == (0, 0)
    json.dumps(r, allow_nan=False)                  # no Infinity in the JSON
    assert "GLORFINDEL_CONFIDENCE_THRESHOLD invalid" in _report_cli()


def test_rule_by_band_counts_each_rule_in_its_own_bands(gate):
    _decided(0.95, "right")
    _decided(0.95, "wrong")
    _decided(0.75, "wrong", rule="sudo-privilege-escalation")
    _decided(0.75, rule="sudo-privilege-escalation")
    rows = escalations.observation_report()["by_rule_confidence"]
    assert {rule: list(bands) for rule, bands in rows.items()} == {
        "ssh-brute-force": ["[0.9, 1]"], "sudo-privilege-escalation": ["[0.7, 0.8)"]}
    ssh, sudo = rows["ssh-brute-force"]["[0.9, 1]"], rows["sudo-privilege-escalation"]["[0.7, 0.8)"]
    assert (ssh["right"], ssh["wrong"], ssh["judged"], ssh["too_few"]) == (1, 1, 2, True)
    assert (sudo["wrong"], sudo["unjudged"], sudo["judged"]) == (1, 1, 1)


def test_the_bands_leave_the_exercises_out_as_the_report_does(gate):
    _decided(0.95, "right", source="exercise", exercise_run="run-1")
    r = escalations.observation_report()
    assert r["exercises"] == 1
    assert sum(b["judged"] for b in r["by_confidence"].values()) == 0
    assert sum(c["judged"] for c in r["by_provenance"].values()) == 0


def test_provenance_the_bench_is_its_perimeter_read_from_the_card_alone(gate):
    """bree, the VM of the pre-observation, is in the bench's group and enrolled nowhere: its cards are the
    bench's. A park's, another subscription's, and a card attributed to no VM (filed on a bench VM, about
    none) are unknown — and no read of Azure is made."""
    gate.setenv("AZURE_SUBSCRIPTION_ID", SUB)

    def no_call(*a, **k):
        raise AssertionError("the report reads the cards alone")
    gate.setattr("requests.get", no_call)
    gate.setattr("glorfindel.gestures.TAGS_READER", no_call)
    _decided(0.9, "right", where=ON_BENCH)
    _decided(0.9, "wrong", where=IN_A_PARK)
    _decided(0.9, "wrong", where=ON_BENCH.replace(SUB, "00000000-0000-0000-0000-00000000ffff"))
    _decided(0.9, "unsure", where=ON_BENCH, attribution={"state": "unattributed", "candidates": ["a", "b"]})
    where = escalations.observation_report()["by_provenance"]
    assert list(where) == ["bench", "unknown"]
    assert (where["bench"]["right"], where["bench"]["judged"]) == (1, 1)
    assert (where["unknown"]["wrong"], where["unknown"]["unsure"], where["unknown"]["judged"]) == (2, 1, 3)
    gate.delenv("AZURE_SUBSCRIPTION_ID")            # the perimeter names no subscription: none is the bench's
    assert escalations.observation_report()["by_provenance"]["bench"]["judged"] == 0


def test_the_cli_says_each_band_with_its_count_and_too_few_never_a_percentage(gate):
    for verdict in ["right"] * 9 + ["wrong"]:
        _decided(0.95, verdict)
    for _ in range(3):
        _decided(0.75, "right")
    _decided(0.0, "wrong")
    out = _report_cli()
    lines = out.splitlines()
    few = next(line for line in lines if "[0.7, 0.8)" in line)        # the first table's row
    assert "too few" in few and "%" not in few
    assert "90%" in next(line for line in lines if "[0.9, 1]" in line)
    assert "Above the gate's threshold (≥ 0.7): 13 judged" in out
    assert "1 card(s) left out of the bands (1 judged)" in out
    assert "By detection rule × confidence" in out and "By provenance" in out
    r = json.loads(_report_cli("--json"))
    assert r["by_confidence"]["[0.9, 1]"]["right_share"] == 0.9 and r["few_judged"] == 10
    assert r["above_threshold"]["judged"] == 13 and r["confidence_unknown"]["wrong"] == 1


def test_provenance_a_card_held_by_the_attribution_guard_before_slf1_is_unknown(gate):
    """B4a, review: the older shape of a card attributed to no VM — `unattributed_signal`, no
    `attribution` field — is unknown too, filed on a bench VM though it is about none."""
    gate.setenv("AZURE_SUBSCRIPTION_ID", SUB)
    old = _decided(0.9, "right", where=ON_BENCH)
    _set(old, escalation_type="unattributed_signal")
    _decided(0.9, "right", where=ON_BENCH)
    where = escalations.observation_report()["by_provenance"]
    assert (where["bench"]["right"], where["unknown"]["right"]) == (1, 1)
