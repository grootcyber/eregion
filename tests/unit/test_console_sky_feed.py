"""SKY7 (#1282): the feed in the sky as wide as its lines, each stopped at the arc (Jonathan, 27/11, « Jusqu'à l'anneau »).

On Imladris in a 1430 × 1129 window, the feed was 308 px wide: a VM's name cut to « vm… », what tells bree from gondolin
gone. Its corner was kept off the orbit's outermost labels' circle (RL) for the whole list, beyond the ring it draws,
and a fixed 330 px held it on a larger screen. Now the feed is as wide as its widest line, short of To judge; each line
is kept off the arc the sky draws at its own height, and off the labels drawn beside it; the list's box is clipped where
it would cross the arc; its height reaches only as deep as a line keeps its time, its action and its share. In the sky,
a VM's name says no « vm- », as the sky's labels. A long feed scrolls, never crushed. Out of the sky — the table, a
phone — nothing changes.

Run as it is, in Node or a headless Chromium (tests/unit/js_engine.py): the rules of the pure module, the page's
functions on neighbours of the test's.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from tests.unit import js_engine

STATIC = Path(__file__).resolve().parents[2] / "eregion_console" / "static"
SKY = (STATIC / "infra_sky.js").read_text(encoding="utf-8")
DRAW = (STATIC / "infra_sky_draw.js").read_text(encoding="utf-8")
JS = (STATIC / "glorfindel.js").read_text(encoding="utf-8")
HTML = (STATIC / "glorfindel.html").read_text(encoding="utf-8")
STYLE = HTML.split("<style>", 1)[1].split("</style>", 1)[0]

# A list's height at a width, as the page would measure it (test_console_sky_lists.py's own).
_HEIGHTS = "const heightOf = (name, w) => name === 'legend' ? (w >= 600 ? 64 : w >= 300 ? 96 : 150) : name === 'feed' ? 157 : 92;\n"


def _lists(w, h, feed="undefined"):
    return json.loads(js_engine.run(SKY + _HEIGHTS + f"""
const L = InfraSky.skyLists({{ w: {w}, h: {h} }}, heightOf, {feed});
emit(JSON.stringify({{ arr: L.arr, feed: L.feed, judge: L.judge, bands: L.bands, c: L.c, k: InfraSky.skyFit({{ w: {w}, h: {h} }}).k,
                      arcG: InfraSky.arcR(true) }}));
"""))


_FEED = "{ natural: NATURAL, least: LEAST, arc: InfraSky.arcR(true) }"


def _feed(natural, least="NaN"):
    return _FEED.replace("NATURAL", str(natural)).replace("LEAST", str(least))


def test_the_feed_is_as_wide_as_its_lines_short_of_to_judge():
    before = _lists(1406, 1028)                               # Jonathan's 1430 × 1129: the sky's box
    assert before["arr"] == "corners" and before["feed"]["width"] < 330 and "arc" not in before["feed"]
    now = _lists(1406, 1028, _feed(404))
    assert now["feed"]["width"] == 404                        # as wide as its widest line
    assert math.isclose(now["feed"]["arc"], now["arcG"] * now["k"], rel_tol=1e-9)   # its lines kept off the arc drawn
    assert now["bands"]["left"] >= now["feed"]["left"] + 404 + 20       # the bands still between the feed and To judge
    assert _lists(1406, 1028, _feed(120))["feed"]["width"] == before["feed"]["width"]   # never narrower than before
    huge, j = _lists(1406, 1028, _feed(2000)), before["judge"]
    assert huge["feed"]["left"] + huge["feed"]["width"] + 20 <= 1406 - j["right"] - j["width"] - 20   # short of To judge
    wide = _lists(1896, 979)                                  # a 1920 × 1080: a column beside the circle, 375 px
    assert wide["arr"] == "sides" and wide["feed"]["width"] < 404 and _lists(1896, 979, _feed(404))["feed"]["width"] == 404
    tall_before, tall = _lists(1056, 1714), _lists(1056, 1714, _feed(404))   # under the circle: as before
    assert tall["arr"] == "below" and tall["feed"] == tall_before["feed"]


_LINE = r"""
const c = { x: 700, y: 500 }, R = 400, line = (top, bottom, left = 20) => ({ top, bottom, left });
emit(JSON.stringify({
  above: InfraSky.lineRight(c, R, line(90, 110)),                       // above the centre: its bottom nearest the arc
  far: InfraSky.lineRight(c, R, line(0, 20)) === Infinity && InfraSky.lineRight(c, R, line(-200, -180)) === Infinity,
  middle: InfraSky.lineRight(c, R, line(490, 510)),                     // at the centre's height: the whole radius
  below: InfraSky.lineRight(c, R, line(890, 910)),                      // below it: its top nearest the arc
  label: InfraSky.lineRight(c, R, line(90, 110), [{ left: 150, right: 260, top: 100, bottom: 114 }]),
  apart: InfraSky.lineRight(c, R, line(90, 110), [{ left: 150, right: 260, top: 130, bottom: 144 },    // under it
                                                  { left: 5, right: 60, top: 95, bottom: 105 }]),       // where it starts
}));
"""


def test_a_line_keeps_off_the_arc_at_its_own_height_and_off_the_labels_beside_it():
    got = json.loads(js_engine.run(SKY + _LINE))
    r = 400 + 8                                               # the arc, and the gap a line keeps off it
    assert math.isclose(got["above"], 700 - math.sqrt(r * r - (500 - 110) ** 2), abs_tol=1e-6)
    assert got["far"]                                         # out of the arc's reach: nothing in its way
    assert math.isclose(got["middle"], 700 - r, abs_tol=1e-6)
    assert math.isclose(got["below"], 700 - math.sqrt(r * r - (890 - 500) ** 2), abs_tol=1e-6)
    assert got["label"] == 150 - 8                            # a label beside it on its right: kept off it
    assert got["apart"] == got["above"]                       # under it, or where it starts: not in its way


_CLIP = r"""
const c = { x: 700, y: 500 }, R = 400;
emit(JSON.stringify({ off: InfraSky.arcClip(c, R, { left: 10, top: 10, width: 200, height: 60 }),
                      on: InfraSky.arcClip(c, R, { left: 10, top: 10, width: 404, height: 300 }),
                      none: InfraSky.arcClip(c, R, { left: 10, top: 10, width: 0, height: 0 }) }));
