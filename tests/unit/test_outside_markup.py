"""SEC-F (#845) — text from outside is never markup, and the decision thread of a VM never dies.

The watch, the CLI, the bot and the TUI print with Rich, which reads its strings as markup. Text
from outside — the model's action, the fields of a line an injector wrote, the fields of the cards'
store, a Discord member's name, an exception — is said as it is (`glorfindel/terminal.py`):

1. A value printed is escaped where it is printed; the console never raises on markup (the last
   guard); an error is said escaped, and its saying never raises in turn.
2. The watch's decision thread of a VM: a display that fails never leaves a detection undecided,
   and whatever one detection raised leaves the thread to take the next one.
3. The admission of a line of runs/: its gravity in a closed list, its signal id and resource type
   of a bounded form — out of it, the line is refused and said.
4. The bot: one card never stops the others, nor the notices, nor the heartbeat; the loop's task,
   ended by an error, is said and started again; a click refused is answered and logged whatever
   the clicker's name. Its commands to copy quote every argument, its ``` block is never closed by
   what it holds.
5. `glorfindel pending` and the TUI: every card shown, its fields as they are; one card that cannot
   be shown never hides the next; the TUI's commands quoted.

Each path has its control at normal values. The values below are made up (repository public); no
Azure call, no model call. Mutants M5701–M5720 (scripts/mutants/SEC-F.py) are measured here.

6. SEC-Fc (#907), the rest of SEC-F's review: Azure's poll error said as it is, the search going
   on; a decision taken whose display fails said as such; the name in `pending`'s `az vm show`
   quoted; the TUI's panels never handing a control character to the terminal. Mutants
   M6271–M6290 (scripts/mutants/SEC-Fc.py).
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import shlex
import threading
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from rich.console import Console
from rich.text import Text

from glorfindel import escalations, signal_origin, terminal

VM = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/web"
# A tag that opens (obeyed if read as markup), then one that closes nothing (MarkupError).
EVIL = "[blink]z[/blink][/x]"


def _plain(text: str) -> str:
    """What a console printed, the values from outside taken out: no markup of its own may remain."""
    return text.replace(EVIL, "")


def _row(label: str, value: str, out: str) -> bool:
    """A table's row « label   value » in what a console printed."""
    return re.search(rf"{label}\s+{re.escape(value)}", out) is not None


def _console() -> tuple[Console, io.StringIO]:
    """A plain Rich console — no guard of its own: an escape missing raises, as Rich does."""
    buf = io.StringIO()
    return Console(file=buf, width=300, color_system=None, emoji=False), buf


# ── 1. terminal.py: outside(), the console, say_failure ─────────────────────────────────────────

def test_outside_says_markup_and_controls_as_they_are():
    console, buf = _console()
    console.print(f"[bold]a[/bold] {terminal.outside(EVIL + chr(0x1b) + '[2J' + chr(0x9b))}")
    out = buf.getvalue()
    assert f"a {EVIL}\\x1b[2J\\x9b" in out
    assert "\x1b" not in out and "\x9b" not in out
    assert terminal.outside(None) == "" and terminal.outside(42) == "42"


def test_the_console_never_raises_on_markup():
    buf = io.StringIO()
    console = terminal.GlorfindelConsole(file=buf, width=300, color_system=None)
    from rich.table import Table
    table = Table()
    table.add_column("c")
    table.add_row(f"cell {EVIL}")
    console.print(f"[red]line {EVIL}[/red]")
    console.rule(f"rule {EVIL}")
    console.print(table)
    out = buf.getvalue()
    assert "line" in out and "rule" in out and "cell" in out and "[/x]" in out


def test_an_error_is_said_escaped_and_its_saying_never_raises(capsys):
    console, buf = _console()
    terminal.say_failure(console, f"head {EVIL}", RuntimeError(EVIL))
    assert buf.getvalue().strip() == f"head {EVIL} : {EVIL}"

    class Broken:
        def print(self, *a, **k):
            raise OSError("terminal gone")
    terminal.say_failure(Broken(), "head", RuntimeError("x" + chr(0x1b)))     # never raises
    assert "head : x\\x1b" in capsys.readouterr().err


# ── 2. the watch, end to end: its decision thread of a VM ───────────────────────────────────────

