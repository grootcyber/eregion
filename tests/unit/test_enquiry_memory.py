"""SEC-I (#850): the enquiry, two shipped rules and the memory.

- The enquiry (`investigate`) scopes its queries by the VM the registry names — the signal's
  `_ResourceId`, never the line's `Computer`, which root on any host of the workspace chooses: a
  host named like the VM wrote the rows the model read. A detection attributed to no VM runs no
  query. The correlation (`correlation.scope`) no longer falls back on `Computer`: a row without
  its `_ResourceId` names no VM, its result unknown (a card).
- The blob exfiltration rule counts written writes only (HTTP 2xx): a refused write moved nothing.
- The log-tampering rule sets a known writer aside only on an event of one SYSCALL record of its
  key: a second one, written at the event's serial, made the whole event vanish.
- The memory weighs the VM and the rule of a past cycle, and gives at most one precedent per VM:
  a flood of one VM's cycles no longer fills every place. Each cycle is stored as not corroborated
  (no verdict exists before SEC-A3), in its metadata — never in what the model reads.

The rules run as written on placeholder lines through the suite's KQL reader (kql_subset). No Azure
call, no model call. Mutants M5821–M5840 (scripts/mutants/SEC-I.py) are measured here.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from glorfindel import agent, correlation
from glorfindel.kql import literal
from glorfindel.memory import CycleMemory

from . import kql_subset

NOW = datetime.now(timezone.utc)
SUB = "00000000-0000-0000-0000-0000000000aa"


def _vm(name: str) -> str:
    return f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/{name}"


VM_A, VM_B, VM_C, VM_D = _vm("vm-a"), _vm("vm-b"), _vm("vm-c"), _vm("vm-d")
# A machine of the same workspace whose host name is chosen by its root (an Arc machine here).
NAMESAKE = (f"/subscriptions/{SUB}/resourceGroups/rg-other/providers/Microsoft.HybridCompute/machines/"
            "host-other")
PEER = "198.51.100.7"
WS = "00000000-0000-0000-0000-0000000000dd"

_RULES = yaml.safe_load((Path(__file__).resolve().parents[2] / "glorfindel" / "rules" / "azure"
                         / "detection_rules.yaml").read_text())
RULES = {r["name"]: r for r in _RULES["rules"]}


def _syslog(message: str, rid: str, computer: str, process: str, facility: str = "auth") -> dict:
    return {"Type": "Syslog", "TimeGenerated": NOW - timedelta(minutes=1), "Facility": facility,
            "ProcessName": process, "SyslogMessage": message, "Computer": computer, "_ResourceId": rid}


# ── 1. The enquiry: the registry's VM, never the line's host name ─────────────────────────────

_TEMPLATES = ("_IQ_HEARTBEAT_GAP", "_IQ_DISK_PROCESSES", "_IQ_BACKUP_AGENT", "_IQ_SUCCESS_AUTH",
              "_IQ_ROOT_COMMANDS", "_IQ_DISK_AFTER_ESC")


@pytest.mark.parametrize("name", _TEMPLATES)
def test_every_enquiry_query_is_scoped_by_the_resource_id(name):
    """M5821: one query of the enquiry scoped by the host name again."""
    template = getattr(agent, name)
    assert "| where _ResourceId =~ {vm}\n" in template
    assert "Computer" not in template


def _world() -> list[dict]:
    """vm-a's own lines, and those of a host of the workspace that calls itself vm-a."""
    return [
        _syslog("alice : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/cat /etc/shadow",
                VM_A, "vm-a", "sudo", "authpriv"),
        _syslog(f"Accepted password for alice from {PEER} port 41000 ssh2", VM_A, "vm-a", "sshd"),
        # The namesake: root there names its host vm-a, and writes what it wants the model to read.
        _syslog("ops : TTY=pts/1 ; PWD=/ ; USER=root ; COMMAND=/usr/bin/apt upgrade (routine)",
                NAMESAKE, "vm-a", "sudo", "authpriv"),
        _syslog(f"Accepted publickey for backup from {PEER} port 41001 ssh2", NAMESAKE, "vm-a", "sshd"),
    ]


