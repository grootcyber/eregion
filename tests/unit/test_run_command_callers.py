"""AL3 (#867): two operations of Azure's control plane detected and escalated — Run Command on a
VM by a caller other than Glorfindel (T1651), a Bastion shareable link (T1133) — with no false
card on Glorfindel's own session drains, and never dropped for a VM outside the discovery.

Lines shaped like the ones measured on the bench on 17/11 (AzureActivity: `OperationNameValue`,
`Caller` = the object id of a service principal, its ids in `Claims`, `_ResourceId` the VM or the
Bastion; Start, then Success or Failure), every id a placeholder. The shipped queries run as
written (tests/unit/kql_subset.py), then through the real AzureActivityDetector, the real
RulePoller and the real decision; the isolation states in a throwaway HOME. No Azure, no model.
What is held:
  - the two rules are in the base, enabled, and match the measured shape; every operation is
    escalated, those that only failed too (Jonathan, 17/11 — unlike the family, AL1d), the card
    says it failed; no action, decided by the code;
  - Glorfindel's session drain is escalated by no Run Command rule — the shipped two, a client's;
    the same command outside a drain is SID1's card, once; another identity's is the external
    rule's card, whether a drain of Glorfindel's is recorded on that VM or not;
  - a row naming a VM the discovery does not know (another subscription) is a card on its
    group, unattributed, its `_ResourceId` as read — never dropped, never acted on; a VM the
    discovery knows and the rule does not watch (excluded) stays dropped.
Mutants M5501–M5519 (scripts/mutants/AL3.py).
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

import glorfindel.detection_rules as dr
from glorfindel import card_target
from glorfindel.detection_rules import RulePoller, load_config, shipped_rules_path
from glorfindel.providers.azure import activity, own_run_command as orc
from glorfindel.providers.azure.monitor import AzureMonitorDetector

from . import kql_subset

SHIPPED_PATH = shipped_rules_path()
SHIPPED = {r["name"]: r for r in yaml.safe_load(SHIPPED_PATH.read_text())["rules"]}
EXTERNAL = "run-command-by-external-caller"
SID1 = "run-command-by-glorfindel-outside-isolation"
BASTION_RULE = "bastion-shareable-link-created"
RUN_OP = "MICROSOFT.COMPUTE/VIRTUALMACHINES/RUNCOMMAND/ACTION"
BASTION_OP = "MICROSOFT.NETWORK/BASTIONHOSTS/CREATESHAREABLELINKS/ACTION"

# Placeholders, never real ids: the bench's subscription, and a dedicated one the discovery does
# not read (the targets of a public technique library live there).
SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
OTHER_SUB = "/subscriptions/11111111-1111-1111-1111-111111111111"
VM1 = f"{SUB}/resourcegroups/rg-example/providers/microsoft.compute/virtualmachines/vm1"
VM2 = f"{SUB}/resourcegroups/rg-example/providers/microsoft.compute/virtualmachines/vm2"
FAR_GROUP = f"{OTHER_SUB}/resourcegroups/rg-lab-example"
FAR_VM = f"{FAR_GROUP}/providers/microsoft.compute/virtualmachines/vm-lab"
BASTION = f"{FAR_GROUP}/providers/microsoft.network/bastionhosts/bastion-lab"
OWN_APP = "a1111111-b111-c111-d111-e11111111111"
OWN_OID = "a2222222-b222-c222-d222-e22222222222"
SP_APP = "c3333333-d333-e333-f333-a33333333333"
SP_OID = "c4444444-d444-e444-f444-a44444444444"
OID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _now_when_the_test_starts(monkeypatch):
    global NOW
    NOW = datetime.now(timezone.utc)
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)


def _line(op, rid, status, minutes_ago, corr="c-1", oid=SP_OID, app=SP_APP, bare=False):
    """One line of AzureActivity as measured on the bench: a service principal's object id as
    its Caller, its ids in Claims (`bare`: a line that names no caller)."""
    return {"Type": "AzureActivity", "TimeGenerated": NOW - timedelta(minutes=minutes_ago),
            "OperationNameValue": op, "ActivityStatusValue": status,
            "Caller": "" if bare else oid, "CallerIpAddress": "" if bare else "203.0.113.7",
            "Claims": "" if bare else json.dumps({"appid": app, OID_CLAIM: oid}),
            "_ResourceId": rid, "ResourceGroup": rid.split("/")[4].upper(), "CorrelationId": corr,
            "SubscriptionId": rid.split("/")[2]}


def _op(op, rid, outcome="Success", corr="c-1", minutes_ago=5, **kw):
    """An operation: its Start, then its outcome a minute later."""
    return [_line(op, rid, "Start", minutes_ago + 1, corr=corr, **kw),
            _line(op, rid, outcome, minutes_ago, corr=corr, **kw)]


def _own(rid=VM1, outcome="Success", corr="c-own", minutes_ago=5):
    return _op(RUN_OP, rid, outcome, corr=corr, minutes_ago=minutes_ago, oid=OWN_OID, app=OWN_APP)


def _drain_recorded(vm=VM1, minutes_ago=6.5):
    """Glorfindel's isolation of `vm`, its drain noted just before the Run Command was asked."""
    import glorfindel.actions as actions
    d = actions._ISOLATION_STATE_DIR
    d.mkdir(parents=True, exist_ok=True)
    at = (NOW - timedelta(minutes=minutes_ago)).isoformat()
    (d / f"{vm.rsplit('/', 1)[-1]}.json").write_text(
        json.dumps({"resource_id": vm, "placements": [], "drains_at": [at]}))