def _line(signal_id: str, **over) -> dict:
    sig = {"signal_id": signal_id, "timestamp": "2026-11-13T10:00:00+00:00", "provider": "azure",
           "resource_id": VM, "resource_type": "vm", "ttp": "T1486", "severity": "high",
           "event": "detection_missed", "raw_signal": {}, "context": {"run_id": "20261113T100000Z"}}
    sig.update(over)
    return sig


def _watch(tmp_path, monkeypatch, lines, decide, expect, admit_all=False):
    """The real watch (dry-run) on tmp_path/runs, HOME in tmp_path, its real display of a signal
    and of a decision on a plain console; `lines` appended to runs/annatar/ once it runs; the
    model simulated by `decide(data)` (a state). `admit_all`: what an injector wrote reaches the
    decision thread as it is — the admission's checks set aside, as for a signal of another path
    (the RulePoller's, a file given to `respond`): the display is proven on its own.
    Returns (what reached the model, what the watch printed)."""
    from click.testing import CliRunner

    from eregion_core.signals import Signal
    from glorfindel import cli
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(cli, "_INJECTORS_DIR", home / ".glorfindel" / "injectors")
    runs = tmp_path / "runs"
    signals = runs / "annatar"
    signals.mkdir(parents=True)
    console, buf = _console()
    monkeypatch.setattr(cli, "console", console)
    responded: list[dict] = []

    class _Agent:
        def __init__(self, **kw):
            self.autonomy = SimpleNamespace(default="human_only", assets=[])
            self.config_error = ""
            self.connector = SimpleNamespace(permission_mode=lambda: "read_write")

        def respond(self, data):
            responded.append(data)
            return decide(data)

    monkeypatch.setattr("glorfindel.agent.GlorfindelAgent", _Agent)
    monkeypatch.setattr(cli, "_find_rules_file", lambda: None)
    monkeypatch.setattr("eregion_core.inscription.TagEnrollment", lambda *a, **k: (lambda rid: True))
    if admit_all:
        monkeypatch.setattr(cli, "_admit_from_runs", lambda data, source: (
            data, Signal(**{k: data.get(k, "") for k in Signal.__dataclass_fields__})))
    import atexit
    import signal as signalmod
    monkeypatch.setattr(atexit, "register", lambda *a, **k: None)
    monkeypatch.setattr(signalmod, "signal", lambda *a, **k: None)
    real_sleep = time.sleep
    calls = [0]

    def _sleep(s):
        if threading.current_thread() is not threading.main_thread():
            return real_sleep(s)
        calls[0] += 1
        if calls[0] == 1:
            with open(signals / "run_signals.jsonl", "a") as f:
                for line in lines:
                    f.write(json.dumps(line) + "\n")
            return
        if calls[0] == 2:
            deadline = time.monotonic() + 10
            while len(responded) < expect and time.monotonic() < deadline:
                real_sleep(0.05)
            real_sleep(0.3)                    # what else would arrive, given the time
            raise KeyboardInterrupt
        return real_sleep(0)

    monkeypatch.setattr(cli.time, "sleep", _sleep)
    result = CliRunner().invoke(cli.cli, ["watch", str(runs), "--dry-run", "--interval", "0"])
    assert result.exit_code == 0, result.output
    return responded, buf.getvalue()


def _decided(action="isolate_vm", **over) -> dict:
    return {"action": action, "escalate": False, "confidence": 0.5, "outcome": {},
            "explanation": "", "reasoning": "", **over}


def test_a_signal_and_a_decision_from_outside_are_shown_as_they_are_and_the_next_one_decided(
        tmp_path, monkeypatch):
    """The model's action, the line's signal id, gravity and resource type: each a tag that closes
    nothing. Shown as they are; the next detection of the VM decided too."""
    lines = [_line(EVIL, severity=EVIL, resource_type=EVIL), _line("next_detection_missed")]
    actions = iter([EVIL, "isolate_vm"])
    responded, out = _watch(tmp_path, monkeypatch, lines, lambda d: _decided(next(actions)), 2,
                            admit_all=True)
    assert [d["signal_id"] for d in responded] == [EVIL, "next_detection_missed"]
    assert f"Signal — {EVIL}" in out
    assert f"Severity: {EVIL}" in out and f"Resource: {EVIL}" in out
    assert _row("Decision", EVIL, out)
    assert "en erreur" not in out and "Error processing" not in out
    assert "[/" not in _plain(out)                                    # no markup of its own left


