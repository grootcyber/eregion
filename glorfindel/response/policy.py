"""Which actions Glorfindel runs alone, the errors an action raises, and the verdicts
and checks shared by the agent, the CLI and the War Room (moved from actions.py, A1).
"""
from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console


# Actions Glorfindel peut exécuter seul (réversibles)
AUTONOMOUS_ACTIONS = {
    "isolate_vm",
    "release_isolation",  # inverse of isolate_vm — safe to reverse autonomously
    # revoke_temp_access: removed 2026-10-06 — announced to the model, never implemented
    # (it ended as a no_op "executed", then notified). Proposed → escalated as unknown.
    "snapshot",           # forensic snapshot of current (compromised) state
    "block_suspicious_ip",
}

# The verbs of the response to a stolen identity (IR1, docs/design/reponse-identite.md §3.3): a
# closed list. Never autonomous, whatever the mode; always a human's approval, verb by verb, on
# the plan of an `identity_change` card (IR1a) — and never a decision's: an identity detection
# is decided by the code, `action: ""` (agent._identity_decision), and the route after `decide`
# never sends one to an action. They are the identity executor's (IR1c), which does not exist yet.
IDENTITY_ACTIONS = frozenset({
    "entra_remove_credential",
    "entra_restore_credential",
    "entra_disable_principal",
    "entra_enable_principal",
    "entra_revoke_sessions",
    "entra_disable_user",       # 05/11 (Q2): a test user of the bench's administrative unit
    "entra_enable_user",
})

# Actions nécessitant validation humaine (destructives ou à impact large)
HUMAN_APPROVAL_REQUIRED = {
    "delete_resource",
    "modify_network_rule",
    "escalate_permissions",
    "wipe_storage",
    "restore_from_backup",  # replaces disk content — irreversible without another backup
} | IDENTITY_ACTIONS

# What the model reads as « requires approval » (agent._SYSTEM_PROMPT and the decision tool):
# the gated actions a decision may name — the identity verbs left out, never a decision's. The
# prompt reads what it read before IR1a (tests/unit/test_identity_plan.py).
MODEL_GATED_ACTIONS = frozenset(HUMAN_APPROVAL_REQUIRED - IDENTITY_ACTIONS)


class PartialActionError(RuntimeError):
    """An NSG action landed on some NICs, then failed on the next one.

    The rules already in place are KEPT (partial containment beats none) and recorded
    in state, so release / unblock / reset can remove them later. Before this, a failure
    on NIC n left the rules of NICs 1..n-1 on Azure with no state at all: invisible to
    `glorfindel list`, and out of reach of `reset`.

    Carries the original error's status_code so execute_action still tells an IAM gap
    (403 → write_blocked) from any other failure (action_failed).
    """

    def __init__(self, message: str, *, cause: BaseException, covered: list[str], failed_nic: str):
        super().__init__(message)
        self.cause = cause
        self.status_code = getattr(cause, "status_code", None)
        self.covered = covered
        self.failed_nic = failed_nic


# An Azure error names the lock (ScopeLocked) or the policy at the END of its first
# line: cut at 200 characters, the operator lost what to remove (real run, 2026-10-05).
_ERR_MAX = 600


# DRN1 (#677): what a card says of the session drain — still running on Azure, refused, sessions
# left open, or never ended (still running at its deadline, or no longer followed).
DRAIN_CASES = {
    "pending": "coupure en attente",
    "refused": "coupure refusée",
    "open": "sessions restées ouvertes",
    "never": "coupure jamais aboutie",
}
_CUT_BY_HAND = ("Couper à la main : az vm run-command invoke --command-id RunShellScript "
                "--scripts 'ss -K state established'")


