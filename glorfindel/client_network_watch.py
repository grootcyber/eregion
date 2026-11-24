"""What the watch does and says of the client's network (SEC2b, #1089): the read at the discovery's
cadence, its cards, and its lines at the start.

- **The read** (`refresh`, from glorfindel/discovery.py every `client_network.READ_INTERVAL_S`): the
  provider's listings written as the list known (glorfindel/client_network.py), or the failure noted
  over the list kept.
- **A list that can't be trusted** (decision 4): one card on the console and on Discord
  (`client_network.CARD_TYPE`, filed on `client-network`), folded while it lasts, closed once the list
  is whole and fresh again; said in the watch's log at each read.
- **A named network's object that changes** (decision 9): what it designates now and before, on a card
  of its own (`client_network.CHANGE_TYPE`, filed on `client-network/<name>`) — a new change replaces
  the card of the one before —, and in the log. A first resolution is no change: said in the log.
- **At the start** (`start_lines`): each name, what it holds, where it serves; the names that serve
  nowhere; the overlaps between the layers (decision 8: said, never refused); the list's state.
"""
from __future__ import annotations

import ipaddress
import logging
from datetime import datetime, timezone

from glorfindel import client_network as cn
from glorfindel import lateral
from glorfindel.response.policy import CLIENT, EXPECTED, EXPOSED

logger = logging.getLogger("glorfindel.client_network")

_WHILE = ("Tant qu'elle ne l'est pas, les blocages hors Internet restent refusés — plages privées livrées, "
          "never_block et ce qu'une lecture plus ancienne listait —, mais une adresse ni privée ni connue "
          "du client reste bloquable : une adresse d'un VNet hors des plages privées, non lue, peut l'être.")


def refresh(reader, cfg, now: datetime | None = None) -> cn.Snapshot:
    """One read of the client's network: written, its changes and its state said."""
    from glorfindel.response.policy import _first_line
    now = now or datetime.now(timezone.utc)
    before = cn.load(now)
    try:
        read = reader()
    except Exception as exc:
        why = f"{type(exc).__name__}: {_first_line(exc)}"
        snap = _written(lambda: cn.note_failure(why, now), why)
    else:
        snap = _written(lambda: cn.save(read, now, cfg.networks), "")
    if snap.state != "failed":
        _say_changes(before.named, snap.named, cfg)
    _say_state(snap, cfg)
    return snap


def _written(write, why: str) -> cn.Snapshot:
    """The store written — or, when it can't be (a directory docker made as root, a disk full), a
    list failed in memory: a list that can't be written is always a card, never a line of the log alone
    (the review of SEC2b). The store on disk stays as it was; the guard reads it as it is."""
    from glorfindel.response.policy import _first_line
    try:
        snap = write()
    except Exception as exc:
        said = (f"liste non écrite ({cn._STORE} : {type(exc).__name__}: {_first_line(exc)})"
                + (f" ; lecture en échec : {why}" if why else ""))
        cn.unwritten(said)          # SEC2c, reprise 1: the guard of this process reads it back
        return cn.Snapshot(state="failed", error=said)
    cn.unwritten("")
    return snap


def degraded(cfg, snap: cn.Snapshot) -> str:
    """Why the list can't be trusted — its own state, or a named network unresolved — "" when it can."""
    from glorfindel.response.policy import address_layers
    return " ; ".join(address_layers(cfg, snap)[1])


# SEC2c, reprise 6: what the log said of a whole read with no VNet — said once per change, never at each
# read (every 10 min).
_SAID: dict[str, str] = {}


def _say_state(snap: cn.Snapshot, cfg) -> None:
    from glorfindel import escalations
    why = degraded(cfg, snap)
    if not why:
        logger.info("réseau du client lu : %d VNet, %d adresse(s) ou plage(s) publique(s)",
                    len(snap.vnets), len(snap.public_ips) + len(snap.prefixes))
        empty = _empty_read(snap)
        if empty and _SAID.get("empty") != empty:
            logger.warning("réseau du client : %s", empty)
        _SAID["empty"] = empty
        if any(e.get("resource_id") == cn.CARD_RESOURCE and e.get("escalation_type") == cn.CARD_TYPE
               for e in escalations.pending()):
            escalations.resolve_by_resource(cn.CARD_RESOURCE, "none")
        return
    logger.warning("réseau du client : %s", why)
    escalations.record(signal_id="client-network-unreadable", resource_id=cn.CARD_RESOURCE, action="none",
                       escalation_type=cn.CARD_TYPE, severity="high", source="real",
                       reason=f"Liste du réseau du client non fiable : {why}. {_WHILE}",
                       suggested_steps=["Vérifier les droits de lecture de la watch (Reader sur l'abonnement)",
                                        "Corriger le nom du réseau nommé, s'il en manque un",
                                        "La carte se ferme seule à la prochaine lecture entière"])


