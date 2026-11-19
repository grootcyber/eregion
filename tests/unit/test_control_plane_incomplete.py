"""CPT1 (#930): a row of the control plane that names neither its caller nor its resource is a card
of incomplete telemetry — visible in TO JUDGE, of a lower severity than high, never approvable,
never dropped — and a row that names one of the two keeps the card it had.

Seen on Imladris (~3 days, 19/11): `role-assignment-write` and `nsg-change-outside-glorfindel` made
high cards that read « … par appelant inconnu sur ? »: no one could judge them. Two things here:
  - the card read its caller in `Caller` alone, though the rules project the ids they draw from
    `Claims` (`CallerAppId`, `CallerObjectId`): a row with an empty `Caller` and an id in `Claims`
    said « appelant inconnu » (the extraction, corrected: the card names the id);
  - a row that names no one and nothing — the platform's own event, or a line of an operation
    that Azure wrote without its resource and that the rules' `by … _ResourceId` keeps apart from
    its other lines (to be read on the workspace) — is a card « Télémétrie incomplète », `medium`.

The shipped queries run as written (`tests/unit/kql_subset.py`) on lines shaped like
AzureActivity's, through the real AzureActivityDetector, the RulePoller and the graph. Every
identifier is made up (repository public). No Azure, no model.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from glorfindel.agent import INCOMPLETE_TELEMETRY, _control_plane_text
from glorfindel.detection_rules import _control_plane_summary, names_no_one, normalize_row
from glorfindel.providers.azure.monitor import AzureMonitorDetector

from . import kql_subset
from . import test_activity_operation_read as op_read
from .test_activity_logs import _graph, _initial, _llm
from .test_activity_operation_read import (  # noqa: F401 — its clock, set when each test starts
    OUTSIDER, OUTSIDER_OID, RULES, _line, _now_when_the_test_starts, _poller,
)

TWO = ("role-assignment-write", "nsg-change-outside-glorfindel")
APP = "c4444444-d444-e444-f444-a44444444444"


@pytest.fixture(autouse=True)
def _no_ambient_identity(monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)


@pytest.fixture()
def workspace(monkeypatch):
    """The workspace runs the rule's query on the lines it holds (as test_activity_operation_read's)."""
    lines: list[dict] = []

    def run_query(self, query, timespan=None):
        return [{k: (v.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(v, datetime) else v)
                 for k, v in r.items()} for r in kql_subset.run(query, lines, now=op_read.NOW)]
    monkeypatch.setattr(AzureMonitorDetector, "run_query", run_query)
    return lines


def _bare(rule, status, minutes_ago, **kw):
    """A line that names no caller (no Caller, no address, no Claims) and no resource."""
    line = _line(rule, status, minutes_ago, bare=True, **kw)
    line["_ResourceId"] = ""
    return line


def _signal(workspace, rule_name, lines):
    p, rule, sent = _poller(rule_name)
    workspace += lines
    p.poll_once(rule)
    assert len(sent) == 1, sent
    return sent[0]


def _card(tmp_path, monkeypatch, signal):
    """The graph on the signal, the model never asked, nothing run — its card."""
    from glorfindel import escalations
    connector = MagicMock()
    connector.dry_run = False
    with patch("litellm.completion", return_value=_llm("isolate_vm")) as llm:
        final = _graph(tmp_path, monkeypatch, connector).invoke(_initial(signal))
    llm.assert_not_called()
    for name in ("isolate_vm", "block_suspicious_ip", "snapshot", "release_isolation"):
        getattr(connector, name).assert_not_called()
    cards = escalations.pending()
    assert len(cards) == 1, cards
    return final, cards[0]


# ── a row that names no one and nothing ───────────────────────────────────────────

@pytest.mark.parametrize("rule_name", TWO)
def test_a_bare_line_on_each_rule_is_a_card_of_incomplete_telemetry(tmp_path, monkeypatch, workspace, rule_name):
    """Fini quand: never a high card, never nothing — a card, `medium`, that says so."""
    from glorfindel import escalations
    sig = _signal(workspace, rule_name, [_bare(rule_name, "Start", 6), _bare(rule_name, "Success", 5)])
    row = sig["raw_signal"]["first_result_row"]
    assert (row["Caller"], row["CallerObjectId"], row["CallerAppId"], row["_ResourceId"]) == ("", "", "", "")
    assert row["OperationNameValue"] == RULES[rule_name][0]
    assert sig["severity"] == "medium"
    final, card = _card(tmp_path, monkeypatch, sig)
    assert final["held_by"] == "control_plane_incomplete" and final["action"] == ""
    assert card["escalation_type"] == "control_plane_change"
    assert card["severity"] == "medium"
    assert card["reason"].startswith(INCOMPLETE_TELEMETRY) and "Sévérité : moyenne" in card["reason"]
    assert "ni l'appelant" in card["explanation"] and "ni la ressource" in card["explanation"]
    assert card["suggested_steps"][0].startswith("Lire toutes les lignes de cette opération")
    # Visible where the operator judges.
    assert [c["id"] for c in escalations.to_judge()] == [card["id"]]
    assert escalations.to_judge()[0]["severity"] == "medium"


@pytest.mark.parametrize("rule_name", TWO)
def test_the_card_of_incomplete_telemetry_is_never_approvable(tmp_path, monkeypatch, workspace, rule_name):
    """No action to run, no verb signed, refused by the console and the bot's approval alike — even
    fresh, even with an action written on it."""
    from eregion_core import action_queue
    from eregion_console.api import _approval_refusal
    from glorfindel.approval import approval_refusal
    sig = _signal(workspace, rule_name, [_bare(rule_name, "Start", 6), _bare(rule_name, "Success", 5)])
    _final, card = _card(tmp_path, monkeypatch, sig)
    assert card["escalation_type"] not in action_queue.APPROVABLE_TYPES
    assert action_queue.proposed_verbs(card) == frozenset()
    for esc in (card, {**card, "action": "isolate_vm"}, {**card, "action": "block_suspicious_ip"}):
        assert approval_refusal(esc, "vm1") and _approval_refusal(esc, "vm1")
        assert action_queue.proposed_verbs(esc) == frozenset()


def test_two_bare_operations_are_two_cards_never_one(tmp_path, monkeypatch, workspace):
    """Each is one operation, never folded into the other: both stay to judge."""
    from glorfindel import escalations
    rule_name = "role-assignment-write"
    p, rule, sent = _poller(rule_name)
    workspace += [_bare(rule_name, "Success", 6, corr="c-a"), _bare(rule_name, "Success", 5, corr="c-b")]
    p.poll_once(rule)
    assert [s["severity"] for s in sent] == ["medium", "medium"]
    for s in sent:
        _graph(tmp_path, monkeypatch, MagicMock(dry_run=False)).invoke(_initial(s))
    assert len(escalations.to_judge()) == 2
    p.poll_once(rule)                                    # the same operations: no card more
    assert len(sent) == 2


def test_a_high_signal_on_a_bare_row_is_still_a_medium_card(tmp_path, monkeypatch, workspace):
    """A signal that came high (written before CPT1, replayed): `decide` lowers it — never a high
    card on a row that names no one and nothing."""
    rule_name = "nsg-change-outside-glorfindel"
    sig = _signal(workspace, rule_name, [_bare(rule_name, "Success", 5)])
    final, card = _card(tmp_path, monkeypatch, {**sig, "severity": "high"})
    assert card["severity"] == "medium" and final["signal"]["severity"] == "medium"
    assert "Sévérité : moyenne" in card["reason"]


# ── a row that names one of the two: as before ──────────────────────────────────

@pytest.mark.parametrize("rule_name", TWO)
def test_a_line_naming_only_its_caller_keeps_its_high_card(tmp_path, monkeypatch, workspace, rule_name):
    lines = [_line(rule_name, "Start", 6), _line(rule_name, "Success", 5)]
    for line in lines:
        line["_ResourceId"] = ""
    sig = _signal(workspace, rule_name, lines)
    assert sig["severity"] == "high"
    final, card = _card(tmp_path, monkeypatch, sig)
    assert final["held_by"] == "control_plane"
    assert card["severity"] == "high" and INCOMPLETE_TELEMETRY not in card["reason"]
    assert f"par {OUTSIDER}" in card["explanation"]


@pytest.mark.parametrize("rule_name", TWO)
def test_a_line_naming_only_its_resource_keeps_its_high_card(tmp_path, monkeypatch, workspace, rule_name):
    lines = [_line(rule_name, "Start", 6, bare=True), _line(rule_name, "Success", 5, bare=True)]
    sig = _signal(workspace, rule_name, lines)
    assert sig["raw_signal"]["first_result_row"]["Caller"] == ""
    assert sig["severity"] == "high"
    final, card = _card(tmp_path, monkeypatch, sig)
    assert final["held_by"] == "control_plane"
    assert card["severity"] == "high" and INCOMPLETE_TELEMETRY not in card["reason"]
    assert "appelant inconnu" in card["explanation"]


@pytest.mark.parametrize("rule_name", TWO)
def test_a_complete_line_is_read_as_before(tmp_path, monkeypatch, workspace, rule_name):
    """The witness: its caller, its resource, `high`, the card of AL1."""
    sig = _signal(workspace, rule_name, [_line(rule_name, "Start", 6), _line(rule_name, "Success", 5)])
    assert sig["severity"] == "high"
    final, card = _card(tmp_path, monkeypatch, sig)
    assert final["held_by"] == "control_plane"
    assert card["severity"] == "high" and INCOMPLETE_TELEMETRY not in card["reason"]
    assert card["explanation"].startswith("Plan de contrôle : ")
    assert f"par {OUTSIDER}" in card["explanation"] and "Sévérité : haute" in card["reason"]


# ── the extraction: the caller's ids the rules draw from Claims ──────────────────

@pytest.mark.parametrize("rule_name", TWO)
def test_an_empty_caller_with_its_object_id_in_claims_is_named(tmp_path, monkeypatch, workspace, rule_name):
    """The form that said « appelant inconnu » though the row carried the caller: `Caller` empty,
    its object id in `Claims` (projected as CallerObjectId). Named, and the card stays high."""
    lines = [_line(rule_name, "Start", 6, caller=""), _line(rule_name, "Success", 5, caller="")]
    sig = _signal(workspace, rule_name, lines)
    row = sig["raw_signal"]["first_result_row"]
    assert (row["Caller"], row["CallerObjectId"]) == ("", OUTSIDER_OID)
    assert sig["severity"] == "high"
    _final, card = _card(tmp_path, monkeypatch, sig)
    assert "appelant inconnu" not in card["explanation"] and OUTSIDER_OID in card["explanation"]
    assert card["severity"] == "high"


@pytest.mark.parametrize("rule_name", TWO)
def test_an_empty_caller_with_only_an_application_id_is_named_as_an_application(
        tmp_path, monkeypatch, workspace, rule_name):
    lines = [_line(rule_name, "Success", 5, caller="", oid="", app=APP)]
    sig = _signal(workspace, rule_name, lines)
    assert sig["raw_signal"]["first_result_row"]["CallerAppId"] == APP
    _final, card = _card(tmp_path, monkeypatch, sig)
    assert f"l'application {APP}" in card["explanation"] and "appelant inconnu" not in card["explanation"]
    assert card["severity"] == "high"


# ── what is never a card of incomplete telemetry ──────────────────────────────────

_BARE_ROW = {"OperationNameValue": RULES["role-assignment-write"][0], "ActivityStatusValue": "Success",
             "Caller": "", "CallerIpAddress": "", "CallerAppId": "", "CallerObjectId": "",
             "_ResourceId": "", "ResourceGroup": "", "CorrelationId": "c-1", "Succeeded": 1, "Callers": 0}


def test_names_no_one_reads_every_column_that_names_a_caller_or_a_resource():
    assert names_no_one(_BARE_ROW)
    for col, value in (("Caller", OUTSIDER), ("CallerAppId", APP), ("CallerObjectId", OUTSIDER_OID),
                       ("_ResourceId", RULES["role-assignment-write"][1]),
                       ("ResourceId", RULES["role-assignment-write"][1])):
        assert not names_no_one({**_BARE_ROW, col: value}), col
    # A rule that projects Claims (a client's): the ids in it name the caller.
    assert not names_no_one({**_BARE_ROW, "Claims": json.dumps({"appid": APP})})
    assert not names_no_one({**_BARE_ROW, "Claims_d": {"oid": OUTSIDER_OID}})
    assert names_no_one({**_BARE_ROW, "Claims": "{}"}) and names_no_one({**_BARE_ROW, "Claims": "nope"})
    # Blank is nothing.
    assert names_no_one({**_BARE_ROW, "Caller": "  ", "_ResourceId": " "})


def test_a_row_whose_lines_name_several_callers_is_not_missing_telemetry():
    """AL1d: its lines name callers, the row keeps none — the card says to read each; high."""
    assert not names_no_one({**_BARE_ROW, "Callers": 2})


@pytest.mark.parametrize("mark", [{"GlorfindelManaged": True}, {"GlorfindelIdentity": True},
                                  {"GlorfindelRunCommand": "caller_unreadable"}])
def test_a_grave_row_is_never_lowered(mark):
    assert not names_no_one({**_BARE_ROW, **mark})


def test_a_summary_card_and_a_data_row_are_not_cards_of_incomplete_telemetry():
    assert not names_no_one({**_BARE_ROW, "OmittedOperations": [dict(_BARE_ROW)]})
    assert not names_no_one({"Computer": "vm1", "SyslogMessage": "x"})
    assert not names_no_one({**_BARE_ROW, "OperationNameValue": ""})


# ── CPT1b (#940): the summary card names who and what, as each individual card does ──────────
#
# Past 5 operations in one poll (SEC2), one summary card lists the others (`OmittedOperations`).
# It read each one's caller in `Caller` alone, « ? » else: an operation whose caller the rules name
# from `Claims` (`CallerObjectId`, `CallerAppId`) read « … par ? sur … », whereas its own card would
# have named it. Each operation is now read by the individual card's readings (`_caller_said`,
# `operation_resource`); a true void stays « appelant inconnu ». The shipped queries never give a row
# without its `OperationNameValue`: the « ? » of an operation cannot come from them.

UPN_URI = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn"
NAME_URI = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
SOMEONE_ELSE = "someone-else@example.org"


def _target(rule_name, i):
    return f"{RULES[rule_name][1]}-{i}"


def _ops(rule_name, n, **kw):
    """n operations of the rule, each its own CorrelationId and resource, the oldest last."""
    return [_line(rule_name, "Success", 5 + i, corr=f"c-{i}", target=_target(rule_name, i), **kw)
            for i in range(n)]


def _summary_of(workspace, rule_name, lines):
    p, rule, sent = _poller(rule_name)
    workspace += lines
    p.poll_once(rule)
    summaries = [s for s in sent if s["raw_signal"]["first_result_row"].get("OmittedOperations")]
    assert len(sent) == 6 and len(summaries) == 1 and sent[-1] is summaries[0], sent
    return summaries[0]


def _listed(signal):
    return _control_plane_text(signal)[0]


@pytest.mark.parametrize("rule_name", TWO)
def test_a_summary_card_names_the_caller_and_the_resource_of_each_operation(
        tmp_path, monkeypatch, workspace, rule_name):
    """Fini quand: more than 5 operations that the log names — the summary names each one's caller
    and resource, never « ? »; its card, through the graph, says the same."""
    sig = _summary_of(workspace, rule_name, _ops(rule_name, 8))
    what = _listed(sig)
    assert "3 opération(s) de plus" in what
    for i in (5, 6, 7):
        assert f"par {OUTSIDER} sur {_target(rule_name, i)} (" in what, what
    assert "par ?" not in what and "sur ?" not in what and "appelant inconnu" not in what
    _final, card = _card(tmp_path, monkeypatch, sig)
    assert card["severity"] == "high" and INCOMPLETE_TELEMETRY not in card["reason"]
    for i in (5, 6, 7):
        assert f"par {OUTSIDER} sur {_target(rule_name, i)} (" in card["explanation"]


@pytest.mark.parametrize("rule_name", TWO)
def test_a_summary_operation_whose_caller_is_in_claims_alone_is_named(workspace, rule_name):
    """The form that read « par ? »: `Caller` empty, the caller's object id in `Claims` (the rules
    project it as CallerObjectId) — named as its own card names it; the application id alone too."""
    lines = _ops(rule_name, 6) + [
        _line(rule_name, "Success", 30, corr="c-oid", target=_target(rule_name, "oid"), caller=""),
        _line(rule_name, "Success", 31, corr="c-app", target=_target(rule_name, "app"), caller="",
              oid="", app=APP)]
    sig = _summary_of(workspace, rule_name, lines)
    omitted = sig["raw_signal"]["first_result_row"]["OmittedOperations"]
    assert [(o["Caller"], o["CallerObjectId"], o["CallerAppId"]) for o in omitted[-2:]] == [
        ("", OUTSIDER_OID, ""), ("", "", APP)]
    what = _listed(sig)
    assert (f"par l'identité d'objet {OUTSIDER_OID} (lue dans Claims, Caller vide) sur "
            f"{_target(rule_name, 'oid')} (") in what
    assert f"par l'application {APP} (lue dans Claims, Caller vide" in what
    assert f"sur {_target(rule_name, 'app')} (" in what
    assert "par ?" not in what and "appelant inconnu" not in what


@pytest.mark.parametrize("rule_name", TWO)
def test_a_true_void_in_a_summary_stays_unknown(workspace, rule_name):
    """An operation whose lines name no one and nothing: « appelant inconnu », its resource « ? » —
    nothing made up; the others of the summary still named."""
    lines = _ops(rule_name, 7) + [_bare(rule_name, "Success", 30, corr="c-bare")]
    sig = _summary_of(workspace, rule_name, lines)
    what = _listed(sig)
    assert f"{RULES[rule_name][0]} par appelant inconnu sur ? (" in what
    assert what.count("appelant inconnu") == 1
    for i in (5, 6):
        assert f"par {OUTSIDER} sur {_target(rule_name, i)} (" in what


def test_a_summary_reads_what_a_clients_rule_projects():
    """A rule that projects `Claims` itself and `ResourceId` (a client's): each operation is read by
    the same readings as its own card — its name in Claims (the long URIs), its oid, its app, its
    resource."""
    op = RULES["role-assignment-write"][0]
    rows = [{"OperationNameValue": op, "TimeGenerated": f"2026-11-19T10:00:0{i}Z", "CorrelationId": f"c-{i}",
             "ResourceId": f"/subscriptions/x/r-{i}", "Claims": json.dumps(claims)}
            for i, claims in enumerate([{UPN_URI: SOMEONE_ELSE}, {NAME_URI: "Some One"},
                                        {"oid": OUTSIDER_OID}, {"azp": APP}])]
    summary = _control_plane_summary(rows)
    listed = _listed({"raw_signal": {"first_result_row": summary}})
    for row, entry in zip(rows, summary["OmittedOperations"]):
        own_card = _listed({"raw_signal": {"first_result_row": row}})
        who = own_card.split(" par ", 1)[1].split(" sur ", 1)[0]
        assert who != "appelant inconnu" and f"par {who} sur {row['ResourceId']} (" in listed, who
        assert entry["_ResourceId"] == row["ResourceId"]
    assert [e["CallerName"] for e in summary["OmittedOperations"]] == [SOMEONE_ELSE, "Some One", "", ""]
    assert [e["CallerObjectId"] for e in summary["OmittedOperations"]] == ["", "", OUTSIDER_OID, ""]
    assert [e["CallerAppId"] for e in summary["OmittedOperations"]] == ["", "", "", APP]


def test_an_older_summary_card_with_caller_alone_reads_as_before():
    """A summary written before CPT1b (its operations with `Caller` alone): read as it was, a true
    void said « appelant inconnu »."""
    op = RULES["role-assignment-write"][0]
    row = {"OperationNameValue": op, "OmittedOperations": [
        {"OperationNameValue": op, "Caller": OUTSIDER, "_ResourceId": "/r/1", "TimeGenerated": ""},
        {"OperationNameValue": op, "Caller": "", "_ResourceId": "", "TimeGenerated": ""}]}
    what = _listed({"raw_signal": {"first_result_row": row}})
    assert f"{op} par {OUTSIDER} sur /r/1 ()" in what and f"{op} par appelant inconnu sur ? ()" in what


@pytest.mark.parametrize("rule_name", TWO)
def test_the_individual_card_is_unchanged(workspace, rule_name):
    """The witness: the five individual cards of the same poll read word for word as before."""
    p, rule, sent = _poller(rule_name)
    workspace += _ops(rule_name, 8)
    p.poll_once(rule)
    for i, sig in enumerate(sent[:5]):
        assert _listed(sig) == (f"Plan de contrôle : {RULES[rule_name][0]} (Success) par {OUTSIDER} "
                                f"depuis 203.0.113.7 sur {_target(rule_name, i)}.")
        assert sig["raw_signal"]["normalized_signal"]["resource"] == _target(rule_name, i)


@pytest.mark.parametrize("rule_name", TWO)
def test_the_shipped_queries_never_give_an_operation_without_its_name(rule_name):
    """The other path to « ? » — a row without `OperationNameValue` — cannot come from these two
    rules: they keep only their operations and group by it; bare lines, named ones, all statuses."""
    lines = (_ops(rule_name, 3) + [_bare(rule_name, s, 6 + k, corr=f"b-{k}")
                                   for k, s in enumerate(("Start", "Accept", "Success"))]
             + [_line(rule_name, "Success", 9, op="MICROSOFT.X/Y/WRITE", corr="c-other")])
    rows = kql_subset.run(op_read.SHIPPED[rule_name]["query"], lines, now=op_read.NOW)
    assert len(rows) == 6
    assert all(r["OperationNameValue"] == RULES[rule_name][0] for r in rows)
    assert all(normalize_row(r)["indicator_value"] == RULES[rule_name][0] for r in rows)


# ── CPT1b: the limits CPT1's review left ─────────────────────────────────────────

def test_a_critical_signal_on_a_bare_row_never_says_lower_severity(tmp_path, monkeypatch, workspace):
    """« Télémétrie incomplète … Sévérité moindre » only when the card is lowered: a signal that came
    critical stays critical, and its text says no lower severity."""
    rule_name = "role-assignment-write"
    sig = _signal(workspace, rule_name, [_bare(rule_name, "Success", 5)])
    critical = {**sig, "severity": "critical"}
    what, _steps = _control_plane_text(critical)
    assert INCOMPLETE_TELEMETRY not in what and "Sévérité moindre" not in what
    final, card = _card(tmp_path, monkeypatch, critical)
    assert card["severity"] == "critical" and final["held_by"] == "control_plane"
    assert "Sévérité : critique" in card["reason"] and "Sévérité moindre" not in card["reason"]
    # Lowered, it says so.
    assert "Sévérité moindre" in _listed(sig)


@pytest.mark.parametrize("claim", [UPN_URI, NAME_URI])
def test_the_long_uris_of_upn_and_name_name_the_caller(claim):
    """`Claims` as the Activity Log writes it: the long URIs of `upn` and `name` name the caller —
    the row is no incomplete telemetry, and its card names them."""
    row = {**_BARE_ROW, "Claims": json.dumps({claim: SOMEONE_ELSE})}
    assert not names_no_one(row)
    assert not names_no_one({**_BARE_ROW, "Claims_d": {claim: SOMEONE_ELSE}})
    what = _listed({"raw_signal": {"first_result_row": row}})
    assert f"par {SOMEONE_ELSE} (lu dans Claims, Caller vide)" in what and INCOMPLETE_TELEMETRY not in what


def test_a_clients_rule_that_projects_the_callers_name_alone_is_not_lowered():
    """A client's rule that projects `CallerName` alone (no `Caller`, no ids, no Claims): the row
    names its caller — never « ne nomme ni l'appelant … par ops@… »; the card high, the name said."""
    row = {**_BARE_ROW, "CallerName": "ops@example.org"}
    assert not names_no_one(row)
    what = _listed({"raw_signal": {"first_result_row": row}})
    assert INCOMPLETE_TELEMETRY not in what and "par ops@example.org (lu dans Claims, Caller vide)" in what
    assert names_no_one({**_BARE_ROW, "CallerName": "  "})       # blank is nothing


def test_the_short_name_claim_names_the_caller():
    """The short `name` claim, read on the prudent side: the row is no incomplete telemetry, and
    its card names it."""
    row = {**_BARE_ROW, "Claims": json.dumps({"name": "Some One"})}
    assert not names_no_one(row)
    what = _listed({"raw_signal": {"first_result_row": row}})
    assert "par Some One (lu dans Claims, Caller vide)" in what and INCOMPLETE_TELEMETRY not in what


def test_the_caller_is_named_by_its_name_then_its_object_id_then_its_application():
    """`Caller` empty: a name first, then the object id, then the application — on its own card as
    on a summary's."""
    both = json.dumps({UPN_URI: SOMEONE_ELSE, "oid": OUTSIDER_OID, "appid": APP})
    ids = json.dumps({"oid": OUTSIDER_OID, "appid": APP})
    for claims, said, unsaid in ((both, f"par {SOMEONE_ELSE} (lu dans Claims", (OUTSIDER_OID, APP)),
                                 (ids, f"par l'identité d'objet {OUTSIDER_OID}", (APP, SOMEONE_ELSE))):
        row = {**_BARE_ROW, "Claims": claims}
        summary = _control_plane_summary([dict(row, CorrelationId=f"c-{i}") for i in range(2)])
        for what in (_listed({"raw_signal": {"first_result_row": row}}),
                     _listed({"raw_signal": {"first_result_row": summary}})):
            assert said in what, what
            assert all(u not in what for u in unsaid), what
    # The columns the shipped rules project, in the same order.
    what = _listed({"raw_signal": {"first_result_row": {
        **_BARE_ROW, "CallerObjectId": OUTSIDER_OID, "CallerAppId": APP}}})
    assert f"par l'identité d'objet {OUTSIDER_OID}" in what and APP not in what


def test_a_row_with_the_callers_address_alone_is_lowered(tmp_path, monkeypatch, workspace):
    """As the doc says: an address (`CallerIpAddress`) names no caller — the row is incomplete
    telemetry, its card `medium`, and says the address it read."""
    assert names_no_one({**_BARE_ROW, "CallerIpAddress": "203.0.113.7"})
    rule_name = "nsg-change-outside-glorfindel"
    line = _bare(rule_name, "Success", 5)
    line["CallerIpAddress"] = "203.0.113.7"
    sig = _signal(workspace, rule_name, [line])
    assert sig["raw_signal"]["first_result_row"]["CallerIpAddress"] == "203.0.113.7"
    assert sig["severity"] == "medium"
    _final, card = _card(tmp_path, monkeypatch, sig)
    assert card["severity"] == "medium" and card["reason"].startswith(INCOMPLETE_TELEMETRY)
    assert "depuis 203.0.113.7" in card["explanation"]


def test_the_console_feed_names_a_card_of_incomplete_telemetry():
    """The console's feed (glorfindel.js, read in its text: no browser in the suite) says what holds
    the card, never « review »."""
    js = (Path(__file__).resolve().parents[2] / "eregion_console/static/glorfindel.js").read_text()
    words = js.split("const _HELD_BY_WORDS = {", 1)[1].split("};", 1)[0]
    assert "control_plane_incomplete: 'control plane, incomplete telemetry (detection only)'" in words
    assert "control_plane: 'control plane (detection only)'" in words
