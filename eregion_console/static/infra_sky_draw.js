// SKY1 (#1236): the map at 360°, drawn — the SVG of what infra_sky.js decides. Built once per shape (the tiles, the
// lanes, the satellites), then updated in place at each refresh, so that its motion never restarts: the planets
// turn (still under the pointer, never under `prefers-reduced-motion`), the lines are kept from frame to frame.
// Every text goes in by textContent: nothing from outside is written as markup here. The page gives the model and
// is told the focus (a hover, a pin), which it shows in its panel — the tile itself, as everywhere.
//
// The model: { mode, tiles: [InfraSky tiles], lanes, sectors: { <key>: { label, out, own } },
//   backends: { d: [{ id, name, err }], p: [...], r: [...] }, watch: <the watch's cards>,
//   heartOf: () => { tone, short, beat } (the watch's beat, console.js watchSaid), reduced: bool }.
// A focus: { a: <a tile's key> } | { s: <a body's id> } | { b: <a satellite's id> } | { m: 'd' | 'p' | 'r' } | null.
const InfraSkyDraw = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const S = InfraSky, G = S.G, MODS = [['d', 'DETECT'], ['p', 'PROTECT'], ['r', 'RECOVER']];
  let svg = null, L = {}, M = null, laid = null, sats = {}, laneIx = {}, tileBy = new Map(), bodyOf = new Map();
  let hover = null, pin = null, tau = 0, last = null, raf = 0, shape = '', onFocus = () => {};
  let FC = 1, onPlace = () => {};                // SKY4: the centre's scale (InfraSky.size); told when the bodies move
  let lastBeat = '', heartAt = 0;               // SKY2: the watch's last beat seen (its `since`), the last second the heart was drawn
  const grow = new Map(), LINKS = new Map();
  let gen = 0;
  const C = n => (getComputedStyle(document.documentElement).getPropertyValue('--' + n) || '').trim() || '#888';
  // Every attribute by its name written here (the console's escaping guard reads each one): none is a handler, a URL
  // or a link; another name is left out.
  function put(e, k, v) {
    v = String(v);
    switch (k) {
      case 'viewBox': e.setAttribute('viewBox', v); break;
      case 'class': e.setAttribute('class', v); break;
      case 'role': e.setAttribute('role', v); break;
      case 'aria-label': e.setAttribute('aria-label', v); break;
      case 'cx': e.setAttribute('cx', v); break;
      case 'cy': e.setAttribute('cy', v); break;
      case 'r': e.setAttribute('r', v); break;
      case 'fill': e.setAttribute('fill', v); break;
      case 'opacity': e.setAttribute('opacity', v); break;
      case 'x1': e.setAttribute('x1', v); break;
      case 'y1': e.setAttribute('y1', v); break;
      case 'x2': e.setAttribute('x2', v); break;
      case 'y2': e.setAttribute('y2', v); break;
      case 'stroke': e.setAttribute('stroke', v); break;
      case 'stroke-width': e.setAttribute('stroke-width', v); break;
      case 'stroke-dasharray': e.setAttribute('stroke-dasharray', v); break;
      case 'd': e.setAttribute('d', v); break;
      case 'tabindex': e.setAttribute('tabindex', v); break;
      case 'data-b': e.setAttribute('data-b', v); break;
      case 'data-m': e.setAttribute('data-m', v); break;
      case 'data-s': e.setAttribute('data-s', v); break;
      case 'data-a': e.setAttribute('data-a', v); break;
      case 'data-ring': e.setAttribute('data-ring', v); break;
      case 'data-core': e.setAttribute('data-core', v); break;
      case 'data-glow': e.setAttribute('data-glow', v); break;
      case 'data-h': e.setAttribute('data-h', v); break;
      case 'data-label': e.setAttribute('data-label', v); break;
      case 'fill-opacity': e.setAttribute('fill-opacity', v); break;
      case 'font-family': e.setAttribute('font-family', v); break;
      case 'font-size': e.setAttribute('font-size', v); break;
      case 'font-weight': e.setAttribute('font-weight', v); break;
      case 'text-anchor': e.setAttribute('text-anchor', v); break;
      case 'paint-order': e.setAttribute('paint-order', v); break;
      case 'stroke-linejoin': e.setAttribute('stroke-linejoin', v); break;
      case 'stroke-linecap': e.setAttribute('stroke-linecap', v); break;
      case 'letter-spacing': e.setAttribute('letter-spacing', v); break;
      case 'attributeName': e.setAttribute('attributeName', v); break;
      case 'from': e.setAttribute('from', v); break;
      case 'to': e.setAttribute('to', v); break;
      case 'dur': e.setAttribute('dur', v); break;
      case 'begin': e.setAttribute('begin', v); break;
      case 'repeatCount': e.setAttribute('repeatCount', v); break;
      case 'values': e.setAttribute('values', v); break;
      case 'x': e.setAttribute('x', v); break;
      case 'y': e.setAttribute('y', v); break;
      case 'transform': e.setAttribute('transform', v); break;
      default: break;
    }
  }
  const el = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) put(e, k, v);
    if (parent) parent.appendChild(e);
    return e;
  };
  // A name along an arc, letter by letter, each turned to the arc — the right way up below (no textPath: no link).
  function arcLabel(s, radius, mid, below, size, spacing, col, parent) {
    const step = (size * 0.62 + spacing) / radius, chars = [...String(s)], half = step * chars.length / 2;
    const g = el('g', { fill: col, 'font-family': 'JetBrains Mono, ui-monospace, monospace', 'font-size': size, 'font-weight': 700, 'text-anchor': 'middle' }, parent);
    chars.forEach((ch, i) => {
      const a = below ? mid + half - (i + 0.5) * step : mid - half + (i + 0.5) * step;
      const [x, y] = S.polar(a, radius), deg = (a * 180 / Math.PI) + (below ? -90 : 90);
      el('text', { x: x.toFixed(1), y: y.toFixed(1), transform: `rotate(${deg.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)})` }, g).textContent = ch;
    });
    return g;
  }
  const label = (x, y, s, col, size, weight, anchor, parent, extra = {}) => {
    const e = el('text', { x, y, fill: col, 'font-family': 'JetBrains Mono, ui-monospace, monospace', 'font-size': size,
      'font-weight': weight, 'text-anchor': anchor, stroke: C('bg'), 'stroke-width': 3.5, 'paint-order': 'stroke',
      'stroke-linejoin': 'round', ...extra }, parent);
    e.textContent = s;
    return e;
  };
  const focusNow = () => pin || hover;
  const grouped = () => M && M.mode !== 'none';

  function mount(slot, model, focusCb, placeCb) {
    M = model;
    if (focusCb) onFocus = focusCb;
    if (placeCb) onPlace = placeCb;
    if (!svg) {
      svg = el('svg', { viewBox: `0 0 ${G.W} ${G.H}`, class: 'sky-svg', role: 'img', 'aria-label': 'The infrastructure at 360°' });
      listen();
    }
    if (svg.parentNode !== slot) slot.appendChild(svg);
    tileBy = new Map(M.tiles.map(t => [t.key, t]));
    // Its shape: what the build draws once — the tiles and whether they are out of reach, the lanes and their names
    // (SUBN1's may come after the first draw), the sectors, the satellites.
    const key = JSON.stringify([M.mode, M.tiles.map(t => [t.key, !!t.out]), (M.lanes || []).map(l => [l.key, l.label, !!l.out]),
      Object.entries(M.sectors || {}).map(([k, v]) => [k, v.label, !!v.out]), MODS.map(([m]) => (M.backends[m] || []).map(b => [b.id, b.name, !!b.err]))]);
    if (key !== shape) { shape = key; build(); }
    if (focusNow()?.a && !tileBy.has(focusNow().a)) { hover = pin = null; }
    paint(); place(); lines(); onPlace();
    if (!raf && typeof requestAnimationFrame === 'function') raf = requestAnimationFrame(frame);
  }

  // ── Built once per shape ────────────────────────────────────────────────────────────────────────────────
  function build() {
    svg.replaceChildren(); LINKS.clear(); grow.clear();
    FC = S.size(M.tiles.length);                  // SKY4: larger for a small estate, tighter for a large one
    for (const k of ['sky', 'sectors', 'links', 'figure', 'suns', 'stars']) L[k] = el('g', { class: 'sky-' + k }, svg);
    let seed = 5; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
    for (let i = 0; i < 120; i++) el('circle', { cx: (rnd() * G.W).toFixed(1), cy: (rnd() * G.H).toFixed(1), r: (rnd() * 1.2 + 0.3).toFixed(2), fill: C('dim'), opacity: (rnd() * 0.3 + 0.08).toFixed(2) }, L.sky);
    laid = S.layout(S.bodies(M.tiles, M.lanes, M.mode));
    bodyOf = new Map();
    for (const b of laid.bodies) (b.lone ? [b.lone] : b.planets).forEach(k => bodyOf.set(k, b));
    // The sectors: an arc and a name per subscription, the name along its arc (the right way up below).
    const RO = grouped() ? G.RS : G.RA;
    laid.sectors.forEach(s => {
      const info = (M.sectors || {})[s.key] || { label: s.key };
      const r = S.arcR(grouped()), big = s.a1 - s.a0 > Math.PI ? 1 : 0, col = info.out ? C('dim') : C('blue');
      const [x1, y1] = S.polar(s.a0, r), [x2, y2] = S.polar(s.a1, r);
      el('path', { d: `M${x1},${y1} A${r},${r} 0 ${big} 1 ${x2},${y2}`, fill: 'none', stroke: col, 'stroke-width': 1.2, opacity: 0.6, 'stroke-dasharray': info.out ? '5 5' : 'none' }, L.sectors);
      const below = Math.sin((s.a0 + s.a1) / 2) > 0, rt = RO + (grouped() ? (below ? 108 : 97) : (below ? 74 : 64));
      arcLabel(String(info.label || '').toUpperCase(), rt, (s.a0 + s.a1) / 2, below, 10.5, 1, col, L.sectors);
    });
    el('circle', { cx: G.cx, cy: G.cy, r: RO, fill: 'none', stroke: C('border'), 'stroke-dasharray': '2 7', opacity: 0.5 }, L.sectors);
    // The satellites, sized by what they serve; then Glorfindel's ring in three arcs, their names along them.
    const served = id => M.tiles.filter(t => t.law === id || t.nsg === id || t.vault === id).length;
    const mods = Object.fromEntries(MODS.map(([m]) => [m, S.satellites(M.backends[m] || [], served)]));
    sats = S.placeSatellites(mods);
    laneIx = {}; Object.keys(sats).forEach((id, i) => { laneIx[id] = i; });
    L.bsub = {};
    for (const [id, b] of Object.entries(sats)) {
      const [x, y] = b.at, a = Math.atan2(y - G.cy, x - G.cx), [sx, sy] = S.polar(a, G.RG + 4), col = C(S.COLOR[b.mod]);
      el('line', { x1: sx, y1: sy, x2: x, y2: y, stroke: col, 'stroke-width': 1.4, opacity: 0.55 }, L.figure);
      const g = el('g', { 'data-b': id, class: 'sky-sat', tabindex: 0 }, L.figure);
      el('title', {}, g).textContent = b.more ? `${b.more.length} more` : b.name;
      el('circle', { cx: x, cy: y, r: b.r + 8, fill: 'transparent' }, g);
      el('circle', { cx: x, cy: y, r: b.r + 4, fill: col, opacity: 0.12 }, g);
      el('circle', { cx: x, cy: y, r: b.r, fill: C('bg'), stroke: b.err ? C('red') : col, 'stroke-width': 2.4, 'data-ring': 1 }, g);
      el('circle', { cx: x, cy: y, r: b.r * 0.42, fill: col }, g);
      const ux = (x - G.cx) / G.RB, uy = (y - G.cy) / G.RB, o = b.r + 8, ly = y + uy * o + 4 + (uy < -0.5 ? -4 : uy > 0.5 ? 6 : 0);
      const anchor = Math.abs(ux) < 0.35 ? 'middle' : ux > 0 ? 'start' : 'end';
      label(x + ux * o, ly, b.more ? b.name : b.name, col, 11, 700, anchor, g);
      // SKY4: what its module's block says of it, under its name (above, for a satellite over the ring): the card is
      // closed at rest.
      // Side by side over the ring (DETECT's workspaces), each line away from its neighbour: never one over the other.
      const side = anchor !== 'middle' ? anchor : ux < -0.02 ? 'end' : ux > 0.02 ? 'start' : 'middle';
      L.bsub[id] = label(x + ux * o + (side === anchor ? 0 : side === 'start' ? -6 : 6), uy < -0.5 ? ly - 13 : ly + 12, '', C('dim'), 9, 600, side, g);
    }
    el('circle', { cx: G.cx, cy: G.cy, r: G.RG, fill: C('bg') }, L.figure);
    L.alarm = el('g', {}, L.figure);
    L.mod = {};
    for (const [m, name] of MODS) {
      const g = el('g', { 'data-m': m, class: 'sky-mod', tabindex: 0 }, L.figure);
      const a0 = S.ANG[m] - Math.PI / 3 + 0.07, a1 = S.ANG[m] + Math.PI / 3 - 0.07;
      const [x0, y0] = S.polar(a0, G.RG), [x1, y1] = S.polar(a1, G.RG), d = `M${x0},${y0} A${G.RG},${G.RG} 0 0 1 ${x1},${y1}`;
      el('path', { d, fill: 'none', stroke: 'transparent', 'stroke-width': 34 }, g);
      el('path', { d, fill: 'none', stroke: C(S.COLOR[m]), 'stroke-width': 7, 'stroke-linecap': 'round' }, g);
      const below = Math.sin(S.ANG[m]) > 0;
      arcLabel(name, below ? G.RG + 22 : G.RG + 12, S.ANG[m], below, 11, 3, C(S.COLOR[m]), g);
      L.mod[m] = g;
    }
    // SKY2: the heart is the watch — its tone, its age under the name, a beat at each of its beats.
    L.core = el('circle', { cx: G.cx, cy: G.cy, r: Math.round(17 * FC), fill: C('dim'), class: 'sky-heart' }, L.figure);
    label(G.cx, G.cy + Math.round(38 * FC), 'GLORFINDEL', C('blue'), Math.round(11 * Math.min(FC, 1.25)), 700, 'middle', L.figure, { 'letter-spacing': 2 });
    L.heart = label(G.cx, G.cy + Math.round(38 * FC) + 15, '', C('dim'), 9.5, 600, 'middle', L.figure);
    lastBeat = ''; heartAt = 0;
    L.watch = label(G.cx, G.cy - G.RG - 46, '', C('red'), 10.5, 700, 'middle', L.figure);
    // The suns, a system each: its orbit, its glow, a ring in the colour of the worst on its planets.
    L.sun = {};
    for (const b of laid.bodies.filter(x => x.planets.length)) {
      const [x, y] = b.pos, col = C(b.out ? 'dim' : 'yellow'), g = el('g', { 'data-s': b.id, class: 'sky-sun', tabindex: 0 }, L.suns);
      el('circle', { cx: x, cy: y, r: b.pr + 6, fill: 'transparent' }, g);   // SKY3: the pointer's reach, its orbit — no more
      el('circle', { cx: x, cy: y, r: b.pr, fill: 'none', stroke: C('border'), 'stroke-dasharray': b.out ? '3 5' : '2 4', opacity: 0.9 }, g);
      el('circle', { cx: x, cy: y, r: b.rs * 2.5, fill: col, opacity: b.out ? 0.05 : 0.1 }, g);
      const ring = el('circle', { cx: x, cy: y, r: b.rs + 5, fill: 'none', 'stroke-width': 2.4 }, g);
      el('circle', { cx: x, cy: y, r: b.rs, fill: col, 'fill-opacity': b.out ? 0.35 : 1 }, g);
      label(x, y + b.pr + 20, String(b.label || '').replace(/ · .*$/, ''), col, 10.5, 700, 'middle', g);
      label(x, y + b.pr + 32, `${b.planets.length} resource${b.planets.length > 1 ? 's' : ''}${b.out ? ' · out of reach' : ''}`, C('dim'), 9, 600, 'middle', g);
      L.sun[b.id] = { g, ring };
    }
    // The tiles: a star, a planet, a lone body — a group each, moved by its transform.
    L.star = {};
    for (const t of M.tiles) {
      const g = el('g', { 'data-a': t.key, class: 'sky-star', tabindex: 0 }, L.stars);
      el('circle', { r: 16, fill: 'transparent' }, g);
      el('circle', { r: 17, opacity: 0, 'data-glow': 1 }, g);
      [['d', 0], ['p', 1], ['r', 2]].forEach(([k, m]) => {
        const a0 = -Math.PI / 2 + m * 2 * Math.PI / 3 + 0.28, a1 = a0 + 2 * Math.PI / 3 - 0.56, rr = 11;
        el('path', { d: `M${Math.cos(a0) * rr},${Math.sin(a0) * rr} A${rr},${rr} 0 0 1 ${Math.cos(a1) * rr},${Math.sin(a1) * rr}`, fill: 'none', 'stroke-width': 2, 'data-h': k }, g);
      });
      el('circle', { r: 6.5, 'data-core': 1 }, g);
      label(17, 4, String(t.name || t.key).replace(/^vm-/, ''), t.out ? C('dim') : C('text'), 10, 600, 'start', g, { 'data-label': 1 });
      L.star[t.key] = g;
    }
  }

  // ── Painted at each refresh: colours, halos, what a hover dims, the watch's waves ─────────────────────────
  const served = f => S.served(f, M.tiles, laid.bodies, id => S.satOf(id, sats));
  const core = t => (t.out ? C('dim') : C({ red: 'red', orange: 'orange', green: 'green', wait: 'purple', verdict: 'blue', quiet: 'green' }[S.TONE(t.s)]));
  function paint() {
    const f = focusNow(), on = served(f);
    for (const t of M.tiles) {
      const g = L.star[t.key]; if (!g) continue;
      g.style.opacity = on && !on.has(t.key) ? '0.28' : '1';
      const c = g.querySelector('[data-core]');
      c.setAttribute('fill', core(t)); c.setAttribute('class', t.s.r === 'restoring' ? 'sky-pulse' : '');
      if (t.out) { c.setAttribute('fill-opacity', '0.35'); c.setAttribute('stroke', C('dim')); c.setAttribute('stroke-dasharray', '2 2'); }
      g.querySelectorAll('[data-h]').forEach(h => {
        const k = h.dataset.h, reach = k === 'd' ? !!t.s.d : !t.out && (k === 'p' ? !!t.s.p : t.s.r === 'protected' || t.s.r === 'restoring');
        h.setAttribute('stroke', reach ? C(S.COLOR[k]) : 'transparent'); h.setAttribute('opacity', reach ? '0.7' : '0');
      });
      const lone = grouped() && !!bodyOf.get(t.key)?.lone, glow = g.querySelector('[data-glow]');
      glow.setAttribute('fill', core(t)); glow.setAttribute('opacity', lone ? '0.14' : '0');
    }
    for (const [id, sun] of Object.entries(L.sun)) {
      const b = laid.bodies.find(x => x.id === id);
      // The worst on its planets; at the same rank, a card waiting before a verdict (LEG2, its relecture): never the order
      // of the tiles that decides the ring's colour.
      let worst = null;
      for (const k of b.planets) {
        const t = tileBy.get(k); if (!t) continue;
        const r = S.RANK(t.s), w = worst ? S.RANK(worst.s) : 0;
        if (r > w || (worst && r === w && S.TONE(worst.s) === 'verdict' && S.TONE(t.s) !== 'verdict')) worst = t;
      }
      sun.ring.setAttribute('stroke', worst ? core(worst) : 'transparent'); sun.ring.setAttribute('class', worst ? 'sky-pulse' : '');
      sun.g.style.opacity = !f || (f.s ? f.s === id : f.a ? bodyOf.get(f.a) === b : b.planets.some(k => on && on.has(k))) ? '1' : '0.3';
    }
    svg.querySelectorAll('[data-b]').forEach(g => {
      const b = sats[g.dataset.b];
      g.style.opacity = f && ((f.b && f.b !== g.dataset.b) || (f.m && b && b.mod !== f.m)) ? '0.35' : '1';
    });
    for (const [m, g] of Object.entries(L.mod)) g.style.opacity = f && f.m && f.m !== m ? '0.35' : '1';
    // The watch's own cards: red waves from the white core out to its border — two for a card, three for more.
    const n = M.watch ? Math.min(3, M.watch + 1) : 0;
    if (L.alarm.dataset.n !== String(n)) {
      L.alarm.dataset.n = String(n); L.alarm.replaceChildren();
      for (let i = 0; i < n; i++) {
        const r0 = Math.round(17 * FC);
        const c = el('circle', { cx: G.cx, cy: G.cy, r: M.reduced ? Math.round(42 * FC) : r0, fill: 'none', stroke: C('red'), 'stroke-width': 2.6 }, L.alarm);
        if (M.reduced) continue;
        const begin = `${(-i * 1.8 / n).toFixed(2)}s`;
        el('animate', { attributeName: 'r', from: r0, to: G.RG - 7, dur: '1.8s', begin, repeatCount: 'indefinite' }, c);
        el('animate', { attributeName: 'opacity', values: '0.95;0.6;0', dur: '1.8s', begin, repeatCount: 'indefinite' }, c);
      }
    }
    L.watch.textContent = M.watch ? `⚠ ${M.watch} card${M.watch > 1 ? 's' : ''} of the watch` : '';
    const subs = new Map(MODS.flatMap(([m]) => (M.backends[m] || []).map(b => [b.id, String(b.sub || '')])));
    for (const [id, e] of Object.entries(L.bsub || {})) { const t = subs.get(id) || ''; if (e.textContent !== t) e.textContent = t; }
    heart();
  }
  // The heart: the watch's tone, its age; a new beat of the watch, a beat of the heart (none under reduced motion).
  function heart() {
    const h = M && typeof M.heartOf === 'function' ? M.heartOf() : null;
    if (!h || !L.core) return;
    const col = C(h.tone);
    if (L.core.getAttribute('fill') !== col) L.core.setAttribute('fill', col);
    L.heart.setAttribute('fill', col); L.heart.textContent = h.short;
    if (h.beat && h.beat !== lastBeat) {
      if (lastBeat && !M.reduced) { L.core.setAttribute('class', 'sky-heart'); L.core.getBoundingClientRect(); L.core.setAttribute('class', 'sky-heart sky-beat'); }
      lastBeat = h.beat;
    }
  }

  // ── Where each tile is now, and the lines: at each refresh, and at each frame while the planets turn ───────
  function at(t) {
    const b = bodyOf.get(t.key);
    if (!b) return [G.cx, G.cy];
    return b.lone ? b.pos : S.planetAt(b, b.planets.indexOf(t.key), tau);
  }
  function place() {
    for (const t of M.tiles) {
      const g = L.star[t.key], b = bodyOf.get(t.key); if (!g || !b) continue;
      const [x, y] = at(t), planet = !b.lone, lone = grouped() && !planet, gr = grow.get(b.id) || 0;
      const sc = planet ? 0.8 + 0.2 * gr : lone ? 1.8 : 1;
      g.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${sc.toFixed(3)})`;
      const lab = g.querySelector('[data-label]'), right = planet ? x >= b.pos[0] - 1 : x >= G.cx - 5;
      lab.setAttribute('x', right ? 17 : -17); lab.setAttribute('text-anchor', right ? 'start' : 'end');
      lab.setAttribute('font-size', (10 / sc).toFixed(2)); lab.setAttribute('stroke-width', (3.5 / sc).toFixed(2));
      lab.setAttribute('opacity', planet ? Math.max(gr, S.RANK(t.s) ? 1 : 0).toFixed(2) : '1');
    }
  }
  function from(id, mod) {
    const sat = id && !id.endsWith(':arc') ? S.satOf(id, sats) : '';
    if (sat) return { p: sats[sat].at, lane: S.laneOf(laneIx[sat], grouped()), sat };
    const m = mod || id.split(':')[0];
    return { p: S.polar(S.ANG[m] || 0, G.RG + 4), lane: S.laneOf(0, grouped()), sat: m + ':arc' };
  }
  // A line kept from frame to frame: its animation runs on, only its path follows.
  function line(key, a) {
    let p = LINKS.get(key);
    if (!p) { p = el('path', { fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, L.links); LINKS.set(key, p); }
    if (p.getAttribute('d') !== a.d) p.setAttribute('d', a.d);
    if (p.getAttribute('stroke') !== a.stroke) p.setAttribute('stroke', a.stroke);
    if (p.getAttribute('stroke-width') !== String(a.width)) p.setAttribute('stroke-width', String(a.width));
    if (p.getAttribute('opacity') !== String(a.opacity)) p.setAttribute('opacity', String(a.opacity));
    if ((p.getAttribute('class') || '') !== a.cls) p.setAttribute('class', a.cls);
    p.dataset.gen = String(gen);
  }
  function lines() {
    gen++;
    const f = focusNow(), on = served(f);
    for (const t of M.tiles) {
      const mine = !!f && f.a === t.key, here = !!(on && on.has(t.key)), b = bodyOf.get(t.key), planet = !!b && !b.lone;
      for (const l of S.linesOf(t, mine || (here && !(grouped() && planet)))) {
        const src = from(l.from);
        const lit = S.lit(f, mine, here, src.sat, (sats[src.sat] || {}).mod);
        if (!lit && l.faint) continue;
        // LEG2 (its relecture): its stroke in its key, and a step of its own when it waits — a line waiting never lost
        // under the line done of its colour (an isolation, its check that failed; a block, another to approve).
        const to = at(t), sh = (S.SHIFT[l.c] || 0) + (l.wait ? S.SHIFT.wait : 0);
        const pts = planet ? S.intoSystem(src.p, b.pos, b.pr, to, src.lane, sh) : S.route(src.p, to, src.lane, sh);
        line(`${t.key}|${src.sat}|${l.c}|${l.wait ? 'w' : l.pulse ? 'p' : 's'}`, { d: S.toPath(pts), stroke: C(l.c), width: l.faint ? 1.4 : 2.6,
          opacity: !lit ? 0.08 : l.faint ? 0.55 : 0.95, cls: l.wait ? 'sky-flow' : l.pulse ? 'sky-pulse' : '' });
      }
    }
    // Among the systems, a hover's quiet lines go to the sun: one per satellite, as thick as what it serves.
    if (grouped() && f && !f.a) for (const b of laid.bodies.filter(x => x.planets.length)) {
      if (f.s && f.s !== b.id) continue;
      const by = new Map();
      for (const k of b.planets) for (const l of S.linesOf(tileBy.get(k), true)) {
        const src = from(l.from), x = by.get(src.sat) || { n: 0, c: S.COLOR[(sats[src.sat] || {}).mod || src.sat.split(':')[0]], src };
        x.n++; by.set(src.sat, x);
      }
      for (const [sat, x] of by) {
        if ((f.b && sat !== f.b) || (f.m && !(sat === f.m + ':arc' || (sats[sat] && sats[sat].mod === f.m)))) continue;
        line(`sun|${b.id}|${sat}`, { d: S.toPath(S.route(x.src.p, b.pos, x.src.lane, 0)), stroke: C(x.c || 'blue'),
          width: (1.1 + 0.5 * Math.min(x.n, 12)).toFixed(1), opacity: 0.45, cls: '' });
      }
    }
    for (const [k, p] of LINKS) if (p.dataset.gen !== String(gen)) { p.remove(); LINKS.delete(k); }
  }

  // ── The planets' frame, the gestures ────────────────────────────────────────────────────────────────────
  function frame(now) {
    raf = 0;
    if (!svg || !svg.isConnected) { last = null; return; }      // the view left: no frame until it is back
    const dt = last === null ? 0 : Math.min(0.1, (now - last) / 1000); last = now;
    const f = focusNow();
    let moving = grouped() && !f && !M.reduced;
    if (moving) tau += dt;
    for (const b of laid.bodies.filter(x => x.planets.length)) {
      const target = f && (f.s === b.id || (f.a && bodyOf.get(f.a) === b)) ? 1 : 0, g0 = grow.get(b.id) || 0;
      const g = M.reduced ? target : g0 + (target - g0) * Math.min(1, dt * 7), next = Math.abs(target - g) < 0.003 ? target : g;
      if (next !== g0) { grow.set(b.id, next); moving = true; }
    }
    if (moving) { place(); lines(); onPlace(); }
    if (now - heartAt >= 1000) { heartAt = now; heart(); }      // the watch's age, second by second
    raf = requestAnimationFrame(frame);
  }
  function focusOf(target) {
    const e = target && target.closest ? target : null; if (!e) return null;
    // SKY3 (#1246): read within the sky only. The page's <body> carries a data-m of its own (the phone's tab, « judge »):
    // read as a module, an empty spot of the sky took a focus on no module and dimmed everything (measured on Imladris).
    const up = sel => { const x = e.closest(sel); return x && svg && svg.contains(x) ? x : null; };
    const a = up('[data-a]'), s = up('[data-s]'), b = up('[data-b]'), m = up('[data-m]');
    return a ? { a: a.dataset.a } : s ? { s: s.dataset.s } : b ? { b: b.dataset.b } : m ? { m: m.dataset.m } : null;
  }
  const same = (x, y) => JSON.stringify(x || null) === JSON.stringify(y || null);
  function set(h, p) {
    const before = focusNow(), pinned = pin;
    hover = h; pin = p;
    if (!same(before, focusNow())) { paint(); lines(); onFocus(focusNow()); }
    else if (!same(pinned, pin)) onFocus(focusNow());   // SKY4: pinned or let go under the pointer — the card follows the pin
  }
  // SKY3 (#1246; Jonathan 26/11, on Imladris): a hover waits a moment before it dims the rest — the pointer that only
  // passes, entering the sky or going from one body to the next, lights nothing; leaving the sky is at once, the
  // keyboard and a click too.
  const HOVER_MS = 140;
  let hoverTimer = 0;
  function wantHover(h) {
    clearTimeout(hoverTimer);
    if (same(h, hover)) return;
    hoverTimer = setTimeout(() => set(h, pin), HOVER_MS);
  }
  function listen() {
    svg.addEventListener('mouseover', ev => wantHover(focusOf(ev.target)));
    svg.addEventListener('mouseleave', () => { clearTimeout(hoverTimer); set(null, pin); });
    svg.addEventListener('focusin', ev => set(focusOf(ev.target), pin));
    svg.addEventListener('click', ev => { const f = focusOf(ev.target); set(hover, same(f, pin) ? null : f); });
    // The keyboard pins as a click does: Enter or Space on what has the focus, again to let go.
    svg.addEventListener('keydown', ev => {
      if (ev.key !== 'Enter' && ev.key !== ' ') return;
      const f = focusOf(ev.target); if (!f) return;
      ev.preventDefault(); set(hover, same(f, pin) ? null : f);
    });
  }

  // SKY4: where a focus is drawn, and Glorfindel's disc, in the page's pixels — the floating card's place.
  function elOf(f) {
    if (!svg || !f) return null;
    return (f.a ? L.star[f.a] : f.s ? (L.sun[f.s] || {}).g : f.m ? L.mod[f.m]
      : f.b ? [...svg.querySelectorAll('[data-b]')].find(g => g.dataset.b === f.b) : null) || null;
  }
  function rectOf(f) { const e = elOf(f); return e ? e.getBoundingClientRect() : null; }
  // The relecture of SKY4: the card closed from within (its ✕, Escape), the keyboard's focus given back to what was
  // pinned — never dropped on the page's body.
  function focusOn(f) { const e = elOf(f); if (e && typeof e.focus === 'function') e.focus({ preventScroll: true }); }
  // SKY6: the svg fitted to its box (« meet »): the drawing where its matrix puts it, never at the box's top left.
  function centre() {
    const m = typeof svg.getScreenCTM === 'function' ? svg.getScreenCTM() : null;
    if (m && m.a) return { x: m.a * G.cx + m.e, y: m.d * G.cy + m.f, r: (G.RG + 46) * m.a };
    const r = svg.getBoundingClientRect(), k = r.width / G.W;
    return { x: r.left + G.cx * k, y: r.top + G.cy * k, r: (G.RG + 46) * k };
  }
  // SKY6: the sky fitted to its box — the drawing centred, or at its top in a tall box (the lists under it).
  function align(how) { if (svg && svg.getAttribute('preserveAspectRatio') !== `${how} meet`) svg.setAttribute('preserveAspectRatio', `${how} meet`); }
  // SKY6: a line of To judge or of the feed pins its tile, as a click on it in the sky would.
  function pinTo(f) { set(hover, f); }
  // SKY6: a planet's system (the bubble keeps beside it whole, never over its sun); a lone body, none.
  function systemOf(key) { const b = bodyOf && bodyOf.get(key); return b && b.planets && b.planets.length && L.sun && L.sun[b.id] ? b.id : null; }
  return { mount, focus: () => focusNow(), pinned: () => pin, unpin: () => set(hover, null), pinTo, align, systemOf, rectOf, centre, focusOn, _served: served };
})();
