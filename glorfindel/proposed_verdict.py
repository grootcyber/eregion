"""VP1 (#615; docs/design/drill-banc.md §8.2): a verdict proposed on the exercise card of the detection
the drill of the week expected — the right rule, on its target, in time — that the operator confirms
in one click (the console, the bot). A verdict proposed is never a verdict given: its own field on the
card (``glorfindel.escalations.PROPOSED_FIELD``), never counted by the report nor the indicators.

**What it reads, on Imladris — never what the channel says of itself:**

- the drill: **its copy in this host's image** (``drills/<name>.yaml``, ``drill.loaded(…, SHIPPED)``),
  never ``drill.find``, which prefers the instance's layer — a drill of the console named as the
  shipped one would take its place; its name and fingerprint must be those Orodruin's status of the
  request announces (its ``drill``) — two versions of the drill (Orodruin and Imladris apart), nothing
  is proposed;
- the rule expected: ``expectations/<name>.yaml`` of this host's image, the expectation of the
  wire's rank in the drill and of the same experiment;
- the delay: its ``within_s``, after the wire's T0 — the attack time of the run's report;
- the target: the VM of the wire, the window's (its one target) **and** the report's
  (``metrics.resource_id``), the two equal;
- the window: its start, its end, and its grace (``exercise.GRACE_AFTER_S``): the window believed by
  the watch (``exercise.load_windows``);
- the link card ↔ run: the card is an exercise's, its ``exercise_run`` is the run; the run is a wire
  of the request (``metrics.request``, the window's ``request``, and the run among the wire's runs in
  Orodruin's status).

**It proposes only when everything agrees, on one card per wire**: the card's rule is the one
expected, its VM is the target, its time falls in ``[T0, T0 + within_s]`` and inside the window, and
it is the first card of that wire and that rule. Otherwise no proposal, and why is said on the card
(``PROPOSED_WHY``): a code and a sentence, never an identifier.

**On the detection, never on the decision**: the drill declares no decision expected — the action,
and whether it was proportionate, stay the operator's to judge; the proposal says what it compared.

**Glorfindel stays blind**: the decision never reads a card, nor any of this
(``_build_user_message``; tests/unit/test_dagorlad_blind.py). The watch runs the pass every minute
(``refresh``, its housekeeping): a pure computation over the files of this host, no Azure, no model.
Held card by card (VP1b): a card it cannot assess is skipped and said once, the others still proposed;
a card whose time carries no time zone is never proposed — its zone is never guessed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eregion_core import drill as dr
from eregion_core import exercise, run_report, runs_layout
from eregion_core import exercise_request as xr
from eregion_core import expectations as ex
from eregion_core.channel_reader import read_json
from glorfindel import escalations as esc

# The verdict proposed: the detection was the one the drill expected. Whether the action was
# proportionate is not compared — the operator confirms only if it was.
PROPOSED = "right"
# The cards a pass looks at: TO JUDGE's week. An older card is not looked at again.
HORIZON = timedelta(days=7)


@dataclass(frozen=True)
class Outcome:
    """A proposal (the card is the expected detection), or why not: ``code`` and ``said``."""
    proposal: dict | None = None
    code: str = ""
    said: str = ""


def _no(code: str, said: str) -> Outcome:
    return Outcome(None, code, said)


def _vm(value) -> str:
    return str(value or "").rstrip("/").lower()


def _when(value) -> datetime | None:
    at = run_report.epoch(value)
    return datetime.fromtimestamp(at, timezone.utc) if at is not None else None


@dataclass
class Sources:
    """What a pass reads on this host, each read once: the run reports (``runs_layout.run_reports``),
    Orodruin's statuses pulled by the watch (``<root>/glorfindel/orodruin/requests/``), the windows
    the watch believes, the drill's copy and its expectations in this host's image."""
    root: Path = Path("runs")
    windows: list[dict] = field(default_factory=list)
    drills_dir: Path | None = None
    expectations_dir: Path | None = None
    _reports: dict | None = None
    _statuses: dict = field(default_factory=dict)
    _drills: dict = field(default_factory=dict)
    _expected: dict = field(default_factory=dict)

    def report(self, run_id: str) -> tuple[dict | None, str]:
        """The run's unified view (``run_report.read_run``), or None and why."""
        if self._reports is None:
            self._reports = runs_layout.run_reports(self.root)
        path = self._reports.get(run_id)
        if path is None:
            return None, "no_report"
        runs = run_report.read_reports({run_id: path})
        if not runs:
            return None, "report_unread"
        return runs[0], ""

    def status(self, request_id: str) -> tuple[dict | None, str]:
        """Orodruin's status of the request, read by its one reader — or None and why."""
        if request_id not in self._statuses:
            path = runs_layout.dir_of(runs_layout.GLORFINDEL, self.root) / "orodruin" / "requests" / f"{request_id}.json"
            if not os.path.lexists(path):
                self._statuses[request_id] = (None, "no_status")
            else:
                try:
                    doc = xr.read_status(read_json(path))
                    self._statuses[request_id] = ((doc, "") if doc.get("request") == request_id
                                                  else (None, "status_unread"))
                except (OSError, ValueError, RecursionError, xr.RequestRefused):
                    self._statuses[request_id] = (None, "status_unread")
        return self._statuses[request_id]

    def drill(self, name: str) -> tuple[dr.Drill | None, str, str]:
        """The drill's copy in this host's image (``drills/<name>.yaml``, the shipped layer) and its
        fingerprint — never ``drill.find``: the instance's layer never stands in for it."""
        if name not in self._drills:
            path = Path(self.drills_dir or dr.shipped_dir()) / f"{name}.yaml"
            try:
                d, sha = dr.loaded(path, dr.SHIPPED)
                self._drills[name] = (d, sha, "")
            except dr.DrillRefused:
                self._drills[name] = (None, "", "drill_unread")
        return self._drills[name]

    def expectations(self, name: str) -> ex.Expectations | None:
        """The drill's expectations in this host's image (``expectations/<name>.yaml``)."""
        if name not in self._expected:
            try:
                self._expected[name] = ex.load_file(Path(self.expectations_dir or ex.shipped_dir()) / f"{name}.yaml")
            except ex.ExpectationsRefused:
                self._expected[name] = None
        return self._expected[name]


