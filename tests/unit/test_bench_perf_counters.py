"""DCR1 (#985): the bench DCR's performance counters, under the names the Azure Monitor agent knows on Linux.

On 20/11 the bench DCR declared `\\Processor(_Total)\\% Processor Time` and
`\\Network Interface(*)\\Bytes Sent/sec` (Windows names); on gondolin (Linux) only `Logical Disk` reached
`Perf`. Microsoft Learn's list of the Linux counters the agent collects
(DOC_URL, « Legacy Windows and Linux performance counters », Linux tab) has no `_Total` instance and no
`Network Interface` object: the processor is `Processor(*)`, the network `Network(*)`. The disk keeps the
name measured at the bench (a Windows disk name resolves to the same Linux counter, and both at once
collect it twice: DUPLICATE_URL). Read from the files, no Azure, no Terraform needed (the CI's
terraform-test job plans the same list against a fake azurerm: infra/terraform/tests/perf_counters.tftest.hcl):
  - the list is frozen as it is, the processor and the network under their Linux objects, in Learn's list;
  - no Windows name the Linux agent does not collect comes back (`_Total`, `Network Interface`,
    `Processor Information`);
  - the disk keeps arriving: its two counters, to the Perf table, and the alert and the shipped rule that
    read it under `Logical Disk`;
  - every VM associated with this DCR is a Linux VM (a Windows VM would need its own DCR: no Windows case
    in the module today);
  - `make celebrimbor-dcr-plan` / `-up` touch the DCR alone, never with a `-var` of their own — against a
    fake `terraform` first on the PATH.
Mutants M6790–M6799 (scripts/mutants/DCR1.py).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TF = ROOT / "infra/terraform"
MON = TF / "monitoring.tf"
TFTEST = TF / "tests/perf_counters.tftest.hcl"

DOC_URL = "https://learn.microsoft.com/en-us/azure/azure-monitor/vm/metrics-guest-reference"
DUPLICATE_URL = "https://learn.microsoft.com/en-us/azure/azure-monitor/vm/data-collection-performance"

# The Linux tab of DOC_URL (read on 2026-11-20, page updated 2026-08-26), the CPU, disk and network rows,
# copied as written there.
LINUX_COUNTERS = {
    r"Processor(*)\% Processor Time", r"Processor(*)\% Idle Time", r"Processor(*)\% User Time",
    r"Processor(*)\% Nice Time", r"Processor(*)\% Privileged Time", r"Processor(*)\% IO Wait Time",
    r"Processor(*)\% Interrupt Time",
    r"Logical Disk(*)\% Free Inodes", r"Logical Disk(*)\% Used Inodes", r"Logical Disk(*)\Free Megabytes",
    r"Logical Disk(*)\% Free Space", r"Logical Disk(*)\% Used Space", r"Logical Disk(*)\Logical Disk Bytes/sec",
    r"Logical Disk(*)\Disk Read Bytes/sec", r"Logical Disk(*)\Disk Write Bytes/sec",
    r"Logical Disk(*)\Disk Transfers/sec", r"Logical Disk(*)\Disk Reads/sec", r"Logical Disk(*)\Disk Writes/sec",
    r"Network(*)\Total Bytes Transmitted", r"Network(*)\Total Bytes Received", r"Network(*)\Total Bytes",
    r"Network(*)\Total Packets Transmitted", r"Network(*)\Total Packets Received", r"Network(*)\Total Rx Errors",
    r"Network(*)\Total Tx Errors", r"Network(*)\Total Collisions",
}
# The disk, under the names measured at the bench (20/11: `Logical Disk`, both counters, several instances).
DISK = [r"\LogicalDisk(*)\Disk Write Bytes/sec", r"\LogicalDisk(*)\Disk Read Bytes/sec"]
FROZEN = DISK + [r"\Network(*)\Total Bytes Transmitted", r"\Processor(*)\% Processor Time"]
WINDOWS_ONLY = ("_Total", "Network Interface", "Processor Information")


def _hcl_strings(text: str) -> list[str]:
    """The HCL string literals of a list, unescaped (`\\\\` → `\\`)."""
    return [s.replace("\\\\", "\\") for s in re.findall(r'"((?:[^"\\]|\\.)*)"', text)]


def _block(text: str, start: str) -> str:
    i = text.index(start)
    depth, j = 0, text.index("{", i)
    while True:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
        if depth == 0:
            return text[i:j]


def _perf_block() -> str:
    dcr = _block(MON.read_text(), 'resource "azurerm_monitor_data_collection_rule" "celebrimbor"')
    return _block(dcr, "performance_counter {")


def _counters() -> list[str]:
    m = re.search(r"(?s)counter_specifiers = \[(.*?)\]", _perf_block())
    assert m, "no counter_specifiers in the bench DCR"
    return _hcl_strings(m.group(1))


def _linux(spec: str) -> str:
    """A specifier as Learn's Linux table writes it: no leading backslash."""
    return spec.removeprefix("\\")


