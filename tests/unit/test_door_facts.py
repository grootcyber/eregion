"""LEV2 (#690): the door's facts — who acted on a VM by the control plane, and whether they keep their
rights — read on the fake Azure (tests/unit/fake_azure.py), never on Azure. Facts only: the lift is
unchanged (its tests are test_recovery_watch.py, test_glorfindel.py, the machine of the invariants).

The property of the lot: a read cut or failed gives the actors, or the rights, UNREADABLE — never
« nobody », never « absent ». Held here at every read the adapter makes, one by one.

The shapes of the fake (hypotheses H7, H9, H11; docs/design/levee-probation.md §14) follow
Microsoft's documentation and what REC1b measured (09/11): to be measured on the bench before LEV3
(docs/banc-lev2.md).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from glorfindel import door_facts
from glorfindel.actions import _load_isolation_state, _save_isolation_state
from glorfindel.providers.azure.connector import AzureConnector
from glorfindel.providers.azure.door import DOOR_TABLE, CutRead, rule_covers
from glorfindel.providers.azure.door_rights import RightsReading, door_held

from .fake_azure import SUB, FakeAzure, nsg_id

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
THIRD = "11111111-1111-1111-1111-111111111111"      # a third party: a service principal
ADMIN = "22222222-2222-2222-2222-222222222222"      # an administrator, a user
GROUP = "33333333-3333-3333-3333-333333333333"      # a group of administrators
H0 = "44444444-4444-4444-4444-444444444444"
SINCE = (NOW - timedelta(days=7)).isoformat()


def _world():
    """web (10.0.1.4) and api (10.0.1.5) behind one subnet NSG of another group, rg-net: a shared
    NSG. web has its own NIC NSG, a data disk, a public IP, an ASG and an identity."""
    f = FakeAzure()
    f.clock = lambda: NOW
    f.caller = H0
    shared = f.add_nsg("rg-net", "nsg-subnet")
    own = f.add_nsg("rg-app", "nsg-web")
    sub = f.add_subnet("rg-net", "vnet", "app", shared)
    asg = f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Network/applicationSecurityGroups/asg-web"
    pip = f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Network/publicIPAddresses/pip-web"
    ident = f"{SUB}/resourceGroups/rg-app/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-web"
    vm = f.add_vm("rg-app", "web", [{"rg": "rg-app", "name": "web-nic", "ips": ["10.0.1.4"], "subnet": sub,
                                     "nsg": own, "public_ips": [pip], "asgs": [asg]}],
                  data_disks=1, identities=[ident])
    f.add_vm("rg-app", "api", [{"rg": "rg-app", "name": "api-nic", "ips": ["10.0.1.5"], "subnet": sub,
                                "nsg": None}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute, c._rest = f.network, f.compute, f.rest
    c._subscription_id = "s"
    return f, c, vm, {"shared": shared, "own": own, "asg": asg, "pip": pip, "identity": ident}


def _at(minutes: float) -> datetime:
    return NOW + timedelta(minutes=minutes)


def _ops(seen: dict) -> set[tuple[str, str]]:
    return {(a["ids"][0] if a["ids"] else "", g["operation"].lower()) for a in seen["actors"] for g in a["gestures"]}


# ── the actors ─────────────────────────────────────────────────────────────────────────────────

def test_nobody_on_a_vm_read_whole_is_none_not_unreadable():
    f, c, vm, _ = _world()
    seen = c.observed_actors(vm, SINCE)
    assert seen["verdict"] == "none" and seen["actors"] == [] and seen["unreadable"] == []
    # Every resource of the VM read exactly, and each group read once (the NSG's lives elsewhere).
    kinds = sorted(r["what"] for r in seen["reads"])
    assert kinds == ["disk", "disk", "group", "group", "identity", "nic", "nsg", "nsg", "public_ip", "vm"]


def test_a_third_partys_extension_is_a_gesture_whatever_its_type_and_read_from_the_group():
    """§4.1: any extension written by a third party counts — VMAccess as a monitoring agent. Its event
    names the child (`<vm>/extensions/<name>`): the exact read of the VM does not give it (H9), the
    read of the group does, filtered by the prefix of the VM's id, case folded."""
    f, c, vm, _ = _world()
    f.log(vm.upper() + "/extensions/VMAccessForLinux", "Microsoft.Compute/virtualMachines/extensions/write",
          caller=THIRD, at=_at(-60))
    f.log(vm + "/extensions/AzureMonitorLinuxAgent", "Microsoft.Compute/virtualMachines/extensions/write",
          caller=THIRD, at=_at(-50))
    seen = c.observed_actors(vm, SINCE)
    assert seen["verdict"] == "seen"
    [actor] = seen["actors"]
    assert THIRD in actor["ids"] and actor["role"] == ""
    assert [g["kind"] for g in actor["gestures"]] == ["vm_child"] * 4      # Started and Succeeded, twice
    assert {g["status"] for g in actor["gestures"]} == {"Started", "Succeeded"}


