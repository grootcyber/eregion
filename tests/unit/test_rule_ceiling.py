"""RDW1 (#994; Jonathan, 20/11): a rule carries the ceiling of what it may make Glorfindel propose —
`ransomware-disk-write`, on the write rate alone, at most a snapshot and a card.

The bench of 20/11 (G1, v0.6.3): Gothmog's benign fault `vm-disk-write`, a backup's sustained writes
(about 74 MB/s for 10 min), fired `ransomware-disk-write` and made two cards; the model proposed
`isolate_vm` at 80 %, above the threshold of 0.7. Only `human_only` held it: under `non_disruptive`
(or `full_auto`), gondolin would have been isolated. The rate does not tell a backup from an
encryption. Now the shipped rule carries `ceiling: {allow: [snapshot]}`, and a guard of `decide` —
after the gates that judge the model's own choice (the confidence, the signal, the telemetry, the
release), before never_block, the attribution and the mode — brings an autonomous action the rule does
not allow back to the snapshot: the model's proposal and its confidence kept on the card, the reason
said. The snapshot goes as the mode allows; the ceiling's own card (`ceiling_proposal`) proposes the
model's isolation, approvable in one click, never run alone, whatever the mode (Jonathan, 20/11: the
floor's model), never on a detection that names no VM. The memory keeps the model's proposal. A rule
without a ceiling behaves as before; the
client's layer lowers a ceiling, never raises it; a fact of the detection the rule names (`lifted_by`)
lifts it — none in this lot, the corroboration comes in a lot of its own. Nothing of the prompt
changes: the ceiling never enters the signal.

The rows of `vm-disk-write` here are invented, of the shape of the card of 20/11 (Computer,
_ResourceId, MaxWrite), and go through the real shipped rule, the real RulePoller and the production
graph — the model patched (isolate_vm at 80 %), Azure a recorder. No Azure call, no model call, a
throwaway store and HOME (tests/unit/conftest.py). Mutants M6833–M6847 (scripts/mutants/RDW1.py).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from glorfindel import agent, detection_rules, escalations, rule_ceiling
from glorfindel.config import AutonomyConfig
from glorfindel.detection_rules import RulePoller, base_rule_sha256, load_config, shipped_query, shipped_rules_path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "eregion_console/static/glorfindel.js"
RULE = "ransomware-disk-write"
VM = "/subscriptions/s/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-g1"
OTHER = "/subscriptions/s/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-g2"
MB = 1_000_000
# The shipped query before RDW1 (origin/main, 7c8313a7): the lot adds a key, never changes the query.
QUERY_SHA256 = "95c5b4d0d4ce20317d095fd41c54ff269302cd3f14d6466fe0e716cdd36ecbf0"


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    for var in ("GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN", "GLORFINDEL_LLM_BASE_URL",
                "GLORFINDEL_CONFIDENCE_THRESHOLD", "GLORFINDEL_LLM_TIMEOUT_S", "GLORFINDEL_READ_ONLY",
                "GLORFINDEL_DECISION_DRAWS", "GLORFINDEL_WARROOM_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    from eregion_core import llm_call
    monkeypatch.setattr(llm_call, "_AUTO_TOOL_CHOICE", set())
    monkeypatch.setattr(llm_call, "_NO_TEMPERATURE", set())
    monkeypatch.setattr(escalations, "notify_action", lambda **kw: None)
    from glorfindel.actions import AzureConnector

    def no_azure(*_a, **_k):
        raise AssertionError("no Azure in tests (RDW1)")
    monkeypatch.setattr(AzureConnector, "_ensure_clients", no_azure)


def _llm(action: str = "isolate_vm", confidence: float = 0.8) -> MagicMock:
    """The model, patched: it proposes `action` at `confidence` (20/11: isolate_vm at 80 %)."""
    call = MagicMock()
    call.function.arguments = json.dumps({
        "reasoning": f"Sustained disk writes — {action}.", "confidence": confidence, "action": action,
        "reversible": True, "explanation": "Écritures disque soutenues, chiffrement possible.",
        "escalate": False, "escalation_reason": "", "suggested_steps": []})
    resp = MagicMock()
    resp.choices[0].message.tool_calls = [call]
    resp.usage = None
    return resp


def _cfg():
    return SimpleNamespace(monitoring_backends=[SimpleNamespace(
        name="law-bench", type="azure_monitor", workspace_id="ws-rdw1", endpoint="")])


def _shipped(name: str = RULE, client_layer=False):
    return next(r for r in load_config(shipped_rules_path(), glorfindel_cfg=_cfg(),
                                       client_layer=client_layer).rules if r.name == name)


class _Det:
    def __init__(self, rows):
        self.rows = list(rows)

    def run_query(self, query, timespan=None):
        return list(self.rows)


class _Registry:
    def __init__(self, *rids):
        self.assets = [SimpleNamespace(name=r.rsplit("/", 1)[-1], resource_id=r) for r in rids]

    def for_backend(self, _name):
        return self.assets


def _disk_row(rate_bps: int, rid: str = VM) -> dict:
    """A row of the shipped rule, as the RulePoller reads it (the card of 20/11's shape)."""
    return {"Computer": rid.rsplit("/", 1)[-1], "_ResourceId": rid, "MaxWrite": rate_bps}


def _detections(*rows) -> list[dict]:
    """The shipped rule, through the real RulePoller, on `rows` — the signals it sends."""
    rule = _shipped()
    sent: list[dict] = []
    p = RulePoller([rule], sent.append)
    p._detector = lambda _rule: _Det(rows)
    p._registry = _Registry(VM, OTHER)
    p.poll_once(rule)
    return sent


@pytest.fixture
def watch():
    """The watch's process: its key signs the proposals of the cards it writes (the signed queue)."""
    from eregion_core import watch_key
    signer = watch_key.Signer(bytes(range(32)))
    escalations.sign_proposals(lambda: signer)
    return signer


@pytest.fixture
def graph(monkeypatch):
    """The production agent on a recording connector (tests/unit/test_dependency_failures.py)."""
    from glorfindel import jobs

    from .test_dependency_failures import FakeMemory, LogAnalytics, Recorder, _agent
    monkeypatch.setattr(agent, "CycleMemory", FakeMemory)
    monkeypatch.setattr(agent, "_backup_vault_target", lambda: ("rsv-rdw1", "rg"))
    monkeypatch.setattr(jobs, "record_snapshot_job", lambda *a, **kw: None)

    def run(signal, mode, resp=None):
        conn = Recorder()
        agent_ = _agent(conn, autonomy=AutonomyConfig(default=mode))
        with patch("litellm.completion", return_value=resp or _llm()), \
                patch("glorfindel.detectors.detector_for", return_value=LogAnalytics(fail=False)):
            final = agent_.respond(signal)
        run.memory = agent_.memory
        return final, conn
    return run


def _of(kind: str) -> list[dict]:
    return [c for c in escalations.pending() if c["escalation_type"] == kind]


def _one_click(card: dict) -> None:
    """Approvable in one click, as the floor's card: the server, the signed queue, the page."""
    from eregion_core.action_queue import APPROVABLE_TYPES, proposed_verbs
    from glorfindel.approval import approval_refusal
    assert card["escalation_type"] in APPROVABLE_TYPES
    assert approval_refusal(card, "vm-g1") is None
    assert proposed_verbs(card) == frozenset({"isolate_vm"})
    page = re.search(r"const _HELD_TYPES = new Set\(\[([^\]]*)\]\);", JS.read_text())
    assert page and "'ceiling_proposal'" in page.group(1)


def _decide(signal: dict, resp=None, mode: str = "non_disruptive") -> dict:
    state = {"signal": signal, "past_cycles": [], "incident": None, "dry_run": True, "telemetry_gaps": []}
    with patch("litellm.completion", return_value=resp or _llm()):
        return agent.decide(state, model="anthropic/claude-test", autonomy=AutonomyConfig(default=mode))


def _signal(rule: str = RULE, ttp: str = "T1486", row: dict | None = None, **context) -> dict:
    ctx = {"workspace_id": "ws-rdw1", "rule_name": rule, "attribution": "asset",
           "run_id": f"watch-{rule}-20261120T171400Z", **context}
    return {"signal_id": f"rule-{rule}-0000rdw1", "event": "detection", "ttp": ttp, "severity": "high",
            "resource_id": VM, "resource_type": "vm", "timestamp": "2026-11-20T17:14:00+00:00",
            "context": {k: v for k, v in ctx.items() if v is not None},
            "raw_signal": {"first_result_row": row or _disk_row(74 * MB)}}


def _client_layer(*rules: dict) -> None:
    detection_rules.client_rules_path().parent.mkdir(parents=True, exist_ok=True)
    detection_rules.client_rules_path().write_text(yaml.safe_dump({"rules": list(rules)}))


def _shipped_entry(name: str = RULE) -> dict:
    data = yaml.safe_load(shipped_rules_path().read_text())
    return next(dict(r) for r in data["rules"] if r["name"] == name)


# ── Fini quand : les lignes de vm-disk-write ne font plus sortir d'isolement, et la carte le dit ─────

@pytest.mark.parametrize("mode", ["non_disruptive", "full_auto"])
def test_the_vm_disk_write_rows_make_no_isolation_and_the_card_says_so(graph, watch, mode):
    """The bench of 20/11, through the RulePoller and the graph: the model proposes isolate_vm at 80 %;
    no isolation leaves the rule — the snapshot runs (the mode allows it), and one card, the ceiling's,
    says the rule's ceiling, the model's proposal and its confidence, and proposes the isolation to a
    human, approvable in one click."""
    signals = _detections(_disk_row(74_300_000))
    assert len(signals) == 1 and signals[0]["context"]["rule_name"] == RULE
    final, conn = graph(signals[0], mode)
    assert "isolate_vm" not in conn.calls and "snapshot" in conn.calls
    assert final["action"] == "snapshot" and final["escalate"] is False
    assert final["ceiling"]["proposed"] == "isolate_vm" and final["ceiling"]["confidence"] == 0.8
    [card] = escalations.pending()                                  # no card of V-11 beside it
    assert (card["escalation_type"], card["action"]) == ("ceiling_proposal", "isolate_vm")
    assert card["ceiling"] == {"rule": RULE, "proposed": "isolate_vm", "confidence": 0.8, "lowered": "snapshot",
                               "allow": ["snapshot"], "why": card["ceiling"]["why"]}
    assert "débit" in card["ceiling"]["why"] and card["confidence"] == 0.8
    reason = card["reason"]
    assert reason.startswith(f"Plafond de la règle « {RULE} »") and "ne prouve qu'un débit" in reason
    assert "'isolate_vm' (confiance 80%)" in reason and "ramené à 'snapshot'" in reason
    assert "proposé sur la carte du plafond, approuvable en un clic" in reason
    assert "Instantané pris : snap-1." in reason
    _one_click(card)


def test_in_human_only_the_snapshot_is_held_and_the_isolation_proposed_beside_it(graph, watch):
    """human_only (the bench of 20/11): the mode holds what the rule allows — the snapshot, approvable
    in one click —; beside it, the ceiling's card proposes the model's isolation, approvable too.
    Nothing runs."""
    [signal] = _detections(_disk_row(74_300_000))
    final, conn = graph(signal, "human_only")
    assert conn.writes() == [] and "isolate_vm" not in conn.calls
    assert final["action"] == "snapshot" and final["mode_hold"] is True
    [held] = _of("mode_hold")
    assert held["action"] == "snapshot" and held["ceiling"]["proposed"] == "isolate_vm"
    assert held["reason"].startswith(f"Plafond de la règle « {RULE} »")
    # The mode judges the snapshot, never the action brought back (the guard before the mode).
    assert "Mode human_only — action 'snapshot' recommandée" in held["reason"]
    assert "action 'isolate_vm' recommandée" not in held["reason"]
    [card] = _of("ceiling_proposal")
    assert card["action"] == "isolate_vm" and "Instantané pris" not in card["reason"]
    _one_click(card)
    assert len(escalations.pending()) == 2


def test_the_human_isolates_from_the_card_in_one_gesture(graph, watch, monkeypatch):
    """« The human isolates from the card in one gesture » (Jonathan, 20/11): « Approve & execute » on
    the ceiling's card runs the isolation — the console's route, the approval's usual guards."""
    from .console_client import console
    [signal] = _detections(_disk_row(74_300_000))
    graph(signal, "non_disruptive")
    [card] = _of("ceiling_proposal")
    conn = MagicMock()
    conn.isolate_vm.return_value = {"status": "isolated", "drain": {"status": "drained"}}
    conn.verify_isolation.return_value = {"verified": True, "method": "nsg_check"}
    monkeypatch.setattr("glorfindel.actions.AzureConnector", lambda **k: conn)
    r = console().post(f"/api/action/approve/{card['id']}", json={}).json()
    assert r.get("ok") is True and r["action"] == "isolate_vm", r
    conn.isolate_vm.assert_called_once_with(VM)
    assert not _of("ceiling_proposal")                                   # resolved by the approval


def test_the_memory_keeps_the_model_s_proposal(graph):
    """Decision B (Jonathan, 20/11): the cycle stored for the retrieval keeps the model's own
    proposal — what the model reads again does not change; the action brought back stays in the
    outcome, the ceiling's note and the debug line."""
    [signal] = _detections(_disk_row(74_300_000))
    final, _ = graph(signal, "non_disruptive")
    [cycle] = graph.memory.stored
    assert cycle["action"] == "isolate_vm" and final["action"] == "snapshot"
    assert "snapshot" in cycle["outcome"]
    [line] = (Path("runs") / "glorfindel" / f"{signal['context']['run_id']}_debug.jsonl").read_text().splitlines()
    debug = json.loads(line)
    assert debug["action"] == "snapshot" and debug["ceiling"]["proposed"] == "isolate_vm"


def test_an_unattributed_detection_has_no_ceiling_card(graph):
    """ATT1, SEC-Ed prime: a detection that names no VM proposes no isolation approvable."""
    sig = _signal(attribution="unattributed", candidates=["vm-g1", "vm-g2"])
    final, conn = graph(sig, "non_disruptive", _llm("isolate_vm", 0.95))
    assert conn.writes() == [] and not _of("ceiling_proposal")
    assert [c["escalation_type"] for c in escalations.pending()] == ["unattributed_signal"]


def test_a_gate_that_held_before_is_said_on_the_ceiling_s_card(graph, watch):
    """Under the threshold: the confidence's card holds the snapshot; the ceiling's card proposes the
    isolation and says the hold before it."""
    [signal] = _detections(_disk_row(74_300_000))
    graph(signal, "non_disruptive", _llm("isolate_vm", 0.5))
    [held] = _of("low_confidence")
    assert held["action"] == "snapshot"
    [card] = _of("ceiling_proposal")
    assert card["action"] == "isolate_vm" and "Low confidence (50%)" in card["reason"]


def test_the_floor_comes_first_and_names_the_model_s_proposal():
    """B3a and the ceiling on one VM: the floor's card, its reason first, naming the model's own
    proposal (never the snapshot the ceiling left); the ceiling after; no ceiling card beside it."""
    from .test_root_floor import _incident
    both = _incident(agent.ROOT_ELEVATION, agent.LOGIN_AFTER_BRUTE_FORCE, rid=VM)
    state = {"signal": _signal(), "past_cycles": [], "incident": both, "dry_run": True, "telemetry_gaps": []}
    with patch("litellm.completion", return_value=_llm("isolate_vm", 0.8)):
        out = agent.decide(state, model="anthropic/claude-test", autonomy=AutonomyConfig(default="human_only"))
    assert out["held_by"] == "floor" and out["action"] == "isolate_vm" and out["ceiling_card"] is False
    reason = out["escalation_reason"]
    assert reason.startswith("Plancher déterministe (B3a)")
    assert "Le choix du modèle : 'isolate_vm', ramené à 'snapshot' par le plafond de la règle" in reason
    assert reason.index("Plancher") < reason.index("Plafond de la règle")
    # No ceiling's card here: the isolation is the floor's card's to approve, and the reason says so.
    assert "proposé sur la carte du plancher" in reason and "carte du plafond" not in reason


def test_a_block_proposed_above_the_ceiling_leaves_nothing_to_approve(graph, watch):
    """The model blocks (above the ceiling): through the graph to store_cycle, the ceiling's card says
    it and proposes nothing in one click — never a block passed before never_block, never an
    isolation the model did not propose."""
    from eregion_core.action_queue import proposed_verbs
    [signal] = _detections(_disk_row(74_300_000))
    final, conn = graph(signal, "non_disruptive", _llm("block_suspicious_ip", 0.9))
    assert conn.writes() == ["snapshot"] and final["action"] == "snapshot"      # no block written
    [card] = _of("ceiling_proposal")
    assert card["action"] == "" and proposed_verbs(card) == frozenset()
    assert card["ceiling"]["proposed"] == "block_suspicious_ip"
    assert "'block_suspicious_ip' reste à faire à la main" in " ".join(card["suggested_steps"])


@pytest.mark.parametrize("action", ["isolate_vm", "block_suspicious_ip"])
@pytest.mark.parametrize("mode", ["non_disruptive", "full_auto", "human_only"])
def test_no_disruptive_action_leaves_the_rule_whatever_the_mode(mode, action):
    """Whatever the model proposes beyond the snapshot, and however sure, the decision is the snapshot."""
    out = _decide(_signal(), _llm(action, 0.97), mode)
    assert out["action"] == "snapshot" and out["ceiling"]["proposed"] == action
    assert out["ceiling"]["confidence"] == 0.97


def test_the_snapshot_the_model_chose_is_untouched():
    """The model's own snapshot is within the ceiling: no ceiling said, the floor of V-11 as before."""
    out = _decide(_signal(), _llm("snapshot", 0.9))
    assert out["action"] == "snapshot" and out["ceiling"] == {}
    assert out["uncontained"].startswith("Détection caractérisée (T1486)")


def test_an_action_only_a_human_approves_is_untouched():
    """A restore is a human's already: the ceiling never touches it."""
    out = _decide(_signal(), _llm("restore_from_backup", 0.9))
    assert out["action"] == "restore_from_backup" and out["ceiling"] == {}
    assert agent._route_after_decide(out) == "escalate_to_human"


# ── La garde ne relâche jamais une autre garde ──────────────────────────────────────────────────────

def test_a_decision_held_before_stays_held_by_its_gate():
    """Below the threshold: the confidence's card stays the confidence's, its reason kept — it now
    proposes the snapshot, and says the ceiling."""
    out = _decide(_signal(), _llm("isolate_vm", 0.5))
    assert out["escalate"] is True and out["held_by"] == "confidence" and out["action"] == "snapshot"
    assert out["escalation_reason"].startswith(f"Plafond de la règle « {RULE} »")
    assert "Low confidence (50%)" in out["escalation_reason"]


def test_an_unattributed_detection_stays_the_attribution_s_card():
    """A row that names no VM: the attribution's card, whatever the ceiling — never the VM it is filed
    on named in the ceiling's gesture."""
    out = _decide(_signal(attribution="unattributed", candidates=["vm-g1", "vm-g2"]), _llm("isolate_vm", 0.95))
    assert out["held_by"] == "attribution" and out["escalate"] is True and out["action"] == "snapshot"
    assert out["ceiling_card"] is False
    assert "glorfindel isolate" not in out["escalation_reason"]
    assert "depuis la CLI, une fois la VM identifiée" in out["escalation_reason"]


# ── Une règle sans plafond n'est pas touchée ; les autres règles ne changent pas ─────────────────────

def test_only_the_disk_write_rule_carries_a_ceiling():
    """Fini quand: the other shipped rules do not change — one rule only carries a ceiling."""
    rules = load_config(shipped_rules_path(), glorfindel_cfg=_cfg(), client_layer=False).rules
    capped = {r.name: r.ceiling for r in rules if r.ceiling is not None}
    assert capped == {RULE: rule_ceiling.Ceiling(allow=("snapshot",), lifted_by=(), why=capped[RULE].why)}
    assert rule_ceiling.current().by_name[RULE].allow == ("snapshot",)


def test_a_rule_without_a_ceiling_isolates_as_before():
    """ssh-brute-force carries no ceiling: the model's isolation runs alone in non_disruptive."""
    row = {"Computer": "vm-g1", "_ResourceId": VM, "SourceIP": "185.220.101.5", "FailedAttempts": 47}
    out = _decide(_signal("ssh-brute-force", "T1110.001", row), _llm("isolate_vm", 0.95))
    assert out["action"] == "isolate_vm" and out["escalate"] is False and out["ceiling"] == {}


# ── La couche du client abaisse, jamais ne relève ────────────────────────────────────────────────────

def test_the_client_s_layer_never_raises_the_shipped_ceiling():
    """A client copy that allows isolate_vm: the shipped ceiling holds, and it is said."""
    entry = _shipped_entry()
    entry["ceiling"] = {"allow": ["snapshot", "isolate_vm"], "lifted_by": ["root_elevation"]}
    _client_layer(entry)
    cfg = load_config(shipped_rules_path(), glorfindel_cfg=_cfg())
    rule = next(r for r in cfg.rules if r.name == RULE)
    assert rule.layer == "client" and rule.ceiling.allow == ("snapshot",) and rule.ceiling.lifted_by == ()
    assert any("plafond relevé" in n and RULE in n for n in cfg.notes)
    out = _decide(_signal(), _llm("isolate_vm", 0.95))
    assert out["action"] == "snapshot" and out["ceiling"]["allow"] == ["snapshot"]


def test_a_client_rule_that_says_no_ceiling_keeps_the_shipped_one():
    """A client copy without `ceiling:` replaces the rule, never its ceiling."""
    entry = _shipped_entry()
    entry.pop("ceiling")
    _client_layer(entry)
    assert _shipped(client_layer=True).ceiling.allow == ("snapshot",)
    assert _decide(_signal(), _llm("isolate_vm", 0.95))["action"] == "snapshot"


def test_a_client_ceiling_that_cannot_be_read_skips_its_rule_and_the_shipped_one_loads():
    """`allow` naming an action that is not autonomous: the client's entry is skipped and said, the
    shipped rule loads, its ceiling with it."""
    entry = _shipped_entry()
    entry["ceiling"] = {"allow": ["snapshot", "delete_resource"]}
    _client_layer(entry)
    cfg = load_config(shipped_rules_path(), glorfindel_cfg=_cfg())
    rule = next(r for r in cfg.rules if r.name == RULE)
    assert rule.layer == "base" and rule.ceiling.allow == ("snapshot",)
    assert any("ceiling.allow" in n and "delete_resource" in n and "ignorée" in n for n in cfg.notes)


def test_the_client_s_layer_may_lower_a_rule_without_a_ceiling():
    """The client caps a rule the base leaves free: lowering, allowed."""
    entry = _shipped_entry("ssh-brute-force")
    entry["ceiling"] = {"allow": ["snapshot", "block_suspicious_ip"]}
    _client_layer(entry)
    row = {"Computer": "vm-g1", "_ResourceId": VM, "SourceIP": "185.220.101.5", "FailedAttempts": 47}
    out = _decide(_signal("ssh-brute-force", "T1110.001", row), _llm("isolate_vm", 0.95))
    assert out["action"] == "snapshot" and out["ceiling"]["rule"] == "ssh-brute-force"
    out = _decide(_signal("ssh-brute-force", "T1110.001", row), _llm("block_suspicious_ip", 0.95))
    assert out["action"] == "block_suspicious_ip" and out["ceiling"] == {}


# ── La place pour la corroboration ───────────────────────────────────────────────────────────────────

def _sudo_rule(lifted_by: list[str]) -> dict:
    return {"name": "client-sudo-capped", "ttp": "T1548.003", "enabled": True, "assets": ["auto"],
            "query": "Syslog | where ProcessName == 'sudo' | project TimeGenerated, Computer, _ResourceId, "
                     "ProcessName, SyslogMessage",
            "ceiling": {"allow": ["snapshot"], "lifted_by": lifted_by}}


@pytest.mark.parametrize("lifted_by,expected", [(["root_elevation"], "isolate_vm"), ([], "snapshot")])
def test_a_fact_the_rule_names_lifts_its_ceiling(lifted_by, expected):
    """The hook of the corroboration: a fact of the detection named in `lifted_by` lifts the ceiling
    (a sudo to root confirms `root_elevation`, B3a); without it, the snapshot."""
    _client_layer(_sudo_rule(lifted_by))
    row = {"Computer": "vm-g1", "_ResourceId": VM, "ProcessName": "sudo",
           "SyslogMessage": "alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/bash"}
    out = _decide(_signal("client-sudo-capped", "T1548.003", row), _llm("isolate_vm", 0.95))
    assert out["action"] == expected


def test_the_shipped_rule_lifts_nothing_yet():
    """RDW1: the corroboration comes in a lot of its own — the shipped list is empty."""
    assert _shipped_entry()["ceiling"]["lifted_by"] == []


# ── La boucle T1486 : l'attaque reste détectée ; attack_started aussi plafonné ───────────────────────

def test_a_real_t1486_stays_detected_and_its_card_proposes_the_snapshot(graph):
    """Fini quand: an encryption's write rate (the strongest of the measured attacks, 91.7 MB/s) is
    still detected by the rule; its decision is the snapshot and a card — the isolation a human's."""
    signals = _detections(_disk_row(91_700_000))
    assert len(signals) == 1 and signals[0]["ttp"] == "T1486"
    final, conn = graph(signals[0], "non_disruptive", _llm("isolate_vm", 0.93))
    assert "isolate_vm" not in conn.calls and final["action"] == "snapshot"
    assert [c["ceiling"]["proposed"] for c in escalations.pending()] == ["isolate_vm"]


def test_an_attack_started_resolved_by_the_rule_of_its_ttp_is_capped_too():
    """Annatar's attack_started names no rule: the rule of its TTP, the one the graph polls."""
    sig = _signal(rule=None)
    sig["context"].pop("rule_name", None)
    out = _decide(sig, _llm("isolate_vm", 0.95))
    assert out["action"] == "snapshot" and out["ceiling"]["rule"] == RULE


def test_the_shipped_query_does_not_change_only_a_key_is_added():
    """The query to the byte of before RDW1 — `shipped_query` reads it alone (MID1); the fingerprint of
    the whole rule (`base_sha256`, WL1) does change: a client copy made before is set aside."""
    import hashlib
    entry = _shipped_entry()
    assert hashlib.sha256(entry["query"].encode()).hexdigest() == QUERY_SHA256
    assert shipped_query(RULE, entry["query"])
    without = {k: v for k, v in entry.items() if k != "ceiling"}
    assert base_rule_sha256(entry) != base_rule_sha256(without)


# ── Le plafond ne voyage jamais dans le signal ; illisible, le plus bas ──────────────────────────────

def test_the_ceiling_never_enters_what_the_model_reads():
    """The signal the RulePoller sends carries no ceiling (`_build_user_message` dumps it)."""
    [signal] = _detections(_disk_row(74_300_000))
    assert "ceiling" not in json.dumps(signal) and "allow" not in json.dumps(signal["context"])


def test_rules_that_cannot_be_read_bring_the_decision_back_to_the_lowest(monkeypatch):
    def unreadable():
        raise OSError("detection_rules.yaml: permission denied")
    monkeypatch.setattr(rule_ceiling, "current", unreadable)
    row = {"Computer": "vm-g1", "_ResourceId": VM, "SourceIP": "185.220.101.5", "FailedAttempts": 47}
    out = _decide(_signal("ssh-brute-force", "T1110.001", row), _llm("isolate_vm", 0.95))
    assert out["action"] == "snapshot" and "illisibles" in out["ceiling"]["why"]


@pytest.mark.parametrize("content", [None, "", "rules: []\n"])
def test_a_shipped_base_gone_or_empty_is_unreadable_never_no_ceiling(monkeypatch, tmp_path, content):
    """`_read_layer` reads a file gone as {}: the ceilings read then raise — `decide` brings the
    decision back to the lowest, never to no ceiling at all."""
    base = tmp_path / "gone.yaml"
    if content is not None:
        base.write_text(content)
    monkeypatch.setattr(detection_rules, "shipped_rules_path", lambda: base)
    with pytest.raises(FileNotFoundError):
        rule_ceiling.current()
    out = _decide(_signal(), _llm("isolate_vm", 0.95))
    assert out["action"] == "snapshot" and "illisibles" in out["ceiling"]["why"]


@pytest.mark.parametrize("value,said", [
    ("snapshot", "dictionnaire"),
    ({"allow": "snapshot"}, "liste d'actions"),
    ({"allow": ["isolate_vm"]}, "garder « snapshot »"),
    ({"allow": ["snapshot", "wipe_storage"]}, "n'est pas une action autonome"),
    ({"allow": ["snapshot"], "lifted_by": ["Root Elevation"]}, "noms de faits"),
    ({"allow": ["snapshot"], "why": "x" * 301}, "300 caractères"),
    ({"allow": ["snapshot"], "max": 1}, "clé inconnue"),
])
def test_a_ceiling_that_cannot_be_read_is_refused(value, said):
    assert said in rule_ceiling.refusal(value)


def test_an_unreadable_shipped_ceiling_is_the_lowest_and_said():
    notes: list[str] = []
    base = [{"name": "r", "ceiling": {"allow": ["isolate_vm"]}}]
    assert rule_ceiling.of_rules(base, base, {"r": "base"}, notes) == {"r": rule_ceiling.LOWEST}
    assert any("plafond illisible" in n for n in notes)


# ── La console : les deux propositions, la raison, rien de brut ──────────────────────────────────────

def test_the_console_says_both_proposals_and_the_reason_escaped():
    js = JS.read_text()
    body = re.search(r"function _cardBody\(e, vmName\) \{.*?\n\}", js, re.S).group(0)
    assert "${_ceilingNote(e)}" in body
    note = re.search(r"function _ceilingNote\(e\) \{.*?\n\}", js, re.S).group(0)
    for field in ("c.rule", "actionLabelVerb(c.proposed)", "actionLabelVerb(c.lowered || 'snapshot')", "c.why"):
        assert f"_attr({field})" in note, field
    # Nothing raw (#254): the reader of scripts/console_escaping.py, on the pages as they stand.
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("console_escaping", ROOT / "scripts" / "console_escaping.py")
    ce = sys.modules[spec.name] = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ce)
    assert ce.check() == []


