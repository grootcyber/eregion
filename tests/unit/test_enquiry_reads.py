"""ENQ5a (#1162; `docs/design/enquete-raisonnee.md` §4, §5.1, §6.3, §7.2, EH8, EH10): the three reads that
judge a ransomware — `perf_minute_series`, `vault_jobs`, `vault_activity` — served at the harness, and
what serving them brings: the loop's reader, its window anchored on the signal's hour by the code (never
by the model); how far a source has ingested, which says « waiting » (`catalog.outcome`, `ingere`); an
obligatory read still waiting, a gap; the marker of a read not served yet; the vault the configuration
names; the predicates of T1486-H1 and H2, computed by the code. The vault's reads are DOS4's code, run on
the fake Azure (tests/unit/fake_azure.py). No Azure call, no model call. Mutants M7443–M7462
(scripts/mutants/ENQ5a.py).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from glorfindel import kql
from glorfindel.enquiry import catalog, knowledge, lecteur, loop, message, predicats
from glorfindel.providers.azure.connector import AzureConnector

from .fake_azure import FakeAzure

SUB = "00000000-0000-0000-0000-0000000000aa"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/vm-linux-01"
VAULT = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.RecoveryServices/vaults/vault-01"
AT = datetime(2026, 11, 10, 2, 34, 10, tzinfo=timezone.utc)
LATER = AT + timedelta(minutes=10)
DISK = {"Computer": "vm-linux-01", "MaxWrite": 147000000}
SERIE, JOBS, ACTIVITE = "perf_minute_series", "vault_jobs", "vault_activity"


@pytest.fixture(scope="module")
def t1486():
    return knowledge.charger().pour("ransomware-disk-write", "T1486")


class Lecteur:
    """The reads replaced: each id's answer (rows, `catalog.Lu`, None), every call noted."""

    def __init__(self, rows=None):
        self.rows, self.calls = rows or {}, []

    def __call__(self, read, valeurs):
        self.calls.append((read.id, dict(valeurs)))
        if read.id in catalog.INGESTION_DITE and read.id not in self.rows:
            return catalog.Lu([], AT + timedelta(hours=1), True)     # its source ingested past the window
        return self.rows.get(read.id, [])


def _conclut(prompt, texte, outil, timeout):
    _conclut.messages.append(texte)
    return {"geste": "conclure"}


_conclut.messages = []


def _enquete(lecteur, *, fiche, now=LATER, systeme="linux", coffre=VAULT, detection=DISK, modele=_conclut):
    return loop.enqueter(detection=detection, vm=VM, regle="ransomware-disk-write", technique="T1486",
                         systeme=systeme, fiche=fiche, lecteur=lecteur, modele=modele, at=AT,
                         maintenant=lambda: now, coffre=coffre)


def _minute(debut: datetime, moyenne: float, *, pic: datetime | None = None, n: int = 6, vol: str = "/") -> dict:
    return {"Minute": debut.isoformat(), "InstanceName": vol, "Echantillons": n, "MoyenneMBs": moyenne,
            "MaxMBs": moyenne * 3, "PremierPic": pic.isoformat() if pic else None,
            "Dernier": (debut + timedelta(seconds=50)).isoformat()}


M1 = datetime(2026, 11, 10, 2, 33, tzinfo=timezone.utc)      # the minute of the first sample past the threshold
M2 = M1 + timedelta(minutes=1)
PIC = M1 + timedelta(seconds=50)


def _serie(*rows, horizon: datetime | None = AT + timedelta(minutes=4)) -> dict[str, catalog.Reading]:
    return {SERIE: catalog.Reading(SERIE, catalog.LIGNES, rows=list(rows),
                                   ingere=horizon.isoformat() if horizon else "")}


# ── The reads in the catalogue, their window from the code (M7445, M7446) ────────────────────────────

def test_the_three_reads_left_the_announced_ones_and_entered_the_catalogue(t1486):
    for rid in (SERIE, JOBS, ACTIVITE):
        assert rid in catalog.READS and rid not in knowledge.ANNONCEES
    assert catalog.READS[SERIE].kind == "kql" and catalog.READS[JOBS].kind == catalog.READS[ACTIVITE].kind == "arm"
    assert catalog.READS[JOBS].obj == catalog.READS[ACTIVITE].obj == "vault"
    assert set(t1486.obligatoires) == {SERIE, JOBS, ACTIVITE}
    # They depend on no system: an unknown one never stops them.
    assert all(catalog.says(catalog.READS[r], "") == "" for r in (SERIE, JOBS, ACTIVITE))
    # Their sentence says the window is the signal's, never the read's.
    assert all("signal" in catalog.READS[r].phrase for r in (SERIE, JOBS, ACTIVITE))


