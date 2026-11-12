"""I3Q (#771): a NIC the verification couldn't read is said unread, never « the IP still reaches it ».
The branch `False` of I3P, left open by I3N: a perimeter block whose verification concludes `False` (a
NIC proven open, or a block of ours bypassed) took off its list the NICs proven held and kept every other
one « not behind it, the IP still reaches them » — those it couldn't read too; and its answer held one
key, `uncovered_nics` or `nics_unread`, never both. Now three kinds (verify_block._sort_off_perimeter):
held (off the lists), proven open (`open_nics`: `uncovered_nics`, « still reaches »), unread
(`nics_unread`, each NIC with why, « unread … unverified »), both keys together, `blocked_partial`.
M5030: the defect back; M5031: a fix that weakens (the unread NICs said nothing, `blocked` on an
unknown, I3P); M5032: one key again; M5033: the status `blocked` with NICs unread; M5034: the unread
NICs counted open; M5035: « still reaches » said of them; M5036, M5039: why dropped; M5037: a NIC proven
held said unread; M5038: the console says one of the two.
The review (round 1): a perimeter alone whose pair is bypassed or gone stops its verification before the
NICs off it — each said « non jugée … unverified », one the IP reaches too. M5075: they are no longer
asked; M5076: a NIC with a block of its own asked on its perimeter alone (« still reaches » of a NIC its
own block may cut off); M5077: « no » read as held; M5078: the pair gone unsaid, `blocked` once the NICs
off it are held elsewhere; M5079: the verification's reason for a NIC not judged dropped.
Measured by the sequences frozen in tests/unit/test_invariant_regressions.py (the machine's oracle and
the connector) and tests/unit/test_console_blocks.py: the machine draws a bypass on a NIC's own NSG,
another perimeter and a 429 on one read of one call too rarely, and it has one NIC only that can sit off
a perimeter."""
_BLK = "glorfindel/providers/azure/blocks.py"
_VBL = "glorfindel/providers/azure/verify_block.py"
_API = "eregion_console/api.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_MACHINE = f"{_REG}test_an_unread_nic_beside_a_bypass_is_never_said_reached_judged_by_the_machine"
_SAID = f"{_REG}test_an_unread_nic_beside_a_bypass_is_said_unread"
_BOTH = f"{_REG}test_an_open_nic_and_an_unread_one_are_both_said_each_with_its_sentence"
_I3P = f"{_REG}test_a_perimeter_block_keeps_an_unread_nic_off_its_subnet_uncovered"
_BYPASSED = f"{_REG}test_a_bypassed_perimeter_says_reached_the_nic_off_it_the_ip_reaches"
_GONE = f"{_REG}test_a_perimeter_whose_pair_is_gone_at_its_check_says_the_nics_off_it_and_the_rules_gone"
_OWN = f"{_REG}test_a_nic_with_a_block_of_its_own_its_verification_did_not_judge_is_said_unread"
_CONSOLE = "tests/unit/test_console_blocks.py::test_a_promotion_says_the_open_nics_and_the_unread_ones_each_apart"
_RETURN = "        return [n for n in names if n in opened], unread, said\n"
_OPENED = '        opened, unsure = set(check.get("open_nics") or []), set(check.get("perimeter_unread") or [])\n'
_WHY = ("        said = \", \".join(f\"{n} ({'périmètre illisible' if n in unsure else why.get(n, other)})\" "
        "for n in unread)\n")
_OTHER = '        other = "cartes illisibles" if check.get("nics_unread") else "non lue"\n'
_NAMES = '        names = [t["nic_short"] for t in off if t["nic_short"] not in held]\n'
_SKIP = '            if n in held | opened | unsure or n in why or t["nic_id"].rstrip("/").lower() in own:\n'
_ASK = ('            stand = self._perimeter_holds(cache, t, ip, port)\n'
        '            (held if stand == "holds" else opened if stand == "no" else unsure).add(n)\n')
_KEY = ('        if unread:\n'
        '            out["nics_unread"] = unread\n')
_STATUS = '        if uncovered or unread:\n'    # the pair gone: verify_block._say_gone (I3W)
_PHRASE = ('            out["note"] += (f" Not behind it, on another subnet, unread: {unread} — whether {ip} '
           'reaches them "\n'
           '                            "is unverified." if unread_nics else\n')

