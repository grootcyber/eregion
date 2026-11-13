"""MSK2c (#798) — the TUI shows what a card or a signal says through the CLI's masking (MSK2, MSK3b).

1. The steps of a card: each said as the CLI's `pending` says it (`masking.shown`, with the card's
   id): an ARM id by its name and group, a command naming its VM by `<groupe>/<nom>`, a bare id of
   the card's subscription « <abonnement> » — then cut to 72 characters, never before: a cut in the
   middle of an id would let its first characters through the masking.
2. Every other place of the TUI that writes a text of a card or a signal: the card's line (its
   action, its resource), the confirmation's label, the restore's screen (why, warning, an
   unreadable vault's error), what the restore said, the RESOURCES panel, the FEED's lines.

What is written as it is, with its reason (glorfindel/tui.py, `_escalations_renderable`'s comment):
the card's own id (its first 8 characters, a uuid Glorfindel draws), a block's IP, the moments and
ages, the confidence, the command's `<groupe>/<nom>` (`group_and_name`, which never names a
subscription), the operator's own typing.

No Azure call, no model call, no subprocess. Every identifier is made up (repository public).
Mutants M5220–M5224 (scripts/mutants/MSK2c.py) are measured here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console

from glorfindel import escalations, masking, tui

SUB = "7a1c2e3f-4b5d-4e6f-8a9b-0c1d2e3f4a5b"
SUB2 = "9e8d7c6b-5a4f-4e3d-8c2b-1a0f9e8d7c6b"
RG = "rg-example-a"


def _vm(name: str = "vm-example-01", rg: str = RG, sub: str = SUB) -> str:
    return f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"


VM = _vm()
NSG = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkSecurityGroups/nsg-a"
VAULT_403 = (f"HttpResponseError: (AuthorizationFailed) The client 'agent' does not have authorization "
             f"to perform action 'Microsoft.RecoveryServices/vaults/read' over scope "
             f"'/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.RecoveryServices/vaults/rsv-a'.")


def _flat(text: str) -> str:
    return " ".join(str(text).split())


def _clean(output: str) -> None:
    """No subscription's id, whole or its first characters, and no ARM path."""
    flat = "".join(str(output).split()).lower()      # a line wrapped by the terminal is read whole
    for sub in (SUB, SUB2):
        assert sub[:8] not in flat, output
    assert "subscriptions/" not in flat, output


def _render(renderable) -> str:
    screen = Console(width=400, record=True)
    screen.print(renderable)
    return _flat(screen.export_text())


def _card(steps=(), rid: str = VM, action: str = "isolate_vm", kind: str = "verification_failed", **kw) -> dict:
    return {"id": "c0ffee01-aaaa", "resource_id": rid, "action": action, "escalation_type": kind,
            "reason": "r", "run_id": "r1", "timestamp": "2026-11-13T08:00:00+00:00",
            "first_seen": "2026-11-13T07:58:00+00:00", "suggested_steps": list(steps), **kw}


def _tui_shown(monkeypatch, cards) -> str:
    monkeypatch.setattr(escalations, "pending", lambda: [dict(c) for c in cards])
    monkeypatch.setattr(tui, "_last_restore", {})
    return _render(tui._escalations_renderable(datetime.now(timezone.utc), None, False))


def _no_env_subscription(monkeypatch, value: str | None = None) -> None:
    """The operator's shell names no subscription (or `value`): only the card can teach its own."""
    import os
    for name in [n for n in os.environ if n.upper().endswith("SUBSCRIPTION_ID")]:
        monkeypatch.delenv(name, raising=False)
    if value:
        monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", value)


# ── 1. The steps of a card ──────────────────────────────────────────────────────────────────────

def test_the_tui_shows_a_step_s_arm_id_by_its_name_and_group(monkeypatch):
    """M5220: a step citing a NSG's id is said « nsg-a (groupe rg) », as the CLI says it — never the
    path that names the subscription."""
    _no_env_subscription(monkeypatch)
    shown = _tui_shown(monkeypatch, [_card([f"Inspecter les règles de {NSG}"])])
    assert f"• Inspecter les règles de nsg-a (groupe {RG})" in shown, shown
    _clean(shown)


