"""SDK1b (#1017): Azure Resource Manager as the pinned SDKs read it — never an object a test made up.

tests/unit/fake_azure.py hands the adapters `SimpleNamespace` objects: their fields texts, their enums
flattened. The SDKs (azure-mgmt-network, azure-mgmt-compute, azure-mgmt-recoveryservicesbackup, the
versions requirements/glorfindel.txt locks) hand them on otherwise: an enum known to them comes out an
enum (`SecurityRuleAccess.ALLOW`, whose `str()` is not « Allow » — the 06/10 bug, docs/azure.md), a value
they do not know a plain text, a field the body leaves out `None`, a date an aware `datetime`, a
polymorphic `properties` the class its discriminator names (`jobType`, `objectType`).

Here a reply is the body ARM sends (tests/unit/sdk_bodies/, one file per operation, or a body a test
gives), read by the SDKs' own clients: their pipeline, their deserialisation (each operation's
`_deserialize(Model, body)` — the pinned versions are generated from TypeSpec and have no
`Model.deserialize()` classmethod: this is the path a real reply takes), their pager, the errors they
raise (a 404 the SDK's `ResourceNotFoundError`), over azure-core's own `RequestsTransport`. Only the
socket is replaced: a `requests` adapter answers every request a client sends, by its path, and keeps
it (`Arm.requests`: method, path, query). It answers reads only: any other method is refused (405) and
kept (`Arm.writes`). No network, no credential: a token made up.

    arm = sdk_mgmt.Arm(*sdk_mgmt.captures())    # every body of tests/unit/sdk_bodies/
    c = arm.connector(monkeypatch)              # the real AzureConnector, its clients the SDKs'
    arm.writes                                  # what was not a GET: [] for a reader

`offline(monkeypatch)` refuses every socket: a client built on its own transport fails instead of
reaching Azure (the tests of SDK1b call it first).

ARM's names are case-insensitive: so is the path a body is served at (the fake does not play
`recovery_points.list`'s case-sensitive prefix, docs/azure.md). Every identifier is made up, in the
forms scripts/sdk_capture.py writes (repository public).
"""
from __future__ import annotations

import copy
import io
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import requests
from requests.adapters import HTTPAdapter

BODIES = Path(__file__).resolve().parent / "sdk_bodies"
# The identifiers of the bodies — the forms scripts/sdk_capture.py gives the real ones.
SUB = "00000000-0000-4000-8000-000000000001"
RG = "rg-example-01"
ARM = "https://management.azure.com"


def offline(monkeypatch) -> None:
    """No socket opens, no name is resolved: the in-memory ARM needs neither, anything else would
    be the network — even to this machine. On top of the suite's own guard (tests/unit/network_guard.py:
    nothing leaves the machine in any test)."""
    import socket

    def refuse(*_a, **_kw):
        raise ConnectionRefusedError("tests/unit/sdk_mgmt.py: the network is refused in these tests")
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, refuse)
    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, refuse)


def captures() -> list[dict]:
    """Every capture of tests/unit/sdk_bodies/ (each a fresh copy: a test may change it)."""
    return [load(p.stem) for p in sorted(BODIES.glob("*.json"))]


def load(name: str) -> dict:
    """One capture by its file's name (its operation), a fresh copy."""
    return json.loads((BODIES / f"{name}.json").read_text())


def body(capture: dict, page: int = 0) -> dict:
    """The body of one response of a capture (its first page by default)."""
    return capture["responses"][page]["body"]


def items(capture: dict) -> list[dict]:
    """The items of a list's first page (`value`)."""
    return body(capture)["value"]


def named(capture: dict, name: str) -> dict:
    """The item of a list's first page by its name (ARM's, case-insensitive)."""
    return next(i for i in items(capture) if str(i.get("name", "")).lower() == name.lower())


def _key(url: str) -> str:
    """Where a response is served: its path, decoded and lowercase; a page after the first by its
    skip token too."""
    parts = urlsplit(url)
    path = unquote(parts.path).rstrip("/").lower()
    query = {k.lower(): v for k, v in parse_qs(parts.query).items()}
    token = (query.get("$skiptoken") or [""])[0]
    return f"{path}|{token}" if token else path


class _Credential:
    """A token made up: the SDKs' bearer policy asks for one, nothing reads it."""

    def get_token(self, *_scopes, **_kw):
        from azure.core.credentials import AccessToken
        return AccessToken("token-made-up", int(time.time()) + 3600)

    def get_token_info(self, *_scopes, **_kw):
        from azure.core.credentials import AccessTokenInfo
        return AccessTokenInfo("token-made-up", int(time.time()) + 3600)