# ENQ5b: heartbeat_gap's loop text writes its window (catalog.ANCREES; tests/unit/test_enquiry_production.py).
@pytest.mark.parametrize("read_id", [r for r in catalog.INVESTIGATE if r not in catalog.ANCREES])
def test_each_kql_read_of_investigate_is_anchored_on_the_signal_never_on_the_read(read_id):
    """M7446: the `ago()` left — a capture made a day later reads nothing of its episode."""
    read = catalog.READS[read_id]
    vals = {p: {"vm": VM, "ip": "185.220.101.5"}[p] for p in read.params}
    q = lecteur.texte(read, vals, AT)
    debut, fin = catalog.window(read, AT)
    assert "ago(" not in q
    assert f"TimeGenerated between (datetime({lecteur._iso(debut)}) .. datetime({lecteur._iso(fin)}))" in q
    assert f"_ResourceId =~ {kql.literal(VM)}" in q and "{" not in q
    assert read.query.count("ago(") == 1 and "ago(" in read.query        # investigate's text, to the byte


def test_the_minute_series_is_read_from_five_minutes_before_the_signal_to_three_after():
    """M7445: the window taken from the read's own hour, not from the signal's."""
    read = catalog.READS[SERIE]
    q = lecteur.texte(read, {"vm": VM}, AT)
    assert "let debut = datetime(2026-11-10T02:29:10Z);" in q and "let fin = datetime(2026-11-10T02:37:10Z);" in q
    assert "bin(TimeGenerated, 1m)" in q and "ingestion_time()" in q and "print Horizon" in q
    assert q.count(f"_ResourceId =~ {kql.literal(VM)}") == 2 and "Computer" not in q
    # The threshold of `PremierPic` is the predicates' own (25 MB/s on one sample).
    assert "| extend Pic = (Fine and Rate > 45000000) or (not(Fine) and Rate > 25000000)" in q
    debut, fin = lecteur.timespan(read, AT)
    assert debut == AT - timedelta(minutes=6) and fin == AT + timedelta(minutes=3 + 1 + 10)


def test_a_query_whose_window_cannot_be_anchored_is_never_run():
    two = catalog.Read("x", "a read", "Perf\n| where TimeGenerated > ago(5m)\n| where TimeGenerated > ago(5m)\n"
                       "| where _ResourceId =~ {vm}\n", ("vm",), timedelta(minutes=5), 45, catalog.GUEST_PROVOCABLE,
                       catalog.READS["heartbeat_gap"].systems)
    other = catalog.Read("y", "a read", "Perf\n| where TimeGenerated > ago(10m)\n| where _ResourceId =~ {vm}\n",
                         ("vm",), timedelta(minutes=5), 45, catalog.GUEST_PROVOCABLE,
                         catalog.READS["heartbeat_gap"].systems)
    for read in (two, other):
        with pytest.raises(lecteur.NonAncrable):
            lecteur.texte(read, {"vm": VM}, AT)
    ran = []
    assert lecteur.Lecteur(AT, kql=lambda q, s: ran.append(q) or [])(two, {"vm": VM}) is None and ran == []


def test_the_reader_runs_the_anchored_query_on_the_episode_s_timespan_and_splits_the_horizon():
    sent = []
    horizon = AT + timedelta(minutes=5)

    def kql(query, span):
        sent.append((query, span))
        return [_minute(M1, 5.2), {"Minute": None, "Horizon": horizon.isoformat()}]

    lu = lecteur.Lecteur(AT, kql=kql)(catalog.READS[SERIE], {"vm": VM})
    assert isinstance(lu, catalog.Lu) and lu.ingere == horizon and len(lu.rows) == 1
    assert sent[0][1] == lecteur.timespan(catalog.READS[SERIE], AT)
    failing = lecteur.Lecteur(AT, kql=lambda q, s: (_ for _ in ()).throw(RuntimeError("403")))
    assert failing(catalog.READS["root_commands"], {"vm": VM}) is None       # failed, never empty


# ── How far its source ingested (EH10, M7447) ─────────────────────────────────────────────────────

def test_an_empty_answer_waits_until_its_source_has_ingested_the_end_of_its_window():
    """M7447: the horizon ignored — 25 minutes of delay (bree, 11/11) said « nothing » after 45 s."""
    read = catalog.READS[SERIE]
    end = catalog.window(read, AT)[1]
    late = catalog.outcome(read, [], system="linux", at=AT, now=AT + timedelta(minutes=30),
                           ingere=end - timedelta(seconds=1))
    assert late.etat == catalog.EN_ATTENTE and late.ingere
    whole = catalog.outcome(read, [], system="linux", at=AT, now=AT + timedelta(seconds=5), ingere=end)
    assert whole.etat == catalog.VIDE
    # A read that tells its ingestion and did not, or said nothing ingested: never `vide` (M7465).
    assert catalog.outcome(read, [], system="linux", at=AT, now=AT + timedelta(hours=2)).etat == catalog.EN_ATTENTE
    # A read that does not tell it: the declared latency, as before.
    beat = catalog.READS["heartbeat_gap"]
    assert catalog.outcome(beat, [], system="linux", at=AT, now=AT + timedelta(minutes=30)).etat == catalog.VIDE
    rows = catalog.outcome(read, [_minute(M1, 1.0)], at=AT, now=LATER, ingere=end)
    assert rows.etat == catalog.LIGNES and rows.ingere == end.isoformat()


