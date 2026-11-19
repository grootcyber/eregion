"""The channel that carries exercise windows (B2) from the injectors' host (Orodruin) to a
watch on another host (Glorfindel hosted, Imladris) — O1, part C.

A blob container, reached by managed identity only (no shared key): Orodruin's identity
writes, the watch's identity reads. ``EREGION_EXERCISE_CHANNEL`` is the container's URL
(``https://<account>.blob.core.windows.net/exercises``); unset or empty, nothing is
published or pulled and the windows stay local, as before.

Both directions fail toward ``real``: a window that doesn't reach the watch leaves its
cycles labelled real — the label never lowers a guard (eregion_core/exercise.py). So a
failure here is reported, never raised into a run or a cycle.

The same container carries a finished campaign to Imladris, where its report is written (IA0,
#167; analysis/hosted_report.py): its manifest and the report of each of its runs, under
``campaigns/<campaign_id>/`` — nothing else, and no right more than the windows' (one
assignment, on this container: eregion_core/orodruin.py). The prefix keeps them out of the
windows: a run's window is ``<run_id>.json`` at the root, and a name with a ``/`` never
matches ``_SAFE_NAME``, so ``pull`` leaves the campaigns to ``pull_campaigns``.

And the report of a run launched alone (``annatar run``, ``gothmog run``, #193), so that its
verdict is seen on Imladris too: ``runs/<run_id>.json``, under the same container and the same
assignment — a prefix again, which neither ``pull`` nor ``pull_campaigns`` takes. Imladris pulls
it into the watch's own directory, ``runs/glorfindel/<run_id>.json`` (``pull_runs``; SEC18), where
the console of the atelier reads it, once it has the shape Imladris accepts (H-1), and never over a file
it did not pull. Everything the watch pulls goes to its own directory, the only one it writes.

SEC5 holds the channel at its edges:
- a storage bearer token goes only to an Azure Storage blob endpoint — ``https://<account>``
  and one of ``BLOB_SUFFIXES`` (the public cloud, then the sovereign ones), port 443, no user
  in the URL; any other URL is refused before a token is asked for (N-15, ``url_refusal``);
  and only to the account the operator declared (SEC17, ``declared_refusal``): the two channels
  (``EREGION_EXERCISE_CHANNEL``, ``EREGION_WATCH_CHANNEL``) and, on Orodruin, the scopes of
  their containers (``EREGION_CHANNEL_SCOPE``, ``EREGION_WATCH_CHANNEL_SCOPE``, its contract's)
  all name one account — Terraform's outputs. Another account, or declarations that disagree,
  are refused and said, no token sent;
- a pull reads what it is given within bounds (V-21): a blob at most ``MAX_BLOB_BYTES``, a
  listing page at most ``MAX_LISTING_BYTES``, at most ``MAX_BLOBS`` names listed and
  ``MAX_DOWNLOADS`` blobs downloaded per pull — read as a stream cut past the bound, never
  read whole and then checked; what goes past one is said, and left for the next pull or
  skipped, never written. And in all (SEC14): one pull reads at most ``MAX_PULL_BYTES``, its
  listing pages and its blobs together (``Budget``) — past it, the pull stops there and says so,
  the rest waits for the next one;
- a window pulled from the channel carries when its blob was created, as the listing says
  (``CREATED``, written over anything the window said of it, and kept from its first pull):
  the watch bounds the window by it, not by what the window declares (V-20,
  eregion_core/exercise.py);
- Orodruin's journal goes here too, under ``audit/`` (V-29, eregion_core/orodruin.py): an
  append blob per run, a prefix no pull takes.
"""
from __future__ import annotations

import contextlib
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

CHANNEL_ENV = "EREGION_EXERCISE_CHANNEL"
# SEC17 (N-15): where the operator declares the channel's account — the two channels' URLs
# (watch_channel.CHANNEL_ENV is the second) and, on Orodruin, their containers' scopes, which its
# contract reads (eregion_core/orodruin.py CHANNEL_SCOPE_ENV, WATCH_SCOPE_ENV). Each from a
# Terraform output of infra/orodruin (channel_url, watch_channel_url, channel_scope,
# watch_channel_scope).
DECLARED_URLS = ("EREGION_EXERCISE_CHANNEL", "EREGION_WATCH_CHANNEL")
DECLARED_SCOPES = ("EREGION_CHANNEL_SCOPE", "EREGION_WATCH_CHANNEL_SCOPE")
_SCOPE_ACCOUNT = re.compile(
    r"^/subscriptions/[^/]+/resourcegroups/[^/]+/providers/microsoft\.storage"
    r"/storageaccounts/([a-z0-9]{3,24})/blobservices/default/containers/[^/]+$", re.IGNORECASE)
STORAGE = "https://storage.azure.com/.default"
API_VERSION = "2021-08-06"
# A blob becomes a local file: only a plain run_id name, never a path.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.json$")
PULL_EVERY_S = 30.0
# A campaign's blobs: ``campaigns/<campaign_id>/manifest.json`` and
# ``campaigns/<campaign_id>/runs/<run_id>.json`` — each part a plain name, never a path.
CAMPAIGNS = "campaigns"
_SAFE_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_CAMPAIGN_BLOB = re.compile(
    r"^campaigns/(?P<cid>[A-Za-z0-9][A-Za-z0-9_.-]*)/"
    r"(?:manifest\.json|runs/(?P<rid>[A-Za-z0-9][A-Za-z0-9_.-]*)\.json)$")
# The files of a run that go to Imladris: its report only — never its _debug.jsonl (the watch's,
# written on Imladris) nor its _signals.jsonl.
_RUN_FILES = ("{run_id}.json",)
# Beside a manifest pulled from the channel: Imladris writes the report of these campaigns only,
# never of a campaign of its own runs directory (analysis/hosted_report.py).
PULLED = ".pulled"
# The report of a run launched alone: ``runs/<run_id>.json``, the run id a plain name.
RUNS = "runs"
_RUN_BLOB = re.compile(r"^runs/(?P<rid>[A-Za-z0-9][A-Za-z0-9_.-]*)\.json$")
# In Imladris's runs directory, one empty file per run report pulled from the channel: Imladris writes
# again only those, never the report of a run of its own.
PULLED_RUNS = ".pulled-runs"

# SEC5 (N-15): the only hosts a storage bearer token is sent to — Azure Storage's blob
# endpoints: the public cloud, Azure China, Azure US Government.
BLOB_SUFFIXES = (".blob.core.windows.net", ".blob.core.chinacloudapi.cn",
                 ".blob.core.usgovcloudapi.net")
