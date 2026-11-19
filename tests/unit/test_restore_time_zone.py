"""RTZ1 (#923): on the restore path, a time without its time zone is refused, never taken for UTC.

The moment a restore is given chooses the recovery point: a zone guessed wrong takes a point after
the attack began (the disk restored already holds it), or hours too early. Before, `--before
2026-11-19T14:05:00` was read as UTC, and so were a card's first detection and the VM's isolation
written without an offset (the latter even as the host's local time, by `.timestamp()`). Now:

- a moment given (`glorfindel restore --before`, the TUI, the console, the bot) without its zone is
  refused, with a message that asks for an ISO 8601 time with its zone, and an example;
- a card, or the VM's isolation state, whose time carries no zone says what it carries: no moment
  is proposed, no command carries a guessed time, `glorfindel restore` without --before refuses;
- a time with its zone (`Z`, `+00:00`, `+01:00`) reads as before, converted to UTC; a normal card
  still proposes its command, with the same time as before (the control).

No Azure call, no model call: the recovery points, the connector and the command are faked.
Identifiers made up. Mutants M6556–M6570 (scripts/mutants/RTZ1.py) are measured here.
"""
from __future__ import annotations

import asyncio
import io
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from rich.console import Console

from glorfindel import escalations, restore_plan

SUB = "00000000-0000-0000-0000-0000000000dd"
RG = "rg-example-a"
VM = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Compute/virtualMachines/vm-example-01"
NAIVE = "2026-10-29T07:30:00"                       # a time written without its zone
EXAMPLE = "2026-11-19T14:05:00Z"                    # the example the refusal gives


def _card(action: str = "restore_from_backup", esc_type: str = "destructive_action", **kw) -> str:
    return escalations.record("rule-ransomware-0123abcd", VM, action, esc_type, "restore needs a human",
                              ttp="T1486", **kw)


def _unzone(esc_id: str, when: str = NAIVE) -> dict:
    """The card `esc_id` rewritten in its store with `when` as its times, no zone (as an older or a
    foreign writer could leave it): the card as the store now holds it."""
    lines = escalations._STORE.read_text().splitlines()
    out = []
    for line in lines:
        e = json.loads(line)
        if e.get("id") == esc_id:
            e["first_seen"] = e["timestamp"] = when
        out.append(json.dumps(e))
    escalations._STORE.write_text("\n".join(out) + "\n")
    return next(e for e in escalations.pending() if e["id"] == esc_id)


def _pending(esc_id: str) -> dict:
    return next(e for e in escalations.pending() if e["id"] == esc_id)


def _asks_a_zone(text: str) -> None:
    flat = " ".join(str(text).split())
    assert "sans fuseau" in flat and "ISO 8601 avec fuseau" in flat and EXAMPLE in flat, text


# ── The rule ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [NAIVE, "2026-10-29 07:30", "2026-10-29", "20261029T073000"])
def test_a_time_without_its_zone_is_refused_and_the_refusal_asks_for_one(text):
    with pytest.raises(restore_plan.NoTimeZone) as raised:
        restore_plan.parse_moment(text)
    _asks_a_zone(raised.value)
    assert repr(text) in str(raised.value)                  # what was given, said
    assert restore_plan.zone_missing(text) is True
    with pytest.raises(ValueError):                         # every caller that catches ValueError refuses it
        restore_plan.restore_args(VM, text)


@pytest.mark.parametrize("text, utc", [
    ("2026-10-29T07:30:00Z", "2026-10-29T07:30:00+00:00"),
    ("2026-10-29T07:30:00+00:00", "2026-10-29T07:30:00+00:00"),
    ("2026-10-29T07:30:00-00:00", "2026-10-29T07:30:00+00:00"),
    ("2026-10-29T08:30:00+01:00", "2026-10-29T07:30:00+00:00"),
    ("2026-10-29T02:30:00-05:00", "2026-10-29T07:30:00+00:00"),
    ("2026-10-29T07:30:00.250000+0000", "2026-10-29T07:30:00.250000+00:00"),
])
def test_a_time_with_its_zone_reads_as_before_converted_to_utc(text, utc):
    assert restore_plan.parse_moment(text) == utc
    assert restore_plan.zone_missing(text) is False


