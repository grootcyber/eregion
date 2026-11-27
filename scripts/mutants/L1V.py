"""L1V (#864): the oracle of a bypass, which read any flow a customer's allow opens as the hold's bypass, whoever
closed it. The night « Invariants (deep) » of 16/11 (on 4d351ef5) was red on ubuntu: « L1: the isolation of …/web
is bypassed by a customer allow; the reassertion doesn't say so ». web's isolation aimed at its former address
(api's since), its new isolation refused (the role taken away); the customer widened deny-lateral-in, before web's
block: the flows it opened were closed by that very deny and by the block, never by the isolation, whose deny names
no address of web's. The product read web's NIC uncovered and said the disappearance. The oracle's defect, not the
product's (`_bypass_comes_back`, L2C, d380df52, 30/10). Now (`bypassed`): only the flows the hold's own denies close,
evaluated first in the test's world — the isolation's for an isolation, the block's for a block. M5491: the defect
back. M5492: any deny of ours counts (the block's closes the isolation's flows). M5493: the judgement backwards.
M5494: the second pass, after the full disk, judged as before. M5495–M5496: our denies not moved first, or put
last: no flow is ever the hold's, the oracle blind to every bypass. Measured by the frozen sequence and the oracle's
other side, the product made silent on a held isolation or block (tests/unit/test_invariant_regressions.py)."""
_TI = "tests/unit/test_invariants.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_FROZEN = f"{_REG}test_an_isolation_left_on_a_former_address_is_said_gone_not_bypassed"
_STILL = f"{_REG}test_a_bypass_of_a_hold_is_still_required_to_be_said"
_BOTH = f"{_FROZEN} {_STILL}"

_RESULT = "            return (reached() - closed) - still\n"
_FIRST = '                n: {**r, "priority": 0} if (n.startswith(head) and any(h in n for h in marks)\n'
_INTACT = "                                            and (k, n) in intact) else r\n"
_BACK = ("        _note(f\"bypass of {'an isolation' if isolation else 'a block'} back\")\n"
         "        self._bypass_said(vm, isolation, bypassed())\n")

MUTANTS = [
    ("M5491", "any flow the allow opens read as the hold's bypass, whoever closed it: an isolation left on the VM's "
              "former address, the flows closed by the customer's deny and the block, a « contourné » card demanded "
              "(L1V, the defect back)",
     _TI, _RESULT, "            return reached() - closed\n"),
    ("M5492", "any deny of ours counts for the hold: the block's closes the isolation's flows, its bypass demanded "
              "of an isolation that names no address of the VM (L1V)",
     # Re-anchored by RSM2a (22/11): the hold's rules moved first are those the test's world reads intact
     # (`(k, n) in intact`); the mutant takes any deny of ours by its name again, as before RSM2a.
     _TI, _FIRST + _INTACT,
     _FIRST.replace("n.startswith(head)", 'n.startswith("glorfindel-")') + _INTACT.replace(
         "(k, n) in intact", 'r["access"].lower() == "deny"')),
    ("M5493", "the judgement backwards: what the hold's denies don't close read as its bypass, what they close "
              "never (L1V)",
     _TI, _RESULT, "            return (reached() - closed) & still\n"),
    ("M5494", "the second pass, after the full disk, judged as before L1V: the flows closed by others demanded "
              "again (L1V)",
     _TI, _BACK, _BACK.replace("bypassed()", "reached() - closed")),
    ("M5495", "our denies not moved first: no flow is ever the hold's, every bypass unjudged (L1V, complacent)",
     _TI, _FIRST, _FIRST.replace('{**r, "priority": 0}', "{**r}")),
    ("M5496", "our denies put last: no flow is ever the hold's, every bypass unjudged (L1V, complacent)",
     _TI, _FIRST, _FIRST.replace('"priority": 0', '"priority": 4096')),
]
# I3Xb's review (27/11): M5495 and M5496 on the block's side by name. A block's flows have six fields since I3Xb;
# a `still` of the probes (five) subtracted from them took nothing away, and only `[isolation]` caught the two.
TESTS = {"M5491": _FROZEN, "M5492": _FROZEN, "M5493": _BOTH, "M5494": _FROZEN, "M5495": f"{_STILL}[block]",
         "M5496": f"{_STILL}[block]"}
