"""The lateral movement seen (SEC2d, #1147): the time 2 of SEC2, behind a switch off by default.

Decisions of Jonathan of 23/11 (1, 2, 5 and 8) and of 24/11: the code is on `main`, tested, off; it is
switched on in the 0.7 only, after the bench's measure of an internal brute force and the run end to end
of ENQ5 (docs/design/mouvement-lateral.md).

- **The switch**, `GLORFINDEL_LATERAL` — a variable of the watch alone, never a key of the configuration
  (MEM2's reasons: an unknown value there refuses the whole file, and the console rewrites it). Unset,
  empty or `off`: off. `on`: on. Anything else: off, said once on stderr. **Off, nothing the model sees
  changes to the byte**: the shipped rule, the message, the prompt and the tool stay as they are.
- **The rule** (`base_rules`): on, the shipped `ssh-brute-force` loads in a variant (`variant`) — its
  query without the filter of the private ranges, the loopback alone kept out: it sees every source. The
  shipped file is never changed; the client's layer (P1) overrides the variant by name as it overrides the
  base, and a copy of the shipped rule (WL1, `base_sha256`) is set aside against it, the variant loading.
- **The code classes the source, never the model**, in the order of decision 8 (`policy.address_layers`):
  the platform and the loopback, `never_block`, an expected origin, the exposed zone, the rest of the
  client's network, the Internet — the most prudent wins. The Internet: blocked as before. The exposed
  zone: one host blockable, as SEC2c. An expected origin: the detection is set aside before any signal,
  said and counted (`origin_rows`, the RulePoller). The client's network: never a block (decide's guard and
  the connector, SEC2b, on or off) — and a card (`record_card`): when a monitored VM, found by its exact
  address in the discovery's read of the NICs, holds the address, it proposes to isolate that VM
  (`SOURCE_TYPE`, approvable in one click by the path of every held card); otherwise a card for a human
  (`HUMAN_TYPE`).
- **Never an isolation of the source alone**, whatever the mode, `full_auto` too: the address is read in a
  line of the target, which its guest can write — a forged address must never isolate a VM by itself. The
  card says it. A corroboration from the source may automate it later, in a lot of its own.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("glorfindel.lateral")

SWITCH = "GLORFINDEL_LATERAL"
ON, OFF = "on", "off"
RULE = "ssh-brute-force"
SOURCE_TYPE = "lateral_source"
HUMAN_TYPE = "lateral_unknown_source"
_said: set[str] = set()

# The filter of the shipped rule the variant takes off, to the byte (its two comment lines with it): the
# private ranges and the loopback. A shipped rule that no longer holds it once gets no variant (said).
_FILTER = ("// Exclude all RFC-1918 + loopback — aligned with data-exfiltration-blob\n"
           "// (172.16-31 was previously missing → internal 172.x flagged as external)\n"
           r'| where not(SourceIP matches regex @"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.|127\.)")' "\n")
_EVERY_SOURCE = ("// SEC2d (GLORFINDEL_LATERAL=on): every source but the loopback, the client's network included —\n"
                 "// the code classes the address (glorfindel/lateral.py), never the model; never a block of it.\n"
                 r'| where not(SourceIP matches regex @"^127\.")' "\n")
_DESCRIPTION = "Repeated SSH failures from any source but the loopback, classed by the code — T1110.001"


def switch(env=None) -> tuple[bool, str]:
    """(on, what is said of it — "" when nothing is). Unset, empty or `off`: off. `on`, spaces around
    aside: on. Anything else: off — the lateral movement unseen, as before — and said."""
    raw = (os.environ if env is None else env).get(SWITCH)
    value = raw.strip() if isinstance(raw, str) else ""
    if value == ON:
        return True, ""
    if value in ("", OFF):
        return False, ""
    shown = "".join(c if c.isprintable() else "?" for c in raw)[:40]
    return False, (f"{SWITCH}={shown!r} inconnu (attendu : {ON} ou {OFF}) — l'interrupteur reste éteint : "
                   "le mouvement latéral n'est pas vu, la règle livrée inchangée")


def on(env=None) -> bool:
    """The switch, read at each call; an unknown value said once by this process (stderr)."""
    value, said = switch(env)
    if said and said not in _said:
        _said.add(said)
        print(f"⚠ {said}", file=sys.stderr)
    return value


# ── The rule ──────────────────────────────────────────────────────────────────────────────────

def variant(rule: dict) -> dict | None:
    """The shipped `ssh-brute-force` without the filter of the private ranges — every other key as shipped;
    None when its query no longer holds the filter once, to the byte."""
    query = rule.get("query")
    if not isinstance(query, str) or query.count(_FILTER) != 1:
        return None
    return {**rule, "description": _DESCRIPTION, "query": query.replace(_FILTER, _EVERY_SOURCE)}


def base_rules(base: dict, path, environ=None) -> tuple[dict, list[str]]:
    """The base as `rule_layers` reads it: switched on and the shipped base, `ssh-brute-force` in its variant
    (said in the notes); otherwise the base as read, the very object."""
    if not on(environ) or not isinstance(base.get("rules"), list):
        return base, []
    from glorfindel.detection_rules import shipped_rules_path
    try:
        if Path(path).resolve() != shipped_rules_path().resolve():
            return base, []
    except OSError:
        return base, []
    rules, notes = [], []
    for r in base["rules"]:
        if isinstance(r, dict) and r.get("name") == RULE:
            v = variant(r)
            if v is None:
                notes.append(f"règle « {RULE} » : {SWITCH}=on, mais sa requête livrée n'a plus le filtre des plages "
                             "privées attendu — la règle livrée charge telle quelle (le mouvement latéral n'est "
                             "pas vu)")
                v = r
            else:
                notes.append(f"règle « {RULE} » : variante du temps 2 ({SWITCH}=on, SEC2d) — toutes les sources hors "
                             "bouclage ; le code classe l'adresse, jamais le modèle")
            rules.append(v)
        else:
            rules.append(r)
    return {**base, "rules": rules}, notes


# ── An expected origin: set aside, said and counted ───────────────────────────────────────────

def origin_rows(rows: list, cfg) -> set[int]:
    """id(row) of each row whose `SourceIP` an expected origin holds (`policy.EXPECTED`, the first layer that
    holds it: never one `never_block` holds first) — set aside by the RulePoller before any signal. Switched
    off, no expected origin, no config: none. A row the guard can't judge stays a card."""
    if cfg is None or not on() or not (getattr(cfg, "expected_origins", None) or getattr(cfg, "expected_names", None)):
        return set()
    from glorfindel.client_network import load
    from glorfindel.response.policy import EXPECTED, protection
    snap = load()
    out: set[int] = set()
    for r in rows:
        ip = r.get("SourceIP") if isinstance(r, dict) else None
        if not isinstance(ip, str) or not ip.strip():
            continue
        try:
            if protection(ip, cfg, snap).layer == EXPECTED:
                out.add(id(r))
        except Exception:            # judged nowhere: a card, as before
            continue
    return out


