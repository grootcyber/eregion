"""I3Q (#771): a NIC the verification couldn't read is said unread, never « the IP still reaches it ».
The branch `False` of I3P, left open by I3N: a perimeter block whose verification concludes `False` (a
NIC proven open, or a block of ours bypassed) took off its list the NICs proven held and kept every other
one « not behind it, the IP still reaches them » — those it couldn't read too; and its answer held one
key, `uncovered_nics` or `nics_unread`, never both. Now three kinds: held (off the lists), proven open
(`open_nics`: `uncovered_nics`, « still reaches »), unread (`nics_unread`, each NIC with why, « unread …
unverified »), both keys together, `blocked_partial`. M5030: the defect back; M5031: a fix that weakens
(the unread NICs said nothing, `blocked` on an unknown, I3P); M5032: one key again; M5033: the status
`blocked` with NICs unread; M5034: the unread NICs counted open; M5035: « still reaches » said of them;
M5036, M5039: why dropped; M5037: a NIC proven held said unread; M5038: the console says one of the two.
Measured by the sequences frozen in tests/unit/test_invariant_regressions.py (the machine's oracle and
the connector) and tests/unit/test_console_blocks.py: the machine draws a bypass on a NIC's own NSG,
another perimeter and a 429 on one read of one call too rarely, and it has one NIC only that can sit off
a perimeter."""
_BLK = "glorfindel/providers/azure/blocks.py"
_API = "eregion_console/api.py"
_REG = "tests/unit/test_invariant_regressions.py::"
_MACHINE = f"{_REG}test_an_unread_nic_beside_a_bypass_is_never_said_reached_judged_by_the_machine"
_SAID = f"{_REG}test_an_unread_nic_beside_a_bypass_is_said_unread"
_BOTH = f"{_REG}test_an_open_nic_and_an_unread_one_are_both_said_each_with_its_sentence"
_I3P = f"{_REG}test_a_perimeter_block_keeps_an_unread_nic_off_its_subnet_uncovered"
_CONSOLE = "tests/unit/test_console_blocks.py::test_a_promotion_says_the_open_nics_and_the_unread_ones_each_apart"
_UNREAD = "                unread_nics = [n for n in uncovered if n not in opened]\n"
_OPEN = _UNREAD + "                uncovered = [n for n in uncovered if n in opened]\n"
_HELD = "                uncovered = [n for n in uncovered if n not in held]\n"
_OPENED = '                opened = set(check.get("open_nics") or [])\n'
_KEY = ('        if unread:\n'
        '            out["nics_unread"] = unread\n')
_STATUS = ('        if uncovered or unread:\n'
           '            out["status"] = "blocked_partial"\n')
_PHRASE = ('            out["note"] += (f" Not behind it, on another subnet, unread: {unread} — whether {ip} '
           'reaches them "\n'
           '                            "is unverified." if unread_nics else\n')
_WHY = '                    unread = ", ".join(f"{n} ({why.get(n, other)})" for n in unread_nics)\n'
_OTHER = '                    other = "cartes illisibles" if check.get("nics_unread") else "non jugée"\n'

MUTANTS = [
    ("M5030", "a perimeter block whose verification concludes False keeps every NIC off it not proven held "
              "« uncovered, the IP still reaches them » — one it couldn't read, that another perimeter cuts "
              "off (I3Q, the defect back)",
     _BLK, _OPEN, "                unread_nics = []\n"),
    ("M5031", "a perimeter block whose verification concludes False says nothing of the NICs it couldn't "
              "read: `blocked` on an unknown (I3Q, a fix that weakens; I3P)",
     _BLK, _UNREAD, "                unread_nics = []\n"),
    ("M5032", "a perimeter block with NICs open and NICs unread says the open ones alone: one key, the "
              "unread unsaid (I3Q)",
     _BLK, _KEY, _KEY.replace("        if unread:", "        elif unread:")),
    ("M5033", "a perimeter block with NICs unread and none open says `blocked` (I3Q, the status; I3P)",
     _BLK, _STATUS, _STATUS.replace("if uncovered or unread:", "if uncovered:")),
    ("M5034", "a perimeter block counts the NICs its verification couldn't read among the open ones: « the "
              "IP still reaches them », read of none (I3Q, the proof taken from the wrong lists)",
     _BLK, _OPENED, '                opened = set(check.get("open_nics") or []) | set(check.get("nics_unknown") '
                    'or []) | set(check.get("perimeter_unread") or [])\n'),
    ("M5035", "a perimeter block says « still reaches them » of the NICs it names unread (I3Q, the sentence)",
     _BLK, _PHRASE, _PHRASE.replace("— whether {ip} reaches them \"\n", "— {ip} still reaches them \"\n")
                           .replace('"is unverified." if', '"." if')),
    ("M5036", "a perimeter block names its unread NICs without why: neither « périmètre illisible » nor "
              "« règles illisibles » (I3Q)",
     _BLK, _WHY, _WHY.replace("why.get(n, other)", "other")),
    ("M5037", "a perimeter block says a NIC proven held unread: `blocked_partial` of a VM whose NICs all hold "
              "(I3Q, the held ones off the lists first)",
     _BLK, _HELD, ""),
    ("M5038", "the console says the open NICs of a promotion and drops the unread ones when both are said "
              "(I3Q, the reader of the shape)",
     _API, '    if result.get("nics_unread"):\n', '    elif result.get("nics_unread"):\n'),
    ("M5039", "a perimeter block names a NIC unread for its VM's NICs unreadable « non jugée », the cause "
              "dropped (I3Q)",
     _BLK, _OTHER, '                    other = "non jugée"\n'),
]
TESTS = {
    "M5030": f"{_MACHINE} {_SAID} {_BOTH} {_I3P}",
    "M5031": f"{_SAID} {_BOTH} {_I3P}",
    "M5032": _BOTH,
    "M5033": f"{_SAID} {_I3P}",
    "M5034": f"{_MACHINE} {_SAID} {_BOTH}",
    "M5035": f"{_SAID} {_BOTH} {_I3P}",
    "M5036": f"{_SAID} {_BOTH} {_I3P}",
    "M5037": f"{_SAID} {_I3P}",
    "M5038": _CONSOLE,
    "M5039": _SAID,
}
