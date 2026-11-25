"""SLF1 (#929): the watch's own return channel no longer makes the exfiltration rule fire, and a
card on a detection attributed to no VM no longer names one.

On Imladris, about three days running (reported 19/11): the watch publishes its return channel in a
blob container (eregion_core/watch_channel.py, ``EREGION_WATCH_CHANNEL``) — ``heartbeat.json`` and
``detections/<run_id>/<signal_id>.json`` —, and those writes, PutBlob from the watch's private
address, made ``data-exfiltration-blob`` fire about every 20 minutes (a hundred recurrences, a
confidence wandering from 40 to 72 %). Unattributed (no watched VM holds that address), each card
named a VM of the bench as its « Ressource ».

Rows forged as Azure Storage writes them in StorageBlobLogs (``ObjectKey`` ``/<account>/<container>/
<blob>``, ``RequesterObjectId`` the writer's object id — the column names of the table's reference,
to be measured on the bench: docs/glorfindel.md, « La voie de retour de la watch »), the shipped
query run as written (tests/unit/kql_subset.py), then the real RulePoller, the real graph, the real
store, and what the console, Discord and the CLI show. No real id: a zero GUID, a placeholder
account, the bench's VM names already in the repository. Mutants M6391–M6405 (scripts/mutants/SLF1.py).
"""
from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from glorfindel import escalations, own_channel
from glorfindel.detection_rules import RulePoller, load_config

from . import kql_subset

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "glorfindel/rules/azure/detection_rules.yaml"
JS = ROOT / "eregion_console/static/glorfindel.js"

SUB = "/subscriptions/00000000-0000-0000-0000-000000000000"
PROV = f"{SUB}/resourceGroups/rg-celebrimbor/providers"
BREE = f"{PROV}/Microsoft.Compute/virtualMachines/vm-celebrimbor-bree"
GONDOLIN = f"{PROV}/Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
# Placeholders, never real ids: the watch's identity, another one, the channel's account.
WATCH_OID = "00000000-0000-0000-0000-0000000000a1"
OTHER_OID = "00000000-0000-0000-0000-0000000000b2"
ACCOUNT = "steregionwatchtest"
CONTAINER = "watch"
URL = f"https://{ACCOUNT}.blob.core.windows.net/{CONTAINER}"
WATCH_IP = "10.0.9.4"           # the watch's host: no VM the rules watch
GONDOLIN_IP = "10.0.1.5"
NOW = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
CHANNEL = own_channel.Channel(ACCOUNT, CONTAINER, WATCH_OID)

# The rule's query before SLF1, as it ran on Imladris: what the model read is held to it. The shipped
# one also keeps the written writes only (SEC-I, `toint(StatusCode) between (200 .. 299)`): the writes
# forged here are written ones (201), where the two agree — a refused write, which the query of before
# counted, is tested in test_enquiry_memory.py.
BEFORE_SLF1 = """StorageBlobLogs
| where OperationName in ("PutBlob", "PutBlock", "PutBlockList")
| where TimeGenerated > ago(5m)
| where CallerIpAddress matches regex @"^(10\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|192\\.168\\.)"
| extend CallerIpAddress = tostring(split(CallerIpAddress, ":")[0])
| summarize PutBlobCount = count(), EgressBytes = sum(ResponseBodySize)
      by CallerIpAddress, AccountName
| where PutBlobCount >= 1
| project CallerIpAddress, AccountName, PutBlobCount, EgressBytes
"""


def _write(blob, oid=WATCH_OID, ip=WATCH_IP, account=ACCOUNT, container=CONTAINER, size=0, op="PutBlob",
           minutes=1):
    """A write as StorageBlobLogs holds it: the caller's address with its port, the object's key."""
    return {"Type": "StorageBlobLogs", "TimeGenerated": NOW - timedelta(minutes=minutes),
            "OperationName": op, "CallerIpAddress": f"{ip}:50374", "AccountName": account,
            "ObjectKey": f"/{account}/{container}/{blob}", "RequesterObjectId": oid,
            "ResponseBodySize": size, "StatusCode": "201"}     # a text, as measured (SEC-I, SI2)


def _channel_writes(oid=WATCH_OID, **kw):
    """What the watch writes in a pass: its heartbeat, and a detection for a run."""
    return [_write("heartbeat.json", oid=oid, **kw),
            _write("detections/r-20261119-0942/rule-ssh-brute-force-1a2b3c4d.json", oid=oid, **kw)]


