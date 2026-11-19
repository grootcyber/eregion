"""DRL1b (#613; docs/design/drill-banc.md §4.2): the drill of the week judged on Imladris — each
occurrence's verdict by the code, its alert and its mention exactly as §4.2's table; the absence alarm
armed on its four conditions only; the pull that lists the drill's blobs (the permit judged by the
listing); the bot's thread; the console's « Weekly drill » line and the tile of the last proof.

Built on the drill as this host's image holds it (``drills/banc-hebdo.yaml``): its hour and its
fingerprint are read from it, never written here. What the pull saw, the pulse, Orodruin's status,
the run's report and the watch's cycle are written as Imladris would hold them. No Azure, no model, a
throwaway HOME (the conftest), a false clock (``now``), a false channel (``get``), a false bot.

The table of §4.2, copied: ``MENTIONS`` below — each state, and each refusal code, its mention.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from eregion_core import drill as dr
from eregion_core import drill_arming as da
from eregion_core import exercise_channel as xc
from glorfindel import drill_watch as dw

DRILL = "banc-hebdo"
SUB = "00000000-0000-0000-0000-000000000000"
VM = f"/subscriptions/{SUB}/resourceGroups/rg-bench/providers/Microsoft.Compute/virtualMachines/vm-one"
REQ = "r-20261117T190000Z-abc123"
RUN = "20261117T190100Z-ab12"
COPY, SHA = dr.loaded(dr.shipped_dir() / f"{DRILL}.yaml", dr.SHIPPED)
EXPERIMENT = COPY.wires[0].experiment
AT = COPY.schedule.occurrence(datetime(2026, 11, 20, tzinfo=timezone.utc))
ARMED_AT = AT - timedelta(days=5)
OTHER_SHA = "f" * 64

# §4.2, copied: (state, refusal code) → whether its alert mentions the role.
MENTIONS = {
    ("missed", ""): True, ("not_run", ""): True, ("self_disarmed", ""): True,
    ("proof", ""): False, ("skipped", ""): False, ("stopped", ""): False, ("rearm_expected", ""): False,
    **{("refused", c): True for c in ("passive", "not_placed", "not_bench", "off_schedule", "too_soon",
                                      "permit_mismatch")},
    **{("refused", c): False for c in ("drill_changed", "no_permit")},
}


class World:
    """What reached Imladris of the drill: the last pull's sight, the pulse kept, Orodruin's status of the
    occurrence's request, its run's report and the watch's decision on it."""

    def __init__(self, root: Path):
        self.root = root
        self.oro = root / "glorfindel" / "orodruin"
        self.oro.mkdir(parents=True)
        self.history: dict = {}
        self.previous: dict = {}
        self.pulled_at: datetime | None = None      # None: the last pull is a minute before the judge
        self._pulse = None
        self.seen()
        self.pulse()

    def seen(self, *, listed=True, permit=True, permit_doc=None, permit_why="", pulse_listed=True,
             pulse_why="", modified=None, unread_since="", why="", last_listed=None) -> None:
        doc = permit_doc if permit_doc is not None else {"drill": DRILL, "sha256": SHA, "armed_at": ARMED_AT.isoformat()}
        self._seen = {"listed": listed, "why": why, "listed_at": "", "unread_since": unread_since,
                      "permit": {"listed": permit, "doc": doc if permit and not permit_why else None,
                                 "why": permit_why, "last_listed": last_listed.isoformat() if last_listed else ""},
                      "pulse": {"listed": pulse_listed, "why": pulse_why,
                                "modified": (modified or AT + timedelta(minutes=20)).isoformat()}}
        self.write(AT + timedelta(hours=1))

    def pulse(self, *, state="armed", reason="", sha=SHA, drill=DRILL, last=None, at=None) -> None:
        self._pulse = da.pulse(state=state, reason=reason, drill=drill, sha256=sha,
                               next_at=(AT + timedelta(days=7)).isoformat(), last=last, image="commit 0123abc",
                               at=(at or AT + timedelta(minutes=20)).isoformat())
        self.write(AT + timedelta(hours=1))

    def no_pulse(self) -> None:
        self._pulse = None
        self.write(AT + timedelta(hours=1))

    def write(self, at: datetime) -> None:
        seen = {**self._seen, "at": at.isoformat(), "pulse": {**self._seen["pulse"], "doc": self._pulse}}
        (self.oro / xc.SEEN_FILE).write_text(json.dumps(seen))

    @staticmethod
    def last(state="played", code="", occurrence=AT, request=REQ) -> dict:
        return {"at": (occurrence + timedelta(minutes=20)).isoformat(), "occurrence": occurrence.isoformat(),
                "state": state, "code": code, "request": request if state not in ("refused",) or request else ""}

    def played(self, *, detection="detected", decision=True, status=True, state="finished") -> None:
        self.pulse(last=self.last())
        if status:
            doc = {"request": REQ, "state": state, "at": (AT + timedelta(minutes=20)).isoformat(), "codes": [],
                   "wires": [{"rank": 1, "state": "done", "code": "", "runs": [RUN], "result": detection}],
                   "drill": {"name": DRILL, "sha256": SHA, "occurrence": AT.isoformat()}}
            (self.oro / "requests").mkdir(exist_ok=True)
            (self.oro / "requests" / f"{REQ}.json").write_text(json.dumps(doc))
        t0 = AT + timedelta(minutes=2)
        m = {"run_format": 1, "kind": "technique", "injector": "annatar", "experiment_id": EXPERIMENT,
             "resource_id": VM, "request": REQ, "attack_time": t0.isoformat(), "detection": detection,
             "detection_latency_s": 120 if detection == "detected" else None}
        (self.root / "glorfindel" / f"{RUN}.json").write_text(json.dumps(
            {"scenario": "s", "run_id": RUN, "mitre": EXPERIMENT, "result": "PASS", "metrics": m,
             "thresholds": {}, "checks": {}}))
        if decision:
            seen_at = t0 + timedelta(seconds=120)
            rec = {"timestamp": seen_at.isoformat(), "action": "snapshot",
                   "signal": {"event": "detection", "ttp": EXPERIMENT, "timestamp": seen_at.isoformat(),
                              "resource_id": VM}}
            path = self.root / "glorfindel" / "watch-rule-1_debug.jsonl"
            path.write_text(json.dumps(rec) + "\n")
            os.utime(path, (seen_at.timestamp() + 30, seen_at.timestamp() + 30))

    def judge(self, now: datetime | None = None, **kw) -> dict:
        now = now or AT + timedelta(hours=4)
        self.write(self.pulled_at or now - timedelta(minutes=1))
        src = dw.Sources(self.root, channel=True, history=self.history, previous=self.previous, **kw)
        return dw.judge(src, now)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path / "runs")


