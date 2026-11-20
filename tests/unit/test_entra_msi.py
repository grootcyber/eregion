"""MID1 (#981): the certificate Azure puts on a managed identity it creates is no high card — set aside
from the shipped `entra-credential-added` by the object id of the tenant's « Managed Service Identity »
principal (EREGION_ENTRA_MSI_ACTOR_ID), never by its name, and said.

The six rows of 20/11 (the drill's Logic App, created again after failed applies: five cards, each time
another principal), anonymised — invented GUIDs, the columns as the shipped rule projects them —, handed
to the real AzureEntraDetector through its parent's query, then the real RulePoller (no Azure, no Graph,
no model). What is held:
  - the six rows are set aside, counted in the rule's status, said in the watch's log, shown on the
    rule's line in the console;
  - the counter-cases stay high cards: the same name under another ActorId, another operation
    (« Update application », « Certificates and secrets management »), another target type, a human, an
    application, a secret, another usage, a federated credential, a certificate beside a secret, a key
    description forged by a display name;
  - without the id configured, or with one that is no object id, nothing is set aside — said;
  - Glorfindel's marks come first: a certificate added on its identity stays critical, whoever its
    author;
  - the shipped rule only, its query to the byte;
  - `host_env.py --check` knows the variable (tests/unit/test_glorfindel_host.py).
"""
from __future__ import annotations

import json
import logging

import pytest

from glorfindel.detection_rules import msi_certificate_counts, shipped_query
from glorfindel.providers.azure import entra_msi

from glorfindel.providers.azure.monitor import AzureMonitorDetector

from .test_entra_detection import OWN_OID, ROOT, VM1, _cfg, _detector, _poller, _row, _shipped

RULE = "entra-credential-added"
# Placeholders, never real ids: the tenant's « Managed Service Identity » principal, another principal
# that took its name, and the five managed identities Azure created on 20/11.
MSI = "00000000-0000-0000-0000-00000000f001"
IMPOSTOR = "00000000-0000-0000-0000-00000000f0ff"
CREATED = [f"00000000-0000-0000-0000-0000000a{n:04d}" for n in range(1, 6)]
JS = ROOT / "eregion_console/static/glorfindel.js"


def _cert(key: str, usage: str = "Verify", ktype: str = "AsymmetricX509Cert", spaced: bool = True) -> str:
    sep = ", " if spaced else ","
    return f"[KeyIdentifier={key}{sep}KeyType={ktype}{sep}KeyUsage={usage}{sep}DisplayName=CN={key}]"


def _added(*descriptions) -> str:
    """CredentialAdded as the query projects it: `tostring(Added)`, the JSON text of the array."""
    return json.dumps(list(descriptions))


def _msi_row(n: int, corr: str | None = None, **extra) -> dict:
    """A row of 20/11: « Add service principal » by Managed Service Identity on a managed identity's
    service principal, its certificate."""
    target = CREATED[n]
    row = _row("credential", corr=corr or f"c-msi-{n}", ts=f"2026-11-20T08:{10 + n:02d}:00Z",
               ActorName="Managed Service Identity", ActorId=MSI, ActorAppId="", ActorIp="",
               EntraOperation="Add service principal", TargetName="logic-orodruin-drill", TargetId=target,
               TargetType="ServicePrincipal", CredentialAdded=_added(_cert(target)))
    row["EventId"] = f"{row['CorrelationId']}|{target}"
    row.update(extra)
    return row


def _six() -> list[dict]:
    """Five creations, six rows: the last one logged twice (two operations, one principal)."""
    return [_msi_row(n) for n in range(5)] + [_msi_row(4, corr="c-msi-4b")]


@pytest.fixture()
def law(monkeypatch):
    """The workspace: what the parent detector's query returns (test_entra_detection's)."""
    state = {"rows": []}
    monkeypatch.setattr(AzureMonitorDetector, "run_query", lambda self, query, timespan=None: list(state["rows"]))
    return state


@pytest.fixture()
def msi(monkeypatch):
    monkeypatch.setenv(entra_msi.VARIABLE, MSI)
    return MSI


def _status(p) -> dict:
    return p._status.get(RULE, {})


# ── the rows of 20/11 ─────────────────────────────────────────────────────────────────────────

