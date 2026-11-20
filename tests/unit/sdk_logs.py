"""SDK1a (#992): a reply of Log Analytics as the pinned SDK reads it — never a Python list a test
made up.

A test that hands Glorfindel's readers the rows of `kql_subset` (or any dict) passes them Python
values: a `dynamic` column a list, a date a `datetime` or a text, as the test wrote it. The SDK
(`azure-monitor-query`, the version requirements/glorfindel.txt locks) hands them on otherwise: a
`dynamic` column arrives as its JSON text — the body of the API carries it so (measured on
Imladris, 20/11, SLF1b) and `native_col_type` converts only `datetime`, `timespan` and `guid` —, a
`datetime` column as a `datetime` (its zone the SDK's own UTC, not `timezone.utc`). SLF1 passed
its tests and did nothing in production that way.

Here a reply is built as the service sends it — one table or more, each column typed (`string`,
`int`, `long`, `real`, `datetime`, `dynamic`, `bool`, `guid`, `timespan`), each value on the
wire —, and read by the SDK's own `LogsQueryClient`: its pipeline, its deserialisation, its
`LogsQueryResult` (or `LogsQueryPartialResult`, or the `HttpResponseError` it raises), over
azure-core's own `RequestsTransport`. Only the socket is replaced: a `requests` adapter answers
every request the client sends, and keeps it (`Workspace.requests`: the query and the timespan as
sent). No network, no credential: a token made up.

    ws = sdk_logs.Workspace(sdk_logs.kql(lines, now=NOW))   # a query run as written over lines
    rows = ws.detector().run_query(query)                    # the real AzureMonitorDetector
    ws.serve(monkeypatch)                                    # every detector of the process

Every identifier is made up (repository public).
"""
from __future__ import annotations

import io
import json
import time
from datetime import datetime, timezone
from typing import Callable

import requests
from requests.adapters import HTTPAdapter

from . import kql_subset

# The types Log Analytics gives a column (its API's `columns[].type`).
TYPES = ("string", "int", "long", "real", "datetime", "dynamic", "bool", "guid", "timespan")
# What a value of a row the test wrote is, as a column of the reply.
_PYTHON = ((bool, "bool"), (int, "long"), (float, "real"), (datetime, "datetime"),
           (list, "dynamic"), (dict, "dynamic"))


def column_type(values) -> str:
    """The type of a column whose values are `values`: the first that is not None says it;
    none, a `string`."""
    for value in values:
        if value is None:
            continue
        return next((t for kind, t in _PYTHON if isinstance(value, kind)), "string")
    return "string"


def wire(value, ctype: str):
    """A value as the API's body carries it: a `dynamic` one as its JSON text (a text given is
    sent as it is), a `datetime` in ISO 8601, UTC, `Z`; null as null."""
    if value is None:
        return None
    if ctype == "dynamic" and not isinstance(value, str):
        return json.dumps(value)
    if ctype == "datetime" and isinstance(value, datetime):
        at = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return value


def table(rows: list[dict], types: dict[str, str] | None = None, name: str = "PrimaryResult",
          columns: list[str] | None = None) -> dict:
    """One table of the reply: its columns (in the rows' order, or `columns`), each typed by
    `types` or by its values (`column_type`), its rows on the wire."""
    types = types or {}
    if columns is None:
        columns = list(dict.fromkeys(c for r in rows for c in r))
    typed = {c: types.get(c) or column_type(r.get(c) for r in rows) for c in columns}
    unknown = {c: t for c, t in typed.items() if t not in TYPES}
    if unknown:
        raise ValueError(f"not a type of Log Analytics: {unknown}")
    return {"name": name, "columns": [{"name": c, "type": typed[c]} for c in columns],
            "rows": [[wire(r.get(c), typed[c]) for c in columns] for r in rows]}


def body(*tables: dict) -> dict:
    """The body of a reply that succeeded: its tables."""
    return {"tables": list(tables)}


def body_of(rows: list[dict], types: dict[str, str] | None = None, **kw) -> dict:
    """The body of a reply of one table, `rows`."""
    return body(table(rows, types, **kw))


