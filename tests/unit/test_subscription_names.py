"""SUBN1 (#1190) : la watch lit le nom lisible de chaque abonnement qu'elle voit, pour la console.

Les abonnements vus (le sien, ceux des VM découvertes), leur `displayName` lu sur ARM
(glorfindel/providers/azure/subscriptions.py), écrits dans `~/.glorfindel/subscriptions.json`
(glorfindel/subscription_names.py) et servis par `/api/watch/status` sous une clé masquée
(eregion_console/watch_fields.py). Aucun appel à Azure : un faux lecteur (`_Reader`), un faux `get`
d'ARM (`_Arm`), une horloge dans la main du test.
"""
from __future__ import annotations

import io
import json
import threading
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from glorfindel import discovery
from glorfindel import subscription_names as sn
from glorfindel.providers.azure import subscriptions as arm
from glorfindel.terminal import GlorfindelConsole

from .console_client import console

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc).timestamp()
OWN = "aaaaaaaa-1111-2222-3333-444444444444"
OTHER = "BBBBBBBB-5555-6666-7777-888888888888"          # en majuscules dans un resource_id : lu en minuscules
THIRD = "cccccccc-9999-0000-1111-222222222222"


def _vm(sub: str, name: str = "vm1") -> SimpleNamespace:
    return SimpleNamespace(resource_id=f"/subscriptions/{sub}/resourceGroups/rg/providers/"
                                       f"Microsoft.Compute/virtualMachines/{name}")


class _Clock:
    def __init__(self, t=NOW):
        self.t = t

    def __call__(self):
        return self.t


class _HttpError(Exception):
    def __init__(self, status, text):
        super().__init__(text)
        self.status_code = status


class _Reader:
    """Un faux lecteur : par abonnement, son nom ou l'exception qu'il lève ; chaque lecture gardée."""

    def __init__(self, names: dict):
        self.names = names
        self.calls: list[str] = []

    def __call__(self, key):
        self.calls.append(key)
        value = self.names.get(key, "Unnamed")
        if isinstance(value, BaseException):
            raise value
        return value


def _names(reader, tmp_path, assets=(), env=None, clock=None, said=None):
    vms = list(assets)
    return sn.SubscriptionNames(reader=reader, assets=lambda: vms, environ=env if env is not None else
                                {"AZURE_SUBSCRIPTION_ID": OWN}, clock=clock or _Clock(),
                                path=tmp_path / "subscriptions.json",
                                say=(said.append if said is not None else None)), vms


# ── 1. Les abonnements vus ───────────────────────────────────────────────────────────────────────

def test_the_subscriptions_seen_are_its_own_and_those_of_the_discovered_vms_once_each():
    assets = [_vm(OTHER), _vm(OWN.upper(), "vm2"), _vm(OTHER, "vm3"), SimpleNamespace(resource_id="")]
    assert sn.seen({"AZURE_SUBSCRIPTION_ID": OWN}, assets) == [OWN, OTHER.lower()]
    assert sn.seen({}, [_vm(THIRD)]) == [THIRD]                              # sans variable : les VM seules


def test_an_id_that_is_not_a_guid_is_never_taken():
    """M7661 : un `resource_id` vient de Log Analytics — un segment qui n'est pas un GUID n'est jamais lu
    (jamais collé dans l'URL d'ARM)."""
    bad = [SimpleNamespace(resource_id="/subscriptions/x/../../tenants/resourceGroups/rg"),
           SimpleNamespace(resource_id="/subscriptions/s/resourceGroups/rg"),
           SimpleNamespace(resource_id=f"/subscriptions/{OTHER}?x=1/resourceGroups/rg")]
    assert sn.seen({"AZURE_SUBSCRIPTION_ID": "not-a-guid"}, bad) == []


def test_the_registry_of_the_discovery_gives_the_vms_by_default(monkeypatch, tmp_path):
    reg = discovery.AssetRegistry(tmp_path / "assets.json")
    reg.update([discovery.DiscoveredAsset(name="vm9", resource_id=_vm(THIRD).resource_id,
                                          monitoring_backend="la", last_seen="2026-11-25T12:00:00+00:00")])
    monkeypatch.setattr(discovery, "_registry", reg)
    assert sn.seen({"AZURE_SUBSCRIPTION_ID": OWN}) == [OWN, THIRD]


# ── 2. La lecture ────────────────────────────────────────────────────────────────────────────────

