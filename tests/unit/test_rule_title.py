"""RTT1a (#1174; Jonathan, 25/11): the title of a cloud detection's card, declared by its rule.

A card of the control plane or of an identity was titled by its type alone — « Entra ID identity
change » for a mere sign-in. Held here:
  - each of the eleven shipped rules of the two families carries its title, word for word the
    issue's table, checked at load;
  - a title that cannot be read is refused: the client's entry skipped and said, the shipped rule of
    its name loading instead; the shipped base as it is, its unreadable title said;
  - a card carries `rule_title`, written with it from its rule alone — never from the signal nor the
    model; a client rule without a title, a card written before RTT1a, rules unreadable: the
    neutral title of the family;
  - a rule renamed never rewrites a card;
  - the type and its guards unchanged: `identity_change`, `control_plane_change`, wherever read;
  - Discord, the webhook, the CLI and the TUI show the title, escaped as any text (SEC6).

Placeholders, never real ids.
"""
from __future__ import annotations

import copy

import pytest
import yaml
from click.testing import CliRunner

from glorfindel import escalations, rule_layers, rule_title
from glorfindel.detection_rules import load_config, shipped_rules_path

SUB = "00000000-0000-0000-0000-0000000000bb"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Compute/virtualMachines/vm-example-01"
NSG = f"/subscriptions/{SUB}/resourceGroups/rg-example/providers/Microsoft.Network/networkSecurityGroups/nsg-example"
HOSTILE = "[Open](https://evil.example) @everyone <b>`x`</b> [red]x[/red]"

# The issue's table (#1174), word for word.
TITLES = {
    "entra-sp-unusual-signin": "Entra ID unusual sign-in",
    "entra-credential-added": "Entra ID credential added",
    "entra-app-consent": "Entra ID app consent granted",
    "entra-privileged-role-assigned": "Entra ID privileged role assigned",
    "nsg-change-outside-glorfindel": "NSG changed outside Glorfindel",
    "role-assignment-write": "Azure role assigned",
    "snapshot-by-unexpected-caller": "Snapshot or disk export by another caller",
    "restorepoint-by-unexpected-caller": "Restore point or its export by another caller",
    "run-command-by-external-caller": "Run Command by another caller",
    "run-command-by-glorfindel-outside-isolation": "Run Command as Glorfindel, outside an isolation",
    "bastion-shareable-link-created": "Bastion shareable link created",
}
FAMILY = {"azure_entra": "identity_change", "azure_activity": "control_plane_change"}
SHIPPED = {r["name"]: r for r in yaml.safe_load(shipped_rules_path().read_text())["rules"]}


def _type_of(name: str) -> str:
    return FAMILY[SHIPPED[name]["source"]]


def _client_rule(name: str, of: str = "role-assignment-write", **fields) -> dict:
    """A client rule that loads: a copy of a shipped rule of the control plane, under `name`."""
    rule = {k: v for k, v in copy.deepcopy(SHIPPED[of]).items() if k != "title"}
    return {**rule, "name": name, **fields}


def _escalate(name: str, signal_extra: dict | None = None) -> dict:
    """A cloud detection's card as the graph writes it (`escalate_to_human`), from a signal of the
    RulePoller that names its rule. Returns the card written."""
    from glorfindel import agent
    identity = _type_of(name) == "identity_change" if name in SHIPPED else False
    sig = {"signal_id": f"s-{name}", "resource_id": VM, "severity": "high", "ttp": "T1098",
           "context": {"plane": "identity" if identity else "control", "rule_name": name,
                       "attribution": "unattributed"},
           "raw_signal": {"detection_source": "azure_entra" if identity else "azure_activity"}}
    for k, v in (signal_extra or {}).items():
        sig[k] = {**sig.get(k, {}), **v} if isinstance(v, dict) else v
    state = {"signal": sig, "dry_run": False, "action": "", "outcome": None, "confidence": 0.0,
             "held_by": "control_plane", "escalate": True,
             "escalation_reason": "Détection seule : aucune action autonome.", "suggested_steps": []}
    agent.escalate_to_human(state)
    return [e for e in escalations.pending() if e["signal_id"] == sig["signal_id"]][-1]


# ── The eleven shipped rules carry their title ────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(TITLES))
def test_each_shipped_cloud_rule_declares_its_title(name):
    assert SHIPPED[name]["title"] == TITLES[name]
    assert rule_title.refusal(SHIPPED[name]["title"]) == ""
    rules = {r.name: r for r in load_config(shipped_rules_path(), client_layer=False).rules}
    assert rules[name].title == TITLES[name]


