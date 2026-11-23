"""The catalogue of the enquiry's reads (ENQ2, #1064; `docs/design/enquete-raisonnee.md` §4, §4.1).

**A closed catalogue.** Each read (`Read`) carries its id, its sentence for the model (what it reads,
never how), its query, the parameters the code fills (`PARAMS`: never the model, never a value of the
line left unchecked — each parameter declared with its check, which the code applies), how far back its
query reads (`lookback`: its `ago()`, counted from the moment the read runs), its declared latency, its
author, and **what it can say under each system** (`systems`: it reads there, or why it says nothing
there). The six reads are today's six queries of `investigate`, their text unchanged to the byte.

**The seven states of a read** (`ETATS`), never confused (§4): `lignes` (it answered, rows), `vide` (it
answered whole, no row: an absence its source vouches for), `sans_objet` (its source can say nothing
here: the counter does not exist under this system), `en_attente` (its source's latency has not passed
since the end of its window: nothing is said yet), `echec` (it did not complete: the workspace
unreachable, a 403, a 429, the query refused), `refusee` (the code refused to run it: a value of the
line that did not pass `kql.literal`, or a detection attributed to no VM), `non_permise` (a read asked
that is not served: an id outside the list permitted, or past the budget — ENQ4). `outcome` says the
state of a read once run, `ask` that of a read asked by id.

**What changes nothing yet.** The model still sees what it saw (`Reading.seen`: the rows, else `[]`),
and the guard of `decide` still counts what it counted (`Reading.gap`: `echec` and `refusee`, today's
`telemetry_gaps`, G2). **The window is counted from the read, not from the signal**: each query reads
back from the moment it runs (`ago()`), `lookback` long, so a read run late reads past the signal's
minutes. A query anchored on the signal's hour (`window(read, T)`: [T − lookback, T]) changes the rows
the model reads, and lands with the loop, at the harness (ENQ4). The watch does not know a VM's system
yet (the registry of assets does not carry it, and the line is never the source): an unknown system is
said `sans_objet` for the reads that depend on it.

**The form serves more than these six** (DOS4, §4.3; a new type of object later), without code here:
- a read of the dossier is one more `Read` — `kind` says how it is run (`kql` today; `arm`, a read of
  ARM through the provider's adapter, MC0), `obj` what it reads (`vm` today; a vault, a NIC);
- its parameters come from `PARAMS`, which grows by one entry per value the code fills, each declared
  with its check (`Param`: no check, no parameter; a vault's resource id: `kql.resource_id` again);
- `systems` names what it can say under each system; a platform read (`PLATFORM`: the activity log, a
  metric of the host) says the same under both;
- a new type of object (a storage account, an identity) takes its own `obj`, and its own `systems`
  keys if a system means something there: `says` reads only the keys a read declares.
Each read enters only measured (Q8, 23/11: `vault_activity`, `process_write_io`, `file_renames` at the
bench first), each in its own lot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Callable, Mapping

from glorfindel import kql

# ── The seven states (§4) ─────────────────────────────────────────────────────────────────────────

LIGNES, VIDE, SANS_OBJET, EN_ATTENTE = "lignes", "vide", "sans_objet", "en_attente"
ECHEC, REFUSEE, NON_PERMISE = "echec", "refusee", "non_permise"
ETATS = (LIGNES, VIDE, SANS_OBJET, EN_ATTENTE, ECHEC, REFUSEE, NON_PERMISE)
# Today's telemetry gaps (G2): a read that failed, or that was not run — unknown, never « nothing found ».
GAPS = (ECHEC, REFUSEE)

# ── Systems, authors ──────────────────────────────────────────────────────────────────────────────

LINUX, WINDOWS = "linux", "windows"
SYSTEMS = (LINUX, WINDOWS)
READS_HERE = "lit"            # a read's `systems` value: it reads under this system
UNKNOWN_SYSTEM = "le système de la VM n'est pas connu (le registre ne le porte pas) : cette lecture en dépend"

# Who writes what a read reads (§4.1, §10): the guest (root on the VM) can provoke the measure (a disk
# written, an agent stopped) or forge it (Syslog: any process writes there; a process's name, which the
# guest chooses: under the Process counter, a process named like a backup agent is one); the platform's
# own sources (the activity log, a metric of the host) the VM does not write.
GUEST_PROVOCABLE = "invité, provocable"
GUEST_FORGEABLE = "invité, forgeable"
PLATFORM = "plateforme"


@dataclass(frozen=True)
class Param:
    """A parameter the code fills: what it is, and its check (glorfindel/kql.py), which returns the value
    or raises `kql.UnsafeValue`. A parameter without a check is not declared: the check is what makes it
    a parameter, and the enquiry applies it before the value enters its literal (SEC4c)."""
    description: str
    check: Callable[[object], str]

    def __post_init__(self):
        if not callable(self.check):
            raise TypeError(f"un paramètre sans vérification ne se déclare pas ({self.description[:60]!r})")


# The parameters the code fills — each a KQL string literal (glorfindel/kql.py), checked for what it is
# first (SEC4c): the VM the registry names (the signal's resource id, never the line's `Computer`,
# SEC-I), the detection's source address. Never a value the model gives (§5.1).
PARAMS: Mapping[str, Param] = MappingProxyType({
    "vm": Param("l'identifiant de ressource de la VM du registre, jamais le Computer de la ligne",
                kql.resource_id),
    "ip": Param("l'adresse source de la ligne détectée", kql.ip),
})

# Declared ingestion latencies, P95 (glorfindel/rules/azure/detection_rules.yaml, its header: Perf AMA
# ≈ 45 s, Syslog DCR ≈ 480 s). Heartbeat is sent by the same agent as Perf and taken alike: not measured
# apart (EH2, the harness's session, recalibrates them).
PERF_LATENCY_S = 45
SYSLOG_LATENCY_S = 480
HEARTBEAT_LATENCY_S = 45


@dataclass(frozen=True)
class Read:
    """One read of the catalogue. `query` holds `{param}` for each of `params`, filled by the code."""
    id: str
    phrase: str                     # for the model: what it reads, never how (ENQ4's lire(id))
    query: str
    params: tuple[str, ...]
    lookback: timedelta             # its query's ago(): back from the moment it runs (ENQ4: from T)
    latency_s: int                  # its source's declared ingestion latency
    author: str
    systems: Mapping[str, str]      # system → READS_HERE, or why it says nothing there (sans objet)
    kind: str = "kql"               # how it is run: KQL on the workspace; DOS4 adds ARM reads
    obj: str = "vm"                 # what it reads

    def __post_init__(self):
        if undeclared := [p for p in self.params if p not in PARAMS]:
            raise ValueError(f"{self.id} : paramètre non déclaré dans PARAMS, sans vérification ({undeclared})")


@dataclass(frozen=True)
class Reading:
    """A read's outcome: its state, its rows (only when `lignes`), and why when it said nothing."""
    id: str
    etat: str
    rows: list = field(default_factory=list)
    why: str = ""

    @property
    def seen(self) -> list:
        """What the model sees of it, unchanged by ENQ2: its rows, else `[]` (« aucun résultat »)."""
        return self.rows if self.etat == LIGNES else []

    @property
    def gap(self) -> bool:
        """A telemetry gap for the guard of `decide` (G2): failed, or not run."""
        return self.etat in GAPS