def said(v: dict) -> tuple:
    return v["state"], v["code"], v["mention"]


# ── Each state of §4.2, and its mention ─────────────────────────────────────────────────────

def test_a_proof_detected_and_the_decision_attached_a_line_without_mention(world):
    world.played()
    v = world.judge()
    assert said(v) == ("proof", "", False)
    assert (v["drill"], v["occurrence"], v["armed"], v["request"]) == (DRILL, AT.isoformat(), "armed", REQ)
    assert v["next"] == (AT + timedelta(days=7)).isoformat()


def test_detected_without_the_decision_attached_is_no_proof(world):
    world.played(decision=False)
    assert world.judge(AT + timedelta(hours=1))["state"] == "waiting"     # the decision may still come
    assert said(world.judge()) == ("unknown", "unattached", False)


def test_missed_a_regression_with_a_mention(world):
    world.played(detection="missed", decision=False)
    assert said(world.judge()) == ("missed", "missed", True)


def test_unknown_without_mention_the_first_time_with_one_two_in_a_row(world):
    world.played(detection="unknown", decision=False)
    assert said(world.judge()) == ("unknown", "unknown", False)
    world.history[(AT - timedelta(days=7)).isoformat()] = {"state": "unknown", "code": "unknown"}
    assert said(world.judge()) == ("unknown", "unknown", True)
    world.history[(AT - timedelta(days=7)).isoformat()] = {"state": "proof", "code": ""}
    assert world.judge()["mention"] is False


def test_unknown_twice_in_a_row_across_two_passes_of_the_watch(world, tmp_path):
    world.played(detection="unknown", decision=False)
    world.write(AT + timedelta(hours=4) - timedelta(minutes=1))
    dw.refresh(world.root, now=AT + timedelta(hours=4), channel=True)
    assert dw.load()["current"]["mention"] is False
    later = AT + timedelta(days=7)
    world.seen(modified=later + timedelta(minutes=20))
    world.pulse(last=World.last(occurrence=later), at=later + timedelta(minutes=20))
    doc = json.loads((world.oro / "requests" / f"{REQ}.json").read_text())
    doc["drill"]["occurrence"] = later.isoformat()
    (world.oro / "requests" / f"{REQ}.json").write_text(json.dumps(doc))
    world.write(later + timedelta(hours=4) - timedelta(minutes=1))
    v = dw.refresh(world.root, now=later + timedelta(hours=4), channel=True)
    assert said(v) == ("unknown", "unknown", True)
    assert dw.load()["history"][AT.isoformat()]["state"] == "unknown"


@pytest.mark.parametrize(("code", "mentioned"), [(c, m) for (s, c), m in MENTIONS.items() if s == "refused"]
                         + [("watch", False), ("busy", False), ("not_eligible", True), ("over_cap", True)])
