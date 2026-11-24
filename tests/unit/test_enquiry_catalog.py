"""ENQ2 (#1064): the catalogue of the enquiry's reads, out of glorfindel/agent.py
(`docs/design/enquete-raisonnee.md` §4, §4.1, §13).

- **The message to the model, to the byte.** On fixed signals, Linux and Windows, a failure, a
  refusal, an unattributed detection and a row no read of today calls for: the message
  `_build_user_message` writes, the KQL each query sends and the gaps for the guard of `decide` are
  those of origin/main before ENQ2 (their sha256, measured there on the same cases).
- **The catalogue**: the six reads of `investigate`, each with its sentence, its parameters filled by
  the code, how far back it reads (its `ago()`, from the read, never from the signal: ENQ4), its
  latency, its author and what it can say under each system (§4.1's table); every value a KQL literal,
  every query scoped by `_ResourceId`.
- **The parameters** (ENQ2b, #1069): each declared with its check, which the enquiry applies — a
  parameter without one is not declared.
- **The seven states**, never confused: a failure is never `vide`, a counter that does not exist is
  never `vide`, an answer before its source's latency is never `vide`.

No Azure call, no model call. Mutants M7095–M7099 (scripts/mutants/ENQ2.py) and M7103–M7106
(scripts/mutants/ENQ2b.py) are measured here.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from glorfindel import agent, dossier, kql
from glorfindel.enquiry import catalog, fixed

SUB = "00000000-0000-0000-0000-0000000000aa"
WS = "00000000-0000-0000-0000-0000000000dd"
AT = datetime(2026, 11, 10, 2, 34, 10, tzinfo=timezone.utc)


def _vm(name: str) -> str:
    return f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/{name}"


LINUX_VM, WINDOWS_VM = _vm("vm-linux-01"), _vm("vm-win-01")

# ── 1. The message, to the byte ───────────────────────────────────────────────────────────────────
# Each case: the detected row, the resource id, the context, what each query answers (by a text it
# holds; None: the query failed) — then the sha256 of the message, the gaps, and the sha256 of the
# queries sent (joined by a line `----`), measured on origin/main (26ec6587) before ENQ2.

CASES = {
    "linux_escalation": (
        {"Computer": "vm-linux-01", "_ResourceId": LINUX_VM, "TimeGenerated": AT.isoformat(),
         "SyslogMessage": "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash"},
        LINUX_VM, {"run_id": "watch-sudo-1"},
        {'ProcessName == "sudo"': [{"TimeGenerated": AT, "SyslogMessage":
                                    "alice : TTY=pts/0 ; PWD=/ ; USER=root ; COMMAND=/usr/bin/tar czf /tmp/x"}],
         "Disk Write Bytes/sec": [{"MaxWriteMBs": 59.4, "AvgWriteMBs": 31.2}]},
        "e0de6e88a00bd8a934cca5f8a091411ac3551e3ca62393cf15cd5d8c993fb2e5", [],
        "4857da1b3a6fcc2d178d9758cd9224ba74e4ca8662a681d195113f6ca8afe7cc",
    ),
    "linux_disk_write": (
        {"Computer": "vm-linux-01", "_ResourceId": LINUX_VM, "MaxWrite": 59.4, "TimeGenerated": AT.isoformat()},
        LINUX_VM, {"run_id": "watch-disk-1"},
        {"IO Write Bytes/sec": [], "Heartbeat": []},
        "a6ae7ae227db8e0b760081d6f68fb1868b7f56ae06a0ad7de40a0edf5b178252", [],
        "ccf0ea749eaab77234e71b2fd625483ef3919fb45fc68476abbb4d6b3ba0d81d",
    ),
    "windows_disk_write": (
        {"Computer": "vm-win-01", "_ResourceId": WINDOWS_VM, "DiskWrite": 88.0, "TimeGenerated": AT.isoformat()},
        WINDOWS_VM, {"run_id": "watch-disk-2"},
        {"top 5 by MaxWriteMBs": [{"InstanceName": "encryptor", "MaxWriteMBs": 85.1},
                                  {"InstanceName": "svchost", "MaxWriteMBs": 1.2}],
         "MicrosoftAzureRecoveryServices": [{"InstanceName": "MicrosoftAzureRecoveryServices", "MaxWriteMBs": 3.3}],
         "Heartbeat": [{"TimeGenerated": AT, "GapMin": 14}]},
        "b6fa8551767b53a2dededbdf2cb0fcab4b9c92ffb9e00b5608186243160e7bdc", [],
        "6c545c4fc0c75b377b5f426ff10e521816347a3952b2515d7a0308adc7d6ef78",
    ),
    "linux_brute_force": (
        {"Computer": "vm-linux-01", "_ResourceId": LINUX_VM, "SourceIP": "198.51.100.7", "FailedAttempts": 31},
        LINUX_VM, {"run_id": "watch-ssh-1"},
        {"Accepted ": [{"TimeGenerated": AT, "SyslogMessage":
                        "Accepted password for alice from 198.51.100.7 port 41000 ssh2"}]},
        "920bcc9d493212e27b50c1b2593312ee2b215dcd36bdcae97d0d59d7e72e439f", [],
        "759594af3b3aac4833651872be61e9049c3df428637f2fd36c23417c41ee05ea",
    ),
    "a_failure_and_a_refusal": (
        {"Computer": "vm-linux-01", "_ResourceId": LINUX_VM, "SourceIP": "198.51.100.7%eth0",
         "FailedAttempts": 31, "MaxWrite": 61.0},
        LINUX_VM, {"run_id": "watch-mix-1"},
        {"top 5 by MaxWriteMBs": None, "Heartbeat": [{"TimeGenerated": AT, "GapMin": 22}]},
        "69f9dcfcdec2ec58ece8f889a1b348bc447d88c4d54fc703ce5462eecbb4ac8b",
        ["top_write_processes", "successful_auth_from_ip"],
        "ccf0ea749eaab77234e71b2fd625483ef3919fb45fc68476abbb4d6b3ba0d81d",
    ),
    "no_column_of_today": (
        {"Computer": "vm-linux-01", "_ResourceId": LINUX_VM, "MaxWriteMBs": 59.4, "SyslogMessage": "alice : USER=root"},
        LINUX_VM, {"run_id": "watch-other-1"},
        {},
        "f4156635bfe0afdc8e8b90e9406434cd8535c52a76857964af8ee7ce4f6ad401", None,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
    "unattributed": (
        {"Computer": "vm-linux-01", "SyslogMessage": "bob : TTY=pts/1 ; USER=root ; COMMAND=/bin/id"},
        f"/subscriptions/{SUB}/resourceGroups/rg-example", {"run_id": "watch-sudo-2", "attribution": "unattributed"},
        {},
        "a12ecd5b9b50edaaa97781b451db25f3e07845f2defb422312dc496970b4ae5f",
        ["root_commands", "disk_write_after_escalation"],
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    ),
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _state(row: dict, rid: str, context: dict, case: str = "enq2") -> dict:
    signal = {"signal_id": f"sig-{case}", "event": "detection", "resource_id": rid, "ttp": "T1486",
              "severity": "high", "timestamp": AT.isoformat(), "context": dict(context),
              "raw_signal": {"log_analytics_workspace_id": WS, "first_result_row": dict(row)}}
    return {"signal": signal, "past_cycles": [], "incident": None, "dry_run": False}


def _serve(monkeypatch, answers: dict) -> list[str]:
    asked: list[str] = []

    def run(_ws, query):
        asked.append(query)
        for needle, rows in answers.items():
            if needle in query:
                return None if rows is None else [dict(r) for r in rows]
        return []
    monkeypatch.setattr(fixed, "run_query", run)
    return asked


@pytest.mark.parametrize("case", list(CASES))
def test_the_message_to_the_model_is_the_one_before_enq2_to_the_byte(monkeypatch, case):
    """M7099: the message changed — what an enquiry's read is shown as, its rows or « aucun résultat »."""
    row, rid, context, answers, message, gaps, queries = CASES[case]
    asked = _serve(monkeypatch, answers)
    out = agent.investigate(_state(row, rid, context, case))
    assert _digest(agent._build_user_message(out["signal"], [])) == message
    assert out.get("telemetry_gaps") == gaps
    assert _digest("\n----\n".join(asked)) == queries          # the same KQL, in the same order


