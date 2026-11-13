"""MSK3b (#787) — every command to copy Glorfindel writes for a VM names it by « <groupe>/<nom> ».

MSK3 taught the CLI to resolve `<groupe>/<nom>` — the group AND the name matching, on its own host,
or refused — and the bot to give it. But the commands written elsewhere still named the VM by its
name alone: the step of the card « exécutée » (`glorfindel release <vm> --yes`, `unblock <ip> <vm>`),
the TUI's line, the console's 📋 Command, the CLI's own hints and the watch's cards. Copied to
another terminal, or on a subscription where two groups each hold a VM of that name, such a command
could take the other VM — `--yes` asking nothing.

Here, two VMs of one name in two groups (« web » in rg-app-a and rg-app-b): each command names its
own, and the CLI takes it back to that one — never the other. No Azure call, no model call; every
identifier is made up (repository public). Mutants M5125–M5134 (scripts/mutants/MSK3b.py).
"""
from __future__ import annotations

import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

from glorfindel import escalations
from glorfindel.vm_command import UNNAMED, group_and_name

ROOT = Path(__file__).resolve().parents[2]
SUB = "00000000-0000-0000-0000-0000000000ee"
SUB2 = "00000000-0000-0000-0000-0000000000ff"
RG_A, RG_B = "rg-app-a", "rg-app-b"
ATTACKER = "203.0.113.7"


def _vm(rg: str = RG_A, name: str = "web", sub: str = SUB) -> str:
    return f"/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"


WEB_A, WEB_B = _vm(RG_A), _vm(RG_B)


def _known(monkeypatch, *rids):
    """What this host knows: the discovery, nothing isolated nor blocked."""
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [])
    monkeypatch.setattr("glorfindel.actions.active_blocks", lambda: [])
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(
        all=lambda: [SimpleNamespace(resource_id=r) for r in rids]))


def _resolved(arg: str) -> str:
    """The VM a command's argument takes, as the shell hands it to `glorfindel`."""
    from glorfindel import cli
    return cli._resolve_resource_id(shlex.split(arg)[0])


def _clean(text: str) -> None:
    flat = "".join(str(text).split()).lower()
    assert SUB not in flat and SUB2 not in flat and "subscriptions/" not in flat, text


# ── 1. The form ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rid,said", [
    (WEB_A, f"{RG_A}/web"),
    (WEB_A + "/", f"{RG_A}/web"),
    (_vm("rg.(x)"), "'rg.(x)/web'"),                                   # the shell takes it as it is
    (WEB_A + "/extensions/ext-1", UNNAMED),                            # a child of the VM: another resource
    (f"/subscriptions/{SUB}/resourceGroups/{RG_A}/providers/Microsoft.Network/networkSecurityGroups/web", UNNAMED),
    ("web", UNNAMED), ("", UNNAMED), (None, UNNAMED),
])
def test_a_vm_is_named_by_its_group_and_name_only_its_own_id(rid, said):
    assert group_and_name(rid) == said


def test_the_masking_reads_the_same_rule():
    """The bot's form (MSK3) is this one: one function, not two that could part."""
    from glorfindel import masking
    assert masking.group_and_name is group_and_name and masking.UNNAMED == UNNAMED


# ── 2. The card « exécutée » (JUG1) ─────────────────────────────────────────────────────────────

def _executed(rid: str, action: str) -> dict:
    from glorfindel import agent
    signal = {"signal_id": f"rule-x-{rid[-12:]}-{action}", "resource_id": rid, "ttp": "T1486", "severity": "high",
              "context": {"rule_name": "rule-x", "run_id": "watch-x"},
              "raw_signal": {"first_result_row": {"Computer": "web"}}}
    outcome = {"executed": True, "verified": True, "method": "nsg_check",
               "verified_at": "2026-11-13T08:00:00+00:00", **({"ip": ATTACKER} if action != "isolate_vm" else {})}
    cid = agent._record_executed({"signal": signal, "action": action, "outcome": outcome, "dry_run": False,
                                  "escalate": False, "autonomy_mode": "non_disruptive", "confidence": 0.9,
                                  "explanation": "x"}, "watch", "")
    assert cid
    return next(e for e in escalations.pending() if e["id"] == cid)


