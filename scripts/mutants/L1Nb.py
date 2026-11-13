"""L1Nb (#802): L1N's proofs completed, the product untouched. L1N (#795) reads, for `rules_seen` only, the NSGs
of a NIC's placements that no longer govern it (behind a quarantine that lets the attacker in, or taken off
by their owner); its frozen cases had one such placement alone, and froze the 429 behind the quarantine only.
M5250–M5251: only the first (`off[:1]`), or only the last, of two NSGs off the NIC read — the other's
deletion since the acknowledged card read « no worse » by the names alone; M5252: the NSG off a detached NIC
unread makes the NIC unknown (L1N's M5199, on the side its frozen 429 did not see); M5253: unread there, read
as empty — its rules said deleted on a guess (A0); M5254: the first NSG unread, the next never read. Measured
by the connector's and the reassertion's frozen cases (tests/unit/test_invariant_regressions.py)."""
_VBL = "glorfindel/providers/azure/verify_block.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_BOTH = f"{_REG}test_two_placements_off_its_nic_are_both_read_where_they_lie"
_ONE_UNREAD = f"{_REG}test_two_placements_off_its_nic_one_unread_the_other_still_read"
_PASS = f"{_REG}test_two_placements_off_its_nic_acknowledged_are_said_again_when_either_is_deleted"
_UNREAD = f"{_REG}test_a_rule_named_gone_off_its_nic_unread_is_left_out_as_before"
_LOOP = "                        for p in off:\n"
_LIST = '                            self._list_rules(cache, p["nsg_rg"], p["nsg_name"])\n'

MUTANTS = [
    ("M5250", "of two NSGs off the NIC, only the first read (`off[:1]`): the other's rules deleted since the "
              "acknowledged card, read « no worse » by the names alone, never said (L1Nb)",
     _VBL, _LOOP, "                        for p in off[:1]:\n"),
    ("M5251", "of two NSGs off the NIC, only the last read: the first's rules deleted since the acknowledged "
              "card, never said (L1Nb)",
     _VBL, _LOOP, "                        for p in off[-1:]:\n"),
    ("M5252", "an NSG off a detached NIC unread makes the NIC unknown: the verdict changed by a read of an NSG "
              "that governs nothing of the NIC now, out of quarantine only (L1Nb, L1N's M5199 detached)",
     _VBL, _LOOP + _LIST,
     '                        if not t0.get("quarantine") and None in [\n'
     '                                self._list_rules(cache, p["nsg_rg"], p["nsg_name"]) for p in off]:\n'
     '                            unread.append(f\'{t0["nic_short"]}: NSG illisible\')\n'
     '                            undecided.append(t0["nic_short"])\n'
     '                            continue\n' + _LOOP + _LIST),
    ("M5253", "an NSG off a detached NIC unread, read as empty: its rules said deleted on a guess, a card said "
              "again on nothing read (L1Nb, A0)",
     _VBL, _LIST,
     '                            if self._list_rules(cache, p["nsg_rg"], p["nsg_name"]) is None and not t0.get("quarantine"):\n'
     '                                cache[(p["nsg_rg"], p["nsg_name"])] = []\n'),
    ("M5254", "the first NSG off the NIC unread, the next never read: its rules deleted since the card, never "
              "said (L1Nb)",
     _VBL, _LIST,
     '                            if self._list_rules(cache, p["nsg_rg"], p["nsg_name"]) is None:\n'
     '                                break\n'),
]
TESTS = {
    "M5250": f"{_BOTH} {_PASS}",
    "M5251": f"{_BOTH} {_PASS}",
    "M5252": f"{_UNREAD} {_ONE_UNREAD}",
    "M5253": f"{_UNREAD} {_ONE_UNREAD}",
    "M5254": f"{_ONE_UNREAD}",
}
