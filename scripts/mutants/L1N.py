"""L1N (#795): a block named gone behind a quarantine that lets the attacker in, its rules deleted since. The
night « Invariants (deep) » of 13/11, red on ubuntu (Db--01) and macOS (web): the quarantine's investigation
access is the attacker's own IP, so it does not cut it off, and the block's rules, on the NIC's own NSG off
the NIC, were named gone « (nsg-… ne gouverne plus …) » without that NSG being listed — nothing of them in
`rules_seen` (L1G). The card acknowledged, a `terraform apply` deleting them read « no worse » by the names
alone: the pass said nothing, and the release put the NSG back without the block. The product's defect, not
the oracle's; not a regression (90f00faf fails the same). M5195: the defect back; M5196: the NSG read, its
listing not kept for `rules_seen`; M5197–M5198: read on one side only (in quarantine, or not); M5199: a fix
that hardens wrong (that NSG unread makes the NIC unknown, though it governs nothing of it now); M5200: an
NSG unread read as empty, its rules said deleted on a guess (A0). Measured by the frozen sequences and the
connector's tests (tests/unit/test_invariant_regressions.py)."""
_VBL = "glorfindel/providers/azure/verify_block.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_FROZEN = f"{_REG}test_a_block_named_gone_off_its_nic_is_said_again_once_its_rules_are_deleted"
_READ = f"{_REG}test_a_rule_named_gone_off_its_nic_is_read_where_it_lies"
_UNREAD = f"{_REG}test_a_rule_named_gone_off_its_nic_unread_is_left_out_as_before"
_PASS = f"{_REG}test_a_block_named_gone_off_its_nic_acknowledged_is_said_again_when_its_rules_are_deleted"
_LOOP = "                        for p in off:\n"
_LIST = '                            self._list_rules(cache, p["nsg_rg"], p["nsg_name"])\n'

MUTANTS = [
    ("M5195", "a block's rules named gone because their NSG no longer governs the NIC are not read there: "
              "acknowledged, then deleted, read « no worse » by the names alone, never said (L1N, the defect back)",
     _VBL, _LOOP + _LIST, ""),
    ("M5196", "the NSG off the NIC listed, its listing not kept for `rules_seen`: the deletion since the card "
              "read « no worse » (L1N)",
     _VBL, _LIST, '                            self._list_rules({}, p["nsg_rg"], p["nsg_name"])\n'),
    ("M5197", "the NSG off the NIC read only when the NIC is in quarantine: one detached, its rules deleted "
              "since the card, never said (L1N)",
     _VBL, _LOOP, '                        for p in (off if t0.get("quarantine") else []):\n'),
    ("M5198", "the NSG off the NIC read only when the NIC is not in quarantine: behind a quarantine that lets "
              "the attacker in, its rules deleted since the card, never said (L1N)",
     _VBL, _LOOP, '                        for p in (off if not t0.get("quarantine") else []):\n'),
    ("M5199", "the NSG off the NIC unread makes the NIC unknown: the verdict changed by a read of an NSG that "
              "governs nothing of the NIC now (L1N, a fix that hardens wrong)",
     _VBL, _LOOP + _LIST,
     '                        if any(self._list_rules(cache, p["nsg_rg"], p["nsg_name"]) is None for p in off):\n'
     '                            unread.append(f\'{t0["nic_short"]}: NSG illisible\')\n'
     '                            undecided.append(t0["nic_short"])\n'
     '                            continue\n'),
    ("M5200", "an NSG unread read as empty in `rules_seen`: its rules said deleted on a guess, a card said again "
              "on nothing read (L1N, A0)",
     _VBL, "            rules = cache.get((rg, nsg)) if rg and nsg and rule else None\n",
     "            rules = (cache.get((rg, nsg)) or []) if rg and nsg and rule else None\n"),
]
TESTS = {
    "M5195": f"{_FROZEN} {_READ} {_PASS}",
    "M5196": f"{_FROZEN} {_READ} {_PASS}",
    "M5197": f"{_FROZEN} {_READ} {_PASS}",
    "M5198": f"{_FROZEN} {_READ} {_PASS}",
    "M5199": f"{_UNREAD} {_FROZEN}",
    "M5200": f"{_UNREAD} {_FROZEN}",
}