_UNDO = re.compile(r"`glorfindel (release|unblock \S+) (\S+) --yes`")


@pytest.mark.parametrize("action,verb", [("isolate_vm", "release"), ("block_suspicious_ip", f"unblock {ATTACKER}")])
def test_the_executed_card_s_undo_names_its_vm_by_its_group_and_name(monkeypatch, action, verb):
    """Two VMs « web » in two groups, each isolated (or blocked) alone: each card's undo names its own
    by its group — never « web » alone, which the CLI refuses here and could take the other one on a
    terminal that knows only it. The CLI takes each one back to its own VM."""
    _known(monkeypatch, WEB_A, WEB_B)
    for rid, rg in ((WEB_A, RG_A), (WEB_B, RG_B)):
        card = _executed(rid, action)
        [step] = card["suggested_steps"]
        assert f"`glorfindel {verb} {rg}/web --yes`" in step, step
        assert f"`glorfindel {verb} web --yes`" not in step
        _clean(step)
        named = _UNDO.search(step).group(2)
        assert _resolved(named) == rid                                  # that VM, never the other one
    from glorfindel import cli
    import click
    with pytest.raises(click.ClickException, match="several VMs"):
        cli._resolve_resource_id("web")                                # what the step said before MSK3b


def test_the_executed_card_s_undo_on_a_group_the_shell_reads_is_quoted(monkeypatch):
    odd = _vm("rg.(x)")
    _known(monkeypatch, odd, WEB_B)
    step = _executed(odd, "isolate_vm")["suggested_steps"][0]
    assert "`glorfindel release 'rg.(x)/web' --yes`" in step, step
    assert _resolved(re.search(r"release ('[^']+') --yes", step).group(1)) == odd


# ── 3. The TUI ──────────────────────────────────────────────────────────────────────────────────

def _tui_shown(monkeypatch, cards) -> str:
    from glorfindel import tui
    monkeypatch.setattr(escalations, "pending", lambda: [dict(c) for c in cards])
    screen = Console(width=220, record=True)
    screen.print(tui._escalations_renderable(datetime.now(timezone.utc), None, False))
    return " ".join(screen.export_text().split())


def _card(cid: str, rid: str, action: str, kind: str) -> dict:
    return {"id": cid, "resource_id": rid, "action": action, "escalation_type": kind, "reason": "r",
            "run_id": "r1", "timestamp": "2026-11-13T08:00:00+00:00", "first_seen": "2026-11-13T07:58:00+00:00"}


def test_the_tui_s_commands_name_the_vm_by_its_group_and_name(monkeypatch):
    _known(monkeypatch, WEB_A, WEB_B)
    shown = _tui_shown(monkeypatch, [
        _card("aaaaaaaa-1", WEB_A, "restore_from_backup", "destructive_action"),
        _card("bbbbbbbb-2", WEB_B, "isolate_vm", "verification_failed")])
    assert f"→ glorfindel restore {RG_A}/web --yes --before 2026-11-13T07:58:00+00:00" in shown, shown
    assert f"→ glorfindel revert {RG_B}/web --yes" in shown, shown
    assert "glorfindel restore web " not in shown and "glorfindel revert web " not in shown
    _clean(shown)
    assert _resolved(f"{RG_A}/web") == WEB_A and _resolved(f"{RG_B}/web") == WEB_B


# ── 4. The CLI's own commands ─────────────────────────────────────────────────────────────────

