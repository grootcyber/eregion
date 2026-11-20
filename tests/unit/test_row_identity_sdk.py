"""RID1 (#1002): the identity of an aggregated row leaves out the JSON text of a ``dynamic`` column —
read here on the SDK's own objects, never on a Python list.

The constat (SDK1a's review, 20/11): a row without `TimeGenerated`, `EventId` or `CorrelationId` took
into its identity every non-numeric text (`_row_identity`). The SDK (`azure-monitor-query`) hands a
``dynamic`` column (`make_set`, `make_list`, `pack`…) on as its JSON text (SLF1b, measured on
Imladris): that text entered the identity, and a `make_set(User) by SourceIP` that grew made a new
card at each user more. The tests passed Python lists, which never entered it.

Here a query runs as written over forged lines (tests/unit/kql_subset.py), its rows become the body
the Log Analytics API sends — each column typed, a ``dynamic`` one as its JSON text —, parsed by the
pinned SDK's own ``LogsQueryResult``, read by the real `AzureMonitorDetector.run_query`, then the real
RulePoller (as tests/unit/test_own_channel_sdk.py, SLF1b; tests/unit/sdk_logs.py, SDK1a, was not on
main when this was written). Each shipped rule's representative row has its identity frozen, before
RID1 (the function as it was, copied here) and after. Mutants M6910–M6919 (scripts/mutants/RID1.py).
No Azure, no model; every identifier is made up (repository public).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import yaml

from glorfindel import own_channel
from glorfindel.detection_rules import (
    DetectionRule, RulePoller, _row_identity, shipped_rule_names, shipped_rules_path,
)
from glorfindel.providers.azure.monitor import AzureMonitorDetector

from . import kql_subset
from . import test_auditd as aud
from . import test_own_channel as oc
from . import test_vm3_pairs as vm3

SHIPPED = {r["name"]: r for r in yaml.safe_load(shipped_rules_path().read_text())["rules"]}
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
SUB = "00000000-0000-0000-0000-0000000000cc"
RG = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers"
VM = f"{RG}/Microsoft.Compute/virtualMachines/vm-example-01"
PEER = "198.51.100.7"
OUTSIDER = "someone@example.org"
OUTSIDER_OID = "b3333333-c333-d333-e333-f33333333333"
OID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"


# ── the SDK's objects ────────────────────────────────────────────────────────────────────────────

def _type(values) -> str:
    """A column's type, as Log Analytics gives it, from the first value that is not None."""
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "long"
        if isinstance(v, float):
            return "real"
        if isinstance(v, datetime):
            return "datetime"
        if isinstance(v, (list, dict)):
            return "dynamic"
        return "string"
    return "string"


def _wire(value, ctype: str):
    """A value as the API's body carries it: a `dynamic` one as its JSON text (measured, 20/11, SLF1b),
    a date in ISO 8601, UTC."""
    if value is None:
        return None
    if ctype == "dynamic" and not isinstance(value, str):
        return json.dumps(value)
    if ctype == "datetime" and isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value


def body_of(rows: list[dict], types: dict | None = None) -> dict:
    """The body of the API's reply for `rows`: one table, its columns typed, its values on the wire."""
    types = types or {}
    columns = list(dict.fromkeys(c for r in rows for c in r))
    typed = {c: types.get(c) or _type(r.get(c) for r in rows) for c in columns}
    return {"tables": [{"name": "PrimaryResult",
                        "columns": [{"name": c, "type": typed[c]} for c in columns],
                        "rows": [[_wire(r.get(c), typed[c]) for c in columns] for r in rows]}]}


class _Client:
    """Log Analytics through the SDK's objects: `reply(query)` the rows, the body they make parsed by
    `LogsQueryResult._from_generated` — the parse of the body the API sends."""

    def __init__(self, reply, types=None):
        self.reply, self.types = reply, types

    def query_workspace(self, workspace_id, query, timespan=None):
        from azure.monitor.query._models import LogsQueryResult
        body = body_of(self.reply(query), self.types)
        return LogsQueryResult._from_generated(json.loads(json.dumps(body)))