_ACCOUNT = re.compile(r"^[a-z0-9]{3,24}$")
# SEC5 (V-21): what one pull reads at most. A window, a run's report, a campaign's manifest
# are a few KiB; a listing page of Azure's 5 000 names, about 2 MiB.
MAX_BLOB_BYTES = 1024 * 1024
MAX_LISTING_BYTES = 8 * 1024 * 1024
MAX_BLOBS = 2000
MAX_DOWNLOADS = 200
# SEC14 (V-21): what one pull reads in all — its listing pages and its blobs, cumulated. The bounds
# above hold each read; this one holds their sum (200 blobs of 1 MiB, or pages of names, would
# otherwise make hundreds of MiB per pull).
MAX_PULL_BYTES = 32 * 1024 * 1024
# SEC-A1b (#642): the watch's own directory, where the pull writes the windows — at most
# MAX_PULLED_FILES files and MAX_PULLED_BYTES in all; past either, no new window is pulled (a
# closure of one here still is), said once while it lasts. Each window is at most WINDOW_BYTES
# (eregion_core/exercise.py), refused at the pull past it.
MAX_PULLED_FILES = 4096
MAX_PULLED_BYTES = 32 * 1024 * 1024
# The watch's directories found full by a pull: said once while it lasts — again only after a pull
# found room there, then found it full again (every 30 s otherwise).
_full_dirs: set[str] = set()
# SEC-A1b: what the kill lists of the channel at most, page after page (``pull_whole``) — past it, the
# kill fails, never « no window open ». Retention is 9 days (infra/orodruin/variables.tf).
KILL_MAX_BLOBS = 100_000
# SEC-A1b: the margin of clocks the kill leaves before it takes a blob for one that can no longer be
# open (``_never_open``) — Azure's, the operator's, Orodruin's.
KILL_MARGIN_S = 15 * 60
_CHUNK = 64 * 1024
# SEC5 (V-20): in a window pulled from the channel, when its blob was created — the
# listing's word, never the window's (eregion_core/exercise.py reads it).
CREATED = "channel_created"
# SEC5 (V-29): Orodruin's journal, one append blob per run.
AUDIT = "audit"
# DG-b: what Orodruin says to the console — its contract's verdict, each request's status —
# under its own prefix of the same container; the watch of Imladris pulls it into runs/glorfindel/orodruin/,
# each blob read against its shape (eregion_core/orodruin.py read_contract,
# eregion_core/exercise_request.py read_status).
ORODRUIN = "orodruin"
_ORODRUIN_BLOB = re.compile(r"orodruin/(?:contract|requests/(?P<rid>r-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{6}))\.json")

_last_pull = 0.0
_pull_lock = threading.Lock()
_credential = None


class ChannelRefused(ValueError):
    """A channel URL a storage token must never be sent to (N-15)."""


class TooLarge(RuntimeError):
    """A blob or a listing past its bound (V-21): the rest of it is never read."""


class Spent(TooLarge):
    """The pull's cumulated bound reached (V-21, SEC14): it stops, the rest waits for the next."""


class Truncated(RuntimeError):
    """A listing stopped at its bound when it had to be whole (the kill, SEC-A1b): what it did not
    list is not known."""


class Budget:
    """What one pull may still read, its listing pages and its blobs together (MAX_PULL_BYTES)."""

    def __init__(self, total: int | None = None):
        self.left = MAX_PULL_BYTES if total is None else total

    def spend(self, n: int) -> None:
        self.left -= n


def channel_url() -> str:
    return (os.environ.get(CHANNEL_ENV) or "").strip().rstrip("/")


def url_refusal(url: str) -> str:
    """Why a storage token must not go to ``url`` — "" when it is an Azure Storage blob
    endpoint: https, ``<account>`` then one of BLOB_SUFFIXES, port 443, no user (N-15)."""
    try:
        parts = urlsplit(url or "")
        port = parts.port
    except ValueError:
        return "not a URL"
    if parts.scheme != "https":
        return "not https"
    if parts.username is not None or parts.password is not None:
        return "a user in the URL"
    if port not in (None, 443):
        return f"port {port}, not 443"
    host = (parts.hostname or "").lower()
    for suffix in BLOB_SUFFIXES:
        if host.endswith(suffix) and _ACCOUNT.match(host[:-len(suffix)]):
            return ""
    return "not an Azure Storage blob endpoint (https://<account>.blob.core.windows.net)"


def account_of(url: str) -> str:
    """The storage account an Azure Storage blob URL names — "" when it is not one."""
    if url_refusal(url):
        return ""
    host = (urlsplit(url).hostname or "").lower()
    return next(host[:-len(suffix)] for suffix in BLOB_SUFFIXES if host.endswith(suffix))


def declared_accounts(env=None) -> dict[str, str]:
    """``{variable: account}`` for each declaration of the channel's account that is set — the
    two channels' URLs, the two containers' scopes; one that names no account: ``""``."""
    env = os.environ if env is None else env
    out: dict[str, str] = {}
    for name in DECLARED_URLS:
        value = (env.get(name) or "").strip().rstrip("/")
        if value:
            out[name] = account_of(value)
    for name in DECLARED_SCOPES:
        value = (env.get(name) or "").strip().rstrip("/")
        if value:
            m = _SCOPE_ACCOUNT.match(value)
            out[name] = m.group(1).lower() if m else ""
    return out


def declared_refusal(url: str, env=None) -> str:
    """Why a storage token must not go to ``url``'s account (SEC17, N-15) — "" when every
    declaration that is set names that account. Declarations that disagree refuse every account:
    which one is ours cannot be told."""
    account = account_of(url)
    others = {name: acct for name, acct in declared_accounts(env).items() if acct != account}
    if not others:
        return ""
    said = ", ".join(f"{name}: {acct or 'no account'}" for name, acct in sorted(others.items()))
    return f"the account {account or '?'} is not the one declared ({said})"


def check_url(url: str) -> str:
    """``url``, or ChannelRefused — before any token is asked for."""
    why = url_refusal(url) or declared_refusal(url)
    if why:
        host = urlsplit(url or "").hostname or "?"
        raise ChannelRefused(f"channel {host!r} refused, no token sent: {why}")
    return url


def _read(r, limit: int, what: str) -> bytes:
    """The body of ``r``, at most ``limit`` bytes. A real response is read as a stream and
    cut past the bound — never read whole, then checked (V-21); its Content-Length, when it
    says more, refuses it before a byte is read. A client passed in (a fake) gives its body."""
    import requests

    if isinstance(r, requests.Response):
        try:
            declared = int(r.headers.get("Content-Length") or -1)
        except ValueError:
            declared = -1
        if declared > limit:
            r.close()
            raise TooLarge(f"{what}: {declared} bytes, more than {limit}")
        out = bytearray()
        for chunk in r.iter_content(_CHUNK):
            out += chunk
            if len(out) > limit:
                r.close()
                raise TooLarge(f"{what}: more than {limit} bytes")
        return bytes(out)
    body = r.content
    if len(body) > limit:
        raise TooLarge(f"{what}: more than {limit} bytes")
    return body


def fetch(get, url: str, headers: dict, *, limit: int = MAX_BLOB_BYTES, params=None,
          what: str = "", budget: Budget | None = None) -> tuple[object, bytes]:
    """GET ``url``: (the response, its body read within ``limit``) — b"" when it is not ok.
    Without a client passed in, requests streams it (``stream=True``). With a ``budget``, the
    read is bounded by what the pull has left too: past it, ``Spent`` — the bytes read count."""
    import requests

    what = what or url.rsplit("/", 1)[-1]
    if budget is not None and budget.left <= 0:
        raise Spent(f"{what}: this pull has read its {MAX_PULL_BYTES} bytes")
    if get is None:
        r = requests.get(url, headers=headers, params=params, timeout=15, stream=True)
    else:
        r = get(url, headers=headers, params=params, timeout=15)
    if not r.ok:
        return r, b""
    if budget is None:
        return r, _read(r, limit, what)
    bound = min(limit, budget.left)
    try:
        body = _read(r, bound, what)
    except TooLarge as e:
        budget.spend(bound)            # what was read at most: the bound is only ever stricter
        if bound < limit:
            raise Spent(f"{what}: this pull has read its {MAX_PULL_BYTES} bytes") from e
        raise
    budget.spend(len(body))
    return r, body


