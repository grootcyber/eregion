"""Orodruin's contract (O1): the host an injector acts from arms itself only if its
guardrails hold — otherwise the injector stays passive and touches nothing.

        guarantee         checked by (nothing is written)
        identity          its role assignments, at every scope, all inside the bench's
                          resource group (but the two channels'); its effective rights
                          there cover what the injectors read; what they write, granted at
                          the scope of a VM or an experiment of it, never on the whole
                          group (which VMs: Terraform's choice, by their tags — the
                          contract does not read their inscription; O0 does, at each run);
                          and nothing else: what it holds is an allow-list (SEC11)
        graph             its Microsoft Graph token: no right there but the identity guard's
                          reads (GRAPH_READ_ONLY, IDI1), no directory role, no user's
        network           a connection outside the perimeter fails
        cap               the declared cap is read and compared to the ceiling
        kill              revoke the identity, cancel the chaos experiments, stop the
                          VM, close the exercise windows — ``kill``
        audit             every injector call is journaled BEFORE it runs — ``Session``

Targets stay the inscription's business (``eregion_core/inscription.py``, O0): the two
are independent and add up. A contract that cannot be read is ``passive``, never
``armed`` by default — fail closed. Run anywhere but on an armed Orodruin (an operator's
laptop: rights on the whole subscription, open egress), the same checks fail, so an
injector there stays passive: the contract itself is the gate, no host flag to forget.

Design: ``docs/design/orodruin-contract.md``.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from eregion_core.exercise import MAX_DURATION_S
from eregion_core.inscription import token_claims

ARMED, PASSIVE = "armed", "passive"

ARM = "https://management.azure.com"
API_VERSION = "2022-04-01"

# What the injectors ask of Azure on the bench: Annatar on a VM (annatar/executors/
# azure_vm.py), Gothmog on a Chaos Studio experiment (gothmog/engines/chaos_studio.py —
# it starts the experiment; the experiment's own identity acts on the VM).
# SEC5 (V-29, #182): they READ the bench's group; they WRITE only on what is enrolled — each
# VM, each experiment, a role assignment at its own scope (infra/orodruin/main.tf). A write
# right on the whole group (a VM not enrolled, the pre-observation's, would be in reach) is a
# missing guarantee: passive.
READ_ACTIONS = (
    "Microsoft.Resources/subscriptions/resourceGroups/read",
    "Microsoft.Compute/virtualMachines/read",
    "Microsoft.Network/networkSecurityGroups/read",
    # DG-b review: whether Glorfindel holds a VM is read on the NSGs of its NICs and of their
    # subnets (eregion_core/held.py) — the NICs and the subnets read to find them.
    "Microsoft.Network/networkInterfaces/read",
    "Microsoft.Network/virtualNetworks/subnets/read",
    "Microsoft.Chaos/experiments/read",
    "Microsoft.Chaos/experiments/executions/read",
)
VM_ACTIONS = (
    "Microsoft.Compute/virtualMachines/start/action",
    "Microsoft.Compute/virtualMachines/runCommand/action",
)
CHAOS_ACTIONS = (
    "Microsoft.Chaos/experiments/start/action",
    "Microsoft.Chaos/experiments/cancel/action",
)
WRITE_ACTIONS = VM_ACTIONS + CHAOS_ACTIONS
REQUIRED_ACTIONS = READ_ACTIONS + WRITE_ACTIONS
# The resource type each write is granted on — its scope, inside the bench.
_WRITE_SCOPE = {**{a: "/providers/microsoft.compute/virtualmachines/" for a in VM_ACTIONS},
                **{a: "/providers/microsoft.chaos/experiments/" for a in CHAOS_ACTIONS}}
# Log Analytics Reader as Azure defines it — the built-in role infra/orodruin/main.tf gives on
# the bench's workspace: Gothmog reads its fault's effect there, through ARM. At a workspace's
# scope these reach that workspace only (a support ticket is the subscription's, out of reach).
# Its actions, and its data action (read_identity marks it "data:"); its notAction (the shared
# keys) only narrows it.
LOGS_READER_ACTIONS = (
    "*/read",
    "Microsoft.OperationalInsights/workspaces/analytics/query/action",
    "Microsoft.OperationalInsights/workspaces/search/action",
    "Microsoft.Support/*",
)
LOGS_READER_DATA_ACTIONS = (
    "Microsoft.OperationalInsights/workspaces/jobs/export/action",
)
# SEC11 (V-29): what the identity may HOLD inside the bench, by the kind of scope a role is
# assigned at — an allow-list, not a list of what is refused. Every action of the role must be
# one of these, as written (a wildcard is not expanded): any other right, a data action, a role
# that cannot be read, is a missing guarantee (A0: an unknown right refuses). Network
# Contributor on the group, which grants none of the injectors' writes, refuses too.
_HELD_AT = (("/providers/microsoft.compute/virtualmachines/", VM_ACTIONS),
            ("/providers/microsoft.chaos/experiments/", CHAOS_ACTIONS),
            ("/providers/microsoft.operationalinsights/workspaces/",
             LOGS_READER_ACTIONS + tuple(f"data:{a}" for a in LOGS_READER_DATA_ACTIONS)))
# The one kind of assignment allowed outside the bench: reading role assignments, so
# the identity can prove it holds nothing else (a read at the bench's scope cannot see
# the subscription's).
AUTHZ_READ_ONLY = frozenset({
    "microsoft.authorization/roleassignments/read",
    "microsoft.authorization/roledefinitions/read",
})

# IDI1 (#546): what the identity may hold in Microsoft Graph — reading applications and their
# principals (Application.Read.All), and the directory's role assignments, active and eligible
# (RoleManagement.Read.Directory: a privileged identity is never enrolled), for the identity guard
# (eregion_core/inscription.py, GraphEnrollment) — and nothing else: no write there, no other API
# permission, no directory role. Read from the identity's own Graph token, its app roles
# (``roles``) and its directory roles (``wids``): no Graph call, no right needed to read it.
#
# A directory role (a ``wids`` outside ``APP_DEFAULT_WIDS``) is passive, the Graph read declared or
# not (IDI1s, #559): the hypothesis on ``wids`` was measured on 05/11. The declaration still
# decides two things, and only those — GRAPH_DECLARED_ENV.
GRAPH = "https://graph.microsoft.com"
GRAPH_READ_ONLY = frozenset({"Application.Read.All", "RoleManagement.Read.Directory"})
# The ``wids`` value of an app-only token whose principal holds no directory role (published decoded
# tokens of managed identities) — not a built-in role's template id. Measured on 05/11 (#559): the
# first orodruin-check after v0.5.6, armed, said nothing of Graph — the token of Orodruin's managed
# identity carries no ``wids``, or this one alone. Any other value is a role: passive. Microsoft does
# not document this value: should it change on their side, the contract turns passive — closed (A0),
# never armed on a value nobody read.
APP_DEFAULT_WIDS = frozenset({"0997a1d0-0d1d-4acb-b408-d5ca73121e90"})
# The Graph read is declared when orodruin.env names the bench's tenant (``EREGION_TENANT_ID``, the
# step that makes the identity guard read Entra ID). It decides two things, and only those:
# - an app role in the token: undeclared, any one is a right nobody declared
#   (``graph_undeclared_right``); declared, the guard's two reads (``GRAPH_READ_ONLY``) hold;
# - a Graph token that cannot be had: declared, passive (``graph_unreadable``) — the guard reads
#   Graph with that very token, and a declared read that cannot happen is a contract unread;
#   undeclared, only said (``Verdict.notes``): an Orodruin without a Graph right must not fall over a
#   Graph it never reads, and having no token is no privilege — nothing uses what cannot be had.
GRAPH_DECLARED_ENV = "EREGION_TENANT_ID"

# Outside the perimeter (bench control plane, Entra ID, the model's API): reaching any
# of these means the egress is open. Addresses, not names — DNS stays allowed.
NETWORK_PROBES = (("1.1.1.1", 443), ("9.9.9.9", 443))
PROBE_TIMEOUT_S = 3.0

# Ceilings the declared cap may not exceed. A run outliving an exercise window would
# leave its tail unlabelled (eregion_core/exercise.py).
CEILING_INJECTIONS = 20
CEILING_RUN_S = MAX_DURATION_S

# The exercise channel (eregion_core/exercise_channel.py): the identity writes the windows
# to one blob container of its own. That assignment is allowed outside the bench only if
# its scope IS that container — a scope that bounds it whatever the role.
CHANNEL_SCOPE_ENV = "EREGION_CHANNEL_SCOPE"
_CONTAINER_SCOPE = re.compile(
    r"^/subscriptions/[^/]+/resourcegroups/[^/]+/providers/microsoft\.storage"
    r"/storageaccounts/[^/]+/blobservices/default/containers/[^/]+$")

# The return channel (eregion_core/watch_channel.py, #159): the hosted watch writes its
# heartbeat and detections to a container the identity may READ, never write — an
# injector never writes what the watch says. Allowed outside the bench only at that
# container's scope, and only with a read-only role.
WATCH_SCOPE_ENV = "EREGION_WATCH_CHANNEL_SCOPE"
BLOB_READ_ONLY = frozenset({
    "microsoft.storage/storageaccounts/blobservices/containers/read",
    "microsoft.storage/storageaccounts/blobservices/generateuserdelegationkey/action",
    "data:microsoft.storage/storageaccounts/blobservices/containers/blobs/read",
})

BENCH_RG_ENV = "EREGION_BENCH_RG"
DEFAULT_BENCH_RG = "rg-celebrimbor"
AUDIT_ENV = "EREGION_AUDIT_FILE"
MAX_INJECTIONS_ENV = "EREGION_MAX_INJECTIONS"
MAX_RUN_S_ENV = "EREGION_MAX_RUN_S"


class Passive(RuntimeError):
    """An injector call without an armed contract — refused, nothing touched."""


class CapReached(RuntimeError):
    """The run already made as many injector calls as its declared cap allows."""


@dataclass
class Verdict:
    verdict: str
    missing: list[dict] = field(default_factory=list)
    cap: dict = field(default_factory=dict)
    # What orodruin-check says without being a missing guarantee (IDI1: a Graph hypothesis not
    # measured yet) — never published, never arms nor disarms.
    notes: list[dict] = field(default_factory=list)

    @property
    def armed(self) -> bool:
        return self.verdict == ARMED

    def reasons(self) -> str:
        return "; ".join(f"{m['code']}: {m['detail']}" for m in self.missing)


# A detail is shown (orodruin-check, a passive run's reasons): a scope or a URL in it never
# names the subscription (seen on the bench, 26/10, in an unreadable listing's URL).
_SUBSCRIPTION_PART = re.compile(r"/subscriptions/[^/\s'\"]+", re.IGNORECASE)


def _miss(code: str, detail: str) -> dict:
    return {"code": code, "detail": _SUBSCRIPTION_PART.sub("/subscriptions/…", detail)}


def _note(code: str, detail: str) -> dict:
    """What a reader says without it being a missing guarantee: kept apart by ``check``."""
    return {**_miss(code, detail), "said": True}


# ── Readers — each returns what is missing (empty: the guarantee holds) ───────────────

def bench_scope(subscription_id: str, bench_rg: str) -> str:
    return f"/subscriptions/{subscription_id}/resourceGroups/{bench_rg}"


def _inside(scope: str, bench: str) -> bool:
    s, b = scope.lower().rstrip("/"), bench.lower().rstrip("/")
    return s == b or s.startswith(b + "/")


def channel_scope(env=None, name: str = CHANNEL_SCOPE_ENV) -> str:
    """The declared channel container, or "" — anything but a container's scope is ignored
    (a declared subscription must never become an allowed assignment)."""
    env = os.environ if env is None else env
    scope = (env.get(name) or "").strip().rstrip("/")
    return scope if _CONTAINER_SCOPE.match(scope.lower()) else ""


def watch_scope(env=None) -> str:
    """The declared return-channel container (#159), or "" — same shape check."""
    return channel_scope(env, WATCH_SCOPE_ENV)


def _token_oid(token: str) -> str:
    """The principal the token was issued to — who this host IS, read from the token
    itself rather than from a setting that could drift."""
    return token_claims(token)["oid"]


def _allowed(action: str, perms: list[dict]) -> bool:
    a = action.lower()
    return any(
        any(fnmatch.fnmatch(a, x.lower()) for x in (p.get("actions") or []))
        and not any(fnmatch.fnmatch(a, x.lower()) for x in (p.get("notActions") or []))
        for p in perms
    )


def allowed_at(scope: str, bench: str) -> frozenset[str]:
    """What a role assigned at ``scope``, inside ``bench``, may hold (lower case): on the group
    itself, the injectors' reads; on one of its VMs, experiments or workspaces, that kind's
    rights besides — the reads there are narrower than the group's (SEC11, V-29)."""
    reads = frozenset(a.lower() for a in READ_ACTIONS)
    rest = scope.lower().rstrip("/")[len(bench.rstrip("/")):]
    for kind, actions in _HELD_AT:
        if rest.startswith(kind) and rest[len(kind):] and "/" not in rest[len(kind):]:
            return reads | {a.lower() for a in actions}
    return reads


def _grants(action: str, actions: set[str]) -> bool:
    """A role's actions (lower case, as ``role_actions`` lists them) grant ``action``."""
    a = action.lower()
    return any(fnmatch.fnmatch(a, x) for x in actions if not x.startswith("data:"))


def assess_identity(assignments: list[dict], role_actions: Callable[[str], list[str]],
                    perms: list[dict], bench: str, *, sees_subscription: bool,
                    channel: str = "", watch: str = "", experiments: bool = True) -> list[dict]:
    """The identity guarantee from what was read: every assignment inside the bench (or a
    pure role-assignment read, the exercise channel's container, a read-only role on the
    return channel's), and the injectors' actions allowed on the bench.

    Azure lists only the assignments the caller may read (measured on the bench, 19/10:
    with read rights on the workspace alone, the listing showed that one and hid the
    bench's). A listing is proof of absence only if the identity reads role assignments
    over the whole subscription — otherwise nothing is proven (``contract_reader``)."""
    missing = []
    if not sees_subscription:
        missing.append(_miss("identity_unprovable",
                             "cannot read role assignments over the subscription: an assignment "
                             "elsewhere would not be listed (contract_reader)"))
    granted_on: dict[str, list[str]] = {a: [] for a in WRITE_ACTIONS}
    for a in assignments:
        props = a.get("properties") or {}
        scope = props.get("scope") or ""
        if _inside(scope, bench):
            # SEC5 (V-29): a write on the group itself reaches every VM of it, enrolled or not.
            actions = {x.lower() for x in role_actions(props.get("roleDefinitionId") or "")}
            wide = [w for w in WRITE_ACTIONS if _grants(w, actions)]
            if scope.lower().rstrip("/") == bench.lower().rstrip("/") and wide:
                missing.append(_miss("identity_group_wide",
                                     f"{', '.join(wide)} on the whole of {bench}: a write right "
                                     "goes on each enrolled VM or experiment, never on the group"))
                continue
            # SEC11 (V-29): an allow-list — nothing it holds there but what the injectors need.
            unlisted = sorted(actions - allowed_at(scope, bench)) if actions else ["(role unreadable)"]
            if unlisted:
                missing.append(_miss("identity_unlisted_right",
                                     f"{', '.join(unlisted)} at {scope}: not a right the injectors "
                                     "need there"))
                continue
            for w in wide:
                if _WRITE_SCOPE[w] in scope.lower():
                    granted_on[w].append(scope)
            continue
        actions = {x.lower() for x in role_actions(props.get("roleDefinitionId") or "")}
        # Checked before the exercise channel: declared on the same container, the
        # return channel still refuses a writer.
        if watch and scope.lower().rstrip("/") == watch.lower():
            if actions and actions <= BLOB_READ_ONLY:
                continue
            missing.append(_miss("identity_outside_bench",
                                 f"role assignment at {scope} is not read-only (the watch's channel)"))
            continue
        if channel and scope.lower().rstrip("/") == channel.lower():
            continue  # the exercise channel's own container
        if actions and actions <= AUTHZ_READ_ONLY:
            continue
        missing.append(_miss("identity_outside_bench", f"role assignment at {scope}"))
    for action in READ_ACTIONS:
        if not _allowed(action, perms):
            missing.append(_miss("identity_missing_right", f"{action} on {bench}"))
    # Read over the group, a write there: from an assignment above it, or one the listing
    # did not show — never on the group (SEC5, V-29).
    wide = [w for w in WRITE_ACTIONS if _allowed(w, perms)]
    if wide and not any(m["code"] == "identity_group_wide" for m in missing):
        missing.append(_miss("identity_group_wide",
                             f"{', '.join(wide)} effective on the whole of {bench}"))
    # SEC11 (V-29): what is effective on the group — from an assignment on it, above it, or one
    # the listing did not show — is the reads, and the role-assignment read of the contract.
    held = frozenset(a.lower() for a in READ_ACTIONS) | AUTHZ_READ_ONLY
    writes = {w.lower() for w in WRITE_ACTIONS}
    extra = sorted({x for p in perms for x in (p.get("actions") or [])
                    if x.lower() not in held and x.lower() not in writes}
                   | {f"data:{x}" for p in perms for x in (p.get("dataActions") or [])})
    if extra:
        missing.append(_miss("identity_unlisted_right",
                             f"{', '.join(extra)} effective on the whole of {bench}: not a right "
                             "the injectors need"))
    for action, scopes in granted_on.items():
        # No experiment in the group (Celebrimbor's chaos is off by default): nothing to start
        # or cancel, and Gothmog finds no experiment to run — the chaos rights are not asked.
        if not scopes and (experiments or action not in CHAOS_ACTIONS):
            missing.append(_miss("identity_missing_right",
                                 f"{action} on no enrolled resource of {bench}"))
    return missing


CHAOS_API = "2024-01-01"


# The codes ARM answers for a resource provider the subscription never registered: Chaos Studio
# off on a subscription is no experiment, whatever the status (SEC7: ARM's documented answer is
# MissingSubscriptionRegistration, a 409; NoRegisteredProviderFound, a 400 — to measure).
UNREGISTERED_PROVIDER = ("MissingSubscriptionRegistration", "NoRegisteredProviderFound")


def _error_code(r) -> str:
    try:
        body = r.json()
    except Exception:
        return ""
    err = body.get("error") if isinstance(body, dict) else None
    return str(err.get("code") or "") if isinstance(err, dict) else ""


def _has_experiments(get, headers: dict, bench: str) -> bool:
    """Does the bench's group hold a Chaos Studio experiment? A provider not registered in the
    subscription (UNREGISTERED_PROVIDER, read in the error's code, whatever the status) or no
    such collection (404): none. Any other failure raises — the contract is then unreadable,
    passive."""
    r = get(f"{ARM}{bench}/providers/Microsoft.Chaos/experiments", headers=headers,
            params={"api-version": CHAOS_API}, timeout=20)
    if r.status_code == 404 or (not r.ok and _error_code(r) in UNREGISTERED_PROVIDER):
        return False
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} listing the bench's experiments")
    return bool(r.json().get("value"))


