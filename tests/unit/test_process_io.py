"""PIO1 (#1258): who writes under Linux — `process_write_io`, declared, read in PromQL, measured at the bench
before it enters what the model sees (Q8; `docs/design/enquete-raisonnee.md` §4.4, §9.7, proposal 1).

No Azure call, no model call: the workspace is a fake session here. What is held:
- the read is in the catalogue's `A_MESURER`, never in `READS`: the loop, the message and the dossier never
  see it; `top_write_processes` and `backup_agent_check` stay `sans_objet` under Linux, untouched;
- its PromQL is written by the code only: the VM's id checked, as a case-insensitive regex literal escaped;
- the reader is read only (one POST to `/api/v1/query`, on the workspace's own host, no redirection);
- its states are always said: a 403, an absent workspace, an answer unreadable — `echec`; no workspace, no
  series — `sans_objet`; `vide` only on series that answered; its budget taken first, refused said;
- the name of a process is the guest's word: carried as written (bounded), never trusted;
- the capture reads it apart (`a_mesurer`), never in what the harness plays;
- the collection and the right are declared in Terraform, off by default (the `terraform test` files hold
  the plan; here, the files).
Mutants M8090–M8105 (scripts/mutants/PIO1.py).
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests

from glorfindel import read_budget
from glorfindel.enquiry import catalog, knowledge, loop
from glorfindel.providers.azure import prometheus

ROOT = Path(__file__).resolve().parents[2]
SUB = "12345678-aaaa-bbbb-cccc-1234567890ab"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-banc.(x)/providers/Microsoft.Compute/virtualMachines/vm-reelle"
T = datetime(2026, 11, 10, 2, 34, 10, tzinfo=timezone.utc)
LATER = T + timedelta(hours=1)
ENDPOINT = "https://amw-celebrimbor-abcd.westus.prometheus.monitor.azure.com"
PIO = "process_write_io"


class Answer:
    def __init__(self, status=200, body=None, raw=False):
        self.status_code, self._body, self._raw = status, body, raw

    def json(self):
        if self._raw:
            raise ValueError("no JSON")
        return self._body


class Session:
    """The workspace, made up: each POST written down, its answer given (or an exception raised)."""

    def __init__(self, answer=None, raises=None):
        self.answer, self.raises, self.calls = answer, raises, []

    def post(self, url, **kw):
        self.calls.append((url, kw))
        if self.raises is not None:
            raise self.raises
        return self.answer


class Token:
    def __init__(self, fail=False):
        self.fail, self.scopes = fail, []

    def get_token(self, scope):
        self.scopes.append(scope)
        if self.fail:
            raise RuntimeError("no identity")
        return type("T", (), {"token": "tok"})()


def _vector(*items):
    return Answer(body={"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": {catalog.PROCESS_IO_NAME: name} if name is not None else {}, "value": [T.timestamp(), value]}
        for name, value in items]}})


def _reader(answer=None, raises=None, token=None):
    session = Session(answer, raises)
    return prometheus.PromReader(ENDPOINT, credential=token or Token(), session=session), session


def _read(answer=None, raises=None, now=LATER, **kw):
    reader, session = _reader(answer, raises)
    return prometheus.process_write_io(VM, T, reader=reader, now=now, **kw), session


# ── Declared, never in what the model sees (M8090, M8091) ───────────────────────────────────────

def test_declared_apart_never_in_the_reads_the_loop_serves():
    read = catalog.A_MESURER[PIO]
    assert PIO not in catalog.READS and PIO in knowledge.ANNONCEES
    assert read.kind == "promql" and read.obj == "vm" and read.params == ("vm",)
    assert read.author == catalog.GUEST_FORGEABLE
    assert read.lookback == timedelta(minutes=5) and read.ahead == timedelta(0)
    assert catalog.says(read, catalog.LINUX) == "" and catalog.says(read, catalog.WINDOWS)
    assert catalog.says(read, "") == catalog.UNKNOWN_SYSTEM


def test_the_loop_never_permits_it_and_says_it_not_served():
    servies, non_servies = loop.permises(None, catalog.LINUX)
    assert PIO not in servies and PIO not in non_servies
    fiche = type("F", (), {"hypotheses": [type("H", (), {"lectures": (PIO,)})()]})()
    servies, non_servies = loop.permises(fiche, catalog.LINUX)
    assert servies == [] and non_servies[PIO].etat == catalog.NON_PERMISE and not non_servies[PIO].servie


def test_the_two_process_counter_reads_stay_sans_objet_under_linux():
    for rid in ("top_write_processes", "backup_agent_check"):
        assert 'ObjectName == "Process"' in catalog.READS[rid].query
        assert catalog.says(catalog.READS[rid], catalog.LINUX) == catalog._PROCESS_LINUX


def test_no_module_of_the_watch_imports_the_reader():
    """investigate, decide, the loop: none reaches the reader — only the capture at the bench."""
    users = []
    for path in sorted((ROOT / "glorfindel").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [f"{node.module}.{a.name}" for a in node.names] if isinstance(node, ast.ImportFrom) and node.module
                     else [])
            if any("prometheus" in n for n in names):
                users.append(path.relative_to(ROOT).as_posix())
    assert users == []
    for rel in ("glorfindel/agent.py", "glorfindel/enquiry/message.py", "glorfindel/enquiry/loop.py",
                "glorfindel/enquiry/fixed.py"):
        assert PIO not in (ROOT / rel).read_text(encoding="utf-8"), rel
    assert "process_write_io" not in (ROOT / "glorfindel/few_shot_examples.yaml").read_text(encoding="utf-8")


# ── The PromQL, the code's alone (M8092, M8093) ─────────────────────────────────────────────────

def test_the_promql_reads_the_writes_of_the_vm_by_executable_the_first_n():
    q = prometheus.texte(VM, T - timedelta(minutes=5), T, top=5)
    assert q.startswith('topk(5, sum by ("process.executable.name") (increase({"process.disk.io", ')
    assert 'direction="write"' in q and q.endswith("[300s])))")
    lit = re.search(r'"Microsoft\.resourceid"=~("[^"]*")', q).group(1)
    assert lit.startswith('"(?i)/subscriptions/') and "rg-banc\\\\.\\\\(x\\\\)" in lit
    assert "Microsoft\\\\.Compute" in lit
    # The literal, read as PromQL reads it (Go's escapes), then as RE2: it matches the id, whatever its case.
    regex = lit[1:-1].replace("\\\\", "\\")
    assert re.fullmatch(regex, VM.upper()) and not re.fullmatch(regex, VM + "x")
    assert re.fullmatch(regex, VM.replace(".(x)", "a(x)")) is None


@pytest.mark.parametrize("top,expected", [(0, 1), (5, 5), (99, 10)])
def test_top_bounded(top, expected):
    assert prometheus.texte(VM, T - timedelta(minutes=5), T, top=top).startswith(f"topk({expected}, ")


@pytest.mark.parametrize("vm", ["vm-reelle", VM + '"}) or vector(1', "/subscriptions/x/../y", ""])
def test_a_vm_that_is_not_a_resource_id_is_refused_before_any_query(vm):
    reader, session = _reader(_vector(("bash", "1")))
    lu = prometheus.process_write_io(vm, T, reader=reader, now=LATER)
    assert lu.etat == catalog.REFUSEE and session.calls == []


# ── Read only, on the workspace's host (M8094, M8095) ───────────────────────────────────────────

def test_one_post_to_the_query_api_with_the_identity_and_no_redirection():
    token = Token()
    reader, session = _reader(_vector(("bash", "2e6")), token=token)
    lu = prometheus.process_write_io(VM, T, reader=reader, now=LATER)
    assert lu.etat == catalog.LIGNES
    (url, kw), = session.calls
    assert url == ENDPOINT + "/api/v1/query" and kw["allow_redirects"] is False
    assert kw["headers"] == {"Authorization": "Bearer tok"} and token.scopes == [prometheus.SCOPE]
    assert kw["data"]["time"] == f"{T.timestamp():.3f}" and "process.disk.io" in kw["data"]["query"]
    assert kw["timeout"] == prometheus.TIMEOUT_S


@pytest.mark.parametrize("endpoint", ["http://amw-x.westus.prometheus.monitor.azure.com",
                                      "https://evil.example/x.prometheus.monitor.azure.com",
                                      "https://amw-x.westus.prometheus.monitor.azure.com.evil.example",
                                      "https://amw-x.westus.prometheus.monitor.azure.com/api", ""])
def test_only_a_workspace_s_query_endpoint(endpoint):
    with pytest.raises(ValueError):
        prometheus.PromReader(endpoint)


def test_the_reader_writes_nothing():
    """The module's calls on the network: a POST to the query API, and nothing else (no put, patch, delete)."""
    tree = ast.parse((ROOT / "glorfindel/providers/azure/prometheus.py").read_text(encoding="utf-8"))
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "post" in called and not called & {"put", "patch", "delete", "request", "get_or_create"}
    assert "/api/v1/query\"" in (ROOT / "glorfindel/providers/azure/prometheus.py").read_text(encoding="utf-8")


