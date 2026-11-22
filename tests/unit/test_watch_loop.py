"""WCH1 (#1019): the watch's parts, each reached alone (glorfindel/watch/).

`watch()` was one function of 947 lines in glorfindel/cli.py, its state in closures no test reached
alone; the tests that ran it whole (test_outside_markup, test_signal_origin, test_runs_channel,
test_bot_fallback, test_entries_calls…) still do, through `glorfindel watch`. Here, each part that
decides something — a cadence, a bound, a guard, a fallback — is held on its own: the loop's tick, the
runs/ channel's room, a VM's queue and its thread, the passes one at a time, the heartbeats, the rules
kept when what follows them fails, what the startup says.
"""
from __future__ import annotations

import io
import json
import os
import stat
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from eregion_core import channel_reader
from eregion_core.signals import Signal
from glorfindel.terminal import GlorfindelConsole
from glorfindel.watch import beat, loop, passes, rules, runs_channel, startup
from glorfindel.watch.dispatch import Dispatcher
from glorfindel.watch.housekeeping import Housekeeping
from glorfindel.watch.loop import Watch
from glorfindel.watch.runs_channel import ChannelRoom

VM = "/subscriptions/s/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/web"
EVIL = "[/x] [blink]z[/blink]"


def _console():
    buf = io.StringIO()
    return GlorfindelConsole(file=buf, width=400, color_system=None), buf


def _flat(buf) -> str:
    return " ".join(buf.getvalue().split())


def _sig(data: dict) -> Signal:
    return Signal(**{k: data.get(k, "") for k in Signal.__dataclass_fields__})


def _line(event="detection_missed", signal_id="s1", resource_id=VM, ttp="T1486", **over) -> dict:
    return {"signal_id": signal_id, "event": event, "resource_id": resource_id, "ttp": ttp,
            "severity": "high", "resource_type": "vm", "raw_signal": {}, "context": {}, **over}


def _join(name: str) -> None:
    for t in threading.enumerate():
        if t.name == name:
            t.join(timeout=10)


# ── 1. The loop: a tick, its cadences, a task that fails ─────────────────────────────────────────

class _Recorder:
    """Stands for a part of the watch: each of its tasks records its name when it runs; the ones
    named in `fail` raise, with markup in what they say."""

    def __init__(self, calls: list, fail=()):
        self._calls, self._fail = calls, set(fail)

    def __getattr__(self, name):
        def task():
            self._calls.append(name)
            if name in self._fail:
                raise RuntimeError(f"{name} {EVIL}")
        task.__name__ = name
        return task


def _ticking(fail=()):
    console, buf = _console()
    w = Watch("runs", dry_run=True, model="m", memory_path=None, interval=0, rules_file=None,
              mode_override=None, console=console, show_signal=None, show_decision=None)
    calls: list = []
    w.housekeeping = w.beat = w.rules = _Recorder(calls, fail)
    w.channel = SimpleNamespace(_poll=lambda: calls.append("_poll"))
    return w, calls, buf


HOUSEKEEPING = ["_recoveries", "_door_facts", "_dossier_retention", "_relay_notices", "_check_ttl", "_reconcile_jobs", "_reassert",
                "_write_heartbeat", "_observe_windows", "_propose_verdicts", "_judge_drill"]


def test_a_tick_reads_runs_says_verify_every_5_polls_and_keeps_house_every_30():
    w, calls, _ = _ticking()
    for _ in range(30):
        w.tick()
    assert calls.count("_poll") == 30
    assert calls.count("_identity_checks") == 6            # « Verify » answered within ~10 s (IR1a)
    assert calls[-len(HOUSEKEEPING):] == HOUSEKEEPING       # once, at the 30th, in its order
    assert calls.count("_reassert") == 1
    assert calls[-len(HOUSEKEEPING) - 2:-len(HOUSEKEEPING)] == ["_poll", "_identity_checks"]


def test_the_windows_are_read_after_the_heartbeat_and_the_verdicts_proposed_after_the_windows():
    """VP1: the proposed verdicts read the windows the same pass observed."""
    w, calls, _ = _ticking()
    w._ttl_check_counter = 29
    w.tick()
    assert calls.index("_write_heartbeat") < calls.index("_observe_windows") < calls.index("_propose_verdicts")


def test_a_task_that_keeps_failing_never_skips_the_others():
    """Fourth review, Q12: an old isolation the guard refuses made the reassertion and the
    heartbeat skip at every pass — the watch looked dead. Each task said, escaped (SEC-F)."""
    w, calls, buf = _ticking(fail=("_recoveries", "_reassert"))
    w._ttl_check_counter = 29
    w.tick()
    assert calls[2:] == HOUSEKEEPING                     # after the poll and « Verify »
    out = _flat(buf)
    assert f"watch: _recoveries en erreur : _recoveries {EVIL}" in out
    assert f"watch: _reassert en erreur : _reassert {EVIL}" in out


