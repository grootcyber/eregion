"""The drill of the week, on Orodruin (DRL1a, docs/design/drill-banc.md): one occurrence, played by
a systemd timer the operator armed.

    python -m eregion_core.scheduled_drill run          # the service's one command, no argument
    python -m eregion_core.scheduled_drill fingerprint <drill>   # the arming reads it (read only)
    python -m eregion_core.scheduled_drill check [--targets <vm>,…]   # orodruin-drill-check

Three inputs decide an occurrence, and only they may start one: the drill in the verified image
(``/app/drills/``), the arming (``~/drill/armed.json``, the operator's), the clock. What comes from
elsewhere — the watch's heartbeat (V1), the operator's permit in the channel, the targets' state in
Azure — may only refuse. In this order, refused at the first that fails (§2.3, §3.1):

    0  the arming read (``disarmed``); the drill read from the image by its one reader, the shipped
       layer only — never ``drill.find`` (``drill_changed``); its fingerprint, the arming's
       (``drill_changed``); the image's catalogue: each wire a public, implemented, non-destructive
       technique (``not_eligible``); the hour, within 30 min of the schedule's (``off_schedule``)
       — nothing written before it; the permit, present and equal to the arming (``no_permit``,
       ``permit_mismatch``), rewritten as it was under If-Match (§2.4)
    1  Orodruin's one lock (``busy``, never waited for); under it, the registry read (``too_soon``:
       an occurrence played less than 6 days ago, or a registry unreadable) then written, on disk,
       before the judgment; the request made, one VM per name armed (``not_placed``)
    2–4  the runner's first judgment (``Runner.judge``, DG-b's): the contract (``passive``), the watch
       read again up to 10 min (``watch``), each target enrolled in zone bench (``not_bench``), the
       drill's cap within Orodruin's (``over_cap``)
    5  the isolation read before any start: a VM held by Glorfindel is skipped (``isolated``) and
       never started — the drill never lifts an isolation
    6  a VM stopped is started (an ARM ``POST …/start``, no SDK), in an armed session journaled
       before the call (``<request>-start``), the call counted in the cap the runner is given; then
       a fresh Heartbeat awaited, 10 min at most (``not_ready``)
    7  ``Runner.run``: zones ``("bench",)``, no wait for an isolation, the lock's descriptor handed
       down (``EREGION_RUN_LOCK_FD``), the drill's own ``launch`` (``Popen``)
    9  the pulse (``orodruin/drill.json``) at every occurrence, refused included — but a disarmed
       one, which publishes nothing more

SIGTERM (systemd's stop at ``RuntimeMaxSec``, relayed by ``--init``): relayed to the wire in flight,
never raised while it is awaited; the wire is waited for 75 s at most, then killed; the occurrence
is ``stopped``. Outside a wire, the handler raises, or the next checkpoint stops.

The expectations (``expectations/``) are never read here, nor imported: Orodruin cannot read them
(tests/unit/test_drill_expectations.py). Every reader is a parameter: the tests play an occurrence
on fakes, no Azure, no injector.
"""
from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from eregion_core import channel_reader, drill_arming as da, exercise_runner as er
from eregion_core import drill as dr
from eregion_core import exercise_request as xr
from eregion_core import orodruin, runs_layout, watch_gate

# An occurrence starts within this of its schedule's hour, or it is refused (off_schedule): a start
# of the service by hand, or an OnCalendar rewritten, plays nothing.
WINDOW_S = 30 * 60
# At most one occurrence in this, whatever the clock or the timer say (too_soon).
MIN_GAP_S = 6 * 24 * 3600
# The watch read again this long (a deployment of Imladris), then refused (watch).
WATCH_WAIT_S = 10 * 60
# A target started: its fresh Heartbeat awaited this long, then its wire skipped (not_ready). A VM
# already running counts as ready with a Heartbeat this recent.
READY_WAIT_S = 10 * 60
POLL_S = 30.0
# SIGTERM relayed to the wire: waited for this long, under docker stop's 90 s, then killed.
STOP_WAIT_S = 75.0
ZONES = ("bench",)

ARMED_ENV = "EREGION_DRILL_ARMED"
# The codes of an occurrence refused before its request (they live in the pulse only, §4.1).
EARLY = ("disarmed", "drill_changed", "not_eligible", "off_schedule", "no_permit", "permit_mismatch",
         "busy", "too_soon", "not_placed")
