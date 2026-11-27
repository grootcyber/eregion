"""SAT1 (#1271): the vault's satellite and the RECOVER block read the same inventory the same way (Jonathan, on Imladris).

On Imladris, the 360° said « rsv-… · 0 protected » and its card « 0 resource », drew no line from the vault, while the
table's RECOVER block said « 2 protected · oldest 10.2h », none unprotected: the 360° read an item's name raw, Azure's
« VM;iaasvmcontainerv2;<rg>;<vm> », where the block reads its last part (_backupVmName). Now one reading for both; and
an inventory not read — not yet, or in error with nothing good kept — is never said 0: the satellite and its card say so.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py), on neighbours of the test's.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit import js_engine
from tests.unit import test_console_sky as sky

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")

_ITEMS = [{"name": "VM;iaasvmcontainerv2;rg-celebrimbor;vm-celebrimbor-bree"},   # as Azure lists it, no friendly name
          {"name": "vm-celebrimbor-gondolin"},                                     # by its friendly name
          {"resource_id": "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-twin"}]


def _protected(backup, names):
    return json.loads(js_engine.run(js_engine.take(JS, "_backupVmName", "_vaultUnread", "_vmProtected") + f"""
let _backupItems = {json.dumps(backup)};
const block = _backupItems && Array.isArray(_backupItems.items) ? new Set(_backupItems.items.map(it => _backupVmName(it).toLowerCase())) : null;
emit(JSON.stringify({json.dumps(names)}.map(n => [_vmProtected(n), block ? block.has(n.toLowerCase()) : null])));
"""))


def test_an_item_named_as_azure_lists_it_is_its_vm_the_block_s_count_and_the_sky_s_the_same():
    names = ["vm-celebrimbor-bree", "VM-Celebrimbor-Gondolin", "vm-twin", "vm-elsewhere"]
    got = _protected({"vault": "rsv-x", "items": _ITEMS}, names)
    assert [sky for sky, _ in got] == [True, True, True, False]
    assert all(sky == block for sky, block in got)            # the satellite counts what the RECOVER block counts


def test_an_inventory_not_read_says_nothing_never_false():
    assert _protected(None, ["vm-celebrimbor-bree"]) == [[None, None]]                                   # not read yet
    assert _protected({"vault": None, "items": [], "error": "timeout (20s)"}, ["vm-celebrimbor-bree"])[0][0] is None
    assert _protected({"items": [], "error": "Aucun coffre"}, ["vm-celebrimbor-bree"])[0][0] is None    # the API's own refusal
    assert _protected({"vault": "rsv-x", "items": []}, ["vm-celebrimbor-bree"])[0][0] is False         # read, empty: it is not


def _satellite(backup):
    page = sky._PAGE.replace("const _backupItems = { vault: 'rsv-prod', items: [] };", f"let _backupItems = {json.dumps(backup)};")
    page = page.replace("const _vmProtected = n => (n === 'web-1' ? true : n === 'web-2' ? null : false);", "")
    taken = js_engine.take(JS, "_fullId", "_sameAsset", "_backupVmName", "_vaultUnread", "_vmProtected", "_skyModel")
    got = json.loads(js_engine.run(sky.GROUPS + sky.SKY + f"const RID = {json.dumps(sky._RID)};\n" + page.replace("SKY_MODEL", taken)))
    return got["backends"]["r"][0]["sub"], [t[4] for t in got["tiles"][:2]]


def test_the_vault_s_satellite_says_when_its_inventory_is_not_read():
    read = _satellite({"vault": "rsv-prod", "items": [{"name": "VM;iaasvmcontainerv2;rg-web;web-1"}, {"name": "web-2"}]})
    assert read == ("2 kept · 1 restoring", ["nb-rsv-prod", "nb-rsv-prod"])    # both linked, by the block's reading
    assert _satellite(None)[0] == "not read yet"
    assert _satellite({"vault": None, "items": [], "error": "timeout (20s)"}) == ("read error", ["", ""])   # never « 0 kept »
    assert _satellite({"vault": "rsv-prod", "items": []})[0] == "0 kept"     # read, and empty: then it is 0


_CARD = r"""
const _attr = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const InfraSky = { TONE: () => 'none' };
const m = { tiles: [{ key: 'k', name: 'web-1', vault: 'nb-rsv', s: {} }], lanes: [],
            backends: { d: [], p: [], r: [{ id: 'nb-rsv', name: 'rsv-prod' }] } };
let _backupItems = BACKUP;
FNS
emit(JSON.stringify(_skyPanelHtml({ b: 'nb-rsv' }, m)));
"""


def _card(backup):
    fns = js_engine.take(JS, "_vaultUnread", "_skyPanelHtml")
    return json.loads(js_engine.run(_CARD.replace("BACKUP", json.dumps(backup)).replace("FNS", fns)))


def test_the_vault_s_card_says_when_its_inventory_is_not_read_and_why():
    assert "1 resource" in _card({"vault": "rsv-prod", "items": [{"name": "web-1"}]})
    assert "its inventory not read yet" in _card(None)
    err = _card({"vault": None, "items": [], "error": "AuthorizationFailed <on the vault>"})
    assert "its inventory could not be read — AuthorizationFailed &lt;on the vault&gt;" in err and "0 resource" not in err