# ── The six reads of `investigate` (§4.1) ─────────────────────────────────────────────────────────
# Scoped by `_ResourceId`, which the agent writes, never by `Computer`, which root on any host of the
# workspace chooses (SEC-I, V-09): a host named like the VM wrote the rows the model read for it. `=~`:
# the registry's case may differ from Log Analytics' (the routing compares them lowered too). Their
# text is today's, to the byte: their `ago()` is their `lookback`, read back from the moment they run,
# never from the signal (ENQ4 anchors it there). Kept short: the module's comment bounded the whole
# enquiry to 15 s, an intention no delay holds (§5.1: ENQ4 and ENQ5 make it one).

HEARTBEAT_GAP = """
Heartbeat
| where _ResourceId =~ {vm}
| where TimeGenerated > ago(2h)
| order by TimeGenerated asc
| extend PrevBeat = prev(TimeGenerated)
| extend GapMin = datetime_diff('minute', TimeGenerated, PrevBeat)
| where GapMin > 10
| project TimeGenerated, GapMin
| order by TimeGenerated desc
| limit 1
"""

DISK_PROCESSES = """
Perf
| where TimeGenerated > ago(5m)
| where _ResourceId =~ {vm}
| where ObjectName == "Process"
| where CounterName == "IO Write Bytes/sec"
| where InstanceName !in ("_Total", "Idle", "System")
| where CounterValue > 1000000
| summarize MaxWriteMBs = round(max(CounterValue) / 1048576, 1) by InstanceName
| top 5 by MaxWriteMBs desc
"""

