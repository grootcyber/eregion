"""DRL1b (#613; docs/design/drill-banc.md §4.2): the drill of the week, judged on Imladris — each
occurrence's verdict, by the code, never by the model; the absence alarm; what the bot says of it and
what the console shows (« Weekly drill »).

**What it reads, on Imladris — never what the channel says of itself alone:**

- **the drill**: its copy in this host's image (``drills/<name>.yaml``, ``drill.loaded(…, SHIPPED)``),
  never ``drill.find``, which prefers the instance's layer. The planned hour of each occurrence comes
  from this copy, and so does the fingerprint the channel must announce;
- **the permit**: by **the channel's listing at the last pull** (``exercise_channel.pull_drill``,
  ``runs/glorfindel/orodruin/drill-seen.json``) — there or not, and what it said then; never a copy
  kept from an earlier pull, and never what ``drill.json`` says;
- **the pulse** (``drill.json``): its last copy that read, by its one reader, and when the channel
  last wrote it (its ``Last-Modified``, Azure's clock) — in the same file as the permit, written whole
  by one pull: never half of one pull with half of another;
- **the occurrence**: Orodruin's status of its request (``runs/glorfindel/orodruin/requests/<id>.json``)
  and the report of each of its runs, the proof as C1 counts it (detected, and the watch's decision
  attached: ``eregion_console.indicators.decision_of``, over the watch's own cycles).

**The states** (§4.2): ``proof``, ``missed``, ``unknown``, ``refused``, ``skipped``, ``stopped``,
``not_run``, ``rearm_expected``, ``self_disarmed``, ``channel_unread`` — each with its alert and its
mention (``mention``). And the quiet ones, which say nothing to anyone: ``disarmed`` (never armed,
disarmed by the operator, killed), ``waiting`` (armed, the occurrence not due or not concluded yet),
``off`` (no exercise channel on this host).

**The absence alarm** (``not_run``) is armed only when **everything** agrees: the last pull listed the
channel; the permit is in that listing; ``drill.json`` says ``armed``; the permit's fingerprint and the
pulse's are those of this host's copy. The listing unread: « channel unread », and neither ``not_run``
nor ``rearm_expected``. A fingerprint this host does not have, or ``armed`` with no permit listed:
« re-arm expected ». A drill never armed, disarmed by the operator or killed: nothing.

**Glorfindel stays blind**: nothing of this reaches the decision (``_build_user_message``;
tests/unit/test_dagorlad_blind.py). The watch judges every minute (``refresh``, its housekeeping): a
pure computation over the files of this host — no Azure, no model — written to its store
(``~/.glorfindel/drill_verdicts.json``), which the bot and the console read.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eregion_core import channel_reader, run_report, runs_layout
from eregion_core import drill as dr
from eregion_core import exercise_channel as xc
from eregion_core import exercise_request as xr

# The states of §4.2, and the quiet ones (no alert, no line).
STATES = ("proof", "missed", "unknown", "refused", "skipped", "stopped", "not_run",
          "rearm_expected", "self_disarmed", "channel_unread")
QUIET = ("disarmed", "waiting", "off")
# The states an occurrence ends in, kept by occurrence (``history``): « two unknown in a row ».
OCCURRENCE_STATES = ("proof", "missed", "unknown", "refused", "skipped", "stopped", "not_run")
# A refusal said without a mention (§4.2): expected after a release, a kill, a permit expired. The two
# the table names neither way (the watch's heartbeat, the lock held): without one the first time, with
# one when the occurrence before was refused by one of them too — the more careful reading, to be
# confirmed by Jonathan (docs/design/drill-banc.md §13). Every other code, those §4.2 names with a
# mention and any other (not_eligible, over_cap, the contract's), with one.
REFUSED_QUIET = ("drill_changed", "no_permit")
REFUSED_REPEAT = ("watch", "busy")
REFUSED_MENTION = ("passive", "not_placed", "not_bench", "off_schedule", "too_soon", "permit_mismatch")
# No status for the occurrence this long after its hour: ``not_run``.
NOT_RUN_AFTER_S = 2 * 3600
# ``drill.json`` older than this: « Orodruin silent », ``not_run``.
SILENT_AFTER_S = 8 * 86400
# The channel unread this long in a row: ``channel_unread`` with a mention (it hides « Orodruin silent »).
UNREAD_MENTION_S = 8 * 86400
# A played occurrence not concluded this long after its hour: ``unknown``.
SETTLE_S = 3 * 3600
# The permit there, its pulse not read yet (the arming writes the permit, then the pulse): this long
# without a word, then ``unknown``.
ARMING_GRACE_S = 3600
# The permit gone from the listing, the pulse still armed: the disarming and the kill remove the permit
# first and write the pulse after (the kill, after it closed the windows): this long quiet, then
# « re-arm expected ».
DISARM_GRACE_S = 30 * 60
# The last pull this old, or none at all with a channel configured: the pull no longer says anything
# (its thread stopped, its file never written) — ``channel_unread``, never a quiet state without end.
PULL_STALE_S = 15 * 60
HISTORY = 12

_STORE = Path.home() / ".glorfindel" / "drill_verdicts.json"


def _when(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        return None
    return at.astimezone(timezone.utc) if at.tzinfo else None


def mention(state: str, code: str = "", *, previous: str = "", previous_code: str = "",
            unread_s: float = 0.0) -> bool:
    """Whether the alert of this state mentions the role (§4.2) — ``previous`` and ``previous_code``:
    the state and code of the occurrence before (``unknown``, ``watch``, ``busy`` twice in a row);
    ``unread_s``: how long the channel is unread."""
    if state in ("missed", "not_run", "self_disarmed"):
        return True
    if state == "unknown":
        return previous == "unknown"
    if state == "refused":
        if code in REFUSED_REPEAT:
            return previous == "refused" and previous_code in REFUSED_REPEAT
        return code not in REFUSED_QUIET
    if state == "channel_unread":
        return unread_s >= UNREAD_MENTION_S
    return False


# ── What a pass reads on this host ──────────────────────────────────────────────────────────

@dataclass
class Sources:
    """What a pass reads, each once: what the last pull saw (``drill-seen.json``), the pulse kept, the
    drill's copy in this image, Orodruin's statuses, the run reports, the watch's cycles."""
    root: Path = Path("runs")
    drills_dir: Path | None = None
    channel: bool | None = None
    history: dict = field(default_factory=dict)
    previous: dict = field(default_factory=dict)    # the verdict of the pass before (the store's)
    _cycles: list | None = None
    _reports: dict | None = None
    _seen: dict | None = None

    @property
    def orodruin(self) -> Path:
        return runs_layout.dir_of(runs_layout.GLORFINDEL, self.root) / xc.ORODRUIN

    def configured(self) -> bool:
        return bool(xc.channel_url()) if self.channel is None else self.channel

    def seen(self) -> dict | None:
        """What the last pull saw — one file, read once a pass: the permit and the pulse of one pull."""
        if self._seen is None:
            self._seen = xc.read_seen(self.orodruin) or {}
        return self._seen or None

    def pulse(self) -> dict | None:
        """The pulse's last copy that read, as the last pull kept it — None when there is none."""
        doc = ((self.seen() or {}).get("pulse") or {}).get("doc")
        return doc if isinstance(doc, dict) else None

    def copy(self, name: str) -> tuple[dr.Drill | None, str]:
        """The drill's copy in this host's image, the shipped layer — never ``drill.find``."""
        if not dr.valid_name(name):
            return None, ""
        try:
            d, sha = dr.loaded(Path(self.drills_dir or dr.shipped_dir()) / f"{name}.yaml", dr.SHIPPED)
        except dr.DrillRefused:
            return None, ""
        return (d, sha) if d.schedule is not None else (None, "")

    def scheduled(self) -> list[str]:
        """The drills of this image that carry ``schedule``, by name."""
        out = []
        for p in sorted(Path(self.drills_dir or dr.shipped_dir()).glob("*.yaml")):
            if self.copy(p.stem)[0] is not None:
                out.append(p.stem)
        return out

    def status(self, request_id: str) -> dict | None:
        if not xr.valid_id(request_id):
            return None
        path = self.orodruin / "requests" / f"{request_id}.json"
        try:
            doc = xr.read_status(channel_reader.read_json(path))
        except (OSError, ValueError, RecursionError, xr.RequestRefused):
            return None
        return doc if doc.get("request") == request_id else None

    def report(self, run_id: str) -> dict | None:
        if self._reports is None:
            self._reports = runs_layout.run_reports(self.root)
        path = self._reports.get(run_id)
        if path is None:
            return None
        runs = run_report.read_reports({run_id: path})
        return runs[0] if runs else None

    def cycles(self, since: datetime) -> list:
        """The watch's cycles from its files written since ``since`` (``runs/glorfindel/*_debug.jsonl``,
        as the console reads them) — what C1's ``decision_of`` reads of a cycle, nothing more."""
        if self._cycles is None:
            out = []
            floor = since.timestamp() - 60
            for path in sorted(runs_layout.dir_of(runs_layout.GLORFINDEL, self.root).glob("*_debug.jsonl")):
                try:
                    st = channel_reader.lstat_regular(path)   # never through a link (SEC16)
                    if st.st_mtime < floor:
                        continue
                    text = channel_reader.read_text(path)
                except (OSError, ValueError):
                    continue
                for line in text.splitlines():
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    sig = rec.get("signal") if isinstance(rec, dict) else None
                    if isinstance(sig, dict):
                        out.append({"event": sig.get("event", ""), "action": rec.get("action", ""),
                                    "signal_at": sig.get("timestamp", ""), "ttp": sig.get("ttp", ""),
                                    "resource_id": sig.get("resource_id", "")})
            self._cycles = out
        return self._cycles

    def measure(self, run_id: str, since: datetime) -> str:
        """What one run of the occurrence measured: ``proof`` (detected, its decision attached — C1's
        proof), ``missed``, ``unattached`` (detected, no decision attached), ``no_report``,
        ``unknown``."""
        run = self.report(run_id)
        if run is None:
            return "no_report"
        if run["kind"] != "technique" or run["without_glorfindel"]:
            return "unknown"
        if run["detection"] == "missed":
            return "missed"
        if run["detection"] != "detected":
            return "unknown"
        try:
            from eregion_console.indicators import decision_of   # C1's one rule (CROSSINGS)
        except ImportError:   # no console in this image: the proof cannot be told
            return "unattached"
        return "proof" if decision_of(run, self.cycles(since)) is not None else "unattached"

    def signature(self, request_id: str, runs: list[str], since: datetime) -> tuple:
        """What the measures of an occurrence stand on, by their files' versions (the status, the run
        reports, the watch's cycle files written since ``since``) — stat only, nothing read: a pass
        where none changed measures nothing again (``_MEASURES``)."""
        def version(path) -> tuple:
            try:
                st = os.lstat(path)
            except OSError:
                return ()
            return (st.st_mtime_ns, st.st_size, st.st_ino)
        if self._reports is None:
            self._reports = runs_layout.run_reports(self.root)
        floor = since.timestamp() - 60
        cycles = []
        for path in sorted(runs_layout.dir_of(runs_layout.GLORFINDEL, self.root).glob("*_debug.jsonl")):
            v = version(path)
            if v and v[0] / 1e9 >= floor:
                cycles.append((path.name, v))
        return (str(Path(self.root).absolute()), request_id, since.isoformat(),
                version(self.orodruin / "requests" / f"{request_id}.json"),
                tuple((r, str(self._reports.get(r) or ""), version(self._reports[r]) if r in self._reports else ())
                      for r in runs),
                tuple(cycles))

    def measures(self, request_id: str, runs: list[str], since: datetime) -> list[str]:
        """Each run's measure, from the cache while nothing it stands on changed (``signature``)."""
        sig = self.signature(request_id, runs, since)
        if sig not in _MEASURES:
            if len(_MEASURES) >= 32:
                _MEASURES.clear()
            _MEASURES[sig] = [self.measure(r, since) for r in runs]
        return list(_MEASURES[sig])


