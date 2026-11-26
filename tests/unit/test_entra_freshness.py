"""LOGF2 (#1233): the silence of a table of Entra ID judged by Entra, by Graph; a fallback to 7 days
without the right.

In 0.6.9 `logs_silent` opened on AuditLogs after 26 h without a log — a false alarm: the bench's tenant is
calm, AuditLogs receives a log only when the directory changes. Now the watch reads, on Graph, when Entra's
last event happened (glorfindel/providers/azure/entra_last.py), and opens the card only when Entra has an
event more recent than the last log received, for more than 15 min (glorfindel/entra_freshness.py). Without
the right, or Graph unreadable: the threshold of a table of Entra becomes 7 days, said.

No Azure, no Graph here: a fake Log Analytics reader (test_log_freshness's `_Workspace`), a fake Graph
(`_Entra`), a clock in the test's hand, the cards' store redirected by the conftest. The right, declared in
Terraform (infra/glorfindel-host/watch_audit_log.tf), read from the files; planned against mock providers in
infra/glorfindel-host/tests/watch_audit_log.tftest.hcl.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from glorfindel import entra_freshness as ef
from glorfindel import escalations as esc
from glorfindel import log_freshness as lf
from glorfindel.providers.azure import entra_last as el
from glorfindel.providers.azure import graph as g
from glorfindel.read_budget import ReadBudget

from .test_log_freshness import ENTRA, NOW, _ago, _Clock, _housekeeping, _Workspace

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "infra/glorfindel-host"
AUDIT = [ENTRA[0]]                                  # a rule of Entra ID on AuditLogs


class _Entra:
    """A fake Graph: per collection, Entra's last event (an ISO text), None for an empty list, or an
    exception it raises; each read kept."""

    def __init__(self, events: dict):
        self.events = events
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, path, params=None, deadline=None):
        self.calls.append((path, params))
        value = self.events.get(path)
        if isinstance(value, BaseException):
            raise value
        if value == "no-list":
            return {"value": "x"}
        field = "activityDateTime" if "directoryAudits" in path else "createdDateTime"
        return {"value": [] if value is None else [{"id": "x", field: value}]}

    def list(self, path, params=None, deadline=None):           # never: a $top=1 is never followed
        raise AssertionError("the freshness never lists a collection")


DIR = "/auditLogs/directoryAudits"
SIGNINS = "/auditLogs/signIns"
FORBIDDEN = g.Unreadable("droit absent sur Graph (403 Authorization_RequestDenied)", "right", status=403,
                         code="Authorization_RequestDenied")


def _fresh(rules, tables, graph, tmp_path, clock=None, budget=None, said=None):
    ws = _Workspace(tables)
    f = lf.Freshness(rules, client_for=lambda _ws: ws, budget=ReadBudget("LA", "LA_TEST_UNSET", 0),
                     clock=clock or _Clock(), path=tmp_path / "log_freshness.json",
                     say=(said.append if said is not None else None), environ={}, graph=graph,
                     graph_budget=budget or ReadBudget("Graph", "GRAPH_TEST_UNSET", 0))
    return f, ws


def _cards() -> list[dict]:
    return [e for e in esc.pending() if e.get("escalation_type") == lf.TYPE]


def _iso(hours: float) -> str:
    return _ago(hours)


# ── 1. The read on Graph: fixed, $top=1, newest first, read only ──────────────────────────────────

def test_the_graph_requests_are_fixed_top_1_newest_first():
    """M7849, M7850: always `$top=1`, newest first — on the collection of each table."""
    assert el.request("AuditLogs") == (DIR, {"$top": "1", "$orderby": "activityDateTime desc"}, "activityDateTime")
    assert el.request("SigninLogs") == (SIGNINS, {"$top": "1", "$orderby": "createdDateTime desc"},
                                        "createdDateTime")
    assert el.request("AzureActivity") is None and el.request("AADServicePrincipalSignInLogs") is None


def test_the_request_goes_to_graph_v1_with_exactly_those_parameters():
    """The URL and the parameters as GraphReader sends them: a GET on Graph v1.0, nothing else."""
    sent = []

    class _Resp:
        status_code = 200

        def json(self):
            return {"value": [{"activityDateTime": "2026-11-25T08:14:00Z"}], "@odata.nextLink": f"{g.GRAPH}/next"}

    class _Session:
        def get(self, url, **kw):
            sent.append((url, kw["params"], kw["allow_redirects"]))
            return _Resp()

    class _Cred:
        def get_token(self, scope):
            return type("T", (), {"token": "t"})()

    out = el.last_event(g.GraphReader(credential=_Cred(), session=_Session()), "AuditLogs")
    assert out == {"last": "2026-11-25T08:14:00+00:00", "error": None}
    assert sent == [(f"{g.GRAPH}/auditLogs/directoryAudits", {"$top": "1", "$orderby": "activityDateTime desc"},
                     False)]                                     # one page: its next link never followed


def test_what_a_read_answers_a_failure_never_nothing():
    """M7851: a 403 (the right missing) is said, never taken for « Entra has nothing »; nor an answer of
    another form; an empty list is « nothing »."""
    assert el.last_event(_Entra({DIR: None}), "AuditLogs") == {"last": None, "error": None}
    said = el.last_event(_Entra({DIR: FORBIDDEN}), "AuditLogs")
    assert said["last"] is None and said["error"].startswith(
        "no right on Graph (HTTP 403 Authorization_RequestDenied: AuditLog.Read.All missing"), said
    assert "droit" not in said["error"]                          # English, never Graph's or graph.py's text
    assert el.last_event(_Entra({DIR: g.Unreadable("x", "delay")}), "AuditLogs")["error"] == "Graph did not answer in time"
    assert el.last_event(_Entra({DIR: g.Unreadable("x", "error", status=503)}), "AuditLogs")["error"] == \
        "Graph answered HTTP 503"
    assert el.last_event(_Entra({DIR: RuntimeError("bug")}), "AuditLogs")["error"] == "Graph: RuntimeError"
    assert el.last_event(_Entra({DIR: "no-list"}), "AuditLogs")["error"].startswith("Graph's answer unreadable")
    assert el.last_event(_Entra({DIR: "not a date"}), "AuditLogs")["error"] == \
        "Graph's answer unreadable (no activityDateTime)"
    assert el.last_event(g.NoGraph("tests"), "AuditLogs")["error"].startswith("Graph not read")


def test_a_table_with_no_equivalent_on_graph_v1_is_said_never_read():
    """The service principals' sign-ins: on Graph's beta only — never read, never « nothing »."""
    entra = _Entra({})
    out = el.last_event(entra, "AADServicePrincipalSignInLogs")
    assert out == {"last": None, "error": el.NO_EQUIVALENT["AADServicePrincipalSignInLogs"]} and entra.calls == []
    assert "beta" in out["error"]


def test_the_module_only_ever_gets():
    src = (ROOT / "glorfindel/providers/azure/entra_last.py").read_text(encoding="utf-8")
    assert not re.search(r"\.(post|patch|put|delete)\(", src) and "import azure" not in src


# ── 2. The rule: the card opens only when Entra has more recent, for more than 15 min ───────────────

def test_the_card_opens_when_entra_has_an_event_not_received_after_15_min(tmp_path):
    """M7852, M7853: Entra's event 2 h ago, the workspace's last log 26 h ago — lost: one card, both dates."""
    entra = _Entra({DIR: _iso(2)})
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(26)}, entra, tmp_path)
    doc = f.pass_once()
    cards = _cards()
    assert len(cards) == 1, cards
    reason = cards[0]["reason"]
    assert f"its last log arrived at {_iso(26)[:16].replace('T', ' ')} UTC" in reason
    assert f"Entra ID's last event at {_iso(2)[:16].replace('T', ' ')} UTC" in reason
    assert "not received after 15 min" in reason
    t = doc["tables"]["AuditLogs"]
    assert t["judged"] == "entra" and t["silent"] is True and t["entra_last"] == _iso(2)
    assert entra.calls == [(DIR, {"$top": "1", "$orderby": "activityDateTime desc"})]


def test_an_event_within_the_ingestion_s_delay_is_never_a_card(tmp_path):
    """M7853: 10 min ago, still on its way."""
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(26)}, _Entra({DIR: _iso(10 / 60)}), tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"]["silent"] is False and _cards() == []
    assert ef.INGEST_DELAY_S == 900.0


def test_a_calm_tenant_is_never_an_alert(tmp_path):
    """The bench of 0.6.9: 26 h without a log, and Entra's last event older than it — received. And a card
    opened before closes once the log arrives."""
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(26)}, _Entra({DIR: _iso(26.1)}), tmp_path)
    t = f.pass_once()["tables"]["AuditLogs"]
    assert t["judged"] == "entra" and t["silent"] is False and _cards() == []


def test_the_card_closes_when_the_event_arrives(tmp_path):
    clock = _Clock()
    entra = _Entra({DIR: _iso(2)})
    f, ws = _fresh(AUDIT, {"AuditLogs": _iso(26)}, entra, tmp_path, clock=clock)
    f.pass_once()
    card = _cards()[0]["id"]
    ws.tables["AuditLogs"] = _iso(1.5)
    clock.t = NOW + lf.EVERY_S
    f.pass_once()
    assert _cards() == [] and next(e for e in esc.all_escalations() if e["id"] == card)["resolution"] == lf.BACK


def test_entra_with_nothing_is_never_a_card(tmp_path):
    """M7854: an empty list — Entra has no event; the workspace none in its window: no card."""
    f, _ = _fresh(AUDIT, {"AuditLogs": None}, _Entra({DIR: None}), tmp_path)
    t = f.pass_once()["tables"]["AuditLogs"]
    assert t["judged"] == "entra" and t["entra_last"] is None and t["silent"] is False and _cards() == []


def test_no_log_in_the_window_judged_by_the_window_s_start(tmp_path):
    """No log in the 14 days read: an event of Entra in them is lost; one older than them says nothing."""
    f, _ = _fresh(AUDIT, {"AuditLogs": None}, _Entra({DIR: _iso(24 * 15)}), tmp_path)
    assert f.pass_once()["tables"]["AuditLogs"]["silent"] is False
    (tmp_path / "b").mkdir()
    f2, _ = _fresh(AUDIT, {"AuditLogs": None}, _Entra({DIR: _iso(24 * 3)}), tmp_path / "b")
    assert f2.pass_once()["tables"]["AuditLogs"]["silent"] is True and len(_cards()) == 1


def test_a_table_of_entra_is_read_over_14_days(tmp_path):
    """M7858: the comparison needs the last log received even after days of calm — twice the fallback."""
    f, ws = _fresh(ENTRA, {"AuditLogs": _iso(1), "AzureActivity": _iso(1),
                           "AADServicePrincipalSignInLogs": _iso(1)}, _Entra({DIR: _iso(2)}), tmp_path)
    f.pass_once()
    windows = {q.split("\n", 1)[0]: re.search(r"ago\((\d+)h\)", q).group(1) for q, _ in ws.queries}
    assert windows == {"AuditLogs": "336", "AADServicePrincipalSignInLogs": "336", "AzureActivity": "48"}


def test_azure_activity_keeps_its_24_h(tmp_path):
    """The control plane is not judged by Graph (AzureActivity by the Activity Log's API: a later lot)."""
    entra = _Entra({DIR: _iso(30)})
    f, _ = _fresh(ENTRA, {"AuditLogs": _iso(30), "AzureActivity": _iso(26),
                          "AADServicePrincipalSignInLogs": _iso(1)}, entra, tmp_path)
    doc = f.pass_once()
    assert "judged" not in doc["tables"]["AzureActivity"]
    assert [c["reason"].split(" receives")[0] for c in _cards()] == ["Logs silent: the table AzureActivity"]
    assert "threshold 24 h" in _cards()[0]["reason"]


# ── 3. The fallback to 7 days: a 403, Graph unreadable, no equivalent ───────────────────────────────

@pytest.mark.parametrize("failure", [FORBIDDEN, g.Unreadable("x", "delay"), g.Unreadable("x", "error", status=500),
                                     RuntimeError("bug"), "no-list"])
def test_without_graph_the_threshold_of_entra_is_7_days(tmp_path, failure):
    """M7855, M7856: 26 h without a log — no card (before LOGF2: one); 8 days — one, said."""
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(26)}, _Entra({DIR: failure}), tmp_path)
    t = f.pass_once()["tables"]["AuditLogs"]
    assert t["judged"] == "fallback" and t["silent"] is False and t["threshold_hours"] == 168.0, t
    assert t["graph_error"] and _cards() == []
    (tmp_path / "old").mkdir()
    old, _ = _fresh(AUDIT, {"AuditLogs": _iso(24 * 8)}, _Entra({DIR: failure}), tmp_path / "old")
    assert old.pass_once()["tables"]["AuditLogs"]["silent"] is True
    reason = _cards()[0]["reason"]
    assert "threshold 7 days: Graph unread — " in reason and t["graph_error"] in reason
    assert ef.FALLBACK_H == 168.0


