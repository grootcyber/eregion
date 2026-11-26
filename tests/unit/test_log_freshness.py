"""LOGF1 (#1183): the watch says whether the workspace's logs still arrive.

A diagnostic setting cut on the tenant or the subscription, and the rules of Entra ID and of the control
plane keep polling, without an error, on empty tables. The watch now reads, for each table its rules
read, when its last log arrived (glorfindel/log_freshness.py), writes it for the console
(`/api/watch/status`, `log_freshness`), and says a silence past the threshold on a card `logs_silent`.

No Azure here: a fake Log Analytics reader (`_Workspace`), a clock in the test's hand, the cards' store
redirected by the conftest.
"""
from __future__ import annotations

import ast
import io
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from azure.core.exceptions import HttpResponseError   # locked in requirements/dev.txt: never skipped

from glorfindel import escalations as esc
from glorfindel import kql
from glorfindel import log_freshness as lf
from glorfindel.detection_rules import DetectionRule
from glorfindel.read_budget import ReadBudget
from glorfindel.terminal import GlorfindelConsole

from .console_client import console

SHIPPED = Path(lf.__file__).resolve().parent / "rules" / "azure" / "detection_rules.yaml"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc).timestamp()


def _rule(name, query, source="azure_monitor", ws="ws-1", enabled=True) -> DetectionRule:
    return DetectionRule(name=name, source=source, workspace_id=ws, query=query, ttp="", resource_id="",
                         enabled=enabled)


def _shipped(ws="ws-1") -> list[DetectionRule]:
    data = yaml.safe_load(SHIPPED.read_text(encoding="utf-8"))
    return [_rule(r["name"], r["query"], r.get("source") or "azure_monitor", ws) for r in data["rules"]]


def _ago(hours: float) -> str:
    return datetime.fromtimestamp(NOW - hours * 3600, timezone.utc).isoformat()


class _Clock:
    def __init__(self, t=NOW):
        self.t = t

    def __call__(self):
        return self.t


class _Workspace:
    """A fake Log Analytics reader: per table, the last log's arrival (an ISO text, a datetime, None) or
    an exception it raises; each query kept."""

    def __init__(self, tables: dict):
        self.tables = tables
        self.queries: list[tuple[str, tuple]] = []

    def run_query(self, query, timespan=None):
        self.queries.append((query, timespan))
        table = query.split("\n", 1)[0]
        value = self.tables.get(table)
        if isinstance(value, BaseException):
            raise value
        if value == "no-row":
            return []
        return [{_column(query): value}]


def _column(query: str) -> str:
    """The column a query's `summarize` names, as Log Analytics names it in its rows — a fake that
    answers whatever the code reads would never see a name changed on one side only."""
    m = re.search(r"\| summarize (\w+) = ", query)
    assert m, query
    return m.group(1)


class _HttpError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status_code = status


def _fresh(rules, tables, tmp_path, clock=None, budget=None, environ=None, said=None):
    ws = _Workspace(tables)
    f = lf.Freshness(rules, client_for=lambda _ws: ws, budget=budget or ReadBudget("LA", "LA_TEST_UNSET", 0),
                     clock=clock or _Clock(), path=tmp_path / "log_freshness.json",
                     say=(said.append if said is not None else None), environ=environ or {})
    return f, ws


ENTRA = [_rule("entra", "AuditLogs | where TimeGenerated > ago(1h)", "azure_entra"),
         _rule("signin", "AADServicePrincipalSignInLogs | where TimeGenerated > ago(1h)", "azure_entra"),
         _rule("activity", "AzureActivity | where TimeGenerated > ago(1h)", "azure_activity")]


# ── 1. The tables, from the rules ────────────────────────────────────────────────────────────────

def test_the_tables_are_those_the_shipped_rules_read_once_per_workspace():
    assert lf.wanted(_shipped()) == [("ws-1", "Perf"), ("ws-1", "StorageBlobLogs"), ("ws-1", "Syslog"),
                                     ("ws-1", "AzureActivity"), ("ws-1", "AuditLogs"),
                                     ("ws-1", "AADServicePrincipalSignInLogs")]
    two = lf.wanted(ENTRA[:1] + [_rule("other", "AuditLogs | take 1", "azure_entra", ws="ws-2")])
    assert two == [("ws-1", "AuditLogs"), ("ws-2", "AuditLogs")]


def test_a_rule_disabled_or_bound_to_no_workspace_is_not_followed():
    """Only the rules enabled and bound to a backend: a rule that cannot poll reads nothing."""
    rules = [_rule("off", "Syslog | take 1", enabled=False), _rule("nows", "Perf | take 1", ws=""),
             _rule("on", "AuditLogs | take 1", "azure_entra")]
    assert lf.wanted(rules) == [("ws-1", "AuditLogs")]


def test_the_first_table_of_a_query_never_a_let_name_a_function_nor_a_comment():
    ransomware = next(r for r in _shipped() if r.name == "ransomware-disk-write")
    assert lf.first_table(ransomware.query) == "Perf"                      # `samples` is a let name
    assert lf.first_table("// AuditLogs\nAzureActivity | take 1") == "AzureActivity"
    assert lf.first_table("union withsource=T isfuzzy=true Perf, Syslog | take 1") == "Perf"
    assert lf.first_table("let f = (x:string) { x };\nSigninLogs | take 1") == "SigninLogs"
    assert lf.first_table("let n = 5; let on = true; datatable(a:int)[1] | take 1") is None
    assert lf.first_table("") is None


@pytest.mark.parametrize("q", [
    'let s = "a;b"; AuditLogs | take 1',
    "let s = 'a;Perf'; AuditLogs | where x == 'c;d' | take 1",
    'let s = @"C:\\a;b"; let t = @"say ""x;y"""; AuditLogs | take 1',
    'let s = ```a;\nb```; AuditLogs | take 1',
    'let s = "a\\";b"; AuditLogs | take 1'])
def test_a_semicolon_in_a_text_literal_never_cuts_a_statement(q):
    """M7645: the query's text literals emptied before it is cut at `;` — never `b` read for a table."""
    assert lf.first_table(q) == "AuditLogs"


def test_a_query_the_parse_cannot_read_falls_back_on_what_its_detector_knows():
    assert lf.table_of(_rule("a", "datatable(a:int)[1]", "azure_activity")) == "AzureActivity"
    q = "datatable(a:int)[1] | join (AADServicePrincipalSignInLogs | take 1) on a | join (AuditLogs) on a"
    assert lf.table_of(_rule("e", q, "azure_entra")) == "AADServicePrincipalSignInLogs"
    assert lf.table_of(_rule("m", "datatable(a:int)[1]")) is None


