"""SDK1a (#992): each reader of Log Analytics rows in Glorfindel, read once on the objects of the
pinned SDK — never on a Python list a test made up.

The readers were tested on `kql_subset`'s rows or on dicts: a `dynamic` column a list, a date
what the test wrote. The SDK (azure-monitor-query, the version requirements/glorfindel.txt locks)
hands a `dynamic` column on as its JSON text and a `datetime` column as a `datetime` — SLF1 passed
its tests that way and did nothing in production (SLF1b). Here each reader gets its reply through
the SDK's own client (tests/unit/sdk_logs.py): the detector (`run_query`, `poll_alert`, and the
errors the SDK raises), the Activity Log's and Entra ID's adapters, the rule poller and the
correlation, the discovery, the audit's checks, `rules check`, the schema read before authoring,
the enquiry of `investigate`. The campaign replay's is in tests/unit/test_campaign_replay.py (it
crosses to Annatar), the own channel's and auditd's in tests/unit/test_own_channel_sdk.py, the
unreadable Activity reply's in tests/unit/test_control_plane_unreadable.py.

No Azure, no model, no network; every identifier is made up (repository public).
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from glorfindel import correlation, rule_check
from glorfindel.detection_rules import RulePoller, load_config, shipped_rules_path
from glorfindel.providers.azure.activity import AzureActivityDetector
from glorfindel.providers.azure.entra import AzureEntraDetector

from . import sdk_logs
from . import test_correlation as tc

ROOT = Path(__file__).resolve().parents[2]
SHIPPED_PATH = shipped_rules_path()
SHIPPED = {r["name"]: r for r in yaml.safe_load(SHIPPED_PATH.read_text())["rules"]}
SUB = "/subscriptions/00000000-0000-0000-0000-0000000000cc"
VM1 = f"{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/vm-example-01"
NSG = f"{SUB}/resourceGroups/rg-example/providers/Microsoft.Network/networkSecurityGroups/nsg-web"
OWN_APP = "a1111111-b111-c111-d111-e11111111111"
OWN_OID = "a2222222-b222-c222-d222-e22222222222"
OUTSIDER = "someone@example.org"
OUTSIDER_OID = "b3333333-c333-d333-e333-f33333333333"
OID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"
AT = datetime(2026, 11, 20, 11, 58, 7, 123456, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_ambient_identity(monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)


def _iso_z(at: datetime) -> str:
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


class _AppToken:
    """Glorfindel's token, an application's: its appid and oid (what `own_identities` reads)."""

    def get_token(self, _scope):
        def b64(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        claims = {"appid": OWN_APP, "oid": OWN_OID, "idtyp": "app"}
        return SimpleNamespace(token=f"{b64({'alg': 'none'})}.{b64(claims)}.sig")


# ── the utility: the pinned SDK's own client, and what it hands on ──────────────────────────────

def test_the_sdk_read_here_is_the_one_the_image_locks():
    """The SDK these tests read is the version Glorfindel's image installs (requirements/
    glorfindel.txt): its types are the ones production gets."""
    import azure.monitor.query as sdk
    locked = re.search(r"^azure-monitor-query==(\S+) \\$", (ROOT / "requirements/glorfindel.txt").read_text(),
                       re.MULTILINE)
    assert locked and sdk.__version__ == locked.group(1)
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of([])))
    assert type(ws.client()).__module__.startswith("azure.monitor.query")


def test_every_type_comes_out_as_the_sdk_hands_it_on():
    """A reply of every type, through the SDK: a `dynamic` column is its JSON text — never the
    list the test wrote —, a `datetime` an aware `datetime` (the SDK's own UTC), a `guid` a text,
    numbers and booleans as JSON reads them."""
    row = {"TimeGenerated": AT, "Writers": [{"writer": OWN_OID, "writes": 3}], "Bag": {"k": "v"},
           "N": 3, "Ratio": 1.5, "Ok": True, "Name": "vm-example-01", "Id": OWN_OID, "Small": 7}
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of([row], {"Id": "guid", "Small": "int"})))
    [out] = ws.detector().run_query("Rows | take 1")
    assert isinstance(out["Writers"], str) and json.loads(out["Writers"]) == row["Writers"]
    assert isinstance(out["Bag"], str) and json.loads(out["Bag"]) == {"k": "v"}
    assert isinstance(out["TimeGenerated"], datetime) and out["TimeGenerated"] == AT
    # The SDK's own UTC (isodate's), not Python's: a reader that compares `tzinfo is timezone.utc`
    # would take an aware time for a naive one; one that compares instants is right either way.
    assert out["TimeGenerated"].tzinfo is not timezone.utc and out["TimeGenerated"].utcoffset().total_seconds() == 0
    assert (out["N"], out["Ratio"], out["Ok"], out["Name"], out["Id"], out["Small"]) == (
        3, 1.5, True, "vm-example-01", OWN_OID, 7)
    assert type(out["N"]) is int and type(out["Ratio"]) is float and type(out["Ok"]) is bool
    # What the client sent: the query and the window, as the API reads them.
    [sent] = ws.requests
    assert sent["url"] == "https://api.loganalytics.io/v1/workspaces/ws-test/query"
    assert sent["query"] == "Rows | take 1" and re.fullmatch(r"\S+Z/\S+Z", sent["timespan"])


# ── the detector: run_query, poll_alert, and what the SDK raises ────────────────────────────────

def test_run_query_reads_every_table_and_sends_the_window_it_is_given():
    two = sdk_logs.body(sdk_logs.table([{"A": 1}]), sdk_logs.table([{"B": [1, 2]}], name="Table_1"))
    ws = sdk_logs.Workspace(sdk_logs.constant(two))
    start = AT - timedelta(minutes=10)
    assert ws.detector().run_query("Q", timespan=(start, AT)) == [{"A": 1}, {"B": "[1, 2]"}]
    assert ws.requests[0]["timespan"] == f"{_iso_z(start)}/{_iso_z(AT)}"


def test_run_query_raises_on_a_partial_reply_and_lets_the_sdk_error_through():
    """A partial reply (the SDK's `LogsQueryPartialResult`) is no result: raised, never its rows
    taken for the whole. A refused query raises the SDK's own `HttpResponseError`, its status read."""
    from azure.core.exceptions import HttpResponseError
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.partial(sdk_logs.body_of([{"A": 1}]))))
    with pytest.raises(RuntimeError, match="not successful"):
        ws.detector().run_query("Q")
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.failure(403, "InsufficientAccessError", "no access")))
    with pytest.raises(HttpResponseError) as exc:
        ws.detector().run_query("Q")
    assert exc.value.status_code == 403


