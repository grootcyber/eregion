"""The drill's scheduled start, in Terraform (DRL1c, #613; docs/design/drill-banc.md §5.1, §11):
infra/orodruin/drill_autostart.tf and the ARM template it deploys, infra/orodruin/drill_autostart.json.

The contract DRL1a fixed, and infra/orodruin/drill_ops.py reads: the output ``drill_autostart_id``, the id
of a ``Microsoft.Logic/workflows``; its one trigger a weekly Recurrence in UTC at the drill's schedule less
20 min; created Disabled, and no apply ever enabling it; its identity's role one action
(``virtualMachines/start/action``), assignable in Orodruin's group, assigned to Orodruin's VM alone; and
Orodruin shut down every day at 23:00 UTC. The module is read as text (as test_orodruin.py does), the
template as JSON, and the trigger is handed to drill_ops's own reader. The same contract, planned against
a fake azurerm: infra/orodruin/tests/drill_autostart.tftest.hcl (`terraform test`, the CI's
terraform-test job). Nothing reaches Azure. Mutants M5881–M5900 (scripts/mutants/DRL1c.py).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from eregion_core import drill as dr

ROOT = Path(__file__).resolve().parents[2]
ORO = ROOT / "infra" / "orodruin"
SUB = "00000000-0000-0000-0000-000000000000"


def _text(name: str) -> str:
    return (ORO / name).read_text(encoding="utf-8")


def _block(text: str, kind: str, name: str) -> str:
    head = f'resource "{kind}" "{name}" {{'
    assert text.count(head) == 1, head
    return text.split(head)[1].split("\n}\n")[0]


def _attr(block: str, key: str) -> str:
    m = re.search(rf"^  {key}\s+=\s+(.+)$", block, re.M)
    assert m, key
    return m.group(1).strip()


@pytest.fixture(scope="module")
def ops():
    sys.path.insert(0, str(ORO))
    spec = importlib.util.spec_from_file_location("drill_ops", ORO / "drill_ops.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _template() -> dict:
    return json.loads(_text("drill_autostart.json"))


def _workflow_resource() -> dict:
    resources = _template()["resources"]
    assert len(resources) == 1
    assert resources[0]["type"] == "Microsoft.Logic/workflows"
    return resources[0]


def _autostart_default() -> str:
    var = _text("variables.tf").split('variable "drill_autostart_at" {')[1].split("\n}\n")[0]
    m = re.search(r'^  default\s+=\s+"([^"]*)"$', var, re.M)
    assert m
    return m.group(1)


def _parameters(at: str) -> dict:
    """What Terraform hands the template for ``drill_autostart_at = at``: the day mapped by the
    module's own table, the hour and the minute by their index in « HH:MM » — read in the module."""
    tf = _text("drill_autostart.tf")
    days = dict(re.findall(r"\b(mon|tue|wed|thu|fri|sat|sun) = \"(\w+)\"", tf))
    params = tf.split("parameters_content = jsonencode({")[1].split("})")[0]
    day, hm = at.split(" ")
    parts = hm.split(":")
    out = {}
    for key, expr in re.findall(r"^\s+(\w+)\s+= \{ value = (.+) \}$", params, re.M):
        if expr == "local.autostart_days[local.autostart_at[0]]":
            out[key] = days[day]
        elif m := re.fullmatch(r"tonumber\(local\.autostart_hm\[(\d)\]\)", expr):
            out[key] = int(parts[int(m.group(1))])
    assert re.search(r'^\s+autostart_at\s+= split\(" ", var\.drill_autostart_at\)$', tf, re.M)
    assert re.search(r'^\s+autostart_hm\s+= split\(":", local\.autostart_at\[1\]\)$', tf, re.M)
    assert sorted(out) == ["hour", "minute", "weekDay"]
    return out


def _filled(node, params: dict):
    """The template's ``[parameters('x')]`` replaced by their value, as ARM does when deploying."""
    if isinstance(node, dict):
        return {k: _filled(v, params) for k, v in node.items()}
    if isinstance(node, list):
        return [_filled(v, params) for v in node]
    if isinstance(node, str) and (m := re.fullmatch(r"\[parameters\('(\w+)'\)\]", node)):
        return params[m.group(1)]
    return node


# ── The Logic App: created Disabled, and no apply enabling it ────────────────────────────────

def test_the_logic_app_is_created_disabled_by_the_template_itself():
    """§5.1, §11: created Disabled — the state written in the one PUT that creates it, never left to
    ARM's default for a PUT without one."""
    wf = _workflow_resource()
    assert wf["properties"]["state"] == "Disabled"
    assert wf["identity"] == {"type": "SystemAssigned"}
    assert wf["apiVersion"] == "2019-05-01"


