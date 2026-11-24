"""DOS4 (#1138; `docs/design/dossier-isolation.md` §3.2, §3.3, §3.6, §4.5, §7, §12): the dossier's reads of Azure
— read on the fake Azure (tests/unit/fake_azure.py), never on Azure; no model.

The property of the lot, held at each source: a read that fails, is refused, cut past its bound, or answers
in a shape ARM does not document is unreadable, never empty. Its window is anchored on the signal's hour,
never on the read's. Never a read for a detection attributed to no VM. The reads draw on the budget they
take from their own ARM budget, never from the detection's (`tests/unit/test_read_budget.py`), and the
message to the model is unchanged. Mutants M7290–M7309 and M7338–M7349 (`scripts/mutants/DOS4.py`). The shapes of the fake follow the
documentation, unmeasured (DH1, DH2, DH3, DH4, DH7).
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from glorfindel import dossier, dossier_pass, read_budget
from glorfindel.enquiry import catalog
from glorfindel.enquiry.platform import PLATFORM_READS
from glorfindel.providers.azure.connector import AzureConnector

from .fake_azure import FakeAzure

T = datetime(2026, 11, 10, 2, 35, 56, tzinfo=timezone.utc)
ME = "55555555-5555-5555-5555-555555555555"          # Glorfindel's identity on Azure
THIRD = "11111111-1111-1111-1111-111111111111"
EXT = "Microsoft.Compute/virtualMachines/extensions/write"
OS_WRITE = "OS Disk Write Bytes/sec"


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for var in ("GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "EREGION_REF", "EREGION_REVISION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AZURE_CLIENT_ID", ME)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)
    for env in ("GLORFINDEL_ARM_BUDGET_PER_MIN", "GLORFINDEL_LA_BUDGET_PER_MIN"):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("GLORFINDEL_BACKUP_VAULT", "rsv-bench")


class World:
    """bree's night in miniature: a VM of the bench, its vault, its log, its host's metrics, its health."""

    def __init__(self, at: datetime = T + timedelta(minutes=40)):
        self.now = at
        self.f = f = FakeAzure()
        f.clock = lambda: self.now
        f.caller = ME
        sub = f.add_subnet("rg-bench", "vnet", "app", None)
        self.vm = f.add_vm("rg-bench", "vm-dos4", [{"rg": "rg-bench", "name": "vm-dos4-nic", "ips": ["10.0.1.4"],
                                                   "subnet": sub, "nsg": None}])
        self.c = c = AzureConnector(dry_run=False, read_only=True)
        c._network, c._compute, c._rest, c._backup = f.network, f.compute, f.rest, f.backup
        c._subscription_id = "s"
        f.health[self.vm.lower()] = {"properties": {"availabilityState": "Available", "reasonType": "",
                                                    "occuredTime": T.isoformat()}}

    def bree(self) -> "World":
        """The backup 2 min 37 s before the signal, an extension written by the backup service, the
        isolation's rule and drain by Glorfindel, the host's writes."""
        self.f.backup_job(self.vm, T - timedelta(seconds=157), T + timedelta(minutes=20))
        self.f.backup_job(self.vm, T - timedelta(days=1, seconds=157), T - timedelta(days=1) + timedelta(minutes=20))
        self.f.log(self.vm + "/extensions/VMSnapshotLinux", EXT, caller=THIRD, at=T - timedelta(seconds=150))
        self.f.log(self.vm, "Microsoft.Compute/virtualMachines/runCommand/action", caller=ME,
                   at=T + timedelta(seconds=26), lasts_s=434)
        self.f.log(self.vm + "/extensions/AzureMonitorLinuxAgent", EXT, caller=THIRD, at=T + timedelta(seconds=60))
        for m, avg in ((-1, 11.1e6), (0, 9.4e6), (1, 2e6)):
            self.f.metric(self.vm, OS_WRITE, (T + timedelta(minutes=m)).replace(second=0), avg, avg * 3)
        return self

    def reads(self, **kw):
        return self.c.dossier_reads(self.vm, T, vault="rsv-bench", vault_rg="rg-bench", now=self.now, **kw)


def _state(vm: str, **ctx) -> dict:
    signal = {"signal_id": "rule-ransomware-disk-write-0000dos4", "event": "detection", "ttp": "T1486",
              "severity": "high", "resource_id": vm, "resource_type": "vm",
              "timestamp": (T + timedelta(seconds=14)).isoformat(),
              "context": {"rule_name": "ransomware-disk-write", "attribution": "asset",
                          "run_id": "watch-ransomware-disk-write-20261110T023610Z", **ctx},
              "raw_signal": {"first_result_row": {"_ResourceId": vm, "MaxWrite": 65900000, "TimeGenerated": T.isoformat()},
                             "investigative_context": {"top_write_processes": [], "backup_agent_check": [],
                                                       "heartbeat_gap": []}}}
    return {"signal": signal, "dry_run": False, "action": "isolate_vm", "escalate": True, "mode_hold": True,
            "confidence": 0.8, "autonomy_mode": "human_only", "escalation_reason": "Mode human_only",
            "outcome": {"status": "escalated", "executed": False, "action_pending": "isolate_vm"}}


def _dossier(w: World, source: str = "real", **ctx):
    name = dossier.at_cycle_end(_state(w.vm, **ctx), True, source, "", now=T.timestamp() + 60)
    assert name
    return dossier.DOSSIER_DIR / name


def _doc(path) -> dict:
    return json.loads(path.read_text())


def _facts(path) -> dict:
    return {(f["code"], f["id"]): f for f in _doc(path)["faits"]}


def _budget() -> read_budget.ReadBudget:
    """An ARM budget of its own, at its default (60 a minute)."""
    return read_budget.ReadBudget("ARM", "GLORFINDEL_ARM_BUDGET_PER_MIN", 60, floor=read_budget.MINIMUM)


# ── The five reads, each anchored on T, each bounded ────────────────────────────────────────────────

def test_a_vm_read_whole_gives_its_facts_with_their_source_author_and_measure():
    w = World().bree()
    readings, calls = w.reads()
    assert {i: r.etat for i, r in readings.items()} == {i: catalog.LIGNES for i in PLATFORM_READS}
    assert calls == 7
    path = _dossier(w)
    assert dossier_pass.reads_pass(w.c, now=w.now, budget=_budget()) == [
        {"vm": "vm-dos4", "dossier": path.name, "etape": "1", "issue": "lu"}]
    facts, doc = _facts(path), _doc(path)
    job = facts[("F1a", "backup_job")]
    assert job["etat"] == "lu" and job["etat_lecture"] == "lignes" and job["auteur"] == "plateforme"
    assert job["valeurs"]["liste"][0]["ecart_s"] == -157 and "(-157 s de T)" in job["dit"]
    assert len(job["valeurs"]["sauvegardes_10j"]) == 2 and job["mesure"] == "à mesurer (DH2)"
    assert facts[("F1b", "extensions_log")]["etat"] == "lu"
    assert facts[("F1c", "reboot")]["etat"] == "vide"
    assert facts[("F1d", "availability")]["dit"].startswith("disponibilité selon Azure : Available")
    assert facts[("F1d", "service_health")]["etat"] == "sans_objet"
    assert facts[("F2", "host_metric")]["valeurs"]["nombre"] == 3
    own = facts[("F5a", "own_operations")]
    # M7309: Glorfindel's alone — a third party's extension after T is not its gesture.
    assert own["etat"] == "lu" and own["valeurs"]["nombre"] == 1
    assert own["valeurs"]["liste"][0]["duree_s"] == 434                                 # bree's drain: 7 min 14 s
    assert facts[("F1b", "extensions_view")]["auteur"] == catalog.GUEST_PROVOCABLE
    assert doc["lectures"]["etat"] == "faites" and doc["etape"] == 1 and doc["lectures"]["appels"] == 7


def test_the_window_is_anchored_on_the_signal_never_on_the_read():
    """M7290: the window anchored on the moment of the read — read two hours after T, the reads look at
    the two hours after, and bree's backup and extension are gone."""
    w = World(at=T + timedelta(hours=2)).bree()
    readings, _ = w.reads()
    assert readings["backup_jobs"].etat == catalog.LIGNES and readings["activity_window"].etat == catalog.LIGNES
    filters = [p["$filter"] for u, p in w.f.rest_calls if "eventtypes" in u]
    assert all("eventTimestamp ge '2026-11-10T02:05:56Z' and eventTimestamp le '2026-11-10T03:05:56Z'" in x
               for x in filters) and len(filters) == 2
    metrics = next(p for u, p in w.f.rest_calls if u.endswith("/metrics"))
    assert metrics["timespan"] == "2026-11-10T02:30:56Z/2026-11-10T02:38:56Z" and metrics["interval"] == "PT1M"


