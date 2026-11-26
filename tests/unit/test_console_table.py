"""TBL1 (#1230): the infrastructure map as a table (Jonathan, 26/11, on a mockup).

A row per tile, its three modules as pills. The maintainer's condition: rows open each on its own, several at
once — an open row shows the tile in full. What asks for the eye (a detection to judge, a block, an isolation,
an action to approve, a restore) opens by itself; a row the operator folds stays folded until its next
incident. The totals filter. « tiles · table » is kept in this browser; on a phone the table by default beyond
8 resources.

The logic (`infra_table.js`) runs as it is, in Node or a headless Chromium (tests/unit/js_engine.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
TABLE = (STATIC / "infra_table.js").read_text(encoding="utf-8")

_SUMMARIES = [
    {"key": "entra:identities", "d": "watched", "p": None, "r": None},
    {"key": "plane:control", "d": "judge", "p": None, "r": None},
    {"key": "/subscriptions/a/vm/bree", "d": "watched", "p": "blocked", "r": "protected"},
    {"key": "/subscriptions/a/vm/gondolin", "d": "watched", "p": "isolated", "r": "protected"},
    {"key": "/subscriptions/a/vm/twin", "d": "watched", "p": "approve", "r": "restoring"},
    {"key": "/subscriptions/a/vm/calm", "d": "watched", "p": "ready", "r": "protected"},
    {"key": "/subscriptions/b/vm/dev", "d": "watched", "p": None, "r": None},
]
_HARNESS = r"""
const out = {}, T = InfraTable;
const openKeys = rows => SUMS.filter(s => T.isOpen(s, rows)).map(s => s.key.split(/[/:]/).pop());
// What asks for the eye opens by itself; a calm row stays folded.
let rows = T.rows();
out.start = openKeys(rows);
// Several open at once: the operator opens two calm rows, nothing closes.
T.toggle(SUMS[5], rows); T.toggle(SUMS[6], rows);
out.two_more = openKeys(rows);
// Folding a row that asks: it stays folded across refreshes while its incident lasts…
T.toggle(SUMS[3], rows); T.settle(SUMS, rows); T.settle(SUMS, rows);
out.folded_kept = openKeys(rows).includes('gondolin');
// …and its next incident opens it again: the incident passed, then a new one.
const calmNow = SUMS.map(s => s.key.endsWith('gondolin') ? { ...s, p: 'ready' } : s);
T.settle(calmNow, rows);
out.reopened = T.isOpen(SUMS[3], rows);
// All, then none.
T.foldAll(SUMS, rows); out.none = openKeys(rows);
T.openAll(SUMS, rows); out.all = openKeys(rows).length;
// A row no longer on the map forgets its state.
T.settle(SUMS.slice(0, 2), rows); out.forgotten = [...rows.opened].length;
// The totals and the filters.
out.totals = T.totals(SUMS);
out.filtered = T.filtered(SUMS, 'isolated').map(s => s.key.split('/').pop());
out.bogus_filter = T.filtered(SUMS, 'toString').length;
// The view kept in the browser; the phone's default.
const box = {}; const mem = { getItem: k => (k in box ? box[k] : null), setItem: (k, v) => { box[k] = String(v); } };
out.phone_small = T.view(() => mem, true, 8);
out.phone_big = T.view(() => mem, true, 9);
out.desk_big = T.view(() => mem, false, 200);
out.saved = T.save(() => mem, 'table'); out.after_save = T.view(() => mem, false, 3); out.key = Object.keys(box);
out.bad_save = T.save(() => mem, 'everything');
out.throws = T.view(() => { throw new Error('denied'); }, true, 30);
out.bogus_kept = T.view(() => ({ getItem: () => 'cards' }), false, 1);
emit(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def ran() -> dict:
    return json.loads(js_engine.run(TABLE + f"const SUMS = {json.dumps(_SUMMARIES)};\n" + _HARNESS))


def test_what_asks_for_the_eye_opens_by_itself_a_calm_row_stays_folded(ran):
    assert ran["start"] == ["control", "bree", "gondolin", "twin"], ran["start"]


def test_rows_open_each_on_its_own_several_at_once(ran):
    """The maintainer's condition: opening a row closes no other."""
    assert ran["two_more"] == ["control", "bree", "gondolin", "twin", "calm", "dev"], ran["two_more"]


def test_a_folded_row_stays_folded_until_its_next_incident(ran):
    assert ran["folded_kept"] is False
    assert ran["reopened"] is True


def test_all_or_none_and_a_row_gone_forgets_its_state(ran):
    assert ran["none"] == [] and ran["all"] == 7
    assert ran["forgotten"] == 2


def test_the_totals_filter_the_rows(ran):
    assert ran["totals"] == {"judge": 1, "isolated": 1, "blocked": 1, "approve": 1, "restoring": 1}
    assert ran["filtered"] == ["gondolin"]
    assert ran["bogus_filter"] == 7                     # a filter not of the list keeps every row


def test_the_view_kept_in_the_browser_the_table_by_default_on_a_phone_beyond_8(ran):
    assert ran["phone_small"] == "tiles" and ran["phone_big"] == "table" and ran["desk_big"] == "tiles"
    assert ran["saved"] is True and ran["after_save"] == "table" and ran["key"] == ["glorfindel_infra_view"]
    assert ran["bad_save"] is False
    assert ran["throws"] == "table" and ran["bogus_kept"] == "tiles"


def test_the_logic_is_pure():
    body = TABLE.split("const InfraTable", 1)[1]
    for word in ("document.", "window.", "fetch(", "localStorage", "innerHTML", "_cfgData", "Console."):
        assert word not in body, word