def test_a_bad_iteration_is_said_and_the_loop_goes_on_until_ctrl_c(monkeypatch):
    """The daemon outlives a bad iteration; Ctrl+C stops the rules' poller and removes the heartbeat."""
    w, calls, buf = _ticking()
    polls = iter([RuntimeError(f"unreadable {EVIL}"), None])

    def _poll():
        calls.append("_poll")
        err = next(polls)
        if err:
            raise err
    w.channel = SimpleNamespace(_poll=_poll)
    sleeps = []

    def _sleep(s):
        sleeps.append(s)
        if len(sleeps) == 2:
            raise KeyboardInterrupt
    monkeypatch.setattr(loop.time, "sleep", _sleep)
    w.run_forever()
    assert calls == ["_poll", "_poll", "stop", "_remove_heartbeat"]
    assert w._ttl_check_counter == 1                       # the iteration that raised is not counted
    out = _flat(buf)
    assert f"watch: itération en erreur : unreadable {EVIL}" in out and out.endswith("Watch stopped.")


# ── 2. runs/: the channel's room (SEC8) ──────────────────────────────────────────────────────────

def _room(monkeypatch, polls=2, per_vm=2, vms=2, queues=None) -> ChannelRoom:
    monkeypatch.setattr(channel_reader, "CHANNEL_POLLS", polls)
    monkeypatch.setattr(channel_reader, "CHANNEL_QUEUED_PER_VM", per_vm)
    monkeypatch.setattr(channel_reader, "CHANNEL_VMS", vms)
    return ChannelRoom(queues if queues is not None else {})


def _vm(i: int) -> str:
    return VM.replace("web", f"vm-{i}")


def test_one_search_per_vm_and_technique_its_room_given_back_when_it_ends(monkeypatch):
    room = _room(monkeypatch)
    why, search = room._channel_room(_line("attack_started"))
    assert why == "" and search == (VM.lower(), "T1486")
    why, again = room._channel_room(_line("attack_started", resource_id=VM.upper()))
    assert "déjà en cours" in why and again is None
    room._free_search(search)
    assert room._channel_room(_line("attack_started"))[0] == ""


def test_the_searches_in_flight_are_bounded(monkeypatch):
    room = _room(monkeypatch, polls=2, vms=10)
    assert [room._channel_room(_line("attack_started", resource_id=_vm(i)))[0] for i in range(2)] == ["", ""]
    why, _ = room._channel_room(_line("attack_started", resource_id=_vm(3)))
    assert why == "2 recherches du canal déjà en cours : une de plus est refusée"


def test_the_lines_waiting_for_one_vm_are_bounded_and_freed_as_they_are_decided(monkeypatch):
    room = _room(monkeypatch, per_vm=2)
    assert [room._channel_room(_line())[0] for _ in range(2)] == ["", ""]
    assert room._channel_room(_line())[0].startswith("2 lignes du canal attendent déjà")
    room._free_line(VM.lower())
    assert room._channel_room(_line())[0] == ""
    for _ in range(5):
        room._free_line("never-seen")
    assert room._channel_waiting["never-seen"] == 0       # never below nothing


def test_the_vms_the_channel_names_are_bounded_a_vm_with_a_queue_already_named(monkeypatch):
    queues: dict = {}
    room = _room(monkeypatch, vms=2, per_vm=10, queues=queues)
    assert [room._channel_room(_line(resource_id=_vm(i)))[0] for i in range(2)] == ["", ""]
    assert room._channel_room(_line(resource_id=_vm(2)))[0] == "le canal nomme déjà 2 VM : une de plus est refusée"
    queues[_vm(3).lower()] = object()                      # a queue of its own already (the RulePoller's)
    assert room._channel_room(_line(resource_id=_vm(3)))[0] == ""


def test_a_line_of_runs_is_admitted_then_dispatched_with_its_source_a_bad_one_said(tmp_path):
    console, buf = _console()
    runs = tmp_path / "runs"
    (runs / "annatar").mkdir(parents=True)
    dispatched: list = []
    channel = runs_channel.RunsChannel(console, threading.Lock(), str(runs),
                                       lambda data, sig, source="": dispatched.append((data["signal_id"], source)))
    with open(runs / "annatar" / "r1_signals.jsonl", "a") as f:
        f.write(json.dumps(_line(signal_id="r1_detection_missed", context={"run_id": "r1"})) + "\n")
        f.write("{not json\n")
    channel._poll()
    assert dispatched == [("r1_detection_missed", "r1_signals.jsonl")]
    assert "Ligne de signal ignorée (r1_signals.jsonl)" in _flat(buf)


