"""Who writes under Linux, read in auditd's write watches (WRT1, #1275; `docs/design/enquete-raisonnee.md`
§4.4, §9.7).

PIO1 measured at the bench (27/11, #1258) that the agent's per-process metric, `process.disk.io`, sees only
the agent's own collector — the cause confirmed by the sources, not measured: it runs unprivileged, and the
kernel lets a process read /proc/<pid>/io only for its own processes. The bench's auditd (AUD1) gains write watches instead (`infra/terraform/scripts/
auditd_write.sh`, off by default): for each bounded folder, one event per opening for write, creation,
rename, unlink or truncation under it (key `eregion_write`) — the executable, its uid, auid and pid, the
paths it named — and the watch's beat (key `eregion_write_beat`, every 5 minutes). The lines go to Syslog as
AUD1's do (audisp-syslog, facility local6): the same table, the same right (Log Analytics Reader).

**`process_write_audit(vm, at, kql_run=…)`**: for `vm` and the window anchored on `at` (T − 5 min → T, as
`process_write_io`), the executables that modified files in the watched folders, each with its uid, its
login uid, how many processes, files and events, a few paths, as a `catalog.Reading` — its state always said.
`Chemins` is a `dynamic` column: the SDK hands it on as its JSON text, read as a list (`chemins`):
- `lignes`: some executable modified files; the rows, the most files first, `catalog.WRT_TOP` at most;
- `vide`: none did, and the beat was seen on both sides of the window (before its start, at or past its end)
  — the source vouches for the absence (a write by io_uring, or into a file opened before the watch was
  loaded, escapes the watch: `vide` never says more than « no syscall the watch sees »);
- `en_attente`: no writer, and the beat's period and the source's latency have not passed since the end;
- `sans_objet`: no writer and no beat for the VM (the watch is not set, or does not arrive), a beat that
  stopped before the window's end or was not seen before its start — never « nobody wrote »;
- `echec`: the query failed — a 401 or 403 (the right), the Syslog table absent, a 404 (the workspace), a
  delay, anything else —, or an answer unreadable; each said apart;
- `refusee`: the VM's id did not pass its check, or the read budget (`read_budget.LOG_ANALYTICS`, DOS4)
  refused it.

**Run by the caller's KQL runner** (`kql_run(query, timespan)`, the capture's: the provider's adapter, which
raises on a failed query) — this module imports no SDK (MC0). Neither `investigate` nor `decide` nor the
enquiry's loop runs it before ENQ5b: the read is in `catalog.A_MESURER`, never in `READS`.

**Bounded and pseudonymised, as the rest of the enquiry**: a path is kept as its folder and its extension
(`/var/backups/bree-site/*.tgz`), never its file's name; a home folder's owner is hidden (`/home/<u>/…`); a
relative path (an `openat` on a directory's descriptor, or on the working directory) is said relative
(`./…`), never completed by a guess; at most `PATHS` patterns a writer, each `PATH_MAX` characters; the
executable's path bounded, its control characters dropped. The capture's pseudonyms (the VM, the
subscription, the GUIDs, the IPv4 addresses) apply on top.

**The executable's path comes from the kernel, but a malicious binary chooses it**: `exe` is the path the
kernel resolved (argv[0] cannot hide it), and root on the VM puts its encryptor at /usr/bin/tar, or in a
folder named like the backup extension's. Any local user writes local6 (`logger`): a forged line adds a
writer, or gives an event a second SYSCALL record — that event's writer is then never chosen (`Doubles`,
an empty writer), and the event is never taken for a beat (a beat's line at a real write's serial hides
nothing). Root can remove the watches and keep the beat. **No hypothesis that relaxes leans on this
read** (§4.4): it only tightens.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from glorfindel import auditd, kql, read_budget
from glorfindel.enquiry import catalog

READ_ID = "process_write_audit"
WHO = "enquete"
EXE_MAX = 200
PATH_MAX = 120
PATHS = 3
_EXT = re.compile(r"\.([A-Za-z0-9]{1,10})$")
_HOME = re.compile(r"^/home/[^/]+")


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def bornes(at: datetime, now: datetime) -> tuple[datetime, datetime, datetime]:
    """The window [debut, fin] anchored at `at` (its end never past `now`), and the beat's horizon past it."""
    debut, fin = catalog.window(catalog.A_MESURER[READ_ID], at)
    fin = min(fin, now)
    return debut, fin, fin + catalog.WRT_HORIZON


