"""The session drain followed past its first wait (DRN1, #677): one step of the reassertion's pass.

On the bench, 09/11, the drain of an autonomous isolation ran 302 s on Azure under the quarantine;
the watch waited 300 s, read an empty output and declared the isolation unverified, while the NSG
held and the cut succeeded 2 s later. The choice, said in docs/glorfindel.md: **the isolation is
verified on the NSG, as it already was; the drain is followed apart.** The VM's worker waits 300 s,
as before (a longer wait would hold every later signal of that VM, and the reassertion's thread
when it puts an isolation back); past it the drain is `pending` (providers/azure/run_command.py),
the cycle stored with the rules' verdict and the drain said pending (response/policy.py
`isolation_verdict`). Every pass (GLORFINDEL_REASSERT_INTERVAL_S) reads its status again on Azure,
through the poller the watch kept, under the VM's lock:

- still running: one card « coupure en attente » (`drain_pending`, action `review_drain`) — no
  decision, nothing to approve;
- ended, the sessions cut: that card closes, with a note — the isolation verified;
- refused, failed, sessions left open: a `verification_failed` card on `isolate_vm`, whose reason
  says « coupure refusée » or « sessions restées ouvertes » (`policy.drain_said`), the pending card
  closed in the same write;
- still running DRAIN_DEADLINE_S after it was asked, or no longer followed — the watch restarted
  and lost its poller, or another process isolated the VM (`glorfindel respond`: the state's
  `asked_at`, the drain's nonce, is not the poller's): « coupure jamais aboutie », the sessions
  « peut-être pas coupées », on the same kind of card.

The card first, then the state (L1A): the outcome said, the state takes it (`drain`,
`drain_ended_at`) and the poller is dropped; a card refused (a full disk), the state still says
pending and the poller is read again at the next pass. A VM released (or isolated again with a
drain that ended) while its card waits: the card closes, said, and its poller is dropped. The
reassertion off (`GLORFINDEL_REASSERT_INTERVAL_S=0`): nothing reads a pending drain again — the
cycle's verdict says it then (« coupure en attente, non suivie »: `policy.isolation_verdict`).
A restart loses the poller: said as never ended, though the cut may have succeeded — the activity
log tells.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Past this after it was asked, a drain still running is said never to have ended: 302 s measured
# once under the quarantine (09/11), and the guest agent held 15 min 45 at a boot under it — the
# cause not told apart (rules 110 and 111, a decision of Jonathan's). Run Command itself stops at
# 90 min on Azure.
DRAIN_DEADLINE_S = 1800.0
PENDING_TYPE = "drain_pending"
PENDING_ACTION = "review_drain"
_LOCK_WAIT_S = 30


def drain_sid(vm: str, rid: str) -> str:
    """The id of the drain's cards on a VM: one per VM, its whole id in it (I3C), lowercase. Its
    separator, `:`, is never in an Azure VM's name: a card of the reassertion on a VM named
    `drain-web` (`reassert-drain-web-<hash>`) is never one of these (DRN1 review)."""
    from glorfindel.actions import _rid_hash
    from glorfindel.escalations import _DRAIN_FOLLOW
    return f"{_DRAIN_FOLLOW}{vm}-{_rid_hash(rid)}".lower()


def _when(value) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def follow_drains(connector, report: list[dict]) -> None:
    """Read again on Azure every drain an isolation state records `pending`; say what it became.
    Never raises: a drain not read this pass is read at the next."""
    if getattr(connector, "dry_run", False) is True:
        return
    try:
        _follow_all(connector, report)
    except Exception as exc:                       # the reassertion's pass goes on
        log.warning("drain: follow failed (%s)", exc)
        report.append({"kind": "drain", "vm": "?", "outcome": "failed", "detail": f"suivi des coupures en erreur : {exc}"})


def _follow_all(connector, report: list[dict]) -> None:
    from glorfindel.actions import _vm_lock, active_isolations
    from glorfindel.reassert_cards import unrecorded
    waiting = set()
    for snap in active_isolations():
        drain = snap.get("drain")
        if not isinstance(drain, dict) or drain.get("status") != "pending":
            continue
        vm, rid = snap["vm_name"], snap["resource_id"]
        try:
            with _vm_lock(vm, timeout=_LOCK_WAIT_S):
                if _follow_one(connector, vm, rid, report):
                    waiting.add(drain_sid(vm, rid))
        except TimeoutError:
            waiting.add(drain_sid(vm, rid))       # a write runs on this VM: next pass
        except OSError as exc:
            waiting.add(drain_sid(vm, rid))
            report.append(unrecorded(vm, exc))
    _close_the_others(connector, waiting, report)
    # A poller this process keeps for a VM whose state no longer waits for it (released, the state
    # lost): dropped, never read later as another drain's outcome.
    followed = getattr(connector, "followed_drains", None)
    for rid in (followed() if callable(followed) else []):
        _drop_if_not_pending(connector, rid)


def _drop_if_not_pending(connector, rid: str) -> None:
    """Under the VM's lock (an isolation running holds it: its drain is asked before its state is
    written), the poller dropped when the state no longer waits for a drain."""
    from glorfindel.actions import _isolation_unreadable, _load_isolation_state, _vm_lock
    drop = getattr(connector, "drop_drain", None)
    if not callable(drop) or not rid:
        return
    try:
        with _vm_lock(rid.rstrip("/").rsplit("/", 1)[-1], timeout=_LOCK_WAIT_S):
            if _isolation_unreadable(rid):
                return
            drain = (_load_isolation_state(rid) or {}).get("drain")
            if not isinstance(drain, dict) or drain.get("status") != "pending":
                drop(rid)
    except TimeoutError:
        return


def _follow_one(connector, vm: str, rid: str, report: list[dict]) -> bool:
    """One pending drain, under its VM's lock; True while it still runs."""
    from glorfindel.actions import _load_isolation_state, _save_isolation_state
    state = _load_isolation_state(rid)
    drain = (state or {}).get("drain")
    drop = getattr(connector, "drop_drain", None)
    drop = drop if callable(drop) else (lambda _rid: None)
    if not isinstance(drain, dict) or drain.get("status") != "pending":
        drop(rid)                                 # released, or ended, meanwhile
        return False
    follow = getattr(connector, "follow_drain", None)
    # The drain the state waits for, by its nonce: another process's (`glorfindel respond`) is not
    # this poller's (DRN1 review).
    got = follow(rid, asked_at=drain.get("asked_at")) if callable(follow) else None
    got = got if isinstance(got, dict) else None
    now = datetime.now(timezone.utc)
    asked = _when(drain.get("asked_at"))
    elapsed = got.get("after_s") if got and isinstance(got.get("after_s"), (int, float)) else (
        (now - asked).total_seconds() if asked else None)
    if got is None:
        ended = {**drain, "status": "failed", "never": True,
                 "error": ("statut non relu : la watch ne suit pas cette Run Command (redémarrée pendant "
                           "la coupure, ou isolée par un autre processus : `glorfindel respond`) — lire son "
                           "statut au journal d'activité de la VM")}
    elif got.get("status") == "pending":
        if elapsed is None or elapsed < DRAIN_DEADLINE_S:
            _say_pending(vm, rid, drain, got, elapsed, report)
            return True
        ended = {**drain, **got, "status": "failed", "never": True,
                 "error": (f"Run Command toujours en cours sur Azure après {int(elapsed)} s "
                           f"({got.get('azure_status') or 'statut non lu'}) — elle peut encore finir : "
                           "Azure l'arrête à 90 min ; lire le journal d'activité de la VM")}
    else:
        ended = {**got, "asked_at": drain.get("asked_at")}
    # The card first (L1A): refused, the state still says pending, the poller kept — read again.
    _say_ended(vm, rid, ended, report)
    _save_isolation_state(rid, {**state, "drain": ended, "drain_ended_at": now.isoformat()})
    drop(rid)
    return False