def test_the_channels_rate_passed_is_said_in_one_line_and_counted(monkeypatch):
    console, buf = _console()
    refused: list = []
    monkeypatch.setattr("glorfindel.signal_origin.refuse", lambda data, why, files, count=1: refused.append(count))
    channel = runs_channel.RunsChannel.__new__(runs_channel.RunsChannel)
    channel.console, channel._output_lock = console, threading.Lock()
    channel._say_rate({f"f{i}_signals.jsonl": (2, 10) for i in range(7)})
    out = _flat(buf)
    assert out.count("Canal runs/ :") == 1 and "14 ligne(s) refusée(s) et 70 octet(s) non lus" in out
    assert " …" in out and refused == [14]


# ── 3. A VM's queue and its thread ───────────────────────────────────────────────────────────────

def _dispatcher(show_signal=None, show_decision=None, respond=None, room=None):
    console, buf = _console()
    agent = SimpleNamespace(respond=respond or (lambda data: {"action": "none"}), incidents=None)
    d = Dispatcher(console, threading.Lock(), agent, dry_run=True,
                   show_signal=show_signal or (lambda sig: None),
                   show_decision=show_decision or (lambda state, dry_run: None))
    return d, buf


class _Queue:
    def __init__(self):
        self.back: list = []
        self.done = 0

    def put_back(self, item, wait_s):
        self.back.append((item, wait_s))

    def task_done(self):
        self.done += 1


def test_one_worker_per_vm_whatever_the_case_of_its_id(monkeypatch):
    """Real run, 2026-10-05: the RulePoller's lowercase id and Annatar's canonical one ran two
    decisions of one VM in parallel."""
    started: list = []
    monkeypatch.setattr(Dispatcher, "_worker", lambda self, q, key: started.append(key))
    d, _ = _dispatcher()
    q1 = d._get_or_start_worker(VM)
    q2 = d._get_or_start_worker(VM.lower())
    _join(f"glorf-{VM.split('/')[-1]}")
    assert q1 is q2 and started == [VM.lower()] and list(d._resource_queues) == [VM.lower()]


def test_a_display_that_fails_never_stands_between_a_detection_and_its_decision(monkeypatch):
    def broken(sig):
        raise RuntimeError(f"head {EVIL}")
    d, buf = _dispatcher(show_signal=broken)
    monkeypatch.setattr("glorfindel.decision_queue.decide_or_card",
                        lambda data, respond, gate, **k: (respond(data), "", 0.0))
    q, data = _Queue(), _line()
    d.room._channel_waiting[VM.lower()] = 1
    d._one(q, VM.lower(), (data, _sig(data), True))
    out = _flat(buf)
    assert f"Affichage du signal en erreur : head {EVIL}" in out and q.done == 1
    assert d.room._channel_waiting[VM.lower()] == 0        # decided: its channel line freed


def test_a_detection_past_the_ceiling_waits_in_its_queue_and_its_line_still_counts(monkeypatch):
    d, buf = _dispatcher()
    monkeypatch.setattr("glorfindel.decision_queue.decide_or_card", lambda data, respond, gate, **k: (None, "plafond", 30.0))
    q, data = _Queue(), _line()
    d.room._channel_waiting[VM.lower()] = 1
    d._one(q, VM.lower(), (data, _sig(data), True))
    assert q.back and q.back[0][1] == 30.0
    assert d.room._channel_waiting[VM.lower()] == 1        # it still waits
    assert "En attente du plafond (30 s) : plafond" in _flat(buf)


def test_a_detection_the_model_does_not_decide_is_said_as_its_card():
    d, buf = _dispatcher()
    d._say_decided(_sig(_line()), None, "même passe", 0.0)
    assert "Non décidée par le modèle : même passe — carte undecided_detection" in _flat(buf)


def test_a_decision_whose_display_fails_is_said_taken_never_unprocessed(monkeypatch):
    def broken(state, dry_run):
        raise ValueError(f"display {EVIL}")
    d, buf = _dispatcher(show_decision=broken)
    d._say_decided(_sig(_line()), {"action": "isolate_vm"}, "", 0.0)
    out = _flat(buf)
    assert f"Décision prise pour s1, son affichage a échoué : display {EVIL}" in out
    assert "Error processing" not in out


def test_a_detection_out_of_a_full_queue_is_said_carded_and_frees_its_line(monkeypatch):
    recorded: list = []
    monkeypatch.setattr("glorfindel.decision_queue.record_undecided",
                        lambda data, kind, why, dry_run=False: recorded.append((data["signal_id"], kind)))
    d, buf = _dispatcher()
    d.room._channel_waiting[VM.lower()] = 1
    data = _line()
    d._left(VM, VM.lower(), (data, _sig(data), True), "file pleine")
    assert recorded == [("s1", "full")] and d.room._channel_waiting[VM.lower()] == 0
    assert f"File pleine ({VM}) : s1 — file pleine ; carte undecided_detection" in _flat(buf)