def drain_case(drain: dict | None) -> str:
    """The case of a drain's outcome (DRAIN_CASES), "" when it cut the sessions (or did not run)."""
    drain = drain if isinstance(drain, dict) else {}
    status = drain.get("status")
    if status == "pending":
        return "pending"
    if drain.get("never"):
        return "never"
    if status not in ("failed", "partial", "unsupported"):
        return ""
    return "refused" if drain.get("refused") else "open"


def drain_said(drain: dict | None) -> str:
    """What a card says of a drain that did not cut the sessions, its case first; "" otherwise."""
    drain = drain if isinstance(drain, dict) else {}
    case = drain_case(drain)
    if case in ("", "pending"):
        return ""
    if drain.get("status") == "unsupported":
        return (f"{DRAIN_CASES[case]} : sessions déjà ouvertes non coupées ("
                + (drain.get("note") or "OS non pris en charge")
                + ") : un attaquant connecté garde la main — les couper à la main")
    if case == "never":       # not read: perhaps cut, perhaps not — never said either way
        return (f"{DRAIN_CASES[case]} : règles posées, mais les sessions déjà ouvertes n'ont peut-être pas "
                f"été coupées ({drain.get('error', drain.get('status'))}) — un attaquant connecté garde "
                f"peut-être la main. {_CUT_BY_HAND}")
    return (f"{DRAIN_CASES[case]} : règles posées, mais les sessions déjà ouvertes n'ont pas été "
            f"coupées ({drain.get('error', drain.get('status'))}) — un attaquant connecté garde la "
            f"main. {_CUT_BY_HAND}")


def drain_followed() -> bool:
    """A pending drain is read again: the watch's reassertion pass runs (`posture._reassertion_on`:
    GLORFINDEL_REASSERT_INTERVAL_S > 0). Off, nothing reads it again (DRN1 review)."""
    from glorfindel.posture import _reassertion_on
    return _reassertion_on()


# The cycle's word for a drain pending that nothing will read again (the reassertion off).
DRAIN_UNFOLLOWED = ("coupure en attente, non suivie : la Run Command tourne encore sur Azure après sa "
                    "première attente, et la réaffirmation est coupée (GLORFINDEL_REASSERT_INTERVAL_S) : "
                    "son statut ne sera pas relu — un attaquant connecté garde peut-être la main. "
                    + _CUT_BY_HAND)
# CMD1: the same, for a gesture of the CLI on a host where no watch lives — none here reads it again.
DRAIN_UNWATCHED = ("coupure en attente, non suivie : la Run Command tourne encore sur Azure après sa "
                   "première attente, et aucune watch vivante sur cet hôte ne relira son statut — un "
                   "attaquant connecté garde peut-être la main. " + _CUT_BY_HAND)


def isolation_verdict(verification: dict, outcome: dict, followed: bool | None = None) -> dict:
    """verify_isolation's result, downgraded when the drain left sessions open.

    The rules only stop NEW connections (measured 2026-10-05): rules in place with an
    attacker's session still open is not a contained VM. Shared by the agent's
    verify_action and the War Room's approve route.

    A drain still running on Azure past its first wait (DRN1: 302 s under the quarantine) keeps
    the rules' verdict, and says it is pending (`drain_case`): its status is read again by the
    reassertion's pass (glorfindel/drain_watch.py), which closes its card once the cut ends, or
    says on a card that it was refused, left sessions open, or never ended. The reassertion off,
    nothing reads it again: not verified (« coupure en attente, non suivie »). ``followed`` False
    (CMD1: the CLI on a host where no watch lives): nothing here reads it again either, whatever the
    reassertion's setting — not verified, said so."""
    drain = (outcome or {}).get("drain") or {}
    case = drain_case(drain)
    if verification.get("verified") is True and case == "pending":
        if followed is False:
            return {**verification, "verified": False, "drain": drain, "drain_case": case,
                    "drain_followed": False, "error": DRAIN_UNWATCHED}
        if not drain_followed():
            return {**verification, "verified": False, "drain": drain, "drain_case": case,
                    "drain_followed": False, "error": DRAIN_UNFOLLOWED}
        return {**verification, "drain": drain, "drain_case": case}
    if verification.get("verified") is True and case:
        return {**verification, "verified": False, "drain": drain, "drain_case": case,
                "error": drain_said(drain)}
    return verification


