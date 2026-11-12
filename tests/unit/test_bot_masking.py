"""MSK3 (#772) — no subscription's id in what the Discord bot or the webhook posts, as the CLI (MSK2).

A message of the bot or of the webhook is posted in a channel, from which an operator pastes it in an
issue of the public repository. Every path the bot renders, and the webhook's (its fallback when the
bot is mute, the escalations and announcements without a bot), says an ARM id by its name and group
and a subscription's id « <abonnement> » (glorfindel/masking.py):

1. the commands to copy (📋 Command): the VM by the CLI's rule (`_name_for_a_command`) — its short
   name, or « <id: glorfindel list --ids> », never a homonym;
2. the card's embed: the model's explanation, the reason, the steps, the target, the evidence, an
   identity plan (a command shown whole or held, never altered), the footer; the thread's name and
   /pending;
3. what a button says it ran, its output and its error, a restore's confirmation and its form;
4. the notices in the VM's thread and the webhook's messages.

What keeps the id: the buttons' arguments (they act), the escalations' and the notices' stores.

No Azure call, no model call, no Discord call: discord.py's objects are built, never connected.
Every identifier is made up (repository public). Mutants M5020–M5029 (scripts/mutants/MSK3.py).
"""
from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace

import pytest

pytest.importorskip("discord")

from glorfindel import bot, escalations, vm_notices  # noqa: E402

SUB = "00000000-0000-0000-0000-0000000000cc"
SUB2 = "00000000-0000-0000-0000-0000000000dd"
RG, RG_B = "rg-example-a", "rg-example-b"


def _vm(name: str = "vm-example-01", rg: str = RG, sub: str = SUB) -> str:
    return f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"


VM = _vm()
VM_B = _vm(rg=RG_B)                                     # the same name, another group
NSG = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/networkSecurityGroups/nsg-a"
FORBIDDEN = (f"(AuthorizationFailed) The client 'agent' does not have authorization to perform action "
             f"'Microsoft.Network/networkSecurityGroups/write' over scope '{NSG}' or the scope is invalid.")
HOOK = "https://hooks.example.invalid/services/T0/B0/x"
DISCORD_HOOK = "https://discord.com/api/webhooks/1/token-example"


def _clean(text) -> None:
    flat = "".join(str(text).split()).lower()
    assert SUB not in flat and SUB2 not in flat, text
    assert "subscriptions/" not in flat and "subscriptions%2f" not in flat, text


def _known(monkeypatch, *rids) -> None:
    """The discovery knows these VMs (no state of isolation or block: the suite's HOME is empty)."""
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry",
                        lambda: SimpleNamespace(all=lambda: [SimpleNamespace(resource_id=r) for r in rids]))


def _card(**kw) -> dict:
    explanation = f"La VM {VM} chiffre ses disques (abonnement {SUB})."
    card = {"id": "abcdef12-0000-4000-8000-000000000001", "resource_id": VM, "action": "isolate_vm",
            "escalation_type": "low_confidence", "status": "pending",
            "explanation": explanation, "reason": f"{explanation} Mode human_only : {FORBIDDEN}",
            "suggested_steps": [f"glorfindel restore {VM} --yes", f"az vm show --ids {VM}", FORBIDDEN],
            "run_id": f"watch-rule-{SUB}", "ttp": "T1486", "severity": "critical", "confidence": 0.9,
            "rule_name": "ransomware-disk-write", "first_seen": "2026-11-12T08:00:00+00:00",
            "timestamp": "2026-11-12T08:00:00+00:00"}
    card.update(kw)
    return card


def _embed_text(card: dict) -> str:
    async def build():
        return bot._build_embed(card)
    embed = asyncio.run(build())
    return "\n".join([embed.title or "", embed.description or "", embed.footer.text or "",
                      *(f"{f.name}: {f.value}" for f in embed.fields)])


