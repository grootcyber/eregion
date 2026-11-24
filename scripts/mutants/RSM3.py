"""RSM3 (#1036, #1057): what the reassertion says of what is no longer there (docs/design/reaffirmation.md §3.5,
§3.6, E7, E8). A perimeter pair on an NSG that governs none of the VM's NICs is gone for where it lies, said on a
card of the block, never put back; a VM deleted has its own card (Q6), nothing written for it. Each mutant puts
back a way it could go wrong: M7057 reads a merged entry's pair on an NSG taken off its subnet as held (RSM2a's
night n° 50: `True`, said nowhere); M7058 the same on the path of a perimeter block alone (« contourné » with an
allow there, #1057; « autre subnet » without, M5); M7059 asks the NSG only after the precedence (« contourné »
back); M7060 and M7492 put the pair back on the NSG the subnet carries now, the first time and the second; M7493
reads an unreadable attachment (the NIC's subnet a 429) as the NSG taken off; M7494 says « non vérifiée » of a VM
gone again; M7495 tries a put-back for a VM gone, its rules gone. Measured by tests/unit/test_reassert_gone.py and
the two sequences of tests/unit/test_invariant_regressions.py once frozen in `xfail` (#1057, night n° 50)."""
_PER = "glorfindel/providers/azure/perimeter.py"
_VB = "glorfindel/providers/azure/verify_block.py"
_R = "glorfindel/reassert.py"
_RP = "glorfindel/reassert_perimeters.py"
_G = "glorfindel/reassert_gone.py"
_GONE = "tests/unit/test_reassert_gone.py::"
_REG = "tests/unit/test_invariant_regressions.py::"

_AT_HOME = ('            reach: dict = {"off": []}        # its NSG off the VM\'s subnet: gone there, never bypassed '
            '(RSM3, #1057)\n'
            '            if entry.get("scoped") is False and (stop := self._pair_at_home(rg, vm_name, nsg_rg, nsg_name, '
            'reach)):\n'
            '                return stop\n')
_BYPASSED = ("                if self._threat_open(shadowed):\n"
             "                    return self._block_bypassed(ip, shadowed)\n")

MUTANTS = [
    ("M7057", "a merged entry's perimeter pair on an NSG taken off its subnet read held: the VM held by its own "
              "block, the check `True`, the subnet's other VMs reached, said nowhere (RSM3, night n° 50)",
     _PER,
     ('        if any(home in {(v["nsg_rg"].lower(), v["nsg_name"].lower()) for v in self._nic_nsg_views(t)\n'
      '                        if v.get("nsg_rg")} for t in targets.values()):\n'
      "            return {}\n"),
     "        if True:\n            return {}\n"),
    ("M7058", "a perimeter block alone on an NSG taken off its subnet read as before: « contourné » by an allow "
              "there (#1057), « ne couvre pas … (autre subnet) » without one (M5, #1036) (RSM3)",
     _PER, '        if not seen or len(reach["off"]) < len(seen):\n            return {}\n',
     "        if True:\n            return {}\n"),
    ("M7059", "the pair's NSG asked only after its precedence: an allow on the NSG taken off said « contourné » "
              "again, never gone (RSM3, #1057)",
     _VB, (_AT_HOME, _BYPASSED),
     ('            reach: dict = {"off": []}\n',
      _BYPASSED + '                if entry.get("scoped") is False and (stop := self._pair_at_home(rg, vm_name, '
      'nsg_rg, nsg_name, reach)):\n                    return stop\n')),
    ("M7060", "a pair on an NSG taken off its subnet put back by the first time, the VM's rules gone too: written "
              "on the NSG the subnet carries now, without the operator's decision (RSM3, E7)",
     _RP, '    if verification.get("perimeter_off"):\n        return False\n', ""),
    ("M7492", "a pair on an NSG taken off its subnet put back by the second time with the VM's rules: written on "
              "the NSG the subnet carries now (RSM3, E7)",
     _R, '    scopes = [s for s in scopes if s != "subnet"] if said.get("perimeter_off") else scopes\n', ""),
    ("M7493", "an unreadable attachment read gone: the NIC's subnet a 429, the pair said off its subnet, a card "
              "that claims what was never read (RSM3, A0)",
     _PER, '        if any(t.get("subnet_unreadable") for t in targets.values()):\n',
     "        if False:\n"),
    ("M7494", "a VM deleted said « non vérifiée » again, « (ResourceNotFound) », never that it no longer exists "
              "(RSM3, Q6)",
     _G, "    except Exception:\n        if _is_gone(connector, rid):\n            return dict(GONE)\n        raise\n",
     "    except Exception:\n        raise\n"),
    ("M7495", "a put-back tried for a VM deleted, its rules gone: « le reposer a échoué : (ResourceNotFound) » "
              "(RSM3, Q6)",
     _G,
     '    unsure = verification.get("verified") is None or (_missing(verification) and '
     'verification.get("nics_unread"))\n',
     '    unsure = verification.get("verified") is None\n'),
]
TESTS = {
    "M7057": (f"{_REG}test_a_merged_perimeter_on_an_nsg_taken_off_its_subnet_is_said "
              f"{_GONE}test_a_merged_perimeter_on_an_nsg_taken_off_is_said_and_closes_when_it_is_back"),
    "M7058": (f"{_REG}test_a_perimeter_on_an_nsg_taken_off_its_subnet_is_not_said_bypassed "
              f"{_GONE}test_a_perimeter_alone_on_an_nsg_taken_off_is_said_gone_never_bypassed_nor_another_subnet"),
    "M7059": f"{_REG}test_a_perimeter_on_an_nsg_taken_off_its_subnet_is_not_said_bypassed",
    "M7060": f"{_GONE}test_a_merged_entry_its_rules_gone_and_its_pair_off_puts_back_its_own_rules_only",
    "M7492": f"{_GONE}test_a_merged_entry_its_rules_gone_and_its_pair_off_puts_back_its_own_rules_only",
    "M7493": f"{_GONE}test_an_unreadable_attachment_is_never_read_gone_nor_held",
    "M7494": f"{_GONE}test_an_isolated_vm_deleted_has_its_own_card_closed_at_the_release",
    "M7495": f"{_GONE}test_a_blocked_vm_deleted_has_its_own_card_and_nothing_is_written",
}