def test_the_control_at_normal_values(tmp_path, monkeypatch):
    lines = [_line("first_detection_missed"), _line("next_detection_missed")]
    responded, out = _watch(tmp_path, monkeypatch, lines, lambda d: _decided(), 2)
    assert [d["signal_id"] for d in responded] == ["first_detection_missed", "next_detection_missed"]
    assert "Signal — first_detection_missed" in out and _row("Decision", "isolate_vm", out)
    assert "en erreur" not in out and "Error processing" not in out


def test_a_display_that_fails_never_leaves_the_detection_undecided(tmp_path, monkeypatch):
    from glorfindel import cli

    def _broken(sig):
        raise RuntimeError(f"head {EVIL}")
    monkeypatch.setattr(cli, "_signal_head", _broken)
    lines = [_line("first_detection_missed"), _line("next_detection_missed")]
    responded, out = _watch(tmp_path, monkeypatch, lines, lambda d: _decided(), 2)
    assert [d["signal_id"] for d in responded] == ["first_detection_missed", "next_detection_missed"]
    assert out.count(f"Affichage du signal en erreur : head {EVIL}") == 2


def test_whatever_one_detection_raised_the_thread_takes_the_next(tmp_path, monkeypatch):
    """The model's call raising (a tag in what it said), then its display failing: the thread lives,
    the error said escaped, the next detection of the VM decided. A display that fails after the
    decision is said as such (SEC-Fc), never « Error processing »."""
    def decide(data):
        if data["signal_id"] == "first_detection_missed":
            raise RuntimeError(EVIL)
        if data["signal_id"] == "second_detection_missed":
            return _decided(confidence=EVIL)               # its display fails: not a number
        return _decided()
    lines = [_line("first_detection_missed"), _line("second_detection_missed"),
             _line("next_detection_missed")]
    responded, out = _watch(tmp_path, monkeypatch, lines, decide, 3)
    assert [d["signal_id"] for d in responded] == [
        "first_detection_missed", "second_detection_missed", "next_detection_missed"]
    assert f"Error processing first_detection_missed : {EVIL}" in out
    assert "Error processing second_detection_missed" not in out
    assert "Décision prise pour second_detection_missed, son affichage a échoué" in out
    assert "Signal — next_detection_missed" in out


# ── 3. the admission of a line of runs/ ─────────────────────────────────────────────────────────

def _admit(**over):
    line = {**_line("20261113T100000Z_detection_missed"), **over}
    return signal_origin.admit(line, known={"T1486"}, workspaces=frozenset())


@pytest.mark.parametrize("field, value", [
    ("severity", EVIL), ("severity", "urgent"), ("severity", 3), ("signal_id", EVIL),
    ("signal_id", "a b"), ("signal_id", ["x"]), ("signal_id", "x" * 201), ("resource_type", EVIL),
    ("resource_type", "vm\n"), ("resource_type", 7)])
def test_a_line_whose_gravity_id_or_type_is_out_of_form_is_refused(field, value):
    adm = _admit(**{field: value})
    assert adm.signal is None and adm.refused


@pytest.mark.parametrize("over", [
    {}, {"severity": "high"}, {"severity": "medium"}, {"severity": "low"}, {"severity": ""},
    {"resource_type": "azure_vm"}, {"resource_type": "Microsoft.Compute/virtualMachines"},
    {"signal_id": "20261113T100000Z_attack_started"}, {"signal_id": "watch-rule:01.2"},
    {"signal_id": ""}, {"resource_type": ""}])
def test_the_control_a_line_of_the_injectors_form_is_admitted(over):
    adm = _admit(**over)
    assert adm.signal is not None, adm.refused


