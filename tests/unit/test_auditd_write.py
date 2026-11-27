"""WRT1 (#1275): who writes under Linux, by auditd — the write watches (`infra/terraform/scripts/
auditd_write.sh`, off by default), and `process_write_audit`, their reader (`glorfindel/auditd_write.py`),
declared in the enquiry's catalogue apart from what the model sees (Q8; `docs/design/enquete-raisonnee.md`
§4.4, §9.7).

No Azure call, no model call: the workspace is the KQL subset here (`kql_subset`, the query run as written on
lines the test writes). What is held:
- the read is in the catalogue's `A_MESURER`, never in `READS`: neither `investigate`, nor `decide`, nor the
  loop sees it; `process_write_io` stays as PIO1 left it;
- its KQL is the code's: the VM's id checked; the window anchored on the signal; the VM's lines alone, the
  watch's keys alone, in local6 from auditd's plugin;
- the beat is never a writer, and it alone vouches for an absence: no beat is `sans_objet`, never `vide`;
- its refusals are said: a 403, the table absent, a 404, a delay, an answer unreadable — `echec`; its budget
  taken first, refused said;
- an event with two SYSCALL records (a line written to look like it) is never attributed;
- the paths are kept as their folder and extension, a home's owner hidden; the executable's path is the
  kernel's, bounded, never trusted;
- the capture reads it apart (`a_mesurer`), never in what the harness plays;
- the collection is declared in Terraform, off by default and without effect off auditd, its folders
  bounded; off, the extension's script is AUD1's to the byte (the `terraform test` file plans it).
Mutants M8193–M8206 (scripts/mutants/WRT1.py).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from glorfindel import auditd_write, read_budget
from glorfindel.enquiry import catalog, knowledge, loop

from . import kql_subset

ROOT = Path(__file__).resolve().parents[2]
TF = ROOT / "infra/terraform"
FRAGMENT = TF / "scripts/auditd_write.sh"
SUB = "12345678-aaaa-bbbb-cccc-1234567890ab"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-banc/providers/Microsoft.Compute/virtualMachines/vm-reelle"
VM2 = VM.replace("vm-reelle", "vm-autre")
T = datetime(2026, 11, 10, 2, 34, 10, tzinfo=timezone.utc)
LATER = T + timedelta(hours=1)
WRT = "process_write_audit"
UNSET = 4294967295


# ── Lines as audisp-syslog sends them ─────────────────────────────────────────────────────────────

def _q(text: str) -> str:
    """A string as the kernel writes it: quoted, or hex when it holds a space or a quote."""
    if any(c in text for c in ' "') or any(ord(c) < 0x21 or ord(c) > 0x7e for c in text):
        return text.encode().hex().upper()
    return f'"{text}"'


def _stamp(serial: int) -> str:
    return f"msg=audit(1762741000.{serial % 1000:03d}:{serial}):"


def _syscall(serial, *, exe, uid=0, auid=UNSET, pid=4000, key=catalog.WRT_KEY, syscall=257):
    return (f"type=SYSCALL {_stamp(serial)} arch=c000003e syscall={syscall} success=yes exit=3 a0=ffffff9c "
            f"a1=7ffd1 a2=241 a3=1b6 items=2 ppid=1 pid={pid} auid={auid} uid={uid} gid=0 euid={uid} suid=0 "
            f"fsuid=0 egid=0 sgid=0 fsgid=0 tty=(none) ses=4294967295 comm=\"x\" exe={_q(exe)} "
            f"subj=unconfined key=\"{key}\"\x1dARCH=x86_64 SYSCALL=openat AUID=\"unset\" UID=\"root\"")


def _path(serial, item, name, nametype):
    return (f"type=PATH {_stamp(serial)} item={item} name={_q(name) if name else '(null)'} inode=12 dev=08:01 "
            f"mode=0100644 ouid=0 ogid=0 rdev=00:00 nametype={nametype} cap_fp=0 cap_fi=0 cap_fe=0")


def _line(message, at, rid=VM, facility="local6", process="audisp-syslog"):
    return {"Type": "Syslog", "TimeGenerated": at, "Facility": facility, "ProcessName": process,
            "SyslogMessage": message, "Computer": "vm-reelle", "_ResourceId": rid}


def event(serial, at, exe, *names, rid=VM, extra=(), **kw) -> list[dict]:
    """One watch event: its SYSCALL, a PARENT record, then an entry per name (CREATE)."""
    records = [_syscall(serial, exe=exe, **kw), f'type=CWD {_stamp(serial)} cwd="/root"',
               _path(serial, 0, "/var/www/", "PARENT")]
    records += [_path(serial, i + 1, n, "CREATE") for i, n in enumerate(names)]
    return [_line(r, at, rid=rid) for r in (*records, *extra)]


def beat(serial, at, rid=VM):
    return event(serial, at, "/usr/bin/dash", "/var/lib/eregion/write-watch/beat", key=catalog.WRT_BEAT_KEY,
                 rid=rid)


def _run(lines, *, now=LATER, **kw):
    seen = []

    def kql_run(query, span):
        seen.append((query, span))
        return kql_subset.run(query, lines, now=now)
    return auditd_write.process_write_audit(VM, T, kql_run=kql_run, now=now, **kw), seen


def _alive():
    """The watch's beats, before and past the window."""
    return beat(1, T - timedelta(minutes=4)) + beat(2, T + timedelta(minutes=1))