def _say_changes(before: dict, after: dict, cfg) -> None:
    """Each named network whose object designates other ranges than at the read before."""
    from glorfindel import escalations
    for name, now_ranges in sorted(after.items()):
        if name not in before:
            logger.info("réseau nommé « %s » : %s", name, ", ".join(now_ranges or []) or "introuvable")
            continue
        if before.get(name) == now_ranges:
            continue
        net = cfg.networks.get(name)
        where = ", ".join(cfg.network_uses.get(name) or []) or "aucune clé (réseau du client seul)"
        said = (f"Le réseau nommé « {name} » ({net.written() if net else '?'}) désigne maintenant "
                f"{', '.join(now_ranges or []) or 'rien (introuvable)'} — avant : "
                f"{', '.join(before.get(name) or []) or 'rien (introuvable)'}. Où il sert : {where}.")
        logger.warning("%s", said)
        rid = f"{cn.CARD_RESOURCE}/{name}"
        replaced = {e["id"]: "remplacée : ce que le nom désigne a encore changé" for e in escalations.pending()
                    if e.get("resource_id") == rid and e.get("escalation_type") == cn.CHANGE_TYPE}
        escalations.record(signal_id=f"network-changed-{name}", resource_id=rid, action="none",
                           escalation_type=cn.CHANGE_TYPE, severity="medium", source="real", reason=said,
                           replaces=replaced or None)


def _overlaps(entries) -> list[str]:
    """Each pair of ranges of two different layers, or of two named networks, that overlap."""
    out: list[str] = []
    nets = []
    for cidr, layer, source in entries:
        try:
            nets.append((ipaddress.ip_network(cidr, strict=False), layer, source))
        except ValueError:
            continue
    def name(source: str) -> str:
        return source.rsplit("réseau nommé", 1)[-1] if "réseau nommé" in source else ""
    for i, (a, la, sa) in enumerate(nets):
        for b, lb, sb in nets[i + 1:]:
            if name(sa) and name(sa) == name(sb):
                continue            # one name in two layers (never_block, and the client's network)
            if {la, lb} in ({EXPOSED, CLIENT}, {EXPECTED, CLIENT}) and not (name(sa) and name(sb)):
                continue            # SEC2c, SEC2d: a zone, an origin inside the client's network — said on its own
            named = bool(name(sa) and name(sb))
            if (la != lb or named) and a.version == b.version and a.overlaps(b):
                out.append(f"{a} ({sa}) chevauche {b} ({sb}) — {sa if la != lb else 'le plus prudent'} l'emporte")
    return out


def _empty_read(snap: cn.Snapshot) -> str:
    """A whole read that lists no VNet while the registry knows Azure VMs: perhaps the Reader role does
    not see their groups — Azure leaves them out of a listing without a word. Said, never refused."""
    if snap.state not in ("fresh", "stale") or snap.vnets:
        return ""
    try:
        from glorfindel.discovery import AssetRegistry
        vms = [a for a in AssetRegistry().all() if "/providers/microsoft.compute/" in a.resource_id.lower()]
    except Exception:
        return ""
    return (f"lecture du réseau du client entière mais sans aucun VNet, alors que le registre connaît "
            f"{len(vms)} VM Azure : le rôle Reader de la watch voit-il leurs groupes de ressources ?"
            if vms else "")


_DECISION_6 = ("la règle livrée (ssh-brute-force) filtre encore les plages privées, dans ce temps 1 : le blocage "
               "seul n'y joue qu'avec le temps 2 (SEC2d, 0.7) — d'ici là, la zone sert aux gestes humains "
               "(une approbation, la CLI) et aux règles du client")