def test_poll_alert_hands_the_sdk_row_to_its_matcher_and_back():
    """`poll_alert` (resolve_attack_started, the adapters): the row its matcher reads and the row it
    returns are the SDK's — a `dynamic` column a text, a date a `datetime`."""
    rows = [{"TimeGenerated": AT, "Computer": "vm-other", "Set": ["x"]},
            {"TimeGenerated": AT, "Computer": "vm-example-01", "Set": ["y"]}]
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of(rows)))
    seen: list = []

    def match(row):
        seen.append(row)
        return row["Computer"] == "vm-example-01"
    elapsed, row = ws.detector().poll_alert("Q", since=AT.timestamp(), timeout_s=5, interval_s=0,
                                            verbose=False, match_row=match)
    assert row == {"TimeGenerated": AT, "Computer": "vm-example-01", "Set": '["y"]'}
    assert [type(r["Set"]) for r in seen] == [str, str] and isinstance(row["TimeGenerated"], datetime)


def test_poll_alert_on_partial_replies_only_is_an_unreachable_workspace():
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.partial(sdk_logs.body_of([{"A": 1}]))))
    with pytest.raises(RuntimeError, match="workspace unreachable"):
        ws.detector().poll_alert("Q", since=AT.timestamp(), timeout_s=0.2, interval_s=0.02, verbose=False)
    assert ws.requests                         # it reached the workspace: partial, never « no match »


