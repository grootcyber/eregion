"""bench_history — what a bench VM went through, read and judged before a run (BNC3b, #770).

docs/design/banc-autonome.md, §3 (its row 3) and §3.1. Three verdicts, each read under the
operator's `az login`, each refusing on a doubt — a read that fails, a read cut at its bound, a
history that does not reach back far enough, is never a ✓:

  the calm        the VM started 10 min ago at least — a start, a restart, a write on it (its creation),
                  the end of its last restore —, and no Run Command on it for 10 min, read in its own
                  activity log — a ✗ that says the minutes left, never a wait (Q6); no start read and its
                  creation unread: unreadable;
  restore first   no Run Command on the VM since its last restore that may be destructive (Q3b): every
                  `runCommand/action` on it, whatever its caller, counts — the caller says who acted,
                  never what is filtered. Two are left out of the count: a session drain of Imladris
                  within [−2 min, +7 min] of the start of a verified isolation of the watch (one drain,
                  one Run Command), and a run of the current Orodruin whose technique reads as
                  non-destructive, from Orodruin's own journal in the channel (`audit/<run_id>.jsonl`)
                  then its run's report (`runs/<run_id>.json`) against the catalogue — one journal
                  line, one Run Command, the nearest after it: a Run Command without its own line is
                  destructive. « Since its last restore » is read in the vault's jobs: the newest restore
                  of the VM completed AND proven in place, on the same VM, as REC1 proves it (measured
                  on the bench, 09/11 and 12/11): its container names this VM's group and name, its
                  job's property bag says « Job Type » « Replace disks » (glorfindel.recovery_watch.
                  IN_PLACE_TYPES), and the VM's current OS disk was created during the job
                  (DISK_AFTER_END_S) —; a « Restore disks » or a « Create new virtual machine » leaves
                  the VM as it was, and is no restore here. Else the VM's creation, within the horizon;
  the clean point the newest recovery point of the VM, the one the restore takes, taken after its last
                  restore and outside every quarantine — over every run, read on Imladris by
                  scripts/bench_h0_reader.py (`history`), in its disposable, network-less container.

The horizon: the activity log keeps 90 days; it is read over HORIZON_DAYS (89: a window Azure
accepts whatever the clocks), as the vault's jobs. A last restore older than that, and a VM older
than that never restored, are « unreadable » — a ✗, until a restore.

What it does not see (said in docs/banc-t1486.md): « every Run Command » is every
`runCommand/action` on the VM — not a managed Run Command (`runCommands/write`, a child resource
`--resource-id` does not bring back), not a Custom Script extension, not an SSH session. And the
activity log's ingestion delay (a few minutes, a hypothesis to measure) may hide a start or a Run
Command younger than it from the calm; a restart by the platform (the host's maintenance, a health
event) goes through none of START_OPS. Under the action queue (FS1), the watch's isolations and lifts
for a request write no cycle: the drain the isolation starts is then a Run Command of Imladris no
verified cycle answers (destructive), and a lift missed leaves the quarantine open (the point refused).

Nothing is written: each read is `az … list|show`, an ssh to Imladris reading in its reader's
container, `az storage blob list|download` on the channel. No identifier is printed: a caller is a
role (bench_shared.Roles), each line goes through bench_shared.scrub.
"""
from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import bench_shared as bs

HORIZON_DAYS = 89
HORIZON_S = HORIZON_DAYS * 86400.0
CALM_S = 600.0
MAX_EVENTS = 5000
START_OPS = ("microsoft.compute/virtualmachines/start/action",
             "microsoft.compute/virtualmachines/restart/action",
             "microsoft.compute/virtualmachines/redeploy/action",
             "microsoft.compute/virtualmachines/performmaintenance/action",
             # its creation, or any write on it: counted as a start, to be prudent (BNC3b review)
             "microsoft.compute/virtualmachines/write")
# A Run Command without its end, younger than this, is still running (Azure's own bound: 90 min).
RUN_COMMAND_MAX_S = 90 * 60.0
# The drain's window around the start of an isolation: SID1's, as a model (§3.1).
from glorfindel.providers.azure.own_run_command import DRAIN_AFTER_S, DRAIN_BEFORE_S  # noqa: E402