def test_the_loop_reads_how_far_its_source_ingested(t1486):
    e = _enquete(Lecteur({SERIE: catalog.Lu([], AT)}), fiche=t1486, now=AT + timedelta(hours=1))
    assert e.lectures[SERIE].etat == catalog.EN_ATTENTE


# ── An obligatory read waiting is a gap (§7.2, M7444) ───────────────────────────────────────────────

def test_an_obligatory_read_still_waiting_is_a_gap_an_optional_one_never(t1486):
    """M7444: an obligatory read en_attente reaching decide as « aucun résultat », no gap."""
    early = _enquete(Lecteur({SERIE: catalog.Lu([], AT + timedelta(seconds=20), True)}), fiche=t1486,
                     now=AT + timedelta(seconds=30))
    assert {r: early.lectures[r].etat for r in t1486.obligatoires} == dict.fromkeys(t1486.obligatoires,
                                                                                    catalog.EN_ATTENTE)
    assert sorted(early.trous) == sorted(t1486.obligatoires)
    asked = loop.enqueter(detection=DISK, vm=VM, regle="ransomware-disk-write", technique="T1486", systeme="linux",
                          fiche=t1486, lecteur=Lecteur(), at=AT, maintenant=lambda: AT + timedelta(seconds=30),
                          coffre=VAULT, modele=lambda *a: {"geste": "lire", "id": "root_commands"})
    assert asked.lectures["root_commands"].etat == catalog.EN_ATTENTE and "root_commands" not in asked.trous


# ── The vault: the configuration's, never the model's (M7448) ────────────────────────────────────────

def test_the_vault_is_the_configuration_s_never_the_model_s_and_unknown_it_is_refused(t1486):
    seen = Lecteur()
    loop.enqueter(detection={**DISK, "vault": "/subscriptions/x/resourceGroups/y/providers/Microsoft."
                             "RecoveryServices/vaults/z"}, vm=VM, regle="ransomware-disk-write", technique="T1486",
                  systeme="linux", fiche=t1486, lecteur=seen, at=AT, maintenant=lambda: LATER, coffre=VAULT,
                  modele=lambda *a: {"geste": "lire", "id": JOBS, "vault": "/elsewhere"})
    assert {c[1]["vault"] for c in seen.calls if "vault" in c[1]} == {VAULT}
    none = _enquete(Lecteur(), fiche=t1486, coffre="")
    assert none.lectures[JOBS].etat == catalog.REFUSEE and none.lectures[JOBS].why == loop.SANS_COFFRE
    assert set(none.trous) == {JOBS, ACTIVITE}                      # the code asked them: unknown, a gap
    bad = _enquete(Lecteur(), fiche=t1486, coffre="vault-01' or 1==1")
    assert bad.lectures[JOBS].etat == catalog.REFUSEE


# ── The system of the VM: unknown, never « vide » (M7449) ───────────────────────────────────────────

def test_an_unknown_system_never_stops_t1486_s_reads_and_never_reads_a_counter_empty(t1486):
    seen = Lecteur()
    e = _enquete(seen, fiche=t1486, systeme="")
    assert {c[0] for c in seen.calls} == set(t1486.obligatoires)
    sheet = knowledge.valider({
        "technique": "T1485", "nom": "a test sheet", "regles": ["test-rule"], "grave": True,
        "obligatoires": ["top_write_processes"],
        "hypotheses": [{"id": "T1485-H1", "enonce": "a statement", "sens": "confirme", "effet": "resserre",
                        "lectures": ["top_write_processes"], "sources": [{"genre": "externe", "ref": "a source"}],
                        "etat": "supposee", "limite": "a limit"}]})
    other = Lecteur()
    u = loop.enqueter(detection=DISK, vm=VM, regle="test-rule", technique="T1485", systeme="", fiche=sheet,
                      lecteur=other, modele=_conclut, at=AT, maintenant=lambda: LATER)
    lu = u.lectures["top_write_processes"]
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.UNKNOWN_SYSTEM and other.calls == []
    assert e.trous == []


# ── T1486-H1 (M7450, M7451, M7452) ───────────────────────────────────────────────────────────────