def _detector(reply, types=None) -> AzureMonitorDetector:
    det = AzureMonitorDetector("ws-test")
    det._logs_client = lambda: _Client(reply, types)
    return det


def through_sdk(rows: list[dict], types: dict | None = None) -> list[dict]:
    """`rows` as the real `run_query` hands them on, read from the SDK's objects."""
    return _detector(lambda _q: rows, types).run_query("PrimaryResult")


def _kql(lines, now=NOW):
    return lambda query: kql_subset.run(query, lines, now=now)


# ── the identity before RID1, as it was (glorfindel/detection_rules.py, origin/main 8e5cb1d8) ──

def _looks_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def identity_before_rid1(row: dict) -> str:
    """`_row_identity` before RID1, to the letter: the "before" every shipped rule is compared with."""
    if row.get("EntraOperation") and row.get("EventId"):
        return "entra:" + str(row["EventId"]).lower()
    if row.get("OperationNameValue") and row.get("CorrelationId"):
        return "op:" + "|".join(str(row.get(k) or "").lower()
                                for k in ("CorrelationId", "OperationNameValue", "_ResourceId"))
    ts = row.get("TimeGenerated")
    if ts:
        msg = row.get("SyslogMessage")
        if isinstance(msg, str):
            return f"ts:{ts}|{hashlib.sha256(msg.encode('utf-8', 'replace')).hexdigest()[:16]}"
        event = row.get("AuditEvent")
        if isinstance(event, str) and event:
            return f"ts:{ts}|ev:{event}"
        return f"ts:{ts}"
    keys = sorted(
        f"{k}={v}" for k, v in row.items()
        if isinstance(v, str) and v and not _looks_numeric(v)
    )
    return "row:" + "|".join(keys)


# ── Fini quand: an aggregated row that grows keeps its identity ─────────────────────────────────

# A rule of the client's layer, or one the model wrote (detection_authoring): the users an address
# tried, gathered by `make_set` — the form the shipped rules never had.
GATHERED = """Syslog
| where TimeGenerated > ago(15m)
| where ProcessName == "sshd" and SyslogMessage has "Failed password"
| extend SourceIP = extract(@"from (\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}) port", 1, SyslogMessage),
         User = extract(@"for (?:invalid user )?(\\S+) from", 1, SyslogMessage)
| summarize Attempts = count(), Users = make_set(User, 20) by SourceIP, Computer, _ResourceId
| where Attempts >= 3
"""


def _failure(user: str, minutes_ago: float, ip: str = PEER) -> dict:
    return {"Type": "Syslog", "TimeGenerated": NOW - timedelta(minutes=minutes_ago), "Facility": "auth",
            "ProcessName": "sshd", "SyslogMessage": f"Failed password for {user} from {ip} port 4{int(minutes_ago * 10):04d} ssh2",
            "Computer": "vm-example-01", "_ResourceId": VM}


def _tries(*users, ip: str = PEER, start: float = 9.0) -> list[dict]:
    return [_failure(u, start - i * 0.5, ip) for i, u in enumerate(users)]


def test_the_sdk_hands_the_gathered_users_on_as_text():
    """The client's row out of the SDK's objects: `Users` a `str`, its JSON the set the query made —
    the form the tests on lists never passed."""
    [row] = _detector(_kql(_tries("root", "admin", "oracle"))).run_query(GATHERED)
    assert isinstance(row["Users"], str) and json.loads(row["Users"]) == ["root", "admin", "oracle"]
    assert row["Attempts"] == 3 and row["SourceIP"] == PEER


def test_an_aggregated_row_whose_set_grows_keeps_its_identity():
    """Fini quand (#1002): the same address on the same VM, one user more in its set — one identity;
    before RID1, two."""
    [first] = _detector(_kql(_tries("root", "admin", "oracle"))).run_query(GATHERED)
    [grown] = _detector(_kql(_tries("root", "admin", "oracle", "postgres"))).run_query(GATHERED)
    assert first["Users"] != grown["Users"]
    assert _row_identity(first) == _row_identity(grown) == (
        f"row:Computer=vm-example-01|SourceIP={PEER}|_ResourceId={VM}")
    assert identity_before_rid1(first) != identity_before_rid1(grown)