def test_a_table_with_no_equivalent_falls_back_and_says_why(tmp_path):
    entra = _Entra({})
    f, _ = _fresh(ENTRA[1:2], {"AADServicePrincipalSignInLogs": _iso(30)}, entra, tmp_path)
    t = f.pass_once()["tables"]["AADServicePrincipalSignInLogs"]
    assert t["judged"] == "fallback" and t["silent"] is False and "beta" in t["graph_error"] and entra.calls == []


def test_a_graph_failure_is_said_once_in_the_watch_s_log(tmp_path):
    said: list[str] = []
    clock = _Clock()
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(1)}, _Entra({DIR: FORBIDDEN}), tmp_path, clock=clock, said=said)
    f.pass_once()
    clock.t = NOW + lf.EVERY_S
    f.pass_once()
    lines = [x for x in said if "not read on Graph" in x]
    assert len(lines) == 1 and "AuditLogs" in lines[0] and "threshold 7 days" in lines[0], said


def test_a_card_opened_by_the_comparison_is_not_closed_by_a_403(tmp_path):
    """M7859: Entra's event lost, then the right removed — the workspace still without it: the card stays;
    once a log as recent arrives, it closes."""
    clock = _Clock()
    entra = _Entra({DIR: _iso(2)})
    f, ws = _fresh(AUDIT, {"AuditLogs": _iso(26)}, entra, tmp_path, clock=clock)
    f.pass_once()
    assert len(_cards()) == 1
    entra.events[DIR] = FORBIDDEN
    clock.t = NOW + lf.EVERY_S
    f.pass_once()
    assert len(_cards()) == 1
    ws.tables["AuditLogs"] = _iso(1)
    clock.t = NOW + 2 * lf.EVERY_S
    f.pass_once()
    assert _cards() == []


