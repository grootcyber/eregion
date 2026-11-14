"""CMD1 (#797) — `glorfindel isolate` and `glorfindel block`: a containment by a human's hand.

The console proposed them for a held card, the reassertion for a NIC a perimeter does not cover; the
CLI had neither. They are the console's approval of a held card, without the card, from a terminal —
the console closed (the workstation's shell, the phone's, MOB1), or no card at all: the same calls and
the same guards (glorfindel/gestures.py), in this order, before any call to the cloud:

  - the VM resolved as `release` and `unblock` resolve it (`<groupe>/<nom>`, MSK3b), said before;
  - one host address (`single_host_ip`), never one of the never-block list (SEC2);
  - a VM the watch knows (its perimeter: discovered, held, or of a pending card), never a VM a card
    is only anchored on (AL1);
  - a host whose credentials can write (GLORFINDEL_READ_ONLY);
  - then, under the VM's lock, the connector's own write — its state written as the watch writes it —
    and the check after: the console's (`approval.verify_approved`), the gesture noted in runs/console,
    a `verification_failed` card when it is not True, said, exit 2.

A held card of the same VM and action is said, never resolved: the human acknowledges it. On the
in-memory Azure (fake_azure.py): the isolation and the block are real writes of the connector, their
state read back by `release`, `unblock` and the reassertion. No Azure call, no model call; every
identifier is made up (repository public). Mutants M5205–M5219 (scripts/mutants/CMD1.py).

CMD1b (#811, §4): the VM's enrollment zone said on one line before the prompt, read as the console reads
it, by a fake reader of tags — never a refusal (Jonathan's decision of 14/11). Mutants M5285–M5294
(scripts/mutants/CMD1b.py).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from glorfindel import escalations
from glorfindel.actions import AzureConnector

from .fake_azure import FakeAzure, key, vm_id

WEB = vm_id("rg-app1", "web")
OTHER = vm_id("rg-app2", "web")
ATTACKER = "203.0.113.7"


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """web in rg-app1: its NIC behind its own NSG, on a subnet with its NSG; the connector a real one
    on the in-memory Azure, made for each command as the CLI makes it; web discovered."""
    for var in ("GLORFINDEL_READ_ONLY", "GLORFINDEL_WEBHOOK_URL", "DISCORD_BOT_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GLORFINDEL_QUARANTINE_NSG", "0")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(escalations, "notify_action", lambda **kw: None, raising=False)
    f = FakeAzure()
    own = f.add_nsg("rg-app1", "nsg-web")
    s_nsg = f.add_nsg("rg-net", "nsg-subnet")
    subnet = f.add_subnet("rg-net", "vnet-hub", "app", s_nsg)
    f.add_vm("rg-app1", "web", [{"rg": "rg-app1", "name": "web-nic", "ips": ["10.0.0.4"], "subnet": subnet,
                                 "nsg": own}])
    made: list = []

    def factory(dry_run: bool = False, read_only=None):
        c = AzureConnector(dry_run=dry_run, read_only=read_only)
        c._network, c._compute = f.network, f.compute
        c._subscription_id = "s"
        c.recent_changes = lambda *a, **k: []
        made.append(c)
        return c
    monkeypatch.setattr("glorfindel.actions.AzureConnector", factory)
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(
        all=lambda: [SimpleNamespace(resource_id=WEB)]))
    return SimpleNamespace(fake=f, own=own, subnet_nsg=s_nsg, made=made, runs=tmp_path / "runs")


def _run(*args, input=None):
    """The command's result, its output on one line (rich wraps it at the terminal's width)."""
    from glorfindel.cli import cli
    r = CliRunner().invoke(cli, list(args), input=input, terminal_width=200)
    return SimpleNamespace(exit_code=r.exit_code, output=" ".join(r.output.split()))


def _noted(world) -> list[dict]:
    path = world.runs / "console" / "manual_actions.jsonl"
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def _rules(world, nsg) -> set[str]:
    return set(world.fake.nsgs[key(nsg)]["rules"])


def _card(rid=WEB, action="isolate_vm", etype="mode_hold") -> str:
    escalations.record(signal_id="s-1", resource_id=rid, action=action, escalation_type=etype,
                       reason="held", ttp="T1110", severity="high")
    return next(e["id"] for e in escalations.pending() if e["escalation_type"] == etype)


# ── 1. isolate ────────────────────────────────────────────────────────────────────────────────────

def test_isolate_by_group_and_name_cuts_the_vm_off_verified_noted_and_held(world):
    """The VM by `<groupe>/<nom>` (the commands to copy), isolated for real, checked after, noted for
    the feed; its state the watch's — `list`, the reassertion and `release` read it."""
    from glorfindel.actions import active_isolations
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert "web (groupe rg-app1)" in r.output and "la vérification le confirme" in r.output
    assert any(x["resource_id"] == WEB for x in active_isolations())
    assert any(n.startswith("glorfindel-iso") for n in _rules(world, world.own))
    [noted] = _noted(world)
    assert noted["action"] == "isolate_vm" and noted["outcome"]["verified"] is True
    assert not escalations.pending()                       # verified: no card


