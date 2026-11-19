"""The drill of the week, from the operator's machine (DRL1a, docs/design/drill-banc.md §2.1, §3.1,
§5.1): ``make orodruin-drill-check``, ``-arm`` and ``-disarm``, and the three steps of the kill.

What runs on Orodruin goes by SSH, the host key pinned (``DRILL_ORO_SSH``, the Makefile's
ORO_SSH); what is written in the channel and on the scheduled start goes by the operator's own
``az login`` — never Orodruin's identity:

    check   dry: the drill read in Orodruin's image (its fingerprint, its schedule), the contract,
            the watch, the permit, the targets; the scheduled start of DRL1c; the arming on the disk.
            Nothing is written, on Orodruin or on Azure.
    arm     DRILL= TARGETS=<vm>[,<vm>…] — never ``all``: refused unless the scheduled start exists
            and its hour is the schedule's less 20 min (« apply first »); then the arming
            (~/drill/armed.json, mode 600), the units (eregion-drill.timer, eregion-drill.service),
            the timer enabled; the permit written, the scheduled start enabled, the pulse « armed »
    disarm  the timer disabled and its units removed, the arming removed, the permit removed, the
            scheduled start disabled, the pulse « disarmed »: each step said, exit 1 if one fails

The scheduled start (DRL1c, the contract fixed here): Terraform's output ``drill_autostart_id``
(``DRILL_AUTOSTART``), the resource id of a Logic App (``Microsoft.Logic/workflows``) whose one
trigger is a weekly ``Recurrence`` in UTC (``frequency: Week``, ``interval: 1``, ``timeZone: UTC``,
``schedule: {weekDays: [<day>], hours: [<h>], minutes: [<m>]}``), created ``Disabled``, its state
ignored by Terraform; enabled by the arming (``POST …/enable``), disabled by the disarming and the
kill (``POST …/disable``), api-version 2019-05-01. The Makefile reads it from
``terraform output -json`` (``autostart-id``, below), in three cases: the output absent (DRL1c not
applied), « no scheduled start »; Terraform's state unreadable (``az login``, the backend), the
sentinel ``unreadable``, an error for the kill and the disarming — never taken for absent; an id,
read. A 404 on the id: « no scheduled start ». Anything else unreadable: an error.

    python infra/orodruin/drill_ops.py check|arm|disarm
    terraform output -json | python infra/orodruin/drill_ops.py autostart-id
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from eregion_core import drill as dr  # noqa: E402
from eregion_core import drill_arming as da  # noqa: E402
from eregion_core import exercise_channel as xc  # noqa: E402

ARM = "https://management.azure.com"
LOGIC_API = "2019-05-01"
# The scheduled start wakes Orodruin this long before the drill's hour (§5.1).
LEAD_MIN = 20
SERVICE, TIMER = "eregion-drill.service", "eregion-drill.timer"
UNIT_DIR = "/etc/systemd/system"
IMAGE = "eregion-annatar:orodruin"
CONTAINER = "eregion-drill"
# As ORO_HARDEN in the Makefile: every injector's docker run on Orodruin.
HARDEN = "--read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true"
# As ORO_EXEC_HOME in the Makefile (R2BZ): the one executable tmpfs of Annatar's runs, where its
# control-plane adapter builds the run HOME (annatar/executors/stratus_host.py, EXEC_HOME) and
# Terraform executes its providers; /tmp stays noexec. The drill plays Annatar's runs only (a
# technique, never a fault in v1: eregion_core/drill.py), so its service gets it (DRL1d).
EXEC_HOME = "--tmpfs /stratus-home:exec"
# The options of the drill's docker run, those of ORO_RUN (Annatar's runs on Orodruin): ORO_HARDEN
# then ORO_EXEC_HOME, no more, no less (tests/unit/test_drill_ops.py reads them in the Makefile).
RUN_OPTS = f"{HARDEN} {EXEC_HOME}"
_LOGIC_ID = re.compile(r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[-\w._()]{1,90}/providers/"
                       r"Microsoft\.Logic/workflows/[A-Za-z0-9][A-Za-z0-9._-]{0,79}", re.ASCII)
_WEEKDAYS = {"Monday": "mon", "Tuesday": "tue", "Wednesday": "wed", "Thursday": "thu",
             "Friday": "fri", "Saturday": "sat", "Sunday": "sun"}
_USER = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
# DRL1c's output, and what the Makefile says when Terraform's state does not read.
AUTOSTART_OUTPUT = "drill_autostart_id"
UNREADABLE = "unreadable"


def az(args: list[str]) -> str:
    r = subprocess.run(["az", *args], capture_output=True, text=True)
    if r.returncode:
        last = (r.stderr.strip().splitlines() or ["no message"])[-1]
        raise RuntimeError(f"az {' '.join(args[:3])} … exit {r.returncode}: {last}")
    return r.stdout


# ── The scheduled start of DRL1c (a Logic App), by the operator's identity ───────────────

def read_autostart(logic_id: str, run: Callable = az) -> dict | None:
    """The Logic App, as ARM says it — None when there is none (no id given, or not found).
    Anything else that fails raises: unreadable, never taken for absent."""
    if not logic_id:
        return None
    if logic_id == UNREADABLE:
        raise RuntimeError("the scheduled start unreadable: Terraform's state of Orodruin did not read "
                           "(az login? make orodruin-init?) — never taken for absent; AUTOSTART=<id> to give it")
    if not _LOGIC_ID.fullmatch(logic_id):
        raise RuntimeError("DRILL_AUTOSTART is not a Logic App's resource id")
    try:
        out = run(["rest", "--method", "get", "--url", f"{ARM}{logic_id}?api-version={LOGIC_API}", "-o", "json"])
    except RuntimeError as e:
        if "ResourceNotFound" in str(e) or "Not Found" in str(e):
            return None
        raise
    doc = json.loads(out or "{}")
    if not isinstance(doc, dict):
        raise RuntimeError("the Logic App read is not an object")
    return doc


def autostart_at(workflow: dict) -> tuple[str, str]:
    """(day, HH:MM UTC) of the Logic App's one trigger — ValueError unless it is one weekly
    Recurrence in UTC, on one day, at one hour and one minute."""
    triggers = ((workflow.get("properties") or {}).get("definition") or {}).get("triggers") or {}
    if not isinstance(triggers, dict) or len(triggers) != 1:
        raise ValueError("not one trigger")
    trigger = next(iter(triggers.values()))
    if not isinstance(trigger, dict) or trigger.get("type") != "Recurrence":
        raise ValueError("its trigger is not a Recurrence")
    rec = trigger.get("recurrence") or {}
    if rec.get("frequency") != "Week" or int(rec.get("interval", 0)) != 1 or rec.get("timeZone", "UTC") != "UTC":
        raise ValueError("its recurrence is not weekly, in UTC")
    sched = rec.get("schedule") or {}
    days, hours, minutes = sched.get("weekDays") or [], sched.get("hours") or [], sched.get("minutes") or []
    if len(days) != 1 or len(hours) != 1 or len(minutes) != 1 or days[0] not in _WEEKDAYS:
        raise ValueError("its recurrence is not one day, one hour, one minute")
    h, m = int(hours[0]), int(minutes[0])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("its hour is not an hour")
    return _WEEKDAYS[days[0]], f"{h:02d}:{m:02d}"


def autostart_id(outputs: str) -> str:
    """The scheduled start's id from ``terraform output -json``: "" when the output is absent or
    null (DRL1c not applied), the id when it is one, else ``UNREADABLE`` — never an absence."""
    try:
        doc = json.loads(outputs)
    except ValueError:
        return UNREADABLE
    if not isinstance(doc, dict):
        return UNREADABLE
    if AUTOSTART_OUTPUT not in doc:
        return ""
    out = doc[AUTOSTART_OUTPUT]
    value = out.get("value") if isinstance(out, dict) else UNREADABLE
    if value is None or value == "":
        return ""
    return value if isinstance(value, str) and _LOGIC_ID.fullmatch(value) else UNREADABLE


def expected_at(schedule: dr.Schedule) -> tuple[str, str]:
    """The schedule's hour less LEAD_MIN, the day carried back across midnight."""
    total = schedule.weekday * 1440 + schedule.minutes - LEAD_MIN
    total %= 7 * 1440
    return dr.DAYS[total // 1440], f"{(total % 1440) // 60:02d}:{total % 60:02d}"


def set_autostart(logic_id: str, enabled: bool, run: Callable = az) -> None:
    run(["rest", "--method", "post", "--url",
         f"{ARM}{logic_id}/{'enable' if enabled else 'disable'}?api-version={LOGIC_API}"])


# ── The units (§2.1) ─────────────────────────────────────────────────────────────────

def units(schedule: dr.Schedule, user: str) -> dict[str, str]:
    """eregion-drill.timer and eregion-drill.service, for Orodruin's admin user (its home holds
    orodruin.env, ~/runs and ~/drill)."""
    if not _USER.fullmatch(user or ""):
        raise ValueError(f"not a user name: {user!r}")
    home = f"/home/{user}"
    mounts = " ".join(f"-v {home}/runs/{w}:/app/runs/{w}" for w in ("annatar", "gothmog", "orodruin"))
    timer = (
        "[Unit]\n"
        "Description=Eregion: the drill of the week (DRL1), armed by the operator\n\n"
        "[Timer]\n"
        f"OnCalendar={schedule.on_calendar()}\n"
        "Persistent=false\n"
        "AccuracySec=1min\n"
        f"Unit={SERVICE}\n\n"
        "[Install]\n"
        "WantedBy=timers.target\n")
    service = (
        "[Unit]\n"
        "Description=Eregion: one occurrence of the drill of the week (DRL1)\n"
        "Requires=docker.service\n"
        "After=docker.service\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={user}\n"
        f"WorkingDirectory={home}\n"
        f"ExecStartPre=-/usr/bin/docker rm -f {CONTAINER}\n"
        f"ExecStart=/usr/bin/docker run --rm --pull never --init --name {CONTAINER} {RUN_OPTS} "
        f"--env-file orodruin.env {mounts} -v {home}/drill:/app/drill:ro {IMAGE} "
        "python -m eregion_core.scheduled_drill run\n"
        f"ExecStop=-/usr/bin/docker stop --time 90 {CONTAINER}\n"
        "TimeoutStopSec=120\n"
        "RuntimeMaxSec=3600\n")
    return {TIMER: timer, SERVICE: service}


# ── Orodruin, by SSH (the host key pinned) ───────────────────────────────────────────

class Orodruin:
    """One remote command on Orodruin: ``(code, stdout, stderr)``. Never a prompt."""

    def __init__(self, ssh: str | list[str], run=subprocess.run):
        self.base = shlex.split(ssh) if isinstance(ssh, str) else list(ssh)
        if len(self.base) < 2 or self.base[0] != "ssh" or self.base[-1].endswith("@"):
            raise RuntimeError("no Orodruin to reach (DRILL_ORO_SSH: make orodruin-up, ORO_SSH_FINGERPRINT)")
        self._run = run

    def __call__(self, command: str, stdin: str | None = None) -> tuple[int, str, str]:
        argv = [*self.base[:-1], "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", self.base[-1], command]
        r = self._run(argv, input=stdin, capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout or "", r.stderr or ""


def _must(oro, command: str, what: str, stdin: str | None = None) -> str:
    code, out, err = oro(command, stdin)
    if code:
        last = (err.strip().splitlines() or [f"exit {code}"])[-1]
        raise RuntimeError(f"{what}: {last}"[:300])
    return out


DISARM_UNITS = (f"sudo -n systemctl disable --now {TIMER} >/dev/null 2>&1; "
                f"sudo -n rm -f {UNIT_DIR}/{TIMER} {UNIT_DIR}/{SERVICE} && sudo -n systemctl daemon-reload && "
                f"test ! -e {UNIT_DIR}/{TIMER} && test ! -e {UNIT_DIR}/{SERVICE}")
DISARM_FILE = "rm -f drill/armed.json && test ! -e drill/armed.json"


# ── The pulse and the permit, by the operator's identity ─────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def write_pulse(doc: dict, *, channel: str, credential=None, put=None) -> None:
    if not xc.publish_drill(xc.DRILL_BLOB, da.read_pulse(doc), channel=channel, credential=credential, put=put):
        raise RuntimeError("no exercise channel: the pulse not written")


def disarmed_pulse(reason: str, *, channel: str, credential=None, get=None, now=_now) -> dict:
    """The pulse ``disarmed (<reason>)``: the drill, its fingerprint, its last occurrence kept from
    the pulse in the channel when it reads — else said unknown (empty)."""
    keep = {}
    try:
        doc, _ = xc.read_drill(xc.DRILL_BLOB, channel=channel, credential=credential, get=get)
        if doc is not None:
            keep = da.read_pulse(doc)
    except (RuntimeError, da.ArmingRefused, OSError):
        keep = {}
    return da.pulse(state="disarmed", reason=reason, drill=keep.get("drill", ""),
                    sha256=keep.get("sha256", ""), next_at="", last=keep.get("last"),
                    image=keep.get("image", ""), at=now().isoformat())


def kill_steps(logic_id: str, *, channel: str, run: Callable = az, credential=None, get=None, put=None,
               delete=None, dry_run: bool = False, say=print, now=_now, cli: Callable | None = None,
               said: dict | None = None) -> dict:
    """The kill's three steps for the drill (§3.1), by the operator's identity: the scheduled start
    disabled, the permit removed, the pulse written ``disarmed (killed)``. Each raises on failure —
    the kill says it and goes on (eregion_core/orodruin.py ``kill``). ``cli``: the kill's own
    ``az login`` credential; ``said``: what each step did, for the kill's summary (``summary``)."""
    said = {} if said is None else said

    def cred():
        return credential or (cli or _cli_credential)()

    def disable_start() -> None:
        if dry_run:
            what = {"": "none given", UNREADABLE: "Terraform's state unreadable"}.get(logic_id, "the Logic App")
            say(f"[dry-run] disable the scheduled start ({what})")
            return
        if read_autostart(logic_id, run) is None:
            said["disable_start"] = "no scheduled start"
            say("drill: no scheduled start (DRL1c not applied, or gone)")
            return
        set_autostart(logic_id, False, run)
        said["disable_start"] = "scheduled start disabled"
        say("drill: scheduled start disabled")

    def remove_permit() -> None:
        if not channel:
            raise RuntimeError("no exercise channel given: the drill's permit was not removed")
        if dry_run:
            say("[dry-run] remove the drill's permit from the channel")
            return
        gone = xc.delete_drill(xc.PERMIT_BLOB, channel=channel, credential=cred(), delete=delete)
        said["remove_permit"] = "permit removed" if gone else "no permit in the channel"
        say(f"drill: {said['remove_permit']}")

    def disarm() -> None:
        if not channel:
            raise RuntimeError("no exercise channel given: the drill's pulse was not written")
        if dry_run:
            say("[dry-run] write the drill's pulse: disarmed (killed)")
            return
        c = cred()
        write_pulse(disarmed_pulse("killed", channel=channel, credential=c, get=get, now=now),
                    channel=channel, credential=c, put=put)
        said["disarm"] = "pulse disarmed (killed)"
        say("drill: pulse written, disarmed (killed)")

    return {"disable_start": disable_start, "remove_permit": remove_permit, "disarm": disarm}


def summary(said: dict) -> str:
    """The kill's last line for the drill, from what its steps did — never a disabling or a removal
    that did not happen (« drill: scheduled start disabled, permit removed; refused until
    re-armed » when both did)."""
    parts = [said.get("disable_start", "scheduled start not checked"),
             said.get("remove_permit", "permit not checked")]
    return f"drill: {', '.join(parts)}; refused until re-armed"


def _cli_credential():
    # The operator's own `az login`, as the kill takes it (infra/orodruin/kill.py, the adapter that
    # imports the SDK: MC0) — never DefaultAzureCredential. The kill passes its own (``cli``):
    # this import serves this script's own commands, run as __main__.
    from kill import _cli_credential as cli
    return cli()


# ── check, arm, disarm ───────────────────────────────────────────────────────────────

def _fingerprint(oro, oro_run: str, name: str) -> dict:
    out = _must(oro, f"{oro_run} python -m eregion_core.scheduled_drill fingerprint {shlex.quote(name)}",
                f"the drill {name} in Orodruin's image")
    try:
        fp = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"the drill {name} in Orodruin's image: its fingerprint does not read") from None
    if fp.get("drill") != name:
        raise RuntimeError(f"Orodruin's image read another drill than {name}")
    return fp


def _schedule(fp: dict) -> dr.Schedule:
    return dr.Schedule(fp["day"], fp["at"], int(fp["max_injections"]), int(fp["max_run_s"]))


def _autostart_refusal(logic_id: str, schedule: dr.Schedule, run: Callable) -> str:
    """Why the arming may not go on, by the scheduled start — "" when it may."""
    wf = read_autostart(logic_id, run)
    if wf is None:
        return ("no scheduled start (the Logic App of DRL1c): apply first — make orodruin-plan, then "
                "make orodruin-lock")
    try:
        day, at = autostart_at(wf)
    except (ValueError, TypeError) as e:
        return f"the scheduled start's trigger does not read ({e}): apply first"
    want = expected_at(schedule)
    if (day, at) != want:
        return (f"the scheduled start wakes Orodruin {day} {at} UTC, not {want[0]} {want[1]} (the drill's "
                f"{schedule.day} {schedule.at} less {LEAD_MIN} min): apply first")
    return ""


def check(name: str, targets: list[str], *, oro, oro_run: str, logic_id: str, run: Callable = az,
          say=print) -> int:
    """orodruin-drill-check: nothing written. Exit 0 when the next occurrence would play."""
    ok = True
    try:
        fp = _fingerprint(oro, oro_run, name)
        say(f"✓ the drill {name} in Orodruin's image: {fp['sha256'][:12]}…, {fp['day']} {fp['at']} UTC")
        why = _autostart_refusal(logic_id, _schedule(fp), run)
        say(f"{'✗' if why else '✓'} scheduled start: {why or 'its hour is the drill less 20 min'}")
        ok = not why
    except RuntimeError as e:
        say(f"✗ {e}")
        return 1
    code, out, _ = oro("test -f drill/armed.json && head -c 16384 drill/armed.json")
    if code:
        say("· arming: none on Orodruin (make orodruin-drill-arm)")
    else:
        try:
            armed = da.read_armed(json.loads(out))
            same = armed["drill"] == name and armed["sha256"] == fp["sha256"]
            say(f"{'✓' if same else '✗'} arming: {armed['drill']} on {', '.join(armed['targets'])}, "
                f"armed {armed['armed_at']}" + ("" if same else " — not this drill as the image holds it: "
                                                "drill_changed until re-armed"))
            ok = ok and same
            targets = targets or armed["targets"]
        except (ValueError, da.ArmingRefused) as e:
            say(f"✗ arming unreadable: {e}")
            ok = False
    args = f" --targets {shlex.quote(','.join(targets))}" if targets else ""
    code, out, err = oro(f"{oro_run} python -m eregion_core.scheduled_drill check {shlex.quote(name)}{args}")
    for line in (out or err).strip().splitlines():
        say(f"  {line}")
    return 0 if ok and code == 0 else 1


def arm(name: str, targets: list[str], *, oro, oro_run: str, user: str, logic_id: str, channel: str,
        run: Callable = az, credential=None, put=None, now=_now, say=print) -> int:
    """orodruin-drill-arm: refused before anything is written unless the drill reads in Orodruin's
    image and the scheduled start is there, at the drill's hour less 20 min. Then each step said."""
    if not channel:
        say("✗ no exercise channel (EREGION_EXERCISE_CHANNEL): the permit could not be written — nothing armed")
        return 1
    try:
        fp = _fingerprint(oro, oro_run, name)
        schedule = _schedule(fp)
        why = _autostart_refusal(logic_id, schedule, run)
    except RuntimeError as e:
        say(f"✗ {e} — nothing armed")
        return 1
    if why:
        say(f"✗ {why} — nothing armed")
        return 1
    code, image, _ = oro("head -c 200 .eregion-image 2>/dev/null")
    image = " ".join(image.split()) if code == 0 else ""
    try:
        armed = da.read_armed({"drill": name, "sha256": fp["sha256"], "targets": list(targets),
                               "armed_at": now().isoformat(timespec="seconds"), "image": image})
        unit_text = units(schedule, user)
    except (da.ArmingRefused, ValueError) as e:
        say(f"✗ {e} — nothing armed")
        return 1
    cred = credential or _cli_credential()
    steps = [
        ("the arming written (~/drill/armed.json, mode 600)", lambda: _must(
            oro, "umask 077 && mkdir -p drill && chmod 700 drill && cat > drill/.armed.json.tmp && "
                 "mv -f drill/.armed.json.tmp drill/armed.json", "the arming", json.dumps(armed, indent=2))),
        ("the runs' directories (never a link, SEC18)", lambda: _must(
            oro, 'for d in runs/annatar runs/gothmog runs/orodruin; do { test ! -L "$d" && { test ! -e "$d" '
                 '|| test -d "$d"; }; } || exit 3; mkdir -p "$d"; done', "the runs' directories")),
        (f"the units posed ({TIMER}: {schedule.on_calendar()})", lambda: [
            _must(oro, f"sudo -n tee {UNIT_DIR}/{unit} >/dev/null", unit, text) for unit, text in unit_text.items()]),
        ("the timer enabled", lambda: _must(oro, f"sudo -n systemctl daemon-reload && sudo -n systemctl enable --now {TIMER}",
                                            "the timer")),
        ("the permit written (orodruin/drill-permit.json)", lambda: xc.publish_drill(
            xc.PERMIT_BLOB, da.permit_of(armed), channel=channel, credential=cred, put=put)),
        ("the scheduled start enabled", lambda: set_autostart(logic_id, True, run)),
        ("the pulse written: armed", lambda: write_pulse(da.pulse(
            state="armed", drill=name, sha256=fp["sha256"], next_at=schedule.next(now()).isoformat(),
            image=image, at=now().isoformat()), channel=channel, credential=cred, put=put)),
    ]
    for what, step in steps:
        try:
            step()
        except Exception as e:
            say(f"✗ {what}: {e}"[:400])
            say("  the arming is partial: make orodruin-drill-disarm, then arm again")
            return 1
        say(f"✓ {what}")
    say(f"armed: {name} on {', '.join(targets)} — next {schedule.next(now()).isoformat(timespec='minutes')}; "
        "make orodruin-drill-disarm, or make orodruin-kill")
    return 0


def disarm(*, oro, logic_id: str, channel: str, run: Callable = az, credential=None, get=None, put=None,
           delete=None, now=_now, say=print, unreached: str = "") -> int:
    """orodruin-drill-disarm: every step tried and said; exit 1 when one fails. Orodruin not
    reached (``oro`` None: stopped, no address, its host key not verified — ``unreached`` says
    why): its two steps said missed, the permit and the scheduled start still done by the
    operator's identity — an occurrence then refuses (``no_permit``), whenever Orodruin wakes."""
    failures = 0
    cred = None

    def on_orodruin(command: str, what: str):
        def step():
            if oro is None:
                raise RuntimeError(f"Orodruin not reached ({unreached or 'no address'}): missed — it stays "
                                   "on its disk; disarm again once Orodruin is up")
            _must(oro, command, what)
        return step

    def creds():
        nonlocal cred
        cred = cred or credential or _cli_credential()
        return cred

    def autostart() -> str:
        if read_autostart(logic_id, run) is None:
            return "no scheduled start"
        set_autostart(logic_id, False, run)
        return "scheduled start disabled"

    def permit() -> str:
        if not channel:
            raise RuntimeError("no exercise channel: the permit not removed")
        gone = xc.delete_drill(xc.PERMIT_BLOB, channel=channel, credential=creds(), delete=delete)
        return "permit removed" if gone else "no permit in the channel"

    def pulse() -> str:
        if not channel:
            raise RuntimeError("no exercise channel: the pulse not written")
        write_pulse(disarmed_pulse("operator", channel=channel, credential=creds(), get=get, now=now),
                    channel=channel, credential=creds(), put=put)
        return "pulse written: disarmed"

    steps = [
        ("the timer disabled, its units removed", on_orodruin(DISARM_UNITS, "the units")),
        ("the arming removed", on_orodruin(DISARM_FILE, "the arming")),
        ("the permit", permit),
        ("the scheduled start", autostart),
        ("the pulse", pulse),
    ]
    for what, step in steps:
        try:
            said = step()
        except Exception as e:
            failures += 1
            say(f"✗ {what}: {e}"[:400])
            continue
        say(f"✓ {what}" + (f": {said}" if said else ""))
    say("an occurrence running now runs to its end: make orodruin-kill stops it")
    if failures:
        say(f"✗ disarming INCOMPLETE: {failures} step(s) failed — above")
        return 1
    say("disarmed")
    return 0


def session_refusal(env, cwd: str | None = None, here: str | None = None) -> str:
    """Why this runs in a code session — '' when it does not (§6.1: no session arms, triggers nor
    re-arms the drill). A lot's session carries EREGION_AGENT_SESSION, or works in a worktree of
    .claude/worktrees/ — as its directory, or as the checkout this script runs from (the rule of
    scripts/bench_shared.py, ``session_refusal``)."""
    if env.get("EREGION_AGENT_SESSION"):
        return "a code session (EREGION_AGENT_SESSION) never arms the drill: Jonathan arms it"
    for where in (Path(cwd or os.getcwd()), Path(here or Path(__file__).resolve().parents[2])):
        parts = where.resolve().parts
        if ".claude" in parts and "worktrees" in parts[parts.index(".claude"):]:
            return "a lot's worktree (.claude/worktrees/) never arms the drill: Jonathan arms it"
    return ""


def main(argv: list[str] | None = None, env=None, cwd: str | None = None, here: str | None = None) -> int:
    env = os.environ if env is None else env
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["autostart-id"]:
        print(autostart_id(sys.stdin.read()))
        return 0
    if len(args) != 1 or args[0] not in ("check", "arm", "disarm"):
        print(__doc__)
        return 2
    cmd = args[0]
    if cmd == "arm" and (why := session_refusal(env, cwd, here)):
        print(f"✗ {why} — nothing armed", file=sys.stderr)
        return 1
    name = env.get("EREGION_DRILL", "") or ("banc-hebdo" if cmd == "check" else "")
    if cmd != "disarm" and not dr.valid_name(name):
        print(f"✗ DRILL={name!r}: a drill's name (a-z, 0-9, '-') — nothing done", file=sys.stderr)
        return 1
    unreached = env.get("DRILL_ORO_UNREACHED", "").strip()
    try:
        raw = env.get("EREGION_DRILL_TARGETS", "")
        targets = da.parse_targets(raw) if (cmd == "arm" or raw.strip()) else []
        oro = None if (cmd == "disarm" and unreached) else Orodruin(env.get("DRILL_ORO_SSH", ""))
    except RuntimeError as e:
        if cmd != "disarm":
            print(f"✗ {e} — nothing done", file=sys.stderr)
            return 1
        # The disarming does what needs no Orodruin: the permit, the scheduled start, the pulse.
        oro, unreached = None, unreached or "no address: make orodruin-start"
    except da.ArmingRefused as e:
        print(f"✗ {e} — nothing done", file=sys.stderr)
        return 1
    oro_run = env.get("DRILL_ORO_RUN", "")
    logic_id = env.get("DRILL_AUTOSTART", "").strip()
    channel = env.get("DRILL_CHANNEL", "").strip()
    if cmd == "check":
        return check(name, targets, oro=oro, oro_run=oro_run, logic_id=logic_id)
    if cmd == "arm":
        return arm(name, targets, oro=oro, oro_run=oro_run, user=env.get("DRILL_ORO_USER", ""),
                   logic_id=logic_id, channel=channel)
    return disarm(oro=oro, logic_id=logic_id, channel=channel, unreached=unreached)


if __name__ == "__main__":
    sys.exit(main())
