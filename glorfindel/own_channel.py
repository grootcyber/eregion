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
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
from dataclasses import dataclass
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
# above; a text past it is not read (nothing set aside, said).
WRITERS_MAX = 64 * 1024
# Azure's container names: 3 to 63 of lowercase letters, digits and single hyphens.
_CONTAINER = re.compile(r"^(?=.{3,63}$)[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Channel:
    """The return channel the watch writes: its account, its container, and the object id of the
    identity it writes with ("" when it could not be read)."""
    account: str
    container: str
    writer: str = ""


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


def of_publisher(publisher) -> Callable[[], Channel | None] | None:
    """What the RulePoller reads at each pass: the channel this publisher writes, with its writer.
    None for no storage channel (a local channel of verdicts writes no blob)."""
    parsed = parse_url(str(getattr(publisher, "channel", "") or ""))
    writer = getattr(publisher, "writer", None)
    if parsed is None or not callable(writer):
        return None
    account, container = parsed

    def current() -> Channel | None:
        try:
            oid = str(writer() or "")
        except Exception:
            oid = ""
        return Channel(account, container, oid)
    return current


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


def writers_of(value) -> list[dict] | None:
    """BlobWriters as a list of objects (SLF1b): the list itself, or its JSON text — the SDK hands a
    ``dynamic`` column on as text. None when it is neither: a text unreadable or longer than
    ``WRITERS_MAX``, a value that is not a list, a list holding anything but objects. Never raises."""
    if isinstance(value, str):
        if len(value) > WRITERS_MAX:
            return None
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return None
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


def settle(rows: list[dict], channel: Channel | None) -> tuple[list[dict], dict]:
    """(the rows for the poller, what was set aside). Each row that carries BlobWriters is a copy
    without it; the watch's own writes taken off its counts, and the row left out when nothing else
    is in it. Counts: ``writes`` and ``rows`` set aside, ``unread`` when a row carried the column
    while a channel is configured and the watch's identity is not read (nothing set aside),
    ``unparsed`` the rows of the channel's account whose column could not be read (`writers_of`:
    nothing set aside of them, SLF1b)."""
    said = {"writes": 0, "rows": 0, "unread": False, "unparsed": 0}
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