# ── the Activity Log's adapter (activity.py): its marks, its drains, on the SDK's rows ───────────

def _activity_line(status, minutes_ago, caller=OUTSIDER, oid=OUTSIDER_OID, app="", now=None):
    return {"Type": "AzureActivity", "TimeGenerated": (now or AT) - timedelta(minutes=minutes_ago),
            "OperationNameValue": "MICROSOFT.NETWORK/NETWORKSECURITYGROUPS/SECURITYRULES/WRITE",
            "ActivityStatusValue": status, "Caller": caller, "CallerIpAddress": "203.0.113.7",
            "Claims": json.dumps({"appid": app, OID_CLAIM: oid}), "_ResourceId": f"{NSG}/securityRules/allow-web",
            "ResourceGroup": "rg-example", "CorrelationId": "c-1"}


def _poller(rule_name, det):
    cfg = SimpleNamespace(monitoring_backends=[SimpleNamespace(
        name="law-example", type="azure_monitor", workspace_id="ws-test", endpoint="")])
    rule = next(r for r in load_config(SHIPPED_PATH, glorfindel_cfg=cfg, client_layer=False).rules
                if r.name == rule_name)
    sent: list = []
    p = RulePoller([rule], sent.append)
    p._detector = lambda _rule: det
    p._registry = SimpleNamespace(for_backend=lambda _name: [SimpleNamespace(name="vm-example-01",
                                                                             resource_id=VM1)])
    return p, rule, sent


def test_an_nsg_write_read_through_the_sdk_is_one_card_that_names_its_caller():
    """The shipped rule run as written, its rows through the SDK (`TimeGenerated` a `datetime`,
    `Succeeded` a number): one high card that names its caller, the same operation never twice."""
    from glorfindel.agent import _control_plane_text
    now = datetime.now(timezone.utc)
    lines = [_activity_line("Start", 6, now=now), _activity_line("Success", 5, now=now)]
    det = sdk_logs.Workspace(sdk_logs.kql(lines, now=now)).detector(AzureActivityDetector,
                                                                     credential=_AppToken())
    p, rule, sent = _poller("nsg-change-outside-glorfindel", det)
    p.poll_once(rule)
    assert len(sent) == 1 and sent[0]["severity"] == "high"
    row = sent[0]["raw_signal"]["first_result_row"]
    assert isinstance(row["TimeGenerated"], datetime) and row["Succeeded"] == 1
    assert (row["GlorfindelManaged"], row["GlorfindelIdentity"]) == (False, False)
    what, _steps = _control_plane_text(sent[0])
    assert f"par {OUTSIDER}" in what
    p.poll_once(rule)
    assert len(sent) == 1


def test_glorfindel_s_own_write_named_by_its_claims_is_set_aside_through_the_sdk():
    """A client's rule that projects `Claims_d` (dynamic, so a JSON text through the SDK): a write of
    Glorfindel's identity on its quarantine NSG is its own — read from the claims' text, set aside,
    by `run_query` and by `poll_alert` (resolve_attack_started on the control plane) alike."""
    quarantine = f"{SUB}/resourceGroups/rg-example/providers/Microsoft.Network/networkSecurityGroups/nsg-glorfindel-quarantine-vm-example-01"
    row = {"TimeGenerated": AT, "OperationNameValue": "MICROSOFT.NETWORK/NETWORKSECURITYGROUPS/WRITE",
           "ActivityStatusValue": "Success", "Claims_d": {"appid": OWN_APP, OID_CLAIM: OWN_OID},
           "_ResourceId": quarantine.lower(), "CorrelationId": "c-own"}
    other = {**row, "Claims_d": {"appid": "", OID_CLAIM: OUTSIDER_OID}, "CorrelationId": "c-other"}
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of([row, other])))
    kept = ws.detector(AzureActivityDetector, credential=_AppToken()).run_query("AzureActivity | project …")
    assert [r["CorrelationId"] for r in kept] == ["c-other"]
    assert isinstance(kept[0]["Claims_d"], str)
    _elapsed, polled = ws.detector(AzureActivityDetector, credential=_AppToken()).poll_alert(
        "AzureActivity | project …", since=AT.timestamp(), timeout_s=5, interval_s=0, verbose=False)
    assert polled["CorrelationId"] == "c-other" and polled["GlorfindelIdentity"] is False