def test_a_window_still_open_is_read_up_to_now_and_says_it():
    w = World(at=T + timedelta(minutes=8)).bree()
    readings, _ = w.reads()
    end = next(p for u, p in w.f.rest_calls if "eventtypes" in u)["$filter"]
    assert "eventTimestamp le '2026-11-10T02:43:56Z'" in end
    assert readings["activity_window"].etat == catalog.LIGNES


def _fails(w: World, read_id: str) -> None:
    f = w.f
    if read_id == "activity_window":
        f.rest_denied.add("eventtypes")
    elif read_id == "host_metrics":
        f.rest_denied.add("/metrics")
    elif read_id == "resource_health":
        f.rest_denied.add("resourcehealth")
    else:
        op = {"backup_jobs": "backup.jobs", "instance_view": "vm.instance_view"}[read_id]

        def chaos(name, phase, write):
            if name == op:
                raise RuntimeError("HTTP 429 TooManyRequests")
        f.chaos = chaos


@pytest.mark.parametrize("read_id", list(PLATFORM_READS))
def test_a_read_that_fails_is_unreadable_never_empty(read_id):
    """M7291: a read that fails said empty — « no backup job », « no gesture » where nothing was read."""
    w = World().bree()
    _fails(w, read_id)
    readings, _ = w.reads()
    assert readings[read_id].etat == catalog.ECHEC and readings[read_id].why
    assert all(r.etat == catalog.LIGNES for i, r in readings.items() if i != read_id)
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    drawn = [f for f in _doc(path)["faits"] if f.get("etat_lecture") == "echec"]
    assert drawn and all(f["etat"] == "illisible" and f["pourquoi"] for f in drawn)