def test_h1_confirms_on_a_settled_minute_past_25():
    assert predicats.h1(_serie(_minute(M1, 18.4, pic=PIC), _minute(M2, 59.4, pic=M2)), AT, LATER) == "confirme"


def test_h1_never_confirms_on_a_minute_not_whole_nor_ingested():
    """M7450: a minute with half its samples, or not ingested past, taken whole."""
    partial = _serie(_minute(M1, 2.0, pic=PIC), _minute(M2, 40.0, n=3, pic=M2), _minute(M2 + timedelta(minutes=1), 1.0))
    assert predicats.h1(partial, AT, LATER) != "confirme"
    unsettled = _serie(_minute(M1, 2.0, pic=PIC), _minute(M2, 40.0, pic=M2), horizon=M2 + timedelta(seconds=55))
    assert predicats.h1(unsettled, AT, LATER) == "en_attente"


def test_h1_infirms_only_on_two_minutes_of_every_volume_each_under_15():
    """M7451: one minute read infirms — the attack of 09/11 passes the threshold at its second minute."""
    bree = _serie(_minute(M1, 5.2, pic=PIC), _minute(M2, 11.1, pic=M2), _minute(M1, 0.1, vol="/mnt"),
                  _minute(M2, 0.1, vol="/mnt"))
    assert predicats.h1(bree, AT, LATER) == "infirme"
    one = _serie(_minute(M1, 5.2, pic=PIC), horizon=M2 + timedelta(seconds=30))
    assert predicats.h1(one, AT, LATER) == "en_attente"
    gone = _serie(_minute(M1, 5.2, pic=PIC))                        # the next minute never came, past it
    assert predicats.h1(gone, AT, LATER) == "inconnu"
    other_volume = _serie(_minute(M1, 5.2, pic=PIC), _minute(M2, 11.1), _minute(M1, 0.1, vol="/data"),
                          _minute(M2, 17.0, vol="/data"))
    assert predicats.h1(other_volume, AT, LATER) == "inconnu"
    attack_start = _serie(_minute(M1, 18.4, pic=PIC), _minute(M2, 12.0))
    assert predicats.h1(attack_start, AT, LATER) == "inconnu"


def test_h1_says_waiting_while_its_read_waits_and_unknown_when_it_does_not_read():
    waiting = {SERIE: catalog.Reading(SERIE, catalog.EN_ATTENTE)}
    assert predicats.h1(waiting, AT, LATER) == "en_attente"
    for etat in (catalog.ECHEC, catalog.VIDE, catalog.REFUSEE, catalog.SANS_OBJET):
        assert predicats.h1({SERIE: catalog.Reading(SERIE, etat)}, AT, LATER) == "inconnu"
    broken = _serie(_minute(M1, 5.2, pic=PIC), {"Minute": "hier"})
    assert predicats.h1(broken, AT, LATER) == "inconnu"
    # No horizon said: the minute's end plus the declared latency of Perf.
    assert predicats.h1(_serie(_minute(M1, 30.0, pic=PIC), horizon=None), AT, M1 + timedelta(seconds=70)) == "en_attente"
    assert predicats.h1(_serie(_minute(M1, 30.0, pic=PIC), horizon=None), AT, LATER) == "confirme"


# ── T1486-H2 (M7453, M7454) ──────────────────────────────────────────────────────────────────────

def _jobs(*starts: datetime, operation: str = "Backup", etat: str = catalog.LIGNES) -> dict:
    rows = [{"operation": operation, "status": "InProgress", "start": s.isoformat()} for s in starts]
    return {JOBS: catalog.Reading(JOBS, etat if rows or etat != catalog.LIGNES else catalog.VIDE, rows=rows)}


BREE = _serie(_minute(M1, 5.2, pic=PIC), _minute(M2, 11.1, pic=M2))


def test_h2_confirms_on_h1_infirmed_and_a_backup_started_in_the_five_minutes_before_the_first_sample():
    assert predicats.h2({**BREE, **_jobs(PIC - timedelta(seconds=31))}, AT, LATER) == "confirme"


def test_h2_never_confirms_without_h1_infirmed():
    """M7453: a job at the hour of the backup confirms H2 whatever the minute said — the cover of case 3."""
    attack = _serie(_minute(M1, 18.4, pic=PIC), _minute(M2, 59.4, pic=M2))
    assert predicats.h2({**attack, **_jobs(PIC - timedelta(minutes=2))}, AT, LATER) == "infirme"
    early = _serie(_minute(M1, 5.2, pic=PIC), horizon=M2)
    assert predicats.h2({**early, **_jobs(PIC - timedelta(minutes=2))}, AT, LATER) == "inconnu"


