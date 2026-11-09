"""The watch sees the recovery of a VM it isolated, on Azure, and says it (REC1, #668).

H0 never restores (SEC17): a restore runs from the operator's workstation, whose
`glorfindel restore --wait` writes its `recovery_complete` where it runs. The watch on H0
never reads that host's files (SEC3), so it never lifted an isolation on its own; and a
release made elsewhere was put back by its reassertion. Now, every
GLORFINDEL_RECOVERY_INTERVAL_S (60 s; 0: off), for each isolation of its state, the watch
reads on Azure (`observed_restore`, the adapter; never a file another host wrote, never the
model) that:

  - a restore job of this VM, started after its isolation, is finished and succeeded;
  - the recovery point it restored precedes the start of the incident — the isolation, or
    the first detection when it came before (`restore_plan.incident_start`, the rule of
    `--before`);
  - the VM runs.

Then it builds its own `recovery_complete` — the fields `glorfindel restore --wait` gives, the
neutralization of Run Command as Azure reads it after the restore, the scripts a restored disk
may replay — vouched for in this process, and hands it to the graph: the release follows as on
the workstation (autonomous in the modes that allow it, a card otherwise; the release
precondition of agent.py unchanged). A job that failed, a point not before the incident, a
point it can't read: one card that says why (`release_hold`, nothing to approve), no release.
A VM that does not run once the job is done: one card, and the watch keeps reading — started,
the release follows.

Once per job (RECOVERIES_FILE, written before the signal leaves): two passes never emit twice
nor write two cards. A job started here (`glorfindel restore` on this host, its claim held)
is left to it, and a job ended less than GRACE_S ago waits: the process that restored releases
itself first (`restore --wait`).
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
# A record older than this is dropped at the next write: a VM isolated again has a new isolation,
# after which an old job is never read.
_KEEP_S = 30 * 86400
# A job still running: nothing to say yet (the statuses Azure Backup gives a job).
RUNNING = frozenset({"inprogress", "cancelling", "notstarted"})
# The kinds of card that end a job: nothing more is read of it.
_TERMINAL = frozenset({"failed", "point_after", "point_unknown"})


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


def _note(resource_id: str, job: str, now: float, **fields) -> None:
    """Write what was done of this job, at once (a temp file renamed over it). Raises OSError."""
    from glorfindel.response.state import _atomic_write_text
    with _LOCK:
        data = {k: v for k, v in _load().items()
                if isinstance(v, dict) and now - float(v.get("at_epoch") or 0) < _KEEP_S}
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


def _signal(resource_id: str, provider: str, obs: dict, now: float) -> dict:
    """The recovery_complete the watch emits: the fields `glorfindel restore --wait` gives
    (cli._build_recovery_signal) — what the model reads is the same as on the workstation —,
    vouched for in this process (SEC3)."""
    from glorfindel.actions import _rid_hash
    from glorfindel.signal_origin import vouch
    ts = datetime.fromtimestamp(now, tz=timezone.utc)
    run_id = f"{ts:%Y%m%dT%H%M%SZ}-{_rid_hash(resource_id)}"
    job = obs["job"]
    start, end = _epoch(job.get("start")), _epoch(job.get("end"))
    rc = obs.get("run_command") or {}
    vectors = [str(v) for v in obs.get("replay_vectors") or []]
    neutralized = rc.get("neutralized")
    if vectors:
        neutralized = False            # as on the workstation: another script a disk may replay
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
            "recovery_point_time": (obs.get("point") or {}).get("time", ""),
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
    something of: {"vm", "job", "outcome": "emitted" | "card" | "wait", "detail"}. `emit`
    takes the recovery_complete (the watch: its VM's queue). Raises nothing but an OSError of a
    record that could not be written (said by the watch; the next pass tries again)."""
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
    for iso in isolations:
        try:
            _one(connector, emit, iso, vault, vault_rg, now, report)
        except NotImplementedError:
            return report                      # the provider can't say: nothing proven
        except OSError:
            raise
        except Exception as exc:               # unreadable here: no proof, no release
            report.append({"vm": iso.get("vm_name", "?"), "job": "", "outcome": "unreadable",
                           "detail": f"reprise illisible sur Azure : {exc}"})
    return report


