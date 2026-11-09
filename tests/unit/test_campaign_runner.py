"""Campaign runner — sequential execution, budget, scope re-check, kill switch.

Engine + NSG reset are injected (no Azure, no LLM, no subprocess).
"""

import os
import subprocess

import pytest

from annatar.campaign.manifest import (
    Budget,
    CampaignManifest,
    ScenarioEntry,
    Scope,
    campaign_dir,
    new_campaign_id,
)
from annatar.campaign.runner import KILL_SWITCH_SET, KILL_SWITCH_UNREADABLE, CampaignRunner
from annatar.runner.engine import RunOutcome

SANDBOX_VM = (
    "/subscriptions/sub-1/resourceGroups/rg-celebrimbor/providers/"
    "Microsoft.Compute/virtualMachines/vm-celebrimbor-gondolin"
)
PROD_VM = (
    "/subscriptions/sub-1/resourceGroups/rg-prod/providers/"
    "Microsoft.Compute/virtualMachines/vm-prod"
)


class FakeEngine:
    """Returns canned outcomes in order; records the paths it was asked to run."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def run(self, path, skip_confirm=False):
        self.calls.append(path)
        return self.outcomes.pop(0)


def _entry(seq, ttp, target=SANDBOX_VM, destructive=False, tactic="impact"):
    return ScenarioEntry(
        seq=seq, ttp=ttp, tactic=tactic, name=ttp,
        scenario_file=f"scenarios/{seq:02d}-{ttp}.yaml",
        target_resource_id=target, destructive=destructive,
    )


def _make_campaign(tmp_path, scenarios, *, budget=None, state="ratified", kill=False):
    cid = new_campaign_id()
    m = CampaignManifest(
        campaign_id=cid,
        objective="t",
        scope=Scope(subscription_id="sub-1", allowed_resource_groups=["rg-celebrimbor"]),
        budget=budget or Budget(),
        scenarios=scenarios,
        state=state,
        kill_switch=kill,
    )
    cdir = campaign_dir(cid, runs_dir=tmp_path)
    m.save(cdir)
    return cdir


def test_happy_path_sequential(tmp_path):
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001"), _entry(2, "T1041")])
    engine = FakeEngine([
        RunOutcome("run-1", "detected"),
        RunOutcome("run-2", "missed"),
    ])
    resets = []
    r = CampaignRunner(
        cdir, reset_fn=resets.append, engine_factory=lambda: engine,
    ).run()
    assert r.state == "done"
    res = r.results
    assert (res["executed"], res["detected"], res["missed"]) == (2, 1, 1)
    assert len(engine.calls) == 2
    assert resets == [SANDBOX_VM, SANDBOX_VM]  # reset between each
    assert r.scenarios[0].run_id == "run-1"
    assert r.scenarios[1].detection == "missed"


def test_budget_ceiling_skips_rest(tmp_path):
    cdir = _make_campaign(
        tmp_path, [_entry(1, "T1110.001"), _entry(2, "T1041")],
        budget=Budget(max_scenarios=1),
    )
    engine = FakeEngine([RunOutcome("run-1", "detected")])
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert r.scenarios[0].status == "executed"
    assert r.scenarios[1].status == "skipped"
    assert "budget" in r.scenarios[1].error
    assert len(engine.calls) == 1


def test_kill_switch_aborts(tmp_path):
    cdir = _make_campaign(
        tmp_path, [_entry(1, "T1110.001")], kill=True,
    )
    engine = FakeEngine([RunOutcome("run-1", "detected")])
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert r.state == "aborted"
    assert engine.calls == []  # nothing ran
    assert r.scenarios[0].status == "pending"


def test_out_of_scope_scenario_errors(tmp_path):
    cdir = _make_campaign(tmp_path, [_entry(1, "T1486", target=PROD_VM)])
    engine = FakeEngine([])  # must never be called
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert r.scenarios[0].status == "error"
    assert "out of scope" in r.scenarios[0].error
    assert engine.calls == []


def test_destructive_skipped_without_budget(tmp_path):
    cdir = _make_campaign(
        tmp_path, [_entry(1, "T1486", destructive=True)],
        budget=Budget(allow_destructive=False),
    )
    engine = FakeEngine([])
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert r.scenarios[0].status == "skipped"
    assert "destructive" in r.scenarios[0].error
    assert engine.calls == []


def test_destructive_runs_with_budget(tmp_path):
    cdir = _make_campaign(
        tmp_path, [_entry(1, "T1486", destructive=True)],
        budget=Budget(allow_destructive=True),
    )
    engine = FakeEngine([RunOutcome("run-1", "detected")])
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert r.scenarios[0].status == "executed"


def test_refuses_unratified_campaign(tmp_path):
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")], state="planned")
    with pytest.raises(ValueError, match="ratify"):
        CampaignRunner(cdir, reset_fn=lambda x: None).run()


def test_refuses_done_campaign_with_replan_hint(tmp_path):
    # A 'done' campaign is terminal — ratify does not unblock it; the message
    # must point to re-planning, not ratifying (2026-07-30 CLI hygiene finding).
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")], state="done")
    with pytest.raises(ValueError, match="re-plan"):
        CampaignRunner(cdir, reset_fn=lambda x: None).run()


def test_multi_scenario_warns_human_only(tmp_path, capsys):
    cdir = _make_campaign(
        tmp_path, [_entry(1, "T1110.001"), _entry(2, "T1041")],
    )
    engine = FakeEngine([
        RunOutcome("run-1", "detected"),
        RunOutcome("run-2", "detected"),
    ])
    CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert "human_only" in capsys.readouterr().out


def test_single_scenario_no_human_only_warning(tmp_path, capsys):
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")])
    engine = FakeEngine([RunOutcome("run-1", "detected")])
    CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert "human_only" not in capsys.readouterr().out


def test_engine_error_marks_error_continues(tmp_path):
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001"), _entry(2, "T1041")])
    engine = FakeEngine([
        RunOutcome("run-1", "unknown", error="preflight failed"),
        RunOutcome("run-2", "detected"),
    ])
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    assert r.scenarios[0].status == "error"
    assert r.scenarios[0].error == "preflight failed"
    assert r.scenarios[1].status == "executed"  # campaign continued
    assert r.state == "done"


def test_atomic_run_records_detection_and_latency_in_manifest(tmp_path):
    # An atomic run's outcome (detection + latency, #157) reaches the manifest exactly as a
    # local-script run's does — the campaign reads it post-hoc, and the report uses it.
    cdir = _make_campaign(tmp_path, [_entry(1, "T1136.001", tactic="persistence")])
    engine = FakeEngine([RunOutcome("run-atomic", "detected", detection_latency_s=44.7)])
    r = CampaignRunner(cdir, reset_fn=lambda x: None, engine_factory=lambda: engine).run()
    entry = r.scenarios[0]
    assert entry.status == "executed"
    assert entry.detection == "detected"
    assert entry.detection_latency_s == 44.7
    # and it survives a reload from disk (the manifest is the audit artifact)
    reloaded = CampaignManifest.load(cdir)
    assert reloaded.scenarios[0].detection == "detected"
    assert reloaded.scenarios[0].detection_latency_s == 44.7


def test_reset_status_recorded_in_manifest(tmp_path):
    # Whatever the reset did is written on the entry — here a quiet skip the runner records.
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")])
    engine = FakeEngine([RunOutcome("run-1", "detected")])
    r = CampaignRunner(
        cdir,
        reset_fn=lambda x: "skipped: glorfindel absent (reset is not in the Orodruin image)",
        engine_factory=lambda: engine,
    ).run()
    assert "skipped" in r.scenarios[0].reset
    assert "skipped" in CampaignManifest.load(cdir).scenarios[0].reset


def _no_shell_out(*a, **k):  # the reset must NOT shell out when glorfindel cannot run
    raise AssertionError("subprocess.run must not be called when glorfindel is absent")


def test_default_reset_skips_quietly_in_the_orodruin_image(tmp_path, monkeypatch):
    # The Orodruin image as it is (annatar/Dockerfile, `pip install -e ".[annatar]"`): the
    # `glorfindel` launcher IS on PATH (every [project.scripts] entry is installed) but the
    # glorfindel package is not copied, so `glorfindel reset` would exit 1 on
    # ModuleNotFoundError. _default_reset must test the package and skip — no subprocess, no
    # raise, no write — and say so (recorded in the manifest), never "failed: exit 1" (M125).
    import annatar.campaign.runner as runner_mod

    monkeypatch.setattr(runner_mod, "find_spec", lambda name: None)
    monkeypatch.setattr(runner_mod.shutil, "which", lambda _name: "/usr/local/bin/glorfindel")
    monkeypatch.setattr(runner_mod.subprocess, "run", _no_shell_out)
    status = runner_mod._default_reset("/subscriptions/s/…/vm")
    assert status.startswith("skipped")
    assert "glorfindel absent" in status


def test_default_reset_skips_quietly_without_launcher(tmp_path, monkeypatch):
    # Package importable but no launcher on PATH: skipped as well, without shelling out.
    import annatar.campaign.runner as runner_mod

    monkeypatch.setattr(runner_mod, "find_spec", lambda name: object())
    monkeypatch.setattr(runner_mod.shutil, "which", lambda _name: None)
    monkeypatch.setattr(runner_mod.subprocess, "run", _no_shell_out)
    status = runner_mod._default_reset("/subscriptions/s/…/vm")
    assert status.startswith("skipped")
    assert "glorfindel absent" in status


def test_default_reset_runs_when_glorfindel_present(tmp_path, monkeypatch):
    import annatar.campaign.runner as runner_mod

    monkeypatch.setattr(runner_mod, "find_spec", lambda name: object())
    monkeypatch.setattr(runner_mod.shutil, "which", lambda _name: "/usr/bin/glorfindel")
    calls = []

    def _run(*a, **k):
        calls.append(a)
        return subprocess.CompletedProcess(a[0], 0)

    monkeypatch.setattr(runner_mod.subprocess, "run", _run)
    status = runner_mod._default_reset("/subscriptions/s/…/vm")
    assert status == "reset"
    assert len(calls) == 1  # it did shell out


def test_default_reset_failing_exit_is_recorded_as_failed(tmp_path, monkeypatch):
    # `glorfindel reset` exiting non-zero did NOT reset: the manifest must say "failed",
    # never "reset" (review #165 point 5, M123).
    import annatar.campaign.runner as runner_mod

    monkeypatch.setattr(runner_mod, "find_spec", lambda name: object())
    monkeypatch.setattr(runner_mod.shutil, "which", lambda _name: "/usr/bin/glorfindel")
    monkeypatch.setattr(
        runner_mod.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 2)
    )
    status = runner_mod._default_reset("/subscriptions/s/…/vm")
    assert status == "failed: exit 2"


# ── #358: a campaign launched by hand on Orodruin takes the request's lock ────────────────────

def _cli_campaign(tmp_path, monkeypatch, *args, state="planned"):
    """`annatar campaign run` on a campaign of tmp, its runner replaced: what it was asked."""
    from types import SimpleNamespace

    from click.testing import CliRunner

    import annatar.campaign.runner as runner_mod
    from annatar.cli import cli
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")], state=state)
    ran = []

    def runner(cdir, dry_run=False, without_glorfindel=False):
        def run():
            ran.append(dry_run)
            return SimpleNamespace(campaign_id=cdir.name, state="done", without_glorfindel=False,
                                   results={"executed": 0, "detected": 0, "missed": 0, "skipped": 0,
                                            "errors": 0})
        return SimpleNamespace(run=run)
    monkeypatch.setattr(runner_mod, "CampaignRunner", runner)
    res = CliRunner().invoke(cli, ["campaign", "run", cdir.name, "--runs-dir", str(tmp_path),
                                   "--no-report", *args])
    return res, ran, cdir


def test_a_campaign_by_hand_during_a_request_is_refused_and_ratifies_nothing(tmp_path, monkeypatch):
    from eregion_core.exercise_runner import request_lock
    with request_lock("request r-20261031T080000Z-abcdef"):
        res, ran, cdir = _cli_campaign(tmp_path, monkeypatch, "--yes")
    assert res.exit_code == 1, res.output
    said = " ".join(res.output.split())   # rich folds the line
    assert "refused — busy: request r-20261031T080000Z-abcdef runs on this Orodruin" in said
    assert ran == [] and CampaignManifest.load(cdir).state == "planned"


def test_a_preview_of_a_campaign_takes_no_lock(tmp_path, monkeypatch):
    from eregion_core.exercise_runner import request_lock
    with request_lock("request r-20261031T080000Z-abcdef"):
        res, ran, _ = _cli_campaign(tmp_path, monkeypatch, "--dry-run")
    assert res.exit_code == 0, res.output
    assert ran == [True]


def test_a_request_during_a_campaign_by_hand_is_refused_naming_the_campaign(tmp_path, monkeypatch):
    """While the campaign runs, the lock is its own: a request is refused, and told why."""
    from types import SimpleNamespace

    from click.testing import CliRunner

    import annatar.campaign.runner as runner_mod
    from annatar.cli import cli
    from eregion_core.exercise_runner import Busy, request_lock
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")])
    seen = []

    def runner(cdir, dry_run=False, without_glorfindel=False):
        def run():
            with pytest.raises(Busy) as e:
                with request_lock("request r-20261031T080000Z-abcdef"):
                    pass
            seen.append(str(e.value))
            return SimpleNamespace(campaign_id=cdir.name, state="done", without_glorfindel=False,
                                   results={"executed": 1, "detected": 1, "missed": 0, "skipped": 0,
                                            "errors": 0})
        return SimpleNamespace(run=run)
    monkeypatch.setattr(runner_mod, "CampaignRunner", runner)
    res = CliRunner().invoke(cli, ["campaign", "run", cdir.name, "--runs-dir", str(tmp_path), "--no-report"])
    assert res.exit_code == 0, res.output
    assert seen == [f"campaign {cdir.name} runs on this Orodruin: one at a time — wait for its end, "
                    "or stop it (make orodruin-kill)"]
    with request_lock("request r-20261031T080000Z-abcdef"):   # let go once it is over
        pass


def test_a_holder_whose_name_looks_like_markup_is_said_as_it_is(tmp_path, monkeypatch):
    """#388's review: rich never reads the holder's name, nor the campaign's id, as markup."""
    from eregion_core.exercise_runner import request_lock
    with request_lock("request [/red][bold]x"):
        res, ran, _ = _cli_campaign(tmp_path, monkeypatch, "--yes")
    assert res.exit_code == 1 and isinstance(res.exception, SystemExit), res.exception
    assert "busy: request [/red][bold]x runs" in " ".join(res.output.split()) and ran == []