def test_whatever_one_detection_raised_its_vms_thread_takes_the_next(monkeypatch):
    d, buf = _dispatcher()
    taken: list = []
    a, b = _line(signal_id="a"), _line(signal_id="b")
    items = iter([(a, _sig(a), False), (b, _sig(b), False), None])

    def one(q, key, item):
        taken.append(item[0]["signal_id"])
        if item[0]["signal_id"] == "a":
            raise RuntimeError(EVIL)
    monkeypatch.setattr(d, "_one", one)
    d._worker(SimpleNamespace(get=lambda: next(items)), VM.lower())
    assert taken == ["a", "b"] and f"Error processing a : {EVIL}" in _flat(buf)


def test_a_line_the_channel_has_no_room_for_is_refused_said_and_never_queued(monkeypatch):
    d, buf = _dispatcher()
    refused: list = []
    monkeypatch.setattr("glorfindel.signal_origin.refuse", lambda data, why, source: refused.append(source))
    monkeypatch.setattr(d.room, "_channel_room", lambda data: ("plus de place", None))
    queued: list = []
    monkeypatch.setattr(d, "_get_or_start_worker", lambda rid: SimpleNamespace(put=queued.append))
    data = _line()
    d._dispatch(data, _sig(data), source="x_signals.jsonl")
    assert refused == ["x_signals.jsonl"] and queued == []
    assert "Signal refusé (x_signals.jsonl) : plus de place" in _flat(buf)
    d._dispatch(data, _sig(data))                            # the RulePoller's: never bounded by the channel
    assert queued == [(data, _sig(data), False)]


def test_an_attack_line_is_searched_in_its_own_thread_and_its_search_freed(monkeypatch):
    d, _ = _dispatcher()
    queued: list = []
    monkeypatch.setattr(d, "_get_or_start_worker", lambda rid: SimpleNamespace(put=queued.append))
    monkeypatch.setattr("glorfindel.agent.resolve_attack_started",
                        lambda data, ip_owners=None: {**data, "event": "detection"})
    noted: list = []
    d.watch_channel = SimpleNamespace(note_poll=noted.append)
    data = _line("attack_started", signal_id="r1_attack")
    d._dispatch(data, _sig(data), source="r1_signals.jsonl")
    _join("poll-web-attack")
    assert [item[0]["event"] for item in queued] == ["detection"] and queued[0][2] is False
    assert noted and d.room._channel_polls == set()


def test_a_search_that_fails_is_a_card_said_never_a_thread_dead_in_silence(monkeypatch):
    d, buf = _dispatcher()
    failed: list = []

    def resolve(data, ip_owners=None):
        raise RuntimeError(f"backend {EVIL}")
    monkeypatch.setattr("glorfindel.agent.resolve_attack_started", resolve)
    monkeypatch.setattr("glorfindel.agent.record_cycle_failure",
                        lambda data, exc, stage, dry_run: failed.append(stage))
    data = _line("attack_started", signal_id="r1_attack")
    d._poll_and_enqueue(data, _sig(data), VM)
    assert failed == ["detection"] and d._resource_queues == {}
    assert f"Détection impossible pour r1_attack (escalade cycle_failed enregistrée) : backend {EVIL}" in _flat(buf)


def test_a_rule_detection_is_noted_on_the_return_channel_then_queued(monkeypatch):
    d, _ = _dispatcher()
    seen: list = []
    d.watch_channel = SimpleNamespace(note=lambda data: seen.append(("noted", data["signal_id"])))
    monkeypatch.setattr(d, "_dispatch", lambda data, sig, source="": seen.append(("queued", sig.signal_id, source)))
    d._rule_dispatch(_line(signal_id="watch-rule-1", unknown_field=1))
    d._emit_recovery(_line("recovery_complete", signal_id="rec-1"))
    assert seen == [("noted", "watch-rule-1"), ("queued", "watch-rule-1", ""), ("queued", "rec-1", "")]


# ── 4. The passes, one at a time ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [(None, 60.0), ("abc", 60.0), ("", 60.0), ("0", 0.0), ("2.5", 2.5)])
def test_a_pass_interval_that_does_not_read_keeps_a_minute(raw, expected, monkeypatch):
    if raw is None:
        monkeypatch.delenv("GLORFINDEL_RECOVERY_INTERVAL_S", raising=False)
    else:
        monkeypatch.setenv("GLORFINDEL_RECOVERY_INTERVAL_S", raw)
    assert passes.interval_s("GLORFINDEL_RECOVERY_INTERVAL_S") == expected


def test_one_thread_of_a_kind_at_a_time():
    solo, go = passes.Solo("solo-test"), threading.Event()
    assert not solo.busy()
    solo.start(go.wait)
    assert solo.busy() and solo._thread.name == "solo-test" and solo._thread.daemon
    go.set()
    solo._thread.join(timeout=5)
    assert not solo.busy()


class _Connector:
    read_only = False

    def __init__(self, dry_run=False):
        self.dry_run = dry_run


