"""FS1b (#563, docs/design/file-actions-signee.md §2.5–§2.13): the watch picks the signed action
queue up — behind ``EREGION_ACTION_QUEUE=1`` only, like the console and the bot that deposit in it
(eregion_core/action_queue.py, ``enabled``): without the flag, no queue is read.

**Its own thread** (``start``): every second, ``runs/console/queue/`` and ``runs/bot/queue/`` are
read (each a writer's directory, read-only to the watch, SEC18), a bounded number of files per poll.
Never the watch's loop, never its heartbeat: a request in flight runs in a worker of its own (at most
``IN_FLIGHT``), under the VM's lock (``_vm_lock``), never cut midway. SEC-B: judging never waits for
a worker — an accepted request waits in a bounded wait list (``BACKLOG``), a containment before a
lift; full, ``busy``; its life ended before its turn, ``no_slot``.

**Each request, from the cheapest to the dearest, no call to the cloud before the execution**:
- its name is its nonce (``<id>.json``), else it is passed over and said once;
- a receipt ``received`` first — the watch never judges a request twice: a stop between its claim
  and its end leaves that receipt, and the next start says it ``failed`` (interrupted), never runs
  it again (``recover``);
- §2.8, steps 1 to 9 — read bounded, the form, the signature by the key pinned for this directory,
  the service, the time, the rate (before the register: a service's claims are bounded), the nonce
  claimed in a register written durably, the verb (``action_queue.verify_request``);
- step 10, the attachment: a card's proposal this watch signed and that is not consumed
  (``action_queue.proposal_refusal``), or what the watch holds for a verb without a card;
- step 11, the guards of the gesture, replayed — the console's own (glorfindel/approval.py): the
  approval in one click, its age read from the proposal's signed ``issued_at``, an address and a
  reach, the VM in the watch's perimeter, the block of this IP on this VM, the bot's human;
- step 12, the posture: a read-only watch refuses;
- the receipt ``accepted``, the request in the wait list; its turn come, its proposal consumed, written
  durably, before the execution — one proposal, one execution;
- ``done`` or ``failed`` — or ``refused`` at the first step that refuses, its code and its reason.

SEC-B: once attached, the request runs on the target and the address of the proposal the watch
signed (``_signed_target``), never its own spelling of them.

**What it writes**: its receipts and its status, in its own directory (``runs/glorfindel/queue/``),
signed by its key under ``eregion.action-queue/1`` (``kind`` signed: a receipt never reads as a
proposal). A refusal of ``action_queue.CRITICAL`` makes a critical card — decided by the code, never
by a model, no action, at most one per service and per hour; a register that cannot be kept, a
card too (not critical). Each refusal is counted in the status.

**What runs**: the watch's own functions — the connector's writes, the CLI's lifts
(glorfindel/gestures.py), the check after (``approval.verify_approved``) and a ``verification_failed``
card when it is not ``True``, the card settled. The guards of the model (the confidence gate, the
mode) are not replayed: a human's approval is what they wait for.
"""
from __future__ import annotations

import collections
import dataclasses
import itertools
import json
import os
import queue
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from eregion_core import action_queue as aq
from eregion_core import channel_reader