def read_identity(*, credential=None, get=None) -> list[dict]:
    """Role assignments of this host's identity at every scope, and its effective rights
    on the bench — two reads (proving an absence takes the first)."""
    import requests

    if credential is None:
        from azure.identity import DefaultAzureCredential
        credential = DefaultAzureCredential()
    get = get or requests.get
    sub = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not sub:
        raise RuntimeError("AZURE_SUBSCRIPTION_ID is not set")
    bench = bench_scope(sub, os.environ.get(BENCH_RG_ENV) or DEFAULT_BENCH_RG)
    token = credential.get_token(f"{ARM}/.default").token
    headers = {"Authorization": f"Bearer {token}"}

    def pages(url: str, params: dict | None) -> list[dict]:
        out: list[dict] = []
        while url:
            # The token goes to Azure Resource Manager only (SEC8): a next page elsewhere is
            # refused, never followed — the contract then unreadable, passive.
            if not url.startswith(ARM + "/"):
                raise RuntimeError("a listing's next page outside Azure Resource Manager: refused")
            r = get(url, headers=headers, params=params, timeout=20)
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code} on {url.split('?')[0]}")
            body = r.json()
            out += body.get("value") or []
            url, params = body.get("nextLink"), None
        return out

    oid = _token_oid(token)
    assignments = pages(
        f"{ARM}/subscriptions/{sub}/providers/Microsoft.Authorization/roleAssignments",
        {"api-version": API_VERSION, "$filter": f"assignedTo('{oid}')"},
    )

    read_roles: dict[str, list[str]] = {}

    def role_actions(definition_id: str) -> list[str]:
        if definition_id in read_roles:  # one read per role: the same on every enrolled VM
            return read_roles[definition_id]
        from eregion_core.held import arm_relative
        try:
            # An id read from a listing: a path under ARM, or not read at all (SEC8) — the
            # token never goes where the id would point it.
            path = arm_relative(definition_id)
        except ValueError:
            return []  # unreadable: not proven read-only, so it counts as outside
        r = get(f"{ARM}{path}", headers=headers,
                params={"api-version": API_VERSION}, timeout=20)
        if not r.ok:
            return []  # unreadable: not proven read-only, so it counts as outside
        perms = (r.json().get("properties") or {}).get("permissions") or []
        # Data actions marked "data:": never mistaken for a role-assignment read.
        read_roles[definition_id] = [x for p in perms for x in (p.get("actions") or [])] + \
            [f"data:{x}" for p in perms for x in (p.get("dataActions") or [])]
        return read_roles[definition_id]

    perms = pages(f"{ARM}{bench}/providers/Microsoft.Authorization/permissions",
                  {"api-version": API_VERSION})
    sub_perms = pages(f"{ARM}/subscriptions/{sub}/providers/Microsoft.Authorization/permissions",
                      {"api-version": API_VERSION})
    return assess_identity(
        assignments, role_actions, perms, bench,
        sees_subscription=_allowed("Microsoft.Authorization/roleAssignments/read", sub_perms),
        channel=channel_scope(), watch=watch_scope(),
        experiments=_has_experiments(get, headers, bench))


