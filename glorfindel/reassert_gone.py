"""What the reassertion says of what is no longer there (RSM3, #1036, #1057; docs/design/reaffirmation.md
§3.5, §3.6, E7, E8): a VM deleted (Q6), and a perimeter pair on an NSG that no longer governs its subnet.
Neither is written to: nothing of a VM gone can be read nor put back, and the NSG the customer took off
the subnet is theirs (I2) — nor is the pair put on another one without the operator's decision.

- **A VM deleted** (Q6, Jonathan's decision of 21/11): its own card, « la VM n'existe plus », with the
  command that lifts its isolation or its block (the lift of a VM gone exists, I7S), closed at the lift.
  The card « non vérifiée » (« (ResourceNotFound) … ») and « le reposer a échoué : (ResourceNotFound) »
  said it in covered words, and the pass tried to write for it. Read gone only on the VM's own 404
  (`vm_gone`), and only where the check could not conclude or read rules gone: never on a guess (A0).
- **A perimeter pair on an NSG off the VM's subnet** (E7): gone for where it lies (§2.3: « bypassed »
  supposes the hold intact). Said on a card of the block — the NSG taken off, the subnet no longer
  covered by it —, once per NSG, its own mark (`perimeter_off_said`, as « never covered »'s
  `uncovered_said`), written after the card (L1F); closed once that NSG is read on the subnet again.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

GONE_TYPE = "vm_gone"
OFF_TYPE = "perimeter_off"
_GONE_ACTION = "review_gone_vm"
_GONE_PREFIX = "reassert-gone-"
_OFF_PREFIX = "reassert-off-"


def _gone_id(vm: str, rid: str, ip: str = "") -> str:
    from glorfindel.actions import _rid_hash
    return (f"{_GONE_PREFIX}{'block' if ip else 'iso'}-{vm}-{_rid_hash(rid)}" + (f"-{ip}" if ip else "")).lower()


def _off_id(vm: str, rid: str, ip: str) -> str:
    from glorfindel.actions import _rid_hash
    return f"{_OFF_PREFIX}{vm}-{_rid_hash(rid)}-{ip}".lower()


def _is_gone(connector, rid: str) -> bool:
    """The VM read gone by its own 404 — a provider that can't tell (None), or a stand-in, never."""
    try:
        return getattr(connector, "vm_gone", lambda _rid: None)(rid) is True
    except Exception:
        return False


GONE = {"verified": None, "method": "vm_gone", "vm_gone": True, "error": "la VM n'existe plus"}


def _pair_not_home(verification: dict) -> bool:
    """The entry's perimeter pair is not read where its entry puts it: on an NSG off the subnet
    (`perimeter_off`), or unread there — its listing, its NICs or their subnet (`pair_unread`,
    `nics_unread`, A0). No put-back of the pair then, in either time (RSM3 and its review)."""
    return bool(verification.get("perimeter_off") or verification.get("pair_unread")
                or verification.get("nics_unread"))


class PairUnread(RuntimeError):
    """A put-back of the pair refused for want of a read of where it would land — not a decision to make:
    deferred, never spent (RSM3's second review)."""


def withheld(b: dict, said: dict, pair: dict | None) -> bool:
    """The entry's perimeter pair to put back, held back this pass for want of a read alone — its NICs, their
    subnet or its listing unread (`pair_unread`, `nics_unread`), or the first time's write refused unread
    (`PairUnread`, `pair["deferred"]`) — never on an NSG off the subnet (`perimeter_off`: a decision). Its
    put-back is then deferred, not spent: spent (`reasserted_at`), a 429 that passed lost it for good — the
    VM's rules put back, the pair never, and the next pass said « une deuxième fois » of a pair never put
    back, the subnet's other VMs reached (RSM3's second review)."""
    return b.get("scoped") is False and not said.get("perimeter_off") and bool(
        said.get("pair_unread") or said.get("nics_unread") or (pair or {}).get("deferred"))


def defer_marks(b: dict, deferred: bool, now: str) -> dict:
    """The entry's fields once its rules are written again: its pair deferred, its put-back not spent — the
    `reasserted_at` it had before kept, `pair_deferred` noted (the first time puts it back once it reads);
    not deferred, the mark goes."""
    return {"reasserted_at": b.get("reasserted_at"), "pair_deferred": now} if deferred else {"pair_deferred": None}


def deferred_said(reason: str, deferred: bool) -> str:
    """The card of a put-back whose pair was held back for want of a read: said so, and that it comes at the
    next pass the read allows — never « ne les réécrit pas de nouveau » of a put-back not spent."""
    if not deferred:
        return reason
    note = ("Sa règle de périmètre n'a pas été reposée, faute de lecture de l'endroit où elle est : elle le sera "
            "à la passe suivante si la lecture le permet, sur son propre NSG seulement.")
    head = " Glorfindel ne les réécrit pas de nouveau : "
    return reason.replace(head, f" {note} Sinon : ", 1) if head in reason else f"{reason} {note}"