def test_the_rows_of_the_20_11_make_no_card_and_are_counted_and_said(law, msi, caplog):
    """Fini quand: the six rows are set aside, counted in the rule's status, said in the watch's log;
    a human's credential in the same pass stays a high card."""
    caplog.set_level(logging.INFO, logger="glorfindel.detection_rules")
    rule = _shipped(RULE)
    law["rows"] = _six() + [_row("credential", corr="c-human")]
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    assert [s["raw_signal"]["first_result_row"]["CorrelationId"] for s in sent] == ["c-human"]
    assert sent[0]["severity"] == "high"
    st = _status(p)["msi_certificate"]
    assert st["rows"] == 6 and st["last"] and st["reason"] == entra_msi.REASON and "config" not in st
    said = [r.getMessage() for r in caplog.records if "set aside, no card" in r.getMessage()]
    assert said and "6 row(s)" in said[0] and "Managed Service Identity" in said[0]
    assert MSI not in " ".join(r.getMessage() for r in caplog.records)      # never the id
    snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
    assert snap["msi_certificate_count"] == 6 and snap["msi_certificate_config"] == ""


def test_the_count_goes_on_across_passes(law, msi):
    rule = _shipped(RULE)
    law["rows"] = _six()[:2]
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    law["rows"] = _six()[2:]
    p.poll_once(rule)
    law["rows"] = []
    p.poll_once(rule)                                           # a quiet pass keeps the count
    assert sent == [] and _status(p)["msi_certificate"]["rows"] == 6
    assert msi_certificate_counts(_status(p))["msi_certificate_count"] == 6


@pytest.mark.parametrize("spaced", [True, False])
def test_a_managed_identity_s_certificate_is_read_with_or_without_blanks(msi, spaced):
    row = _msi_row(0, CredentialAdded=_added(_cert(CREATED[0], spaced=spaced)))
    assert entra_msi.is_managed_identity_certificate(row, MSI)


def test_the_actor_id_is_compared_without_case(monkeypatch):
    monkeypatch.setenv(entra_msi.VARIABLE, MSI.upper())
    kept, said = entra_msi.set_aside(RULE, [_msi_row(0, ActorId=MSI.upper()), _msi_row(1)])
    assert kept == [] and said["rows"] == 2


# ── the counter-cases: high cards, as before ──────────────────────────────────────────────────

COUNTER = {
    "the same name, another ActorId": dict(ActorId=IMPOSTOR),
    "the name only, no ActorId": dict(ActorId=""),
    "Update application": dict(EntraOperation="Update application"),
    "Certificates and secrets management": dict(
        EntraOperation="Update application – Certificates and secrets management "),
    "another target type": dict(TargetType="Application"),
    "a human": dict(ActorName="admin@example.org", ActorId="00000000-0000-0000-0000-0000000000b1"),
    "an application": dict(ActorName="app-deploy", ActorId="00000000-0000-0000-0000-0000000000c2",
                           ActorAppId="00000000-0000-0000-0000-0000000000c1"),
    "a secret": dict(CredentialAdded=_added(_cert(CREATED[0], ktype="Password"))),
    "another usage": dict(CredentialAdded=_added(_cert(CREATED[0], usage="Sign"))),
    "a federated credential": dict(CredentialAdded=json.dumps(
        [{"Name": "gh-main", "Issuer": "https://token.actions.example", "Subject": "repo:x"}])),
    "a certificate beside a secret": dict(CredentialAdded=_added(
        _cert(CREATED[0]), _cert(CREATED[1], ktype="Password"))),
    "a key type forged by a display name": dict(CredentialAdded=_added(
        f"[KeyIdentifier={CREATED[0]}, KeyType=Password, KeyUsage=Verify, "
        "DisplayName=x, KeyType=AsymmetricX509Cert, KeyUsage=Verify]")),
    "no credential": dict(CredentialAdded="[]"),
    "a text unreadable": dict(CredentialAdded="[KeyType=AsymmetricX509Cert,KeyUsage=Verify"),
    "a text past its bound": dict(CredentialAdded=_added(*[_cert(CREATED[0])] * 200)),
    "no description, no type": dict(CredentialAdded=_added("[KeyIdentifier=x, KeyUsage=Verify]")),
}