POLL_S = 1.0
PER_POLL = 16                 # requests judged per service and per poll
SCAN_MAX = 512                # entries of a queue's directory looked at per poll
IN_FLIGHT = 4                 # requests executing at once (each under its VM's lock)
# SEC-B (audit du 06/11, V-09): the requests accepted that wait for an execution, at most — past it, a
# request is refused at once (``busy``), never left to expire in silence.
BACKLOG = 32
# What contains runs before what lifts: an isolation, a block, its promotion and a snapshot before a
# release, a reset or an unblock (SEC-B: the wait list is in this order, then the order of arrival).
CONTAIN = frozenset({"isolate_vm", "block_ip", "promote_block", "snapshot"})
RECEIPT_KEEP_S = 2 * 3600     # a receipt kept while its request may still be there (an hour)
CRITICAL_EVERY_S = 3600       # at most one critical card per service and per hour
STATUS_EVERY_S = 10
RESULT_BYTES = 16 * 1024
# The verbs that need a card, and the verbs a card may be named for without (§2.2).
CARD_ONLY = frozenset({"isolate_vm", "block_ip"})
# A verb's action, as the connector, the cards and the feed name it.
ACTION_OF_VERB = {"isolate_vm": "isolate_vm", "block_ip": "block_suspicious_ip", "snapshot": "snapshot",
                  "release_isolation": "release_isolation", "reset": "reset", "unblock_ip": "unblock_ip",
                  "promote_block": "block_suspicious_ip"}


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _plain(value, limit: int = RESULT_BYTES):
    """What the connector returned, as JSON (a date said as text), bounded: a receipt is read by
    the console within its limit, and signed whole."""
    try:
        text = json.dumps(value, default=str, sort_keys=True)
    except (TypeError, ValueError, RecursionError):
        return {"unreadable": True}
    if len(text) > limit:
        status = value.get("status") if isinstance(value, dict) else None
        return {"truncated": True, "status": str(status)[:80] if status is not None else None}
    return json.loads(text)


def _vm(resource_id: str) -> str:
    return (resource_id or "").rstrip("/").rsplit("/", 1)[-1]


def _priority(verb: str) -> int:
    """0 for what contains, 1 for what lifts: a lift never passes before a containment."""
    return 0 if verb in CONTAIN else 1


def _signed_target(req: aq.Request, proposal) -> aq.Request:
    """SEC-B (audit du 06/11, V-08): the request as it runs — the target and the address of the
    proposal the watch signed, never the request's own spelling of them. The guards, the VM's lock,
    the connector and the receipt all read these."""
    if not isinstance(proposal, dict):
        return req
    return dataclasses.replace(req, resource_id=proposal["resource_id"], ip=proposal["ip"] or req.ip)


class _Guard(Exception):
    """A guard of the gesture refuses (§2.9) — said as ``guard``, with its reason."""