# ── 4. The budget of Graph's reads ─────────────────────────────────────────────────────────────────

def test_each_read_of_graph_is_taken_on_its_budget_and_put_off_when_held(tmp_path):
    """M7857: one `take` per read, by `freshness`; held, put off a minute, its last value kept, the
    fallback said meanwhile (« not read yet »), never « nothing »."""
    clock = _Clock()
    budget = ReadBudget("Graph", "GRAPH_TEST_CAP", 1, clock=clock)
    budget.spend(1, "other")                               # the minute already taken
    entra = _Entra({DIR: _iso(2)})
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(26)}, entra, tmp_path, clock=clock, budget=budget)
    t = f.pass_once()["tables"]["AuditLogs"]
    assert entra.calls == [] and t["judged"] == "fallback" and t["graph_error"] == ef.DEFERRED
    assert f.has_work(NOW + ef.RETRY_S) and not f.has_work(NOW + 1)
    clock.t = NOW + ef.RETRY_S
    t = f.pass_once()["tables"]["AuditLogs"]
    assert len(entra.calls) == 1 and t["judged"] == "entra" and budget.used() == {"freshness": 1}


def test_graph_s_budget_is_its_own():
    from glorfindel import read_budget as rb
    assert rb.GRAPH.env == "GLORFINDEL_GRAPH_BUDGET_PER_MIN" and rb.GRAPH.default == 30
    assert rb.GRAPH is not rb.LOG_ANALYTICS and rb.GRAPH is not rb.ARM