def test_the_list_is_frozen():
    assert _counters() == FROZEN


def test_processor_and_network_under_their_linux_objects():
    for spec in _counters():
        if spec in DISK:
            continue
        assert _linux(spec) in LINUX_COUNTERS, f"{spec} is not in Learn's Linux list ({DOC_URL})"
    objects = {_linux(s).split("(")[0] for s in _counters()}
    assert {"Processor", "Network"} <= objects


def test_no_windows_name_the_linux_agent_does_not_collect():
    for spec in _counters():
        for name in WINDOWS_ONLY:
            assert name not in spec, f"{spec}: {name} is a Windows name, never collected on Linux"


def test_the_disk_keeps_arriving():
    counters = _counters()
    for spec in DISK:
        assert spec in counters, f"{spec} removed: the disk no longer reaches Perf"
        # The Linux counter it resolves to is in Learn's list.
        assert _linux(spec).replace("LogicalDisk", "Logical Disk") in LINUX_COUNTERS
    # One name per counter: a Windows and a Linux name of the same disk counter collect it twice.
    linux_names = [_linux(s).replace("LogicalDisk", "Logical Disk") for s in counters]
    assert len(linux_names) == len(set(linux_names))


def test_the_counters_go_to_the_perf_table():
    perf = _perf_block()
    assert re.search(r'(?m)^\s*streams\s*= \["Microsoft-Perf"\]$', perf)
    dcr = _block(MON.read_text(), 'resource "azurerm_monitor_data_collection_rule" "celebrimbor"')
    flow = _block(dcr, "data_flow {")
    m = re.search(r"streams\s*= \[(.*?)\]", flow)
    assert m and "Microsoft-Perf" in _hcl_strings(m.group(1))


def test_what_reads_the_disk_reads_the_name_that_arrives():
    """The bench's alert and the shipped ransomware rule read the disk under `Logical Disk`, the measured name."""
    alert = _block(MON.read_text(), 'resource "azurerm_monitor_scheduled_query_rules_alert_v2" "disk_write_anomaly"')
    assert 'ObjectName == "Logical Disk" and CounterName == "Disk Write Bytes/sec"' in alert
    rules = (ROOT / "glorfindel/rules/azure/detection_rules.yaml").read_text()
    assert 'ObjectName == "Logical Disk"' in rules and "Disk Write Bytes/sec" in rules


def test_every_vm_on_the_dcr_is_a_linux_vm():
    """A Windows VM on this DCR would get Linux names it does not collect: it needs a DCR of its own."""
    found = 0
    for f in sorted(TF.glob("*.tf")):
        text = f.read_text()
        assert "azurerm_windows_virtual_machine" not in text, f.name
        for m in re.finditer(r'(?m)^resource "azurerm_monitor_data_collection_rule_association" "[\w-]+" \{', text):
            body = _block(text, m.group(0))
            if "azurerm_monitor_data_collection_rule.celebrimbor.id" not in body:
                continue
            found += 1
            target = re.search(r"(?m)^\s*target_resource_id\s*=\s*(\S+)$", body)
            assert target and target.group(1).startswith("azurerm_linux_virtual_machine."), (f.name, body)
    assert found >= 3  # the baseline VMs, multinic, sharednsg


def test_the_terraform_test_freezes_the_same_list():
    text = TFTEST.read_text()
    assert 'run "linux_counters_the_disk_kept_the_windows_names_gone"' in text
    m = re.search(r"(?s)counter_specifiers == tolist\(\[(.*?)\]\)", text)
    assert m and _hcl_strings(m.group(1)) == FROZEN
    assert re.search(r"(?m)^  cron_logs_enabled\s*= false$", text) and re.search(r"(?m)^  auditd_enabled\s*= false$", text)


def test_the_docs_give_the_names_and_their_source():
    azure = (ROOT / "docs/azure.md").read_text()
    assert DOC_URL in azure and r"`\Processor(*)\% Processor Time`" in azure
    assert "don't specify a platform type" in azure and "`kind`" in azure
    ops = (ROOT / "docs/operations.md").read_text()
    assert "## Les compteurs de performance du banc (DCR1, #985)" in ops
    assert "make celebrimbor-dcr-plan" in ops and "| distinct ObjectName, CounterName, InstanceName" in ops


