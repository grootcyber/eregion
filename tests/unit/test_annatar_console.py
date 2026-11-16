"""SEC-Fa (#852): what Annatar prints from the outside is said as it is, and no print fails a run.

Each path below gets, from the outside, a closing tag with no opening one (Rich raises on it), valid
markup (Rich would apply it) and a terminal escape sequence (the terminal would obey it). The paths:
a target VM's Run Command output, Stratus's output, a phase's error, a refusal quoting a tag of the
cloud, a preflight issue, what the return channel holds, a run's report, a campaign's fields, a
scenario's step, a scenario listed, an operational failure. Each is said as it is: the tags as text,
the escape shown (`\\x1b`), the line's own markup still applied, and what the run keeps unaltered.

The guards at the end read the whole package: one console, no exception printed without `outside`,
no bracket of the code around a raw value. No Azure, no model: fakes and dry_run throughout.
"""
from __future__ import annotations

import ast
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from rich.console import Console
from rich.table import Table

import annatar
from annatar.console import AnnatarConsole, outside
from annatar.runner.engine import Engine

TAG = "[/x] [bold]b[/bold] \x1b[2J"        # what the outside sends
SAID = "[/x] [bold]b[/bold] \\x1b[2J"      # what the operator reads


def _screen(monkeypatch, *modules: str) -> AnnatarConsole:
    """Annatar's console, recorded and wide, in place of the given modules' own."""
    screen = AnnatarConsole(file=io.StringIO(), width=500, record=True, emoji=False)
    for module in modules:
        monkeypatch.setattr(f"{module}.console", screen)
    return screen


def _said(screen: AnnatarConsole) -> str:
    """What the screen shows: the outside's words as they are, no escape sequence obeyed."""
    text = screen.export_text()
    assert SAID in text, text
    assert "\x1b" not in text, text
    return text


# ── outside() and the console ──────────────────────────────────────────────────────────────

def test_outside_says_the_tags_and_shows_the_controls():
    plain = Console(file=io.StringIO(), width=500, record=True)
    plain.print(f"[red]{outside(TAG)}[/red]")
    assert plain.export_text() == SAID + "\n"     # even through a console that is not Annatar's
    assert outside("\x9b2J") == "\\x9b2J"         # a one-byte CSI (C1) is shown too
    assert outside("a\tb\nc") == "a\tb\nc"        # a tab and a newline stay what they are
    assert outside(ValueError("[/x]")) == "\\[/x]"   # an exception, by its text


def test_the_console_never_fails_a_run_on_markup():
    from annatar.console import console

    table = Table()
    table.add_column("c")
    table.add_row("[/x]")
    with console.capture() as captured:
        console.print("[bold]fine[/bold]")
        console.print("[bold]ok[/bold] [/x]")
        console.rule("[/x]")
        console.print(table)
        console.print(":x:")
    out = captured.get()
    assert "fine" in out and "[bold]fine" not in out   # valid markup is still markup
    assert "[bold]ok[/bold] [/x]" in out               # the string Rich cannot read: said as it is
    assert out.count("[/x]") == 3                      # a print, a rule's title, a table's cell
    assert ":x:" in out                                # an emoji code stays a code


# ── What a target answers ──────────────────────────────────────────────────────────────────

def _vm_executor(message: str):
    from annatar.executors.azure_vm import AzureVMExecutor

    ex = object.__new__(AzureVMExecutor)   # no credential, no client: a fake Compute below
    ex.resource_group, ex.vm_name = "rg-bench", "vm-bench"
    result = SimpleNamespace(value=[SimpleNamespace(message=message)])
    ex._compute = SimpleNamespace(virtual_machines=SimpleNamespace(
        begin_run_command=lambda *a, **k: SimpleNamespace(result=lambda: result)))
    return ex