# Identifiable backup agents only — generic POSIX tools (rsync, cp, tar, gzip)
# are NOT included: a ransomware archiving before encryption would match them,
# producing a false-negative "legitimate backup" conclusion.
BACKUP_AGENT = """
Perf
| where TimeGenerated > ago(10m)
| where _ResourceId =~ {vm}
| where ObjectName == "Process"
| where CounterName == "IO Write Bytes/sec"
| where InstanceName in~ ("waagent", "WALinuxAgent", "azure-backup", "snapd", "MicrosoftAzureRecoveryServices")
| summarize MaxWriteMBs = round(max(CounterValue) / 1048576, 1) by InstanceName
"""

SUCCESS_AUTH = """
Syslog
| where TimeGenerated > ago(5m)
| where _ResourceId =~ {vm}
| where Facility == "auth"
| where ProcessName in ("sshd", "sshd-session")
// sshd's own wording, at the start of the line (SEC2): never a user name holding it.
| where SyslogMessage startswith "Accepted " and SyslogMessage has {ip}
| project TimeGenerated, SyslogMessage
| limit 3
"""

# ago(10m) rather than ago(5m): privilege escalation takes ~40s, root commands
# follow immediately — a 5m window risks missing activity that started before
# the detection signal was processed.
ROOT_COMMANDS = """
Syslog
| where TimeGenerated > ago(10m)
| where _ResourceId =~ {vm}
// sudo logs to authpriv (measured under AMA).
| where Facility in ("auth", "authpriv")
// sudo's own lines (SEC2): the word is its tag (ProcessName), not in the message.
| where ProcessName == "sudo"
| where SyslogMessage has "USER=root" and SyslogMessage has "COMMAND="
| project TimeGenerated, SyslogMessage
| limit 10
"""

DISK_AFTER_ESC = """
Perf
| where TimeGenerated > ago(10m)
| where _ResourceId =~ {vm}
| where ObjectName in ("Logical Disk", "LogicalDisk")
| where CounterName == "Disk Write Bytes/sec"
| summarize MaxWriteMBs = round(max(CounterValue) / 1048576, 1),
            AvgWriteMBs = round(avg(CounterValue) / 1048576, 1)
"""

# KNOWN LIMITATION: \\Process(*)\\IO Write Bytes/sec is Windows-only. Linux AMA does not map this
# counter → ObjectName=Process data is never present in LAW on Linux VMs: these two reads always return
# [] there (Microsoft Learn, the guest OS metrics of the agent, Linux tab; the bench's DCR declares no
# Process counter, infra/terraform/monitoring.tf). That [] says nothing — `sans_objet`, never `vide` —,
# though the model still reads it as « aucun résultat » and the guard of `decide` does not count it
# (§1.3: never measured; ENQ5 says it to the model).
_PROCESS_LINUX = "compteur Process (IO Write Bytes/sec) : Windows seul, jamais collecté sous Linux"
_NO_SSHD = "aucun sshd dans Syslog sous Windows"
_NO_SUDO = "aucun sudo dans Syslog sous Windows"

