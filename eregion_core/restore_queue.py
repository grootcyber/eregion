"""FS1g (#1127, docs/design/file-actions-signee.md, decision Q2 of 04/11): the restore's own queue —
its requests, their verification, and the restore executor's receipts. The watch never reads it: the
restore is in none of its verbs, and never will be (SEC7). A fourth service, the restore executor
(glorfindel/restore_executor.py), alone holding Restore and Restore Neutralize, reads it.

**A request** is one JSON file the console or the bot writes in its own directory of ``runs/``
(``runs/console/restore/``, ``runs/bot/restore/``): exactly ``REQUEST_FIELDS``, each of its kind, at
most ``action_queue.MAX_BYTES``. Signed by the service's key — the same key as its requests of the
action queue (decision Q1) — under another domain, ``DOMAIN_REQUEST``: a restore's signature never
reads as a request of the watch's queue, nor the reverse. It names the card the restore answers
(``card``, a restore card: its id) and the moment to restore before (``before``, SEC4c) — never a
recovery point, never a verb.

**The verification** (``verify``), from the cheapest to the dearest, no network, no call to the
cloud — the steps of the action queue (§2.8), under this domain: read bounded, the form, a
signature, the key pinned for this directory (``EREGION_QUEUE_KEYS``, the executor's own copy), the
signature holds, the service, the time (``SKEW_S``, ``MAX_LIFETIME_S``), the rate, the nonce claimed
in the executor's own register (written durably, before anything runs), the identifiers in ASCII.

**The receipts** (``runs/restore/<service>-<id>.json``) and the status (``runs/restore/status.json``)
are the executor's, signed by its own key under ``DOMAIN_EXECUTOR`` — never the watch's domain, so
an executor's receipt never reads as the watch's. The console and the bot read them from the mount
(one host); with the executor's key pinned (``KEY_ENV``), only signed by it.

D1: the shared core — the console, the bot and the executor read this module, none importing another.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from eregion_core import action_queue as aq
from eregion_core import watch_key

VERSION = 1
DOMAIN_REQUEST = "eregion.restore-request/1"
DOMAIN_EXECUTOR = "eregion.restore-queue/1"
KIND = "restore_request"
EXECUTOR_KINDS = ("receipt", "status")
SERVICES = aq.SERVICES
WRITER = "restore"                  # runs/restore/: the executor's receipts and its status
SUBDIR = "restore"                  # runs/<service>/restore/: a service's requests

REQUEST_FIELDS = ("v", "kind", "id", "service", "by", "resource_id", "card", "before",
                  "issued_at", "expires_at", "key", "sig")
MAX_LIFETIME_S = aq.MAX_LIFETIME_S
SKEW_S = aq.SKEW_S
RATE_PER_MIN = 6                    # a restore is a rare gesture: six a minute per service, at most
RECEIPT_BYTES = aq.RECEIPT_BYTES
RECEIPT_STATES = aq.RECEIPT_STATES
FINAL_STATES = aq.FINAL_STATES
STATUS_NAME = aq.STATUS_NAME
KEY_ENV = "EREGION_RESTORE_KEY"     # the executor's public key, pinned by a reader on another host
# The restore's own flag (Jonathan, 24/11): the action queue may switch on by default (FS1c) without
# touching today's Restore button — this one is turned on once TOT1 and the principal are there.
FLAG_ENV = "EREGION_RESTORE_QUEUE"


def enabled(environ=None) -> bool:
    """The console and the bot deposit their Restore for the executor, and the executor starts, only
    behind ``EREGION_RESTORE_QUEUE=1`` — false by default, whatever ``EREGION_ACTION_QUEUE`` says."""
    return (os.environ if environ is None else environ).get(FLAG_ENV, "") == "1"

# The tests point it at their own tmp dir (tests/unit/conftest.py): never the operator's.
EXECUTOR_DIR: Path | None = None

# The refusals of the restore's queue: the action queue's words where the case is the same, and
# its own (the card of a restore, the second factor, a restore already running).
_SHARED = ("malformed", "unsigned", "no_key_pinned", "unknown_key", "bad_signature", "wrong_service",
           "not_yet_valid", "too_long", "expired", "replayed", "seen_store_unavailable", "rate_limited",
           "card_not_pending", "guard", "not_ascii", "busy", "no_slot")
REFUSALS = {code: aq.REFUSALS[code] for code in _SHARED}
REFUSALS.update({
    "card_mismatch": "the request does not name the card's VM, at the byte: the restore runs on the card's",
    # §4.2 of docs/design/banc-autonome.md: a restore from a button asks for the operator's one-time
    # code (TOT1, #685) — until it exists, refused, and said.
    "second_factor": ("a restore from a button asks for the operator's one-time code (TOT1, #685), which "
                      "is not delivered yet: nothing is restored — from the workstation, `make "
                      "bench-restore`, or `glorfindel restore <vm> --before <ISO 8601>` under the restore "
                      "pair"),
    "restore_busy": "another restore of this VM is running or about to (one at a time, SEC4c)",
    # Jonathan, 24/11: a restore the vault runs already, started from another host (`make
    # bench-restore` from the workstation) that this host's claim cannot see — read before anything.
    "vault_job_running": "the vault runs a restore of this VM already, or its jobs do not read: nothing is touched",
    "interrupted": ("the restore executor stopped while it judged or ran this request: nothing is run "
                    "again — check the VM on Azure (its disks, the vault's jobs), then ask again"),
})
# The refusals that say someone writes in a service's restore queue who should not: a card decided
# by the code, never by a model.
CRITICAL = frozenset({"unsigned", "unknown_key", "bad_signature", "wrong_service", "replayed"})
PIN_GESTURE = aq.PIN_GESTURE.replace("at the watch", "at the restore executor (and the watch)")


class Refused(Exception):
    """A restore request the executor does not take: ``code`` (one of ``REFUSALS``), its reason."""

    def __init__(self, code: str, detail: str = ""):
        if code not in REFUSALS:
            raise ValueError(f"not a refusal of the restore queue: {code!r}")
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {self.reason}")

    @property
    def reason(self) -> str:
        return self.detail or REFUSALS[self.code]

    @property
    def critical(self) -> bool:
        return self.code in CRITICAL


@dataclass(frozen=True)
class Request:
    """A restore request verified up to its identifiers."""
    id: str
    service: str
    by: dict
    resource_id: str
    card_id: str
    before: str
    issued_at: datetime
    expires_at: datetime
    key: str


def executor_dir() -> Path:
    """The executor's own directory: its key, its register of nonces, its lock — mounted by it alone,
    never under ~/.glorfindel nor runs/."""
    return EXECUTOR_DIR if EXECUTOR_DIR is not None else Path.home() / ".eregion" / "restore-executor"


def request_dir(service: str, root=None) -> Path:
    """``runs/<service>/restore/``: the service's own directory of runs/ (SEC18)."""
    return aq.request_dir(service, root).parent / SUBDIR