@pytest.mark.parametrize("text", ["2026-10-29T07:30:00 UTC", "2026-10-29T07:30:00z", "2026-10-29T07:30:00 GMT",
                                  "2026-10-29T07:30:00+00:0", "2026-10-29T07:30:00ZZ"])
def test_a_zero_offset_written_wrong_is_refused_never_taken_for_utc(text):
    with pytest.raises(ValueError):
        restore_plan.parse_moment(text)


# ── `glorfindel restore --before` ─────────────────────────────────────────────────────────

def _restore_env(tmp_path, monkeypatch, iso=None):
    """`glorfindel restore` with a fake connector and job starter, in tmp_path."""
    from glorfindel import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "_backup_vault_from_config", lambda v: ("rsv-example", "rg-backup", "stexample"))
    monkeypatch.setattr("glorfindel.actions.AzureConnector", lambda dry_run=False: SimpleNamespace(dry_run=dry_run))
    monkeypatch.setattr("glorfindel.actions._load_isolation_state", lambda rid: iso)
    monkeypatch.setattr(cli, "_record_manual_action", lambda *a, **k: None)
    started: list[tuple] = []

    def start_restore(resource_id, connector, vault, before, **kw):
        started.append((resource_id, before))
        return {"job_id": "j", "restore_job_name": "rj", "recovery_point_time": "2026-10-29 07:00:00+00:00",
                "recovery_point_vault_tier": True}
    monkeypatch.setattr("glorfindel.jobs.start_restore", start_restore)
    return cli, started


def test_before_without_its_zone_is_refused_before_anything_with_the_message(tmp_path, monkeypatch):
    cli, started = _restore_env(tmp_path, monkeypatch)
    out = CliRunner().invoke(cli.cli, ["restore", VM, "--yes", "--before", NAIVE], terminal_width=200)
    assert out.exit_code != 0 and started == []
    _asks_a_zone(out.output)


@pytest.mark.parametrize("given", ["2026-10-29T07:30:00Z", "2026-10-29T08:30:00+01:00"])
def test_before_with_its_zone_gives_the_same_point_as_before(tmp_path, monkeypatch, given):
    cli, started = _restore_env(tmp_path, monkeypatch)
    out = CliRunner().invoke(cli.cli, ["restore", VM, "--yes", "--before", given], terminal_width=200)
    assert out.exit_code == 0, out.output
    assert started == [(VM, "2026-10-29T07:30:00+00:00")]


def test_the_help_no_longer_says_utc_when_no_offset():
    from glorfindel import cli
    out = CliRunner().invoke(cli.cli, ["restore", "--help"], terminal_width=200)
    flat = " ".join(out.output.split())
    assert "when no offset" not in flat and "UTC when" not in flat
    assert "time zone" in flat and EXAMPLE in flat


def test_restore_without_before_on_a_card_without_zone_refuses_and_says_what_it_carries(tmp_path, monkeypatch):
    cli, started = _restore_env(tmp_path, monkeypatch, iso={"isolated_at": "2026-10-29T09:00:00+00:00"})
    _unzone(_card(), "2026-10-29T06:00:00")             # earlier than the isolation, if it were UTC
    out = CliRunner().invoke(cli.cli, ["restore", VM, "--yes"], terminal_width=250)
    assert out.exit_code != 0 and started == []
    flat = " ".join(out.output.split())
    assert "non deviné" in flat and "la carte porte '2026-10-29T06:00:00'" in flat
    _asks_a_zone(flat)


def test_restore_without_before_on_an_isolation_without_zone_refuses(tmp_path, monkeypatch):
    cli, started = _restore_env(tmp_path, monkeypatch, iso={"isolated_at": "2026-10-29T05:00:00"})
    _card()                                              # a card with its zone: still no moment guessed
    out = CliRunner().invoke(cli.cli, ["restore", VM, "--yes"], terminal_width=250)
    assert out.exit_code != 0 and started == []
    flat = " ".join(out.output.split())
    assert "l'état d'isolation de la VM porte '2026-10-29T05:00:00'" in flat
    _asks_a_zone(flat)


