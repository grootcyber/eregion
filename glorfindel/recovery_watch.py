"""The watch sees the recovery of a VM it isolated, on Azure, and says it (REC1, #668).

H0 never restores (SEC17): a restore runs from the operator's workstation, whose
`glorfindel restore --wait` writes its `recovery_complete` where it runs. The watch on H0
never reads that host's files (SEC3), so it never lifted an isolation on its own; and a
release made elsewhere was put back by its reassertion. Now, every
GLORFINDEL_RECOVERY_INTERVAL_S (60 s; 0: off), for each isolation of its state, the watch
reads on Azure (`observed_restore`, the adapter; never a file another host wrote, never the
model), and holds it to be at least as strict as the workstation, which proves the
neutralization by its own gesture and restores in place:

  - a restore job of this VM (its container), started after its isolation, finished, Completed;
  - a restore IN PLACE, by the control plane: the job's type « Replace disks », and the VM's OS
    disk created during the job — a restore elsewhere (« Restore disks », a new VM) leaves the
    isolated VM as it was;
  - the recovery point it restored before the start of the incident — the isolation, or the
    first detection when it came before (`restore_plan.incident_start`, the rule of `--before`);
  - the VM running;
  - the neutralization, by the control plane: in the activity log, the last succeeded Run
    Command on the VM before the job started was made by a principal that restores
    (GLORFINDEL_RESTORE_PRINCIPALS, their ids), after the isolation, and none by anyone else
    since; then, a condition more and never enough alone, the guest's word after the restore
    is the harmless one.

Then it builds its own `recovery_complete` — the same fields as `glorfindel restore --wait` —,
vouched for in this process, and hands it to the graph: the release follows as on the
workstation (autonomous in the modes that allow it, a card otherwise; the release precondition
of agent.py unchanged: without the control plane's fact the signal says `run_command_neutralized`
unknown, and the release is held). A job that failed, not in place, of no named container, a
point not before the incident or unreadable: one card that says why (`release_hold`, nothing to
approve), no release. A VM that does not run once the job is done: one card, and the watch keeps
reading — started, the release follows.

Once per job (RECOVERIES_FILE, written before the signal leaves): two passes never emit twice
nor write two cards. A job started here (`glorfindel restore` on this host, its claim held)
is left to it, and a job ended less than GRACE_S ago waits: the process that restored releases
itself first (`restore --wait`). A release running (`releasing_at`) is left alone.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

RECOVERIES_FILE = Path.home() / ".glorfindel" / "recoveries.json"
_LOCK = threading.Lock()
_LOCK_WAIT_S = 30
# A job still running: nothing to say yet (the statuses Azure Backup gives a job).
RUNNING = frozenset({"inprogress", "cancelling", "notstarted"})
# The kinds of card that end a job: nothing more is read of it.
_TERMINAL = frozenset({"failed", "point_after", "point_unknown", "not_in_place", "not_this_vm"})
# The job type of a restore in place (the property bag's « Job Type » — unmeasured: any other
# value, or none, is not in place).
IN_PLACE_TYPES = frozenset({"replace disks"})
# The OS disk of a restore in place is created during its job: at most this long after its end.
DISK_AFTER_END_S = 600


def _env_s(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def grace_s() -> float:
    """A job ended less than this ago waits (GLORFINDEL_RECOVERY_GRACE_S, 300 s)."""
    return _env_s("GLORFINDEL_RECOVERY_GRACE_S", 300.0)


def start_wait_s() -> float:
    """A VM that does not run this long after its job ended gets its card (600 s)."""
    return _env_s("GLORFINDEL_RECOVERY_START_WAIT_S", 600.0)


def replay_wait_s() -> float:
    """How long the watch waits for Run Command's word after the restore (900 s): past it, the
    neutralization is unknown, and the release precondition holds the release."""
    return _env_s("GLORFINDEL_RECOVERY_REPLAY_WAIT_S", 900.0)


def restore_principals() -> frozenset[str]:
    """The principals that restore, whose Run Command neutralizes (GLORFINDEL_RESTORE_PRINCIPALS:
    their object ids or appIds, comma-separated; on H0, the workstation's console principal, in
    host.env). None given: no neutralization is ever proven."""
    raw = os.environ.get("GLORFINDEL_RESTORE_PRINCIPALS", "")
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def _epoch(text) -> float | None:
    try:
        dt = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).timestamp()


def _key(resource_id: str, job: str) -> str:
    return f"{resource_id.rstrip('/').lower()}|{job}"


def _load() -> dict:
    try:
        data = json.loads(RECOVERIES_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _note(resource_id: str, job: str, now: float, isolated: set[str], **fields) -> None:
    """Write what was done of this job, at once (a temp file renamed over it). The records of a VM
    no longer isolated are dropped: isolated again, its old jobs are before the new isolation, never
    read. Raises OSError."""
    from glorfindel.response.state import _atomic_write_text
    with _LOCK:
        data = {k: v for k, v in _load().items() if isinstance(v, dict) and k.split("|", 1)[0] in isolated}
        rec = dict(data.get(_key(resource_id, job)) or {})
        rec.update(fields, at_epoch=now)
        data[_key(resource_id, job)] = rec
        _atomic_write_text(RECOVERIES_FILE, json.dumps(data, sort_keys=True))


def seen(resource_id: str, job: str) -> dict:
    """What was done of this job of this VM: {"emitted"?, "said"?}."""
    with _LOCK:
        rec = _load().get(_key(resource_id, job))
    return rec if isinstance(rec, dict) else {}


def _card_id(vm: str, resource_id: str) -> str:
    from glorfindel.actions import _rid_hash
    return f"recovery-{vm}-{_rid_hash(resource_id)}".lower()


def _mine(resource_id: str) -> list[dict]:
    """The pending cards this module wrote on this VM."""
    from glorfindel import escalations
    prefix = _card_id(resource_id.rstrip("/").rsplit("/", 1)[-1], resource_id)
    return [e for e in escalations.pending() if str(e.get("signal_id") or "").lower().startswith(prefix)]


def _card(resource_id: str, vm: str, job: str, kind: str, reason: str, steps: list[str]) -> None:
    """One card for this job: the one before on this VM replaced (closed in the same write)."""
    from glorfindel import escalations, restore_plan
    esc = restore_plan.card_of(resource_id) or {}
    replaced = {e["id"]: "Remplacée : la watch a relu la reprise sur Azure." for e in _mine(resource_id)}
    escalations.record(
        signal_id=f"{_card_id(vm, resource_id)}-{job}-{kind}"[:200], resource_id=resource_id,
        action="review_recovery", escalation_type="release_hold", reason=reason,
        suggested_steps=steps, replaces=replaced,
        source=str(esc.get("source") or ""), exercise_run=str(esc.get("exercise_run") or ""))


def neutralized_by_the_control_plane(obs: dict, job_start: float, trusted: frozenset[str]):
    """(True | False | None, why) — the neutralization as the activity log says it: the last
    succeeded Run Command on the VM before the job started made by a principal that restores, none
    by anyone else since. False when another's is the last, or came after; None when it can't be
    told (the log unreadable, no principal configured)."""
    if obs.get("run_commands_error"):
        return None, str(obs["run_commands_error"])
    if not trusted:
        return None, "GLORFINDEL_RESTORE_PRINCIPALS vide : qui a lancé la dernière Run Command ne se compare à rien"
    runs = [r for r in obs.get("run_commands") or [] if _epoch(r.get("at")) is not None]
    before = [r for r in runs if _epoch(r["at"]) < job_start]
    after = [r for r in runs if _epoch(r["at"]) >= job_start]

    def ours(r) -> bool:
        return bool(set(r.get("callers") or []) & trusted)
    if not before:
        return False, "aucune Run Command réussie sur la VM entre l'isolement et le restore : rien n'a été neutralisé"
    if not ours(before[-1]):
        who = ", ".join(before[-1].get("callers") or []) or "?"
        return False, f"la dernière Run Command avant le restore vient de {who[:80]}, pas d'un principal qui restaure"
    other = next((r for r in after if not ours(r)), None)
    if other is not None:
        return False, f"une Run Command de {', '.join(other.get('callers') or ['?'])[:80]} après le début du restore"
    return True, ""


def _signal(resource_id: str, provider: str, obs: dict, neutralized, now: float) -> dict:
    """The recovery_complete the watch emits: the same fields as `glorfindel restore --wait`
    (cli._build_recovery_signal), `recovery_point_time` written as the workstation writes it —
    vouched for in this process (SEC3)."""
    from glorfindel.actions import _rid_hash
    from glorfindel.signal_origin import vouch
    ts = datetime.fromtimestamp(now, tz=timezone.utc)
    run_id = f"{ts:%Y%m%dT%H%M%SZ}-{_rid_hash(resource_id)}"
    job = obs["job"]
    start, end = _epoch(job.get("start")), _epoch(job.get("end"))
    vectors = [str(v) for v in obs.get("replay_vectors") or []]
    if vectors:
        neutralized = False            # as on the workstation: another script a disk may replay
    point = str((obs.get("point") or {}).get("time") or "")
    try:
        point = str(datetime.fromisoformat(point))    # as restore_from_backup gives it: str(datetime)
    except ValueError:
        pass
    return vouch({
        "signal_id": f"{run_id}_recovery_complete",
        "timestamp": ts.isoformat(),
        "provider": provider,
        "resource_id": resource_id,
        "resource_type": "vm",
        "ttp": "",
        "severity": "low",
        "event": "recovery_complete",
        "raw_signal": {
            "recovery_point_time": point,
            "restore_time_s": int(end - start) if start is not None and end is not None else 0,
            "run_command_neutralized": neutralized,
            **({"replay_vectors": vectors} if vectors else {}),
        },
        "context": {"run_id": run_id},
    })


def _provider(connector) -> str:
    try:
        from glorfindel.providers.interface import capabilities_of
        return capabilities_of(connector).provider or "azure"
    except Exception:
        return "azure"


def recovery_pass(connector, emit, now: float | None = None) -> list[dict]:
    """One pass: each isolation of the state read on Azure; one record per job it said
    something of: {"vm", "job", "outcome": "emitted" | "card" | "wait" | "unreadable", "detail"}.
    `emit` takes the recovery_complete (the watch: its VM's queue). Raises nothing but an OSError
    of a record that could not be written (said by the watch; the next pass tries again)."""
    import time
    from glorfindel.actions import active_isolations
    from glorfindel.config import resolve_backup_vault

    now = time.time() if now is None else now
    report: list[dict] = []
    isolations = active_isolations()
    if not isolations:
        return report                          # a local read: no Azure call when nothing is isolated
    vault, vault_rg, _ = resolve_backup_vault(None)
    if not vault:
        return report
    isolated = {str(i.get("resource_id") or "").rstrip("/").lower() for i in isolations}
    for iso in isolations:
        try:
            _one(connector, emit, iso, vault, vault_rg, now, report, isolated)
        except NotImplementedError:
            return report                      # the provider can't say: nothing proven
        except OSError:
            raise
        except Exception as exc:               # unreadable here: no proof, no release
            report.append({"vm": iso.get("vm_name", "?"), "job": "", "outcome": "unreadable",
                           "detail": f"reprise illisible sur Azure : {exc}"})
    return report


def _one(connector, emit, iso: dict, vault: str, vault_rg: str, now: float, report: list[dict],
         isolated: set[str]) -> None:
    from glorfindel import restore_plan
    from glorfindel.jobs import restore_in_progress

    rid, vm = str(iso.get("resource_id") or ""), str(iso.get("vm_name") or "")
    isolated_at = _epoch(iso.get("isolated_at"))
    if not rid or isolated_at is None or iso.get("releasing_at"):
        return                                  # a release running: left to it
    if restore_in_progress(vm):
        return                                  # restored from here: its own process releases
    since = datetime.fromtimestamp(isolated_at, tz=timezone.utc).isoformat()
    obs = connector.observed_restore(rid, since, vault=vault, vault_rg=vault_rg)
    job = obs.get("job") if isinstance(obs, dict) else None
    if not job or not job.get("name"):
        return
    status = str(job.get("status") or "")
    if status.lower() in RUNNING or not job.get("end"):
        return
    name = job["name"]
    done = seen(rid, name)
    if done.get("emitted") or done.get("said") in _TERMINAL:
        return

    def card(kind: str, reason: str, steps: list[str]) -> None:
        if done.get("said") == kind:
            return
        _card(rid, vm, name, kind, reason, steps)
        _note(rid, name, now, isolated, said=kind)   # after the card: refused, the next pass says it
        report.append({"vm": vm, "job": name, "outcome": "card", "detail": reason})

    head = f"Restauration de {vm} lue sur Azure (job {name}"
    if status.lower() != "completed":
        return card("failed", f"{head}, {status}) : elle n'a pas abouti. L'isolation reste en place, "
                              "aucune levée.",
                    ["Lire le job dans le coffre (portail, `az backup job show`).",
                     f"Relancer le restore depuis le poste : glorfindel restore {rid} --before <ISO8601>",
                     "Ou garder l'isolation et acquitter cette carte."])
    point = obs.get("point") or {}
    if not point.get("time"):
        return card("point_unknown",
                    f"{head}, finie) : le point restauré ne se lit pas sur Azure ({point.get('why') or '?'}). "
                    "Glorfindel ne peut pas dire qu'il précède l'incident : aucune levée.",
                    ["Vérifier dans le coffre le point que le job a restauré.",
                     f"S'il précède l'incident et que la VM est saine : glorfindel release {rid} --yes",
                     "Sinon, restaurer un point antérieur depuis le poste."])
    if not job.get("container_named") and point.get("by") != "id":
        return card("not_this_vm",
                    f"{head}) : le job ne nomme pas son conteneur, et son point n'est pas désigné par son "
                    "identifiant — rien ne dit que c'est cette VM qui a été restaurée : aucune levée.",
                    ["Lire le job dans le coffre : quelle VM a-t-il restaurée ?",
                     f"Si c'est bien celle-ci, saine : glorfindel release {rid} --yes"])
    start = _epoch(job.get("start"))
    end = _epoch(job.get("end")) or now
    kind = " ".join(str(obs.get("job_type") or "").split()).lower()
    created = _epoch(obs.get("os_disk_created"))
    in_place = kind in IN_PLACE_TYPES and created is not None and start is not None \
        and start < created <= end + DISK_AFTER_END_S
    if not in_place:
        why = (f"son type est « {obs.get('job_type') or 'non dit'} », pas « Replace disks »" if kind not in IN_PLACE_TYPES
               else f"le disque OS de la VM n'a pas été créé pendant le job ({obs.get('os_disk_created') or obs.get('os_disk_why') or '?'})")
        return card("not_in_place",
                    f"{head}, finie) : ce n'est pas une restauration sur place de cette VM — {why}. La VM "
                    "isolée n'a pas été restaurée (des disques restaurés, une autre VM) : ne pas lever.",
                    ["Restaurer la VM sur place depuis le poste : glorfindel restore "
                     f"{rid} --before <ISO8601>", "Ou garder l'isolation et acquitter cette carte."])
    at = _epoch(point["time"])
    first, why = restore_plan.incident_start(rid)
    if first is None or at is None or at >= first:
        when = (datetime.fromtimestamp(first, tz=timezone.utc).isoformat() if first is not None else "?")
        return card("point_after",
                    f"{head}, finie) : son point de restauration ({point['time']}) n'est pas antérieur au "
                    f"début de l'incident ({when} : {why}). Le disque restauré peut porter l'attaque : "
                    "aucune levée.",
                    [f"Restaurer un point antérieur depuis le poste : glorfindel restore {rid} --before {when}",
                     "La watch relira la reprise sur Azure et lèvera l'isolation si elle est prouvée."])
    power = str(obs.get("power") or "unknown")
    if power != "running":
        if now - end < start_wait_s():
            report.append({"vm": vm, "job": name, "outcome": "wait", "detail": f"VM {power}"})
            return
        return card("stopped",
                    f"{head}, finie, point {point['time']} antérieur à l'incident) : la VM ne tourne pas "
                    f"({power}) {int((now - end) // 60)} min après. Aucune levée tant qu'elle est arrêtée.",
                    [f"Démarrer la VM : az vm start --ids {rid}",
                     "La watch lèvera alors l'isolation (dans les modes qui le permettent), ou le dira."])
    cp, cp_why = neutralized_by_the_control_plane(obs, start if start is not None else end, restore_principals())
    word = (obs.get("run_command") or {}).get("neutralized")
    if cp is True and word is None and now - end < replay_wait_s():
        report.append({"vm": vm, "job": name, "outcome": "wait",
                       "detail": (obs.get("run_command") or {}).get("why") or "Run Command"})
        return
    neutralized = cp if cp is not True else (True if word is True else (False if word is False else None))
    if now - end < grace_s():
        report.append({"vm": vm, "job": name, "outcome": "wait", "detail": "délai après la fin du job"})
        return
    _emit(connector, emit, rid, vm, iso, obs, neutralized, cp_why, now, report, isolated)


def _emit(connector, emit, rid: str, vm: str, iso: dict, obs: dict, neutralized, why: str, now: float,
          report: list[dict], isolated: set[str]) -> None:
    """Under the VM's lock, from a fresh read: still isolated — the same isolation, no release
    running — noted, then the signal handed on. Noted first: a crash in between loses one release
    (the TTL card says it), never makes two."""
    from glorfindel import escalations
    from glorfindel.actions import _load_isolation_state, _vm_lock

    name = obs["job"]["name"]
    try:
        with _vm_lock(vm, timeout=_LOCK_WAIT_S):
            state = _load_isolation_state(rid)
            if not state or state.get("isolated_at") != iso.get("isolated_at") or state.get("releasing_at"):
                return                          # released, isolated again, or a release running
            _note(rid, name, now, isolated, emitted=datetime.fromtimestamp(now, tz=timezone.utc).isoformat())
    except TimeoutError:
        return                                  # a write is running on this VM: next pass
    for e in _mine(rid):
        try:
            escalations.resolve(e["id"], "La reprise est prouvée sur Azure : recovery_complete émis.")
        except Exception as exc:               # the card stays: said in the log, never blocks
            log.warning("recovery card %s not closed (%s)", e.get("id"), exc)
    signal = _signal(rid, _provider(connector), obs, neutralized, now)
    emit(signal)
    report.append({"vm": vm, "job": name, "outcome": "emitted",
                   "detail": f"recovery_complete {signal['signal_id']}"
                             + (f" — neutralisation : {neutralized} ({why})" if neutralized is not True and why else "")})