def _isolated(vm, drains):
    """Glorfindel's isolation state of `vm`, with the drains it recorded (as SID1 writes it)."""
    import glorfindel.actions as actions
    d = actions._ISOLATION_STATE_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{vm.rsplit('/', 1)[-1]}.json").write_text(json.dumps(
        {"resource_id": vm, "placements": [], "drains_at": [t.isoformat() for t in drains]}))


def test_the_drain_of_an_isolation_read_through_the_sdk_is_nothing():
    """SID1's rule: the Run Command of a drain Glorfindel recorded, its `Started` and `TimeGenerated`
    the SDK's `datetime` — attached to the drain, nothing; outside any isolation, a card."""
    drain = AT - timedelta(minutes=5)
    row = {"TimeGenerated": drain + timedelta(seconds=70), "Started": drain + timedelta(seconds=30),
           "OperationNameValue": "MICROSOFT.COMPUTE/VIRTUALMACHINES/RUNCOMMAND/ACTION",
           "ActivityStatusValue": "Success", "Caller": OWN_OID, "CallerIpAddress": "198.51.100.4",
           "CallerAppId": "", "CallerObjectId": OWN_OID, "_ResourceId": VM1.lower(),
           "ResourceGroup": "rg-example", "CorrelationId": "c-run", "WatchedCaller": "glorfindel"}
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of([row])))
    det = ws.detector(AzureActivityDetector, credential=_AppToken())
    [card] = det.run_query(SHIPPED["run-command-by-glorfindel-outside-isolation"]["query"])
    assert card["GlorfindelRunCommand"] == "no_isolation" and isinstance(card["Started"], datetime)
    _isolated(VM1, [drain])
    det = ws.detector(AzureActivityDetector, credential=_AppToken())
    assert det.run_query(SHIPPED["run-command-by-glorfindel-outside-isolation"]["query"]) == []


# ── Entra ID's adapter (entra.py): thresholds, marks, the plan's hour ───────────────────────────

ENTRA_TYPES = {"TimeGenerated": "datetime", "AdminConsent": "bool", "SignIns": "long",
               "BaselineSignIns": "long", "BaselineDays": "long"}


def _entra(kind, **kw):
    row = {"TimeGenerated": AT, "EntraKind": kind, "EntraOperation": f"op {kind}", "EventId": f"e-{kind}",
           "Result": "success", "ActorName": "admin@example.org", "ActorId": OUTSIDER_OID, "ActorAppId": "",
           "ActorIp": "203.0.113.7", "TargetName": "app-example", "TargetId": "c5555555-d555-e555-f555-a55555555555",
           "TargetType": "ServicePrincipal", "CorrelationId": f"corr-{kind}"}
    return {**row, **kw}


