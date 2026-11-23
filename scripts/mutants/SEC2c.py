"""SEC2c (#1107): the exposed zone (glorfindel/config_zones.py, glorfindel/exposed_zone.py,
glorfindel/exposed_blocks.py, glorfindel/response/policy.py, glorfindel/client_network_watch.py).
M7182–M7195: a zone wider than the ceiling accepted; a zone on Azure's platform accepted; one host of the zone
never blockable; a NAT gateway's address of the zone blockable; an appliance's address of the zone blockable; a
list that can't be trusted letting the zone block; the zone before never_block; decide holding one host of the
zone as protected; a block of the zone written without its deadline; the deadline never lifting; another VM
holding the address never lifting; a lift that fails said lifted; the zone never said loud at the start; a list
that can't be written said « never read » by the guard of the watch (the review of SEC2b, point 1). Measured by
tests/unit/test_exposed_zone.py."""
ZONES = "glorfindel/config_zones.py"
ZONE = "glorfindel/exposed_zone.py"
EXP = "glorfindel/exposed_blocks.py"
POL = "glorfindel/response/policy.py"
CNW = "glorfindel/client_network_watch.py"
_T = "tests/unit/test_exposed_zone.py"

MUTANTS = [
    ("M7182", "an exposed zone wider than /16 accepted: never a /8, decision 6 (SEC2c)", ZONES,
     "    if net.prefixlen < widest:\n", "    if False:\n"),
    ("M7183", "an exposed zone on Azure's platform or the loopback accepted (SEC2c, decision 6)", ZONES,
     "    for f in FORBIDDEN:\n", "    for f in ():\n"),
    ("M7184", "one host of the exposed zone never blockable: the zone read as the client's network (SEC2c)", POL,
     "    if held.entry and held.layer != EXPOSED:\n", "    if held.entry:\n"),
    ("M7185", "a NAT gateway's public IP in the exposed zone blockable: no single host (SEC2c, decision 6)", ZONE,
     "        if _addr(p.get(\"address\")) == addr and p.get(\"kind\") != \"nic\":\n",
     "        if False:\n"),
    ("M7186", "an appliance's address in the exposed zone blockable: a NIC that forwards packets (SEC2c)", ZONE,
     "    if held & _forwarders(snap):\n", "    if False:\n"),
    ("M7187", "a list that can't be trusted lets the exposed zone block: decision 4 (SEC2c)", ZONE,
     "    why = (\"liste du réseau du client non fiable\" if degraded else \"\") or not_one_host(addr, zone, snap)\n",
     "    why = not_one_host(addr, zone, snap)\n"),
    ("M7188", "the exposed zone before never_block and the platform: the most prudent no longer wins (SEC2c, "
     "decision 8)", POL,
     "    out += _exposed_layer(cfg, ranges)\n", "    out[:0] = _exposed_layer(cfg, ranges)\n"),
    ("M7189", "decide holds one host of the exposed zone as a protected address: the mode never decides (SEC2c)",
     POL, "    if p.layer == EXPOSED:\n        return \"\"\n", ""),
    ("M7190", "a block of the exposed zone written without its deadline: it never expires (SEC2c, decision 7)",
     "glorfindel/providers/azure/blocks.py",
     "        exposed = exposed_mark(ip)\n", "        exposed = None\n"),
    ("M7191", "a block of the exposed zone never lifted at its deadline (SEC2c, decision 7)", EXP,
     "    if now >= deadline:\n", "    if False:\n"),
    ("M7192", "a block of the exposed zone kept once another VM holds the address (SEC2c, decision 7)", EXP,
     "    if now_held and now_held != then:\n", "    if False:\n"),
    ("M7193", "a lift of the exposed zone that fails said lifted: its rules still block, said nowhere (SEC2c)",
     EXP, "    if out.get(\"status\") in (\"unblocked\", \"not_found\"):\n", "    if True:\n"),
    ("M7194", "the exposed zone never said loud at the watch's start (SEC2c)", CNW,
     "        out.append((\"strong\", f\"Zone exposée {cidr}", "        out.append((\"info\", f\"Zone exposée {cidr}"),
    ("M7195", "a list that can't be written said « jamais lue » by the guard of the watch, an older file read "
     "fresh (SEC2c, the review of SEC2b)", CNW,
     "        cn.unwritten(said)          # SEC2c, reprise 1: the guard of this process reads it back\n", ""),
    # The review of SEC2c: M7200–M7205.
    ("M7200", "an address of a subnet that no known NIC holds taken for one host: a firewall, a gateway, a "
     "uniform scale set (SEC2c review)", ZONE,
     "    if not held:\n        return (f\"aucune carte réseau connue", "    if False:\n        return (f\"aucune carte réseau connue"),
    ("M7201", "an address of a subnet Azure reserves to a service (AzureFirewallSubnet, AzureBastionSubnet…) "
     "taken for one host (SEC2c review)", ZONE,
     "    if subnet is not None and subnet[1].lower() in RESERVED_SUBNETS:\n", "    if False:\n"),
    ("M7202", "a block of the zone the second judgement can't judge written without its deadline, as an "
     "Internet one (SEC2c review)", ZONE,
     "        raise ProtectedAddressError(\n            f\"blocage de {ip} refusé : sa zone ne se juge plus",
     "        return None\n        raise ProtectedAddressError(\n            f\"blocage de {ip} refusé : sa zone ne se juge plus"),
    ("M7203", "the lift never judged again under the lock: a block taken again since lifted on the old "
     "deadline (SEC2c review)", EXP,
     "            if now_entry[\"exposed\"] != entry[\"exposed\"] or not due(now_entry, now, snap):\n",
     "            if False:\n"),
    ("M7204", "a block written over a failed lift keeps its past deadline: lifted at the next pass (SEC2c "
     "review)", "glorfindel/response/state.py",
     "            prev.pop(\"exposed\", None)\n            prev.update({\"exposed\": exposed} if exposed else {})\n",
     "            pass\n"),
    ("M7205", "an address of a client VNet outside every subnet read taken for one host (SEC2c review)", ZONE,
     "    if subnet is None:\n        return \"adresse d'un VNet du client hors de tout sous-réseau lu",
     "    if False:\n        return \"adresse d'un VNet du client hors de tout sous-réseau lu"),
]

TESTS = {f"M{n}": _T for n in (*range(7182, 7196), *range(7200, 7206))}
