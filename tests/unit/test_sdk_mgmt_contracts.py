"""SDK1b (#1017): the ten `azure.mgmt` operations Glorfindel's adapters read most, each read on the
pinned SDK's own objects — the body ARM sends, deserialized by the SDK's operation, then read by the
adapter's code. Never only on fake_azure's `SimpleNamespace`, whose enums are flat texts: on 06/10,
azure-mgmt-network 33's enums made every allow rule invisible to the precedence check (docs/azure.md).

The pinned versions (requirements/glorfindel.txt) are generated from TypeSpec: they have no
`Model.deserialize()` classmethod; each operation reads its reply with `_deserialize(Model, body)`, and
that is the path these tests take — the SDK's client, its pipeline, its pager, its errors, over
azure-core's transport, only the socket replaced (tests/unit/sdk_mgmt.py).

The ten, by how often the adapters read them (INVENTORY: every `azure.mgmt` call of the adapters):
- `network_security_groups.list_all` — each pass of the watch (60 s), whatever the state: the
  quarantine NSGs read by content and the orphan sweep (reassert.py, `nsg_listing`);
- `network_interfaces.list_all` — each pass too: the orphan sweep; and the rule poller's attribution
  of an address to its VM (`private_ip_owners`);
- `virtual_machines.get`, `network_interfaces.get`, `subnets.get`, `network_security_groups.get`,
  `security_rules.list` — each verification of an isolated VM or a block (each pass, for each), each
  action, and the posture's NSG check (each 30 min, each VM): a VM's NICs, the NSGs that govern
  them, whether one is shared, the allows evaluated before a deny (`_get_vm_nic_targets`,
  `_list_rules`, `_precedence_issues`);
- `backup_jobs.list` — each recovery pass (60 s), for each isolated VM (`observed_restore`), and the
  search of a snapshot's or a restore's job;
- `job_details.get` — the jobs' reconciliation while a restore runs, each recovery pass once a restore
  ended, a snapshot's verification;
- `recovery_points.list` — the posture's backup check (each 30 min, each VM), a restore, the point a
  restore restored.
Left out, read less often: `security_rules.get` (a block without state, a rule turned, a narrowing),
`virtual_machines.instance_view`, `disks.get`, the extensions and run commands (after a restore
only), `protected_items.get` and `backup_protected_items.list` (posture, the console), the public
IPs (posture), and every write.

**The bodies are HYPOTHESES** until the maintainer measures them (scripts/sdk_capture.py): the
shape of the REST reference's sample response, for the API version the pinned SDK sends
(learn.microsoft.com, each file's `reference`), the values made up for the bench at rest — one VM
behind its NIC's NSG (an allow of SSH at 100) and its subnet's, the quarantine NSG on standby, a
vault with a restore. SDK1b's second time puts the measured ones in their place (`source:
"measured"`). The ids the tests use are read from the bodies, so that the measured ones fit.

No Azure, no model, no network (`sdk_mgmt.offline`); every identifier is made up.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from . import sdk_mgmt as m

ROOT = Path(__file__).resolve().parents[2]

TEN = (
    "network.network_security_groups.list_all",
    "network.network_interfaces.list_all",
    "compute.virtual_machines.get",
    "network.network_interfaces.get",
    "network.subnets.get",
    "network.security_rules.list",
    "network.network_security_groups.get",
    "backup.backup_jobs.list",
    "backup.job_details.get",
    "backup.recovery_points.list",
)

# Every `azure.mgmt` operation the adapters call (glorfindel/providers/azure/): how often, what for.
# pass: each pass of the watch (60 s); reassert: each verification of an isolated VM or a block, each
# pass; posture: each posture pass (30 min), each VM; action: each action or its verification;
# recovery: each recovery pass of an isolated VM; rare: a command, the console, a card; write.
INVENTORY = {
    "network.network_security_groups.list_all": "pass — quarantine NSGs, orphan sweep; console, card target",
    "network.network_interfaces.list_all": "pass — orphan sweep; rule poller attribution; console",
    "compute.virtual_machines.get": "reassert, posture, action — NICs, OS type, disks",
    "network.network_interfaces.get": "reassert, posture, action — NSG, addresses, subnet, public IPs",
    "network.subnets.get": "reassert, posture, action — the subnet's NSG",
    "network.security_rules.list": "reassert, posture, action — precedence, quarantine content, blocks",
    "network.network_security_groups.get": "reassert, posture, action — sharing, quarantine read by id",
    "backup.backup_jobs.list": "recovery, action — the last restore of a VM, a trigger's job",
    "backup.job_details.get": "recovery, action — property bag, status, error details",
    "backup.recovery_points.list": "posture, recovery, action — the newest point, the vault tier",
    "network.security_rules.get": "action, rare — a block without state, a rule turned, a narrowing",
    "network.public_ip_addresses.get": "posture — the NSG audit's public addresses",
    # SEC2b (#1089): the client's network, never blocked — every 10 minutes, the discovery.
    "network.virtual_networks.list_all": "discovery — the VNets' address spaces and subnets (SEC2b)",
    "network.public_ip_addresses.list_all": "discovery — the client's public IPs, what holds each (SEC2b)",
    "network.public_ip_prefixes.list_all": "discovery — the client's public prefixes (SEC2b)",
    "network.load_balancers.list_all": "discovery — the load balancers' private frontends (SEC2b)",
    "compute.virtual_machines.instance_view": "recovery — power state, Run Command's word",
    "compute.disks.get": "recovery — the OS disk's creation time",
    "compute.disks.list": "rare — card target",
    "compute.snapshots.list": "rare — card target",
    "compute.snapshots.get": "rare — an older snapshot's verification",
    "compute.virtual_machine_extensions.list": "recovery, action — replayable scripts",
    "compute.virtual_machine_run_commands.list_by_virtual_machine": "recovery, action — replayable scripts",
    "backup.protected_items.get": "action, recovery, posture — the item's stored names",
    "backup.backup_protected_items.list": "posture, rare — the vault's inventory",
    "network.security_rules.begin_create_or_update": "write",
    "network.security_rules.begin_delete": "write",
    "network.network_security_groups.begin_create_or_update": "write",
    "network.network_security_groups.update_tags": "write",
    "network.network_interfaces.begin_create_or_update": "write",
    "compute.virtual_machines.begin_run_command": "write",
    "compute.virtual_machines.begin_deallocate": "write",
    "compute.virtual_machines.begin_start": "write",
}

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    m.offline(monkeypatch)


# ── the bodies' ids, read from the bodies (the measured ones keep fitting) ────────────────────────

def _vm() -> dict:
    return m.body(m.load("compute.virtual_machines.get"))


def _nic() -> dict:
    return m.body(m.load("network.network_interfaces.get"))


def _subnet() -> dict:
    return m.body(m.load("network.subnets.get"))


VM_ID = _vm()["id"]
NIC_ID = _nic()["id"]
NSG_ID = _nic()["properties"]["networkSecurityGroup"]["id"]
SUBNET_ID = _nic()["properties"]["ipConfigurations"][0]["properties"]["subnet"]["id"]
SUBNET_NSG_ID = _subnet()["properties"]["networkSecurityGroup"]["id"]
VAULT_RG, VAULT = re.search(r"resourceGroups/([^/]+)/providers/Microsoft\.RecoveryServices/vaults/([^/?]+)",
                            m.load("backup.backup_jobs.list")["responses"][0]["url"]).groups()


def _name(arm_id: str) -> str:
    return arm_id.rstrip("/").rsplit("/", 1)[-1]


def _rg(arm_id: str) -> str:
    return arm_id.split("/")[4]


def _restore_job() -> dict:
    return next(j for j in m.items(m.load("backup.backup_jobs.list"))
                if j["properties"]["operation"] == "Restore"
                and j["properties"]["entityFriendlyName"].lower() == _name(VM_ID).lower())


def _arm(*changed: dict) -> m.Arm:
    """Every body, those of `changed` in their operation's place."""
    ops = {c["operation"] for c in changed}
    return m.Arm(*[c for c in m.captures() if c["operation"] not in ops], *changed)