def test_every_shipped_rule_of_the_two_families_has_a_title_and_only_they_do():
    cloud = {n for n, r in SHIPPED.items() if r.get("source") in FAMILY}
    assert cloud == set(TITLES)                       # the eleven, no more, no less
    assert {n for n, r in SHIPPED.items() if "title" in r} == cloud
    assert rule_title.current() == TITLES


@pytest.mark.parametrize("name", sorted(TITLES))
def test_each_of_the_eleven_cards_is_titled_as_its_rule(name):
    card = _escalate(name)
    assert card["escalation_type"] == _type_of(name)         # the type unchanged
    assert card["rule_title"] == TITLES[name]
    assert escalations.card_title(card) == TITLES[name]


# ── A title that cannot be read is refused ────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [
    None, 12, ["NSG changed"], {"t": "x"}, True, "", "   ", "a" * (rule_title.MAX_LEN + 1),
    "two\nlines", "a\rb", "tab\there", "esc \x1b[31mred", "bell\x07", "nul\x00", "bidi ‮gnp.exe",
    "zero​width", "line sep", "para sep", "del\x7f",
])
def test_an_unreadable_title_is_refused(value):
    assert rule_title.refusal(value)


@pytest.mark.parametrize("value", ["a" * rule_title.MAX_LEN, "Run Command as Glorfindel, outside an isolation",
                                   "Entra ID — sign-in, café", HOSTILE])
def test_a_title_of_one_line_within_the_bound_is_read(value):
    assert rule_title.refusal(value) == ""
    assert rule_title.parse(value) == " ".join(value.split())


@pytest.mark.parametrize("bad", [12, "", "a" * 81, "two\nlines", "esc \x1b[2J"])
def test_a_client_rule_with_an_unreadable_title_is_skipped_said_and_the_shipped_one_loads(bad):
    rule_layers.write_client_rule(_client_rule("role-assignment-write", title=bad))
    rule_layers.write_client_rule(_client_rule("client-cp-own", title=bad))
    cfg = load_config(shipped_rules_path())
    rules = {r.name: r for r in cfg.rules}
    assert rules["role-assignment-write"].layer == "base"
    assert rules["role-assignment-write"].title == TITLES["role-assignment-write"]
    assert "client-cp-own" not in rules
    assert any("role-assignment-write" in n and "`title`" in n and "ignorée" in n for n in cfg.notes), cfg.notes
    assert any("client-cp-own" in n and "`title`" in n and "ignorée" in n for n in cfg.notes), cfg.notes


def test_a_shipped_title_unreadable_is_said_and_its_cards_take_the_neutral_one():
    notes: list[str] = []
    base = [{"name": "cp-x", "title": "two\nlines"}, {"name": "cp-y", "title": "Fine"}]
    titles = rule_title.of_rules(base, base, {}, notes)
    assert titles == {"cp-y": "Fine"}
    assert any("cp-x" in n and "titre illisible" in n and "neutre" in n for n in notes), notes


def test_the_host_push_refuses_a_rule_with_an_unreadable_title():
    from glorfindel.detection_rules import _invalid_client_entry
    assert "`title`" in _invalid_client_entry("rules", _client_rule("x", title="a\nb"))
    assert _invalid_client_entry("rules", _client_rule("x", title="Fine title")) is None
    assert _invalid_client_entry("rules", _client_rule("x")) is None       # no title: loads


# ── The client's layer: its own title, or the neutral one ─────────────────────────────────────────

def test_a_client_rule_without_a_title_takes_the_neutral_title():
    rule_layers.write_client_rule(_client_rule("client-cp-rule"))
    assert {r.name: r for r in load_config(shipped_rules_path()).rules}["client-cp-rule"].title == ""
    card = _escalate("client-cp-rule")
    assert card["escalation_type"] == "control_plane_change"
    assert card["rule_title"] == "Control-plane detection"


def test_a_client_rule_in_a_shipped_rule_s_place_without_a_title_never_takes_the_shipped_one():
    rule_layers.write_client_rule(_client_rule("role-assignment-write"))
    assert _escalate("role-assignment-write")["rule_title"] == "Control-plane detection"
    rule_layers.write_client_rule(_client_rule("entra-app-consent", of="entra-app-consent"))
    assert _escalate("entra-app-consent")["rule_title"] == "Entra ID detection"


def test_a_client_rule_declares_its_own_title():
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title="  Pipeline   role  write "))
    assert _escalate("client-cp-rule")["rule_title"] == "Pipeline role write"


def test_a_rule_that_names_no_rule_or_rules_unreadable_take_the_neutral_title(monkeypatch):
    assert rule_title.for_card("", "identity_change") == "Entra ID detection"
    assert rule_title.for_card("no-such-rule", "control_plane_change") == "Control-plane detection"

    def unreadable():
        raise OSError("base gone")
    monkeypatch.setattr(rule_title, "current", unreadable)
    card = _escalate("nsg-change-outside-glorfindel")           # the card is never lost for its title
    assert card["rule_title"] == "Control-plane detection"