def test_h2_counts_only_a_backup_of_the_five_minutes_before_the_first_sample():
    """M7454: a job after the first sample, or long before, or not a backup, taken as the explanation."""
    for start, op in ((PIC + timedelta(seconds=5), "Backup"), (PIC - timedelta(minutes=6), "Backup"),
                      (PIC - timedelta(seconds=31), "Restore")):
        assert predicats.h2({**BREE, **_jobs(start, operation=op)}, AT, LATER) == "infirme", (start, op)


def test_h2_infirms_on_no_job_only_once_the_vault_s_jobs_are_read_whole():
    """M7455: the vault's listing read before its latency taken as « no job »."""
    assert predicats.h2({**BREE, **_jobs()}, AT, LATER) == "infirme"
    soon = AT + timedelta(seconds=40)
    listed = {JOBS: catalog.Reading(JOBS, catalog.LIGNES, rows=[{"operation": "Backup",
                                                                 "start": (AT - timedelta(minutes=25)).isoformat()}])}
    assert predicats.h2({**BREE, **listed}, AT, soon) == "inconnu"
    assert predicats.h2({**BREE, **listed}, AT, LATER) == "infirme"
    for etat in (catalog.EN_ATTENTE, catalog.ECHEC, catalog.REFUSEE):
        assert predicats.h2({**BREE, JOBS: catalog.Reading(JOBS, etat)}, AT, LATER) == "inconnu"


def test_each_enquiry_computes_its_predicates_cited_or_not_and_shows_them(t1486):
    msgs = []

    def modele(prompt, texte, outil, timeout):
        msgs.append(texte)
        return {"geste": "conclure"}

    e = _enquete(Lecteur({SERIE: catalog.Lu(BREE[SERIE].rows, AT + timedelta(minutes=4)),
                          JOBS: [{"operation": "Backup", "start": (PIC - timedelta(seconds=31)).isoformat()}]}),
                 fiche=t1486, modele=modele)
    assert e.verdicts_code == {"T1486-H1": "infirme", "T1486-H2": "confirme"} and e.hypotheses == []
    assert "T1486-H1 [mesuree]" in msgs[0] and "(now: infirme)" in msgs[0]
    cited = loop.verifier([{"id": "T1486-H2", "verdict": "infirme", "preuves": []}], t1486, e.lectures,
                          code=e.verdicts_code)
    assert cited[0].verdict == "confirme" and cited[0].par == "code" and cited[0].desaccord


# ── The vault's reads: DOS4's code, on the enquiry's windows (M7456, M7457) ─────────────────────────

T = datetime(2026, 11, 10, 2, 35, 56, tzinfo=timezone.utc)


class Coffre:
    """A VM of the bench and its vault, on the fake Azure."""

    def __init__(self):
        self.now = T + timedelta(minutes=40)
        self.f = f = FakeAzure()
        f.clock = lambda: self.now
        sub = f.add_subnet("rg-bench", "vnet", "app", None)
        self.vm = f.add_vm("rg-bench", "vm-enq5a", [{"rg": "rg-bench", "name": "vm-enq5a-nic", "ips": ["10.0.1.4"],
                                                     "subnet": sub, "nsg": None}])
        self.c = c = AzureConnector(dry_run=False, read_only=True)
        c._network, c._compute, c._rest, c._backup = f.network, f.compute, f.rest, f.backup
        c._subscription_id = "s"
        self.vault = f"{self.vm.split('/providers/')[0]}/providers/Microsoft.RecoveryServices/vaults/rsv-bench"

    def reads(self, **kw):
        return self.c.enquiry_reads(self.vm, T, vault="rsv-bench", vault_rg="rg-bench", now=self.now, **kw)


def test_the_vault_s_jobs_are_dos4_s_read_on_the_thirty_minutes_before_the_signal():
    w = Coffre()
    w.f.backup_job(w.vm, T - timedelta(seconds=157), T + timedelta(minutes=20))
    w.f.backup_job(w.vm, T - timedelta(minutes=45), T - timedelta(minutes=30))
    w.f.backup_job(w.vm, T + timedelta(minutes=2), None)
    readings, calls = w.reads(only=[JOBS])
    lu = readings[JOBS]
    assert lu.etat == catalog.LIGNES and [r["start"] for r in lu.rows] == [(T - timedelta(seconds=157)).isoformat()]
    assert lu.rows[0]["operation"] == "Backup" and calls >= 1


