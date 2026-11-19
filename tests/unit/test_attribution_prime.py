"""ATT1 (#936): the attribution guard primes over any hold before it — a card on a detection attributed
to no VM is never approvable in one click.

Seen on Imladris on 19/11: a detection that names no VM, below the confidence threshold, became a
`low_confidence` card carrying `isolate_vm` — a type the approval takes —, and the console offered
« Approve & execute ». One click would have isolated the VM the card is only filed on (the first VM
watched, by name), which the detection does not name. `_apply_attribution_guard` left at once when a
gate before it (the confidence) had held the decision.

Now, on such a detection, an action aimed at the VM (`isolate_vm`, `block_suspicious_ip`,
`release_isolation`) is always the attribution's card (`unattributed_signal`), whatever held it
first — the confidence, never_block, the release precondition —, the reason before kept. The mode's
hold stays the mode's: a `mode_hold` card there approves the model's own action only when it is not
aimed at the VM (a snapshot). And everywhere one approves — the server (`approval_refusal`, the
signed queue), the console's buttons, the bot, the TUI —, a card that says it is unattributed and
holds an action aimed at the VM has no one-click approval; the suggested commands never name the VM
it is filed on. Last, the exclusion of the watch's return channel (SLF1) is the shipped rule's only.

No Azure call, no model call (the model is patched), a throwaway store (tests/unit/conftest.py).
Mutants M6451–M6465 (scripts/mutants/ATT1.py).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from eregion_core import action_queue
from eregion_core.action_queue import proposed_verbs
from glorfindel import agent, escalations
from glorfindel.approval import approval_refusal
from glorfindel.config import AutonomyConfig

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "eregion_console/static/glorfindel.js"
RID = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-b3a"
CANDIDATES = ["vm-b3a", "vm-b3b"]
LOOSE = {"state": "unattributed", "candidates": CANDIDATES}
IP = "185.220.101.5"


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
        raise AssertionError("no Azure in tests (ATT1)")
    monkeypatch.setattr(AzureConnector, "_ensure_clients", no_azure)


def _decision(action: str, confidence: float = 0.9) -> MagicMock:
    """The model, patched: a security_decision call that answers `action`."""
    call = MagicMock()
    call.function.arguments = json.dumps({
        "reasoning": f"r — {action}", "confidence": confidence, "action": action, "reversible": True,
        "explanation": "e", "escalate": False, "escalation_reason": "", "suggested_steps": []})
    resp = MagicMock()
    resp.choices[0].message.tool_calls = [call]
    resp.usage = None
    return resp


def _signal(*, attributed: bool = False, **row) -> dict:
    """A RulePoller detection of `ssh-brute-force` on vm-b3a — attributed to it, or anchored there
    without naming it (`unattributed`, its candidates), as the RulePoller sends it."""
    context = {"rule_name": "ssh-brute-force", "run_id": "watch-ssh-brute-force-20261119T100000Z"}
    context.update({"attribution": "asset"} if attributed
                   else {"attribution": "unattributed", "candidates": list(CANDIDATES)})
    return {
        "signal_id": f"rule-ssh-brute-force-b3a-{'own' if attributed else 'loose'}", "event": "detection",
        "ttp": "T1110.001",
        "severity": "high", "resource_id": RID, "resource_type": "vm",
        "timestamp": "2026-11-19T10:00:00+00:00", "context": context,
        "raw_signal": {"first_result_row": {"SourceIP": IP, "FailedAttempts": 47, **row}},
    }


def _decide(signal: dict, resp, mode: str = "non_disruptive") -> dict:
    state = {"signal": signal, "past_cycles": [], "incident": None, "dry_run": True,
             "telemetry_gaps": []}
    with patch("litellm.completion", return_value=resp):
        return agent.decide(state, model="anthropic/claude-test", autonomy=AutonomyConfig(default=mode))


def _card_of(out: dict) -> dict:
    """The card the cycle writes (escalate_to_human, the store), as every surface reads it."""
    agent.escalate_to_human({**out, "dry_run": False})
    [card] = [c for c in escalations.pending() if c["signal_id"] == out["signal"]["signal_id"]]
    return card


def _no_one_click(card: dict) -> None:
    """Nowhere approvable in one click: the server refuses it, the watch signs no proposal, the
    bot and the TUI give no button nor key aimed at its VM."""
    assert approval_refusal(card, "vm-b3a"), card
    assert "non attribuée" in approval_refusal(card, "vm-b3a").lower()
    assert proposed_verbs(card) == frozenset() and "proposal" not in card
    from glorfindel import tui
    assert tui._anchored(card) and not tui._can_restore(card) and not tui._can_undo(card)
    assert tui._commands("r", card, "2026-11-19T09:00:00+00:00") == []


@pytest.fixture
def watch():
    """The watch's process: its key signs the proposals of the cards it writes."""
    from eregion_core import watch_key
    signer = watch_key.Signer(bytes(range(32)))
    escalations.sign_proposals(lambda: signer)
    return signer