def test_the_query_is_fixed_by_the_code_and_reads_the_arrival():
    assert lf.query("AuditLogs", 24) == ("AuditLogs\n| where TimeGenerated > ago(24h)\n"
                                         "| summarize LastIngest = max(ingestion_time())")
    with pytest.raises(ValueError):
        lf.query("AuditLogs | take 1", 24)


# ── 2. The threshold, read strictly ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,hours,noted", [
    ("", 24.0, False), ("6", 6.0, False), ("12.5", 12.5, False), ("1", 1.0, False), ("168", 168.0, False),
    ("0", 24.0, True), ("-3", 24.0, True), ("nan", 24.0, True), ("inf", 24.0, True), ("six", 24.0, True),
    ("0.5", 24.0, True), ("169", 24.0, True)])
def test_the_threshold_is_read_strictly(raw, hours, noted):
    """M7615: a value that is no finite number of hours in its range is the default (24 h), said."""
    h, note = lf.silent_after_hours({lf.ENV: raw})
    assert h == hours
    assert bool(note) is noted
    assert lf.window_hours(h) == max(24.0, 2 * h)


# ── 3. The read: fresh, old, none, an error ──────────────────────────────────────────────────────

def test_fresh_old_none_and_an_error_each_said_as_they_are(tmp_path):
    rules = ENTRA + [_rule("perf", "Perf | take 1"), _rule("sys", "Syslog | take 1")]
    tables = {"AuditLogs": _ago(1), "AADServicePrincipalSignInLogs": _ago(9), "AzureActivity": None,
              "Perf": "no-row", "Syslog": _HttpError(429, "Too many requests\nretry later")}
    f, ws = _fresh(rules, tables, tmp_path)
    doc = f.pass_once()
    t = doc["tables"]
    assert t["AuditLogs"] == {"last": _ago(1), "error": None, "plane": "identity"}
    assert t["AADServicePrincipalSignInLogs"] == {"last": _ago(9), "error": None, "plane": "identity"}
    assert t["AzureActivity"] == {"last": None, "error": None, "plane": "control"}   # read: no log in the window
    assert t["Perf"] == {"last": None, "error": None, "plane": "data"}
    assert t["Syslog"] == {"last": None, "error": "HTTP 429 — Too many requests", "plane": "data"}
    # the window: twice the threshold (24 h by default), at least a day — the timespan as the query
    q, span = ws.queries[0]
    assert "ago(48h)" in q and span[1] - span[0] == timedelta(hours=48, minutes=1)


# A fake id (no real workspace's): azure-core's network error repeats requests' text, its URL with it.
WS_ID = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
_NETWORK = ConnectionError(f"HTTPSConnectionPool(host='api.loganalytics.io', port=443): Max retries exceeded with "
                           f"url: /v1/workspaces/{WS_ID}/query (Caused by NewConnectionError('refused'))")
_IDENTITY = RuntimeError(f"ClientSecretCredential: AADSTS700016: application {WS_ID.replace('-', '')} not found in "
                         f"tenant {WS_ID.upper()} — see https://login.microsoftonline.com/{WS_ID}/oauth2")


@pytest.mark.parametrize("exc,said", [
    (_HttpError(403, "Forbidden"), "HTTP 403 — Forbidden"),
    (ConnectionError("network unreachable"), "ConnectionError — network unreachable"),
    (RuntimeError("workspace query not successful: PARTIAL"), "RuntimeError — workspace query not successful: PARTIAL"),
    (_NETWORK, "ConnectionError — HTTPSConnectionPool(host='api.loganalytics.io', port=443): Max retries exceeded "
               "with url: /v1/workspaces/<id>/query (Cau"),
    (_IDENTITY, "RuntimeError — ClientSecretCredential: AADSTS700016: application <id> not found in tenant <id> — "
                "see <url>")])
def test_a_read_that_fails_is_an_error_never_no_log(tmp_path, exc, said):
    """M7611: a 403, the network, a partial answer — `error`, never `last: null` alone. M7641: its text
    without a GUID nor a URL (a workspace's, a tenant's, an application's id), masked before it is cut —
    not a fragment of the id survives."""
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": exc}, tmp_path)
    error = f.pass_once()["tables"]["AuditLogs"]["error"]
    assert error == said
    for part in WS_ID.split("-"):
        assert part.lower() not in error.lower()
    assert not esc.pending()                                               # M7612: no card « silent »


def test_a_datetime_from_the_sdk_is_written_as_iso_in_utc(tmp_path):
    dt = datetime(2026, 11, 25, 11, 30, tzinfo=timezone.utc)
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": dt}, tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"]["last"] == "2026-11-25T11:30:00+00:00"


def test_two_workspaces_the_table_is_as_old_as_its_oldest_and_failed_if_one_fails():
    a = {"table": "AuditLogs", "last": _ago(1), "error": None}
    b = {"table": "AuditLogs", "last": _ago(8), "error": None}
    planes = {"AuditLogs": "identity"}
    assert lf.merged({"1|A": a, "2|A": b}, planes)["AuditLogs"] == {"last": _ago(8), "error": None, "plane": "identity"}
    none = {"table": "AuditLogs", "last": None, "error": None}
    assert lf.merged({"1|A": a, "2|A": none}, planes)["AuditLogs"] == {"last": None, "error": None, "plane": "identity"}
    err = {"table": "AuditLogs", "last": None, "error": "HTTP 403"}
    assert lf.merged({"1|A": a, "2|A": err})["AuditLogs"] == {"last": _ago(1), "error": "HTTP 403", "plane": "data"}


# ── 4. The rhythm and the budget ─────────────────────────────────────────────────────────────────

def test_each_table_is_read_every_15_minutes_not_at_every_pass(tmp_path):
    """M7617: the watch looks every minute; a table is read again only once EVERY_S passed."""
    clock = _Clock()
    f, ws = _fresh(ENTRA, {"AuditLogs": _ago(1)}, tmp_path, clock=clock)
    assert f.pass_once() is not None and len(ws.queries) == 3
    for step in (60, 600, lf.EVERY_S - 61):
        clock.t = NOW + step
        assert f.due() == [] and f.pass_once() is None
    clock.t = NOW + lf.EVERY_S
    f.pass_once()
    assert len(ws.queries) == 6


