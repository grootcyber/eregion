#!/usr/bin/env python3
"""operator_cidr — the one address SSH admits toward Imladris and Orodruin (SEC-G, audit of 13/11, V-40).

  python3 scripts/operator_cidr.py      the operator's address, as `<IPv4>/32`, on stdout — or exit 1

What it reads: EREGION_OPERATOR_CIDR (the Makefile hands it OPERATOR_CIDR, never expanded by make). Set,
it must be one public IPv4 address in /32: a range (0.0.0.0/1, /24…), an IPv6, a private, loopback,
link-local, shared (CGNAT), multicast or reserved address is refused — the NSG of Imladris and of
Orodruin admits SSH from it, and the firewall of Orodruin's channel takes it too. IPv6 is refused
as well, /128 included: both VMs have an IPv4 public address only (an IPv6 source never reaches them),
and a rule of a storage account's firewall takes IPv4 only.

Unset, the address is read on a third-party service (api.ipify.org, IPv4 only) — said on stderr,
never silently —, and its answer passes the same check: anything but one public IPv4 address is
refused, never suffixed « /32 » and handed to Terraform. Setting OPERATOR_CIDR avoids the service.

The address itself is never printed but on stdout (the Makefile keeps it in the shell, off the
command it shows). The same reserved ranges are in the validation of both modules
(infra/glorfindel-host/variables.tf, infra/orodruin/variables.tf): tests/unit/test_operator_cidr.py
keeps the three lists equal. Standard library only.
"""
from __future__ import annotations

import ipaddress
import os
import re
import sys
import urllib.request

# The ranges never admitted as the operator's address (IANA's special-purpose registry, IPv4). The
# documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) stay admitted: the placeholders
# of the tests and of the docs, never routed to anyone.
RESERVED = ("0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
            "192.0.0.0/24", "192.168.0.0/16", "198.18.0.0/15", "224.0.0.0/4", "240.0.0.0/4")
# Four decimal octets, no leading zero (« 010 » is octal to some readers), then /32.
FORM = re.compile(r"(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])(\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])){3}")
SERVICE = os.environ.get("EREGION_OPERATOR_IP_URL") or "https://api.ipify.org"
MAX = 64


class Refused(Exception):
    """Not one public IPv4 address."""


def check_address(text: str) -> str:
    """The address, when it is one public IPv4 address; else Refused, saying why (never echoing it)."""
    if not FORM.fullmatch(text):
        raise Refused("pas une adresse IPv4 écrite en quatre nombres (une IPv6, /128 comprise, ne joint pas "
                      "Imladris ni Orodruin : leur adresse publique est IPv4)")
    ip = ipaddress.IPv4Address(text)
    for net in RESERVED:
        if ip in ipaddress.IPv4Network(net):
            raise Refused(f"une adresse de {net}, jamais publique (privée, boucle locale, partagée, réservée…)")
    return text


def check_cidr(value: str) -> str:
    """`<IPv4>/32` for one public address; else Refused — a range, a prefix other than /32."""
    address, slash, prefix = value.partition("/")
    if ":" in address:
        raise Refused("une IPv6, /128 comprise : elle ne joint pas Imladris ni Orodruin, dont l'adresse publique "
                      "est IPv4, et le pare-feu du canal ne prend que l'IPv4")
    if not slash or prefix != "32":
        raise Refused("pas un /32 : une seule adresse, jamais une plage (0.0.0.0/0, 0.0.0.0/1, /24…)")
    return check_address(address) + "/32"


def from_service() -> str:
    """The workstation's public address as the service answers it — checked, never trusted."""
    req = urllib.request.Request(SERVICE, headers={"User-Agent": "eregion-operator-cidr"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read(MAX + 1)
    except Exception as e:  # noqa: BLE001 — the network, the service: said, refused
        raise Refused(f"{SERVICE} ne répond pas ({type(e).__name__})") from None
    if len(body) > MAX:
        raise Refused(f"la réponse de {SERVICE} n'est pas une adresse (trop longue)")
    try:
        text = body.decode("ascii").strip()
    except UnicodeDecodeError:
        raise Refused(f"la réponse de {SERVICE} n'est pas une adresse") from None
    try:
        return check_address(text) + "/32"
    except Refused as e:
        raise Refused(f"la réponse de {SERVICE} : {e}") from None


def main() -> int:
    value = os.environ.get("EREGION_OPERATOR_CIDR", "")
    try:
        if value:
            cidr = check_cidr(value)
        else:
            print(f"  ℹ OPERATOR_CIDR non posé : ton adresse publique lue sur {SERVICE}, un service tiers, et "
                  "vérifiée — OPERATOR_CIDR=<ton IP>/32 pour ne pas en dépendre", file=sys.stderr)
            cidr = from_service()
    except Refused as e:
        print(f"✗ OPERATOR_CIDR refusé : {e}. La seule source SSH admise vers Imladris et Orodruin est ton "
              "adresse publique, en /32 : OPERATOR_CIDR=<ton IP>/32. Rien n'est planifié.", file=sys.stderr)
        return 1
    print(cidr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