def test_a_cut_activity_log_is_unreadable_never_complete_and_its_pages_counted():
    """M7292: the bound of the activity log's pages removed — 30 pages read as « all of it ». M7342: a read
    that fails counted one call — the 20 pages read before the cut spent unseen."""
    w = World().bree()
    w.f.page_size = 1
    for i in range(30):
        w.f.log(w.vm + f"/extensions/x{i}", EXT, ("Succeeded",), caller=THIRD, at=T - timedelta(seconds=i))
    readings, calls = w.reads(only=["activity_window"])
    assert readings["activity_window"].etat == catalog.ECHEC and "pages" in readings["activity_window"].why
    assert calls == len(w.f.rest_calls) and calls > 20          # the exact read, then 20 pages of the group


def test_an_instance_view_that_fails_counts_its_two_calls():
    """M7342: the instance view failing on its second call counted one."""
    w = World()

    def chaos(name, phase, write):
        if name == "vm.instance_view":
            raise RuntimeError("HTTP 429 TooManyRequests")
    w.f.chaos = chaos
    readings, calls = w.reads(only=["instance_view"])
    assert readings["instance_view"].etat == catalog.ECHEC and calls == 2


def test_the_vault_s_pages_are_each_counted():
    """M7343: the SDK's pages of the vault's listing counted as one call."""
    w = World().bree()
    real = w.f.backup.backup_jobs

    class Pager:
        def __init__(self, items):
            self.items = items

        def by_page(self):
            return iter([self.items[:1], self.items[1:2], self.items[2:]])

    class Jobs:
        def list(self, vault, rg, filter=None):
            return Pager(list(real.list(vault, rg)) + [])
    w.c._backup = type("B", (), {"backup_jobs": Jobs()})()
    readings, calls = w.reads(only=["backup_jobs"])
    assert readings["backup_jobs"].etat == catalog.LIGNES and calls == 3


def test_a_dry_run_connector_reads_nothing_and_refuses_every_read():
    c = AzureConnector(dry_run=True, read_only=True)
    readings, calls = c.dossier_reads("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/"
                                      "virtualMachines/vm", T, vault="rsv", now=T + timedelta(minutes=40))
    assert set(readings) == set(PLATFORM_READS) and calls == 0
    assert {r.etat for r in readings.values()} == {catalog.REFUSEE}
    assert all(r.why == "dry run : rien n'est lu" for r in readings.values())


def test_a_metrics_answer_of_another_shape_is_unreadable():
    """M7293: an answer of the metrics' API that is not the documented list read as « no point »."""
    w = World().bree()
    w.f.metrics_body = {"value": [{"name": {"value": OS_WRITE}, "timeseries": "rien"}]}
    assert w.reads(only=["host_metrics"])[0]["host_metrics"].etat == catalog.ECHEC
    w.f.metrics_body = {"error": "x"}
    assert w.reads(only=["host_metrics"])[0]["host_metrics"].etat == catalog.ECHEC


def test_a_health_answer_without_its_state_is_unreadable():
    """M7294: Resource Health answering without `availabilityState`, read as a state."""
    w = World()
    w.f.health[w.vm.lower()] = {"properties": {"summary": "?"}}
    assert w.reads(only=["resource_health"])[0]["resource_health"].etat == catalog.ECHEC


def test_a_vault_past_its_bound_is_unreadable(monkeypatch):
    """M7295: the bound of the vault's listing removed — a vault longer than it read as whole."""
    from glorfindel.providers.azure import dossier_reads
    w = World().bree()
    monkeypatch.setattr(dossier_reads, "JOBS_MAX", 1)
    assert w.reads(only=["backup_jobs"])[0]["backup_jobs"].etat == catalog.ECHEC


def test_a_homonyms_job_in_another_group_is_not_this_vms():
    w = World()
    other = w.f.add_vm("rg-other", "vm-dos4", [{"rg": "rg-other", "name": "n2", "ips": ["10.0.2.4"],
                                                "subnet": w.f.add_subnet("rg-other", "v2", "a", None), "nsg": None}])
    w.f.backup_job(other, T - timedelta(seconds=60))
    reading = w.reads(only=["backup_jobs"])[0]["backup_jobs"]
    assert reading.etat == catalog.VIDE and reading.rows == []


def test_an_empty_answer_before_its_latency_is_waiting_never_empty():
    w = World(at=T + timedelta(minutes=2))
    readings, _ = w.reads(only=["host_metrics", "backup_jobs"])
    assert readings["host_metrics"].etat == catalog.EN_ATTENTE and readings["backup_jobs"].etat == catalog.EN_ATTENTE
    w.now = T + timedelta(minutes=40)
    assert w.reads(only=["host_metrics"])[0]["host_metrics"].etat == catalog.VIDE


def test_no_vault_known_no_read_of_it_said_why(monkeypatch):
    w = World()
    reading = w.c.dossier_reads(w.vm, T, vault="", now=w.now, only=["backup_jobs"])[0]["backup_jobs"]
    assert reading.etat == catalog.REFUSEE and "aucun coffre connu" in reading.why
    assert not any("backup" in str(c) for c in w.f.rest_calls)


