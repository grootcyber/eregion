"""SLF1b (#976): the watch's own return channel set aside when the SDK hands ``BlobWriters`` on as
text — read here on the SDK's own objects, never on a Python list.

Seen on Imladris (20/11, after the v0.6.2 was deployed at 12:35 UTC): a card `data-exfiltration-blob`,
unattributed, proposing `isolate_vm`, every 10 minutes — `PutBlobCount 3`, `EgressBytes 0` —, the
rule's `own_channel` counter empty. StorageBlobLogs over 2 h: 118 PutBlob in the container `watch`,
one writer, OAuth, the object `heartbeat.json` — the watch's heartbeat. The channel configured, the
watch's identity read, the shipped rule loaded. The row out of `detector_for(...).run_query` held
`BlobWriters` as a ``str`` (JSON): its entry, decoded, met every condition of SLF1 — and `settle`,
which wanted a list, kept the row. The tests of SLF1 passed a Python list.

Here the shipped query runs as written over forged writes (tests/unit/kql_subset.py, as
tests/unit/test_own_channel.py), its rows become the body the Log Analytics API sends — a
``dynamic`` column as its JSON text, as measured —, read by the pinned SDK's own client
(azure-monitor-query, tests/unit/sdk_logs.py since SDK1a: its `LogsQueryResult`, over azure-core's
transport), then by the real `AzureMonitorDetector.run_query` and the real RulePoller. Mutants M6715–M6727 (scripts/mutants/SLF1b.py). No Azure, no model; every
identifier is made up (repository public).
"""
from __future__ import annotations

import json
import logging

import pytest

from glorfindel import auditd, own_channel
from glorfindel.detection_rules import RulePoller
from glorfindel.providers.azure.monitor import AzureMonitorDetector

from . import sdk_logs
from . import test_auditd as aud
from .test_own_channel import (
    ACCOUNT, BREE, CHANNEL, CONTAINER, GONDOLIN, GONDOLIN_IP, NOW, OTHER_OID, WATCH_IP, WATCH_OID,
    _channel_writes, _Registry, _rule, _write,
)

RULE = "data-exfiltration-blob"
# The row of the 20/11, as its column decoded on Imladris: one writer, its three heartbeats.
ENTRY_2011 = {"bytes": 0, "container": CONTAINER, "known": 3, "writer": WATCH_OID, "writes": 3}


def _heartbeats(n=3, **kw):
    """The watch's heartbeats in the window: `heartbeat.json`, by its identity, from its address."""
    return [_write("heartbeat.json", minutes=1 + i, **kw) for i in range(n)]


def _detector(lines, mangle=None) -> AzureMonitorDetector:
    """Log Analytics through the SDK's objects: the query run as written over `lines`, its reply
    read by the pinned SDK's client (tests/unit/sdk_logs.py). `mangle`: the body changed before
    it is sent (a value the reply would carry)."""
    return sdk_logs.Workspace(sdk_logs.kql(lines, now=NOW, mangle=mangle)).detector()


def _poll(lines, channel=CHANNEL, mangle=None):
    """One pass of the shipped rule, read through the SDK: (signals sent, the rule's status, poller)."""
    rule = _rule()
    sent: list = []
    p = RulePoller([rule], sent.append, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN}, channel=lambda: channel)
    p._status = {}
    det = _detector(lines, mangle)
    p._detector = lambda _rule: det
    p._registry = _Registry(BREE, GONDOLIN)
    p.poll_once(rule)
    p.stop()
    return sent, p._status.get(rule.name, {}), p


def _writers_text(text):
    """A mangle: the BlobWriters value of every row replaced by `text` (on the wire, as sent)."""
    def mangle(body):
        table = body["tables"][0]
        i = [c["name"] for c in table["columns"]].index(own_channel.WRITERS)
        for row in table["rows"]:
            row[i] = text(row[i]) if callable(text) else text
    return mangle


# ── the reading: the column as the SDK hands it on ──────────────────────────────────────────────

