"""CAN3 (#673): the azurerm canary's OIDC sign-ins set aside from `entra-sp-unusual-signin`, in the
bench's client layer — by its principal and its federated credential together, and nothing else.

The scheduled run of `canary-azurerm` (`.github/workflows/canary-azurerm.yml`, P-04) signs in to
Entra ID from GitHub's hosted runners, whose address changes every run, with the OIDC token GitHub
gives the job, exchanged for the principal `eregion-canary` by its federated identity credential:
the shipped rule, which cards a principal's sign-in from an address never seen in its 14 days, made
a card at every run on H0. Its description foresaw it: a runner with rotating addresses is set
aside in the client's layer. The bench's copy is the shipped rule plus one exclusion, read on each
sign-in line before the lines are grouped: the client application is the canary's (`AppId`, the
appid taken from the watch's environment by `env_guids: [EREGION_RULE_CANARY_APPID]`, CAN2's
variable, never in the repository) **and** the line was made with a federated identity credential
(`ClientCredentialType` is `federatedIdentityCredential`, Microsoft Graph's value — the workspace's
form is to be measured on the bench — and `FederatedCredentialId` names the credential). The
canary's principal by a secret or a certificate, and any other principal, still make a card.

The rules run as written (`tests/unit/kql_subset.py`, which now reads `let`, `join`, `distinct`,
`between`, `dcount`, `make_set`, `bin`, `strcat_array`) on lines in AADServicePrincipalSignInLogs'
form; through the RulePoller and the Entra adapter too. Every identifier is made up: 00000000-…
GUIDs, 192.0.2.0/24 and 198.51.100.0/24 addresses. No Azure, no model.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from glorfindel.detection_rules import (
    RulePoller,
    base_rule_sha256,
    load_config,
    routing_refusal,
    shipped_rules_path,
)
from glorfindel.detectors import AzureEntraDetector
from glorfindel.providers.azure.monitor import AzureMonitorDetector

from . import kql_subset

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "infra" / "glorfindel-host" / "client_rules.bench.yaml"
NAME = "entra-sp-unusual-signin"
VAR = "EREGION_RULE_CANARY_APPID"
SHIPPED = {r["name"]: r for r in yaml.safe_load(shipped_rules_path().read_text())["rules"]}
CLIENT = {r["name"]: r for r in yaml.safe_load(BENCH.read_text())["rules"]}
# The shipped rule's fingerprint when CAN3 copied it: a change of the base fails here, in the pull
# request that makes it (and the watch sets the copy aside, its drift said: WL1).
BASE_SHA256 = "777e9b5a7e7d69c0e0c8536cc887b8cd08be6a9cc1643655fbfe0eebd320e785"

# Placeholders, never real ids.
CANARY_APP = "00000000-0000-0000-0000-00000000ca17"
CANARY_SP = "00000000-0000-0000-0000-00000000ca19"
CANARY_FIC = "00000000-0000-0000-0000-00000000ca1f"
OTHER_APP = "00000000-0000-0000-0000-0000000000ab"
OTHER_SP = "00000000-0000-0000-0000-0000000000ad"
OTHER_FIC = "00000000-0000-0000-0000-0000000000af"
SECRET_KEY = "00000000-0000-0000-0000-0000000000e1"
OWN_APP = "00000000-0000-0000-0000-0000000000f1"     # Glorfindel's own identity, for the adapter
FEDERATED = "federatedIdentityCredential"
KNOWN_IPS = ("198.51.100.11", "198.51.100.12", "198.51.100.13", "198.51.100.14")
NEW_IP = "192.0.2.77"                                  # a runner's address never seen before
NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _now_when_the_test_starts():
    global NOW
    NOW = datetime.now(timezone.utc)


def _signin(at: datetime, ip: str = NEW_IP, app: str = CANARY_APP, sp: str = CANARY_SP,
            credential: str = FEDERATED, fic: str | None = CANARY_FIC, key: str = "",
            thumbprint: str = "", result: str = "0", corr: str = "c-1") -> dict:
    """One line of AADServicePrincipalSignInLogs, as the diagnostic setting writes it."""
    return {"Type": "AADServicePrincipalSignInLogs", "TimeGenerated": at, "ResultType": result,
            "AppId": app, "ServicePrincipalId": sp, "ServicePrincipalName": "eregion-canary" if sp == CANARY_SP
            else "sp-other", "IPAddress": ip, "ResourceDisplayName": "Windows Azure Service Management API",
            "Location": "US", "CorrelationId": corr, "ClientCredentialType": credential,
            "FederatedCredentialId": fic or "", "ServicePrincipalCredentialKeyId": key,
            "ServicePrincipalCredentialThumbprint": thumbprint}


def _history(app: str = CANARY_APP, sp: str = CANARY_SP, fic: str | None = CANARY_FIC) -> list[dict]:
    """The principal's 14 days: a run a day, four days, each from another runner's address — a
    principal with a history (MIN_BASELINE_DAYS), so the shipped rule speaks of a new address."""
    return [_signin(NOW - timedelta(days=d, hours=2), ip=ip, app=app, sp=sp, fic=fic, corr=f"h-{d}")
            for d, ip in zip(range(2, 6), KNOWN_IPS)]


def _query(environ: dict) -> str:
    cfg = load_config(shipped_rules_path(), client_layer=BENCH, environ=environ)
    return next(r for r in cfg.rules if r.name == NAME).query


def _bench(rows, appid: str = CANARY_APP):
    return kql_subset.run(_query({VAR: appid}), rows, now=NOW)


def _base(rows):
    return kql_subset.run(SHIPPED[NAME]["query"], rows, now=NOW)


def _run(**line) -> list[dict]:
    """A run of the canary: its history, then a sign-in from a new runner's address."""
    return _history() + [_signin(NOW - timedelta(minutes=10), **line)]