def test_what_a_vm_answers_is_said_as_it_is(monkeypatch):
    screen = _screen(monkeypatch, "annatar.executors.azure_vm")
    assert _vm_executor(TAG)._run_shell("true", "probe") == TAG   # the run reads what the VM said
    _said(screen)


def test_a_failed_integrity_check_says_the_vm_s_output_as_it_is(monkeypatch):
    screen = _screen(monkeypatch, "annatar.executors.azure_vm")
    ex = _vm_executor(TAG)
    monkeypatch.setattr(ex, "run_script", lambda path: TAG)
    assert ex.verify_restore_integrity() is False
    _said(screen)


def test_what_stratus_answers_is_said_as_it_is(tmp_path, monkeypatch):
    from tests.unit.test_annatar_stratus import _executor

    screen = _screen(monkeypatch, "annatar.executors.stratus_host")
    answered = lambda argv, **kw: SimpleNamespace(returncode=0, stdout=TAG, stderr="")  # noqa: E731
    assert _executor(tmp_path, run=answered).run_phase("warmup") == TAG
    _said(screen)


def test_a_phase_that_fails_on_the_outside_s_words_fails_as_itself(tmp_path, monkeypatch):
    from tests.unit.test_annatar_stratus import _fake_executor, _scenario

    monkeypatch.chdir(tmp_path)
    screen = _screen(monkeypatch, "annatar.runner.engine")
    fake, resolved, calls = _fake_executor(tmp_path)

    def warmup():
        calls.append("warmup")
        raise RuntimeError(TAG)

    fake.warmup = warmup
    with pytest.raises(RuntimeError) as raised:
        Engine()._run_stratus_cycle(_scenario(), fake, "20260101T000040Z", resolved)
    assert str(raised.value) == TAG          # the phase's own error, never a MarkupError of its print
    assert "cleanup" in calls                # and the teardown still ran
    assert f"Stratus phase failed: RuntimeError: {SAID}" in _said(screen)


# ── What the cloud and the channel say ─────────────────────────────────────────────────────

BENCH = {"eregion-target": "celebrimbor", "eregion-zone": "bench"}


def test_a_refusal_quoting_a_tag_of_the_cloud_says_it_as_it_is(tmp_path, monkeypatch):
    from tests.unit.test_engine import EXFIL_YAML, _make_executor, _run

    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")   # the bench's perimeter
    screen = _screen(monkeypatch, "annatar.runner.engine")
    executor = _make_executor(tags=BENCH, vm_tags={**BENCH, "eregion-zone": TAG})
    outcome = _run(tmp_path, monkeypatch, executor, EXFIL_YAML)
    assert outcome.refused and TAG in outcome.error   # the outcome keeps the words; the screen escapes
    assert "Safety check failed: " in _said(screen)
    executor.run_script.assert_not_called()


def test_a_preflight_issue_is_said_as_it_is(tmp_path, monkeypatch):
    from tests.unit.test_engine import EXFIL_YAML, _make_executor, _run

    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-123")
    screen = _screen(monkeypatch, "annatar.runner.engine")
    executor = _make_executor()
    executor.check_preflight.return_value = [f"VM held ({TAG})"]
    outcome = _run(tmp_path, monkeypatch, executor, EXFIL_YAML)
    assert outcome.error == "preflight failed"
    assert f"✗ VM held ({SAID})" in _said(screen)


def test_a_detection_the_channel_refuses_is_said_as_it_is(monkeypatch):
    screen = _screen(monkeypatch, "annatar.runner.engine")
    monkeypatch.setattr("annatar.runner.engine.watch_channel.vouched_detections",
                        lambda run_id: ([], [TAG], 1))
    assert Engine()._vouched("r1") == []
    _said(screen)


def test_a_run_s_report_says_what_its_file_holds_as_it_is(monkeypatch):
    from annatar.runner.report import RunReport

    screen = _screen(monkeypatch, "annatar.runner.report")
    RunReport(scenario="s", run_id="r1", mitre="T1486", result="PASS", thresholds={}, checks={},
              metrics={"detection": TAG, "detection_refused": [TAG]}).render()
    text = _said(screen)
    assert f"Detection: {SAID}" in text
    assert f"  - {SAID}" in text