def auth_headers(credential, url: str) -> dict:
    """Storage, by managed identity — shared with the return channel (watch_channel.py). The
    token is asked for only once ``url`` is an Azure Storage blob endpoint (N-15)."""
    global _credential
    check_url(url)
    if credential is None:
        if _credential is None:
            from azure.identity import DefaultAzureCredential
            _credential = DefaultAzureCredential()
        credential = _credential
    return {"Authorization": f"Bearer {credential.get_token(STORAGE).token}",
            "x-ms-version": API_VERSION}


def publish(window: dict, *, channel: str | None = None, credential=None, put=None) -> bool:
    """Write the window as ``<run_id>.json``. False when no channel is configured."""
    import json
    import requests

    url = channel if channel is not None else channel_url()
    if not url:
        return False
    name = f"{window['run_id']}.json"
    if not _SAFE_NAME.match(name):
        raise ValueError(f"unsafe window name: {name!r}")
    headers = {**auth_headers(credential, url), "x-ms-blob-type": "BlockBlob",
               "Content-Type": "application/json"}
    r = (put or requests.put)(f"{url}/{name}", headers=headers,
                              data=json.dumps(window, indent=2).encode(), timeout=15)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} publishing {name}")
    return True


def _created(blob) -> str:
    """When the blob was created, as the listing says (``Creation-Time``) — else its
    ``Last-Modified``, never earlier — else now: the bound is only ever stricter (V-20)."""
    for field in ("Properties/Creation-Time", "Properties/Last-Modified"):
        value = blob.findtext(field)
        if value:
            try:
                return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                continue
    return datetime.now(timezone.utc).isoformat()


def _stamped(body: bytes, blob, local: Path | None) -> bytes:
    """The window as pulled, with ``CREATED`` set to when its blob was created — the value of
    its first pull, kept when the window comes again (closed), else the listing's (V-20). Without
    ``local`` (a copy the watch never wrote down as pulled), the listing's alone: what a copy on
    disk says is nobody's word. A body that is no JSON object is written as it came: the watch
    refuses it anyway."""
    import json

    try:
        window = json.loads(body)
    except ValueError:
        return body
    if not isinstance(window, dict):
        return body
    from eregion_core.channel_reader import read_json
    from eregion_core.exercise import WINDOW_BYTES
    first = ""
    try:
        if local is not None:     # read as runs/ is read (SEC-A1b): never a link, never blocking
            first = str(read_json(local, WINDOW_BYTES).get(CREATED) or "")
    except (OSError, ValueError, AttributeError, RecursionError):
        pass
    window[CREATED] = first or _created(blob)
    return json.dumps(window, indent=2).encode()


# A window, once pulled, may come again only closed (V-20): every field as it was, ``end`` from
# null to a date not before its start (``closed_by`` beside it, the kill's). Anything else —
# a target added, a start moved, its expiry pushed, ``end`` withdrawn or moved — is refused,
# the local copy kept. When it was refused, by blob: said once, not downloaded again.
_KEPT_AS_PULLED = {CREATED, "end", "closed_by"}
_refused_rewrites: dict[str, str] = {}
# SEC-A1b: the blobs refused remembered, at most this many — the oldest forgotten first (a blob
# forgotten is downloaded again once, and refused again).
_REFUSED_KEPT = 4096


def _remember_refused(key: str, modified: str) -> None:
    _refused_rewrites.pop(key, None)
    _refused_rewrites[key] = modified
    while len(_refused_rewrites) > _REFUSED_KEPT:
        del _refused_rewrites[next(iter(_refused_rewrites))]


def window_shape_refusal(name: str, window) -> str:
    """Why a blob pulled from the channel is not a window the watch would believe — "" when it is
    one (SEC-A1b): a JSON object, named after its run (``<run_id>.json``), that passes
    ``exercise.window_refusal`` with the date its blob was created. Refused at the pull, it is never
    written to the watch's directory nor to its record."""
    from eregion_core.exercise import window_refusal
    if not isinstance(window, dict):
        return "not a JSON object"
    if f"{window.get('run_id')}.json" != name:
        return "its run_id is not its blob's name"
    return window_refusal(window)


def _pulled_room(directory: Path) -> tuple[int, int]:
    """(files, bytes) the watch's directory of windows holds — by lstat, never through a link."""
    files = size = 0
    try:
        with os.scandir(directory) as entries:
            for entry in entries:
                files += 1
                with contextlib.suppress(OSError):    # gone since it was listed
                    size += entry.stat(follow_symlinks=False).st_size
    except OSError:
        pass
    return files, size


def rewrite_refusal(old, new) -> str:
    """Why a window pulled again may not replace its local copy — "" when it is its closure."""
    from eregion_core.exercise import _parse  # exercise imports this module lazily

    if not isinstance(old, dict) or not isinstance(new, dict):
        return "" if not isinstance(old, dict) else "not a JSON object"
    if old.get("purged_at"):
        return "purged here already"
    changed = sorted(k for k in (set(old) | set(new)) - _KEPT_AS_PULLED if old.get(k) != new.get(k))
    if changed:
        return f"rewritten after it was pulled: {', '.join(changed)} changed"
    if old.get("end") == new.get("end"):
        return ""
    start, end = _parse(old.get("start")), _parse(new.get("end"))
    if old.get("end") is None and end is not None and start is not None and end >= start:
        return ""
    return "its end withdrawn or moved after it was pulled"


def pull(directory: Path, *, channel: str | None = None, credential=None, get=None,
         say=print, seen: Path | None = None) -> int:
    """Copy into ``directory`` every window of the channel that is new or changed since the
    local copy, page after page of the listing — the container's root only (the windows; the
    prefixes are other pulls'), within the bounds of V-21. Each window carries when its blob
    was created (``CREATED``, V-20); one pulled already is replaced only by its closure
    (``rewrite_refusal``). With ``seen`` (the watch's own record, eregion_core/exercise.py), each
    window written is written down there as pulled — the only proof the watch takes that it came
    from the channel (SEC14, V-20). Returns how many were written."""
    url = channel if channel is not None else channel_url()
    if not url:
        return 0
    headers = auth_headers(credential, url)   # the URL refused first, before any directory
    from eregion_core import runs_layout
    # SEC18: never through a link — its directory, and what is below.
    if why := runs_layout.pull_root(directory) or runs_layout.parents_hold(Path(directory), Path(directory) / "w.json"):
        raise RuntimeError(f"windows not pulled: {why}")
    written: list[str] = []
    try:
        _pull_windows(directory, url, headers, get, say, Budget(), written, seen)
    except Spent as e:   # the pull's cumulated bound (V-21): what was written stays
        say(f"[exercise-channel] {e}: the rest waits for the next pull")
    return len(written)


