"""The dossier's reads of Azure, read only (DOS4, #1138; `docs/design/dossier-isolation.md` §3.2, §3.3, §3.6,
§6, §7; declared in `glorfindel/enquiry/platform.py`).

Five reads, each anchored on the signal's hour T, each bounded, each under the Reader Imladris holds:
  activity_window  the activity log of the VM (an exact read) and of its children (the read of its group,
                   filtered on the prefix of its id: LEV2's H9), T − 30 min → T + 30 min, ACTIVITY_PAGES
                   pages each (as LEV2 reads it, each page counted): every event, its category, its
                   operation and its `operationId`, who made it (`door.actor_ids`);
  backup_jobs      the vault's jobs of this VM (REC1's filter: its name and its container), T − 10 days →
                   T + 10 min, at most JOBS_MAX jobs listed — the window asked of the service too (ENQ5v);
  instance_view    the VM's model (its system, written by the platform) and its instance view (its
                   extensions' states, written by its agent: the guest's word; the planned maintenance);
  host_metrics     the host's disk writes, `PT1M`, `Average` and `Maximum`, T − 5 min → T + 3 min, one call,
                   at most POINTS_MAX points;
  resource_health  the VM's availability as Resource Health says it now.

**The enquiry's reads of the vault** (ENQ5a, #1162; `glorfindel/enquiry/catalog.py`, `ENQ5A_READS`): the
same code, on the enquiry's windows — `vault_jobs` is `backup_jobs`' listing and filter, T − 30 min → T;
`vault_activity` is `activity_window`'s read, on the vault and its children instead of the VM, T − 60 min
→ T, its reads set aside. `enquiry_reads` runs them; nothing of the watch calls it before ENQ5b (the
harness plays them recorded; `scripts/capture_enquete.py` reads them at the bench, the maintainer's hand).

**Unreadable is never empty.** A read that fails, is refused (403), is cut past its bound, or answers in a
shape it does not document is `echec`, with its reason — never rows, never `vide`. An empty answer before
its source's latency has passed is `en_attente` (`catalog.outcome`). A value that does not pass its check
(`catalog.PARAMS`), or a vault that is not known, is `refusee`: the read is not made. Nothing is written.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from glorfindel import kql
from glorfindel.enquiry import catalog
from glorfindel.enquiry.platform import PLATFORM_READS
from glorfindel.providers.azure.door import ARM, ACTIVITY_API, CutRead, _event_key, _group_of, _iso, actor_ids
from glorfindel.providers.azure.recovery import ACTIVITY_PAGES, _utc

JOBS_MAX = 5000               # a vault's jobs listed at most; past it the read is cut, never « none »
POINTS_MAX = 500              # the points of the metrics' answer kept at most; past it: cut
ROWS_MAX = 500                # the events of the activity log kept at most; past it: cut
METRICS_API = "2018-01-01"
HEALTH_API = "2020-05-01"
METRIC_NAMES = "OS Disk Write Bytes/sec,Data Disk Write Bytes/sec,Disk Write Bytes"
# ENQ5v (#1221): the vault's listing is asked on the read's window (`$filter`, `startTime` and `endTime`), never
# on the service's default. Unfiltered, the listing read no job of an episode captured days later (bree, 10/11:
# the 02:33:19 backup, seen in the vault, read 0 rows on 26/11) — the default range of `backupJobs` is not
# documented, and measured nowhere yet: `docs/design/enquete-raisonnee.md` §9.7. The form is the one
# `az backup job list --start-date` writes (azure-cli, `backup/custom_help.py`, `get_filter_string`: UTC,
# `yyyy-MM-dd hh:mm:ss tt`). Widened by JOBS_FILTER_MARGIN each side, whatever the service compares the bounds to
# (a job's start, or its end, a backup still running at T having none): the read keeps its own window, exactly,
# below. A filter the service refuses is a failed read (`echec`), never « no job ».
JOBS_FILTER_MARGIN = timedelta(hours=1)
_SELECT = ("caller,claims,category,level,operationName,operationId,eventTimestamp,submissionTimestamp,status,"
           "subStatus,properties,resourceId,resourceGroupName,eventDataId")


def _read_why(exc: BaseException) -> str:
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


class Calls:
    """The calls a read made, counted before each one: what a read that fails has spent is known."""
    __slots__ = ("n",)

    def __init__(self) -> None:
        self.n = 0


class DossierReadsMixin:
    """The dossier's reads of Azure (part of AzureConnector)."""

    def dossier_reads(self, resource_id: str, at: datetime, *, vault: str = "", vault_rg: str = "",
                      only=None, now: datetime | None = None) -> tuple[dict, int]:
        """({read id: catalog.Reading}, the calls made) for the reads `only` names (all by default), on the
        VM `resource_id`, anchored on `at` (T). Never raises: what fails is said in its reading."""
        return self._platform_reads(PLATFORM_READS, resource_id, at, vault=vault, vault_rg=vault_rg, only=only,
                                    now=now)

    def enquiry_reads(self, resource_id: str, at: datetime, *, vault: str = "", vault_rg: str = "",
                      only=None, now: datetime | None = None) -> tuple[dict, int]:
        """ENQ5a: the enquiry's reads of ARM (`catalog.READS`, `kind="arm"`: the vault's jobs, its activity
        log), as `dossier_reads` reads the dossier's — the same loop, the same states, the same counting."""
        arm = {i: r for i, r in catalog.READS.items() if r.kind == "arm"}
        return self._platform_reads(arm, resource_id, at, vault=vault, vault_rg=vault_rg, only=only, now=now)

    def _platform_reads(self, reads, resource_id: str, at: datetime, *, vault: str, vault_rg: str, only,
                        now: datetime | None) -> tuple[dict, int]:
        now = now or datetime.now(timezone.utc)
        ids = [i for i in reads if only is None or i in only]
        if self.dry_run:
            return {i: catalog.Reading(i, catalog.REFUSEE, why="dry run : rien n'est lu") for i in ids}, 0
        values, refused = self._dossier_values(resource_id, vault, vault_rg)
        out, calls = {}, 0
        for read_id in ids:
            read = reads[read_id]
            if missing := [p for p in read.params if p not in values]:
                out[read_id] = catalog.Reading(read_id, catalog.REFUSEE,
                                               why="; ".join(refused.get(p, f"{p} absent") for p in missing))
                continue
            start, end = catalog.window(read, at)
            made = Calls()                   # each call counted before it is made: a read that fails says its own
            try:
                rows = getattr(self, f"_dossier_{read_id}")(values, start, min(end, now), made)
            except Exception as exc:        # failed, refused, cut, malformed: unreadable, said
                out[read_id] = catalog.Reading(read_id, catalog.ECHEC, why=_read_why(exc))
                calls += made.n
                continue
            calls += made.n
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

    # ── the five reads: their rows, each call counted in `made`; each raises when it cannot be read whole ─

    def _dossier_paged(self, url: str, params: dict | None, made: Calls) -> list:
        """Every page of an activity log's listing, ACTIVITY_PAGES at most (as `DoorMixin._arm_paged`, each
        page counted): a page left past the bound raises CutRead; a next page outside ARM is refused."""
        items: list = []
        for _ in range(ACTIVITY_PAGES):
            if not str(url).startswith(f"{ARM}/"):
                raise RuntimeError("page suivante hors d'Azure Resource Manager, refusée")
            made.n += 1
            body = self._arm_get(url, params)
            value = body.get("value") if isinstance(body, dict) else None
            link = body.get("nextLink") if isinstance(body, dict) else None
            if not isinstance(value, list) or not all(isinstance(i, dict) for i in value) \
                    or not (link is None or isinstance(link, str)):
                raise RuntimeError("réponse d'ARM mal formée : pas la liste `value` d'une page")
            items += value
            url, params = link, None
            if not url:
                return items
        raise CutRead(f"plus de {ACTIVITY_PAGES} pages, la suite n'est pas lue")

    def _dossier_activity_window(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        return self._activity_of(values["vm"], start, end, made)

    def _dossier_vault_activity(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        """ENQ5a: the vault's log and its children's (protected items, policies, its security settings); a
        read of it (`…/read`) is no write: set aside."""
        return [r for r in self._activity_of(values["vault"], start, end, made)
                if not r["operation"].lower().endswith("/read")]

    def _dossier_vault_jobs(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        """ENQ5a: `backup_jobs`' listing and filter, on the enquiry's window."""
        return self._dossier_backup_jobs(values, start, end, made)

    def _activity_of(self, vm: str, start: datetime, end: datetime, made: Calls) -> list:
        """The activity log of one resource (an exact read) and of its children (the read of its group,
        filtered on the prefix of its id), between `start` and `end`."""
        url = f"{ARM}/subscriptions/{vm.split('/')[2]}/providers/Microsoft.Insights/eventtypes/management/values"
        events, prefix = {}, vm.rstrip("/").lower() + "/"
        for field, value in (("resourceUri", vm), ("resourceGroupName", _group_of(vm))):
            params = {"api-version": ACTIVITY_API, "$select": _SELECT,
                      "$filter": f"eventTimestamp ge '{_iso(start)}' and eventTimestamp le '{_iso(end)}' "
                                 f"and {field} eq '{value}'"}
            got = self._dossier_paged(url, params, made)
            for e in got:
                rid = str(e.get("resourceId") or e.get("resourceUri") or "").rstrip("/").lower()
                if field == "resourceUri" or rid.startswith(prefix):
                    events.setdefault(_event_key(e), e)
        if len(events) > ROWS_MAX:
            raise CutRead(f"plus de {ROWS_MAX} événements dans la fenêtre, la suite n'est pas gardée")
        return sorted((_event_row(e) for e in events.values()), key=lambda r: r["at"])

    def _dossier_backup_jobs(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        from glorfindel.response.ids import _parse_vm_resource_id
        rg, name = _parse_vm_resource_id(values["vm"])
        parts = values["vault"].split("/")
        want, rows, seen = f";{rg.lower()};{name.lower()}", [], 0
        listed = self._backup_client().backup_jobs.list(parts[-1], parts[4], filter=jobs_filter(start, end))
        for j in _items(listed, made):
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
        return sorted(rows, key=lambda r: r["start"])

    def _dossier_instance_view(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        from glorfindel.response.ids import _parse_vm_resource_id
        self._ensure_clients()
        rg, name = _parse_vm_resource_id(values["vm"])
        made.n += 1
        model = self._compute.virtual_machines.get(rg, name)
        os_type = str(getattr(getattr(getattr(model, "storage_profile", None), "os_disk", None), "os_type", "") or "")
        made.n += 1
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
                 "extensions": exts, "maintenance": maintenance}]

    def _dossier_host_metrics(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        made.n += 1
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
        return sorted(rows, key=lambda r: (r["metrique"], r["minute"]))

    def _dossier_resource_health(self, values: dict, start: datetime, end: datetime, made: Calls) -> list:
        made.n += 1
        body = self._arm_get(f"{ARM}{values['vm']}/providers/Microsoft.ResourceHealth/availabilityStatuses/current",
                             {"api-version": HEALTH_API})
        props = body.get("properties") if isinstance(body, dict) else None
        if not isinstance(props, dict) or not props.get("availabilityState"):
            raise RuntimeError("réponse d'ARM mal formée : pas d'availabilityState")
        return [{"etat": str(props.get("availabilityState"))[:40], "raison": str(props.get("reasonType") or "")[:80],
                 "resume": str(props.get("summary") or "")[:200],
                 "depuis": str(props.get("occuredTime") or props.get("occurredTime") or ""),
                 "dit_a": str(props.get("reportedTime") or "")}]


def jobs_filter(start: datetime, end: datetime) -> str:
    """ENQ5v: the `$filter` of the vault's listing, the read's window widened by JOBS_FILTER_MARGIN each side, in
    UTC (a naive time is UTC), `yyyy-MM-dd hh:mm:ss tt` written by hand: `%p` would follow the process's locale."""
    def at(t: datetime) -> str:
        u = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        return f"{u:%Y-%m-%d} {(u.hour + 11) % 12 + 1:02d}:{u:%M:%S} {'PM' if u.hour >= 12 else 'AM'}"
    return f"startTime eq '{at(start - JOBS_FILTER_MARGIN)}' and endTime eq '{at(end + JOBS_FILTER_MARGIN)}'"


def _items(listed, made: Calls):
    """The items of an SDK listing, each page counted as a call: a pager's pages (`by_page`), else the
    listing as one page."""
    pages = listed.by_page() if hasattr(listed, "by_page") else [listed]
    for page in pages:
        made.n += 1
        yield from page
