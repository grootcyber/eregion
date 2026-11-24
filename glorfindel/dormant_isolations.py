"""A possible older isolation of Glorfindel, said — never taken off (ORPH2, #1113).

An older version isolated a VM with a deny any/any under two fixed names
(`glorfindel-isolation-deny-all`, `-out`) on its NIC's own NSG. Its state lost, the NIC taken off
that NSG since (our quarantine, its tags lost, the card left bare), the pair stays on an NSG that
governs no NIC and no subnet: the release says `released` (right: the VM is cut by nothing), the
orphan sweep finds nothing (no NIC hash in the name), the reset neither — and once someone puts
that NSG back on a NIC, the VM is cut. The name alone never proves whose the rules are (SEC-H:
another tool, another Glorfindel host), so nothing here writes: one card per NSG, which says the
NSG, the rules, why nothing is taken off and the command to take them off by hand, after a check
(Jonathan's decision, 23/11). The same version's names suffixed by a VM
(`glorfindel-isolation-deny-all-<vm>`, `-<vm>-out`: its deny scoped to the VM's address on a
subnet's NSG) left on an NSG that governs nothing are said the same way, on the same card, which
names the VM they named — a hint for the operator, never a proof (ORPH2b, #1126, 24/11).

Said once (`dormant_alerts.json`, beside the orphans' file): the same NSG with the same rules and
the same NICs and subnets governed keeps its card, pending or acknowledged. The card closes when the
rules are no longer on the NSG (taken off, or the NSG deleted — proven by a read by its id, never by a
listing that leaves it out); it is closed before the mark is forgotten, so a refused closure is tried
again. An NSG that can't be read again keeps its card, and the pass says so. It does NOT close when the
NSG governs something again: that is when the rules cut — the card is replaced by one that says what
the NSG governs now, and again each time that changes, once per state. A pair on an NSG that governs something, never
said dormant, stays to the paths that have always judged it (the release, the reset of its VM).
Run by the orphan sweep (orphans.py) every pass of the watch, or by the posture check when the
reassertion doesn't run.
"""
from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)

TYPE = "dormant_isolation"
ACTION = "review_dormant_isolation"


def _alerts_path():
    """Beside the isolation states (~/.glorfindel/dormant_alerts.json): the NSGs said, each with
    its card, the rules and the NICs and subnets it governed when said."""
    from glorfindel import actions
    return actions._ISOLATION_STATE_DIR.parent / "dormant_alerts.json"


def _load_alerts() -> dict:
    try:
        data = json.loads(_alerts_path().read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict) and isinstance(v.get("card"), str)}


def _save_alerts(alerts: dict) -> None:
    from glorfindel import actions
    try:
        actions._atomic_write_text(_alerts_path(), json.dumps(alerts, sort_keys=True))
    except Exception as exc:                  # said again at the next pass, merged in its card: noisier
        log.warning("dormant isolations: alerts not recorded (%s)", exc)


def _short(ref: str) -> str:
    return (ref or "").rstrip("/").rsplit("/", 1)[-1]


def _rules_text(e: dict) -> str:
    return ", ".join(f"{r['name']} ({r.get('direction') or '?'}, priorité {r.get('priority')}"
                     + (f", VM {r['vm']}" if r.get("vm") else "") + ")" for r in e["rules"])


def _whose(e: dict) -> str:
    """What the names say of whose the rules were: the fixed names, the VMs the suffixed ones
    named (ORPH2b) — a hint, never a proof (SEC-H)."""
    vms = sorted({r["vm"] for r in e["rules"] if r.get("vm")}, key=str.lower)
    names = (["les noms fixes du refus total"] if any(not r.get("vm") for r in e["rules"]) else []) + (
        [f"les noms suffixés par la VM qu'ils isolaient ({', '.join(vms)})"] if vms else [])
    of = f" de {', '.join(vms)}" if vms else ""
    return (f"{' et '.join(names)} d'une ancienne version de Glorfindel (avant les placements), "
            f"peut-être une ancienne isolation{of}")


def _governs(e: dict) -> list[str]:
    return [f"la carte {_short(n)}" for n in e["nics"]] + [f"le sous-réseau {_short(s)}" for s in e["subnets"]]