# ── 1. The commands to copy ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("kw,said", [
    ({"action": "restore_from_backup", "escalation_type": "destructive_action"},
     "glorfindel restore vm-example-01 --yes --before 2026-11-12T08:00:00+00:00"),
    ({"escalation_type": "verification_failed"}, "glorfindel revert vm-example-01 --yes"),
    ({"escalation_type": "readiness_hold"}, "glorfindel activate vm-example-01"),
    ({"escalation_type": escalations.EXECUTED_TYPE}, "glorfindel release vm-example-01 --yes"),
    ({"escalation_type": escalations.EXECUTED_TYPE, "action": "block_suspicious_ip",
      "action_params": {"ip": "203.0.113.7"}}, "glorfindel unblock 203.0.113.7 vm-example-01 --yes"),
])
def test_the_command_to_copy_names_the_vm_by_its_name(monkeypatch, kw, said):
    _known(monkeypatch, VM)
    command = bot._cli_command(_card(**kw))
    assert said in command
    _clean(command)


@pytest.mark.parametrize("known", [(VM, VM_B), (VM_B,)])
def test_the_command_never_names_a_homonym(monkeypatch, known):
    """Two VMs of that name, or the card's VM no longer known while another of its name is: the short
    name would be refused, or take the other one — the command asks for the id, and shows none."""
    _known(monkeypatch, *known)
    for kw in ({"action": "restore_from_backup", "escalation_type": "destructive_action"},
               {"escalation_type": "verification_failed"},
               {"escalation_type": escalations.EXECUTED_TYPE}):
        command = bot._cli_command(_card(**kw))
        assert "<id: glorfindel list --ids>" in command and "vm-example-01 " not in command, command
        _clean(command)


def test_the_buttons_keep_the_full_id(monkeypatch):
    """A button acts: its arguments keep the full id — what it says it ran shows none."""
    from glorfindel import restore_plan
    _known(monkeypatch, VM)
    button = bot._make_action_button(_card(escalation_type="verification_failed"))
    assert button.cli_args == ["revert", VM, "--yes"]
    assert bot._args_said(button.cli_args) == "revert vm-example-01 --yes"
    args = restore_plan.restore_args(VM, "2026-11-12T08:00:00+00:00")
    assert VM in args
    _clean(bot._args_said(args))


# ── 2. The card ───────────────────────────────────────────────────────────────────────

