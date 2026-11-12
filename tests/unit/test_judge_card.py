"""JUG1 (#760): a disruptive action Glorfindel takes alone makes a card to judge, and everything is
said in the VM's thread when the bot is configured.

On the bench, 12/11, gondolin's autonomous isolation (the T1486, `non_disruptive`) was verified and
left no card: TO JUDGE stayed empty, the indicator of the disruptive actions taken wrongly could not
count it, and its announcement went by the webhook into the channel — the bot's cards, and the
closure of the session cut (DRN2), in the VM's thread. Now:

- an `isolate_vm` or a `block_suspicious_ip` run alone and verified makes one card « exécutée »
  (`autonomous_action`): the action, the VM, the evidence, the check, the mode; it enters TO JUDGE,
  is judged like any other and counts among the disruptive actions — one per action, after a
  restart too; a snapshot or a release makes none; nothing to approve on it;
- its announcement goes in the VM's thread when the bot is configured (`vm_notices.say`, posted by
  the bot), by the webhook otherwise, as before — never both, and the card's own notification
  stays quiet: one message in the channel without the bot, none with it.

The cycles go through the real graph, on the in-memory Azure (tests/unit/fake_azure.py: the NSG
written and read back), the model patched, a fake webhook (`requests.post` caught) and a fake
Discord thread: no cloud call, no model call, nothing sent.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from glorfindel import config, escalations, readiness, vm_notices
from glorfindel.actions import AzureConnector
from glorfindel.config import AutonomyConfig
from glorfindel.providers.azure import run_command

from .fake_azure import FakeAzure, vm_id

WEB = vm_id("rg-app1", "web")
HOOK = "https://hooks.example.invalid/eregion"
ATTACKER = "203.0.113.9"


# ── set-up ─────────────────────────────────────────────────────────────────────────────────────

class FakeMemory:
    def __init__(self, path=None, **_) -> None:
        self.stored: list[dict] = []

    def retrieve_similar(self, signal, n=3):
        return []

    def store(self, cycle):
        self.stored.append(cycle)


class LogAnalytics:
    def run_query(self, query, timespan=None):
        return []


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    """No LLM endpoint nor operator switch; runs/ under tmp; ChromaDB replaced; no drain followed
    from another test."""
    for var in ("GLORFINDEL_LLM_BASE_URL", "GLORFINDEL_CONFIDENCE_THRESHOLD", "GLORFINDEL_LLM_TIMEOUT_S",
                "GLORFINDEL_READ_ONLY", "GLORFINDEL_DECISION_DRAWS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    import glorfindel.agent as agent
    monkeypatch.setattr(agent, "CycleMemory", FakeMemory)
    run_command._FOLLOWED.clear()
    yield
    run_command._FOLLOWED.clear()


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


@pytest.fixture
def bot_on(monkeypatch, posts):
    """The bot configured, as compose tells the watch (GLORFINDEL_DISCORD_BOT): the webhook set too."""
    monkeypatch.setenv("GLORFINDEL_DISCORD_BOT", "1")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    return posts


@pytest.fixture
def azure(tmp_path, monkeypatch):
    """web on its own NSG, isolation by rules, its session cut ended at once; the real connector."""
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    cfg = tmp_path / "glorfindel-config.yaml"
    cfg.write_text("isolation:\n  quarantine_nsg: false\n")
    monkeypatch.setattr(config, "_DEFAULT_PATHS", [cfg])
    f = FakeAzure()
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", None)
    nsg = f.add_nsg("rg-app1", "nsg-web")
    f.add_vm("rg-app1", "web", [{"rg": "rg-app1", "name": "web-nic", "ips": ["10.0.0.4"],
                                 "subnet": subnet, "nsg": nsg}])
    c = AzureConnector(dry_run=False, read_only=False)
    c._network, c._compute = f.network, f.compute
    c._subscription_id = "s"
    c.recent_changes = lambda *a, **k: []
    readiness.record_assessment(readiness._verdict("web", []), WEB)
    return f, c


def _llm(action: str, confidence: float = 0.95, explanation: str = ""):
    call = MagicMock()
    call.function.arguments = json.dumps({
        "reasoning": f"Threat confirmed — {action}.", "confidence": confidence, "action": action,
        "reversible": True, "explanation": explanation or f"{action} recommended.", "escalate": False,
        "escalation_reason": "", "suggested_steps": []})
    resp = MagicMock()
    resp.choices[0].message.tool_calls = [call]
    resp.usage = None
    return resp


def _ransomware(signal_id: str = "rule-ransomware-disk-write-0000j1j1") -> dict:
    return {
        "signal_id": signal_id, "event": "detection", "ttp": "T1486", "severity": "high",
        "resource_id": WEB, "resource_type": "vm", "timestamp": "2026-11-12T09:16:00+00:00",
        "context": {"workspace_id": "ws-j1", "rule_name": "ransomware-disk-write",
                    "run_id": "watch-ransomware-disk-write-20261112T091600Z", "attribution": "asset"},
        "raw_signal": {"first_result_row": {"Computer": "web", "_ResourceId": WEB, "MaxWrite": 147000000}},
    }


def _scanner(signal_id: str = "rule-ssh-brute-force-0000j1j2") -> dict:
    return {
        "signal_id": signal_id, "event": "detection", "ttp": "T1110.001", "severity": "medium",
        "resource_id": WEB, "resource_type": "vm", "timestamp": "2026-11-12T09:16:00+00:00",
        "context": {"workspace_id": "ws-j1", "rule_name": "ssh-brute-force", "suspicious_ip": ATTACKER,
                    "run_id": "watch-ssh-brute-force-20261112T091600Z", "attribution": "asset"},
        "raw_signal": {"first_result_row": {"Computer": "web", "SourceIP": ATTACKER, "FailedAttempts": 40}},
    }


def _respond(c, signal, action: str, *, mode: str = "non_disruptive", explanation: str = ""):
    from glorfindel.agent import GlorfindelAgent
    agent = GlorfindelAgent(connector=c, memory_path="unused", incidents_path="incidents.jsonl",
                            model="anthropic/claude-test", dry_run=False, autonomy=AutonomyConfig(default=mode),
                            readiness_gate=lambda vm, rid, configured: (configured, {}))
    with patch("litellm.completion", return_value=_llm(action, explanation=explanation)), \
            patch("glorfindel.detectors.detector_for", return_value=LogAnalytics()):
        return agent.respond(signal)


def _cards(kind: str = escalations.EXECUTED_TYPE) -> list[dict]:
    return [e for e in escalations.all_escalations() if e.get("escalation_type") == kind]


def _announcements() -> list[dict]:
    return [n for n in vm_notices._read() if n["kind"] == escalations.EXECUTED_TYPE]


def _robot(sent: list[dict]) -> list[str]:
    """What the webhook carried of the autonomous actions (`:robot_face:`)."""
    return [p["text"] for p in sent if p["text"].startswith(":robot_face:")]


# ── the card to judge ──────────────────────────────────────────────────────────────────────────

def test_an_autonomous_isolation_verified_makes_one_card_to_judge(azure, posts):
    """The bench of 12/11: gondolin isolated alone, verified — and no card. Now its card says the
    action, the VM, the evidence, the check and the mode; TO JUDGE lists it; the report counts it."""
    f, c = azure
    final = _respond(c, _ransomware(), "isolate_vm", explanation="Écritures disque 147 Mo/s, chiffrement probable.")
    assert final["outcome"]["executed"] is True and final["outcome"]["verified"] is True
    assert not final["escalate"]
    [card] = _cards()
    assert (card["action"], card["resource_id"], card["status"]) == ("isolate_vm", WEB, "pending")
    assert card["explanation"] == "Écritures disque 147 Mo/s, chiffrement probable."
    assert card["rule_name"] == "ransomware-disk-write" and card["ttp"] == "T1486"
    x = card["executed"]
    assert x["mode"] == "non_disruptive" and x["action"] == "isolate_vm"
    assert x["verification"]["verified"] is True and x["verification"]["method"]
    assert x["verification"]["verified_at"] == final["outcome"]["verified_at"]
    assert "MaxWrite: 147000000" in x["evidence"]
    assert "mode non_disruptive" in card["reason"] and "vérifiée sur Azure" in card["reason"]
    assert "glorfindel release web --yes" in card["suggested_steps"][0]
    # Nothing else: no escalation — the action ran and held.
    assert [e["escalation_type"] for e in escalations.pending()] == [escalations.EXECUTED_TYPE]
    [judge] = escalations.to_judge()
    assert judge["id"] == card["id"] and judge["executed"] == x
    report = escalations.observation_report()
    assert report["disruptive"]["unjudged"] == 1 and report["by_action"]["isolate_vm"]["unjudged"] == 1


def test_its_verdict_counts_among_the_disruptive_actions_taken_wrongly(azure, posts):
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    escalations.set_verdict(card["id"], "wrong", "la sauvegarde de la nuit")
    report = escalations.observation_report()
    assert report["disruptive"]["wrong"] == 1 and report["disruptive"]["false_rate"] == 1.0
    assert escalations.to_judge() == []                                 # judged: out of the list


def test_an_autonomous_block_verified_makes_its_card_with_its_address(azure, posts):
    f, c = azure
    final = _respond(c, _scanner(), "block_suspicious_ip")
    assert final["outcome"]["executed"] is True and final["outcome"]["verified"] is True
    [card] = _cards()
    assert card["action"] == "block_suspicious_ip" and card["action_params"]["ip"] == ATTACKER
    assert card["executed"]["ip"] == ATTACKER and f"({ATTACKER})" in card["reason"]
    assert f"glorfindel unblock {ATTACKER} web --yes" in card["suggested_steps"][0]
    assert escalations.observation_report()["disruptive"]["unjudged"] == 1


def test_the_card_is_one_per_action_even_after_a_restart(azure, posts):
    """The same cycle stored again — the watch restarted, a cycle replayed — writes no second
    card, nor a second announcement, the card judged and acknowledged since or not."""
    from glorfindel.agent import store_cycle
    f, c = azure
    final = _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    store_cycle(final, memory=FakeMemory())
    assert len(_cards()) == 1 and len(_robot(posts)) == 1
    escalations.set_verdict(card["id"], "right", "")
    escalations.resolve(card["id"])
    store_cycle(final, memory=FakeMemory())
    assert [e["id"] for e in _cards()] == [card["id"]] and len(_robot(posts)) == 1


def test_two_actions_are_two_cards_each_judged_on_its_own(azure, posts):
    """A second isolation of the same VM, another detection, the first card still pending: its own
    card — never folded into the first (« pour chaque action »): each is judged and counted."""
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [first] = _cards()
    _respond(c, _ransomware("rule-ransomware-disk-write-0000j1j3"), "isolate_vm")
    assert len(_cards()) == 2 and len(escalations.to_judge()) == 2
    escalations.set_verdict(first["id"], "right", "")
    assert [c["id"] for c in escalations.to_judge()] != [first["id"]] and len(escalations.to_judge()) == 1
    assert escalations.observation_report()["disruptive"] == {"right": 1, "wrong": 0, "unsure": 0,
                                                              "unjudged": 1, "false_rate": 0.0}


def test_a_snapshot_or_a_release_makes_no_card(azure, posts, monkeypatch):
    """Not disruptive: announced as before, never a card to judge."""
    from glorfindel.agent import store_cycle
    state = {"signal": _ransomware(), "reasoning": "", "confidence": 0.9, "escalate": False,
             "past_cycles": [], "autonomy_mode": "non_disruptive", "dry_run": False}
    store_cycle({**state, "action": "snapshot",
                 "outcome": {"executed": True, "status": "ok", "snapshot_id": "s1", "verified": None}},
                memory=FakeMemory())
    store_cycle({**state, "signal": _ransomware("rule-x-0000j1j4"), "action": "release_isolation",
                 "outcome": {"executed": True, "status": "released", "verified": True}}, memory=FakeMemory())
    assert _cards() == [] and len(_robot(posts)) == 2


def test_an_action_held_by_the_mode_makes_its_held_card_only(azure, posts):
    f, c = azure
    final = _respond(c, _ransomware(), "isolate_vm", mode="human_only")
    assert final["outcome"].get("executed") is not True
    assert _cards() == [] and [e["escalation_type"] for e in escalations.pending()] == ["mode_hold"]
    assert _robot(posts) == []


def test_an_action_whose_check_fails_makes_no_card_of_an_action_held(azure, posts, monkeypatch):
    """Verified false: its card is `verification_failed`, to revert — never a card « exécutée »."""
    f, c = azure
    monkeypatch.setattr(c, "verify_isolation", lambda rid: {"verified": False, "method": "nsg_check",
                                                            "error": "allow-ssh passe avant le deny"})
    _respond(c, _ransomware(), "isolate_vm")
    assert _cards() == [] and [e["escalation_type"] for e in escalations.pending()] == ["verification_failed"]
    assert _robot(posts) == []


def test_a_card_refused_never_stops_the_announcement(azure, posts, monkeypatch):
    """A full disk on the cards' store: said on the console, the announcement still goes."""
    f, c = azure

    def full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(escalations, "_write_lines", full)
    final = _respond(c, _ransomware(), "isolate_vm")
    assert final["outcome"]["verified"] is True and len(_robot(posts)) == 1
    assert "Carte à juger" not in _robot(posts)[0]