def test_the_tui_says_a_step_s_command_as_the_cli_s_pending_does(monkeypatch):
    """M5221: a command of the step naming its VM by its id names it by `<groupe>/<nom>` — masked
    alone, it would be « vm (groupe rg) », no command at all. The same text as the CLI's `pending`
    (`masking.shown` with the card's id), cut to 72."""
    _no_env_subscription(monkeypatch)
    step = f"glorfindel release {VM} --yes"
    shown = _tui_shown(monkeypatch, [_card([step])])
    assert f"• glorfindel release {RG}/vm-example-01 --yes" in shown, shown
    assert "(groupe" not in shown, shown
    assert f"• {masking.shown(step, VM)[:72]}" in shown
    _clean(shown)


def test_the_card_s_id_teaches_its_subscription_to_the_tui(monkeypatch):
    """M5222: a step citing the bare id of the card's subscription (no « subscription » before it),
    while the operator's shell names another one: masked by what the card's id teaches."""
    _no_env_subscription(monkeypatch, SUB2)
    shown = _tui_shown(monkeypatch, [_card([f"Vérifier le coffre de {SUB} puis relancer"])])
    assert "• Vérifier le coffre de <abonnement> puis relancer" in shown, shown
    _clean(shown)


def test_a_step_is_cut_after_its_masking_never_before(monkeypatch):
    """M5223: a subscription's id across the 72nd character. Cut first, it is no longer a whole id:
    neither the card's subscription nor « abonnement <guid> » would read it, and its first
    characters would show. Masked first, then cut."""
    _no_env_subscription(monkeypatch)
    step = "a" * 45 + f" abonnement {SUB} à relire"
    assert step.index(SUB) < 72 < step.index(SUB) + len(SUB)
    shown = _tui_shown(monkeypatch, [_card([step])])
    assert "a" * 45 + " abonnement <abonnement> à" in shown, shown
    _clean(shown)


def test_two_steps_at_most_each_cut_to_72(monkeypatch):
    _no_env_subscription(monkeypatch)
    shown = _tui_shown(monkeypatch, [_card(["b" * 100, "deux", "trois"])])
    assert "• " + "b" * 72 + " " in shown and "b" * 73 not in shown, shown
    assert "• deux" in shown and "trois" not in shown


# ── 2. Every other text of a card or a signal ───────────────────────────────────────────────────

def test_the_card_s_line_says_its_action_and_its_resource_masked(monkeypatch):
    """A card filed on a subscription itself (its resource is « /subscriptions/<guid> »): its line
    says « <abonnement> »; an action the model proposed citing an id is masked too."""
    _no_env_subscription(monkeypatch)
    shown = _tui_shown(monkeypatch, [
        _card(rid=f"/subscriptions/{SUB}", action=f"lock_{SUB}", kind="proposed_action")])
    assert "<abonnement>" in shown, shown
    assert "→ glorfindel ack c0ffee01" in shown, shown
    _clean(shown)


def test_the_restore_screen_masks_an_unreadable_vault_s_error(monkeypatch):
    """M5224: Azure's 403 on the vault cites its scope — the restore's screen says the vault by its
    name and group, never the subscription."""
    _no_env_subscription(monkeypatch)
    pending = {"key": "r", "esc": _card(action="restore_from_backup", kind="destructive_action"),
               "stage": "points", "before": "2026-11-13T07:58:00+00:00", "points": [],
               "points_error": VAULT_403, "label": "restore vm-example-01 from backup (~20 min)"}
    shown = _render(tui._restore_panel(pending))
    assert f"rsv-a (groupe {RG})" in shown, shown
    _clean(shown)