def _pull_windows(directory: Path, url: str, headers: dict, get, say, budget: Budget,
                  written: list[str], seen: Path | None = None) -> None:
    import json

    from eregion_core.channel_reader import read_json
    from eregion_core.exercise import WINDOW_BYTES, note_pulled, noted_pulled  # imported lazily
    downloads = 0
    room: list[int] | None = None       # SEC-A1b: what the directory holds, read at the first new window
    # SEC14 review (V-20): a copy here the watch never wrote down as pulled — one pulled before
    # this version, a window still open at the first pass — is pulled once again, through
    # rewrite_refusal like any other, then written down. Only then is it the channel's.
    noted = noted_pulled(seen) if seen is not None else None
    for blob in _blobs(get, url, headers, delimiter="/", say=say, budget=budget):
        name = blob.findtext("Name") or ""
        if not _SAFE_NAME.match(name):  # a campaign's blob (a ``/``) or a path: never a window
            continue
        modified = blob.findtext("Properties/Last-Modified")
        local = directory / name
        unnoted = noted is not None and local.exists() and name[:-len(".json")] not in noted
        if local.exists() and modified and not unnoted:
            remote_ts = parsedate_to_datetime(modified).timestamp()
            if remote_ts <= local.stat().st_mtime:
                continue
        key = f"{directory}/{name}"
        if modified and _refused_rewrites.get(key) == modified:
            continue  # refused already, said already: not downloaded again
        if downloads >= MAX_DOWNLOADS:
            say(f"[exercise-channel] {MAX_DOWNLOADS} windows downloaded: the rest waits for "
                "the next pull")
            break
        if not local.exists():
            # SEC-A1b: the watch's directory bounded — past it, no new window pulled.
            if room is None:
                room = list(_pulled_room(directory))
            if room[0] >= MAX_PULLED_FILES or room[1] >= MAX_PULLED_BYTES:
                if str(directory) not in _full_dirs:     # said once while it lasts
                    _full_dirs.add(str(directory))
                    say(f"[exercise-channel] the watch's directory of windows holds {room[0]} files, "
                        f"{room[1]} bytes (MAX_PULLED_FILES {MAX_PULLED_FILES}, MAX_PULLED_BYTES "
                        f"{MAX_PULLED_BYTES}): no new window pulled until its windows are purged — "
                        "said once while it lasts")
                continue
            _full_dirs.discard(str(directory))     # room again: a new flood will be said
        downloads += 1
        try:
            # SEC-A1b: a window is under 1 KiB; a blob past WINDOW_BYTES is no window.
            r, body = fetch(get, f"{url}/{name}", headers, limit=WINDOW_BYTES, what=f"window {name}",
                            budget=budget)
        except Spent:
            raise
        except TooLarge as e:
            if modified:
                _remember_refused(key, modified)
            say(f"[exercise-channel] {e} — not pulled")
            continue
        if not r.ok:
            continue
        # As it would be written here: the creation of its first pull kept (V-20).
        stamped = _stamped(body, blob, None if unnoted else local)
        try:
            shaped = json.loads(stamped)
        except (ValueError, RecursionError):
            shaped = None
        if why := window_shape_refusal(name, shaped):
            if modified:
                _remember_refused(key, modified)    # said once, not downloaded again
            say(f"[exercise-channel] blob {name} refused, not pulled: {why}")
            continue
        if local.exists():
            try:
                old = read_json(local, WINDOW_BYTES)   # SEC-A1b: never a link, never blocking
            except (OSError, ValueError, RecursionError):
                old = None
            try:
                new = json.loads(body)
            except ValueError:
                new = None
            # A copy here that cannot be read (corrupt, a permission) is never replaced: what was
            # pulled first cannot be compared, so no rewrite is known to be a closure (SEC7). One
            # deleted here comes again as new, bounded by its blob's creation (V-20).
            why = ("the copy pulled before cannot be read here" if not isinstance(old, dict)
                   else rewrite_refusal(old, new))
            if why:
                _remember_refused(key, modified or "")
                say(f"[exercise-channel] window {name} refused, the copy pulled before kept: {why}")
                continue
        _refused_rewrites.pop(key, None)
        tmp = local.with_suffix(".json.tmp")
        new_file = not local.exists()
        tmp.write_bytes(stamped)
        tmp.replace(local)  # atomic: the watch never reads half a window
        written.append(name)
        if new_file and room is not None:
            room[0] += 1
            room[1] += len(stamped)
        try:
            note_pulled(seen, json.loads(stamped))
        except ValueError:
            pass                     # not JSON: the watch refuses it anyway


def _never_open(blob, now: datetime) -> bool:
    """This blob can carry no window open now (SEC-A1b): created — the listing's Creation-Time, else
    its Last-Modified, never earlier — more than MAX_DURATION_S + FUTURE_SKEW_S + KILL_MARGIN_S
    ago. A window the watch believes starts within FUTURE_SKEW_S of its blob's creation
    (``exercise.window_refusal``) and lasts at most MAX_DURATION_S: open now, its blob was created
    after ``now - MAX_DURATION_S - FUTURE_SKEW_S``. Unreadable dates: it may be open."""
    from eregion_core.exercise import FUTURE_SKEW_S, MAX_DURATION_S
    from datetime import timedelta
    for field in ("Properties/Creation-Time", "Properties/Last-Modified"):
        value = blob.findtext(field)
        if value:
            try:
                born = parsedate_to_datetime(value).astimezone(timezone.utc)
            except (TypeError, ValueError):
                return False
            return born < now - timedelta(seconds=MAX_DURATION_S + FUTURE_SKEW_S + KILL_MARGIN_S)
    return False


def pull_whole(directory: Path, *, channel: str | None = None, credential=None, get=None,
               say=print, max_blobs: int | None = None, now: datetime | None = None) -> int:
    """For the kill (SEC-A1b): copy into ``directory`` (an empty one of its own) every window of the
    channel, page after page of the whole listing — not the MAX_BLOBS names nor the MAX_DOWNLOADS
    blobs a pull of the watch stops at, which leave out the windows listed after them. Each window
    carries when its blob was created (``CREATED``), as ``pull`` writes it. A blob past
    WINDOW_BYTES, or that is no window (``window_shape_refusal``), is said and left: the watch never
    pulls it either. Raises — never a partial list taken for the whole — when the listing goes past
    ``max_blobs`` (KILL_MAX_BLOBS), a listing page past its bound, or a window cannot be downloaded
    — a blob gone between the listing and its download (404) too: deleted (the retention, a
    writer), it fails closed, the kill run again. A blob that can no longer carry an open window
    (``_never_open``: created too long ago) is not downloaded: every one that can is. Returns how
    many were written."""
    import json

    from eregion_core.exercise import WINDOW_BYTES
    url = channel if channel is not None else channel_url()
    if not url:
        raise RuntimeError("no exercise channel: its windows were not read")
    headers = auth_headers(credential, url)
    from eregion_core import runs_layout
    if why := runs_layout.pull_root(directory) or runs_layout.parents_hold(Path(directory), Path(directory) / "w.json"):
        raise RuntimeError(f"windows not pulled: {why}")
    limit = KILL_MAX_BLOBS if max_blobs is None else max_blobs
    now = now or datetime.now(timezone.utc)
    written = 0
    for blob in _whole_listing(get, url, headers, limit):
        name = blob.findtext("Name") or ""
        if not _SAFE_NAME.match(name) or _never_open(blob, now):
            continue
        try:
            r, body = fetch(get, f"{url}/{name}", headers, limit=WINDOW_BYTES, what=f"window {name}")
        except TooLarge as e:
            say(f"[exercise-channel] {e} — no window the watch pulls, left")
            continue
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code} downloading the window {name}: not every "
                               "window of the channel seen")
        stamped = _stamped(body, blob, None)
        try:
            why = window_shape_refusal(name, json.loads(stamped))
        except (ValueError, RecursionError):
            why = "not JSON"
        if why:
            say(f"[exercise-channel] blob {name}: {why} — no window the watch pulls, left")
            continue
        (Path(directory) / name).write_bytes(stamped)
        written += 1
    return written


