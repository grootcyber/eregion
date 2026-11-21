"""SLF1 (#929): the watch's own return channel, set aside from the exfiltration rule — its own
writes only, and said.

The hosted watch publishes its return channel (eregion_core/watch_channel.py,
``EREGION_WATCH_CHANNEL``) in a blob container: ``heartbeat.json`` and
``detections/<run_id>/<signal_id>.json``. Those writes (PutBlob, from the watch's private
address) made ``data-exfiltration-blob`` fire about every 20 minutes on Imladris — a hundred
recurrences in three days, unattributed (the watch's host is no watched VM).

The rule's query keeps, in each row (one per caller address and account), who wrote what:
``BlobWriters``, one entry per container and writer — its writes, its bytes, and how many of them
are objects a return channel holds (``known``). Here, before any routing or signal, an entry is set
aside only when **all** of it holds:

- the account is the configured channel's, and the container is its container;
- the writer (``RequesterObjectId``) is the identity the watch writes with — the ``oid`` of its own
  storage token (``Publisher.writer``), never a value written by anyone;
- every write of the entry is one of those objects (``known == writes``).

Another write from the same address, a write to another container of the same account, a write in
the container by another identity: they stay in the row, and the row stays a card. Without a
channel configured, or the watch's identity not read: nothing is set aside, and the second is said.
The row of a card then has its counts less the watch's own writes, and ``BlobWriters`` is taken off
— always, channel or not: the row is the one of before SLF1, column for column, and what the model
reads (``_build_user_message``) is unchanged to the byte. What is set aside is counted
(``rule_status.json``, ``own_channel``), shown on the rule's line in the console, and written to the
watch's log; never silent.

ATT1 (#936): only for the shipped rule — ``data-exfiltration-blob``, known by its name **and** the
fingerprint of its query as the base ships it (``is_shipped``) —, never for a rule of the client's
layer that would compute a wider ``Known`` under that name (an override, a copy that changed its
query): its rows stay cards, the column taken off all the same. A copy of the shipped rule to the
letter (WL1, ``base_sha256``) computes the same ``Known``: set aside as the shipped one.

SLF1b (#976): the SDK (``azure-monitor-query``) hands a ``dynamic`` column on as the API sent it, its
JSON text — ``BlobWriters`` arrived as a ``str`` on Imladris (20/11), and nothing was set aside: the
tests of SLF1 passed a Python list. The column is read in either form (`writers_of`): a list, or a
JSON text of at most ``WRITERS_MAX`` characters that decodes to one. A text unreadable, longer, or
that is not a list of objects sets nothing aside, never raises, and is said: ``unparsed``, counted
beside ``unread`` in the rule's status.

SLF2 (#1010), two more forms seen on the 21/11:

- **Orodruin's exercise channel.** Orodruin publishes its windows and its run reports in the
  exercise channel (``EREGION_EXERCISE_CHANNEL``, eregion_core/exercise_channel.py) — a PutBlob from
  its private address, on the account of the watch's channel. An entry of BlobWriters is set aside
  only when all of it holds: the account is the exercise channel's, the container is its container,
  and the writer is Orodruin's identity — the object id of its managed identity's principal,
  ``EREGION_ORODRUIN_PRINCIPAL_ID`` in the watch's environment (Imladris's host.env, never the
  repository), never an address. Without that id (or the channel), nothing is set aside, and the
  rule's status says why (``exercise_config``); an id that is no object id, the same.
- **The watch that restarts.** The watch keeps, in its own state (``~/.glorfindel/own_channel.json``),
  its identity and when it wrote in its channel over the rule's window (``LOOKBACK_S``). A watch that
  starts and cannot read its own identity yet reads the record of the one before: the writes of
  **that** identity, in **that** container of **that** account, are set aside up to the number the
  record holds in the window (``Channel.budget``) — never more, never another identity's, never once
  its own identity is read (then the record is not used: an identity changed is another identity).
  A record absent, unreadable, of another channel or of nothing in the window: nothing stands in,
  the identity is « unread », as before. Counted (``restart``), said.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

WRITERS = "BlobWriters"
# ATT1: the one rule whose rows may be set aside, as the base ships it.
SHIPPED_RULE = "data-exfiltration-blob"
REASON = ("the watch's own return channel: its identity, the container of EREGION_WATCH_CHANNEL, "
          "the objects it writes there (SLF1)")
# SLF1b: the longest BlobWriters text decoded. The query keeps 64 entries at most (`make_list(…, 64)`),
# each a container, a writer's object id and three counts — a few hundred characters: 64 Ki characters is far
# above; a text past it is not read (nothing set aside, said). ROW1: the bound of every dynamic text
# `json_of` reads — a column of an aggregated row past it stays in the row's identity, as before.
WRITERS_MAX = 64 * 1024
# Azure's container names: 3 to 63 of lowercase letters, digits and single hyphens.
_CONTAINER = re.compile(r"^(?=.{3,63}$)[a-z0-9]+(?:-[a-z0-9]+)*$")
# SLF2: Orodruin's exercise channel — the variable naming the identity that writes there.
EXERCISE_ENV = "EREGION_EXERCISE_CHANNEL"
ORODRUIN_ENV = "EREGION_ORODRUIN_PRINCIPAL_ID"
EXERCISE_REASON = ("Orodruin's exercise channel: its identity (EREGION_ORODRUIN_PRINCIPAL_ID), the container of "
                   "EREGION_EXERCISE_CHANNEL, its account (SLF2)")
RESTART_REASON = ("the watch before this one: its identity, its container, as many writes as its record holds "
                  "in the rule's window (SLF2)")
# SLF2: the watch's record of its own writes, read by the next one at its start.
_STATE_FILE = Path.home() / ".glorfindel" / "own_channel.json"
# The rule's window (`ago(5m)`) and a minute of margin: a write older than this is in no row of it.
LOOKBACK_S = 6 * 60
# The record holds at most this many writes (a heartbeat a minute, the detections of a window); past
# it, the oldest leave — fewer stand in, never more. And its file, at most STATE_MAX bytes read.
MAX_WRITES = 512
STATE_MAX = 64 * 1024
_GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Channel:
    """The return channel the watch writes: its account, its container, and the object id of the
    identity it writes with ("" when it could not be read). ``budget`` (SLF2): None when that identity
    is this watch's own, read; else the number of writes the record of the watch before this one holds
    in the rule's window — at most that many set aside."""
    account: str
    container: str
    writer: str = ""
    budget: int | None = None


