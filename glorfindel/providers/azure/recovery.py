"""What Azure says of a VM's recovery, read only (REC1, #668): the last restore job of this VM
in the vault since a moment, the recovery point it restored, the VM's power state, and what
its last Run Command said since the restore.

H0 never restores (SEC17): a restore runs from the operator's workstation, and the
`recovery_complete` it writes stays on that host. The watch that isolated the VM reads the
recovery here instead — never from a file another host wrote, never from the model — and
glorfindel/recovery_watch.py decides what it proves. Reads only, under Reader:
`Microsoft.RecoveryServices/vaults/backupJobs/read`, `.../recoveryPoints/read`,
`Microsoft.Compute/virtualMachines/instanceView/read`, `.../extensions/read`,
`.../runCommands/read` — all under `*/read`. Unmeasured on the bench (REC1): the property
bag of a restore job (`Recovery point time`, its format), the instance view's word of Run
Command v1 after a restored disk boots.
"""
from __future__ import annotations

from datetime import datetime, timezone

from glorfindel.providers.azure.restore import NEUTRALIZED_MARKER, _rp_time
from glorfindel.response.ids import _parse_vm_resource_id

# The time formats a job's property bag may give a point's time in (Azure writes it as text,
# US style in the portal's exports — unmeasured): each candidate must match one of the VM's
# recovery points to the second, or the point is unreadable.
_BAG_FORMATS = ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S")
# Run Command v1's handlers (a type, or the extension's name): v2's commands are resources of
# their own, listed by _replayable_scripts.
_RUN_COMMAND_V1 = ("runcommandlinux", "runcommandwindows")


def _utc(value) -> datetime | None:
    """A datetime in UTC (naive: UTC), from a datetime or an ISO text; None otherwise."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).astimezone(timezone.utc)


def _bag_times(text: str) -> list[datetime]:
    """Every reading of a point's time as the property bag writes it, in UTC."""
    raw = " ".join(str(text or "").replace("UTC", "").split())
    found = []
    iso = _utc(raw)
    if iso is not None:
        found.append(iso)
    for fmt in _BAG_FORMATS:
        try:
            found.append(datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc))
        except ValueError:
            continue
    return found


def _bag(details) -> dict[str, str]:
    """A job's property bag, its keys folded (spaces, case): Azure's keys carry a trailing space
    or not, by version."""
    info = getattr(getattr(details, "properties", None), "extended_info", None)
    bag = getattr(info, "property_bag", None) or {}
    return {" ".join(str(k).split()).lower(): str(v) for k, v in dict(bag).items()}


def _sections(message: str) -> tuple[str, str]:
    """(stdout, stderr) of Run Command v1's word ("Enable succeeded: [stdout] … [stderr] …"), or
    the whole message as stdout when it has no sections."""
    text = str(message or "")
    if "[stdout]" not in text:
        return text.strip(), ""
    out = text.split("[stdout]", 1)[1]
    out, _, err = out.partition("[stderr]")
    return out.strip(), err.strip()


