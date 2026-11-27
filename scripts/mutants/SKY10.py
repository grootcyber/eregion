"""SKY10 (#1290): a VM's tile unfolded, read from the top (Jonathan, 27/11, on a mockup). Each mutant takes a piece
back: the priority written from the card before CFG5 (M8304), the mode's menu acting on nothing (M8305), the mode
written under read-only credentials (M8306), the identity without its group (M8307), a failed check marked as good
(M8308), an NSG counted once per NIC (M8309), a NIC without NSG given a name (M8310), a NIC's public addresses left out
of the table (M8311), the network folded at first: Ctrl+F no longer finds an address (M8312), its fold not kept
(M8313), the sky's card framed twice (M8314), what waits stuck to the network (M8315). M8304–M8315, measured by
tests/unit/test_console_vm_card.py.

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
VC = "eregion_console/static/vm_card.js"
GF_JS = "eregion_console/static/glorfindel.js"
GF_HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_vm_card.py::"

MUTANTS = [
    ("M8304", "the priority written from the card before CFG5: its menu enabled (SKY10)", VC,
     'aria-label="Priority" disabled title=', 'aria-label="Priority" title='),
    ("M8305", "the mode's menu acting on nothing: its change unwired (SKY10)", VC,
     "aria-label=\"Mode\" ${_on('change', 'modeChange', vm)} ${_on('click', 'stop')}", "aria-label=\"Mode\" ${_on('click', 'stop')}"),
    ("M8306", "the mode written under read-only credentials: its lock gone (SKY10)", VC,
     "  const lock = readOnly ? ' disabled title=\"Observe-only (read-only credentials): human-only is locked\"' : ' title=",
     "  const lock = false ? ' disabled title=\"Observe-only (read-only credentials): human-only is locked\"' : ' title="),
    ("M8307", "the identity without its group (SKY10)", VC,
     "[row('Group', v.rg), row('Subscription', v.sub),", "[row('Subscription', v.sub),"),
    ("M8308", "a failed check marked as a good one: a VM Glorfindel cannot act on, said ready (SKY10)", VC,
     ": st === 'fail' ? ['✗', 'fail'] :", ": st === 'fail' ? ['✓', 'ok'] :"),
    ("M8309", "an NSG counted once per NIC: nsg-wan on two NICs, two NSGs (SKY10)", VC,
     "  return { nsgs: nsgs.size,", "  return { nsgs: net.nics.filter(n => n.nsg && !n.bare).length,"),
    ("M8310", "a NIC without NSG given a name: nothing filters it, said filtered (SKY10)", VC,
     "    const nsg = n.bare ? '<span class=\"vm-bare-txt\">no NSG, nor on its subnet</span>'",
     "    const nsg = false ? '<span class=\"vm-bare-txt\">no NSG, nor on its subnet</span>'"),
    ("M8311", "a NIC's public addresses left out of the table: the VM's exposure unsaid (SKY10)", VC,
     "const ips = [...n.ips.map(a => _addrBtn(a, false)), ...n.pubs.map(p => _pubAddr(p, true, n.bare))].join('<br>')",
     "const ips = [...n.ips.map(a => _addrBtn(a, false))].join('<br>')"),
    ("M8312", "the network folded at first: Ctrl+F no longer finds an address in the card (SKY10)", GF_JS,
     "  const netOpen = !_vmNetFolded.has(key), netTable", "  const netOpen = _vmNetFolded.has(key), netTable"),
    ("M8313", "the network's fold not kept: each click undone at the next render (SKY10)", GF_JS,
     "  toggleNet(key) { if (_vmNetFolded.has(key)) _vmNetFolded.delete(key); else _vmNetFolded.add(key); renderInfra(); },",
     "  toggleNet(key) { renderInfra(); },"),
    ("M8314", "the sky's card framed twice: its own frame around the tile's (SKY10)", GF_HTML,
     "  body.sky-full .sky-panel.is-tile { border: 0; padding: 0; background: transparent; }\n", ""),
    ("M8315", "what waits on the VM stuck to its network: no rule between (SKY10)", GF_JS,
     "    ${waits.trim() ? `<hr class=\"vm-rule\">${waits}` : ''}`;", "    ${waits}`;"),
]

TESTS = {
    "M8304": f"{_T}test_the_menus_at_the_top_the_priority_read_only_the_mode_its_own",
    "M8305": f"{_T}test_the_menus_at_the_top_the_priority_read_only_the_mode_its_own",
    "M8306": f"{_T}test_the_menus_at_the_top_the_priority_read_only_the_mode_its_own",
    "M8307": f"{_T}test_the_identity_one_click_copies_a_value_the_resource_id_on_one_line",
    "M8308": f"{_T}test_a_check_says_its_mark_its_words_and_its_gesture",
    "M8309": f"{_T}test_the_network_summed_up_each_nsg_counted_once",
    "M8310": f"{_T}test_the_network_unfolded_a_nic_a_row_its_nsg_where_it_sits_its_addresses_each_copied",
    "M8311": f"{_T}test_the_network_unfolded_a_nic_a_row_its_nsg_where_it_sits_its_addresses_each_copied",
    "M8312": f"{_T}test_the_network_unfolded_at_first_its_fold_kept_across_renders",
    "M8313": f"{_T}test_the_network_unfolded_at_first_its_fold_kept_across_renders",
    "M8314": f"{_T}test_the_sky_s_card_is_the_tile",
    "M8315": f"{_T}test_the_tile_unfolded_reads_from_the_top",
}