class QueueWatch:
    """The watch's side of the queue. ``poll`` judges what is waiting (the tests call it; ``start``
    runs it every POLL_S in a thread of its own). ``inline``: a request accepted runs in the poll
    itself (the tests), else in a worker of its own."""

    def __init__(self, signer, connector, *, root=None, pins: dict | None = None, pin_errors=(),
                 seen=None, consumed=None, rate=None, read_only: bool | None = None, say=print,
                 environ=None, inline: bool = False, clock=None):
        self.signer = signer
        self.connector = connector
        self.root = root
        if pins is None:
            pins, pin_errors = aq.pinned_keys()
        self.pins = dict(pins)
        self.pin_errors = list(pin_errors)
        self.seen = seen if seen is not None else aq.SeenFile()
        self.consumed = consumed if consumed is not None else aq.ConsumedFile()
        self.rate = rate if rate is not None else aq.Rate()
        if read_only is None:
            read_only = bool(getattr(connector, "read_only", False))
        self.read_only = read_only
        self.say = say
        self.environ = os.environ if environ is None else environ
        self.inline = inline
        self.since = datetime.now(timezone.utc)
        self.refused: collections.Counter = collections.Counter()
        self._critical_at: dict[str, float] = {}
        self._judged: dict[tuple[str, str], float] = {}
        self._said: set[tuple[str, str, int]] = set()
        self._lock = threading.Lock()
        # SEC-B (audit du 06/11, V-09): the wait list — explicit, bounded (BACKLOG), in priority
        # (``_priority``, then arrival); IN_FLIGHT workers take from it. Judging never waits for one.
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._backlog: queue.PriorityQueue = queue.PriorityQueue()
        self._arrival = itertools.count()
        self._running = 0
        self._workers: list[threading.Thread] = []
        self._last_status = 0.0
        self._hold = None               # the lock of one watch per HOME (``start``)

    # ── The receipts ─────────────────────────────────────────────────────────────────

    def _receipt(self, service: str, request_id: str, state: str, *, request: aq.Request | None = None,
                 code: str = "", reason: str = "", result=None, verification=None, now=None) -> dict:
        body = {
            "request": request_id, "service": service,
            "verb": request.verb if request else "", "resource_id": request.resource_id if request else "",
            "ip": request.ip if request else "", "scope": request.scope if request else "",
            "card": request.card_id if request else None,
            "state": state, "code": code, "reason": str(reason)[:1000],
            "result": _plain(result) if result is not None else None,
            "verification": _plain(verification) if verification is not None else None,
            "at": _iso(now or datetime.now(timezone.utc)),
        }
        doc = aq.sign_watch("receipt", body, self.signer)
        path = aq.receipt_path(service, request_id, self.root)
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        channel_reader.write_file(path, json.dumps(doc, sort_keys=True), mode=0o644)
        return doc

    def recover(self, now: datetime | None = None) -> int:
        """At the start: a receipt still ``received`` or ``accepted`` was cut by a stop of the watch —
        between its claim and its end. Said ``failed``, never run again: the VM's state is to be
        checked, and the request asked again. How many."""
        now = now or datetime.now(timezone.utc)
        n = 0
        try:
            entries = list(os.scandir(aq.receipts_dir(self.root)))
        except OSError:
            return 0
        for e in entries:
            name = e.name
            if not name.endswith(".json") or "-" not in name:
                continue
            service, _, rest = name.partition("-")
            request_id = rest[:-5]
            if service not in aq.SERVICES:
                continue
            doc = aq.read_receipt(service, request_id, root=self.root)
            if doc is None or doc["state"] not in ("received", "accepted"):
                continue
            req = _Said(doc)
            self._receipt(service, request_id, "failed", request=req, code="interrupted",
                          reason=("the watch stopped while it judged or ran this request: nothing is run "
                                  "again — check the VM's state, then ask again"), now=now)
            n += 1
        return n

    # ── One poll ─────────────────────────────────────────────────────────────────────

    def _waiting(self, service: str) -> list[Path]:
        """The requests of this service not judged yet, oldest first — at most PER_POLL, among
        SCAN_MAX entries; a name that is not a nonce passed over and said once."""
        directory = aq.request_dir(service, self.root)
        found = []
        try:
            with os.scandir(directory) as it:
                for i, e in enumerate(it):
                    if i >= SCAN_MAX:
                        break
                    if e.name.startswith(".") or not e.name.endswith(".json"):
                        continue
                    stem = e.name[:-5]
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if not aq._ID.fullmatch(stem):
                        key = (service, e.name, st.st_mtime_ns)
                        if key not in self._said:
                            self._said.add(key)
                            with self._lock:
                                self.refused["malformed"] += 1
                            self.say(f"file d'actions : {service}/queue/{e.name[:60]!r} n'est pas une demande "
                                     "(son nom n'est pas son nonce) : jamais lue")
                        continue
                    if (service, stem) in self._judged:
                        continue
                    if aq.receipt_path(service, stem, self.root).exists():
                        self._judged[(service, stem)] = time.time()
                        continue
                    found.append((st.st_mtime_ns, e.name, Path(e.path)))
        except OSError:
            return []
        return [p for _, _, p in sorted(found)[:PER_POLL]]

    def poll(self, now: datetime | None = None) -> list[dict]:
        """Judge what waits in each service's queue; the receipts written now (accepted ones run:
        inline, or in a worker). Never raises."""
        out = []
        for service in aq.SERVICES:
            for path in self._waiting(service):
                try:
                    out.append(self.judge(service, path, now or datetime.now(timezone.utc)))
                except Exception as exc:   # a request never stops the queue
                    self.say(f"file d'actions : {service}/{path.name} — erreur {type(exc).__name__}: {exc}")
        try:
            self.status(now or datetime.now(timezone.utc))
        except Exception as exc:
            self.say(f"file d'actions : statut non écrit ({exc})")
        return out

    def judge(self, service: str, path: Path, now: datetime) -> dict:
        request_id = path.name[:-5]
        self._judged[(service, request_id)] = time.time()
        self._receipt(service, request_id, "received", now=now)
        req = None
        try:
            try:
                data = aq.read_request(path)
            except FileNotFoundError:
                raise aq.Refused("malformed", "gone before it was read") from None
            req = aq.verify_request(data, service=service, pins=self.pins, now=now, seen=self.seen, rate=self.rate)
            if req.id != request_id:
                raise aq.Refused("malformed", "its name is not its nonce")
            card, proposal = self._attach(req)
            req = _signed_target(req, proposal)                  # SEC-B: what runs is what was signed
            ctx = self._guards(req, card, proposal, now)
            if self.read_only:                                   # 12. the posture
                raise aq.Refused("read_only")
            if not self.inline and self._backlog.qsize() >= BACKLOG:
                raise aq.Refused("busy", f"{IN_FLIGHT} executions running and {BACKLOG} waiting: nothing is "
                                         "run — ask again in a moment")
        except aq.Refused as r:
            return self._refuse(service, request_id, req, r, now)
        except _Guard as g:
            return self._refuse(service, request_id, req, aq.Refused("guard", str(g)), now)
        accepted = self._receipt(service, request_id, "accepted", request=req, now=now)
        self.say(f"file d'actions : {service} demande {req.verb} sur {_vm(req.resource_id)} — acceptée")
        item = (service, req, card, proposal, ctx)
        if self.inline:
            return self._take(item, now)
        self._backlog.put_nowait((_priority(req.verb), next(self._arrival), item))
        self._serve()
        return accepted

    # ── The wait list, its workers (SEC-B) ───────────────────────────────────────────

    def _serve(self) -> None:
        """The workers, started at the first request accepted — IN_FLIGHT of them, each taking the
        first of the wait list in turn."""
        with self._lock:
            self._workers = [t for t in self._workers if t.is_alive()]
            while len(self._workers) < IN_FLIGHT:
                t = threading.Thread(target=self._work, daemon=True, name=f"queue-run-{len(self._workers)}")
                self._workers.append(t)
                t.start()

    def stop(self) -> None:
        """The workers stopped once the wait list ahead of them is done (the tests)."""
        with self._lock:
            workers = list(self._workers)
        for _ in workers:
            self._backlog.put((2, next(self._arrival), None))

    def _work(self) -> None:
        while True:
            _, _, item = self._backlog.get()
            if item is None:
                self._backlog.task_done()
                return
            with self._lock:
                self._running += 1
            try:
                self._take(item)
            except Exception as exc:            # a worker never dies on one request
                self.say(f"file d'actions : exécution en erreur — {type(exc).__name__}: {exc}")
            finally:
                with self._lock:
                    self._running -= 1
                self._backlog.task_done()

    def busy(self) -> dict:
        """What the watch's executions hold now: running, and waiting."""
        with self._lock:
            return {"running": self._running, "waiting": self._backlog.qsize()}

    def _take(self, item, now: datetime | None = None) -> dict:
        """A request accepted, its turn come (``now``: the worker's clock; inline, the poll's): refused
        when its life ended while it waited (said, never run late: ``no_slot``); else its proposal
        consumed — one proposal, one execution — then run."""
        service, req, card, proposal, ctx = item
        now = now or self.clock()
        try:
            if now >= req.expires_at:
                raise aq.Refused("no_slot", f"{aq.REFUSALS['no_slot']} (waited past its end of life, "
                                            f"{(now - req.expires_at).total_seconds():.0f} s ago)")
            if proposal is not None:
                try:
                    fresh = self.consumed.consume(req.proposal, req.card_id, now)
                except (OSError, ValueError) as e:
                    raise aq.Refused("seen_store_unavailable", f"{aq.REFUSALS['seen_store_unavailable']} "
                                                               f"({str(e)[:120]})") from None
                if not fresh:
                    raise aq.Refused("proposal_consumed")
        except aq.Refused as r:
            return self._refuse(service, req.id, req, r, now)
        return self._run(service, req, card, ctx)

    def _refuse(self, service: str, request_id: str, req, refused: aq.Refused, now: datetime) -> dict:
        with self._lock:              # the relève and the workers both refuse: never a count lost
            self.refused[refused.code] += 1
        self.say(f"file d'actions : {service} {request_id[:8]} refusée — {refused.code} : {refused.reason}")
        if refused.critical or refused.code == "seen_store_unavailable":
            self._card(service, refused, now)
        return self._receipt(service, request_id, "refused", request=req, code=refused.code,
                             reason=refused.reason, now=now)

    def _card(self, service: str, refused: aq.Refused, now: datetime) -> None:
        """A card decided by the code (§2.11): no model, no action — at most one per service and per
        hour."""
        critical = refused.critical
        key = f"{service}:{'critical' if critical else 'register'}"
        at = time.time()
        with self._lock:
            if at - self._critical_at.get(key, -CRITICAL_EVERY_S) < CRITICAL_EVERY_S:
                return
            self._critical_at[key] = at
        try:
            from glorfindel import escalations
            if critical:
                reason = (f"File d'actions de {service} : une demande refusée ({refused.code} — "
                          f"{refused.reason[:300]}). Quelqu'un écrit dans la file de ce service sans être lui, ou "
                          "la rejoue : examiner l'hôte (qui écrit runs/" + service + "/queue/), la clé épinglée "
                          "(EREGION_QUEUE_KEYS) et la clé du service. Aucune action n'est prise.")
                etype, severity = "queue_tampered", "critical"
            else:
                reason = (f"File d'actions : le registre de la watch ne se lit ou ne s'écrit pas "
                          f"({refused.reason[:300]}) — aucune demande n'est prise tant qu'il ne se tient pas "
                          "(~/.eregion/watch-queue/).")
                etype, severity = "queue_unavailable", "high"
            escalations.record(signal_id=f"queue-{service}-{refused.code}", resource_id=f"~/runs/{service}/queue",
                               action="none", escalation_type=etype, reason=reason, severity=severity,
                               source="real")
        except Exception as exc:
            self.say(f"file d'actions : carte non écrite ({exc})")

    # ── Step 10, the attachment ──────────────────────────────────────────────────────

    def _attach(self, req: aq.Request) -> tuple[dict | None, dict | None]:
        """(the card, its proposal) a request is bound to, or (None, None) for a verb that acts on
        what the watch holds. Raises Refused."""
        if req.card_id is None:
            if req.verb in CARD_ONLY or req.service == "bot":
                raise aq.Refused("proposal_missing", f"{req.verb} goes through its card, and its proposal")
            return None, None
        from glorfindel import escalations
        card = next((e for e in escalations.all_escalations() if e.get("id") == req.card_id), None)
        try:
            consumed = self.consumed.digests()
        except (OSError, ValueError) as e:
            raise aq.Refused("seen_store_unavailable", f"{aq.REFUSALS['seen_store_unavailable']} ({str(e)[:120]})") from None
        aq.proposal_refusal(card, req, watch_public=self.signer.public, consumed=consumed)
        return card, card["proposal"]

    # ── Step 11, the guards of the gesture (glorfindel/approval.py) ──────────────────

    def _guards(self, req: aq.Request, card, proposal, now: datetime) -> dict:
        from glorfindel import approval
        rid, vm = req.resource_id, _vm(req.resource_id)
        ctx: dict = {}
        # Step 10 for a verb without a card: what the watch holds for this VM, or this address.
        if req.verb == "release_isolation" and card is None:
            if not approval.held_isolation(rid):
                raise aq.Refused("nothing_to_undo", f"no isolation the watch holds on {vm[:64]}")
        elif req.verb == "reset" and card is None:
            if not (approval.held_isolation(rid) or approval.held_blocks(rid)):
                raise aq.Refused("nothing_to_undo", f"nothing the watch holds on {vm[:64]}")
        elif req.verb in ("unblock_ip", "promote_block"):
            block = approval.held_block(rid, req.ip)
            if block is None:
                raise aq.Refused("nothing_to_undo", f"no block of {req.ip[:45]!r} the watch holds on {vm[:64]}")
            ctx.update(ip=block["ip"], block_rid=block.get("resource_id") or rid, scoped=block.get("scoped", True))
        # Step 11, the guards of the gesture.
        if not approval.in_perimeter(rid):
            raise _Guard(f"{vm[:64]!r} n'est pas une VM du périmètre de la watch")
        if card is not None and req.verb != "reset":
            why = approval.approval_refusal(card, vm, dated=proposal["issued_at"], now=now)
            if why:
                raise _Guard(why)
        if req.service == "bot":
            why = approval.discord_refusal(req.by, self.environ)
            if why:
                raise _Guard(why)
        if req.verb == "block_ip":
            ip = proposal["ip"] or req.ip
            if not ip:
                raise _Guard("la carte ne porte pas l'adresse : la nommer (ip)")
            ip, why = approval.address_refusal(ip)
            if why:
                raise _Guard(why)
            why = approval.scope_refusal(req.scope)
            if why:
                raise _Guard(why)
            ctx.update(ip=ip, scope=req.scope, port=proposal["port"])
        elif req.verb == "snapshot":
            from glorfindel.config import NO_VAULT_MSG, resolve_backup_vault
            vault, vault_rg, _ = resolve_backup_vault()
            if not vault:
                raise _Guard(NO_VAULT_MSG)
            ctx.update(vault=vault, vault_rg=vault_rg)
        elif req.verb == "promote_block":
            if req.scope not in ("", "vm"):
                raise _Guard(f"une promotion part d'un blocage de la VM (scope vm), pas {req.scope[:20]!r}")
            if ctx["scoped"] is False:
                raise _Guard(f"{ctx['ip']} est déjà bloquée pour tout le sous-réseau")
        return ctx

    # ── The execution ────────────────────────────────────────────────────────────────

    def _run(self, service: str, req: aq.Request, card, ctx: dict) -> dict:
        """Under the VM's lock, with the watch's own functions; the receipt ``done`` or ``failed``.
        Never raises."""
        from glorfindel.response.locks import _vm_lock, writer_wait_s
        try:
            with _vm_lock(_vm(req.resource_id), timeout=writer_wait_s()):   # bounded (SEC-H)
                state, result, verification, reason = getattr(self, f"_do_{req.verb}")(req, card, ctx)
        except Exception as exc:
            state, result, verification = "failed", None, None
            reason = f"{type(exc).__name__}: {str(exc)[:300]}"
        self.say(f"file d'actions : {service} {req.verb} sur {_vm(req.resource_id)} → {state}"
                 + (f" ({reason[:200]})" if reason else ""))
        try:
            return self._receipt(service, req.id, state, request=req, result=result,
                                 verification=verification, reason=reason)
        except Exception as exc:
            self.say(f"file d'actions : reçu {req.id[:8]} non écrit ({exc})")
            return {}

    def _settle(self, card) -> None:
        """The card settled once its action is done — SEC-B (audit du 06/11, V-12): a store that cannot
        be rewritten (a full disk) never makes the receipt of an action done say ``failed``: said,
        and the card stays open for the operator to close."""
        if card is None:
            return
        try:
            from glorfindel import escalations
            escalations.resolve(card["id"], note="exécutée par la file d'actions (FS1b)")
        except Exception as exc:
            self.say(f"file d'actions : carte {str(card.get('id'))[:8]} non réglée ({type(exc).__name__}: "
                     f"{str(exc)[:200]}) — l'action est faite, la carte reste ouverte")

    def _check(self, req, card, action: str, result, ip: str = "") -> dict:
        """``approval.verify_approved``; a card ``verification_failed`` it leaves bears the request's
        own signal (FS1c: ``queue-<service>-<id>``, as its receipt — never the console's
        ``approve-<card>``)."""
        from glorfindel import approval
        return approval.verify_approved(self.connector, card or {"id": ""}, action, req.resource_id, result, ip,
                                        signal_id=f"queue-{req.service}-{req.id}")

    def _do_isolate_vm(self, req, card, ctx):
        result = self.connector.isolate_vm(req.resource_id)
        self._settle(card)
        return "done", result, self._check(req, card, "isolate_vm", result), ""

    def _do_block_ip(self, req, card, ctx):
        result = self.connector.block_suspicious_ip(ctx["ip"], req.resource_id, ctx["scope"], False, ctx["port"])
        self._settle(card)
        return "done", result, self._check(req, card, "block_suspicious_ip", result, ctx["ip"]), ""

    def _do_snapshot(self, req, card, ctx):
        from glorfindel.jobs import start_snapshot, vault_job
        job = start_snapshot(req.resource_id, self.connector, ctx["vault"], vault_rg=ctx["vault_rg"])
        self._settle(card)
        # SNP1: the receipt names the vault's job beside Glorfindel's own record, as the direct route does.
        return "done", {"status": "started", "job_id": job.get("job_id"),
                        "vault_job": vault_job(job.get("snap_id"))}, None, ""

    def _do_release_isolation(self, req, card, ctx):
        from glorfindel.gestures import release_needed
        if not release_needed(self.connector, req.resource_id):
            self._settle(card)
            return "done", {"status": "nothing_to_release"}, None, "no isolation rule on Azure: state cleared"
        result = self.connector.release_isolation(req.resource_id)
        if result.get("status") == "release_partial":
            return "failed", result, None, "released in part: rules still in place — " + "; ".join(
                str(x) for x in result.get("failed", []))[:600]
        self._settle(card)
        if result.get("status") == "released":
            from glorfindel.gestures import released
            released(req.resource_id)        # SEC-E (#846): B3a's facts forgotten
        return "done", result, self._check(req, card, "release_isolation", {"status": "released"}), ""

    def _do_reset(self, req, card, ctx):
        from glorfindel.gestures import reset_apply, reset_targets
        isolations, blocks = reset_targets(req.resource_id)
        if not isolations and not blocks:
            self._settle(card)
            return "done", {"status": "clean", "note": "nothing to reset"}, None, ""
        leftovers = reset_apply(self.connector, req.resource_id, isolations, blocks)
        if leftovers:
            return "failed", {"status": "partial", "failed": leftovers}, None, "reset incomplete — " + "; ".join(
                str(x) for x in leftovers)[:600]
        self._settle(card)
        return "done", {"status": "clean"}, None, ""

    def _do_unblock_ip(self, req, card, ctx):
        result = self.connector.unblock_ip(ctx["ip"], ctx["block_rid"])
        if result.get("status") == "unblock_partial":
            return "failed", result, None, "unblocked in part: rules still in place"
        return "done", result, None, ("no block rule found (already removed?)"
                                      if result.get("status") == "not_found" else "")

    def _do_promote_block(self, req, card, ctx):
        result = self.connector.block_suspicious_ip(ctx["ip"], ctx["block_rid"], "subnet", True)
        return "done", result, None, ""

    # ── The status, the thread ───────────────────────────────────────────────────────

    def status(self, now: datetime, force: bool = False) -> dict | None:
        """``runs/glorfindel/queue/status.json``, signed: the posture, the keys pinned per service,
        since when the queue is picked up, the refusals counted. At most every STATUS_EVERY_S; the
        receipts older than RECEIPT_KEEP_S whose request is gone removed."""
        at = time.time()
        if not force and at - self._last_status < STATUS_EVERY_S:
            return None
        self._last_status = at
        from eregion_core import watch_key
        with self._lock:
            refused = dict(sorted(self.refused.items()))
        body = {"posture": "read_only" if self.read_only else "write",
                "pins": {s: (watch_key.fingerprint(self.pins[s]) if s in self.pins else "") for s in aq.SERVICES},
                "pin_errors": [str(e)[:200] for e in self.pin_errors][:10],
                "since": _iso(self.since), "at": _iso(now), "refused": refused,
                "executions": {**self.busy(), "slots": IN_FLIGHT, "backlog": BACKLOG}}
        doc = aq.sign_watch("status", body, self.signer)
        path = aq.receipts_dir(self.root) / aq.STATUS_NAME
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        channel_reader.write_file(path, json.dumps(doc, sort_keys=True), mode=0o644)
        self._sweep(at)
        return doc

    def _sweep(self, at: float) -> None:
        try:
            entries = list(os.scandir(aq.receipts_dir(self.root)))
        except OSError:
            return
        for e in entries:
            if e.name == aq.STATUS_NAME or not e.name.endswith(".json") or "-" not in e.name:
                continue
            service, _, rest = e.name.partition("-")
            try:
                if at - e.stat(follow_symlinks=False).st_mtime < RECEIPT_KEEP_S:
                    continue
                if service in aq.SERVICES and (aq.request_dir(service, self.root) / rest).exists():
                    continue
                os.unlink(e.path)
            except OSError:
                continue
        cutoff = at - RECEIPT_KEEP_S
        self._judged = {k: v for k, v in self._judged.items() if v > cutoff}

    def one_pass(self) -> None:
        """One pass of the thread: ``poll``, whatever it raises said — the thread never dies in
        silence."""
        try:
            self.poll()
        except Exception as exc:
            try:
                self.say(f"file d'actions : passage en erreur — {type(exc).__name__}: {exc}")
            except Exception:
                pass

    def start(self) -> threading.Thread:
        """The queue picked up every POLL_S, in a thread of its own — never the watch's loop."""
        self.recover()
        self.status(datetime.now(timezone.utc), force=True)

        def _loop():
            while True:
                self.one_pass()
                time.sleep(POLL_S)
        t = threading.Thread(target=_loop, daemon=True, name="action-queue")
        t.start()
        return t


