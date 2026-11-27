"""ENQ5a (#1162): the capture of an episode's reads at the bench (`scripts/capture_enquete.py`), and the
harness that plays a folder of them (`scripts/harness_enquete.py`, `llm_smoke.py --enquete --captures`).

The capture is the maintainer's gesture, under his rights: here its readers are always replaced by fake
answers — no Azure call, no model call. What is checked: it reads each read of the catalogue anchored on
the signal's hour, only by the reads it declares (read only); it never writes in the repository; it
leaves no real name, GUID nor e-mail address in its file unless asked; the harness plays the file, as
the watch would have read it at the moment of its decision, and refuses a folder inside the repository.
Mutants M7443–M7462 (scripts/mutants/ENQ5a.py).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from glorfindel.enquiry import catalog, knowledge, loop

ROOT = Path(__file__).resolve().parents[2]
SUB = "12345678-aaaa-bbbb-cccc-1234567890ab"            # « the bench's » ids, made up here
VM = f"/subscriptions/{SUB}/resourceGroups/rg-banc-reel/providers/Microsoft.Compute/virtualMachines/vm-reelle"
WS = "87654321-dddd-eeee-ffff-ba0987654321"
AT = "2026-11-10T02:34:10Z"
T = datetime(2026, 11, 10, 2, 34, 10, tzinfo=timezone.utc)
OPERATOR = "operateur.reel@client.example"          # a reserved domain (RFC 2606)
OID = "abcdef01-2345-6789-abcd-ef0123456789"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _subscription(monkeypatch):
    """The operator's shell: the bench's subscription set, no principal of the environment."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", SUB)
    for var in ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_CLIENT_CERTIFICATE_PATH", "AZURE_FEDERATED_TOKEN_FILE"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="module")
def cap():
    return _load("capture_enquete")


@pytest.fixture(scope="module")
def he():
    return _load("harness_enquete")


class Banc:
    """The bench's answers, made up: each KQL query by its table, the vault's reads, the VM's system."""

    def __init__(self, fail=()):
        self.queries, self.arm, self.fail = [], [], set(fail)

    def kql(self, query, span):
        self.queries.append((query, span))
        if "Syslog" in query and "sudo" in query and "root_commands" in self.fail:
            raise RuntimeError("HTTP 429")
        if query.lstrip().startswith("let debut") and "Perf" in query:      # ENQ5b: heartbeat_gap writes its window too
            minute = T.replace(second=0) - timedelta(minutes=1)
            return [{"Minute": minute, "InstanceName": "/", "Echantillons": 6, "MoyenneMBs": 59.4, "MaxMBs": 96.2,
                     "Dernier": minute + timedelta(seconds=50), "PremierPic": minute + timedelta(seconds=10),
                     "IngereA": minute + timedelta(seconds=100), "Computer": "vm-reelle"},
                    {"Minute": None, "Horizon": T + timedelta(minutes=5)}]
        if "sudo" in query:
            return [{"TimeGenerated": T - timedelta(minutes=3), "Computer": "vm-reelle",
                     "SyslogMessage": "alice : TTY=pts/0 ; PWD=/srv/rg-banc-reel ; USER=root ; COMMAND=/bin/bash"}]
        return []

    def vm_os(self, vm):
        return "Linux"

    def enquiry_reads(self, vm, at, *, vault, vault_rg, only, now):
        self.arm.append((vm, at, vault, vault_rg, tuple(only)))
        rid = only[0]
        if rid == "vault_jobs":
            rows = [{"name": "job-1", "operation": "Backup", "status": "InProgress",
                     "start": (at - timedelta(minutes=2)).isoformat(), "end": ""}]
        else:
            rows = [{"at": (at - timedelta(minutes=20)).isoformat(), "operation": "Microsoft.RecoveryServices/"
                     "vaults/backupconfig/write", "status": "Succeeded", "ids": [OID, OPERATOR],
                     "resource": f"/subscriptions/{SUB}/resourceGroups/rg-coffre/providers/Microsoft."
                                 "RecoveryServices/vaults/coffre-reel"}]
        return {rid: catalog.Reading(rid, catalog.LIGNES, rows=rows)}, 1