def test_the_vault_s_activity_is_its_log_and_its_children_s_its_reads_set_aside():
    """M7457: a read of the vault (`…/read`) kept as one of its writes, or an event of another vault."""
    w = Coffre()
    item = w.vault + "/backupFabrics/Azure/protectionContainers/c/protectedItems/vm"
    w.f.log(item, "Microsoft.RecoveryServices/vaults/backupFabrics/protectionContainers/protectedItems/delete",
            at=T - timedelta(minutes=20))
    w.f.log(w.vault, "Microsoft.RecoveryServices/vaults/backupconfig/write", at=T - timedelta(minutes=10))
    w.f.log(w.vault, "Microsoft.RecoveryServices/vaults/read", at=T - timedelta(minutes=5))
    w.f.log(w.vault + "-other", "Microsoft.RecoveryServices/vaults/backupconfig/write", at=T - timedelta(minutes=5))
    w.f.log(w.vault, "Microsoft.RecoveryServices/vaults/backupconfig/write", at=T - timedelta(minutes=70))
    readings, _ = w.reads(only=[ACTIVITE])
    lu = readings[ACTIVITE]
    ops = sorted({r["operation"] for r in lu.rows})
    assert lu.etat == catalog.LIGNES and ops == [
        "Microsoft.RecoveryServices/vaults/backupFabrics/protectionContainers/protectedItems/delete",
        "Microsoft.RecoveryServices/vaults/backupconfig/write"]
    assert all(r["resource"].lower().startswith(w.vault.lower()) and not r["resource"].lower().endswith("-other")
               for r in lu.rows)


def test_a_vault_read_that_fails_is_unreadable_an_unknown_vault_refused_a_dry_run_reads_nothing():
    w = Coffre()
    w.f.rest_denied.add("eventtypes")
    readings, _ = w.reads(only=[ACTIVITE])
    assert readings[ACTIVITE].etat == catalog.ECHEC
    none, calls = w.c.enquiry_reads(w.vm, T, vault="", now=w.now)
    assert {r.etat for r in none.values()} == {catalog.REFUSEE} and calls == 0
    w.c.dry_run = True
    dry, calls = w.reads()
    assert set(dry) == {JOBS, ACTIVITE} and {r.etat for r in dry.values()} == {catalog.REFUSEE} and calls == 0


def test_the_loop_s_reader_hands_the_vault_s_reads_to_the_adapter_with_the_code_s_vault():
    w = Coffre()
    w.f.backup_job(w.vm, T - timedelta(seconds=157), T + timedelta(minutes=20))
    read = lecteur.Lecteur(T, arm=w.c, now=lambda: w.now)
    rows = read(catalog.READS[JOBS], {"vm": w.vm, "vault": w.vault})
    assert isinstance(rows, list) and len(rows) == 1
    w.f.rest_denied.add("eventtypes")
    assert read(catalog.READS[ACTIVITE], {"vm": w.vm, "vault": w.vault}) is None     # failed, never empty


# ── ENQ5v (#1221; §9.7): the vault's listing asked on the read's window, never on the service's default ───
# The fake's default range (`jobs_default_range`) is a hypothesis, unmeasured: bree's backup of 10/11 02:33:19,
# seen in the vault, read 0 rows by the capture of 26/11. Whatever that range is, the read asks its own.

def test_an_episode_read_days_later_still_reads_the_vault_s_job_of_its_window():
    """M7811: the listing asked without its window — an episode captured sixteen days later reads « no job »."""
    w = Coffre()
    w.now = T + timedelta(days=16)
    w.f.jobs_default_range = timedelta(hours=24)
    w.f.backup_job(w.vm, T - timedelta(seconds=157), T + timedelta(minutes=20))
    w.f.backup_job(w.vm, w.now - timedelta(hours=1), w.now - timedelta(minutes=40))     # of the day, not the window's
    lu = w.reads(only=[JOBS])[0][JOBS]
    assert lu.etat == catalog.LIGNES and [r["start"] for r in lu.rows] == [(T - timedelta(seconds=157)).isoformat()]


def test_the_dossier_s_ten_days_of_jobs_are_asked_whole():
    """M7811 too: the dossier's `backup_jobs` (T − 10 days → T + 10 min), read 40 minutes after T, keeps the job
    of the day before — an unfiltered listing that gives one day only would say the record has none."""
    w = Coffre()
    w.f.jobs_default_range = timedelta(hours=24)
    w.f.backup_job(w.vm, T - timedelta(seconds=157), T + timedelta(minutes=20))
    w.f.backup_job(w.vm, T - timedelta(days=3), T - timedelta(days=3) + timedelta(minutes=20))
    lu = w.c.dossier_reads(w.vm, T, vault="rsv-bench", vault_rg="rg-bench", only=["backup_jobs"],
                           now=w.now)[0]["backup_jobs"]
    assert lu.etat == catalog.LIGNES and len(lu.rows) == 2