"""


def test_the_list_s_box_is_clipped_where_it_would_cross_the_arc():
    got = json.loads(js_engine.run(SKY + _CLIP))
    assert got["off"] == "" and got["none"] == ""             # it does not meet the arc: no clip
    r = 400 + 4                                               # half the lines' gap: their text further off
    assert got["on"] == (f'path(evenodd, "M0 0H404V300H0Z M{690 - r} 490a{r} {r} 0 1 0 {2 * r} 0a{r} {r} 0 1 0 {-2 * r} 0Z")')


def test_the_feed_is_as_tall_as_its_lines_keep_their_time_action_and_share():
    tall = "{ natural: 404, least: 300, arc: InfraSky.arcR(true) }"
    got = json.loads(js_engine.run(SKY + _HEIGHTS.replace("name === 'feed' ? 157", "name === 'feed' ? 2400") + f"""
const box = {{ w: 1406, h: 1028 }}, L = InfraSky.skyLists(box, heightOf, {tall});
const free = InfraSky.skyLists(box, heightOf, {{ natural: 404, arc: InfraSky.arcR(true) }});
const deepest = L.feed.top + L.feed.maxH, room = d => InfraSky.lineRight(L.c, L.feed.arc, {{ top: d - 20, bottom: d, left: L.feed.left }}) - L.feed.left;
emit(JSON.stringify({{ maxH: L.feed.maxH, freeMaxH: free.feed.maxH, atIt: room(deepest), past: room(deepest + 30) }}));
"""))
    assert got["maxH"] < got["freeMaxH"]                      # shorter than its corner would let it: it scrolls
    assert 300 <= got["atIt"] < 302                           # its deepest line keeps its time, action and share
    assert got["past"] < 300                                  # deeper, a line would be cut in them


def test_the_sky_s_arc_is_the_one_drawn():
    got = json.loads(js_engine.run(SKY + "emit(JSON.stringify([InfraSky.arcR(true), InfraSky.arcR(false), InfraSky.G.RS, InfraSky.G.RA]));"))
    assert got[0] == got[2] + 88 and got[1] == got[3] + 56    # beyond the satellites' ring, or the orbit's
    assert "const r = S.arcR(grouped()), big" in DRAW         # the very arc the sky draws around its sectors
    lists = js_engine.take(JS, "_skyLists")
    assert "const grouped = ((_skyModelLast && _skyModelLast.mode) || _groupBy) !== 'none';" in lists
    assert "InfraSky.skyLists(box, heightOf, { ..._skyFeedWidths(), arc: InfraSky.arcR(grouped) });" in lists


def test_a_vm_s_name_in_the_sky_says_no_vm_prefix_the_table_its_name_whole():
    got = json.loads(js_engine.run(r"""