def _investigate(monkeypatch, row: dict, *, rid: str = VM_A, context: dict | None = None):
    ran: list[str] = []
    world = _world()

    def run(_ws, query):
        ran.append(query)
        if query.lstrip().startswith("Syslog"):
            return kql_subset.run(query.strip(), world, now=NOW)
        return []                       # Perf, Heartbeat: their text is checked, not their rows

    monkeypatch.setattr(agent, "_run_investigative_query", run)
    signal = {"event": "detection", "resource_id": rid, "ttp": "T1548.003", "context": context or {},
              "raw_signal": {"log_analytics_workspace_id": WS, "detected_data": row}}
    return agent.investigate({"dry_run": False, "signal": signal}), ran


def test_a_line_whose_host_name_and_resource_id_diverge_is_enquired_on_the_registrys_vm(monkeypatch):
    """L-51 replayed: a row of vm-a's _ResourceId whose Computer says vm-b — the enquiry reads vm-a's
    lines, never vm-b's nor those of a namesake host. M5822: the host name read again."""
    row = {"Computer": "vm-b", "_ResourceId": VM_A,
           "SyslogMessage": "alice : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/bash"}
    out, ran = _investigate(monkeypatch, row)
    assert len(ran) == 2 and out["telemetry_gaps"] == []
    assert all(f"_ResourceId =~ {literal(VM_A)}" in q for q in ran)
    assert not any("vm-b" in q for q in ran)
    seen = out["signal"]["raw_signal"]["investigative_context"]["root_commands"]
    assert [r["SyslogMessage"] for r in seen] == [
        "alice : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/bin/cat /etc/shadow"]


def test_a_namesake_host_never_writes_the_successful_logins_the_model_reads(monkeypatch):
    out, _ran = _investigate(monkeypatch, {"Computer": "vm-a", "_ResourceId": VM_A,
                                           "SourceIP": PEER, "FailedAttempts": 30})
    logins = out["signal"]["raw_signal"]["investigative_context"]["successful_auth_from_ip"]
    assert [r["SyslogMessage"] for r in logins] == [f"Accepted password for alice from {PEER} port 41000 ssh2"]


def test_the_registrys_case_matches_log_analytics_lowered_id(monkeypatch):
    """`=~`: the registry may hold the id in another case than Log Analytics writes it."""
    out, _ran = _investigate(monkeypatch, {"SourceIP": PEER, "FailedAttempts": 30},
                             rid=VM_A.replace("rg-example", "RG-Example").replace("vm-a", "VM-A"))
    assert len(out["signal"]["raw_signal"]["investigative_context"]["successful_auth_from_ip"]) == 1


def test_an_unattributed_detection_runs_no_enquiry(monkeypatch, capsys):
    """M5823: the anchor of a detection attributed to no VM enquired on as if it were the VM."""
    row = {"Computer": "vm-a", "SyslogMessage": "x : USER=root ; COMMAND=/bin/bash"}
    out, ran = _investigate(monkeypatch, row, context={"attribution": "unattributed", "candidates": ["vm-a"]})
    assert ran == []
    assert set(out["telemetry_gaps"]) == {"root_commands", "disk_write_after_escalation"}
    assert out["signal"]["raw_signal"]["investigative_context"] == {
        "root_commands": [], "disk_write_after_escalation": []}
    assert "non attribuée" in capsys.readouterr().out


def test_an_attributed_detection_still_runs_its_enquiry(monkeypatch):
    out, ran = _investigate(monkeypatch, {"SourceIP": PEER, "FailedAttempts": 30},
                            context={"attribution": "asset"})
    assert len(ran) == 1 and out["telemetry_gaps"] == []


# ── 2. The correlation: no fallback on the host name ─────────────────────────────────────────

