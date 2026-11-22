"""DOS2 (#1042; `docs/design/dossier-isolation.md` §3.7, F6): the decision noted on the cycle's debug line.

The line gains `decision_model`, `decision_sampling`, `confirming_sampling`, `confidence_threshold`,
`decision_draws_required`, `glorfindel_version` and `rule_fingerprint` (`glorfindel/cycle_line.py`) — one
test a field, a model that refuses the temperature among them. And nothing the model sees changes: the
`cycle` the memory keeps (it feeds `past_cycles`) and the message to the model are frozen to the byte, at
their value on origin/main before the lot (d543ec49). Mutants M6977–M6979 (`scripts/mutants/DOS2.py`).

The cycles go through the real graph (G2's set-up: a recording connector in place of Azure, the model
patched, `human_only`: nothing acts), and no call reaches Azure nor a model.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from eregion_core import llm_call
from glorfindel import agent, cycle_line, detection_rules, rule_ceiling
from glorfindel.config import AutonomyConfig
from glorfindel.detection_rules import shipped_rules_path
from tests.unit.test_dependency_failures import FakeMemory, LogAnalytics, Recorder, _agent, _debug, _ransomware

MODEL = "anthropic/claude-test"
RULE = "ransomware-disk-write"
REFUSAL = ('litellm.BadRequestError: AnthropicException - {"type":"error","error":{"type":'
           '"invalid_request_error","message":"`temperature` is deprecated for this model."}}')
NEW_FIELDS = ("decision_model", "decision_sampling", "confirming_sampling", "confidence_threshold",
              "decision_draws_required", "glorfindel_version", "rule_fingerprint")


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    for var in ("GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "GLORFINDEL_LLM_BASE_URL",
                "GLORFINDEL_CONFIDENCE_THRESHOLD", "GLORFINDEL_LLM_TIMEOUT_S", "GLORFINDEL_READ_ONLY",
                "GLORFINDEL_DECISION_DRAWS", "EREGION_REF", "EREGION_REVISION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_call, "_AUTO_TOOL_CHOICE", set())
    monkeypatch.setattr(llm_call, "_NO_TEMPERATURE", set())
    monkeypatch.setattr(agent, "CycleMemory", FakeMemory)
    from eregion_core import version
    monkeypatch.setattr(version, "_version_cache", {})
    monkeypatch.setattr(version, "checkout_revision", lambda: "")
    from glorfindel.actions import AzureConnector

    def no_azure(*_a, **_k):
        raise AssertionError("no Azure in tests (DOS2)")
    monkeypatch.setattr(AzureConnector, "_ensure_clients", no_azure)


def _llm(action: str = "isolate_vm", confidence: float = 0.8) -> MagicMock:
    call = MagicMock()
    call.function.arguments = json.dumps({
        "reasoning": f"Écritures disque soutenues — {action}.", "confidence": confidence, "action": action,
        "reversible": True, "explanation": "Écritures disque soutenues, chiffrement possible.",
        "escalate": False, "escalation_reason": "", "suggested_steps": []})
    resp = MagicMock()
    resp.choices[0].message.tool_calls = [call]
    resp.usage = None
    return resp


def _cycle(*, refuse: bool = False, fail: bool = False, mode: str = "human_only", signal=None):
    """One cycle through the real graph; returns (the final state, the debug line, the agent)."""
    seen: list[dict] = []

    def completion(**kw):
        seen.append(kw)
        if fail:
            raise RuntimeError("provider unreachable")
        if refuse and "temperature" in kw:
            raise RuntimeError(REFUSAL)
        return _llm()
    agent_ = _agent(Recorder(), autonomy=AutonomyConfig(default=mode))
    agent_.model = MODEL
    with patch("litellm.completion", side_effect=completion), \
            patch("glorfindel.detectors.detector_for", return_value=LogAnalytics(fail=False)):
        final = agent_.respond(signal or _ransomware())
    _cycle.calls = seen
    return final, _debug()[-1], agent_


def _shipped_query(name: str = RULE) -> str:
    data = yaml.safe_load(shipped_rules_path().read_text())
    return next(r["query"] for r in data["rules"] if r["name"] == name)


# ── Les sept champs ─────────────────────────────────────────────────────────────────────────────

def test_the_model_called_is_on_the_line():
    """M6977: the model the decision was asked of, its string as LiteLLM got it."""
    _, line, _ = _cycle()
    assert [c["model"] for c in _cycle.calls] == [MODEL]
    assert line["decision_model"] == MODEL


def test_a_failed_call_still_names_the_model_it_asked():
    """A decision that could not be obtained (cycle_failed): the model asked is said all the same."""
    final, line, _ = _cycle(fail=True)
    assert final["cycle_error"].startswith("decide:")
    assert line["decision_model"] == MODEL
    assert line["decision_sampling"] == {"requested_temperature": 0.0, "refused": False, "sampling": "fixed"}


def test_a_model_that_accepts_the_temperature_draws_fixed():
    _, line, _ = _cycle()
    assert [c.get("temperature") for c in _cycle.calls] == [0.0]
    assert line["decision_temperature"] == 0.0
    assert line["decision_sampling"] == {"requested_temperature": 0.0, "refused": False, "sampling": "fixed"}


def test_a_model_that_refuses_the_temperature_says_the_provider_s_default():
    """claude-sonnet-5-5, the default (26/10): 0 asked, refused, the provider's default sampling drew —
    said in clear, never a bare null."""
    _, line, _ = _cycle(refuse=True)
    assert [("temperature" in c) for c in _cycle.calls] == [True, False]
    assert line["decision_temperature"] is None
    assert line["decision_sampling"] == {"requested_temperature": 0.0, "refused": True,
                                         "sampling": "provider_default"}


def test_a_failed_call_on_a_model_that_refused_says_it_refused(monkeypatch):
    monkeypatch.setattr(llm_call, "_NO_TEMPERATURE", {MODEL})
    _, line, _ = _cycle(fail=True)
    assert "decision_temperature" not in line
    assert line["decision_sampling"]["refused"] is True and line["decision_sampling"]["sampling"] == "provider_default"


def test_the_confirming_draws_are_said_at_the_provider_s_default():
    """The confirming draws (D-1) ask no temperature: the line says so, whether one was asked or not."""
    _, line, _ = _cycle()
    assert line["confirming_sampling"] == {"requested_temperature": None, "refused": False,
                                           "sampling": "provider_default"}


@pytest.mark.parametrize("raw, said", [("", 0.7), ("0.85", 0.85), ("O.95", None), ("nan", None)])
def test_the_confidence_threshold_in_force(monkeypatch, raw, said):
    """The gate's threshold as it stands; malformed — every autonomous action held — null, never an
    Infinity a JSON reader refuses."""
    monkeypatch.setenv("GLORFINDEL_CONFIDENCE_THRESHOLD", raw)
    _, line, _ = _cycle()
    assert line["confidence_threshold"] == said
    json.loads(json.dumps(line, allow_nan=False))


@pytest.mark.parametrize("raw, said", [("", 3), ("5", 5), ("1", 0), ("three", 0)])
def test_the_draws_required_in_force(monkeypatch, raw, said):
    monkeypatch.setenv("GLORFINDEL_DECISION_DRAWS", raw)
    _, line, _ = _cycle()
    assert line["decision_draws_required"] == said


def test_the_version_of_glorfindel_that_decided(monkeypatch):
    """M6978: the reference Imladris deployed, its commit, the package's version."""
    from importlib.metadata import version as pkg_version
    monkeypatch.setenv("EREGION_REF", "v0.6.4")
    monkeypatch.setenv("EREGION_REVISION", "79f220f2c1d0e9a8b7c6d5e4f3a2b1c0d9e8f7a6")
    _, line, _ = _cycle()
    assert line["glorfindel_version"] == {"ref": "v0.6.4", "revision": "79f220f2c1d0e9a8b7c6d5e4f3a2b1c0d9e8f7a6",
                                          "package": pkg_version("eregion")}


