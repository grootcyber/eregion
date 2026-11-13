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

**Its closure (DRN2, #754)**: on the bench, 12/11, the cut ran 304 s, the isolation's notification
said « coupure en attente … suivie », the next pass read it drained — and no message said so. Every
drain this process announced pending now has one closure, its outcome and how long after it was
asked it was read so: a notice (glorfindel/vm_notices.py) in the VM's Discord thread when the bot
is configured, else by the webhook — cut, refused, sessions left open, never ended, or no longer
followed (its VM released, or isolated again, before its end). Once per drain, by its nonce
(`asked_at`), even after a restart. Its card first, then the state — the outcome read on Azure,
and a mark `drain_closure_due` —, then the notice, then the mark taken off (L1A): the card
refused, the state still says pending; the notice refused (a full disk, a store unreadable), the
mark says it at the next pass. The notices' store only tells whether a closure was said: the
console and the bot write `~/.glorfindel` too, so a notice never writes an outcome — forged, it
can silence a closure or say one twice, never declare a session cut (DRN2 review).

**Never a webhook under the lock** (JUG2c, #788): without the bot, the closure — said under its VM's
lock — and the cards — written there too, or by the reassertion's pass — are queued for the webhook
(glorfindel/vm_notices.py, `must_defer`): a pass of the watch posts them in its own thread. A webhook
that does not answer holds neither the VM's lock nor the reassertion.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Past this after it was asked, a drain still running is said never to have ended: 302 s measured
# once under the quarantine (09/11), 304 s on 12/11. The guest agent did not announce itself for
# about 15 min 45 at a boot under it, after a restore on 09/11 (the cause not told apart: rules 110
# and 111, a decision of Jonathan's); on 12/11, before any restore, it was read `Ready` under the
# quarantine once, at 09:36:46, the delay not measured (docs/azure.md, L17). Run Command itself
# stops at 90 min on Azure.
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
        if not isinstance(drain, dict):
            continue
        vm, rid = snap["vm_name"], snap["resource_id"]
        if drain.get("status") != "pending":
            if snap.get("drain_closure_due"):     # an outcome written, its closure not said yet
                _say_due_locked(vm, rid, report)
            continue
        try:
            with _vm_lock(vm, timeout=_LOCK_WAIT_S):
                if _follow_one(connector, vm, rid, report):
                    waiting.add(drain_sid(vm, rid))
        except TimeoutError:
            waiting.add(drain_sid(vm, rid))       # a write runs on this VM: next pass
        except (OSError, ValueError) as exc:      # a store full or unreadable: this VM, next pass
            waiting.add(drain_sid(vm, rid))
            report.append(unrecorded(vm, exc))
    _close_superseded(connector, report)
    _close_the_others(connector, waiting, report)
    # A poller this process keeps for a VM whose state no longer waits for it (released, the state
    # lost): dropped, never read later as another drain's outcome.
    followed = getattr(connector, "followed_drains", None)
    for rid in (followed() if callable(followed) else []):
        _drop_if_not_pending(connector, rid)


def _say_due_locked(vm: str, rid: str, report: list[dict]) -> None:
    """Under the VM's lock, the closure its state marks due (`_say_due`)."""
    from glorfindel.actions import _load_isolation_state, _vm_lock
    try:
        with _vm_lock(vm, timeout=_LOCK_WAIT_S):
            state = _load_isolation_state(rid)
            if isinstance(state, dict):
                _say_due(vm, rid, state, report)
    except TimeoutError:
        return
    except (OSError, ValueError) as exc:
        report.append(_closure_unsaid(vm, exc))


def _close_superseded(connector, report: list[dict]) -> None:
    """The drains this process asked again before their end (a VM isolated anew while its cut still
    ran): each closed « plus suivie : reprise avant sa fin », once, then forgotten."""
    superseded = getattr(connector, "superseded_drains", None)
    forget = getattr(connector, "forget_superseded", None)
    if not callable(superseded) or not callable(forget):
        return
    for rid, asked in superseded():
        try:
            _say_unfollowed(rid, asked, "reprise")
        except (OSError, ValueError) as exc:     # said at the next pass
            log.warning("drain: closure of %s not recorded (%s)", rid, exc)
            continue
        forget(rid, asked)


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
            state = _load_isolation_state(rid)
            drain = (state or {}).get("drain")
            if not isinstance(drain, dict) or drain.get("status") != "pending":
                _let_go(connector, rid, state)
    except TimeoutError:
        return
    except (OSError, ValueError) as exc:           # its closure not recorded: the poller kept, said next pass
        log.warning("drain: closure of %s not recorded (%s)", rid, exc)


def closure_key(rid: str, asked_at) -> str:
    """The closure's key of one drain: its VM's id and its nonce (`asked_at`)."""
    return f"drain:{rid.rstrip('/').lower()}:{asked_at or '?'}"


def _let_go(connector, rid: str, state: dict | None) -> None:
    """The poller dropped; the drain it followed, never closed (its VM released, or isolated again
    before its end), closed first — said once (DRN2)."""
    asked_of = getattr(connector, "drain_asked_at", None)
    asked = asked_of(rid) if callable(asked_of) else None
    recorded = ((state or {}).get("drain") or {}).get("asked_at") if isinstance(state, dict) else None
    # The drain the state records is its own business (its outcome, its closure due): only a poller
    # of another drain — its VM released, or isolated again — is closed here as no longer followed.
    if isinstance(asked, str) and asked and asked != recorded:
        _say_unfollowed(rid, asked, "levée" if not state else "reprise")
    drop = getattr(connector, "drop_drain", None)
    if callable(drop):
        drop(rid)


def _say_unfollowed(rid: str, asked: str, how: str) -> None:
    """A drain no longer followed before its end (its VM released, or isolated again): its closure,
    once, by its nonce."""
    from glorfindel import vm_notices
    key = closure_key(rid, asked)
    if vm_notices.said(key) is not None:
        return
    vm = rid.rstrip("/").rsplit("/", 1)[-1]
    since = _when(asked)
    after = (datetime.now(timezone.utc) - since).total_seconds() if since else None
    text = (f"Coupure des sessions de {vm} plus suivie : l'isolation a été {how} avant sa fin"
            + (f", {int(after)} s après la demande" if after is not None else "")
            + " — son issue se lit au journal d'activité de la VM (Run Command).")
    vm_notices.say(rid, key, "drain_closed", "Coupure des sessions : plus suivie", text,
                   level="unknown", detail={"outcome": "unfollowed", "after_s": after})


def _say_closed(vm: str, rid: str, ended: dict, after, report: list[dict], read: bool = True) -> None:
    """The closure of a drain announced pending (DRN2): its outcome and when it was read so — once,
    by its nonce. Raises OSError when it cannot be recorded: the state then still says pending."""
    from glorfindel import vm_notices
    from glorfindel.response.policy import DRAIN_CASES, drain_case, drain_said
    case = drain_case(ended)
    # « relue » only for an outcome read on Azure: a poller lost (the watch restarted) read nothing.
    word = "relue " if read else ""
    when = f", {word}{int(after)} s après la demande" if isinstance(after, (int, float)) else ""
    if not case:
        title, level = "Coupure des sessions aboutie", "ok"
        text = f"Coupure des sessions aboutie sur {vm}{when} : sessions coupées, isolement vérifié."
    else:
        title = f"Coupure des sessions : {DRAIN_CASES[case]}"
        level = "unknown" if case == "never" else "failed"
        text = f"Sur {vm}{when} — {drain_said(ended)} La carte « vérification échouée » le dit."
    via = vm_notices.say(rid, closure_key(rid, ended.get("asked_at")), "drain_closed", title, text,
                         level=level, detail={"outcome": case or "drained", "after_s": after})
    report.append({"kind": "drain", "vm": vm, "outcome": "closure", "detail": f"{title} ({via})"})


def _follow_one(connector, vm: str, rid: str, report: list[dict]) -> bool:
    """One pending drain, under its VM's lock; True while it still runs."""
    from glorfindel.actions import _load_isolation_state, _save_isolation_state
    state = _load_isolation_state(rid)
    drain = (state or {}).get("drain")
    if not isinstance(drain, dict) or drain.get("status") != "pending":
        _let_go(connector, rid, state)            # released, or ended, meanwhile
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
    # The card first, then the state with the outcome read on Azure and its closure due, then the
    # closure (L1A, DRN2): the card refused, the state still says pending, the poller kept — read
    # again; the closure refused, its mark says it at the next pass. The notices' store never
    # writes the state: the console and the bot write it too (DRN2 review).
    _say_ended(vm, rid, ended, report)
    due = {"key": closure_key(rid, ended.get("asked_at")), "after_s": elapsed, "read": got is not None}
    ended_state = {**state, "drain": ended, "drain_ended_at": now.isoformat(), "drain_closure_due": due}
    _save_isolation_state(rid, ended_state)
    _let_go(connector, rid, ended_state)
    try:
        _say_due(vm, rid, ended_state, report)
    except (OSError, ValueError) as exc:          # the outcome written; its closure, next pass
        report.append(_closure_unsaid(vm, exc))
    return False


def _closure_unsaid(vm: str, exc: Exception) -> dict:
    detail = (f"Clôture de la coupure sur {vm} non dite ({exc}) : l'issue est écrite dans l'état, la "
              "clôture est redite à la passe suivante.")
    log.warning("drain: %s", detail)
    return {"kind": "drain", "vm": vm, "outcome": "failed", "detail": detail}


def _say_due(vm: str, rid: str, state: dict, report: list[dict]) -> None:
    """The closure the state marks due (`drain_closure_due`), said from the state — the outcome read
    on Azure — unless its key was said already; then the mark taken off. Raises OSError (or
    ValueError) when it cannot be said or the mark cannot be taken off: the mark stays, said again
    next pass. A forged notice under its key can silence it, never write an outcome (DRN2 review)."""
    from glorfindel import vm_notices
    from glorfindel.actions import _save_isolation_state
    due = state.get("drain_closure_due")
    drain = state.get("drain")
    if not isinstance(due, dict) or not isinstance(drain, dict):
        return
    if drain.get("status") != "pending" and vm_notices.said(str(due.get("key") or "")) is None:
        after = due.get("after_s") if isinstance(due.get("after_s"), (int, float)) else None
        _say_closed(vm, rid, drain, after, report, read=due.get("read") is True)
    _save_isolation_state(rid, {k: v for k, v in state.items() if k != "drain_closure_due"})


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
              f"après {int(DRAIN_DEADLINE_S // 60)} min, une carte le dit ; dans tous les cas, un message "
              f"en dit l'issue, une fois.")
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