def test_refused_its_mention_by_its_code_as_the_table(world, code, mentioned):
    world.pulse(last=World.last("refused", code))
    assert said(world.judge()) == ("refused", code, mentioned)


@pytest.mark.parametrize(("state", "code"), [("skipped", "isolated"), ("skipped", "not_ready"), ("stopped", "stopped")])
def test_skipped_and_stopped_alert_without_mention(world, state, code):
    world.pulse(last=World.last(state, code))
    assert said(world.judge()) == (state, code, False)


def test_an_occurrence_that_broke_is_unknown_said(world):
    world.pulse(last=World.last("failed", "crashed"))
    assert said(world.judge()) == ("unknown", "crashed", False)


def test_the_table_copied_holds_for_every_state():
    for (state, code), mentioned in MENTIONS.items():
        assert dw.mention(state, code) is mentioned, (state, code)
    assert set(dw.REFUSED_MENTION) <= {c for (s, c), m in MENTIONS.items() if s == "refused" and m}
    assert dw.mention("unknown") is False and dw.mention("unknown", previous="unknown") is True
    assert dw.mention("channel_unread", unread_s=dw.UNREAD_MENTION_S - 1) is False
    assert dw.mention("channel_unread", unread_s=dw.UNREAD_MENTION_S) is True


# ── The absence alarm: its four conditions, one by one ───────────────────────────────────────

def test_not_run_when_everything_agrees_and_no_status_two_hours_after(world):
    assert world.judge(AT + timedelta(hours=1, minutes=59))["state"] == "waiting"
    assert said(world.judge(AT + timedelta(hours=2, minutes=1))) == ("not_run", "no_status", True)


def test_orodruin_silent_drill_json_older_than_eight_days(world):
    world.seen(modified=AT - timedelta(days=9))
    assert said(world.judge(AT + timedelta(minutes=30))) == ("not_run", "silent", True)
    world.seen(modified=AT - timedelta(days=7))
    assert world.judge(AT + timedelta(minutes=30))["state"] == "waiting"


def test_the_channel_unread_arms_neither_not_run_nor_rearm_expected(world):
    world.seen(listed=False, why="HTTP 503", unread_since=(AT - timedelta(days=1)).isoformat())
    v = world.judge(AT + timedelta(hours=5))
    assert said(v) == ("channel_unread", "unread", False)
    world.pulse(sha=OTHER_SHA)                          # a fingerprint this host does not have: still unread
    assert world.judge(AT + timedelta(hours=5))["state"] == "channel_unread"


def test_the_channel_unread_eight_days_in_a_row_mentions(world):
    world.seen(listed=False, why="HTTP 503", unread_since=(AT - timedelta(days=8)).isoformat())
    assert said(world.judge(AT + timedelta(hours=1))) == ("channel_unread", "unread", True)


def test_no_permit_listed_and_drill_json_armed_rearm_expected_never_not_run(world):
    world.seen(permit=False)
    (world.oro / "drill-permit.json").write_text(json.dumps(          # a copy on disk: never believed
        {"drill": DRILL, "sha256": SHA, "armed_at": ARMED_AT.isoformat()}))
    assert said(world.judge(AT + timedelta(hours=5))) == ("rearm_expected", "no_permit", False)


def test_drill_json_disarmed_by_the_operator_or_the_kill_says_nothing(world):
    for reason in ("operator", "killed"):
        world.seen(permit=False)
        world.pulse(state="disarmed", reason=reason)
        v = world.judge(AT + timedelta(hours=5))
        assert (v["state"], v["code"]) == ("disarmed", reason) and v["state"] in dw.QUIET


def test_the_permit_present_and_drill_json_disarmed_self_disarmed(world):
    world.pulse(state="disarmed", reason="operator")
    assert said(world.judge(AT + timedelta(hours=5))) == ("self_disarmed", "operator", True)


def test_never_armed_says_nothing(world):
    world.seen(permit=False)
    world.no_pulse()
    v = world.judge(AT + timedelta(hours=5))
    assert (v["state"], v["code"], v["drill"]) == ("disarmed", "never armed", DRILL)


@pytest.mark.parametrize("which", ["permit", "pulse"])
def test_a_fingerprint_imladris_does_not_have_rearm_expected(world, which):
    if which == "permit":
        world.seen(permit_doc={"drill": DRILL, "sha256": OTHER_SHA, "armed_at": ARMED_AT.isoformat()})
    else:
        world.pulse(sha=OTHER_SHA)
    assert said(world.judge(AT + timedelta(hours=5))) == ("rearm_expected", "fingerprint", False)