def add_count(was, n: int, now_iso: str) -> dict:
    """The rule's status of the expected origins set aside, `n` more at this pass."""
    before = origin_counts({"expected_origins": was})
    return {"count": before["expected_origin_count"] + n, "last": now_iso if n else before["expected_origin_last"]}


def origin_counts(status: dict) -> dict:
    """The detections a rule set aside as an expected origin's, as its status holds them — the console reads
    them here."""
    eo = status.get("expected_origins") if isinstance(status, dict) else None
    eo = eo if isinstance(eo, dict) else {}
    count = eo.get("count")
    return {"expected_origin_count": count if type(count) is int and count >= 0 else 0,
            "expected_origin_last": str(eo.get("last") or "")}


# ── The client's network: the card of the source ──────────────────────────────────────────────

def _row(signal: dict) -> dict:
    raw = signal.get("raw_signal") or {}
    for row in (raw.get("detected_data"), raw.get("first_result_row")):
        if isinstance(row, dict) and row.get("SourceIP"):
            return row
    return {}


def _short(rid: str) -> str:
    return str(rid or "").rstrip("/").rsplit("/", 1)[-1]


def source_vm(addr, snap, degraded: str, registry=None) -> tuple[str, str]:
    """(the monitored VM that holds `addr`, its id as the registry keeps it; "") or ("", why none). By the
    exact address, in the discovery's read of the NICs (`exposed_zone.holders`); never an appliance's, never
    an address two VMs hold, never on a list that can't be trusted; a VM the registry watches."""
    from glorfindel.client_network import _LISTS
    from glorfindel.exposed_zone import _forwarders, holders
    if degraded:
        return "", f"liste du réseau du client non fiable ({degraded}) : la VM qui tient l'adresse n'est pas sûre"
    if missing := [k for k in _LISTS if k not in snap.listed]:
        return "", f"lecture du réseau du client sans {', '.join(missing)} : la VM qui tient l'adresse est inconnue"
    held = holders(snap).get(addr, set())
    names = ", ".join(_short(v) for v in sorted(held))
    if not held:
        return "", "aucune carte réseau lue ne la tient (une passerelle, un pare-feu, un bastion, une VM hors du registre ?)"
    if held & _forwarders(snap):
        return "", f"adresse d'une appliance ({names} : une carte qui transfère les paquets) — la VM source est derrière elle"
    if len(held) > 1:
        return "", f"tenue par {len(held)} VM ({names}) : aucune n'est sûre"
    (vm,) = held
    if registry is None:
        from glorfindel.discovery import AssetRegistry
        registry = AssetRegistry()
    watched = {a.resource_id.rstrip("/").lower(): a.resource_id for a in registry.all() if a.resource_id}
    if vm not in watched:
        return "", f"tenue par {_short(vm)}, une VM que Glorfindel ne surveille pas"
    return watched[vm], ""