def _cfg():
    return SimpleNamespace(monitoring_backends=[SimpleNamespace(
        name="law-bench", type="azure_monitor", workspace_id="ws-test", endpoint="")])


def _rule(query=None):
    rule = next(r for r in load_config(SHIPPED, glorfindel_cfg=_cfg(), client_layer=False).rules
                if r.name == "data-exfiltration-blob")
    if query is not None:
        rule.query = query
    return rule


class _Workspace:
    """Log Analytics, for the rule: its query run as written over the forged writes."""

    def __init__(self, rows):
        self.rows = rows

    def run_query(self, query, timespan=None):
        return kql_subset.run(query, self.rows, now=NOW)


class _Registry:
    def __init__(self, *rids):
        self.assets = [SimpleNamespace(name=r.rsplit("/", 1)[-1], resource_id=r) for r in rids]

    def for_backend(self, _name):
        return self.assets

    def all(self):
        return self.assets


def _poll(rows, channel=CHANNEL, query=None, owners=None):
    """One pass of the shipped rule over `rows`: (signals sent, the rule's status, the poller)."""
    rule = _rule(query)
    sent: list = []
    p = RulePoller([rule], sent.append, ip_owners=owners or (lambda: {GONDOLIN_IP: GONDOLIN}),
                   channel=lambda: channel)
    p._status = {}
    p._detector = lambda _rule: _Workspace(rows)
    p._registry = _Registry(BREE, GONDOLIN)
    p.poll_once(rule)
    p.stop()
    return sent, p._status.get(rule.name, {}), p


# ── the query: who wrote what, kept for the watch to read ─────────────────────────────────────────

def test_the_query_keeps_who_wrote_in_which_container_and_routes_as_before():
    """Each row says, per writer and container, its writes, its bytes and how many are objects a
    return channel holds; the row is still routed by its caller's address alone (SEC-A4)."""
    from eregion_core import rule_routing
    rule = _rule()
    assert rule_routing.explain(rule.query) == (frozenset({"CallerIpAddress"}), "")
    [row] = kql_subset.run(rule.query, _channel_writes() + [_write("db.bak", container="backup", size=10)], now=NOW)
    assert [k for k in row] == ["CallerIpAddress", "AccountName", "PutBlobCount", "EgressBytes",
                                own_channel.WRITERS]
    assert row["CallerIpAddress"] == WATCH_IP and row["PutBlobCount"] == 3
    entries = {e["container"]: e for e in row[own_channel.WRITERS]}
    assert entries[CONTAINER] == {"container": CONTAINER, "writer": WATCH_OID, "writes": 2, "bytes": 0, "known": 2}
    assert entries["backup"]["known"] == 0


# ── the return channel, set aside — and said ──────────────────────────────────────────────────────

def test_the_watch_s_own_writes_make_no_card_and_are_said(caplog):
    """Fini quand (#929): the heartbeat and the detections the watch writes in its channel, by its
    identity, make no card; how many, and why, are in the rule's status and the watch's log."""
    caplog.set_level(logging.INFO, logger="glorfindel.detection_rules")
    sent, st, p = _poll(_channel_writes() + [_write("heartbeat.json", minutes=2)])
    assert sent == []
    assert st["own_channel"]["writes"] == 3 and st["own_channel"]["rows"] == 1
    assert st["own_channel"]["reason"] == own_channel.REASON and st["own_channel"]["container"] == CONTAINER
    said = [r.getMessage() for r in caplog.records if "set aside" in r.getMessage()]
    assert said and "3 write(s)" in said[0] and "return channel" in said[0]
    snap = next(s for s in p.status_snapshot() if s["name"] == "data-exfiltration-blob")
    assert snap["own_channel_count"] == 3 and snap["own_channel_rows"] == 1
    # A second pass counts on (the status is cumulative, never reset by a quiet pass).
    rule = _rule()
    p._detector = lambda _rule: _Workspace(_channel_writes())
    p.poll_once(rule)
    assert p._status[rule.name]["own_channel"]["writes"] == 5


