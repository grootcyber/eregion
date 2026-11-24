"""SEC2d (#1147): the lateral movement seen, behind a switch off by default (glorfindel/lateral.py,
glorfindel/config_zones.py, glorfindel/response/policy.py, glorfindel/detection_rules.py, glorfindel/exposed_blocks.py,
eregion_core/action_queue.py). M7360–M7379: a switch guessed on; the variant keeping the filter of the private ranges,
or loaded over a base that is not the shipped one; an expected origin too wide, or a name not declared, accepted; the
order of decision 8 broken at each frontier (never_block, the exposed zone, the rest of the client's network); a
detection from an expected origin dispatched, or never counted; the card of the source said taken alone, or not
approvable; a source VM proposed on an appliance's address, on a list that can't be trusted, or unwatched; decide's
guard and the connector letting a block of the client's network go once switched on; the switch never said loud at
the start; the review of SEC2c (a failed lift's card of a replaced episode left open, or closed on its own episode).
Measured by tests/unit/test_lateral.py."""
LAT = "glorfindel/lateral.py"
ZONES = "glorfindel/config_zones.py"
POL = "glorfindel/response/policy.py"
DR = "glorfindel/detection_rules.py"
EXP = "glorfindel/exposed_blocks.py"
_T = "tests/unit/test_lateral.py"

MUTANTS = [
    ("M7360", "the switch of the lateral movement guessed on from another value than `on` (SEC2d)", LAT,
     "    if value == ON:\n        return True, \"\"\n",
     "    if value.lower() in (ON, \"1\", \"true\", \"oui\"):\n        return True, \"\"\n"),
    ("M7361", "the variant of ssh-brute-force keeps the filter of the private ranges: the lateral movement unseen "
     "(SEC2d)", LAT,
     "    return {**rule, \"description\": _DESCRIPTION, \"query\": query.replace(_FILTER, _EVERY_SOURCE)}\n",
     "    return {**rule, \"description\": _DESCRIPTION, \"query\": query}\n"),
    ("M7362", "an expected origin wider than /16, or on Azure's platform, accepted (SEC2d)", ZONES,
     "        elif bad := usable(net):\n            check.bad(at, f\"{text!r} : {bad}\")\n",
     "        elif False:\n            check.bad(at, f\"{text!r} : {bad}\")\n"),
    ("M7363", "an expected origin citing a name not declared accepted: the file not refused (SEC2d, decision 5)",
     ZONES, "        elif why:\n            check.bad(at, f\"{text!r} : {why}\"",
     "        elif why and key == \"exposed\":\n            check.bad(at, f\"{text!r} : {why}\""),
    ("M7364", "an expected origin before never_block and the platform: the most prudent no longer wins (SEC2d, "
     "decision 8)", POL,
     "    out += _expected_layer(cfg, ranges)\n    out += _exposed_layer(cfg, ranges)\n",
     "    out[:0] = _expected_layer(cfg, ranges)\n    out += _exposed_layer(cfg, ranges)\n"),
    ("M7365", "the exposed zone before an expected origin: an origin of the zone blockable (SEC2d, decision 8)", POL,
     "    out += _expected_layer(cfg, ranges)\n    out += _exposed_layer(cfg, ranges)\n",
     "    out += _exposed_layer(cfg, ranges)\n    out += _expected_layer(cfg, ranges)\n"),
    ("M7366", "one host of the exposed zone taken for the rest of the client's network: a card of the source "
     "(SEC2d, decision 8)", LAT,
     "    if held.layer != CLIENT:\n        return None\n",
     "    if held.layer not in (CLIENT, \"exposed_zone\"):\n        return None\n"),
    ("M7367", "a detection from an expected origin dispatched: never set aside (SEC2d)", LAT,
     "            if protection(ip, cfg, snap).layer == EXPECTED:\n                out.add(id(r))\n",
     "            if protection(ip, cfg, snap).layer == EXPECTED:\n                pass\n"),
    ("M7368", "the detections from an expected origin set aside, never counted (SEC2d)", DR,
     "            if aside_n:\n                st[\"expected_origins\"]",
     "            if False:\n                st[\"expected_origins\"]"),
    ("M7369", "the card of the source written as an action taken alone, never a proposal (SEC2d)", LAT,
     "                resource_id=j[\"vm\"], action=\"isolate_vm\", escalation_type=SOURCE_TYPE,\n",
     "                resource_id=j[\"vm\"], action=\"isolate_vm\", escalation_type=escalations.EXECUTED_TYPE,\n"),
    ("M7370", "the card of the source not approvable: the path of every held card refuses it (SEC2d)",
     "eregion_core/action_queue.py",
     "APPROVABLE_TYPES |= {\"lateral_source\"}\n", ""),
    ("M7371", "an appliance's address taken for the source VM: the hub isolated, the VM behind it left (SEC2d)", LAT,
     "    if held & _forwarders(snap):\n        return \"\", f\"adresse d'une appliance",
     "    if False:\n        return \"\", f\"adresse d'une appliance"),
    ("M7372", "a source VM proposed on a client's list that can't be trusted (SEC2d, decision 4)", LAT,
     "    if degraded:\n        return \"\", f\"liste du réseau du client non fiable",
     "    if False:\n        return \"\", f\"liste du réseau du client non fiable"),
    ("M7373", "decide's guard lets a block of the client's network go once the switch is on (SEC2d, SEC2b)", POL,
     "    if not p.entry:\n        return \"\"\n",
     "    if not p.entry or (p.layer == CLIENT and __import__(\"glorfindel.lateral\").lateral.on()):\n"
     "        return \"\"\n"),
    ("M7374", "the switch of the lateral movement never said loud at the watch's start (SEC2d)", LAT,
     "    out.append((\"strong\", f\"Mouvement latéral vu", "    out.append((\"info\", f\"Mouvement latéral vu"),
    ("M7375", "the card of a failed lift left open once its episode is replaced (SEC2d, the review of SEC2c)", EXP,
     "    _close_replaced(entries)\n", ""),
    ("M7376", "the connector blocks an address of the client's network once the switch is on (SEC2d, SEC2b)", POL,
     "    if held.layer == CLIENT:\n        raise ProtectedAddressError(",
     "    if held.layer == CLIENT and not __import__(\"glorfindel.lateral\").lateral.on():\n"
     "        raise ProtectedAddressError("),
    ("M7377", "a VM Glorfindel does not watch proposed as the source (SEC2d)", LAT,
     "    if vm not in watched:\n        return \"\", f\"tenue par",
     "    if False:\n        return \"\", f\"tenue par"),
    ("M7378", "the card of a failed lift closed on its own episode: a block still failing said nowhere (SEC2d, the "
     "review of SEC2c)", EXP,
     "        if entry is not None and said_at is not None and marked_at is not None and marked_at > said_at:\n",
     "        if entry is not None:\n"),
    ("M7379", "the variant of ssh-brute-force loaded over a base that is not the shipped one (SEC2d)", LAT,
     "        if Path(path).resolve() != shipped_rules_path().resolve():\n            return base, []\n",
     "        if False:\n            return base, []\n"),
]

TESTS = {f"M{n}": _T for n in range(7360, 7380)}