# The lifts that hold: a release done, or nothing left to release, a reset clean.
LIFTED = ("released", "nothing_to_release", "clean")
# An isolation by the console or the bot: its line is written after its action — its start taken
# this much before, to be prudent.
MANUAL_BEFORE_S = 600.0
# Orodruin's journal in the channel: a line written before each call (O1), a Run Command started
# at most this long after it (the VM started first, the Conflict retries), at most this before.
JOURNAL_BEFORE_S = 900.0
JOURNAL_AFTER_S = 60.0
MAX_BLOBS = 5000
MAX_JOURNALS = 20
MAX_BLOB_BYTES = 1024 * 1024
CHANNEL_URL = re.compile(r"https://([a-z0-9]{3,24})\.blob\.core\.windows\.net/([a-z0-9][a-z0-9-]{2,62})/?")
_RUN_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}")
_JOB_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}")
# The calls of an injector that are a Run Command on the VM (annatar/executors/azure_vm.py).
INJECTOR_CALLS = ("run_command", "run_script")


class Unreadable(RuntimeError):
    """A read that does not say enough to conclude: a ✗, never a ✓."""


def _name(rid) -> str:
    return str(rid or "").rstrip("/").rsplit("/", 1)[-1].lower()


@dataclass
class Anchor:
    """Where « since its last restore » starts: the restore's start (the runs counted from it) and its
    end (the points taken after it), or the VM's creation."""
    start: float
    end: float
    kind: str          # "restore" or "creation"
    notes: str = ""    # the restores not counted, and why (a creation after them)


def vm_jobs(jobs: list[dict], vm: str, rg: str = "") -> list[dict]:
    """The vault's jobs of the VM, oldest first, each with its name and its container. A job whose
    container names another group or another VM is another VM's (two VMs of one name share a vault:
    REC1's `_last_restore_job`); its `container` empty when it names none."""
    want = f";{rg.lower()};{vm.lower()}" if rg else ""
    out = []
    for j in jobs or []:
        p = j.get("properties") or {}
        if str(p.get("entityFriendlyName") or "").lower() != vm:
            continue
        container = str(p.get("containerName") or "").lower()
        if container and want and not container.endswith(want):
            continue
        start = bs.epoch(p.get("startTime"))
        if start is None:
            continue
        out.append({"name": str(j.get("name") or ""), "operation": str(p.get("operation") or ""),
                    "status": str(p.get("status") or ""), "start": start, "end": bs.epoch(p.get("endTime")),
                    "container": container})
    return sorted(out, key=lambda j: j["start"])


# A restore in place, as REC1 proves it (glorfindel/recovery_watch.py; measured on the bench 09/11,
# REC1b, and held by the lift of 12/11): the property bag's « Job Type » « Replace disks » — one
# source for the values —, and the VM's current OS disk created during the job.
from glorfindel.recovery_watch import DISK_AFTER_END_S, IN_PLACE_TYPES  # noqa: E402

MAX_RESTORES_READ = 5


def job_type(detail) -> str:
    """The « Job Type » of `az backup job show`'s property bag, its keys and its value folded as REC1
    folds them (spaces, case: Azure's keys carry a trailing space or not, by version); '' when none."""
    ext = ((detail or {}).get("properties") or {}).get("extendedInfo") or {}
    bag = ext.get("propertyBag") if isinstance(ext, dict) else None
    if not isinstance(bag, dict):
        return ""
    folded = {" ".join(str(k).split()).lower(): str(v) for k, v in bag.items()}
    return " ".join(folded.get("job type", "").split())


def said_in_place(detail) -> bool:
    return job_type(detail).lower() in IN_PLACE_TYPES


def disk_created_during(created: float | None, job: dict) -> bool:
    """The VM's current OS disk created during the restore job, DISK_AFTER_END_S after its end at most."""
    end = job["end"] if job["end"] is not None else job["start"]
    return created is not None and job["start"] < created <= end + DISK_AFTER_END_S