def test_graph_is_read_every_15_min_and_its_reads_survive_a_restart(tmp_path):
    clock = _Clock()
    entra = _Entra({DIR: _iso(2)})
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(1)}, entra, tmp_path, clock=clock)
    f.pass_once()
    again, _ = _fresh(AUDIT, {"AuditLogs": _iso(1)}, entra, tmp_path, clock=clock)
    assert not again.has_work(NOW + 60)
    assert again.has_work(NOW + ef.EVERY_S)
    assert json.loads((tmp_path / "log_freshness.json").read_text())["graph"]["AuditLogs"]["last"] == _iso(2)


# ── 5. The console's field, the watch's wiring ─────────────────────────────────────────────────────

def test_the_console_s_field_carries_the_verdict_read_strictly(tmp_path):
    """M7860: LOGF2's keys in `/api/watch/status`, each checked — a `judged` of another value drops the
    field."""
    f, _ = _fresh(AUDIT, {"AuditLogs": _iso(26)}, _Entra({DIR: FORBIDDEN}), tmp_path)
    f.pass_once()
    path = tmp_path / "log_freshness.json"
    t = lf.console_field(path)["log_freshness"]["tables"]["AuditLogs"]
    assert {k: t[k] for k in ("judged", "silent", "threshold_hours")} == {"judged": "fallback", "silent": False,
                                                                        "threshold_hours": 168.0}
    assert t["graph_error"].startswith("no right on Graph")
    for bad in ({"judged": "maybe"}, {"silent": "no"}, {"threshold_hours": True}, {"entra_last": "x"},
                {"graph_error": 3}):
        doc = json.loads(path.read_text())
        doc["tables"]["AuditLogs"].update(bad)
        (tmp_path / "bad.json").write_text(json.dumps(doc))
        assert lf.console_field(tmp_path / "bad.json") == {}, bad