def graph_declared(env=None) -> bool:
    """Is Orodruin's Graph read declared — orodruin.env naming the bench's tenant (IDI1)?"""
    env = os.environ if env is None else env
    return bool((env.get(GRAPH_DECLARED_ENV) or "").strip())


def assess_graph(claims: dict, *, declared: bool = True) -> list[dict]:
    """The Graph guarantee from the claims of the identity's own Graph token (IDI1): an app's
    token (a user's carries ``scp``), its app roles within ``GRAPH_READ_ONLY``, no directory
    role (``wids``, but ``APP_DEFAULT_WIDS``). An unknown right refuses (A0). A directory role
    refuses declared or not (IDI1s, #559); undeclared, any app role is a right nobody declared
    (``graph_undeclared_right``)."""
    missing = []
    if claims.get("scp") or not isinstance(claims.get("roles", []), list) \
            or not isinstance(claims.get("wids", []), list):
        missing.append(_miss("graph_unlisted_right",
                             "not an application's token (a user's scopes, or claims of no list)"))
        return missing
    if not declared and claims.get("roles"):
        missing.append(_miss("graph_undeclared_right",
                             f"{', '.join(sorted(str(r) for r in claims['roles']))} in Microsoft Graph, "
                             f"and nobody declared a Graph read ({GRAPH_DECLARED_ENV} not set)"))
    unlisted = sorted({str(r) for r in claims.get("roles") or []} - GRAPH_READ_ONLY)
    if declared and unlisted:
        missing.append(_miss("graph_unlisted_right",
                             f"{', '.join(unlisted)} in Microsoft Graph: the injectors read applications, "
                             "nothing else (graph_read_enabled)"))
    roles = sorted({str(w).lower() for w in claims.get("wids") or []} - APP_DEFAULT_WIDS)
    if roles:
        missing.append(_miss("graph_directory_role",
                             f"directory role {', '.join(roles)}: an injector holds none in Entra ID"))
    return missing