@pytest.mark.parametrize("case", list(COUNTER))
def test_every_counter_case_stays_a_high_card(law, msi, case):
    rule = _shipped(RULE)
    law["rows"] = [_msi_row(0, **COUNTER[case])]
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    assert len(sent) == 1 and sent[0]["severity"] == "high", case
    assert _status(p)["msi_certificate"]["rows"] == 0


def test_glorfindel_s_identity_comes_first_whoever_the_author(law, msi):
    """A certificate added on Glorfindel's identity stays critical, even by the « Managed Service
    Identity » principal in every other respect; and a principal that is Glorfindel's own, marked
    actor, is never set aside either."""
    rule = _shipped(RULE)
    law["rows"] = [_msi_row(0, TargetId=OWN_OID, TargetName="sp-glorfindel")]
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    assert len(sent) == 1 and sent[0]["severity"] == "critical"
    assert sent[0]["raw_signal"]["first_result_row"]["GlorfindelManaged"] is True
    assert not entra_msi.is_managed_identity_certificate({**_msi_row(1), "GlorfindelIdentity": True}, MSI)


# ── without the id, or with one that is no object id: nothing set aside, said ───────────────────

@pytest.mark.parametrize("value, config", [
    (None, "unset"), ("", "unset"), ("   ", "unset"),
    ("Managed Service Identity", "malformed"), (MSI + "0", "malformed"), (MSI[:-1], "malformed"),
    (f"{MSI},{IMPOSTOR}", "malformed"),
])
def test_without_a_valid_id_nothing_is_set_aside_and_it_is_said(law, monkeypatch, caplog, value, config):
    """Fini quand: without configuration, nothing is set aside; the status says why at each pass, the
    log once."""
    caplog.set_level(logging.INFO, logger="glorfindel.detection_rules")
    if value is not None:
        monkeypatch.setenv(entra_msi.VARIABLE, value)
    assert entra_msi.actor_id() == ("", config)
    rule = _shipped(RULE)
    law["rows"] = _six()
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    # A row whose ActorId the log left empty is never matched by an id left empty.
    law["rows"] = [_msi_row(0, corr="c-again"), _msi_row(1, corr="c-no-id", ActorId="")]
    p.poll_once(rule)
    assert len(sent) == 8 and all(s["severity"] == "high" for s in sent)
    st = _status(p)["msi_certificate"]
    assert st["rows"] == 0 and st["config"] == config
    snap = next(s for s in p.status_snapshot() if s["name"] == RULE)
    assert snap["msi_certificate_config"] == config and snap["msi_certificate_count"] == 0
    said = [r for r in caplog.records if "EREGION_ENTRA_MSI_ACTOR_ID" in r.getMessage()]
    assert len(said) == 1 and "nothing set aside" in said[0].getMessage()
    assert said[0].levelno == (logging.WARNING if config == "malformed" else logging.INFO)
    assert not (value or "").strip() or value.strip() not in said[0].getMessage()


def test_a_configured_id_clears_what_the_status_said(law, monkeypatch):
    rule = _shipped(RULE)
    law["rows"] = [_msi_row(0)]
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    assert _status(p)["msi_certificate"]["config"] == "unset" and len(sent) == 1
    monkeypatch.setenv(entra_msi.VARIABLE, MSI)
    law["rows"] = [_msi_row(1)]
    p.poll_once(rule)
    assert "config" not in _status(p)["msi_certificate"] and len(sent) == 1
    assert _status(p)["msi_certificate"]["rows"] == 1


# ── the shipped rule only ────────────────────────────────────────────────────────────────────

def test_only_the_shipped_rule_to_the_byte_sets_aside(law, msi):
    """ATT1's shape: a rule of the client's layer under the same name that changed its query keeps its
    cards; another Entra rule sets nothing aside; the shipped query under another name neither."""
    from dataclasses import replace
    shipped = _shipped(RULE)
    assert shipped_query(RULE, shipped.query)
    assert not shipped_query(RULE, shipped.query + "\n")
    assert not shipped_query("my-credential-rule", shipped.query)
    assert not shipped_query("no-such-rule", "")
    for rule in (replace(shipped, query=shipped.query.replace("ago(1h)", "ago(2h)")),
                 replace(shipped, name="my-credential-rule")):
        law["rows"] = [_msi_row(0)]
        p, sent = _poller(_detector(), rule, VM1)
        p.poll_once(rule)
        assert len(sent) == 1, rule.name
        assert "msi_certificate" not in p._status.get(rule.name, {})
    assert entra_msi.set_aside("entra-app-consent", [_msi_row(0)]) == ([_msi_row(0)], None)