def test_what_the_cli_isolated_is_released_by_release(world):
    """The state written is the one `release` lifts — never a second one beside it."""
    from glorfindel.actions import active_isolations
    assert _run("isolate", "rg-app1/web", "--yes").exit_code == 0
    r = _run("release", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert not active_isolations()
    assert not any(n.startswith("glorfindel-iso") for n in _rules(world, world.own))


def test_the_reassertion_reads_what_the_cli_isolated(world):
    """Its rules taken off by someone after the gesture: the watch's pass sees it, as for its own."""
    from glorfindel.reassert import reassert_pass
    assert _run("isolate", "rg-app1/web", "--yes").exit_code == 0
    for n in [n for n in _rules(world, world.own) if n.startswith("glorfindel-iso")]:
        del world.fake.nsgs[key(world.own)]["rules"][n]
    report = reassert_pass(world.made[-1], None)
    assert any(x["kind"] == "isolation" and x["vm"] == "web" for x in report), report


def test_the_whole_gesture_holds_the_vm_s_lock(world, monkeypatch):
    """The write and its check under the VM's lock, as the queue runs a request: another writer of the
    VM (the watch, the console) waits — never a release between the isolation and its check."""
    import contextlib
    from glorfindel.response import locks
    held: list[str] = []
    real = locks._vm_lock

    @contextlib.contextmanager
    def spy(vm, timeout=None):
        held.append(vm)
        with real(vm, timeout):
            yield
        held.append("/" + vm)
    monkeypatch.setattr(locks, "_vm_lock", spy)
    seen: list = []
    verify = AzureConnector.verify_isolation

    def checked(self, rid):
        seen.append(list(held))
        return verify(self, rid)
    monkeypatch.setattr(AzureConnector, "verify_isolation", checked)
    assert _run("isolate", "rg-app1/web", "--yes").exit_code == 0
    assert held[0] == "web" and held[-1] == "/web"
    assert seen and seen[0][0] == "web" and "/web" not in seen[0]


def test_a_check_that_fails_is_said_left_on_a_card_and_exits_2(world, monkeypatch):
    """Not verified is not a success (fourth review, Q11): said, a verification_failed card, exit 2."""
    monkeypatch.setattr(AzureConnector, "verify_isolation",
                        lambda self, rid: {"verified": False, "error": "a NIC still open"})
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 2, r.output
    assert "la vérification a échoué" in r.output and "a NIC still open" in r.output
    [card] = escalations.pending()
    assert card["escalation_type"] == "verification_failed" and card["action"] == "isolate_vm"
    assert card["signal_id"] == "cli-isolate_vm"


def test_a_check_that_cannot_conclude_is_said_and_exits_2(world, monkeypatch):
    def unread(self, rid):
        raise RuntimeError("429 throttled")
    monkeypatch.setattr(AzureConnector, "verify_isolation", unread)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 2, r.output
    assert "n'a pas pu être vérifiée" in r.output
    assert [e["escalation_type"] for e in escalations.pending()] == ["verification_failed"]


def test_a_vm_outside_the_watch_s_perimeter_is_refused_before_any_call(world, monkeypatch):
    """A VM neither discovered, nor held, nor of a pending card: nothing is made, not even the
    connector."""
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(all=lambda: []))
    r = _run("isolate", OTHER, "--yes")
    assert r.exit_code == 1 and "périmètre de la watch" in r.output, r.output
    assert not world.made and not _rules(world, world.own)