def test_the_identity_is_the_same_whether_the_set_is_a_list_or_its_json_text():
    """The row a test on lists wrote, and the row the SDK hands on: one identity."""
    row = {"SourceIP": PEER, "Computer": "vm-example-01", "_ResourceId": VM, "Attempts": 3}
    for gathered in (["root", "admin"], json.dumps(["root", "admin"]), {"root": 2}, json.dumps({"root": 2}),
                     "[]", " [\"root\"] "):
        assert _row_identity({**row, "Users": gathered}) == _row_identity(row), gathered


class _Registry:
    def __init__(self, *rids):
        self.assets = [SimpleNamespace(name=r.rsplit("/", 1)[-1], resource_id=r) for r in rids]

    def for_backend(self, _name):
        return self.assets

    def all(self):
        return self.assets


def _gathered_rule() -> DetectionRule:
    return DetectionRule(name="client-ssh-users", source="azure_monitor", workspace_id="ws", query=GATHERED,
                         ttp="T1110.001", resource_id="", interval_s=30, auto_apply=True,
                         monitoring_backend_name="law")


def _passes(*passes: list[dict]):
    """The client's rule polled once per `passes` (its lines then), each read through the SDK, by one
    poller: the signals sent, and the poller."""
    rule = _gathered_rule()
    sent: list = []
    p = RulePoller([rule], sent.append)
    p._status = {}
    p._registry = _Registry(VM)
    for lines in passes:
        det = _detector(_kql(lines))
        p._detector = lambda _r, det=det: det
        p.poll_once(rule)
    p.stop()
    return sent, p


def test_a_grown_set_makes_no_new_card():
    """Fini quand (#1002): one card for the address, its set grown at the next pass — no second card."""
    first = _tries("root", "admin", "oracle")
    sent, p = _passes(first, first + _tries("postgres", start=7.0))
    assert len(sent) == 1
    assert json.loads(sent[0]["raw_signal"]["first_result_row"]["Users"]) == ["root", "admin", "oracle"]
    dispatched = p._status["client-ssh-users"]["dispatched"]
    assert [list(v) for v in dispatched.values()] == [[f"row:Computer=vm-example-01|SourceIP={PEER}|_ResourceId={VM}"]]


def test_another_address_still_makes_its_card():
    """The grouping keys stay: another address on the same VM is another detection, its own card."""
    first = _tries("root", "admin", "oracle")
    sent, _ = _passes(first, first + _tries("root", "admin", "oracle", ip="203.0.113.9", start=7.0))
    assert len(sent) == 2
    assert {s["raw_signal"]["first_result_row"]["SourceIP"] for s in sent} == {PEER, "203.0.113.9"}


def test_a_plain_text_that_changes_is_still_a_new_identity():
    """A text that is no JSON (an account, a name, a text that only looks like one) stays in the
    identity: when it changes, the identity changes."""
    row = {"SourceIP": PEER, "Computer": "vm-example-01", "Attempts": 3}
    seen = {_row_identity({**row, "Account": a}) for a in
            ("alice", "bob", "[alice", "{bob", "[alice]x", "null", "true", '"carol"', "Infinity x")}
    assert len(seen) == 9
    for a in ("alice", "[alice", "null", '"carol"'):
        assert f"Account={a}" in _row_identity({**row, "Account": a})
    # through the SDK: a string column whose text changes, a new identity
    a, b = through_sdk([{**row, "Account": "alice"}]), through_sdk([{**row, "Account": "bob"}])
    assert _row_identity(a[0]) != _row_identity(b[0])