def test_a_campaign_with_its_own_runs_dir_still_takes_orodruins_one_lock(tmp_path, monkeypatch):
    """SEC14 (R-10): --runs-dir names where the campaign writes, never another lock."""
    from eregion_core.exercise_runner import request_lock
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    with request_lock("request r-20261031T080000Z-abcdef"):
        res, ran, cdir = _cli_campaign(elsewhere, monkeypatch, "--yes")
    assert res.exit_code == 1 and "busy: request r-20261031T080000Z-abcdef" in " ".join(res.output.split())
    assert ran == [] and CampaignManifest.load(cdir).state == "planned"
    assert not list(elsewhere.rglob(".lock"))


# ── KS1 (#648): the stop of a campaign, read fail-closed ─────────────────────────────────────
# The kill switch is the manifest's, re-read before each run and before each write of the
# manifest, kept once seen. Between the two scenarios, or during the first run, what an operator
# (or a hostile writer) could put in the manifest's place: the runner meets it before the second.

def _between(cdir, put, status=None):
    """A reset that puts something in the manifest's place, then returns `status` (None: the
    runner does not write the manifest after it; "reset": it does, as `_default_reset`)."""
    def reset(_rid):
        put(cdir / "manifest.json")
        return status
    return reset


class PuttingEngine(FakeEngine):
    """An engine whose first run puts something in the manifest's place, as the run goes."""

    def __init__(self, outcomes, cdir, put):
        super().__init__(outcomes)
        self.cdir, self.put = cdir, put

    def run(self, path, skip_confirm=False):
        if not self.calls:
            self.put(self.cdir / "manifest.json")
        return super().run(path, skip_confirm)