# ── Declared, never in what the model sees (M8193) ──────────────────────────────────────────────────

def test_declared_apart_never_in_the_reads_the_loop_serves():
    read = catalog.A_MESURER[WRT]
    assert WRT not in catalog.READS and "process_write_io" in catalog.A_MESURER
    assert read.kind == "kql" and read.obj == "vm" and read.params == ("vm",)
    assert read.author == catalog.GUEST_FORGEABLE
    assert read.lookback == timedelta(minutes=5) and read.ahead == timedelta(0)
    assert read.latency_s == catalog.SYSLOG_LATENCY_S
    assert catalog.says(read, catalog.LINUX) == "" and catalog.says(read, catalog.WINDOWS) == catalog.WRT_WINDOWS
    assert WRT not in knowledge.ANNONCEES       # no sheet names it: ENQ5b brings it, after the measure


def test_the_loop_never_permits_it():
    servies, non_servies = loop.permises(None, catalog.LINUX)
    assert WRT not in servies and WRT not in non_servies
    fiche = type("F", (), {"hypotheses": [type("H", (), {"lectures": (WRT,)})()]})()
    servies, non_servies = loop.permises(fiche, catalog.LINUX)
    assert servies == [] and non_servies[WRT].etat == catalog.NON_PERMISE


def test_no_module_of_the_watch_reaches_the_reader():
    users = []
    for path in sorted((ROOT / "glorfindel").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [f"{node.module}.{a.name}" for a in node.names] if isinstance(node, ast.ImportFrom) and node.module
                     else [])
            if any("auditd_write" in n for n in names):
                users.append(path.relative_to(ROOT).as_posix())
    assert users == []
    for rel in ("glorfindel/agent.py", "glorfindel/enquiry/message.py", "glorfindel/enquiry/loop.py",
                "glorfindel/enquiry/fixed.py", "glorfindel/few_shot_examples.yaml"):
        assert WRT not in (ROOT / rel).read_text(encoding="utf-8"), rel
    for sheet in (ROOT / "glorfindel/enquiry/fiches").glob("*.yaml"):
        assert WRT not in sheet.read_text(encoding="utf-8"), sheet.name


def test_the_reader_imports_no_sdk():
    tree = ast.parse((ROOT / "glorfindel/auditd_write.py").read_text(encoding="utf-8"))
    mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.split(".")[0] in ("azure", "requests", "boto3") for m in mods), mods


# ── The query, the code's (M8194, M8195, M8196) ─────────────────────────────────────────────────────