def test_the_subscription_is_checked_before_any_gesture():
    """`export ARM_SUBSCRIPTION_ID ?=`: one already set in the shell reaches Terraform (G1, 20/11)."""
    ops = (ROOT / "docs/operations.md").read_text()
    section = ops[ops.index("## Les compteurs de performance du banc (DCR1, #985)"):]
    section = section[:section.index("\n## ", 1)]
    guard = section.index("### Avant tout : le bon abonnement")
    assert guard < section.index("### Avant tout : la DCR déployée") < section.index("make celebrimbor-dcr-plan")
    block = section[guard:section.index("### Avant tout : la DCR déployée")]
    assert '[ -z "${ARM_SUBSCRIPTION_ID:-}" ] || [ "$ARM_SUBSCRIPTION_ID" = "$AZURE_SUBSCRIPTION_ID" ] || echo' in block
    assert '[ "$(az account show --query id -o tsv)" = "$AZURE_SUBSCRIPTION_ID" ] || echo' in block
    assert "s'arrêter" in block and "```zsh" in block
    # Nothing that prints an id.
    assert "echo $" not in block and 'echo "$' not in block
    assert "export ARM_SUBSCRIPTION_ID ?= $(AZURE_SUBSCRIPTION_ID)" in (ROOT / "Makefile").read_text()


# ── the Make targets, against a fake terraform ───────────────────────────────

pytestmark_make = pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
TARGETS = ["-target=azurerm_monitor_data_collection_rule.celebrimbor"]


BENCH_SUB = "11111111-aaaa-4bbb-8ccc-000000000001"
OTHER_SUB = "22222222-aaaa-4bbb-8ccc-000000000002"


def _make(tmp_path, target, *args, active=BENCH_SUB):
    """A fake ``terraform`` that writes down its arguments, and a fake ``az`` whose
    ``account show`` answers ``active``: the subscription guard (G1c) reads it first."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    tfvars_dir = tmp_path / "tfvars"   # the guard's, empty: never the operator's terraform.tfvars
    tfvars_dir.mkdir(exist_ok=True)
    log = tmp_path / "tf.log"
    log.write_text("")
    tf = bin_dir / "terraform"
    tf.write_text('#!/bin/sh\necho "$*" >> "$FAKE_TF_LOG"\n')
    tf.chmod(0o755)
    az = bin_dir / "az"
    az.write_text('#!/bin/sh\nprintf "%s\\n" "$FAKE_AZ_SUB"\n')
    az.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_TF_LOG": str(log),
           "HOME": str(tmp_path), "AZURE_SUBSCRIPTION_ID": BENCH_SUB, "FAKE_AZ_SUB": active}
    for var in ("INSTANCE", "YES", "TOPO", "ARM_SUBSCRIPTION_ID", "TF_VAR_subscription_id",
                "CELEBRIMBOR_TFVARS_DIR"):
        env.pop(var, None)
    res = subprocess.run(["make", "-s", "--no-print-directory", "-C", str(ROOT), target, *args,
                          f"CELEBRIMBOR_TFVARS_DIR={tfvars_dir}"],
                         env=env, capture_output=True, text=True, timeout=60)
    return res.returncode, res.stdout + res.stderr, [c.split() for c in log.read_text().splitlines()]


@pytestmark_make
@pytest.mark.parametrize("target", ["celebrimbor-dcr-plan", "celebrimbor-dcr-up"])
def test_dcr_targets_never_run_terraform_off_the_bench_s_subscription(tmp_path, target):
    """G1c's guard: az on another subscription, terraform is never run — the variable named, never
    the value (the 20/11 apply that went to another subscription)."""
    code, out, calls = _make(tmp_path, target, "YES=1", active=OTHER_SUB)
    assert code != 0 and calls == [], out
    assert "L'abonnement actif d'az n'est pas AZURE_SUBSCRIPTION_ID" in out
    assert BENCH_SUB not in out and OTHER_SUB not in out


@pytestmark_make
@pytest.mark.parametrize("args,instance", [((), "default"), (("INSTANCE=ci-1234",), "ci-1234")])
def test_dcr_plan_plans_the_dcr_alone(tmp_path, args, instance):
    code, out, calls = _make(tmp_path, "celebrimbor-dcr-plan", *args)
    assert code == 0, out
    chdir = "-chdir=infra/terraform"
    assert calls == [[chdir, "init"], [chdir, "workspace", "select", instance], [chdir, "plan", *TARGETS]]


@pytest.mark.parametrize("args,approve", [((), []), (("YES=1",), ["-auto-approve"])])
@pytestmark_make
def test_dcr_up_applies_it_alone_confirmed_unless_yes(tmp_path, args, approve):
    code, out, calls = _make(tmp_path, "celebrimbor-dcr-up", *args)
    assert code == 0, out
    assert calls[-1] == ["-chdir=infra/terraform", "apply", *approve, *TARGETS]
    assert not any(a.startswith("-var") for c in calls for a in c)