def _first_line(exc: BaseException) -> str:
    """First line of an exception message (Azure SDK errors repeat it on later lines)."""
    text = str(exc).strip()
    return text.splitlines()[0].strip() if text else type(exc).__name__


def _as_address(ip: str):
    """`ip` as an address, None when it is not one."""
    import ipaddress
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return None
    # An IPv4 address written as IPv6 (::ffff:a.b.c.d) is that IPv4 address.
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return addr


def single_host_ip(ip: str) -> str:
    """The address itself when `ip` is ONE host address, else ValueError. An approval
    passed `ip=*&scope=subnet` straight to a subnet-wide deny (fourth review, Q4). An IPv4
    written as IPv6 (`::ffff:a.b.c.d`) is judged, and returned, as that IPv4 (SEC2b):
    `::ffff:169.254.169.254` is the link-local address it writes."""
    addr = _as_address(ip)
    if addr is None:
        raise ValueError(f"adresse IP invalide : {ip!r} (une seule adresse attendue, pas de plage ni de tag)")
    if addr.is_unspecified or addr.is_loopback or addr.is_multicast or addr.is_link_local:
        raise ValueError(f"adresse IP refusée : {ip} (non routable ou réservée)")
    return str(addr)


# Addresses Glorfindel never blocks, whatever the rule or the model says (SEC2): Azure's
# platform (DNS and the host agent at 168.63.129.16, IMDS at 169.254.169.254), the private
# ranges (RFC 1918, the shared space of carrier NAT, IPv6's unique local) and the loopback.
# A private address is never blocked: lateral movement is answered by isolating the source
# VM. glorfindel-config.yaml's `never_block` adds the deployment's own (a scanner, a
# monitoring probe, the office).
NEVER_BLOCK_SHIPPED = (
    "168.63.129.16/32", "169.254.169.254/32",
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7",
    "127.0.0.0/8", "::1/128",
)


class ProtectedAddressError(ValueError):
    """The address is protected — the platform, never_block, the client's network: no block,
    ever — a human looks."""


def protected_by(ip: str) -> str:
    """The protected entry that holds `ip` ("" when none): the first layer's that holds it
    (`protection`)."""
    addr = _as_address(ip)
    return protection(str(addr)).entry if addr is not None else ""


# SEC2b (#1089): the layers an address is judged by, in their order (decision 8 of 23/11) — the most
# prudent declaration wins, and an address is said held by the first layer that holds it; an overlap
# is said at the watch's start (glorfindel/client_network_watch.py), never refused:
#   1. PLATFORM — Azure's platform (DNS and the host agent, IMDS) and the loopback: always protected;
#   2. NEVER_BLOCK — glorfindel-config.yaml's `never_block`, its ranges and its named networks;
#   3. EXPECTED (SEC2d, #1147) — the expected origins (`network_zones.expected_origins`): never blocked, a
#      detection from one set aside, said and counted (glorfindel/lateral.py) — only while the switch of the
#      lateral movement is on (`GLORFINDEL_LATERAL`): off, the key is read and checked, this layer is empty;
#   4. EXPOSED (SEC2c, #1107) — the exposed zone (`network_zones.exposed`): a block of ONE host possible
#      again (glorfindel/exposed_zone.py, `judge`: else held as the client's network), the attacked VM's
#      mode permitting (decide's gate of the mode, as for the Internet), expiring at 24 h — never over 1
#      or 2, nor over 3; on Azure only (`exposed_applies`: on AWS no discovery tells one host);
#   5. CLIENT — the client's network: the shipped private ranges, the named networks, the VNets and
#      public IPs the discovery read (glorfindel/client_network.py): never blocked;
#   6. the Internet: blockable.
PLATFORM, NEVER_BLOCK, EXPOSED, CLIENT = "platform", "never_block", "exposed_zone", "client_network"
EXPECTED = "expected_origin"
_PLATFORM_SHIPPED = frozenset({"168.63.129.16/32", "169.254.169.254/32", "127.0.0.0/8", "::1/128"})