def test_who_modified_files_by_executable_the_most_files_first():
    lines = _alive()
    lines += event(10, T - timedelta(minutes=3), "/usr/bin/tar", "/var/backups/bree-site/site-2026-11-10.tgz")
    for i in range(6):
        lines += event(20 + i, T - timedelta(minutes=2), "/opt/x/chiffre", f"/home/alice/doc{i}.txt.locked",
                       uid=1001, auid=1001, pid=5000)
    lu, seen = _run(lines)
    assert lu.etat == catalog.LIGNES and len(seen) == 1
    first, second = lu.rows
    assert first == {"Executable": "/opt/x/chiffre", "Uid": 1001, "Auid": 1001, "Processus": 1, "Fichiers": 6,
                     "Evenements": 6, "Chemins": ["/home/<u>/*.locked"], "Premier": first["Premier"],
                     "Dernier": first["Dernier"]}
    assert second["Executable"] == "/usr/bin/tar" and second["Uid"] == 0 and second["Auid"] is None
    assert second["Fichiers"] == 1 and second["Chemins"] == ["/var/backups/bree-site/*.tgz"]
    assert all(r["Executable"] != "/usr/bin/dash" for r in lu.rows)     # the beat is never a writer


def test_the_window_is_the_signal_s_and_its_end_is_never_past():
    lines = _alive()
    lines += event(30, T - timedelta(minutes=6), "/usr/bin/cp", "/srv/avant.dat")      # before the window
    lines += event(31, T + timedelta(minutes=2), "/usr/bin/cp", "/srv/apres.dat")      # past its end
    lines += event(32, T - timedelta(minutes=1), "/usr/bin/rsync", "/srv/dedans.dat")
    lu, seen = _run(lines)
    assert [r["Executable"] for r in lu.rows] == ["/usr/bin/rsync"]
    query, (start, end) = seen[0]
    assert "datetime(2026-11-10T02:29:10Z) .. datetime(2026-11-10T02:49:10Z)" in query
    assert "TimeGenerated <= datetime(2026-11-10T02:34:10Z)" in query
    assert start <= T - timedelta(minutes=5) and end >= T + catalog.WRT_HORIZON


def test_only_the_vm_s_lines_its_watch_s_keys_in_local6_from_the_plugin():
    lines = _alive()
    lines += event(40, T - timedelta(minutes=1), "/usr/bin/cp", "/srv/a.dat", rid=VM2)
    lines += event(41, T - timedelta(minutes=1), "/usr/bin/cp", "/srv/b.dat", key="root_command")
    lines += [dict(r, Facility="user") for r in event(42, T - timedelta(minutes=1), "/usr/bin/cp", "/srv/c.dat")]
    lines += [dict(r, ProcessName="logger") for r in event(43, T - timedelta(minutes=1), "/usr/bin/cp", "/srv/d")]
    lines += [dict(r, _ResourceId=VM.upper()) for r in event(44, T - timedelta(minutes=1), "/usr/bin/vi",
                                                             "/srv/e.conf")]
    lu, _ = _run(lines)
    assert [(r["Executable"], r["Chemins"]) for r in lu.rows] == [("/usr/bin/vi", ["/srv/*.conf"])]


@pytest.mark.parametrize("vm", ["vm-reelle", VM + '" or 1 == 1 or "', "/subscriptions/x/../y", ""])
def test_a_vm_that_is_not_a_resource_id_is_refused_before_any_query(vm):
    seen = []
    lu = auditd_write.process_write_audit(vm, T, kql_run=lambda q, s: seen.append(q) or [], now=LATER)
    assert lu.etat == catalog.REFUSEE and seen == []


def test_the_top_is_bounded_and_a_full_answer_said_truncated():
    rows = [{"Battement": False, "Writer": f'"/usr/bin/w{i}"', "WriterUid": "0", "WriterAuid": str(UNSET),
             "Evenements": 1, "Fichiers": i + 1, "Chemins": ['"/srv/a.dat"'], "Processus": 1, "Doubles": 0,
             "Premier": T, "Dernier": T} for i in range(catalog.WRT_ROWS)]
    lu = auditd_write.process_write_audit(VM, T, kql_run=lambda q, s: rows, now=LATER, top=3)
    assert [r["Fichiers"] for r in lu.rows] == [50, 49, 48]
    assert lu.why == catalog.WRT_TRONQUEE.format(catalog.WRT_ROWS)
    lu = auditd_write.process_write_audit(VM, T, kql_run=lambda q, s: rows[:4], now=LATER)
    assert len(lu.rows) == 4 and lu.why == ""