def test_another_write_from_the_watch_s_address_stays_a_card():
    """Fini quand: the same address, another container of the same account — a card, its counts
    the other write's only (the watch's own taken off)."""
    sent, st, _ = _poll(_channel_writes() + [_write("db.bak", container="backup", size=4096)])
    assert len(sent) == 1
    row = sent[0]["raw_signal"]["first_result_row"]
    assert row == {"CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 1, "EgressBytes": 4096}
    assert st["own_channel"]["writes"] == 2 and st["own_channel"]["rows"] == 0
    # Even of a channel's shape, by the watch's identity: another container is no channel of its own.
    sent, _, _ = _poll(_channel_writes() + _channel_writes(container="watch-old"))
    assert len(sent) == 1 and sent[0]["raw_signal"]["first_result_row"]["PutBlobCount"] == 2


def test_a_write_in_the_channel_by_another_identity_stays_a_card():
    """Fini quand: another identity writing in the channel's container — anomalous, a card; the
    watch's own writes beside it taken off."""
    sent, _, _ = _poll(_channel_writes() + [_write("heartbeat.json", oid=OTHER_OID)])
    assert len(sent) == 1 and sent[0]["raw_signal"]["first_result_row"]["PutBlobCount"] == 1
    # Another identity alone: every one of its writes counted.
    sent, st, _ = _poll(_channel_writes(oid=OTHER_OID))
    assert len(sent) == 1 and sent[0]["raw_signal"]["first_result_row"]["PutBlobCount"] == 2
    assert "own_channel" not in st
    # A write without an OAuth identity (a key, a SAS: no RequesterObjectId) is no watch's either.
    sent, _, _ = _poll(_channel_writes(oid=None))
    assert len(sent) == 1


def test_without_a_channel_configured_nothing_is_set_aside():
    """Fini quand: no return channel configured — every write stays, the row as before SLF1."""
    sent, st, _ = _poll(_channel_writes(), channel=None)
    assert len(sent) == 1
    assert sent[0]["raw_signal"]["first_result_row"] == {
        "CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 2, "EgressBytes": 0}
    assert "own_channel" not in st


def test_the_watch_s_identity_not_read_sets_nothing_aside_and_says_so(caplog):
    """The channel configured, the watch's identity not read (no token): nothing set aside — a card —,
    and said, in the status and once in the log."""
    caplog.set_level(logging.WARNING, logger="glorfindel.detection_rules")
    sent, st, p = _poll(_channel_writes(), channel=own_channel.Channel(ACCOUNT, CONTAINER, ""))
    assert len(sent) == 1
    assert st["own_channel"]["unread"] and st["own_channel"]["writes"] == 0
    assert any("identity could not be read" in r.getMessage() for r in caplog.records)
    snap = next(s for s in p.status_snapshot() if s["name"] == "data-exfiltration-blob")
    assert snap["own_channel_unread"] and snap["own_channel_count"] == 0
    # An unknown identity is no wildcard: writes without one (a key, a SAS) stay a card too.
    sent, st, _ = _poll(_channel_writes(oid=None), channel=own_channel.Channel(ACCOUNT, CONTAINER, ""))
    assert len(sent) == 1 and st["own_channel"]["writes"] == 0


def test_an_object_the_channel_does_not_hold_stays_a_card():
    """The watch's identity writing in its container an object a return channel never holds: a card
    — the entry is set aside only when every one of its writes is a heartbeat or a detection."""
    for blob in ("payload.bin", "detections/r1/s1.json/extra.bin", "heartbeat.json.bak", "x/heartbeat.json"):
        sent, _, _ = _poll(_channel_writes() + [_write(blob)])
        assert len(sent) == 1, blob
        assert sent[0]["raw_signal"]["first_result_row"]["PutBlobCount"] == 3, blob


def test_another_account_with_a_container_of_that_name_stays_a_card():
    """The container's name on another account (an attacker's, say): a card."""
    sent, _, _ = _poll(_channel_writes(account="stattacker"))
    assert len(sent) == 1 and sent[0]["raw_signal"]["first_result_row"]["AccountName"] == "stattacker"


def test_a_vm_s_exfiltration_is_still_routed_and_held_to_its_vm():
    """A watched VM writing with its own identity: routed to it, as before (the witness)."""
    sent, _, _ = _poll(_channel_writes() + [_write("loot.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout",
                                                   container="drop", size=0)])
    assert [s["resource_id"] for s in sent] == [GONDOLIN]
    assert sent[0]["context"]["attribution"] == "asset"


def test_a_fault_in_the_setting_aside_takes_the_column_off_and_says_it(monkeypatch):
    """A fault reading the channel: nothing set aside, the column off all the same, said."""
    def boom(*_a, **_k):
        raise RuntimeError("no")
    monkeypatch.setattr(own_channel, "settle", boom)
    sent, st, _ = _poll(_channel_writes())
    assert len(sent) == 1 and own_channel.WRITERS not in sent[0]["raw_signal"]["first_result_row"]
    assert "own_channel" in st["last_error"]


# ── the model reads what it read before ───────────────────────────────────────────────────────────

def _message(sig):
    from glorfindel.agent import _build_user_message
    sig = json.loads(json.dumps(sig))
    sig["signal_id"], sig["timestamp"] = "rule-data-exfiltration-blob-00000000", NOW.isoformat()
    sig["context"]["run_id"] = "watch-data-exfiltration-blob-20261119T100000Z"
    return _build_user_message(sig, [])


@pytest.mark.parametrize("channel", [None, CHANNEL])
def test_the_message_to_the_model_is_the_one_of_before_to_the_byte(channel):
    """Fini quand: a detection that is no write of the watch reaches the model as it did before SLF1
    — the same signal, the same message, to the byte (`_build_user_message` untouched). Run by the
    query of before and by the shipped one over the same writes."""
    rows = [_write("loot.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout", container="drop", size=512),
            _write("loot2.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout", container="drop", size=256),
            _write("x.bin", oid=OTHER_OID, ip="10.0.7.7", account="stout", container="other")]
    before, _, _ = _poll(rows, channel=channel, query=BEFORE_SLF1)
    after, _, _ = _poll(rows, channel=channel)
    assert len(before) == len(after) == 2
    for b, a in zip(sorted(before, key=lambda s: s["resource_id"]), sorted(after, key=lambda s: s["resource_id"])):
        assert json.dumps(a["raw_signal"]) == json.dumps(b["raw_signal"])
        assert _message(a) == _message(b)


# ── an attack_started is never answered by the watch's own writes ────────────────────────────────

def test_an_attack_started_is_not_answered_by_the_watch_s_own_writes(monkeypatch):
    """A run's T1041 resolved by the rule (`resolve_attack_started`): the watch's heartbeat, always in
    the window, was a row that names no VM — taken for the run's detection. Set aside now; the run's
    own write is the detection, its row as before."""
    from glorfindel.agent import resolve_attack_started
    from glorfindel.providers.azure.monitor import AzureMonitorDetector
    rows = _channel_writes() + [_write("loot.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout",
                                       container="drop")]

    def poll(self, query, since, timeout_s, interval_s=10.0, verbose=True, match_row=None):
        found = [r for r in kql_subset.run(query, rows, now=NOW) if match_row is None or match_row(r)]
        return (5, found[0]) if found else None
    monkeypatch.setattr(AzureMonitorDetector, "poll_alert", poll)
    monkeypatch.setattr(own_channel, "_SOURCE", lambda: CHANNEL)
    signal = {"event": "attack_started", "ttp": "T1041", "resource_id": GONDOLIN,
              "raw_signal": {"detection_source": "azure_monitor", "detection_query": _rule().query,
                             "log_analytics_workspace_id": "ws-test", "detection_timeout_s": 1}}
    out = resolve_attack_started(signal, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN})
    assert out["event"] == "detection"
    assert out["raw_signal"]["detected_data"] == {"CallerIpAddress": GONDOLIN_IP, "AccountName": "stout",
                                                  "PutBlobCount": 1, "EgressBytes": 0}
    # The watch's writes alone: no detection for the run.
    rows[:] = _channel_writes()
    assert resolve_attack_started(signal, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN})["event"] == "detection_timeout"
    # No channel registered (a workstation's `respond`): the column off, nothing set aside.
    monkeypatch.setattr(own_channel, "_SOURCE", None)
    out = resolve_attack_started(signal, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN})
    assert out["event"] == "detection" and own_channel.WRITERS not in out["raw_signal"]["detected_data"]


