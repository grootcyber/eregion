"""I3W (#778): a perimeter block whose pair is gone at its check is never said `blocked`, nor silent of it.
Found by I3Q's second review. On the placements' path of `verify_block_ip`, the perimeter pair gone while
nothing else is went in `held_missing`: the VM held by its own block, the check `True`, the block
`blocked`, « denied for ALL VMs on the subnet », the subnet's other VMs reached. In the branch `False` the
pair went unsaid beside `uncovered_nics` (the review's finding 1), and in the branch `None` the check
returned without it. Now the check says the pair apart, in every branch (`perimeter_gone`, read by the block
alone), and the block says it (`verify_block._say_gone`): `blocked_partial`, `missing_rules` the pair, its
note never « denied for ALL VMs ». The NICs the check names in `missing_rules` (no rule of the block on
them) are said apart (`missing_nics`): « Rules of this block missing on Azure » named a NIC as a rule (the
review's finding 2). The drift card says « reste bloquée » of the VM, the pair no longer holding on the
subnet's other VMs.
M5088: the defect back; M5089: a fix of the branch `False` alone; M5090: the status `blocked` with the pair
said gone; M5091: « denied for ALL VMs » kept; M5092: the branch `None` silent again; M5093: the pair read
gone on a guess (its listing unread, A0); M5094: a NIC named as a rule again; M5095: the console's
promotion window silent of the pair; M5096: the perimeter alone's pair gone, the head kept; M5097: the drift card
silent of the subnet.
The review (round 1): the oracle excused every pair said gone — a block that lost its own pair passed. It
excuses now what a third party the test sets acting took off (`world_deleted`), or a fault drawn, way by way.
M5105, M5106: the pair, or its `-out`, never written; M5107, M5108: half the pair said as the whole, by the
block and by the card; M5109: the pair unread, « denied for ALL VMs » kept.
Measured by the sequences frozen in tests/unit/test_invariant_regressions.py (the machine's oracle and the
connector) and tests/unit/test_console_blocks.py: the machine draws no third party deleting a rule between a
block's write and its check."""
_BLK = "glorfindel/providers/azure/blocks.py"
_VBL = "glorfindel/providers/azure/verify_block.py"
_SAY = "glorfindel/reassert_said.py"
_API = "eregion_console/api.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_MACHINE = f"{_REG}test_a_perimeter_whose_pair_is_gone_at_its_check_judged_by_the_machine"
_SAID = f"{_REG}test_a_perimeter_whose_pair_is_gone_at_its_check_is_never_said_blocked"
_NONE = f"{_REG}test_a_perimeter_whose_pair_is_gone_at_an_unconcluded_check_says_it_gone"
_PROMOTED = f"{_REG}test_a_promotion_whose_pair_is_gone_names_the_nic_apart_from_the_rules"
_ALONE = f"{_REG}test_a_perimeter_whose_pair_is_gone_at_its_check_says_the_nics_off_it_and_the_rules_gone"
_CONSOLE = "tests/unit/test_console_blocks.py::test_a_promotion_says_its_pair_gone_beside_a_nic_uncovered"
_PAIR = '                    pair = {"perimeter_gone": names, "perimeter_nsg": perimeter[1]}\n'
_READ = "        pair = [str(n) for n in check.get(\"perimeter_gone\") or []]\n"
_HEAD = ('        if pair:\n'
         '            out["note"] = (f"NSG {out[\'nsg\']} — perimeter block written, then read missing or altered '
         'on Azure "\n')
_RULES = "        rules = [str(n) for n in lost if str(n) not in nics and str(n) not in pair]\n"
_GONE = ('                if st in ("absent", "altered"):\n'
         '                    (missing if missing else held_missing).extend(names)\n')
_OWN_PAIR = f"{_REG}test_a_perimeter_block_beside_a_vm_block_is_judged_on_its_own_pair"
_HALF = f"{_REG}test_half_a_perimeter_pair_gone_is_said_the_way_it_no_longer_denies"
_WRITE = ('        self._put_deny_rule(nsg_rg, nsg_name, rule_name, "Inbound", priority["inbound"], src=ip, dst="*")\n'
          '        self._put_deny_rule(nsg_rg, nsg_name, f"{rule_name}-out", "Outbound", priority["outbound"],\n'
          '                            src="*", dst=ip)\n')
_WAYS = '    return "" if out == {True, False} else " outbound" if out == {True} else " inbound"\n'
_WAY = '    return "" if out == {True, False} else " en sortie" if out == {True} else " en entrée"\n'