def anchor(jobs: list[dict], vm: str, created: float | None, now: float, in_place=None, rg: str = "") -> Anchor:
    """The VM's last restore completed and proven in place (`in_place(job)`: True, or why it is not, a
    str), read in the vault's jobs; or its creation, within the horizon. Raises Unreadable when a restore
    runs, or when nothing reaches back far enough — a restore not proven in place among them."""
    mine = vm_jobs(jobs, vm, rg)
    restores = [j for j in mine if j["operation"].lower() == "restore"]
    if any(j["status"].lower() in ("inprogress", "cancelling") for j in restores):
        raise Unreadable("un restore de la VM est en cours dans le coffre")
    done = sorted((j for j in restores if j["status"].lower() == "completed" and j["end"] is not None),
                  key=lambda j: j["end"], reverse=True)
    refused: list[str] = []
    for j in done[:MAX_RESTORES_READ]:
        verdict = in_place(j) if in_place is not None else "son détail n'est pas lu"
        if verdict is True:
            return Anchor(j["start"], j["end"], "restore")
        day = datetime.fromtimestamp(j["end"], timezone.utc).strftime("%d/%m")
        refused.append(f"{bs.hms(j['end'])} le {day} : {verdict}")
    said = " ; ".join(refused[:3])
    if created is not None and now - created <= HORIZON_S:
        return Anchor(created, created, "creation", notes=f"restore(s) non prouvé(s) en place : {said}" if said else "")
    if refused:
        raise Unreadable(f"restore non prouvé en place ({said}){NOT_PROVEN_HINT}")
    raise Unreadable(f"aucun restore de la VM lu dans les jobs du coffre sur {HORIZON_DAYS} jours, et la VM est "
                     "plus ancienne (ou sa création ne se lit pas) : la liste ne remonte pas jusqu'à son dernier "
                     "restore")


# What to do when the last restore is not proven in place — not « restore again » after a
# `make bench-restore` that has just succeeded: read the job's bag, and say it (BNC3b review).
NOT_PROVEN_HINT = (" — si make bench-restore vient de réussir, lire le sac du job (az backup job show -g <groupe du "
                   "coffre> -v <coffre> -n <le job, az backup job list> --query properties.extendedInfo.propertyBag ; "
                   "attendu : « Job Type » « Replace disks ») et le disque OS de la VM (créé pendant le job), puis le "
                   "signaler ; un « Restore disks » ou une nouvelle VM faits à la main : restaurer en place")


def target_ops(events: list[dict], roles: bs.Roles, vm: str) -> list[dict]:
    import bench_report
    return [o for o in bench_report.operations(events, roles) if o["resource"] == vm]


# ── the calm ──────────────────────────────────────────────────────────────────

def _last_moment(op: dict, now: float) -> float:
    """When an operation was last at work: its end; without one, now while it may still run."""
    if op["end"] is not None:
        return op["end"]
    return now if now - op["start"] < RUN_COMMAND_MAX_S else op["start"]