def test_the_watch_refuses_such_a_line_says_it_and_decides_the_next(tmp_path, monkeypatch):
    lines = [_line("bad_detection_missed", resource_type=EVIL), _line("next_detection_missed")]
    responded, out = _watch(tmp_path, monkeypatch, lines, lambda d: _decided(), 1)
    assert [d["signal_id"] for d in responded] == ["next_detection_missed"]
    assert "Signal refusé (run_signals.jsonl) : type de ressource hors forme" in out
    assert "[/" not in _plain(out)


# ── 4. the bot ──────────────────────────────────────────────────────────────────────────────────

def _bot_console(monkeypatch):
    pytest.importorskip("discord")
    from glorfindel import bot
    console, buf = _console()
    monkeypatch.setattr(bot, "_console", console)
    return bot, buf


def _card(esc_id: str, action: str = "isolate_vm", **over) -> dict:
    card = {"id": esc_id, "action": action, "resource_id": VM, "escalation_type": "mode_hold",
            "status": "pending", "timestamp": "2026-11-13T10:00:00+00:00", "reason": "r", "run_id": ""}
    card.update(over)
    return card


def _bot_turns(monkeypatch, cards_by_turn: dict, fails: set, turns: int = 2):
    """The bot's loop for `turns` turns, its posts recorded (turn, card id) — a card of `fails`
    raising in its post, as Discord would; its notices by turn. Returns (posted, notices, log)."""
    bot, buf = _bot_console(monkeypatch)
    from glorfindel import bot_beat
    b = bot.GlorfindelBot(channel_id=1, ping_role=None)
    turn = {"n": 0}
    posted: list = []
    notices: list = []

    async def sleep(_s):
        turn["n"] += 1
        if turn["n"] > turns:
            raise asyncio.CancelledError

    async def post(_channel, esc):
        if esc["id"] in fails:
            raise RuntimeError(EVIL)
        posted.append((turn["n"], esc["id"]))

    async def note(_channel):
        notices.append(turn["n"])
        return 0

    async def nothing(*a, **k):
        return 0
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    monkeypatch.setattr(b, "get_channel", lambda _id: type("C", (), {"name": "alerts"})())
    monkeypatch.setattr(b, "_post_escalation", post)
    monkeypatch.setattr(b, "_post_notices", note)
    monkeypatch.setattr(b, "_post_weekly", nothing)
    monkeypatch.setattr(bot.esc_module, "pending", lambda: cards_by_turn.get(turn["n"], []))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(b._watch_escalations())
    assert bot_beat.mute() == ""                                     # its heartbeat written
    return posted, notices, buf.getvalue()


def test_a_card_from_outside_never_stops_the_bot_s_loop(monkeypatch):
    """A card whose action is a tag, one whose post fails on a tag: the others posted in the same
    turn, the notices and the next turn's card too."""
    cards = {1: [_card("evil0001", EVIL), _card("boom0002"), _card("good0003")],
             2: [_card("next0004")]}
    posted, notices, log = _bot_turns(monkeypatch, cards, {"boom0002"})
    assert posted == [(1, "evil0001"), (1, "good0003"), (2, "next0004")]
    assert notices == [1, 2]
    assert f"✓ Posted evil0001 ({EVIL})" in log
    assert f"Bot post error : {EVIL}" in log
    assert "[/" not in _plain(log)


def test_the_control_the_bot_s_loop_at_normal_values(monkeypatch):
    posted, notices, log = _bot_turns(monkeypatch, {1: [_card("good0001")], 2: [_card("next0002")]},
                                      set())
    assert posted == [(1, "good0001"), (2, "next0002")] and notices == [1, 2]
    assert "error" not in log.lower()


def test_the_bot_s_loop_ended_by_an_error_is_said_and_started_again(monkeypatch):
    bot, buf = _bot_console(monkeypatch)
    b = bot.GlorfindelBot(channel_id=1, ping_role=None)
    calls: list = []

    async def once():
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError(EVIL)
        if len(calls) == 2:
            return                                   # a loop that ended: started again too
        raise asyncio.CancelledError
    monkeypatch.setattr(b, "_watch_escalations", once)
    real_sleep = asyncio.sleep
    monkeypatch.setattr(bot.asyncio, "sleep", lambda _s: real_sleep(0))

    async def go():
        b.loop = asyncio.get_running_loop()
        await b.on_ready()
        first = b.bg_task
        await b.on_ready()                           # a reconnection: never a second loop
        assert b.bg_task is first
        with pytest.raises(asyncio.CancelledError):
            await first
    asyncio.run(go())
    assert len(calls) == 3
    out = buf.getvalue()
    assert f"Boucle du bot arrêtée — relancée dans 5 s : {EVIL}" in out
    assert "Boucle du bot arrêtée — relancée dans 5 s : la boucle a rendu la main" in out