def _with(op: str, change) -> dict:
    """A capture of `op`, its first body changed in place by `change(body)`."""
    cap = m.load(op)
    change(m.body(cap))
    return cap


# ── the utility and the bodies themselves ───────────────────────────────────────────────────────

def test_the_sdks_read_here_are_the_ones_the_image_locks():
    """The SDKs these tests read are the versions Glorfindel's image installs: their models, their
    enums, the API versions they send are production's."""
    from importlib.metadata import version
    locked = (ROOT / "requirements/glorfindel.txt").read_text()
    for pkg in ("azure-mgmt-network", "azure-mgmt-compute", "azure-mgmt-recoveryservicesbackup", "azure-core"):
        pin = re.search(rf"^{pkg}==(\S+) \\$", locked, re.MULTILINE)
        assert pin and version(pkg) == pin.group(1), pkg


def test_each_of_the_ten_has_a_body_that_says_where_it_comes_from(monkeypatch):
    """Each of the ten has its file: `hypothesis` (with the REST reference it follows, for the
    version the SDK sends, or the gap said) or `measured` (with its day). Its API version is the one
    the pinned SDK sends for it — a new SDK sending another one asks for a body measured again."""
    arm = m.Arm(*m.captures())
    c = arm.connector(monkeypatch)
    calls = {
        "network.network_security_groups.list_all": lambda: c.nsg_listing(),
        "network.network_interfaces.list_all": lambda: list(c._network.network_interfaces.list_all()),
        "compute.virtual_machines.get": lambda: c.vm_os(VM_ID),
        "network.network_interfaces.get": lambda: c._nic_nsg_id(NIC_ID),
        "network.subnets.get": lambda: c._get_subnet_nsg(NIC_ID),
        "network.security_rules.list": lambda: c._list_rules({}, _rg(NSG_ID), _name(NSG_ID)),
        "network.network_security_groups.get": lambda: c._nsg_sharing(_rg(NSG_ID), _name(NSG_ID)),
        "backup.backup_jobs.list": lambda: list(c._backup.backup_jobs.list(VAULT, VAULT_RG)),
        "backup.job_details.get": lambda: c.restore_job_status(VAULT, VAULT_RG, _restore_job()["name"]),
        "backup.recovery_points.list": lambda: c.check_backup_points(VM_ID, VAULT, VAULT_RG),
    }
    for op in TEN:
        cap = m.load(op)
        assert cap["operation"] == op and cap["source"] in ("hypothesis", "measured"), op
        if cap["source"] == "hypothesis":
            assert cap["reference"].startswith("https://learn.microsoft.com/en-us/rest/api/"), op
            # The reference's view is the version the SDK sends — or the gap is said.
            view = re.search(r"view=rest-[a-z]+-(\d{4}-\d{2}-\d{2})", cap["reference"]).group(1)
            assert view == cap["api_version"] or (view in cap.get("reference_note", "")
                                                  and cap["api_version"] in cap["reference_note"]), op
        else:
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", cap["captured"]), op
        arm.requests.clear()
        calls[op]()
        sent = {re.search(r"api-version=([^&]+)", r["query"]).group(1) for r in arm.requests}
        assert sent == {cap["api_version"]}, op
    assert arm.writes == []