def _housekeeping(monkeypatch, dry_run=False, **env):
    monkeypatch.setattr("glorfindel.actions.AzureConnector", _Connector)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    console, buf = _console()
    said: list = []
    hk = Housekeeping(console, threading.Lock(), dry_run=dry_run, mode_override="human_only", runs_dir="runs",
                      ttl_h=4.0, emit=lambda data: None, say_channel=said.append)
    return hk, buf, said


def _passes_of(monkeypatch, name: str) -> list:
    ran: list = []
    monkeypatch.setattr(passes, name, lambda *a, **k: ran.append(a))
    return ran


def test_the_reassertion_starts_with_nothing_recorded_once_its_interval_passed(monkeypatch):
    """I1F (#226): the pass reads our quarantines whatever the local state says — nothing recorded
    here, the pass starts all the same; never before its interval, never two at once."""
    ran = _passes_of(monkeypatch, "_watch_reassert_pass")
    hk, _, _ = _housekeeping(monkeypatch, GLORFINDEL_REASSERT_INTERVAL_S="60")
    hk._reassert()
    assert ran == []                                       # its first pass a full interval after the start
    hk._last_reassert = time.time() - 61
    hk._reassert()
    _join("reassert")
    assert len(ran) == 1 and ran[0][1] is hk.ttl_connector and ran[0][2] == "human_only"
    assert ran[0][4] is hk._reassert_seen                  # its memory between passes


@pytest.mark.parametrize("why", ["dry_run", "interval", "read_only", "busy"])
def test_the_reassertion_never_starts_where_it_must_not(why, monkeypatch):
    ran = _passes_of(monkeypatch, "_watch_reassert_pass")
    hk, _, _ = _housekeeping(monkeypatch, dry_run=why == "dry_run",
                             GLORFINDEL_REASSERT_INTERVAL_S="0" if why == "interval" else "60")
    hk._last_reassert = 0.0
    if why == "read_only":
        hk.ttl_connector.read_only = True
    go = threading.Event()
    if why == "busy":
        hk._reassert_thread.start(go.wait)
    hk._reassert()
    go.set()
    _join("reassert")
    assert ran == []
    if why == "busy":
        assert hk._last_reassert == 0.0                    # tried again at the next housekeeping


def test_the_first_recovery_pass_runs_at_the_first_housekeeping_then_every_interval(monkeypatch):
    ran = _passes_of(monkeypatch, "_watch_recovery_pass")
    hk, _, _ = _housekeeping(monkeypatch, GLORFINDEL_RECOVERY_INTERVAL_S="60")
    hk._recoveries()
    _join("recoveries")
    hk._recoveries()
    _join("recoveries")
    assert len(ran) == 1 and ran[0][2] is hk._emit_recovery and ran[0][4] is hk._recovery_said


@pytest.mark.parametrize("dry_run,interval", [(True, "60"), (False, "0")])
def test_no_recovery_pass_in_a_dry_run_or_at_0(dry_run, interval, monkeypatch):
    ran = _passes_of(monkeypatch, "_watch_recovery_pass")
    hk, _, _ = _housekeeping(monkeypatch, dry_run=dry_run, GLORFINDEL_RECOVERY_INTERVAL_S=interval)
    hk._recoveries()
    _join("recoveries")
    assert ran == []


def test_the_door_facts_run_one_pass_at_a_time_off_at_0(monkeypatch):
    ran = _passes_of(monkeypatch, "_watch_door_pass")
    hk, _, _ = _housekeeping(monkeypatch)
    monkeypatch.setattr("glorfindel.door_facts.interval_s", lambda: 0)
    hk._door_facts()
    assert ran == []
    monkeypatch.setattr("glorfindel.door_facts.interval_s", lambda: 900)
    hk._door_facts()
    _join("door-facts")
    assert len(ran) == 1 and ran[0][3] is hk._door_said


def test_verify_reads_graph_only_when_asked_in_its_own_thread_and_says_its_failure(monkeypatch):
    hk, buf, _ = _housekeeping(monkeypatch)
    asked: list = []
    monkeypatch.setattr("glorfindel.escalations.identity_checks_requested", lambda: asked)

    def run_requested():
        raise RuntimeError(f"graph {EVIL}")
    monkeypatch.setattr("glorfindel.identity_checks.run_requested", run_requested)
    hk._identity_checks()
    assert hk._identity_thread._thread is None               # nothing waits: no Graph call
    asked.append({"id": "x"})
    hk._identity_checks()
    _join("identity-checks")
    assert f"watch: vérification d'identité en erreur : graph {EVIL}" in _flat(buf)