class _Adapter(HTTPAdapter):
    """The socket: every request a client sends is kept and answered, never sent."""

    def __init__(self, arm: "Arm"):
        super().__init__(max_retries=0)
        self.arm = arm

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        from urllib3.response import HTTPResponse
        parts = urlsplit(request.url)
        self.arm.requests.append({"method": request.method, "path": unquote(parts.path), "query": parts.query})
        status, payload = self.arm.answer(request.method, request.url)
        content = json.dumps(payload).encode("utf-8")
        raw = HTTPResponse(body=io.BytesIO(content), status=status, preload_content=False,
                           reason="OK" if status == 200 else "Error",
                           headers={"Content-Type": "application/json; charset=utf-8",
                                    "Content-Length": str(len(content))})
        return self.build_response(request, raw)


class Arm:
    """ARM behind the pinned SDKs' own clients: each capture's responses served at their paths;
    a path served nothing is a 404 as ARM writes one; any method but GET a 405, kept apart."""

    def __init__(self, *captures: dict):
        self.routes: dict[str, tuple[int, dict]] = {}
        self.first: dict[str, list[tuple[int, dict]]] = {}     # answered once each, before the route
        self.requests: list[dict] = []
        for capture in captures:
            self.add(capture)

    def add(self, capture: dict) -> "Arm":
        for r in capture["responses"]:
            self.routes[_key(r["url"])] = (int(r.get("status", 200)), r["body"])
        return self

    def serve(self, path: str, payload: dict, status: int = 200) -> "Arm":
        """One more response, at `path` (an ARM id, or a URL)."""
        self.routes[_key(path)] = (status, payload)
        return self

    def once(self, path: str, payload: dict, status: int) -> "Arm":
        """A response given once at `path`, before what is served there (a 429 the SDK retries)."""
        self.first.setdefault(_key(path), []).append((status, payload))
        return self

    def answer(self, method: str, url: str) -> tuple[int, dict]:
        if method.upper() != "GET":
            return 405, {"error": {"code": "MethodNotAllowed",
                                   "message": "the in-memory ARM of the tests answers reads only"}}
        key = _key(url)
        if self.first.get(key):
            return self.first[key].pop(0)
        if key in self.routes:
            status, payload = self.routes[key]
            return status, copy.deepcopy(payload)
        return 404, {"error": {"code": "ResourceNotFound",
                               "message": f"The Resource '{unquote(urlsplit(url).path)}' was not found."}}

    @property
    def writes(self) -> list[dict]:
        """Every request that was not a read."""
        return [r for r in self.requests if r["method"].upper() != "GET"]

    def sent(self, fragment: str) -> list[dict]:
        """The requests whose path holds `fragment` (case-insensitive)."""
        return [r for r in self.requests if fragment.lower() in r["path"].lower()]

    def session(self) -> requests.Session:
        """A `requests` session whose socket is this ARM (scripts/sdk_capture.py's tests give it)."""
        session = requests.Session()
        for prefix in ("https://", "http://"):
            session.mount(prefix, _Adapter(self))
        return session

    def _transport(self):
        from azure.core.pipeline.transport import RequestsTransport
        return RequestsTransport(session=self.session(), session_owner=False)

    def network(self, subscription: str = SUB):
        from azure.mgmt.network import NetworkManagementClient
        return NetworkManagementClient(_Credential(), subscription, transport=self._transport())

    def compute(self, subscription: str = SUB):
        from azure.mgmt.compute import ComputeManagementClient
        return ComputeManagementClient(_Credential(), subscription, transport=self._transport())

    def backup(self, subscription: str = SUB):
        # The class itself, from its module: `connector` puts this ARM's in the package's place.
        from azure.mgmt.recoveryservicesbackup._client import RecoveryServicesBackupClient
        return RecoveryServicesBackupClient(_Credential(), subscription, transport=self._transport())

    def connector(self, monkeypatch, read_only: bool = True, subscription: str = SUB):
        """The real AzureConnector, its clients the SDKs' over this ARM — the vault's client the
        adapters build for themselves (backup.py, restore.py) too, through `monkeypatch`: a client
        left to its own transport would reach the network."""
        from glorfindel.actions import AzureConnector
        c = AzureConnector(dry_run=False, read_only=read_only)
        c._credential = _Credential()
        c._subscription_id = subscription
        c._compute = self.compute(subscription)
        c._network = self.network(subscription)
        c._backup = self.backup(subscription)
        monkeypatch.setattr("azure.mgmt.recoveryservicesbackup.RecoveryServicesBackupClient",
                            lambda *_a, **_kw: self.backup(subscription))
        return c