# ── The shipped rule, as written: a card at every run of the canary ─────────────────

def test_the_shipped_rule_cards_each_run_of_the_canary_and_not_a_known_address():
    [card] = _base(_run())
    assert card["EventId"] == f"{CANARY_SP}|{NEW_IP}" and card["ActorAppId"] == CANARY_APP
    assert card["BaselineDays"] == 4 and card["SignIns"] == 1 and card["EntraKind"] == "signin"
    # Known address, or no history: no card — the reader follows the rule's baseline.
    assert _base(_history() + [_signin(NOW - timedelta(minutes=10), ip=KNOWN_IPS[0])]) == []
    assert _base([_signin(NOW - timedelta(minutes=10))]) == []
    # A failure is no sign-in.
    assert _base(_run(result="7000215")) == []


# ── The copy: the base, plus the exclusion block, nothing else ──────────────────────

_BLOCK_START = "// CAN3 (#673)"
_BLOCK_END = "and isnotempty(FederatedCredentialId))"


def _without_block(query: str) -> str:
    lines = query.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.strip().startswith(_BLOCK_START))
    end = next(i for i in range(start, len(lines)) if _BLOCK_END in lines[i])
    return "".join(lines[:start] + lines[end + 1:])


def test_the_base_has_not_moved():
    """The shipped rule is untouched by CAN3: its fingerprint is the one the copy came from."""
    assert base_rule_sha256(SHIPPED[NAME]) == BASE_SHA256 == CLIENT[NAME]["base_sha256"]
    assert VAR not in shipped_rules_path().read_text()


def test_the_bench_rule_is_the_shipped_query_plus_the_exclusion_block_alone():
    client, base = CLIENT[NAME], SHIPPED[NAME]
    assert _without_block(client["query"]) == base["query"]
    for key in ("source", "ttp", "assets", "interval_s", "expected_latency_s", "enabled"):
        assert client[key] == base[key], key
    assert client["description"].startswith(base["description"].strip())
    assert set(client) - set(base) == {"base_sha256", "env_guids"}
    assert client["env_guids"] == [VAR]
    query = client["query"]
    # On each sign-in line of the last hour, before they are grouped: a line's credential is its own.
    assert query.index("| join kind=leftanti known") < query.index(_BLOCK_START) < query.index("| summarize TimeGenerated")
    # The baseline (the three `let`s) is the shipped rule's: the canary's history still counts.
    assert query.index("let history") < query.index(_BLOCK_START)
    block = query[query.index(_BLOCK_START):query.index(_BLOCK_END) + len(_BLOCK_END)]
    assert block.count("| where not(") == 1 and "${" + VAR + "}" in block