const _attr = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
""" + js_engine.take(JS, "_feedVm") + """
emit(JSON.stringify([_feedVm('vm-celebrimbor-bree'), _feedVm('vm-<b>x</b>'), _feedVm('db-1'), _feedVm(undefined), _feedVm('avm-1')]));
"""))
    assert got[0] == '<span class="feed-vm-pre">vm-</span>celebrimbor-bree'
    assert got[1] == '<span class="feed-vm-pre">vm-</span>&lt;b&gt;x&lt;/b&gt;'      # its name escaped, never markup
    assert got[2:] == ["db-1", "", "avm-1"]
    assert "  body.sky-full #feed-list .feed-vm-pre { display: none; }" in STYLE     # hidden in the sky only
    assert STYLE.count(".feed-vm-pre") == 1
    assert JS.count("${_attr(entry.ttp || '')} ${_feedVm(entry.vm)}</span>") == 2     # a signal's line, an action's


def test_a_long_feed_scrolls_in_the_sky_never_crushed():
    # The feed's lines are cut at their end (overflow hidden): in its column, a flex item so cut could shrink — 30 lines
    # were 8 px tall each, over one another (SKY6, measured on main).
    assert "  body.sky-full #feed-list .feed-entry { white-space: nowrap; overflow: hidden; flex-shrink: 0; }" in STYLE


_WIDTHS = r"""
const kid = (cls, w) => ({ classList: { contains: c => c === cls }, scrollWidth: w });
const row = kids => ({ children: kids, getBoundingClientRect: () => ({ left: 22 }) });
const rows = [row([kid('feed-ts', 85), kid('feed-event', 120), kid('feed-meta', 120), kid('feed-pct', 30)]),
              row([kid('feed-ts', 85), kid('feed-event', 150), kid('feed-meta', 60), kid('feed-pct', 30)])];
const feed = { getBoundingClientRect: () => ({ left: 10 }) };
const doc = { getElementById: id => (id === 'sky-feed' ? feed : null), querySelectorAll: () => rows };
const getComputedStyle = () => ({ columnGap: '8px', paddingLeft: '2px', paddingRight: '2px' });
(function (document) {
  FNS
  const none = (() => { const keep = rows.splice(0); const w = _skyFeedWidths(); rows.push(...keep); return w; })();
  emit(JSON.stringify({ got: _skyFeedWidths(), none }));
})(doc);
"""


def test_the_feed_s_widths_its_widest_line_whole_and_its_least_without_its_name():
    got = json.loads(js_engine.run(_WIDTHS.replace("FNS", js_engine.take(JS, "_skyFeedWidths"))))
    gaps = 3 * 8 + 4                                          # three gaps between four spans, the line's paddings
    assert got["got"]["natural"] == max(85 + 120 + 120 + 30, 85 + 150 + 60 + 30) + gaps + 2 * 12 + 2   # the list's either side
    assert got["got"]["least"] == max(85 + 120 + 30, 85 + 150 + 30) + gaps + 12 + 2                    # from the list's left
    assert got["none"] is not None and all(v is None for v in got["none"].values())                   # NaN: no line, no width


_FEED_LINES = r"""
const counted = () => { const s = { writes: 0, _v: '' }; Object.defineProperty(s, 'maxWidth', { get: () => s._v, set: v => { s._v = v; s.writes++; } }); return s; };
const row = (top, bottom) => ({ style: counted(), getBoundingClientRect: () => ({ top, bottom, left: 22, width: 380 }) });
const rows = [row(36, 56), row(56, 76), row(76, 96)];
let clipWrites = 0, clip = '';
const feed = { style: {}, getBoundingClientRect: () => ({ left: 10, top: 10, width: 404, height: 300 }) };
Object.defineProperty(feed.style, 'clipPath', { get: () => clip, set: v => { clip = v; clipWrites++; } });
const wrap = { getBoundingClientRect: () => ({ left: 0, top: 0 }) };
let labels = [];
const doc = { getElementById: id => ({ 'sky-wrap': wrap, 'sky-feed': feed }[id] || null),
              querySelectorAll: sel => (sel === '#feed-list .feed-entry' ? rows : sel === '#sky-wrap svg text' ? labels.map(l => ({ getBoundingClientRect: () => l })) : []) };
