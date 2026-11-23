"""The named networks of glorfindel-config.yaml (SEC2b, #1089; decisions of 23/11, 5 and 9).

A section `networks` declares each network once, by a name: a list of CIDR ranges, or one object of
the client's Azure, read by the discovery, by its exact name — a subnet (`{subnet: "<vnet>/<subnet>"}`)
or a VNet (`{vnet: "<name>"}`):

    networks:
      bureau: [198.51.100.0/28]
      dmz: {subnet: "vnet-hub/snet-dmz"}
      partenaire: {vnet: "vnet-partenaire"}

They are cited by their name where a range is read — `never_block` and
`expected_sudo.admins[].origins` (ADM1, COR1); a range written there directly is still accepted. Read
as strictly as the rest of the file (A3):

- a name cited and not declared refuses the file; a name declared and cited nowhere is said, never
  refused (`GlorfindelConfig.notes`): it still counts in the client's network, never blocked;
- a range is read as an origin is (`correlation.origin`): no host bits, never `/0`;
- an object is named exactly — a pattern (`*`, `?`, `[`) is refused: a VNet made later never widens a
  name in silence. Two VNets of one name in the subscription are no exact name either: the name is
  unresolved (`glorfindel.client_network`), like a name the discovery does not find.

`network_zones` is read in glorfindel/config_zones.py: the exposed zone (SEC2c), which cites these names
too; the expected origins wait for SEC2d.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A name of the config: a letter first, then letters, digits, « _ » and « - » — never an address.
NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,62}")
# An Azure name, written whole: letters, digits, « _ . - » — no « * ? [ », never a pattern.
_AZURE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}")
_OBJECT_KEYS = ("vnet", "subnet")


@dataclass(frozen=True)
class NamedNetwork:
    """One entry of `networks`: its ranges (`cidrs`), or the object it names — `vnet` (a VNet's
    name) or `subnet` (`<vnet>/<subnet>`), resolved by the discovery."""
    name: str
    cidrs: tuple[str, ...] = ()
    vnet: str = ""
    subnet: str = ""

    @property
    def is_object(self) -> bool:
        return bool(self.vnet or self.subnet)

    def written(self) -> str:
        """What the config says it is, as the watch says it at its start."""
        if self.subnet:
            return f"sous-réseau {self.subnet}"
        if self.vnet:
            return f"VNet {self.vnet}"
        return ", ".join(self.cidrs)


def _range(text: str) -> tuple[str, str]:
    """A range of the section, read as an origin is: (canonical range, "") or ("", why)."""
    from glorfindel.correlation import origin
    return origin(text)


def check_networks(raw: dict, check) -> dict[str, NamedNetwork]:
    """The section `networks`, each problem noted on `check` (config._Checker)."""
    out: dict[str, NamedNetwork] = {}
    for name, value in raw.items():
        where = f"networks.{name}"
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            check.bad(where, "un nom commence par une lettre, puis lettres, chiffres, « _ » ou « - » "
                             "(jamais une adresse)")
            continue
        if isinstance(value, list):
            cidrs: list[str] = []
            if not value:
                check.bad(where, "une liste vide ne désigne aucune adresse — retirer le nom")
            for j, item in enumerate(value):
                net, why = _range(item) if isinstance(item, str) else ("", "un texte est attendu")
                if why:
                    check.bad(f"{where}[{j}]", f"{item!r} : {why}")
                elif net not in cidrs:
                    cidrs.append(net)
            out[name] = NamedNetwork(name=name, cidrs=tuple(cidrs))
        elif isinstance(value, dict):
            found = _object(value, where, check)
            if found is not None:
                out[name] = NamedNetwork(name=name, **found)
        else:
            check.bad(where, "une liste de plages CIDR, ou {subnet: \"<vnet>/<sous-réseau>\"}, ou "
                             "{vnet: \"<nom>\"} est attendu")
    return out


def _object(value: dict, where: str, check) -> dict | None:
    """{vnet: …} or {subnet: …}: one key, an exact Azure name (`vnet/subnet` for a subnet)."""
    check.keys(value, where, _OBJECT_KEYS)
    keys = [k for k in _OBJECT_KEYS if k in value]
    if len(keys) != 1:
        check.bad(where, "une seule clé, vnet ou subnet")
        return None
    key, text = keys[0], value[keys[0]]
    if not isinstance(text, str):
        check.bad(f"{where}.{key}", "un texte est attendu (le nom exact de l'objet)")
        return None
    parts = text.split("/") if key == "subnet" else [text]
    if len(parts) != (2 if key == "subnet" else 1) or not all(_AZURE_NAME_RE.fullmatch(p) for p in parts):
        form = "<vnet>/<sous-réseau>" if key == "subnet" else "<nom du VNet>"
        check.bad(f"{where}.{key}", f"{text!r} : le nom exact attendu, {form} — lettres, chiffres, "
                                    "« _ . - », jamais un motif")
        return None
    return {key: text}


def cite(text: str, networks: dict[str, NamedNetwork]) -> tuple[NamedNetwork | None, str]:
    """A text of `never_block` or `origins` that is not a range: (the network it names, "") or
    (None, why). Only a declared name is a network; any other text is refused by the caller."""
    if NAME_RE.fullmatch(text) and text in networks:
        return networks[text], ""
    if NAME_RE.fullmatch(text):
        return None, f"aucun réseau nommé « {text} » déclaré dans networks"
    return None, ""


def unused_notes(networks: dict[str, NamedNetwork], uses: dict[str, list[str]]) -> list[str]:
    """A name declared and cited nowhere: said, never refused."""
    return [f"networks.{n} : déclaré, cité par aucune clé — compté dans le réseau du client "
            "(jamais bloqué), rien d'autre" for n in networks if not uses.get(n)]
