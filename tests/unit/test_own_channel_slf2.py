"""SLF2 (#1010): Orodruin's exercise channel and the watch that restarts no longer make a card
`data-exfiltration-blob` — two forms seen on the 21/11 (the cards of the session G1, judged Wrong).

1. **Orodruin's exercise channel.** A single PutBlob from Orodruin's private address to the account of
   the channels (`infra/orodruin/main.tf`, `azurerm_storage_account.channel`), `EgressBytes` 0:
   Orodruin publishing its run's report in the exercise channel (``EREGION_EXERCISE_CHANNEL``,
   eregion_core/exercise_channel.py, ``runs/<run_id>.json``). Unattributed, a snapshot at 40 %.
2. **The watch that restarts.** After the restart of 16:48 UTC (the v0.6.3 deployed), lines of the
   watch's heartbeat, from Imladris's address, made a card for a window: the watch that starts knew
   nothing of the writes of the one before.

Read here on the SDK's own objects (tests/unit/sdk_logs.py, SDK1a): the shipped query run as written
over forged writes (tests/unit/kql_subset.py), its rows the body the Log Analytics API sends — a
``dynamic`` column as its JSON text —, read by the pinned SDK's own ``LogsQueryClient``, then the real
`AzureMonitorDetector.run_query` and the real RulePoller. Mutants M6927–M6941 (scripts/mutants/SLF2.py).
No Azure, no model; every identifier is made up (repository public).
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from types import SimpleNamespace

import pytest

from glorfindel import own_channel
from glorfindel.detection_rules import RulePoller

from .test_own_channel import (
    ACCOUNT, BREE, CHANNEL, CONTAINER, GONDOLIN, GONDOLIN_IP, JS, NOW, OTHER_OID, URL, WATCH_IP, WATCH_OID,
    _Credential, _jwt, _Registry, _rule, _write,
)
from . import sdk_logs
from .test_own_channel_sdk import _detector, _heartbeats

RULE = "data-exfiltration-blob"
# Placeholders, never real ids: Orodruin's identity (the principal of its managed identity), its address.
ORODRUIN_OID = "00000000-0000-0000-0000-0000000000c3"
ORODRUIN_IP = "10.0.8.4"
EXERCISES = "exercises"
EXERCISE_URL = f"https://{ACCOUNT}.blob.core.windows.net/{EXERCISES}"
EXERCISE = own_channel.Channel(ACCOUNT, EXERCISES, ORODRUIN_OID)
CONFIGURED = (EXERCISE, "")
RUN = "r-20261121-0912"


def _orodruin(blob=f"runs/{RUN}.json", **kw):
    """A write of Orodruin as StorageBlobLogs holds it: its address, its identity, its container."""
    kw = {"oid": ORODRUIN_OID, "ip": ORODRUIN_IP, "container": EXERCISES, **kw}
    return _write(blob, **kw)


def _poll(lines, exercise=CONFIGURED, channel=CHANNEL, query=None):
    """One pass of the rule, read through the SDK: (signals sent, the rule's status, the poller)."""
    rule = _rule(query)
    sent: list = []
    p = RulePoller([rule], sent.append, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN},
                   channel=lambda: channel, exercise=lambda: exercise)
    p._status = {}
    det = _detector(lines)
    p._detector = lambda _rule: det
    p._registry = _Registry(BREE, GONDOLIN)
    p.poll_once(rule)
    p.stop()
    return sent, p._status.get(rule.name, {}), p


# ── 1. Orodruin's exercise channel ───────────────────────────────────────────────────────────────

def test_the_line_of_orodruin_of_the_21_11_through_the_sdk_is_set_aside_and_said(caplog):
    """Fini quand: the single PutBlob of the 21/11 (Orodruin's run report, `EgressBytes` 0), read
    through the SDK, makes no card; counted beside `own_channel`, said in the watch's log."""
    caplog.set_level(logging.INFO, logger="glorfindel.detection_rules")
    rows = _detector([_orodruin()]).run_query(_rule().query)
    assert len(rows) == 1 and isinstance(rows[0][own_channel.WRITERS], str)     # as the SDK hands it on
    assert {k: v for k, v in rows[0].items() if k != own_channel.WRITERS} == {
        "CallerIpAddress": ORODRUIN_IP, "AccountName": ACCOUNT, "PutBlobCount": 1, "EgressBytes": 0}
    sent, st, p = _poll([_orodruin()])
    assert sent == []
    ec = st["exercise_channel"]
    assert (ec["writes"], ec["rows"], ec["container"]) == (1, 1, EXERCISES) and ec["last"]
    assert ec["reason"] == own_channel.EXERCISE_REASON and "config" not in ec
    assert "own_channel" not in st and "last_error" not in st
    snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
    assert (snap["exercise_channel_count"], snap["exercise_channel_rows"], snap["exercise_channel_config"]) \
        == (1, 1, "")
    assert any("1 write(s) of Orodruin set aside" in r.getMessage() and "EREGION_ORODRUIN_PRINCIPAL_ID"
               in r.getMessage() for r in caplog.records)