def test_the_card_shows_no_subscription_and_the_store_keeps_it(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", SUB2)
    card = _card(explanation=f"Vu depuis l'abonnement de la watch ({SUB2}) : {VM}.",
                 target={"kind": "nsg", "id": NSG, "name": "nsg-a", "via": f"règle {NSG}/securityRules/r1",
                         "vm_names": ["vm-example-01"], "limit": f"La portée {VM} n'est pas lue."})
    kept = copy.deepcopy(card)
    text = _embed_text(card)
    _clean(text)
    assert "vm-example-01 \\(groupe rg-example-a\\)" in text        # said by its name and group (escaped)
    assert card == kept                                             # a copy masked, never the card
    esc_id = escalations.record("sig-1", VM, "isolate_vm", "low_confidence", card["reason"],
                                run_id=card["run_id"], suggested_steps=card["suggested_steps"],
                                explanation=card["explanation"])
    stored = next(e for e in escalations.all_escalations() if e["id"] == esc_id)
    assert stored["resource_id"] == VM and VM in stored["reason"] and VM in stored["suggested_steps"][0]
    _clean(_embed_text(stored))


def test_an_executed_card_s_evidence_names_no_subscription(monkeypatch):
    card = _card(escalation_type=escalations.EXECUTED_TYPE, executed={
        "mode": "non_disruptive", "evidence": [f"_ResourceId: {VM}", "MaxWrite: 147000000"],
        "verification": {"verified": True, "method": "rules", "nsg": NSG}})
    text = _embed_text(card)
    _clean(text)
    assert "MaxWrite: 147000000" in text


def test_an_identity_plan_s_command_is_shown_whole_or_held():
    """A command of the plan is shown as written, or not at all: masked, it would be no command."""
    graph = "az rest --method POST --url https://graph.microsoft.com/v1.0/users/<id-utilisateur>/revokeSignInSessions"
    arm = f"az role assignment delete --ids {VM}/providers/Microsoft.Authorization/roleAssignments/ra-1"
    plan = {"confirm": f"Confirmer la portée {VM}", "items": [
        {"n": 1, "what": f"Révoquer les sessions (vu sur {VM})", "command": graph},
        {"n": 2, "what": "Retirer l'attribution", "command": arm, "find": f"az role assignment list --scope {VM}"}]}
    card = _card(escalation_type="identity_change", identity_plan=plan, resource_id="entra:user:u-1",
                 target={"kind": "identity", "name": "user-example", "identity_type": "Utilisateur"})
    text = _embed_text(card)
    _clean(text)
    assert graph.replace("<", "\\<").replace(">", "\\>") in text or graph in text
    assert bot._COMMAND_HELD in text


def test_a_card_filed_on_a_subscription_names_no_id(monkeypatch):
    rid = f"/subscriptions/{SUB}"
    assert bot._thread_name(rid) == "<abonnement>"
    _clean(bot._target_fields({"resource_id": rid}))
    assert bot._thread_name(NSG) == "nsg-a"                          # a resource: its short name, as before

    sent = []

    class _Response:
        async def send_message(self, text, ephemeral=False):
            sent.append(text)

    interaction = SimpleNamespace(user=SimpleNamespace(id=1, roles=()), response=_Response(),
                                  client=SimpleNamespace(button_policy=bot.ButtonPolicy(frozenset({1}))))
    monkeypatch.setattr(bot.esc_module, "pending", lambda: [_card(resource_id=rid), _card()])
    asyncio.run(bot._pending_reply(interaction))
    _clean(sent[0])
    assert "vm-example-01" in sent[0]


# ── 3. What a button runs ─────────────────────────────────────────────────────────────

class _Channel:
    def __init__(self):
        self.posted: list[str] = []

    async def send(self, text="", **kw):
        self.posted.append(text)


def _settled(monkeypatch):
    monkeypatch.setattr(bot.esc_module, "resolve", lambda esc_id: None)
    monkeypatch.setattr(bot.esc_module, "pending", lambda: [])


@pytest.mark.parametrize("ran", ["output", "error"])
def test_what_a_button_ran_is_said_without_the_subscription(monkeypatch, ran):
    _known(monkeypatch, VM)
    _settled(monkeypatch)
    called = []

    def run_cli(args):
        called.append(args)
        if ran == "error":
            raise RuntimeError(FORBIDDEN)
        return 0, f"✓ Reset {VM}\n{FORBIDDEN}"
    monkeypatch.setattr(bot, "_run_cli", run_cli)
    channel = _Channel()

    class _Message:
        async def edit(self, **kw):
            pass

    async def click():
        view = bot.EscalationView(_card(escalation_type="verification_failed"))
        button = next(i for i in view.children if isinstance(i, bot._ExecuteButton))

        async def defer():
            pass
        interaction = SimpleNamespace(response=SimpleNamespace(defer=defer), message=_Message(),
                                      channel=channel, user=SimpleNamespace(display_name="operator"))
        await button.callback(interaction)
        await asyncio.gather(*[t for t in asyncio.all_tasks() if t is not asyncio.current_task()])
    asyncio.run(click())
    assert called == [["revert", VM, "--yes"]]                      # the button acts on the full id
    assert "glorfindel revert vm-example-01 --yes" in channel.posted[0]
    for text in channel.posted:
        _clean(text)


def test_a_restore_s_confirmation_names_no_subscription(monkeypatch):
    _known(monkeypatch, VM)
    _settled(monkeypatch)
    before = "2026-11-12T07:55:00+00:00"
    plan = {"before": before, "why": f"début de l'exercice sur {VM}", "source": "exercise"}
    text = bot._points_text(_card(), before, plan, [], unread=f"HttpResponseError: {FORBIDDEN}")
    _clean(text)
    assert "vm-example-01" in text

    async def form():
        return bot._RestoreModal(_card(), plan)
    modal = asyncio.run(form())
    _clean(getattr(modal.field, "description", "") or "")

    ran, channel = [], _Channel()
    monkeypatch.setattr(bot, "_run_cli", lambda args: (ran.append(args), (0, f"restore of {VM} started"))[1])

    async def edit_message(**kw):
        pass

    async def confirm():
        view = bot._RestoreConfirmView(_card(), before)
        interaction = SimpleNamespace(response=SimpleNamespace(edit_message=edit_message), channel=channel,
                                      user=SimpleNamespace(display_name="operator"))
        await view.confirm.callback(interaction)
        await asyncio.gather(*[t for t in asyncio.all_tasks() if t is not asyncio.current_task()])
    asyncio.run(confirm())
    assert ran and VM in ran[0]                                     # the restore runs on the full id
    assert "glorfindel restore vm-example-01 --yes --before" in channel.posted[0]
    for posted in channel.posted:
        _clean(posted)


# ── 4. The notices and the webhook ────────────────────────────────────────────────────

def _notice(**kw) -> dict:
    n = {"key": "k-1", "resource_id": VM, "kind": vm_notices.CLOSURE_KIND, "level": "failed",
         "title": f"Coupure des sessions de {VM}",
         "text": f"Sur {VM} — refusée : {FORBIDDEN} (abonnement {SUB})", "at": "2026-11-12T08:00:00+00:00"}
    n.update(kw)
    return n


def test_a_notice_is_said_without_the_subscription_and_kept_whole():
    _clean(vm_notices.bot_message(_notice()))
    _clean(vm_notices.webhook_payload(_notice())["text"])
    assert "vm-example-01" in vm_notices.bot_message(_notice())
    assert "<abonnement>" in vm_notices.bot_message(_notice(resource_id=f"/subscriptions/{SUB}"))
    assert vm_notices.say(VM, "k-2", vm_notices.CLOSURE_KIND, "Coupure", f"Sur {VM}") == "none"
    assert vm_notices.said("k-2")["text"] == f"Sur {VM}"            # the store keeps the text


@pytest.mark.parametrize("url", [HOOK, DISCORD_HOOK])
def test_the_fallback_says_no_subscription(monkeypatch, url):
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", url)
    monkeypatch.setenv("DISCORD_PING_ROLE", "42")
    for kind in (vm_notices.CLOSURE_KIND, vm_notices.ACTION_KIND):
        payload, _key, _url = vm_notices.fallback(_notice(kind=kind, relayed={"ping": True}))
        _clean(payload)


@pytest.fixture
def posts(monkeypatch):
    """The webhook set, the bot not: every POST caught, none sent."""
    import requests
    for k in ("GLORFINDEL_DISCORD_BOT", "DISCORD_BOT_TOKEN", "DISCORD_CHANNEL_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("GLORFINDEL_WEBHOOK_URL", HOOK)
    sent: list[dict] = []
    monkeypatch.setattr(requests, "post", lambda url, json=None, timeout=None: sent.append({"url": url, **json}))
    return sent


def test_an_escalation_by_the_webhook_says_no_subscription(posts):
    escalations._notify(_card())
    escalations._notify(_card(resource_id=f"/subscriptions/{SUB}"))
    assert len(posts) == 2
    _clean(posts)
    assert "vm-example-01" in posts[0]["text"]


def test_an_action_s_announcement_by_the_webhook_says_no_subscription(posts):
    via = escalations.notify_action("isolate_vm", VM, f"watch-rule-{SUB}", 0.93,
                                    f"Écritures massives sur {VM} : {FORBIDDEN}", True,
                                    note=f"DNS d'Azure ouvert ({SUB})", key="action:k-3", card="card-1")
    assert via == "webhook" and posts
    _clean(posts)
    assert VM in vm_notices.said("action:k-3")["text"]              # the store keeps the text
