// GRP1 (#1189; Jonathan 25/11, on a mockup, option B): the infrastructure map grouped by subscription or by
// resource group, and what is out of reach. Pure — no page, no fetch: what glorfindel.js draws is decided
// here, and the suite runs it as it is (tests/unit/test_console_groups.py, through tests/unit/js_engine.py).
//
// - A tile's place, read in its resource id: its subscription, masked as /api/config sends the watch's (its
//   first 8 characters, « … », its last 4: SEC1), in lower case — the key SUBN1 names it by; never whole —,
//   and its resource group. Entra ID's tile is the tenant's; the control plane's own tile (IDT1) the watch's.
// - Out of reach: a subscription read in its id, the watch's known, and not the same — a watch acts only in
//   its own (one watch, one subscription: WrongSubscriptionError). Unknown: never said out of reach.
// - The lanes: the tenant first, then the watch's subscription, the others by name, the unknown last; each
//   tile in its lane in the order of its slot (the operator's, dragged). A lane is named by the
//   subscription's name when the watch serves it (SUBN1, `subscriptions.names` of /api/watch/status), else
//   by its masked id. A name comes from outside: the page escapes it.
// - The choice (none, subscription, resource group) kept in this browser, as the tiles' order: each
//   browser its own, nothing written on the server. A storage that throws or forgets: none, said by nothing.
const InfraGroups = (() => {
  const MODES = ['none', 'subscription', 'rg'];
  const KEY = 'glorfindel_group_by';
  const mask = s => (s ? `${s.slice(0, 8)}…${s.slice(-4)}` : '');
  const own = watch => String(watch || '').toLowerCase();

  function place(tile, watch) {
    if (tile.kind === 'identity') return { tenant: true, sub: '', rg: '' };
    const m = /^\/subscriptions\/([^/]+)(?:\/resourceGroups\/([^/]+))?/i.exec(String(tile.resource_id || ''));
    if (m) return { tenant: false, sub: mask(m[1]).toLowerCase(), rg: m[2] || '' };
    if (tile.kind === 'control_plane') return { tenant: false, sub: own(watch), rg: '' };
    return { tenant: false, sub: '', rg: '' };
  }

  function outOfReach(tile, watch) {
    const p = place(tile, watch);
    return !!(own(watch) && p.sub && p.sub !== own(watch));
  }

  // SUBN1: { name: text | null, error: text | null } under the masked key; anything else, no name.
  function named(key, names) {
    const n = names && typeof names === 'object' && Object.hasOwn(names, key) ? names[key] : null;
    if (!n || typeof n !== 'object') return { name: '', error: '' };
    return { name: typeof n.name === 'string' ? n.name.trim() : '', error: typeof n.error === 'string' ? n.error : '' };
  }

  function laneOf(p, mode, watch, names) {
    if (p.tenant) return { key: 'tenant', label: 'tenant', title: "Entra ID: the tenant's, above every subscription", rank: 0, sort: '' };
    if (!p.sub) return { key: '?', label: 'subscription unknown', title: 'no subscription in its id', rank: 3, sort: '' };
    const n = named(p.sub, names);
    const sub = n.name || p.sub;
    const mine = !!own(watch) && p.sub === own(watch);
    const out = !!own(watch) && !mine;
    const where = mode === 'rg' && p.rg ? `${sub} / ${p.rg}` : sub;
    const tail = mode === 'rg' ? (out ? ' · out of reach' : '')
      : mine ? ' · Glorfindel acts here' : out ? ' · seen, out of reach' : '';
    const title = `subscription ${p.sub}${n.name ? ` (${n.name})` : n.error ? ` — its name not read: ${n.error}` : ''}`
      + (out ? " — not the watch's: it acts only in its own" : '');
    return { key: mode === 'rg' ? `${p.sub}/${p.rg.toLowerCase()}` : p.sub, label: where + tail, title,
             own: mine, out, rank: mine ? 1 : 2, sort: `${sub.toLowerCase()}\u0000${p.rg.toLowerCase()}` };
  }

  // [{ key, label, title, own, out, tiles: [the tiles, in the order given] }] — the tiles given in their
  // slots' order.
  function lanes(tiles, mode, watch, names) {
    const by = new Map();
    for (const t of tiles) {
      const lane = laneOf(place(t, watch), mode, watch, names);
      if (!by.has(lane.key)) by.set(lane.key, { ...lane, tiles: [] });
      by.get(lane.key).tiles.push(t);
    }
    return [...by.values()].sort((a, b) => a.rank - b.rank || (a.sort < b.sort ? -1 : a.sort > b.sort ? 1 : 0));
  }

  // The storage given by a function: the browser's own may throw on its very read (a private window).
  function load(storage) {
    try { const g = storage().getItem(KEY); return MODES.includes(g) ? g : 'none'; } catch (e) { return 'none'; }
  }
  function save(storage, mode) {
    try { storage().setItem(KEY, mode); return true; } catch (e) { return false; }
  }

  return { MODES, KEY, mask, place, outOfReach, lanes, load, save };
})();
