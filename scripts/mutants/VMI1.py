"""VMI1 (#971): a VM's identity on its card, on hover of its name and copied from its unfolded card
(Jonathan, 20/11, on a mockup, option A). Each mutant takes a piece back: the tooltip back to the
name alone (M6673), the group and the subscription swapped (M6674), an id said for a card filed
under a name (M6675), the block left out of the unfolded card (M6676), a value written raw (M6677),
a value no longer copied (M6678), the name copying instead of unfolding (M6679), the id spread over
every line (M6680), a long value whole in the toast (M6681), the id of Log Analytics (lowercased)
no longer read (M6682). M6673–M6682, measured by tests/unit/test_console_vm_identity.py (M6677 also
by tests/unit/test_console_escaping.py, M6681 by tests/unit/test_console_ips.py).

Form loaded by scripts/mutation_check.py: MUTANTS (id, description, file, old, new) and TESTS (its ids
→ the test that catches it); paths as plain strings.
"""
JS = "eregion_console/static/glorfindel.js"
HTML = "eregion_console/static/glorfindel.html"

_T = "tests/unit/test_console_vm_identity.py::"

MUTANTS = [
    ("M6673", "the name's tooltip back to the name alone (VMI1)", JS,
     '        <span class="node-asset-name" title="${_attr(_identityTip(ident))}">${_attr(vm_name)}</span>\n',
     '        <span class="node-asset-name" title="${_attr(vm_name)}">${_attr(vm_name)}</span>\n'),
    ("M6674", "the group and the subscription swapped (VMI1)", JS,
     "    rg: m ? m[2] : '', sub: m ? m[1] : '',\n",
     "    rg: m ? m[1] : '', sub: m ? m[2] : '',\n"),
    ("M6675", "an id said for a card filed under a name (« discovered:<name> ») (VMI1)", JS,
     "    id: id.startsWith('/subscriptions/') ? id : '',   // a discovered name without its id: no id said\n",
     "    id,\n"),
    ("M6676", "the identity block left out of the unfolded card (VMI1)", JS,
     "    ${readinessExpanded}\n    ${_idBlock(ident)}\n",
     "    ${readinessExpanded}\n"),
    ("M6677", "a value of the identity written raw into the page (VMI1, #254)", JS,
     "(long ? ': ' + val : ''))}\">${_attr(val)}</button>`",
     "(long ? ': ' + val : ''))}\">${val}</button>`"),
    ("M6678", "a value of the identity no longer copied: the click does nothing (VMI1)", JS,
     "class=\"vm-ip${long ? ' long' : ''}\" ${_on('click', 'copyAddr', val)} title=",
     "class=\"vm-ip${long ? ' long' : ''}\" title="),
    ("M6679", "the name copies instead of unfolding the card (VMI1, option C set aside)", JS,
     '        <span class="node-asset-name" title="${_attr(_identityTip(ident))}">',
     "        <span class=\"node-asset-name\" ${_on('click', 'copyAddr', vm_name)} title=\"${_attr(_identityTip(ident))}\">"),
    ("M6680", "the resource id spread over every line of the block (VMI1)", HTML,
     "  .vm-id .vm-ip.long { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }\n",
     ""),
    ("M6681", "a long value whole in the toast: a resource id over four lines (VMI1)", JS,
     "  const shown = text.length > 48 ? `${text.slice(0, 18)}…${text.slice(-26)}` : text;\n",
     "  const shown = text;\n"),
    ("M6682", "the id of Log Analytics (lowercased « resourcegroups ») no longer read: no group, no "
              "subscription (VMI1)", JS,
     "  const m = /\\/subscriptions\\/([^/]+)\\/resourceGroups\\/([^/]+)\\//i.exec(id);\n",
     "  const m = /\\/subscriptions\\/([^/]+)\\/resourceGroups\\/([^/]+)\\//.exec(id);\n"),
]

TESTS = {
    "M6673": f"{_T}test_the_name_says_the_identity_on_hover_and_still_unfolds_the_card",
    "M6674": f"{_T}test_the_identity_is_read_from_the_id_the_page_already_has",
    "M6675": f"{_T}test_the_identity_is_read_from_the_id_the_page_already_has",
    "M6676": f"{_T}test_the_unfolded_card_holds_the_block_each_value_a_copy_button",
    "M6677": f"{_T}test_the_unfolded_card_holds_the_block_each_value_a_copy_button tests/unit/test_console_escaping.py",
    "M6678": f"{_T}test_the_unfolded_card_holds_the_block_each_value_a_copy_button",
    "M6679": f"{_T}test_the_name_says_the_identity_on_hover_and_still_unfolds_the_card",
    "M6680": f"{_T}test_the_id_takes_two_lines_at_most",
    "M6681": "tests/unit/test_console_ips.py::test_where_the_page_may_not_write_the_clipboard_the_browser_copies_during_the_click",
    "M6682": f"{_T}test_the_identity_is_read_from_the_id_the_page_already_has",
}