def _press_refused(monkeypatch, name: str, console=None):
    bot, buf = _bot_console(monkeypatch)
    if console is not None:
        monkeypatch.setattr(bot, "_console", console)
    from .test_bot import STRANGER, ALLOWED, _press, _stored, _User, _verdict_right
    esc_id = escalations.record("rule-ssh-brute-force-0123abcd", VM, "block_suspicious_ip",
                                "mode_hold", "held", confidence=0.95)
    user = _User(STRANGER)
    user.display_name = name
    click = _press(_stored(esc_id), user, bot.ButtonPolicy(users=frozenset({ALLOWED})), _verdict_right)
    return click, buf.getvalue(), _stored(esc_id)


@pytest.mark.parametrize("name", [EVIL, "an operator"])
def test_a_click_refused_is_answered_and_logged_whatever_the_name(monkeypatch, name):
    click, log, stored = _press_refused(monkeypatch, name)
    assert stored.get("verdict") is None                              # nothing done
    assert len(click.ephemeral) == 1 and click.ephemeral[0][0].startswith("✗ Bouton refusé")
    assert f"Button refused: user 222 ({name}) on " in log
    assert "[/" not in _plain(log)


def test_a_click_refused_is_answered_even_when_its_log_fails(monkeypatch, capsys):
    class Broken:
        def print(self, *a, **k):
            raise OSError("terminal gone")
    click, _log, _stored_card = _press_refused(monkeypatch, "an operator", console=Broken())
    assert len(click.ephemeral) == 1 and click.ephemeral[0][0].startswith("✗ Bouton refusé")
    assert "terminal gone" in capsys.readouterr().err


FORGED = "203.0.113.9;$(touch /tmp/x)`id`"


def _args_after(command: str, word: str) -> str:
    tokens = shlex.split(command)
    return tokens[tokens.index(word) + 1]


def test_each_argument_of_the_bot_s_command_is_quoted_for_the_shell():
    pytest.importorskip("discord")
    from glorfindel import bot
    undo = bot._cli_command(_card("c1", "block_suspicious_ip", escalation_type=escalations.EXECUTED_TYPE,
                                  action_params={"ip": FORGED}))
    assert _args_after(undo.splitlines()[2], "unblock") == FORGED
    restore = bot._cli_command(_card("c2", "restore_from_backup", first_seen=FORGED))
    assert _args_after(restore.splitlines()[1], "--before") == FORGED
    ack = bot._cli_command(_card(FORGED, escalation_type="identity_change"))
    assert shlex.split(ack) == ["glorfindel", "ack", FORGED]


def test_the_control_the_bot_s_command_at_normal_values():
    pytest.importorskip("discord")
    from glorfindel import bot
    undo = bot._cli_command(_card("c1", "block_suspicious_ip", escalation_type=escalations.EXECUTED_TYPE,
                                  action_params={"ip": "203.0.113.9"}))
    assert "glorfindel unblock 203.0.113.9 rg/web --yes" in undo
    restore = bot._cli_command(_card("c2", "restore_from_backup", first_seen="2026-11-13T10:00:00+00:00"))
    assert "--before 2026-11-13T10:00:00+00:00\n" in restore
    assert bot._cli_command(_card("c3", escalation_type="identity_change")) == "glorfindel ack c3"
    assert "<ip>" in bot._cli_command(_card("c4", "block_suspicious_ip",
                                            escalation_type=escalations.EXECUTED_TYPE))


@pytest.mark.parametrize("first_seen", ["2026-11-13T10:00:00+00:00\n```\n@everyone [x](https://e)",
                                        "2026-11-13T10:00:00+00:00"])