def test_the_correlation_scope_is_the_resource_id_only():
    """M5824: a row without its _ResourceId scoped by its Computer again."""
    assert correlation.scope({"_ResourceId": VM_A, "Computer": "vm-b"}) == f"_ResourceId == {literal(VM_A)}"
    assert correlation.scope({"Computer": "vm-a"}) is None
    assert correlation.scope({"_ResourceId": "", "Computer": "vm-a"}) is None
    assert correlation.scope({"_ResourceId": VM_A + '" or true', "Computer": "vm-a"}) is None


def test_a_brute_force_row_without_its_resource_id_is_left_unchecked():
    """Its logins are not read on a host name: the row says it was not checked (a card)."""
    asked: list[str] = []
    row = {"SourceIP": PEER, "FailedAttempts": 30, "Computer": "vm-a"}
    counts = correlation.settle(correlation.BRUTE_FORCE_TTP, {"vm-a": ((VM_A, "vm-a"), [row])}, {},
                                lambda q, timespan=None: asked.append(q) or [], set(), lambda r: id(r), 600,
                                now=NOW)
    assert asked == [] and counts["unchecked"] == 1
    assert row["LoginCheck"]["status"] == "unchecked" and "Correlation" not in row


# ── 3. The blob exfiltration rule: written writes only ───────────────────────────────────────

WRITER_OID = "00000000-0000-0000-0000-0000000000c3"     # a placeholder, never a real id


def _write(ip: str, status: str, text: str, op: str = "PutBlob", size: int = 0) -> dict:
    return {"Type": "StorageBlobLogs", "TimeGenerated": NOW - timedelta(minutes=1), "OperationName": op,
            "CallerIpAddress": f"{ip}:50374", "AccountName": "stexample", "StatusCode": status,
            "StatusText": text, "ResponseBodySize": size, "ObjectKey": "/stexample/drop/loot.bin",
            "RequesterObjectId": WRITER_OID}


def _writers(writes: int) -> list[dict]:
    """The rule's BlobWriters (SLF1): who wrote, in which container — the written writes only."""
    return [{"container": "drop", "writer": WRITER_OID, "writes": writes, "bytes": 0, "known": 0}]


def _blob(rows):
    return kql_subset.run(RULES["data-exfiltration-blob"]["query"], rows, now=NOW)


def test_a_written_write_counts():
    rows = [_write("10.0.1.4", "201", "Success", "PutBlock"), _write("10.0.1.4", "201", "Success", "PutBlockList")]
    assert _blob(rows) == [{"CallerIpAddress": "10.0.1.4", "AccountName": "stexample",
                            "PutBlobCount": 2, "EgressBytes": 0, "BlobWriters": _writers(2)}]


@pytest.mark.parametrize("status,text", [("403", "AuthorizationPermissionMismatch"), ("404", "ContainerNotFound"),
                                         ("409", "BlobAlreadyExists"), ("Unknown", "Unknown"), ("", "")])
def test_a_refused_write_moved_nothing(status, text):
    """M5825: the refused writes counted as an exfiltration again."""
    assert _blob([_write("10.0.1.5", status, text)]) == []


def test_only_the_written_writes_are_counted_beside_refused_ones():
    rows = [_write("10.0.1.6", "403", "AuthorizationFailure")] * 5 + [_write("10.0.1.6", "201", "Success")]
    [hit] = _blob(rows)
    # Filtered before the first summarize: a refused write is in neither the count nor BlobWriters,
    # whose writes the return channel's setting aside subtracts from the count (SLF1).
    assert hit["PutBlobCount"] == 1 and hit["BlobWriters"] == _writers(1)


# ── 4. The log-tampering rule: one SYSCALL record per event ──────────────────────────────────

def _audit(serial, *records):
    return [{"Type": "Syslog", "TimeGenerated": NOW - timedelta(minutes=1), "Facility": "local6",
             "ProcessName": "audisp-syslog", "Computer": "vm-a", "_ResourceId": VM_A,
             "SyslogMessage": f"type={kind} msg=audit(1730800000.{serial}:{serial}): {body}"}
            for kind, body in records]


def _syscall(exe: str, comm: str = "x") -> tuple[str, str]:
    return ("SYSCALL", f'arch=c000003e syscall=257 success=yes exit=3 items=2 auid=4294967295 uid=0 '
                       f'euid=0 comm="{comm}" exe="{exe}" key="log_tamper"')


