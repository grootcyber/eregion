"""SEC-A4 (#633; audit of 06/11, V-04 and V-05) — what a detection row is attributed by.

1. V-04: never by the host name. A row is routed by the resource it names (`_ResourceId`) or the
   private address that made a call (`CallerIpAddress`); a row named only by its `Computer` —
   which root on the VM chooses — names no VM. A rule of the data plane whose query keeps
   neither key is refused at load, in any layer, and its approval is refused with a clear
   message (`eregion_core/rule_routing.py`). The control plane and identities are filed on what
   their rows name (AL1c): not concerned.
2. V-05: never by an appliance's address. A VM one of whose NICs forwards packets (a firewall, a
   hub's appliance that SNATs toward a private endpoint) is marked in the private IP map: a
   storage call made from its address names no VM, every action is held — on the appliance
   (which would cut a hub) and on any other —, and the card says the source is behind it.

No Azure call (the connector reads the in-memory Azure of tests/unit/fake_azure.py), no model
call (patched). Mutants M4540–M4544 (scripts/mutants/SEC-A4.py) are measured here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eregion_core import rule_routing
from glorfindel import agent
from glorfindel.detection_rules import (
    DetectionRule,
    RulePoller,
    appliance_owner,
    load_config,
    routing_refusal,
)
from tests.unit.fake_azure import FakeAzure, subnet_id, vm_id
from tests.unit.test_unexpected_decision import (  # noqa: F401  (hermetic: the module's autouse)
    RID,
    _decide,
    _decision,
    _resolve,
    _started,
    hermetic,
)

ROOT = Path(__file__).resolve().parents[2]
SHIPPED_BASE = ROOT / "glorfindel" / "rules" / "azure" / "detection_rules.yaml"
BY_HOST = "Syslog | where SyslogMessage has \"x\" | summarize count() by Computer"


# ── 1. V-04: the routing keys a query keeps ─────────────────────────────────────────────

# Refused: rows that name no VM, or a key that no longer holds what Azure wrote (B1, B2, C1 of
# the review: each a way the first reader let V-04 back in, two stages at a time).
REFUSED = [
    "Syslog | summarize count() by Computer",
    "Syslog | project Computer, SyslogMessage",
    "Syslog | extend _ResourceId = Computer",                # the host name, under the key's name
    "Syslog | extend _ResourceId = strcat(_ResourceId, Computer)",
    "Syslog | project _ResourceId = tolower(_ResourceId), Computer",   # any write, whatever from
    "Syslog | summarize _ResourceId = take_any(_ResourceId) by Computer",
    "Syslog | extend _ResourceId = Computer | project _ResourceId",
    "Syslog | extend _ResourceId = Computer | summarize count() by _ResourceId",
    "Syslog | extend _ResourceId = Computer | distinct _ResourceId",
    "Syslog | extend _ResourceId = Computer | summarize arg_max(TimeGenerated, _ResourceId) by Computer",
    "Syslog | summarize arg_max(TimeGenerated, _ResourceId = Computer) by Computer",
    "Syslog | project-rename _ResourceId = Computer | project _ResourceId",
    "Syslog | project-rename X = _ResourceId | project _ResourceId",
    "Syslog | extend ResourceId = Computer | project ResourceId",
    "Syslog | extend _resourceid = Computer | project _ResourceId",     # whatever the case
    "Syslog | extend CallerIpAddress = extract('(.*)', 1, SyslogMessage) | project CallerIpAddress",
    "print _ResourceId = 1 | project _ResourceId",
    "let _ResourceId = 1; Syslog | project _ResourceId",
    "datatable(_ResourceId:string)['x']",
    "datatable(x:string)['a'] | extend y = 1",
    "union withsource=_ResourceId Syslog, Perf | project _ResourceId",
    "union withsource=['_ResourceId'] Syslog | project _ResourceId",
    "Syslog | extend ['_ResourceId'] = Computer",               # B2: a form it does not read
    "Syslog | extend (_ResourceId, B) = (Computer, 1)",
    "Syslog | summarize hint.strategy = shuffle count() by _ResourceId",
    "Syslog | parse SyslogMessage with * 'x' _ResourceId:string",
    "Syslog | parse SyslogMessage with * 'x' _ResourceId ' '",
    "Syslog | parse SyslogMessage with * 'x' ['_ResourceId']:string",
    "MyTable_CL | project CallerIpAddress",                    # C1: a custom table, root's word
    "Syslog | extend CallerIpAddress = tostring(split(CallerIpAddress, ':')[0]) | project CallerIpAddress",
    'StorageBlobLogs | extend CallerIpAddress = tostring(split(CallerIpAddress, "5")[0]) | project CallerIpAddress',
    "union StorageBlobLogs, Syslog | project CallerIpAddress",
    "Syslog | project-away _ResourceId",
    "Syslog | project-away _*",
    "Syslog | summarize take_any(_ResourceId) by Computer",   # named any__ResourceId
    "Syslog | distinct Computer",
    "Syslog | join kind=rightanti (Heartbeat | project Computer) on Computer",
    "Syslog | join kind=RightSemi (Heartbeat) on Computer",
    "Syslog | count",
    "Syslog | evaluate bag_unpack(x)",
    "let t = Syslog | project Computer; t | where 1 == 1",
    "StorageBlobLogs | project CallerIpAddress = SourceIP",
]
ACCEPTED = [
    "Syslog | where x",                                        # a table: its _ResourceId
    "Syslog | where _ResourceId == 'x' | project _ResourceId",  # read, never written
    "Syslog | summarize count() by Computer, _ResourceId",
    "Syslog | summarize by Computer, _ResourceId",
    "Syslog | project _ResourceId, Computer",
    "Syslog | project-keep _Res*",
    "Syslog | summarize arg_max(TimeGenerated, *) by Computer",
    "Syslog | summarize arg_max(TimeGenerated, _ResourceId) by Computer",
    "Syslog | distinct Computer, _ResourceId",
    "Syslog | extend Vm = iff(isnotempty(_ResourceId), tolower(_ResourceId), Computer) | project _ResourceId",
    "let t = Syslog | project Computer, _ResourceId; t",
    "union Syslog, Perf | where 1 == 1",
    "union kind=outer Syslog, Perf | project _ResourceId",
    'Syslog | where SyslogMessage has "| project Computer"',  # a string is no stage
    "Syslog // | project Computer\n| where 1 == 1",            # nor a comment
    "StorageBlobLogs | project CallerIpAddress, AccountName",
    "union StorageBlobLogs, StorageFileLogs | project CallerIpAddress",
    # The one rewrite read as none: the port off the storage caller's address (data-exfiltration-blob).
    'StorageBlobLogs | extend CallerIpAddress = tostring(split(CallerIpAddress, ":")[0]) '
    "| summarize n = count() by CallerIpAddress, AccountName",
]


@pytest.mark.parametrize("query, routed", [(q, False) for q in REFUSED] + [(q, True) for q in ACCEPTED])
def test_the_reader_keeps_the_keys_every_row_carries(query, routed):
    assert bool(rule_routing.routing_columns(query)) is routed
    assert (rule_routing.refusal(query) == "") is routed


def test_a_query_that_cannot_be_read_is_refused_never_assumed():
    why = rule_routing.refusal('Syslog | where x == "not closed')
    assert why.startswith("requête illisible")


def test_the_refusal_says_what_the_query_does():
    assert "écrit la clé de routage `_ResourceId`" in rule_routing.refusal(
        "Syslog | extend _ResourceId = Computer | project _ResourceId")
    assert "forme illisible" in rule_routing.refusal("Syslog | extend ['_ResourceId'] = Computer")
    assert "Computer" in rule_routing.refusal("MyTable_CL | project CallerIpAddress")


def test_every_shipped_rule_loads_and_its_rows_name_their_vm():
    """The shipped base is conformant (V-04 — « les règles livrées sont conformes »): every rule
    loads; each of the data plane keeps `_ResourceId`, but data-exfiltration-blob, routed by the
    address that made the storage call. None is changed by SEC-A4."""
    import yaml
    shipped = yaml.safe_load(SHIPPED_BASE.read_text())["rules"]
    cfg = load_config(SHIPPED_BASE, client_layer=False)
    assert {r.name for r in cfg.rules} == {r["name"] for r in shipped if r.get("enabled", True)}
    assert not [n for n in cfg.notes if "refusée" in n], cfg.notes
    keys = {r["name"]: rule_routing.routing_columns(r["query"]) for r in shipped
            if rule_routing.data_plane(r.get("source", "azure_monitor"), r["query"])}
    assert keys.pop("data-exfiltration-blob") == {"CallerIpAddress"}
    assert keys and all("_ResourceId" in k for k in keys.values()), keys


def _base(tmp_path, *rules) -> Path:
    path = tmp_path / "base.yaml"
    path.write_text(json.dumps({"rules": [dict(r) for r in rules]}))     # JSON is YAML
    return path


def test_a_rule_routed_by_its_host_name_is_refused_at_load(tmp_path):
    """V-04: its rows fell back on `Computer` — root on a VM made the watch isolate another."""
    base = _base(tmp_path, {"name": "by-host", "ttp": "T1486", "assets": ["auto"], "query": BY_HOST},
                 {"name": "by-rid", "ttp": "T1486", "assets": ["auto"],
                  "query": BY_HOST + ", _ResourceId"})
    cfg = load_config(base, client_layer=False)
    assert [r.name for r in cfg.rules] == ["by-rid"]
    (note,) = [n for n in cfg.notes if "by-host" in n]
    assert "refusée" in note and "_ResourceId" in note and "Computer" in note


def test_a_client_replacement_routed_by_its_host_name_keeps_the_base_rule(tmp_path):
    base = _base(tmp_path, {"name": "ssh", "ttp": "T1110.001", "assets": ["auto"],
                            "query": BY_HOST + ", _ResourceId"})
    client = tmp_path / "client_rules.yaml"
    client.write_text(json.dumps({"rules": [{"name": "ssh", "ttp": "T1110.001", "query": BY_HOST},
                                            {"name": "new", "ttp": "T1078", "query": BY_HOST}]}))
    cfg = load_config(base, client_layer=client)
    assert [(r.name, r.layer) for r in cfg.rules] == [("ssh", "base")]
    assert len([n for n in cfg.notes if "couche du client" in n and "Computer" in n]) == 2


def test_the_other_planes_are_not_concerned():
    """The control plane and identities are filed on what their rows name (AL1c)."""
    assert routing_refusal("azure_activity", "AzureActivity | project Caller") == ""
    assert routing_refusal("azure_entra", "AuditLogs | project OperationName") == ""
    assert routing_refusal("azure_monitor", "SigninLogs | project UserPrincipalName") == ""
    assert routing_refusal("azure_monitor", "AzureActivity | project Caller") == ""
    assert routing_refusal("azure_monitor", BY_HOST) != ""


def test_the_data_plane_copy_agrees_with_the_watch():
    """eregion_core's copy (for analysis/triage.py, which cannot import glorfindel) reads the
    planes as `RulePoller._plane` does: every registered source, and the tables that move a
    query of another source to the control plane or to identities."""
    from types import SimpleNamespace
    from glorfindel.detectors import _DETECTORS
    queries = ["Syslog | where x", "AzureActivity | project Caller", "SigninLogs | take 1",
               "AADServicePrincipalSignInLogs | take 1", "Syslog // AzureActivity\n| take 1"]
    for source in list(_DETECTORS) + ["", "unknown"]:
        for q in queries:
            watch = RulePoller._plane(SimpleNamespace(source=source or "azure_monitor", query=q)) == "data"
            assert rule_routing.data_plane(source, q) is watch, (source, q)


def _proposal(query: str) -> str:
    from glorfindel.proposed_rules import record
    return record(run_id="20261109T120000Z", ttp="T1070.002", resource_id=RID, rule_name="log-clearing",
                  source="azure_monitor", workspace_id="", query=query, interval_s=30.0,
                  explanation="Log files removed", confidence=0.8, analysis="a")


def test_an_approval_of_a_rule_routed_by_its_host_name_is_refused_clearly():
    """The model may propose a rule without `_ResourceId`: approved, it loaded in the client's
    layer and routed by the host name. Refused at approval, said, the proposal kept pending."""
    from glorfindel import rule_layers
    from glorfindel.proposed_rules import approve, pending
    pid = _proposal(BY_HOST)
    with pytest.raises(ValueError) as refused:
        approve(pid, SHIPPED_BASE)
    words = str(refused.value)
    assert "log-clearing" in words and "_ResourceId" in words and "Computer" in words
    assert [p["id"] for p in pending()] == [pid]
    assert not rule_layers.client_rules_path().exists() or \
        "log-clearing" not in rule_layers.client_rules_path().read_text()
    # The same rule with its resource: approved, and loaded.
    ok = approve(_proposal(BY_HOST + ", _ResourceId"), SHIPPED_BASE)
    assert ok["status"] == "approved"


def test_the_cli_says_why_an_approval_is_refused():
    from click.testing import CliRunner
    from glorfindel.cli import cli
    pid = _proposal(BY_HOST)
    res = CliRunner().invoke(cli, ["approve-rule", pid, "--rules", str(SHIPPED_BASE)])
    assert "Error" in res.output and "_ResourceId" in res.output


# ── The RulePoller, then decide ─────────────────────────────────────────────────────────

class _Det:
    def __init__(self, rows):
        self.rows = rows

    def run_query(self, query, timespan=None):
        return list(self.rows)


class _Asset:
    def __init__(self, rid):
        self.resource_id, self.name = rid, rid.rsplit("/", 1)[-1]


class _Registry:
    def __init__(self, *rids):
        self.assets = [_Asset(r) for r in rids]

    def for_backend(self, _name):
        return self.assets


def _rule(**kw) -> DetectionRule:
    base = dict(name="data-exfiltration-blob", source="azure_monitor", workspace_id="ws", ttp="T1041",
                query="StorageBlobLogs | where TimeGenerated > ago(5m)", resource_id="", interval_s=30.0,
                enabled=True, description="", auto_apply=True)
    base.update(kw)
    return DetectionRule(**base)


def _poll(rule, rows, rids, owners) -> list[dict]:
    from glorfindel.detection_rules import _save_status
    _save_status({})                     # each poll a first one: nothing deduplicated
    sent: list = []
    p = RulePoller([rule], sent.append, ip_owners=owners)
    p._detector = lambda r: _Det(rows)
    p._registry = _Registry(*rids) if rule.auto_apply else None
    p.poll_once(rule)
    return sent


VM2 = RID.replace("vm-s4", "vm-two")


def test_a_row_named_only_by_its_host_name_routes_to_no_vm():
    """V-04: a row whose `Computer` is the other VM's name — written by root on the VM — is no
    attribution: unattributed, the isolation held, whichever VM the card is anchored on."""
    rule = _rule(name="ransomware-disk-write", ttp="T1486", query="Perf | where x")
    for rids in ([RID, VM2], [VM2]):
        (sig,) = _poll(rule, [{"Computer": "vm-two", "MaxWrite": 9e7}], rids, None)
        assert sig["context"]["attribution"] == "unattributed", rids
        assert _decide(sig, _decision())["held_by"] == "attribution"
    # Its resource names it.
    (sig,) = _poll(rule, [{"Computer": "vm-s4", "_ResourceId": VM2, "MaxWrite": 9e7}], [RID, VM2], None)
    assert sig["resource_id"] == VM2 and sig["context"]["attribution"] == "asset"


# ── 2. V-05: an appliance's address ─────────────────────────────────────────────────────

HUB = vm_id("rg-hub", "hub-fw")
SPOKE = vm_id("rg-spoke", "app-1")


def _hub_and_spoke():
    """A hub's firewall (two NICs, IP forwarding on the trusted one: the SNAT goes out by the
    other) and a spoke VM behind it; the connector reads them from the in-memory Azure."""
    from glorfindel.actions import AzureConnector
    f = FakeAzure()
    net = subnet_id("rg-hub", "vnet-hub", "fw")
    f.add_vm("rg-hub", "hub-fw", [
        {"rg": "rg-hub", "name": "fw-trusted", "ips": ["10.0.0.4"], "subnet": net, "nsg": None,
         "forwarding": True},
        {"rg": "rg-hub", "name": "fw-untrusted", "ips": ["10.0.1.4"], "subnet": net, "nsg": None}])
    f.add_vm("rg-spoke", "app-1", [{"rg": "rg-spoke", "name": "app-nic", "ips": ["10.1.0.4"],
                                    "subnet": subnet_id("rg-spoke", "vnet-spoke", "app"), "nsg": None}])
    c = AzureConnector(dry_run=False)
    c._network, c._compute = f.network, f.compute
    c.__dict__["_ensure_clients"] = lambda: None
    return c


def test_the_connector_marks_every_address_of_a_vm_that_forwards():
    owners = _hub_and_spoke().private_ip_owners()
    assert owners == {"10.0.0.4": appliance_owner(HUB), "10.0.1.4": appliance_owner(HUB),
                      "10.1.0.4": SPOKE}


def _exfil(ip: str) -> dict:
    return {"CallerIpAddress": f"{ip}:50374", "AccountName": "stexample", "PutBlobCount": 40}


@pytest.mark.parametrize("ip", ["10.0.0.4", "10.0.1.4"])
def test_an_exfiltration_through_the_appliance_is_never_pinned_on_it(ip):
    """V-05: the storage service sees the SNAT's address. The card is anchored on the appliance
    (what the address names, said as such), unattributed: no action at all — neither the
    isolation that cuts the hub, nor a block, nor a snapshot — and the card says where to look."""
    owners = _hub_and_spoke().private_ip_owners
    (sig,) = _poll(_rule(), [_exfil(ip)], [HUB, SPOKE], owners)
    ctx = sig["context"]
    assert sig["resource_id"] == HUB
    assert ctx["attribution"] == "unattributed" and ctx["attribution_via"] == "appliance"
    assert ctx["appliance"] == "hub-fw"
    for action in ("isolate_vm", "block_suspicious_ip", "snapshot", "release_isolation"):
        final = _decide(sig, _decision(action=action))
        assert final["escalate"] is True and final["held_by"] == "attribution", action
        assert "hub-fw" in final["escalation_reason"] and "journaux de l'appliance" in final["escalation_reason"]
    # The model's own escalation keeps its words, after the appliance's.
    final = _decide(sig, _decision(escalate=True, escalation_reason="doute du modèle"))
    assert final["held_by"] == "attribution" and final["escalation_reason"].endswith("doute du modèle")
    # The spoke's own address still names it.
    (sig,) = _poll(_rule(), [_exfil("10.1.0.4")], [HUB, SPOKE], owners)
    assert sig["resource_id"] == SPOKE and sig["context"]["attribution"] == "asset"
    assert _decide(sig, _decision())["action"] == "isolate_vm" and not _decide(sig, _decision())["escalate"]


def test_a_rule_bound_to_the_appliance_never_takes_its_rows():
    """A rule bound to one asset takes the rows that name none: never one made from behind it."""
    rule = _rule(auto_apply=False, resource_id=HUB, asset_name="hub-fw")
    (sig,) = _poll(rule, [_exfil("10.0.0.4")], [], _hub_and_spoke().private_ip_owners)
    assert sig["context"]["attribution"] == "unattributed" and sig["context"]["attribution_via"] == "appliance"
    assert _decide(sig, _decision())["held_by"] == "attribution"


def test_the_appliance_unwatched_still_holds_everything():
    (sig,) = _poll(_rule(), [_exfil("10.0.0.4")], [SPOKE], _hub_and_spoke().private_ip_owners)
    assert sig["resource_id"] == SPOKE and sig["context"]["attribution_via"] == "appliance"
    assert _decide(sig, _decision(action="snapshot"))["held_by"] == "attribution"


def test_an_attack_started_through_the_appliance_holds_everything():
    """`respond`'s reading is the RulePoller's: the line's VM, the appliance's address — held."""
    out, _ = _resolve(_started(), [_exfil("10.0.0.4")], owners={"10.0.0.4": appliance_owner(RID)},
                      query="StorageBlobLogs | where x")
    assert out["context"]["attribution"] == "unattributed"
    assert out["context"]["attribution_via"] == "appliance" and out["context"]["appliance"] == "vm-s4"
    final = _decide(out, _decision(action="snapshot"))
    assert final["held_by"] == "attribution" and "journaux de l'appliance" in final["escalation_reason"]


def test_a_control_plane_card_says_the_call_came_from_behind_the_appliance():
    from glorfindel import card_target
    t = card_target.of_row({"OperationNameValue": "MICROSOFT.NETWORK/NETWORKSECURITYGROUPS/WRITE"},
                           "control", None, [], None, caller_appliance="hub-fw")
    assert "hub-fw" in t["via"] and "the source VM is behind it" in t["via"]
    rule = _rule(name="nsg", source="azure_activity", query="AzureActivity | where x")
    row = {"OperationNameValue": "MICROSOFT.NETWORK/NETWORKSECURITYGROUPS/WRITE", "CorrelationId": "c",
           "CallerIpAddress": "10.0.0.4", "_ResourceId": "/subscriptions/s/resourceGroups/rg/providers/"
                                                         "Microsoft.Network/networkSecurityGroups/nsg"}
    (sig,) = _poll(rule, [row], [HUB, SPOKE], _hub_and_spoke().private_ip_owners)
    assert "hub-fw" in sig["context"]["target"]["via"]
    assert agent._is_control_plane(sig)


# ── 3. A row read by the keys its query proves (SEC-A4, review R1) ──────────────────────

APP_Q = "App_CL | project TimeGenerated, _ResourceId, ResourceId, CallerIpAddress"
BY_ROOT = [{"_ResourceId": "", "ResourceId": VM2, "MaxWrite": 9e7},   # a custom table fed from a VM
           {"_ResourceId": "", "CallerIpAddress": "10.0.0.5", "MaxWrite": 8e7}]


def test_a_row_is_read_by_the_keys_its_query_proves_only():
    """The load proves `_ResourceId` for this query, nothing else: a row whose `_ResourceId` is
    empty (the ingestion API) is never routed by a `ResourceId` or a `CallerIpAddress` root
    writes — unattributed, the isolation held. The RulePoller and an attack_started alike."""
    from glorfindel.detection_rules import RowAttribution, proven_keys
    assert rule_routing.routing_columns(APP_Q) == {"_ResourceId"}
    owners = {"10.0.0.5": VM2}
    for row in BY_ROOT:
        (sig,) = _poll(_rule(name="app", ttp="T1486", query=APP_Q), [row], [RID, VM2], lambda: owners)
        assert sig["context"]["attribution"] == "unattributed", row
        assert _decide(sig, _decision())["held_by"] == "attribution"
        out, _ = _resolve(_started(), [row], owners={"10.0.0.5": RID}, query=APP_Q)
        assert out["context"]["attribution"] == "unattributed", row
    index = RowAttribution([(RID, "vm-s4"), (VM2, "vm-two")], lambda: owners, keys=proven_keys(APP_Q))
    assert [index.attribute(r) for r in BY_ROOT] == [(False, None), (False, None)]
    assert index.attribute({"_ResourceId": VM2}) == (True, (VM2, "vm-two"))
    # What a storage query proves: the caller's address, as before.
    storage = RowAttribution([(VM2, "vm-two")], lambda: owners, keys=proven_keys("StorageBlobLogs | where x"))
    assert storage.attribute({"CallerIpAddress": "10.0.0.5:5000"}) == (True, (VM2, "vm-two"))
    # The control plane reads its rows as they are (AL1c): no keys.
    assert RowAttribution([(VM2, "vm-two")]).attribute({"ResourceId": VM2}) == (True, (VM2, "vm-two"))
