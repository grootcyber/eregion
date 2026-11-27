// The console's shared header (docs/design/console.md): EREGION, then the tabs — Overview,
// Glorfindel always, Dagorlad (Annatar's and Gothmog's runs, §7) greyed while neither injector is
// set up (/api/sections) —, then on the right the model breaker while one of its cards is open
// (MBV1), Config, and the clock in UTC, like every time shown in the console. The same on every
// page: what belongs to one page (the live feed's dot) stays in that page. Each page calls
// Console.init(<its tab>) first.
// HRT1 (#1272; Jonathan 27/11): the watch's beat and the return channel are no longer in the header — the watch is
// said where Glorfindel is drawn (the 360°'s heart, the table's GLORFINDEL, the overview's, Dagorlad's), from one
// reading told to each place (onWatch); the return channel where its runs are (the overview's CHANNELS, Dagorlad's
// GLORFINDEL and the Runs view's: channelSaid), and V1 with it, at their head (gateSaid).
// SKY2 (#1241): what the watch's beat says — its tone and its words, the header's and the 360°'s alike (one source,
// never two that disagree). The watch is read every 15 s, the clock ticks every second: its age goes on between two
// reads (`seen`, when it was read), and past the server's threshold a running watch is said stale, as the server
// would say it at its next read. `beat`: the watch's last beat as the server gives it (`since`, its heartbeat's
// time) — a new one makes the 360°'s heart beat; a running watch's only. A read that failed (`failed`): unknown,
// grey, until a read succeeds.
const WATCH_STALE_S = 90;                 // api.py _heartbeat: running under 90 s, stale after
function watchSaid(w, now) {
  if (!w || typeof w !== 'object' || w.failed) return { tone: 'dim', text: 'watch unknown', short: 'unknown', beat: '' };
  const extra = w.seen ? Math.max(0, (now - w.seen) / 1000) : 0;
  const raw = Math.max(0, (Number(w.age_s) || 0) + extra), age = Math.round(raw);
  const status = w.status === 'running' && raw >= WATCH_STALE_S ? 'stale' : w.status;   // the server's threshold, on the age unrounded
  const tone = { running: 'green', stale: 'orange', stopped: 'red' }[status] || 'dim';
  const text = status === 'running' ? `watch · ${age}s ago`
    : status === 'stale' ? `watch stale · ${Math.round(age / 60)}m ago` : `watch ${status || 'unknown'}`;
  const short = status === 'running' ? `${age}s ago`
    : status === 'stale' ? `stale · ${Math.round(age / 60)}m ago` : String(status || 'unknown');
  const beat = status === 'running' && typeof w.since === 'string' ? w.since : '';
  return { tone, text, short, beat };
}