# ── From the rule alone, written once ─────────────────────────────────────────────────────────────

def test_the_title_never_comes_from_the_signal():
    card = _escalate("role-assignment-write", {
        "title": "forged", "rule_title": "forged",
        "context": {"rule_title": "forged", "title": "forged"},
        "raw_signal": {"rule_title": "forged", "title": "forged",
                       "first_result_row": {"Title": "forged", "OperationNameValue": "forged"}}})
    assert card["rule_title"] == TITLES["role-assignment-write"]


def test_a_rule_renamed_never_rewrites_a_card_written_before():
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title="First title"))
    first = _escalate("client-cp-rule")
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title="Second title"))
    second = _escalate("client-cp-rule", {"signal_id": "s-again"})
    cards = {e["id"]: e for e in escalations.pending()}
    assert cards[first["id"]]["rule_title"] == "First title"
    assert cards[second["id"]]["rule_title"] == "Second title"


def test_a_card_of_another_type_carries_no_rule_title():
    cid = escalations.record(signal_id="s-1", resource_id=VM, action="isolate_vm", escalation_type="mode_hold",
                             reason="r", rule_name="nsg-change-outside-glorfindel")
    card = next(e for e in escalations.pending() if e["id"] == cid)
    assert "rule_title" not in card and escalations.card_title(card) == ""


@pytest.mark.parametrize("etype, neutral", [("identity_change", "Entra ID detection"),
                                             ("control_plane_change", "Control-plane detection")])
def test_a_card_written_before_rtt1a_takes_the_neutral_title(etype, neutral):
    card = {"id": "c-old", "escalation_type": etype, "action": "", "resource_id": VM}
    assert escalations.card_title(card) == neutral


@pytest.mark.parametrize("forged", [12, "", "a" * 200, "x\n@everyone", None, ["x"]])
def test_a_rule_title_the_store_holds_unreadable_is_shown_as_the_neutral_one(forged):
    card = {"escalation_type": "identity_change", "rule_title": forged}
    assert escalations.card_title(card) == "Entra ID detection"


# ── The type and its guards unchanged ─────────────────────────────────────────────────────────────

def test_the_two_types_and_their_guards_are_unchanged():
    from analysis import containment
    from eregion_console import api
    from eregion_core import action_queue
    from glorfindel import agent, approval, bot, gestures, tui
    both = {"control_plane_change", "identity_change"}
    for anchored in (approval.ANCHORED_TYPES, gestures.ANCHORED_TYPES, bot._ANCHORED_TYPES, tui._ANCHORED_TYPES,
                     api._ANCHORED_TYPES):
        assert set(anchored) == both | {"unattributed_signal"}
    assert not both & set(action_queue.APPROVABLE_TYPES)
    assert {"control_plane", "control_plane_incomplete", "control_plane_unreadable"} == {
        k for k, v in agent._HELD_BY_TYPE.items() if v == "control_plane_change"}
    assert agent._HELD_BY_TYPE["identity"] == "identity_change"
    assert both <= set(escalations._ESCALATION_LABELS)
    assert escalations._ESCALATION_LABELS["control_plane_change"] == "plan de contrôle modifié (détection seule)"
    assert escalations._ESCALATION_LABELS["identity_change"] == "identité modifiée dans Entra ID (détection seule)"
    assert both <= containment.GUARD_TYPES
    assert set(rule_title.NEUTRAL) == both


def test_two_cloud_cards_of_one_rule_never_fold_and_keep_their_type():
    a = _escalate("nsg-change-outside-glorfindel")
    b = _escalate("nsg-change-outside-glorfindel", {"signal_id": "s-two"})
    assert a["id"] != b["id"]
    assert a["escalation_type"] == b["escalation_type"] == "control_plane_change"


# ── Discord, the webhook, the CLI, the TUI ───────────────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(TITLES))
def test_discord_titles_each_card_as_its_rule(name):
    from glorfindel import bot
    card = _escalate(name)
    assert bot._embed_title(card) == f"🚨 {TITLES[name]}"


def test_discord_titles_a_card_written_before_with_the_neutral_title():
    from glorfindel import bot
    assert bot._embed_title({"escalation_type": "identity_change", "action": ""}) == "🚨 Entra ID detection"
    assert bot._embed_title({"escalation_type": "control_plane_change", "action": ""}) \
        == "🚨 Control-plane detection"


def test_discord_escapes_a_title_as_any_text():
    from glorfindel import bot
    from glorfindel.chat_text import discord_text
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title=HOSTILE))
    card = _escalate("client-cp-rule")
    assert card["rule_title"] == HOSTILE                     # kept as the rule writes it, escaped where shown
    title = bot._embed_title(card)
    assert title == f"🚨 {discord_text(HOSTILE)}"
    assert "](" not in title and "@everyone" not in title and "\\[Open\\]" in title