def test_a_vm_id_that_does_not_pass_its_check_is_never_read():
    w = World()
    readings, calls = w.c.dossier_reads(w.vm + "' or resourceUri eq 'x", T, vault="rsv-bench", now=w.now)
    assert {r.etat for r in readings.values()} == {catalog.REFUSEE} and calls == 0 and w.f.rest_calls == []


def test_a_dry_run_reads_nothing():
    w = World()
    w.c.dry_run = True
    readings, calls = w.reads()
    assert {r.etat for r in readings.values()} == {catalog.REFUSEE} and calls == 0 and w.f.rest_calls == []


# ── Never for a detection attributed to no VM (23/11) ───────────────────────────────────────────────

def test_a_detection_attributed_to_no_vm_is_never_read_on_azure_and_says_it():
    """M7296: the attribution not read — the anchor VM of an unattributed detection read on Azure."""
    w = World().bree()
    path = _dossier(w, attribution="unattributed")
    assert dossier_pass.reads_pass(w.c, now=w.now, budget=_budget()) == []
    assert w.f.rest_calls == []
    doc = _doc(path)
    assert doc["lectures"]["etat"] == "sans_lecture"
    assert _facts(path)[("F1", "platform_reads")]["dit"] == "pas de lecture d'Azure, aucune VM attribuée"


# ── The steps: 1, 1 bis, 2, settled ─────────────────────────────────────────────────────────────────

def test_step_1_bis_reads_again_what_was_not_delivered_and_settles_once_its_last_read_is_complete():
    w = World(at=T + timedelta(minutes=2))
    w.f.metric(w.vm, OS_WRITE, T.replace(second=0), 9.4e6, delay_s=240)       # the host, four minutes late
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    assert _facts(path)[("F2", "host_metric")]["etat"] == "en_attente"
    assert "host_metrics" in _doc(path)["lectures"]["a_relire"]
    w.now = T + timedelta(minutes=5, seconds=30)                       # T + 5: read again
    w.f.rest_calls.clear()
    assert [r["etape"] for r in dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())] == ["1 bis"]
    assert _facts(path)[("F2", "host_metric")]["etat"] == "lu"
    assert not any("resourcehealth" in u for u, _ in w.f.rest_calls)  # only what was not delivered
    w.now = T + timedelta(minutes=36)                                  # the last read complete: read again
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    w.now = T + timedelta(minutes=37)
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())] == ["regle"]
    doc = _doc(path)
    assert doc["lectures"]["etat"] == "reglees" and not [f for f in doc["faits"] if f["etat"] in ("en_attente",
                                                                                                    "illisible")
                                                         and f.get("lecture_id")]
    assert dossier_pass.reads_pass(w.c, now=w.now + timedelta(hours=1), budget=_budget()) == []


def test_a_vm_with_no_event_read_at_40_min_has_its_log_said_empty():
    """The review of DOS4: the log's window runs to T + 30 min and its latency 300 s — read at T + 40, it
    is complete: no event is « empty », never « waiting »."""
    w = World(at=T + timedelta(minutes=40))
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    facts = _facts(path)
    for key in (("F1b", "extensions_log"), ("F1c", "reboot"), ("F1d", "health_events"), ("F5a", "own_operations")):
        assert facts[key]["etat"] == "vide", key


def test_a_log_with_no_event_is_said_empty_at_its_last_reading_never_waiting_at_the_settling():
    """M7338: the dossier settled at T + 30 min, before its log is complete (T + 35): the log with no event
    is never said empty, and « the source delivered nothing » is said where its window was still open."""
    w = World(at=T + timedelta(minutes=2))
    path = _dossier(w)
    for minutes in (2, 31, 32, 36, 37):
        w.now = T + timedelta(minutes=minutes)
        dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    facts, doc = _facts(path), _doc(path)
    assert doc["lectures"]["etat"] == "reglees"
    assert facts[("F1b", "extensions_log")]["etat"] == "vide" and facts[("F1c", "reboot")]["etat"] == "vide"
    assert not [f for f in doc["faits"] if f.get("pourquoi") == dossier_pass.NOTHING]
    assert dossier_pass.SETTLE_S == 2100 and dossier_pass.MARKS_S[-1] == dossier_pass.SETTLE_S


def test_a_fact_read_with_its_window_open_says_when_it_is_read_again():
    w = World(at=T + timedelta(minutes=8)).bree()
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    ext = _facts(path)[("F1b", "extensions_log")]
    assert ext["etat"] == "lu" and ext["dit"].endswith("(fenêtre encore ouverte : relu vers 02:50 UTC)")
    assert "activity_window" in _doc(path)["lectures"]["a_relire"]
    w.now = T + timedelta(minutes=40)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    assert "fenêtre encore ouverte" not in _facts(path)[("F1b", "extensions_log")]["dit"]


