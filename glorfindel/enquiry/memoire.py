"""The enquiry's memory per object, in the watch (ENQ5b, #1284; `docs/design/enquete-raisonnee.md` §5.5): what
the last enquiry on the same VM and the same rule read, the decision it led to, and — read on its card when
the next enquiry comes — the human verdict. The form is ENQ4's (`reference.py`); here, where it is kept.

- **Where**: ``~/.glorfindel/enquiry/references/<key>.json`` (`DOSSIER`), one file per object, its key the
  sha256 of the VM's resource id (lowercase, as Azure compares them) and of the rule — written whole and
  atomically by the watch alone, 0600 in a folder 0700 (SEC13), read never through a link (SEC16).
- **Written at the end of the cycle** (`retenir`, from `store_cycle`): the reads of this enquiry, bounded
  (`reference.trace`), the decision as it stood, the signal's id. The next enquiry on the object replaces
  it: it never accumulates, and changes no state of the base.
- **Read for its own object only** (`lire`): the file of this VM and this rule, and in it this VM and this
  rule again — a file whose content names another object is never shown, whatever its name. Then the
  loop's bounds (`reference.montrable`: dated, not in the future, 30 days at most).
- **The human verdict** is the card's (`memory_keys.card_verdicts`, MEM2b's reading of the cards' store), by
  the signal of the reference's cycle, read when the next enquiry comes — never written in the file: a
  verdict comes after the decision. Only what reads one way: judged right, a decision that did nothing is a
  false alarm (`benin`), one that responded a real attack (`malveillant`); judged wrong, a decision that did
  nothing left a threat (`malveillant`). Judged wrong after a response (a false alarm, or a response out of
  proportion: MEM2b's words) and `unsure` give no verdict: « as usual » is never received on them.

Rule 1 and rule 2 (§5.5) are the loop's: the reference never fills a read of today, and « as usual » is
received only on a human verdict « benign », never on a grave technique.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from glorfindel.enquiry import catalog
from glorfindel.enquiry import reference as ref_

_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
TAILLE_MAX = 64 * 1024            # a reference is a few kilobytes: a larger file is not one


def dossier() -> Path:
    """Read at call time: the throwaway HOME of the tests, the watch's own."""
    return Path.home() / ".glorfindel" / "enquiry" / "references"


def cle(vm: str, regle: str) -> str:
    """The object's key: its VM (lowercase) and its rule — 128 bits, never a name."""
    return hashlib.sha256(f"{str(vm).rstrip('/').lower()}\n{regle}".encode()).hexdigest()[:32]


def _chemin(vm: str, regle: str, root: Path | None) -> Path:
    return (root or dossier()) / f"{cle(vm, regle)}.json"


def ecrire(ref: ref_.Reference, signal_id: str, *, root: Path | None = None) -> Path:
    """`ref` on its object's file, with the signal of its cycle — replacing the last one."""
    from glorfindel.response.state_files import _atomic_write_text
    path = _chemin(ref.vm, ref.regle, root)
    data = {"vm": ref.vm, "regle": ref.regle, "date": ref.date.isoformat(), "decision": ref.decision,
            "signal_id": str(signal_id or "")[:200],
            "lectures": [{"id": t.id, "etat": t.etat, "lignes": [dict(row) for row in t.lignes]} for t in ref.lectures]}
    _atomic_write_text(path, json.dumps(data, ensure_ascii=False))
    return path


def _lu(path: Path) -> dict | None:
    try:
        fd = os.open(path, _FLAGS)
    except OSError:                                # absent, a link in its place (ELOOP): nothing shown
        return None
    with os.fdopen(fd, "rb") as f:
        raw = f.read(TAILLE_MAX + 1)
    if len(raw) > TAILLE_MAX:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def verdict_humain(verdict: dict | None, action: str) -> str:
    """The card's verdict, as a reference reads it (the module's docstring): `benin`, `malveillant`, or ""."""
    from glorfindel.memory_keys import RESPONSES
    if not isinstance(verdict, dict):
        return ""
    acted = str(verdict.get("action") or action or "") in RESPONSES
    if verdict.get("verdict") == "right":
        return ref_.MALVEILLANT if acted else ref_.BENIN
    if verdict.get("verdict") == "wrong" and not acted:
        return ref_.MALVEILLANT
    return ""


def lire(vm: str, regle: str, *, now: datetime, verdicts=None, root: Path | None = None) -> ref_.Reference | None:
    """The last enquiry on this object — this VM, this rule —, with its human verdict, or None: no file, a
    file that does not read, a file that names another object, or one the loop's bounds do not show."""
    if not vm or not regle:
        return None
    data = _lu(_chemin(vm, regle, root))
    if data is None or str(data.get("vm", "")).rstrip("/").lower() != str(vm).rstrip("/").lower() \
            or data.get("regle") != regle:
        return None
    try:
        ref = ref_.lire_dict(data)
    except ValueError:
        return None
    try:
        judged = (verdicts or _verdicts)().get(str(data.get("signal_id") or ""))
    except Exception:                              # the cards do not read: no verdict, never « benign »
        judged = None
    ref = dataclasses.replace(ref, verdict_humain=verdict_humain(judged, ref.decision))
    return ref_.montrable(ref, vm=vm, regle=regle, now=now)


def _verdicts() -> dict:
    from glorfindel.memory_keys import card_verdicts
    return card_verdicts()


def retenir(state: dict, *, root: Path | None = None, now: datetime | None = None) -> Path | None:
    """At the end of the cycle (`store_cycle`): this enquiry on its object — its VM the registry's (none on
    a detection attributed to none: nothing kept), its rule — and the decision as it stood."""
    from glorfindel.enquiry.production import lectures_de
    signal, enquete = state.get("signal") or {}, state.get("enquete") or {}
    ctx = signal.get("context") or {}
    vm = "" if ctx.get("attribution") == "unattributed" else str(signal.get("resource_id") or "")
    regle = str(enquete.get("regle") or ctx.get("rule_name") or "")
    if not vm or not regle:
        return None
    lectures = [lu for lu in lectures_de(enquete).values() if lu.etat in catalog.ETATS]
    ref = ref_.depuis(lectures, vm=vm, regle=regle, date=now or datetime.now(timezone.utc),
                      decision=str(state.get("action") or "")[:60])
    return ecrire(ref, signal.get("signal_id", ""), root=root)