@dataclass(frozen=True)
class Protection:
    """What holds an address: its range (`entry`, "" when nothing does), its layer, what the range is
    (`source`) — and why the client's list can't be trusted (`degraded`, "" when it can)."""
    entry: str = ""
    layer: str = ""
    source: str = ""
    degraded: str = ""


def address_layers(cfg=None, snap=None) -> tuple[list[tuple[str, str, str]], list[str]]:
    """([(range, layer, source)] in the order of the layers, [why the client's list can't be
    trusted]). `cfg`: glorfindel-config.yaml (read, raising when it can't be: fail closed); `snap`: the
    client's network (glorfindel/client_network.py, never raising)."""
    from glorfindel.client_network import load
    from glorfindel.config import load_glorfindel_config
    cfg = load_glorfindel_config() if cfg is None else cfg
    snap = load() if snap is None else snap
    degraded = [snap.degraded()] if snap.degraded() else []
    ranges: dict[str, list[str]] = {}
    for n in cfg.networks.values():
        got, why = snap.resolve(n) if n.is_object else (list(n.cidrs), "")
        if why:     # decision 9: a name the discovery does not find counts as a list unread (4)
            degraded.append(f"réseau nommé « {n.name} » ({n.written()}) : {why}")
        ranges[n.name] = got
    by_name = {c: n for n in cfg.never_block_names for c in ranges.get(n, [])}
    out = [(c, PLATFORM, "plateforme Azure ou bouclage, liste never_block livrée")
           for c in NEVER_BLOCK_SHIPPED if c in _PLATFORM_SHIPPED]
    out += [(c, NEVER_BLOCK, f"never_block, réseau nommé « {by_name[c]} »" if c in by_name else "never_block")
            for c in list(cfg.never_block) + [c for c in by_name if c not in cfg.never_block]]
    out += _expected_layer(cfg, ranges, degraded)
    out += _exposed_layer(cfg, ranges)
    out += [(c, CLIENT, "plage privée livrée") for c in NEVER_BLOCK_SHIPPED if c not in _PLATFORM_SHIPPED]
    out += [(c, CLIENT, f"réseau nommé « {n} »") for n, cs in ranges.items() for c in cs]
    out += [(c, CLIENT, source) for c, source in snap.entries()]
    return out, degraded


def _expected_layer(cfg, ranges: dict, degraded: list | None = None) -> list[tuple[str, str, str]]:
    """SEC2d: the expected origins' ranges, a named network's said by its name — while the switch of the lateral
    movement is on (glorfindel/lateral.py), else none. Always the client's network, never the Internet (Jonathan,
    24/11): a range written is private (`config_zones.not_private`, refused at the read otherwise); a named
    object's range the discovery read (a VNet, a subnet, perhaps outside the private ranges) only while the list
    is trusted — a list that can't be (decision 4) keeps its private ranges alone: nothing public set aside on a
    read nobody trusts. Wider than the ceiling, or touching the platform: left out (`usable`), as for the zone."""
    from glorfindel import lateral
    if not lateral.on():
        return []
    from glorfindel.config_zones import not_private, usable
    named = {c: n for n in getattr(cfg, "expected_names", []) for c in ranges.get(n, [])}
    written = [c for c in getattr(cfg, "expected_origins", []) if not not_private(c)]
    cidrs = written + [c for c in named if c not in written and not usable(c) and (not degraded or not not_private(c))]
    return [(c, EXPECTED, f"origine attendue, réseau nommé « {named[c]} »" if c in named else "origine attendue")
            for c in cidrs]


