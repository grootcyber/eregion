"""FS1g (#1127): the console's side of the restore queue — behind ``EREGION_ACTION_QUEUE=1`` only.
Without it, nothing changes: the restore route runs ``glorfindel restore --before`` in the background,
as before (eregion_console/api.py, ``_bg_restore``).

With it, the route no longer restores: once its own guards hold (the card, the moment — SEC1,
SEC4c), it deposits a request signed by the console's key in ``runs/console/restore/``, for the
restore executor (glorfindel/restore_executor.py), never the watch. It answers at once — the page
says « restore requested » as before. What became of it is said on the card, as a refused or failed
command always was (``restore_failures``, SEC4c): ``settle``, run with each read of the page's state,
reads the executor's receipt of each request of the console and notes it — refused (and why),
failed, not taken in its life; started, the card's last refusal cleared, the job said as any other.

The executor replays every guard; until TOT1 (#685) brings the operator's one-time code, it refuses
every request (``second_factor``), and the card says it.
"""
from __future__ import annotations

from eregion_core import restore_queue as rq

SERVICE = "console"


def ask(vm_name: str, resource_id: str, card: str, before: str, *, root, by: dict, started=None) -> dict:
    """The card's restore deposited for the executor, never awaited: what the route answers.
    ``started(vm_name, resource_id)``: the restore said in progress on the card until its receipt."""
    asked = rq.deposit(SERVICE, resource_id, card=card, before=before, by=by, root=root)
    if "error" in asked:
        return {"error": asked["error"]}
    if started is not None:
        started(vm_name, resource_id)
    return {"status": "requested", "via": "restore-queue", "request": asked["request"],
            "resource_id": resource_id, "before": before}


def _said(followed: dict) -> str | None:
    """What the card says of a request whose fate is final: None once the restore started; else
    why it did not (its code and its reason, never a secret: the executor masks what it writes)."""
    r = followed.get("receipt")
    if r is None:
        return f"restore queue ({followed.get('state', '?')}): {followed.get('error') or '?'}"
    if r.get("state") == "done":
        return None
    code = f" ({r['code']})" if r.get("code") else ""
    return f"restore {r.get('state')}{code}: {r.get('reason') or '?'}"


def settle(*, root, noted, done, now=None) -> int:
    """Each restore request of the console whose fate is final, said on its card once and withdrawn:
    ``noted(card, vm_name, error_or_None)`` (the card's last restore), ``done(vm_name)`` (no longer in
    progress). How many settled. Never raises."""
    n = 0
    public = rq.pinned_key()
    for request_id in rq.waiting(SERVICE, root):
        try:
            followed = rq.follow(SERVICE, request_id, root=root, public=public, now=now)
            if not followed["final"]:
                continue
            own = rq.own_request(SERVICE, request_id, root) or {}
            card = str(own.get("card") or (followed.get("receipt") or {}).get("card") or "")
            vm = str(own.get("resource_id") or "").rstrip("/").rsplit("/", 1)[-1]
            if not rq.withdraw(SERVICE, request_id, root):
                continue                 # another read settled it
            if card:
                noted(card, vm, _said(followed))
            if vm:
                done(vm)
            n += 1
        except Exception:
            continue
    return n