def test_no_identifier_of_the_canary_in_the_repository():
    assert "${" + VAR + "}" in CLIENT[NAME]["query"]
    guids = re.findall(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                       BENCH.read_text())
    assert guids == []


def test_the_copy_loads_with_the_guid_of_the_environment_bound_to_the_workspace():
    cfg = load_config(shipped_rules_path(), client_layer=BENCH, environ={VAR: CANARY_APP.upper()},
                      glorfindel_cfg=SimpleNamespace(monitoring_backends=[SimpleNamespace(
                          name="law-bench", type="azure_monitor", workspace_id="ws-test", endpoint="")]))
    rule = next(r for r in cfg.rules if r.name == NAME)
    assert rule.layer == "client" and rule.replaces_base and rule.source == "azure_entra"
    assert rule.enabled and rule.workspace_id == "ws-test" and rule.ttp == "T1078.004"
    assert "${" not in rule.query and rule.query.count(CANARY_APP) == 1          # lowercase
    assert rule.query == CLIENT[NAME]["query"].replace("${" + VAR + "}", CANARY_APP)
    assert NAME in cfg.overrides and cfg.drifted == []
    assert not any(VAR in n for n in cfg.notes)
    # SEC-A4: an identity rule is filed on what its rows name, never routed to a VM — not refused.
    assert routing_refusal(rule.source, rule.query) == ""


# ── The canary's federated sign-ins: no card ────────────────────────────────────────

@pytest.mark.parametrize("appid", [CANARY_APP, CANARY_APP.upper()])
def test_the_canary_s_federated_sign_in_from_a_new_runner_makes_no_card(appid):
    rows = _run(app=appid)
    assert len(_base(rows)) == 1                    # the shipped rule's card, every run
    assert _bench(rows) == []


def test_every_sign_in_of_a_run_from_new_runners_is_set_aside():
    """A run signs in several times (az login, then Terraform with the token, a row per azurerm
    line of the matrix), from one or more runners: none of them a card."""
    rows = _history() + [_signin(NOW - timedelta(minutes=m), ip=f"192.0.2.{m}", corr=f"c-{m}")
                         for m in range(5, 40, 5)]
    assert len(_base(rows)) == 7
    assert _bench(rows) == []


# ── Anything else is a card ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("line", [
    {"credential": "clientSecret", "fic": None, "key": SECRET_KEY},                 # a secret
    {"credential": "certificate", "fic": None, "key": SECRET_KEY, "thumbprint": "AB" * 20},
    {"credential": "clientAssertion", "fic": None, "key": SECRET_KEY},              # a signed assertion
    {"credential": "clientAssertion", "fic": CANARY_FIC},                           # not said federated
    {"credential": FEDERATED, "fic": None},                                         # names no credential
    {"credential": "", "fic": CANARY_FIC},                                          # the column empty
    {"credential": "none", "fic": None},
], ids=["secret", "certificate", "assertion", "assertion-with-fic", "federated-no-fic", "empty", "none"])
def test_the_canary_s_principal_by_another_credential_makes_a_card(line):
    rows = _run(**line)
    assert len(_bench(rows)) == 1 == len(_base(rows))


def test_another_principal_s_federated_sign_in_makes_a_card():
    rows = (_history(app=OTHER_APP, sp=OTHER_SP, fic=OTHER_FIC)
            + [_signin(NOW - timedelta(minutes=10), app=OTHER_APP, sp=OTHER_SP, fic=OTHER_FIC)])
    [card] = _bench(rows)
    assert card["ActorAppId"] == OTHER_APP and len(_base(rows)) == 1


def test_the_canary_s_secret_among_its_federated_sign_ins_from_the_same_address_is_a_card():
    """One group, principal and address, two credentials: the federated line set aside, the secret
    one still read — its card, its sign-in alone counted."""
    rows = _history() + [_signin(NOW - timedelta(minutes=20), corr="c-oidc"),
                         _signin(NOW - timedelta(minutes=10), credential="clientSecret", fic=None,
                                 key=SECRET_KEY, corr="c-secret")]
    [base] = _base(rows)
    [card] = _bench(rows)
    assert base["SignIns"] == 2 and card["SignIns"] == 1 and card["CorrelationId"] == "c-secret"