def test_the_control_a_normal_card_still_gives_its_moment(tmp_path, monkeypatch):
    cli, started = _restore_env(tmp_path, monkeypatch)
    esc = _pending(_card())
    out = CliRunner().invoke(cli.cli, ["restore", VM, "--yes"], terminal_width=250)
    assert out.exit_code == 0, out.output
    assert started == [(VM, restore_plan.parse_moment(esc["first_seen"]))]


# ── What the defender recorded: the card, the isolation ──────────────────────────────────

def test_a_card_without_zone_gives_no_moment_and_the_reason(monkeypatch):
    monkeypatch.setattr("glorfindel.actions._load_isolation_state", lambda rid: None)
    esc = _unzone(_card())
    assert restore_plan.card_moment(esc) == ("", f"la carte porte {NAIVE!r} : {restore_plan.NO_ZONE}")
    plan = restore_plan.proposed_moment(VM, esc)
    assert plan["before"] == "" and plan["no_zone"] == NAIVE
    _asks_a_zone(plan["why"])
    normal = _pending(escalations.record("rule-other-0123abcd", VM, "snapshot", "low_confidence", "r"))
    assert restore_plan.card_moment(normal) == (restore_plan.parse_moment(normal["first_seen"]), "")


def test_a_card_without_zone_is_the_one_a_restore_answers_and_dates_nothing(monkeypatch):
    """Sorted first: its time may be the earliest. Neither it nor a later card's time is taken."""
    monkeypatch.setattr("glorfindel.actions._load_isolation_state",
                        lambda rid: {"isolated_at": "2026-10-29T09:00:00+00:00"})
    later = escalations.record("rule-other-0123abcd", VM, "snapshot", "low_confidence", "later")
    naive = _unzone(_card(), "2026-10-29T06:00:00")    # before the isolation, if it were UTC
    assert restore_plan.card_of(VM)["id"] == naive["id"] != later
    first, why = restore_plan.incident_start(VM)
    assert first is None and "la carte porte '2026-10-29T06:00:00'" in why


def test_an_isolation_without_zone_is_never_read_as_a_moment(monkeypatch):
    monkeypatch.setattr("glorfindel.actions._load_isolation_state",
                        lambda rid: {"isolated_at": "2026-10-29T05:00:00"})
    assert restore_plan.isolation_time(VM) == (None, "")
    assert restore_plan.unzoned_isolation(VM) == "2026-10-29T05:00:00"
    esc = _pending(_card())
    plan = restore_plan.proposed_moment(VM, esc)
    assert plan["before"] == "" and "l'état d'isolation de la VM porte '2026-10-29T05:00:00'" in plan["why"]
    first, why = restore_plan.incident_start(VM)
    assert first is None and "sans fuseau" in why
    assert "sans fuseau" in restore_plan.moment_warning(VM, "2026-10-29T04:00:00+00:00")


def test_the_control_an_isolation_with_its_zone_still_bounds_the_moment(monkeypatch):
    monkeypatch.setattr("glorfindel.actions._load_isolation_state",
                        lambda rid: {"isolated_at": "2026-10-29T05:00:00+00:00"})
    esc = _pending(_card())
    assert restore_plan.proposed_moment(VM, esc)["before"] == "2026-10-29T05:00:00+00:00"
    assert restore_plan.incident_start(VM)[0] == datetime(2026, 10, 29, 5, tzinfo=timezone.utc).timestamp()


# ── The commands to copy: the CLI's steps, the TUI's, the bot's ──────────────────────────

def _cli_steps(e: dict) -> str:
    from glorfindel import cli
    buf = io.StringIO()
    real, cli.console = cli.console, Console(file=buf, width=300)
    try:
        cli._render_next_steps(e)
    finally:
        cli.console = real
    return " ".join(buf.getvalue().split())


@pytest.mark.parametrize("action, esc_type", [("restore_from_backup", "destructive_action"),
                                               ("snapshot", "low_confidence")])