def test_another_vms_extension_of_a_similar_name_is_not_this_vms():
    f, c, vm, _ = _world()
    f.log(vm + "-old/extensions/x", "Microsoft.Compute/virtualMachines/extensions/write", caller=THIRD, at=_at(-5))
    assert c.observed_actors(vm, SINCE)["verdict"] == "none"


def test_a_failed_gesture_counts_a_refusal_of_the_platform_does_not():
    """Whatever its status (REC1b): a Run Command that failed in the guest was tried by a principal
    whose rights are then read; one the platform refused (Conflict, OperationNotAllowed, the VM
    deallocated) reached nothing."""
    f, c, vm, _ = _world()
    agent_failure = {"http": None, "message": '{"status":"Failed","error":{"code":"VMAgentStatusCommunicationError"}}'}
    refusal = {"http": "Conflict", "message": '{"error":{"code":"OperationNotAllowed","message":"deallocated"}}'}
    f.log(vm, "Microsoft.Compute/virtualMachines/runCommand/action", ("Started", "Failed"), caller=THIRD,
          at=_at(-30), failed=agent_failure)
    f.log(vm, "Microsoft.Compute/virtualMachines/runCommand/action", ("Started", "Failed"), caller=ADMIN,
          at=_at(-20), failed=refusal)
    seen = c.observed_actors(vm, SINCE)
    assert [a["ids"] for a in seen["actors"]] == [[THIRD]]
    assert {g["status"] for g in seen["actors"][0]["gestures"]} == {"Started", "Failed"}


def test_a_rule_of_a_shared_nsg_counts_only_when_it_covers_the_vm():
    """§4.1: on a shared NSG, a rule aimed at another VM is not a gesture on this one. Its target read
    from the event's request body, else from the NSG now, else it counts."""
    f, c, vm, n = _world()
    rule = n["shared"] + "/securityRules/{}"
    op = "Microsoft.Network/networkSecurityGroups/securityRules/write"

    def body(dst, direction="Inbound", **more):
        return {"properties": {"direction": direction, "destinationAddressPrefix": dst, "sourceAddressPrefix": "*",
                               **more}}
    f.log(rule.format("to-api"), op, caller=THIRD, at=_at(-40), body=body("10.0.1.5"))          # another VM
    f.log(rule.format("to-api-cidr"), op, caller=THIRD, at=_at(-39), body=body("10.0.1.5/32"))
    assert c.observed_actors(vm, SINCE)["verdict"] == "none"
    f.log(rule.format("to-subnet"), op, caller=ADMIN, at=_at(-30), body=body("10.0.1.0/24"))   # holds web
    f.log(rule.format("to-vnet"), op, caller=ADMIN, at=_at(-29), body=body("VirtualNetwork"))
    f.log(rule.format("to-asg"), op, caller=ADMIN, at=_at(-28), body={"properties": {
        "direction": "Inbound", "destinationApplicationSecurityGroups": [{"id": n["asg"]}]}})
    f.log(rule.format("unread"), op, caller=ADMIN, at=_at(-27))                                  # no body
    f.log(rule.format("out-from-web"), op, caller=ADMIN, at=_at(-26), body={"properties": {
        "direction": "Outbound", "sourceAddressPrefix": "10.0.1.4", "destinationAddressPrefix": "10.9.9.9"}})
    seen = c.observed_actors(vm, SINCE)
    resources = {g["resource"].rsplit("/", 1)[-1] for a in seen["actors"] for g in a["gestures"]}
    assert resources == {"to-subnet", "to-vnet", "to-asg", "unread", "out-from-web"}
    assert all(g["covers"] for a in seen["actors"] for g in a["gestures"])


