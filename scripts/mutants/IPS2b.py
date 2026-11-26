"""IPS2b (#950): a VM without NSG shows its addresses, its card says « NO NSG » and its public address
of a NIC without NSG is red; a public IP that did not read is said in English by its code (Jonathan,
19/11, on a mockup). Each mutant takes a piece back: the addresses of a failed check hidden again
(M6521), a failed check shown as a good one (M6522), a NIC without NSG not seen (M6523), the chip
left out (M6524), the public address not red (M6525), the red set for the VM as a whole, not NIC by
NIC (M6526), PROTECT's inventory fed by a failed check (M6527), the codes ignored (M6528), a code of
the prototype taken for a label (M6529), the NSG line drawn from a failed check (M6530).
M6521–M6530, measured by tests/unit/test_console_no_nsg.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"

_T = "tests/unit/test_console_no_nsg.py::"

MUTANTS = [
    ("M6521", "a failed check that read the NICs hides their addresses: the most exposed VM says « ip — » "
              "again (IPS2b)", JS,
     "  if (failed && !nsgs.length) return { unread:",
     "  if (failed) return { unread:"),
    ("M6522", "a failed check shown as a good one: its failure no longer said beside its addresses (IPS2b)", JS,
     "    failed: failed ? String(check.message || 'NSG audit failed') : '',\n",
     "    failed: '',\n"),
    ("M6523", "a NIC without NSG not seen: no chip, no red (IPS2b)", JS,
     "      bare: x?.nsg_scope === 'none',                  // nothing filters this NIC (IPS2)\n",
     "      bare: false,\n"),
    ("M6524", "the « NO NSG » chip left out of the card (IPS2b)", JS,
     "        ${_priorityMark(priority, modeBadge)}\n        ${_bareChip(net)}\n",
     "        ${_priorityMark(priority, modeBadge)}\n"),
    ("M6525", "the public address of a NIC without NSG not red: shown as filtered (IPS2b)", JS,
     "    if (bare) return `<span class=\"vm-pub bare\"",
     "    if (false) return `<span class=\"vm-pub bare\""),
    ("M6526", "the red set for the VM as a whole: a filtered NIC's public address red too (IPS2b)", JS,
     "  const pubs = net.nics.flatMap(n => n.pubs.map(p => [p, n.bare]));\n",
     "  const pubs = net.nics.flatMap(n => n.pubs.map(p => [p, net.nics.some(x => x.bare)]));\n"),
    ("M6527", "PROTECT's fallback inventory fed by a failed check (IPS2b)", JS,
     "    if (c.status !== 'ok') return;             // a failed check names no NSG (IPS2)\n",
     ""),
    ("M6528", "the codes ignored: the French words in an English page again (IPS2b)", JS,
     "  const said = Object.prototype.hasOwnProperty.call(_PUB_REASONS, p.code) ? _PUB_REASONS[p.code] : '';\n",
     "  const said = '';\n"),
    ("M6529", "a code of the prototype taken for a label (« constructor », « toString ») (IPS2b)", JS,
     "  const said = Object.prototype.hasOwnProperty.call(_PUB_REASONS, p.code) ? _PUB_REASONS[p.code] : '';\n",
     "  const said = p.code in _PUB_REASONS ? _PUB_REASONS[p.code] : '';\n"),
    ("M6530", "the NSG line of the unfolded card drawn from a failed check: « 2 NSGs » for a VM without "
              "any (IPS2b)", JS,
     "  const _nsgData = (_nsgCheck && _nsgCheck.status === 'ok' && _nsgCheck.data) || {};\n",
     "  const _nsgData = (_nsgCheck && _nsgCheck.data) || {};\n"),
]

TESTS = {
    "M6521": f"{_T}test_a_failed_check_that_read_the_nics_gives_their_addresses_and_stays_a_failure",
    "M6522": f"{_T}test_a_failed_check_that_read_the_nics_gives_their_addresses_and_stays_a_failure",
    "M6523": f"{_T}test_a_failed_check_that_read_the_nics_gives_their_addresses_and_stays_a_failure",
    "M6524": f"{_T}test_the_card_says_no_nsg_once_in_the_row_of_its_mode",
    "M6525": f"{_T}test_the_public_address_of_a_nic_without_nsg_is_red_nic_by_nic",
    "M6526": f"{_T}test_the_public_address_of_a_nic_without_nsg_is_red_nic_by_nic",
    "M6527": f"{_T}test_a_failed_check_never_names_an_nsg",
    "M6528": f"{_T}test_a_public_ip_that_did_not_read_is_said_in_english_by_its_code",
    "M6529": f"{_T}test_a_public_ip_that_did_not_read_is_said_in_english_by_its_code",
    "M6530": f"{_T}test_a_failed_check_never_names_an_nsg",
}