def test_the_cli_steps_of_a_card_without_zone_carry_no_time_and_say_why(monkeypatch, action, esc_type):
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [{"resource_id": VM}])
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(all=lambda: []))
    e = {"resource_id": VM, "action": action, "escalation_type": esc_type, "id": "e1", "first_seen": NAIVE}
    said = _cli_steps(e)
    assert "--before <ISO8601>" in said and f"--before {NAIVE}" not in said and "+00:00" not in said
    assert f"la carte porte {NAIVE!r}" in said
    _asks_a_zone(said)


def test_the_control_the_cli_steps_of_a_normal_card_keep_their_time(monkeypatch):
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [{"resource_id": VM}])
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", lambda: SimpleNamespace(all=lambda: []))
    e = {"resource_id": VM, "action": "restore_from_backup", "escalation_type": "destructive_action",
         "id": "e1", "first_seen": "2026-10-29T08:12:00+00:00"}
    said = _cli_steps(e)
    assert f"glorfindel restore {RG}/vm-example-01 --yes --before 2026-10-29T08:12:00+00:00" in said
    assert "sans fuseau" not in said


def test_the_tui_and_the_bot_copy_no_time_without_zone_and_keep_a_normal_one(monkeypatch):
    from glorfindel import tui
    monkeypatch.setattr("glorfindel.actions.active_isolations", lambda: [{"resource_id": VM}])
    naive = _unzone(_card())
    screen = Console(width=220, record=True)
    screen.print(tui._escalations_renderable(datetime.now(timezone.utc), None, True))
    shown = " ".join(screen.export_text().split())
    assert "--before <ISO8601>" in shown and f"--before {NAIVE}" not in shown
    bot = pytest.importorskip("glorfindel.bot")
    assert "--before <ISO8601>" in bot._cli_command(naive)
    escalations.resolve(naive["id"])
    normal = _pending(_card())
    screen = Console(width=220, record=True)
    screen.print(tui._escalations_renderable(datetime.now(timezone.utc), None, True))
    assert f"--before {normal['first_seen']}" in " ".join(screen.export_text().split())
    assert f"--before {normal['first_seen']}" in bot._cli_command(normal)


# ── The faces that take a moment: the TUI, the console, the bot ──────────────────────────

def test_the_tui_refuses_a_moment_without_zone_and_takes_one_with_it(monkeypatch):
    from glorfindel import tui
    ran = []
    monkeypatch.setattr(tui.subprocess, "run", lambda argv, **kw: ran.append(argv))
    monkeypatch.setattr(restore_plan, "points_before", lambda rid, before, connector=None: [])
    pending = tui._restore_pending(_pending(_card()))
    pending["buffer"] = NAIVE
    pending = tui._restore_key(pending, "\r")
    assert pending["stage"] == "moment" and ran == []
    _asks_a_zone(pending["error"])
    pending["buffer"] = "2026-10-29T08:30:00+01:00"
    pending = tui._restore_key(pending, "\r")
    assert pending["stage"] == "points" and pending["before"] == "2026-10-29T07:30:00+00:00"


def test_the_tui_proposes_no_moment_for_a_card_without_zone(monkeypatch):
    from glorfindel import tui
    pending = tui._restore_pending(_unzone(_card()))
    assert pending["buffer"] == "" and f"la carte porte {NAIVE!r}" in pending["why"]