def test_the_command_s_block_is_never_closed_by_what_it_holds(first_seen):
    pytest.importorskip("discord")
    from glorfindel import bot
    from .test_bot import _Click, _User

    async def go():
        view = bot.EscalationView(_card("c1", "restore_from_backup", first_seen=first_seen))
        item = next(i for i in view.children if getattr(i, "custom_id", "") == "glorfindel_cmd")
        click = _Click(_User(1), None, "glorfindel_cmd")
        await item.callback(click)
        return click
    text = asyncio.run(go()).ephemeral[0][0]
    assert text.count("```") == 2 and text.rstrip().endswith("```")
    assert "@everyone" not in text


# ── 5. glorfindel pending and the TUI ───────────────────────────────────────────────────────────

def _pending(monkeypatch, cards):
    from click.testing import CliRunner

    from glorfindel import cli
    console, buf = _console()
    monkeypatch.setattr(cli, "console", console)
    monkeypatch.setattr(escalations, "pending", lambda: cards)
    monkeypatch.setattr("glorfindel.proposed_rules.pending", lambda: [])
    result = CliRunner().invoke(cli.cli, ["pending"])
    return result, buf.getvalue()


def test_pending_shows_a_card_from_outside_as_it_is_and_the_next_one(monkeypatch):
    evil = _card("evil0001-aaaa", EVIL, escalation_type=EVIL, run_id=EVIL, reason=EVIL)
    result, out = _pending(monkeypatch, [evil, _card("good0002-bbbb")])
    assert result.exit_code == 0, result.output
    assert _row("Action", EVIL, out) and _row("Run", EVIL, out)
    assert "glorfindel ack good0002-bbbb" in out
    assert "illisible" not in out and "[/" not in _plain(out)


def test_pending_one_card_unreadable_never_hides_the_next(monkeypatch):
    result, out = _pending(monkeypatch, [_card("bad00001-aaaa", timestamp="not a moment"),
                                         _card("good0002-bbbb")])
    assert result.exit_code == 0, result.output
    assert "Carte bad00001 illisible" in out and "glorfindel ack good0002-bbbb" in out


def test_the_control_pending_at_normal_values(monkeypatch):
    result, out = _pending(monkeypatch, [_card("good0001-aaaa"), _card("good0002-bbbb")])
    assert result.exit_code == 0 and "illisible" not in out
    assert "glorfindel ack good0001-aaaa" in out and "glorfindel ack good0002-bbbb" in out


def test_the_tui_feed_shows_a_line_from_outside_as_it_is():
    from glorfindel import tui
    debug = tui._format_debug({"timestamp": EVIL, "action": EVIL, "confidence": 0.5,
                               "signal": {"resource_id": VM, "ttp": EVIL}, "outcome": {}})
    signal = tui._format_signal({"timestamp": EVIL, "event": EVIL, "ttp": EVIL, "resource_id": VM})
    for line in (debug, signal):
        assert Text.from_markup(line).plain.count(EVIL[:16]) >= 2
    assert EVIL in Text.from_markup(debug).plain
    tui._feed_renderable([f"[red]raw {EVIL}", debug], "run")      # one line not markup: never raised


def test_the_control_the_tui_feed_at_normal_values():
    from glorfindel import tui
    line = tui._format_debug({"timestamp": "2026-11-13T10:00:00", "action": "isolate_vm",
                              "confidence": 0.9, "signal": {"resource_id": VM, "ttp": "T1486"},
                              "outcome": {"verified": True}})
    assert "isolate_vm" in Text.from_markup(line).plain and "90%" in Text.from_markup(line).plain


def test_the_tui_quotes_each_argument_of_a_command(monkeypatch):
    from glorfindel import tui
    cards = [_card("abc$(id)x", "restore_from_backup", first_seen=FORGED),
             _card("d e;`id`yz", escalation_type="identity_change")]
    monkeypatch.setattr(escalations, "pending", lambda: cards)
    console = Console(record=True, width=400, file=io.StringIO())
    console.print(tui._escalations_renderable(datetime.now(timezone.utc), None, False))
    text = console.export_text()
    restore = next(line for line in text.splitlines() if "glorfindel restore" in line)
    assert _args_after(restore.split("→", 1)[1].split("#", 1)[0].strip(" │"), "--before") == FORGED
    ack = next(line for line in text.splitlines() if "glorfindel ack" in line)
    assert shlex.split(ack.split("→", 1)[1].strip(" │")) == ["glorfindel", "ack", "d e;`id`"]  # one argument (SEC-Fc)


