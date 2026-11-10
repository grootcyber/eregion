"""What Azure says of a VM's recovery, read only (REC1, #668): facts, each with its author —
the control plane (the vault, ARM, the activity log) or the guest (what the VM's agent reports).

H0 never restores (SEC17): a restore runs from the operator's workstation, and the
`recovery_complete` it writes stays on that host. The watch that isolated the VM reads the
recovery here instead — never from a file another host wrote, never from the model — and
glorfindel/recovery_watch.py decides what the facts prove. Read here:

  the control plane  the VM's last restore job since a moment (the vault: its status, its type,
                     its container, the point it restored); the VM's power state and the creation
                     time of its OS disk (ARM: a restore in place puts new disks on it); each Run
                     Command on the VM, who ran it, its status, and whether the platform refused it
                     (the activity log) — enough to decide the neutralization (REC1b);
  the guest          what Run Command v1 last said (the instance view: the agent writes it, root
                     on the VM can write it too) — information only: absent, it holds nothing;
                     present and contrary, the watch holds the release;

and the scripts a restored disk may replay (`_replayable_scripts`). Reads only, under Reader:
`Microsoft.RecoveryServices/vaults/backupJobs/read`, `.../recoveryPoints/read`,
`Microsoft.Compute/virtualMachines/read`, `.../instanceView/read`, `.../extensions/read`,
`.../runCommands/read`, `Microsoft.Compute/disks/read`, `Microsoft.Insights/eventtypes/values/read`
— all under `*/read`. Measured on the bench (09/11, REC1b): the instance view never carries Run
Command v1 (`RunCommandLinux` `Ready` in `vmAgent.extensionHandlers`, absent from
`instanceView.extensions`, before and after a restore); the activity log names a managed identity
and a principal with a secret alike (`caller` = object id, `claims.appid` = appId, `claims.oid` =
object id); a Run Command tried on a deallocated VM is logged `Started` then `Failed`, `Conflict`,
code `OperationNotAllowed`, under its real caller, the VM model left as it was; a restore in place
has the « Job Type » « Replace disks ». Unmeasured: in which fields the event carries that status
and that code (`_refused` reads `properties.statusCode`, else `subStatus`, then the error of
`properties.statusMessage`), and how a job names its point.
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
RUN_COMMAND_OP = "microsoft.compute/virtualmachines/runcommand/action"
# The activity log read at most this many pages; one left past it is an error, never « all read ».
ACTIVITY_PAGES = 20
_OID_CLAIM = "http://schemas.microsoft.com/identity/claims/objectidentifier"
# A refusal of the platform (REC1b, measured 09/11 on a deallocated VM): the HTTP status and the
# error code ARM gives a Run Command it never sent to the guest. Any other failure may have reached
# it, and a code that can't be read is not this one.
_REFUSED_STATUS = "conflict"
_REFUSED_CODE = "operationnotallowed"


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


def _callers(event: dict) -> list[str]:
    """The identifiers of who made an activity log event, lowercased: its `caller` (a user's UPN, a
    service principal's appId or object id depending on the token), and its claims' appid and oid."""
    claims = event.get("claims") if isinstance(event.get("claims"), dict) else {}
    ids = [event.get("caller"), claims.get("appid"), claims.get(_OID_CLAIM), claims.get("oid")]
    return sorted({str(i).strip().lower() for i in ids if i and str(i).strip()})


def _fold(value) -> str:
    return " ".join(str(value or "").split()).lower()


def _status(event: dict) -> str:
    return _fold((event.get("status") or {}).get("value"))


def _error_code(message) -> str:
    """The top-level error code of an event's status message — a JSON text (`{"error": {"code":
    …}}`, or `{"status": "Failed", "error": {…}}`) or its object; "" when it can't be read. A code
    under `details` is not the operation's own (a long operation that failed once begun)."""
    import json
    body = message
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return ""
    err = body.get("error") if isinstance(body, dict) else None
    return _fold(err.get("code")) if isinstance(err, dict) else ""


def _refused(event: dict) -> bool:
    """A Run Command the platform refused (REC1b): its event `Failed`, its HTTP status `Conflict`
    (`properties.statusCode`, else `subStatus`), its error code `OperationNotAllowed` (the status
    message). Measured on a deallocated VM: it never reached the guest, the VM model as it was.
    Anything else — another code, another status, a message that can't be read — is not."""
    if _status(event) != "failed":
        return False
    props = event.get("properties") if isinstance(event.get("properties"), dict) else {}
    status = props.get("statusCode") or (event.get("subStatus") or {}).get("value")
    return _fold(status) == _REFUSED_STATUS and _error_code(props.get("statusMessage")) == _REFUSED_CODE


def _refused_operations(events: list[dict]) -> set[str]:
    """The operations (`operationId`) the platform refused: one of their events is a refusal, and
    every other one is a `Started` by the same callers, no later — none that went further."""
    groups: dict[str, list[dict]] = {}
    for e in events:
        if _fold(e.get("operationId")):
            groups.setdefault(_fold(e.get("operationId")), []).append(e)
    out = set()
    for op, group in groups.items():
        refusals = [e for e in group if _refused(e)]
        if not refusals:
            continue
        by, until = _callers(refusals[0]), max(_utc(e.get("eventTimestamp")) for e in refusals)
        if all(_refused(e) or (_status(e) == "started" and _callers(e) == by and _utc(e.get("eventTimestamp")) <= until)
               for e in group):
            out.add(op)
    return out


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

        {"job": None} when there is none. Else {"job": {"name", "status", "start", "end",
        "container_named"}} — and, the job ended (whatever its status: the watch judges it):
        "point" ({"name", "time", "by": "id" | "time"} or {"time": "", "why"}); "job_type" (the
        property bag's « Job Type », "" when absent); "os_disk_created" (ISO, "" when unreadable,
        with "os_disk_why"); "power"; "run_commands" (each Run Command event on the VM since
        `since`: [{"at", "callers", "status", "refused"}], oldest first) or "run_commands_error";
        and, the VM running, "run_command" (the guest's word since the job's end: {"neutralized":
        True | False | None, "why"}) and "replay_vectors". Facts only: nothing here says the
        recovery is proven. Raises when the vault or the VM can't be read."""
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
        bag = _bag(client.job_details.get(vault, v_rg, job["name"]))
        out["job_type"] = bag.get("job type", "")
        out["point"] = self._restored_point(client, bag, vault, v_rg, rg, vm_name)
        out.update(self._os_disk_created(rg, vm_name))
        try:
            out["run_commands"] = self._run_commands_on(resource_id, since)
        except Exception as exc:               # unreadable: the neutralization unknown, said
            out["run_commands_error"] = f"journal d'activité illisible : {str(exc)[:160]}"
        view = self._compute.virtual_machines.instance_view(rg, vm_name)
        out["power"] = self._power_of(view)
        if out["power"] == "running":
            out["run_command"] = self._run_command_since(view, _utc(job["end"]))
            out["replay_vectors"] = self._replayable_scripts(rg, vm_name)
        return out

    def _last_restore_job(self, client, vault: str, v_rg: str, vm_rg: str, vm_name: str,
                          since: datetime | None) -> dict | None:
        """The newest Restore job of THIS VM started after `since`: its name in the vault
        (`entity_friendly_name`), and its container — a job naming another group's is another
        VM's (two VMs of one name share a vault); one naming none is said (`container_named`)."""
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
                best = (start, j, p, bool(container))
        if best is None:
            return None
        start, j, p, named = best
        end = _utc(getattr(p, "end_time", None))
        return {"name": str(getattr(j, "name", "") or ""), "status": str(getattr(p, "status", "") or "Unknown"),
                "start": start.isoformat(), "end": end.isoformat() if end else "", "container_named": named}

    def _restored_point(self, client, bag: dict, vault: str, v_rg: str, vm_rg: str, vm_name: str) -> dict:
        """The recovery point a restore job restored, as the VM's recovery points give it: named
        by the job's property bag (`by: "id"`), or found by the time the bag writes (`by:
        "time"`) — each reading of it must match exactly one point, to the second. Else
        {"time": "", "why"}."""
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
                return {"name": name, "time": points[name].isoformat(), "by": "id"}
            return {"time": "", "why": f"le point {name[:60]} que nomme le job n'est pas parmi ceux de la VM"}
        said = bag.get("recovery point time", "")
        if not said:
            return {"time": "", "why": "le job ne dit pas quel point il a restauré"}
        hits = {n for n, t in points.items() for c in _bag_times(said) if abs((t - c).total_seconds()) < 1}
        if len(hits) == 1:
            name = hits.pop()
            return {"name": name, "time": points[name].isoformat(), "by": "time"}
        return {"time": "", "why": (f"« {said[:40]} » ne désigne "
                                    + ("aucun" if not hits else "pas un seul") + " point de la VM")}

    def _os_disk_created(self, rg: str, vm_name: str) -> dict:
        """When the VM's current OS disk was created (ARM): a restore in place puts new disks on the
        VM; a restore elsewhere (« Restore disks », a new VM) leaves its disk as it was."""
        try:
            vm = self._compute.virtual_machines.get(rg, vm_name)
            disk_id = str(getattr(getattr(getattr(vm.storage_profile, "os_disk", None), "managed_disk", None),
                                  "id", "") or "")
            if not disk_id:
                return {"os_disk_created": "", "os_disk_why": "la VM ne nomme pas de disque OS managé"}
            d_rg, d_name = _parse_vm_resource_id(disk_id)
            created = _utc(getattr(self._compute.disks.get(d_rg, d_name), "time_created", None))
            if created is None:
                return {"os_disk_created": "", "os_disk_why": "la date de création du disque OS ne se lit pas"}
            return {"os_disk_created": created.isoformat(), "os_disk": disk_id}
        except Exception as exc:
            return {"os_disk_created": "", "os_disk_why": f"disque OS illisible : {str(exc)[:160]}"}

    def _run_commands_on(self, resource_id: str, since: str) -> list[dict]:
        """Every Run Command (v1, `runCommand/action`) event on this VM since `since`, from the
        activity log — the control plane's word, never the guest's: [{"at", "callers", "status",
        "refused"}], oldest first, whatever the status. A command that failed, or stayed Accepted
        or Started (cut by the deallocation), left its settings in the VM model all the same: a
        restored disk may replay it. `refused`: the platform refused it (`_refused`, and the
        `Started` of its operation): it never reached the guest (REC1b). Raises when the log can't
        be read."""
        events = self._activity_events(resource_id, since)
        mine = []
        want = resource_id.rstrip("/").lower()
        for e in events:
            op = str((e.get("operationName") or {}).get("value") or "").lower()
            status = str((e.get("status") or {}).get("value") or "")
            rid = str(e.get("resourceId") or e.get("resourceUri") or want).rstrip("/").lower()
            at = _utc(e.get("eventTimestamp"))
            if op != RUN_COMMAND_OP or rid != want or at is None:
                continue
            mine.append((e, {"at": at.isoformat(), "callers": _callers(e), "status": status}))
        refused = _refused_operations([e for e, _ in mine])
        out = [{**r, "refused": _refused(e) or _fold(e.get("operationId")) in refused} for e, r in mine]
        return sorted(out, key=lambda e: e["at"])

    def _activity_events(self, resource_id: str, since: str) -> list[dict]:
        """The activity log's events on this resource since `since` (REST, every page): the test's
        fake when it gave one (`_activity`)."""
        given = getattr(self, "_activity", None)
        if given is not None:
            return list(given(resource_id, since))
        import requests
        start = _utc(since)
        token = self._credential.get_token("https://management.azure.com/.default").token
        url = (f"https://management.azure.com/subscriptions/{self._subscription_id}"
               "/providers/Microsoft.Insights/eventtypes/management/values")
        params = {"api-version": "2015-04-01",
                  "$filter": f"eventTimestamp ge '{start:%Y-%m-%dT%H:%M:%SZ}' and resourceUri eq '{resource_id}'",
                  "$select": ("caller,claims,operationName,operationId,eventTimestamp,status,subStatus,"
                              "properties,resourceId")}
        events: list[dict] = []
        for _ in range(ACTIVITY_PAGES):        # bounded: a VM's few hours of events
            r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20, params=params)
            if not r.ok:
                raise RuntimeError(f"journal d'activité : {r.status_code} {r.text[:120]}")
            body = r.json()
            events += list(body.get("value") or [])
            url, params = body.get("nextLink"), None
            if not url:
                return events
        # Pages left past the bound: what they hold is unknown — the last command among them, maybe.
        raise RuntimeError(f"journal d'activité : plus de {ACTIVITY_PAGES} pages, la suite n'est pas lue")

    @staticmethod
    def _power_of(view) -> str:
        for s in getattr(view, "statuses", None) or []:
            code = str(getattr(s, "code", "") or "")
            if code.lower().startswith("powerstate/"):
                return code.split("/", 1)[1].lower() or "unknown"
        return "unknown"

    @staticmethod
    def _run_command_since(view, end: datetime | None) -> dict:
        """What Run Command v1 last said on the VM — the GUEST's word: its agent writes it, root on
        the VM can too. Read after the restore's end: the harmless command (NEUTRALIZED_MARKER,
        nothing on stderr) → neutralized; another word → not; no word since the restore → None.
        Information, never a proof: the activity log decides, and a word present and contrary holds
        the release (recovery_watch, REC1b). On the bench the instance view never carries Run
        Command v1 (09/11): None."""
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
