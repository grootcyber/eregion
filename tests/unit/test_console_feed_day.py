"""CON-D (#735): the console's live feed says the day of a line that is not today's, in UTC, and
orders its lines by their full moment, the latest on top — never by the time of day alone, nor by
the text of the timestamp. Around midnight UTC: a line of yesterday at 23:59 comes before one of
today at 00:00, and says « yesterday ». M4820–M4823 (scripts/mutants/CON-D.py)."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from eregion_core import runs_layout

pytest.importorskip("fastapi")

_JS = Path(__file__).resolve().parents[2] / "eregion_console" / "static" / "glorfindel.js"


def _api():
    import eregion_console.api as api
    return api


def _runs(tmp_path, monkeypatch) -> Path:
    api = _api()
    runs = tmp_path / "runs"
    for w in runs_layout.WRITERS:
        (runs / w).mkdir(parents=True)
    monkeypatch.setattr(api, "_RUNS", runs)
    return runs


def _cycle(ts: str, action: str) -> str:
    return json.dumps({"timestamp": ts, "action": action,
                       "signal": {"ttp": "T1486", "resource_id": "/x/vm-a"}, "outcome": {"verified": True}})


def _signal(ts: str, event: str) -> str:
    return json.dumps({"timestamp": ts, "event": event, "ttp": "T1110.001", "resource_id": "/x/vm-a"})


# ── the server: each line's moment, in UTC ────────────────────────────────────────────────

@pytest.mark.parametrize("ts, day, time", [
    ("2026-11-11T23:59:59.999999+00:00", "2026-11-11", "23:59:59"),
    ("2026-11-12T00:00:00+00:00", "2026-11-12", "00:00:00"),
    # an offset: 01:30 at +02:00 is 23:30 of the day before, in UTC
    ("2026-11-12T01:30:00+02:00", "2026-11-11", "23:30:00"),
    ("2026-11-11T22:30:00-02:00", "2026-11-12", "00:30:00"),
    ("2026-11-12T00:00:05Z", "2026-11-12", "00:00:05"),
    # a time with no offset is read as UTC, as every writer writes it
    ("2026-11-12T00:00:05", "2026-11-12", "00:00:05"),
    # a year below 1000 keeps its four digits (strftime's %Y does not, under glibc: review 1)
    ("0999-03-04T05:06:07.5+00:00", "0999-03-04", "05:06:07"),
])
def test_a_lines_day_and_time_are_read_in_utc_around_midnight(ts, day, time):
    when = _api()._feed_when(ts)
    assert (when["day"], when["time"]) == (day, time)
    utc = datetime.strptime(f"{day} {time}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    assert math.floor(when["at"]) == utc.timestamp()     # the second of the line, before 1970 too


@pytest.mark.parametrize("ts", ["", "   ", "yesterday", "16:15:45", None, 1731340545, "0001-01-01T00:00:00+01:00"])
def test_a_timestamp_that_does_not_read_gives_no_day_and_goes_to_the_bottom(ts):
    api = _api()
    assert api._feed_when(ts) == {"at": None, "day": "", "time": ""}
    assert api._feed_order({"at": None}) == float("-inf")


def test_each_line_of_the_feed_carries_its_moment():
    api = _api()
    sig = api._parse(json.loads(_signal("2026-11-11T21:05:00+00:00", "detection")), "signal")
    act = api._parse(json.loads(_cycle("2026-11-12T00:00:02+00:00", "snapshot")), "action")
    assert (sig["day"], sig["time"], sig["timestamp"]) == ("2026-11-11", "21:05:00", "2026-11-11T21:05:00+00:00")
    assert (act["day"], act["time"]) == ("2026-11-12", "00:00:02")
    assert act["at"] - sig["at"] == 2 * 3600 + 55 * 60 + 2


# ── the server: the order, by the full moment ────────────────────────────────────────────

def test_the_history_is_ordered_by_the_full_moment_around_midnight_never_by_the_time_of_day(tmp_path, monkeypatch):
    """M4820: yesterday's 21:05, 23:00 (written at +02:00), 23:59:58, then today's 00:00:02 and
    15:54 — in that order, whatever file holds each line. By the time of day, today's 00:00:02
    would come first; by the text of the timestamp, the line at +02:00 after 23:59:58."""
    runs = _runs(tmp_path, monkeypatch)
    (runs / "annatar" / "r1_signals.jsonl").write_text(
        _signal("2026-11-12T15:54:00+00:00", "attack_started") + "\n"
        + _signal("2026-11-11T21:05:00+00:00", "detection") + "\n")
    (runs / "glorfindel" / "watch-x_debug.jsonl").write_text(
        _cycle("2026-11-12T00:00:02+00:00", "isolate_vm") + "\n"
        + _cycle("2026-11-12T01:00:00+02:00", "block_suspicious_ip") + "\n")
    (runs / "console" / "manual_actions.jsonl").write_text(_cycle("2026-11-11T23:59:58+00:00", "snapshot") + "\n")
    got = _api()._load_recent(40)
    assert [(e["day"], e["time"]) for e in got] == [
        ("2026-11-11", "21:05:00"), ("2026-11-11", "23:00:00"), ("2026-11-11", "23:59:58"),
        ("2026-11-12", "00:00:02"), ("2026-11-12", "15:54:00")]
    # The last n are the latest by their moment.
    assert [e["time"] for e in _api()._load_recent(2)] == ["00:00:02", "15:54:00"]


def test_a_line_whose_moment_does_not_read_is_the_oldest(tmp_path, monkeypatch):
    runs = _runs(tmp_path, monkeypatch)
    (runs / "glorfindel" / "watch-x_debug.jsonl").write_text(
        _cycle("2026-11-12T00:00:02+00:00", "isolate_vm") + "\n" + _cycle("not a time", "snapshot") + "\n")
    got = _api()._load_recent(40)
    assert [e["action"] for e in got] == ["snapshot", "isolate_vm"]
    assert got[0]["day"] == "" and got[0]["at"] is None


def test_a_turn_of_the_live_feed_is_ordered_by_the_moment_whatever_the_file(tmp_path, monkeypatch):
    """M4821: a turn of the live feed reads Annatar's file before the watch's; the watch's line of
    yesterday at 23:59 still comes before Annatar's of today at 00:00 — the page puts each in its
    place, the latest on top."""
    runs = _runs(tmp_path, monkeypatch)
    (runs / "annatar" / "r1_signals.jsonl").write_text(_signal("2026-11-12T00:00:01+00:00", "attack_started") + "\n")
    (runs / "glorfindel" / "watch-x_debug.jsonl").write_text(_cycle("2026-11-11T23:59:59+00:00", "snapshot") + "\n")
    got = _api()._feed_new({})
    assert [(e["type"], e["day"]) for e in got] == [("action", "2026-11-11"), ("signal", "2026-11-12")]


# ── the page: the day said, the place by the moment (read in its text: no browser in the suite) ──

def _body(js: str, head: str) -> str:
    return js.split(head, 1)[1].split("\n}\n", 1)[0]


def test_the_page_says_yesterday_or_the_date_of_a_line_that_is_not_todays():
    """M4822: a line of today says its time alone; of yesterday, « yesterday »; before, its date
    (10/11), and its year when it is not this one — compared to the page's own day, in UTC."""
    js = _JS.read_text()
    when = _body(js, "function _feedWhen(entry, now) {")
    assert "const today = new Date(now).toISOString().slice(0, 10);" in when
    assert "const yesterday = new Date(now - _FEED_DAY_MS).toISOString().slice(0, 10);" in when
    assert "const _FEED_DAY_MS = 86400000;" in js
    assert "if (day === today) return time + ' UTC';" in when
    assert "if (day === yesterday) return 'yesterday ' + time;" in when
    assert "const year = day.slice(0, 4) === today.slice(0, 4) ? '' : '/' + day.slice(0, 4);" in when
    assert "return day.slice(8, 10) + '/' + day.slice(5, 7) + year + ' ' + time;" in when
    assert when.index("if (!day) return '';") < when.index("if (day === today)")
    entry = _body(js, "function appendFeedEntry(entry) {")
    assert "const ts = _feedWhen(entry, Date.now());" in entry
    assert "fmtTime(" not in entry
    # The time written through _attr, the full moment on hover.
    assert entry.count('<span class="feed-ts" title="${_attr(full)}">${_attr(ts)}</span>') == 2


