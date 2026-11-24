"""FS1g (#1127, docs/design/file-actions-signee.md, decision Q2 of 04/11): the restore executor — a
fourth service, beside the watch, the console and the bot, the only one to hold Restore and Restore
Neutralize. The watch never restores (SEC7): the restore is in none of its verbs, and the watch never
reads this queue.

**What it does, and nothing else**: it picks up the restore requests the console and the bot sign
(``runs/console/restore/``, ``runs/bot/restore/``, read-only here: eregion_core/restore_queue.py),
verifies them, replays the guards, and starts the restore under its own principal
(``EREGION_RESTORE_AZURE_CLIENT_*``). It never isolates, never blocks, never writes a configuration:
the one write it calls is the restore (``jobs.start_restore``).

**It refuses to start** (``startup_refusal``) — behind the queue's flag only (``EREGION_RESTORE_QUEUE=1``,
false by default: without it, nothing is picked up); with a whole pair of its own (a principal, never
a managed identity); and when the instance's metadata point (IMDS, 169.254.169.254) answers its
container — there it could take the VM's managed identity, which is the watch's (Q3). The host rule
that cuts IMDS (``DOCKER-USER``, deploy.sh) is FS1d's: on Imladris, until it is there, the executor
refuses to start, and says why. One executor per HOME (a ``flock``, as the watch's).

**Each request, from the cheapest to the dearest, no call to the cloud before the restore**:
- its name is its nonce, a receipt ``received`` first — never judged twice; a stop between its claim
  and its end leaves that receipt, and the next start says it ``failed`` (``interrupted``), never runs
  it again (``recover``);
- the verification (``restore_queue.verify``): read bounded, the form, the signature by the key pinned
  for this directory, the service, the time, the rate, the nonce, ASCII;
- the card (``approval.restore_refusal``): pending, a restore, on this VM, never an anchored one — the
  request names the card's VM at the byte (``card_mismatch``);
- the guards: a VM's id, the moment with its zone and never ahead (``restore_plan.parse_moment``,
  SEC4c, RTZ1), the vault configured, no other restore of the VM running (SEC4c), the bot's human
  read against the executor's own copy of DISCORD_ALLOWED_* (``approval.discord_refusal``);
- the second factor (``second_factor_refusal``): the operator's one-time code (TOT1, #685) —
  **not delivered yet: every request is refused here**, and said (docs/design/banc-autonome.md §4.2);
- the receipt ``accepted``, the request in a short wait list (one restore at a time); its turn come
  after its end of life, ``no_slot`` — never restored late;
- under the VM's restore claim (``jobs.restore_claim``, the CLI's own: a restore the CLI runs on this
  host, or another request, refuses this one), ``jobs.start_restore`` — ``done`` (started; the job
  is followed as any other) or ``failed``, its reason masked.

A refusal of ``restore_queue.CRITICAL`` makes a critical card — decided by the code, no action, at
most one per service and per hour. Its receipts and its status (``runs/restore/``) are signed by its
own key (``~/.eregion/restore-executor/``), under the restore's domain.
"""
from __future__ import annotations

import collections
import json
import os
import queue
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from eregion_core import action_queue as aq
from eregion_core import channel_reader
from eregion_core import restore_queue as rq

POLL_S = 1.0
PER_POLL = 8                  # requests judged per service and per poll
SCAN_MAX = 256                # entries of a directory looked at per poll
BACKLOG = 4                   # requests accepted that wait for the one restore at a time
RECEIPT_KEEP_S = 2 * 3600
CRITICAL_EVERY_S = 3600
STATUS_EVERY_S = 10
RESULT_BYTES = 8 * 1024
IMDS = ("169.254.169.254", 80)
IMDS_TIMEOUT_S = 2.0
LOCK_NAME = "executor.lock"


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _vm(resource_id: str) -> str:
    return (resource_id or "").rstrip("/").rsplit("/", 1)[-1]


REASON_CHARS = 3000          # a refusal of the vault says everything to restore by hand (Jonathan, 24/11)