def test_the_hour_and_the_fingerprint_are_this_hosts_copy_never_the_instances(world, tmp_path, monkeypatch):
    """The copy of this image (``load_file(…, SHIPPED)``), never ``drill.find``: a drill of the console
    named as the shipped one, whose fingerprint the channel announces, never stands in for it."""
    other = tmp_path / "instance"
    other.mkdir()
    body = (dr.shipped_dir() / f"{DRILL}.yaml").read_text().replace("19:00", "07:00")
    (other / f"{DRILL}.yaml").write_text(body)
    monkeypatch.setenv(dr.DRILLS_ENV, str(other))
    fake = dr.fingerprint(body.encode())
    world.seen(permit_doc={"drill": DRILL, "sha256": fake, "armed_at": ARMED_AT.isoformat()})
    world.pulse(sha=fake)
    v = world.judge(AT + timedelta(hours=5))
    assert said(v) == ("rearm_expected", "fingerprint", False)
    assert v["occurrence"] == AT.isoformat()            # 19:00, the shipped copy's hour


def test_a_release_that_changes_the_drill_rearm_expected_not_not_run(world, tmp_path):
    changed = tmp_path / "drills"
    changed.mkdir()
    (changed / f"{DRILL}.yaml").write_text((dr.shipped_dir() / f"{DRILL}.yaml").read_text()
                                           .replace('at: "19:00"', 'at: "20:00"'))
    v = world.judge(AT + timedelta(hours=5), drills_dir=changed)
    assert said(v) == ("rearm_expected", "fingerprint", False)


def test_drill_changed_on_orodruin_the_occurrence_refused_without_mention_then_rearm(world):
    world.pulse(state="disarmed", reason="drill_changed", last=World.last("refused", "drill_changed"))
    assert said(world.judge(AT + timedelta(hours=5))) == ("refused", "drill_changed", False)
    world.pulse(state="disarmed", reason="drill_changed")
    assert said(world.judge(AT + timedelta(hours=5))) == ("rearm_expected", "drill_changed", False)


def test_armed_after_the_occurrence_waits_for_the_next(world):
    world.seen(permit_doc={"drill": DRILL, "sha256": SHA, "armed_at": (AT + timedelta(minutes=5)).isoformat()})
    world.pulse(at=AT + timedelta(minutes=6))
    assert world.judge(AT + timedelta(hours=5))["state"] == "waiting"


def test_the_arming_s_pulse_not_read_yet_waits_then_unknown(world):
    world.seen(permit_doc={"drill": DRILL, "sha256": SHA, "armed_at": (AT + timedelta(hours=4)).isoformat()})
    world.pulse(state="disarmed", reason="operator", at=AT - timedelta(days=1))   # before this arming
    assert world.judge(AT + timedelta(hours=4, minutes=1))["state"] == "waiting"
    assert said(world.judge(AT + timedelta(hours=6))) == ("unknown", "no_pulse", False)


# ── An Imladris older than Orodruin: unknown, said (§4.1) ─────────────────────────────────────

def test_a_status_this_imladris_refused_is_unknown_said(world):
    world.played(status=False)
    assert world.judge(AT + timedelta(hours=1))["state"] == "waiting"
    v = world.judge()
    assert said(v) == ("unknown", "status_unread", False) and "older than Orodruin" in v["said"]


def test_a_pulse_this_imladris_refused_is_unknown_said(world):
    world.seen(pulse_why="refused: the drill's pulse carries a field it never holds: more")
    v = world.judge(AT + timedelta(hours=5))
    assert said(v) == ("unknown", "pulse_unread", False) and "never holds" in v["said"]


# ── The pull: the permit judged by the listing ───────────────────────────────────────────────

URL = "https://acct.blob.core.windows.net/exercises"


class _Resp:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code, self.content, self.headers = status, body, headers or {}
        self.ok = 200 <= status < 300


def _listing(*names, modified="Tue, 17 Nov 2026 19:20:00 GMT") -> bytes:
    blobs = "".join(f"<Blob><Name>{n}</Name><Properties><Last-Modified>{modified}</Last-Modified></Properties></Blob>"
                    for n in names)
    return f"<?xml version='1.0'?><EnumerationResults><Blobs>{blobs}</Blobs><NextMarker/></EnumerationResults>".encode()


def _channel(names=(xc.DRILL_BLOB, xc.PERMIT_BLOB), *, listing_status=200, pulse=None, permit=None):
    pulse = pulse or da.pulse(state="armed", drill=DRILL, sha256=SHA, at=(AT + timedelta(minutes=20)).isoformat())
    permit = permit or {"drill": DRILL, "sha256": SHA, "armed_at": ARMED_AT.isoformat()}

    def get(url, headers=None, params=None, timeout=None):
        if params and params.get("comp") == "list":
            assert params.get("prefix") == "orodruin/drill"
            return _Resp(listing_status, _listing(*names) if listing_status == 200 else b"")
        if url.endswith(xc.DRILL_BLOB):
            return _Resp(200, json.dumps(pulse).encode())
        if url.endswith(xc.PERMIT_BLOB):
            return _Resp(200, json.dumps(permit).encode())
        return _Resp(404)
    return get