def test_the_watch_judges_entra_with_its_own_reader_of_graph(monkeypatch, tmp_path):
    """The watch hands its reader of Graph (the conftest's NoGraph: Graph never read in a test) — the
    tables of Entra judged by Graph, here on the fallback."""
    monkeypatch.setenv("HOME", str(tmp_path))
    ws = _Workspace({"AuditLogs": _iso(1)})
    monkeypatch.setattr(lf, "_default_client", lambda _ws: ws)
    hk, _ = _housekeeping(monkeypatch)
    hk.follow_logs(AUDIT)
    hk._log_freshness()
    hk._freshness_thread._thread.join(timeout=10)
    t = json.loads(lf.state_file().read_text())["tables"]["AuditLogs"]
    assert t["judged"] == "fallback" and t["graph_error"].startswith("Graph not read"), t


def test_without_a_reader_logf1_s_threshold_for_every_table(tmp_path):
    """`graph=None` (LOGF1's tests): no Graph, 24 h for AuditLogs, no LOGF2 key."""
    ws = _Workspace({"AuditLogs": _iso(26)})
    f = lf.Freshness(AUDIT, client_for=lambda _ws: ws, budget=ReadBudget("LA", "LA_TEST_UNSET", 0),
                     clock=_Clock(), path=tmp_path / "log_freshness.json", environ={})
    t = f.pass_once()["tables"]["AuditLogs"]
    assert "judged" not in t and len(_cards()) == 1


# ── 6. The right, declared in Terraform (infra/glorfindel-host/watch_audit_log.tf) ─────────────────

def _tf() -> str:
    return (HOST / "watch_audit_log.tf").read_text(encoding="utf-8")


def test_the_right_is_audit_log_read_all_alone_behind_its_flag_to_the_vm_s_identity():
    tf = _tf()
    local = re.search(r"watch_audit_log_permissions\s*=\s*var\.watch_audit_log_read_enabled \? "
                      r"toset\(\[([^\]]*)\]\) : toset\(\[\]\)", tf)
    assert local and set(re.findall(r'"([^"]+)"', local.group(1))) == {el.RIGHT}
    assert "principal_object_id = azurerm_linux_virtual_machine.host.identity[0].principal_id" in tf
    assert set(re.findall(r'resource "(\w+)"', tf)) == {"azuread_app_role_assignment"}
    variables = (HOST / "variables.tf").read_text(encoding="utf-8")
    block = variables.split('variable "watch_audit_log_read_enabled"')[1].split("\n}\n")[0]
    assert "default     = false" in block
    for kind, name in re.findall(r'(?:resource|data) "(\w+)" "(\w+)" \{', tf):
        body = tf.split(f'"{kind}" "{name}" {{')[1].split("\n}\n")[0]
        assert ("count" in body and "var.watch_audit_log_read_enabled" in body) or \
            "for_each            = local.watch_audit_log_permissions" in body, (kind, name)


def test_its_tfvars_stay_off_the_repository_and_its_example_does_not():
    import subprocess
    if not (ROOT / ".git").exists():
        pytest.skip("outside a checkout (the mutants' copy): git cannot say what it ignores")

    def ignored(rel):
        return subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT).returncode == 0
    assert ignored("infra/glorfindel-host/watch_audit_log.auto.tfvars")
    assert not ignored("infra/glorfindel-host/watch_audit_log.auto.tfvars.example")