def test_the_reads_are_on_the_budget_within_half_its_minute_and_never_refuse_the_detection(tmp_path):
    """M7616: on Log Analytics' budget of the watch (DOS4), half of its minute at most — the detection,
    which only notes, keeps the other half; a table left out is read a minute later, `not read`."""
    clock = _Clock()
    budget = ReadBudget("Log Analytics", "LA_TEST_CAP", 4, clock=clock)
    f, ws = _fresh(ENTRA, {"AuditLogs": _ago(1), "AADServicePrincipalSignInLogs": _ago(1),
                           "AzureActivity": _ago(1)}, tmp_path, clock=clock, budget=budget)
    t = f.pass_once()["tables"]
    assert len(ws.queries) == 2 and budget.used() == {"freshness": 2}
    assert t["AzureActivity"] == {"last": None, "error": lf.DEFERRED, "deferred": True, "plane": "control"}
    assert not esc.pending()                                               # not read: no card
    clock.t = NOW + 30
    budget.spend(3)                                                        # the detection: counted, never refused
    assert budget.used() == {"freshness": 2, "detection": 3}
    clock.t = NOW + lf.RETRY_S
    assert f.due() == [("ws-1", "AzureActivity")]
    f.pass_once()
    assert len(ws.queries) == 2                                            # the minute is still full
    clock.t = NOW + lf.RETRY_S * 2 + 1
    assert f.pass_once()["tables"]["AzureActivity"] == {"last": _ago(1), "error": None, "plane": "control"}
    assert len(ws.queries) == 3


def test_a_budget_of_zero_has_no_threshold_the_reads_are_counted(tmp_path):
    budget = ReadBudget("Log Analytics", "LA_TEST_UNSET", 0)
    f, ws = _fresh(ENTRA, {}, tmp_path, budget=budget)
    f.pass_once()
    assert len(ws.queries) == 3 and budget.used() == {"freshness": 3}


def test_a_budget_of_one_still_lets_one_read_in_an_empty_minute(tmp_path, monkeypatch):
    """M7647: `GLORFINDEL_LA_BUDGET_PER_MIN=1` — half of it is 0, and no read ever passed. One read at
    least, in a minute nothing else used; the detection, which only notes, still never refused."""
    clock = _Clock()
    monkeypatch.setenv("LA_TEST_ONE", "1")
    budget = ReadBudget("Log Analytics", "LA_TEST_ONE", 120, clock=clock)
    f, ws = _fresh(ENTRA, {"AuditLogs": _ago(1)}, tmp_path, clock=clock, budget=budget)
    f.pass_once()
    assert len(ws.queries) == 1 and budget.used() == {"freshness": 1}
    budget.spend(2)                                                        # the detection: never refused
    clock.t = NOW + lf.RETRY_S + 1
    budget.spend(1)                                                        # a minute already used
    f.pass_once()
    assert len(ws.queries) == 1


# ── 5. The file, and the console's field ─────────────────────────────────────────────────────────

def test_the_file_is_written_at_once_and_the_console_reads_its_contract(tmp_path):
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(1)}, tmp_path)
    f.pass_once()
    path = tmp_path / "log_freshness.json"
    assert not list(tmp_path.glob(".log_freshness.json.*"))                # no temp file left
    assert lf.console_field(path) == {"log_freshness": {
        "read_at": datetime.fromtimestamp(NOW, timezone.utc).isoformat(), "silent_after_hours": 24.0,
        "tables": {"AuditLogs": {"last": _ago(1), "error": None, "plane": "identity"}}}}


@pytest.mark.parametrize("text", ["", "{not json", "[]", '{"tables": {}}',
                                  '{"read_at": "2026-11-25T12:00:00+00:00", "silent_after_hours": "6", "tables": {}}',
                                  '{"read_at": "x", "silent_after_hours": 6, "tables": {}}',
                                  '{"read_at": "2026-11-25T12:00:00+00:00", "silent_after_hours": 6, "tables": []}',
                                  '{"read_at": "2026-11-25T12:00:00+00:00", "silent_after_hours": 6, '
                                  '"tables": {"AuditLogs": {"last": 5, "error": null}}}',
                                  '{"read_at": "2026-11-25T12:00:00+00:00", "silent_after_hours": 6, '
                                  '"tables": {"AuditLogs": {"last": null, "error": ["x"]}}}'])
def test_a_file_that_cannot_be_read_leaves_the_field_out(tmp_path, text):
    """M7619: a file unreadable, or of another form — no field, never a route broken."""
    path = tmp_path / "log_freshness.json"
    path.write_text(text)
    assert lf.console_field(path) == {}
    assert lf.console_field(tmp_path / "absent.json") == {}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return console()


def test_the_route_carries_the_field_and_leaves_it_out_when_unreadable(client, tmp_path):
    assert "log_freshness" not in client.get("/api/watch/status").json()      # nothing written yet
    path = lf.state_file()
    assert path == tmp_path / "home" / ".glorfindel" / "log_freshness.json"
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _HttpError(403, "Forbidden")}, tmp_path)
    f._path = path
    f.pass_once()
    w = client.get("/api/watch/status").json()
    assert w["log_freshness"]["tables"] == {"AuditLogs": {"last": None, "error": "HTTP 403 — Forbidden",
                                                          "plane": "identity"}}
    assert w["log_freshness"]["silent_after_hours"] == 24.0
    assert w["status"] == "stopped" and w["model_breaker"] == 0
    path.write_text("{broken")
    w = client.get("/api/watch/status").json()
    assert "log_freshness" not in w and w["status"] == "stopped"


def test_the_route_stands_when_the_module_raises(client, monkeypatch):
    """M7646: `_log_freshness` guarded as `_model_breakers` — a module that raises leaves the field out,
    the route and the heartbeat kept."""
    def broken(path=None):
        raise RuntimeError("module broken")
    monkeypatch.setattr(lf, "console_field", broken)
    r = client.get("/api/watch/status")
    assert r.status_code == 200
    w = r.json()
    assert "log_freshness" not in w and w["status"] == "stopped" and w["model_breaker"] == 0


# ── 6. The card: once an episode and per table, closed when the logs come back ───────────────────

def _silent_cards() -> list[dict]:
    return [e for e in esc.pending() if e.get("escalation_type") == lf.TYPE]


def test_logs_silent_past_the_threshold_make_one_card_an_episode_and_per_table(tmp_path):
    """M7613, M7620: one card per table (two tables never one card), never a second in the episode."""
    clock, said = _Clock(), []
    tables = {"AuditLogs": _ago(25), "AzureActivity": None, "AADServicePrincipalSignInLogs": _ago(23)}
    f, _ = _fresh(ENTRA, tables, tmp_path, clock=clock, said=said)
    f.pass_once()
    cards = _silent_cards()
    assert sorted(c["reason"].split("the table ")[1].split(" ")[0] for c in cards) == ["AuditLogs", "AzureActivity"]
    assert all(c["resource_id"] == "" and c["action"] == "" for c in cards)  # the watch's (MBV1)
    assert not esc.is_decision(cards[0]) and lf.TYPE in esc._NOT_DECISIONS
    assert any("no log arrived in the last 48 hours" in c["reason"] for c in cards)
    for step in (lf.EVERY_S, 2 * lf.EVERY_S):                              # still silent: no other card
        clock.t = NOW + step
        f.pass_once()
    assert len(_silent_cards()) == 2
    assert sum("logs silent" in s for s in said) == 2