# ── Its states, always said (M8096–M8101) ───────────────────────────────────────────────────────

def test_rows_the_writers_by_bytes_zeros_dropped():
    lu, _ = _read(_vector(("tar", "3000000"), ("openssl", "9000000"), ("sshd", "0")))
    assert lu.etat == catalog.LIGNES
    assert [r["Executable"] for r in lu.rows] == ["openssl", "tar"]
    assert lu.rows[0] == {"Executable": "openssl", "EcritMo": 9.0, "Octets": 9000000}


def test_series_that_answered_none_wrote_is_empty_vouched():
    lu, _ = _read(_vector(("sshd", "0"), ("cron", "0")))
    assert lu.etat == catalog.VIDE


def test_no_series_for_the_vm_is_sans_objet_never_empty():
    lu, _ = _read(_vector())
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.PIO_SANS_SERIE


def test_before_the_latency_nothing_is_said_yet():
    lu, _ = _read(_vector(), now=T + timedelta(seconds=30))
    assert lu.etat == catalog.EN_ATTENTE
    lu, _ = _read(_vector(("sshd", "0")), now=T + timedelta(seconds=30))
    assert lu.etat == catalog.EN_ATTENTE


def test_no_workspace_is_sans_objet_and_nothing_queried():
    lu = prometheus.process_write_io(VM, T, reader=None, now=LATER)
    assert lu.etat == catalog.SANS_OBJET and lu.why == catalog.PIO_SANS_ESPACE