def judge(signal: dict, cfg=None, snap=None, registry=None) -> dict | None:
    """The source of a detection when the client's network holds it (`policy.CLIENT`, decision 8) — `{ip, entry,
    source, vm, why, target}` — else None: switched off, no detection, no `SourceIP`, another layer (the
    Internet, the exposed zone, an expected origin, the platform, never_block). `vm`: the monitored VM that
    holds it (`source_vm`), "" with `why` otherwise. A config the guard can't read: a card for a human."""
    if not on() or signal.get("event") != "detection":
        return None
    from glorfindel.response.policy import CLIENT, _as_address, _first_line, protection
    addr = _as_address(str(_row(signal).get("SourceIP") or ""))
    if addr is None:
        return None
    rid = str(signal.get("resource_id") or "")
    out = {"ip": str(addr), "entry": "", "source": "", "vm": "", "why": "", "target": rid}
    if snap is None:
        from glorfindel.client_network import load
        snap = load()
    try:
        held = protection(str(addr), cfg, snap)
    except Exception as exc:
        return {**out, "why": f"glorfindel-config.yaml illisible ({_first_line(exc)}) : la source n'est pas classée"}
    if held.layer != CLIENT:
        return None
    out.update(entry=held.entry, source=held.source)
    if (signal.get("context") or {}).get("attribution") == "unattributed":
        return {**out, "why": "la ligne ne nomme aucune VM : qui l'a écrite n'est pas connu"}
    vm, why = source_vm(addr, snap, held.degraded, registry)
    return {**out, "vm": vm, "why": why}


def _reason(j: dict, ttp: str) -> str:
    target, ip = _short(j["target"]) or "?", j["ip"]
    said = (f"Force brute ({ttp or 'T1110.001'}) sur {target} depuis {ip}, une adresse du réseau du client "
            f"({j['entry'] or '?'}, {j['source'] or '?'}) : Glorfindel ne la bloque jamais (SEC2d). ")
    if j["vm"]:
        return (said + f"La VM surveillée {_short(j['vm'])} tient cette adresse : la carte propose de l'isoler — une "
                "proposition, jamais exécutée seule, quel que soit le mode. L'adresse vient d'une ligne de la cible "
                f"({target}), que son invité peut écrire : vérifier sur {_short(j['vm'])} qu'elle a bien ouvert ces "
                "connexions avant d'approuver.")
    return (said + f"Aucune VM surveillée n'est à isoler : {j['why']}. L'adresse vient d'une ligne de la cible "
            f"({target}), que son invité peut écrire : chercher d'où vient ce trafic.")