class _Said:
    """A request as its receipt says it (``recover``): its fields, no more."""

    def __init__(self, doc: dict):
        self.verb, self.resource_id = doc.get("verb", ""), doc.get("resource_id", "")
        self.ip, self.scope, self.card_id = doc.get("ip", ""), doc.get("scope", ""), doc.get("card")


WATCH_LOCK = "watch.lock"


class SecondWatch(RuntimeError):
    """SEC-B (audit du 06/11, V-10): another watch picks the queue of this HOME up already."""


def hold_the_queue(directory=None) -> int:
    """SEC-B (audit du 06/11, V-10): one watch per HOME picks the queue up — an exclusive ``flock`` on
    ``queue_dir()/watch.lock``, never waited for, held for the life of the process (the kernel lets
    it go with it, a crash included), its pid written in it. The descriptor held; SecondWatch, the
    other's pid said, when another process holds it."""
    import fcntl
    directory = Path(directory) if directory is not None else aq.queue_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / WATCH_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        try:
            other = os.pread(fd, 16, 0).decode("ascii", "replace").strip()
        except OSError:
            other = ""
        os.close(fd)
        raise SecondWatch(
            f"une autre watch relève déjà la file d'actions de ce HOME ({directory / WATCH_LOCK}"
            + (f", pid {other[:12]}" if other.isdigit() else "") + ") : deux watches sur les mêmes "
            "registres doublent les actions — arrêter l'autre (make glorfindel-stop), puis relancer") from None
    except BaseException:
        os.close(fd)
        raise
    try:
        os.ftruncate(fd, 0)
        os.pwrite(fd, str(os.getpid()).encode("ascii"), 0)
    except OSError:
        pass
    return fd


def start(connector, signer_of, *, say=print, root=None) -> QueueWatch | None:
    """The watch's queue (glorfindel/cli.py, ``watch``): started only behind EREGION_ACTION_QUEUE=1,
    and with the watch's key — without it, no proposal can be checked: nothing is picked up, said.
    SEC-B: one watch per HOME — a second one raises SecondWatch (``hold_the_queue``), which the
    watch command says, then refuses to run."""
    if not aq.enabled():
        return None
    signer = signer_of()
    if signer is None:
        say("File d'actions : la clé de la watch est indisponible — la file n'est pas relevée")
        return None
    hold = hold_the_queue()
    pins, wrong = aq.pinned_keys()
    # FS1c: the start says each key that is missing or wrong — the same words as host_env.py --check.
    for line in aq.pin_problems(pins, wrong):
        say(f"File d'actions : {line}")
    q = QueueWatch(signer, connector, root=root, pins=pins, pin_errors=wrong, say=say)
    q._hold = hold
    q.start()
    say(f"File d'actions relevée : runs/console/queue, runs/bot/queue → runs/glorfindel/queue "
        f"({'lecture seule' if q.read_only else 'écriture'})")
    return q