# The names the adapters give an SDK's client (`self._network`, `network`, `client`…): an operation
# group reached on one of them must be called there and then.
CLIENTS = frozenset({"_network", "_compute", "_backup", "network", "compute", "client", "backup_client", "bc"})


def _sdk_groups() -> dict[str, tuple[str, frozenset[str]]]:
    """Every operation group of the three SDKs' clients → its SDK and its operations."""
    arm = m.Arm()
    out = {}
    for sdk, client in (("network", arm.network()), ("compute", arm.compute()), ("backup", arm.backup())):
        for name, ops in vars(client).items():
            if type(ops).__name__.endswith("Operations"):
                out[name] = (sdk, frozenset(n for n in dir(type(ops)) if not n.startswith("_")))
    return out


def _model_fields() -> frozenset[str]:
    """Every field name of the three SDKs' models: `vm.network_profile.network_interfaces` is a
    model's field, not an operation group."""
    import azure.mgmt.compute.models as cm
    import azure.mgmt.network.models as nm
    import azure.mgmt.recoveryservicesbackup.models as bm
    fields = set()
    for module in (nm, cm, bm):
        for cls in vars(module).values():
            if isinstance(cls, type):
                fields |= {k for c in cls.__mro__ for k, v in vars(c).items() if type(v).__name__ == "_RestField"}
    return frozenset(fields)


def _client(node) -> bool:
    return ((isinstance(node, ast.Name) and node.id in CLIENTS)
            or (isinstance(node, ast.Attribute) and node.attr in CLIENTS))


def scan(source: str, groups: dict, fields: frozenset[str]) -> tuple[set[str], list[int]]:
    """The calls `<…>.<group>.<operation>(` of a source, by its syntax tree (a call written on two
    lines is one call), and the lines where an operation group is reached otherwise — kept in a
    name, passed to `getattr`, a client given to `getattr`: an inventory by text would not see what
    is called there."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found, odd = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "getattr" and node.args:
            named = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else None
            if _client(node.args[0]) or (named in groups and named not in fields):
                odd.append(node.lineno)
        if not (isinstance(node, ast.Attribute) and node.attr in groups):
            continue
        sdk, ops = groups[node.attr]
        parent = parents.get(node)
        if (isinstance(parent, ast.Attribute) and parent.attr in ops
                and isinstance(parents.get(parent), ast.Call) and parents[parent].func is parent):
            found.add(f"{sdk}.{node.attr}.{parent.attr}")
        elif _client(node.value) or node.attr not in fields:
            odd.append(node.lineno)
    return found, odd


def test_every_azure_mgmt_call_of_the_adapters_is_inventoried():
    """Every call of an SDK's operation group in the adapters, read by their syntax tree, is in
    INVENTORY, and INVENTORY names no call that is gone: a new read is placed among the others, or
    among the ten. A group reached any other way — an alias, `getattr` — fails: it would escape the
    inventory."""
    groups, fields = _sdk_groups(), _model_fields()
    found, odd = set(), []
    for path in sorted((ROOT / "glorfindel/providers/azure").glob("*.py")):
        calls, lines = scan(path.read_text(), groups, fields)
        found |= calls
        odd += [f"{path.name}:{n}" for n in lines]
    assert odd == []
    assert found == set(INVENTORY)
    assert set(TEN) <= set(INVENTORY)
    assert all(op.rsplit(".", 1)[1] in ("get", "list", "list_all") for op in TEN)


def test_the_scan_sees_a_call_on_two_lines_an_alias_and_a_getattr():
    """The scan itself: a call written on two lines is found; an alias of a group, a `getattr` of
    an operation, a `getattr` on a client are said; a model's field is none of them."""
    groups, fields = _sdk_groups(), _model_fields()
    two_lines = "def f(self):\n    return self._network.route_tables\\\n        .get('rg', 'rt')\n"
    assert scan(two_lines, groups, fields) == ({"network.route_tables.get"}, [])
    alias = "def f(self):\n    rt = self._network.route_tables\n    return rt.get('rg', 'rt')\n"
    assert scan(alias, groups, fields)[1] == [2]
    by_name = "def f(self):\n    return getattr(self._network.route_tables, 'get')('rg', 'rt')\n"
    assert scan(by_name, groups, fields)[1]
    by_group = "def f(c):\n    return getattr(c, 'route_tables').get('rg', 'rt')\n"
    assert "route_tables" not in fields and scan(by_group, groups, fields)[1]
    on_client = "def f(self):\n    return getattr(self._network, 'route_tables').get('rg', 'rt')\n"
    assert scan(on_client, groups, fields)[1]
    model = ("def f(vm, nsg):\n    return [n.id for n in vm.network_profile.network_interfaces]"
             " + list(getattr(nsg, 'security_rules', None) or [])\n")
    assert scan(model, groups, fields) == (set(), [])