def test_a_name_read_a_refusal_and_a_network_error(tmp_path):
    """M7662 : une lecture en échec est une erreur, jamais un nom ; M7663 : son texte masqué avant d'être
    coupé (une URL, un GUID)."""
    net = ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url "
                          f"https://management.azure.com/subscriptions/{THIRD}?api-version=2022-12-01 "
                          f"(tenant {OWN.replace('-', '')})")
    r = _Reader({OWN: "Production", OTHER.lower(): _HttpError(403, "AuthorizationFailed"), THIRD: net})
    names, _ = _names(r, tmp_path, [_vm(OTHER), _vm(THIRD)])
    doc = names.pass_once()
    got = {k: {"name": e["name"], "error": e["error"]} for k, e in doc["names"].items()}
    assert got[OWN] == {"name": "Production", "error": None}
    assert got[OTHER.lower()] == {"name": None, "error": "HTTP 403 — AuthorizationFailed"}
    assert got[THIRD]["name"] is None and got[THIRD]["error"].startswith("ConnectionError — ")
    assert "<url>" in got[THIRD]["error"] and "<id>" in got[THIRD]["error"]
    assert THIRD not in got[THIRD]["error"] and OWN.replace("-", "") not in got[THIRD]["error"]
    assert "management.azure.com" not in got[THIRD]["error"]


def test_an_answer_without_a_name_is_an_error():
    assert sn.read_one(lambda key: "\x00\x07  ", OWN) == {"name": None, "error": sn.NO_NAME}
    assert sn.read_one(lambda key: 42, OWN) == {"name": None, "error": sn.NO_NAME}


@pytest.mark.parametrize("raw, expected", [
    ("Production", "Production"),
    ("Prod\nInjected\r\tline", "ProdInjectedline"),                          # contrôle : retiré
    ("Prod‮evil​ x\x1b[31m", "Prodevilx[31m"),                 # format, séparateur, échappement
    ("  Équipe données  ", "Équipe données"),
    ("x" * 200, "x" * 64),
    (f"sub {OWN} named by its id", "sub <id> named by its id"),
    ("\x00\x01", None),
    (None, None),
])
def test_the_name_is_cleaned_and_cut(raw, expected):
    """M7664 : les caractères de contrôle et de format retirés ; M7665 : coupé à 64."""
    assert sn.clean_name(raw) == expected


def test_the_provider_reads_the_display_name_with_the_watch_identity_and_says_no_message_of_arm():
    class _Answer:
        def __init__(self, status, body):
            self.status_code, self.ok, self._body = status, 200 <= status < 300, body

        def json(self):
            if isinstance(self._body, BaseException):
                raise self._body
            return self._body

    class _Arm:
        def __init__(self, answer):
            self.answer, self.calls = answer, []

        def __call__(self, url, **kw):
            self.calls.append((url, kw))
            return self.answer

    cred = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token=f"tok-{scope}"))
    ok = _Arm(_Answer(200, {"displayName": "Production", "subscriptionId": OWN}))
    assert arm.SubscriptionReader(credential=cred, get=ok)(OWN) == "Production"
    url, kw = ok.calls[0]
    assert url == f"https://management.azure.com/subscriptions/{OWN}"
    assert kw["params"] == {"api-version": arm.API_VERSION}
    assert kw["headers"] == {"Authorization": "Bearer tok-https://management.azure.com/.default"}
    assert kw["timeout"] == (10, 60)
    denied = _Arm(_Answer(403, {"error": {"code": "AuthorizationFailed", "message": f"The client {OWN} …"}}))
    with pytest.raises(arm.ArmReadError) as err:
        arm.SubscriptionReader(credential=cred, get=denied)(OWN)
    assert err.value.status_code == 403 and str(err.value) == "AuthorizationFailed"
    with pytest.raises(arm.ArmReadError):
        arm.SubscriptionReader(credential=cred, get=_Arm(_Answer(404, ValueError("no json"))))(OWN)
    with pytest.raises(RuntimeError, match="no displayName"):
        arm.SubscriptionReader(credential=cred, get=_Arm(_Answer(200, ["x"])))(OWN)


def test_the_provider_refuses_an_id_that_is_not_a_guid_before_any_call():
    """La garde de l'adaptateur, derrière celle de `seen` (M7661) : jamais un texte du dehors collé dans
    l'URL d'ARM."""
    calls = []
    reader = arm.SubscriptionReader(credential=object(), get=lambda *a, **k: calls.append(a))
    for bad in ("s", f"{OWN}/../x", "", None):
        with pytest.raises(ValueError):
            reader(bad)
    assert calls == []


# ── 3. Le rythme ────────────────────────────────────────────────────────────────────────────────