def read_graph(*, credential=None, env=None) -> list[dict]:
    """The identity's own Microsoft Graph token, asked for and read — no Graph call (IMDS gives
    it on Orodruin, Entra ID being in the perimeter). Declared, a token that cannot be had raises
    (unreadable: passive, the identity guard reads Graph with it); undeclared, it is only said —
    an Orodruin without a Graph right does not fall, and having no token is no privilege."""
    declared = graph_declared(env)
    try:
        if credential is None:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
        claims = token_claims(credential.get_token(f"{GRAPH}/.default").token)
    except Exception as e:
        if declared:
            raise
        return [_note("graph_unreadable", f"{type(e).__name__}: {e}"[:200]
                      + " (said: no Graph read declared, and no token is no privilege)")]
    return assess_graph(claims, declared=declared)


def read_network(*, probes=NETWORK_PROBES, connect=None) -> list[dict]:
    """A TCP connection to each probe outside the perimeter must fail."""
    connect = connect or socket.create_connection
    missing = []
    for host, port in probes:
        try:
            conn = connect((host, port), timeout=PROBE_TIMEOUT_S)
        except OSError:
            continue  # refused or timed out: what the perimeter should do
        conn.close()
        missing.append(_miss("network_open", f"{host}:{port} reachable"))
    return missing


def read_cap(env=None) -> tuple[list[dict], dict]:
    """The declared cap, read and compared to the ceilings."""
    env = os.environ if env is None else env
    missing, cap = [], {}
    for name, key, ceiling in ((MAX_INJECTIONS_ENV, "max_injections", CEILING_INJECTIONS),
                               (MAX_RUN_S_ENV, "max_run_s", CEILING_RUN_S)):
        raw = env.get(name)
        if raw in (None, ""):
            missing.append(_miss("cap_missing", f"{name} not declared"))
            continue
        value = int(raw)
        if not 0 < value <= ceiling:
            missing.append(_miss("cap_exceeded", f"{name}={value}, ceiling {ceiling}"))
            continue
        cap[key] = value
    return missing, cap


# ── R2c (#608): the Stratus guarantee — the contract arms FOR Stratus ─────────────────────────
# Active only when EREGION_STRATUS_SUBSCRIPTION names Stratus's dedicated subscription; unset,
# read_stratus returns nothing and the contract stays Orodruin's own, unchanged (non-regression
# measured 19/11: orodruin-check "armed" with the AUTHZ_READ_ONLY role posed, no Stratus env).
# Set, it arms for Stratus only if, on that subscription, Stratus holds NOTHING but its closed
# role, the subscription is cold, and its activity-log diagnostic is routed — read (a) with
# Orodruin's AUTHZ_READ_ONLY token, (b) with Stratus's token, by Orodruin's process outside the
# sandbox (docs/design/stratus-cible.md § 1, "Le code hermétique de R2c").
STRATUS_SUB_ENV = "EREGION_STRATUS_SUBSCRIPTION"
# The Stratus app's client id and the host-fetched assertion mounted into the run (pièce 4B): the
# contract becomes Stratus by the federated exchange to read (b) the groups and the diagnostic.
STRATUS_CLIENT_ID_ENV = "EREGION_STRATUS_CLIENT_ID"
STRATUS_ASSERTION_FILE_ENV = "EREGION_STRATUS_ASSERTION_FILE"
# Subscriptions Stratus must never be armed on: Orodruin's own (AZURE_SUBSCRIPTION_ID) always,
# plus any the operator declares here (comma-separated: the bench, the VM, Imladris, when they
# differ from Orodruin's). EREGION_STRATUS_SUBSCRIPTION equal to one of these is the v1 blocker
# (rights reaching the whole bench) — passive.
PROTECTED_SUBS_ENV = "EREGION_PROTECTED_SUBSCRIPTIONS"

