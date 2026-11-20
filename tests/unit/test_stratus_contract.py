"""R2c (#608) — the contract arms FOR Stratus (Pièce 2, docs/design/stratus-cible.md,
« Le code hermétique de R2c »). The arming LOGIC (assess_stratus) is tested directly; the reader
(read_stratus) with an injected ``get`` and fake tokens; and the allow-list is held EQUAL to the
Terraform's closed role (R2BGc), so the contract and the role never drift. No apply, no Azure."""
import base64
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import eregion_core.orodruin as orodruin

STRATUS_SUB = "11111111-1111-1111-1111-111111111111"   # the dedicated Stratus subscription
BENCH_SUB = "22222222-2222-2222-2222-222222222222"     # Orodruin's own / the bench (protected)
CLOSED = sorted(orodruin.STRATUS_CLOSED_ROLE_ACTIONS)
_ROLE = f"/subscriptions/{STRATUS_SUB}/providers/Microsoft.Authorization/roleDefinitions/closed"


def _assign(scope, role="closed"):
    return {"properties": {"scope": scope, "roleDefinitionId": role}}


def _codes(**over):
    """assess_stratus with armed defaults (Stratus holds only its closed role, the subscription
    is cold, the diagnostic routes), overridden per case; returns the missing codes."""
    kw = dict(subscription=STRATUS_SUB, protected=frozenset({BENCH_SUB}),
              assignments=[_assign(f"/subscriptions/{STRATUS_SUB}")],
              role_actions=lambda _id: list(CLOSED),
              sees_subscription=True, groups=["NetworkWatcherRG"], diag_ok=True)
    kw.update(over)
    return [m["code"] for m in orodruin.assess_stratus(**kw)]


# ── assess_stratus: armed only if Stratus holds nothing but its closed role, cold, routed ──

def test_armed_when_stratus_holds_only_its_closed_role_cold_and_routed():
    assert _codes() == []


def test_a_forbidden_subscription_is_refused_and_stops_everything():
    # EREGION_STRATUS_SUBSCRIPTION being the bench/VM/Imladris/Orodruin is the v1 blocker: even
    # with every other signal broken, the subscription itself is the only (and first) reason.
    assert _codes(subscription=BENCH_SUB) == ["stratus_forbidden_subscription"]
    assert _codes(subscription=BENCH_SUB, sees_subscription=False, diag_ok=False,
                  groups=["x"]) == ["stratus_forbidden_subscription"]


def test_an_empty_or_partial_listing_is_never_an_absence():   # M5
    assert _codes(sees_subscription=False) == ["stratus_identity_unprovable"]


def test_a_right_beyond_the_closed_role_is_passive():
    assert _codes(role_actions=lambda _id: CLOSED + ["microsoft.authorization/roleassignments/write"]) \
        == ["stratus_unlisted_right"]


def test_a_wildcard_is_more_than_the_closed_role():
    assert _codes(role_actions=lambda _id: ["microsoft.compute/*"]) == ["stratus_unlisted_right"]


def test_an_authorization_action_is_more_than_the_closed_role():
    # the one family the closed role must never hold (granting itself roles): not in the allow-list.
    assert _codes(role_actions=lambda _id: ["microsoft.authorization/roleassignments/write"]) \
        == ["stratus_unlisted_right"]


def test_an_assignment_outside_the_dedicated_subscription_is_passive():
    assert _codes(assignments=[_assign(f"/subscriptions/{BENCH_SUB}")]) == ["stratus_outside_subscription"]


def test_a_role_that_cannot_be_read_is_not_proven_the_closed_role():
    assert _codes(role_actions=lambda _id: []) == ["stratus_unlisted_right"]


def test_a_subscription_that_is_not_cold_is_passive():   # M6
    assert _codes(groups=["NetworkWatcherRG", "srt-vmrc-rg-abc"]) == ["stratus_not_cold"]


def test_the_groups_azure_creates_itself_do_not_break_cold():
    assert _codes(groups=["NetworkWatcherRG", "DefaultResourceGroup-westus",
                          "defaultresourcegroup-eastus"]) == []


def test_a_missing_or_dead_diagnostic_is_passive():
    assert _codes(diag_ok=False) == ["stratus_diagnostic_missing"]


def test_several_broken_guarantees_each_show():
    codes = _codes(groups=["evil-rg"], diag_ok=False, sees_subscription=False)
    assert set(codes) == {"stratus_identity_unprovable", "stratus_not_cold",
                          "stratus_diagnostic_missing"}


# ── the protected set: Orodruin's own always, plus the operator's declared list ─────────────

def test_protected_always_holds_orodruins_own_subscription():
    assert orodruin.protected_subscriptions({"AZURE_SUBSCRIPTION_ID": "ABC"}) == frozenset({"abc"})