MUTANTS = [
    ("M5088", "a perimeter block whose pair is gone at a check that reads the VM held by its own block says "
              "`blocked`, « denied for ALL VMs on the subnet », the other VMs reached (I3W, the defect back)",
     _VBL, _PAIR, "                    pass\n"),
    ("M5089", "a perimeter block says its pair gone when its check concludes False alone: `blocked` when the "
              "VM is held by its own block (I3W, a fix that weakens)",
     _VBL, _READ, _READ.replace("or []]\n", "or []] if check.get(\"verified\") is False else []\n")),
    ("M5090", "a perimeter block says its pair gone and the status `blocked` (I3W, the status)",
     _VBL, '        out["status"] = "blocked_partial"\n', ""),
    ("M5091", "a perimeter block whose pair is gone still says « denied for ALL VMs on the subnet » (I3W, "
              "the note)",
     _VBL, _HEAD, _HEAD.replace("        if pair:\n", "        if False:\n")),
    ("M5092", "a perimeter block whose pair is gone at a check that couldn't list the VM's NICs says nothing "
              "of it (I3W, the branch None)",
     _VBL, '                return {"verified": None, "method": "nsg_check", **pair,\n',
     '                return {"verified": None, "method": "nsg_check",\n'),
    ("M5093", "a perimeter pair whose listing couldn't be read said gone: put back and said on a guess (I3W, "
              "A0)",
     _VBL, _GONE, _GONE.replace('("absent", "altered")', '("absent", "altered", "unknown")')),
    ("M5094", "a perimeter block names a NIC without a rule of the block as a rule: « Rules of this block "
              "missing on Azure: db-nic-0 » (I3W, I3Q's review, finding 2)",
     _VBL, _RULES, "        rules = [str(n) for n in lost if str(n) not in pair]\n"),
    ("M5095", "the console's promotion window says a NIC uncovered and drops the pair gone beside it (I3W, "
              "the reader of the shape)",
     _API, '    if result.get("missing_rules"):\n', '    if False:\n'),
    ("M5096", "a perimeter block alone whose pair is gone at its check says « denied for ALL VMs on the "
              "subnet » beside the rules missing (I3W, the path of a perimeter alone)",
     _VBL, '                    **({"perimeter_gone": missing, "perimeter_nsg": nsg_name} if entry.get("scoped") '
           'is False else {}),\n', ""),
    ("M5097", "a drift card says « l'IP reste bloquée » of a VM whose perimeter pair is gone, silent of the "
              "subnet's other VMs (I3W, the drift card)",
     _SAY, '                  ) if v.get("perimeter_gone") else ""\n', '                  ) if False else ""\n'),
    # I3W's review (round 1).
    ("M5105", "a perimeter block that never writes its pair, its check reading it « missing », says « read "
              "missing at its check »: excused by an oracle that excused every pair said gone (I3W's review)",
     _BLK, _WRITE, ""),
    ("M5106", "a perimeter block that never writes its `-out`: the subnet's VMs reached outbound, half the pair "
              "said gone of itself (I3W's review)",
     _BLK, _WRITE, _WRITE.split("\n", 1)[0] + "\n"),
    ("M5107", "half a perimeter pair gone said « no longer denied by it »: the other way still denied to every "
              "VM on the subnet (I3W's review, finding 2)",
     _VBL, _WAYS, '    return ""\n'),
    ("M5108", "the drift card of half a perimeter pair gone says « ne tient plus », the way lost dropped (I3W's "
              "review, finding 2)",
     _SAY, _WAY, '    return ""\n'),
    ("M5109", "a perimeter block whose pair couldn't be read at its check keeps « denied for ALL VMs on the "
              "subnet » (I3W's review, finding 3)",
     _VBL, '        elif unread:\n            out["pair_unread"] = unread\n',
     '        elif False:\n            out["pair_unread"] = unread\n'),
]
TESTS = {
    "M5088": f"{_MACHINE} {_SAID} {_NONE}",
    "M5089": f"{_MACHINE} {_SAID}",
    "M5090": f"{_MACHINE} {_SAID}",
    "M5091": f"{_SAID} {_NONE}",
    "M5092": _NONE,
    "M5093": _NONE,
    "M5094": _PROMOTED,
    "M5095": _CONSOLE,
    "M5096": _ALONE,
    "M5097": _SAID,
    "M5105": f"{_OWN_PAIR} {_MACHINE}",
    "M5106": f"{_OWN_PAIR} {_MACHINE}",
    "M5107": _HALF,
    "M5108": _HALF,
    "M5109": _NONE,
}
