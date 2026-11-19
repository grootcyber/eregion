"""DRL1c (#613): the drill's scheduled start in Terraform — the Logic App created Disabled, its one weekly
trigger at the drill's schedule less 20 min, its identity's role of one action on Orodruin's VM alone, and
Orodruin's shutdown of 23:00 UTC (infra/orodruin/drill_autostart.tf, drill_autostart.json; docs/design/
drill-banc.md §5.1, §9, §11). M5881–M5900, each caught by tests/unit/test_drill_autostart.py.

The form of a lot's file, as scripts/mutation_check.py loads it: MUTANTS, TESTS (its own ids); its paths
as plain strings.
"""
TF = "infra/orodruin/drill_autostart.tf"
TPL = "infra/orodruin/drill_autostart.json"
VARS = "infra/orodruin/variables.tf"
OUT = "infra/orodruin/outputs.tf"
T = "tests/unit/test_drill_autostart.py::"

_DISABLED = T + "test_the_logic_app_is_created_disabled_by_the_template_itself"
_NO_APPLY = T + "test_no_apply_enables_the_scheduled_start"
_ACTION = T + "test_its_one_action_starts_orodruins_vm_by_its_own_identity"
_DEFAULT = T + "test_the_default_hour_is_the_shipped_drill_s_schedule_less_20_min"
_TRIGGER = T + "test_the_trigger_drill_ops_reads_is_drill_autostart_at"
_VARIABLE = T + "test_the_variable_takes_only_a_day_and_an_hour"
_ROLE = T + "test_its_role_is_one_action_assignable_in_orodruins_group_alone"
_GRANT = T + "test_its_role_is_assigned_to_the_logic_app_s_identity_on_orodruins_vm_alone"
_ORODRUIN = T + "test_orodruins_own_identity_gains_nothing"
_SHUTDOWN = T + "test_orodruin_is_shut_down_every_day_at_23_utc"
_OUTPUT = T + "test_the_output_is_the_logic_app_s_id_as_drill_ops_reads_it"