def _argv(out, *extra):
    return ["--vm", VM, "--at", AT, "--workspace", WS, "--rule", "ransomware-disk-write", "--ttp", "T1486",
            "--expect", "contain", "--label", "an attack of the bench", "--vault", "coffre-reel",
            "--vault-rg", "rg-coffre", "--out", str(out), *extra]


def _capture(cap, tmp_path, *extra, banc=None):
    banc = banc or Banc()
    out = tmp_path / "captures" / "episode.json"
    assert cap.main(_argv(out, *extra), readers=lambda ws: (banc.kql, banc)) == 0
    return banc, out, json.loads(out.read_text(encoding="utf-8"))


# ── Never in the repository (M7458) ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("where", ["capture.json", "docs/capture.json", "tests/unit/x.json"])
def test_a_capture_inside_the_repository_is_refused_before_any_call(cap, where, capsys):
    def readers(ws):
        pytest.fail("a reader was built: a call could follow")
    assert cap.main(_argv(ROOT / where), readers=readers) == 2
    assert "jamais dans le dépôt" in capsys.readouterr().out
    assert not (ROOT / where).exists()


def test_a_capture_already_there_is_never_overwritten(cap, tmp_path):
    out = tmp_path / "x.json"
    out.write_text("{}")
    assert cap.main(_argv(out), readers=lambda ws: pytest.fail("built")) == 2
    assert out.read_text() == "{}"


# ── Read only, each read anchored on the signal (M7459) ──────────────────────────────────────────

def test_the_capture_reads_each_read_of_the_catalogue_anchored_on_the_signal(cap, tmp_path):
    banc, out, doc = _capture(cap, tmp_path)
    assert doc["format"] == "eregion-enquete-capture/1" and doc["systeme"] == "linux"
    kql = [r for r in catalog.READS.values() if r.kind == "kql" and r.id != "successful_auth_from_ip"]
    # WRT1: process_write_audit, a read to measure, by the same runner (apart, in `a_mesurer`).
    kql += [r for r in catalog.A_MESURER.values() if r.kind == "kql"]
    assert len(banc.queries) == len(kql)
    for query, (start, end) in banc.queries:
        assert "ago(" not in query and "datetime(2026-11-10T" in query
        assert start <= T - timedelta(minutes=5) and end >= T and end - start <= timedelta(hours=3)
    assert [a[4] for a in banc.arm] == [("vault_jobs",), ("vault_activity",)]
    assert {(a[2], a[3]) for a in banc.arm} == {("coffre-reel", "rg-coffre")} and {a[1] for a in banc.arm} == {T}
    # The address no row of this episode gives: its read is not made, and said.
    assert "successful_auth_from_ip" in doc["non_lues"] and "successful_auth_from_ip" not in doc["lectures"]
    serie = doc["lectures"]["perf_minute_series"]
    assert serie["ingere_jusqu_a"] == (T + timedelta(minutes=5)).isoformat() and len(serie["lignes"]) == 1
    assert stat.S_IMODE(out.stat().st_mode) == 0o600


def test_a_read_that_fails_is_written_null_never_empty(cap, tmp_path):
    _, _, doc = _capture(cap, tmp_path, banc=Banc(fail={"root_commands"}))
    assert doc["lectures"]["root_commands"] is None and doc["lectures"]["heartbeat_gap"] == []


def test_the_capture_calls_only_reads():
    """The script's own calls on Azure: a query, the adapter's reads, the VM's system — no write."""
    tree = ast.parse((ROOT / "scripts" / "capture_enquete.py").read_text(encoding="utf-8"))
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    writes = {c for c in called if c.startswith(("begin_", "create", "delete", "update", "put", "post", "set_"))}
    assert writes == set()
    assert {"vm_os", "run_query"} <= called


# ── No real identifier left (M7460) ───────────────────────────────────────────────────────────────