_CRED = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="t"))


def _pull(directory, get, now=AT + timedelta(hours=1)):
    return xc.pull_drill(directory, channel=URL, credential=_CRED, get=get, now=now)


@pytest.fixture
def pulled(tmp_path, monkeypatch):
    monkeypatch.setenv("EREGION_EXERCISE_CHANNEL", URL)
    d = tmp_path / "runs" / "glorfindel" / "orodruin"
    d.mkdir(parents=True)
    return d


def test_the_pull_lists_the_permit_and_keeps_the_pulse(pulled):
    seen = _pull(pulled, _channel())
    assert seen["listed"] is True and seen["permit"]["listed"] is True
    assert seen["permit"]["doc"]["sha256"] == SHA
    assert {k: seen["pulse"][k] for k in ("listed", "modified", "why")} == {
        "listed": True, "modified": "2026-11-17T19:20:00+00:00", "why": ""}
    assert da.read_pulse(seen["pulse"]["doc"])["state"] == "armed"
    assert seen["permit"]["last_listed"] == (AT + timedelta(hours=1)).isoformat()
    assert xc.read_seen(pulled) == seen
    assert sorted(p.name for p in pulled.iterdir()) == [xc.SEEN_FILE]   # one file; no copy of the permit


def test_the_permit_absent_from_the_listing_is_absent_whatever_was_seen_before(pulled):
    _pull(pulled, _channel())
    seen = _pull(pulled, _channel(names=(xc.DRILL_BLOB,)), now=AT + timedelta(hours=2))
    assert seen["listed"] is True
    assert seen["permit"] == {"listed": False, "doc": None, "why": "",
                              "last_listed": (AT + timedelta(hours=1)).isoformat()}   # when it was last there


def test_a_listing_that_fails_is_unread_never_absent_and_its_first_moment_kept(pulled):
    _pull(pulled, _channel())
    first = _pull(pulled, _channel(listing_status=503), now=AT + timedelta(hours=2))
    assert first["listed"] is False and "503" in first["why"]
    assert first["unread_since"] == (AT + timedelta(hours=2)).isoformat()
    again = _pull(pulled, _channel(listing_status=503), now=AT + timedelta(days=3))
    assert again["unread_since"] == (AT + timedelta(hours=2)).isoformat()
    back = _pull(pulled, _channel(), now=AT + timedelta(days=4))
    assert back["listed"] is True and back["unread_since"] == ""


def test_a_permit_or_a_pulse_refused_by_its_reader_is_said(pulled):
    _pull(pulled, _channel())
    bad = {**da.pulse(state="armed", drill=DRILL, sha256=SHA, at=AT.isoformat()), "more": 1}
    seen = _pull(pulled, _channel(pulse=bad, permit={"drill": DRILL}))
    assert seen["permit"]["listed"] is True and seen["permit"]["doc"] is None and "refused" in seen["permit"]["why"]
    assert seen["pulse"]["listed"] is True and "never holds" in seen["pulse"]["why"]
    assert seen["pulse"]["doc"]["at"] == (AT + timedelta(minutes=20)).isoformat()   # the copy before stays


def test_without_a_channel_nothing_is_written(tmp_path, monkeypatch):
    monkeypatch.delenv("EREGION_EXERCISE_CHANNEL", raising=False)
    d = tmp_path / "o"
    assert xc.pull_drill(d) == {} and not d.exists()
    assert dw.judge(dw.Sources(tmp_path / "runs"))["state"] == "off"


def test_the_watch_s_thread_pulls_the_drill_before_the_campaigns(tmp_path, monkeypatch):
    from analysis import hosted_report
    monkeypatch.setenv("EREGION_EXERCISE_CHANNEL", URL)
    runs = tmp_path / "runs" / "glorfindel"
    runs.mkdir(parents=True)
    seen = hosted_report.pull_drill(runs, channel=URL, credential=_CRED, get=_channel())
    assert seen["permit"]["listed"] is True
    assert xc.read_seen(runs / "orodruin")["listed"] is True


def test_the_drills_listing_failing_is_said_once_while_it_lasts(tmp_path, monkeypatch):
    from analysis import hosted_report
    monkeypatch.setenv("EREGION_EXERCISE_CHANNEL", URL)
    runs = tmp_path / "runs" / "glorfindel"
    runs.mkdir(parents=True)
    said: list[str] = []
    for n in range(3):            # its text changes at every call (an object's address): said once
        def fails(url, headers=None, params=None, timeout=None, n=n):
            raise ConnectionError(f"timed out at 0x{n:x}")
        seen = hosted_report.pull_drill(runs, channel=URL, credential=_CRED, get=fails, say=said.append)
        assert seen["listed"] is False
    assert len(said) == 1 and said[0].startswith("the drill's blobs not listed: ConnectionError")
    hosted_report.pull_drill(runs, channel=URL, credential=_CRED, get=_channel(), say=said.append)
    hosted_report.pull_drill(runs, channel=URL, credential=_CRED, get=fails, say=said.append)
    assert len(said) == 2                                  # back after a listing that went through