COMPUTE_API = "2024-07-01"
LOGS_API = "2017-01-01-preview"
WORKSPACE_ENV = "EREGION_BENCH_WORKSPACE"     # as Gothmog reads it (gothmog/engines/chaos_studio.py)
DEFAULT_WORKSPACE = "law-celebrimbor-amonsul"


class Stopped(RuntimeError):
    """The service was stopped (SIGTERM): the occurrence ends, ``stopped``. A ``RuntimeError``, so
    that the runner takes it from a wire's ``launch`` as a wire that failed and runs nothing more;
    every read of this module that takes ``Exception`` lets it through (``except Stopped: raise``),
    and ``_end`` says ``stopped`` whatever the code, once SIGTERM came."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def armed_path() -> Path:
    """``~/drill/armed.json`` on the host, mounted read-only at ``/app/drill/`` (the working
    directory's ``drill/``); ``EREGION_DRILL_ARMED`` for the tests."""
    return Path(os.environ.get(ARMED_ENV) or Path("drill") / "armed.json")


def registry_path(runs_dir: Path | str = "runs") -> Path:
    return runs_layout.dir_of(runs_layout.ORODRUIN, runs_dir) / "drills" / "played.jsonl"


def pulse_path(runs_dir: Path | str = "runs") -> Path:
    return runs_layout.dir_of(runs_layout.ORODRUIN, runs_dir) / "drill.json"


# ── Orodruin's reads and its one write on a VM, by its identity (no SDK) ─────────────────

class Arm:
    """ARM with Orodruin's identity — the paths checked as the inscription's (SEC8), the token to
    Azure Resource Manager only."""

    def __init__(self, credential=None, http=None):
        self._credential, self._http = credential, http

    def _call(self, method: str, path: str, api: str, body=None) -> dict:
        from eregion_core.held import safe_path
        from eregion_core.inscription import ARM, TagEnrollment
        if self._http is None:
            import requests
            self._http = requests
        path = safe_path(path)
        # The inscription's reader holds the identity (no SDK of a provider imported here: MC0).
        reader = self._reader = getattr(self, "_reader", None) or TagEnrollment(credential=self._credential)
        r = getattr(self._http, method)(f"{ARM}{path}", headers=reader._headers(),
                                        params={"api-version": api}, json=body, timeout=30)
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code} on {method.upper()} …/{path.rsplit('/', 1)[-1]}")
        try:
            return r.json() if r.content else {}
        except ValueError:
            return {}

    def power(self, vm_id: str) -> str:
        """The VM's power state now (``running``, ``deallocated``, …) — "" when it says none."""
        view = self._call("get", f"{vm_id}/instanceView", COMPUTE_API)
        for s in view.get("statuses") or []:
            code = str(s.get("code") or "")
            if code.startswith("PowerState/"):
                return code.split("/", 1)[1]
        return ""

    def start(self, vm_id: str) -> None:
        self._call("post", f"{vm_id}/start", COMPUTE_API)

    def last_heartbeat(self, vm_id: str) -> datetime | None:
        """The VM's last Heartbeat in the bench's workspace (Log Analytics Reader, through ARM)."""
        sub = os.environ.get("AZURE_SUBSCRIPTION_ID") or ""
        rg = os.environ.get(orodruin.BENCH_RG_ENV) or orodruin.DEFAULT_BENCH_RG
        ws = os.environ.get(WORKSPACE_ENV) or DEFAULT_WORKSPACE
        rid = vm_id.replace("'", "")
        body = self._call("post", f"/subscriptions/{sub}/resourceGroups/{rg}/providers/"
                          f"Microsoft.OperationalInsights/workspaces/{ws}/api/query", LOGS_API,
                          body={"query": f"Heartbeat | where _ResourceId =~ '{rid}' "
                                         "| summarize LastSeen = max(TimeGenerated)", "timespan": "PT1H"})
        for table in body.get("tables") or []:
            for row in table.get("rows") or []:
                if row and row[0]:
                    try:
                        return datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
                    except ValueError:
                        return None
        return None


# ── One occurrence ─────────────────────────────────────────────────────────────────────