def test_a_local_watch_says_its_checkout(monkeypatch):
    from eregion_core import version
    monkeypatch.setattr(version, "checkout_revision", lambda: "a" * 40)
    _, line, _ = _cycle()
    assert line["glorfindel_version"]["ref"] == "" and line["glorfindel_version"]["revision"] == "a" * 40


def test_the_rule_that_fired_and_the_fingerprint_of_its_query():
    _, line, _ = _cycle()
    sha = hashlib.sha256(_shipped_query().encode("utf-8")).hexdigest()
    assert line["rule_fingerprint"] == {"name": RULE, "query_sha256": sha[:8]}


def test_a_client_rule_that_changed_the_query_has_another_fingerprint():
    """The rule changes from one version or one layer to the next: the line says which one fired."""
    query = _shipped_query() + "\n| where MaxWrite > 1"
    detection_rules.client_rules_path().parent.mkdir(parents=True, exist_ok=True)
    detection_rules.client_rules_path().write_text(yaml.safe_dump({"rules": [
        {"name": RULE, "source": "azure_monitor", "ttp": "T1486", "query": query}]}))
    _, line, _ = _cycle()
    assert line["rule_fingerprint"] == {"name": RULE,
                                        "query_sha256": hashlib.sha256(query.encode()).hexdigest()[:8]}