def _run_two(tmp_path, put, *, during_run=False, status=None):
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001"), _entry(2, "T1041")])
    outcomes = [RunOutcome("run-1", "detected"), RunOutcome("run-2", "missed")]
    if during_run:
        engine = PuttingEngine(outcomes, cdir, put)
        reset = lambda _rid: status  # noqa: E731
    else:
        engine = FakeEngine(outcomes)
        reset = _between(cdir, put, status)
    r = CampaignRunner(cdir, reset_fn=reset, engine_factory=lambda: engine).run()
    return cdir, engine, r


def _said(capsys) -> str:
    return " ".join(capsys.readouterr().out.split())


def _as_link(path):
    """A link to a copy of the manifest that says "go on": never followed."""
    copy = path.with_name("elsewhere.json")
    path.replace(copy)
    path.symlink_to(copy)


def _as_pipe(path):
    path.unlink()
    os.mkfifo(path)


def _too_large(path):
    from eregion_core.channel_reader import DOC_BYTES
    path.write_text(path.read_text() + " " * DOC_BYTES)


def _kill(path):
    path.write_text(path.read_text().replace('"kill_switch": false', '"kill_switch": true'))


@pytest.mark.parametrize("put", [_as_link, _as_pipe, _too_large], ids=["link", "pipe", "too-large"])
def test_a_kill_switch_refused_by_the_bounded_reader_stops_the_campaign_and_says_so(tmp_path, capsys, put):
    """KS1 (M4573): a manifest the bounded reader refuses (SEC-A1) is never read as "go on"."""
    cdir, engine, r = _run_two(tmp_path, put)
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.scenarios[1].status == "pending"
    assert r.stop_reason.startswith(KILL_SWITCH_UNREADABLE) and "refused" in r.stop_reason
    assert r.kill_switch is False          # nobody asked: it could not be read
    assert _said(capsys).count(KILL_SWITCH_UNREADABLE) == 1
    on_disk = CampaignManifest.load(cdir)  # the manifest, written again, says why
    assert on_disk.state == "aborted" and on_disk.stop_reason == r.stop_reason