def _path(name: str, nametype: str = "NORMAL") -> tuple[str, str]:
    return ("PATH", f'item=1 name="{name}" inode=2 nametype={nametype}')


def _tamper(rows):
    return kql_subset.run(RULES["t1070-002-log-tamper"]["query"], rows, now=NOW)


def test_a_daemons_record_added_to_the_event_no_longer_sets_it_aside():
    """M5827, M5828: the shell's write and a line written at its serial in rsyslogd's name."""
    rows = _audit(9001, _syscall("/usr/bin/dash", "dash"), _path("/var/log/auth.log"),
                  _syscall("/usr/sbin/rsyslogd"))
    [hit] = _tamper(rows)
    assert sorted(hit["Writer"]) == ["/usr/bin/dash", "/usr/sbin/rsyslogd"]


def test_a_known_writers_record_added_to_the_event_no_longer_sets_it_aside():
    """M5829: a shell that empties wtmp (the logins' trace), an sshd record written at its serial."""
    rows = _audit(9002, _syscall("/usr/bin/dash", "dash"), _syscall("/usr/sbin/sshd", "sshd"),
                  _path("/var/log/wtmp"))
    assert len(_tamper(rows)) == 1


def test_a_record_the_agent_delivers_twice_is_one_record():
    """M5826: the lines counted, not the distinct records — rsyslogd's own write, its SYSCALL line
    delivered twice by the agent (at least once), made a card."""
    rows = _audit(9004, _syscall("/usr/sbin/rsyslogd"), _path("/var/log/syslog"))
    assert _tamper(rows + rows[:1]) == []
    sshd = _audit(9005, _syscall("/usr/sbin/sshd", "sshd"), _path("/var/log/btmp"))
    assert _tamper(sshd + sshd) == []


def test_a_forged_daemons_record_still_counts_as_a_second_one_beside_duplicates():
    """Distinct records: a daemon's line written at the serial differs from the shell's — two,
    whatever the agent delivers twice."""
    rows = _audit(9006, _syscall("/usr/bin/dash", "dash"), _path("/var/log/auth.log"),
                  _syscall("/usr/sbin/rsyslogd"))
    assert len(_tamper(rows + rows)) == 1


@pytest.mark.parametrize("exe,path", [
    ("/usr/sbin/rsyslogd", "/var/log/syslog"),
    ("/usr/sbin/sshd", "/var/log/btmp"),
    ("/usr/bin/dpkg", "/var/log/dpkg.log"),
])
def test_a_known_writer_alone_on_its_event_is_still_set_aside(exe, path):
    assert _tamper(_audit(9003, _syscall(exe), _path(path))) == []


# ── 5. The memory: the VM and the rule weigh in, one VM bounded ──────────────────────────────

SIG = {"ttp": "T1110.001", "severity": "critical", "resource_type": "vm", "event": "detection",
       "provider": "azure"}


def _signal(rid: str, rule: str = "ssh-brute-force", **context) -> dict:
    return {**SIG, "resource_id": rid, "context": {"rule_name": rule, **context}}


def _cycle(signal_id: str, rid: str, rule: str = "ssh-brute-force", **over) -> dict:
    return {"signal_id": signal_id, "run_id": signal_id, "ttp": "T1110.001", "severity": "critical",
            "resource_type": "vm", "event": "detection", "reasoning": f"reasoning {signal_id}",
            "action": "block_suspicious_ip", "outcome": "x", "source": "real", "confidence": 0.9,
            "resource_id": rid, "rule_name": rule, **over}


@pytest.fixture
def mem(tmp_path):
    return CycleMemory(path=tmp_path / "cycles", clock=time.time)


def _vms(found):
    return [c["resource_id"] for c in found]


def test_a_flood_of_one_vms_cycles_takes_one_place_on_its_neighbours(mem):
    """M5832: a VM's provoked cycles fill the three places of every detection of the technique."""
    for i in range(20):
        mem.store(_cycle(f"flood-{i}", VM_A))
    mem.store(_cycle("b-own", VM_B))
    found = mem.retrieve_similar(_signal(VM_C), n=3)
    assert sorted(_vms(found)) == sorted([VM_A.lower(), VM_B.lower()])