def _exposed_lines(cfg, snap: cn.Snapshot) -> list[tuple[str, str]]:
    """SEC2c: each range of the exposed zone said loud (`strong`) — what it allows, its deadline, what it
    holds that is no single host —, the note of decision 6 for a range in the private ranges, a named
    object's range left out (too wide, the platform's), and the zone off while the list can't be trusted."""
    from glorfindel.config_zones import usable
    from glorfindel.exposed_zone import EXPIRY_S, contents
    from glorfindel.response.policy import _PLATFORM_SHIPPED, NEVER_BLOCK_SHIPPED, address_layers
    entries, degraded_list = address_layers(cfg, snap)
    zones = [(c, s) for c, layer, s in entries if layer == EXPOSED]
    private = [ipaddress.ip_network(p) for p in NEVER_BLOCK_SHIPPED if p not in _PLATFORM_SHIPPED]   # the private ranges
    out: list[tuple[str, str]] = []
    for cidr, source in zones:
        net = ipaddress.ip_network(cidr, strict=False)
        out.append(("strong", f"Zone exposée {cidr} ({source}) — sert : network_zones.exposed : le blocage "
                              "seul d'UN hôte y est possible, le mode de la VM attaquée le permettant (human_only : "
                              f"une carte) ; levé seul au bout de {EXPIRY_S / 3600:.0f} h, ou dès que l'adresse passe "
                              "à une autre VM ; jamais une passerelle NAT, un frontal d'équilibreur, une appliance "
                              "ni une IP publique partagée, ni une adresse qu'aucune carte connue ne tient"))
        if held := contents(cidr, snap):
            out.append(("note", f"zone exposée {cidr} : gardé(s) protégé(s), pas un seul hôte — {' ; '.join(held)}"))
        if not lateral.on() and any(p.version == net.version and net.overlaps(p) for p in private):
            out.append(("note", f"zone exposée {cidr} en plage privée : {_DECISION_6}"))
    for name in cfg.exposed_names:
        net = cfg.networks.get(name)
        for cidr in (snap.resolve(net)[0] if net is not None and net.is_object else []):
            if why := usable(cidr):
                out.append(("note", f"zone exposée, réseau nommé « {name} » : {cidr} écartée — {why} ; elle reste "
                                    "le réseau du client, jamais bloquée"))
    if (zones or cfg.exposed_names) and degraded_list:
        out.append(("loud", "Zone exposée sans effet tant que la liste du réseau du client n'est pas fiable : "
                            "ses adresses restent protégées comme le reste du réseau du client"))
    return out


def start_lines(cfg, snap: cn.Snapshot | None = None) -> list[tuple[str, str]]:
    """(level, text) the watch prints at its start: `info`, `note` (said, never refused) or `loud`."""
    from glorfindel.response.policy import address_layers
    snap = cn.load() if snap is None else snap
    lines: list[tuple[str, str]] = []
    for name, net in cfg.networks.items():
        held = (", ".join(snap.resolve(net)[0]) or snap.resolve(net)[1]) if net.is_object else ""
        where = ", ".join(cfg.network_uses.get(name) or []) or "aucune clé"
        lines.append(("info", f"réseau nommé « {name} » : {net.written()}" + (f" → {held}" if held else "")
                      + f" — sert : {where}"))
    lines += [("note", n) for n in cfg.notes]
    lines += _exposed_lines(cfg, snap)
    lines += lateral.start_lines(cfg, snap)         # SEC2d: the switch, the expected origins
    entries, _ = address_layers(cfg, snap)
    lines += [("note", f"chevauchement : {o}") for o in _overlaps(entries) if "plage privée livrée" not in o
              or "never_block" in o]
    why = degraded(cfg, snap)
    if empty := _empty_read(snap):
        lines.append(("note", empty))
    if why:
        lines.append(("loud", f"Réseau du client non fiable : {why}. {_WHILE}"))
    else:
        lines.append(("info", f"Réseau du client : lu à {snap.read_at[:16]} — {len(snap.vnets)} VNet, "
                              f"{len(snap.public_ips) + len(snap.prefixes)} adresse(s) ou plage(s) publique(s) ; "
                              "jamais bloqué"))
    return lines