def texte(vm: str, debut: datetime, fin: datetime, horizon: datetime) -> str:
    """`process_write_audit`'s KQL for `vm`: its values from the code only (`kql.literal` after the check).
    The beat is read from one period before the window (`avant`) to its horizon; the writers, in the window."""
    return catalog.A_MESURER[READ_ID].query.format(
        vm=kql.literal(kql.resource_id(vm)), avant=f"datetime({_iso(debut - catalog.WRT_AVANT)})",
        debut=f"datetime({_iso(debut)})", fin=f"datetime({_iso(fin)})",
        horizon=f"datetime({_iso(horizon)})").strip()


# The `dynamic` column as the SDK hands it on: its JSON text (measured on Imladris, 20/11, SLF1b;
# `docs/azure.md`), or a list (the tests' subset); a text longer than this is unreadable, never decoded.
CHEMINS_TEXT_MAX = 64 * 1024


def chemins(value) -> list:
    """The `Chemins` column, a `make_set_if`: a list, or its JSON text (bounded) decoding to one; each element a
    text. Anything else raises ValueError: an answer unreadable, never « no path »."""
    if isinstance(value, str):
        if len(value) > CHEMINS_TEXT_MAX:
            raise ValueError("Chemins")
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            raise ValueError("Chemins") from None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("Chemins")
    return value


def _clean(text: str, n: int) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")[:n]


def executable(raw) -> str:
    """The executable's path as the kernel wrote it (quoted, or hex when it holds a space): decoded, its
    home folder's owner hidden, its control characters dropped, EXE_MAX at most; unreadable: `?`."""
    text = auditd._untrusted(raw) if isinstance(raw, str) and raw else None
    if text is None:
        return "?"
    return _clean(_HOME.sub("/home/<u>", text), EXE_MAX) or "?"


def motif(raw) -> str | None:
    """A PATH record's name as a pattern: its folder and its extension, never the file's name; None when
    the name is unreadable (`(null)`, neither quoted nor hex)."""
    name = auditd._untrusted(raw) if isinstance(raw, str) and raw else None
    if not name:
        return None
    name = _clean(name, 4096)
    folder, _, base = name.rpartition("/")
    ext = _EXT.search(base)
    pattern = "*" + ("." + ext.group(1) if ext else "")
    if name.startswith("/"):
        folder = _HOME.sub("/home/<u>", folder)
        return (folder + "/" + pattern)[-PATH_MAX:]
    return ("./" + (folder + "/" if folder else "") + pattern)[:PATH_MAX]


def _uid(value) -> int | None:
    """A uid as the query extracted it (ASCII digits); the unset auid ((uid_t)-1), or none: None."""
    text = str(value) if value is not None else ""
    if not re.fullmatch(r"[0-9]{1,10}", text):
        return None
    n = int(text)
    return None if n == auditd.UNSET else n


def _count(value) -> int:
    """A count the query returned: a non-negative integer, else raises ValueError (an answer unreadable)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or value < 0:
        raise ValueError("count")
    if value != int(value):
        raise ValueError("count")
    return int(value)


def _true(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    raise ValueError("bool")


def _pourquoi(exc: Exception) -> str:
    """Why the query failed, by what the adapter raised: its status, its text, its kind — never its text
    itself (it may name the workspace), only its class."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    text = str(exc)
    name = type(exc).__name__
    if status in (401, 403) or re.search(r"AuthorizationFailed|InsufficientAccess|Forbidden", text):
        return catalog.WRT_DROIT
    if re.search(r"Failed to resolve table|SEM0100", text, re.IGNORECASE):
        return catalog.WRT_TABLE
    if status == 404 or re.search(r"WorkspaceNotFound|ResourceNotFound", text):
        return catalog.WRT_ABSENT
    if status in (408, 504) or "Timeout" in name:
        return catalog.WRT_DELAI
    return catalog.WRT_ECHEC