# ── The guard primes over every hold before it ───────────────────────────────────────────────────

def test_the_guard_holds_the_approval_s_own_set():
    """One list (the decision never imports the signed queue, FS1a): the actions the guard holds
    are the ones no approval runs on an unattributed card — the VM's isolation, a block on its NSG,
    the release of its isolation; never the snapshot."""
    assert agent._ATTRIBUTION_HELD == action_queue.VM_AIMED_ACTIONS
    assert {"isolate_vm", "block_suspicious_ip", "release_isolation"} <= action_queue.VM_AIMED_ACTIONS
    assert "snapshot" not in action_queue.VM_AIMED_ACTIONS
    page = re.search(r"const _VM_AIMED = new Set\(\[([^\]]*)\]\);", JS.read_text())
    assert page and set(re.findall(r"'([a-z_]+)'", page.group(1))) == action_queue.VM_AIMED_ACTIONS


def test_the_attribution_s_card_is_no_approvable_type():
    """The attribution's card is never one of the types a human approves in one click — on the
    server (the queue's list, the console's) nor on the page (`_HELD_TYPES`) — whatever else
    refuses it before (its type, `unattributed_aim`): one refusal never stands for the others."""
    assert "unattributed_signal" not in action_queue.APPROVABLE_TYPES
    page = re.search(r"const _HELD_TYPES = new Set\(\[([^\]]*)\]\);", JS.read_text())
    assert page and "unattributed_signal" not in page.group(1)


@pytest.mark.parametrize("action,before,row", [
    ("isolate_vm", "Low confidence (50%)", {}),                                  # the confidence
    ("block_suspicious_ip", "Blocage de 10.0.0.5 retenu : adresse protégée", {"SourceIP": "10.0.0.5"}),
    ("release_isolation", "Levée d'isolation proposée", {}),                     # the release precondition
], ids=["confidence", "never_block", "release_precondition"])
def test_an_unattributed_detection_held_before_is_the_attribution_s_card(watch, action, before, row):
    """Fini quand: whatever held it first, an action aimed at the VM on a detection that names no
    VM is the attribution's card (`unattributed_signal`) — never `low_confidence`,
    `protected_address`, `release_hold` (each approvable or proposable before) —, the reason before
    kept after its own; the server refuses it, no proposal is signed, no button nor key."""
    confidence = 0.5 if action == "isolate_vm" else 0.95
    out = _decide(_signal(**row), _decision(action, confidence))
    assert out["escalate"] is True and out["action"] == action
    assert out["held_by"] == "attribution" and out["mode_hold"] is False
    reason = out["escalation_reason"]
    assert reason.startswith("Détection non attribuable à une VM") and "vm-b3a, vm-b3b" in reason
    assert f" — {before}" in reason                                     # the hold before, kept
    card = _card_of(out)
    assert card["escalation_type"] == "unattributed_signal" and card["attribution"] == LOOSE
    _no_one_click(card)


def test_an_attack_started_line_unattributed_keeps_the_reason_before_too():
    """The line named the VM, the row the rule found does not (SEC4a): the same precedence."""
    sig = _signal()
    sig["context"]["attribution_from"] = "attack_started"
    out = _decide(sig, _decision("isolate_vm", 0.4))
    assert out["held_by"] == "attribution"
    assert out["escalation_reason"].startswith("La ligne de détection trouvée ne nomme pas la VM")
    assert " — Low confidence (40%)" in out["escalation_reason"]


