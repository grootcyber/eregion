"""CPT1c (#940): a reply of the journal out of the rule's schema is a card « réponse du journal
illisible » — of a lower severity than high, never approvable, never dropped, one per rule and poll
with the number of its rows, said in the rule's status — never a high card that names no one.

Seen on Imladris (16/11, 12:57:02Z, one poll): `nsg-change-outside-glorfindel` and
`role-assignment-write` each made a high card « ? par appelant inconnu sur ? ». Their row held
`TimeGenerated` alone, the text « Exceptions », and Glorfindel's two marks (`prepare_rows`): none of
the 12 columns the rules project. `names_no_one` (CPT1) did not lower it: it wants an operation.

The reading side (`AzureMonitorDetector.run_query`) is not changed here: the SDK (azure-monitor-query
2.0.0) keeps every table of the reply and a row shorter than its columns, and `zip` cuts — the row of
the 16/11 comes out of either, read here on the SDK's own objects; what Azure sent is not established
(docs/azure.md, « Journal d'activité »). The guard is on the card.

Every identifier is made up (repository public). No Azure, no model.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from glorfindel.agent import INCOMPLETE_TELEMETRY, UNREADABLE_REPLY, _control_plane_text
from glorfindel.detection_rules import (
    UNREADABLE_EXPECTED, names_no_one, unreadable_card, unreadable_counts, unreadable_reply,
)
from glorfindel.providers.azure.monitor import AzureMonitorDetector

from . import kql_subset
from . import test_activity_operation_read as op_read
from .test_activity_logs import _graph, _initial, _llm
from .test_activity_operation_read import (  # noqa: F401 — its clock, set when each test starts
    COLUMNS, OUTSIDER, RULES, _line, _now_when_the_test_starts, _poller,
)

TWO = ("role-assignment-write", "nsg-change-outside-glorfindel")
# The row of the 16/11, as the card read it (`first_result_row`).
ROW_1611 = {"TimeGenerated": "Exceptions", "GlorfindelManaged": False, "GlorfindelIdentity": False}
_TYPES = {"TimeGenerated": "datetime", "Succeeded": "long", "Callers": "long"}


@pytest.fixture(autouse=True)
def _no_ambient_identity(monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)


def _table(name, columns, rows):
    return {"name": name, "columns": [{"name": c, "type": _TYPES.get(c, "string")} for c in columns],
            "rows": rows}


@pytest.fixture()
def reply(monkeypatch):
    """The workspace answers with the SDK's own objects (`LogsQueryResult._from_generated`, the
    parse of a reply's body): the tables set here, as Azure's body would carry them."""
    from azure.monitor.query._models import LogsQueryResult
    body: dict = {"tables": []}

    class _Client:
        def query_workspace(self, workspace_id, query, timespan=None):
            return LogsQueryResult._from_generated(json.loads(json.dumps(body)))
    monkeypatch.setattr(AzureMonitorDetector, "_logs_client", lambda self: _Client())
    return body


@pytest.fixture()
def workspace(monkeypatch):
    """The shipped query on the lines it holds (as test_activity_operation_read's), then the rows of
    `extra` as the reply carried them besides — through the real AzureActivityDetector (its marks)."""
    lines: list[dict] = []
    extra: list[dict] = []

    def run_query(self, query, timespan=None):
        rows = [{k: (v.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(v, datetime) else v)
                 for k, v in r.items()} for r in kql_subset.run(query, lines, now=op_read.NOW)]
        return rows + [dict(r) for r in extra]
    monkeypatch.setattr(AzureMonitorDetector, "run_query", run_query)
    return SimpleNamespace(lines=lines, extra=extra)


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


def _unreadable_signal(sent):
    found = [s for s in sent if "UnreadableCount" in s["raw_signal"]["first_result_row"]]
    assert len(found) == 1, sent
    return found[0]


# ── the reading: the row of the 16/11 out of the SDK's objects ────────────────────────

@pytest.mark.parametrize("shape", ["a short row", "a table more"])
def test_the_row_of_the_16_11_comes_out_of_an_sdk_reply_of_either_shape(reply, shape):
    """The hypothesis, read in the SDK's code, not proven of Azure: a row of one value in the main
    table (`zip` cuts it to its first column), or a table more whose column is TimeGenerated, both
    give the row the card read on Imladris — the reading takes every table and never counts values."""
    if shape == "a short row":
        reply["tables"] = [_table("PrimaryResult", COLUMNS, [["Exceptions"]])]
    else:
        reply["tables"] = [_table("PrimaryResult", COLUMNS, []),
                           _table("Table_1", ["TimeGenerated"], [["Exceptions"]])]
    p, rule, sent = _poller("role-assignment-write")
    assert p._detector(rule).run_query(rule.query) == [ROW_1611]


# ── the card ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rule_name", TWO)
def test_the_row_of_the_16_11_is_one_card_of_an_unreadable_reply(tmp_path, monkeypatch, reply, rule_name):
    """Fini quand: a card « réponse illisible », `medium`, never a high card that names no one; it
    names what is missing and what the row carried; the rule's status says it."""
    from glorfindel import escalations
    from glorfindel.detection_rules import _load_status
    reply["tables"] = [_table("PrimaryResult", COLUMNS, [["Exceptions"]])]
    p, rule, sent = _poller(rule_name)
    p.poll_once(rule)
    assert len(sent) == 1, sent
    sig = sent[0]
    assert sig["severity"] == "medium"
    row = sig["raw_signal"]["first_result_row"]
    assert row["UnreadableCount"] == 1 and row["UnreadableRows"] == [{"TimeGenerated": "Exceptions"}]
    final, card = _card(tmp_path, monkeypatch, sig)
    assert final["held_by"] == "control_plane_unreadable" and final["action"] == ""
    assert card["escalation_type"] == "control_plane_change" and card["severity"] == "medium"
    assert card["reason"].startswith(f"{UNREADABLE_REPLY} : colonnes attendues absentes.")
    assert "Sévérité : moyenne" in card["reason"]
    text = card["explanation"]
    assert "appelant inconnu" not in text and " sur ?" not in text and INCOMPLETE_TELEMETRY not in text
    assert "1 ligne(s) de cette règle" in text
    assert "Absentes : " + ", ".join(UNREADABLE_EXPECTED) + "." in text
    assert "TimeGenerated = « Exceptions »" in text and "TimeGenerated est un texte, pas une date" in text
    assert "Glorfindel" not in text.split("Ce que portaient les lignes", 1)[1]
    assert card["suggested_steps"][0].startswith("Rejouer la requête de la règle")
    # Visible where the operator judges; the rule's status says it.
    assert [c["id"] for c in escalations.to_judge()] == [card["id"]]
    counts = unreadable_counts(_load_status()[rule_name])
    assert (counts["unreadable_rows"], counts["unreadable_cards"]) == (1, 1) and counts["unreadable_last"]
    snap = next(s for s in p.status_snapshot() if s["name"] == rule_name)
    assert (snap["unreadable_rows"], snap["unreadable_cards"]) == (1, 1)
    assert not snap["last_error"]        # a reply out of schema is no unreachable workspace


@pytest.mark.parametrize("rule_name", TWO)
def test_the_card_of_an_unreadable_reply_is_never_approvable(tmp_path, monkeypatch, reply, rule_name):
    """No action to run, no verb signed, refused by the console and the bot's approval alike — even
    with an action written on it."""
    from eregion_core import action_queue
    from eregion_console.api import _approval_refusal
    from glorfindel.approval import approval_refusal
    reply["tables"] = [_table("PrimaryResult", COLUMNS, [["Exceptions"]])]
    p, rule, sent = _poller(rule_name)
    p.poll_once(rule)
    _final, card = _card(tmp_path, monkeypatch, sent[0])
    assert card["escalation_type"] not in action_queue.APPROVABLE_TYPES
    assert action_queue.proposed_verbs(card) == frozenset()
    for esc in (card, {**card, "action": "isolate_vm"}, {**card, "action": "block_suspicious_ip"}):
        assert approval_refusal(esc, "vm1") and _approval_refusal(esc, "vm1")
        assert action_queue.proposed_verbs(esc) == frozenset()


def test_many_unreadable_rows_in_one_poll_are_one_card_with_their_number(tmp_path, monkeypatch, reply):
    """A whole reply malformed never floods the queue: one card, its rows counted, the first shown;
    the same rows at the next poll make no card more, and are never lost (marked sent with it)."""
    from glorfindel.detection_rules import _load_status
    rule_name = "nsg-change-outside-glorfindel"
    rows = [["Exceptions"], ["Exceptions"]] + [[f"Exceptions {i}"] for i in range(38)]
    reply["tables"] = [_table("PrimaryResult", COLUMNS, rows)]
    p, rule, sent = _poller(rule_name)
    p.poll_once(rule)
    assert len(sent) == 1
    row = sent[0]["raw_signal"]["first_result_row"]
    assert row["UnreadableCount"] == 40 and len(row["UnreadableRows"]) == 5
    _final, card = _card(tmp_path, monkeypatch, sent[0])
    assert "40 ligne(s) de cette règle" in card["explanation"]
    assert "(35 ligne(s) de plus, non montrées.)" in card["explanation"]
    p.poll_once(rule)
    assert len(sent) == 1
    counts = unreadable_counts(_load_status()[rule_name])
    assert (counts["unreadable_rows"], counts["unreadable_cards"]) == (40, 1)
    # A row new at the next poll: one card more, counted.
    reply["tables"] = [_table("PrimaryResult", COLUMNS, rows + [["Exceptions again"]])]
    p.poll_once(rule)
    assert len(sent) == 2 and sent[1]["raw_signal"]["first_result_row"]["UnreadableCount"] == 1
    counts = unreadable_counts(_load_status()[rule_name])
    assert (counts["unreadable_rows"], counts["unreadable_cards"]) == (41, 2)


# ── what does not change ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rule_name", TWO)
def test_a_complete_line_beside_an_unreadable_row_keeps_its_card(tmp_path, monkeypatch, workspace, rule_name):
    """The witness: its caller, its resource, `high`, the card of AL1 — as without the row out of
    schema, which makes its own card beside."""
    workspace.lines += [_line(rule_name, "Start", 6), _line(rule_name, "Success", 5)]
    p, rule, alone = _poller(rule_name)
    p.poll_once(rule)
    assert len(alone) == 1
    workspace.extra.append({"TimeGenerated": "Exceptions"})
    p, rule, sent = _poller(rule_name)
    p._status = {}                       # the same operation, read afresh
    p.poll_once(rule)
    assert len(sent) == 2
    complete = next(s for s in sent if "UnreadableCount" not in s["raw_signal"]["first_result_row"])
    assert complete["raw_signal"]["first_result_row"] == alone[0]["raw_signal"]["first_result_row"]
    assert complete["severity"] == "high" == alone[0]["severity"]
    what, _steps = _control_plane_text(complete)
    assert what.startswith("Plan de contrôle : ") and f"par {OUTSIDER}" in what
    assert _unreadable_signal(sent)["severity"] == "medium"


@pytest.mark.parametrize("rule_name", TWO)
def test_a_line_of_cpt1_stays_incomplete_telemetry(tmp_path, monkeypatch, workspace, rule_name):
    """Its operation, neither caller nor resource: « Télémétrie incomplète », as before — never
    folded into the card of the reply out of schema."""
    bare = _line(rule_name, "Success", 5, bare=True)
    bare["_ResourceId"] = ""
    workspace.lines.append(bare)
    workspace.extra.append({"TimeGenerated": "Exceptions"})
    p, rule, sent = _poller(rule_name)
    p.poll_once(rule)
    assert len(sent) == 2
    cpt1 = next(s for s in sent if "UnreadableCount" not in s["raw_signal"]["first_result_row"])
    assert cpt1["raw_signal"]["first_result_row"]["OperationNameValue"] == RULES[rule_name][0]
    assert cpt1["severity"] == "medium"
    final, card = _card(tmp_path, monkeypatch, cpt1)
    assert final["held_by"] == "control_plane_incomplete"
    assert card["reason"].startswith(INCOMPLETE_TELEMETRY) and UNREADABLE_REPLY not in card["reason"]


def test_a_row_of_cpt1_is_never_an_unreadable_reply():
    """The operation alone (no CorrelationId, no column of the caller or the resource) is CPT1's."""
    row = {"OperationNameValue": RULES["role-assignment-write"][0], "GlorfindelManaged": False,
           "GlorfindelIdentity": False}
    assert names_no_one(row) and not unreadable_reply(row)


@pytest.mark.parametrize("mark", [{"GlorfindelManaged": True}, {"GlorfindelIdentity": True},
                                  {"GlorfindelRunCommand": "caller_unreadable"}])
def test_a_grave_row_out_of_schema_stays_critical(tmp_path, monkeypatch, mark):
    """A row that names a write on Glorfindel's rules, its identity or its Run Command is never
    lowered, however incomplete: its own card, critical — never folded into the medium one."""
    assert not unreadable_reply({**ROW_1611, **mark})
    p, rule, sent = _poller("nsg-change-outside-glorfindel")
    rows = [{**ROW_1611, **mark}, dict(ROW_1611)]
    p._detector = lambda _rule: SimpleNamespace(run_query=lambda q, timespan=None: [dict(r) for r in rows])
    p.poll_once(rule)
    assert len(sent) == 2
    grave = next(s for s in sent if "UnreadableCount" not in s["raw_signal"]["first_result_row"])
    assert grave["severity"] == "critical"
    assert _unreadable_signal(sent)["raw_signal"]["first_result_row"]["UnreadableCount"] == 1
    final, card = _card(tmp_path, monkeypatch, grave)
    assert card["severity"] == "critical" and "Sévérité : critique" in card["reason"]
    assert final["held_by"] == "control_plane" and UNREADABLE_REPLY not in card["reason"]


def test_a_critical_signal_on_an_unreadable_row_stays_critical(tmp_path, monkeypatch):
    sig = {"signal_id": "rule-x", "event": "detection", "ttp": "T1562.007", "severity": "critical",
           "resource_id": "control-plane", "resource_type": "control_plane", "provider": "azure",
           "timestamp": "2026-11-16T12:57:02+00:00",
           "context": {"rule_name": "nsg-change-outside-glorfindel", "asset_name": "control-plane",
                       "run_id": "watch-x", "attribution": "unattributed", "plane": "control"},
           "raw_signal": {"detection_source": "azure_activity", "first_result_row": dict(ROW_1611)}}
    final, card = _card(tmp_path, monkeypatch, sig)
    assert card["severity"] == "critical" and final["held_by"] == "control_plane"


def test_a_high_signal_of_the_16_11_replayed_is_a_medium_card(tmp_path, monkeypatch):
    """A signal written before CPT1c (high, the raw row): `decide` lowers it and says it."""
    sig = {"signal_id": "rule-y", "event": "detection", "ttp": "T1098", "severity": "high",
           "resource_id": "control-plane", "resource_type": "control_plane", "provider": "azure",
           "timestamp": "2026-11-16T12:57:02+00:00",
           "context": {"rule_name": "role-assignment-write", "asset_name": "control-plane",
                       "run_id": "watch-y", "attribution": "unattributed", "plane": "control"},
           "raw_signal": {"detection_source": "azure_activity", "first_result_row": dict(ROW_1611)}}
    final, card = _card(tmp_path, monkeypatch, sig)
    assert card["severity"] == "medium" and final["held_by"] == "control_plane_unreadable"
    assert card["reason"].startswith(UNREADABLE_REPLY) and "TimeGenerated = « Exceptions »" in card["explanation"]


# ── the reading of a row ──────────────────────────────────────────────────────────────

def test_unreadable_reply_reads_every_column_that_says_what_a_row_is():
    assert unreadable_reply(dict(ROW_1611)) and unreadable_reply({})
    for col in UNREADABLE_EXPECTED + ("ResourceId", "CallerName"):
        assert not unreadable_reply({**ROW_1611, col: "x"}), col
    assert unreadable_reply({**ROW_1611, "Caller": "  ", "_ResourceId": ""})     # blank is nothing
    assert not unreadable_reply({**ROW_1611, "Claims": json.dumps({"appid": "c4444444"})})
    assert not unreadable_reply({**ROW_1611, "Callers": 2})
    assert not unreadable_reply({**ROW_1611, "Callers": "two"})
    assert not unreadable_reply({**ROW_1611, "OmittedOperations": [dict(ROW_1611)]})
    assert not unreadable_reply("nope")
    # The card itself reads as one (a replay of it says the same).
    assert unreadable_reply(unreadable_card([dict(ROW_1611)]))


def test_the_card_keeps_what_the_rows_carried_cut_never_whole():
    rows = [{"TimeGenerated": "x" * 500, "Other": {"nested": 1}, "N": 3, "GlorfindelIdentity": False}] * 7
    card = unreadable_card(rows)
    assert card["UnreadableCount"] == 7 and len(card["UnreadableRows"]) == 5
    assert card["UnreadableRows"][0] == {"TimeGenerated": "x" * 80, "Other": "<dict>", "N": 3}
    assert card["GlorfindelManaged"] is False and card["GlorfindelIdentity"] is False


def test_unreadable_counts_read_a_status_as_it_is():
    assert unreadable_counts({}) == {"unreadable_rows": 0, "unreadable_cards": 0, "unreadable_last": ""}
    assert unreadable_counts({"unreadable": {"rows": -1, "cards": "2"}})["unreadable_rows"] == 0
    assert unreadable_counts({"unreadable": {"rows": 3, "cards": 1, "last": "t"}}) == {
        "unreadable_rows": 3, "unreadable_cards": 1, "unreadable_last": "t"}


# ── the data plane: as before (not this lot's) ───────────────────────────────────────

def test_a_rule_of_the_data_plane_is_not_read_by_the_guard(monkeypatch):
    """Point 3 of the lot, said in its report: a data rule that read the same row would send it as
    the newest event of its pass (`high`, unattributed, to the model) — unchanged here."""
    from glorfindel.detection_rules import DetectionRule
    rule = DetectionRule(name="data-rule", ttp="T1486", source="azure_monitor", workspace_id="ws-test",
                         query="Perf | where TimeGenerated > ago(10m)", resource_id="", interval_s=60,
                         auto_apply=True)
    p, _r, sent = _poller("nsg-change-outside-glorfindel")
    p._rules = [rule]
    p._detector = lambda _rule: SimpleNamespace(run_query=lambda q, timespan=None: [{"TimeGenerated": "Exceptions"}])
    p.poll_once(rule)
    assert len(sent) == 1 and "UnreadableCount" not in sent[0]["raw_signal"]["first_result_row"]
    assert sent[0]["severity"] == "high"


def test_the_console_feed_names_a_card_of_an_unreadable_reply():
    js = (Path(__file__).resolve().parents[2] / "eregion_console/static/glorfindel.js").read_text()
    words = js.split("const _HELD_BY_WORDS = {", 1)[1].split("};", 1)[0]
    assert "control_plane_unreadable: 'control plane, unreadable reply (detection only)'" in words


def test_the_console_reads_the_counts_of_each_rule():
    """`/api/state` gives each rule its counts (eregion_console/api.py, beside SLF1's)."""
    src = (Path(__file__).resolve().parents[2] / "eregion_console/api.py").read_text()
    assert "**unreadable_counts(s)," in src