# ── nothing to approve on it ───────────────────────────────────────────────────────────────────

def test_the_card_changes_nothing_of_the_action_nor_of_the_autonomy(azure, posts):
    """No one-click execute (the console, the queue), no proposal signed, no button that undoes:
    a judgement after the fact."""
    from eregion_core import action_queue
    from glorfindel.approval import approval_refusal
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    assert escalations.EXECUTED_TYPE not in action_queue.APPROVABLE_TYPES
    assert not action_queue.proposable(card) and "proposal" not in card
    assert "ne s'exécute pas en un clic" in approval_refusal(card, "web")


def test_the_bot_card_says_it_ran_and_offers_only_its_verdict(azure, posts):
    pytest.importorskip("discord")
    from glorfindel import bot
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()

    async def build():
        return bot._build_embed(card), bot.EscalationView(card)
    embed, view = asyncio.run(build())
    assert embed.title == "✅ VM isolée du réseau — exécutée seule, à juger"
    fields = {fl.name: fl.value for fl in embed.fields}
    assert "Pourquoi rien n'est exécuté" not in fields
    assert fields["Mode"] == "`non_disruptive`" and "vérifiée" in fields["Vérification"]
    assert "MaxWrite: 147000000" in fields["Preuves"]
    assert bot._make_action_button(card) is None                       # no execute, no revert
    labels = [getattr(i, "label", "") for i in view.children]
    assert "✓ Right" in labels and not any("Revert" in str(x) or "Restore" in str(x) for x in labels)
    assert "glorfindel release web --yes" in bot._cli_command(card)