def test_an_attack_started_names_the_rule_of_its_ttp():
    """A detection the graph resolved names no rule: the rule the ceiling reads for it (its TTP)."""
    signal = {**_ransomware(), "context": {"run_id": "watch-ransomware-disk-write-20261021T100000Z"}}
    fields = cycle_line.decision_fields({"signal": signal})
    assert fields["rule_fingerprint"]["name"] == rule_ceiling.current().for_signal(signal)[0] != ""
    assert len(fields["rule_fingerprint"]["query_sha256"]) == 8


def test_rules_that_cannot_be_read_never_cost_the_line(monkeypatch):
    def unreadable():
        raise OSError("detection_rules.yaml: permission denied")
    monkeypatch.setattr(rule_ceiling, "current", unreadable)
    _, line, _ = _cycle()
    assert line["rule_fingerprint"] == {"name": RULE, "query_sha256": "",
                                        "unreadable": "detection_rules.yaml: permission denied"}
    assert line["decision_model"] == MODEL


def test_a_cycle_the_model_never_saw_names_no_model():
    """A decision the code builds (the control plane, an identity): no model, no sampling — the
    settings, the version and the rule all the same."""
    fields = cycle_line.decision_fields({"signal": _ransomware(), "action": "", "escalate": True})
    assert not {"decision_model", "decision_sampling", "confirming_sampling"} & set(fields)
    assert {"confidence_threshold", "decision_draws_required", "glorfindel_version", "rule_fingerprint"} <= set(fields)


# ── Rien de ce que voit le modèle ne change ──────────────────────────────────────────────────────

VM = "/subscriptions/s/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-dos2"
PAST = [{"summary": "T1486 vm-dos2 snapshot 0.70", "source": "real"}]


def _bree() -> dict:
    return {"signal_id": "rule-ransomware-disk-write-0000dos2", "event": "detection", "ttp": "T1486",
            "severity": "high", "resource_id": VM, "resource_type": "vm",
            "timestamp": "2026-11-10T02:14:00+00:00",
            "context": {"workspace_id": "ws-dos2", "rule_name": RULE,
                        "run_id": "watch-ransomware-disk-write-20261110T021400Z", "attribution": "asset"},
            "raw_signal": {"first_result_row": {"Computer": "vm-dos2", "_ResourceId": VM, "MaxWrite": 74300000},
                           "investigative_context": {"top_write_processes": [], "backup_agent_check": []}}}