const Console = (() => {
  const TABS = [
    { id: 'overview',   label: 'Overview',   href: '/',           role: 'Eregion at a glance' },
    { id: 'glorfindel', label: 'Glorfindel', href: '/glorfindel' },
    { id: 'dagorlad',   label: 'Dagorlad',   href: '/dagorlad',   role: 'attacks and faults drawn against Glorfindel, and their runs' },
  ];
  // On the right, where the War Room had it (Jonathan, 26/10).
  const CONFIG = { id: 'config', label: '⚙ Config', href: '/config', role: 'how Glorfindel and this console are set' };
  let active = null, sections = null, judge = null;
  let lastWatch = null;               // IDT1: /api/watch/status as last read
  const listeners = [];

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g,
      c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  const $ = id => document.getElementById(id);
  const section = id => ((sections && sections.sections) || []).find(s => s.id === id);
  const injectorActive = () => ['annatar', 'gothmog'].some(id => (section(id) || {}).active);

  function tab(t) {
    const s = section(t.id);
    // Dagorlad holds both injectors: greyed only once the sections say neither is set up here.
    const greyed = t.id === 'dagorlad' ? Boolean(sections) && !injectorActive() : Boolean(s && !s.active);
    const title = s ? `${s.label} — ${s.role}${greyed ? ' · not set up here: what it would add' : ''}`
      : `${t.label.replace('⚙ ', '')} — ${t.role}${greyed ? ' · neither Annatar nor Gothmog is set up here' : ''}`;
    const badge = t.id === 'glorfindel' && judge ? `<span class="badge" title="Cards to judge (7 days)">${judge}</span>` : '';
    return `<a class="tab${t.id === active ? ' active' : ''}${greyed ? ' greyed' : ''}" href="${t.href}" title="${esc(title)}">${esc(t.label)}${badge}</a>`;
  }

  function renderTabs() {
    const nav = $('c-nav'), cfg = $('c-config');
    if (nav) nav.innerHTML = TABS.map(tab).join('');
    if (cfg) cfg.innerHTML = tab(CONFIG);
  }

  // What this console runs, beside the logo: the deployed tag, else the version and the commit.
  function renderVersion() {
    const el = $('c-version'), v = sections && sections.version;
    if (!el || !v) return;
    el.textContent = v.label;
    el.title = [v.ref && `deployed tag ${v.ref}`, v.revision && `${v.source === 'checkout' ? 'checkout' : 'deployed'} commit ${v.revision}`,
                v.package && `package ${v.package}`].filter(Boolean).join(' · ');
  }

  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function refreshSections() {
    try {
      const d = await getJSON('/api/sections');
      if (d.error) throw new Error(d.error);
      sections = d;
    } catch (e) { return; }
    renderTabs();
    renderVersion();
    listeners.forEach(cb => { try { cb(sections); } catch (_) { /* a page's own error */ } });
  }

  async function refreshWatch() {
    try {
      const w = await getJSON('/api/watch/status');
      lastWatch = { ...w, seen: Date.now() };   // IDT1: what a page reads of the watch; SKY2: when it was read
      showWatch();
      setBreakers(w.model_breaker);
    } catch (e) {
      lastWatch = { ...(lastWatch || {}), failed: true, seen: Date.now() };   // SKY2: unknown until a read succeeds; the rest kept (IDT1)
      showWatch();
    }
  }
  // SKY2: what the watch says, from watchSaid — at each read, and at each second between two. HRT1: told to the places
  // that say it (onWatch), each the same reading at the same second: one age, one server's since, a missed beat alike.
  const watchers = [];
  function showWatch() {
    if (!lastWatch) return;
    const s = watchSaid(lastWatch, Date.now());
    watchers.forEach(cb => { try { cb(s, lastWatch); } catch (_) { /* a place's own error, never the others' */ } });
  }
  function onWatch(cb) {
    watchers.push(cb);
    if (lastWatch) { try { cb(watchSaid(lastWatch, Date.now()), lastWatch); } catch (_) { /* its own */ } }
  }
  // HRT1: a place's dot and words, written only when they change (its text, never markup).
  function paintWatch(el, s, words) {
    if (!el || !s) return;
    const text = `● ${words === 'short' ? s.short : s.text}`, color = `var(--${s.tone})`;
    if (el.textContent !== text) el.textContent = text;
    if (el.style.color !== color) el.style.color = color;
  }
  // HRT1: the return channel's words — the heartbeat the watch publishes, what a run on Orodruin reads — for the pages
  // where its runs are (Dagorlad's GLORFINDEL, the Runs view's), as the header said them. An age it was not given
  // (none published, unreadable): unknown, said — never 0 s nor NaN (A0).
  function channelSaid(rc) {
    const c = rc && typeof rc === 'object' ? rc : {};
    if (!c.configured) return { tone: 'dim', text: 'return channel off', title: 'No return channel: a run reads the local watch files' };
    if (c.error) return { tone: 'red', text: 'return channel unreadable', title: String(c.error) };
    const age = typeof c.age_s === 'number' && Number.isFinite(c.age_s) ? `${Math.round(c.age_s)}s ago` : 'age unknown';
    return { tone: c.alive ? 'green' : 'yellow', text: `return channel · ${age}`,
             title: c.alive === false ? 'A run on Orodruin reads this as no watch' : 'The heartbeat the watch publishes — what a run on Orodruin reads' };
  }
  // HRT1: V1, as a run reads it — the gate the console shows (api.py _watch_refusal): without a live watch of its
  // targets, a run is refused before any call to the cloud. Said at the head where its runs are (Dagorlad's
  // GLORFINDEL, the Runs view's), in red, its reason under it; null when a watch stands behind a run; unknown, said,
  // when the console could not read it.
  function gateSaid(gate) {
    if (typeof gate !== 'string') return { tone: 'dim', text: 'run gate unknown', title: 'The console could not read the gate a run passes (V1)' };
    return gate ? { tone: 'red', text: 'no live watch for a run', title: gate } : null;
  }

  // MBV1 (#1175): the model breaker's cards still open, on every page — until 00:00 UTC a detection may
  // not be seen by the model. Shown while one is open; a click leads to them (the page Glorfindel opens
  // them in place). An Ack closes a card, never the breaker: it resets at 00:00 UTC (model_budget._roll),
  // a provider's limit once a call is served — never told otherwise. A count, whoever gives it (#257).
  function setBreakers(n) {
    const pill = $('c-breaker');
    if (!pill) return;
    const count = Math.max(0, Math.floor(Number(n) || 0));
    pill.hidden = count === 0;
    $('c-breaker-label').textContent = count > 1 ? `model breaker ×${count}` : 'model breaker';
  }

  async function refreshJudge() {
    try {
      const q = await getJSON('/api/to-judge?since=7d');
      if (Array.isArray(q.cards)) setJudgeCount(q.cards.length);
    } catch (e) { /* the badge stays as it was */ }
  }

  function setJudgeCount(n) {
    const count = Number(n) || 0;       // a count, whoever gives it (#257)
    if (judge === count) return;
    judge = count;
    renderTabs();
  }

  // RTT1 (#1174): a cloud detection's title as its rule declares it (`rule_title`, RTT1a), read again as
  // the Python reads it (glorfindel/rule_title.py, `shown`) — the console never shows more: a string,
  // not empty, at most 80 characters, on one line, no control or invisible character, its spaces as one.
  // Else its type's neutral title; '' for any other type. Raw text: escaped where it lands (#254).
  const RULE_TITLE_MAX = 80;
  const CLOUD_NEUTRAL = { identity_change: 'Entra ID detection', control_plane_change: 'Control-plane detection' };
  function ruleTitle(card) {
    if (!card || !Object.hasOwn(CLOUD_NEUTRAL, card.escalation_type)) return '';
    const t = card.rule_title;
    if (typeof t !== 'string' || !t.trim() || [...t].length > RULE_TITLE_MAX || /[\p{C}\u2028\u2029]/u.test(t)) return '';
    return t.split(/\s+/).filter(Boolean).join(' ');
  }
  function cloudTitle(card) {
    return ruleTitle(card) || (card && Object.hasOwn(CLOUD_NEUTRAL, card.escalation_type) ? CLOUD_NEUTRAL[card.escalation_type] : '');
  }

  function tick() {
    const c = $('c-clock');
    if (c) c.textContent = new Date().toISOString().slice(11, 19) + ' UTC';
    showWatch();                          // SKY2: the watch's age goes on with the clock
  }

  // UTC, like the clock: HH:MM:SS today, else MM-DD HH:MM.
  function hms(v) {
    const d = v === null || v === undefined || v === '' ? null
      : new Date(typeof v === 'number' ? v * 1000 : v);
    if (!d || isNaN(d)) return '—';
    const iso = d.toISOString();
    return iso.slice(0, 10) === new Date().toISOString().slice(0, 10)
      ? iso.slice(11, 19) : `${iso.slice(5, 10)} ${iso.slice(11, 16)}`;
  }

  function init(page, opts = {}) {
    active = page;
    const h = $('console-header');
    h.classList.add('console');
    h.innerHTML = `<a class="logo" href="/" title="Eregion — Glorfindel defends, Annatar and Gothmog prove it">EREGION</a>
      <span id="c-version" class="ver"></span>
      <nav id="c-nav"></nav>
      <span class="spacer"></span>
      <a class="hstat c-breaker" id="c-breaker" href="/glorfindel?watch" hidden title="The model breaker tripped: until 00:00 UTC (a provider's limit: until a call is served), a detection may not be seen by the model. An Ack closes the card, not the breaker. Open its cards">⚡ <span id="c-breaker-label">model breaker</span></a>
      <nav id="c-config"></nav>
      <span id="c-clock"></span>`;
    renderTabs();
    tick(); setInterval(tick, 1000);
    refreshSections(); setInterval(refreshSections, 30000);
    refreshWatch(); setInterval(refreshWatch, 15000);
    if (typeof opts.onBreaker === 'function')
      $('c-breaker').addEventListener('click', ev => { ev.preventDefault(); opts.onBreaker(); });
    if (opts.judge !== false) { refreshJudge(); setInterval(refreshJudge, 30000); }
  }

  // A page that needs the sections (a greyed page, the overview, the config) subscribes.
  function onSections(cb) {
    listeners.push(cb);
    if (sections) cb(sections);
  }

  // IDT1: the watch's status as last read (/api/watch/status, every 15 s), null before the first.
  function watchStatus() { return lastWatch; }

  return { init, onSections, setJudgeCount, setBreakers, hms, esc, section, ruleTitle, cloudTitle, watchStatus, watchSaid,
           onWatch, paintWatch, channelSaid, gateSaid };
})();
