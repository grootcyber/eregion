"""The expiry of a block in the exposed zone (SEC2c, #1107; decision 7 of 23/11): lifted by the watch, said.

A block written on one host of the exposed zone (glorfindel/exposed_zone.py) carries `exposed` in its entry
(~/.glorfindel/blocks/<vm>.json): its zone, its deadline (`expires_at`, 24 h after its first write) and who
held the address then (`holder`). Written, never in memory: the deadline outlives a restart of the watch.

Each pass of the watch's housekeeping (about every minute, `expiry_pass`), in a thread of its own, each
entry that carries it is lifted, under its VM's lock, by the connector's own unblock (`unblock_ip`: every
rule of the block, the guards of I4B kept):

- **at its deadline** — then re-judged: a new detection blocks again, for 24 h more;
- **as soon as the address is held by another VM** than when it was blocked — the discovery's read (every
  10 min), fresh only: a list that can't be trusted tells no holder, the deadline alone then.

Said each time, on the console and on Discord (a card, `LIFTED_TYPE`, by the path of every card), and in
the watch's log. **A lift that fails** (Azure refuses, a rule held back, the watch read-only) keeps the
entry — the rules still there keep blocking — and is said on a card of its own (`FAILED_TYPE`, high, folded
while it lasts, closed once the lift passes); it is tried again at the next pass, every minute, until it
passes or a human lifts the block. Blocks of the Internet carry no deadline: they do not change.

**What it reads is written in ~/.glorfindel**, which the console and the bot mount writable
(docs/design/modele-de-menace.md, as for every block's entry): a writer of theirs could move a deadline
sooner — a block lifted early, what an unblock of theirs already can — or remove it — the block then kept,
an Internet one's fate. Never a block written: the lift only ever takes off what Glorfindel put.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("glorfindel.exposed_blocks")

LIFTED_TYPE = "exposed_block_lifted"
FAILED_TYPE = "exposed_block_lift_failed"
_LOCK_WAIT_S = 30


def _when(text) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def marked() -> list[dict]:
    """The recorded blocks of the exposed zone (a cheap local read: no Azure call when there are none)."""
    from glorfindel.actions import active_blocks
    return [b for b in active_blocks() if isinstance(b.get("exposed"), dict) and b.get("resource_id")]


def due(entry: dict, now: datetime, snap) -> str:
    """Why this block of the exposed zone is to be lifted now — "" when not yet. A deadline that can't be
    read is a deadline past: never a block of the zone kept without end on a value nobody can read."""
    from glorfindel.exposed_zone import holder_of
    mark = entry.get("exposed") or {}
    deadline = _when(mark.get("expires_at"))
    if deadline is None:
        return f"échéance illisible ({str(mark.get('expires_at'))[:40]!r}) : levé comme à échéance"
    if now >= deadline:
        return f"échéance de 24 h atteinte (posé le {str(mark.get('at') or entry.get('blocked_at'))[:16]} UTC)"
    if snap.state != "fresh":
        return ""
    now_held, then = holder_of(entry.get("ip", ""), snap), str(mark.get("holder") or "")
    if now_held and now_held != then:
        short = ", ".join(v.rsplit("/", 1)[-1] for v in now_held.split(","))
        return (f"l'adresse est passée à une autre VM ({short}"
                + (f", tenue avant par {', '.join(v.rsplit('/', 1)[-1] for v in then.split(','))}" if then else "")
                + ")")
    return ""


def expiry_pass(connector, now: datetime | None = None) -> list[dict]:
    """Each block of the exposed zone due, lifted and said: `[{vm, ip, why, outcome, detail}]`. Never
    raises for one entry: the others are still read."""
    from glorfindel.client_network import load
    entries = marked()
    if not entries:
        return []
    now = now or datetime.now(timezone.utc)
    snap = load(now)
    report: list[dict] = []
    for entry in entries:
        why = due(entry, now, snap)
        if why:
            report.append(_lift(connector, entry, why))
    return report


def _lift(connector, entry: dict, why: str) -> dict:
    from glorfindel.actions import _load_block_entries, _vm_lock
    from glorfindel.response.policy import _first_line
    vm, ip, rid = entry["vm_name"], entry.get("ip", ""), entry["resource_id"]
    out: dict = {}
    try:
        with _vm_lock(vm, timeout=_LOCK_WAIT_S):
            now_entry = next((e for e in _load_block_entries(rid) if e.get("ip") == ip), None)
            if not now_entry or not isinstance(now_entry.get("exposed"), dict):
                return {"vm": vm, "ip": ip, "why": why, "outcome": "gone", "detail": "levé entre-temps"}
            try:
                out = connector.unblock_ip(ip, rid)
            except Exception as exc:
                out = {"status": "error", "failed": [f"{type(exc).__name__}: {_first_line(exc)}"]}
    except TimeoutError:
        return {"vm": vm, "ip": ip, "why": why, "outcome": "busy", "detail": "VM occupée : prochaine passe"}
    if out.get("status") in ("unblocked", "not_found"):
        return _said_lifted(entry, why, out)
    return _said_failed(entry, why, out)


def _card_id(entry: dict) -> str:
    from glorfindel.actions import _rid_hash
    return f"exposed-{entry['vm_name']}-{_rid_hash(entry['resource_id'])}-{entry.get('ip', '')}".lower()


def _pending_of(entry: dict, kinds: tuple[str, ...]) -> list[dict]:
    """The pending cards of this block's lift (its VM, its address) of these types."""
    from glorfindel import escalations
    rid, ip = entry["resource_id"].rstrip("/").lower(), entry.get("ip", "")
    return [e for e in escalations.pending() if e.get("escalation_type") in kinds
            and str(e.get("resource_id") or "").rstrip("/").lower() == rid
            and (e.get("action_params") or {}).get("ip") == ip]