def test_entra_rows_through_the_sdk_keep_their_thresholds_marks_and_hour():
    """Entra ID's columns as the SDK hands them on — `BaselineDays` a number, `AdminConsent` a
    boolean, `TimeGenerated` a `datetime`: the thresholds hold, the marks are set, the card says an
    administrator's consent, the plan reads the event's hour."""
    from glorfindel.providers.azure import entra, entra_plan
    rows = [_entra("role", RoleName="Global Administrator", EventId="e-role-1"),
            _entra("role", RoleName="Reports Reader", EventId="e-role-2"),
            _entra("signin", BaselineDays=2, SignIns=4, BaselineSignIns=20, EventId="e-new"),
            _entra("signin", BaselineDays=5, SignIns=4, BaselineSignIns=90, EventId="e-old"),
            _entra("consent", AdminConsent=True, Permissions="User.Read", ActorId=OWN_OID)]
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of(rows, ENTRA_TYPES)))
    det = ws.detector(AzureEntraDetector, credential=_AppToken())
    kept = det.run_query(SHIPPED["entra-privileged-role-assigned"]["query"])
    assert [r["EventId"] for r in kept] == ["e-role-1", "e-old", "e-consent"]
    role, signin, consent = kept
    assert type(signin["BaselineDays"]) is int and consent["AdminConsent"] is True
    assert (consent["GlorfindelIdentity"], role["GlorfindelIdentity"]) == (True, False)
    what, _steps = entra.describe(consent)
    assert "consentement d'administrateur" in what
    assert entra_plan.build(role, None)["event_at"] == _iso_z(AT)
    # poll_alert: the first row above the thresholds, marked.
    _elapsed, first = det.poll_alert(SHIPPED["entra-privileged-role-assigned"]["query"], since=AT.timestamp(),
                                     timeout_s=5, interval_s=0, verbose=False)
    assert first["EventId"] == "e-role-1" and first["GlorfindelManaged"] is False


# ── the rule poller and the correlation (detection_rules.py, correlation.py) ─────────────────────

def test_a_brute_force_and_its_login_through_the_sdk_are_one_critical_card():
    """`ssh-brute-force` and the correlation's query, both through the SDK: `FailedAttempts` a
    number, the login's time a `datetime` the card writes in ISO 8601; deduplicated after."""
    lines = tc._attempts(tc.STRANGER) + tc._login(tc.STRANGER, account="ops", minutes_ago=1, method="password")
    ws = sdk_logs.Workspace(sdk_logs.kql(lines, now=tc.NOW))
    p, rule, _sent, _kql = tc._poller(lines, rule_name="ssh-brute-force")
    det = ws.detector()
    p._detector = lambda _r: det
    [sig] = p.poll_once(rule)
    row = sig["raw_signal"]["first_result_row"]
    assert sig["severity"] == "critical" and row["Correlation"] == correlation.COMPROMISED
    assert type(row["FailedAttempts"]) is int and row["FailedAttempts"] == 12
    accepted = next(x for x in lines if x["SyslogMessage"].startswith("Accepted "))
    assert row["SuccessfulLogins"] == [{"account": "ops", "method": "password",
                                        "at": accepted["TimeGenerated"].isoformat()}]
    assert len(ws.requests) == 2 and "ProcessID" in ws.requests[1]["query"]
    assert p.poll_once(rule) == []


def test_a_root_shell_from_a_declared_origin_through_the_sdk_is_set_aside():
    """ADM1 and COR1 on the SDK's rows: the sudo line and the session's lines, their times
    `datetime`, the session read and its origin found — no card."""
    lines = tc._login(tc.BASTION) + [tc._row(tc.SUDO_I)]
    ws = sdk_logs.Workspace(sdk_logs.kql(lines, now=tc.NOW))
    p, rule, sent, _kql = tc._poller(lines)
    det = ws.detector()
    p._detector = lambda _r: det
    assert p.poll_once(rule) == []
    assert p.status_snapshot()[0]["correlation"]["origin"] == 1


# ── discovery (discovery.py): the Heartbeat's last time ─────────────────────────────────────────