# ── where it is said: the VM's thread with the bot, the webhook without ────────────────────────

def test_without_the_bot_the_webhook_says_it_once_as_before(azure, posts):
    """One message in the channel: the announcement, its card named — the card's own notification
    quiet (it would say the same twice)."""
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    [text] = _robot(posts)
    assert text.startswith(":robot_face: *VM isolée du réseau* ✓  |  `web`")
    assert f"Carte à juger : {card['id'][:8]}" in text and "mode non_disruptive" in text
    assert [p for p in posts if p["text"].startswith(":rotating_light:")] == []
    [n] = _announcements()
    assert n["via"] == "webhook" and n["detail"]["card"] == card["id"]


def test_with_the_bot_everything_is_in_the_vm_s_thread_and_the_channel_stays_quiet(azure, bot_on):
    """The bench of 12/11: « aucun fil Discord pour gondolin (les deux messages, isolement et levée,
    sont dans le salon) ». With the bot: nothing by the webhook; the card and the announcement
    posted by the bot in the VM's thread, once, after its restart too."""
    pytest.importorskip("discord")
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    assert bot_on == []                                                 # nothing in the channel
    [card] = _cards()
    [n] = vm_notices.for_bot()
    assert n["kind"] == escalations.EXECUTED_TYPE and n["via"] == "bot" and n["detail"]["card"] == card["id"]

    threads: dict = {}
    b = _bot(threads)

    async def turn(b):
        await b._post_escalation(None, card)
        return await b._post_notices(None)
    assert asyncio.run(turn(b)) == 1
    assert list(threads) == [WEB.lower()]                               # one thread, the VM's
    embed_msg, notice_msg = threads[WEB.lower()].sent
    assert embed_msg["embed"].title.startswith("✅ VM isolée du réseau")
    assert notice_msg["content"].startswith("✅ **VM isolée du réseau ✓** · `web`")
    assert f"Carte à juger : {card['id'][:8]}" in notice_msg["content"]
    again = _bot(threads)                                               # the bot restarted
    assert asyncio.run(again._post_notices(None)) == 0