def test_a_listing_on_two_pages_is_read_whole(monkeypatch):
    """A listing ARM gives on two pages (its `nextLink`, a skip token): the SDK's pager reads both,
    and the watch's pass sees every NSG."""
    cap = m.load("network.network_security_groups.list_all")
    first = cap["responses"][0]
    *head, last = first["body"]["value"]
    path = first["url"].split("?")[0]
    first["body"] = {"value": head, "nextLink": f"{m.ARM}{path}?api-version={cap['api_version']}&$skiptoken=page-2"}
    cap["responses"].append({"url": f"{path}?api-version={cap['api_version']}&$skiptoken=page-2", "status": 200,
                             "body": {"value": [last]}})
    arm = _arm(cap)
    listed = arm.connector(monkeypatch).nsg_listing()
    assert [n.name for n in listed] == [n["name"] for n in head] + [last["name"]]
    assert len(arm.sent("networkSecurityGroups")) == 2


def test_the_in_memory_arm_answers_reads_only(monkeypatch):
    """The utility: a write through the SDK is refused (405) and kept apart — a reader's test sees
    every write it would have sent."""
    from azure.core.exceptions import HttpResponseError
    arm = m.Arm(*m.captures())
    c = arm.connector(monkeypatch)
    with pytest.raises(HttpResponseError) as exc:
        c._network.security_rules.begin_delete(_rg(NSG_ID), _name(NSG_ID), "any").result()
    assert exc.value.status_code == 405 and [w["method"] for w in arm.writes] == ["DELETE"]


# ── 1. network_security_groups.list_all ─────────────────────────────────────────────────────────

def test_the_nsg_listing_through_the_sdk_keeps_its_enums_and_reads_the_quarantine_on_standby(monkeypatch):
    """The listing the watch's pass reads each minute, as the SDK gives it: an enum for a rule's
    access and direction (never « Allow »'s text — the 06/10 bug), the integer priority. Our
    quarantine NSG on standby reads `ok`, by its content (its four denies), holding no NIC."""
    from azure.mgmt.network.models import NetworkSecurityGroup, SecurityRuleAccess, SecurityRuleDirection
    arm = m.Arm(*m.captures())
    c = arm.connector(monkeypatch)
    nsgs = c.nsg_listing()
    assert all(type(n) is NetworkSecurityGroup for n in nsgs)
    rule = next(r for n in nsgs for r in n.security_rules or [])
    assert type(rule.access) is SecurityRuleAccess and type(rule.direction) is SecurityRuleDirection
    assert str(rule.access) != rule.access.value and type(rule.priority) is int
    [q] = c.find_altered_quarantines(nsgs)
    assert (q["status"], q["nics"], q["diff"]) == ("ok", [], [])
    assert _name(q["nsg_id"]).startswith("nsg-glorfindel-quarantine")
    assert arm.writes == []


def test_a_quarantine_deny_turned_into_an_allow_reads_altered_through_the_sdk(monkeypatch):
    """Our deny-all turned into an allow by hand, as the SDK reads it: `altered`, the rule named —
    the access read by its value."""
    def turn(body):
        q = next(n for n in body["value"] if n["name"].startswith("nsg-glorfindel-quarantine"))
        deny = next(r for r in q["properties"]["securityRules"] if r["name"] == "glorfindel-quarantine-deny-in")
        deny["properties"]["access"] = "Allow"
    c = _arm(_with("network.network_security_groups.list_all", turn)).connector(monkeypatch)
    [q] = c.find_altered_quarantines(c.nsg_listing())
    assert q["status"] == "altered" and q["diff"] == ["glorfindel-quarantine-deny-in"]


def test_an_nsg_with_our_name_and_no_tag_is_not_ours(monkeypatch):
    """An NSG named like our quarantine, in another group, without tags (the body leaves `tags`
    out: the SDK gives None): not ours, never read as one — and no error."""
    def homonym(body):
        q = next(n for n in body["value"] if n["name"].startswith("nsg-glorfindel-quarantine"))
        other = {k: v for k, v in q.items() if k != "tags"}
        other["id"] = q["id"].replace(f"/resourceGroups/{m.RG}/", "/resourceGroups/rg-example-09/")
        body["value"].append(other)
    c = _arm(_with("network.network_security_groups.list_all", homonym)).connector(monkeypatch)
    listed = c.find_altered_quarantines(c.nsg_listing())
    assert [_rg(q["nsg_id"]) for q in listed] == [m.RG]