def test_a_rule_of_the_vms_own_nsg_counts_whatever_it_aims_at():
    f, c, vm, n = _world()
    f.log(n["own"] + "/securityRules/x", "Microsoft.Network/networkSecurityGroups/securityRules/write",
          caller=THIRD, at=_at(-5), body={"properties": {"direction": "Inbound", "destinationAddressPrefix": "10.7.7.7"}})
    assert c.observed_actors(vm, SINCE)["verdict"] == "seen"


@pytest.mark.parametrize("target,op", [
    ("vm", "Microsoft.Compute/virtualMachines/write"),
    ("disk", "Microsoft.Compute/disks/beginGetAccess/action"),
    ("noted", "Microsoft.Compute/disks/write"),
    ("nic", "Microsoft.Network/networkInterfaces/write"),
    ("pip", "Microsoft.Network/publicIPAddresses/join/action"),
    ("nic", "Microsoft.Network/publicIPAddresses/join/action"),
    ("own", "Microsoft.Network/networkSecurityGroups/write"),
    ("identity", "Microsoft.ManagedIdentity/userAssignedIdentities/assign/action"),
    ("serial", "Microsoft.SerialConsole/serialPorts/connect/action"),
    ("managed", "Microsoft.Compute/virtualMachines/runCommands/write"),
    ("group", "Microsoft.Resources/subscriptions/resourceGroups/write"),
    ("tags", "Microsoft.Resources/tags/write"),
])
def test_each_gesture_of_the_table_is_read_on_its_resource(target, op):
    f, c, vm, n = _world()
    noted = f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Compute/disks/web-osdisk-before-restore"
    where = {"vm": vm, "disk": f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Compute/disks/web-data0",
             "noted": noted, "nic": f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Network/networkInterfaces/web-nic",
             "pip": n["pip"], "own": n["own"], "identity": n["identity"],
             "serial": vm + "/providers/Microsoft.SerialConsole/serialPorts/0",
             "managed": vm + "/runCommands/persist", "group": f"{SUB}/resourceGroups/rg-app",
             "tags": vm + "/providers/Microsoft.Resources/tags/default"}[target]
    f.log(where, op, caller=THIRD, at=_at(-10))
    seen = c.observed_actors(vm, SINCE, disks=[noted])
    assert seen["verdict"] == "seen", seen
    assert _ops(seen) == {(THIRD, op.lower())}


def test_outside_the_table_or_the_window_is_no_gesture():
    f, c, vm, _ = _world()
    f.log(vm, "Microsoft.Compute/virtualMachines/start/action", caller=THIRD, at=_at(-5))      # a start puts nothing
    f.log(vm, "Microsoft.Compute/virtualMachines/deallocate/action", caller=THIRD, at=_at(-5))
    f.log(vm, "Microsoft.Compute/virtualMachines/write", caller=THIRD, at=NOW - timedelta(days=8))
    # The op of the table, on a kind it does not name: a disk write logged on the VM.
    f.log(vm, "Microsoft.Compute/disks/write", caller=THIRD, at=_at(-5))
    assert c.observed_actors(vm, SINCE)["verdict"] == "none"


def test_a_gesture_late_in_the_log_is_read_once_it_lands():
    """The log is late (H12, unmeasured for this REST read): read too early, it says none; read again,
    the gesture is there. The watch reads again at every interval."""
    f, c, vm, _ = _world()
    f.log(vm, "Microsoft.Compute/virtualMachines/write", caller=THIRD, at=_at(-1), delay_s=300)
    assert c.observed_actors(vm, SINCE)["verdict"] == "none"
    f.clock = lambda: NOW + timedelta(minutes=5)
    assert c.observed_actors(vm, SINCE)["verdict"] == "seen"