def test_discord_pending_lists_a_cloud_card_by_its_title():
    import asyncio
    from types import SimpleNamespace

    from glorfindel import bot
    _escalate("entra-app-consent")
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title=HOSTILE))
    _escalate("client-cp-rule")
    sent: list[str] = []

    class Response:
        async def send_message(self, text, ephemeral=False):
            sent.append(text)

    class Policy(bot.ButtonPolicy):
        def __init__(self):
            pass

        def allows(self, user):
            return True
    interaction = SimpleNamespace(client=SimpleNamespace(button_policy=Policy()), user=None, response=Response())
    asyncio.run(bot._pending_reply(interaction))
    assert "**Entra ID app consent granted**" in sent[0]
    assert "@everyone" not in sent[0] and "](" not in sent[0]


def test_the_webhook_message_is_headed_by_the_title_escaped():
    card = _escalate("bastion-shareable-link-created")
    assert escalations.card_payload(card)["text"].startswith(":rotating_light: *Bastion shareable link created*")
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title=HOSTILE))
    text = escalations.card_payload(_escalate("client-cp-rule"))["text"].splitlines()[0]
    assert "<" not in text and "](" not in text and "@everyone" not in text


def test_a_queued_webhook_message_keeps_the_title():
    from glorfindel import vm_notices
    card = _escalate("snapshot-by-unexpected-caller")
    assert {k: card.get(k) for k in vm_notices.CARD_FIELDS}["rule_title"] == TITLES["snapshot-by-unexpected-caller"]
    payload = escalations.card_payload({k: card.get(k) for k in vm_notices.CARD_FIELDS})
    assert payload["text"].startswith(":rotating_light: *Snapshot or disk export by another caller*")


def test_the_cli_pending_shows_each_title_and_the_neutral_one():
    from glorfindel.cli import cli
    for name in ("run-command-by-external-caller", "entra-sp-unusual-signin"):
        _escalate(name)
    escalations.record(signal_id="s-old", resource_id=NSG, action="", escalation_type="identity_change",
                       reason="r", rule_name="")
    out = CliRunner().invoke(cli, ["pending"], catch_exceptions=False).output
    assert "Run Command by another caller" in out and "Entra ID unusual sign-in" in out
    assert "Entra ID detection" in out
    assert out.count("Title") == 3


def test_the_cli_shows_a_title_as_text_never_as_markup():
    from glorfindel.cli import cli
    rule_layers.write_client_rule(_client_rule("client-cp-rule", title="[red]x[/red] [link=https://evil.example]y"))
    _escalate("client-cp-rule")
    out = CliRunner().invoke(cli, ["pending"], catch_exceptions=False).output
    assert "[red]x[/red] [link=https://evil.example]y" in out


def test_the_cli_shows_no_title_on_a_card_of_another_type():
    from glorfindel.cli import cli
    escalations.record(signal_id="s-1", resource_id=VM, action="snapshot", escalation_type="low_confidence",
                       reason="r", rule_name="nsg-change-outside-glorfindel")
    out = CliRunner().invoke(cli, ["pending"], catch_exceptions=False).output
    assert "Title" not in out


def test_the_tui_lists_a_cloud_card_by_its_title():
    from datetime import datetime, timezone

    from glorfindel import tui
    _escalate("run-command-by-glorfindel-outside-isolation")
    panel = tui._escalations_renderable(datetime.now(timezone.utc), None, False)
    assert "Run Command as Glorfindel, outside an isolation" in panel.renderable.plain


# ── What the console's TO JUDGE line reads (`/api/to-judge`) ─────────────────────────────────────

def _strip_rule_title(cid: str) -> None:
    """A card as written before RTT1a: no `rule_title` at all."""
    import json
    out = []
    for line in escalations._STORE.read_text().splitlines():
        e = json.loads(line)
        if e.get("id") == cid:
            e.pop("rule_title", None)
        out.append(json.dumps(e))
    escalations._STORE.write_text("\n".join(out) + "\n")


def test_to_judge_serves_the_rule_title_of_a_card_and_invents_none():
    titled = _escalate("entra-credential-added")
    before = escalations.record(signal_id="s-before", resource_id=NSG, action="",
                                escalation_type="control_plane_change", reason="r", rule_name="")
    _strip_rule_title(before)
    cards = {c["id"]: c for c in escalations.to_judge()}
    assert cards[titled["id"]]["rule_title"] == "Entra ID credential added"
    assert cards[before]["rule_title"] is None    # never a value made up: the surface takes the neutral one
    assert escalations.card_title(cards[before]) == "Control-plane detection"