def test_every_object_orodruin_writes_in_its_channel_is_set_aside():
    """Its window, a campaign's manifest and report, its journal, its word to the console: Orodruin's
    identity in its container, whatever the object (its role is that container's alone)."""
    lines = [_orodruin(f"{RUN}.json"), _orodruin("campaigns/c-1/manifest.json"),
             _orodruin(f"campaigns/c-1/runs/{RUN}.json"), _orodruin(f"audit/{RUN}.jsonl"),
             _orodruin("orodruin/contract.json", size=512)]
    sent, st, _ = _poll(lines)
    assert sent == [] and st["exercise_channel"]["writes"] == 5


@pytest.mark.parametrize("case, line", [
    ("another identity in the exercise channel", _orodruin(oid=OTHER_OID)),
    ("a write without an identity (a key, a SAS)", _orodruin(oid="")),
    ("Orodruin's identity in another container", _orodruin("db.bak", container="backup", size=4096)),
    ("Orodruin's identity in the watch's container", _orodruin("heartbeat.json", container=CONTAINER)),
    ("a container of that name on another account", _orodruin(account="stattacker")),
])
def test_another_writer_container_or_account_stays_a_card(case, line):
    """Fini quand: never the address alone — another identity from Orodruin's address, Orodruin's
    identity elsewhere, another account: a card, its counts whole."""
    sent, st, _ = _poll([line])
    assert len(sent) == 1, case
    row = sent[0]["raw_signal"]["first_result_row"]
    assert row["CallerIpAddress"] == ORODRUIN_IP and row["PutBlobCount"] == 1 and own_channel.WRITERS not in row
    assert not (st.get("exercise_channel") or {}).get("writes")


def test_orodruin_s_write_and_another_keep_the_rest():
    """Orodruin's report and, from its address, a write to another container: one card, its counts the
    other write's alone."""
    lines = [_orodruin(size=300), _orodruin("loot.tar", container="drop", oid=OTHER_OID, size=4096)]
    sent, st, _ = _poll(lines)
    assert len(sent) == 1
    assert sent[0]["raw_signal"]["first_result_row"] == {
        "CallerIpAddress": ORODRUIN_IP, "AccountName": ACCOUNT, "PutBlobCount": 1, "EgressBytes": 4096}
    assert (st["exercise_channel"]["writes"], st["exercise_channel"]["rows"]) == (1, 0)


def test_the_watch_s_own_writes_and_orodruin_s_are_each_their_own():
    """The two channels on one account: each set aside by its own identity and container, counted on
    its own line; Orodruin's identity in the watch's container, or the watch's in Orodruin's, a card."""
    sent, st, _ = _poll(_heartbeats() + [_orodruin()])
    assert sent == []
    assert st["own_channel"]["writes"] == 3 and st["exercise_channel"]["writes"] == 1
    crossed = [_write("heartbeat.json", oid=ORODRUIN_OID), _orodruin(oid=WATCH_OID, ip=WATCH_IP)]
    sent, _, _ = _poll(crossed)
    assert len(sent) == 1 and sent[0]["raw_signal"]["first_result_row"]["PutBlobCount"] == 2


# ── without configuration, nothing is set aside, and it is said ─────────────────────────────────

def test_the_exercise_channel_is_read_from_the_watch_s_environment():
    """`of_env`: the channel's URL and Orodruin's identity, both; else why not."""
    env = {"EREGION_EXERCISE_CHANNEL": EXERCISE_URL, "EREGION_ORODRUIN_PRINCIPAL_ID": ORODRUIN_OID}
    assert own_channel.of_env(env) == (EXERCISE, "")
    assert own_channel.of_env({**env, "EREGION_ORODRUIN_PRINCIPAL_ID": f" {ORODRUIN_OID.upper()} "}) \
        == (EXERCISE, "")
    assert own_channel.of_env({"EREGION_EXERCISE_CHANNEL": EXERCISE_URL}) == (None, "unset")
    for bad in ("orodruin", ORODRUIN_OID + "0", f"{ORODRUIN_OID},{OTHER_OID}"):
        assert own_channel.of_env({**env, "EREGION_ORODRUIN_PRINCIPAL_ID": bad}) == (None, "malformed")
    assert own_channel.of_env({"EREGION_ORODRUIN_PRINCIPAL_ID": ORODRUIN_OID}) == (None, "no channel")
    assert own_channel.of_env({**env, "EREGION_EXERCISE_CHANNEL": EXERCISE_URL + "/sub"}) == (None, "no channel")
    assert own_channel.of_env({}) == (None, "")
    assert own_channel.current_exercise() == (None, "")         # nothing registered: nothing