@pytest.mark.parametrize("status,why", [(403, catalog.PIO_DROIT), (401, catalog.PIO_DROIT),
                                        (404, catalog.PIO_ABSENT), (429, catalog.PIO_ILLISIBLE),
                                        (500, catalog.PIO_ILLISIBLE), (302, catalog.PIO_ILLISIBLE)])
def test_a_refusal_of_the_workspace_is_a_failure_said(status, why):
    lu, _ = _read(Answer(status=status, body={}))
    assert lu.etat == catalog.ECHEC and lu.why.startswith(why) and lu.gap


@pytest.mark.parametrize("raises,why", [(requests.ConnectionError("dns"), catalog.PIO_ABSENT),
                                        (requests.ConnectTimeout("t"), catalog.PIO_ILLISIBLE),
                                        (requests.ReadTimeout("t"), catalog.PIO_ILLISIBLE),
                                        (requests.TooManyRedirects("r"), catalog.PIO_ILLISIBLE)])
def test_a_workspace_that_does_not_answer_is_a_failure_said(raises, why):
    lu, _ = _read(raises=raises)
    assert lu.etat == catalog.ECHEC and lu.why.startswith(why)


@pytest.mark.parametrize("answer", [
    Answer(raw=True), Answer(body=[]), Answer(body={"status": "error", "error": "bad"}),
    Answer(body={"status": "success", "data": {"resultType": "matrix", "result": []}}),
    Answer(body={"status": "success", "data": {"resultType": "vector", "result": None}}),
    _vector(("bash", "NaN")), _vector(("bash", "+Inf")), _vector(("bash", "many")),
    Answer(body={"status": "success", "data": {"resultType": "vector", "result": [{"metric": {}}]}}),
])
def test_an_answer_unreadable_is_a_failure_never_nothing(answer):
    lu, _ = _read(answer)
    assert lu.etat == catalog.ECHEC and lu.why.startswith(catalog.PIO_ILLISIBLE)


def test_no_token_is_the_right_absent():
    reader, session = _reader(_vector(), token=Token(fail=True))
    lu = prometheus.process_write_io(VM, T, reader=reader, now=LATER)
    assert lu.etat == catalog.ECHEC and lu.why.startswith(catalog.PIO_DROIT)


# ── The name of a process: the guest's word (M8102) ─────────────────────────────────────────────

def test_the_name_is_carried_as_the_guest_wrote_it_bounded_whatever_the_label_s_case():
    long = "w" * 200
    answer = Answer(body={"status": "success", "data": {"resultType": "vector", "result": [
        {"metric": {"PROCESS.EXECUTABLE.NAME": "waagent\x1b[31m\n"}, "value": [0, "5e6"]},
        {"metric": {catalog.PROCESS_IO_NAME: long}, "value": [0, "4e6"]},
        {"metric": {}, "value": [0, "3e6"]}]}})
    lu, _ = _read(answer)
    assert [r["Executable"] for r in lu.rows] == ["waagent[31m", "w" * prometheus.NAME_MAX, "?"]
    assert catalog.A_MESURER[PIO].author == catalog.GUEST_FORGEABLE
    assert "forg" in (ROOT / "glorfindel/providers/azure/prometheus.py").read_text(encoding="utf-8")