def test_the_card_closes_when_the_logs_come_back_and_a_new_episode_makes_a_new_card(tmp_path):
    """M7614: the logs back, the card closed by the watch; silent again, a new card."""
    clock, said = _Clock(), []
    f, ws = _fresh(ENTRA[:1], {"AuditLogs": _ago(25)}, tmp_path, clock=clock, said=said)
    f.pass_once()
    first = _silent_cards()[0]["id"]
    clock.t = NOW + lf.EVERY_S
    ws.tables["AuditLogs"] = datetime.fromtimestamp(clock.t - 60, timezone.utc).isoformat()
    f.pass_once()
    assert _silent_cards() == []
    closed = next(e for e in esc.all_escalations() if e["id"] == first)
    assert closed["status"] == "resolved" and closed["resolution"] == lf.BACK
    assert any(s.startswith("logs back: AuditLogs") for s in said)
    clock.t = NOW + 2 * lf.EVERY_S + 25 * 3600
    f.pass_once()
    assert [c["id"] for c in _silent_cards()] != [first] and len(_silent_cards()) == 1


def test_a_failed_read_neither_opens_nor_closes_a_card_and_is_said_once(tmp_path):
    """M7612: a read in error is unknown — no card « silent »; an open one stays; said once in the log."""
    clock, said = _Clock(), []
    f, ws = _fresh(ENTRA[:1], {"AuditLogs": _ago(25)}, tmp_path, clock=clock, said=said)
    f.pass_once()
    assert len(_silent_cards()) == 1
    ws.tables["AuditLogs"] = _HttpError(403, "Forbidden")
    for step in (1, 2, 3):
        clock.t = NOW + step * lf.EVERY_S
        f.pass_once()
    assert len(_silent_cards()) == 1                                       # neither closed nor another
    assert sum("failed" in s for s in said) == 1


def test_a_restart_of_the_watch_in_an_episode_makes_no_second_card_nor_one_after_an_ack(tmp_path):
    clock = _Clock()
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(25)}, tmp_path, clock=clock)
    f.pass_once()
    card = _silent_cards()[0]["id"]
    esc.resolve(card, note="ack")                                          # the operator's Ack
    clock.t = NOW + lf.EVERY_S
    again, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(25)}, tmp_path, clock=clock)
    again.pass_once()
    assert _silent_cards() == []
    acked = next(e for e in esc.all_escalations() if e["id"] == card)
    assert acked["resolution"] == "ack"                                    # never rewritten


def test_the_threshold_is_the_watch_s_and_said_in_the_field_and_once_in_the_log(tmp_path):
    said: list = []
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(7)}, tmp_path, environ={lf.ENV: "8"}, said=said)
    assert f.pass_once()["silent_after_hours"] == 8.0 and _silent_cards() == []
    bad, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(1)}, tmp_path / "x", environ={lf.ENV: "0"}, said=said)
    bad.pass_once()
    assert sum(lf.ENV in s for s in said) == 1


def test_only_the_identity_and_the_control_plane_open_a_card_the_others_stay_in_the_field(tmp_path):
    """M7642 (the maintainer's decision of 25/11): Perf, Syslog, StorageBlobLogs, silent past the
    threshold — read, in the field, never a card; AuditLogs and AzureActivity, a card each."""
    assert lf.carded(_shipped()) == {"AzureActivity", "AuditLogs", "AADServicePrincipalSignInLogs"}
    # A rule of another source on Entra ID's or the Activity Log's table: its table still opens one.
    assert lf.carded([_rule("x", "SigninLogs | take 1"), _rule("y", "AzureActivity | take 1")]) == {
        "SigninLogs", "AzureActivity"}
    rules = ENTRA[:1] + ENTRA[2:] + [_rule("perf", "Perf | take 1"), _rule("sys", "Syslog | take 1"),
                                     _rule("blob", "StorageBlobLogs | take 1")]
    tables = {"AuditLogs": _ago(25), "AzureActivity": _ago(30), "Perf": _ago(40), "Syslog": None,
              "StorageBlobLogs": "no-row"}
    f, _ = _fresh(rules, tables, tmp_path)
    t = f.pass_once()["tables"]
    assert t["Perf"] == {"last": _ago(40), "error": None, "plane": "data"}
    assert t["Syslog"] == {"last": None, "error": None, "plane": "data"}
    assert t["StorageBlobLogs"] == {"last": None, "error": None, "plane": "data"}
    assert sorted(c["reason"].split("the table ")[1].split(" ")[0] for c in _silent_cards()) == [
        "AuditLogs", "AzureActivity"]
    assert set(lf.console_field(tmp_path / "log_freshness.json")["log_freshness"]["tables"]) == {
        "AuditLogs", "AzureActivity", "Perf", "Syslog", "StorageBlobLogs"}


def test_a_table_no_longer_followed_has_its_episode_and_its_card_closed(tmp_path):
    """M7643: the rule removed, the watch restarted — its table's card closed at the next pass, even when
    no other table is due; never left open on a table nobody reads."""
    clock, said = _Clock(), []
    perf = _rule("perf", "Perf | take 1")
    f, _ = _fresh(ENTRA[:1] + [perf], {"AuditLogs": _ago(25), "Perf": _ago(1)}, tmp_path, clock=clock)
    f.pass_once()
    card = _silent_cards()[0]["id"]
    clock.t = NOW + 60                                                     # Perf is not due again
    again, ws = _fresh([perf], {"Perf": _ago(1)}, tmp_path, clock=clock, said=said)
    assert again.due() == [] and again.has_work()
    doc = again.pass_once()
    assert _silent_cards() == [] and ws.queries == []
    closed = next(e for e in esc.all_escalations() if e["id"] == card)
    assert closed["status"] == "resolved" and closed["resolution"] == lf.UNFOLLOWED
    assert doc["episodes"] == {} and not again.has_work()
    assert any("AuditLogs" in s and lf.UNFOLLOWED in s for s in said)


def test_a_card_the_store_cannot_write_is_said_once_and_the_pass_still_writes_its_file(tmp_path):
    """M7644: `record` raises for one table — the other still gets its card, the file is written, the
    failure said once; the store back, the card is opened."""
    clock, said, broken = _Clock(), [], {"on": True}

    def record(**kw):
        if broken["on"] and "AuditLogs" in kw["signal_id"]:
            raise OSError("disk full")
        return esc.record(**kw)
    ws = _Workspace({"AuditLogs": _ago(25), "AzureActivity": _ago(30)})
    path = tmp_path / "log_freshness.json"
    f = lf.Freshness(ENTRA[:1] + ENTRA[2:], client_for=lambda _ws: ws,
                     budget=ReadBudget("LA", "LA_TEST_UNSET", 0), clock=clock, path=path, record=record,
                     say=said.append, environ={})
    f.pass_once()
    assert [c["reason"].split("the table ")[1].split(" ")[0] for c in _silent_cards()] == ["AzureActivity"]
    assert set(json.loads(path.read_text())["tables"]) == {"AuditLogs", "AzureActivity"}
    clock.t = NOW + lf.EVERY_S
    f.pass_once()
    assert sum("could not be written" in s for s in said) == 1
    broken["on"] = False
    clock.t = NOW + 2 * lf.EVERY_S
    f.pass_once()
    assert len(_silent_cards()) == 2