def test_the_shipped_base_is_read_once_over_passes_of_every_rule(law, msi, monkeypatch):
    """MID1 review: `shipped_query` runs for every rule at every pass — the shipped base is read and
    parsed once, whatever the number of rules and passes."""
    import glorfindel.detection_rules as dr
    from glorfindel.detection_rules import _shipped_query_sha256s, shipped_rules_path
    rules = [r for r in dr.load_config(dr.shipped_rules_path(), glorfindel_cfg=_cfg(), client_layer=False).rules
             if r.enabled]
    assert len(rules) > 16                       # more than a cache of one entry per rule would hold
    credential = _shipped(RULE)
    p, _sent = _poller(_detector(), credential, VM1)
    _shipped_query_sha256s.cache_clear()
    reads: list[str] = []
    real = dr._read_layer
    monkeypatch.setattr(dr, "_read_layer", lambda path, *a, **k: reads.append(str(path)) or real(path, *a, **k))
    for _ in range(3):
        for rule in rules:
            assert shipped_query(rule.name, rule.query), rule.name
    for corr in ("c-1", "c-2", "c-3"):
        law["rows"] = [_msi_row(0, corr=corr)]
        p.poll_once(credential)
    assert _status(p)["msi_certificate"]["rows"] == 3
    assert reads.count(str(shipped_rules_path())) == 1


def test_a_fault_sets_nothing_aside_and_is_said(law, msi, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(entra_msi, "set_aside", boom)
    rule = _shipped(RULE)
    law["rows"] = [_msi_row(0)]
    p, sent = _poller(_detector(), rule, VM1)
    p.poll_once(rule)
    assert len(sent) == 1 and "set_aside: RuntimeError" in _status(p)["last_error"]


def test_the_shipped_query_does_not_change():
    """P1: the shipped query is the one of before MID1 — the set-aside is in code."""
    import hashlib
    q = _shipped(RULE).query
    assert "Managed Service Identity" not in q and "MSI" not in q
    assert hashlib.sha256(q.encode()).hexdigest() == (
        "abeadfa8c57b0de10593a152a796cbcd49b32ddcd1eab159ab5c808654921744")


# ── the console ──────────────────────────────────────────────────────────────────────────────

def test_the_console_counts_the_rows_set_aside_on_the_rule():
    """The rule's line and its details say how many rows were set aside, and why, through `_attr`; an
    id that is no object id is said on the line; the console's API carries the counts."""
    js = JS.read_text()
    row = js.split("const _ruleRow = (r) => {", 1)[1].split("\n  };\n", 1)[0]
    assert "Number(r.msi_certificate_count) > 0 || r.msi_certificate_config === 'malformed'" in row
    assert "${msi}" in row and 'title="${_attr(_msiCertificateTxt(r))}"' in row
    assert "${_attr(Number(r.msi_certificate_count))} MSI" in row
    txt = js.split("function _msiCertificateTxt(r) {", 1)[1].split("\n}\n", 1)[0]
    assert "row(s) set aside, no card: the certificate Azure puts on a managed identity" in txt
    assert "EREGION_ENTRA_MSI_ACTOR_ID is no object id: nothing set aside" in txt
    assert "EREGION_ENTRA_MSI_ACTOR_ID unset: nothing set aside" in txt
    assert "return [said, config].filter(Boolean).join(' · ');" in txt
    detail = js.split("function showRuleDetail(rule) {", 1)[1].split("\n}\n", 1)[0]
    assert "_attr(_msiCertificateTxt(rule))" in detail
    api = (ROOT / "eregion_console/api.py").read_text()
    assert "**msi_certificate_counts(s)," in api


def test_the_counts_read_from_a_status_are_bounded():
    assert msi_certificate_counts({}) == {"msi_certificate_count": 0, "msi_certificate_last": "",
                                          "msi_certificate_config": ""}
    odd = {"msi_certificate": {"rows": "6", "config": "<script>", "last": 3}}
    assert msi_certificate_counts(odd) == {"msi_certificate_count": 0, "msi_certificate_last": "3",
                                           "msi_certificate_config": ""}
    assert msi_certificate_counts({"msi_certificate": {"rows": -1}})["msi_certificate_count"] == 0
