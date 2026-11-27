"""A VM the reassertion skips because its lock is held (SEC-H): said, never silent.

A write runs on the VM (a release from the console, an isolation and its drain): the pass skips it
and reads it at the next one. Skipped pass after pass — a writer stuck behind an Azure that does not
answer —, the VM is no longer checked at all, and nothing said it. Each skip is in the pass's report;
from the GLORFINDEL_REASSERT_SKIPS_SAID-th in a row (5 by default), one card per VM (and IP) says
it. Counted in this process: a restart counts again.

Closed at the end of the first pass that reads the VM again, or no longer has it to read — lifted or
unblocked while skipped (RSM6) —, never while it is still skipped: `settle`, read from the card store,
not from the count in memory — a restart left the card pending, the count at 0, and a VM lifted was
never read again, its card pending till the operator acknowledged it.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_SKIPPED: dict[str, int] = {}
_PREFIX = "reassert-busy-"
_PASS: dict[str, set[str]] = {"skipped": set(), "read": set()}     # this pass's, till `settle`


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
    _PASS["skipped"].add(sid)
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
                             "la carte se ferme à la première passe qui relit la VM, ou qui ne l'a plus à "
                             "relire (levée, débloquée)."],
            severity="high", action_params={"ip": ip} if ip else None)
    except Exception as exc:                    # said again at the next pass past the count
        log.warning("reassert: skip card not recorded (%s)", exc)
        _SKIPPED[sid] = n - 1
    finally:
        from glorfindel.reassert_cards import new_pass
        new_pass()                              # the pass's cache of its cards read again (`settle`)


def read(vm: str, rid: str, ip: str = "") -> None:
    """The VM read by the pass: its run of skips over; its card, if any, closed by `settle` at the end of
    the pass. Never raises."""
    sid = _sid(vm, rid, ip)
    _SKIPPED.pop(sid, None)
    _PASS["read"].add(sid)


def settle() -> None:
    """The end of a pass: every card « sautée » closed unless its VM was skipped by this pass — read again,
    whatever this process counted (a restart), or no longer recorded (lifted, unblocked while skipped: no
    pass reads it again). Not while a state can't be read: what it holds is unknown (SEC4b), as the card
    of a VM gone. A run of skips not continued by this pass is over: a VM lifted, isolated again later,
    counts from one. Never raises."""
    skipped_now, read_now = set(_PASS["skipped"]), set(_PASS["read"])
    for kind in _PASS.values():
        kind.clear()
    for sid in [s for s in _SKIPPED if s not in skipped_now]:
        _SKIPPED.pop(sid, None)
    try:
        from glorfindel.actions import unreadable_states
        from glorfindel.reassert_cards import _history, _resolve
        from glorfindel.reassert_gone import LIFTED
        unread = None
        for e in _history():
            sid = (e.get("signal_id") or "").lower()
            if not sid.startswith(_PREFIX) or e.get("status") != "pending" or sid in skipped_now:
                continue
            if sid in read_now:
                _resolve(e["id"], note="La réaffirmation relit la VM de nouveau.")
                continue
            unread = bool(unreadable_states()) if unread is None else unread
            if not unread:
                _resolve(e["id"], note=LIFTED)        # lifted or unblocked while skipped (RSM6)
    except Exception as exc:
        log.warning("reassert: skip cards not settled (%s)", exc)