MUTANTS = [
    ("M5030", "a perimeter block whose verification concludes False keeps every NIC off it not proven held "
              "« uncovered, the IP still reaches them » — one it couldn't read, that another perimeter cuts "
              "off (I3Q, the defect back)",
     _VBL, _RETURN, '        return names, [], ""\n'),
    ("M5031", "a perimeter block whose verification concludes False says nothing of the NICs it couldn't "
              "read: `blocked` on an unknown (I3Q, a fix that weakens; I3P)",
     _VBL, _RETURN, '        return [n for n in names if n in opened], [], ""\n'),
    ("M5032", "a perimeter block with NICs open and NICs unread says the open ones alone: one key, the "
              "unread unsaid (I3Q)",
     _BLK, _KEY, _KEY.replace("        if unread:", "        elif unread:")),
    ("M5033", "a perimeter block with NICs unread and none open says `blocked` (I3Q, the status; I3P)",
     _BLK, _STATUS, "        if uncovered:\n"),
    ("M5034", "a perimeter block counts the NICs its verification couldn't read among the open ones: « the "
              "IP still reaches them », read of none (I3Q, the proof taken from the wrong lists)",
     _VBL, _OPENED, '        opened, unsure = {*(check.get("open_nics") or []), *(check.get("perimeter_unread") '
                    'or []), *(check.get("nics_unknown") or [])}, set()\n'),
    ("M5035", "a perimeter block says « still reaches them » of the NICs it names unread (I3Q, the sentence)",
     _BLK, _PHRASE, _PHRASE.replace("— whether {ip} reaches them \"\n", "— {ip} still reaches them \"\n")
                           .replace('"is unverified." if', '"." if')),
    ("M5036", "a perimeter block names its unread NICs without why: neither « périmètre illisible » nor "
              "« NSG du subnet illisible » (I3Q)",
     _VBL, _WHY, '        said = ", ".join(f"{n} ({other})" for n in unread)\n'),
    ("M5037", "a perimeter block says a NIC proven held unread: `blocked_partial` of a VM whose NICs all hold "
              "(I3Q, the held ones off the lists first)",
     _VBL, _NAMES, '        names = [t["nic_short"] for t in off]\n'),
    ("M5038", "the console says the open NICs of a promotion and drops the unread ones when both are said "
              "(I3Q, the reader of the shape)",
     _API, '    if result.get("nics_unread"):\n', '    elif result.get("nics_unread"):\n'),
    ("M5039", "a perimeter block names a NIC unread for its VM's NICs unreadable « non lue », the cause "
              "dropped (I3Q)",
     _VBL, _OTHER, '        other = "non lue"\n'),
    ("M5075", "a perimeter block whose own pair is bypassed or gone never asks the NICs off it its "
              "verification didn't judge: one the IP reaches said « unverified » (I3Q's review)",
     _VBL, _ASK, "            continue\n"),
    ("M5076", "a NIC with a block of its own asked on its perimeter alone: « still reaches » of a NIC its own "
              "block may cut off (I3Q's review)",
     _VBL, _SKIP, '            if n in held | opened | unsure or n in why:\n'),
    ("M5077", "a NIC off a bypassed perimeter that no perimeter holds read as held: the IP reaches it, nothing "
              "said (I3Q's review)",
     _VBL, _ASK, _ASK.replace('opened if stand == "no" else unsure', 'held if stand == "no" else unsure')),
    ("M5078", "a perimeter block whose pair is gone at its check says nothing of it: `blocked` once the NICs "
              "off it are held elsewhere (I3Q's review)",
     _BLK, '        self._say_gone(out, check, vm_name)     # what its check read gone: its pair in every branch (I3W)\n',
     ""),
    ("M5079", "the verification's reason for a NIC it didn't judge dropped: « illisible » for a subnet's NSG, "
              "rules or a quarantine unread (I3Q's review)",
     _VBL, '                    **({"nics_unknown": undecided, "nics_unknown_why": unknown_why} if undecided else {}),\n',
     '                    **({"nics_unknown": undecided} if undecided else {}),\n'),
]
TESTS = {
    "M5030": f"{_MACHINE} {_SAID} {_BOTH} {_I3P}",
    "M5031": f"{_SAID} {_BOTH} {_I3P}",
    "M5032": _BOTH,
    "M5033": f"{_SAID} {_I3P}",
    "M5034": f"{_MACHINE} {_SAID} {_BOTH}",
    "M5035": f"{_SAID} {_BOTH} {_I3P}",
    "M5036": f"{_SAID} {_BOTH} {_I3P}",
    "M5037": _BYPASSED,
    "M5038": _CONSOLE,
    "M5039": _SAID,
    "M5075": f"{_BYPASSED} {_GONE}",
    "M5076": _OWN,
    "M5077": f"{_BYPASSED} {_GONE}",
    "M5078": _GONE,
    "M5079": _SAID,
}
