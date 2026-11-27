// SKY1 (#1236; Jonathan 26/11, on a mockup): the map seen at 360° — Glorfindel at the centre, one node, its ring in
// three arcs (DETECT, PROTECT, RECOVER), their backends as satellites drawn from their arc (the workspaces, the
// NSGs, the vaults), and around them the estate. The systems follow « group by »: a sun per resource group (its
// VMs its planets), or per subscription, or one star per resource (« none », the constellation); Entra ID, the
// control plane, a group's own tile, lone bodies the size of a sun. A sector per subscription; out of reach,
// dashed. A line lights only when something happens on a tile; at rest, a hover draws the quiet ones.
//
// Pure — no page, no fetch, no clock of its own: what infra_sky_draw.js draws is decided here, and the suite runs
// it as it is (tests/unit/test_console_sky.py).
//
// A tile, as the page gives it: { key, name, own: 'identity'|'control_plane'|'resource_group'|'', sub, tenant, out,
//   law, nsg, vault, s: { d, p, a, r } (infra_table.js's summary) }.
// A lane (infra_groups.js): { key, label, own, out, tiles: [tiles] }.
const InfraSky = (() => {
  const G = { W: 1000, H: 920, cx: 500, cy: 460, RG: 72, RB: 172, RA: 372, RS: 336 };
  const ANG = { d: -Math.PI / 2, p: Math.PI / 6, r: 5 * Math.PI / 6 };
  const COLOR = { d: 'blue', p: 'orange', r: 'green' };
  const SAT_MAX = 6;                     // beyond, the smallest satellites of a module go into one « +N »
  const polar = (a, r) => [G.cx + Math.cos(a) * r, G.cy + Math.sin(a) * r];
  // SKY4 (#1249; Jonathan 26/11, on the mockup): the centre follows the estate — Glorfindel's ring and its satellites
  // larger for a small one, tighter for a large one, between 80 % and 140 %; 25 resources, the size it always had.
  const RG0 = G.RG, RB0 = G.RB;
  const scaleFor = n => Math.max(0.8, Math.min(1.4, 1 + (25 - (Number(n) || 0)) * 0.02));
  function size(n) {
    const f = scaleFor(n);
    // The satellites keep their gap from the ring (SKY5, Jonathan on Imladris: scaled with it, they went out to the orbit
    // of the systems and their words under the bodies there).
    G.RG = Math.round(RG0 * f); G.RB = G.RG + (RB0 - RG0);
    return f;
  }
  // SKY5 (#1257; Jonathan 27/11, on the mockup): the phone's sheet let go — at a fraction of the screen, at a speed in
  // px/ms (+ downward): its next rest, or 0, closed. Past a third of its lowest rest downward, or a quick swipe down,
  // closed; a quick swipe up, the top rest; else the nearest rest.
  function sheetRest(frac, speed, rests) {
    const low = rests[0], top = rests[rests.length - 1];
    if (speed > 0.9 || frac < low * 2 / 3) return 0;
    if (speed < -0.9) return top;
    return rests.reduce((a, r) => (Math.abs(r - frac) < Math.abs(a - frac) ? r : a), low);
  }
  const SHEET_RESTS = [0.55, 0.92];      // SKY5: half the screen, then nearly all of it
  // SKY4: where the floating card goes, in its frame's own pixels. Places around what was clicked — beside it, above,
  // below, at its corners — and the frame's four corners, each held inside the frame; the best is the one that keeps
  // off Glorfindel's disc first (by how far it would go into it), then off what was clicked, then the nearest to it.
  // box: { w, h }; t: { x, y, w, h } (what was clicked); card: { w, h }; c: { x, y, r } (the centre's disc, at its
  // scale: InfraSky.size); view: { y0, y1 }, the window's band in the frame — the card held within it (the frame may be
  // taller than the window). Nowhere off the disc (a narrow frame, a small estate's larger centre), or a card wider
  // than the frame: null — under the circle, as on a phone (the relecture of SKY4).
  // SKY6: avoid, the lists in the sky ({ x, y, w, h } each) — a place over one weighs less than over what was clicked.
  function placeCard(box, t, card, c, view, avoid) {
    const pad = 8, gap = 14, w = card.w, h = card.h, tx = t.x + t.w / 2, ty = t.y + t.h / 2;
    const top0 = Math.max(pad, (view ? view.y0 : 0) + pad), top1 = Math.max(top0, Math.min(box.h, view ? view.y1 : box.h) - h - pad);
    const hold = ([x, y]) => [Math.max(pad, Math.min(box.w - w - pad, x)), Math.max(top0, Math.min(top1, y))];
    const R = t.x + t.w + gap, L = t.x - w - gap, B = t.y + t.h + gap, A = t.y - h - gap;
    // SKY7: under and above each list too — the circle at the right, the room left in the left column between them.
    const byLists = (avoid || []).flatMap(o => [[o.x, o.y + o.h + gap], [o.x, o.y - h - gap]]);
    const places = [[R, ty - h / 2], [L, ty - h / 2], [tx - w / 2, B], [tx - w / 2, A], [R, B], [L, B], [R, A], [L, A],
                    [pad, top0], [box.w - w - pad, top0], [pad, top1], [box.w - w - pad, top1], ...byLists].map(hold);
    const into = ([x, y]) => Math.max(0, c.r - Math.hypot(Math.max(x, Math.min(c.x, x + w)) - c.x, Math.max(y, Math.min(c.y, y + h)) - c.y));
    const covers = ([x, y]) => x < t.x + t.w && x + w > t.x && y < t.y + t.h && y + h > t.y;
    const far = ([x, y]) => Math.hypot(Math.max(x - tx, 0, tx - x - w), Math.max(y - ty, 0, ty - y - h));
    const over = ([x, y]) => (avoid || []).filter(o => x < o.x + o.w && x + w > o.x && y < o.y + o.h && y + h > o.y).length;
    const score = p => into(p) * 1e5 + (covers(p) ? 1e4 : 0) + over(p) * 5e3 + far(p);
    const best = places.reduce((b, p) => (score(p) < score(b) ? p : b));
    if (into(best) > 0 || w > box.w - 2 * pad) return null;
    return { left: Math.round(best[0]), top: Math.round(best[1]) };
  }

  // SKY6 (#1268; Jonathan 27/11, on the mockup): the lists in the sky — To judge, the feed, the legend, the bands — in
  // the room the circle leaves in its box, the sky fitted to the window (width and height, as the svg's « meet » draws
  // it). A box with a column beside the circle (« sides »): the feed at the top left, To judge at the top right, at the
  // edges; the legend at the bottom left, as wide as the circle lets it. A tall one (« below »): the circle at the top,
  // the three under it. Else (« left », SKY7; « corners » until then): the circle at the right, the three at the left,
  // To judge at the top. Never into the orbit's labels (RL). The bands at the top, centred between the lists.
  // box: { w, h }; heightOf(name, width): a list's height at a width, as the page measures it. Rects in the box's px:
  // { left|right, top|bottom, width, maxH }.
  const RL = 458;                                  // the orbit's outermost labels, from the centre
  // SKY7 (#1282): the arc the sky draws around its sectors, from the centre, as infra_sky_draw.js draws it. SKY8 (#1288;
  // Jonathan 27/11): one arc in the three views — « none » drew it a little wider (the orbit's RA + 56, 428), the circle
  // a size larger than in the grouped views; now at the satellites' ring + 88 in all three.
  const arcR = () => G.RS + 88;
  const LINE_GAP = 8;                              // a line of the feed, off the arc
  const LEFT_COL = 420, SHRINK_MAX = 0.1;          // SKY7: a line of the feed whole at the circle's widest; the circle at most 10 % smaller
  const EDGE = 16, COL = 440, SIDE_MIN = 300, TALL_MIN = 220;
  function skyFit(box) {
    const k = Math.min(box.w / G.W, box.h / G.H), side = (box.w - G.W * k) / 2, below = box.h - G.H * k;
    const tall = side < SIDE_MIN && below >= TALL_MIN;
    return { k, side, below, tall, c: { x: box.w / 2, y: tall ? G.cy * k : box.h / 2, r: RL * k } };
  }
  function skyLists(box, heightOf, feed) {
    const f = skyFit(box), c = f.c;
    // A corner's list as wide as it may be, as tall as it may be (maxH: past it, its content scrolls), its height read at
    // that width, its inner corner kept off the circle. A list that reaches the centre's height has the whole radius to
    // keep off (the relecture: a sqrt of a negative, NaN, a feed of 52 lines over the drawing and the legend); still
    // into it at its least width, shorter — its content scrolls.
    const corner = (name, top, wide, edge, least, maxH) => {
      const tall = maxH || Infinity;
      const room = (w, h) => {
        const dy = top ? c.y - (edge + h) : (box.h - edge - h) - c.y;
        const dx = dy >= c.r ? 0 : dy <= 0 ? c.r : Math.sqrt(c.r * c.r - dy * dy);
        return Math.max(least, Math.floor(c.x - edge - dx - 8));
      };
      let w = wide, h = Math.min(heightOf(name, w), tall);
      for (let i = 0; i < 4; i++) {
        const r = room(w, h);
        if (w <= r) break;
        w = r; h = Math.min(heightOf(name, w), tall);
      }
      const a = Math.max(0, c.x - edge - w - 8);
      const fit = a >= c.r ? Infinity : Math.floor((top ? c.y - edge : box.h - edge - c.y) - Math.sqrt(c.r * c.r - a * a));
      const cap = Math.max(40, Math.min(tall, fit));
      return { w, h: Math.min(h, cap), maxH: Number.isFinite(cap) ? cap : null };
    };
    // SKY7: a list at the left from a top under another's: as wide as it may be, its nearest point kept off the circle.
    const column = (name, top, wide, least, maxH) => {
      const room = h => {
        const dy = top + h < c.y ? c.y - (top + h) : top > c.y ? top - c.y : 0, dx = dy >= c.r ? 0 : Math.sqrt(c.r * c.r - dy * dy);
        return Math.max(least, Math.floor(c.x - 10 - dx - 8));
      };
      let w = wide, h = Math.min(heightOf(name, w), maxH);
      for (let i = 0; i < 4; i++) {
        const r = room(h);
        if (w <= r) break;
        w = r; h = Math.min(heightOf(name, w), maxH);
      }
      return { w, h };
    };
    const out = { arr: '', align: f.tall ? 'xMidYMin' : 'xMidYMid', c };
    if (f.side >= SIDE_MIN) {
      const ww = Math.min(COL, Math.floor(f.side - 40));
      const lg = corner('legend', false, Math.min(1100, box.w - 2 * EDGE), 14, ww);
      out.arr = 'sides';
      out.legend = { left: EDGE, bottom: 14, width: lg.w, maxH: lg.maxH };
      out.feed = { left: EDGE, top: EDGE, width: ww, maxH: Math.max(120, Math.floor(box.h - 14 - lg.h - 3 * EDGE)) };
      out.judge = { right: EDGE, top: EDGE, width: ww, maxH: Math.floor(box.h * 0.45) };
    } else if (f.tall) {
      // Under the circle: the legend across, then the feed at the left and To judge at the right — the same order.
      const top = Math.round(G.H * f.k + 4), lw = Math.max(0, box.w - 24), lh = heightOf('legend', lw);
      const half = Math.max(0, Math.floor((box.w - 36) / 2)), y = top + lh + 10, room = Math.max(120, Math.floor(box.h - y - 12));
      out.arr = 'below';
      out.legend = { left: 12, top, width: lw };
      out.feed = { left: 12, top: y, width: half, maxH: room };
      out.judge = { right: 12, top: y, width: half, maxH: room };
    } else {
      // SKY7 (#1282; Jonathan 27/11, « Cercle à droite », « To judge, puis le fil »): too little room beside a centred
      // circle (its corners before) — the circle set at the right (xMaxYMid), the room of both sides given to the left,
      // the three there: To judge at the top, the feed under it, the legend at the bottom, each as wide as the circle
      // lets it where it is.
      // Jonathan (27/11): the circle a little smaller if need be, the most lines seen — down to SHRINK_MAX, as small as
      // a line of LEFT_COL px stays whole beside its widest (its arc, or its outermost labels without it). The drawing
      // follows (padY: its viewBox grown above and below, InfraSkyDraw.align).
      const arcG = feed && Number.isFinite(feed.arc) ? feed.arc : RL;
      f.k = Math.max(f.k * (1 - SHRINK_MAX), Math.min(f.k, (box.w - 10 - LEFT_COL - LINE_GAP) / (G.W - G.cx + arcG)));
      c.x = box.w - (G.W - G.cx) * f.k; c.r = RL * f.k;
      out.padY = Math.max(0, Math.round((box.h / f.k - G.H) / 2 * 10) / 10);
      const lg = corner('legend', false, 430, 10, 200, Math.floor(box.h / 3)), jd = corner('judge', true, 300, 10, 200, Math.floor(box.h * 0.45));
      const top = 10 + jd.h + 14, fd = column('feed', top, 330, 200, Math.max(60, box.h - top - lg.h - 24));
      out.arr = 'left'; out.align = 'xMaxYMid';
      out.judge = { left: 10, top: 10, width: jd.w, maxH: jd.maxH };
      out.feed = { left: 10, top, width: fd.w, maxH: Math.max(60, box.h - top - lg.h - 24) };
      out.legend = { left: 10, bottom: 10, width: lg.w, maxH: lg.maxH };
    }
    // SKY7 (#1282; Jonathan 27/11, « Jusqu'à l'anneau »): beside the circle or in its corner, the feed as wide as its
    // widest line (feed.natural, as the page measures it), short of To judge — no longer a fixed width nor its corner
    // kept off the orbit's outermost labels (RL) for the whole list: each line is kept off the arc at its own height,
    // and off the labels drawn there (lineRight; feed.arc, the arc's radius). Never narrower than before; its height as
    // at first; its height to where a line keeps its time, its action and its share. Under the circle: as before.
    if (feed && out.arr !== 'below') {
      if (Number.isFinite(feed.natural)) {
        const room = out.arr === 'left' ? c.x - out.feed.left                            // short of the circle's centre
          : box.w - out.feed.left - out.judge.right - out.judge.width - 40;               // of To judge: the bands' gaps
        out.feed.width = Math.max(out.feed.width, Math.min(Math.ceil(feed.natural), Math.floor(room)));
      }
      if (Number.isFinite(feed.arc)) {
        out.feed.arc = feed.arc * f.k;
        // As tall as the arc leaves each line its time, its action and its share (feed.least, from the list's left):
        // past that depth, it scrolls — a line never cut in its digits, only its name.
        const r = out.feed.arc + LINE_GAP, a = c.x - out.feed.left - feed.least;
        if (Number.isFinite(feed.least) && a < r) {
          const deep = Math.floor(c.y - Math.sqrt(r * r - Math.max(0, a) * Math.max(0, a)) - out.feed.top);
          out.feed.maxH = Math.max(60, Math.min(out.feed.maxH || Infinity, deep));
        }
      }
    }
    const atTop = out.arr !== 'below';               // the bands between the two lists at the top; under the circle, across it
    // SKY7: the circle at the right, the bands right of the left's lists, to the box's edge;
    // the relecture: right of the feed too, wider than To judge under it — the bands' height never read, never over it.
    const l = out.arr === 'left' ? out.judge.left + Math.max(out.judge.width, out.feed.width) + 20 : atTop ? out.feed.left + out.feed.width + 20 : 12;
    const r = out.arr === 'left' ? 10 : atTop ? out.judge.right + out.judge.width + 20 : 12;
    const free = Math.max(0, box.w - l - r), wide = Math.min(760, free);
    out.bands = { left: Math.round(l + (free - wide) / 2), top: 10, width: Math.round(wide) };
    return out;
  }
  // SKY6: the bubble beside what it is on — its outer side first (away from the centre), then its inner side, below it,
  // above it: the first clear of the lists and off its target, held within the box. As tall as it is, else shorter, down
  // to its least (its content scrolls): the tallest that finds such a place (the second relecture: a bubble of verdicts,
  // tall, held at the top of the box, laid over To judge or the feed). No place even then: clear false — a bubble that
  // opens by itself does not, a clicked one takes the first place off its target. t: { x, y, w, h } (what it is on, its
  // system's bounds for a planet); size: { w, h } (the height its content wants); c: the centre; lists: [{ x, y, w, h }].
  // Returns { left, top, h, clear }.
  function bubbleAt(box, t, size, c, lists, least) {
    const pad = 8, gap = 16, w = size.w, tx = t.x + t.w / 2, ty = t.y + t.h / 2, right = tx >= c.x;
    const out = right ? t.x + t.w + gap : t.x - w - gap, inn = right ? t.x - w - gap : t.x + t.w + gap;
    const at = h => [[out, ty - h / 2], [inn, ty - h / 2], [tx - w / 2, t.y + t.h + 12], [tx - w / 2, t.y - h - 12]]
      .map(([x, y]) => [Math.max(pad, Math.min(box.w - w - pad, x)), Math.max(pad, Math.min(box.h - h - pad, y))]);
    const clear = ([x, y], h) => (lists || []).every(o => x >= o.x + o.w || x + w <= o.x || y >= o.y + o.h || y + h <= o.y);
    // Held within the box, a place may come back over its own target (the relecture: a tall window): never then.
    const covers = ([x, y], h) => x < t.x + t.w && x + w > t.x && y < t.y + t.h && y + h > t.y;
    const lo = Math.min(size.h, least || 140);
    for (let h = size.h; ; h = Math.max(lo, h - 20)) {
      const q = at(h).find(p => clear(p, h) && !covers(p, h));
      if (q) return { left: Math.round(q[0]), top: Math.round(q[1]), h: Math.round(h), clear: true };
      if (h === lo) break;
    }
    const tries = at(size.h), q = tries.find(p => !covers(p, size.h)) || tries[0];
    return { left: Math.round(q[0]), top: Math.round(q[1]), h: Math.round(size.h), clear: false };
  }
  // SKY6: a bubble that opens by itself stays a minute (an event that leaves a card to judge or to approve).
  const BUBBLE_MS = 60000;

  // The bodies: a system per lane (its tiles that orbit: a VM, a cluster, an NSG), a lone body per tile of its own
  // (Entra ID, the control plane, a group) — and, without a grouping, a lone star per tile.
  function bodies(tiles, lanes, mode) {
    const out = [];
    const sectorOf = t => (t.tenant ? 'tenant' : t.sub || '?');
    if (mode === 'none' || !lanes) {
      // SKY8: a tile of its own (Entra ID, the control plane) the size it is in a grouped view, and its share as there.
      for (const t of tiles) out.push({ id: 'star:' + t.key, lone: t.key, planets: [], sector: sectorOf(t), out: !!t.out, w: t.own ? 1.5 : 1 });
      return out;
    }
    for (const l of lanes) {
      const orbit = l.tiles.filter(t => !t.own);
      for (const t of l.tiles.filter(t => t.own)) out.push({ id: 'lone:' + t.key, lone: t.key, planets: [], sector: sectorOf(t), out: !!t.out, w: 1.5 });
      if (orbit.length) out.push({ id: 'sys:' + l.key, label: l.label, lone: null, planets: orbit.map(t => t.key),
                                   sector: sectorOf(orbit[0]), out: !!l.out, own: !!l.own, w: 1 + orbit.length * 0.35 });
    }
    return out;
  }

  // Their place: a sector per subscription (the tenant's at the top, then the order given), each body a share of
  // the circle by its weight; a sun's size and its planets' orbit by how many it holds.
  function layout(list, gap = 0.16) {
    const sectors = [];
    for (const b of list) if (!sectors.some(s => s.key === b.sector)) sectors.push({ key: b.sector, out: b.out });
    sectors.sort((x, y) => (x.key === 'tenant' ? -1 : y.key === 'tenant' ? 1 : 0));
    const total = list.reduce((n, b) => n + b.w, 0) || 1, span = 2 * Math.PI - gap * sectors.length;
    const first = list.filter(b => b.sector === sectors[0]?.key).reduce((n, b) => n + b.w, 0);
    let a = -Math.PI / 2 - (span * first / total) / 2;
    const placed = [];
    for (const s of sectors) {
      s.a0 = a;
      for (const b of list.filter(x => x.sector === s.key)) {
        const w = span * b.w / total, n = b.planets.length;
        placed.push({ ...b, ang: a + w / 2, pos: polar(a + w / 2, n ? G.RS : (list.every(x => !x.planets.length) ? G.RA : G.RS)),
                      rs: 7 + n * 0.75, pr: n ? 28 + n * 3.8 : 0 });
        a += w;
      }
      s.a1 = a; a += gap;
    }
    return { bodies: placed, sectors };
  }

  // A planet's place on its orbit: k of n, turned by tau (seconds) at one turn in 90 s.
  const OMEGA = 2 * Math.PI / 90;
  function planetAt(body, k, tau) {
    const phi = 2 * Math.PI * k / Math.max(1, body.planets.length) + OMEGA * tau + body.ang;
    return [body.pos[0] + Math.cos(phi) * body.pr, body.pos[1] + Math.sin(phi) * body.pr];
  }

  // The satellites of a module, spread around its arc; beyond SAT_MAX, the smallest ones into one « +N ».
  function satellites(list, served) {
    const sized = list.map(b => ({ ...b, n: served(b.id) })).sort((x, y) => y.n - x.n);
    const kept = sized.length > SAT_MAX ? sized.slice(0, SAT_MAX - 1) : sized;
    if (sized.length > SAT_MAX) {
      const rest = sized.slice(SAT_MAX - 1);
      kept.push({ id: 'more:' + rest.map(b => b.id).join('|'), name: `+${rest.length}`, more: rest.map(b => b.id), n: rest.reduce((x, b) => x + b.n, 0) });
    }
    return kept;
  }
  function placeSatellites(mods) {
    const pos = {};
    for (const [m, list] of Object.entries(mods)) list.forEach((b, j) => {
      pos[b.id] = { ...b, mod: m, at: polar(ANG[m] + (j - (list.length - 1) / 2) * 0.36, G.RB), r: 7 + Math.sqrt(b.n || 0) * 1.6 };
    });
    return pos;
  }
  // The satellite a backend is drawn as: itself, or the « +N » that holds it.
  function satOf(id, sats) {
    if (sats[id]) return id;
    const m = Object.keys(sats).find(k => (sats[k].more || []).includes(id));
    return m || '';
  }

  // What lights the lines of a tile: the backend that acts, its colour, flowing (a human must act) or pulsing (a
  // restore). `all`: its quiet lines too (a hover). Out of reach: DETECT's only. A tile's NSG unknown: from the
  // PROTECT arc itself.
  // LEG2 (#1244; Jonathan 26/11): a card waiting for a human in its action's colour, as the legend says it (LEG1),
  // dotted and flowing, from the backend that acts — a detection from its workspace, an isolation or a block from its
  // NSG, a restore from its vault, another card from PROTECT. `s.w`: what waits, by kind (the page's _waitKind).
  const WAIT = { detect: ['law', 'blue'], isolate: ['nsg', 'red'], block: ['nsg', 'orange'], restore: ['vault', 'green'],
                 other: ['nsg', 'purple'] };
  function linesOf(t, all) {
    const s = t.s || {}, out = [];
    const from = { law: t.law || 'd:arc', nsg: t.nsg || 'p:arc', vault: t.vault || 'r:arc' };
    const waits = (Array.isArray(s.w) ? s.w : []).filter(k => Object.hasOwn(WAIT, k) && (!t.out || k === 'detect'));
    const waitsFrom = m => waits.some(k => WAIT[k][0] === m);
    for (const k of waits) out.push({ from: from[WAIT[k][0]], c: WAIT[k][1], wait: true });
    if (all && s.d && !waitsFrom('law')) out.push({ from: from.law, c: 'blue', faint: true });
    if (!t.out && s.p) {
      if (s.p === 'isolated' || s.p === 'both') out.push({ from: from.nsg, c: 'red' });
      if (s.p === 'blocked' || s.p === 'both') out.push({ from: from.nsg, c: 'orange' });
      if (all && s.p === 'ready' && !waitsFrom('nsg')) out.push({ from: from.nsg, c: 'orange', faint: true });
    }
    if (!t.out && s.r === 'restoring') out.push({ from: from.vault, c: 'green', pulse: true });
    else if (all && !t.out && s.r === 'protected' && !waitsFrom('vault')) out.push({ from: from.vault, c: 'green', faint: true });
    return out;
  }
  // What asks for the eye on a tile, and its weight: the worst on a system colours its sun.
  const RANK = s => (s.p === 'isolated' || s.p === 'both' ? 5 : s.p === 'blocked' ? 4 : s.r === 'restoring' ? 3
    : s.a || s.d === 'judge' || s.d === 'card' ? 2 : 0);
  // LEG2: a tile on which only verdicts wait (detections, a rule proposed) is blue — the legend's « a verdict waits ».
  const verdict = s => Array.isArray(s.w) && s.w.length > 0 && s.w.every(k => k === 'detect');
  const TONE = s => (RANK(s) === 2 && verdict(s) ? 'verdict' : ['quiet', '', 'wait', 'green', 'orange', 'red'][RANK(s)] || 'quiet');

  // A line never crosses Glorfindel: it leaves its satellite outward, runs around the centre on its backend's own
  // orbit (a lane each), and comes out to its target; a near target, one smooth curve.
  const smooth = x => x * x * (3 - 2 * x);
  const quad = (p, q, r, n = 20) => Array.from({ length: n + 1 }, (_, i) => {
    const u = i / n, v = 1 - u;
    return [v * v * p[0] + 2 * v * u * q[0] + u * u * r[0], v * v * p[1] + 2 * v * u * q[1] + u * u * r[1]];
  });
  function route(p1, p2, lane, shift = 0) {
    const { cx, cy } = G;
    const a1 = Math.atan2(p1[1] - cy, p1[0] - cx), r1 = Math.hypot(p1[0] - cx, p1[1] - cy);
    const a2 = Math.atan2(p2[1] - cy, p2[0] - cx), r2 = Math.hypot(p2[0] - cx, p2[1] - cy);
    let da = a2 - a1; while (da > Math.PI) da -= 2 * Math.PI; while (da < -Math.PI) da += 2 * Math.PI;
    if (Math.abs(da) < 0.6) {
      const mx = (p1[0] + p2[0]) / 2, my = (p1[1] + p2[1]) / 2, dx = p2[0] - p1[0], dy = p2[1] - p1[1], len = Math.hypot(dx, dy) || 1;
      const ox = mx - cx, oy = my - cy, ol = Math.hypot(ox, oy) || 1;
      return quad(p1, [mx - dy / len * shift * 2.5 + ox / ol * 10, my + dx / len * shift * 2.5 + oy / ol * 10], p2, 24);
    }
    const L = lane + shift, pts = [];
    for (let i = 0; i <= 40; i++) {
      const t = i / 40, a = a1 + da * smooth(Math.min(1, Math.max(0, (t - 0.12) / 0.76)));
      const r = t < 0.3 ? r1 + (L - r1) * smooth(t / 0.3) : t > 0.7 ? L + (r2 - L) * smooth((t - 0.7) / 0.3) : L;
      pts.push(polar(a, r));
    }
    return pts;
  }
  // Into a system: toward the planet itself when it faces the source, toward the sun when it hides behind it, then
  // from the system's edge in one arc to the planet — no elbow, no jump as it turns.
  function intoSystem(src, sun, pr, to, lane, shift) {
    const px = to[0] - sun[0], py = to[1] - sun[1], sx = src[0] - sun[0], sy = src[1] - sun[1];
    const k = ((px * sx + py * sy) / ((Math.hypot(px, py) * Math.hypot(sx, sy)) || 1) + 1) / 2;
    const w = [sun[0] + px * k, sun[1] + py * k], pts = route(src, w, lane, shift);
    let i = pts.findIndex(q => Math.hypot(q[0] - sun[0], q[1] - sun[1]) < pr * 1.1);
    if (i < 1) i = pts.length - 1;
    return pts.slice(0, i).concat(quad(pts[i], w, to, 14));
  }
  // Each satellite its own lane; two colours never on one track.
  // LEG2 (its relecture): a line waiting of the colour of a line done — an isolation and its check that failed — runs
  // a step beside it, never under it.
  const SHIFT = { red: 0, orange: 5, purple: -5, green: 3, blue: -3, wait: 8 };
  function laneOf(index, grouped) { return (grouped ? G.RB + 32 : 268) + (index % 9) * 5; }
  const toPath = pts => 'M' + pts.map(q => q[0].toFixed(1) + ',' + q[1].toFixed(1)).join(' L');

  // What a focus serves — the tiles a hover lights: a tile, a system's planets, what a satellite serves, a module's
  // reach. Out of reach, PROTECT and RECOVER serve nothing (the watch acts only in its own subscription).
  function served(f, tiles, list, satOfId) {
    if (!f) return null;
    if (f.a) return new Set([f.a]);
    if (f.s) { const b = list.find(x => x.id === f.s); return new Set(b ? (b.lone ? [b.lone] : b.planets) : []); }
    if (f.b) return new Set(tiles.filter(t => [['d', t.law], ['p', t.nsg], ['r', t.vault]]
      .some(([m, id]) => id && satOfId(id) === f.b && (m === 'd' || !t.out))).map(t => t.key));
    if (f.m) return new Set(tiles.filter(t => f.m === 'd' || (!t.out && (f.m === 'p' ? !!t.s.p : t.s.r === 'protected' || t.s.r === 'restoring'))).map(t => t.key));
    return null;
  }
  // A line under a focus: lit when it is the focused tile's, the focused satellite's, the focused module's, or reaches
  // a tile the focus serves; nothing focused, every line as it is.
  function lit(f, mine, here, sat, satMod) {
    return !f || (f.a ? mine : f.b ? sat === f.b : f.m ? sat === f.m + ':arc' || satMod === f.m : here);
  }

  // SKY7 (#1282): how far right a line of the feed may reach — its rect { top, bottom, left } in the box's px: LINE_GAP
  // off the arc (radius R, centre c) at its own height — the nearest of its edges to the centre's height —, and off
  // each rect in `keep` (a label the sky draws) beside it on its right. Infinity: nothing in its way.
  function lineRight(c, R, line, keep) {
    const r = R + LINE_GAP, dy = line.bottom < c.y ? c.y - line.bottom : line.top > c.y ? line.top - c.y : 0;
    let right = dy >= r ? Infinity : c.x - Math.sqrt(r * r - dy * dy);
    for (const k of keep || []) {
      if (k.top < line.bottom && k.bottom > line.top && k.left > line.left) right = Math.min(right, k.left - LINE_GAP);
    }
    return right;
  }
  // SKY7: a list's box clipped where it would cross the arc — its rect { left, top, width, height } in the box's px: a
  // CSS clip-path, the box less the arc's disc (LINE_GAP / 2 off it: the lines' text further), "" when it does not meet it.
  function arcClip(c, R, rect) {
    const r = R + LINE_GAP / 2, x = c.x - rect.left, y = c.y - rect.top, w = Math.round(rect.width), h = Math.round(rect.height);
    const nx = Math.max(0, Math.min(x, w)), ny = Math.max(0, Math.min(y, h));
    if (!(w > 0 && h > 0) || Math.hypot(nx - x, ny - y) >= r) return '';
    const n = v => Math.round(v * 10) / 10;
    return `path(evenodd, "M0 0H${w}V${h}H0Z M${n(x - r)} ${n(y)}a${n(r)} ${n(r)} 0 1 0 ${n(2 * r)} 0a${n(r)} ${n(r)} 0 1 0 ${n(-2 * r)} 0Z")`;
  }

  return { G, ANG, COLOR, SAT_MAX, OMEGA, polar, scaleFor, size, placeCard, sheetRest, SHEET_RESTS, skyFit, skyLists, bubbleAt, BUBBLE_MS, RL, arcR, lineRight, arcClip, bodies, layout, planetAt, satellites, placeSatellites, satOf,
           linesOf, RANK, TONE, route, intoSystem, SHIFT, laneOf, toPath, served, lit };
})();