def test_events_read_twice_count_once_if_the_exact_filter_gives_the_children():
    """H9 the other way: `resourceUri eq` also gives the children — read by both, counted once."""
    f, c, vm, _ = _world()
    f.uri_children = True
    f.log(vm + "/extensions/x", "Microsoft.Compute/virtualMachines/extensions/write", ("Succeeded",),
          caller=THIRD, at=_at(-5))
    seen = c.observed_actors(vm, SINCE)
    assert len(seen["actors"][0]["gestures"]) == 1


def test_one_principal_under_two_ids_is_one_actor_and_roles_are_said_for_information(monkeypatch):
    monkeypatch.setenv("GLORFINDEL_OWN_CALLERS", H0)
    monkeypatch.setenv("GLORFINDEL_RESTORE_PRINCIPALS", ADMIN)
    f, c, vm, _ = _world()
    f.log(vm, "Microsoft.Compute/virtualMachines/write", ("Succeeded",), caller="ops@example.org",
          claims={"oid": THIRD, "upn": "ops@example.org"}, at=_at(-9))
    f.log(vm, "Microsoft.Compute/virtualMachines/write", ("Succeeded",), caller=THIRD, at=_at(-8))
    f.log(vm, "Microsoft.Compute/virtualMachines/runCommand/action", ("Succeeded",), caller=H0, at=_at(-7))
    f.log(vm, "Microsoft.Compute/virtualMachines/runCommand/action", ("Succeeded",), caller=ADMIN, at=_at(-6))
    seen = c.observed_actors(vm, SINCE)
    assert [(a["role"], len(a["gestures"])) for a in seen["actors"]] == [("", 2), ("glorfindel", 1), ("restore", 1)]
    assert "ops@example.org" in seen["actors"][0]["ids"]


def _reads(c, vm):
    base = c.observed_actors(vm, SINCE)
    return [(r["how"], r["what"]) for r in base["reads"]]


@pytest.mark.parametrize("cut", [CutRead("plus de 20 pages, la suite n'est pas lue"),
                                 RuntimeError("HTTP 403 AuthorizationFailed"), RuntimeError("HTTP 429")])
def test_every_read_cut_or_failed_makes_the_actors_unreadable_never_none(cut):
    """THE property of LEV2, at each read the adapter makes, one at a time: the VM, its NIC, each disk,
    each NSG, the public IP, the identity, each group. A third party seen elsewhere stays listed."""
    f, c, vm, _ = _world()
    f.log(vm + "/extensions/x", "Microsoft.Compute/virtualMachines/extensions/write", caller=THIRD, at=_at(-5))
    reads = c.observed_actors(vm, SINCE)["reads"]
    assert len(reads) == 10
    real = c._activity_read
    for i in range(len(reads)):
        calls = []

        def one_fails(how, value, since, until, i=i):
            calls.append(value)
            if len(calls) - 1 == i:
                raise cut
            return real(how, value, since, until)
        c._activity_read = one_fails
        seen = c.observed_actors(vm, SINCE)
        assert seen["verdict"] == "unreadable", (i, reads[i])
        assert seen["unreadable"] and any("error" in r for r in seen["reads"])
        del c._activity_read


def test_a_busy_group_past_twenty_pages_is_unreadable_and_twenty_pages_are_read():
    """The bound of REC1b on the real pager: 20 pages, a 21st is never « all read »."""
    f, c, vm, _ = _world()
    f.page_size = 1
    other = f"{SUB}/resourceGroups/rg-app/providers/Microsoft.Compute/virtualMachines/api"
    for i in range(21):
        f.log(other, "Microsoft.Compute/virtualMachines/write", ("Succeeded",), caller=THIRD, at=_at(-30 + i))
    seen = c.observed_actors(vm, SINCE)
    assert seen["verdict"] == "unreadable"
    group = [r for r in seen["reads"] if r["what"] == "group" and "error" in r]
    assert group and "20 pages" in group[0]["error"]
    f.activity = f.activity[:20]                                   # 20 events: 20 pages, read whole
    assert c.observed_actors(vm, SINCE)["verdict"] == "none"