@pytest.mark.parametrize("config", ["unset", "malformed", "no channel"])
def test_without_orodruin_s_identity_nothing_is_set_aside_and_the_status_says_it(config, caplog):
    """Fini quand: Orodruin's identity unset, no object id, or no channel — the line of the 21/11 stays a
    card, and a write without any identity too; the rule's status says why, at each pass, the log once."""
    caplog.set_level(logging.WARNING, logger="glorfindel.detection_rules")
    for line in (_orodruin(), _orodruin(oid="")):
        sent, st, p = _poll([line], exercise=(None, config))
        assert len(sent) == 1
        assert st["exercise_channel"]["config"] == config and st["exercise_channel"]["writes"] == 0
        snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
        assert snap["exercise_channel_config"] == config and snap["exercise_channel_count"] == 0
    assert any("Orodruin's exercise channel" in r.getMessage() and "every row a card" in r.getMessage()
               for r in caplog.records)


def test_without_any_exercise_channel_nothing_is_set_aside_nor_said():
    """Neither the channel nor the identity declared (a watch with no Orodruin): a card, no line."""
    sent, st, _ = _poll([_orodruin()], exercise=(None, ""))
    assert len(sent) == 1 and "exercise_channel" not in st


def test_settle_without_an_identity_sets_nothing_aside():
    """`settle` itself: a channel without its writer is no configuration — a write without an identity
    in its container stays."""
    row = {"CallerIpAddress": ORODRUIN_IP, "AccountName": ACCOUNT, "PutBlobCount": 1, "EgressBytes": 0,
           own_channel.WRITERS: json.dumps([{"container": EXERCISES, "writer": "", "writes": 1, "bytes": 0,
                                             "known": 0}])}
    for exercise in (None, own_channel.Channel(ACCOUNT, EXERCISES, "")):
        kept, said = own_channel.settle([row], None, exercise)
        assert len(kept) == 1 and not said.get("exercise_writes")


def test_the_shipped_rule_only():
    """ATT1's condition holds: a rule of the client's layer under that name, its query changed, sets
    none of Orodruin's writes aside — a card, the column taken off."""
    sent, st, _ = _poll([_orodruin()], query=_rule().query + "| where PutBlobCount >= 1\n")
    assert len(sent) == 1 and own_channel.WRITERS not in sent[0]["raw_signal"]["first_result_row"]
    assert "exercise_channel" not in st


def test_an_unreadable_column_of_the_exercise_account_is_said_and_kept():
    """What cannot be read stays a card (SLF1b's condition): counted unparsed, once, the channel of the
    watch configured or not."""
    from .test_own_channel_sdk import _writers_text
    for channel in (CHANNEL, None):
        rule = _rule()
        sent: list = []
        p = RulePoller([rule], sent.append, ip_owners=lambda: {}, channel=lambda c=channel: c,
                       exercise=lambda: CONFIGURED)
        p._status = {}
        det = _detector([_orodruin()], _writers_text("nope"))
        p._detector = lambda _rule: det
        p._registry = _Registry(BREE, GONDOLIN)
        p.poll_once(rule)
        p.stop()
        assert len(sent) == 1 and p._status[RULE]["own_channel"]["unparsed"] == 1


def test_an_attack_started_is_not_answered_by_orodruin_s_report(monkeypatch):
    """`resolve_attack_started` polls through the SDK too: Orodruin's report in its channel is set
    aside — the run's own write is the detection."""
    from glorfindel.agent import resolve_attack_started
    lines = [_orodruin(), _write("loot.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout", container="drop")]
    sdk_logs.Workspace(sdk_logs.kql(lines, now=NOW)).serve(monkeypatch)
    monkeypatch.setattr(own_channel, "_EXERCISE", CONFIGURED)
    signal = {"event": "attack_started", "ttp": "T1041", "resource_id": GONDOLIN,
              "raw_signal": {"detection_source": "azure_monitor", "detection_query": _rule().query,
                             "log_analytics_workspace_id": "ws-test", "detection_timeout_s": 5}}
    out = resolve_attack_started(signal, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN, ORODRUIN_IP: BREE})
    assert out["event"] == "detection"
    assert out["raw_signal"]["detected_data"]["CallerIpAddress"] == GONDOLIN_IP


