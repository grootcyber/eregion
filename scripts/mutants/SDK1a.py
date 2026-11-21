"""SDK1a (#992): the readers of Log Analytics rows read on the pinned SDK's own objects — a `dynamic`
column as its JSON text, a `datetime` column as a `datetime`, a partial reply and the SDK's errors as
the SDK gives them —, the utility that builds them saying what the service sends, the floor of the
SDK in pyproject.toml held to the lock. M6820–M6824, measured by tests/unit/test_sdk_contracts.py and
tests/unit/test_dependency_lock.py."""
_T = "tests/unit/test_sdk_contracts.py"
_LOCK = "tests/unit/test_dependency_lock.py"

MUTANTS = [
    ("M6820", "a reader of a dynamic column brought back to its object-only form: the Activity Log's "
     "`Claims_d`, as the SDK hands it on, read as no claims — Glorfindel's own write named by them a "
     "card (SDK1a)", "glorfindel/providers/azure/activity.py",
     "    if isinstance(raw, str):\n        try:\n            raw = json.loads(raw)\n"
     "        except ValueError:\n            return {}\n    return raw if isinstance(raw, dict) else {}\n",
     "    return raw if isinstance(raw, dict) else {}\n"),
    ("M6821", "a datetime read as a text only: the start of a Run Command as the SDK hands it on is "
     "unreadable, the drain of an isolation a card (SDK1a)", "glorfindel/providers/azure/own_run_command.py",
     "    if isinstance(value, datetime):\n        dt = value\n    elif isinstance(value, str) and value.strip():\n",
     "    if isinstance(value, str) and value.strip():\n"),
    ("M6822", "the reply's status no longer read: a partial reply of the SDK fails on its missing tables, "
     "an unknown error for `rules check` and the CD, never « partial » (SDK1a)",
     "glorfindel/providers/azure/monitor.py",
     "        if response.status != LogsQueryStatus.SUCCESS:\n"
     "            detail = getattr(response, \"partial_error\", None) or response.status\n"
     "            raise RuntimeError(f\"workspace query not successful: {detail}\")\n        rows = []\n",
     "        rows = []\n"),
    ("M6823", "the utility hands a dynamic column on as kql_subset's list — the form SLF1 passed its tests "
     "on, never what the SDK gives (SDK1a)", "tests/unit/sdk_logs.py",
     "    if ctype == \"dynamic\" and not isinstance(value, str):\n        return json.dumps(value)\n",
     ""),
    ("M6824", "the floor of the SDK relaxed back to 1.3: a release line Glorfindel's readers were never "
     "read on admitted (SDK1a)", "pyproject.toml",
     "    \"azure-monitor-query>=2.0\",\n", "    \"azure-monitor-query>=1.3\",\n"),
]
TESTS = {
    "M6820": f"{_T}::test_glorfindel_s_own_write_named_by_its_claims_is_set_aside_through_the_sdk",
    "M6821": f"{_T}::test_the_drain_of_an_isolation_read_through_the_sdk_is_nothing",
    "M6822": f"{_T}::test_run_query_raises_on_a_partial_reply_and_lets_the_sdk_error_through "
             f"{_T}::test_rules_check_reads_the_sdk_s_rows_and_errors",
    "M6823": f"{_T}::test_every_type_comes_out_as_the_sdk_hands_it_on",
    "M6824": f"{_LOCK}::test_the_floor_of_the_log_analytics_sdk_is_the_release_line_the_lock_tests",
}