def test_a_text_past_the_bound_or_unreadable_stays_and_never_raises():
    """The reading is `own_channel.json_of`'s (SLF1b): bounded by WRITERS_MAX, never raising. A JSON
    array past the bound is not read — it stays in the identity, as before RID1; a text nested too deep
    for the decoder, or broken, stays too, and nothing raises."""
    row = {"SourceIP": PEER, "Computer": "vm-example-01"}
    at_bound = json.dumps(["x" * (own_channel.WRITERS_MAX - 4)])
    assert len(at_bound) == own_channel.WRITERS_MAX
    assert _row_identity({**row, "Users": at_bound}) == _row_identity(row)
    past = json.dumps(["x" * (own_channel.WRITERS_MAX - 3)])
    assert len(past) == own_channel.WRITERS_MAX + 1
    assert _row_identity({**row, "Users": past}) == _row_identity(row) + f"|Users={past}"
    deep = "[" * 32_000 + "]" * 32_000           # under the bound, deeper than the decoder goes
    broken = '["root", "admin"'
    for text in (deep, broken, "\udcff", "[1, 2, ]"):
        assert _row_identity({**row, "Users": text}).endswith(f"|Users={text}"), text[:20]


def test_a_row_with_its_instant_is_untouched():
    """A row with `TimeGenerated` is that event (unchanged): its JSON columns never were in it, and a
    row of an identity or of the control plane neither."""
    t = NOW - timedelta(minutes=2)
    rows = [
        {"TimeGenerated": t, "Computer": "vm-example-01", "SyslogMessage": "x", "Paths": ["/var/log/a"]},
        {"TimeGenerated": t, "Computer": "vm-example-01", "AuditEvent": "1.2:3", "Execve": ["a0=sh"]},
        {"TimeGenerated": t, "Computer": "vm-example-01", "Writer": ["/usr/bin/dash"]},
        {"EntraOperation": "Add service principal credentials", "EventId": "C-1|T-1", "Added": ["k"]},
        {"OperationNameValue": "MICROSOFT.COMPUTE/SNAPSHOTS/WRITE", "CorrelationId": "c-1", "_ResourceId": VM},
    ]
    for row in rows:
        [sdk] = through_sdk([row])
        assert _row_identity(sdk) == identity_before_rid1(sdk), row
    [sdk] = through_sdk([rows[0]])
    assert isinstance(sdk["Paths"], str) and isinstance(sdk["TimeGenerated"], datetime)
    assert _row_identity(sdk) == identity_before_rid1(sdk) == (
        f"ts:{sdk['TimeGenerated']}|{hashlib.sha256(b'x').hexdigest()[:16]}")


# ── Fini quand: the shipped rules' identities are unchanged ─────────────────────────────────────

def _activity(op, rid, status="Success", minutes_ago=5.0, corr="c-1", caller=OUTSIDER, oid=OUTSIDER_OID,
              app=""):
    """One line of AzureActivity, as the table writes it (as tests/unit/test_activity_operation_read.py)."""
    return {"Type": "AzureActivity", "TimeGenerated": NOW - timedelta(minutes=minutes_ago),
            "OperationNameValue": op, "ActivityStatusValue": status, "Caller": caller,
            "CallerIpAddress": "203.0.113.7", "Claims": json.dumps({"appid": app, OID_CLAIM: oid}),
            "_ResourceId": rid, "ResourceGroup": "rg-example", "CorrelationId": corr,
            "SubscriptionId": SUB}


def _operation(op, rid, **kw):
    """An operation: its Start, then its Success a minute later."""
    return [_activity(op, rid, "Start", 6.0, **kw), _activity(op, rid, "Success", 5.0, **kw)]


def _syslog(message, process, facility, minutes_ago=2.0, **extra):
    return {"Type": "Syslog", "TimeGenerated": NOW - timedelta(minutes=minutes_ago), "Facility": facility,
            "ProcessName": process, "SyslogMessage": message, "Computer": "vm-example-01", "_ResourceId": VM,
            "SeverityLevel": "info", **extra}


RUN_OP = "MICROSOFT.COMPUTE/VIRTUALMACHINES/RUNCOMMAND/ACTION"
BASTION = f"{RG}/Microsoft.Network/bastionHosts/bastion-example"