def _one(connector, emit, iso: dict, vault: str, vault_rg: str, now: float, report: list[dict]) -> None:
    from glorfindel import restore_plan
    from glorfindel.jobs import restore_in_progress

    rid, vm = str(iso.get("resource_id") or ""), str(iso.get("vm_name") or "")
    isolated_at = _epoch(iso.get("isolated_at"))
    if not rid or isolated_at is None:
        return
    if restore_in_progress(vm):
        return                                  # restored from here: its own process releases
    since = datetime.fromtimestamp(isolated_at, tz=timezone.utc).isoformat()
    obs = connector.observed_restore(rid, since, vault=vault, vault_rg=vault_rg)
    job = obs.get("job") if isinstance(obs, dict) else None
    if not job or not job.get("name"):
        return
    status = str(job.get("status") or "")
    if status.lower() in RUNNING:
        return
    name = job["name"]
    done = seen(rid, name)
    if done.get("emitted") or done.get("said") in _TERMINAL:
        return

    def card(kind: str, reason: str, steps: list[str]) -> None:
        if done.get("said") == kind:
            return
        _card(rid, vm, name, kind, reason, steps)
        _note(rid, name, now, said=kind)        # after the card: refused, the next pass says it
        report.append({"vm": vm, "job": name, "outcome": "card", "detail": reason})

    head = f"Restauration de {vm} lue sur Azure (job {name}"
    if status.lower() != "completed":
        return card("failed", f"{head}, {status}) : elle n'a pas abouti. L'isolation reste en place, "
                              "aucune levée.",
                    ["Lire le job dans le coffre (portail, `az backup job show`).",
                     f"Relancer le restore depuis le poste : glorfindel restore {rid} --before <ISO8601>",
                     "Ou garder l'isolation et acquitter cette carte."])
    point = obs.get("point") or {}
    start, why = restore_plan.incident_start(rid)
    if not point.get("time"):
        return card("point_unknown",
                    f"{head}, finie) : le point restauré ne se lit pas sur Azure ({point.get('why') or '?'}). "
                    "Glorfindel ne peut pas dire qu'il précède l'incident : aucune levée.",
                    ["Vérifier dans le coffre le point que le job a restauré.",
                     f"S'il précède l'incident et que la VM est saine : glorfindel release {rid} --yes",
                     "Sinon, restaurer un point antérieur depuis le poste."])
    at = _epoch(point["time"])
    if start is None or at is None or at >= start:
        when = (datetime.fromtimestamp(start, tz=timezone.utc).isoformat() if start is not None else "?")
        return card("point_after",
                    f"{head}, finie) : son point de restauration ({point['time']}) n'est pas antérieur au "
                    f"début de l'incident ({when} : {why}). Le disque restauré peut porter l'attaque : "
                    "aucune levée.",
                    [f"Restaurer un point antérieur depuis le poste : glorfindel restore {rid} --before {when}",
                     "La watch relira la reprise sur Azure et lèvera l'isolation si elle est prouvée."])
    end = _epoch(job.get("end")) or now
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
    rc = obs.get("run_command") or {}
    if rc.get("neutralized") is None and now - end < replay_wait_s():
        report.append({"vm": vm, "job": name, "outcome": "wait", "detail": rc.get("why") or "Run Command"})
        return
    if now - end < grace_s():
        report.append({"vm": vm, "job": name, "outcome": "wait", "detail": "délai après la fin du job"})
        return
    _emit(connector, emit, rid, vm, iso, obs, now, report)


def _emit(connector, emit, rid: str, vm: str, iso: dict, obs: dict, now: float, report: list[dict]) -> None:
    """Under the VM's lock, from a fresh read: still isolated — the same isolation — noted, then
    the signal handed on. Noted first: a crash in between loses one release (the TTL card says
    it), never makes two."""
    from glorfindel import escalations
    from glorfindel.actions import _load_isolation_state, _vm_lock

    name = obs["job"]["name"]
    try:
        with _vm_lock(vm, timeout=_LOCK_WAIT_S):
            state = _load_isolation_state(rid)
            if not state or state.get("isolated_at") != iso.get("isolated_at"):
                return                          # released, or isolated again, meanwhile
            _note(rid, name, now, emitted=datetime.fromtimestamp(now, tz=timezone.utc).isoformat())
    except TimeoutError:
        return                                  # a write is running on this VM: next pass
    for e in _mine(rid):
        try:
            escalations.resolve(e["id"], "La reprise est prouvée sur Azure : recovery_complete émis.")
        except Exception as exc:               # the card stays: said in the log, never blocks
            log.warning("recovery card %s not closed (%s)", e.get("id"), exc)
    signal = _signal(rid, _provider(connector), obs, now)
    emit(signal)
    report.append({"vm": vm, "job": name, "outcome": "emitted",
                   "detail": f"recovery_complete {signal['signal_id']}"})