# ── What a scenario, a campaign and the CLI say ────────────────────────────────────────────

def test_a_step_s_action_is_shown_between_its_brackets(monkeypatch):
    from annatar.runner.parser import Scenario

    screen = _screen(monkeypatch, "annatar.runner.engine")
    scenario = Scenario(name="n", description="", mitre="T1486", version="1.0.0",
                        target={"type": "azure_vm", "resource_group": "rg"}, setup=[],
                        steps=[{"action": "attack", "name": TAG}], detection={},
                        detection_hints={}, raw={})
    Engine(dry_run=True)._dry_run_display(scenario)
    assert f"1. [attack] {SAID}" in _said(screen)   # the action was read as a tag, and vanished


def test_a_campaign_s_state_is_shown_between_its_brackets(tmp_path, monkeypatch):
    from annatar.campaign.manifest import Budget, CampaignManifest, Scope, campaign_dir
    from annatar.cli import cli

    m = CampaignManifest(campaign_id="c-1", objective=TAG,
                         scope=Scope(subscription_id="s", allowed_resource_groups=["rg"]),
                         budget=Budget(max_scenarios=1))
    m.save(campaign_dir(m.campaign_id, runs_dir=tmp_path))
    screen = _screen(monkeypatch, "annatar.cli")
    for args in (["campaign", "list"], ["campaign", "show", "c-1"]):
        res = CliRunner().invoke(cli, [*args, "--runs-dir", str(tmp_path)])
        assert res.exit_code == 0, res.output
    text = screen.export_text()
    assert "c-1  [planned]  0 scenario(s)" in text   # the state was read as a tag, and vanished
    assert "objective='[/x] [bold]b[/bold] \\x1b[2J'" in text and "[bold]c-1" not in text


def test_a_scenario_listed_is_said_as_it_is(tmp_path, monkeypatch):
    from annatar.runner.parser import list_available

    root = tmp_path / "annatar" / "scenarios"
    (root / "azure").mkdir(parents=True)
    (root / "azure" / "s.yaml").write_text(
        'name: "[/x] [bold]b[/bold] \\e[2J"\ndescription: d\nmitre: T1486\n'
        "target:\n  type: azure_vm\n  resource_group: rg\nsteps: []\n")
    monkeypatch.setattr("annatar.runner.parser.scenarios_root", lambda: root)
    screen = _screen(monkeypatch, "annatar.runner.parser")
    list_available()
    _said(screen)


def test_a_refusal_busy_says_the_holder_as_it_is(tmp_path, monkeypatch):
    """A run and a campaign refused busy: the lock's holder, as it is (#358). Valid markup this time —
    the console's fallback reads an unreadable string as it is, so only valid markup tells an escaped
    holder from a raw one (the lock already drops the controls)."""
    from annatar.cli import cli
    from eregion_core.exercise_runner import request_lock
    from tests.unit.test_campaign_runner import _cli_campaign
    from tests.unit.test_engine import EXFIL_YAML

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Engine, "run", lambda self, path, skip_confirm=False: None)
    screen = _screen(monkeypatch, "annatar.cli")
    with request_lock("request [bold]b[/bold]"):
        assert CliRunner().invoke(cli, ["run", EXFIL_YAML, "--yes"]).exit_code == 1
        res, ran, _ = _cli_campaign(tmp_path, monkeypatch, "--yes")
    assert res.exit_code == 1 and ran == []
    assert screen.export_text().count("busy: request [bold]b[/bold] runs") == 2


def test_an_operational_failure_is_said_as_it_is(monkeypatch):
    from annatar.cli import cli

    def fails():
        raise RuntimeError(TAG)

    monkeypatch.setattr("annatar.runner.parser.list_available", fails)
    screen = _screen(monkeypatch, "annatar.cli")
    res = CliRunner().invoke(cli, ["list"])
    assert res.exit_code == 1
    assert f"✗ RuntimeError: {SAID}" in _said(screen)