def pull_if_due(directory: Path, *, now: float | None = None) -> None:
    """``pull`` at most every PULL_EVERY_S — load_windows runs on every cycle, and on the
    return channel's thread (eregion_core/watch_channel.py): one pull at a time."""
    global _last_pull
    if not channel_url():
        return
    now = time.monotonic() if now is None else now
    if now - _last_pull < PULL_EVERY_S or not _pull_lock.acquire(blocking=False):
        return
    try:
        _last_pull = now
        from eregion_core.exercise import seen_path
        pull(directory, seen=seen_path())
    except Exception as e:  # the local windows still count; the rest falls toward real
        print(f"[exercise-channel] pull failed at {datetime.now():%H:%M:%S}: {e}")
    finally:
        _pull_lock.release()


def pull_now(directory: Path, **kw) -> int:
    """``pull`` now, whatever PULL_EVERY_S, under the lock ``pull_if_due`` takes: two pulls
    never write the same window at once. For the campaign report, which needs the last
    window, closed just before its campaign ended (analysis/hosted_report.py)."""
    from eregion_core.exercise import exercises_dir, seen_path
    if Path(directory) == exercises_dir():
        kw.setdefault("seen", seen_path())     # the watch's own windows: written down as pulled (V-20)
    if not _pull_lock.acquire(timeout=60):
        raise RuntimeError("another pull of the windows is still running")
    try:
        return pull(directory, **kw)
    finally:
        _pull_lock.release()


# ── A finished campaign, carried to Imladris (#167) ─────────────────────────────────────────

def safe_part(part: str) -> bool:
    """A plain name — never a path: what a campaign id or a run id read from a manifest (it
    may come from another host) must be before it names a file."""
    return bool(_SAFE_PART.match(part)) and ".." not in part


_safe_part = safe_part


def unpublished_runs(campaign_dir: Path, runs_dir: Path | None = None) -> list[str]:
    """The executed runs of the campaign whose report is not in ``runs_dir`` — Imladris waits for
    each one before it writes the campaign's report, so it will not write it on its own
    (``campaign run --runs-dir X``: the runs' reports stay in ``runs/annatar/``, annatar/runner/report.py)."""
    from eregion_core.channel_reader import read_json
    cdir = Path(campaign_dir)
    runs = Path(runs_dir) if runs_dir is not None else cdir.parent.parent
    manifest = read_json(cdir / "manifest.json")   # KS1, SEC-A1b: never a link, never blocking, bounded
    out = []
    for scenario in manifest.get("scenarios") or []:
        if not isinstance(scenario, dict) or scenario.get("status") != "executed":
            continue
        rid = str(scenario.get("run_id") or "")
        if rid and (not safe_part(rid) or not (runs / f"{rid}.json").is_file()):
            out.append(rid)
    return out


def campaign_blobs(campaign_dir: Path, runs_dir: Path | None = None) -> list[tuple[str, Path]]:
    """What a campaign carries to Imladris, as (blob name, local file): the report of each of its
    runs (``runs/annatar/<run_id>.json``, which holds ``attack_time``), then its manifest — last, so
    a watch that sees the manifest sees the runs too. Nothing else: not the runs' debug or
    signal files, not another run, not a file of the campaign directory (scenarios, report).
    A run_id that is not a plain name is left out; a campaign_id that is not raises."""
    from eregion_core.channel_reader import read_json
    cdir = Path(campaign_dir)
    runs = Path(runs_dir) if runs_dir is not None else cdir.parent.parent
    manifest = read_json(cdir / "manifest.json")   # KS1, SEC-A1b: what is published to Imladris, read bounded
    cid = str(manifest.get("campaign_id") or cdir.name)
    if not _safe_part(cid):
        raise ValueError(f"unsafe campaign id: {cid!r}")
    out: list[tuple[str, Path]] = []
    for scenario in manifest.get("scenarios") or []:
        rid = str((scenario or {}).get("run_id") or "")
        if not _safe_part(rid):
            continue
        for pattern in _RUN_FILES:
            name = pattern.format(run_id=rid)
            if (runs / name).is_file():
                out.append((f"{CAMPAIGNS}/{cid}/runs/{name}", runs / name))
    out.append((f"{CAMPAIGNS}/{cid}/manifest.json", cdir / "manifest.json"))
    return out


def publish_campaign(campaign_dir: Path, runs_dir: Path | None = None, *,
                     channel: str | None = None, credential=None,
                     put=None) -> tuple[str, list[str]]:
    """Write the campaign's blobs (``campaign_blobs``) to the channel: the campaign id they
    are published under (the manifest's, after which Imladris names the campaign's directory and
    report) and the names written — ``("", [])`` when no channel is configured. A refused
    write raises to its caller, which reports it (annatar/cli.py): the campaign has run,
    its report can be written later."""
    import requests

    url = channel if channel is not None else channel_url()
    if not url:
        return "", []
    blobs = campaign_blobs(campaign_dir, runs_dir)
    cid = blobs[-1][0].split("/")[1]  # campaigns/<cid>/manifest.json, always the last
    headers = {**auth_headers(credential, url), "x-ms-blob-type": "BlockBlob",
               "Content-Type": "application/json"}
    from eregion_core.channel_reader import DOC_BYTES, read_file
    written = []
    for name, path in blobs:
        # KS1, SEC-A1b: the manifest and the runs' reports read as runs/ is read.
        r = (put or requests.put)(f"{url}/{name}", headers=headers, data=read_file(path, DOC_BYTES),
                                  timeout=15)
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code} publishing {name}")
        written.append(name)
    return cid, written


# ── The report of a run launched alone, carried to Imladris (#193) ──────────────────────────

def publish_run(run_id: str, runs_dir: Path | str, *, channel: str | None = None,
                credential=None, put=None) -> str:
    """Write the report of a run launched alone to the channel, as ``runs/<run_id>.json`` —
    from ``runs_dir``, its injector's own directory (SEC18: ``runs/annatar``, ``runs/gothmog``):
    its report only, never its debug or signal files. The blob's name, or "" when no channel
    is configured or the run wrote no report. A refused write raises to its caller."""
    import requests

    url = channel if channel is not None else channel_url()
    if not url:
        return ""
    if not safe_part(run_id):
        raise ValueError(f"unsafe run id: {run_id!r}")
    path = Path(runs_dir) / f"{run_id}.json"
    if not path.is_file():
        return ""
    name = f"{RUNS}/{run_id}.json"
    headers = {**auth_headers(credential, url), "x-ms-blob-type": "BlockBlob",
               "Content-Type": "application/json"}
    r = (put or requests.put)(f"{url}/{name}", headers=headers, data=path.read_bytes(),
                              timeout=15)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} publishing {name}")
    return name


def carry_run(run_id: str, runs_dir: Path | str) -> bool:
    """``publish_run`` at the end of a run (``annatar run``, ``gothmog run``), beside its
    closed window. A failure is said, never raised: the run is over, and its report stays
    on this host. True once published."""
    try:
        name = publish_run(run_id, runs_dir)
    except Exception as e:
        print(f"[exercise-channel] run report {run_id} not published: {e}")
        return False
    if name:
        print(f"[exercise-channel] run report published to Imladris: {name}")
    return bool(name)