def receipts_dir(root=None) -> Path:
    """``runs/restore/``: the executor's own directory — its receipts and its status."""
    from eregion_core import runs_layout
    return runs_layout.dir_of(WRITER, root)


def receipt_path(service: str, request_id: str, root=None) -> Path:
    if service not in SERVICES or not aq._ID.fullmatch(str(request_id)):
        raise ValueError(f"not a restore request: {service!r} {str(request_id)[:40]!r}")
    return receipts_dir(root) / f"{service}-{request_id}.json"


# ── The request ─────────────────────────────────────────────────────────────────────

def new_request(signer: watch_key.Signer, *, service: str, resource_id: str, card: str, before: str,
                by: Mapping[str, str] | None = None, now: datetime | None = None,
                lifetime_s: float = MAX_LIFETIME_S, nonce: str | None = None) -> dict:
    """A restore request, signed by ``signer`` (the service's key) under DOMAIN_REQUEST."""
    import secrets
    now = now or datetime.now(timezone.utc)
    body = {
        "v": VERSION, "kind": KIND, "id": nonce or secrets.token_hex(16), "service": service,
        "by": {f: str((by or {}).get(f, "")) for f in aq.BY_FIELDS},
        "resource_id": resource_id, "card": card, "before": before,
        "issued_at": aq._iso(now), "expires_at": aq._iso(now + timedelta(seconds=lifetime_s)),
        "key": signer.fingerprint,
    }
    body["sig"] = signer.sign(DOMAIN_REQUEST, body)
    return body


