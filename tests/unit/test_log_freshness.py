"""LOGF1 (#1183): the watch says whether the workspace's logs still arrive.

A diagnostic setting cut on the tenant or the subscription, and the rules of Entra ID and of the control
plane keep polling, without an error, on empty tables. The watch now reads, for each table its rules
read, when its last log arrived (glorfindel/log_freshness.py), writes it for the console
(`/api/watch/status`, `log_freshness`), and says a silence past the threshold on a card `logs_silent`.

No Azure here: a fake Log Analytics reader (`_Workspace`), a clock in the test's hand, the cards' store
redirected by the conftest.
"""
from __future__ import annotations

import io
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from glorfindel import escalations as esc
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
        return [{"last": value}]


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
    """M7618: only the rules enabled and bound to a backend — a rule that cannot poll reads nothing."""
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


def test_a_query_the_parse_cannot_read_falls_back_on_what_its_detector_knows():
    assert lf.table_of(_rule("a", "datatable(a:int)[1]", "azure_activity")) == "AzureActivity"
    q = "datatable(a:int)[1] | join (AADServicePrincipalSignInLogs | take 1) on a | join (AuditLogs) on a"
    assert lf.table_of(_rule("e", q, "azure_entra")) == "AADServicePrincipalSignInLogs"
    assert lf.table_of(_rule("m", "datatable(a:int)[1]")) is None


def test_the_query_is_fixed_by_the_code_and_reads_the_arrival():
    assert lf.query("AuditLogs", 24) == ("AuditLogs\n| where TimeGenerated > ago(24h)\n"
                                         "| summarize last = max(ingestion_time())")
    with pytest.raises(ValueError):
        lf.query("AuditLogs | take 1", 24)


# ── 2. The threshold, read strictly ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,hours,noted", [
    ("", 6.0, False), ("6", 6.0, False), ("12.5", 12.5, False), ("1", 1.0, False), ("168", 168.0, False),
    ("0", 6.0, True), ("-3", 6.0, True), ("nan", 6.0, True), ("inf", 6.0, True), ("six", 6.0, True),
    ("0.5", 6.0, True), ("169", 6.0, True)])
def test_the_threshold_is_read_strictly(raw, hours, noted):
    """M7615: a value that is no finite number of hours in its range is the default, said."""
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
    assert t["AuditLogs"] == {"last": _ago(1), "error": None}
    assert t["AADServicePrincipalSignInLogs"] == {"last": _ago(9), "error": None}
    assert t["AzureActivity"] == {"last": None, "error": None}             # read: no log in the window
    assert t["Perf"] == {"last": None, "error": None}
    assert t["Syslog"] == {"last": None, "error": "HTTP 429 — Too many requests"}
    # the window: twice the threshold, at least a day — the timespan as the query
    q, span = ws.queries[0]
    assert "ago(24h)" in q and span[1] - span[0] == timedelta(hours=24, minutes=1)


@pytest.mark.parametrize("exc,said", [(_HttpError(403, "Forbidden"), "HTTP 403 — Forbidden"),
                                      (ConnectionError("network unreachable"), "ConnectionError — network unreachable"),
                                      (RuntimeError("workspace query not successful: PARTIAL"),
                                       "RuntimeError — workspace query not successful: PARTIAL")])
def test_a_read_that_fails_is_an_error_never_no_log(tmp_path, exc, said):
    """M7611: a 403, the network, a partial answer — `error`, never `last: null` alone."""
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": exc}, tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"] == {"last": None, "error": said}
    assert not esc.pending()                                               # M7612: no card « silent »


def test_a_datetime_from_the_sdk_is_written_as_iso_in_utc(tmp_path):
    dt = datetime(2026, 11, 25, 11, 30, tzinfo=timezone.utc)
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": dt}, tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"]["last"] == "2026-11-25T11:30:00+00:00"


def test_two_workspaces_the_table_is_as_old_as_its_oldest_and_failed_if_one_fails():
    a = {"table": "AuditLogs", "last": _ago(1), "error": None}
    b = {"table": "AuditLogs", "last": _ago(8), "error": None}
    assert lf.merged({"1|A": a, "2|A": b})["AuditLogs"] == {"last": _ago(8), "error": None}
    none = {"table": "AuditLogs", "last": None, "error": None}
    assert lf.merged({"1|A": a, "2|A": none})["AuditLogs"] == {"last": None, "error": None}
    err = {"table": "AuditLogs", "last": None, "error": "HTTP 403"}
    assert lf.merged({"1|A": a, "2|A": err})["AuditLogs"] == {"last": _ago(1), "error": "HTTP 403"}


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
    assert t["AzureActivity"] == {"last": None, "error": lf.DEFERRED}
    assert not esc.pending()                                               # not read: no card
    clock.t = NOW + 30
    budget.spend(3)                                                        # the detection: counted, never refused
    assert budget.used() == {"freshness": 2, "detection": 3}
    clock.t = NOW + lf.RETRY_S
    assert f.due() == [("ws-1", "AzureActivity")]
    f.pass_once()
    assert len(ws.queries) == 2                                            # the minute is still full
    clock.t = NOW + lf.RETRY_S * 2 + 1
    assert f.pass_once()["tables"]["AzureActivity"] == {"last": _ago(1), "error": None}
    assert len(ws.queries) == 3