def test_ack_and_verdict_say_a_card_from_outside_as_it_is(monkeypatch):
    from click.testing import CliRunner

    from glorfindel import cli
    console, buf = _console()
    monkeypatch.setattr(cli, "console", console)
    esc_id = escalations.record("s-1", VM, EVIL, "mode_hold", "held", confidence=0.5)
    assert CliRunner().invoke(cli.cli, ["verdict", esc_id, "right"]).exit_code == 0
    assert CliRunner().invoke(cli.cli, ["ack", esc_id]).exit_code == 0
    out = buf.getvalue()
    assert f"✓ {EVIL} on web: right" in out and f"Escalation {esc_id} acknowledged" in out
    assert "[/" not in _plain(out)


# ── 6. SEC-Fc: the rest of SEC-F's review ───────────────────────────────────────────────────────

class _Workspace:
    """A Log Analytics client: each query raises the next error of `errors`, then answers its row."""

    def __init__(self, errors):
        self.errors = list(errors)
        self.queries = 0

    def query_workspace(self, workspace_id, query, timespan):
        from azure.monitor.query import LogsQueryStatus
        self.queries += 1
        if self.errors:
            raise self.errors.pop(0)
        return SimpleNamespace(status=LogsQueryStatus.SUCCESS, tables=[SimpleNamespace(
            columns=["TimeGenerated", "Computer"], rows=[["2026-11-13T10:00:00Z", "web"]])])


def _detector(monkeypatch, errors):
    """The real Azure Monitor detector on `_Workspace`, its console a plain one (an escape missing
    raises, as Rich does), its wait between two queries none."""
    from glorfindel.providers.azure import monitor
    det = monitor.AzureMonitorDetector("ws-0000")
    det._client = _Workspace(errors)
    console, buf = _console()
    monkeypatch.setattr(monitor, "_console", console)
    monkeypatch.setattr(monitor, "time", SimpleNamespace(time=time.time, sleep=lambda s: None))
    return det, buf


def _search(monkeypatch, det):
    """The search of an attack_started line, as the watch's poll thread runs it."""
    from glorfindel import agent
    monkeypatch.setattr("glorfindel.detectors.detector_for", lambda source, **kw: det)
    return agent.resolve_attack_started({**_line("s-1", event="attack_started"), "raw_signal": {
        "detection_source": "azure_monitor", "detection_query": "Heartbeat | take 1",
        "log_analytics_workspace_id": "ws-0000", "detection_timeout_s": 60,
        "attack_time": time.time()}})


def test_a_poll_error_from_azure_is_said_as_it_is_and_the_search_goes_on(monkeypatch):
    """A transient error whose text holds a tag that closes nothing: said as it is, the next query
    made, the row found — no exception out of the search, so no cycle_failed card."""
    det, buf = _detector(monkeypatch, [RuntimeError(f"throttled {EVIL}")])
    resolved = _search(monkeypatch, det)
    assert resolved["event"] == "detection" and det._client.queries == 2
    assert f"Poll error: throttled {EVIL}" in buf.getvalue()
    assert "[/" not in _plain(buf.getvalue())


def test_the_control_a_poll_error_at_normal_values(monkeypatch):
    det, buf = _detector(monkeypatch, [RuntimeError("throttled (429)")])
    assert _search(monkeypatch, det)["event"] == "detection" and det._client.queries == 2
    assert "Poll error: throttled (429)" in buf.getvalue()


def test_a_decision_whose_display_fails_is_said_taken_never_error_processing(tmp_path, monkeypatch):
    """`_render_decision` raising after the decision: its cycle stored (by `respond`, before the
    display), the failure said as a display's, the next detection of the VM decided."""
    from glorfindel import cli

    def _broken(state, dry_run):
        raise RuntimeError(f"render {EVIL}")
    monkeypatch.setattr(cli, "_render_decision", _broken)
    stored: list[str] = []

    def decide(data):
        stored.append(data["signal_id"])           # what `respond` does before it returns: the cycle
        return _decided()
    lines = [_line("first_detection_missed"), _line("next_detection_missed")]
    responded, out = _watch(tmp_path, monkeypatch, lines, decide, 2)
    assert stored == ["first_detection_missed", "next_detection_missed"]
    assert "Error processing" not in out
    assert (f"Décision prise pour first_detection_missed, son affichage a échoué : render {EVIL}"
            in out)
    assert "Décision prise pour next_detection_missed, son affichage a échoué" in out