def _blobs(get, url: str, headers: dict, prefix: str = "", *, delimiter: str = "",
           say=print, budget: Budget | None = None):
    """Every blob of the channel (under ``prefix``, when one is given; not below a
    ``delimiter``), page after page — each page read within MAX_LISTING_BYTES, at most
    MAX_BLOBS names in all: past them, the listing stops and says so (V-21). The pages count
    against the pull's ``budget``: past it, ``Spent``."""
    marker, seen = "", 0
    while True:
        params = {"restype": "container", "comp": "list"}
        if prefix:
            params["prefix"] = prefix
        if delimiter:
            params["delimiter"] = delimiter
        if marker:
            params["marker"] = marker
        r, body = fetch(get, url, headers, limit=MAX_LISTING_BYTES, params=params,
                        what="a listing page of the channel", budget=budget)
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code} listing the channel")
        root = ET.fromstring(body)
        for blob in root.iter("Blob"):
            if seen >= MAX_BLOBS:
                say(f"[exercise-channel] listing stopped at {MAX_BLOBS} blobs"
                    f"{' under ' + prefix if prefix else ''}: the rest is not pulled")
                return
            seen += 1
            yield blob
        marker = (root.findtext("NextMarker") or "").strip()
        if not marker:
            return


def _whole_listing(get, url: str, headers: dict, limit: int):
    """Every blob at the channel's root (not below a ``/``), page after page, for the kill (SEC-A1b):
    each page read within MAX_LISTING_BYTES, and past ``limit`` names in all, ``Truncated`` — never
    a listing cut taken for the whole."""
    marker, seen = "", 0
    while True:
        params = {"restype": "container", "comp": "list", "delimiter": "/"}
        if marker:
            params["marker"] = marker
        r, body = fetch(get, url, headers, limit=MAX_LISTING_BYTES, params=params,
                        what="a listing page of the channel")
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code} listing the channel")
        root = ET.fromstring(body)
        for blob in root.iter("Blob"):
            seen += 1
            if seen > limit:
                raise Truncated(f"the channel lists more than {limit} blobs: not all seen")
            yield blob
        marker = root.findtext("NextMarker", "").strip()     # absent or empty: the last page
        if not marker:
            return


def _bounded(blobs, skipped: dict):
    """The listing's blobs until the pull's budget is spent on a page: said in ``skipped``
    (``"listing"``), the rest waits for the next pull."""
    try:
        yield from blobs
    except Spent as e:
        skipped["listing"] = f"not listed whole: {e}"


def pull_campaigns(directory: Path, *, channel: str | None = None, credential=None,
                   get=None) -> tuple[int, set[str]]:
    """Copy the published campaigns into ``directory`` (``runs/glorfindel/campaigns`` on Imladris, SEC18):
    ``<campaign_id>/runs/<run_id>.json``, then ``<campaign_id>/manifest.json``, each new or
    changed since the local copy, written whole (tmp, then replace). A blob of any other
    shape is skipped; the windows are never touched.

    The runs first, the manifests last, and a campaign's manifest only when every one of
    its runs came: a manifest here says its runs are here too (analysis/hosted_report.py
    reads a ``done`` manifest as « report due »). Beside each manifest, a ``PULLED`` marker:
    the hosted report writes only the campaigns that came this way, never one of a local run
    on the same runs directory. Returns how many files were written, and the campaigns whose
    pull failed (a run or the manifest refused) — not due at this pull."""

    url = channel if channel is not None else channel_url()
    if not url:
        return 0, set()
    headers = auth_headers(credential, url)
    directory = Path(directory)
    runs, manifests = [], []
    budget = Budget()
    try:
        for blob in _blobs(get, url, headers, f"{CAMPAIGNS}/", budget=budget):
            name = blob.findtext("Name") or ""
            m = _CAMPAIGN_BLOB.match(name)
            if not m or not _safe_part(m["cid"]) or (m["rid"] is not None and not _safe_part(m["rid"])):
                continue
            (manifests if m["rid"] is None else runs).append((blob, name, m))
    except Spent as e:   # a listing cut: no campaign is known whole, none is written
        print(f"[exercise-channel] {e}: the campaigns wait for the next pull")
        return 0, {m["cid"] for _, _, m in runs + manifests}
    written, failed, downloads = 0, set(), 0
    for blob, name, m in runs + manifests:
        if m["rid"] is None and m["cid"] in failed:
            continue  # a run of it did not come: its manifest waits for the next pull
        local = directory / m["cid"] / ("manifest.json" if m["rid"] is None
                                        else f"runs/{m['rid']}.json")
        modified = blob.findtext("Properties/Last-Modified")
        if local.exists() and modified:
            if parsedate_to_datetime(modified).timestamp() <= local.stat().st_mtime:
                if m["rid"] is None:
                    (local.parent / PULLED).touch()
                continue
        if downloads >= MAX_DOWNLOADS or budget.left <= 0:  # V-21: the rest waits; its manifest with it
            failed.add(m["cid"])
            continue
        downloads += 1
        try:
            r, body = fetch(get, f"{url}/{name}", headers, what=name, budget=budget)
        except TooLarge as e:
            print(f"[exercise-channel] {e} — not pulled")
            failed.add(m["cid"])
            continue
        if not r.ok:
            failed.add(m["cid"])
            continue
        from eregion_core import runs_layout
        if runs_layout.pull_root(directory) or runs_layout.parents_hold(Path(directory), local):   # SEC18
            failed.add(m["cid"])
            continue
        tmp = local.with_suffix(".json.tmp")
        tmp.write_bytes(body)
        tmp.replace(local)  # atomic: the report never reads half a manifest
        if m["rid"] is None:  # this campaign came from the channel: its report is Imladris's
            (local.parent / PULLED).touch()
        written += 1
    return written, failed


def pull_runs(directory: Path, *, refusal, channel: str | None = None, credential=None,
              get=None) -> tuple[int, dict[str, str]]:
    """Copy into ``directory`` (``runs/glorfindel`` on Imladris, SEC18) the published report of each run launched
    alone, as ``<run_id>.json``, new or changed since the local copy, written whole (tmp,
    then replace). Each one is read against the shape Imladris accepts first — ``refusal(report,
    run_id)`` says why not, "" when it does (analysis/campaign_schema.py
    ``run_report_refusal``, H-1) — and a refused one is not written. A local file without
    its ``PULLED_RUNS`` marker (a run of this host) is never written over. Returns how many
    were written, and why each one that was not, by run id; the windows and the campaigns
    are never touched."""
    import json

    url = channel if channel is not None else channel_url()
    if not url:
        return 0, {}
    headers = auth_headers(credential, url)
    directory = Path(directory)
    marks = directory / PULLED_RUNS
    written, skipped, downloads = 0, {}, 0
    budget = Budget()
    for blob in _bounded(_blobs(get, url, headers, f"{RUNS}/", budget=budget), skipped):
        name = blob.findtext("Name") or ""
        m = _RUN_BLOB.match(name)
        if not m or not safe_part(m["rid"]):
            continue
        rid = m["rid"]
        local, mark = directory / f"{rid}.json", marks / rid
        if local.exists():
            if not mark.exists():
                skipped[rid] = "a report of this name is here already, not pulled: kept"
                continue
            modified = blob.findtext("Properties/Last-Modified")
            if modified and parsedate_to_datetime(modified).timestamp() <= local.stat().st_mtime:
                continue
        if downloads >= MAX_DOWNLOADS:
            skipped[rid] = f"not pulled yet: {MAX_DOWNLOADS} reports downloaded by this pull"
            continue
        downloads += 1
        try:
            r, content = fetch(get, f"{url}/{name}", headers, what=name, budget=budget)
        except Spent as e:
            skipped[rid] = f"not pulled yet: {e}"
            continue
        except TooLarge as e:
            skipped[rid] = f"refused: {e}"
            continue
        if not r.ok:
            skipped[rid] = f"HTTP {r.status_code} downloading it"
            continue
        try:
            report = json.loads(content)
        except ValueError:
            skipped[rid] = "refused: not JSON"
            continue
        why = refusal(report, rid)
        if why:
            skipped[rid] = f"refused: {why}"
            continue
        from eregion_core import runs_layout
        if why := runs_layout.pull_root(directory) or runs_layout.parents_hold(directory, mark):   # SEC18
            skipped[rid] = f"refused: {why}"
            continue
        mark.touch()  # the marker first: cut before the file, the next pull still writes it
        tmp = local.with_suffix(".json.tmp")
        tmp.write_bytes(content)
        tmp.replace(local)  # atomic: the console never reads half a report
        written += 1
    return written, skipped