def test_the_restore_screen_masks_its_why_its_warning_and_its_error(monkeypatch):
    _no_env_subscription(monkeypatch)
    esc = _card(action="restore_from_backup", kind="destructive_action")
    moment = {"key": "r", "esc": esc, "stage": "moment", "buffer": "", "why": f"attaque de {VM}",
              "error": f"moment illisible pour {VM}", "label": "restore"}
    shown = _render(tui._restore_panel(moment))
    assert f"attaque de vm-example-01 (groupe {RG})" in shown, shown
    _clean(shown)
    points = {"key": "r", "esc": esc, "stage": "points", "before": "2026-11-13T07:58:00+00:00",
              "points": [{"time": "2026-11-13T06:00:00+00:00"}], "warning": f"après l'isolation de {VM}",
              "label": "restore"}
    shown = _render(tui._restore_panel(points))
    assert "2026-11-13T06:00:00+00:00" in shown and "← restored" in shown, shown
    _clean(shown)


def test_the_restore_s_label_and_what_it_said_are_masked(monkeypatch):
    _no_env_subscription(monkeypatch)
    esc = _card(rid=f"/subscriptions/{SUB}", action="restore_from_backup", kind="destructive_action")
    import glorfindel.restore_plan as restore_plan
    monkeypatch.setattr(restore_plan, "proposed_moment", lambda rid, e: {"before": "", "why": ""})
    assert SUB not in tui._restore_pending(esc)["label"]
    monkeypatch.setattr(escalations, "pending", lambda: [])
    monkeypatch.setattr(tui, "_last_restore", {"rid": VM, "ok": False,
                                               "text": f"✗ restore refused: {VAULT_403}"})
    shown = _render(tui._escalations_renderable(datetime.now(timezone.utc), None, False))
    assert f"rsv-a (groupe {RG})" in shown, shown
    _clean(shown)


def test_the_confirmation_s_label_says_the_resource_masked(monkeypatch):
    """The keys' confirmation (ack, release, unblock, reset): the resource said masked."""
    _no_env_subscription(monkeypatch)
    card = _card(rid=f"/subscriptions/{SUB}")
    for key in "axuv":
        pending = tui._confirmation(key, card)
        assert pending["key"] == key and pending["esc"] is card
        shown = _tui_shown(monkeypatch, [card]) and _render(
            tui._escalations_renderable(datetime.now(timezone.utc), pending, False))
        assert "<abonnement>" in shown, shown
        _clean(shown)
    assert tui._confirmation("a", card)["label"] == "ack [c0ffee01] on <abonnement>"
    assert tui._confirmation("x", _card())["label"] == "release vm-example-01 (isolation only)"
    assert tui._confirmation("x", _card(kind="low_confidence")) is None      # the keys that act (SEC5)
    assert tui._confirmation("r", card) is None


def test_the_resources_panel_masks_a_resource_s_name(monkeypatch):
    _no_env_subscription(monkeypatch)
    import glorfindel.actions as actions
    monkeypatch.setattr(actions, "active_isolations", lambda: [{"resource_id": f"/subscriptions/{SUB}"}])
    monkeypatch.setattr(actions, "active_blocks", lambda: [{"resource_id": VM, "ip": "203.0.113.7"}])
    shown = _render(tui._resources_renderable(datetime.now(timezone.utc)))
    assert "<abonnement>" in shown and "vm-example-01" in shown and "203.0.113.7" in shown, shown
    _clean(shown)


def test_the_feed_masks_a_signal_s_and_a_cycle_s_words(monkeypatch):
    """A signal's resource (a subscription's own id) and its TTP, a cycle's action and TTP."""
    _no_env_subscription(monkeypatch)
    from rich.text import Text
    signal = {"timestamp": "2026-11-13T08:00:00+00:00", "event": "detection", "ttp": f"T1078 {SUB}",
              "resource_id": f"/subscriptions/{SUB}"}
    cycle = {"timestamp": "2026-11-13T08:00:01+00:00", "action": f"lock {NSG}", "confidence": 0.5,
             "signal": {"ttp": f"T1078 {SUB}", "resource_id": VM}, "outcome": {}}
    shown = _render(Text.from_markup(tui._format_signal(signal)))
    assert "<abonnement>" in shown, shown
    _clean(shown)
    shown = _render(Text.from_markup(tui._format_debug(cycle)))
    assert "nsg-a (groupe" in shown, shown
    _clean(shown)