def test_pending_s_fallback_steps_quote_the_card_s_name_and_id(monkeypatch):
    """A card without the model's steps (an older one, a dry-run): its `az vm show` names the VM by
    one argument, its ack the card by one — whatever the store holds."""
    name = "we b;id"
    card = _card(FORGED, "snapshot", escalation_type="low_confidence",
                 resource_id=VM.rsplit("/", 1)[0] + "/" + name)
    result, out = _pending(monkeypatch, [card])
    assert result.exit_code == 0, result.output
    show = next(line for line in out.splitlines() if "az vm show" in line)
    assert _args_after(show.split("Check VM state:", 1)[1], "-n") == name
    ack = next(line for line in out.splitlines() if "If false positive:" in line)
    assert shlex.split(ack.split("If false positive:", 1)[1]) == ["glorfindel", "ack", FORGED]


def test_the_control_pending_s_fallback_steps_at_normal_values(monkeypatch):
    result, out = _pending(monkeypatch, [_card("good0001-aaaa", "snapshot",
                                               escalation_type="low_confidence")])
    assert "az vm show -g <rg> -n web --query powerState" in out
    assert "If false positive: glorfindel ack good0001-aaaa" in out


ESC = "\x1b[2J\x1b]8;;https://e\x07x\x9b"


def test_the_tui_s_panels_never_hand_a_control_character_to_the_terminal(monkeypatch):
    """A card's id, action, steps and first detection, a restore's words: each with an escape
    sequence (ESC, a C1 CSI). The panel's text holds none, each shown as `\\x1b`."""
    from glorfindel import tui
    cards = [_card(f"ab{ESC}", f"isolate{ESC}", suggested_steps=[f"look {ESC}"]),
             _card(f"cd{ESC}", "restore_from_backup", first_seen=f"2026{ESC}"),
             _card("ef000003", resource_id=f"{VM}\x1b[2Jx\x9b")]
    monkeypatch.setattr(escalations, "pending", lambda: cards)
    monkeypatch.setattr(tui, "_last_restore", {"text": f"done {ESC}", "rid": VM, "ok": True})
    panel = tui._escalations_renderable(datetime.now(timezone.utc), None, False).renderable
    assert not re.search(r"[\x1b\x9b\x07]", panel.plain)
    assert panel.plain.count("\\x1b") >= 10 and "\\x9b" in panel.plain
    assert "glorfindel restore" in panel.plain and "done \\x1b" in panel.plain
    assert "web\\x1b[2Jx\\x9b" in panel.plain          # the VM's name, from the card
    confirm = tui._escalations_renderable(datetime.now(timezone.utc), {"label": f"ack {ESC}"}, False)
    assert not re.search(r"[\x1b\x9b\x07]", confirm.renderable.plain)
    assert "ack \\x1b" in confirm.renderable.plain
    restore = tui._restore_panel({"esc": cards[1], "stage": "moment", "label": f"restore {ESC}",
                                  "buffer": "2026", "why": f"why {ESC}", "error": f"no {ESC}"})
    assert not re.search(r"[\x1b\x9b\x07]", restore.renderable.plain)
    assert "why \\x1b" in restore.renderable.plain and "no \\x1b" in restore.renderable.plain


def test_the_control_the_tui_s_panels_at_normal_values(monkeypatch):
    from glorfindel import tui
    monkeypatch.setattr(escalations, "pending", lambda: [_card("ab000001-x", "isolate_vm",
                                                                suggested_steps=["look at web"])])
    monkeypatch.setattr(tui, "_last_restore", {})
    plain = tui._escalations_renderable(datetime.now(timezone.utc), None, False).renderable.plain
    assert "[ab000001]" in plain and "isolate_vm" in plain and "• look at web" in plain
    assert "glorfindel ack ab000001" in plain and "\\x" not in plain