def test_the_vault_s_filter_is_the_service_s_form_in_utc_widened_by_its_margin():
    """M7812, M7814, M7815: the hour on 24 hours where the service reads 12 and AM/PM; the upper bound past the
    moment of the read; the lower margin dropped."""
    from glorfindel.providers.azure import dossier_reads
    at = datetime(2026, 11, 11, 16, 17, 40, tzinfo=timezone.utc)
    assert dossier_reads.jobs_filter(at - timedelta(minutes=30), at) == (
        "startTime eq '2026-11-11 02:47:40 PM' and endTime eq '2026-11-12 04:17:40 PM'")
    assert dossier_reads.jobs_filter(at - timedelta(minutes=30), at, at + timedelta(hours=2)) == (
        "startTime eq '2026-11-11 02:47:40 PM' and endTime eq '2026-11-11 06:17:40 PM'")      # never past now
    assert dossier_reads.jobs_filter(at - timedelta(minutes=30), at, at - timedelta(hours=1)).endswith(
        "endTime eq '2026-11-11 04:17:40 PM'")                                                # never before the end
    paris = timezone(timedelta(hours=1))
    assert dossier_reads.jobs_filter(datetime(2026, 11, 10, 1, 5, tzinfo=paris), datetime(2026, 11, 10, 13, 0)) == (
        "startTime eq '2026-11-09 11:05:00 PM' and endTime eq '2026-11-11 01:00:00 PM'")
    assert dossier_reads.jobs_filter(datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc), at).startswith(
        "startTime eq '2026-11-10 12:00:00 AM'")


def test_a_long_backup_still_listed_if_the_service_compares_the_end():
    """M7813: the upper bound not widened — if the service compares its bounds to a job's end (unmeasured: the
    fake's `jobs_filter_by`), a backup started 157 s before T whose transfer ends three hours later falls out of
    the listing, read days after."""
    w = Coffre()
    w.now = T + timedelta(days=16)
    w.f.jobs_filter_by = "end"
    w.f.backup_job(w.vm, T - timedelta(seconds=157), T + timedelta(hours=3))
    lu = w.reads(only=[JOBS])[0][JOBS]
    assert lu.etat == catalog.LIGNES and [r["start"] for r in lu.rows] == [(T - timedelta(seconds=157)).isoformat()]


def test_a_filter_the_service_refuses_is_a_failed_read_never_no_job():
    """The listing refused (400 on its `$filter`) is unreadable, as any failed read: never `vide`."""
    from glorfindel.providers.azure import dossier_reads
    w = Coffre()
    w.f.backup_job(w.vm, T - timedelta(seconds=157), T + timedelta(minutes=20))
    real = dossier_reads.jobs_filter
    try:
        dossier_reads.jobs_filter = lambda start, end, now=None: "startTime ge 'hier'"
        assert w.reads(only=[JOBS])[0][JOBS].etat == catalog.ECHEC
    finally:
        dossier_reads.jobs_filter = real


# ── What the model is told: the marker, and the reads permitted ────────────────────────────────────

def test_the_prompt_of_the_enquiry_says_not_served_apart_from_sans_objet():
    text = " ".join(message.ENQUIRY_PROMPT.split())
    assert "not served yet" in text and "a read not served yet)" not in text


# ── The review of 80b4fd7d (ENQ5a): never `vide` without the source's word, the rule's crossing, the reads
# « after », the horizon on the same counter, the cadence ──────────────────────────────────────────

def test_a_horizon_row_there_but_null_is_nothing_ingested_never_not_said():
    """M7465: a read that tells its ingestion, and said nothing ingested (or nothing), read `vide` once the
    declared latency passed."""
    rien = lecteur.serie([{"Minute": None, "Horizon": None}])
    assert rien.dit is True and rien.ingere is None and rien.rows == []
    muet = lecteur.serie([])
    assert muet.dit is False and muet.ingere is None
    read = catalog.READS[SERIE]
    for lu in (rien, muet):
        got = catalog.outcome(read, lu.rows, system="linux", at=AT, now=AT + timedelta(hours=3), ingere=lu.ingere)
        assert got.etat == catalog.EN_ATTENTE and got.why


def _regle() -> str:
    import yaml
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "glorfindel/rules/azure/detection_rules.yaml"
    rules = yaml.safe_load(path.read_text(encoding="utf-8"))
    rules = rules.get("rules", rules) if isinstance(rules, dict) else rules
    return next(r["query"] for r in rules if r.get("name") == "ransomware-disk-write")


