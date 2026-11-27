"""The catalogue of the enquiry's reads (ENQ2, #1064; `docs/design/enquete-raisonnee.md` §4, §4.1).

**A closed catalogue.** Each read (`Read`) carries its id, its sentence for the model (what it reads,
never how), its query, the parameters the code fills (`PARAMS`: never the model, never a value of the
line left unchecked — each parameter declared with its check, which the code applies), how far back its
query reads (`lookback`: its `ago()`, counted from the moment the read runs), its declared latency, its
author, and **what it can say under each system** (`systems`: it reads there, or why it says nothing
there). Its first six (`INVESTIGATE`) are today's queries of `investigate`, to the byte; ENQ5a's follow.

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
the model reads, and lands with the loop's KQL reader, in production (ENQ5: the harness of ENQ4 reads recorded rows). The watch does not know a VM's system
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
    "vm": Param("l'identifiant de ressource de la VM du registre, jamais le Computer de la ligne", kql.resource_id),
    "ip": Param("l'adresse source de la ligne détectée", kql.ip),
    "vault": Param("l'identifiant de ressource du coffre de la VM, tiré de la configuration (DOS4)", kql.resource_id),
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
    ahead: timedelta = timedelta(0)     # DOS4: how far past T its window runs (the dossier's reads)
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
    servie: bool = True             # ENQ5a: False for a read not served yet (announced), never `sans_objet`'s « never »
    ingere: str = ""                # ENQ5a: what its source had ingested for the VM (ISO), when the read tells it

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
# never from the signal (ENQ5, the loop's KQL reader, anchors it there). Kept short: the module's comment bounded the whole
# enquiry to 15 s, an intention no delay holds (§5.1: the loop of ENQ4 holds one, at the harness).

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
         "Un trou de plus de 10 minutes dans les battements de l'agent de la VM, sur les 2 heures avant le "
         "signal : un redémarrage, une restauration, ou un agent coupé.",
         HEARTBEAT_GAP, ("vm",), timedelta(hours=2), HEARTBEAT_LATENCY_S, GUEST_PROVOCABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE})),
    Read("top_write_processes",
         "Les cinq processus de la VM qui écrivent le plus sur le disque (plus de 1 Mo/s), sur les 5 minutes "
         "avant le signal.",
         DISK_PROCESSES, ("vm",), timedelta(minutes=5), PERF_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: _PROCESS_LINUX, WINDOWS: READS_HERE})),          # if the DCR collects Process
    Read("backup_agent_check",
         "L'écriture disque des agents de sauvegarde nommés (l'agent Azure, Recovery Services), sur les 10 "
         "minutes avant le signal.",
         BACKUP_AGENT, ("vm",), timedelta(minutes=10), PERF_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: _PROCESS_LINUX, WINDOWS: READS_HERE})),
    Read("successful_auth_from_ip",
         "Les connexions SSH acceptées depuis l'adresse source de la détection, sur les 5 minutes avant le "
         "signal.",
         SUCCESS_AUTH, ("vm", "ip"), timedelta(minutes=5), SYSLOG_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: _NO_SSHD})),
    Read("root_commands",
         "Les commandes lancées en root par sudo sur la VM, de 10 minutes avant le signal à 5 minutes après.",
         ROOT_COMMANDS, ("vm",), timedelta(minutes=10), SYSLOG_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: _NO_SUDO}), ahead=timedelta(minutes=5)),
    Read("disk_write_after_escalation",
         "Le débit d'écriture disque de la VM, son maximum et sa moyenne, de 10 minutes avant le signal à 5 après.",
         DISK_AFTER_ESC, ("vm",), timedelta(minutes=10), PERF_LATENCY_S, GUEST_PROVOCABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE}), ahead=timedelta(minutes=5)),
)})


# ── What a read can say, and when ───────────────────────────────────────────────────────────────

def says(read: Read, system: str) -> str:
    """Why `read` says nothing under `system` — "" when it reads there. A system it does not declare
    (unknown: "") makes every read that depends on the system sans objet, said as such."""
    if system in read.systems:
        return "" if read.systems[system] == READS_HERE else read.systems[system]
    return "" if all(v == READS_HERE for v in read.systems.values()) else UNKNOWN_SYSTEM


def window(read: Read, at: datetime) -> tuple[datetime, datetime]:
    """The window `read` covers anchored at `at`: [at - lookback, at + ahead]. Today's queries end at the
    moment they run (their `ago()`), never at the signal's hour: anchoring them on T comes with ENQ5. The
    dossier's reads (DOS4) are anchored on T, and run `ahead` past it (`glorfindel/enquiry/platform.py`)."""
    return at - read.lookback, at + read.ahead


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
            at: datetime | None = None, now: datetime | None = None, ingere: datetime | None = None) -> Reading:
    """The state of `read` once asked: `refused` (why the code did not run it), else its rows — None
    when it failed. Rows are rows, whatever the system; an empty answer is `sans_objet` where its source
    cannot say anything, `en_attente` while its latency has not passed since the end of its window (or
    when the signal's hour is unknown), `vide` only then. ENQ5a (EH10): `ingere`, what the source had
    ingested for the VM (the read tells it: `ingestion_time()`, the last sample in the table), replaces the
    declared latency — `en_attente` until it reaches the end of the window, `vide` only once it has. A read
    that tells its ingestion (`INGESTION_DITE`) and did not, or said nothing ingested, is never `vide`."""
    if refused:
        return Reading(read.id, REFUSEE, why=refused)
    if rows is None:
        return Reading(read.id, ECHEC, why="la lecture n'a pas abouti (espace de travail injoignable, refus, quota)")
    seen = ingere.isoformat() if ingere is not None else ""
    if rows:
        return Reading(read.id, LIGNES, rows=rows, ingere=seen)
    if why := says(read, system):
        return Reading(read.id, SANS_OBJET, why=why)
    if at is not None and (ingere is not None or read.id in INGESTION_DITE):
        if ingere is None or ingere < window(read, at)[1]:
            return Reading(read.id, EN_ATTENTE, ingere=seen, why=(
                f"sa source n'a ingéré que jusqu'à {seen} : la fin de sa fenêtre n'est pas lue" if seen else
                "sa source n'a rien dit d'ingéré pour la VM depuis le début de la fenêtre : rien n'est encore dit"))
        return Reading(read.id, VIDE, ingere=seen)
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