def test_the_notices_relay_never_holds_the_loop_and_runs_one_pass_at_a_time(monkeypatch):
    """JUG2b (#768): a webhook that does not answer holds its own thread, never the loop."""
    hk, buf, _ = _housekeeping(monkeypatch)
    entered, go = threading.Event(), threading.Event()
    passes_run: list = []

    def relay_pass():
        passes_run.append(1)
        entered.set()
        go.wait(10)
        return 2
    monkeypatch.setattr("glorfindel.vm_notices.relay_pass", relay_pass)
    hk._relay_notices()
    assert entered.wait(5)
    hk._relay_notices()                                    # the first still waits: none started
    go.set()
    _join("relay-notices")
    assert passes_run == [1]
    assert "2 notice(s) dite(s) par le webhook" in _flat(buf)


def test_past_the_ttl_an_isolation_is_said_escalated_never_released(monkeypatch):
    hk, buf, _ = _housekeeping(monkeypatch)
    monkeypatch.setattr("glorfindel.reassert.ttl_alerts", lambda ttl_h: [{"vm": "web", "age_h": 5.25}])
    hk._check_ttl()
    assert "TTL exceeded — web isolated 5.2h (limit 4.0h): escalated, NOT released" in _flat(buf)
    hk.dry_run = True
    monkeypatch.setattr("glorfindel.reassert.ttl_alerts", lambda ttl_h: pytest.fail("read in a dry run"))
    hk._check_ttl()


def test_the_jobs_are_reconciled_only_when_one_is_in_progress(monkeypatch):
    hk, buf, _ = _housekeeping(monkeypatch)
    jobs: list = [{"status": "Completed"}]
    monkeypatch.setattr("glorfindel.jobs.all_jobs", lambda: jobs)
    monkeypatch.setattr("glorfindel.jobs.reconcile_jobs", lambda connector: pytest.fail("no job pending"))
    hk._reconcile_jobs()
    jobs.append({"status": "InProgress"})
    monkeypatch.setattr("glorfindel.jobs.reconcile_jobs", lambda connector: [
        {"type": "restore", "resource_id": VM, "status": "Completed"}])
    hk._reconcile_jobs()
    assert "Job restore web → Completed" in _flat(buf)


def test_the_windows_the_verdicts_and_the_drill_are_read_from_the_watchs_runs(monkeypatch):
    hk, _, said = _housekeeping(monkeypatch)
    seen: list = []
    monkeypatch.setattr("eregion_core.exercise.observe", lambda: seen.append("observe"))
    monkeypatch.setattr("eregion_core.runs_layout.say_strays", lambda root, say: (seen.append(root), say("stray")))
    monkeypatch.setattr("glorfindel.proposed_verdict.refresh", lambda root, say: (seen.append(root), say("card")))
    monkeypatch.setattr("glorfindel.drill_watch.refresh", lambda root: seen.append(("drill", root)))
    hk._observe_windows()
    hk._propose_verdicts()
    hk._judge_drill()
    assert seen == ["observe", "runs", "runs", ("drill", "runs")]
    assert said == ["Canal runs/ : stray", "Verdict proposé : card"]


# ── 5. The heartbeats ────────────────────────────────────────────────────────────────────────────

def test_both_heartbeats_are_written_and_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(beat, "_INJECTORS_DIR", tmp_path / ".glorfindel" / "injectors")
    monkeypatch.setattr("eregion_core.watch_key.shared", lambda: (None, "no key here"))
    console, buf = _console()
    beat._make_injectors_dir(console)
    assert stat.S_IMODE(os.stat(tmp_path / ".glorfindel" / "injectors").st_mode) == 0o755
    hb = beat.Heartbeat(console)
    hb._write_heartbeat()
    assert datetime.fromisoformat(hb._HEARTBEAT.read_text()) <= datetime.now(timezone.utc)
    assert "at" in json.loads(hb._INJECTOR_BEAT.read_text())
    assert stat.S_IMODE(os.stat(hb._INJECTOR_BEAT).st_mode) == 0o644
    hb._remove_heartbeat()
    assert not hb._HEARTBEAT.exists() and not hb._INJECTOR_BEAT.exists()
    hb._INJECTOR_BEAT.mkdir()                              # a file in its place: never an error at stop
    hb._remove_heartbeat()