# ── The guards: the whole package, read ────────────────────────────────────────────────────

PKG = Path(annatar.__file__).parent
SINKS = {"print", "rule", "log"}
# A literal `[` right before a raw value makes a tag of it: Rich drops it, or applies it. The few
# the code means, with why.
BRACKETED: dict[tuple[str, str], str] = {
    ("runner/report.py", "color"): "the style the code chose (green, red): its own markup",
    ("cli.py", "e.seq"): "an int: Rich reads no tag from a digit",
    ("campaign/runner.py", "entry.seq"): "an int: Rich reads no tag from a digit",
    ("campaign/runner.py", "e.seq"): "an int: Rich reads no tag from a digit",
}


def _modules():
    for path in sorted(PKG.rglob("*.py")):
        yield path.relative_to(PKG).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _is_call(node, name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


def _sinks(tree):
    """Each call that writes to the terminal: console.print/rule/log, a table's add_row."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (
                (node.func.attr in SINKS and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == "console") or node.func.attr == "add_row"):
            yield node


def test_annatar_prints_through_its_one_console():
    found = []
    for rel, tree in _modules():
        if rel == "console.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("rich"):
                names = {a.name for a in node.names}
                if names & {"Console", "get_console", "print", "escape"}:
                    found.append(f"{rel}:{node.lineno}: from {node.module} import {sorted(names)}")
            elif isinstance(node, ast.Call) and (
                    (isinstance(node.func, ast.Name) and node.func.id == "Console")
                    or (isinstance(node.func, ast.Attribute) and node.func.attr == "Console")):
                found.append(f"{rel}:{node.lineno}: a Console of its own")
    assert not found, "annatar.console is Annatar's one console, and outside() its one escape:\n" + "\n".join(found)


def _raw(node, name: str) -> int:
    """The uses of `name` in `node` that no outside(…) holds — type(name).__name__ aside."""
    if _is_call(node, "outside"):
        return 0
    if isinstance(node, ast.Attribute) and node.attr == "__name__" and _is_call(node.value, "type"):
        return 0
    if isinstance(node, ast.Name) and node.id == name:
        return 1
    return sum(_raw(child, name) for child in ast.iter_child_nodes(node))


def test_no_exception_is_printed_without_outside():
    found = []
    for rel, tree in _modules():
        for handler in ast.walk(tree):
            if not (isinstance(handler, ast.ExceptHandler) and handler.name):
                continue
            for stmt in handler.body:
                for sink in _sinks(stmt):
                    if any(_raw(arg, handler.name) for arg in [*sink.args, *(k.value for k in sink.keywords)]):
                        found.append(f"{rel}:{sink.lineno}: {ast.unparse(sink)[:100]}")
    assert not found, "an exception quotes the outside: print it through outside():\n" + "\n".join(found)


def test_no_bracket_of_the_code_holds_a_raw_value():
    found = []
    for rel, tree in _modules():
        for sink in _sinks(tree):
            for fstr in (n for arg in sink.args for n in ast.walk(arg) if isinstance(n, ast.JoinedStr)):
                for before, value in zip(fstr.values, fstr.values[1:]):
                    if not (isinstance(before, ast.Constant) and isinstance(value, ast.FormattedValue)):
                        continue
                    # outside() is no help here: `attack` escaped is still `attack`, and `[attack]` a tag
                    expr = ast.unparse(value.value)
                    if (before.value.endswith("[") and not before.value.endswith("\\[")
                            and (rel, expr) not in BRACKETED):
                        found.append(f"{rel}:{sink.lineno}: [{{{expr}}}")
    assert not found, "a value between the code's brackets is read as a tag: write \\\\[:\n" + "\n".join(found)