def _form(doc: dict) -> tuple[datetime, datetime]:
    """Exactly its fields, each of its kind (``key`` and ``sig``: the signature's step)."""
    extra = sorted(set(doc) - set(REQUEST_FIELDS))
    if extra:
        raise Refused("malformed", f"a field it never holds: {', '.join(str(f)[:40] for f in extra)}")
    missing = [f for f in REQUEST_FIELDS if f not in doc and f not in aq.SIGNATURE_FIELDS]
    if missing:
        raise Refused("malformed", f"lacks {', '.join(missing)}")
    if isinstance(doc["v"], bool) or doc["v"] != VERSION:
        raise Refused("malformed", f"not version {VERSION}")
    if doc["kind"] != KIND:
        raise Refused("malformed", "not a restore request (kind)")
    if not isinstance(doc["id"], str) or not aq._ID.fullmatch(doc["id"]):
        raise Refused("malformed", "its id is not 128 bits in hex")
    for name in ("service", "resource_id", "card", "before"):
        if not isinstance(doc[name], str):
            raise Refused("malformed", f"{name} is not a string")
    if not doc["card"]:
        raise Refused("malformed", "a restore from a button goes through its card: card is empty")
    by = doc["by"]
    if not isinstance(by, dict) or set(by) != set(aq.BY_FIELDS) or not all(isinstance(v, str) for v in by.values()):
        raise Refused("malformed", f"by is not exactly {', '.join(aq.BY_FIELDS)}, as strings")
    try:
        issued = aq._time(doc["issued_at"], "issued_at")
        expires = aq._time(doc["expires_at"], "expires_at")
    except aq.Refused as r:
        raise Refused("malformed", r.reason) from None
    if expires <= issued:
        raise Refused("malformed", "expires_at is not after issued_at")
    if "key" in doc and not isinstance(doc["key"], str):
        raise Refused("malformed", "key is not a string")
    if doc.get("sig") is not None and "key" not in doc:
        raise Refused("malformed", "signed without naming its key")
    return issued, expires


def verify(data, *, service: str, pins: Mapping[str, bytes], now: datetime, seen, rate) -> Request:
    """A restore request read from ``runs/<service>/restore/``, verified — or ``Refused``. ``pins``:
    the services' keys the executor pins (``action_queue.pinned_keys``, its own environment), never a
    key read in the queue. No network, no call to the cloud; ``seen`` (the executor's register) is
    written before anything is run."""
    if service not in SERVICES:
        raise ValueError(f"not a service of the restore queue: {service!r}")
    try:
        doc = aq._parse(data)
    except aq.Refused as r:
        raise Refused("malformed", r.reason) from None
    issued, expires = _form(doc)
    if doc.get("sig") is None:
        raise Refused("unsigned", "unsigned: someone writes in this service's restore queue without its key")
    pin = pins.get(service)
    if pin is None:
        raise Refused("no_key_pinned", f"no key pinned for the {service}: {PIN_GESTURE}")
    want, said = watch_key.fingerprint(pin), doc["key"]
    if said != want:
        for other, key in pins.items():
            if other != service and watch_key.fingerprint(key) == said and watch_key.holds(key, DOMAIN_REQUEST, doc):
                raise Refused("wrong_service", f"signed by the {other}'s key, in the {service}'s restore queue")
        raise Refused("unknown_key", f"signed by another key ({watch_key._short(said)}) than the one pinned "
                                     f"for the {service} ({watch_key._short(want)}): a key drawn again, or "
                                     "another hand")
    if not watch_key.holds(pin, DOMAIN_REQUEST, doc):
        raise Refused("bad_signature")
    if doc["service"] != service:
        raise Refused("wrong_service", f"a request of {str(doc['service'])[:20]!r} in the {service}'s restore queue")
    if issued - now > timedelta(seconds=SKEW_S):
        raise Refused("not_yet_valid", f"issued {(issued - now).total_seconds():.0f} s ahead of the executor's "
                                       f"clock (at most {SKEW_S} s)")
    if expires - issued > timedelta(seconds=MAX_LIFETIME_S):
        raise Refused("too_long", f"valid for {(expires - issued).total_seconds():.0f} s (at most "
                                  f"{MAX_LIFETIME_S} s)")
    if now >= expires:
        raise Refused("expired", f"expired {(now - expires).total_seconds():.0f} s ago: the executor was "
                                 "stopped or slow — never restored late")
    if not rate.take(service, now):
        raise Refused("rate_limited", f"more than {rate.per_min} restore requests of this service in a minute")
    try:
        fresh = seen.claim(doc["id"], expires + timedelta(seconds=SKEW_S), now)
    except (OSError, ValueError) as e:
        raise Refused("seen_store_unavailable", f"{REFUSALS['seen_store_unavailable']} ({str(e)[:120]})") from None
    if not fresh:
        raise Refused("replayed")
    for name in ("resource_id", "card", "before"):
        if not doc[name].isascii():
            raise Refused("not_ascii", f"{name} carries a character out of ASCII: never an identifier of Azure")
    return Request(id=doc["id"], service=service, by=dict(doc["by"]), resource_id=doc["resource_id"],
                   card_id=doc["card"], before=doc["before"], issued_at=issued, expires_at=expires, key=said)