# The closed role's actions (R2BGc, infra/orodruin/stratus_guardrails.tf): the 19 measured
# writes/deletes/actions of the two techniques, the 9 reads the activity log does not trace, the
# 3 joins. The allow-list Stratus may hold on the dedicated subscription and NOTHING else (SEC11,
# like the bench's allowed_at) — any action outside it, a Microsoft.Authorization action, a
# wildcard, is "more than the closed role": passive. Kept EQUAL to the Terraform by a test
# (tests/unit/test_stratus_contract.py), so the contract and the role never drift (Jonathan,
# 19/11: identify the closed role by its actions, never by a role-definition id hardcoded).
STRATUS_CLOSED_ROLE_ACTIONS = frozenset(a.lower() for a in (
    "Microsoft.Compute/disks/delete",
    "Microsoft.Compute/virtualMachines/delete",
    "Microsoft.Compute/virtualMachines/write",
    "Microsoft.Compute/virtualMachines/runCommand/action",
    "Microsoft.Network/bastionHosts/write",
    "Microsoft.Network/bastionHosts/delete",
    "Microsoft.Network/bastionHosts/createShareableLinks/action",
    "Microsoft.Network/bastionHosts/getShareableLinks/action",
    "Microsoft.Network/bastionHosts/deleteShareableLinks/action",
    "Microsoft.Network/networkInterfaces/write",
    "Microsoft.Network/networkInterfaces/delete",
    "Microsoft.Network/publicIPAddresses/write",
    "Microsoft.Network/publicIPAddresses/delete",
    "Microsoft.Network/virtualNetworks/write",
    "Microsoft.Network/virtualNetworks/delete",
    "Microsoft.Network/virtualNetworks/subnets/write",
    "Microsoft.Network/virtualNetworks/subnets/delete",
    "Microsoft.Resources/subscriptions/resourceGroups/write",
    "Microsoft.Resources/subscriptions/resourceGroups/delete",
    "Microsoft.Resources/subscriptions/resourceGroups/read",
    "Microsoft.Network/virtualNetworks/read",
    "Microsoft.Network/virtualNetworks/subnets/read",
    "Microsoft.Network/networkInterfaces/read",
    "Microsoft.Network/publicIPAddresses/read",
    "Microsoft.Network/bastionHosts/read",
    "Microsoft.Compute/virtualMachines/read",
    "Microsoft.Compute/disks/read",
    "Microsoft.Insights/diagnosticSettings/read",
    "Microsoft.Network/virtualNetworks/subnets/join/action",
    "Microsoft.Network/networkInterfaces/join/action",
    "Microsoft.Network/publicIPAddresses/join/action",
))

# The resource groups Azure creates by itself (M6): a subscription "empty but these" is cold.
# NetworkWatcherRG is born with a VNet; DefaultResourceGroup-<region> from Defender /
# DeployIfNotExists. Measured cold on the dedicated subscription 19/11 (RG_COLD: NetworkWatcherRG).
AZURE_OWN_GROUPS = frozenset({"networkwatcherrg"})
AZURE_OWN_GROUP_PREFIXES = ("defaultresourcegroup-",)


def stratus_subscription(env=None) -> str:
    """The dedicated Stratus subscription, or "" — read_stratus is inert without it."""
    env = os.environ if env is None else env
    return (env.get(STRATUS_SUB_ENV) or "").strip()


def protected_subscriptions(env=None) -> frozenset[str]:
    """Subscriptions Stratus must never be armed on (lower case): Orodruin's own
    (AZURE_SUBSCRIPTION_ID) always — the v1 blocker needs no declaration — plus the operator's
    comma-separated list (the bench, the VM, Imladris, when they differ)."""
    env = os.environ if env is None else env
    subs = {(env.get("AZURE_SUBSCRIPTION_ID") or "").strip().lower()}
    subs |= {s.strip().lower() for s in (env.get(PROTECTED_SUBS_ENV) or "").split(",")}
    return frozenset(s for s in subs if s)


def _azure_own_group(name: str) -> bool:
    n = (name or "").strip().lower()
    return n in AZURE_OWN_GROUPS or any(n.startswith(p) for p in AZURE_OWN_GROUP_PREFIXES)


def _on_subscription(scope: str, subscription: str) -> bool:
    s, sub = scope.lower().rstrip("/"), subscription.lower().strip()
    return s == f"/subscriptions/{sub}" or s.startswith(f"/subscriptions/{sub}/")


def assess_stratus(*, subscription: str, protected: frozenset[str], assignments: list[dict],
                   role_actions: Callable[[str], list[str]], sees_subscription: bool,
                   groups: list[str], diag_ok: bool) -> list[dict]:
    """The Stratus guarantee from what was read (docs/design/stratus-cible.md, R2c): on the
    dedicated subscription, Stratus holds NOTHING but its closed role (SEC11 allow-list — any
    action beyond STRATUS_CLOSED_ROLE_ACTIONS, a Microsoft.Authorization action or a wildcard
    among them, is more than the role); the subscription is cold (no group but Azure's own, M6);
    its activity-log diagnostic routes to a live workspace. Passive on a protected subscription
    (the v1 blocker), on an unprovable listing (M5: an empty one is no absence), on a right
    beyond the closed role, on a broken COLD, on a missing diagnostic. Nothing is written."""
    if subscription.lower() in protected:
        # The subscription itself is wrong: nothing read there would mean anything — stop here.
        return [_miss("stratus_forbidden_subscription",
                      "EREGION_STRATUS_SUBSCRIPTION is Orodruin's own, the bench's, the VM's or "
                      "Imladris's — rights there would reach the bench (the v1 blocker)")]
    missing: list[dict] = []
    if not sees_subscription:  # M5: a listing Orodruin cannot fully read is no absence
        missing.append(_miss("stratus_identity_unprovable",
                             "cannot read Stratus's role assignments over the dedicated "
                             "subscription: an assignment elsewhere would not be listed (M5: an "
                             "empty listing is not an absence of rights)"))
    for a in assignments:
        props = a.get("properties") or {}
        scope = props.get("scope") or ""
        if not _on_subscription(scope, subscription):
            missing.append(_miss("stratus_outside_subscription",
                                 f"Stratus holds a role at {scope}: not on its dedicated subscription"))
            continue
        actions = {x.lower() for x in role_actions(props.get("roleDefinitionId") or "")}
        if not actions:
            missing.append(_miss("stratus_unlisted_right",
                                 "Stratus holds a role that cannot be read: not proven to be the "
                                 "closed role"))
            continue
        unlisted = sorted(actions - STRATUS_CLOSED_ROLE_ACTIONS)
        if unlisted:
            missing.append(_miss("stratus_unlisted_right",
                                 f"{', '.join(unlisted)}: Stratus holds more than its closed role"))
    extra = sorted(g for g in groups if not _azure_own_group(g))
    if extra:  # M6: a group beside Azure's own means the subscription is not cold
        missing.append(_miss("stratus_not_cold",
                             f"the dedicated subscription is not cold: {', '.join(extra)}"))
    if not diag_ok:
        missing.append(_miss("stratus_diagnostic_missing",
                             "the activity-log diagnostic setting is absent or routes to no live "
                             "workspace: the watch would be blind to Stratus"))
    return missing


def _stratus_credential(env=None):
    """Stratus's credential, obtained by the federated exchange from Orodruin's process OUTSIDE
    the sandbox (the voulu direction, § 1): a WorkloadIdentityCredential whose subject is
    Orodruin's managed identity (the FIC posed by R2BGc). Built with explicit arguments from
    EREGION_STRATUS_CLIENT_ID, the tenant (EREGION_TENANT_ID) and the assertion file the host
    fetched and mounted into the run (EREGION_STRATUS_ASSERTION_FILE, pièce 4B) — not from the
    azure.identity default AZURE_* names, which nothing sets here. A piece missing raises: the
    guarantee is then missing, never armed (fail closed)."""
    env = os.environ if env is None else env
    from azure.identity import WorkloadIdentityCredential
    client_id = (env.get(STRATUS_CLIENT_ID_ENV) or "").strip()
    tenant_id = (env.get(GRAPH_DECLARED_ENV) or env.get("AZURE_TENANT_ID") or "").strip()
    token_file = (env.get(STRATUS_ASSERTION_FILE_ENV) or "").strip()
    if not (client_id and tenant_id and token_file):
        raise RuntimeError(
            "the Stratus federated credential is incomplete (EREGION_STRATUS_CLIENT_ID, the tenant "
            "EREGION_TENANT_ID, and EREGION_STRATUS_ASSERTION_FILE — the host-fetched assertion "
            "mounted into the run, pièce 4B) — not armed")
    return WorkloadIdentityCredential(
        client_id=client_id, tenant_id=tenant_id, token_file_path=token_file)


