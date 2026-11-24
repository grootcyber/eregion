"""The dossier's reads of Azure, read only (DOS4, #1138; `docs/design/dossier-isolation.md` §3.2, §3.3, §3.6,
§6, §7; declared in `glorfindel/enquiry/platform.py`).

Five reads, each anchored on the signal's hour T, each bounded, each under the Reader Imladris holds:
  activity_window  the activity log of the VM (an exact read) and of its children (the read of its group,
                   filtered on the prefix of its id: LEV2's H9), T − 30 min → T + 30 min, ACTIVITY_PAGES
                   pages each (`DoorMixin._arm_paged`, LEV2's reader): every event, its category, its
                   operation and its `operationId`, who made it (`door.actor_ids`);
  backup_jobs      the vault's jobs of this VM (REC1's filter: its name and its container), T − 10 days →
                   T + 10 min, at most JOBS_MAX jobs listed;
  instance_view    the VM's model (its system, written by the platform) and its instance view (its
                   extensions' states, written by its agent: the guest's word; the planned maintenance);
  host_metrics     the host's disk writes, `PT1M`, `Average` and `Maximum`, T − 5 min → T + 3 min, one call,
                   at most POINTS_MAX points;
  resource_health  the VM's availability as Resource Health says it now.

**Unreadable is never empty.** A read that fails, is refused (403), is cut past its bound, or answers in a
shape it does not document is `echec`, with its reason — never rows, never `vide`. An empty answer before
its source's latency has passed is `en_attente` (`catalog.outcome`). A value that does not pass its check
(`catalog.PARAMS`), or a vault that is not known, is `refusee`: the read is not made. Nothing is written.
"""
from __future__ import annotations

from datetime import datetime, timezone

from glorfindel import kql
from glorfindel.enquiry import catalog
from glorfindel.enquiry.platform import PLATFORM_READS
from glorfindel.providers.azure.door import ARM, ACTIVITY_API, CutRead, _event_key, _group_of, actor_ids
from glorfindel.providers.azure.recovery import _utc

JOBS_MAX = 5000               # a vault's jobs listed at most; past it the read is cut, never « none »
POINTS_MAX = 500              # the points of the metrics' answer kept at most; past it: cut
ROWS_MAX = 500                # the events of the activity log kept at most; past it: cut
METRICS_API = "2018-01-01"
HEALTH_API = "2020-05-01"
METRIC_NAMES = "OS Disk Write Bytes/sec,Data Disk Write Bytes/sec,Disk Write Bytes"
_SELECT = ("caller,claims,category,level,operationName,operationId,eventTimestamp,submissionTimestamp,status,"
           "subStatus,properties,resourceId,resourceGroupName,eventDataId")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_line(exc: BaseException) -> str:
    return (str(exc).strip().splitlines() or [type(exc).__name__])[0][:200]


def _value(e: dict, key: str) -> str:
    v = e.get(key)
    return str((v or {}).get("value") or "") if isinstance(v, dict) else str(v or "")


def _event_row(e: dict) -> dict:
    """What the dossier keeps of an event: bounded, its token reduced to who made it."""
    return {"at": str(e.get("eventTimestamp") or ""), "submitted": str(e.get("submissionTimestamp") or ""),
            "operation": _value(e, "operationName"), "status": _value(e, "status"),
            "category": _value(e, "category"), "resource": str(e.get("resourceId") or e.get("resourceUri") or ""),
            "operation_id": str(e.get("operationId") or ""), "ids": sorted(actor_ids(e))[:6]}