class Occurrence:
    def __init__(self, *, armed_file: Path | str | None = None, drills_dir: Path | str | None = None,
                 catalog: dict | None = None, runs_dir: Path | str = "runs", now=_now, sleep=time.sleep,
                 monotonic=time.monotonic, say=print,
                 read_permit: Callable | None = None, write_permit: Callable | None = None,
                 publish_pulse: Callable | None = None, lock=er.request_lock,
                 list_vms: Callable | None = None, check: Callable | None = None,
                 watch: Callable | None = None, isolated: Callable | None = None,
                 power: Callable | None = None, start: Callable | None = None,
                 heartbeat: Callable | None = None, arm: Callable = orodruin.arm,
                 read_target: Callable | None = None, publish_status: Callable | None = er.publish_status,
                 publish_contract: Callable | None = orodruin.publish_contract,
                 popen=subprocess.Popen, watch_wait_s: float = WATCH_WAIT_S,
                 ready_wait_s: float = READY_WAIT_S, poll_s: float = POLL_S,
                 stop_wait_s: float = STOP_WAIT_S, child_poll_s: float = 1.0):
        from eregion_core import exercise_channel as xc
        from eregion_core.exercise_plan import load_catalog
        self.armed_file = Path(armed_file) if armed_file is not None else armed_path()
        self.drills_dir = Path(drills_dir) if drills_dir is not None else dr.shipped_dir()
        self.catalog = catalog if catalog is not None else load_catalog()
        self.runs_dir = Path(runs_dir)
        self.now, self.sleep, self.monotonic, self.say = now, sleep, monotonic, say
        self.read_permit = read_permit or (lambda: xc.read_drill(xc.PERMIT_BLOB))
        self.write_permit = write_permit or (lambda doc, etag: xc.publish_drill(xc.PERMIT_BLOB, doc, if_match=etag))
        self.publish_pulse = publish_pulse or (lambda doc: xc.publish_drill(xc.DRILL_BLOB, doc))
        self.lock = lock
        arm_ = None if all((power, start, heartbeat)) else Arm()
        self.list_vms = list_vms or self._vms
        self.check = check or orodruin.check
        self.watch = watch or watch_gate.refusal
        self.isolated = isolated or er.isolated
        self.power = power or arm_.power
        self.start = start or arm_.start
        self.heartbeat = heartbeat or arm_.last_heartbeat
        self.arm = arm
        self.read_target = read_target or er.read_target
        self.publish_status, self.publish_contract = publish_status, publish_contract
        self.popen = popen
        self.watch_wait_s, self.ready_wait_s, self.poll_s = watch_wait_s, ready_wait_s, poll_s
        self.stop_wait_s, self.child_poll_s = stop_wait_s, child_poll_s
        # What the occurrence learns, step by step.
        self.armed: dict | None = None
        self.drill: dr.Drill | None = None
        self.sha = ""
        self.planned: datetime | None = None
        self.request: xr.Request | None = None
        self.start_calls = 0
        self.unready: dict[str, str] = {}
        self.declared_cap: dict = {}
        self._watched = False
        # SIGTERM: when it came (monotonic), and the wire in flight to relay it to.
        self.stop_at: float | None = None
        self.child = None
        self._launching = False
        self._relayed = False

    @staticmethod
    def _vms() -> list[dict]:
        from eregion_core.inscription import TagEnrollment
        return TagEnrollment().vms(os.environ.get("AZURE_SUBSCRIPTION_ID", ""))

    # ── SIGTERM ──────────────────────────────────────────────────────────────────────
    def install(self) -> None:
        """The handler (the service's stop): never raises while a wire is awaited."""
        signal.signal(signal.SIGTERM, self.on_term)

    def on_term(self, signum=None, frame=None) -> None:
        first = self.stop_at is None
        if first:
            self.stop_at = self.monotonic()
        child = self.child
        if child is not None:
            # A wire in flight: relayed, and awaited by launch — never a raise here, which would
            # let the wire be killed without its finally (its window open, its cleanup not run).
            self._relay(child)
            return
        if self._launching or not first:
            # Between Popen and the wire known (launch relays it once it is), or a second signal:
            # noted, never raised — the next checkpoint stops.
            return
        raise Stopped("the service was stopped (SIGTERM)")

    def _relay(self, child) -> None:
        if not self._relayed:
            self._relayed = True
            with contextlib.suppress(OSError):
                child.send_signal(signal.SIGTERM)

    def _checkpoint(self) -> None:
        if self.stop_at is not None:
            raise Stopped("the service was stopped (SIGTERM)")

    def launch(self, argv: list[str], env: dict) -> int:
        """The drill's wire: its injector's own process (``Popen``), the request's lock handed down,
        awaited — SIGTERM relayed to it, then STOP_WAIT_S at most before it is killed. Stopped, it
        raises once the wire has ended: the runner marks it failed and runs nothing more."""
        self._checkpoint()
        fd = env.get(er.LOCK_FD_ENV, "")
        self._launching, self._relayed = True, False
        try:
            child = self.popen(argv, env={**os.environ, **env}, pass_fds=(int(fd),) if fd.isdigit() else ())
            self.child = child
        finally:
            self._launching = False
        if self.stop_at is not None:
            self._relay(child)   # SIGTERM came while the wire was launched: relayed now, then awaited
        try:
            while True:
                try:
                    code = child.wait(timeout=self.child_poll_s)
                    break
                except subprocess.TimeoutExpired:
                    if self.stop_at is not None and self.monotonic() - self.stop_at >= self.stop_wait_s:
                        self.say(f"[drill] the wire did not end {self.stop_wait_s:.0f} s after SIGTERM: killed")
                        child.kill()
                        code = child.wait()
                        break
        finally:
            self.child = None
        if self.stop_at is not None:
            raise Stopped(f"the service was stopped: the wire got SIGTERM and ended (exit {code})")
        return code

    # ── The steps ────────────────────────────────────────────────────────────────────
    def _read_armed(self) -> tuple[dict | None, str]:
        try:
            doc = channel_reader.read_json(self.armed_file, da.MAX_BYTES)
        except FileNotFoundError:
            return None, "no arming on this Orodruin (make orodruin-drill-arm)"
        except (OSError, ValueError) as e:
            return None, f"the arming unreadable: {e}"
        try:
            return da.read_armed(doc), ""
        except da.ArmingRefused as e:
            return None, f"the arming refused: {e}"

    def _permit(self) -> tuple[str, str]:
        """(code, why) — ("", "") when the permit is in the channel, equal to the arming, and
        rewritten as it was over the very blob read (If-Match)."""
        from eregion_core.exercise_channel import Changed
        try:
            doc, etag = self.read_permit()
        except Stopped:
            raise
        except Exception as e:
            return "permit_mismatch", f"the permit unreadable: {e}"[:300]
        if doc is None:
            return "no_permit", "no permit in the channel: removed by a kill or a disarming, or expired — re-arm"
        try:
            permit = da.read_permit(doc)
        except da.ArmingRefused as e:
            return "permit_mismatch", f"the permit refused: {e}"
        if permit != da.permit_of(self.armed):
            return "permit_mismatch", "the permit is not this arming's (drill, fingerprint, time)"
        if not etag:
            return "permit_mismatch", "the permit read without its ETag: never rewritten unconditionally"
        try:
            self.write_permit(permit, etag)
        except Changed as e:
            return "no_permit", f"the permit changed or was removed since it was read: {e}"
        except Stopped:
            raise
        except Exception as e:
            return "permit_mismatch", f"the permit not rewritten: {e}"[:300]
        return "", ""

    def _last_played(self) -> tuple[datetime | None, str]:
        path = registry_path(self.runs_dir)
        last = None
        try:
            for line in channel_reader.read_text(path).splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                when = datetime.fromisoformat(rec["played"])
                if when.tzinfo is None:
                    raise ValueError(f"an occurrence played at {rec['played']!r}, without its time zone")
                last = when if last is None or when > last else last
        except FileNotFoundError:
            return None, ""
        except (OSError, ValueError, KeyError, TypeError) as e:
            return None, f"the registry of the occurrences played cannot be read ({e}): nothing plays"
        return last, ""

    def _mark_played(self) -> None:
        path = registry_path(self.runs_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        channel_reader.append_line(path, json.dumps({
            "drill": self.drill.name, "sha256": self.sha, "occurrence": self.planned.isoformat(),
            "played": self.now().isoformat()}), sync=True)

    def _place(self) -> tuple[list[tuple[str, str]], str]:
        """The wires' (experiment, VM id) pairs: each name armed, one enrolled VM of that name read
        now by Orodruin's identity — whatever its zone (the judgment says not_bench)."""
        try:
            cands = dr.candidates(self.list_vms())
        except Stopped:
            raise
        except Exception as e:
            return [], f"the bench's VMs unreadable: {e}"[:300]
        pairs = []
        for w in self.drill.wires:
            for name in self.armed["targets"]:
                found = [c for c in cands if c.name.lower() == name.lower()]
                if len(found) != 1:
                    return [], (f"{name}: {len(found)} enrolled VM(s) of that name read here — one, or the "
                                "drill does not play")
                pairs.append((w.experiment, found[0].resource_id))
        return pairs, ""

    def _watch(self) -> str:
        """The watch (V1): at the first judgment read again up to WATCH_WAIT_S, then as it is."""
        if self._watched:
            return self.watch()
        self._watched = True
        deadline = self.now() + timedelta(seconds=self.watch_wait_s)
        while True:
            why = self.watch()
            if not why or self.now() >= deadline:
                return why
            self.say(f"[drill] no live watch yet ({why}) — read again")
            self.sleep(self.poll_s)
            self._checkpoint()

    def _reduced(self) -> orodruin.Verdict:
        """The contract read now, its cap the drill's within the declared one, less the calls the
        start of a target made (the runner counts only its own)."""
        verdict = self.check()
        if not verdict.armed:
            return verdict
        self.declared_cap = dict(verdict.cap)
        s = self.drill.schedule
        cap = {"max_injections": min(s.max_injections, verdict.cap.get("max_injections", 0)) - self.start_calls,
               "max_run_s": min(s.max_run_s, verdict.cap.get("max_run_s", 0))}
        return orodruin.Verdict(verdict.verdict, list(verdict.missing), cap, list(verdict.notes))

    def _prepare(self, req: xr.Request) -> None:
        """Steps 5 and 6, for each target: the isolation read first; a VM held is never started.
        A VM stopped is started, journaled before the call, counted; then its Heartbeat awaited."""
        for rid in {w.target.lower(): w.target for w in req.wires}.values():
            self._checkpoint()
            held = self.isolated(rid)
            if held:
                self.unready[rid.lower()] = f"held by Glorfindel at the drill's start ({held}): never started"
                continue
            try:
                state = self.power(rid)
            except Stopped:
                raise
            except Exception as e:
                self.unready[rid.lower()] = f"its power state unreadable: {e}"[:200]
                continue
            since = self.now() - timedelta(seconds=self.ready_wait_s)
            if state != "running":
                self._checkpoint()
                since = self.now()
                why = self._start(req, rid, state)
                if why:
                    self.unready[rid.lower()] = why
                    continue
            if not self._ready(rid, since):
                self.unready[rid.lower()] = f"no fresh Heartbeat within {self.ready_wait_s / 60:.0f} min"

    def _start(self, req: xr.Request, rid: str, state: str) -> str:
        """A stopped target started, in an armed session journaled before the call — "" when it
        is; else why not. A session refused, a journal that cannot be written or a cap reached
        (``before_call``), a start that fails: the target is not ready, its wire skipped, the
        occurrence said — never a crash without its pulse, this week already spent."""
        try:
            verdict, session = self.arm(f"{req.id}-start", "drill", verdict=self._reduced(), request=req.id)
            if session is None:
                return "Orodruin passive at the start: never started"
            session.before_call("start_vm", rid, f"drill {self.drill.name}: its target was {state or 'not running'}")
            self.start_calls += 1
            self.say(f"[drill] {rid.rsplit('/', 1)[-1]} {state or 'not running'}: started")
            self.start(rid)
        except Stopped:
            raise
        except Exception as e:
            return f"its start failed: {type(e).__name__}: {e}"[:200]
        return ""

    def _ready(self, rid: str, since: datetime) -> bool:
        deadline = self.now() + timedelta(seconds=self.ready_wait_s)
        while True:
            try:
                beat = self.heartbeat(rid)
            except Stopped:
                raise
            except Exception as e:
                self.say(f"[drill] the Heartbeat unreadable now: {e}"[:200])
                beat = None
            if beat is not None and beat >= since:
                return True
            if self.now() >= deadline:
                return False
            self.sleep(self.poll_s)
            self._checkpoint()

    def _runner(self) -> er.Runner:
        info = {"name": self.drill.name, "sha256": self.sha, "occurrence": self.planned.isoformat()}
        return er.Runner(check=self._reduced, watch=self._watch, read_target=self.read_target,
                         fault_targets=lambda: {}, isolated=self.isolated, launch=self.launch,
                         publish=self.publish_status, publish_contract=self.publish_contract,
                         catalog=self.catalog, runs_dir=self.runs_dir, now=self.now, sleep=self.sleep,
                         wait_isolation_s=0, say=self.say, zones=ZONES,
                         not_ready=lambda rid: self.unready.get(rid.lower(), ""), drill=info)

    # ── The occurrence, in its order ─────────────────────────────────────────────────
    def run(self) -> dict:
        """One occurrence: what it did, as its pulse says it (``last``)."""
        try:
            return self._occur()
        except Stopped as e:
            return self._end("stopped", "stopped", str(e))
        except Exception as e:
            # Whatever broke, the occurrence is said and its pulse published: Imladris reads a
            # cause, never a silence.
            return self._end("failed", "crashed", f"the occurrence broke: {type(e).__name__}: {e}"[:300])

    def _occur(self) -> dict:
        armed, why = self._read_armed()
        if armed is None:
            self.say(f"[drill] disarmed — {why}. Nothing runs, nothing is published.")
            return {"state": "refused", "code": "disarmed", "why": why}
        self.armed = armed
        try:
            drill, sha = dr.loaded(self.drills_dir / f"{armed['drill']}.yaml", dr.SHIPPED, self.catalog)
        except dr.DrillRefused as e:
            return self._end("refused", "drill_changed", f"the drill armed does not read in this image: {e}")
        if drill.schedule is None:
            return self._end("refused", "drill_changed", f"{drill.name} in this image is not scheduled")
        self.drill = drill
        if sha != armed["sha256"]:
            return self._end("refused", "drill_changed", f"{drill.name} in this image is not the drill armed "
                             "(its fingerprint changed): re-arm after reading it")
        self.sha = sha
        for w in drill.wires:
            why = dr.eligible(self.catalog.get(w.experiment))
            if why:
                return self._end("refused", "not_eligible", f"the image's catalogue: {why}")
        now = self.now()
        self.planned = drill.schedule.occurrence(now)
        if (now - self.planned).total_seconds() > WINDOW_S:
            return self._end("refused", "off_schedule", (
                f"{now.isoformat(timespec='minutes')} is not within {WINDOW_S // 60} min of the schedule "
                f"({drill.schedule.day} {drill.schedule.at} UTC): a start by hand plays nothing"))
        self._checkpoint()
        code, why = self._permit()
        if code:
            return self._end("refused", code, why)
        stack = contextlib.ExitStack()
        try:
            fd = stack.enter_context(self.lock(f"drill {drill.name}"))
        except er.Busy as e:
            return self._end("refused", "busy", str(e))
        with stack:
            return self._locked(fd)

    def _locked(self, fd: int) -> dict:
        last, why = self._last_played()
        if why:
            return self._end("refused", "too_soon", why)
        if last is not None and (self.now() - last).total_seconds() < MIN_GAP_S:
            return self._end("refused", "too_soon", f"an occurrence played {last.isoformat(timespec='minutes')}: "
                             f"one in {MIN_GAP_S // 86400} days at most")
        self._mark_played()   # on disk before the judgment: whatever follows, this week is played
        self._checkpoint()
        pairs, why = self._place()
        if why:
            return self._end("refused", "not_placed", why)
        req = xr.new(pairs, now=self.now())
        self.request = req
        runner = self._runner()
        status, verdicts, cap, _names, _faults = runner.judge(req, {})
        if status.state != "refused":
            s = self.drill.schedule
            if s.max_injections > self.declared_cap.get("max_injections", 0) \
                    or s.max_run_s > self.declared_cap.get("max_run_s", 0):
                status.state, status.codes = "refused", ["over_cap"]
                for w in status.wires:
                    w.state, w.code = "refused", "over_cap"
        if status.state == "refused":
            runner._emit(status)
            code = status.codes[0] if status.codes and status.codes[0] != "refused_wires" else \
                next((w.code for w in status.wires if w.code), "refused")
            code = "watch" if code == "no_watch" else code
            reasons = "; ".join(f"{v.code}: {v.reason}" for v in verdicts if v.code) or ", ".join(status.codes)
            return self._end("refused", code, reasons)
        self._prepare(req)
        self._checkpoint()
        before = os.environ.get(er.LOCK_FD_ENV)
        os.environ[er.LOCK_FD_ENV] = str(fd)   # the runner holds this very lock: never Busy
        try:
            status = runner.run(req, {})
        finally:
            if before is None:
                os.environ.pop(er.LOCK_FD_ENV, None)
            else:
                os.environ[er.LOCK_FD_ENV] = before
        if self.stop_at is not None:
            return self._end("stopped", "stopped", "the service was stopped (SIGTERM) during the occurrence")
        if status.state == "refused":
            return self._end("refused", status.codes[0] if status.codes else "refused", "refused at the run")
        skipped = next((w for w in status.wires if w.state in ("skipped", "refused")), None)
        failed = next((w for w in status.wires if w.state == "failed"), None)
        if failed is not None:
            return self._end("failed", failed.code or "failed", f"wire {failed.rank} failed")
        if skipped is not None:
            return self._end("skipped", skipped.code, f"wire {skipped.rank} {skipped.state}: {skipped.code}")
        return self._end("played", "", f"{len(status.wires)} wire(s) played")

    def _end(self, state: str, code: str, why: str) -> dict:
        """The occurrence said, then its pulse kept here and published (§4.1). SIGTERM came: it is
        ``stopped``, whatever a read that took it said."""
        if code != "stopped" and self.stop_at is not None:
            state, code, why = "stopped", "stopped", f"the service was stopped (SIGTERM); then {why}"
        at = self.now()
        self.say(f"[drill] {state}{(' — ' + code) if code else ''}: {xr.shown(why)}")
        drill_changed = code == "drill_changed"
        name = self.drill.name if self.drill else (self.armed or {}).get("drill", "")
        sha = self.sha or (self.armed or {}).get("sha256", "")
        nxt = ""
        if self.drill is not None and self.drill.schedule is not None and not drill_changed:
            nxt = self.drill.schedule.next(at).isoformat()
        last = {"at": at.isoformat(), "occurrence": self.planned.isoformat() if self.planned else "",
                "state": state, "code": code if code != "stopped" else "stopped",
                "request": self.request.id if self.request else ""}
        try:
            doc = da.pulse(state="disarmed" if drill_changed else "armed",
                           reason="drill_changed" if drill_changed else "", drill=name, sha256=sha,
                           next_at=nxt, last=last, image=(self.armed or {}).get("image", ""),
                           at=at.isoformat())
        except da.ArmingRefused as e:
            self.say(f"[drill] the pulse not written: {e}")
            return {"state": state, "code": code, "why": why}
        path = pulse_path(self.runs_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            channel_reader.write_file(path, json.dumps(doc, indent=2))
        except OSError as e:   # the pulse still goes to the channel
            self.say(f"[drill] the pulse not kept on this disk: {e}"[:300])
        try:
            self.publish_pulse(doc)
        except Exception as e:   # the occurrence is said here; Imladris says the silence
            self.say(f"[drill] the pulse not published: {e}"[:300])
        return {"state": state, "code": code, "why": why}


# ── The read-only commands of the operator's targets (orodruin-drill-arm, -check) ─────────

def fingerprint(name: str, drills_dir: Path | None = None, catalog: dict | None = None) -> dict:
    """What the arming reads in the image: the drill, its fingerprint, its schedule. Nothing written."""
    if not dr.valid_name(name):
        raise dr.DrillRefused(f"{name!r} is not a drill's name")
    drill, sha = dr.loaded(Path(drills_dir or dr.shipped_dir()) / f"{name}.yaml", dr.SHIPPED, catalog)
    if drill.schedule is None:
        raise dr.DrillRefused(f"{name} is not scheduled: only a drill with a schedule is armed")
    s = drill.schedule
    return {"drill": drill.name, "sha256": sha, "day": s.day, "at": s.at, "on_calendar": s.on_calendar(),
            "max_injections": s.max_injections, "max_run_s": s.max_run_s}


def check(name: str, targets: list[str], *, now=_now, catalog: dict | None = None,
          drills_dir: Path | str | None = None,
          contract: Callable = orodruin.check, watch: Callable | None = None,
          list_vms: Callable | None = None, isolated: Callable = er.isolated,
          power: Callable | None = None, read_permit: Callable | None = None) -> tuple[list[str], bool]:
    """``orodruin-drill-check``, dry: what the next occurrence would do, and when — the drill in the
    image, the contract, the watch, the permit, the targets. Nothing written, on Orodruin or Azure."""
    from eregion_core import exercise_channel as xc
    from eregion_core.exercise_plan import load_catalog
    catalog = catalog if catalog is not None else load_catalog()
    lines, ok = [], True
    try:
        fp = fingerprint(name, drills_dir, catalog=catalog)
    except dr.DrillRefused as e:
        return [f"✗ the drill {name}: {e}"], False
    drill = dr.load_file(Path(drills_dir or dr.shipped_dir()) / f"{name}.yaml", dr.SHIPPED, catalog)
    lines.append(f"✓ the drill {name} in this image: fingerprint {fp['sha256'][:12]}…, "
                 f"{fp['day']} {fp['at']} UTC — next {drill.schedule.next(now()).isoformat(timespec='minutes')}")
    for w in drill.wires:
        why = dr.eligible(catalog.get(w.experiment))
        lines.append(f"{'✗' if why else '✓'} wire {w.experiment}: {why or 'public, implemented, non-destructive'}")
        ok = ok and not why
    verdict = contract()
    lines.append(f"{'✓' if verdict.armed else '✗'} contract: {verdict.verdict}"
                 + ("" if verdict.armed else f" ({verdict.reasons()})"))
    if verdict.armed:
        over = (drill.schedule.max_injections > verdict.cap.get("max_injections", 0)
                or drill.schedule.max_run_s > verdict.cap.get("max_run_s", 0))
        lines.append(f"{'✗' if over else '✓'} cap: the drill's {drill.schedule.max_injections} calls, "
                     f"{drill.schedule.max_run_s} s — declared {verdict.cap}")
        ok = ok and not over
    ok = ok and verdict.armed
    lost = (watch or (lambda: watch_gate.refusal(record=False)))()
    lines.append(f"{'✗' if lost else '✓'} watch: {lost or 'a live Glorfindel watch'}")
    ok = ok and not lost
    try:
        doc, _ = (read_permit or (lambda: xc.read_drill(xc.PERMIT_BLOB)))()
        lines.append(f"· permit: {'present' if doc is not None else 'absent (written by the arming)'}")
    except Exception as e:
        lines.append(f"✗ permit unreadable: {e}"[:300])
        ok = False
    if targets:
        try:
            cands = dr.candidates((list_vms or Occurrence._vms)())
        except Exception as e:
            return lines + [f"✗ the bench's VMs unreadable: {e}"[:300]], False
        reader = power or Arm().power
        for t in targets:
            found = [c for c in cands if c.name.lower() == t.lower()]
            if len(found) != 1:
                lines.append(f"✗ {t}: {len(found)} enrolled VM(s) of that name (not_placed)")
                ok = False
                continue
            c = found[0]
            held = isolated(c.resource_id)
            try:
                state = reader(c.resource_id)
            except Exception as e:
                state = f"unreadable ({e})"[:120]
            bad = c.zone != "bench" or bool(held)
            lines.append(f"{'✗' if bad else '✓'} {t}: zone {c.zone}{' (not_bench)' if c.zone != 'bench' else ''}, "
                         f"{('held: ' + held + ' (isolated)') if held else 'free'}, {state or 'no power state'}"
                         + (" — would be started, journaled first" if state not in ("running",) and not bad else ""))
            ok = ok and not bad
    return lines, ok


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["run"]:
        occ = Occurrence()
        occ.install()
        out = occ.run()
        return 0 if out["state"] == "played" else 1
    if len(args) == 2 and args[0] == "fingerprint":
        try:
            print(json.dumps(fingerprint(args[1])))
        except dr.DrillRefused as e:
            print(f"✗ {xr.shown(e)}", file=sys.stderr)
            return 1
        return 0
    if args and args[0] == "check" and len(args) in (2, 4) and (len(args) == 2 or args[2] == "--targets"):
        try:
            targets = da.parse_targets(args[3]) if len(args) == 4 else []
        except da.ArmingRefused as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1
        lines, ok = check(args[1], targets)
        print("\n".join(xr.shown(line) for line in lines))
        return 0 if ok else 1
    print("usage: python -m eregion_core.scheduled_drill run | fingerprint <drill> | "
          "check <drill> [--targets <vm>,…]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