def _exposed_layer(cfg, ranges: dict) -> list[tuple[str, str, str]]:
    """SEC2c: the exposed zone's ranges, a named network's said by its name. A named object's range the
    discovery read wider than the ceiling, or touching the platform, is left out (`config_zones.usable`):
    it stays the client's network, never blocked — said at the watch's start."""
    from glorfindel.config_zones import usable
    named = {c: n for n in getattr(cfg, "exposed_names", []) for c in ranges.get(n, [])}
    written = list(getattr(cfg, "exposed", []))
    cidrs = written + [c for c in named if c not in written and not usable(c)]
    return [(c, EXPOSED, f"zone exposée, réseau nommé « {named[c]} »" if c in named else "zone exposée")
            for c in cidrs]


def exposed_applies(resource_id: str) -> bool:
    """SEC2c: the exposed zone plays for a block on this resource — on Azure, where the discovery tells
    one host from a NAT gateway or an appliance; never on AWS (an ARN), whose network nothing reads."""
    return not str(resource_id or "").strip().lower().startswith("arn:")


def protection(ip: str, cfg=None, snap=None, exposed: bool = True) -> Protection:
    """The first layer that holds `ip` (`address_layers`), with why the client's list can't be
    trusted. Raises when glorfindel-config.yaml can't be read: never a block then (fail closed).
    An address of the exposed zone (SEC2c) is judged there (`exposed_zone.judge`): one host, the
    list trusted — EXPOSED, blockable; else held as the client's network. `exposed` False (AWS): the
    zone is skipped, the address judged by the layers after it."""
    import ipaddress
    from glorfindel.client_network import load
    snap = load() if snap is None else snap
    entries, degraded = address_layers(cfg, snap)
    why = " ; ".join(degraded)
    addr = _as_address(ip)
    for net, layer, source in entries if addr is not None else []:
        if layer == EXPOSED and not exposed:
            continue
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                if layer == EXPOSED:
                    from glorfindel.exposed_zone import judge
                    return judge(addr, net, source, snap, why)
                return Protection(entry=net, layer=layer, source=source, degraded=why)
        except ValueError:
            continue
    return Protection(degraded=why)


def degraded_words(why: str) -> str:
    """What a card and a refusal add when the client's list can't be trusted (decision 4)."""
    return (f" Attention : {why} — les blocages hors Internet restent refusés (plages privées, never_block), "
            "mais une adresse du client que cette liste ne connaît pas serait bloquée comme une adresse "
            "d'Internet." if why else "")


def held_words(ip: str, resource_id: str = "") -> str:
    """What a card says of a block it holds (SEC2, SEC2b) — "" when the address is blockable: one host
    of the exposed zone too (SEC2c: the mode's gate then decides, as for the Internet). The list unknown
    (glorfindel-config.yaml unreadable): held (fail closed)."""
    try:
        p = protection(ip, exposed=exposed_applies(resource_id))
    except Exception as exc:
        return (f"adresse protégée (liste never_block illisible : {_first_line(exc)}) — aucun blocage tant "
                "que glorfindel-config.yaml ne se lit pas.")
    if not p.entry:
        return ""
    if p.layer == EXPOSED:
        return ""
    check = "Vérifier d'où vient la détection (une ligne de journal peut nommer n'importe quelle adresse)."
    if p.layer == CLIENT:
        return (f"adresse protégée ({p.entry}, réseau du client : {p.source}) — Glorfindel ne bloque "
                "jamais une adresse du réseau du client, quelle que soit la règle ou le modèle ; un "
                f"mouvement latéral se répond par l'isolation de la VM source. {check}"
                + _source_card_words() + degraded_words(p.degraded))
    return (f"adresse protégée ({p.entry}, {p.source}) — Glorfindel ne la bloque jamais, quelle que "
            f"soit la règle ou le modèle. {check}" + degraded_words(p.degraded))