let full = true;
const _skyFull = () => full;
let _skyLayout = { c: { x: 700, y: 500 }, feed: { arc: 470 } }, _skyFeedClip = '';
(function (document) {
  SKY_SRC
  FNS
  const widths = () => rows.map(r => r.style.maxWidth), writes = () => rows.map(r => r.style.writes);
  const out = {};
  _skyFeedLines(); out.first = widths(); out.clip = clip; out.writes = writes(); out.clipWrites = clipWrites;
  _skyFeedLines(); out.again = writes(); out.clipAgain = clipWrites;                 // nothing changed: nothing written
  labels = [{ left: 200, right: 320, width: 120, height: 14, top: 60, bottom: 74 }];
  _skyFeedLines(); out.label = widths();
  full = false; _skyFeedLines(); out.out = widths(); out.clipOut = clip;             // out of the sky: as wide as its list
  out.expect = rows.map(r => { const o = r.getBoundingClientRect(); return Math.floor(InfraSky.lineRight(_skyLayout.c, 470, { top: o.top, bottom: o.bottom, left: 22 }, []) - 22) + 'px'; });
  emit(JSON.stringify(out));
})(doc);
"""


def test_each_line_is_written_as_wide_as_its_room_and_only_when_it_changes():
    got = json.loads(js_engine.run(_FEED_LINES.replace("SKY_SRC", SKY).replace("FNS", js_engine.take(
        JS, "_skyLabelRects", "_skyFeedLines"))))
    assert got["first"] == got["expect"]                      # each its own room, at its own height
    assert int(got["first"][0][:-2]) > int(got["first"][2][:-2])   # deeper, nearer the arc: narrower
    assert got["writes"] == [1, 1, 1] and got["again"] == [1, 1, 1]
    assert got["clip"].startswith('path(evenodd, "M0 0H404V300H0Z') and got["clipWrites"] == 1 and got["clipAgain"] == 1
    assert got["label"][1] == f"{200 - 8 - 22}px" and got["label"][0] == got["first"][0]   # the line beside the label
    assert got["out"] == ["", "", ""] and got["clipOut"] == ""


_SOON = r"""
const frames = [];
const requestAnimationFrame = fn => { frames.push(fn); return frames.length; }, cancelAnimationFrame = id => { frames[id - 1] = null; };
const calls = [];
const _skyLists = () => calls.push('lists'), _skyFeedLines = () => calls.push('lines');
let _skyFeedRaf = 0, _skyFeedAll = false;
FNS
const flush = () => { const fs = frames.splice(0); fs.forEach(f => f && f()); };
_skyFeedSoon(false); _skyFeedSoon(true); _skyFeedSoon(false); flush(); const one = calls.splice(0);
_skyFeedSoon(false); flush(); const scrolled = calls.splice(0);
emit(JSON.stringify({ one, scrolled }));
"""


def test_a_line_added_or_the_feed_scrolled_places_its_lines_again_once_a_frame():
    got = json.loads(js_engine.run(_SOON.replace("FNS", js_engine.take(JS, "_skyFeedSoon"))))
    assert got["one"] == ["lists"]                            # a line added in the frame: the lists placed again, once
    assert got["scrolled"] == ["lines"]                       # scrolled only: its lines alone
    append = js_engine.take(JS, "appendFeedEntry")
    assert "  if (_skyFull()) _skyFeedSoon(true);" in append
    assert ("document.getElementById('feed-list').addEventListener('scroll', () => { if (_skyFull()) _skyFeedSoon(false); }, "
            "{ passive: true });") in JS
    assert js_engine.take(JS, "_skyLists").rstrip().endswith("_skyFeedLines();\n}")   # placed, its lines after


_OUT = r"""
const mk = id => ({ id, parentElement: null, kids: [], attrs: {}, hasAttribute(n) { return n in this.attrs; }, removeAttribute(n) { delete this.attrs[n]; }, append(...ns) { ns.forEach(n => { n.parentElement = this; this.kids.push(n); }); } });
const col = mk('feed-col'), feed = mk('sky-feed');
const nodes = ['judge-head', 'judge-list', 'feed-head', 'feed-list'].map(mk);
nodes.forEach(n => feed.append(n));
const rows = [{ style: { maxWidth: '300px' } }, { style: { maxWidth: '' } }];
const doc = { getElementById: id => [col, feed, ...nodes].find(n => n.id === id) || null,
              querySelectorAll: sel => (sel === '#feed-list .feed-entry' ? rows : []),
              body: { classList: { toggle() {} } } };
let _skyFeedClip = 'path(evenodd, "M0 0H1V1H0Z")';
(function (document) { FNS; _skyFullOn(false); })(doc);
emit(JSON.stringify({ widths: rows.map(r => r.style.maxWidth), clip: _skyFeedClip }));
"""


def test_out_of_the_sky_the_lines_are_as_wide_as_their_list_again():
    got = json.loads(js_engine.run(_OUT.replace("FNS", js_engine.take(JS, "_COL_NODES", "_skyFullOn"))))
    assert got == {"widths": ["", ""], "clip": ""}            # its clip let go with its style: drawn again on the way back