def _not_json(path):
    path.write_text("{not json")


def _nested_too_deep(path):
    path.write_text("[" * 200_000 + "]" * 200_000)


def _switch(value):
    def put(path):
        path.write_text(path.read_text().replace('"kill_switch": false', f'"kill_switch": {value}'))
    return put


def _not_an_object(path):
    path.write_text("[]")


def _io_error(path, monkeypatch):
    import errno

    from annatar.campaign import runner as runner_mod

    def fail(_path, *a, **k):
        raise OSError(errno.EIO, "Input/output error")
    monkeypatch.setattr(runner_mod, "read_json", fail)


@pytest.mark.parametrize("put", [_not_json, _nested_too_deep, _switch('"no"'), _switch("null"),
                                 _not_an_object, "io"],
                         ids=["not-json", "nested-too-deep", "not-a-switch", "null", "not-an-object",
                              "io-error"])
def test_an_unreadable_kill_switch_stops_the_campaign_and_says_so(tmp_path, capsys, monkeypatch, put):
    """KS1 (M4574, M4577): invalid JSON, a RecursionError, an I/O error, a document that is not
    an object, a switch neither true nor false (null included) — the campaign stops, said once,
    never silently goes on."""
    if put == "io":
        put = lambda path: _io_error(path, monkeypatch)  # noqa: E731
    cdir, engine, r = _run_two(tmp_path, put)
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.stop_reason.startswith(KILL_SWITCH_UNREADABLE) and r.kill_switch is False
    assert _said(capsys).count(KILL_SWITCH_UNREADABLE) == 1