def test_the_windows_and_linux_cases_say_what_their_reads_said(monkeypatch):
    """The frozen cases are what they claim: rows under Windows, `[]` for the Process reads under Linux."""
    _serve(monkeypatch, CASES["windows_disk_write"][3])
    win = agent.investigate(_state(*CASES["windows_disk_write"][:3]))["signal"]["raw_signal"]["investigative_context"]
    assert [len(v) for v in win.values()] == [2, 1, 1]
    _serve(monkeypatch, CASES["linux_disk_write"][3])
    lin = agent.investigate(_state(*CASES["linux_disk_write"][:3]))["signal"]["raw_signal"]["investigative_context"]
    assert list(lin) == ["top_write_processes", "backup_agent_check", "heartbeat_gap"] and not any(lin.values())


def test_agent_holds_no_query_of_the_enquiry_any_more():
    """WCH1: the templates and their runner left agent.py; investigate reads them from the catalogue."""
    source = Path(agent.__file__).read_text(encoding="utf-8")
    assert "_IQ_" not in source and "_run_investigative_query" not in source
    assert "from glorfindel.enquiry import fixed" in source
    for read in catalog.READS.values():
        assert read.query not in source


# ── 2. The catalogue ──────────────────────────────────────────────────────────────────────────────

# §4.1, the table of the note: what each read says under each system.
EXPECTED_SYSTEMS = {
    "heartbeat_gap": (True, True),
    "top_write_processes": (False, True),
    "backup_agent_check": (False, True),
    "successful_auth_from_ip": (True, False),
    "root_commands": (True, False),
    "disk_write_after_escalation": (True, True),
}