@pytest.mark.parametrize("plurals", ["absent", "empty", "null"])
def test_a_rule_s_absent_or_null_lists_read_as_none(monkeypatch, plurals):
    """A rule's plural fields (`sourceAddressPrefixes`, `destinationPortRanges`…) left out, empty or
    null — the reference leaves them out, the API may send []: our quarantine reads `ok` all the
    same, never raises."""
    def fill(body):
        for n in body["value"]:
            for r in n["properties"].get("securityRules") or []:
                for f in ("sourceAddressPrefixes", "destinationAddressPrefixes", "sourcePortRanges",
                          "destinationPortRanges", "sourceApplicationSecurityGroups"):
                    if plurals == "empty":
                        r["properties"][f] = []
                    elif plurals == "null":
                        r["properties"][f] = None
    c = _arm(_with("network.network_security_groups.list_all", fill)).connector(monkeypatch)
    [q] = c.find_altered_quarantines(c.nsg_listing())
    assert q["status"] == "ok"


def test_a_quarantine_whose_rules_are_left_out_reads_altered(monkeypatch):
    """`securityRules` left out of our quarantine's body (the SDK: None): every deny missing,
    `altered` — never `ok`, never an error."""
    def strip(body):
        q = next(n for n in body["value"] if n["name"].startswith("nsg-glorfindel-quarantine"))
        del q["properties"]["securityRules"]
    c = _arm(_with("network.network_security_groups.list_all", strip)).connector(monkeypatch)
    [q] = c.find_altered_quarantines(c.nsg_listing())
    assert q["status"] == "altered" and "glorfindel-quarantine-deny-in" in q["diff"]


def test_the_console_s_inventory_through_the_sdk(monkeypatch):
    """`list_nsgs` (the console's NSG inventory): each NSG with its associations as the SDK gives
    them — the NIC's NSG its NIC and VM, the subnet's its subnet and the VMs behind it; the
    quarantine on standby not « restricted »."""
    c = m.Arm(*m.captures()).connector(monkeypatch)
    by_id = {n["id"].lower(): n for n in c.list_nsgs()}
    own, sub = by_id[NSG_ID.lower()], by_id[SUBNET_NSG_ID.lower()]
    assert own["nics"] == [NIC_ID] and own["vms"] == [VM_ID] and own["subnets"] == []
    assert sub["subnets"] == [SUBNET_ID] and VM_ID in sub["vms"]
    [q] = [n for n in by_id.values() if n["quarantine"]]
    assert (q["restricted"], q["glorfindel_rules"]) == (False, 4)


# ── 2. network_interfaces.list_all ──────────────────────────────────────────────────────────────

def _orphan_rule(body, nic_id: str, ip: str) -> None:
    """A deny of ours left by a NIC that no longer exists, on the subnet's NSG, aimed at `ip`."""
    import hashlib
    nsg = next(n for n in body["value"] if n["id"].lower() == SUBNET_NSG_ID.lower())
    mark = hashlib.sha256(nic_id.lower().encode()).hexdigest()[:32]
    name = f"glorfindel-iso-vm-example-09-nic-example-09-{mark}"
    nsg["properties"]["securityRules"].append({
        "name": name, "id": f"{nsg['id']}/securityRules/{name}",
        "properties": {"access": "Deny", "direction": "Inbound", "priority": 101, "protocol": "*",
                       "sourceAddressPrefix": "*", "destinationAddressPrefixes": [ip],
                       "sourcePortRange": "*", "destinationPortRange": "*", "provisioningState": "Succeeded"}})


def test_the_orphan_sweep_reads_the_nic_listing_through_the_sdk(monkeypatch):
    """The orphan sweep of the watch's pass on the SDK's NICs: a deny of a deleted NIC aimed at an
    address another VM holds now — that VM's NIC has no NSG of its own (`networkSecurityGroup` left
    out: None) and sits behind the subnet's — is removable, and names what it cuts off."""
    nics = m.items(m.load("network.network_interfaces.list_all"))
    bare = next(n for n in nics if "networkSecurityGroup" not in n["properties"])
    ip = bare["properties"]["ipConfigurations"][0]["properties"]["privateIPAddress"]
    gone = bare["id"].replace(_name(bare["id"]), "nic-example-09")
    cap = _with("network.network_security_groups.list_all", lambda b: _orphan_rule(b, gone, ip))
    arm = _arm(cap)
    c = arm.connector(monkeypatch)
    [orphan] = c.find_orphan_rules(c.nsg_listing())
    assert orphan["removable"] and orphan["ips"] == [ip]
    [cut] = orphan["cut"]
    assert (cut["ip"], cut["nic_id"], cut["vm_id"]) == (ip, bare["id"], bare["properties"]["virtualMachine"]["id"])
    assert cut["governed_by"] == [SUBNET_NSG_ID.lower()]
    assert arm.writes == []