# ── The beat vouches for an absence, alone (M8197, M8198, M8199) ─────────────────────────────────────

def test_no_writer_and_the_beat_past_the_window_is_empty():
    lu, _ = _run(_alive())
    assert lu.etat == catalog.VIDE and lu.rows == []


def test_no_beat_is_sans_objet_never_empty():
    lu, _ = _run([])
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.WRT_SANS_MONTRE


def test_a_beat_that_stopped_before_the_end_is_sans_objet():
    lu, _ = _run(beat(1, T - timedelta(minutes=4)))
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.WRT_TUE


def test_too_early_is_waiting_never_empty_nor_sans_objet():
    soon = T + timedelta(minutes=2)
    lu, _ = _run(beat(1, T - timedelta(minutes=4)), now=soon)
    assert lu.etat == catalog.EN_ATTENTE
    assert lu.why == catalog.WRT_LATENCE.format(catalog.WRT_BEAT_S, catalog.SYSLOG_LATENCY_S)
    lu, _ = _run([], now=soon)
    assert lu.etat == catalog.EN_ATTENTE


def test_a_writer_without_a_beat_is_still_a_writer():
    lu, _ = _run(event(50, T - timedelta(minutes=1), "/usr/bin/shred", "/srv/x.db"))
    assert lu.etat == catalog.LIGNES and lu.rows[0]["Executable"] == "/usr/bin/shred"


# ── Forged lines, never chosen (M8200) ───────────────────────────────────────────────────────────────

def test_an_event_with_two_syscall_records_is_never_attributed():
    at = T - timedelta(minutes=1)
    real = event(60, at, "/opt/x/chiffre", "/srv/a.db.locked")
    forged = _line(_syscall(60, exe="/usr/bin/tar"), at)
    lu, _ = _run(_alive() + real + [forged])
    [row] = lu.rows
    assert row["Executable"] == "(several SYSCALL records: not attributed)" and row["Doubles"] == 1
    assert row["Chemins"] == ["/srv/*.locked"]


def test_a_line_delivered_twice_is_one_event():
    once = event(61, T - timedelta(minutes=1), "/usr/bin/cp", "/srv/a.dat")
    lu, _ = _run(_alive() + once + once)
    [row] = lu.rows
    assert row["Executable"] == "/usr/bin/cp" and row["Evenements"] == 1 and "Doubles" not in row


# ── Bounded, pseudonymised (M8201, M8202) ───────────────────────────────────────────────────────────

def test_paths_are_their_folder_and_extension_never_the_file_s_name():
    names = ["/home/bob/Mes documents/salaires 2026.xlsx", "/srv/data/rapport-final.pdf", "relatif/x.tmp",
             "/var/www/bree/index.html", "/srv/sans-extension"]
    lu, _ = _run(_alive() + event(70, T - timedelta(minutes=1), "/usr/bin/python3.10", *names))
    [row] = lu.rows
    assert row["Fichiers"] == 5 and len(row["Chemins"]) == auditd_write.PATHS
    for p in row["Chemins"]:
        assert "salaires" not in p and "rapport" not in p and "bob" not in p and "index" not in p
    every = sorted(auditd_write.motif(_q(n)) for n in names)
    assert every == ["./relatif/*.tmp", "/home/<u>/Mes documents/*.xlsx", "/srv/*", "/srv/data/*.pdf",
                     "/var/www/bree/*.html"]
    assert auditd_write.motif("(null)") is None and auditd_write.motif("") is None


