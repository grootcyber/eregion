"""VMI1 (#971): a VM's identity on its card — on hover of its name, and copied from its unfolded card.

Jonathan's decision of 20/11, on a mockup (option A): the name's tooltip says the name, the
resource group, the subscription, the backend that detected the VM and its last heartbeat, and its
full id; the unfolded card holds the same fields in a block, each copied in one click (the value is
the button: a copy outside a secure context selects the button's own text, IPS1b). The name still
unfolds the card; the folded card is unchanged. Nothing is asked of the server: the page reads
`resource_id`, `monitoring_backend` and `last_seen`, already in /api/state.

Measured in a headless Chromium on the sample console (the PR says how); read here in the page's
text: no browser in the suite (as test_card_target.py does).
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


CARD = body("function _renderAssetNode(resource, vmEscs, detEscs, restoreByVm) {")


def test_the_identity_is_read_from_the_id_the_page_already_has():
    ident = body("function _vmIdentity(resource) {")
    # Case ignored: the ids of Log Analytics come lowercased (« resourcegroups »).
    assert "const m = /\\/subscriptions\\/([^/]+)\\/resourceGroups\\/([^/]+)\\//i.exec(id);" in ident
    assert "rg: m ? m[2] : '', sub: m ? m[1] : ''," in ident
    # A card filed under a name without its id (`discovered:<name>`): no id said.
    assert "id: id.startsWith('/subscriptions/') ? id : ''," in ident
    assert "ws: String(resource.monitoring_backend || '')," in ident
    assert "seen: resource.last_seen ? _relTime(resource.last_seen) : ''," in ident
    assert "  const ident      = _vmIdentity(resource);" in CARD


def test_the_name_says_the_identity_on_hover_and_still_unfolds_the_card():
    tip = body("function _identityTip(v) {")
    assert "return [v.name, v.rg && `resource group  ${v.rg}`, v.sub && `subscription    ${v.sub}`," in tip
    assert "detected && `detected by     ${detected}`, v.id].filter(Boolean).join('\\n');" in tip
    # The name's own span: the tooltip, escaped; no action of its own — the header's unfolds.
    span = '        <span class="node-asset-name" title="${_attr(_identityTip(ident))}">${_attr(vm_name)}</span>\n'
    assert span in CARD
    header = CARD.split('<div class="node-asset-header"', 1)[1].split("</div>", 1)[0]
    assert header.lstrip().startswith("${_on('click', 'toggleAsset', key)}>")      # TRID1: its key


def test_the_unfolded_card_holds_the_block_each_value_a_copy_button():
    block = body("function _idBlock(v) {")
    assert ("<button type=\"button\" class=\"vm-ip${long ? ' long' : ''}\" ${_on('click', 'copyAddr', val)} "
            "title=\"${_attr('Copy the ' + k + (long ? ': ' + val : ''))}\">${_attr(val)}</button>") in block
    for field in ("row('name', v.name)", "row('group', v.rg)", "row('subscription', v.sub)", "row('resource id', v.id, true)"):
        assert field in block, field
    # The backend and the heartbeat are said, not copied.
    assert "detected ? `<span class=\"vm-id-k\">detected by</span><span>${_attr(detected)}</span>` : ''" in block
    expanded = CARD.split("const expandedBody = `", 1)[1].split("`;", 1)[0]
    assert "    ${readinessExpanded}\n    ${_idBlock(ident)}\n    ${nsgLine}\n" in expanded
    compact = CARD.split("const compactBody = ", 1)[1].split(";\n", 1)[0]
    assert "_idBlock" not in compact


def test_the_id_takes_two_lines_at_most():
    assert re.search(r"\.vm-id \.vm-ip\.long \{ display: -webkit-box; -webkit-line-clamp: 2; "
                     r"-webkit-box-orient: vertical; overflow: hidden; \}", HTML)
