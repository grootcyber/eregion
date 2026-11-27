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
  function placeCard(box, t, card, c, view) {
    const pad = 8, gap = 14, w = card.w, h = card.h, tx = t.x + t.w / 2, ty = t.y + t.h / 2;
    const top0 = Math.max(pad, (view ? view.y0 : 0) + pad), top1 = Math.max(top0, Math.min(box.h, view ? view.y1 : box.h) - h - pad);
    const hold = ([x, y]) => [Math.max(pad, Math.min(box.w - w - pad, x)), Math.max(top0, Math.min(top1, y))];
    const R = t.x + t.w + gap, L = t.x - w - gap, B = t.y + t.h + gap, A = t.y - h - gap;
    const places = [[R, ty - h / 2], [L, ty - h / 2], [tx - w / 2, B], [tx - w / 2, A], [R, B], [L, B], [R, A], [L, A],
                    [pad, top0], [box.w - w - pad, top0], [pad, top1], [box.w - w - pad, top1]].map(hold);
    const into = ([x, y]) => Math.max(0, c.r - Math.hypot(Math.max(x, Math.min(c.x, x + w)) - c.x, Math.max(y, Math.min(c.y, y + h)) - c.y));
    const covers = ([x, y]) => x < t.x + t.w && x + w > t.x && y < t.y + t.h && y + h > t.y;
    const far = ([x, y]) => Math.hypot(Math.max(x - tx, 0, tx - x - w), Math.max(y - ty, 0, ty - y - h));
    const score = p => into(p) * 1e5 + (covers(p) ? 1e4 : 0) + far(p);
    const best = places.reduce((b, p) => (score(p) < score(b) ? p : b));
    if (into(best) > 0 || w > box.w - 2 * pad) return null;
    return { left: Math.round(best[0]), top: Math.round(best[1]) };
  }

  // The bodies: a system per lane (its tiles that orbit: a VM, a cluster, an NSG), a lone body per tile of its own
  // (Entra ID, the control plane, a group) — and, without a grouping, a lone star per tile.
  function bodies(tiles, lanes, mode) {
    const out = [];
    const sectorOf = t => (t.tenant ? 'tenant' : t.sub || '?');
    if (mode === 'none' || !lanes) {
      for (const t of tiles) out.push({ id: 'star:' + t.key, lone: t.key, planets: [], sector: sectorOf(t), out: !!t.out, w: 1 });
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

  return { G, ANG, COLOR, SAT_MAX, OMEGA, polar, scaleFor, size, placeCard, sheetRest, SHEET_RESTS, bodies, layout, planetAt, satellites, placeSatellites, satOf,
           linesOf, RANK, TONE, route, intoSystem, SHIFT, laneOf, toPath, served, lit };
})();