def test_the_executable_is_decoded_bounded_its_control_characters_dropped():
    assert auditd_write.executable(_q("/home/eve/bin/mon outil")) == "/home/<u>/bin/mon outil"
    assert auditd_write.executable(_q("/tmp/a\x1b[31mb")) == "/tmp/a[31mb"
    assert len(auditd_write.executable(_q("/x" * 300))) == auditd_write.EXE_MAX
    assert auditd_write.executable("(null)") == "?" and auditd_write.executable("") == "?"
    assert "forg" in (ROOT / "glorfindel/auditd_write.py").read_text(encoding="utf-8")
    assert "kernel" in catalog.A_MESURER[WRT].phrase or "noyau" in catalog.A_MESURER[WRT].phrase


# ── Its refusals, said (M8203, M8204) ────────────────────────────────────────────────────────────────

class _Http(Exception):
    def __init__(self, status, text="error"):
        super().__init__(text)
        self.status_code = status


class ReadTimeout(Exception):
    pass


@pytest.mark.parametrize("exc,why", [
    (_Http(403, "AuthorizationFailed"), catalog.WRT_DROIT),
    (_Http(401), catalog.WRT_DROIT),
    (_Http(400, "'where' operator: Failed to resolve table or column expression named 'Syslog'"), catalog.WRT_TABLE),
    (RuntimeError("workspace query not successful: SEM0100"), catalog.WRT_TABLE),
    (_Http(404, "WorkspaceNotFound"), catalog.WRT_ABSENT),
    (ReadTimeout("read timed out"), catalog.WRT_DELAI),
    (RuntimeError("workspace query not successful: PartialError"), catalog.WRT_ECHEC),
])
def test_a_failed_query_is_a_failure_said_never_nothing(exc, why):
    def kql_run(q, s):
        raise exc
    lu = auditd_write.process_write_audit(VM, T, kql_run=kql_run, now=LATER)
    assert lu.etat == catalog.ECHEC and lu.why.startswith(why) and lu.rows == []
    assert "workspace" not in lu.why.split("(")[-1]        # the class, never the adapter's text


@pytest.mark.parametrize("answer", [
    None, {"rows": []}, ["not a row"],
    [{"Battement": "peut-être", "Dernier": T}],
    [{"Battement": True}],
    [{"Battement": False, "Writer": '"/usr/bin/cp"', "Fichiers": "beaucoup", "Evenements": 1, "Processus": 1,
      "Doubles": 0, "Chemins": []}],
    [{"Battement": False, "Writer": '"/usr/bin/cp"', "Fichiers": 1, "Evenements": 1, "Processus": 1,
      "Doubles": 0, "Chemins": "/srv/a"}],
    [{"Battement": False, "Writer": '"/usr/bin/cp"', "Fichiers": -1, "Evenements": 1, "Processus": 1,
      "Doubles": 0, "Chemins": []}],
])
def test_an_answer_unreadable_is_a_failure_never_nothing(answer):
    lu = auditd_write.process_write_audit(VM, T, kql_run=lambda q, s: answer, now=LATER)
    assert lu.etat == catalog.ECHEC and lu.why == catalog.WRT_ILLISIBLE


def test_no_workspace_or_windows_is_sans_objet_and_nothing_queried():
    lu = auditd_write.process_write_audit(VM, T, kql_run=None, now=LATER)
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.WRT_SANS_ESPACE
    seen = []
    lu = auditd_write.process_write_audit(VM, T, kql_run=lambda q, s: seen.append(q) or [], now=LATER,
                                          system=catalog.WINDOWS)
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.WRT_WINDOWS and seen == []


# ── Its budget (M8205) ───────────────────────────────────────────────────────────────────────────────

def test_the_budget_is_taken_before_the_query_and_refused_said():
    clock = [0.0]
    budget = read_budget.ReadBudget("Log Analytics", "GLORFINDEL_LA_BUDGET_PER_MIN", 1, clock=lambda: clock[0])
    seen = []

    def kql_run(q, s):
        seen.append(q)
        return kql_subset.run(q, _alive(), now=LATER)
    assert auditd_write.process_write_audit(VM, T, kql_run=kql_run, now=LATER, budget=budget).etat == catalog.VIDE
    lu = auditd_write.process_write_audit(VM, T, kql_run=kql_run, now=LATER, budget=budget)
    assert lu.etat == catalog.REFUSEE and lu.why == catalog.WRT_BUDGET and len(seen) == 1
    assert budget.used() == {auditd_write.WHO: 1}


