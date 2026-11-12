"""I3N (#746): a perimeter block whose verification a 429 cut short. The night « Invariants (deep) »
of 12/11, red on macOS (a draw of that system's, not its case-insensitive disk): Db--01's primary
NIC on the data subnet, web blocked on the app subnet, then Db--01 on its own, the read of its
verification answered 429. The verification not concluded (`verified: None`), the block kept every
NIC off its perimeter « not behind it, the IP still reaches them » (`uncovered_nics`) — db-nic-0,
that web's perimeter cuts off, read of none. The product's defect, not the oracle's: it is now
`nics_unread`, `blocked_partial`. M4860: the defect back; M4861: a fix that weakens (cleared, the
status `blocked` on an unknown); M4862: an excuse for the NICs read held alone (a 429 before any
was read keeps them all); M4863–M4864: the verification that raises read as verified, or as a
proof of « uncovered »; M4865: its cause dropped. Two neighbors, found looking for them: a NIC
whose subnet couldn't be read, its block's placement on that subnet's NSG, read « ne gouverne
plus » by verify_block_ip (M4866; M4868, the other side: taken for blocked), and « no » by
_perimeter_holds (M4867). Measured by the frozen sequences (tests/unit/test_invariant_regressions.py):
the machine draws a data-primary world, another perimeter and a 429 on one of eight reads of one
call too rarely."""
_BLK = "glorfindel/providers/azure/blocks.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_FOUND = f"{_REG}test_a_perimeter_block_a_429_cut_short_never_says_reached_a_nic_another_perimeter_cuts_off"
_MACHINE = f"{_REG}test_a_perimeter_block_whose_verification_is_cut_short_is_judged_by_the_machine"
_SAID = f"{_REG}test_a_perimeter_block_whose_verification_is_cut_short_says_its_nics_unread"
_RAISES = f"{_REG}test_a_perimeter_block_whose_verification_raises_says_its_nics_unread"
_NONE = ("                uncovered = []\n"
         '                unread = unread or check.get("error") or "illisible"\n')
_EXCEPT = '                check = {"verified": None, "error": _first_line(exc)}\n'
_VBL = "glorfindel/providers/azure/verify_block.py"
_PER = "glorfindel/providers/azure/perimeter.py"
_UNSURE = ("                    unsure = [f'{p[\"rule\"]} ({p[\"nsg_name\"]})' for p in off] "
           "if t0.get(\"subnet_unreadable\") else []\n")
_MERGED = (f"{_REG}test_a_merged_block_never_reads_a_429_on_a_subnet_as_an_nsg_that_no_longer_governs "
           f"{_REG}test_a_merged_block_whose_nic_subnet_is_unread_says_it_unknown")

MUTANTS = [
    ("M4860", "a perimeter block whose verification can't conclude names every NIC off it uncovered, « the "
              "IP still reaches them » — one another perimeter cuts off, read of none (I3N, the defect back)",
     _BLK, _NONE, '                unread = unread or check.get("error") or "illisible"\n'),
    ("M4861", "a perimeter block whose verification can't conclude says its NICs off it nothing: `blocked` "
              "on an unknown, a NIC nothing cuts off open (I3N, a fix that weakens)",
     _BLK, _NONE, "                uncovered = []\n"),
    ("M4862", "a perimeter block whose verification can't conclude excuses only the NICs it read held: a 429 "
              "before any was read keeps them all « uncovered » (I3N, a narrower excuse)",
     _BLK, _NONE,
     '                uncovered = [n for n in uncovered if n not in (check.get("held_by_perimeter") or [])]\n'
     '                unread = unread or check.get("error") or "illisible"\n'),
    ("M4863", "a perimeter block whose verification raises reads it as verified: `blocked` on an unknown "
              "(I3N, the other way of not concluding)",
     _BLK, _EXCEPT, '                check = {"verified": True}\n'),
    ("M4864", "a perimeter block whose verification raises reads it as a proof against its NICs: every NIC "
              "off it « uncovered » (I3N, the defect back by the exception)",
     _BLK, _EXCEPT, '                check = {"verified": False, "error": _first_line(exc)}\n'),
    ("M4865", "a perimeter block whose verification can't conclude says its NICs unread without why: the "
              "429 dropped (I3N)",
     _BLK, _NONE, "                uncovered = []\n"
                  '                unread = unread or "illisible"\n'),
    ("M4866", "a block's verification reads a NIC whose subnet it couldn't read as off the NSG its block "
              "lies on: « ne gouverne plus », a rule missing, the NIC open behind two blocks of ours (I3N's "
              "neighbor, in verify_block_ip)",
     _VBL, _UNSURE, "                    unsure = []\n"),
    ("M4867", "a NIC whose subnet couldn't be read is read off any perimeter: « no », the NIC said open "
              "behind one (I3N's neighbor, in _perimeter_holds)",
     _PER, '        return "unknown" if out == "no" and t0.get("subnet_unreadable") else out\n',
     "        return out\n"),
    ("M4868", "a NIC whose subnet couldn't be read, its block's placement off its views, taken for blocked: "
              "`blocked` on an unknown (I3N's neighbor, the other side, I3P)",
     _VBL, "                        unread.append(f'{t0[\"nic_short\"]}: NSG du subnet illisible')\n"
           "                        undecided.append(t0[\"nic_short\"])\n",
     "                        proven.append(t0[\"nic_short\"])\n"),
]
TESTS = {
    "M4860": f"tests/unit/test_invariants.py {_FOUND} {_SAID}",
    "M4861": f"{_MACHINE} {_SAID}",
    "M4862": f"{_FOUND} {_SAID}",
    "M4863": _RAISES,
    "M4864": _RAISES,
    "M4865": _RAISES,
    "M4866": _MERGED,
    "M4867": f"{_REG}test_a_perimeter_is_never_read_absent_on_a_nic_whose_subnet_was_not_read",
    "M4868": _MERGED,
}
