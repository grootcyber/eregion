"""SDK1r (Partie de #992): Annatar's Log Analytics collector read through the pinned SDK's own
objects. `AzureMonitorCollector` (annatar/collectors/azure_monitor.py) had no test; SDK1r drives it
through the real `LogsQueryClient` over sdk_logs' in-memory transport. One mutant per reading step
of its two polls (heartbeat, alert), M6826–M6830, measured by tests/unit/test_annatar_collector_sdk.py.

Forme chargée par scripts/mutation_check.py : MUTANTS (id, description, fichier, old, new) et
TESTS (ses ids → le test qui l'attrape) ; chemins en chaînes.
"""
COLL = "annatar/collectors/azure_monitor.py"
_T = "tests/unit/test_annatar_collector_sdk.py"

_NULL = f"{_T}::test_wait_for_heartbeat_rejects_a_null_last_heartbeat"
_HB_OK = f"{_T}::test_wait_for_heartbeat_reads_the_sdk_datetime_row"
_SOURCE = f"{_T}::test_poll_alert_refuses_an_unknown_source"
_ALERT_EMPTY = f"{_T}::test_poll_alert_times_out_when_no_rows"
_ALERT_OK = f"{_T}::test_poll_alert_reads_the_sdk_rows"

# The heartbeat poll's success block (lines guarded by the status) and the alert poll's — the two
# share the status line, so a status mutant carries the method's own next lines to stay unique.
_HB_STATUS_OLD = ("                if response.status == LogsQueryStatus.SUCCESS:\n"
                  "                    for table in response.tables:\n"
                  "                        if table.rows and table.rows[0][0] is not None:")
_HB_STATUS_NEW = ("                if response.status != LogsQueryStatus.SUCCESS:\n"
                  "                    for table in response.tables:\n"
                  "                        if table.rows and table.rows[0][0] is not None:")
_ALERT_STATUS_OLD = ("                if response.status == LogsQueryStatus.SUCCESS:\n"
                     "                    for table in response.tables:\n"
                     "                        if table.rows:")
_ALERT_STATUS_NEW = ("                if response.status != LogsQueryStatus.SUCCESS:\n"
                     "                    for table in response.tables:\n"
                     "                        if table.rows:")

MUTANTS = [
    ("M6826", "the heartbeat accepts a null LastHeartbeat: the empty summary taken for a pulse (SDK1r)",
     COLL, "if table.rows and table.rows[0][0] is not None:", "if table.rows:"),
    ("M6827", "the heartbeat poll ignores a successful reply: never reads a heartbeat (SDK1r)",
     COLL, _HB_STATUS_OLD, _HB_STATUS_NEW),
    ("M6828", "the alert poll accepts azure_monitor and refuses it: the source check inverted (SDK1r)",
     COLL, 'if source != "azure_monitor":', 'if source == "azure_monitor":'),
    ("M6829", "the alert poll fires on an empty table and not on rows: the row check inverted (SDK1r)",
     COLL, "                        if table.rows:", "                        if not table.rows:"),
    ("M6830", "the alert poll ignores a successful reply: never reads an alert (SDK1r)",
     COLL, _ALERT_STATUS_OLD, _ALERT_STATUS_NEW),
]

TESTS = {
    "M6826": _NULL,
    "M6827": _HB_OK,
    "M6828": _SOURCE,
    "M6829": _ALERT_EMPTY,
    "M6830": _ALERT_OK,
}