def test_an_io_error_names_its_kind(tmp_path, monkeypatch):
    cdir, engine, r = _run_two(tmp_path, lambda path: _io_error(path, monkeypatch))
    assert r.stop_reason == f"{KILL_SWITCH_UNREADABLE} (OSError)"


def test_a_manifest_gone_stops_the_campaign(tmp_path, capsys):
    """KS1 (M4575): the runner never leaves its manifest absent (an atomic write): gone, it was
    deleted from outside — the campaign stops, said once, and the manifest is written again."""
    cdir, engine, r = _run_two(tmp_path, lambda path: path.unlink())
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.stop_reason == f"{KILL_SWITCH_UNREADABLE} (manifest gone)" and r.kill_switch is False
    assert _said(capsys).count(KILL_SWITCH_UNREADABLE) == 1
    assert CampaignManifest.load(cdir).stop_reason == r.stop_reason


def test_a_campaign_deleted_during_a_run_stops_and_is_never_recreated(tmp_path, capsys):
    """KS1: its directory removed as a run goes (`rm -rf`): the next scenarios are not played,
    and the runner never writes the directory back."""
    import shutil
    cdir, engine, r = _run_two(tmp_path, lambda path: shutil.rmtree(path.parent),
                               during_run=True, status="reset")
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.stop_reason == f"{KILL_SWITCH_UNREADABLE} (manifest gone)"
    assert _said(capsys).count(KILL_SWITCH_UNREADABLE) == 1
    assert not cdir.exists()