def test_all_are_read_at_the_start_then_every_6_hours_and_a_new_one_at_once(tmp_path):
    """M7667 : pas toutes les minutes — au démarrage, toutes les 6 h, et un abonnement qui apparaît."""
    clock = _Clock()
    r = _Reader({OWN: "Own", OTHER.lower(): "Other", THIRD: "Third"})
    names, vms = _names(r, tmp_path, [_vm(OTHER)], clock=clock)
    assert names.has_work() and names.pass_once() and sorted(r.calls) == sorted([OWN, OTHER.lower()])
    clock.t += 60
    assert not names.has_work() and names.pass_once() is None and len(r.calls) == 2
    vms.append(_vm(THIRD))                                                   # un nouvel abonnement
    assert names.has_work()
    names.pass_once()
    assert r.calls[2:] == [THIRD]
    clock.t = NOW + sn.EVERY_S - 1
    assert not names.has_work()
    clock.t = NOW + sn.EVERY_S
    names.pass_once()
    assert sorted(r.calls[3:]) == sorted([OWN, OTHER.lower(), THIRD])        # la tournée des 6 h


def test_a_restart_reads_all_again_and_serves_what_it_had_until_then(tmp_path):
    r = _Reader({OWN: "Own"})
    names, _ = _names(r, tmp_path)
    names.pass_once()
    again, _ = _names(r, tmp_path)
    assert again.has_work()                                                  # le démarrage relit tout
    assert sn.console_field(tmp_path / "subscriptions.json")["subscriptions"]["names"] == {
        sn.mask(OWN): {"name": "Own", "error": None}}


def test_a_pass_reads_at_most_per_pass_the_rest_not_yet_read(tmp_path, monkeypatch):
    """Au plus PER_PASS lectures par passe ; un abonnement pas encore lu est servi sans nom ni erreur."""
    monkeypatch.setattr(sn, "PER_PASS", 2)
    subs = [f"{i:08x}-0000-0000-0000-000000000000" for i in range(1, 4)]
    r = _Reader({})
    names, _ = _names(r, tmp_path, [_vm(s) for s in subs], env={})
    doc = names.pass_once()
    assert r.calls == subs[:2]
    assert doc["names"][subs[2]] == {"name": None, "error": None, "read_at": None}
    field = sn.console_field(tmp_path / "subscriptions.json")["subscriptions"]["names"]
    assert field[sn.mask(subs[2])] == {"name": None, "error": None}
    names.pass_once()
    assert r.calls == subs


def test_a_subscription_no_longer_seen_leaves_the_file(tmp_path):
    r = _Reader({})
    names, vms = _names(r, tmp_path, [_vm(OTHER)])
    names.pass_once()
    vms.clear()
    assert names.has_work()
    doc = names.pass_once()
    assert list(doc["names"]) == [OWN] and len(r.calls) == 2


def test_the_watch_log_says_counts_never_a_name_nor_an_error(tmp_path):
    said: list[str] = []
    r = _Reader({OWN: "Secret Project Name", OTHER.lower(): _HttpError(403, "AuthorizationFailed")})
    names, vms = _names(r, tmp_path, [_vm(OTHER)], said=said)
    names.pass_once()
    assert said == ["subscription names: 1 of 2 read"]
    vms.append(_vm(OTHER, "vm2"))                                            # rien de neuf : rien de dit
    names._round_at = None
    names._read.clear()
    names.pass_once()
    assert said == ["subscription names: 1 of 2 read"]


# ── 4. Le dry-run, la watch ──────────────────────────────────────────────────────────────────────

class _Connector:
    read_only = False

    def __init__(self, dry_run=False):
        self.dry_run = dry_run


def _housekeeping(monkeypatch, dry_run=False):
    from glorfindel.watch.housekeeping import Housekeeping
    monkeypatch.setattr("glorfindel.actions.AzureConnector", _Connector)
    buf = io.StringIO()
    hk = Housekeeping(GlorfindelConsole(file=buf, width=400, color_system=None), threading.Lock(),
                      dry_run=dry_run, mode_override="human_only", runs_dir="runs", ttl_h=4.0,
                      emit=lambda data: None, say_channel=lambda line: None)
    return hk, buf


def test_the_watch_reads_in_a_thread_and_never_in_dry_run(monkeypatch, tmp_path):
    """M7669 : jamais en dry-run (aucun Azure)."""
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", OWN)
    monkeypatch.setattr(discovery, "_registry", discovery.AssetRegistry(tmp_path / "assets.json"))
    r = _Reader({OWN: "Own"})
    monkeypatch.setattr(sn, "_default_reader", lambda: r)
    dry, _ = _housekeeping(monkeypatch, dry_run=True)
    dry._subscription_names()
    assert dry._names is None and r.calls == []
    hk, buf = _housekeeping(monkeypatch)
    hk._subscription_names()
    hk._names_thread._thread.join(timeout=10)
    assert r.calls == [OWN]
    assert json.loads(sn.state_file().read_text())["names"][OWN]["name"] == "Own"
    assert "subscription names: 1 of 1 read" in buf.getvalue() and "Own" not in buf.getvalue()
    hk._subscription_names()                                                 # rien de dû : aucun fil
    assert r.calls == [OWN]