def _cards(sid: str) -> list[dict]:
    from glorfindel import escalations
    return [e for e in escalations.pending() if (e.get("signal_id") or "").lower() == sid]


def _say_pending(vm: str, rid: str, drain: dict, got: dict, elapsed, report: list[dict]) -> None:
    """One card while the drain runs, written once (no occurrence a minute)."""
    from glorfindel import escalations
    sid = drain_sid(vm, rid)
    if any(e.get("escalation_type") == PENDING_TYPE for e in _cards(sid)):
        return
    status = got.get("azure_status") or drain.get("azure_status") or "statut non lu"
    since = f" après {int(elapsed)} s" if elapsed is not None else ""
    reason = (f"Coupure en attente sur {vm} : l'isolation tient (règles relues sur le NSG), mais la "
              f"coupure des sessions déjà ouvertes (Run Command, `ss -K`) tourne encore sur Azure{since} "
              f"({status}). Sous la quarantaine, elle a pris 302 s le 09/11. Son statut est relu à chaque "
              f"passe : cette carte se ferme d'elle-même quand elle aboutit ; refusée, en échec, ou sans fin "
              f"après {int(DRAIN_DEADLINE_S // 60)} min, une carte le dit.")
    steps = ["Attendre : rien à approuver, la carte se ferme seule quand la coupure aboutit.",
             "Pressé : lire la Run Command au journal d'activité de la VM (Started, Accepted, Succeeded).",
             "Une session à couper tout de suite : az vm run-command invoke --command-id RunShellScript "
             "--scripts 'ss -K state established'"]
    card = escalations.record(signal_id=sid, resource_id=rid, action=PENDING_ACTION, escalation_type=PENDING_TYPE,
                              reason=reason, severity="medium", suggested_steps=steps)
    escalations.refresh(card, reason, drain_case="pending")
    report.append({"kind": "drain", "vm": vm, "outcome": "pending", "detail": reason})