def test_the_injectors_beat_not_written_is_said_and_the_watch_goes_on(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(beat, "_INJECTORS_DIR", tmp_path / "root-owned")
    monkeypatch.setattr("eregion_core.watch_key.shared", lambda: (None, "no key here"))
    (tmp_path / "root-owned").write_text("not a directory")
    console, buf = _console()
    beat.Heartbeat(console)._write_heartbeat()
    assert (tmp_path / ".glorfindel" / "watch_heartbeat").exists()
    assert "Battement pour les injecteurs non écrit" in _flat(buf)


@pytest.mark.parametrize("age_s,warned", [(10, True), (200, False), (None, False)])
def test_a_fresh_heartbeat_of_another_watch_is_said(age_s, warned, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    console, buf = _console()
    hb = beat.Heartbeat(console)
    hb._HEARTBEAT.parent.mkdir(parents=True)
    hb._HEARTBEAT.write_text("not a date" if age_s is None
                             else (datetime.now(timezone.utc) - timedelta(seconds=age_s)).isoformat())
    hb.warn_if_another()
    assert ("Another glorfindel watch appears to be running" in _flat(buf)) is warned


def test_the_watch_key_is_said_once_until_what_it_says_changes(monkeypatch):
    console, buf = _console()
    answers = iter([(None, "no key"), (None, "no key"), (SimpleNamespace(fingerprint="ab12"), "")])
    monkeypatch.setattr("eregion_core.watch_key.shared", lambda: next(answers))
    hb = beat.Heartbeat(console)
    assert hb._signer() is None and hb._signer() is None
    assert hb._signer().fingerprint == "ab12"
    out = _flat(buf)
    assert out.count("Clé de la watch indisponible") == 1 and out.count("Clé de la watch : ab12") == 1


# ── 6. The rules: the poller kept, what fails said ───────────────────────────────────────────────

class _Poller:
    _live: list = []                                       # what conftest stops after each test

    def __init__(self, rules, dispatch, **kw):
        self.kw, self.started, self.stopped = kw, False, False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def _det_cfg(**over):
    rule = SimpleNamespace(auto_apply=False, layer="base", resource_id="")
    return SimpleNamespace(**{"rules": [rule], "notes": [], "overrides": [], "disabled_base": [], "drifted": [],
                              "client_file": None, **over})


def test_without_a_rules_file_nothing_is_loaded_nor_audited(monkeypatch):
    console, _ = _console()
    monkeypatch.setattr("glorfindel.detection_rules.load_config", lambda *a, **k: pytest.fail("loaded"))
    r = rules.Rules(console, None, dry_run=False, mode_override=None)
    r.start(lambda data: None, None)
    r.start_audit()
    r.stop()
    assert r._rule_poller is None


def test_the_poller_is_kept_and_stopped_even_when_what_follows_it_fails(monkeypatch):
    """Discovery failing after the poller started: said, and the poller still stopped at Ctrl+C."""
    console, buf = _console()
    monkeypatch.setattr("glorfindel.config.load_glorfindel_config", lambda: SimpleNamespace(monitoring_backends=[]))
    monkeypatch.setattr("glorfindel.detection_rules.load_config", lambda path, glorfindel_cfg: _det_cfg())
    monkeypatch.setattr("glorfindel.detection_rules.RulePoller", _Poller)

    def broken():
        raise RuntimeError(f"cache {EVIL}")
    monkeypatch.setattr("glorfindel.discovery.AssetRegistry", broken)
    r = rules.Rules(console, "rules.yaml", dry_run=True, mode_override=None)
    r.start(lambda data: None, ip_owners=None)
    assert r._rule_poller.started and r._rule_poller.kw["topology"] is None      # a dry run reads no Azure
    assert f"Could not load rules: cache {EVIL}" in _flat(buf)
    r.stop()
    assert r._rule_poller.stopped


def test_the_client_layer_is_said_its_drift_loudly(monkeypatch):
    console, buf = _console()
    rules._say_layers(console, _det_cfg(client_file="client.yaml", notes=[f"note {EVIL}"],
                                        overrides=["a"], disabled_base=["b"], drifted=["c"]))
    out = _flat(buf)
    assert "Couche du client : 0 règle(s) — client.yaml" in out and f"· note {EVIL}" in out
    assert "« a » remplacée" in out and "« b » désactivée" in out and "« c » : copie périmée" in out


def test_an_expansion_that_fails_is_said_and_never_stops_the_loop(monkeypatch):
    console, buf = _console()
    r = rules.Rules(console, "rules.yaml", dry_run=False, mode_override=None)

    def expand(registry, cfg):
        raise RuntimeError(f"expand {EVIL}")
    r._rule_poller = SimpleNamespace(expand_for_discovered=expand)
    r._expand_once(None, None)
    assert f"expand rules: expand {EVIL}" in _flat(buf)


# ── 7. What the startup says and refuses ─────────────────────────────────────────────────────────

def _agent(default="human_only", modes=(), config_error="", perm="read_write"):
    return SimpleNamespace(autonomy=SimpleNamespace(default=default, assets=[SimpleNamespace(mode=m) for m in modes]),
                           config_error=config_error, connector=SimpleNamespace(permission_mode=lambda: perm))


def test_a_badly_written_config_stops_the_watch_before_anything(monkeypatch):
    from glorfindel import config
    console, buf = _console()

    def refused():
        raise config.ConfigError(f"isolation.quarantine_nsg {EVIL}")
    monkeypatch.setattr(config, "load_glorfindel_config", refused)
    with pytest.raises(SystemExit) as e:
        startup._refuse_bad_config(console)
    assert e.value.code == 2 and f"isolation.quarantine_nsg {EVIL}" in _flat(buf)


def test_an_unreadable_config_says_every_vm_in_human_only_the_mode_ignored(monkeypatch):
    monkeypatch.setattr("glorfindel.escalations.alerting_configured", lambda: True)
    console, buf = _console()
    startup._say_autonomy(console, _agent(config_error=f"broken {EVIL}"), "non_disruptive", dry_run=False)
    out = _flat(buf)
    assert f"glorfindel-config.yaml illisible (broken {EVIL})" in out and "--mode non_disruptive ignoré" in out


@pytest.mark.parametrize("default,modes,dry_run,gate", [
    ("human_only", (), False, False), ("non_disruptive", (), False, True),
    ("human_only", ("non_disruptive",), False, True), ("non_disruptive", (), True, False)])
def test_the_readiness_gate_is_said_where_a_vm_may_act_alone(default, modes, dry_run, gate, monkeypatch):
    monkeypatch.setattr("glorfindel.escalations.alerting_configured", lambda: True)
    console, buf = _console()
    startup._say_autonomy(console, _agent(default, modes), None, dry_run)
    assert ("Readiness gate" in _flat(buf)) is gate


@pytest.mark.parametrize("default,alerting,warned", [
    ("human_only", False, True), ("human_only", True, False), ("non_disruptive", False, False)])
def test_human_only_without_alerting_is_said(default, alerting, warned, monkeypatch):
    monkeypatch.setattr("glorfindel.escalations.alerting_configured", lambda: alerting)
    console, buf = _console()
    startup._say_autonomy(console, _agent(default), None, dry_run=True)
    assert ("human_only mode active but no alerting configured" in _flat(buf)) is warned


@pytest.mark.parametrize("default,said", [("non_disruptive", "Autonomous actions will fail"),
                                          ("human_only", "Observe-only deployment")])
def test_read_only_credentials_are_said_by_what_the_modes_would_do(default, said, monkeypatch):
    monkeypatch.setenv("AZURE_CLIENT_ID", "app-id")
    console, buf = _console()
    startup._say_credentials(console, _agent(default, perm="read_only"), dry_run=False)
    out = _flat(buf)
    assert "Credentials: read_only" in out and said in out and "Identity:" not in out


def test_a_second_watch_on_this_home_is_refused_another_failure_of_the_queue_said(monkeypatch):
    from glorfindel import queue_watch
    monkeypatch.setattr("glorfindel.actions.AzureConnector", _Connector)
    monkeypatch.setattr("glorfindel.escalations.sign_proposals", lambda signer: None)
    console, buf = _console()

    def second(*a, **k):
        raise queue_watch.SecondWatch(f"une autre watch {EVIL}")
    monkeypatch.setattr(queue_watch, "start", second)
    with pytest.raises(SystemExit) as e:
        startup._start_action_queue(console, True, None, print, "runs")
    assert e.value.code == 1 and f"Watch refusée : une autre watch {EVIL}" in _flat(buf)

    def broken(*a, **k):
        raise OSError("queue unreadable")
    monkeypatch.setattr(queue_watch, "start", broken)
    startup._start_action_queue(console, True, None, print, "runs")      # goes on
    assert "File d'actions non relevée : queue unreadable" in _flat(buf)


def test_a_dry_run_opens_no_return_channel_and_sets_no_writes_aside(monkeypatch):
    monkeypatch.setattr("eregion_core.watch_channel.start", lambda: pytest.fail("a channel in a dry run"))
    console, buf = _console()
    registered: list = []
    monkeypatch.setattr("glorfindel.own_channel.register", lambda source: registered.append(source))
    monkeypatch.setattr("glorfindel.own_channel.register_exercise", lambda pair: registered.append(pair))
    assert startup._open_return_channel(console, True, "runs") is None
    startup._register_own_writes(console, None, True)
    assert registered == [None, (None, "")] and buf.getvalue() == ""


def test_the_loop_is_no_longer_in_the_cli():
    """WCH1: `glorfindel watch` stays the command; its loop is glorfindel/watch/."""
    import inspect

    from glorfindel import cli
    src = inspect.getsource(cli.watch.callback)
    assert "from glorfindel.watch.loop import run" in src and len(src.splitlines()) < 30


def test_an_agent_that_cannot_be_imported_is_said_never_a_search_thread_dead_in_silence(monkeypatch):
    """The review of WCH1: the search thread imports the agent inside its guarded block. If the
    agent cannot be imported at all, its escalation cannot be recorded either: the failure is said
    all the same, and the thread returns instead of dying."""
    import sys
    import types
    d, buf = _dispatcher()
    monkeypatch.setitem(sys.modules, "glorfindel.agent", types.ModuleType("glorfindel.agent"))
    data = _line("attack_started", signal_id="r2_attack")
    d._poll_and_enqueue(data, _sig(data), VM)
    assert d._resource_queues == {}
    said = _flat(buf)
    assert "Détection impossible pour r2_attack, et son escalade non enregistrée (ImportError)" in said