# ── 7. In the watch ──────────────────────────────────────────────────────────────────────────────

class _Connector:
    read_only = False

    def __init__(self, dry_run=False):
        self.dry_run = dry_run


def _housekeeping(monkeypatch, dry_run=False):
    from glorfindel.watch.housekeeping import Housekeeping
    monkeypatch.setattr("glorfindel.actions.AzureConnector", _Connector)
    buf = io.StringIO()
    hk = Housekeeping(GlorfindelConsole(file=buf, width=400, color_system=None), threading.Lock(),
                      dry_run=dry_run, mode_override="human_only", runs_dir="runs", ttl_h=4.0,
                      emit=lambda data: None, say_channel=lambda line: None)
    return hk, buf


def test_the_watch_follows_its_rules_tables_in_a_thread_and_never_in_dry_run(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = _Workspace({"AuditLogs": _ago(1)})
    monkeypatch.setattr(lf, "_default_client", lambda _ws: ws)
    dry, _ = _housekeeping(monkeypatch, dry_run=True)
    dry.follow_logs(ENTRA[:1])
    dry._log_freshness()
    assert dry._freshness is None and ws.queries == []
    hk, buf = _housekeeping(monkeypatch)
    hk.follow_logs(ENTRA[:1])
    hk._log_freshness()
    hk._freshness_thread._thread.join(timeout=10)
    assert len(ws.queries) == 1
    assert json.loads(lf.state_file().read_text())["tables"]["AuditLogs"]["last"] is not None
    hk._log_freshness()                                                    # nothing due: no thread
    assert len(ws.queries) == 1


def test_a_pass_that_fails_is_said_never_the_watch_stopped(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    hk, buf = _housekeeping(monkeypatch)
    hk.follow_logs(ENTRA[:1])

    def broken():
        raise OSError("disk full [/x]")
    monkeypatch.setattr(hk._freshness, "pass_once", broken)
    hk._log_freshness()
    hk._freshness_thread._thread.join(timeout=10)
    assert "logs' freshness failed" in buf.getvalue()


# ── 8. LOGF1b (#1191): a table the budget left out, the plane of each table, LOGF1's limits ─────────

def test_a_table_the_budget_left_out_is_deferred_its_last_value_kept_and_a_table_read_has_no_key(tmp_path):
    """M7671: `deferred: true` on a table left out at this pass — its last value read kept (null: never
    read), its `error` the deferral's, which the console sets aside; a table read has no `deferred`."""
    clock = _Clock()
    budget = ReadBudget("Log Analytics", "LA_TEST_CAP", 2, clock=clock)    # half of 2: one read a minute
    rules = ENTRA[:1] + ENTRA[2:]
    f, ws = _fresh(rules, {"AuditLogs": _ago(1), "AzureActivity": _ago(2)}, tmp_path, clock=clock, budget=budget)
    t = f.pass_once()["tables"]
    assert t["AuditLogs"] == {"last": _ago(1), "error": None, "plane": "identity"}
    assert t["AzureActivity"] == {"last": None, "error": lf.DEFERRED, "deferred": True, "plane": "control"}
    clock.t = NOW + lf.RETRY_S + 1
    assert f.pass_once()["tables"]["AzureActivity"] == {"last": _ago(2), "error": None, "plane": "control"}
    clock.t = NOW + lf.EVERY_S + lf.RETRY_S + 2
    budget.spend(1)                                                        # the detection took the minute
    t = f.pass_once()["tables"]
    assert t["AuditLogs"] == {"last": _ago(1), "error": lf.DEFERRED, "deferred": True, "plane": "identity"}
    assert t["AzureActivity"] == {"last": _ago(2), "error": lf.DEFERRED, "deferred": True, "plane": "control"}
    field = lf.console_field(tmp_path / "log_freshness.json")["log_freshness"]["tables"]
    assert field["AuditLogs"]["deferred"] is True and field["AuditLogs"]["last"] == _ago(1)
    assert not _silent_cards()


def test_a_failure_or_a_silence_is_never_hidden_behind_a_deferral():
    """M7701: a read left out keeps its last state — `deferred` only when it keeps a date, or was never
    read; a failure (its own last read, or another workspace's) and a silence (likewise) stay as they are."""
    left = {"table": "AuditLogs", "last": _ago(1), "error": None, "deferred_at": _ago(0)}
    failed = {"table": "AuditLogs", "last": None, "error": "HTTP 403"}
    assert lf.merged({"1|A": left, "2|A": failed})["AuditLogs"] == {"last": _ago(1), "error": "HTTP 403",
                                                                     "plane": "data"}
    stale = {"table": "AuditLogs", "last": None, "error": "HTTP 403", "deferred_at": _ago(0)}
    assert lf.merged({"1|A": stale})["AuditLogs"] == {"last": None, "error": "HTTP 403", "plane": "data"}
    mute = {"table": "AuditLogs", "last": None, "error": None, "deferred_at": _ago(0)}
    assert lf.merged({"1|A": mute})["AuditLogs"] == {"last": None, "error": None, "plane": "data"}
    silent = {"table": "AuditLogs", "last": None, "error": None}
    assert lf.merged({"1|A": left, "2|A": silent})["AuditLogs"] == {"last": None, "error": None, "plane": "data"}
    unread = {"table": "AuditLogs", "last": None, "error": lf.DEFERRED, "deferred_at": _ago(0)}
    assert lf.merged({"1|A": unread})["AuditLogs"] == {"last": None, "error": lf.DEFERRED, "deferred": True,
                                                       "plane": "data"}
    assert lf.merged({"1|A": left, "2|A": unread})["AuditLogs"] == {"last": None, "error": lf.DEFERRED,
                                                                     "deferred": True, "plane": "data"}


def _tile(entry: dict) -> str:
    """The console's reading of a table (IDT1): `deferred === true` and `last` null — not read yet."""
    if entry.get("deferred") is True:
        return "not read yet" if not entry.get("last") else "read"
    if entry.get("error"):
        return "failed"
    return "read" if entry.get("last") else "silent"


def _one_minute_held(tables, tmp_path, clock):
    """A pass, then one 15 min later whose minute the detection already took: the table left out."""
    budget = ReadBudget("Log Analytics", "LA_TEST_CAP", 2, clock=clock)    # half of 2: one read a minute
    f, ws = _fresh(ENTRA[:1], tables, tmp_path, clock=clock, budget=budget)
    f.pass_once()
    clock.t = NOW + lf.EVERY_S
    budget.spend(1)
    entry = f.pass_once()["tables"]["AuditLogs"]
    assert len(ws.queries) == 1 and f._reads["ws-1|AuditLogs"].get("deferred_at")
    return entry


def test_a_403_then_a_deferral_is_still_the_403(tmp_path):
    entry = _one_minute_held({"AuditLogs": _HttpError(403, "Forbidden")}, tmp_path, _Clock())
    assert entry == {"last": None, "error": "HTTP 403 — Forbidden", "plane": "identity"}
    field = lf.console_field(tmp_path / "log_freshness.json")["log_freshness"]["tables"]["AuditLogs"]
    assert _tile(field) == "failed"


def test_a_silent_table_then_a_deferral_stays_silent_its_card_open(tmp_path):
    """The tile never back to green on a table silent whose read the budget left out."""
    entry = _one_minute_held({"AuditLogs": None}, tmp_path, _Clock())
    assert entry == {"last": None, "error": None, "plane": "identity"}
    field = lf.console_field(tmp_path / "log_freshness.json")["log_freshness"]["tables"]["AuditLogs"]
    assert _tile(field) == "silent"
    assert len(_silent_cards()) == 1 and _silent_cards()[0]["status"] == "pending"


def test_the_plane_of_each_table_of_the_shipped_rules_and_of_a_client_s_rule():
    assert lf.planes(_shipped()) == {"Perf": "data", "StorageBlobLogs": "data", "Syslog": "data",
                                     "AzureActivity": "control", "AuditLogs": "identity",
                                     "AADServicePrincipalSignInLogs": "identity"}
    # A client's rule on SigninLogs, of the data source: the table says Entra ID — identity, a card.
    client = [_rule("signin", "SigninLogs | where ResultType != 0"), _rule("perf", "Perf | take 1")]
    assert lf.planes(client) == {"SigninLogs": "identity", "Perf": "data"}
    assert lf.carded(client) == {"SigninLogs"}


def test_a_table_read_by_two_rules_of_two_planes_takes_a_card_over_none_identity_first():
    """M7672: a table of no known plane read by rules of two sources — the plane that opens a card wins,
    identity before control, whatever the rules' order; a table that names its plane keeps it."""
    a, b = _rule("a", "MyApp_CL | take 1"), _rule("b", "MyApp_CL | take 1", "azure_activity")
    c = _rule("c", "MyApp_CL | take 1", "azure_entra")
    for rules in ([a, b], [b, a]):
        assert lf.planes(rules) == {"MyApp_CL": "control"}
    for rules in ([b, c], [c, b], [a, c, b]):
        assert lf.planes(rules) == {"MyApp_CL": "identity"}
    d = _rule("d", "SigninLogs | take 1", "azure_activity")
    assert lf.planes([_rule("e", "SigninLogs | take 1"), d]) == {"SigninLogs": "identity"}


def test_a_rule_of_entra_or_of_the_control_plane_misfiled_on_a_data_table_opens_no_card(tmp_path):
    """M7673 (limit 1): an `azure_entra` or `azure_activity` rule whose query starts with Perf or Syslog —
    the table stays `data`, never a card; a table of Entra ID the regex does not know, read by an
    `azure_entra` rule, keeps its card."""
    rules = [_rule("m1", "Perf | take 1", "azure_entra"), _rule("m2", "Syslog | take 1", "azure_activity"),
             _rule("m3", "StorageFileLogs | take 1", "azure_entra"),
             _rule("prov", "AADProvisioningLogs | take 1", "azure_entra")]
    assert lf.planes(rules) == {"Perf": "data", "Syslog": "data", "StorageFileLogs": "data",
                                "AADProvisioningLogs": "identity"}
    f, _ = _fresh(rules, {"Perf": _ago(40), "Syslog": None, "StorageFileLogs": None,
                          "AADProvisioningLogs": _ago(30)}, tmp_path)
    f.pass_once()
    assert [c["reason"].split("the table ")[1].split(" ")[0] for c in _silent_cards()] == ["AADProvisioningLogs"]


_FIELD = '{"read_at": "2026-11-25T12:00:00+00:00", "silent_after_hours": 6, "tables": {"AuditLogs": %s}}'


@pytest.mark.parametrize("entry,kept", [
    ('{"last": null, "error": "x", "deferred": true, "plane": "identity"}',
     {"last": None, "error": "x", "deferred": True, "plane": "identity"}),
    ('{"last": null, "error": null, "deferred": false, "plane": "data"}',
     {"last": None, "error": None, "deferred": False, "plane": "data"}),
    ('{"last": null, "error": null, "plane": "control"}', {"last": None, "error": None, "plane": "control"}),
    ('{"last": null, "error": null}', {"last": None, "error": None})])               # a file of LOGF1
def test_the_console_takes_the_new_keys(tmp_path, entry, kept):
    path = tmp_path / "log_freshness.json"
    path.write_text(_FIELD % entry)
    assert lf.console_field(path)["log_freshness"]["tables"] == {"AuditLogs": kept}


@pytest.mark.parametrize("entry", [
    '{"last": null, "error": null, "deferred": "true"}', '{"last": null, "error": null, "deferred": 1}',
    '{"last": null, "error": null, "deferred": null}', '{"last": null, "error": null, "plane": "Identity"}',
    '{"last": null, "error": null, "plane": "network"}', '{"last": null, "error": null, "plane": null}',
    '{"last": null, "error": null, "plane": ["data"]}', '{"last": null, "error": null, "plane": 2}'])
def test_the_new_keys_of_another_form_leave_the_whole_field_out(tmp_path, entry):
    """M7674: `deferred` a boolean, `plane` one of three — any other form, and the whole field is gone."""
    path = tmp_path / "log_freshness.json"
    path.write_text(_FIELD % entry)
    assert lf.console_field(path) == {}


def _an_episode(tmp_path, clock):
    """A pass that opens the card of AuditLogs, silent: its id."""
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(25)}, tmp_path, clock=clock)
    f.pass_once()
    return _silent_cards()[0]["id"]