def guid(value) -> str:
    """``value`` in lower case when it is an object id (a GUID), else ""."""
    v = str(value or "").strip().lower()
    return v if _GUID.match(v) else ""


def parse_url(url: str) -> tuple[str, str] | None:
    """(account, container) of a return channel's URL (``https://<account>.blob.core.windows.net/
    <container>``), or None — the URL refused as the channel refuses it, a path that is not one
    container, a query or a fragment."""
    from eregion_core.exercise_channel import account_of
    url = (url or "").strip().rstrip("/")
    account = account_of(url)
    if not account:
        return None
    parts = urlsplit(url)
    container = parts.path.strip("/")
    if parts.query or parts.fragment or not _CONTAINER.match(container):
        return None
    return account, container


@dataclass(frozen=True)
class Previous:
    """SLF2: the record a watch kept of its own writes — its identity, and when it wrote."""
    writer: str
    writes: tuple[datetime, ...] = ()

    def vouched(self, now: datetime) -> int:
        """How many of its writes fall in the rule's window at ``now`` (one dated after now: none)."""
        return sum(1 for w in self.writes if now - timedelta(seconds=LOOKBACK_S) <= w <= now)


def _when(value) -> datetime | None:
    """An ISO date with its offset, else None."""
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        return None
    return at if at.tzinfo is not None else None


def load_previous(account: str, container: str, path: Path | None = None) -> Previous | None:
    """SLF2: the record of the watch before this one, for this very channel — None when there is none,
    or it cannot be read whole: bigger than STATE_MAX, no JSON object, another account or container, a
    writer that is no object id, a list of writes that is not one of dates (or longer than MAX_WRITES).
    An unreadable record never stands in. Never raises."""
    path = _STATE_FILE if path is None else path
    try:
        with open(path, "rb") as f:
            data = f.read(STATE_MAX + 1)
        if len(data) > STATE_MAX:
            return None
        raw = json.loads(data)
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(raw, dict) or raw.get("account") != account or raw.get("container") != container:
        return None
    writer = raw.get("writer")
    if not isinstance(writer, str) or guid(writer) != writer:
        return None
    writes = raw.get("writes")
    if not isinstance(writes, list) or len(writes) > MAX_WRITES:
        return None
    times = [_when(w) for w in writes]
    if any(t is None for t in times):
        return None
    return Previous(writer, tuple(times))