def _lines(name: str, monkeypatch) -> list[dict]:
    """The lines a shipped rule reads, forged so it matches once."""
    if name == "data-exfiltration-blob":
        return oc._channel_writes(oid=oc.OTHER_OID) + [oc._write("db.bak", oid=oc.OTHER_OID, size=4096)]
    if name == "ssh-brute-force":
        return [_syslog(f"Failed password for root from {PEER} port {40000 + i} ssh2", "sshd", "auth")
                for i in range(10)]
    if name == "sudo-privilege-escalation":
        return [_syslog("   alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/id", "sudo",
                        "authpriv")]
    if name == "auditd-sensitive-root-command":
        monkeypatch.setattr(aud, "NOW", NOW)
        return aud.event(41, "cat", "/etc/shadow", rid=VM)
    if name == "t1136-001-local-account-creation-linux-v1":
        return [_syslog("new user: name=svc-example, UID=2001, GID=2001, home=/home/svc-example, "
                        "shell=/bin/bash, from=none", "useradd", "authpriv")]
    if name == "t1053-003-cron-crontab-replace":
        return [_syslog("(root) REPLACE (root)", "crontab", "cron")]
    if name == "t1070-002-log-tamper":
        monkeypatch.setattr(vm3, "NOW", NOW - timedelta(minutes=2))
        return vm3._tamper(4567, "/usr/bin/dash", "/var/log/eregion-t1070-disposable.log", comm="dash")
    if name == "t1059-004-shell-from-world-writable":
        monkeypatch.setattr(vm3, "NOW", NOW - timedelta(minutes=2))
        return vm3._shell_event(7777, "sh", "/tmp/eregion-t1059-art.sh")
    if name == "nsg-change-outside-glorfindel":
        return _operation("MICROSOFT.NETWORK/NETWORKSECURITYGROUPS/SECURITYRULES/WRITE",
                          f"{RG}/Microsoft.Network/networkSecurityGroups/nsg-web/securityRules/allow-web")
    if name == "role-assignment-write":
        return _operation("MICROSOFT.AUTHORIZATION/ROLEASSIGNMENTS/WRITE",
                          f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleAssignments/"
                          "00000000-0000-0000-0000-0000000000aa")
    if name == "snapshot-by-unexpected-caller":
        return _operation("MICROSOFT.COMPUTE/SNAPSHOTS/WRITE", f"{RG}/Microsoft.Compute/snapshots/snap-example")
    if name == "restorepoint-by-unexpected-caller":
        return _operation("MICROSOFT.COMPUTE/RESTOREPOINTCOLLECTIONS/RESTOREPOINTS/RETRIEVESASURIS/ACTION",
                          f"{RG}/Microsoft.Compute/restorePointCollections/rpc-vm1/restorePoints/rp-1")
    if name in ("run-command-by-glorfindel-outside-isolation", "run-command-by-external-caller"):
        return _operation(RUN_OP, VM)
    if name == "bastion-shareable-link-created":
        return _operation("MICROSOFT.NETWORK/BASTIONHOSTS/CREATESHAREABLELINKS/ACTION", BASTION)
    if name == "entra-sp-unusual-signin":
        from . import test_canary_signin as cs
        monkeypatch.setattr(cs, "NOW", NOW)
        return cs._run()
    raise KeyError(name)


