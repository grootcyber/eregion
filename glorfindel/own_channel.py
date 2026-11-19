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
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

WRITERS = "BlobWriters"
REASON = ("the watch's own return channel: its identity, the container of EREGION_WATCH_CHANNEL, "
          "the objects it writes there (SLF1)")
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


def _count(value) -> int | None:
    """A count from the row: an int (a float that is one, as JSON may read it), else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


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
    while a channel is configured and the watch's identity is not read (nothing set aside)."""
    said = {"writes": 0, "rows": 0, "unread": False}
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
        if (total is None or not isinstance(writers, list)
                or str(row.get("AccountName") or "").lower() != channel.account):
            out.append(row)
            continue
        own = [o for o in (_own(e, channel) for e in writers) if o is not None]
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