def test_no_name_guid_nor_mail_of_the_bench_is_left_in_the_capture(cap, tmp_path):
    _, out, doc = _capture(cap, tmp_path, "--hide", "alice")
    text = out.read_text(encoding="utf-8")
    for real in (SUB, "rg-banc-reel", "vm-reelle", WS, "coffre-reel", "rg-coffre", OPERATOR, OID, "alice"):
        assert real not in text, real
    assert "vm-smoke" in text and "vault-smoke" in text and "@example.invalid" in text
    assert doc["capture"]["pseudonymise"] is True
    kept = _capture(cap, tmp_path / "kept", "--keep-names")[2]
    assert "vm-reelle" in json.dumps(kept) and kept["capture"]["pseudonymise"] is False


def test_a_name_is_hidden_whole_never_inside_a_longer_word(cap):
    p = cap.Pseudonymes({"rg": "rg-x", "vm-a": "vm-smoke"})
    assert p.texte("/resourceGroups/rg/x vm-a vm-ab morgue") == "/resourceGroups/rg-x/x vm-smoke vm-ab morgue"


# ── The harness plays the captures (M7461, M7462) ─────────────────────────────────────────────────

def test_the_harness_plays_a_folder_of_captures_as_its_cases(cap, he, tmp_path):
    _capture(cap, tmp_path)
    [case] = he.charger_captures(tmp_path / "captures")
    assert case["label"].startswith("captured: ") and case["expect"] == "contain" and case["now_s"] == 60
    decided = []

    def decide(state):
        decided.append(state)
        return {"action": "isolate_vm", "escalate": False, "confidence": 0.9}

    gestes = [{"geste": "lire", "id": "root_commands"}, {"geste": "conclure"}]
    out = he.un_cas(case, modele=lambda *a: gestes.pop(0), decide=decide,
                    etat=lambda ttp, raw: {"signal": {"ttp": ttp, "raw_signal": raw}}, budget=loop.Budget(),
                    read_delay=0, base=knowledge.charger(), now_s=600)
    e = out["enquete"]
    assert out["good"] and e["lectures"]["perf_minute_series"] == "lignes" and e["lectures"]["vault_jobs"] == "lignes"
    assert e["verdicts_code"]["T1486-H1"] == "confirme"
    ctx = decided[0]["signal"]["raw_signal"]["investigative_context"]
    assert ctx["root_commands"][0]["Computer"] == "vm-smoke"      # the captured row, pseudonymised


def test_a_capture_replayed_early_shows_only_what_had_been_ingested(he):
    """M7461: the rows ingested after the moment of the decision shown to it, a capture's hindsight."""
    entry = {"lignes": [{"Minute": "2026-11-10T02:33:00+00:00", "Dernier": "2026-11-10T02:33:50+00:00",
                         "IngereA": "2026-11-10T02:34:40+00:00"},
                        {"Minute": "2026-11-10T02:34:00+00:00", "Dernier": "2026-11-10T02:34:50+00:00",
                         "IngereA": "2026-11-10T02:35:40+00:00"}], "ingere_jusqu_a": "2026-11-10T02:40:00+00:00"}
    early = he.au_moment(entry, T + timedelta(seconds=60))
    assert [r["Minute"][11:16] for r in early.rows] == ["02:33"]
    assert early.ingere == datetime(2026, 11, 10, 2, 33, 50, tzinfo=timezone.utc)
    late = he.au_moment(entry, T + timedelta(minutes=10))
    assert len(late.rows) == 2 and late.ingere == datetime(2026, 11, 10, 2, 40, tzinfo=timezone.utc)
    assert he.au_moment(None, T) is None and he.au_moment([{"a": 1}], T) == [{"a": 1}]