# ── 2. the watch that restarts ───────────────────────────────────────────────────────────────────

def _record(writer=WATCH_OID, writes=3, account=ACCOUNT, container=CONTAINER, **over):
    """The record the watch before this one left: its identity, its writes over the last minutes."""
    doc = {"account": account, "container": container, "writer": writer,
           "writes": [(NOW - timedelta(minutes=1 + i)).isoformat() for i in range(writes)]}
    doc.update(over)
    own_channel._STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    own_channel._STATE_FILE.write_text(json.dumps(doc), encoding="utf-8")
    return doc


def _starting(oid=""):
    """The channel as a watch that just started reads it: its identity not read yet (``oid`` "")."""
    pub = SimpleNamespace(channel=URL, writer=lambda: oid)
    return own_channel.of_publisher(pub, now=lambda: NOW)


def test_the_heartbeats_just_after_a_restart_are_set_aside_and_said(caplog):
    """Fini quand: the heartbeats of the watch before this one, in the window, its identity in its
    container, while this one cannot read its own yet — set aside through the SDK, counted (`restart`),
    said in the log."""
    caplog.set_level(logging.INFO, logger="glorfindel.detection_rules")
    _record()
    channel = _starting()()
    assert channel == own_channel.Channel(ACCOUNT, CONTAINER, WATCH_OID, budget=3)
    sent, st, p = _poll(_heartbeats(), channel=channel, exercise=(None, ""))
    assert sent == []
    oc = st["own_channel"]
    assert (oc["writes"], oc["rows"], oc["restart"]) == (3, 1, 3) and oc["restart_last"] and "unread" not in oc
    snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
    assert (snap["own_channel_count"], snap["own_channel_restart"]) == (3, 3)
    assert any("by the record of the watch before this one" in r.getMessage() for r in caplog.records)


def test_once_its_identity_is_read_the_record_stands_in_for_nothing():
    """The watch's own identity read: the record is not used — the same identity sets its writes aside
    as before (no `restart`); another identity, the record's writes are another identity's: a card."""
    _record()
    assert _starting(WATCH_OID)() == CHANNEL
    sent, st, _ = _poll(_heartbeats(), channel=_starting(WATCH_OID)(), exercise=(None, ""))
    assert sent == [] and "restart" not in st["own_channel"]
    sent, _, _ = _poll(_heartbeats(), channel=_starting(OTHER_OID)(), exercise=(None, ""))
    assert len(sent) == 1


def test_another_identity_or_container_at_restart_stays_a_card():
    """Fini quand: at restart, never another identity's writes, nor the record's identity elsewhere."""
    _record()
    channel = _starting()()
    for lines in (_heartbeats(oid=OTHER_OID), _heartbeats(container="backup"), _heartbeats(account="stattacker")):
        sent, st, _ = _poll(lines, channel=channel, exercise=(None, ""))
        assert len(sent) == 1, lines
        assert not (st.get("own_channel") or {}).get("restart")


def test_more_writes_than_the_record_holds_stay_a_card():
    """No more than the record holds in the window: two recorded, three in the row — a card."""
    _record(writes=2)
    sent, st, _ = _poll(_heartbeats(3), channel=_starting()(), exercise=(None, ""))
    assert len(sent) == 1 and not (st.get("own_channel") or {}).get("writes")
    _record(writes=3)
    sent, _, _ = _poll(_heartbeats(3), channel=_starting()(), exercise=(None, ""))
    assert sent == []


def _bad():
    return {
        "absent": None,
        "not json": "{not json",
        "a list": json.dumps([]),
        "another account": json.dumps({**_doc(), "account": "stattacker"}),
        "another container": json.dumps({**_doc(), "container": "backup"}),
        "a writer that is no object id": json.dumps({**_doc(), "writer": "watch"}),
        "a writer in upper case": json.dumps({**_doc(), "writer": WATCH_OID.upper()}),
        "writes that are no list": json.dumps({**_doc(), "writes": 999}),
        "a write that is no date": json.dumps({**_doc(), "writes": [*_doc()["writes"], "soon"]}),
        "a date without its offset": json.dumps({**_doc(), "writes": ["2026-11-19T09:59:00"]}),
        "too many writes": json.dumps({**_doc(), "writes": [_doc()["writes"][0]] * (own_channel.MAX_WRITES + 1)}),
        "past its bound": json.dumps({**_doc(), "pad": "x" * own_channel.STATE_MAX}),
        "writes past the window": json.dumps({**_doc(), "writes": [(NOW - timedelta(minutes=7)).isoformat()]}),
        "writes after now": json.dumps({**_doc(), "writes": [(NOW + timedelta(minutes=1)).isoformat()]}),
    }