def _card(e: dict) -> tuple[str, list[str]]:
    """The reason and the steps of the card of one NSG."""
    from glorfindel.actions import _parse_nsg_resource_id
    rg, name = _parse_nsg_resource_id(e["nsg_id"])
    governs = _governs(e)
    now = (f"Ce NSG gouverne de nouveau {', '.join(governs)} : ces refus les coupent peut-être, sans "
           "qu'aucune isolation de Glorfindel ne le tienne aujourd'hui."
           if governs else
           "Ce NSG ne gouverne aucune carte ni aucun sous-réseau : ils ne coupent rien aujourd'hui, mais remis "
           "sur une carte ou un sous-réseau (un redéploiement, à la main), ils coupent ce qu'ils visent : le "
           "refus total, tout ce que le NSG gouverne ; un nom suffixé, l'adresse qu'il vise.")
    reason = (f"NSG {name} ({rg}) : {_rules_text(e)} — {_whose(e)}. {now} Glorfindel "
              "ne les retire pas, ni à ce passage, ni par une levée, ni par un reset : le nom seul ne prouve "
              "pas à qui elles sont (un autre outil, un autre hôte Glorfindel — SEC-H). Vérifier, puis les "
              "retirer à la main.")
    steps = [f"Vérifier : az network nsg rule show -g {rg} --nsg-name {name} -n {r['name']}" for r in e["rules"]]
    steps += [f"Si elles sont à vous : az network nsg rule delete -g {rg} --nsg-name {name} -n {r['name']}"
              for r in e["rules"]]
    return reason, steps


def _signature(e: dict) -> dict:
    """What the card says, compared from one pass to the next: the rules, and every NIC and subnet
    the NSG governs — a card that names NIC A while the NSG went to NIC B, or took a subnet too,
    says what is no longer so (the review of ORPH2)."""
    return {"rules": sorted(r["name"].lower() for r in e["rules"]),
            "governed": sorted(i.lower() for i in list(e["nics"]) + list(e["subnets"]))}


def _replaced(said: dict, sig: dict, k: str) -> str:
    """Why a card of an NSG is replaced: its older-name denies changed, or what it governs."""
    if said.get("rules") != sig["rules"]:
        return f"Remplacée : les refus d'une ancienne version sur {_short(k)} ont changé."
    if not sig["governed"]:
        return f"Remplacée : {_short(k)} ne gouverne plus aucune carte ni aucun sous-réseau."
    if not said.get("governed"):
        return f"Remplacée : {_short(k)} gouverne de nouveau une carte ou un sous-réseau."
    return f"Remplacée : {_short(k)} gouverne désormais {', '.join(_short(g) for g in sig['governed'])}."


def say_dormant_isolations(connector, report: list | None = None, nsgs=None) -> list[dict]:
    """One pass: the NSGs holding an older version's denies (fixed names, or suffixed by a VM)
    and governing nothing, said. `nsgs`: the NSGs the watch's pass already listed. Never raises,
    never writes on Azure."""
    report = report if report is not None else []
    find = getattr(connector, "find_dormant_isolations", None)
    if find is None or getattr(connector, "dry_run", False) is True:
        return report
    alerts = _load_alerts()
    try:
        found = find(nsgs=nsgs, said=sorted(alerts))
    except Exception as exc:                  # unread: every card stays as it is
        log.warning("dormant isolations: not checked (%s)", exc)
        return report
    if not isinstance(found, list):
        return report
    before = json.dumps(alerts, sort_keys=True)
    try:
        _say(found, alerts, report)
    except Exception as exc:
        log.warning("dormant isolations: pass failed (%s)", exc)
    if json.dumps(alerts, sort_keys=True) != before:
        _save_alerts(alerts)
    return report


def _say(found: list[dict], alerts: dict, report: list) -> None:
    from glorfindel import escalations
    pending = {e.get("id") for e in escalations.pending()}
    for e in found:
        k = str(e.get("nsg_id") or "").rstrip("/").lower()
        if not k:
            continue
        if e.get("unread"):                       # not read: its card stays as it is, and that is said
            log.warning("dormant isolations: %s not read (%s): its card stays", _short(k), e["unread"])
            report.append({"kind": TYPE, "vm": _short(k), "outcome": "unread", "detail": (
                f"NSG {_short(k)} : sa carte d'ancienne isolation reste telle quelle — le NSG n'a pas pu être "
                f"relu ({e['unread']}).")})
            continue
        said = alerts.get(k)
        if e.get("gone") or not e.get("rules"):
            if said is not None:
                if said["card"] in pending:       # closed first: refused, the mark stays, the next pass retries
                    escalations.resolve(said["card"], note=(
                        f"Le NSG {_short(k)} n'existe plus." if e.get("gone") else
                        f"Les refus d'une ancienne version ne sont plus sur {_short(k)} (retirés)."))
                del alerts[k]
            continue
        sig = _signature(e)
        if said is not None and {"rules": said.get("rules"), "governed": said.get("governed")} == sig:
            continue                              # said once: pending, or acknowledged
        if said is None and sig["governed"]:
            continue                              # never said dormant: the paths of its VM judge it
        reason, steps = _card(e)
        takes = ({said["card"]: _replaced(said, sig, k)} if said is not None and said["card"] in pending else None)
        card = escalations.record(
            signal_id=f"dormant-{e['nsg_id']}",
            resource_id=e["nsg_id"],
            action=ACTION,
            escalation_type=TYPE,
            reason=reason,
            suggested_steps=steps,
            severity="high" if sig["governed"] else "medium",
            replaces=takes,
        )
        alerts[k] = {"card": card, **sig}
        report.append({"kind": TYPE, "vm": _short(k), "outcome": "escalated", "detail": reason})