def test_the_module_s_budget_is_log_analytics(monkeypatch):
    auditd_write.process_write_audit(VM, T, kql_run=lambda q, s: [], now=LATER)
    assert read_budget.LOG_ANALYTICS.used() == {auditd_write.WHO: 1}
    monkeypatch.setenv("GLORFINDEL_LA_BUDGET_PER_MIN", "0")
    seen = []
    lu = auditd_write.process_write_audit(VM, T, kql_run=lambda q, s: seen.append(q) or [], now=LATER)
    assert lu.etat == catalog.REFUSEE and seen == []


# ── The capture at the bench reads it apart (M8206) ─────────────────────────────────────────────────

def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cap():
    return _load("capture_enquete")


class Banc:
    def __init__(self, lines):
        self.lines, self.audit = lines, 0

    def kql(self, query, span):
        if "eregion_write" in query:
            self.audit += 1
            return kql_subset.run(query, self.lines, now=LATER)
        return []

    def vm_os(self, vm):
        return "Linux"

    def enquiry_reads(self, vm, at, *, vault, vault_rg, only, now):
        return {only[0]: catalog.Reading(only[0], catalog.VIDE)}, 1


def _argv(out, *extra):
    return ["--vm", VM, "--at", "2026-11-10T02:34:10Z", "--workspace", "ws", "--rule", "ransomware-disk-write",
            "--ttp", "T1486", "--expect", "caution", "--out", str(out), *extra]


@pytest.fixture
def _sub(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", SUB)
    for var in ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)


def test_the_capture_reads_it_apart_never_in_what_the_harness_plays(cap, tmp_path, _sub):
    lines = _alive() + event(80, T - timedelta(minutes=1), "/home/vm-reelle/bin/x", "/srv/vm-reelle/a.locked")
    banc = Banc(lines)
    out = tmp_path / "c" / "e.json"
    assert cap.main(_argv(out), readers=lambda ws: (banc.kql, banc)) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert WRT not in doc["lectures"] and banc.audit == 1
    entry = doc["a_mesurer"][WRT]
    assert entry["etat"] == catalog.LIGNES and entry["queried"]
    [row] = entry["lignes"]
    assert row["Executable"] == "/home/<u>/bin/x" and row["Chemins"] == ["/srv/vm-smoke/*.locked"]
    assert doc["a_mesurer"]["process_write_io"]["etat"] == catalog.SANS_OBJET      # PIO1's, as it was


def test_the_capture_without_the_beat_says_sans_objet(cap, tmp_path, _sub):
    banc = Banc([])
    out = tmp_path / "c" / "e.json"
    assert cap.main(_argv(out), readers=lambda ws: (banc.kql, banc)) == 0
    entry = json.loads(out.read_text(encoding="utf-8"))["a_mesurer"][WRT]
    assert entry == {"etat": catalog.SANS_OBJET, "lignes": [], "pourquoi": catalog.WRT_SANS_MONTRE, "queried": True}


# ── The collection, declared in Terraform (M8193–M8196 on the files) ─────────────────────────────────

def _variable(name: str) -> str:
    text = (TF / "variables.tf").read_text(encoding="utf-8")
    m = re.search(rf'(?ms)^variable "{name}" \{{\n(.*?)^\}}', text)
    assert m, name
    return m.group(1)