# The rules the KQL subset cannot run (`prev()`, `mv-apply`): their row written as the query projects
# it, each column as the API types it.
_WRITTEN = {
    "ransomware-disk-write": [{"Computer": "vm-example-01", "_ResourceId": VM, "MaxWrite": 61234567.5}],
    "entra-credential-added": [{
        "TimeGenerated": NOW - timedelta(minutes=3), "EntraKind": "credential",
        "EntraOperation": "Update application – Certificates and secrets management",
        "EventId": "c-entra-1|00000000-0000-0000-0000-0000000000e1", "Result": "success",
        "ActorName": "admin@example.org", "ActorId": "00000000-0000-0000-0000-0000000000e2", "ActorAppId": "",
        "ActorIp": "203.0.113.8", "TargetName": "app-example", "TargetId": "00000000-0000-0000-0000-0000000000e1",
        "TargetType": "Application", "CredentialAdded": json.dumps([{"KeyIdentifier": "k-1"}]),
        "CorrelationId": "c-entra-1"}],
    "entra-app-consent": [{
        "TimeGenerated": NOW - timedelta(minutes=3), "EntraKind": "consent",
        "EntraOperation": "Consent to application", "EventId": "c-entra-2|00000000-0000-0000-0000-0000000000e3",
        "Result": "success", "ActorName": "user@example.org", "ActorId": "00000000-0000-0000-0000-0000000000e4",
        "ActorAppId": "", "ActorIp": "203.0.113.8", "TargetName": "app-example",
        "TargetId": "00000000-0000-0000-0000-0000000000e3", "TargetType": "ServicePrincipal",
        "Permissions": "Mail.Read offline_access", "AdminConsent": False, "AppOnly": "False",
        "ClientId": "00000000-0000-0000-0000-0000000000e5", "CorrelationId": "c-entra-2"}],
    "entra-privileged-role-assigned": [{
        "TimeGenerated": NOW - timedelta(minutes=3), "EntraKind": "role",
        "EntraOperation": "Add member to role", "EventId": "c-entra-3|00000000-0000-0000-0000-0000000000e6",
        "Result": "success", "RoleName": "Global Administrator", "ActorName": "admin@example.org",
        "ActorId": "00000000-0000-0000-0000-0000000000e2", "ActorAppId": "", "ActorIp": "203.0.113.8",
        "TargetName": "user@example.org", "TargetId": "00000000-0000-0000-0000-0000000000e6",
        "TargetType": "User", "CorrelationId": "c-entra-3"}],
}
# The rules whose row is written as its query projects it, though the subset could run it: the one
# that reads Glorfindel's own identity, set at load (tests/unit/test_run_command_callers.py holds it).
_PROJECTED = {
    "run-command-by-glorfindel-outside-isolation": [{
        "TimeGenerated": NOW - timedelta(minutes=5), "Started": NOW - timedelta(minutes=6),
        "OperationNameValue": RUN_OP, "ActivityStatusValue": "Success", "Callers": 1,
        "Caller": "c4444444-d444-e444-f444-a44444444444", "CallerIpAddress": "203.0.113.7",
        "CallerAppId": "c3333333-d333-e333-f333-a33333333333", "CallerObjectId": "c4444444-d444-e444-f444-a44444444444",
        "_ResourceId": VM, "ResourceGroup": "rg-example", "CorrelationId": "c-1", "WatchedCaller": "glorfindel"}],
}

# Each shipped rule's representative row, its identity as the poller computes it (frozen by RID1,
# 20/11): before RID1 and after, the same. `ts:`, `op:` and `entra:` never read the row's other
# columns; the three aggregated rows (`row:`) carry no JSON text — BlobWriters, the one dynamic column
# of an aggregated shipped row, is taken off before any identity (`own_channel.settle` / `strip`).
_TS = f"ts:{NOW - timedelta(minutes=2)}"
FROZEN = {
    "ransomware-disk-write": f"row:Computer=vm-example-01|_ResourceId={VM}",
    "data-exfiltration-blob": f"row:AccountName={oc.ACCOUNT}|CallerIpAddress={oc.WATCH_IP}",
    "ssh-brute-force": f"row:Computer=vm-example-01|SourceIP={PEER}|_ResourceId={VM}",
    "sudo-privilege-escalation": f"{_TS}|"
    + hashlib.sha256(b"   alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/usr/bin/id").hexdigest()[:16],
    "auditd-sensitive-root-command": None,      # filled below: its instant and its event
    "t1136-001-local-account-creation-linux-v1": f"{_TS}|" + hashlib.sha256(
        b"new user: name=svc-example, UID=2001, GID=2001, home=/home/svc-example, shell=/bin/bash, "
        b"from=none").hexdigest()[:16],
    "t1053-003-cron-crontab-replace": f"{_TS}|" + hashlib.sha256(b"(root) REPLACE (root)").hexdigest()[:16],
    "t1070-002-log-tamper": f"{_TS}|ev:1730800000.4567:4567",
    "t1059-004-shell-from-world-writable": f"{_TS}|ev:1730800000.7777:7777",
    "nsg-change-outside-glorfindel": "op:c-1|microsoft.network/networksecuritygroups/securityrules/write|"
    + f"{RG}/Microsoft.Network/networkSecurityGroups/nsg-web/securityRules/allow-web".lower(),
    "role-assignment-write": "op:c-1|microsoft.authorization/roleassignments/write|"
    + f"/subscriptions/{SUB}/providers/Microsoft.Authorization/roleAssignments/00000000-0000-0000-0000-0000000000aa".lower(),
    "snapshot-by-unexpected-caller": "op:c-1|microsoft.compute/snapshots/write|"
    + f"{RG}/Microsoft.Compute/snapshots/snap-example".lower(),
    "restorepoint-by-unexpected-caller": "op:c-1|"
    + "microsoft.compute/restorepointcollections/restorepoints/retrievesasuris/action|"
    + f"{RG}/Microsoft.Compute/restorePointCollections/rpc-vm1/restorePoints/rp-1".lower(),
    "run-command-by-glorfindel-outside-isolation": f"op:c-1|{RUN_OP.lower()}|{VM.lower()}",
    "run-command-by-external-caller": f"op:c-1|{RUN_OP.lower()}|{VM.lower()}",
    "bastion-shareable-link-created": "op:c-1|microsoft.network/bastionhosts/createshareablelinks/action|"
    + BASTION.lower(),
    "entra-credential-added": "entra:c-entra-1|00000000-0000-0000-0000-0000000000e1",
    "entra-app-consent": "entra:c-entra-2|00000000-0000-0000-0000-0000000000e3",
    "entra-privileged-role-assigned": "entra:c-entra-3|00000000-0000-0000-0000-0000000000e6",
    "entra-sp-unusual-signin": None,            # filled below: its principal and the new address
}