def read_stratus(*, orodruin_credential=None, stratus_credential=None, get=None, env=None) -> list[dict]:
    """The Stratus guarantee, read with two tokens (docs/design/stratus-cible.md § 1): (a)
    Stratus's role assignments on the dedicated subscription, and whether Orodruin may read them
    there at all (M5), with Orodruin's AUTHZ_READ_ONLY token; (b) the subscription's resource
    groups (COLD) and its activity-log diagnostic with Stratus's token, by Orodruin's process
    outside the sandbox. Inert (nothing missing) when EREGION_STRATUS_SUBSCRIPTION is unset — the
    contract is Orodruin's own. A forbidden subscription is refused before any token is asked. A
    read that cannot happen raises: the guarantee is then missing (fail closed, see ``check``).
    (API versions confirmed at the real run, ID1 #281; the unit tests inject ``get``.)"""
    import requests
    env = os.environ if env is None else env
    sub = stratus_subscription(env)
    if not sub:
        return []
    protected = protected_subscriptions(env)
    if sub.lower() in protected:
        # Refuse before asking any token for a forbidden subscription (the v1 blocker).
        return assess_stratus(subscription=sub, protected=protected, assignments=[],
                              role_actions=lambda _id: [], sees_subscription=False,
                              groups=[], diag_ok=False)
    get = get or requests.get
    if orodruin_credential is None:
        from azure.identity import DefaultAzureCredential
        orodruin_credential = DefaultAzureCredential()
    if stratus_credential is None:
        stratus_credential = _stratus_credential(env)
    o_headers = {"Authorization": f"Bearer {orodruin_credential.get_token(f'{ARM}/.default').token}"}
    s_token = stratus_credential.get_token(f"{ARM}/.default").token
    s_headers = {"Authorization": f"Bearer {s_token}"}
    stratus_oid = _token_oid(s_token)

    def pages(url: str, params: dict | None, headers: dict) -> list[dict]:
        out: list[dict] = []
        while url:
            if not url.startswith(ARM + "/"):   # SEC8: the token goes to ARM only
                raise RuntimeError("a listing's next page outside Azure Resource Manager: refused")
            r = get(url, headers=headers, params=params, timeout=20)
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code} on {url.split('?')[0]}")
            body = r.json()
            out += body.get("value") or []
            url, params = body.get("nextLink"), None
        return out

    # (a) Stratus's assignments, and Orodruin's right to read them there (M5), with Orodruin's token.
    assignments = pages(
        f"{ARM}/subscriptions/{sub}/providers/Microsoft.Authorization/roleAssignments",
        {"api-version": API_VERSION, "$filter": f"assignedTo('{stratus_oid}')"}, o_headers)
    sub_perms = pages(f"{ARM}/subscriptions/{sub}/providers/Microsoft.Authorization/permissions",
                      {"api-version": API_VERSION}, o_headers)
    sees = _allowed("Microsoft.Authorization/roleAssignments/read", sub_perms)

    read_roles: dict[str, list[str]] = {}

    def role_actions(definition_id: str) -> list[str]:
        if definition_id in read_roles:
            return read_roles[definition_id]
        from eregion_core.held import arm_relative
        try:
            path = arm_relative(definition_id)   # a path under ARM, or not read at all (SEC8)
        except ValueError:
            return []
        r = get(f"{ARM}{path}", headers=o_headers, params={"api-version": API_VERSION}, timeout=20)
        if not r.ok:
            return []
        perms = (r.json().get("properties") or {}).get("permissions") or []
        read_roles[definition_id] = [x for p in perms for x in (p.get("actions") or [])]
        return read_roles[definition_id]

    # (b) the groups (COLD) and the activity-log diagnostic, with Stratus's token.
    groups = [g.get("name") or "" for g in pages(
        f"{ARM}/subscriptions/{sub}/resourcegroups", {"api-version": "2021-04-01"}, s_headers)]
    diags = pages(f"{ARM}/subscriptions/{sub}/providers/microsoft.insights/diagnosticSettings",
                  {"api-version": "2021-05-01-preview"}, s_headers)
    diag_ok = any((d.get("properties") or {}).get("workspaceId") for d in diags)

    return assess_stratus(subscription=sub, protected=protected, assignments=assignments,
                          role_actions=role_actions, sees_subscription=sees, groups=groups,
                          diag_ok=diag_ok)


# ── R2c pièce 3: the hardened sandbox — the IMDS unreachable from Stratus's network ───────────
# At Orodruin's startup a dedicated docker network carries Stratus's egress to ARM, but a
# DOCKER-USER rule drops its traffic to the IMDS (infra/orodruin/main.tf): a Stratus container on
# it cannot obtain Orodruin's managed-identity token (M4: IMDS 000 measured, bridge witness 200).
# orodruin-check reads that rule before arming for Stratus. It cannot read iptables itself — the
# contract runs in a hardened container (ORO_HARDEN: --cap-drop ALL, its own netns) that can neither
# run iptables nor see the host's DOCKER-USER chain. So the root service that poses the rule also
# writes `iptables -S DOCKER-USER` to a proof file and re-poses + rewrites it on a timer; read_sandbox
# reads that mounted file and refuses a stale one (the rule not currently proven) — fail closed. The
# only privileged actor stays the root poser; the sandbox run never gets NET_ADMIN (R2c, decision A).
SANDBOX_NET = "172.30.250.0/24"
IMDS_ADDR = "169.254.169.254"
SANDBOX_PROOF = "/run/eregion-sandbox-rules"
SANDBOX_PROOF_MAX_AGE_S = 180   # the timer rewrites it every ~60s; older than this = not proven now


def _flag_value(parts: list[str], flag: str) -> str:
    try:
        return parts[parts.index(flag) + 1]
    except (ValueError, IndexError):
        return ""


def sandbox_drops_imds(rules: str) -> bool:
    """A line of ``iptables -S DOCKER-USER`` drops the sandbox network's traffic to the IMDS: an
    append to DOCKER-USER, jump DROP, source the sandbox network, destination the IMDS (iptables
    writes the host address as /32)."""
    imds = {IMDS_ADDR, IMDS_ADDR + "/32"}
    for line in rules.splitlines():
        p = line.split()
        if p[:2] != ["-A", "DOCKER-USER"] or _flag_value(p, "-j") != "DROP":
            continue
        if _flag_value(p, "-s") == SANDBOX_NET and _flag_value(p, "-d") in imds:
            return True
    return False