def test_the_six_reads_of_investigate_are_the_catalogue():
    """`investigate` routes among its six (ENQ2); ENQ5a's three follow them, never routed by `investigate`."""
    assert catalog.INVESTIGATE == tuple(EXPECTED_SYSTEMS)
    assert tuple(catalog.READS) == catalog.INVESTIGATE + ("perf_minute_series", "vault_jobs", "vault_activity")
    every = {"MaxWrite": 1, "FailedAttempts": 3, "SourceIP": "198.51.100.7", "SyslogMessage": "USER=root ; COMMAND=/x"}
    assert sorted(fixed.selection(every)) == sorted(catalog.INVESTIGATE)


@pytest.mark.parametrize("read_id", list(EXPECTED_SYSTEMS))
def test_what_each_read_says_under_each_system(read_id):
    """M7095: a Linux read said applicable where its source does not exist (the Process counter)."""
    read = catalog.READS[read_id]
    linux, windows = EXPECTED_SYSTEMS[read_id]
    assert set(read.systems) == set(catalog.SYSTEMS)
    assert (catalog.says(read, catalog.LINUX) == "") is linux
    assert (catalog.says(read, catalog.WINDOWS) == "") is windows
    # An unknown system: a read that depends on the system says so, never that it read.
    assert (catalog.says(read, "") == "") is (linux and windows)
    if not (linux and windows):
        assert catalog.says(read, "") == catalog.UNKNOWN_SYSTEM


# §4.1, who writes what each read reads (ENQ2b): a process's name is the guest's choice — a process named
# like a backup agent is one, under the Process counter — so the two Process reads are forgeable.
EXPECTED_AUTHORS = {
    "heartbeat_gap": catalog.GUEST_PROVOCABLE,
    "top_write_processes": catalog.GUEST_FORGEABLE,
    "backup_agent_check": catalog.GUEST_FORGEABLE,
    "successful_auth_from_ip": catalog.GUEST_FORGEABLE,
    "root_commands": catalog.GUEST_FORGEABLE,
    "disk_write_after_escalation": catalog.GUEST_PROVOCABLE,
    # ENQ5a: the guest's series (provoked by writing), the vault's word (the platform's).
    "perf_minute_series": catalog.GUEST_PROVOCABLE,
    "vault_jobs": catalog.PLATFORM,
    "vault_activity": catalog.PLATFORM,
}


def test_who_writes_what_each_read_reads():
    """M7103: `backup_agent_check` said provocable — its rows name a process, which the guest names. No code
    reads a read's author yet, nor does it enter the message: the catalogue is what holds it (DOS4 reads it)."""
    assert {r.id: r.author for r in catalog.READS.values()} == EXPECTED_AUTHORS


def test_the_dossier_takes_its_windows_only_reads_from_the_catalogue():
    """DOS3's facts: a Process read empty under Linux is sans objet — the same list, from one place."""
    assert dossier.WINDOWS_ONLY == ("top_write_processes", "backup_agent_check")