def test_what_is_still_waiting_at_the_settling_is_unreadable_never_empty_with_its_true_reason():
    """M7297: the settling writes a waiting fact empty — « nothing » where the source delivered nothing."""
    w = World(at=T + timedelta(minutes=2))
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    waiting = [k for k, f in _facts(path).items() if f["etat"] == "en_attente"]
    assert ("F2", "host_metric") in waiting and ("F1b", "extensions_log") in waiting
    # F2 as if last read once complete (T + 36), F1b last read with its window open (T + 2) — and the
    # budget never lets the last reading happen: the dossier is settled all the same, each with its why.
    doc = _doc(path)
    doc["faits"] = [dict(f, lu_a=(T + timedelta(minutes=36)).isoformat()) if f["code"] == "F2" else f
                    for f in doc["faits"]]
    dossier._write(path, doc)
    held = _budget()
    held.take(held.per_min())
    w.now = T + timedelta(minutes=37)
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=w.now, budget=held)] == ["regle"]
    facts = _facts(path)
    assert facts[("F2", "host_metric")]["etat"] == "illisible"
    assert facts[("F2", "host_metric")]["pourquoi"] == dossier_pass.NOTHING           # read complete, nothing
    assert facts[("F1b", "extensions_log")]["etat"] == "illisible"
    assert facts[("F1b", "extensions_log")]["pourquoi"] == dossier_pass.NOT_READ_AGAIN  # open, never read again


def test_the_system_read_in_the_vms_model_says_the_process_counter_without_object():
    w = World().bree()
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    f6g = _facts(path)[("F6g", "model_inputs")]
    by = {i["requete"]: i for i in f6g["valeurs"]["requetes"]}
    assert f6g["valeurs"]["systeme"] == "linux" and f6g["valeurs"]["systeme_lu_dans"] == "le modèle de la VM (ARM)"
    assert by["backup_agent_check"]["etat"] == "sans_objet" and "Linux" in by["backup_agent_check"]["pourquoi"]


def test_step_2_once_the_drain_is_settled_reads_it_again_and_the_log():
    from glorfindel.response import state as st
    w = World(at=T + timedelta(minutes=3)).bree()
    state = _state(w.vm)
    state.update(action="isolate_vm", escalate=False, mode_hold=False,
                 outcome={"status": "isolated", "executed": True, "verified": True, "drain": {"status": "pending"}})
    st._save_isolation_state(w.vm, {"resource_id": w.vm, "isolated_at": (T + timedelta(seconds=20)).isoformat(),
                                    "placements": [], "drain": {"status": "pending"},
                                    "drains_at": [(T + timedelta(seconds=26)).isoformat()]})
    path = dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp() + 60)
    assert _facts(path)[("F5b", "drain")]["etat"] == "en_attente"
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    w.now = T + timedelta(minutes=8)
    st._save_isolation_state(w.vm, {**st._load_isolation_state(w.vm), "drain": {"status": "drained"},
                                    "drain_ended_at": (T + timedelta(seconds=460)).isoformat()})
    report = dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    assert [r["etape"] for r in report] == ["2"]
    drain, doc = _facts(path)[("F5b", "drain")], _doc(path)
    assert drain["etat"] == "lu" and drain["valeurs"]["duree_s"] == 434 and doc["etape"] == 2


def test_a_drain_never_confirmed_is_unreadable():
    from glorfindel import dossier_local
    from glorfindel.response import state as st
    w = World()
    st._save_isolation_state(w.vm, {"resource_id": w.vm, "isolated_at": T.isoformat(), "placements": [],
                                    "drain": {"status": "failed", "never": True, "error": "délai dépassé"}})
    f = dossier_local._drain({"signal": {"resource_id": w.vm}, "outcome": {}}, dossier.ISOLATION, T.isoformat())
    assert f["etat"] == "illisible" and "peut-être" in f["pourquoi"]


def test_glorfindel_unknown_on_azure_its_gestures_are_unreadable(monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_ID")
    w = World().bree()
    path = _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    own = _facts(path)[("F5a", "own_operations")]
    assert own["etat"] == "illisible" and "AZURE_CLIENT_ID" in own["pourquoi"]


def test_a_provider_that_cannot_read_says_each_read_unreadable():
    class Other:
        def dossier_reads(self, *a, **kw):
            raise NotImplementedError
    w = World()
    path = _dossier(w)
    dossier_pass.reads_pass(Other(), now=w.now, budget=_budget())
    drawn = [f for f in _doc(path)["faits"] if f.get("etat_lecture")]
    assert drawn and {f["etat"] for f in drawn} == {"illisible"}


def test_a_forged_row_time_never_steers_the_window():
    """DOS4 reads `signal_at`: the row's time is the guest's on a Syslog line — a time after the signal,
    or hours before it, gives T from the signal."""
    w = World()
    state = _state(w.vm)
    state["signal"]["raw_signal"]["first_result_row"]["TimeGenerated"] = (T - timedelta(days=3)).isoformat()
    doc = _doc(dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp() + 60))
    assert doc["T"] == (T + timedelta(seconds=14)).isoformat() and doc["T_lu_dans"] == "signal (ligne écartée)"
    state["signal"]["raw_signal"]["first_result_row"]["TimeGenerated"] = (T + timedelta(hours=1)).isoformat()
    state["signal"]["signal_id"] += "b"
    assert _doc(dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp()))["T_lu_dans"] \
        == "signal (ligne écartée)"