@pytest.mark.parametrize("bad, why", [
    ({"format": "autre"}, "pas une capture"),
    ({"format": "eregion-enquete-capture/1", "expect": "maybe"}, "expect parmi"),
    ({"format": "eregion-enquete-capture/1", "expect": "act", "at": AT, "lectures": {}}, "sans allowed"),
    ({"format": "eregion-enquete-capture/1", "expect": "contain", "at": "hier", "lectures": {}}, "son heure"),
])
def test_a_capture_that_does_not_read_refuses_the_whole_folder(he, tmp_path, bad, why):
    (tmp_path / "a.json").write_text(json.dumps(bad))
    with pytest.raises(he.CaptureRefusee, match=why):
        he.charger_captures(tmp_path)


def test_the_harness_never_reads_captures_inside_the_repository(he, tmp_path):
    """M7462: a folder of the repository taken for captures — the bench's names would enter it."""
    for where in (ROOT, ROOT / "tests"):
        with pytest.raises(he.CaptureRefusee, match="jamais dans le dépôt"):
            he.charger_captures(where)
    with pytest.raises(he.CaptureRefusee, match="aucune capture"):
        he.charger_captures(tmp_path)


def test_llm_smoke_refuses_a_folder_of_captures_it_cannot_play_before_any_call(monkeypatch, capsys, tmp_path):
    smoke = _load("llm_smoke")
    import litellm
    monkeypatch.setattr(litellm, "completion", lambda **kw: pytest.fail("a call was made"))
    for extra in (["--captures", str(ROOT / "docs")], ["--captures", str(tmp_path)],
                  ["--captures", str(tmp_path), "--precedents"]):
        monkeypatch.setattr(sys, "argv", ["llm_smoke.py", "--enquete", "--models", "m/a", "--max-usd", "1", *extra])
        assert smoke.main() == 2
        assert "nothing run" in capsys.readouterr().out


def test_make_passes_the_captures_and_the_moment_of_their_replay():
    if shutil.which("make") is None:
        pytest.skip("make not installed")
    out = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "llm-compare", "MODELS=m/a",
                          "ENQUETE=1", "CAPTURES=/home/op/eregion-banc/captures", "CAPTURE_NOW_S=120", "MAX_USD=5"],
                         capture_output=True, text=True, timeout=60).stdout
    assert ('--captures "/home/op/eregion-banc/captures" --capture-now-s 120 --max-usd 5' in out)
    cap = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "enquete-capture", f"ENQ_VM={VM}",
                          f"ENQ_AT={AT}", f"ENQ_WORKSPACE={WS}", "ENQ_EXPECT=caution",
                          "ENQ_OUT=/home/op/eregion-banc/captures/a.json", "ENQ_VAULT=v", "ENQ_VAULT_RG=g"],
                         capture_output=True, text=True, timeout=60).stdout
    assert "scripts/capture_enquete.py" in cap and '--expect "caution"' in cap and '--vault "v" --vault-rg "g"' in cap


# ── The review of 80b4fd7d (ENQ5a) ────────────────────────────────────────────────────────────────

def test_a_capture_25_minutes_late_replayed_at_600_s_is_waiting_never_empty(he):
    """M7465: nothing ingested by the moment of the decision — the rows came 25 minutes late — read
    `vide` once the declared latency passed: « no write » where nothing had arrived."""
    late = []
    for i in range(-2, 3):
        minute = T.replace(second=0) + timedelta(minutes=i)
        late.append({"Minute": minute.isoformat(), "InstanceName": "/", "Echantillons": 6, "MoyenneMBs": 59.4,
                     "Dernier": (minute + timedelta(seconds=50)).isoformat(),
                     "IngereA": (minute + timedelta(minutes=25)).isoformat()})
    entry = {"lignes": late, "ingere_jusqu_a": (T + timedelta(minutes=30)).isoformat(), "ingestion_dite": True}
    now = T + timedelta(seconds=600)
    lu = he.au_moment(entry, now)
    assert lu.rows == [] and lu.ingere is None and lu.dit is True
    e = loop.enqueter(detection={"Computer": "vm-smoke", "MaxWrite": 147000000}, vm=he.RID,
                      regle="ransomware-disk-write", technique="T1486", systeme="linux",
                      fiche=knowledge.charger().pour("ransomware-disk-write", "T1486"),
                      lecteur=he.Enregistre({"perf_minute_series": entry, "vault_jobs": [], "vault_activity": []},
                                            0, now=now),
                      modele=lambda *a: {"geste": "conclure"}, at=T, maintenant=lambda: now, coffre=he.VAULT_RID)
    assert e.lectures["perf_minute_series"].etat == catalog.EN_ATTENTE
    assert "perf_minute_series" in e.trous and e.verdicts_code["T1486-H1"] == "en_attente"


