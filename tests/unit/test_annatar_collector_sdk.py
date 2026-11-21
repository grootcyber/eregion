"""SDK1r (#992): Annatar's Log Analytics collector, read through the pinned SDK's own objects.

`AzureMonitorCollector` (annatar/collectors/azure_monitor.py) polls Log Analytics for the VM's
heartbeat after a restore and for an attack's alert. Before SDK1r it had no test at all; here it is
driven through the real `LogsQueryClient` over sdk_logs' in-memory transport (tests/unit/sdk_logs.py)
— never a hand-made response. The collector reads a `LogsQueryResult`, as the service sends it.

D1 (the Annatar component runs alone, Glorfindel absent): this test uses only the `.client()` brick
(the raw SDK client), never `.detector()` / `.serve()` / `through_sdk()`, which pull in Glorfindel.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from annatar.collectors.azure_monitor import AzureMonitorCollector

from . import sdk_logs

AT = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _collector(answer):
    """The collector wired to a workspace whose socket is sdk_logs' in-memory adapter."""
    ws = sdk_logs.Workspace(answer)
    collector = AzureMonitorCollector({"log_analytics_workspace_id": "ws-made-up"}, client=ws.client())
    return collector, ws


def test_wait_for_heartbeat_reads_the_sdk_datetime_row():
    """A Heartbeat row — `max(TimeGenerated)`, a datetime the SDK hands back as a datetime — is a
    heartbeat: the collector returns the elapsed time, having sent its query through the SDK client."""
    answer = sdk_logs.constant(sdk_logs.body_of([{"LastHeartbeat": AT}], {"LastHeartbeat": "datetime"}))
    collector, ws = _collector(answer)
    elapsed = collector.wait_for_heartbeat("vm-made-up", timeout_s=0.3, interval_s=0.02)
    assert elapsed is not None
    assert ws.requests and "Heartbeat" in ws.requests[0]["query"]


def test_wait_for_heartbeat_times_out_when_no_row():
    """No row at all → no heartbeat → the poll times out (None)."""
    answer = sdk_logs.constant(sdk_logs.body_of([], {"LastHeartbeat": "datetime"}))
    collector, _ = _collector(answer)
    assert collector.wait_for_heartbeat("vm-made-up", timeout_s=0.3, interval_s=0.02) is None


def test_wait_for_heartbeat_rejects_a_null_last_heartbeat():
    """A row whose `LastHeartbeat` is null — `summarize` over no heartbeat — is not a heartbeat (the
    `is not None` guard): the poll times out (None), never takes the empty summary for a pulse."""
    answer = sdk_logs.constant(sdk_logs.body_of([{"LastHeartbeat": None}], {"LastHeartbeat": "datetime"}))
    collector, _ = _collector(answer)
    assert collector.wait_for_heartbeat("vm-made-up", timeout_s=0.3, interval_s=0.02) is None


def test_poll_alert_reads_the_sdk_rows():
    """A table with at least one row → the alert is detected, the elapsed time returned; the query
    was sent verbatim through the SDK client."""
    answer = sdk_logs.constant(sdk_logs.body_of([{"Count": 1}], {"Count": "long"}))
    collector, ws = _collector(answer)
    elapsed = collector.poll_alert("MyAlert | count", "azure_monitor", timeout_s=0.3, interval_s=0.02)
    assert elapsed is not None
    assert ws.requests and ws.requests[0]["query"] == "MyAlert | count"


def test_poll_alert_times_out_when_no_rows():
    """An empty table → no alert → the poll times out (None)."""
    answer = sdk_logs.constant(sdk_logs.body_of([], {"Count": "long"}))
    collector, _ = _collector(answer)
    assert collector.poll_alert("Q", "azure_monitor", timeout_s=0.3, interval_s=0.02) is None


def test_poll_alert_refuses_an_unknown_source():
    """A source other than azure_monitor is refused up front, before any query."""
    collector, _ = _collector(sdk_logs.constant(sdk_logs.body_of([])))
    with pytest.raises(ValueError, match="Unsupported detection source"):
        collector.poll_alert("Q", "sentinel", timeout_s=0.2, interval_s=0.02)