# ── DOS4 (#1138): the dossier's reads, one vocabulary of states, the sentinel of `raw` ────────────────
# Kept at the end: the lines above are cited by the design notes (`docs/design/enquete-raisonnee.md`).
#
# The dossier's reads of the platform are declared in this form, apart (`glorfindel/enquiry/platform.py`,
# `PLATFORM_READS`, `kind="arm"`), never in READS until the bench has measured them (Q8): their window is
# anchored on the signal's hour (`ahead`: how far past T it runs), their parameters come from PARAMS (the
# vault's id among them), their author (`Read.author`) is what the dossier says of each fact.
#
# One vocabulary of states: the seven are the reads'; a fact of the dossier says one of five words — the
# same mapping for the enquiry and the dossier, before DOS6 and DOS7 show them (`lignes` is `lu`;
# `echec`, `refusee` and `non_permise` are each `illisible`, with their reason).
CARD_STATE: Mapping[str, str] = MappingProxyType({
    LIGNES: "lu", VIDE: "vide", SANS_OBJET: "sans_objet", EN_ATTENTE: "en_attente",
    ECHEC: "illisible", REFUSEE: "illisible", NON_PERMISE: "illisible"})


class _NoObject:
    """The sentinel of a parameter that has no object to name (a detection attributed to no VM): never
    `None`, which a raw value may be, and which then goes through its check like any other (fixed.py)."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "NO_OBJECT"


NO_OBJECT = _NoObject()


# ── ENQ5a (#1162): the three reads that judge a ransomware, served at the harness ─────────────────────
# Kept at the end too, for the same reason. T1486's obligatory reads (`fiches/T1486.yaml`) leave the
# reads announced (`knowledge.ANNONCEES`) and enter the catalogue: the harness plays them on reads
# recorded, or captured at the bench by the maintainer (`scripts/capture_enquete.py`); the watch reads
# none of them before ENQ5b. Each window is anchored on the signal's hour T (`window`), by the code —
# never by the model, which gives an id and nothing else (§5.1).
#
# - `perf_minute_series`: KQL, the guest's disk writes in `bin(1m)`, by volume, T − 5 min → T + 3 min —
#   the minute of the first sample past the rule's threshold and the next one (T1486-H1). Its window is
#   written in the query (`{debut}`, `{fin}`), filled by the loop's KQL reader; each minute says its
#   samples, its mean, its peak, its last sample, the step of the volume's series (`PasS`, read from the
#   data as the rule reads it), when it was ingested (`ingestion_time()`), and its first crossing of the
#   rule's threshold (`PremierPic`), computed as the shipped rule computes it (`ransomware-disk-write`,
#   glorfindel/rules/azure/detection_rules.yaml): a step of 25 s or less, the mean of two consecutive
#   samples of the same volume (`prev()`) above 45 MB/s — the first of the two is the crossing's hour —;
#   a coarser step, one sample above 25 MB/s. One row more (`Horizon`) says how far the table has
#   ingested this VM's samples of the same counter (a VM that sends its CPU, not its disk, has none): what
#   « waiting » is computed on (EH10), never the declared latency alone.
# - `vault_jobs`, `vault_activity`: ARM, read by the provider's adapter (DOS4's reads of the vault,
#   `glorfindel/providers/azure/dossier_reads.py`, the same code): the vault's jobs of this VM, T − 30 min
#   → T; the vault's activity log and its children's (its protected items, its policies, its settings),
#   T − 60 min → T. The platform's word: the VM does not write them. The activity log is read by ARM,
#   not in `AzureActivity` (EH8): the same Reader, no diagnostic setting to rely on at the client.

PERF_MINUTE_SERIES = """
let debut = {debut};
let fin = {fin};
let samples = Perf
| where TimeGenerated between (debut .. fin)
| where _ResourceId =~ {vm}
| where ObjectName in ("Logical Disk", "LogicalDisk")
| where CounterName == "Disk Write Bytes/sec"
| project TimeGenerated, InstanceName, CounterValue, Ingere = ingestion_time()
| order by InstanceName asc, TimeGenerated asc
| extend Same = prev(InstanceName) == InstanceName
| extend Gap = iff(Same, TimeGenerated - prev(TimeGenerated), timespan(null)),
         PrevValue = iff(Same, prev(CounterValue), real(null));