# ── the role pinged: once per action, by its card (Jonathan, 12/11) ───────────────────────────

ROLE = 4242


class _Thread:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, content=None, **kw):
        self.sent.append({"content": content, **kw})
        return MagicMock(id=len(self.sent))


def _bot(threads: dict):
    """The bot, its threads in `threads` (by lowercased resource id): one opened as the real one is —
    the « Incident opened » ping sent at its creation when `ping` asks for it, never after."""
    pytest.importorskip("discord")
    from glorfindel import bot
    b = bot.GlorfindelBot(channel_id=1, ping_role=ROLE)

    async def thread(channel, rid, ping=True):
        if rid.lower() not in threads:
            threads[rid.lower()] = _Thread()
            if ping and b.ping_role:
                await threads[rid.lower()].send(f"<@&{b.ping_role}> Incident opened on `x`",
                                                allowed_mentions=b._role_mentions())
        return threads[rid.lower()]
    b._get_or_create_thread = thread
    return b


def _pings(threads: dict) -> list[dict]:
    return [m for t in threads.values() for m in t.sent if f"<@&{ROLE}>" in str(m.get("content") or "")]


def test_the_card_of_an_action_taken_alone_pings_the_role_in_a_thread_already_open(azure, bot_on):
    """The VM's thread exists (an earlier incident): the card pings the role in it, the role alone."""
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    threads: dict = {WEB.lower(): _Thread()}
    b = _bot(threads)
    asyncio.run(b._post_escalation(None, card))
    [ping] = _pings(threads)
    assert ping["content"] == f"<@&{ROLE}>" and ping["embed"].title.startswith("✅ VM isolée du réseau")
    mentions = ping["allowed_mentions"]
    assert mentions.everyone is False and mentions.users is False and mentions.replied_user is False
    assert [r.id for r in mentions.roles] == [ROLE]