def test_private_ip_owners_through_the_sdk(monkeypatch):
    """The rule poller's attribution: each address to its VM; a NIC attached to no VM
    (`virtualMachine` left out) is nobody's; one that forwards packets (`enableIPForwarding` true, a
    boolean as JSON reads it) makes its VM an appliance."""
    from glorfindel.detection_rules import appliance_owner

    def change(body):
        first, second = body["value"][:2]
        second["properties"]["enableIPForwarding"] = True
        loose = {**first, "id": first["id"] + "-loose", "properties": {
            k: v for k, v in first["properties"].items() if k != "virtualMachine"}}
        loose["properties"]["ipConfigurations"] = [{"name": "ipconfig1", "properties": {
            "privateIPAddress": "10.240.1.99", "subnet": {"id": SUBNET_ID}}}]
        body["value"].append(loose)
    cap = _with("network.network_interfaces.list_all", change)
    owners = _arm(cap).connector(monkeypatch).private_ip_owners()
    first, second = m.items(cap)[:2]
    ip = lambda n: n["properties"]["ipConfigurations"][0]["properties"]["privateIPAddress"]  # noqa: E731
    assert owners[ip(first)] == first["properties"]["virtualMachine"]["id"]
    assert owners[ip(second)] == appliance_owner(second["properties"]["virtualMachine"]["id"])
    assert "10.240.1.99" not in owners


# ── 3. virtual_machines.get ─────────────────────────────────────────────────────────────────────

def test_the_vm_through_the_sdk_names_its_nic_its_os_and_its_disks(monkeypatch):
    """The VM as the SDK gives it: its OS type an enum read as « linux » (the readiness), its managed
    disks (the snapshot's readiness), its NIC — a reference with no `properties`, so no `primary`:
    the first one."""
    from azure.mgmt.compute.models import OperatingSystemTypes
    c = m.Arm(*m.captures()).connector(monkeypatch)
    vm = c._compute.virtual_machines.get(_rg(VM_ID), _name(VM_ID))
    assert type(vm.storage_profile.os_disk.os_type) is OperatingSystemTypes
    assert c.vm_os(VM_ID) == _vm()["properties"]["storageProfile"]["osDisk"]["osType"].lower()
    disk = _vm()["properties"]["storageProfile"]["osDisk"]["managedDisk"]["id"]
    assert c.check_compute_access(VM_ID) == {"ok": True, "vm": _name(VM_ID), "disks": [_name(disk)]}
    assert c._get_primary_nic_id(_rg(VM_ID), _name(VM_ID)) == NIC_ID


def test_a_vm_whose_body_leaves_out_its_data_disks(monkeypatch):
    """`dataDisks` left out of the body: the SDK gives None, never [] — the snapshot's readiness
    reads no data disk; it said the VM unreadable (« 'NoneType' object is not iterable »)."""
    cap = _with("compute.virtual_machines.get", lambda b: b["properties"]["storageProfile"].pop("dataDisks"))
    out = _arm(cap).connector(monkeypatch).check_compute_access(VM_ID)
    assert out["ok"] is True and len(out["disks"]) == 1


# ── 4–7. network_interfaces.get, subnets.get, network_security_groups.get, security_rules.list ──

def test_the_nsg_audit_through_the_sdk(monkeypatch):
    """The NSG audit (the posture, each 30 min; the same reads as each verification of an isolated
    VM): the VM, its NIC, its subnet, the NIC's NSG and its rules, each from the SDK — the NIC's NSG
    governs it alone (`subnets` left out of its body), the subnet's is the other place a deny holds,
    and the allow of SSH at 100 is found before the deny an isolation or a block would place: the
    access and the direction read by their value. A public IP Azure does not have (404): said by
    its code, never an error of the audit."""
    arm = m.Arm(*m.captures())
    c = arm.connector(monkeypatch)
    out = c.check_nsg_access(VM_ID)
    assert out["ok"] is True and out["scope"] == "nic" and out["nsg"] == f"{_rg(NSG_ID)}/{_name(NSG_ID)}"
    [nic] = out["nsgs"]
    ips = [cfg["properties"]["privateIPAddress"] for cfg in _nic()["properties"]["ipConfigurations"]]
    assert nic["nic_id"] == NIC_ID and nic["ips"] == ips
    assert [p.get("code") for p in nic["public_ips"]] == ["not_found"]
    allow = next(r for r in m.items(m.load("network.security_rules.list")) if r["properties"]["access"] == "Allow")
    found = {(p["rule"], p["action"], p["direction"], p["ports"]) for p in out["precedence"]}
    assert found == {(allow["name"], "isolate_vm", "inbound", "22"), (allow["name"], "block_suspicious_ip", "inbound", "22")}
    [target] = c._get_vm_nic_targets(_rg(VM_ID), _name(VM_ID), allow_no_nsg=True)
    assert (target["shared_nsg"], target["ip_scoped"], target["subnet_unreadable"]) == (False, False, False)
    assert target["alt_nsg"] == {"nsg_rg": _rg(SUBNET_NSG_ID), "nsg_name": _name(SUBNET_NSG_ID)}
    assert target["location"] == _nic()["location"]
    assert arm.writes == []


def test_a_nic_without_its_own_nsg_is_governed_by_its_subnet_s(monkeypatch):
    """`networkSecurityGroup` left out of the NIC's body (the SDK: None): its subnet's NSG governs
    it, the deny scoped to its addresses."""
    cap = _with("network.network_interfaces.get", lambda b: b["properties"].pop("networkSecurityGroup"))
    [t] = _arm(cap).connector(monkeypatch)._get_vm_nic_targets(_rg(VM_ID), _name(VM_ID), allow_no_nsg=True)
    assert (t["scope"], t["nsg_name"], t["ip_scoped"], t["nic_has_nsg"]) == ("subnet", _name(SUBNET_NSG_ID), True, False)