# ── The variable absent or invalid: the shipped rule runs ───────────────────────────

@pytest.mark.parametrize("environ", [
    {}, {VAR: ""}, {VAR: "   "}, {VAR: "not-a-guid"}, {VAR: CANARY_APP + "0"},
    # What would leave the string and widen the exclusion, if it reached the query (KQL injection).
    {VAR: '" or 1 == 1 or "'}, {VAR: CANARY_APP + '" or AppId != "'},
])
def test_the_variable_absent_or_invalid_sets_the_copy_aside_and_the_shipped_rule_runs(environ):
    cfg = load_config(shipped_rules_path(), client_layer=BENCH, environ=environ)
    rule = next(r for r in cfg.rules if r.name == NAME)
    assert rule.layer == "base" and rule.query == SHIPPED[NAME]["query"]
    assert NAME not in cfg.overrides
    [note] = [n for n in cfg.notes if VAR in n and NAME in n]
    assert "la règle livrée tourne à sa place" in note
    value = environ.get(VAR, "").strip()
    assert not value or value not in note                           # never the value
    # …so the canary makes its cards again: more cards, never fewer.
    assert len(kql_subset.run(rule.query, _run(), now=NOW)) == 1
    # The layer's copy that takes no variable is untouched.
    assert next(r for r in cfg.rules if r.name == "sudo-privilege-escalation").layer == "client"


# ── Through the poller and the Entra adapter: the canary makes no signal ────────────

@pytest.fixture()
def law(monkeypatch):
    """The workspace: the rule's query run as written on the lines of `rows`."""
    state = {"rows": []}
    monkeypatch.setattr(AzureMonitorDetector, "run_query",
                        lambda self, query, timespan=None: kql_subset.run(query, state["rows"], now=NOW))
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GLORFINDEL_OWN_CALLERS", raising=False)
    return state


class _Credential:
    def get_token(self, _scope):
        def b64(d):
            return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
        return SimpleNamespace(token=f"{b64({'alg': 'none'})}.{b64({'appid': OWN_APP, 'oid': OWN_APP})}.sig")


def _poll(rows, environ):
    cfg = load_config(shipped_rules_path(), client_layer=BENCH, environ=environ,
                      glorfindel_cfg=SimpleNamespace(monitoring_backends=[SimpleNamespace(
                          name="law-bench", type="azure_monitor", workspace_id="ws-test", endpoint="")]))
    rule = next(r for r in cfg.rules if r.name == NAME)
    sent: list = []
    p = RulePoller([rule], sent.append)
    det = AzureEntraDetector("ws-test", credential=_Credential())
    p._detector = lambda _rule: det
    vm = ("/subscriptions/00000000-0000-0000-0000-0000000000cc/resourceGroups/rg-celebrimbor/providers/"
          "Microsoft.Compute/virtualMachines/vm-1")
    p._registry = SimpleNamespace(for_backend=lambda _n: [SimpleNamespace(name="vm-1", resource_id=vm)])
    p.poll_once(rule)
    return sent


def test_through_the_poller_the_canary_makes_no_signal_and_its_secret_one(law):
    law["rows"] = _run()
    assert _poll(law["rows"], {VAR: CANARY_APP}) == []
    # Without the variable, the shipped rule: the canary's run, its card.
    [signal] = _poll(law["rows"], {})
    assert signal["context"]["plane"] == "identity"
    # The canary's principal by a secret, from another new address: its card, through the copy.
    law["rows"] += [_signin(NOW - timedelta(minutes=5), ip="192.0.2.99", credential="clientSecret",
                            fic=None, key=SECRET_KEY, corr="c-secret")]
    [signal] = _poll(law["rows"], {VAR: CANARY_APP})
    row = signal["raw_signal"]["first_result_row"]
    assert row["EventId"] == f"{CANARY_SP}|192.0.2.99" and row["CorrelationId"] == "c-secret"