def test_one_ping_per_action_whichever_the_bot_reads_first_and_after_its_restart(azure, bot_on):
    """The race of the card and its notice (the notice read first opens the thread), then a restart:
    the role is pinged once — by the card; the announcement pings nothing."""
    from glorfindel import bot as bot_module
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    [card] = _cards()
    threads: dict = {}
    b = _bot(threads)
    assert asyncio.run(b._post_notices(None)) == 1                       # the notice first: a new thread
    assert _pings(threads) == []
    asyncio.run(b._post_escalation(None, card))
    bot_module._save_posted({card["id"]})                                # as the watch loop keeps it
    again = _bot(threads)                                                # restarted
    assert card["id"] in again._posted and asyncio.run(again._post_notices(None)) == 0
    assert len(_pings(threads)) == 1
    threads.clear()
    other = _bot(threads)                                                # the card first, a new thread
    asyncio.run(other._post_escalation(None, card))
    assert len(_pings(threads)) == 1


def test_a_card_of_another_type_pings_as_before(azure, bot_on):
    """A held isolation (`mode_hold`): the role pinged when its post opens the thread, its message
    mentioning no one — as before JUG1; in a thread already open, no ping."""
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm", mode="human_only")
    [held] = escalations.pending()
    threads: dict = {}
    asyncio.run(_bot(threads)._post_escalation(None, held))
    [opened, msg] = threads[WEB.lower()].sent
    assert "Incident opened" in opened["content"] and msg["content"] is None and "allowed_mentions" not in msg
    threads[WEB.lower()].sent.clear()
    asyncio.run(_bot(threads)._post_escalation(None, held))
    assert _pings(threads) == []