def test_a_pass_that_fails_is_said_never_the_watch_stopped(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", OWN)
    monkeypatch.setattr(discovery, "_registry", discovery.AssetRegistry(tmp_path / "assets.json"))
    hk, buf = _housekeeping(monkeypatch)

    def broken():
        raise OSError("disk full")
    monkeypatch.setattr(hk._names, "pass_once", broken)
    hk._subscription_names()
    hk._names_thread._thread.join(timeout=10)
    assert "subscription names failed" in buf.getvalue()


# ── 5. Le fichier, le champ de la console ────────────────────────────────────────────────────────

def test_the_file_is_written_at_once_and_the_key_is_masked_no_raw_id_in_the_field(tmp_path):
    """M7670 : la clé masquée au moment de servir — aucun identifiant d'abonnement brut dans le champ."""
    r = _Reader({OWN: f"Named {OTHER}", OTHER.lower(): _HttpError(404, f"SubscriptionNotFound {OTHER}")})
    names, _ = _names(r, tmp_path, [_vm(OTHER)])
    names.pass_once()
    path = tmp_path / "subscriptions.json"
    assert not list(tmp_path.glob(".subscriptions.json.*"))                  # aucun fichier temporaire
    assert OWN in json.loads(path.read_text())["names"]                      # le fichier local : la clé brute
    field = sn.console_field(path)["subscriptions"]
    assert field["read_at"] == datetime.fromtimestamp(NOW, timezone.utc).isoformat()
    assert field["names"] == {"aaaaaaaa…4444": {"name": "Named <id>", "error": None},
                              "bbbbbbbb…8888": {"name": None, "error": "HTTP 404 — SubscriptionNotFound <id>"}}
    text = json.dumps(field, ensure_ascii=False).lower()
    for raw in (OWN, OTHER.lower()):
        assert raw not in text and raw.replace("-", "") not in text


def test_the_mask_is_the_one_config_shows_in_lower_case():
    import eregion_console.api as api
    for raw in (OWN, OTHER):
        assert sn.mask(raw) == api._mask(raw).lower()


@pytest.mark.parametrize("text", [
    "", "{not json", "[]", '{"names": {}}',
    '{"read_at": "x", "names": {}}',
    '{"read_at": "2026-11-25T12:00:00+00:00", "names": []}',
    '{"read_at": "2026-11-25T12:00:00+00:00", "names": {"not-a-guid": {"name": "x", "error": null}}}',
    f'{{"read_at": "2026-11-25T12:00:00+00:00", "names": {{"{OWN}": {{"name": 5, "error": null}}}}}}',
    f'{{"read_at": "2026-11-25T12:00:00+00:00", "names": {{"{OWN}": {{"name": null, "error": ["x"]}}}}}}',
    f'{{"read_at": "2026-11-25T12:00:00+00:00", "names": {{"{OWN}": "Prod"}}}}'])
def test_a_file_that_cannot_be_read_leaves_the_field_out(tmp_path, text):
    """M7666 : un fichier illisible, ou d'une autre forme — pas de champ, jamais la route cassée."""
    path = tmp_path / "subscriptions.json"
    path.write_text(text)
    assert sn.console_field(path) == {}
    assert sn.console_field(tmp_path / "absent.json") == {}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return console()


def test_the_route_carries_the_field_and_leaves_it_out_when_unreadable(client, tmp_path):
    """M7668 : le champ `subscriptions` dans `/api/watch/status`, à côté de `log_freshness`."""
    assert "subscriptions" not in client.get("/api/watch/status").json()     # rien d'écrit encore
    path = sn.state_file()
    assert path == tmp_path / "home" / ".glorfindel" / "subscriptions.json"
    names, _ = _names(_Reader({OWN: "Production"}), tmp_path)
    names._path = path
    names.pass_once()
    w = client.get("/api/watch/status").json()
    assert w["subscriptions"]["names"] == {sn.mask(OWN): {"name": "Production", "error": None}}
    assert w["status"] == "stopped" and w["model_breaker"] == 0 and OWN not in json.dumps(w)
    path.write_text("{broken")
    w = client.get("/api/watch/status").json()
    assert "subscriptions" not in w and w["status"] == "stopped"


def test_the_route_stands_when_the_module_raises(client, monkeypatch):
    """La garde de watch_fields.py : un module qui lève fait disparaître son champ, la route et le
    battement gardés (M7646, de LOGF1, la mesure)."""
    def broken(path=None):
        raise RuntimeError("module broken")
    monkeypatch.setattr(sn, "console_field", broken)
    r = client.get("/api/watch/status")
    assert r.status_code == 200
    w = r.json()
    assert "subscriptions" not in w and w["status"] == "stopped" and w["model_breaker"] == 0