let serie = samples
| join kind=leftouter (samples | summarize Step = minif(Gap, Gap >= 1s) by InstanceName) on InstanceName
| extend Fine = isnotnull(Step) and Step <= 25s
| extend Rate = iff(Fine, iff(Gap <= 25s, (CounterValue + PrevValue) / 2, real(null)), CounterValue)
| extend Pic = (Fine and Rate > 45000000) or (not(Fine) and Rate > 25000000)
| extend PicAt = iff(Fine, TimeGenerated - Gap, TimeGenerated)
| summarize Echantillons = count(), MoyenneMBs = round(avg(CounterValue) / 1000000, 1),
            MaxMBs = round(max(CounterValue) / 1000000, 1), Dernier = max(TimeGenerated),
            PremierPic = minif(PicAt, Pic), PasS = toint(any(Step) / 1s),
            IngereA = max(Ingere) by Minute = bin(TimeGenerated, 1m), InstanceName;
let horizon = toscalar(Perf
| where TimeGenerated between (debut .. fin + 10m)
| where _ResourceId =~ {vm}
| where ObjectName in ("Logical Disk", "LogicalDisk")
| where CounterName == "Disk Write Bytes/sec"
| summarize max(TimeGenerated));
union (serie), (print Horizon = horizon)
| order by InstanceName asc, Minute asc
"""
WINDOW_MARKS = ("debut", "fin")        # the window's bounds the code writes in a query, never the model

VAULT_JOBS = "backupJobs.list({vault}) filtrée sur {vm} (entity_friendly_name, container), de T − 30 min à T"
VAULT_ACTIVITY = ("GET /subscriptions/<abonnement>/providers/Microsoft.Insights/eventtypes/management/values "
                  "$filter=eventTimestamp ge T − 60 min and le T and resourceUri eq {vault} (le coffre de {vm}) ; puis "
                  "le groupe de {vault}, filtré sur ses enfants (ACTIVITY_PAGES pages au plus) ; ses lectures "
                  "écartées")
# DH2 and DH1: the documentation's order (a few minutes), as DOS4 declares them (glorfindel/enquiry/platform.py).
VAULT_LATENCY_S = 300
_BOTH = MappingProxyType({LINUX: READS_HERE, WINDOWS: READS_HERE})


@dataclass(frozen=True)
class Lu:
    """What a reader that can tell how far its source has ingested returns: the rows, and that instant.
    `dit` tells « the source said » from « no horizon said »: a `Horizon` row there, but null, is « nothing
    ingested » (`dit` True, `ingere` None). `outcome` reads it in place of the declared latency (EH10);
    for a read of `INGESTION_DITE`, neither ever reads `vide`."""
    rows: list
    ingere: datetime | None = None
    dit: bool = False


# The reads that tell how far their source ingested: an empty answer is `vide` only on that word.
INGESTION_DITE = frozenset({"perf_minute_series"})


ENQ5A_READS: Mapping[str, Read] = MappingProxyType({r.id: r for r in (
    Read("perf_minute_series",
         "Le débit d'écriture disque de la VM minute par minute, par volume (moyenne, maximum, nombre "
         "d'échantillons, heure d'ingestion), de 5 minutes avant le signal à 3 minutes après.",
         PERF_MINUTE_SERIES, ("vm",), timedelta(minutes=5), PERF_LATENCY_S, GUEST_PROVOCABLE, _BOTH,
         ahead=timedelta(minutes=3)),
    Read("vault_jobs",
         "Les jobs du coffre de sauvegarde sur cette VM (opération, état, début, fin), sur les 30 minutes "
         "avant le signal.",
         VAULT_JOBS, ("vm", "vault"), timedelta(minutes=30), VAULT_LATENCY_S, PLATFORM, _BOTH, kind="arm",
         obj="vault"),
    Read("vault_activity",
         "Les écritures et les suppressions sur le coffre de sauvegarde et ses éléments (protection, "
         "politiques, suppression douce), et qui les a faites, sur l'heure avant le signal.",
         VAULT_ACTIVITY, ("vm", "vault"), timedelta(minutes=60), VAULT_LATENCY_S, PLATFORM, _BOTH, kind="arm",
         obj="vault"),
)})

# The six reads of `investigate` (ENQ2: `fixed.selection` routes among them, to the byte), then ENQ5a's.
INVESTIGATE = tuple(READS)
READS = MappingProxyType({**READS, **ENQ5A_READS})


# ── PIO1 (#1258): who writes under Linux, declared — measured at the bench before it enters (Q8) ───────
# Kept at the end too. Under Linux the agent sends no `Process` counter to Log Analytics (`_PROCESS_LINUX`):
# `top_write_processes` and `backup_agent_check` stay `sans_objet` there, untouched. The agent's one way of
# saying who writes is its OTel metric `process.disk.io` (a cumulative sum, `direction` read|write; the
# executable, the pid, the owner promoted to dimensions — Learn, the guest OS metrics
# reference), sent to an Azure Monitor workspace by a DCR of its own (infra/terraform/process_io.tf) and
# read in PromQL by the provider's adapter (`glorfindel/providers/azure/prometheus.py`), under the watch's
# identity — no new right: the Reader it already has on the bench's group, if `*/read` is enough for PromQL
# (built-in reading roles carry no data action), which the bench (a data action asked or not) and
# ENQ5b's end-to-end run (under the watch's identity) settle.
#
# **Declared, never served yet.** `process_write_io` is in `A_MESURER`, never in `READS`: the loop's lists
# (`loop.permises`), the message (`message.py`), the dossier's list (`dossier.WINDOWS_ONLY`) and the sheets
# read `READS` — none of them sees it, and it stays announced (`knowledge.ANNONCEES`: « non servie »).
# Neither `investigate` nor `decide` runs it; only the maintainer's capture at the bench
# (`scripts/capture_enquete.py --prom-endpoint`), apart from the reads the harness plays (its `a_mesurer`).
#
# **The process's name is forged by the guest**: it comes from /proc/[pid]/status, which the process
# chooses (prctl, argv[0]); root on the VM names its encryptor `waagent`. The read only tightens: no
# hypothesis that relaxes leans on the name of a backup agent (§4.4). Its author says it (GUEST_FORGEABLE).
#
# **Its states** (§4), said by the adapter, never confused: `lignes` (the series answered, some process
# wrote); `vide` (the VM's series answered, none wrote in the window: an absence the source vouches for);
# `sans_objet` (no workspace configured, or no series of the metric for this VM — the collection is not set
# or does not arrive: never « nothing written »); `en_attente` (the source's latency has not passed);
# `echec` (no token for the identity; a 403: the right absent; the workspace absent or unreachable; a delay;
# an answer unreadable — each said apart); `refusee`
# (the VM's id did not pass its check, or the read budget refused it).
#
# **Not measured** (docs/operations.md, « Qui écrit sous Linux, au banc (PIO1) »): the series' name and
# its labels in PromQL (Learn writes only the dotted, quoted form: `{"system.cpu.utilization"}`, `by
# ("Microsoft.resourceid")`); that the Linux agent of the bench collects it; its ingestion latency.

PROCESS_IO_METRIC = "process.disk.io"
PROCESS_IO_NAME = "process.executable.name"     # the dimension the sum is taken by: the guest's word
PROCESS_IO_RESOURCE = "Microsoft.resourceid"     # stamped by Azure Monitor on what the agent sends
PROCESS_IO_TOP = 5
# The PromQL, its values filled by the adapter, never by the model: `{vm}` the VM's resource id as a
# case-insensitive regex literal (the workspace's case may differ from the registry's), `{duree}` the
# window in seconds (the query runs at its end), `{top}` how many executables.
PROCESS_WRITE_IO = ('topk({top}, sum by ("' + PROCESS_IO_NAME + '") (increase({{"' + PROCESS_IO_METRIC
                    + '", "' + PROCESS_IO_RESOURCE + '"=~{vm}, direction="write"}}[{duree}s])))')
PROMQL_MARKS = ("top", "duree")                   # the code writes them, never the model
# Not measured (the documentation gives none for metrics sent to a workspace): two minutes, to measure.
PROM_LATENCY_S = 120

PIO_SANS_ESPACE = ("aucun espace de travail Azure Monitor configuré : la collecte de PIO1 n'est pas posée "
                   "(process_io_enabled)")
PIO_SANS_SERIE = ("aucune série process.disk.io pour cette VM dans l'espace : la collecte n'est pas posée sur "
                  "elle ou n'arrive pas — jamais « rien écrit »")
PIO_WINDOWS = "non mesurée sous Windows : le banc n'a que des VM Linux"
PIO_DROIT = ("le droit de lire l'espace de travail Azure Monitor manque : `*/read` ne suffit pas, une action de données est demandée (un rôle réduit à microsoft.monitor/accounts/data/metrics/read, un lot à lui)")
PIO_ABSENT = "l'espace de travail Azure Monitor est absent ou injoignable"
PIO_IDENTITE = "aucun jeton pour l'identité du processus (DefaultAzureCredential) : rien n'a été demandé à l'espace"
PIO_DELAI = "l'espace de travail Azure Monitor n'a pas répondu à temps (connexion ou réponse)"
PIO_ILLISIBLE = "la réponse de l'espace de travail Azure Monitor est illisible"
PIO_REFUSEE = "une valeur refusée : {}"
PIO_SANS_NOMBRE = "la réponse de l'espace de travail Azure Monitor est illisible (une valeur sans nombre)"
PIO_LATENCE = "la latence de sa source ({} s) n'est pas passée"
PIO_BUDGET = "le budget de lectures Prometheus de la minute est tenu (GLORFINDEL_PROM_BUDGET_PER_MIN)"

A_MESURER: Mapping[str, Read] = MappingProxyType({r.id: r for r in (
    Read("process_write_io",
         "Les exécutables de la VM qui ont écrit le plus d'octets sur le disque, chacun avec ses octets, sur "
         "les 5 minutes avant le signal (le nom vient de la VM, qui le choisit).",
         PROCESS_WRITE_IO, ("vm",), timedelta(minutes=5), PROM_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: PIO_WINDOWS}), kind="promql"),
)})


# ── WRT1 (#1275): who writes under Linux, by auditd's write watches — measured at the bench first (Q8) ──
# Kept at the end too. PIO1's measure at the bench (27/11, #1258): `process.disk.io` sees only the agent's
# own collector. The cause, confirmed by the sources and not measured: it runs as an unprivileged account,
# and the kernel lets a process read /proc/<pid>/io only for its own processes, short of CAP_SYS_PTRACE
# (proc_pid_io(5), ptrace(2)) — `process_write_io` says nothing of who writes under Linux without a privilege
# the agent does not have. The maintainer chose (27/11):
# « auditd, étendu ». The bench's auditd (AUD1) gains write watches on bounded folders
# (infra/terraform/scripts/auditd_write.sh, `auditd_write_watch_enabled`, off by default): one line per
# opening for write, creation, rename, unlink or truncation under a folder (key `eregion_write`), never one
# per write(); and the watch's beat (key `eregion_write_beat`, every 5 minutes), which says that the watch
# is set and that its lines arrive. Same channel as AUD1 (audisp-syslog → local6 → Syslog), same right (the
# workspace's Log Analytics Reader): nothing new.
#
# **Declared, never served yet**, as `process_write_io`: in `A_MESURER`, never in `READS` — neither
# `investigate` nor `decide` nor the loop runs it; only the capture at the bench (`scripts/capture_enquete.py`,
# its `a_mesurer`). Its reader (`glorfindel/auditd_write.py`) runs the query below through the KQL runner it
# is given (the capture's): no SDK of its own (MC0).
#
# **The executable's path is the kernel's, but the guest chooses where a binary lies**: `exe` is the path
# the kernel resolved, which argv[0] cannot hide — and root on the VM copies its encryptor to /usr/bin/tar,
# or runs it from a folder named like the backup extension's. Any local user writes local6 (`logger`): a
# line can add a writer, or a second SYSCALL record to an event (said, never chosen: such an event is
# never attributed, and never a beat — a beat's line written at a real write's serial does not hide it).
# The read only tightens: no hypothesis that relaxes leans on the executable's path (§4.4). Its author:
# GUEST_FORGEABLE.
#
# **Its states** (§4), said by the reader, never confused: `lignes` (some executable modified files in the
# window); `vide` (none did in the watched folders present on the VM, and the watch's beat was seen on both
# sides of the window — before its start, at or past its end — with none missing between: the source vouches
# for the absence against a failure only, never against a local user, who forges a beat with `logger -t
# audisp-syslog -p local6.info '… key="eregion_write_beat"'`); `sans_objet` (no beat for the VM: the watch is
# not set, no watched folder is on the VM, or its lines do not arrive; or it fell silent before the window's
# end, was not seen before its start, or missed a beat between — never « nobody wrote »); `en_attente` (the
# beat's period and the source's
# latency have not passed since the window's end); `echec` (a 403, the Syslog table absent, the query failed,
# an answer unreadable — each said apart); `refusee` (the VM's id did not pass its check, or the read budget
# refused it).

PROCESS_WRITE_AUDIT = r"""
let lignes = Syslog
| where TimeGenerated between ({avant} .. {horizon})
| where _ResourceId =~ {vm}
| where Facility == "local6"
| where ProcessName == "audisp-syslog" or ProcessName == "audispd"
| where SyslogMessage has "msg=audit("
| extend AuditEvent = extract(@"msg=audit\((\d+\.\d+:\d+)\)", 1, SyslogMessage),
         RecordType = extract(@"(?:^|\s)type=(SYSCALL|PATH)\s", 1, SyslogMessage),
         Key = extract(@'(?:^|\s)key="([^"]*)"', 1, SyslogMessage),
         Exe = extract(@"(?:^|\s)exe=(\S+)", 1, SyslogMessage),
         Uid = extract(@"(?:^|\s)uid=([0-9]{{1,10}})(?:\s|$)", 1, SyslogMessage),
         Auid = extract(@"(?:^|\s)auid=([0-9]{{1,10}})(?:\s|$)", 1, SyslogMessage),
         Pid = extract(@"(?:^|\s)pid=([0-9]{{1,10}})(?:\s|$)", 1, SyslogMessage),
         Name = extract(@"(?:^|\s)name=(\S+)", 1, SyslogMessage),
         NameType = extract(@"(?:^|\s)nametype=([A-Z_]+)", 1, SyslogMessage)