class Recorder:
    """SLF2: this watch's record of its own writes, kept for the next one — written after each write
    its publisher makes, once its identity is read; the writes past the rule's window leave it."""

    def __init__(self, account: str, container: str, writer: Callable[[], str],
                 previous: Previous | None = None, path: Path | None = None):
        self.account, self.container, self._writer = account, container, writer
        self._path = path
        self._lock = threading.Lock()
        self._oid = previous.writer if previous is not None else ""
        self._writes = list(previous.writes) if previous is not None else []

    def wrote(self, _name: str = "") -> None:
        """A write acknowledged: kept under this watch's identity. Never raises (the publisher's)."""
        try:
            oid = guid(self._writer())
        except Exception:
            return
        if not oid:
            return
        now = _now()
        with self._lock:
            if oid != self._oid:
                self._oid, self._writes = oid, []
            keep = [w for w in self._writes if now - timedelta(seconds=LOOKBACK_S) <= w <= now]
            self._writes = (keep + [now])[-MAX_WRITES:]
            doc = {"account": self.account, "container": self.container, "writer": oid,
                   "writes": [w.isoformat() for w in self._writes]}
            try:
                _save_state(doc, self._path)
            except Exception:
                pass


def _save_state(doc: dict, path: Path | None = None) -> None:
    """Atomic write (tmp + rename), as the rule's status."""
    path = _STATE_FILE if path is None else path
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".own_channel.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def of_publisher(publisher, *, previous: Previous | None | bool = True,
                 now: Callable[[], datetime] = _now) -> Callable[[], Channel | None] | None:
    """What the RulePoller reads at each pass: the channel this publisher writes, with its writer.
    None for no storage channel (a local channel of verdicts writes no blob). SLF2: the record of the
    watch before this one read once, here (``previous``: True reads it from the state; a test hands its
    own); this publisher's writes recorded for the next one."""
    parsed = parse_url(str(getattr(publisher, "channel", "") or ""))
    writer = getattr(publisher, "writer", None)
    if parsed is None or not callable(writer):
        return None
    account, container = parsed
    if previous is True:
        previous = load_previous(account, container)
    previous = previous if isinstance(previous, Previous) else None
    try:
        publisher.on_written = Recorder(account, container, writer, previous).wrote
    except Exception:
        pass

    def current() -> Channel | None:
        try:
            oid = str(writer() or "")
        except Exception:
            oid = ""
        if oid or previous is None:
            return Channel(account, container, oid)
        # SLF2: this watch's identity not read yet — the one before stands in, its writes only, as
        # many as its record holds in the window; none in it: unread, as before.
        n = previous.vouched(now())
        return Channel(account, container, previous.writer, budget=n) if n > 0 else Channel(account, container, "")
    return current


def of_env(env=None) -> tuple[Channel | None, str]:
    """SLF2: Orodruin's exercise channel, as the watch's environment declares it — (the channel and
    Orodruin's identity, "") when both are there; else (None, why): ``unset`` (the channel declared,
    not the identity), ``malformed`` (an identity that is no object id), ``no channel`` (the identity
    declared, the channel not, or a URL the channel refuses). Neither declared: (None, "") — no
    exercise channel on this watch. Never raises."""
    env = os.environ if env is None else env
    url = str(env.get(EXERCISE_ENV) or "").strip()
    raw = str(env.get(ORODRUIN_ENV) or "").strip()
    if not url and not raw:
        return None, ""
    parsed = parse_url(url) if url else None
    if parsed is None:
        return None, "no channel"
    if not raw:
        return None, "unset"
    oid = guid(raw)
    if not oid:
        return None, "malformed"
    return Channel(parsed[0], parsed[1], oid), ""


_EXERCISE: tuple[Channel | None, str] = (None, "")


def register_exercise(exercise: tuple[Channel | None, str]) -> None:
    """Orodruin's exercise channel, for the RulePoller and the poll of an attack_started (`glorfindel
    watch`, from its environment at its start)."""
    global _EXERCISE
    _EXERCISE = exercise


def current_exercise() -> tuple[Channel | None, str]:
    """The exercise channel registered and its problem; (None, "") when none. Never raises."""
    return _EXERCISE


_SOURCE: Callable[[], Channel | None] | None = None