def test_the_cli_s_hints_name_each_homonym_by_its_own_group(monkeypatch, capsys):
    """`pending` and `list`: two VMs « web » in two groups — each named by its group, where MSK2 could
    only ask for the id. Copied to another terminal, the command takes that one or is refused."""
    from glorfindel import cli
    _known(monkeypatch, WEB_A, WEB_B)
    cli._render_escalation(_card("e1", WEB_A, "release_isolation", "low_confidence"))
    cli._render_escalation(_card("e2", WEB_B, "restore_from_backup", "destructive_action"))
    said = " ".join(capsys.readouterr().out.split())
    assert f"glorfindel release {RG_A}/web --yes" in said, said
    assert f"glorfindel restore {RG_B}/web --yes --before" in said, said
    assert "glorfindel release web " not in said and "glorfindel restore web " not in said
    _clean(said)


def test_the_cli_asks_for_the_id_when_its_group_and_name_would_take_another_vm(monkeypatch, capsys):
    """Only a VM of the same group and name in another subscription known here: `<groupe>/<nom>`
    would take that one — the id is asked for (MSK2's rule, kept)."""
    from glorfindel import cli
    _known(monkeypatch, _vm(sub=SUB2))
    cli._render_escalation(_card("e1", WEB_A, "release_isolation", "low_confidence"))
    said = " ".join(capsys.readouterr().out.split())
    assert f"glorfindel release {UNNAMED} --yes" in said and f"release {RG_A}/web" not in said, said


def test_the_cli_names_the_vm_of_a_card_s_own_steps_written_before(monkeypatch):
    """A card written before MSK3b (its step by the short name or by the full id): `pending` names
    its VM by `<groupe>/<nom>` — masked, a full id was no command at all (« web (groupe …) »)."""
    from click.testing import CliRunner
    from glorfindel import cli
    _known(monkeypatch, WEB_A, WEB_B)
    escalations.record("sig-1", WEB_A, "isolate_vm", escalations.EXECUTED_TYPE, "r", run_id="r1",
                       suggested_steps=["Si elle est jugée à tort, la défaire : `glorfindel release web --yes`.",
                                        f"glorfindel snapshot {WEB_A} --yes"])
    out = CliRunner().invoke(cli.cli, ["pending"], terminal_width=200)
    said = " ".join(out.output.split())
    assert out.exit_code == 0, out.output
    assert f"`glorfindel release {RG_A}/web --yes`" in said and f"glorfindel snapshot {RG_A}/web --yes" in said, said
    _clean(said)


# ── 5. The watch's cards ────────────────────────────────────────────────────────────────────────

def test_the_ttl_card_names_its_vm_by_its_group_and_name(monkeypatch):
    from glorfindel.actions import _save_isolation_state
    from glorfindel.reassert import ttl_alerts
    for rid in (WEB_A, WEB_B):
        _save_isolation_state(rid, {"resource_id": rid, "isolated_at": "2026-11-12T08:00:00+00:00", "placements": []})
    ttl_alerts(4.0, now=datetime(2026, 11, 13, 8, tzinfo=timezone.utc))
    cards = {c["resource_id"]: c for c in escalations.pending() if c["escalation_type"] == "ttl_exceeded"}
    assert set(cards) == {WEB_A, WEB_B}
    for rid, rg in ((WEB_A, RG_A), (WEB_B, RG_B)):
        text = cards[rid]["reason"] + " " + " ".join(cards[rid]["suggested_steps"])
        assert f"`glorfindel release {rg}/web --yes`" in cards[rid]["reason"], text
        assert f"Lever : glorfindel release {rg}/web --yes" in cards[rid]["suggested_steps"], text
        assert rid not in text.split("glorfindel release ")[1]


def test_the_readiness_card_names_activate_s_vm_by_its_group_and_name():
    from tests.unit.test_readiness import _NO_DRAIN, _asset, _conn, _tracker
    _tracker(_conn(missing=_NO_DRAIN)).refresh([_asset(WEB_B)])
    [card] = [c for c in escalations.pending() if c["escalation_type"] == "readiness_hold"]
    assert any(f"`glorfindel activate {RG_B}/web`" in s for s in card["suggested_steps"]), card["suggested_steps"]
    assert not any("`glorfindel activate web`" in s for s in card["suggested_steps"])