_SAID = {
    "no_report": "its run's report has not reached this host",
    "report_unread": "its run's report is unreadable here",
    "not_technique": "its run is no technique's",
    "no_request": "its run is no wire of a request",
    "no_status": "Orodruin's status of its request has not reached this host",
    "status_unread": "Orodruin's status of its request is unreadable here",
    "not_drill": "its request is no drill's of the week",
    "not_a_wire": "its run is not one wire's of its request's status",
    "drill_unread": "the drill is not readable in this host's image",
    "fingerprint": "the drill Orodruin played is not this host's copy (two versions of the drill)",
    "expectations_unread": "the drill's expectations are not readable in this host's image",
    "layout": "the request's wires do not lay out the drill's",
    "experiment": "its run is not the experiment the drill expects at its rank",
    "no_window": "its run's exercise window is not believed here",
    "link": "the window, the run's report and the request do not name the same request",
    "target": "the window and the run's report do not name the same single target",
    "t0": "its run's T0 falls outside its window",
    "vm": "the card is on another VM than the wire's target",
    "rule": "the card's rule is not the rule the drill expects",
    "early": "the card is dated before its run's T0",
    "late": "the card falls after T0 + the delay the drill expects",
    "window": "the card falls outside its window and its grace",
    "second": "a card of this wire and this rule came first: only the first is proposed",
    "no_time": "the card or its run has no readable time",
    "no_tz": "the card's time carries no time zone: it is never guessed",
    "unordered": "a card of this wire and this rule has a time without a time zone: which came first is never guessed",
}


def _said(code: str) -> Outcome:
    return _no(code, _SAID[code])


