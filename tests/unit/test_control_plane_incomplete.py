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
from unittest.mock import MagicMock, patch

import pytest

from glorfindel.agent import INCOMPLETE_TELEMETRY
from glorfindel.detection_rules import names_no_one
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