def test_an_episode_whose_card_could_not_be_closed_is_written_back_and_closed_later(tmp_path):
    """M7675 (limit 2): the table no longer followed, its card not closed (the store fails) — the episode
    still in the file: read back, its card is closed at a later pass, never left open."""
    clock, said = _Clock(), []
    card = _an_episode(tmp_path, clock)

    def resolve(*a, **kw):
        raise OSError("disk full")
    path = tmp_path / "log_freshness.json"
    f = lf.Freshness([], client_for=lambda _ws: None, clock=clock, path=path, resolve=resolve,
                     say=said.append, environ={})
    clock.t = NOW + 60
    f.pass_once()
    assert set(json.loads(path.read_text())["episodes"]) == {"AuditLogs"}
    assert sum("could not be written" in s for s in said) == 1
    again, _ = _fresh([], {}, tmp_path, clock=clock)
    assert again.has_work()
    again.pass_once()
    closed = next(e for e in esc.all_escalations() if e["id"] == card)
    assert closed["resolution"] == lf.UNFOLLOWED and json.loads(path.read_text())["episodes"] == {}


def test_a_stale_card_closed_after_a_failure_is_no_longer_held_as_failed(tmp_path):
    """M7680 (limit 6): the store back, the card closed — its table out of `_card_failed`."""
    clock, broken = _Clock(), {"on": True}
    card = _an_episode(tmp_path, clock)

    def resolve(*a, **kw):
        if broken["on"]:
            raise OSError("disk full")
        return esc.resolve(*a, **kw)
    f = lf.Freshness([], client_for=lambda _ws: None, clock=clock, path=tmp_path / "log_freshness.json",
                     resolve=resolve, environ={})
    f.pass_once()
    assert f._card_failed == {"AuditLogs"}
    broken["on"] = False
    f.pass_once()
    assert f._card_failed == set() and not f.has_work()
    assert next(e for e in esc.all_escalations() if e["id"] == card)["status"] == "resolved"