def test_discovery_reads_the_heartbeat_s_last_time_from_the_sdk(monkeypatch):
    """`LastSeen` (max(TimeGenerated)) comes out of the SDK a `datetime`: the asset keeps the real
    last heartbeat, in ISO 8601 — never now, never a text it could not read."""
    from glorfindel.discovery import _discover_from_azure_monitor
    now = datetime.now(timezone.utc).replace(microsecond=250000)
    beats = [{"Type": "Heartbeat", "TimeGenerated": now - timedelta(minutes=m),
              "Computer": "vm-example-01.internal.example.net", "_ResourceId": VM1,
              "SourceComputerId": "d6666666-e666-f666-a666-b66666666666"} for m in (40, 25)]
    sdk_logs.Workspace(sdk_logs.kql(beats, now=now)).serve(monkeypatch)
    [asset] = _discover_from_azure_monitor("law-example", "ws-test")
    assert (asset.name, asset.resource_id) == ("vm-example-01", VM1)
    assert asset.last_seen == (now - timedelta(minutes=25)).isoformat()


# ── the audit's checks (audit.py): the sampling, Syslog, the unattributed lines ─────────────────

def _audit_answer(perf_rows, syslog_rows, unattributed=0):
    def answer(query, _timespan):
        if "isempty(_ResourceId)" in query:
            return sdk_logs.body_of([{"n": unattributed}], {"n": "long"})
        if "summarize n = sum(c)" in query:
            return sdk_logs.body_of(perf_rows, {"n": "long", "step": "long", "gaps": "long"},
                                    columns=["InstanceName", "n", "step", "gaps"])
        return sdk_logs.body_of(syslog_rows, {"n": "long"}, columns=["n", "facilities"])
    return answer


def test_the_audit_reads_its_counts_through_the_sdk():
    from glorfindel.audit import _check_perf_sampling, _check_syslog
    det = sdk_logs.Workspace(_audit_answer(
        [{"InstanceName": "/", "n": 240, "step": 15, "gaps": 239}],
        [{"n": 1200, "facilities": "auth, authpriv"}])).detector()
    perf = _check_perf_sampling(VM1, "ws-test", detector=det)
    assert (perf.status, perf.data) == ("ok", {"present": True, "samples": 240, "step_s": 15})
    syslog = _check_syslog(VM1, "ws-test", detector=det)
    assert syslog.status == "ok" and syslog.data == {"present": True, "rows": 1200, "facilities": "auth, authpriv"}


def test_the_audit_says_a_blind_vm_and_its_unattributed_lines_through_the_sdk():
    from glorfindel.audit import _check_perf_sampling, _check_syslog
    det = sdk_logs.Workspace(_audit_answer([], [{"n": 0, "facilities": ""}], unattributed=3)).detector()
    perf = _check_perf_sampling(VM1, "ws-test", detector=det)
    assert perf.status == "warn" and perf.data == {"present": False, "unattributed": 3}
    syslog = _check_syslog(VM1, "ws-test", detector=det)
    assert syslog.data == {"present": False, "unattributed": 3}


# ── `glorfindel rules check` (rule_check.py): rows, and the SDK's own errors ────────────────────

_RULE = SimpleNamespace(name="ssh-brute-force", layer="base", source="azure_monitor",
                        query="Syslog | where TimeGenerated > ago(15m) | take 2")