@pytest.mark.parametrize("read_id", list(EXPECTED_SYSTEMS))
def test_each_read_is_whole_and_bounded_by_the_registrys_vm(read_id):
    """M7098: the `_ResourceId` bound of a query taken out — it reads every VM of the workspace."""
    read = catalog.READS[read_id]
    assert read.phrase.strip() and read.author in (catalog.GUEST_PROVOCABLE, catalog.GUEST_FORGEABLE, catalog.PLATFORM)
    assert read.latency_s > 0 and read.kind == "kql" and read.obj == "vm"
    assert set(read.params) <= set(catalog.PARAMS) and "vm" in read.params
    assert set(re.findall(r"\{(\w+)\}", read.query)) == set(read.params)
    assert read.query.count("| where _ResourceId =~ {vm}\n") == 1 and "Computer" not in read.query
    # How far back it reads is its query's `ago()`, back from the moment it runs — never from the signal
    # (ENQ4 anchors it there); its sentence says the same.
    (ago,) = re.findall(r"ago\((\d+)([mh])\)", read.query)
    assert timedelta(**{"minutes" if ago[1] == "m" else "hours": int(ago[0])}) == read.lookback
    assert "avant la lecture" in read.phrase and "signal" not in read.phrase


# ── The parameters, each with its check (ENQ2b) ───────────────────────────────────────────────────

def test_each_parameter_is_declared_with_its_check():
    assert catalog.PARAMS["vm"].check is kql.resource_id and catalog.PARAMS["ip"].check is kql.ip
    assert all(isinstance(p, catalog.Param) and p.description.strip() for p in catalog.PARAMS.values())


def test_a_parameter_without_a_check_is_not_declared():
    """M7105: a parameter declared without its check, accepted — a value of the line then enters bare.
    M7106: a read naming a parameter PARAMS does not declare, accepted."""
    for check in (None, "kql.ip"):
        with pytest.raises(TypeError, match="sans vérification"):
            catalog.Param("une valeur de la ligne", check)
    with pytest.raises(ValueError, match="non déclaré"):
        catalog.Read("x", "x", "Perf | where Computer == {host}", ("host",), timedelta(minutes=5), 45,
                     catalog.GUEST_FORGEABLE, MappingProxyType({}))


def test_the_enquiry_applies_each_parameters_own_check(monkeypatch):
    """M7104: the check of a parameter skipped in `fixed` — the value goes to its literal unchecked."""
    seen = []

    def refuse(value):
        seen.append(value)
        raise kql.UnsafeValue("refusée par la vérification du catalogue")
    params = {**catalog.PARAMS, "ip": catalog.Param("l'adresse", refuse)}
    monkeypatch.setattr(catalog, "PARAMS", MappingProxyType(params))
    asked = _serve(monkeypatch, {})
    out = fixed.enquire({"SourceIP": "198.51.100.7", "FailedAttempts": 3}, LINUX_VM, WS, unattributed=False)
    assert seen == ["198.51.100.7"] and asked == [] and out.gaps == ["successful_auth_from_ip"]
    assert out.refused == {"198.51.100.7": "refusée par la vérification du catalogue"}


def test_every_value_enters_its_query_as_a_literal(monkeypatch):
    """M7097: a value out of its literal (`kql.literal`) — the VM's id and the address written bare."""
    asked = _serve(monkeypatch, {})
    row = {"SourceIP": "198.51.100.7", "FailedAttempts": 3, "MaxWrite": 9, "SyslogMessage": "USER=root ; COMMAND=/x"}
    fixed.enquire(row, LINUX_VM, WS, unattributed=False)
    assert len(asked) == 6
    assert all(f"| where _ResourceId =~ {kql.literal(LINUX_VM)}\n" in q for q in asked)
    (auth,) = [q for q in asked if "Accepted " in q]
    assert f"SyslogMessage has {kql.literal('198.51.100.7')}\n" in auth


def test_a_value_refused_runs_no_query_and_is_a_gap(monkeypatch):
    asked = _serve(monkeypatch, {})
    out = fixed.enquire({"SourceIP": "198.51.100.7 or 1==1", "FailedAttempts": 3}, LINUX_VM, WS, unattributed=False)
    assert asked == [] and out.gaps == ["successful_auth_from_ip"] and out.context == {"successful_auth_from_ip": []}
    (reading,) = out.readings
    assert reading.etat == catalog.REFUSEE and "kql.literal" in reading.why
    assert list(out.refused) == ["198.51.100.7 or 1==1"]