def register(source: Callable[[], Channel | None] | None) -> None:
    """The watch's channel, for the RulePoller and the poll of an attack_started (`glorfindel
    watch`); None: no channel, nothing set aside."""
    global _SOURCE
    _SOURCE = source


def current() -> Channel | None:
    """The channel registered, or None. Never raises."""
    try:
        return _SOURCE() if _SOURCE is not None else None
    except Exception:
        return None


def query_sha256(query) -> str:
    """sha256 of a rule's query, as text, to the byte."""
    return hashlib.sha256(str(query or "").encode("utf-8")).hexdigest()


@functools.lru_cache(maxsize=4)
def _shipped_sha256(path: str) -> str:
    from glorfindel.detection_rules import _named, _read_layer
    rule = next((r for r in _named(_read_layer(Path(path)).get("rules")) if r.get("name") == SHIPPED_RULE),
                None)
    return query_sha256(rule.get("query")) if isinstance(rule, dict) and rule.get("query") else ""


def shipped_sha256() -> str:
    """The fingerprint of the shipped rule's query, read from the base shipped with Glorfindel
    (``detection_rules.shipped_rules_path``); "" when it cannot be read — then nothing is set aside."""
    try:
        from glorfindel.detection_rules import shipped_rules_path
        return _shipped_sha256(str(shipped_rules_path()))
    except Exception:
        return ""


def is_shipped(query, name: str = SHIPPED_RULE) -> bool:
    """ATT1 (#936): the rule whose rows `settle` may set aside — named as the shipped one, its query
    the shipped one to the byte. Never a rule of the client's layer that changed it (a ``Known``
    wider than the channel's objects, another container, any writer). An `attack_started` names no
    rule: its query alone says it (`name` left to the shipped one's)."""
    sha = shipped_sha256()
    return bool(sha) and name == SHIPPED_RULE and query_sha256(query) == sha