def test_a_dossier_written_before_dos4_is_left_as_it_is():
    w = World()
    path = _dossier(w)
    doc = _doc(path)
    doc.pop("lectures")
    dossier._write(path, doc)
    assert dossier_pass.reads_pass(w.c, now=w.now, budget=_budget()) == [] and w.f.rest_calls == []


# ── The ARM budget: the dossier's own, a real one before an exercise, a critical object never dropped ─

def _taken(budget: read_budget.ReadBudget, n: int = 60) -> None:
    """The minute's ARM calls already spent by the dossiers read before."""
    budget.spend(n, read_budget.DOSSIER)


def test_a_minute_without_room_the_dossier_waits_and_says_what_held_it():
    w = World().bree()
    budget = _budget()
    _taken(budget)
    path = _dossier(w, source="exercise")
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=T + timedelta(minutes=2), budget=budget)] \
        == ["attente_budget"]
    assert w.f.rest_calls == []
    said = _facts(path)[("F1", "platform_reads")]
    assert said["etat"] == "en_attente" and _doc(path)["lectures"]["etat"] == "attente_budget"
    assert _doc(path)["lectures"]["pourquoi"] == ("budget ARM du dossier tenu : 60 appel(s) dans la minute (dossier "
                                                  "60) sur 60 (GLORFINDEL_ARM_BUDGET_PER_MIN)")


def test_the_dossier_takes_from_arm_never_from_the_detection_s_budget(monkeypatch):
    """M7340: the dossier taking from Log Analytics' budget — the detection's queries hold it, the
    dossier waits on them again."""
    la = read_budget.ReadBudget("Log Analytics", "GLORFINDEL_LA_BUDGET_PER_MIN", 120)
    arm = _budget()
    monkeypatch.setattr(read_budget, "LOG_ANALYTICS", la)
    monkeypatch.setattr(read_budget, "ARM", arm)
    la.spend(500, read_budget.DETECTION)
    w = World().bree()
    _dossier(w)
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=w.now)] == ["lu"]
    assert arm.used() == {read_budget.DOSSIER: 7} and la.used() == {read_budget.DETECTION: 500}


def test_a_dossier_without_room_by_its_settling_says_it_was_not_composed_and_why():
    w = World().bree()
    budget = _budget()
    _taken(budget)
    path = _dossier(w)
    doc = _doc(path)
    doc["critique"] = False
    dossier._write(path, doc)
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=w.now, budget=budget)] == ["non_compose"]
    said = _facts(path)[("F1", "platform_reads")]
    assert said["etat"] == "illisible" and "budget ARM du dossier tenu" in said["pourquoi"]
    assert "GLORFINDEL_ARM_BUDGET_PER_MIN" in said["pourquoi"] and "détection" not in said["pourquoi"]
    assert dossier_pass.reads_pass(w.c, now=w.now + timedelta(hours=1), budget=_budget()) == []


def test_an_arm_budget_of_zero_says_the_reads_are_off(monkeypatch):
    monkeypatch.setenv("GLORFINDEL_ARM_BUDGET_PER_MIN", "0")
    w = World().bree()
    path = _dossier(w)
    doc = _doc(path)
    doc["critique"] = False
    dossier._write(path, doc)
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    assert "éteintes (GLORFINDEL_ARM_BUDGET_PER_MIN=0)" in _facts(path)[("F1", "platform_reads")]["pourquoi"]


def test_an_arm_budget_under_one_pass_still_lets_a_dossier_read(monkeypatch):
    """M7339 (its other side): a budget of 3 taken as set — no dossier ever reads."""
    monkeypatch.setenv("GLORFINDEL_ARM_BUDGET_PER_MIN", "3")
    w = World().bree()
    path = _dossier(w)
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())] == ["lu"]
    assert _doc(path)["lectures"]["etat"] == "faites"


def test_a_critical_object_is_never_without_its_dossier():
    """M7298: a critical object dropped like any other — past 30 min without room, « not composed »."""
    w = World().bree()
    budget = _budget()
    _taken(budget)
    path = _dossier(w)
    assert _doc(path)["critique"] is True                       # T1486: a grave technique
    for minutes in (40, 90, 300):
        assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=T + timedelta(minutes=minutes), budget=budget)] \
            == ["attente_budget"]
    assert _doc(path)["lectures"]["etat"] == "attente_budget"
    assert [r["issue"] for r in dossier_pass.reads_pass(w.c, now=T + timedelta(minutes=301), budget=_budget())] == ["lu"]


def test_a_real_isolation_reads_before_an_exercise():
    """M7299: the order of the dossiers lost — the exercise, older, read first and the real one waits."""
    w = World().bree()
    exercise = _dossier(w, source="exercise")
    doc = _doc(exercise)
    doc["T"] = (T - timedelta(minutes=10)).isoformat()
    doc["critique"] = False
    dossier._write(exercise, doc)
    state = _state(w.vm)
    state["signal"]["signal_id"] = "rule-real-00000001"
    real = dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp() + 90)
    real_doc = _doc(real)
    real_doc["critique"] = False
    dossier._write(real, real_doc)
    budget = _budget()
    _taken(budget, 60 - sum(dossier_pass.CALLS.values()))                               # room for one
    report = dossier_pass.reads_pass(w.c, now=T + timedelta(minutes=2), budget=budget)
    assert [(r["dossier"], r["issue"]) for r in report] == [(real.name, "lu"), (exercise.name, "attente_budget")]