def read_sandbox(*, read_proof=None, env=None, now=None) -> list[dict]:
    """The hardened sandbox read (R2c pièce 3, decision A): the DOCKER-USER rule that cuts the IMDS
    from Stratus's network, proven by the FILE the root service writes — the contract cannot read
    live iptables (it runs with ``--cap-drop ALL`` in its own netns). Inert without
    EREGION_STRATUS_SUBSCRIPTION. A proof that cannot be read, is stale (the timer has not refreshed
    it, so the rule is not proven now), or does not drop the sandbox net to the IMDS is missing —
    never armed on an open sandbox (fail closed, see ``check``). ``read_proof`` and ``now`` are
    injected in the tests."""
    env = os.environ if env is None else env
    if not stratus_subscription(env):
        return []
    if read_proof is None:
        def read_proof():
            p = Path(SANDBOX_PROOF)
            return p.read_text(encoding="utf-8"), p.stat().st_mtime
    if now is None:
        import time
        now = time.time
    try:
        rules, mtime = read_proof()
    except Exception as e:
        return [_miss("stratus_sandbox_unreadable",
                      f"cannot read the sandbox proof {SANDBOX_PROOF}: {type(e).__name__}: {e}"[:200])]
    if now() - mtime > SANDBOX_PROOF_MAX_AGE_S:
        return [_miss("stratus_sandbox_stale",
                      f"the sandbox proof {SANDBOX_PROOF} is older than {SANDBOX_PROOF_MAX_AGE_S}s — "
                      "the root service has not refreshed it; the DROP rule is not proven now")]
    if not sandbox_drops_imds(rules):
        return [_miss("stratus_sandbox_open",
                      f"no DOCKER-USER rule drops {SANDBOX_NET} to the IMDS — a Stratus container "
                      "could reach Orodruin's managed-identity token")]
    return []


READERS = {"identity": read_identity, "graph": read_graph, "network": read_network,
           "cap": read_cap, "stratus": read_stratus, "sandbox": read_sandbox}
# The Stratus guarantees (read_stratus, read_sandbox) protect a Stratus run — the dedicated
# identity's closed role and the sandbox that blocks the IMDS from the sandbox network. They gate
# ONLY an arming FOR Stratus (``check(for_stratus=True)`` / ``arm(..., for_stratus=True)``): the run
# that mounts the federated assertion and the sandbox proof. Every other arming — Gothmog, an
# Annatar VM run, the drill, orodruin-check — arms on the base contract (the current readers minus
# the two Stratus guarantees) and never requires them, even when EREGION_STRATUS_SUBSCRIPTION is set
# in orodruin.env (found at the bench, G1, #1003: ORO_RUN_GOTHMOG mounts neither the assertion nor
# the proof, so they would read unreadable and the run turn passive though Gothmog runs no Stratus).
# A Stratus phase is refused all the same if its session was not armed with them (stratus_host.py),
# so forgetting the flag fails closed, never open.
STRATUS_GUARANTEES = ("stratus", "sandbox")


def check(readers: dict | None = None, *, for_stratus: bool = False) -> Verdict:
    """The contract's guarantees read, nothing written. Armed only if all hold; a reader that
    fails makes its guarantee missing (fail closed). ``for_stratus`` adds the Stratus guarantees
    (the closed role, the sandbox) — only an arming for a Stratus run asks for them; the base
    contract (orodruin-check, Gothmog, an Annatar VM run, the drill) does not (G1, #1003)."""
    if readers is None:
        # Derived from the current READERS (so a test that swaps READERS is honoured), minus the
        # Stratus guarantees unless this arming is for a Stratus run.
        readers = READERS if for_stratus else {k: v for k, v in READERS.items()
                                               if k not in STRATUS_GUARANTEES}
    missing: list[dict] = []
    notes: list[dict] = []
    cap: dict = {}
    for name in ("identity", "graph", "network", "cap", "stratus", "sandbox"):
        reader = readers.get(name)
        if reader is None:   # a test may pass a partial set; "stratus" is inert without its env
            continue
        try:
            result = reader()
        except Exception as e:
            missing.append(_miss(f"{name}_unreadable", f"{type(e).__name__}: {e}"[:300]))
            continue
        if name == "cap":
            result, cap = result
        notes += [{k: v for k, v in m.items() if k != "said"} for m in result if m.get("said")]
        missing += [m for m in result if not m.get("said")]
    return Verdict(PASSIVE if missing else ARMED, missing, cap, notes)


# ── The verdict, published for the console (DG-b) ─────────────────────────────────────

CONTRACT_BLOB = "orodruin/contract.json"
_CODE = re.compile(r"[a-z][a-z0-9_]{0,39}")


def contract_doc(verdict: Verdict, now: datetime | None = None) -> dict:
    """What Orodruin publishes of its contract: armed or passive, the codes of what is missing,
    the time — never a detail (a scope, a group, a subscription), never an identifier."""
    return {"verdict": verdict.verdict, "codes": sorted({m["code"] for m in verdict.missing}),
            "at": (now or datetime.now(timezone.utc)).isoformat()}


def read_contract(doc) -> dict:
    """The verdict as published, or ValueError: exactly its three fields, armed without a code,
    passive with at least one, codes only, an ISO time with its zone."""
    if not isinstance(doc, dict) or set(doc) != {"verdict", "codes", "at"}:
        raise ValueError("not Orodruin's verdict: exactly verdict, codes, at")
    codes = doc["codes"]
    if not isinstance(codes, list) or len(codes) > 20 or not all(isinstance(c, str) and _CODE.fullmatch(c) for c in codes):
        raise ValueError("its codes are not a list of codes")
    if doc["verdict"] not in (ARMED, PASSIVE) or (doc["verdict"] == ARMED) != (not codes):
        raise ValueError("armed without a code, or passive with its codes")
    try:
        at = datetime.fromisoformat(doc["at"]) if isinstance(doc["at"], str) else None
    except ValueError:
        at = None
    if at is None or at.tzinfo is None:
        raise ValueError("its time is not an ISO time with its zone")
    return doc


def publish_contract(verdict: Verdict, **kw) -> bool:
    """The verdict to the exercise channel (``orodruin/contract.json``: the same container, the
    same assignment — no right more), for the watch of Imladris to pull and the console to show.
    False without a channel; a refused write raises to its caller."""
    from eregion_core import exercise_channel
    return exercise_channel.publish_doc(CONTRACT_BLOB, contract_doc(verdict), **kw)


# ── Audit — the journal precedes the call ─────────────────────────────────────────────

def audit_path() -> Path:
    return Path(os.environ.get(AUDIT_ENV) or Path("runs") / "orodruin" / "audit.jsonl")


def _append(path: Path, record: dict) -> None:
    from eregion_core.channel_reader import append_line
    path.parent.mkdir(parents=True, exist_ok=True)
    # On disk before the call: a crash leaves the intent. A whole line, never through a link —
    # in Orodruin's own directory, runs/orodruin/ (SEC16, SEC18).
    append_line(path, json.dumps(record), sync=True)