def test_the_page_says_the_day_again_past_midnight():
    js = _JS.read_text()
    relabel = _body(js, "function _feedRelabel() {")
    assert "if (day === _feedDay) return;" in relabel
    assert "if (ts && row._when) ts.textContent = _feedWhen(row._when, now);" in relabel
    assert "setInterval(_feedRelabel, 60000);" in js


def test_the_page_puts_each_line_in_its_place_by_its_moment_the_latest_on_top():
    """M4823: each line goes above the first one not newer than it — by `at`, the full moment;
    never on top by its arrival alone, never at the bottom."""
    js = _JS.read_text()
    place = _body(js, "function _feedPlace(list, el, entry) {")
    assert "el._at = entry.at != null && Number.isFinite(at) ? at : -Infinity;" in place
    assert ("    if (row._at <= el._at) { list.insertBefore(el, row); return list.firstElementChild === el; }\n"
            in place)
    assert place.rstrip().endswith("list.appendChild(el);\n  return list.firstElementChild === el;")
    entry = _body(js, "function appendFeedEntry(entry) {")
    assert "const onTop = _feedPlace(list, el, entry);" in entry
    assert "list.appendChild(el)" not in entry
    assert "_autoScroll = this.scrollTop <= 40;" in js


def test_the_page_scrolls_back_to_the_top_only_for_a_line_put_on_top():
    """Review 1: a late line placed further down never moves the operator's reading; a line put on
    top keeps the head in sight while the operator reads it. No harness runs the page's script in the
    suite: read in its text (the behaviour was run once in a headless Chromium, out of the suite)."""
    entry = _body(_JS.read_text(), "function appendFeedEntry(entry) {")
    assert "  if (_autoScroll && onTop) {\n    list.scrollTop = 0;\n  }" in entry
    assert entry.count("scrollTop") == 1 and "scrollHeight" not in entry