def test_a_next_page_outside_arm_is_refused_and_unreadable():
    f, c, vm, _ = _world()
    real = f.rest
    c._rest = lambda url, params: {**real(url, params), "nextLink": "https://elsewhere.example/next"}
    assert c.observed_actors(vm, SINCE)["verdict"] == "unreadable"


def test_a_vm_or_a_nic_that_cant_be_read_is_unreadable():
    f, c, vm, _ = _world()
    f.vms.clear()
    seen = c.observed_actors(vm, SINCE)
    assert seen["verdict"] == "unreadable" and seen["reads"] == []


def test_the_table_is_closed_and_names_the_design():
    ops = {op for op, _, _ in DOOR_TABLE}
    assert "Microsoft.Compute/virtualMachines/extensions/write" in ops
    assert "Microsoft.Compute/virtualMachines/start/action" not in ops
    assert len(ops) == len(DOOR_TABLE) == 19


def test_a_rule_that_names_nothing_counts_and_a_tag_not_evaluated_counts():
    assert rule_covers(None, ["10.0.1.4"], set())
    assert rule_covers({"direction": "Inbound"}, ["10.0.1.4"], set())
    assert rule_covers({"direction": "Inbound", "destination_address_prefix": "AzureCloud"}, ["10.0.1.4"], set())
    assert not rule_covers({"direction": "Inbound", "destination_address_prefix": "10.0.2.0/24"}, ["10.0.1.4"], set())
    # Inbound: the source is not what covers; outbound: the destination is not.
    assert not rule_covers({"direction": "Inbound", "source_address_prefix": "10.0.1.4",
                            "destination_address_prefix": "10.0.9.9"}, ["10.0.1.4"], set())


# ── the rights ─────────────────────────────────────────────────────────────────────────────────

def _rights(c, vm, ids, **kw):
    seen = c.observed_actors(vm, SINCE)
    return c.observed_rights(ids, vm, scopes=seen["scopes"], **kw)


@pytest.mark.parametrize("role,where,verdict", [
    ("Contributor", "group", "held"),
    ("Owner", "subscription", "held"),
    ("User Access Administrator", "subscription", "held"),        # it gives itself the door back
    ("Virtual Machine Contributor", "vm", "held"),
    ("Virtual Machine Administrator Login", "vm", "held"),         # dataActions: a login to the VM
    ("Network Contributor", "nsg-other-group", "held"),
    ("Reader", "subscription", "absent"),
    ("Compute Reader, writes taken back", "group", "absent"),       # notActions take them back
])
def test_a_direct_assignment_is_read_as_azure_reads_it(role, where, verdict):
    f, c, vm, n = _world()
    scope = {"group": f"{SUB}/resourceGroups/rg-app", "subscription": SUB, "vm": vm,
             "nsg-other-group": n["shared"]}[where]
    f.assign(scope, THIRD, role)
    r = _rights(c, vm, [THIRD])
    assert r["verdict"] == verdict, r
    if verdict == "held":
        assert r["held"][0]["role"] == role


def test_nobody_holds_the_door_is_absent_and_another_principals_rights_are_not_the_actors():
    f, c, vm, _ = _world()
    f.assign(SUB, ADMIN, "Owner", principal_type="User")
    assert _rights(c, vm, [THIRD])["verdict"] == "absent"


@pytest.mark.parametrize("case", ["group", "eligible", "eligible-group", "management-group", "deleted", "orphan"])
def test_what_h0_cant_read_whole_is_unreadable_never_absent(case):
    """§4.4: a right through a group (members not read), a PIM eligibility (to the actor or a
    group), an assignment at a management group, a deleted principal (restorable from Entra's
    recycle bin) — all unreadable, the quarantine kept (Q11)."""
    f, c, vm, _ = _world()
    kw = {}
    if case == "group":
        f.assign(SUB, GROUP, "Contributor", principal_type="Group")
    elif case == "eligible":
        f.assign(f"{SUB}/resourceGroups/rg-app", THIRD, "Contributor", eligible=True)
    elif case == "eligible-group":
        f.assign(SUB, GROUP, "Owner", principal_type="Group", eligible=True)
    elif case == "management-group":
        f.assignments.append({"id": "/providers/Microsoft.Management/managementGroups/mg/providers/"
                                    "Microsoft.Authorization/roleAssignments/a-mg",
                              "properties": {"scope": "/providers/Microsoft.Management/managementGroups/mg",
                                             "principalId": THIRD, "principalType": "ServicePrincipal",
                                             "roleDefinitionId": f.role_id("Contributor")}})
        real = f.rest
        c._rest = lambda url, params: _with_mg(real(url, params), f.assignments[-1], url)
    elif case == "deleted":
        f.assign(vm, THIRD, "Reader")
        kw = {"deleted": True}
    elif case == "orphan":
        f.assign(vm, THIRD, "Virtual Machine Contributor", principal_type="Unknown")
    r = _rights(c, vm, [THIRD], **kw)
    assert r["verdict"] == "unreadable", r
    assert r["held"] == []