def test_an_unattributed_detection_is_refused_never_run(monkeypatch):
    asked = _serve(monkeypatch, {})
    out = fixed.enquire({"SyslogMessage": "USER=root ; COMMAND=/x"}, f"/subscriptions/{SUB}", WS, unattributed=True)
    assert asked == [] and [r.etat for r in out.readings] == [catalog.REFUSEE] * 2
    assert all("non attribuée" in r.why for r in out.readings) and out.refused == {}


# ── 3. The seven states ───────────────────────────────────────────────────────────────────────────

def test_the_seven_states_are_seven():
    assert len(set(catalog.ETATS)) == 7 and catalog.GAPS == (catalog.ECHEC, catalog.REFUSEE)


def test_a_failed_read_is_a_failure_never_empty(monkeypatch):
    """M7096: a failure rendered empty — the guard of `decide` no longer sees the gap (G2)."""
    read = catalog.READS["heartbeat_gap"]
    failed = catalog.outcome(read, None, system=catalog.LINUX, at=AT, now=AT + timedelta(hours=1))
    assert failed.etat == catalog.ECHEC and failed.gap and failed.seen == [] and failed.why
    _serve(monkeypatch, {"Heartbeat": None})
    out = fixed.enquire({"MaxWrite": 9}, LINUX_VM, WS, unattributed=False)
    assert [r.etat for r in out.readings] == [catalog.SANS_OBJET, catalog.SANS_OBJET, catalog.ECHEC]
    assert out.gaps == ["heartbeat_gap"]


def test_an_empty_answer_says_what_its_source_vouches_for():
    later = AT + timedelta(minutes=30)
    process, heartbeat = catalog.READS["top_write_processes"], catalog.READS["heartbeat_gap"]
    # The Process counter under Linux: it says nothing there — never « nothing found ».
    assert catalog.outcome(process, [], system=catalog.LINUX, at=AT, now=later).etat == catalog.SANS_OBJET
    assert catalog.outcome(process, [], system=catalog.WINDOWS, at=AT, now=later).etat == catalog.VIDE
    assert catalog.outcome(process, [], system="", at=AT, now=later).etat == catalog.SANS_OBJET
    # Before its source's latency has passed since the end of its window: nothing is said yet.
    soon = AT + timedelta(seconds=heartbeat.latency_s - 1)
    assert catalog.outcome(heartbeat, [], system=catalog.LINUX, at=AT, now=soon).etat == catalog.EN_ATTENTE
    assert catalog.outcome(heartbeat, [], system=catalog.LINUX, now=later).etat == catalog.EN_ATTENTE   # no hour
    assert catalog.outcome(heartbeat, [], system=catalog.LINUX, at=AT, now=later).etat == catalog.VIDE
    # Rows are rows, whatever the system; neither a gap.
    rows = [{"GapMin": 14}]
    lines = catalog.outcome(process, rows, system=catalog.LINUX, at=AT, now=later)
    assert lines.etat == catalog.LIGNES and lines.seen is rows and not lines.gap
    assert not catalog.outcome(heartbeat, [], system=catalog.LINUX, at=AT, now=later).gap


def test_the_window_ends_where_it_is_anchored():
    """Today a query ends at the moment it runs (`ago()`); `window(read, T)` is the window anchored on the
    signal's hour T, which `outcome` reads and ENQ4's queries will."""
    read = catalog.READS["root_commands"]
    assert catalog.window(read, AT) == (AT - timedelta(minutes=10), AT)
    assert "ago(10m)" in read.query and "{at}" not in read.query          # the KQL reads from the read
    row_time = {"raw_signal": {"first_result_row": {"TimeGenerated": "2026-11-10T02:34:10Z"}},
                "timestamp": "2026-11-10T02:40:00+00:00"}
    assert catalog.signal_at(row_time) == AT
    assert catalog.signal_at({"timestamp": "2026-11-10T02:34:10"}) == AT
    assert catalog.signal_at({"raw_signal": {"first_result_row": {"TimeGenerated": "hier"}}}) is None


def test_a_read_asked_outside_the_list_is_not_permitted():
    assert catalog.ask("root_commands") is catalog.READS["root_commands"]
    for asked, permitted in (("drop_table", None), ("root_commands", ["heartbeat_gap"]), (["root_commands"], None)):
        out = catalog.ask(asked, permitted)
        assert isinstance(out, catalog.Reading) and out.etat == catalog.NON_PERMISE and not out.gap