def test_a_subnet_without_nsg_is_read_as_none_and_an_unread_one_as_unknown(monkeypatch):
    """`networkSecurityGroup` left out of the subnet's body: no other place for a deny — and the
    subnet READ, never unknown. A subnet the SDK cannot read (403): unknown, never « none »."""
    cap = _with("network.subnets.get", lambda b: b["properties"].pop("networkSecurityGroup"))
    [t] = _arm(cap).connector(monkeypatch)._get_vm_nic_targets(_rg(VM_ID), _name(VM_ID), allow_no_nsg=True)
    assert (t["scope"], t["alt_nsg"], t["subnet_unreadable"]) == ("nic", None, False)
    arm = m.Arm(*m.captures()).serve(SUBNET_ID, {"error": {"code": "AuthorizationFailed", "message": "no"}}, 403)
    [t] = arm.connector(monkeypatch)._get_vm_nic_targets(_rg(VM_ID), _name(VM_ID), allow_no_nsg=True)
    assert t["subnet_unreadable"] is True


def test_an_nsg_attached_to_two_nics_is_shared_through_the_sdk(monkeypatch):
    """The NIC's NSG attached to another NIC as well (its `networkInterfaces`): shared — an any/any
    deny there would cut the other VM off; the deny is scoped to the NIC's addresses."""
    other = NIC_ID.replace(_name(NIC_ID), "nic-example-08")
    cap = _with("network.network_security_groups.get",
                lambda b: b["properties"]["networkInterfaces"].append({"id": other}))
    [t] = _arm(cap).connector(monkeypatch)._get_vm_nic_targets(_rg(VM_ID), _name(VM_ID), allow_no_nsg=True)
    assert (t["shared_nsg"], t["ip_scoped"]) == (True, True)


def test_the_rules_of_an_nsg_gone_are_none_and_of_an_unread_one_unknown(monkeypatch):
    """`security_rules.list` of an NSG Azure no longer has (the SDK's ResourceNotFoundError): no
    rules — a block on it reads gone; of an NSG the SDK cannot read (403): unknown (None), never
    « nothing precedes our deny »."""
    rules = f"{NSG_ID}/securityRules"
    c = m.Arm(*m.captures()).serve(rules, {"error": {"code": "NotFound", "message": "gone"}}, 404) \
        .connector(monkeypatch)
    assert c._list_rules({}, _rg(NSG_ID), _name(NSG_ID)) == []
    c = m.Arm(*m.captures()).serve(rules, {"error": {"code": "AuthorizationFailed", "message": "no"}}, 403) \
        .connector(monkeypatch)
    assert c._list_rules({}, _rg(NSG_ID), _name(NSG_ID)) is None


def test_a_quarantine_read_by_its_id_through_the_sdk(monkeypatch):
    """`read_quarantine` (a card the listing no longer shows): our NSG read by `get`, by its content;
    gone (404): None."""
    q = next(n for n in m.items(m.load("network.network_security_groups.list_all"))
             if n["name"].startswith("nsg-glorfindel-quarantine"))
    c = m.Arm(*m.captures()).serve(q["id"], q).connector(monkeypatch)
    assert c.read_quarantine(q["id"])["status"] == "ok"
    assert m.Arm(*m.captures()).connector(monkeypatch).read_quarantine(q["id"]) is None


# ── 8. backup_jobs.list ─────────────────────────────────────────────────────────────────────────

def test_the_vault_s_jobs_through_the_sdk(monkeypatch):
    """The vault's jobs as the SDK gives them: `properties` the class its `jobType` names (an
    AzureIaaSVMJob, whose `containerName` the base class has not), its times aware datetimes. The
    last restore of the VM since its isolation; a backup's job found after its trigger, never
    another VM's."""
    from azure.mgmt.recoveryservicesbackup.models import AzureIaaSVMJob
    arm = m.Arm(*m.captures())
    c = arm.connector(monkeypatch)
    jobs = list(c._backup.backup_jobs.list(VAULT, VAULT_RG))
    assert all(type(j.properties) is AzureIaaSVMJob for j in jobs)
    assert all(j.properties.start_time.utcoffset() == timedelta(0) for j in jobs)
    restore = _restore_job()
    since = datetime.fromisoformat(restore["properties"]["startTime"].replace("Z", "+00:00")) - timedelta(hours=1)
    last = c._last_restore_job(c._backup, VAULT, VAULT_RG, _rg(VM_ID), _name(VM_ID), since)
    assert last["name"] == restore["name"] and last["status"] == restore["properties"]["status"]
    assert last["container_named"] is True and last["end"].endswith("+00:00")
    assert c._last_restore_job(c._backup, VAULT, VAULT_RG, _rg(VM_ID), _name(VM_ID),
                               since + timedelta(days=1)) is None
    backup = next(j for j in m.items(m.load("backup.backup_jobs.list"))
                  if j["properties"]["operation"] == "Backup" and j["properties"]["entityFriendlyName"] == _name(VM_ID))
    triggered = datetime.fromisoformat(backup["properties"]["startTime"].replace("Z", "+00:00"))
    found = c._find_backup_job(c._backup, VAULT, VAULT_RG, "Backup", _name(VM_ID), triggered,
                               attempts=1, delay_s=0, vm_rg=_rg(VM_ID))
    assert found.name == backup["name"]
    assert arm.writes == []