def _source_card_words() -> str:
    """SEC2d: switched on, the card of a held block of the client's network names the card of the source ("" off:
    its text as before)."""
    from glorfindel import lateral
    return (" Une carte à part (isolation de la VM source proposée, SEC2d) propose d'isoler la VM surveillée qui "
            "tient l'adresse, quand il y en a une." if lateral.on() else "")


def blockable_ip(ip: str, exposed: bool = True) -> str:
    """`single_host_ip`, and never a protected address (SEC2, SEC2b): the platform, `never_block`,
    the client's network. Every block goes through here — the agent's, an approval's, the CLI's, a
    reassertion's, on every provider. One host of the exposed zone is blockable (SEC2c); `exposed`
    False (the AWS connector): the zone skipped."""
    addr = single_host_ip(ip)
    try:
        held = protection(addr, exposed=exposed)
    except Exception as exc:
        raise ProtectedAddressError(
            f"blocage de {addr} refusé : liste never_block illisible "
            f"(glorfindel-config.yaml : {_first_line(exc)})") from exc
    if held.layer == CLIENT:
        raise ProtectedAddressError(
            f"blocage de {addr} refusé : réseau du client ({held.entry}, {held.source}) — Glorfindel ne "
            "bloque jamais une adresse du réseau du client ; à examiner par un humain"
            + degraded_words(held.degraded))
    if held.entry and held.layer != EXPOSED:
        raise ProtectedAddressError(
            f"blocage de {addr} refusé : adresse protégée ({held.entry}, {held.source}) — "
            "Glorfindel ne la bloque jamais ; à examiner par un humain")
    if held.degraded:
        import logging
        logging.getLogger("glorfindel.policy").warning(
            "blocage de %s : %s — ni privée ni connue du client, bloquée comme une adresse d'Internet",
            addr, held.degraded)
    return addr


def platform_open_nics(placements) -> list[str]:
    """The NICs (short names) an isolation holds by rules only — no quarantine placement:
    Azure's DNS and IMDS stay reachable from them (Q15, measured). The War Room, `list` and
    the autonomous isolation's notification say it (sixth review, S7): it was in the
    outcome, and shown nowhere."""
    held = {str(p.get("nic_id", "")).rstrip("/").lower()
            for p in placements or [] if p.get("kind") == "quarantine"}
    out: list[str] = []
    for p in placements or []:
        nic = str(p.get("nic_id", "")).rstrip("/")
        short = nic.rsplit("/", 1)[-1]
        if nic and nic.lower() not in held and short not in out:
            out.append(short)
    return out


def original_unknown_nics(placements) -> list[str]:
    """The NICs (short names) in our quarantine whose original NSG nothing recorded — not
    the state, and so not our tag either (Q7; or isolated beside a state that couldn't be
    read, SEC4b): their release, autonomous or not, stops until the operator sets the tag.
    Said at the isolation, not first at the release (SEC4b, second review)."""
    out: list[str] = []
    for p in placements or []:
        short = str(p.get("nic_id", "")).rstrip("/").rsplit("/", 1)[-1]
        if p.get("kind") == "quarantine" and "original_nsg_id" not in p and short and short not in out:
            out.append(short)
    return out


class WrongSubscriptionError(RuntimeError):
    """The target lives in another subscription than the one Glorfindel acts in."""


# What a block's check says for the reassertion alone (L1G, #461): each rule of the entry as it read
# it. Never in a cycle's outcome — the cycles stored feed what the model sees (`past_cycles`) — nor
# in a manual action's record.
_REASSERTION_ONLY = ("rules_seen",)


def as_recorded(verification: dict) -> dict:
    """A check as the cycle and the journal keep it: without what only the reassertion reads."""
    return {k: v for k, v in verification.items() if k not in _REASSERTION_ONLY}


_console = Console()
