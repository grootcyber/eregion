#!/usr/bin/env python3
"""RST1 (#680, g): when the secrets of the workstation's three pairs end — `make azure-pairs-expiry`.

On the bench, 09/11, the console's pair was left commented in `.envrc`: a restore under an empty pair
takes another identity without saying so (docs/operations.md, « Identités Azure »). The session
reactivated it with a 30-day secret. This reads, on demand, the end date of each pair's secrets —
the watch's, the console's, the bot's — under the operator's own `az login` (Microsoft Graph).

PAIR1 (#736): a pair's secret lives on one of two objects, its application or its service
principal. On the bench, 12/11, the watch's was on its application, the console's on its service
principal — and `az ad app credential list`, which reads only the application, said « aucun
secret » of a pair that connected, and would never have seen its secret expire. So each pair is
read twice, `az ad app show --id <appId>` then `az ad sp show --id <appId>`, both asked the same
query, the end dates only:

    {secrets: passwordCredentials[].endDateTime, certificates: keyCredentials[].endDateTime}

and each date is said with where it lives (« sur son principal de service »). It says:
  - « aucune paire » for a pair whose `…_CLIENT_ID` is empty;
  - the nearest end of the two objects decides: a warning under 14 days, ✗ when none is valid;
  - « aucun secret ni certificat » only when both objects are read and both are empty (✗);
  - an object that can't be read: ✗, said so, never read as « aucun » — and no ✓ beside it, a
    nearer date could be there;
  - several valid secrets: their dates and places, and that one is expected;
  - an expired secret beside a valid one: an old one, to remove — the pair is not broken.

What it never does: print a secret (only `endDateTime` is asked of az, never `hint` nor a password),
print a client id or a key id (each pair by its name), or run at start — `check-azure-env` and
Glorfindel's start never call Graph. Stdlib only. Exit 1 when a pair's object can't be read, it
holds no secret, or none of its secrets is valid; 0 otherwise (a warning, an absent pair, an old
expired secret beside a valid one included).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

PAIRS = (("watch", "GLORFINDEL_AZURE_CLIENT_ID"),
         ("console", "EREGION_CONSOLE_AZURE_CLIENT_ID"),
         ("bot", "GLORFINDEL_BOT_AZURE_CLIENT_ID"))
WARN_DAYS = 14
ROTATE = "docs/operations.md, « Faire tourner un secret »"
_GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")

# The two objects a pair's secret can live on, read in this order: az's word, and how it is said.
OBJECTS = (("app", "son application"), ("sp", "son principal de service"))
# What each object is asked: its credentials' end dates, nothing else (never a hint, a key id, a secret).
QUERY = "{secrets: passwordCredentials[].endDateTime, certificates: keyCredentials[].endDateTime}"
# Each list of the answer: its key, how one of it is said, the flag of its delete.
KINDS = (("secrets", "secret", ""), ("certificates", "certificat", " --cert"))


@dataclass(frozen=True)
class Credential:
    end: datetime
    kind: str        # « secret » or « certificat »
    obj: str         # « app » or « sp »
    cert_flag: str   # « --cert » for a certificate's delete, empty for a secret's


def _parse(value: str) -> datetime:
    # Graph may give seven digits of a second: Python reads six.
    text = re.sub(r"(\.\d{6})\d+", r"\1", str(value).strip().replace("Z", "+00:00"))
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _where(obj: str) -> str:
    return dict(OBJECTS)[obj]


def credentials(app_id: str, obj: str, az: str = "az") -> list[Credential]:
    """The end date of each secret and certificate of one object (`app` or `sp`), only the dates
    asked. Raises when az fails or answers anything but the two lists: never read as « aucun »."""
    res = subprocess.run([az, "ad", obj, "show", "--id", app_id, "--query", QUERY, "-o", "json"],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        first = (res.stderr or res.stdout or "").strip().splitlines()[:1]
        raise RuntimeError(_GUID.sub("<id>", first[0] if first else f"az a rendu {res.returncode}")[:300])
    try:
        doc = json.loads(res.stdout)
    except ValueError:
        raise RuntimeError("réponse d'az illisible") from None
    out = []
    for key, kind, flag in KINDS:
        values = doc.get(key) if isinstance(doc, dict) else None
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise RuntimeError(f"réponse d'az inattendue (une liste de dates attendue sous « {key} »)")
        out += [Credential(_parse(v), kind, obj, flag) for v in values]
    return out


def _plural(creds: list[Credential]) -> str:
    kinds = {c.kind for c in creds}
    if kinds == {"secret"}:
        return "secrets"
    return "certificats" if kinds == {"certificat"} else "secrets ou certificats"


def _day(c: Credential) -> str:
    return c.end.strftime("%Y-%m-%d")


def report(env: dict, now: datetime, az: str = "az") -> tuple[list[str], bool]:
    """(the lines to print, whether a pair is broken: unreadable, without a secret, or expired)."""
    lines, broken = [], False
    for name, var in PAIRS:
        app_id = (env.get(var) or "").strip()
        if not app_id:
            lines.append(f"ℹ {name} : aucune paire ({var} vide)")
            continue
        found: list[Credential] = []
        unread: list[str] = []
        for obj, where in OBJECTS:
            try:
                found += credentials(app_id, obj, az)
            except Exception as e:  # noqa: BLE001 — said, never a success, never « aucun »
                lines.append(f"✗ {name} : date de fin illisible sur {where} ({_GUID.sub('<id>', str(e))})")
                unread.append(where)
                broken = True
        if not found:
            if not unread:
                lines.append(f"✗ {name} : aucun secret ni certificat, ni sur son application ni sur son principal "
                             "de service — la paire ne peut pas se connecter")
                broken = True
            continue
        # The nearest end of the two objects decides; an unread one may hold a nearer: never a ✓ then.
        found.sort(key=lambda c: c.end)
        partial = f" ; {' et '.join(unread)} illisible : une date plus proche peut s'y trouver" if unread else ""
        valid = [c for c in found if c.end >= now]
        expired = [c for c in found if c.end < now]
        if not valid:
            last = expired[-1]
            lines.append(f"✗ {name} : {last.kind} expiré le {_day(last)} sur {_where(last.obj)}"
                         f" — le faire tourner ({ROTATE}){partial}")
            broken = True
            continue
        first = valid[0]
        days = (first.end - now).total_seconds() / 86400
        where = _where(first.obj)
        if days < WARN_DAYS:
            lines.append(f"⚠ {name} : {first.kind} qui expire dans {int(days)} j, le {_day(first)}, sur {where}"
                         f" — le faire tourner ({ROTATE}){partial}")
        else:
            mark = "⚠" if unread else "✓"
            lines.append(f"{mark} {name} : {first.kind} valable jusqu'au {_day(first)} ({int(days)} j), "
                         f"sur {where}{partial}")
        # An old secret, expired beside a valid one: no longer a way in, to remove — the pair holds.
        for c in expired:
            lines.append(f"  ⚠ {name} : un ancien {c.kind} expiré le {_day(c)} sur {_where(c.obj)}, à retirer "
                         f"(az ad {c.obj} credential delete{c.cert_flag})")
        if len(valid) > 1:
            mixed = len({c.kind for c in valid}) > 1
            said = ", ".join((f"{c.kind} " if mixed else "") + f"{_day(c)} sur {_where(c.obj)}" for c in valid)
            lines.append(f"  ⚠ {name} : {len(valid)} {_plural(valid)} valables ({said})"
                         " — un seul attendu : celui de .envrc ne se distingue pas des autres ; retirer les anciens")
    return lines, broken


def main() -> int:
    lines, broken = report(dict(os.environ), datetime.now(timezone.utc))
    print("\n".join(lines))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