def test_the_card_s_command_names_the_isolation_left_to_a_human_never_on_a_loose_card():
    js = JS.read_text()
    cli = re.search(r"function cliCommand\(esc\) \{.*?\n\}", js, re.S).group(0)
    assert cli.index("if (loose)") < cli.index("_ceilingCommand(esc)")
    assert cli.index("_isAnchored(esc)") < cli.index("_ceilingCommand(esc)")
    # The held snapshot's commands, and a card's ack, say it first.
    assert "return ceiling + (actionMap[esc.action]" in cli and "return ceiling + `glorfindel ack ${id}`;" in cli
    cmd = re.search(r"function _ceilingCommand\(e\) \{.*?\n\}", js, re.S).group(0)
    # A comment only: the block is run as a whole — its snapshot must never isolate too.
    [line] = [ln for ln in cmd.splitlines() if "glorfindel isolate" in ln]
    said = line.split("return `", 1)[1]
    assert said.startswith("# rule ceiling:") and "only after judging" in said
    assert "\\nglorfindel isolate" not in cmd
    assert "e.action === 'isolate_vm'" in cmd        # the ceiling's own card: its own command


# ── Dagorlad : ce qu'on attend d'un fil T1486 ────────────────────────────────────────────────────────

def test_dagorlad_expects_a_snapshot_alone_and_a_card_for_a_capped_rule():
    """The envelope of a T1486 wire in `non_disruptive`: the rule's ceiling — a snapshot alone, a card,
    never « may contain alone »; a rule without a ceiling is said as before."""
    from eregion_console import board
    from eregion_core.exercise_plan import load_catalog
    cat = load_catalog()
    card = {"backend": "law", "mode": "non_disruptive", "hold": "", "read_only": False}
    capped = [{"name": RULE, "ttp": "T1486", "enabled": True, "backend": "law", "expected_latency_s": 45,
               "allow": ["snapshot"]}]
    out = board.expected(cat["T1486"], card, capped, 0.7)
    assert out["summary"].endswith("snapshot alone · card") and RULE in out["glorfindel"]
    assert "at most a snapshot, the restore waits" in out["glorfindel"]
    free = [{**capped[0], "allow": None}]
    assert board.expected(cat["T1486"], card, free, 0.7)["summary"].endswith("may contain alone")


def test_the_console_reads_each_rule_s_ceiling(monkeypatch):
    import eregion_console.api as api
    monkeypatch.setattr(api, "_base_rules_path", lambda: shipped_rules_path())
    rules = {r["name"]: r for r in api._board_rules()}
    assert rules[RULE]["allow"] == ["snapshot"] and rules["ssh-brute-force"]["allow"] is None