# The measures of an occurrence by what they stand on (``Sources.signature``): the watch judges every
# minute, all week; the files of the watch's cycles are read again only when one of them changed.
_MEASURES: dict[tuple, list[str]] = {}


# ── The verdict ─────────────────────────────────────────────────────────────────────────────

_MEASURED = {
    "no_report": "a run's report has not reached this host",
    "unknown": "a run measured nothing (its detection unknown)",
    "unattached": "detected, but the watch's decision is not attached to it",
}


def judge(src: Sources, now: datetime | None = None) -> dict:
    """The verdict of the drill of the week now: its last occurrence, its state, why, whether its
    alert mentions the role, the next occurrence and the arming as this host reads them."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    v = {"drill": "", "occurrence": "", "next": "", "state": "off", "code": "", "said": "",
         "mention": False, "armed": "", "reason": "", "request": "", "image": "", "pulse_at": "", "since": "",
         "at": now.isoformat()}

    def out(state: str, code: str = "", said: str = "", **kw) -> dict:
        v.update(state=state, code=code, said=said, **kw)
        return v

    if not src.configured():
        return out("off", "", "no exercise channel on this host: no drill is followed here")
    seen = src.seen()
    permit_seen = (seen or {}).get("permit") or {}
    permit = permit_seen.get("doc") if isinstance(permit_seen.get("doc"), dict) else None
    pulse = src.pulse()
    names = [n for n in ((permit or {}).get("drill"), (pulse or {}).get("drill")) if n] or src.scheduled()
    name = names[0] if names else ""
    copy, sha = src.copy(name)
    v["drill"] = name
    if copy is not None:
        o = copy.schedule.occurrence(now)
        v.update(occurrence=o.isoformat(), next=copy.schedule.next(now).isoformat())
    if pulse is not None:
        v.update(armed=pulse["state"], reason=pulse["reason"], image=pulse["image"],
                 pulse_at=str(((seen or {}).get("pulse") or {}).get("modified") or pulse["at"]))
    if seen is None:
        # Never pulled: quiet a while (the watch just started), then said — never a quiet state without end.
        before = src.previous if src.previous.get("code") == "not_pulled" else {}
        since = min(_when(before.get("since")) or now, now)   # a since to come never holds it quiet
        v["since"] = since.isoformat()
        if (now - since).total_seconds() < PULL_STALE_S:
            return out("waiting", "not_pulled", "the channel not pulled yet on this host")
        return out("channel_unread", "not_pulled", f"no pull of the drill's blobs written on this host since "
                   f"{since.isoformat(timespec='minutes')}: the permit's state is unknown",
                   mention=mention("channel_unread", unread_s=(now - since).total_seconds()))

    # 1. The listing: unread, the permit's state is unknown — neither not_run nor rearm_expected. A last
    # pull too old says nothing more of the channel than one that failed.
    pulled = _when(seen["at"]) or now
    if seen["listed"] and (now - pulled).total_seconds() > PULL_STALE_S:
        return out("channel_unread", "stale", f"the last pull of the drill's blobs is of "
                   f"{pulled.isoformat(timespec='minutes')}: the permit's state is unknown",
                   mention=mention("channel_unread", unread_s=(now - pulled).total_seconds()))
    if not seen["listed"]:
        since = _when(seen["unread_since"]) or now
        unread = (now - since).total_seconds()
        return out("channel_unread", "unread", f"the channel could not be listed since {since.isoformat(timespec='minutes')}"
                   f" ({_error_said(seen['why'])}): the permit's state is unknown",
                   mention=mention("channel_unread", unread_s=unread))
    listed = permit_seen.get("listed") is True
    pulse_seen = seen.get("pulse") or {}
    if pulse_seen.get("listed") and pulse_seen.get("why"):   # §4.1: an Imladris older than Orodruin
        return out("unknown", "pulse_unread", f"drill.json not read here: {pulse_seen['why']}",
                   mention=_previous_unknown(src, v))
    if listed and permit is None:
        return out("unknown", "permit_unread", f"the permit not read here: {permit_seen.get('why')}",
                   mention=_previous_unknown(src, v))
    # A pulse written before this arming is not its word (the arming writes the permit, then the pulse).
    if pulse is not None and permit is not None and (_when(pulse["at"]) or now) < (_when(permit["armed_at"]) or now):
        pulse = None
    last = _own_word(pulse, v)

    # 2. The permit there, Orodruin says it is disarmed: never silent.
    if listed and pulse is not None and pulse["state"] == "disarmed" and pulse["reason"] != "drill_changed":
        return out("self_disarmed", pulse["reason"], "permit present, Orodruin says it is disarmed "
                   f"({pulse['reason']})", mention=mention("self_disarmed"))
    if listed and pulse is None:
        if (now - (_when(permit["armed_at"]) or now)).total_seconds() < ARMING_GRACE_S:
            return out("waiting", "arming", "armed: its pulse not read yet")
        return out("unknown", "no_pulse", "the permit is in the channel, drill.json is not (or predates it)",
                   mention=_previous_unknown(src, v))

    # 3. No permit listed: disarmed — or re-arm expected when the pulse still says armed.
    if not listed:
        if pulse is None or (pulse["state"] == "disarmed" and pulse["reason"] != "drill_changed"):
            why = (pulse or {}).get("reason") or "never armed"
            return out("disarmed", why, f"disarmed ({why}): nothing is expected")
        if last is not None:
            return _result(src, v, last, now, out)
        if pulse["state"] == "disarmed":
            return out("rearm_expected", "drill_changed", "Orodruin's image holds another drill than the "
                       "one armed: re-arm expected")
        gone = _when(permit_seen.get("last_listed"))
        if gone is not None and (now - gone).total_seconds() < DISARM_GRACE_S:
            return out("waiting", "disarming", "the permit just left the channel: a disarming or a kill "
                       "writes its pulse after it")
        return out("rearm_expected", "no_permit", "drill.json says armed, no permit in the channel "
                   "(expired, or removed): re-arm expected")

    # 4. The fingerprints: the permit's and the pulse's, this host's copy's.
    if copy is None or permit["sha256"] != sha or pulse["sha256"] != sha \
            or permit["drill"] != name or pulse["drill"] != name:
        if last is not None:
            return _result(src, v, last, now, out)
        return out("rearm_expected", "fingerprint", "the drill armed is not this host's copy (a release "
                   "changed it): re-arm expected")
    if pulse["state"] != "armed":   # disarmed by drill_changed, the permit still there
        if last is not None:
            return _result(src, v, last, now, out)
        return out("rearm_expected", "drill_changed", "Orodruin's image holds another drill than the one "
                   "armed: re-arm expected")

    # 5. Everything agrees: the absence alarm is armed.
    v["armed"] = "armed"
    at = _when(v["pulse_at"]) or _when(pulse["at"]) or now
    if (now - at).total_seconds() > SILENT_AFTER_S:
        return out("not_run", "silent", f"Orodruin silent: drill.json not written since "
                   f"{at.isoformat(timespec='minutes')}", mention=mention("not_run"))
    o = _when(v["occurrence"])
    if o is None or o < (_when(permit["armed_at"]) or now):
        return out("waiting", "first", "armed: its first occurrence is the next one")
    if last is not None:
        return _result(src, v, last, now, out)
    if (now - o).total_seconds() < NOT_RUN_AFTER_S:
        return out("waiting", "due", "armed: the occurrence is due, its status not here yet")
    return out("not_run", "no_status", f"no status of the occurrence {NOT_RUN_AFTER_S // 3600} h after "
               "its hour: Orodruin did not run it", mention=mention("not_run"))


def _own_word(pulse: dict | None, v: dict) -> dict | None:
    """The pulse's last occurrence when it is this one (the planned hour of this host's copy)."""
    last = (pulse or {}).get("last")
    if not isinstance(last, dict) or not v["occurrence"]:
        return None
    return last if _when(last.get("occurrence")) == _when(v["occurrence"]) else None


def _error_said(why: str) -> str:
    """What a failure to list says outside this host: its type and its HTTP status — never its text,
    which may name the storage account (as analysis/hosted_report.py ``_error_key``)."""
    import re
    kind = re.match(r"[A-Za-z_][A-Za-z0-9_.]*", why or "")
    status = re.search(r"HTTP \d{3}", why or "")
    return " ".join(x for x in ((kind.group(0) if kind else "an error"), status.group(0) if status else "") if x)


def _previous(src: Sources, v: dict) -> tuple[str, str]:
    """The state and the code of the occurrence before this one (``history``)."""
    o = _when(v["occurrence"])
    if o is None:
        return "", ""
    h = src.history.get((o - timedelta(days=7)).isoformat()) or {}
    return str(h.get("state") or ""), str(h.get("code") or "")


def _previous_unknown(src: Sources, v: dict) -> bool:
    return mention("unknown", previous=_previous(src, v)[0])


def _result(src: Sources, v: dict, last: dict, now: datetime, out) -> dict:
    """The occurrence by its own word (the pulse's ``last``), then its status and its runs."""
    state, code = last["state"], last["code"]
    v["request"] = last["request"]
    if state == "refused":
        before, before_code = _previous(src, v)
        return out("refused", code, f"refused before any call: {code}",
                   mention=mention("refused", code, previous=before, previous_code=before_code))
    if state == "skipped":
        return out("skipped", code, f"a wire skipped: {code}")
    if state == "stopped":
        return out("stopped", code or "stopped", "the service was stopped (RuntimeMaxSec, SIGTERM)")
    if state == "failed":
        return out("unknown", code or "failed", f"the occurrence broke ({code or 'failed'}): it measured nothing",
                   mention=_previous_unknown(src, v))
    o = _when(v["occurrence"]) or now
    settled = (now - o).total_seconds() >= SETTLE_S

    def pending(code: str, said: str) -> dict:
        if not settled:
            return out("waiting", code, f"played: {said}")
        return out("unknown", code, said, mention=_previous_unknown(src, v))

    status = src.status(last["request"])
    if status is None:
        return pending("status_unread", "Orodruin's status of its request has not reached this host, or this "
                       "host refused it (an Imladris older than Orodruin)")
    drill = status.get("drill")
    if not isinstance(drill, dict) or drill.get("name") != v["drill"] or _when(drill.get("occurrence")) != o:
        return out("unknown", "status_drill", "the status of its request is not this occurrence's",
                   mention=_previous_unknown(src, v))
    if status["state"] != "finished":
        return pending("not_finished", f"its request is {status['state']}")
    runs = [r for w in status["wires"] for r in w["runs"]]
    if not runs:
        return pending("no_runs", "its request has no run")
    measured = src.measures(last["request"], runs, o)
    if "missed" in measured:
        return out("missed", "missed", "the technique played, no detection: a regression", mention=mention("missed"))
    if all(m == "proof" for m in measured):
        return out("proof", "", f"a proof: {len(runs)} run(s) detected, the decision attached (C1)")
    worst = next(m for m in measured if m != "proof")
    return pending(worst, _MEASURED.get(worst, worst))


# ── The watch's pass, its store ─────────────────────────────────────────────────────────────

def load() -> dict:
    """The store: the current verdict (``current``) and the occurrences' (``history``) — {} when none."""
    try:
        doc = json.loads(_STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def refresh(root: str | Path = "runs", *, now: datetime | None = None, drills_dir: Path | None = None,
            channel: bool | None = None) -> dict:
    """The watch's pass (every minute): the verdict now, written to the store with the occurrences'
    states kept (``history``, the last ``HISTORY``). Returns the verdict."""
    store = load()
    history = store.get("history") if isinstance(store.get("history"), dict) else {}
    current = store.get("current") if isinstance(store.get("current"), dict) else {}
    src = Sources(Path(root), drills_dir, channel, history, current)
    v = judge(src, now)
    if v["occurrence"] and v["state"] in OCCURRENCE_STATES:
        history[v["occurrence"]] = {"state": v["state"], "code": v["code"]}
    history = dict(sorted(history.items())[-HISTORY:])
    doc = {"current": v, "history": history}
    if doc != store:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_name(f".{_STORE.name}.{os.getpid()}")
        tmp.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        tmp.replace(_STORE)
    return v


def alerts(v: dict) -> bool:
    """Whether the bot says this verdict: every state of §4.2 (``proof`` as a line), never a quiet one."""
    return v.get("state") in STATES


def key(v: dict) -> str:
    """What the bot posts once: the drill, the occurrence, its state, its code, its mention."""
    return "|".join(str(v.get(k) or "") for k in ("drill", "occurrence", "state", "code")) \
        + ("|@" if v.get("mention") else "")


_LABELS = {
    "proof": "✅ preuve", "missed": "❌ manquée", "unknown": "❔ inconnue", "refused": "⛔ refusée",
    "skipped": "⏭ fil sauté", "stopped": "⏹ arrêtée", "not_run": "🚨 non jouée",
    "rearm_expected": "🔁 réarmement attendu", "self_disarmed": "⚠ permis présent, Orodruin se dit désarmé",
    "channel_unread": "📡 canal illisible",
}


def bot_message(v: dict) -> str:
    """The verdict as the bot posts it in the drill's thread: every value escaped (SEC6,
    glorfindel/chat_text.py) — the mention, when there is one, is the bot's (the role configured)."""
    from glorfindel.chat_text import discord_code, discord_text
    o = _when(v.get("occurrence"))
    when = o.strftime("%a %d/%m %H:%M UTC") if o else "—"
    nxt = _when(v.get("next"))
    parts = [f"**drill {discord_code(v.get('drill'))} · {discord_text(_LABELS.get(v.get('state'), v.get('state')))}**"
             f" · occurrence {discord_code(when)}"]
    if v.get("code"):
        parts.append(f"code {discord_code(v.get('code'))}")
    line = " · ".join(parts)
    said = discord_text(" ".join(str(v.get("said") or "").split())[:900])
    tail = f"\n> {said}" if said else ""
    if nxt:
        tail += f"\nprochaine : {discord_code(nxt.strftime('%a %d/%m %H:%M UTC'))}"
    return line + tail


def thread_key(drill: str) -> str:
    """The drill's own thread in the bot's channel (« drill · <name> »)."""
    return f"drill:{drill}"


def drill_of_run(root: str | Path, run_id: str, request_id: str) -> str:
    """The drill whose occurrence this run is a wire of — its request's status carries ``drill`` — else
    "": the tile of the last proof says when it comes from the drill of the week (§1.1)."""
    status = Sources(Path(root)).status(request_id)
    if status is None or not isinstance(status.get("drill"), dict):
        return ""
    if not any(run_id in w["runs"] for w in status["wires"]):
        return ""
    return str(status["drill"].get("name") or "")
