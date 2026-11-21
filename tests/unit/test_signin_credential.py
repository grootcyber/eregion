"""CRD1 (#1011): an unusual sign-in of a service principal proposes to remove the one credential it
used — never only to disable the whole principal — read from the shipped query to the plan.

The constat (E7 of ID1, on the bench, 21/11): `AADServicePrincipalSignInLogs.ServicePrincipalCredentialKeyId`
names the credential a sign-in used (5 sign-ins out of 5, `clientAssertion`; its value the `keyId`
of the certificate): hypothesis 7 of docs/design/reponse-identite.md, measured. But the shipped rule
`entra-sp-unusual-signin` did not keep that column — neither in its `summarize … by
ServicePrincipalId, IPAddress` nor in its `project` — and `entra_items._signin_items` read a column
no real row had: the plan always disabled the principal (all its legitimate use stopped). The tests
(test_identity_plan.py, test_canary_signin.py) gave the column to the row by hand.

Here the shipped query runs as written over lines of the table (tests/unit/kql_subset.py), its rows
become the body Log Analytics sends — the set of keyIds a ``dynamic`` column, so its JSON text —, read
by the pinned SDK's own objects (tests/unit/sdk_logs.py), the real `AzureEntraDetector`, the real
RulePoller, then `_identity_decision` (glorfindel/agent.py) and the plan (entra_plan.build). One
credential: its removal. Two, none, a value that is no keyId, a text that does not decode: the
principal disabled, as before. Nothing runs: a plan for a human. Mutants M6942–M6951
(scripts/mutants/CRD1.py). No Azure, no Graph (tests/unit/fake_graph.py), no model; every identifier
is made up (repository public).
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from glorfindel.agent import _identity_decision
from glorfindel.detection_rules import RulePoller, load_config, shipped_rules_path
from glorfindel.detectors import AzureEntraDetector
from glorfindel.providers.azure import entra_items, entra_plan
from tests.unit.fake_graph import FakeGraph

from . import sdk_logs

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "infra" / "glorfindel-host" / "client_rules.bench.yaml"
NAME = "entra-sp-unusual-signin"
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
# Placeholders, never real ids.
APP = "00000000-0000-0000-0000-0000000000c1"           # the application (its object)
APP_ID = "00000000-0000-0000-0000-0000000000c9"        # its client id
SP = "00000000-0000-0000-0000-0000000000c2"            # its service principal
KEY = "00000000-0000-0000-0000-00000000000a"           # the certificate the sign-in used
OTHER_KEY = "00000000-0000-0000-0000-00000000000b"     # another credential of the application
OWN_APP = "00000000-0000-0000-0000-0000000000f1"       # Glorfindel's own identity, for the adapter
CANARY_APP = "00000000-0000-0000-0000-00000000ca17"
KNOWN_IPS = ("198.51.100.11", "198.51.100.12", "198.51.100.13", "198.51.100.14")
NEW_IP = "192.0.2.77"
VM = ("/subscriptions/00000000-0000-0000-0000-0000000000cc/resourceGroups/rg-example/providers/"
      "Microsoft.Compute/virtualMachines/vm-example-01")


@pytest.fixture(autouse=True)
def _no_ambient_identity(monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)


def _signin(at: datetime, ip: str = NEW_IP, key: str | None = KEY, corr: str = "c-1") -> dict:
    """One line of AADServicePrincipalSignInLogs, as the diagnostic setting writes it: the keyId
    of the credential used in `ServicePrincipalCredentialKeyId` (measured, 21/11)."""
    line = {"Type": "AADServicePrincipalSignInLogs", "TimeGenerated": at, "ResultType": "0",
            "AppId": APP_ID, "ServicePrincipalId": SP, "ServicePrincipalName": "sp-ci-deploy", "IPAddress": ip,
            "ResourceDisplayName": "Windows Azure Service Management API", "Location": "FR",
            "CorrelationId": corr, "ClientCredentialType": "clientAssertion", "FederatedCredentialId": ""}
    if key is not None:
        line["ServicePrincipalCredentialKeyId"] = key
    return line


def _history() -> list[dict]:
    """The principal's baseline: four days, each from a known address, with its usual credential."""
    return [_signin(NOW - timedelta(days=d, hours=2), ip=ip, corr=f"h-{d}")
            for d, ip in zip(range(2, 6), KNOWN_IPS)]