def test_off_by_default_and_without_effect_off_auditd():
    body = _variable("auditd_write_watch_enabled")
    assert re.search(r"(?m)^\s*type\s*=\s*bool\s*$", body) and re.search(r"(?m)^\s*default\s*=\s*false\s*$", body)
    assert re.search(r"(?m)^\s*nullable\s*=\s*false\s*$", body)
    tf = (TF / "auditd.tf").read_text(encoding="utf-8")
    assert "auditd_write_watch = var.auditd_enabled && var.auditd_write_watch_enabled" in tf
    assert ': file("${path.module}/scripts/auditd.sh")\n' in tf           # off: AUD1's script, to the byte
    assert "script = base64encode(local.auditd_script)" in tf
    assert tf.count('resource "') == 1 and not re.search(r"(?m)^\s*custom_data\s*=", tf)
    assert "auditd" not in (TF / "vm.tf").read_text(encoding="utf-8")
    example = (TF / "terraform.tfvars.example").read_text(encoding="utf-8")
    assert re.search(r"(?m)^# auditd_write_watch_enabled\s*=\s*true", example)
    assert not re.search(r"(?m)^\s*auditd_write_watch_(enabled|dirs)\s*=", example)


def test_the_folders_are_bounded():
    body = _variable("auditd_write_watch_dirs")
    default = json.loads(re.search(r"(?m)^\s*default\s*=\s*(\[.*\])\s*$", body).group(1))
    assert default == ["/home", "/root", "/srv", "/var/www", "/var/backups", "/mnt/testdata"]
    assert "length(var.auditd_write_watch_dirs) <= 8" in body
    assert "length(distinct(var.auditd_write_watch_dirs)) == length(var.auditd_write_watch_dirs)" in body
    assert "^/(proc|sys|dev|run|tmp|var/tmp|var/log|var/lib/eregion)(/|$)" in body
    assert "^(/[A-Za-z0-9_-][A-Za-z0-9._-]*)+$" in body


def test_one_contract_the_fragment_the_catalogue_the_query():
    text = FRAGMENT.read_text(encoding="utf-8")
    rules = re.findall(r'(?m)^\s*echo "(-a always,exit .*)"$', text)
    assert rules == [
        f"-a always,exit -F arch=b64 -F dir=$WRT1_BEAT_DIR -F perm=w -k {catalog.WRT_BEAT_KEY}",
        f"-a always,exit -F arch=b32 -F dir=$WRT1_BEAT_DIR -F perm=w -k {catalog.WRT_BEAT_KEY}",
        f"-a always,exit -F arch=b64 -F dir=$d -F perm=w -k {catalog.WRT_KEY}",
        f"-a always,exit -F arch=b32 -F dir=$d -F perm=w -k {catalog.WRT_KEY}",
    ]
    assert "-S write" not in text and "perm=wa" not in text and "-p wa" not in text
    assert "OnCalendar=*:0/5" in text and catalog.WRT_BEAT_S == 300
    assert "WRT1_BEAT_DIR=/var/lib/eregion/write-watch" in text
    query = catalog.A_MESURER[WRT].query
    assert f'Key in ("{catalog.WRT_KEY}", "{catalog.WRT_BEAT_KEY}")' in query
    assert 'Facility == "local6"' in query and 'ProcessName == "audisp-syslog" or ProcessName == "audispd"' in query
    assert "_ResourceId =~ {vm}" in query and "Computer" not in query
    assert 'auditd_facility = "local6"' in (TF / "auditd.tf").read_text(encoding="utf-8")


