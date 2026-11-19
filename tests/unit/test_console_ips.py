"""IPS1b (#931): a VM's own addresses on its card, in the Glorfindel page.

Jonathan's decision of 19/11 (option A, on a mockup): a line under the VM's name, folded and
unfolded — its private addresses (four at most, then « +N »), then its public one behind 🌐, in
yellow; an address copied in one click; unfolded, the detail NIC by NIC and the age of the read;
« ip — » and why, for a VM whose NSG audit failed. Ctrl+F finds the VM of an address without
opening a card, and a public address shows a VM the Internet can reach.

The addresses are the NSG audit's (`check_nsg_access`, each `nsgs[]` entry: `ips`, and
`public_ips` from IPS1a — `{address}`, or `{address: null, error}`). Measured in a headless
Chromium on the sample console, its audit stubbed with documentation addresses (the PR says how);
read here in the page's text: no browser in the suite (as test_card_target.py does).
"""
from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")


def body(head: str) -> str:
    assert head in JS, head
    return JS.split(head, 1)[1].split("\n}\n", 1)[0]


CARD = body("function _renderAssetNode(resource, vmEscs, detEscs, restoreByVm, slotIdx = 0) {")


def test_the_addresses_are_the_nsg_audits_and_a_failed_audit_says_why():
    net = body("function _vmNet(auditEntry) {")
    assert "if (!auditEntry) return null;" in net
    assert "const check = (auditEntry.checks || []).find(c => c.name === 'NSG access');" in net
    # Only a check that read the NICs gives addresses; any other says why it did not.
    assert "if (!check || check.status !== 'ok') return { unread: (check && check.message) || 'no NSG audit for this VM' };" in net
    assert "at: auditEntry.timestamp," in net
    assert "ips: (Array.isArray(x?.ips) ? x.ips : []).filter(Boolean).map(String)," in net
    assert "pubs: (Array.isArray(x?.public_ips) ? x.public_ips : []).filter(p => p && typeof p === 'object')," in net
    assert "const net        = _vmNet(auditEntry);" in CARD


def test_folded_and_unfolded_the_card_carries_its_line_of_addresses():
    # In the header, whatever the card's state: never behind `isExpanded` (option C, set aside).
    header = CARD.split('<div class="node-asset-header"', 1)[1].split("${isExpanded ? expandedBody : compactBody}", 1)[0]
    assert "      ${_addrLine(net)}\n" in header
    assert "isExpanded ? _addrLine" not in CARD and "!isExpanded ? _addrLine" not in CARD
    # Unfolded, NIC by NIC, under the NSG line.
    expanded = CARD.split("const expandedBody = `", 1)[1].split("`;", 1)[0]
    assert "${nsgLine}\n    ${_netBlock(net)}\n" in expanded


def test_the_folded_line_four_private_addresses_then_plus_n_then_the_public_ones():
    line = body("function _addrLine(net) {")
    assert "const _ADDR_FOLDED = 4;" in JS
    assert "if (net.unread) return `<div class=\"vm-addr\" title=\"${_attr('Addresses not read: ' + net.unread)}\">ip —</div>`;" in line
    assert "const priv = [...new Set(net.nics.flatMap(n => n.ips))];" in line
    assert "const more = priv.length > _ADDR_FOLDED ? `<span title=\"Unfold the card for every address\">+${Number(priv.length - _ADDR_FOLDED)}</span>` : '';" in line
    assert ("return `<div class=\"vm-addr\">${priv.slice(0, _ADDR_FOLDED).map(a => _addrBtn(a, false)).join('')}${more}"
            "${pubs.map(p => _pubAddr(p, false)).join('')}</div>`;") in line


def test_a_public_address_is_marked_and_one_that_did_not_read_is_said():
    pub = body("function _pubAddr(p, unfolded) {")
    assert "if (p.address) return `<span class=\"vm-pub\">🌐 ${_addrBtn(String(p.address), true)}" in pub
    # The address did not read: its reason is said at once, folded or not — never nothing.
    assert "const why = String(p.error || 'unknown');\n  return unfolded\n" in pub
    assert pub.count("return") == 2
    assert "? `<span class=\"vm-pub unread\">🌐 public IP not read: ${_attr(why)}</span>`" in pub
    assert ": `<span class=\"vm-pub unread\" title=\"${_attr('Public IP not read: ' + why)}\">🌐 ?</span>`;" in pub
    # Yellow text, never a filled badge: the filled orange one stays an attacker's address (BLOCKED).
    assert re.search(r"\.vm-ip\.pub, \.vm-pub \{ color: var\(--yellow\); \}", HTML)
    assert "background" not in HTML.split(".vm-ip.pub, .vm-pub {", 1)[1].split("}", 1)[0]


def test_unfolded_each_nic_its_addresses_and_the_age_of_the_read():
    block = body("function _netBlock(net) {")
    assert "if (net.unread) return `<div class=\"vm-net\"><span class=\"vm-netfoot\">addresses not read — ${_attr(net.unread)}</span></div>`;" in block
    assert "<span class=\"vm-nicname\">⇄ ${_attr(n.nic || 'NIC')}</span>${n.ips.map(a => _addrBtn(a, false)).join('')}${n.pubs.map(p => _pubAddr(p, true)).join('')}" in block
    assert "read by the NSG audit ${_attr(_relTime(net.at))}" in block


def test_an_address_is_escaped_and_copied_in_one_click_never_unfolding_its_card():
    btn = body("function _addrBtn(a, pub) {")
    assert "${_on('click', 'copyAddr', String(a))}" in btn
    assert "title=\"${_attr('Copy ' + a)}\">${_attr(a)}</button>`;" in btn
    # The nearest element with an action takes the click (the dispatcher, #257): the button's,
    # not the header's toggleAsset. The action is in the closed table.
    actions = JS.split("const ACTIONS = {", 1)[1].split("\n};\n", 1)[0]
    assert re.search(r"^  copyAddr,", actions, re.M)


def test_the_copy_falls_back_to_a_selection_where_the_page_may_not_write_the_clipboard():
    copy = body("function copyAddr(a) {")
    assert ("if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(String(a))"
            ".then(() => toast(`✓ ${a} copied`), select);") in copy
    assert "else select();" in copy
    assert "r.selectNodeContents(el);" in copy and "const el = _target;" in copy
