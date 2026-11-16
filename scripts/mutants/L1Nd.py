"""L1Nd (#795): a block gone from Azure behind a quarantine whose verdict is unknown (the config unread). The
night « Invariants (deep) » of 15/11, red on macOS (api), replayed the same on `main` 4d351ef5: api blocked,
isolated in the quarantine, its own NSG — where the block's rules lay, off the NIC — deleted by the customer,
then the configuration unreadable. Whether the quarantine cuts the attacker off was unknown, and the block's
verification said « non vérifiable » alone, its rules off the NIC never read: an « unverified » card, the
disappearance unsaid while the config stayed unread. The product's defect, not the oracle's; not a regression
(v0.5.0 fails the same); the branch sibling of L1N's. M5477: the defect back; M5478: the rules gone held, not
said (the verdict « non vérifiable » again); M5479: a deny turned off the NIC not counted; M5480: an NSG
unread read absent (A0); M5481: the NIC said open, though the quarantine may cut it off; M5482–M5483: one
placement of two read; M5484: the NIC dropped from the unknown once a rule is said gone. Measured by the
frozen sequences and the connector's tests (tests/unit/test_invariant_regressions.py)."""
_VBL = "glorfindel/providers/azure/verify_block.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_FOUND = f"{_REG}test_a_block_gone_behind_a_quarantine_unjudged_is_said_gone"
_REDUCED = f"{_REG}test_a_block_gone_behind_a_quarantine_unjudged_is_said_gone_reduced"
_READ = f"{_REG}test_a_block_off_its_nic_in_an_unjudged_quarantine_is_said_gone_the_nic_unknown"
_UNREAD = f"{_REG}test_a_block_off_its_nic_in_an_unjudged_quarantine_unread_stays_unknown"
_PASS = f"{_REG}test_a_block_gone_in_an_unjudged_quarantine_is_said_once_and_not_again_once_judged"
_TWO = f"{_REG}test_two_placements_off_their_nic_in_an_unjudged_quarantine_each_read"
_LOOP = "                            for placement in off:\n"
_READ_PAIR = (
    "                                st, names = self._block_pair_state(\n"
    '                                    cache, placement["nsg_rg"], placement["nsg_name"], placement["rule"], ip,\n'
    '                                    own_ips or placement.get("ips") or None)\n')
_IF = '                                if st in ("absent", "altered"):\n'
_GONE = "                                    missing += names\n"
_UNKNOWN = ("                            unread.append(f'{t0[\"nic_short\"]}: {t0[\"quarantine\"][\"nsg_name\"]}')\n"
            '                            undecided.append(t0["nic_short"])\n')

MUTANTS = [
    ("M5477", "the block's rules off a NIC in a quarantine whose verdict is unknown are not read: gone, the "
              "verification says « non vérifiable » alone, and the disappearance goes unsaid (L1Nd, the defect back)",
     _VBL, _LOOP + _READ_PAIR + _IF + _GONE, ""),
    ("M5478", "the rules off the NIC, read gone, held and not said: the verdict « non vérifiable » again, an "
              "« unverified » card, the disappearance unsaid (L1Nd)",
     _VBL, _IF + _GONE, _IF + "                                    held_missing += names\n"),
    ("M5479", "a deny off the NIC turned into an allow (altered) not counted: put back like a rule gone on "
              "every other path, said nowhere here (L1Nd)",
     _VBL, _IF + _GONE, '                                if st == "absent":\n' + _GONE),
    ("M5480", "the NSG off the NIC unread (a 429) read as gone: its rules said deleted on a guess (L1Nd, A0)",
     _VBL, _IF + _GONE, '                                if st in ("absent", "altered", "unknown"):\n' + _GONE),
    ("M5481", "the rules off the NIC said gone the NIC said open: « n'est plus bloquée », though the quarantine "
              "may cut the attacker off (L1Nd)",
     _VBL, _IF + _GONE, _IF + "                                    _lost(t0, names)\n"),
    ("M5482", "only the first placement off the NIC read: the other NSG's pair deleted goes unsaid (L1Nd)",
     _VBL, _LOOP, "                            for placement in off[:1]:\n"),
    ("M5483", "only the last placement off the NIC read: the other NSG's pair deleted goes unsaid (L1Nd)",
     _VBL, _LOOP, "                            for placement in off[-1:]:\n"),
    ("M5484", "a rule off the NIC said gone, the NIC dropped from the unknown: « l'IP n'est plus bloquée » said "
              "of a NIC the quarantine may still cut off (L1Nd)",
     _VBL, _GONE + _UNKNOWN,
     _GONE + "                            if not missing:\n"
     + "".join("    " + line + "\n" for line in _UNKNOWN.splitlines())),
]
TESTS = {
    "M5477": f"{_FOUND} {_REDUCED} {_READ} {_PASS}",
    "M5478": f"{_FOUND} {_REDUCED} {_READ} {_PASS}",
    "M5479": f"{_READ}",
    "M5480": f"{_UNREAD}",
    "M5481": f"{_READ} {_PASS}",
    "M5482": f"{_TWO}",
    "M5483": f"{_TWO}",
    "M5484": f"{_READ} {_PASS}",
}