def _fragment(tmp_path, dirs: str):
    """The fragment run in bash, its system paths moved under tmp_path, its commands stubbed."""
    text = FRAGMENT.read_text(encoding="utf-8")
    for real, fake in (("/etc/audit/rules.d", "rules.d"), ("/etc/systemd/system", "systemd"),
                       ("/var/lib/eregion/write-watch", "beat")):
        (tmp_path / fake).mkdir(exist_ok=True)
        text = text.replace(real, str(tmp_path / fake))
    stubs = ('augenrules() { :; }\nsystemctl() { echo "systemctl $*" >> "$LOG"; }\n'
             'auditctl() { sed -n \'s/^\\(-a .*\\) -k \\(.*\\)$/\\1 -F key=\\2/p\' "$RULES"; }\n')
    script = tmp_path / "run.sh"
    script.write_text("set -euo pipefail\n" + stubs + f'WRT1_DIRS="{dirs}"\n' + text, encoding="utf-8")
    env = {**os.environ, "LOG": str(tmp_path / "log"), "RULES": str(tmp_path / "rules.d/55-eregion-wrt1.rules")}
    res = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True, timeout=30)
    rules = (tmp_path / "rules.d/55-eregion-wrt1.rules").read_text(encoding="utf-8") if res.returncode == 0 else ""
    return res, rules


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash absent")
def test_the_fragment_watches_the_folders_present_and_says_the_others(tmp_path):
    present = tmp_path / "srv"
    present.mkdir()
    (tmp_path / "lien").symlink_to(present)
    res, rules = _fragment(tmp_path, f"{present} /absent-wrt1 {tmp_path / 'lien'}")
    assert res.returncode == 0, res.stderr
    lines = [r for r in rules.splitlines() if r.startswith("-a ")]
    assert lines[:2] == [f"-a always,exit -F arch={a} -F dir={tmp_path / 'beat'} -F perm=w -k eregion_write_beat"
                         for a in ("b64", "b32")]
    assert lines[2:] == [f"-a always,exit -F arch={a} -F dir={present} -F perm=w -k eregion_write"
                         for a in ("b64", "b32")]
    assert "/absent-wrt1 is not on the VM" in res.stderr and "lien is not on the VM" in res.stderr
    log = (tmp_path / "log").read_text(encoding="utf-8")
    assert "enable --now eregion-write-beat.timer" in log
    unit = (tmp_path / "systemd/eregion-write-beat.service").read_text(encoding="utf-8")
    assert "date -u +%%s > " in unit and (tmp_path / "beat").is_dir()


def test_the_terraform_test_plans_the_cases_and_the_old_ones_stay_hermetic():
    text = (TF / "tests/auditd_write.tftest.hcl").read_text(encoding="utf-8")
    for run in ("off_the_script_is_aud1_s_to_the_byte", "on_without_auditd_nothing_is_posed",
                "on_aud1_s_script_the_dirs_then_wrt1_s_nothing_else", "refused_a_virtual_or_noisy_dir"):
        assert f'run "{run}"' in text, run
    assert re.search(r"(?m)^  auditd_write_watch_enabled\s*= false$",
                     (TF / "tests/auditd.tftest.hcl").read_text(encoding="utf-8"))


def test_the_bench_targets_are_aud1_s():
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert ("AUDITD_TARGETS = -target=azurerm_virtual_machine_extension.auditd "
            "-target=azurerm_monitor_data_collection_rule.celebrimbor\n") in make


# ── The docs ─────────────────────────────────────────────────────────────────────────────────────────

def _section(doc: str, title: str) -> str:
    text = (ROOT / doc).read_text(encoding="utf-8")
    start = text.index(title)
    return text[start:text.index("\n## ", start + 1)]


def test_the_docs_say_the_measure_the_volume_and_the_forged_path():
    sec = _section("docs/operations.md", "## Qui écrit sous Linux, par auditd (WRT1")
    for word in ("auditd_write_watch_enabled", "make celebrimbor-auditd-plan", "make celebrimbor-auditd-up",
                 "human_only", "02:00 UTC", "eregion_write_beat", "Syslog", "_BilledSize", "2,99 USD",
                 "hypothèse qui relâche", "Ce qui dirait", "process_write_audit", "ENQ_OUT"):
        assert word in sec, word
    pio = _section("docs/operations.md", "## Qui écrit sous Linux, au banc (PIO1")
    for word in ("az provider register --namespace Microsoft.Monitor", "registrationState",
                 "/api/v1/label/__name__/values", "microsoft.resourceid", "azureotelcollector", "#1258", "WRT1"):
        assert word in pio, word
    assert '__name__=~' not in pio
    threat = (ROOT / "docs/design/modele-de-menace.md").read_text(encoding="utf-8")
    row = next(line for line in threat.splitlines() if "(WRT1, #1275)" in line and line.startswith("| I, T |"))
    for word in ("chemins", "exécutable", "uid", "aucun droit nouveau", "forge"):
        assert word in row.lower(), word
    design = (ROOT / "docs/design/enquete-raisonnee.md").read_text(encoding="utf-8")
    assert "`process_write_audit`" in design[design.index("### 4.4"):design.index("## 5.")]
