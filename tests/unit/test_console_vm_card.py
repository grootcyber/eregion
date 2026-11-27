"""SKY10 (#1290): a VM's tile unfolded, read from the top (Jonathan, 27/11, on a mockup, one question at a time).

In the sky's card as in the table — one tile: its priority and its mode as menus at the top (the priority read only
until CFG5: it is set by hand in the config file); its identity, one click copying a value, the resource id on one
line; its checks in this order, Backup (its points, the last, Snapshot), Compute, Detection (by what, its heartbeat),
NSG — the network summed up on the NSG row (its NSGs counted once, its NICs, its addresses, the shared, a NIC without
NSG), unfolded at first in a table (a NIC a row: its NSG and where it sits, its addresses, each copied in one click),
the table scrolling past five NICs; after a rule, what waits on the VM. The sky's card is the tile: no head « the
tile », no frame of its own, its ✕ in the tile's corner, no ▾ there. The tile folded is as before.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py): vm_card.js on the page's own helpers.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
VC = (STATIC / "vm_card.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
PRIO = (STATIC / "priorities.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
CARD = JS.split("function _renderAssetNode(resource, vmEscs, detEscs, restoreByVm) {", 1)[1].split("\n}\n", 1)[0]

# vm_card.js on the page's own helpers: _attr, _on, _addrBtn, _pubAddr and its words, _relTime; the priorities' words.
_HELPERS = js_engine.take(JS, "_attr", "_on", "_addrBtn", "_pubReason", "_pubAddr") + "\nconst _PUB_REASONS = { forbidden: 'access denied' };\n" \
    + "const _relTime = iso => 'at ' + iso;\n" + PRIO.split("function _prioUsd", 1)[0]


def _run(body: str):
    return json.loads(js_engine.run(_HELPERS + VC + "\n" + body))


_NET7 = r"""
const nic = (nic, nsg, scope, ips, pubs) => ({ nic, nsg, scope, bare: scope === 'none', ips, pubs: pubs.map(a => (a ? { address: a } : { address: null, error: 'x', code: 'forbidden' })) });
const net7 = { at: '2026-11-27T22:00:00Z', failed: '', nics: [
  nic('nic-wan', 'nsg-wan', 'nic', ['10.1.0.4'], ['203.0.113.40']), nic('nic-wan2', 'nsg-wan', 'nic', ['10.1.0.5'], ['203.0.113.41']),
  nic('nic-dmz', 'nsg-snet-dmz', 'subnet', ['10.1.1.4'], []), nic('nic-app', 'nsg-snet-app', 'subnet', ['10.1.2.4'], []),
  nic('nic-data', 'nsg-snet-app', 'subnet', ['10.1.3.4', '10.1.3.5'], []), nic('nic-mgmt', 'nsg-mgmt', 'nic', ['10.1.9.4'], [null]),
  nic('nic-adm', '', 'none', ['10.1.8.4'], ['203.0.113.42'])] };