def _now(*keys) -> list[dict]:
    """The sign-ins of the last hour from the new address, one per key given (None: the column
    absent from the line)."""
    return [_signin(NOW - timedelta(minutes=10 + i), key=k, corr=f"c-{i}") for i, k in enumerate(keys)]


class _Credential:
    def get_token(self, _scope):
        def b64(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        return SimpleNamespace(token=f"{b64({'alg': 'none'})}.{b64({'appid': OWN_APP, 'oid': OWN_APP})}.sig")


def _cfg():
    return SimpleNamespace(monitoring_backends=[SimpleNamespace(
        name="law-bench", type="azure_monitor", workspace_id="ws-test", endpoint="")])


def _rule(bench: bool = False):
    if bench:
        cfg = load_config(shipped_rules_path(), client_layer=BENCH, glorfindel_cfg=_cfg(),
                          environ={"EREGION_RULE_CANARY_APPID": CANARY_APP})
    else:
        cfg = load_config(shipped_rules_path(), client_layer=False, glorfindel_cfg=_cfg())
    rule = next(r for r in cfg.rules if r.name == NAME)
    assert rule.layer == ("client" if bench else "base")
    return rule


def _detector(lines, mangle=None) -> AzureEntraDetector:
    """The real Entra detector over the pinned SDK's own client: the query run as written over
    `lines`, its rows the body of the reply (`mangle(body)`: changed before it is sent)."""
    ws = sdk_logs.Workspace(sdk_logs.kql(lines, now=NOW, mangle=mangle))
    return ws.detector(cls=AzureEntraDetector, credential=_Credential())


def _rows(lines, bench: bool = False, mangle=None) -> list[dict]:
    return _detector(lines, mangle).run_query(_rule(bench).query)


@pytest.fixture()
def tenant():
    g = FakeGraph()
    g.apps[APP] = {"id": APP, "appId": APP_ID, "displayName": "app-ci-deploy", "passwordCredentials": [],
                   "keyCredentials": [{"keyId": KEY, "type": "AsymmetricX509Cert", "usage": "Verify"},
                                      {"keyId": OTHER_KEY, "type": "AsymmetricX509Cert", "usage": "Verify"}]}
    g.sps[SP] = {"id": SP, "appId": APP_ID, "displayName": "sp-ci-deploy", "accountEnabled": True,
                 "passwordCredentials": [], "keyCredentials": []}
    return g


def _first(plan) -> dict:
    return plan["items"][0]


def _removes(plan, key: str = KEY) -> bool:
    first = _first(plan)
    return first["verb"] == "entra_remove_credential" and {p["name"]: p["value"] for p in first["params"]}.get(
        "keyId") == key


def _disables(plan) -> bool:
    first = _first(plan)
    return (first["verb"] == "entra_disable_principal"
            and first["command"] == f"az ad sp update --id {SP} --set accountEnabled=false"
            and not any(i["verb"] == "entra_remove_credential" for i in plan["items"]))


# ── The query keeps the credentials, as a dynamic column the SDK hands on as text ───────────────

def test_the_shipped_query_keeps_the_credentials_the_sign_ins_used_in_one_column():
    query = _rule().query
    assert "make_set(ServicePrincipalCredentialKeyId, 5)" in query
    assert f"{entra_items.USED_CREDENTIALS} = make_set(ServicePrincipalCredentialKeyId, 5)" in query
    project = query[query.rindex("| project"):]
    assert entra_items.USED_CREDENTIALS in project
    # The baseline and its thresholds are untouched (14 days, the last hour left out).
    assert "between (ago(14d) .. ago(1h))" in query and "where TimeGenerated > ago(1h)" in query
    assert "join kind=inner history" in query


def test_through_the_sdk_the_set_arrives_as_its_json_text():
    [row] = _rows(_history() + _now(KEY))
    value = row[entra_items.USED_CREDENTIALS]
    assert isinstance(value, str) and json.loads(value) == [KEY]


# ── One credential: its removal; two, none, illegible: the principal disabled ───────────────────

@pytest.mark.parametrize("bench", [False, True], ids=["shipped", "bench-copy"])
def test_one_credential_used_proposes_its_removal(tenant, bench):
    """Fini quand: one credential known, the card proposes its removal — proved by the shipped query
    (and the bench's copy, CAN3) and the SDK's objects."""
    [row] = _rows(_history() + _now(KEY, KEY, KEY), bench=bench)          # three sign-ins, one key
    assert row["SignIns"] == 3 and json.loads(row[entra_items.USED_CREDENTIALS]) == [KEY]
    plan = entra_plan.build(row, tenant, now=NOW)
    assert _removes(plan)
    first = _first(plan)
    # A certificate, read on Graph: its removal by its keyId, the command complete.
    assert first["command"] == f"az ad app credential delete --id {APP} --key-id {KEY} --cert" and first["complete"]
    assert first["why_human"] == entra_items._NO_EXECUTOR   # a plan for a human: nothing runs alone
    # The other credential of the application stays: its legitimate use goes on.
    assert OTHER_KEY not in first["command"]
    assert not any(i["verb"] == "entra_disable_principal" for i in plan["items"])


def test_two_credentials_used_propose_to_disable_the_principal(tenant):
    [row] = _rows(_history() + _now(KEY, OTHER_KEY))
    assert sorted(json.loads(row[entra_items.USED_CREDENTIALS])) == sorted([KEY, OTHER_KEY])
    plan = entra_plan.build(row, tenant, now=NOW)
    assert _disables(plan)
    assert "2 identifiants" in _first(plan)["what"]


def test_a_sign_in_that_names_no_credential_beside_one_that_does_is_two(tenant):
    """One sign-in named the key, another named none (the column empty): removing the key would
    leave the other — the principal disabled."""
    [row] = _rows(_history() + _now(KEY, ""))
    assert json.loads(row[entra_items.USED_CREDENTIALS]) == [KEY, ""]
    assert _disables(entra_plan.build(row, tenant, now=NOW))


@pytest.mark.parametrize("keys", [("",), (None,), ("", "")], ids=["empty", "absent", "empty-twice"])
def test_no_credential_named_proposes_to_disable_the_principal(tenant, keys):
    [row] = _rows(_history() + _now(*keys))
    plan = entra_plan.build(row, tenant, now=NOW)
    assert _disables(plan)
    assert "ne nomme aucun identifiant" in _first(plan)["what"]


@pytest.mark.parametrize("graph", ["read", "unread"])
def test_a_value_that_is_no_key_id_proposes_nothing_more_than_disabling(tenant, graph):
    from glorfindel.providers.azure.graph import NoGraph
    [row] = _rows(_history() + _now("not-a-key; az ad app delete"))
    plan = entra_plan.build(row, tenant if graph == "read" else NoGraph("droit absent sur Graph (403)"), now=NOW)
    assert _disables(plan)
    assert not any("not-a-key" in (i["command"] + i["rollback"] + i["what"]) for i in plan["items"])
    assert "n'est pas un keyId" in _first(plan)["what"]


def test_a_key_id_graph_finds_on_neither_object_proposes_to_disable(tenant):
    """A federated sign-in names a keyId that is no credential of the application (measured on the
    canary, 11/11), or the credential is already removed: Graph read, nothing to remove by it."""
    tenant.apps[APP]["keyCredentials"] = [{"keyId": OTHER_KEY, "type": "AsymmetricX509Cert", "usage": "Verify"}]
    [row] = _rows(_history() + _now(KEY))
    plan = entra_plan.build(row, tenant, now=NOW)
    assert _disables(plan)
    assert "ni l'application ni le principal" in _first(plan)["what"]


def test_graph_unread_the_key_id_of_the_log_is_still_proposed():
    """Without Graph (dry run, a right missing), the keyId of the log is proposed, said not confirmed
    and its object not read — as before CRD1, never a disable in its place."""
    from glorfindel.providers.azure.graph import NoGraph
    [row] = _rows(_history() + _now(KEY))
    plan = entra_plan.build(row, NoGraph("droit absent sur Graph (403)"), now=NOW)
    first = _first(plan)
    assert first["verb"] == "entra_remove_credential" and not first["complete"]
    assert {p["name"]: p["value"] for p in first["params"]}["keyId"] == KEY


def _illegible(body):
    """The set's text cut in the middle, as no JSON decodes it."""
    table = body["tables"][0]
    col = [c["name"] for c in table["columns"]].index(entra_items.USED_CREDENTIALS)
    for r in table["rows"]:
        r[col] = r[col][:-3]


def test_an_illegible_text_proposes_to_disable_the_principal_and_never_raises(tenant):
    [row] = _rows(_history() + _now(KEY), mangle=_illegible)
    assert isinstance(row[entra_items.USED_CREDENTIALS], str)
    plan = entra_plan.build(row, tenant, now=NOW)
    assert _disables(plan)
    assert "illisible" in _first(plan)["what"]


@pytest.mark.parametrize("value", [
    None, "", "[", "null", "{}", '"' + KEY + '"', KEY, 42, json.dumps([KEY, KEY.upper()]),
    json.dumps([{"keyId": KEY}]), json.dumps([None]), json.dumps([[KEY]]), "[" + "1," * 40000 + "1]",
    json.dumps(["not-a-key"]), json.dumps([KEY + "0"]), json.dumps([KEY[:-1]]),
])
def test_the_reader_never_raises_and_takes_only_a_single_key_id(value):
    key, why = entra_items.used_credential({entra_items.USED_CREDENTIALS: value})
    assert key == "" and why


@pytest.mark.parametrize("value", [json.dumps([KEY]), json.dumps([KEY.upper()]), [KEY], json.dumps([" " + KEY])])
def test_the_reader_takes_the_single_key_id_lowercase(value):
    assert entra_items.used_credential({entra_items.USED_CREDENTIALS: value}) == (KEY, "")


def test_the_old_names_are_no_longer_read():
    """One name on both sides (the query projects it, the code reads it): a column of the table
    given to the row by hand is not the rule's."""
    assert entra_items.used_credential({"ServicePrincipalCredentialKeyId": KEY})[0] == ""
    assert entra_items.used_credential({"CredentialKeyId": KEY})[0] == ""


# ── The whole path: the RulePoller, the decision, the card's plan ───────────────────────────────

def _card(lines):
    """A poll of the shipped rule over the SDK's objects, then the decision on its signal (dry
    run: Graph not read)."""
    rule = _rule()
    sent: list = []
    p = RulePoller([rule], sent.append)
    det = _detector(lines)
    p._detector = lambda _rule: det
    p._registry = SimpleNamespace(for_backend=lambda _n: [SimpleNamespace(name="vm-example-01", resource_id=VM)])
    p.poll_once(rule)
    [signal] = sent
    state = {"signal": signal, "past_cycles": [], "incident": None, "dry_run": True, "reasoning": "",
             "confidence": 0.0, "action": "", "reversible": True, "explanation": "", "escalate": False,
             "escalation_reason": "", "suggested_steps": [], "outcome": None}
    return _identity_decision(state)


def test_through_the_poller_one_credential_the_card_proposes_its_removal_to_a_human():
    d = _card(_history() + _now(KEY))
    assert d["action"] == "" and d["escalate"] is True            # no action: a card for a human
    plan = d["identity_plan"]
    first = _first(plan)
    assert first["verb"] == "entra_remove_credential" and first["why_human"]
    assert {p["name"]: p["value"] for p in first["params"]}["keyId"] == KEY
    assert any(f"--key-id {KEY}" in s for s in d["suggested_steps"])
    assert not any(i["verb"] == "entra_disable_principal" for i in plan["items"])


def test_through_the_poller_two_credentials_the_card_proposes_to_disable():
    d = _card(_history() + _now(KEY, OTHER_KEY))
    first = _first(d["identity_plan"])
    assert d["action"] == "" and first["verb"] == "entra_disable_principal" and first["why_human"]
    assert first["what"].startswith("Bloquer la connexion du principal de service sp-ci-deploy,")   # E-6
