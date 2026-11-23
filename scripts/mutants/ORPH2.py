"""ORPH2 (#1113): an older version's isolation (the fixed names `glorfindel-isolation-deny-all` and `-out`)
left on an NSG that governs no NIC and no subnet — its state lost, the NIC taken off that NSG since — is said
by the watch's pass, one card per NSG, never taken off (SEC-H: the name alone proves nothing). The card is
said once; it closes when the rules are no longer on the NSG (proven by the listing, or a read by its id —
never by a listing that leaves the NSG out); put back on a NIC or a subnet, it is replaced by one that says
what the NSG governs now, once per state. M7206–M7218, measured by tests/unit/test_dormant_isolation.py
(M7216–M7218: the review of ORPH2).
"""
PASS = "glorfindel/dormant_isolations.py"
FIND = "glorfindel/providers/azure/dormant.py"
ORPH = "glorfindel/orphans.py"
_T = "tests/unit/test_dormant_isolation.py"

MUTANTS = [
    ("M7206", "the orphan sweep no longer runs the pass: the older isolation on an NSG that governs nothing "
              "said by nothing, as before ORPH2", ORPH,
     "    return say_dormant_isolations(connector, report, nsgs)\n",
     "    return report\n"),
    ("M7207", "a pair on an NSG that governs something said as dormant: a card for what the release and the "
              "reset of its VM judge, saying it governs nothing (ORPH2)", PASS,
     "        if said is None and sig[\"governed\"]:\n"
     "            continue                              # never said dormant: the paths of its VM judge it\n",
     ""),
    ("M7208", "said at every pass: the card bumped each minute, never « said once » (ORPH2)", PASS,
     "        if said is not None and {\"rules\": said.get(\"rules\"), \"governed\": said.get(\"governed\")} == sig:\n",
     "        if False:\n"),
    ("M7209", "an NSG a listing leaves out, read refused (403), taken for deleted: its card closed on what "
              "proves nothing (A0)", FIND,
     "            if _is_not_found(exc):\n"
     "                return {\"nsg_id\": nsg_id, \"gone\": True}\n",
     "            if True:\n"
     "                return {\"nsg_id\": nsg_id, \"gone\": True}\n"),
    ("M7210", "the card closed when the NSG governs a NIC again — silent exactly when the rules cut (ORPH2)", PASS,
     "        if e.get(\"gone\") or not e.get(\"rules\"):\n",
     "        if e.get(\"gone\") or not e.get(\"rules\") or e.get(\"nics\") or e.get(\"subnets\"):\n"),
    ("M7211", "an acknowledged card said again at the next pass: « said once » only while pending (ORPH2)", PASS,
     "        if said is not None and {\"rules\": said.get(\"rules\"), \"governed\": said.get(\"governed\")} == sig:\n",
     "        if said is not None and {\"rules\": said.get(\"rules\"), \"governed\": said.get(\"governed\")} == sig \\\n"
     "                and said[\"card\"] in pending:\n"),
    ("M7212", "the access not read: a fixed name turned into an allow, which cuts nothing, said as a deny "
              "(ORPH2)", FIND,
     "                   if _rule_name(r).lower() in fixed and _enum_text(getattr(r, \"access\", \"\")) == \"deny\"),\n",
     "                   if _rule_name(r).lower() in fixed),\n"),
    ("M7213", "the subnets not read: an NSG put on a subnet since, that governs every NIC there, said as "
              "governing nothing (ORPH2)", FIND,
     "            \"subnets\": _attached_ids(getattr(nsg, \"subnets\", None))}\n",
     "            \"subnets\": []}\n"),
    ("M7214", "a said NSG of another subscription read here by its name: its homonym in this one decides "
              "its card (ORPH2)", FIND,
     "        if not target or target.lower() != (self._subscription_id or \"\").lower():\n",
     "        if not target:\n"),
    ("M7215", "the card replaced without closing it: folded into the pending one, its text « governs "
              "nothing » kept while the NSG cuts a NIC (ORPH2)", PASS,
     "            replaces=takes,\n",
     "            replaces=None,\n"),
    ("M7216", "the mark forgotten before the card is closed: the closure refused (a full disk), the card "
              "pending for ever with a text no longer true (the review of ORPH2)", PASS,
     "                if said[\"card\"] in pending:       # closed first: refused, the mark stays, the next pass retries\n",
     "                del alerts[k]\n"
     "                if said[\"card\"] in pending:       # closed first: refused, the mark stays, the next pass retries\n"),
    ("M7217", "an NSG that can't be read again skipped in silence: its card kept, nothing said of why (the "
              "review of ORPH2)", PASS,
     "            report.append({\"kind\": TYPE, \"vm\": _short(k), \"outcome\": \"unread\", \"detail\": (\n",
     "            [].append({\"kind\": TYPE, \"vm\": _short(k), \"outcome\": \"unread\", \"detail\": (\n"),
    ("M7218", "what the NSG governs kept as a yes or no: moved from NIC A to NIC B, or given a subnet, its "
              "card still names A (the review of ORPH2)", PASS,
     "            \"governed\": sorted(i.lower() for i in list(e[\"nics\"]) + list(e[\"subnets\"]))}\n",
     "            \"governed\": [\"*\"] if (e[\"nics\"] or e[\"subnets\"]) else []}\n"),
]

TESTS = {
    "M7206": f"{_T}::test_the_narrow_world_is_said_once_and_nothing_is_taken_off",
    "M7207": f"{_T}::test_a_pair_on_an_nsg_that_governs_something_is_left_to_its_paths",
    "M7208": f"{_T}::test_the_narrow_world_is_said_once_and_nothing_is_taken_off",
    "M7209": f"{_T}::test_an_nsg_the_listing_leaves_out_keeps_its_card",
    "M7210": f"{_T}::test_put_back_on_a_nic_the_card_is_replaced_by_what_it_cuts",
    "M7211": f"{_T}::test_an_acknowledged_card_stays_closed",
    "M7212": f"{_T}::test_only_the_fixed_names_denied_count",
    "M7213": f"{_T}::test_an_nsg_on_a_subnet_only_governs_something",
    "M7214": f"{_T}::test_a_said_nsg_of_another_subscription_is_never_read_here",
    "M7215": f"{_T}::test_put_back_on_a_nic_the_card_is_replaced_by_what_it_cuts",
    "M7216": f"{_T}::test_a_closure_refused_is_tried_again",
    "M7217": f"{_T}::test_an_nsg_the_listing_leaves_out_keeps_its_card",
    "M7218": f"{_T}::test_a_card_follows_what_the_nsg_governs",
}