def assess(card: dict, cards: list[dict], src: Sources) -> Outcome:
    """Does ``card`` carry the detection the drill expected? A proposal when everything agrees
    (docs/design/drill-banc.md §8.2), else why not. ``cards``: every card of the store, in its order —
    the first card of the wire is found among them."""
    if not esc.proposable(card):
        return _no("not_proposable", "no exercise card waiting for a verdict")
    run_id = str(card["exercise_run"])
    run, why = src.report(run_id)
    if run is None:
        return _said(why)
    if run["kind"] != "technique":
        return _said("not_technique")
    request_id = run["request"]
    if not xr.valid_id(request_id):
        return _said("no_request")
    status, why = src.status(request_id)
    if status is None:
        return _said(why)
    announced = status.get("drill")
    if not isinstance(announced, dict):
        return _said("not_drill")
    wires = [w for w in status["wires"] if run_id in w["runs"]]
    if len(wires) != 1:
        return _said("not_a_wire")
    wire = wires[0]
    name = announced["name"]
    drill, sha, why = src.drill(name)
    if drill is None:
        return _said(why)
    if sha != announced["sha256"]:
        return _said("fingerprint")
    expected = src.expectations(name)
    if expected is None or expected.drill != name or len(expected.wires) != len(drill.wires):
        return _said("expectations_unread")
    # The wires of the drill's request, as Orodruin's timer lays them (scheduled_drill._place): each
    # wire of the drill, on each target armed, in that order.
    n, m = len(drill.wires), len(status["wires"])
    if m == 0 or m % n:
        return _said("layout")
    rank = (wire["rank"] - 1) // (m // n) + 1
    exp = expected.wires[rank - 1]
    if not (exp.rank == rank and exp.experiment == drill.wires[rank - 1].experiment == run["experiment"]):
        return _said("experiment")
    windows = [w for w in src.windows if w.get("run_id") == run_id]
    if len(windows) != 1:
        return _said("no_window")
    window = windows[0]
    if str(window.get("experiment") or "").split(" ")[0] != exp.experiment:
        return _said("experiment")
    if window.get("request") != request_id:
        return _said("link")
    targets = [_vm(t) for t in window.get("targets") or []]
    target = _vm(run["resource_id"])
    if not target or targets != [target]:
        return _said("target")
    start, last = _when(window.get("start")), exercise.last_moment(window)
    t0, at = _when(run["at"]), esc._when(card)
    if start is None or last is None or t0 is None or at is None:
        return _said("no_time")
    if at.tzinfo is None:                  # VP1b: never compared to an aware time, never guessed
        return _said("no_tz")
    if not start <= t0 <= last:
        return _said("t0")
    if _vm(card.get("resource_id")) != target:
        return _said("vm")
    if esc.rule_of(card) != exp.rule:
        return _said("rule")
    if at < t0:
        return _said("early")
    if at > t0 + timedelta(seconds=exp.within_s):
        return _said("late")
    if not start <= at <= last:
        return _said("window")
    first, unordered = _first(cards, set(wire["runs"]), exp.rule)
    if unordered:
        return _said("unordered")
    if first is None or first.get("id") != card.get("id"):
        return _said("second")
    return Outcome({
        "verdict": PROPOSED, "on": "detection", "at": datetime.now(timezone.utc).isoformat(),
        "drill": name, "sha256": sha, "request": request_id, "rank": wire["rank"], "run": run_id,
        "rule": exp.rule, "within_s": exp.within_s, "after_s": int((at - t0).total_seconds()),
    })


def _first(cards: list[dict], runs: set[str], rule: str) -> tuple[dict | None, bool]:
    """The first decision card of the wire's runs and of the rule expected, by its time then its
    place in the store — whatever became of it since (judged, refused, on another VM). And whether
    one of them has a time without a time zone (VP1b): then which came first is not known, and never
    guessed — ``(None, True)``."""
    found = [(t, i, c) for i, c in enumerate(cards)
             if esc.is_decision(c) and c.get("source") == "exercise" and c.get("exercise_run") in runs
             and esc.rule_of(c) == rule and (t := esc._when(c)) is not None]
    if any(t.tzinfo is None for t, _, _ in found):
        return None, True
    return (min(found, key=lambda f: (f[0], f[1]))[2] if found else None), False


# VP1b (#917): the cards a pass could not assess — an error of its own, never the pass's — said once
# each, by their id, for the life of the watch.
_SKIPPED: set[str] = set()


def _recent(card: dict, now: datetime) -> bool:
    """A card of TO JUDGE's week — or one whose time carries no time zone: its age is not known, and
    never guessed; ``assess`` says why it is not proposed (``no_tz``)."""
    at = esc._when(card)
    return at is not None and (at.tzinfo is None or now - at <= HORIZON)


def refresh(root: str | Path = "runs", *, windows: list[dict] | None = None, drills_dir: Path | None = None,
            expectations_dir: Path | None = None, now: datetime | None = None, say=None) -> int:
    """The watch's pass (every minute): each exercise card of the week still waiting for a verdict,
    without a proposal made or refused, assessed — its proposal, or why not, written on it
    (``escalations.note_proposals``). ``windows``: the windows the watch believes
    (``exercise.load_windows``, read only when a card is to assess). Returns the cards changed.

    VP1b (#917): the pass is held card by card — a card whose assessment fails is skipped, said once
    (``say``, the watch's channel; its id and the error's kind, never the error's text), and the
    others are still proposed: one faulty card never stops the pass, minute after minute."""
    now = now or datetime.now(timezone.utc)
    cards = esc.all_escalations()
    todo = [c for c in cards if esc.proposable(c) and _recent(c, now)]
    if not todo:
        return 0
    if windows is None:
        windows = exercise.load_windows(pull=False)
    src = Sources(Path(root), windows, drills_dir, expectations_dir)
    results = {}
    for c in todo:
        cid = str(c["id"])
        try:
            o = assess(c, cards, src)
        except Exception as exc:          # the card skipped, the pass goes on (VP1b)
            if cid not in _SKIPPED:
                _SKIPPED.add(cid)
                if say is not None:
                    say(f"card {cid[:8]} skipped by the proposed-verdict pass ({type(exc).__name__}): "
                        "nothing is proposed on it")
            continue
        results[cid] = {"proposed": o.proposal} if o.proposal else {"why": {"code": o.code, "said": o.said}}
    return esc.note_proposals(results)