def _doc():
    return {"account": ACCOUNT, "container": CONTAINER, "writer": WATCH_OID,
            "writes": [(NOW - timedelta(minutes=1 + i)).isoformat() for i in range(3)]}


@pytest.mark.parametrize("case", list(_bad()))
def test_an_unreadable_record_never_stands_in(case, caplog):
    """Fini quand: a record absent, unreadable, of another channel, or of nothing in the window is never
    « all known » — the identity is unread, as before: a card, and said."""
    caplog.set_level(logging.WARNING, logger="glorfindel.detection_rules")
    text = _bad()[case]
    if text is not None:
        own_channel._STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        own_channel._STATE_FILE.write_text(text, encoding="utf-8")
    channel = _starting()()
    assert channel == own_channel.Channel(ACCOUNT, CONTAINER, "")
    sent, st, _ = _poll(_heartbeats(), channel=channel, exercise=(None, ""))
    assert len(sent) == 1 and st["own_channel"]["unread"] and not st["own_channel"]["writes"]
    assert any("identity could not be read" in r.getMessage() for r in caplog.records)


def test_the_publisher_keeps_the_record_for_the_next_watch():
    """The real publisher: each write acknowledged recorded under its identity, read by the next watch
    at its start — the writes past the window leave the record; another identity starts it again."""
    from eregion_core.watch_channel import Publisher
    puts = []

    def put(url, **_kw):
        puts.append(url)
        return SimpleNamespace(ok=True, status_code=201)
    pub = Publisher(URL, credential=_Credential(_jwt({"oid": WATCH_OID})), put=put, windows=lambda: [])
    pub.SIGNS = False
    own_channel.of_publisher(pub, previous=None)
    pub.tick()
    assert puts == [f"{URL}/heartbeat.json"]
    rec = json.loads(own_channel._STATE_FILE.read_text())
    assert (rec["account"], rec["container"], rec["writer"], len(rec["writes"])) == (ACCOUNT, CONTAINER, WATCH_OID, 1)
    prev = own_channel.load_previous(ACCOUNT, CONTAINER)
    assert prev.writer == WATCH_OID and len(prev.writes) == 1
    assert own_channel.load_previous(ACCOUNT, "backup") is None
    # The next watch carries the record on under the same identity, never another one's.
    nxt = Publisher(URL, credential=_Credential(_jwt({"oid": OTHER_OID})), put=put, windows=lambda: [])
    nxt.SIGNS = False
    own_channel.of_publisher(nxt)
    nxt.tick()
    rec = json.loads(own_channel._STATE_FILE.read_text())
    assert rec["writer"] == OTHER_OID and len(rec["writes"]) == 1
    # A watch whose identity is not read records nothing.
    blind = Publisher(URL, credential=_Credential(error=RuntimeError("imds")), put=put, windows=lambda: [])
    blind.SIGNS = False
    own_channel.of_publisher(blind)
    blind.on_written("heartbeat.json")
    assert json.loads(own_channel._STATE_FILE.read_text()) == rec


def test_the_record_keeps_the_window_alone():
    """Writes older than the rule's window leave the record; at most MAX_WRITES are kept."""
    old = (NOW - timedelta(hours=1)).isoformat()
    rec = own_channel.Recorder(ACCOUNT, CONTAINER, lambda: WATCH_OID,
                               own_channel.Previous(WATCH_OID, (own_channel._when(old),)))
    rec.wrote("heartbeat.json")
    doc = json.loads(own_channel._STATE_FILE.read_text())
    assert len(doc["writes"]) == 1 and doc["writes"][0] != old


# ── the console: the rule's line and its details, through `_attr` ───────────────────────────────

def test_the_console_says_orodruin_s_writes_and_the_restart_on_the_rule():
    txt = JS.read_text()
    fn = txt.split("function _exerciseChannelTxt(r) {", 1)[1].split("\n}\n", 1)[0]
    assert "r.exercise_channel_count" in fn and "EREGION_ORODRUIN_PRINCIPAL_ID unset" in fn
    assert "_attr(_exerciseChannelTxt(r))" in txt and "_attr(_exerciseChannelTxt(rule))" in txt
    assert "${oro}" in txt
    own = txt.split("function _ownChannelTxt(r) {", 1)[1].split("\n}\n", 1)[0]
    assert "r.own_channel_restart" in own and "the record of the watch before this one" in own