def test_a_kill_switch_set_mid_campaign_stops_it(tmp_path, capsys):
    """KS1: the operator's stop, set between two runs, is taken before the next one."""
    cdir, engine, r = _run_two(tmp_path, _kill)
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.kill_switch is True and r.stop_reason == KILL_SWITCH_SET
    assert _said(capsys).count(KILL_SWITCH_SET) == 1
    assert CampaignManifest.load(cdir).stop_reason == KILL_SWITCH_SET


@pytest.mark.parametrize("where", ["during-run", "at-reset"])
def test_a_kill_switch_set_while_the_runner_writes_is_never_overwritten(tmp_path, capsys, where):
    """KS1 (M4576): set during a run (the engine) or at the reset that returns "reset" — the
    runner writes its manifest after both: the stop is read before each write, kept, and still
    on disk at the end."""
    cdir, engine, r = _run_two(tmp_path, _kill, during_run=where == "during-run", status="reset")
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.kill_switch is True and r.stop_reason == KILL_SWITCH_SET
    assert _said(capsys).count(KILL_SWITCH_SET) == 1
    on_disk = CampaignManifest.load(cdir)
    assert on_disk.kill_switch is True and on_disk.state == "aborted"


def test_a_pipe_put_during_a_run_stops_the_campaign(tmp_path, capsys):
    """KS1 (M4576): a pipe put in the manifest's place during a run is read as a stop before the
    runner's next write replaces it — never lost by that write."""
    cdir, engine, r = _run_two(tmp_path, _as_pipe, during_run=True, status="reset")
    assert len(engine.calls) == 1 and r.state == "aborted"
    assert r.stop_reason.startswith(KILL_SWITCH_UNREADABLE) and "refused" in r.stop_reason
    assert _said(capsys).count(KILL_SWITCH_UNREADABLE) == 1
    assert CampaignManifest.load(cdir).stop_reason == r.stop_reason


def test_a_stop_asked_during_the_last_run_aborts_the_campaign(tmp_path, capsys):
    """KS1: nothing left to run, the stop asked is still recorded — aborted, said once."""
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")])
    engine = PuttingEngine([RunOutcome("run-1", "detected")], cdir, _kill)
    r = CampaignRunner(cdir, reset_fn=lambda _rid: "reset", engine_factory=lambda: engine).run()
    assert len(engine.calls) == 1 and r.state == "aborted" and r.stop_reason == KILL_SWITCH_SET
    assert _said(capsys).count(KILL_SWITCH_SET) == 1


@pytest.mark.parametrize("value", ['"no"', '"yes"', "1", "null", "[]"])
def test_a_kill_switch_not_a_boolean_is_not_loaded_as_one(tmp_path, value):
    """KS1 (M4578): the manifest loads a kill_switch true only when it is true — like
    without_glorfindel; the runner reads such a value as unreadable, and stops."""
    cdir = _make_campaign(tmp_path, [_entry(1, "T1110.001")])
    _switch(value)(cdir / "manifest.json")
    m = CampaignManifest.load(cdir)
    assert m.kill_switch is False
    engine = FakeEngine([RunOutcome("run-1", "detected")])
    r = CampaignRunner(cdir, reset_fn=lambda _rid: None, engine_factory=lambda: engine).run()
    assert engine.calls == [] and r.state == "aborted" and r.kill_switch is False
    assert r.stop_reason == f"{KILL_SWITCH_UNREADABLE} (kill_switch is not true or false)"