def _run(rule, lines):
    return kql_subset.run(SHIPPED[rule]["query"], lines, now=NOW)


class _Credential:
    def __init__(self, error=None):
        self.error = error

    def get_token(self, _scope):
        if self.error:
            raise self.error

        def b64(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        claims = {"appid": OWN_APP, "oid": OWN_OID, "idtyp": "app"}
        return SimpleNamespace(token=f"{b64({'alg': 'none'})}.{b64(claims)}.sig")


@pytest.fixture()
def workspace(monkeypatch):
    """The workspace runs the rule's query on the lines it holds; the instants as text."""
    lines: list[dict] = []

    def run_query(self, query, timespan=None):
        return [{k: (v.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(v, datetime) else v)
                 for k, v in r.items()} for r in kql_subset.run(query, lines, now=NOW)]
    monkeypatch.setattr(AzureMonitorDetector, "run_query", run_query)
    return lines


class _Registry:
    """The discovery: `vms` on the rule's backend; `known`, VMs it knows the rule does not watch."""

    def __init__(self, vms=(VM1, VM2), known=()):
        self.assets = [SimpleNamespace(name=v.rsplit("/", 1)[-1], resource_id=v) for v in vms]
        self.others = [SimpleNamespace(name=v.rsplit("/", 1)[-1], resource_id=v) for v in known]

    def for_backend(self, _name):
        return self.assets

    def all(self):
        return self.assets + self.others


def _cfg():
    return SimpleNamespace(monitoring_backends=[SimpleNamespace(
        name="law-example", type="azure_monitor", workspace_id="ws-test", endpoint="")])


def _rule(name, path=SHIPPED_PATH):
    return next(r for r in load_config(path, glorfindel_cfg=_cfg(), client_layer=False).rules if r.name == name)


def _poll(name, lines, registry=None, error=None, rule=None):
    """One poll of the rule over `lines`, through the real detector (Glorfindel's identity read
    from its token, unless `error`) and the real RulePoller."""
    rule = rule or _rule(name)
    det = activity.AzureActivityDetector("ws-test", credential=_Credential(error))
    sent: list = []
    p = RulePoller([rule], sent.append)
    p._status = {}
    p._detector = lambda _rule: det
    p._registry = registry or _Registry()
    p.poll_once(rule)
    p.stop()
    return sent


def _row(sig):
    return sig["raw_signal"]["first_result_row"]


def _decision(sig):
    from glorfindel.agent import _control_plane_decision
    from .test_own_run_command import _initial
    return _control_plane_decision(_initial(sig))


# ── the two rules, in the base, on the measured shape ──────────────────────────

def test_the_two_rules_are_in_the_base_enabled_and_bound_to_the_workspace():
    for name, ttp, op in ((EXTERNAL, "T1651", RUN_OP), (BASTION_RULE, "T1133", BASTION_OP)):
        r = _rule(name)
        assert (r.source, r.ttp, r.enabled, r.workspace_id) == ("azure_activity", ttp, True, "ws-test")
        assert r.auto_apply and r.monitoring_backend_name == "law-example"
        assert op in r.query and dr._query_lookback_s(r.query) >= activity.MIN_LOOKBACK_S
        for col in ("CallerAppId", "CallerObjectId", "CorrelationId", "Succeeded", "Callers"):
            assert col in r.query
        # Every operation, those that only failed too (AL3): no failure filter.
        assert "Failure" not in r.query and "Failed" not in r.query
    # The base, not a client's layer: in the shipped file, P1's manifest included.
    assert EXTERNAL in SHIPPED and BASTION_RULE in SHIPPED
    # The external rule reads every caller but Glorfindel; the Bastion rule, every caller.
    assert 'WatchedCaller = "others"' in SHIPPED[EXTERNAL]["query"] and "Started" in SHIPPED[EXTERNAL]["query"]
    assert "WatchedCaller" not in SHIPPED[BASTION_RULE]["query"]


@pytest.mark.parametrize("name,op,rid", [(EXTERNAL, RUN_OP, VM1), (BASTION_RULE, BASTION_OP, BASTION)])
def test_each_rule_matches_an_operation_as_measured(name, op, rid):
    rows = _run(name, _op(op, rid))
    assert len(rows) == 1
    row = rows[0]
    assert (row["OperationNameValue"], row["ActivityStatusValue"], row["Succeeded"]) == (op, "Success", 1)
    assert (row["Caller"], row["CallerAppId"], row["CallerObjectId"], row["_ResourceId"]) == (
        SP_OID, SP_APP, SP_OID, rid)
    # A refused attempt is read too, its count saying no line succeeded.
    [failed] = _run(name, _op(op, rid, "Failure", corr="c-refused"))
    assert (failed["ActivityStatusValue"], failed["Succeeded"]) == ("Failure", 0)
    # What the rule does not read stays out: another operation, a line older than its window.
    other = "MICROSOFT.COMPUTE/VIRTUALMACHINES/READ"
    assert _run(name, [*_op(other, rid, corr="c-x"), _line(op, rid, "Success", 90, corr="c-old")]) == []


@pytest.mark.parametrize("name,op,rid", [(EXTERNAL, RUN_OP, FAR_VM), (BASTION_RULE, BASTION_OP, BASTION)])
def test_an_operation_is_a_card_with_no_action_and_a_refused_one_too(workspace, name, op, rid):
    """An outsider's operation: one card, high, decided by the code, no action. A refused attempt:
    its card too, saying it failed; the success says no failure."""
    workspace += _op(op, rid) + _op(op, rid, "Failure", corr="c-refused", minutes_ago=3)
    sent = _poll(name, workspace)
    assert sorted((_row(s)["CorrelationId"], s["severity"]) for s in sent) == [("c-1", "high"), ("c-refused", "high")]
    by = {_row(s)["CorrelationId"]: _decision(s) for s in sent}
    for d in by.values():
        assert d["escalate"] is True and d["action"] == "" and d["held_by"] == "control_plane"
        assert d["llm_usage"] is None and "aucune action autonome" in d["escalation_reason"]
    assert "(Failure)" in by["c-refused"]["explanation"] and "a échoué" in by["c-refused"]["explanation"]
    assert "(Success)" in by["c-1"]["explanation"] and "échoué" not in by["c-1"]["explanation"]


def test_a_failure_is_said_only_when_the_count_is_read():
    """A client's rule that projects no `Succeeded` (or an unread one): the status it read, nothing
    more — never « failed » on a count it did not read."""
    from glorfindel.agent import _control_plane_text
    base = {"OperationNameValue": RUN_OP, "ActivityStatusValue": "Failure", "Caller": SP_OID,
            "_ResourceId": VM1, "CorrelationId": "c-1"}
    for extra in ({}, {"Succeeded": None}, {"Succeeded": "n/a"}):
        what, _ = _control_plane_text({"raw_signal": {"first_result_row": {**base, **extra}}})
        assert "(Failure)" in what and "échoué" not in what
    what, _ = _control_plane_text({"raw_signal": {"first_result_row": {**base, "Succeeded": 0}}})
    assert "a échoué" in what


def test_the_two_rules_show_in_the_status_and_are_seen_recently_matched(workspace):
    workspace += _op(BASTION_OP, BASTION) + _op(RUN_OP, VM1, corr="c-2")
    rules = [_rule(BASTION_RULE), _rule(EXTERNAL)]
    det = activity.AzureActivityDetector("ws-test", credential=_Credential())
    p = RulePoller(rules, lambda _s: None)
    p._status = {}
    p._detector = lambda _rule: det
    p._registry = _Registry()
    for r in rules:
        assert len(p.poll_once(r)) == 1
    p.stop()
    snap = {s["name"]: s for s in p.status_snapshot()}
    assert snap[BASTION_RULE]["match_count"] == 1 and snap[EXTERNAL]["match_count"] == 1
    assert dr.rulepoller_recently_matched("T1133", 60) and dr.rulepoller_recently_matched("T1651", 60)


# ── Glorfindel's drain: no Run Command rule escalates it ───────────────────────

def _client_rule(tmp_path):
    """A client's own rule on Run Command, without WatchedCaller: every caller."""
    path = tmp_path / "client.yaml"
    query = SHIPPED[EXTERNAL]["query"].replace('| extend WatchedCaller = "others"\n', "").replace(
        ", WatchedCaller", "")
    assert "WatchedCaller" not in query
    path.write_text(yaml.safe_dump({"rules": [{**SHIPPED[EXTERNAL], "name": "client-run-command", "query": query}]}))
    return _rule("client-run-command", path)


def test_a_drain_of_glorfindel_is_escalated_by_no_run_command_rule(workspace, tmp_path):
    """Its identity, a Run Command on a VM under an isolation it recorded, within its drain: the
    external rule, SID1 and a client's rule all say nothing — refused or not."""
    _drain_recorded()
    for outcome in ("Success", "Failure"):
        workspace[:] = _own(outcome=outcome, corr=f"c-drain-{outcome}")
        assert _poll(EXTERNAL, workspace) == []
        assert _poll(SID1, workspace) == []
        assert _poll("", workspace, rule=_client_rule(tmp_path)) == []


def test_the_same_command_outside_a_drain_is_sid1_s_card_once(workspace, tmp_path):
    """Its identity, outside any drain (no isolation of vm2; vm1's drain far earlier): SID1's
    critical card, the reason said; the external rule says nothing (one card, never two). A
    client's rule, which reads every caller, marks it the same way."""
    _drain_recorded(minutes_ago=50)
    workspace += _own(VM2, corr="c-vm2") + _own(VM1, corr="c-late")
    assert _poll(EXTERNAL, workspace) == []
    sent = _poll(SID1, workspace)
    assert sorted((_row(s)["CorrelationId"], _row(s)[orc.MARK], s["severity"]) for s in sent) == [
        ("c-late", "outside_drain", "critical"), ("c-vm2", "no_isolation", "critical")]
    client = _poll("", workspace, rule=_client_rule(tmp_path))
    assert sorted(_row(s)[orc.MARK] for s in client) == ["no_isolation", "outside_drain"]


def test_another_identity_is_the_external_rule_s_card_drain_or_not(workspace):
    """Another identity's Run Command on vm1 inside the window of Glorfindel's drain is not
    taken for it: the external rule's card, high, never marked Glorfindel's; SID1 says nothing."""
    _drain_recorded()
    workspace += _op(RUN_OP, VM1, corr="c-intruder")
    [sig] = _poll(EXTERNAL, workspace)
    row = _row(sig)
    assert sig["severity"] == "high" and row["GlorfindelIdentity"] is False and orc.MARK not in row
    assert sig["resource_id"] == VM1 and sig["context"]["attribution"] == "asset"
    assert _poll(SID1, workspace) == []
    # Glorfindel's own drain beside it, under its own id: still nothing for it.
    workspace += _own(corr="c-drain")
    assert [_row(s)["CorrelationId"] for s in _poll(EXTERNAL, workspace)] == ["c-intruder"]


def test_under_the_external_rule_a_row_that_cannot_be_told_glorfindel_s_stays(workspace):
    """A0: a row that names no caller, or every row while Glorfindel's identity is unknown, may be
    another's — the external rule keeps it."""
    _drain_recorded()
    workspace += [_line(RUN_OP, VM1, "Start", 6, corr="c-bare", bare=True),
                  _line(RUN_OP, VM1, "Success", 5, corr="c-bare", bare=True)]
    assert [_row(s)["CorrelationId"] for s in _poll(EXTERNAL, workspace)] == ["c-bare"]
    workspace[:] = _own(corr="c-own") + _op(RUN_OP, VM2, corr="c-out")
    sent = _poll(EXTERNAL, workspace, error=RuntimeError("no token"))
    assert sorted(_row(s)["CorrelationId"] for s in sent) == ["c-out", "c-own"]


def test_the_adapter_reads_the_scope_of_the_rule():
    """`mark`, row by row: under the rule that reads the others, Glorfindel's identity is the
    sister rule's — dropped, drain or not; another caller is kept, unmarked."""
    book = orc.DrainBook(isolated=frozenset())
    row = {"WatchedCaller": "others", "Started": NOW.isoformat()}
    assert orc.mark(row, orc.RUN_COMMAND, VM1, True, True, book) is None
    assert orc.mark(row, orc.RUN_COMMAND, VM1, True, False, book) == ""
    assert orc.mark(row, orc.RUN_COMMAND, VM1, False, False, book, has_caller=False) == ""
    # A client's rule: Glorfindel outside any drain, marked; inside, dropped.
    assert orc.mark({"Started": NOW.isoformat()}, orc.RUN_COMMAND, VM1, True, True, book) == "no_isolation"
    at = NOW.timestamp()
    drained = orc.DrainBook(times={VM1: [at]}, isolated=frozenset({VM1}))
    assert orc.mark({"Started": NOW.isoformat()}, orc.RUN_COMMAND, VM1, True, True, drained) is None


# ── a VM outside the discovery: said, never dropped, never acted on ────────────

def test_a_run_command_on_a_vm_outside_the_discovery_is_a_card_on_its_group(workspace):
    """A VM of another subscription (a dedicated one): its row was dropped unsaid. Now a card,
    filed on its group, unattributed, its `_ResourceId` kept as read, the limit said."""
    workspace += _op(RUN_OP, FAR_VM)
    [sig] = _poll(EXTERNAL, workspace)
    t = sig["context"]["target"]
    assert sig["resource_id"] == FAR_GROUP and sig["resource_type"] == "resource_group"
    assert sig["context"]["attribution"] == "unattributed" and t["kind"] == "resource_group"
    assert t["via"] == "vm-lab" and card_target._UNDISCOVERED in t["limit"]
    assert _row(sig)["_ResourceId"] == FAR_VM
    d = _decision(sig)
    assert d["action"] == "" and d["escalate"] is True and FAR_VM in d["explanation"]


def test_a_bastion_link_is_a_card_on_the_bastion_s_group(workspace):
    workspace += _op(BASTION_OP, BASTION)
    [sig] = _poll(BASTION_RULE, workspace)
    assert sig["resource_id"] == FAR_GROUP and sig["context"]["attribution"] == "unattributed"
    assert sig["context"]["target"]["via"] == "bastion-lab"
    assert _row(sig)["GlorfindelIdentity"] is False and sig["severity"] == "high"
    # Under Glorfindel's identity: kept, critical — a Bastion link is never its own.
    workspace[:] = _op(BASTION_OP, BASTION, corr="c-own", oid=OWN_OID, app=OWN_APP)
    [own] = _poll(BASTION_RULE, workspace)
    assert own["severity"] == "critical" and _row(own)["GlorfindelIdentity"] is True


def test_a_vm_the_discovery_knows_and_the_rule_does_not_watch_stays_dropped(workspace):
    """Excluded from the rule, or another backend's: the client's choice, as before (AL1)."""
    workspace += _op(RUN_OP, FAR_VM)
    assert _poll(EXTERNAL, workspace, registry=_Registry(known=(FAR_VM,))) == []
    # The discovery unreadable: never dropped on an unknown.

    class _Broken(_Registry):
        def all(self):
            raise OSError("registry")
    assert len(_poll(EXTERNAL, workspace, registry=_Broken())) == 1


def test_a_rule_bound_to_one_asset_keeps_dropping_another_vm(workspace, tmp_path):
    path = tmp_path / "bound.yaml"
    path.write_text(yaml.safe_dump({"assets": [{"name": "vm1", "resource_id": VM1}],
                                    "rules": [{**SHIPPED[EXTERNAL], "name": "bound", "assets": ["vm1"]}]}))
    rule = _rule("bound", path)
    assert not rule.auto_apply
    workspace += _op(RUN_OP, FAR_VM)
    assert _poll("", workspace, rule=rule) == []


def test_the_card_on_a_vm_outside_the_discovery_acts_on_nothing(tmp_path, monkeypatch, workspace):
    """Through the real graph, in non_disruptive, a model that would isolate at 99 % never asked:
    nothing runs against any VM, the card is `control_plane_change`, never approvable in one click."""
    from glorfindel import escalations
    from glorfindel.agent import _build_graph
    from glorfindel.config import AutonomyConfig
    from glorfindel.memory import CycleMemory
    from .test_own_run_command import _initial, _llm
    workspace += _op(RUN_OP, FAR_VM)
    [sig] = _poll(EXTERNAL, workspace)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir(exist_ok=True)
    queries: list = []
    monkeypatch.setattr("glorfindel.enquiry.fixed.run_query", lambda ws, q: queries.append(q) or [])
    connector = MagicMock()
    connector.dry_run = False
    graph = _build_graph(CycleMemory(path=tmp_path / "cycles"), connector, "claude-test",
                         autonomy=AutonomyConfig(default="non_disruptive"))
    with patch("litellm.completion", return_value=_llm("isolate_vm")) as llm:
        final = graph.invoke(_initial(sig))
    llm.assert_not_called()
    assert queries == []
    for name in ("isolate_vm", "block_suspicious_ip", "snapshot", "release_isolation", "drain_connections"):
        getattr(connector, name).assert_not_called()
    assert final["outcome"]["escalation_type"] == "control_plane_change" and final["action"] == ""
    [card] = escalations.pending()
    assert card["action"] == ""
    from eregion_console.api import _approval_refusal
    assert _approval_refusal(card, "vm-lab")