def _masked(text, limit: int = 600) -> str:
    """What Azure or the code said, the subscriptions masked (MSK2), bounded."""
    try:
        from glorfindel.masking import ids_masked
        return ids_masked(str(text))[:limit]
    except Exception:
        return "(unreadable)"


# ── The start ──────────────────────────────────────────────────────────────────────

def imds_reachable(timeout: float = IMDS_TIMEOUT_S, connect=None) -> bool:
    """Does the instance's metadata point answer this container? A connection that opens: yes. Any
    refusal, an unreachable network, a timeout (a rule that drops it): no."""
    connect = connect or socket.create_connection
    try:
        conn = connect(IMDS, timeout)
    except OSError:
        return False
    try:
        conn.close()
    except OSError:
        pass
    return True


def pair_problem(environ) -> str:
    """Why this container holds no whole principal of its own — "" when it does: a client id, a
    tenant, and a secret or a certificate. Never a value said."""
    def has(name: str) -> bool:
        return bool(str(environ.get(name, "")).strip())
    lacking = [n for n in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID") if not has(n)]
    if not (has("AZURE_CLIENT_SECRET") or has("AZURE_CLIENT_CERTIFICATE_PATH")):
        lacking.append("AZURE_CLIENT_SECRET (or AZURE_CLIENT_CERTIFICATE_PATH)")
    if not lacking:
        return ""
    return (f"no whole restore principal ({', '.join(lacking)} empty): the executor restores under its "
            "own pair only (EREGION_RESTORE_AZURE_CLIENT_* in the compose), never a managed identity nor "
            "another chain of DefaultAzureCredential")


def startup_refusal(environ=None, reach=None) -> str:
    """Why the executor refuses to start — "" when it may: the queue's flag, its own pair, IMDS cut."""
    environ = os.environ if environ is None else environ
    if not rq.enabled(environ):
        return (f"{rq.FLAG_ENV} is not « 1 »: the restore queue is off — nothing is picked up, the restore "
                "stays a gesture of the CLI")
    why = pair_problem(environ)
    if why:
        return why
    if (reach or imds_reachable)():
        return (f"the instance's metadata point ({IMDS[0]}) answers this container: it could take the VM's "
                "managed identity, the watch's — the executor refuses to start until it is cut (the host rule "
                "DOCKER-USER, FS1d: docs/design/file-actions-signee.md, Q3)")
    return ""


class SecondExecutor(RuntimeError):
    """Another restore executor picks this HOME's restore queue up already."""


def hold(directory=None) -> int:
    """One executor per HOME: an exclusive ``flock`` on its lock, never waited for, held for the life
    of the process. The descriptor; SecondExecutor when another holds it."""
    import fcntl
    directory = Path(directory) if directory is not None else rq.executor_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(directory / LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise SecondExecutor(f"another restore executor picks this HOME's restore queue up already "
                             f"({directory / LOCK_NAME}): stop it first") from None
    return fd


# ── The second factor (TOT1) ─────────────────────────────────────────────────────────

def second_factor_refusal(req: rq.Request) -> str:
    """Why the operator's second factor does not hold — "" when it does. TOT1 (#685) brings the
    one-time code; until then, a restore from a button is refused, and the reason said
    (docs/design/banc-autonome.md §4.2)."""
    return rq.REFUSALS["second_factor"]


class _Guard(Exception):
    """A guard of the restore refuses — said as ``guard``, with its reason."""


class RestoreExecutor:
    """The executor's side of the restore queue. ``poll`` judges what waits (the tests call it);
    ``run_forever`` runs it every POLL_S. ``inline``: a request accepted runs in the poll itself (the
    tests), else in the one worker."""

    def __init__(self, signer, connector, *, root=None, pins: dict | None = None, pin_errors=(),
                 seen=None, rate=None, say=print, environ=None, inline: bool = False, clock=None):
        self.signer = signer
        self.connector = connector
        self.root = root
        if pins is None:
            pins, pin_errors = aq.pinned_keys()
        self.pins, self.pin_errors = dict(pins), list(pin_errors)
        self.seen = seen if seen is not None else rq.seen_file()
        self.rate = rate if rate is not None else rq.rate()
        self.say = say
        self.environ = os.environ if environ is None else environ
        self.inline = inline
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.since = self.clock()
        self.refused: collections.Counter = collections.Counter()
        self._critical_at: dict[str, float] = {}
        self._judged: dict[tuple[str, str], float] = {}
        self._backlog: queue.Queue = queue.Queue(maxsize=BACKLOG)
        self._running = 0
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_status = 0.0

    # ── The receipts ─────────────────────────────────────────────────────────────────

    def _receipt(self, service: str, request_id: str, state: str, *, request=None, code: str = "",
                 reason: str = "", result=None, now=None) -> dict:
        text = json.dumps(result, default=str, sort_keys=True) if result is not None else ""
        body = {
            "request": request_id, "service": service,
            "resource_id": request.resource_id if request else "",
            "card": request.card_id if request else "", "before": request.before if request else "",
            "state": state, "code": code, "reason": str(reason)[:REASON_CHARS],
            "result": (json.loads(text) if len(text) <= RESULT_BYTES else {"truncated": True}) if text else None,
            "at": _iso(now or self.clock()),
        }
        doc = rq.sign_executor("receipt", body, self.signer)
        path = rq.receipt_path(service, request_id, self.root)
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        channel_reader.write_file(path, json.dumps(doc, sort_keys=True), mode=0o644)
        return doc

    def recover(self, now: datetime | None = None) -> int:
        """At the start: a receipt still ``received`` or ``accepted`` was cut by a stop — said
        ``failed`` (``interrupted``), never run again. How many."""
        now = now or self.clock()
        n = 0
        try:
            entries = list(os.scandir(rq.receipts_dir(self.root)))
        except OSError:
            return 0
        for e in entries:
            service, _, rest = e.name.partition("-")
            if service not in rq.SERVICES or not e.name.endswith(".json"):
                continue
            doc, _ = rq.receipt_said(service, rest[:-5], root=self.root)
            if doc is None or doc["state"] not in ("received", "accepted"):
                continue
            said = rq.Request(id=rest[:-5], service=service, by={}, resource_id=str(doc.get("resource_id") or ""),
                              card_id=str(doc.get("card") or ""), before=str(doc.get("before") or ""),
                              issued_at=now, expires_at=now, key="")
            self._receipt(service, said.id, "failed", request=said, code="interrupted",
                          reason=rq.REFUSALS["interrupted"], now=now)
            n += 1
        return n

    # ── One poll ─────────────────────────────────────────────────────────────────────

    def _waiting(self, service: str) -> list[Path]:
        found = []
        try:
            with os.scandir(rq.request_dir(service, self.root)) as it:
                for i, e in enumerate(it):
                    if i >= SCAN_MAX:
                        break
                    stem = e.name[:-5] if e.name.endswith(".json") else ""
                    if not aq._ID.fullmatch(stem) or (service, stem) in self._judged:
                        continue
                    if rq.receipt_path(service, stem, self.root).exists():
                        self._judged[(service, stem)] = time.time()
                        continue
                    try:
                        found.append((e.stat(follow_symlinks=False).st_mtime_ns, e.name, Path(e.path)))
                    except OSError:
                        continue
        except OSError:
            return []
        return [p for _, _, p in sorted(found)[:PER_POLL]]

    def poll(self, now: datetime | None = None) -> list[dict]:
        """Judge what waits in each service's restore queue. Never raises."""
        out = []
        for service in rq.SERVICES:
            for path in self._waiting(service):
                try:
                    out.append(self.judge(service, path, now or self.clock()))
                except Exception as exc:
                    self.say(f"restore queue: {service}/{path.name} — error {type(exc).__name__}: {_masked(exc)}")
        try:
            self.status(now or self.clock())
        except Exception as exc:
            self.say(f"restore queue: status not written ({exc})")
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
                raise rq.Refused("malformed", "gone before it was read") from None
            except aq.Refused as r:
                raise rq.Refused("malformed", r.reason) from None
            req = rq.verify(data, service=service, pins=self.pins, now=now, seen=self.seen, rate=self.rate)
            if req.id != request_id:
                raise rq.Refused("malformed", "its name is not its nonce")
            card = self._attach(req)
            ctx = self._guards(req, card)
            why = second_factor_refusal(req)
            if why:
                raise rq.Refused("second_factor", why)
            if not self.inline and self._backlog.full():
                raise rq.Refused("busy", f"one restore at a time, and {BACKLOG} waiting: nothing is run — ask "
                                         "again in a moment")
        except rq.Refused as r:
            return self._refuse(service, request_id, req, r, now)
        except _Guard as g:
            return self._refuse(service, request_id, req, rq.Refused("guard", str(g)), now)
        except Exception as exc:     # a store that does not read, a bug: said failed, never left « received »
            reason = f"{type(exc).__name__}: {_masked(exc)} — nothing is restored"
            self.say(f"restore queue: {service} {request_id[:8]} failed while judged — {reason}")
            return self._receipt(service, request_id, "failed", request=req, reason=reason, now=now)
        accepted = self._receipt(service, request_id, "accepted", request=req, now=now)
        self.say(f"restore queue: the {service} asks a restore of {_vm(req.resource_id)} — accepted")
        if self.inline:
            return self._take((service, req, ctx), now)
        self._backlog.put_nowait((service, req, ctx))
        self._serve()
        return accepted

    def _attach(self, req: rq.Request) -> dict:
        """The card a restore answers: pending, a restore, on this VM, never anchored — the request
        names its VM at the byte. Raises Refused or _Guard."""
        from glorfindel import approval, escalations
        card = next((e for e in escalations.pending() if e.get("id") == req.card_id), None)
        if card is None:
            raise rq.Refused("card_not_pending", "no card of this id waits")
        why = approval.restore_refusal(card, _vm(req.resource_id))
        if why:
            raise _Guard(why)
        if req.resource_id != card.get("resource_id"):
            raise rq.Refused("card_mismatch")
        return card

    def _guards(self, req: rq.Request, card: dict) -> dict:
        from glorfindel import approval, jobs, restore_plan
        from glorfindel.config import NO_VAULT_MSG, resolve_backup_vault
        if not approval.is_vm_id(req.resource_id):
            raise _Guard(f"{_vm(req.resource_id)[:64]!r} is not a VM's id")
        try:
            before = restore_plan.parse_moment(req.before)
        except ValueError as exc:
            raise _Guard(f"the moment to restore before: {exc}") from None
        if req.service == "bot":
            why = approval.discord_refusal(req.by, self.environ)
            if why:
                raise _Guard(why)
        vault, vault_rg, staging = resolve_backup_vault(None)
        if not vault:
            raise _Guard(NO_VAULT_MSG)
        busy = jobs.restore_in_progress(req.resource_id)
        if busy:
            raise rq.Refused("restore_busy", f"{rq.REFUSALS['restore_busy']}: {busy}")
        return {"before": before, "vault": vault, "vault_rg": vault_rg, "staging": staging}

    def _refuse(self, service: str, request_id: str, req, refused: rq.Refused, now: datetime) -> dict:
        with self._lock:
            self.refused[refused.code] += 1
        self.say(f"restore queue: {service} {request_id[:8]} refused — {refused.code}: {refused.reason[:300]}")
        if refused.critical or refused.code == "seen_store_unavailable":
            self._card(service, refused)
        return self._receipt(service, request_id, "refused", request=req, code=refused.code,
                             reason=refused.reason, now=now)

    def _card(self, service: str, refused: rq.Refused) -> None:
        """A card decided by the code: no model, no action — at most one per service and per hour."""
        key = f"{service}:{'critical' if refused.critical else 'register'}"
        at = time.time()
        with self._lock:
            if at - self._critical_at.get(key, -CRITICAL_EVERY_S) < CRITICAL_EVERY_S:
                return
            self._critical_at[key] = at
        try:
            from glorfindel import escalations
            if refused.critical:
                reason = (f"File de restore de {service} : une demande refusée ({refused.code} — "
                          f"{refused.reason[:300]}). Quelqu'un écrit dans la file de restore de ce service sans "
                          f"être lui, ou la rejoue : examiner l'hôte (qui écrit runs/{service}/restore/), la clé "
                          "épinglée (EREGION_QUEUE_KEYS) et la clé du service. Rien n'est restauré.")
                etype, severity = "queue_tampered", "critical"
            else:
                reason = (f"File de restore : le registre de l'exécuteur ne se lit ou ne s'écrit pas "
                          f"({refused.reason[:300]}) — aucune demande n'est prise tant qu'il ne se tient pas "
                          "(~/.eregion/restore-executor/).")
                etype, severity = "queue_unavailable", "high"
            escalations.record(signal_id=f"restore-queue-{service}-{refused.code}",
                               resource_id=f"~/runs/{service}/restore", action="none", escalation_type=etype,
                               reason=reason, severity=severity, source="real")
        except Exception as exc:
            self.say(f"restore queue: card not written ({exc})")

    # ── The one worker, the restore ──────────────────────────────────────────────────

    def _serve(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._work, daemon=True, name="restore-run")
                self._worker.start()

    def _work(self) -> None:
        while True:
            item = self._backlog.get()
            if item is None:
                return
            with self._lock:
                self._running += 1
            try:
                self._take(item)
            except Exception as exc:
                self.say(f"restore queue: run in error — {type(exc).__name__}: {_masked(exc)}")
            finally:
                with self._lock:
                    self._running -= 1

    def stop(self) -> None:
        """The worker stopped once what waits ahead of it is done (the tests)."""
        self._backlog.put(None)

    def _take(self, item, now: datetime | None = None) -> dict:
        """A request accepted, its turn come: refused when its life ended while it waited (never
        restored late: ``no_slot``), or when its card no longer holds (acknowledged, resolved meanwhile:
        the card read again); else run."""
        service, req, ctx = item
        now = now or self.clock()
        if now >= req.expires_at:
            return self._refuse(service, req.id, req, rq.Refused(
                "no_slot", f"{rq.REFUSALS['no_slot']} (waited past its end of life, "
                           f"{(now - req.expires_at).total_seconds():.0f} s ago)"), now)
        try:
            self._attach(req)                        # the card read again at its turn
        except rq.Refused as r:
            return self._refuse(service, req.id, req, r, now)
        except _Guard as g:
            return self._refuse(service, req.id, req, rq.Refused("guard", str(g)), now)
        return self._run(service, req, ctx)

    def _run(self, service: str, req: rq.Request, ctx: dict) -> dict:
        """The restore, under the VM's restore claim (the CLI's own), with the CLI's own function:
        the receipt ``done`` (started) or ``failed``. Never raises."""
        from glorfindel import jobs
        code, result = "", None
        try:
            with jobs.restore_claim(req.resource_id):
                job = jobs.start_restore(req.resource_id, self.connector, ctx["vault"], ctx["before"],
                                         staging_storage=ctx["staging"], vault_rg=ctx["vault_rg"])
            state, reason = "done", ""
            result = {"status": "started", "job_id": job.get("job_id"),
                      "restore_job_name": job.get("restore_job_name"),
                      "recovery_point_time": job.get("recovery_point_time"),
                      "recovery_point_vault_tier": bool(job.get("recovery_point_vault_tier"))}
        except jobs.RestoreBusy as exc:
            state, code, reason = "failed", "restore_busy", f"{rq.REFUSALS['restore_busy']}: {_masked(exc)}"
        except Exception as exc:
            if getattr(exc, "code", "") == "vault_job_running":
                # A restore of this VM the vault runs already, started elsewhere (Jonathan, 24/11):
                # refused, the VM untouched (the provider reads the vault's jobs before anything).
                state, code, reason = "refused", "vault_job_running", _masked(exc, REASON_CHARS)
                with self._lock:
                    self.refused[code] += 1
            else:
                state, reason = "failed", f"{type(exc).__name__}: {_masked(exc)}"
        self.say(f"restore queue: {service} restore of {_vm(req.resource_id)} → {state}"
                 + (f" ({reason[:200]})" if reason else ""))
        try:
            return self._receipt(service, req.id, state, request=req, code=code, reason=reason, result=result)
        except Exception as exc:
            self.say(f"restore queue: receipt {req.id[:8]} not written ({exc})")
            return {}

    # ── The status, the loop ─────────────────────────────────────────────────────────

    def status(self, now: datetime, force: bool = False) -> dict | None:
        """``runs/restore/status.json``, signed: the keys pinned per service, since when, the refusals
        counted, what runs — and that the second factor is not delivered yet."""
        at = time.time()
        if not force and at - self._last_status < STATUS_EVERY_S:
            return None
        self._last_status = at
        from eregion_core import watch_key
        with self._lock:
            refused, running = dict(sorted(self.refused.items())), self._running
        body = {"pins": {s: (watch_key.fingerprint(self.pins[s]) if s in self.pins else "") for s in rq.SERVICES},
                "pin_errors": [str(e)[:200] for e in self.pin_errors][:10],
                "since": _iso(self.since), "at": _iso(now), "refused": refused,
                "second_factor": "absent (TOT1, #685): every restore from a button is refused",
                "executions": {"running": running, "waiting": self._backlog.qsize(), "backlog": BACKLOG}}
        doc = rq.sign_executor("status", body, self.signer)
        path = rq.receipts_dir(self.root) / rq.STATUS_NAME
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        channel_reader.write_file(path, json.dumps(doc, sort_keys=True), mode=0o644)
        self._sweep(at)
        return doc

    def _sweep(self, at: float) -> None:
        try:
            entries = list(os.scandir(rq.receipts_dir(self.root)))
        except OSError:
            return
        for e in entries:
            service, _, rest = e.name.partition("-")
            if service not in rq.SERVICES or not e.name.endswith(".json"):
                continue
            try:
                if at - e.stat(follow_symlinks=False).st_mtime < RECEIPT_KEEP_S:
                    continue
                if (rq.request_dir(service, self.root) / rest).exists():
                    continue
                os.unlink(e.path)
            except OSError:
                continue
        cutoff = at - RECEIPT_KEEP_S
        self._judged = {k: v for k, v in self._judged.items() if v > cutoff}

    def run_forever(self) -> None:
        self.recover()
        self.status(self.clock(), force=True)
        while True:
            try:
                self.poll()
            except Exception as exc:
                self.say(f"restore queue: pass in error — {type(exc).__name__}: {_masked(exc)}")
            time.sleep(POLL_S)


def restore_connector(environ=None):
    """The connector the executor restores with, under its own principal given explicitly — never
    DefaultAzureCredential's chain, which would reach the VM's managed identity (the watch's)."""
    from glorfindel.actions import AzureConnector
    from glorfindel.providers.azure.connector import explicit_credential
    connector = AzureConnector(dry_run=False)
    connector.explicit_credential = explicit_credential(os.environ if environ is None else environ)
    return connector


def main(argv: list[str] | None = None) -> int:
    """``python -m glorfindel.restore_executor [<runs>]``: the executor, or its refusal to start."""
    import sys
    from eregion_core import watch_key
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else None
    why = startup_refusal()
    if why:
        print(f"✗ restore executor: {why}", file=sys.stderr)
        return 1
    try:
        fd = hold()
    except SecondExecutor as exc:
        print(f"✗ restore executor: {exc}", file=sys.stderr)
        return 1
    try:
        signer = watch_key.load_or_create(rq.executor_dir(), name=watch_key.RESTORE_KEY_FILE)
    except watch_key.KeyUnavailable as exc:
        print(f"✗ restore executor: its key is unavailable — {exc}", file=sys.stderr)
        os.close(fd)
        return 1
    pins, wrong = aq.pinned_keys()
    for line in aq.pin_problems(pins, wrong):
        print(f"restore executor: {line}", flush=True)
    executor = RestoreExecutor(signer, restore_connector(), root=root, pins=pins, pin_errors=wrong,
                               say=lambda m: print(m, flush=True))
    print(f"restore executor: runs/console/restore, runs/bot/restore → runs/restore (key "
          f"{signer.fingerprint}) — the second factor (TOT1) is not delivered: every request is refused",
          flush=True)
    executor.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