| where isnotempty(AuditEvent) and isnotempty(RecordType);
let qui = lignes
| where RecordType == "SYSCALL" and Key in ("eregion_write", "eregion_write_beat")
| summarize Syscalls = dcount(SyslogMessage), Writer = take_any(Exe), WriterUid = take_any(Uid),
            WriterAuid = take_any(Auid), WriterPid = take_any(Pid), WatchKey = take_any(Key) by AuditEvent
| extend Writer = iff(Syscalls == 1, Writer, ""), WatchKey = iff(Syscalls == 1, WatchKey, "eregion_write")
| extend WriterUid = iff(Syscalls == 1, WriterUid, ""), WriterAuid = iff(Syscalls == 1, WriterAuid, "");
lignes
| join kind=inner qui on AuditEvent
| extend Battement = WatchKey == "eregion_write_beat"
| where Battement or (TimeGenerated >= {debut} and TimeGenerated <= {fin})
| extend Entry = RecordType == "PATH" and NameType != "PARENT" and isnotempty(Name)
| summarize Evenements = dcount(AuditEvent), Fichiers = dcountif(Name, Entry), Chemins = make_set_if(Name, Entry, 16),
            Processus = dcount(WriterPid), Doubles = dcountif(AuditEvent, Syscalls != 1),
            Premier = min(TimeGenerated), Dernier = max(TimeGenerated)
            by Battement, Writer, WriterUid, WriterAuid