# ── Orodruin's word for the console (DG-b): its contract, each request's status ───────────

def publish_doc(name: str, doc: dict, *, channel: str | None = None, credential=None, put=None) -> bool:
    """Write ``orodruin/contract.json`` or ``orodruin/requests/<id>.json``. False without a
    channel; any other name raises."""
    import json
    import requests

    if not _ORODRUIN_BLOB.fullmatch(name):
        raise ValueError(f"not one of Orodruin's blobs: {name!r}")
    url = channel if channel is not None else channel_url()
    if not url:
        return False
    headers = {**auth_headers(credential, url), "x-ms-blob-type": "BlockBlob",
               "Content-Type": "application/json"}
    r = (put or requests.put)(f"{url}/{name}", headers=headers, data=json.dumps(doc).encode(),
                              timeout=15)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} publishing {name}")
    return True


# DRL1 (docs/design/drill-banc.md §2.4, §4.1): the drill of the week's pulse (``drill.json``, written
# by Orodruin at each occurrence, by the operator at the arming, the disarming and the kill) and the
# operator's permit (``drill-permit.json``: written at the arming, removed by the disarming and the
# kill, rewritten by Orodruin as it was, under If-Match). Under Orodruin's prefix, the same container,
# the same assignments: no right more. ``pull_orodruin`` takes neither (its pattern does not): Imladris
# lists them with ``pull_drill`` (DRL1b, below), each read by its one reader (eregion_core/drill_arming.py).
DRILL_BLOB = f"{ORODRUIN}/drill.json"
PERMIT_BLOB = f"{ORODRUIN}/drill-permit.json"
DRILL_BLOBS = (DRILL_BLOB, PERMIT_BLOB)


class Changed(RuntimeError):
    """A conditional write refused (HTTP 412): the blob is no longer the one read — removed, or
    written again, between the read and the write."""


def _drill_url(name: str, channel: str | None) -> str:
    if name not in DRILL_BLOBS:
        raise ValueError(f"not one of the drill's blobs: {name!r}")
    return channel if channel is not None else channel_url()


def publish_drill(name: str, doc: dict, *, if_match: str | None = None, channel: str | None = None,
                  credential=None, put=None) -> bool:
    """Write ``orodruin/drill.json`` or ``orodruin/drill-permit.json``. With ``if_match`` (an ETag
    read), only over that very blob: removed or changed since, ``Changed`` — never written again
    (§2.4: a permit removed is never recreated). False without a channel."""
    import json
    import requests

    url = _drill_url(name, channel)
    if not url:
        return False
    headers = {**auth_headers(credential, url), "x-ms-blob-type": "BlockBlob",
               "Content-Type": "application/json"}
    if if_match is not None:
        headers["If-Match"] = if_match
    r = (put or requests.put)(f"{url}/{name}", headers=headers, data=json.dumps(doc).encode(), timeout=15)
    if r.status_code in (404, 412) and if_match is not None:
        raise Changed(f"{name} is no longer the one read (HTTP {r.status_code}): not written")
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} publishing {name}")
    return True


def read_drill(name: str, *, channel: str | None = None, credential=None, get=None) -> tuple[dict | None, str]:
    """One of the drill's blobs and its ETag: (None, "") when it is absent (404) or no channel is
    configured — an absence; anything else that fails raises (unreadable, never taken for absent)."""
    import json

    url = _drill_url(name, channel)
    if not url:
        return None, ""
    r, body = fetch(get, f"{url}/{name}", auth_headers(credential, url), what=name)
    if r.status_code == 404:
        return None, ""
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} reading {name}")
    try:
        doc = json.loads(body)
    except ValueError:
        raise RuntimeError(f"{name} is not JSON") from None
    if not isinstance(doc, dict):
        raise RuntimeError(f"{name} is not a JSON object")
    return doc, str(r.headers.get("ETag") or "")


def delete_drill(name: str, *, channel: str | None = None, credential=None, delete=None) -> bool:
    """Remove one of the drill's blobs: True when it was there, False when it was not (404).
    Anything else raises. No channel: a ``RuntimeError`` — nothing proven removed."""
    import requests

    url = _drill_url(name, channel)
    if not url:
        raise RuntimeError(f"no exercise channel: {name} not removed")
    r = (delete or requests.delete)(f"{url}/{name}", headers=auth_headers(credential, url), timeout=15)
    if r.status_code == 404:
        return False
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} removing {name}")
    return True


def orodruin_refusal(name: str, doc) -> str:
    """Why a blob of Orodruin's is not believed — "" when it has its shape."""
    from eregion_core.exercise_request import RequestRefused, read_status
    from eregion_core.orodruin import read_contract
    m = _ORODRUIN_BLOB.fullmatch(name)
    if not m:
        return "not one of Orodruin's blobs"
    try:
        if m["rid"] is None:
            read_contract(doc)
        else:
            read_status(doc)
            if doc["request"] != m["rid"]:
                return "the status of another request"
    except (ValueError, RequestRefused) as e:
        return str(e)
    return ""


def pull_orodruin(directory: Path, *, channel: str | None = None, credential=None,
                  get=None) -> tuple[int, dict[str, str]]:
    """Copy into ``directory`` (``runs/glorfindel/orodruin`` on Imladris, SEC18) Orodruin's verdict (``contract.json``)
    and the status of each request (``requests/<id>.json``), new or changed since the local
    copy, each read against its shape first (``orodruin_refusal``) — a refused one is never
    written. Within the bounds of V-21. Returns how many were written, and why each one that was
    not, by blob."""
    import json

    url = channel if channel is not None else channel_url()
    if not url:
        return 0, {}
    headers = auth_headers(credential, url)
    directory = Path(directory)
    written, skipped, downloads = 0, {}, 0
    budget = Budget()
    for blob in _bounded(_blobs(get, url, headers, f"{ORODRUIN}/", budget=budget), skipped):
        name = blob.findtext("Name") or ""
        if not _ORODRUIN_BLOB.fullmatch(name):
            continue
        local = directory / name[len(ORODRUIN) + 1:]
        modified = blob.findtext("Properties/Last-Modified")
        if local.exists() and modified and parsedate_to_datetime(modified).timestamp() <= local.stat().st_mtime:
            continue
        if downloads >= MAX_DOWNLOADS:
            skipped[name] = f"not pulled yet: {MAX_DOWNLOADS} downloaded by this pull"
            continue
        downloads += 1
        try:
            r, body = fetch(get, f"{url}/{name}", headers, what=name, budget=budget)
        except Spent as e:
            skipped[name] = f"not pulled yet: {e}"
            continue
        except TooLarge as e:
            skipped[name] = f"refused: {e}"
            continue
        if not r.ok:
            skipped[name] = f"HTTP {r.status_code} downloading it"
            continue
        try:
            doc = json.loads(body)
        except ValueError:
            skipped[name] = "refused: not JSON"
            continue
        why = orodruin_refusal(name, doc)
        if why:
            skipped[name] = f"refused: {why}"
            continue
        from eregion_core import runs_layout
        if why := runs_layout.pull_root(directory) or runs_layout.parents_hold(directory, local):   # SEC18
            skipped[name] = f"refused: {why}"
            continue
        tmp = local.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        tmp.replace(local)
        written += 1
    return written, skipped