def test_a_flood_of_one_vms_cycles_takes_one_place_on_its_own_vm(mem):
    for i in range(20):
        mem.store(_cycle(f"flood-{i}", VM_A))
    found = mem.retrieve_similar(_signal(VM_A), n=3)
    assert _vms(found) == [VM_A.lower()]


def test_the_vms_own_cycle_is_found_past_a_flood_of_nearer_ones(mem):
    """M5830, M5834, M5838: the VM's own history found by its id, even when a flood of another VM's
    cycles, nearer by their text, fills every place the text alone reads."""
    for flooded in (VM_A, VM_C, VM_D):                  # three VMs' floods: every place, by the text
        for i in range(15):
            mem.store(_cycle(f"flood-{flooded[-4:]}-{i}", flooded))
    mem.store(_cycle("b-own", VM_B.replace("vm-b", "VM-B"), severity="high",
                     ttp="T1078", resource_type="identity", event="detection_timeout"))
    found = mem.retrieve_similar(_signal(VM_B), n=3)
    assert found[0]["signal_id"] == "b-own"             # the VM's own first
    assert len(set(_vms(found))) == 3                    # then one place per flooded VM


def test_another_vms_cycle_is_found_past_a_flood_of_nearer_ones(mem):
    """M5833: once a VM is at its bound, the search reads past it — a farther cycle of a third VM is
    given, never hidden by the flood."""
    for i in range(30):
        mem.store(_cycle(f"flood-{i}", VM_A))
    mem.store(_cycle("d-far", VM_D, severity="high", ttp="T1078", resource_type="identity",
                     event="detection_timeout"))
    found = mem.retrieve_similar(_signal(VM_C, rule="other-rule"), n=3)
    assert sorted(_vms(found)) == sorted([VM_A.lower(), VM_D.lower()])


def test_a_cycle_of_the_same_rule_comes_before_a_nearer_one_of_another(mem):
    """M5836: the rule absent from the similarity."""
    mem.store(_cycle("same-rule", VM_A, rule="ssh-brute-force", severity="high", event="detection_timeout"))
    mem.store(_cycle("other-rule", VM_B, rule="sudo-privilege-escalation"))
    [first] = mem.retrieve_similar(_signal(VM_C), n=1)
    assert first["signal_id"] == "same-rule"


def test_a_cycle_of_the_same_vm_comes_before_a_nearer_one_of_another(mem):
    """M5831: the VM absent from the ranking."""
    mem.store(_cycle("same-vm", VM_C, severity="high", event="detection_timeout"))
    mem.store(_cycle("other-vm", VM_B))
    [first] = mem.retrieve_similar(_signal(VM_C), n=1)
    assert first["signal_id"] == "same-vm"


def test_cycles_that_name_no_vm_count_as_one_vm_unknown(mem):
    """A cycle stored before SEC-I names no VM: they share one bound, as one VM unknown."""
    for i in range(5):
        mem._collection.add(ids=[f"cycle-legacy-{i}"], documents=[f"TTP: T1110.001 | legacy {i}"],
                            metadatas=[{"source": "real", "signal_id": f"legacy-{i}", "action": "x",
                                        "run_id": "r", "ttp": "T1110.001", "stored_at": int(time.time())}])
    mem.store(_cycle("b-own", VM_B))
    found = mem.retrieve_similar(_signal(VM_C), n=3)
    assert sorted(c["signal_id"].split("-")[0] for c in found) == ["b", "legacy"]