def test_a_dossier_refused_lets_none_behind_it_read():
    """M7301: the order not held — a dossier refused, the one behind it asks less and reads before it."""
    w = World().bree()
    first = _dossier(w)
    state = _state(w.vm)
    state["signal"]["signal_id"] = "rule-later-00000002"
    state["signal"]["raw_signal"]["first_result_row"]["TimeGenerated"] = (T + timedelta(seconds=5)).isoformat()
    later = dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp() + 90)
    doc = _doc(later)                     # its step 1 done, one read left for T + 5 min: one call
    doc["lectures"] = {"etat": "faites", "faites_a": (T + timedelta(minutes=1)).isoformat(),
                       "a_relire": ["resource_health"]}
    dossier._write(later, doc)
    budget = _budget()
    _taken(budget, 60 - 3)                                                      # room for 3: not for step 1
    report = dossier_pass.reads_pass(w.c, now=T + timedelta(minutes=6), budget=budget)
    assert [(r["dossier"], r["issue"]) for r in report] == [(first.name, "attente_budget")]
    assert w.f.rest_calls == [] and _doc(later)["lectures"]["faites_a"] == (T + timedelta(minutes=1)).isoformat()


def test_the_pages_past_one_are_counted_after_they_are_read():
    w = World().bree()
    w.f.page_size = 1
    budget = _budget()
    _dossier(w)
    dossier_pass.reads_pass(w.c, now=w.now, budget=budget)
    assert budget.used()[read_budget.DOSSIER] > sum(dossier_pass.CALLS.values())


# ── The approved proposal of a block, its retention ─────────────────────────────────────────────────

def test_a_block_proposal_approved_keeps_its_dossier_until_30_days_after_the_unblock():
    """M7300: the block approved since not read by the retention — its dossier gone 30 days after the
    card, the address still blocked."""
    from glorfindel.response import state as st
    w = World()
    state = _state(w.vm)
    state.update(action="block_suspicious_ip")
    state["signal"]["raw_signal"]["first_result_row"]["SourceIP"] = "203.0.113.9"
    path = dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp())
    assert _doc(path)["ip"] == "203.0.113.9" and _doc(path)["perimetre"] == "proposition"
    st._save_block_state("vm-dos4", "203.0.113.9", w.vm)
    day = 86400
    assert dossier.retention_pass(now=T.timestamp() + 40 * day) == 0 and path.exists()
    assert not _doc(path)["leve_vu_a"]
    st._clear_block_state(w.vm, "203.0.113.9")
    assert dossier.retention_pass(now=T.timestamp() + 41 * day) == 0 and _doc(path)["leve_vu_a"]
    assert dossier.retention_pass(now=T.timestamp() + 72 * day) == 1 and not path.exists()


def test_another_address_blocked_does_not_hold_the_proposal():
    from glorfindel.response import state as st
    w = World()
    state = _state(w.vm)
    state.update(action="block_suspicious_ip")
    state["signal"]["raw_signal"]["first_result_row"]["SourceIP"] = "203.0.113.9"
    path = dossier.DOSSIER_DIR / dossier.at_cycle_end(state, True, "real", "", now=T.timestamp())
    st._save_block_state("vm-dos4", "198.51.100.7", w.vm)
    dossier.retention_pass(now=T.timestamp() + 3600)
    assert _doc(path)["leve_vu_a"]


# ── The rewrite under the lock; the message to the model ────────────────────────────────────────────

def test_two_rewrites_of_one_dossier_never_lose_one_another(monkeypatch):
    """M7077 (DOS3's lock, now the rewrite's): out of the lock, the retention and the reads' pass each read
    the file, and the last to write drops the other's change."""
    w = World()
    path = _dossier(w)
    real = dossier._read

    def slow(p):
        doc = real(p)
        time.sleep(0.05)
        return doc
    monkeypatch.setattr(dossier, "_read", slow)
    threads = [threading.Thread(target=dossier.update, args=(path, lambda d, k=k: {**d, k: True})) for k in "ab"]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    doc = real(path)
    assert doc.get("a") is True and doc.get("b") is True


def test_the_reads_leave_the_message_to_the_model_unchanged_to_the_byte():
    import hashlib

    from glorfindel import agent
    from tests.unit.test_cycle_line import PAST, USER_SHA256, _bree
    w = World().bree()
    state = _state(w.vm)
    state["signal"] = {**_bree(), "resource_id": w.vm}
    before = json.dumps(state["signal"], sort_keys=True)
    dossier.at_cycle_end(state, True, "real", "", now=T.timestamp())
    dossier_pass.reads_pass(w.c, now=w.now, budget=_budget())
    assert json.dumps(state["signal"], sort_keys=True) == before
    signal = {**state["signal"], "resource_id": _bree()["resource_id"]}
    assert hashlib.sha256(agent._build_user_message(signal, PAST).encode()).hexdigest() == USER_SHA256