def _code(text: str) -> str:
    """A .tf file's code, its comment lines dropped: what an apply runs."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _module_tf(where: Path = ORO) -> dict[str, str]:
    """Every .tf file of the module, by name, its code only — never one file picked (DRL1e)."""
    return {p.name: _code(p.read_text(encoding="utf-8")) for p in sorted(where.glob("*.tf"))}


def _provisioners(code: str) -> list[str]:
    """Each ``provisioner "…" { … }`` block of a file's code, its braces matched."""
    blocks = []
    for m in re.finditer(r'provisioner\s+"[^"]*"\s*\{', code):
        depth, i = 1, m.end()
        while depth and i < len(code):
            depth += {"{": 1, "}": -1}.get(code[i], 0)
            i += 1
        blocks.append(code[m.start():i])
    return blocks


def _activations(module: dict[str, str]) -> list[str]:
    """What, in any file of the module, could enable the scheduled start at an apply: a call to
    …/enable (or the word enable), a provisioner naming the Logic App, an azurerm Logic App resource,
    and outside drill_autostart.tf, the Logic App named anywhere but in a description."""
    found = []
    for name, code in module.items():
        if "/enable" in code or re.search(r"\benable\b", code, re.I):
            found.append(f"{name}: enable")
        if "azurerm_logic_app" in code:
            found.append(f"{name}: an azurerm Logic App resource")
        for block in _provisioners(code):
            if re.search(r"logic|workflow|autostart|enable", block, re.I):
                found.append(f"{name}: a provisioner on the Logic App")
        if name != "drill_autostart.tf":
            for line in code.splitlines():
                if re.search(r"logic", line, re.I) and not re.match(r'\s*description\s*=\s*"', line):
                    found.append(f"{name}: the Logic App named ({line.strip()[:60]})")
    return found


def test_no_apply_enables_the_scheduled_start():
    """Terraform never holds the Logic App's state: no azurerm_logic_app_workflow (whose `enabled` an
    apply would put back), no trigger or action component (azurerm rewrites the whole workflow without
    its state), no provisioner, no call to …/enable — in any .tf file of the module, main.tf included
    (DRL1e); the template deployed incrementally — Complete would delete every other resource of
    Orodruin's group."""
    module = _module_tf()
    assert {"main.tf", "drill_autostart.tf", "outputs.tf", "variables.tf", "stratus_guardrails.tf"} <= set(module)
    assert _activations(module) == []
    tf = _text("drill_autostart.tf")
    code = module["drill_autostart.tf"]
    assert re.findall(r'resource "(\w+)" "(\w+)"', code) == [
        ("azurerm_resource_group_template_deployment", "drill_autostart"),
        ("azurerm_role_definition", "drill_autostart"),
        ("azurerm_role_assignment", "drill_autostart"),
        ("azurerm_dev_test_global_vm_shutdown_schedule", "host"),
    ]
    for word in ("azurerm_logic_app", "provisioner", "local-exec", "/enable", "enabled = var", "state"):
        assert word not in code, word
    deploy = _block(tf, "azurerm_resource_group_template_deployment", "drill_autostart")
    assert _attr(deploy, "deployment_mode") == '"Incremental"'
    assert _attr(deploy, "template_content") == 'file("${path.module}/drill_autostart.json")'
    assert _attr(deploy, "resource_group_name") == "azurerm_resource_group.host.name"
    others = "".join(code for name, code in module.items() if name != "drill_autostart.tf")
    assert "azurerm_logic_app" not in others and "Microsoft.Logic" not in others


_ENABLE_FROM = {
    "a local-exec posting …/enable": (
        'resource "terraform_data" "autostart_on" {\n  provisioner "local-exec" {\n    command = "az rest '
        '--method post --url https://management.azure.com${local.autostart_outputs.workflowId.value}/enable'
        '?api-version=2019-05-01"\n  }\n}\n'),
    "a local-exec by az logic": (
        'resource "terraform_data" "autostart_on" {\n  provisioner "local-exec" {\n    command = "az logic '
        'workflow update --ids ${local.autostart_outputs.workflowId.value} --state Enabled"\n  }\n}\n'),
    "an external data source by az logic, no provisioner": (
        'data "external" "wake" {\n  program = ["az", "logic", "workflow", "update", "--state", "Enabled", '
        '"--ids", local.autostart_outputs.workflowId.value]\n}\n'),
    "a remote-exec by its output": (
        'resource "null_resource" "wake" {\n  provisioner "remote-exec" {\n    inline = ["az rest --method post '
        '--url ${local.autostart_outputs.workflowId.value}/start"]\n  }\n}\n'),
}


