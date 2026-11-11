"""INF-FL (#654): the bench's network flow logs in an account of their own, which no identity
reachable from a watched VM writes (infra/terraform/storage.tf, monitoring.tf) — the prerequisite of
the proof by connection (SEC-A3f; docs/design/corroboration.md, CR15). M4760–M4764, measured by
tests/unit/test_bench_flow_logs.py (the Terraform plan itself: infra/terraform/tests/flow_logs.tftest.hcl).
"""
STORAGE_TF = "infra/terraform/storage.tf"
MONITORING_TF = "infra/terraform/monitoring.tf"
LOCALS_TF = "infra/terraform/locals.tf"
MAIN_TF = "infra/terraform/main.tf"
_TESTS = "tests/unit/test_bench_flow_logs.py"

MUTANTS = [
    ("M4760", "the flow log writes to the exercises' account again: a VM's identity writes or deletes the "
     "proof of a connection (INF-FL)", MONITORING_TF,
     "  storage_account_id = azurerm_storage_account.flows.id\n",
     "  storage_account_id = azurerm_storage_account.exfil.id\n"),
    ("M4761", "the exercises' write at the bench group's scope: inherited by the flows account, every enrolled "
     "VM writes its blobs (INF-FL)", STORAGE_TF,
     "  scope                = azurerm_storage_account.exfil.id\n",
     "  scope                = azurerm_resource_group.celebrimbor.id\n"),
    ("M4762", "the flows account accepts the shared key whatever the variable: a key or a SAS left on a VM "
     "writes there (INF-FL)", STORAGE_TF,
     "  shared_access_key_enabled       = var.flow_logs_shared_key_enabled\n",
     "  shared_access_key_enabled       = true\n"),
    ("M4763", "the flows account named as the exercises' one: one account, the separation undone (INF-FL)",
     LOCALS_TF,
     'flows_storage_name = local.instance == "default" ? "stcelebrimborflows"',
     'flows_storage_name = local.instance == "default" ? "stcelebrimborexfil"'),
    ("M4764", "the provider reads each account's data plane with its key again: the flows account without a "
     "key fails every plan of the bench (INF-FL)", MAIN_TF,
     "      data_plane_available = false\n", "      data_plane_available = true\n"),
]
TESTS = {f"M{n}": _TESTS for n in range(4760, 4765)}
