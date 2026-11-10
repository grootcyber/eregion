#!/usr/bin/env python3
"""RST1 (#680, g): when the secrets of the workstation's three pairs end — `make azure-pairs-expiry`.

On the bench, 09/11, the console's pair was left commented in `.envrc`: a restore under an empty pair
takes another identity without saying so (docs/operations.md, « Identités Azure »). The session
reactivated it with a 30-day secret. This reads, on demand, the end date of each pair's secrets —
the watch's, the console's, the bot's — under the operator's own `az login`
(`az ad app credential list`, Microsoft Graph), and says:
  - « aucune paire » for a pair whose `…_CLIENT_ID` is empty;
  - a warning under 14 days, and a secret already expired;
  - several valid secrets on one application: their dates, and that one is expected;
  - an expired secret beside a valid one: an old one, to remove — the pair is not broken.

What it never does: print a secret (only `endDateTime` is asked of az, never `hint` nor a password),
print a client id (each pair by its name), or run at start — `check-azure-env` and Glorfindel's
start never call Graph. Stdlib only. Exit 1 when a pair's date can't be read or none of its
secrets is valid, 0 otherwise (a warning, an absent pair, an old expired secret beside a valid one
included).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

PAIRS = (("watch", "GLORFINDEL_AZURE_CLIENT_ID"),
         ("console", "EREGION_CONSOLE_AZURE_CLIENT_ID"),
         ("bot", "GLORFINDEL_BOT_AZURE_CLIENT_ID"))
WARN_DAYS = 14
ROTATE = "docs/operations.md, « Faire tourner un secret »"
_GUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _parse(value: str) -> datetime:
    # Graph may give seven digits of a second: Python reads six.
    text = re.sub(r"(\.\d{6})\d+", r"\1", str(value).strip().replace("Z", "+00:00"))
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def end_dates(app_id: str, az: str = "az") -> list[datetime]:
    """The end date of each secret of the application, sorted — only `endDateTime` asked."""
    res = subprocess.run([az, "ad", "app", "credential", "list", "--id", app_id,
                          "--query", "[].endDateTime", "-o", "json"],
                         capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        first = (res.stderr or res.stdout or "").strip().splitlines()[:1]
        raise RuntimeError(_GUID.sub("<id>", first[0] if first else f"az a rendu {res.returncode}")[:300])
    values = json.loads(res.stdout or "[]")
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise RuntimeError("réponse d'az inattendue (une liste de dates attendue)")
    return sorted(_parse(v) for v in values)


def report(env: dict, now: datetime, az: str = "az") -> tuple[list[str], bool]:
    """(the lines to print, whether a pair is broken: unreadable or expired)."""
    lines, broken = [], False
    for name, var in PAIRS:
        app_id = (env.get(var) or "").strip()
        if not app_id:
            lines.append(f"ℹ {name} : aucune paire ({var} vide)")
            continue
        try:
            dates = end_dates(app_id, az)
        except Exception as e:  # noqa: BLE001 — said, never a success
            lines.append(f"✗ {name} : date de fin illisible ({_GUID.sub('<id>', str(e))})")
            broken = True
            continue
        if not dates:
            lines.append(f"⚠ {name} : aucun secret lu sur son application — la paire ne peut pas se connecter")
            broken = True
            continue
        valid = [d for d in dates if d >= now]
        expired = [d for d in dates if d < now]
        if not valid:
            when = expired[-1].strftime("%Y-%m-%d")
            lines.append(f"✗ {name} : secret expiré le {when} — le faire tourner ({ROTATE})")
            broken = True
            continue
        first = valid[0]
        days = (first - now).total_seconds() / 86400
        when = first.strftime("%Y-%m-%d")
        if days < WARN_DAYS:
            lines.append(f"⚠ {name} : secret qui expire dans {int(days)} j, le {when} — le faire tourner ({ROTATE})")
        else:
            lines.append(f"✓ {name} : secret valable jusqu'au {when} ({int(days)} j)")
        # An old secret, expired beside a valid one: no longer a way in, to remove — the pair holds.
        for d in expired:
            lines.append(f"  ⚠ {name} : un ancien secret expiré le {d.strftime('%Y-%m-%d')}, à retirer "
                         "(az ad app credential delete)")
        if len(valid) > 1:
            lines.append(f"  ⚠ {name} : {len(valid)} secrets valables ({', '.join(d.strftime('%Y-%m-%d') for d in valid)})"
                         " — un seul attendu : celui de .envrc ne se distingue pas des autres ; retirer les anciens")
    return lines, broken


def main() -> int:
    lines, broken = report(dict(os.environ), datetime.now(timezone.utc))
    print("\n".join(lines))
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