def test_protected_adds_the_operators_declared_subscriptions():
    env = {"AZURE_SUBSCRIPTION_ID": "a", "EREGION_PROTECTED_SUBSCRIPTIONS": "B, c "}
    assert orodruin.protected_subscriptions(env) == frozenset({"a", "b", "c"})


# ── read_stratus: inert without its subscription; two tokens; a forbidden one refused first ──

def _tok(oid):
    payload = base64.urlsafe_b64encode(json.dumps({"oid": oid}).encode()).decode().rstrip("=")
    return f"h.{payload}.s"


def test_read_stratus_is_inert_without_its_subscription():
    assert orodruin.read_stratus(env={}) == []


def test_read_stratus_refuses_a_forbidden_subscription_before_any_token_or_read():
    def get(*a, **k):
        raise AssertionError("no read on a forbidden subscription")
    cred = MagicMock()
    cred.get_token.side_effect = AssertionError("no token for a forbidden subscription")
    env = {"EREGION_STRATUS_SUBSCRIPTION": BENCH_SUB, "AZURE_SUBSCRIPTION_ID": BENCH_SUB}
    missing = orodruin.read_stratus(env=env, get=get, orodruin_credential=cred,
                                    stratus_credential=cred)
    assert [m["code"] for m in missing] == ["stratus_forbidden_subscription"]


def _reading_get(role_actions=None, groups=("NetworkWatcherRG",), diag=True):
    acts = list(CLOSED) if role_actions is None else role_actions

    def get(url, headers, params, timeout):
        r = MagicMock(ok=True)
        rel = url[len(orodruin.ARM):]
        if url.endswith("/roleAssignments"):
            r.json.return_value = {"value": [_assign(f"/subscriptions/{STRATUS_SUB}", _ROLE)]}
        elif rel == f"/subscriptions/{STRATUS_SUB}/providers/Microsoft.Authorization/permissions":
            r.json.return_value = {"value": [{"actions": ["Microsoft.Authorization/roleAssignments/read"]}]}
        elif rel == _ROLE:
            r.json.return_value = {"properties": {"permissions": [{"actions": acts}]}}
        elif url.endswith("/resourcegroups"):
            r.json.return_value = {"value": [{"name": g} for g in groups]}
        elif url.endswith("/diagnosticSettings"):
            r.json.return_value = {"value": [{"properties": {"workspaceId": "w"}}] if diag else []}
        else:
            raise AssertionError(f"unexpected url {url}")
        return r
    return get


def test_read_stratus_reads_a_with_orodruins_token_b_with_stratuss_and_arms():
    o = MagicMock()
    o.get_token.return_value.token = _tok("oid-orodruin")
    s = MagicMock()
    s.get_token.return_value.token = _tok("oid-stratus")
    seen = []
    base = _reading_get()

    def get(url, headers, params, timeout):
        seen.append((url, headers["Authorization"], params))
        return base(url, headers, params, timeout)

    env = {"EREGION_STRATUS_SUBSCRIPTION": STRATUS_SUB, "AZURE_SUBSCRIPTION_ID": BENCH_SUB}
    missing = orodruin.read_stratus(env=env, get=get, orodruin_credential=o, stratus_credential=s)
    assert [m["code"] for m in missing] == []       # armed
    # (a) Stratus's assignments filtered by Stratus's oid, read with Orodruin's token
    ra = next(c for c in seen if c[0].endswith("/roleAssignments"))
    assert ra[2]["$filter"] == "assignedTo('oid-stratus')"
    assert ra[1] == f"Bearer {_tok('oid-orodruin')}"
    # (b) the resource groups read with Stratus's token
    rg = next(c for c in seen if c[0].endswith("/resourcegroups"))
    assert rg[1] == f"Bearer {_tok('oid-stratus')}"


def test_read_stratus_is_passive_when_stratus_holds_more_than_its_closed_role():
    o = MagicMock()
    o.get_token.return_value.token = _tok("o")
    s = MagicMock()
    s.get_token.return_value.token = _tok("s")
    get = _reading_get(role_actions=list(CLOSED) + ["microsoft.authorization/roleassignments/write"])
    env = {"EREGION_STRATUS_SUBSCRIPTION": STRATUS_SUB, "AZURE_SUBSCRIPTION_ID": BENCH_SUB}
    missing = orodruin.read_stratus(env=env, get=get, orodruin_credential=o, stratus_credential=s)
    assert [m["code"] for m in missing] == ["stratus_unlisted_right"]


# ── check: the stratus guarantee makes the contract passive; a partial reader set is fine ────

def test_check_is_passive_when_the_stratus_guarantee_is_missing():
    readers = {"identity": lambda: [], "graph": lambda: [], "network": lambda: [],
               "cap": lambda: ([], {"max_injections": 20, "max_run_s": 3600}),
               "stratus": lambda: [orodruin._miss("stratus_not_cold", "x")]}
    verdict = orodruin.check(readers)
    assert not verdict.armed and verdict.missing[0]["code"] == "stratus_not_cold"