def seen_file() -> aq.SeenFile:
    """The executor's register of nonces — its own, beside its key, never the watch's."""
    return aq.SeenFile(executor_dir() / "seen.json")


def rate() -> aq.Rate:
    return aq.Rate(RATE_PER_MIN)


# ── What the executor signs ────────────────────────────────────────────────────────────

def sign_executor(kind: str, body: dict, signer: watch_key.Signer) -> dict:
    """A receipt or a status of the executor, under DOMAIN_EXECUTOR, its ``kind`` signed."""
    if kind not in EXECUTOR_KINDS:
        raise ValueError(f"not a kind the restore executor signs: {kind!r}")
    out = {k: v for k, v in body.items() if k not in aq.SIGNATURE_FIELDS}
    out["v"], out["kind"], out["key"] = VERSION, kind, signer.fingerprint
    out["sig"] = signer.sign(DOMAIN_EXECUTOR, out)
    return out


def executor_refusal(body, kind: str, public: bytes) -> str:
    """Why ``body`` is not a ``kind`` the executor whose public key this is signed — "" when it is."""
    if not isinstance(body, dict):
        return "not a JSON object"
    if body.get("kind") != kind:
        return f"not a {kind} ({str(body.get('kind'))[:20]!r})"
    if body.get("key") != watch_key.fingerprint(public):
        return "not signed by the restore executor's key"
    if not watch_key.holds(public, DOMAIN_EXECUTOR, body):
        return "its signature does not hold"
    return ""


def pinned_key() -> bytes | None:
    """The executor's public key a reader pins (``EREGION_RESTORE_KEY``) — None when none, or not one."""
    text = os.environ.get(KEY_ENV, "").strip()
    if not text:
        return None
    key, _ = watch_key.parse_pin(text)
    return key


# ── A service's side: deposit, follow, withdraw ────────────────────────────────────────

def deposit(service: str, resource_id: str, *, card: str, before: str, by: Mapping[str, str], root=None) -> dict:
    """A service's restore as a request, signed by its key (drawn at its first use), written in
    ``runs/<service>/restore/`` (beside, then renamed; 0600) and never awaited: ``{"request": id}``,
    or ``{"error": …}`` when the service could not ask. Its fate is read by ``follow``."""
    from eregion_core import channel_reader
    try:
        signer = aq.load_service_key(service)
    except watch_key.KeyUnavailable as e:
        return {"error": f"the {service}'s key of the action queue is unavailable: {e}"}
    request = new_request(signer, service=service, resource_id=resource_id, card=card, before=before, by=by)
    directory = request_dir(service, root)
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        channel_reader.write_file(directory / f"{request['id']}.json", json.dumps(request, separators=(",", ":")),
                                  mode=0o600)
    except OSError as e:
        return {"error": f"the restore request could not be written in runs/{service}/{SUBDIR}/: {e}"}
    return {"request": request["id"]}