def partial(reply: dict, message: str = "There were some errors when processing your query.") -> dict:
    """The same reply, partial: the API's body carries its tables and an error beside them."""
    return {**reply, "error": {"code": "PartialError", "message": message,
                               "details": [{"code": "EngineError", "message": "Query exceeded limits"}]}}


def failure(status: int, code: str, message: str, inner: dict | None = None) -> tuple[int, dict]:
    """A reply refused (`status`), its body as the API writes one: code, message, inner error."""
    error = {"code": code, "message": message}
    if inner:
        error["innererror"] = inner
    return status, {"error": error}


def kql(lines: list[dict], now: datetime | None = None, types: dict[str, str] | None = None,
        mangle: Callable[[dict], None] | None = None):
    """An answer: the query run as written over `lines` (tests/unit/kql_subset.py), its rows the
    body of the reply; `mangle(body)`: the body changed before it is sent."""
    def answer(query: str, _timespan) -> dict:
        reply = body_of(kql_subset.run(query, lines, now=now), types)
        if mangle is not None:
            mangle(reply)
        return reply
    return answer


def constant(reply):
    """An answer: the same reply to every query (a body, or a `(status, body)`)."""
    return lambda _query, _timespan: reply


class _Credential:
    """A token made up: the SDK's bearer policy asks for one, nothing reads it."""

    def get_token(self, *_scopes, **_kw):
        from azure.core.credentials import AccessToken
        return AccessToken("token-made-up", int(time.time()) + 3600)


class _Adapter(HTTPAdapter):
    """The socket: every request the client sends is kept and answered, never sent — the
    answer an HTTP response in memory, made a `requests` response by requests' own adapter."""

    def __init__(self, workspace: "Workspace"):
        super().__init__(max_retries=0)
        self.workspace = workspace

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        from urllib3.response import HTTPResponse
        sent = json.loads(request.body or b"{}")
        self.workspace.requests.append({"url": request.url, **sent})
        reply = self.workspace.answer(sent.get("query", ""), sent.get("timespan"))
        status, payload = reply if isinstance(reply, tuple) else (200, reply)
        content = json.dumps(payload).encode("utf-8")
        raw = HTTPResponse(body=io.BytesIO(content), status=status, preload_content=False,
                           reason="OK" if status == 200 else "Error",
                           headers={"Content-Type": "application/json; charset=utf-8",
                                    "Content-Length": str(len(content))})
        return self.build_response(request, raw)


class Workspace:
    """A Log Analytics workspace behind the pinned SDK's own client. `answer(query, timespan)` is
    the reply's body (or `(status, body)`); `requests` what the client sent, in order."""

    def __init__(self, answer):
        self.answer = answer
        self.requests: list[dict] = []

    def client(self):
        """The SDK's `LogsQueryClient`, as `AzureMonitorDetector._logs_client` builds it, over
        azure-core's `RequestsTransport` — its session's socket this workspace."""
        from azure.core.pipeline.transport import RequestsTransport
        from azure.monitor.query import LogsQueryClient
        session = requests.Session()
        for prefix in ("https://", "http://"):
            session.mount(prefix, _Adapter(self))
        return LogsQueryClient(_Credential(), transport=RequestsTransport(session=session))

    def detector(self, cls=None, workspace_id: str = "ws-test", **kw):
        """The real detector (`AzureMonitorDetector`, or `cls`), its client this workspace's."""
        if cls is None:
            from glorfindel.providers.azure.monitor import AzureMonitorDetector as cls
        det = cls(workspace_id, **kw)
        client = self.client()
        det._logs_client = lambda: client
        return det

    def serve(self, monkeypatch):
        """Every detector of the process (`detector_for`, its subclasses) reads this workspace."""
        from glorfindel.providers.azure.monitor import AzureMonitorDetector
        client = self.client()
        monkeypatch.setattr(AzureMonitorDetector, "_logs_client", lambda self: client)
        return self


def through_sdk(rows: list[dict], types: dict[str, str] | None = None, query: str = "Rows") -> list[dict]:
    """`rows` as `AzureMonitorDetector.run_query` hands them on, once the SDK has read them."""
    return Workspace(constant(body_of(rows, types))).detector().run_query(query)