def test_check_still_arms_with_a_reader_set_that_has_no_stratus():
    # a partial set (the existing tests): "stratus" absent is skipped, never a KeyError.
    readers = {"identity": lambda: [], "graph": lambda: [], "network": lambda: [],
               "cap": lambda: ([], {"max_injections": 20, "max_run_s": 3600})}
    assert orodruin.check(readers).armed


# ── read_sandbox: the DOCKER-USER rule that cuts the IMDS from Stratus's network (pièce 3) ──

_DROP = f"-A DOCKER-USER -s {orodruin.SANDBOX_NET} -d {orodruin.IMDS_ADDR}/32 -j DROP"


def test_the_sandbox_rule_drops_the_net_to_the_imds():
    assert orodruin.sandbox_drops_imds(f"-N DOCKER-USER\n{_DROP}\n-A DOCKER-USER -j RETURN")


def test_a_drop_to_another_destination_does_not_count():
    assert not orodruin.sandbox_drops_imds(
        f"-A DOCKER-USER -s {orodruin.SANDBOX_NET} -d 8.8.8.8 -j DROP")


def test_a_drop_from_another_network_does_not_count():
    assert not orodruin.sandbox_drops_imds(
        f"-A DOCKER-USER -s 10.0.0.0/24 -d {orodruin.IMDS_ADDR}/32 -j DROP")


def test_an_accept_to_the_imds_does_not_count():
    assert not orodruin.sandbox_drops_imds(
        f"-A DOCKER-USER -s {orodruin.SANDBOX_NET} -d {orodruin.IMDS_ADDR} -j ACCEPT")


def test_read_sandbox_is_inert_without_its_subscription():
    assert orodruin.read_sandbox(env={}) == []


def test_read_sandbox_arms_when_the_proof_is_fresh_and_the_rule_is_present():
    # decision A: the root service's proof file (iptables -S DOCKER-USER), fresh, with the DROP rule.
    env = {"EREGION_STRATUS_SUBSCRIPTION": STRATUS_SUB}
    assert orodruin.read_sandbox(
        env=env, read_proof=lambda: (f"-N DOCKER-USER\n{_DROP}", 1000.0),
        now=lambda: 1000.0) == []


def test_read_sandbox_flags_a_missing_rule():
    env = {"EREGION_STRATUS_SUBSCRIPTION": STRATUS_SUB}
    missing = orodruin.read_sandbox(
        env=env, read_proof=lambda: ("-N DOCKER-USER\n-A DOCKER-USER -j RETURN", 1000.0),
        now=lambda: 1000.0)
    assert [m["code"] for m in missing] == ["stratus_sandbox_open"]


def test_read_sandbox_refuses_a_stale_proof():
    # the timer has not refreshed the proof → the rule is not proven now → fail closed.
    env = {"EREGION_STRATUS_SUBSCRIPTION": STRATUS_SUB}
    missing = orodruin.read_sandbox(
        env=env, read_proof=lambda: (f"-N DOCKER-USER\n{_DROP}", 1000.0),
        now=lambda: 1000.0 + orodruin.SANDBOX_PROOF_MAX_AGE_S + 1)
    assert [m["code"] for m in missing] == ["stratus_sandbox_stale"]


def test_read_sandbox_fails_closed_when_the_proof_cannot_be_read():
    def boom():
        raise PermissionError("no proof file")
    env = {"EREGION_STRATUS_SUBSCRIPTION": STRATUS_SUB}
    missing = orodruin.read_sandbox(env=env, read_proof=boom)
    assert [m["code"] for m in missing] == ["stratus_sandbox_unreadable"]


# ── the allow-list held EQUAL to the Terraform's closed role (R2BGc) ─────────────────────────

_GUARDRAILS = (Path(__file__).resolve().parents[2] / "infra" / "orodruin"
               / "stratus_guardrails.tf").read_text(encoding="utf-8")


def _block(source, header):
    """The body of an HCL ``resource "<type>" "<name>"`` block — balanced braces."""
    start = source.index(header)
    depth, opened = 0, False
    for i in range(start, len(source)):
        if source[i] == "{":
            depth, opened = depth + 1, True
        elif source[i] == "}":
            depth -= 1
            if opened and depth == 0:
                return source[start:i + 1]
    raise AssertionError(f"bloc non terminé : {header}")


def test_the_contract_allow_list_equals_the_terraform_closed_role():
    block = _block(_GUARDRAILS, 'resource "azurerm_role_definition" "stratus_closed"')
    m = re.search(r"\bactions\s*=\s*\[(.*?)\]", block, re.DOTALL)
    assert m, "actions list not found in the closed role"
    tf_actions = {a.lower() for a in re.findall(r'"([^"]+)"', m.group(1))}
    assert tf_actions == set(orodruin.STRATUS_CLOSED_ROLE_ACTIONS)
