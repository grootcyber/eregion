"""SEC2b (#1089): the client's network never blocked (glorfindel/client_network.py,
glorfindel/client_network_watch.py, glorfindel/config_networks.py, glorfindel/response/policy.py).
M7143–M7152: an address of a client VNet outside the private ranges blocked; a NAT gateway's public IP
blocked; decide's guard that lets a client address go; a list unreadable read as an empty one, in silence;
`::ffff:169.254.x.x` accepted by `single_host_ip`; a named network unknown accepted; a name resolved on a
pattern; `never_block` behind the client's network; a read partial taken for a whole one (M7151); a change
of what a name designates said on no card (M7152). Measured by tests/unit/test_client_network.py."""
CN = "glorfindel/client_network.py"
CNW = "glorfindel/client_network_watch.py"
NETS = "glorfindel/config_networks.py"
POL = "glorfindel/response/policy.py"
_T = "tests/unit/test_client_network.py"

MUTANTS = [
    ("M7143", "an address of a client VNet outside the private ranges, blocked: the VNets never listed (SEC2b)", CN,
     "        for v in self.vnets:\n            out += [(p, f\"VNet",
     "        for v in ():\n            out += [(p, f\"VNet"),
    ("M7144", "the public IP of a client's NAT gateway blocked: the public IPs never listed (SEC2b)", CN,
     "        for p in self.public_ips + self.prefixes:\n",
     "        for p in self.prefixes:\n"),
    ("M7145", "decide's guard lets a block of a client address go (SEC2b)", POL,
     "    if not p.entry:\n        return \"\"\n",
     "    if not p.entry or p.layer == CLIENT:\n        return \"\"\n"),
    ("M7146", "a client's list unreadable read as an empty one, in silence (SEC2b, decision 4)", CN,
     "        return Snapshot(state=\"unreadable\", error=f\"{type(exc).__name__}: {str(exc)[:160]}\")\n",
     "        return Snapshot(state=\"fresh\")\n"),
    ("M7147", "::ffff:169.254.x.x accepted by single_host_ip: the IPv4 it writes never judged (SEC2b)", POL,
     "    addr = _as_address(ip)\n    if addr is None:\n        raise ValueError(f\"adresse IP invalide",
     "    import ipaddress\n    try:\n        addr = ipaddress.ip_address((ip or \"\").strip())\n"
     "    except ValueError:\n        addr = None\n    if addr is None:\n        raise ValueError(f\"adresse IP invalide"),
    ("M7148", "a named network cited and not declared, accepted (SEC2b)", NETS,
     "    if NAME_RE.fullmatch(text) and text in networks:\n        return networks[text], \"\"\n",
     "    if NAME_RE.fullmatch(text):\n        return networks.get(text, NamedNetwork(name=text)), \"\"\n"),
    ("M7149", "a named network's object resolved on a pattern, never its exact name (SEC2b, decision 9)", CN,
     "if str(v.get(\"name\", \"\")).lower() == want_vnet.lower()]",
     "if str(v.get(\"name\", \"\")).lower().startswith(want_vnet.lower())]"),
    ("M7150", "never_block behind the client's network: another declaration said first (SEC2b, decision 8)", POL,
     ("    out += [(c, NEVER_BLOCK, f\"never_block, réseau nommé",
      "    out += [(c, CLIENT, source) for c, source in snap.entries()]\n    return out, degraded"),
     ("    nb = [(c, NEVER_BLOCK, f\"never_block, réseau nommé",
      "    out += [(c, CLIENT, source) for c, source in snap.entries()] + nb\n    return out, degraded")),
    ("M7151", "a read of the client's network partial (a listing refused) taken for a whole one (SEC2b)", CN,
     "        state = \"partial\" if lists[\"unread\"] else \"fresh\"\n",
     "        state = \"fresh\"\n"),
    ("M7152", "a change of what a named network designates said on no card (SEC2b, decision 9)", CNW,
     "        escalations.record(signal_id=f\"network-changed-{name}\"",
     "        (lambda **_k: None)(signal_id=f\"network-changed-{name}\""),
]

TESTS = {f"M{n}": _T for n in range(7143, 7153)}
