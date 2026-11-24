"""The zones of glorfindel-config.yaml's `network_zones` (SEC2c, #1107; decisions of 23/11, 5, 6 and 8).

`network_zones.exposed` declares the client's exposed zone — a DMZ, a partner's range —, where a block of
ONE host is possible again, the attacked VM's mode permitting (glorfindel/exposed_zone.py): a list of
ranges, or of named networks of `networks` (glorfindel/config_networks.py), cited by their name:

    networks:
      dmz: {subnet: "vnet-hub/snet-dmz"}
    network_zones:
      exposed: [dmz, 203.0.113.0/26]

Read as strictly as the rest of the file (A3):

- each entry a range read as an origin is (`correlation.origin`: no host bits, never `/0`), or a name
  declared in `networks` — a name not declared refuses the file;
- **narrow**: a range wider than `EXPOSED_CEILING` (/16 in IPv4, /48 in IPv6) refuses the file, a named
  network's range too. A named object's range, read by the discovery, wider than it is left out of the
  zone — it stays the client's network, never blocked — and said (`usable`);
- **never** Azure's platform, the loopback, the link-local, multicast, unspecified or reserved ranges, nor
  an IPv4 written as IPv6 (`::ffff:0:0/96`): a range that touches one refuses the file (decision 6);
`network_zones.expected_origins` (SEC2d, #1147; decisions 1, 5 and 8): the origins a detection is expected
from — an internal scanner, the office's bastion, a partner's monitoring. Read as `exposed` is: a range or a
named network, narrow (never a /8), never the platform; a name not declared refuses the file. Its place is
the third layer of `policy.address_layers`, before the exposed zone (an overlap is said at the start, the
expected origin wins); a detection from it is set aside, said and counted (glorfindel/lateral.py) — only
while the switch of the lateral movement is on (`GLORFINDEL_LATERAL`). Off, the key is read, checked and
said at the start as without effect.

A new key: an older version refuses a file that carries it (A3), as for `networks`.
"""
from __future__ import annotations

import ipaddress

# The widest exposed range, by IP version: a DMZ or a partner is a few subnets, never a /8 (decision 6).
EXPOSED_CEILING = {4: 16, 6: 48}
# What an exposed range never touches: Azure's platform (168.63.129.16, IMDS in the link-local), the
# loopback, the link-local, multicast, the unspecified and reserved ranges, IPv4 written as IPv6.
FORBIDDEN = ("168.63.129.16/32", "169.254.0.0/16", "127.0.0.0/8", "0.0.0.0/8", "224.0.0.0/4", "240.0.0.0/4",
             "::1/128", "::/128", "fe80::/10", "ff00::/8", "::ffff:0:0/96")
_KEYS = ("exposed", "expected_origins")


def usable(cidr: str) -> str:
    """Why a range can't be part of the exposed zone ("" when it can): too wide, or touching a range it
    never touches."""
    try:
        net = ipaddress.ip_network(str(cidr), strict=False)
    except ValueError:
        return "ni une adresse ni une plage CIDR"
    widest = EXPOSED_CEILING[net.version]
    if net.prefixlen < widest:
        return (f"plus large que /{widest} : une zone exposée ou une origine attendue est étroite (une DMZ, "
                "un partenaire, un scanner), jamais un /8 — la découper, ou la déclarer en plusieurs plages")
    for f in FORBIDDEN:
        other = ipaddress.ip_network(f)
        if other.version == net.version and net.overlaps(other):
            return (f"touche {f} (plateforme Azure, bouclage, lien local, multidiffusion ou plage réservée) : "
                    "jamais dans une zone exposée ni une origine attendue")
    return ""


def check_zones(raw: dict, networks: dict, uses: dict, check) -> tuple[list[str], list[str], list[str], list[str]]:
    """(the exposed ranges, canonical, the names it cites, the expected origins, the names they cite) —
    each problem noted on `check` (config._Checker). An object's name is kept for the discovery to
    resolve (its range, `usable` then)."""
    where = "network_zones"
    check.keys(raw, where, _KEYS)
    exposed, names = _ranges(raw, "exposed", networks, uses, check, "une liste vide ne déclare aucune zone")
    expected, expected_names = _ranges(raw, "expected_origins", networks, uses, check,
                                       "une liste vide ne déclare aucune origine")
    return exposed, names, expected, expected_names


def _ranges(raw: dict, key: str, networks: dict, uses: dict, check, empty: str) -> tuple[list[str], list[str]]:
    """One key of `network_zones`: its ranges, canonical, and the names it cites — narrow, never the
    platform (`usable`), each name declared in `networks`."""
    from glorfindel.config_networks import cite
    from glorfindel.correlation import origin
    where = f"network_zones.{key}"
    if raw.get(key) == []:
        check.bad(where, f"{empty} — omettre la clé")
    out: list[str] = []
    names: list[str] = []
    for j, text in enumerate(check.texts(raw, key, "network_zones")):
        at = f"{where}[{j}]"
        net, why = origin(text)
        named, unknown = cite(text.strip(), networks) if why else (None, "")
        if named is not None:
            uses.setdefault(named.name, []).append(where)
            names += [named.name] if named.name not in names else []
            for c in named.cidrs:
                if bad := usable(c):
                    check.bad(at, f"réseau nommé « {named.name} », {c} : {bad}")
                elif c not in out:
                    out.append(c)
        elif why:
            check.bad(at, f"{text!r} : {why}" + (f" ; {unknown}" if unknown else ""))
        elif bad := usable(net):
            check.bad(at, f"{text!r} : {bad}")
        elif net not in out:
            out.append(net)
    return out, names