def push_offhost(run_id: str, line: str, *, created: bool, channel: str | None = None,
                 credential=None, put=None) -> None:
    """One journal line to the exercise channel, off this host (SEC5, V-29): the append blob
    ``audit/<run_id>.jsonl`` — created on the run's first line (never over an existing one),
    then appended to. Raises when the channel refuses: the caller says it."""
    import requests

    from eregion_core import exercise_channel as xc

    url = channel if channel is not None else xc.channel_url()
    if not url:
        return
    if not xc.safe_part(run_id):
        raise ValueError(f"unsafe run id: {run_id!r}")
    put = put or requests.put
    blob = f"{url}/{xc.AUDIT}/{run_id}.jsonl"
    headers = xc.auth_headers(credential, url)
    if not created:
        r = put(blob, headers={**headers, "x-ms-blob-type": "AppendBlob", "If-None-Match": "*"},
                data=b"", timeout=15)
        if not r.ok and r.status_code not in (409, 412):  # there already: append to it
            raise RuntimeError(f"HTTP {r.status_code} creating {xc.AUDIT}/{run_id}.jsonl")
    r = put(blob, headers={**headers, "Content-Type": "application/x-ndjson"},
            params={"comp": "appendblock"}, data=line.encode(), timeout=15)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} appending to {xc.AUDIT}/{run_id}.jsonl")


@dataclass
class Session:
    """An armed run: each injector call goes through ``before_call``, which journals it
    and enforces the cap, before anything reaches Azure. The journal is on this host's disk
    first (fsync), then — with an exercise channel — off it (SEC5, V-29): a host lost or
    wiped keeps its trace in the channel. Off-host is best effort: a push that fails is
    journaled here and said, and the call goes on (refusing it could leave a target
    half-cleaned); it is no defence against a compromised host, which could stop pushing."""
    run_id: str
    injector: str
    max_injections: int
    path: Path = field(default_factory=audit_path)
    calls: int = 0
    offhost: Callable | None = None   # push_offhost unless a test swaps it
    _pushed: bool = False
    # DG-b: the request this run is a wire of — each line says it, and Orodruin counts the
    # request's calls against its cap (eregion_core/exercise_runner.py).
    request: str = ""
    # R2c/#1003: this run is a Stratus run, armed on the Stratus guarantees (the closed role, the
    # sandbox). A Stratus phase refuses without it (annatar/executors/stratus_host.py) — the net
    # that keeps the for_stratus arming from failing open if a path forgets the flag.
    for_stratus: bool = False

    def _journal(self, record: dict) -> None:
        if self.request:
            record = {**record, "request": self.request}
        _append(self.path, record)
        try:
            (self.offhost or push_offhost)(self.run_id, json.dumps(record) + "\n",
                                           created=self._pushed)
            self._pushed = True
        except Exception as e:
            why = f"{type(e).__name__}: {e}"[:300]
            _append(self.path, {**record, "outcome": "offhost_failed", "detail": why})
            print(f"[orodruin] journal line not pushed off the host: {why}")

    def before_call(self, action: str, target: str, detail: str = "") -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(), "run_id": self.run_id,
            "injector": self.injector, "action": action, "target": target, "detail": detail,
        }
        if self.calls >= self.max_injections:
            self._journal({**record, "outcome": "refused_cap"})
            raise CapReached(f"{self.calls} injector calls, cap {self.max_injections}")
        self._journal({**record, "outcome": "about_to_call"})
        self.calls += 1

    def declare(self, what: str, detail: str = "") -> None:
        """A fact of the run, journaled — no call, not counted against the cap. A run
        ``--without-glorfindel`` is written here (SEC5, N-04), not only in its report."""
        self._journal({
            "ts": datetime.now(timezone.utc).isoformat(), "run_id": self.run_id,
            "injector": self.injector, "action": what, "target": "", "detail": detail,
            "outcome": "declared",
        })


def arm(run_id: str, injector: str, verdict: Verdict | None = None,
        request: str = "", *, for_stratus: bool = False) -> tuple[Verdict, Session | None]:
    """The gate at the start of a run: a session only when the contract holds. ``request``: the
    request this run is a wire of (DG-b), written on each line of the journal. ``for_stratus``: a
    Stratus run — the contract is also armed on the Stratus guarantees, and the session carries
    that so a Stratus phase refuses without them (stratus_host.py)."""
    # A for_stratus arming always judges the guarantees itself (ORG1): a caller's pre-computed
    # verdict (the drill's) is honoured only for a base arming, so a supplied base verdict can
    # never mark a Stratus session without the closed role and the sandbox actually proven.
    if for_stratus or verdict is None:
        verdict = check(for_stratus=for_stratus)
    if not verdict.armed:
        return verdict, None
    return verdict, Session(run_id, injector, verdict.cap["max_injections"], request=request,
                            for_stratus=for_stratus)


# ── Kill — revoke first, then stop ────────────────────────────────────────────────────

def kill(revoke: Callable[[], None], cancel: Callable[[], None], stop: Callable[[], None],
         close: Callable[[], None], *, disable_start: Callable[[], None] | None = None,
         remove_permit: Callable[[], None] | None = None,
         disarm: Callable[[], None] | None = None,
         revoke_stratus: Callable[[], None] | None = None) -> list[str]:
    """``orodruin-kill``: revoke the identity, cancel the chaos experiments still running,
    stop the VM, close the open exercise windows — in that order. Revoke first, so a
    running injector loses its rights even if the rest drags (a stopped VM keeps its
    identity); cancel next, since an experiment acts with its own identity and outlives
    the revocation; close last, once nothing of Orodruin's can reopen a window (M-1).
    A failed step does not stop the next ones, and is reported: never a kill that claims
    success while something survives. Returns the failures.

    The drill of the week (DRL1, docs/design/drill-banc.md §3.1), by the operator's identity:
    right after the revocation and before the VM is stopped, its scheduled start disabled
    (nothing may wake Orodruin while the kill runs), then its permit removed (an occurrence
    refuses without it, whenever it comes); last, its pulse written ``disarmed (killed)``.

    ``revoke_stratus`` (R2c, docs/design/stratus-cible.md §1), when a Stratus identity is given:
    right after Orodruin's own revocation, the operator cuts the Stratus identity's role on its
    dedicated subscription. Orodruin cannot (there it holds only AUTHZ_READ_ONLY); kill.py tools
    the operator's gesture. Absent when no Stratus identity is given."""
    failures = []

    def run(name: str, step: Callable[[], None] | None) -> None:
        if step is None:
            return
        try:
            step()
        except Exception as e:
            failures.append(f"{name}: {type(e).__name__}: {e}")

    for name, step in (("revoke", revoke), ("cancel", cancel), ("stop", stop), ("close", close)):
        if name == "cancel":   # DRL1: right after the revocation, before the VM is stopped
            run("disable_start", disable_start)
            run("remove_permit", remove_permit)
        run(name, step)
        if name == "revoke":   # R2c: the operator cuts the Stratus identity's role too, on its
            run("revoke_stratus", revoke_stratus)  # own dedicated subscription (Orodruin cannot)
    run("disarm", disarm)
    return failures


def main() -> int:
    """``orodruin-check`` on the host: the verdict and what is missing; exit 0 if armed. The
    verdict is published for the console (DG-b), best effort: said when it fails."""
    verdict = check()
    try:
        publish_contract(verdict)
    except Exception as e:
        print(f"  (verdict not published for the console: {type(e).__name__}: {e})"[:300])
    print(f"orodruin: {verdict.verdict}")
    for m in verdict.missing:
        print(f"  ✗ {m['code']}: {m['detail']}")
    for m in verdict.notes:
        print(f"  ⚠ {m['code']}: {m['detail']}")
    if verdict.armed:
        print(f"  cap: {verdict.cap}")
    return 0 if verdict.armed else 1


if __name__ == "__main__":
    raise SystemExit(main())
