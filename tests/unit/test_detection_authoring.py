"""Unit tests for the grounded detection-rule authoring engine.

No Azure, no real LLM (litellm.completion patched), no ~/.glorfindel writes.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from glorfindel import detection_authoring as da


# ── helpers ──────────────────────────────────────────────────────────────────────

def _fake_completion(args: dict):
    """Build a litellm-style response whose tool call carries `args`."""
    tool_call = SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(args)))
    message = SimpleNamespace(tool_calls=[tool_call])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _SchemaDetector:
    """Detector stub whose run_query answers a getschema query."""
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def run_query(self, query):
        self.queries.append(query)
        return self.rows


_VALID_ARGS = {
    "analysis": "Perf disk write counter, threshold calibrated to 50MB/s.",
    "rule_name": "ransomware-disk-write-v2",
    "proposed_query": "Perf | where CounterName == 'Disk Write Bytes/sec'",
    "interval_s": 30,
    "explanation": "Catches sustained disk writes from encryption.",
    "confidence": 0.82,
}


# ── catalog loading ────────────────────────────────────────────────────────────

def test_load_catalog_reads_real_file_and_merges_resource_type():
    cat = da.load_catalog()  # repo-root technique_catalog.yaml
    assert "T1486" in cat
    assert cat["T1486"]["resource_type"] == "azure_vm"
    assert cat["T1486"]["log_source"] == "Perf"


def test_catalog_entry_unknown_ttp_returns_none():
    assert da.catalog_entry("T9999") is None


def test_load_catalog_missing_file_returns_empty(tmp_path):
    assert da.load_catalog(tmp_path / "nope.yaml") == {}


# ── schema introspection ────────────────────────────────────────────────────────

def test_fetch_table_schema_parses_getschema_rows():
    det = _SchemaDetector([
        {"ColumnName": "TimeGenerated", "ColumnType": "datetime"},
        {"ColumnName": "MaxWrite", "ColumnType": "real"},
    ])
    schema = da.fetch_table_schema(det, "Perf")
    assert schema == [
        {"name": "TimeGenerated", "type": "datetime"},
        {"name": "MaxWrite", "type": "real"},
    ]
    assert "getschema" in det.queries[0]


def test_fetch_table_schema_none_detector_returns_empty():
    assert da.fetch_table_schema(None, "Perf") == []


def test_fetch_table_schema_rejects_injectionish_table_name():
    det = _SchemaDetector([{"ColumnName": "x", "ColumnType": "string"}])
    assert da.fetch_table_schema(det, "Perf | project foo") == []
    assert det.queries == []  # never ran a query


def test_fetch_table_schema_swallows_detector_errors():
    class Boom:
        def run_query(self, q):
            raise RuntimeError("workspace unreachable")
    assert da.fetch_table_schema(Boom(), "Perf") == []


def test_format_schema_block_empty_has_fallback():
    assert "unavailable" in da.format_schema_block([])


# ── user message grounding ──────────────────────────────────────────────────────

def test_build_user_message_includes_catalog_and_schema():
    msg = da.build_user_message(
        ttp="T1486",
        resource_id="/sub/rg/vm1",
        source="azure_monitor",
        workspace_id="ws-123",
        table_schema=[{"name": "MaxWrite", "type": "real"}],
        catalog={"log_source": "Perf", "indicator_columns": ["MaxWrite"],
                 "expected_latency_s": 90},
        failed_query="Perf | take 1",
        detection_timeout_s=300,
    )
    assert "T1486" in msg
    assert "Perf" in msg
    assert "MaxWrite: real" in msg          # schema block
    assert "indicator columns" in msg.lower()
    assert "90s" in msg                      # expected latency
    assert "Perf | take 1" in msg           # failed query


# ── author_rule (LLM mocked) ────────────────────────────────────────────────────

def test_author_rule_returns_proposal_without_schema_when_no_detector():
    with patch("litellm.completion", return_value=_fake_completion(_VALID_ARGS)):
        out = da.author_rule(
            ttp="T1486", resource_id="/sub/rg/vm1", source="azure_monitor",
            workspace_id="ws", model="claude-test",
        )
    assert out["rule_name"] == "ransomware-disk-write-v2"
    assert out["confidence"] == pytest.approx(0.82)
    assert out["source"] == "azure_monitor"
    assert out["grounded_schema"] is False


def test_author_rule_grounds_on_schema_when_detector_present():
    det = _SchemaDetector([{"ColumnName": "MaxWrite", "ColumnType": "real"}])
    with patch("litellm.completion", return_value=_fake_completion(_VALID_ARGS)) as m:
        out = da.author_rule(
            ttp="T1486", resource_id="/sub/rg/vm1", source="azure_monitor",
            workspace_id="ws", model="claude-test", detector=det,
        )
    assert out["grounded_schema"] is True
    # the real table schema reached the prompt
    sent = m.call_args.kwargs["messages"][1]["content"]
    assert "MaxWrite: real" in sent


# SEC-A4b: the routing key asked of the model that proposes rules — the bullet, to the byte.
_ROUTING_KEY_BOUND = (
    "This never applies to AzureActivity nor to an Entra ID table (AuditLogs, SigninLogs and the other "
    "sign-in logs): keep their grouping as it is, and never add `_ResourceId` to a `by` that groups by "
    "caller, identity or address.\n")
_ROUTING_KEY_BULLET = (
    "- On a data-plane table, one a VM or a storage service writes (Perf, Syslog, the storage logs…), "
    "Glorfindel routes each row to its VM by a key, never by `Computer` (the VM writes its own host "
    "name): a rule whose rows lose the key is refused. Keep the key in the query's output exactly as "
    "the table holds it: name it in the last `project` and in the `by` of every `summarize`, and never "
    "write, rename or recompute it (`extend`, `project <key> = …`, `project-rename`). The key is "
    "`_ResourceId`, a standard column of every Log Analytics table, even when the table schema "
    "provided does not list it; on a storage table (StorageBlobLogs…), it is `CallerIpAddress` as the "
    "service wrote it — the address that made the call names the VM, while `_ResourceId` names the "
    "storage account there: do not add it to a `by`. " + _ROUTING_KEY_BOUND)
# The prompt without the bullet: origin/main's before SEC-A4b, to the byte (the harness's
# `before`, scripts/llm_smoke.py --proposals).
_PROMPT_BEFORE_SHA256 = "0d28780f90580b64f9e9ae606dce86483ab9fb217be2b658c2533a5a108e9fc3"


def test_the_proposal_prompt_asks_to_keep_the_routing_key_to_the_byte():
    import hashlib
    assert da.ROUTING_KEY_INSTRUCTION == _ROUTING_KEY_BULLET
    prompt = da.RULE_PROPOSAL_SYSTEM_PROMPT
    assert prompt.count(_ROUTING_KEY_BULLET) == 1
    # One bullet of the grounding rules, the last; nothing else of the prompt changed.
    assert ("- If a prior query was close, fix only what was wrong; do not over-engineer.\n"
            + _ROUTING_KEY_BULLET + "\nYou always call the propose_detection_rule tool") in prompt
    before = prompt.replace(_ROUTING_KEY_BULLET, "", 1)
    assert hashlib.sha256(before.encode()).hexdigest() == _PROMPT_BEFORE_SHA256


def test_the_bullet_is_bounded_to_the_data_plane_where_the_refusal_applies():
    """The control plane and identities keep their grouping: a threshold per caller made one per
    resource would let an attack spread over several resources pass under it. The bullet names
    the data plane as the routing refusal reads it, and excludes the others in so many words."""
    from eregion_core.rule_routing import data_plane
    bullet = da.ROUTING_KEY_INSTRUCTION
    assert bullet.startswith("- On a data-plane table,") and bullet.endswith(_ROUTING_KEY_BOUND)
    for table in ("Perf", "Syslog", "StorageBlobLogs"):          # named as data plane
        assert table in bullet and data_plane("azure_monitor", f"{table} | take 1")
    for table in ("AzureActivity", "AuditLogs", "SigninLogs"):   # named as excluded
        assert table in _ROUTING_KEY_BOUND and not data_plane("azure_monitor", f"{table} | take 1")
    # Never asked to add `_ResourceId` where the key is the caller's address (the storage tables,
    # `data-exfiltration-blob`: `by CallerIpAddress, AccountName`).
    assert "`_ResourceId` names the storage account there: do not add it to a `by`" in bullet
    assert "In KQL on a Log Analytics table" not in bullet


def test_the_bullet_reaches_the_model_that_proposes_rules():
    with patch("litellm.completion", return_value=_fake_completion(_VALID_ARGS)) as m:
        da.author_rule(ttp="T1486", resource_id="/sub/rg/vm1", source="azure_monitor",
                       workspace_id="ws", model="claude-test")
    system = m.call_args.kwargs["messages"][0]["content"][0]["text"]
    assert _ROUTING_KEY_BULLET in system


def test_author_rule_raises_on_no_tool_call():
    bad = SimpleNamespace(choices=[SimpleNamespace(
        message=SimpleNamespace(tool_calls=None))])
    with patch("litellm.completion", return_value=bad):
        with pytest.raises(ValueError):
            da.author_rule(
                ttp="T1486", resource_id="r", source="azure_monitor",
                workspace_id="ws", model="claude-test",
            )


# ── cold-start selection ─────────────────────────────────────────────────────────

_CATALOG = {
    "T1486": {"ttp": "T1486", "status": "implemented"},
    "T1041": {"ttp": "T1041", "status": "implemented"},
    "T1530": {"ttp": "T1530", "status": "planned"},
}


def test_techniques_needing_rules_skips_covered_and_planned():
    todo = da.techniques_needing_rules(_CATALOG, existing_ttps={"T1486"})
    ttps = {e["ttp"] for e in todo}
    assert ttps == {"T1041"}  # T1486 covered, T1530 planned (excluded by default)


def test_techniques_needing_rules_include_planned():
    todo = da.techniques_needing_rules(
        _CATALOG, existing_ttps=set(), include_planned=True)
    assert {e["ttp"] for e in todo} == {"T1486", "T1041", "T1530"}


def test_techniques_needing_rules_only_ttps_filter():
    todo = da.techniques_needing_rules(
        _CATALOG, existing_ttps=set(), only_ttps={"T1041"})
    assert {e["ttp"] for e in todo} == {"T1041"}


def test_propose_rules_cli_dry_run_authors_without_recording(tmp_path, monkeypatch):
    """propose-rules --dry-run authors via the (mocked) LLM and records nothing."""
    from click.testing import CliRunner
    from glorfindel.cli import cli
    from glorfindel import proposed_rules as _pr

    # Isolate the proposals store so the test never touches ~/.glorfindel.
    monkeypatch.setattr(_pr, "_STORE", tmp_path / "proposed_rules.jsonl")

    # T1530 is a 'planned' catalog technique with no detection rule → deterministic
    # target regardless of the local detection_rules.yaml (which covers the 5 implemented).
    # Stub getschema so the test makes zero Azure calls (dry-run now runs read-only
    # introspection — see the command). litellm is mocked too.
    with patch("litellm.completion", return_value=_fake_completion(_VALID_ARGS)), \
         patch("glorfindel.detection_authoring.fetch_table_schema", return_value=[]):
        result = CliRunner().invoke(
            cli, ["propose-rules", "--ttp", "T1530",
                  "--include-planned", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "T1530" in result.output
    assert _pr.pending() == []  # dry-run records nothing