"""


def test_the_menus_at_the_top_the_priority_read_only_the_mode_its_own():
    got = _run("emit(JSON.stringify([_vmCtl('vm-a', 'essential', 'non_disruptive', false, ''), _vmCtl('vm-b', 'other', 'human_only', true, '<i>hold</i>')]));")
    a, b = got
    assert '<select class="vm-prio essential" aria-label="Priority" disabled title="' in a      # read only until CFG5
    assert '<option value="essential" selected>ESSENTIAL</option>' in a and "the model budget" in a and "CFG5" in a
    assert 'data-on-change="modeChange" data-change-args="[&quot;vm-a&quot;]"' in a and 'class="vm-mode act"' in a
    assert '<option value="non_disruptive" selected>⚡ non-disruptive (execute)</option>' in a
    assert 'data-on-click="capability"' in a and "🔒 priority set by hand" in a              # what the mode allows, one click
    assert '<option value="standard" selected>standard</option>' in b                          # a level it does not know: standard
    assert ' disabled title="Observe-only (read-only credentials): human-only is locked"' in b and "<i>hold</i>" in b


def test_the_identity_one_click_copies_a_value_the_resource_id_on_one_line():
    got = _run("emit(JSON.stringify([_vmIdRows({ rg: 'rg-app', sub: 'sub-1', id: '/subscriptions/sub-1/rg/<b>x</b>' }), _vmIdRows({ rg: '', sub: '', id: '' })]));")
    rows, none = got
    assert rows.count('data-on-click="copyAddr"') == 3 and rows.count('class="vm-ip vm-full') == 3
    assert '<span class="vm-k">Group</span>' in rows and '<span class="vm-k">Subscription</span>' in rows
    assert 'class="vm-ip vm-full vm-one"' in rows and "&lt;b&gt;x&lt;/b&gt;" in rows and "<b>x</b>" not in rows
    assert none == ""                                                                            # nothing known: no row
    assert ".vm-ckl .vm-full { grid-column: 2 / -1;" in HTML                                     # the whole width


def test_a_check_says_its_mark_its_words_and_its_gesture():
    got = _run("emit(JSON.stringify(['ok', 'warn', 'fail', ''].map(s => _vmCheckRow('NSG', s, 'why', 'said', '<b>g</b>'))));")
    for row, (ic, cls) in zip(got, (("✓", "ok"), ("⚠", "warn"), ("✗", "fail"), ("—", "none"))):
        assert f'<span class="vm-c {cls}" title="NSG: ' in row and f">{ic} NSG</span>" in row, cls
        assert '<span class="vm-d">said</span><span class="vm-g"><b>g</b></span>' in row
    assert "NSG: not read" in got[3]


def test_the_network_summed_up_each_nsg_counted_once():
    got = _run(_NET7 + "emit(JSON.stringify({ c: _vmNetCount(net7), said: _vmNetSaid(net7), unread: _vmNetSaid({ unread: 'no NSG audit' }), "
                       "failed: _vmNetSaid({ ...net7, failed: 'NIC nic-adm: no NSG' }), none: _vmNetSaid(null) }));")
    assert got["c"] == {"nsgs": 4, "nics": 7, "ips": 12, "shared": 2, "bare": 1}   # nsg-wan twice, nsg-snet-app twice: once;
    # an address not read still an IP the VM has (12: 8 private, 4 public, one of them unread)
    assert got["said"].startswith("4 NSGs · 7 NICs · 12 IPs · <span class=\"vm-shared\">2 shared</span> · <span class=\"vm-bare-txt\">1 NIC without NSG</span>")
    assert got["said"].endswith("read at 2026-11-27T22:00:00Z")
    assert got["unread"] == '<span class="vm-dim">addresses not read — no NSG audit</span>' and got["none"] == ""
    assert '<span class="vm-bare-txt">audit failed: NIC nic-adm: no NSG</span>' in got["failed"]


def test_the_network_unfolded_a_nic_a_row_its_nsg_where_it_sits_its_addresses_each_copied():
    got = _run(_NET7 + "emit(JSON.stringify(_vmNetTable(net7)));")
    assert got.startswith('<div class="vm-net-t"><span class="vm-nh">NIC</span><span class="vm-nh">NSG</span><span class="vm-nh">IP</span>')
    assert got.count('<span class="vm-nc">⇄ ') == 7
    assert 'nsg-snet-app<br><span class="vm-shared">subnet, shared</span>' in got and 'nsg-wan<br><span class="vm-dim">NIC</span>' in got
    assert '<span class="vm-bare-txt">no NSG, nor on its subnet</span>' in got                 # a NIC nothing filters (IPS2)
    assert got.count('data-on-click="copyAddr"') == 12 - 1                                     # every address read, one click
    assert "public IP not read: access denied" in got                                          # one not read, said
    assert 'class="vm-pub bare"' in got                                                        # the bare NIC's public one, red
    # Past five NICs, it scrolls, its head kept.
    assert "max-height: calc(5 * 3em + 1.8em); overflow-y: auto;" in HTML and "position: sticky; top: -6px;" in HTML


def test_the_tile_unfolded_reads_from_the_top():
    body = CARD.split("  const expandedBody = `", 1)[1].split("`;", 1)[0]
    order = ["_vmCtl(vm_name, priority, autonomyMode, !!_state?.read_only, holdChip)", "${_priorityLine(priority)}",
             '<div class="vm-ckl">${idRows}', "${checkRows}", '${netTable ? `<div class="vm-net-row">', '<hr class="vm-rule">${waits}']
    at = [body.index(x) for x in order]
    assert at == sorted(at), at
    rows = CARD.split("  const checkRows = ", 1)[1].split(";\n", 1)[0]
    names = [rows.index(f"_vmCheckRow('{n}'") for n in ("Backup", "Compute", "Detection", "NSG")]
    assert names == sorted(names)                                                               # Jonathan's order
    assert "_vmCheckRow('Backup', bSt, bDet, `${backupSummary} ${refreshBtn}`, snapshotBtn)" in rows
    # Gone from the body: the old readiness line, the MODE menu, the BACKUP block, the NSG line and its NIC block.
    for gone in ("readinessExpanded", "modeSelector", "backupSection", "nsgLine", "_netBlock", "_idBlock"):
        assert gone not in CARD, gone
    # The head: unfolded, the marks go to the menus (out of reach, its chip stays); the address line, folded only.
    assert "${isExpanded && !oor ? '' : _priorityMark(priority, modeBadge)}" in CARD
    assert "${isExpanded ? '' : _addrLine(net)}" in CARD


_FOLD = r"""
let renders = 0; const renderInfra = () => { renders++; };
const ACTIONS = { TOGGLE };
const key = 'sub/rg/vm-a';
const open = () => !_vmNetFolded.has(key);
const out = [open()]; ACTIONS.toggleNet(key); out.push(open()); ACTIONS.toggleNet(key); out.push(open(), renders);
emit(JSON.stringify(out));
"""


def test_the_network_unfolded_at_first_its_fold_kept_across_renders():
    toggle = JS.split("  toggleNet(key) {", 1)[1].split("},", 1)[0]
    got = _run(_FOLD.replace("TOGGLE", "toggleNet(key) {" + toggle + "}"))
    assert got == [True, False, True, 2]                       # unfolded at first (Ctrl+F finds an address), its fold kept
    assert "const netOpen = !_vmNetFolded.has(key), netTable = netOpen ? _vmNetTable(net) : '';" in CARD


def test_the_sky_s_card_is_the_tile():
    html = JS.split("function _skyPanelHtml(f, m) {", 1)[1].split("\n}\n", 1)[0]
    assert "    if (r) return _unfolded(r, _skyCtx);" in html and "head('the tile')" not in html   # no head of its own
    assert "  if (box.classList) box.classList.toggle('is-tile', !!pinned);" in JS
    assert "body.sky-full .sky-panel.is-tile { border: 0; padding: 0; background: transparent; }" in HTML   # no frame
    assert "body.sky-full .sky-panel.is-tile .sky-card-x { position: absolute; top: 8px; right: 8px;" in HTML   # its ✕ inside
    assert "body.sky-full .sky-panel .vm-fold { display: none; }" in HTML                       # no ▾: it folded nothing there
    assert '<span class="vm-fold"' in CARD
    assert '<script src="/static/vm_card.js"></script>\n<script src="/static/glorfindel.js"></script>' in HTML
