"""FS1g (#1127): the bot's Restore as a request for the restore executor — behind
``EREGION_ACTION_QUEUE=1`` only (``arun`` is None without it: the bot runs ``glorfindel restore``
as before, glorfindel/bot.py).

With the flag, the confirmed restore is deposited in ``runs/bot/restore/``, signed by the bot's key,
the human named by Discord (``by``: their id and their name — said, never proved; the executor reads
the id against its own copy of DISCORD_ALLOWED_*); then the executor's receipt is followed without
holding a thread, each state said in the VM's thread as it comes, then what the final receipt says.
Done (the restore started): code 0, and the card is acknowledged as before; anything else — refused
(until TOT1, #685, every request: ``second_factor``), failed, not taken —: said, the card stays open
(SEC4c).
"""
from __future__ import annotations

import asyncio

from eregion_core import restore_queue as rq

SERVICE = "bot"
POLL_S = 1.0
RUN_S = 900                 # a restore's start waits for the VM's deallocation (minutes)
_STATE_SAID = {"received": "📥 Restore ({rid}) : reçu par l'exécuteur de restore.",
               "accepted": "⚙️ Restore ({rid}) : accepté — l'exécuteur lance le restore."}


def arun(esc: dict, before: str, interaction):
    """The coroutine's maker ``_execute_and_report`` awaits in place of the CLI — None when the
    queue is off (the CLI, as before)."""
    from eregion_core import action_queue as aq
    if not aq.enabled():
        return None
    user, channel = interaction.user, interaction.channel
    return lambda: ask(esc, before, user, channel)


def _text(request_id: str, followed: dict) -> tuple[int, str]:
    head = f"restore ({request_id[:8]})"
    if "receipt" not in followed:
        return 1, f"{head} : {followed.get('state', '?')} — {followed.get('error') or '?'}"
    r = followed["receipt"]
    said = f"{head} : {r['state']}" + (f" — {r['code']}" if r.get("code") else "")
    if r.get("reason"):
        said += f" : {r['reason']}"
    result = r.get("result") if isinstance(r.get("result"), dict) else {}
    if result.get("recovery_point_time"):
        said += f"\npoint de restauration : {result['recovery_point_time']}"
    return (0 if r["state"] == "done" else 1), said


async def ask(esc: dict, before: str, user, channel, poll_s: float | None = None) -> tuple[int, str]:
    """The card's restore deposited, then its receipt followed — (code, what it says)."""
    from glorfindel import restore_plan
    poll_s = POLL_S if poll_s is None else poll_s
    try:
        moment = restore_plan.parse_moment(before)
    except ValueError as exc:
        return 1, f"restore : le moment ne se lit pas ({exc})"
    by = {"via": "discord", "user": str(getattr(user, "id", "") or ""),
          "name": str(getattr(user, "display_name", "") or "")[:100]}
    loop = asyncio.get_running_loop()
    deposited = await loop.run_in_executor(None, lambda: rq.deposit(
        SERVICE, str(esc.get("resource_id") or ""), card=str(esc.get("id") or ""), before=moment, by=by))
    if "error" in deposited:
        return 1, f"restore : {deposited['error']}"
    rid = deposited["request"]
    await channel.send(f"📨 Restore ({rid[:8]}) : demande déposée — l'exécuteur de restore la juge.")
    public, said, started = rq.pinned_key(), set(), loop.time()
    while True:
        followed = rq.follow(SERVICE, rid, public=public)
        state = followed["state"]
        if state in _STATE_SAID and state not in said:
            said.add(state)
            await channel.send(_STATE_SAID[state].format(rid=rid[:8]))
        if followed["final"]:
            break
        if loop.time() - started > rq.TAKE_S + RUN_S:
            return 1, (f"restore ({rid[:8]}) : toujours « {state} » après {rq.TAKE_S + RUN_S:.0f} s — son reçu "
                       "le dira ; la carte reste ouverte")
        await asyncio.sleep(poll_s)
    rq.withdraw(SERVICE, rid)
    return _text(rid, followed)