def calm(ops: list[dict], power: str, created: float | None, now: float, vm: str,
         restored: float | None = None) -> tuple[str, str]:
    """(mark, text): the VM running for CALM_S — since its last start, restart, write, or the end of its
    last restore (`restored`) —, and no Run Command on it for CALM_S (Q6). No start read and its creation
    unread: unreadable, a ✗."""
    if power != "running":
        return bs.FAIL, (f"le calme : {vm} est {power or 'dans un état illisible'} — make celebrimbor-start VM=…, "
                         "puis 10 min, puis relancer")
    starts = [o for o in ops if o["op"] in START_OPS and o["status"].lower() != "failed"]
    moments = [_last_moment(o, now) for o in starts] + ([restored] if restored is not None else [])
    started = max(moments, default=None)
    if started is None:
        if created is None:
            return bs.FAIL, (f"le calme : illisible — ni démarrage de {vm} lu en {HORIZON_DAYS} jours, ni sa "
                             "création (az vm show, timeCreated) : jamais un ✓ sur une lecture qui manque")
        if now - created <= HORIZON_S:
            started = created
    rcs = [o for o in ops if o["op"] == bs.RUN_COMMAND_OP]
    last_rc = max((_last_moment(o, now) for o in rcs), default=None)
    waits = []
    if started is not None and now - started < CALM_S:
        waits.append((CALM_S - (now - started), f"démarrée il y a {bs.duration(now - started)}"))
    if last_rc is not None and now - last_rc < CALM_S:
        waits.append((CALM_S - (now - last_rc), f"sa dernière Run Command il y a {bs.duration(now - last_rc)}"))
    if waits:
        left = max(w for w, _ in waits)
        minutes = max(1, int(-(-left // 60)))
        return bs.FAIL, (f"le calme : {vm} {' ; '.join(s for _, s in waits)} — il reste {minutes} min : relancer "
                         "make bench-run alors (un ✗, jamais une attente)")
    since = (f"démarrée il y a {bs.duration(now - started)}" if started is not None
             else f"démarrée avant les {HORIZON_DAYS} jours lus")
    rc = (f"sa dernière Run Command il y a {bs.duration(now - last_rc)}" if last_rc is not None
          else "aucune Run Command lue")
    return bs.OK, f"le calme : {vm} {since}, {rc} (10 min au moins)"


# ── the quarantines and the drains, as Imladris recorded them ────────────────

def isolation_times(x: dict) -> tuple[float, float]:
    """(its start, its line's own time) of an isolation: the start is `verified_at` − `action_s` for the
    watch's (§3.1), the console's or the bot's line less MANUAL_BEFORE_S; a lift counts only after the
    line's own time — never after the start taken earlier to be prudent (BNC3b review). Raises
    Unreadable when it can't be told."""
    if x.get("source") == "watch":
        at = bs.epoch(x.get("verified_at")) or bs.epoch(x.get("timestamp"))
        spent = x.get("action_s")
        if at is None or not isinstance(spent, (int, float)) or isinstance(spent, bool):
            raise Unreadable("une isolation de la watch sans `verified_at` ou sans `action_s` : son début ne se lit pas")
        return at - float(spent), at
    at = bs.epoch(x.get("timestamp"))
    if at is None:
        raise Unreadable("une isolation de la console ou du bot sans heure")
    return at - MANUAL_BEFORE_S, at


def isolation_start(x: dict) -> float:
    return isolation_times(x)[0]


def _checked(history: dict) -> dict:
    if not isinstance(history, dict):
        raise Unreadable("l'historique d'Imladris ne se lit pas")
    if history.get("unreadable"):
        raise Unreadable("des fichiers de la watch d'Imladris ne se lisent pas ("
                         + ", ".join(str(u) for u in history["unreadable"][:3]) + ")")
    files = history.get("files")
    if not isinstance(files, int) or isinstance(files, bool) or files < 1:
        raise Unreadable("aucun fichier de cycles de la watch sur Imladris : une quarantaine non lue n'est pas "
                         "une quarantaine absente")
    return history


def drain_starts(history: dict) -> list[float]:
    """The starts of the watch's verified isolations of the VM — what a drain of Imladris answers."""
    out = []
    for x in _checked(history).get("isolations") or []:
        if x.get("source") == "watch" and x.get("verified") is True:
            out.append(isolation_start(x))
    return sorted(out)


def quarantines(history: dict, now: float) -> list[tuple[float, float | None]]:
    """Every quarantine of the VM over every run: [its start, its lift) — None while no lift is read
    (an open quarantine: every point after its start is in it). An isolation executed, verified, or
    partial counts; its lift is the first one that holds after it."""
    h = _checked(history)
    starts = sorted(isolation_times(x) for x in h.get("isolations") or []
                    if x.get("executed") or x.get("verified") or x.get("partial"))
    lifts = []
    for x in h.get("lifts") or []:
        held = x.get("verified") is True if x.get("source") == "watch" else str(x.get("status") or "") in LIFTED
        at = bs.epoch(x.get("verified_at")) or bs.epoch(x.get("timestamp"))
        if held and at is not None:
            lifts.append(at)
    lifts.sort()
    out: list[tuple[float, float | None]] = []
    for s, line_at in starts:
        end = next((t for t in lifts if t > line_at), None)
        out.append((s, end))
    now_iso = (h.get("isolation") or {}) if isinstance(h.get("isolation"), dict) else {}
    if now_iso:
        at = bs.epoch(now_iso.get("isolated_at"))
        if at is None:
            raise Unreadable("l'isolation en cours de la VM sur Imladris n'a pas d'heure")
        out.append((at, None))
    return out


# ── the runs of the VM since its last restore ────────────────────────────────

def restore_first(ops: list[dict], since: Anchor, drains, technique) -> tuple[str, str]:
    """(mark, text) of « restore d'abord » (Q3b). `drains()`: the starts of the watch's verified
    isolations (read only when Imladris ran a Run Command); `technique(rcs)`: of the current Orodruin's
    Run Commands, the set (by `id`) of those that read as non-destructive — each with its own line in
    Orodruin's journal."""
    rcs = sorted((o for o in ops if o["op"] == bs.RUN_COMMAND_OP and o["start"] >= since.start),
                 key=lambda o: o["start"])
    oro = [rc for rc in rcs if rc["role"] == "orodruin"]
    held = technique(oro) if oro else set()
    destructive: list[dict] = []
    drained = harmless = 0
    starts: list[float] | None = None
    taken: set[int] = set()
    for rc in rcs:
        if rc["role"] == "h0":
            if starts is None:
                starts = drains()
            match = next((i for i, s in enumerate(starts) if i not in taken
                          and s - DRAIN_BEFORE_S <= rc["start"] <= s + DRAIN_AFTER_S), None)
            if match is not None:
                taken.add(match)
                drained += 1
                continue
        elif rc["role"] == "orodruin" and id(rc) in held:
            harmless += 1
            continue
        destructive.append(rc)
    when = ("son dernier restore" if since.kind == "restore" else "sa création")
    at = bs.hms(since.end) + " le " + datetime.fromtimestamp(since.end, timezone.utc).strftime("%d/%m")
    if destructive:
        who = ", ".join(dict.fromkeys(bs.ROLE_NAMES.get(r["role"], r["role"]) for r in destructive))
        last = destructive[-1]["start"]
        notes = f" ({since.notes}{NOT_PROVEN_HINT})" if since.notes else ""
        return bs.FAIL, (f"restore d'abord : {len(destructive)} Run Command sur la VM depuis {when} ({at}) — {who}, "
                         f"la dernière à {bs.hms(last)} — : elle peut porter un run destructif ; make bench-restore "
                         f"TARGET=… RUN=… (ou BEFORE=…), puis relancer{notes}")
    out = []
    if drained:
        out.append(f"{drained} coupure(s) des sessions d'Imladris")
    if harmless:
        out.append(f"{harmless} Run Command d'un run non destructif d'Orodruin")
    tail = f" ; hors du compte : {', '.join(out)}" if out else ""
    return bs.OK, f"restore d'abord : aucune Run Command destructive depuis {when} ({at}){tail}"


def point_clean(point: float | None, since: Anchor, quarantine: list[tuple[float, float | None]]) -> tuple[bool, str]:
    """(clean, why) for the newest point: after the last restore, outside every quarantine."""
    if point is None:
        return False, "aucun point lu pour la cible"
    if point <= since.end:
        what = "son dernier restore" if since.kind == "restore" else "sa création"
        return False, f"le plus récent ({bs.hms(point)}) est d'avant {what}"
    for s, e in quarantine:
        if point >= s and (e is None or point < e):
            lifted = f", levée à {bs.hms(e)}" if e is not None else ", sans levée lue"
            return False, f"le plus récent ({bs.hms(point)}) est pris dans une quarantaine (depuis {bs.hms(s)}{lifted})"
    return True, f"le plus récent ({bs.hms(point)}), pris après le dernier restore et hors de toute quarantaine"


# ── the reads ─────────────────────────────────────────────────────────────────

def _days(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%d-%m-%Y")


class Reads:
    """The VM's history, each source read once, under the operator's `az login` — and Imladris by
    ssh, the channel by `az storage`. Each read failing raises Unreadable, kept and raised again."""

    def __init__(self, target: str, vm_id: str, rg: str, vault: str, vault_rg: str, env: dict, now: float,
                 roles: bs.Roles | None = None, catalog=None):
        self.target, self.vm_id, self.rg, self.env, self.now = target, vm_id, rg, env, now
        self.vault, self.vault_rg = vault, vault_rg or rg
        self._roles, self._catalog = roles, catalog
        self._cache: dict = {}

    def _once(self, key: str, read):
        if key not in self._cache:
            try:
                self._cache[key] = (True, read())
            except Unreadable as e:
                self._cache[key] = (False, str(e))
            except RuntimeError as e:
                self._cache[key] = (False, bs.scrub(str(e))[:200])
        ok, value = self._cache[key]
        if not ok:
            raise Unreadable(value)
        return value

    def roles(self) -> bs.Roles:
        if self._roles is None:
            self._roles = bs.Roles.from_environment(self.env)
        return self._roles

    def events(self) -> list[dict]:
        def read():
            start = datetime.fromtimestamp(self.now - HORIZON_S, timezone.utc)
            end = datetime.fromtimestamp(self.now, timezone.utc)
            got = bs.az_json(["monitor", "activity-log", "list", "--resource-id", self.vm_id,
                              "--start-time", start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "--end-time", end.strftime("%Y-%m-%dT%H:%M:%SZ"), "--max-events", str(MAX_EVENTS)],
                             timeout=300)
            if not isinstance(got, list):
                raise Unreadable("le journal d'activité de la VM : une réponse qui n'est pas une liste")
            if len(got) >= MAX_EVENTS:
                raise Unreadable(f"le journal d'activité de la VM : {MAX_EVENTS} événements lus, la borne — la "
                                 "lecture est coupée")
            return got
        return self._once("events", lambda: _said("le journal d'activité de la VM", read))

    def ops(self) -> list[dict]:
        return target_ops(self.events(), self.roles(), self.target)

    def jobs(self) -> list[dict]:
        def read():
            if not self.vault:
                raise Unreadable("aucun coffre dans la configuration du poste")
            got = bs.az_json(["backup", "job", "list", "-g", self.vault_rg, "-v", self.vault,
                              "--start-date", _days(self.now - HORIZON_S),
                              "--end-date", _days(self.now + 86400)], timeout=300)
            if not isinstance(got, list):
                raise Unreadable("les jobs du coffre : une réponse qui n'est pas une liste")
            return got
        return self._once("jobs", lambda: _said("les jobs du coffre", read))

    def created(self) -> float | None:
        def read():
            return bs.epoch(bs.az_json(["vm", "show", "--ids", self.vm_id, "--query", "timeCreated"]))
        try:
            return self._once("created", read)
        except Unreadable:
            return None                  # a creation unread: no anchor from it, never a ✓

    def in_place(self, job: dict):
        """True when the restore job is proven in place on this VM, as REC1 proves it — its container
        names this VM, its « Job Type » is « Replace disks », the VM's current OS disk was created during
        it —, else why not (a str)."""
        if not _JOB_NAME.fullmatch(job.get("name") or ""):
            return "son nom ne se lit pas"
        if not job.get("container"):
            return "il ne nomme pas son conteneur : rien ne dit que c'est cette VM qui a été restaurée"
        try:
            detail = bs.az_json(["backup", "job", "show", "-g", self.vault_rg, "-v", self.vault, "-n", job["name"]])
        except RuntimeError as e:
            return f"son détail ne se lit pas ({bs.scrub(str(e))[:120]})"
        if not said_in_place(detail):
            return f"son type est « {job_type(detail) or 'non dit'} », pas « Replace disks »"
        try:
            created = self.os_disk_created()
        except Unreadable as e:
            return f"le disque OS de la VM ne se lit pas ({e})"
        if not disk_created_during(created, job):
            return "le disque OS de la VM n'a pas été créé pendant le job"
        return True

    def os_disk_created(self) -> float | None:
        """When the VM's current OS disk was created (two reads under Reader, REC1's)."""
        def read():
            disk = bs.az_json(["vm", "show", "--ids", self.vm_id, "--query", "storageProfile.osDisk.managedDisk.id"])
            if not isinstance(disk, str) or not disk.lower().startswith("/subscriptions/"):
                raise Unreadable("la VM ne nomme pas de disque OS managé")
            created = bs.epoch(bs.az_json(["disk", "show", "--ids", disk, "--query", "timeCreated"]))
            if created is None:
                raise Unreadable("la date de création du disque OS ne se lit pas")
            return created
        return self._once("os_disk", read)

    def anchor(self) -> Anchor:
        return self._once("anchor", lambda: anchor(self.jobs(), self.target, self.created(), self.now,
                                                   self.in_place, self.rg))

    def restored(self) -> float | None:
        """The end of the VM's last restore completed, whatever it was — a start for the calm. None
        when the jobs do not read (« restore d'abord » says it, a ✗)."""
        try:
            jobs = self.jobs()
        except Unreadable:
            return None
        ends = [j["end"] for j in vm_jobs(jobs, self.target, self.rg)
                if j["operation"].lower() == "restore" and j["status"].lower() == "completed" and j["end"] is not None]
        return max(ends, default=None)

    def history(self) -> dict:
        return self._once("history", lambda: _said("l'historique d'Imladris",
                                                   lambda: bs.read_h0("history", self.target, env=self.env)))

    def drains(self) -> list[float]:
        return self._once("drains", lambda: drain_starts(self.history()))

    def quarantines(self) -> list[tuple[float, float | None]]:
        return self._once("quarantines", lambda: quarantines(self.history(), self.now))

    def catalog(self) -> dict:
        if self._catalog is None:
            from eregion_core.exercise_plan import load_catalog
            self._catalog = load_catalog()
        return self._catalog

    def channel(self) -> "Channel":
        return self._once("channel", lambda: Channel.from_terraform())

    def harmless(self, rcs: list[dict]) -> set[int]:
        """Of the current Orodruin's Run Commands, those (by `id`) whose own journal line names a run that
        reads as non-destructive — the others, a technique unread, are destructive."""
        try:
            channel = self.channel()
            paired = channel.pair(rcs, self.vm_id)
            catalog = self.catalog()
            return {key for key, rid in paired.items() if channel.non_destructive_run(rid, catalog)}
        except Unreadable:
            return set()


def _said(what: str, read):
    try:
        return read()
    except Unreadable:
        raise
    except RuntimeError as e:
        raise Unreadable(f"{what} : illisible ({bs.scrub(str(e))[:200]})") from e


# ── Orodruin's journal in the channel ────────────────────────────────────────

class Channel:
    """The exercise channel, read under the operator's `az login` (`channel_operator`: Storage Blob
    Data Contributor on its container, the operator's address through its firewall): Orodruin's
    journal, `audit/<run_id>.jsonl`, and a run's report, `runs/<run_id>.json`. Read only, bounded."""

    def __init__(self, account: str, container: str):
        self.account, self.container = account, container
        self._listing: list[dict] | None = None
        self._blobs: dict[str, str] = {}
        self.downloads = 0

    @classmethod
    def from_terraform(cls) -> "Channel":
        url = bs.tf_output("orodruin", "channel_url")
        m = CHANNEL_URL.fullmatch(url or "")
        if not m:
            raise Unreadable("le canal d'Orodruin ne se lit pas (terraform output channel_url d'infra/orodruin)")
        return cls(m.group(1), m.group(2))

    def _base(self) -> list[str]:
        return ["--auth-mode", "login", "--account-name", self.account, "--container-name", self.container]

    def listing(self) -> list[dict]:
        if self._listing is None:
            got = bs.az_json(["storage", "blob", "list", *self._base(), "--prefix", "audit/",
                              "--num-results", str(MAX_BLOBS), "--query",
                              "[].{name:name, created:properties.creationTime, modified:properties.lastModified}"],
                             timeout=120)
            if not isinstance(got, list):
                raise Unreadable("le journal d'Orodruin : une liste illisible")
            if len(got) >= MAX_BLOBS:
                raise Unreadable(f"le journal d'Orodruin : {MAX_BLOBS} blobs listés, la borne")
            self._listing = got
        return self._listing

    def text(self, name: str) -> str:
        if name in self._blobs:
            return self._blobs[name]
        if self.downloads >= MAX_JOURNALS:
            raise Unreadable(f"le journal d'Orodruin : plus de {MAX_JOURNALS} blobs à lire")
        self.downloads += 1
        with tempfile.TemporaryDirectory(prefix="bench-channel-") as tmp:
            path = Path(tmp) / "blob"
            res = bs.run(["az", "storage", "blob", "download", *self._base(), "--name", name, "--file", str(path),
                          "--no-progress", "-o", "none"], timeout=120)
            if not res.ok or not path.is_file():
                raise Unreadable(f"le blob du canal ne se lit pas ({res.first_error()})")
            if path.stat().st_size > MAX_BLOB_BYTES:
                raise Unreadable("un blob du canal dépasse sa borne")
            text = path.read_text(encoding="utf-8", errors="replace")
        self._blobs[name] = text
        return text

    def lines(self, rcs: list[dict], vm_id: str) -> list[tuple[float, str]]:
        """Orodruin's calls on this VM (`run_command`, `run_script`, before the call) around the Run
        Commands `rcs`: (their time, their run), oldest first."""
        lo = min(rc["start"] for rc in rcs) - JOURNAL_BEFORE_S
        hi = max(rc["start"] for rc in rcs) + JOURNAL_AFTER_S
        out: list[tuple[float, str]] = []
        for blob in self.listing():
            name = str(blob.get("name") or "")
            created, modified = bs.epoch(blob.get("created")), bs.epoch(blob.get("modified"))
            if not name.startswith("audit/") or created is None or modified is None:
                continue
            if created > hi or modified < lo:
                continue
            for line in self.text(name).splitlines():
                try:
                    doc = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(doc, dict) or doc.get("outcome") != "about_to_call":
                    continue
                if doc.get("action") not in INJECTOR_CALLS:
                    continue
                if str(doc.get("target") or "").rstrip("/").lower() != vm_id.rstrip("/").lower():
                    continue
                at = bs.epoch(doc.get("ts"))
                rid = str(doc.get("run_id") or "")
                if at is not None and lo <= at <= hi and _RUN_PART.fullmatch(rid):
                    out.append((at, rid))
        return sorted(out)

    def pair(self, rcs: list[dict], vm_id: str) -> dict[int, str]:
        """One line, one Run Command (BNC3b review): each line of the journal answers at most one Run
        Command — the nearest one after it, within [−JOURNAL_AFTER_S, +JOURNAL_BEFORE_S] —; {id(rc):
        run_id} for the Run Commands that have a line of their own. The others have none: destructive."""
        if not rcs:
            return {}
        free = sorted(rcs, key=lambda r: r["start"])
        out: dict[int, str] = {}
        for at, rid in self.lines(rcs, vm_id):
            match = next((r for r in free if id(r) not in out and at - JOURNAL_AFTER_S <= r["start"] <= at + JOURNAL_BEFORE_S),
                         None)
            if match is not None:
                out[id(match)] = rid
        return out

    def non_destructive_run(self, rid: str, catalog: dict) -> bool:
        """The run's report says a technique of the catalogue marked `destructive: false`."""
        try:
            doc = json.loads(self.text(f"runs/{rid}.json"))
        except (ValueError, Unreadable):
            return False
        ids = [str(doc.get(k) or "") for k in ("mitre", "scenario")] if isinstance(doc, dict) else []
        entry = next((catalog[i] for i in ids if i in catalog), None)
        return entry is not None and entry.destructive is False