def refused_elsewhere(connector, b: dict, scope: str) -> None:
    """A put-back of a perimeter pair never lands on an NSG other than the one its entry records
    (`b["nsg"]`): the provider asked which NSG the VM's subnet carries now (`perimeter_nsg_now`), another
    one, none, or unread — RAISES, said by the card of the put-back (« refusé »). Defence in depth behind
    `_pair_not_home` (the review of RSM3): the write itself reads the subnet's NSG of the moment. A
    provider that can't say (no such method): asked nothing, as before."""
    if scope != "subnet" or b.get("scoped") is not False:
        return
    read = getattr(type(connector), "perimeter_nsg_now", None)
    if read is None:
        return
    recorded = str(b.get("nsg") or "")
    try:
        now = read(connector, b.get("resource_id") or "")
    except Exception as exc:
        raise PairUnread(f"refusé : le NSG du sous-réseau ne se lit pas ({exc}) — rien n'est posé") from exc
    if (now or "").lower() != recorded.lower():
        raise RuntimeError(f"refusé : le sous-réseau porte {now or 'aucun NSG'}, l'entrée enregistre {recorded} — "
                           "Glorfindel ne pose pas le périmètre sur un autre NSG sans décision")


def checked(connector, rid: str, check) -> dict:
    """The check of an isolation or a block, or, its VM gone, what says so (`vm_gone`): asked only where
    the check raised, could not conclude, or read rules gone without reading the VM's NICs
    (`nics_unread`) — where the pass would say « non vérifiée », or write for it: its rules gone, a VM
    deleted was put back, « le reposer a échoué : (ResourceNotFound) ». A check that read the NICs read
    the VM: nothing more is asked (the cost of a pass that puts back is one read of each, as before)."""
    from glorfindel.reassert import _missing
    try:
        verification = check()
    except Exception:
        if _is_gone(connector, rid):
            return dict(GONE)
        raise
    unsure = verification.get("verified") is None or (_missing(verification) and verification.get("nics_unread"))
    if unsure and verification.get("method") != "dry_run" and _is_gone(connector, rid):
        return dict(GONE)
    return verification


def say_vm_gone(vm: str, rid: str, report: list[dict], ip: str = "") -> None:
    """The VM of a recorded isolation (or, with `ip`, block) no longer exists: one card while it is
    recorded — not at every pass, not again once the operator closed it —, closed at the lift
    (`gone_released`). Its card « non vérifiée » closes: this one says why. Nothing is written."""
    from glorfindel import escalations
    from glorfindel.reassert_cards import _history, _record, _resolve, _unverified_id, same_sid
    from glorfindel.vm_command import group_and_name
    sid = _gone_id(vm, rid, ip)
    for e in escalations.pending():
        if same_sid(e.get("signal_id"), _unverified_id(vm, rid, ip)):
            _resolve(e["id"], note="La VM n'existe plus : une carte le dit.")
    last = next((e for e in reversed(_history()) if same_sid(e.get("signal_id"), sid)), None)
    if last is not None and (last.get("status") == "pending" or not last.get("resolution")):
        return                                  # said: pending, or closed by the operator
    target = group_and_name(rid)
    if ip:
        what, lift = (f"le blocage de {ip}", f"glorfindel unblock {ip} {target} --yes")
        tail = "Le lever : `" + lift + "` ; la carte se ferme au déblocage."
    else:
        what, lift = ("son isolation", f"glorfindel release {target} --yes")
        tail = "La lever : `" + lift + "` ; la carte se ferme à la levée."
    reason = (f"{vm} n'existe plus sur Azure (VM supprimée) : {what}, que l'état local de Glorfindel tient "
              f"encore, ne peut plus être vérifié{'' if ip else 'e'} ni remis — rien n'est écrit. {tail}")
    _record(signal_id=sid, resource_id=rid, action=_GONE_ACTION, escalation_type=GONE_TYPE, reason=reason,
            severity="medium", suggested_steps=[f"Vérifier que la suppression de {vm} est voulue.", f"Lever : {lift}"],
            action_params={"ip": ip} if ip else None)
    log.warning("reassert: %s", reason)
    report.append({"kind": "block" if ip else "isolation", "vm": vm, **({"ip": ip} if ip else {}),
                   "outcome": "escalated", "detail": reason})