# ── The second review (DRL1b, round 1): the guards it found untested, the false alerts ───────

def test_last_weeks_word_never_stands_for_this_occurrence_not_run_after_two_hours(world):
    """The pulse's ``last`` is the occurrence of a week before, the permit and the pulse agree: Orodruin
    did not run this one — ``not_run``, never the week before's result."""
    before = AT - timedelta(days=7)
    world.seen(modified=before + timedelta(minutes=20),
               permit_doc={"drill": DRILL, "sha256": SHA, "armed_at": (before - timedelta(days=3)).isoformat()})
    world.pulse(last=World.last("refused", "busy", occurrence=before), at=before + timedelta(minutes=20))
    assert world.judge(AT + timedelta(hours=1))["state"] == "waiting"
    assert said(world.judge(AT + timedelta(hours=2, minutes=1))) == ("not_run", "no_status", True)


def test_a_status_of_another_hour_is_unknown_never_a_proof(world):
    world.played()
    path = world.oro / "requests" / f"{REQ}.json"
    doc = json.loads(path.read_text())
    doc["drill"]["occurrence"] = (AT - timedelta(days=7)).isoformat()
    path.write_text(json.dumps(doc))
    assert said(world.judge()) == ("unknown", "status_drill", False)


def test_a_run_without_glorfindel_is_no_proof(world):
    world.played()
    path = world.root / "glorfindel" / f"{RUN}.json"
    doc = json.loads(path.read_text())
    doc["metrics"]["without_glorfindel"] = True
    path.write_text(json.dumps(doc))
    assert said(world.judge()) == ("unknown", "unknown", False)


def test_one_run_missed_among_two_is_missed(world):
    world.played()
    other = "20261117T190500Z-cd34"
    path = world.oro / "requests" / f"{REQ}.json"
    doc = json.loads(path.read_text())
    doc["wires"].append({"rank": 2, "state": "done", "code": "", "runs": [other], "result": "missed"})
    path.write_text(json.dumps(doc))
    report = json.loads((world.root / "glorfindel" / f"{RUN}.json").read_text())
    report["run_id"] = other
    report["metrics"].update(detection="missed", detection_latency_s=None)
    (world.root / "glorfindel" / f"{other}.json").write_text(json.dumps(report))
    assert said(world.judge()) == ("missed", "missed", True)


def test_a_permit_listed_but_refused_by_its_reader_is_unknown_said(world):
    world.seen(permit_why="refused: the permit lacks armed_at")
    v = world.judge(AT + timedelta(hours=5))
    assert said(v) == ("unknown", "permit_unread", False) and "lacks armed_at" in v["said"]


def test_the_permit_just_gone_while_drill_json_still_says_armed_is_quiet_a_while(world):
    world.seen(permit=False, last_listed=AT + timedelta(hours=4, minutes=50))
    v = world.judge(AT + timedelta(hours=5))
    assert (v["state"], v["code"]) == ("waiting", "disarming") and not dw.alerts(v)
    assert said(world.judge(AT + timedelta(hours=5, minutes=21))) == ("rearm_expected", "no_permit", False)


@pytest.mark.parametrize(("reason", "late"), [("operator", 1), ("killed", 8)])
def test_a_disarming_or_a_kill_seen_by_the_pull_says_nothing_at_any_moment(pulled, reason, late):
    """The disarming and the kill remove the permit, then write the pulse — the kill after it closed
    the windows, minutes later. Every pull between them, judged: never an alert (§4.2)."""
    root = pulled.parents[1]
    t = AT + timedelta(minutes=30)
    armed = da.pulse(state="armed", drill=DRILL, sha256=SHA, at=(AT + timedelta(minutes=20)).isoformat())
    disarmed = da.pulse(state="disarmed", reason=reason, drill=DRILL, sha256=SHA,
                        at=(t + timedelta(minutes=late)).isoformat())
    steps = [(t, _channel(pulse=armed)),                                      # armed
             (t + timedelta(seconds=30), _channel(names=(xc.DRILL_BLOB,), pulse=armed)),   # the permit removed
             (t + timedelta(minutes=late, seconds=30), _channel(names=(xc.DRILL_BLOB,), pulse=disarmed))]
    verdicts = []
    for when, get in steps:
        _pull(pulled, get, now=when)
        verdicts.append(dw.judge(dw.Sources(root, channel=True), when + timedelta(seconds=10)))
    assert [v["state"] for v in verdicts] == ["waiting", "waiting", "disarmed"]
    assert not any(dw.alerts(v) for v in verdicts)


