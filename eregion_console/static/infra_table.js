// TBL1 (#1230; Jonathan 26/11, on a mockup): the infrastructure map as a table — a row per tile, its three
// modules as pills, rows that open each on its own and several at once (the tile in full under its row: the
// maintainer's condition), what asks for the eye opened by itself, a row the operator folds staying folded until
// its next incident; the totals as filters; the choice « tiles · table » kept in this browser, the table by
// default on a phone beyond 8 resources. Pure — no page, no fetch: what glorfindel.js draws is decided here, and
// the suite runs it as it is (tests/unit/test_console_table.py, through tests/unit/js_engine.py).
//
// A tile's summary, given by the page (glorfindel.js _tileSummary): { key, d, p, a, r } —
//   d: 'watched' | 'judge' | 'card' | null     (a decision to judge on it; only cards that are not decisions —
//                                              a posture gap, a quarantine altered —; null: no DETECT, an NSG)
//   p: 'ready' | 'blocked' | 'isolated' | 'both' | null   (null: PROTECT does not reach it — out of reach, a
//                                              tile of its own)
//   a: true when an action held waits for an approval on it
//   r: 'protected' | 'restoring' | 'unread' | null   (unread: the vaults' inventory not read yet; null: no vault
//                                              of the watch's holds it, or none is configured)
const InfraTable = (() => {
  const VIEWS = ['tiles', 'table'];
  const KEY = 'glorfindel_infra_view';
  const PHONE_TABLE_OVER = 8;               // on a phone, the table by default beyond this many resources
  const FILTERS = {
    judge: s => s.d === 'judge',
    approve: s => s.a === true,
    isolated: s => s.p === 'isolated' || s.p === 'both',
    blocked: s => s.p === 'blocked' || s.p === 'both',
    restoring: s => s.r === 'restoring',
  };

  // The view: the one this browser chose, else the table on a phone beyond 8 resources, else the tiles. A
  // storage that throws or forgets: the default, said by nothing.
  function view(storage, phone, count) {
    let kept = null;
    try { kept = storage().getItem(KEY); } catch (e) { kept = null; }
    if (VIEWS.includes(kept)) return kept;
    return phone && count > PHONE_TABLE_OVER ? 'table' : 'tiles';
  }
  function save(storage, v) {
    if (!VIEWS.includes(v)) return false;
    try { storage().setItem(KEY, v); return true; } catch (e) { return false; }
  }

  // What asks for the eye: a card on it, a block, an isolation, an action to approve, a restore in course.
  function asks(s) {
    return s.d === 'judge' || s.d === 'card' || s.a === true || ['blocked', 'isolated', 'both'].includes(s.p) || s.r === 'restoring';
  }
  // What a row's three pills say, and their tone (a class of the page): DETECT, PROTECT, RECOVER. Words of the
  // product, in English; « — » where the module does not reach.
  const NONE = ['—', 'none'];
  function cells(s) {
    const d = s.d === 'judge' ? ['to judge', 'wait'] : s.d === 'card' ? ['a card', 'wait'] : s.d === 'watched' ? ['watched', 'quiet'] : NONE;
    const p = s.a === true ? ['to approve', 'wait']
      : s.p === 'both' ? ['isolated · blocked', 'red'] : s.p === 'isolated' ? ['isolated', 'red']
      : s.p === 'blocked' ? ['blocked', 'orange'] : s.p === 'ready' ? ['ready', 'quiet'] : NONE;
    const r = s.r === 'restoring' ? ['restoring', 'green'] : s.r === 'protected' ? ['protected', 'quiet']
      : s.r === 'unread' ? ['not read', 'none'] : NONE;
    // The row's dot: the worst of what is on it, as a tile's dot says it.
    const dot = ['isolated', 'both'].includes(s.p) ? 'red' : s.p === 'blocked' ? 'orange' : s.r === 'restoring' ? 'green'
      : asks(s) ? 'wait' : 'quiet';
    return { d, p, r, dot };
  }
  // Open: opened by the operator, or asking for the eye and not folded by the operator.
  function isOpen(s, rows) { return rows.opened.has(s.key) || (asks(s) && !rows.folded.has(s.key)); }
  function toggle(s, rows) {
    if (isOpen(s, rows)) { rows.opened.delete(s.key); rows.folded.add(s.key); }
    else { rows.opened.add(s.key); rows.folded.delete(s.key); }
  }
  // At each refresh: a row folded on an incident that has passed forgets its fold — its next incident opens it
  // again, as a tile does today (_collapsedVms). A row no longer on the map forgets both.
  function settle(summaries, rows) {
    const keys = new Set(summaries.map(s => s.key));
    for (const s of summaries) if (!asks(s)) rows.folded.delete(s.key);
    for (const k of [...rows.opened]) if (!keys.has(k)) rows.opened.delete(k);
    for (const k of [...rows.folded]) if (!keys.has(k)) rows.folded.delete(k);
  }
  function openAll(summaries, rows) { summaries.forEach(s => { rows.opened.add(s.key); rows.folded.delete(s.key); }); }
  function foldAll(summaries, rows) { summaries.forEach(s => { rows.opened.delete(s.key); rows.folded.add(s.key); }); }

  function totals(summaries) {
    return Object.fromEntries(Object.entries(FILTERS).map(([k, f]) => [k, summaries.filter(f).length]));
  }
  // The rows a filter keeps: a filter not of the list keeps them all.
  function filtered(summaries, filter) {
    return Object.hasOwn(FILTERS, filter) ? summaries.filter(FILTERS[filter]) : summaries;
  }

  return { VIEWS, KEY, PHONE_TABLE_OVER, FILTERS, view, save, asks, cells, isOpen, toggle, settle, openAll, foldAll, totals, filtered,
           rows: () => ({ opened: new Set(), folded: new Set() }) };
})();