def test_another_resource_than_a_vm_is_refused(world):
    nsg = world.own
    r = _run("isolate", nsg, "--yes")
    assert r.exit_code == 1 and "pas une VM" in r.output, r.output
    assert not world.made


@pytest.mark.parametrize("etype", ["control_plane_change", "identity_change", "unattributed_signal"])
def test_a_vm_a_card_is_only_anchored_on_is_refused(world, etype):
    """AL1: the detection does not name this VM — read the card, acknowledge it, act on the VM it is
    about; never isolated on the anchor's word."""
    card = _card(etype=etype)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 1, r.output
    assert "ancrée" in r.output and card[:8] in r.output
    assert not world.made and not _rules(world, world.own)


def test_a_held_card_of_the_same_gesture_is_said_never_resolved(world):
    """The CLI resolves nothing in silence: the card stays, its `ack` said."""
    card = _card()
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert f"glorfindel ack {card[:8]}" in r.output
    assert [e["id"] for e in escalations.pending()] == [card]


def test_read_only_credentials_refuse_before_any_write(world, monkeypatch):
    """Said before the prompt, as a refusal — never the connector's PermissionError at the write,
    which the CLI's boundary reads as a root-owned state file."""
    monkeypatch.setenv("GLORFINDEL_READ_ONLY", "1")
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 1 and "lecture seule" in r.output and "rien n'est fait" in r.output, r.output
    assert "appartenant à root" not in r.output
    assert not _rules(world, world.own) and not _noted(world)


def _drain_pending(monkeypatch):
    """The isolation's session cut still running on Azure past its first wait (DRN1)."""
    from datetime import datetime, timezone
    real = AzureConnector.isolate_vm

    def with_drain(self, rid):
        out = real(self, rid)
        out["drain"] = {"status": "pending", "asked_at": datetime.now(timezone.utc).isoformat()}
        return out
    monkeypatch.setattr(AzureConnector, "isolate_vm", with_drain)