class RecoveryMixin:
    """A VM's recovery, read on Azure (part of AzureConnector)."""

    def _backup_client(self):
        """The vault's client: the test's fake when it gave one (`_backup`), else the SDK's."""
        given = getattr(self, "_backup", None)
        if given is not None:
            return given
        from azure.mgmt.recoveryservicesbackup import RecoveryServicesBackupClient
        return RecoveryServicesBackupClient(self._credential, self._subscription_id)

    def observed_restore(self, resource_id: str, since: str, vault: str = "", vault_rg: str = "") -> dict:
        """The last restore of this VM the vault ran since `since` (ISO 8601), read only.

        {"job": None} when there is none. Else {"job": {"name", "status", "start", "end"}} —
        and, the job ended (whatever its status: the watch judges it, glorfindel/recovery_watch.py):
        "point" ({"name", "time"} or {"time": "", "why"}), "power" ("running", "deallocated",
        "stopped", … or "unknown"), and, the VM running, "run_command" ({"neutralized": True |
        False | None, "why"}) and "replay_vectors". Facts only: nothing here says the recovery is
        proven. Raises when the vault or the VM can't be read."""
        if self.dry_run:
            return {"job": None, "dry_run": True}
        if not vault:
            from glorfindel.config import NO_VAULT_MSG
            raise RuntimeError(NO_VAULT_MSG)
        self._ensure_clients()
        rg, vm_name = _parse_vm_resource_id(resource_id)
        v_rg = vault_rg or rg
        client = self._backup_client()
        job = self._last_restore_job(client, vault, v_rg, rg, vm_name, _utc(since))
        if job is None:
            return {"job": None}
        out: dict = {"job": job}
        if not job["end"]:
            return out                         # still running: nothing ended to read
        out["point"] = self._restored_point(client, vault, v_rg, rg, vm_name, job["name"])
        view = self._compute.virtual_machines.instance_view(rg, vm_name)
        out["power"] = self._power_of(view)
        if out["power"] == "running":
            out["run_command"] = self._run_command_since(view, _utc(job["end"]))
            out["replay_vectors"] = self._replayable_scripts(rg, vm_name)
        return out

    def _last_restore_job(self, client, vault: str, v_rg: str, vm_rg: str, vm_name: str,
                          since: datetime | None) -> dict | None:
        """The newest Restore job of THIS VM started after `since`: its name in the vault
        (`entity_friendly_name`), and its container when the job names one — two VMs of one
        name in two groups share a vault."""
        if since is None:
            return None
        want = f";{vm_rg.lower()};{vm_name.lower()}"
        best = None
        for j in client.backup_jobs.list(vault, v_rg):
            p = getattr(j, "properties", None)
            if p is None or str(getattr(p, "operation", "") or "").lower() != "restore":
                continue
            if str(getattr(p, "entity_friendly_name", "") or "").lower() != vm_name.lower():
                continue
            container = str(getattr(p, "container_name", "") or "").lower()
            if container and not container.endswith(want):
                continue
            start = _utc(getattr(p, "start_time", None))
            if start is None or start <= since:
                continue
            if best is None or start > best[0]:
                best = (start, j, p)
        if best is None:
            return None
        start, j, p = best
        end = _utc(getattr(p, "end_time", None))
        return {"name": str(getattr(j, "name", "") or ""), "status": str(getattr(p, "status", "") or "Unknown"),
                "start": start.isoformat(), "end": end.isoformat() if end else ""}

    def _restored_point(self, client, vault: str, v_rg: str, vm_rg: str, vm_name: str, job_name: str) -> dict:
        """The recovery point a restore job restored, as the VM's recovery points give it: named
        by the job's property bag, or found by the time the bag writes — each reading of it
        must match exactly one point, to the second. Else {"time": "", "why"}."""
        bag = _bag(client.job_details.get(vault, v_rg, job_name))
        container, item = self._resolve_backup_item_names(client, vault, v_rg, vm_rg, vm_name)
        points = {}
        for rp in client.recovery_points.list(vault, v_rg, "Azure", container, item):
            t = _utc(_rp_time(rp))
            if t is not None and getattr(rp, "name", None):
                points[str(rp.name)] = t
        named = next((bag[k] for k in ("recovery point id", "recoverypointid", "recovery point name")
                      if bag.get(k)), "")
        if named:
            name = named.rstrip("/").rsplit("/", 1)[-1]
            if name in points:
                return {"name": name, "time": points[name].isoformat()}
            return {"time": "", "why": f"le point {name[:60]} que nomme le job n'est pas parmi ceux de la VM"}
        said = bag.get("recovery point time", "")
        if not said:
            return {"time": "", "why": "le job ne dit pas quel point il a restauré"}
        hits = {n for n, t in points.items() for c in _bag_times(said) if abs((t - c).total_seconds()) < 1}
        if len(hits) == 1:
            name = hits.pop()
            return {"name": name, "time": points[name].isoformat()}
        return {"time": "", "why": (f"« {said[:40]} » ne désigne "
                                    + ("aucun" if not hits else "pas un seul") + " point de la VM")}

    @staticmethod
    def _power_of(view) -> str:
        for s in getattr(view, "statuses", None) or []:
            code = str(getattr(s, "code", "") or "")
            if code.lower().startswith("powerstate/"):
                return code.split("/", 1)[1].lower() or "unknown"
        return "unknown"

    @staticmethod
    def _run_command_since(view, end: datetime | None) -> dict:
        """What Run Command v1 last said on the VM, read after the restore's end: the harmless
        command (NEUTRALIZED_MARKER, nothing on stderr) → neutralized; another word → not; no
        word since the restore (the restored disk not yet booted, no handler) → None. A word
        from before the restore proves nothing: written by the guest, the old disk's attacker
        could have written it."""
        latest = None
        for ext in getattr(view, "extensions", None) or []:
            kind = f"{getattr(ext, 'type', '') or ''} {getattr(ext, 'name', '') or ''}".lower()
            if not any(k in kind for k in _RUN_COMMAND_V1):
                continue
            for s in getattr(ext, "statuses", None) or []:
                at = _utc(getattr(s, "time", None))
                if at is not None and (latest is None or at > latest[0]):
                    latest = (at, str(getattr(s, "message", "") or ""))
        if latest is None:
            return {"neutralized": None, "why": "aucune parole de Run Command sur la VM"}
        if end is None or latest[0] <= end:
            return {"neutralized": None, "why": "Run Command n'a rien dit depuis la fin du restore"}
        out, err = _sections(latest[1])
        if out == NEUTRALIZED_MARKER and not err:
            return {"neutralized": True, "why": ""}
        return {"neutralized": False,
                "why": "la dernière commande Run Command rejouée n'est pas l'inoffensive de Glorfindel"}
