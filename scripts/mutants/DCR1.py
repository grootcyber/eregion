"""DCR1 (#985): the bench DCR's processor and network counters under the names the Azure Monitor agent
collects on Linux, the disk kept as measured, the counters to the Perf table, Linux VMs only on the DCR,
and the DCR planned and applied alone. One mutant per property, M6790–M6799, measured by
tests/unit/test_bench_perf_counters.py (the module has no Windows VM: no Windows case to break)."""
MON = "infra/terraform/monitoring.tf"
MAKE = "Makefile"
_T = "tests/unit/test_bench_perf_counters.py"

MUTANTS = [
    ("M6790", "the processor back under its Windows name, never collected on Linux (DCR1)", MON,
     '        "\\\\Processor(*)\\\\% Processor Time",\n',
     '        "\\\\Processor(_Total)\\\\% Processor Time",\n'),
    ("M6791", "the network back under its Windows object, never collected on Linux (DCR1)", MON,
     '        "\\\\Network(*)\\\\Total Bytes Transmitted",\n',
     '        "\\\\Network Interface(*)\\\\Bytes Sent/sec",\n'),
    ("M6792", "the disk's writes removed: the ransomware signal no longer reaches Perf (DCR1)", MON,
     '        "\\\\LogicalDisk(*)\\\\Disk Write Bytes/sec",\n',
     ""),
    ("M6793", "the disk's reads removed (DCR1)", MON,
     '        "\\\\LogicalDisk(*)\\\\Disk Read Bytes/sec",\n',
     ""),
    ("M6794", "the counters sent to the metrics stream only: nothing reaches the Perf table (DCR1)", MON,
     '      streams                       = ["Microsoft-Perf"]\n',
     '      streams                       = ["Microsoft-InsightsMetrics"]\n'),
    ("M6795", "the data flow no longer carries Microsoft-Perf to the workspace (DCR1)", MON,
     '    streams      = ["Microsoft-Perf", "Microsoft-Syslog"]\n',
     '    streams      = ["Microsoft-Syslog"]\n'),
    ("M6796", "the disk alert reads the Windows object name, which never arrives from Linux (DCR1)", MON,
     '      | where ObjectName == "Logical Disk" and CounterName == "Disk Write Bytes/sec"\n',
     '      | where ObjectName == "LogicalDisk" and CounterName == "Disk Write Bytes/sec"\n'),
    ("M6797", "the targeted plan plans the whole bench (DCR1)", MAKE,
     "DCR_TARGETS = -target=azurerm_monitor_data_collection_rule.celebrimbor\n",
     "DCR_TARGETS =\n"),
    ("M6798", "the targeted apply never asks: applied without YES=1 (DCR1)", MAKE,
     "\t@$(TF) apply$(if $(YES), -auto-approve) $(DCR_TARGETS)\n",
     "\t@$(TF) apply -auto-approve $(DCR_TARGETS)\n"),
    ("M6799", "a Windows VM on the Linux DCR: Linux names it does not collect (DCR1)", MON,
     "  target_resource_id      = azurerm_linux_virtual_machine.baseline[each.key].id\n",
     "  target_resource_id      = azurerm_windows_virtual_machine.baseline[each.key].id\n"),
]

TESTS = {
    "M6790": f"{_T}::test_the_list_is_frozen",
    "M6791": f"{_T}::test_processor_and_network_under_their_linux_objects",
    "M6792": f"{_T}::test_the_disk_keeps_arriving",
    "M6793": f"{_T}::test_the_disk_keeps_arriving",
    "M6794": f"{_T}::test_the_counters_go_to_the_perf_table",
    "M6795": f"{_T}::test_the_counters_go_to_the_perf_table",
    "M6796": f"{_T}::test_what_reads_the_disk_reads_the_name_that_arrives",
    "M6797": f"{_T}::test_dcr_plan_plans_the_dcr_alone",
    "M6798": f"{_T}::test_dcr_up_applies_it_alone_confirmed_unless_yes",
    "M6799": f"{_T}::test_every_vm_on_the_dcr_is_a_linux_vm",
}