READS: Mapping[str, Read] = MappingProxyType({r.id: r for r in (
    Read("heartbeat_gap",
         "Un trou de plus de 10 minutes dans les battements de l'agent de la VM, sur les 2 heures avant la "
         "lecture : un redémarrage, une restauration, ou un agent coupé.",
         HEARTBEAT_GAP, ("vm",), timedelta(hours=2), HEARTBEAT_LATENCY_S, GUEST_PROVOCABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE})),
    Read("top_write_processes",
         "Les cinq processus de la VM qui écrivent le plus sur le disque (plus de 1 Mo/s), sur les 5 minutes "
         "avant la lecture.",
         DISK_PROCESSES, ("vm",), timedelta(minutes=5), PERF_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: _PROCESS_LINUX, WINDOWS: READS_HERE})),          # if the DCR collects Process
    Read("backup_agent_check",
         "L'écriture disque des agents de sauvegarde nommés (l'agent Azure, Recovery Services), sur les 10 "
         "minutes avant la lecture.",
         BACKUP_AGENT, ("vm",), timedelta(minutes=10), PERF_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: _PROCESS_LINUX, WINDOWS: READS_HERE})),
    Read("successful_auth_from_ip",
         "Les connexions SSH acceptées depuis l'adresse source de la détection, sur les 5 minutes avant la "
         "lecture.",
         SUCCESS_AUTH, ("vm", "ip"), timedelta(minutes=5), SYSLOG_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: _NO_SSHD})),
    Read("root_commands",
         "Les commandes lancées en root par sudo sur la VM, sur les 10 minutes avant la lecture.",
         ROOT_COMMANDS, ("vm",), timedelta(minutes=10), SYSLOG_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: _NO_SUDO})),
    Read("disk_write_after_escalation",
         "Le débit d'écriture disque de la VM, son maximum et sa moyenne, sur les 10 minutes avant la lecture.",
         DISK_AFTER_ESC, ("vm",), timedelta(minutes=10), PERF_LATENCY_S, GUEST_PROVOCABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE})),
)})


# ── What a read can say, and when ───────────────────────────────────────────────────────────────

def says(read: Read, system: str) -> str:
    """Why `read` says nothing under `system` — "" when it reads there. A system it does not declare
    (unknown: "") makes every read that depends on the system sans objet, said as such."""
    if system in read.systems:
        return "" if read.systems[system] == READS_HERE else read.systems[system]
    return "" if all(v == READS_HERE for v in read.systems.values()) else UNKNOWN_SYSTEM


def window(read: Read, at: datetime) -> tuple[datetime, datetime]:
    """The window `read` covers when it ends at `at`: [at - lookback, at]. Today's queries end at the
    moment they run (their `ago()`), never at the signal's hour: anchoring them on T comes with ENQ4.
    Only `outcome` reads it, for a state the watch does not pass the hour of yet."""
    return at - read.lookback, at


def signal_at(signal: dict) -> datetime | None:
    """The signal's hour: the time of the row that fired, else the signal's own; None when neither reads."""
    raw = signal.get("raw_signal") if isinstance(signal.get("raw_signal"), dict) else {}
    row = raw.get("first_result_row") or raw.get("detected_data") or {}
    for value in ((row.get("TimeGenerated") if isinstance(row, dict) else None), signal.get("timestamp")):
        at = _when(value)
        if at is not None:
            return at
    return None


def outcome(read: Read, rows: list | None, *, refused: str = "", system: str = "",
            at: datetime | None = None, now: datetime | None = None) -> Reading:
    """The state of `read` once asked: `refused` (why the code did not run it), else its rows — None
    when it failed. Rows are rows, whatever the system; an empty answer is `sans_objet` where its source
    cannot say anything, `en_attente` while its latency has not passed since the end of its window (or
    when the signal's hour is unknown), `vide` only then."""
    if refused:
        return Reading(read.id, REFUSEE, why=refused)
    if rows is None:
        return Reading(read.id, ECHEC, why="la lecture n'a pas abouti (espace de travail injoignable, refus, quota)")
    if rows:
        return Reading(read.id, LIGNES, rows=rows)
    if why := says(read, system):
        return Reading(read.id, SANS_OBJET, why=why)
    if at is None or (now or datetime.now(timezone.utc)) < window(read, at)[1] + timedelta(seconds=read.latency_s):
        return Reading(read.id, EN_ATTENTE, why=f"la latence de sa source ({read.latency_s} s) n'est pas passée")
    return Reading(read.id, VIDE)


def ask(read_id: str, permitted=None) -> Read | Reading:
    """The read `read_id` names, or a `non_permise` outcome: an id outside the catalogue, or outside the
    list `permitted` (the fiche and the system's, ENQ4). The caller never builds a query from the id."""
    read = READS.get(read_id) if isinstance(read_id, str) else None
    if read is None or (permitted is not None and read_id not in permitted):
        return Reading(str(read_id)[:60], NON_PERMISE, why="hors de la liste permise")
    return read


def _when(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        return _when(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None