def test_never_pulled_is_quiet_a_while_then_said_unread(tmp_path):
    root = tmp_path / "runs"
    first = dw.judge(dw.Sources(root, channel=True), AT)
    assert (first["state"], first["code"]) == ("waiting", "not_pulled")
    v = dw.judge(dw.Sources(root, channel=True, previous=first), AT + timedelta(minutes=16))
    assert said(v) == ("channel_unread", "not_pulled", False) and v["since"] == AT.isoformat()


def test_a_since_to_come_in_a_forged_store_never_holds_never_pulled_quiet(tmp_path):
    root = tmp_path / "runs"
    forged = {"state": "waiting", "code": "not_pulled", "since": (AT + timedelta(days=365)).isoformat()}
    first = dw.judge(dw.Sources(root, channel=True, previous=forged), AT)
    assert (first["state"], first["code"], first["since"]) == ("waiting", "not_pulled", AT.isoformat())
    v = dw.judge(dw.Sources(root, channel=True, previous=first), AT + timedelta(minutes=16))
    assert (v["state"], v["code"]) == ("channel_unread", "not_pulled")


def test_a_pull_that_stopped_is_unread_never_its_last_word(world):
    world.played()
    world.pulled_at = AT + timedelta(hours=1)
    v = world.judge(AT + timedelta(hours=4))
    assert said(v) == ("channel_unread", "stale", False)


def test_the_unread_said_names_the_error_never_its_text(world):
    world.seen(listed=False, why="ConnectionError: HTTPSConnectionPool(host='acct.blob.core.windows.net') "
               "HTTP 503", unread_since=AT.isoformat())
    v = world.judge(AT + timedelta(hours=1))
    assert "ConnectionError HTTP 503" in v["said"] and "acct" not in v["said"]


@pytest.mark.parametrize("code", dw.REFUSED_REPEAT)
def test_watch_and_busy_twice_in_a_row_mention(world, code):
    world.pulse(last=World.last("refused", code))
    assert said(world.judge()) == ("refused", code, False)
    world.history[(AT - timedelta(days=7)).isoformat()] = {"state": "refused", "code": "watch"}
    assert said(world.judge()) == ("refused", code, True)


def test_a_second_pass_without_change_reads_nothing_again(world, monkeypatch):
    world.played()
    assert world.judge()["state"] == "proof"
    reads = []
    real = dw.channel_reader.read_text
    monkeypatch.setattr(dw.channel_reader, "read_text",
                        lambda *a, **k: (reads.append(a) if str(a[0]).endswith("_debug.jsonl") else None) or real(*a, **k))
    assert world.judge()["state"] == "proof"
    assert reads == []                                      # the cycles not read again
    (world.root / "glorfindel" / "watch-rule-2_debug.jsonl").write_text("")
    os.utime(world.root / "glorfindel" / "watch-rule-2_debug.jsonl",
             (AT.timestamp() + 600, AT.timestamp() + 600))
    world.judge()
    assert reads                                            # a cycle file more: measured again


def test_the_cycles_read_are_those_the_console_reads(world):
    """The five fields kept of a cycle (``Sources.cycles``) give C1's ``decision_of`` what the console's
    own reading gives it (``api._slim_cycle``), line for line."""
    pytest.importorskip("fastapi")
    import eregion_console.api as api
    from eregion_console.indicators import decision_of
    world.played()
    other = {"timestamp": (AT + timedelta(minutes=4)).isoformat(), "action": "",
             "signal": {"event": "detection", "ttp": EXPERIMENT, "timestamp": (AT + timedelta(minutes=4)).isoformat(),
                        "resource_id": VM}}
    path = world.root / "glorfindel" / "watch-rule-1_debug.jsonl"
    path.write_text(path.read_text() + json.dumps(other) + "\n")
    os.utime(path, (AT.timestamp() + 600, AT.timestamp() + 600))
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    console = [c for rec in lines if (c := api._slim_cycle(rec))]
    ours = dw.Sources(world.root).cycles(AT)
    run = dw.Sources(world.root).report(RUN)
    assert decision_of(run, console) == decision_of(run, console) is not None
    assert {k: decision_of(run, ours)[k] for k in ours[0]} == {k: decision_of(run, console)[k] for k in ours[0]}
    for field in ("event", "action", "signal_at", "ttp", "resource_id"):
        assert [c[field] for c in ours] == [c[field] for c in console]


# ── The bot: its own thread, its text by chat_text, the mention §4.2 gives ───────────────────

ROLE = 4242


class _Thread:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, content=None, **kw):
        self.sent.append({"content": content, **kw})
        return MagicMock(id=len(self.sent))