def _count(value) -> int | None:
    """A count from the row: an int (a float that is one, as JSON may read it), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def json_of(value):
    """What the JSON text of a ``dynamic`` column decodes to, as the SDK hands the column on (SLF1b):
    None when the value is not a text, is longer than ``WRITERS_MAX`` or does not decode (a JSON
    ``null`` reads as None too). Bounded, never raises: `writers_of` reads BlobWriters by it, and
    `detection_rules._row_identity` the other columns of an aggregated row (ROW1, #1002)."""
    if isinstance(value, str):
        if len(value) > WRITERS_MAX:
            return None
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
        return value
    return None


def writers_of(value) -> list[dict] | None:
    """BlobWriters as a list of objects (SLF1b): the list itself, or its JSON text — the SDK hands a
    ``dynamic`` column on as text. None when it is neither: a text unreadable or longer than
    ``WRITERS_MAX``, a value that is not a list, a list holding anything but objects. Never raises."""
    if isinstance(value, str):
        value = json_of(value)
    if not isinstance(value, list) or not all(isinstance(e, dict) for e in value):
        return None
    return value


def _own(entry, channel: Channel) -> tuple[int, int] | None:
    """(writes, bytes) of an entry of BlobWriters that is the watch's own, else None."""
    if not isinstance(entry, dict):
        return None
    writes, known = _count(entry.get("writes")), _count(entry.get("known"))
    if writes is None or writes <= 0 or known != writes:
        return None
    if str(entry.get("container") or "") != channel.container:
        return None
    if str(entry.get("writer") or "").lower() != channel.writer:
        return None
    return writes, _count(entry.get("bytes")) or 0


def _orodruin(entry, exercise: Channel) -> tuple[int, int] | None:
    """SLF2: (writes, bytes) of an entry of BlobWriters that is Orodruin's in its exercise channel —
    its container, its identity —, else None."""
    if not isinstance(entry, dict):
        return None
    writes = _count(entry.get("writes"))
    if writes is None or writes <= 0:
        return None
    if str(entry.get("container") or "") != exercise.container:
        return None
    if str(entry.get("writer") or "").lower() != exercise.writer:
        return None
    return writes, _count(entry.get("bytes")) or 0


def _read_by_own(row: dict, channel: Channel | None) -> bool:
    """Whether the pass of the watch's own channel reads this row's column (and counts it unparsed)."""
    return (channel is not None and bool(channel.writer) and _count(row.get("PutBlobCount")) is not None
            and str(row.get("AccountName") or "").lower() == channel.account)


def settle_exercise(rows: list[dict], exercise: Channel | None, channel: Channel | None = None,
                    said: dict | None = None) -> list[dict]:
    """SLF2: Orodruin's writes in its exercise channel taken off each row that carries BlobWriters —
    its entries out of the column (left a list), its writes and bytes off the row's counts, the row
    left out when nothing else is in it. Counted in ``said``: ``exercise_writes``, ``exercise_rows``,
    ``unparsed`` (a column unreadable, the row of the exercise channel's account, when the pass of
    the watch's channel does not count it). Without the channel and Orodruin's identity: nothing."""
    said = {} if said is None else said
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or WRITERS not in row:
            out.append(row)
            continue
        account = str(row.get("AccountName") or "").lower()
        total = _count(row.get("PutBlobCount"))
        mine = exercise is not None and bool(exercise.writer) and exercise.account == account
        if total is None or not mine:
            out.append(row)
            continue
        entries = writers_of(row[WRITERS])
        if entries is None:
            if not _read_by_own(row, channel):
                said["unparsed"] = said.get("unparsed", 0) + 1
            out.append(row)
            continue
        oro = [_orodruin(e, exercise) for e in entries]
        writes = min(total, sum(o[0] for o in oro if o is not None))
        if not writes:
            out.append(row)
            continue
        said["exercise_writes"] = said.get("exercise_writes", 0) + writes
        if writes >= total:
            said["exercise_rows"] = said.get("exercise_rows", 0) + 1
            continue
        row = dict(row)
        row[WRITERS] = [e for e, o in zip(entries, oro) if o is None]
        row["PutBlobCount"] = total - writes
        egress = _count(row.get("EgressBytes"))
        if egress is not None:
            row["EgressBytes"] = max(0, egress - sum(o[1] for o in oro if o is not None))
        out.append(row)
    return out


def settle(rows: list[dict], channel: Channel | None,
           exercise: Channel | None = None) -> tuple[list[dict], dict]:
    """(the rows for the poller, what was set aside). Each row that carries BlobWriters is a copy
    without it; the watch's own writes taken off its counts, and the row left out when nothing else
    is in it. Counts: ``writes`` and ``rows`` set aside, ``unread`` when a row carried the column
    while a channel is configured and the watch's identity is not read (nothing set aside),
    ``unparsed`` the rows of the channel's account whose column could not be read (`writers_of`:
    nothing set aside of them, SLF1b). SLF2: Orodruin's writes in its exercise channel first
    (`settle_exercise`: ``exercise_writes``, ``exercise_rows``); ``restart`` the writes set aside by
    the record of the watch before this one (``Channel.budget``) — each of the three only when not 0."""
    said = {"writes": 0, "rows": 0, "unread": False, "unparsed": 0}
    rows = settle_exercise(rows, exercise, channel, said)
    out: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or WRITERS not in row:
            out.append(row)
            continue
        row = dict(row)
        writers = row.pop(WRITERS)
        if channel is None:
            out.append(row)
            continue
        if not channel.writer:
            said["unread"] = True
            out.append(row)
            continue
        total = _count(row.get("PutBlobCount"))
        if total is None or str(row.get("AccountName") or "").lower() != channel.account:
            out.append(row)
            continue
        entries = writers_of(writers)
        if entries is None:
            said["unparsed"] += 1
            out.append(row)
            continue
        own = [o for o in (_own(e, channel) for e in entries) if o is not None]
        writes = sum(w for w, _ in own)
        if channel.budget is not None:
            # SLF2: the watch before this one stands in — no more writes than its record holds.
            if writes > channel.budget:
                own, writes = [], 0
            if writes:
                said["restart"] = said.get("restart", 0) + min(writes, total)
        if not writes:
            out.append(row)
            continue
        said["writes"] += min(writes, total)
        if total - writes <= 0:
            said["rows"] += 1
            continue
        row["PutBlobCount"] = total - writes
        egress = _count(row.get("EgressBytes"))
        if egress is not None:
            row["EgressBytes"] = max(0, egress - sum(b for _, b in own))
        out.append(row)
    return out, said


def strip(rows: list[dict]) -> list[dict]:
    """The rows without BlobWriters, nothing set aside — the fallback of a fault in `settle`."""
    return [{k: v for k, v in r.items() if k != WRITERS} if isinstance(r, dict) else r for r in rows]
