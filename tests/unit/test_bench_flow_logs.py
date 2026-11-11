"""INF-FL (#654): the bench's network flow logs in an account of their own, which no VM identity writes.

The blobs of the VNet flow logs are the proof of a connection that SEC-A3f will read
(docs/design/corroboration.md, §3.10): they hold only while no identity reachable from a watched VM
can write the account that carries them (CR15). Until INF-FL, that account was the exfiltration
exercises' one, where each enrolled VM's managed identity writes. Read from the files, no Azure, no
Terraform needed (the CI's terraform-test job plans the same contract against a fake azurerm:
infra/terraform/tests/flow_logs.tftest.hcl):
  - the flow log writes to the flows account, never to the exercises' nor to the restore's;
  - every role assignment of the module, WHATEVER ITS PRINCIPAL, is scoped to a resource of a
    closed list strictly below the group (the exercises' account, the DCR, a VM, the workspace), or
    is named in a closed list with its exact scope and its reason (the operator's read of the flows
    account, today alone). Anything else is refused: the flows account, a group, the subscription, a
    literal id, a `local` or a `var` (what it names is not read here). An inherited role is worth as
    much as a direct one, and a principal is not followed through a `local` (the review's probe of
    INF-FL: a VM's identity through `local.p`, Storage Blob Data Contributor on the group): the default
    is the refusal, not the reading of the principal;
  - every role assignment given to a VM's identity is, besides, never above its own resource;
  - on the flows account, one assignment only: the operator's read;
  - the flows account refuses the shared key by default (a variable, the measured way back) and
    public containers; the provider no longer reads any account's data plane with a key;
  - its name is never another account's, for the canonical instance or a named one;
  - `make celebrimbor-flows-plan` / `-up` touch the account, its read and the flow log, nothing else
    of the bench, never with a `-var` of their own — against a fake `terraform` first on the PATH.
Mutants M4760–M4764, M4770 (scripts/mutants/INF-FL.py).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TF = ROOT / "infra/terraform"

# What a VM's identity is, in the module: the system-assigned identity of a VM, or a user-assigned
# identity (chaos.tf attaches one to a VM of the benign noise) — both reachable by IMDS from the VM.
VM_PRINCIPAL = re.compile(r"azurerm_(linux_|windows_)?virtual_machine(_scale_set)?\.|azurerm_user_assigned_identity\.")
# A scope that is the flows account or above it: the account, a resource group (the bench's, a
# topology's — each could carry it, and the bench's does), the subscription, or a literal id.
ABOVE_OR_FLOWS = re.compile(r"azurerm_storage_account\.flows\b|azurerm_resource_group\.|azurerm_subscription\.|\"/")


# The scopes a role assignment of the module may take, each a resource strictly below the bench's
# group and never the flows account — with what is assigned there today. A new kind of scope is
# added here with its reason, in review; never a group, the subscription, a literal, a local, a var.
SCOPES_BELOW = {
    r"azurerm_storage_account\.exfil\.id": "the exercises' account: the enrolled VMs write their exfiltration (T1041)",
    r"azurerm_monitor_data_collection_rule\.celebrimbor\.id": "the DCR: each VM's agent publishes its metrics",
    r"azurerm_linux_virtual_machine\.\w+(\[each\.key\]|\[0\])?\.id": "a VM: the Chaos Studio experiments act on their own VM",
    r"azurerm_log_analytics_workspace\.celebrimbor\.id": "the workspace: the bench's read identity (BRO1)",
}
# The assignments named one by one, outside SCOPES_BELOW: (their exact scope, their reason). On the
# group or above it, none today — the module gives no role on the group; one added here says why.
CLOSED = {
    "flows_operator_reader": ("azurerm_storage_account.flows.id",
                              "the operator's read of the flows (Storage Blob Data Reader), for the bench's measurements"),
}


def _module_texts() -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(TF.glob("*.tf"))}


def _blocks(kind: str, name: str | None = None, texts: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    """Every `resource|data "<kind>" "<name>" { … }` of the module: (file, name, body), braces matched."""
    found = []
    for fname, text in (texts if texts is not None else _module_texts()).items():
        for m in re.finditer(rf'(?m)^(?:resource|data) "{kind}" "([\w-]+)" \{{', text):
            if name is not None and m.group(1) != name:
                continue
            depth, i = 1, m.end()
            while depth:
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                i += 1
            found.append((fname, m.group(1), text[m.end():i - 1]))
    return found


def _attr(body: str, key: str) -> str:
    m = re.search(rf"(?m)^  {key}\s*=\s*(.+)$", body)
    assert m, key
    return m.group(1).strip()


def _assignments(texts: dict[str, str] | None = None):
    return [(f, n, _attr(b, "scope"), _attr(b, "principal_id"), b)
            for f, n, b in _blocks("azurerm_role_assignment", texts=texts)]


def _refused(texts: dict[str, str]) -> list[str]:
    """The role assignments whose scope is neither of SCOPES_BELOW nor theirs in CLOSED, any principal."""
    refused = []
    for f, n, scope, _, _ in _assignments(texts):
        if n in CLOSED:
            if scope != CLOSED[n][0]:
                refused.append(f"{f}: {n} at {scope}, not its closed scope {CLOSED[n][0]}")
        elif not any(re.fullmatch(p, scope) for p in SCOPES_BELOW):
            refused.append(f"{f}: {n} at {scope}")
    # A role assignment declared by another resource type passes by no reading here: none at all.
    for f, text in texts.items():
        if re.search(r"Microsoft\.Authorization/roleAssignments", text, re.I):
            refused.append(f"{f}: a role assignment through azapi")
    return refused


# The review's probe of INF-FL: a VM's identity through a local, a data write on the group.
PROBE = """
locals {
  p = azurerm_linux_virtual_machine.baseline["gondolin"].identity[0].principal_id
}

