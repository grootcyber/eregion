"""The drill of the week's three small documents (DRL1, docs/design/drill-banc.md §2.1, §2.4, §4.1):
each with its one reader, exact (no field more, none of the wrong kind), shared by Orodruin
(eregion_core/scheduled_drill.py), the operator's machine (infra/orodruin/drill_ops.py, the kill)
and, later, Imladris (DRL1b).

- **The arming** (``~/drill/armed.json`` on Orodruin's disk, mode 600, mounted read-only into the
  drill's container): the drill's name and fingerprint read in the image at the arming, the names of
  its targets (never ``all``), the time of the arming, the image's commit. No identifier, no secret.
- **The permit** (``orodruin/drill-permit.json`` in the exercise channel): written by the operator at
  the arming, removed by the disarming and the kill; the drill, its fingerprint, the time of the
  arming — the arming's own, nothing else. Its absence closes.
- **The pulse** (``orodruin/drill.json``): armed or disarmed and why, the drill and its fingerprint,
  the next occurrence, the last one (its time, its state, its code, its request), the image's
  commit. Written by Orodruin at each occurrence, refused included; by the operator at the arming,
  the disarming and the kill.

D1: the shared core — no Azure, no channel here; the readers only.
"""
from __future__ import annotations

import re
from datetime import datetime

from eregion_core.orodruin import CEILING_INJECTIONS

ARMED_FIELDS = ("drill", "sha256", "targets", "armed_at", "image")
PERMIT_FIELDS = ("drill", "sha256", "armed_at")
PULSE_FIELDS = ("state", "reason", "drill", "sha256", "next", "last", "image", "at")
LAST_FIELDS = ("at", "occurrence", "state", "code", "request")
STATES = ("armed", "disarmed")
# Why the drill is disarmed: by the operator (make orodruin-drill-disarm), by the kill, or because
# the image holds another drill than the one armed (a release changed it: re-arm).
REASONS = ("", "operator", "killed", "drill_changed")
LAST_STATES = ("refused", "skipped", "played", "failed", "stopped")
MAX_BYTES = 16 * 1024

_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_VM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_CODE = re.compile(r"[a-z][a-z0-9_]{0,39}")
_REQUEST = re.compile(r"r-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{6}")
# The image's commit as ~/.eregion-image says it on Orodruin (« commit digest », « dev <sha> »):
# printable ASCII, short — said, never trusted.
_IMAGE = re.compile(r"[A-Za-z0-9 :@._-]{0,200}")


class ArmingRefused(ValueError):
    """A document of the drill the one reader does not take: why, in a sentence."""


def _exact(doc, fields: tuple[str, ...], what: str) -> None:
    if not isinstance(doc, dict):
        raise ArmingRefused(f"{what} is not an object")
    extra = sorted(str(k) for k in set(doc) - set(fields))
    if extra:
        raise ArmingRefused(f"{what} carries a field it never holds: {', '.join(extra)}")
    missing = [f for f in fields if f not in doc]
    if missing:
        raise ArmingRefused(f"{what} lacks {', '.join(missing)}")


def _time(value, what: str, empty: bool = False) -> None:
    if empty and value == "":
        return
    try:
        when = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        when = None
    if when is None or when.tzinfo is None:
        raise ArmingRefused(f"{what} is not an ISO time with its zone")


def _drill(doc, what: str, empty: bool = False) -> None:
    if not (empty and doc["drill"] == "") and (not isinstance(doc["drill"], str) or not _NAME.fullmatch(doc["drill"])):
        raise ArmingRefused(f"{what}: its drill is not a drill's name")
    if not (empty and doc["sha256"] == "") and (not isinstance(doc["sha256"], str) or not _SHA256.fullmatch(doc["sha256"])):
        raise ArmingRefused(f"{what}: its fingerprint is not a sha256")