def record_card(state: dict, source: str, exercise_run: str) -> None:
    """The card of a detection whose source the client's network holds (`judge`), written at the cycle's end,
    apart from the decision's, whatever the mode and the decision: `SOURCE_TYPE` on the source VM, proposing
    `isolate_vm` (approvable in one click, never run here); `HUMAN_TYPE` on the target otherwise. Never in a
    dry run; never raises."""
    if state.get("dry_run"):
        return
    signal = state.get("signal") or {}
    from glorfindel.terminal import outside
    try:
        j = judge(signal)
        if j is None:
            return
        from glorfindel import escalations
        from glorfindel.vm_command import group_and_name
        ctx = signal.get("context") or {}
        common = dict(signal_id=signal.get("signal_id", ""), reason=_reason(j, signal.get("ttp", "")),
                      run_id=ctx.get("run_id", ""), ttp=signal.get("ttp", ""), severity="high",
                      rule_name=ctx.get("rule_name", ""), source=source, exercise_run=exercise_run)
        if j["vm"]:
            escalations.record(
                resource_id=j["vm"], action="isolate_vm", escalation_type=SOURCE_TYPE,
                suggested_steps=[f"Sur {group_and_name(j['vm'])} : chercher les connexions SSH sortantes vers "
                                 f"{_short(j['target'])} (son journal, `ss -tnp`) — l'adresse {j['ip']} n'est qu'une "
                                 "ligne de la cible",
                                 "Approuver l'isolation si la VM source est compromise ; sinon, acquitter la carte"],
                **common)
        else:
            escalations.record(
                resource_id=j["target"], action="none", escalation_type=HUMAN_TYPE, action_params={"ip": j["ip"]},
                suggested_steps=[f"Chercher qui tient {j['ip']} dans le réseau du client (une VM hors du registre, "
                                 "une passerelle, un bastion, un poste par le VPN)",
                                 "Si c'est attendu (un scanner, une supervision), le déclarer dans "
                                 "network_zones.expected_origins"],
                **common)
    except Exception as exc:          # said; the cycle's debug line is still written
        print(f"store_cycle: carte du mouvement latéral (SEC2d) non écrite — {outside(exc)}", file=sys.stderr)


# ── At the watch's start ──────────────────────────────────────────────────────────────────────

def start_lines(cfg, snap) -> list[tuple[str, str]]:
    """(level, text) the watch adds at its start (glorfindel/client_network_watch.py): switched on, the switch
    loud and each expected origin; off, the expected origins declared said without effect; an unknown value
    of the switch, loud. Off without any expected origin: nothing."""
    value, said = switch()
    names = list(getattr(cfg, "expected_names", []) or [])
    of_names = {c for n in names for c in getattr((getattr(cfg, "networks", {}) or {}).get(n), "cidrs", ())}
    declared = names + [c for c in getattr(cfg, "expected_origins", []) or [] if c not in of_names]
    out: list[tuple[str, str]] = []
    if said:
        out.append(("loud", said))
    if not value:
        if declared:
            out.append(("note", f"network_zones.expected_origins : {', '.join(declared)} — sans effet tant que "
                                f"l'interrupteur {SWITCH} est éteint (SEC2d, 0.7)"))
        return out
    out.append(("strong", f"Mouvement latéral vu ({SWITCH}=on, SEC2d) : la règle {RULE} voit toutes les sources ; une "
                          "source du réseau du client n'est jamais bloquée — tenue par une VM surveillée, une carte "
                          "propose de l'isoler, jamais seule ; sinon, une carte pour un humain"))
    from glorfindel.config_zones import usable
    from glorfindel.response.policy import EXPECTED, address_layers
    entries, _ = address_layers(cfg, snap)
    for cidr, layer, source in entries:
        if layer == EXPECTED:
            out.append(("info", f"Origine attendue {cidr} ({source}) — sert : network_zones.expected_origins : une "
                                "détection qui en vient est écartée, dite et comptée ; jamais bloquée"))
    for name in getattr(cfg, "expected_names", []) or []:
        net = cfg.networks.get(name)
        for cidr in (snap.resolve(net)[0] if net is not None and net.is_object else []):
            if why := usable(cidr):
                out.append(("note", f"origine attendue, réseau nommé « {name} » : {cidr} écartée — {why} ; elle reste "
                                    "le réseau du client"))
    return out