def _representative(name: str, monkeypatch) -> list[dict]:
    """A shipped rule's rows as the poller reads them: through the SDK's objects, BlobWriters taken off
    as `poll_once` does before the routing."""
    if name in _WRITTEN or name in _PROJECTED:
        rows = through_sdk((_WRITTEN | _PROJECTED)[name])
    else:
        query = SHIPPED[name]["query"]
        now = oc.NOW if name == "data-exfiltration-blob" else NOW
        rows = _detector(_kql(_lines(name, monkeypatch), now)).run_query(query)
    return own_channel.strip(rows)


def test_every_shipped_rule_has_its_identity_frozen():
    """A shipped rule added later is frozen here too, or this fails."""
    assert set(FROZEN) == set(shipped_rule_names()) == set(SHIPPED)


@pytest.mark.parametrize("name", sorted(SHIPPED))
def test_a_shipped_rule_s_identity_is_unchanged(name, monkeypatch):
    """Fini quand (#1002): each shipped rule's representative row, read through the SDK, has the same
    identity before RID1 and after — and the one frozen here."""
    rows = _representative(name, monkeypatch)
    assert len(rows) == 1, (name, rows)
    [row] = rows
    after, before = _row_identity(row), identity_before_rid1(row)
    assert after == before, name
    frozen = FROZEN[name]
    if name == "auditd-sensitive-root-command":
        frozen = f"ts:{row['TimeGenerated']}|ev:{row['AuditEvent']}"
        assert row["AuditEvent"] and isinstance(row["Syscall"], str)       # its sets as text, not in it
    if name == "entra-sp-unusual-signin":
        frozen = f"entra:{row['EventId'].lower()}"
        assert row["EventId"].endswith("|192.0.2.77")
    assert after == frozen, name


def test_the_raw_exfiltration_row_no_longer_depends_on_its_writers():
    """BlobWriters never reaches an identity (taken off before the routing); read raw, it would have
    made one per writer set before RID1 — after, the row's identity is its address and account alone."""
    lines = oc._channel_writes(oid=oc.OTHER_OID) + [oc._write("db.bak", oid=oc.OTHER_OID, size=4096)]
    [raw] = _detector(_kql(lines, oc.NOW)).run_query(SHIPPED["data-exfiltration-blob"]["query"])
    assert isinstance(raw[own_channel.WRITERS], str)
    assert _row_identity(raw) == FROZEN["data-exfiltration-blob"]
    assert identity_before_rid1(raw) != _row_identity(raw)