def _say_ended(vm: str, rid: str, ended: dict, report: list[dict]) -> None:
    """The drain ended: its pending card closed (cut), or replaced by the card that says why not."""
    from glorfindel import escalations
    from glorfindel.response.policy import DRAIN_CASES, drain_case, drain_said
    sid = drain_sid(vm, rid)
    waiting = [e for e in _cards(sid) if e.get("escalation_type") == PENDING_TYPE]
    case = drain_case(ended)
    after = f" en {int(ended['after_s'])} s" if isinstance(ended.get("after_s"), (int, float)) else ""
    if not case:
        note = f"Coupure aboutie sur Azure{after} : sessions coupées, isolement vérifié."
        for e in waiting:
            escalations.resolve(e["id"], note=note)
        report.append({"kind": "drain", "vm": vm, "outcome": "drained", "detail": note})
        return
    reason = f"Action 'isolate_vm' executed but verification failed: {drain_said(ended)}"
    replaced = {e["id"]: f"Remplacée : {DRAIN_CASES[case]}{after} — la carte suivante le dit." for e in waiting}
    card = escalations.record(signal_id=sid, resource_id=rid, action="isolate_vm",
                              escalation_type="verification_failed", reason=reason, severity="high",
                              replaces=replaced)
    escalations.refresh(card, reason, drain_case=case)
    report.append({"kind": "drain", "vm": vm, "outcome": case, "detail": reason})


def _close_the_others(connector, waiting: set[str], report: list[dict]) -> None:
    """A pending card whose drain no longer waits — its VM released, or isolated again with a drain
    that ended — closes, said; its poller dropped."""
    from glorfindel import escalations
    from glorfindel.actions import _isolation_unreadable
    for e in escalations.pending():
        sid = (e.get("signal_id") or "").lower()
        if e.get("escalation_type") != PENDING_TYPE or sid in waiting:
            continue
        if _isolation_unreadable(e.get("resource_id") or ""):
            continue                              # its state can't be read: said elsewhere (SEC4b)
        note = "Plus de coupure en attente : l'isolation a été levée, ou reprise, avant sa fin."
        escalations.resolve(e["id"], note=note)
        _drop_if_not_pending(connector, e.get("resource_id") or "")
        vm = (e.get("resource_id") or "").rstrip("/").rsplit("/", 1)[-1]
        report.append({"kind": "drain", "vm": vm, "outcome": "closed", "detail": note})