def test_a_guid_with_its_dashes_is_masked_even_stuck_to_a_hex_character():
    """M7676 (limit 3): `a<guid>f` — the dashed GUID masked all the same; 32 hex characters alone masked,
    a longer hash (40) left as it is."""
    for text in (f"id=a{WS_ID}f", f"tenant {WS_ID.upper()}0", f"x{WS_ID}"):
        out = lf._scrubbed(text)
        assert "<id>" in out and not any(part.lower() in out.lower() for part in WS_ID.split("-"))
    assert lf._scrubbed(f"app {WS_ID.replace('-', '')}") == "app <id>"
    sha1 = "0f1e2d3c4b5a69788796a5b4c3d2e1f0aabbccdd"
    assert lf._scrubbed(f"commit {sha1}") == f"commit {sha1}"
    assert lf.short_error(RuntimeError(f"workspace a{WS_ID}b not found")) == "RuntimeError — workspace a<id>b not found"


@pytest.mark.parametrize("q", [
    "let s = h'a;b'; AuditLogs | take 1", 'let s = h"secret"; AuditLogs | take 1',
    'let s = H@"C:\\a;b"; AuditLogs | take 1', "let s = h@'x'; AuditLogs | take 1"])
def test_a_masked_literal_is_a_literal_never_its_h_read_for_a_table(q):
    """M7677 (limit 4): `h'…'`, `h"…"`, `H@"…"` — the literal emptied with its `h`, never `h` a table."""
    assert lf.first_table(q) == "AuditLogs"


def test_a_double_slash_in_a_string_cuts_nothing_and_a_quote_in_a_comment_opens_nothing():
    """M7678 (limit 4): comments and literals read in one pass — `"https://…"` never cuts its line,
    `// it's` never opens a string. `_query_code` (detection_rules), shared, is left as it is."""
    assert lf.first_table('let u = "https://x"; AuditLogs | take 1') == "AuditLogs"
    assert lf.first_table("let u = 'a//b'; let v = @\"c//d\"; SigninLogs | take 1") == "SigninLogs"
    assert lf.first_table("// it's a note\nAuditLogs | take 1") == "AuditLogs"
    assert lf.first_table("// 'Perf'; Syslog\nAuditLogs // the table's\n| take 1") == "AuditLogs"
    q = 'datatable(a:int)[1] | where u == "https://x" | join (SigninLogs) on a'
    assert lf.table_of(_rule("e", q, "azure_entra")) == "SigninLogs"


def test_the_watch_starts_no_pass_when_nothing_is_due(monkeypatch, tmp_path):
    """Limit 5: `has_work()` read by the watch — nothing due nor stale, no thread started."""
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = _Workspace({"AuditLogs": _ago(1)})
    monkeypatch.setattr(lf, "_default_client", lambda _ws: ws)
    hk, _ = _housekeeping(monkeypatch)
    hk.follow_logs(ENTRA[:1])
    hk._log_freshness()
    first = hk._freshness_thread._thread
    first.join(timeout=10)
    hk._log_freshness()
    assert hk._freshness_thread._thread is first and len(ws.queries) == 1


