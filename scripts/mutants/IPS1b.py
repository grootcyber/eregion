"""IPS1b (#931): a VM's own addresses on its card, in the Glorfindel page (option A, Jonathan, 19/11).
Each mutant takes back a piece of the decision: the public address left off the folded line
(M6431), a public IP that did not read left unsaid (M6432), an address written raw (M6433), a
failed NSG audit read as one without addresses, its reason lost (M6434), the line on the unfolded
card only — option C, set aside (M6435), the copy not in the closed table of actions (M6436), the
clipboard written where the page may not, no selection to fall back on (M6437), the unfolded card
without its NICs (M6438), the addresses beyond four dropped without « +N » (M6439), a public
address shown as a private one (M6440). M6431–M6440, measured by tests/unit/test_console_ips.py
(M6433 also by tests/unit/test_console_escaping.py).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_ips.py::"

MUTANTS = [
    ("M6431", "the public address left off the folded line: the VM's exposure no longer seen at a glance "
              "(IPS1b)", JS,
     "${more}${pubs.map(p => _pubAddr(p, false)).join('')}</div>`;\n",
     "${more}</div>`;\n"),
    ("M6432", "a public IP whose address did not read left unsaid: the VM looks unexposed (IPS1b)", JS,
     "  const why = String(p.error || 'unknown');\n",
     "  const why = String(p.error || 'unknown');\n  if (!p.address) return '';\n"),
    ("M6433", "an address from Azure written raw into the page (IPS1b, #254)", JS,
     "title=\"${_attr('Copy ' + a)}\">${_attr(a)}</button>`;\n",
     "title=\"${_attr('Copy ' + a)}\">${a}</button>`;\n"),
    ("M6434", "a failed NSG audit read as a VM without addresses: its reason lost (IPS1b)", JS,
     "  if (!check || check.status !== 'ok') return { unread: (check && check.message) || 'no NSG audit for this VM' };\n",
     "  if (!check) return { unread: 'no NSG audit for this VM' };\n"),
    ("M6435", "the line of addresses on the unfolded card only: Ctrl+F no longer finds a folded VM "
              "(IPS1b, option C set aside)", JS,
     "      ${_addrLine(net)}\n",
     "      ${isExpanded ? _addrLine(net) : ''}\n"),
    ("M6436", "the copy not in the closed table of actions: a click on an address does nothing (IPS1b, #257)", JS,
     "  copyAddr,                                       // a VM's address, copied from its card (IPS1)\n",
     ""),
    ("M6437", "the clipboard written where the page may not (a plain http address): no selection to fall "
              "back on (IPS1b)", JS,
     "  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(String(a))"
     ".then(() => toast(`✓ ${a} copied`), select);\n  else select();\n",
     "  navigator.clipboard.writeText(String(a)).then(() => toast(`✓ ${a} copied`));\n"),
    ("M6438", "the unfolded card without its NICs and the age of the read (IPS1b)", JS,
     "    ${nsgLine}\n    ${_netBlock(net)}\n",
     "    ${nsgLine}\n"),
    ("M6439", "the private addresses beyond four dropped, without « +N » (IPS1b)", JS,
     "${priv.slice(0, _ADDR_FOLDED).map(a => _addrBtn(a, false)).join('')}${more}",
     "${priv.slice(0, _ADDR_FOLDED).map(a => _addrBtn(a, false)).join('')}"),
    ("M6440", "a public address shown as a private one, not marked (IPS1b)", JS,
     "  if (p.address) return `<span class=\"vm-pub\">🌐 ${_addrBtn(String(p.address), true)}",
     "  if (p.address) return `<span>${_addrBtn(String(p.address), false)}"),
]

TESTS = {
    "M6431": f"{_T}test_the_folded_line_four_private_addresses_then_plus_n_then_the_public_ones",
    "M6432": f"{_T}test_a_public_address_is_marked_and_one_that_did_not_read_is_said",
    "M6433": f"{_T}test_an_address_is_escaped_and_copied_in_one_click_never_unfolding_its_card "
             "tests/unit/test_console_escaping.py",
    "M6434": f"{_T}test_the_addresses_are_the_nsg_audits_and_a_failed_audit_says_why",
    "M6435": f"{_T}test_folded_and_unfolded_the_card_carries_its_line_of_addresses",
    "M6436": f"{_T}test_an_address_is_escaped_and_copied_in_one_click_never_unfolding_its_card",
    "M6437": f"{_T}test_the_copy_falls_back_to_a_selection_where_the_page_may_not_write_the_clipboard",
    "M6438": f"{_T}test_folded_and_unfolded_the_card_carries_its_line_of_addresses",
    "M6439": f"{_T}test_the_folded_line_four_private_addresses_then_plus_n_then_the_public_ones",
    "M6440": f"{_T}test_a_public_address_is_marked_and_one_that_did_not_read_is_said",
}