def _with_mg(body, mg, url):
    """A listing at a scope that also gives an assignment at a management group above it."""
    if url.lower().endswith("/roleassignments"):
        body = {**body, "value": list(body.get("value") or []) + [mg]}
    return body


def test_a_group_or_an_eligibility_that_would_not_give_the_door_leaves_it_absent():
    f, c, vm, _ = _world()
    f.assign(SUB, GROUP, "Reader", principal_type="Group")
    f.assign(SUB, THIRD, "Reader", eligible=True)
    assert _rights(c, vm, [THIRD])["verdict"] == "absent"


def test_a_deleted_principal_with_nothing_left_is_absent():
    f, c, vm, _ = _world()
    assert _rights(c, vm, [THIRD], deleted=True)["verdict"] == "absent"


def test_an_actor_known_by_no_object_id_is_unreadable():
    f, c, vm, _ = _world()
    assert _rights(c, vm, ["ops@example.org"])["verdict"] == "unreadable"


def test_every_scope_read_refused_or_cut_makes_the_rights_unreadable():
    """At each scope (the VM, its NIC, each disk, each NSG — one in another group, without Reader —,
    the identity), assignments and eligibilities: one refused, the verdict unreadable."""
    f, c, vm, n = _world()
    scopes = c.observed_actors(vm, SINCE)["scopes"]
    assert len(scopes) == 7
    for scope in scopes:
        for what in ("/roleAssignments", "/roleEligibilityScheduleInstances"):
            f.rest_denied = {scope.rstrip("/") + "/providers/Microsoft.Authorization" + what}
            r = c.observed_rights([THIRD], vm, scopes=scopes)
            assert r["verdict"] == "unreadable", (scope, what)
    f.rest_denied = set()
    f.page_size = 1
    for i in range(21):
        f.assign(SUB, f"{i:08d}-0000-0000-0000-000000000000", "Reader")
    r = c.observed_rights([THIRD], vm, scopes=scopes)
    assert r["verdict"] == "unreadable" and any("20 pages" in w for w in r["unreadable"])


def test_a_definition_that_cant_be_read_is_unreadable():
    f, c, vm, _ = _world()
    f.assign(SUB, THIRD, "Contributor")
    f.roles.clear()
    assert _rights(c, vm, [THIRD])["verdict"] == "unreadable"


def test_held_wins_over_what_else_cant_be_read():
    f, c, vm, _ = _world()
    f.assign(SUB, THIRD, "Owner")
    f.assign(SUB, GROUP, "Contributor", principal_type="Group")
    r = _rights(c, vm, [THIRD])
    assert r["verdict"] == "held" and r["unreadable"]


def test_one_reading_serves_every_actor_of_a_pass():
    f, c, vm, _ = _world()
    f.assign(SUB, THIRD, "Owner")
    scopes = c.observed_actors(vm, SINCE)["scopes"]
    reading, before = RightsReading(), len(f.rest_calls)
    assert c.observed_rights([THIRD], vm, scopes=scopes, reading=reading)["verdict"] == "held"
    first = len(f.rest_calls) - before
    assert c.observed_rights([ADMIN], vm, scopes=scopes, reading=reading)["verdict"] == "absent"
    assert len(f.rest_calls) - before == first            # nothing read twice