# ── the identity of the watch: its own token ──────────────────────────────────────────────────────

def _jwt(claims) -> str:
    def part(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{part({'alg': 'RS256', 'typ': 'JWT'})}.{part(claims)}.c2ln"


class _Credential:
    def __init__(self, token="", error=None):
        self.token, self.error, self.asked = token, error, 0

    def get_token(self, *_scopes, **_kw):
        self.asked += 1
        if self.error:
            raise self.error
        return SimpleNamespace(token=self.token)


def test_the_watch_s_identity_is_the_oid_of_its_own_storage_token():
    from eregion_core.watch_channel import Publisher, token_object_id
    assert token_object_id(_jwt({"oid": WATCH_OID.upper(), "aud": "https://storage.azure.com"})) == WATCH_OID
    for bad in ("", "not-a-jwt", _jwt({"sub": "x"}), _jwt({"oid": "bree"}), _jwt(["oid"]),
                _jwt({"oid": WATCH_OID + "0"}), "a.!!!.b"):
        assert token_object_id(bad) == "", bad
    cred = _Credential(_jwt({"oid": WATCH_OID}))
    pub = Publisher(URL, credential=cred)
    assert pub.writer() == WATCH_OID and pub.writer() == WATCH_OID
    assert cred.asked == 1                                       # read once
    assert Publisher(URL, credential=_Credential(error=RuntimeError("imds"))).writer() == ""
    assert Publisher(URL, credential=_Credential("opaque")).writer() == ""


def test_the_channel_is_read_from_its_url_and_a_local_channel_sets_nothing_aside(tmp_path):
    from eregion_core.watch_channel import LocalVerdicts, Publisher
    assert own_channel.parse_url(URL) == (ACCOUNT, CONTAINER)
    assert own_channel.parse_url(URL + "/") == (ACCOUNT, CONTAINER)
    for bad in ("", "http://a.blob.core.windows.net/watch", f"https://{ACCOUNT}.blob.core.windows.net",
                f"{URL}/sub", f"{URL}?sv=x", "https://evil.example.org/watch",
                f"https://{ACCOUNT}.blob.core.windows.net/Watch", f"https://{ACCOUNT}.blob.core.windows.net/a"):
        assert own_channel.parse_url(bad) is None, bad
    current = own_channel.of_publisher(Publisher(URL, credential=_Credential(_jwt({"oid": WATCH_OID}))))
    assert current() == CHANNEL
    assert own_channel.of_publisher(LocalVerdicts(tmp_path)) is None
    unread = own_channel.of_publisher(Publisher(URL, credential=_Credential(error=RuntimeError("no"))))
    assert unread() == own_channel.Channel(ACCOUNT, CONTAINER, "")


def test_the_registered_channel_is_read_and_never_raises(monkeypatch):
    monkeypatch.setattr(own_channel, "_SOURCE", None)
    assert own_channel.current() is None
    own_channel.register(lambda: CHANNEL)
    try:
        assert own_channel.current() == CHANNEL
        own_channel.register(lambda: 1 / 0)
        assert own_channel.current() is None
    finally:
        own_channel.register(None)


# ── the card of a detection attributed to no VM ───────────────────────────────────────────────────

def _unattributed_signal():
    [sig] = _poll([_write("x.bin", oid=OTHER_OID, ip="10.0.7.7", account="stout", container="other")])[0]
    assert sig["context"]["attribution"] == "unattributed" and sig["resource_id"] == BREE
    return sig


def _graph_card(tmp_path, monkeypatch, sig, action="isolate_vm", confidence=0.99):
    from .test_activity_logs import _graph, _initial, _llm
    connector = MagicMock(dry_run=False)
    with patch("litellm.completion", return_value=_llm(action, confidence)):
        final = _graph(tmp_path, monkeypatch, connector).invoke(_initial(sig))
    for name in ("isolate_vm", "block_suspicious_ip", "release_isolation"):
        getattr(connector, name).assert_not_called()
    [card] = [c for c in escalations.pending() if c["signal_id"] == sig["signal_id"]]
    return final, card


@pytest.mark.parametrize("confidence,etype", [(0.99, "unattributed_signal"), (0.5, "unattributed_signal")])
def test_an_unattributed_card_says_so_and_names_its_candidates(tmp_path, monkeypatch, confidence, etype):
    """Fini quand: the card of a detection attributed to no VM says « not attributed » with its
    candidates — in the store, TO JUDGE, the CLI, Discord — never one VM as its resource. The
    attribution guard holds the isolation at 99 %, and at 50 % too since ATT1 (#936): it primes over
    the confidence gate, which held it first and made it a `low_confidence` card, approvable."""
    sig = _unattributed_signal()
    final, card = _graph_card(tmp_path, monkeypatch, sig, confidence=confidence)
    assert final["outcome"]["escalation_type"] == card["escalation_type"] == etype
    assert card["resource_id"] == BREE                                   # filed there, as before
    assert card["attribution"] == {"state": "unattributed",
                                   "candidates": ["vm-celebrimbor-bree", "vm-celebrimbor-gondolin"]}
    assert escalations.unattributed(card) == {"candidates": card["attribution"]["candidates"], "appliance": ""}
    [line] = [c for c in escalations.to_judge() if c["id"] == card["id"]]
    assert line["attribution"] == card["attribution"]
    # The CLI's card.
    from glorfindel import cli
    with patch.object(cli, "console") as out:
        cli._render_escalation(card)
    table = out.print.call_args_list[0].args[0]
    resource = [str(c) for c in table.columns[1]._cells][[str(c) for c in table.columns[0]._cells].index("Resource")]
    assert resource == "not attributed — candidates: vm-celebrimbor-bree, vm-celebrimbor-gondolin"


def test_the_discord_card_says_not_attributed_never_its_anchor():
    pytest.importorskip("discord")
    from glorfindel.bot import _target_fields
    card = {"id": "e1", "action": "isolate_vm", "escalation_type": "low_confidence", "resource_id": BREE,
            "attribution": {"state": "unattributed",
                            "candidates": ["vm-celebrimbor-bree", "vm-celebrimbor-gondolin"]}}
    [(label, value, inline)] = _target_fields(card)
    assert label == "Ressource" and inline is False
    assert value == "non attribuée — candidates : `vm-celebrimbor-bree`, `vm-celebrimbor-gondolin`"
    many = {**card, "attribution": {"state": "unattributed", "candidates": [f"vm{i}" for i in range(11)]}}
    assert _target_fields(many)[0][1].endswith("`vm7` et 3 autre(s)")
    # Held by the attribution guard before SLF1 (no attribution kept): not attributed, no name.
    legacy = {"id": "e2", "action": "isolate_vm", "escalation_type": "unattributed_signal", "resource_id": BREE}
    assert _target_fields(legacy) == [("Ressource", "non attribuée — la détection ne nomme aucune VM", False)]
    appliance = {**card, "attribution": {"state": "unattributed", "candidates": ["a"], "appliance": "vm-fw"}}
    assert "`vm-fw`" in _target_fields(appliance)[0][1] and "`a`" not in _target_fields(appliance)[0][1]


def test_an_attributed_card_keeps_its_resource(tmp_path, monkeypatch):
    """The witness: a detection that names its VM keeps its resource everywhere."""
    pytest.importorskip("discord")
    from glorfindel.bot import _target_fields
    sent, _, _ = _poll([_write("loot.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout", container="drop")])
    [sig] = sent
    _, card = _graph_card(tmp_path, monkeypatch, sig, confidence=0.5)
    assert card["resource_id"] == GONDOLIN and "attribution" not in card
    assert escalations.unattributed(card) is None
    assert _target_fields(card) == [("Ressource", "`vm-celebrimbor-gondolin`", True)]
    [line] = [c for c in escalations.to_judge() if c["id"] == card["id"]]
    assert line["attribution"] is None
    from glorfindel import cli
    with patch.object(cli, "console") as out:
        cli._render_escalation(card)
    table = out.print.call_args_list[0].args[0]
    assert "vm-celebrimbor-gondolin" in [str(c) for c in table.columns[1]._cells]


def test_an_unattributed_detection_never_folds_into_its_anchor_s_card():
    """A hundred re-fires on one VM's card: an unattributed detection is never counted as its anchor's."""
    kw = dict(resource_id=BREE, action="snapshot", escalation_type="low_confidence", reason="r")
    own = escalations.record(signal_id="s1", **kw)
    loose = {"state": "unattributed", "candidates": ["vm-celebrimbor-bree"]}
    other = escalations.record(signal_id="s2", attribution=loose, **kw)
    again = escalations.record(signal_id="s3", attribution=loose, **kw)
    assert own != other == again
    cards = {c["id"]: c for c in escalations.pending()}
    assert cards[own]["occurrences"] == 1 and "attribution" not in cards[own]
    assert cards[other]["occurrences"] == 2
    # Filed on its target (AL1c): the target says what it is about, no attribution kept.
    tid = escalations.record(signal_id="s4", attribution=loose, target={"kind": "nsg", "name": "n"},
                             resource_id="nsg", action="", escalation_type="control_plane_change", reason="r")
    assert "attribution" not in {c["id"]: c for c in escalations.pending()}[tid]


def test_the_console_says_not_attributed_never_its_anchor():
    """The page (glorfindel.js, read as tests/unit/test_card_target.py reads it): TO JUDGE's line,
    the card's note, the card's title say « not attributed » and the candidates — through `_attr`."""
    js = JS.read_text()
    loose = js.split("function _unattributed(e) {", 1)[1].split("\n}\n", 1)[0]
    assert "if (!e || _targetOf(e)) return null;" in loose
    assert "a.state === 'unattributed'" in loose and "e.escalation_type === 'unattributed_signal'" in loose
    txt = js.split("function _unattributedTxt(u) {", 1)[1].split("\n}\n", 1)[0]
    assert "not attributed — candidates: ${u.candidates.slice(0, _VMS_SHOWN).join(', ')}${more}" in txt
    judge = js.split("function renderToJudge() {", 1)[1].split("\n}\n", 1)[0]
    assert "const loose = _unattributed(c);" in judge
    assert ": loose ? _unattributedTxt(loose)\n" in judge
    assert "${_attr(vm)}" in judge
    note = js.split("function _targetNote(e, vmName) {", 1)[1].split("\n}\n", 1)[0]
    assert ("return `<div class=\"esc-context\" title=\"${_attr(_LOOSE_TITLE)}\">⚓ ${_attr(_unattributedTxt(loose))}"
            "${choose}</div>`;") in note
    # SEC-Ed (#954): on a snapshot's card, a constant says the human chooses the VM — through `_attr`.
    assert "const choose = _looseSnapshot(e) ? ` · ${_attr(_LOOSE_SNAPSHOT_SAID)}` : '';" in note
    assert note.index("if (loose)") < note.index("if (!_isAnchored(e)")
    # RTT1b: a tile of its own named by its label — an unattributed card still says it, first.
    assert "${_unattributed(e) ? 'not attributed' : (_tileSaid(e) || vmName)}" in js
    # ATT1 (#936): what `_isHeld` reads of the attribution is `_aimsLoose` only — an action aimed at
    # the VM on an unattributed card is never approved in one click (tests/unit/test_attribution_prime.py).
    held = js.split("function _isHeld(e) {", 1)[1].split("\n}\n", 1)[0]
    assert "&& !_aimsLoose(e)" in held and "attribution" not in held


def test_the_console_counts_the_writes_set_aside_on_the_rule():
    """The rule's line and its details say how many writes of the channel were set aside, and why."""
    js = JS.read_text()
    row = js.split("const _ruleRow = (r) => {", 1)[1].split("\n  };\n", 1)[0]
    assert "r.own_channel_count > 0" in row and "${own}" in row
    txt = js.split("function _ownChannelTxt(r) {", 1)[1].split("\n}\n", 1)[0]
    assert "write(s) of the watch's own return channel set aside" in txt
    assert "the watch's identity not read" in txt
    detail = js.split("function showRuleDetail(rule) {", 1)[1].split("\n}\n", 1)[0]
    assert "_attr(_ownChannelTxt(rule))" in detail
    api = (ROOT / "eregion_console/api.py").read_text()
    assert "**own_channel_counts(s)," in api


def test_the_shipped_base_names_no_account_address_nor_identity():
    """The exclusion is computed at run time from the configuration: the shipped rule stays generic."""
    rule = next(r for r in yaml.safe_load(SHIPPED.read_text())["rules"] if r["name"] == "data-exfiltration-blob")
    # Its code, comments left out (one names the address of the T1041 of 07/10, an example).
    q = "\n".join(line for line in rule["query"].splitlines() if not line.strip().startswith("//"))
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", q, re.I)
    assert not re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", q)
    assert "blob.core.windows.net" not in q and "${" not in q
    assert rule.get("env_guids") is None