def test_the_sdk_hands_the_dynamic_column_on_as_text():
    """The row of the 20/11 out of the SDK's objects, as `run_query` gives it: `BlobWriters` a `str`,
    its JSON the entry Imladris decoded — the form the tests of SLF1 never passed."""
    rows = _detector(_heartbeats()).run_query(_rule().query)
    assert len(rows) == 1
    row = rows[0]
    assert {k: v for k, v in row.items() if k != own_channel.WRITERS} == {
        "CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 3, "EgressBytes": 0}
    assert isinstance(row[own_channel.WRITERS], str)
    assert json.loads(row[own_channel.WRITERS]) == [ENTRY_2011]


# ── Fini quand: the row of the 20/11 is set aside ───────────────────────────────────────────────

def test_the_row_of_the_20_11_through_the_sdk_is_set_aside_and_said(caplog):
    """Fini quand (#976): the watch's three heartbeats, read through the SDK, make no card; the rule's
    status counts them, as SLF1 meant."""
    caplog.set_level(logging.INFO, logger="glorfindel.detection_rules")
    sent, st, p = _poll(_heartbeats())
    assert sent == []
    assert st["own_channel"]["writes"] == 3 and st["own_channel"]["rows"] == 1
    assert "unparsed" not in st["own_channel"] and "last_error" not in st
    snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
    assert (snap["own_channel_count"], snap["own_channel_rows"], snap["own_channel_unparsed"]) == (3, 1, 0)
    assert any("3 write(s) set aside" in r.getMessage() for r in caplog.records)


def test_settle_reads_the_column_as_a_list_or_its_json_text():
    """The same row, its column a list (SLF1's form) or its JSON text (the SDK's): set aside alike."""
    row = {"CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 3, "EgressBytes": 0}
    for writers in ([ENTRY_2011], json.dumps([ENTRY_2011])):
        kept, said = own_channel.settle([{**row, own_channel.WRITERS: writers}], CHANNEL)
        assert kept == [] and said == {"writes": 3, "rows": 1, "unread": False, "unparsed": 0}


def test_another_write_through_the_sdk_keeps_its_rest():
    """A write of another identity in the channel's container, and one of the watch's address to
    another container: the row stays a card, its counts the other writes' only."""
    lines = _heartbeats() + [_write("heartbeat.json", oid=OTHER_OID, size=512),
                             _write("db.bak", container="backup", size=4096)]
    sent, st, _ = _poll(lines)
    assert len(sent) == 1
    assert sent[0]["raw_signal"]["first_result_row"] == {
        "CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 2, "EgressBytes": 4608}
    assert st["own_channel"]["writes"] == 3 and st["own_channel"]["rows"] == 0


def test_the_conditions_of_slf1_hold_through_the_sdk():
    """Nothing else changes: another account, another identity alone, an object the channel never
    holds, no channel configured, the watch's identity not read — a card, read through the SDK."""
    cases = [
        (_channel_writes(account="stattacker"), CHANNEL),
        (_channel_writes(oid=OTHER_OID), CHANNEL),
        (_heartbeats() + [_write("payload.bin")], CHANNEL),
        (_heartbeats(), None),
        (_heartbeats(), own_channel.Channel(ACCOUNT, CONTAINER, "")),
    ]
    for lines, channel in cases:
        sent, _, _ = _poll(lines, channel=channel)
        assert len(sent) == 1, (lines, channel)
        assert own_channel.WRITERS not in sent[0]["raw_signal"]["first_result_row"]


def test_an_attack_started_is_not_answered_by_the_watch_s_heartbeat_through_the_sdk(monkeypatch):
    """`resolve_attack_started` polls through the SDK too (`poll_alert`): the watch's heartbeat, its
    column as text, is set aside — the run's own write is the detection."""
    from glorfindel.agent import resolve_attack_started
    lines = _heartbeats() + [_write("loot.tar", oid=OTHER_OID, ip=GONDOLIN_IP, account="stout",
                                    container="drop")]
    sdk_logs.Workspace(sdk_logs.kql(lines, now=NOW)).serve(monkeypatch)
    monkeypatch.setattr(own_channel, "_SOURCE", lambda: CHANNEL)
    signal = {"event": "attack_started", "ttp": "T1041", "resource_id": GONDOLIN,
              "raw_signal": {"detection_source": "azure_monitor", "detection_query": _rule().query,
                             "log_analytics_workspace_id": "ws-test", "detection_timeout_s": 5}}
    out = resolve_attack_started(signal, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN})
    assert out["event"] == "detection"
    assert out["raw_signal"]["detected_data"] == {"CallerIpAddress": GONDOLIN_IP, "AccountName": "stout",
                                                  "PutBlobCount": 1, "EgressBytes": 0}


# ── Fini quand: a text unreadable sets nothing aside, never raises, and is said ─────────────────

def _deep(_text):
    return "[" * 60_000          # under the bound, deeper than the decoder goes: RecursionError


def _long(text):
    return text + " " * own_channel.WRITERS_MAX      # the same list, past the bound


UNREADABLE = {
    "truncated": lambda text: text[: len(text) // 2],
    "not json": "heartbeat.json by the watch",
    "nested too deep": _deep,
    "past the bound": _long,
    "an object, not a list": lambda text: json.dumps(json.loads(text)[0]),
    "a list of lists": lambda text: json.dumps([list(e.values()) for e in json.loads(text)]),
    "an object and a null": lambda text: json.dumps(json.loads(text) + [None]),
    "an object and a text": lambda text: json.dumps(json.loads(text) + ["x"]),
    "null": "null",
}


@pytest.mark.parametrize("case", list(UNREADABLE))
def test_an_unreadable_column_sets_nothing_aside_never_raises_and_is_said(case, caplog):
    """Fini quand: a BlobWriters text unreadable, past `WRITERS_MAX`, or not a list of objects — the
    row of the 20/11 stays a card, as read (its counts whole); no fault, the pass goes on; the rule's
    status counts the row beside `own_channel` (`unparsed`), the watch's log says it."""
    caplog.set_level(logging.WARNING, logger="glorfindel.detection_rules")
    sent, st, p = _poll(_heartbeats(), mangle=_writers_text(UNREADABLE[case]))
    assert len(sent) == 1
    assert sent[0]["raw_signal"]["first_result_row"] == {
        "CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 3, "EgressBytes": 0}
    assert "last_error" not in st                      # read, not a fault of the reading
    oc = st["own_channel"]
    assert oc["unparsed"] == 1 and oc["unparsed_last"] and oc["writes"] == 0
    snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
    assert snap["own_channel_unparsed"] == 1 and snap["own_channel_unparsed_last"]
    assert any("column unreadable" in r.getMessage() and own_channel.WRITERS in r.getMessage()
               for r in caplog.records)


@pytest.mark.parametrize("case", list(UNREADABLE))
def test_settle_never_raises_on_an_unreadable_column(case):
    """`settle` itself, never the poller's net: the row kept, counted, no exception."""
    text = json.dumps([ENTRY_2011])
    value = UNREADABLE[case](text) if callable(UNREADABLE[case]) else UNREADABLE[case]
    row = {"CallerIpAddress": WATCH_IP, "AccountName": ACCOUNT, "PutBlobCount": 3, "EgressBytes": 0,
           own_channel.WRITERS: value}
    kept, said = own_channel.settle([row], CHANNEL)
    assert kept == [{k: v for k, v in row.items() if k != own_channel.WRITERS}]
    assert said == {"writes": 0, "rows": 0, "unread": False, "unparsed": 1}


def test_the_bound_is_the_text_s_and_a_text_at_it_is_read():
    """At `WRITERS_MAX` characters the text is read; one more, not."""
    text = json.dumps([ENTRY_2011])
    at = text + " " * (own_channel.WRITERS_MAX - len(text))
    assert own_channel.writers_of(at) == [ENTRY_2011]
    assert own_channel.writers_of(at + " ") is None
    assert own_channel.writers_of([]) == [] and own_channel.writers_of("[]") == []


def test_unparsed_rows_count_on_across_passes_and_writes_keep_them():
    """The counter is cumulative: a second unreadable pass adds to it, a pass that sets writes aside
    keeps it."""
    rule = _rule()
    sent: list = []
    p = RulePoller([rule], sent.append, ip_owners=lambda: {GONDOLIN_IP: GONDOLIN}, channel=lambda: CHANNEL)
    p._status = {}
    p._registry = _Registry(BREE, GONDOLIN)
    bad = _detector(_heartbeats(), _writers_text("nope"))
    p._detector = lambda _rule: bad
    p.poll_once(rule)
    p._detector = lambda _rule: _detector(_heartbeats(2), _writers_text("still nope"))
    p.poll_once(rule)
    assert p._status[RULE]["own_channel"]["unparsed"] == 2
    p._detector = lambda _rule: _detector(_heartbeats(4))
    p.poll_once(rule)
    p.stop()
    oc = p._status[RULE]["own_channel"]
    assert oc["unparsed"] == 2 and oc["writes"] == 4


def test_a_row_of_another_account_is_not_counted_unparsed():
    """Only a row the channel could hold is read: another account's column is not, nor counted."""
    sent, st, _ = _poll(_channel_writes(account="stattacker"), mangle=_writers_text("nope"))
    assert len(sent) == 1 and "own_channel" not in st


def test_the_console_says_the_unparsed_rows_on_the_rule():
    """The rule's details say the rows whose column could not be read (through `_attr`)."""
    from .test_own_channel import JS
    txt = JS.read_text().split("function _ownChannelTxt(r) {", 1)[1].split("\n}\n", 1)[0]
    assert "r.own_channel_unparsed" in txt and "whose BlobWriters column could not be read" in txt
    assert "return [said, unread, unparsed].filter(Boolean).join(' · ');" in txt


# ── the other readers of a dynamic column: auditd's records ─────────────────────────────────────

def test_auditd_s_records_through_the_sdk_are_read_as_text():
    """`auditd-sensitive-root-command` projects `Syscall` and `Execve` (`make_set_if`, dynamic): through
    the SDK they arrive as text — read (hypothesis A11 of AUD1, now on the SDK's objects), the command
    named, never an « unreadable » card."""
    lines = aud.event(42, "cat", "/etc/shadow")
    rows = sdk_logs.Workspace(sdk_logs.kql(lines, now=aud.NOW)).detector().run_query(aud.RULE["query"])
    assert len(rows) == 1
    assert isinstance(rows[0]["Syscall"], str) and isinstance(rows[0]["Execve"], str)
    kept, counts = auditd.settle(auditd.TTP, rows)
    assert counts["sensitive"] == 1 and counts["unreadable"] == 0
    [card] = kept
    assert card["Sensitive"] == "shadow" and card["AuditCommand"] == "cat /etc/shadow"
    assert "AuditRead" not in card