# ── Its budget (M8103) ──────────────────────────────────────────────────────────────────────────

def test_the_budget_is_taken_before_the_query_and_refused_said():
    clock = [0.0]
    budget = read_budget.ReadBudget("Prometheus", "GLORFINDEL_PROM_BUDGET_PER_MIN", 1, clock=lambda: clock[0])
    reader, session = _reader(_vector(("bash", "1e6")))
    assert prometheus.process_write_io(VM, T, reader=reader, now=LATER, budget=budget).etat == catalog.LIGNES
    lu = prometheus.process_write_io(VM, T, reader=reader, now=LATER, budget=budget)
    assert lu.etat == catalog.REFUSEE and lu.why == catalog.PIO_BUDGET and len(session.calls) == 1
    assert budget.used() == {prometheus.WHO: 1}


def test_the_module_s_budget_is_the_reader_s_and_the_watch_says_it(monkeypatch):
    reader, session = _reader(_vector(("bash", "1e6")))
    prometheus.process_write_io(VM, T, reader=reader, now=LATER)
    assert read_budget.PROMETHEUS.used() == {prometheus.WHO: 1}
    assert read_budget.PROMETHEUS.env == "GLORFINDEL_PROM_BUDGET_PER_MIN" and read_budget.PROMETHEUS.default == 30
    monkeypatch.setenv("GLORFINDEL_PROM_BUDGET_PER_MIN", "-3")
    assert any("GLORFINDEL_PROM_BUDGET_PER_MIN" in n for n in read_budget.notes())
    monkeypatch.setenv("GLORFINDEL_PROM_BUDGET_PER_MIN", "0")
    lu = prometheus.process_write_io(VM, T, reader=reader, now=LATER)
    assert lu.etat == catalog.REFUSEE and len(session.calls) == 1


# ── The capture at the bench reads it apart (M8104) ─────────────────────────────────────────────

def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cap():
    return _load("capture_enquete")


class Banc:
    def kql(self, query, span):
        return []

    def vm_os(self, vm):
        return "Linux"

    def enquiry_reads(self, vm, at, *, vault, vault_rg, only, now):
        return {only[0]: catalog.Reading(only[0], catalog.VIDE)}, 1


def _argv(out, *extra):
    vm = f"/subscriptions/{SUB}/resourceGroups/rg-banc-reel/providers/Microsoft.Compute/virtualMachines/vm-reelle"
    return ["--vm", vm, "--at", "2026-11-10T02:34:10Z", "--workspace", "ws", "--rule", "ransomware-disk-write",
            "--ttp", "T1486", "--expect", "caution", "--out", str(out), *extra]