def test_every_rule_removed_the_watch_still_closes_the_episodes_of_its_file(monkeypatch, tmp_path):
    """M7679 (limit 5): `follow_logs` with no rule — nothing read, but the card of a table no longer
    followed closed (before: the watch returned early, the card stayed open)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    clock = _Clock()
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(25)}, tmp_path, clock=clock)
    f._path = lf.state_file()
    f.pass_once()
    card = _silent_cards()[0]["id"]
    ws = _Workspace({})
    monkeypatch.setattr(lf, "_default_client", lambda _ws: ws)
    hk, _ = _housekeeping(monkeypatch)
    hk.follow_logs([])
    hk._log_freshness()
    hk._freshness_thread._thread.join(timeout=10)
    assert next(e for e in esc.all_escalations() if e["id"] == card)["resolution"] == lf.UNFOLLOWED
    assert ws.queries == [] and not hk._freshness.has_work()


def test_the_fallback_of_entra_reads_a_table_named_in_a_literal():
    """`table("SigninLogs")`: the fallback of `azure_entra` strips the comments only, never the literals."""
    assert lf.table_of(_rule("t", 'table("SigninLogs") | where ResultType != 0', "azure_entra")) == "SigninLogs"
    assert lf.table_of(_rule("c", '// table("AuditLogs")\ntable("SigninLogs") | take 1', "azure_entra")) == "SigninLogs"


def test_a_plane_this_module_does_not_know_is_data_never_the_following_stopped(monkeypatch, tmp_path):
    """A detector of a plane outside PLANES: its table is `data`, no card, the other tables still read."""
    import glorfindel.detectors as det
    monkeypatch.setattr(det, "plane_of", lambda source: "network")
    rules = [_rule("x", "MyApp_CL | take 1", "azure_entra"), _rule("a", "AuditLogs | take 1", "azure_entra")]
    assert lf.planes(rules) == {"MyApp_CL": "data", "AuditLogs": "identity"}
    f, _ = _fresh(rules, {"MyApp_CL": None, "AuditLogs": _ago(1)}, tmp_path)
    assert f.pass_once()["tables"]["MyApp_CL"] == {"last": None, "error": None, "plane": "data"}
    assert _silent_cards() == []


# ── LOGF1c (#1212): the column never a word of KQL, the inner error said ─────────────────────────
# In 0.6.8 every read failed: `summarize last = …` — `last` a word of KQL (`nulls last`), a SyntaxError
# that Log Analytics answers in a 400 BadArgumentError, and `short_error` kept only its first line. The
# fake reader above never parsed the query: it could not see it. Measured in the workspace's editor
# (26/11): `last =` fails, `LastIngest =` answers.

V068 = "AuditLogs\n| where TimeGenerated > ago(48h)\n| summarize last = max(ingestion_time())"


@pytest.mark.parametrize("table,hours", [("AuditLogs", 24), ("AzureActivity", 48), ("Perf", 336.5)])
def test_the_query_names_no_word_of_kql_and_the_guard_was_red_on_0_6_8(table, hours):
    """M7751: the column a word of KQL again (`last`) — the guard says it, as it would have on 0.6.8."""
    q = lf.query(table, hours)
    assert kql.reserved_names(q) == []
    assert f"| summarize {lf.COLUMN} = max(ingestion_time())" in q and lf.COLUMN == "LastIngest"
    assert kql.reserved_names(V068) == ["last"]


def test_the_read_takes_its_value_under_the_column_the_query_names(tmp_path):
    """M7752: a read that takes `last` from its rows while the query names `LastIngest` reads nothing."""
    f, ws = _fresh(ENTRA[:1], {"AuditLogs": _ago(2)}, tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"]["last"] == _ago(2)
    assert _column(ws.queries[0][0]) == lf.COLUMN


def test_the_guard_reads_a_name_before_its_equal_sign_never_a_comparison():
    assert kql.reserved_names("T | extend first = 1, Last = 2, nulls = 3 | project desc = x") == ["first", "nulls", "desc"]
    assert kql.reserved_names("T | summarize n = sum(c), step = min(gap) by InstanceName") == []   # audit.py's
    assert kql.reserved_names("T | summarize n = count() by on = bin(TimeGenerated, 1h)") == ["on"]
    assert kql.reserved_names("T | project-rename last = Old") == ["last"]
    assert kql.reserved_names("T | where last == 1 or first =~ 'a' | summarize LastSeen = max(x), Peak = max(y)") == []
    assert kql.reserved_names("T | extend f = iff(x, last == 1, first =~ 'a')") == []   # M7760: a comparison
    assert kql.reserved_names("") == [] and kql.reserved_names(None) == []


def test_the_shipped_rules_name_no_word_of_kql_either():
    """The rules Glorfindel ships, under the same guard: none names a column with a word of KQL."""
    for rule in _shipped():
        assert kql.reserved_names(rule.query) == [], rule.name


GLORFINDEL = Path(lf.__file__).resolve().parent


def _kql_strings(root: Path):
    """Each string of the package's code that holds a `|` — a constant, or an f-string its placeholders
    read as `X` — with where it stands: what a query of the code is written with."""
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.JoinedStr):
                text = "".join(v.value if isinstance(v, ast.Constant) else "X" for v in node.values)
            else:
                continue
            if "|" in text:
                yield f"{path.relative_to(root.parent)}:{node.lineno}", text


def test_every_kql_string_of_glorfindel_names_no_word_of_kql():
    """M7761: a query of another module (the audit's) names a column `last` — the guard reads all of
    glorfindel/, not this module alone. What it does not see is said in glorfindel/kql.py (`RESERVED`)."""
    strings = list(_kql_strings(GLORFINDEL))
    assert any("summarize" in text for _, text in strings) and len(strings) > 50      # it reads the queries
    assert any(where.startswith("glorfindel/audit.py:") for where, _ in strings)
    assert [(where, kql.reserved_names(text)) for where, text in strings if kql.reserved_names(text)] == []


# The answer of Log Analytics to a query it cannot parse, as azure-core reads it (its form; the
# correlation id a fake one, never a real workspace's).
_AZURE_400 = {"error": {
    "message": "The request had some invalid properties", "code": "BadArgumentError", "correlationId": WS_ID,
    "innererror": {"code": "SyntaxError", "message": "A recognition error occurred in the query.",
                   "innererror": {"code": "SYN0002", "message": "Query could not be parsed at 'last' on line [3,13]",
                                  "line": 3, "pos": 13, "token": "last"}}}}
SAID_400 = ("HTTP 400 — SYN0002: Query could not be parsed at 'last' on line [3,13] — "
            "(BadArgumentError) The request had some invalid properties")


class _Response:
    """What azure-core reads of an HTTP answer to make its HttpResponseError."""

    def __init__(self, status, body):
        self.status_code, self.reason, self._body = status, "Bad Request", body
        self.headers, self.request = {}, None

    def text(self, encoding=None):
        return json.dumps(self._body)

    def body(self):
        return self.text().encode()


def _http_response_error(body, status=400):
    return HttpResponseError(response=_Response(status, body))


def test_short_error_says_the_deepest_inner_error_of_an_azure_answer(tmp_path):
    """M7753: the inner error lost again — the 400 said « invalid properties », its SyntaxError unsaid."""
    exc = _http_response_error(_AZURE_400)
    assert "Inner error" in str(exc) and exc.error.innererror                 # azure-core's own form
    assert lf.short_error(exc) == SAID_400
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": exc}, tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"]["error"] == SAID_400
    assert _silent_cards() == []                                              # a failure, never « no log »


def test_short_error_reads_the_inner_error_from_the_text_when_the_exception_has_no_error():
    """M7754: an error whose text alone carries « Inner error: {…} » (a wrapper, a re-raise) — said all the same."""
    text = str(_http_response_error(_AZURE_400))
    assert lf.short_error(_HttpError(400, text)) == SAID_400
    assert lf.short_error(_HttpError(400, text.split("Inner error:")[0])) == (
        "HTTP 400 — (BadArgumentError) The request had some invalid properties")
    assert lf.short_error(_HttpError(400, "(X) y\nInner error: {not json")) == "HTTP 400 — (X) y"


def test_the_inner_error_is_masked_cut_and_the_deepest_that_says_something():
    """M7755: the inner error without its mask — a GUID, a URL shown. Cut at INNER_MAX; an empty deepest
    node gives way to its parent."""
    body = json.loads(json.dumps(_AZURE_400))
    deepest = body["error"]["innererror"]["innererror"]
    deepest["message"] = f"Workspace {WS_ID} not found — see https://portal.example/{WS_ID}\nsecond line" + "x" * 300
    said = lf.short_error(_http_response_error(body))
    assert said.startswith("HTTP 400 — SYN0002: Workspace <id> not found — see <url>")
    assert "second line" not in said
    for part in WS_ID.split("-"):
        assert part.lower() not in said.lower()
    body["error"]["innererror"]["innererror"]["message"] = "y" * 400
    inner = lf.short_error(_http_response_error(body)).split(" — ")[1]
    assert inner == ("SYN0002: " + "y" * 400)[:lf.INNER_MAX]
    body["error"]["innererror"]["innererror"] = {"line": 3}
    assert lf.short_error(_http_response_error(body)) == (
        "HTTP 400 — SyntaxError: A recognition error occurred in the query. — "
        "(BadArgumentError) The request had some invalid properties")
