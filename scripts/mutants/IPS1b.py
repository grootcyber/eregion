"""IPS1b (#931): a VM's own addresses on its card, in the Glorfindel page (option A, Jonathan, 19/11).
Each mutant takes back a piece of the decision: the public address left off the folded line
(M6431), a public IP that did not read left unsaid (M6432), an address written raw (M6433), a
failed NSG audit read as one without addresses, its reason lost (M6434), the line on the unfolded
card only — option C, set aside (M6435), the copy not in the closed table of actions (M6436),
outside a secure context the browser copying nothing (M6437), the unfolded card without its NICs
(M6438), the addresses beyond four dropped without « +N » (M6439), a public address shown as a
private one (M6440), the address not selectable on its draggable card (M6441), a toast that says
copied without reading the browser's answer (M6442). M6437, M6441 and M6442 are the defect the
review of IPS1b measured, back. M6431–M6442, measured by tests/unit/test_console_ips.py (M6433
also by tests/unit/test_console_escaping.py).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"
HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_ips.py::"

MUTANTS = [
    ("M6431", "the public address left off the folded line: the VM's exposure no longer seen at a glance "
              "(IPS1b)", JS,
     "${more}${pubs.map(([p, bare]) => _pubAddr(p, false, bare)).join('')}</div>`;\n",
     "${more}</div>`;\n"),
    ("M6432", "a public IP whose address did not read left unsaid: the VM looks unexposed (IPS1b)", JS,
     "  const why = _pubReason(p);\n  return unfolded\n",
     "  const why = _pubReason(p);\n  return '';\n  return unfolded\n"),
    ("M6433", "an address from Azure written raw into the page (IPS1b, #254)", JS,
     "title=\"${_attr('Copy ' + a)}\">${_attr(a)}</button>`;\n",
     "title=\"${_attr('Copy ' + a)}\">${a}</button>`;\n"),
    ("M6434", "a failed NSG audit read as a VM without addresses: its reason lost (IPS1b)", JS,
     "  if (failed && !nsgs.length) return { unread: (check && check.message) || 'no NSG audit for this VM' };\n",
     "  if (failed && !nsgs.length) return { unread: 'no NSG audit for this VM' };\n"),
    ("M6435", "the line of addresses on the unfolded card only: Ctrl+F no longer finds a folded VM "
              "(IPS1b, option C set aside)", JS,
     "      ${_addrLine(net)}\n",
     "      ${isExpanded ? _addrLine(net) : ''}\n"),
    ("M6436", "the copy not in the closed table of actions: a click on an address does nothing (IPS1b, #257)", JS,
     "  copyAddr,                                       // a VM's address, copied from its card (IPS1)\n",
     ""),
    ("M6437", "outside a secure context the browser copies nothing: the address only selected, a selection "
              "the next refresh takes away (IPS1b, review: the defect back)", JS,
     "    try { copied = String(s) === text && document.execCommand('copy'); } catch (e) { copied = false; }\n",
     ""),
    ("M6438", "the unfolded card without its NICs and the age of the read (IPS1b)", JS,
     "    ${nsgLine}\n    ${_netBlock(net)}\n",
     "    ${nsgLine}\n"),
    ("M6439", "the private addresses beyond four dropped, without « +N » (IPS1b)", JS,
     "${priv.slice(0, _ADDR_FOLDED).map(a => _addrBtn(a, false)).join('')}${more}",
     "${priv.slice(0, _ADDR_FOLDED).map(a => _addrBtn(a, false)).join('')}"),
    ("M6440", "a public address shown as a private one, not marked (IPS1b)", JS,
     "    return `<span class=\"vm-pub\">🌐 ${_addrBtn(a, true)}",
     "    return `<span>${_addrBtn(a, false)}"),
    ("M6441", "the address not selectable on a draggable card: outside a secure context nothing is ever "
              "copied (IPS1b, review: the defect back)", HTML,
     "              -webkit-user-select: text; user-select: text; }   /* the card is draggable: none, else */\n",
     "              }\n"),
    ("M6442", "the toast says copied without reading the browser's answer: a copy refused passes for done "
              "(IPS1b, review)", JS,
     "    toast(copied ? `✓ ${text} copied` : `✗ ${text} not copied — select it and copy it by hand`);\n",
     "    toast(`✓ ${text} copied`);\n"),
]

TESTS = {
    "M6431": f"{_T}test_the_folded_line_four_private_addresses_then_plus_n_then_the_public_ones",
    "M6432": f"{_T}test_a_public_address_is_marked_and_one_that_did_not_read_is_said",
    "M6433": f"{_T}test_an_address_is_escaped_and_copied_in_one_click_never_unfolding_its_card "
             "tests/unit/test_console_escaping.py",
    "M6434": f"{_T}test_the_addresses_are_the_nsg_audits_and_a_failed_audit_says_why",
    "M6435": f"{_T}test_folded_and_unfolded_the_card_carries_its_line_of_addresses",
    "M6436": f"{_T}test_an_address_is_escaped_and_copied_in_one_click_never_unfolding_its_card",
    "M6437": f"{_T}test_where_the_page_may_not_write_the_clipboard_the_browser_copies_during_the_click",
    "M6438": f"{_T}test_folded_and_unfolded_the_card_carries_its_line_of_addresses",
    "M6439": f"{_T}test_the_folded_line_four_private_addresses_then_plus_n_then_the_public_ones",
    "M6440": f"{_T}test_a_public_address_is_marked_and_one_that_did_not_read_is_said",
    "M6441": f"{_T}test_an_address_is_selectable_though_its_card_is_draggable",
    "M6442": f"{_T}test_where_the_page_may_not_write_the_clipboard_the_browser_copies_during_the_click",
}