def test_a_snapshot_on_an_unattributed_detection_is_not_held_by_the_guard():
    """The snapshot is not aimed at the VM (SEC-Ec: what it does there stays Jonathan's): below the
    threshold, it stays the confidence's card."""
    out = _decide(_signal(), _decision("snapshot", 0.5))
    assert out["held_by"] == "confidence"


# ── The mode's hold stays the mode's ─────────────────────────────────────────────────────────────

def test_human_only_never_holds_an_unattributed_isolation_for_approval(watch):
    """human_only, the model isolates at 95 %: the guard holds it before the mode — the attribution's
    card, never `mode_hold` (approvable)."""
    out = _decide(_signal(), _decision("isolate_vm", 0.95), mode="human_only")
    assert out["held_by"] == "attribution" and out["mode_hold"] is False
    card = _card_of(out)
    assert card["escalation_type"] == "unattributed_signal"
    _no_one_click(card)


def test_a_mode_hold_on_an_unattributed_detection_approves_the_snapshot_only(watch):
    """human_only, the model's snapshot: the card stays the mode's, approvable for the snapshot —
    its own action, not aimed at the VM. A `mode_hold` card that would hold an isolation there (one
    written before ATT1, another writer of the store) approves nothing in one click."""
    out = _decide(_signal(), _decision("snapshot", 0.95), mode="human_only")
    assert out["mode_hold"] is True
    snap = _card_of(out)
    assert snap["escalation_type"] == "mode_hold" and snap["attribution"] == LOOSE
    assert approval_refusal(snap, "vm-b3a") is None and proposed_verbs(snap) == {"snapshot"}
    for action in ("isolate_vm", "block_suspicious_ip", "release_isolation"):
        cid = escalations.record(signal_id=f"s-{action}", resource_id=RID, action=action,
                                 escalation_type="mode_hold", reason="held", attribution=LOOSE,
                                 action_params={"ip": IP} if action == "block_suspicious_ip" else None)
        _no_one_click(next(c for c in escalations.pending() if c["id"] == cid))


@pytest.mark.parametrize("etype", ["low_confidence", "uncharacterized_signal", "release_hold", "telemetry_gap",
                                   "unstable_decision", "floor_proposal", "mode_hold"])
def test_no_approvable_type_runs_an_unattributed_isolation(watch, etype):
    """Whatever its type: a card that says it is unattributed and holds an action aimed at its VM is
    refused by the server, signed no proposal (the cards written before ATT1 included)."""
    cid = escalations.record(signal_id=f"s-{etype}", resource_id=RID, action="isolate_vm",
                             escalation_type=etype, reason="held", attribution=LOOSE)
    _no_one_click(next(c for c in escalations.pending() if c["id"] == cid))


# ── The witness: an attributed card keeps its behaviour ──────────────────────────────────────────

def test_an_attributed_detection_below_the_threshold_stays_low_confidence_and_approvable(watch):
    """Fini quand: a detection that names its VM, below the threshold — `low_confidence`, held by
    the confidence, approvable in one click and proposed, as before ATT1."""
    out = _decide(_signal(attributed=True), _decision("isolate_vm", 0.5))
    assert out["held_by"] == "confidence"
    card = _card_of(out)
    assert card["escalation_type"] == "low_confidence" and "attribution" not in card
    assert approval_refusal(card, "vm-b3a") is None
    assert proposed_verbs(card) == {"isolate_vm"} and card["proposal"]["action"] == "isolate_vm"
    from glorfindel import tui
    assert not tui._anchored(card)