def _said_lifted(entry: dict, why: str, out: dict) -> dict:
    """The lift said on a card of its own: it replaces this address's card of a failed lift (closed, the
    lift passed) and a lift said before (a new block of the address, lifted again) — never folded into it."""
    from glorfindel import escalations
    from glorfindel.vm_command import group_and_name
    vm, ip, mark = entry["vm_name"], entry.get("ip", ""), entry.get("exposed") or {}
    reason = (f"Blocage de {ip} sur {vm} levé seul par Glorfindel : {why}. Zone exposée {mark.get('zone')} "
              f"({mark.get('source')}) — un blocage y expire au bout de 24 h, puis la prochaine détection "
              "le reprend si l'attaque continue.")
    replaced = {e["id"]: ("levée passée" if e.get("escalation_type") == FAILED_TYPE
                          else "remplacée : un nouveau blocage de l'adresse, levé à son tour")
                for e in _pending_of(entry, (FAILED_TYPE, LIFTED_TYPE))}
    escalations.record(signal_id=f"{_card_id(entry)}-{str(mark.get('at'))[:19]}", resource_id=entry["resource_id"],
                       action="none", escalation_type=LIFTED_TYPE, severity="medium", source="real", reason=reason,
                       action_params={"ip": ip}, replaces=replaced or None,
                       suggested_steps=["Rien à faire si l'adresse ne se manifeste plus",
                                        f"La rebloquer à la main : glorfindel block {ip} "
                                        f"{group_and_name(entry['resource_id'])} --yes (elle expirera de même)"])
    logger.warning("%s", reason)
    return {"vm": vm, "ip": ip, "why": why, "outcome": "lifted", "detail": out.get("status", "")}


def _said_failed(entry: dict, why: str, out: dict) -> dict:
    """A lift that failed: one card while it lasts (folded at each pass), the entry kept for the next."""
    from glorfindel import escalations
    from glorfindel.vm_command import group_and_name
    vm, ip = entry["vm_name"], entry.get("ip", "")
    failed = "; ".join(str(f) for f in out.get("failed") or []) or str(out.get("status") or "?")
    reason = (f"Levée du blocage de {ip} sur {vm} en échec ({why}) : {failed[:600]}. Les règles encore "
              "posées bloquent toujours l'adresse ; Glorfindel retente à chaque passe (environ chaque minute).")
    escalations.record(signal_id=_card_id(entry), resource_id=entry["resource_id"], action="none",
                       escalation_type=FAILED_TYPE, severity="high", source="real", reason=reason,
                       action_params={"ip": ip},
                       suggested_steps=["Lire ce qu'Azure refuse (droits de la watch, un verrou, une règle "
                                        "retournée)",
                                        f"Lever à la main : glorfindel unblock {ip} "
                                        f"{group_and_name(entry['resource_id'])} --yes"])
    logger.warning("%s", reason)
    return {"vm": vm, "ip": ip, "why": why, "outcome": "failed", "detail": failed}


def said(entry: dict, now: datetime | None = None) -> str:
    """What `glorfindel list` adds to a block of the exposed zone — "" for any other."""
    mark = entry.get("exposed")
    if not isinstance(mark, dict):
        return ""
    deadline = _when(mark.get("expires_at"))
    if deadline is None:
        return "  · zone exposée, échéance illisible (levé à la prochaine passe)"
    left_h = ((deadline - (now or datetime.now(timezone.utc))).total_seconds()) / 3600
    return (f"  · zone exposée {mark.get('zone')}, levé seul le {deadline.isoformat()[:16].replace('T', ' ')} UTC"
            + (f" (dans {left_h:.1f} h)" if left_h > 0 else " (échu : levé à la prochaine passe)"))