# ── The watch's thread ──────────────────────────────────────────────────────────────────────────────

def test_the_watch_reads_the_dossiers_in_a_thread_of_its_own_never_in_dry_run(monkeypatch):
    from rich.console import Console

    from glorfindel.watch.housekeeping import Housekeeping
    calls, gate = [], threading.Event()

    def slow_pass(connector):
        calls.append(threading.current_thread().name)
        gate.wait(2)
        return []
    monkeypatch.setattr(dossier_pass, "reads_pass", slow_pass)
    hk = Housekeeping(Console(file=open("/dev/null", "w")), threading.Lock(), dry_run=False, mode_override=None,
                      runs_dir="runs", ttl_h=24, emit=lambda *_: None, say_channel=lambda *_: None)
    hk._dossier_reads()                                    # no dossier on disk: no thread
    assert calls == []
    dossier.DOSSIER_DIR.mkdir(parents=True, exist_ok=True)
    hk._dossier_reads()
    hk._dossier_reads()                                    # one pass at a time
    time.sleep(0.1)
    gate.set()
    hk._dossier_thread._thread.join(2)
    assert calls == ["dossier"]
    dry = Housekeeping(Console(file=open("/dev/null", "w")), threading.Lock(), dry_run=True, mode_override=None,
                       runs_dir="runs", ttl_h=24, emit=lambda *_: None, say_channel=lambda *_: None)
    dry._dossier_reads()
    assert dry._dossier_thread._thread is None


# ── The catalogue's form (ENQ2): one vocabulary of states, the sentinel, the parameters ─────────────

def test_one_vocabulary_the_seven_states_of_a_read_and_the_five_words_of_a_fact():
    assert set(catalog.CARD_STATE) == set(catalog.ETATS)
    assert set(catalog.CARD_STATE.values()) == set(dossier.ETATS)
    assert {s for s, w in catalog.CARD_STATE.items() if w == "illisible"} == {"echec", "refusee", "non_permise"}
    with pytest.raises(ValueError):
        dossier.fact("F2", "host_metric", etat="vide", etat_lecture="echec", dit="?", source="s", lecture="l", lu_a="")


def test_the_platform_reads_are_declared_as_the_enquiry_s_and_kept_out_of_it_until_measured():
    for read in PLATFORM_READS.values():
        assert read.kind == "arm" and set(read.params) <= set(catalog.PARAMS) and "vm" in read.params
        assert read.id not in catalog.READS                 # Q8: the enquiry asks only what the bench measured
        assert isinstance(catalog.ask(read.id), catalog.Reading)
        assert all(catalog.says(read, s) == "" for s in catalog.SYSTEMS)
    assert catalog.PARAMS["vault"].check("/subscriptions/s/resourceGroups/rg/providers/Microsoft."
                                         "RecoveryServices/vaults/rsv")
    assert catalog.window(PLATFORM_READS["activity_window"], T) == (T - timedelta(minutes=30), T + timedelta(minutes=30))


def test_a_raw_none_goes_through_its_check_only_the_sentinel_skips_it(monkeypatch):
    """M7304: a raw None skipping its check again — the read not run, and the value refused never said."""
    from glorfindel.enquiry import fixed
    monkeypatch.setattr(fixed, "selection", lambda row: ["successful_auth_from_ip"])
    out = fixed.enquire({"FailedAttempts": 9, "SourceIP": None}, "/subscriptions/s/resourceGroups/rg/providers/"
                        "Microsoft.Compute/virtualMachines/vm", "ws", unattributed=False)
    assert out.readings[0].etat == catalog.REFUSEE and out.refused       # the check said why
    loose = fixed.enquire({"FailedAttempts": 9, "SourceIP": "203.0.113.9"}, "x", "ws", unattributed=True)
    assert loose.readings[0].etat == catalog.REFUSEE and loose.readings[0].why.startswith("détection non attribuée")
    assert loose.refused == {}                                          # the sentinel is not a value refused


def test_a_parameter_declared_and_given_no_value_is_a_hole_never_a_key_error(monkeypatch):
    from types import MappingProxyType

    from glorfindel import kql
    from glorfindel.enquiry import fixed
    params = {**catalog.PARAMS, "disk": catalog.Param("un disque", kql.resource_id)}
    monkeypatch.setattr(catalog, "PARAMS", MappingProxyType(params))
    read = catalog.Read("disk_read", "un disque", "Perf | where _ResourceId =~ {disk}", ("disk",),
                        timedelta(minutes=5), 45, catalog.PLATFORM, {catalog.LINUX: catalog.READS_HERE})
    monkeypatch.setattr(catalog, "READS", MappingProxyType({**catalog.READS, "disk_read": read}))
    monkeypatch.setattr(fixed, "selection", lambda row: ["disk_read"])
    out = fixed.enquire({}, "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm",
                        "ws", unattributed=False)
    assert out.readings[0].etat == catalog.REFUSEE and out.gaps == ["disk_read"]
    assert out.readings[0].why == "paramètre absent : disk" and out.refused == {}   # absent, never « refused »