@pytest.fixture()
def console(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    monkeypatch.delenv("GLORFINDEL_WARROOM_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "runs").mkdir()
    monkeypatch.setattr(restore_plan, "points_before", lambda rid, before, connector=None: [])
    from .console_client import console as client
    return client()


def test_the_console_refuses_a_moment_without_zone_and_starts_nothing(console, monkeypatch):
    import eregion_console.api as api
    started = []
    monkeypatch.setattr(api, "_restore_start", lambda *a: started.append(a))

    async def never(*a, **kw):                  # a mutant that lets it through runs nothing either
        started.append(a)
    monkeypatch.setattr(api, "_bg_restore", never)
    monkeypatch.setattr(api.subprocess, "run", lambda *a, **kw: started.append(a))
    esc_id = _card()
    d = console.get(f"/api/restore/plan/vm-example-01?escalation={esc_id}&before={NAIVE}").json()
    _asks_a_zone(d["error"])
    r = console.post("/api/action/restore/vm-example-01", json={"escalation": esc_id, "before": NAIVE}).json()
    assert started == [] and "status" not in r
    _asks_a_zone(r["error"])
    d = console.get(f"/api/restore/plan/vm-example-01?escalation={esc_id}&before=2026-10-29T08:30:00%2B01:00").json()
    assert d["moment"] == "2026-10-29T07:30:00+00:00"


def test_the_console_proposes_no_moment_for_a_card_without_zone(console):
    esc_id = _unzone(_card())["id"]
    d = console.get(f"/api/restore/plan/vm-example-01?escalation={esc_id}").json()
    assert d["before"] == "" and d["moment"] == "" and f"la carte porte {NAIVE!r}" in d["why"]


class _Interaction:
    def __init__(self, bot):
        self.user = SimpleNamespace(id=111, display_name="operator", roles=[])
        self.client = SimpleNamespace(button_policy=bot.ButtonPolicy(users=frozenset({111})))
        self.channel, self.message, self.data = None, None, {"custom_id": "x"}
        self.ephemeral = []
        outer = self

        class _Response:
            async def send_message(self, text, ephemeral=False):
                outer.ephemeral.append(text)

            async def defer(self, **kw):
                raise AssertionError("a refused moment goes no further")
        self.response = _Response()


def test_the_bot_refuses_a_moment_without_zone(monkeypatch):
    bot = pytest.importorskip("glorfindel.bot")
    ran = []
    monkeypatch.setattr(bot, "_run_cli", lambda args: ran.append(args))
    esc = _pending(_card())
    form = bot._RestoreModal(esc, restore_plan.proposed_moment(VM, esc))
    form.moment._value = NAIVE
    click = _Interaction(bot)
    asyncio.run(form.on_submit(click))
    assert ran == [] and click.ephemeral
    _asks_a_zone(click.ephemeral[0])


def test_the_bot_proposes_no_moment_for_a_card_without_zone():
    bot = pytest.importorskip("glorfindel.bot")
    esc = _unzone(_card())
    plan = restore_plan.proposed_moment(VM, esc)
    form = bot._RestoreModal(esc, plan)
    assert not form.moment.default and plan["before"] == ""


# ── The provider, last reader ────────────────────────────────────────────────────────────

def test_the_provider_refuses_a_moment_without_zone_before_any_call(monkeypatch):
    from tests.unit.test_glorfindel import _RID, _backup_env, _rp
    connector, client, posted, now = _backup_env(monkeypatch, rps=[_rp("rp-1", datetime(2026, 10, 29, 6,
                                                                                        tzinfo=timezone.utc))],
                                                 jobs=[])
    with pytest.raises(RuntimeError) as raised:
        connector.restore_from_backup(_RID, vault="rsv", wait=False, staging_storage="st", before_attack_time=NAIVE)
    _asks_a_zone(raised.value)
    assert posted == [] and not client.recovery_points.list.called


def test_the_control_the_provider_takes_a_moment_with_its_zone(monkeypatch):
    from tests.unit.test_glorfindel import _RID, _backup_env, _job, _rp
    connector, client, posted, now = _backup_env(monkeypatch, rps=[], jobs=[])
    attack = now - timedelta(hours=2)
    before, after = _rp("rp-before", attack - timedelta(hours=1)), _rp("rp-after", attack + timedelta(minutes=5))
    before.name, after.name = "rp-before", "rp-after"
    client.recovery_points.list.return_value = [before, after]
    job = _job("restore-1", "vm", "Restore", now)
    job.name = "restore-1"
    client.backup_jobs.list.return_value = [job]
    local = attack.astimezone(timezone(timedelta(hours=1))).isoformat()      # the same instant, at +01:00
    out = connector.restore_from_backup(_RID, vault="rsv", wait=False, staging_storage="st",
                                        before_attack_time=local)
    assert out["recovery_point"] == "rp-before"