MUTANTS = [
    # The state: created Disabled, and no apply enabling it.
    ("M5881", "the Logic App created Enabled: the first apply wakes Orodruin every week, never armed (DRL1c)",
     TPL, '        "state": "Disabled",\n', '        "state": "Enabled",\n'),
    ("M5882", "the template carries no state: each apply that deploys it is a PUT without one, ARM's default "
     "re-enabling a scheduled start the kill disabled (DRL1c)", TPL, '        "state": "Disabled",\n', ""),
    ("M5883", "an apply re-enables the scheduled start: a local-exec posts …/enable after each deployment "
     "(DRL1c)", TF, "locals {\n  autostart_outputs",
     'resource "terraform_data" "autostart_on" {\n  triggers_replace = [azurerm_resource_group_template_deployment'
     '.drill_autostart.id]\n  provisioner "local-exec" {\n    command = "az rest --method post --url '
     'https://management.azure.com${local.autostart_outputs.workflowId.value}/enable?api-version=2019-05-01"\n'
     "  }\n}\n\nlocals {\n  autostart_outputs"),
    ("M5884", "the template deployed in Complete mode: an apply deletes every other resource of Orodruin's "
     "group (DRL1c)", TF, 'deployment_mode     = "Incremental"', 'deployment_mode     = "Complete"'),
    # The role: one action, Orodruin's group, Orodruin's VM.
    ("M5885", "the scheduled start's role gains an action: Run Command on Orodruin by the Logic App's identity "
     "(DRL1c)", TF, '      "Microsoft.Compute/virtualMachines/start/action",\n',
     '      "Microsoft.Compute/virtualMachines/start/action",\n'
     '      "Microsoft.Compute/virtualMachines/runCommand/action",\n'),
    ("M5886", "the scheduled start's role assignable on the bench: one assignment away from starting its VMs "
     "(DRL1c)", TF, "  assignable_scopes = [azurerm_resource_group.host.id]",
     "  assignable_scopes = [azurerm_resource_group.host.id, data.azurerm_resource_group.bench.id]"),
    ("M5887", "the scheduled start's role assignable on the whole subscription (DRL1c)", TF,
     "  assignable_scopes = [azurerm_resource_group.host.id]",
     "  assignable_scopes = [data.azurerm_subscription.current.id]"),
    ("M5888", "the scheduled start's role assigned on Orodruin's group: every VM in it started, beyond "
     "Orodruin's (DRL1c)", TF, "  scope              = azurerm_linux_virtual_machine.host.id\n"
     "  role_definition_id = azurerm_role_definition.drill_autostart",
     "  scope              = azurerm_resource_group.host.id\n"
     "  role_definition_id = azurerm_role_definition.drill_autostart"),
    ("M5889", "the scheduled start's role given to Orodruin's own identity, not the Logic App's: a right more "
     "for the injectors' host (DRL1c)", TF,
     "  principal_id       = local.autostart_outputs.principalId.value",
     "  principal_id       = azurerm_linux_virtual_machine.host.identity[0].principal_id"),
    # The hour: the drill's schedule less 20 min.
    ("M5890", "the scheduled start at the drill's own hour, not 20 min before: Orodruin not up when the "
     "timer fires (DRL1c)", VARS, '  default     = "tue 18:40"', '  default     = "tue 19:00"'),
    ("M5891", "the day's table shifted: « tue » wakes Orodruin on Wednesday (DRL1c)", TF,
     'tue = "Tuesday"', 'tue = "Wednesday"'),
    ("M5892", "the hour taken from the minutes: « tue 18:40 » wakes Orodruin at 40:18, never (DRL1c)", TF,
     "    hour     = { value = tonumber(local.autostart_hm[0]) }",
     "    hour     = { value = tonumber(local.autostart_hm[1]) }"),
    ("M5893", "the recurrence daily: Orodruin woken every day, the arming's check refuses (DRL1c)", TPL,
     '"frequency": "Week"', '"frequency": "Day"'),
    ("M5894", "the recurrence in Paris time: the scheduled start an hour off the drill, half the year "
     "(DRL1c)", TPL, '"timeZone": "UTC"', '"timeZone": "Romance Standard Time"'),
    ("M5899", "drill_autostart_at takes 24:00 or 99:99: the trigger fails at deployment, or never fires "
     "(DRL1c)", VARS, '"^(mon|tue|wed|thu|fri|sat|sun) ([01][0-9]|2[0-3]):[0-5][0-9]$"',
     '"^(mon|tue|wed|thu|fri|sat|sun) [0-9]{2}:[0-9]{2}$"'),
    # The action: Orodruin's VM, nothing to read.
    ("M5897", "the start followed to its end: the Logic App reads the operation, a right its role does not "
     "hold (DRL1c)", TPL, '              "operationOptions": "DisableAsyncPattern",\n', ""),
    ("M5900", "the Logic App starts another resource than Orodruin's VM (DRL1c)", TF,
     "    vmId     = { value = azurerm_linux_virtual_machine.host.id }",
     "    vmId     = { value = azurerm_resource_group.host.id }"),
    # The shutdown of 23:00 UTC.
    ("M5895", "Orodruin's shutdown disabled: left up all night after the drill (DRL1c)", TF,
     '  enabled               = true\n  daily_recurrence_time = "2300"',
     '  enabled               = false\n  daily_recurrence_time = "2300"'),
    ("M5896", "Orodruin shut down at 07:00 UTC, not 23:00: up twelve hours after the drill (DRL1c)", TF,
     'daily_recurrence_time = "2300"', 'daily_recurrence_time = "0700"'),
    # The output: the contract drill_ops reads.
    ("M5898", "drill_autostart_id gives the Logic App's identity, not its id: « unreadable » for the arming "
     "and the kill (DRL1c)", OUT, "  value       = local.autostart_outputs.workflowId.value",
     "  value       = local.autostart_outputs.principalId.value"),
]
TESTS = {
    "M5881": _DISABLED,
    "M5882": _DISABLED,
    "M5883": _NO_APPLY,
    "M5884": _NO_APPLY,
    "M5885": _ROLE,
    "M5886": _ROLE,
    "M5887": _ROLE + " " + _ORODRUIN,
    "M5888": _GRANT,
    "M5889": _GRANT + " " + _ORODRUIN,
    "M5890": _DEFAULT,
    "M5891": _TRIGGER,
    "M5892": _TRIGGER,
    "M5893": _TRIGGER,
    "M5894": _TRIGGER,
    "M5899": _VARIABLE,
    "M5897": _ACTION,
    "M5900": _ACTION,
    "M5895": _SHUTDOWN,
    "M5896": _SHUTDOWN,
    "M5898": _OUTPUT,
}