| extend Rang = iff(Battement, tolong(1000000000), Fichiers)
| order by Rang desc
| limit 50
"""
AUDIT_MARKS = ("avant", "debut", "fin", "horizon")    # the window, and the beat's on both sides: the code's
WRT_KEY, WRT_BEAT_KEY = "eregion_write", "eregion_write_beat"    # infra/terraform/scripts/auditd_write.sh
WRT_BEAT_S = 300                                 # the beat's period (eregion-write-beat.timer, OnCalendar=*:0/5)
WRT_HORIZON = timedelta(minutes=15)              # how far past the window's end the beat is looked for
WRT_AVANT = timedelta(seconds=WRT_BEAT_S + 60)   # how far before its start: one period, and a minute
WRT_ROWS = 50                                    # the query's `limit`: a full answer is said truncated
WRT_TOP = 5

WRT_SANS_ESPACE = "aucun espace de travail Log Analytics donné : rien n'a été lu"
WRT_SANS_MONTRE = ("aucun battement de la montre d'écriture pour cette VM : la montre n'est pas posée "
                   "(auditd_write_watch_enabled) ou ses lignes n'arrivent pas — jamais « personne n'a écrit »")
WRT_TUE = ("la montre d'écriture s'est tue avant la fin de la fenêtre (aucun battement après elle) : la VM "
           "éteinte, auditd arrêté ou ses règles retirées — jamais « personne n'a écrit »")
WRT_DEBUT = ("aucun battement de la montre d'écriture avant le début de la fenêtre : elle n'est pas prouvée "
             "posée sur toute la fenêtre — jamais « personne n'a écrit »")
WRT_TROU = ("un battement de la montre d'écriture manque dans la fenêtre : la montre rechargée, auditd arrêté ou "
            "la VM redémarrée — elle n'est pas prouvée posée sur toute la fenêtre, jamais « personne n'a écrit »")
WRT_WINDOWS = "auditd : Linux seul"
WRT_DROIT = "le droit de lire l'espace de travail manque (401, 403) : Log Analytics Reader sur l'espace"
WRT_TABLE = "la table Syslog est absente de l'espace de travail : aucune facilité n'y est collectée"
WRT_ABSENT = "l'espace de travail est absent ou injoignable"
WRT_DELAI = "l'espace de travail n'a pas répondu à temps"
WRT_ECHEC = "la requête n'a pas abouti"
WRT_ILLISIBLE = "la réponse de l'espace de travail est illisible"
WRT_REFUSEE = "une valeur refusée : {}"
WRT_LATENCE = "le battement ({} s) et la latence de sa source ({} s) ne sont pas passés depuis la fin de la fenêtre"
WRT_BUDGET = "le budget de lectures Log Analytics de la minute est tenu (GLORFINDEL_LA_BUDGET_PER_MIN)"
WRT_TRONQUEE = "plus de {} lignes dans la réponse : tronquée, les écrivains au-delà ne sont pas lus"

A_MESURER = MappingProxyType({**A_MESURER, **{r.id: r for r in (
    Read("process_write_audit",
         "Les exécutables de la VM qui ont modifié des fichiers dans les dossiers suivis par auditd, chacun avec "
         "son uid, son nombre de fichiers et quelques chemins, sur les 5 minutes avant le signal (le chemin de "
         "l'exécutable vient du noyau, mais la VM choisit où poser un binaire).",
         PROCESS_WRITE_AUDIT, ("vm",), timedelta(minutes=5), SYSLOG_LATENCY_S, GUEST_FORGEABLE,
         MappingProxyType({LINUX: READS_HERE, WINDOWS: WRT_WINDOWS})),
)}})
