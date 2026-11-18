"""A VM the reassertion skips because its lock is held (SEC-H): said, never silent.

A write runs on the VM (a release from the console, an isolation and its drain): the pass skips it
and reads it at the next one. Skipped pass after pass — a writer stuck behind an Azure that does not
answer —, the VM is no longer checked at all, and nothing said it. Each skip is in the pass's report;
from the GLORFINDEL_REASSERT_SKIPS_SAID-th in a row (5 by default), one card per VM (and IP) says
it, closed at the first pass that reads the VM again. Counted in this process: a restart counts again.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_SKIPPED: dict[str, int] = {}
_PREFIX = "reassert-busy-"


def skips_said() -> int:
    try:
        value = int(os.environ.get("GLORFINDEL_REASSERT_SKIPS_SAID") or 5)
    except ValueError:
        return 5
    return value if value > 0 else 5


def _sid(vm: str, rid: str, ip: str = "") -> str:
    from glorfindel.actions import _rid_hash
    return (f"{_PREFIX}{vm}-{_rid_hash(rid)}" + (f"-{ip}" if ip else "")).lower()


def skipped(report: list[dict], vm: str, rid: str, ip: str = "") -> None:
    """This VM (this block) skipped by the pass: in its report, and on a card once skipped
    `skips_said()` passes in a row. Never raises: the pass goes on."""
    sid = _sid(vm, rid, ip)
    n = _SKIPPED[sid] = _SKIPPED.get(sid, 0) + 1
    what = f"le blocage de {ip} sur {vm}" if ip else f"l'isolation de {vm}"
    detail = (f"{what} non vérifiée : une écriture tient la VM ({n} passe(s) de suite) — relue à la "
              "passe suivante")
    report.append({"kind": "block" if ip else "isolation", "vm": vm, **({"ip": ip} if ip else {}),
                   "outcome": "skipped", "detail": detail})
    if n != skips_said():
        return
    try:
        from glorfindel import escalations
        if any(e.get("signal_id") == sid for e in escalations.pending()):
            return
        escalations.record(
            signal_id=sid, resource_id=rid, action="reassert_skipped", escalation_type="verification_failed",
            reason=(f"Réaffirmation sautée {n} passes de suite : {what} n'est plus vérifiée, une écriture "
                    "tient la VM depuis (une levée, une isolation, un blocage qui attend Azure). Ce que "
                    "la VM porte sur Azure n'est pas relu tant que ça dure."),
            suggested_steps=["Lire ce que la watch, la console ou la CLI font sur cette VM (leurs journaux).",
                             "Une écriture bloquée sur Azure tombe d'elle-même (GLORFINDEL_ARM_WRITE_TIMEOUT_S) ; "
                             "la carte se ferme à la première passe qui relit la VM."],
            severity="high", action_params={"ip": ip} if ip else None)
    except Exception as exc:                    # said again at the next pass past the count
        log.warning("reassert: skip card not recorded (%s)", exc)
        _SKIPPED[sid] = n - 1


def read(vm: str, rid: str, ip: str = "") -> None:
    """The VM read by the pass: its count over, its card closed. Never raises."""
    sid = _sid(vm, rid, ip)
    if _SKIPPED.pop(sid, 0) < skips_said():
        return
    try:
        from glorfindel import escalations
        for e in escalations.pending():
            if e.get("signal_id") == sid:
                escalations.resolve(e["id"], note="La réaffirmation relit la VM de nouveau.")
    except Exception as exc:
        log.warning("reassert: skip card not closed (%s)", exc)
