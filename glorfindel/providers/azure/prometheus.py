"""An Azure Monitor workspace, read in PromQL, read only (PIO1, #1258; `docs/design/enquete-raisonnee.md`
§4.4, §9.7, proposal 1) — the one place Eregion reads the guest's metrics per process: who writes under
Linux (`process.disk.io`, the agent's OTel metric, sent by the agent through the DCR of
`infra/terraform/process_io.tf`).

**Read only by construction**: one POST to the workspace's `/api/v1/query` — PromQL's instant query, a
read: the form the API documents for a long query (Learn, « Query Prometheus metrics using the API and
PromQL », `/api/v1/query`, GET or POST with `application/x-www-form-urlencoded`). Nothing else is written
here, and tests/unit/test_process_io.py keeps it so. Only the workspace's own host is called
(`https://<workspace>.<region>.prometheus.monitor.azure.com`, `ENDPOINT`), never a redirection
(`allow_redirects=False`: a 3xx is an error). The identity is the process's (`DefaultAzureCredential`: the
managed identity of Imladris, `az login` at the maintainer's capture), for the audience
`https://prometheus.monitor.azure.com` (`SCOPE`), with no new right: the Reader the watch already has on
the bench's group, the operator's Owner — if `*/read` is enough for PromQL (built-in reading roles carry no
data action), which the measure at the bench settles; a 403 says `PIO_DROIT`.

**Its budget**: `read_budget.PROMETHEUS` (`GLORFINDEL_PROM_BUDGET_PER_MIN`, 30 by default), taken before the
query; refused, the read is `refusee`, said — never run past it.

**Its refusals are said, never taken for « nothing »** (`process_write_io`, the states of
`glorfindel/enquiry/catalog.py`): no token for the process's identity, a 401 or 403 (the right absent), a 404
or a host that does not answer (the workspace absent or unreachable), no connection or no answer in time (a
delay), a 429 or a 5xx, an answer that is no JSON, not `success`, not a vector, or whose value is no finite
number — each `echec`, with why, each its own. No workspace configured, or no series of the
metric for the VM, is `sans_objet`: the collection is not set or does not arrive. `vide` only when the VM's
series answered and none wrote in the window.

**The process's name is forged by the guest** (it comes from /proc/[pid]/status, which the process chooses):
the rows carry it as the guest wrote it, truncated, its control characters dropped; no hypothesis that
relaxes leans on it (§4.4). Its author, `invité, forgeable`, is the read's.

**Not measured** (`docs/operations.md`, « Qui écrit sous Linux, au banc (PIO1) »): the series' name and its
labels as the workspace stores them (Learn writes the dotted, quoted form only), that the bench's Linux agent
collects the metric, its ingestion latency. Neither `investigate` nor `decide` reads it before ENQ5b: the
capture at the bench only (`scripts/capture_enquete.py --prom-endpoint`).
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from glorfindel import kql, read_budget
from glorfindel.enquiry import catalog

SCOPE = "https://prometheus.monitor.azure.com/.default"
ENDPOINT = re.compile(r"^https://[a-z0-9][a-z0-9-]{0,62}\.[a-z0-9]{2,40}\.prometheus\.monitor\.azure\.com$")
# Connection in 5 s, an answer in 15 s: a read of the capture, or of an enquiry later (ENQ5b).
TIMEOUT_S = (5, 15)
NAME_MAX = 64
WHO = "enquete"
# What a resource id may hold once `kql.resource_id` passed it; anything else is refused before the PromQL.
_ID_CHARS = re.compile(r"^[A-Za-z0-9._()/-]+$")
_RE2_META = re.compile(r"([.()\\])")


class Illisible(Exception):
    """The workspace could not be read. `kind`: `identity` (no token for the process's identity), `right`
    (401, 403), `absent` (404, the host unreachable), `delay` (no connection or no answer in time), `error`
    (429, 5xx, 3xx, an answer unreadable)."""

    def __init__(self, why: str, kind: str = "error", *, status: int = 0):
        super().__init__(why)
        self.kind, self.status = kind, status


class PromReader:
    """PromQL's instant query on one Azure Monitor workspace, with the process's identity."""

    def __init__(self, endpoint: str, credential=None, session=None, timeout=TIMEOUT_S):
        endpoint = (endpoint or "").strip().rstrip("/").lower()
        if not ENDPOINT.fullmatch(endpoint):
            raise ValueError("not the query endpoint of an Azure Monitor workspace "
                             "(https://<workspace>.<region>.prometheus.monitor.azure.com)")
        self.endpoint = endpoint
        self._credential, self._session, self._timeout = credential, session, timeout

    def _token(self) -> str:
        try:
            if self._credential is None:
                from azure.identity import DefaultAzureCredential
                self._credential = DefaultAzureCredential()
            return self._credential.get_token(SCOPE).token
        except Exception as exc:
            raise Illisible(f"no token for the workspace ({type(exc).__name__})", "identity") from None

    def query(self, promql: str, at: datetime) -> list:
        """The vector PromQL answers at `at`: a list of `{"metric": {…}, "value": [t, "v"]}`. Raises Illisible."""
        import requests
        session = self._session or requests
        try:
            r = session.post(self.endpoint + "/api/v1/query",
                             headers={"Authorization": f"Bearer {self._token()}"},
                             data={"query": promql, "time": f"{at.timestamp():.3f}"},
                             timeout=self._timeout, allow_redirects=False)
        except requests.Timeout:
            raise Illisible(f"no answer from the workspace in {self._timeout[1]} s", "delay") from None
        except requests.ConnectionError:
            raise Illisible("the workspace's host is unreachable", "absent") from None
        except requests.RequestException as exc:
            raise Illisible(f"the workspace: {type(exc).__name__}", "error") from None
        status = getattr(r, "status_code", 0)
        if status in (401, 403):
            raise Illisible(f"no right on the workspace ({status})", "right", status=status)
        if status == 404:
            raise Illisible("the workspace answered 404", "absent", status=status)
        if status != 200:
            raise Illisible(f"the workspace answered {status}", "error", status=status)
        try:
            body = r.json()
        except Exception:
            raise Illisible("the workspace's answer is no JSON", "error") from None
        data = body.get("data") if isinstance(body, dict) else None
        if (not isinstance(body, dict) or body.get("status") != "success" or not isinstance(data, dict)
                or data.get("resultType") != "vector" or not isinstance(data.get("result"), list)):
            raise Illisible("the workspace's answer is not a PromQL vector", "error")
        return data["result"]


def regex_literal(vm: str) -> str:
    """The VM's resource id as a PromQL string literal holding a case-insensitive, anchored RE2 regex: its
    `.`, `(`, `)` escaped, each backslash doubled for the string. Raises kql.UnsafeValue."""
    vm = kql.resource_id(vm)
    if not _ID_CHARS.fullmatch(vm):
        raise kql.UnsafeValue("a resource id with a character PromQL would read")
    return '"(?i)' + _RE2_META.sub(r"\\\\\1", vm) + '"'


def texte(vm: str, debut: datetime, fin: datetime, top: int = catalog.PROCESS_IO_TOP) -> str:
    """`process_write_io`'s PromQL for `vm` over [debut, fin] (run at `fin`): its values from the code only."""
    duree = max(60, int((fin - debut).total_seconds()))
    top = max(1, min(int(top), 10))
    return catalog.A_MESURER["process_write_io"].query.format(top=top, vm=regex_literal(vm), duree=duree)


def _name(metric: dict) -> str:
    """The executable's name as the guest wrote it — the label read whatever its case —, its control
    characters dropped, NAME_MAX at most; none: `?`."""
    raw = next((v for k, v in metric.items() if isinstance(k, str) and k.lower() == catalog.PROCESS_IO_NAME),
               "") if isinstance(metric, dict) else ""
    text = "".join(ch for ch in str(raw) if unicodedata.category(ch)[0] != "C")[:NAME_MAX]
    return text or "?"


def process_write_io(vm, at: datetime, *, reader: PromReader | None, now: datetime | None = None,
                     top: int = catalog.PROCESS_IO_TOP, budget=None) -> catalog.Reading:
    """Who wrote on `vm`'s disk over the read's window anchored at `at` (T − 5 min → T, its end never past
    `now`): the bytes written by executable, the `top` first, as a `catalog.Reading` — its state always said."""
    read = catalog.A_MESURER["process_write_io"]
    now = now or datetime.now(timezone.utc)
    try:
        query_vm = kql.resource_id(vm)
        regex_literal(query_vm)
    except kql.UnsafeValue as exc:
        return catalog.Reading(read.id, catalog.REFUSEE, why=catalog.PIO_REFUSEE.format(exc))
    if reader is None:
        return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.PIO_SANS_ESPACE)
    debut, fin = catalog.window(read, at)
    fin = min(fin, now)
    if not (budget or read_budget.PROMETHEUS).take(1, WHO):
        return catalog.Reading(read.id, catalog.REFUSEE, why=catalog.PIO_BUDGET)
    try:
        result = reader.query(texte(query_vm, debut, fin, top), fin)
    except Illisible as exc:
        why = {"identity": catalog.PIO_IDENTITE, "right": catalog.PIO_DROIT, "absent": catalog.PIO_ABSENT,
               "delay": catalog.PIO_DELAI}.get(exc.kind, catalog.PIO_ILLISIBLE)
        return catalog.Reading(read.id, catalog.ECHEC, why=f"{why} ({exc})")
    rows = []
    for item in result:
        value = item.get("value") if isinstance(item, dict) else None
        try:
            octets = float(value[1])
        except (TypeError, ValueError, IndexError, KeyError):
            octets = math.nan
        if not math.isfinite(octets):
            return catalog.Reading(read.id, catalog.ECHEC, why=catalog.PIO_SANS_NOMBRE)
        if octets > 0:
            rows.append({"Executable": _name(item.get("metric")), "EcritMo": round(octets / 1e6, 1),
                         "Octets": int(octets)})
    rows.sort(key=lambda r: -r["Octets"])
    if rows:
        return catalog.Reading(read.id, catalog.LIGNES, rows=rows)
    if now < fin + timedelta(seconds=read.latency_s):
        return catalog.Reading(read.id, catalog.EN_ATTENTE,
                               why=catalog.PIO_LATENCE.format(read.latency_s))
    if not result:
        return catalog.Reading(read.id, catalog.SANS_OBJET, why=catalog.PIO_SANS_SERIE)
    return catalog.Reading(read.id, catalog.VIDE)