def _beat_here(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from eregion_core import watch_gate
    beat = tmp_path / "watch_heartbeat"
    beat.write_text(datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(watch_gate, "heartbeat_path", lambda: beat)


def test_a_session_cut_no_watch_here_rereads_is_not_verified(world, monkeypatch):
    """No live watch on this host: the cut still running is read again by nobody — never « ✓ … the
    reassertion rereads it »: not verified, a card, exit 2, and how to cut the sessions by hand
    (review 1)."""
    monkeypatch.setenv("GLORFINDEL_REASSERT_INTERVAL_S", "60")
    _drain_pending(monkeypatch)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 2, r.output
    assert "aucune watch vivante sur cet hôte ne relira son statut" in r.output
    assert "Couper à la main" in r.output and "la réaffirmation la relit" not in r.output
    [card] = escalations.pending()
    assert card["escalation_type"] == "verification_failed" and card["signal_id"] == "cli-isolate_vm"


def test_a_session_cut_the_watch_here_rereads_is_said_and_holds(world, monkeypatch, tmp_path):
    monkeypatch.setenv("GLORFINDEL_REASSERT_INTERVAL_S", "60")
    _drain_pending(monkeypatch)
    _beat_here(monkeypatch, tmp_path)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0 and "la réaffirmation la relit" in r.output, r.output
    assert not escalations.pending()


def test_an_isolation_that_lands_on_some_nics_only_is_noted_and_left_on_a_card(world, monkeypatch):
    """A PartialActionError (what landed kept, recorded by the connector): noted, a card that names
    the NIC that failed, exit 2 — never an Azure error said once and lost (review 1)."""
    from glorfindel.response.policy import PartialActionError

    def partly(self, rid):
        raise PartialActionError("isolation partielle : web-nic2 refusée", cause=RuntimeError("409"),
                                 covered=["web-nic"], failed_nic="web-nic2")
    monkeypatch.setattr(AzureConnector, "isolate_vm", partly)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 2, r.output
    assert "en partie seulement" in r.output and "web-nic2" in r.output
    [card] = escalations.pending()
    assert card["escalation_type"] == "verification_failed" and "web-nic2" in card["reason"]
    [noted] = _noted(world)
    assert noted["action"] == "isolate_vm" and noted["outcome"]["partial"] is True
    assert noted["outcome"]["verified"] is False


def test_a_dry_run_holds_the_read_only_guard_too(world, monkeypatch):
    """« The guards only »: read-only credentials are a guard, read locally — refused in a dry run
    too (review 1)."""
    monkeypatch.setenv("GLORFINDEL_READ_ONLY", "1")
    r = _run("isolate", "rg-app1/web", "--dry-run")
    assert r.exit_code == 1 and "lecture seule" in r.output, r.output


def test_the_way_to_the_watch_s_container_is_one_a_prompt_answers_in(world):
    """`docker exec` without `-it`: `click.confirm` reads an end of file — the line says `-it`."""
    r = _run("isolate", "rg-app1/web", "--yes")
    assert "docker exec -it eregion-watch" in r.output, r.output


def test_a_dry_run_checks_the_guards_and_writes_nothing(world, monkeypatch):
    from glorfindel.actions import active_isolations
    r = _run("isolate", "rg-app1/web", "--dry-run")
    assert r.exit_code == 0 and "DRY RUN" in r.output, r.output
    assert not _rules(world, world.own) and not active_isolations() and not _noted(world)
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(all=lambda: []))
    assert _run("isolate", OTHER, "--dry-run").exit_code == 1          # the guards still hold


def test_without_yes_the_human_is_asked(world):
    r = _run("isolate", "rg-app1/web", input="n\n")
    assert "Aborted" in r.output and not _rules(world, world.own)


def test_no_live_watch_here_is_said(world):
    """The state is this host's: a watch of another host (Imladris) does not read it — said, never
    refused (a watch stopped is when a hand is needed)."""
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0 and "Aucune watch vivante sur cet hôte" in r.output, r.output


def test_a_live_watch_here_says_nothing_of_it(world, monkeypatch, tmp_path):
    """The heartbeat in this test's own folder: never left in the session's HOME, where it would
    tell the console's tests that a watch runs."""
    from datetime import datetime, timezone
    from eregion_core import watch_gate
    beat = tmp_path / "watch_heartbeat"
    beat.write_text(datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(watch_gate, "heartbeat_path", lambda: beat)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0 and "Aucune watch vivante" not in r.output, r.output


# ── 2. block ──────────────────────────────────────────────────────────────────────────────────────

def test_block_on_the_vm_by_default_verified_noted_and_unblocked_by_unblock(world):
    from glorfindel.actions import active_blocks
    r = _run("block", ATTACKER, "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert "la vérification le confirme" in r.output
    [b] = [b for b in active_blocks() if b["ip"] == ATTACKER]
    assert b["resource_id"] == WEB and b["scoped"] is True
    assert _rules(world, world.own) and not _rules(world, world.subnet_nsg)    # this VM's NSG alone
    [noted] = _noted(world)
    assert noted["action"] == "block_suspicious_ip" and noted["outcome"]["verified"] is True
    r = _run("unblock", ATTACKER, "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert not [b for b in active_blocks() if b["ip"] == ATTACKER]


def test_block_on_the_subnet_is_the_human_s_choice(world):
    from glorfindel.actions import active_blocks
    r = _run("block", ATTACKER, "rg-app1/web", "--scope", "subnet", "--yes")
    assert r.exit_code == 0, r.output
    assert "every VM of its subnet" in r.output
    [b] = [b for b in active_blocks() if b["ip"] == ATTACKER]
    assert b["scoped"] is False
    assert _rules(world, world.subnet_nsg)


@pytest.mark.parametrize("ip,why", [
    ("203.0.113.0/24", "adresse IP invalide"),          # a range
    ("*", "adresse IP invalide"),
    ("Internet", "adresse IP invalide"),                # a service tag
    ("0.0.0.0", "non routable"),
    ("127.0.0.1", "non routable"),
    ("10.0.0.9", ""),                                   # private: never blocked (SEC2)
    ("168.63.129.16", ""),                              # Azure's platform
])
def test_only_one_blockable_host_address_is_blocked(world, ip, why):
    r = _run("block", ip, "rg-app1/web", "--yes")
    assert r.exit_code == 1, r.output
    assert why in r.output
    assert not world.made and not _rules(world, world.own) and not _rules(world, world.subnet_nsg)


def test_a_scope_that_is_no_reach_is_refused_by_the_cli(world):
    r = _run("block", ATTACKER, "rg-app1/web", "--scope", "nic", "--yes")
    assert r.exit_code == 2 and not world.made


def test_block_holds_the_guards_of_isolate(world):
    _card(etype="unattributed_signal")
    r = _run("block", ATTACKER, "rg-app1/web", "--yes")
    assert r.exit_code == 1 and "ancrée" in r.output and not world.made


def test_a_block_that_does_not_hold_is_said_and_exits_2(world, monkeypatch):
    monkeypatch.setattr(AzureConnector, "verify_block_ip",
                        lambda self, ip, rid: {"verified": False, "error": "an allow before the deny"})
    r = _run("block", ATTACKER, "rg-app1/web", "--yes")
    assert r.exit_code == 2 and "an allow before the deny" in r.output, r.output
    [card] = escalations.pending()
    assert card["escalation_type"] == "verification_failed" and card["action"] == "block_suspicious_ip"


# ── 3. ack, with what the commands to copy give ───────────────────────────────────────────────────

def test_ack_takes_the_eight_characters_the_console_and_the_tui_give(world):
    """`glorfindel ack <8 characters>` matched nothing and said « acknowledged » (CMD1)."""
    card = _card()
    r = _run("ack", card[:8])
    assert r.exit_code == 0, r.output
    assert not escalations.pending()


def test_ack_of_no_card_is_said_never_acknowledged(world):
    r = _run("ack", "ffffffff")
    assert r.exit_code == 1 and "no card" in r.output, r.output
    assert "acknowledged" not in r.output


def test_ack_of_a_prefix_two_cards_share_is_refused(world):
    escalations.record(signal_id="s-1", resource_id=WEB, action="isolate_vm", escalation_type="mode_hold",
                       reason="a", ttp="T1110", severity="high")
    escalations.record(signal_id="s-2", resource_id=OTHER, action="snapshot", escalation_type="low_confidence",
                       reason="b", ttp="T1486", severity="high")
    ids = [e["id"] for e in escalations.pending()]
    r = _run("ack", "")
    assert r.exit_code == 0                                 # no id: said, as before
    r = _run("ack", ids[0][:5])
    assert r.exit_code == 1 and "6 characters" in r.output
    assert len(escalations.pending()) == 2


def test_ack_of_a_prefix_two_cards_share_acknowledges_neither(world, monkeypatch):
    """Two cards whose ids share their first 8 characters: `ack <those 8>` refuses, both stay —
    never the first of the two acknowledged in silence (review 1)."""
    import uuid
    made = iter(["abcdef01-0000-4000-8000-000000000001", "abcdef01-0000-4000-8000-000000000002"])
    monkeypatch.setattr(uuid, "uuid4", lambda: next(made))
    escalations.record(signal_id="s-1", resource_id=WEB, action="isolate_vm", escalation_type="mode_hold",
                       reason="a", ttp="T1110", severity="high")
    escalations.record(signal_id="s-2", resource_id=OTHER, action="snapshot", escalation_type="low_confidence",
                       reason="b", ttp="T1486", severity="high")
    assert sorted(e["id"] for e in escalations.pending())[0].startswith("abcdef01")
    r = _run("ack", "abcdef01")
    assert r.exit_code == 1 and "matches 2 cards" in r.output, r.output
    assert len(escalations.pending()) == 2
    r = _run("ack", "abcdef01-0000-4000-8000-000000000002")          # the whole id: that one alone
    assert r.exit_code == 0, r.output
    assert [e["id"] for e in escalations.pending()] == ["abcdef01-0000-4000-8000-000000000001"]


def test_the_anchored_set_is_the_bot_s_and_the_tui_s():
    """The CLI's guard reads the same anchored types as the bot and the TUI (the console's too:
    tests/unit/test_proposed_commands.py)."""
    import ast
    from pathlib import Path
    from glorfindel import gestures
    root = Path(__file__).resolve().parents[2]
    for rel in ("glorfindel/bot.py", "glorfindel/tui.py"):
        tree = ast.parse((root / rel).read_text())
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", "") == "_ANCHORED_TYPES" for t in n.targets))
        assert set(ast.literal_eval(node.value)) == set(gestures.ANCHORED_TYPES), rel


# ── 4. the VM's enrollment zone, said before the prompt — never a refusal (CMD1b, #811) ───────────────
#
# Jonathan's decision of 14/11: the CLI says the zone, it never refuses for it. Read as the console
# reads it (TagEnrollment's tags, judged by ``enrollment``), here by a fake reader of tags: no Azure
# call. A VM not enrolled, a zone none of the three, tags unread: said as such, never taken for the
# bench. Mutants M5285–M5294 (scripts/mutants/CMD1b.py).

SUB = "00000000-0000-4000-8000-00000000abcd"


def _tags(monkeypatch, vm_tags=None, rg_tags=None, fail=None):
    """The fake reader of tags: (the group's, the VM's) — or ``fail`` raised. Its calls kept."""
    from glorfindel import gestures
    calls: list[str] = []

    def read(resource_id):
        calls.append(resource_id)
        if fail is not None:
            raise fail
        return dict(rg_tags if rg_tags is not None else {"eregion-target": "celebrimbor"}), dict(vm_tags or {})
    monkeypatch.setattr(gestures, "TAGS_READER", read)
    return calls


def _enrolled(zone: str) -> dict:
    return {"eregion-target": "celebrimbor", "eregion-zone": zone}


@pytest.mark.parametrize("zone", ["bench", "twin"])
def test_bench_and_twin_are_said_as_they_are(world, monkeypatch, zone):
    calls = _tags(monkeypatch, _enrolled(zone))
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert f"Zone : {zone} " in r.output and "charge réelle" not in r.output, r.output
    assert calls == [WEB]


def test_production_is_said_a_real_load_and_never_refused(world, monkeypatch):
    """In production the line says a real load — and the gesture is made, verified, exit 0: O0's rule
    bounds what Eregion injects, not what it contains (the isolation is lifted by `release`)."""
    from glorfindel.actions import active_isolations
    _tags(monkeypatch, _enrolled("production"))
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert "Zone : production — une charge réelle" in r.output and "glorfindel release" in r.output, r.output
    assert any(x["resource_id"] == WEB for x in active_isolations())
    assert "la vérification le confirme" in r.output


def test_block_in_production_is_said_and_made_lifted_by_unblock(world, monkeypatch):
    from glorfindel.actions import active_blocks
    _tags(monkeypatch, _enrolled("production"))
    r = _run("block", ATTACKER, "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert "une charge réelle" in r.output and "glorfindel unblock" in r.output, r.output
    assert any(b["ip"] == ATTACKER for b in active_blocks())


@pytest.mark.parametrize("vm_tags, rg_tags", [
    ({}, None),                                                                  # no tag at all
    ({"eregion-target": "celebrimbor", "eregion-zone": "bench"}, {}),            # its group not enrolled
    ({"eregion-target": "another-bench", "eregion-zone": "bench"}, None),        # another bench's
    ({"eregion-target": "celebrimbor"}, None),                                   # enrolled, no zone
])
def test_a_vm_not_enrolled_is_said_so_never_taken_for_the_bench(world, monkeypatch, vm_tags, rg_tags):
    """The VM with a real load is the one never enrolled: nothing says it is the bench's."""
    _tags(monkeypatch, vm_tags, rg_tags)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert "Zone : VM non inscrite (" in r.output and "rien ne dit qu'elle soit du banc" in r.output, r.output
    assert "Zone : bench" not in r.output


def test_a_zone_none_of_the_three_is_said_unknown_never_the_bench(world, monkeypatch):
    _tags(monkeypatch, _enrolled("Production"))
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert "« Production », inconnue" in r.output and "rien ne dit qu'elle soit du banc" in r.output, r.output


@pytest.mark.parametrize("fail", [RuntimeError("HTTP 403 reading web"), PermissionError("no credential"),
                                  ValueError("not a VM resource id")])
def test_tags_unread_are_said_unreadable_and_the_gesture_is_made(world, monkeypatch, fail):
    """A read that fails (a 403, no credential, an error) stops nothing and changes no exit code."""
    from glorfindel.actions import active_isolations
    _tags(monkeypatch, fail=fail)
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert f"Zone : illisible ({fail})" in r.output and "rien ne dit qu'elle soit du banc" in r.output, r.output
    assert any(x["resource_id"] == WEB for x in active_isolations())


def test_the_conftest_reader_reads_nothing_and_is_said_unreadable(world):
    """Every other test of the CLI: tags never read through Azure, the zone said unreadable."""
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0 and "Zone : illisible (tests : tags jamais lus)" in r.output, r.output


def test_the_zone_is_said_before_the_prompt(world, monkeypatch):
    """Before the question: the human reads it, then answers — « no » leaves the VM as it was."""
    from glorfindel.actions import active_isolations
    _tags(monkeypatch, _enrolled("production"))
    r = _run("isolate", "rg-app1/web", input="n\n")
    assert "Aborted" in r.output, r.output
    assert r.output.index("une charge réelle") < r.output.index("Isolate this VM")
    assert not active_isolations() and not _noted(world)


def test_a_dry_run_says_the_zone_unread_and_reads_nothing(world, monkeypatch):
    """A dry run asks nothing of Azure: the line is there, the zone unread — never the bench."""
    calls = _tags(monkeypatch, _enrolled("bench"))
    for args in (("isolate", "rg-app1/web", "--dry-run"), ("block", ATTACKER, "rg-app1/web", "--dry-run", "--yes")):
        r = _run(*args)
        assert r.exit_code == 0, r.output
        assert "Zone : non lue — essai à blanc" in r.output and "Zone : bench" not in r.output, r.output
    assert calls == []


def test_a_refused_gesture_reads_no_tag(world, monkeypatch):
    """The guards first: read-only credentials refuse before the zone is read — nothing asked of Azure."""
    calls = _tags(monkeypatch, _enrolled("bench"))
    monkeypatch.setenv("GLORFINDEL_READ_ONLY", "1")
    assert _run("isolate", "rg-app1/web", "--yes").exit_code == 1
    assert calls == []


def test_what_the_reader_says_is_masked_printable_and_never_markup(world, monkeypatch):
    """Azure's text and a tag's value come from outside: no subscription's id on the terminal (MSK2),
    no markup taken as rich's, one line."""
    full = f"/subscriptions/{SUB}/resourceGroups/rg-app1/providers/Microsoft.Compute/virtualMachines/web"
    _tags(monkeypatch, fail=RuntimeError(f"HTTP 403 over scope '{full}'\nsecond line"))
    r = _run("isolate", "rg-app1/web", "--yes")
    assert r.exit_code == 0, r.output
    assert SUB not in r.output, r.output
    assert "Zone : illisible (HTTP 403 over scope 'web (groupe rg-app1)' second line)" in r.output, r.output
    assert _run("release", "rg-app1/web", "--yes").exit_code == 0
    _tags(monkeypatch, _enrolled("[bold]prod[/bold]"))
    r = _run("isolate", "rg-app1/web", "--yes")
    assert "« [bold]prod[/bold] », inconnue" in r.output, r.output


def test_the_default_reader_is_tag_enrollment_s_two_gets(monkeypatch):
    """The real reader: TagEnrollment's own read — the group, then the VM, two GETs through Azure
    Resource Manager, never a write."""
    import requests

    from eregion_core.inscription import TagEnrollment
    from glorfindel import gestures
    seen: list[tuple[str, str]] = []

    class Answer:
        ok = True

        def __init__(self, tags):
            self._tags = tags

        def json(self):
            return {"tags": self._tags}

    def get(url, **kw):
        seen.append(("GET", url))
        return Answer({"eregion-target": "celebrimbor"} if url.endswith("/rg-app1") else _enrolled("twin"))

    def write(*a, **kw):
        raise AssertionError("a write")
    monkeypatch.setattr(requests, "get", get)
    for verb in ("post", "put", "patch", "delete"):
        monkeypatch.setattr(requests, verb, write)
    monkeypatch.setattr(TagEnrollment, "_headers", lambda self: {"Authorization": "Bearer x"})
    assert gestures.tags_read(WEB) == ({"eregion-target": "celebrimbor"}, _enrolled("twin"))
    assert [v for v, _ in seen] == ["GET", "GET"] and seen[1][1].endswith("/virtualMachines/web")
    monkeypatch.setattr(gestures, "TAGS_READER", gestures.tags_read)
    assert gestures.zone_of(WEB) == ("twin", "")