def test_the_door_counts_every_operation_of_the_table_and_the_rights_that_give_one_back():
    assert door_held([{"actions": ["Microsoft.Authorization/roleAssignments/write"]}]) == [
        "Microsoft.Authorization/roleAssignments/write"]
    assert door_held([{"actions": ["Microsoft.Authorization/roleDefinitions/write"]}])
    assert door_held([{"actions": ["*/read"]}]) == []
    # A `*` of actions never gives a data action; a data action taken back is not held.
    assert "Microsoft.Compute/virtualMachines/login/action" not in door_held([{"actions": ["Microsoft.Network/*"]}])
    assert door_held([{"dataActions": ["Microsoft.Compute/*"], "notDataActions": ["Microsoft.Compute/*"]}]) == []


def test_the_rights_are_read_with_get_only_and_nothing_is_written():
    f, c, vm, _ = _world()
    f.assign(SUB, THIRD, "Owner")
    before = len(f.journal)
    _rights(c, vm, [THIRD])
    assert len(f.journal) == before                        # no write through the API
    assert all("/providers/Microsoft.Authorization/" in u or "eventtypes" in u or "/fake-next/" in u
               for u, _ in f.rest_calls)


# ── the disks at the isolation ─────────────────────────────────────────────────────────────────

def test_the_disks_are_noted_at_the_isolation_and_kept_by_an_isolation_again():
    f, c, vm, _ = _world()
    c.isolate_vm(vm)
    disks = _load_isolation_state(vm)["disks_at_isolation"]
    assert disks["os"].endswith("/disks/web-osdisk") and [d.rsplit("/", 1)[-1] for d in disks["data"]] == ["web-data0"]
    assert len(disks["ids"]) == 2
    # A restore in place puts new disks; isolated again before its release, the first ones stay noted.
    f.vms[vm.lower()]["os_disk"] = f._new_disk("rg-app", "web-osdisk-restored", NOW)
    c.isolate_vm(vm)
    assert _load_isolation_state(vm)["disks_at_isolation"] == disks


def test_an_isolation_state_written_before_lev2_is_read_again_and_released():
    f, c, vm, _ = _world()
    c.isolate_vm(vm)
    state = _load_isolation_state(vm)
    state.pop("disks_at_isolation")
    _save_isolation_state(vm, state)
    assert _load_isolation_state(vm) == state
    assert c.release_isolation(vm)["status"] == "released"


def test_noting_the_disks_reads_nothing_more_than_the_isolation_did():
    f, c, vm, _ = _world()
    calls = []
    f.chaos = lambda op, phase, write: calls.append(op) if phase == "before" else None
    c.isolate_vm(vm)
    # The targets' read and the session drain's (its OS type), as before LEV2: none for the disks —
    # the machine of the invariants counts its faults by call.
    assert calls.count("vm.get") == 2 and "disk.get" not in calls


# ── the watch's pass, and its file ─────────────────────────────────────────────────────────────

def test_the_pass_writes_the_facts_for_information_and_reads_again_only_after_its_interval(monkeypatch):
    f, c, vm, _ = _world()
    c.isolate_vm(vm)
    f.log(vm, "Microsoft.Compute/virtualMachines/write", caller=THIRD, at=_at(-30))
    f.assign(SUB, THIRD, "Contributor")
    now = NOW.timestamp()
    [r] = door_facts.facts_pass(c, now=now)
    # Two actors: the third party, and H0 itself — its session drain at the isolation (a Run
    # Command), said too: who is excused is LEV3's (§4.2).
    assert r["verdict"] == "seen" and r["actors"] == 2
    facts = door_facts.load(vm)
    third = next(a for a in facts["actors"] if THIRD in a["ids"])
    assert facts["for_information"] is True and third["rights"]["verdict"] == "held"
    view = next(a for a in door_facts.card_view(vm)["actors"] if THIRD in a["ids"])
    assert view["rights"] == "held" and view["held"] == ["Contributor (l'abonnement)"]
    calls = len(f.rest_calls)
    assert door_facts.facts_pass(c, now=now + 60) == []
    assert len(f.rest_calls) == calls
    assert len(door_facts.facts_pass(c, now=now + door_facts.interval_s() + 1)) == 1