def gone_released() -> None:
    """A card of a VM gone whose isolation or block is no longer recorded (lifted) closes — not while a
    state can't be read: what it holds is unknown (SEC4b), as the card « non vérifiée »."""
    from glorfindel.actions import active_blocks, active_isolations, unreadable_states
    from glorfindel.reassert_cards import _history, _resolve
    if unreadable_states():
        return
    held = {_gone_id(e["vm_name"], e["resource_id"]) for e in active_isolations() if e.get("resource_id")}
    held |= {_gone_id(e["vm_name"], e["resource_id"], e["ip"]) for e in active_blocks()
             if e.get("resource_id") and e.get("ip")}
    for e in _history():
        sid = (e.get("signal_id") or "").lower()
        if sid.startswith(_GONE_PREFIX) and e.get("status") == "pending" and sid not in held:
            _resolve(e["id"], note="Levé : plus rien d'enregistré pour cette VM.")


def say_perimeter_off(vm: str, rid: str, ip: str, b: dict, v: dict, report: list[dict], ref: str = "") -> None:
    """The entry's perimeter pair read on an NSG that governs none of the VM's NICs (`perimeter_off`): said
    once per NSG on a card of the block — the NSG taken off its subnet, the subnet no longer covered by it,
    the VM's own block (a merged entry) read apart —, never put back (E7). Read on the subnet again (a
    check that concludes, its NICs and its pair read): the card closes, the mark goes."""
    from glorfindel import escalations
    from glorfindel.actions import _update_block_entry
    from glorfindel.reassert_cards import _record, _resolve, same_sid
    from glorfindel.vm_command import group_and_name
    off, mark, sid = v.get("perimeter_off"), b.get("perimeter_off_said"), _off_id(vm, rid, ip)
    if not off:
        if mark and v.get("verified") is not None and not (v.get("nics_unread") or v.get("pair_unread")):
            for e in escalations.pending():
                if same_sid(e.get("signal_id"), sid):
                    _resolve(e["id"], note=f"Le NSG {mark} est de nouveau celui du sous-réseau de {vm}.")
            _update_block_entry(ref or vm, ip, perimeter_off_said=None)
        return
    if (mark or "").lower() == str(off).lower():
        return                                  # said for this NSG: its card, pending or acknowledged
    target = group_and_name(rid)
    merged = bool(b.get("placements"))
    # The cause is not read (the NSG's own subnets are not asked): said as the three it may be, and the
    # subnet's other VMs said uncovered only on the first two (the review of RSM3).
    reason = (f"La règle de périmètre du blocage de {ip} ({vm}) a disparu du sous-réseau de {vm} : son NSG {off} "
              f"ne gouverne plus aucune carte de {vm} — ôté du sous-réseau par le client, remplacé par un autre, ou "
              f"la VM a changé de sous-réseau. Elle ne couvre plus {vm}"
              + (", qui a ses propres règles de blocage, lues à part" if merged else "")
              + ". Ôté ou remplacé, ce NSG ne la fait plus tenir pour les autres VM du sous-réseau ; la VM déplacée, "
              "elle les couvre encore. Glorfindel ne la repose pas, ni sur ce NSG ni sur un autre sans décision. "
              f"Remettre le NSG sur le sous-réseau, ou re-bloquer : `glorfindel block {ip} {target} --scope subnet "
              "--yes` (sur le NSG que porte le sous-réseau aujourd'hui, s'il en a un), ou `--scope vm` pour la VM "
              f"seule ; `glorfindel unblock {ip} {target} --yes` si c'est voulu.")
    # Its own type: a drift card of the same block (`verification_failed`, its VM rules gone too) and this
    # one are two cards — one type, the store folded one into the other, its words lost (`escalations.record`).
    # Closed in the write of the new one, never before it (L1A).
    replaced = {e["id"]: "Remplacée : une nouvelle carte la suit." for e in escalations.pending()
                if same_sid(e.get("signal_id"), sid)}
    _record(signal_id=sid, resource_id=rid, action="block_suspicious_ip", escalation_type=OFF_TYPE,
            reason=reason, severity="high", action_params={"ip": ip}, replaces=replaced,
            suggested_steps=[f"Lire le sous-réseau de {vm} : qui a ôté {off} (journal d'activité), et pourquoi.",
                             f"Remettre {off} sur le sous-réseau, ou re-bloquer : glorfindel block {ip} {target} "
                             "--scope subnet --yes (ou --scope vm).",
                             f"Ou lever le blocage : glorfindel unblock {ip} {target} --yes."])
    _update_block_entry(ref or vm, ip, perimeter_off_said=str(off).lower())     # after its card (L1F)
    report.append({"kind": "block", "vm": vm, "ip": ip, "outcome": "escalated", "detail": reason})