# ── DRL1b (docs/design/drill-banc.md §2.4, §4.1, §4.2): the drill's two blobs, as Imladris sees them ──
# What the last pull saw of them, beside Orodruin's other blobs (``runs/glorfindel/orodruin/``), in one
# file written whole: whether it could list the channel, whether the permit was in that listing (what
# it said, and when it was last listed), and the pulse — its last copy that read, and when the channel
# last wrote it. One file: the judge never reads half of one pull with half of another.
SEEN_FILE = "drill-seen.json"
SEEN_FIELDS = ("at", "listed", "why", "listed_at", "unread_since", "permit", "pulse")
PERMIT_SEEN = ("listed", "doc", "why", "last_listed")
PULSE_SEEN = ("listed", "modified", "why", "doc")


def _drill_listing(get, url: str, headers: dict, budget: Budget) -> dict:
    """The drill's blobs the channel lists now, by name — the listing whole, or it raises: a listing
    cut, or that fails, is never taken for « no permit » (§4.2: the permit's state is then unknown)."""
    cut: list[str] = []
    found = {}
    for blob in _blobs(get, url, headers, f"{ORODRUIN}/drill", delimiter="/", say=cut.append,
                       budget=budget):
        name = blob.findtext("Name") or ""
        if name in DRILL_BLOBS:
            found[name] = blob
    if cut:
        raise Truncated(cut[0])
    return found


def _drill_doc(get, url: str, name: str, headers: dict, budget: Budget, reader) -> tuple[dict | None, str, bool]:
    """(the blob read by its one reader, why not, still there) — a blob gone between the listing and
    its download (404) is no longer there."""
    import json
    try:
        r, body = fetch(get, f"{url}/{name}", headers, what=name, budget=budget)
    except TooLarge as e:
        return None, f"refused: {e}", True
    if r.status_code == 404:
        return None, "gone since it was listed", False
    if not r.ok:
        return None, f"HTTP {r.status_code} downloading it", True
    try:
        doc = reader(json.loads(body))
    except (ValueError, RecursionError) as e:
        return None, f"refused: {e}"[:300], True
    return doc, "", True


def read_seen(directory: Path) -> dict | None:
    """What the last pull saw of the drill's blobs (``pull_drill``), or None: never pulled, or the file
    unreadable, or not of its shape. The permit and the pulse it carries are read again by their one
    reader: one that does not read is None."""
    from eregion_core import channel_reader, drill_arming
    try:
        doc = channel_reader.read_json(Path(directory) / SEEN_FILE)
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(doc, dict) or set(doc) != set(SEEN_FIELDS) or not isinstance(doc["listed"], bool) \
            or not all(isinstance(doc[k], str) for k in ("at", "why", "listed_at", "unread_since")) \
            or not isinstance(doc["permit"], dict) or set(doc["permit"]) != set(PERMIT_SEEN) \
            or not isinstance(doc["pulse"], dict) or set(doc["pulse"]) != set(PULSE_SEEN):
        return None
    for part, reader in (("permit", drill_arming.read_permit), ("pulse", drill_arming.read_pulse)):
        if doc[part]["doc"] is not None:
            try:
                reader(doc[part]["doc"])
            except ValueError:
                doc[part]["doc"] = None
    return doc


def pull_drill(directory: Path, *, channel: str | None = None, credential=None, get=None,
               now: datetime | None = None) -> dict:
    """List the drill's two blobs in the channel, on Imladris (DRL1b), and write down what was seen, in
    one file written whole (``drill-seen.json`` in ``directory``: ``runs/glorfindel/orodruin`` on
    Imladris, SEC18):

    - ``listed``: whether the listing went through, whole — else ``why``, and ``unread_since``, the
      first pull that could not list since the last one that could (§4.2, ``channel_unread``);
    - ``permit``: whether **the listing** names it (``listed``) and, when it does, what it says, read
      by its one reader (``drill_arming.read_permit``) — never a copy of an earlier pull: the listing
      alone says the permit is there; ``last_listed``, the last pull whose listing named it (the
      disarming and the kill remove it before they write the pulse: a grace, glorfindel/drill_watch.py);
    - ``pulse``: whether the listing names ``drill.json``, when the channel last wrote it (its
      ``Last-Modified``, Azure's clock — never Orodruin's word), why it did not read, and its last copy
      that read (``doc``, by ``drill_arming.read_pulse``) — refused (an Imladris older than Orodruin) or
      no longer listed, the copy before stays and ``why`` says it.

    Without a channel, nothing is written ({}). Never raises: a failure is a listing that did not go
    through, written down."""
    import json
    from eregion_core import channel_reader, drill_arming, runs_layout

    now = now or datetime.now(timezone.utc)
    url = channel if channel is not None else channel_url()
    if not url:
        return {}
    directory = Path(directory)
    before = read_seen(directory) or {}
    at = now.isoformat()
    was = before.get("permit") or {}
    permit = {"listed": False, "doc": None, "why": "", "last_listed": str(was.get("last_listed") or "")}
    kept = before.get("pulse") or {}
    pulse = {"listed": False, "modified": str(kept.get("modified") or ""), "why": "", "doc": kept.get("doc")}
    try:
        headers = auth_headers(credential, url)
        budget = Budget()
        listed = _drill_listing(get, url, headers, budget)
        if PERMIT_BLOB in listed:
            doc, why, there = _drill_doc(get, url, PERMIT_BLOB, headers, budget, drill_arming.read_permit)
            permit.update(listed=there, doc=doc, why=why, last_listed=at if there else permit["last_listed"])
        if DRILL_BLOB in listed:
            modified = listed[DRILL_BLOB].findtext("Properties/Last-Modified") or ""
            doc, why, there = _drill_doc(get, url, DRILL_BLOB, headers, budget, drill_arming.read_pulse)
            pulse.update(listed=there, why=why)
            if doc is not None:
                pulse.update(doc=doc, modified=(parsedate_to_datetime(modified).astimezone(timezone.utc).isoformat()
                                                if modified else at))
    except Exception as e:   # unread: the permit's state is unknown, never « absent »
        seen = {"at": at, "listed": False, "why": f"{type(e).__name__}: {e}"[:300],
                "listed_at": str(before.get("listed_at") or ""),
                "unread_since": (str(before.get("unread_since") or at) if before.get("listed") is False else at),
                "permit": before.get("permit") or permit, "pulse": before.get("pulse") or pulse}
    else:
        seen = {"at": at, "listed": True, "why": "", "listed_at": at, "unread_since": "",
                "permit": permit, "pulse": pulse}
    if not (runs_layout.pull_root(directory) or runs_layout.parents_hold(directory, directory / SEEN_FILE)):
        with contextlib.suppress(OSError):
            channel_reader.write_file(directory / SEEN_FILE, json.dumps(seen))
    return seen