def test_the_pass_writes_unreadable_when_the_log_cant_be_read_and_drops_a_released_vm():
    f, c, vm, _ = _world()
    c.isolate_vm(vm)
    f.rest_denied = {"eventtypes"}
    [r] = door_facts.facts_pass(c, now=NOW.timestamp())
    assert r["verdict"] == "unreadable"
    assert door_facts.card_view(vm)["unreadable"]
    c.release_isolation(vm)
    door_facts.facts_pass(c, now=NOW.timestamp() + 1)
    assert door_facts.load(vm) is None and not list(door_facts.FACTS_DIR.glob("*.json"))


def test_the_pass_window_starts_seven_days_before_the_isolation():
    f, c, vm, _ = _world()
    c.isolate_vm(vm)
    door_facts.facts_pass(c, now=NOW.timestamp())
    iso = datetime.fromisoformat(_load_isolation_state(vm)["isolated_at"])
    since = datetime.fromisoformat(door_facts.load(vm)["since"].replace("Z", "+00:00"))
    assert abs((iso - since) - timedelta(days=7)) < timedelta(seconds=2)


def test_a_provider_that_cant_say_writes_nothing(tmp_path):
    class Other:
        def observed_actors(self, *a, **k):
            raise NotImplementedError

    _save_isolation_state("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/x", {
        "resource_id": "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/x",
        "isolated_at": NOW.isoformat(), "placements": []})
    assert door_facts.facts_pass(Other(), now=NOW.timestamp()) == []
    assert not door_facts.FACTS_DIR.exists() or not list(door_facts.FACTS_DIR.glob("*.json"))


def test_the_facts_file_of_another_vm_is_not_read_for_this_one():
    f, c, vm, _ = _world()
    c.isolate_vm(vm)
    door_facts.facts_pass(c, now=NOW.timestamp())
    path = door_facts._file(vm)
    data = json.loads(path.read_text())
    data["resource_id"] = vm + "-other"
    path.write_text(json.dumps(data))
    assert door_facts.load(vm) is None and door_facts.card_view(vm) is None


def test_dry_run_reads_nothing():
    c = AzureConnector(dry_run=True)
    assert c.observed_actors("/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/x",
                             SINCE)["verdict"] == "unreadable"
    assert c.observed_rights([THIRD], "/subscriptions/s/x")["verdict"] == "unreadable"


def test_the_shared_nsg_is_another_groups_and_read_there():
    f, c, vm, n = _world()
    assert n["shared"] == nsg_id("rg-net", "nsg-subnet")
    groups = [r for r in c.observed_actors(vm, SINCE)["reads"] if r["how"] == "group"]
    assert len(groups) == 2


def test_the_door_command_reads_only_and_says_the_rights_reads(monkeypatch):
    """`glorfindel door <vm>` on H0, by Jonathan: H1 and H2 read under H0's identity with one GET each
    (docs/banc-lev2.md). Nothing written, on the fake or here."""
    from click.testing import CliRunner
    import glorfindel.actions as actions
    from glorfindel.cli import cli
    f, c, vm, _ = _world()
    f.clock = lambda: datetime.now(timezone.utc)
    f.log(vm, "Microsoft.Compute/virtualMachines/write", caller=THIRD,
          at=datetime.now(timezone.utc) - timedelta(hours=1))
    f.assign(SUB, THIRD, "Owner")
    monkeypatch.setattr(actions, "AzureConnector", lambda dry_run=False: c)
    out = CliRunner().invoke(cli, ["door", vm, "--json"])
    assert out.exit_code == 0, out.output
    seen = json.loads(out.output)
    assert seen["verdict"] == "seen" and seen["actors"][0]["rights"]["verdict"] == "held"
    assert {r["what"] for r in seen["rights_reads"]} == {"assignments", "eligibilities"}
    assert any(r["inherited"] for r in seen["rights_reads"])           # H1: the subscription's, read at the VM
    out = CliRunner().invoke(cli, ["door", vm])
    assert out.exit_code == 0 and "lecture seule" in out.output
    assert f.journal == [] and not door_facts.FACTS_DIR.exists()
