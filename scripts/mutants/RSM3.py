"""RSM3 (#1036, #1057): what the reassertion says of what is no longer there (docs/design/reaffirmation.md §3.5,
§3.6, E7, E8). A perimeter pair on an NSG that governs none of the VM's NICs is gone for where it lies, said on a
card of the block, never put back; a VM deleted has its own card (Q6), nothing written for it. Each mutant puts
back a way it could go wrong: M7057 reads a merged entry's pair on an NSG taken off its subnet as held (RSM2a's
night n° 50: `True`, said nowhere); M7058 the same on the path of a perimeter block alone (« contourné » with an
allow there, #1057; « autre subnet » without, M5); M7059 asks the NSG only after the precedence (« contourné »
back); M7060 and M7492 put the pair back on the NSG the subnet carries now, the first time and the second; M7493
reads an unreadable attachment (the NIC's subnet a 429) as the NSG taken off; M7494 says « non vérifiée » of a VM
gone again; M7495 tries a put-back for a VM gone, its rules gone. The review of RSM3 (25/11): M7496 reads the
pair « at home » while the VM's NICs are unread at the check; M7497 holds the put-back on `perimeter_off` alone, the
pair unread written on the subnet's NSG of the moment; M7498 and M7499 drop the write's own check of the NSG its
entry records, at the first time and at the second; M7500 refuses only a subnet without NSG; M7501 says the cause
« ôté ou remplacé » alone, the subnet's other VMs uncovered for sure; M7502 leaves a fresh block `blocked` on a
pair off; M7503 says the pair off only after a put-back's return; M7504 reads any 404 as a VM gone; M7505 has the
interface (AWS) say a VM gone. The second review (25/11): M7506 spends the put-back held back for want of a read
(a 429 that passed lost the pair for good); M7507 and M7508 spend it on a write refused unread, at the second time
and at the first; M7509 leaves the VM's put-back unspent while deferring (the third review: the VM's rules
put back at every pass); M7510 never puts the deferred pair back once it reads. The third review (25/11): M7511
keeps `pair_deferred` once the pair was tried; M7512 defers a pair read whole on its NSG; M7513 rewrites the VM's
rules with the deferred pair; M7514 puts the deferred pair back in human_only; M7515 says « ses règles réécrites
une fois » of the deferred pair put back alone. Measured by tests/unit/test_reassert_gone.py and
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
     ('                                    if v.get("nsg_rg")} for t in targets.values()):\n'
      "            return {}\n"),
     ('                                    if v.get("nsg_rg")} for t in targets.values()) or True:\n'
      "            return {}\n")),
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
     _RP, '    if _pair_not_home(verification):\n        return False\n', ""),
    ("M7492", "a pair on an NSG taken off its subnet put back by the second time with the VM's rules: written on "
              "the NSG the subnet carries now (RSM3, E7)",
     _R, '    scopes = [s for s in scopes if s != "subnet"] if _pair_not_home(said) else scopes\n', ""),
    ("M7493", "an unreadable attachment read gone: the NIC's subnet a 429, the pair said off its subnet, a card "
              "that claims what was never read (RSM3, A0)",
     _PER, '        if not targets or any(t.get("subnet_unreadable") for t in targets.values()):\n',
     "        if not targets:\n"),
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
_SAY_OFF = ("    # Its pair on an NSG off the subnet (E7): said before any return — a put-back's too (RW2's `partial_unsaid`).\n"
            "    say_perimeter_off(vm, rid, ip, b, verification, report, ref)\n")
_PUT_BACK = ("    if pair is not None:\n"
             "        return _rewrite_block(connector, b, vm, rid, ip, report, ref, now, verification, pair)\n")

MUTANTS += [
    ("M7496", "the pair read « at home » while the VM's NICs are unread at the check: a pair there whole read held, "
              "a pair gone put back on the subnet's NSG of the moment (RSM3's review, A0)",
     _PER, '        if targets and any(home in {(v["nsg_rg"].lower(), v["nsg_name"].lower()) for v in self._nic_nsg_views(t)\n',
     '        if not targets or any(home in {(v["nsg_rg"].lower(), v["nsg_name"].lower()) for v in self._nic_nsg_views(t)\n'),
    ("M7497", "the put-back held on `perimeter_off` alone: a pair unread where it lies (its NICs, their subnet) written "
              "on the NSG the subnet carries at the write (RSM3's review)",
     _G, '    return bool(verification.get("perimeter_off") or verification.get("pair_unread")\n'
         '                or verification.get("nics_unread"))\n',
     '    return bool(verification.get("perimeter_off"))\n'),
    ("M7498", "the first time's put-back of a pair never asks the NSG the subnet carries: written on one its entry "
              "doesn't name (RSM3's review, defence in depth)",
     _RP, '                    refused_elsewhere(connector, b, "subnet")      # on the NSG its entry names only (RSM3)\n',
     ""),
    ("M7499", "the second time's put-back of a pair never asks the NSG the subnet carries (RSM3's review)",
     _R, "            refused_elsewhere(connector, b, scope)     # never a perimeter on an NSG its entry doesn't name "
         "(RSM3)\n", ""),
    ("M7500", "a put-back refused only on a subnet without NSG: another NSG there taken for the entry's (RSM3's review)",
     _G, '    if (now or "").lower() != recorded.lower():\n', "    if now is None:\n"),
    ("M7501", "the card says the NSG taken off or replaced alone, never the VM moved: the subnet's other VMs said "
              "uncovered while the pair still covers them (RSM3's review)",
     _G, ('              f"la VM a changé de sous-réseau. Elle ne couvre plus {vm}"\n',
          '              "elle les couvre encore. Glorfindel ne la repose pas, ni sur ce NSG ni sur un autre sans décision. "\n'),
     ('              f"autre chose. Elle ne couvre plus {vm}"\n',
      '              "et ne les couvre plus non plus. Glorfindel ne la repose pas, ni sur ce NSG ni sur un autre sans décision. "\n')),
    ("M7502", "a fresh block whose check reads its pair off left `blocked`, « denied for ALL VMs » (RSM3's review)",
     _VB, "        if off := check.get(\"perimeter_off\"):    # its pair's NSG off the VM's subnet (RSM3): never `blocked`\n",
     '        if off := check.get("perimeter_off_never"):\n'),
    ("M7503", "the pair off said only after a put-back's return: an entry of an earlier pass's partial pair skips the "
              "card a pass (RSM3's review)",
     _R, _SAY_OFF + _PUT_BACK, _PUT_BACK + _SAY_OFF),
    ("M7504", "any 404 read as the VM gone: the identity's subscription not found said « la VM n'existe plus » "
              "(RSM3's review, A0)",
     "glorfindel/providers/azure/gone.py",
     "            return True if _is_not_found(exc) and _not_found_code(exc) in _VM_NOT_FOUND else None\n",
     "            return True if _is_not_found(exc) else None\n"),
    ("M7505", "the interface — AWS — says a VM gone it can't read (RSM3's review)",
     "glorfindel/providers/interface.py",
     "        a card of its own, and writes nothing for it (Q6, RSM3). Default: can't tell.\"\"\"\n        return None\n",
     "        a card of its own, and writes nothing for it (Q6, RSM3). Default: can't tell.\"\"\"\n        return True\n"),
]
MUTANTS += [
    ("M7506", "a put-back held back for want of a read spent: a 429 that passed lost the pair for good, « une deuxième "
              "fois » said of a pair never put back (RSM3's second review)",
     _G, '    return (b.get("scoped") is False and not said.get("perimeter_off") and not said.get("pair_whole")\n',
     '    return (False and not said.get("perimeter_off") and not said.get("pair_whole")\n'),
    ("M7507", "the second time's write refused unread (`PairUnread`) spent like a refusal for another NSG "
              "(RSM3's second review)",
     _R, "            deferred = deferred or isinstance(exc, PairUnread)\n", ""),
    ("M7508", "the first time's write refused unread spent: its put-back never deferred (RSM3's second review)",
     _RP, "                    deferred = isinstance(exc, PairUnread)       # unread where it would land: deferred "
          "(RSM3)\n", ""),
    ("M7509", "a pair deferred that leaves the VM's put-back unspent (`reasserted_at` kept as it was): the VM's "
              "rules put back at every pass against the customer's Terraform (RSM3's third review)",
     _G, '    return {"pair_deferred": now} if deferred else {"pair_deferred": None}\n',
     '    return {"reasserted_at": b.get("reasserted_at"), "pair_deferred": now} if deferred else '
     '{"pair_deferred": None}\n'),
    ("M7510", "the deferred pair never put back once it reads: its drift card said, the first time silent "
              "(RSM3's second review)",
     _RP, '    if b.get("pair_deferred"):\n        # Held back', "    if False:\n        # Held back"),
]
MUTANTS += [
    ("M7511", "the deferred pair's mark kept once it was tried: tried again at every pass (RSM3's third review)",
     _RP, "                    _update_block_entry(ref, ip, pair_deferred=None)     # tried once, whatever it answered\n",
     ""),
    ("M7512", "a pair read whole on its NSG deferred all the same: nothing to put back, put back (RSM3's third review)",
     _G, 'not said.get("perimeter_off") and not said.get("pair_whole")\n', 'not said.get("perimeter_off")\n'),
    ("M7513", "the VM's rules rewritten with the deferred pair: their put-back spent twice (RSM3's third review)",
     _R, '    scopes, at = (scopes[:1], b.get("reasserted_at") or now) if pair_alone(pair) else '
         '(scopes, at)\n', ""),                 # re-anchored (RSM6: `pair_alone`)
    ("M7514", "the deferred pair put back in human_only (RSM3's third review)",
     _RP, '        return r._missing(verification) and r._mode(autonomy, vm, ref) != "human_only"\n',
     "        return r._missing(verification)\n"),
    ("M7515", "the deferred pair put back alone said « ses règles réécrites une fois » (RSM3's third review)",
     _G, '    if pair_alone(pair):\n        return reason.replace(',      # re-anchored (RSM6: `pair_alone`)
     "    if False:\n        return reason.replace("),
]
TESTS = {
    "M7057": (f"{_REG}test_a_merged_perimeter_on_an_nsg_taken_off_its_subnet_is_said "
              f"{_GONE}test_a_merged_perimeter_on_an_nsg_taken_off_is_said_and_closes_when_it_is_back"),
    "M7058": (f"{_REG}test_a_perimeter_on_an_nsg_taken_off_its_subnet_is_not_said_bypassed "
              f"{_GONE}test_a_perimeter_alone_on_an_nsg_taken_off_is_said_gone_never_bypassed_nor_another_subnet"),
    "M7059": f"{_REG}test_a_perimeter_on_an_nsg_taken_off_its_subnet_is_not_said_bypassed",
    "M7060": (f"{_GONE}test_a_merged_entry_its_rules_gone_and_its_pair_off_puts_back_its_own_rules_only "
              f"{_GONE}test_nics_unread_at_the_check_never_put_the_pair_on_another_nsg"),
    "M7492": (f"{_GONE}test_a_merged_entry_its_rules_gone_and_its_pair_off_puts_back_its_own_rules_only "
              f"{_GONE}test_nics_unread_at_the_check_never_put_the_pair_on_another_nsg"),
    "M7493": f"{_GONE}test_an_unreadable_attachment_is_never_read_gone_nor_held",
    "M7494": f"{_GONE}test_an_isolated_vm_deleted_has_its_own_card_closed_at_the_release",
    "M7495": f"{_GONE}test_a_blocked_vm_deleted_has_its_own_card_and_nothing_is_written",
    "M7496": f"{_GONE}test_nics_unread_at_the_check_never_put_the_pair_on_another_nsg",
    "M7497": f"{_GONE}test_nics_unread_at_the_check_never_put_the_pair_on_another_nsg",
    "M7498": f"{_GONE}test_a_put_back_never_lays_a_perimeter_on_an_nsg_its_entry_does_not_name",
    "M7499": f"{_GONE}test_a_put_back_never_lays_a_perimeter_on_an_nsg_its_entry_does_not_name",
    "M7500": f"{_GONE}test_a_put_back_never_lays_a_perimeter_on_an_nsg_its_entry_does_not_name",
    "M7501": f"{_GONE}test_a_perimeter_alone_on_an_nsg_taken_off_is_said_gone_never_bypassed_nor_another_subnet",
    "M7502": f"{_GONE}test_a_fresh_block_whose_pair_is_off_is_never_blocked",
    "M7503": f"{_GONE}test_the_pair_off_is_said_on_a_put_back_of_an_earlier_pass",
    "M7504": f"{_GONE}test_only_a_vm_not_found_is_gone",
    "M7505": f"{_GONE}test_a_provider_that_cant_tell_never_says_a_vm_gone",
    "M7506": f"{_GONE}test_a_transient_429_defers_the_pairs_put_back_never_spends_it",
    "M7507": f"{_GONE}test_a_transient_429_defers_the_pairs_put_back_never_spends_it",
    "M7508": f"{_GONE}test_a_transient_429_defers_the_pairs_put_back_never_spends_it",
    "M7509": f"{_GONE}test_a_terraform_that_keeps_taking_the_vm_rules_off_is_never_fought",
    "M7510": f"{_GONE}test_a_transient_429_defers_the_pairs_put_back_never_spends_it",
    "M7511": f"{_GONE}test_a_terraform_that_keeps_taking_the_vm_rules_off_is_never_fought",
    "M7512": f"{_GONE}test_a_pair_read_whole_is_never_deferred",
    "M7513": f"{_GONE}test_a_terraform_that_keeps_taking_the_vm_rules_off_is_never_fought",
    "M7514": f"{_GONE}test_a_deferred_pair_is_never_put_back_in_human_only",
    "M7515": f"{_GONE}test_the_deferred_pair_is_put_back_once_when_the_read_comes_back",
}