class DossierReadsMixin:
    """The dossier's reads of Azure (part of AzureConnector)."""

    def dossier_reads(self, resource_id: str, at: datetime, *, vault: str = "", vault_rg: str = "",
                      only=None, now: datetime | None = None) -> tuple[dict, int]:
        """({read id: catalog.Reading}, the calls made) for the reads `only` names (all by default), on the
        VM `resource_id`, anchored on `at` (T). Never raises: what fails is said in its reading."""
        now = now or datetime.now(timezone.utc)
        ids = [i for i in PLATFORM_READS if only is None or i in only]
        if self.dry_run:
            return {i: catalog.Reading(i, catalog.REFUSEE, why="dry run : rien n'est lu") for i in ids}, 0
        values, refused = self._dossier_values(resource_id, vault, vault_rg)
        out, calls = {}, 0
        for read_id in ids:
            read = PLATFORM_READS[read_id]
            if missing := [p for p in read.params if p not in values]:
                out[read_id] = catalog.Reading(read_id, catalog.REFUSEE,
                                               why="; ".join(refused.get(p, f"{p} absent") for p in missing))
                continue
            start, end = catalog.window(read, at)
            try:
                rows, n = getattr(self, f"_dossier_{read_id}")(values, start, min(end, now))
            except Exception as exc:        # failed, refused, cut, malformed: unreadable, said
                out[read_id] = catalog.Reading(read_id, catalog.ECHEC, why=_first_line(exc))
                calls += 1
                continue
            calls += n
            out[read_id] = catalog.outcome(read, rows, at=at, now=now)
        return out, calls

    def _dossier_values(self, resource_id: str, vault: str, vault_rg: str) -> tuple[dict, dict]:
        """The parameters, each through its check (`catalog.PARAMS`); ({name: value}, {name: why refused})."""
        values, refused = {}, {}
        try:
            values["vm"] = catalog.PARAMS["vm"].check(resource_id)
        except kql.UnsafeValue as exc:
            refused["vm"] = f"la VM refusée : {exc}"
            return values, refused
        if not vault:
            refused["vault"] = "aucun coffre connu (action_backends, GLORFINDEL_BACKUP_VAULT)"
            return values, refused
        sub = resource_id.split("/")[2]
        try:
            values["vault"] = catalog.PARAMS["vault"].check(
                f"/subscriptions/{sub}/resourceGroups/{vault_rg or _group_of(resource_id)}"
                f"/providers/Microsoft.RecoveryServices/vaults/{vault}")
        except kql.UnsafeValue as exc:
            refused["vault"] = f"le coffre refusé : {exc}"
        return values, refused

    # ── the five reads: (rows, calls); each raises when it cannot be read whole ──────────────────

    def _dossier_activity_window(self, values: dict, start: datetime, end: datetime) -> tuple[list, int]:
        vm = values["vm"]
        url = f"{ARM}/subscriptions/{vm.split('/')[2]}/providers/Microsoft.Insights/eventtypes/management/values"
        events, calls, prefix = {}, 0, vm.rstrip("/").lower() + "/"
        for field, value in (("resourceUri", vm), ("resourceGroupName", _group_of(vm))):
            params = {"api-version": ACTIVITY_API, "$select": _SELECT,
                      "$filter": f"eventTimestamp ge '{_iso(start)}' and eventTimestamp le '{_iso(end)}' "
                                 f"and {field} eq '{value}'"}
            got, pages = self._arm_paged(url, params)
            calls += pages
            for e in got:
                rid = str(e.get("resourceId") or e.get("resourceUri") or "").rstrip("/").lower()
                if field == "resourceUri" or rid.startswith(prefix):
                    events.setdefault(_event_key(e), e)
        if len(events) > ROWS_MAX:
            raise CutRead(f"plus de {ROWS_MAX} événements dans la fenêtre, la suite n'est pas gardée")
        return sorted((_event_row(e) for e in events.values()), key=lambda r: r["at"]), calls

    def _dossier_backup_jobs(self, values: dict, start: datetime, end: datetime) -> tuple[list, int]:
        from glorfindel.response.ids import _parse_vm_resource_id
        rg, name = _parse_vm_resource_id(values["vm"])
        parts = values["vault"].split("/")
        want, rows, seen = f";{rg.lower()};{name.lower()}", [], 0
        for j in self._backup_client().backup_jobs.list(parts[-1], parts[4]):
            seen += 1
            if seen > JOBS_MAX:
                raise CutRead(f"plus de {JOBS_MAX} jobs dans le coffre, la suite n'est pas lue")
            p = getattr(j, "properties", None)
            if p is None or str(getattr(p, "entity_friendly_name", "") or "").lower() != name.lower():
                continue
            container = str(getattr(p, "container_name", "") or "").lower()
            if container and not container.endswith(want):
                continue                     # a homonym's, in another group (SEC-H, REC1)
            began, ended = _utc(getattr(p, "start_time", None)), _utc(getattr(p, "end_time", None))
            if began is None or not start <= began <= end:
                continue
            rows.append({"name": str(getattr(j, "name", "") or ""), "operation": str(getattr(p, "operation", "") or ""),
                         "status": str(getattr(p, "status", "") or ""), "start": began.isoformat(),
                         "end": ended.isoformat() if ended else "",
                         **({"duration_s": round((ended - began).total_seconds())} if ended else {})})
        return sorted(rows, key=lambda r: r["start"]), 1

    def _dossier_instance_view(self, values: dict, start: datetime, end: datetime) -> tuple[list, int]:
        from glorfindel.response.ids import _parse_vm_resource_id
        self._ensure_clients()
        rg, name = _parse_vm_resource_id(values["vm"])
        model = self._compute.virtual_machines.get(rg, name)
        os_type = str(getattr(getattr(getattr(model, "storage_profile", None), "os_disk", None), "os_type", "") or "")
        view = self._compute.virtual_machines.instance_view(rg, name)
        exts = []
        for ext in (getattr(view, "extensions", None) or [])[:20]:
            states = [{"code": str(getattr(s, "code", "") or ""), "time": str(getattr(s, "time", "") or "")}
                      for s in (getattr(ext, "statuses", None) or [])[:4]]
            exts.append({"name": str(getattr(ext, "name", "") or ""), "type": str(getattr(ext, "type", "") or ""),
                         "states": states})
        m = getattr(view, "maintenance_redeploy_status", None)
        maintenance = None if m is None else {
            k: str(getattr(m, k, "") or "") for k in ("is_customer_initiated_maintenance_allowed",
                                                       "pre_maintenance_window_start_time",
                                                       "maintenance_window_start_time", "last_operation_result_code")}
        system = os_type.split(".")[-1].lower()
        return [{"systeme": system if system in catalog.SYSTEMS else "", "os_type": os_type[:40],
                 "extensions": exts, "maintenance": maintenance}], 2

    def _dossier_host_metrics(self, values: dict, start: datetime, end: datetime) -> tuple[list, int]:
        body = self._arm_get(f"{ARM}{values['vm']}/providers/Microsoft.Insights/metrics",
                             {"api-version": METRICS_API, "metricnames": METRIC_NAMES, "interval": "PT1M",
                              "aggregation": "Average,Maximum", "timespan": f"{_iso(start)}/{_iso(end)}"})
        metrics = body.get("value") if isinstance(body, dict) else None
        if not isinstance(metrics, list) or not all(isinstance(m, dict) for m in metrics):
            raise RuntimeError("réponse d'ARM mal formée : pas la liste `value` des métriques")
        rows = []
        for m in metrics:
            series = m.get("timeseries")
            if not isinstance(series, list):
                raise RuntimeError("réponse d'ARM mal formée : une métrique sans sa liste `timeseries`")
            for ts in series:
                for d in (ts.get("data") if isinstance(ts, dict) else None) or []:
                    if not isinstance(d, dict) or (d.get("average") is None and d.get("maximum") is None):
                        continue             # a minute the host has not given yet: no point
                    rows.append({"metrique": _value(m, "name"), "minute": str(d.get("timeStamp") or ""),
                                 "moyenne": d.get("average"), "maximum": d.get("maximum")})
                    if len(rows) > POINTS_MAX:
                        raise CutRead(f"plus de {POINTS_MAX} points de métrique, la suite n'est pas gardée")
        return sorted(rows, key=lambda r: (r["metrique"], r["minute"])), 1

    def _dossier_resource_health(self, values: dict, start: datetime, end: datetime) -> tuple[list, int]:
        body = self._arm_get(f"{ARM}{values['vm']}/providers/Microsoft.ResourceHealth/availabilityStatuses/current",
                             {"api-version": HEALTH_API})
        props = body.get("properties") if isinstance(body, dict) else None
        if not isinstance(props, dict) or not props.get("availabilityState"):
            raise RuntimeError("réponse d'ARM mal formée : pas d'availabilityState")
        return [{"etat": str(props.get("availabilityState"))[:40], "raison": str(props.get("reasonType") or "")[:80],
                 "resume": str(props.get("summary") or "")[:200],
                 "depuis": str(props.get("occuredTime") or props.get("occurredTime") or ""),
                 "dit_a": str(props.get("reportedTime") or "")}], 1