def test_a_case_replayed_at_its_signal_s_own_moment(he):
    """`--capture-now-s 0`: the signal's moment, never the default of 600 s."""
    case = he.CASES[5]                                      # ransomware by day: the vault's jobs empty
    kw = dict(modele=lambda *a: {"geste": "conclure"}, decide=lambda s: {"action": "isolate_vm"},
              etat=lambda ttp, raw: {"signal": {}}, budget=loop.Budget(), read_delay=0, base=knowledge.charger())
    assert he.un_cas(case, now_s=0, **kw)["enquete"]["lectures"]["vault_jobs"] == catalog.EN_ATTENTE
    assert he.un_cas(case, **kw)["enquete"]["lectures"]["vault_jobs"] == catalog.VIDE


def test_ip_addresses_and_the_reads_not_made_are_hidden_too(cap):
    """M7471: an address of the bench left in a capture."""
    p = cap.Pseudonymes({})
    text = p.texte("Accepted password for alice from 10.1.2.3 port 52144 ; 10.1.2.3 again ; 198.51.100.7")
    assert "10.1.2.3" not in text and text.count("192.0.2.1") == 2 and "198.51.100.7" in text
    assert "alice" in text                                  # a user name of Syslog stays, unless --hide
    assert p.texte("2026-11-10T02:33:00+00:00 v1.2") == "2026-11-10T02:33:00+00:00 v1.2"


def test_the_reads_not_made_pass_through_the_pseudonyms(cap, tmp_path):
    args = cap._args(_argv(tmp_path / "o.json"))
    prep = cap.preparer(args)
    lu = {"systeme": "linux", "lectures": {}, "non_lues": {"x": "vm-reelle 10.9.8.7"}, "requetes": 0}
    doc = json.loads(cap.ecrire(args, prep, lu, T).read_text(encoding="utf-8"))
    assert doc["non_lues"]["x"] == "vm-smoke 192.0.2.1"


@pytest.mark.parametrize("sub, why", [("", "absent"), ("99999999-9999-9999-9999-999999999999", "abonnement")])
def test_the_subscription_of_the_shell_is_the_vm_s_or_nothing_is_read(cap, monkeypatch, tmp_path, capsys, sub, why):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", sub)
    assert cap.main(_argv(tmp_path / "x.json"), readers=lambda ws: pytest.fail("built")) == 2
    assert why in capsys.readouterr().out


def test_a_principal_of_the_environment_is_said(cap, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AZURE_CLIENT_ID", "00000000-0000-0000-0000-0000000000cc")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "not-a-secret")
    banc = Banc()
    assert cap.main(_argv(tmp_path / "y.json"), readers=lambda ws: (banc.kql, banc)) == 0
    assert "passe avant az login" in capsys.readouterr().out


def test_a_capture_in_the_main_checkout_a_worktree_shares_is_refused(cap, monkeypatch, tmp_path):
    """M7472: a worktree's guard that only knows its own folder — the main checkout takes the capture."""
    main = tmp_path / "eregion"
    (main / ".git").mkdir(parents=True)

    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, stdout=f"{main / '.git'}\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    assert main.resolve() in cap.depots() and ROOT in cap.depots()
    with pytest.raises(cap.Refus, match="jamais dans le dépôt"):
        cap.hors_du_depot(str(main / "captures" / "x.json"))
    assert cap.hors_du_depot(str(tmp_path / "ailleurs.json")).name == "ailleurs.json"