def _row(row: dict) -> dict:
    """One writer as the capture keeps it. Raises ValueError on a row the query could not have written."""
    patterns = sorted({p for p in (motif(c) for c in chemins(row.get("Chemins"))) if p})[:PATHS]
    writer, events, doubles = row.get("Writer"), _count(row.get("Evenements")), _count(row.get("Doubles"))
    out = {"Executable": executable(writer) if writer else _unattributed(events, doubles),
           "Uid": _uid(row.get("WriterUid")), "Auid": _uid(row.get("WriterAuid")),
           "Processus": _count(row.get("Processus")), "Fichiers": _count(row.get("Fichiers")),
           "Evenements": events, "Chemins": patterns}
    for k in ("Premier", "Dernier"):
        at = catalog._when(row.get(k))
        out[k] = at.isoformat() if at else ""
    if doubles > 0:
        out["Doubles"] = doubles
    return out


def _unattributed(events: int, doubles: int) -> str:
    """What an empty writer is: events of several SYSCALL records (`Doubles`), a SYSCALL without `exe=`, or both."""
    if doubles and doubles >= events:
        return UNATTRIBUTED
    return NO_EXE if not doubles else UNATTRIBUTED + " " + NO_EXE


UNATTRIBUTED = "(several SYSCALL records: not attributed)"
NO_EXE = "(a SYSCALL record without exe=: not attributed)"


def process_write_audit(vm, at: datetime, *, kql_run, now: datetime | None = None, system: str = "",
                        top: int = catalog.WRT_TOP, budget=None) -> catalog.Reading:
    """Who modified files in the watched folders of `vm` over the window anchored at `at`, as a
    `catalog.Reading`: its state always said. `kql_run(query, timespan)` runs one query (its rows; it raises
    when the query fails); None: no workspace, nothing read."""
    read = catalog.A_MESURER[READ_ID]
    now = now or datetime.now(timezone.utc)
    try:
        vm = kql.resource_id(vm)
    except kql.UnsafeValue as exc:
        return catalog.Reading(read.id, catalog.REFUSEE, why=catalog.WRT_REFUSEE.format(exc))
    if system and (why := catalog.says(read, system)):
        return catalog.Reading(read.id, catalog.SANS_OBJET, why=why)
    if kql_run is None:
        return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.WRT_SANS_ESPACE)
    debut, fin, horizon = bornes(at, now)
    if not (budget or read_budget.LOG_ANALYTICS).take(1, WHO):
        return catalog.Reading(read.id, catalog.REFUSEE, why=catalog.WRT_BUDGET)
    try:
        rows = kql_run(texte(vm, debut, fin, horizon),
                       (debut - catalog.WRT_AVANT - timedelta(minutes=1), horizon + timedelta(minutes=1)))
    except Exception as exc:  # what the adapter raised: a failure said, never an empty answer
        return catalog.Reading(read.id, catalog.ECHEC, why=f"{_pourquoi(exc)} ({type(exc).__name__})")
    if not isinstance(rows, list):
        return catalog.Reading(read.id, catalog.ECHEC, why=catalog.WRT_ILLISIBLE)
    writers, first, beat = [], None, None
    try:
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("row")
            if _true(row.get("Battement")):
                start, last = catalog._when(row.get("Premier")), catalog._when(row.get("Dernier"))
                if start is None or last is None:
                    raise ValueError("Premier, Dernier")
                first = start if first is None else min(first, start)
                beat = last if beat is None else max(beat, last)
            else:
                writers.append(_row(row))
    except (ValueError, TypeError):
        return catalog.Reading(read.id, catalog.ECHEC, why=catalog.WRT_ILLISIBLE)
    writers.sort(key=lambda r: (-r["Fichiers"], -r["Evenements"], r["Executable"]))
    if writers:
        why = catalog.WRT_TRONQUEE.format(catalog.WRT_ROWS) if len(rows) >= catalog.WRT_ROWS else ""
        return catalog.Reading(read.id, catalog.LIGNES, rows=writers[:max(1, min(int(top), 10))], why=why)
    # The beat on both sides of the window: before its start, and at or past its end (W8).
    if beat is not None and beat >= fin and first <= debut:
        return catalog.Reading(read.id, catalog.VIDE)
    if now < fin + timedelta(seconds=catalog.WRT_BEAT_S + read.latency_s):
        return catalog.Reading(read.id, catalog.EN_ATTENTE,
                               why=catalog.WRT_LATENCE.format(catalog.WRT_BEAT_S, read.latency_s))
    if beat is not None:
        return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.WRT_TUE if beat < fin else catalog.WRT_DEBUT)
    return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.WRT_SANS_MONTRE)