def test_a_forged_notice_silences_an_announcement_never_the_card(azure, posts):
    """The notices' store is written by the console and the bot too (DRN2): a notice forged under
    the action's key takes the announcement — never the card, which decides on its own store."""
    from glorfindel.agent import _executed_key
    f, c = azure
    state = {"signal": _ransomware(), "action": "isolate_vm"}
    vm_notices.say(WEB, _executed_key(state), "autonomous_action", "rien", "rien", level="ok")
    posts.clear()
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_cards()) == 1 and _robot(posts) == []


def test_a_notice_store_that_refuses_still_announces_by_the_webhook(azure, posts, monkeypatch):
    f, c = azure

    def full(notice):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vm_notices, "_record", full)
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_robot(posts)) == 1 and len(_cards()) == 1


def test_a_notice_store_that_refuses_with_the_bot_says_nothing_in_the_channel(azure, bot_on, monkeypatch):
    """Its card written, the bot says the action in the VM's thread: nothing in the channel."""
    f, c = azure

    def full(notice):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vm_notices, "_record", full)
    _respond(c, _ransomware(), "isolate_vm")
    assert bot_on == [] and len(_cards()) == 1


def test_a_full_disk_with_the_bot_still_alerts_by_the_webhook(azure, bot_on, monkeypatch):
    """Imladris has the webhook and the bot (JUG1 review): the disk full, neither the card nor the
    notice is written, the bot has nothing to post — the webhook says the action, as before JUG1.
    An autonomous action always alerts somewhere."""
    f, c = azure

    def full(*a, **k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vm_notices, "_record", full)
    monkeypatch.setattr(escalations, "_write_lines", full)
    final = _respond(c, _ransomware(), "isolate_vm")
    assert final["outcome"]["verified"] is True and _cards() == []
    [text] = _robot(bot_on)
    assert text.startswith(":robot_face: *VM isolée du réseau* ✓") and "Carte à juger" not in text


def test_a_vm_isolated_alone_still_gives_no_moment_to_a_restore(azure, posts):
    """`glorfindel restore <vm> --yes` without --before: the card of the action is written after it
    and says nothing of when the attack began — the refusal of before (SEC4c: no card, no moment);
    a card of a detection still gives it (JUG1 review)."""
    from glorfindel import restore_plan
    from glorfindel.cli import _restore_before
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm")
    assert len(_cards()) == 1 and restore_plan.card_of(WEB) is None
    before, why = _restore_before(WEB, None)
    assert before == "" and "passer --before" in why
    held = escalations.record("rule-x-0000j1j9", WEB, "restore_from_backup", "destructive_action", "à restaurer")
    assert restore_plan.card_of(WEB)["id"] == held


# ── what reaches a chat or the console is inert ────────────────────────────────────────────────

EVIL = "@everyone [support](https://evil.example) <@&1> <!channel>"


def test_the_announcement_escapes_what_comes_from_outside(azure, bot_on):
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm", explanation=EVIL)
    [n] = vm_notices.for_bot()
    msg = vm_notices.bot_message(n)
    assert "@everyone" not in msg and "\\[support\\]\\(https://evil.example\\)" in msg and "\\<@&1\\>" in msg


def test_the_webhook_announcement_escapes_what_comes_from_outside(azure, posts):
    f, c = azure
    _respond(c, _ransomware(), "isolate_vm", explanation=EVIL)
    [text] = _robot(posts)
    assert "<!channel>" not in text and "‹!channel›" in text and "](https" not in text


def test_the_bot_card_escapes_its_evidence():
    pytest.importorskip("discord")
    from glorfindel import bot
    fields = dict((n, v) for n, v, _ in bot._executed_fields(
        {"mode": "non_disruptive", "verification": {"verified": True, "method": "nsg"},
         "evidence": [f"Computer: {EVIL}"]}, "fait"))
    assert "@everyone" not in fields["Preuves"] and "\\[support\\]" in fields["Preuves"]
