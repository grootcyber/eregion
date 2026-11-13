"""FS1b (#563, docs/design/file-actions-signee.md §2.9): the operator's lifts of a containment — a
release, a reset — out of glorfindel/cli.py as callables, so the watch runs a request of the queue
with the CLI's own code (glorfindel/queue_watch.py), never a copy of it. The CLI keeps its prompt
and its words around them (``release``, ``reset``); what they do is here.

CMD1 (#797): and the containments a human makes by hand — ``glorfindel isolate``, ``glorfindel block``
(``direct_refusal``, ``address_refusal``, ``contain``): the console's approval of a held card, without
the card, the same calls and the same guards.
"""
from __future__ import annotations


def release_needed(connector, resource_id: str) -> bool:
    """False when no NIC still carries an isolation rule — then the stale state is cleared, so the
    console updates. A partially isolated VM (one NIC still cut off) needs its release: the former
    test (``not verify_isolation()``) cleared its state, the rule left orphaned."""
    verification = connector.verify_release(resource_id)
    if verification.get("verified"):
        from glorfindel.actions import _clear_isolation_state
        _clear_isolation_state(resource_id)      # by id: two VMs may share a name
        return False
    return True


def reset_targets(resource_id: str) -> tuple[list[dict], list[dict]]:
    """(the isolations, the blocks) the local state holds on this VM — what a reset lifts.
    Case-insensitive: Azure ARM ids are, Python's == is not (an orphan isolation state was left,
    « Nothing to reset » while `list` still showed ISOLATED). Its isolation state unreadable is
    not « nothing to reset »: the release says what it can't verify, the file kept (I3U, #440)."""
    from glorfindel.actions import _isolation_unreadable, active_blocks, active_isolations
    rid_lower = resource_id.lower()
    isolations = [i for i in active_isolations() if i.get("resource_id", "").lower() == rid_lower]
    blocks = [b for b in active_blocks() if b.get("resource_id", "").lower() == rid_lower]
    isolations = isolations or ([{"resource_id": resource_id}] if _isolation_unreadable(resource_id) else [])
    return isolations, blocks


def reset_apply(connector, resource_id: str, isolations: list[dict], blocks: list[dict],
                say=None) -> list[str]:
    """Lift what ``reset_targets`` found: the isolation released, each block removed. What is
    still in place (each rule a removal could not take off) is returned — empty: the VM is clean.
    ``say``: each step's outcome, as the CLI prints it."""
    leftovers: list[str] = []
    if isolations:
        r = connector.release_isolation(resource_id)
        if say is not None:
            say(f"  [cyan]release_isolation[/cyan] → {r.get('status', '?')}")
        leftovers += r.get("failed", [])
    for b in blocks:
        r = connector.unblock_ip(b["ip"], resource_id)
        if say is not None:
            say(f"  [cyan]unblock {b['ip']}[/cyan] → {r.get('status', '?')}")
        leftovers += r.get("failed", [])
    return leftovers


# ── CMD1 (#797): a containment by a human's hand — `glorfindel isolate`, `glorfindel block` ──────────
#
# The console's approval of a held card (eregion_console/api.py, ``action_approve``), without the card:
# the same calls and the same guards, here, where the CLI calls them and the console may import them
# (D1: glorfindel/ never imports the console). What the CLI keeps: its prompt and its words. What a
# card would have said is asked of the human, who names the VM and the address.

# The cards whose VM is an anchor the detection may not concern (AL1, C2) — the console's, the bot's
# and the TUI's own set (tests/unit/test_cli_contain.py keeps the four equal).
ANCHORED_TYPES = frozenset({"control_plane_change", "identity_change", "unattributed_signal"})


def _same(a: str, b: str) -> bool:
    return (a or "").rstrip("/").lower() == (b or "").rstrip("/").lower()


def _pending_on(resource_id: str) -> list[dict]:
    from glorfindel import escalations
    return [e for e in escalations.pending() if _same(e.get("resource_id", ""), resource_id)]


def direct_refusal(resource_id: str) -> str:
    """Why a human's containment of this VM by the CLI is refused — "" when it is not. A VM's own id
    the watch knows (``approval.in_perimeter``: discovered, held, or the VM of a pending card), never
    another resource; and never a VM a pending card is only anchored on (AL1): the detection does not
    name it — read the card, acknowledge it, then act on the VM it is about."""
    from glorfindel import approval
    if not approval.is_vm_id(resource_id):
        return (f"{str(resource_id)[:80]} : pas une VM connue ici (ni découverte, ni tenue, ni d'une carte) "
                "— son id complet : glorfindel list --ids (ce terminal seulement)")
    if not approval.in_perimeter(resource_id):
        return ("cette VM n'est pas du périmètre de la watch (ni découverte, ni isolée ou bloquée, ni d'une "
                "carte en attente) : rien n'est fait")
    anchored = [e for e in _pending_on(resource_id) if e.get("escalation_type") in ANCHORED_TYPES]
    if anchored:
        ids = ", ".join(str(e.get("id", ""))[:8] for e in anchored)
        return (f"carte(s) {ids} ancrée(s) sur cette VM sans que la détection la nomme (AL1) : la lire, "
                "l'acquitter (glorfindel ack <id>), puis agir sur la VM qu'elle concerne")
    return ""


def address_refusal(ip: str) -> tuple[str, str]:
    """(the address, "") when ``ip`` is one host address Glorfindel may block — the console's two
    guards in their order: ``single_host_ip`` (a range, a tag, ``*``, a reserved address), then the
    never-block list (``approval.address_refusal``, SEC2). Else ("", why)."""
    from glorfindel import approval
    from glorfindel.response.policy import single_host_ip
    try:
        ip = single_host_ip(ip)
    except ValueError as exc:
        return "", str(exc)
    return approval.address_refusal(ip)


def held_cards(resource_id: str, action: str) -> list[dict]:
    """The pending cards of this VM that hold this very action — said by the CLI, never resolved by
    it: the human acknowledges them (``glorfindel ack``) once the containment is verified."""
    return [e for e in _pending_on(resource_id)
            if e.get("action") == action and e.get("escalation_type") not in ANCHORED_TYPES]


def contain(connector, action: str, resource_id: str, *, ip: str = "", scope: str = "vm",
            port: int | None = None, record=None) -> dict:
    """``isolate_vm`` or ``block_suspicious_ip``, then the check after — under the VM's lock for the
    whole gesture, as the watch runs a request of the queue (glorfindel/queue_watch.py). The check is
    the console's (``approval.verify_approved``): the agent's own verification, the gesture noted
    (``record``), a ``verification_failed`` card when it is not ``True``. A dry run calls nothing on
    Azure, writes nothing, verifies nothing. {"result", "verification"} (verification None in a dry
    run)."""
    if action not in ("isolate_vm", "block_suspicious_ip"):
        raise ValueError(f"not a containment: {action!r}")

    def _act() -> dict:
        if action == "isolate_vm":
            return connector.isolate_vm(resource_id)
        return connector.block_suspicious_ip(ip, resource_id, scope, False, port)

    if getattr(connector, "dry_run", False):
        return {"result": _act(), "verification": None}
    from glorfindel import approval
    from glorfindel.response.locks import _vm_lock
    with _vm_lock(resource_id.rstrip("/").rsplit("/", 1)[-1]):
        result = _act()
        verification = approval.verify_approved(connector, {"id": ""}, action, resource_id, result, ip,
                                                record=record, signal_id=f"cli-{action}")
    return {"result": result, "verification": verification}