@pytest.fixture
def _sub(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", SUB)
    for var in ("AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)


def test_the_capture_reads_it_apart_never_in_what_the_harness_plays(cap, tmp_path, _sub):
    banc, made = Banc(), []

    def prom_reader(endpoint):
        made.append(endpoint)
        return _reader(_vector(("openssl", "9e6")))[0]
    out = tmp_path / "c" / "e.json"
    assert cap.main(_argv(out, "--prom-endpoint", ENDPOINT + "/"), readers=lambda ws: (banc.kql, banc),
                    prom_reader=prom_reader) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert made == [ENDPOINT] and PIO not in doc["lectures"]
    entry = doc["a_mesurer"][PIO]
    assert entry["etat"] == catalog.LIGNES and entry["lignes"][0]["Executable"] == "openssl" and entry["queried"]


def test_without_the_endpoint_it_is_said_sans_objet_and_nothing_queried(cap, tmp_path, _sub):
    banc = Banc()
    out = tmp_path / "c" / "e.json"
    assert cap.main(_argv(out), readers=lambda ws: (banc.kql, banc)) == 0
    entry = json.loads(out.read_text(encoding="utf-8"))["a_mesurer"][PIO]
    assert entry == {"etat": catalog.SANS_OBJET, "lignes": [], "pourquoi": catalog.PIO_SANS_ESPACE, "queried": False}


def test_an_endpoint_that_is_not_a_workspace_s_is_refused_before_any_call(cap, tmp_path, _sub):
    out = tmp_path / "e.json"
    assert cap.main(_argv(out, "--prom-endpoint", "https://evil.example"),
                    readers=lambda ws: pytest.fail("built")) == 2


def test_make_passes_the_endpoint():
    if shutil.which("make") is None:
        pytest.skip("make not installed")
    out = subprocess.run(["make", "-n", "--no-print-directory", "-C", str(ROOT), "enquete-capture", "ENQ_VM=v",
                          "ENQ_AT=a", "ENQ_WORKSPACE=w", "ENQ_EXPECT=caution", "ENQ_OUT=/tmp/x.json",
                          f"ENQ_PROM={ENDPOINT}"], capture_output=True, text=True, timeout=60).stdout
    assert f'--prom-endpoint "{ENDPOINT}"' in out


# ── Declared in Terraform, off by default (M8105) ───────────────────────────────────────────────

TF = ROOT / "infra/terraform"
HOST = ROOT / "infra/glorfindel-host"


def test_the_collection_is_off_by_default_and_collects_process_disk_io_alone():
    variables = (TF / "variables.tf").read_text(encoding="utf-8")
    block = variables[variables.index('variable "process_io_enabled"'):]
    assert re.search(r"default\s+=\s+false", block[:block.index("\n}")])
    tf = (TF / "process_io.tf").read_text(encoding="utf-8")
    assert 'process_io_counters = ["process.disk.io"]' in tf
    assert 'process_io_stream   = "Microsoft-OtelPerfMetrics"' in tf
    assert '"Microsoft.Insights/dataCollectionRules@2024-03-11"' in tf and "performanceCountersOTel" in tf
    assert tf.count("count     = local.process_io_enabled ? 1 : 0") == 1
    assert tf.count("count               = local.process_io_enabled ? 1 : 0") == 1
    assert tf.count("count                = local.process_io_enabled ? 1 : 0") == 1
    assert tf.count('role_definition_name = "Monitoring Data Reader"') == 1
    assert "for k, v in local.vms : k => v if local.process_io_enabled" in tf


def test_the_rule_s_dcr_stays_intact():
    mon = (TF / "monitoring.tf").read_text(encoding="utf-8")
    assert "Otel" not in mon and "monitor_account" not in mon and "process.disk.io" not in mon


def test_the_watch_s_right_is_monitoring_data_reader_on_the_workspace_alone_off_by_default():
    tf = (HOST / "watch_process_io.tf").read_text(encoding="utf-8")
    assert 'role_definition_name = "Monitoring Data Reader"' in tf
    assert "scope                = data.azurerm_monitor_workspace.bench[0].id" in tf
    assert tf.count("var.watch_process_io_read_enabled ? 1 : 0") == 2
    variables = (HOST / "variables.tf").read_text(encoding="utf-8")
    block = variables[variables.index('variable "watch_process_io_read_enabled"'):]
    assert re.search(r"default\s+=\s+false", block[:block.index("\n}")])
    for path in (TF / "tests/process_io.tftest.hcl", HOST / "tests/watch_process_io.tftest.hcl"):
        assert "mock_provider \"azurerm\"" in path.read_text(encoding="utf-8")


def test_the_bench_targets_touch_the_collection_alone():
    if shutil.which("make") is None:
        pytest.skip("make not installed")
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert ("PROCESS_IO_TARGETS = -target=azurerm_monitor_workspace.process_io -target=azapi_resource.process_io_dcr "
            "-target=azurerm_monitor_data_collection_rule_association.process_io "
            "-target=azurerm_role_assignment.process_io_operator_reader") in make
    for target in ("celebrimbor-process-io-plan", "celebrimbor-process-io-up"):
        recipe = make[make.index(f"\n{target}:"):]
        recipe = recipe[:recipe.index("\n\n")]
        assert "$(CELEBRIMBOR_SUB_GUARD)" in recipe and "$(PROCESS_IO_TARGETS)" in recipe and "-var" not in recipe


def test_the_docs_say_the_measure_and_the_forged_name():
    ops = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
    section = ops[ops.index("## Qui écrit sous Linux, au banc (PIO1"):]
    section = section[:section.index("\n## ", 1)]
    for word in ("make celebrimbor-process-io-plan", "make imladris-plan", "02:00 UTC", "process.disk.io",
                 "ENQ_PROM", "forgeable", "pas mesuré"):
        assert word in section, word
    threat = (ROOT / "docs/design/modele-de-menace.md").read_text(encoding="utf-8")
    assert "Monitoring Data Reader" in threat