def test_the_first_crossing_is_the_shipped_rule_s_own():
    """M7466: `PremierPic` on one sample past 25 MB/s whatever the step — not the rule's crossing, which a
    fine step reads on two samples' mean past 45 MB/s."""
    rule, q = _regle(), lecteur.texte(catalog.READS[SERIE], {"vm": VM}, AT)
    for line in ("| extend Fine = isnotnull(Step) and Step <= 25s",
                 "| extend Rate = iff(Fine, iff(Gap <= 25s, (CounterValue + PrevValue) / 2, real(null)), CounterValue)"):
        assert line in rule and line in q, line
    (fine, coarse), = re.findall(r"\(Fine and Rate > (\d+)\) or \(not\(Fine\) and Rate > (\d+)\)", rule)
    assert f"| extend Pic = (Fine and Rate > {fine}) or (not(Fine) and Rate > {coarse})" in q
    assert int(fine) == predicats.SEUIL_PIC_FIN * 1_000_000 and int(coarse) == predicats.SEUIL_PIC * 1_000_000
    assert "summarize Step = minif(Gap, Gap >= 1s)" in rule and "summarize Step = minif(Gap, Gap >= 1s)" in q
    assert re.search(r"Step <= (\d+)s", rule).group(1) == str(predicats.PAS_FIN_S)
    assert "PremierPic = minif(PicAt, Pic)" in q and "prev(CounterValue)" in q


def test_a_peak_before_the_true_crossing_is_not_the_first_minute():
    """A lone sample past 25 MB/s on a fine step is no crossing (`PremierPic` empty): the minute that counts
    is the crossing's, the next one 17 MB/s — never infirmed on the two minutes before."""
    lone = M1 - timedelta(minutes=1)
    rows = [_minute(lone, 3.0), _minute(M1, 12.0, pic=PIC), _minute(M2, 17.0, pic=M2)]
    rows[0]["MaxMBs"] = 30.0                                       # past 25 on one sample, no crossing
    assert predicats.h1(_serie(*rows), AT, LATER) == "inconnu"
    rows[2]["MoyenneMBs"] = 11.0
    assert predicats.h1(_serie(*rows), AT, LATER) == "infirme"


def test_the_reads_after_the_escalation_run_five_minutes_past_the_signal_never_past_now():
    """M7467, M7468: `root_commands` and `disk_write_after_escalation` read what follows the escalation —
    five minutes past T — but never past the moment the query runs."""
    for rid in ("root_commands", "disk_write_after_escalation"):
        read = catalog.READS[rid]
        assert catalog.window(read, AT) == (AT - timedelta(minutes=10), AT + timedelta(minutes=5))
        assert "après" in read.phrase and "signal" in read.phrase
        live = lecteur.texte(read, {"vm": VM}, AT, AT + timedelta(seconds=60))
        assert "datetime(2026-11-10T02:35:10Z))" in live
        later = lecteur.texte(read, {"vm": VM}, AT, AT + timedelta(days=1))
        assert "datetime(2026-11-10T02:39:10Z))" in later
    assert catalog.READS["heartbeat_gap"].ahead == timedelta(0)


def _horizon(query: str) -> str:
    return query.split("let horizon = toscalar(", 1)[1].split(");", 1)[0]


def _keeps(block: str, row: dict) -> bool:
    """What the block's `where` lines on ObjectName and CounterName keep of `row`."""
    for objets in re.findall(r'\| where ObjectName in \(([^)]*)\)', block):
        if row["ObjectName"] not in re.findall(r'"([^"]+)"', objets):
            return False
    for counter in re.findall(r'\| where CounterName == "([^"]+)"', block):
        if row["CounterName"] != counter:
            return False
    return True


def test_the_horizon_reads_the_series_own_counter():
    """M7469: a VM that sends its CPU, not its disk, said ingested past the window — its disk empty `vide`."""
    q = lecteur.texte(catalog.READS[SERIE], {"vm": VM}, AT)
    cpu = {"ObjectName": "Processor", "CounterName": "% Processor Time"}
    disk = {"ObjectName": "Logical Disk", "CounterName": "Disk Write Bytes/sec"}
    serie = q.split("let samples = Perf", 1)[1].split(";", 1)[0]
    assert not _keeps(_horizon(q), cpu) and _keeps(_horizon(q), disk)
    assert _keeps(serie, disk) and not _keeps(serie, cpu)


def test_the_cadence_is_the_step_s_or_the_most_common_never_the_largest():
    """M7470: one minute of seven samples (a jitter on the bin) makes every minute of six incomplete."""
    minutes = [_minute(M1 + timedelta(minutes=i), 30.0 if i == 2 else 5.0, n=7 if i == 1 else 6,
                       pic=PIC if i == 0 else None) for i in range(4)]
    assert predicats.h1(_serie(*minutes), AT, LATER) == "confirme"
    stepped = [dict(m, PasS=10) for m in minutes]
    assert predicats.h1(_serie(*stepped), AT, LATER) == "confirme"
    half = [dict(m, PasS=10, Echantillons=3) if i == 2 else dict(m, PasS=10) for i, m in enumerate(minutes)]
    assert predicats.h1(_serie(*half), AT, LATER) != "confirme"