def test_more_cycles_that_name_no_vm_than_a_search_reads_never_hide_the_other_vms(mem):
    """M5840: a cycle stored before SEC-I has no `resource_id`, which no `$nin` leaves out — once the
    VM unknown was at its bound, its cycles filled every place the search past it read, and the
    other VMs' precedents never came: one precedent instead of three. Nothing stored is rewritten."""
    for i in range(20):                                  # more than a search reads (n × 4)
        mem._collection.add(ids=[f"cycle-legacy-{i}"],
                            documents=["TTP: T1110.001 | severity: critical | resource_type: vm | "
                                       f"event: detection | action: block_suspicious_ip | legacy {i}"],
                            metadatas=[{"source": "real", "signal_id": f"legacy-{i}", "action": "x",
                                        "run_id": "r", "ttp": "T1110.001", "stored_at": int(time.time())}])
    far = {"severity": "high", "ttp": "T1078", "resource_type": "identity", "event": "detection_timeout"}
    mem.store(_cycle("a-far", VM_A, **far))
    mem.store(_cycle("b-far", VM_B, **far))
    found = mem.retrieve_similar(_signal(VM_C, rule="other-rule"), n=3)
    assert sorted(c["signal_id"].split("-")[0] for c in found) == ["a", "b", "legacy"]
    legacy = mem._collection.get(ids=["cycle-legacy-0"], include=["metadatas"])["metadatas"][0]
    assert "resource_id" not in legacy                   # the memory read, never migrated


def test_a_cycle_keeps_its_vm_rule_and_says_it_was_not_corroborated(mem):
    """M5837: a cycle stored as corroborated, when nothing corroborated it."""
    mem.store(_cycle("one", VM_A.replace("vm-a", "VM-A") + "/"))
    meta = mem._collection.get(include=["metadatas"])["metadatas"][0]
    assert meta["resource_id"] == VM_A.lower()
    assert meta["rule_name"] == "ssh-brute-force"
    assert meta["corroborated"] is False


class _Memory:
    def __init__(self):
        self.stored: list[dict] = []

    def store(self, cycle):
        self.stored.append(cycle)


def _stored_by_the_agent(signal: dict) -> dict:
    mem = _Memory()
    state = {"signal": {"signal_id": "s", "event": "detection", "ttp": "T1110.001", "raw_signal": {},
                        **signal},
             "reasoning": "r", "confidence": 0.5, "action": "snapshot", "escalate": True,
             "escalation_reason": "", "outcome": None, "past_cycles": [], "dry_run": True}
    agent.store_cycle(state, memory=mem)
    [cycle] = mem.stored
    return cycle


def test_the_agent_stores_the_vm_and_the_rule_of_a_cycle():
    cycle = _stored_by_the_agent({"resource_id": VM_A, "context": {"rule_name": "ssh-brute-force",
                                                                   "attribution": "asset"}})
    assert (cycle["resource_id"], cycle["rule_name"], cycle["corroborated"]) == (VM_A, "ssh-brute-force", False)


def test_the_anchor_of_an_unattributed_detection_is_never_stored_as_its_vm():
    """M5835: the anchor's history fed by detections that were never about it."""
    cycle = _stored_by_the_agent({"resource_id": VM_A, "context": {"rule_name": "data-exfiltration-blob",
                                                                   "attribution": "unattributed"}})
    assert cycle["resource_id"] == ""


def test_an_unattributed_signal_is_weighed_by_no_vm(mem):
    mem.store(_cycle("a", VM_A, severity="high", event="detection_timeout"))
    mem.store(_cycle("b", VM_B))
    [first] = mem.retrieve_similar(_signal(VM_A, attribution="unattributed"), n=1)
    assert first["signal_id"] == "b"                 # the nearer text, the anchor not preferred


def test_what_the_model_reads_is_the_same_byte_for_byte_with_the_new_metadata():
    """The VM, the rule and the corroboration of a past cycle stay in the memory's metadata: the
    message to the model is identical to the byte (no end-to-end run required)."""
    signal = {"resource_id": VM_A, "event": "detection", "ttp": "T1110.001", "raw_signal": {}}
    base = [{"summary": "TTP: T1110.001 | severity: critical | action: block_suspicious_ip", "source": "real"}]
    more = [{**base[0], "resource_id": VM_B.lower(), "rule_name": "ssh-brute-force", "corroborated": False}]
    assert agent._build_user_message(signal, more) == agent._build_user_message(signal, base)