@pytest.mark.parametrize("reply, status, kind, code", [
    (sdk_logs.body_of([{"Computer": "vm-example-01", "FailedAttempts": 12}] * 2), "ok", "", ""),
    (sdk_logs.failure(400, "BadArgumentError", "The request had some invalid properties", {
        "code": "SemanticError", "message": "A semantic error occurred.", "innererror": {
            "code": "SEM0100", "message": "'where' operator: Failed to resolve table or column expression named 'NoSuchTable'"}}),
     "error", "table", "SEM0100"),
    (sdk_logs.failure(400, "BadArgumentError", "The request had some invalid properties", {
        "code": "SyntaxError", "message": "A syntax error occurred.", "innererror": {
            "code": "SYN0002", "message": "Query could not be parsed at 'BROKEN' on line [1,8]"}}),
     "error", "syntax", "SYN0002"),
    (sdk_logs.failure(403, "InsufficientAccessError", "The provided credentials have insufficient access"),
     "error", "access", "403"),
    (sdk_logs.failure(404, "WorkspaceNotFoundError", "Workspace could not be found"), "error", "workspace", "404"),
    (sdk_logs.partial(sdk_logs.body_of([{"A": 1}])), "unproven", "partial", ""),
], ids=["rows", "table", "syntax", "forbidden", "not-found", "partial"])
def test_rules_check_reads_the_sdk_s_rows_and_errors(reply, status, kind, code):
    """What `rules check` (and the CD after a switch) says of a reply, from the SDK's own objects
    and the `HttpResponseError` it raises: its rows counted, a lasting error by its kind and KQL's
    code, a partial reply unproven — never an unknown error."""
    ws = sdk_logs.Workspace(sdk_logs.constant(reply))
    out = rule_check.run_once(_RULE, 5.0, lambda _r: ws.detector())
    assert (out.status, out.kind) == (status, kind)
    if code:
        assert out.code == code
    if status == "ok":
        assert out.rows == 2
    assert re.fullmatch(r"\S+Z/\S+Z", ws.requests[0]["timespan"])


# ── the schema read before authoring (detection_authoring.py) ───────────────────────────────────

def test_the_schema_is_read_from_getschema_through_the_sdk():
    from glorfindel.detection_authoring import fetch_table_schema
    rows = [{"ColumnName": "TimeGenerated", "ColumnType": "datetime"},
            {"ColumnName": "SyslogMessage", "ColumnType": "string"}]
    ws = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.body_of(rows)))
    assert fetch_table_schema(ws.detector(), "Syslog") == [
        {"name": "TimeGenerated", "type": "datetime"}, {"name": "SyslogMessage", "type": "string"}]
    assert ws.requests[0]["query"] == "Syslog | getschema | project ColumnName, ColumnType"
    refused = sdk_logs.Workspace(sdk_logs.constant(sdk_logs.failure(400, "BadArgumentError", "no such table")))
    assert fetch_table_schema(refused.detector(), "Nope") == []


# ── the enquiry of `investigate` (agent.py, _run_investigative_query) ───────────────────────────

def _inv_state(first_row):
    return {"signal": {"signal_id": "inv-sdk", "event": "detection", "resource_id": VM1, "ttp": "T1548.003",
                       "severity": "high", "context": {"run_id": "test"},
                       "raw_signal": {"log_analytics_workspace_id": "ws-test", "first_result_row": first_row}},
            "past_cycles": [], "incident": None, "dry_run": False}


def test_the_enquiry_reads_its_rows_through_the_sdk_and_a_refusal_is_a_gap(monkeypatch):
    """The enquiry's rows come out of the SDK (a date a `datetime`, a rounded number a float): kept
    as they are in the context the model reads — rendered, never raised on —; a query the SDK
    refuses is a gap for the guard of `decide`, never « nothing found »."""
    from glorfindel.agent import _build_user_message, investigate

    def answer(query, _timespan):
        if query.startswith("Perf"):
            return sdk_logs.failure(403, "InsufficientAccessError", "no access")
        return sdk_logs.body_of([{"TimeGenerated": AT, "SyslogMessage": "sudo: user1 : USER=root ; COMMAND=/bin/id"}])
    sdk_logs.Workspace(answer).serve(monkeypatch)
    syslog = "sudo: user1 : TTY=pts/0 ; USER=root ; COMMAND=/bin/bash"
    out = investigate(_inv_state({"Computer": "vm-example-01", "SyslogMessage": syslog}))
    ctx = out["signal"]["raw_signal"]["investigative_context"]
    assert ctx["root_commands"][0]["TimeGenerated"] == AT and ctx["disk_write_after_escalation"] == []
    assert out["telemetry_gaps"] == ["disk_write_after_escalation"]
    assert str(AT) in _build_user_message(out["signal"], [])