def withdraw(service: str, request_id: str, root=None) -> bool:
    """The service removes its own request once its receipt is read — True for the one call that did."""
    if not aq._ID.fullmatch(str(request_id)):
        return False
    try:
        (request_dir(service, root) / f"{request_id}.json").unlink()
    except FileNotFoundError:
        return False
    return True


def waiting(service: str, root=None, limit: int = 64) -> list[str]:
    """The ids of the service's restore requests still in its directory (at most ``limit``)."""
    out = []
    try:
        with os.scandir(request_dir(service, root)) as it:
            for e in it:
                stem = e.name[:-5] if e.name.endswith(".json") else ""
                if aq._ID.fullmatch(stem):
                    out.append(stem)
                    if len(out) >= limit:
                        break
    except OSError:
        return []
    return out


def receipt_said(service: str, request_id: str, *, root=None, public: bytes | None = None) -> tuple[dict | None, str]:
    """(the executor's receipt of a request, "") — or (None, why there is none to believe): "" while
    there is none; else unreadable, another request's, or (``public``: the executor's key pinned)
    signed by another key."""
    from eregion_core import channel_reader
    try:
        doc = json.loads(channel_reader.read_file(receipt_path(service, request_id, root), RECEIPT_BYTES))
    except FileNotFoundError:
        return None, ""
    except (OSError, ValueError, RecursionError) as e:
        return None, f"a receipt of the restore executor is there but unreadable ({type(e).__name__})"
    if (not isinstance(doc, dict) or doc.get("kind") != "receipt" or doc.get("request") != request_id
            or doc.get("service") != service or doc.get("state") not in RECEIPT_STATES):
        return None, "a receipt of the restore executor is there but is not this request's"
    if public is not None:
        why = executor_refusal(doc, "receipt", public)
        if why:
            return None, f"a receipt is there, but {why} ({KEY_ENV} pinned here): another hand, or a key drawn again"
    return doc, ""


def own_request(service: str, request_id: str, root=None) -> dict | None:
    """A service's own request as it wrote it — None when gone, or not one (its card and its VM,
    for what the service says of a request the executor never answered)."""
    from eregion_core import channel_reader
    if not aq._ID.fullmatch(str(request_id)):
        return None
    try:
        doc = json.loads(channel_reader.read_file(request_dir(service, root) / f"{request_id}.json", aq.MAX_BYTES))
    except (OSError, ValueError, RecursionError):
        return None
    return doc if isinstance(doc, dict) else None


def _issued(service: str, request_id: str, root=None) -> datetime | None:
    doc = own_request(service, request_id, root) or {}
    try:
        when = datetime.fromisoformat(doc["issued_at"])
    except (ValueError, KeyError, TypeError):
        return None
    return when if when.tzinfo is not None else None


TAKE_S = MAX_LIFETIME_S + SKEW_S
NOT_TAKEN = (f"the restore executor did not take the request in {MAX_LIFETIME_S} s — is it running "
             f"(docker compose --profile restore), with {FLAG_ENV}=1 and this service's key pinned "
             f"({aq.KEYS_ENV})?")


def follow(service: str, request_id: str, *, root=None, public: bytes | None = None,
           now: datetime | None = None) -> dict:
    """Where a restore request stands, read once — never waiting: the receipt's state, or
    ``waiting`` (within its life), ``not_taken``, ``untrusted``, ``unknown``. ``final``: nothing more
    will come of it."""
    if not aq._ID.fullmatch(str(request_id)):
        return {"request": "", "state": "unknown", "final": True, "error": "not a restore request"}
    doc, why = receipt_said(service, request_id, root=root, public=public)
    if doc is not None:
        return {"request": request_id, "state": doc["state"], "final": doc["state"] in FINAL_STATES,
                "receipt": doc}
    if why:
        return {"request": request_id, "state": "untrusted", "final": True, "error": why}
    issued = _issued(service, request_id, root)
    if issued is None:
        return {"request": request_id, "state": "unknown", "final": True,
                "error": "no restore request of this id here, and no receipt"}
    if ((now or datetime.now(timezone.utc)) - issued).total_seconds() > TAKE_S:
        return {"request": request_id, "state": "not_taken", "final": True, "error": NOT_TAKEN}
    return {"request": request_id, "state": "waiting", "final": False}