def test_a_job_of_a_kind_the_sdk_does_not_know_is_left_aside(monkeypatch):
    """A job whose `jobType` the SDK does not know: its base class, without `containerName` — the
    search reads it as unnamed, never raises."""
    def odd(body):
        j = next(j for j in body["value"] if j["properties"]["operation"] == "Restore")
        j["properties"]["jobType"] = "SomeNewJob"
    c = _arm(_with("backup.backup_jobs.list", odd)).connector(monkeypatch)
    since = datetime(2026, 11, 1, tzinfo=timezone.utc)
    last = c._last_restore_job(c._backup, VAULT, VAULT_RG, _rg(VM_ID), _name(VM_ID), since)
    assert last is not None and last["container_named"] is False


# ── 9. job_details.get ──────────────────────────────────────────────────────────────────────────

def test_a_job_s_details_through_the_sdk(monkeypatch):
    """The details of the restore's job, as the SDK gives them: its status a text (the SDK declares
    one), its property bag a dict whose keys carry a trailing space or not — folded; the point it
    restored found by the bag's time, to the second; a snapshot's verification reads `Completed`."""
    from glorfindel.providers.azure.recovery import _bag
    c = m.Arm(*m.captures()).connector(monkeypatch)
    name = _restore_job()["name"]
    details = c._backup.job_details.get(VAULT, VAULT_RG, name)
    bag = _bag(details)
    assert bag["job type"] == "Replace disks" and "recovery point time" in bag
    assert c.restore_job_status(VAULT, VAULT_RG, name) == "Completed"
    assert c.verify_snapshot(f"rsv:{VAULT}/{VAULT_RG}/{name}") == {"verified": True, "method": "rsv_backup", "job": name}
    point = c._restored_point(c._backup, bag, VAULT, VAULT_RG, _rg(VM_ID), _name(VM_ID))
    assert point["by"] == "time" and point["name"] == "62481920470211"


def test_a_job_whose_details_carry_no_extended_info(monkeypatch):
    """`extendedInfo` left out of the details (the SDK: None): an empty bag — the point said not
    named, never an error."""
    from glorfindel.providers.azure.recovery import _bag
    cap = _with("backup.job_details.get", lambda b: b["properties"].pop("extendedInfo"))
    c = _arm(cap).connector(monkeypatch)
    bag = _bag(c._backup.job_details.get(VAULT, VAULT_RG, _restore_job()["name"]))
    assert bag == {}
    assert c._restored_point(c._backup, bag, VAULT, VAULT_RG, _rg(VM_ID), _name(VM_ID)) == {
        "time": "", "why": "le job ne dit pas quel point il a restauré"}


# ── 10. recovery_points.list ────────────────────────────────────────────────────────────────────

def test_the_recovery_points_through_the_sdk(monkeypatch):
    """The VM's points as the SDK gives them (`nextLink` null: the last page): each the class its
    `objectType` names, its time an aware datetime, its tiers enums. The posture's age is the
    newest point's — the reference lists them in no order —; the points for a restore come newest
    first, each said in the vault tier or not by its tier's value."""
    from azure.mgmt.recoveryservicesbackup.models import IaasVMRecoveryPoint, RecoveryPointTierType
    import glorfindel.providers.azure.backup as backup_module
    arm = m.Arm(*m.captures())
    c = arm.connector(monkeypatch)
    container, item = backup_module._backup_item_names(_rg(VM_ID), _name(VM_ID))
    points = list(c._backup.recovery_points.list(VAULT, VAULT_RG, "Azure", container, item))
    assert all(type(p.properties) is IaasVMRecoveryPoint for p in points)
    assert all(type(t.type) is RecoveryPointTierType for p in points for t in p.properties.recovery_point_tier_details)
    newest = max(p.properties.recovery_point_time for p in points)
    out = c.check_backup_points(VM_ID, VAULT, VAULT_RG)
    assert out["ok"] is True and out["points"] == len(points)
    age = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    assert abs(out["latest_age_h"] - age) <= 0.2
    listed = c.list_recovery_points(VM_ID, VAULT, VAULT_RG)
    assert [p["time"] for p in listed] == sorted((p["time"] for p in listed), reverse=True)
    assert listed[0]["time"] == newest.isoformat() and all(p["vault_tier"] for p in listed)
    assert arm.writes == []


def test_a_point_whose_vault_tier_is_gone_is_not_in_the_vault_tier(monkeypatch):
    """A point whose `HardenedRP` tier reads `Deleted`: not in the vault tier — the enum compared
    by its value, both ways."""
    def drop(body):
        for p in body["value"]:
            for t in p["properties"]["recoveryPointTierDetails"]:
                if t["type"] == "HardenedRP":
                    t["status"] = "Deleted"
    c = _arm(_with("backup.recovery_points.list", drop)).connector(monkeypatch)
    assert [p["vault_tier"] for p in c.list_recovery_points(VM_ID, VAULT, VAULT_RG)] == [False, False]
