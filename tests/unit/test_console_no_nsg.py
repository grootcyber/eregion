"""IPS2b (#950): a VM without NSG shows its addresses, says nothing filters it; a public IP that did
not read is said in English, by its code.

Jonathan's decisions of 19/11, on a mockup. A VM with no NSG on its NIC nor on its subnet failed its
NSG audit before its NICs were read: its card said « ip — », though it is the most exposed. IPS2a
(Glorfindel) keeps the check `fail` and gives `data.nsgs[]`, a NIC without NSG at `nsg_scope:
"none"`; each `public_ips` element that did not read carries a `code` (forbidden, not_found,
not_allocated, unreadable) beside its French words. The page: the addresses, a « NO NSG » chip, the
public address of a NIC without NSG in red; an English label by code, the words on hover; a failed
check never read as a good one.

Measured in a headless Chromium on the sample console, its audit stubbed (the PR says how); read
here in the page's text: no browser in the suite (as test_card_target.py does).
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


def test_a_failed_check_that_read_the_nics_gives_their_addresses_and_stays_a_failure():
    net = body("function _vmNet(auditEntry) {")
    assert "const nsgs = Array.isArray(check?.data?.nsgs) ? check.data.nsgs : [];" in net
    assert "if (failed && !nsgs.length) return { unread:" in net
    assert "failed: failed ? String(check.message || 'NSG audit failed') : ''," in net
    assert "bare: x?.nsg_scope === 'none'," in net
    # Never turned into a good check: the readiness (its ✗) reads the checks themselves.
    assert "status = 'ok'" not in net and "status: 'ok'" not in net
    block = body("function _netBlock(net) {")
    assert "const failed = net.failed ? `<div class=\"vm-netfoot\">NSG audit failed: ${_attr(net.failed)}</div>` : '';" in block
    assert "return `<div class=\"vm-net\">${nics}${failed}<div class=\"vm-netfoot\">" in block


def test_a_failed_check_never_names_an_nsg():
    # The NSG line of the unfolded card, and PROTECT's fallback inventory: a good check only.
    assert "const _nsgData = (_nsgCheck && _nsgCheck.status === 'ok' && _nsgCheck.data) || {};" in CARD
    assert "    if (c.status !== 'ok') return;             // a failed check names no NSG (IPS2)\n" \
           "    if (c.data && c.data.nsg) nsgKeys.add(c.data.nsg);\n" in JS


def test_the_card_says_no_nsg_once_in_the_row_of_its_mode():
    chip = body("function _bareChip(net) {")
    assert "const bare = (net && net.nics || []).filter(n => n.bare);" in chip
    assert "if (!bare.length) return '';" in chip
    assert "nothing filters its traffic')}\">NO NSG</span>`;" in chip
    assert "${_attr('No NSG on ' + bare.map(n => n.nic || 'a NIC').join(', ')" in chip
    header = CARD.split('<div class="node-asset-header"', 1)[1].split("${isExpanded ? expandedBody : compactBody}", 1)[0]
    assert "        ${modeBadge}\n        ${_bareChip(net)}\n" in header
    rule = HTML.split(".vm-bare  {", 1)[1].split("}", 1)[0]
    assert "color: var(--red);" in rule


def test_the_public_address_of_a_nic_without_nsg_is_red_nic_by_nic():
    pub = body("function _pubAddr(p, unfolded, bare) {")
    assert ("    if (bare) return `<span class=\"vm-pub bare\" title=\"${_attr('No NSG on the NIC nor on its subnet: "
            "nothing filters ' + a)}\">🌐 ${_addrBtn(a, true)}") in pub
    assert pub.index("if (bare) return") < pub.index("return `<span class=\"vm-pub\">")
    # Each public address with its own NIC's state: never the VM's as a whole.
    line = body("function _addrLine(net) {")
    assert "const pubs = net.nics.flatMap(n => n.pubs.map(p => [p, n.bare]));" in line
    block = body("function _netBlock(net) {")
    assert "${n.pubs.map(p => _pubAddr(p, true, n.bare)).join('')}" in block
    assert "${n.bare ? ' · <span class=\"vm-bare-txt\">no NSG</span>' : ''}" in block
    assert re.search(r"\.vm-pub\.bare, \.vm-pub\.bare \.vm-ip\.pub, \.vm-bare-txt \{ color: var\(--red\); \}", HTML)


def test_a_public_ip_that_did_not_read_is_said_in_english_by_its_code():
    assert "const _PUB_REASONS = {" in JS
    reasons = JS.split("const _PUB_REASONS = {", 1)[1].split("};", 1)[0]
    for code in ("forbidden:", "not_found:", "not_allocated:", "unreadable:"):
        assert code in reasons, code
    why = body("function _pubReason(p) {")
    # Its own key only: a code « constructor » or « toString » is no label (never the prototype's).
    assert "const said = Object.prototype.hasOwnProperty.call(_PUB_REASONS, p.code) ? _PUB_REASONS[p.code] : '';" in why
    # A code the page does not know: the words as they are; one it knows: the words on hover.
    assert "return { said: said || words, words: said ? words : '' };" in why
    pub = body("function _pubAddr(p, unfolded, bare) {")
    assert "? `<span class=\"vm-pub unread\"${why.words ? ` title=\"${_attr(why.words)}\"` : ''}>🌐 public IP not read: ${_attr(why.said)}</span>`" in pub


def test_the_coverage_window_says_a_nic_without_nsg():
    # A placement at `scope: "none"`, `nsg: ""` (an isolation on a bare NIC, IPS2a's contract): « no NSG »
    # in red and « — » for its NSG, never « NIC NSG (this VM) » and an empty name.
    modal = body("function showCoverageModal(idx) {")
    assert "const scope = p.scope === 'subnet' ? 'subnet NSG (shared)' : p.scope === 'none' ? 'no NSG' : 'NIC NSG (this VM)';" in modal
    assert "const scopeCol = p.scope === 'subnet' ? 'var(--orange)' : p.scope === 'none' ? 'var(--red)' : 'var(--dim)';" in modal
    assert "🛡 ${_attr(nsg || '—')}" in modal