@pytest.mark.parametrize("where", ["main.tf", "stratus_guardrails.tf", "outputs.tf"])
@pytest.mark.parametrize("form", sorted(_ENABLE_FROM))
def test_an_apply_enabling_the_scheduled_start_from_any_file_of_the_module_fails_the_test(tmp_path, where, form):
    """The search reads every .tf of the module: the module copied, an activation added to main.tf (or
    another file than drill_autostart.tf), and the search finds it (DRL1e, M6485)."""
    for p in ORO.glob("*.tf"):
        (tmp_path / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    assert _activations(_module_tf(tmp_path)) == []
    target = tmp_path / where
    target.write_text(target.read_text(encoding="utf-8") + "\n" + _ENABLE_FROM[form], encoding="utf-8")
    found = _activations(_module_tf(tmp_path))
    assert found and all(f.startswith(f"{where}:") for f in found), found


def test_its_one_action_starts_orodruins_vm_by_its_own_identity():
    definition = _workflow_resource()["properties"]["definition"]
    assert list(definition["actions"]) == ["start_orodruin"]
    action = definition["actions"]["start_orodruin"]
    assert action["type"] == "Http" and action["runAfter"] == {}
    # The start is not followed: following it would read the operation, a right more.
    assert action["operationOptions"] == "DisableAsyncPattern"
    inputs = action["inputs"]
    assert inputs["method"] == "POST"
    assert inputs["uri"] == ("[concat('https://management.azure.com', parameters('vmId'), "
                             "'/start?api-version=2024-07-01')]")
    assert inputs["authentication"] == {"type": "ManagedServiceIdentity", "audience": "https://management.azure.com/"}
    params = _text("drill_autostart.tf").split("parameters_content = jsonencode({")[1].split("})")[0]
    assert re.search(r"^\s+vmId\s+= \{ value = azurerm_linux_virtual_machine\.host\.id \}$", params, re.M)


# ── Its hour: the drill's schedule less 20 min ───────────────────────────────────────────────

def test_the_default_hour_is_the_shipped_drill_s_schedule_less_20_min(ops):
    """`orodruin-drill-arm` refuses unless the trigger is the schedule less 20 min (« apply first »):
    the default the module ships is exactly that, for the drill the repository ships."""
    schedule = dr.load_file(dr.shipped_dir() / "banc-hebdo.yaml", dr.SHIPPED).schedule
    day, at = ops.expected_at(schedule)
    assert _autostart_default() == f"{day} {at}" == "tue 18:40"


@pytest.mark.parametrize("at,want", [("tue 18:40", ("tue", "18:40")), ("sun 00:05", ("sun", "00:05")),
                                     ("mon 23:59", ("mon", "23:59")), ("sat 07:00", ("sat", "07:00"))])
def test_the_trigger_drill_ops_reads_is_drill_autostart_at(ops, at, want):
    """The template, its parameters filled as Terraform hands them, read by drill_ops's own reader
    (the one the arming trusts): one weekly Recurrence in UTC, one day, one hour, one minute."""
    definition = _filled(_workflow_resource()["properties"]["definition"], _parameters(at))
    assert list(definition["triggers"]) == ["weekly"]
    assert ops.autostart_at({"properties": {"definition": definition}}) == want


def test_the_variable_takes_only_a_day_and_an_hour():
    var = _text("variables.tf").split('variable "drill_autostart_at" {')[1].split("\n}\n")[0]
    m = re.search(r'regex\("(.+)", var\.drill_autostart_at\)', var)
    assert m
    pattern = m.group(1).replace("\\\\", "\\")
    for good in ("tue 18:40", "sun 00:05", "mon 23:59"):
        assert re.fullmatch(pattern, good), good
    for bad in ("tue 24:00", "Tuesday 18:40", "18:40", "tue 18:4", "tue 18:60", "tue  18:40", ""):
        assert not re.fullmatch(pattern, bad), bad
    assert "nullable    = false" in var


# ── Its identity: one action, Orodruin's group, Orodruin's VM ───────────────────────────────

def test_its_role_is_one_action_assignable_in_orodruins_group_alone():
    role = _block(_text("drill_autostart.tf"), "azurerm_role_definition", "drill_autostart")
    actions = role.split("actions = [")[1].split("]")[0]
    assert re.findall(r'"([^"]+)"', actions) == ["Microsoft.Compute/virtualMachines/start/action"]
    assert "not_actions = []" in role and "data_actions" not in role
    assert _attr(role, "scope") == "azurerm_resource_group.host.id"
    assert _attr(role, "assignable_scopes") == "[azurerm_resource_group.host.id]"


def test_its_role_is_assigned_to_the_logic_app_s_identity_on_orodruins_vm_alone():
    grant = _block(_text("drill_autostart.tf"), "azurerm_role_assignment", "drill_autostart")
    assert _attr(grant, "scope") == "azurerm_linux_virtual_machine.host.id"
    assert _attr(grant, "role_definition_id") == "azurerm_role_definition.drill_autostart.role_definition_resource_id"
    assert _attr(grant, "principal_id") == "local.autostart_outputs.principalId.value"
    assert _attr(grant, "principal_type") == '"ServicePrincipal"'
    assert "for_each" not in grant and "count" not in grant
    # The identity is the Logic App's, as the deployment returns it.
    out = _template()["outputs"]["principalId"]["value"]
    assert out == ("[reference(resourceId('Microsoft.Logic/workflows', parameters('name')), '2019-05-01', "
                   "'Full').identity.principalId]")


def test_orodruins_own_identity_gains_nothing():
    """§6.1, geste 2: no right more for Orodruin's identity — its `start` on a target is already in the
    contract (injector_vm). Nothing in DRL1c names it."""
    code = "\n".join(line for line in _text("drill_autostart.tf").splitlines() if not line.lstrip().startswith("#"))
    assert "identity[0].principal_id" not in code
    assert "data.azurerm_resource_group.bench" not in code and "data.azurerm_subscription" not in code


# ── The shutdown of 23:00 UTC ────────────────────────────────────────────────────────────────

def test_orodruin_is_shut_down_every_day_at_23_utc(ops):
    off = _block(_text("drill_autostart.tf"), "azurerm_dev_test_global_vm_shutdown_schedule", "host")
    assert _attr(off, "virtual_machine_id") == "azurerm_linux_virtual_machine.host.id"
    assert _attr(off, "enabled") == "true"
    assert _attr(off, "daily_recurrence_time") == '"2300"'
    assert _attr(off, "timezone") == '"UTC"'
    assert "count" not in off and "for_each" not in off
    # The hour the arming guards (drill_ops.shutdown_guard, DRL1e) is this one.
    assert _attr(off, "daily_recurrence_time") == f'"{ops.SHUTDOWN_MIN // 60:02d}{ops.SHUTDOWN_MIN % 60:02d}"'


# ── The output: the contract drill_ops reads ─────────────────────────────────────────────────

def test_the_output_is_the_logic_app_s_id_as_drill_ops_reads_it(ops):
    outputs = _text("outputs.tf")
    block = outputs.split('output "drill_autostart_id" {')[1].split("\n}\n")[0]
    assert _attr(block, "value") == "local.autostart_outputs.workflowId.value"
    assert _template()["outputs"]["workflowId"]["value"] == "[resourceId('Microsoft.Logic/workflows', parameters('name'))]"
    tf = _text("drill_autostart.tf")
    assert 'autostart_name = "logic-${local.name}-drill"' in tf
    assert re.search(r"^\s+name\s+= \{ value = local\.autostart_name \}$", tf, re.M)
    # What `terraform output -json` would say once applied, an example: the id read, the name DRL1c gives.
    logic = f"/subscriptions/{SUB}/resourceGroups/rg-orodruin/providers/Microsoft.Logic/workflows/logic-orodruin-drill"
    sample = json.dumps({"vm_id": {"value": "x"}, "drill_autostart_id": {"sensitive": False, "type": "string",
                                                                         "value": logic}})
    assert ops.autostart_id(sample) == logic
    assert ops.AUTOSTART_OUTPUT == "drill_autostart_id"


def test_the_plan_of_the_module_holds_the_same_contract():
    """The same contract, planned against a fake azurerm (`terraform test`, the CI's terraform-test job)."""
    tftest = _text("tests/drill_autostart.tftest.hcl")
    for run in ("the_scheduled_start_is_created_disabled_on_its_one_weekly_trigger",
                "its_hour_comes_from_drill_autostart_at", "an_hour_that_is_not_one_is_refused",
                "a_day_spelled_out_is_refused", "an_hour_without_its_day_is_refused",
                "its_role_starts_orodruin_and_nothing_else", "orodruin_is_shut_down_every_day_at_23_utc"):
        assert f'run "{run}"' in tftest, run
    assert "command = apply" not in tftest
    # Only example identifiers: the zero subscription.
    assert set(re.findall(r"/subscriptions/([0-9a-f-]{36})", tftest)) == {SUB}