def _bot(threads: dict):
    pytest.importorskip("discord")
    from glorfindel import bot
    b = bot.GlorfindelBot(channel_id=1, ping_role=ROLE)

    async def thread(channel, key, ping=True):
        assert ping is False                              # never « Incident opened »
        threads.setdefault(key, _Thread())
        return threads[key]
    b._get_or_create_thread = thread
    return b


def _store(v: dict) -> None:
    dw._STORE.parent.mkdir(parents=True, exist_ok=True)
    dw._STORE.write_text(json.dumps({"current": v, "history": {}}))


def _verdict(world, **kw) -> dict:
    world.played(detection="missed", decision=False)
    return {**world.judge(), **kw}


def test_the_bot_posts_in_the_drills_own_thread_once_mentioning_the_role(world):
    _store(_verdict(world))
    threads: dict = {}
    b = _bot(threads)
    assert asyncio.run(b._post_drill(None)) is True
    assert list(threads) == [f"drill:{DRILL}"]
    [m] = threads[f"drill:{DRILL}"].sent
    assert m["content"].startswith(f"<@&{ROLE}> ") and "manquée" in m["content"]
    assert [r.id for r in m["allowed_mentions"].roles] == [ROLE] and m["allowed_mentions"].everyone is False
    assert asyncio.run(_bot(threads)._post_drill(None)) is False      # restarted: never twice


def test_the_bot_mentions_no_one_where_the_table_does_not(world):
    _store(_verdict(world, state="rearm_expected", code="fingerprint", mention=False))
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_drill(None)) is True
    [m] = threads[f"drill:{DRILL}"].sent
    assert "<@&" not in m["content"] and not m["allowed_mentions"].roles and not m["allowed_mentions"].everyone


def test_a_quiet_verdict_is_never_posted(world):
    _store({**world.judge(AT + timedelta(hours=1)), "state": "waiting"})
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_drill(None)) is False and threads == {}


def test_the_bots_text_passes_by_chat_text(world):
    v = _verdict(world, said="see [here](https://example.invalid) @everyone **now**", code="x_y")
    text = dw.bot_message(v)
    assert "\\[here\\]\\(https://example.invalid\\)" in text and "@​everyone" in text
    assert "\\*\\*now\\*\\*" in text and "`x_y`" in text


def test_a_store_naming_no_drill_opens_no_thread(world):
    _store(_verdict(world, drill="../../a thread"))
    threads: dict = {}
    assert asyncio.run(_bot(threads)._post_drill(None)) is False and threads == {}


def test_the_thread_is_named_after_the_drill():
    pytest.importorskip("discord")
    from glorfindel import bot
    assert bot._thread_name(dw.thread_key(DRILL)) == f"drill · {DRILL}"


# ── The tile of the last proof: from the drill ───────────────────────────────────────────────

def test_a_run_of_the_drill_is_said_from_the_drill(world):
    world.played()
    assert dw.drill_of_run(world.root, RUN, REQ) == DRILL
    assert dw.drill_of_run(world.root, "another-run", REQ) == ""
    assert dw.drill_of_run(world.root, RUN, "r-20261117T190000Z-ffffff") == ""


# ── The console: « Weekly drill » and the tile ───────────────────────────────────────────────

def test_the_console_shows_the_weekly_drill_as_the_watch_judged_it(world):
    pytest.importorskip("fastapi")
    from .console_client import console
    world.played(detection="missed", decision=False)
    world.write(AT + timedelta(hours=4) - timedelta(minutes=1))
    dw.refresh(world.root, now=AT + timedelta(hours=4), channel=True)
    with console() as c:
        d = c.get("/api/dagorlad/drill").json()
    v = d["verdict"]
    assert (v["drill"], v["state"], v["mention"], v["occurrence"]) == (DRILL, "missed", True, AT.isoformat())
    assert d["alerts"] is True
    assert d["history"] == [{"occurrence": AT.isoformat(), "state": "missed", "code": "missed"}]


def test_the_console_without_a_verdict_says_not_judged_yet():
    pytest.importorskip("fastapi")
    from .console_client import console
    with console() as c:
        assert c.get("/api/dagorlad/drill").json() == {"verdict": None, "alerts": False, "history": []}


def test_the_tile_of_the_last_proof_says_the_drill(world, monkeypatch):
    pytest.importorskip("fastapi")
    import eregion_console.api as api
    world.played()
    monkeypatch.setattr(api, "_RUNS", world.root)
    monkeypatch.setattr(api, "_run_reports", lambda: {RUN: world.root / "glorfindel" / f"{RUN}.json"})
    assert api._drill_of_proof({"run_id": RUN}) == DRILL
    assert api._drill_of_proof({"run_id": "other"}) == ""
    assert api._drill_of_proof(None) == ""