# The message to the model and its tool (the system prompt included), and the user message alone, as
# origin/main rendered them before DOS2 (d543ec49).
MESSAGE_SHA256 = "7c1a6454c2ace7d8a8563d20214b3c605c6661b7a9dee6924a9be915cbd98930"
USER_SHA256 = "edaa864d69082d35922b660c4e6dc2bc7dc3cc3b6550136b703911633bc4ab45"
# The memory's cycle of that decision, as origin/main wrote it — the state carrying every field DOS2
# reads, none of which may reach it.
CYCLE = ('{"signal_id": "rule-ransomware-disk-write-0000dos2", "run_id": "watch-ransomware-disk-write-'
         '20261110T021400Z", "ttp": "T1486", "severity": "high", "resource_type": "vm", "event": "detection", '
         '"reasoning": "Écritures soutenues.", "confidence": 0.8, "action": "snapshot", "escalate": false, '
         '"escalation_reason": "", "outcome": "{\'executed\': True, \'status\': \'dry_run\', \'action_s\': 1.5}", '
         '"detection_s": 0, "action_s": 1.5, "past_cycles_used": ["T1486 vm-dos2 snapshot 0.70"], '
         '"resolved_autonomy_mode": "human_only", "autonomy_gate": {}, "source": "real", "exercise_run": "", '
         '"resource_id": "/subscriptions/s/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/'
         'vm-dos2", "rule_name": "ransomware-disk-write", "corroborated": false}')


def test_the_message_to_the_model_is_unchanged_to_the_byte():
    seen: list[dict] = []

    def completion(**kw):
        seen.append(kw)
        return _llm("snapshot")
    state = {"signal": _bree(), "past_cycles": PAST, "incident": None, "dry_run": True, "telemetry_gaps": []}
    with patch("litellm.completion", side_effect=completion):
        out = agent.decide(state, model=MODEL, autonomy=AutonomyConfig(default="human_only"))
    blob = json.dumps({"messages": seen[0]["messages"], "tools": seen[0]["tools"]}, sort_keys=True,
                      ensure_ascii=False)
    assert hashlib.sha256(blob.encode()).hexdigest() == MESSAGE_SHA256
    assert hashlib.sha256(agent._build_user_message(_bree(), PAST).encode()).hexdigest() == USER_SHA256
    assert out["decision_model"] == MODEL and not any(f in json.dumps(out["signal"]) for f in NEW_FIELDS)


def test_the_memory_s_cycle_is_unchanged_to_the_byte():
    """M6979: a field of the line leaking into the memory — it would reach the model by past_cycles."""
    mem = FakeMemory()
    state = {"signal": _bree(), "past_cycles": PAST, "incident": None, "dry_run": True, "telemetry_gaps": [],
             "reasoning": "Écritures soutenues.", "confidence": 0.8, "action": "snapshot", "escalate": False,
             "escalation_reason": "", "outcome": {"executed": True, "status": "dry_run", "action_s": 1.5},
             "autonomy_mode": "human_only", "autonomy_gate": {}, "decision_temperature": None,
             "decision_draws": [], "decision_model": "anthropic/claude-sonnet-5-5"}
    agent.store_cycle(state, memory=mem)
    assert json.dumps(mem.stored[0], ensure_ascii=False) == CYCLE
    line = json.loads((Path("runs") / "glorfindel" /
                       "watch-ransomware-disk-write-20261110T021400Z_debug.jsonl").read_text().splitlines()[-1])
    assert set(NEW_FIELDS) <= set(line)


def test_a_whole_cycle_keeps_the_new_fields_out_of_the_memory_and_the_signal():
    final, line, agent_ = _cycle()
    [stored] = agent_.memory.stored
    assert not set(NEW_FIELDS) & set(stored)
    assert set(stored) == set(json.loads(CYCLE))
    assert not set(NEW_FIELDS) & set(final["signal"]) and not set(NEW_FIELDS) & set(final["signal"]["context"])
    assert set(NEW_FIELDS) <= set(line)


def test_the_console_reads_the_version_from_the_shared_core():
    """D1: the version moved from the console to eregion_core; the console imports it from there."""
    from eregion_console import sections
    from eregion_core import version
    assert sections.version is version.version
    import ast
    tree = ast.parse(open(version.__file__, encoding="utf-8").read())
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
               {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not {m for m in imported if m.split(".")[0] in ("eregion_console", "glorfindel", "annatar", "gothmog")}