# ── The server: the console's route ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("etype", ["low_confidence", "mode_hold"])
def test_the_console_s_approve_route_refuses_an_unattributed_isolation(monkeypatch, etype):
    """Called directly, the route refuses it before any connector (the page shows no button)."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from .console_client import console
    monkeypatch.setattr("glorfindel.actions.AzureConnector",
                        lambda **k: (_ for _ in ()).throw(AssertionError("no Azure")))
    cid = escalations.record(signal_id="s", resource_id=RID, action="isolate_vm", escalation_type=etype,
                             reason="held", attribution=LOOSE)
    error = console().post(f"/api/action/approve/{cid}", json={}).json()["error"]
    assert "non attribuée" in error.lower() and "isolate_vm" in error
    assert [c["id"] for c in escalations.pending()] == [cid]            # still waiting, untouched


def test_the_console_restores_no_unattributed_card():
    """A restore the model proposed on a detection that names no VM: the page has no « 🔄 Restore » on
    it, and the route refuses it (the VM is the one the card is filed on); an attributed one, as
    before."""
    pytest.importorskip("fastapi")
    from eregion_console import api
    loose = _card("restore_from_backup", "destructive_action", loose=True)
    refusal, _ = api._restore_refusal(loose["id"], "vm-b3a")
    assert refusal and "anchored" in refusal
    own = _card("restore_from_backup", "destructive_action", loose=False)
    assert api._restore_refusal(own["id"], "vm-b3a") == (None, RID)
    js = JS.read_text()
    assert "const restoreOffered = isRestore && !_unattributed(e);" in js
    assert js.count("_on('click', 'confirmRestore'") == 1
    assert ": restoreOffered\n    ? `<button class=\"action primary\" ${_on('click', 'confirmRestore'" in js


# ── The console's page: no button ────────────────────────────────────────────────────────────────

def _fn(js: str, head: str) -> str:
    return js.split(head, 1)[1].split("\n}\n", 1)[0]


def test_the_page_offers_no_one_click_approval_on_an_unattributed_card():
    """« Approve & execute » is drawn only where `_isHeld` says so, and `_isHeld` refuses a card that
    says it is unattributed and holds an action aimed at its VM; « 📸 Snapshot » is never offered on
    an unattributed card (it would snapshot the VM the card is filed on)."""
    js = JS.read_text()
    held = _fn(js, "function _isHeld(e) {")
    assert "&& !_aimsLoose(e)" in held
    assert "function _aimsLoose(e) { return !!_unattributed(e) && _VM_AIMED.has(e.action); }" in js
    assert "&& !_unattributed(e)" in _fn(js, "function _isSnapshotPending(e) {")
    # Every « Approve & execute » under `isModeHold`, and `isModeHold` is `_isHeld`.
    approves = [m.start() for m in re.finditer("▶ Approve & execute", js)]
    assert len(approves) == 2
    for at in approves:
        assert js[:at].rstrip().rsplit("\n", 2)[-2].strip().startswith(": isModeHold")
    assert js.count("isModeHold        = _isHeld(e);") == 2
    # Every « 📸 Snapshot » of a card under `isSnapshotPending`, which is `_isSnapshotPending`.
    assert js.count("isSnapshotPending = _isSnapshotPending(") == 3
    assert "e.action === 'snapshot' && e.escalation_type === 'low_confidence')" not in js.replace(
        "&& !(e.action === 'snapshot' && e.escalation_type === 'low_confidence')", "")
    assert "const hasSnapshotEsc = myEscs.some(e => _isSnapshotPending(e) || _looseSnapshot(e));" in js


def test_the_page_s_command_never_names_the_vm_of_an_unattributed_card():
    """`cliCommand`: on a card that says it is unattributed, whatever its type, « not attributed »
    and its candidates, the judgement to the CLI, the ack — never a command on its VM."""
    cmd = _fn(JS.read_text(), "function cliCommand(esc) {")
    loose = cmd.split("if (loose) {", 1)[1].split("\n  }\n", 1)[0]
    assert cmd.index("if (loose) {") < cmd.index("if (_isAnchored(esc))") < cmd.index("if (_isHeld(esc))")
    assert "_vmArg" not in loose and "rid" not in loose
    assert "${said}" in loose and "judge which VM it is about from the CLI" in loose
    assert "glorfindel ack ${id}" in loose
    assert ".replace(/[\\u0000-\\u001f\\u007f]/g, ' ')" in loose     # one line: no command slipped in


def test_the_page_never_says_an_unattributed_card_s_action_done():
    """A card no longer `_isHeld` took its past label (« VM isolated from network ») — said of an
    isolation nothing ran. On a card that says it is unattributed: its verb, « held: not attributed »,
    wherever its title is drawn (the tile's card, its details, the command's window); never on a card
    whose action did run."""
    js = JS.read_text()
    loose = _fn(js, "function _looseTitle(e) {")
    assert "if (!_unattributed(e) || !ACTION_LABELS_VERB[e.action] || _RAN_TYPES.has(e.escalation_type)) return '';" in loose
    assert "return `${ACTION_LABELS_VERB[e.action]} — held: not attributed`;" in loose
    ran = re.search(r"const _RAN_TYPES = new Set\(\[([^\]]*)\]\);", js)
    assert ran and set(re.findall(r"'([a-z_]+)'", ran.group(1))) == {
        "autonomous_action", "verification_failed", "write_blocked", "action_failed"}
    title = _fn(js, "function escTitle(e) {")
    assert title.index("if (loose) return loose;") < title.index("ACTION_LABELS[e.action]")
    assert "const loose = _looseTitle(e);" in title
    assert ": isSnapshotPending ? 'Snapshot recommended' : (_looseTitle(esc) || actionLabel(esc.action));" in js
    # The tile's card and its details fall to escTitle for a card not held.
    assert "\n    : escTitle(e);\n" in js and "\n      : escTitle(e);\n" in js


def test_the_tile_s_snapshot_stays_hidden_while_an_unattributed_snapshot_waits():
    """The card of an unattributed snapshot has no « 📸 Snapshot »: the tile's own button stays hidden
    too while it waits — it would snapshot the VM the detection does not name."""
    js = JS.read_text()
    assert "function _looseSnapshot(e) { return e.action === 'snapshot' && !!_unattributed(e); }" in js
    assert js.count("      : hasSnapshotEsc\n        ? ''\n") == 2


def test_the_bot_says_an_unattributed_card_s_action_not_done():
    """Discord's title says what is recommended, not done — an unattributed card's included."""
    pytest.importorskip("discord")
    from glorfindel.bot import _embed_title
    for etype in ("low_confidence", "unattributed_signal"):
        title = _embed_title(_card("isolate_vm", etype, loose=True))
        assert "non exécuté" in title and "isolée" not in title, title


# ── The suggested commands ───────────────────────────────────────────────────────────────────────

def _cli_steps(card: dict) -> list[str]:
    from glorfindel import cli
    with patch.object(cli, "console") as out:
        cli._render_next_steps(card)
    return [str(c.args[0]) for c in out.print.call_args_list if c.args]


def _card(action: str, etype: str, *, loose: bool, **kw) -> dict:
    cid = escalations.record(signal_id=f"s-{action}-{etype}-{loose}", resource_id=RID, action=action,
                             escalation_type=etype, reason="held", attribution=LOOSE if loose else None,
                             **kw)
    return next(c for c in escalations.pending() if c["id"] == cid)


@pytest.mark.parametrize("action,etype", [
    ("snapshot", "low_confidence"), ("restore_from_backup", "destructive_action"),
    ("release_isolation", "unattributed_signal"), ("delete_resource", "destructive_action"),
])
def test_glorfindel_pending_never_names_the_vm_an_unattributed_card_is_filed_on(action, etype):
    """The fallback of `glorfindel pending` (a card without the model's steps): « not attributed »,
    its candidates, the judgement to the CLI — never `az vm show -n <vm>`, `glorfindel restore <vm>`,
    `glorfindel release <vm>`."""
    steps = " ".join(_cli_steps(_card(action, etype, loose=True)))
    assert "Not attributed — candidates: vm-b3a, vm-b3b" in steps and "act on that VM from the CLI" in steps
    assert "-n vm-b3a" not in steps and "rg/vm-b3a" not in steps and "<id: glorfindel list --ids>" not in steps
    for verb in ("restore", "release", "az vm show", "delete"):
        assert verb not in steps.replace("glorfindel ack", "")


def _with_steps(loose: bool) -> dict:
    return _card("isolate_vm", "low_confidence", loose=loose,
                 suggested_steps=["glorfindel isolate rg/vm-b3a --yes", "Vérifier les journaux"])


def test_the_model_s_steps_of_an_unattributed_card_are_said_aimed_at_the_anchor():
    """The model's steps, shown as written, may name the VM the card is filed on: on an unattributed
    card, a line of the code says so before them — `glorfindel pending`, the console's details,
    Discord; never on an attributed one. The model's message is untouched (no zone of the prompt)."""
    lines = _cli_steps(_with_steps(True))
    note = next(i for i, ln in enumerate(lines) if "these steps aim at the VM the card is filed on" in ln)
    assert "Not attributed — candidates: vm-b3a, vm-b3b; judge from the CLI" in lines[note]
    assert note < next(i for i, ln in enumerate(lines) if "glorfindel isolate" in ln)
    assert not any("these steps aim" in ln for ln in _cli_steps(_with_steps(False)))
    js = JS.read_text()
    steps = _fn(js, "function _looseSteps(e) {")
    assert "if (!loose || !(e.suggested_steps || []).length) return '';" in steps
    assert "${_attr(_unattributedTxt(loose))}; judge from the CLI — these steps aim at the VM the card is filed on" in steps
    assert "return _looseSteps(e) + (e.suggested_steps || [])" in js
    assert "_identityPlan(e) : _looseSteps(e) + (e.suggested_steps || [])" in js


def test_discord_says_the_model_s_steps_of_an_unattributed_card_aim_at_the_anchor():
    pytest.importorskip("discord")
    from glorfindel.bot import _embed_body
    [steps] = [v for k, v, _ in _embed_body(_with_steps(True))[1] if k == "Prochaines étapes"]
    first = steps.splitlines()[0]
    assert first.startswith("⚓ non attribuée — candidates : `vm-b3a`, `vm-b3b`")
    assert first.endswith("juger depuis la CLI, ces étapes visent la VM d'ancrage")
    [own] = [v for k, v, _ in _embed_body(_with_steps(False))[1] if k == "Prochaines étapes"]
    assert "⚓" not in own and own.startswith("• ")


def test_glorfindel_pending_keeps_its_commands_on_an_attributed_card():
    """The witness: on a card whose VM is its own, the fallback as before."""
    steps = " ".join(_cli_steps(_card("snapshot", "low_confidence", loose=False)))
    assert "az vm show -g <rg> -n vm-b3a" in steps and "glorfindel restore" in steps
    assert "Not attributed" not in steps


def test_the_card_s_snapshot_step_never_names_the_vm_it_is_filed_on():
    """The step the cycle adds to a snapshot's card (`escalate_to_human`): on an unattributed
    detection, the judgement first, the VM to snapshot named by the human; else as before."""
    out = _decide(_signal(), _decision("snapshot", 0.5))
    steps = " ".join(_card_of(out)["suggested_steps"])
    assert "Détection non attribuée (candidates : vm-b3a, vm-b3b)" in steps
    assert "glorfindel snapshot <groupe>/<nom> --yes" in steps and "rg/vm-b3a" not in steps
    witness = _decide(_signal(attributed=True), _decision("snapshot", 0.5))
    assert "`glorfindel snapshot rg/vm-b3a --yes`" in " ".join(_card_of(witness)["suggested_steps"])


@pytest.mark.parametrize("action,etype", [
    ("restore_from_backup", "destructive_action"), ("snapshot", "low_confidence"),
    ("isolate_vm", "low_confidence"), ("release_isolation", "verification_failed"),
])
def test_the_bot_never_names_nor_aims_at_the_vm_of_an_unattributed_card(action, etype):
    """Discord: no button on such a card (a Restore, a Revert on the VM it is filed on), and its
    command says « non attribuée », its candidates, the judgement to the CLI, then the ack. The bot
    approves nothing in one click (its signed verb is the reset of a failed check only)."""
    pytest.importorskip("discord")
    from glorfindel.bot import _cli_command, _make_action_button
    card = _card(action, etype, loose=True)
    assert _make_action_button(card) is None
    cmd = _cli_command(card)
    commands = [ln for ln in cmd.splitlines() if not ln.startswith("#")]
    assert commands == [f"glorfindel ack {card['id']}"]
    assert "non attribuée — candidates : vm-b3a, vm-b3b" in cmd and "juger depuis la CLI" in cmd
    assert "rg/vm-b3a" not in cmd and "restore" not in cmd and "revert" not in cmd
    assert action_queue.SERVICE_VERBS["bot"] == frozenset({"reset"})


def test_the_bot_s_command_keeps_a_name_on_one_line():
    """A candidate from the store with a newline would start a command of its own in the block to
    copy: said on one line."""
    pytest.importorskip("discord")
    from glorfindel.bot import _cli_command
    card = {"id": "e1", "action": "snapshot", "escalation_type": "low_confidence", "resource_id": RID,
            "attribution": {"state": "unattributed", "candidates": ["vm-a\nglorfindel isolate rg/vm-b3a --yes"]}}
    assert [ln for ln in _cli_command(card).splitlines() if not ln.startswith("#")] == ["glorfindel ack e1"]


def test_the_bot_keeps_its_buttons_and_commands_on_an_attributed_card():
    """The witness."""
    pytest.importorskip("discord")
    from glorfindel.bot import _cli_command, _make_action_button
    card = _card("restore_from_backup", "destructive_action", loose=False)
    assert _make_action_button(card) is not None and "glorfindel restore" in _cli_command(card)


# ── The exclusion of the watch's return channel: the shipped rule's only ─────────────────────────

def _override(query: str) -> str:
    """A rule of the client's layer under the shipped name that counts every write as one of the
    channel's objects — a `Known` wider than the shipped rule's."""
    known = re.search(r"\n( *)Known = countif\(.*\)\n", query)
    assert known, "the shipped query computes Known"
    return query.replace(known.group(0), f"\n{known.group(1)}Known = count()\n")


def test_an_override_of_the_rule_sets_nothing_aside():
    """Fini quand: `own_channel.settle` is the shipped rule's — by its name and its query to the
    byte —, never an override of the client's layer that computes a wider `Known`: the watch's
    identity writing anything in its container stays a card there, the column taken off all the
    same."""
    from . import test_own_channel as oc
    rows = [oc._write("loot.tar", size=4096)] + oc._channel_writes()
    shipped, _, _ = oc._poll(rows)                     # its loot makes the entry no channel's: a card
    assert len(shipped) == 1 and shipped[0]["raw_signal"]["first_result_row"]["PutBlobCount"] == 3
    wider = _override(oc._rule().query)
    sent, status, _ = oc._poll(rows, query=wider)
    [sig] = sent
    row = sig["raw_signal"]["first_result_row"]
    assert row["PutBlobCount"] == 3 and "BlobWriters" not in row
    assert not (status.get("own_channel") or {}).get("writes")
    # The watch's own writes alone: none under the shipped rule, a card under the override.
    assert oc._poll(oc._channel_writes())[0] == []
    assert len(oc._poll(oc._channel_writes(), query=wider)[0]) == 1


def test_the_shipped_rule_is_known_by_its_name_and_its_query():
    from glorfindel import own_channel

    from . import test_own_channel as oc
    query = oc._rule().query
    assert own_channel.is_shipped(query, "data-exfiltration-blob")
    assert not own_channel.is_shipped(query, "my-blob-rule")                 # another name
    assert not own_channel.is_shipped(_override(query), "data-exfiltration-blob")
    assert not own_channel.is_shipped(query + "\n", "data-exfiltration-blob")  # to the byte


def test_an_attack_started_with_another_query_sets_nothing_aside(monkeypatch):
    """`resolve_attack_started`: the watch's own writes set aside under the shipped query only."""
    from glorfindel import own_channel
    from glorfindel.agent import resolve_attack_started
    from glorfindel.providers.azure.monitor import AzureMonitorDetector

    from . import kql_subset
    from . import test_own_channel as oc
    rows = oc._channel_writes()

    def poll(self, query, since, timeout_s, interval_s=10.0, verbose=True, match_row=None):
        found = [r for r in kql_subset.run(query, rows, now=oc.NOW) if match_row is None or match_row(r)]
        return (5, found[0]) if found else None
    monkeypatch.setattr(AzureMonitorDetector, "poll_alert", poll)
    monkeypatch.setattr(own_channel, "_SOURCE", lambda: oc.CHANNEL)

    def resolve(query):
        signal = {"event": "attack_started", "ttp": "T1041", "resource_id": oc.GONDOLIN,
                  "raw_signal": {"detection_source": "azure_monitor", "detection_query": query,
                                 "log_analytics_workspace_id": "ws-test", "detection_timeout_s": 1}}
        return resolve_attack_started(signal, ip_owners=lambda: {oc.GONDOLIN_IP: oc.GONDOLIN})
    assert resolve(oc._rule().query)["event"] != "detection"
    wider = resolve(_override(oc._rule().query))
    assert wider["event"] == "detection"
    assert "BlobWriters" not in wider["raw_signal"]["detected_data"]