def parse_targets(value) -> list[str]:
    """The targets an arming names (``TARGETS=``): VM names, separated by commas, at least one —
    never ``all`` (§1.3: a VM enrolled later would become a target without a gesture), never twice."""
    names = [n.strip() for n in str(value or "").split(",") if n.strip()]
    if not names:
        raise ArmingRefused("TARGETS: name the drill's VMs (TARGETS=<vm>[,<vm>…]) — never empty")
    if any(n.lower() == "all" for n in names):
        raise ArmingRefused("TARGETS=all is refused for an armed drill: a VM enrolled later would become "
                            "a target without a gesture — name its VMs")
    _targets(names)
    return names


def _targets(names) -> None:
    if not isinstance(names, list) or not 1 <= len(names) <= CEILING_INJECTIONS:
        raise ArmingRefused(f"its targets are not a list of 1 to {CEILING_INJECTIONS} VM names")
    for n in names:
        if not isinstance(n, str) or not _VM_NAME.fullmatch(n) or n.lower() == "all":
            raise ArmingRefused(f"its targets: {n!r} is not a VM's name (never all)")
    if len({n.lower() for n in names}) != len(names):
        raise ArmingRefused("its targets name a VM twice")


def read_armed(doc) -> dict:
    """The arming, or ``ArmingRefused``."""
    _exact(doc, ARMED_FIELDS, "the arming")
    _drill(doc, "the arming")
    _targets(doc["targets"])
    _time(doc["armed_at"], "the arming's time")
    if not isinstance(doc["image"], str) or not _IMAGE.fullmatch(doc["image"]):
        raise ArmingRefused("the arming's image is not a commit as Orodruin says it")
    return doc


def read_permit(doc) -> dict:
    """The permit, or ``ArmingRefused``."""
    _exact(doc, PERMIT_FIELDS, "the permit")
    _drill(doc, "the permit")
    _time(doc["armed_at"], "the permit's time")
    return doc


def permit_of(armed: dict) -> dict:
    """The permit an arming writes: its drill, its fingerprint, its time — nothing else (no target,
    no identifier)."""
    return {"drill": armed["drill"], "sha256": armed["sha256"], "armed_at": armed["armed_at"]}


def read_pulse(doc) -> dict:
    """The pulse, or ``ArmingRefused``. A disarmed pulse whose drill is not known (written by a kill
    that could not read the last one) carries an empty drill and fingerprint."""
    _exact(doc, PULSE_FIELDS, "the drill's pulse")
    if doc["state"] not in STATES:
        raise ArmingRefused(f"the drill's pulse: its state is not one of {', '.join(STATES)}")
    if doc["reason"] not in REASONS or (doc["state"] == "armed") != (doc["reason"] == ""):
        raise ArmingRefused("the drill's pulse: armed without a reason, disarmed with one of "
                            + ", ".join(r for r in REASONS if r))
    _drill(doc, "the drill's pulse", empty=doc["state"] == "disarmed")
    _time(doc["next"], "the drill's next occurrence", empty=True)
    _time(doc["at"], "the drill's pulse's time")
    if not isinstance(doc["image"], str) or not _IMAGE.fullmatch(doc["image"]):
        raise ArmingRefused("the drill's pulse: its image is not a commit as Orodruin says it")
    last = doc["last"]
    if last is not None:
        _exact(last, LAST_FIELDS, "the drill's last occurrence")
        _time(last["at"], "the last occurrence's time")
        _time(last["occurrence"], "the last occurrence's planned time", empty=True)
        if last["state"] not in LAST_STATES:
            raise ArmingRefused(f"the last occurrence's state is not one of {', '.join(LAST_STATES)}")
        if not isinstance(last["code"], str) or (last["code"] and not _CODE.fullmatch(last["code"])):
            raise ArmingRefused("the last occurrence's code is not a code")
        if not isinstance(last["request"], str) or (last["request"] and not _REQUEST.fullmatch(last["request"])):
            raise ArmingRefused("the last occurrence's request is not a request id")
    return doc


def pulse(*, state: str, reason: str = "", drill: str = "", sha256: str = "", next_at: str = "",
          last: dict | None = None, image: str = "", at: str) -> dict:
    """A pulse, passed through ``read_pulse`` like any other."""
    return read_pulse({"state": state, "reason": reason, "drill": drill, "sha256": sha256,
                       "next": next_at, "last": last, "image": image, "at": at})