def test_a_budget_of_zero_has_no_threshold_the_reads_are_counted(tmp_path):
    budget = ReadBudget("Log Analytics", "LA_TEST_UNSET", 0)
    f, ws = _fresh(ENTRA, {}, tmp_path, budget=budget)
    f.pass_once()
    assert len(ws.queries) == 3 and budget.used() == {"freshness": 3}


# ── 5. The file, and the console's field ─────────────────────────────────────────────────────────

def test_the_file_is_written_at_once_and_the_console_reads_its_contract(tmp_path):
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(1)}, tmp_path)
    f.pass_once()
    path = tmp_path / "log_freshness.json"
    assert not list(tmp_path.glob(".log_freshness.json.*"))                # no temp file left
    assert lf.console_field(path) == {"log_freshness": {
        "read_at": datetime.fromtimestamp(NOW, timezone.utc).isoformat(), "silent_after_hours": 6.0,
        "tables": {"AuditLogs": {"last": _ago(1), "error": None}}}}


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
    assert w["log_freshness"]["tables"] == {"AuditLogs": {"last": None, "error": "HTTP 403 — Forbidden"}}
    assert w["log_freshness"]["silent_after_hours"] == 6.0
    assert w["status"] == "stopped" and w["model_breaker"] == 0
    path.write_text("{broken")
    w = client.get("/api/watch/status").json()
    assert "log_freshness" not in w and w["status"] == "stopped"


# ── 6. The card: once an episode and per table, closed when the logs come back ───────────────────

def _silent_cards() -> list[dict]:
    return [e for e in esc.pending() if e.get("escalation_type") == lf.TYPE]


def test_logs_silent_past_the_threshold_make_one_card_an_episode_and_per_table(tmp_path):
    """M7613, M7620: one card per table (two tables never one card), never a second in the episode."""
    clock, said = _Clock(), []
    tables = {"AuditLogs": _ago(7), "AzureActivity": None, "AADServicePrincipalSignInLogs": _ago(5)}
    f, _ = _fresh(ENTRA, tables, tmp_path, clock=clock, said=said)
    f.pass_once()
    cards = _silent_cards()
    assert sorted(c["reason"].split("la table ")[1].split(" ")[0] for c in cards) == ["AuditLogs", "AzureActivity"]
    assert all(c["resource_id"] == "" and c["action"] == "" for c in cards)  # the watch's (MBV1)
    assert not esc.is_decision(cards[0]) and lf.TYPE in esc._NOT_DECISIONS
    assert any("aucun journal arrivé dans les 24 dernières heures" in c["reason"] for c in cards)
    for step in (lf.EVERY_S, 2 * lf.EVERY_S):                              # still silent: no other card
        clock.t = NOW + step
        f.pass_once()
    assert len(_silent_cards()) == 2
    assert sum("journaux muets" in s for s in said) == 2


def test_the_card_closes_when_the_logs_come_back_and_a_new_episode_makes_a_new_card(tmp_path):
    """M7614: the logs back, the card closed by the watch; silent again, a new card."""
    clock, said = _Clock(), []
    f, ws = _fresh(ENTRA[:1], {"AuditLogs": _ago(7)}, tmp_path, clock=clock, said=said)
    f.pass_once()
    first = _silent_cards()[0]["id"]
    clock.t = NOW + lf.EVERY_S
    ws.tables["AuditLogs"] = datetime.fromtimestamp(clock.t - 60, timezone.utc).isoformat()
    f.pass_once()
    assert _silent_cards() == []
    closed = next(e for e in esc.all_escalations() if e["id"] == first)
    assert closed["status"] == "resolved" and closed["resolution"] == "journaux revenus (LOGF1)"
    assert any(s.startswith("journaux revenus : AuditLogs") for s in said)
    clock.t = NOW + 2 * lf.EVERY_S + 7 * 3600
    f.pass_once()
    assert [c["id"] for c in _silent_cards()] != [first] and len(_silent_cards()) == 1


def test_a_failed_read_neither_opens_nor_closes_a_card_and_is_said_once(tmp_path):
    """M7612: a read in error is unknown — no card « silent »; an open one stays; said once in the log."""
    clock, said = _Clock(), []
    f, ws = _fresh(ENTRA[:1], {"AuditLogs": _ago(7)}, tmp_path, clock=clock, said=said)
    f.pass_once()
    assert len(_silent_cards()) == 1
    ws.tables["AuditLogs"] = _HttpError(403, "Forbidden")
    for step in (1, 2, 3):
        clock.t = NOW + step * lf.EVERY_S
        f.pass_once()
    assert len(_silent_cards()) == 1                                       # neither closed nor another
    assert sum("en échec" in s for s in said) == 1


def test_a_restart_of_the_watch_in_an_episode_makes_no_second_card_nor_one_after_an_ack(tmp_path):
    clock = _Clock()
    f, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(7)}, tmp_path, clock=clock)
    f.pass_once()
    card = _silent_cards()[0]["id"]
    esc.resolve(card, note="ack")                                          # the operator's Ack
    clock.t = NOW + lf.EVERY_S
    again, _ = _fresh(ENTRA[:1], {"AuditLogs": _ago(7)}, tmp_path, clock=clock)
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
    assert "fraîcheur des journaux en erreur" in buf.getvalue()