def test_the_snapshot_step_of_a_held_card_names_its_vm_by_its_group_and_name(monkeypatch):
    from glorfindel import agent
    seen = {}
    monkeypatch.setattr(escalations, "record", lambda **kw: seen.update(kw) or "id-1")
    agent.escalate_to_human({"signal": {"signal_id": "s1", "resource_id": WEB_B, "ttp": "T1486", "context": {}},
                             "action": "snapshot", "dry_run": False, "escalation_reason": "low", "confidence": 0.4,
                             "suggested_steps": [], "explanation": "", "reasoning": ""})
    assert any(f"`glorfindel snapshot {RG_B}/web --yes`" in s for s in seen["suggested_steps"]), seen
    assert not any(WEB_B in s for s in seen["suggested_steps"])


# Every command to copy written in the tree names its VM through `group_and_name` (or, in the CLI, the
# bot and the TUI, a name their own code made by it): a new one written with a VM's id or its name
# alone fails here. Commands cut over two lines of source are read by the tests above.
_COMMAND = re.compile(r"glorfindel (?:release|reset|revert|restore|activate|snapshot|unblock \{[^}]*\}|unblock \S+)"
                      r" \{([^}]*)\}")
_MADE_BY_IT = {
    "glorfindel/agent.py": {"vm"},                          # vm = group_and_name(rid)
    "glorfindel/bot.py": {"vm", "rid"},                     # rid = _vm_for_a_command(...) = group_and_name
    "glorfindel/tui.py": {"vm_arg"},                        # vm_arg = group_and_name(...)
    "glorfindel/cli.py": {"rid", "_esc_markup(target)",     # _name_for_a_command(...)
                          "_esc_markup(_name_for_a_command(job.get('resource_id') or resource_id))"},
}


def test_every_command_to_copy_in_the_tree_names_its_vm_by_its_group_and_name():
    found = []
    for path in sorted((ROOT / "glorfindel").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for m in _COMMAND.finditer(path.read_text(encoding="utf-8")):
            expr = m.group(1)
            found.append(rel)
            assert expr.startswith("group_and_name(") or expr in _MADE_BY_IT.get(rel, set()), (rel, m.group(0))
    # The guard reads them: the watch's cards and the CLI's, the card « exécutée », the TUI's.
    for rel in ("glorfindel/agent.py", "glorfindel/reassert.py", "glorfindel/recovery_watch.py",
                "glorfindel/readiness.py", "glorfindel/cli.py", "glorfindel/tui.py", "glorfindel/bot.py"):
        assert rel in found, rel


# ── 6. The console's 📋 Command ─────────────────────────────────────────────────────────────────

def _js_function(name: str) -> str:
    js = (ROOT / "eregion_console/static/glorfindel.js").read_text(encoding="utf-8")
    start = js.index(name)
    return js[start:js.index("\n}\n", start) + 2]


def test_the_console_s_command_names_the_vm_by_its_group_and_name():
    """The console's 📋 Command follows the same rule (its `_vmArg`, glorfindel/vm_command.py's): no
    command of `cliCommand` names a VM by `rid.split('/').pop()` nor by its full id."""
    helper = _js_function("function _vmArg(rid)")
    assert "'resourcegroups'" in helper and "'virtualmachines'" in helper and "'<id: glorfindel list --ids>'" in helper
    assert "`'${pair.replace(/'/g, `'\"'\"'`)}'`" in helper                 # quoted for the shell
    cmd = _js_function("function cliCommand(esc)")
    assert "split('/').pop()" not in cmd, cmd
    assert not re.search(r"glorfindel (?:release|reset|revert|restore|activate|snapshot|isolate)\s+\$\{rid\}", cmd), cmd
    assert cmd.count("const vm = _vmArg(rid);") == 2
    for line in ("glorfindel restore ${_vmArg(rid)} --yes --before", "glorfindel activate ${_vmArg(rid)}`",
                 "glorfindel revert ${_vmArg(rid)} --yes"):
        assert line in cmd, line