resource "azurerm_role_assignment" "probe" {
  scope                = azurerm_resource_group.celebrimbor.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = local.p
}
"""


def test_every_assignment_is_below_the_group_or_closed_whatever_its_principal():
    assert _refused(_module_texts()) == []
    # Not vacuous: each scope kind is used, and each closed assignment exists.
    scopes = {a[2] for a in _assignments()}
    for pattern in SCOPES_BELOW:
        assert any(re.fullmatch(pattern, s) for s in scopes), pattern
    assert set(CLOSED) <= {a[1] for a in _assignments()}


@pytest.mark.parametrize("probe", [
    PROBE,
    PROBE.replace("azurerm_resource_group.celebrimbor.id", "local.s").replace(
        "locals {\n", "locals {\n  s = azurerm_resource_group.celebrimbor.id\n"),
    PROBE.replace("azurerm_resource_group.celebrimbor.id", "data.azurerm_subscription.bench.id"),
    PROBE.replace("azurerm_resource_group.celebrimbor.id", '"/subscriptions/00000000-0000-0000-0000-000000000000"'),
    PROBE.replace("azurerm_resource_group.celebrimbor.id", "azurerm_storage_account.flows.id"),
    PROBE.replace("azurerm_resource_group.celebrimbor.id", "var.any_scope"),
], ids=["group-principal-through-a-local", "scope-through-a-local", "subscription", "literal", "flows", "var"])
def test_the_probe_is_refused(probe):
    texts = {**_module_texts(), "probe.tf": probe}
    assert [r for r in _refused(texts) if "probe" in r], probe
    # The closed list is not a way around: a closed name at another scope is refused too.
    moved = texts["storage.tf"].replace("  scope                = azurerm_storage_account.flows.id\n",
                                        "  scope                = azurerm_resource_group.celebrimbor.id\n")
    assert _refused({**texts, "storage.tf": moved, "probe.tf": ""})


def test_the_flow_log_writes_to_the_flows_account():
    [(f, _, body)] = _blocks("azurerm_network_watcher_flow_log")
    assert f == "monitoring.tf"
    assert _attr(body, "storage_account_id") == "azurerm_storage_account.flows.id"


def test_the_flows_account_is_none_of_the_others():
    names = {n for _, n, _ in _blocks("azurerm_storage_account")}
    assert {"flows", "exfil", "restore_staging"} <= names
    [(f, _, body)] = _blocks("azurerm_storage_account", "flows")
    assert f == "storage.tf"
    assert _attr(body, "name") == "local.flows_storage_name"
    locals_tf = (TF / "locals.tf").read_text()
    names_of = {}
    for local in ("flows_storage_name", "exfil_storage_name", "staging_storage_name"):
        m = re.search(rf'(?m)^  {local}\s*=\s*local\.instance == "default" \? "(\w+)" : "(\w+)\$\{{', locals_tf)
        assert m, local
        names_of[local] = m.groups()
    # Neither the canonical name nor a named instance's prefix (its hash appended) is another's.
    for i in (0, 1):
        assert len({v[i] for v in names_of.values()}) == 3, names_of
    assert names_of["flows_storage_name"][0] == "stcelebrimborflows"
    assert 3 <= len(names_of["flows_storage_name"][0]) <= 24 and len(names_of["flows_storage_name"][1]) + 8 <= 24


def test_no_vm_identity_is_granted_the_flows_account_nor_above_it():
    to_vms = [(f, n, scope) for f, n, scope, principal, _ in _assignments() if VM_PRINCIPAL.search(principal)]
    # The known ones, so that the reading is not vacuous: the exercises' write, the agent's metrics.
    assert {n for _, n, _ in to_vms} >= {"vm_storage_exfil", "ama_dcr", "multinic_ama_dcr", "sharednsg_ama_dcr"}
    for f, n, scope in to_vms:
        assert not ABOVE_OR_FLOWS.search(scope), f"{f}: {n} gives a VM's identity a role at {scope}"
    [(_, _, scope, _, body)] = [a for a in _assignments() if a[1] == "vm_storage_exfil"]
    assert scope == "azurerm_storage_account.exfil.id"
    assert _attr(body, "role_definition_name") == '"Storage Blob Data Contributor"'


def test_the_flows_account_is_read_by_the_operator_alone():
    on_flows = [a for a in _assignments() if "azurerm_storage_account.flows" in a[2]]
    assert [a[1] for a in on_flows] == ["flows_operator_reader"]
    [(_, _, scope, principal, body)] = on_flows
    assert scope == "azurerm_storage_account.flows.id"
    assert principal == "data.azurerm_client_config.operator.object_id"
    assert _attr(body, "role_definition_name") == '"Storage Blob Data Reader"'


def test_no_key_nor_sas_of_the_flows_account_leaves_the_module():
    for path in TF.glob("*.tf"):
        text = path.read_text()
        assert not re.search(r"azurerm_storage_account\.flows\.(primary|secondary)_", text), path.name
        assert "azurerm_storage_account_sas" not in text and "azurerm_storage_account_blob_container_sas" not in text
    # Nothing the VMs run names it: the exercises write to the exercises' account.
    for path in [*(TF / "scripts").iterdir(), *(ROOT / "scripts/vm").iterdir()]:
        if path.is_file():
            assert "stcelebrimborflows" not in path.read_text(errors="replace"), path


def test_the_shared_key_is_refused_by_default():
    [(_, _, body)] = _blocks("azurerm_storage_account", "flows")
    assert _attr(body, "shared_access_key_enabled") == "var.flow_logs_shared_key_enabled"
    assert _attr(body, "allow_nested_items_to_be_public") == "false"
    assert _attr(body, "account_tier") == '"Standard"'
    variables = (TF / "variables.tf").read_text()
    m = re.search(r'(?ms)^variable "flow_logs_shared_key_enabled" \{\n(.*?)^\}', variables)
    assert m
    assert re.search(r"(?m)^  default\s*= false$", m.group(1)) and re.search(r"(?m)^  nullable\s*= false$", m.group(1))
    # Never opened from the tracked files: the example sets nothing, the config has no such key.
    assert "flow_logs_shared_key_enabled" not in (TF / "config.yaml").read_text()
    assert not re.search(r"(?m)^\s*flow_logs_shared_key_enabled\s*=\s*true", (TF / "terraform.tfvars.example").read_text())


def test_the_provider_reads_no_account_s_data_plane_with_a_key():
    main = (TF / "main.tf").read_text()
    m = re.search(r'(?ms)^provider "azurerm" \{\n(.*?)^\}', main)
    assert m
    assert re.search(r"(?m)^    storage \{\n      data_plane_available = false\n    \}$", m.group(1))
    # The flag forbids these two blocks: no account of the module may carry them.
    for _, n, body in _blocks("azurerm_storage_account"):
        assert "queue_properties" not in body and "static_website" not in body, n


def test_traffic_analytics_and_retention_as_before():
    [(_, _, body)] = _blocks("azurerm_network_watcher_flow_log")
    assert re.search(r"(?m)^  retention_policy \{\n    enabled = true\n    days    = 7\n  \}$", body)
    assert re.search(r"(?m)^    interval_in_minutes   = 10$", body)
    assert _attr(body, "target_resource_id") == "azurerm_virtual_network.celebrimbor.id"


def test_the_terraform_test_plans_the_property():
    text = (TF / "tests/flow_logs.tftest.hcl").read_text()
    for run in ("the_flow_log_writes_to_the_flows_account_never_the_exercises_one",
                "the_flows_account_refuses_the_shared_key_and_public_containers",
                "no_vm_identity_is_granted_the_flows_account_nor_above_it",
                "the_test_topologies_vms_are_not_granted_it_either",
                "the_rollback_reopens_the_key_and_nothing_else"):
        assert f'run "{run}"' in text, run
    assert re.search(r"(?m)^  flow_logs_shared_key_enabled\s*= false$", text)


# ── the Make targets, against a fake terraform ───────────────────────────────

pytestmark_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
TARGETS = ["-target=azurerm_storage_account.flows", "-target=azurerm_role_assignment.flows_operator_reader",
           "-target=azurerm_network_watcher_flow_log.celebrimbor"]


def _make(tmp_path, target, *args):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = tmp_path / "tf.log"
    log.write_text("")
    tf = bin_dir / "terraform"
    tf.write_text('#!/bin/sh\necho "$*" >> "$FAKE_TF_LOG"\n')
    tf.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_TF_LOG": str(log),
           "HOME": str(tmp_path)}
    for var in ("INSTANCE", "YES", "TOPO"):
        env.pop(var, None)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, *args],
                         env=env, capture_output=True, text=True, timeout=60)
    return res.returncode, res.stdout + res.stderr, [c.split() for c in log.read_text().splitlines()]


@pytestmark_make
@pytest.mark.parametrize("args,instance", [((), "default"), (("INSTANCE=ci-1234",), "ci-1234")])
def test_flows_plan_plans_the_account_its_read_and_the_flow_log_alone(tmp_path, args, instance):
    code, out, calls = _make(tmp_path, "celebrimbor-flows-plan", *args)
    assert code == 0, out
    chdir = "-chdir=infra/terraform"
    assert calls == [[chdir, "init"], [chdir, "workspace", "select", instance], [chdir, "plan", *TARGETS]]


@pytest.mark.parametrize("args,approve", [((), []), (("YES=1",), ["-auto-approve"])])
@pytestmark_make
def test_flows_up_applies_them_alone_confirmed_unless_yes(tmp_path, args, approve):
    code, out, calls = _make(tmp_path, "celebrimbor-flows-up", *args)
    assert code == 0, out
    assert calls[-1] == ["-chdir=infra/terraform", "apply", *approve, *TARGETS]
    assert not any(a.startswith("-var") for c in calls for a in c)


def test_the_targets_name_resources_that_exist():
    for t in TARGETS:
        kind, name = t.removeprefix("-target=").split(".")
        assert _blocks(kind, name), t
